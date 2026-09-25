#!/usr/bin/env python3
"""ONE SLOT PER CHECKOUT ON THIS MACHINE, CLAIMED ONCE AND KEPT
(D261).

D43 promised "every checkout has its own ports" and delivered a hash of the path into 300
slots. Measured 2026-09-24: 44 folders under `.claude/worktrees/` on this Mac. The chance
that two of n paths share a slot out of 300 is about 87% at 35 and 96% at 44 (the birthday
bound). Two of them did: `jovial-banach-362f31`
and `agent-a591036a4885f7533` both derived dev port 5218. A design-check in one reused the
other's Vite and passed.

A hash has no memory of who already holds a slot. This file is that memory. `claim` records
this checkout's slot in one machine-wide file, `~/.pkmnscan/port-slots.json`
(`PKMNSCAN_SLOT_REGISTRY` overrides). `server/ports.py:slot_for` and `app/devPort.ts:slotFor`
READ it before the hash. Nothing else writes it.

HOW A SLOT IS CHOSEN, under one `flock`:
  1. Entries whose path is no longer a directory are dropped. A removed worktree frees its
     slot the next time anyone claims.
  2. A checkout that already holds a slot keeps it. Once claimed, the answer never moves,
     which is what D43 wanted from "derived, not allocated".
  3. Otherwise it starts at its own hash slot, so a tree whose slot was never contested keeps
     the port it always had. It steps forward past a slot that another checkout has claimed,
     or whose dev or capture port some other checkout's server is holding right now. A port
     held by THIS checkout's own server (its Vite names this checkout at `/__checkout`, or the
     listener's working directory is inside this checkout) does not count against it.

WHAT IT NEVER DOES: kill, signal or connect to anything beyond a one-second probe, and write
anywhere but the registry and its lock. The primary checkout claims nothing: it keeps 8000
and 5173.

A DAMAGED REGISTRY IS KEPT, NEVER SILENTLY LOST. A reader reads it as nothing claimed. A
claim that must write over it first copies it to `port-slots.json.bad-<stamp>` and prints
that every claim it held is gone.

A CLAIM THAT CANNOT BE MADE FAILS OPEN, LOUDLY. The derivation then answers the hash, as it
did before this file existed, and `app/checkoutIdentity.ts` still refuses a test run against
a server that is not this checkout's. So `make dev` never fails because of this file.

`selftest` builds two throwaway trees forced into one slot and proves both halves of the
decision end to end: a real Playwright run in one tree refuses the other tree's real Vite,
and after both claim, each has its own slot and the same run passes against its own server.
It also proves that `.claude/launch.json`, which the Browser pane opens, names the claimed
port and not the hash port, for both of the file's writers.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server import ports  # noqa: E402

IDENTITY_PATH = "/__checkout"  # `app/checkoutIdentity.ts:IDENTITY_PATH`, read by the self-test.


# ------------------------------------------------------------------------------ the probes


def port_held(port: int) -> bool:
    """Is anything listening on this port, on either loopback family?"""
    for family, host in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        try:
            with socket.socket(family, socket.SOCK_STREAM) as sock:
                sock.settimeout(1.0)
                if sock.connect_ex((host, port)) == 0:
                    return True
        except OSError:
            continue
    return False


def served_checkout(port: int) -> Optional[str]:
    """The checkout a Vite on this port names at `/__checkout`, or None when it names none."""
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}{IDENTITY_PATH}", headers={"Accept": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=1.0) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError):
        return None
    served = body.get("checkout") if isinstance(body, dict) else None
    return served if isinstance(served, str) else None


def listener_cwds(port: int) -> list:
    """The working directory of every process listening on this port. Read-only `lsof`.

    Empty when `lsof` is missing or answers nothing, and then the holder is unknown.
    """
    try:
        pids = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True, text=True, timeout=5, check=False,
        ).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return []
    cwds = []
    for pid in pids:
        try:
            out = subprocess.run(
                ["lsof", "-a", "-p", pid, "-d", "cwd", "-Fn"],
                capture_output=True, text=True, timeout=5, check=False,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        cwds += [line[1:] for line in out.splitlines() if line.startswith("n")]
    return cwds


def _inside(path: str, root: str) -> bool:
    """Is `path` in the checkout at `root`, and not in another checkout nested inside it?

    A linked worktree can sit inside another checkout's folder (`.claude/worktrees/<name>`).
    It is another checkout with its own ports, as `scripts/reap.py:linked_worktrees` rules. So
    a directory between `path` and `root` that holds a `.git` ends the answer: not inside.
    """
    real = os.path.realpath(path)
    if not (real == root or real.startswith(root.rstrip("/") + "/")):
        return False
    here = real
    while len(here) > len(root.rstrip("/")):
        if os.path.lexists(os.path.join(here, ".git")):
            return False
        here = os.path.dirname(here)
    return True


def held_by_other(port: int, root: str) -> Optional[str]:
    """None when the port is free or this checkout's own. Else a sentence naming the holder."""
    if not port_held(port):
        return None
    served = served_checkout(port)
    if served is not None:
        return None if served == root else f"a server for {served}"
    cwds = listener_cwds(port)
    if cwds and all(_inside(cwd, root) for cwd in cwds):
        return None
    if cwds:
        return "a process in " + ", ".join(sorted(set(cwds)))
    return "a process this script cannot name"


# ---------------------------------------------------------------------------- the registry


def registry_path() -> Path:
    path = ports.slot_registry()
    if path is None:
        raise RuntimeError("there is no home directory, so there is no machine-wide registry")
    return path


@contextmanager
def locked(registry: Path) -> Iterator[None]:
    registry.parent.mkdir(parents=True, exist_ok=True)
    with open(registry.with_name(registry.name + ".lock"), "a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield


def write_claims(registry: Path, claims: dict) -> None:
    """Replace the file whole, through a rename, so a reader never sees half of it."""
    payload = json.dumps({"version": 1, "slots": dict(sorted(claims.items()))}, indent=2)
    handle, temp = tempfile.mkstemp(prefix=".port-slots.", dir=str(registry.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write(payload + "\n")
        os.replace(temp, registry)
    except BaseException:
        if os.path.exists(temp):
            os.unlink(temp)
        raise


def damage(registry: Path) -> Optional[str]:
    """None when the file is absent or every entry in it reads. Else what is wrong with it.

    `ports.read_claims` reads a damaged file as "nothing claimed", which is right for a
    reader. A WRITER that trusted that answer would replace the file and lose every other
    checkout's claim with no word. So the writer asks this first.
    """
    try:
        text = registry.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        return f"could not be read ({exc})"
    try:
        data = json.loads(text, parse_constant=ports.refuse_json_constant)
    except ValueError:
        return "is not JSON"
    slots = data.get("slots") if isinstance(data, dict) else None
    if not isinstance(slots, dict):
        return "has no table of slots"
    unread = len(slots) - len(ports.read_claims(registry))
    if unread:
        return f"has {unread} entry(ies) that are not a whole slot in the band"
    return None


def replace(registry: Path, claims: dict, damaged: Optional[str]) -> str:
    """Write the claims. Over a damaged file, keep a copy of it first. Returns a note."""
    note = ""
    if damaged:
        stamp = time.strftime("%Y%m%dT%H%M%S") + f"-{os.getpid()}"
        kept = registry.with_name(f"{registry.name}.bad-{stamp}")
        shutil.copy2(registry, kept)
        note = (f"; the registry {damaged}, so it was REPLACED, and any claim it held is "
                f"lost. The old file is kept at {kept}")
    write_claims(registry, claims)
    return note


def claim(
    root: Path,
    registry: Path,
    other_holder: Callable[[int, str], Optional[str]] = held_by_other,
) -> tuple:
    """Claim a slot for `root`. Returns (slot or None, what happened, in one sentence)."""
    key = ports.canonical(root)
    with locked(registry):
        damaged = damage(registry)
        before = ports.read_claims(registry)
        live = {path: slot for path, slot in before.items() if os.path.isdir(path)}
        dropped = sorted(set(before) - set(live))
        note = f"; dropped {len(dropped)} removed checkout(s)" if dropped else ""
        if key in live:
            if dropped:
                note += replace(registry, live, damaged)
            return live[key], f"kept slot {live[key]}{note}"
        taken = set(live.values())
        start = ports.hashed_slot(root)
        skipped = []
        for step in range(ports.SLOTS):
            slot = (start + step) % ports.SLOTS
            if slot in taken:
                skipped.append(f"slot {slot} is claimed by another checkout")
                continue
            holder = next(
                (
                    f"port {port} is held by {who}"
                    for port in (ports.DEV_LOW + slot, ports.CAPTURE_LOW + slot)
                    for who in [other_holder(port, key)]
                    if who
                ),
                None,
            )
            if holder:
                skipped.append(holder)
                continue
            live[key] = slot
            note += replace(registry, live, damaged)
            why = f" ({skipped[0]})" if skipped else ""
            return slot, f"claimed slot {slot}, hash slot {start}{why}{note}"
        return None, "no free slot among all " + str(ports.SLOTS)


def cmd_claim(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else ports.REPO_ROOT
    if ports.is_primary_checkout(root):
        if not args.quiet:
            print("port-slots: the primary checkout keeps 8000 and 5173 and claims no slot.")
        return 0
    try:
        slot, what = claim(root, registry_path())
    except (OSError, RuntimeError) as exc:
        print(f"port-slots: claim SKIPPED ({exc}). The ports fall back to the path hash, "
              f"and a test run still refuses a server that is not this checkout's.")
        return 0
    if slot is None:
        print(f"port-slots: claim FAILED, {what}. The ports fall back to the path hash.")
        return 0
    if not (args.quiet and what == f"kept slot {slot}"):
        print(f"port-slots: {what}. This checkout serves dev {ports.DEV_LOW + slot}, "
              f"capture {ports.CAPTURE_LOW + slot}.")
    return 0


def cmd_show(_args: argparse.Namespace) -> int:
    registry = registry_path()
    claims = ports.read_claims(registry)
    print(f"port-slots: {len(claims)} claimed in {registry}")
    for path, slot in sorted(claims.items(), key=lambda item: item[1]):
        state = "" if os.path.isdir(path) else "  (removed; freed on the next claim)"
        print(f"  slot {slot:3d}  dev {ports.DEV_LOW + slot}  capture "
              f"{ports.CAPTURE_LOW + slot}  {path}{state}")
    return 0


# ------------------------------------------------------------------------------ the selftest

APP_FILES = ("devPort.ts", "checkoutIdentity.ts", "vite.config.ts", "playwright.config.ts",
             "design-check-reporter.ts",
             "package.json")
PROBE_SPEC = (
    "import { test, expect } from '@playwright/test'\n"
    "test('the run reached a test', () => { expect(1).toBe(1) })\n"
)


def build_tree(tree: Path) -> None:
    """A throwaway linked-worktree-shaped checkout: the real configs, a real Vite, no source.

    `node_modules` is a real directory of symlinks, one per package, so Vite's own caches
    land in the throwaway tree and never in this checkout's install.
    """
    app = tree / "app"
    (app / "tests").mkdir(parents=True)
    (tree / ".git").write_text("gitdir: /nowhere/.git/worktrees/probe\n", encoding="utf-8")
    for name in APP_FILES:
        shutil.copy2(ROOT / "app" / name, app / name)
    (app / "index.html").write_text("<!doctype html><title>probe</title>\n", encoding="utf-8")
    for rel in ("scripts/screenshot.sh", "server/ports.py"):
        (tree / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, tree / rel)
    (app / "tests" / "identity-probe.spec.ts").write_text(PROBE_SPEC, encoding="utf-8")
    modules = app / "node_modules"
    modules.mkdir()
    for entry in (ROOT / "app" / "node_modules").iterdir():
        if entry.name in (".vite", ".vite-temp", ".cache"):
            continue
        (modules / entry.name).symlink_to(entry)


def start_vite(tree: Path, env: dict) -> subprocess.Popen:
    """Start the tree's own Vite and return once it says where it listens."""
    proc = subprocess.Popen(
        [str(tree / "app" / "node_modules" / ".bin" / "vite")],
        cwd=str(tree / "app"), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, start_new_session=True,
    )
    ready = threading.Event()
    lines: list = []

    def read() -> None:
        for line in proc.stdout:
            lines.append(line)
            if "Local:" in line:
                ready.set()
        ready.set()

    threading.Thread(target=read, daemon=True).start()
    if not ready.wait(60) or proc.poll() is not None:
        stop(proc)
        raise SystemExit("port-slots selftest: the throwaway Vite did not start — unproven:\n"
                         + "".join(lines[-20:]))
    return proc


def stop(proc: subprocess.Popen) -> None:
    """Stop a process group THIS self-test started, and nothing else."""
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, 15)
            proc.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            os.killpg(proc.pid, 9)
            proc.wait(timeout=10)


def run_playwright(tree: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(tree / "app" / "node_modules" / ".bin" / "playwright"), "test",
         "--reporter=line", "tests/identity-probe.spec.ts"],
        cwd=str(tree / "app"), env=env, capture_output=True, text=True, timeout=180,
        check=False,
    )


def run_screenshot(tree: Path, env: dict, port: int) -> str:
    """The tree's copy of `scripts/screenshot.sh` over its own dev origin. Its stderr.

    The tree has no `scripts/screenshot.mjs`, so a render that is not refused stops there and
    loads no page.
    """
    done = subprocess.run(
        ["bash", "scripts/screenshot.sh", f"http://localhost:{port}/", "identity-probe"],
        cwd=str(tree), env=env, capture_output=True, text=True, timeout=60, check=False,
    )
    return done.stdout + done.stderr


def node_ports(tree: Path, env: dict) -> tuple:
    """(DEV_PORT, CAPTURE_PORT) the tree's own copy of `app/devPort.ts` answers."""
    done = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e",
         "const m = await import(%s); console.log(JSON.stringify([m.DEV_PORT, m.CAPTURE_PORT]))"
         % json.dumps((tree / "app" / "devPort.ts").as_uri())],
        cwd=str(tree), env=env, capture_output=True, text=True, check=False,
    )
    if done.returncode != 0:
        raise SystemExit("port-slots selftest: node could not read devPort.ts — unproven:\n"
                         + done.stderr.strip())
    return tuple(json.loads(done.stdout.strip().splitlines()[-1]))


def launch_config_failures(base: Path, registry: Path, env: dict) -> list:
    """`.claude/launch.json` must name the CLAIMED port, whoever writes it first.

    The Browser pane opens the port that file names, and it reuses a server already there. So
    a file written from the hash, before the claim moved the tree, previews ANOTHER tree.
    Each throwaway tree gets the real `launch-config.py`, this script and `server/ports.py`.
    The registry already gives the tree's hash slot to another checkout. Each tree then runs
    one caller's call (the SessionStart hook's, and `make launch-config`'s), then the claim
    every serving target makes next, then the read-only check `make status` makes. The check
    must say `current`, at the claimed port.
    """
    failures = []
    holder = base / "launch-holder"
    holder.mkdir()
    for label, flags in (("the SessionStart hook", ["--if-needed", "--quiet"]),
                         ("make launch-config", [])):
        tree = base / ("launch-" + ("hook" if flags else "make"))
        for sub in ("scripts", "server"):
            (tree / sub).mkdir(parents=True)
        (tree / ".git").write_text("gitdir: /nowhere/.git/worktrees/launch\n", encoding="utf-8")
        for rel in ("scripts/launch-config.py", "scripts/port-slots.py", "server/ports.py"):
            shutil.copy2(ROOT / rel, tree / rel)
        hashed = ports.hashed_slot(tree)
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(json.dumps({"version": 1, "slots": {str(holder): hashed}}),
                            encoding="utf-8")

        def run(*args: str, tree: Path = tree) -> str:
            done = subprocess.run([sys.executable, *args], cwd=str(tree), env=env,
                                  capture_output=True, text=True, timeout=180, check=False)
            return done.stdout + done.stderr

        run("scripts/launch-config.py", *flags)
        run("scripts/port-slots.py", "claim", "--quiet")
        checked = run("scripts/launch-config.py", "--check")
        slot = ports.read_claims(registry).get(ports.canonical(tree))
        try:
            named = json.loads((tree / ".claude" / "launch.json").read_text(encoding="utf-8"))
            named = named["configurations"][0]["port"]
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            named = None
        if slot is None or slot == hashed:
            failures.append(f"{label}: the tree never claimed a slot away from its hash slot "
                            f"{hashed}, which another checkout holds (got {slot})")
        elif named != ports.DEV_LOW + slot or "launch-config: current" not in checked:
            failures.append(
                f"{label}: .claude/launch.json names {named}, but the tree claimed slot "
                f"{slot} (dev {ports.DEV_LOW + slot}). The Browser pane would open the port "
                f"of the checkout that holds slot {hashed}. The claim must run before the file "
                f"is written. `--check` said: {checked.strip()}")
    return failures


def nested_failures(base: Path) -> list:
    """A listener in a checkout nested inside this one is another checkout's, never ours."""
    tree = base / "outer"
    nested = tree / ".claude" / "worktrees" / "inner"
    (nested / "app").mkdir(parents=True)
    (tree / "app").mkdir()
    (tree / ".git").write_text("gitdir: /nowhere/.git/worktrees/outer\n", encoding="utf-8")
    (nested / ".git").write_text("gitdir: /nowhere/.git/worktrees/inner\n", encoding="utf-8")
    root = ports.canonical(tree)
    failures = []
    if not _inside(str(tree / "app"), root):
        failures.append("a listener in this checkout's own app/ must count as this checkout's")
    if _inside(str(nested / "app"), root):
        failures.append("a listener in a linked worktree nested inside this checkout counted as "
                        "this checkout's, so a claim would keep a port another tree serves on")
    return failures


def free_pair(slot: int) -> bool:
    return not any(port_held(base + s) for base in (ports.DEV_LOW, ports.CAPTURE_LOW)
                   for s in (slot, slot + 1))


def cmd_selftest(_args: argparse.Namespace) -> int:
    if not (ROOT / "app" / "node_modules" / ".bin" / "playwright").exists():
        print("port-slots selftest: FAILED — app/node_modules is missing, so nothing is "
              "proven. Run `npm --prefix app ci`.")
        return 1
    failures: list = []
    base = Path(tempfile.mkdtemp(prefix="pkmnscan-slots.")).resolve()
    registry = base / "registry" / "port-slots.json"
    saved = os.environ.get(ports.SLOT_REGISTRY_ENV)
    os.environ[ports.SLOT_REGISTRY_ENV] = str(registry)
    env = {k: v for k, v in os.environ.items()
           if k not in ("CI", "PKMNSCAN_CHECKOUT_IDENTITY", ports.PORT_ENV)}
    foreign = None
    try:
        # 0. THE FILE THE BROWSER PANE READS names the claimed port, on its own registry.
        launch_registry = base / "launch-registry" / "port-slots.json"
        failures += launch_config_failures(
            base, launch_registry, {**env, ports.SLOT_REGISTRY_ENV: str(launch_registry)})
        failures += nested_failures(base)

        # Two paths FORCED into one hash slot, on a slot whose ports and the next slot's are
        # free on this machine right now, so no real checkout's server is ever reached.
        by_slot: dict = {}
        pair = None
        for index in range(20000):
            path = base / f"tree-{index:05d}"
            slot = ports.hashed_slot(path)
            if slot + 1 >= ports.SLOTS:
                continue
            by_slot.setdefault(slot, []).append(path)
            if len(by_slot[slot]) == 2 and free_pair(slot):
                pair = (slot, *by_slot[slot])
                break
        if pair is None:
            raise SystemExit("port-slots selftest: found no free shared slot — unproven.")
        shared, tree_a, tree_b = pair
        build_tree(tree_a)
        build_tree(tree_b)

        # 1. THE INCIDENT. No claims: both trees derive one port. B serves; A runs its suite.
        want = (ports.DEV_LOW + shared, ports.CAPTURE_LOW + shared)
        for tree in (tree_a, tree_b):
            if node_ports(tree, env) != want:
                failures.append(f"with nothing claimed, {tree.name} should derive {want}")
        foreign = start_vite(tree_b, env)
        refused = run_playwright(tree_a, env)
        said = refused.stdout + refused.stderr
        if refused.returncode == 0:
            failures.append(
                "a Playwright run in tree A PASSED against tree B's Vite on the shared port "
                f"{want[0]}. That is the 2026-09-24 incident: a green run over another tree's "
                "code. The identity check in app/checkoutIdentity.ts must refuse it.")
        elif "REFUSED" not in said or str(tree_b) not in said:
            failures.append("tree A's run failed, but not by refusing tree B's server by "
                            "name:\n" + said[-1500:])
        shot = run_screenshot(tree_a, env, want[0])
        if "REFUSED" not in shot or str(tree_b) not in shot:
            failures.append("scripts/screenshot.sh in tree A did not refuse tree B's server "
                            "by name before it rendered:\n" + shot[-1500:])

        # 2. THE CLAIM. A claims first and B's live server pushes it one slot on. B claims
        #    next and keeps its own slot, because the server on it names B.
        slot_a, what_a = claim(tree_a, registry)
        slot_b, what_b = claim(tree_b, registry)
        if (slot_a, slot_b) != (shared + 1, shared):
            failures.append(f"claims gave A {slot_a} ({what_a}) and B {slot_b} ({what_b}); "
                            f"want A {shared + 1} and B {shared}")
        for tree, slot in ((tree_a, shared + 1), (tree_b, shared)):
            both = (ports.DEV_LOW + slot, ports.CAPTURE_LOW + slot)
            python = (ports.dev_port(tree), ports.capture_port(tree))
            node = node_ports(tree, env)
            if python != both or node != both:
                failures.append(f"{tree.name} after claiming: python {python}, node {node}, "
                                f"want {both} on both sides")
        again, _ = claim(tree_a, registry)
        if again != slot_a:
            failures.append(f"a second claim moved tree A from {slot_a} to {again}")

        # 3. THE SAME RUN, NOW ON ITS OWN SLOT: Playwright starts A's own Vite and passes.
        passed = run_playwright(tree_a, env)
        if passed.returncode != 0 or "1 passed" not in passed.stdout:
            failures.append("tree A's run on its own claimed slot did not pass:\n"
                            + (passed.stdout + passed.stderr)[-1500:])
        own = start_vite(tree_a, env)
        try:
            shot = run_screenshot(tree_a, env, ports.DEV_LOW + slot_a)
        finally:
            stop(own)
        if "REFUSED" in shot:
            failures.append("scripts/screenshot.sh in tree A refused tree A's own server:\n"
                            + shot[-1500:])

        # 4. A removed checkout frees its slot, and a damaged file reads as nothing claimed.
        stop(foreign)
        foreign = None
        shutil.rmtree(tree_b)
        claim(tree_a, registry)
        if ports.canonical(tree_b) in ports.read_claims(registry):
            failures.append("a claim kept the slot of a checkout that no longer exists")
        registry.write_text("{not json", encoding="utf-8")
        if ports.slot_for(tree_a) != ports.hashed_slot(tree_a) or node_ports(tree_a, env) != (
            ports.DEV_LOW + ports.hashed_slot(tree_a), ports.CAPTURE_LOW + ports.hashed_slot(tree_a)
        ):
            failures.append("a damaged registry must read as nothing claimed, on both sides")

        # 5. A claim over a damaged registry replaces it, so every other tree's claim in it
        #    is gone. The claim keeps the damaged file beside it and says where.
        _, what = claim(tree_a, registry)
        kept = sorted(registry.parent.glob(registry.name + ".bad-*"))
        if (len(kept) != 1 or kept[0].read_text(encoding="utf-8") != "{not json"
                or str(kept[0]) not in what):
            failures.append(
                "a claim over a damaged registry must keep a copy of it beside it "
                f"(.bad-<stamp>) and name that copy; it kept {[p.name for p in kept]} and "
                f"said: {what}")
    finally:
        if foreign is not None:
            stop(foreign)
        if saved is None:
            os.environ.pop(ports.SLOT_REGISTRY_ENV, None)
        else:
            os.environ[ports.SLOT_REGISTRY_ENV] = saved
        shutil.rmtree(base, ignore_errors=True)

    if failures:
        print("port-slots selftest: FAILED")
        for line in failures:
            print("  " + line.replace("\n", "\n    "))
        return 1
    print(f"port-slots selftest: two trees forced into slot {shared}; a run in one refused "
          f"the other's server by name; after claiming, each holds its own slot on both "
          f"sides and the run passed on its own server; screenshot.sh refused the other "
          f"tree's server and not its own; a removed tree's slot is freed; a "
          f"damaged registry reads as nothing claimed, and a claim over it keeps a copy and "
          f"says so; .claude/launch.json names the claimed port for both of its writers")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    claim_parser = sub.add_parser("claim", help="claim this checkout a slot of its own")
    claim_parser.add_argument("--root", help="the checkout to claim for (default: this one)")
    claim_parser.add_argument("--quiet", action="store_true",
                              help="say nothing when an existing slot is simply kept")
    claim_parser.set_defaults(func=cmd_claim)
    sub.add_parser("show", help="list every claimed slot").set_defaults(func=cmd_show)
    sub.add_parser("selftest", help="prove the claim and the identity check end to end"
                   ).set_defaults(func=cmd_selftest)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
