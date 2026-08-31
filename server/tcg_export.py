"""The outbound call to the seller admin host, and the only place allowed to make it.

IT SAID "THE ONE OUTBOUND CALL THIS SERVER MAKES" UNTIL 2026-08-30, AND IT IS NOW ONE OF
TWO. `server/order_transport.py` is the other (D67), against a different host. The
guarantee that actually mattered was never the count — it is that an outbound call lives
in its OWN MODULE, names ONE host, reads its credential AT CALL TIME, and never lets that
credential into a return value. That holds for both files, and it is restated below in
that form rather than being deleted along with the number that went stale.

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

THAT LAST CLAUSE WAS MEASURED FALSE ON 2026-08-30 AND IS CORRECTED HERE RATHER THAN
DELETED (D67). `order-management-api.tcgplayer.com` answers NO `www-authenticate` header on
any path probed; it is a COOKIE SESSION authenticated by the same `TCGAuthTicket_Production`
cookie `_cookie()` below reads, because that cookie is scoped to `.tcgplayer.com` and both
hosts sit under it. The portal's own XHR sets no `Authorization` header either. The
sentence stands because the CONFLATION it warns about was real and the two hosts genuinely
are different — what was wrong was the scheme it attributed to the second one.

WHAT GENUINELY DOES NOT TRANSFER BETWEEN THE TWO HOSTS IS THE BODY CONVENTION, NOT THE
AUTH. This host needs Knockout's `postJson` form — `model=<json>`, form-urlencoded, which
is D65's shape — and the order host takes a plain JSON document. A client carrying this
file's request shape over there fails, and it fails in a way that reads like an auth
problem. That is the trap this paragraph exists to keep somebody out of.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode, urljoin, urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import envfile  # noqa: E402

# The seller portal's own download. A constant rather than something a request can name: a
# route that fetched any URL a client sent, carrying the operator's session cookie, would be
# a credential-forwarding primitive guarded by an origin header.
DEFAULT_URL = "https://store.tcgplayer.com/admin/pricing/downloadexportcsv"

# The filter vocabulary for one category: its sets, rarities, printings and conditions with
# the ids the export scopes on. A GET, and the only other call this module makes.
FILTERS_URL = "https://store.tcgplayer.com/admin/pricing/getjsonfilters"

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


@dataclass(frozen=True)
class Scope:
    """What to ask TCGplayer for. Empty tuples mean "all of them", as the portal encodes it.

    THE POINT OF ASKING RATHER THAN INSPECTING (D65). An export's completeness cannot be read
    off its contents — three filters narrow it and one leaves no trace in the file — but a
    file fetched to a scope this names is complete WITHIN that scope by construction. So the
    check downstream becomes "did I get the sets I asked for", which is a fact, rather than an
    inference about what might be missing.
    """

    category_id: int
    set_ids: Tuple[int, ...] = ()
    rarity_ids: Tuple[int, ...] = ()
    condition_ids: Tuple[int, ...] = ()

    def model(self) -> dict:
        """The request body, field for field as `main-built.js` builds it.

        READ OFF THE PORTAL'S OWN BUNDLE rather than guessed, and the two fields that matter
        most are the ones nobody would have guessed. `MyInventory` false is what makes this
        the CATALOG rather than the operator's current listings — with it true the same
        request returns only what they already have listed, which is useless to a join that
        exists to list new cards. `ExcludeListos` is the exclude-listings-with-photos flag,
        the axis D64 measured as leaving no trace in the file; setting it explicitly is what
        stops it being invisible.

        `PrintingIds` is left empty on purpose. All Printings is the whole point: a number
        stocked in several finishes must arrive with all of them, or D3 rung 2 decides it
        from whichever one survived.
        """
        def ids(chosen):
            # "ALL OF THEM" IS `["0"]` AND NOT THE EMPTY LIST, which is the single detail that
            # cost the most. An empty array answers `System Error` — a 200 carrying an HTML
            # error page — and reads exactly like a rejected session unless you look at the
            # title. `0` is the "All Set Names" / "All Rarities" option's own id, so the
            # portal is asking for a filter that matches everything rather than for no filter.
            return [str(int(v)) for v in chosen] or ["0"]

        # EVERY VALUE IS A STRING AND THE TYPES ARE NOT NEGOTIABLE. Captured off the portal's
        # own submit in the owner's browser on 2026-08-30 rather than inferred from the
        # bundle: `PricingType` is the literal `"Pricing"` and not an enum ordinal, the ids
        # are strings, and the three price fields carry values even when comparison is off.
        # Guessing produced a body that was structurally plausible and answered `System Error`
        # five different ways.
        return {
            "PricingType": "Pricing",
            "CategoryId": str(int(self.category_id)),
            "SetNameIds": ids(self.set_ids),
            "ConditionIds": ids(self.condition_ids),
            "RarityIds": ids(self.rarity_ids),
            "LanguageIds": ["1"],
            # All Printings, always. A number stocked in several finishes must arrive with all
            # of them or D3 rung 2 decides it from whichever one survived.
            "PrintingIds": ["0"],
            "CompareAgainstPrice": False,
            "PriceToCompare": 3,
            "ValueToCompare": 1,
            "PriceValueToCompare": None,
            # The catalog, not the operator's current listings. With this true the same
            # request returns only what is already listed, which is useless to a join whose
            # whole job is listing cards that are not.
            "MyInventory": False,
            "ExcludeListos": False,
            "ExportLowestListingNotMe": True,
        }


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


def _filters_endpoint() -> str:
    """Where the filter list is read from. Follows `endpoint()`'s override so a test that
    redirects the download does not leave this one pointed at TCGplayer."""
    override = (envfile.get_live(URL_ENV) or "").strip()
    if not override:
        return FILTERS_URL
    endpoint()  # re-uses its https-or-loopback refusal rather than restating it
    return override.rstrip("/").rsplit("/", 1)[0] + "/getjsonfilters"


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


def _open(
    url: str, *, cookie: Optional[str], data: Optional[bytes] = None, content_type: str = ""
) -> Tuple[int, dict, bytes]:
    """One request. Returns (status, headers, body) and raises only for a dead socket."""
    request = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    if content_type:
        request.add_header("Content-Type", content_type)
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
    if b"system error" in body[:4000].lower() or b"<title>system error" in body[:4000].lower():
        # NOT AN EXPIRED SESSION, AND SAYING SO WAS A REAL DEFECT. The portal answers a
        # malformed request with HTTP 200 carrying an HTML page titled `System Error`, and the
        # branch below read any HTML as a login page — so a body this code got wrong was
        # reported as the operator's credential being stale. That sends them to re-copy a
        # cookie that was working. Measured while D65 was being built: five different bad
        # request bodies, every one reported as `tcg_session_expired`.
        raise FetchRefusal(
            "tcg_request_rejected",
            "TCGplayer rejected the request and returned its System Error page. The session "
            "is fine — this is the export request itself being malformed, which is a defect "
            "here rather than anything to fix in the portal. Nothing was written.",
        )
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


def filters(category_id: int) -> Dict[str, Any]:
    """One category's filter vocabulary: `Sets`, `Rarities`, `Conditions`, `Printings`.

    Each entry is `{Text, Value, Selected, ...}` and `Value` is the id the export scopes on.
    WITHOUT A CATEGORY THIS ANSWERS ALMOST NOTHING — measured 2026-08-30, the bare call returns
    one "All Set Names" row and one "All Rarities" row, because the portal populates those
    lists from whichever category is picked. Passing `categoryId=89` returns Riftbound's 13
    sets, 8 rarities and 3 printings. That is why this takes the argument rather than being a
    constant read once.
    """
    url = f"{_filters_endpoint()}?categoryId={int(category_id)}"
    status, headers, body = _open(url, cookie=_cookie())
    if _check_status(status, headers, url) is not None:
        raise FetchRefusal(
            "tcg_unexpected_response",
            "TCGplayer redirected the filter list. Nothing was read.",
        )
    try:
        parsed = json.loads(body.decode("utf-8", "replace"))
    except ValueError:
        raise FetchRefusal(
            "tcg_filters_unreadable",
            "TCGplayer's filter list did not parse as JSON. The portal may have changed "
            "shape; nothing was fetched.",
        ) from None
    if not isinstance(parsed, dict) or "Sets" not in parsed:
        raise FetchRefusal(
            "tcg_filters_unreadable",
            "TCGplayer's filter list is not the shape this reads — no `Sets`. Nothing was "
            "fetched.",
        )
    return parsed


def match_sets(hints, sets, aliases=None) -> Tuple[Tuple[int, ...], Tuple[str, ...]]:
    """Capture-time set hints -> TCGplayer set ids. Returns (matched ids, hints that missed).

    THE HINT IS THE OPERATOR'S SHORTHAND AND THE SET NAME IS TCGPLAYER'S, and nothing
    guarantees they are the same string. Measured against the two the store actually holds:
    `UNL` against `Unleashed`, and `ME01` against `ME01: Mega Evolution`. Three rules, tried
    in order, each stricter than a substring search would be:

      exact      case-folded equality.
      prefix     the hint is a case-folded prefix of the name. `UNL` -> `Unleashed`.
      code       the name's leading token before `:` equals the hint. `ME01` -> `ME01: ...`.

    AN AMBIGUOUS HINT MATCHES NOTHING RATHER THAN GUESSING. Two sets sharing a prefix is a
    real shape — `Origins` and `Origins: Proving Grounds` — and picking either would scope the
    export to a set the box may not be in. The hint is returned as unresolved instead, and the
    caller widens to the whole category, which is slower and always correct.

    Substring is deliberately NOT one of the rules. `Origins` appears inside
    `Origins: Proving Grounds`, so a substring test makes every hint that names a base set
    ambiguous with its own sub-sets and resolves nothing.
    """
    by_id = [(str(entry.get("Text") or ""), str(entry.get("Value") or "")) for entry in sets]
    # RULE ZERO: the game's own alias table, folded before the shape rules run. `MEG` and
    # `ME01` name one set in two vocabularies and no string rule bridges them, so the registry
    # carries the pairing (D65). An alias resolves to another HINT rather than to an id, so
    # the three rules below still do the matching and the table never repeats a full set name.
    folded = {str(k).strip().casefold(): str(v) for k, v in (aliases or {}).items()}
    matched, missed = [], []
    for hint in hints:
        raw = str(hint or "").strip()
        needle = folded.get(raw.casefold(), raw).strip().casefold()
        if not needle:
            continue
        found = [v for t, v in by_id if t.casefold() == needle]
        if not found:
            found = [v for t, v in by_id if t.casefold().startswith(needle)]
        if not found:
            found = [v for t, v in by_id if t.split(":")[0].strip().casefold() == needle]
        # `0` is the "All Set Names" row and is not a set; matching it would silently widen.
        found = [v for v in found if v != "0"]
        if len(found) == 1:
            matched.append(int(found[0]))
        else:
            missed.append(str(hint))
    return tuple(dict.fromkeys(matched)), tuple(dict.fromkeys(missed))


def fetch(scope: Scope) -> bytes:
    """The catalog export for `scope`, as bytes, or a `FetchRefusal` naming what went wrong.

    A POST, AND THE METHOD IS THE WHOLE CORRECTION (D65). This module shipped against
    `/Admin/Pricing/DownloadMyExportCSV` with the scope on the query string, and that endpoint
    ignores every parameter: eight different spellings returned byte-identical output, because
    it is a different, unscoped endpoint that serves whatever the portal's saved filter last
    was. What the Export Filtered CSV button actually sends — captured off the wire in the
    owner's own browser — is a POST to `/admin/pricing/downloadexportcsv`.

    THE BODY IS KNOCKOUT'S `postJson` SHAPE, which is a form whose fields are JSON strings
    rather than a JSON document. `ko.utils.postJson(url, {model: {...}})` builds a hidden form
    with one field named `model` holding `JSON.stringify(model)` and submits it. A plain JSON
    body is what a reader would write first and it answers 500.

    One deliberate redirect hop, as before: the cookie is not re-sent across a host change,
    because a redirect is a destination somebody else chose.
    """
    url = endpoint()
    cookie = _cookie()
    payload = urlencode({"model": json.dumps(scope.model())}).encode("utf-8")
    status, headers, body = _open(
        url,
        cookie=cookie,
        data=payload,
        content_type="application/x-www-form-urlencoded",
    )
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
