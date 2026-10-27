#!/usr/bin/env python3
"""A named registry of tree-descriptive numbers, so a digit in prose can say where it came
from and a machine can tell a stale one from a fresh one.

THE OWNER'S RULING (2026-09-20): every number in CLAUDE.md that describes the tree AS IT IS
must be a derived, auto-updating value, never a hand-typed guess that rots the moment the
tree moves. The worked example was one sentence in `CLAUDE.md`'s design-system section:
"102 files under app/src" (really 137, measured the day this file was written) and "266
uses of `var(--bn-ink)`" (really 296). The alias count beside them ("twenty-four") turned
out to be stale too, at 25 — see `tokens_css_legacy_alias_count`'s own docstring.

WHAT BELONGS HERE, AND WHAT NEVER DOES — read this before adding an entry. A figure belongs
in this registry only when it is a LIVE PROPERTY OF THE CHECKED-OUT TREE: something that is
true today because of what the files say today, and would read differently tomorrow if a
file changed, with no human needing to have witnessed anything for the number to be right.
A figure must NEVER be added here when it is instead a RECORD OF A PAST EVENT — a gate run,
an incident measurement, a fixed test's result, a benchmark taken on one rig on one day.
Gate B's "53 cards end to end", the "969 threads, 338% CPU" incident, the join bug that
"silently zero-joined 950 rows", "430 answers examined, 0 safe to auto-prune", QR decode at
"140/140" — none of these can ever be recomputed from the tree as it stands now, because the
tree does not hold the rig, the run, or the day any more. A generator that rewrote one of
those to match today's tree would not be fixing rot, it would be FALSIFYING A RECORD: the
number's whole job is to say what a specific run measured, not what is true right now.

HOW A READER TELLS THE TWO CLASSES APART, without having to trust a comment's own claim
about itself: every function in `REGISTRY` is named for a LIVE ARTIFACT under version
control (a file count, a substring count, a declaration count) and takes only `root: Path`
— nothing here reads a date, a run id, or a fixture. A number that can only be produced by
reading `docs/gates/gate-runs/*.md` or a `harness/traces/*.json` file has no honest way into
this shape, which is `check_derived_numbers`'s enforcement of the distinction: THIS FILE
NEVER GROWS AN ENTRY FOR A HISTORICAL FIGURE, so a marker naming one finds nothing in
`REGISTRY` and fails exactly like a typo (see `scripts/docs-audit.py`'s `derived numbers`
row). Adding such an entry deliberately is a code-review question this module cannot stop by
itself; the module's contract is that nobody accidentally lands one, because computing a
number this shape cannot produce is not a bug fix somebody reaches for by accident — it is a
new function somebody would have to sit down and write, with no live artifact to point it at.

DELIBERATELY LEFT OUT, AND WHY (read before adding either back):

  - CLAUDE.md's own "~56,000 tokens" (docs/map.py's size) and "~627KB" / "~163,000 tokens"
    (docs/decisions/'s total size) are already marked approximate with `~` in the prose.
    A tokenizer is not stdlib, and byte-to-token is a MEASURED ratio this repo has been
    burned by inventing before (see MEMORY.md's `big-output-never-enters-context`). A byte
    count could be derived honestly; the TOKEN estimate it is paired with cannot, without
    vendoring a tokenizer this script has no other reason to depend on. Left both out rather
    than derive half a sentence.
  - "218 references live in this tree" (build-order step ids, `n` in docs/map.py). Measured
    three candidate definitions while building this registry — a bare `step \d+` scan across
    tracked markdown alone (241), the same scan restricted to numbers that are actually valid
    `n` ids in docs/map.py (391, across the whole tracked tree) — and none of them lands
    anywhere near 218, because "step" is ordinary English: `docs/specs/store-scaling/
    02-per-box-read.md` alone numbers its OWN 27 unrelated steps, and motion-trigger prose
    uses "step" as a capture stage. There is no citation registry in this tree that marks a
    "step N" as a build-order reference versus a spec's own numbered list, so no regex can
    honestly tell them apart. Left out rather than invented; a real fix is a citation
    registry for `step <n>`, the same shape this repo already keeps for its decision and
    debt ids, which is a separate, larger piece of work than this one.
  - The `--bn-*` token and route-census counts elsewhere in CLAUDE.md (route/screen totals,
    storage-key counts, decision-index totals) are NOT duplicated here: `docs-audit.py`
    already carries a dedicated row for each (`route census`, `storage keys`, `decision
    index`), per this task's own instruction not to re-cover ground a mirrored-constant row
    already owns.

MARKER SYNTAX. A number in prose names its derivation with an HTML comment immediately
after it, on the same line: `137<!-- derived:app_src_file_count -->`. Markdown renders an
HTML comment as nothing, so a reader sees only the number; `MARKER_RE` below is how a
machine finds it. `scripts/docs-audit.py`'s `derived numbers` row reads every marker in the
tracked markdown and asserts the number in front of it equals `compute(name, root)` for the
checked-out tree — it gates and writes nothing (D18). `scripts/derived-numbers-pin.py
--write` is the only thing that edits a marked number, on nobody's schedule but a person's.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Dict, List, NamedTuple, Optional

# One marker per number: the digits (commas allowed for thousands), then this comment,
# on the same line as the number it describes. `derived:<name>` is deliberately spelled out
# rather than abbreviated, so a reader who has never seen this file can still tell what the
# comment is for from the marker alone.
MARKER_RE = re.compile(
    r"(?P<number>\d[\d,]*)\s*<!--\s*derived:(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*-->"
)


class Derivation(NamedTuple):
    name: str
    about: str
    compute: Callable[[Path], int]


def _files_under(root: Path, relative: str) -> List[Path]:
    """Every real file under `root/relative`, or `[]` if that directory does not exist.

    Plain `Path.rglob`, not `git ls-files` — this registry has to run over a synthetic
    fixture tree under `--self-test` with no `.git` in sight, and a real answer over the
    live checkout has to be provable without shelling out to it. Measured to agree with
    `git ls-files app/src` on the real tree (137 either way): the checkout carries no
    stray untracked file under `app/src` for the two to disagree over, and if one ever
    appears, an untracked file being counted here and not in a commit is the more honest
    failure of the two — this reads what is ACTUALLY on disk, not what got staged.
    """
    base = root / relative
    if not base.is_dir():
        return []
    return [p for p in base.rglob("*") if p.is_file()]


def app_src_file_count(root: Path) -> int:
    """Every file tracked under `app/src`, of any type. CLAUDE.md's own worked example."""
    return len(_files_under(root, "app/src"))


def bn_ink_var_uses(root: Path) -> int:
    """Occurrences of the literal substring `var(--bn-ink)` across every file under
    `app/src`. A substring count, not a CSS parse: the sentence it backs ("against 296 uses
    of `var(--bn-ink)` alone") is itself counting raw text occurrences as the argument for
    how embedded the token is, not counting only where it is syntactically a declaration's
    value — the two files agreeing this way, `.tsx` and `.css` alike, is the whole point of
    the sentence: it is not a stylesheet-only habit."""
    total = 0
    for path in _files_under(root, "app/src"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        total += text.count("var(--bn-ink)")
    return total


# `app/src/tokens.css`'s own header comment names this block "LEGACY ALIASES" TWICE: once
# in the file's opening docstring-style comment (prose, describing the block further down),
# and once immediately above the block itself, as a section banner. `.finditer(...)[-1]` —
# the LAST match — is deliberate: taking the first would walk from the top-of-file mention
# all the way to the `:root` block's own closing brace and count every real token in the
# file as a "legacy alias" (measured: 130, while there are 25 real aliases). The banner
# immediately preceding the block is the one whose following `}` is the block's own.
_LEGACY_ALIAS_HEADER = re.compile(r"LEGACY ALIASES.*?\*/\s*", re.S)
_LEGACY_ALIAS_DECL = re.compile(r"^\s*--[A-Za-z0-9-]+\s*:", re.M)


def tokens_css_legacy_alias_count(root: Path) -> int:
    """Custom-property declarations inside `app/src/tokens.css`'s own LEGACY ALIASES
    block — the retired `--ink`/`--muted`/`--s1`… names kept, unread, for D-whatever's own
    stated reason. Measured 2026-09-20: 25, not the 24 CLAUDE.md's prose claimed — a second
    stale figure in the same sentence the owner named as the worked example, found by
    actually counting rather than trusting the earlier count."""
    path = root / "app" / "src" / "tokens.css"
    if not path.is_file():
        raise FileNotFoundError(str(path))
    text = path.read_text(encoding="utf-8", errors="ignore")
    matches = list(_LEGACY_ALIAS_HEADER.finditer(text))
    if not matches:
        raise ValueError("no 'LEGACY ALIASES' banner found in tokens.css")
    rest = text[matches[-1].end():]
    end = rest.find("}")
    block = rest if end == -1 else rest[:end]
    return len(_LEGACY_ALIAS_DECL.findall(block))


REGISTRY: Dict[str, Derivation] = {
    d.name: d
    for d in (
        Derivation(
            "app_src_file_count",
            "files tracked under app/src, of any type",
            app_src_file_count,
        ),
        Derivation(
            "bn_ink_var_uses",
            "occurrences of the literal string var(--bn-ink) under app/src",
            bn_ink_var_uses,
        ),
        Derivation(
            "tokens_css_legacy_alias_count",
            "custom-property declarations in tokens.css's own LEGACY ALIASES block",
            tokens_css_legacy_alias_count,
        ),
    )
}


def compute(name: str, root: Path) -> Optional[int]:
    """`REGISTRY[name].compute(root)`, or `None` for a name this registry does not carry.
    Never raises on an unknown name — that is `None`'s job — but a KNOWN name's own
    `compute` is left to raise on a tree it cannot read (a missing file, an unparsable
    block): that failure is itself informative and the caller decides how to report it."""
    entry = REGISTRY.get(name)
    return None if entry is None else entry.compute(root)


def find_markers(text: str):
    """Yield every `MARKER_RE` match in `text`, in order. Pure text, no filesystem —
    the same shape `line_anchor_candidates` keeps in `scripts/docs-audit.py`, so a
    self-test can hand this a string fixture with no document on disk at all."""
    return list(MARKER_RE.finditer(text))
