#!/usr/bin/env python3
"""`make map` — docs/map.py, rendered for a person.

THE FILE IS 2,600 LINES AND NOBODY COULD LOOK AT IT. That is the defect this script closes,
and it is the one the map had that no audit row could see: `make docs-audit` proved every
path in it resolved, `scripts/decision-context.py` fed it to a hook, and the only rendering
a human ever got was the three lines `make status` lifts for its header. A file that can
only be read whole, at ~56,000 tokens, is read by nobody and edited by everybody — which is
exactly how `TRACKS` sat wrong for three weeks (D80).

Four views, because four questions get asked of this file:

    make map                    the shape: tracks, the build order, every package
    make map ARGS=app/          one package: what it does, what governs it, its modules
    make map ARGS=store/master.py   one module, in full, with its decisions resolved
    make map ARGS=D17           every entry D17 governs, and the entry's own title
    make map ARGS=--stale       entries whose FILE has moved since the prose about it did

`--stale` is the one view that reports something no other check in this repo can. The
repo-map row proves a path exists and that its citations resolve; nothing anywhere asks
whether the SENTENCE is still true, because that is not decidable. This gets as close as a
machine can: `git blame` on the map's own lines against the file's last commit. It ranks
suspicion and never fails — a note that was written to outlive a refactor is not a defect,
which is why this prints and does not block, and why it is not an audit row.

Stdlib only, and the map is read with `ast.literal_eval` rather than imported — the same
rule `scripts/docs-audit.py` and `scripts/status.py` follow, for the same reason: a tool
that describes the project must not run the project. `decision_gists` is imported from
`scripts/decision-context.py` rather than reimplemented; one lift of docs/DECISIONS.md,
one place to break.
"""

from __future__ import annotations

import ast
import importlib.util
import re
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / "docs" / "map.py"
WIDTH = 92
LABEL = 16


# ------------------------------------------------------------------------------- reading


def literals(path: Path) -> Dict[str, object]:
    """Module-level literal assignments, without importing the module."""
    out: Dict[str, object] = {}
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                try:
                    out[target.id] = ast.literal_eval(node.value)
                except ValueError:
                    continue
    return out


def gists() -> Dict[str, Tuple[str, List[str]]]:
    """Decision titles and rulings, lifted by the hook's own parser."""
    path = ROOT / "scripts" / "decision-context.py"
    if not path.exists():
        return {}
    try:
        spec = importlib.util.spec_from_file_location("decision_context", path)
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        return module.decision_gists()
    except Exception:  # noqa: BLE001 - a broken hook must not take the renderer down
        return {}


def modules_of(component: Dict[str, object]) -> Dict[str, Dict[str, object]]:
    return dict(component.get("modules") or {})  # type: ignore[arg-type]


# ------------------------------------------------------------------------------ printing


def wrap(text: str, indent: int) -> List[str]:
    if not text:
        return []
    return textwrap.wrap(text, width=WIDTH, initial_indent=" " * indent,
                         subsequent_indent=" " * indent) or []


def field(label: str, value: str) -> List[str]:
    lines = wrap(value, LABEL)
    if not lines:
        return []
    first = lines[0]
    return [f"  {label:<{LABEL - 2}}{first[LABEL:]}"] + lines[1:]


def rule(title: str) -> List[str]:
    return ["", title, "-" * min(len(title), WIDTH)]


def decisions(ids: Sequence[str], resolved: Dict[str, Tuple[str, List[str]]],
              rulings: bool = False) -> List[str]:
    out: List[str] = []
    for name in sorted(ids, key=lambda d: (d[0], int(re.sub(r"\D", "", d) or 0))):
        title, said = resolved.get(name, ("(no entry in docs/DECISIONS.md)", []))
        out += wrap(f"{name:<5} {title}", 4)
        if rulings:
            for said_one in said[:2]:
                out += wrap(said_one, 11)
    return out


# --------------------------------------------------------------------------------- views


def shape(data: Dict[str, object], resolved: Dict[str, Tuple[str, List[str]]]) -> List[str]:
    out: List[str] = [f"docs/map.py — {len(MAP.read_text(encoding='utf-8').splitlines())} lines, "
                      f"rendered. `make map ARGS=<package|path|D<n>|--stale>` for one thing."]

    tracks = data.get("TRACKS") or []
    out += rule("TRACKS")
    for track in tracks:  # type: ignore[union-attr]
        owns = track.get("owns") or "everything else"
        out += field(str(track.get("name")), f"{track.get('status')} · owns {owns} · "
                                             f"{track.get('decisions')} · {track.get('rules')}")

    build = data.get("BUILD_ORDER") or []
    done = [s for s in build if s.get("status") == "done"]          # type: ignore[union-attr]
    nxt = [s for s in build if s.get("status") == "next"]           # type: ignore[union-attr]
    blocked = [s for s in build if s.get("status") == "blocked"]    # type: ignore[union-attr]
    out += rule("BUILD ORDER")
    out += field("steps", f"{len(build)} — {len(done)} done, {len(nxt)} next, {len(blocked)} blocked")
    for step in nxt + blocked:
        mark = "next" if step.get("status") == "next" else f"blocked on {step.get('blocked_by')}"
        out += field(f"  {step.get('step')}.", f"{step.get('title')}  [{mark}]")
    out += wrap("A BACKLOG, NOT A SCHEDULE, since 2026-08-24 — see the section header in "
                "docs/map.py. Work is proposed and recorded in docs/DECISIONS.md; step 9 is "
                "the one row here that still describes the future.", 2)

    out += rule("PACKAGES")
    for component in data.get("COMPONENTS") or []:  # type: ignore[union-attr]
        count = len(modules_of(component))  # type: ignore[arg-type]
        out += field(str(component.get("path")),
                     f"[{component.get('status')}] {count} module{'' if count == 1 else 's'} · "
                     f"{component.get('does')}")
    return out


def package(component: Dict[str, object], resolved: Dict[str, Tuple[str, List[str]]]) -> List[str]:
    out = rule(f"{component.get('path')}   [{component.get('status')}]")
    out += wrap(str(component.get("does") or ""), 2)
    if component.get("note"):
        out += [""] + wrap(str(component["note"]), 2)
    if component.get("governed_by"):
        out += ["", "  governed by"]
        out += decisions(component["governed_by"], resolved)  # type: ignore[arg-type]
    mods = modules_of(component)
    if mods:
        out += ["", f"  {len(mods)} modules"]
        for name, entry in mods.items():
            out += wrap(f"{name}  —  {entry.get('does', '')}", 4)
    return out


def module(path: str, component: Dict[str, object], entry: Dict[str, object],
           resolved: Dict[str, Tuple[str, List[str]]]) -> List[str]:
    out = rule(path)
    out += wrap(str(entry.get("does") or ""), 2)
    if entry.get("note"):
        out += [""] + wrap(str(entry["note"]), 2)
    governed = list(entry.get("governed_by") or [])
    if governed:
        out += ["", "  governed by — settled, do not re-litigate"]
        out += decisions(governed, resolved, rulings=True)
    if entry.get("tested_by"):
        out += ["", "  tested by"] + wrap(", ".join(entry["tested_by"]), 4)  # type: ignore[arg-type]
    out += ["", f"  in {component.get('path')} — {component.get('does')}"]
    return out


def by_decision(name: str, data: Dict[str, object],
                resolved: Dict[str, Tuple[str, List[str]]]) -> List[str]:
    title, said = resolved.get(name, ("(no entry in docs/DECISIONS.md)", []))
    out = rule(f"{name} — {title}")
    for one in said[:3]:
        out += wrap(one, 2)
    hits: List[str] = []
    for component in data.get("COMPONENTS") or []:  # type: ignore[union-attr]
        if name in (component.get("governed_by") or []):
            hits.append(str(component.get("path")))
        for mod, entry in modules_of(component).items():  # type: ignore[arg-type]
            if name in (entry.get("governed_by") or []):
                hits.append(f"{component.get('path')}{mod}")
    out += ["", f"  governs {len(hits)} entr{'y' if len(hits) == 1 else 'ies'}"]
    for hit in hits:
        out += wrap(hit, 4)
    if not hits:
        out += wrap("Nothing in the map cites it. That is not necessarily wrong — an entry "
                    "may rule on a document or a practice rather than on a file.", 4)
    return out


def stale(data: Dict[str, object]) -> List[str]:
    """Entries whose file has moved since the map's prose about it did.

    Suspicion, not a verdict — see this module's docstring. Ranked by the gap so the
    reading order is the order worth checking.
    """
    blame = subprocess.run(["git", "blame", "--line-porcelain", str(MAP)],
                           cwd=ROOT, capture_output=True, text=True)
    if blame.returncode != 0:
        return ["", "--stale needs git, and `git blame docs/map.py` failed here."]
    when: Dict[int, int] = {}
    number, stamp = 0, None
    for line in blame.stdout.split("\n"):
        if re.match(r"^[0-9a-f]{40} \d+ \d+", line):
            number = int(line.split()[2])
        elif line.startswith("author-time "):
            stamp = int(line.split()[1])
        elif line.startswith("\t") and stamp is not None:
            when[number] = stamp

    lines = MAP.read_text(encoding="utf-8").splitlines()
    rows: List[Tuple[int, str, int, int]] = []
    cursor = 0
    for component in data.get("COMPONENTS") or []:  # type: ignore[union-attr]
        base = str(component.get("path"))
        for name in modules_of(component):  # type: ignore[arg-type]
            target = ROOT / f"{base}{name}"
            if not target.exists():
                continue
            key = re.compile(r'^\s+"' + re.escape(name) + r'":')
            start = next((i + 1 for i in range(cursor, len(lines)) if key.match(lines[i])),
                         next((i + 1 for i in range(len(lines)) if key.match(lines[i])), None))
            if start is None:
                continue
            indent = len(lines[start - 1]) - len(lines[start - 1].lstrip())
            end = start
            for i in range(start, len(lines)):
                text = lines[i]
                if (text.strip() and i + 1 != start and re.match(r'^\s+"', text)
                        and len(text) - len(text.lstrip()) <= indent):
                    end = i
                    break
                end = i + 1
            cursor = end
            stamps = [when[i] for i in range(start, end + 1) if i in when]
            if not stamps:
                continue
            said = max(stamps)
            moved = subprocess.run(["git", "log", "-1", "--format=%at", "--", f"{base}{name}"],
                                   cwd=ROOT, capture_output=True, text=True).stdout.strip()
            if not moved:
                continue
            gap = int(moved) - said
            if gap > 86400:
                rows.append((gap, f"{base}{name}", said, int(moved)))

    out = rule("PROSE THE FILE HAS OUTRUN")
    out += wrap("The map's sentence about each file below was written before the file's last "
                "commit. Suspicion only — nothing here is provably wrong, which is why no "
                "audit row can carry it and why this never fails.", 2)
    if not rows:
        out += ["", "  Nothing. Every entry was written at or after its file's last commit."]
        return out
    out += ["", f"  {len(rows)} of the entries whose file exists, worst first:", ""]
    import datetime

    def day(stamp: int) -> str:
        return datetime.datetime.fromtimestamp(stamp).strftime("%Y-%m-%d")

    out.append(f"  {'entry':<44}{'prose':<13}{'file moved':<13}days")
    for gap, name, said, moved in sorted(rows, reverse=True):
        out.append(f"  {name:<44}{day(said):<13}{day(moved):<13}{gap // 86400}")
    return out


# ---------------------------------------------------------------------------------- main


def find(data: Dict[str, object], query: str
         ) -> Optional[Tuple[str, Dict[str, object], Optional[Dict[str, object]]]]:
    """A package or a module, by the path the map calls it."""
    wanted = query.strip().lstrip("./")
    for component in data.get("COMPONENTS") or []:  # type: ignore[union-attr]
        base = str(component.get("path"))
        if wanted in (base, base.rstrip("/")):
            return base, component, None
        for name in modules_of(component):  # type: ignore[arg-type]
            if wanted in (f"{base}{name}", name):
                return f"{base}{name}", component, modules_of(component)[name]  # type: ignore[arg-type]
    return None


def main(argv: Sequence[str]) -> int:
    if not MAP.exists():
        print(f"docs/map.py not found at {MAP}", file=sys.stderr)
        return 1
    data = literals(MAP)
    resolved = gists()
    query = (argv[0] if argv else "").strip()

    if query in ("", "--all"):
        lines = shape(data, resolved)
    elif query in ("--stale", "stale"):
        lines = stale(data)
    elif re.fullmatch(r"[CD]\d+", query.upper()):
        lines = by_decision(query.upper(), data, resolved)
    else:
        hit = find(data, query)
        if hit is None:
            print(f"no entry in docs/map.py for {query!r}.\n"
                  f"Try a package (`app/`), a path (`store/master.py`), a decision "
                  f"(`D17`), or `--stale`.", file=sys.stderr)
            return 1
        path, component, entry = hit
        lines = package(component, resolved) if entry is None else module(path, component, entry, resolved)

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
