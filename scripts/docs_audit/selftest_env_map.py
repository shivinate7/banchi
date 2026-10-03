"""Self-test cases, env map rows. Called by `selftest.self_test`."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import List

from . import core
from .core import (
    ROOT,
    Report,
    SKIP_DIRS,
    _NUMBER_WORDS,
    _STAGED_PATHS,
    _walk,
    child_names,
    exists,
    glob_files,
    leave_staged_mode,
    module_globals,
    read,
    rel,
)
from .env_map import _hook_triples, check_codex_hooks, source_names
from .registry_scopes import _spec_map_should_run
from .rules import (
    HARD_RULE_FLOOR,
    PROSE_ONLY_EXPECTED,
    check_identifier_spelling,
    check_rule_enforcement,
)
from .screens import _ROSTER_RE, _storage_sites, check_storage_keys
from .spelling import check_shell_substitution


def run(ok) -> None:
    report = Report()
    check_identifier_spelling(report)
    check_shell_substitution(report)
    check_rule_enforcement(report)
    by_label = {row.check: row.findings for row in report.checks}
    ok(
        not by_label["identifier spelling"],
        "every identifier in code, and every British word in markdown prose, is spelled American",
        "\n".join(f.where for f in by_label["identifier spelling"][:12]),
    )

    # THE TWO PINS, PROVED BY A CLAUDE.md THAT BREAKS EACH. The real tree is above both, so the
    # row stays green with either check deleted; only a fixture on the wrong side of a pin shows
    # the check fires. The real tree must also agree with the pins, or the row is red today.
    print("\nrule enforcement: the floor and the prose pin each fire on a fixture")
    ok(not by_label["rule enforcement"],
       "the real CLAUDE.md agrees with both pins",
       "\n".join(f.message for f in by_label["rule enforcement"][:4]))
    argued = ("- **Rule {n}.** **NOT MECHANIZED:** a machine cannot see what a person would "
              "have to judge here at all.\n")
    mech = "- **Rule {n}.** Enforced by `make check`.\n"

    def rule_messages(n_argued: int, n_mech: int) -> List[str]:
        here = module_globals()
        saved_root, saved_index = here["ROOT"], here["_INDEX_PATHS"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            body = "".join(argued.format(n=i) for i in range(n_argued))
            body += "".join(mech.format(n=n_argued + i) for i in range(n_mech))
            (root / "CLAUDE.md").write_text("# T\n\n## Hard rules\n\n" + body, encoding="utf-8")
            (root / "Makefile").write_text("check:\n\ttrue\n", encoding="utf-8")
            here["ROOT"], here["_INDEX_PATHS"] = root, None
            try:
                fixture_report = Report()
                check_rule_enforcement(fixture_report)
            finally:
                here["ROOT"], here["_INDEX_PATHS"] = saved_root, saved_index
        return [f.message for f in fixture_report.checks[0].findings]

    pin, floor = PROSE_ONLY_EXPECTED, HARD_RULE_FLOOR
    found = rule_messages(pin, floor - pin)
    ok(not found, "control: exactly the pinned counts raise nothing", str(found))
    found = rule_messages(pin, floor - 1 - pin)
    ok(len(found) == 1 and f"read {floor - 1} hard rules where {floor} are pinned" in found[0],
       "one rule under the floor raises the floor finding and only that", str(found))
    found = rule_messages(pin + 1, floor - pin - 1)
    ok(len(found) == 1 and "argue their own unenforceability" in found[0],
       "one more admission than pinned raises the prose-debt finding", str(found))
    found = rule_messages(pin - 1, floor - pin + 1)
    ok(len(found) == 1 and "only" in found[0] and "argue their own unenforceability" in found[0],
       "one fewer admission than pinned raises it too: the pin reads both ways", str(found))

    print("\nspec map: path-gated in staged mode (test-audit plan S3)")
    here = module_globals()
    saved_index, saved_staged = here["_INDEX_PATHS"], set(_STAGED_PATHS)
    try:
        here["_INDEX_PATHS"] = {"docs/x.md"}
        _STAGED_PATHS.clear()
        _STAGED_PATHS.add("docs/x.md")
        ok(not _spec_map_should_run(),
           "a staged commit touching only docs/ does not run the row")
        _STAGED_PATHS.add("app/src/Orders.tsx")
        ok(_spec_map_should_run(),
           "a staged commit touching app/ runs the row")
        _STAGED_PATHS.discard("app/src/Orders.tsx")
        _STAGED_PATHS.add("scripts/browser-scope.py")
        ok(_spec_map_should_run(),
           "a staged commit touching scripts/browser-scope.py runs the row")
        _STAGED_PATHS.clear()
        ok(_spec_map_should_run(),
           "RED before the fix: an empty staged set fails open and runs the row")
        here["_INDEX_PATHS"] = None
        ok(_spec_map_should_run(), "a full run (no staged mode) always runs the row")
    finally:
        here["_INDEX_PATHS"] = saved_index
        _STAGED_PATHS.clear()
        _STAGED_PATHS.update(saved_staged)

    # ------------------------------------------------------------------ storage keys
    #
    # The reader binds a key to a store BY ITS FILE, which is sound only while no file in
    # `app/src` opens both. That is a property of the tree rather than of the code, so it is
    # asserted here: the day it stops holding, this case fails and the row starts reporting
    # the file instead of guessing at it.
    sites, site_findings = _storage_sites()
    ok(
        not site_findings,
        "no file in app/src touches both stores, so the file is a sound binding",
        str(site_findings),
    )
    # `banchi.session.box` STOOD HERE UNTIL 2026-09-11 and is gone (D141): six of D27's seven
    # session keys moved to the device, and `banchi.session.captureId` is the one left — which
    # is the same shape (declared as a const in `SESSION_KEYS` and read through `readSession`'s
    # parameter) and so still exercises both halves this case is named for. A live key has to
    # be named because the point is that the READER resolves it, not that a string appears.
    ok(
        "banchi.capture.deviceId" in sites["local"]
        and "banchi.session.captureId" in sites["session"],
        "keys resolve to the right store through a const and through a helper's parameter",
        str(sorted(sites["local"]) + sorted(sites["session"])),
    )
    ok(
        _NUMBER_WORDS.get((_ROSTER_RE.search(read(ROOT / "CLAUDE.md")) or [None, "x"])[1].lower())
        == len(sites["local"]),
        "CLAUDE.md's count word parses and equals the number of device-local keys",
        str(sorted(sites["local"])),
    )
    report = Report()
    check_storage_keys(report)
    by_label = {row.check: row.findings for row in report.checks}
    ok(
        not by_label["storage keys"],
        "every storage key the app writes is published where the docs promise it is",
        str(by_label["storage keys"]),
    )

    # ------------------------------------------------------------------ codex hooks (D135)
    #
    # `_hook_triples` is the extractor, pure and file-free, so the mutation this row exists
    # for can be driven on synthetic dicts rather than on the real tree — the same split
    # `_storage_sites` uses above, for the same reason: the logic that could be wrong lives
    # here, not in which two paths the real check reads.
    print("\ncodex hooks reads (event, matcher, command) out of a settings-shaped dict")
    claude_shaped = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Write|Edit", "hooks": [{"type": "command", "command": "scripts/guard-opsec.sh"}]},
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "scripts/reap.py --hook"}]},
            ],
            "Stop": [{"hooks": [{"type": "command", "command": "scripts/typecheck-hook.py"}]}],
        }
    }
    triples = _hook_triples(claude_shaped)
    ok(
        ("PreToolUse", "Write|Edit", "scripts/guard-opsec.sh") in triples
        and ("PreToolUse", "Bash", "scripts/reap.py --hook") in triples,
        "a matcher on the entry is carried into the triple",
        str(sorted(triples)),
    )
    ok(
        ("Stop", "", "scripts/typecheck-hook.py") in triples,
        "an event with no tool to match reads its matcher as the empty string, not skipped",
        str(sorted(triples)),
    )
    ok(not _hook_triples({"hooks": "not a dict"}) and not _hook_triples("not even a dict"),
       "a malformed hooks block reads as no hooks, not a crash")
    ok(not _hook_triples({"hooks": {"Stop": [{"hooks": [{"type": "prompt", "text": "x"}]}]}}),
       "a non-command hook (a prompt, say) contributes nothing to the roster")

    # THE MUTATION: drop one hook from the Codex side, prove the row reports exactly the
    # drop, restore it, prove the row is silent again. This is D135's own worked example —
    # `.codex/hooks.json` really did ship a day behind `WorktreeRemove` and `reap.py --hook`
    # — replayed here as data so it never depends on the two files staying out of sync.
    print("\nremoving one hook from one side is reported, and restoring it clears the report")
    codex_shaped = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Write|Edit", "hooks": [{"type": "command", "command": "scripts/guard-opsec.sh"}]},
            ],
            "Stop": [{"hooks": [{"type": "command", "command": "scripts/typecheck-hook.py"}]}],
        }
    }
    missing = _hook_triples(claude_shaped) - _hook_triples(codex_shaped)
    ok(
        missing == {("PreToolUse", "Bash", "scripts/reap.py --hook")},
        "the row's own diff finds exactly the hook the mutation removed",
        str(missing),
    )
    codex_shaped["hooks"]["PreToolUse"].append(
        {"matcher": "Bash", "hooks": [{"type": "command", "command": "scripts/reap.py --hook"}]}
    )
    ok(
        not (_hook_triples(claude_shaped) - _hook_triples(codex_shaped))
        and not (_hook_triples(codex_shaped) - _hook_triples(claude_shaped)),
        "restoring the hook clears the diff in both directions",
        str(_hook_triples(claude_shaped) ^ _hook_triples(codex_shaped)),
    )
    ok(
        ("PreToolUse", "Bash", "scripts/reap.py --hook") in _hook_triples(claude_shaped)
        and ("PreToolUse", "Write|Edit", "scripts/decision-context.py")
        not in _hook_triples(claude_shaped),
        "the triple is exact — same event and matcher, a different command is not a match",
    )

    # And the real tree: the two files this row actually reads should already agree, because
    # the change that added the row is the same change that brought .codex/hooks.json to
    # parity (D135) — a self-test that could not pass against its own repository would be
    # asserting a rule this tree does not follow.
    report = Report()
    check_codex_hooks(report)
    by_label = {row.check: row.findings for row in report.checks}
    ok(
        not by_label["codex hooks"],
        ".codex/hooks.json and .claude/settings.json name the same hooks in this tree",
        str(by_label["codex hooks"]),
    )

    # CODEX_ONLY: one hook the shared layer owns for Claude Code (silent-write runs on both sides).
    # Driven on temp files through the row's own two path globals.
    print("\ncodex hooks: the CODEX_ONLY hook is allowed in Codex only, in both directions")
    import json
    from . import env_map

    def hook(matcher: str, command: str) -> dict:
        return {"matcher": matcher, "hooks": [{"type": "command", "command": command}]}

    shared = hook("Write|Edit", "scripts/guard-opsec.sh")
    reap = hook("Bash", "scripts/reap.py --hook")
    silent = hook("Bash", "scripts/silent-write-guard.py --hook")
    extra = hook("Bash", "scripts/janitor.py --hook")

    def codex_hooks_findings(claude: list, codex: list) -> list:
        with tempfile.TemporaryDirectory() as tmp:
            c, x = Path(tmp) / "settings.json", Path(tmp) / "hooks.json"
            c.write_text(json.dumps({"hooks": {"PreToolUse": claude}}), encoding="utf-8")
            x.write_text(json.dumps({"hooks": {"PreToolUse": codex}}), encoding="utf-8")
            saved = env_map.CLAUDE_SETTINGS, env_map.CODEX_HOOKS
            env_map.CLAUDE_SETTINGS, env_map.CODEX_HOOKS = c, x
            try:
                rep = Report()
                check_codex_hooks(rep)
            finally:
                env_map.CLAUDE_SETTINGS, env_map.CODEX_HOOKS = saved
        return [f for row in rep.checks for f in row.findings]

    found = codex_hooks_findings([shared, silent], [shared, silent, reap])
    ok(not found, "green: Claude lacks the CODEX_ONLY hook and Codex runs it", str(found))
    found = codex_hooks_findings([shared, silent, reap], [shared, silent, reap])
    ok(len(found) == 1 and "CODEX_ONLY is stale" in str(found[0]),
       "red: Claude runs a CODEX_ONLY hook again", str(found))
    found = codex_hooks_findings([shared, silent], [shared, silent])
    ok(len(found) == 1 and "lost" in str(found[0]),
       "red: Codex loses a CODEX_ONLY hook", str(found))
    found = codex_hooks_findings([shared, silent], [shared, silent, reap, extra])
    ok(len(found) == 1 and "does not run" in str(found[0]),
       "red: an unlisted Codex-only hook appears", str(found))

    # GUARD_SHELL_SKIP pin: Claude's Bash entry skips three clauses, every other guard-shell entry is empty.
    gs = "scripts/guard-shell.py --hook"
    sk = "GUARD_SHELL_SKIP=checkout,stash,reset "
    c_bash, c_edit = hook("Bash", sk + gs), hook("Write|Edit", "GUARD_SHELL_SKIP= " + gs)
    x_bash, x_edit = hook("Bash", "GUARD_SHELL_SKIP= " + gs), hook("Write|Edit", "GUARD_SHELL_SKIP= " + gs)
    found = codex_hooks_findings([c_bash, c_edit], [x_bash, x_edit, reap])
    ok(not found, "green: each guard-shell entry carries its pinned skip value", str(found))
    found = codex_hooks_findings([hook("Bash", "GUARD_SHELL_SKIP=checkout " + gs), c_edit], [x_bash, x_edit, reap])
    ok(len(found) == 1 and "GUARD_SHELL_SKIP=checkout,stash,reset" in str(found[0]),
       "red: Claude's Bash entry carries a different skip value", str(found))
    found = codex_hooks_findings([c_bash, c_edit], [hook("Bash", gs), x_edit, reap])
    ok(len(found) == 1 and "must set `GUARD_SHELL_SKIP=`" in str(found[0]),
       "red: a Codex entry misses the empty prefix", str(found))
    found = codex_hooks_findings([c_bash, hook("Write|Edit", sk + gs)], [x_bash, x_edit, reap])
    ok(len(found) == 1 and "must set `GUARD_SHELL_SKIP=`" in str(found[0]),
       "red: Claude's Write|Edit entry carries a skip value", str(found))

    # The staged-mode primitives, which have no loud failure mode: every one of them
    # answers plausibly against the worktree while auditing a tree the commit will not
    # produce. Driven through the module globals because that is how audit() drives them.
    print("\nstaged mode answers about the index, not the worktree")
    # A WORKTREE IS ANOTHER BRANCH'S SOURCE INSIDE THIS TREE, and walking it checks one branch's
    # prose against another branch's code. Observed on 2026-08-29: a concurrent session's worktree
    # documented `make worktree-setup`, a target real on ITS branch, and the `make targets` check
    # failed a commit on THIS one. Two branches are allowed to disagree.
    #
    # THE STAGED PATH IS COVERED HERE AND THE ON-DISK PATH IS COVERED BY `nested_worktrees`, which
    # asks git rather than guessing a name. Only the first is reachable from a self-test: the
    # second needs a real repository with a real worktree in it, and was verified by hand — a
    # worktree named `zz-scratch-wt`, which no name rule could guess, walked zero files. That gap
    # is named rather than papered over.
    print("\na worktree inside the tree is another branch, and is not walked")
    core._INDEX_PATHS = {
        "docs/GATES.md",
        ".claude/worktrees/other-branch/CLAUDE.md",
        ".claude/worktrees/other-branch/docs/GATES.md",
    }
    walked = [rel(p) for p in _walk(ROOT, (".md",))]
    ok(
        walked == ["docs/GATES.md"],
        "a worktree's markdown is not discovered, however tracked-looking the path",
        str(walked),
    )
    ok("worktrees" in SKIP_DIRS, "the convention is pruned by name as well as by git")
    try:
        core._INDEX_PATHS = {"docs/GATES.md", "docs/specs/batch-script.md", "harness/run.py"}
        ok(exists(ROOT / "docs" / "GATES.md"), "a tracked file exists")
        ok(not exists(ROOT / "Makefile"), "an untracked file does not, however real on disk")
        ok(exists(ROOT / "docs"), "a directory exists through the files under it")
        ok(not exists(ROOT / "scripts"), "a directory with nothing tracked under it does not")
        ok(
            child_names(ROOT / "docs") == {"GATES.md", "specs"},
            "children come from the index, one level deep",
            str(child_names(ROOT / "docs")),
        )
        ok(
            [rel(p) for p in _walk(ROOT, (".md",))] == ["docs/GATES.md", "docs/specs/batch-script.md"],
            "discovery enumerates the index",
            str([rel(p) for p in _walk(ROOT, (".md",))]),
        )
        ok(
            [rel(p) for p in glob_files(ROOT / "docs", "*.md")] == ["docs/GATES.md"],
            "glob matches within one directory of the index",
            str([rel(p) for p in glob_files(ROOT / "docs", "*.md")]),
        )
        # The orphan scan's deep mode, through the index. It is the only check in this file
        # that walks a directory tree, so it is the only one that could quietly go back to
        # asking the worktree — and in the hook the worktree is the tree that will not be
        # committed.
        ok(
            source_names(ROOT / "docs", (".md",), True) == {"GATES.md", "specs/batch-script.md"},
            "a deep scan enumerates the index, nested paths and all",
            str(sorted(source_names(ROOT / "docs", (".md",), True))),
        )
    finally:
        leave_staged_mode()
    ok(core._INDEX_PATHS is None and exists(ROOT / "Makefile"), "and the worktree comes back")

    # Argparse's own exit for a bad flag is 2 — this script's advisory code, which the
    # pre-commit hook prints and allows. A caller that grew a stale flag would switch the
    # gate off and look routine doing it.
    print("\ninvoking this script wrongly is not mistaken for an advisory")
