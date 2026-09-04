#!/usr/bin/env python3
"""PreToolUse hook: say which settled decisions govern a file, before it is edited.

`docs/DECISIONS.md` opens with "Every entry here is closed. Sessions do not re-litigate
them." Nothing enforced that. An agent editing `pipeline/variant.py` had no way to know
D3 had already ruled that the capture toggle is trusted and `--variant` fills gaps rather
than overriding — so the way that ruling got discovered was by violating it and being
corrected. This closes the loop at the moment of the edit.

The gists are read out of docs/DECISIONS.md itself — the heading, plus the bolded lead-in
sentences the entries already use for their rulings ("**The toggle is trusted.**"). Nothing
is restated here, so nothing here can disagree with the decision it summarises. That is the
whole design: a hand-written summary of a decision is one more thing to keep in sync, and
this project already has enough of those.

NEVER BLOCKS, NEVER WRITES. Exit 0 unconditionally, including on malformed input, a
missing map, or its own bugs. A hook that can fail an edit is a hook that will one day fail
every edit — and this one is advisory by nature, so there is no failure mode worth that.

Silent for files no entry covers, which is most of them. A hook that speaks on every edit
gets muted, and the disabled PreToolUse block in .claude/settings.json is this repo's own
evidence for that: guard-opsec.sh over-triggered and was turned off within a day.

    scripts/decision-context.py                  read a hook payload on stdin
    scripts/decision-context.py --check <path>   print what a given file would show
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / "docs" / "map.py"
DECISIONS = ROOT / "docs" / "DECISIONS.md"

MAX_RULINGS = 3  # per decision. The rest is a Read away, and this is a nudge, not a briefing.


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def literals(path: Path) -> Dict[str, object]:
    """Module-level literal assignments, without importing. Same rule as docs-audit.py:
    a hook that runs project code to describe project code is a hook with side effects."""
    out: Dict[str, object] = {}
    for node in ast.parse(read(path)).body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                try:
                    out[target.id] = ast.literal_eval(node.value)
                except (ValueError, SyntaxError):
                    continue
    return out


def decision_gists(path: Optional[Path] = None, prefix: str = "D") -> Dict[str, Tuple[str, List[str]]]:
    """`D3` -> ("Variant resolution ladder", ["The toggle is trusted.", ...]).

    The two parameters exist so a TRACK's own decisions file goes through THIS parser
    rather than a second one — `docs/CODES-DECISIONS.md` numbers its entries `C1`..`C11`
    and is otherwise the same document shape. Both default to the singles track, so every
    existing caller (`scripts/status.py`, and this file's own hook path) is unchanged.
    """
    DECISIONS_PATH = path or DECISIONS
    if not DECISIONS_PATH.exists():
        return {}
    gists: Dict[str, Tuple[str, List[str]]] = {}
    current: Optional[str] = None
    title = ""
    bolds: List[str] = []

    def store() -> None:
        if current:
            gists[current] = (title, pick_rulings(bolds))

    for line in read(DECISIONS_PATH).splitlines():
        heading = re.match(r"^##\s+(" + prefix + r"[1-9][0-9]{0,2})\s*[—-]\s*(.+)$", line)
        if heading:
            store()
            current, title, bolds = heading.group(1), heading.group(2).strip(), []
            continue
        if line.startswith("## ") and current:
            store()
            current, title, bolds = None, "", []
            continue
        if current:
            # The entries state their rulings in a bold lead-in. Reuse that convention
            # rather than guessing which sentence matters.
            for bold in re.findall(r"\*\*(.+?)\*\*", line):
                text = bold.strip()
                if len(text) > 12 and text not in bolds:
                    bolds.append(text)
    store()
    return gists


def pick_rulings(bolds: Sequence[str]) -> List[str]:
    """Sentences first, labels only to fill.

    D3 opens with the ladder rung names in bold — `Capture-time metadata`,
    `Catalog-forced` — and its actual rulings, `The toggle is trusted.` and the one about
    `--variant` filling gaps rather than overriding, come further down. Taking the first
    three bolds returns the table of contents instead of the decision.
    """
    sentences = [text for text in bolds if text.endswith(".")]
    labels = [text for text in bolds if not text.endswith(".")]
    return (sentences + labels)[:MAX_RULINGS]


def track_for(relative: str) -> Optional[Dict[str, object]]:
    """The track that owns this path, per docs/map.py's TRACKS. Longest `owns` prefix wins.

    THE ONLY READER TRACKS HAS. It sat in the map with none from 2026-08-07 to 2026-08-31
    and went wrong twice unnoticed; a section with no consumer cannot be caught being
    false. What it buys is real rather than ceremonial: a session editing `codes/` was
    shown the D decisions the rig shares and was never told that C1-C11 and a second rules
    file exist at all, which is D14's two-tracks-one-rig arriving as a surprise (D80).
    """
    if not MAP.exists():
        return None
    best: Optional[Dict[str, object]] = None
    for track in literals(MAP).get("TRACKS") or []:  # type: ignore[union-attr]
        owns = str(track.get("owns") or "")
        if owns and relative.startswith(owns) and (
            best is None or len(owns) > len(str(best.get("owns") or ""))
        ):
            best = track
    return best


def lookup(relative: str) -> Optional[Dict[str, object]]:
    """What docs/map.py says about this file: the module entry, falling back to its package."""
    if not MAP.exists():
        return None
    components = literals(MAP).get("COMPONENTS") or []
    best: Optional[Dict[str, object]] = None
    for component in components:
        path = str(component.get("path", ""))
        if not path or not relative.startswith(path):
            continue
        modules = component.get("modules") or {}
        name = relative[len(path):]
        if name in modules:
            # The module's own list, NOT merged with the package's. The package list is the
            # union of everything any module under it touches, so merging would tell you
            # that pipeline/pricing.py is governed by D2 (Haiku vision) — true of the
            # package, useless here, and the fastest way to make this hook noise.
            entry = dict(modules[name])
            entry["scope"] = relative
            return entry
        # Package-level fallback, but keep looking for a more specific component.
        if best is None or len(path) > len(str(best.get("scope_path", ""))):
            best = {
                "does": component.get("does", ""),
                "governed_by": list(component.get("governed_by") or []),
                "tested_by": list(component.get("tested_by") or []),
                "note": component.get("note", ""),
                "scope": path,
                "scope_path": path,
            }
    return best


def render(relative: str, entry: Dict[str, object]) -> str:
    governed = [d for d in (entry.get("governed_by") or [])]
    if not governed:
        return ""
    gists = decision_gists()
    lines = [f"{relative} — {entry.get('does') or 'no description in docs/map.py'}"]
    scope = str(entry.get("scope", ""))
    if scope and scope != relative:
        lines.append(f"(no entry for this file; showing what governs {scope})")
    lines.append("Settled decisions that govern it — docs/DECISIONS.md, do not re-litigate:")
    for name in sorted(governed, key=lambda d: int(d[1:])):
        title, rulings = gists.get(name, ("(no such entry)", []))
        lines.append(f"  {name:<4} {title}")
        for ruling in rulings:
            lines.append(f"       - {ruling}")
    tested = entry.get("tested_by") or []
    if tested:
        lines.append(f"Covered by: {', '.join(tested)}. Run `make harness` before claiming it works.")
    track = track_for(relative)
    if track:
        lines.append(
            f"TRACK: {track.get('name')} (D14, two tracks one rig). The decisions above are "
            f"the shared rig's; this path ALSO answers to {track.get('decisions')} and to "
            f"{track.get('rules')}, which is auto-loaded in that directory."
        )
        codes = [d for d in governed if d.startswith("C")]
        if codes:
            track_gists = decision_gists(ROOT / str(track.get("decisions")), prefix="C")
            for name in sorted(codes, key=lambda d: int(d[1:])):
                title, rulings = track_gists.get(name, ("(no such entry)", []))
                lines.append(f"  {name:<4} {title}")
                for ruling in rulings:
                    lines.append(f"       - {ruling}")
    if entry.get("note"):
        lines.append(f"Also: {entry['note']}")
    return "\n".join(lines)


def relative_to_root(raw: str) -> Optional[str]:
    if not raw:
        return None
    try:
        resolved = Path(raw).resolve()
        return str(resolved.relative_to(ROOT))
    except (ValueError, OSError):
        return None


def main(argv: Sequence[str]) -> int:
    if len(argv) >= 2 and argv[0] == "--check":
        relative = relative_to_root(argv[1]) or argv[1]
        entry = lookup(relative)
        print(render(relative, entry) if entry else f"{relative}: no entry in docs/map.py")
        return 0

    payload = json.loads(sys.stdin.read() or "{}")
    relative = relative_to_root(str(payload.get("tool_input", {}).get("file_path", "")))
    if not relative:
        return 0
    entry = lookup(relative)
    if not entry:
        return 0
    context = render(relative, entry)
    if not context:
        return 0

    # additionalContext is the documented way to hand a PreToolUse hook's text to the
    # model without touching the permission decision. Deliberately NOT permissionDecision:
    # "allow" — that would auto-approve every Edit and Write in the project, which is a
    # security change wearing a convenience hat.
    #
    # Hook payload shape has moved between Claude Code releases (see the _comment in
    # .claude/settings.json). If a release ignores this field the JSON is merely printed,
    # which is still readable and still harmless — the failure mode is a lost nudge, never
    # a blocked edit. CLAUDE.md points at docs/map.py directly for that reason.
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": context,
        }
    }))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception:  # noqa: BLE001 - advisory only; an edit must never fail because of this
        sys.exit(0)
