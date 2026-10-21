#!/usr/bin/env python3
"""`pipeline/cardladder.py` stays inside the bounds the owner set for the Card Ladder login,
proved against a fake transport and a fake clock: no network, no real sleep, no `.env` read.

Protects: The Card Ladder client calls only the six read callables, never `search.cardladder.com`, waits 8 seconds between calls, stops at a rate limit, refreshes its ID token in time, and never prints a token.
Governs: D-my-slabs-card-ladder

BUILD PLAN STEP 1 (`docs/specs/my-slabs.md`). `pipeline/cardladder.py` does not exist yet.
This file is written first and is red until it does. The interface it tests:

    ALLOWED_CALLABLES        frozenset of exactly the six read callables of spec 3.1 to 3.6.
                             The one constant. `Client` reads it, it holds no copy.
    CardLadderError          base class of the three below, and of any other failure.
    Refused                  a callable off the list, or host search.cardladder.com.
                             Raised before ANY request is sent, the token exchange included.
    RateLimited              the "Too many requests" answer. Latches: every later call on the
                             same client raises it at once and sends nothing.
    TokenRejected            the token exchange failed. Its text names CARDLADDER_REFRESH_TOKEN.
    Client(*, refresh_token, transport, clock, sleep)
        transport(method, url, headers, body: bytes) -> (status: int, body: bytes)
        clock() -> float seconds, sleep(seconds) -> None. Both injected, never `time`.
        .call(name, data) -> dict   POST https://us-central1-cardladder-71d53.cloudfunctions.net/<name>
                                    with JSON {"data": data} and Authorization: Bearer <id_token>.
                                    Returns the answer's "result".
        .send(method, url, headers, body) -> (status, body)
                                    The one send path. EVERY request goes through it, the token
                                    exchange included. It refuses the host before the transport.

Token exchange: POST https://securetoken.googleapis.com/v1/token?key=<public key>, the refresh
token in the BODY only (form or JSON, with grant_type=refresh_token). The answer is Google's:
{"id_token", "expires_in": "3600" (a string), "refresh_token", "user_id", ...}.

What this file leaves open, on purpose: the refresh margin (any margin that keeps the token
under its age limit), whether the token exchange counts toward the 8 seconds (this file
constrains only sends to the callable host), the public API key value, and Firestore (3.7 is
not a callable and is not covered).

WIRING THE BUILDER ADDS (the test-author guard refuses Makefile and scripts/checks.py, so the
orchestrator assigns them; copy the `pricehistory-offline-selftest` pattern in both):
    Makefile    add `cardladder-selftest` to the .PHONY line, and the target
                `cardladder-selftest:` running `$(PYTHON) scripts/cardladder-selftest.py`.
    checks.py   a CHECKS row after `pricehistory-offline-selftest`: target "cardladder-selftest",
                shard "guards-2", runs "$(PYTHON) scripts/cardladder-selftest.py", needs
                ("python3",), writes '', commit_path False, gates True, governed_by
                ("D-my-slabs-card-ladder",), and the same why_off_commit_path text.
    Also        docs/map.py entry for this file; `make tests-page` to regenerate docs/TESTS.md.
This file parses on the bare system python3 (3.9).

The fake world refuses the real clock, the real socket and any open of a file named `.env`,
and removes CARDLADDER_REFRESH_TOKEN from the environment. A client that reaches for one fails
its case.
"""

from __future__ import annotations

import builtins
import contextlib
import io
import json
import logging
import os
import socket
import sys
import time
import traceback
import urllib.parse
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

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
    in its message)."""

    def __init__(self, *, expires_in: str = "3600", answer=None, exchange: str = "ok") -> None:
        self.now = 1_000_000.0
        self.slept = 0.0
        self.expires_in = expires_in
        self.answer = answer
        self.exchange_mode = exchange
        self.log: list = []  # every request the transport saw
        self.exchanges: list = []  # (issued_at, id_token)
        self.calls: list = []  # (t, name, token, age) per callable request
        self.card_ladder_sends = 0

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds
        self.slept += seconds

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


CASES = [case_allow_list, case_refuse_callable, case_refuse_host, case_spacing,
         case_rate_limit, case_token, case_no_token_in_text]


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
