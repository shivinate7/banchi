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


def corpus_order(root: Path) -> List[str]:
    """Corpus membership: the manifest's list, then anything on disk it has not been told of.

    DERIVED, BECAUSE A BRANCH DOES NOT EDIT THE MANIFEST. An entry-adding branch carries its
    own file and nothing shared — `settle_corpus` writes the manifest at claim time. A
    claimer reading only the manifest would therefore be blind to exactly the entry it exists
    to claim, which is how this was found: an unregistered slug reported `nothing to claim`
    while sitting in the directory.
    """
    manifest = root / DECISIONS_MANIFEST
    if not manifest.exists():
        return []
    listed = json.loads(read(manifest))["order"]
    known = set(listed)
    extra = sorted(p.name for p in (root / DECISIONS_DIR).glob("*.md")
                   if p.name not in known)
    return listed + extra


def corpus_text(root: Path) -> str:
    """The entries of a working tree, concatenated in corpus order."""
    if not (root / DECISIONS_MANIFEST).exists():
        return read(root / DECISIONS) if (root / DECISIONS).exists() else ""
    return "\n".join(read(root / DECISIONS_DIR / name)
                     for name in corpus_order(root)
                     if (root / DECISIONS_DIR / name).exists())


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
        if kind == "decision":
            here = corpus_text(root)
            was = corpus_text_at(base, cwd=cwd)
            now = corpus_text_at(ref, cwd=cwd)
        else:
            here = read(root / path) if (root / path).exists() else ""
            was = git("show", f"{base}:{path}", cwd=cwd)
            now = git("show", f"{ref}:{path}", cwd=cwd)
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
        if item.kind == "decision":
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
    """(pending slug, the number `ref` already claimed it under) for every decision slug this
    branch still carries unclaimed that `ref` has already resolved under a different number.

    DECISIONS ONLY. `codes` and `step` slugs are headings inside one shared file apiece, never
    a filename of their own — the rename ambiguity this function exists for cannot arise for
    either, and `decision index`/`id claims` already watch the shared-file kinds for the
    ordinary two-number collision.
    """
    out: List[Tuple[str, str]] = []
    listing = git("ls-tree", "-r", "--name-only", ref, "--", DECISIONS_DIR, cwd=cwd)
    claimed_text = {}
    for name in listing.splitlines():
        m = re.match(r"^D(\d+)-(.+)\.md$", Path(name).name)
        if m:
            claimed_text[m.group(2)] = m.group(1)
    for slug in pending(root)["decision"]:
        text = slug[len("D-"):] if slug.startswith("D-") else slug
        if text in claimed_text:
            out.append((slug, f"D{claimed_text[text]}"))
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
    2026-09-19: `docs/specs/revenue-plan.md` cited a still-unclaimed entry as
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
    (`docs/DEBTS.md`'s header cites it for `DEBT<n>` the same way) — a decision is cited by
    its bare `D<n>`, the form `Claim.becomes` already carries, and the path is dropped
    entirely rather than repaired. No new formatter is built for this: `claim.becomes` is
    already the exact citation form the rest of this file uses everywhere else.

    RUNS BEFORE `apply_to_text`, MATCHING `renumber_gates`/`renumber_map`'s OWN ORDERING, so
    it still has the slug to find the path by; the generic pass then finds nothing left to
    double-substitute inside what was the path, and still catches every OTHER, bare citation
    of the same token elsewhere in the file.

    DECISIONS ONLY. A codes id and a build step have no file of their own to be pointed at —
    `docs/CODES-DECISIONS.md` and `docs/GATES.md` are one shared file apiece, never a
    directory with one file per entry — so there is no path shape for either to produce, and
    none is built here for a citation that cannot exist.
    """
    for claim in claims:
        if claim.kind != "decision":
            continue
        # THE FILE'S OWN TAIL, AND NOT ONLY THE BARE `<token>.md`, MATCHING
        # `rename_claimed_entries`'S OWN RULE: that function finds the pre-claim file by
        # `n.startswith(claim.slug + "-") or n == claim.slug + ".md"`, because the file a
        # branch writes may carry more descriptive text after the slug than the slug's own
        # citation form does. A citation naming that same file has to be found by the same
        # rule, or a longer-tailed filename would leave its own path citation unrewritten
        # while the file underneath it renamed. An optional backtick on each side: every
        # live example in this tree backtick-quotes the path, but the citation is dropped
        # either way rather than left half-repaired.
        pattern = re.compile(r"`?docs/decisions/" + re.escape(claim.token) + r"[\w-]*\.md`?")
        text = pattern.sub(claim.becomes, text)
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
    listed = list(manifest["order"])
    # The file may not be in the manifest yet — a branch does not put it there. Look in the
    # DERIVED order so a claim can rename an entry the manifest has never heard of.
    order = corpus_order(root)
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
        if old_name in listed:
            listed[listed.index(old_name)] = new_name
        if write:
            (root / DECISIONS_DIR / old_name).rename(root / DECISIONS_DIR / new_name)
    if renames and write:
        # Only what the manifest already NAMED is rewritten here; an entry it has never heard
        # of is appended by `settle_corpus`, which runs after this and knows the final order.
        manifest["order"] = listed
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
        after = rewrite_decision_paths(after, claims)
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
    for label in settle_corpus(root, write):
        touched[label] = 1
    return touched


def settle_corpus(root: Path, write: bool) -> List[str]:
    """Write the two DERIVED things at claim time: the manifest's order and the index.

    THE MERGE IS THE ONE MOMENT EITHER IS KNOWABLE, which is exactly D140's argument for the
    number and the reason both belong here rather than on a branch. A branch adding an entry
    would otherwise have to append to a shared JSON array and add a line to CLAUDE.md's index
    at the position every other such branch touches — two more collisions, in the change that
    exists to remove one.

    So a branch carries its entry FILE and nothing shared. Corpus membership is derived by
    `decisions_corpus.order()` until this runs, and the index is regenerated from the headings
    that exist after the claim — including the number this claim just allocated, which is why
    it runs AFTER the substitution and the rename rather than beside them.

    D18 PUTS THIS ON THE WRITING SIDE and keeps the checking side elsewhere: `decision index`
    still computes the index independently and blocks, and it is a different program. A
    generator that also gated could satisfy itself.
    """
    moved: List[str] = []
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "index_decisions", root / "scripts" / "index-decisions.py")
        index = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(index)
    except Exception as exc:                       # a tree without the generator still claims
        return [f"(index generator not runnable: {exc})"]
    try:
        appended = index.normalize(root, write)
        if appended:
            moved.append(f"{DECISIONS_MANIFEST} (+{len(appended)} entry)")
        if index.rewrite_index(root, write):
            moved.append("CLAUDE.md (decision index regenerated)")
    except Exception as exc:
        return [f"(corpus not settled: {exc})"]
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
# `docs/CODES-DECISIONS.md` is one file for the whole codes corpus and `docs/GATES.md`'s build
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
    kind: str        # "decision" | "codes" | "step"
    number: int       # the bare integer: 188, 4, 12
    token: str        # the literal claimed form, as it is cited in prose: "D188", "C4", "step 12"
    becomes: str      # the literal slug form citations revert to: "D-...", "C-...", "step ..."
    slug: str         # the BARE slug, no letter and no `step ` prefix — what `--to-slug` takes
    old_name: str = ""  # decisions only: the D<n>-<slug>.md file this checkout holds right now
    new_name: str = ""  # decisions only: the D-<slug>.md file it reverts to


_UNCLAIM_DECISION = re.compile(r"^D([1-9][0-9]{0,2})$")
_UNCLAIM_CODES = re.compile(r"^C([1-9][0-9]{0,2})$")
_UNCLAIM_STEP = re.compile(r"^step\s+([1-9][0-9]*)$")


def parse_claimed_ident(ident: str) -> Tuple[str, int]:
    """(kind, number) for a CLAIMED id's own spelling, or raises ValueError.

    A CLAIMED ID, NEVER A SLUG — there is nothing to unclaim from a slug, because a slug is
    already the form this command puts things back into. Rejecting one here is the same
    refusal-over-guessing this whole file is built on, one function along.
    """
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
        f"of the three namespaces this file allocates: `D188`, `C4`, `step 12` — never a "
        f"slug, since a slug is already unclaimed.")


def find_decision_file(root: Path, number: int) -> Tuple[Optional[Path], str]:
    """The claimed entry's own file, and the slug tail its filename still carries.

    THE FILENAME IS THE ONE SURVIVING RECORD. `rename_claimed_entries` renames the slug-named
    file to `D<n>-<tail>.md` rather than deleting it, so the tail after the number is exactly
    the descriptive half of the original slug — no guessing, the same fact `plan_unclaim`'s
    docstring above spells out. `None` when there is not exactly one match: zero is "not
    claimed here", and more than one is refused rather than picked from.
    """
    prefix = f"D{number:03d}-"
    matches = sorted((root / DECISIONS_DIR).glob(prefix + "*.md"))
    if len(matches) != 1:
        return None, ""
    path = matches[0]
    return path, path.stem[len(prefix):]


def plan_unclaim(root: Path, ident: str, to_slug: Optional[str]) -> Unclaim:
    """The single reverse claim for an already-claimed id. Raises ValueError to refuse."""
    kind, number = parse_claimed_ident(ident)

    if kind == "decision":
        path, tail = find_decision_file(root, number)
        if path is None:
            raise ValueError(
                f"no single {DECISIONS_DIR}/D{number:03d}-*.md file in this tree — `{ident}` "
                f"is not a claimed decision this checkout holds.")
        heading = read(path).split("\n", 1)[0]
        if not re.match(r"^##\s+D" + str(number) + r"\b", heading):
            raise ValueError(
                f"{path.relative_to(root)}: heading is {heading!r}, which does not start "
                f"`## D{number}` — refusing to guess which entry this is.")
        bare = to_slug if to_slug else tail
        if not re.fullmatch(SLUG, bare):
            raise ValueError(
                f"{bare!r} is not a slug — two or more lowercase hyphenated segments.")
        slug = "D-" + bare
        return Unclaim("decision", number, f"D{number}", slug, bare,
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
    if u.kind == "decision":
        path, _ = find_decision_file(root, u.number)
        return read(path).split("\n", 1)[0] if path else ""
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
    if u.kind == "decision":
        listing = git("ls-tree", "-r", "--name-only", ref, DECISIONS_DIR, cwd=cwd)
        prefix = f"{DECISIONS_DIR}/D{u.number:03d}-"
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


def apply_unclaim_to_text(text: str, u: Unclaim) -> Tuple[str, int]:
    """`apply_to_text`'s own bound, run with the token and the replacement swapped.

    THE SAME `(?<![-\\w])...(?![-\\w])` GUARD, reused rather than rebuilt, is the whole point:
    a hand-rolled reverse would have to remember the `\\b`-boundary bug independently, and
    this one cannot forget it because it is not a second implementation.
    """
    pattern = re.compile(r"(?<![-\w])" + re.escape(u.token) + r"(?![-\w])")
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

    ONLY A DECISION HAS ONE TO REMOVE: codes and steps get no index line from `settle_corpus`
    to begin with (the index is `docs/decisions/`'s alone).
    """
    if u.kind != "decision":
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
    if u.kind != "decision":
        return moved
    manifest_path = root / DECISIONS_MANIFEST
    if not manifest_path.exists():
        return moved
    manifest = json.loads(read(manifest_path))
    order = list(manifest["order"])
    if u.old_name not in order:
        return moved
    order.remove(u.old_name)
    manifest["order"] = order
    if write:
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    moved.append(f"{DECISIONS_MANIFEST} (-1 entry)")
    return moved


def perform_unclaim(root: Path, u: Unclaim, write: bool) -> Dict[str, int]:
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
    manifest_path = root / DECISIONS_MANIFEST
    claude_path = root / "CLAUDE.md"
    for path in text_files(root):
        if path == manifest_path:
            continue
        before = read(path)
        after = before
        if path == root / GATES:
            after = unrenumber_gates(after, u)
        if path == root / MAP:
            after = unrenumber_map(after, u)
        if path == claude_path:
            after = unindex(after, u)
        after, hits = apply_unclaim_to_text(after, u)
        if after == before:
            continue
        touched[str(path.relative_to(root))] = hits or 1
        if write:
            path.write_text(after, encoding="utf-8")

    if u.kind == "decision" and u.old_name:
        old_path = root / DECISIONS_DIR / u.old_name
        new_path = root / DECISIONS_DIR / u.new_name
        if old_path.exists():
            touched[f"{DECISIONS_DIR}/{u.old_name} -> {u.new_name}"] = 1
            if write:
                old_path.rename(new_path)

    for label in unsettle_manifest(root, u, write):
        touched[label] = 1
    return touched


def run_unclaim(root: Path, ident: str, to_slug: Optional[str], ref: str, write: bool) -> int:
    """`--unclaim`'s whole body: plan, check it is safe, then perform or preview it."""
    try:
        u = plan_unclaim(root, ident, to_slug)
    except ValueError as exc:
        say(f"REFUSED: {exc}")
        return 2

    resolved = git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", cwd=str(root)).strip()
    if not resolved:
        say(f"REFUSED: `{ref}` does not name a commit in {root}.",
            "",
            "  The safety check reads what that ref has taken. Without it there is nothing",
            "  to check against, and unclaiming on a guess is the thing this command exists",
            "  to prevent — same rule as the allocation itself.")
        return 2

    taken = ids_at(ref, cwd=str(root))
    note: List[str] = []
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
        note = [
            f"  NOTE: `{ref}` also carries {u.token}, but for a DIFFERENT entry — this is",
            "  the collision this command exists to fix, not a reason to refuse. Only this",
            f"  branch's own copy is touched; the one on `{ref}` keeps its number.",
            "",
        ]

    say(f"PKMNSCAN — unclaim {u.token} -> {u.becomes}{'' if write else '  (PREVIEW)'}")
    say("=" * 72, "")
    if note:
        say(*note)
    touched = perform_unclaim(root, u, write)
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
                        help="put an already-claimed id back to slug form: `D188`, `C4`, or "
                             "`step 12`. The exact inverse of a claim, for the id "
                             "`stale_claims` reported gone stale — REFUSES when ID is already "
                             "on --ref, since an id main holds is not this branch's to give "
                             "back. Previews by default; needs --write to perform it.")
    parser.add_argument("--to-slug", metavar="SLUG",
                        help="the bare slug (no letter, no `step `) a codes id or a build "
                             "step reverts to. REQUIRED for both, because neither keeps its "
                             "slug anywhere once claimed — only a decision's does, in its own "
                             "entry's filename, which --unclaim reads automatically. Ignored "
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

    if args.stale:
        say(f"PKMNSCAN — ids this branch adds, checked against {args.ref}")
        say("=" * 72, "")
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
