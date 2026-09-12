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
D72 records what that costs thirteen times over.

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
# standing answer to that shape — `port-agreement`, `set-hint-agreement`, `logo parity`.
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
CODES_DECISIONS = "docs/CODES-DECISIONS.md"
MAP = "docs/map.py"
GATES = "docs/GATES.md"

# THE THREE NAMESPACES, DECLARED ONCE AND READ TWICE. `ceiling_at` asks each for its highest
# allocated id and `stale_claims` asks the same three for their whole sets. Spelling the list
# out at both call sites is how a fourth namespace arrives in one of them and not the other,
# which is the shape `storage keys` and `codex hooks` both exist to catch elsewhere in this
# repo. The last field is the form a person READS the id in, which is also the token every
# citation of it carries.
KINDS = (
    ("decision", DECISIONS, DECISION_HEADING, "D{0}"),
    ("codes", CODES_DECISIONS, CODES_HEADING, "C{0}"),
    ("step", GATES, GATES_NUMBERED, "step {0}"),
)

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
    kind: str      # "decision" | "codes" | "step"
    slug: str      # the unclaimed form, with its letter for D and C and bare for a step
    number: str    # the allocated form: a letter and digits, or a bare number for a step
    token: str     # the exact text replaced
    becomes: str   # the exact text written


def say(*lines: str) -> None:
    for line in lines:
        print(line)


def git(*args: str, cwd: Optional[str] = None) -> str:
    try:
        done = subprocess.run(["git"] + list(args), cwd=cwd or str(ROOT),
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    except OSError:
        return ""
    return done.stdout.decode("utf-8", errors="replace")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def text_files(root: Path) -> List[Path]:
    """Every tracked-looking text file under `root`, excluding the trees SKIP names."""
    out: List[Path] = []
    for base, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP and not d.startswith("."))
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
    return out


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


def ceiling_at(ref: str, cwd: Optional[str] = None) -> Dict[str, int]:
    """The highest allocated id of each kind, as of `ref`.

    READ FROM THE REF AND NEVER FROM THE WORKING TREE. The whole point is to allocate against
    what main holds at the moment of the merge; allocating against the branch's own copy is
    the guess this entry exists to delete.
    """
    return {kind: highest(corpus_text_at(ref, cwd=cwd) if kind == "decision"
                          else git("show", f"{ref}:{path}", cwd=cwd), pattern)
            for kind, path, pattern, _ in KINDS}


# ------------------------------------------------------------------------- what is unclaimed


def pending_in(decisions: str, codes: str, gates: str) -> Dict[str, List[str]]:
    """Every slug HEADING in these three texts, by kind, in the order they declare them.

    Headings rather than citations: a citation of a slug that has no heading is a dangling
    id, which is `id claims`' job to report and not this command's to invent an entry for.

    TEXTS RATHER THAN A DIRECTORY, SO THE SAME READER CAN BE POINTED AT A COMMIT. `pending`
    hands it a working tree and `pending_at` hands it `git show` output, and the grammar is
    declared once for both. A second declaration of these three patterns is how a heading
    shape that one reader accepts becomes one the other cannot see.
    """
    out: Dict[str, List[str]] = {"decision": [], "codes": [], "step": []}
    out["decision"] = [f"D{i}" for i in DECISION_HEADING.findall(decisions) if i.startswith("-")]
    out["codes"] = [f"C{i}" for i in CODES_HEADING.findall(codes) if i.startswith("-")]
    out["step"] = re.findall(r"^0\.\s+`step (" + SLUG + r")`", gates, re.M)
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


def corpus_text(root: Path) -> str:
    """The entries of a working tree, concatenated in manifest order."""
    manifest = root / DECISIONS_MANIFEST
    if not manifest.exists():
        return read(root / DECISIONS) if (root / DECISIONS).exists() else ""
    order = json.loads(read(manifest))["order"]
    return "\n".join(read(root / DECISIONS_DIR / name)
                     for name in order if (root / DECISIONS_DIR / name).exists())


def corpus_text_at(rev: str, cwd: Optional[str] = None) -> str:
    """The entries AT A COMMIT, concatenated in that commit's own manifest order.

    Falls back to that commit's `docs/DECISIONS.md` when it has no manifest, which is every
    commit before the split — so `ceiling_at` and `pending_at` keep answering across the
    boundary rather than reporting a repository with no decisions in it.
    """
    manifest = git("show", f"{rev}:{DECISIONS_MANIFEST}", cwd=cwd)
    if not manifest.strip():
        return git("show", f"{rev}:{DECISIONS}", cwd=cwd)
    try:
        order = json.loads(manifest)["order"]
    except Exception:
        return git("show", f"{rev}:{DECISIONS}", cwd=cwd)
    return "\n".join(git("show", f"{rev}:{DECISIONS_DIR}/{name}", cwd=cwd) for name in order)


def pending(root: Path) -> Dict[str, List[str]]:
    """`pending_in` over a working tree."""
    return pending_in(
        corpus_text(root),
        read(root / CODES_DECISIONS) if (root / CODES_DECISIONS).exists() else "",
        read(root / GATES) if (root / GATES).exists() else "",
    )


def pending_at(rev: str, cwd: Optional[str] = None) -> Dict[str, List[str]]:
    """`pending_in` over a COMMIT, which is a different question from the one above.

    Every other reader in this file asks about a checkout. This one asks what a commit
    CARRIES, and it exists because the invariant the whole design rests on — main carries no
    slug — is a claim about main's own trees and not about anybody's working directory. A
    file missing at that commit reads as empty, which is right: a repository with no
    docs/CODES-DECISIONS.md has no unclaimed code-card id in it.
    """
    return pending_in(
        corpus_text_at(rev, cwd=cwd),
        git("show", f"{rev}:{CODES_DECISIONS}", cwd=cwd),
        git("show", f"{rev}:{GATES}", cwd=cwd),
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
                letter = slug[0]
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
    kind: str      # "decision" | "codes" | "step"
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
    """
    out: List[Stale] = []
    ceiling = ceiling_at(ref, cwd=cwd)
    for kind, path, pattern, shape in KINDS:
        here = read(root / path) if (root / path).exists() else ""
        added = allocated_ids(here, pattern) - allocated_ids(
            git("show", f"{base}:{path}", cwd=cwd), pattern)
        taken = allocated_ids(git("show", f"{ref}:{path}", cwd=cwd), pattern)
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
        "  Put the id back to the slug form and let the merge allocate it again — a heading",
        f"  `## {'D-' + 'two-lowercase-segments'}` for an entry, a `0.` list marker carrying",
        f"  `{'step ' + 'two-lowercase-segments'}` for a build step — then `make claim-ids`",
        "  previews what it would take against main as it stands now.")


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


def rename_claimed_entries(root: Path, claims: Sequence[Claim], write: bool) -> Dict[str, str]:
    """Rename each claimed entry's FILE, and rewrite the manifest to match.

    A CLAIM USED TO BE A SUBSTITUTION AND NOTHING ELSE. With the corpus as a directory it is
    also a rename: the slug-named file holds a heading that now reads as a number, and a file
    named after an id it no longer carries is the drift `path_for` would resolve wrongly.

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
    renames: Dict[str, str] = {}
    manifest_path = root / DECISIONS_MANIFEST
    if not manifest_path.exists():
        return renames
    manifest = json.loads(read(manifest_path))
    order = list(manifest["order"])
    for claim in claims:
        if claim.kind != "decision":
            continue
        old_name = next((n for n in order if n.startswith(claim.slug + "-")
                         or n == claim.slug + ".md"), None)
        if old_name is None:
            continue
        # THE DESCRIPTIVE TAIL IS THE SLUG WITHOUT ITS LEADING LETTER AND DASH. A slug
        # heading's file is named for the whole slug, so there is no separate tail to lift
        # off; treating it as if there were produced a bare numeric filename that says
        # nothing and sorts nowhere near its neighbours.
        number = int(claim.number[1:])
        described = claim.slug[2:] if claim.slug.startswith("D-") else claim.slug
        tail = old_name[len(claim.slug) + 1:-3] if old_name.startswith(claim.slug + "-") else described
        new_name = f"D{number:03d}-{tail}.md"
        renames[old_name] = new_name
        order[order.index(old_name)] = new_name
        if write:
            (root / DECISIONS_DIR / old_name).rename(root / DECISIONS_DIR / new_name)
    if renames and write:
        manifest["order"] = order
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return renames


def perform(root: Path, claims: Sequence[Claim], write: bool) -> Dict[str, int]:
    """Substitute every claim across the tree. Returns path -> replacements."""
    touched: Dict[str, int] = {}
    manifest_path = root / DECISIONS_MANIFEST
    for path in text_files(root):
        # The manifest is names, not prose, and `rename_claimed_entries` owns it. Belt and
        # braces — the token grammar already declines a match inside a longer slug. See there.
        if path == manifest_path:
            continue
        before = read(path)
        after = before
        if path == root / GATES:
            after = renumber_gates(after, claims)
        if path == root / MAP:
            after = renumber_map(after, claims)
        after, _ = apply_to_text(after, claims)
        if after == before:
            continue
        touched[str(path.relative_to(root))] = sum(
            len(re.findall(r"\b" + re.escape(c.token) + r"\b", before)) for c in claims
        ) or 1
        if write:
            path.write_text(after, encoding="utf-8")
    for old_name, new_name in rename_claimed_entries(root, claims, write).items():
        touched[f"{DECISIONS_DIR}/{old_name} -> {new_name}"] = 1
    return touched


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
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()

    # ANSWERED BEFORE `--ref` IS RESOLVED, because it does not use one. `--landed` reads a
    # commit's own trees; there is no allocation in it and nothing to allocate against, so a
    # checkout with no remote-tracking branch can still be asked what a commit carries.
    if args.landed:
        return report_landed(root, args.landed)

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

    if args.stale:
        say(f"PKMNSCAN — ids this branch adds, checked against {args.ref}")
        say("=" * 72, "")
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
