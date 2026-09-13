"""The order transport: this account's own orders, read off `order-management-api`.

THE SECOND OUTBOUND CALL THIS SERVER MAKES, and `server/tcg_export.py`'s docstring — which
says it is "the ONE outbound call this server makes, and the only place allowed to make it" —
is now one module out of date. That sentence was true when it was written and is a promise
worth keeping in the shape rather than in the letter: what it actually guarantees is that an
outbound call lives in a module of its own, names one host, reads its credential at call time,
and never lets the credential into a return value. Every one of those holds here. A second
host does not weaken any of them; a second host reached from `capture_server.py` would.

WHAT THIS IS FOR (D66, T3). `pipeline/orders.py` resolves an order line to the physical copies
that fill it, and it is transport-independent by construction: its input is domain objects.
Until now the only way an order got into the process was a human pasting JSON. This module is
the fetch that replaces the paste, behind a control that the order screen already draws. It
writes nothing, reads no card state, and cannot spend money — `POST /pipeline/identify` is
still the only route in this server that can put a number on an invoice.

STDLIB ONLY. `urllib.request` and not `requests`: `requirements.txt` names that absence on
purpose, and a second fetch is not a reason to spend the dependency the first one was refused
for.

--------------------------------------------------------------------------------------------
STATUS, PLAINLY: THE SESSION IS PROVEN AND THE DETAIL CALL IS NOT
--------------------------------------------------------------------------------------------

**`search` HAS NOW RUN AUTHENTICATED, 2026-08-30, and returned three real orders.** The
operator ran it — an agent may not read `.env` here, which is `.claude/settings.json`'s rule
and was left standing rather than worked around. What that one call settles is more than the
session: the `TCGPLAYER_STORE_COOKIE` value stored in `.env` DOES authenticate this host, so
one credential really does serve the admin portal and the order API; `PKMNSCAN_TCG_SELLER_KEY`
was accepted, so the 403 shape is understood correctly; the plain-JSON body was accepted, so
D65's form encoding really is the wrong shape here and not merely a different one; and the
response parsed and projected without raising.

**`fetch_open_orders` HAS RUN AGAINST THE LIVE HOST AND RETURNED NOTHING, 2026-09-02.** The
owner pressed Fetch and was refused `order_too_many`: the search pages walked far enough to
count 370 orders in `LastThreeMonths` against a cap of 100, so the PAGING is proven live and
the cap, as it stood, meant this module had never handed an order to the ledger on the one
account it exists for. D91 moved the cap to the detail calls and put the status filter in the
operator's hands; the refusal that fired is quoted in that entry.

**`detail` IS STILL UNEXERCISED AGAINST THE LIVE HOST**, and that is the half that carries a
buyer's name and address. `products[].skuId` has been read in the BROWSER and never through
this module, so `project_order`'s drop of `buyerName`, `shippingAddress` and `paymentType` is
proven against T7's fixtures and against nothing that came off the wire. The first filtered
fetch — the owner ticking a status and pressing — exercises it; until then this line stands.

What was measured in the owner's own logged-in browser on 2026-08-30, before any of that:

  - the endpoints, their methods, their query string and their request bodies;
  - that the auth is a cookie session and NOT a Bearer challenge;
  - that `TCGAuthTicket_Production` is scoped to `.tcgplayer.com`;
  - that omitting `filters.sellerKey` answers 403 rather than 400;
  - that `GET /orders` answers 405, because `/orders` is a prefix and not a route;
  - that refusals come back as RFC 7807 problem+json.

Corroborated against `tcgtracking-bridge-v2.4.2/background.js`, a third-party MV3 extension
the owner supplied, which bridges this same flow with the same two endpoints, the same
`credentials: 'include'`, and the same `Origin`/`Referer` pair.

**The session question is closed** — see the top of this block. A session that later expires
still arrives as `order_session_expired`, and the remedy is the one that message prints.

Every refusal path in this file is reachable without a network. `search_body`,
`project_order` and `problem_note` are pure functions and are public for exactly that reason:
T7 can drive the body shape, the projection and the problem+json reader with no socket at all,
and the transport itself takes a loopback override for the rest.

--------------------------------------------------------------------------------------------
WHAT IS DIFFERENT FROM `server/tcg_export.py`, AND EVERY DIFFERENCE IS LOAD-BEARING
--------------------------------------------------------------------------------------------

**THE BODY IS A PLAIN JSON DOCUMENT. DO NOT "FIX" IT INTO KNOCKOUT'S `postJson` FORM.** D65
paid real time to discover that the admin portal takes `model=<json>` form-urlencoded and
answers 500 to a JSON body. That is a fact about `store.tcgplayer.com`'s MVC controllers and
it does not travel: this host is ASP.NET Core with `Content-Type: application/json`, and
carrying D65's form shape here fails. The two conventions look interchangeable and are not.

**ONE CREDENTIAL LEGITIMATELY SERVES TWO HOSTS.** `TCGAuthTicket_Production` is set on
`.tcgplayer.com`, the registrable domain, so a browser sends it to `store.tcgplayer.com`,
`sellerportal.tcgplayer.com` and `order-management-api.tcgplayer.com` alike — the cookie is
the account's session, not one site's. That is why this reads `TCGPLAYER_STORE_COOKIE` rather
than introducing a second env name: a second name is a second thing to rotate, and an operator
who refreshed one and not the other would have half a working tree with no way to tell which
half. The name says `STORE` for historical reasons only; the value is the session.

**WHAT DOES NOT TRANSFER IS THE AUTH FAILURE MODE.** The admin portal answers an expired
session with `302 -> /admin/account/logon`, which is why `tcg_export` follows no redirect
blindly. This host answers 401 with problem+json. Both are handled below, because an
unauthenticated request to a host behind the same edge can be turned into either.

**403 IS NOT "SIGN IN AGAIN" HERE.** Omitting `filters.sellerKey` is a 403, measured. A
client that reads 403 as an expired session sends the operator to re-copy a cookie that was
working, over a bug in the request body — which is precisely the defect D65 recorded and fixed
in `tcg_export._check_body` (five malformed bodies, all reported as `tcg_session_expired`).
So 403 gets `order_seller_key_rejected` and leads with the body, not the credential.

**IT IS TWO CALLS, AND THAT IS NOT AN OPTIMISATION FAILURE.** The search result carries no
SKU; only the order detail does, as `products[].skuId`. The SKU is the join key —
`products[].skuId` is the export's `TCGplayer Id` is `store/master.py:Card.sku` — so an order
without it resolves to nothing at all. There is no bulk line-item endpoint. Search for the
numbers, then one detail GET per number.

--------------------------------------------------------------------------------------------
THE PROJECTION IS THE POINT
--------------------------------------------------------------------------------------------

The order detail carries `buyerName`, `shippingAddress` (recipient, street, city, postal
code), `paymentType` and a full transaction breakdown. **Exactly one of those now leaves
this module: `buyerName`, as `buyer`, a display name and nothing more**
(D193). The rest is returned from NO function here — not from
`detail`, not from `search`, not from `fetch_open_orders`. The projection happens the
moment the response is parsed, so a buyer's ADDRESS exists in this process only as a local
`dict` inside one call frame and reaches no caller, no route, no screen, no file.

`buyerName` joining the allowlist is an OWNER'S RULING, not a session's judgement call: the
owner walks drawers per *person*, and a screen that can only say "order A2FFC195" has no way
to say "these three are the same buyer" — which is the whole reason `#/orders` groups by
buyer rather than by number. Everything else stays excluded for the reason it always was:
none of it is needed to pick a card off a shelf and put it in an envelope, and this repo has
no use for a bearer instrument it does not need.

It is an ALLOWLIST and not a denylist, which is the whole difference, and that mechanism is
UNCHANGED by `buyerName` joining it. A denylist grows a hole every time the vendor adds a
field, and it grows it silently: the day TCGplayer adds `buyerEmail`, a denylist starts
returning it and nothing anywhere fails. An allowlist stops returning a field it has never
heard of, which is the direction an accident should fall in — and it stops just as hard on a
field this module already knows the NAME of. `buyerEmail` is not `buyerName`; nothing here
reads it, and nothing granted `buyerName` a general licence to widen further.

Nothing here is a substitute for the seller portal. If a human needs the buyer's address to
put on an envelope, they read it in TCGplayer's own UI, and this repo's shipping path
(`pipeline/pirateship.py`) takes the address from the operator rather than from here.

--------------------------------------------------------------------------------------------
WHAT IS DELIBERATELY NOT BUILT
--------------------------------------------------------------------------------------------

    POST /orders/status-updates?api-version=2.0            {orderNumbers:[], status:"Shipped"}
    POST /orders/<orderNumber>/tracking?api-version=2.0    {carrier, trackingNumber}

Both exist and both were seen. Both are WRITES back to TCGplayer, and
`docs/specs/order-pipeline.md` §3 T5 already rules on them: pkmnscan never writes order status
back to TCGplayer, because tcgtracking owns mark-shipped and two authors on one shipment is
D34's problem twice. Recorded here so the next reader knows the endpoints exist and that not
using them is a decision rather than an oversight — and so that adding them is visibly a
change of policy rather than a change of code.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import quote, urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import envfile  # noqa: E402
from server import tcg_export  # noqa: E402

# The order host, as a constant rather than as something a request can name. The reasoning is
# `tcg_export`'s and is not weaker here: a route that fetched whatever URL a client sent, while
# carrying the operator's session cookie, is a credential-forwarding primitive with an origin
# check in front of it.
DEFAULT_BASE = "https://order-management-api.tcgplayer.com"

# EVERY CALL CARRIES `api-version=2.0`. It is not optional and it is not a default: it was on
# every request the portal's own XHR made, and the bridge extension pins the same string.
API_VERSION = "2.0"

# THE COOKIE NAME IS TAKEN FROM THE MODULE THAT ALREADY OWNS IT rather than retyped, so the two
# hosts cannot drift into two half-configured credentials. See the docstring for why one
# session legitimately serves both.
COOKIE_ENV = tcg_export.COOKIE_ENV

# The same User-Agent knob, for the same reason: it is a remedy a refusal names, and an
# operator who set it for one host meant it for this client.
AGENT_ENV = tcg_export.AGENT_ENV

# THE SELLER KEY IS NOT A SECRET AND IS STILL NOT A CONSTANT. It is the lowercased prefix of
# every order number this account has, so it identifies the account and would be wrong in
# anyone else's checkout — which makes it configuration, and configuration in this repo is a
# `PKMNSCAN_`-prefixed name in `.env`. The split is the existing one: knobs are prefixed,
# secrets are not (`ANTHROPIC_API_KEY`, `TCGPLAYER_STORE_COOKIE`).
SELLER_KEY_ENV = "PKMNSCAN_TCG_SELLER_KEY"

# How T7 aims this at a socket it controls. Guarded by `endpoint()`, which will not carry the
# cookie anywhere but https or loopback — a knob that redirects a session cookie is an
# exfiltration channel wearing a test seam.
BASE_ENV = "PKMNSCAN_TCG_ORDERS_URL"

# THE PORTAL'S OWN XHR SENDS THESE AND SO DOES THE BRIDGE. Neither was proven to be REQUIRED —
# an unauthenticated probe cannot tell an origin check from an auth check — so they are sent
# because the two clients known to work send them, and are named here rather than left as
# unexplained constants. They disclose nothing: both are public URLs.
ORIGIN = "https://sellerportal.tcgplayer.com"
REFERER = "https://sellerportal.tcgplayer.com/"

# The ranges this client will ask for. `LastThreeMonths` is the one captured off the wire;
# `LastTwoYears` is the bridge extension's own default, so it is attested by a client that
# works rather than invented here. Anything else is refused rather than forwarded: a range the
# server does not recognise comes back as a 4xx whose message this module would have to guess
# at, and guessing is what `order_range_unknown` exists to avoid.
DEFAULT_RANGE = "LastThreeMonths"
KNOWN_RANGES = ("LastThreeMonths", "LastTwoYears")

# `Custom` IS REAL AND IS REFUSED ON PURPOSE. It needs `orderDateFrom`/`orderDateTo`, a
# different query string and a `page` parameter the other ranges do not use, and none of that
# was captured against a live session. A half-built date range that silently returned the wrong
# window is worse than a refusal that says the window is not built.
CUSTOM_RANGE = "Custom"

# What was measured. 25 is the page the portal itself asks for; the ceiling is this module's,
# not the server's, and exists so a typo cannot turn one call into a scrape.
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100

# ONE FETCH IS ONE SEARCH PAGE PER 25 ORDERS PLUS ONE DETAIL PER ORDER DETAILED, AND THE
# CEILING IS A RATE LIMIT ON THE DETAILS. The bridge extension limits itself to 120 requests a
# minute against these hosts, which is the only number anyone has for what this API tolerates —
# it is that client's own self-limit, not a measurement of the server. 15 pages plus 100 details
# is 115, inside that budget without this module sleeping in the middle of a request.
#
# THE CEILING COUNTS DETAIL CALLS, NOT ORDERS IN THE WINDOW (D91). It counted the window until
# 2026-09-02, and on the owner's account that meant this module had never returned an order:
# `LastThreeMonths` holds 370, every press was refused `order_too_many`, and the remedy printed
# — "ask for a narrower range" — is one the range vocabulary below cannot express. The pages are
# walked whole now; what is capped is what gets detailed, which is the statuses the operator
# ticked and the ledger does not already hold. Past the cap the rest is COUNTED and reported as
# `remaining`, never silently left behind, and the next press picks it up.
MAX_ORDERS = 100

# A JSON API, not a CSV the portal builds on demand, so this is a fraction of `tcg_export`'s
# 120s. A request that never answers is worse than one that refuses.
TIMEOUT_S = 30

# An order page is tens of kilobytes. Eight megabytes is a backstop against a body that never
# ends, not a judgement about how large an order may be.
MAX_BYTES = 8 * 1024 * 1024

# An expired session behind the same edge can still be answered as a redirect to the portal's
# login page, which is why redirects are read rather than followed.
_LOGON_MARKER = "account/logon"

# An order number is `A2FFC195-...`: hex, dashes, and on some channels a trailing suffix. The
# characters this will put in a path are restricted to that alphabet — not because TCGplayer
# would mind, but because the number arrives from a response body and a path segment built from
# a response body is how a fetch reaches a route nobody chose.
_NUMBER_OK = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")

# ---------------------------------------------------------------------------- the refusal


class FetchRefusal(Exception):
    """A refusal with its own code. A caller converts it to a 4xx.

    A private exception rather than `capture_server.BadRequest`, `PipelineRefusal` or
    `tcg_export.FetchRefusal`. The first two would make this module depend on a file that
    imports it; the third would make one `except` clause catch two hosts' failures and report
    the wrong remedy for whichever it was not. The seam is one `except` at each call site.

    THE MESSAGE NEVER CARRIES THE COOKIE, AND IT NEVER CARRIES A RESPONSE BODY. Every string
    built in this file is composed from a status code, a header this module chose, a constant,
    an order number, or the `traceId` out of a problem+json document. A vendor body is exactly
    where a credential gets echoed back, so none of one is ever interpolated — see
    `problem_note`, which reads one field out of it and drops the rest.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ------------------------------------------------------------------- pure, socket-free bits


def problem_note(headers: Dict[str, Any], body: bytes) -> str:
    """The trailing ` (traceId …)` for a refusal message, or `""`. Never the body itself.

    RFC 7807 IS WHAT THIS HOST REFUSES IN: `{type, title, status, traceId}`. The `traceId` is
    the one field worth carrying — it is what the operator would quote if they ever had to ask
    TCGplayer why a request was refused, and it is meaningless to anyone else.

    EVERYTHING ELSE IN THE DOCUMENT IS DROPPED, INCLUDING `title` AND `detail`. They are the
    fields most likely to quote the request back, and a refusal that echoes a request is how a
    credential ends up in a log line. Dropping them costs a caller nothing this module does not
    already say in its own words, and the trace id survives to make the refusal traceable.

    Pure: hand it any headers dict and any bytes. It raises nothing — a body that is not JSON,
    is not a dict, or carries no trace id is simply worth no note, and a refusal without a
    trace id is still a refusal.
    """
    kind = str(headers.get("Content-Type") or headers.get("content-type") or "").lower()
    if "json" not in kind:
        return ""
    try:
        parsed = json.loads(body[:MAX_BYTES].decode("utf-8", "replace"))
    except ValueError:
        return ""
    if not isinstance(parsed, dict):
        return ""
    trace = str(parsed.get("traceId") or "").strip()
    if not trace:
        return ""
    # Bounded and stripped of anything that is not an identifier character. The field is
    # vendor-authored and lands in a message a human reads; a newline or an escape sequence in
    # it would be the vendor formatting this repo's output.
    keep = [c for c in trace if c.isalnum() or c in "-_:"]
    trace = "".join(keep)[:64]
    return f" (traceId {trace})" if trace else ""


def search_body(
    range_: str, page_size: int, frm: int, seller_key: str
) -> Dict[str, Any]:
    """The search request body, field for field as the portal's own XHR sends it.

    Captured off the wire rather than inferred. `sortBy` is TWO clauses in this order — status
    first, then date — which is what makes a page of results stable enough to walk: without a
    total order over the result set, `from`/`size` paging hands back a shuffled window and an
    order can appear on two pages or on none.

    VALIDATES ITS OWN ARGUMENTS, WHICH IS WHY IT IS PUBLIC AND PURE. Every refusal about the
    SHAPE of a request is reachable from a test with no socket in it: an unknown range, the
    `Custom` range that is not built, a page size outside the measured bounds, a negative
    offset, and a missing seller key are five different problems with five different remedies.

    The seller key is passed in rather than read here, so this stays pure and so the one place
    that touches `.env` is `_seller_key`.
    """
    range_ = str(range_ or "").strip()
    if range_.casefold() == CUSTOM_RANGE.casefold():
        raise FetchRefusal(
            "order_range_custom_unsupported",
            f"The {CUSTOM_RANGE} range needs a date pair and a different query string, and "
            f"none of that was captured against a live session, so it is not built. Ask for "
            f"one of {', '.join(KNOWN_RANGES)} instead. Nothing was fetched.",
        )
    canonical = next(
        (known for known in KNOWN_RANGES if known.casefold() == range_.casefold()), ""
    )
    if not canonical:
        raise FetchRefusal(
            "order_range_unknown",
            f"{range_!r} is not a search range this client will ask for. The ones it knows "
            f"are {', '.join(KNOWN_RANGES)}. Nothing was fetched.",
        )
    try:
        size = int(page_size)
        offset = int(frm)
    except (TypeError, ValueError):
        raise FetchRefusal(
            "order_page_invalid",
            "The page size and the offset must both be whole numbers. Nothing was fetched.",
        ) from None
    if not 1 <= size <= MAX_PAGE_SIZE:
        raise FetchRefusal(
            "order_page_invalid",
            f"A page of {size} orders is outside 1..{MAX_PAGE_SIZE}. {DEFAULT_PAGE_SIZE} is "
            f"what the portal itself asks for. Nothing was fetched.",
        )
    if offset < 0:
        raise FetchRefusal(
            "order_page_invalid",
            f"An offset of {offset} is not a place in a result set. Nothing was fetched.",
        )
    key = str(seller_key or "").strip()
    if not key:
        raise FetchRefusal(
            "order_seller_key_missing",
            f"No {SELLER_KEY_ENV} in .env. Without it this host answers 403, which reads "
            f"exactly like an expired session and is not one. The value is the lowercased "
            f"prefix of any order number on the Orders page — the part before the first dash "
            f"and everything up to it, lowercased. Nothing was fetched.",
        )
    return {
        "searchRange": canonical,
        # THE FIELD WHOSE ABSENCE IS A 403 AND NOT A 400. Measured.
        "filters": {"sellerKey": key},
        "sortBy": [
            {"sortingType": "orderStatus", "direction": "ascending"},
            {"sortingType": "orderDate", "direction": "ascending"},
        ],
        "from": offset,
        "size": size,
    }


def project_order(
    detail: Any, summary: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """One order detail, reduced to the five things this repo is allowed to hold.

    THE ALLOWLIST IS THE SECURITY BOUNDARY and it is short on purpose:

        orderNumber   the identifier. Not personal; it is what the ledger keys on.
        orderDate     when it was placed. Decides the sequence two orders competing for one
                      SKU are resolved in (`pipeline/orders.py:order_sequence`).
        status        verbatim, whatever the feed said.
        buyer         the buyer's DISPLAY NAME, and nothing else about who they are
                      (D193). The owner walks drawers per *person*,
                      and an order number carries no name a human can group by.
        products      one entry per line: {skuId, quantity, name, unitPrice}.

    Everything else is dropped where it was parsed: `shippingAddress`, `sellerName`,
    `paymentType`, `transaction`, `refunds`, `trackingNumbers`, `allowedActions` and any
    field TCGplayer adds after this was written. The last clause is why it is an allowlist —
    a denylist would return the new field and nothing would fail.

    THE DETAIL AND THE SUMMARY DISAGREE ABOUT TWO NAMES, which is a fact about the API and not
    a defect: the detail says `createdAt` and `status`, the search result says `orderDate` and
    `orderStatus`. The detail wins where it has an answer, and the summary fills in where it
    does not, so an order is not left dateless because one endpoint spells it differently.
    `buyer` follows the same rule — the detail's own `buyerName` wins, and the (already
    projected) summary's `buyer` fills in where the detail carries none.

    A LINE IS NEVER SILENTLY DROPPED. A line with no readable SKU or no readable quantity
    refuses, naming the order — `CLAUDE.md`'s rule is that ambiguity faces a human, and a
    quietly shortened order is an envelope that goes out light with nothing anywhere saying so.
    """
    if not isinstance(detail, dict):
        raise FetchRefusal(
            "order_response_unreadable",
            "An order came back as something other than a JSON object. The API may have "
            "changed shape; nothing was read.",
        )
    fallback = summary if isinstance(summary, dict) else {}
    number = str(detail.get("orderNumber") or fallback.get("orderNumber") or "").strip()
    if not number:
        raise FetchRefusal(
            "order_response_unreadable",
            "An order came back with no order number, so there is nothing to key it by. "
            "Nothing was read.",
        )
    raw_lines = detail.get("products")
    if raw_lines is None:
        raise FetchRefusal(
            "order_response_unreadable",
            f"Order {number} carries no `products` list, so its lines cannot be read. An "
            f"order with unreadable lines is refused rather than treated as empty. Nothing "
            f"was read.",
        )
    if not isinstance(raw_lines, list):
        raise FetchRefusal(
            "order_response_unreadable",
            f"Order {number}'s `products` is not a list. Nothing was read.",
        )

    lines: List[Dict[str, Any]] = []
    for position, entry in enumerate(raw_lines, start=1):
        if not isinstance(entry, dict):
            raise FetchRefusal(
                "order_line_unreadable",
                f"Line {position} of order {number} is not an object. Nothing was read.",
            )
        # COERCED TO A STRING AT THE BOUNDARY. `store/master.py:Card.sku` is a string because
        # it came out of a CSV cell; this feed sends the same value as an int, and
        # `"9191486" == 9191486` is False. `pipeline/orders.py:OrderLine` coerces too — this is
        # belt and braces on the one comparison that, when it fails, fails silently and
        # completely: every line unresolvable, nothing raised, nothing logged.
        sku = str(entry.get("skuId") or "").strip()
        if not sku:
            raise FetchRefusal(
                "order_line_unreadable",
                f"Line {position} of order {number} carries no skuId, so there is no way to "
                f"find the card it wants. It is refused rather than dropped. Nothing was read.",
            )
        try:
            quantity = int(entry.get("quantity"))
        except (TypeError, ValueError):
            raise FetchRefusal(
                "order_line_unreadable",
                f"Line {position} of order {number} has no readable quantity. Nothing was "
                f"read.",
            ) from None
        if quantity < 1:
            raise FetchRefusal(
                "order_line_unreadable",
                f"Line {position} of order {number} wants {quantity} copies, which is not a "
                f"quantity. Nothing was read.",
            )
        price = entry.get("unitPrice")
        lines.append(
            {
                "skuId": sku,
                "quantity": quantity,
                # Kept verbatim for a screen to show beside the position, and never used as a
                # join key: `CLAUDE.md` forbids joining on a product name because the column
                # inconsistently embeds numbers, and that rule is not weaker here.
                "name": str(entry.get("name")) if entry.get("name") is not None else None,
                "unitPrice": str(price) if price is not None else None,
            }
        )

    date = detail.get("createdAt") or fallback.get("orderDate")
    status = detail.get("status") or fallback.get("orderStatus")
    # THE ONE FIELD THAT LEAVES THIS FUNCTION AND IS ABOUT A PERSON. `buyerName` is read here
    # and nowhere lower — `_ingest_line`, `_line_answer`, every function that touches a
    # `products[]` entry never sees it, because it never went into `entry` in the first
    # place. The detail's own name wins; the summary's already-projected `buyer` (itself
    # `buyerName`, one call earlier) fills in where the detail said nothing, the same
    # fallback `orderDate`/`orderStatus` use two lines up.
    buyer = str(detail.get("buyerName") or "").strip() or fallback.get("buyer")
    return {
        "orderNumber": number,
        "orderDate": str(date) if date is not None else None,
        "status": str(status) if status is not None else None,
        "buyer": buyer or None,
        "products": lines,
    }


def project_summary(entry: Any) -> Dict[str, Any]:
    """One search result, reduced to the four fields this repo is allowed to hold.

    THE SUMMARY IS PROJECTED TOO, AND THAT IS NOT BELT-AND-BRACES. The search result carries
    `buyerName` beside `shippingAddress` and the rest, and a public `search` that handed back
    raw summaries would be the same leak as an unprojected `detail`, one call earlier — and
    the easier one to miss, because nobody thinks of a list endpoint as carrying an address.
    `buyer` is the one field that survives the projection now, for `project_order`'s reason:
    the owner walks drawers by person, and this is where that name is FIRST available — a
    names-only backfill (`FetchResult.names`) reads it off exactly this function, at zero
    detail calls, because the summary already carries the one fact it needs.
    """
    if not isinstance(entry, dict):
        raise FetchRefusal(
            "order_response_unreadable",
            "A search result came back as something other than a JSON object. Nothing was "
            "read.",
        )
    number = str(entry.get("orderNumber") or "").strip()
    if not number:
        raise FetchRefusal(
            "order_response_unreadable",
            "A search result carries no order number. Nothing was read.",
        )
    date = entry.get("orderDate")
    status = entry.get("orderStatus")
    buyer = str(entry.get("buyerName") or "").strip() or None
    return {
        "orderNumber": number,
        "orderDate": str(date) if date is not None else None,
        "status": str(status) if status is not None else None,
        "buyer": buyer,
    }


# --------------------------------------------------------------------- credentials and URLs


def base_url() -> str:
    """The host this will talk to, and the check that the cookie may go there.

    HTTPS OR LOOPBACK, NOTHING ELSE — `tcg_export.endpoint`'s guard, restated rather than
    imported because the two modules take different override names and sharing the function
    would mean sharing the name. The override exists so a test can point this at a socket it
    controls; the guard exists because a knob that redirects a session cookie is an
    exfiltration channel wearing a test seam. `http://127.0.0.1` is permitted because it cannot
    leave the machine.
    """
    override = (envfile.get_live(BASE_ENV) or "").strip().rstrip("/")
    if not override:
        return DEFAULT_BASE
    parsed = urlparse(override)
    loopback = parsed.hostname in ("127.0.0.1", "::1", "localhost")
    if parsed.scheme == "https" or (parsed.scheme == "http" and loopback):
        return override
    raise FetchRefusal(
        "order_url_invalid",
        f"{BASE_ENV} must be an https URL, or http on 127.0.0.1 for a local test. The "
        f"session cookie is not sent over plain http to anywhere else.",
    )


def _cookie() -> str:
    """The `Cookie:` header value, or the refusal that says where to put one.

    READ THROUGH `envfile.get_live` AND NOT `envfile.get`, WHICH IS NOT A DETAIL. The session
    EXPIRES; `order_session_expired` tells the operator to sign in again and replace the value
    in `.env`; and `get` caches per process and cannot replace a value it already lifted out of
    the file. Under D53's supervisor, which runs for days and does not watch `.env`, that
    printed remedy would not have worked and the refusal would have repeated forever over a
    cookie the operator had already fixed.

    THE WHOLE HEADER, NOT ONE TICKET, for `tcg_export._cookie`'s reason: `TCGAuthTicket_Production`
    is the ticket the session hangs on, and it is not established that it is the only cookie
    either host requires. Copying the whole `Cookie:` header out of the browser is one action
    and cannot be wrong about which cookies matter.
    """
    value = envfile.get_live(COOKIE_ENV)
    if not value:
        raise FetchRefusal(
            "order_cookie_missing",
            f"No {COOKIE_ENV} in .env, so there is no session to read orders with. Sign in to "
            f"tcgplayer.com, copy the whole `Cookie:` header off any request the Orders page "
            f"makes in the browser's network tab, and put it in .env as {COOKIE_ENV}=<that "
            f"value>. It is the same cookie the export uses — one session, both hosts. It is a "
            f"bearer instrument: .env only.",
        )
    if "=" not in value:
        raise FetchRefusal(
            "order_cookie_malformed",
            f"{COOKIE_ENV} holds no `name=value` pair, so it is not a Cookie header. Copy the "
            f"whole header value, not just the ticket.",
        )
    return value


def _seller_key() -> str:
    """The account's seller key, or the refusal that says where to find it.

    Not a secret — it is the lowercased prefix of every order number this account has — and so
    it appears in no message, because printing configuration a reader did not ask for is how a
    value that "is not a secret" ends up in a screenshot.
    """
    return (envfile.get_live(SELLER_KEY_ENV) or "").strip()


def _agent() -> str:
    return (envfile.get_live(AGENT_ENV) or "").strip() or tcg_export.DEFAULT_AGENT


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Hand a 3xx back to the caller instead of following it.

    NOT ONE HOP, UNLIKE `tcg_export.fetch`. That module follows a single redirect because the
    portal genuinely serves its download off a second URL. This is a JSON API and a redirect
    off it is not a destination anybody meant: it is the edge sending an unauthenticated
    request to a login page. Following it would return a 200 full of HTML, which is the
    failure `_check_status` exists to name instead.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


def _open(
    url: str, *, cookie: str, data: Optional[bytes] = None
) -> Tuple[int, dict, bytes]:
    """One request. Returns (status, headers, body) and raises only for a dead socket."""
    request = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET")
    if data is not None:
        # A PLAIN JSON DOCUMENT. See the module docstring: carrying D65's `model=<json>`
        # form-urlencoded shape here fails, and it is the first thing a reader will try to
        # "fix" this into.
        request.add_header("Content-Type", "application/json")
    request.add_header("Accept", "application/json")
    request.add_header("User-Agent", _agent())
    request.add_header("Origin", ORIGIN)
    request.add_header("Referer", REFERER)
    request.add_header("Cookie", cookie)
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        response = opener.open(request, timeout=TIMEOUT_S)
        return response.status, dict(response.headers), response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as caught:
        # A 3xx reaches here BECAUSE of `_NoRedirect`, which is the point: a non-followed
        # redirect is delivered as an HTTPError, and its headers carry the Location.
        return caught.code, dict(caught.headers), caught.read(MAX_BYTES + 1)
    except urllib.error.URLError as caught:
        raise FetchRefusal(
            "order_unreachable",
            f"Could not reach {urlparse(url).netloc}: {caught.reason}. Nothing was read and "
            f"nothing was written.",
        ) from None
    except TimeoutError:
        raise FetchRefusal(
            "order_unreachable",
            f"{urlparse(url).netloc} did not answer within {TIMEOUT_S}s. Nothing was read and "
            f"nothing was written.",
        ) from None


def _check_status(status: int, headers: dict, body: bytes) -> None:
    """Turn a status into a refusal, or return so the body can be read. One code per problem.

    THE 401/403 SPLIT IS THE WHOLE REASON THIS IS NOT ONE BRANCH. 403 on this host is what a
    missing or wrong `filters.sellerKey` answers, measured — not a 400, which is what anybody
    would assume of a body error. A client that folds it into "sign in again" sends the
    operator to re-copy a working cookie over a bug in this file, which is the exact defect
    D65 recorded on the other host and fixed there.
    """
    note = problem_note(headers, body)
    if status in (301, 302, 303, 307, 308):
        location = str(headers.get("Location") or "")
        if _LOGON_MARKER in location.lower():
            raise FetchRefusal(
                "order_session_expired",
                f"TCGplayer redirected the order request to its login page, which means the "
                f"session in {COOKIE_ENV} has expired. Sign in again, copy the fresh `Cookie:` "
                f"header, and replace the value in .env. Nothing was read.",
            )
        raise FetchRefusal(
            "order_unexpected_response",
            f"The order API answered {status} with a redirect. This is a JSON API and no "
            f"redirect off it is followed. Nothing was read.{note}",
        )
    if status == 401:
        raise FetchRefusal(
            "order_session_expired",
            f"The order API refused the session in {COOKIE_ENV} (401). Sign in again and "
            f"replace the value in .env. It is the same cookie the export uses, so the export "
            f"will have stopped working too. Nothing was read.{note}",
        )
    if status == 403:
        raise FetchRefusal(
            "order_seller_key_rejected",
            f"The order API answered 403. ON THIS HOST THAT IS USUALLY THE REQUEST, NOT THE "
            f"SESSION: a missing or wrong `filters.sellerKey` answers 403 rather than 400. "
            f"Check {SELLER_KEY_ENV} in .env — it is the lowercased prefix of any order number "
            f"on the Orders page. Only if that is right is this the account having lost its "
            f"seller permissions. Nothing was read.{note}",
        )
    if status == 404:
        raise FetchRefusal(
            "order_not_found",
            f"The order API has no such order. It may have been cancelled, or it may belong to "
            f"another account. Nothing was read.{note}",
        )
    if status == 405:
        raise FetchRefusal(
            "order_route_missing",
            f"The order API answered 405, which is what it says when a path is not one of its "
            f"routes — `/orders` is a prefix, not a route. That is a defect here rather than "
            f"anything to fix at TCGplayer. Nothing was read.{note}",
        )
    if status == 429:
        raise FetchRefusal(
            "order_rate_limited",
            f"The order API is rate-limiting this client (429). One fetch is one search plus "
            f"one request per order, so a narrower range is fewer requests. Try again in a "
            f"minute. Nothing was read.{note}",
        )
    if status >= 500:
        raise FetchRefusal(
            "order_unavailable",
            f"The order API answered {status}. That is their end, not this one — try again "
            f"later. Nothing was read.{note}",
        )
    if status != 200:
        raise FetchRefusal(
            "order_unexpected_response",
            f"The order API answered {status} rather than sending orders. Nothing was "
            f"read.{note}",
        )


def _parse(body: bytes, headers: dict) -> Any:
    """The body as JSON, or the refusal that says which kind of not-JSON it is."""
    if len(body) > MAX_BYTES:
        raise FetchRefusal(
            "order_response_too_large",
            f"The order API's answer passed {MAX_BYTES // (1024 * 1024)} MB and was abandoned. "
            f"An order page is tens of kilobytes, so this is not one. Nothing was read.",
        )
    if not body.strip():
        raise FetchRefusal(
            "order_response_unreadable",
            "The order API answered 200 with an empty body. Nothing was read.",
        )
    kind = str(headers.get("Content-Type") or "").lower()
    head = body.lstrip()[:200].lower()
    if "html" in kind or head.startswith(b"<"):
        # A LOGIN PAGE SERVED AS A 200 IS THE THIRD WAY A SESSION FAILS, and on the admin host
        # it is the one that got parsed as data. The header is checked as well as the body
        # because either alone is defeatable.
        raise FetchRefusal(
            "order_session_expired",
            f"The order API sent a web page rather than JSON, which is what a login page looks "
            f"like when it is served without a redirect. The session in {COOKIE_ENV} has most "
            f"likely expired. Nothing was read.",
        )
    try:
        return json.loads(body.decode("utf-8", "replace"))
    except ValueError:
        raise FetchRefusal(
            "order_response_unreadable",
            "The order API's answer did not parse as JSON. The API may have changed shape; "
            "nothing was read.",
        ) from None


def _order_path(order_number: str) -> str:
    """One order number as a path segment, or a refusal.

    THE NUMBER COMES OUT OF A RESPONSE BODY, and a path built out of a response body is how a
    fetch reaches a route nobody chose — `/orders/<n>` with the right `<n>` is
    `/orders/status-updates`, which is a WRITE this repo has ruled it does not make. The
    alphabet is the one real order numbers use; `quote` on top of it is the belt to that
    braces.
    """
    number = str(order_number or "").strip()
    if not number or not set(number) <= _NUMBER_OK:
        raise FetchRefusal(
            "order_number_invalid",
            "That is not an order number this client will put in a URL. Nothing was read.",
        )
    return quote(number, safe="")


# ------------------------------------------------------------------------------- the calls


def _search_page(
    range_: str, page_size: int, frm: int, cookie: str
) -> Tuple[int, List[Dict[str, Any]]]:
    """One page of search results: (totalOrders, projected summaries)."""
    body = search_body(range_, page_size, frm, _seller_key())
    url = f"{base_url()}/orders/search?api-version={API_VERSION}"
    status, headers, raw = _open(url, cookie=cookie, data=json.dumps(body).encode("utf-8"))
    _check_status(status, headers, raw)
    parsed = _parse(raw, headers)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("orders"), list):
        raise FetchRefusal(
            "order_response_unreadable",
            "The order search answered without an `orders` list. The API may have changed "
            "shape; nothing was read.",
        )
    try:
        total = int(parsed.get("totalOrders"))
    except (TypeError, ValueError):
        # NOT FATAL AND NOT GUESSED AT. `totalOrders` only decides whether there is another
        # page; without it, what came back is what there is, which is the honest reading and
        # is what `fetch_open_orders` then reports.
        total = len(parsed["orders"])
    return total, [project_summary(entry) for entry in parsed["orders"]]


def search(
    range_: str = DEFAULT_RANGE,
    page_size: int = DEFAULT_PAGE_SIZE,
    frm: int = 0,
) -> List[Dict[str, Any]]:
    """One page of orders as `{orderNumber, orderDate, status, buyer}`. NO SKUs — see `detail`.

    Public because a caller may legitimately want the numbers without paying for a detail
    request each. Projected, so everything but the display name stays out — see
    `project_summary`.
    """
    return _search_page(range_, page_size, frm, _cookie())[1]


def _detail(
    order_number: str, cookie: str, summary: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """One detail request, checked against the order it was asked for.

    THE ANSWER MUST BE THE ORDER THAT WAS ASKED FOR. A detail response carrying a different
    `orderNumber` is a response to somebody else's request — a proxy serving a cached body, or
    a path this module built wrong — and every line in it belongs to an order this fetch is not
    reading. Merging it in would attribute another order's cards to this one, which resolves to
    a real position and sends a picker to a real box. It is cheap to check and there is no
    reading of it that is safe to accept.
    """
    path = _order_path(order_number)
    url = f"{base_url()}/orders/{path}?api-version={API_VERSION}"
    status, headers, raw = _open(url, cookie=cookie)
    _check_status(status, headers, raw)
    answer = project_order(_parse(raw, headers), summary)
    if answer["orderNumber"].casefold() != str(order_number).strip().casefold():
        raise FetchRefusal(
            "order_number_mismatch",
            f"Asked the order API for {str(order_number).strip()} and it answered with a "
            f"different order. Nothing was read.",
        )
    return answer


def detail(order_number: str) -> Dict[str, Any]:
    """One order, projected: `{orderNumber, orderDate, status, products[]}`.

    THIS IS THE CALL THAT CARRIES THE SKU. `products[].skuId` is the export's `TCGplayer Id`
    is `store/master.py:Card.sku`, and it appears on no other endpoint — which is why a fetch
    is two calls and not one.
    """
    return _detail(order_number, _cookie())


@dataclass(frozen=True)
class FetchResult:
    """What one filtered fetch did, beside the orders it detailed (D91).

    `orders` is the ingest-shaped list and is the only part a caller forwards. The counts are
    what the screen says about the press. `remaining` is the honest word for a cap that stopped
    the detailing: the summaries past it were SEEN and are named as a number rather than dropped
    without a trace, and the next press picks them up because the ledger then knows the ones
    this press detailed.

    `names` IS THE BACKFILL, AND IT COSTS NOTHING (D193). Every entry
    is `{orderNumber, buyer}` for a MATCHED, ALREADY-KNOWN order — one the ledger holds at
    this exact status and so was skipped from `to_detail` — that carries a buyer the summary
    can see. Not `remaining` (uncounted; the next press's detail call will carry its buyer
    same as any other), not `to_detail` (its `orders[]` already carries the name, off the
    detail). This is the set the caller could otherwise never learn a name for: an order this
    press will not detail because nothing about it changed, and so a names-only pass over it
    is the entire cost — one field read off a summary this fetch already paid for.
    """

    orders: List[Dict[str, Any]]
    total: int
    matched: int
    skipped_known: int
    detailed: int
    remaining: int
    names: List[Dict[str, Any]] = field(default_factory=list)


def _summaries(
    range_: str, page_size: int, cookie: str
) -> Tuple[int, List[Dict[str, Any]]]:
    """Every summary in `range_`: the search pages walked whole. `(totalOrders, summaries)`.

    NO CEILING HERE, AND THAT IS D91'S CHANGE. The pages are the cheap half of a fetch — one
    request per 25 orders, 15 for the 370 the owner's account holds in three months — and they
    are what the operator has to see before anything is detailed: which statuses the window
    holds, and how many of each. The two guards below are about PROGRESS, not size.
    """
    summaries: List[Dict[str, Any]] = []
    seen = set()
    total = 0
    offset = 0
    while True:
        total, page = _search_page(range_, page_size, offset, cookie)
        if not page:
            # An empty page ends the walk whatever the total claimed. Trusting `totalOrders`
            # over what arrived is how a loop that cannot make progress runs forever.
            break
        before = len(summaries)
        for entry in page:
            if entry["orderNumber"] not in seen:
                seen.add(entry["orderNumber"])
                summaries.append(entry)
        if len(summaries) == before:
            # A PAGE THAT ADDED NOTHING ENDS THE WALK, and this guard is not theoretical: an
            # endpoint that ignores `from` hands back page one forever, and the loop would
            # then ask for `totalOrders / page_size` pages of the same twenty-five orders.
            # Progress is measured in NEW order numbers rather than in the offset, because
            # the offset is what such an endpoint is ignoring.
            break
        offset += len(page)
        if len(summaries) >= total or offset >= total:
            break
    return total, summaries


def summaries(
    range_: str = DEFAULT_RANGE, *, page_size: int = DEFAULT_PAGE_SIZE
) -> List[Dict[str, Any]]:
    """Every order in `range_` as `{orderNumber, orderDate, status, buyer}`, NOT ONE DETAIL
    CALL.

    Public because `POST /orders/fetch {preview: true}` answers from this alone: the statuses
    the window holds, counted by the STRING the wire returned, so the operator can tick the ones
    worth a detail request each (D91). Projected, so everything but the display name stays out
    — see `project_summary`. This is also the whole of a names-only backfill's cost: a caller
    that wants buyers for orders it will not detail reads `buyer` off exactly these rows.
    """
    return _summaries(range_, page_size, _cookie())[1]


def fetch_open_orders(
    range_: str = DEFAULT_RANGE,
    *,
    page_size: int = DEFAULT_PAGE_SIZE,
    limit: int = MAX_ORDERS,
    statuses: Optional[Sequence[str]] = None,
    known: Optional[Dict[str, str]] = None,
) -> FetchResult:
    """The orders in `range_` the operator asked for, each with its lines, projected.

    THE SHAPE IS WHAT `pipeline/orders.py` INGESTS, field for field:

        {"orderNumber": str,  ->  Order.number
         "orderDate":   str,  ->  Order.placed_at
         "status":      str,  ->  kept for the screen; nothing here routes on it
         "buyer": str | None, ->  Order.buyer — the display name, and nothing else
                                   about who they are (D193)
         "products": [{"skuId":  str,  ->  OrderLine.sku
                       "quantity": int, ->  OrderLine.quantity
                       "name":   str,   ->  OrderLine.name
                       "unitPrice": str ->  OrderLine.unit_price}]}

    `OrderLine.kind` is deliberately absent. `pipeline/orders.py` defaults it to `single` and
    its docstring rules that the module ROUTES on what the feed says rather than classifying —
    deciding that "Booster Box" is sealed by reading a product name is the guessing `CLAUDE.md`
    forbids. This feed does not say, so this module does not say either, and a sealed product
    surfaces honestly as `sku_unseen` rather than being quietly reclassified.

    THE WINDOW IS THE RANGE AND THE STATUS IS THE FILTER, AND THE OPERATOR HOLDS IT (D91).
    "Open" is still not a status filter this module applies on its own: the vocabulary was
    never enumerated on the wire — one capture, one account, one afternoon — and a guess that
    drops an order is an envelope that never ships. What changed is who chooses. `statuses` is
    the list the operator ticked off the strings `summaries` returned, compared VERBATIM after a
    strip — never folded, never mapped — and `None` still means every order in the window.

    THE CAP IS ON DETAIL CALLS, NOT ON THE WINDOW, and until D91 that inversion meant this
    function had never returned an order on the owner's account: 370 in three months against a
    cap of 100, refused on every press with a remedy the range vocabulary cannot express. The
    summaries are walked whole. Of the ones that match, `known` — `{number: status}` as the
    ledger holds them — removes the orders a previous press already detailed at this status,
    and the first `limit` of the rest are detailed. What is left is `remaining`: seen, counted,
    reported, and picked up by the next press because the ledger will then know these.

    IT NEVER SLEEPS. Fifteen pages plus a hundred details is 115 requests against the 120 a
    minute the bridge extension holds itself to. A route that slept its way through 370 would
    block one request for minutes, which is the wrong shape for a button. Two presses inside one
    minute can pass the budget and this module does not stop them; D91 names that cost.

    NOTHING IS WRITTEN. This is a read: no card state, no listing count, no run directory. D63
    makes a replay a no-op by construction rather than by a guard.
    """
    cookie = _cookie()
    try:
        ceiling = int(limit)
    except (TypeError, ValueError):
        raise FetchRefusal(
            "order_page_invalid",
            "The order limit must be a whole number. Nothing was fetched.",
        ) from None
    if not 1 <= ceiling <= MAX_ORDERS:
        raise FetchRefusal(
            "order_page_invalid",
            f"A limit of {ceiling} orders is outside 1..{MAX_ORDERS}. The ceiling is a rate "
            f"limit, not a preference: one fetch is one search page per 25 orders plus one "
            f"request per order detailed, and {MAX_ORDERS} details keeps a press inside the "
            f"120-per-minute budget the only other client anyone has measured holds itself to. "
            f"Nothing was fetched.",
        )
    wanted: Optional[set] = None
    if statuses is not None:
        wanted = {str(status).strip() for status in statuses if str(status).strip()}
        if not wanted:
            raise FetchRefusal(
                "order_status_required",
                "An empty status list would detail nothing. Send the statuses to detail, as "
                "the summaries spelled them, or None for every order in the window. Nothing "
                "was fetched.",
            )
    # THE LEDGER'S KEY IS FOLDED TO COMPARE AND THE STATUS IS NOT. `store/orders.py:order_key`
    # folds the number for the same reason; the status is the API's own word and a fold of it
    # would be the first step toward the vocabulary this module refuses to have.
    known_at: Dict[str, str] = {
        str(number).strip().casefold(): str(status).strip()
        for number, status in (known or {}).items()
    }

    total, every = _summaries(range_, page_size, cookie)
    matched = [
        entry for entry in every
        if wanted is None or str(entry.get("status") or "").strip() in wanted
    ]
    fresh = [
        entry for entry in matched
        if known_at.get(str(entry["orderNumber"]).strip().casefold())
        != str(entry.get("status") or "").strip()
    ]
    to_detail = fresh[:ceiling]

    # THE SUMMARY IS PASSED IN so the detail's `createdAt`/`status` can fall back to the
    # search's `orderDate`/`orderStatus`. The two endpoints spell the same two facts
    # differently, and an order left dateless sorts LAST in `order_sequence` — which would hand
    # stock to a newer order over an older one.
    orders = [_detail(entry["orderNumber"], cookie, entry) for entry in to_detail]

    # THE BACKFILL, AND IT IS `matched MINUS fresh` — never `matched minus to_detail`. `fresh`
    # is already the entries whose status DISAGREES with what the ledger holds, so `matched
    # minus fresh` is every summary the ledger already holds at this EXACT status: the ones a
    # detail call would be spent on for nothing, `known_at` having already agreed with the
    # wire. An entry that is fresh but past the detail ceiling belongs to `remaining` and
    # NOT to `names` — its status changed, its buyer may have too, and the honest place for
    # it is the next press's detail call, not a guess read off a summary this press did not
    # trust enough to skip.
    #
    # Their names are otherwise invisible to a caller that skips known orders on every press:
    # this account's window holds far more than `MAX_ORDERS` lets it detail per press, so the
    # steady state is "matched but not fresh" for almost everything, and a names backfill that
    # only read `orders[]` would only ever learn a name for the handful of orders that
    # happened to change status today.
    fresh_numbers = {str(entry["orderNumber"]).strip().casefold() for entry in fresh}
    names = [
        {"orderNumber": entry["orderNumber"], "buyer": entry["buyer"]}
        for entry in matched
        if str(entry["orderNumber"]).strip().casefold() not in fresh_numbers
        and entry.get("buyer")
    ]

    return FetchResult(
        orders=orders,
        total=total,
        matched=len(matched),
        skipped_known=len(matched) - len(fresh),
        detailed=len(to_detail),
        remaining=len(fresh) - len(to_detail),
        names=names,
    )
