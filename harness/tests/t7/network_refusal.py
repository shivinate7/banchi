"""T7 group: while T7 runs, non-loopback network is refused, and loopback still answers.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.

WHY. T7 reached the live TCGplayer and tcgcsv hosts from about a dozen checks, 12 to 23 real
connections a run, so a cloud run sat silent for minutes on answers no case needed. The fix
refuses non-loopback network for the length of T7's run, in process and in the child processes
T7 starts. These cases pin the three halves of that: a refused call names its check and host on
stderr, a child inherits a route that goes nowhere, and loopback, which every fake portal in T7
uses, still answers.

THE PROBE HOST IS A DOCUMENTATION ADDRESS, NOT A LIVE HOST. 192.0.2.0/24 is reserved for
examples, so no service answers there. Probing a live host on the current code would reach it,
and a test fixture never reaches a paid or live service. An IP literal also keeps the refusal
independent of name lookup.
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import sys
from contextlib import redirect_stderr
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from harness.tests import Checks
from harness.tests.t7.common import _spawn_server
from pipeline import net

PROBE_HOST = "192.0.2.1"
PROBE_URL = f"https://{PROBE_HOST}/"
PROBE_TIMEOUT_S = 2.0
# A hang guard for the child only. No case asserts how long a refusal took (P5).
CHILD_TIMEOUT_S = 30
REFUSAL_LINE = re.compile(r"^T7 network refused: (\S+) -> (\S+)$", re.MULTILINE)

# The child's view of its route, then its own call. It connects to the route only when the route is
# loopback, so the case never opens a socket to anything but this machine.
CHILD_SOURCE = """\
import json, socket, sys, urllib.parse, urllib.request
host = sys.argv[1]
route = urllib.request.getproxies().get("https") or ""
print(json.dumps({"route": route, "bypass": bool(urllib.request.proxy_bypass(host))}))
where = urllib.parse.urlsplit(route)
if where.hostname is None:
    print("NO ROUTE")
elif where.hostname not in ("127.0.0.1", "localhost", "::1"):
    print("ROUTE NOT LOOPBACK")
else:
    try:
        socket.create_connection((where.hostname, where.port or 80), timeout=3).close()
        print("ROUTE OPEN")
    except OSError as exc:
        print("ROUTE REFUSED " + type(exc).__name__)
try:
    urllib.request.urlopen(f"https://{host}/", timeout=3)
    print("ANSWERED")
except Exception as exc:
    print("FAILED " + type(exc).__name__)
"""


class _Pong(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's name
        body = b"pong"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003 - BaseHTTPRequestHandler's name
        pass


def check_run_refuses_live_network_in_process(checks: Checks) -> None:
    """A check that reaches a host in process gets no answer, and a stderr line names it.

    `pipeline.net.request` is the one door product calls go out by, so a refusal at the socket
    level covers it. The line is `T7 network refused: <check> -> <host>`: it is what a reader of a
    stalled run needs, to see which check reached out. "Refused" is the raise plus that line
    together, because a connect failure on the current code also raises.
    """
    checks.note("")
    checks.note("T7 NETWORK — a live call is refused in process, and its line names the check and host")
    buffer = io.StringIO()
    raised = None
    with redirect_stderr(buffer):
        try:
            net.request(PROBE_URL, timeout=PROBE_TIMEOUT_S)
        except Exception as exc:  # noqa: BLE001 - every failure to answer is the answer here
            raised = exc
    checks.ok(
        raised is not None,
        f"the call to {PROBE_HOST} returned no answer",
        "it returned a body",
    )
    named = [
        match.group(1) for match in REFUSAL_LINE.finditer(buffer.getvalue())
        if match.group(2) == PROBE_HOST
    ]
    checks.equal(
        named,
        ["check_run_refuses_live_network_in_process"],
        f"the refusal printed one stderr line naming this check and {PROBE_HOST}",
    )


def check_run_loopback_still_answers(checks: Checks) -> None:
    """Green control beside the refusal: a loopback call still gets its answer.

    Every fake portal and the capture server in T7 listens on 127.0.0.1. A refusal that caught
    loopback too would turn every one of those cases red for a reason that has nothing to do
    with the case.
    """
    checks.note("")
    checks.note("T7 NETWORK — loopback is not refused")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Pong)
    _spawn_server(httpd)
    try:
        body = net.request(f"http://127.0.0.1:{httpd.server_address[1]}/ping", timeout=PROBE_TIMEOUT_S)
    finally:
        httpd.shutdown()
        httpd.server_close()
    checks.equal(body, b"pong", "a loopback call still answers while non-loopback network is refused")


def check_run_child_process_routes_through_refused_proxy(checks: Checks) -> None:
    """A child process T7 starts inherits a route that goes nowhere, not the host.

    The child reports the HTTPS route urllib would take and whether it bypasses the proxy for the
    probe host. The route must be a loopback port that refuses a connection, the probe host must
    not be bypassed, and the child's own call must not answer. The route check is a real connect
    to that loopback port, so a sandbox whose own egress proxy listens on loopback fails it.
    """
    checks.note("")
    checks.note("T7 NETWORK — a child process goes through the refused route")
    try:
        done = subprocess.run(
            [sys.executable, "-c", CHILD_SOURCE, PROBE_HOST],
            capture_output=True,
            text=True,
            timeout=CHILD_TIMEOUT_S,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        checks.ok(False, f"the child did not finish within {CHILD_TIMEOUT_S} s")
        return
    lines = done.stdout.splitlines()
    try:
        report = json.loads(lines[0]) if lines else {}
    except ValueError:
        report = {}
    route_state = lines[1] if len(lines) > 1 else "no report"
    checks.ok(
        route_state.startswith("ROUTE REFUSED"),
        "a child process's HTTPS route is a loopback port that refuses connections",
        f"route {report.get('route')!r} was: {route_state}",
    )
    checks.ok(
        report.get("bypass") is False,
        f"and the child does not bypass that route for {PROBE_HOST}",
        f"report: {report!r}",
    )
    checks.ok(
        "ANSWERED" not in lines[2:3],
        f"the child's own call to {PROBE_HOST} did not answer",
        done.stdout[-400:],
    )


CHECKS = (
    check_run_refuses_live_network_in_process,
    check_run_loopback_still_answers,
    check_run_child_process_routes_through_refused_proxy,
)
