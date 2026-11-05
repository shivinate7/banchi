#!/usr/bin/env python3
"""PreToolUse hook: say which settled decisions govern a file, before it is edited.

`docs/decisions/` opens with "Every entry here is closed. Sessions do not re-litigate
them." Nothing enforced that. An agent editing `pipeline/variant.py` had no way to know
D3 had already ruled that the capture toggle is trusted and `--variant` fills gaps rather
than overriding — so the way that ruling got discovered was by violating it and being
corrected. This closes the loop at the moment of the edit.

The gists are read out of docs/decisions/ itself — the heading, plus the bolded lead-in
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

ONCE PER FILE PER SESSION, on the owner's word. The nudge for a file is printed the first time
the session edits it and is silent after, because the session already holds it. The paths shown
are kept in a temp file named for the session id and agent id. A SessionStart event deletes that file
(`--reset`), so a compaction, which drops the printed text from the context, prints each file
again. No session id in the payload means no memory, so the nudge prints every time.

    scripts/decision-context.py                  read a hook payload on stdin
    scripts/decision-context.py --check <path>   print what a given file would show
    scripts/decision-context.py --reset          SessionStart: forget what this session was shown
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
MAP_DIR = ROOT / "docs" / "map"  # the plain-English map: one page per area, one line per code file
TRACKS = ROOT / "docs" / "tracks.json"  # the two tracks, a JSON list of {name, owns, decisions, rules, status, note}
# The corpus is `docs/decisions/`, one file per entry, and was one file until the split.
# `scripts/decisions_corpus.py` reassembles it, so the parsing below is unchanged — and
# `path_for` now makes "the file holding this entry" a real answer, which the entry that
# dropped the `@` wanted and a monolith could not give: this hook can name a file a session
# opens rather than a region of one it must not.
DECISIONS = ROOT / "docs" / "decisions"  # the corpus directory

MAX_RULINGS = 3  # per decision. The rest is a Read away, and this is a nudge, not a briefing.


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")



def _corpus_text() -> str:
    """`docs/decisions/` as one document, or "" if it cannot be read.

    FAIL-SOFT ON PURPOSE. This hook is wrapped in `except Exception: sys.exit(0)` and is
    advisory by design (see .claude/settings.json); an unreadable corpus must cost the nudge
    and never the edit.
    """
    try:
        import json

        directory = ROOT / "docs" / "decisions"
        order = json.loads((directory / "ORDER.json").read_text(encoding="utf-8"))["order"]
        return "\n".join(read(directory / name) for name in order)
    except Exception:
        return ""


def decision_gists(path: Optional[Path] = None, prefix: str = "D") -> Dict[str, Tuple[str, List[str]]]:
    """`D3` -> ("Variant resolution ladder", ["The toggle is trusted.", ...]).

    The two parameters exist so a TRACK's own decisions file goes through THIS parser
    rather than a second one — `docs/specs/code-cards.md` numbers its entries `C1`..`C11`
    and is otherwise the same document shape. Both default to the singles track, so every
    existing caller (`scripts/status.py`, and this file's own hook path) is unchanged.
    """
    # A caller naming a path gets that file; the default is the CORPUS, reassembled. The
    # `C` track is still one file and passes its own path, which is why this takes text from
    # two places rather than always reaching for the directory.
    if path is None:
        body = _corpus_text()
        if not body:
            return {}
    else:
        if not path.exists():
            return {}
        body = read(path)
    gists: Dict[str, Tuple[str, List[str]]] = {}
    current: Optional[str] = None
    level = 0
    title = ""
    bolds: List[str] = []

    def store() -> None:
        if current:
            gists[current] = (title, pick_rulings(bolds))

    for line in body.splitlines():
        # The slug form is an id until the merge claims it (D140, rewritten 2026-09-11), and
        # a session editing a file its branch's own unclaimed entry governs must be shown
        # that entry — which is the one moment it is least likely to be remembered.
        heading = re.match(
            r"^(#{1,2})\s+(" + prefix + r"(?:[1-9][0-9]{0,2}|-[a-z][a-z0-9]*(?:-[a-z0-9]+)+))"
            r"\s*[—-]\s*(.+)$", line)
        if heading:
            store()
            level = len(heading.group(1))
            current, title, bolds = heading.group(2), heading.group(3).strip(), []
            continue
        # A decision's title is an H1 and ends at the next entry heading; a track file such
        # as code-cards.md heads each entry with an H2 and ends at the next `## `.
        if level == 2 and line.startswith("## ") and current:
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
    """The track that owns this path, per docs/tracks.json. Longest `owns` prefix wins.

    What it buys is real rather than ceremonial: a session editing `codes/` was shown the D
    decisions the rig shares and was never told that C1-C11 and a second rules file exist at
    all, which is D14's two-tracks-one-rig arriving as a surprise (D80).
    """
    try:
        tracks = json.loads(read(TRACKS))
    except (OSError, ValueError):
        return None
    best: Optional[Dict[str, object]] = None
    for track in tracks if isinstance(tracks, list) else []:
        owns = str(track.get("owns") or "") if isinstance(track, dict) else ""
        if owns and relative.startswith(owns) and (
            best is None or len(owns) > len(str(best.get("owns") or ""))
        ):
            best = track
    return best


_MAP_LINE = re.compile(r"^- `([^`]+)` — (.*)$")
_DECISIONS_LINE = "  - Decisions: "


def lookup(relative: str) -> Optional[Dict[str, object]]:
    """The docs/map/ line for this file: its sentence, and the ids on the decisions line under it.

    ONE MORE READER OF THE MAP FORMAT, because this is a PreToolUse hook that runs on every edit
    and must run alone: its self-test copies only this file, so there is no `map.config.json` to
    read and no node to start. The skill's `map-show.mjs` (`make map`) is the full reader and stays
    the one for people. Only the two line shapes below are read here, and a line this does not
    parse costs the nudge, never the edit.
    """
    try:
        pages = sorted(MAP_DIR.glob("*.md"))
    except OSError:
        return None
    for page in pages:
        lines = read(page).splitlines()
        for number, line in enumerate(lines):
            found = _MAP_LINE.match(line)
            if not found or found.group(1) != relative:
                continue
            governed: List[str] = []
            for under in lines[number + 1:]:
                if not under.startswith("  "):
                    break
                if under.startswith(_DECISIONS_LINE):
                    governed = re.findall(r"`([^`]+)`", under[len(_DECISIONS_LINE):])
            return {"does": found.group(2).strip(), "governed_by": governed}
    return None


def normal_id(name: str) -> str:
    """`D092` and `D92` are one decision: the map line carries the form a comment cites."""
    return re.sub(r"\d+", lambda match: str(int(match.group())), name)


def render(relative: str, entry: Dict[str, object]) -> str:
    """One line per governing decision: id and title, no rulings.

    A ruling was the expensive part: 108 decisions on `server/capture_server.py` cost
    38,130 bytes on every single edit, most of it text the record gives on demand. The
    owner's ruling, from the token-budget review: "Id + title only (Recommended)."
    `decision_gists()` still computes rulings, and `scripts/status.py` still reads titles off
    the same call, so nothing is removed, only what THIS render prints.
    """
    governed = sorted(
        {normal_id(d) for d in (entry.get("governed_by") or [])},  # type: ignore[union-attr]
        key=lambda d: int(re.sub(r"\D", "", d) or 0),
    )
    if not governed:
        return ""
    gists = decision_gists()
    lines = [f"{relative} — {entry.get('does') or 'no description in docs/map/'}"]
    lines.append("Settled decisions that govern it — docs/decisions/, do not re-litigate:")
    for name in governed:
        title, _ = gists.get(name, ("(no such entry)", []))
        lines.append(f"  {name:<4} {title}")
    track = track_for(relative)
    if track:
        track_file = ROOT / str(track.get("decisions"))
        lines.append(
            f"TRACK: {track.get('name')} (D14, two tracks one rig). The decisions above are "
            f"the shared rig's; this path ALSO answers to {track_file.relative_to(ROOT)} and to "
            f"{track.get('rules')}, which is auto-loaded in that directory."
        )
    lines.append("Full text: docs/decisions/<id>-<slug>.md, or `make map ARGS=<path>` for the file's map line.")
    return "\n".join(lines)


def _seen_file(payload: Dict[str, object]) -> Optional[Path]:
    """The temp file holding the paths this session was already shown, or None without an id."""
    def clean(key):
        return re.sub(r"[^A-Za-z0-9_-]", "", str(payload.get(key) or ""))

    safe = clean("session_id")
    # The session id is shared by the orchestrator and every subagent, so the agent id (empty
    # for the main session) is part of the key: each agent is shown a file once.
    return Path(tempfile.gettempdir()) / f"banchi-decision-context-{safe}-{clean('agent_id')}" if safe else None


def already_shown(payload: Dict[str, object], relative: str) -> bool:
    """True when this session saw `relative` already. Records it when it did not. Fail-soft."""
    seen = _seen_file(payload)
    if seen is None:
        return False
    try:
        if seen.exists() and relative in seen.read_text(encoding="utf-8").splitlines():
            return True
        with seen.open("a", encoding="utf-8") as handle:
            handle.write(relative + "\n")
    except OSError:
        pass
    return False


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
        print(render(relative, entry) if entry else f"{relative}: no map line in docs/map/")
        return 0

    payload = json.loads(sys.stdin.read() or "{}")
    if argv[:1] == ["--reset"]:
        seen = _seen_file(payload)
        if seen is not None:
            for each in seen.parent.glob(seen.name.rsplit("-", 1)[0] + "-*"):
                each.unlink(missing_ok=True)
        return 0
    relative = relative_to_root(str(payload.get("tool_input", {}).get("file_path", "")))
    if not relative:
        return 0
    entry = lookup(relative)
    if not entry:
        return 0
    context = render(relative, entry)
    if not context or already_shown(payload, relative):
        return 0

    # additionalContext is the documented way to hand a PreToolUse hook's text to the
    # model without touching the permission decision. Deliberately NOT permissionDecision:
    # "allow" — that would auto-approve every Edit and Write in the project, which is a
    # security change wearing a convenience hat.
    #
    # Hook payload shape has moved between Claude Code releases (see the _comment in
    # .claude/settings.json). If a release ignores this field the JSON is merely printed,
    # which is still readable and still harmless — the failure mode is a lost nudge, never
    # a blocked edit. CLAUDE.md points at docs/map/ directly for that reason.
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
