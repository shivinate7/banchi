#!/usr/bin/env python3
"""Is the LAN URL still good? — the whole chain, end to end, from this machine.

THIS IS NOT IN `make check`, AND THE REASON IS NOT D18's. Nothing here writes, so the rule
about generators is not what keeps it out. It is out because `make check` is HERMETIC: every
row of it answers from the tree alone, and a row that resolves DNS, opens sockets and depends
on a server being up would go red on a train, in a worktree, and on any machine that is not
the owner's rig. A check that fails for reasons unrelated to the commit is one people learn to
ignore, and a check people ignore is worse than an absent one.

So it is a target you RUN, on the machine the URL points at, when you want to know.

WHAT IT IS FOR. The owner reaches this product from a phone at `http://pkmnscan.lan:8000`,
and that address is held up by six things in two places. Two are the owner's, on their UniFi,
and this repo does not touch them (D43): a DHCP reservation pinning this Mac to an address,
and a local DNS record mapping the name to it. Four are here: Vite's `allowedHosts`, the
client composing the capture base from `location.hostname`, `PKMNSCAN_LAN_NAME` in `.env`, and
the `PKMNSCAN_ALLOWED_ORIGINS` the supervisor composes from it.

THE FAILURE THIS EXISTS FOR IS SILENT, WHICH IS WHY LOOKING IS NOT ENOUGH. Reads are ungated
and writes are origin-checked (D43). If `PKMNSCAN_LAN_NAME` goes missing from `.env` — a fresh
clone, a rewritten `.env`, a `.env` copied from `.env.example` before this variable was listed
there — every screen still renders and the whole inventory still draws, and capture, undo,
mark-sold, retire, the mid-box delete and the claim editor all answer 403 `origin_not_allowed`.
The app looks fine until you try to change something. So the last check here PRESSES a write.

NOTHING IS WRITTEN BY PRESSING IT. The origin gate runs in `_dispatch`, ahead of every handler
and therefore ahead of the body being read at all. `POST /capture` with no body is refused by
the gate as `origin_not_allowed` when the origin is unknown, and by `_body()` as
`body_required` when it is known — and `body_required` is raised before the store is opened,
let alone locked. The two answers are the experiment: same request, one header different.
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]

# The supervisor is imported rather than restated, for the reason it states about the capture
# server: a second hand-written spelling of `PKMNSCAN_LAN_NAME` would agree until the day one
# moved, and the symptom of the disagreement is exactly the silent 403 above. `serve.py` is
# import-safe — it defines and computes, and starts nothing until called.
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from server import ports  # noqa: E402

import serve  # noqa: E402  isort:skip

TIMEOUT = 8

GREEN, RED, YELLOW, DIM, BOLD, OFF = (
    "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"
)


class Result:
    """One row. `ok=None` is 'could not tell', which is never reported as a pass."""

    def __init__(self, name: str, ok: Optional[bool], detail: str, fix: str = "") -> None:
        self.name = name
        self.ok = ok
        self.detail = detail
        self.fix = fix


def local_addresses() -> List[str]:
    """Every IPv4 address this Mac currently holds, for comparing against the DNS answer.

    A lost DHCP reservation does not look like a missing record — the name still resolves, to
    an address this machine no longer has, and every request goes to whatever took it.
    """
    found: List[str] = []
    for iface in ("en0", "en1", "en2"):
        try:
            out = subprocess.run(
                ["ipconfig", "getifaddr", iface], capture_output=True, text=True, timeout=5
            )
        except (OSError, subprocess.SubprocessError):
            continue
        value = out.stdout.strip()
        if value:
            found.append(value)
    return found


def resolves_to(name: str) -> Optional[str]:
    try:
        return socket.gethostbyname(name)
    except OSError:
        return None


def request(
    url: str, origin: Optional[str] = None, method: str = "GET"
) -> Tuple[Optional[int], str, dict]:
    """(status, body, headers). A refusal is an ANSWER here, not an error to raise."""
    req = urllib.request.Request(url, method=method)
    if origin:
        req.add_header("Origin", origin)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            return response.status, response.read(4096).decode("utf-8", "replace"), dict(
                response.headers
            )
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(4096).decode("utf-8", "replace"), dict(exc.headers)
    except (urllib.error.URLError, OSError, ValueError):
        return None, "", {}


def preflight(url: str, origin: str, method: str = "POST") -> Tuple[Optional[int], List[str]]:
    """What a BROWSER asks before it sends a write, and the methods it is told it may use.

    THIS IS THE ROW THAT SPEAKS FOR THE PHONE, and it is not the same question as the one
    below it. `curl` sends no preflight, so it reaches the origin gate and reads a 403 with a
    message naming the remedy. A browser never gets that far: an origin the server does not
    know is answered `Access-Control-Allow-Methods: GET, HEAD, OPTIONS`, POST is not among
    them, and
    the browser refuses to send the request at all. `fetch` then rejects with a bare TypeError
    carrying no reason — so the 403 and its message are never seen by the page.

    A check that only did the `curl` half would therefore pass on a rig where every write from
    the phone is blocked before it leaves the handset.
    """
    req = urllib.request.Request(url, method="OPTIONS")
    req.add_header("Origin", origin)
    req.add_header("Access-Control-Request-Method", method)
    req.add_header("Access-Control-Request-Headers", "Content-Type")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            allow = response.headers.get("Access-Control-Allow-Methods", "")
            return response.status, [m.strip().upper() for m in allow.split(",") if m.strip()]
    except urllib.error.HTTPError as exc:
        allow = exc.headers.get("Access-Control-Allow-Methods", "") if exc.headers else ""
        return exc.code, [m.strip().upper() for m in allow.split(",") if m.strip()]
    except (urllib.error.URLError, OSError, ValueError):
        return None, []


def error_code(body: str) -> str:
    try:
        return json.loads(body).get("error", {}).get("code", "")
    except (ValueError, AttributeError):
        return ""


def check() -> List[Result]:
    results: List[Result] = []
    # ONE PORT, BECAUSE THERE IS ONE SERVER (D138). The dev port was read here until the app
    # moved onto the capture port; `make dev` still uses it and is still reachable on the LAN,
    # but it is a development loop rather than the address the phone is pointed at, and a row
    # about it would be asking whether a thing nobody opens from a phone is answering.
    capture = ports.capture_port(REPO_ROOT)

    # 1 — the name itself. `lan_hostnames()` is the supervisor's own reader, so this row is
    # answering the question the running server answered when it was started.
    names = serve.lan_hostnames()
    lan_names = [n for n in names if not n.endswith(".local")]
    if not lan_names:
        results.append(
            Result(
                "PKMNSCAN_LAN_NAME in .env",
                False,
                "not set — no LAN name is in the origin allowlist",
                "Add `PKMNSCAN_LAN_NAME=pkmnscan.lan` to .env (see .env.example), then "
                "`make up ARGS=--restart` when the rig is idle. Reads will work without it and "
                "every write from the LAN will answer 403 origin_not_allowed.",
            )
        )
        return results
    results.append(
        Result("PKMNSCAN_LAN_NAME in .env", True, ", ".join(lan_names))
    )

    mine = local_addresses()
    for name in lan_names:
        # 2 — DNS, and the address it answers with. Both halves matter: a record that resolves
        # to an address this Mac no longer holds is a lost DHCP reservation, and it looks
        # exactly like a working record until a request goes somewhere else.
        address = resolves_to(name)
        if address is None:
            results.append(
                Result(
                    f"{name} resolves",
                    False,
                    "does not resolve from this Mac",
                    "On the UniFi: check the local DNS record for this name still exists. "
                    "This repo does not touch your DNS (D43).",
                )
            )
            continue
        if mine and address not in mine:
            results.append(
                Result(
                    f"{name} resolves",
                    False,
                    f"-> {address}, but this Mac holds {', '.join(mine)}",
                    "The DNS record points somewhere this Mac is not. On the UniFi: the DHCP "
                    "reservation for this Mac has probably been lost or changed. Re-pin it, or "
                    "point the record at the address above.",
                )
            )
            continue
        results.append(Result(f"{name} resolves", True, f"-> {address} (this Mac)"))

        # 3 — the app, WHICH IS NOW ON THE CAPTURE PORT (D138). The supervisor serves
        # `app/dist/` beside the API, so the phone's one address is the capture port and
        # `allowedHosts` no longer decides anything here: Vite's Host check was a property of
        # Vite's dev server, and nothing on the LAN path runs it any more. A 503 is its own
        # answer and gets its own sentence — the network is fine and the build is not.
        status, body, _ = request(f"http://{name}:{capture}/")
        if status is None:
            results.append(
                Result(
                    f"app on {name}:{capture}",
                    False,
                    "nothing answered",
                    "Is the server up? `make status`, then `make up` if it is not.",
                )
            )
        elif status == 503:
            results.append(
                Result(
                    f"app on {name}:{capture}",
                    False,
                    "the app is not built",
                    "The network is fine and the bundle is not. `make status` says what the "
                    "last build did; see .serve/supervisor.log.",
                )
            )
        elif status != 200:
            results.append(Result(f"app on {name}:{capture}", False, f"HTTP {status}"))
        else:
            results.append(Result(f"app on {name}:{capture}", True, f"HTTP {status}"))

        # 4 — the capture server on the same name. The client composes this base from
        # `location.hostname` plus the checkout's baked port, so this is the address the page
        # will actually call when it is opened at that name.
        status, body, _ = request(f"http://{name}:{capture}/status")
        if status != 200:
            results.append(
                Result(
                    f"capture server on {name}:{capture}",
                    False,
                    "nothing answered" if status is None else f"HTTP {status}",
                    "Is the capture server up? `make status`.",
                )
            )
            continue
        try:
            cards = json.loads(body).get("cards")
        except ValueError:
            cards = None
        results.append(
            Result(
                f"capture server on {name}:{capture}",
                True,
                "HTTP 200" + (f", {cards} cards" if cards is not None else ""),
            )
        )

        # 5 — THE PREFLIGHT, which is what the phone actually runs into. See `preflight`.
        #
        # IT IS THE SAME ORIGIN ON BOTH SIDES NOW (D138) AND THE ROW IS KEPT ANYWAY. A page
        # served from `name:capture` calling `name:capture` is same-origin, so a browser sends
        # no preflight at all and the gate cannot refuse it — which is the one real
        # simplification this change buys the LAN path. The row stays because the gate itself
        # is unchanged and still governs `make dev` on its own port and any second device
        # pointed here by `VITE_CAPTURE_SERVER`; a green row that has become easy to pass is
        # worth more than a deleted one nobody notices the absence of.
        origin = f"http://{name}:{capture}"
        status, allowed = preflight(f"http://{name}:{capture}/capture", origin)
        if status is None:
            results.append(Result(f"browser preflight from {origin}", None, "no answer"))
        elif "POST" in allowed:
            results.append(
                Result(
                    f"browser preflight from {origin}",
                    True,
                    f"may send {', '.join(allowed)}",
                )
            )
        else:
            results.append(
                Result(
                    f"browser preflight from {origin}",
                    False,
                    f"may send only {', '.join(allowed) or '(nothing)'} — a browser will "
                    f"block every write before sending it",
                    "This is the phone's symptom and it does not look like this one. The "
                    "page gets a bare network error, so the app reports the capture server "
                    "as DOWN when it is up and answering. Restarting it fixes nothing: the "
                    "cause is the origin, so check PKMNSCAN_LAN_NAME in .env.",
                )
            )

        # 6 — THE WRITE ITSELF, without a preflight, which is how curl reaches the gate and
        # reads the refusal a browser is never shown.
        status, body, _ = request(
            f"http://{name}:{capture}/capture", origin=origin, method="POST"
        )
        code = error_code(body)
        if status == 403 and code == "origin_not_allowed":
            results.append(
                Result(
                    f"WRITES from {origin}",
                    False,
                    "403 origin_not_allowed — reads work, every write is refused",
                    "The running server does not have this origin. Either PKMNSCAN_LAN_NAME "
                    "was added to .env after the server started (restart it when the rig is "
                    "idle), or it is absent. This is the silent failure: the app looks "
                    "entirely healthy until you try to change something.",
                )
            )
        elif status == 400 and code == "body_required":
            # Past the gate and refused by the body reader, which is the pass: the gate runs
            # first, so reaching `body_required` proves the origin was accepted.
            results.append(Result(f"WRITES from {origin}", True, "allowed (gate passed)"))
        elif status is None:
            results.append(Result(f"WRITES from {origin}", None, "no answer"))
        else:
            results.append(
                Result(f"WRITES from {origin}", None, f"HTTP {status} {code}".strip())
            )

        # 6 — the control. If an origin nobody allowed can also write, the gate is not doing
        # its job and row 5 proved nothing. Same request, one header different.
        status, body, _ = request(
            f"http://{name}:{capture}/capture",
            origin="http://not-allowed.invalid:1234",
            method="POST",
        )
        if status == 403 and error_code(body) == "origin_not_allowed":
            results.append(
                Result("an unknown origin is refused", True, "403 origin_not_allowed")
            )
        else:
            results.append(
                Result(
                    "an unknown origin is refused",
                    False,
                    f"HTTP {status} — expected 403 origin_not_allowed",
                    "The write gate is not refusing a foreign origin. Any page open in the "
                    "owner's browser could drive this server. See D43 and "
                    "docs/specs/capture-server.md section 6.4.",
                )
            )

    return results


def main() -> int:
    print(f"{BOLD}Is the LAN URL still good?{OFF}  {DIM}(reaches the network; not in `make check`){OFF}")
    print()
    results = check()
    width = max(len(r.name) for r in results)
    failed = 0
    unknown = 0
    for r in results:
        if r.ok is True:
            mark, color = "PASS", GREEN
        elif r.ok is False:
            mark, color = "FAIL", RED
            failed += 1
        else:
            mark, color = "????", YELLOW
            unknown += 1
        print(f"  {color}{mark}{OFF}  {r.name.ljust(width)}  {DIM}{r.detail}{OFF}")
        if r.fix:
            for line in _wrap(r.fix, width + 8):
                print(f"        {YELLOW}{line}{OFF}")
    print()
    if failed:
        print(f"{RED}{failed} of {len(results)} checks failed.{OFF}")
        return 1
    if unknown:
        print(f"{YELLOW}Nothing failed, but {unknown} could not be told.{OFF}")
        return 1
    print(f"{GREEN}All {len(results)} checks passed — the URL works, writes included.{OFF}")
    return 0


def _wrap(text: str, indent: int, width: int = 92) -> List[str]:
    room = max(40, width - indent)
    words = text.split()
    lines: List[str] = []
    current = ""
    for word in words:
        if current and len(current) + 1 + len(word) > room:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return lines


if __name__ == "__main__":
    sys.exit(main())
