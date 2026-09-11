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

IT WRITES, SO IT IS NOT ON THE COMMIT PATH (D18) and it is not in `make check`. Its self-test
is — `make claim-selftest`, against a throwaway repository.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

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

# Binary and generated trees the substitution has no business walking. `.git` is the one that
# would be catastrophic rather than merely slow.
SKIP = {".git", "node_modules", "dist", "dist-demo", "captures", "inventory", "runs",
        "__pycache__", ".venv", "venv", "test-results", "playwright-report", ".serve",
        "worktrees", "demo-assets", "harness/images"}
TEXT_SUFFIXES = {".md", ".py", ".ts", ".tsx", ".css", ".html", ".json", ".txt", ".yml",
                 ".yaml", ".sh", ".mjs", ".toml"}


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
    return out


# --------------------------------------------------------------------- what main has taken


def highest(text: str, pattern: re.Pattern) -> int:
    """The largest allocated id in `text`, or 0. Slug headings are not numbers and are skipped."""
    found = [int(m) for m in pattern.findall(text) if str(m).lstrip("-").isdigit()]
    return max(found) if found else 0


def ceiling_at(ref: str, cwd: Optional[str] = None) -> Dict[str, int]:
    """The highest allocated id of each kind, as of `ref`.

    READ FROM THE REF AND NEVER FROM THE WORKING TREE. The whole point is to allocate against
    what main holds at the moment of the merge; allocating against the branch's own copy is
    the guess this entry exists to delete.
    """
    decisions = git("show", f"{ref}:{DECISIONS}", cwd=cwd)
    codes = git("show", f"{ref}:{CODES_DECISIONS}", cwd=cwd)
    gates = git("show", f"{ref}:{GATES}", cwd=cwd)
    return {
        "decision": highest(decisions, DECISION_HEADING),
        "codes": highest(codes, CODES_HEADING),
        "step": max([int(n) for n in GATES_NUMBERED.findall(gates)] or [0]),
    }


# ------------------------------------------------------------------------- what is unclaimed


def pending(root: Path) -> Dict[str, List[str]]:
    """Every slug HEADING in the tree, by kind, in the order the files declare them.

    Headings rather than citations: a citation of a slug that has no heading is a dangling
    id, which is `id claims`' job to report and not this command's to invent an entry for.
    """
    out: Dict[str, List[str]] = {"decision": [], "codes": [], "step": []}
    decisions = read(root / DECISIONS) if (root / DECISIONS).exists() else ""
    codes = read(root / CODES_DECISIONS) if (root / CODES_DECISIONS).exists() else ""
    gates = read(root / GATES) if (root / GATES).exists() else ""
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


def perform(root: Path, claims: Sequence[Claim], write: bool) -> Dict[str, int]:
    """Substitute every claim across the tree. Returns path -> replacements."""
    touched: Dict[str, int] = {}
    for path in text_files(root):
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
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()

    # `--verify` AND `^{commit}`, because a bare `git rev-parse foo` prints `foo` on STDOUT
    # and puts the error on stderr — which this reader discards. The refusal below was
    # unreachable without it, and the command went on to allocate against nothing.
    if not git("rev-parse", "--verify", "--quiet", f"{args.ref}^{{commit}}", cwd=str(root)).strip():
        say(f"REFUSED: `{args.ref}` does not name a commit in {root}.",
            "",
            "  The allocation reads what that ref has taken. Without it there is nothing to",
            "  allocate against, and guessing is the thing this command exists to delete.")
        return 2

    claims = plan(root, args.ref, cwd=str(root))
    if args.porcelain:
        # TAB, not a space: a step's token is the word `step` and a slug, so a space-separated line
        # cannot be split by a caller. scripts/merge-pr.py is that caller.
        for claim in claims:
            say(f"{claim.token}\t{claim.becomes}")
        return 0

    say(f"PKMNSCAN — claim ids against {args.ref}{'' if args.write else '  (PREVIEW)'}")
    say("=" * 72, "")
    if not claims:
        say("  no unclaimed slug in this tree — nothing to do.")
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
