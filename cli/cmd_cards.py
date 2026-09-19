"""`pkmnscan cards` — the card's stable name: preview it, audit it, move the photographs.

FOUR SUBCOMMANDS AND TWO OF THEM WRITE NOTHING EVER.

  cards name      what the naming would do, or has done — the source census, every card that
                  would land `nophoto:`, every duplicate photograph, and the receipt
  cards audit     does every card's name still resolve to its photograph? THREE verdicts,
                  never two, and the third is `not known`
  cards photos    move the corpus off the legacy `(box, index)` address onto the card's own
                  name. Previews by default; `--write` performs it
  cards variants  backfill `set` and `rarity` from whatever export a card's game already
                  has on disk (D213).
                  Previews by default; `--write` performs it. Never guesses: a SKU that
                  resolves to nothing keeps a null set.

`name` AND `audit` OPEN THE STORE READ-ONLY AND MUST NEVER CALL `db.connect`. That function
is the single entry to the store and it always calls `_ensure_schema`, so a preview routed
through it would PERFORM the migration it claims to be previewing. It is a hard property
with a harness arm behind it, and it is why this module talks to `sqlite3` directly instead
of going through `store.session`.

`cards photos` IS THE ONE THING HERE THAT TOUCHES 4.45 GB THAT CANNOT BE RE-TAKEN, which is
why it previews first and why every file it moves is verified against a digest that was
already proved. `store/photos.py:adopt` is the per-card step and its docstring carries the
argument for the link-verify-unlink order; this module is the driver, the census and the
report.

`cards variants` GOES THROUGH `store.Store`, NOT RAW `sqlite3`, unlike `name`/`audit` above —
it writes ordinary card fields through the ordinary lock, the same door `set_state` already
uses, and the `db.connect`-must-not-migrate rule above is `photos`'/`name`'s/`audit`'s own
because a stray call there would perform a multi-gigabyte photograph move nobody asked for;
resolving a SKU against a CSV already on disk carries no such risk, and this store's own
schema migration (`store/db.py:_add_set_columns`) is what adds the two columns this
subcommand fills in the first place.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from store import Store, db, files, master, photos

# The ladder's own names, in the order `_name_one_card` tries them, so a report can rank a
# source by how much it is worth rather than printing a dict in hash order.
SOURCE_ORDER = ("kept", "disk", "record", "identification", "nophoto")


def _read_only(directory: Path) -> sqlite3.Connection:
    """The store, read-only and immutable, WITHOUT `db.connect`.

    `immutable=1` is deliberate on top of `mode=ro`: it tells SQLite the file will not change
    under it, so no WAL recovery is attempted and no `-shm` is created — which means this
    cannot write a byte even as a side effect of opening, including beside a store a capture
    server is live on.
    """
    target = db.path(directory)
    if not target.is_file():
        raise FileNotFoundError(f"no store at {target}")
    return sqlite3.connect(f"file:{target}?mode=ro&immutable=1", uri=True)


def _meta(conn: sqlite3.Connection) -> Dict[str, str]:
    try:
        return {str(k): str(v) for k, v in conn.execute("SELECT key, value FROM meta")}
    except sqlite3.OperationalError:
        return {}


def _has_cid(conn: sqlite3.Connection) -> bool:
    return "cid" in {row[1] for row in conn.execute("PRAGMA table_info(cards)")}


def _cards(conn: sqlite3.Connection) -> List[Tuple[str, Optional[str], Optional[int], Optional[int], dict]]:
    """`(key, cid, box, idx, record)` for every card, in ascending position."""
    select = "SELECT key, cid, box, idx, payload FROM cards" if _has_cid(conn) else (
        "SELECT key, NULL AS cid, box, idx, payload FROM cards"
    )
    out = []
    for key, cid, box, idx, text in conn.execute(select):
        try:
            record = json.loads(text)
        except (TypeError, ValueError):
            record = {}
        out.append((str(key), cid, box, idx, record))
    out.sort(key=lambda row: (row[2] is None, row[2] or 0, row[3] is None, row[3] or 0, row[0]))
    return out


def _relocated(conn: sqlite3.Connection) -> bool:
    return bool(_meta(conn).get(db.PHOTOS_RELOCATED))


# ------------------------------------------------------------------------- cards name


def _name(args, say) -> int:
    directory = files.inventory_dir()
    conn = _read_only(directory)
    meta = _meta(conn)
    rows = _cards(conn)
    home = directory.parent

    say(f"STORE  {db.path(directory)}")
    say(f"  schema {meta.get('schema', '?')}   cards {len(rows)}")
    if not _has_cid(conn):
        say("  NO `cid` COLUMN. This store has not been named yet; the next read names it.")
    seeded = meta.get(db.CARD_IDS_SEEDED)
    say(f"  card_ids_seeded {seeded if seeded is not None else '(never)'}")
    sources = meta.get(db.CARD_ID_SOURCES)
    if sources:
        try:
            census = json.loads(sources)
        except (TypeError, ValueError):
            census = {}
        say("  sources: " + "  ".join(
            f"{name}={census.get(name, 0)}" for name in SOURCE_ORDER
        ))
        # `disk: 0` MUST NEVER READ AS "NO PHOTOGRAPH NEEDED HASHING", so it is said out loud.
        if not census.get("disk") and not census.get("record"):
            say("  NOT ONE CARD WAS NAMED FROM ITS OWN BYTES. Every name here came from a "
                "weaker source; `cards audit` is the thing that can say whether they are right.")
        weak = census.get("identification", 0)
        if weak:
            say(f"  {weak} card(s) named from an identification row rather than from a "
                "photograph — a digest that `do_reshoot` can leave stale. Named below.")
    say("")

    # What the naming WOULD do, computed here rather than read back, so a store that has not
    # been named yet produces the same report shape as one that has.
    counters = {name: 0 for name in SOURCE_ORDER}
    counters["suffixed"] = 0
    unnamed: List[str] = []
    weak_keys: List[str] = []
    seen: Dict[str, str] = {}
    duplicates: List[Tuple[str, str, str]] = []
    identifications = {
        str(k): v for k, v in conn.execute(
            "SELECT key, photo_sha256 FROM identifications"
        ) if v
    }
    relocated = _relocated(conn)
    first = last = None
    for key, cid, box, idx, record in rows:
        if isinstance(cid, str) and cid:
            counters["kept"] += 1
            digest = photos.digest_of(cid)
            if digest and digest in seen and seen[digest] != key:
                duplicates.append((key, seen[digest], cid))
            if digest:
                seen.setdefault(digest, key)
            if not photos.is_photo_cid(cid):
                unnamed.append(key)
            if first is None:
                first = (key, cid)
            last = (key, cid)
            continue
        found = photos.find(cid, box, idx, relocated=relocated, home=home)
        if found is not None:
            counters["disk"] += 1
            continue
        if record.get("photo_sha256"):
            counters["record"] += 1
        elif identifications.get(key):
            counters["identification"] += 1
            weak_keys.append(key)
        else:
            counters["nophoto"] += 1
            unnamed.append(key)

    say("WHAT THE NAMING SEES NOW")
    say("  " + "  ".join(f"{name}={counters[name]}" for name in SOURCE_ORDER))
    if weak_keys:
        say(f"  named by an identification row ({len(weak_keys)}): " + ", ".join(weak_keys[:40]))
    if unnamed:
        say(f"  NO PHOTOGRAPH AND NO DIGEST ({len(unnamed)}) — these get `nophoto:` names, "
            "which is a shape and never a NULL:")
        for key in unnamed[:40]:
            say(f"    {key}")
        if len(unnamed) > 40:
            say(f"    … and {len(unnamed) - 40} more")
    if duplicates:
        say(f"  DUPLICATE PHOTOGRAPHS ({len(duplicates)}) — the second and later of each get "
            "a `-<n>` suffix:")
        for key, other, cid in duplicates[:20]:
            say(f"    {key} shares bytes with {other}  ({cid})")
    if first is not None:
        # TWO CARDS A HUMAN CAN CHECK BY HAND with `sha256sum`, which is the only part of this
        # report that does not depend on trusting the program that printed it.
        say("")
        say("  CHECK EITHER OF THESE BY HAND:")
        by_key = {key: (cid, box, idx) for key, cid, box, idx, _r in rows}
        for label, pair in (("first", first), ("last", last)):
            if pair is None:
                continue
            key, cid = pair
            say(f"    {label} {key}  cid {cid}")
            stored_cid, box, idx = by_key.get(key, (cid, None, None))
            found = photos.find(stored_cid, box, idx, relocated=relocated, home=home)
            if found is not None:
                say(f"      sha256sum {found}")

    receipt = directory / db.MIGRATIONS_DIRNAME / db.CARD_ID_RECEIPT
    say("")
    if receipt.is_file():
        say(f"RECEIPT {receipt}")
        try:
            payload = json.loads(receipt.read_text("utf-8"))
        except (OSError, ValueError) as exc:
            say(f"  unreadable: {exc}")
        else:
            for field in ("migrated_at", "card_ids_seeded", "verified_against_disk",
                          "rehashed", "cards_reissued"):
                if field in payload:
                    say(f"  {field}: {payload[field]}")
            if payload.get("reverse"):
                say("  reverse: " + payload["reverse"])
    else:
        say(f"RECEIPT none at {receipt} — this store has not been named by this build.")

    count, total = photos.survey(home)
    say("")
    say(f"PHOTOGRAPH STORE  {photos.root(home)}")
    say(f"  {count} photograph(s), {total:,} bytes")
    say(f"  photos_relocated: {'yes' if relocated else 'NO — the legacy address is still read'}")
    conn.close()
    say("")
    say("NOTHING WAS WRITTEN. This command opens the store read-only and never calls "
        "`db.connect`, because that function performs the migration it would be previewing.")
    return 0


# ------------------------------------------------------------------------ cards audit


def _audit(args, say) -> int:
    """Does every card's name still resolve to its photograph?

    THREE VERDICTS, NEVER TWO, AND THE THIRD IS WHY THIS IS WORTH RUNNING. A check shaped
    "for every card, sha256(file) == cid" over zero rows prints `checked 0, mismatch 0` and
    reads as a pass; this repo has hit that shape enough times to have a rule about it. So an
    absent column, a NULL name, or no photographs at all is `not known` and exits non-zero.

    WHAT IT PROVES IS TEMPORAL. Run immediately after the naming it is close to tautological
    — the naming read those bytes and this reads them again. Its value is that it proves the
    link STILL holds later, after renumbers, moves, deletions and reclaims.
    """
    directory = files.inventory_dir()
    conn = _read_only(directory)
    meta = _meta(conn)
    home = directory.parent
    rows = _cards(conn)
    relocated = _relocated(conn)

    unknown: List[str] = []
    if not _has_cid(conn):
        unknown.append("the `cid` column is absent — this store has never been named")
    nulls = [key for key, cid, *_rest in rows if not cid]
    if nulls:
        unknown.append(
            f"{len(nulls)} card(s) carry no name: {', '.join(nulls[:12])}"
            f"{' …' if len(nulls) > 12 else ''}. An older build strips the column on any "
            "ordinary write; the next read re-issues them."
        )
    if not rows:
        unknown.append("there are no cards in this store")

    checked = match = mismatch = 0
    excused: List[Tuple[str, str]] = []
    missing: List[str] = []
    unprovable: List[Tuple[str, str]] = []
    failures: List[Tuple[str, str, str]] = []
    nbytes = 0

    # THE EXCUSED SET COMES FROM A RECORDED DIGEST AND NEVER FROM THE BARE FACT OF A
    # RE-SHOOT. D172 §7 item 1 is the doubt this answers: the one `reshot` event on the
    # owner's store carries two capture ids and NO digest at all, so before this there was
    # nothing to excuse a re-shot card WITH. `do_reshoot` records `photo_sha256` now, and a
    # `reshot` line without one is a NAMED UNPROVABLE rather than an excuse.
    reshot: Dict[str, List[str]] = {}
    try:
        for position, text in conn.execute(
            "SELECT position, payload FROM events WHERE event = 'reshot'"
        ):
            try:
                payload = json.loads(text)
            except (TypeError, ValueError):
                payload = {}
            reshot.setdefault(str(position), []).append(payload.get("photo_sha256") or "")
    except sqlite3.OperationalError:
        pass

    for key, cid, box, idx, record in rows:
        if not cid:
            continue
        checked += 1
        want = photos.digest_of(cid)
        found = photos.find(cid, box, idx, relocated=relocated, home=home)
        if found is None:
            if record.get("photo_reclaimed_at"):
                excused.append((key, "photograph reclaimed on purpose (D89)"))
            elif not photos.is_photo_cid(cid):
                excused.append((key, f"name is a {cid.split(':', 1)[0]}: shape, which names "
                                     "no photograph"))
            else:
                missing.append(key)
            continue
        nbytes += found.stat().st_size
        actual = photos.sha256_of(found)
        if actual == want:
            match += 1
            continue
        digests = [d for d in reshot.get(key, []) if d]
        if digests and actual in digests:
            excused.append((key, f"re-shot, and the `reshot` line records {actual[:12]}…"))
            continue
        if key in reshot and not digests:
            unprovable.append((key, "a `reshot` line with no recorded digest — the bare fact "
                                    "of a re-shoot is never an excuse"))
            continue
        mismatch += 1
        failures.append((key, want or "?", actual))

    count, total = photos.survey(home)
    say(f"CID AUDIT  {db.path(directory)}")
    say(f"  schema {meta.get('schema', '?')}   cards {len(rows)}   photographs {count}")
    say(f"  checked {checked}   match {match}   mismatch {mismatch}   excused {len(excused)}")
    say(f"  read {nbytes:,} bytes")
    if missing:
        say(f"  NO FILE AT EITHER NAME ({len(missing)}): " + ", ".join(missing[:20]))
    if unprovable:
        say(f"  UNPROVABLE ({len(unprovable)}):")
        for key, why in unprovable[:20]:
            say(f"    {key}  {why}")
    if failures:
        say(f"  MISMATCH ({len(failures)}):")
        for key, want, actual in failures[:40]:
            say(f"    {key}  named {want[:16]}…  file hashes {actual[:16]}…")
    if excused and getattr(args, "verbose", False):
        say(f"  excused ({len(excused)}):")
        for key, why in excused[:40]:
            say(f"    {key}  {why}")
    conn.close()

    if not checked and not unknown:
        unknown.append("no card carried a name to check")
    if unknown:
        say("")
        say("VERDICT: not known")
        for line in unknown:
            say(f"  {line}")
        say("  `not known` is a third verdict on purpose. A check over zero rows prints "
            "`checked 0, mismatch 0` and reads as a pass, and that is the shape this repo "
            "keeps paying for.")
        return 2
    if failures or missing or unprovable:
        say("")
        say("VERDICT: fail")
        return 1
    say("")
    say("VERDICT: pass — every named card's photograph hashes to its name, or is excused by "
        "a recorded digest.")
    return 0


# ----------------------------------------------------------------------- cards photos


def _photos(args, say) -> int:
    """Move the corpus onto the card's own name. Previews unless `--write`.

    RESUMABLE AND VERIFIED PER CARD, which is `store/photos.py:adopt`'s whole design: hard
    link, re-hash the destination, THEN unlink the source, so the bytes exist under at least
    one name at every instant and a re-run finishes whatever a kill interrupted.

    IT TAKES NO STORE WRITE LOCK AND OPENS THE DATABASE READ-ONLY — except for the one
    statement that stamps `photos_relocated` when a pass finds every card at its name. So it
    can be interrupted freely, it cannot corrupt a transaction, and it does not contend with
    a live capture server for the flock.
    """
    write = bool(getattr(args, "write", False))
    limit = getattr(args, "limit", None)
    directory = files.inventory_dir()
    conn = _read_only(directory)
    home = directory.parent
    if not _has_cid(conn):
        say("This store has no `cid` column, so no photograph has a name to move to. Open "
            "the store once with this build — the next read names every card — then run "
            "this again.")
        conn.close()
        return 2
    rows = _cards(conn)
    already_relocated = _relocated(conn)
    conn.close()

    say(f"PHOTOGRAPHS -> {photos.root(home)}")
    say(f"  {len(rows)} card(s); {'WRITING' if write else 'PREVIEW, nothing will be moved'}")
    if already_relocated:
        say("  this store is already stamped `photos_relocated`; a re-run verifies and moves "
            "anything that arrived since.")
    say("")

    census = {
        "already": 0, "moved": 0, "refused": 0, "unnamed": 0, "no_file": 0,
        "sidecars": 0, "reclaimed": 0,
    }
    refusals: List[Tuple[str, str]] = []
    bytes_moved = 0
    would: List[Tuple[str, Path, Path]] = []

    for key, cid, box, idx, record in rows:
        if not photos.is_photo_cid(cid):
            # A `moved:` tombstone or a `nophoto:` card names no file. Neither is a problem
            # and both are counted rather than skipped silently.
            census["unnamed"] += 1
            continue
        source = photos.legacy_path(box, idx, home) if box is not None and idx is not None \
            else None
        target = photos.path(cid, home)
        if target.is_file():
            census["already"] += 1
            # A SOURCE STILL SITTING AT THE OLD ADDRESS IS THE FOOTPRINT OF AN INTERRUPTED
            # RUN, and clearing it is step 5 of that run finishing rather than a tidy-up:
            # `adopt` links, re-hashes the destination, and only then unlinks — so a kill in
            # that window leaves both names, and skipping this branch would leave the legacy
            # copy there forever while the census reported a clean pass.
            if write and source is not None and source.is_file():
                try:
                    photos.adopt(source, cid, home)
                except files.StoreError as exc:
                    census["refused"] += 1
                    refusals.append((key, str(exc)))
            continue
        if record.get("photo_reclaimed_at"):
            census["reclaimed"] += 1
            continue
        if source is None or not source.is_file():
            census["no_file"] += 1
            continue
        if not write:
            would.append((key, source, target))
            bytes_moved += source.stat().st_size
            census["moved"] += 1
            if limit and census["moved"] >= int(limit):
                break
            continue
        size = source.stat().st_size
        try:
            verdict = photos.adopt(source, cid, home)
        except files.StoreError as exc:
            census["refused"] += 1
            refusals.append((key, str(exc)))
            continue
        census[verdict] += 1
        if verdict == "moved":
            bytes_moved += size
        sidecar = photos.legacy_path(box, idx, home).with_suffix(photos.SIDECAR_SUFFIX)
        if sidecar.is_file():
            try:
                photos.adopt_sidecar(sidecar, cid, home)
                census["sidecars"] += 1
            except OSError as exc:
                # NEVER FATAL. `identify.sidecar.scan` keys on the PHOTOGRAPH, so a sidecar
                # that did not travel costs the recovery path in that module's docstring and
                # never a card.
                refusals.append((key, f"sidecar: {exc}"))
        if limit and census["moved"] >= int(limit):
            break

    say("  " + "  ".join(f"{name}={value}" for name, value in census.items()))
    say(f"  {bytes_moved:,} bytes {'moved' if write else 'would move'}")
    if would:
        say("")
        say("  FIRST FEW:")
        for key, source, target in would[:10]:
            say(f"    {key}  {source.name} -> {target.relative_to(home)}")
        if len(would) > 10:
            say(f"    … and {len(would) - 10} more")
    if refusals:
        say("")
        say(f"  REFUSED ({len(refusals)}) — each left exactly where it was:")
        for key, why in refusals[:20]:
            say(f"    {key}  {why}")

    if not write:
        say("")
        say("Nothing was moved. Re-run with `--write` to perform it; it is resumable, so a "
            "kill costs nothing and a second run finishes it.")
        return 0

    # THE STAMP IS THE LAST THING AND ONLY ON A CLEAN PASS. Until it is set, `photos.find`
    # still reads the legacy address, which is what keeps every screen drawing during a
    # partial move; once set, the legacy address is never consulted again.
    outstanding = census["refused"] + census["no_file"]
    if outstanding:
        say("")
        say(f"  {outstanding} card(s) are not at their name, so `photos_relocated` is NOT "
            "stamped and the legacy address is still read. Fix or accept those and run "
            "again.")
        return 1
    with files.exclusive(directory):
        conn = db.connect(directory, locked=True)
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                (db.PHOTOS_RELOCATED, master.now()),
            )
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        conn.close()
    say("")
    say("  STAMPED `photos_relocated`. The legacy `(box, index)` address is never read "
        "again — a renumber moves no file, a move moves no file, and two cards cannot "
        "compose one photograph's name.")
    return 0


def _variants(args, say) -> int:
    """Backfill `set` and `rarity` from whatever export a card's own game already has on
    disk (D213). Previews unless `--write`.

    NEVER REFUSES A CARD AND NEVER GATES. A SKU that resolves to nothing keeps a null set,
    counted and reported, never guessed. RE-RUNNABLE: a card that already carries a set is
    left exactly as it is, so a second pass over a store an export arrived into since the
    first only fills what the first pass could not — the same idiom `photos`/`prices adopt`
    already use for a fact this store can only partially answer the day it is asked.

    EVERY EXPORT UNDER `inventory/.exports/<game>/`, MERGED, first-file-wins on a SKU seen
    twice — `pipeline/setnames.py:known_sets` makes the identical choice for the same reason:
    a set released since an older file was fetched must still be visible, and a Set Name or
    Rarity for one SKU does not change file to file.
    """
    write = bool(getattr(args, "write", False))
    from pipeline import games, tcgcsv

    exports: Dict[str, Dict[str, dict]] = {}

    def export_for(game: str) -> Dict[str, dict]:
        if game not in exports:
            directory = files.inventory_dir() / files.EXPORTS_DIRNAME / game
            merged: Dict[str, dict] = {}
            if directory.is_dir():
                for path in sorted(directory.glob("*.csv")):
                    try:
                        export = tcgcsv.read_export(path)
                    except (OSError, tcgcsv.MalformedCsv):
                        continue
                    for row in export.rows:
                        sku = str(row.get(tcgcsv.SKU_COLUMN) or "").strip()
                        if sku and sku not in merged:
                            merged[sku] = row
            exports[game] = merged
        return exports[game]

    inventory = Store().read().inventory
    census = {"already_set": 0, "no_sku": 0, "resolved": 0, "unresolved": 0}
    by_game: Dict[str, Dict[str, int]] = {}
    changes: List[Tuple[str, str, str, Optional[str]]] = []

    for key, card in inventory.cards.items():
        if card.set_name is not None:
            census["already_set"] += 1
            continue
        if not card.sku:
            census["no_sku"] += 1
            continue
        game = card.game or games.DEFAULT_GAME
        stats = by_game.setdefault(game, {"resolved": 0, "unresolved": 0})
        row = export_for(game).get(card.sku)
        set_name = str((row or {}).get(tcgcsv.SET_COLUMN) or "").strip() or None
        rarity = str((row or {}).get(tcgcsv.RARITY_COLUMN) or "").strip() or None
        if set_name is None:
            census["unresolved"] += 1
            stats["unresolved"] += 1
            continue
        census["resolved"] += 1
        stats["resolved"] += 1
        changes.append((key, card.sku, set_name, rarity))

    say("CARD VARIANTS -> set + rarity, from the export each game already has on disk")
    say(f"  {len(inventory.cards)} card(s); {'WRITING' if write else 'PREVIEW, nothing will be written'}")
    say("  " + "  ".join(f"{name}={value}" for name, value in census.items()))
    for game, stats in sorted(by_game.items()):
        say(f"    {game}: {stats['resolved']} resolve, {stats['unresolved']} do not")
    if changes:
        say("")
        say("  FIRST FEW:")
        for key, sku, set_name, rarity in changes[:10]:
            say(f"    {key}  {sku} -> {set_name}" + (f" · {rarity}" if rarity else ""))
        if len(changes) > 10:
            say(f"    … and {len(changes) - 10} more")

    if not write:
        say("")
        say(f"  {len(changes)} card(s) would gain a set. Re-run with --write to apply.")
        return 0

    written = 0
    if changes:
        with Store().write() as snapshot:
            for key, sku, set_name, rarity in changes:
                card = snapshot.inventory.cards.get(key)
                # RE-CHECKED INSIDE THE LOCK, AGAINST THE SKU THIS PASS READ — a card sold,
                # re-answered or re-emitted between the preview above and this write is a
                # card this pass no longer has authority to describe, and skipping it here
                # is the same caution `photos`'s per-card digest re-check applies.
                if card is None or card.sku != sku or card.set_name is not None:
                    continue
                card.set_name = set_name
                card.rarity = rarity
                written += 1
    say("")
    say(f"  WROTE {written} card(s).")
    return 0


# --------------------------------------------------------------------------- dispatch


_SUBCOMMANDS = {"name": _name, "audit": _audit, "photos": _photos, "variants": _variants}


def run(args, say) -> int:
    action = getattr(args, "cards_action", None)
    handler = _SUBCOMMANDS.get(action)
    if handler is None:
        say("pkmnscan cards <name|audit|photos|variants>")
        return 2
    return handler(args, say)
