"""Doc hygiene, route rosters, deletions, the seal, the verdict file and positional references."""

from __future__ import annotations

import ast
import io
import os
import re
import tokenize
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .core import (
    ADVISORY,
    ALLOWLIST,
    Finding,
    MECHANICAL,
    ROOT,
    Report,
    TS_COMMENT,
    _sibling,
    _strip_ts_comments,
    _walk,
    exists,
    glob_files,
    python_files,
    read,
    rel,
)
from .design import _POSITIONAL_RE
from .records import _corpus, decisions_text
from .screens import APP_TESTS, APP_TSX

# --------------------------------------------------------------- doc hygiene


# An editor's instruction, written to a session and committed as prose. The real one read
# "Leave lines 37-38 exactly as they are. Insert a blank line and this blockquote after line
# 38" — and the edit that pasted it DELETED the sentence it was meant to preserve, leaving a
# decapitated clause behind. Anchored at the start of a line and requiring a literal line
# NUMBER, because "insert a blank line" is ordinary English and "insert ... after line 38" is
# not: prose about a document does not cite the document's own line numbers.
_EDITOR_INSTRUCTION = re.compile(
    r"^\s*(?:Leave|Insert|Replace|Delete|Add|Append|Keep)\b[^.]{0,80}\b(?:line|lines)\s+\d+",
    re.I,
)

_DOC_LINE_CITATION = re.compile(
    r"`([A-Za-z0-9_./-]+\.(?:py|ts|tsx|css|json|sh|txt|md)):(\d+)"
)


def check_doc_hygiene(report: Report, docs: List[Path]) -> None:
    """Three ways a markdown file is malformed as a DOCUMENT, independent of what it claims.

    Every other row here reads a doc's assertions and checks them against the code. This one
    reads the file as a file, and it exists because the 2026-08-30 prose sweep found two
    defects that every row was structurally unable to see: no assertion was wrong, so nothing
    asked.

    THE THREE, all decidable on the committed tree alone:

      an editor's instruction committed as prose  `docs/specs/capture-server.md` carried
          "Leave lines 37-38 exactly as they are. Insert ... after line 38" in the middle of
          a paragraph, from 2026-08-22. The paste that put it there deleted the line it was
          preserving, so the paragraph also lost "Do not add a harness test for the server in
          this plan, and do not register" and ended mid-clause. Green for eight days.

      two level-1 headings  a research spec once was two documents in one file, the
          second titled "PKMNSCAN UI: final design recommendation". A reader's table of
          contents, this project's own heading parsers, and the status line that governs a
          file all assume one title.

      a line citation past the end of its file  a `ReviewQueue.css` line number outliving the line it
          named. The `paths` row proves the FILE resolves and stops there, so the number is
          unchecked; this catches only the provable half, where the file is shorter than the
          number. A citation pointing at the wrong line of a long-enough file is invisible
          here and is `docs/debts/`'s to carry.

    ADVISORY, and the severity is the argument. Each condition is provably true of the tree,
    which is D16's test for a blocking row — but "true" and "wrong" part company on the second
    one: a file that deliberately carries two titles is a judgement, not a defect, and a
    blocking row would settle it by fiat. The first condition alone would qualify to block and
    is not split out, because a row that fires once every eight days does not need two
    severities and `make check` puts an advisory in front of a person anyway. **What would
    earn it a promotion: a second instance of the instruction case reaching main.**

    Fenced blocks are skipped for the heading and instruction conditions — a `#` inside one is
    a shell comment and prose inside one is a quotation. The audit's own convention of quoting
    verbatim doc text in blockquotes rather than fences (`docs/specs/audit-retirement.md` §0)
    is what makes that safe.
    """
    findings: List[Finding] = []
    for doc in docs:
        titles = 0
        fenced = False
        for number, line in enumerate(read(doc).splitlines(), start=1):
            if line.startswith("```"):
                fenced = not fenced
                continue
            if fenced:
                continue
            if line.startswith("# "):
                titles += 1
                if titles == 2:
                    findings.append(
                        Finding(
                            f"{rel(doc)}:{number}",
                            "a second level-1 heading — one file, two document titles. "
                            "Demote it, or split the file.",
                        )
                    )
            if _EDITOR_INSTRUCTION.match(line):
                findings.append(
                    Finding(
                        f"{rel(doc)}:{number}",
                        "reads as an instruction to an editor, committed as prose: "
                        f"{line.strip()[:70]!r}. Check what it replaced.",
                    )
                )
            for match in _DOC_LINE_CITATION.finditer(line):
                target = ROOT / match.group(1)
                if not target.is_file():
                    continue
                # A LINE CITATION OF `docs/DECISIONS.md` MEANT THE CORPUS, and that file is a
                # 38-line stub since the split. Measured against the stub, eight true
                # citations written before the split read as pointing past the end — D149's
                # four among them, landed an hour earlier. The author meant the entries, so
                # the entries are what the number is checked against. Same ruling as the
                # relative-path case in `resolve_candidate`, and for the same reason: the
                # entries' bytes are unchanged by design, so the alternative is editing prose
                # inside a change whose whole claim is that it edited none.
                #
                # WHAT THIS RESTORES IS EXACTLY WHAT EXISTED BEFORE — this row only ever
                # proved the file was long enough, never that the line still says what the
                # citation claims. A number drifting under an edit was invisible here before
                # the split and is invisible now; docs/debts/ carries that half.
                if match.group(1) == "docs/DECISIONS.md":
                    total = len(decisions_text().splitlines())
                    if total and int(match.group(2)) <= total:
                        continue
                total = len(target.read_text(errors="replace").splitlines())
                if int(match.group(2)) > total:
                    findings.append(
                        Finding(
                            f"{rel(doc)}:{number}",
                            f"cites {match.group(1)}:{match.group(2)}, "
                            f"but that file has {total} lines.",
                        )
                    )
    report.add(
        "doc hygiene",
        ADVISORY,
        findings,
        f"{len(docs)} markdown files well-formed as documents",
        scanned=len(docs),
    )


# `ROUTE-ROSTER all` or `ROUTE-ROSTER hotkey`, in a comment directly above the literal it
# governs. A marker rather than a filename list inside this script: the spec that pins the
# routes is the file that has to say so, and a registry here would be a second list to keep
# in step with the first — which is the whole defect this check exists for, relocated.
ROSTER_MARK = re.compile(r"ROUTE-ROSTER\s+(all|hotkey)\b")

# `#/`, `#/runs`, and the `/#/runs` form `page.goto` takes. Normalised to the first.
ROUTE_HASH = re.compile(r"'/?(#/[a-z-]*)'")

# How many pinned route hashes make a file a roster. Two is a spec that opens on its own
# screen and one other; three is a list of screens somebody typed out, and a list of
# screens somebody typed out is the thing that goes stale.
ROSTER_FLOOR = 3


def _balanced(text: str, start: int) -> str:
    """The literal beginning at `start`, to its matching bracket. '' if unbalanced.

    Bracket-matched rather than regexed to the next `]`: `VIEW` below is an object of
    objects in every version of this file that has more than one shape, and a non-greedy
    match to the first closer would silently read half a roster and pass on the half.
    """
    pairs = {"[": "]", "{": "}"}
    opener = text[start]
    closer = pairs.get(opener)
    if closer is None:
        return ""
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return ""


def app_routes() -> Tuple[List[Tuple[str, str, bool]], List[str], List[Finding]]:
    """`App.tsx`'s ROUTES table as (path, group, has hotkey), plus GROUP_ORDER.

    Read from the source rather than from a browser, because this check runs at a commit
    and `make design-check` starts a browser (docs/GATES.md's contract keeps that off the
    hook path). The table is the register either way — `App.tsx` routes from it, renders
    its nav from it and derives its Cmd-arrow ring from it, which is the property that
    makes reconciling a test's hand-typed copy against it meaningful.
    """
    findings: List[Finding] = []
    if not exists(APP_TSX):
        return [], [], [Finding(rel(APP_TSX), "is missing, so no route roster can be checked.")]

    source = _strip_ts_comments(read(APP_TSX))

    anchor = re.search(r"const\s+ROUTES\s*:[^=]*=\s*", source)
    if anchor is None:
        return [], [], [
            Finding(
                rel(APP_TSX),
                "defines no `const ROUTES` this reader can find, so the specs below are\n"
                "reconciled against nothing. Reconcile this extractor with the table.",
            )
        ]
    table = _balanced(source, anchor.end())
    if not table:
        return [], [], [Finding(rel(APP_TSX), "`const ROUTES` does not close — unbalanced brackets?")]

    rows: List[Tuple[str, str, bool]] = []
    index = 0
    while True:
        opening = table.find("{", index)
        if opening == -1:
            break
        row = _balanced(table, opening)
        if not row:
            break
        index = opening + len(row)
        path = re.search(r"path:\s*'([^']*)'", row)
        group = re.search(r"group:\s*'([^']*)'", row)
        if path is None or group is None:
            findings.append(
                Finding(
                    rel(APP_TSX),
                    f"a ROUTES row carries no {'path' if path is None else 'group'}: {row[:60]}…",
                )
            )
            continue
        rows.append((path.group(1), group.group(1), "hotkey:" in row))

    # THE NAV'S ORDER, UNDER EITHER OF THE TWO NAMES IT HAS HAD. It was `GROUP_ORDER`, a
    # list of bare strings; the Banchi shell draws from `GROUPS`, a list of `{id, label}`
    # objects, because a group now carries a heading as well as an order. Reading only the
    # old name did not fail loudly — it returned NO groups, which made `expected_rosters()`
    # hand back an empty dict, which made the `route rosters` row skip every roster a spec
    # had pinned. A check that stops checking is worse than one that fails, so both spellings
    # are read and the absence of both is still a finding.
    groups: List[str] = []
    order = re.search(r"const\s+GROUP_ORDER\s*:[^=]*=\s*", source)
    if order is not None:
        groups = re.findall(r"'([^']*)'", _balanced(source, order.end()))
    if not groups:
        modern = re.search(r"const\s+GROUPS\s*:[^=]*=\s*", source)
        if modern is not None:
            # `{ id: 'work', label: 'Workflow' }` — the id is the group, the label is chrome.
            groups = re.findall(r"id:\s*'([^']*)'", _balanced(source, modern.end()))
    if not groups:
        findings.append(
            Finding(rel(APP_TSX), "defines no readable `GROUP_ORDER` or `GROUPS`, so a nav ORDER cannot be derived.")
        )
    # A group the shell deliberately keeps out of the nav list is still a drawn group as far
    # as this row is concerned: its routes are reached from the sidebar foot or the command
    # palette. `App.tsx:OFF_NAV` is where that intent is declared, so it is read rather than
    # guessed. Absent, nothing is added and the row behaves exactly as it did.
    off = re.search(r"const\s+OFF_NAV\s*:[^=]*=\s*", source)
    if off is not None:
        groups = list(groups) + [g for g in re.findall(r"'([^']*)'", _balanced(source, off.end())) if g not in groups]
    return rows, groups, findings


def expected_rosters() -> Tuple[Dict[str, List[str]], List[Finding]]:
    """The two rosters a spec may pin, in the order the nav draws them.

    `all` is every registered route; `hotkey` is the Cmd-arrow ring, which `App.tsx`
    itself derives as `hotkey !== undefined` over GROUP_ORDER-then-table. Both are built
    here the same way the shell builds them, so a re-ordered table moves both together.
    """
    rows, groups, findings = app_routes()
    if not rows or not groups:
        return {}, findings
    drawn = [row for group in groups for row in rows if row[1] == group]
    missing = [row[0] for row in rows if row[1] not in groups]
    if missing:
        findings.append(
            Finding(
                rel(APP_TSX),
                "these routes carry a group GROUP_ORDER does not draw, so the nav renders "
                f"no link for them: {', '.join(missing)}",
            )
        )
    return (
        {
            "all": [f"#{path}" for path, _, _ in drawn],
            "hotkey": [f"#{path}" for path, _, keyed in drawn if keyed],
        },
        findings,
    )


def _route_prose_findings() -> List[Finding]:
    """The route lists in prose, against `ROUTES`, both ways.

    README's `## Usage` table must name every route, and mark `Off-nav` on exactly the
    `aside` routes. A route added, dropped or moved off the nav fails until the prose follows.
    CLAUDE.md no longer lists routes: `ROUTES` is the one roster.
    """
    rows, _, _ = app_routes()
    if not rows:
        return []
    want = {f"#{path}" for path, _, _ in rows}
    aside = {f"#{path}" for path, group, _ in rows if group == "aside"}
    out: List[Finding] = []

    def diff(where: str, what: str, have: set, need: set) -> None:
        gone, extra = sorted(need - have), sorted(have - need)
        if gone or extra:
            out.append(Finding(
                where,
                f"{what} does not match App.tsx's ROUTES.\n"
                + (f"missing: {', '.join(gone)}\n" if gone else "")
                + (f"not a route here: {', '.join(extra)}" if extra else ""),
            ))

    readme = ROOT / "README.md"
    if exists(readme):
        text = read(readme)
        part = text.split("## Usage", 1)[-1]
        table = re.findall(r"^\|[^|\n]*\|\s*`(#/[^`]*)`\s*\|(.*)$", part, re.M)
        diff(rel(readme), "the `## Usage` route table", {r for r, _ in table}, want)
        diff(rel(readme), "the table's `Off-nav` rows", {r for r, rest in table if "Off-nav" in rest}, aside)
    return out


# CLAUDE.md's "Codex reads this same file" paragraph names these four links.
AGENT_LINKS: Tuple[Tuple[str, str], ...] = (
    ("AGENTS.md", "CLAUDE.md"),
    (".agents/skills", "../.claude/skills"),
    ("code-card-fork/AGENTS.md", "CLAUDE.md"),
    ("code-card-fork/CLAUDE.md", "../CLAUDE.md"),
)


def check_agent_links(report: Report) -> None:
    """Each link CLAUDE.md names is a relative symlink to its stated target."""
    findings: List[Finding] = []
    for link, target in AGENT_LINKS:
        path = ROOT / link
        if not path.is_symlink():
            findings.append(Finding(link, f"is not a symlink; CLAUDE.md says it links to `{target}`."))
        elif os.readlink(path) != target:
            findings.append(Finding(link, f"links to `{os.readlink(path)}`; CLAUDE.md says `{target}`."))
    report.add(
        "agent links",
        MECHANICAL,
        findings,
        f"{len(AGENT_LINKS)} relative symlinks resolve to CLAUDE.md or .claude/skills",
        scanned=len(AGENT_LINKS),
    )


TEST_ROSTER_FLOOR = 90  # non-vacuity: the roster held 95 files when this row was built.


def check_test_purposes(report: Report) -> None:
    """Every test file states what it protects, and docs/TESTS.md says the same as the files.

    `scripts/tests_page.py` owns the roster, the header format and the page. This row
    only READS it (D18): it never writes the page, it regenerates in memory and compares. A
    test file with no `Protects:` line, a `Governs:` id that resolves to no entry, a file no
    area names, or a page that differs from the regenerated one is a finding.
    """
    mod = _sibling("tests_page.py")
    if mod is None:
        report.add("test purposes", MECHANICAL,
                   [Finding("scripts/tests_page.py", "is missing or unreadable; the test roster cannot be read.")],
                   "", scanned=0)
        return
    findings: List[Finding] = []
    corpus = _corpus()
    known = set(corpus.idents()) if corpus is not None else set()
    files = mod.roster()
    if len(files) < TEST_ROSTER_FLOOR:
        findings.append(Finding("scripts/tests_page.py", f"found {len(files)} test files, under the floor of {TEST_ROSTER_FLOOR}; the roster globs no longer reach the tests."))
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        head = mod.header(path)
        if not head.get("Protects", "").strip():
            findings.append(Finding(rel, "has no `Protects:` line in its first 80 lines. Add one plain sentence saying what the test protects."))
        for ident in mod.governs(head):
            if known and ident not in known:
                findings.append(Finding(rel, f"`Governs:` cites `{ident}`, which is no decision entry."))
        if mod.area_of(path) == mod.UNFILED:
            findings.append(Finding(rel, "names no area. Add a rule to `AREAS` in scripts/tests_page.py."))
    page = mod.PAGE
    if not page.exists():
        findings.append(Finding("docs/TESTS.md", "is missing. Run `make tests-page ARGS=--write`."))
    elif page.read_text(encoding="utf-8") != mod.render():
        findings.append(Finding("docs/TESTS.md", "is stale against the test headers. Run `make tests-page ARGS=--write`."))
    report.add(
        "test purposes",
        MECHANICAL,
        findings,
        f"{len(files)} test files carry a Protects line, and docs/TESTS.md matches them",
        scanned=len(files),
    )


def check_readme_blocks(report: Report) -> None:
    """README's `<!-- gen:NAME -->` blocks equal what `scripts/readme_gen.py` renders from the source.

    Reads only (D18). A stale block is a finding; `python3 scripts/readme_gen.py --write` fixes it.
    """
    mod = _sibling("readme_gen.py")
    findings: List[Finding] = []
    blocks = 0
    if mod is None:
        findings.append(Finding("scripts/readme_gen.py", "is missing or unreadable."))
    else:
        text = read(ROOT / "README.md")
        blocks = len(mod.BLOCK.findall(text))
        if blocks == 0:
            findings.append(Finding("README.md", "has no generated block; the `routes` block is gone."))
        if mod.render(text) != text:
            findings.append(Finding("README.md", "a generated block is stale. Run `python3 scripts/readme_gen.py --write`."))
    report.add("readme blocks", MECHANICAL, findings, f"{blocks} generated block(s) match their source", scanned=blocks)


def check_route_rosters(report: Report) -> None:
    """A hand-typed list of routes in a spec, against `App.tsx`'s own table.

    **The failure this exists for, in full, because it happened twice inside two days.**
    `app/tests/cursor.spec.ts` swept "every route" off seven hashes somebody typed out. D69
    added `#/orders` and `#/shipping`; D70 added `#/codes`. None of the three was added to
    that list, so three screens were asserted by nothing — and the spec's own header spends
    a paragraph explaining that a pinned roster is exactly the defect it must not have. The
    list was four lines under the warning. `make design-check` stayed green throughout,
    because a roster that is missing a route does not fail: it simply walks the routes it
    has. `app/tests/nav.spec.ts` pinned the same ring and did go red on D70 — but only
    because its "never a wrap" case happened to step off the end of the list it knew about,
    which is luck rather than coverage.

    **So the guard is at the commit and not in a browser.** `docs/GATES.md`'s contract keeps
    Playwright off the hook path, and this needs no browser: `App.tsx` is the register — it
    routes from ROUTES, renders the nav from ROUTES, and derives the Cmd-arrow ring from
    ROUTES — so a text reconciliation against it answers the question a browser would.

    **Declared, not sniffed.** A spec that pins three or more routes has to say WHICH roster
    it is pinning, in a `ROUTE-ROSTER all` or `ROUTE-ROSTER hotkey` comment above the
    literal, and the literal is then checked in order against the table. Sniffing every
    array of hashes would be the check inventing an intent the file never stated: `#/gallery`
    appears in nav.spec.ts as a route the ring deliberately CANNOT reach, and a check that
    read it as a missing ring member would be wrong in the direction that gets a guard
    disabled. Three is the floor because two is a spec that opens on its own screen and one
    other, and three is a list somebody typed.

    **A spec that derives its roster trips nothing, which is the point.** `cursor.spec.ts`
    now reads the nav strip at run time, so it pins one hash — the way in — and this check
    has nothing to reconcile there. That is the better fix and this row does not replace it;
    it covers the specs where a pinned list is deliberate, and it catches a pinned list
    creeping back into one where it is not.
    """
    expected, findings = expected_rosters()
    specs = sorted(glob_files(APP_TESTS, "*.spec.ts"), key=rel)

    marked = 0
    for spec in specs:
        code = _strip_ts_comments(read(spec))
        pinned = {match for match in ROUTE_HASH.findall(code)}
        text = read(spec)
        marks = list(ROSTER_MARK.finditer(text))

        if not marks:
            if len(pinned) >= ROSTER_FLOOR:
                findings.append(
                    Finding(
                        rel(spec),
                        f"pins {len(pinned)} routes ({', '.join(sorted(pinned))}) and declares no\n"
                        "roster. A list of screens typed by hand goes stale silently — the route\n"
                        "added next month is simply not in it and nothing goes red. Either derive\n"
                        "the list at run time (see cursor.spec.ts), or put `ROUTE-ROSTER all` or\n"
                        "`ROUTE-ROSTER hotkey` in a comment above the literal so this row can\n"
                        "check it against App.tsx's ROUTES table.",
                    )
                )
            continue

        for mark in marks:
            marked += 1
            kind = mark.group(1)
            line = text.count("\n", 0, mark.start()) + 1
            where = f"{rel(spec)}:{line}"
            if not expected:
                continue
            # FROM THE `=`, NOT FROM THE MARKER. `const VIEW: Record<(typeof RING)[number],
            # string> = {` puts a `[` in the TYPE, and a reader that took the first bracket
            # after the comment read `[number]` and reported a roster with no routes in it —
            # a failure that says "you pinned nothing", which is not what is wrong and is not
            # a message anybody could act on. The assignment is the only `=` between a marker
            # and the literal it governs.
            assign = text.find("=", mark.end())
            opening = (
                min(
                    (found for found in (text.find(bracket, assign) for bracket in "[{") if found != -1),
                    default=-1,
                )
                if assign != -1
                else -1
            )
            literal = _balanced(text, opening) if opening != -1 else ""
            if not literal:
                findings.append(
                    Finding(where, "declares a roster with no array or object literal under it.")
                )
                continue
            found = ROUTE_HASH.findall(_strip_ts_comments(literal))
            want = expected[kind]
            if found != want:
                absent = [route for route in want if route not in found]
                extra = [route for route in found if route not in want]
                detail = []
                if absent:
                    detail.append(f"missing: {', '.join(absent)}")
                if extra:
                    detail.append(f"not a `{kind}` route: {', '.join(extra)}")
                if not detail:
                    detail.append("same routes, wrong order")
                findings.append(
                    Finding(
                        where,
                        f"declares `ROUTE-ROSTER {kind}` and does not match App.tsx's table.\n"
                        + "\n".join(detail)
                        + f"\nwant: {', '.join(want)}"
                        + f"\nhave: {', '.join(found)}",
                    )
                )

    findings.extend(_route_prose_findings())

    report.add(
        "route rosters",
        MECHANICAL,
        findings,
        f"{marked} declared roster{'' if marked == 1 else 's'} against "
        f"{len(expected.get('all', []))} registered routes",
        scanned=marked,
    )

# ------------------------------------------------------ deletions a decision records
#
# A DELETION IS THE ONE KIND OF RULING A MERGE CAN UNDO WITHOUT ANYBODY WRITING A LINE. D119
# deleted `LocationCard` on 2026-09-07 (PR #218, `4bf5a44`) and the very next PR to land put it
# back: `9439765` (PR #221, a cap-wording change) was committed from a tree that still held the
# pre-deletion copy of every file #218 had touched — the component, its stylesheet, the specs
# that asserted its absence and the map rows that recorded it — and the merge carried all of it
# onto main in one commit whose message was about something else. Every guard the deletion had
# was IN the files that came back, so every guard came back with the thing it guarded against,
# and `make check` was green on both sides. Three days later D132's session found the component,
# read the owner's screenshot of it as evidence they wanted it, and wrote that down.
#
# So the guard lives HERE, in a file no screen change touches, and it is the smallest possible
# claim: a decision that records a symbol as deleted is contradicted by that symbol existing
# under app/src. The table is hand-written on purpose — reading docs/decisions/ for the word
# "deleted" would fire on every entry that deletes a sentence — and adding a row to it is how a
# session says a deletion is meant to stay one. A symbol that is meant to come back is removed
# from the table in the same commit that restores it, with the entry amended to say so.

# THE SCAN ROOTS. `app/src` alone until 2026-09-12, which is why the row printed `ok` over
# a resurrection in the OTHER language for a quarter: four of this quarter's five recorded
# deletions took code out of `server/`, `cli/` and `harness/`, and the scan could not look
# at any of them. A deletion is not an app-only kind of ruling.
DELETION_ROOTS: Tuple[str, ...] = (
    "app/src", "server", "store", "pipeline", "cli", "harness",
)
DELETION_SUFFIXES: Tuple[str, ...] = (".ts", ".tsx", ".css", ".py")

# NAMES THAT CAME BACK ON PURPOSE, AND MAY NOT BE NEEDLES. Recorded here rather than left
# out silently, because "not in the table" and "deliberately not in the table" are the same
# absence to a reader, and the next session to widen this row would add them straight back.
#
#   `do_order_fill`, `POST /orders/fill`   D97 deleted D90's envelope fill; D113 REBUILT a
#       route and a handler under both names for a different job — closing copies of a line
#       with no card behind them. Both exist today (server/capture_server.py, app/src/
#       server.ts, app/src/types.ts) and both are correct. A name is not a capability.
#   D110's three dark-only hover overrides   `.bn-nav-link`, `.capture-row` and
#       `.capture-opt` are LIVE classes; what D110 deleted is a declaration inside a
#       `[data-theme='dark']` block. A substring needle for that is either the class name —
#       red on every run — or a string that appears nowhere, which is a needle that can
#       never fire, i.e. the vacuous green this row is about. It wants a CSS-structural
#       reader, not this one.

RECORDED_DELETIONS: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
    # (decision, what it deleted, the strings whose presence in the scanned code contradicts it)
    ("D119", "the `#/inventory` location card", ("LocationCard", "inventory-location")),
    ("D97", "D90's envelope fill — the walk, its banner and its harness case",
     ("orderWalk", "OrderWalkBanner", "check_order_fill")),
    ("D132", "`PositionLabel`'s `indexNote`", ("indexNote",)),
    ("D155", "the segment reader that computed edges from card counts", ("lensOf",)),
    # `cadence.ts` is the needle that keeps the prose classifier LIVE: it appears today in
    # exactly one place, a block comment in `app/src/motion.ts` narrating the retirement, so
    # every run exercises the comment/code split rather than leaving it to the self-test
    # alone. A classifier nothing routes through is the vacuous green one register down.
    ("D144", "the beat-locked cadence trigger, its module and its period pin",
     ("cadenceTrigger", "CadenceMachine", "DEFAULT_CADENCE", "periodPin", "pinPeriod",
      "cadence.ts")),
)


def _prose_blanked(path: Path, text: str) -> str:
    """`text` with comments — and, in Python, docstrings — replaced by spaces.

    OFFSETS AND LINE NUMBERS SURVIVE, so a hit found here reports the line it is really on.

    WHY THIS EXISTS: `server/capture_server.py`'s docstring NARRATES one of these
    deletions — "`/orders/fill`, which D97 deleted rather than wired up" — and reading that
    as the symbol existing would make the row red for the prose that is doing its job.
    Prose about a deletion is the record of it; executable code is the contradiction.

    Python docstrings only, never every string literal. Blanking all of them would turn a
    real code hit like `if name == "orderWalk"` into prose, which is the wrong direction to
    be wrong in for a row whose whole subject is a resurrection.
    """
    out = list(text)

    def blank(start: int, end: int) -> None:
        for i in range(max(0, start), min(len(out), end)):
            if out[i] != "\n":
                out[i] = " "

    if path.suffix == ".py":
        try:
            for token in tokenize.generate_tokens(io.StringIO(text).readline):
                if token.type == tokenize.COMMENT:
                    blank(_offset(text, token.start), _offset(text, token.end))
        except (tokenize.TokenError, IndentationError, SyntaxError):
            pass  # fails open: an unparseable file is scanned raw
        try:
            tree = ast.parse(text)
        except SyntaxError:
            tree = None
        if tree is not None:
            for node in ast.walk(tree):
                for child in ast.iter_child_nodes(node):
                    if (
                        isinstance(child, ast.Expr)
                        and isinstance(child.value, ast.Constant)
                        and isinstance(child.value.value, str)
                    ):
                        blank(
                            _offset(text, (child.lineno, child.col_offset)),
                            _offset(text, (child.end_lineno or child.lineno,
                                           child.end_col_offset or 0)),
                        )
    else:
        for found in TS_COMMENT.finditer(text):
            blank(found.start(), found.end())
    return "".join(out)


def _offset(text: str, position: Tuple[int, int]) -> int:
    """(1-based line, 0-based column) -> character offset."""
    line, column = position
    offset = 0
    for _ in range(line - 1):
        found = text.find("\n", offset)
        if found == -1:
            return len(text)
        offset = found + 1
    return min(len(text), offset + column)


def check_recorded_deletions(report: Report) -> None:
    """A symbol a decision records as deleted does not exist in the code.

    MECHANICAL: the entry says the thing is gone, and a grep says whether it is. See the banner
    above for the merge that made this row necessary — and for why the guard cannot live in
    the files the deletion touched.

    **SIX ROOTS, NOT ONE.** The scan walked `app/src` and nothing else, so it could not see
    four of the five deletions recorded this quarter — `do_order_fill` and its dispatcher in
    `server/`, harness T7's `check_order_fill`, the cadence module's Python mirror. A row
    whose subject is "does this symbol exist" has to look everywhere the symbol could be.

    **PROSE IS NOT A RESURRECTION.** A hit inside a comment or a docstring is the deletion
    being narrated and is counted in the summary rather than raised: `capture_server.py`
    carries exactly such a sentence about D97. The count is printed so a needle that lives
    only in prose can be told from one with no hits at all — and it is deliberately NOT an
    advisory finding, because `exit 2` in this repo already stands permanently lit and one
    more standing question would teach the next reader to skip the code entirely.

    **ITS OWN DENOMINATORS ARE PUBLISHED.** The roster is hand-kept, so its size is the
    thing most likely to be wrong about this row, and a scan that enumerated zero roots or
    zero needles is a finding rather than an `ok` — the shape a bare `scanned` count cannot
    see, since the row would still have walked hundreds of files to compare nothing.
    """
    findings: List[Finding] = []
    needle_count = sum(len(needles) for _, _, needles in RECORDED_DELETIONS)

    roots = [ROOT / root for root in DELETION_ROOTS if exists(ROOT / root)]
    if not roots:
        findings.append(
            Finding(
                "scripts/docs_audit/hygiene.py -> DELETION_ROOTS",
                f"names {len(DELETION_ROOTS)} roots and none of them is on disk, so this row "
                f"compared nothing. Re-point the list: a scan with no root reports no "
                f"resurrection however many there are.",
            )
        )
    if not needle_count:
        findings.append(
            Finding(
                "scripts/docs_audit/hygiene.py -> RECORDED_DELETIONS",
                "holds no needle, so the row is watching nothing. An emptied roster and a "
                "tree with no resurrection in it print the same word otherwise.",
            )
        )

    paths = sorted({path for root in roots for path in _walk(root, DELETION_SUFFIXES)}, key=rel)
    narrated = 0
    for path in paths:
        text = read(path)
        code = None
        for decision, what, needles in RECORDED_DELETIONS:
            for needle in needles:
                if needle not in text:
                    continue
                if code is None:
                    code = _prose_blanked(path, text)
                if needle not in code:
                    narrated += 1
                    continue
                line = code.count("\n", 0, code.index(needle)) + 1
                findings.append(
                    Finding(
                        f"{rel(path)}:{line}",
                        f"names `{needle}`, and {decision} records {what} as deleted.\n"
                        "Either the deletion is being undone — amend the entry and remove the "
                        "row from RECORDED_DELETIONS in the same commit — or a merge has "
                        "carried the pre-deletion file back onto this branch, which is how it "
                        "happened the first time.",
                    )
                )

    report.add(
        "recorded deletions",
        MECHANICAL,
        findings,
        f"{len(RECORDED_DELETIONS)} recorded deletion{'' if len(RECORDED_DELETIONS) == 1 else 's'}, "
        f"{needle_count} needles over {len(roots)} roots and {len(paths)} files"
        + (f"; {narrated} narrated in prose" if narrated else ""),
        scanned=needle_count * len(roots),
    )


# ------------------------------------------------------------- the capture-port seal
#
# `app/src/server.ts` talks to a DIFFERENT ORIGIN from the one the page came off —
# `${location.protocol}//${location.hostname}:${CAPTURE_PORT}` — so a spec that stubs
# everything its own SCREEN asks for still leaks the shell's `GET /status`, which
# `App.tsx:useServerPresence` polls from outside every route boundary and which therefore
# belongs to no screen. Ten specs did, and two of them read boxes, inventory, runs and four
# real card photographs besides. In the main checkout that port is the owner's live capture
# server over their real store, kept alive at login by `make launch-agent`; in a worktree
# nothing answers and the shell draws a 44px banner that moves every geometry floor
# `make design-check` asserts. `app/tests/shell.ts` closes it.
#
# THIS ROW IS THE HALF THAT CANNOT BE CLOSED IN TYPESCRIPT. A missing call fails loudly on
# its own — the spec's reads reach the port and the roster in `sealEveryTest`'s `afterEach`
# names them. A call placed BELOW the file's own `test.beforeEach` does not: hooks run in
# declaration order, so the seal installs after the navigation it was meant to catch, those
# requests reach the real port UNRECORDED, and the assertion passes over an empty list. A
# guard that goes green for having watched nothing is the failure `check dispatch` two
# sections down exists about, in a second place.

SEAL_CALL = re.compile(r"\bsealEveryTest\s*\(")

# THE ANCHOR IS THE HOOK AND NOT `page.goto(`, and that distinction is the whole of what this
# row gets right. A spec's `open()` helper is DEFINED above the seal call and RUNS inside the
# test body, long after every hook has registered — `live-reconcile`, `markdown`, `pricing`
# and `run-panel` are all shaped that way and all correct. Only a hook can register before the
# seal does.
SPEC_HOOK = re.compile(r"^\s*test\.before(?:Each|All)\s*\(", re.M)

# Navigation is what makes a spec need the seal at all. `motion.spec.ts` drives
# `app/src/motion.ts` directly with no page, and must not be dragged in.
SPEC_GOTO = re.compile(r"\bpage\.goto\s*\(")


def _blank_ts_comments(text: str) -> str:
    """TypeScript comments replaced by their own newlines, so ORDER and LINE NUMBERS survive.

    `_strip_ts_comments` collapses a block comment to a single space, which is right for
    `route rosters` — it re-reads the raw text to find line numbers — and wrong here, where
    the whole question is which of two constructs comes first in the file.
    """
    return TS_COMMENT.sub(lambda found: "\n" * found.group(0).count("\n"), text)


# --------------------------------------------------------------- the design-check verdict
#
# `make design-check` is the one target a session cannot wait for inside a tool call: ~2
# minutes clean, 171s measured under load, against a 120s timeout. So it leaves a verdict at
# `.serve/design-check.json` and CLAUDE.md tells the next session to read that file instead
# of the 450-line stream. Four files have to agree for that instruction to be true, and
# THREE OF THE FOUR WAYS THEY CAN DISAGREE ARE SILENT:
#
#   * the reporter dropped from `playwright.config.ts`'s reporter list — the suite runs, is
#     green, and writes nothing;
#   * `RESULT_FILE` moved in the reporter but not in the prose — the suite writes a verdict
#     nobody reads;
#   * the `rm -f` dropped from a Makefile recipe — and this is the worst of the three,
#     because it is what makes a MISSING file mean "died before Playwright loaded its
#     config". Without it a run that never started leaves the PREVIOUS run's `"pass"`
#     sitting there for a session to believe. That is a false green reached by following
#     the documented procedure, which is the shape this repo has the fewest defences
#     against.
#
# Only the fourth is loud: delete `design-check-reporter.ts` while the config still names
# it and Playwright refuses to start.
#
# THIS IS A STATIC AGREEMENT CHECK AND NOT A BEHAVIOURAL ONE, which is a real limit and is
# recorded rather than papered over. It reads four files and reconciles one path and one
# name across them; it cannot tell you the reporter still WORKS. Proving that needs a
# Playwright run, which is the whole reason `design-check` is not in `make check` — a check
# that starts a browser is a different weight of check from the rest. Same bargain
# `check registry` records about itself: this row can only lie about agreement, and it
# fails a commit when it does.
_VERDICT_RESULT_FILE = re.compile(
    r"RESULT_FILE\s*=\s*resolve\(\s*REPO_ROOT\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*\)"
)
_VERDICT_REPORTER = ROOT / "app" / "design-check-reporter.ts"
_VERDICT_CONFIG = ROOT / "app" / "playwright.config.ts"
_VERDICT_RECIPES = ("design-check", "design-check-quiet")


def _make_recipe(text: str, target: str) -> Optional[List[str]]:
    """The recipe lines of one Makefile target, or None where the target has no rule.

    Pure, so `--self-test` can drive it without a Makefile.
    """
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not line.startswith(f"{target}:"):
            continue
        body: List[str] = []
        for following in lines[index + 1:]:
            if following.startswith("\t"):
                body.append(following[1:])
            elif following.strip() == "" or following.startswith("#"):
                continue
            else:
                break
        return body
    return None


def verdict_disagreements(
    reporter: Optional[str],
    config: Optional[str],
    makefile: str,
    published: str,
) -> List[Finding]:
    """The four-way agreement, as a pure function of four file bodies.

    Split out from the file reading so `--self-test` can hand it each way of disagreeing
    without a repository — the same split `check_dispatch` and `phony_gaps` already make.
    """
    findings: List[Finding] = []
    if reporter is None:
        findings.append(
            Finding(
                "app/design-check-reporter.ts",
                "does not exist, but CLAUDE.md tells a session to read the file it writes.",
            )
        )
        return findings

    match = _VERDICT_RESULT_FILE.search(reporter)
    if match is None:
        findings.append(
            Finding(
                "app/design-check-reporter.ts",
                "no `RESULT_FILE = resolve(REPO_ROOT, ...)` to read.\n"
                "  That constant is what every claim below is reconciled against.",
            )
        )
        return findings
    path = f"{match.group(1)}/{match.group(2)}"

    if config is None:
        findings.append(Finding("app/playwright.config.ts", "does not exist."))
    elif "design-check-reporter" not in _blank_ts_comments(config):
        findings.append(
            Finding(
                "app/playwright.config.ts",
                "its `reporter` setting no longer names `./design-check-reporter.ts`.\n"
                "  The suite would run green and write no verdict at all, and a session "
                "following CLAUDE.md would read the absent file as `the run died before "
                "Playwright loaded its config` — a wrong diagnosis reached by following the "
                "documented procedure.\n"
                "  Comments do not count: this reads the config with them blanked.",
            )
        )

    for target in _VERDICT_RECIPES:
        body = _make_recipe(makefile, target)
        if body is None:
            findings.append(Finding("Makefile", f"no `{target}` rule to read."))
            continue
        removes = next((n for n, line in enumerate(body) if "rm -f" in line and path in line), None)
        runs = next((n for n, line in enumerate(body) if "run design-check" in line), None)
        if runs is None:
            findings.append(
                Finding("Makefile", f"`{target}` never invokes the design-check script.")
            )
            continue
        if removes is None:
            findings.append(
                Finding(
                    "Makefile",
                    f"`{target}` does not delete `{path}` before it runs.\n"
                    "  Deleting first is the whole reason a MISSING file means something. "
                    "Without it, a run that dies before Playwright loads its config leaves "
                    "the PREVIOUS run's verdict in place — a stale `\"pass\"` for the next "
                    "session to believe.",
                )
            )
        elif removes > runs:
            findings.append(
                Finding(
                    "Makefile",
                    f"`{target}` deletes `{path}` AFTER running the suite, which throws the "
                    "verdict away instead of clearing a stale one.",
                )
            )

    if path not in published:
        findings.append(
            Finding(
                "CLAUDE.md",
                f"the reporter writes `{path}`, which this file never names.\n"
                "  The path is the whole instruction — a session told to read a verdict file "
                "needs to be told which one.",
            )
        )
    return findings


def check_design_check_verdict(report: Report) -> None:
    """`.serve/design-check.json` is named the same in the reporter, the config, make and the prose."""
    reporter = read(_VERDICT_REPORTER) if exists(_VERDICT_REPORTER) else None
    config = read(_VERDICT_CONFIG) if exists(_VERDICT_CONFIG) else None
    makefile = read(ROOT / "Makefile") if exists(ROOT / "Makefile") else ""
    published = read(ROOT / "CLAUDE.md") if exists(ROOT / "CLAUDE.md") else ""
    findings = verdict_disagreements(reporter, config, makefile, published)
    match = _VERDICT_RESULT_FILE.search(reporter or "")
    where = f"{match.group(1)}/{match.group(2)}" if match else "unreadable"
    report.add(
        "verdict file",
        MECHANICAL,
        findings,
        f"{where} agreed by the reporter, the config, {len(_VERDICT_RECIPES)} recipes and the prose",
        scanned=sum(1 for text in (reporter, config, makefile, published) if text),
    )


def check_spec_seal(report: Report) -> None:
    """Every spec that mounts the app seals this checkout's capture port, and seals it first.

    Two claims, and the second is the one that cannot fail loudly on its own. See the banner
    above for what each costs.
    """
    findings: List[Finding] = []
    sealed = 0
    for spec in sorted(glob_files(APP_TESTS, "*.spec.ts"), key=rel):
        code = _blank_ts_comments(read(spec))
        if SPEC_GOTO.search(code) is None:
            continue
        call = SEAL_CALL.search(code)
        if call is None:
            findings.append(
                Finding(
                    rel(spec),
                    "navigates the app and never calls `sealEveryTest()`.\n"
                    "Its unstubbed reads go to this checkout's capture port — in the main tree "
                    "that is the owner's live server over their real store, and in a worktree it "
                    "is the 44px offline banner that moves every design floor.\n"
                    "Add `import { sealEveryTest } from './shell'` and call it at module scope, "
                    "above the file's first `test.beforeEach`.",
                )
            )
            continue
        sealed += 1
        hook = SPEC_HOOK.search(code)
        if hook is not None and hook.start() < call.start():
            findings.append(
                Finding(
                    f"{rel(spec)}:{code.count(chr(10), 0, call.start()) + 1}",
                    "calls `sealEveryTest()` below the `test.beforeEach` on line "
                    f"{code.count(chr(10), 0, hook.start()) + 1}.\n"
                    "Hooks run in declaration order, so the seal would install AFTER that "
                    "hook's `page.goto` — the requests it exists to catch would reach the real "
                    "port and the roster would still be empty. Move the call above it.",
                )
            )

    report.add(
        "spec seal",
        MECHANICAL,
        findings,
        f"{sealed} spec{'' if sealed == 1 else 's'} sealed against the capture port",
        scanned=sealed,
    )

# `route census` is CUT (test-audit plan Q2, 2026-09-28). It reconciled a hand-typed
# route/screen count against ROUTES; the counts it watched are deleted from CLAUDE.md,
# README.md and docs/map.py rather than kept in step.


def check_positional_references(report: Report, docs: List[Path]) -> None:
    """A check named by its position, in the docs and in the code.

    **Two rows, because they are two different questions.** They do not share a scope and
    they do not share a severity, so a combined verdict would have had to take the widest
    scope and the strictest severity of both and apply them to each:

      check numbering    a check named by position in the markdown. Staged-scoped like
                         every other doc check, so a commit answers for its own lines.
      numbering in code  the same, in `.py` comments and the allowlist. ADVISORY and
                         whole-tree, for the reason `decision ids in code` is: a comment
                         saying it will check N rows is ordinary English, and a false
                         positive that blocks a commit is worse than one that prints a
                         line. This paragraph tripped it while being written, which is
                         about as direct as evidence gets.

    That split is the same reasoning as `check_decision_ids`, which reads the docs and the
    code as two rows rather than one, and it is why nothing here has to choose between
    scanning code at all and scanning it under the docs' rules.

    Named, not numbered: the report's labels are the public contract, and this function's
    name is not. It was `check_registry` while it also checked a published count of the
    checks; that count is gone (D18), the labels it prints did not change.
    """

    def positional(paths: Iterable[Path]) -> List[Finding]:
        found: List[Finding] = []
        for path in paths:
            if not exists(path):
                continue
            for number, line in enumerate(read(path).splitlines(), start=1):
                for hit in _POSITIONAL_RE.findall(line):
                    found.append(
                        Finding(
                            f"{rel(path)}:{number}",
                            f"`{hit}` names a check by its position. Use the label the "
                            f"report prints — `repo map`, `status sources`, and so on "
                            f"(D17). If this is ordinary English about a count, reword it: "
                            f"there is no allowlist for a phrase.",
                        )
                    )
        return found

    report.add("check numbering", MECHANICAL, positional(docs),
               "no check named by position", scanned=len(docs))
    in_code = python_files() + [ALLOWLIST]
    report.add(
        "numbering in code",
        ADVISORY,
        positional(in_code),
        "comments name checks by label",
        scanned=len(in_code),
    )
