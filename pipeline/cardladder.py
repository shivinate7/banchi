"""Card Ladder reads with the owner's own login (D320, My Slabs spec sections 2, 3, 5).

One client, one send path. `Client.send` is where every request goes, the token exchange
included, so the three bounds the owner set hold in one place:

- only the callables in `ALLOWED_CALLABLES` are called (`Client.call` reads that constant);
- `search.cardladder.com` is never reached (`BLOCKED_HOSTS`, checked before the transport);
- callable sends are `PACE_SECONDS` apart, and a rate-limit answer stops the client for good.

The refresh token comes from the caller (the server reads `CARDLADDER_REFRESH_TOKEN`).
No exception, log line or repr holds a token or a response body: errors carry a status code
and a name only. The transport defaults to `net_transport` (`net.open`); the clock and sleep
are injected, and a test may inject a transport too.
"""

from __future__ import annotations

import json
import threading
import urllib.parse

from pipeline import net

# Card Ladder's public web config (a Firebase web key, not a secret).
API_KEY = "AIzaSyBqbxgaaGlpeb1F6HRvEW319OcuCsbkAHM"
TOKEN_URL = "https://securetoken.googleapis.com/v1/token?key=" + API_KEY
CALLABLE_BASE = "https://us-central1-cardladder-71d53.cloudfunctions.net/"
KEY_NAME = "CARDLADDER_REFRESH_TOKEN"

# The six read callables of spec 3.1 to 3.6. The callables that write, sync or scrape (spec 3.8)
# are not here and never go here.
ALLOWED_CALLABLES = frozenset({
    "httpcertlookup", "httpprofile", "httpprofilesales",
    "httpcardestimate", "httpsaleprofile", "httpIndexFromDescription",
})
BLOCKED_HOSTS = frozenset({"search.cardladder.com"})  # Cloudflare challenge; never solved or avoided

PACE_SECONDS = 8.0  # spec 5: 8 s held for about 600 calls; 3 s drew a refusal after about 8
REFRESH_MARGIN = 300.0  # refresh the ID token this long before it expires (capped at a fifth of its life)

# Card Ladder maps these to `beckett` (spec 3.1).
GRADERS = {"psa": "psa", "beckett": "beckett", "bgs": "beckett", "bvg": "beckett", "sgc": "sgc", "cgc": "cgc"}


class CardLadderError(Exception):
    """Any failure. Its text never holds a token or a response body."""


class Refused(CardLadderError):
    """A callable off the allow list, or a blocked host. Raised before any request is sent."""


class RateLimited(CardLadderError):
    """Card Ladder said "Too many requests". The client sends nothing more."""


class TokenRejected(CardLadderError):
    """The refresh-token exchange failed."""


def net_transport(method, url, headers, body):
    """The default transport: any HTTP answer comes back as (status, body), so the Client reads it.

    A write (`idempotent=False`) is sent again only when the connect never opened, and a 3xx is an
    answer, so no header or token goes to a second host. `net.Offline` and `net.Dropped` leave it.
    """
    status, _headers, answer = net.open(
        url, method=method, data=body, headers=headers, idempotent=False, follow_redirects=False)
    return status, answer


class Client:
    def __init__(self, *, refresh_token, transport=None, clock, sleep):
        self._refresh_token = refresh_token
        self._transport = transport or net_transport  # (method, url, headers, body: bytes) -> (status, body: bytes)
        self._clock = clock
        self._sleep = sleep
        self._id_token = None
        self._refresh_at = 0.0
        self._last_send = None  # clock time of the last callable send, failed ones included
        self._limited = False
        self._lock = threading.RLock()  # the token refresh sends through `send`

    def send(self, method, url, headers, body):
        """The one send path."""
        host = urllib.parse.urlsplit(url).hostname
        if host in BLOCKED_HOSTS:
            raise Refused("Card Ladder host %s is never called." % host)
        if self._limited:
            raise RateLimited("Card Ladder rate-limited this sweep. Try again tomorrow.")
        if host == urllib.parse.urlsplit(CALLABLE_BASE).hostname:
            if urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1] not in ALLOWED_CALLABLES:
                raise Refused("That Card Ladder callable is not on the allow list.")
            with self._lock:
                if self._last_send is not None:
                    wait = self._last_send + PACE_SECONDS - self._clock()
                    if wait > 0:
                        self._sleep(wait)
                if self._limited:  # another thread's 429 landed while this one waited
                    raise RateLimited("Card Ladder rate-limited this sweep. Try again tomorrow.")
                self._last_send = self._clock()
        try:
            return self._transport(method, url, headers, body)
        except Exception as exc:
            # A 429 comes back as a status, not a raise, so a raise never latches.
            # The transport's own text can hold the request, so only its type survives.
            raise CardLadderError("The request to %s failed (%s)." % (host, type(exc).__name__)) from None

    def _token(self):
        with self._lock:
            return self._token_locked()

    def _token_locked(self):
        if self._id_token is not None and self._clock() < self._refresh_at:
            return self._id_token
        body = urllib.parse.urlencode(
            {"grant_type": "refresh_token", "refresh_token": self._refresh_token}).encode()
        status, answer = self.send(
            "POST", TOKEN_URL, {"Content-Type": "application/x-www-form-urlencoded"}, body)
        if status == 429:  # Google's limit on the exchange, not Card Ladder's: no latch
            raise CardLadderError(
                "Google (securetoken.googleapis.com) is limiting login exchanges. Try again later.")
        if status != 200:
            if 400 <= status < 500:  # only Google refusing the token says the token is bad
                raise TokenRejected("Google refused the login. Copy %s again." % KEY_NAME)
            raise CardLadderError(  # 5xx or 3xx: nothing is known about the token
                "Google (securetoken.googleapis.com) did not complete the login exchange. Try again later.")
        try:
            fields = json.loads(answer)
            token, life = fields["id_token"], float(fields["expires_in"])
        except (ValueError, KeyError, TypeError):
            raise TokenRejected("Google's token answer was not understood. Copy %s again." % KEY_NAME) from None
        self._id_token = token
        self._refresh_at = self._clock() + life - min(REFRESH_MARGIN, life / 5)
        return token

    def call(self, name, data):
        """POST {"data": data} to one allowed callable and return the answer's "result"."""
        if name not in ALLOWED_CALLABLES:
            raise Refused("Callable %r is not on the Card Ladder allow list." % (name,))
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + self._token()}
        status, answer = self.send(
            "POST", CALLABLE_BASE + name, headers, json.dumps({"data": data}).encode())
        if status != 200:
            text = answer.decode("utf-8", "replace")
            if status == 429 or "Too many requests" in text or "RESOURCE_EXHAUSTED" in text:
                self._limited = True
                raise RateLimited("Card Ladder rate-limited this sweep. Try again tomorrow.")
            raise CardLadderError("Card Ladder answered %d to %s." % (status, name))
        try:
            return json.loads(answer)["result"]
        except (ValueError, KeyError, TypeError):
            raise CardLadderError("Card Ladder's answer to %s was not understood." % name) from None


def _grader(grader):
    try:
        return GRADERS[str(grader).lower()]
    except KeyError:
        raise CardLadderError("Unknown grader %r." % (grader,)) from None


def cert_lookup(client, cert, grader):
    """3.1: the slab itself, with its card profile."""
    return client.call("httpcertlookup", {"cert": cert, "grader": _grader(grader), "includeProfile": True})


def profile(client, profile_id):
    """3.2: the whole card, every grade, its whole sales history."""
    return client.call("httpprofile", {"profileId": profile_id})


def profile_sales(client, cert, grader, grade):
    """3.3: up to 20 sales at this slab's grade."""
    return client.call("httpprofilesales", {"cert": cert, "grader": _grader(grader), "grade": grade})


def card_estimate(client, profile_id, grader, grade, description, qualifier_type, autograph_grade):
    """3.4: Card Ladder's value, its confidence and the sales speed."""
    return client.call("httpcardestimate", {
        "profileId": profile_id, "grader": _grader(grader), "grade": grade, "description": description,
        "qualifierType": qualifier_type, "autographGrade": autograph_grade})


def sale_profile(client, sale_id):
    """3.5: one sale in detail."""
    return client.call("httpsaleprofile", {"saleId": sale_id})


def index_from_description(client, description):
    """3.6: the card's market index and its daily sales total."""
    return client.call("httpIndexFromDescription", {"description": description})
