"""Game and export vocabulary."""

from __future__ import annotations

import csv
import io
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Set, Tuple

from .core import (
    ADVISORY,
    Finding,
    GAME_COVERAGE_ALLOWLIST,
    MECHANICAL,
    ROOT,
    Report,
    exists,
    glob_files,
    literals_from_module,
    read,
    rel,
)
from .paths_commands import load_game_coverage_allowlist

# ------------------------------------------------------------------- the game registry
#
# `pipeline/games.py` authors one taxonomy per game (D22): the exact `Product Line` cell,
# the ordered `Rarity` cells, the finish enum, the finish -> `Condition` map and the
# rarity -> finish matrix. Nothing generates any of it — every field is ARGUMENT in D18's
# sense — so what is checkable is the authoring against a real export, and only in the
# directions where an export can actually settle the question.
#
# FOUR ROWS RATHER THAN ONE, SPLIT BY WHAT AN EXPORT PROVES. The same reasoning
# `check_positional_references` uses for its two rows: a combined verdict would have to
# take the strictest severity of all four and apply it to findings that are questions.
#
#   game vocabulary   MECHANICAL. The shape of the literal, plus the two export findings
#                     that cannot false-positive: a rarity whose folded form matches an
#                     export cell and whose raw form does not (a typo, provably), and an
#                     export cell no entry accounts for (a gap, provably).
#   game coverage     ADVISORY. Authored strings no export in view contains, and matrix
#                     pairs no export in view stocks. Absence from one set proves nothing —
#                     `Promo` and every pre-SV rarity are legitimately missing from an SV09
#                     fixture, and D23 requires the matrix to exceed its evidence.
#   matrix superset   MECHANICAL. An observed (rarity, finish) pair the matrix is MISSING.
#                     This is the row that keeps D23's unselectable finish chips safe.
#   join key shape    MECHANICAL. A `join_key` that the export's own `Number` cells prove
#                     can never match a row. One direction only — see the check.
#
# BLOCKING ROWS READ ONLY THE EXPORTS THE REPO CARRIES. `PKMNSCAN_EXPORTS` widens the
# advisory row and nothing else, and a path in it that does not resolve is skipped in
# silence rather than reported. A gate that can be failed by a file on one person's disk is
# a gate that gets switched off, and a gate that *requires* such a file has already switched
# itself off for everyone else — which is the same failure the repo-map orphan rule went
# quiet under, arriving from the opposite direction.

GAMES_MODULE = ROOT / "pipeline" / "games.py"
RARITY_MARKS_MODULE = ROOT / "app" / "src" / "kit" / "rarityMarks.ts"
MARK_PALETTES_MODULE = ROOT / "app" / "src" / "kit" / "markPalettes.ts"

# The one module allowed to build the export request (D65), and the three fields of it
# that are a standing instruction rather than a transcription of the portal's own form.
#
# THE REASON EACH ONE HOLDS IS CARRIED HERE RATHER THAN LEFT TO THE READER, because the person
# this row stops is the person who has just decided the value should be different — and the
# only thing that will change their mind is the argument, not a restatement of the number.
EXPORT_MODULE = ROOT / "server" / "tcg_export.py"
#: The live-inventory download's two query parameters (D104), MEASURED off the portal's own
#: `Export From Live` button rather than designed. That request is a GET with no scope: no
#: category, no sets, no conditions, no `MyInventory`, no `ExcludeListos`.
#:
#: WHY A BLOCKING ROW OVER TWO PARAMETERS. The first build of this path GUESSED a filtered POST
#: with `CategoryId: "0"`, on the reasoning that `"0"` is the portal's all-row everywhere else.
#: It is not — the category select is the one field on that form with no `0=All` option — and
#: the portal answered with a valid CSV header and ZERO rows. So on this endpoint a wrong
#: request is not refused, it is answered emptily, and the only thing standing between that and
#: a store-wide `live: 0` is this row plus `fetch_live`'s own empty-export refusal.
LIVE_QUERY_EXPECTED = (
    (
        "type",
        "Pricing",
        "The LIVE tab rather than Staged. `Export From Staged` is the same endpoint with the "
        "other value and is a different document — D87 reconciles the store against the live "
        "one, so this value decides what `live` means for every SKU.",
    ),
    (
        "exportLowestListingNotMe",
        "true",
        "The portal's own default, checked on that form as 'If me, show next lowest'. It "
        "changes the `TCG Low Price` column this pipeline reads and prices against, so it is "
        "transcription that MATTERS rather than transcription that does not.",
    ),
)

EXPORT_STANDING = (
    (
        "ExcludeListos",
        True,
        "Exclude listings with photos — the owner's standing instruction (2026-08-31, D76). "
        "It holds on the owner's word: what the flag changes in the file is NOT measured, "
        "because the axis leaves no trace in it. NOTHING DOWNSTREAM CAN CATCH A WRONG VALUE: "
        "D65 measured `Photo URL` empty in every export, filtered and unfiltered, so a wrong "
        "value gives a clean join and a green `make check` forever. Do not flip this on a "
        "reading of the field name — take it back to the owner.",
    ),
    (
        "MyInventory",
        False,
        "The CATALOG, not the operator's current listings. With this true the same request "
        "returns only what is already listed, which is useless to a join whose whole job is "
        "listing cards that are not.",
    ),
    (
        "PrintingIds",
        ["0"],
        "All Printings. A number stocked in several finishes must arrive with all of them, "
        "or D3 rung 2 decides it from whichever one survived — which is a silent mislisting "
        "rather than a loud miss.",
    ),
)

# ---------------------------------------------- the transport promise, read off its own file
#
# `server/tcg_export.py` opens with FOUR BULLETS that are, in its own words, the REPLACEMENT
# for a guarantee it deleted rather than qualified — the file that reads the operator's
# `TCGPLAYER_STORE_COOKIE` saying in prose what it is allowed to do with it. The first bullet
# is a count of hosts, methods and routes, and it is the one thing in that block a machine can
# settle: the constants are in the same file, and so is the request construction.
#
# IT WAS WRONG FOR A WEEK AND NOTHING COULD SAY SO. Written 2026-08-30 over a single GET, it
# read `One host, one method, one route` until 2026-09-06 — through D65 turning the download
# into a POST against a different route and promoting the filter list from a probe to a real
# call the same day, and through D104 adding the live download six days later. Three route
# changes and a second method under a sentence that never moved, and `server/pipeline_routes.py`
# had copied the sentence besides.
#
# WHY MECHANICAL RATHER THAN A QUESTION. Nothing here is a judgement. The host of a `https://`
# constant is a fact, the path of one is a fact, and whether a `_open` call carries a body is a
# fact — `_open` builds `method="POST" if data else "GET"`, so the keyword IS the method. A
# finding is a route or a method the code can reach and the promise does not name, or the
# reverse, and either one is provably wrong in the sense D16 asks for.
TRANSPORT_PROMISE_MODULE = ROOT / "server" / "tcg_export.py"

#: The one function every outbound request in that module goes through. Named here because the
#: whole reading hangs off it: a second opener would make this row describe half the traffic.
TRANSPORT_OPENER = "_open"

#: The headline the bullet leads with, whose three numbers are what this row settles. Anchored
#: on the bold run so a rewording is REPORTED rather than silently uncovered — `check census`'s
#: hard-won half, and the failure mode that matters most here: a promise this row stops
#: watching is a promise back in the state it spent a week in.
_TRANSPORT_HEADLINE_RE = re.compile(
    r"\*\*(\w+) hosts?, (\w+) methods?, (\w+) routes?\*\*", re.I
)

#: The routes the bullet tabulates, one `METHOD /path` per line. Indented under the headline
#: as a block, which is how the file writes a captured request everywhere else.
_TRANSPORT_ROUTE_RE = re.compile(r"^\s{4,}(GET|POST|PUT|PATCH|DELETE)\s+(/\S*)", re.M)

#: Number words, because the headline is prose and this repo writes counts in prose. Only as
#: far as anything here could plausibly reach; a count past it is reported rather than guessed.
_TRANSPORT_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
# ------------------------------------------- the set list's refusals, against the screen's map
#
# `GET /pipeline/games/<game>/sets` is the one refusal path in this repo that answers 200 and
# hands the CODE to a screen to re-word. That is argued and right — the operator is mid-capture
# and a failed autocomplete is not a failed capture — but it makes `CaptureScreen.tsx`'s
# `hintReason` the place a transport refusal becomes a sentence, and nothing checked that it
# covered the refusals that can arrive.
#
# IT COVERED TWO OF NINE. Measured 2026-09-06: `tcg_export.filters` can raise nine distinct
# codes and the map named `tcg_session_expired` and `tcg_cookie_missing`, so a WAF block at the
# rig read `Set list unavailable (tcg_blocked)` — a raw machine string on screen, which
# docs/DESIGN.md's register rule forbids, with the module's own remedy (set the user agent in
# `.env`) discarded one function above it.
#
# THE ROUTE CARRIES `message` NOW AND THAT IS THE FLOOR, NOT THIS ROW'S SUBJECT. A fallback
# that is routinely what the operator reads is a fallback nobody widens the map for, which is
# how the two-of-nine state lasted; this row is what keeps the net out from under the screen.
HINT_REASON_SCREEN = ROOT / "app" / "src" / "CaptureScreen.tsx"

#: The transport function the set-list route calls, and the root of the walk. Every refusal
#: reachable from it — through the endpoint accessors, the cookie read, the opener and the
#: status reader — is a code that can land on the capture screen.
HINT_REASON_ROOT = "filters"

#: The screen's map, read as the codes it compares against. Anchored on the function so a
#: rewrite that moves the comparisons elsewhere is REPORTED rather than silently uncovered.
_HINT_REASON_FN_RE = re.compile(r"function hintReason\([^)]*\)[^{]*\{(.*?)\n\}", re.S)
_HINT_REASON_CODE_RE = re.compile(r"code === '([a-z_]+)'")

#: Codes the map may name that no transport refusal produces, each with the reason it is there.
#: Declared rather than inferred: a map allowed to name anything is a map this row cannot read
#: in the second direction, and the dead branch is the finding that direction exists for.
HINT_REASON_NON_TRANSPORT = {
    "no_category": (
        "the route's own, raised before anything is fetched — this game carries no "
        "`tcgplayer_category_id` in pipeline/games.py, which is a fact about the registry "
        "rather than about the portal."
    ),
    "unreachable": (
        "the CLIENT's own, invented in `loadSets`'s catch when the request never reached the "
        "capture server. No server sends it, and the operator cannot tell it from "
        "`tcg_unreachable`, which is why the screen labels them together."
    ),
}
FIXTURES_DIR = ROOT / "fixtures"

# Opt-in extra exports, colon-separated, absolute or repo-relative. For the operator who
# has a full-catalog export or a Riftbound one on disk and wants the coverage questions
# asked against it. Never blocking — see the note above.
EXPORTS_ENV = "PKMNSCAN_EXPORTS"

PRODUCT_LINE_CELL = "Product Line"
RARITY_CELL = "Rarity"
CONDITION_CELL = "Condition"
NUMBER_CELL = "Number"

# Every key a registry entry must carry, and the one it may. Written here rather than read
# out of the module so that deleting a field from every entry at once is still a finding.
GAME_REQUIRED_KEYS = frozenset({
    "key", "display", "product_line", "rarities", "rarities_not_claimed", "finishes",
    "condition_by_finish", "finish_by_rarity", "located", "join_key", "prompt",
    "crop_bands", "card_aspect", "catalogued", "unverified",
})
GAME_OPTIONAL_KEYS = frozenset(
    {
        "product_line_rarities",
        "tcgplayer_category_id",
        "set_aliases",
        "export_scope",
        "export_needs_hint",
        "export_category_bytes",
        "rarity_display",
    }
)

# The `join_key` an uncatalogued game must name. Written here rather than read out of the
# module for the same reason GAME_REQUIRED_KEYS is: renaming the strategy in the registry
# alone would leave this rule matching nothing, silently, and a rule that cannot fire is
# worse than no rule. The existing shape check already proves the name is a member of
# JOIN_KEY_STRATEGIES, so the two together pin both halves.
NOT_JOINED_STRATEGY = "not_joined"

# The `join_key` whose key is COMPOSED as `zfill(3)(number) + "/" + printedTotal`. Named
# here because `check_join_key_shape` reasons about the "/" that composition always
# produces; nothing else in this file cares which strategy is which.
COMPOSED_STRATEGY = "number_and_printed_total"

_FOLD_RE = re.compile(r"[^a-z0-9]")


def fold_cell(text: str) -> str:
    """Case and punctuation removed. Two cells that fold alike are the same cell misspelt."""
    return _FOLD_RE.sub("", str(text).casefold())


class ExportFacts(NamedTuple):
    """What one export file says about product lines, rarities and conditions."""

    source: str
    committed: bool
    rarities: Dict[str, Set[str]]  # product line -> the `Rarity` cells under it
    triples: Set[Tuple[str, str, str]]  # (product line, rarity, condition)
    numbers: Dict[str, Set[str]]  # product line -> the non-blank `Number` cells under it


def _read_export(path: Path, committed: bool) -> Optional[ExportFacts]:
    """Parse one export with the stdlib `csv`, never with `pipeline.tcgcsv`.

    Importing a project module to audit a project data file is the same violation as
    importing one to audit its source, one layer down: it puts project code on the audit
    path, and this file's whole contract is that nothing there runs. The cost is that this
    reader is naive about the byte format — which is correct, because the byte format is
    T2's question and not this one's.

    Returns None for a CSV that is not an export at all. A file without both columns is not
    a malformed export, it is a different kind of file.
    """
    try:
        text = read(path)
    except (OSError, UnicodeError, subprocess.SubprocessError):
        return None
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if not reader.fieldnames:
        return None
    if PRODUCT_LINE_CELL not in reader.fieldnames or RARITY_CELL not in reader.fieldnames:
        return None

    rarities: Dict[str, Set[str]] = {}
    triples: Set[Tuple[str, str, str]] = set()
    numbers: Dict[str, Set[str]] = {}
    try:
        for row in reader:
            line = (row.get(PRODUCT_LINE_CELL) or "").strip()
            rarity = (row.get(RARITY_CELL) or "").strip()
            condition = (row.get(CONDITION_CELL) or "").strip()
            if not line:
                continue
            # `Number` is gathered before the rarity filter below, because the join key is
            # a property of the product line and not of a rarity — and because the rows
            # this file most needs to see the shape of (sealed product, DON!! cards) are
            # exactly the ones with no rarity cell.
            number = (row.get(NUMBER_CELL) or "").strip()
            if number:
                numbers.setdefault(line, set()).add(number)
            if not rarity:
                continue
            rarities.setdefault(line, set()).add(rarity)
            if condition:
                triples.add((line, rarity, condition))
    except csv.Error:
        return None
    return ExportFacts(rel(path), committed, rarities, triples, numbers)


_EXPORTS: Optional[List[ExportFacts]] = None


def export_facts() -> List[ExportFacts]:
    """Every export in view: the committed fixtures always, then the opt-in ones.

    Built once. A `PKMNSCAN_EXPORTS` entry that does not resolve, does not read, or is not
    an export is dropped without a word — see the section note for why that silence is the
    point rather than a gap.
    """
    global _EXPORTS
    if _EXPORTS is not None:
        return _EXPORTS
    found: List[ExportFacts] = []
    for path in glob_files(FIXTURES_DIR, "*.csv"):
        facts = _read_export(path, committed=True)
        if facts is not None:
            found.append(facts)
    for entry in (os.environ.get(EXPORTS_ENV) or "").split(":"):
        entry = entry.strip()
        if not entry:
            continue
        path = Path(entry)
        if not path.is_absolute():
            path = ROOT / entry
        if not path.is_file():
            continue
        facts = _read_export(path, committed=False)
        if facts is not None:
            found.append(facts)
    _EXPORTS = found
    return _EXPORTS


def observed_rarities(committed_only: bool) -> Dict[str, Set[str]]:
    """product line -> every `Rarity` cell seen under it."""
    out: Dict[str, Set[str]] = {}
    for facts in export_facts():
        if committed_only and not facts.committed:
            continue
        for line, cells in facts.rarities.items():
            out.setdefault(line, set()).update(cells)
    return out


def observed_triples(committed_only: bool) -> Set[Tuple[str, str, str]]:
    return {
        triple
        for facts in export_facts()
        if not (committed_only and not facts.committed)
        for triple in facts.triples
    }


def game_entries() -> Tuple[Dict[str, object], List[Finding]]:
    """The registry's literals, or the one finding that says why there are none."""
    if not exists(GAMES_MODULE):
        return {}, [Finding(rel(GAMES_MODULE), "does not exist")]
    data = literals_from_module(GAMES_MODULE)
    if not data.get("GAMES"):
        return {}, [
            Finding(
                rel(GAMES_MODULE),
                "no GAMES literal could be read. The registry is read with "
                "`ast.literal_eval` and never imported, so every entry must be a plain "
                "literal — a name, a call or an f-string inside one makes the whole "
                "registry unreadable to this check rather than only that field.",
            )
        ]
    return data, []


def _claimed_by(entry: Dict[str, object]) -> Set[str]:
    """Every `Rarity` cell this entry accounts for, claimed as a stack or not."""
    return (
        set(entry.get("rarities") or ())
        | set(entry.get("rarities_not_claimed") or ())
        | set(entry.get("product_line_rarities") or ())
    )


def rarity_mark_table() -> Optional[Dict[str, Dict[str, str]]]:
    """`app/src/kit/rarityMarks.ts`'s (game, rarity, palette) table as a dict, read as text:
    one `  <game>: {` block per game and one `'<rarity>': '<palette>',` line per rarity. None
    when the file is missing, which is a finding at the caller."""
    if not RARITY_MARKS_MODULE.exists():
        return None
    text = RARITY_MARKS_MODULE.read_text(encoding="utf-8")
    table: Dict[str, Dict[str, str]] = {}
    game: Optional[str] = None
    for line in text[text.index("export const RARITY_MARKS") :].splitlines():
        opened = re.match(r"^  (\w+): \{$", line)
        if opened:
            game = opened.group(1)
            table[game] = {}
            continue
        if line.startswith("  }"):
            game = None
            continue
        row = re.match(r"^    '([^']+)': '(\w+)',$", line)
        if row and game is not None:
            table[game][row.group(1)] = row.group(2)
    return table


def mark_palette_names() -> Set[str]:
    """The palette names `markPalettes.ts`'s `LogoVariant` union declares."""
    if not MARK_PALETTES_MODULE.exists():
        return set()
    text = MARK_PALETTES_MODULE.read_text(encoding="utf-8")
    union = re.search(r"export type LogoVariant = ([^\n]+)", text)
    return set(re.findall(r"'(\w+)'", union.group(1))) if union else set()


def check_game_vocabulary(report: Report) -> None:
    """`pipeline/games.py`'s shape, and the two export findings that cannot false-positive.

    **Structure first, because everything downstream reads these fields.** Required keys
    present, no unknown ones, keys unique, `finish_by_rarity` confined to the rarities and
    finishes the same entry declares, `condition_by_finish` covering exactly the finish
    enum, `join_key` and `prompt` naming a strategy the module publishes, and the entry
    sitting squarely in ONE of the registry's three states rather than between two of them.
    Each of those is the shape of a literal, and the shape of a literal is provable — there
    is no context this script is missing, which is what makes the row blocking.

    **The three states are `catalogued` x `unverified`, and keeping them apart is the
    newest thing this row does.** `unverified: True` is a measurement somebody owes and a
    consumer must refuse until it arrives. `catalogued: False` is the finished answer for a
    game that spans several product lines at once — `misc`, roughly 1% of the shelf — and
    it must never refuse in the same voice, or every one of those captures reads as a fault
    and a genuinely unmeasured game hides among them. So the flags are separate, an entry
    setting both is a finding, and each state pins `product_line`, `rarities`, `join_key`
    and `card_aspect` to a shape the other two cannot wear.

    **Then the two export questions that are not questions.** A rarity whose *folded* form
    matches a cell in a committed export while its raw form matches nothing is a typo:
    `Illustration  Rare` for `Illustration Rare`, `double rare` for `Double Rare`. It can
    never false-positive, because the fold only fires when the export contains the same
    string modulo case and punctuation. And a cell in a committed export that no entry
    accounts for is a gap in the registry, provable in the same direction.

    `rarities_not_claimed` is what makes the second one liveable. `Code Card` is a Pokemon
    rarity that the `pokemon` game never offers as a stack claim — `pokemon_code` claims it
    — so accounting for a cell and claiming it have to be different things, or every entry
    would have to lie about its own picker to keep this row quiet.
    """
    data, findings = game_entries()
    if findings:
        report.add("game vocabulary", MECHANICAL, findings)
        return

    entries = list(data["GAMES"])
    join_keys = set(data.get("JOIN_KEY_STRATEGIES") or ())
    prompts = set(data.get("PROMPT_STRATEGIES") or ())
    bands = set(data.get("CROP_BAND_NAMES") or ())
    where_module = rel(GAMES_MODULE)

    marks = rarity_mark_table()
    palettes = mark_palette_names()
    if marks is None:
        findings.append(
            Finding(rel(RARITY_MARKS_MODULE), "the (game, rarity, palette) table is missing."),
        )
    else:
        # Both directions, and the palette must be one the mark ships.
        known = {str(e.get("key")): set(e.get("rarities") or ()) for e in entries}
        for game, rows in marks.items():
            for rarity, palette in rows.items():
                if palette not in palettes:
                    findings.append(
                        Finding(
                            f"{rel(RARITY_MARKS_MODULE)} -> {game}",
                            f"{rarity!r} wears {palette!r}, which markPalettes.ts does not declare.",
                        )
                    )
                if rarity not in known.get(game, set()):
                    findings.append(
                        Finding(
                            f"{rel(RARITY_MARKS_MODULE)} -> {game}",
                            f"{rarity!r} is no rarity of {game!r} in pipeline/games.py.",
                        )
                    )

    seen: Set[str] = set()
    for entry in entries:
        key = str(entry.get("key", "?"))
        where = f"{where_module} -> {key}"
        if marks is not None:
            for rarity in entry.get("rarities") or ():
                if rarity not in marks.get(key, {}):
                    findings.append(
                        Finding(
                            where,
                            f"rarity {rarity!r} has no mark palette in "
                            f"{rel(RARITY_MARKS_MODULE)}: add a line for it.",
                        )
                    )
        if key in seen:
            findings.append(Finding(where, f"two entries claim the key {key!r}."))
        seen.add(key)

        missing = sorted(GAME_REQUIRED_KEYS - set(entry))
        if missing:
            findings.append(Finding(where, f"missing required fields: {', '.join(missing)}."))
        unknown = sorted(set(entry) - GAME_REQUIRED_KEYS - GAME_OPTIONAL_KEYS)
        if unknown:
            findings.append(
                Finding(
                    where,
                    f"unknown fields: {', '.join(unknown)}. A field no consumer reads is a "
                    f"field nothing keeps honest — add it to GAME_REQUIRED_KEYS here when "
                    f"it becomes real, or drop it.",
                )
            )

        rarities = set(entry.get("rarities") or ())
        finishes = set(entry.get("finishes") or ())
        conditions = entry.get("condition_by_finish") or {}
        matrix = entry.get("finish_by_rarity") or {}

        for rarity, allowed in matrix.items():
            if rarity not in rarities:
                findings.append(
                    Finding(where, f"finish_by_rarity keys {rarity!r}, which is not in `rarities`.")
                )
            stray = sorted(set(allowed or ()) - finishes)
            if stray:
                findings.append(
                    Finding(
                        where,
                        f"finish_by_rarity[{rarity!r}] names {', '.join(stray)}, which is "
                        f"not in this entry's `finishes`.",
                    )
                )
        if set(conditions) != finishes:
            findings.append(
                Finding(
                    where,
                    f"condition_by_finish covers {sorted(set(conditions))} but `finishes` is "
                    f"{sorted(finishes)}. Every finish needs exactly one condition string, "
                    f"and a condition string with no finish is unreachable.",
                )
            )

        # D76's per-game fetch width. Two provable things and nothing softer: the value is
        # one of the two the registry publishes, and `category` — the claim that a whole
        # TCGplayer category comes down in one file — cannot be authored for a game naming
        # no category to fetch. Both are the shape of a literal, which is what keeps this row
        # blocking rather than advisory.
        scope = entry.get("export_scope")
        if scope is not None:
            if scope not in set(data.get("EXPORT_SCOPES") or ()):
                findings.append(
                    Finding(
                        where,
                        f"export_scope {scope!r} is not one of "
                        f"{', '.join(sorted(data.get('EXPORT_SCOPES') or ()))}.",
                    )
                )
            elif scope == "category" and not entry.get("tcgplayer_category_id"):
                findings.append(
                    Finding(
                        where,
                        "export_scope is `category` but the entry names no "
                        "`tcgplayer_category_id`, so there is no category to fetch whole.",
                    )
                )

        # THE HINT REQUIREMENT, AND ITS EVIDENCE, WHICH MAY NOT TRAVEL APART.
        #
        # `export_needs_hint` refuses a real run — it is the only field here that can stop
        # an operator mid-pipeline — and it is a JUDGEMENT ABOUT A NUMBER: that this game's
        # whole category is too close to `tcg_export.MAX_BYTES` to widen into on a guess.
        # Authored without `export_category_bytes` beside it, that judgement is unarguable
        # and unre-makeable by the next person to read the entry, so it is refused.
        #
        # AND IT IS REFUSED ON A `category` GAME, which would be a DEAD field rather than a
        # wrong one: `_scope_for_run` only reaches the question where the CARDS widened the
        # scope, and a game that always fetches its whole category widens by policy and
        # never gets there. A rule that cannot fire is worse than no rule, which is the
        # argument `NOT_JOINED_STRATEGY` above is written out for.
        needs_hint = entry.get("export_needs_hint")
        measured = entry.get("export_category_bytes")
        if needs_hint is not None and not isinstance(needs_hint, bool):
            findings.append(
                Finding(
                    where,
                    f"export_needs_hint is {needs_hint!r}, which is not a boolean. It "
                    f"gates a refusal; it may not be a string that is merely truthy.",
                )
            )
        elif needs_hint:
            if not isinstance(measured, int) or isinstance(measured, bool) or measured <= 0:
                findings.append(
                    Finding(
                        where,
                        "export_needs_hint is authored but `export_category_bytes` is not a "
                        "positive integer. The requirement is a judgement about how wide "
                        "this game's whole category is, so the measurement has to sit "
                        "beside it — the refusal quotes it to the operator.",
                    )
                )
            if not entry.get("tcgplayer_category_id"):
                findings.append(
                    Finding(
                        where,
                        "export_needs_hint is authored but the entry names no "
                        "`tcgplayer_category_id`, so there is no export for a hint to "
                        "narrow.",
                    )
                )
            if scope == "category":
                findings.append(
                    Finding(
                        where,
                        "export_needs_hint is authored beside `export_scope: category`. "
                        "That game widens by policy and never reaches the cards, so the "
                        "requirement could never fire.",
                    )
                )
        if measured is not None and (
            not isinstance(measured, int) or isinstance(measured, bool) or measured <= 0
        ):
            findings.append(
                Finding(
                    where,
                    f"export_category_bytes is {measured!r}, which is not a positive "
                    f"integer of bytes.",
                )
            )

        if entry.get("join_key") not in join_keys:
            findings.append(
                Finding(
                    where,
                    f"join_key {entry.get('join_key')!r} is not one of "
                    f"JOIN_KEY_STRATEGIES ({', '.join(sorted(join_keys))}).",
                )
            )
        if entry.get("prompt") not in prompts:
            findings.append(
                Finding(
                    where,
                    f"prompt {entry.get('prompt')!r} is not one of PROMPT_STRATEGIES "
                    f"({', '.join(sorted(prompts))}).",
                )
            )
        stray_bands = sorted(set(entry.get("crop_bands") or ()) - bands)
        if stray_bands:
            findings.append(
                Finding(
                    where,
                    f"crop_bands names {', '.join(stray_bands)}, which geometry/crop.py does "
                    f"not cut. CROP_BAND_NAMES is the list of regions that exist.",
                )
            )

        # THREE STATES, AND THE ROW THAT KEEPS THEM APART. `catalogued` and `unverified`
        # answer different questions and an entry that blurs them is the failure this
        # block exists for: "nobody has measured this yet, refuse until someone does" and
        # "there is no catalog and there never will be" have opposite remedies, and a
        # single flag serving both makes every `misc` capture read as a fault while a
        # genuinely unmeasured game hides among them.
        #
        # Provable from the literal alone, which is why it blocks: an entry is in exactly
        # one of the three states below, and each state fixes the shape of the same four
        # fields.
        catalogued = bool(entry.get("catalogued"))
        unverified = bool(entry.get("unverified"))
        product_line = entry.get("product_line")
        aspect = entry.get("card_aspect")

        if not catalogued:
            if unverified:
                findings.append(
                    Finding(
                        where,
                        "catalogued is False AND unverified is True. These are different "
                        "states with opposite remedies — unverified is a measurement "
                        "somebody owes, uncatalogued is the finished answer for a game "
                        "that spans several product lines at once. An entry claiming both "
                        "tells a consumer to wait for an export that is not coming.",
                    )
                )
            if product_line is not None:
                findings.append(
                    Finding(
                        where,
                        f"catalogued is False but product_line is {product_line!r}. It must "
                        f"be None: a game with no catalog has no `Product Line` cell, and "
                        f"None is not a str, so no export row can ever compare equal to it. "
                        f"An empty string is both a value a row could carry and the value "
                        f"an unverified entry uses, which collapses the two states on the "
                        f"one field that most needs to tell them apart.",
                    )
                )
            for field in ("rarities", "finishes", "finish_by_rarity", "condition_by_finish"):
                if entry.get(field):
                    findings.append(
                        Finding(
                            where,
                            f"catalogued is False but {field} is not empty. There is no "
                            f"export to author it against and none is coming, so a value "
                            f"here was reasoned out rather than measured.",
                        )
                    )
            if entry.get("join_key") != NOT_JOINED_STRATEGY:
                findings.append(
                    Finding(
                        where,
                        f"catalogued is False but join_key is {entry.get('join_key')!r}. It "
                        f"must be {NOT_JOINED_STRATEGY!r} — a game with no catalog never "
                        f"reaches one, and a strategy name that builds a key says the "
                        f"opposite to anything dispatching on it.",
                    )
                )
            if aspect is not None:
                findings.append(
                    Finding(
                        where,
                        f"catalogued is False but card_aspect is {aspect!r}. A game that "
                        f"spans product lines spans card sizes with them, so a single "
                        f"ratio here is a guess about whichever card is in hand. None is "
                        f"the honest value, and nothing detects or crops these cards.",
                    )
                )
        else:
            if aspect is None:
                findings.append(
                    Finding(
                        where,
                        "card_aspect is None on a catalogued game. None is reserved for the "
                        "uncatalogued case, where there is genuinely no single card size; a "
                        "game with one product line has one, measured off the cardboard.",
                    )
                )
            if unverified and rarities:
                findings.append(
                    Finding(
                        where,
                        "unverified is True but `rarities` is not empty. Unverified means no "
                        "export has been seen; a vocabulary that arrived without one is a "
                        "guess, which is the thing D22 refuses.",
                    )
                )
            if not unverified and not rarities:
                findings.append(
                    Finding(
                        where,
                        "`rarities` is empty but unverified is False and catalogued is True. "
                        "An empty vocabulary must say which of the two reasons it is empty "
                        "for, because every consumer refuses on one and a silent empty entry "
                        "reads as a game that works.",
                    )
                )
            if unverified and str(product_line or "").strip():
                findings.append(
                    Finding(
                        where,
                        f"unverified is True but product_line is {product_line!r}. The cell "
                        f"is measured off an export, so an entry that has one has seen one.",
                    )
                )
            if not unverified and not str(product_line or "").strip():
                findings.append(
                    Finding(
                        where,
                        "product_line is empty on a catalogued entry that is not marked "
                        "unverified.",
                    )
                )

    # The two export findings. Committed fixtures only — see the section note.
    by_line = observed_rarities(committed_only=True)
    accounted: Dict[str, Set[str]] = {}
    for entry in entries:
        line = str(entry.get("product_line") or "").strip()
        if not line:
            continue
        accounted.setdefault(line, set()).update(_claimed_by(entry))
        observed = by_line.get(line) or set()
        folded = {fold_cell(cell): cell for cell in observed}
        for authored in sorted(_claimed_by(entry)):
            if authored in observed:
                continue
            match = folded.get(fold_cell(authored))
            if match is not None:
                findings.append(
                    Finding(
                        f"{where_module} -> {entry.get('key')}",
                        f"rarity {authored!r} does not appear in any committed export, but "
                        f"{match!r} does and the two differ only in case or punctuation. "
                        f"The export's cell is the one that has to win — the string is "
                        f"joined on and rendered verbatim.",
                    )
                )

    checked = 0
    for line, cells in sorted(by_line.items()):
        for cell in sorted(cells):
            checked += 1
            if cell in (accounted.get(line) or set()):
                continue
            findings.append(
                Finding(
                    where_module,
                    f"a committed export carries `Product Line` {line!r} with `Rarity` "
                    f"{cell!r}, and no entry accounts for it. Add it to the game that "
                    f"claims it, or to another game's `rarities_not_claimed` if it belongs "
                    f"to a different capture choice sharing this product line.",
                )
            )

    report.add(
        "game vocabulary",
        MECHANICAL,
        findings,
        f"{len(entries)} games, {checked} export rarities accounted for",
        scanned=len(entries),
    )


def check_game_coverage(report: Report) -> None:
    """What the exports in view do not corroborate. Prints; never blocks.

    **Absence from one set proves nothing, and that is the whole reason this row is
    separate.** `Promo`, `Radiant Rare`, `Amazing Rare` and every pre-SV rarity are
    legitimately missing from an SV09 fixture, and D23 REQUIRES `finish_by_rarity` to
    exceed what any one export stocks — SV09 carries no plain Near Mint `Rare` row, and a
    matrix narrowed to that observation would make a real plain-NM `Rare` stack unclaimable
    behind an unselectable chip. So the excess is a question by construction, and the row
    that blocks is `matrix superset`, which asks the same question the other way round.

    Opt-in `PKMNSCAN_EXPORTS` files feed this row and only this row. An operator with a
    full-catalog export gets every question asked against it without any of them being able
    to stop a commit on a machine that does not have the file.
    """
    data, findings = game_entries()
    if findings:
        report.add("game coverage", ADVISORY, findings)
        return

    coverage_allow = load_game_coverage_allowlist()
    consumed: Set[str] = set()

    entries = list(data["GAMES"])
    where_module = rel(GAMES_MODULE)
    sources = export_facts()
    by_line = observed_rarities(committed_only=False)
    triples = observed_triples(committed_only=False)

    accounted: Dict[str, Set[str]] = {}
    for entry in entries:
        key = entry.get("key")
        where = f"{where_module} -> {key}"
        line = str(entry.get("product_line") or "").strip()
        if not line:
            continue  # an unverified game authors nothing to corroborate
        observed = by_line.get(line) or set()
        accounted.setdefault(line, set()).update(_claimed_by(entry))
        if not observed:
            findings.append(
                Finding(
                    where,
                    f"`Product Line` {line!r} appears in no export in view. Set "
                    f"{EXPORTS_ENV} to a colon-separated list of exports to widen this.",
                )
            )
            continue
        for authored in sorted(_claimed_by(entry) - observed):
            findings.append(
                Finding(where, f"rarity {authored!r} appears in no export in view.")
            )
        conditions = entry.get("condition_by_finish") or {}
        for finish, condition in sorted(conditions.items()):
            if not any(
                line_seen == line and cond == condition for line_seen, _, cond in triples
            ):
                findings.append(
                    Finding(
                        where,
                        f"condition {condition!r} (finish {finish!r}) appears in no export "
                        f"in view.",
                    )
                )
        for rarity, allowed in sorted((entry.get("finish_by_rarity") or {}).items()):
            for finish in allowed or ():
                condition = conditions.get(finish)
                if condition is None:
                    continue
                if (line, rarity, condition) not in triples:
                    pair = f"{key} {rarity}"
                    if pair in coverage_allow:
                        consumed.add(pair)
                        continue
                    findings.append(
                        Finding(
                            where,
                            f"finish_by_rarity allows {rarity} / {finish}, and no export in "
                            f"view stocks {rarity!r} as {condition!r}. Expected where the "
                            f"matrix is deliberately a superset (D23); a question, not a "
                            f"defect.",
                        )
                    )

    for facts in sources:
        if facts.committed:
            continue  # the blocking row already answered for these
        for line, cells in sorted(facts.rarities.items()):
            for cell in sorted(cells - (accounted.get(line) or set())):
                findings.append(
                    Finding(
                        facts.source,
                        f"`Product Line` {line!r} / `Rarity` {cell!r} is accounted for by no "
                        f"entry. Read from {EXPORTS_ENV}, so this asks rather than blocks.",
                    )
                )

    committed = sum(1 for facts in sources if facts.committed)
    report.add(
        "game coverage",
        ADVISORY,
        findings,
        f"{committed} committed exports, {len(sources) - committed} opt-in",
        scanned=len(sources),
    )

    stale = [
        Finding(
            rel(GAME_COVERAGE_ALLOWLIST),
            f"`{pair}` is allowed but `game coverage` would not ask about it anyway "
            f"(the pair is no longer an unproven finish_by_rarity cell) — delete the "
            f"line.\nIt was allowed because: {reason or '(no reason recorded)'}",
        )
        for pair, reason in sorted(coverage_allow.items())
        if pair not in consumed
    ]
    report.add(
        "game coverage allowlist",
        MECHANICAL,
        stale,
        f"{len(coverage_allow)} entries, none stale",
        scanned=len(allowed),
    )


def check_matrix_superset(report: Report) -> None:
    """An observed (rarity, finish) pair that `finish_by_rarity` does not allow.

    **This is the row that keeps D23's unselectable finish chips honest, and it only ever
    reads in one direction.** The capture screen renders a chip excluded by a rarity claim
    as unselectable rather than hidden; that is safe while the matrix is a superset of
    reality and a trap the moment it is not, because the operator would have no way to say
    what is true about the card in their hand. So a pair an export PROVES exists and the
    matrix omits is a defect and blocks, while a pair the matrix allows and no export
    stocks is a question and belongs to `game coverage`.

    The finish is derived from the export's own `Condition` cell through the entry's
    `condition_by_finish`, inverted. A condition that maps to no finish — a graded or
    vintage string, which D12 puts out of scope — is skipped rather than reported: this row
    is about the matrix, and a condition the entry never claimed is not evidence about it.

    Committed fixtures only, like every blocking row here.
    """
    data, findings = game_entries()
    if findings:
        report.add("matrix superset", MECHANICAL, findings)
        return

    entries = list(data["GAMES"])
    where_module = rel(GAMES_MODULE)
    triples = observed_triples(committed_only=True)
    checked = 0

    for entry in entries:
        line = str(entry.get("product_line") or "").strip()
        rarities = set(entry.get("rarities") or ())
        if not line or not rarities:
            continue
        finish_by_condition = {
            condition: finish
            for finish, condition in (entry.get("condition_by_finish") or {}).items()
        }
        matrix = entry.get("finish_by_rarity") or {}
        for line_seen, rarity, condition in sorted(triples):
            if line_seen != line or rarity not in rarities:
                continue
            finish = finish_by_condition.get(condition)
            if finish is None:
                continue
            checked += 1
            if finish in set(matrix.get(rarity) or ()):
                continue
            findings.append(
                Finding(
                    f"{where_module} -> {entry.get('key')}",
                    f"a committed export stocks {rarity!r} as {condition!r}, so "
                    f"{rarity} / {finish} exists — and finish_by_rarity[{rarity!r}] is "
                    f"{tuple(matrix.get(rarity) or ())}. The matrix may only ever be a "
                    f"SUPERSET of what an export proves: widen it, never narrow it, or the "
                    f"capture screen renders that finish unselectable for a stack that "
                    f"really is that finish.",
                )
            )

    report.add(
        "matrix superset",
        MECHANICAL,
        findings,
        f"{checked} observed rarity/finish pairs, all allowed",
        scanned=checked,
    )


def check_join_key_shape(report: Report) -> None:
    """A `join_key` the export's own `Number` cells prove can never match a row.

    **The one thing about a join strategy an export can settle, and it settles it
    absolutely.** `number_and_printed_total` composes its key as
    `zfill(3)(number) + "/" + printedTotal`, so every key it can ever produce contains a
    `/`. `pipeline/join.py` indexes the catalog on the export's `Number` cell verbatim.
    Therefore: if not one non-blank `Number` cell under a game's `Product Line` contains a
    `/`, that strategy matches nothing, for every card, forever. There is no context this
    script is missing and no export that could make it come out differently — which is
    D16's test for mechanical, so it blocks.

    **One direction only, deliberately.** The reverse — a game on `printed_code` whose
    cells all carry denominators — is NOT a finding, because matching the printed
    identifier verbatim works perfectly well on `179/298`. Riftbound is exactly that case
    and it is the right authoring: 9540 of its rows carry a denominator and 450 do not
    (`R04`, `T02 // T03`), a per-game field holds one strategy, and the verbatim match is
    the only one of the two that covers both shapes. A row that flagged it would be
    punishing the entry for being correct.

    **`name_only` and `not_joined` are skipped rather than reasoned about.** A code card's
    rows are the blank-`Number` ones, so a `Number` column says nothing about them; a
    `misc` card has no product line to look up at all. Neither absence is evidence.

    **This row was written because One Piece would have been authored wrong without it.**
    Its whole catalogue is `OP15-079`, `EB04-042`, `ST26-005`, `P-105` — no denominator
    anywhere, and `printed_total` is a field with no referent for that game. Inheriting
    Pokemon's strategy is the obvious default and it would have produced a run that joined
    zero rows and blamed the export.

    Committed fixtures only, like every blocking row here.
    """
    data, findings = game_entries()
    if findings:
        report.add("join key shape", MECHANICAL, findings)
        return

    entries = list(data["GAMES"])
    where_module = rel(GAMES_MODULE)
    by_line: Dict[str, Set[str]] = {}
    for facts in export_facts():
        if not facts.committed:
            continue
        for line, cells in facts.numbers.items():
            by_line.setdefault(line, set()).update(cells)

    checked = 0
    for entry in entries:
        line = str(entry.get("product_line") or "").strip()
        strategy = entry.get("join_key")
        if not line or strategy != COMPOSED_STRATEGY:
            continue
        observed = by_line.get(line) or set()
        if not observed:
            continue  # no `Number` cells in view: no evidence, no finding
        checked += 1
        if any("/" in cell for cell in observed):
            continue
        findings.append(
            Finding(
                f"{where_module} -> {entry.get('key')}",
                f"join_key is {COMPOSED_STRATEGY!r}, which composes every key it produces "
                f"as `number + \"/\" + printedTotal` — and not one of the "
                f"{len(observed)} non-blank `Number` cells a committed export carries for "
                f"`Product Line` {line!r} contains a `/`. The catalog is indexed on that "
                f"cell verbatim, so this strategy matches nothing for every card of this "
                f"game. A catalogue with no denominator needs the strategy that matches "
                f"the printed identifier as printed.",
            )
        )

    report.add(
        "join key shape",
        MECHANICAL,
        findings,
        f"{checked} composed-key games checked against export Number cells",
        scanned=checked,
    )
