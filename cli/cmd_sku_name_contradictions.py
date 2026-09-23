"""`pkmnscan cards sku-names` — one SKU, two stored names. The sibling `D242` cannot see:
its own class needs the stored NUMBERS to disagree, and this class needs them to AGREE while
the NAME does not.

READ-ONLY, ALWAYS, AND OPENS NO SOCKET, EVER. Reads the store through the same door
`cli/cmd_sku_contradictions.py:_read_only` already opens (`mode=ro&immutable=1`, never
`db.connect` — see that module's own docstring for why a preview routed through `db.connect`
would perform the migration it claims to be previewing) and reads whatever the store already
has cached under `inventory/.exports/<game>/` — the NEWEST file per game, never fetched here.
There is no `--resolve` flag and no live catalogue call anywhere in this module; unlike
`cards contradictions`, this check's whole subject is data already on disk.

Kept in its own file rather than folded into `cli/cmd_cards.py` directly, on `D242`'s own
precedent — a fifth, sibling stored-data check kept apart from the four `D239` approved, and
this is a sixth kept apart from both: the SKU is fixed and the disagreement is the NAME, the
mirror image of D242's fixed-number / disagreeing-SKU shape.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from cli.cmd_sku_contradictions import _read_only
from pipeline import games as games_module
from pipeline import tcgcsv
from pipeline.sku_name_contradictions import (
    CardRecord,
    Catalog,
    Dispute,
    find_contradictions,
)
from store import db, files, photos


def _claim_tuple(value) -> Tuple[str, ...]:
    """`metadata_finish`/`rarity_claim` off the stored payload — a bare string, a list, or
    `None` — folded to a tuple the same way `pipeline.variant._check_claim` reads the field,
    without importing that function (it also validates against a game's vocabulary, which is
    a write-path concern this read-only report has no business enforcing)."""
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    return tuple(str(v) for v in value if str(v).strip())


def _cards_with_sku(conn: sqlite3.Connection) -> List[Tuple[CardRecord, Optional[str], Optional[int], Optional[int]]]:
    """Every card, its `(cid, box, idx)` for the photograph lookup kept beside it rather than
    in `pipeline/sku_name_contradictions.py` — that module never imports `store`."""
    out = []
    for key, state, sku, name, game, set_hint, cid, box, idx, text in conn.execute(
        "SELECT key, state, sku, name, game, set_hint, cid, box, idx, payload FROM cards"
    ):
        try:
            record = json.loads(text) if text else {}
        except (TypeError, ValueError):
            record = {}
        card = CardRecord(
            key=str(key),
            state=str(state or ""),
            sku=sku,
            name=name,
            game=game,
            set_hint=set_hint,
            metadata_finish=_claim_tuple(record.get("metadata_finish")),
            rarity_claim=_claim_tuple(record.get("rarity_claim")),
        )
        out.append((card, cid, box, idx))
    return out


def _relocated(conn: sqlite3.Connection) -> bool:
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key = ?", (db.PHOTOS_RELOCATED,)
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    return bool(row and row[0])


def _newest_export(game: str) -> Optional[Path]:
    """The newest cached export for `game`, by the timestamp already in its own filename
    (`export-tcgplayer-<stamp>-<hash>.csv`) — the same "sort the filenames, take the last"
    idiom `pipeline/readings.py:_newest_live_reading` uses for `inventory/.live/`, on the
    same reasoning: never parse every file in the directory just to have the newest
    overwrite the rest.
    """
    directory = files.inventory_dir() / files.EXPORTS_DIRNAME / game
    if not directory.is_dir():
        return None
    found = sorted(directory.glob("*.csv"))
    return found[-1] if found else None


def _load_catalogs(games: List[str]) -> Tuple[Dict[str, Catalog], Dict[str, str]]:
    """One `Catalog` per game that has a cached export, and the load failures named per
    game rather than swallowed — a malformed or unreadable file is `not_known`, never a
    silent skip.
    """
    catalogs: Dict[str, Catalog] = {}
    failures: Dict[str, str] = {}
    for game in games:
        path = _newest_export(game)
        if path is None:
            continue
        try:
            export = tcgcsv.read_export(path)
        except (OSError, tcgcsv.MalformedCsv) as exc:
            failures[game] = f"{path} could not be read: {exc}"
            continue
        catalogs[game] = Catalog.from_export(export)
    return catalogs, failures


def _print_row(say, row, indent="      ") -> None:
    say(
        f"{indent}SKU {row.get(tcgcsv.SKU_COLUMN)}  {row.get(tcgcsv.NAME_COLUMN)!r}  "
        f"{row.get(tcgcsv.NUMBER_COLUMN)}  {row.get(tcgcsv.CONDITION_COLUMN)}"
    )


def _print_dispute(say, dispute: Dispute, photo, verbose: bool) -> None:
    card = dispute.card
    say(f"    {card.key}  ({card.state})  stored name {card.name!r}")
    say(f"      under SKU {card.sku}:")
    _print_row(say, dispute.sku_row)
    if photo is not None:
        say(f"      photo: {photo}")
    else:
        say("      photo: none found")
    if dispute.alternatives:
        say(f"      {len(dispute.alternatives)} export row(s) named {card.name!r}, ranked:")
        limit = len(dispute.alternatives) if verbose else min(3, len(dispute.alternatives))
        for row in dispute.alternatives[:limit]:
            _print_row(say, row, indent="        ")
        if not verbose and len(dispute.alternatives) > limit:
            say(f"        … and {len(dispute.alternatives) - limit} more (--verbose)")
    else:
        say("      no export row anywhere carries this exact name — no likely SKU to propose")


def run(args, say) -> int:
    directory = files.inventory_dir()
    conn = _read_only(directory)
    rows = _cards_with_sku(conn)
    relocated = _relocated(conn)
    conn.close()
    home = directory.parent

    games_seen = sorted({card.game or games_module.DEFAULT_GAME for card, _c, _b, _i in rows})
    catalogs, load_failures = _load_catalogs(games_seen)

    cards = [card for card, _cid, _box, _idx in rows]
    by_key = {card.key: (cid, box, idx) for card, cid, box, idx in rows}
    report = find_contradictions(cards, catalogs)

    say(f"SKU NAME CONTRADICTIONS  {db.path(directory)}")
    say(f"  games with a cached export: {', '.join(sorted(catalogs)) or 'none'}")
    if load_failures:
        say("  export load failures (counted as `not known` for that game's cards):")
        for game, why in load_failures.items():
            say(f"    {game}: {why}")
    say(
        f"  {report.checked} card(s) checked   {report.skipped_no_sku} skipped (no SKU yet, "
        f"not a subject of this check)   {len(report.not_known)} not known"
    )
    say(f"  {len(report.identified)} identified, {len(report.sold)} sold disagree")

    verbose = bool(getattr(args, "verbose", False))

    if report.identified:
        say("")
        say(f"  IDENTIFIED ({len(report.identified)}):")
        for dispute in report.identified:
            cid, box, idx = by_key.get(dispute.card.key, (None, None, None))
            photo = photos.find(cid, box, idx, relocated=relocated, home=home)
            _print_dispute(say, dispute, photo, verbose)

    if report.sold:
        say("")
        say(f"  SOLD ({len(report.sold)}):")
        for dispute in report.sold:
            cid, box, idx = by_key.get(dispute.card.key, (None, None, None))
            photo = photos.find(cid, box, idx, relocated=relocated, home=home)
            _print_dispute(say, dispute, photo, verbose)

    if report.not_known and verbose:
        say("")
        say(f"  NOT KNOWN ({len(report.not_known)}):")
        for unknown in report.not_known:
            say(f"    {unknown.card.key}  ({unknown.card.state})  {unknown.reason}")
    elif report.not_known:
        say(f"  {len(report.not_known)} card(s) not known — pass --verbose to list them")

    say("")
    verdict = report.verdict
    if verdict == "not_known":
        say("VERDICT: not known — nothing could be checked. No card in this store carries a "
            "SKU, name and a matching cached export, or every such card fell into one of "
            "the reasons above.")
        return 2
    if verdict == "fail":
        say(f"VERDICT: fail — {len(report.disputes)} card(s) disagree with their own SKU's "
            "stored product name. Never a repair — each is a review signal. Look at the "
            "photo before touching the card.")
        return 1
    say("VERDICT: pass — every checked card's stored name agrees with its SKU's product "
        "name.")
    return 0
