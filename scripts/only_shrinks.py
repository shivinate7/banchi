#!/usr/bin/env python3
"""ONLY SHRINKS: the one helper every shrinking offender list reads (D280).

Four lists use it. `scripts/docs-audit.py` imports it for the `ste offenders`, `typed
interpunct` and `line anchor offenders` rows. `scripts/kit-adoption.mjs` cannot import Python,
so it runs this file as a command and reads JSON back. Before this file there were three
copies of the same rules, one in JavaScript, and a fix to one did not reach the others.

WHAT IT DECIDES, AND NOTHING ELSE.

  1. THE LIST AT THE MERGE-BASE (`list_at_merge_base`). `git merge-base HEAD origin/main`,
     then `git show <base>:<list>`. Two plain reads, so D18 holds. IT FAILS OPEN, AND SAYS
     WHY: no git, no `origin/main`, no merge-base, no list at the merge-base (the branch that
     gives the list its birth), or a list there that is not JSON. The caller prints the
     reason. It can also hand back other files as they stood at the same merge-base, so a
     caller that reads its rule definitions from source reads them at the same commit.
  2. GROWTH (`growth`). The caller turns each list into a multiset of `(rule, identity)`
     pairs. Every pair HEAD holds more often than the merge-base did is growth. Growth is
     REFUSED under a rule the merge-base defines, and ALLOWED under a rule born on this
     branch, because a new rule finds offenders nobody could list before it existed. If any
     rule the merge-base defines is missing at HEAD, ALL growth is refused: a renamed rule
     would otherwise bring every old offender back as new. A rule set that could not be read,
     at either end, allows nothing.

WHAT THE CALLER DECIDES: what an identity is, and so whether growth is counted over the whole
list or per file. The prose list counts a sentence hash over the whole list. The typed-dot list
puts the file in the identity, so a dot fixed in one file excuses nothing in another. The kit
list puts the file and the rule in the identity, one entry per pair.

    python3 scripts/only_shrinks.py base --path <list> [--reference <ref>] [--also <path> ...]
        the list at the merge-base as JSON: {document, base, reason, files}.
    python3 scripts/only_shrinks.py growth < {base, head, base_rules, head_rules}
        growth as JSON: {refused, allowed}, each a list of {rule, identity, extra, why}.
    python3 scripts/only_shrinks.py --self-test

STDLIB ONLY, because the pre-commit hook runs the audit on a bare `python3`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, NamedTuple, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = "origin/main"

Pair = Tuple[str, str]


class Growth(NamedTuple):
    """One identity HEAD holds more often than the merge-base did."""

    rule: str
    identity: str
    extra: int
    why: str


def _git(root: Path, *args: str) -> Optional[str]:
    try:
        done = subprocess.run(["git", *args], cwd=str(root), stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, check=False)
    except OSError:
        return None
    return done.stdout.decode("utf-8", errors="replace") if done.returncode == 0 else None


def list_at_merge_base(
    relpath: str,
    root: Path = ROOT,
    reference: str = REFERENCE,
    also: Sequence[str] = (),
) -> Tuple[Optional[object], str, Optional[str], Dict[str, Optional[str]]]:
    """`(document, where, base, files)`: the list as it stood at the merge-base with
    `reference`, a short merge-base id (or, with no document, the reason there is none), the
    full merge-base id, and each path in `also` as text at that commit (None when absent)."""
    base = (_git(root, "merge-base", "HEAD", reference) or "").strip()
    if not base:
        return None, (f"no merge-base between HEAD and {reference} (no git, no {reference}, "
                      "or no shared history)"), None, {}
    files = {path: _git(root, "show", f"{base}:{path}") for path in also}
    text = _git(root, "show", f"{base}:{relpath}")
    if text is None:
        return None, (f"{relpath} does not exist at the merge-base {base[:8]}, so this branch "
                      "gives it its birth and every entry is new"), base, files
    try:
        return json.loads(text), base[:8], base, files
    except ValueError as exc:
        return None, f"{relpath} at the merge-base {base[:8]} is not JSON ({exc})", base, files


def growth(
    base: Iterable[Pair],
    head: Iterable[Pair],
    base_rules: Optional[Set[str]],
    head_rules: Optional[Set[str]],
) -> Tuple[List[Growth], List[Growth]]:
    """`(refused, allowed)`: every `(rule, identity)` pair `head` holds more often than
    `base`, as a multiset. See the module docstring for the rule-born-on-branch exception and
    the removed-rule block."""
    before, after = Counter(base), Counter(head)
    if base_rules is None or head_rules is None:
        which = "the merge-base" if base_rules is None else "HEAD"
        blocked: Optional[str] = (f"the rules at {which} could not be read, so no rule can be "
                                  "shown to be new and no growth is allowed")
    else:
        removed = sorted(base_rules - head_rules)
        blocked = (f"{', '.join(chr(34) + r + chr(34) for r in removed)}, defined at "
                   f"the merge-base, {'are' if len(removed) > 1 else 'is'} missing at HEAD "
                   "(removed or renamed), so no growth is allowed") if removed else None
    refused: List[Growth] = []
    allowed: List[Growth] = []
    for (rule, identity), n in sorted(after.items()):
        extra = n - before.get((rule, identity), 0)
        if extra <= 0:
            continue
        if blocked is not None:
            refused.append(Growth(rule, identity, extra, blocked))
        elif rule in base_rules:  # type: ignore[operator]
            refused.append(Growth(rule, identity, extra,
                                  f"rule \"{rule}\" exists at the merge-base, and a rule that "
                                  "exists only shrinks"))
        else:
            allowed.append(Growth(rule, identity, extra,
                                  f"rule \"{rule}\" is not defined at the merge-base, so it was "
                                  "born on this branch and its first offenders may be listed"))
    return refused, allowed


# ------------------------------------------------------------------------------ the command


class BadInput(ValueError):
    """A command line or a request this command refuses (exit 64)."""


def _pairs(raw: object, name: str) -> List[Pair]:
    """A list of `[rule, identity]` string pairs, or BadInput."""
    if not isinstance(raw, list) or not all(
            isinstance(p, list) and len(p) == 2 and all(isinstance(x, str) for x in p) for p in raw):
        raise BadInput(f"`{name}` must be a list of [rule, identity] string pairs")
    return [(rule, identity) for rule, identity in raw]


def _rules(raw: object, name: str) -> Optional[Set[str]]:
    """A list of rule strings, or null (the rules could not be read), or BadInput. A bare
    string is refused: read as a set it would be a set of letters."""
    if raw is None:
        return None
    if not isinstance(raw, list) or not all(isinstance(r, str) for r in raw):
        raise BadInput(f"`{name}` must be a list of rule strings, or null")
    return set(raw)


def _base_args(args: List[str]) -> Tuple[str, str, List[str]]:
    """`--path`, `--reference` and each `--also`, or BadInput on a missing value or an
    unknown flag."""
    path, reference, also = None, REFERENCE, []
    while args:
        flag = args.pop(0)
        if flag not in ("--path", "--reference", "--also"):
            raise BadInput(f"unknown flag {flag!r}")
        if not args or not args[0] or args[0].startswith("--"):
            raise BadInput(f"{flag} needs a value")
        value = args.pop(0)
        if flag == "--path":
            path = value
        elif flag == "--reference":
            reference = value
        else:
            also.append(value)
    if path is None:
        raise BadInput("--path <list> is required")
    return path, reference, also


def _growth_request(text: str) -> Tuple[List[Pair], List[Pair], Optional[Set[str]], Optional[Set[str]]]:
    try:
        request = json.loads(text)
    except ValueError as exc:
        raise BadInput(f"the request is not JSON ({exc})") from exc
    if not isinstance(request, dict):
        raise BadInput("the request must be a JSON object")
    return (_pairs(request.get("base"), "base"), _pairs(request.get("head"), "head"),
            _rules(request.get("base_rules"), "base_rules"),
            _rules(request.get("head_rules"), "head_rules"))


def main(argv: Sequence[str]) -> int:
    """The command. Exit 0 with JSON on stdout, or 64 with the reason on stderr: a caller
    reads anything but 0 as "the helper could not run", and refuses all growth."""
    try:
        if argv[:1] == ["--self-test"]:
            return self_test()
        if argv[:1] == ["base"]:
            path, reference, also = _base_args(list(argv[1:]))
            document, where, base, files = list_at_merge_base(path, ROOT, reference, also)
            print(json.dumps({"document": document, "base": base,
                              "reason": None if document is not None else where, "files": files}))
            return 0
        if argv[:1] == ["growth"]:
            refused, allowed = growth(*_growth_request(sys.stdin.read()))
            print(json.dumps({"refused": [g._asdict() for g in refused],
                              "allowed": [g._asdict() for g in allowed]}))
            return 0
    except BadInput as exc:
        print(f"only_shrinks: {exc}", file=sys.stderr)
        return 64
    print(__doc__)
    return 64


# ---------------------------------------------------------------------------- the self-test


def self_test() -> int:
    """The growth rules in memory, and the merge-base read in a throwaway repository. Writes
    nothing in this checkout."""
    import tempfile

    ok = True

    def check(label: str, got, want) -> None:
        nonlocal ok
        if got == want:
            print(f"  ok   {label}")
        else:
            ok = False
            print(f"  FAIL {label}\n       got  {got!r}\n       want {want!r}")

    def why(found: List[Growth]) -> str:
        """The first answer's reason, or "" — never an IndexError on a regression."""
        return found[0].why if found else ""

    rules = {"R1", "R2"}
    base = [("R1", "a"), ("R1", "a"), ("R2", "b")]
    print("only_shrinks: growth")
    check("the same list is no growth", growth(base, base, rules, rules), ([], []))
    check("a list that only lost entries is no growth",
          growth(base, [("R1", "a")], rules, rules), ([], []))
    refused, allowed = growth(base, base + [("R1", "a")], rules, rules)
    check("RED: a third copy of an identity listed twice is growth, +1, refused",
          ([(g.rule, g.identity, g.extra) for g in refused], allowed), ([("R1", "a", 1)], []))
    refused, _ = growth(base, base + [("R2", "c")], rules, rules)
    check("RED: a new identity under a rule the merge-base defines is refused, and says why",
          len(refused) == 1 and "exists at the merge-base" in why(refused), True)
    refused, allowed = growth(base, base + [("R3", "d")], rules, rules | {"R3"})
    check("a rule born on this branch may list its first offenders, and says why",
          (refused, len(allowed) == 1 and "born on this branch" in why(allowed)), ([], True))
    refused, allowed = growth(base, base + [("R3", "d")], rules, {"R2", "R3"})
    check("RED: a rule the merge-base defines is missing at HEAD, so no growth at all",
          (len(refused), allowed, '"R1"' in why(refused) and "missing at HEAD" in why(refused)),
          (1, [], True))
    refused, _ = growth(base, base + [("R3", "d")], None, rules | {"R3"})
    check("RED: rules at the merge-base that cannot be read allow nothing",
          len(refused) == 1 and "could not be read" in why(refused), True)
    refused, _ = growth(base, base + [("R3", "d")], rules, None)
    check("RED: rules at HEAD that cannot be read allow nothing",
          len(refused) == 1 and "HEAD could not be read" in why(refused), True)

    print("\nonly_shrinks: the list at the merge-base, in a throwaway repository")
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)

        def run_git(*args: str) -> None:
            subprocess.run(["git", *args], cwd=str(repo), check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        run_git("init", "-q")
        run_git("config", "user.email", "selftest@example.invalid")
        run_git("config", "user.name", "selftest")
        (repo / "rules.txt").write_text("R1\n")
        run_git("add", "-A")
        run_git("commit", "-q", "-m", "no list yet")
        run_git("branch", "-q", "before-list")
        document, where, _, files = list_at_merge_base("list.json", repo, "HEAD", ["rules.txt"])
        check("FAIL OPEN, AND SAYS WHY: no list at the merge-base is the list's birth",
              (document, "gives it its birth" in where, files), (None, True, {"rules.txt": "R1\n"}))
        (repo / "list.json").write_text('{"files": {"a.md": {"R1": ["x"]}}}\n')
        run_git("add", "-A")
        run_git("commit", "-q", "-m", "list")
        document, where, base, _ = list_at_merge_base("list.json", repo, "HEAD")
        check("the list as it stood at the merge-base, and a short merge-base id",
              (document, len(where), bool(base)), ({"files": {"a.md": {"R1": ["x"]}}}, 8, True))
        document, where, _, _ = list_at_merge_base("list.json", repo, "no-such-ref")
        check("FAIL OPEN, AND SAYS WHY: no merge-base",
              (document, "no merge-base" in where), (None, True))
        (repo / "list.json").write_text("<<<<<<< ours\n")
        run_git("add", "-A")
        run_git("commit", "-q", "-m", "broken")
        document, where, _, _ = list_at_merge_base("list.json", repo, "HEAD")
        check("FAIL OPEN, AND SAYS WHY: a list at the merge-base that is not JSON",
              (document, "is not JSON" in where), (None, True))

    print("\nonly_shrinks: the command a JavaScript caller runs")
    request = json.dumps({"base": [["R1", "a"]], "head": [["R1", "a"], ["R1", "b"]],
                          "base_rules": ["R1"], "head_rules": ["R1"]})
    done = subprocess.run([sys.executable, str(Path(__file__).resolve()), "growth"],
                          input=request.encode(), stdout=subprocess.PIPE, check=False)
    answer = json.loads(done.stdout.decode() or "{}")
    check("`growth` on stdin answers the same refusal as the function",
          [(g["rule"], g["identity"], g["extra"]) for g in answer.get("refused", [])],
          [("R1", "b", 1)])

    def command(args: List[str], stdin: str = "") -> Tuple[int, str]:
        done = subprocess.run([sys.executable, str(Path(__file__).resolve()), *args],
                              input=stdin.encode(), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, check=False)
        return done.returncode, done.stderr.decode()

    check("`base --path` with no value exits 64", command(["base", "--path"])[0], 64)
    check("an unknown flag exits 64", command(["base", "--path", "x.json", "--nope", "y"])[0], 64)
    check("rules sent as a string are refused (64), never read as a set of letters",
          command(["growth"], json.dumps({"base": [], "head": [["R9", "x"]],
                                          "base_rules": "R1", "head_rules": "R1R9"}))[0], 64)
    check("a request that is not JSON exits 64", command(["growth"], "not json")[0], 64)
    check("a pair of three exits 64",
          command(["growth"], json.dumps({"base": [], "head": [["R1", "x", "y"]],
                                          "base_rules": [], "head_rules": []}))[0], 64)

    print("\nself-test clean" if ok else "\nself-test FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
