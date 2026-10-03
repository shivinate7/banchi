"""A scratch capture server over a scratch store, for the background reader's two measurements.

`scripts/sweep-memory.py` and `scripts/capture-gate.py` both need the same fixture: a temporary
`PKMNSCAN_HOME`, the model file and the fingerprint index placed in it, and a capture server on a
free high port that is never 8000, 5173 or this checkout's own slot. Nothing here touches the
owner's store. The photographs are read from a list the caller names and posted to the scratch
server over HTTP, so they land only in the temporary store, which `Scratch.close` deletes.
"""

from __future__ import annotations

import base64
import contextlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
PYTHON = REPO / ".venv" / "bin" / "python"
RESERVED_PORTS = {8000, 5173, 3000, 8080}


def free_port() -> int:
    while True:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        if port not in RESERVED_PORTS and port > 10000:
            return port


def rss_kb(pid: int) -> Optional[int]:
    out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return int(out) if out else None


def children_of(pid: int, word: str) -> List[int]:
    out = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,command="], capture_output=True, text=True).stdout
    found = []
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and parts[1] == str(pid) and word in parts[2]:
            found.append(int(parts[0]))
    return found


class Scratch:
    def __init__(self, model: Path, index: Path) -> None:
        self.home = Path(tempfile.mkdtemp(prefix="sweep-scratch-"))
        inventory = self.home / "inventory"
        (inventory / "models").mkdir(parents=True)
        os.symlink(model.resolve(), inventory / "models" / model.name)
        shutil.copy(index, inventory / "fingerprints.sqlite")
        self.port = free_port()
        # THE SERVER ONLY ANSWERS WRITES TO ITS OWN APP'S ORIGINS, so the scratch port is named.
        self.env = {
            **os.environ,
            "PKMNSCAN_HOME": str(self.home),
            "PYTHONUNBUFFERED": "1",
            "PKMNSCAN_ALLOWED_ORIGINS": f"http://127.0.0.1:{self.port}",
        }
        self.server: Optional[subprocess.Popen] = None
        self.box: Optional[int] = None

    # ------------------------------------------------------------------ the server
    def start(self) -> None:
        code = f"from server import capture_server; capture_server.serve('127.0.0.1', {self.port})"
        self.log = open(self.home / "server.log", "wb")  # noqa: SIM115 - held for the server's life
        self.server = subprocess.Popen(
            [str(PYTHON), "-c", code], cwd=str(REPO), env=self.env, stdout=self.log, stderr=subprocess.STDOUT
        )
        for _ in range(100):
            try:
                self.get("/status")
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.2)
        else:
            raise RuntimeError("the scratch server did not come up; see " + str(self.home / "server.log"))
        made = self.send("POST", "/boxes", {"name": "scratch"})
        self.box = int(made.get("box") or (made.get("box") or {}).get("box", 1)) if isinstance(made, dict) else 1

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def get(self, path: str):
        with urllib.request.urlopen(self.url(path), timeout=30) as response:
            return json.loads(response.read() or b"{}")

    def send(self, method: str, path: str, body: dict):
        request = urllib.request.Request(
            self.url(path), data=json.dumps(body).encode(), method=method,
            headers={"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.port}"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read() or b"{}")

    # ---------------------------------------------------------------- the captures
    def capture(self, photo: Path, game: str = "riftbound") -> float:
        """POST one capture and return how long the request took, in seconds."""
        body = {
            "box": self.box,
            "image": base64.b64encode(photo.read_bytes()).decode(),
            "capture_id": str(uuid.uuid4()),
            "game": game,
        }
        started = time.perf_counter()
        self.send("POST", "/capture", body)
        return time.perf_counter() - started

    def sql(self, statement: str, args=()):
        import sqlite3

        conn = sqlite3.connect(f"file:{self.home / 'inventory' / 'store.sqlite'}?mode=ro", uri=True)
        try:
            return conn.execute(statement, args).fetchall()
        finally:
            conn.close()

    def set_switch(self, on: bool):
        return self.send("PUT", "/pipeline/match/sweep", {"on": on})

    # ------------------------------------------------------------------- shutdown
    def close(self) -> None:
        for pid in self._watchers():
            with contextlib.suppress(OSError):
                os.kill(pid, 15)
        if self.server is not None:
            self.server.terminate()
            try:
                self.server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.server.kill()
        shutil.rmtree(self.home, ignore_errors=True)

    def _watchers(self) -> List[int]:
        record_path = self.home / "inventory" / "match-sweep.json"
        try:
            record = json.loads(record_path.read_text())
        except (OSError, ValueError):
            return []
        pids = [record.get("pid"), record.get("worker")]
        return [p for p in pids if isinstance(p, int)]


def photo_list(path: Path, count: int) -> List[Path]:
    listed = [Path(p) for p in json.loads(path.read_text())]
    listed = [p for p in listed if p.is_file()]
    return [listed[i % len(listed)] for i in range(count)]


def quantile(values: List[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))]


def summary(label: str, values: List[float]) -> Dict[str, float]:
    out = {"n": len(values), "p50_ms": quantile(values, 0.5) * 1000, "p99_ms": quantile(values, 0.99) * 1000,
           "max_ms": max(values) * 1000}
    print(f"{label:<14} n={out['n']}  p50 {out['p50_ms']:.1f} ms  p99 {out['p99_ms']:.1f} ms  max {out['max_ms']:.1f} ms")
    return out


if __name__ == "__main__":  # pragma: no cover
    sys.exit("a library for sweep-memory.py and capture-gate.py")
