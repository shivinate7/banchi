"""The ONE outbound call this server makes, and the only place allowed to make it.

`server/capture_server.py` said for months that this process "holds no API key and makes no
outbound call". D33 broke half of that already — a route there can START A CHILD that spends
money — and rewrote the sentence rather than leaning on its letter. This file breaks the
other half literally: it reads a secret out of `.env`, and it opens a socket to a host on the
internet. Pretending otherwise by qualifying the promise to "no socket TO ANTHROPIC" is
exactly the technicality-narrowing D16 exists to catch, so the promise is replaced instead.

WHAT REPLACES IT, since a guarantee deleted and not replaced is a regression:

  - **One host, one method, one route.** `GET` against `store.tcgplayer.com`, and nothing
    else is reachable from here. The URL is a constant with an override that refuses to
    carry the cookie anywhere but https or loopback.
  - **It cannot cause a charge.** The Filtered Export is a download of the operator's own
    Pricing tab. `POST /pipeline/identify` is still the only route in this server that can
    put a number on an invoice, and this one is beside `join` — free and re-runnable.
  - **The secret never leaves this module.** It is read at call time, it is put in one
    header, and it is in no return value, no refusal message, no log line and no run
    directory. `CLAUDE.md`'s opsec rule for code cards is the same rule: a bearer instrument
    does not go in a file anyone else reads.
  - **Every anticipated failure has its own code**, because `docs/specs/capture-server.md`
    requires one and because the three that matter here — an expired session, a WAF block
    and a login page served as a 200 — are indistinguishable to a caller that only sees
    "the fetch failed".

WHY THIS EXISTS. `runs -> join` is otherwise autonomous: `identify` spawns detached (D33),
`join`, `emit` and `reconcile` are free and re-runnable, and the queues, the pricing table
and the import files are all reachable from a screen. The one step nobody could automate was
the operator going to TCGplayer, pressing Export Filtered CSV, waiting for the download and
uploading the file back. That is the manual step this removes, and D64 is the decision entry
— including the part it does NOT remove, which is that one fetch answers for one game.

STDLIB ONLY, like the rest of the server. `urllib.request` and not `requests`:
`requirements.txt` names that absence on purpose, and one more fetch is not a reason to
spend the dependency it was refused for.

THE AUTHENTICATION IS A COOKIE SESSION, WHICH WAS MEASURED RATHER THAN ASSUMED. Every seller
admin route answers `302 -> /admin/account/logon` unauthenticated:

    GET  /Admin/Pricing/DownloadMyExportCSV   302 -> /admin/account/logon?ReturnUrl=...
    GET  /admin/pricing/getjsonfilters        302 -> /admin/account/logon?ReturnUrl=...
    POST /admin/pricing/productsearch         302 -> /admin/account/logon?ReturnUrl=...

so a plain client carrying the portal's session cookies satisfies it. This is NOT the
order-management API, which lives on another host and answers `www-authenticate: Bearer` —
the two were conflated once while this was being scoped, and reached the wrong conclusion.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urljoin, urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import envfile  # noqa: E402

# The seller portal's own download. A constant rather than something a request can name: a
# route that fetched any URL a client sent, carrying the operator's session cookie, would be
# a credential-forwarding primitive guarded by an origin header.
DEFAULT_URL = "https://store.tcgplayer.com/Admin/Pricing/DownloadMyExportCSV"

# The cookie is a BEARER INSTRUMENT and lives in `.env` and nowhere else — gitignored, and
# denied to an agent by `.claude/settings.json`.
#
# READ THROUGH `envfile.get_live` AND NOT `envfile.get`, WHICH IS NOT A DETAIL: this session
# EXPIRES, and `tcg_session_expired` tells the operator to sign in again and replace the value
# in `.env`. `get` caches per process and, worse, cannot replace a value it already lifted out
# of the file — so under D53's supervisor, which runs for days and does not watch `.env`, that
# printed remedy would not have worked and the refusal would have repeated forever over a
# cookie the operator had already fixed. A bare name rather than a
# `PKMNSCAN_` one, which is this repo's existing split: knobs are prefixed, secrets are not
# (`ANTHROPIC_API_KEY`, `POKEMONTCG_API_KEY`).
COOKIE_ENV = "TCGPLAYER_STORE_COOKIE"

# Two knobs, and each exists because a named refusal points at it. The URL is how T7 aims
# this at a local socket instead of at TCGplayer; the agent is the first thing to try when
# the WAF refuses.
URL_ENV = "PKMNSCAN_TCG_EXPORT_URL"
AGENT_ENV = "PKMNSCAN_TCG_USER_AGENT"

# AN HONEST AGENT RATHER THAN A DISGUISED ONE, and the measurement is why it can be. AWS WAF
# sits on `store.tcgplayer.com` and blocks by request signature, so a block was a plausible
# outcome this build had to survive — but the stdlib default `Python-urllib/3.x` reaches the
# endpoint unblocked (302 to logon, identical to a browser UA), measured 2026-08-30 while
# unauthenticated. So there is no evidence that a disguise is needed, and this is the
# operator's own tooling against the operator's own account. If an AUTHENTICATED request is
# scored differently, `tcg_blocked` names `AGENT_ENV` as the remedy.
DEFAULT_AGENT = "pkmnscan/1 (+local; python-urllib)"

# Generous, because the portal builds the CSV before it sends it and a large catalog is not a
# failure — bounded, because a request that never answers is worse than one that refuses.
# `server/pipeline_routes.py` makes the same trade one constant over for a free step.
TIMEOUT_S = 120

# The widest export this project has ever read is ~1.5 MB (riftbound, 10,078 rows). Thirty-two
# megabytes is far past anything real and is a backstop against a body that never ends, not a
# judgement about how large an export may be.
MAX_BYTES = 32 * 1024 * 1024

# What an expired session looks like. The portal answers a 302 to its own logon page rather
# than a 401, so the redirect is what has to be read — which is why redirects are NOT followed
# blindly below. An HTML login page parsed as a CSV is the failure this prevents.
_LOGON_MARKER = "account/logon"


class FetchRefusal(Exception):
    """A refusal with its own code. `server/pipeline_routes.py` converts it to a 4xx.

    A private exception rather than `capture_server.BadRequest` or `PipelineRefusal`,
    because importing either would make this module depend on a file that imports it. The
    seam is one `except` clause at the one call site.

    THE MESSAGE NEVER CARRIES THE COOKIE. Every string built here is composed from a status
    code, a header this module chose, or a constant — never from the credential and never
    from a response body, which is where a portal would echo one back.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def endpoint() -> str:
    """The URL this fetch will use, and the check that the cookie may go there.

    HTTPS OR LOOPBACK, NOTHING ELSE. The override exists so T7 can point this at a socket it
    controls; the guard exists because a knob that redirects a session cookie is an
    exfiltration channel wearing a test seam. `http://127.0.0.1` is permitted because it
    cannot leave the machine, which is the same reason `store/files.py` trusts a local path.
    """
    override = (envfile.get_live(URL_ENV) or "").strip()
    if not override:
        return DEFAULT_URL
    parsed = urlparse(override)
    loopback = parsed.hostname in ("127.0.0.1", "::1", "localhost")
    if parsed.scheme == "https" or (parsed.scheme == "http" and loopback):
        return override
    raise FetchRefusal(
        "tcg_url_invalid",
        f"{URL_ENV} must be an https URL, or http on 127.0.0.1 for a local test. "
        f"The session cookie is not sent over plain http to anywhere else.",
    )


def _cookie() -> str:
    """The `Cookie:` header value, or the refusal that says where to put one.

    THE WHOLE HEADER VALUE, NOT ONE TICKET. `TCGAuthTicket_Production` is the cookie the
    session hangs on, and it is not established that it is the only one the portal requires —
    hard-coding one name would be a guess that fails as an expired session and sends the
    operator looking in the wrong place. Copying the whole `Cookie:` header out of the
    browser's network tab is one action and cannot be wrong about which cookies matter.
    """
    value = envfile.get_live(COOKIE_ENV)
    if not value:
        raise FetchRefusal(
            "tcg_cookie_missing",
            f"No {COOKIE_ENV} in .env, so there is no session to fetch the export with. "
            f"Sign in to store.tcgplayer.com, copy the whole `Cookie:` header off any "
            f"/admin/pricing request in the browser's network tab, and put it in .env as "
            f"{COOKIE_ENV}=<that value>. It is a bearer instrument: .env only.",
        )
    if "=" not in value:
        raise FetchRefusal(
            "tcg_cookie_malformed",
            f"{COOKIE_ENV} holds no `name=value` pair, so it is not a Cookie header. Copy "
            f"the whole header value, not just the ticket.",
        )
    return value


def _agent() -> str:
    return (envfile.get_live(AGENT_ENV) or "").strip() or DEFAULT_AGENT


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Hand a 3xx back to the caller instead of following it.

    FOLLOWING BLINDLY IS THE BUG THIS PREVENTS. An expired session answers 302 to the logon
    page, and the default handler would fetch that page and return it as a 200 full of HTML —
    which `_check_body` would then have to recognise as "not a CSV" without being able to say
    that the SESSION is what expired. One hop is followed deliberately below, by
    `fetch`, and only where the destination is not the logon page.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


def _open(url: str, *, cookie: Optional[str]) -> Tuple[int, dict, bytes]:
    """One request. Returns (status, headers, body) and raises only for a dead socket."""
    request = urllib.request.Request(url, method="GET")
    request.add_header("User-Agent", _agent())
    request.add_header("Accept", "text/csv, application/octet-stream, */*")
    if cookie:
        request.add_header("Cookie", cookie)
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        response = opener.open(request, timeout=TIMEOUT_S)
        return response.status, dict(response.headers), response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as caught:
        # A 3xx reaches here BECAUSE of `_NoRedirect`, which is the point: an HTTPError is
        # how a non-followed redirect is delivered, and its headers carry the Location.
        return caught.code, dict(caught.headers), caught.read(MAX_BYTES + 1)
    except urllib.error.URLError as caught:
        raise FetchRefusal(
            "tcg_unreachable",
            f"Could not reach {urlparse(url).netloc}: {caught.reason}. Nothing was fetched "
            f"and nothing was written.",
        ) from None
    except TimeoutError:
        raise FetchRefusal(
            "tcg_unreachable",
            f"{urlparse(url).netloc} did not answer within {TIMEOUT_S}s. The export may be "
            f"large; nothing was fetched and nothing was written.",
        ) from None


def _check_status(status: int, headers: dict, url: str) -> Optional[str]:
    """Turn a status into a refusal, or into the one URL worth following. None means keep it.

    Returns a URL to follow once, or None if the response is the body itself.
    """
    if status in (301, 302, 303, 307, 308):
        location = str(headers.get("Location") or "")
        if _LOGON_MARKER in location.lower():
            raise FetchRefusal(
                "tcg_session_expired",
                f"TCGplayer redirected the download to its login page, which means the "
                f"session in {COOKIE_ENV} has expired. Sign in again, copy the fresh "
                f"`Cookie:` header, and replace the value in .env. Nothing was written.",
            )
        if not location:
            raise FetchRefusal(
                "tcg_unexpected_response",
                f"TCGplayer answered {status} with no Location header. Nothing was written.",
            )
        return urljoin(url, location)
    if status == 401:
        raise FetchRefusal(
            "tcg_session_expired",
            f"TCGplayer refused the session in {COOKIE_ENV} (401). Sign in again and "
            f"replace the value in .env. Nothing was written.",
        )
    if status == 403:
        raise FetchRefusal(
            "tcg_blocked",
            f"TCGplayer answered 403. That is either the session having lost its "
            f"permissions or the WAF declining this client by its request signature — set "
            f"{AGENT_ENV} in .env to the User-Agent your browser sends and try again. If it "
            f"keeps refusing, download the export by hand; nothing was written.",
        )
    if status >= 500:
        raise FetchRefusal(
            "tcg_unavailable",
            f"TCGplayer answered {status}. That is their end, not this one — try again "
            f"later. Nothing was written.",
        )
    if status != 200:
        raise FetchRefusal(
            "tcg_unexpected_response",
            f"TCGplayer answered {status} rather than sending a file. Nothing was written.",
        )
    return None


def _check_body(body: bytes, headers: dict) -> bytes:
    """The body is a CSV, or it is a refusal that says which kind of not-a-CSV it is."""
    if len(body) > MAX_BYTES:
        raise FetchRefusal(
            "tcg_export_too_large",
            f"The download passed {MAX_BYTES // (1024 * 1024)} MB and was abandoned. The "
            f"widest export this project has read is under 2 MB, so this is not one.",
        )
    if not body.strip():
        raise FetchRefusal(
            "tcg_export_empty",
            "TCGplayer sent an empty file. That is what the Pricing tab returns when its "
            "filter matches nothing — check the filter in the portal. Nothing was written.",
        )
    kind = str(headers.get("Content-Type") or "").lower()
    head = body.lstrip()[:400].lower()
    if "html" in kind or head.startswith(b"<"):
        # A LOGIN PAGE SERVED AS A 200 IS THE THIRD WAY A SESSION FAILS, and it is the one
        # that would otherwise be parsed as a CSV. The header is checked as well as the body
        # because either alone is defeatable: a portal can send HTML as octet-stream, and a
        # CSV whose first cell begins with `<` is not a thing TCGplayer writes.
        raise FetchRefusal(
            "tcg_session_expired",
            f"TCGplayer sent a web page rather than a file, which is what the login page "
            f"looks like when it is served without a redirect. The session in {COOKIE_ENV} "
            f"has most likely expired. Nothing was written.",
        )
    first = body.split(b"\n", 1)[0]
    if b"," not in first:
        # The same cheapest-possible check `_store_upload` makes of an uploaded file, and it
        # earns its place here for the same reason: the alternative is `join` refusing an
        # empty catalog several seconds later with a message about product lines.
        raise FetchRefusal(
            "tcg_not_csv",
            "What TCGplayer sent has no comma in its first line, so it is not an export. "
            "Nothing was written.",
        )
    return body


def fetch() -> bytes:
    """The Filtered Export, as bytes, or a `FetchRefusal` that names what went wrong.

    ONE DELIBERATE HOP. The endpoint may reasonably answer a redirect to wherever the built
    file actually lives, and refusing every 3xx would break the feature on an implementation
    detail — but the cookie is NOT re-sent across a host change, because a redirect is a
    destination somebody else chose and forwarding a bearer instrument to it is the whole
    shape of a credential leak. A second redirect is refused rather than followed: a chain is
    not something this needs to support, and a loop is not something it may.
    """
    url = endpoint()
    cookie = _cookie()
    status, headers, body = _open(url, cookie=cookie)
    following = _check_status(status, headers, url)
    if following is not None:
        same_host = urlparse(following).netloc == urlparse(url).netloc
        if urlparse(following).scheme not in ("https", "http"):
            raise FetchRefusal(
                "tcg_unexpected_response",
                "TCGplayer redirected the download somewhere this will not follow. "
                "Nothing was written.",
            )
        status, headers, body = _open(following, cookie=cookie if same_host else None)
        if _check_status(status, headers, following) is not None:
            raise FetchRefusal(
                "tcg_unexpected_response",
                "TCGplayer redirected the download twice. One hop is followed; a chain is "
                "not. Nothing was written.",
            )
    return _check_body(body, headers)
