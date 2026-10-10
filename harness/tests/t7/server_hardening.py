"""T7 group: concurrency, origin gate, photo cache, app serve, dual-stack bind.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.
"""

from __future__ import annotations

import base64
import contextlib
import errno
import json
import os
import socket
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request

from contextlib import contextmanager
from pathlib import Path
from unittest import mock
from typing import List
from harness.tests import Checks
from server import capture_server, ports
from store import photos
from store.session import Store
from harness.tests.t7.common import (
    QuietHandler,
    _spawn_server,
    capture_payload,
    error_code,
    isolated_home,
    photo_of,
    request,
    sent_image,
)


def photo_named_by(blob: bytes) -> Path:
    """Where a capture of THESE BYTES would be filed, whether or not one ever was (D172).

    The second question: *where would a capture land*. `do_capture` names the card by hashing
    the photograph before it takes the store lock (`photos.sha256_of_bytes`), so the path is
    knowable from the request body alone — which is what lets a case assert that a REFUSED
    capture wrote no file at all, with no record left behind to look one up by.
    """
    return photos.path(photos.sha256_of_bytes(blob))

# -------------------------------------------------------------------------- concurrency


def check_concurrency(checks: Checks) -> None:
    """Simultaneous captures into one box over real sockets.

    Small N on purpose. D5 has two devices, so two and four concurrent writers is the real
    shape; the twenty-way case that found the listen backlog proved something about a socket
    option, and paying for it at the end of every turn buys nothing that this does not.

    Sockets rather than in-process calls because the lock is an flock on a fresh handle per
    call — two threads contend exactly as two processes do — and the thing worth proving is
    that no two captures ever receive the same index.
    """
    checks.note("")
    checks.note("CONCURRENCY — real sockets, small N")

    with isolated_home():
        capture_server.captures_root().mkdir(parents=True, exist_ok=True)
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = _spawn_server(httpd)
        try:
            for count in (2, 4):
                results: list = []
                errors: list = []

                def one(box=count):
                    try:
                        request = urllib.request.Request(
                            f"http://127.0.0.1:{port}/capture",
                            data=json.dumps(capture_payload(box)).encode("utf-8"),
                            headers={"Content-Type": "application/json"},
                            method="POST",
                        )
                        with urllib.request.urlopen(request, timeout=30) as response:
                            # `one` is started and joined within this same iteration,
                            # before `results`/`errors` rebind on the next one.
                            results.append(json.loads(response.read()))  # noqa: B023
                    except Exception as exc:  # noqa: BLE001
                        errors.append(exc)  # noqa: B023

                workers = [threading.Thread(target=one) for _ in range(count)]
                for worker in workers:
                    worker.start()
                for worker in workers:
                    worker.join(timeout=60)

                checks.equal(errors, [], f"{count} simultaneous captures: none errored")
                checks.equal(
                    len(results), count, f"{count} simultaneous captures: all were served"
                )
                indices = sorted(r["index"] for r in results)
                checks.equal(
                    indices,
                    list(range(1, count + 1)),
                    f"{count} simultaneous captures: indices are contiguous and unique",
                )
                # THROUGH THE STORE, BECAUSE A BOX HAS NO DIRECTORY OF ITS OWN ANY MORE
                # (D172). This globbed `box{count}/*.jpg`; photographs are filed under their
                # cards' names in one sharded root, so the only way to ask "one photo per
                # card in this box" is to walk the box and look each card's name up. That is
                # also the stronger question — a file per card rather than a file count.
                stored = [
                    index
                    for index in range(1, count + 1)
                    if photo_of(count, index).is_file()
                ]
                checks.equal(
                    len(stored), count, f"{count} simultaneous captures: one photo each"
                )
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=10)

# ----------------------------------------------------------------------- the origin gate


@contextmanager
def allowed_origins_env(value):
    """Set (or clear) `BANCHI_ALLOWED_ORIGINS`, restoring it on the way out.

    Restored rather than deleted for the reason `isolated_home` gives: six other tests share
    this process, and an origin list leaking out of here would be invisible until one of them
    made a request.
    """
    previous = os.environ.get(capture_server.ORIGINS_ENV)
    if value is None:
        os.environ.pop(capture_server.ORIGINS_ENV, None)
    else:
        os.environ[capture_server.ORIGINS_ENV] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(capture_server.ORIGINS_ENV, None)
        else:
            os.environ[capture_server.ORIGINS_ENV] = previous


def raw_head(port, path):
    """One HEAD over a bare socket, returning `(head, rest)` — every byte the server sent.

    `urllib` CANNOT ANSWER THIS QUESTION, and finding that out is the whole reason this
    exists. `http.client` knows a HEAD response carries no content and sets its own length
    to zero before reading a byte, so `response.read()` returns `b""` whether the server
    withheld the body or wrote all of it. Measured by mutation: `_send` was made to write
    the body under HEAD and every `urllib`-based assertion in `check_app_serve` stayed green.

    IT IS NOT A PEDANTIC VIOLATION. Bytes after the headers are the NEXT response as far as
    a proxy or a keep-alive client is concerned — `Connection: close` is what hides it here,
    which makes it exactly the kind of defect that surfaces on somebody else's infrastructure
    and never on this rig.
    """
    with socket.create_connection(("127.0.0.1", port), timeout=30) as sock:
        sock.sendall(
            f"HEAD {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
            f"Connection: close\r\n\r\n".encode("utf-8")
        )
        seen = b""
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            seen += chunk
    head, _, rest = seen.partition(b"\r\n\r\n")
    return head, rest


def check_origin_gate(checks: Checks) -> None:
    """The CSRF gate on the three mutating verbs, over real sockets.

    THIS IS THE ONLY SECURITY CONTROL IN THE REPO, and it is the only thing between a page
    the owner happens to have open in another tab and `DELETE /inventory/<box>/<index>` —
    D10's hard delete of the record, the sidecar and the photo, with no backup. Until this
    section existed it was a control nobody had watched fail.

    SOCKETS, NOT THE `do_*` FUNCTIONS. Every other server case in this file calls the route
    function directly, and not one of them can reach this: the gate lives in `_dispatch`,
    ahead of the handler, and reads a request HEADER. An in-process call has no headers, so
    the whole control is invisible from where the rest of this test stands.

    THE THREE CASES IT WOULD BE EASIEST TO GET WRONG LATER, each asserted with its reason:

      a refusal must change    the existing undo cases assert this about `undo_too_late` and
      NOTHING                  it matters more here, because the request that is refused is
                               the one a hostile page sent on purpose.
      an ABSENT `Origin`       `curl`, `./banchi` and this test send none, and a browser
      must still write         page cannot omit one. Tightening this to require the header
                               kills every command-line path in the project at once, and it
                               is exactly the change that looks like hardening.
      `GET` must stay open     `GET /photo` is D6's route and both the review queue and the
                               pull preview load it as an `<img>`, which sends no `Origin`
                               at all. Narrowing the read side breaks the two screens the
                               photo service exists for and protects nothing: a read of a
                               photo of a card is not a write.
    """
    checks.note("")
    checks.note("ORIGIN GATE — CSRF allowlist on POST, PUT and DELETE")

    unknown = "http://evil.example"
    allowed = capture_server.DEFAULT_ALLOWED_ORIGINS[0]
    second = capture_server.DEFAULT_ALLOWED_ORIGINS[1]

    checks.equal(
        capture_server.ORIGINS_ENV,
        "BANCHI_ALLOWED_ORIGINS",
        "the env var is spelled BANCHI_ALLOWED_ORIGINS — pinned here because the docs "
        "audit reconciles documented environment variables against real ones, and a rename "
        "would otherwise fail that check somewhere far from the code that caused it",
    )
    checks.equal(
        sorted(capture_server.DEFAULT_ALLOWED_ORIGINS),
        sorted(
            f"http://{host}:{port}"
            for port in (ports.capture_port(), ports.dev_port())
            for host in ("localhost", "127.0.0.1")
        ),
        "BOTH PORTS AND BOTH spellings of this machine are allowed by default — a browser's Origin is the "
        "literal string in the address bar, so localhost and 127.0.0.1 are the same host "
        "and not the same origin, and the owner types both — AT THE PORT THIS CHECKOUT'S "
        "APP IS ACTUALLY SERVED ON, which is the whole of D43's amendment: the list was the "
        "constant 5173 while D43 made the dev port per-checkout, so a linked worktree "
        "served an app whose every write its own server then refused",
    )
    with tempfile.TemporaryDirectory() as primary:
        (Path(primary) / ".git").mkdir()
        checks.equal(
            ports.dev_port(Path(primary)),
            5173,
            "AND THE MAIN TREE IS UNMOVED: a root whose .git is a DIRECTORY still "
            "derives 5173, so this list is byte-identical to the constant it replaced "
            "wherever the owner actually works, and every doc naming that number stays true",
        )
    with tempfile.TemporaryDirectory() as plain:
        checks.ok(
            ports.dev_port(Path(plain)) != 5173,
            "and a root with NO .git does not derive 5173 (D261, a copied "
            "tree never gets the live port): a scratch copy of main once derived the main "
            "tree's ports and its app read the owner's live store",
        )
    if ports.is_linked_worktree(ports.REPO_ROOT):
        checks.ok(
            "5173" not in "".join(capture_server.DEFAULT_ALLOWED_ORIGINS),
            "and a WORKTREE allows its own origin and not the main tree's — letting a page "
            "served by the main checkout write into a branch's store is the cross-tree "
            "write D43 exists to prevent, arriving through the one control meant to stop "
            "it. Pointing one tree's app at another's is already deliberate "
            "(VITE_CAPTURE_SERVER) and takes the deliberate answer: name the origin in "
            "BANCHI_ALLOWED_ORIGINS",
        )
    else:
        checks.note(
            "        (the worktree case is not exercised here: this IS the main checkout, "
            "and 5173 being correct in it is exactly how the defect stayed hidden)"
        )

    with isolated_home(), allowed_origins_env(None):
        capture_server.captures_root().mkdir(parents=True, exist_ok=True)
        for _ in range(3):
            capture_server.do_capture(capture_payload(3))

        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = _spawn_server(httpd)
        try:
            # --- a mutating verb from an origin this server does not know ---------------
            # THE BODY IS HELD RATHER THAN INLINED, because the assertion below is about the
            # name those bytes WOULD have been filed under. A refused capture leaves no
            # record, so there is no position to ask the store about afterwards.
            refused = capture_payload(3)
            status, body, _ = request(
                port, "POST", "/capture", origin=unknown, payload=refused
            )
            checks.equal(status, 403, "POST from an unknown origin is refused")
            checks.equal(
                error_code(body),
                "origin_not_allowed",
                "and it refuses in its own code, not as a routing or validation failure",
            )
            checks.ok(
                capture_server.ORIGINS_ENV in body.decode("utf-8", "replace"),
                "and the refusal names the env var to add a real app to, which is this "
                "server's copy rule reaching a message a person will read",
                body.decode("utf-8", "replace"),
            )
            checks.equal(
                Store().read().inventory.next_index(3),
                4,
                "AND THE REFUSAL CHANGED NOTHING: no index was burned",
            )
            checks.ok(
                not photo_named_by(sent_image(refused)).is_file(),
                "and no photo was written — the gate runs before the body is read, so the "
                "24 MB buffer for the image was never allocated either. Asserted at the name "
                "those bytes WOULD have been filed under (D172): a capture names its card by "
                "hashing its own photograph, so the path is knowable from the request alone",
            )

            status, body, _ = request(
                port,
                "PUT",
                "/inventory/3/1",
                origin=unknown,
                payload={"set_hint": "sv9"},
            )
            checks.equal(status, 403, "PUT from an unknown origin is refused")
            checks.equal(error_code(body), "origin_not_allowed", "in the same code")
            checks.ok(
                Store().read().inventory.get("3/1").set_hint is None,
                "and the recorded claim is untouched — a correction is a write, and this "
                "one never happened",
            )

            status, body, _ = request(port, "DELETE", "/inventory/3/3", origin=unknown)
            checks.equal(
                status,
                403,
                "DELETE from an unknown origin is refused — THE ONE THIS CONTROL EXISTS "
                "FOR, because the route behind it destroys a record, a sidecar and a "
                "photograph with no backup (D10)",
            )
            checks.equal(error_code(body), "origin_not_allowed", "in the same code again")
            # READ WHILE THE RECORD IS STILL THERE, because the delete below takes it and
            # the photograph's name lives ON the record now (D172) — after the successful
            # DELETE there is nothing left to derive a path from.
            doomed = photo_of(3, 3)
            checks.ok(
                Store().read().inventory.get("3/3") is not None and doomed.is_file(),
                "and the card, its position and its photograph are all still there",
            )

            # --- the same verb from the capture app ------------------------------------
            status, _, _ = request(port, "DELETE", "/inventory/3/3", origin=allowed)
            checks.equal(
                status, 200, "the SAME DELETE from an allowed origin is served"
            )
            checks.ok(
                Store().read().inventory.get("3/3") is None and not doomed.is_file(),
                "and it really did the work — so the case above is the gate refusing, not "
                "the route failing for some other reason",
            )

            # --- no `Origin` at all -----------------------------------------------------
            status, body, _ = request(port, "POST", "/capture", payload=capture_payload(3))
            checks.equal(
                status,
                201,
                "A REQUEST WITH NO `Origin` STILL WRITES. `curl`, `./banchi` and this "
                "test send none, and a browser page cannot omit one — so requiring the "
                "header would kill every command-line path in this project at once while "
                "stopping nothing a page could do. Anything holding a shell here can open "
                "inventory.json with an editor anyway",
            )
            # `.get`, so a refused write is REPORTED by the line above rather than raising a
            # KeyError here that would hide every check behind it. Same rule as the label
            # read in `check_server_routes`: `Checks` exists to report every failure.
            checks.equal(
                json.loads(body or b"{}").get("key"),
                "3/3",
                "and it took the index the undo above released, which is the ordinary "
                "capture path running unchanged through the gate",
            )

            status, body, _ = request(
                port, "POST", "/capture", origin=second, payload=capture_payload(3)
            )
            checks.equal(
                status,
                201,
                "and the second spelling of this machine writes too — 127.0.0.1 and "
                "localhost are both in the default list for that reason",
            )

            # --- reads stay open --------------------------------------------------------
            status, _, headers = request(port, "GET", "/status", origin=unknown)
            checks.equal(status, 200, "GET is served to ANY origin — a read is not a write")
            status, _, headers = request(port, "GET", "/photo/3/1", origin=unknown)
            checks.equal(
                status,
                200,
                "including GET /photo, which D6's review queue and pull preview load as an "
                "`<img>` — and an `<img>` sends no Origin at all",
            )
            checks.equal(
                headers.get("Access-Control-Allow-Origin"),
                "*",
                "and it stays embeddable: an unknown origin is still answered `*` on the "
                "read side",
            )

            # --- the preflight ----------------------------------------------------------
            # The belt to the dispatcher's braces, and the half that produces a legible
            # console error rather than a 403 nobody sees: a browser told GET and OPTIONS
            # only never sends the DELETE at all.
            status, _, headers = request(port, "OPTIONS", "/inventory/3/1", origin=unknown)
            checks.equal(status, 204, "the preflight answers for any path, by design")
            checks.equal(
                headers.get("Access-Control-Allow-Methods"),
                ", ".join(capture_server.SAFE_METHODS),
                "and advertises GET and OPTIONS ONLY to an unknown origin, so the browser "
                "refuses the request that would have followed rather than sending it",
            )
            checks.equal(
                headers.get("Vary"),
                "Origin",
                "with Vary: Origin, because the answer now depends on a request header and "
                "a cache that did not know would hand one origin's answer to another",
            )

            status, _, headers = request(port, "OPTIONS", "/inventory/3/1", origin=allowed)
            checks.equal(
                headers.get("Access-Control-Allow-Methods"),
                ", ".join(capture_server.ALL_METHODS),
                "an ALLOWED origin is told every verb, including the three that write",
            )
            checks.equal(
                headers.get("Access-Control-Allow-Origin"),
                allowed,
                "and is ECHOED rather than answered `*` — `*` and credentials do not mix, "
                "and echoing is what makes the browser's own check agree with this server's",
            )
            status, _, headers = request(port, "OPTIONS", "/inventory/3/1")
            checks.equal(
                headers.get("Access-Control-Allow-Methods"),
                ", ".join(capture_server.ALL_METHODS),
                "and a preflight with no Origin is told every verb too, for the same reason "
                "the write above is served",
            )

            # --- the env var EXTENDS, and cannot re-open the door ------------------------
            lan = "http://the-mac.local:5173"
            with allowed_origins_env(f"  {lan.upper()}/  "):
                checks.equal(
                    sorted(capture_server.allowed_origins()),
                    sorted(capture_server.DEFAULT_ALLOWED_ORIGINS + (lan,)),
                    "BANCHI_ALLOWED_ORIGINS EXTENDS the defaults rather than replacing "
                    "them — rebuilding the whole list from an env var would let a typo "
                    "switch the protection off while looking like configuration. Case and "
                    "a trailing slash are folded, because that is what a human types",
                )
                status, _, _ = request(
                    port, "DELETE", "/inventory/3/4", origin=lan.upper() + "/"
                )
                checks.equal(
                    status,
                    200,
                    "the added origin can write, with no restart: the list is read on every "
                    "request, and a `make server` the owner started once is the reason",
                )
                status, _, _ = request(
                    port, "POST", "/capture", origin=allowed, payload=capture_payload(3)
                )
                checks.equal(
                    status,
                    201,
                    "and the DEFAULTS still write while it is set — extended, never replaced",
                )

            with allowed_origins_env("*"):
                checks.ok(
                    unknown not in capture_server.allowed_origins(),
                    "a `*` in the env var is one more literal string in an exact-match "
                    "list, never a wildcard — nothing at all becomes allowed by it",
                    f"allowed: {capture_server.allowed_origins()}",
                )
                status, body, _ = request(
                    port, "POST", "/capture", origin=unknown, payload=capture_payload(3)
                )
                checks.equal(
                    status,
                    403,
                    "AND `*` CANNOT RE-ENABLE THE HOLE. The list is compared by exact "
                    "string, so a wildcard is one more origin nobody is ever called — a "
                    "value that silently switched this control off is the one way the env "
                    "var could undo everything above it",
                )
                checks.equal(
                    error_code(body), "origin_not_allowed", "refused in the same code"
                )

            # THREE POSTs WERE SERVED AND TWO REFUSED, and two DELETEs were served against
            # three attempted. Asserted as the positions themselves rather than as a count,
            # because a count is the one shape that can come out right for the wrong reason.
            checks.equal(
                sorted(Store().read().inventory.cards),
                ["3/1", "3/2", "3/3", "3/4"],
                "and across the whole section the box holds exactly what the SERVED "
                "requests put there — every refusal above reached neither the allocator "
                "nor the disk",
            )
            checks.equal(
                Store().read().inventory.next_index(3),
                5,
                "with the high-water mark to match: a refused capture burns no index (D10)",
            )
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=10)

# ------------------------------------------------------------------------- command seams


def check_photo_cache(checks: Checks) -> None:
    """`GET /photo` is a conditional request, because its URL names a SLOT, not a card.

    THE DEFECT THIS EXISTS FOR WAS FOUND FROM THE FAR END, by the owner reporting that a
    mid-box delete on `#/inventory` "doesn't kick in super quickly ... it makes you think
    you need to delete more". Measured against a copy of their real store on 2026-08-29:
    the delete answered in 288 ms and the walk redrew in 500 ms, and the screen went on
    drawing the photograph of the deleted card over the facts of its replacement. Nothing
    was slow. The response carried no `ETag`, no `Last-Modified` and no `Cache-Control`, so
    the browser reused what it had for a URL whose bytes had moved underneath it.

    THE READING THAT MAKES IT DANGEROUS RATHER THAN UNTIDY: the operator sees the same
    picture at the same position label and presses again — and the second press aims at the
    card that slid in, which is a real capture with a real photograph, and is not refused,
    because the aim check is satisfied by the freshly re-read record.

    SOCKETS, NOT THE `do_*` FUNCTION, and for `check_origin_gate`'s exact reason: the whole
    behaviour is a request header, a status code and two response headers, none of which an
    in-process call has. The in-process case up in `check_store` asserts only that a
    validator comes back at all.

    THE PHOTOS CARRY DISTINGUISHABLE BYTES, `check_remove_and_delete`'s rule, and here it is
    the entire assertion: "the browser is told the bytes changed" is only worth checking if
    the test can tell two photographs apart.
    """
    checks.note("")
    checks.note("GET /photo — the validator that survives a renumber")

    def blob(i: int) -> str:
        return base64.b64encode(b"\xff\xd8\xff" + bytes([i]) * 64).decode("ascii")

    with isolated_home():
        for i in (1, 2):
            capture_server.do_capture(
                {"box": 3, "capture_id": f"p{i}", "image": blob(i), "set_hint": "sv9"}
            )
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = _spawn_server(httpd)
        try:
            status, body, headers = request(port, "GET", "/photo/3/1")
            first = headers.get("ETag")
            checks.equal(status, 200, "a photo answers 200 with its bytes")
            checks.equal(
                body, b"\xff\xd8\xff" + bytes([1]) * 64, "and the bytes are card 1's"
            )
            checks.ok(
                first is not None and first.startswith('"') and first.endswith('"'),
                "and a quoted strong ETag — without one a browser has nothing to ask about "
                "and reuses a slot's previous occupant",
            )
            checks.equal(
                headers.get("Cache-Control"),
                "no-cache",
                "`no-cache` and not `no-store`: keep the bytes, ask before reusing them. "
                "`no-store` would re-send 1.9 MB per arrow key on the Fulfiller's LAN",
            )

            status, body, _ = request(
                port, "GET", "/photo/3/1", extra_headers={"If-None-Match": first}
            )
            checks.equal(status, 304, "an unchanged photo revalidates to 304")
            checks.equal(body, b"", "and carries no body — that is what makes it cheap")

            status, _, _ = request(
                port, "GET", "/photo/3/1", extra_headers={"If-None-Match": f"W/{first}"}
            )
            checks.equal(
                status, 304, "the comparison is weak, as RFC 9110 requires of If-None-Match"
            )
            status, _, _ = request(
                port, "GET", "/photo/3/1", extra_headers={"If-None-Match": "*"}
            )
            checks.equal(status, 304, "and `*` matches any existing resource, not a tag")

            status, body, _ = request(
                port, "GET", "/photo/3/1", extra_headers={"If-None-Match": '"stale"'}
            )
            checks.equal(status, 200, "a tag we never issued gets the bytes")
            checks.equal(len(body), 67, "all of them")

            # ------------------------------------------------------ the renumber itself
            # D10 ruling 1: deleting card 1 slides card 2 down into slot 1. The URL does not
            # change and its bytes do, which is the whole case.
            capture_server.do_remove_card(3, 1, {"capture_id": "p1"})

            status, body, headers = request(
                port, "GET", "/photo/3/1", extra_headers={"If-None-Match": first}
            )
            checks.equal(
                status,
                200,
                "AFTER THE SHIFT THE SAME URL WITH THE SAME TAG ANSWERS 200, NOT 304 — the "
                "browser is told the slot's occupant changed, which is the defect",
            )
            checks.equal(
                body,
                b"\xff\xd8\xff" + bytes([2]) * 64,
                "and the bytes are card 2's, which slid down into slot 1",
            )
            checks.ok(
                headers.get("ETag") not in (None, first),
                "under a new ETag, so the next request revalidates against the right "
                "photograph rather than the one that was deleted",
            )
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    # -------------------------------------- by-card: versioned, 304 without a read, re-shoot
    # `?v=<capture_id>` versions the address. A matching revalidation is a 304 that never READS
    # the file. A D26 re-shoot writes new bytes under the SAME cid, and the new version must
    # get the new bytes, with the OLD tag answered 200. No version means `no-cache` over a
    # content digest, never `immutable`.
    with isolated_home():
        capture_server.do_capture(
            {"box": 3, "capture_id": "q1", "image": blob(9), "set_hint": "sv9"}
        )
        cid = next(iter(Store().read().inventory.cards.values())).cid
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = _spawn_server(httpd)
        reads: List[str] = []
        real = Path.read_bytes

        def counting(self: Path) -> bytes:
            if cid[:16] in str(self):
                reads.append(str(self))
            return real(self)

        url = f"/photo/by-card/{cid}"
        try:
            with mock.patch.object(Path, "read_bytes", counting):
                status, body, headers = request(port, "GET", f"{url}?v=q1")
                checks.equal(status, 200, "by-card with a version answers 200 with the bytes")
                checks.ok(
                    "immutable" in (headers.get("Cache-Control") or ""),
                    "and is immutable, because the URL names the version",
                )
                old_tag = headers.get("ETag")
                reads.clear()
                status, body, headers = request(
                    port, "GET", f"{url}?v=q1", extra_headers={"If-None-Match": old_tag}
                )
                checks.equal(status, 304, "a matching If-None-Match answers 304")
                checks.equal(body, b"", "with no body")
                checks.equal(reads, [], "and the 304 never READ the photograph")
                checks.equal(
                    (headers.get("Connection") or "").lower(),
                    "close",
                    "and still says Connection: close (DEBT11: a kept socket holds a worker)",
                )
                reshot = b"\xff\xd8\xff" + bytes([77]) * 64
                capture_server.do_reshoot(
                    3, 1, {"capture_id": "q2", "image": base64.b64encode(reshot).decode("ascii")}
                )
                status, body, headers = request(
                    port, "GET", f"{url}?v=q2", extra_headers={"If-None-Match": old_tag}
                )
                checks.equal(
                    status, 200, "AFTER A RE-SHOOT THE OLD TAG ON THE NEW VERSION IS 200, NOT 304"
                )
                checks.equal(body, reshot, "and the bytes are the new photograph's")
                checks.ok(headers.get("ETag") not in (None, old_tag), "under a new ETag")
                status, body, headers = request(port, "GET", url)
                checks.equal(body, reshot, "an unversioned request gets the current bytes")
                checks.equal(
                    headers.get("Cache-Control"),
                    "no-cache",
                    "and is never immutable: it cannot say which version it means",
                )
                status, _, _ = request(
                    port, "GET", url, extra_headers={"If-None-Match": headers.get("ETag")}
                )
                checks.equal(status, 304, "its digest tag still revalidates to 304")
                # The id is the version in `?v=`: new bytes under the card's CURRENT id would
                # sit behind an immutable URL for a year. Same bytes stay an idempotent replay.
                caught = checks.raises(
                    capture_server.BadRequest,
                    lambda: capture_server.do_reshoot(
                        3,
                        1,
                        {
                            "capture_id": "q2",
                            "image": base64.b64encode(b"\xff\xd8\xff" + bytes([88]) * 64).decode(
                                "ascii"
                            ),
                        },
                    ),
                    "a re-shoot with the card's CURRENT capture_id and different bytes refuses",
                )
                if caught is not None:
                    checks.equal(
                        getattr(caught, "code", None), "capture_id_in_use", "in its own code"
                    )
                capture_server.do_reshoot(
                    3, 1, {"capture_id": "q2", "image": base64.b64encode(reshot).decode("ascii")}
                )
                checks.equal(
                    request(port, "GET", f"{url}?v=q2")[1],
                    reshot,
                    "and the same bytes replay cleanly",
                )
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)


def check_app_serve(checks: Checks) -> None:
    """The capture server hands out the built app, and does not stop being an API (D138).

    WHAT THIS IS GUARDING IS NOT "can Python send a file". It is the seam: a static serve
    bolted onto an API is one ordering mistake away from shadowing a route, and one missing
    `resolve()` away from serving the store. Both are asserted here against a real socket,
    because both are properties of the dispatch order and the filesystem rather than of any
    function called on its own.

    THE ROUTES ARE THE FIRST ASSERTION AND THE LOUDEST. `app_claims` is narrow — the root,
    or a final segment whose extension `vite build` emits — precisely so that every JSON
    refusal in this server survives the app moving in beside it. The catch-all an SPA host
    would normally use was written, measured against this file, and withdrawn: it turned
    `GET /boxes/abc` into 200 HTML and would have made a dozen named refusals unreachable
    with nothing failing.

    THE BUILD IS A STUB, NOT A `vite build`. The point is the server, and a real bundle
    would make this test depend on Node, on the app compiling, and on ~1.7 MB of output
    whose bytes say nothing about the seam. Four files with known extensions is the whole
    surface the server has an opinion about.
    """
    checks.note("")
    checks.note("GET / — the built app, served beside the API (D138)")

    original = capture_server.APP_DIST
    with tempfile.TemporaryDirectory() as tmp:
        dist = Path(tmp) / "dist"
        (dist / "assets").mkdir(parents=True)
        (dist / "index.html").write_text("<!doctype html><title>Banchi</title>", "utf-8")
        (dist / "assets" / "main-a1b2c3.js").write_text("export const x = 1\n", "utf-8")
        (dist / "assets" / "main-a1b2c3.css").write_text(":root{--bn-ink:#000}\n", "utf-8")
        (dist / "manifest.webmanifest").write_text('{"id": "/"}', "utf-8")
        # The escape a `..` check alone does not catch: a symlink INSIDE the build pointing
        # out of it satisfies every string test and resolves somewhere else entirely.
        secret = Path(tmp) / "outside.json"
        secret.write_text('{"secret": true}', "utf-8")
        with contextlib.suppress(OSError, NotImplementedError):
            (dist / "escape.json").symlink_to(secret)

        capture_server.APP_DIST = dist
        with isolated_home():
            httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
            port = httpd.server_address[1]
            thread = _spawn_server(httpd)
            try:
                status, body, headers = request(port, "GET", "/")
                checks.equal(status, 200, "`GET /` answers with the app")
                checks.ok(b"<!doctype html>" in body, "and the bytes are index.html's")
                checks.equal(
                    headers.get("Content-Type"),
                    "text/html; charset=utf-8",
                    "as HTML, from this server's own eight-entry map rather than from "
                    "whichever `/etc/mime.types` the machine happens to have",
                )
                checks.equal(
                    headers.get("Cache-Control"),
                    "no-store",
                    "and NEVER cached: `index.html` keeps its name while its bytes move on "
                    "every build, so a held copy asks for assets the swap has deleted",
                )

                status, body, headers = request(port, "GET", "/assets/main-a1b2c3.js")
                checks.equal(status, 200, "a hashed asset answers with its bytes")
                checks.equal(body, b"export const x = 1\n", "all of them")
                checks.equal(
                    headers.get("Content-Type"),
                    "text/javascript; charset=utf-8",
                    "under the type a browser will execute",
                )
                checks.equal(
                    headers.get("Cache-Control"),
                    capture_server.APP_IMMUTABLE,
                    "held forever, which is safe for exactly the files whose NAME changes "
                    "when their bytes do",
                )

                status, _, headers = request(port, "GET", "/manifest.webmanifest")
                checks.equal(status, 200, "the dock app's manifest is served (D108)")
                checks.equal(
                    headers.get("Content-Type"),
                    "application/manifest+json",
                    "under the type that makes it installable — the one extension macOS's "
                    "own mime table does not know at all",
                )

                # ------------------------------------------------------------------ HEAD
                # THE HEADERS OF THE GET, WITH NO BODY. `BaseHTTPRequestHandler` dispatches
                # on the method name and this class defined no `do_HEAD`, so until it did
                # `curl -I http://localhost:8000/` answered 501 — invisible while this
                # process was an API nothing HEADs, and the first thing a monitor, a link
                # checker or a proxy asks the moment the app is served from the same port.
                #
                # EQUALITY WITH THE GET IS THE ASSERTION, rather than a second list of the
                # headers this test expects. RFC 9110 asks for the GET's own header field
                # values, and a list written out here is exactly what stops being true the
                # day `_send` gains a header — which is the drift `do_HEAD` is a flag rather
                # than a second header block to avoid. `Date` is dropped because it is the
                # one header that legitimately differs between two requests.
                def without_date(headers):
                    return {
                        key: value
                        for key, value in headers.items()
                        if key.lower() != "date"
                    }

                for path in ("/", "/assets/main-a1b2c3.js", "/manifest.webmanifest"):
                    _, got_body, got_headers = request(port, "GET", path)
                    status, _, headers = request(port, "HEAD", path)
                    checks.equal(status, 200, f"`HEAD {path}` answers 200 and not 501")
                    checks.equal(
                        without_date(headers),
                        without_date(got_headers),
                        "under the GET's own headers, every one of them — the boot header, "
                        "the CORS block and `Connection: close` included",
                    )
                    checks.equal(
                        headers.get("Content-Length"),
                        str(len(got_body)),
                        "with `Content-Length` the length the body WOULD have had, which is "
                        "the one header a HEAD is usually sent to read",
                    )
                    # OVER A BARE SOCKET, BECAUSE `urllib` CANNOT SEE THIS. `raw_head` carries
                    # the measurement: the client discards a HEAD body without reading it, so
                    # asserting `response.read() == b""` passes against a server that wrote
                    # every byte. Mutation-tested — this is the only arm here that fails when
                    # `_send`'s suppression is removed.
                    _, rest = raw_head(port, path)
                    checks.equal(
                        rest, b"", f"and nothing follows the headers on the wire for {path}"
                    )

                # The two named in the ask, asserted on their own so a failure says which is
                # wrong rather than only that the dicts differ.
                _, _, headers = request(port, "HEAD", "/")
                checks.equal(
                    headers.get("Content-Type"),
                    "text/html; charset=utf-8",
                    "`HEAD /` carries the app's own Content-Type",
                )
                checks.equal(
                    headers.get("Cache-Control"),
                    "no-store",
                    "and its `no-store`, so a proxy that decides on a HEAD decides the same "
                    "way the GET would have made it decide",
                )
                _, _, headers = request(port, "HEAD", "/assets/main-a1b2c3.js")
                checks.equal(
                    headers.get("Cache-Control"),
                    capture_server.APP_IMMUTABLE,
                    "and a hashed asset carries the immutable one under HEAD too",
                )

                # HEAD REACHES EVERY GET ROUTE AND NOT ONLY THE APP, which is `do_HEAD`'s own
                # recorded decision and the half a narrow implementation would have got
                # wrong: `/status` is the likeliest thing of all to have a monitor pointed at
                # it, and a 405 there would reproduce the 501 one route over.
                status, _, headers = request(port, "HEAD", "/status")
                checks.equal(status, 200, "`HEAD /status` answers, because HEAD is not the "
                             "app's private verb")
                _, rest = raw_head(port, "/status")
                checks.equal(rest, b"", "with the JSON withheld on the wire")
                checks.ok(
                    int(headers.get("Content-Length") or 0) > 0,
                    "and a Content-Length describing the JSON it withheld",
                )

                # A REFUSAL IS STILL A REFUSAL UNDER HEAD, headers and status intact and the
                # sentence withheld. Worth its own arm because `_dispatch` answers a refusal
                # through `_fail` -> `_json` -> `_send`, which is the same suppression point
                # by a different road.
                status, _, headers = request(port, "HEAD", "/statuss")
                checks.equal(status, 404, "`HEAD` on a mistyped route is still 404")
                head, rest = raw_head(port, "/statuss")
                checks.equal(rest, b"", "with the refusal's JSON withheld on the wire")
                checks.ok(
                    b"Content-Length: " in head,
                    "and a Content-Length still describing it — a refusal is a response "
                    "like any other and HEAD withholds only its body",
                )

                # THE ORIGIN GATE IS NOT WEAKENED BY HEAD BEING SAFE. A read is open to any
                # origin and a write is not, and `SAFE_METHODS` gaining HEAD must not have
                # moved the second half — the whole gate is one `in` against that tuple.
                checks.ok(
                    "HEAD" in capture_server.SAFE_METHODS
                    and "POST" not in capture_server.SAFE_METHODS
                    and "PUT" not in capture_server.SAFE_METHODS
                    and "DELETE" not in capture_server.SAFE_METHODS,
                    "HEAD is a safe method and the three mutating verbs still are not",
                    f"safe methods: {capture_server.SAFE_METHODS}",
                )
                status, body, _ = request(
                    port, "POST", "/", payload={}, origin="http://evil.example"
                )
                checks.equal(
                    error_code(body),
                    "origin_not_allowed",
                    "and a foreign origin's write is still refused before anything is read",
                )

                # ------------------------------------------------- the API is still the API
                status, body, _ = request(port, "GET", "/status")
                checks.equal(status, 200, "`GET /status` is untouched")
                status, body, _ = request(port, "GET", "/boxes/abc")
                checks.equal(status, 404, "AND SO IS EVERY REFUSAL: a non-numeric box is 404")
                checks.equal(
                    error_code(body),
                    "no_such_route",
                    "with the code that names what was wrong — a catch-all `index.html` "
                    "fallback would have answered 200 HTML here and silently retired a "
                    "dozen refusals in this file",
                )
                status, body, _ = request(port, "GET", "/statuss")
                checks.equal(
                    error_code(body), "no_such_route", "a mistyped route is still JSON"
                )

                # ------------------------------------------------------------ the traversals
                for attempt in ("/../outside.json", "/assets/../../outside.json"):
                    status, body, _ = request(port, "GET", attempt)
                    checks.ok(
                        status == 404 and b"secret" not in body,
                        f"`GET {attempt}` reads nothing outside the build",
                    )
                if (dist / "escape.json").is_symlink():
                    status, body, _ = request(port, "GET", "/escape.json")
                    checks.ok(
                        status == 404 and b"secret" not in body,
                        "and a SYMLINK out of the build is refused too — the string check "
                        "passes it and only the resolved path catches it",
                    )
                status, body, _ = request(port, "GET", "/assets/gone-9z9z9z.js")
                checks.equal(
                    error_code(body),
                    "no_such_file",
                    "a named file the build does not have is 404 and not HTML — a browser "
                    "asked for `.js` and given a page reports a syntax error instead",
                )

                # ------------------------------------------------------------ read-only
                status, body, _ = request(port, "POST", "/", payload={})
                checks.equal(status, 405, "`POST /` is a method error")
                checks.equal(
                    error_code(body),
                    "method_not_allowed",
                    "not `no_such_route`: the resource is there, the verb is wrong",
                )

                # ------------------------------------------------------ with nothing built
                capture_server.APP_DIST = Path(tmp) / "never-built"
                status, body, _ = request(port, "GET", "/")
                checks.equal(status, 503, "with no build, `GET /` is 503 and not 404")
                checks.equal(
                    error_code(body),
                    "app_not_built",
                    "naming the state rather than the address — the app is not missing, it "
                    "is not ready, and the supervisor is what makes it ready",
                )
                status, _, _ = request(port, "GET", "/status")
                checks.equal(
                    status,
                    200,
                    "AND THE API IS STILL UP: a TypeScript file that will not compile may "
                    "never stop this server handing out cards",
                )
                status, _, headers = request(port, "HEAD", "/")
                checks.equal(
                    status,
                    503,
                    "`HEAD /` is 503 with no build too — a monitor asking the cheap way "
                    "must not be told the app is fine while the GET says it is not ready",
                )
                _, rest = raw_head(port, "/")
                checks.equal(rest, b"", "with the refusal's sentence withheld, as HEAD asks")
                checks.ok(
                    int(headers.get("Content-Length") or 0) > 0,
                    "and its `Content-Length` still describing that sentence",
                )
                status, body, _ = request(port, "POST", "/", payload={})
                checks.equal(
                    error_code(body),
                    "no_such_route",
                    "and with nothing built, a write to `/` is 404 again — 405 would be a "
                    "claim about a resource that is not there",
                )
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(timeout=5)
    capture_server.APP_DIST = original


def check_dual_stack_bind(checks: Checks) -> None:
    """The 2026-09-23 incident, proved and closed (D43).

    MEASURED ON THE OWNER'S MAC: an IPv4 `0.0.0.0` bind and a LATER IPv6 `::` bind (with
    `IPV6_V6ONLY` cleared) both succeed on the same port — two unrelated processes, one per
    family. A stray `python3 -m http.server 8000` took the IPv6 half while the capture
    server already held the IPv4 half, and macOS resolves `localhost` to `::1` first, so
    `http://localhost:8000` silently 404'd every route while `127.0.0.1:8000` still worked.

    `capture_server._capture_server()` closes this by binding `::` itself, dual-stack, so
    ONE socket answers both families and there is no second family left for a stray process
    to take. This proves the closed door rather than the open one: after this server binds,
    both a later `::` dual-stack bind AND a later plain `0.0.0.0` bind on the same port must
    be refused. Bind IPv4-only here (revert `_capture_server` to the old
    `CaptureServer((host, port), ...)` with no `::` branch) and the `0.0.0.0`-refusal
    assertion goes red — the IPv6 half is free again and the split is back.
    """
    checks.note("")
    checks.note("dual-stack bind — the port split behind the 2026-09-23 incident (D43)")

    httpd, host = capture_server._capture_server("::", 0)
    try:
        checks.equal(host, "::", "binds IPv6 dual-stack by default")

        reached = False
        with contextlib.suppress(OSError), \
                socket.create_connection(("127.0.0.1", httpd.server_address[1]), timeout=1):
            reached = True
        checks.ok(reached, "an IPv4 client (127.0.0.1) reaches the same socket")

        port = httpd.server_address[1]
        refused_v6 = False
        try:
            second = capture_server._DualStackCaptureServer(("::", port), capture_server.CaptureHandler)
            second.server_close()
        except OSError as exc:
            refused_v6 = exc.errno == errno.EADDRINUSE
        checks.ok(
            refused_v6,
            "a SECOND `::` dual-stack bind on the same port is refused, not merely slow",
        )

        refused_v4 = False
        try:
            third = capture_server.CaptureServer(("0.0.0.0", port), capture_server.CaptureHandler)
            third.server_close()
        except OSError as exc:
            refused_v4 = exc.errno == errno.EADDRINUSE
        checks.ok(
            refused_v4,
            "and a plain `0.0.0.0` bind on the same port is ALSO refused — the split the "
            "incident measured cannot recur",
        )
    finally:
        httpd.server_close()


CHECKS = (
    check_concurrency,
    check_origin_gate,
    check_photo_cache,
    check_app_serve,
    check_dual_stack_bind,
)
