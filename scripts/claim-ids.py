#!/usr/bin/env python3
"""Allocate the numbers a branch's slug ids will take, and substitute them (D140).

A branch cannot allocate a decision number, because the allocation's only input is what
`main` has taken and that is not knowable until the merge. So a branch writes a SLUG —
a heading of two or more lowercase segments, or a `0.` list marker carrying one — and it runs at the
merge, once, against main as it stands THEN.

PREVIEWS BY DEFAULT. `--write` performs it. Nothing here is clever: the slug is a token that
occurs nowhere else in the tree (measured: zero tokens of either shape existed the day the
vocabulary was chosen), so the substitution is exhaustive text replacement and there is no
judgement in it anywhere. That is the entire argument for doing it at merge time rather than
by hand — a hand renumber is the same edit with a human deciding which occurrences count, and
D140 records what that costs thirteen times over.

`max + 1`, NEVER THE LOWEST FREE ID. D80 culled step 12 and rules that the hole is correct;
reusing it would resurrect every `step 12` in the tree onto a step that is not the one meant.
It also keeps a sorted list sorted, so a slug appended to a `governed_by` list is in the right
place before the claim and after it.

AND IT ANSWERS A SECOND QUESTION, WHICH IT DID NOT UNTIL D140 WAS AMENDED 2026-09-11. Once a
branch has claimed, there is no slug left and this command said `nothing to do` — a true statement about
slugs and an incomplete one about safety, because the number it already allocated can be taken
by main afterwards and nothing looked again. `--stale` is that second look, and the default run
performs it before it writes.

IT WRITES, SO IT IS NOT ON THE COMMIT PATH (D18). The staleness half writes nothing and IS in
`make check`, as its own target. Its self-test is too — `make claim-selftest`, against a
throwaway repository.
"""

from __future__ import annotations

import argparse
import os
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent

# THE VOCABULARY IS DECLARED TWICE ON PURPOSE, HERE AND IN scripts/docs-audit.py, and the
# `claim vocabulary` row reconciles them. The auditor is stdlib-only, parses rather than
# imports, and must not run project code; importing this module would break that promise for
# the one check that gates every commit. Two declarations plus a reader is this repo's
# standing answer to that shape — `port-agreement`, `set-hint-agreement`, `logo`.
SLUG = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)+"
DECISION_SLUG = re.compile(r"\b(D-" + SLUG + r")\b")
CODES_SLUG = re.compile(r"\b(C-" + SLUG + r")\b")
STEP_SLUG = re.compile(r"\bstep (" + SLUG + r")\b")

DECISION_HEADING = re.compile(r"^##\s+D([1-9][0-9]{0,2}|-" + SLUG + r")\b", re.M)
CODES_HEADING = re.compile(r"^##\s+C([1-9][0-9]{0,2}|-" + SLUG + r")\b", re.M)
# The marker a step wears while its number is unclaimed. `0.` is never an id.
GATES_PENDING = re.compile(r"^0\.(\s+`step " + SLUG + r"`)", re.M)
GATES_NUMBERED = re.compile(r"^([1-9][0-9]*)\.\s", re.M)

DECISIONS = "docs/DECISIONS.md"
CODES_DECISIONS = "docs/specs/code-cards.md"
MAP = "docs/map.py"
GATES = "docs/GATES.md"
DEBTS = "docs/debts/README.md"

# DEBTS JOINED THE CLAIM PATH ON THE OWNER'S WORD ("they just get assigned numbers upon
# merge with CI"), REUSING THE DECISION MACHINERY RATHER THAN A SECOND ONE. A debt is a
# DIRECTORY CORPUS exactly like a decision (D160's own shape: one file per entry, a manifest
# recording order) — the two differ only in TWO SPELLINGS, both handled as data rather than
# as a second code path: the CLAIMED heading a decision writes IS its citation form (`## D188`
# cites as `D188`), while a debt's citation has always carried a prefix its heading did not
# (`docs/debts/README.md`: "CITE BY ID, DEBT<n>... never a bare §<n>", while the ~50 real entries
# under `docs/debts/` head themselves bare — `## 11`, not `## DEBT11`). Rather than migrate
# every existing file, a NEWLY CLAIMED entry's heading matches its citation (`## DEBT<n>`),
# and `DEBT_HEADING` below — and `scripts/debts_corpus.py`'s own `HEADING_RE` — read EITHER
# spelling for the ceiling/lookup half, so no existing file moves. The FILENAME keeps the
# bare, unlettered convention every real entry already uses (`188-tail.md`, not
# `DEBT<n>-tail.md`) — `rename_claimed_entries` takes the filename letter as a parameter for
# exactly this asymmetry.
DEBT_HEADING = re.compile(r"^##\s+(?:DEBT)?([1-9][0-9]{0,2})\b", re.M)

# THE THREE NAMESPACES, DECLARED ONCE AND READ TWICE. `ceiling_at` asks each for its highest
# allocated id and `stale_claims` asks the same three for their whole sets. Spelling the list
# out at both call sites is how a fourth namespace arrives in one of them and not the other,
# which is the shape `storage keys` and `codex hooks` both exist to catch elsewhere in this
# repo. The last field is the form a person READS the id in, which is also the token every
# citation of it carries.
#
# DEBT IS THE FOURTH, AND A DIRECTORY-CORPUS KIND LIKE `decision` — `ceiling_at`, `pending`,
# `stale_claims` and `duplicate_numbers` each special-case the two kinds whose corpus is a
# directory rather than reading `path` as a flat file, exactly as `decision` already needed
# before `debt` existed.
KINDS = (
    ("decision", DECISIONS, DECISION_HEADING, "D{0}"),
    ("codes", CODES_DECISIONS, CODES_HEADING, "C{0}"),
    ("step", GATES, GATES_NUMBERED, "step {0}"),
    ("debt", DEBTS, DEBT_HEADING, "DEBT{0}"),
)

# A DIRECTORY-CORPUS KIND'S OWN SHAPE, ONE ROW PER KIND, READ BY EVERY FUNCTION BELOW THAT
# USED TO SAY "decision" BY NAME. `unclaimed_letter` is the literal text a PENDING heading
# wears after `## ` (`D-<slug>`, `DEBT-<slug>`) — `unclaimed_from_pieces`'s own `letter`
# argument. `filename_letter` is what a CLAIMED entry's file is renamed to carry in front of
# its zero-padded number (`D` for a decision, `` for a debt — see the block comment above
# `DEBT_HEADING`).
class DirKind(NamedTuple):
    kind: str
    directory: str
    manifest: str
    stub: str
    unclaimed_letter: str
    filename_letter: str
    index_stub: str   # the file carrying the rendered INDEX BLOCK, never the corpus's own
                       # pointer stub — a decision's index lives in CLAUDE.md, a debt's in
                       # its own `docs/debts/README.md` (the two coincide for debt, not for decision)


DIR_KINDS = {
    "decision": DirKind("decision", "docs/decisions",
                        "docs/decisions/ORDER.json", DECISIONS, "D", "D", "CLAUDE.md"),
    "debt": DirKind("debt", "docs/debts", "docs/debts/ORDER.json", DEBTS, "DEBT", "",
                    "docs/debts/README.md"),
}

# EVERY DIRECTORY-CORPUS KIND KEEPS ITS SLUG SOMEWHERE ONCE CLAIMED — its entry's own
# FILENAME, per `rename_claimed_entries` — unlike a codes id or a build step, which keep it
# nowhere and need `--unclaim ... --to-slug`. Read wherever a message branches on that.
DIR_KEEPS_SLUG = frozenset(DIR_KINDS)

# Binary and generated trees the substitution has no business walking. `.git` is the one that
# would be catastrophic rather than merely slow.
SKIP = {".git", "node_modules", "dist", "dist-demo", "captures", "inventory", "runs",
        "__pycache__", ".venv", "venv", "test-results", "playwright-report", ".serve",
        "worktrees", "demo-assets", "harness/images"}
# `.js` JOINED THE SET ON THE FIRST BRANCH TO NEED IT, which is this mechanism working rather
# than failing. `app/eslint.config.js` cites decisions in its own comments — six of them today,
# and `docs/map.py` lists them under its `governed_by` — so a branch writing a SLUG there had it
# survive the claim silently, and main would carry a citation of an id that does not exist.
# `.mjs` was already here and `.js` was not, which is an omission rather than a rule: nothing
# about a config file makes its citations less real than a script's.
#
# THE GUARD COULD NOT SEE IT EITHER, which is why both moved together. `docs-audit.py`'s
# `id claims` row walks its own set and gained `.js` in the same change — the invariant this
# whole design rests on is MAIN CARRIES NO SLUG, and a file neither the claimer nor the guard
# opens is a file that invariant is not actually asserted over.
TEXT_SUFFIXES = {".md", ".py", ".ts", ".tsx", ".css", ".html", ".json", ".txt", ".yml",
                 ".yaml", ".sh", ".js", ".mjs", ".toml"}

# AND A GIT HOOK HAS NO SUFFIX AT ALL, which is the same hole one shape further along. The
# five files `make hooks` installs are shell with no extension, so a suffix set can never
# reach them — `scripts/githooks/post-checkout` cited a slug on 2026-09-12 and the claim
# walked straight past it, leaving a citation `id claims` would have had to call unclaimed
# on main. They are named rather than pattern-matched: the roster is five, `hook roster`
# reconciles it against docs/map.py, and a sixth hook arriving is a commit that fails there.
HOOK_DIR = "scripts/githooks"


class Claim(NamedTuple):
    kind: str      # "decision" | "codes" | "step" | "debt"
    slug: str      # the unclaimed form, with its letter for D and C and bare for a step
    number: str    # the allocated form: a letter and digits, or a bare number for a step
    token: str     # the exact text replaced
    becomes: str   # the exact text written


def say(*lines: str) -> None:
    for line in lines:
        print(line)


def git(*args: str, cwd: Optional[str] = None, input_bytes: Optional[bytes] = None) -> str:
    try:
        done = subprocess.run(["git"] + list(args), cwd=cwd or str(ROOT), input=input_bytes,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    except OSError:
        return ""
    return done.stdout.decode("utf-8", errors="replace")


def blobs_at(rev: str, paths: Sequence[str], cwd: Optional[str] = None) -> List[str]:
    """`git show rev:path` for every path, in ONE `cat-file --batch` process rather than one
    per file (a corpus read was ~1,200 processes). A missing path answers "", as `git` does."""
    try:
        done = subprocess.run(["git", "cat-file", "--batch"], cwd=cwd or str(ROOT),
                              input="".join(f"{rev}:{p}\n" for p in paths).encode("utf-8"),
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    except OSError:
        return [""] * len(paths)
    out, at, blobs = done.stdout, 0, []
    try:
        for _ in paths:
            header_end = out.index(b"\n", at)
            header = out[at:header_end].split()
            at = header_end + 1
            if header[-1].isdigit():  # any object has a body: blob, tree or commit
                size = int(header[-1])
                blobs.append(out[at:at + size].decode("utf-8", errors="replace")
                             if header[-2] == b"blob" else "")
                at += size + 1
            else:  # `missing`, `ambiguous`
                blobs.append("")
    except (ValueError, IndexError):
        return [""] * len(paths)
    return blobs


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def ignored_paths(root: Path, paths: Sequence[Path]) -> Set[Path]:
    """Every path in `paths` that git ignores, asked in ONE call rather than one per file.

    `SKIP` prunes a fixed, hand-typed list of directory NAMES, which is a performance floor
    rather than a correctness claim — it has no way to know about a directory `.gitignore`
    names but nobody thought to type here. `demo`, `app/demo` and `app/public/demo` are
    gitignored (D295, docs/specs/demo.md) and none of them were in `SKIP`, so a branch that
    had built the demo locally handed `text_files()` two 24-133 MB JSON bundles it had no
    business reading — gitignored build output, never a source a citation could live in.

    `git check-ignore --no-index` is asked rather than `git ls-files`, because `--no-index`
    answers from `.gitignore` alone and does not care whether the path has ever been staged —
    a freshly generated file that is gitignored answers the same as one nobody has touched in
    years. FAILS OPEN: no git, or `root` outside a checkout, answers with no ignored paths at
    all, because a text file this cannot classify is a text file the walk already knew how to
    read before this existed.
    """
    if not paths:
        return set()
    rels = [str(p.relative_to(root)) for p in paths]
    out = git("check-ignore", "--no-index", "-z", "--stdin", cwd=str(root),
              input_bytes=("\0".join(rels) + "\0").encode("utf-8"))
    if not out:
        return set()
    return {root / rel for rel in out.split("\0") if rel}


def text_files(root: Path) -> List[Path]:
    """Every tracked-looking text file under `root`, excluding the trees SKIP names and
    whatever git ignores.

    A DOTTED DIRECTORY IS NOT SKIPPED FOR BEING DOTTED. `SKIP` names the trees to prune, the
    same way `docs_audit/core.py`'s own `SKIP_DIRS` does — by name, never by a leading dot — and
    until this line `dirs[:] = ... and not d.startswith(".")` pruned every one of them anyway,
    `.claude/` included. `docs-audit.py`'s `decision ids` row DOES read `.claude/skills/`
    (`markdown_files()`'s own `_walk` has no such filter), so a slug cited there survived a
    claim commit unrewritten and `make check` refused PR #462's merge over the dangling
    citation (commits 34c54259/eaef7ce7). `decision_id_code_haystack()` in that file is the reader whose
    coverage this walk must be a superset of — proved in `scripts/claim-selftest.py`. `.git`,
    `.venv`, `venv` and `.serve` stay excluded because they are named in `SKIP`, not because
    they start with a dot.

    `SKIP` IS A PERFORMANCE FLOOR, NOT A CORRECTNESS CLAIM, and `ignored_paths` is the
    correctness half. `demo`, `app/demo` and `app/public/demo` are gitignored build output
    (D295) that nobody had typed into `SKIP`, so a branch that had built the demo locally
    handed every caller of this walk two 24-133 MB JSON bundles to read for citations they
    could never hold — the owner's ruling, 2026-09-27: this walk skips what git ignores.
    """
    out: List[Path] = []
    for base, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP)
        for name in sorted(names):
            path = Path(base) / name
            # A SYMLINK IS THE SAME FILE (D47, D135). `AGENTS.md -> CLAUDE.md` is tracked, and
            # walking both rewrites CLAUDE.md twice and reports it under a path git stores as
            # a link rather than as text. The real file is walked in its own right.
            if path.is_symlink():
                continue
            if path.suffix in TEXT_SUFFIXES:
                out.append(path)
                continue
            # An extensionless file directly under scripts/githooks is a hook: shell that
            # `make hooks` copies into the common git dir, and text like any other here.
            if path.parent.as_posix().endswith(HOOK_DIR) and not path.suffix:
                out.append(path)
    ignored = ignored_paths(root, out)
    return [p for p in out if p not in ignored]


# --------------------------------------------------------------------- what main has taken


def allocated_ids(text: str, pattern: re.Pattern) -> Set[int]:
    """Every ALLOCATED id in `text`. A slug heading is not a number and is skipped.

    THE SET AND NOT ONLY THE MAXIMUM, because a hole in the sequence is real and ruled correct:
    D80 culled step 12 and keeps the gap, so `max` can say what the next id is but cannot say
    whether a GIVEN id is free. The staleness half needs the second question answered.
    """
    return {int(m) for m in pattern.findall(text) if str(m).lstrip("-").isdigit()}


def highest(text: str, pattern: re.Pattern) -> int:
    """The largest allocated id in `text`, or 0. Slug headings are not numbers and are skipped."""
    found = allocated_ids(text, pattern)
    return max(found) if found else 0


def kind_text_at(kind: str, path: str, ref: str, cwd: Optional[str] = None) -> str:
    """One `KINDS` row's own corpus text, as of `ref` — a DIRECTORY (`DIR_KINDS`) read
    through `corpus_text_at`, or a flat file read straight with `git show`.

    ONE DISPATCH, USED BY EVERY READER BELOW THAT USED TO SPECIAL-CASE `kind == "decision"`
    BY NAME. `debt` joined the claim path reusing this exact branch (D160's directory-corpus
    shape, not a second one) — a THIRD directory kind needs no new `if` here, only a `DIR_KINDS`
    entry.
    """
    if kind in DIR_KINDS:
        d = DIR_KINDS[kind]
        return corpus_text_at(ref, cwd=cwd, directory=d.directory, manifest=d.manifest,
                              stub=d.stub)
    return git("show", f"{ref}:{path}", cwd=cwd)


def kind_text(kind: str, root: Path) -> str:
    """`kind_text_at`'s own question, over a working tree instead of a ref."""
    if kind in DIR_KINDS:
        d = DIR_KINDS[kind]
        return corpus_text(root, d.directory, d.manifest, d.stub)
    path = next(p for k, p, _, _ in KINDS if k == kind)
    return read(root / path) if (root / path).exists() else ""


def ceiling_at(ref: str, cwd: Optional[str] = None) -> Dict[str, int]:
    """The highest allocated id of each kind, as of `ref`.

    READ FROM THE REF AND NEVER FROM THE WORKING TREE. The whole point is to allocate against
    what main holds at the moment of the merge; allocating against the branch's own copy is
    the guess this entry exists to delete.
    """
    return {kind: highest(kind_text_at(kind, path, ref, cwd=cwd), pattern)
            for kind, path, pattern, _ in KINDS}


# ------------------------------------------------------------------------- what is unclaimed


# RECOGNITION IS BY THE COMPLEMENT, NOT BY SLUG'S OWN SHAPE. `DECISION_HEADING`/`CODES_HEADING`
# accept a NUMBER or a proper two-segment lowercase SLUG and nothing else, which would ALSO
# miss a heading whose slug is merely irregular: mixed case, a doubled hyphen, a digit where
# a letter was meant. An unrecognised `D`-prefixed heading must refuse, never pass silently,
# so `unclaimed_from_pieces`/`unclaimed_from_flat` ask the complement instead: does this
# heading open `<letter><digit-or-hyphen>` and fail to be a clean, unpadded number? If so it
# is unclaimed, whatever shape the rest of it is in — a defense the real 2026-09-20 incident
# (below, `corpus_order_at`) did not itself need, since its slug was properly shaped, but
# which the next one may.
_NUMBER = re.compile(r"^[1-9][0-9]*$")


def unclaimed_from_pieces(pieces: List[str], letter: str) -> List[str]:
    """The unclaimed id on each entry's OWN FIRST heading, for a corpus split one file per
    entry (decisions, since D160).

    SCOPED TO THE FIRST LINE OF EACH FILE, NEVER ANY `##` LINE FURTHER DOWN. An entry can
    hold an internal subsection that also starts with the letter — a section file whose
    only heading is `## Deferred — argued, not gated: …` starts with `D` — and
    scanning every `##` line in the corpus rather than each file's own first would report
    that as a second unclaimed decision beside itself. `Deferred` does not match here because
    the character right after `D` is `e`, neither a digit nor a hyphen.
    """
    pattern = re.compile(r"^##\s+" + letter + r"([0-9-]\S*)")
    out: List[str] = []
    for piece in pieces:
        first = piece.split("\n", 1)[0]
        match = pattern.match(first)
        if not match:
            continue
        token = match.group(1)
        if not _NUMBER.fullmatch(token):
            out.append(letter + token)
    return out


def unclaimed_from_flat(text: str, letter: str) -> List[str]:
    """`unclaimed_from_pieces`'s own question, for a corpus that stays ONE shared file
    (the code-card ledger; decisions before D160). Every line starting `## <letter><digit-or-
    hyphen>` really is its own entry heading there, so scanning every line carries none of
    the subsection risk `unclaimed_from_pieces` guards against.
    """
    pattern = re.compile(r"^##\s+" + letter + r"([0-9-]\S*)", re.M)
    return [letter + token for token in pattern.findall(text) if not _NUMBER.fullmatch(token)]


def pending_in(decisions: str, codes: str, gates: str,
                decision_pieces: Optional[List[str]] = None,
                debt_pieces: Optional[List[str]] = None) -> Dict[str, List[str]]:
    """Every slug HEADING in these three texts, by kind, in the order they declare them.

    `debt_pieces` IS THE SAME SPLIT-CORPUS ANSWER AS `decision_pieces`, one namespace over.
    `docs/debts/` has carried a manifest from day one on this branch (D160's own shape,
    never a pre-split flat-file era to fall back on), so `debt_pieces` is `None` only when
    the checkout has no `docs/debts/ORDER.json` at all — a fixture that never wrote one, or
    this file imported against a tree that predates debts joining the claim path.

    Headings rather than citations: a citation of a slug that has no heading is a dangling
    id, which is `id claims`' job to report and not this command's to invent an entry for.

    TEXTS RATHER THAN A DIRECTORY, SO THE SAME READER CAN BE POINTED AT A COMMIT. `pending`
    hands it a working tree and `pending_at` hands it `git show` output, and the grammar is
    declared once for both. A second declaration of these three patterns is how a heading
    shape that one reader accepts becomes one the other cannot see.

    `decision_pieces`, WHEN GIVEN, IS THE SPLIT CORPUS'S OWN ANSWER (`unclaimed_from_pieces`)
    AND `decisions` IS IGNORED FOR THAT KIND. `None` means there is no split corpus at all —
    the pre-D160 shape, one flat `docs/DECISIONS.md` — and that path keeps `DECISION_HEADING`'s
    narrower, SLUG-only match on purpose: a one-segment heading pasted into that flat file's
    prose (`D-pad`) is deliberately not an id, `docs-audit`'s `id claims` row is what reports
    it as unreachable, and a real per-file entry cannot be shaped that way to begin with —
    D160's own naming convention already forces a multi-segment slug at file-creation.
    """
    out: Dict[str, List[str]] = {"decision": [], "codes": [], "step": [], "debt": []}
    if decision_pieces is not None:
        out["decision"] = unclaimed_from_pieces(decision_pieces, "D")
    else:
        out["decision"] = [f"D{i}" for i in DECISION_HEADING.findall(decisions) if i.startswith("-")]
    out["codes"] = unclaimed_from_flat(codes, "C")
    out["step"] = re.findall(r"^0\.\s+`step (" + SLUG + r")`", gates, re.M)
    if debt_pieces is not None:
        out["debt"] = unclaimed_from_pieces(debt_pieces, "DEBT")
    for kind in out:
        seen: List[str] = []
        for slug in out[kind]:
            if slug not in seen:
                seen.append(slug)
        out[kind] = seen
    return out


# ------------------------------------------------------------- the corpus is a directory

# THE DECISION CORPUS IS `docs/decisions/`, ONE FILE PER ENTRY, and `docs/DECISIONS.md` is a
# stub. Everything below reads the same TEXT it always did — the entries concatenated in
# `ORDER.json`'s order — so the allocation, the ceiling and the staleness question are
# unchanged. What is new is the RENAME: a claim used to be a substitution and nothing else,
# and now the file holding the entry is named after the id it no longer carries.
#
# READ FAIL-SOFT, AND THAT IS NOT COSMETIC HERE. An unreadable corpus must look like NO
# UNCLAIMED SLUG rather than like an empty one — the invariant is "main carries no slug", and
# a reader that returned "" on error would report every branch as clean and let an unclaimed
# heading through the merge. That is the failure that turned main red on 2026-09-12, arriving
# by a different road.
DECISIONS_DIR = "docs/decisions"
DECISIONS_MANIFEST = DECISIONS_DIR + "/ORDER.json"


def corpus_order(root: Path, directory: str = DECISIONS_DIR,
                 manifest: str = DECISIONS_MANIFEST) -> List[str]:
    """Corpus membership: the manifest's list, then anything on disk it has not been told of.

    DERIVED, BECAUSE A BRANCH DOES NOT EDIT THE MANIFEST. An entry-adding branch carries its
    own file and nothing shared — `settle_corpus` writes the manifest at claim time. A
    claimer reading only the manifest would therefore be blind to exactly the entry it exists
    to claim, which is how this was found: an unregistered slug reported `nothing to claim`
    while sitting in the directory.

    `directory`/`manifest` ARE PARAMETERS, NOT A SECOND FUNCTION, because a debt corpus asks
    this exact question of `docs/debts/` — same manifest shape, same derivation — and the
    default keeps every existing decision call site unchanged.
    """
    manifest_path = root / manifest
    if not manifest_path.exists():
        return []
    listed = json.loads(read(manifest_path))["order"]
    known = set(listed)
    extra = sorted(p.name for p in (root / directory).glob("*.md")
                   if p.name not in known and p.name != "README.md")
    return listed + extra


def corpus_pieces(root: Path, directory: str = DECISIONS_DIR,
                  manifest: str = DECISIONS_MANIFEST) -> Optional[List[str]]:
    """Each entry's own file text, in corpus order. `None` when there is no split corpus at
    all (no manifest) — the caller's cue to fall back to the flat stub file.
    """
    if not (root / manifest).exists():
        return None
    return [read(root / directory / name)
            for name in corpus_order(root, directory, manifest)
            if (root / directory / name).exists()]


def corpus_text(root: Path, directory: str = DECISIONS_DIR,
                manifest: str = DECISIONS_MANIFEST, stub: str = DECISIONS) -> str:
    """The entries of a working tree, concatenated in corpus order."""
    pieces = corpus_pieces(root, directory, manifest)
    if pieces is None:
        return read(root / stub) if (root / stub).exists() else ""
    return "\n".join(pieces)


def corpus_order_at(rev: str, cwd: Optional[str] = None, directory: str = DECISIONS_DIR,
                    manifest: str = DECISIONS_MANIFEST) -> List[str]:
    """`corpus_order`'s own question, asked of a REF instead of a working tree.

    A REF HAS NO WORKING DIRECTORY TO `Path.glob` OVER, so `corpus_order`'s trick — list the
    manifest, then add whatever the directory holds that the manifest does not name — has to
    be done with `git ls-tree` instead of a glob. Skipping this and trusting the manifest
    ALONE is exactly the shape that let a real, correctly-slugged entry reach `origin/main`
    on 2026-09-20 unclaimed and invisible: the file was on that commit's own tree, the
    manifest never named it (by design — `settle_corpus` writes the manifest at CLAIM time,
    so an entry-adding branch never touches it), and `report_landed`/`landed_half` — the one
    reader whose whole job is asking a REF what it carries — read the manifest's list alone
    and reported the commit clean.
    """
    manifest_text = git("show", f"{rev}:{manifest}", cwd=cwd)
    listing = git("ls-tree", "-r", "--name-only", rev, "--", directory, cwd=cwd)
    on_disk = sorted(Path(p).name for p in listing.splitlines()
                     if p.endswith(".md") and Path(p).name != "README.md")
    if not manifest_text.strip():
        return on_disk
    try:
        listed = json.loads(manifest_text)["order"]
    except Exception:
        return on_disk
    known = set(listed)
    extra = sorted(name for name in on_disk if name not in known)
    return listed + extra


def corpus_pieces_at(rev: str, cwd: Optional[str] = None, directory: str = DECISIONS_DIR,
                     manifest: str = DECISIONS_MANIFEST) -> Optional[List[str]]:
    """`corpus_pieces`'s own question, asked of a REF. `None` when that rev has no split
    corpus at all (pre-D160, or the manifest blob does not exist there).
    """
    manifest_text = git("show", f"{rev}:{manifest}", cwd=cwd)
    if not manifest_text.strip():
        return None
    names = corpus_order_at(rev, cwd=cwd, directory=directory, manifest=manifest)
    return blobs_at(rev, [f"{directory}/{name}" for name in names], cwd=cwd)


def corpus_text_at(rev: str, cwd: Optional[str] = None, directory: str = DECISIONS_DIR,
                   manifest: str = DECISIONS_MANIFEST, stub: str = DECISIONS) -> str:
    """The entries AT A COMMIT, concatenated in that commit's own corpus order.

    Falls back to that commit's flat stub file when it has no manifest, which is every
    commit before the split — so `ceiling_at` and `pending_at` keep answering across the
    boundary rather than reporting a repository with no entries in it.
    """
    pieces = corpus_pieces_at(rev, cwd=cwd, directory=directory, manifest=manifest)
    if pieces is None:
        return git("show", f"{rev}:{stub}", cwd=cwd)
    return "\n".join(pieces)


def pending(root: Path) -> Dict[str, List[str]]:
    """`pending_in` over a working tree."""
    return pending_in(
        corpus_text(root),
        read(root / CODES_DECISIONS) if (root / CODES_DECISIONS).exists() else "",
        read(root / GATES) if (root / GATES).exists() else "",
        decision_pieces=corpus_pieces(root),
        debt_pieces=corpus_pieces(root, DIR_KINDS["debt"].directory, DIR_KINDS["debt"].manifest),
    )


def pending_at(rev: str, cwd: Optional[str] = None) -> Dict[str, List[str]]:
    """`pending_in` over a COMMIT, which is a different question from the one above.

    Every other reader in this file asks about a checkout. This one asks what a commit
    CARRIES, and it exists because the invariant the whole design rests on — main carries no
    slug — is a claim about main's own trees and not about anybody's working directory. A
    file missing at that commit reads as empty, which is right: a repository with no
    docs/specs/code-cards.md has no unclaimed code-card id in it.
    """
    debt = DIR_KINDS["debt"]
    return pending_in(
        corpus_text_at(rev, cwd=cwd),
        git("show", f"{rev}:{CODES_DECISIONS}", cwd=cwd),
        git("show", f"{rev}:{GATES}", cwd=cwd),
        decision_pieces=corpus_pieces_at(rev, cwd=cwd),
        debt_pieces=corpus_pieces_at(rev, cwd=cwd, directory=debt.directory,
                                     manifest=debt.manifest),
    )


def plan(root: Path, ref: str, cwd: Optional[str] = None) -> List[Claim]:
    """(slug -> number) for every unclaimed id, allocated max+1 against `ref`."""
    ceiling = ceiling_at(ref, cwd=cwd)
    claims: List[Claim] = []
    for kind, slugs in pending(root).items():
        nxt = ceiling[kind]
        for slug in slugs:
            nxt += 1
            if kind == "step":
                claims.append(Claim(kind, slug, str(nxt), f"step {slug}", f"step {nxt}"))
            else:
                # THE CLAIMED LETTER IS THE SLUG'S FIRST CHARACTER FOR `decision`/`codes`
                # (`D-foo` -> `D`, `C-foo` -> `C`), BUT NOT FOR `debt`: its unclaimed slug is
                # `DEBT-<slug>`, and `slug[0]` alone would give the wrong, one-letter prefix
                # (`D188` instead of `DEBT<n>`) — see the block comment above `DEBT_HEADING`
                # for why a debt's heading/citation letter is a whole word, not one letter.
                letter = DIR_KINDS[kind].unclaimed_letter if kind in DIR_KINDS else slug[0]
                claims.append(Claim(kind, slug, f"{letter}{nxt}", slug, f"{letter}{nxt}"))
    return claims


# ------------------------------------------------------ a claimed number that has gone stale

# THE CLAIMER IS A NO-OP ONCE A BRANCH HAS CLAIMED, AND THAT IS THE GAP THIS HALF CLOSES.
# `plan` reads SLUGS, so a branch already holding an allocated number has nothing pending and
# the command printed `no unclaimed slug in this tree — nothing to do.` That is a true
# statement about slugs and an incomplete one about safety: the number it allocated can be
# taken by main afterwards, and nothing looked again.
#
# TWICE IN ONE EVENING, 2026-09-11, and both times a PERSON was the mechanism. PR #262 and
# PR #265 both held one number; #262 merged first and #265 re-claimed, caught before the merge
# at the cost of a re-claim. Then #265 and #270 both held the next one; #265 merged first and
# #270 had to renumber, caught only because a session read another session's PR title. The
# numbers themselves are incidental and are deliberately not spelled here — a spelled id in a
# comment is a CITATION, which is the rule D140 learned by having its own auditor's fixture
# eaten by a claim. The asymmetry is
# the argument: the first was luck with a small cost, the second was luck with no cost at all.
# `decision index` does catch this, but it catches it by failing the COMMIT of whichever
# branch is unlucky, after two headings carry one number — loud, late, and paid by whoever
# happened to merge second.
#
# IT REPORTS AND IT NEVER REPAIRS. An un-claim has to happen BEFORE a merge and never after:
# once main is merged in, a substitution on that token reaches main's own copy of the entry
# too. So this names the collision, says what the id would become, and exits non-zero so it
# can gate. What to do about it is a person's call, or `make merge`'s.
#
# NO NETWORK AND NO `gh` ON THIS PATH. The local `origin/main` ref is enough, and D140 records
# the rejection of reading OPEN pull requests deliberately. This half does not need them: an
# open PR's number is not yet a fact about main, and the branch that merges SECOND is the one
# that has to move — so the case that actually bites is the one where the other branch has
# already LANDED, which is exactly what a ref read can see.


class Stale(NamedTuple):
    kind: str      # "decision" | "codes" | "step" | "debt"
    taken: str     # the id as a person reads it: `D140`, `C11`, `step 23`
    becomes: str   # what it would be allocated if it went back to being a slug
    where: str     # the file whose headings were read


def merging(cwd: Optional[str] = None) -> bool:
    """Whether a merge is in progress and uncommitted.

    WHAT THE BRANCH ADDS IS NOT ANSWERABLE HERE, and answering anyway reports a collision the
    reader cannot act on. Mid-merge the working tree already holds the other side's entries
    while the merge base has NOT moved, so every id the other side added reads as this
    branch's own and every one of them is on the ref by definition. The advice would be to
    un-claim an id that belongs to somebody else's merged work.

    IT IS THE DOCUMENTED PRE-MERGE STEP THAT PRODUCES IT, which is what makes this worth a
    guard rather than a footnote: fetch, merge `origin/main`, resolve, push is the routine
    every branch runs before it is merged, and `make claim-stale` is in `make check`. Measured
    on this entry's own branch while it resolved a merge: one refusal naming an id that main
    had merged an hour earlier. The number is not spelled here on purpose — an id in a comment
    is a CITATION, and this one is somebody else's entry passing through. Committing the merge
    moves the base and clears it.
    """
    return bool(git("rev-parse", "--verify", "--quiet", "MERGE_HEAD", cwd=cwd).strip())


def merge_base(ref: str, cwd: Optional[str] = None) -> str:
    """The commit `ref` and HEAD share — what `git diff <ref>...HEAD` measures from.

    THE BASELINE IS THE MERGE BASE AND NOT THE REF, and getting that backwards is the one way
    to write this check so that it cannot see its own subject. Asking what the branch adds
    relative to the ref's CURRENT content answers nothing: an id the ref has just taken reads
    as already present on both sides, every collision cancels itself out, and the check
    reports clean forever while being exactly as green as it was before it existed.
    """
    return git("merge-base", ref, "HEAD", cwd=cwd).strip()


def stale_claims(root: Path, ref: str, base: str, cwd: Optional[str] = None) -> List[Stale]:
    """Allocated ids this branch ADDS since `base` that `ref` has taken in the meantime.

    ADDS, NEVER HOLDS. Every id main already had is in the branch's copy too, so reporting
    what the branch merely holds would report most of the file. The difference against the
    merge base is exactly the set this branch is claiming to own.

    THE WORKING TREE IS THE BRANCH'S SIDE, matching `pending` rather than introducing a second
    answer about where the branch's ids live. At the merge the two are identical — `make
    merge` refuses a dirty tree before it reaches this — and before the commit the working
    tree is the earlier warning.

    `becomes` IS ADVISORY AND NOTHING WRITES IT. It is what the id would be allocated if it
    went back to a slug and were claimed alone; a branch carrying pending slugs as well
    interleaves with them, and the claim at merge time is what actually decides.

    A DECISION READS THE CORPUS, NEVER THE STUB, matching `ceiling_at` and `pending` rather
    than introducing a third answer about where a decision's ids live. `docs/DECISIONS.md` is
    `docs/decisions/`'s pointer since D160 and carries no `## D<id>` heading at all, so reading
    it directly — which this function did until it was found here — sees an empty set on
    every side of every comparison and reports every decision collision as clean. That is not
    a theoretical gap: found while reproducing the 2026-09-12 incident this file's `--unclaim`
    exists to answer — a branch's own claimed number colliding with an unrelated entry
    (D186's own merge landed over this exact race) — where this function's own CHEAP early
    warning had silently stopped firing for the one namespace the incident was in —
    `decision index`'s loud, late backstop, and a person reading PR titles, were the only
    things left to catch it. `corpus_text`/`corpus_text_at` fall back to the flat file when
    there is no manifest, so this is backward-compatible with a pre-split tree and changes
    nothing there.
    """
    out: List[Stale] = []
    ceiling = ceiling_at(ref, cwd=cwd)
    for kind, path, pattern, shape in KINDS:
        here = kind_text(kind, root)
        was = kind_text_at(kind, path, base, cwd=cwd)
        now = kind_text_at(kind, path, ref, cwd=cwd)
        added = allocated_ids(here, pattern) - allocated_ids(was, pattern)
        taken = allocated_ids(now, pattern)
        nxt = ceiling[kind]
        for number in sorted(added & taken):
            nxt += 1
            out.append(Stale(kind, shape.format(number), shape.format(nxt), path))
    return out


def report_stale(stale: Sequence[Stale], ref: str) -> None:
    """Name every collision, say what it would become, and say why nothing was rewritten."""
    say(f"REFUSED: {len(stale)} id(s) this branch adds are already taken on `{ref}`.", "")
    for item in stale:
        say(f"  {item.taken}  is taken on {ref}  —  this branch's own would become "
            f"{item.becomes}",
            f"      {item.where}")
    say("",
        "  The number was allocated against a `main` that did not hold it yet, and `main` has",
        "  moved since. NOTHING HAS BEEN REWRITTEN FOR YOU, on purpose: an un-claim has to",
        "  happen BEFORE the merge and never after, because once main is merged in a",
        "  substitution on that token reaches main's own copy of the entry too.",
        "",
        "  Put it back to slug form and let a fresh plan allocate it again:",
        "")
    for item in stale:
        if item.kind in DIR_KEEPS_SLUG:
            say(f"    python3 scripts/claim-ids.py --unclaim {item.taken} --write")
        else:
            say(f"    python3 scripts/claim-ids.py --unclaim '{item.taken}' "
                "--to-slug <the-original-slug> --write",
                f"      (the slug {item.kind} used before it was claimed — a codes id or a "
                "step keeps it nowhere once claimed, unlike a decision's own filename)")
    say("",
        "  Then `python3 scripts/claim-ids.py --ref {0}` previews what it would take against"
        .format(ref),
        "  main as it stands now.")


# ----------------------------------------------------- one number, worn twice in this tree

# `stale_claims` GOES BLIND AT EXACTLY THE MOMENT THE ROUTINE SAYS TO MERGE MAIN IN, and this
# is the reader that does not. That check is a DIFFERENCE — ids the branch adds since the
# merge base, against ids the ref has taken. Merge `origin/main` into the branch and the base
# MOVES TO IT: main's colliding entry is now on both sides, the branch "adds" nothing at that
# number, and the collision it was refusing five minutes earlier reports clean. Measured in
# the fixture that reproduces the 2026-09-19 race, which is the incident this whole section
# was written for: `--stale` said `nothing has gone stale` over a tree holding two entries
# under one number.
#
# IT NEEDS NO REF AND NO BASE, WHICH IS WHY IT CANNOT BE BLINDED. Two headings carrying one
# id is wrong on its own terms, however the tree got that way — `docs-audit`'s `decision ids`
# row says exactly that and blocks the commit for it. This asks the same question in the one
# place that is EARLY: `make merge` reads the staleness half before it claims anything, so a
# branch that merged main in and lost a race is refused here, by name, with the remedy that
# now runs, rather than by CI after the claim has been pushed.
#
# IT IS A SECOND READER OF ONE RULE AND NOT A SECOND RULE. `decision ids` stays the gate; it
# is loud, late, and paid by whoever merges second. This is the cheap early warning, the same
# division of labour `stale_claims`' own docstring sets out.


def duplicate_numbers(root: Path) -> List[Tuple[str, int]]:
    """`(token, how many headings carry it)` for every id this tree declares more than once."""
    out: List[Tuple[str, int]] = []
    for kind, _path, pattern, shape in KINDS:
        text = kind_text(kind, root)
        counts: Dict[int, int] = {}
        for found in pattern.findall(text):
            if str(found).lstrip("-").isdigit():
                counts[int(found)] = counts.get(int(found), 0) + 1
        for number in sorted(n for n, c in counts.items() if c > 1):
            out.append((shape.format(number), counts[number]))
    return out


def report_duplicate_numbers(doubled: Sequence[Tuple[str, int]], ref: str) -> None:
    """Name every id worn twice, and the one command that puts this branch's own back."""
    say(f"REFUSED: {len(doubled)} id(s) are declared twice in this tree.", "")
    for token, count in doubled:
        say(f"  {token}  has {count} headings")
    say("",
        "  THIS IS A LOST RACE WITH main ALREADY MERGED IN. The number was allocated against",
        f"  a `{ref}` that did not hold it, `{ref}` took it for a different entry, and the",
        "  merge brought that entry here beside this branch's own. `--stale` cannot see it:",
        "  the merge moved the base it measures from, so neither copy reads as added.",
        "",
        "  Put THIS branch's own back to slug form and let a fresh plan allocate it:",
        "")
    for token, _ in doubled:
        if token.startswith("D"):
            say(f"    python3 scripts/claim-ids.py --unclaim {token} --write")
        else:
            say(f"    python3 scripts/claim-ids.py --unclaim '{token}' "
                "--to-slug <the-original-slug> --write")
    say("",
        f"  It reads `{ref}` to tell the two apart — whichever entry `{ref}` carries is",
        f"  `{ref}`'s, and every line `{ref}` already has is left alone.")


# ------------------------------------------- an unclaimed file main has already claimed once

# `stale_claims` ANSWERS "A NUMBER THIS BRANCH TOOK, TAKEN AGAIN" — it needs the branch to have
# claimed first. This answers a different question: a slug this branch has NOT claimed yet,
# that `ref` has already claimed under some OTHER number, via a branch that never passed
# through here at all. `plan()` cannot see it either — it only asks what number is FREE on
# `ref`, never whether `ref` has already resolved this exact slug under a different one.
#
# THE CORPUS IS A DIRECTORY (D160), so a claim is a RENAME: `docs/decisions/D-<slug>.md`
# becomes `docs/decisions/D<n>-<slug>.md`. Two branches that both still carry the unclaimed
# file — because neither had merged the other's claim back in yet — can each rename it under
# a DIFFERENT number without either one's `plan()` ever looking at the other's tree. This is
# exactly what happened on 2026-09-12: #329 claimed a stranded slug as D185, and #330 — cut
# earlier and never merged forward — claimed the identical unclaimed file as the very next number in a `make
# merge` run of its own, producing a rename/rename collision `stale_claims` cannot see (no
# number this branch added was ever taken on `ref`; the number it picked was free) and that
# surfaced only as a
# GitHub merge conflict after the claim commit had already been pushed.
#
# MATCHED BY THE SLUG TEXT, NOT THE PATH: the unclaimed file and its claimed twin differ only
# in the leading `D` vs `D<n>`, so stripping that prefix and comparing what remains is the
# whole test. `ref`'s tree is read with `git ls-tree`, never a fetch — this runs on the same
# local ref every other reader here does.


def duplicate_pending(root: Path, ref: str, cwd: Optional[str] = None) -> List[Tuple[str, str]]:
    """(pending slug, the number `ref` already claimed it under) for every DIRECTORY-CORPUS
    slug (`decision`, `debt`) this branch still carries unclaimed that `ref` has already
    resolved under a different number.

    ONLY THE DIRECTORY KINDS. `codes` and `step` slugs are headings inside one shared file
    apiece, never a filename of their own — the rename ambiguity this function exists for
    cannot arise for either, and `decision index`/`debt index`/`id claims` already watch the
    shared-file kinds for the ordinary two-number collision.
    """
    out: List[Tuple[str, str]] = []
    pend = pending(root)
    for kind, d in DIR_KINDS.items():
        letter = d.filename_letter
        # A DECISION'S CLAIMED FILE CARRIES ITS LETTER (`D188-tail.md`); A DEBT'S DOES NOT
        # (`188-tail.md`, matching every real entry under `docs/debts/` today) — see the
        # block comment above `DEBT_HEADING`. `letter` may be empty, and the pattern below
        # still anchors correctly either way.
        listing = git("ls-tree", "-r", "--name-only", ref, "--", d.directory, cwd=cwd)
        claimed_text: Dict[str, str] = {}
        for name in listing.splitlines():
            m = re.match(r"^" + re.escape(letter) + r"(\d+)-(.+)\.md$", Path(name).name)
            if m:
                claimed_text[m.group(2)] = m.group(1)
        prefix = d.unclaimed_letter + "-"
        for slug in pend[kind]:
            text = slug[len(prefix):] if slug.startswith(prefix) else slug
            if text in claimed_text:
                out.append((slug, f"{d.unclaimed_letter}{claimed_text[text]}"))
    return out


def report_duplicate(dupes: Sequence[Tuple[str, str]], ref: str) -> None:
    """Name every already-claimed slug this branch is still carrying as unclaimed."""
    say(f"REFUSED: {len(dupes)} pending slug(s) this branch carries are already claimed on "
        f"`{ref}`, under a different number.", "")
    for slug, number in dupes:
        say(f"  `{slug}` is already `{number}` on {ref} — some other branch claimed the",
            "      identical file first, and this branch never merged that claim back in.")
    say("",
        "  THIS IS NOT A NEW ENTRY TO CLAIM. Merge `origin/main`, take its numbered file for",
        "  this slug, and drop this branch's own unclaimed copy — `git rm` it and, on",
        "  conflict, `git checkout --theirs` the numbered path. Minting a fresh number for it",
        "  here would duplicate content main already carries, under a second number nothing",
        "  else on main has ever heard of.")


# ------------------------------------------------- what a commit CARRIES, after it is landed

# THE INVARIANT IS `MAIN CARRIES NO SLUG`, AND NOTHING ASKED THE COMMIT ITSELF.
# Every reader above asks about a CHECKOUT: what this branch has pending, what it added, what
# the ref has taken. None of them can be pointed at the commit a merge just produced, which is
# the one subject the invariant is actually about — and the invariant failed twice in the
# fortnight this was written, both times in silence, because `make merge` runs the merge
# script of whatever checkout invoked it and a checkout older than the claim has no claim in
# it to run.
#
# IT IS A REPORT AND NOT A REFUSAL, and the asymmetry with `--stale` is the point. A staleness
# report is read BEFORE anything moves, so refusing costs nothing. This one is read AFTER: the
# pull request is merged on GitHub and main carries the slug whatever anybody here decides.
# Refusing the local fast-forward at that point would leave this clone behind a main that is
# already wrong, which repairs nothing and breaks everything downstream of it. So it names
# what landed, names the repair, and exits 3 so a caller cannot read it as a pass.
#
# ITS SUBJECT IS A REV AND NEVER `HEAD`. Pointing it at a working tree would make it a
# duplicate of `id claims`, which already does that job on the commit path.


def report_landed(root: Path, rev: str) -> int:
    """Every unclaimed id in `rev`'s own trees. 0 when clean, 3 when not, 2 when unaskable."""
    resolved = git("rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}", cwd=str(root)).strip()
    if not resolved:
        say(f"REFUSED: `{rev}` does not name a commit in {root}.",
            "",
            "  This reads what a COMMIT carries. Without one there is nothing to read, and an",
            "  unreadable subject is not evidence that anything is clean.")
        return 2

    found = pending_at(resolved, cwd=str(root))
    names = [f"{slug}" for slug in found["decision"] + found["codes"]]
    names += [f"step {slug}" for slug in found["step"]]

    say(f"PKMNSCAN — unclaimed ids carried by {resolved[:9]}")
    say("=" * 72, "")
    if not names:
        say(f"  {resolved[:9]} carries no unclaimed id — every heading in it is a number.")
        return 0

    say(f"REFUSED: {resolved[:9]} carries {len(names)} unclaimed id.", "")
    for name in names:
        say(f"  {name}")
    say("",
        "  A slug is a BRANCH's placeholder and the merge is what turns it into a number",
        "  (D140). One on a commit main now carries means the claim half did not run: every",
        "  citation of that id resolves to nothing, and no later claim can ever find it,",
        "  because the branch that wrote it is merged and gone.",
        "",
        "  Repair, on a branch cut from main as it stands now:",
        "",
        "    python3 scripts/claim-ids.py --ref origin/main --write",
        "    make check && gh pr create --base main",
        "",
        "  And ask why the claim did not run. `make merge` runs the merge script of the",
        "  CHECKOUT it was invoked from, and a checkout cut before a capability landed does",
        "  not have it — that is what `scripts/merge-pr.py --surface` refuses.")
    return 3


# ------------------------------------------------------------------------- the substitution


def apply_to_text(text: str, claims: Sequence[Claim]) -> Tuple[str, int]:
    """`text` with every claim's token replaced, and how many replacements happened.

    BOUNDED AGAINST A HYPHEN, AND `\b` IS NOT THAT. A hyphen is a non-word character, so
    a `\b`-bounded slug matches INSIDE a longer one that extends it — the boundary sits between the
    `g` and the `-`. Two slugs where one is the other plus a segment then substitute the
    shorter inside the longer and leave a number with a tail on it, which resolves
    to nothing and reads like somebody's typo rather than like a tool's bug. Found by the
    self-test arm written to mutation-test the boundary, on the unmutated code.
    """
    count = 0
    for claim in claims:
        pattern = re.compile(r"(?<![-\w])" + re.escape(claim.token) + r"(?![-\w])")
        text, hits = pattern.subn(claim.becomes, text)
        count += hits
    return text, count


def entry_gloss(root: Path, claim: Claim) -> str:
    """STOPGAP (DEBT78): up to 6 words of a pending entry's own heading title.

    The docs-audit `rule enforcement` row wants `D<n> (words)` at a cite's first use in a
    paragraph of CLAUDE.md, and the claim turned a slug into a bare number. Read before the
    rename, while the file still carries the slug. "" for a kind with no entry file.
    """
    d = DIR_KINDS.get(claim.kind)
    if not d:
        return ""
    for path in sorted((root / d.directory).glob("*.md")):
        m = re.match(r"#+\s+" + re.escape(claim.slug) + r"\s+[\u2014-]\s*(.+)", read(path).split("\n", 1)[0])
        if m:
            return title_gloss(m.group(1))
    return ""


def title_gloss(title: str) -> str:
    """STOPGAP: the gloss a claim writes for an entry title. `--unclaim` strips exactly this."""
    return " ".join(re.sub(r"[()`]", "", title).split()[:6])


def claimed_gloss(root: Path, u: "Unclaim") -> str:
    """The gloss `entry_gloss` wrote for this claimed entry, read from its heading now."""
    if u.kind not in DIR_KINDS or not u.old_name:
        return ""
    path = root / DIR_KINDS[u.kind].directory / u.old_name
    if not path.exists():
        return ""
    m = re.match(r"#+\s+" + re.escape(u.token) + r"\s+[\u2014-]\s*(.+)", read(path).split("\n", 1)[0])
    return title_gloss(m.group(1)) if m else ""


def gloss_first_uses(text: str, claims: Sequence[Claim], glosses: Dict[str, str]) -> str:
    """STOPGAP: add ` (gloss)` to a claimed cite at its first use in a paragraph when it has none.

    A paragraph ends at a blank line or starts at a bullet, as the audit reads it. A cite that
    already has ` (..)` or `, words` after it is left alone, so a gloss is never doubled.
    """
    out, seen = [], set()
    for line in text.split("\n"):
        if not line.strip() or re.match(r"\s*[-*] ", line):
            seen = set()
        if not line.startswith("#"):
            for c in claims:
                g = glosses.get(c.slug)
                if not g:
                    continue

                def add(m, c=c, g=g, seen=seen):
                    if c.becomes in seen:
                        return m.group(0)
                    seen.add(c.becomes)
                    if re.match(r"`?( \(|,\s+\w)", m.string[m.end():]):
                        return m.group(0)
                    return f"{c.becomes}{m.group(1)} ({g})"
                line = re.sub(r"(?<![-\w])" + re.escape(c.becomes) + r"(`?)(?![-\w])", add, line, count=1)
        out.append(line)
    return "\n".join(out)


def renumber_gates(text: str, claims: Sequence[Claim]) -> str:
    """Turn each claimed step's `0.` marker into its allocated number.

    The one edit here that is not a token substitution, and it is one line per step: markdown
    has no ordered-list marker that can hold a slug, so an unclaimed step wears `0.` and the
    claim puts the real number in its place. Runs BEFORE the token pass, so it still has the
    slug to find the line by.
    """
    for claim in claims:
        if claim.kind != "step":
            continue
        # The whole pending prefix goes, marker and backticked slug together. Leaving the
        # slug for the token pass to rewrite produced ``4. `step 4` **Title**`` — a claimed
        # step wearing the scaffolding of an unclaimed one, which reads as a second id.
        text = re.sub(r"^0\.\s+`step " + re.escape(claim.slug) + r"`\s*",
                      claim.number + ". ", text, count=1, flags=re.M)
    return text


def renumber_map(text: str, claims: Sequence[Claim]) -> str:
    """Turn each claimed step's `"n": "<slug>"` into the allocated INTEGER.

    THE SECOND EDIT THAT IS NOT A TOKEN SUBSTITUTION, and it was missing until the bootstrap
    PR tried to claim its own step. A step is cited in prose as `step <slug>`, so that is the
    token — but `docs/map.py` stores the id BARE, as the `n` field, which the token cannot
    reach. Left alone it keeps the slug while docs/GATES.md gets the number, and `build order
    mirror` fails the commit: loud, but only because that row exists.

    AN INTEGER AND NOT A STRING. `build order mirror` reads GATES.md's markers with `int()`
    and compares them against `n` by equality, so `"23"` agrees with nothing.
    """
    for claim in claims:
        if claim.kind != "step":
            continue
        text = re.sub(r'"n":\s*"' + re.escape(claim.slug) + r'"',
                      '"n": ' + claim.number, text, count=1)
    return text


def rewrite_decision_paths(text: str, claims: Sequence[Claim]) -> str:
    """Turn a PATH citation of a decision's own slug-named file into a bare id citation.

    THE THIRD EDIT THAT IS NOT A TOKEN SUBSTITUTION, and it is the one that was missing on
    2026-09-19: `docs/specs/sales-plan.md` cited a still-unclaimed entry as
    `` `docs/decisions/D-<slug>.md` `` — a real path, true the day it was written, because the
    unclaimed file really is named after its bare slug. `apply_to_text` alone substitutes only
    the TOKEN inside that path, `D-<slug>` -> `D<n>`, and leaves `` `docs/decisions/D<n>.md` ``
    behind: a path that has never existed, since `rename_claimed_entries` renames the real
    file to `D<n>-<slug>.md` in the SAME pass — the number joins the slug, it does not replace
    it. `make docs-audit`'s `paths` row (a general existence check over every path-shaped
    token in every markdown file, not a rule aimed at this one shape) correctly refused the
    dangling path, and the pre-commit hook stopped the claim commit with the tree already
    rewritten.

    THE FIX IS NOT A BETTER PATH. The global rule this repo already holds
    (`~/Developer/claude-settings/CLAUDE.md`: "Give each record its own file, one folder per
    kind. Cite by id, never by path.") is D160's own argument applied a second time
    (`docs/debts/README.md`'s header cites it for `DEBT<n>` the same way) — a decision is cited by
    its bare `D<n>`, the form `Claim.becomes` already carries, and the path is dropped
    entirely rather than repaired. No new formatter is built for this: `claim.becomes` is
    already the exact citation form the rest of this file uses everywhere else.

    RUNS BEFORE `apply_to_text`, MATCHING `renumber_gates`/`renumber_map`'s OWN ORDERING, so
    it still has the slug to find the path by; the generic pass then finds nothing left to
    double-substitute inside what was the path, and still catches every OTHER, bare citation
    of the same token elsewhere in the file.

    DIRECTORY KINDS ONLY (`decision`, `debt`). A codes id and a build step have no file of
    their own to be pointed at — `docs/specs/code-cards.md` and `docs/GATES.md` are one shared
    file apiece, never a directory with one file per entry — so there is no path shape for
    either to produce, and none is built here for a citation that cannot exist. `docs/debts/README.md`
    carries the identical "cite by id, never by path" rule for `DEBT<n>`, so a debt's own
    unclaimed path (`` `docs/debts/DEBT-<slug>.md` ``) is the same defect one namespace over.
    """
    for claim in claims:
        if claim.kind not in DIR_KINDS:
            continue
        directory = DIR_KINDS[claim.kind].directory
        # THE FILE'S OWN TAIL, AND NOT ONLY THE BARE `<token>.md`, MATCHING
        # `rename_claimed_entries`'S OWN RULE: that function finds the pre-claim file by
        # `n.startswith(claim.slug + "-") or n == claim.slug + ".md"`, because the file a
        # branch writes may carry more descriptive text after the slug than the slug's own
        # citation form does. A citation naming that same file has to be found by the same
        # rule, or a longer-tailed filename would leave its own path citation unrewritten
        # while the file underneath it renamed. An optional backtick on each side: every
        # live example in this tree backtick-quotes the path, but the citation is dropped
        # either way rather than left half-repaired.
        pattern = re.compile(r"`?" + re.escape(directory) + "/" + re.escape(claim.token)
                             + r"[\w-]*\.md`?")
        text = pattern.sub(claim.becomes, text)
    return text


def rename_claimed_entries(root: Path, claims: Sequence[Claim], write: bool,
                           kind: str = "decision") -> Dict[str, str]:
    """Rename each claimed entry's FILE, and rewrite the manifest to match.

    A CLAIM USED TO BE A SUBSTITUTION AND NOTHING ELSE. With the corpus as a directory it is
    also a rename: the slug-named file holds a heading that now reads as a number, and a file
    named after an id it no longer carries is the drift `path_for` would resolve wrongly.

    `kind` PICKS THE DIRECTORY CORPUS (`DIR_KINDS`) — `decision` by default, so every existing
    caller of this function keeps its exact behaviour. `debt` is the second: its claimed
    filename carries NO letter (`188-tail.md`, `DirKind.filename_letter == ""`), matching
    every real entry under `docs/debts/` today, while its heading and citation both carry
    `DEBT` (see the block comment above `DEBT_HEADING` for why the two spellings differ).

    THE MANIFEST IS EDITED HERE, AND ITS EXCLUSION FROM THE GENERIC PASS IS DEFENCE IN DEPTH
    RATHER THAN THE THING HOLDING IT UP. `ORDER.json` carries the slug inside a longer
    filename, and `apply_to_text` already refuses that match — measured, not assumed:
    substituting over a manifest naming `<slug>-<tail>.md` changes nothing today. The
    exclusion stays because the cost is one comparison and the failure it would prevent is
    silent, but it is NOT load-bearing, and a reader should not be told it is.

    WHAT IS LOAD-BEARING is that the manifest and the directory move TOGETHER. A rename
    without a manifest update, or the reverse, leaves a name pointing at nothing — and the
    corpus stops reassembling with every audit row still green until something opens it.
    That is the invariant the self-test asserts.
    """
    d = DIR_KINDS[kind]
    renames: Dict[str, str] = {}
    manifest_path = root / d.manifest
    if not manifest_path.exists():
        return renames
    manifest = json.loads(read(manifest_path))
    listed = list(manifest["order"])
    # The file may not be in the manifest yet — a branch does not put it there. Look in the
    # DERIVED order so a claim can rename an entry the manifest has never heard of.
    order = corpus_order(root, d.directory, d.manifest)
    for claim in claims:
        if claim.kind != kind:
            continue
        old_name = next((n for n in order if n.startswith(claim.slug + "-")
                         or n == claim.slug + ".md"), None)
        if old_name is None:
            continue
        # THE DESCRIPTIVE TAIL IS THE SLUG WITHOUT ITS LEADING LETTER AND DASH. A slug
        # heading's file is named for the whole slug, so there is no separate tail to lift
        # off; treating it as if there were produced a bare numeric filename that says
        # nothing and sorts nowhere near its neighbours.
        number = int(claim.number[len(d.unclaimed_letter):])
        prefix = d.unclaimed_letter + "-"
        described = claim.slug[len(prefix):] if claim.slug.startswith(prefix) else claim.slug
        tail = old_name[len(claim.slug) + 1:-3] if old_name.startswith(claim.slug + "-") else described
        new_name = f"{d.filename_letter}{number:03d}-{tail}.md"
        renames[old_name] = new_name
        order[order.index(old_name)] = new_name
        if old_name in listed:
            listed[listed.index(old_name)] = new_name
        if write:
            (root / d.directory / old_name).rename(root / d.directory / new_name)
    if renames and write:
        # Only what the manifest already NAMED is rewritten here; an entry it has never heard
        # of is appended by `settle_corpus`, which runs after this and knows the final order.
        manifest["order"] = listed
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return renames


def perform(root: Path, claims: Sequence[Claim], write: bool) -> Dict[str, int]:
    """Substitute every claim across the tree. Returns path -> replacements."""
    touched: Dict[str, int] = {}
    glosses = {c.slug: entry_gloss(root, c) for c in claims}
    manifest_paths = {root / d.manifest for d in DIR_KINDS.values()}
    for path in text_files(root):
        # A manifest is names, not prose, and `rename_claimed_entries` owns it. Belt and
        # braces — the token grammar already declines a match inside a longer slug. See there.
        if path in manifest_paths:
            continue
        before = read(path)
        after = before
        if path == root / GATES:
            after = renumber_gates(after, claims)
        if path == root / MAP:
            after = renumber_map(after, claims)
        after = rewrite_decision_paths(after, claims)
        after, _ = apply_to_text(after, claims)
        if path == root / "CLAUDE.md":  # the only file the audit's gloss rule reads
            after = gloss_first_uses(after, claims, glosses)
        if after == before:
            continue
        touched[str(path.relative_to(root))] = sum(
            len(re.findall(r"\b" + re.escape(c.token) + r"\b", before)) for c in claims
        ) or 1
        if write:
            path.write_text(after, encoding="utf-8")
    for kind, d in DIR_KINDS.items():
        for old_name, new_name in rename_claimed_entries(root, claims, write, kind=kind).items():
            touched[f"{d.directory}/{old_name} -> {new_name}"] = 1
    for label in settle_corpus(root, write):
        touched[label] = 1
    for label in regenerate_derived(root, write):
        touched[label] = 1
    return touched


# GENERATED FILES THAT READ DECISION IDS FROM A HEADER. The rewrite above changes a test's
# `Governs:` line, and `docs/TESTS.md` is derived from it, so `docs-audit`'s `test purposes`
# row failed on the claim commit itself. One place regenerates: a generated file the rewrite
# can stale is added here. Checked: `docs/map.py` is rewritten by `renumber_map`, the decision
# index is a rendering (D60), and `map-fix` / `offenders-prune` only delete stale entries.
DERIVED = (("scripts/tests_page.py", "docs/TESTS.md"),)


def regenerate_derived(root: Path, write: bool) -> List[str]:
    out: List[str] = []
    for script, page in DERIVED:
        if not write or not (root / script).exists():
            continue
        before = read(root / page) if (root / page).exists() else ""
        done = subprocess.run([sys.executable, str(root / script), "--write"], cwd=str(root),
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False)
        if done.returncode:
            say(f"REFUSED: `{script}` failed, so `{page}` is stale.",
                "  The tree HOLDS the rewrite, uncommitted. Nothing is committed or pushed.",
                "  Read the error below, fix its cause, then run `make tests-page ARGS=--write`",
                "  and commit the tree as it stands.", "",
                done.stderr.decode("utf-8", errors="replace")[-800:])
            raise SystemExit(4)
        if read(root / page) != before:
            out.append(page)
    return out


def settle_corpus(root: Path, write: bool) -> List[str]:
    """Write the one DERIVED thing at claim time: the manifest's order.

    THE MERGE IS THE ONE MOMENT THIS IS KNOWABLE, which is exactly D140's argument for the
    number and the reason it belongs here rather than on a branch. A branch adding an entry
    would otherwise have to append to a shared JSON array at the position every other such
    branch touches — one more collision, in the change that exists to remove one.

    So a branch carries its entry FILE and nothing shared. Corpus membership is derived by
    `decisions_corpus.order()`/`debts_corpus.order()` until this runs, and each manifest is
    appended from the headings that exist after the claim — including the number this claim
    just allocated, which is why it runs AFTER the substitution and the rename rather than
    beside them.

    CLAUDE.md'S DECISION INDEX IS RETIRED (D60 amended). `make map ARGS=--decisions` renders
    the same id-and-title list off the corpus itself, on demand, never a stored copy — so
    nothing here writes CLAUDE.md, and nothing ever will again. `docs/debts/README.md` KEEPS ITS
    WRITTEN INDEX — no rendered view has replaced it — so the debt kind's own stub still gets
    regenerated here, the one asymmetry between the two `IndexSpec`s
    (`scripts/index-decisions.py`). `debt` reused decisions' own scheme (the owner's word:
    assign numbers at merge, the way decisions already do) rather than a second settling
    mechanism.

    D18 PUTS THIS ON THE WRITING SIDE and keeps the checking side elsewhere: `debt index`
    still computes its own index independently and blocks, a different program. A generator
    that also gated could satisfy itself.
    """
    moved: List[str] = []
    try:
        import importlib.util

        gen_spec = importlib.util.spec_from_file_location(
            "index_decisions", root / "scripts" / "index-decisions.py")
        index = importlib.util.module_from_spec(gen_spec)
        gen_spec.loader.exec_module(index)
    except Exception as exc:                       # a tree without the generator still claims
        return [f"(index generator not runnable: {exc})"]
    # CLAUDE.md NEVER APPEARS HERE. `index.DECISION_SPEC`'s manifest is folded (below), and its
    # `rewrite_index` is never called — that half is retired along with the stub it used to
    # write. `index.DEBT_SPEC` is the one kind whose stub (`docs/debts/README.md`) still gets
    # regenerated, because nothing renders that index yet.
    for kind_spec, manifest, rewrite, stub_label in (
        (index.DECISION_SPEC, DECISIONS_MANIFEST, False, None),
        (index.DEBT_SPEC, DIR_KINDS["debt"].manifest, True,
         "docs/debts/README.md (debt index regenerated)"),
    ):
        try:
            appended = index.normalize(root, write, kind_spec)
            if appended:
                moved.append(f"{manifest} (+{len(appended)} entry)")
            if rewrite and index.rewrite_index(root, write, kind_spec):
                moved.append(stub_label)
        except Exception as exc:            # a tree without that corpus still claims the rest
            moved.append(f"({kind_spec.corpus_script} not settled: {exc})")
    return moved


# ------------------------------------------------------------------- the exact inverse claim

# THE REMEDY `stale_claims` NAMES AND NOTHING BUILT. `report_stale`'s own text says "put the
# id back to the slug form and let the merge allocate it again" — and until this, that was a
# sentence with no command behind it: a human (or a session) had to hand-rename the file,
# hand-edit the heading, and hand-find every citation, which is exactly the error surface D140
# exists to delete from the FORWARD direction. It bit for real on 2026-09-12: a coordinating
# session hit `stale_claim`'s refusal mid conflict-resolution and, with no un-claim command to
# reach for, hand-picked new numbers instead — one guess collided too, before landing on D188
# — the hand-guessing this whole file exists to replace, one direction over.
#
# BUILT AS THE LITERAL INVERSE OF THE FORWARD SUBSTITUTION, REUSING ITS OWN GRAMMAR, NOT A
# SECOND ONE. `apply_to_text`'s docstring records the `\b`-boundary bug this repo was burned by
# once already: a bound built from `\b` alone matches a shorter slug INSIDE a longer one that
# extends it, because a hyphen is a non-word character. A hand-rolled reverse substitution would
# have to remember that bug independently; this one cannot forget it, because it is the same
# `(?<![-\w])...(?![-\w])` pattern, run with the token and the replacement swapped.
#
# A DECISION KEEPS ITS SLUG SOMEWHERE; A CODE-CARD ID AND A BUILD STEP DO NOT. That asymmetry
# is not a shortcut taken here — it is already true of the forward direction. A decision's
# entry is a FILE, and `rename_claimed_entries` renames it rather than deleting it, so the
# slug survives in the filename after the heading itself has been overwritten with a number.
# `docs/specs/code-cards.md` is one file for the whole codes corpus and `docs/GATES.md`'s build
# order is one file for every step; neither gets a rename, so the substitution that turns
# `C-<slug>` or `step <slug>` into a number is TOTAL — nothing anywhere in the tree still spells
# the slug once it commits. So a decision's slug is derived automatically from its own file;
# a codes id or a step needs `--to-slug`, supplied by whoever still remembers what they wrote
# (their own commit that introduced the entry names it, in the heading, before the claim ran).
#
# THE SAFETY CHECK IS `stale_claims`' OWN ARGUMENT, READ BACKWARDS. That entry's docstring says
# an un-claim "has to happen BEFORE the merge and never after, because once main is merged in a
# substitution on that token reaches main's own copy of the entry too." So before touching
# anything, this asks the same question `stale_claims` asks per id — is it on `ref` yet — and
# refuses outright when the answer is yes: an id already on main is not this branch's to give
# back, however this branch came to hold it.


class Unclaim(NamedTuple):
    kind: str        # "decision" | "codes" | "step" | "debt"
    number: int       # the bare integer: 188, 4, 12
    token: str        # the literal claimed form, as it is cited in prose: "D188", "C4", "step 12"
    becomes: str      # the literal slug form citations revert to: "D-...", "C-...", "step ..."
    slug: str         # the BARE slug, no letter and no `step ` prefix — what `--to-slug` takes
    old_name: str = ""  # directory kinds only: the <letter><n>-<slug>.md file held right now
    new_name: str = ""  # directory kinds only: the <letter>-<slug>.md file it reverts to


_UNCLAIM_DECISION = re.compile(r"^D([1-9][0-9]{0,2})$")
_UNCLAIM_CODES = re.compile(r"^C([1-9][0-9]{0,2})$")
_UNCLAIM_STEP = re.compile(r"^step\s+([1-9][0-9]*)$")
_UNCLAIM_DEBT = re.compile(r"^DEBT([1-9][0-9]{0,2})$")


def parse_claimed_ident(ident: str) -> Tuple[str, int]:
    """(kind, number) for a CLAIMED id's own spelling, or raises ValueError.

    A CLAIMED ID, NEVER A SLUG — there is nothing to unclaim from a slug, because a slug is
    already the form this command puts things back into. Rejecting one here is the same
    refusal-over-guessing this whole file is built on, one function along.

    `DEBT<n>` IS CHECKED BEFORE `D<n>`, because `DEBT<n>` also starts with `D` and the
    decision pattern is anchored (`^D([1-9]...)$`), which already refuses it — `T` is not a
    digit — so the order here is belt and braces, not load-bearing.
    """
    match = _UNCLAIM_DEBT.match(ident)
    if match:
        return "debt", int(match.group(1))
    match = _UNCLAIM_DECISION.match(ident)
    if match:
        return "decision", int(match.group(1))
    match = _UNCLAIM_CODES.match(ident)
    if match:
        return "codes", int(match.group(1))
    match = _UNCLAIM_STEP.match(ident)
    if match:
        return "step", int(match.group(1))
    raise ValueError(
        f"{ident!r} is not a claimed id's own spelling. A claimed id is a bare number in one "
        f"of the four namespaces this file allocates: `D188`, `C4`, `step 12`, `DEBT48` — "
        f"never a slug, since a slug is already unclaimed.")


def entries_at(ref: str, number: int, cwd: Optional[str] = None, kind: str = "decision") -> Set[str]:
    """The FILENAMES `ref` itself carries at this number, for one directory-corpus `kind`.
    Empty when it carries none.

    THE ONE FACT THAT TELLS TWO COLLIDING ENTRIES APART, and the branch is the side that
    knows it: a file `ref` has is `ref`'s, and the entry this branch is holding is the one
    `ref` does not have. Nothing here reads content — a name is enough, because the collision
    is two DIFFERENT slugs wearing one number and the tail after the number is the slug.
    """
    d = DIR_KINDS[kind]
    prefix = f"{d.directory}/{d.filename_letter}{number:03d}-"
    listing = git("ls-tree", "-r", "--name-only", ref, d.directory, cwd=cwd)
    return {line.split("/")[-1] for line in listing.splitlines() if line.startswith(prefix)}


def find_decision_file(root: Path, number: int, ref: Optional[str] = None,
                       cwd: Optional[str] = None, kind: str = "decision"
                       ) -> Tuple[Optional[Path], str]:
    """The claimed entry's own file, and the slug tail its filename still carries.

    `kind` PICKS THE DIRECTORY CORPUS (`DIR_KINDS`), `decision` by default so every existing
    call keeps its exact behaviour. The name stays singular even though `debt` reuses it,
    matching this whole file's practice of not renaming a function just because a second
    caller arrived — see `rename_claimed_entries`.

    THE FILENAME IS THE ONE SURVIVING RECORD. `rename_claimed_entries` renames the slug-named
    file to `<letter><n>-<tail>.md` rather than deleting it, so the tail after the number is
    exactly the descriptive half of the original slug — no guessing, the same fact
    `plan_unclaim`'s docstring above spells out.

    TWO FILES AT ONE NUMBER IS THE STATE THIS COMMAND EXISTS FOR, NOT A REASON TO GIVE UP.
    Until 2026-09-19 a second match refused outright — `no single D<n>-*.md file in this
    tree` — and the state that produces it is the documented pre-merge routine: a branch that
    lost a race for its number fetches `origin/main` and MERGES IT IN, and now holds both its
    own entry and main's under one number. That is exactly the incident `--unclaim` was built
    to answer, and it was the one input it could not read. Measured that evening: a claim
    allocated, pushed, and refused at the GitHub half, with the remedy the refusal itself
    named unable to run.

    SO THE REF DECIDES, AND ONLY WHEN IT HAS TO. One match is answered without asking git
    anything. Two or more are filtered by `entries_at`: whatever `ref` carries is `ref`'s, and
    one survivor is this branch's own. `None` still when the answer is not a single file —
    zero matches is "not claimed here", and an unresolvable several is refused rather than
    picked from.
    """
    d = DIR_KINDS[kind]
    prefix = f"{d.filename_letter}{number:03d}-"
    matches = sorted((root / d.directory).glob(prefix + "*.md"))
    if len(matches) > 1 and ref:
        theirs = entries_at(ref, number, cwd=cwd, kind=kind)
        mine = [path for path in matches if path.name not in theirs]
        if len(mine) == 1:
            matches = mine
    if len(matches) != 1:
        return None, ""
    path = matches[0]
    return path, path.stem[len(prefix):]


def plan_unclaim(root: Path, ident: str, to_slug: Optional[str], ref: Optional[str] = None,
                 cwd: Optional[str] = None) -> Unclaim:
    """The single reverse claim for an already-claimed id. Raises ValueError to refuse.

    `ref` IS PASSED IN RATHER THAN LOOKED UP, and it is resolved by the caller BEFORE this
    runs. `find_decision_file` needs it to tell this branch's entry from the one a merge of
    `ref` brought in, and a plan built without it would refuse the collision state outright —
    which is what this command did until 2026-09-19.
    """
    kind, number = parse_claimed_ident(ident)

    if kind in DIR_KINDS:
        d = DIR_KINDS[kind]
        path, tail = find_decision_file(root, number, ref=ref, cwd=cwd, kind=kind)
        glob_pat = f"{d.filename_letter}{number:03d}-*.md"
        if path is None:
            held = sorted(x.name for x in (root / d.directory).glob(glob_pat))
            if len(held) > 1:
                raise ValueError(
                    f"{len(held)} files in {d.directory} carry {glob_pat.split('-')[0]} — "
                    + ", ".join(held)
                    + f" — and `{ref}` accounts for none of them or for all but one of them "
                    f"in a way this cannot read. Exactly one of these is this branch's own; "
                    f"the rest belong to `{ref}`. Nothing is guessed here.")
            raise ValueError(
                f"no single {d.directory}/{glob_pat} file in this tree — `{ident}` "
                f"is not a claimed {kind} this checkout holds.")
        heading = read(path).split("\n", 1)[0]
        # A DEBT'S CLAIMED HEADING MAY BE BARE (`## 188`, every real entry today) OR CARRY
        # THE WORD (`## DEBT<n>`, a newly claimed one) — see the block comment above
        # `DEBT_HEADING` in this file. A DECISION'S NEVER IS BARE, so its own check stays
        # strict.
        heading_letter = re.escape(d.unclaimed_letter) if kind == "decision" \
            else "(?:" + re.escape(d.unclaimed_letter) + ")?"
        if not re.match(r"^##\s+" + heading_letter + str(number) + r"\b", heading):
            raise ValueError(
                f"{path.relative_to(root)}: heading is {heading!r}, which does not start "
                f"`## {d.unclaimed_letter}{number}` — refusing to guess which entry this is.")
        bare = to_slug if to_slug else tail
        if not re.fullmatch(SLUG, bare):
            raise ValueError(
                f"{bare!r} is not a slug — two or more lowercase hyphenated segments.")
        slug = d.unclaimed_letter + "-" + bare
        return Unclaim(kind, number, f"{d.unclaimed_letter}{number}", slug, bare,
                       old_name=path.name, new_name=slug + ".md")

    if kind == "codes":
        if not to_slug:
            raise ValueError(
                "a code-card id keeps its slug NOWHERE once claimed. "
                f"{CODES_DECISIONS} is one file for the whole corpus, not a directory with "
                "one file per entry — a decision's slug survives in its entry's own "
                "FILENAME (see find_decision_file); a codes entry has no such file, so the "
                "substitution that turned `C-<slug>` into this id left nothing behind to "
                "read it back from. Pass --to-slug <the-original-slug> — the slug the "
                "commit that first introduced this entry used in its heading.")
        if not re.fullmatch(SLUG, to_slug):
            raise ValueError(
                f"{to_slug!r} is not a slug — two or more lowercase hyphenated segments.")
        path = root / CODES_DECISIONS
        if not path.exists():
            raise ValueError(f"{CODES_DECISIONS} does not exist in this tree.")
        heading_re = re.compile(r"^##\s+C" + str(number) + r"\b", re.M)
        if not heading_re.search(read(path)):
            raise ValueError(
                f"no `## C{number}` heading in {CODES_DECISIONS} — `{ident}` is not a "
                f"claimed entry this checkout holds.")
        return Unclaim("codes", number, f"C{number}", "C-" + to_slug, to_slug)

    # kind == "step"
    if not to_slug:
        raise ValueError(
            "a build step keeps its slug NOWHERE once claimed. `renumber_gates` replaces the "
            "WHOLE `0. `step <slug>`` prefix with the allocated number in one edit, and "
            f"nothing in {GATES} or {MAP} carries the slug afterwards — a decision survives "
            "this because its FILE is still named after the slug; a step has no file of its "
            "own to be renamed. Pass --to-slug <the-original-slug> — the slug the commit "
            "that first claimed this step used.")
    if not re.fullmatch(SLUG, to_slug):
        raise ValueError(
            f"{to_slug!r} is not a slug — two or more lowercase hyphenated segments.")
    gates_path = root / GATES
    if not gates_path.exists():
        raise ValueError(f"{GATES} does not exist in this tree.")
    if not re.search(r"^" + str(number) + r"\.\s", read(gates_path), re.M):
        raise ValueError(
            f"no `{number}. ` build-order line in {GATES} — `step {number}` is not a "
            f"claimed step this checkout holds.")
    return Unclaim("step", number, f"step {number}", "step " + to_slug, to_slug)


def ids_at(ref: str, cwd: Optional[str] = None) -> Dict[str, Set[int]]:
    """Every ALLOCATED id of each kind, as of `ref` — `ceiling_at`'s set, not its max.

    THE FIRST, CHEAP HALF OF THE SAFETY GATE: whether `ref` has an entry at this number AT
    ALL. It says nothing about whether that entry is THIS one — see `same_entry_on_ref`, which
    asks the question this file's own worked incident needs answered, and is why a bare
    presence check here is not the whole gate.
    """
    return {kind: allocated_ids(corpus_text_at(ref, cwd=cwd) if kind == "decision"
                                else git("show", f"{ref}:{path}", cwd=cwd), pattern)
            for kind, path, pattern, _ in KINDS}


def local_heading(root: Path, u: Unclaim) -> str:
    """The current heading (or GATES.md marker line) for this id, IN THIS TREE, right now —
    before anything is unclaimed. `""` when it cannot be found, which `plan_unclaim` has
    already made unreachable for a valid `Unclaim` other than a step/codes id whose own file
    went missing between planning and this read.
    """
    if u.kind in DIR_KINDS:
        # THE PLAN ALREADY RESOLVED WHICH FILE IS OURS, so this reads that answer rather than
        # asking the question a second time — a second glob would be a second chance to pick
        # the wrong one of two files sharing a number, with no ref in hand to tell them apart.
        path = root / DIR_KINDS[u.kind].directory / u.old_name if u.old_name else None
        return read(path).split("\n", 1)[0] if path and path.exists() else ""
    if u.kind == "codes":
        path = root / CODES_DECISIONS
        if not path.exists():
            return ""
        match = re.search(r"^##\s+C" + str(u.number) + r"\b.*$", read(path), re.M)
        return match.group(0) if match else ""
    path = root / GATES
    if not path.exists():
        return ""
    match = re.search(r"^" + str(u.number) + r"\..*$", read(path), re.M)
    return match.group(0) if match else ""


def ref_heading(ref: str, u: Unclaim, cwd: Optional[str] = None) -> str:
    """The SAME line, as `ref` carries it right now — which may belong to a completely
    different entry that merely landed on the same number (see `same_entry_on_ref`)."""
    if u.kind in DIR_KINDS:
        d = DIR_KINDS[u.kind]
        listing = git("ls-tree", "-r", "--name-only", ref, d.directory, cwd=cwd)
        prefix = f"{d.directory}/{d.filename_letter}{u.number:03d}-"
        match = next((line for line in listing.splitlines() if line.startswith(prefix)), None)
        return git("show", f"{ref}:{match}", cwd=cwd).split("\n", 1)[0] if match else ""
    if u.kind == "codes":
        text = git("show", f"{ref}:{CODES_DECISIONS}", cwd=cwd)
        match = re.search(r"^##\s+C" + str(u.number) + r"\b.*$", text, re.M)
        return match.group(0) if match else ""
    text = git("show", f"{ref}:{GATES}", cwd=cwd)
    match = re.search(r"^" + str(u.number) + r"\..*$", text, re.M)
    return match.group(0) if match else ""


def same_entry_on_ref(root: Path, ref: str, u: Unclaim, cwd: Optional[str] = None) -> bool:
    """Whether `ref`'s own entry at this number IS this entry, rather than an unrelated one
    that happens to have landed on the same number.

    THE DISTINCTION THE RAW PRESENCE CHECK CANNOT DRAW, AND THE WHOLE REASON THIS FUNCTION
    EXISTS. `ids_at` alone answers "does `ref` have an entry here" — and answering `--unclaim`
    with a flat refusal whenever that is true would refuse the ONE CASE this file was built
    to answer: the actual 2026-09-12 incident is precisely a branch whose own D<n+1> collided
    with an UNRELATED entry that `ref` independently claimed at the same number. Reverting
    THIS branch's own file there corrupts nothing of ref's, because ref's D<n+1> is not this
    entry — it is someone else's, sharing a number by the same race D140's amendment exists
    to catch.

    THE HEADING LINE IS THE FINGERPRINT, not the whole body: it is what `apply_to_text`'s own
    substitution already treats as the identifying text for every OTHER purpose in this file,
    and two genuinely different entries sharing one by coincidence is a collision this whole
    mechanism already treats as astronomically unlikely (`claim-ids.py`'s own docstring: "zero
    collisions of either shape the day the vocabulary was chosen").

    A CLAIMED HEADING is what `ref_heading`/`local_heading` compare — this branch's OWN
    heading here still reads NUMBERED at this point (unclaiming has not run yet), so both
    sides are numbers when this fires, and equality means `ref` did not just collide, it
    correctly carries the SAME entry this branch already sees the answer to.
    """
    ours = local_heading(root, u)
    theirs = ref_heading(ref, u, cwd=cwd)
    return bool(ours) and ours == theirs


def unrenumber_gates(text: str, u: Unclaim) -> str:
    """Reverse of `renumber_gates`: the numbered marker becomes `0. `step <slug>` ` again.

    THE PREFIX ONLY, exactly mirroring the forward edit — `renumber_gates` touches nothing
    past the marker it replaces, so neither does this. The number is the step's own id and
    unique in the file by construction (that uniqueness is what makes it an id at all), so an
    anchored, single-replacement match is as safe here as the slug-keyed match is going
    forward.
    """
    if u.kind != "step":
        return text
    pattern = re.compile(r"^" + re.escape(str(u.number)) + r"\.\s+", re.M)
    return pattern.sub("0. `step " + u.slug + "` ", text, count=1)


def unrenumber_map(text: str, u: Unclaim) -> str:
    """Reverse of `renumber_map`: the map's bare `"n": <int>` becomes `"n": "<slug>"` again."""
    if u.kind != "step":
        return text
    pattern = re.compile(r'"n":\s*' + re.escape(str(u.number)) + r"(?!\d)")
    return pattern.sub('"n": "' + u.slug + '"', text, count=1)


def apply_unclaim_to_text(text: str, u: Unclaim, gloss: str = "") -> Tuple[str, int]:
    """`apply_to_text`'s own bound, run with the token and the replacement swapped.

    THE SAME `(?<![-\\w])...(?![-\\w])` GUARD, reused rather than rebuilt, is the whole point:
    a hand-rolled reverse would have to remember the `\\b`-boundary bug independently, and
    this one cannot forget it because it is not a second implementation.
    """
    tail = r"(?: \(" + re.escape(gloss) + r"\))?" if gloss else ""  # STOPGAP: the gloss the claim added
    pattern = re.compile(r"(?<![-\w])" + re.escape(u.token) + r"(?![-\w])" + tail)
    return pattern.subn(u.becomes, text)


def unindex(text: str, u: Unclaim) -> str:
    """Reverse of the one line `settle_corpus` added to CLAUDE.md's index for this id.

    MUST RUN BEFORE THE GENERIC SUBSTITUTION TOUCHES THIS FILE, and that ordering is the
    whole of this function's reason to exist separately from `unsettle_manifest` below. The
    index line reads `D188 <title>` — a token this id's own generic substitution also
    matches, since it is bounded exactly like a citation — so a removal keyed on that token
    that runs AFTER the generic pass finds nothing: the line has already been rewritten to
    start with the slug by the time it looks. Caught by the self-test's round-trip arm, which
    is the whole reason this is its own function instead of a `continue` inside `perform()`.

    NOT A CALL TO THE FORWARD GENERATOR WITH THE HEADING ALREADY REVERTED, either.
    `index-decisions.py` locates a heading by `_ID`, which matches a slug heading too — D182
    made that heading exempt from the AUDIT, not invisible to the GENERATOR — so regenerating
    the index after this id's heading is back to slug form would print a slug line into
    CLAUDE.md that the pre-claim tree never had, and the round trip would not be
    byte-identical. This removes exactly the one line `settle_corpus` added for THIS id,
    rather than asking the generator to recompute the whole set and hoping it lands on
    nothing.

    ONLY A DIRECTORY-CORPUS KIND HAS ONE TO REMOVE: codes and steps get no index line from
    `settle_corpus` to begin with (a decision's index is `docs/decisions/`'s alone, a debt's
    is `docs/debts/`'s).
    """
    if u.kind not in DIR_KINDS:
        return text
    pattern = re.compile(r"^" + re.escape(u.token) + r"\s")
    lines = [line for line in text.split("\n") if not pattern.match(line)]
    return "\n".join(lines)


def unsettle_manifest(root: Path, u: Unclaim, write: bool) -> List[str]:
    """Reverse of the one entry `settle_corpus` appended to `ORDER.json`'s `order`.

    A SEPARATE STEP FROM `unindex`, RATHER THAN THE SAME KIND OF FIX, because the manifest
    was never at risk of the ordering bug that motivated `unindex`: `perform_unclaim` already
    skips `ORDER.json` in the generic loop exactly as `perform()` does, so there is no
    generic-substitution pass to race against here. Kept as its own function anyway — a
    manifest edit and a text edit are different operations even when both undo the same
    forward step, and folding them into one function is how the ordering bug above would have
    hidden inside a diff that looked like one change.
    """
    moved: List[str] = []
    if u.kind not in DIR_KINDS:
        return moved
    manifest = DIR_KINDS[u.kind].manifest
    manifest_path = root / manifest
    if not manifest_path.exists():
        return moved
    contents = json.loads(read(manifest_path))
    order = list(contents["order"])
    if u.old_name not in order:
        return moved
    order.remove(u.old_name)
    contents["order"] = order
    if write:
        manifest_path.write_text(json.dumps(contents, indent=2) + "\n", encoding="utf-8")
    moved.append(f"{manifest} (-1 entry)")
    return moved


def is_index_line(line: str, u: Unclaim) -> bool:
    """`unindex`'s own test, one line at a time — see that function for why it exists."""
    return u.kind in DIR_KINDS and bool(re.match(r"^" + re.escape(u.token) + r"\s", line))


def protected_lines(ref: str, u: Unclaim, cwd: Optional[str] = None) -> Dict[str, Set[str]]:
    """Every line `ref` ITSELF carries that spells this id, keyed by the file it sits in.

    THE OTHER ENTRY'S CITATIONS ARE NOT THIS BRANCH'S TO REVERT, and until 2026-09-19 nothing
    here knew the difference. The substitution is keyed on the TOKEN, so in the
    collision state it rewrites main's own entry's heading, main's index line and main's
    prose citations into this branch's slug, silently, in the same pass that correctly
    reverts this branch's own. A half-reversed claim is worse than an unreversed one, and
    this is the half that would have been wrong.

    A LINE `ref` ALREADY HAS IS `ref`'S. The same fact `find_decision_file` uses one level
    up, at line granularity rather than file granularity: this branch's own citations were
    written by this branch and are not in `ref`'s copy of anything. Every transform in
    `perform_unclaim` is line-local — anchored with `re.M`, or bounded by
    `(?<![-\\w])...(?![-\\w])` — so a line is the right unit and no multi-line construct is
    cut in half by working one at a time.

    IT IS EMPTY UNLESS THE NUMBERS COLLIDED, AND THAT IS WHY THIS IS NOT A BEHAVIOUR CHANGE
    IN THE ORDINARY CASE. `run_unclaim` asks for it only when `ref` carries a DIFFERENT entry
    at this number. In every other state `ref` does not spell the token at all, the set is
    empty by construction, and `perform_unclaim` takes the identical path it always took —
    which the round-trip arm of `claim-selftest` asserts byte for byte.

    ONE `git grep` RATHER THAN ONE `git show` PER FILE. The token is matched fixed-string
    here and bounded properly later; over-collecting a line that merely contains `D2223` only
    ever protects a line this command had no business rewriting anyway.
    """
    out: Dict[str, Set[str]] = {}
    found = git("grep", "-F", "-n", "--no-color", u.token, ref, "--", ".", cwd=cwd)
    for row in found.splitlines():
        # `<ref>:<path>:<lineno>:<content>` — the ref half is ours, so split from the left
        # past it, and never past the content, which can hold any number of colons.
        parts = row.split(":", 3)
        if len(parts) != 4:
            continue
        out.setdefault(parts[1], set()).add(parts[3])
    return out


def perform_unclaim(root: Path, u: Unclaim, write: bool,
                    guard: Optional[Dict[str, Set[str]]] = None) -> Dict[str, int]:
    """Substitute the reverse claim across the tree. Returns path -> replacements.

    SAME SHAPE AS `perform()`, IN THE SAME ORDER: every per-file special case runs BEFORE the
    generic substitution touches that file (`unrenumber_gates`, `unrenumber_map`, `unindex`),
    exactly as `renumber_gates`/`renumber_map` run before `apply_to_text` going forward — a
    special case that ran after would be looking at text the generic pass has already
    rewritten out from under it, which is exactly the bug `unindex`'s own docstring records.
    Then the file rename, then the manifest. The rename runs against the file's CURRENT name,
    which is still `u.old_name` until this function renames it, after the loop that reads
    every file's content by name has already finished.
    """
    touched: Dict[str, int] = {}
    manifest_paths = {root / d.manifest for d in DIR_KINDS.values()}
    # THE INDEX FILE FOR *THIS* UNCLAIM, ONLY — never every kind's, matching `is_index_line`/
    # `unindex`'s own `u.kind` check. A debt's index lives in `docs/debts/README.md`; a decision's in
    # `CLAUDE.md` (`DirKind.index_stub`).
    index_path = root / DIR_KINDS[u.kind].index_stub if u.kind in DIR_KINDS else None
    guard = guard or {}
    gloss = claimed_gloss(root, u)
    for path in text_files(root):
        if path in manifest_paths:
            continue
        g = gloss if path == root / "CLAUDE.md" else ""
        rel = str(path.relative_to(root))
        before = read(path)
        keep = guard.get(rel) or set()
        if keep:
            # THE GUARDED PATH, LINE BY LINE. Identical transforms in the identical order,
            # applied to every line `ref` does not already carry and to no line it does. It
            # runs only where `protected_lines` found something, so the whole-text path below
            # stays the one the round-trip is proved on.
            kept: List[str] = []
            hits = 0
            for line in before.split("\n"):
                if line in keep:
                    kept.append(line)
                    continue
                if path == index_path and is_index_line(line, u):
                    continue
                line = unrenumber_gates(line, u) if path == root / GATES else line
                line = unrenumber_map(line, u) if path == root / MAP else line
                line, got = apply_unclaim_to_text(line, u, g)
                hits += got
                kept.append(line)
            after = "\n".join(kept)
        else:
            after = before
            if path == root / GATES:
                after = unrenumber_gates(after, u)
            if path == root / MAP:
                after = unrenumber_map(after, u)
            if path == index_path:
                after = unindex(after, u)
            after, hits = apply_unclaim_to_text(after, u, g)
        if after == before:
            continue
        touched[str(path.relative_to(root))] = hits or 1
        if write:
            path.write_text(after, encoding="utf-8")

    if u.kind in DIR_KINDS and u.old_name:
        directory = DIR_KINDS[u.kind].directory
        old_path = root / directory / u.old_name
        new_path = root / directory / u.new_name
        if old_path.exists():
            touched[f"{directory}/{u.old_name} -> {u.new_name}"] = 1
            if write:
                old_path.rename(new_path)

    for label in unsettle_manifest(root, u, write):
        touched[label] = 1
    for label in regenerate_derived(root, write):
        touched[label] = 1
    return touched


def run_unclaim(root: Path, ident: str, to_slug: Optional[str], ref: str, write: bool) -> int:
    """`--unclaim`'s whole body: plan, check it is safe, then perform or preview it."""
    # THE REF IS RESOLVED FIRST, BEFORE THE PLAN, AND THAT ORDER IS NOT COSMETIC. The plan
    # itself needs the ref now: two entry files can share one number in this tree, and which
    # of them is this branch's is a question only `ref` can answer (`find_decision_file`).
    resolved = git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", cwd=str(root)).strip()
    if not resolved:
        say(f"REFUSED: `{ref}` does not name a commit in {root}.",
            "",
            "  The safety check reads what that ref has taken. Without it there is nothing",
            "  to check against, and unclaiming on a guess is the thing this command exists",
            "  to prevent — same rule as the allocation itself.")
        return 2

    try:
        u = plan_unclaim(root, ident, to_slug, ref=ref, cwd=str(root))
    except ValueError as exc:
        say(f"REFUSED: {exc}")
        return 2

    taken = ids_at(ref, cwd=str(root))
    note: List[str] = []
    guard: Dict[str, Set[str]] = {}
    if u.number in taken[u.kind]:
        if same_entry_on_ref(root, ref, u, cwd=str(root)):
            say(f"REFUSED: {u.token} on `{ref}` IS this entry.",
                "",
                f"  Unclaiming it would put `{u.becomes}` back into this tree while `{ref}`",
                f"  answers every citation of {u.token} with the SAME entry — a substitution",
                "  on this token then reaches main's own copy too, which is exactly what",
                "  `stale_claims` refuses in the other direction and for the same reason.",
                "",
                "  D140's design assumes a claimed number is permanent the moment it reaches",
                f"  `{ref}`. This branch's own claim of {u.token} already correctly landed",
                "  there — there is nothing stale to put back.")
            return 3
        # `ref` has an entry at this number too, but it is a DIFFERENT one — the exact shape
        # D186's own landing collided with: two unrelated branches independently claimed the
        # same next free number, and this branch's own copy is the one that lost the race.
        # Unclaiming touches only THIS branch's own file; `ref`'s entry is untouched by name
        # or by number.
        # AND `ONLY THIS BRANCH'S OWN COPY IS TOUCHED` IS NOW TRUE. It was a claim this
        # function made and nothing enforced: the substitution is keyed on the token, so
        # every citation of the OTHER entry was rewritten too wherever this tree could see
        # one. It could not see any until a branch merged `ref` in — and that merge is the
        # documented pre-merge step, so the state where the sentence was false is the state
        # a branch reaches by following the routine. `protected_lines` is what makes it hold.
        guard = protected_lines(ref, u, cwd=str(root))
        note = [
            f"  NOTE: `{ref}` also carries {u.token}, but for a DIFFERENT entry — this is",
            "  the collision this command exists to fix, not a reason to refuse. Only this",
            f"  branch's own copy is touched; every line `{ref}` itself carries is left",
            "  exactly as it is, so the other entry keeps its number AND its citations.",
            "",
        ]

    say(f"PKMNSCAN — unclaim {u.token} -> {u.becomes}{'' if write else '  (PREVIEW)'}")
    say("=" * 72, "")
    if note:
        say(*note)
    touched = perform_unclaim(root, u, write, guard=guard)
    for name in sorted(touched):
        say(f"  {'rewrote' if write else 'would rewrite'}  {name}")
    say("", f"  1 id, {len(touched)} file(s).")
    if not write:
        say("", "  PREVIEW — nothing was written. Add --write to perform it.")
    else:
        say("",
            f"  Run `python3 scripts/claim-ids.py --ref {ref}` to see it allocated again —",
            "  that is the whole point: a fresh number against main as it stands now, rather",
            "  than the one that went stale.")
    return 0


# ------------------------------------------------------------------------------------ cli


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="claim the numbers this branch's slug ids will take (D140)")
    parser.add_argument("--ref", default="origin/main",
                        help="allocate against this ref's ids (default: origin/main)")
    parser.add_argument("--write", action="store_true",
                        help="perform the substitution. Without it, nothing is written.")
    parser.add_argument("--root", default=str(ROOT),
                        help="the checkout to act on (default: this one)")
    parser.add_argument("--porcelain", action="store_true",
                        help="one `slug number` line per claim, for a caller")
    parser.add_argument("--stale", action="store_true",
                        help="report allocated ids this branch adds that the ref has taken "
                             "since, and exit 3 if there are any. Writes nothing, ever.")
    parser.add_argument("--landed", metavar="REV",
                        help="report every unclaimed id REV's own trees carry, and exit 3 if "
                             "there are any. The subject is a COMMIT and never a checkout. "
                             "Writes nothing, ever.")
    parser.add_argument("--unclaim", metavar="ID",
                        help="put an already-claimed id back to slug form: `D188`, `C4`, "
                             "`step 12`, or `DEBT48`. The exact inverse of a claim, for the id "
                             "`stale_claims` reported gone stale — REFUSES when ID is already "
                             "on --ref, since an id main holds is not this branch's to give "
                             "back. Previews by default; needs --write to perform it.")
    parser.add_argument("--to-slug", metavar="SLUG",
                        help="the bare slug (no letter, no `step `) a codes id or a build "
                             "step reverts to. REQUIRED for both, because neither keeps its "
                             "slug anywhere once claimed — a decision's and a debt's both do, "
                             "in their own entry's filename, which --unclaim reads automatically. Ignored "
                             "for a decision id unless it is given, in which case it "
                             "overrides the filename's own tail.")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()

    # ANSWERED BEFORE `--ref` IS RESOLVED, because it does not use one. `--landed` reads a
    # commit's own trees; there is no allocation in it and nothing to allocate against, so a
    # checkout with no remote-tracking branch can still be asked what a commit carries.
    if args.landed:
        return report_landed(root, args.landed)

    # ALSO ANSWERED BEFORE THE SHARED `--ref` RESOLUTION BELOW, because `run_unclaim` does its
    # own — the message it prints on a bad ref is about the SAFETY CHECK rather than about an
    # allocation, and folding it into the generic block above would blur the two.
    if args.unclaim:
        return run_unclaim(root, args.unclaim, args.to_slug, args.ref, args.write)

    # `--verify` AND `^{commit}`, because a bare `git rev-parse foo` prints `foo` on STDOUT
    # and puts the error on stderr — which this reader discards. The refusal below was
    # unreachable without it, and the command went on to allocate against nothing.
    resolved = git("rev-parse", "--verify", "--quiet", f"{args.ref}^{{commit}}",
                   cwd=str(root)).strip()
    # THE STALENESS HALF ALLOWS WHERE THE CLAIM REFUSES, and the asymmetry is deliberate. A
    # claim that cannot read the ref must not guess — that is the entire entry. A staleness
    # check that cannot read it has simply not been asked a question it can answer, and it is
    # in `make check`, which runs in a fresh clone that may carry no remote-tracking branch at
    # all. `revert-guard` makes the same call for the same reason and says so on the way past.
    if args.stale and not resolved:
        say(f"PKMNSCAN — ids this branch adds, checked against {args.ref}")
        say("=" * 72, "")
        say(f"  no `{args.ref}` in this checkout — there is nothing to check against.",
            "  ALLOWED, and not a failure: a clone with no remote-tracking branch cannot be",
            "  asked whether an id has gone stale. `make merge` fetches before it asks.")
        return 0
    if not resolved:
        say(f"REFUSED: `{args.ref}` does not name a commit in {root}.",
            "",
            "  The allocation reads what that ref has taken. Without it there is nothing to",
            "  allocate against, and guessing is the thing this command exists to delete.")
        return 2

    # `--porcelain` KEEPS ITS CONTRACT EXACTLY, and is the one caller the staleness half does
    # not run for. scripts/merge-pr.py reads this stream for claim lines and treats a non-zero
    # exit as "no claims are pending", so refusing here would SKIP the claim silently — the
    # opposite of what a guard is for. That caller asks for `--stale` in its own right, first.
    if args.porcelain:
        # TAB, not a space: a step's token is the word `step` and a slug, so a space-separated line
        # cannot be split by a caller. scripts/merge-pr.py is that caller.
        for claim in plan(root, args.ref, cwd=str(root)):
            say(f"{claim.token}\t{claim.becomes}")
        return 0

    if args.stale and merging(cwd=str(root)):
        say(f"PKMNSCAN — ids this branch adds, checked against {args.ref}")
        say("=" * 72, "")
        say("  a merge is in progress and not yet committed — there is nothing to check yet.",
            "  ALLOWED, and not a failure: this tree already holds the other side's entries",
            "  while the merge base has not moved, so every id that merge brought in would",
            "  read as this branch's own. Commit the merge and run it again.")
        return 0

    base = merge_base(args.ref, cwd=str(root))
    if not base:
        say(f"REFUSED: `{args.ref}` and HEAD share no commit in {root}.",
            "",
            "  What this branch ADDS is its difference against the commit the two share.",
            "  Without one there is no baseline, and treating the whole branch as added would",
            "  report every id main already holds as a collision.")
        return 2
    stale = stale_claims(root, args.ref, base, cwd=str(root))
    dupes = duplicate_pending(root, args.ref, cwd=str(root))
    doubled = duplicate_numbers(root)

    if args.stale:
        say(f"PKMNSCAN — ids this branch adds, checked against {args.ref}")
        say("=" * 72, "")
        if doubled:
            report_duplicate_numbers(doubled, args.ref)
            return 3
        if dupes:
            report_duplicate(dupes, args.ref)
            return 3
        if not stale:
            say("  every id this branch adds is still free — nothing has gone stale.")
            return 0
        report_stale(stale, args.ref)
        return 3

    say(f"PKMNSCAN — claim ids against {args.ref}{'' if args.write else '  (PREVIEW)'}")
    say("=" * 72, "")

    # CHECKED BEFORE ANYTHING IS WRITTEN. A tree carrying a collision is one no merge may
    # proceed on, and performing the claim beside it would commit a fresh number and a stale
    # one together — leaving the branch worse off than the run that refused.
    if doubled:
        report_duplicate_numbers(doubled, args.ref)
        return 3
    if dupes:
        report_duplicate(dupes, args.ref)
        return 3
    if stale:
        report_stale(stale, args.ref)
        return 3

    claims = plan(root, args.ref, cwd=str(root))
    if not claims:
        # THE SECOND SENTENCE IS THE WHOLE POINT OF D140's 2026-09-11 amendment. The first line
        # alone was a true statement about slugs that a reader took for a statement about safety.
        say("  no unclaimed slug in this tree — nothing to claim.",
            f"  and every id this branch adds is still free on `{args.ref}`.")
        return 0
    for claim in claims:
        say(f"  {claim.token}  ->  {claim.becomes}")
    say("")
    touched = perform(root, claims, args.write)
    for name in sorted(touched):
        say(f"  {'rewrote' if args.write else 'would rewrite'}  {name}")
    say("", f"  {len(claims)} id(s), {len(touched)} file(s).")
    if not args.write:
        say("", "  PREVIEW — nothing was written. Add --write to perform it.")
    else:
        say("", "  Run `make check` before pushing: the claim is exhaustive by construction,",
            "  and `id claims` is what proves no slug survived it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
