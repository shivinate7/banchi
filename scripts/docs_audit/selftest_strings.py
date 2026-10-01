"""Self-test cases, strings rows. Called by `selftest.self_test`."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List

from .core import _sibling
from .strings import (
    NO_MECHANISM_EXEMPT_FILES,
    TYPED_INTERPUNCT_EXTRACT_ARGS,
    TYPED_INTERPUNCT_RULE,
    _offender_diff,
    _offender_growth,
    _offender_list_shape,
    UNKNOWN_NO_TOOLCHAIN,
    _run_user_strings,
    _user_strings_toolchain_missing,
    _typed_interpunct_found,
    _typed_interpunct_growth,
    _typed_interpunct_hits,
)


def run(ok) -> None:
    # THE PIN. `NO_MECHANISM_EXEMPT_FILES` is a set of exactly one entry, named in the
    # coordinator's 2026-09-13 ruling and nowhere else — a session widening it to a second
    # file must edit this literal, which fails `--self-test` (and therefore
    # `make audit-self-test`, which is in `make check`) until the assertion is updated to
    # match, on purpose and in a diff a reviewer sees. This is the mechanism, not a comment
    # promising one: mutate the set to add a second name and this line goes red.
    ok(frozenset({"Gallery.tsx"}) == NO_MECHANISM_EXEMPT_FILES,
       "the no-mechanism-on-screen exemption is pinned to exactly one file, `Gallery.tsx`",
       f"got: {sorted(NO_MECHANISM_EXEMPT_FILES)}")

    print("\ntyped interpunct: the two extractor widenings, and the ratchet's own arithmetic")
    with tempfile.TemporaryDirectory() as tmp_name:
        fixture_dir = Path(tmp_name)

        def written(name: str, body: str) -> Path:
            path = fixture_dir / name
            path.write_text(body)
            return path

        written(
            "PlainDot.tsx",
            "export function PlainDot() {\n"
            "  return <p>Box 2 · Section 1</p>\n"
            "}\n",
        )
        written(
            "NoticeCodeDot.tsx",
            "export function NoticeCodeDot() {\n"
            '  return <Notice code="reason · code">Held back.</Notice>\n'
            "}\n",
        )
        written(
            "JoinLiteral.tsx",
            "import type { ReactNode } from 'react'\n"
            "const whole = (body: string): ReactNode => <>{body}</>\n"
            "export function JoinLiteral() {\n"
            "  const parts = ['Box 2', 'Section 1']\n"
            "  return whole(parts.join(' · '))\n"
            "}\n",
        )
        written(
            "CommaJoin.tsx",
            "export function CommaJoin() {\n"
            "  const parts = ['a', 'b']\n"
            "  return <p>{parts.join(', ')}</p>\n"
            "}\n",
        )

        # No node or app/node_modules/typescript is a read that could not run: unknown,
        # never a crash and never an ok. The node arm below runs whenever the toolchain is present.
        if _user_strings_toolchain_missing():
            ok.unknown(f"the extractor arm of this self-test did not run: {UNKNOWN_NO_TOOLCHAIN}")
        else:
            # THE DEFAULT CALL — no widening flags, exactly what `no mechanism on screen` uses —
            # proves the two new channels stay OFF unless a caller asks for them, which is the
            # whole argument for why widening them does not touch that row's own fixtures above.
            default_strings = _run_user_strings(["--dir", str(fixture_dir)])
            ok(default_strings is not None, "the extractor runs, unwidened, over the fixture tree")
            if default_strings is not None:
                default_hits = {f.where.split(":")[0].split("/")[-1] for f in _typed_interpunct_hits(default_strings)}
                ok("PlainDot.tsx" in default_hits,
                   "a middle dot in plain JSX text is caught with NO widening at all")
                ok("NoticeCodeDot.tsx" not in default_hits,
                   "`Notice`'s `code` prop is NOT caught without `--include-code-attr` — the "
                   "widening is opt-in, so `no mechanism on screen`'s own call is untouched")
                ok("JoinLiteral.tsx" not in default_hits,
                   "a `.join(' · ')` call is NOT caught without `--join-literals` — the same "
                   "opt-in argument, for the other widening")

            # THE ROW'S OWN CALL — `TYPED_INTERPUNCT_EXTRACT_ARGS`, both widenings together,
            # exactly what `check_typed_interpunct` passes in production.
            widened_strings = _run_user_strings(["--dir", str(fixture_dir), *TYPED_INTERPUNCT_EXTRACT_ARGS])
            ok(widened_strings is not None, "the extractor runs, widened, over the fixture tree")
            if widened_strings is not None:
                widened_hits = {f.where.split(":")[0].split("/")[-1] for f in _typed_interpunct_hits(widened_strings)}
                ok("PlainDot.tsx" in widened_hits,
                   "plain JSX text is still caught once widened")
                ok("NoticeCodeDot.tsx" in widened_hits,
                   "`--include-code-attr` catches a typed dot inside `Notice`'s own `code` prop — "
                   "extractor addition (a)")
                ok("JoinLiteral.tsx" in widened_hits,
                   "`--join-literals` catches `parts.join(' · ')` fed to a local helper "
                   "(`PositionLabel.tsx`'s `whole()` shape) — extractor addition (b)/(c), the "
                   "direct-literal check for a call the AST walk cannot see through by reference")
                ok("CommaJoin.tsx" not in widened_hits,
                   "a `.join(', ')` call is extracted (the literal argument reaches the walk) but "
                   "carries no interpunct character, so it is not a HIT — the widening reads every "
                   "`.join(<literal>)` separator, and the character test is what decides a finding")

            # ONE ENTRY EXCUSES ONE STRING IN ONE NAMED FUNCTION. The review's probe: a listed bare
            # `·` join removed from one component, and a new one typed in another, stayed green
            # while the key was the string alone.
            def scoped(body: str) -> Dict[str, Dict[str, List[str]]]:
                scope_dir = fixture_dir / "scoped"
                scope_dir.mkdir(exist_ok=True)
                (scope_dir / "Two.tsx").write_text(body)
                got = _run_user_strings(["--dir", str(scope_dir), *TYPED_INTERPUNCT_EXTRACT_ARGS])
                return _typed_interpunct_found(got or [])

            two_components = (
                "export function First(p: { a: string[] }) {\n"
                "  return <p>{p.a.join(' · ')}</p>\n"
                "}\n"
                "export function Second(p: { a: string[] }) {\n"
                "  return <p>{p.a.join(', ')}</p>\n"
                "}\n"
                "const helper = (a: string[]) => a.join(' · ')\n"
            )
            before = scoped(two_components)
            ok(before == {"Two.tsx": {TYPED_INTERPUNCT_RULE: ["First: ·", "helper: ·"]}},
               "each typed dot is keyed by the named function around it: a component, or an "
               "arrow bound to a name", f"{before}")
            moved_dot = scoped(two_components.replace("join(' · ')}</p>", "join(', ')}</p>", 1)
                               .replace("join(', ')}</p>\n}\nconst", "join(' · ')}</p>\n}\nconst"))
            unlisted, stale = _offender_diff(moved_dot, before)
            ok(unlisted == [("Two.tsx", TYPED_INTERPUNCT_RULE, "Second: ·")]
               and stale == [("Two.tsx", TYPED_INTERPUNCT_RULE, "First: ·")],
               "RED: the listed dot removed from one component and the same bare `·` typed in "
               "another is a NEW offender and a stale entry, not a pass", f"{unlisted} {stale}")
            ok(_offender_diff(scoped(two_components.replace("First(p", "First(q")
                                     .replace("p.a.join(' · ')", "q.a.join(' · ')")), before)
               == ([], []),
               "an edit elsewhere in the same function moves nothing: the key is the function's "
               "name, never a line")

            nested = scoped(
                "export function One(p: { a: string[] }) {\n"
                "  const sep = (a: string[]) => a.join(' · ')\n"
                "  return <p>{sep(p.a)}</p>\n"
                "}\n"
                "export function Two(p: { a: string[] }) {\n"
                "  const sep = (a: string[]) => a.join(' · ')\n"
                "  return <p>{sep(p.a)}</p>\n"
                "}\n")
            ok(nested == {"Two.tsx": {TYPED_INTERPUNCT_RULE: ["One.sep: ·", "Two.sep: ·"]}},
               "two local helpers with one name in two functions get two keys: a nested scope "
               "is qualified by the scope around it", f"{nested}")

            # A FUNCTION RENAME MOVES ITS ENTRIES, the way a file rename does. The rename is red
            # until the entries are re-keyed. Re-keyed, it is not growth, because growth drops
            # the scope (`typed_interpunct_growth_key`).
            renamed_fn = scoped(two_components.replace("function First(", "function Renamed("))
            unlisted, stale = _offender_diff(renamed_fn, before)
            ok(len(unlisted) == 1 and len(stale) == 1,
               "RED: a function renamed and its entry left alone is one unlisted, one stale",
               f"{unlisted} {stale}")
            dot_rules = {TYPED_INTERPUNCT_RULE}
            ok(_offender_diff(renamed_fn, renamed_fn) == ([], [])
               and _typed_interpunct_growth(before, renamed_fn, dot_rules, []) == ([], []),
               "T7b: the entry re-keyed to the new function name is not growth — the same "
               "string, the same number of times, in the same file")
            refused, _ = _offender_growth(before, renamed_fn, dot_rules, dot_rules)
            ok(len(refused) == 1,
               "RED without the growth key: counted with its scope, the re-key reads as growth",
               f"{refused}")
            more = {"Two.tsx": {TYPED_INTERPUNCT_RULE: before.get("Two.tsx", {}).get(TYPED_INTERPUNCT_RULE, [])
                                + ["Second: ·"]}}
            refused, _ = _typed_interpunct_growth(before, more, dot_rules, [])
            ok(len(refused) == 1,
               "RED: one more copy of a listed string in the same file is growth",
               f"{refused}")

    # DOT GROWTH IS PER FILE, with a file rename mapped back through git's rename pairs. The
    # second review's X1 and X2: counted over the whole list, a dot fixed in one file excused
    # a new dot with the same string in another file, or in a brand-new one.
    print("\ntyped interpunct: growth per file, and a rename maps back to its old path")
    R4 = TYPED_INTERPUNCT_RULE
    rules4 = {R4}
    base4 = {"app/src/Runs.tsx": {R4: ["selectionLine: ·"]},
             "app/src/Bar.tsx": {R4: ["Bar: ·"]},
             "app/src/Gallery.tsx": {R4: [f"Gallery: Box {n} · Card {n}" for n in range(45)]}}
    fixed_there = {k: v for k, v in base4.items() if k != "app/src/Runs.tsx"}
    x1 = {**fixed_there, "app/src/Bar.tsx": {R4: ["Bar: ·", "Bar: ·"]}}
    refused, _ = _typed_interpunct_growth(base4, x1, rules4, [])
    ok(len(refused) == 1 and "app/src/Bar.tsx" in refused[0],
       "RED, X1: a dot fixed in one file does not excuse a new one with the same string in "
       "another listed file", f"{refused}")
    x2 = {**fixed_there, "app/src/Brand.tsx": {R4: ["Brand: ·"]}}
    refused, _ = _typed_interpunct_growth(base4, x2, rules4, [])
    ok(len(refused) == 1 and "app/src/Brand.tsx" in refused[0],
       "RED, X2: nor one in a brand-new file — a new file starts clean", f"{refused}")
    renamed_file = {("app/src/RunsX.tsx" if k == "app/src/Runs.tsx" else k): v
                    for k, v in base4.items()}
    ok(_typed_interpunct_growth(base4, renamed_file, rules4,
                                [("app/src/Runs.tsx", "app/src/RunsX.tsx")]) == ([], []),
       "T5: a file git renamed, its entries moved with it, is not growth")
    refused, _ = _typed_interpunct_growth(base4, renamed_file, rules4, [])
    ok(len(refused) == 1,
       "a rename git does not see reads as a new file and fails closed", f"{refused}")
    gallery_renamed = {**base4, "app/src/Gallery.tsx": {R4: [
        e.replace("Gallery: ", "KitGallery: ", 1) for e in base4["app/src/Gallery.tsx"][R4]]}}
    ok(_typed_interpunct_growth(base4, gallery_renamed, rules4, []) == ([], []),
       "T8b: a component renamed, its 45 entries re-keyed to the new name, is not growth")

    # The rename pairs come from `offenders-prune.py:git_renames`, shared rather than copied.
    prune = _sibling("offenders-prune.py")
    ok(prune is not None and hasattr(prune, "git_renames"),
       "the row reads git's rename pairs through the pruner's own `git_renames`")
    with tempfile.TemporaryDirectory() as tmp_name:
        repo = Path(tmp_name)

        def run_git(*args: str) -> None:
            subprocess.run(["git", *args], cwd=str(repo), check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        run_git("init", "-q")
        run_git("config", "user.email", "selftest@example.invalid")
        run_git("config", "user.name", "selftest")
        (repo / "Runs.tsx").write_text("".join(f"export const line{i} = {i}\n" for i in range(30)))
        run_git("add", "-A")
        run_git("commit", "-q", "-m", "base")
        run_git("mv", "Runs.tsx", "RunsX.tsx")
        pairs = prune.git_renames(repo, "HEAD") if prune is not None else []
        ok(pairs == [("Runs.tsx", "RunsX.tsx")],
           "and a staged `git mv` in a throwaway repository is one rename pair", f"{pairs}")

    # THE SHRINKING LIST'S OWN ARITHMETIC (D280), in memory: plain
    # dicts in, findings out, no file read and none written (D18). Each arm below is one of the
    # three failures the list exists for, or one of the two things it must let through.
    print("\ntyped interpunct: the shrinking list, in memory")
    R = TYPED_INTERPUNCT_RULE
    LISTED = {"app/src/A.tsx": {R: ["Box 2 · Section 1", "Box 2 · Section 1", "a · b"]}}

    ok(_offender_diff(LISTED, LISTED) == ([], []),
       "the tree and the list agree — nothing unlisted, nothing stale")

    grew_in_file = {"app/src/A.tsx": {R: ["Box 2 · Section 1", "Box 2 · Section 1", "a · b",
                                          "c · d"]}}
    unlisted, stale = _offender_diff(grew_in_file, LISTED)
    ok(unlisted == [("app/src/A.tsx", R, "c · d")] and not stale,
       "RED: a NEW typed dot in a file the list already names is unlisted — the file being "
       "listed excuses only the strings it lists, never a count of them",
       f"{unlisted} {stale}")

    swapped = {"app/src/A.tsx": {R: ["Box 2 · Section 1", "Box 2 · Section 1", "c · d"]}}
    unlisted, stale = _offender_diff(swapped, LISTED)
    ok(unlisted == [("app/src/A.tsx", R, "c · d")] and stale == [("app/src/A.tsx", R, "a · b")],
       "RED both ways: one dot fixed and a new one typed in the same file is still a new "
       "offender AND a stale entry. The pinned count this replaced read that as no change",
       f"{unlisted} {stale}")

    one_fixed = {"app/src/A.tsx": {R: ["Box 2 · Section 1", "a · b"]}}
    unlisted, stale = _offender_diff(one_fixed, LISTED)
    ok(not unlisted and stale == [("app/src/A.tsx", R, "Box 2 · Section 1")],
       "RED: a listed entry that matches nothing now is stale — one copy of a string listed "
       "twice was fixed, so one of its two entries must go", f"{unlisted} {stale}")

    copied = {"app/src/A.tsx": {R: ["Box 2 · Section 1"] * 3 + ["a · b"]}}
    unlisted, _ = _offender_diff(copied, LISTED)
    ok(unlisted == [("app/src/A.tsx", R, "Box 2 · Section 1")],
       "RED: a THIRD copy of a string listed twice is unlisted — an identity is listed once per "
       "occurrence, so a copy never hides behind the first", f"{unlisted}")

    new_file = {**LISTED, "app/src/B.tsx": {R: ["x · y"]}}
    unlisted, _ = _offender_diff(new_file, LISTED)
    ok(unlisted == [("app/src/B.tsx", R, "x · y")],
       "RED: a typed dot in a file the list does not name at all is unlisted", f"{unlisted}")

    rules = {R}
    refused, allowed = _offender_growth(LISTED, grew_in_file, rules, rules)
    ok(len(refused) == 1 and "c · d" in refused[0] and not allowed,
       "RED: an entry the merge-base list did not hold is GROWTH, and the rule exists at the "
       "merge-base, so it is refused", f"{refused} {allowed}")
    ok(_offender_growth(LISTED, one_fixed, rules, rules) == ([], []),
       "a list that only lost entries is not growth")
    moved = {"app/src/Renamed.tsx": LISTED["app/src/A.tsx"]}
    ok(_offender_growth(LISTED, moved, rules, rules) == ([], []),
       "a file renamed with its entries is not growth — growth is counted across the whole "
       "list, so a `git mv` moves its debt and adds none")
    copied_across = {**LISTED, "app/src/B.tsx": {R: ["a · b"]}}
    refused, _ = _offender_growth(LISTED, copied_across, rules, rules)
    ok(len(refused) == 1 and "a · b" in refused[0],
       "RED: a listed string copied into a SECOND file is growth — the identity now occurs "
       "once more than the merge-base allowed", f"{refused}")

    _, _, errors = _offender_list_shape({"files": {"app/src/A.tsx": {R: ["a · b"]}}}, rules)
    ok(any("lane" in e for e in errors),
       "an entry with no lane is refused: every offender names the lane that owes the fix",
       f"{errors}")
    _, _, errors = _offender_list_shape(
        {"files": {"app/src/A.tsx": {"lane": "x", "dots": ["a · b"]}}}, rules)
    ok(any("dots" in e for e in errors),
       "a misspelt rule key is refused rather than read as covering nothing", f"{errors}")
    ok(_offender_list_shape(
           {"files": {"app/src/A.tsx": {"lane": "kit", R: ["a · b"]}}}, rules)[2] == [],
       "and a well-formed entry reads back with no error, so the refusals above are about the "
       "shape and not a broken reader")
