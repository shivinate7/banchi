#!/usr/bin/env python3
"""DELETE THE STALE ENTRIES FROM THE TWO SHRINKING OFFENDER LISTS, AND RE-KEY A RENAMED FILE.

    scripts/offenders-prune.py            what it would delete and re-key. Writes nothing.
    scripts/offenders-prune.py --write    apply it.
    scripts/offenders-prune.py --selftest its own cases, in memory and in a throwaway repo.

THE TWO LISTS (D-ratchets-become-offender-lists): `scripts/ste-offenders.json`, which
`make docs-audit`'s `ste offenders` row reads, and `scripts/typed-interpunct-allow.json`,
which its `typed interpunct` row reads. Each row fails on a STALE entry, one that matches
nothing now because the fix landed. The prose list holds more than 14,000 lines, and a stale
entry there is a hash, so a hand delete is slow and a merge conflict is worse. This does the
delete.

THIS IS A GENERATOR AND IT GATES NOTHING (D18: "A generator may write. Nothing that writes
may gate a commit."). It is on no hook and in no `make check`. A person runs it, or an agent
whose commit a row has just refused for a stale entry. The rows keep their job: they read,
they refuse, they never write. It writes a data file under `scripts/`, the standing
`scripts/line-anchors-pin.py` already has, so it opens no seam in D18's list, which governs
the prose files agents read as argument.

IT ONLY EVER DELETES, AND RE-KEYS. It never adds an entry. An offender the list does not name
stays unlisted, and the row stays red on it: the fix for new prose or a new dot is to rewrite
it, never to list it. Two edits are all it makes.

  1. A STALE ENTRY IS DELETED, one occurrence for each occurrence the tree no longer has. The
     comparison is the row's own `_offender_diff`, keyed by the row's own identity
     (`ste_measure.entry_key` for prose, the string itself for a dot), imported and never
     reimplemented. A second copy would drift, and a pruner that disagreed with the gate
     would delete what the gate still needed.
  2. A FILE GIT SAYS WAS RENAMED IS RE-KEYED. When a listed file key names no file today, and
     git's rename detection (`git diff -M`, from the merge-base with origin/main to the
     working tree) names exactly one new path for it, the entries move to the new key. The
     count of each identity does not change, so the move is never growth. A rename onto a
     key the list already holds is refused and named: joining two files' entries is a
     person's call.

A write is refused, and nothing is written, when the planned list holds any identity more
often than the list it read. That guard is the "never adds" rule, checked on the output.

STDLIB ONLY, like every script the rows import.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent

Entries = Dict[str, Dict[str, List[str]]]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _audit():
    """The audit's own module: its readers, its list shape and its comparison."""
    return _load("_docs_audit_for_offenders_prune", ROOT / "scripts" / "docs-audit.py")


def _dump(document: object) -> str:
    """The lists' own serialisation, byte for byte: two-space indent, UTF-8 kept."""
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def _census(files: Entries, key: Callable[[str], str]) -> "Counter[Tuple[str, str]]":
    return Counter((rule, key(e)) for per in files.values() for rule, es in per.items() for e in es)


# --------------------------------------------------------------------------------- the plan


class Plan:
    """What one list would become, and why."""

    def __init__(self, document: object):
        self.document = document
        self.rekeyed: List[Tuple[str, str]] = []
        self.refused: List[str] = []
        self.deleted: List[Tuple[str, str, str]] = []
        self.unlisted = 0
        self.errors: List[str] = []

    @property
    def changed(self) -> bool:
        return bool(self.rekeyed or self.deleted)


def plan(
    document: object,
    found: Entries,
    present: Callable[[str], bool],
    renames: Sequence[Tuple[str, str]],
    list_key: Callable[[str], str],
    key: Callable[[str], str],
    rules: Optional[Set[str]],
    shape: Callable,
    diff: Callable,
) -> Plan:
    """The pruned list for `document`, computed in memory. Never touches disk.

    `found` is the tree's offenders (file key -> rule -> entries), `present(k)` says whether
    any file today has list key `k`, `renames` is git's (old path, new path) pairs, and
    `list_key` turns a path into a list key. `shape` and `diff` are the row's own
    `_offender_list_shape` and `_offender_diff`."""
    listed, _lanes, errors = shape(document, rules)
    result = Plan(copy.deepcopy(document))
    if errors:
        result.errors = list(errors)
        return result
    block: Dict[str, Dict[str, object]] = result.document["files"]  # type: ignore[index]

    # 1. RE-KEY. Only a key that names no file today, and only onto one target.
    targets: Dict[str, Set[str]] = {}
    for old, new in renames:
        targets.setdefault(list_key(old), set()).add(list_key(new))
    taken = set(block)
    moves: Dict[str, str] = {}
    for file_key in list(block):
        if present(file_key):
            continue
        choices = targets.get(file_key, set()) - {file_key}
        if len(choices) != 1:
            if len(choices) > 1:
                result.refused.append(f"{file_key}: git names {len(choices)} new paths "
                                      f"({', '.join(sorted(choices))}), so it is not re-keyed")
            continue
        (target,) = choices
        if target in taken:
            result.refused.append(f"{file_key} -> {target}: the list already holds {target}. "
                                  "Joining two files' entries is a person's call")
            continue
        moves[file_key] = target
        taken.add(target)
    if moves:
        # In place, so the list's own order holds and the diff is one line per move.
        result.document["files"] = {moves.get(k, k): v for k, v in block.items()}  # type: ignore[index]
        block = result.document["files"]  # type: ignore[index]
        result.rekeyed = sorted(moves.items())

    # 2. DELETE STALE ENTRIES, by the row's own comparison.
    listed, _lanes, _ = shape(result.document, rules)
    unlisted, stale = diff(found, listed, key=key)
    result.unlisted = len(unlisted)
    for file_key, rule, entry in stale:
        entries = block[file_key][rule]  # type: ignore[index]
        entries.remove(entry)  # one occurrence, the one the comparison named
        result.deleted.append((file_key, rule, entry))
        if not entries:
            del block[file_key][rule]  # type: ignore[attr-defined]
            if not [r for r in block[file_key] if r != "lane"]:
                del block[file_key]

    # 3. THE "NEVER ADDS" RULE, CHECKED ON THE OUTPUT.
    extra = grown(document, result.document, shape, rules, key)
    if extra:
        result.errors.append(f"the plan would hold {len(extra)} identit"
                             f"{'y' if len(extra) == 1 else 'ies'} more often than the list "
                             f"it read ({extra[:3]}). Nothing is written.")
    return result


def grown(before: object, after: object, shape: Callable, rules: Optional[Set[str]],
          key: Callable[[str], str]) -> List[Tuple[str, str]]:
    """Every (rule, identity) that `after` holds more often than `before`, across all files.
    Empty for any plan this module makes. `main` writes nothing when it is not."""
    was = _census(shape(before, rules)[0], key)
    now = _census(shape(after, rules)[0], key)
    return sorted(k for k, n in now.items() if n > was.get(k, 0))


# ------------------------------------------------------------------------- reading the tree


def git_renames(root: Path, reference: str = "origin/main") -> List[Tuple[str, str]]:
    """git's rename pairs from the merge-base with `reference` to the working tree.

    From the merge-base, not from HEAD, so a rename in any commit on this branch is seen.
    Falls back to HEAD with no merge-base. A rename git cannot see (a plain `mv` never
    staged) is not re-keyed. Its entries go stale and are deleted, and the new file's
    offenders are unlisted, which is the row's own answer."""

    def run(*args: str) -> Optional[str]:
        try:
            done = subprocess.run(["git", *args], cwd=str(root), stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, check=False)
        except OSError:
            return None
        return done.stdout.decode("utf-8", errors="replace") if done.returncode == 0 else None

    base = (run("merge-base", "HEAD", reference) or "").strip() or "HEAD"
    out = run("diff", "-M", "--name-status", "-z", base)
    if not out:
        return []
    parts = out.split("\0")
    pairs: List[Tuple[str, str]] = []
    i = 0
    while i < len(parts) and parts[i]:
        status = parts[i]
        if status.startswith(("R", "C")):
            if status.startswith("R"):
                pairs.append((parts[i + 1], parts[i + 2]))
            i += 3
        else:
            i += 2
    return pairs


def ste_inputs(audit):
    """(document path, found, present, list_key, key, rules) for the prose list."""
    ste_measure = audit._sibling("ste_measure.py")
    if ste_measure is None:
        raise SystemExit("scripts/ste_measure.py could not be loaded, so nothing was measured")
    docs = audit.markdown_files()
    paths = [(audit.rel(p), audit.read(p)) for p in docs]
    found = ste_measure.measure(paths).offenders
    keys_now = {ste_measure.list_key(rel) for rel, _ in paths}
    rules = set(ste_measure.error_codes(ste_measure.load_ste_lint()))
    return (audit.STE_OFFENDERS_JSON, found, keys_now.__contains__, ste_measure.list_key,
            ste_measure.entry_key, rules)


def interpunct_inputs(audit):
    """The same six for the typed-dot list, or None when node cannot run the extractor."""
    strings = audit._run_user_strings(list(audit.TYPED_INTERPUNCT_EXTRACT_ARGS))
    if strings is None:
        return None
    found = audit._typed_interpunct_found(strings)
    return (audit.TYPED_INTERPUNCT_ALLOW, found, lambda k: (ROOT / k).is_file(),
            lambda path: path, lambda entry: entry, {audit.TYPED_INTERPUNCT_RULE})


# ------------------------------------------------------------------------------------ main


def _report(name: str, result: Plan) -> None:
    if result.errors:
        print(f"{name}: not pruned.")
        for error in result.errors:
            print(f"  {error}")
        return
    print(f"{name}: {len(result.deleted)} stale entr{'y' if len(result.deleted) == 1 else 'ies'}"
          f" to delete, {len(result.rekeyed)} file{'' if len(result.rekeyed) == 1 else 's'} to "
          f"re-key, {result.unlisted} unlisted offender"
          f"{'' if result.unlisted == 1 else 's'} (never added here).")
    for old, new in result.rekeyed:
        print(f"  re-key  {old} -> {new}")
    for line in result.refused:
        print(f"  refused {line}")
    for file_key, rule, entry in result.deleted[:30]:
        print(f"  delete  {file_key}  {rule}  {entry}")
    if len(result.deleted) > 30:
        print(f"  ... and {len(result.deleted) - 30} more")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="apply the deletes and re-keys")
    parser.add_argument("--selftest", action="store_true", help="prove it, in memory")
    args = parser.parse_args()
    if args.selftest:
        return selftest()

    audit = _audit()
    renames = git_renames(ROOT)
    inputs = [("ste offenders", ste_inputs(audit))]
    dots = interpunct_inputs(audit)
    if dots is None:
        print("typed interpunct: not read. `node` or app/node_modules/typescript is missing, "
              "so its list is left alone. Run `npm --prefix app ci` first.")
    else:
        inputs.append(("typed interpunct", dots))

    status = 0
    for name, (path, found, present, list_key, key, rules) in inputs:
        document = json.loads(path.read_text(encoding="utf-8"))
        result = plan(document, found, present, renames, list_key, key, rules,
                      audit._offender_list_shape, audit._offender_diff)
        _report(f"{name} ({audit.rel(path)})", result)
        if result.errors:
            status = 1
            continue
        if args.write and result.changed:
            path.write_text(_dump(result.document), encoding="utf-8")
            print("  written.")
    if not args.write:
        print("\nPreview. `scripts/offenders-prune.py --write` applies it. "
              "`make docs-audit` is what says the lists are right. This never gates (D18).")
    return status


# -------------------------------------------------------------------------------- selftest


def selftest() -> int:
    """The plan in memory, the rename reader in a throwaway repo. Writes nothing in this
    checkout."""
    import tempfile

    audit = _audit()
    shape, diff = audit._offender_list_shape, audit._offender_diff
    ok = True

    def check(label: str, got, want) -> None:
        nonlocal ok
        if got == want:
            print(f"  ok   {label}")
        else:
            ok = False
            print(f"  FAIL {label}\n       got  {got!r}\n       want {want!r}")

    def entry_key(entry: str) -> str:
        return entry.split(" ", 1)[0]

    rules = {"STE006"}
    doc = {"_about": "x", "rules": ["STE006"], "files": {
        "docs/a.md": {"lane": "docs-sweep", "STE006": ["aaaa One; two.", "bbbb Three; four.",
                                                        "bbbb Three; four."]},
        "docs/old.md": {"lane": "docs-sweep", "STE006": ["cccc Five; six."]},
        "docs/gone.md": {"lane": "docs-sweep", "STE006": ["dddd Seven; eight."]},
    }}

    def run(found, present, renames=(), document=doc):
        return plan(document, found, present, list(renames), lambda p: p, entry_key, rules,
                    shape, diff)

    print("offenders-prune: stale entries go, nothing is added")
    everything = {"docs/a.md": {"STE006": ["aaaa One; two.", "bbbb Three; four.",
                                           "bbbb Three; four."]},
                  "docs/old.md": {"STE006": ["cccc Five; six."]},
                  "docs/gone.md": {"STE006": ["dddd Seven; eight."]}}
    same = run(everything, lambda k: True)
    check("a list that matches the tree is left exactly as it was",
          (same.changed, same.document), (False, doc))

    one_fixed = copy.deepcopy(everything)
    one_fixed["docs/a.md"]["STE006"] = ["aaaa One; two.", "bbbb Three; four."]
    result = run(one_fixed, lambda k: True)
    check("one of two copies fixed: ONE occurrence is deleted, the other stays listed",
          result.document["files"]["docs/a.md"]["STE006"], ["aaaa One; two.", "bbbb Three; four."])

    with_new = copy.deepcopy(everything)
    with_new["docs/a.md"]["STE006"].append("eeee A new one; unlisted.")
    with_new["docs/new.md"] = {"STE006": ["ffff Brand new; file."]}
    result = run(with_new, lambda k: True)
    check("an unlisted offender is NEVER added, in a listed file or a new one",
          (result.changed, result.unlisted, result.document), (False, 2, doc))

    relabeled = copy.deepcopy(everything)
    relabeled["docs/old.md"]["STE006"] = ["cccc a label a claim rewrote"]
    check("only the key is compared: a label that changed is not stale",
          run(relabeled, lambda k: True).deleted, [])

    no_gone = {k: v for k, v in everything.items() if k != "docs/gone.md"}
    result = run(no_gone, lambda k: k != "docs/gone.md")
    check("a deleted file's entries all go, and its key with them",
          ("docs/gone.md" in result.document["files"], len(result.deleted)), (False, 1))

    print("\noffenders-prune: a renamed file is re-keyed, by git's rename pairs")
    moved = {k: v for k, v in everything.items() if k != "docs/old.md"}
    moved["docs/new-name.md"] = everything["docs/old.md"]
    result = run(moved, lambda k: k != "docs/old.md", renames=[("docs/old.md", "docs/new-name.md")])
    check("the entries move to the new key, in place, and none is deleted",
          (list(result.document["files"]), result.deleted, result.rekeyed),
          (["docs/a.md", "docs/new-name.md", "docs/gone.md"], [],
           [("docs/old.md", "docs/new-name.md")]))
    result = run(moved, lambda k: k != "docs/old.md")
    check("with no rename from git, the old key's entries go stale and are deleted",
          ("docs/old.md" in result.document["files"], "docs/new-name.md" in result.document["files"]),
          (False, False))
    result = run(everything, lambda k: True, renames=[("docs/old.md", "docs/new-name.md")])
    check("a key whose file still exists is never re-keyed", result.rekeyed, [])
    onto_listed = run(moved, lambda k: k != "docs/old.md", renames=[("docs/old.md", "docs/a.md")])
    check("a rename onto a key the list already holds is refused and named",
          (onto_listed.rekeyed, len(onto_listed.refused)), ([], 1))

    print("\noffenders-prune: the output guard")
    broken = copy.deepcopy(doc)
    broken["files"]["docs/a.md"]["STE099"] = ["zzzz Bad rule."]
    check("a list the row's own shape refuses is not pruned at all",
          bool(run(everything, lambda k: True, document=broken).errors), True)

    added = copy.deepcopy(doc)
    added["files"]["docs/a.md"]["STE006"].append("gggg Grown.")
    check("RED: the output guard names an identity the output holds more often than the "
          "input", grown(doc, added, shape, rules, entry_key), [("STE006", "gggg")])
    copied_across = copy.deepcopy(doc)
    copied_across["files"]["docs/old.md"]["STE006"].append("aaaa One; two.")
    check("RED: a copy into a second file is growth too — the guard counts across files",
          grown(doc, copied_across, shape, rules, entry_key), [("STE006", "aaaa")])
    renamed = copy.deepcopy(doc)
    renamed["files"] = {("docs/new.md" if k == "docs/old.md" else k): v
                        for k, v in renamed["files"].items()}
    check("a re-key is not growth: the same identities, under another file key",
          grown(doc, renamed, shape, rules, entry_key), [])
    check("the serialisation is the lists' own: two-space indent, UTF-8 kept",
          _dump({"a": ["…"]}), '{\n  "a": [\n    "…"\n  ]\n}\n')

    print("\noffenders-prune: git's rename detection, in a throwaway repository")
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)

        def git(*args: str) -> None:
            subprocess.run(["git", *args], cwd=str(repo), check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        git("init", "-q")
        git("config", "user.email", "selftest@example.invalid")
        git("config", "user.name", "selftest")
        (repo / "docs").mkdir()
        body = "".join(f"Line {i} of a document that is long enough to be a rename.\n"
                       for i in range(30))
        (repo / "docs" / "old.md").write_text(body)
        (repo / "docs" / "kept.md").write_text("Kept.\n")
        git("add", "-A")
        git("commit", "-q", "-m", "base")
        git("mv", "docs/old.md", "docs/new-name.md")
        check("a staged `git mv` is one rename pair, from HEAD with no origin/main",
              git_renames(repo), [("docs/old.md", "docs/new-name.md")])
        git("commit", "-q", "-m", "move")
        git("branch", "-q", "base-ref", "HEAD~1")
        check("a rename committed on the branch is seen from the merge-base",
              git_renames(repo, reference="base-ref"), [("docs/old.md", "docs/new-name.md")])

    print("\nself-test clean" if ok else "\nself-test FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
