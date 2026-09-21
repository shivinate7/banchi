#!/usr/bin/env python3
"""`make explain` — what `make check` runs, and what each row of it is worth.

THE COMPOSITION OF `make check` WAS ARGUED AT LENGTH AND PUBLISHED NOWHERE READABLE. Eleven
targets, each with a paragraph in the Makefile saying why it is or is not on the commit path,
what toolchain it needs, and whether it writes — roughly 120 lines of comment spread through a
522-line file, none of it reachable without opening that file. `make help` carried the summary,
and the summary was WRONG: it said `harness + docs-audit + the self-tests + lint + typecheck`
while five more targets ran, and had said so since those five landed. CLAUDE.md caught up; the
front door never did, and nothing compared them.

So the composition becomes data with a reader. Three rows in `scripts/docs-audit.py` consume
this file — `check registry` reconciles it against the Makefile recipe, `check census`
reconciles the published prose against it, and `commit path writes` asserts D18 mechanically
for the first time by refusing any writing check on the commit path.

**THIS FILE DOES NOT DRIVE `make check` AND MUST NOT.** The Makefile recipe is what runs; this
is a parallel declaration reconciled against it. The distinction is the whole point of the
shape: a wrong entry here is an explainer that lies, which the audit catches, whereas a
registry that DROVE the suite could silently stop running a check — and a check that silently
stops running is the failure this repo has paid for more than any other.

`CHECKS` is a tuple of pure literals for the reason `docs/map.py` and `scripts/status.py`'s
`SOURCES` are: the audit parses it with `ast.literal_eval` rather than importing it, because a
read-only check must not execute the code it is checking.

Stdlib only, no venv, no network — `python3` and not `$(PYTHON)` in the Makefile, same as
`status` and `docs-audit`. A step-away tool that needs `make venv` first is not a step-away
tool.

    scripts/checks.py            the table
    scripts/checks.py <target>   one entry, in full
"""

from __future__ import annotations

import sys
from typing import List, Sequence

WIDTH = 78


# The `needs` vocabulary, declared rather than spelled freehand per entry. A token nobody
# defined is a token nobody can reason about, and the `check registry` row refuses one — so
# this dict is a reader for itself as well as the renderer's legend.
NEEDS = {
    "python3": "a bare system python3. No venv, no packages.",
    "venv": "`make venv` — the harness needs the anthropic SDK, Pillow and numpy.",
    "node": "node on PATH.",
    "app deps": "`npm --prefix app install` — gitignored, so it does not travel to a worktree.",
    "git": "git, and a repository.",
    "bash": "bash, not merely a POSIX sh.",
    "lsof": "lsof, which macOS ships. It is how a pid's working directory and a port's "
            "holders are read; absent, reap-selftest's port cases cannot be posed at all.",
    "sh": "any POSIX sh.",
    "vale": "the vale binary — `brew install vale`. Absent, the target reports and exits 0.",
    "ruff": "ruff, installed by `make venv` from requirements.txt (D82). RUFF_GUARD fails "
            "loudly rather than letting the target no-op.",
}


# One entry per target in the Makefile's `check:` recipe, in recipe order.
#
# `writes` IS A SENTENCE AND NOT A FLAG, and that is deliberate: "it writes" is the start of
# the question D18 asks, never the end of it. An empty string means it writes nothing anywhere.
# `commit path writes` in the audit reads it as truthy/falsy and reports the sentence, so the
# reason travels with the finding.
#
# `why_off_commit_path` is empty exactly where `commit_path` is true. The audit checks that
# pairing, because an entry claiming both would be describing nothing.
CHECKS = (
    {
        "target": "harness",
        "runs": "$(PYTHON) harness/run.py",
        "asserts": "Every verification test in harness/run.py's TESTS list. RECOUNT FROM THERE "
                   "— this entry deliberately carries no number, because a count published "
                   "beside a list is the drift this whole file exists about.",
        "needs": ("venv",),
        "writes": "harness/results/t1*.json, but only when the measurement itself changed — a "
                  "timestamp bump alone is not a change and is not written.",
        "commit_path": False,
        "why_off_commit_path": "It writes, and it needs the venv. D18 keeps a writing thing off "
                               "the path that decides whether a commit proceeds; the Stop hook "
                               "runs it at turn end instead.",
        "gates": True,
        "governed_by": ("D18",),
    },
    {
        "target": "docs-audit",
        "runs": "python3 scripts/docs-audit.py",
        "asserts": "Every reference in the markdown resolves against the code it names. Exit 1 "
                   "is provably wrong and blocks; exit 2 is the coupling question, printed and "
                   "allowed (D16).",
        "needs": ("python3",),
        "writes": "",
        "commit_path": True,
        "why_off_commit_path": "",
        "gates": True,
        "governed_by": ("D16", "D18"),
    },
    {
        "target": "claim-stale",
        "runs": "python3 scripts/claim-ids.py --stale",
        "asserts": "No id this branch ADDS since its merge base with `origin/main` — decision "
                   "heading, code-card `C` entry, or build-order step — has been taken on "
                   "that ref in the meantime. The claimer is a no-op once a branch has "
                   "claimed: there is no slug left, so it says `nothing to do` while the "
                   "number it allocated may have been taken by main since. That happened "
                   "TWICE on 2026-09-11 — #262 and #265 on one id, #265 and #270 on the next "
                   "— and a person reading PR titles was the only thing that caught either. "
                   "It REPORTS and never repairs, because an un-claim has to happen before a "
                   "merge and never after. It can only ever under-report against a stale "
                   "`origin/main`, never over-report, and a clone with no `origin/main` at "
                   "all is allowed and says so.",
        "needs": ("python3", "git"),
        "writes": "",
        "commit_path": False,
        "why_off_commit_path": "It asks about `origin/main`, which a commit never consults "
                               "and a fresh clone may not have — `revert-guard`'s reason, "
                               "and the same answer. `make merge` is where it is worth the "
                               "most, because the fetch immediately above it makes the answer "
                               "current; `make check` is the earlier, cheaper warning.",
        "gates": True,
        "governed_by": ("D16", "D42", "D80", "D140"),
    },
    {
        "target": "revert-guard",
        "runs": "python3 scripts/revert-audit.py branch",
        "asserts": "What this branch would land on origin/main — the clean merge's tree, or "
                   "the branch's diff off the merge-base when the merge conflicts — puts no "
                   "file back the way main had it before a commit in main's last 60, unless a "
                   "commit on the branch names that file. A partial reversal beside real edits "
                   "is a note. On main itself, and in a clone with no origin/main, it allows "
                   "and says so.",
        "needs": ("python3", "git"),
        "writes": "",
        "commit_path": False,
        "why_off_commit_path": "It is on the PUSH path, not the commit path: "
                               "scripts/githooks/pre-push runs it on every branch push. The "
                               "question it asks is about origin/main, which a commit never "
                               "consults and a fresh clone may not have, and a commit on a "
                               "branch is not yet a claim about main — the push is.",
        "gates": True,
        "governed_by": ("D42", "D133"),
    },
    {
        "target": "port-agreement",
        "runs": "python3 scripts/port-agreement.py",
        "asserts": "server/ports.py and app/devPort.ts answer the same port for the same "
                   "checkout path. Two languages hold one algorithm and neither can import the "
                   "other; a disagreement is silent and total.",
        "needs": ("python3", "node"),
        "writes": "a temporary directory it makes and removes.",
        "commit_path": False,
        "why_off_commit_path": "It runs node, and the pre-commit hook runs a bare python3 with "
                               "nothing installed — a check needing a toolchain would fail on a "
                               "machine that has none rather than on a defect.",
        "gates": True,
        "governed_by": ("D18", "D43"),
    },
    {
        "target": "set-hint-agreement",
        "runs": "python3 scripts/set-hint-agreement.py",
        "asserts": "The capture screen and the export fetch resolve a set hint alike. The same "
                   "shape as port-agreement one decision over, and worse when it drifts: a "
                   "verdict shown at the rig gets trusted.",
        "needs": ("python3", "node"),
        "writes": "",
        "commit_path": False,
        "why_off_commit_path": "node again, so it is off the commit path for port-agreement's "
                               "reason: the git hook runs a bare python3.",
        "gates": True,
        "governed_by": ("D18", "D65", "D76"),
    },
    {
        "target": "readiness-agreement",
        "runs": "python3 scripts/readiness-agreement.py",
        "asserts": "`app/src/readiness.ts` against `pipeline/decisions.py:blocking`, which it "
                   "re-implements on purpose (D54 — the screen settles on the keystroke, so a "
                   "server-computed answer would lag it). An AST walk of the Python against "
                   "this file's own flat literals: the two refusal reasons, FLOOR_CHOICE, "
                   "FLAT_KEY, and every `decisions.py:<line>` citation in the header. A third "
                   "refusal reason in Python with no third here is a refusal the screen cannot "
                   "show, and until 2026-09-17 only a person reading both files would find it. "
                   "The file was SHAPED to be audited in 2026-09-02 and nothing read it until "
                   "now; its header claimed this target existed for five days before it did.",
        "needs": ("python3",),
        "writes": "",
        "commit_path": False,
        "why_off_commit_path": "Not the toolchain — this one needs a bare python3 and would "
                               "run in the hook. The commit path is two checks by choice, and "
                               "widening it is its own decision rather than a thing a new "
                               "reader does on the way in.",
        "gates": True,
        "governed_by": ("D18", "D54", "D149"),
    },
    {
        "target": "screen-freshness",
        "runs": "node scripts/screen-freshness.mjs",
        "asserts": "Every server write in app/src has a way back — a re-read, an invalidation "
                   "signal, or a reason in the code why none is owed. It finds NOTHING today: "
                   "it guards write number 39, not a bug that exists.",
        "needs": ("node", "app deps"),
        "writes": "",
        "commit_path": False,
        "why_off_commit_path": "port-agreement's reason exactly — it runs node, and the git "
                               "hook runs bare.",
        "gates": True,
        "governed_by": ("D18",),
    },
    {
        "target": "screen-freshness-selftest",
        "runs": "node scripts/screen-freshness.mjs --self-test",
        "asserts": "The freshness guard's own classifier, against pinned cases in both "
                   "directions: a write with a re-read after it, the same write with nothing "
                   "after it, a write behind a module-level wrapper with evidence at the "
                   "caller, the same wrapper with no caller that re-reads — plus the one blind "
                   "spot it CANNOT catch, pinned so it cannot change silently.",
        "needs": ("node", "app deps"),
        "writes": "",
        "commit_path": False,
        "why_off_commit_path": "screen-freshness' reason exactly — it runs node, and the git "
                               "hook runs bare.",
        "gates": True,
        "why": "IT WAS ON NO TARGET AT ALL UNTIL 2026-09-12, and it was RED on main while the "
               "plain `screen-freshness` beside it passed and printed \"run --self-test\". So "
               "the check told the operator to run the check that was red, and nothing made "
               "them. That is the whole shape of a rule with no reader, and it is why this "
               "one is gated now rather than argued about: PR #307 filled the 17 exports its "
               "RECORDED table was missing, so the gate is safe and costs one node process.",
        "governed_by": ("D18", "D173"),
    },
    {
        "target": "sigil-check",
        "runs": "python3 scripts/sigil-check.py --self-test && python3 scripts/sigil-check.py",
        "asserts": "A bare `#` on an owner-side screen draws D58's COUNT and never the store "
                   "key. Three renderers spelled both with one sigil — the sticky section "
                   "header in count space, the neighbour row and the departed key from the "
                   "index — and on box 3 those spaces are 76 apart, so `#27` named two "
                   "different cards on one screen. Text-matched and therefore narrow: it "
                   "refuses a `#` composed from an expression naming `index`, and a renamed "
                   "local walks past it (docs/DEBTS.md).",
        "needs": ("python3",),
        "writes": "",
        "commit_path": True,
        "why_off_commit_path": "",
        "gates": True,
        "governed_by": ("D58", "D68", "D92"),
    },
    {
        "target": "css-var-check",
        "runs": "python3 scripts/css-var-check.py",
        "asserts": "A `var(--x)` with no fallback, where `--x` is defined nowhere — the whole "
                   "declaration drops silently, with no console warning. Five of these "
                   "accumulated across four screens (2026-09-20 UX review, Tier 1 item 1): two "
                   "misspellings of a real token, three reaching for a token never defined. "
                   "References are read from BOTH `.css` and `.ts`/`.tsx` (a plain or "
                   "template-literal string such as `'var(--bn-ok)'` is not stripped, only "
                   "comments are) — the check shipped reading `.css` only, and a reviewer's "
                   "mutation of a real Gallery.tsx reference exited 0 the same day. A "
                   "definition is collected from a `.css` declaration or from a TS/TSX "
                   "`style={{...}}` span's own runtime set (`style={{ '--x': ... }}`, a "
                   "bracket computed key, `.setProperty('--x', ...)`), measured across the "
                   "tree before those three shapes were chosen — the first two are read only "
                   "inside that span, by brace-counting, so an unrelated object literal whose "
                   "key happens to be spelled like a token cannot mask a real finding. "
                   "`var(--x, fallback)` is never a finding — the fallback IS the definition.",
        "needs": ("python3",),
        "writes": "",
        "commit_path": False,
        "why_off_commit_path": "not armed in scripts/githooks/pre-commit — `make check` is "
                               "where it runs today. Nothing here stops it joining the hook "
                               "the way sigil-check.py did; it simply has not been asked.",
        "gates": True,
        "governed_by": ("D18", "D173"),
    },
    {
        "target": "css-var-check-selftest",
        "runs": "python3 scripts/css-var-check.py --self-test",
        "asserts": "the guard sees its own subject before it is trusted: a genuinely undefined "
                   "`var()` fails, one with a fallback passes, one defined only from TSX "
                   "passes, a reference or definition written only in a comment is ignored, "
                   "an `@media` block is scanned like anywhere else, the two real "
                   "misspellings this check was built to catch (`--bn-r-md`, "
                   "`--bn-radius-md`) are caught, an undefined `var()` inside a TSX inline "
                   "style STRING is caught (the Gallery.tsx gap a reviewer found), and a "
                   "quoted key outside any `style={{...}}` span does not count as a "
                   "definition (the latent gap the same review named).",
        "needs": ("python3",),
        "writes": "",
        "commit_path": False,
        "why_off_commit_path": "css-var-check's reason exactly — not armed in "
                               "scripts/githooks/pre-commit, `make check` only.",
        "gates": True,
        "governed_by": ("D18", "D173"),
    },
    {
        "target": "ignore-check",
        "runs": "sh scripts/ignore-check.sh",
        "asserts": "Every path a worktree provisions is gitignored — as a file, as a directory "
                   "and as a symlink (D47).",
        "needs": ("sh", "git"),
        "writes": "",
        "commit_path": False,
        "why_off_commit_path": "D18, plus one of its own: it asks about local PROVISIONING, so "
                               "a fresh clone with none of these paths present would fail a "
                               "commit over nothing.",
        "gates": True,
        "governed_by": ("D18", "D47"),
    },
    {
        "target": "lint",
        "runs": "npm --prefix app run lint; ruff check . (ruff.toml)",
        "asserts": "eslint over app/, one rule per bug this project caught itself, plus ruff "
                   "over the Python packages on a slice measured against this tree — pyflakes, "
                   "bugbear, flake8-simplify, never ruff's own ~900-rule default (D82). No "
                   "`--fix`, in either language, per D18.",
        "needs": ("node", "app deps", "venv", "ruff"),
        "writes": "",
        "commit_path": False,
        "why_off_commit_path": "It runs node, and the git hook runs a bare python3.",
        "gates": True,
        "governed_by": ("D18", "D82"),
    },
    {
        "target": "vale",
        "runs": "git ls-files '*.md' | xargs vale --no-exit",
        "asserts": "Prose style over every TRACKED markdown file (D74). IT NEVER GATES, twice "
                   "over: `--no-exit` swallows its findings' status, and a missing binary "
                   "reports and exits 0 so `make check` still runs on a machine without it.",
        "needs": ("vale",),
        "writes": "",
        "commit_path": False,
        "why_off_commit_path": "vale is a third-party Go binary, and the pre-commit hook runs a "
                               "bare python3 (D18). A commit gate needing software PRESENT "
                               "would make the three opsec rules depend on it too.",
        "why_off_ci": "the binary is not on the GitHub runner, and it never gated anyway — "
                      "`--no-exit` swallows its status. `make ci-check` is what a fresh clone "
                      "can PROVE, so a target that proves nothing there is left out rather "
                      "than run for the shape of it. The one declared difference between the "
                      "two recipes, and `check registry` refuses a second without a sentence.",
        "gates": False,
        "governed_by": ("D18", "D60", "D74"),
    },
    {
        "target": "typecheck",
        "runs": "npm --prefix app run typecheck",
        "asserts": "tsc --noEmit over app/.",
        "needs": ("node", "app deps"),
        "writes": "",
        "commit_path": False,
        "why_off_commit_path": "It runs node, and the git hook runs a bare python3.",
        "gates": True,
        "governed_by": ("D18",),
    },
    {
        "target": "audit-self-test",
        "runs": "python3 scripts/docs-audit.py --self-test",
        "asserts": "The auditor's own extractors, against fixtures it builds and destroys. It "
                   "sat red and unnoticed until 2026-08-24 because nothing ran it at all.",
        "needs": ("python3",),
        "writes": "a temporary directory it makes and removes.",
        "commit_path": False,
        "why_off_commit_path": "D18: `--self-test` is the one mode of docs-audit.py that "
                               "writes, and nothing that writes may run on the path that "
                               "decides whether a commit proceeds. `make check` is invoked by a "
                               "person, so it is not that path.",
        "gates": True,
        "governed_by": ("D16", "D18"),
    },
    {
        "target": "mutate-anchors",
        "runs": "python3 scripts/mutate-guards.py --verify-anchors",
        "asserts": "Every mutation in `scripts/mutate-guards.py` still has its anchor text "
                   "present exactly once in the guard it targets. 35 arms over 6 guards, in "
                   "0.03s. THE ROT CHECK AND NOT THE PROOF: `make mutate-guards` is what runs "
                   "the mutations, at 190s, and is off every list for that reason. This is the "
                   "half that catches a guard reworded past its own mutation — the corpus goes "
                   "on reporting a count while proving nothing, which is precisely how the "
                   "PROSE arm counts rotted (the sentence at :378 in this file says its own "
                   "number was wrong once). A behaviour-preserving reword of one anchored line "
                   "takes this from 35 verified to `1 of 35 stale`, exit 1.",
        "needs": ("python3",),
        "writes": "",
        "commit_path": False,
        "why_off_commit_path": "Not the toolchain and not the runtime — it needs a bare python3 "
                               "and costs 0.03s. The commit path is two checks by choice.",
        "gates": True,
        "governed_by": ("D18", "D173"),
    },
    {
        "target": "githooks-selftest",
        "runs": "bash scripts/githooks-selftest.sh",
        "asserts": "D42's two hooks over main, exercised in a bare repo and a clone built for "
                   "the run. A refusal must carry the hooks' own `REFUSED:` marker, so git's "
                   "own refusals cannot score as the guard's.",
        "needs": ("bash", "git"),
        "writes": "a bare repo, a clone, commits and pushes, all under `mktemp -d`.",
        "commit_path": False,
        "why_off_commit_path": "D18, and a second reason of its own: it exercises the guard by "
                               "VIOLATING it, so a version on the commit path would be refusing "
                               "its own commits.",
        "gates": True,
        "governed_by": ("D18", "D42"),
    },
    {
        "target": "merge-selftest",
        "runs": "bash scripts/merge-selftest.sh",
        "asserts": "scripts/merge-pr.py's local half, against a throwaway origin, clone and "
                   "second worktree. The case that matters is the footgun D42 names: main "
                   "checked out NOWHERE while a feature branch sits in the other tree, where "
                   "the wrong command silently fast-forwards that branch and trips no hook.",
        "needs": ("python3", "bash", "git"),
        "writes": "a bare repo, a clone and a linked worktree, all under `mktemp -d`.",
        "commit_path": False,
        "why_off_commit_path": "D18 — it writes — and githooks-selftest's second reason applies "
                               "unchanged: it drives the thing that moves main.",
        "gates": True,
        "governed_by": ("D18", "D42"),
    },
    {
        "target": "revert-selftest",
        "runs": "python3 scripts/revert-audit.py selftest",
        "asserts": "The revert guard, against a throwaway origin and clone that rebuild the "
                   "#218/#221 sequence: a deletion merged, a branch cut from before it that "
                   "merges main keeping `ours` and squashes onto main. Ten cases: the fixture's "
                   "own arming, the squash refused, the history walk naming the merge AND the "
                   "deleting commit inside it, a clean branch allowed, a partial reversal "
                   "noted and allowed, a declared restoration allowed, a silent one refused at "
                   "hunk level, the escape hatch honoured, and main itself landing nothing.",
        "needs": ("python3", "git"),
        "writes": "a bare repo and a clone, under `mktemp -d`.",
        "commit_path": False,
        "why_off_commit_path": "D18 — it writes — and githooks-selftest's second reason: it "
                               "drives the guard by defeating it.",
        "gates": True,
        "governed_by": ("D18", "D42", "D133"),
    },
    {
        "target": "claim-selftest",
        "runs": "python3 scripts/claim-selftest.py",
        "asserts": "scripts/claim-ids.py against a throwaway repository in which MAIN MOVES "
                   "underneath the branch, which is the only condition that can tell an "
                   "allocation against the ref from an allocation against the branch's own "
                   "copy. FORTY-TWO arms — the count in this sentence said sixteen over a "
                   "file that held eighteen, which is what a prose count does. Fourteen of "
                   "them cover the staleness half (D140, amended 2026-09-11): a branch claims "
                   "honestly, main takes the number underneath it, and the check must go red "
                   "and NAME it. Mutation-tested on twelve — five when the claimer landed, "
                   "seven over the staleness half and eight over the tree precondition, none "
                   "of which survived. The boundary "
                   "arm found a real bug in the unmutated code — `\\b` fires between a letter "
                   "and a hyphen, so one slug was substituted inside another that extended "
                   "it; the staleness arms found a second, that reading the baseline from the "
                   "REF rather than the merge base makes every collision cancel itself out. "
                   "SINCE 2026-09-20 IT ALSO COVERS THE WAIT'S SECOND QUESTION: whether the "
                   "pull request can still merge while the wait is happening. A branch that "
                   "goes CONFLICTING under it ends the wait early and says main moved, and "
                   "`UNKNOWN` — which GitHub answers routinely while it computes — never "
                   "does. Every no-news arm runs over a roster that NEVER COMPLETES, because "
                   "one that goes green in two reads never reaches the mergeability reader at "
                   "all and passes whatever it answers. That defect was live here until a "
                   "mutation survived it.",
        "needs": ("python3", "git"),
        "writes": "a temporary directory it makes and removes.",
        "commit_path": False,
        "why_off_commit_path": "D18: it writes, and nothing that writes may run on the path "
                               "that decides whether a commit proceeds. It also builds three "
                               "git repositories, which the hook has no business doing.",
        "gates": True,
        "governed_by": ("D16", "D18", "D140"),
    },
    {
        "target": "decisions-selftest",
        "runs": "python3 scripts/split-decisions.py --selftest",
        "asserts": "`docs/decisions/` is a complete, well-formed set: every file "
                   "`ORDER.json` names is present, every markdown file present is named, no "
                   "id appears in two files, and the reassembly still ends in a newline. The "
                   "duplicate arm is the one a directory newly needs — one entry copied "
                   "rather than moved puts `## D58` in two files, which a single document "
                   "could not express and nothing else would notice. It does NOT hash the "
                   "live corpus: editing an entry is the normal way this corpus changes, and "
                   "a digest over the whole thing would go red on the next decision entry "
                   "and blame a routine append for a loss that had not happened. The "
                   "historical claim — that the split itself lost nothing — is "
                   "`--verify-split REF`, which reads both sides out of git.",
        "needs": ("python3",),
        "writes": "",
        "commit_path": False,
        "why_off_commit_path": "Nothing here is urgent enough to pay for on every commit: a "
                               "corpus that has lost a file fails `decision ids` and "
                               "`decision index` in the same run, so the commit gate already "
                               "refuses the damage this names. It is in `check` and "
                               "`ci-check` for the earlier, clearer message.",
        "gates": True,
        "governed_by": ("D16", "D18", "D60", "D160"),
    },
    {
        "target": "debts-selftest",
        "runs": "python3 scripts/split-debts.py --selftest",
        "asserts": "`docs/debts/` is a complete, well-formed set — the debts twin of "
                   "`decisions-selftest`, same shape: every file `ORDER.json` names is "
                   "present, every markdown file present is named, no id appears in two "
                   "files, and the reassembly still ends in a newline. It does NOT hash the "
                   "live corpus for the same reason `decisions-selftest` does not: editing "
                   "a finding is the normal way this corpus changes. The historical claim "
                   "that the split itself lost nothing is `--verify-split REF`.",
        "needs": ("python3",),
        "writes": "",
        "commit_path": False,
        "why_off_commit_path": "Same argument as `decisions-selftest`: a corpus that has "
                               "lost a file fails `debt ids` and `debt index` in the same "
                               "run, so the commit gate already refuses the damage this "
                               "names. It is in `check` and `ci-check` for the earlier, "
                               "clearer message.",
        "gates": True,
        "governed_by": ("D16", "D18", "D149", "D160"),
    },
    {
        "target": "gates-selftest",
        "runs": "python3 scripts/split-gates.py --selftest",
        "asserts": "`docs/gates/` is a complete, well-formed set: every file `ORDER.json` "
                   "names is present, every markdown file present is named, no step id "
                   "appears in both the shipped and open lists, and the corpus meets its "
                   "pinned non-vacuity floor (>=9 contract entries T1..T9, >=5 run entries, "
                   ">=15 shipped steps) — a parser finding nothing over a renamed heading is "
                   "reported as BROKEN, never as a clean tree. It does NOT hash the live "
                   "corpus, for `decisions-selftest`'s own reason: editing an entry is the "
                   "normal way this corpus changes. The historical claim — that the split "
                   "itself lost nothing — is `--verify-split REF`, which reads both sides "
                   "out of git.",
        "needs": ("python3",),
        "writes": "",
        "commit_path": False,
        "why_off_commit_path": "Nothing here is urgent enough to pay for on every commit: a "
                               "corpus that has lost a file fails `gates structure` and "
                               "`build order mirror` in the same run, so the commit gate "
                               "already refuses the damage this names. It is in `check` and "
                               "`ci-check` for the earlier, clearer message.",
        "gates": True,
        "governed_by": ("D16", "D18", "D80", "D160"),
    },
    {
        "target": "submission-selftest",
        "runs": "python3 scripts/submission-selftest.py",
        "asserts": "store/submissions.py — the claim table that refuses a second `identify` "
                   "press over cards a live run is already paying to read — by violating it "
                   "against a throwaway store. The two concurrent cases are real separate "
                   "processes racing a real flock over one card, and the first of them "
                   "REPRODUCES the bug rather than asserting about it: the children run the "
                   "check-then-claim order anybody writes first and both buy the same card. "
                   "Then the disjoint selections in one drawer that the box form refuses, the "
                   "press spanning drawers that the box form cannot see at all, a holder "
                   "killed with -9 whose claim must keep blocking and become releasable, and "
                   "the FIGURES — rows live and CARDS locked — because a table that claimed "
                   "nothing would pass every outcome assertion here.",
        "needs": ("python3",),
        "writes": "one sqlite store per case and two short-lived processes, all under "
                  "`mktemp -d`. `PKMNSCAN_HOME` is repointed for every case, so the "
                  "operator's own store is never opened.",
        "commit_path": False,
        "why_off_commit_path": "D18 — it writes a temp store and it signals processes. Same "
                               "standing as janitor-selftest and reap-selftest.",
        "gates": True,
        "governed_by": ("D7", "D18", "D48", "D88"),
    },
    {
        "target": "cid-selftest",
        "runs": "python3 scripts/cid-selftest.py",
        "asserts": "D172's stable card name and the photograph store filed under it, by "
                   "violating both against a throwaway store. The naming's SOURCE CENSUS, "
                   "because every row gets a value and a count of them cannot tell a correct "
                   "seeding from one nothing checked; a name stripped by an older build "
                   "re-issued BYTE-IDENTICALLY, which is the whole argument against an "
                   "allocator; the three value shapes that have never fired in production, "
                   "PROVOKED rather than asserted over; the forward-version guard; a `-9` "
                   "mid-transaction leaving the store unchanged; the relocation's per-card "
                   "link-verify-unlink, its resumption, and its refusal of a file whose bytes "
                   "are not the card's; and a re-shoot excused by a RECORDED digest, with the "
                   "audit going red when that digest is mutated. Two cases COUNT FILESYSTEM "
                   "CALLS — a renumber renames nothing where it was N-k renames and N-k "
                   "sidecar rewrites, and a move touches no file at all — because an outcome "
                   "assertion cannot see work that no longer happens.",
        "needs": ("python3",),
        "writes": "one sqlite store and one photograph tree per case, all under `mktemp -d`, "
                  "plus one short-lived process. `PKMNSCAN_HOME` is repointed for every case, "
                  "so the operator's own store and their 4.45 GB of photographs are never "
                  "opened.",
        "commit_path": False,
        "why_off_commit_path": "D18 — it writes a temp store, draws photographs and kills a "
                               "process. Same standing as submission-selftest.",
        "gates": True,
        "governed_by": ("D18", "D26", "D83", "D88", "D89", "D172"),
    },
    {
        "target": "readings-selftest",
        "runs": "python3 scripts/readings-selftest.py",
        "asserts": "the cached market-reading table (store/readings.py) and the two-source "
                   "walk that fills it (pipeline/readings.py), by comparing `collect()` "
                   "against an INDEPENDENT reimplementation of the same rule over a "
                   "throwaway store — an empty store, a store with only run tables, a store "
                   "with only a live export, a run and a live export disagreeing on one SKU "
                   "in both directions of which is newer, the newest-by-name live export "
                   "carrying an unparseable filename (must lose to everything and never fall "
                   "back to an older readable file), `readings adopt --write` followed by "
                   "the exact SELECT `_readings()` now performs, two adopts in a row over "
                   "unchanged files (idempotent, no duplicate rows), a new run landing "
                   "between two adopts, and a run directory deleted between two adopts (its "
                   "SKU drops out of the table — a cache refresh, never an accumulating "
                   "ledger).",
        "needs": ("python3",),
        "writes": "one sqlite store per case, under `mktemp -d`. `PKMNSCAN_HOME` is "
                  "repointed for the whole run, so the operator's own store is never opened.",
        "commit_path": False,
        "why_off_commit_path": "D18 — it writes a temp store. Same standing as "
                               "submission-selftest and cid-selftest.",
        "gates": True,
        "governed_by": ("D189", "D18", "D86", "D88"),
    },
    {
        "target": "janitor-selftest",
        "runs": "bash scripts/janitor-selftest.sh",
        "asserts": "scripts/janitor.py, against a throwaway clone with real worktrees, a fake "
                   "liveness oracle and real processes in their own process groups. The cases "
                   "that matter are the refusals: a worktree with a live session in it, a "
                   "branch that is unmerged and on no remote, and a husk directory something "
                   "is still running under. Each asserts the janitor's OWN sentence, because "
                   "git would refuse some of them on its own and survival by somebody else's "
                   "refusal is not coverage.",
        "needs": ("python3", "bash", "git"),
        "writes": "a bare repo, a clone, four linked worktrees and four short-lived processes, "
                  "all under `mktemp -d` and all confined to it by `--confine`.",
        "commit_path": False,
        "why_off_commit_path": "D18 — it writes, and it signals processes. It drives the one "
                               "tool here besides icloud-sweep that can delete a worktree.",
        "gates": True,
        "governed_by": ("D18", "D44", "D53"),
    },
    {
        "target": "reap-selftest",
        "runs": "bash scripts/reap-selftest.sh",
        "asserts": "scripts/reap.py, against a throwaway checkout, a throwaway sibling "
                   "directory standing in for everywhere-else, and real processes in their own "
                   "process groups. BOTH INCIDENTS ARE CASES rather than prose: `pkill -f "
                   "<name>` where a stranger also matches, and `for p in $(lsof -ti tcp:PORT); "
                   "do kill $p; done` where a CLIENT holds the port. The cases that matter "
                   "either way are the two edges — that a stranger's process is refused AND "
                   "survives, and that the session's own is still killable, because a guard "
                   "that breaks cleanup is one that gets switched off.",
        "needs": ("python3", "bash", "git", "lsof"),
        "writes": "a git repo, two scripts, a `.serve/` pidfile and four short-lived "
                  "processes, all under `mktemp -d`. It signals only what it spawned.",
        "commit_path": False,
        "why_off_commit_path": "D18 — it writes, and it signals processes. It drives the one "
                               "guard here that can refuse a shell command outright.",
        "gates": True,
        "governed_by": ("D18", "D53", "D111", "D127"),
    },
    {
        "target": "silent-write-selftest",
        "runs": "bash scripts/silent-write-selftest.sh",
        "asserts": "scripts/silent-write-guard.py, the PreToolUse hook that refuses a git "
                   "write whose own output is discarded. THE INCIDENT IS REPRODUCED rather "
                   "than asserted about: a throwaway repository with a pre-commit hook that "
                   "refuses, the 2026-09-12 command run verbatim, and the proof that "
                   "`git log --oneline -1` then answers with the PREVIOUS commit — the stale "
                   "read that was reported as `pushed`. The half that decides whether this "
                   "guard survives is the false positives, and each is RUN in the fixture "
                   "before it is scored: `git rev-parse … 2>/dev/null`, `git fetch origin -q "
                   "2>/dev/null`, `git merge --abort 2>/dev/null`, `git merge-tree`, "
                   "`make merge-selftest`, and a quoted `>/dev/null` inside a commit message. "
                   "The refusal's own text is scored too — a refusal that does not print "
                   "`PKMNSCAN_SILENT=off` fails here.",
        "needs": ("python3", "bash", "git"),
        "writes": "a git repository, a pre-commit hook and two commits, all under `mktemp -d`. "
                  "It starts no long-lived process and signals nothing.",
        "commit_path": False,
        "why_off_commit_path": "D18 — it writes a temp repository and makes real commits in "
                               "it. Same standing as reap-selftest beside it, whose guard it "
                               "copies its fail-open asymmetry from.",
        "gates": True,
        "governed_by": ("D18", "D42", "D127"),
    },
    {
        "target": "guard-shell-selftest",
        "runs": "bash scripts/guard-shell-selftest.sh",
        "asserts": "scripts/guard-shell.py, the PreToolUse hook that refuses six shell "
                   "mistakes this repo has already paid for: `git checkout` over a modified "
                   "file, a write outside this checkout, `gh api -f` with no method, `ln -s` "
                   "at an existing path, a polling loop, and `git push <remote> HEAD` (or the "
                   "branch's own literal name) when the tracked upstream is a different name. "
                   "FIVE OF THE SIX INCIDENTS ARE "
                   "PERFORMED rather than asserted about — 240 lines really destroyed by a "
                   "real `git checkout`, a real worktree whose root differs from its main "
                   "checkout's, a real `harness/images/images` created by a real `ln -s`, "
                   "`pgrep -f` really matching a process that merely NAMES its pattern, and a "
                   "real local branch made to track a differently-named remote branch. The "
                   "half that decides whether the guard survives is the false positives, and "
                   "the git ones are RUN in the fixture before they are scored: a branch, a "
                   "clean path, `--staged`, a named source, `-sfn`, `--method GET`, `graphql`, "
                   "a pid wait, a bounded retry, the ordinary first push of a new branch, an "
                   "upstream already matching its own name, and every `git`/`gh`/`ln` line "
                   "swept out of "
                   "this repo's own tooling. Each hatch is scored in both of "
                   "its forms, and the clause table is READ rather than retyped, so a new "
                   "clause with no hatch fails here instead of shipping unescapable. "
                   "A NINTH CLAUSE LANDED 2026-09-20 and is the one that names its subjects "
                   "rather than resolving them: a command that waits for minutes while "
                   "narrating, piped into a truncating filter or redirected away. Its "
                   "incident is performed here too — a real narrator, a real pipe and a real "
                   "`tail`, measured at 0 bytes delivered mid-run and 2 of 5 lines kept — and "
                   "its named roster is RECONCILED against the heartbeat constant in the file "
                   "that runs each command it names. Thirteen must-never-refuse cases carry "
                   "that clause, because a general form of it would fire on honest work every "
                   "day.",
        "needs": ("python3", "bash", "git"),
        "writes": "a git repository, a linked worktree, two commits, a symlink and one "
                  "short-lived decoy process, all under `mktemp -d`. It signals only what it "
                  "spawned there.",
        "commit_path": False,
        "why_off_commit_path": "D18 — it writes a temp repository, adds a worktree to it and "
                               "makes real commits. Same standing as silent-write-selftest "
                               "beside it, whose parser its guard shares.",
        "gates": True,
        "governed_by": ("D18", "D43", "D127", "D171", "D173"),
    },
    {
        "target": "coordinator-selftest",
        "runs": "python3 scripts/coordinator.py --selftest",
        "asserts": "scripts/coordinator.py's verdict rules, against synthetic check-run "
                   "payloads. Every case is a payload that a reader looking at conclusions "
                   "ALONE would call clean, and the assertion is that this one does not: one "
                   "required check of two with everything reported passing, a required check "
                   "that reported `skipped`, a commit with no runs at all. The two mirrors are "
                   "cases as well — a null conclusion is `running` and never `failed`, and an "
                   "OPTIONAL check may be skipped without spoiling a green. It also asserts "
                   "the report's own floor: a block that could not be read makes the exit "
                   "non-zero, so an incomplete report cannot be relayed as the state of the "
                   "queue.",
        "needs": ("python3",),
        "writes": "",
        "commit_path": False,
        "why_off_commit_path": "D16 — it is a self-test rather than a doc check, and it belongs "
                               "beside the other selftests at the end of `check` rather than "
                               "on the hook. Nothing here writes, so D18 is not the reason.",
        "gates": True,
        "governed_by": ("D42", "D141"),
    },
    {
        "target": "suite-lock-selftest",
        "runs": "python3 scripts/suite-lock.py selftest",
        "asserts": "scripts/suite-lock.py, by violating it: a holder, a second run refused, a "
                   "`--wait` that queues and announces itself, and a holder killed with -9 to "
                   "prove the OS releases what it took. That last case is the whole argument "
                   "for `flock` over a pidfile, and it is the one a reader would otherwise "
                   "have to take on trust.",
        "needs": ("python3",),
        "writes": "a lock directory and lock files under `mktemp -d`, reached through "
                  "PKMNSCAN_LOCK_DIR so the real lock is never touched — a self-test that "
                  "took the real one would refuse a suite running in another checkout.",
        "commit_path": False,
        "why_off_commit_path": "D18 — it writes, and it spawns processes and kills them. It "
                               "also holds a lock for a second or two, and the commit path is "
                               "not a place to queue behind anything.",
        "gates": True,
        "governed_by": ("D18", "D43", "D122"),
    },
    {
        "target": "browser-scope-selftest",
        "runs": "python3 scripts/browser-scope.py selftest",
        "asserts": "the browser-matrix classifier's spec map (D215), on "
                   "fixtures and on the real tree: `app/src/kit/` narrows nothing, a real "
                   "screen (`Inventory.tsx`) reaches its own spec and every `routesFromNav(` "
                   "spec but not an unrelated one, an unknown `app/` path and a path carrying "
                   "whitespace both select every spec rather than a guess, and "
                   "`PKMNSCAN_BROWSER_SCOPE=off` does too.",
        "needs": ("python3",),
        "writes": "",
        "commit_path": False,
        "why_off_commit_path": "D16 — it is a self-test rather than a doc check, and it "
                               "belongs beside the other selftests at the end of `check`.",
        "gates": True,
        "governed_by": ("D141", "D18", "D173"),
    },
    {
        "target": "serve-selftest",
        "runs": "python3 scripts/serve-selftest.py",
        "asserts": "the supervisor's build job (D138), against a throwaway checkout whose "
                   "`vite build` is a shell stub. What is under test is the supervisor and "
                   "never the compiler: that a cold tree builds BEFORE the port opens, that a "
                   "screen edit rebuilds and does not restart the capture child, that a "
                   "Python edit restarts it and does not rebuild, that a failed build leaves "
                   "the previous bundle byte-identical, that every request during a build "
                   "answers 200 — the swap is two renames — and that with no node on PATH the "
                   "API comes up anyway while `GET /` says 503. Five mutations were observed "
                   "failing it, including building straight into `dist/`.",
        "needs": ("python3",),
        "writes": "two throwaway checkouts, their `.serve/` directories and the supervisors "
                  "and capture servers running under them, all inside `mktemp -d`. The "
                  "capture port is PINNED with `PKMNSCAN_PORT` rather than derived: a copied "
                  "tree is not a linked worktree, so it would call itself the main checkout "
                  "and claim :8000 — the owner's live server.",
        "commit_path": False,
        "why_off_commit_path": "D18 — it writes, and it starts and signals real processes.",
        "gates": True,
        "governed_by": ("D18", "D43", "D53", "D138"),
    },
    {
        "target": "sync-selftest",
        "runs": "python3 scripts/sync-selftest.py",
        "asserts": "the primary checkout's self-sync, proved by violating it in throwaway "
                   "clones with their own worktrees and a real bare origin. Both parts, from "
                   "one call: a tree parked on a feature branch goes back to main AND main "
                   "fast-forwards to origin/main. And the six refusals, each a real repository "
                   "state rather than a mock — uncommitted TRACKED work, named and never "
                   "discarded; untracked exhaust, which must NOT block a sync; a half-finished "
                   "merge and a stopped rebase, whose markers are a file and a directory; main "
                   "held by another worktree; a local main that is ahead or diverged, which is "
                   "no fast-forward; and a detached HEAD no ref contains. A LINKED WORKTREE IS "
                   "LEFT COMPLETELY ALONE, asked from inside one. One arm arms D42's own "
                   "`reference-transaction` hook and proves BOTH directions: the sync's "
                   "fast-forward is permitted by allow rule 3, and a move to a commit origin "
                   "does not carry is still refused. Its own bugs fail OPEN and silently; a "
                   "fact it cannot read fails CLOSED and loud.",
        "needs": ("python3", "git"),
        "writes": "bare origins, clones and linked worktrees under `mktemp -d`, with real "
                  "commits and real `refs/heads/main` moves in them. NEVER this checkout: the "
                  "subject of a sync is the PRIMARY tree, which on this machine is the owner's "
                  "live rig with a capture server kept alive at login over their real store.",
        "commit_path": False,
        "why_off_commit_path": "D18 — it writes, and what it writes are branch switches and "
                               "ref moves. Same standing as merge-selftest beside it.",
        "gates": True,
        "governed_by": ("D18", "D42", "D43", "D53", "D139", "D158"),
    },
    {
        "target": "verdict-selftest",
        "runs": "python3 scripts/verdict-selftest.py",
        "asserts": "app/design-check-reporter.ts, run for real against one passing and one "
                   "failing spec: the verdict, the counts, the failing title and its "
                   "location — file AND line, the line asserted against the probe's own "
                   "source, because Playwright 1.55.1 miscounted it under Node 23+ and the "
                   "verdict named the wrong line (D129; 1.58.0 is the floor that counts it "
                   "right, and this arm is what would see a bump bring it back) — the in-flight `running` sentinel (observed by the passing test "
                   "from inside the run, which is the only way to see it that is not a race), "
                   "and that the error text carries no ANSI escapes and no NUL bytes. "
                   "`make docs-audit`'s `verdict file` row is the static half — it reconciles "
                   "the four files that NAME the verdict path and cannot say the reporter "
                   "still works. The regression neither name-checking nor the design suite "
                   "would catch is a @playwright/test bump moving the Reporter API under it: "
                   "every name stays in place and every count goes wrong, and a session reads "
                   "a green verdict off a reporter that stopped counting.",
        "needs": ("python3", "node", "app deps"),
        "writes": "a throwaway tree under `tempfile.TemporaryDirectory()` holding a COPY of the "
                  "reporter, the real app/package.json, a symlink to app/node_modules and two "
                  "generated specs. The copy is what keeps its verdict inside the temporary "
                  "directory: RESULT_FILE is derived from the reporter's own location, so "
                  "running the real file in place would overwrite `.serve/design-check.json` — "
                  "a file a session may be about to read, which would make this check cause "
                  "the false green it exists to prevent.",
        "commit_path": False,
        "why_off_commit_path": "D18 — it writes, and it shells out to node.",
        "gates": True,
        "governed_by": ("D16", "D18", "D129"),
    },
    {
        "target": "js-breakpoints-selftest",
        "runs": "python3 scripts/js-breakpoints.py selftest",
        "asserts": "the pure extraction and comparison behind `make docs-audit`'s `js "
                   "breakpoints` row (D123): a JS media-query width is read out of a "
                   "matchMedia-shaped string with comments stripped (a block comment's own "
                   "width does not fool it, and the line number survives the strip), a CSS "
                   "width is read only out of an `@media` block and never an `@container` "
                   "one, `min-width: V` and `max-width: V-1` canonicalize to the same regime "
                   "boundary, a JS breakpoint with no CSS counterpart is reported (RED) and "
                   "the same breakpoint once a stylesheet declares it is clean (GREEN), a "
                   "clean file beside a broken one names only the broken one, and the real "
                   "`app/src` tree has at least one breakpoint on each side to compare.",
        "needs": ("python3",),
        "writes": "",
        "commit_path": False,
        "why_off_commit_path": "D16 — it is a self-test rather than a doc check, and it "
                               "belongs beside the other selftests at the end of `check`.",
        "gates": True,
        "governed_by": ("D18", "D123", "D173"),
    },
    {
        "target": "subagent-override-selftest",
        "runs": "python3 scripts/subagent-override-selftest.py",
        "asserts": "`make docs-audit`'s `subagent override` row, by violating it in a real "
                   "throwaway git repository with a real nested worktree (the shape "
                   "`.claude/worktrees/<name>/` is, and the exact place a 2026-09-19 "
                   "forgotten subagent-model override sat): a clean tree is green; the "
                   "override in the checkout's own settings.local.json is red and named; "
                   "the same override in the NESTED WORKTREE's own settings.local.json is "
                   "red and named by its own path — the case a root-only reader would miss; "
                   "an expiry already past is red; an expiry inside the 24-hour lookahead "
                   "ceiling is GREEN, proving this is not a bare forbid; an expiry past the "
                   "ceiling is red again; and the override in the TRACKED settings.json is "
                   "red regardless of expiry, because no expiry excuses committing it.",
        "needs": ("python3", "git"),
        "writes": "a temporary git repository and a real nested worktree under "
                  "`mktemp -d`, removed at the end of the run — never the real repo's own "
                  "`.claude/` or `.claude/worktrees/`.",
        "commit_path": False,
        "why_off_commit_path": "D18 — it writes a temporary git repository and worktree. "
                               "The row it proves runs on every commit regardless, in "
                               "`check_subagent_override` inside docs-audit.py's own "
                               "unconditional (never `--staged`-narrowed) call list.",
        "gates": True,
        "governed_by": ("D18", "D135", "D173", "D178"),
    },
)


# --------------------------------------------------------------------------- rendering


def wrap(text: str, indent: int, width: int = WIDTH) -> List[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) + indent > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def table() -> str:
    longest = max(len(entry["target"]) for entry in CHECKS)
    lines = [
        "PKMNSCAN — what `make check` runs" + f"{len(CHECKS)} checks".rjust(
            WIDTH - len("PKMNSCAN — what `make check` runs")
        ),
        "=" * WIDTH,
        "",
        f"  {'target':<{longest}}  gates  commit  writes  needs",
        f"  {'-' * (WIDTH - 2)}",
    ]
    for entry in CHECKS:
        lines.append(
            "  {target:<{w}}  {gates:^5}  {commit:^6}  {writes:^6}  {needs}".format(
                w=longest,
                target=entry["target"],
                gates="yes" if entry["gates"] else "NO",
                commit="YES" if entry["commit_path"] else "no",
                writes="yes" if entry["writes"] else "-",
                needs=", ".join(entry["needs"]),
            )
        )
    lines += [
        "",
        "  gates   a finding here fails `make check`. `vale` deliberately does not.",
        "  commit  scripts/githooks/pre-commit runs it, so it decides whether a commit",
        "          proceeds. D18: nothing that WRITES may ever be in this column.",
        "",
        "  `make explain ARGS=<target>` for one entry in full.",
        "",
        "The Makefile's `check:` recipe is what actually runs; this file is a parallel",
        "declaration, and `make docs-audit`'s `check registry` row fails the commit that",
        "lets the two disagree.",
    ]
    return "\n".join(lines)


def one(name: str) -> str:
    entry = next((e for e in CHECKS if e["target"] == name), None)
    if entry is None:
        known = ", ".join(e["target"] for e in CHECKS)
        return f"no check called `{name}` runs in `make check`.\n  These do: {known}"

    lines = [f"make {entry['target']}", "=" * WIDTH, ""]

    def block(label: str, text: str) -> None:
        for i, line in enumerate(wrap(text, 14)):
            lines.append(f"  {label if i == 0 else '':<12}{line}")

    block("runs", entry["runs"])
    block("asserts", entry["asserts"])
    block("needs", "; ".join(f"{n} — {NEEDS[n]}" for n in entry["needs"]))
    block("writes", entry["writes"] or "nothing, anywhere.")
    if entry["commit_path"]:
        block("commit path", "YES — scripts/githooks/pre-commit runs this, so it decides "
                             "whether a commit proceeds.")
    else:
        block("commit path", "no.")
        block("", entry["why_off_commit_path"])
    block("gates", "a finding fails `make check`." if entry["gates"]
          else "NO — it reports and `make check` carries on.")
    # Rendered wherever it is declared, so the field is not a sentence only the audit reads.
    # `check registry` pairs it against the `ci-check:` recipe in both directions: present
    # exactly where the target is absent from that recipe.
    if entry.get("why_off_ci"):
        block("ci-check", "NOT run on CI.")
        block("", entry["why_off_ci"])
    block("governed by", ", ".join(entry["governed_by"]) + "  — docs/DECISIONS.md")
    return "\n".join(lines)


def main(argv: Sequence[str]) -> int:
    if argv:
        print(one(argv[0]))
        return 0 if any(e["target"] == argv[0] for e in CHECKS) else 1
    print(table())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
