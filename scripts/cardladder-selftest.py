#!/usr/bin/env python3
"""`pipeline/cardladder.py` stays inside the bounds the owner set for the Card Ladder login,
proved against a fake transport, or the real `pipeline/net.py` over a fake opener (for the default
transport), and a fake clock: no network, no real sleep, no `.env` read.

Protects: The Card Ladder client calls only the six read callables, never `search.cardladder.com`, waits 8 seconds between calls, stops at a rate limit, refreshes its ID token in time, and never prints a token.
Governs: D-my-slabs-card-ladder

BUILD PLAN STEP 1 (`docs/specs/my-slabs.md`). The interface of `pipeline/cardladder.py` that
this file tests:

    ALLOWED_CALLABLES        frozenset of exactly the six read callables of spec 3.1 to 3.6.
                             The one constant. `Client` reads it, it holds no copy.
    CardLadderError          base class of the three below, and of any other failure.
    Refused                  a callable off the list, or host search.cardladder.com.
                             Raised before ANY request is sent, the token exchange included.
    RateLimited              the "Too many requests" answer. Latches: every later call on the
                             same client raises it at once and sends nothing.
    TokenRejected            the token exchange failed. Its text names CARDLADDER_REFRESH_TOKEN.
    Client(*, refresh_token, transport=None, clock, sleep)
        transport(method, url, headers, body: bytes) -> (status: int, body: bytes)
        A Client given no transport sends through `net_transport`.
        clock() -> float seconds, sleep(seconds) -> None. Both injected, never `time`.
        .call(name, data) -> dict   POST https://us-central1-cardladder-71d53.cloudfunctions.net/<name>
                                    with JSON {"data": data} and Authorization: Bearer <id_token>.
                                    Returns the answer's "result".
        .send(method, url, headers, body) -> (status, body)
                                    The one send path. EVERY request goes through it, the token
                                    exchange included. It refuses the host before the transport.
        A Client may be shared by threads: callable sends stay 8 seconds apart across them.
        A transport may raise anything. Whatever it raises, that send still counts for the pace.
        A transport that RETURNS (429, body) is the rate limit: RateLimited, and the latch. The
        default transport returns a 429 as a status (`net.open` never raises one), so this is the
        only shape production sends. A transport that RAISES is a CardLadderError and no latch
        (a `pipeline.pricehistory` error, a bare HTTPError 403 or 500, an OSError). A raised 429
        is left open: production never raises one, and the cases pin neither outcome.
        The latch holds across threads: once one call is answered 429, no thread sends again,
        one already waiting for its turn in the pace included.
        `send` of a cloudfunctions URL whose callable is off the list raises Refused, sends
        nothing and does not stamp the pace.
    Read functions, one per point of spec section 3 (each takes the client first):
        cert_lookup(client, cert, grader)       httpcertlookup    {cert, grader, includeProfile: true}
        profile(client, profile_id)             httpprofile       {profileId}
        profile_sales(client, cert, grader, grade)
                                                httpprofilesales  {cert, grader, grade}
        card_estimate(client, profile_id, grader, grade, description, qualifier_type, autograph_grade)
                                                httpcardestimate  {profileId, grader, grade,
                                                                   description, qualifierType, autographGrade}
        sale_profile(client, sale_id)           httpsaleprofile   {saleId}
        index_from_description(client, description)
                                                httpIndexFromDescription  {description}
        A grader of bgs or bvg goes out as beckett. psa, sgc, cgc and beckett go out as given.
    net_transport(method, url, headers, body: bytes) -> (status: int, body: bytes)
                             The default transport, built on the one retry home (`pipeline/net.py`,
                             every network call retries through one method). It calls `net.open` AS A MODULE
                             ATTRIBUTE, looked up at each call (`from pipeline import net`, then
                             `net.open(...)`): the net cases swap that attribute for a spy, then run the
                             real `net.open` on its `opener`, `clock` and `sleep` seams. Every call
                             passes method=<the method>, data=<body>, headers=<headers>,
                             idempotent=False and follow_redirects=False, each as a keyword. It returns
                             the status and body of ANY HTTP answer, a 429 or a 5xx included, because
                             the Client reads the status itself. net.Offline and net.Dropped may leave
                             it: `Client.send` turns them into a CardLadderError.
        idempotent=False: a 429 or a 5xx answer is sent once and read as it came. Only a connect that
        never opened may be sent again (`net.open` decides, and the cases do not pin the count).
        A failure after the connect (a reset or a socket.timeout once the request is out, a reset
        while the answer is read) may have done the work, so it gets exactly ONE attempt: the
        transport never sends again on `net.Dropped`. The Client turns it into a CardLadderError, with
        no latch.
        follow_redirects=False: a 3xx is an answer, not followed, so no header or body goes to a
        second host.
        A Google 400, 401 or 403 on the token exchange is TokenRejected, and its text says to copy
        CARDLADDER_REFRESH_TOKEN again. Any other status is not about the token: a Google 429, a 5xx
        (500, 503) or a 3xx is a CardLadderError that names securetoken.googleapis.com, that is
        not TokenRejected or RateLimited, that does not say to copy the token again, and that does
        not latch the client.

Token exchange: POST https://securetoken.googleapis.com/v1/token?key=<public key>, the refresh
token in the BODY only (form or JSON, with grant_type=refresh_token). The answer is Google's:
{"id_token", "expires_in": "3600" (a string), "refresh_token", "user_id", ...}.

What this file leaves open, on purpose: the refresh margin (any margin that keeps the token
under its age limit), whether the token exchange counts toward the 8 seconds (this file
constrains only sends to the callable host), the public API key value, whether a RAISED 429
latches (production never raises one), and Firestore (3.7 is not a callable and is not covered).

This file parses on the bare system python3 (3.9).

The fake world refuses the real clock, the real socket and any open of a file named `.env`,
and removes CARDLADDER_REFRESH_TOKEN from the environment. A client that reaches for one fails
its case.
"""

from __future__ import annotations

import builtins
import contextlib
import email.message
import errno
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
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import net, pricehistory  # noqa: E402 - the retry home and its error classes

PASS = 0
FAIL = 0
VIOLATIONS: list = []

RT = "RTSENTINEL-9f3c1d7a-refresh"  # the fake refresh token
ID_MARK = "IDSENTINEL-4b2e8a60"  # every fake ID token holds this
KEY_NAME = "CARDLADDER_REFRESH_TOKEN"
CF_HOST = "us-central1-cardladder-71d53.cloudfunctions.net"
CF_BASE = "https://" + CF_HOST + "/"
GOOGLE_HOST = "securetoken.googleapis.com"
SIX = {
    "httpcertlookup", "httpprofile", "httpprofilesales",
    "httpcardestimate", "httpsaleprofile", "httpIndexFromDescription",
}
OUT_OF_BOUNDS = [  # spec 3.8
    "httpbuildcollectioncard", "httpSyncCardStats", "httpRefreshCert", "httpInitialSalesScrape",
]
LIMIT_TEXT = "Too many requests. Please wait a minute and try again."
ENVELOPE = json.dumps({"error": {"message": LIMIT_TEXT, "status": "RESOURCE_EXHAUSTED"}}).encode()


def ok(condition: bool, label: str, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ok     {label}")
    else:
        FAIL += 1
        print(f"  FAIL   {label}  {detail}")


def _fields(body: bytes) -> dict:
    """The token exchange body as a dict, whether the client sent a form or JSON."""
    text = body.decode("utf-8", "replace")
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return {k: str(v) for k, v in data.items()}
    except ValueError:
        pass
    return {k: v[0] for k, v in urllib.parse.parse_qs(text).items()}


class World:
    """A fake clock, a fake Google token endpoint and a fake Card Ladder, one per case.

    `answer(world, n, headers, body)` may return (status, bytes) for the n-th callable
    request, return None for the default 200, or raise. `exchange` is "ok", "reject"
    (400 that echoes the request body) or "raise" (the transport itself fails with the body
    in its message). `vtime` (a VirtualTime) replaces the plain clock when threads share it."""

    def __init__(self, *, expires_in: str = "3600", answer=None, exchange: str = "ok",
                 vtime=None) -> None:
        self.vtime = vtime
        self._now = 1_000_000.0
        self.slept = 0.0
        self.expires_in = expires_in
        self.answer = answer
        self.exchange_mode = exchange
        self.log: list = []  # every request the transport saw
        self.exchanges: list = []  # (issued_at, id_token)
        self.calls: list = []  # (t, name, token, age) per callable request
        self.card_ladder_sends = 0

    @property
    def now(self) -> float:
        return self.vtime.now if self.vtime else self._now

    @now.setter
    def now(self, value: float) -> None:
        self._now = value

    def clock(self) -> float:
        return self.vtime.clock() if self.vtime else self.now

    def sleep(self, seconds: float) -> None:
        self.slept += seconds
        if self.vtime:
            self.vtime.sleep(seconds)
        else:
            self.now += seconds

    def client(self, cardladder):
        return cardladder.Client(
            refresh_token=RT, transport=self.transport, clock=self.clock, sleep=self.sleep)

    def callable_requests(self) -> list:
        return [r for r in self.log if r.host == CF_HOST]

    def transport(self, method, url, headers, body):
        parts = urllib.parse.urlsplit(url)
        req = SimpleNamespace(
            t=self.now, method=method, url=url, host=parts.hostname, path=parts.path,
            query=urllib.parse.parse_qs(parts.query),
            headers={k.lower(): v for k, v in headers.items()}, body=body)
        self.log.append(req)
        if req.host == GOOGLE_HOST:
            return self._exchange(req)
        if req.host == CF_HOST:
            return self._callable(req)
        raise OSError("the fake world has no host " + str(req.host))

    def _exchange(self, req):
        if self.exchange_mode == "raise":
            raise OSError("connection reset while sending %r" % (req.body,))
        f = _fields(req.body)
        if self.exchange_mode == "reject" or f.get("refresh_token") != RT \
                or f.get("grant_type") != "refresh_token":
            return 400, req.body  # a worst case: the answer echoes the request
        token = "ID-%d-%s" % (len(self.exchanges) + 1, ID_MARK)
        self.exchanges.append((self.now, token))
        return 200, json.dumps({
            "access_token": token, "id_token": token, "refresh_token": RT,
            "expires_in": self.expires_in, "token_type": "Bearer", "user_id": "UID-TEST",
        }).encode()

    def _callable(self, req):
        n = len(self.callable_requests())
        auth = req.headers.get("authorization", "")
        match = [(t, tok) for t, tok in self.exchanges if auth == "Bearer " + tok]
        if not match:
            return 401, json.dumps({"error": {"message": "unauthenticated " + auth}}).encode()
        issued, token = match[0]
        age = self.now - issued
        name = req.path.rsplit("/", 1)[-1]
        self.calls.append(SimpleNamespace(t=self.now, name=name, token=token, age=age))
        if age >= float(self.expires_in):
            return 401, json.dumps({"error": {"message": "token expired " + auth}}).encode()
        if self.answer is not None:
            reply = self.answer(self, n, req.headers, req.body)
            if reply is not None:
                return reply
        data = json.loads(req.body)["data"]
        return 200, json.dumps({"result": {"echo": name, "data": data}}).encode()


class VirtualTime:
    """A clock for threads. Time moves only when no thread has done anything for QUIET real
    seconds, and then it jumps to the earliest deadline of a thread parked in `sleep`. A thread
    that waits on a lock is not parked, so a client that serialises its sends moves on one
    sleeper at a time, and one that does not lets every thread read the same stale time and
    wake together. Real waits here are Event and Condition timeouts, never `time.sleep`."""

    QUIET = 0.05

    def __init__(self, start: float) -> None:
        self.now = start
        self._cv = threading.Condition()
        self._deadlines: dict = {}
        self._activity = 0

    def clock(self) -> float:
        with self._cv:
            self._activity += 1
            return self.now

    def sleep(self, seconds: float) -> None:
        me = threading.get_ident()
        with self._cv:
            self._activity += 1
            self._deadlines[me] = self.now + seconds
            self._cv.notify_all()
            while self.now < self._deadlines[me]:
                if not self._cv.wait(timeout=20):  # the driver is gone: never hang the suite
                    break
            del self._deadlines[me]
            self._activity += 1

    def run(self, threads: list) -> None:
        """Drive the clock until every thread has ended (or 10 real seconds have passed)."""
        gate = threading.Event()
        for _ in range(200):
            if not any(t.is_alive() for t in threads):
                return
            with self._cv:
                seen = self._activity
            gate.wait(self.QUIET)
            with self._cv:
                if self._activity == seen and self._deadlines:
                    self.now = max(self.now, min(self._deadlines.values()))
                    self._cv.notify_all()


def _limited_on(n: int, status: int, body: bytes):
    def answer(_world, k, _headers, _body):
        return (status, body) if k == n else None
    return answer


@contextlib.contextmanager
def offline():
    """No real clock, socket or `.env` for the length of one case. A touch is recorded in
    VIOLATIONS, so a client that swallows the raised error still fails its case."""
    real = (time.sleep, socket.socket.connect, builtins.open, io.open)
    saved_token = os.environ.pop(KEY_NAME, None)

    def no_sleep(*_a, **_k):
        VIOLATIONS.append("time.sleep: use the injected sleep")
        raise AssertionError("real time.sleep")

    def no_connect(*_a, **_k):
        VIOLATIONS.append("socket connect: the test is offline")
        raise AssertionError("real socket")

    def guarded_open(file, *a, **k):
        if isinstance(file, (str, bytes, os.PathLike)) and os.path.basename(os.fsdecode(file)) == ".env":
            VIOLATIONS.append("read of .env")
            raise AssertionError("read of .env")
        return real[2](file, *a, **k)

    time.sleep, socket.socket.connect = no_sleep, no_connect
    builtins.open = io.open = guarded_open
    try:
        yield
    finally:
        time.sleep, socket.socket.connect, builtins.open, io.open = real
        if saved_token is not None:
            os.environ[KEY_NAME] = saved_token


class _Lines(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.lines: list = []
        self.setFormatter(logging.Formatter("%(name)s %(levelname)s %(message)s"))

    def emit(self, record) -> None:
        self.lines.append(self.format(record))  # format() adds exc_info text


@contextlib.contextmanager
def printed():
    """Everything the code prints or logs inside the block, at DEBUG, as one string."""
    handler, root = _Lines(), logging.getLogger()
    old_level, old_disable = root.level, logging.root.manager.disable
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    logging.disable(logging.NOTSET)
    out, err = io.StringIO(), io.StringIO()
    box = SimpleNamespace(text="")
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            yield box
    finally:
        root.removeHandler(handler)
        root.setLevel(old_level)
        logging.disable(old_disable)
        box.text = "\n".join(handler.lines) + out.getvalue() + err.getvalue()


def _trace(exc: BaseException) -> str:
    """The text a traceback prints, `__cause__` and `__context__` chain included."""
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


def _leaks(text: str) -> list:
    return [name for name, mark in (("refresh token", "RTSENTINEL"), ("ID token", ID_MARK))
            if mark in text]


def _outcome(fn, *args):
    """What `fn(*args)` returns, or the CardLadderError-or-other exception it raises."""
    try:
        return fn(*args)
    except Exception as exc:  # noqa: BLE001 - the case inspects it
        return exc


def _raises(cls, fn, *args):
    """The exception `fn(*args)` raises, or None. Arguments are passed, not closed over."""
    try:
        fn(*args)
    except cls as exc:
        return exc
    except Exception as exc:  # noqa: BLE001 - the case reports the wrong type
        return exc
    return None


# 1 -------------------------------------------------------------------------------------
def case_allow_list(cl) -> None:
    allowed = cl.ALLOWED_CALLABLES
    ok(set(allowed) == SIX, "the allow list holds exactly the six read callables of 3.1 to 3.6",
       "got %s" % sorted(allowed))
    ok(not (set(allowed) & set(OUT_OF_BOUNDS)), "no callable of 3.8 is on the list")
    ok(isinstance(allowed, (frozenset, tuple)), "the constant cannot be mutated in place",
       type(allowed).__name__)

    # the client reads the constant: take one callable out and it is refused; put an
    # invented one in and it goes through.
    real = cl.ALLOWED_CALLABLES
    try:
        cl.ALLOWED_CALLABLES = frozenset(SIX - {"httpprofile"})
        w = World()
        err = _raises(cl.Refused, lambda: w.client(cl).call("httpprofile", {}))
        ok(isinstance(err, cl.Refused) and not w.log,
           "a callable taken off the constant is refused with nothing sent",
           "%r, %d sent" % (err, len(w.log)))
        cl.ALLOWED_CALLABLES = frozenset(SIX | {"httpinvented"})
        w = World()
        answer = w.client(cl).call("httpinvented", {"k": 1})
        ok(answer == {"echo": "httpinvented", "data": {"k": 1}},
           "a callable put on the constant is sent: the client holds no copy", repr(answer))
    finally:
        cl.ALLOWED_CALLABLES = real

    w = World()
    client = w.client(cl)
    shapes_ok = True
    for name in sorted(SIX):
        before = len(w.callable_requests())
        got = client.call(name, {"k": name})
        req = w.callable_requests()[before:]
        good = (len(req) == 1 and req[0].method == "POST" and req[0].url == CF_BASE + name
                and json.loads(req[0].body) == {"data": {"k": name}}
                and req[0].headers.get("authorization") == "Bearer " + w.exchanges[-1][1]
                and "json" in req[0].headers.get("content-type", "").lower()
                and got == {"echo": name, "data": {"k": name}})
        shapes_ok = shapes_ok and good
        if not good:
            print("         bad request or answer for", name)
    ok(shapes_ok, "each of the six is one POST of {\"data\": ...} with a Bearer ID token, and returns its result")


# 2 -------------------------------------------------------------------------------------
def case_refuse_callable(cl) -> None:
    w = World()
    client = w.client(cl)
    names = OUT_OF_BOUNDS + [
        "httpnotreal", "", "HTTPPROFILE", "httpprofile ", "httpprofile/../httpbuildcollectioncard",
        "https://example.test/httpprofile",
    ]
    wrong = []
    for name in names:
        err = _raises(cl.Refused, client.call, name, {"cert": "1"})
        if not isinstance(err, cl.Refused):
            wrong.append((name, err))
    ok(not wrong, "a callable off the list raises Refused", "got %r" % wrong)
    ok(not w.log, "nothing is sent for them, the token exchange included", "%d sent" % len(w.log))


# 3 -------------------------------------------------------------------------------------
def case_refuse_host(cl) -> None:
    urls = [
        "https://search.cardladder.com/anything",
        "https://SEARCH.CardLadder.com/x?q=1",
        "https://search.cardladder.com:443/x",
    ]
    for primed in (False, True):
        w = World()
        client = w.client(cl)
        if primed:
            client.call("httpprofile", {})
        before = len(w.log)
        headers = {"Authorization": "Bearer ID-0-" + ID_MARK}
        errs = [_raises(cl.Refused, client.send, "POST", u, headers, b"{}") for u in urls]
        ok(all(isinstance(e, cl.Refused) for e in errs),
           "search.cardladder.com raises Refused (%s client)" % ("warm" if primed else "cold"),
           "got %r" % errs)
        ok(len(w.log) == before and not any(r.host == "search.cardladder.com" for r in w.log),
           "no request to it reaches the transport (%s client)" % ("warm" if primed else "cold"),
           "%d sent" % (len(w.log) - before))


# 4 -------------------------------------------------------------------------------------
def _gaps(world) -> list:
    times = [r.t for r in world.callable_requests()]
    return [b - a for a, b in zip(times, times[1:])]


def case_spacing(cl) -> None:
    w = World()
    client = w.client(cl)
    for i in range(6):
        client.call("httpprofile", {"i": i})
    gaps = _gaps(w)
    ok(len(gaps) == 5 and min(gaps) >= 8.0 - 1e-6, "back-to-back calls are 8 seconds or more apart",
       "gaps %s" % gaps)

    # a call that failed still counts as a send
    w = World(answer=lambda _w, n, _h, _b: (500, b"{}") if n == 1 else None)
    client = w.client(cl)
    _raises(cl.CardLadderError, client.call, "httpprofile", {})
    client.call("httpprofile", {})
    gaps = _gaps(w)
    ok(len(gaps) == 1 and gaps[0] >= 8.0 - 1e-6, "the call after a failed call is 8 seconds or more later",
       "gaps %s" % gaps)


# 5 -------------------------------------------------------------------------------------
def case_rate_limit(cl) -> None:
    shapes = [
        ("429 with the callable error envelope", 429, ENVELOPE),
        ("429 with an empty body", 429, b""),
        ("403 with the same envelope", 403, ENVELOPE),
    ]
    for label, status, body in shapes:
        w = World(answer=_limited_on(2, status, body))
        client = w.client(cl)
        client.call("httpprofile", {})
        err = _raises(cl.RateLimited, client.call, "httpprofile", {})
        ok(isinstance(err, cl.RateLimited), "%s raises RateLimited" % label, repr(err))
        ok(len(w.callable_requests()) == 2, "%s: the limited call is sent once, no retry" % label,
           "%d sent" % len(w.callable_requests()))
        sent_calls = w.callable_requests()
        limited_at = sent_calls[min(1, len(sent_calls) - 1)].t  # the limited call is the second
        ok(w.now == limited_at, "%s: the client does not wait and try again" % label,
           "clock moved %.1fs after the limited call" % (w.now - limited_at))
        sent, exchanges = len(w.log), len(w.exchanges)
        w.now += 120.0  # "wait a minute", twice over
        later = [_raises(cl.RateLimited, client.call, n, {})
                 for n in ("httpprofile", "httpcardestimate")]
        ok(all(isinstance(e, cl.RateLimited) for e in later) and len(w.log) == sent
           and len(w.exchanges) == exchanges,
           "%s: the stop holds, so a later call raises and sends nothing" % label,
           "%r, %d new requests" % (later, len(w.log) - sent))


# 6 -------------------------------------------------------------------------------------
def case_token(cl) -> None:
    w = World()
    client = w.client(cl)
    client.call("httpprofile", {})
    ex = [r for r in w.log if r.host == GOOGLE_HOST]
    f = _fields(ex[0].body) if ex else {}
    ok(len(ex) == 1 and ex[0].method == "POST" and ex[0].path == "/v1/token",
       "the token exchange is one POST to securetoken.googleapis.com/v1/token",
       "%d to Google" % len(ex))
    ok(f.get("grant_type") == "refresh_token" and f.get("refresh_token") == RT,
       "the refresh token goes in the body with grant_type=refresh_token", repr(sorted(f)))
    ok(ex and ex[0].query.get("key", [""])[0] != "", "the exchange carries a public API key in the URL")
    ok(ex and RT not in ex[0].url and not any(RT in v for v in ex[0].headers.values()),
       "the refresh token is not in the exchange URL or headers")
    ok(not any(RT in r.url or RT.encode() in r.body or any(RT in v for v in r.headers.values())
               for r in w.callable_requests()),
       "the refresh token never reaches Card Ladder")

    for expires_in, early, late in (("3600", 720.0, 3590.0), ("600", 120.0, 595.0)):
        w = World(expires_in=expires_in)
        client = w.client(cl)
        start = w.now
        client.call("httpprofile", {})
        client.call("httpprofile", {})
        ok(len(w.exchanges) == 1, "expires_in %s: a second call reuses the ID token" % expires_in,
           "%d exchanges" % len(w.exchanges))
        w.now = start + early
        client.call("httpprofile", {})
        ok(len(w.exchanges) == 1, "expires_in %s: still reused at %.0fs" % (expires_in, early),
           "%d exchanges" % len(w.exchanges))
        w.now = start + late
        client.call("httpprofile", {})
        ok(len(w.exchanges) == 2 and w.calls[-1].token == w.exchanges[1][1],
           "expires_in %s: the ID token is refreshed before it runs out (at %.0fs)" % (expires_in, late),
           "%d exchanges, sent token age %.0fs" % (len(w.exchanges), w.calls[-1].age))
        ok(all(c.age < float(expires_in) for c in w.calls),
           "expires_in %s: no call carries a token past its age" % expires_in)

    # a sweep of an hour and more: every send within the token's life, and few exchanges
    w = World()
    client = w.client(cl)
    for _ in range(540):  # 540 calls, 8 seconds apart: 72 minutes
        client.call("httpprofile", {})
    ok(all(c.age < 3600.0 for c in w.calls), "a 72 minute sweep never sends an expired ID token",
       "oldest %.0fs" % max(c.age for c in w.calls))
    ok(2 <= len(w.exchanges) <= 4, "a 72 minute sweep exchanges two to four times, not once per call",
       "%d exchanges" % len(w.exchanges))
    ok(min(_gaps(w)) >= 8.0 - 1e-6, "the whole sweep stays 8 seconds apart, refreshes included")


# 7 -------------------------------------------------------------------------------------
def case_no_token_in_text(cl) -> None:
    def check(label, exc, logged="", want_cls=None, want_key=False):
        if want_cls is not None:
            ok(isinstance(exc, want_cls), label + ": raises " + want_cls.__name__, repr(exc))
        if not isinstance(exc, BaseException):
            return
        text = str(exc) + "\n" + _trace(exc) + "\n" + logged
        ok(not _leaks(text), label + ": exception, traceback and log lines hold no token",
           "leaks the " + " and ".join(_leaks(text)))
        if want_key:
            ok(KEY_NAME in str(exc), label + ": the text names " + KEY_NAME)

    for mode, label in (("reject", "exchange refused, answer echoes the request"),
                        ("raise", "exchange transport fails with the request in its text")):
        w = World(exchange=mode)
        with printed() as log:
            err = _raises(cl.CardLadderError, w.client(cl).call, "httpprofile", {})
        want = cl.TokenRejected if mode == "reject" else cl.CardLadderError
        check(label, err, log.text, want, want_key=(mode == "reject"))

    def echo(status):
        return lambda _w, n, headers, _b: (status, json.dumps(
            {"error": {"message": "bad request " + headers.get("authorization", "")}}).encode())

    def boom(_w, n, headers, body):
        raise OSError("socket broke sending %r %r" % (headers, body))

    for label, answer, want in (
            ("callable answers 401 and echoes the Authorization header", echo(401), cl.CardLadderError),
            ("callable answers the rate limit and echoes it", lambda *a: (
                429, json.dumps({"error": {"message": LIMIT_TEXT + " " + a[2]["authorization"]}}).encode()),
             cl.RateLimited),
            ("callable transport fails with the headers in its text", boom, cl.CardLadderError)):
        w = World(answer=answer)
        with printed() as log:
            err = _raises(cl.CardLadderError, w.client(cl).call, "httpprofile", {})
        check(label, err, log.text, want)

    w = World()
    client = w.client(cl)
    client.call("httpprofile", {})
    with printed() as log:
        err = _raises(cl.Refused, client.call, "httpbuildcollectioncard", {"x": RT})
    check("a refused callable", err, log.text, cl.Refused)
    with printed() as log:
        err = _raises(cl.Refused, lambda: client.send(
            "POST", "https://search.cardladder.com/x",
            {"Authorization": "Bearer " + w.exchanges[0][1]}, ("refresh_token=" + RT).encode()))
    check("a refused host", err, log.text, cl.Refused)

    w = World()
    with printed() as log:
        client = w.client(cl)
        for name in sorted(SIX):
            client.call(name, {"cert": "123"})
        shown = repr(client) + str(client)
    ok(not _leaks(log.text + shown), "a clean run prints, logs and repr()s no token",
       "leaks the " + " and ".join(_leaks(log.text + shown)))


# 8 -------------------------------------------------------------------------------------
def case_read_functions(cl) -> None:
    graders = [("psa", "psa"), ("beckett", "beckett"), ("bgs", "beckett"), ("bvg", "beckett"),
               ("sgc", "sgc"), ("cgc", "cgc")]
    w = World()
    client = w.client(cl)

    def sent(fn, *args):
        """(callable name, data, answer) of the one request `fn(client, *args)` sends."""
        before = len(w.callable_requests())
        got = fn(client, *args)
        req = w.callable_requests()[before:]
        if len(req) != 1:
            return None, None, got
        return req[0].path.rsplit("/", 1)[-1], json.loads(req[0].body)["data"], got

    def check(label, fn, args, name, data):
        got_name, got_data, got = sent(fn, *args)
        ok(got_name == name and got_data == data and type(got_data) is dict
           and got == {"echo": name, "data": data},
           label, "sent %s %r, wanted %s %r" % (got_name, got_data, name, data))

    for given, sent_as in graders:
        check("cert_lookup(%s) sends httpcertlookup with %s" % (given, sent_as), cl.cert_lookup,
              ("12345", given), "httpcertlookup",
              {"cert": "12345", "grader": sent_as, "includeProfile": True})
        check("profile_sales(%s) sends httpprofilesales with %s" % (given, sent_as), cl.profile_sales,
              ("12345", given, "g10"), "httpprofilesales",
              {"cert": "12345", "grader": sent_as, "grade": "g10"})
        check("card_estimate(%s) sends httpcardestimate with %s" % (given, sent_as), cl.card_estimate,
              ("psa-9f", given, "g9_5", "2020 Thing Holo", "QUAL", "AUTO"), "httpcardestimate",
              {"profileId": "psa-9f", "grader": sent_as, "grade": "g9_5",
               "description": "2020 Thing Holo", "qualifierType": "QUAL", "autographGrade": "AUTO"})
    check("profile sends httpprofile with profileId", cl.profile, ("psa-9f",),
          "httpprofile", {"profileId": "psa-9f"})
    check("sale_profile sends httpsaleprofile with saleId", cl.sale_profile, ("sale-77",),
          "httpsaleprofile", {"saleId": "sale-77"})
    check("index_from_description sends httpIndexFromDescription with description",
          cl.index_from_description, ("2020 Thing Holo",),
          "httpIndexFromDescription", {"description": "2020 Thing Holo"})
    body = w.callable_requests()[0].body
    ok(json.loads(body)["data"].get("includeProfile") is True, "includeProfile is the JSON true, not 1")


# 9 -------------------------------------------------------------------------------------
def case_threads_keep_the_pace(cl) -> None:
    vt = VirtualTime(1_000_000.0)
    w = World(vtime=vt)
    client = w.client(cl)
    client.call("httpprofile", {"warm": True})  # the exchange and the first send, no waiting
    errors: list = []

    def work(i):
        try:
            client.call("httpprofile", {"i": i})
        except BaseException as exc:  # noqa: BLE001 - reported below
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(i,), daemon=True) for i in range(3)]
    for t in threads:
        t.start()
    vt.run(threads)
    for t in threads:
        t.join(5)
    times = sorted(r.t for r in w.callable_requests())
    gaps = [b - a for a, b in zip(times, times[1:])]
    ok(not errors and len(times) == 4, "three threads sharing one Client all get their call sent",
       "%d sent, errors %r" % (len(times), errors))
    ok(gaps and min(gaps) >= 8.0 - 1e-6, "no two sends from three threads are less than 8 seconds apart",
       "gaps %s" % gaps)


# 10 ------------------------------------------------------------------------------------
def _raising(kind, code=None, body=b"", headers=None):
    """A transport that raises a pricehistory error whose `__cause__` is an HTTPError, the shape
    of the old retry home. The default transport never raises an HTTP status (`net.open` returns
    it), but a transport may raise anything, so a non-429 row stays: it must be a CardLadderError
    and no latch. The HTTPError's text holds the Authorization header, as a careless message could.
    Returns make(request_headers) -> exception."""
    def make(request_headers):
        exc = kind("The service answered %s." % code)
        if code is not None:
            hdrs = email.message.Message()
            for k, v in (headers or {}).items():
                hdrs[k] = v
            exc.__cause__ = urllib.error.HTTPError(
                CF_BASE + "httpprofile", code, "HTTP %d %s" % (code, request_headers.get("authorization", "")),
                hdrs, io.BytesIO(body))
        return exc
    return make


def _raise_on(n: int, make):
    def answer(_w, k, headers, _b):
        if k == n:
            raise make(headers)
        return None
    return answer


def _bare_http(code, body=b"", headers=None):
    """A transport that raises the HTTPError itself, not wrapped. Like `_raising`, its text
    holds the Authorization header, and only a non-429 row uses it."""
    def make(request_headers):
        hdrs = email.message.Message()
        for k, v in (headers or {}).items():
            hdrs[k] = v
        return urllib.error.HTTPError(
            CF_BASE + "httpprofile", code, "HTTP %d %s" % (code, request_headers.get("authorization", "")),
            hdrs, io.BytesIO(body))
    return make


def _latches_on(cl, label, answer) -> None:
    """The transport RETURNS a 429 on the second callable request (`answer`, as World takes it):
    RateLimited, no retry, no wait, no token in the text, and every later call raises and sends
    nothing."""
    w = World(answer=answer)
    client = w.client(cl)
    client.call("httpprofile", {})
    with printed() as log:
        err = _raises(cl.RateLimited, client.call, "httpprofile", {})
    ok(isinstance(err, cl.RateLimited), "%s raises RateLimited" % label, repr(err))
    sent_calls = w.callable_requests()
    ok(len(sent_calls) == 2 and w.now == sent_calls[-1].t,
       "%s: sent once, no retry and no wait" % label,
       "%d sent, clock moved %.1fs" % (len(sent_calls), w.now - sent_calls[-1].t))
    if isinstance(err, BaseException):
        ok(not _leaks(str(err) + _trace(err) + log.text), "%s: no token in the text" % label)
    sent, exchanges = len(w.log), len(w.exchanges)
    w.now += 120.0
    later = [_raises(cl.RateLimited, client.call, n, {}) for n in ("httpprofile", "httpcardestimate")]
    ok(all(isinstance(e, cl.RateLimited) for e in later) and len(w.log) == sent
       and len(w.exchanges) == exchanges,
       "%s: the stop holds, so a later call raises and sends nothing" % label,
       "%r, %d new requests" % (later, len(w.log) - sent))


def _no_latch_on(cl, label, make) -> None:
    """The second callable request raises what `make` builds: a CardLadderError that is not a
    rate limit, and the next call is sent."""
    w = World(answer=_raise_on(2, make))
    client = w.client(cl)
    client.call("httpprofile", {})
    err = _raises(cl.CardLadderError, client.call, "httpprofile", {})
    ok(isinstance(err, cl.CardLadderError) and not isinstance(err, cl.RateLimited),
       "%s is a CardLadderError and not a rate limit" % label, repr(err))
    got = _outcome(client.call, "httpprofile", {"again": 1})
    ok(got == {"echo": "httpprofile", "data": {"again": 1}} and len(w.callable_requests()) == 3,
       "%s does not latch: the next call is sent" % label, repr(got))


def case_raised_rate_limit(cl) -> None:
    """A 429 is a returned status, as `net.open` gives it. A Retry-After header cannot reach the
    Client (the transport returns a status and a body), so `case_net_429_is_sent_once` has that row."""
    unreachable = pricehistory.Unreachable
    for label, body in (("a returned 429 with the message body", ENVELOPE),
                        ("a returned 429 with an empty body", b"")):
        _latches_on(cl, label, _limited_on(2, 429, body))

    # a raised error is not a rate limit: a 403 refused by name, a 500, a connection that never opened
    for label, make in (("Blocked (403)", _raising(pricehistory.Blocked, 403, b"Forbidden")),
                        ("Unreachable from a 500", _raising(unreachable, 500, b"oops")),
                        ("Unreachable from a 503", _raising(unreachable, 503, b"")),
                        ("Offline", _raising(pricehistory.Offline))):
        _no_latch_on(cl, label, make)


def case_bare_http_429(cl) -> None:
    """A 429 whose body is the callable's own message or a bare one, returned as a status, then
    the urllib HTTPError a transport may raise for any other status (not a rate limit)."""
    for label, body in (("a returned 429 whose body is Card Ladder's envelope", ENVELOPE),
                        ("a returned 429 whose body echoes the request header",
                         ENVELOPE + b" Bearer " + ID_MARK.encode())):
        _latches_on(cl, label, _limited_on(2, 429, body))
    for code in (403, 500):
        _no_latch_on(cl, "a bare HTTPError %d" % code, _bare_http(code, b"nope"))


# 11 ------------------------------------------------------------------------------------
def case_raised_transport_paces(cl) -> None:
    raisers = [
        ("a plain OSError", lambda _h: OSError("connection reset")),
        ("Offline", _raising(pricehistory.Offline)),
        ("Blocked (403)", _raising(pricehistory.Blocked, 403, b"Forbidden")),
        ("Unreachable from a 503", _raising(pricehistory.Unreachable, 503, b"")),
    ]
    for label, make in raisers:
        w = World(answer=_raise_on(1, make))
        client = w.client(cl)
        err = _raises(cl.CardLadderError, client.call, "httpprofile", {})
        ok(isinstance(err, cl.CardLadderError), "%s raises a CardLadderError" % label, repr(err))
        got = _outcome(client.call, "httpprofile", {})
        gaps = _gaps(w)
        ok(isinstance(got, dict) and len(gaps) == 1 and gaps[0] >= 8.0 - 1e-6
           and w.slept >= 8.0 - 1e-6,
           "after %s the next call waits the full 8 seconds" % label,
           "gaps %s, slept %.1fs, got %r" % (gaps, w.slept, got))


# 12 ------------------------------------------------------------------------------------
def case_latch_race(cl) -> None:
    """The first thread's call is slow and is answered 429 (a returned status). The other two
    threads are by then in the pace wait, past any check made before it. Neither may send
    after the answer."""
    vt = VirtualTime(1_000_000.0)
    seen: dict = {}

    def slow_429(world, n, headers, _body):
        if n != 2:
            return None
        world.vtime.sleep(3.0)  # the answer takes 3 seconds; the pace wait of the others is 8
        seen["at"] = world.vtime.now
        return 429, ENVELOPE

    w = World(vtime=vt, answer=slow_429)
    client = w.client(cl)
    client.call("httpprofile", {"warm": True})
    outcomes: list = []

    def work(i):
        outcomes.append(_outcome(client.call, "httpprofile", {"i": i}))

    threads = [threading.Thread(target=work, args=(i,), daemon=True) for i in range(3)]
    for t in threads:
        t.start()
    vt.run(threads)
    for t in threads:
        t.join(5)
    late = [r for r in w.callable_requests() if r.t > seen.get("at", float("inf"))]
    ok("at" in seen, "the slow call reached its 429 answer")
    ok(not late, "no thread sends a request after the 429 answer, the ones in the pace wait included",
       "%d sent after it, at %s" % (len(late), [r.t - seen.get("at", 0) for r in late]))
    ok(len(outcomes) == 3 and all(isinstance(o, cl.RateLimited) for o in outcomes),
       "all three threads end in RateLimited", repr(outcomes))


# 13 ------------------------------------------------------------------------------------
def case_send_checks_the_callable(cl) -> None:
    w = World()
    client = w.client(cl)
    client.call("httpprofile", {})
    w.now += 20.0  # past the pace, so the next real send needs no wait
    slept = w.slept
    sent = len(w.log)
    urls = [CF_BASE + name for name in OUT_OF_BOUNDS]
    urls += [CF_BASE + "httpnotreal", CF_BASE.upper().replace("HTTPS", "https") + "httpbuildcollectioncard",
             CF_BASE + "httpbuildcollectioncard?x=1"]
    errs = [_raises(cl.Refused, client.send, "POST", u, {"Authorization": "Bearer x"}, b"{}") for u in urls]
    ok(all(isinstance(e, cl.Refused) for e in errs), "send of a write or unknown callable URL raises Refused",
       "got %r" % errs)
    ok(len(w.log) == sent, "send of those URLs reaches no transport", "%d sent" % (len(w.log) - sent))
    client.call("httpprofile", {"after": 1})
    ok(w.slept == slept, "the refused sends did not stamp the pace: the next real call waits nothing",
       "the next call slept %.1fs" % (w.slept - slept))

    # a read callable through send is not refused
    before = len(w.callable_requests())
    client.send("POST", CF_BASE + "httpprofile", {"Authorization": "Bearer x"}, b"{}")
    ok(len(w.callable_requests()) == before + 1, "send of an allowed callable URL reaches the transport")


# 14 ------------------------------------------------------------------------------------
# The default transport, built on net.open, the one retry home (every network call retries through one method).
class _Resp(io.BytesIO):
    """What urllib's opener returns for a 2xx."""

    status = 200
    headers = None


class _BrokenResp(_Resp):
    """A response whose body read fails: the connect and the status line went through."""

    def read(self, *_a):
        raise ConnectionResetError(errno.ECONNRESET, "Connection reset by peer")


class NetWorld(World):
    """A World behind the real `net.open`, for a Client built with no transport.

    `through()` swaps `pipeline.net.open` for a spy that records the keywords the client passed, then
    runs the REAL `net.open` (its retry rule, its reading of a status) on this world's `opener`,
    `clock` and `sleep`. Nothing reaches a socket.

    opens       one per net.open call the client made: SimpleNamespace(url, kw), kw as passed.
    attempts    one per opener call, the urllib Request each time: every attempt net.open made.
    wire        one per request a host received: host, url, lowercase headers, body. A request
                refused at connect never gets here. A redirect that was followed does.
    net_sleeps  the pauses net.open took between attempts.
    plan        plan(world, k, request) -> None (the World answers), an exception (raised by the
                opener, before anything is sent) or (status, body[, headers]) (a canned answer).
                k counts the opener calls so far, this one included.
    drop        drop(world, k, request) -> None, an exception (raised by the opener AFTER the request
                is on the wire) or a response object (returned, so reading its body fails).
    """

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.opens: list = []
        self.attempts: list = []
        self.wire: list = []
        self.net_sleeps: list = []
        self.plan = None
        self.drop = None
        self.follow = True

    def net_sleep(self, seconds: float) -> None:
        self.net_sleeps.append(seconds)
        self.sleep(seconds)

    def cl_attempts(self) -> int:
        return sum(1 for r in self.attempts if CF_HOST in r.full_url)

    def opener(self, req, timeout):
        self.attempts.append(req)
        return self._serve(req)

    def _serve(self, req):
        reply = self.plan(self, len(self.attempts), req) if self.plan else None
        if isinstance(reply, BaseException):
            raise reply
        headers = dict(req.header_items())
        host = urllib.parse.urlsplit(req.full_url).hostname
        self.wire.append(SimpleNamespace(
            host=host, url=req.full_url, body=req.data or b"",
            headers={k.lower(): v for k, v in headers.items()}))
        lost = self.drop(self, len(self.attempts), req) if self.drop else None
        if isinstance(lost, BaseException):
            raise lost
        if lost is not None:
            return lost
        if reply is None:
            if host in (CF_HOST, GOOGLE_HOST):
                reply = self.transport(req.get_method(), req.full_url, headers, req.data or b"")
            else:
                reply = (200, b"{}")  # some other host: it answers anything
        status, body = reply[0], reply[1]
        hdrs = email.message.Message()
        for k, v in (reply[2] if len(reply) > 2 and reply[2] else {}).items():
            hdrs[k] = v
        if 300 <= status < 400 and self.follow and hdrs.get("Location"):
            # What urllib's own redirect handler does, and the guard in net.open's default opener
            # is not here: ask the new URL with the same headers, and with the body on 307 and 308.
            keep = status in (307, 308)
            return self._serve(urllib.request.Request(
                urllib.parse.urljoin(req.full_url, hdrs["Location"]), data=req.data if keep else None,
                headers=headers, method=req.get_method() if keep else "GET"))
        if status >= 300:  # urllib raises for a 4xx, a 5xx and a 3xx it does not follow
            raise urllib.error.HTTPError(req.full_url, status, "HTTP %d" % status, hdrs, io.BytesIO(body))
        resp = _Resp(body)
        resp.status, resp.headers = status, hdrs
        return resp

    @contextlib.contextmanager
    def through(self):
        real = net.open

        def spy(url, **kw):
            self.opens.append(SimpleNamespace(url=url, kw=dict(kw)))
            self.follow = kw.get("follow_redirects", True)
            kw.update(opener=self.opener, clock=self.clock, sleep=self.net_sleep)
            return real(url, **kw)

        net._clear_hosts()
        net.open = spy
        try:
            yield self
        finally:
            net.open = real
            net._clear_hosts()

    def default_client(self, cl):
        """A Client with no transport, as production builds it. None, and a failed check, if it
        cannot be built."""
        try:
            return cl.Client(refresh_token=RT, clock=self.clock, sleep=self.sleep)
        except TypeError as exc:
            ok(False, "Client(...) with no transport can be built", str(exc))
            return None


def _has_net_transport(cl) -> None:
    ok(callable(getattr(cl, "net_transport", None)), "the module names its default transport net_transport")


def case_net_transport_shape(cl) -> None:
    """Every Card Ladder call and the token exchange go through net.open as a write that never
    follows a redirect."""
    _has_net_transport(cl)
    w = NetWorld()
    with w.through():
        client = w.default_client(cl)
        if client is None:
            return
        results = {name: _outcome(client.call, name, {"k": name}) for name in sorted(SIX)}
    ok(all(results[n] == {"echo": n, "data": {"k": n}} for n in SIX),
       "with no transport given, each of the six calls returns its result", repr(results))
    ok(len(w.opens) == 7 and len(w.attempts) == 7 and len(w.log) == 7,
       "the token exchange and six calls are seven net.open calls, one attempt each",
       "%d net.open calls, %d attempts, %d requests" % (len(w.opens), len(w.attempts), len(w.log)))
    ok(any(GOOGLE_HOST in o.url for o in w.opens) and all(
        (GOOGLE_HOST in o.url) or o.url.startswith(CF_BASE) for o in w.opens),
       "the token exchange is one of those net.open calls", [o.url for o in w.opens])
    ok(w.opens and all(o.kw.get("method") == "POST" for o in w.opens), "every net.open call has method POST")
    ok(w.opens and all(o.kw.get("idempotent") is False for o in w.opens),
       "every net.open call has idempotent=False, so net never sends an answered write again",
       repr([o.kw.get("idempotent", "unset") for o in w.opens]))
    # With an injected opener this keyword changes nothing the world can see, so the keyword is
    # the only check there is: the case below shows what a 3xx does when it is True.
    ok(w.opens and all(o.kw.get("follow_redirects") is False for o in w.opens),
       "every net.open call has follow_redirects=False",
       repr([o.kw.get("follow_redirects", "unset") for o in w.opens]))

    # the transport itself: a status and a body for any HTTP answer, never a raise
    transport = getattr(cl, "net_transport", None)
    if not callable(transport):
        return
    w = NetWorld()
    with w.through():
        for status in (200, 429, 503):
            w.plan = lambda _w, _k, _r, s=status: (s, b"body-%d" % s)
            got = _outcome(transport, "POST", CF_BASE + "httpprofile", {"Content-Type": "application/json"}, b"{}")
            ok(got == (status, b"body-%d" % status), "net_transport returns (%d, body) as it came" % status,
               repr(got))
    ok(w.opens and w.opens[0].kw.get("data") == b"{}"
       and dict(w.opens[0].kw.get("headers") or {}).get("Content-Type") == "application/json",
       "net_transport hands the body and the headers to net.open", repr(w.opens[:1]))


def case_net_429_is_sent_once(cl) -> None:
    _has_net_transport(cl)
    for label, body, headers in (("429 with the message body", ENVELOPE, None),
                                 ("429 with an empty body", b"", None),
                                 ("429 with Retry-After 30", b"", {"Retry-After": "30"})):
        w = NetWorld()
        w.plan = lambda wd, _k, req, b=body, h=headers: (429, b, h) if wd.cl_attempts() >= 2 \
            and CF_HOST in req.full_url else None
        with w.through():
            client = w.default_client(cl)
            if client is None:
                return
            client.call("httpprofile", {})
            mark = len(w.attempts)
            with printed() as log:
                err = _raises(cl.RateLimited, client.call, "httpprofile", {})
            ok(isinstance(err, cl.RateLimited), "%s raises RateLimited" % label, repr(err))
            ok(len(w.attempts) - mark == 1, "%s: the opener is called once, so there is no retry" % label,
               "%d attempts" % (len(w.attempts) - mark))
            ok(not w.net_sleeps, "%s: net.open took no pause" % label, repr(w.net_sleeps))
            if isinstance(err, BaseException):
                ok(not _leaks(str(err) + _trace(err) + log.text), "%s: no token in the text" % label)
            held = len(w.attempts)
            w.now += 120.0
            later = [_raises(cl.RateLimited, client.call, n, {}) for n in ("httpprofile", "httpcardestimate")]
            ok(all(isinstance(e, cl.RateLimited) for e in later) and len(w.attempts) == held,
               "%s: the stop holds, so a later call raises and the opener is not called again" % label,
               "%r, %d new attempts" % (later, len(w.attempts) - held))


def case_net_503_is_sent_once(cl) -> None:
    _has_net_transport(cl)
    for label, body, headers in (("503 with an empty body", b"", None),
                                 ("503 with a body", b"upstream down", None),
                                 ("503 with Retry-After 30", b"", {"Retry-After": "30"})):
        w = NetWorld()
        w.plan = lambda wd, _k, req, b=body, h=headers: (503, b, h) if wd.cl_attempts() >= 2 \
            and CF_HOST in req.full_url else None
        with w.through():
            client = w.default_client(cl)
            if client is None:
                return
            client.call("httpprofile", {})
            mark = len(w.attempts)
            with printed() as log:
                err = _raises(cl.CardLadderError, client.call, "httpprofile", {})
            ok(isinstance(err, cl.CardLadderError) and not isinstance(err, cl.RateLimited),
               "%s is a CardLadderError and not a rate limit" % label, repr(err))
            ok(len(w.attempts) - mark == 1, "%s: the opener is called once, so there is no retry" % label,
               "%d attempts" % (len(w.attempts) - mark))
            ok(not w.net_sleeps, "%s: net.open took no pause" % label, repr(w.net_sleeps))
            if isinstance(err, BaseException):
                ok(not _leaks(str(err) + _trace(err) + log.text), "%s: no token in the text" % label)
            w.plan = None
            before = len(w.attempts)
            got = _outcome(client.call, "httpprofile", {"again": 1})
            ok(got == {"echo": "httpprofile", "data": {"again": 1}} and len(w.attempts) > before,
               "%s does not latch: the next call is sent" % label, repr(got))


def case_net_refused_connect(cl) -> None:
    """A connect that never opened sent nothing, so net.open may send it again. The case allows
    one attempt up to net's own limit, and no more."""
    _has_net_transport(cl)
    most = len(net.RETRY_PAUSES) + 1
    for label, host in (("a Card Ladder call", CF_HOST), ("the token exchange", GOOGLE_HOST)):
        w = NetWorld()
        refused = {"on": host == GOOGLE_HOST}

        def plan(wd, _k, req, host=host, refused=refused):
            if refused["on"] and host in req.full_url:
                auth = dict(req.header_items()).get("Authorization", "")
                return urllib.error.URLError(
                    ConnectionRefusedError(errno.ECONNREFUSED, "Connection refused %s %r" % (auth, req.data)))
            return None

        w.plan = plan
        with w.through():
            client = w.default_client(cl)
            if client is None:
                return
            if host == CF_HOST:
                client.call("httpprofile", {})
                refused["on"] = True
            mark, sent = len(w.attempts), len(w.wire)
            with printed() as log:
                err = _raises(cl.CardLadderError, client.call, "httpprofile", {"x": 1})
            made = w.attempts[mark:]
            ok(isinstance(err, cl.CardLadderError) and not isinstance(err, cl.RateLimited),
               "a refused connect to %s is a CardLadderError and not a rate limit" % label, repr(err))
            ok(1 <= len(made) <= most and all(host in r.full_url for r in made),
               "a refused connect to %s is tried once, or again within net's limit of %d" % (label, most),
               "%d attempts" % len(made))
            ok(len(w.wire) == sent, "a refused connect to %s sent nothing" % label)
            if isinstance(err, BaseException):
                ok(not _leaks(str(err) + _trace(err) + log.text), "%s: no token in the text" % label)
            refused["on"] = False
            got = _outcome(client.call, "httpprofile", {"again": 1})
            ok(got == {"echo": "httpprofile", "data": {"again": 1}},
               "a refused connect to %s does not latch: the next call is sent" % label, repr(got))


def case_net_dropped_after_connect(cl) -> None:
    """A failure after the request went out may have done the work, so the default transport
    sends it ONCE. The failure stays armed for every attempt to the host, so a second try shows
    as a second attempt and a second request on the wire, not as a success that hides it."""
    _has_net_transport(cl)
    shapes = (
        ("a connection reset after the request was sent",
         lambda: urllib.error.URLError(ConnectionResetError(errno.ECONNRESET, "Connection reset by peer"))),
        ("a socket.timeout after the request was sent", lambda: socket.timeout("timed out")),
        ("a reset while the answer is read", lambda: _BrokenResp(b"{}")),
    )
    for where, host in (("a Card Ladder call", CF_HOST), ("the token exchange", GOOGLE_HOST)):
        for what, make in shapes:
            label = "%s: %s" % (where, what)
            w = NetWorld()
            armed = {"on": host == GOOGLE_HOST}
            w.drop = lambda _w, _k, req, make=make, host=host, armed=armed: \
                make() if armed["on"] and host in req.full_url else None
            with w.through():
                client = w.default_client(cl)
                if client is None:
                    return
                if host == CF_HOST:
                    client.call("httpprofile", {})
                    armed["on"] = True
                mark, sent = len(w.attempts), len(w.wire)
                with printed() as log:
                    err = _raises(cl.CardLadderError, client.call, "httpprofile", {"x": 1})
                made = w.attempts[mark:]
                ok(isinstance(err, cl.CardLadderError)
                   and not isinstance(err, (cl.RateLimited, cl.TokenRejected)),
                   "%s raises a CardLadderError, not a rate limit or a rejected token" % label, repr(err))
                ok(len(made) == 1 and all(host in r.full_url for r in made),
                   "%s: the opener is called once, so the write is not sent again" % label,
                   "%d attempts" % len(made))
                ok(len(w.wire) - sent == 1, "%s: one request reached the wire" % label,
                   "%d requests" % (len(w.wire) - sent))
                ok(not w.net_sleeps, "%s: net.open took no pause" % label, repr(w.net_sleeps))
                if host == GOOGLE_HOST:
                    ok(not w.callable_requests(), "%s: nothing is sent to Card Ladder" % label)
                if isinstance(err, BaseException):
                    ok(not _leaks(str(err) + _trace(err) + log.text), "%s: no token in the text" % label)
                armed["on"] = False
                got = _outcome(client.call, "httpprofile", {"again": 1})
                ok(got == {"echo": "httpprofile", "data": {"again": 1}},
                   "%s does not latch: the next call is sent" % label, repr(got))


def _limit_wording(cl) -> str:
    """What the client says when Card Ladder rate-limits it, taken from the client itself."""
    client = World(answer=_limited_on(2, 429, ENVELOPE)).client(cl)
    client.call("httpprofile", {})
    return str(_raises(cl.RateLimited, client.call, "httpprofile", {}))


def case_net_token_exchange(cl) -> None:
    _has_net_transport(cl)
    google_400 = json.dumps({"error": {"code": 400, "message": "INVALID_REFRESH_TOKEN",
                                       "status": "INVALID_ARGUMENT"}}).encode()
    google_429 = json.dumps({"error": {"code": 429, "message": "TOO_MANY_ATTEMPTS_TRY_LATER",
                                       "status": "RESOURCE_EXHAUSTED"}}).encode()

    def on_google(status, body):
        return lambda _w, _k, req: (status, body) if GOOGLE_HOST in req.full_url else None

    # Google refuses the token: say so, and say what to do
    for label, setup in (("answering with Google's own error", lambda w: setattr(w, "plan", on_google(400, google_400))),
                         ("echoing the request", lambda w: setattr(w, "exchange_mode", "reject"))):
        w = NetWorld()
        setup(w)
        with w.through():
            client = w.default_client(cl)
            if client is None:
                return
            with printed() as log:
                err = _raises(cl.TokenRejected, client.call, "httpprofile", {})
            ok(isinstance(err, cl.TokenRejected), "a Google 400 %s raises TokenRejected" % label, repr(err))
            text = str(err)
            ok(re.search(r"copy\s+%s\s+again" % KEY_NAME, text, re.I) is not None,
               "a Google 400 %s: the text says to copy %s again" % (label, KEY_NAME), text)
            ok(not _leaks(text + _trace(err) + log.text) if isinstance(err, BaseException) else False,
               "a Google 400 %s: no token in the text" % label)
            ok(len(w.attempts) == 1 and not w.net_sleeps and not w.callable_requests(),
               "a Google 400 %s is sent once, with no retry and no call to Card Ladder" % label,
               "%d attempts" % len(w.attempts))
            w.plan, w.exchange_mode = None, "ok"
            got = _outcome(client.call, "httpprofile", {"again": 1})
            ok(got == {"echo": "httpprofile", "data": {"again": 1}},
               "a Google 400 %s does not latch: with a good token the next call is sent" % label, repr(got))

    # Google rate-limits the exchange: it is Google's limit, not Card Ladder's
    cl_wording = _limit_wording(cl)
    w = NetWorld()
    w.plan = on_google(429, google_429)
    with w.through():
        client = w.default_client(cl)
        if client is None:
            return
        with printed() as log:
            err = _raises(cl.CardLadderError, client.call, "httpprofile", {})
        text = str(err)
        ok(isinstance(err, cl.CardLadderError) and not isinstance(err, cl.RateLimited),
           "a Google 429 is a CardLadderError and not RateLimited", repr(err))
        ok(GOOGLE_HOST in text, "a Google 429 names %s" % GOOGLE_HOST, text)
        ok(cl_wording and cl_wording not in text and "rate-limited this sweep" not in text,
           "a Google 429 is not worded as Card Ladder's rate limit", text)
        ok(not _leaks(text + _trace(err) + log.text) if isinstance(err, BaseException) else False,
           "a Google 429: no token in the text")
        ok(len(w.attempts) == 1 and not w.net_sleeps and not w.callable_requests(),
           "a Google 429 is sent once, with no retry and no call to Card Ladder", "%d attempts" % len(w.attempts))
        w.plan = None
        got = _outcome(client.call, "httpprofile", {"again": 1})
        ok(got == {"echo": "httpprofile", "data": {"again": 1}} and len(w.exchanges) == 1,
           "a Google 429 does not latch the client: the next call exchanges and is sent", repr(got))


def case_net_token_exchange_statuses(cl) -> None:
    """Only Google refusing the token says to copy it again. Google being down, or redirecting,
    says nothing about the token: the owner must not be sent to copy a good one."""
    _has_net_transport(cl)
    google_error = lambda code, status: json.dumps(  # noqa: E731
        {"error": {"code": code, "message": "from Google", "status": status}}).encode()
    refused = ((400, "INVALID_ARGUMENT"), (401, "UNAUTHENTICATED"), (403, "PERMISSION_DENIED"))
    unrelated = ((500, "INTERNAL"), (503, "UNAVAILABLE"), (302, None))

    for status, name in refused + unrelated:
        w = NetWorld()
        # the 5xx answers echo the request, a worst case for a message built from the body
        w.plan = lambda _w, _k, req, status=status, name=name: (
            (status, b"", {"Location": "https://other.example.test/landing"}) if status == 302
            else (status, req.data if status >= 500 else google_error(status, name))
        ) if GOOGLE_HOST in req.full_url else None
        label = "a Google %d" % status
        with w.through():
            client = w.default_client(cl)
            if client is None:
                return
            with printed() as log:
                err = _raises(cl.CardLadderError, client.call, "httpprofile", {})
            text = str(err)
            copy_again = re.search(r"copy\b.*\bagain", text, re.I | re.S) is not None
            if (status, name) in refused:
                ok(isinstance(err, cl.TokenRejected), "%s raises TokenRejected" % label, repr(err))
                ok(re.search(r"copy\s+%s\s+again" % KEY_NAME, text, re.I) is not None,
                   "%s: the text says to copy %s again" % (label, KEY_NAME), text)
            else:
                ok(isinstance(err, cl.CardLadderError)
                   and not isinstance(err, (cl.TokenRejected, cl.RateLimited)),
                   "%s is a CardLadderError, not a rejected token or a rate limit" % label, repr(err))
                ok(GOOGLE_HOST in text, "%s: the text names %s" % (label, GOOGLE_HOST), text)
                ok(not copy_again, "%s: the text does not say to copy the token again" % label, text)
            ok(not _leaks(text + _trace(err) + log.text) if isinstance(err, BaseException) else False,
               "%s: no token in the text" % label)
            ok(len(w.attempts) == 1 and not w.net_sleeps and not w.callable_requests(),
               "%s is sent once, with no retry and no call to Card Ladder" % label,
               "%d attempts" % len(w.attempts))
            w.plan = None
            got = _outcome(client.call, "httpprofile", {"again": 1})
            ok(got == {"echo": "httpprofile", "data": {"again": 1}},
               "%s does not latch: with a good token the next call is sent" % label, repr(got))


def case_net_redirect_not_followed(cl) -> None:
    """A 3xx is an answer. It is not followed, so nothing goes to a second host: not the
    Authorization header of a call, and not the refresh token of the exchange."""
    _has_net_transport(cl)
    other = "https://other.example.test/landing"
    for label, host, status, where in (
            ("a 302 from a Card Ladder call to another host", CF_HOST, 302, other),
            ("a 307 from a Card Ladder call to another host", CF_HOST, 307, other),
            ("a 302 from a Card Ladder call to its own host", CF_HOST, 302, CF_BASE + "httpcertlookup"),
            ("a 307 from the token exchange to another host", GOOGLE_HOST, 307, other)):
        w = NetWorld()
        moved = {"mark": 0 if host == GOOGLE_HOST else None}  # the wire length when the redirect starts

        def plan(wd, _k, req, host=host, status=status, where=where, moved=moved):
            """Answer the first request to `host` once the redirect has started, and no other."""
            if moved["mark"] is not None and host in req.full_url and len(wd.wire) == moved["mark"]:
                return status, b"", {"Location": where}
            return None

        w.plan = plan
        with w.through():
            client = w.default_client(cl)
            if client is None:
                return
            if host == CF_HOST:
                client.call("httpprofile", {})
            moved["mark"] = mark = len(w.wire)
            with printed() as log:
                got = _outcome(client.call, "httpprofile", {"x": 1})
            sent = w.wire[mark:]
            ok(isinstance(got, cl.CardLadderError) and not isinstance(got, cl.RateLimited),
               "%s ends in a CardLadderError, with no result" % label, repr(got))
            ok(len(sent) == 1 and sent[0].host == host,
               "%s is not followed: one request, to the host that was asked" % label,
               repr([(r.host, r.url) for r in sent]))
            strays = [r for r in w.wire if r.host not in (CF_HOST, GOOGLE_HOST)]
            ok(not strays, "%s: no request reaches a second host" % label, repr([r.url for r in strays]))
            ok(not any("authorization" in r.headers or RT.encode() in r.body or ID_MARK.encode() in r.body
                       for r in w.wire[mark + 1:]),
               "%s: no Authorization header or refresh token follows it" % label)
            if isinstance(got, BaseException):
                ok(not _leaks(str(got) + _trace(got) + log.text), "%s: no token in the text" % label)


CASES = [case_allow_list, case_refuse_callable, case_refuse_host, case_spacing,
         case_rate_limit, case_token, case_no_token_in_text, case_read_functions,
         case_threads_keep_the_pace, case_raised_rate_limit, case_raised_transport_paces,
         case_latch_race, case_send_checks_the_callable, case_bare_http_429,
         case_net_transport_shape, case_net_429_is_sent_once, case_net_503_is_sent_once,
         case_net_refused_connect, case_net_dropped_after_connect, case_net_token_exchange,
         case_net_token_exchange_statuses, case_net_redirect_not_followed]


def main() -> int:
    try:
        from pipeline import cardladder
    except ImportError as exc:
        ok(False, "pipeline.cardladder imports", "%s: %s" % (type(exc).__name__, exc))
        print(f"\n{PASS} passed, {FAIL} failed")
        return 1
    for case in CASES:
        print(case.__name__)
        VIOLATIONS.clear()
        with offline():
            try:
                case(cardladder)
            except Exception as exc:  # noqa: BLE001 - a case that dies is a failed case
                ok(False, f"{case.__name__} ran to the end", f"{type(exc).__name__}: {exc}")
        ok(not VIOLATIONS, f"{case.__name__} touched no real clock, socket or .env", "; ".join(VIOLATIONS))
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
