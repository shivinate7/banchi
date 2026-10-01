"""Self-test cases, records rows. Called by `selftest.self_test`."""

from __future__ import annotations

import ast
import re
import tempfile
from pathlib import Path

from .code_invariants import _PAYLOAD_ASSIGN_RE, _payload_keys, _ts_function_body
from .core import ROOT, _GATES_STEP_SLUG, _sibling, top_level_names
from .env_map import cited_decisions
from .harness_criteria import gates_pass_line, strip_presentation
from .paths_commands import path_candidates, resolve_candidate
from .reasons import _emitted_names, _roster
from .records import (
    _CODES_DECISION_RE,
    _DECISION_RE,
    _ID_SLUG,
    _prose_guard,
    decision_heading_lines,
    is_main,
    is_slug,
    without_noqa,
)
from .screens import _pooled_absence_titles
from .selftest_data import NON_PATHS, REAL_PATHS


def run(ok) -> None:
    print("\nextractor rejects prose that only looks like a path")
    tops = top_level_names()
    for line in NON_PATHS:
        kept = [
            candidate
            for candidate in path_candidates(line)
            if resolve_candidate(candidate, ROOT / "docs" / "X.md", tops) is not None
        ]
        ok(not kept, line[:58], f"extracted: {kept}")

    # A RENUMBER IS A TITLE THAT KEPT ITS NAME AND CHANGED ITS ID, and this is the reader of
    # that. The git walk around it needs a repository; this does not, and it is where the
    # logic that could be wrong lives (D140).
    # WHICH TREE AM I, asked without a repository. The case that was
    # wrong is the third: a NAMED branch sitting at origin/main, which is every branch between
    # `git checkout -b` and its first commit.
    print("\nwhich checkout is main, over the four readings that can say so")
    for ref_name, named, head, origin_main, want, label in [
        ("", "main", "aaa", "aaa", True, "the branch is named main"),
        ("main", "HEAD", "aaa", "bbb", True, "GITHUB_REF_NAME says main, head detached"),
        ("", "HEAD", "aaa", "aaa", True, "detached AT origin/main — the CI runner this rule is for"),
        ("", "HEAD", "aaa", "bbb", False, "detached somewhere else"),
        ("", "", "aaa", "aaa", True, "no name at all, sitting at origin/main"),
        ("", "claude/a-branch", "aaa", "aaa", False,
         "A NAMED BRANCH AT origin/main IS NOT MAIN — every branch before its first commit"),
        ("", "claude/a-branch", "aaa", "bbb", False, "a named branch that has committed"),
    ]:
        got = is_main(ref_name, named, head, origin_main)
        ok(got == want, label, f"wanted {want}, got {got}")

    # THE EQUALITY THAT REPLACED TWO SUBSTRING TESTS. Both legs of check_pass_criteria used
    # to ask whether the criterion appeared SOMEWHERE in the section, which `0.9` satisfies
    # inside `0.95`. These cases are the arithmetic of that, with no filesystem in the way.
    print("\na published criterion is compared by equality, not by containment")
    bullet = "- **Pass**: `holdout_accuracy >= 0.95`\n- **The gate is the holdout**, not all."
    inline = "New 2026-08-30 with C9-C11. **Pass: every decode round-trips its own\ncode.**\n\nProse after."
    ok(gates_pass_line(bullet) == ["`holdout_accuracy >= 0.95`"],
       "the bullet form is lifted and stops at the next bullet",
       f"got: {gates_pass_line(bullet)}")
    ok(gates_pass_line(inline) == ["every decode round-trips its own code.**"],
       "the inline bold form is lifted and joined across its wrap",
       f"got: {gates_pass_line(inline)}")
    ok(gates_pass_line("no claim here at all") == [],
       "a section publishing nothing lifts nothing, which is itself the finding")
    ok(strip_presentation("`holdout_accuracy >= 0.95`") == "holdout_accuracy >= 0.95",
       "code ticks come off a machine string")
    ok(strip_presentation("every decode round-trips.**") == "every decode round-trips",
       "the inline terminator and the full stop come off")
    ok(strip_presentation("a >= 0.9") != strip_presentation("a >= 0.95"),
       "AND THE MEASURED DEFECT: 0.9 no longer satisfies 0.95")
    ok("0.9" in "0.95",
       "which the old containment test could not say, because this is true")

    # The two claim writers' decode tables, read the way check_claim_decode reads them.
    print("\na handler's decode table is read off its `\"key\" in payload` branches")
    tree = ast.parse(
        'def do_put_card(self, payload):\n'
        '    if "game" in payload:\n        pass\n'
        '    if "product" in payload:\n        pass\n'
        '    if "note" in other:\n        pass\n'
    )
    keys = _payload_keys(tree.body[0])
    ok(keys == {"game", "product"}, "every key branched on payload is found", f"got: {sorted(keys)}")
    ok("note" not in keys, "and a branch on a different dict is not one of them")

    # The cross-language half of D101's two doors, and the reader that pins a published
    # figure to the file a scanner wrote.
    print("\nthe client's wire keys are read out of its payload assignments")
    ts = (
        "export async function updateCard(a, fields) {\n"
        "  const payload = {}\n"
        "  if ('product' in fields) payload.product = fields.product ?? null\n"
        "  // payload.commented = 1\n"
        "}\n"
        "export async function other() { payload.elsewhere = 2 }\n"
    )
    body = _ts_function_body(ts, "updateCard")
    keys = set(_PAYLOAD_ASSIGN_RE.findall(body or ""))
    ok(keys == {"product"}, "one function's keys, and not the next function's",
       f"got: {sorted(keys)}")
    ok("commented" not in keys, "and a key that only appears in a comment is not sent")
    ok(_ts_function_body(ts, "noSuchFunction") is None, "a missing function reads as None")

    # The exemption `views exposure` grants, and the ones it used to grant for nothing.
    # EVERY TITLE HERE IS A REAL COMMITTED TITLE, the way moves_across's ids are real
    # history: the two that qualify are the assertions D24 asked for by name, and the two
    # that do not are specs that were suppressing the question while proving the opposite.
    print("\na pooled-free claim is read off a test TITLE, never the spec body")

    proves = ("test('a pooled card is never on his screen — not on the walk, not in a "
              "search, not in a count', async ({\n")
    photo = "test('a pooled card never draws a photograph here', async ({ page }) => {\n"
    presence = ("test('the pooled row is a second no-bar shell, and it has not left', "
                "async ({ page }) => {\n")
    drawn = ("test('a pooled copy is drawn as pooled rather than as a position (D24)', "
             "async ({ page }) => {\n")

    ok(len(_pooled_absence_titles(proves)) == 1,
       "the Fulfillment view's assertion earns the exemption",
       f"got: {_pooled_absence_titles(proves)}")
    ok(len(_pooled_absence_titles(photo)) == 1,
       "and so does the review queue's, which cites this row by name")
    ok(_pooled_absence_titles(presence) == [],
       "THE MEASURED DEFECT: the spec proving the pooled row IS drawn earns nothing",
       "app/tests/gallery.spec.ts held /gallery out of the exposure list on that title")
    ok(_pooled_absence_titles(drawn) == [],
       "nor does a title whose claim is that a pooled copy IS drawn")

    # The body match this replaced, in the three shapes that really bought the exemption:
    # a fixture field, a passing comment, and a substring inside an unrelated word.
    body = ("/* four copies that were all LOCATED and all carried a slot number. */\n"
            "const fixture = { located: true }\n"
            "/* RELOCATED HERE FROM `run-panel.spec.ts` on 2026-08-30 */\n")
    ok(_pooled_absence_titles(body) == [],
       "a fixture field, a comment and the tail of RELOCATED assert nothing")
    ok(re.search(r"pooled|located", body, re.I) is not None,
       "which the old body test could not say, because this is exactly what it matched",
       "it was not word-bounded, so `RELOCATED` alone exempted /pricing")

    # SELF-CLEANING, the property the docstring claims: soften the title off the claim and
    # the route rejoins the list. Same spec, same subject, one word gone.
    ok(_pooled_absence_titles("test('a pooled card is not on his screen', () => {})\n") == [],
       "a title hedged from `never` to `not` stops earning it",
       "the row asks whether ANY render can hold a bearer instrument")
    ok(_pooled_absence_titles("") == [], "and a spec with no tests at all earns nothing")

    # Fail-closed on the forms this repo does not write: a parked proof must not go on
    # holding a route out of the exposure list.
    ok(_pooled_absence_titles(
        "test.skip('a pooled card is never on his screen', () => {})\n") == [],
       "a SKIPPED proof earns nothing")
    ok(_pooled_absence_titles('test("a pooled card is never drawn", () => {})\n')
       == ["a pooled card is never drawn"], "the double-quoted title form is read")
    ok(_pooled_absence_titles("test(`a pooled card is never drawn`, () => {})\n")
       == ["a pooled card is never drawn"], "and the backticked one")

    # `detector standing` and its `_dotted` helper are CUT (test-audit plan Q2, 2026-09-28).

    # The roster reader, and the vacuity this row nearly shipped with.
    print("\na reason roster is resolved through the constants beside it")
    ok(sorted(_roster("pipeline/variant.py", "LADDER_REASONS") or []) == [
        "ambiguous_no_signal", "detected_finish_not_stocked", "duplicate_condition",
        "metadata_not_stocked", "no_catalog_row", "rarity_claim_mismatch"],
       "the ladder's six resolve to their string values",
       f"got: {sorted(_roster('pipeline/variant.py', 'LADDER_REASONS') or [])}")
    ok(_roster("pipeline/variant.py", "NO_SUCH_TUPLE") is None,
       "a module with no such tuple reads as None, which is its own finding")
    ok("normal" not in (_roster("pipeline/variant.py", "LADDER_REASONS") or []),
       "and a finish sharing the constants' exact shape is not swept in",
       "eight of that file's fourteen constants are not reasons")

    print("\nthe roster declaration is not evidence that a reason is emitted")
    emitted = _emitted_names()
    ok("CARD_NOT_DETECTED" not in emitted,
       "a reason whose only load is the roster tuple counts as unemitted",
       "counting it made the row green for all thirteen the moment the rosters landed")
    ok("SET_AMBIGUOUS" in emitted,
       "while a reason with a real producer still counts")

    # THE FIXTURE'S SLUGS ARE COMPOSED, AND THIS BLOCK IS WHY THE RULE IS WRITTEN DOWN. They
    # were spelled out, borrowed from a real entry so the citations would resolve — and the
    # bootstrap claim substituted them, turning two of these into assertions about a NUMBER.
    # A claim is exhaustive text replacement; it cannot tell a fixture from prose. Composed
    # ids are out of its reach, and out of `decision ids in code`'s reach at the same time.
    print("\nan id is a slug until the merge claims it, and a slug is two segments")
    slug = "-" + "a-worked-example"
    step = "a-worked-example"
    ok(re.match(r"^" + _ID_SLUG + r"$", slug) is not None,
       "a two-segment slug is an id")
    ok(re.match(r"^" + _ID_SLUG + r"$", "-" + "pad") is None,
       "and a one-segment one is ordinary prose, not an entry")
    ok(_DECISION_RE.findall(f"see (D{slug}) and D" + "72") == [slug, "72"],
       "the citation scanner reads both forms out of one line",
       str(_DECISION_RE.findall(f"see (D{slug}) and D" + "72")))
    ok(_DECISION_RE.findall("the D" + "-pad on the controller") == [],
       "and reads neither out of a hyphenated English word")
    ok(is_slug(slug) and not is_slug("137"),
       "is_slug separates an unclaimed id from an allocated one")
    ok(_GATES_STEP_SLUG.findall(f"0. `step {step}` **T** — x") == [step],
       "a pending step is read out of its `0.` marker",
       str(_GATES_STEP_SLUG.findall(f"0. `step {step}` **T** — x")))
    ok(_GATES_STEP_SLUG.findall(f"7. `step {step}` **T** — x") == [],
       "and a marker that is not `0.` is a claimed step, read as its number")

    # EVERY PATTERN THAT READS A DECISION ID, AT THE DIGIT THAT USED TO END THEM (D16).
    # docs/debts/ recorded this as a TRIGGERED debt: seven patterns in this file and four
    # more across scripts/ capped at `[1-9][0-9]?`, so at the hundredth entry a heading stops
    # being a heading and a citation stops being a citation — and every row built on them
    # reports GREEN over a file it can no longer see. The debt named the discharge, and these
    # cases are its second half: a widen with nothing exercising the third digit is the same
    # silence one commit later.
    #
    # THE IDS ARE COMPOSED, NEVER WRITTEN, and that is not cuteness. `_DECISION_RE` scans
    # this file, so a literal three-digit id in a fixture is a citation of an entry that does
    # not exist and `decision ids in code` reports it. Composing is what lets a case name a
    # number the file has not reached yet — and it is the whole reason this section could not
    # simply be typed out.
    # Composing is how a case can name a number the file has not reached yet. It also keeps
    # the cases testing the BOUND rather than whatever is written today, which is the
    # opposite of `moves_across` above, where real history is what makes the data honest.
    print("\na decision id is three digits, and a ruff suppression is not one")

    past_end = f"D{100}"
    four_digits = f"D{1000}"
    leading_zero = f"D{0}"
    codes_past_end = f"C{100}"

    with tempfile.TemporaryDirectory() as tmp:
        entries = Path(tmp) / "DECISIONS.md"
        entries.write_text(
            "## D9 — One digit\n\n## D92 — Two digits\n\n"
            f"## {past_end} — Three digits\n\n"
            f"## {four_digits} — Four digits, which is not an id\n\n"
            f"## {leading_zero} — A leading zero, which is not an id\n",
            encoding="utf-8",
        )

        found = [ident for ident, _ in decision_heading_lines(entries, "D")]
        ok(found == ["D9", "D92", past_end], "the heading roster reads one, two and three digits", str(found))
        ok(four_digits not in found and leading_zero not in found,
           "and stops at three digits, and at a leading zero", str(found))

        slugged = Path(tmp) / "SLUGGED.md"
        unclaimed = "D" + "-an-unclaimed-entry"
        slugged.write_text(f"## D9 — One digit\n\n## {unclaimed} — An unclaimed entry\n",
                           encoding="utf-8")
        both = [ident for ident, _ in decision_heading_lines(slugged, "D")]
        ok(both == ["D9", unclaimed],
           "the heading roster reads a number and a slug out of one file", str(both))

    cited = _DECISION_RE.findall(f"this cites D70 and {past_end} in one line")
    ok(cited == ["70", "100"], "a two-digit citation still resolves, beside a three-digit one", str(cited))
    ok(not _DECISION_RE.findall(f"{four_digits} is not an id"), "four digits is not a citation")
    codes = _CODES_DECISION_RE.findall(f"the code track cites C7 and {codes_past_end}")
    ok(codes == ["7", "100"], "the C-track citation reads three digits too", str(codes))

    # THE COLLISION THAT KEPT THIS DEBT UNFIXED FOR THREE DAYS AFTER ITS TRIGGER FIRED. All
    # three suppressions below are real lines in server/, and they were harmless only because
    # the third digit was out of reach. Widening without `without_noqa` turns every one into
    # a citation of an entry that does not exist — measured, not predicted: with the strip
    # disabled and the cap at three, `decision ids in code` reported all three.
    #
    # These labels quote the directive on purpose. It means each label is itself a line
    # carrying a suppression, so the strip has to work for this section to survive its own
    # row — the case and its evidence are the same string.
    for line, label in (
        ("    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102",
         "`# noqa: D102` is a pydocstyle code, not a citation"),
        ("def _run_owes(manifest: dict) -> List[str]:  # noqa: D401",
         "`# noqa: D401` is not a citation either"),
        ("    if complex_thing():  # noqa: C901",
         "`# noqa: C901` is not a C-track citation"),
        ("from server import ports  # noqa: E402, F401",
         "a multi-code suppression is not a citation"),
    ):
        stripped = without_noqa(line)
        ok(not _DECISION_RE.findall(stripped) and not _CODES_DECISION_RE.findall(stripped),
           label, repr(stripped))

    # The directive goes; the sentence after it does not. Blanking the whole line would trade
    # the false positive for a blind spot, which is the trade this file exists to refuse —
    # and this repo really does write prose after the codes.
    with tempfile.TemporaryDirectory() as tmp:
        module = Path(tmp) / "sample.py"
        module.write_text(
            "from server import ports  # noqa: E402\n"
            "def redirect_request(self):  # noqa: D102\n"
            "    return None  # the renumber rule is D140's\n",
            encoding="utf-8",
        )
        ok(cited_decisions(module) == {"D140"},
           "`governed_by`'s reader excludes suppressions too — the row it feeds is MECHANICAL",
           str(cited_decisions(module)))

    kept = without_noqa("    except Exception as exc:  # noqa: BLE001 — 500 is for bugs, see D70")
    ok(_DECISION_RE.findall(kept) == ["70"],
       "a citation in the prose AFTER a suppression survives", repr(kept))
    ok(without_noqa("no directive here, just D140") == "no directive here, just D140",
       "a line with no suppression is returned unchanged")

    # THE SIBLING READERS, which the rows above depend on and which cannot report for
    # themselves. `decision structure` IS scripts/prose-guard.py's regex, and the
    # decision-context hook is what a session reads before editing a governed file. Both
    # carried the same cap; a widen that stopped at this file would have left the audit
    # reporting a heading count over a file the guard could not read, which is precisely the
    # measured symptom above.
    guard = _prose_guard()
    ok(
        guard is not None
        and bool(guard.ANY_H2_RE.match(f"## {past_end} — Three digits"))
        and bool(guard.HEADING_RE.match(f"## {past_end} — Three digits")),
        "scripts/prose-guard.py reads a three-digit heading",
    )
    ok(
        guard is not None and not guard.ANY_H2_RE.match(f"## {four_digits} — Four digits"),
        "and stops at three, like every pattern above it",
    )

    with tempfile.TemporaryDirectory() as tmp:
        entries = Path(tmp) / "DECISIONS.md"
        entries.write_text(
            f"## {past_end} — Three digits\n\n**A ruling long enough to be picked up.**\n",
            encoding="utf-8",
        )
        context = _sibling("decision-context.py")
        gists = context.decision_gists(path=entries) if context else {}
        ok(past_end in gists, "the decision-context hook resolves a three-digit entry", str(list(gists)))

    print("\nextractor finds real references")
    for line, expected in REAL_PATHS:
        found = path_candidates(line)
        ok(expected in found, expected, f"extracted: {found}")

    # The two forms with their own resolution rule. A `@` import that silently resolved to
    # nothing, or a `../` that escaped the repo, would make the whole check quietly vacuous.
    print("\nthe @ import and ../ forms resolve to real files")
    resolved = resolve_candidate("@docs/DESIGN.md", ROOT / "CLAUDE.md", tops)
    ok(
        resolved is not None and resolved.exists(),
        "@docs/DESIGN.md from CLAUDE.md",
        str(resolved),
    )
    resolved = resolve_candidate("@../docs/specs/code-cards.md", ROOT / "code-card-fork" / "CLAUDE.md", tops)
    ok(
        resolved is not None and resolved.exists(),
        "@../docs/specs/code-cards.md from code-card-fork/CLAUDE.md",
        str(resolved),
    )
    ok(
        resolve_candidate("../../../etc/passwd", ROOT / "code-card-fork" / "CLAUDE.md", tops) is None,
        "a ../ path escaping the repo is not ours to check",
    )
