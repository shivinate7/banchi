#!/usr/bin/env python3
"""One-time repair preview for the three cards D252's amendment names, all three corrected
through `POST /inventory/<box>/<index>/correct` before that fix landed.

PREVIEW BY DEFAULT AND READ-ONLY BY CONSTRUCTION. The default run never imports
`store.db` or `store.Store`, and never opens `inventory/store.sqlite` for anything but a
`mode=ro` connection — the same defence `scripts/price-postings-recovery.py` already uses,
for the identical reason: a script meant to run against the owner's real store must not be
able to write even by accident, and `db.connect`'s migration path is the accident this
avoids. It reads `runs/<run>/manifest.json` and the export CSV it names as plain files.
Nothing here calls `do_correct_answer`, opens a write lock, or touches a listing.

THIS SCRIPT WAS WRITTEN BY THE BUILDER SESSION AND WAS NOT RUN AGAINST THE OWNER'S STORE.
`--home` has no default for that reason — it must be typed, so a bare invocation cannot
reach the real inventory directory by accident. The orchestrator runs it, reads the report,
and only then decides whether `--write --confirm` is warranted.

THE THREE CARDS, hard-coded, because a repair over a small NAMED set is not a general
route:

    4/176   ->  9197749   (Daisy!, 196/219, Epic)
    4/442   ->  9191942   (Pyke, Returned (Alternate Art), 145a/219, Showcase)
    6/563   ->  9189327   (Frigid Jewel, 074/219, Uncommon)

WHY NOT undo-then-redo, THE ROUTE'S OWN MECHANISM. `{"undo": true}` then a second
`{"sku": <same sku>}` would run the now-fixed `do_correct_answer` and set rarity/number
correctly. It cannot work: the second call is choosing the SKU the card already carries,
and `do_correct_answer` refuses that outright as `sku_unchanged` — "this one was answered
correctly the first time". Undo-then-redo could only ever apply here by correcting to a
placeholder SKU and back, which moves a listing count TWICE for a card whose sku is
already right, for a field the route never needed a SKU change to fix. This script checks
whether that detour would even be ALLOWED to start — this asks the SAME `undo_too_late`
question `_reverse_correction`'s own guard asks, so the report below states it — and finds
it is worse than unneeded: it risks a real listing-count edit for zero benefit, on the
live server, over a bug that has nothing to do with listing counts.

THE SMALLEST CORRECT MECHANISM: read each card's OWN catalog row for the SKU it already
carries (the same lookup `_catalog_answer` runs, over the same run and export the original
correction read from), and set `rarity`, `number` and `printed_total` from it — nothing
else. `sku`, `condition`, `set_name` and `name` are already correct on all three (the
owner's own report says so) and stay untouched. No listing moves, because nothing about a
listing is wrong here.

USAGE
    python3 scripts/correction-rarity-number-repair.py --home <inventory-parent-dir>
    python3 scripts/correction-rarity-number-repair.py --home <inventory-parent-dir> \\
        --write --confirm

`--home` is the checkout's home directory (the one holding `inventory/` and `runs/`), the
same meaning `PKMNSCAN_HOME` carries elsewhere. `--write --confirm` (both required) opens
`Store().write()` — the ordinary primitive, not a second one — and sets the three fields
inside one transaction per card, logging a `rarity_number_repaired` history line that
carries the pair it overwrote, in `restores_to`'s own shape, so the repair is itself
undoable by hand if it is ever wrong. `--write` alone previews the write's own report
without applying it, the same two-flag shape `make merge` and `pkmnscan queue refresh`
already use elsewhere in this repo.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import join, tcgcsv  # noqa: E402
from pipeline.join import Catalog  # noqa: E402

DB_NAME = "store.sqlite"

# THE THREE CARDS, hard-coded — see the module docstring for why.
CASES = (
    {"box": 4, "index": 176, "expected_sku": "9197749", "expected_name": "Daisy!"},
    {
        "box": 4,
        "index": 442,
        "expected_sku": "9191942",
        "expected_name": "Pyke, Returned (Alternate Art)",
    },
    {"box": 6, "index": 563, "expected_sku": "9189327", "expected_name": "Frigid Jewel"},
)


def _ro_connect(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _read_card(conn: sqlite3.Connection, box: int, index: int) -> dict:
    key = f"{int(box)}/{int(index)}"
    row = conn.execute(
        "SELECT sku, condition, set_name, rarity, name, number, game, run, "
        "number_key, number_display, payload FROM cards WHERE key = ?",
        (key,),
    ).fetchone()
    if row is None:
        return {"key": key, "found": False}
    (
        sku,
        condition,
        set_name,
        rarity,
        name,
        number,
        game,
        run,
        number_key,
        number_display,
        payload_text,
    ) = row
    try:
        payload = json.loads(payload_text)
    except (TypeError, ValueError):
        payload = {}
    return {
        "key": key,
        "found": True,
        "sku": sku,
        "condition": condition,
        "set_name": set_name,
        "rarity": rarity,
        "name": name,
        "number": number,
        "printed_total": payload.get("printed_total"),
        "game": game,
        "run": run,
        "number_key": number_key,
        "number_display": number_display,
    }


def _listing_hold(conn: sqlite3.Connection, sku: str) -> dict:
    row = conn.execute(
        "SELECT pushed, staged, live FROM listings WHERE key = ?", (sku,)
    ).fetchone()
    if row is None:
        return {"pushed": 0, "staged": 0, "live": 0}
    pushed, staged, live = row
    return {"pushed": int(pushed or 0), "staged": int(staged or 0), "live": int(live or 0)}


def _catalog_row_for(home: Path, run_name: str, game: str, sku: str) -> dict:
    """The row `_catalog_answer` would read, over the run's own manifest — plain files,
    never a store connection. Mirrors `server/capture_server.py:_catalog_for_card` /
    `_catalog_answer` exactly, read-only.
    """
    manifest_path = home / "runs" / run_name / "manifest.json"
    if not manifest_path.is_file():
        return {"error": f"run_not_found: {manifest_path}"}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"error": f"manifest_unreadable: {exc}"}
    export_entry = (manifest.get("exports") or {}).get(game)
    if not export_entry or not export_entry.get("path"):
        return {"error": f"no_export_for_game: {game}"}
    export_path = Path(export_entry["path"])
    if not export_path.is_file():
        return {"error": f"export_missing: {export_path}"}
    try:
        export = tcgcsv.read_export(export_path)
        catalog = Catalog.from_export(export, game)
        row = catalog.row_for_sku(sku)
    except (tcgcsv.MalformedCsv, join.EmptyCatalog, OSError, ValueError) as exc:
        # NEVER A CRASH MID-REPORT. A malformed or mismatched export on one card must not
        # stop this script from reporting the other two — the same "never drop a card
        # silently" rule this whole repair exists to serve.
        return {"error": f"{type(exc).__name__}: {exc}"}
    if row is None:
        return {"error": f"sku_not_in_catalog: {sku} not in {export_path}"}
    rarity = str(row.get(tcgcsv.RARITY_COLUMN) or "").strip() or None
    raw_number = row[tcgcsv.NUMBER_COLUMN]
    name = row[tcgcsv.NAME_COLUMN]
    return {
        "export_path": str(export_path),
        "name": name,
        "rarity": rarity,
        "raw_number": raw_number,
    }


def preview(home: Path) -> list:
    store_path = home / "inventory" / DB_NAME
    if not store_path.is_file():
        print(f"no store at {store_path} — nothing to preview")
        return []
    conn = _ro_connect(store_path)
    reports = []
    for case in CASES:
        box, index = case["box"], case["index"]
        card = _read_card(conn, box, index)
        report = {"case": case, "card": card}
        if not card.get("found"):
            report["verdict"] = "not_found"
            reports.append(report)
            continue
        if str(card["sku"] or "") != str(case["expected_sku"]):
            report["verdict"] = "sku_mismatch"
            report["note"] = (
                f"card carries sku {card['sku']!r}, not the expected "
                f"{case['expected_sku']!r} — something else touched this card since "
                f"2026-09-23. Not proposing a write against a card this description no "
                f"longer matches."
            )
            reports.append(report)
            continue
        if not card.get("run"):
            report["verdict"] = "no_run_recorded"
            reports.append(report)
            continue
        row = _catalog_row_for(home, card["run"], str(card.get("game") or ""), card["sku"])
        if "error" in row:
            report["verdict"] = "catalog_lookup_failed"
            report["note"] = row["error"]
            reports.append(report)
            continue
        new_number, new_printed_total = join.split_catalog_number(row["raw_number"])
        new_number_key = (
            join.join_key(new_number, new_printed_total)
            if (new_number and new_printed_total)
            else ""
        )
        new_number_display = join.display_number(new_number, new_printed_total) or ""
        report["proposed"] = {
            "rarity": row["rarity"],
            "number": new_number,
            "printed_total": new_printed_total,
            "number_key": new_number_key,
            "number_display": new_number_display,
        }
        report["catalog_row_name"] = row["name"]
        report["catalog_export"] = row["export_path"]
        report["hold_on_current_sku"] = _listing_hold(conn, card["sku"])
        changed = (
            card["rarity"] != row["rarity"]
            or card["number"] != new_number
            or card["printed_total"] != new_printed_total
        )
        report["verdict"] = "would_change" if changed else "already_correct"
        reports.append(report)
    conn.close()
    return reports


def _print_report(reports: list) -> None:
    for entry in reports:
        case = entry["case"]
        print(f"--- box {case['box']}, card {case['index']} (expected {case['expected_sku']}) ---")
        print(f"  verdict: {entry['verdict']}")
        if entry["verdict"] in ("not_found", "sku_mismatch", "no_run_recorded",
                                  "catalog_lookup_failed"):
            print(f"  {entry.get('note', '')}")
            continue
        card = entry["card"]
        proposed = entry["proposed"]
        print(f"  catalog row: {entry['catalog_row_name']!r}  (from {entry['catalog_export']})")
        print(
            f"  rarity:          {card['rarity']!r:>12}  ->  {proposed['rarity']!r}"
        )
        print(
            f"  number:          {card['number']!r:>12}  ->  {proposed['number']!r}"
        )
        print(
            f"  printed_total:   {card['printed_total']!r:>12}  ->  "
            f"{proposed['printed_total']!r}"
        )
        print(
            f"  number_key:      {card['number_key']!r:>12}  ->  {proposed['number_key']!r}"
        )
        print(
            f"  number_display:  {card['number_display']!r:>12}  ->  "
            f"{proposed['number_display']!r}"
        )
        hold = entry["hold_on_current_sku"]
        blocked = hold["pushed"] or hold["staged"] or hold["live"]
        print(
            f"  undo-then-redo via the route: "
            f"{'WOULD REFUSE undo_too_late' if blocked else 'undo would be allowed'} "
            f"(pushed={hold['pushed']} staged={hold['staged']} live={hold['live']}) — "
            f"not the mechanism this script proposes either way"
        )
    print()
    print(
        "Nothing above was written. Re-run with --write --confirm to apply the "
        "'would_change' rows through Store().write() — see the module docstring."
    )


def apply(home: Path, reports: list) -> None:
    """Set `rarity`/`number`/`printed_total` from `proposed`, one transaction per card, and
    log a `rarity_number_repaired` event carrying the pair it overwrote. The ordinary
    `Store` primitive — never a raw SQL write — so this repair passes through
    `store/master.py:_card_columns` exactly like any other card write, and `number_key`/
    `number_display` are derived there rather than a second time here.
    """
    # Imported here, not at module scope, so the default (preview) run never even imports
    # `store.db` — see the module docstring's read-only argument.
    from store import Store, master  # noqa: PLC0415

    for entry in reports:
        if entry["verdict"] != "would_change":
            continue
        case = entry["case"]
        box, index = case["box"], case["index"]
        key = master.position_key(box, index)
        proposed = entry["proposed"]
        with Store(directory=home / "inventory").write() as snapshot:
            card = snapshot.inventory.cards.get(key)
            if card is None or str(card.sku or "") != str(case["expected_sku"]):
                print(f"  SKIPPED {key} — card moved on since the preview was read")
                continue
            previous = {
                "rarity": card.rarity,
                "number": card.number,
                "printed_total": card.printed_total,
            }
            card.rarity = proposed["rarity"]
            card.number = proposed["number"]
            card.printed_total = proposed["printed_total"]
            snapshot.inventory.events.append(
                {
                    "at": master.now(),
                    "event": "rarity_number_repaired",
                    "position": key,
                    "sku": card.sku,
                    "rarity": card.rarity,
                    "number": card.number,
                    "printed_total": card.printed_total,
                    "restores_to": previous,
                    "note": "D252 amendment: one-time rarity/number repair",
                }
            )
        print(f"  applied {key}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--home", required=True, type=Path,
        help="The checkout's home directory (holds inventory/ and runs/). No default.",
    )
    parser.add_argument("--write", action="store_true", help="Open Store().write() and apply.")
    parser.add_argument(
        "--confirm", action="store_true",
        help="Required alongside --write. Without it, --write alone still only previews.",
    )
    args = parser.parse_args()

    reports = preview(args.home)
    _print_report(reports)

    if args.write and args.confirm:
        print()
        print("--write --confirm given: applying now.")
        apply(args.home, reports)
    elif args.write:
        print()
        print("--write given without --confirm: nothing applied. Add --confirm to write.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
