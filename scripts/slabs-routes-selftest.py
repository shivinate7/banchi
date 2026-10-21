#!/usr/bin/env python3
"""`server/slabs_routes.py`, the My Slabs routes, proved against the real Card Ladder `Client` on
a fake transport, a fake clock and a throwaway store: no network, no real sleep, no real store.

Protects: A slab added by cert is read, written once per day and listed with every number traced to a Card Ladder read, and a failed or limited read writes nothing.
Governs: D320, D88, D196, D319

BUILD PLAN STEP 3 (`docs/specs/my-slabs.md`). The owner DEFERRED the sweep: it waits for the
owner's word. Until that word: NO sweep route, no screen for a sweep, no launchd job. The spec's
build plan names a sweep in steps 3 to 5 and section 5; this file pins the deferral.

ROUTES, in `server/slabs_routes.py`, dispatched by `server/capture_server.py`. A refusal is a
`server.refusal.BadRequest(status, code, message)`: the dispatcher already catches it.

    POST /slabs                    do_slab_add(body) -> receipt
    GET  /slabs                    do_slabs() -> {"slabs": [row, ...]}
    GET  /slabs/<grader>/<cert>    do_slab(grader, cert) -> detail     (URL-decoded; any grader form)

SEAMS: module attributes of `server.slabs_routes`, read at CALL time (never a default argument,
never a copy bound at import). The route builds the real `pipeline.cardladder.Client` from them:

    TRANSPORT  (method, url, headers, body) -> (status, bytes)     None means the client's own
    CLOCK      () -> float, SLEEP (seconds) -> None                 default time.monotonic, time.sleep
    TODAY      () -> "YYYY-MM-DD", the day a snapshot belongs to    default: the local date
    the token  `envfile.get_live("CARDLADDER_REFRESH_TOKEN")`, read on every add

ONE Client LIVES FOR THE PROCESS, not one per request: the pacing (8 s between callable sends) and
the rate-limit latch are the client's, so a Client per request would defeat both. A rate-limit
answer stops adds for that day (`TODAY()`); the next day adds again. A token that is replaced in
`.env` works on the next add, with no restart.

WIRE (text money, ISO dates, `null` for a value Card Ladder did not give):

    add body    {"cert": "<text>", "grader": "psa|beckett|bgs|bvg|sgc|cgc" (any case)}
    receipt     {"cert", "grader" (Card Ladder's name), "label", "day", "added": bool, "message"}
                `added` is false when the slab was already there; `message` is one sentence that
                names the slab by its label.
    snapshot    {"day", "cl_value", "cl_confidence", "estimated_value", "estimated_confidence",
                 "last_sale_price", "last_sale_date", "population", "gem_rate", "speed"}
    row         {"cert", "grader", "label", "grade", "added", "snapshot": newest | null,
                 "note": "no sales" | null}
    detail      {"slab": {"cert", "grader", "label", "grade", "added"}, "snapshots": oldest day
                 first, "sales": newest first (each the stored sale: "id", "date", "price", "url",
                 ...), "ladder": [{"grade", "label", "cl_value", "cl_confidence"}] in Card
                 Ladder's order, "note"}; sales are the slab's grader and grade only.
    refusal codes   grader_unknown 400, cert_required 400, cert_not_found 404, slab_unknown 404,
                    cardladder_token_missing, cardladder_token_rejected, cardladder_rate_limited,
                    sale_date_unreadable, and any other Card Ladder failure under a code of its own.
    client      `addSlab({cert, grader}): Promise<SlabReceipt>`, `getSlabs(): Promise<SlabList>`,
                `getSlabDetail(grader, cert): Promise<SlabDetail>` in `app/src/server.ts`, with
                those four wire types in `app/src/types.ts` (`tsc` ties the names to the file).

WHAT EACH ADD DOES: 3.1, 3.2, 3.4 and no other callable (spec 5: three calls a slab), the reads
OUTSIDE the store lock (they are paced and take 16 seconds or more), then ONE store write: the
slab, today's snapshot and the sales. Any refusal writes nothing at all. The snapshot's last sale
is the newest sale at the slab's grader and grade in 3.2, never 3.4's `lastSalePrice`. The value
fields come from the ladder row at the slab's grade (`clValue`) and from 3.4 (`estimatedValue`).
A slab with no sale at its grade stores NO value (cl_value, estimated_value, last_sale_price and
last_sale_date are None) and its row says "no sales".

This file parses on the bare system python3 (3.9). The fake world refuses the real network and a
real sleep of a second or more; a touch is recorded and fails the run. In `make check`, never in
the git hook: it writes a temp store (D18).
"""

from __future__ import annotations

import calendar
import contextlib
import importlib
import importlib.util
import io
import json
import logging
import os
import re
import socket
import sys
import threading
import time
import traceback
import urllib.parse
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.tests.home import isolated_home  # noqa: E402
from pipeline import cardladder, net  # noqa: E402
from server.refusal import BadRequest  # noqa: E402
from store import files  # noqa: E402
from store.session import Store  # noqa: E402

PASS = 0
FAIL = 0
VIOLATIONS: list = []
POOL: list = []  # every sentence and answer the routes produced, searched for the fake tokens
OUT = sys.__stdout__


def ok(condition: bool, label: str, detail: str = "") -> bool:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ok     {label}", file=OUT)
    else:
        FAIL += 1
        print(f"  FAIL   {label}", file=OUT)
        if detail:
            for line in str(detail).splitlines()[:8]:
                print(f"         {line}", file=OUT)
    return bool(condition)


def same(label: str, got, want) -> bool:
    return ok(got == want, label, f"got  {got!r}\nwant {want!r}")


# ------------------------------------------------------------------------------ constants

KEY = cardladder.KEY_NAME
RT = "RTSENTINEL-5c1e90b2-refresh"  # the fake refresh token in the environment
RT_NEW = "RTSENTINEL-0d43aa17-rotated"
ID_MARK = "IDSENTINEL-77aa31d4"  # every fake ID token holds this
CF_HOST = urllib.parse.urlsplit(cardladder.CALLABLE_BASE).hostname
GOOGLE_HOST = urllib.parse.urlsplit(cardladder.TOKEN_URL).hostname
DAY1, DAY2 = "2026-10-20", "2026-10-21"
CERT, CERT2, CERT3 = "12345678", "87654321", "55555555"
PROFILE = "psa-4d2f"
LABEL = "2023 Pokemon Obsidian Flames Charizard ex 125 PSA 10"
LIMIT_BODY = json.dumps(
    {"error": {"message": "Too many requests. Please wait a minute and try again.",
               "status": "RESOURCE_EXHAUSTED"}}).encode()
# A failing answer that holds both fake tokens: a route that relays a response body leaks them (D320).
FAIL_BODY = json.dumps({"error": {"message": "internal Bearer " + ID_MARK + " " + RT, "status": "INTERNAL"}}).encode()
EMPTY = {"slabs": {}, "snapshots": {}, "sales": {}, "links": {}}
# The sentences D196 refuses: scripts/error-words.py's own checks, plus a host (it has none).
HOST_RE = re.compile(r"://|\b[\w-]+\.(?:com|net|org|io|app|dev|invalid)\b|googleapis|cloudfunctions|cardladder-71d53", re.I)


def _error_words():
    spec = importlib.util.spec_from_file_location("error_words", ROOT / "scripts" / "error-words.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ERROR_WORDS = _error_words()


# ------------------------------------------------------------------------------ Card Ladder's data


def noon(y: int, m: int, d: int) -> int:
    """Epoch seconds at 12:00 UTC: the same calendar day in every time zone."""
    return calendar.timegm((y, m, d, 12, 0, 0))


def raw_sale(sid, date, price, grader="psa", grade="g10") -> dict:
    return {
        "id": sid, "itemId": "item-" + sid, "title": "Charizard ex 125 " + sid, "seller": "cardshop",
        "platform": "ebay", "listingType": "auction", "price": price, "date": date,
        "url": "https://sale.invalid/" + sid, "grader": grader, "grade": grade,
        "memberVerified": False, "cardId": "card-1001",
    }


def default_sales(grader="psa", grade="g10") -> list:
    """Five sales at the grade, each date in a different form Card Ladder might send (the format is
    unmeasured), one newer sale at another grade and one newer sale at another grader."""
    return [
        raw_sale("s-old", "2026-09-01", 41, grader, grade),
        raw_sale("s-mid", "2026-09-10T12:00:00.000Z", 24 * 1.1, grader, grade),  # 26.400000000000002
        raw_sale("s-c", noon(2026, 9, 20), 44.0, grader, grade),
        raw_sale("s-d", noon(2026, 9, 25) * 1000, 99.99, grader, grade),
        raw_sale("s-new", {"_seconds": noon(2026, 9, 30), "_nanoseconds": 0}, 116.4, grader, grade),
        raw_sale("s-off", "2026-10-05", 20, grader, "g9"),
        raw_sale("s-cgc", "2026-10-06", 500, "cgc", grade),
    ]


AT_GRADE = ("s-new", "s-d", "s-c", "s-mid", "s-old")  # newest first
WANT_PRICE = {"s-new": "116.40", "s-d": "99.99", "s-c": "44.00", "s-mid": "26.40", "s-old": "41.00"}
WANT_DAY = {"s-new": "2026-09-30", "s-d": "2026-09-25", "s-c": "2026-09-20",
            "s-mid": "2026-09-10", "s-old": "2026-09-01"}
WINDOWS = {"twoWeekData": (0.5, 99.1, "99.10"), "oneMonthData": (1.5, 101, "101.00"),
           "oneQuarterData": (2.0, 102.25, "102.25"), "sixMonthData": (2.5, 103, "103.00"),
           "oneYearData": (3.0, 104.5, "104.50")}
SPEED_WANT = {w: {"velocity": v, "averagePrice": text} for w, (v, _p, text) in WINDOWS.items()}


def lookup_result(cert, grader, grade, profile_id, label, subgrades) -> dict:
    return {
        "cert": cert, "grader": grader, "subGrader": None, "graderId": grader, "profileId": profile_id,
        "label": label, "grade": grade, "qualifierType": None, "autographGrade": None,
        "subGrades": subgrades, "dateGraded": "2024-02-01", "lastUpdated": "2026-10-19T08:00:00Z",
        "source": grader, "population": 412,
        "profile": {
            "category": "pokemon", "year": "2023", "set": "Obsidian Flames", "subject": "Charizard ex",
            "number": "125", "variation": None, "graderList": [grader], "totalPopulation": 9000,
            "totalGems": 4000, "gemRate": 0.44,
            "graders": {grader: {"grades": {grade: 412, "g9": 3000}}},
        },
    }


def profile_result(grader, grade, sales, ladder) -> dict:
    return {
        "sales": sales,
        "graders": [{"grader": grader, "grades": [
            {"grade": grade, "label": grader.upper() + " 10", "clValue": ladder, "clValueConfidence": 5,
             "price": 116.4, "lastSold": "2026-09-30", "power": 1, "value": ladder},
            {"grade": "g9", "label": grader.upper() + " 9", "clValue": 44, "clValueConfidence": 3,
             "price": 20, "lastSold": "2026-10-05", "power": 1, "value": 44},
        ]}],
        "totalPopulation": 9000, "totalGems": 4000, "gemRate": 0.44, "index": "Pokemon",
    }


def estimate_result(value, confidence) -> dict:
    out = {
        "estimatedValue": value, "confidence": confidence,
        "lastSalePrice": 41.0, "lastSaleDate": "2026-09-01",  # trails the newest sale, as in 4.3
        "index": "Pokemon", "indexId": "idx-1", "indexPercentChange": 1.2,
    }
    for window, (velocity, price, _text) in WINDOWS.items():
        out[window] = {"velocity": velocity, "averagePrice": price}
    return out


def card(cert=CERT, grader="psa", grade="g10", profile_id=PROFILE, label=LABEL, subgrades=None,
         sales=None, ladder=238.5, estimate=123.45, confidence=4) -> SimpleNamespace:
    sales = default_sales(grader, grade) if sales is None else sales
    return SimpleNamespace(
        grader=grader, cert=cert, profile_id=profile_id,
        lookup=lookup_result(cert, grader, grade, profile_id, label, subgrades),
        profile=profile_result(grader, grade, sales, ladder),
        estimate=estimate_result(estimate, confidence))


WANT_V1 = dict(
    cl_value="238.50", cl_confidence=5, estimated_value="123.45", estimated_confidence=4,
    last_sale_price="116.40", population=412, gem_rate=0.44, speed=SPEED_WANT)


class World:
    """A fake clock, a fake Google token endpoint and a fake Card Ladder, one per case.
    The real `cardladder.Client` runs against it. Every request is logged; an exchange of a refresh
    token not in `accepted` is a 400 that echoes the request, the worst case for a leak."""

    def __init__(self) -> None:
        self.now = 1_000_000.0
        self.day = DAY1
        self.accepted = {RT}
        self.google = None  # (status, body) for the token exchange, or None
        self.fail = {}  # callable name -> (status, body)
        self.lookups, self.profiles, self.estimates = {}, {}, {}
        self.log = []  # (t, host) of every request
        self.calls = []  # one SimpleNamespace(t, name, data) per callable request
        self.lock_free = []  # was the store lock free while a callable request was being served?
        self.tokens = set()

    def load(self, c) -> None:
        self.lookups[(c.grader, c.cert)] = c.lookup
        self.profiles[c.profile_id] = c.profile
        self.estimates[c.profile_id] = c.estimate

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds

    def transport(self, method, url, headers, body):
        parts = urllib.parse.urlsplit(url)
        self.log.append((self.now, parts.hostname))
        if parts.hostname == GOOGLE_HOST:
            if self.google is not None:
                return self.google
            fields = {k: v[0] for k, v in urllib.parse.parse_qs(body.decode("utf-8", "replace")).items()}
            if fields.get("refresh_token") not in self.accepted:
                return 400, body
            token = "ID-%d-%s" % (len(self.tokens) + 1, ID_MARK)
            self.tokens.add(token)
            return 200, json.dumps({"id_token": token, "expires_in": "3600", "user_id": "UID-TEST"}).encode()
        if parts.hostname != CF_HOST:
            raise OSError("the fake world has no host " + str(parts.hostname))
        name = parts.path.rsplit("/", 1)[-1]
        data = json.loads(body)["data"]
        self.calls.append(SimpleNamespace(t=self.now, name=name, data=data))
        try:  # the reads are paced and slow, so they may not hold the store lock
            with Store().write(timeout=0.3):
                self.lock_free.append(True)
        except files.LockTimeout:
            self.lock_free.append(False)
        if headers.get("Authorization", "")[len("Bearer "):] not in self.tokens:
            return 401, json.dumps({"error": {"message": "unauthenticated"}}).encode()
        if name in self.fail:
            return self.fail[name]
        if name == "httpcertlookup":
            result = self.lookups.get((data.get("grader"), data.get("cert")))
        elif name == "httpprofile":
            result = self.profiles.get(data.get("profileId"))
        elif name == "httpcardestimate":
            result = self.estimates.get(data.get("profileId"))
        else:
            return 404, b"{}"  # a callable the add may not use
        return 200, json.dumps({"result": result}).encode()


def new_world(routes) -> World:
    """A new fake world AND a fresh module, as after a restart: no client, latch or pacing left over."""
    importlib.reload(routes)
    w = World()
    routes.TRANSPORT, routes.CLOCK, routes.SLEEP = w.transport, w.clock, w.sleep
    routes.TODAY = lambda: w.day
    os.environ[KEY] = RT
    return w


def load_routes():
    try:
        module = import_module("server.slabs_routes")
    except ModuleNotFoundError as exc:
        if exc.name != "server.slabs_routes":
            raise
        return None
    return importlib.reload(module)  # a fresh process: no client, latch or pacing left over


# ------------------------------------------------------------------------------ the store

HOMES: list = []


@contextmanager
def fresh_home():
    with isolated_home() as tmp:
        HOMES.append(Path(tmp).resolve())
        try:
            yield tmp
        finally:
            HOMES.pop()


def store() -> Store:
    if not HOMES or not Store().directory.resolve().is_relative_to(HOMES[-1]):
        raise SystemExit(f"slabs-routes-selftest: {Store().directory} is not inside a temporary home; stopping")
    return Store()


def slabs_now():
    return store().read().slabs


def dump() -> dict:
    """Every row of the four tables, as text, from a fresh read."""
    s = slabs_now()
    return {name: {k: repr(table[k]) for k in sorted(table)}
            for name, table in (("slabs", s.slabs), ("snapshots", s.snapshots), ("sales", s.sales), ("links", s.links))}


def count(table) -> int:
    """Rows in a table. `len(table)` is not used: it double counts rows a `sales_for` already loaded."""
    return len(list(table))


def snap_fields(row, names) -> dict:
    return {name: getattr(row, name) for name in names}


# ------------------------------------------------------------------------------ the checks


def refused(fn, *args):
    try:
        fn(*args)
    except Exception as exc:  # noqa: BLE001 - the case reports a wrong type
        return exc
    return None


def plain(label: str, text: str) -> None:
    """A sentence a person reads: scripts/error-words.py's checks, and no host (D196)."""
    POOL.append(text)
    problems = ERROR_WORDS.problems(text)
    host = HOST_RE.search(text)
    ok(not problems and not host, f"{label}: a plain sentence that names no decision, path or host",
       f"{text!r}  {problems}  {host.group(0) if host else ''}")


def refusal(label: str, exc, code=None, status=None):
    """Check a refusal; return its text."""
    if not ok(isinstance(exc, BadRequest), f"{label}: refused with a BadRequest", repr(exc)):
        return ""
    if code:
        same(f"{label}: code", exc.code, code)
    if status:
        same(f"{label}: status", int(exc.status), status)
    else:
        ok(int(exc.status) >= 400, f"{label}: an error status", str(int(exc.status)))
    plain(label, str(exc))
    return str(exc)


def gaps(calls) -> list:
    return [round(b.t - a.t, 6) for a, b in zip(calls, calls[1:])]


def add(routes, cert=CERT, grader="psa"):
    answer = routes.do_slab_add({"cert": cert, "grader": grader})
    POOL.append(json.dumps(answer, default=str))
    return answer


def date_shape(text) -> str:
    return re.sub(r"\d", "9", text) if isinstance(text, str) else repr(type(text))


# ------------------------------------------------------------------------------ cases


def case_world_control():
    """0. control: the fake world serves the real client, so a red below is the routes' and not the fake's"""
    w = World()
    w.load(card())
    client = cardladder.Client(refresh_token=RT, transport=w.transport, clock=w.clock, sleep=w.sleep)
    look = cardladder.cert_lookup(client, CERT, "psa")
    prof = cardladder.profile(client, look["profileId"])
    est = cardladder.card_estimate(client, look["profileId"], "psa", look["grade"], look["label"], None, None)
    same("a lookup, a profile and an estimate come back whole",
         (look["profileId"], len(prof["sales"]), est["estimatedValue"]), (PROFILE, 7, 123.45))
    ok(all(g >= cardladder.PACE_SECONDS for g in gaps(w.calls)) and len(w.calls) == 3,
       "three paced callable sends", str(gaps(w.calls)))
    w2 = World()
    w2.accepted = set()
    c2 = cardladder.Client(refresh_token=RT, transport=w2.transport, clock=w2.clock, sleep=w2.sleep)
    ok(isinstance(refused(cardladder.cert_lookup, c2, CERT, "psa"), cardladder.TokenRejected),
       "a token Google refuses is TokenRejected")
    w3 = World()
    w3.fail["httpcertlookup"] = (429, LIMIT_BODY)
    c3 = cardladder.Client(refresh_token=RT, transport=w3.transport, clock=w3.clock, sleep=w3.sleep)
    ok(isinstance(refused(cardladder.cert_lookup, c3, CERT, "psa"), cardladder.RateLimited),
       "a 429 is RateLimited")
    ok(w3.lock_free == [True], "and the lock probe sees a free store lock when nothing holds it", str(w3.lock_free))
    with store().write():  # the probe must fire when the lock IS held, or "never holds it" proves nothing
        w4 = World()
        w4.load(card())
        c4 = cardladder.Client(refresh_token=RT, transport=w4.transport, clock=w4.clock, sleep=w4.sleep)
        cardladder.cert_lookup(c4, CERT, "psa")
    ok(w4.lock_free == [False], "and it sees a held one", str(w4.lock_free))


def case_seams(routes):
    """1. the module has the handlers and the four seams, and no sweep"""
    for name in ("do_slab_add", "do_slabs", "do_slab"):
        ok(callable(getattr(routes, name, None)), f"server.slabs_routes has {name}")
    for name in ("TRANSPORT", "CLOCK", "SLEEP", "TODAY"):
        ok(hasattr(routes, name), f"server.slabs_routes has the seam {name}")
    sweeps = [n for n in dir(routes) if "sweep" in n.lower()]
    same("the owner ruled no sweep: nothing in the module is named for one", sweeps, [])


def case_add(routes):
    """2. add: 3.1, 3.2 and 3.4 are read, and the slab, today's snapshot and the sales are written once"""
    w = new_world(routes)
    w.load(card())
    receipt = add(routes)
    same("the receipt names the slab", {k: receipt.get(k) for k in ("cert", "grader", "label", "day", "added")},
         {"cert": CERT, "grader": "psa", "label": LABEL, "day": DAY1, "added": True})
    ok(LABEL in str(receipt.get("message")), "and its message is a sentence that names the slab by its label",
       str(receipt.get("message")))
    plain("the receipt", str(receipt.get("message")))

    names = [c.name for c in w.calls]
    same("exactly three callables, 3.1 first", (len(names), names[:1]), (3, ["httpcertlookup"]))
    same("the other two are 3.2 and 3.4", sorted(names[1:]), ["httpcardestimate", "httpprofile"])
    by = {c.name: c.data for c in w.calls}
    look = by.get("httpcertlookup", {})
    same("3.1 gets the cert as typed, the grader in Card Ladder's name, with the profile",
         (look.get("cert"), look.get("grader"), look.get("includeProfile")), (CERT, "psa", True))
    same("3.2 gets 3.1's profile id", by.get("httpprofile"), {"profileId": PROFILE})
    est = by.get("httpcardestimate", {})
    same("3.4 gets 3.1's profile, grader, grade, qualifier and autograph grade",
         tuple(est.get(k) for k in ("profileId", "grader", "grade", "qualifierType", "autographGrade")),
         (PROFILE, "psa", "g10", None, None))
    ok(isinstance(est.get("description"), str) and est["description"] != "", "and a description")
    ok(w.lock_free and all(w.lock_free), "the paced reads never hold the store lock", str(w.lock_free))

    s = slabs_now()
    slab = s.get(CERT, "psa")
    same("the slab is stored with its profile, label, grade and the day it was added",
         (slab.cert, slab.grader, slab.profile_id, slab.added, slab.identity.get("label"), slab.identity.get("grade"))
         if slab else None, (CERT, "psa", PROFILE, DAY1, LABEL, "g10"))
    snaps = s.snapshots_for(CERT, "psa")
    same("one snapshot, today's", [x.day for x in snaps], [DAY1])
    if snaps:
        same("it holds both values with their confidence, the newest at-grade sale, population, gem rate and speed",
             snap_fields(snaps[0], WANT_V1), WANT_V1)
        same("the last sale is 3.2's newest sale at the grade, not 3.4's trailing one and not a newer sale at another grade",
             (snaps[0].last_sale_price, snaps[0].last_sale_date[:10]), ("116.40", "2026-09-30"))
    stored = {x.id for x in s.sales_for(CERT, "psa")}
    ok(set(AT_GRADE) <= stored, "every sale at the slab's grade is stored", str(sorted(stored)))
    before_sales = count(s.sales)

    w.load(card(estimate=None, confidence=None))  # the same day, and now 3.4 gives no estimate
    again = add(routes)
    same("the same slab added again is an update, not a second slab",
         (again.get("added"), again.get("day")), (False, DAY1))
    s = slabs_now()
    same("still one slab and one snapshot, and no sale twice",
         (count(s.slabs), count(s.snapshots), count(s.sales)), (1, 1, before_sales))
    row = s.snapshots_for(CERT, "psa")[0]
    same("the day's row was REPLACED: no estimate is left from the first read",
         (row.estimated_value, row.estimated_confidence, row.cl_value), (None, None, "238.50"))

    w.load(card())
    w.day = DAY2
    nxt = add(routes)
    s = slabs_now()
    same("the next day adds a second snapshot", [x.day for x in s.snapshots_for(CERT, "psa")], [DAY1, DAY2])
    same("the receipt says it was an update, on the new day", (nxt.get("added"), nxt.get("day")), (False, DAY2))
    same("and the slab keeps the day it was first added", s.get(CERT, "psa").added, DAY1)


def case_grader_forms(routes):
    """3. bgs, bvg and beckett are one slab, and a cert is text"""
    w = new_world(routes)
    sub = {"centering": 9.5, "corners": 9.5, "edges": 9, "surface": 9.5}
    w.load(card(cert="0012345678", grader="beckett", grade="g9_5", profile_id="beckett-77",
                label="2022 Pokemon Crown Zenith Pikachu BGS 9.5", subgrades=sub,
                sales=default_sales("beckett", "g9_5")))
    first = add(routes, "0012345678", "BGS")
    same("a BGS slab is filed under Card Ladder's name and keeps its zeros",
         (first.get("cert"), first.get("grader"), first.get("added")), ("0012345678", "beckett", True))
    look = {c.name: c.data for c in w.calls}.get("httpcertlookup", {})
    same("and 3.1 was asked for beckett", (look.get("cert"), look.get("grader")), ("0012345678", "beckett"))
    s = slabs_now()
    slab = s.get("0012345678", "beckett")
    same("the subgrades are stored as given", slab.subgrades if slab else None, sub)
    second = add(routes, "0012345678", "bvg")
    third = add(routes, "0012345678", "beckett")
    same("bvg and beckett are the same slab: updates", (second.get("added"), third.get("added")), (False, False))
    same("one slab row", count(slabs_now().slabs), 1)


def case_refusals(routes):
    """4. add refusals: a plain sentence and no write, each"""
    w = new_world(routes)
    w.load(card())

    exc = refused(routes.do_slab_add, {"cert": CERT, "grader": "pokemon"})
    refusal("an unknown grader", exc, "grader_unknown", 400)
    same("it sent nothing", w.log, [])
    for body in ({"grader": "psa"}, {"cert": "   ", "grader": "psa"}):
        refusal(f"no cert {body!r}", refused(routes.do_slab_add, body), "cert_required", 400)
    same("and sent nothing", w.log, [])

    del os.environ[KEY]
    text = refusal("no token in the environment", refused(routes.do_slab_add, {"cert": CERT, "grader": "psa"}),
                   "cardladder_token_missing")
    ok(KEY in text, "it names the key", text)
    same("and sent nothing", w.log, [])
    os.environ[KEY] = RT

    gone = new_world(routes)  # Card Ladder has no such cert: a null answer, then an empty one
    for label, answer in (("a null answer", (200, b'{"result": null}')), ("an empty answer", (200, b'{"result": {}}'))):
        gone.fail["httpcertlookup"] = answer
        gone.calls.clear()
        refusal(f"Card Ladder has no such cert ({label})", refused(routes.do_slab_add, {"cert": "999", "grader": "psa"}),
                "cert_not_found", 404)
        same("it stopped after 3.1", [c.name for c in gone.calls], ["httpcertlookup"])

    rejected = new_world(routes)
    rejected.accepted = set()
    text = refusal("a token Google refuses", refused(routes.do_slab_add, {"cert": CERT, "grader": "psa"}),
                   "cardladder_token_rejected")
    low = text.lower()
    ok("copy" in low and "again" in low and KEY in text, "it says to copy the token again, and names the key", text)
    same("and no callable was sent", rejected.calls, [])

    for failing in ("httpcertlookup", "httpprofile", "httpcardestimate"):
        with fresh_home():  # a rate limit is kept in the store for the day, so each one gets a store of its own
            limited = new_world(routes)
            limited.load(card())
            limited.fail[failing] = (429, LIMIT_BODY)
            text = refusal(f"a rate limit on {failing}", refused(routes.do_slab_add, {"cert": CERT, "grader": "psa"}),
                           "cardladder_rate_limited")
            ok("tomorrow" in text.lower(), "it says to try tomorrow", text)
            same("and it stopped at the limited call", limited.calls[-1].name if limited.calls else None, failing)
            same("and it wrote no slab, snapshot or sale", dump(), EMPTY)

    for label, setup in (
        ("Google limits the exchange", lambda x: setattr(x, "google", (429, b"slow down " + RT.encode()))),
        ("Google fails the exchange", lambda x: setattr(x, "google", (503, b"down " + RT.encode()))),
        ("3.1 fails", lambda x: x.fail.update(httpcertlookup=(500, FAIL_BODY))),
        ("3.2 fails", lambda x: x.fail.update(httpprofile=(500, FAIL_BODY))),
        ("3.4 fails", lambda x: x.fail.update(httpcardestimate=(500, FAIL_BODY))),
    ):
        broken = new_world(routes)
        broken.load(card())
        setup(broken)
        exc = refused(routes.do_slab_add, {"cert": CERT, "grader": "psa"})
        text = refusal(label, exc)
        if isinstance(exc, BadRequest):
            ok(exc.code not in ("cardladder_token_rejected", "cardladder_rate_limited", "cardladder_token_missing"),
               f"{label}: its code is not a token or rate-limit code", exc.code)
            ok("copy" not in text.lower() and "tomorrow" not in text.lower(),
               f"{label}: it does not tell the owner to copy the token or wait a day", text)

    bad = new_world(routes)
    for label, date in (("words", "last Tuesday"), ("none", None)):
        bad.load(card(sales=default_sales() + [raw_sale("s-bad", date, 10)]))
        refusal(f"a sale at the grade with a date nobody can read ({label})",
                refused(routes.do_slab_add, {"cert": CERT, "grader": "psa"}), "sale_date_unreadable")

    same("through all of these the store was never written", dump(), EMPTY)


def case_failed_read(routes):
    """5. a failed or limited read writes no snapshot, no sale and no slab over a good one"""
    w = new_world(routes)
    w.load(card())
    add(routes)
    before = dump()
    ok(len(before["snapshots"]) == 1 and len(before["sales"]) >= 5, "a good snapshot and its sales are stored first")
    newer = card(sales=default_sales() + [raw_sale("s-late", "2026-10-10", 150)], ladder=300.0, estimate=200.0)
    for failing, answer in (("httpcardestimate", (500, FAIL_BODY)), ("httpprofile", (500, FAIL_BODY)),
                            ("httpcertlookup", (500, FAIL_BODY)), ("httpcardestimate", (429, LIMIT_BODY))):
        w.load(newer)
        w.fail = {failing: answer}
        exc = refused(routes.do_slab_add, {"cert": CERT, "grader": "psa"})
        refusal(f"{failing} answers {answer[0]} after the others read a newer card", exc)
        same("today's good snapshot, the slab and the sales are exactly as they were", dump(), before)


def case_pacing(routes):
    """6. pacing, the rate-limit latch and a replaced token hold across requests"""
    w = new_world(routes)
    w.load(card())
    w.load(card(cert=CERT2))
    add(routes, CERT)
    add(routes, CERT2)
    ok(len(w.calls) == 6 and all(g >= cardladder.PACE_SECONDS for g in gaps(w.calls)),
       "two adds in a row keep every callable send 8 seconds apart: one client for the process", str(gaps(w.calls)))

    base = dump()
    lim = new_world(routes)
    lim.load(card(cert=CERT3))
    lim.fail["httpprofile"] = (429, LIMIT_BODY)
    refusal("the first add is limited", refused(routes.do_slab_add, {"cert": CERT3, "grader": "psa"}),
            "cardladder_rate_limited")
    sent = len(lim.log)
    lim.fail.clear()
    text = refusal("a second add the same day, though Card Ladder would now answer",
                   refused(routes.do_slab_add, {"cert": CERT3, "grader": "psa"}), "cardladder_rate_limited")
    ok("tomorrow" in text.lower(), "it still says to try tomorrow", text)
    same("and it sent nothing at all", len(lim.log), sent)
    same("and wrote nothing", dump(), base)
    lim.day = DAY2
    receipt = add(routes, CERT3)
    same("the next day an add goes through", (receipt.get("added"), receipt.get("day")), (True, DAY2))

    with fresh_home():  # a store of its own: the limit above is kept in the store for its day
        tok = new_world(routes)
        tok.load(card())
        tok.accepted = {RT_NEW}  # the owner copied a fresh token, but .env still holds the old one
        refusal("the old token is refused", refused(routes.do_slab_add, {"cert": CERT, "grader": "psa"}),
                "cardladder_token_rejected")
        os.environ[KEY] = RT_NEW
        exc = refused(add, routes)
        ok(exc is None, "after the token is replaced the next add works, with no restart", repr(exc))


def case_money_and_dates(routes):
    """7. Card Ladder's numbers become text money and every sale date becomes one ISO shape"""
    w = new_world(routes)
    w.load(card())
    add(routes)
    s = slabs_now()
    snap = s.snapshots_for(CERT, "psa")[0]
    ok(all(isinstance(v, str) for v in (snap.cl_value, snap.estimated_value, snap.last_sale_price)),
       "the snapshot's money is text", repr((snap.cl_value, snap.estimated_value, snap.last_sale_price)))
    ok(type(snap.cl_confidence) is int and type(snap.estimated_confidence) is int and type(snap.population) is int,
       "confidence and population stay whole numbers")
    same("a speed window's average price is text money, its velocity as given", snap.speed, SPEED_WANT)

    rows = {x.id: x for x in s.sales_for(CERT, "psa")}
    same("a sale's price is text money, whatever number Card Ladder sent",
         {sid: rows[sid].data.get("price") for sid in AT_GRADE if sid in rows}, WANT_PRICE)
    dates = {sid: rows[sid].date for sid in AT_GRADE if sid in rows}
    ok(all(isinstance(d, str) and d[:10] == WANT_DAY[sid] for sid, d in dates.items()),
       "an ISO date, an ISO time, epoch seconds, epoch milliseconds and a seconds object all land on the right day",
       repr(dates))
    ok(len({date_shape(d) for d in dates.values()} | {date_shape(snap.last_sale_date)}) == 1,
       "and every stored date has one shape, the last sale's included", repr(dates))
    ok(sorted(dates.values()) == [dates[sid] for sid in reversed(AT_GRADE)],
       "so the strings sort in time order", repr(dates))
    ok(all(rows[sid].data.get("date") == rows[sid].date for sid in dates), "and the stored sale's own date agrees")

    none = new_world(routes)
    none.load(card(cert=CERT2, ladder=None, estimate=None, confidence=None))
    add(routes, CERT2)
    row = slabs_now().snapshots_for(CERT2, "psa")[0]
    same("a value Card Ladder did not give stays None, never 0.00",
         (row.cl_value, row.estimated_value, row.estimated_confidence), (None, None, None))


def case_sale_merge(routes):
    """8. a re-read sale is merged into the stored one before it is written"""
    w = new_world(routes)
    w.load(card())
    add(routes)
    stored = {x.id: x for x in slabs_now().sales_for(CERT, "psa")}["s-new"]
    old = dict(stored.data, title="OLD TITLE", price="1.00", slabSerial="12345678", feedback="99.8% positive")
    with store().write() as snap:
        snap.slabs.record_sales(CERT, "psa", [old])
    w.day = DAY2
    w.load(card(sales=[s for s in default_sales() if s["id"] != "s-old"]))  # Card Ladder dropped s-old
    add(routes)
    rows = {x.id: x for x in slabs_now().sales_for(CERT, "psa")}
    data = rows["s-new"].data
    same("fields only 3.3 gave are kept", (data.get("slabSerial"), data.get("feedback")), ("12345678", "99.8% positive"))
    same("and the fields 3.2 gave are updated, as text money",
         (data.get("title"), data.get("price")), ("Charizard ex 125 s-new", "116.40"))
    ok("s-old" in rows, "a sale Card Ladder dropped stays", str(sorted(rows)))
    same("no sale is stored twice", len(rows), len(set(rows)))


def case_two_slabs(routes):
    """9. two slabs of one card share their sales"""
    w = new_world(routes)
    w.load(card())
    w.load(card(cert=CERT2))
    add(routes, CERT)
    one = count(slabs_now().sales)
    add(routes, CERT2)
    s = slabs_now()
    same("the second slab adds no second copy of a sale", count(s.sales), one)
    for cert in (CERT, CERT2):
        same(f"slab {cert} lists the shared sales", [x["id"] for x in routes.do_slab("psa", cert)["sales"]], list(AT_GRADE))


def case_list(routes):
    """10. list: every slab with its newest snapshot; a slab with no sale at its grade says no sales"""
    w = new_world(routes)
    w.load(card())
    add(routes)
    w.day = DAY2
    w.load(card(estimate=130.0, confidence=3))
    add(routes)
    # No sale at this slab's grade, but Card Ladder still sends a number for its estimate and its ladder.
    w.load(card(cert=CERT3, profile_id="psa-nosale", sales=[raw_sale("s-9", "2026-10-05", 20, "psa", "g9")],
                ladder=60.25, estimate=55.5))
    add(routes, CERT3)
    answer = routes.do_slabs()
    POOL.append(json.dumps(answer, default=str))
    rows = {r["cert"]: r for r in answer.get("slabs", [])}
    same("every slab is listed", sorted(rows), sorted([CERT, CERT3]))
    a = rows.get(CERT, {})
    same("a row names the slab, its grade and the day it was added",
         {k: a.get(k) for k in ("grader", "label", "grade", "added")},
         {"grader": "psa", "label": LABEL, "grade": "g10", "added": DAY1})
    snap = a.get("snapshot") or {}
    same("it carries the newest snapshot", (snap.get("day"), snap.get("estimated_value"), snap.get("estimated_confidence")),
         (DAY2, "130.00", 3))
    same("a slab with sales has no note", a.get("note"), None)
    b = rows.get(CERT3, {})
    snap = b.get("snapshot") or {}
    same("a slab with no sale at its grade carries no value, whatever Card Ladder sent",
         {k: snap.get(k, "missing") for k in ("cl_value", "estimated_value", "last_sale_price", "last_sale_date")},
         {"cl_value": None, "estimated_value": None, "last_sale_price": None, "last_sale_date": None})
    same("and says no sales", b.get("note"), "no sales")
    stored = slabs_now().snapshots_for(CERT3, "psa")[0]
    same("the store holds no value for it either", (stored.cl_value, stored.estimated_value, stored.last_sale_price),
         (None, None, None))
    same("the detail says no sales too", routes.do_slab("psa", CERT3).get("note"), "no sales")


def case_detail(routes):
    """11. detail: one slab, its snapshots oldest first, its sales newest first and its grade ladder"""
    w = new_world(routes)
    w.load(card())
    add(routes)
    w.day = DAY2
    w.load(card(ladder=250.0, estimate=130.0, confidence=3))
    add(routes)
    detail = routes.do_slab("PSA", CERT)
    POOL.append(json.dumps(detail, default=str))
    same("the slab", {k: detail.get("slab", {}).get(k) for k in ("cert", "grader", "label", "grade", "added")},
         {"cert": CERT, "grader": "psa", "label": LABEL, "grade": "g10", "added": DAY1})
    snaps = detail.get("snapshots", [])
    same("snapshots run oldest day first", [x.get("day") for x in snaps], [DAY1, DAY2])
    same("each is that day's own read", [x.get("estimated_value") for x in snaps], ["123.45", "130.00"])
    sales = detail.get("sales", [])
    same("sales run newest first, at the slab's grader and grade only", [x.get("id") for x in sales], list(AT_GRADE))
    ok(all(isinstance(x.get("date"), str) and x["date"][:10] == WANT_DAY[x["id"]] for x in sales),
       "each with its day", repr([x.get("date") for x in sales]))
    same("each with text money and its listing", [(x.get("price"), x.get("url")) for x in sales],
         [(WANT_PRICE[sid], "https://sale.invalid/" + sid) for sid in AT_GRADE])
    ladder = [{k: row.get(k) for k in ("grade", "label", "cl_value", "cl_confidence")} for row in detail.get("ladder", [])]
    same("the grade ladder is the newest read's, in Card Ladder's order, as text money", ladder, [
        {"grade": "g10", "label": "PSA 10", "cl_value": "250.00", "cl_confidence": 5},
        {"grade": "g9", "label": "PSA 9", "cl_value": "44.00", "cl_confidence": 3}])
    same("a slab with sales has no note", detail.get("note"), None)
    exc = refused(routes.do_slab, "psa", "00000000")
    refusal("a slab nobody added", exc, "slab_unknown", 404)
    refusal("a grader nobody has", refused(routes.do_slab, "pokemon", CERT), "grader_unknown", 400)
    zero = new_world(routes)
    zero.load(card(cert="0012345678", grader="beckett", grade="g9_5", profile_id="beckett-77",
                   sales=default_sales("beckett", "g9_5")))
    add(routes, "0012345678", "beckett")
    same("any form of the grader finds the slab", routes.do_slab("BGS", "0012345678").get("slab", {}).get("cert"), "0012345678")


def case_http(routes):
    """12. the routes are dispatched: GET /slabs, GET /slabs/<grader>/<cert>, POST /slabs, and nothing for a sweep"""
    from harness.tests.t7.common import QuietHandler, _spawn_server, request
    from server import capture_server

    os.environ.pop(KEY, None)
    capture_server.captures_root().mkdir(parents=True, exist_ok=True)
    httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
    port = httpd.server_address[1]
    _spawn_server(httpd)
    try:
        ok(port != 8000, "the throwaway server is not on the owner's port", str(port))

        def ask(method, path, payload=None):
            status, body, _ = request(port, method, path, payload=payload)
            try:
                return status, json.loads(body or b"{}")
            except ValueError:
                return status, {}

        status, body = ask("GET", "/slabs")
        same("GET /slabs on an empty store", (status, body), (200, {"slabs": []}))
        status, body = ask("GET", "/slabs/psa/999")
        same("GET /slabs/psa/999 for a slab nobody added", (status, (body.get("error") or {}).get("code")), (404, "slab_unknown"))
        status, body = ask("POST", "/slabs", {"cert": CERT, "grader": "pokemon"})
        same("POST /slabs with an unknown grader", (status, (body.get("error") or {}).get("code")), (400, "grader_unknown"))
        status, body = ask("POST", "/slabs", {"cert": CERT, "grader": "psa"})
        error = body.get("error") or {}
        same("POST /slabs with no token in the settings file", (status >= 400, error.get("code")),
             (True, "cardladder_token_missing"))
        ok(KEY in str(error.get("message")), "and the sentence names the key", str(error.get("message")))
        for method in ("GET", "POST"):
            status, body = ask(method, "/slabs/sweep", {} if method == "POST" else None)
            same(f"{method} /slabs/sweep: the owner ruled no sweep route", (status, (body.get("error") or {}).get("code")),
                 (404, "no_such_route"))
    finally:
        httpd.shutdown()
        httpd.server_close()


def case_client():
    """13. app/src/server.ts has addSlab, getSlabs and getSlabDetail on the routes above"""
    try:
        from scripts.docs_audit.code_invariants import _ts_function_body
    except ImportError as exc:
        ok(False, "the docs-audit TypeScript reader loads", str(exc))
        return
    source = (ROOT / "app" / "src" / "server.ts").read_text(encoding="utf-8")
    for name, wants in (
        ("addSlab", (r"""["'`]/slabs["'`]""", r"""method:\s*["']POST["']""", r"JSON\.stringify", r"\bcert\b", r"\bgrader\b", r"\bSlabReceipt\b")),
        ("getSlabs", (r"""["'`]/slabs["'`]""", r"\bSlabList\b")),
        ("getSlabDetail", (r"/slabs/", r"encodeURIComponent.*encodeURIComponent", r"\bSlabDetail\b")),
    ):
        body = _ts_function_body(source, name)
        if not ok(body is not None, f"server.ts exports {name}"):
            continue
        ok(re.search(r"\brequest\(", body) is not None, f"{name} goes through request()")
        for want in wants:
            ok(re.search(want, body, re.S) is not None, f"{name} has {want}")


def case_no_job():
    """14. the owner ruled no launchd job: no slab script is a sweep, an agent or a schedule"""
    odd = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "scripts").rglob("*")
                 if "slab" in p.name.lower() and re.search(r"sweep|agent|launchd|plist|refresh|daily|cron", p.name, re.I))
    same("no slab sweep script, agent or plist", odd, [])


def case_overlap(routes):
    """15. two adds at once: the second is refused at once and sends and writes nothing; the next add works"""
    w = new_world(routes)
    for cert in (CERT, CERT2, CERT3):
        w.load(card(cert=cert))
    entered, release = threading.Event(), threading.Event()
    sent = []

    def held(method, url, headers, body):
        """The first callable send waits here: that add is in flight until `release`. Every other send goes on.
        It is a callable and not the sign-in, because the client holds its own lock through the sign-in, and
        a second add would then wait on that lock and send nothing, which proves nothing about the routes."""
        sent.append(url)
        if urllib.parse.urlsplit(url).hostname == CF_HOST and not entered.is_set():
            entered.set()
            release.wait(10)
        return w.transport(method, url, headers, body)

    routes.TRANSPORT = held
    results = {}

    def go(name, cert):
        try:
            results[name] = routes.do_slab_add({"cert": cert, "grader": "psa"})
        except Exception as exc:  # noqa: BLE001 - the case reports the type
            results[name] = exc

    threads = [threading.Thread(target=go, args=("first", CERT), daemon=True)]
    threads[0].start()
    try:
        if not ok(entered.wait(5), "the first add reaches Card Ladder and is held there"):
            return
        before, held_sends = dump(), len(sent)
        for name, cert in (("another slab", CERT2), ("the same slab", CERT)):
            thread = threading.Thread(target=go, args=(name, cert), daemon=True)
            threads.append(thread)
            thread.start()
            thread.join(2)
            if ok(not thread.is_alive(), f"a second add ({name}) is answered at once and not queued behind the first"):
                refusal(f"a second add ({name})", results.get(name), None, 409)
        same("the second adds sent no call to Card Ladder", len(sent), held_sends)
        same("and wrote nothing", dump(), before)
    finally:
        release.set()
        for thread in threads:
            thread.join(10)
    first = results.get("first")
    same("the first add finishes and is added",
         (first.get("added"), first.get("cert")) if isinstance(first, dict) else repr(first), (True, CERT))
    same("it wrote its one slab", [x.cert for x in slabs_now().list()], [CERT])

    routes.TRANSPORT = w.transport
    exc = refused(add, routes, CERT2)
    ok(exc is None, "after the first add is done, a new add works", repr(exc))
    same("and the store holds both slabs", sorted(x.cert for x in slabs_now().list()), sorted([CERT, CERT2]))

    w.fail["httpprofile"] = (500, FAIL_BODY)  # a failed add must free the way for the next, too
    refusal("an add Card Ladder fails", refused(routes.do_slab_add, {"cert": CERT3, "grader": "psa"}))
    w.fail.clear()
    exc = refused(add, routes, CERT3)
    ok(exc is None, "after a failed add, a new add works", repr(exc))


def case_no_sale_ladder(routes):
    """16. a slab with no sale at its grade has no value at its own grade in the ladder, and none in the list"""
    w = new_world(routes)
    w.load(card())
    # No sale at this slab's grade, but Card Ladder still sends a number for its ladder row and its estimate.
    w.load(card(cert=CERT3, profile_id="psa-nosale", sales=[raw_sale("s-9", "2026-10-05", 20, "psa", "g9")],
                ladder=60.25, estimate=55.5))
    add(routes, CERT)
    add(routes, CERT3)
    detail, listing = routes.do_slab("psa", CERT3), routes.do_slabs()
    POOL.append(json.dumps([detail, listing], default=str))
    rows = {row.get("grade"): row for row in detail.get("ladder", [])}
    own = rows.get("g10")
    ok(own is not None and own.get("label") == "PSA 10", "the ladder still has a row at the slab's own grade",
       repr(detail.get("ladder")))
    own = own or {}
    same("that row carries no value", own.get("cl_value"), None)
    same("and no estimate", {k: v for k, v in own.items() if "estimat" in k.lower() and v is not None}, {})
    other = rows.get("g9") or {}
    same("another grade's row keeps its value and confidence", (other.get("cl_value"), other.get("cl_confidence")),
         ("44.00", 3))
    listed = {x["cert"]: x for x in listing.get("slabs", [])}.get(CERT3, {})
    snap = listed.get("snapshot") or {}
    same("the list row carries no value either", {k: snap.get(k, "missing") for k in ("cl_value", "estimated_value")},
         {"cl_value": None, "estimated_value": None})
    for label, answer in (("detail", detail), ("list row", listed)):
        text = json.dumps(answer, default=str)
        ok("60.25" not in text and "55.50" not in text, f"the {label} holds neither number Card Ladder sent", text[:300])
    stored = slabs_now().snapshots_for(CERT3, "psa")[0].ladder or []
    same("the store holds no value at the slab's own grade either, whatever Card Ladder sent",
         [row.get("cl_value") for row in stored if row.get("grade") == "g10"], [None])
    with_sale = {row.get("grade"): row for row in routes.do_slab("psa", CERT).get("ladder", [])}.get("g10") or {}
    same("a slab with a sale keeps the value at its own grade", with_sale.get("cl_value"), "238.50")


def case_latch_restart(routes):
    """17. a rate limit stops adds for that day, also after the server restarts"""
    w = new_world(routes)
    w.load(card(cert=CERT3))
    w.fail["httpprofile"] = (429, LIMIT_BODY)
    refusal("the first add is limited", refused(routes.do_slab_add, {"cert": CERT3, "grader": "psa"}),
            "cardladder_rate_limited")
    base = dump()

    w = new_world(routes)  # a restart on the same day: a new process over the same store, and Card Ladder would now answer
    w.load(card(cert=CERT3))
    text = refusal("an add the same day after a restart", refused(routes.do_slab_add, {"cert": CERT3, "grader": "psa"}),
                   "cardladder_rate_limited", 429)
    ok("tomorrow" in text.lower(), "it says to try tomorrow", text)
    same("it sent nothing at all, not even a sign-in", w.log, [])
    same("and wrote nothing", dump(), base)

    w.day = DAY2
    receipt = refused(add, routes, CERT3)
    ok(receipt is None, "the next day an add goes through", repr(receipt))
    same("and it wrote the slab", [x.cert for x in slabs_now().list()], [CERT3])

    w = new_world(routes)  # another restart, on the new day: the old stop does not come back
    w.day = DAY2
    w.load(card(cert=CERT3))
    receipt = refused(add, routes, CERT3)
    ok(receipt is None, "a restart on the new day is not stopped by the old day's limit", repr(receipt))

    with fresh_home():  # the stop belongs to the store and not to the process
        w = new_world(routes)
        w.load(card(cert=CERT3))
        receipt = refused(add, routes, CERT3)
        ok(receipt is None, "a different store holds no stop", repr(receipt))


ROUTE_CASES = (
    case_seams, case_add, case_grader_forms, case_refusals, case_failed_read, case_pacing,
    case_money_and_dates, case_sale_merge, case_two_slabs, case_list, case_detail, case_http,
    case_overlap, case_no_sale_ladder, case_latch_restart,
)


# ------------------------------------------------------------------------------ the run


@contextmanager
def belt():
    """Nothing reaches the network (loopback is the throwaway server's) or sleeps for real."""
    real = (net.open, socket.socket.connect, time.sleep)

    def no_open(*_a, **_k):
        VIOLATIONS.append("pipeline.net.open: the routes must reach Card Ladder through the injected transport")
        raise AssertionError("pipeline.net.open")

    def guarded_connect(self, address, *a, **k):
        host = address[0] if isinstance(address, tuple) else address
        if host not in ("127.0.0.1", "::1", "localhost"):
            VIOLATIONS.append("socket connect to %s" % (host,))
            raise AssertionError("real socket")
        return real[1](self, address, *a, **k)

    def guarded_sleep(seconds):
        if seconds >= 1:
            VIOLATIONS.append("time.sleep(%s): use the injected sleep" % (seconds,))
            raise AssertionError("real time.sleep")
        return real[2](seconds)

    net.open, socket.socket.connect, time.sleep = no_open, guarded_connect, guarded_sleep
    try:
        yield
    finally:
        net.open, socket.socket.connect, time.sleep = real


class _Lines(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.lines: list = []
        self.setFormatter(logging.Formatter("%(name)s %(levelname)s %(message)s"))

    def emit(self, record) -> None:
        self.lines.append(self.format(record))


@contextmanager
def printed():
    """Everything the code prints or logs inside the block goes to POOL."""
    handler, root = _Lines(), logging.getLogger()
    old_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            yield
    finally:
        root.removeHandler(handler)
        root.setLevel(old_level)
        POOL.extend(handler.lines + [out.getvalue(), err.getvalue()])


def run(case, *args) -> None:
    print(f"-- {case.__doc__} --", file=OUT)
    try:
        with fresh_home(), printed():
            case(*args)
    except Exception:
        ok(False, f"{case.__name__} ran to the end", traceback.format_exc()[-900:])


def main() -> int:
    print("My Slabs routes self-test\n", file=OUT)
    saved_token = os.environ.pop(KEY, None)
    try:
        with belt():
            run(case_world_control)
            routes = load_routes()
            if routes is None:
                ok(False, "server/slabs_routes.py exists, with the routes and seams in this file's header")
            else:
                for case in ROUTE_CASES:
                    run(case, load_routes())
            run(case_client)
            run(case_no_job)
    finally:
        if saved_token is None:
            os.environ.pop(KEY, None)
        else:
            os.environ[KEY] = saved_token
    text = "\n".join(str(p) for p in POOL)
    ok(RT not in text and RT_NEW not in text and ID_MARK not in text,
       "the fake refresh tokens and ID tokens appear in no answer, refusal, log line or print (D320)")
    ok(not VIOLATIONS, "nothing touched the real network or slept for real", "\n".join(VIOLATIONS))
    print(f"\n{PASS} passed, {FAIL} failed", file=OUT)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
