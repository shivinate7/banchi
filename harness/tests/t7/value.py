"""T7 group: value table and value page.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.
"""

from __future__ import annotations

import os

from datetime import datetime, timezone
from typing import List
from harness.tests import Checks
from pipeline import corpus, readings
from server import pipeline_routes
from store import files, master
from store.session import Store
from harness.tests.t7.common import (
    fake_cid,
    isolated_home,
)


def check_value_table(checks: Checks) -> None:
    """Every card on hand, ranked by what it is worth, with nothing dropped.

    THE OWNER ASKED FOR THIS AND THE MEASUREMENT SHAPED IT: *"a way to see at all times ...
    either the most valuable or least valuable cards so maybe i can easily start querying them
    for bulk collection and taking them out of boxes"*. What the store said when it was
    measured before anything was built is why the cases below are the cases: 122 of their
    cards sit at or above $5 and those are only 38 SKUs, 1,042 sit under the cut-off, and 390
    of 2,245 cards on hand carry no market price at all.

    THE FIXTURE IS THAT SHAPE IN MINIATURE — one SKU in three slots, one cheap SKU, a card
    never identified, a card identified with nothing read off it, a SKU with no reading, a
    malformed market cell, and a sold copy — because every claim here is about a case a
    smaller store does not contain.

    WHAT IT ASSERTS THAT NOTHING ELSE DOES: that the newest reading wins ON A CLOCK rather
    than on a precedence between run tables and live exports. The obvious rule — "a live fetch
    beats a run table" — is wrong on the owner's own store today, where the newest fetch is a
    day older than the newest join, and a fixed precedence would serve the stale figure for
    every SKU both files carry.
    """
    checks.note("")
    checks.note("VALUE TABLE — every card on hand, ranked, nothing dropped")

    RICH, CHEAP, UNREAD, BROKEN = "9027460", "8925667", "7000001", "7000002"

    with isolated_home():
        with Store().write() as snapshot:
            inventory = snapshot.inventory
            inventory.ensure_box(1, name="WB1 R2")
            inventory.ensure_box(2, name="ME01 C/UC")

            # A COUNTER RATHER THAN THE BOX OR THE SKU (D172). `put` is called thirteen times
            # across two drawers, and three of those calls are the SAME SKU in three slots —
            # so a seed built from either would name several cards alike, and `cards_cid`
            # refuses that, correctly: two cards cannot share one photograph's name.
            minted = 0

            def put(box: int, sku, name, state=master.IDENTIFIED):
                nonlocal minted
                minted += 1
                card, _ = inventory.allocate_capture(box, cid=fake_cid(f"value-{minted}"))
                card.sku = sku
                card.name = name
                card.game = "riftbound"
                card.state = state
                return card

            # ONE SKU IN THREE SLOTS — the case that decides the unit of the row. On the
            # owner's store this is Rengar, Trophy Hunter at $41.57 in three slots of box 4.
            for _ in range(3):
                put(1, RICH, "Last Rites")
            put(1, CHEAP, "Towering Combatant")
            put(1, UNREAD, "A card no export prices")
            put(1, BROKEN, "A card whose market cell is junk")
            # NEVER IDENTIFIED — captured and waiting on a run. 214 of the owner's.
            put(1, None, None, state=master.CAPTURED)
            # IDENTIFIED AND THE MODEL READ NOTHING — a photograph and no SKU. 172 of theirs.
            put(1, None, "")
            # DEPARTED — must not appear at all.
            put(1, RICH, "Last Rites", state=master.SOLD)
            # A second drawer, entirely cheap, which is the shape boxes 2 and 5 have.
            for _ in range(4):
                put(2, CHEAP, "Towering Combatant")
            inventory.listing(RICH).live = 2

        def table(run: str, at: float, rows) -> None:
            directory = files.runs_dir() / run
            directory.mkdir(parents=True, exist_ok=True)
            files.write_json(directory / "manifest.json", {"joined": True})
            path = directory / "pricing.json"
            files.write_json(path, {"run": run, "skus": rows})
            os.utime(path, (at, at))

        def row(sku, market, name, set_name="Spiritforged"):
            return {
                "sku": sku,
                "name": name,
                "set_name": set_name,
                "condition": "Near Mint Foil",
                "snap": {"market": market},
            }

        OLD, NEW = 1789000000, 1789100000
        table("2026-09-01-box1-01", OLD, [row(RICH, "9.00", "Last Rites"), row(BROKEN, "", "Junk")])
        table(
            "2026-09-11-box1-02",
            NEW,
            [row(RICH, "47.57", "Last Rites"), row(CHEAP, "0.03", "Towering Combatant")],
        )
        # A LIVE FETCH OLDER THAN THE NEWEST RUN TABLE, which is the owner's actual situation.
        # Its figure for RICH must LOSE, and its figure for BROKEN must still win — the clock
        # is per SKU and not per file.
        live = files.inventory_dir() / pipeline_routes.LIVE_DIR
        live.mkdir(parents=True, exist_ok=True)
        stamp = datetime.fromtimestamp(OLD + 1, timezone.utc).strftime("%Y%m%d-%H%M%S")
        header = (
            "TCGplayer Id,Product Line,Set Name,Product Name,Title,Number,Rarity,Condition,"
            "TCG Market Price,TCG Direct Low,TCG Low Price With Shipping,TCG Low Price,"
            "Total Quantity,Add to Quantity,TCG Marketplace Price,Photo URL"
        )
        body = "\r\n".join(
            [
                header,
                f'"{RICH}","Riftbound","Spiritforged","Last Rites","","","","Near Mint Foil","1.00","","","","2","0","1.00",""',
                f'"{BROKEN}","Riftbound","Spiritforged","Junk","","","","Near Mint","not-a-price","","","","0","0","0.00",""',
            ]
        )
        (live / f"{pipeline_routes.LIVE_PREFIX}{stamp}.csv").write_bytes(
            (body + "\r\n").encode("utf-8")
        )

        book = corpus.Corpus.read()
        book.threshold = "0.29"
        book.answers[RICH] = corpus.Answer(value="44.00")
        book.write()

        # `_readings()` IS A SELECT NOW (D189): the run tables and the live
        # export just written to disk answer nothing until a `readings adopt --write` folds
        # them into the `readings` table, exactly as `pkmnscan readings adopt --write` does.
        # `pipeline.readings.collect()` is the identical two-source walk the old live
        # `_readings()` ran inline; only WHEN it runs moved.
        with Store().write() as snapshot:
            snapshot.readings.replace(*readings.collect())

        payload = pipeline_routes.do_pipeline_value()
        copies = payload["copies"]
        at = {(row["box"], row["index"]): row for row in copies}

        # --- the unit is the copy ---------------------------------------------------------
        checks.equal(
            sum(1 for row in copies if row["sku"] == RICH),
            3,
            "one SKU in three slots draws three rows, not one",
        )
        checks.equal(len(copies), 12, "every card on hand is a row and the sold one is not")
        checks.ok(
            all(row["state"] not in master.TERMINAL_STATES for row in copies),
            "a departed copy is in no band",
        )

        # --- the newest reading wins on the clock, per SKU ---------------------------------
        checks.equal(
            at[(1, 1)]["market"],
            "47.57",
            "the newest run table beats an OLDER live fetch (never a file precedence)",
        )
        checks.equal(
            at[(1, 1)]["source"],
            "2026-09-11-box1-02",
            "and the row says which file answered it",
        )

        # --- nothing on hand is omitted, and the three causes stay apart ------------------
        checks.equal(
            at[(1, 6)]["market"], None, "a market cell that will not parse is unpriced"
        )
        checks.equal(
            at[(1, 6)]["why"],
            "no_reading",
            "and it is `no_reading`, NEVER $0.00 — a junk cell ranked as zero lands in a bulk pull",
        )
        checks.equal(at[(1, 5)]["why"], "no_reading", "a SKU no file prices is `no_reading`")
        checks.equal(
            at[(1, 7)]["why"],
            "never_identified",
            "a captured card with no SKU is `never_identified` — the remedy is a run",
        )
        checks.equal(
            at[(1, 8)]["why"],
            "read_nothing",
            "an identified card the model read nothing off is `read_nothing` — a human looks at it",
        )
        checks.equal(
            payload["unrankable"],
            {
                "total": 4,
                "never_identified": 1,
                "read_nothing": 1,
                "no_reading": 2,
                "by_box": {"1": 4},
            },
            "and the header counts all four with each cause named",
        )

        # --- the order is the band ---------------------------------------------------------
        priced = [row for row in copies if row["market"] is not None]
        checks.equal(
            [row["market"] for row in priced[:3]],
            ["47.57", "47.57", "47.57"],
            "sorted by market descending",
        )
        checks.equal(
            [(row["box"], row["index"]) for row in priced[:3]],
            [(1, 1), (1, 2), (1, 3)],
            "ties break on (box, index), so one price is one reach into the drawer",
        )
        checks.ok(
            all(row["market"] is not None for row in copies[: len(priced)]),
            "unpriced rows sort last and never interleave with the cheap band",
        )

        # --- the drawer is not a rollup of the priced rows ---------------------------------
        drawer = {row["box"]: row for row in payload["boxes"]}
        checks.equal(drawer[1]["cards"], 8, "a drawer counts every card in it")
        checks.equal(drawer[1]["unpriced"], 4, "including the ones it cannot price")
        checks.equal(
            drawer[1]["per_card"],
            "17.84",
            "and the mean divides by ALL of them — dividing by the priced subset flatters the drawer",
        )
        checks.equal(drawer[2]["under_cutoff"], 4, "box 2 is entirely under the cut-off")
        checks.equal(drawer[2]["at_or_over"], 0, "with nothing at or over it")
        checks.equal(drawer[1]["top"], "47.57", "and a drawer says its best card")
        checks.equal(drawer[2]["name"], "ME01 C/UC", "a drawer carries the name the owner gave it")

        # --- the rest of the row ------------------------------------------------------------
        checks.equal(
            at[(1, 1)]["label"],
            "WB1 R2, Section 1, Card 1",
            "the label is composed against the box as it stands now (D58)",
        )
        checks.equal(at[(1, 1)]["live"], 2, "the row says how many copies TCGplayer holds")
        checks.equal(
            at[(1, 1)]["answer"],
            "44.00",
            "and what the operator decided to ask, which is not what it is worth (D86)",
        )
        checks.equal(payload["threshold"], "0.29", "the cut-off is the store's own (D9)")
        checks.equal(
            payload["totals"]["valued"], 8, "the totals count what could actually be ranked"
        )
        # NEW, ADDITIVE TOTALS FIELDS — the sum of every box's own
        # under_cutoff/at_or_over, checked explicitly since `checks.equal` above compares only
        # `totals["valued"]` and not the whole dict.
        checks.equal(
            payload["totals"]["under_cutoff"],
            5,
            "the store-wide under-cutoff total is the sum of every box's own figure "
            "(1 CHEAP copy in box 1, 4 in box 2)",
        )
        checks.equal(
            payload["totals"]["at_or_over"],
            3,
            "and the store-wide at-or-over total is the sum of every box's own figure "
            "(the 3 RICH copies in box 1)",
        )
        checks.equal(
            {row["kind"] for row in payload["sources"]},
            {"run", "live"},
            "and both kinds of source are named",
        )

    # A STORE WITH NOTHING IN IT ANSWERS, RATHER THAN REFUSING. This is the fresh checkout, and
    # it is the state every worktree in this repo is in.
    with isolated_home():
        empty = pipeline_routes.do_pipeline_value()
        checks.equal(
            (empty["copies"], empty["boxes"], empty["totals"]["cards"]),
            ([], [], 0),
            "an empty store answers an empty table and never a refusal",
        )
        checks.equal(
            (empty["totals"]["under_cutoff"], empty["totals"]["at_or_over"]),
            (0, 0),
            "the new totals fields read 0 on an empty store too",
        )


def check_value_page(checks: Checks) -> None:
    """`GET /pipeline/value?band=...` — the paginated sibling of
    `do_pipeline_value()` must never disagree with the whole-list route it pages through.

    THE FIXTURE IS `check_value_table`'S OWN SHAPE, rebuilt here rather than shared, because
    the two tests assert different things about it (that one, the row's fields and the
    aggregates' arithmetic; this one, that paging reconstructs the SAME order and that a
    cursor survives a store change between two fetches) and a shared builder would couple
    them to one signature neither fully needs.
    """
    checks.note("")
    checks.note("VALUE PAGE — the paginated route must never disagree with the whole list")

    RICH, CHEAP, UNREAD, BROKEN = "9027460", "8925667", "7000001", "7000002"

    def build() -> None:
        with Store().write() as snapshot:
            inventory = snapshot.inventory
            inventory.ensure_box(1, name="WB1 R2")
            inventory.ensure_box(2, name="ME01 C/UC")
            minted = 0

            def put(box: int, sku, name, state=master.IDENTIFIED):
                nonlocal minted
                minted += 1
                card, _ = inventory.allocate_capture(box, cid=fake_cid(f"page-{minted}"))
                card.sku = sku
                card.name = name
                card.game = "riftbound"
                card.state = state
                return card

            for _ in range(3):
                put(1, RICH, "Last Rites")
            put(1, CHEAP, "Towering Combatant")
            put(1, UNREAD, "A card no export prices")
            put(1, BROKEN, "A card whose market cell is junk")
            put(1, None, None, state=master.CAPTURED)
            put(1, None, "")
            for _ in range(4):
                put(2, CHEAP, "Towering Combatant")

        def table(run: str, at: float, rows) -> None:
            directory = files.runs_dir() / run
            directory.mkdir(parents=True, exist_ok=True)
            files.write_json(directory / "manifest.json", {"joined": True})
            path = directory / "pricing.json"
            files.write_json(path, {"run": run, "skus": rows})
            os.utime(path, (at, at))

        def row(sku, market, name, set_name="Spiritforged"):
            return {
                "sku": sku,
                "name": name,
                "set_name": set_name,
                "condition": "Near Mint Foil",
                "snap": {"market": market},
            }

        table(
            "2026-09-11-box1-02",
            1789100000,
            [row(RICH, "47.57", "Last Rites"), row(CHEAP, "0.03", "Towering Combatant")],
        )
        book = corpus.Corpus.read()
        book.threshold = "0.29"
        book.write()
        with Store().write() as snapshot:
            snapshot.readings.replace(*readings.collect())

    with isolated_home():
        build()

        whole = pipeline_routes.do_pipeline_value()
        priced_whole = [row for row in whole["copies"] if row["market"] is not None]

        # --- top, paged with limit=2, reconstructs the whole priced order ------------------
        seen: List[dict] = []
        after = None
        pages = 0
        while True:
            pages += 1
            checks.ok(pages < 20, "the page loop must terminate well before 20 rounds")
            page = pipeline_routes.do_pipeline_value_page(
                band="top", box=None, after=after, limit=2
            )
            seen.extend(page["rows"])
            after = page["next"]
            if after is None:
                break
        checks.equal(
            [(row["box"], row["index"]) for row in seen],
            [(row["box"], row["index"]) for row in priced_whole],
            "paging band=top with limit=2 reconstructs the exact same priced-row sequence "
            "`do_pipeline_value()` returns whole",
        )
        first_page_rows = pipeline_routes.do_pipeline_value_page(
            band="top", box=None, after=None, limit=2
        )["rows"]
        # THE PAGINATED ROUTE'S ROWS CARRY TWO MORE FIELDS THAN THE WHOLE LIST'S — `stack_index`
        # and `stack_of` (§A3 point 4), added because the client no longer holds the whole
        # band in memory to compute "copy N of M" itself. Every OTHER field must agree exactly.
        checks.equal(
            [{k: v for k, v in row.items() if k not in ("stack_index", "stack_of")}
             for row in first_page_rows],
            priced_whole[:2],
            "the first page agrees byte-for-byte with the first two rows of the whole list, "
            "aside from the stack fields the whole-list route does not carry — the two code "
            "paths must never disagree",
        )
        checks.equal(
            [(row["stack_index"], row["stack_of"]) for row in first_page_rows],
            [(1, 3), (2, 3)],
            "and the stack fields say which of the three tied RICH copies each row is",
        )

        # --- bottom reconstructs the priced rows ascending, ties ascending by (box, index) --
        bottom_seen: List[dict] = []
        after = None
        while True:
            page = pipeline_routes.do_pipeline_value_page(
                band="bottom", box=None, after=after, limit=2
            )
            bottom_seen.extend(page["rows"])
            after = page["next"]
            if after is None:
                break
        expected_bottom = sorted(priced_whole, key=pipeline_routes._value_sort_key_reversed)
        checks.equal(
            [(row["box"], row["index"]) for row in bottom_seen],
            [(row["box"], row["index"]) for row in expected_bottom],
            "band=bottom is a REAL ascending comparator — box/index ascending within a tie — "
            "never a `list.reverse()` of the top-sorted array",
        )
        checks.ok(
            [(row["box"], row["index"]) for row in bottom_seen]
            != list(reversed([(row["box"], row["index"]) for row in seen])),
            "a literal reverse of `top`'s order would also reverse the tie-break; this must "
            "differ from that on the RICH trio, which ties at one price",
        )

        # --- gaps reconstructs every unpriced row in (box, index) order ---------------------
        gaps_seen: List[dict] = []
        after = None
        while True:
            page = pipeline_routes.do_pipeline_value_page(
                band="gaps", box=None, after=after, limit=2
            )
            gaps_seen.extend(page["rows"])
            after = page["next"]
            if after is None:
                break
        checks.equal(
            [(row["box"], row["index"]) for row in gaps_seen],
            sorted((row["box"], row["index"]) for row in whole["copies"] if row["market"] is None),
            "band=gaps reconstructs every unpriced row in natural (box, index) order",
        )
        checks.equal(
            len(gaps_seen), whole["unrankable"]["total"], "and its count equals `unrankable.total`"
        )

        # --- the D277 arm: aggregates never shrink to what one page could see ---------------
        for band in ("top", "bottom", "gaps"):
            first_page = pipeline_routes.do_pipeline_value_page(
                band=band, box=None, after=None, limit=1
            )
            checks.equal(
                first_page["unrankable"],
                whole["unrankable"],
                f"band={band}, limit=1 (the very first page) still reports the FULL "
                "store-wide unrankable block — the three `why` causes never shrink to "
                "what one page could see",
            )
            checks.equal(
                first_page["boxes"],
                whole["boxes"],
                f"band={band}'s `boxes` block is identical to the whole list's, describing "
                "the whole store rather than the band",
            )
            checks.equal(
                first_page["totals"]["valued"],
                whole["totals"]["valued"],
                f"band={band}'s `totals.valued` is the whole store's, not the page's",
            )

        # --- a malformed cursor is the first page, never a 400 -------------------------------
        garbled = pipeline_routes.do_pipeline_value_page(
            band="top", box=None, after="not-a-real-cursor!!", limit=2
        )
        checks.equal(
            [(row["box"], row["index"]) for row in garbled["rows"]],
            [(row["box"], row["index"]) for row in priced_whole[:2]],
            "an unreadable `after` token restarts the band from the top rather than refusing",
        )

        # --- an unknown band is refused, loudly --------------------------------------------
        try:
            pipeline_routes.do_pipeline_value_page(
                band="sideways", box=None, after=None, limit=2
            )
            checks.ok(False, "an unrecognised band must raise, not fall through silently")
        except pipeline_routes.PipelineRefusal as exc:
            checks.equal(exc.code, "band_unknown", "and it names the refusal `band_unknown`")

        # --- a stale cursor: the named row left the store between two fetches ---------------
        page1 = pipeline_routes.do_pipeline_value_page(
            band="top", box=None, after=None, limit=1
        )
        cursor = page1["next"]
        stale_row = page1["rows"][0]
        with Store().write() as snapshot:
            key = master.position_key(stale_row["box"], stale_row["index"])
            snapshot.inventory.cards.get(key).state = master.SOLD
        after_sale = pipeline_routes.do_pipeline_value_page(
            band="top", box=None, after=cursor, limit=10
        )
        # `stale_row` was priced_whole[0] (the first page, limit=1). Selling it does not
        # change the rank of anything else — including the OTHER two RICH copies, which tie
        # with it on market and would be silently skipped by an equality-only cursor search
        # (see the comment on the cursor comparison in `do_pipeline_value_page`). The correct
        # remainder is simply everything that was ranked after it.
        checks.equal(
            (stale_row["box"], stale_row["index"]),
            (priced_whole[0]["box"], priced_whole[0]["index"]),
            "sanity: the stale row really is the first page's only row",
        )
        checks.equal(
            [(row["box"], row["index"]) for row in after_sale["rows"]],
            [(row["box"], row["index"]) for row in priced_whole[1:]],
            "a cursor naming a row that has since left the store still returns the correct "
            "remaining rows — including a same-price TIE the sold row sat in front of — "
            "comparing BY VALUE rather than by a remembered list index or exact row identity",
        )


CHECKS = (
    check_value_table,
    check_value_page,
)
