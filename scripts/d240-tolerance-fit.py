#!/usr/bin/env python3
"""Fits D240's proposed name-agreement tolerance against the owner's own hand answers
rather than borrowing D239's 0.82 unmeasured for this shape. The result is recorded in the
decision entry `D251`, measured 2026-09-23 on the owner's store.

THE LABELS ARE SELECTED BY THE GATE THEY FIT. A `name_disputed` entry exists only because
`pipeline/join.py:name_disputes` fired, which is ratio below `NAME_DISPUTE_SIMILARITY` and no
containment. So no label can sit at or above that constant, and the sweep is silent there.
The store-wide listing below is what speaks for that band, read by name.

NO NETWORK CALL, EVER. NO STORE ON DISK IS NEEDED TO RUN THIS FILE. With no `--store`, it
proves the sweep logic itself against a small fixture built in this file (the same
containment/misread pairs `pipeline/join.py`'s own `NAME_DISPUTE_SIMILARITY` comment already
cites), including a mutation arm — the guard is trusted only once it has been seen to fail on
the defect it guards (`CLAUDE.md`'s own rule). With `--store <path>`, it reads that store
READ-ONLY (`store/db.py:open_read_only`, the same door `cli/cmd_sku_contradictions.py` uses) and
refuses outright if the path does not exist — it never silently measures nothing.

WHAT IT MEASURES, WITH A REAL STORE. Three things, and none of them touches a network:

1. `pipeline/sku_number_contradictions.py:find_disagreements` reproduced over the real
   `cards` table (D242's own function, imported rather than re-implemented). This answers
   the store-wide contradiction counts (150 SKUs, 144 Riftbound, the denominator-mismatch
   split) WITHOUT the live catalogue D242's own 131-of-144 name-settle figure needed — that
   one figure stays D242's, cited, never re-derived here, exactly as D242 itself declines to
   re-derive it.

2. Of the contradicting SKUs, how many have at least one member card that was independently
   taken through the review queue and hand-cleared (`store/queues.py`'s `cleared_by_human`)
   — a real human answer, unconnected to any catalogue-name heuristic. This is the "115
   answered SKUs" figure a caller may have heard quoted; this script recomputes it rather
   than trusting the quote.

3. THE ACTUAL LABELLED SET FOR D240's QUESTION. Every `reason='name_disputed'` queue entry
   that is hand-cleared and carries exactly one candidate (the number's own row) is a case
   where a human was shown a number-matched catalog row whose NAME did not agree with the
   model's own reading, and then said which one was right. The card's own FINAL stored
   `sku` (post-answer) tells us whether the human accepted the number's candidate (name
   disagreement was a false alarm — a real card, oddly or differently named in the export)
   or rejected it for a different SKU entirely (name disagreement was a real misread). That
   is ground truth this script did not invent and does not need the photograph for — the
   photograph is what the human already looked at.

   Entries offering MORE than one candidate are excluded from the sweep (`name_alternatives`
   already narrows those a different way — see the module's own comment) and reported
   separately, never silently dropped.

THE SWEEP is run over the labelled set from (3) at every 0.01 step the caller asks for
(default 0.70-0.95, the range named in the brief this script answers), with and without a
substring-containment escape, and reports at each point: how many known misreads it would
still catch, how many known-correct answers it would needlessly re-flag, and the two counts
never conflated into one "accuracy" figure — the asymmetry argument this script exists to
support treats them as different costs, not one score.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import tcgcsv  # noqa: E402
from store import db  # noqa: E402
from pipeline.join import (  # noqa: E402
    NAME_DISPUTE_SIMILARITY,
    Catalog,
    IdentifiedCard,
    Position,
    _name_compare_key,
    name_disputes,
)
from pipeline.sku_number_contradictions import (  # noqa: E402
    NumberRecord,
    find_disagreements,
)

DEFAULT_LOW = 0.70
DEFAULT_HIGH = 0.95
DEFAULT_STEP = 0.01


# --------------------------------------------------------------------- the comparison


def ratio_and_containment(read_name: Optional[str], cand_name: Optional[str]) -> Tuple[float, bool]:
    """The same fold and the same metric `pipeline/join.py:name_disputes` already uses —
    `_name_compare_key` (NFKD-fold, catalog-side qualifier strip) then `difflib.
    SequenceMatcher.ratio()`. A tolerance fitted on a different comparison shape (D239's
    `flag_near_duplicate_names` compares two STORED names to each other, never a stored name
    to a catalog row) is not evidence about this one; this script reuses the join's own
    fold so the number this script fits is fitted on the shape it will actually gate.
    """
    read = _name_compare_key(read_name)
    cand = _name_compare_key(cand_name, catalog_side=True)
    if not read or not cand:
        return 0.0, False
    ratio = SequenceMatcher(None, read, cand).ratio()
    short, long = sorted((read, cand), key=len)
    contains = bool(short) and short in long
    return ratio, contains


def would_trust(ratio: float, contains: bool, tolerance: float, use_containment: bool) -> bool:
    """True = the number match is trusted as-is (no extra review). False = flagged, routed
    to review as a MISS, exactly D240's proposed rung. Containment always passes when the
    caller asks for that arm — the mirror of `name_disputes`'s own `short in long` escape.
    """
    if use_containment and contains:
        return True
    return ratio >= tolerance


# --------------------------------------------------------------------- store readers


def _read_only(store_path: Path) -> sqlite3.Connection:
    if not store_path.is_file():
        raise FileNotFoundError(
            f"no store at {store_path} — this script refuses to run against nothing "
            "rather than silently measuring an empty store"
        )
    return db.open_read_only(store_path)


def sku_contradiction_counts(conn: sqlite3.Connection) -> Dict[str, object]:
    """D242's own `find_disagreements`, reproduced over the real `cards` table. No network:
    this is the store contradicting itself, exactly as `pipeline/sku_number_contradictions.
    py`'s own module docstring says it can be found.
    """
    by_sku: Dict[str, List[NumberRecord]] = {}
    for key, sku, name, number, set_name, game in conn.execute(
        "SELECT key, sku, name, number, set_name, game FROM cards "
        "WHERE sku IS NOT NULL AND sku != ''"
    ):
        by_sku.setdefault(str(sku), []).append(
            NumberRecord(key=str(key), number=number, name=name, set_name=set_name, game=game)
        )
    disagreements = find_disagreements(by_sku)
    denom = [d for d in disagreements.values() if d.denominator_mismatch]
    same = [d for d in disagreements.values() if not d.denominator_mismatch]
    by_game: Dict[str, int] = {}
    for d in disagreements.values():
        by_game[d.game or "unknown"] = by_game.get(d.game or "unknown", 0) + 1

    cleared_positions = {
        key for (key,) in conn.execute("SELECT key FROM queues WHERE cleared_by_human=1")
    }
    answered_skus = sum(
        1
        for d in disagreements.values()
        if any(c.key in cleared_positions for c in d.cards)
    )

    return {
        "total_skus_with_sku": sum(1 for _ in by_sku),
        "total_disagreeing": len(disagreements),
        "by_game": by_game,
        "denominator_mismatch": len(denom),
        "same_denominator": len(same),
        "answered_skus": answered_skus,
        "disagreements": disagreements,
    }


@dataclass(frozen=True)
class LabeledCase:
    key: str
    read_name: str
    cand_name: str
    ratio: float
    contains: bool
    agrees: bool  # True: human confirmed the number's own candidate was correct


def load_labels(conn: sqlite3.Connection, closed: Dict[str, str]) -> Tuple[List[LabeledCase], int]:
    """Every hand-cleared `name_disputed` entry with exactly one candidate. Returns the
    labelled cases and the count of multi-candidate entries excluded (reported, never
    silently dropped).
    """
    rows = conn.execute(
        "SELECT key, payload FROM queues WHERE reason='name_disputed' AND cleared_by_human=1"
    ).fetchall()
    cases: List[LabeledCase] = []
    excluded_multi = 0
    for key, payload in rows:
        if closed.get(key) != "answered":
            continue  # a stand-down closed it: no answer, so no label
        record = json.loads(payload)
        candidates = record.get("candidates", [])
        if len(candidates) != 1:
            excluded_multi += 1
            continue
        read_name = record.get("read", {}).get("name")
        cand_name = candidates[0].get("name")
        cand_sku = candidates[0].get("sku")
        final = conn.execute("SELECT sku FROM cards WHERE key=?", (key,)).fetchone()
        final_sku = final[0] if final else None
        if not read_name or not cand_name or final_sku is None:
            excluded_multi += 0  # not a multi-candidate exclusion; counted separately below
            continue
        ratio, contains = ratio_and_containment(read_name, cand_name)
        cases.append(
            LabeledCase(
                key=key,
                read_name=read_name,
                cand_name=cand_name,
                ratio=ratio,
                contains=contains,
                agrees=(final_sku == cand_sku),
            )
        )
    return cases, excluded_multi


def clearing_events(conn: sqlite3.Connection) -> Dict[str, str]:
    """Which event last closed each position's question: `answered` or `stood_down`.

    `cleared_by_human` HAS TWO MEANINGS (`store/queues.py`'s docstring). A stand-down (D37)
    writes nothing to the card, so its final SKU still equals the number's candidate and
    would read as agreement. Only an `answered` close is a label. An `unanswered` event
    withdraws the answer before it.
    """
    last: Dict[str, str] = {}
    for event, position in conn.execute(
        "SELECT event, position FROM events "
        "WHERE event IN ('answered', 'stood_down', 'unanswered') ORDER BY id"
    ):
        if event == "unanswered":
            last.pop(position, None)
        else:
            last[position] = event
    return last


def _best_against(read_name: str, names: List[str]) -> Tuple[float, bool]:
    """The highest ratio and any containment over every row. `name_disputes` trusts a
    number when ANY of its rows agrees, so the gate reads the best row, never the first.
    """
    best, contains = 0.0, False
    for name in names:
        ratio, inside = ratio_and_containment(read_name, name)
        best, contains = max(best, ratio), contains or inside
    return best, contains


def load_other_reason_labels(
    conn: sqlite3.Connection, closed: Dict[str, str]
) -> Tuple[List[LabeledCase], List[LabeledCase]]:
    """Answered entries of every OTHER reason whose read name disputes every candidate.

    The join runs `name_disputes` only when `not resolution.needs_review`, so a card queued
    for another reason never had the name check. Two groups, never merged:

    - the answer is a SKU outside the candidates: the number's rows were wrong, and the
      name was right. A case the rung must flag (`agrees=False`).
    - the answer is one of the number's own rows, under a different name. The owner
      accepted it, but a peer session reports all of these as misreads. Only the
      photograph can settle it, so these are UNKNOWN and enter no sweep count.
    """
    rejected: List[LabeledCase] = []
    accepted: List[LabeledCase] = []
    for key, payload in conn.execute(
        "SELECT key, payload FROM queues "
        "WHERE reason != 'name_disputed' AND cleared_by_human=1"
    ):
        if closed.get(key) != "answered":
            continue
        record = json.loads(payload)
        read_name = record.get("read", {}).get("name")
        candidates = record.get("candidates", [])
        rows = [{tcgcsv.NAME_COLUMN: c.get("name") or ""} for c in candidates]
        if not read_name or not rows or not name_disputes(read_name, rows):
            continue
        final = conn.execute("SELECT sku FROM cards WHERE key=?", (key,)).fetchone()
        if final is None or not final[0]:
            continue
        ratio, contains = _best_against(read_name, [c.get("name") or "" for c in candidates])
        inside = str(final[0]) in {str(c.get("sku")) for c in candidates}
        case = LabeledCase(key, read_name, "; ".join(sorted({c.get("name") or "" for c in candidates})),
                           ratio, contains, agrees=inside)
        (accepted if inside else rejected).append(case)
    return rejected, accepted


def store_wide(conn: sqlite3.Connection, exports: Path) -> List[Tuple[str, str, float, bool]]:
    """Every numbered, named card, taken through the join's own `Catalog.candidates` against
    the newest cached export of its game, read-only. Returns (key, state, best ratio,
    containment) for each card whose rows came from the NUMBER, never from a name rung.
    """
    catalogs = {}
    for game_dir in sorted(p for p in exports.iterdir() if p.is_dir()):
        files = sorted(game_dir.glob("*.csv"))
        if files:
            catalogs[game_dir.name] = Catalog.from_export(tcgcsv.read_export(files[-1]), game_dir.name)
    out = []
    for key, name, number, game, hint, state, payload in conn.execute(
        "SELECT key, name, number, game, set_hint, state, payload FROM cards"
    ):
        if not name or not number or game not in catalogs:
            continue
        box, index = (int(part) for part in str(key).split("/"))
        card = IdentifiedCard(
            position=Position(box, index), name=name, number=number,
            printed_total=json.loads(payload).get("printed_total"), game=game, set_hint=hint,
        )
        found = catalogs[game].candidates(card)
        if not found.rows or found.lookup.startswith("name"):
            continue
        ratio, contains = _best_against(name, [r.get(tcgcsv.NAME_COLUMN) or "" for r in found.rows])
        out.append((key, state, ratio, contains))
    return out


# --------------------------------------------------------------------- the sweep


@dataclass(frozen=True)
class SweepRow:
    tolerance: float
    misreads_caught: int
    misreads_total: int
    correct_wrongly_flagged: int
    correct_total: int

    @property
    def misreads_missed(self) -> int:
        return self.misreads_total - self.misreads_caught

    @property
    def correct_released(self) -> int:
        return self.correct_total - self.correct_wrongly_flagged


def sweep(cases: List[LabeledCase], low: float, high: float, step: float, use_containment: bool) -> List[SweepRow]:
    misreads = [c for c in cases if not c.agrees]
    correct = [c for c in cases if c.agrees]
    rows: List[SweepRow] = []
    n = round((high - low) / step) + 1
    for i in range(n):
        tolerance = round(low + i * step, 10)
        caught = sum(
            1 for c in misreads if not would_trust(c.ratio, c.contains, tolerance, use_containment)
        )
        wrongly_flagged = sum(
            1 for c in correct if not would_trust(c.ratio, c.contains, tolerance, use_containment)
        )
        rows.append(
            SweepRow(
                tolerance=tolerance,
                misreads_caught=caught,
                misreads_total=len(misreads),
                correct_wrongly_flagged=wrongly_flagged,
                correct_total=len(correct),
            )
        )
    return rows


# --------------------------------------------------------------------- self-test (no store)

# The documented pairs from `pipeline/join.py`'s own `NAME_DISPUTE_SIMILARITY` comment —
# real, already-measured legitimate near-misses this codebase has cited before, none
# reproduced from the owner's store. Alongside one clear misread (`1/51` on the real store,
# named in D240 and D242 both, quoted here as plain strings — not read from any file).
_FIXTURE_LEGITIMATE = [
    ("Corfish", "Corphish"),
    ("Piltrovan Forge", "Piltovan Forge"),
    ("The Runiation", "The Ruination"),
    ("Steraks Gage", "Sterak's Gage"),
]
_FIXTURE_MISREADS = [
    ("Irelia, Blade Dancer", "Forgefire Cape"),
    ("Wizened Elder", "Defy"),
]


def _fixture_cases() -> List[LabeledCase]:
    cases = []
    for read, cand in _FIXTURE_LEGITIMATE:
        ratio, contains = ratio_and_containment(read, cand)
        cases.append(LabeledCase("fixture", read, cand, ratio, contains, agrees=True))
    for read, cand in _FIXTURE_MISREADS:
        ratio, contains = ratio_and_containment(read, cand)
        cases.append(LabeledCase("fixture", read, cand, ratio, contains, agrees=False))
    return cases


def run_selftest() -> int:
    print("D240 TOLERANCE FIT — SELF-TEST (no store, no network)")
    cases = _fixture_cases()
    failures = 0

    # At 0.8 (the value already fitted and running in `pipeline/join.py:NAME_DISPUTED`),
    # every legitimate near-miss above must be trusted and every misread must be flagged.
    for case in cases:
        trusted = would_trust(case.ratio, case.contains, 0.8, use_containment=True)
        expect_trusted = case.agrees
        ok = trusted == expect_trusted
        failures += 0 if ok else 1
        print(
            f"  {'ok' if ok else 'FAIL'}   {case.read_name!r} vs {case.cand_name!r}  "
            f"ratio={case.ratio:.3f} contains={case.contains} trusted={trusted} "
            f"expected={expect_trusted}"
        )

    # MUTATION ARM — a `would_trust` that always trusts must fail this exact assertion, or
    # the assertion above is not testing what it claims to.
    def _broken_would_trust(ratio, contains, tolerance, use_containment):
        return True

    broken_failures = sum(
        1 for case in cases if _broken_would_trust(case.ratio, case.contains, 0.8, True) != case.agrees
    )
    mutation_ok = broken_failures == len(_FIXTURE_MISREADS)
    print(
        f"  {'ok' if mutation_ok else 'FAIL'}   mutation arm: an always-trust stub "
        f"misclassifies exactly the {len(_FIXTURE_MISREADS)} misread fixture(s) "
        f"({broken_failures} found)"
    )
    failures += 0 if mutation_ok else 1

    print()
    if failures:
        print(f"VERDICT: {failures} failure(s).")
        return 1
    print("VERDICT: self-test passes. Run with --store <path> for the real measurement.")
    return 0


# --------------------------------------------------------------------- store-backed report


def run_report(store_path: Path, low: float, high: float, step: float) -> int:
    conn = _read_only(store_path)

    print(f"D240 TOLERANCE FIT  {store_path}")
    print()
    counts = sku_contradiction_counts(conn)
    print("SKU NUMBER CONTRADICTIONS (D242's own function, reproduced, no network):")
    print(f"  {counts['total_skus_with_sku']} SKUs carry a stored number")
    print(f"  {counts['total_disagreeing']} SKU(s) disagree after normalizing")
    print(f"  by game: {counts['by_game']}")
    print(f"  {counts['denominator_mismatch']} disagree on the denominator alone (no catalogue needed)")
    print(f"  {counts['same_denominator']} share a denominator (D242's own 131-of-144 name-settle "
          "figure needs the live catalogue and is NOT re-derived here)")
    print(f"  {counts['answered_skus']} of the {counts['total_disagreeing']} disagreeing SKUs have "
          "at least one member card independently hand-cleared in the review queue")
    print()

    closed = clearing_events(conn)
    cases, excluded_multi = load_labels(conn, closed)
    misreads = [c for c in cases if not c.agrees]
    correct = [c for c in cases if c.agrees]
    print("LABELLED SET (hand-answered `name_disputed` queue entries, single candidate):")
    print(f"  {len(cases)} usable labelled case(s), {excluded_multi} excluded "
          "(multiple candidates offered — a different, already-narrowed rung)")
    print(f"  {len(misreads)} confirmed MISREAD (human rejected the number's own candidate)")
    print(f"  {len(correct)} confirmed CORRECT (human accepted the number's own candidate "
          "despite the name disagreement)")
    if misreads:
        print(f"  misread ratio range: {min(c.ratio for c in misreads):.3f} - "
              f"{max(c.ratio for c in misreads):.3f}")
    if correct:
        print(f"  correct-match ratio range: {min(c.ratio for c in correct):.3f} - "
              f"{max(c.ratio for c in correct):.3f}")
    print(f"  containment (short-in-long) ever true in this set: "
          f"{sum(1 for c in cases if c.contains)} of {len(cases)}")
    print()

    for use_containment, label in ((False, "ratio alone"), (True, "ratio OR containment")):
        print(f"SWEEP {low:.2f}-{high:.2f} step {step:.2f}  ({label}):")
        print(f"  {'tol':>5}  {'misreads caught':>16}  {'misreads MISSED':>16}  "
              f"{'correct wrongly flagged':>24}  {'correct released':>17}")
        rows = sweep(cases, low, high, step, use_containment)
        for row in rows:
            print(
                f"  {row.tolerance:>5.2f}  {row.misreads_caught:>7}/{row.misreads_total:<8}  "
                f"{row.misreads_missed:>16}  {row.correct_wrongly_flagged:>15}/{row.correct_total:<8}  "
                f"{row.correct_released:>17}"
            )
        print()

    rejected, accepted = load_other_reason_labels(conn, closed)
    print("OTHER-REASON ANSWERS WHOSE READ NAME DISPUTES EVERY CANDIDATE (never name-checked):")
    print(f"  {len(rejected)} answered OUTSIDE the candidates (name right, number wrong)")
    for c in rejected:
        print(f"    {c.key:8} ratio={c.ratio:.3f}  {c.read_name!r} vs {c.cand_name!r}")
    print(f"  {len(accepted)} answered WITH a number row under another name — UNKNOWN, "
          "no sweep count")
    for c in accepted:
        print(f"    {c.key:8} ratio={c.ratio:.3f}  {c.read_name!r} vs {c.cand_name!r}")
    print()

    exports = store_path.parent / ".exports"
    if exports.is_dir():
        wide = store_wide(conn, exports)
        print(f"STORE-WIDE: {len(wide)} numbered cards matched by NUMBER in the cached exports")
        print(f"  {'tol':>5}  {'flagged, all':>13}  {'flagged, on hand':>17}  "
              f"{'vs today (0.80)':>16}")
        today = sum(1 for _, _, r, k in wide if not would_trust(r, k, NAME_DISPUTE_SIMILARITY, True))
        n = round((high - low) / step) + 1
        for i in range(n):
            t = round(low + i * step, 10)
            flagged = [(s, r) for _, s, r, k in wide if not would_trust(r, k, t, True)]
            on_hand = sum(1 for s, _ in flagged if s == "identified")
            print(f"  {t:>5.2f}  {len(flagged):>13}  {on_hand:>17}  {len(flagged) - today:>+16}")
        print()
    else:
        print(f"STORE-WIDE: no exports at {exports}, volume NOT measured")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--store", type=Path, default=None,
                         help="path to a store.sqlite to measure against, read-only")
    parser.add_argument("--low", type=float, default=DEFAULT_LOW)
    parser.add_argument("--high", type=float, default=DEFAULT_HIGH)
    parser.add_argument("--step", type=float, default=DEFAULT_STEP)
    args = parser.parse_args()

    if args.store is None:
        return run_selftest()
    try:
        return run_report(args.store, args.low, args.high, args.step)
    except FileNotFoundError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
