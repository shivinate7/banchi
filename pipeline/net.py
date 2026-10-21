"""The one retry home: every network call in this repo goes out through `open` or `request` (D319).

A caller passes a URL and reads an answer or one typed error. No caller writes its own `urlopen`
loop, its own pauses or its own give-up.

THE RULE (rule C). A call that never connected (`Offline`) and HTTP 429, 502, 503 and 504 are
retried, up to `len(RETRY_PAUSES) + 1` attempts, inside one time budget. A `Retry-After` in seconds
sets the pause. A pause that does not fit the budget is not taken, and the call gives up. A plain
500, a 403 and any other 4xx are an answer, never retried.

THE HOST PAUSE. A host pauses for `OFFLINE_WAIT_SECONDS` after `PAUSE_AFTER_FAILURES` lost calls
in a row, each on a different URL. The count is per host and shared by every caller in the process.
A paused host is refused with no request (`Paused`).

A WRITE IS `idempotent=False`. It retries only a connect failure, which urllib raises as a
`URLError` before any byte was sent. Anything that may have reached the other end (a status, a
timeout, a dropped connection) is raised at once with no second request, because a second request
could do the work twice. A write neither checks nor records the host pause: a paused host must
never block a rollback or a recovery write.

Stdlib only. `pipeline/` imports nothing outside itself.
"""

from __future__ import annotations

import http.client
import sys
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

# How long a paused host is refused with no request. The app re-asks for a pending photo for
# about 31 s, so one retried fetch must land inside that.
OFFLINE_WAIT_SECONDS = 12.0

# Lost calls in a row, each on a different URL, before a host pauses.
PAUSE_AFTER_FAILURES = 3

# The pause state, keyed by `urlsplit(url).netloc`. One lock guards it and is never held across a
# request.
_HOSTS: Dict[str, Dict] = {}
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


class Paused(NetError):
    """The host lost `PAUSE_AFTER_FAILURES` calls in a row, or this URL lost its retries a moment
    ago. No request was made."""


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


def _host_state(url: str) -> Dict:
    """The caller holds `_HOSTS_LOCK`."""
    return _HOSTS.setdefault(urllib.parse.urlsplit(url).netloc, {"failed": set(), "until": 0.0, "lost": {}})


def refuse_if_paused(url: str, clock: Callable[[], float] = _monotonic) -> None:
    """Raise `Paused` while `url`'s host is paused, or while `url` itself lost its retries less than
    `OFFLINE_WAIT_SECONDS` ago. Makes no request."""
    with _HOSTS_LOCK:
        state = _host_state(url)
        now = clock()
        if state["until"] <= now and state["lost"].get(url, 0.0) <= now:
            return
    raise Paused(f"{urllib.parse.urlsplit(url).netloc} is paused after repeated failures.")


def _record(url: str, lost: bool, clock: Callable[[], float]) -> None:
    """A success (`lost` False) resets the host's count and leaves every URL's wait alone. A call
    lost on a retryable kind starts that URL's own wait and counts once per distinct URL; the one
    that completes the run pauses the host, and the count starts again."""
    with _HOSTS_LOCK:
        state = _host_state(url)
        if not lost:
            state["failed"].clear()
            return
        now = clock()
        state["lost"] = {u: t for u, t in state["lost"].items() if t > now}
        state["lost"][url] = now + OFFLINE_WAIT_SECONDS
        state["failed"].add(url)
        if len(state["failed"]) >= PAUSE_AFTER_FAILURES:
            state["failed"].clear()
            state["until"] = clock() + OFFLINE_WAIT_SECONDS
            print(
                f"net {urllib.parse.urlsplit(url).netloc}: paused "
                f"{OFFLINE_WAIT_SECONDS:.0f}s after {PAUSE_AFTER_FAILURES} failures",
                file=sys.stderr, flush=True,
            )


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
    connected), `Dropped` (connected, then failed) or `Paused` (read the module header).

    `follow_redirects=False` hands a 3xx back with its `Location`, and never re-sends a Cookie to a
    redirect. `max_bytes` reads at most that many bytes plus one, so a caller can tell a body was cut.
    `on_chunk(block, headers)` receives a 2xx body in 1 MiB blocks instead of returning it, for a file
    too large to hold; a retry happens only before the first block.

    `opener`, `clock` and `sleep` are seams: the default opener is `urllib.request.urlopen` (looked
    up at call time), or a `NoRedirect` opener for `follow_redirects=False`.
    """
    request = urllib.request.Request(url, data=data, method=method, headers=dict(headers or {}))
    if opener is None:
        if follow_redirects:
            def opener(req, timeout):  # noqa: F811
                return urllib.request.urlopen(req, timeout=timeout)
        else:
            opener = urllib.request.build_opener(NoRedirect).open
    clock = clock or _monotonic
    sleep = sleep or _sleep
    if idempotent:
        refuse_if_paused(url, clock)
    started = clock()
    attempts = len(RETRY_PAUSES) + 1
    budget = max(REQUEST_TIMEOUT_SECONDS, attempts * timeout + sum(RETRY_PAUSES))
    for attempt in range(attempts):
        failure: Optional[NetError] = None
        answer = None
        hint: Optional[float] = None
        try:
            answer = _once(opener, request, timeout, max_bytes, on_chunk)
        except urllib.error.URLError as exc:
            # urllib wraps only a failure to send in a URLError, so no byte reached the host.
            failure = Offline(f"Could not connect to {urllib.parse.urlsplit(url).netloc}.")
            failure.__cause__ = exc
            retry = True
        except (OSError, TimeoutError, http.client.HTTPException) as exc:
            # Raised raw by the response or the read: the request may have been sent.
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
            if clock() - started + pause + timeout <= budget:
                sleep(pause)
                continue
        if idempotent and (retry or (answer is not None and answer[0] < 400)):
            _record(url, lost=retry, clock=clock)
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
