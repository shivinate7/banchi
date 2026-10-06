"""The transport both TCGplayer hosts share: one session cookie, one agent, one way to read a status.

`server/tcg_export.py` (the seller portal's CSV) and `server/order_transport.py` (the order API) each
make outbound calls with the same session. The cookie read, the agent, the no-redirect opener, the
socket handling and the status ladder were written twice (DEBT86). They live here once. Each host
keeps what is its own and passes it in: its refusal class and codes, its message text, its stderr
label, its timeout and size cap, and the shape of its own `_check_status` input.

THE MESSAGE NEVER CARRIES THE COOKIE. Nothing here builds a string from the credential or from a
response body.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request
from typing import Callable, Optional, Tuple

import envfile

# Read through `envfile.get_live`, never `get`: the session expires, the refusal tells the operator
# to replace the value, and `get` caches per process and could not pick the new one up.
COOKIE_ENV = "TCGPLAYER_STORE_COOKIE"
AGENT_ENV = "PKMNSCAN_TCG_USER_AGENT"
DEFAULT_AGENT = "pkmnscan/1 (+local; python-urllib)"

# What an expired session looks like on either host: a redirect to the portal's logon page.
LOGON_MARKER = "account/logon"
REDIRECTS = (301, 302, 303, 307, 308)


def agent() -> str:
    """The User-Agent: the operator's knob, else the honest default."""
    return (envfile.get_live(AGENT_ENV) or "").strip() or DEFAULT_AGENT


def read_cookie(label: str) -> Tuple[Optional[str], Optional[str]]:
    """The `Cookie:` header value and the problem with it: `(value, None)`, or `(None, "missing")`
    or `(None, "malformed")`. The host raises its own refusal for a problem, with its own code and
    its own words.

    THE WHOLE HEADER VALUE, NOT ONE TICKET. It is not established that `TCGAuthTicket_Production`
    is the only cookie either host requires, so the operator copies the whole header.
    """
    value = envfile.get_live(COOKIE_ENV)
    if not value:
        print(f"{label}: set {COOKIE_ENV} in the settings file", file=sys.stderr, flush=True)
        return None, "missing"
    if "=" not in value:
        print(f"{label}: {COOKIE_ENV} holds no name=value pair", file=sys.stderr, flush=True)
        return None, "malformed"
    return value, None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Hand a 3xx back to the caller instead of following it.

    FOLLOWING BLINDLY IS THE BUG THIS PREVENTS. An expired session answers a redirect to the logon
    page, and the default handler would fetch it and return a 200 full of HTML.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


def send(
    request: urllib.request.Request,
    *,
    timeout: float,
    max_bytes: int,
    unreachable: Callable[[Exception], Exception],
    dropped: Callable[[], Exception],
    dropped_on: tuple,
    error_body_guard: tuple = (),
) -> Tuple[int, dict, bytes]:
    """One request. Returns (status, headers, body) and raises only for a dead socket.

    A 3xx arrives as an `HTTPError` BECAUSE of `NoRedirect`; its headers carry the Location.
    `unreachable(caught)` builds the host's refusal for a `URLError`; `dropped()` builds it for any
    of `dropped_on` (each host's own list of socket failures). `error_body_guard` names the errors
    that turn an unreadable error body into an empty one, and is empty where the host never did.
    """
    opener = urllib.request.build_opener(NoRedirect)
    try:
        response = opener.open(request, timeout=timeout)
        return response.status, dict(response.headers), response.read(max_bytes + 1)
    except urllib.error.HTTPError as caught:
        try:
            body = caught.read(max_bytes + 1)
        except error_body_guard:
            body = b""
        return caught.code, dict(caught.headers), body
    except urllib.error.URLError as caught:
        raise unreachable(caught) from None
    except dropped_on:
        raise dropped() from None


def classify(status: int, headers: dict) -> str:
    """The one status ladder, as a name: ok, logon, redirect, unauthorized, forbidden, not_found,
    bad_route, rate_limited, unavailable or unexpected. Each host turns a name into its own refusal."""
    if status in REDIRECTS:
        return "logon" if LOGON_MARKER in str(headers.get("Location") or "").lower() else "redirect"
    if status >= 500:
        return "unavailable"
    return {200: "ok", 401: "unauthorized", 403: "forbidden", 404: "not_found",
            405: "bad_route", 429: "rate_limited"}.get(status, "unexpected")

