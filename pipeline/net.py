"""The one retry home: every network call in this repo goes out through `open` or `request` (D319).

A caller passes a URL and reads an answer or one typed error. No caller writes its own `urlopen`
loop, its own pauses or its own give-up.

THE RULE (rule C). A call that never connected (`Offline`) and HTTP 429, 502, 503 and 504 are
retried, up to `len(RETRY_PAUSES) + 1` attempts, inside one time budget. A `Retry-After` in seconds
sets the pause. A pause that does not fit the budget is not taken, and the call gives up. A plain
500, a 403 and any other 4xx are an answer, never retried.

A DEGRADED HOST. After `PAUSE_AFTER_FAILURES` lost calls in a row to one host (distinct URLs are not
required), every call to it makes exactly ONE attempt: no retry and no pause between attempts. A
call is never refused unsent. Any HTTP answer but a 429 or a 5xx (a success, a 3xx, a 400, 403 or
404) resets the count. A plain 500 neither counts nor resets. The count is per host and shared by
every caller in the process. A caller keeps its courtesy delay on a degraded host that answers (429,
502, 503, 504) and skips it only when `unanswered`: no lost call got an HTTP answer (refused,
unreachable, a timeout). `retry_after` is what is left of the last lost call's `Retry-After`, the
least gap before the next call.

A WRITE IS `idempotent=False`. It retries only a connect-time failure: a refused connection, a
failed name lookup, or an unreachable network or host. Anything that may have reached the other end
(a status, a timeout, a drop or a reset after the connect, a broken pipe on the body) is raised at
once with no second request, because a second request could do the work twice. A write neither
counts toward a degraded host nor is limited by it: a degraded host must never weaken a rollback
or a recovery write.

A LOGIN NEVER FOLLOWS A REDIRECT. With `follow_redirects=True`, a call that carries a Cookie or an
Authorization header refuses a redirect to another host, and never sends the header on.

Stdlib only. `pipeline/` imports nothing outside itself.
"""

from __future__ import annotations

import errno
import http.client
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Dict, Mapping, Optional, Tuple

# Pauses between the up to three attempts of one call.
RETRY_PAUSES = (0.5, 1.5)

# HTTP statuses a second ask can change. A plain 500 is not one.
RETRY_STATUSES = (429, 502, 503, 504)

# One attempt's own timeout. Short enough that all three, with their pauses, fit in
# `REQUEST_TIMEOUT_SECONDS`: request threads share four slots.
ATTEMPT_TIMEOUT_SECONDS = 9.0
REQUEST_TIMEOUT_SECONDS = 30

# How long a caller's own latch waits before it asks a lost host again (Market's stale-list latch,
# the stock-image retry). The app re-asks for a pending photo for about 31 s, so it must land inside that.
OFFLINE_WAIT_SECONDS = 12.0

# Lost calls in a row to one host before it is degraded to one attempt per call.
PAUSE_AFTER_FAILURES = 3

# Each host's lost calls in a row, keyed by `urlsplit(url).netloc`: `(count, answered, until)`.
# `answered` is True once a lost call in the run got an HTTP answer. `until` is the `_monotonic()`
# time a `Retry-After` on the last lost call asks a caller to wait for, or None. One lock guards it
# and is never held across a request.
_HOSTS: Dict[str, Tuple[int, bool, Optional[float]]] = {}
_HOSTS_LOCK = threading.Lock()


class NetError(RuntimeError):
    """A call failed. `status` and `headers` are set when the host answered with an HTTP error."""

    def __init__(self, message: str, *, status: Optional[int] = None, headers: Optional[Mapping] = None) -> None:
        super().__init__(message)
        self.status = status
        self.headers = headers


class Offline(NetError):
    """No connection was made: a refused connection, a DNS failure, a timeout before the socket
    opened. `__cause__` is the exception urllib raised. For a write it means nothing was sent."""


class Dropped(NetError):
    """A connection opened and then failed: no answer, a reset, a read that stalled. A write that
    ends here may have been done."""


class _NoLoginRedirect(urllib.request.HTTPRedirectHandler):
    """Follow a redirect, but refuse one that would carry a Cookie or Authorization header to
    another host: urllib copies every request header to the redirected request."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        if urllib.parse.urlsplit(newurl).netloc != urllib.parse.urlsplit(req.full_url).netloc:
            raise NetError("A login header would follow a redirect to another host.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Hand a 3xx back to the caller instead of following it.

    FOLLOWING BLINDLY IS THE BUG THIS PREVENTS. An expired session answers a redirect to the logon
    page, and the default handler would fetch it and return a 200 full of HTML. It also would send
    the Cookie header to wherever the redirect points.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


def _monotonic() -> float:
    return time.monotonic()


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def worth_retrying(exc: Optional[BaseException]) -> bool:
    """Whether a second ask could change this failure: `Offline`, or one of `RETRY_STATUSES`."""
    return isinstance(exc, Offline) or getattr(exc, "status", None) in RETRY_STATUSES


def _clear_hosts() -> None:
    with _HOSTS_LOCK:
        _HOSTS.clear()


def _host(url: str) -> Tuple[int, bool, Optional[float]]:
    with _HOSTS_LOCK:
        return _HOSTS.get(urllib.parse.urlsplit(url).netloc, (0, False, None))


def degraded(url: str) -> bool:
    """Whether `url`'s host lost `PAUSE_AFTER_FAILURES` calls in a row. A degraded host gets one
    attempt per call."""
    return _host(url)[0] >= PAUSE_AFTER_FAILURES


def unanswered(url: str) -> bool:
    """Whether `url`'s host is degraded and none of its lost calls got an HTTP answer: it is down,
    not busy, so a caller skips its courtesy delay. A host that answers 429 or 5xx keeps it."""
    count, answered, _ = _host(url)
    return count >= PAUSE_AFTER_FAILURES and not answered


def retry_after(url: str) -> float:
    """The seconds left of the `Retry-After` on `url`'s host's last lost call, else 0: the least gap
    a caller leaves before its next call, capped at `REQUEST_TIMEOUT_SECONDS` so a long hint never
    holds a request slot past the budget."""
    until = _host(url)[2]
    return 0.0 if until is None else min(float(REQUEST_TIMEOUT_SECONDS), max(0.0, until - _monotonic()))


def _record(url: str, lost: bool, answered: bool = False, hint: Optional[float] = None) -> None:
    """An answer resets the host. A lost call adds one, notes whether the host answered it, and
    keeps its `Retry-After`."""
    host = urllib.parse.urlsplit(url).netloc
    with _HOSTS_LOCK:
        if not lost:
            _HOSTS.pop(host, None)
            return
        count, before, _ = _HOSTS.get(host, (0, False, None))
        _HOSTS[host] = (count + 1, before or answered, None if hint is None else _monotonic() + hint)


# A write's connect-time failures: nothing was sent. Any other `OSError` under a `URLError` may
# have come after the headers went out.
_UNSENT_ERRNOS = (errno.ECONNREFUSED, errno.ENETUNREACH, errno.EHOSTUNREACH)


def _never_sent(exc: urllib.error.URLError) -> bool:
    reason = exc.reason
    return isinstance(reason, socket.gaierror) or getattr(reason, "errno", None) in _UNSENT_ERRNOS


def _retry_after(headers) -> Optional[float]:
    """The seconds a `Retry-After` header asks for, or None. An HTTP date is not read."""
    value = (headers.get("Retry-After") or "").strip() if headers else ""
    return float(value) if value.isdigit() else None


def open(  # noqa: A001 - the module's one verb; callers say `net.open`
    url: str,
    *,
    method: str = "GET",
    data: Optional[bytes] = None,
    headers: Optional[Mapping[str, str]] = None,
    timeout: float = ATTEMPT_TIMEOUT_SECONDS,
    idempotent: bool = True,
    follow_redirects: bool = True,
    max_bytes: Optional[int] = None,
    on_chunk: Optional[Callable[[bytes, Mapping], None]] = None,
    opener: Optional[Callable[..., object]] = None,
    clock: Optional[Callable[[], float]] = None,
    sleep: Optional[Callable[[float], None]] = None,
) -> Tuple[int, Dict, bytes]:
    """One call, retried by rule C. Returns `(status, headers, body)` for ANY HTTP answer, a 4xx or
    5xx included: the host answered, and the caller reads the status. Raises `Offline` (never
    connected) or `Dropped` (connected, then failed). A call is never refused unsent (read the
    module header for a degraded host and for a write).

    `follow_redirects=False` hands a 3xx back with its `Location`, and never re-sends a Cookie to a
    redirect. `follow_redirects=True` refuses a redirect to another host when the call carries a
    Cookie or Authorization header. `max_bytes` reads at most that many bytes plus one, so a caller can tell a body was cut.
    `on_chunk(block, headers)` receives a 2xx body in 1 MiB blocks instead of returning it, for a file
    too large to hold; a retry happens only before the first block.

    `opener`, `clock` and `sleep` are seams: the default opener is `urllib.request.urlopen` (looked
    up at call time), or a `NoRedirect` opener for `follow_redirects=False`.
    """
    request = urllib.request.Request(url, data=data, method=method, headers=dict(headers or {}))
    if opener is None:
        if follow_redirects:
            login = any(name.lower() in ("cookie", "authorization") for name in (headers or {}))
            guarded = urllib.request.build_opener(_NoLoginRedirect).open if login else None

            def opener(req, timeout):  # noqa: F811
                if guarded is not None:
                    return guarded(req, timeout=timeout)
                return urllib.request.urlopen(req, timeout=timeout)
        else:
            opener = urllib.request.build_opener(NoRedirect).open
    clock = clock or _monotonic
    sleep = sleep or _sleep
    started = clock()
    attempts = 1 if idempotent and degraded(url) else len(RETRY_PAUSES) + 1
    # A retry is made only if the time spent, the pause and one normal attempt fit the budget. A caller
    # with a long timeout (a 120 s export) is counted as a normal attempt, so a hang that already ate
    # the budget is not retried, while a quick 503 is.
    next_attempt = min(timeout, ATTEMPT_TIMEOUT_SECONDS)
    for attempt in range(attempts):
        failure: Optional[NetError] = None
        answer = None
        hint: Optional[float] = None
        try:
            answer = _once(opener, request, timeout, max_bytes, on_chunk)
        except urllib.error.URLError as exc:
            # urllib wraps a failure to complete the request in a URLError, before any answer: the
            # request was never completed, so a second one cannot double it.
            if idempotent or _never_sent(exc):
                failure = Offline(f"Could not connect to {urllib.parse.urlsplit(url).netloc}.")
                retry = True
            else:
                failure = Dropped("The connection failed after the request was sent.")
                retry = False
            failure.__cause__ = exc
        except (OSError, TimeoutError, http.client.HTTPException) as exc:
            # Raised raw by the response or the read: the request may have been sent. On Python 3.9
            # `socket.timeout` is an `OSError` and NOT a `TimeoutError`, so both are named.
            if idempotent:
                failure = Offline(f"No answer from {urllib.parse.urlsplit(url).netloc}.")
                retry = True
            else:
                failure = Dropped("The connection failed after the request was sent.")
                retry = False
            failure.__cause__ = exc
        else:
            retry = idempotent and answer[0] in RETRY_STATUSES
            hint = _retry_after(answer[1]) if retry else None
        if retry and attempt < attempts - 1:
            pause = RETRY_PAUSES[attempt] if hint is None else hint
            if clock() - started + pause + next_attempt <= REQUEST_TIMEOUT_SECONDS:
                sleep(pause)
                continue
        # A 429 or a retried 5xx is lost. Any other answer below 500 resets. A plain 500 does neither.
        if idempotent and (retry or (answer is not None and answer[0] < 500)):
            _record(url, lost=retry, answered=answer is not None, hint=hint)
        if failure is not None:
            raise failure
        status, got_headers, body = answer
        return status, dict(got_headers or {}), body
    raise AssertionError("unreachable")  # the loop above always returns or raises


def _once(opener, request, timeout, max_bytes, on_chunk):
    """One attempt. Returns `(status, raw headers, body)`. A connect failure propagates as it came;
    a failure while reading a body that began is `Dropped`."""
    try:
        response = opener(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(max_bytes + 1) if max_bytes else exc.read()
        except (OSError, http.client.HTTPException):
            body = b""  # an unreadable error body must not hide the status
        return exc.code, exc.headers, body
    status = getattr(response, "status", 200)
    got_headers = getattr(response, "headers", None)
    streaming = on_chunk is not None and status < 300

    def read(amount=None):
        try:
            return response.read(amount) if amount else response.read()
        except (OSError, http.client.HTTPException) as exc:
            raise Dropped("The connection failed while the answer was being read.") from exc

    try:
        if streaming:
            for block in iter(lambda: read(1 << 20), b""):
                try:
                    on_chunk(block, got_headers)
                except OSError as exc:  # the caller's sink failed: not a network failure, never retried
                    raise Dropped("The caller could not keep the answer.") from exc
            body = b""
        else:
            body = read(max_bytes + 1 if max_bytes else None)
    finally:
        close = getattr(response, "close", None)
        if close is not None:
            close()
    return status, got_headers, body


def request(
    url: str,
    *,
    method: str = "GET",
    data: Optional[bytes] = None,
    headers: Optional[Mapping[str, str]] = None,
    timeout: float = ATTEMPT_TIMEOUT_SECONDS,
    idempotent: bool = True,
    **more,
) -> bytes:
    """`open`, with every HTTP error status raised as a `NetError` carrying `status` and `headers`.
    Returns the body. `more` reaches `open` (`follow_redirects`, `max_bytes`, `on_chunk` ...)."""
    status, got_headers, body = open(
        url, method=method, data=data, headers=headers, timeout=timeout, idempotent=idempotent, **more
    )
    if status >= 400:
        raise NetError(f"The host answered with status {status}.", status=status, headers=got_headers)
    return body
