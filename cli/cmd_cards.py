"""`pkmnscan cards` — the card's stable name and, since lane 2 of `docs/specs/
identity-follows-sku.md`, its identity: preview it, audit it, move the photographs.

SEVEN SUBCOMMANDS AND FIVE OF THEM WRITE NOTHING EVER.

  cards name            what the naming would do, or has done — the source census, every
                        card that would land `nophoto:`, every duplicate photograph, and
                        the receipt
  cards audit           does every card's name still resolve to its photograph? THREE
                        verdicts, never two, and the third is `not known`
  cards checks          the four stored-data identification checks (D239):
                        a name too long, a denominator or digit count that disagrees with
                        its set, a name one edit from a sibling in the same set. Review
                        signals, never repairs, never a catalogue call.
  cards identity         `docs/specs/identity-follows-sku.md` §5.5, §7 (lane 2): the
                        migration's own classifier AND the merged D242/D255 report — every
                        card's class (T1-T6, `sku_unknown`), the §4.3 audit, and the name/
                        number contradiction halves. Previews by default; `--write`
                        performs the one-time migration. `cards contradictions` and `cards
                        sku-names` retire into this — see their own subcommands below.
  cards contradictions  RETIRED into `cards identity` (§5.5). Prints one line and exits.
  cards sku-names       RETIRED into `cards identity` (§5.5's sibling). Prints one line
                        and exits.
  cards photos          move the corpus off the legacy `(box, index)` address onto the
                        card's own name. Previews by default; `--write` performs it
  cards variants        backfill `set` and `rarity` from whatever export a card's game
                        already has on disk (D213).
                        Previews by default; `--write` performs it. Never guesses: a SKU
                        that resolves to nothing keeps a null set.

`name`, `audit`, `checks`, `identity`, `contradictions` AND `sku-names` OPEN THE STORE
READ-ONLY AND MUST NEVER CALL `db.connect`. That function is the single entry to the store
and it always calls `_ensure_schema`, so a preview routed through it would PERFORM the
migration it claims to be previewing. It is a hard property with a harness arm behind it,
and it is why `name`, `audit`, `checks` and `identity` all talk to `sqlite3` directly
through this module's own `_read_only`, instead of going through `store.session` — `cards
identity`'s own reader functions (`pipeline/identity_binding.py:read_cards`/`read_skus`/
`read_human_events`/`read_identifications_by_digest`/`listing_skus`) take the connection
this door opens and never call `db.connect` themselves. `cards identity --write` is the one
exception among the three identity-aware subcommands: it previews with the read-only door
and then, only once it has decided what to write, opens `store.Store().write()` for the
press itself — `cards photos`'/`cards variants`'s own preview-then-write shape, not a new
one.

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

import time

from cli import cmd_sku_contradictions, cmd_sku_name_contradictions
from pipeline import games as games_module
from pipeline import identity_binding as ib
from pipeline import identity_checks
from store import Store, db, files, master, photos
from store.master import IDENTITY_READ, IDENTITY_SKU

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


# ------------------------------------------------------------------------ cards checks


def _checks(args, say) -> int:
    """The four stored-data checks `D239` builds: read-only, no catalogue,
    no network, never a repair. Opens the store the same way `audit` does, straight
    `sqlite3`, never `db.connect` — this reads `name`, `number` and `set_name` only, and a
    migration is not a preview's business.
    """
    directory = files.inventory_dir()
    conn = _read_only(directory)
    rows = []
    columns = {row[1] for row in conn.execute("PRAGMA table_info(cards)")}
    select_set_name = "set_name" in columns
    query = "SELECT key, name, number, {} FROM cards".format(
        "set_name" if select_set_name else "NULL"
    )
    for key, name, number, set_name in conn.execute(query):
        rows.append(identity_checks.CardRecord(key=str(key), name=name, number=number, set_name=set_name))
    conn.close()

    if not select_set_name:
        say("VERDICT: not known — this store has no `set_name` column, so class 2, 3 and 4 "
            "cannot be checked. Run `pkmnscan cards variants --write` first.")
        return 2
    if not rows:
        say("VERDICT: not known — there are no cards in this store")
        return 2

    results = identity_checks.run_all(rows)
    total = sum(len(flags) for flags in results.values())
    say(f"IDENTITY CHECKS  {db.path(directory)}")
    say(f"  cards {len(rows)}")
    for name, flags in results.items():
        say(f"  {name}: {len(flags)}")
        if flags and getattr(args, "verbose", False):
            for flag in flags:
                say(f"    {flag.key}  {flag.detail}")
    say("")
    say(f"VERDICT: {total} flag(s). Each is a review signal, never a repair — look at the "
        "photo before touching the card.")
    return 0


# ---------------------------------------------------------------------- cards identity


def _read_plan(directory: Path) -> Tuple["ib.MigrationPlan", "ib.AuditFindings", Dict[str, "ib.SkuRow"]]:
    """The whole read-only pass §7 and §4.3 need — one `_read_only` connection, closed
    before this returns. Shared by the preview and by `--write`'s own preview-then-write
    shape (`cards photos`/`cards variants`'s own idiom, not a new one)."""
    conn = _read_only(directory)
    try:
        cards = ib.read_cards(conn)
        skus = ib.read_skus(conn)
        events = ib.read_human_events(conn)
        identifications = ib.read_identifications_by_digest(conn)
        listings = ib.listing_skus(conn)
    finally:
        conn.close()
    plan = ib.plan_migration(cards, skus, events, identifications)
    findings = ib.audit(cards, skus, listings)
    return plan, findings, skus


def _print_plan(plan: "ib.MigrationPlan", findings: "ib.AuditFindings", say) -> None:
    counts = plan.counts
    derive_total = sum(counts[c] for c in ib.DERIVING_CLASSES)
    held_total = sum(counts[c] for c in ib.HELD_CLASSES)
    identified_held = sum(
        1 for p in plan.plans if ib.held(p.cls) and p.state == master.IDENTIFIED
    )
    sold_held = sum(1 for p in plan.plans if ib.held(p.cls) and p.state == master.SOLD)
    other_held = held_total - identified_held - sold_held

    say("CLASSES (identity-follows-sku.md §7.2)")
    say(f"  T3   {counts[ib.T3]:>5}  derive — a human act chose this SKU")
    say(f"  T5   {counts[ib.T5]:>5}  HOLD — read disputes the SKU, or is blank, no human act")
    say(f"  T4s  {counts[ib.T4S]:>5}  HOLD — number disagrees, name names more than one product")
    say(f"  T4u  {counts[ib.T4U]:>5}  derive — number disagrees, name names exactly one (D162)")
    say(f"  T1   {counts[ib.T1]:>5}  derive — name equal after the fold")
    say(f"  T2   {counts[ib.T2]:>5}  derive — name a near miss, not disputed")
    say(f"  T6   {counts[ib.T6]:>5}  no SKU — nothing to derive")
    say(f"  {ib.SKU_UNKNOWN:<4} {counts[ib.SKU_UNKNOWN]:>5}  SKU not yet in the table")
    say("")
    say(f"  {derive_total} derive, {held_total} held "
        f"({identified_held} identified, {sold_held} sold"
        + (f", {other_held} other" if other_held else "") + ")")

    disputed_names = [
        p for p in plan.plans
        if p.cls == ib.T3 and p.classification.new_name is not None
        and (p.read_name or "").strip().upper() != p.classification.new_name.strip().upper()
    ]
    if disputed_names:
        say("")
        say(f"T3 CARDS WHOSE DRAWN NAME WILL DISPUTE THE READ ({len(disputed_names)}, "
            "ruling 2 — derive, listed once):")
        for p in disputed_names[:80]:
            say(f"    {p.key}  read {p.read_name!r}  ->  {p.classification.new_name!r}")
        if len(disputed_names) > 80:
            say(f"    … and {len(disputed_names) - 80} more")

    say("")
    say("AUDIT (§4.3) — the store's own health, over whatever bindings already exist")
    say(f"  identity drift (bound card disagrees with its SKU row): {len(findings.identity_drift)}")
    say(f"  SKU absent from the table: {len(findings.sku_not_in_table)}")
    say(f"  product rarity disagreement: {len(findings.rarity_disagreement)}")

    say("")
    say("NAME/NUMBER CONTRADICTIONS (§5.5 — replaces `cards contradictions`/`cards "
        "sku-names`, human-bound cards excluded)")
    say(f"  name half (read disputes its own bound SKU): {len(findings.name_half)}")
    say(f"  number half (read number disagrees with its own bound SKU): {len(findings.number_half)}")


def _identity(args, say) -> int:
    """`docs/specs/identity-follows-sku.md` §5.5, §7 (lane 2). Previews by default; `--write`
    performs the one-time migration. NEVER calls `db.connect` for the preview half — see the
    module docstring."""
    write = bool(getattr(args, "write", False))
    directory = files.inventory_dir()
    plan, findings, skus = _read_plan(directory)

    say(f"IDENTITY  {db.path(directory)}")
    say(f"  {len(plan.plans)} card(s) checked; {'WRITING' if write else 'PREVIEW, nothing will be written'}")
    say("")
    _print_plan(plan, findings, say)

    if not write:
        say("")
        say("Nothing was written. Re-run with `--write` to bind every deriving class and "
            "hold the rest — re-runnable, and a card already bound correctly is skipped.")
        return 0

    started = time.monotonic()
    census = {
        "bound": 0, "unchanged": 0, "held": 0, "review_opened": 0, "sold_reported": 0,
        "skipped_moved": 0,
    }
    with Store().write() as snapshot:
        for p in plan.plans:
            card = snapshot.inventory.cards.get(p.key)
            if card is None or card.sku != p.sku:
                # THE IN-LOCK RE-CHECK `cards variants`/`cards photos` ALREADY MAKE (§7.3's
                # own words): a card whose SKU moved between the preview above and this
                # write is a card this pass no longer has authority to describe.
                census["skipped_moved"] += 1
                continue
            card.read_name = p.read_name
            card.read_number = p.read_number
            card.read_printed_total = p.read_printed_total
            if ib.derives(p.cls):
                if card.identity_source == IDENTITY_SKU and card.sku == p.sku:
                    census["unchanged"] += 1
                    continue
                row = p.classification.row
                strategy = games_module.get(p.game)["join_key"]
                product_line = games_module.get(p.game).get("product_line")
                disputed = ib.name_disputes(p.read_name, [ib._row_dict(row)])
                snapshot.inventory.bind_sku(
                    p.key, p.sku, bound_by="migration", skus=snapshot.skus,
                    number_strategy=strategy, expected_product_line=product_line,
                    read_disputes=disputed, event="sku_bound",
                )
                # THE CLASS, RECORDED ON THE EVENT (§7.3, "with the class recorded on the
                # event") — `bind_sku`'s own `event=` only renames the line, and lane 1's
                # signature (owned by that lane, not this one) carries no field for it, so
                # this is a second, plain line beside the one `bind_sku` already appends,
                # never a second WRITER of the identity itself.
                snapshot.inventory.events.append({
                    "at": master.now(), "event": "identity_migration_classified",
                    "position": p.key, "sku": p.sku, "class": p.cls,
                })
                census["bound"] += 1
            elif ib.held(p.cls):
                if card.identity_source != IDENTITY_READ:
                    card.identity_source = IDENTITY_READ
                    census["held"] += 1
                if card.state == master.IDENTIFIED:
                    entry = ib.held_review_entry(card, p.classification.row, plan)
                    if snapshot.review.upsert(entry):
                        census["review_opened"] += 1
                elif card.state == master.SOLD:
                    census["sold_reported"] += 1
    elapsed = time.monotonic() - started

    say("")
    say("WROTE")
    say(f"  bound (T1/T2/T3/T4u, bound_by=migration): {census['bound']}")
    say(f"  already correctly bound, skipped: {census['unchanged']}")
    say(f"  held (identity_source=read): {census['held']}")
    say(f"  review entries opened (listing_disputed): {census['review_opened']}")
    say(f"  sold and held, report only: {census['sold_reported']}")
    if census["skipped_moved"]:
        say(f"  SKIPPED, SKU moved since the preview: {census['skipped_moved']}")
    say(f"  write took {elapsed:.2f}s, including every FTS index trigger the identity "
        "writes above fired (§5.2 — no FTS change was needed, the existing trigger indexes "
        "the new `name`/`number` on every UPDATE)")
    say("")
    say("VERDICT: migration written. Zero held cards changed identity; every card that "
        "moved is in T1, T2, T3 or T4u.")
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


_SUBCOMMANDS = {
    "name": _name,
    "audit": _audit,
    "checks": _checks,
    "identity": _identity,
    "contradictions": cmd_sku_contradictions.run,
    "sku-names": cmd_sku_name_contradictions.run,
    "photos": _photos,
    "variants": _variants,
}


def run(args, say) -> int:
    action = getattr(args, "cards_action", None)
    handler = _SUBCOMMANDS.get(action)
    if handler is None:
        say("pkmnscan cards <name|audit|checks|identity|contradictions|sku-names|photos|variants>")
        return 2
    return handler(args, say)
