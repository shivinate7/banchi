"""T7 group: pipeline sets and stock images.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.
"""

from __future__ import annotations

import json
import tempfile
import time
from datetime import datetime, timedelta, timezone

from pathlib import Path
from typing import List
from harness.tests import Checks
from pipeline import games, pricehistory, stockimages
from store.readings import Reading
from store.skus import SkuRow
from server import capture_server, pipeline_routes
from store import master
# `orders` is already `pipeline.orders` above. The store's ledger is a DIFFERENT module
# — the resolver computes and stores nothing, this one persists — so it takes an alias
# rather than shadowing the name half this file's order cases are written against.
from store import orders as order_store
from store.session import Store
from harness.tests.t7.common import (
    QuietHandler,
    _spawn_server,
    request,
    answers,
    capture_payload,
    fake_cid,
    isolated_home,
)


def check_pipeline_sets(checks: Checks) -> None:
    """`GET /pipeline/sets` — the owner's "by set order" view (D293).

    ON HAND MEANS `identified`, NARROWER THAN `do_pipeline_value`'s "not a terminal state":
    a captured-and-not-yet-identified card, a sold one, a retired one and a moved one are
    all excluded, and the fixture below plants one of each so a card wrongly included is a
    row this test can point at.

    THE GROUPING RUNGS: a SKU groups every physical copy of it into one row with a summed
    `qty`; a `sku_unknown` card with a name and a number groups on those; a card with none
    of the three (no SKU, no name, no number) is its own row, because nothing here can tell
    it apart from another blank card, and merging on a shared blank key would silently
    collapse two distinct physical cards into one.

    THE ORDER IS A NATURAL SORT OVER THE RAW `number` COLUMN, never a per-game rule:
    `087/298` < `089a/298` < `090/298`, because the digit run before the letter is compared
    as an integer (87 < 89 < 90) rather than as text, where `'089a' < '090'` would be false.
    """
    checks.note("")
    checks.note("PIPELINE SETS — grouped by set, natural-sorted, on hand only")

    RICH = "9027460"

    with isolated_home():
        with Store().write() as snapshot:
            inventory = snapshot.inventory
            inventory.ensure_box(1, name="Spiritforged box")

            minted = 0

            def put(sku, name, number, printed_total, set_name, game="riftbound", state=master.IDENTIFIED):
                nonlocal minted
                minted += 1
                card, _ = inventory.allocate_capture(1, cid=fake_cid(f"sets-{minted}"))
                card.sku = sku
                card.name = name
                card.number = number
                card.printed_total = printed_total
                card.set_name = set_name
                card.game = game
                card.state = state
                return card

            # THE NATURAL-SORT CASE, three rows of one set, planted out of printed order so
            # a route that merely echoed insertion order would pass by accident.
            put(RICH, "Towering Combatant", "090", "298", "Spiritforged")
            put("8925668", "Ancient Henge", "087", "298", "Spiritforged")
            put("8925669", "Corina Veraza", "089a", "298", "Spiritforged")

            # TWO PHYSICAL COPIES OF ONE SKU — one row, `qty: 2`.
            put(RICH, "Towering Combatant", "090", "298", "Spiritforged")

            # A SECOND SET, SAME GAME — proves grouping is per (game, set), not per game
            # alone. TWO MORE ROWS HERE, "9" and "10", are the digit-WIDTH case a plain
            # lexicographic sort cannot pass: as text "10" < "9" (`'1' < '9'`), so a mutation
            # that dropped the natural sort for `str.lower()` alone would still pass the
            # 087/089a/090 case above (same digit width, so text order and numeric order
            # coincide there) and only goes red on this one.
            put("8611100", "Progress Day", "114", "298", "Origins")
            put("8611101", "Ninth", "9", "298", "Origins")
            put("8611102", "Tenth", "10", "298", "Origins")

            # A SKU_UNKNOWN CARD WITH A NAME AND A NUMBER — groups on those, not dropped for
            # having no SKU.
            put(None, "Read Off The Photo", "200", "298", "Spiritforged")

            # TWO BLANK CARDS — no SKU, no name, no number. Each is its own row: merging them
            # on a shared blank key would report one card where two physical ones are on hand.
            put(None, None, None, None, "Spiritforged")
            put(None, None, None, None, "Spiritforged")

            # NO SET ON FILE — its own group, at the end, never a silent drop.
            put("7000001", "No Set On File", "1", "1", "")

            # THE THREE EXCLUSIONS: not `identified`, so none of these may appear anywhere
            # in the payload.
            put("7100000", None, None, None, None, state=master.CAPTURED)
            put("7100001", "Sold Already", "1", "1", "Spiritforged", state=master.SOLD)
            put("7100002", "Retired Already", "2", "1", "Spiritforged", state=master.RETIRED)
            put("7100003", "Moved Already", "3", "1", "Spiritforged", state=master.MOVED)

        payload = pipeline_routes.do_pipeline_sets()

    groups = {(g["game"], g["set_name"]): g for g in payload["groups"]}

    checks.equal(
        len(payload["groups"]),
        2,
        "two named sets (Spiritforged, Origins) — the excluded states and the no-set "
        "card are not among them",
    )

    spiritforged = groups.get(("riftbound", "Spiritforged"))
    checks.ok(spiritforged is not None, "the Spiritforged group exists")
    if spiritforged is not None:
        # THE TWO BLANK CARDS SHARE THIS SET TOO (checked further down) and their number
        # sorts first — `('',)`, a prefix of every numbered card's own `('', N, '')` — so
        # this order check reads only the rows that have a number at all.
        numbers = [c["number_display"] for c in spiritforged["cards"] if c["number_display"] is not None]
        checks.equal(
            numbers,
            ["087/298", "089a/298", "090/298", "200/298"],
            "NATURAL SORT: 089a sits between 087 and 090 — the digit run compares as an "
            "integer (87 < 89 < 90), not as text, where '089a' < '090' would be false",
        )
        by_number = {c["number_display"]: c for c in spiritforged["cards"]}
        checks.equal(
            by_number["090/298"]["qty"],
            2,
            "two physical copies of one SKU are one row with qty 2, not two rows",
        )
        checks.equal(
            by_number["200/298"]["sku"],
            None,
            "a sku_unknown card groups on its name and number, and is not dropped for "
            "having no SKU",
        )

    origins = groups.get(("riftbound", "Origins"))
    checks.ok(
        origins is not None and len(origins["cards"]) == 3,
        "a second set groups on its own, never folded into the first",
    )
    if origins is not None:
        checks.equal(
            [c["number_display"] for c in origins["cards"]],
            ["9/298", "10/298", "114/298"],
            "DIGIT WIDTH: '9' sorts before '10' numerically, though '10' < '9' as text — "
            "the case a plain string sort passes on 087/089a/090 (same width) and fails "
            "here",
        )

    checks.equal(
        len(payload["no_set"]),
        1,
        "a card with no set on file is one more group, at the end, never a silent drop",
    )
    checks.equal(
        payload["no_set"][0]["name"],
        "No Set On File",
        "and it is the right card",
    )

    blanks = [c for c in spiritforged["cards"] if c["name"] is None] if spiritforged else []
    checks.equal(
        len(blanks),
        2,
        "TWO BLANK CARDS ARE TWO ROWS, not one merged on a shared blank key — the defect "
        "caught against the owner's own store, where four such cards would otherwise have "
        "collapsed into a single row a tap could reach only one of",
    )
    checks.equal(
        len({c["cid"] for c in blanks}),
        2,
        "and each blank row's `cid` names a DIFFERENT physical card",
    )

    all_cards = [c for g in payload["groups"] for c in g["cards"]] + payload["no_set"]
    excluded_names = {"Sold Already", "Retired Already", "Moved Already"}
    checks.ok(
        all(c["name"] not in excluded_names for c in all_cards),
        "a sold, a retired and a moved card are all excluded from every group",
    )
    checks.equal(
        sum(1 for c in all_cards if c["sku"] == "7100000"),
        0,
        "a captured-and-not-yet-identified card carries no set or number to group by, "
        "and is excluded too",
    )
    total_qty = sum(c["qty"] for g in payload["groups"] for c in g["cards"]) + sum(
        c["qty"] for c in payload["no_set"]
    )
    checks.equal(
        total_qty,
        11,
        "on-hand qty sums to exactly the identified cards planted: 3 Spiritforged SKUs + "
        "1 extra RICH copy + 3 Origins + 1 sku_unknown + 2 blanks + 1 no-set = 11",
    )


def check_stock_images(checks: Checks) -> None:
    """`pipeline/stockimages.py` (`D301`) — both sources stubbed, never a socket.

    THREE THINGS THE REVIEW ROUND NAMED. The Pokemon "CODE: " prefix match — the store's
    own `set_name` for ME01 is "ME01: Mega Evolution" against the vendored tree's plain
    "Mega Evolution", 0 of 542 real-store cards resolving before the fix. A miss answering
    `None`. And the route threading — `do_pipeline_sets`/`do_pipeline_worklist` actually
    carry `image_url` when handed a resolver, and carry `None` (open no socket) when not.

    BOTH SOURCES ARE STUBBED. Pokemon reads a throwaway `vendor/pokemon-tcg-data/`-shaped
    tree under a temp dir, never the real vendored one — this proves the CLASS's own fold,
    not today's snapshot. Riftbound's tcgcsv walk goes through a fake `fetcher`, the same
    `pricehistory.Market(fetcher=...)` idiom `check_price_history` already uses.

    THE BACKGROUND-WARM SHAPE ITSELF (the review's second finding: a cold cache must never
    block a request). `url_for` before `warm()` answers `None` at once, off a fetcher that
    would otherwise sleep; `warm()`'s own threads, joined, are what makes the SECOND call
    deterministic rather than a race against a background thread this test never waited
    for.
    """
    checks.note("")
    checks.note("STOCK IMAGES — both sources stubbed, the prefix fix, and the route thread")

    with tempfile.TemporaryDirectory() as tmp:
        vendor_root = Path(tmp) / "pokemon-tcg-data"
        sets_dir = vendor_root / "sets"
        cards_dir = vendor_root / "cards" / "en"
        sets_dir.mkdir(parents=True)
        cards_dir.mkdir(parents=True)
        (sets_dir / "en.json").write_text(
            json.dumps([
                {"id": "me1", "name": "Mega Evolution"},
                # A REAL SET WHOSE OWN NAME CARRIES A COLON — the review round's own
                # regression: a client-side `^[^:]+:\s*` strip, run unconditionally, turned
                # this into "Classic Collection". The unstripped name must hit HERE, on the
                # first try, before any stripping is ever considered.
                {"id": "cel", "name": "Celebrations: Classic Collection"},
            ]),
            "utf-8",
        )
        (cards_dir / "me1.json").write_text(
            json.dumps([
                {"number": "1", "images": {"small": "https://images.pokemontcg.io/me1/1.png"}},
            ]),
            "utf-8",
        )
        (cards_dir / "cel.json").write_text(json.dumps([]), "utf-8")
        pokemon = stockimages._PokemonImages(root=vendor_root)

        # `SetGroupCard`/`PricingSku` both carry the store's OWN `set_name` cell, which for
        # a Pokemon set is "CODE: Name" — never the vendored tree's plain "Name". This is
        # the exact string the real-store measurement found at 0% before the fix.
        checks.equal(
            pokemon.url_for("ME01: Mega Evolution", "1"),
            "https://images.pokemontcg.io/me1/1.png",
            "the store's 'CODE: Name' set_name still resolves, stripped and refolded",
        )
        checks.equal(
            pokemon.url_for("Mega Evolution", "1"),
            "https://images.pokemontcg.io/me1/1.png",
            "a set_name with no code prefix still matches on its first try",
        )
        checks.equal(
            pokemon.url_for("ME01: Mega Evolution", "001/132"),
            "https://images.pokemontcg.io/me1/1.png",
            "a live export's 'number/total' cell resolves to the vendored bare number "
            "(a sold SKU with no photographed copy, #/revenue)",
        )
        checks.equal(
            pokemon.url_for("ME01: Mega Evolution", "999/132"),
            None,
            "a 'number/total' cell with an unknown number is still a miss",
        )
        checks.equal(
            pokemon.url_for("ME01: Mega Evolution", "999"),
            None,
            "a MISS is None, never a guess — this set exists, this number does not",
        )
        checks.equal(
            pokemon.url_for("ME99: No Such Set", "1"),
            None,
            "an unknown set, prefix stripped or not, is a miss and never raises",
        )

        # `display_name` — THE REVIEW ROUND'S FIX: `do_pipeline_sets` sends this, not the
        # store's raw `set_name`, so the client carries no regex of its own to keep in step
        # with the resolver's own two-try order.
        checks.equal(
            pokemon.display_name("ME01: Mega Evolution"),
            "Mega Evolution",
            "the code prefix is stripped for display too, resolved through the SAME "
            "two-try lookup as the photo — not a second, independent regex",
        )
        checks.equal(
            pokemon.display_name("Mega Evolution"),
            "Mega Evolution",
            "a set_name with no prefix still resolves on its first try",
        )
        checks.equal(
            pokemon.display_name("Celebrations: Classic Collection"),
            "Celebrations: Classic Collection",
            "THE REGRESSION THIS CASE GUARDS: a REAL set name that carries its own colon "
            "must hit the catalogue UNSTRIPPED and come back whole — a blind "
            "`^[^:]+:\\s*` strip run unconditionally on this string answers 'Classic "
            "Collection' instead, which is exactly the defect a client-side copy of the "
            "regex committed",
        )
        checks.equal(
            pokemon.display_name("ME99: No Such Set"),
            None,
            "a join miss answers None, never a guess at a stripped name",
        )

        images_for_names = stockimages.StockImages(pokemon=pokemon)
        checks.equal(
            images_for_names.display_name("pokemon", "ME01: Mega Evolution"),
            "Mega Evolution",
            "StockImages.display_name delegates to the Pokemon resolver",
        )
        checks.equal(
            images_for_names.display_name("riftbound", "SFD: Spiritforged"),
            None,
            "NEVER FOR RIFTBOUND OR ONE PIECE — the community code-prefix convention this "
            "exists to strip was measured on Pokemon rows alone; a non-Pokemon game answers "
            "None so the caller keeps the store's own name rather than guessing at one",
        )

    def make_fetcher():
        def fetcher(url: str):
            if url.endswith("/categories"):
                return {"results": [
                    {"name": "Riftbound League of Legends Trading Card Game", "categoryId": 89},
                ]}
            if url.endswith("/89/groups"):
                return {"results": [{"name": "Vendetta", "groupId": 24698}]}
            if url.endswith("/89/24698/products"):
                time.sleep(0.2)  # a real tcgcsv products fetch, standing in for the ~2s cold walk
                return {"results": [{
                    "imageUrl": "https://tcgplayer-cdn.tcgplayer.com/product/705996_200w.jpg",
                    "extendedData": [{"name": "Number", "value": "SP3/006"}],
                }]}
            raise AssertionError(f"unexpected fetch: {url}")
        return fetcher

    # A FRESH INSTANCE, ASKED ONCE, AND NEVER JOINED — `url_for` itself is what schedules a
    # background warm on a miss (its own docstring), so THIS instance's own thread is left
    # to finish on its own; the point of this half is only the CALLING thread's own timing.
    latency = stockimages.StockImages(
        market=pricehistory.Market(cache_dir=None, fetcher=make_fetcher()), pokemon=pokemon
    )
    started = time.time()
    cold = latency.url_for("riftbound", "Vendetta", "SP3/006")
    elapsed = time.time() - started
    checks.equal(cold, None, "a cold cache answers None, never the URL, on the first ask")
    checks.ok(
        elapsed < 0.1,
        f"and it answers in under 100ms even though the fetcher itself sleeps 200ms "
        f"(measured {elapsed*1000:.0f}ms) — the walk never runs on the calling thread",
    )

    # A SECOND, UNTOUCHED INSTANCE, WARMED EXPLICITLY AND JOINED — this is what makes the
    # follow-up read deterministic: `warm()` before any `url_for` call means the ONE thread
    # it returns is the only one racing this test, and joining it settles that race.
    images = stockimages.StockImages(
        market=pricehistory.Market(cache_dir=None, fetcher=make_fetcher()), pokemon=pokemon
    )
    threads = images.warm([("riftbound", "Vendetta")])
    checks.equal(len(threads), 1, "one background thread, for the one pair asked about")
    for thread in threads:
        thread.join(timeout=5)
    checks.equal(
        images.url_for("riftbound", "Vendetta", "SP3/006"),
        "https://tcgplayer-cdn.tcgplayer.com/product/705996_200w.jpg",
        "once the background warm has landed, url_for answers the real URL",
    )
    checks.equal(
        images.warm([("riftbound", "Vendetta")]),
        [],
        "a fresh entry schedules nothing a second time",
    )
    # SPACED-SLASH LOOKUP (measured on a real-store copy: 9 of 1913 on-hand Riftbound
    # misses, of which this shape — a raw number like `019 / 166`, not `019/166` — was the
    # one that was a spacing defect and not a genuine absence). `join.number_index_key`
    # itself is untouched: it keeps a space verbatim by design, so this is a lookup-only
    # fold ahead of it, proved red on a `.bak` copy of the real fixture before the fix.
    checks.equal(
        images.url_for("riftbound", "Vendetta", "SP3 / 006"),
        "https://tcgplayer-cdn.tcgplayer.com/product/705996_200w.jpg",
        "a raw number with spaces around the slash still resolves against a clean index",
    )

    # THE ROUTE THREADING: `do_pipeline_sets`/`do_pipeline_worklist` carry `image_url` only
    # when handed a resolver, and never open a socket when they are not (every OTHER T7
    # case that calls either function bare is this assertion's own regression guard).
    with isolated_home():
        with Store().write() as snapshot:
            inventory = snapshot.inventory
            inventory.ensure_box(1, name="stock-image box")
            card, _ = inventory.allocate_capture(1, cid=fake_cid("stock-image-1"))
            card.sku = "8925700"
            card.name = "Ahri, Inquisitive"
            card.number = "SP3/006"
            card.printed_total = "166"
            card.set_name = "Vendetta"
            card.game = "riftbound"
            card.state = master.IDENTIFIED

        bare = pipeline_routes.do_pipeline_sets()
        threaded = pipeline_routes.do_pipeline_sets(images=images)

    bare_row = bare["groups"][0]["cards"][0]
    threaded_row = threaded["groups"][0]["cards"][0]
    checks.equal(
        bare_row["image_url"], None, "no resolver handed in, `image_url` is None, no socket"
    )
    checks.equal(
        threaded_row["image_url"],
        "https://tcgplayer-cdn.tcgplayer.com/product/705996_200w.jpg",
        "a resolver handed in, and the warmed cache answers it, threaded onto the row",
    )

    # THE DISPLAY-NAME FIX, END TO END, THROUGH `do_pipeline_sets` ITSELF (the review round,
    # 2026-09-27): a colon-bearing store `set_name` — one that IS a code prefix, and one that
    # ISN'T — must come back through the route resolved the same way the image already is,
    # never a client-side regex the caller has to keep in step with this route.
    with isolated_home():
        with Store().write() as snapshot:
            inventory = snapshot.inventory
            inventory.ensure_box(1, name="display-name box")
            coded, _ = inventory.allocate_capture(1, cid=fake_cid("display-name-1"))
            coded.sku = "8930001"
            coded.name = "Charmander"
            coded.number = "1"
            coded.printed_total = "1"
            coded.set_name = "ME01: Mega Evolution"
            coded.game = "pokemon"
            coded.state = master.IDENTIFIED
            colon, _ = inventory.allocate_capture(1, cid=fake_cid("display-name-2"))
            colon.sku = "8930002"
            colon.name = "Pikachu"
            colon.number = "1"
            colon.printed_total = "1"
            colon.set_name = "Celebrations: Classic Collection"
            colon.game = "pokemon"
            colon.state = master.IDENTIFIED

        bare_names = pipeline_routes.do_pipeline_sets()
        named = pipeline_routes.do_pipeline_sets(images=images)

    checks.equal(
        sorted(g["set_name"] for g in bare_names["groups"]),
        ["Celebrations: Classic Collection", "ME01: Mega Evolution"],
        "no resolver handed in, the store's own set_name ships verbatim, prefix and all",
    )
    checks.equal(
        sorted(g["set_name"] for g in named["groups"]),
        ["Celebrations: Classic Collection", "Mega Evolution"],
        "A RESOLVER HANDED IN: the code prefix is gone from 'ME01: Mega Evolution', and "
        "'Celebrations: Classic Collection' — a REAL colon, not a code — is untouched. "
        "This is the exact regression a client-side blind strip committed: it would have "
        "answered 'Classic Collection' here, which this line goes red on without the fix.",
    )


def check_sales_stock_photo_fallback(checks: Checks) -> None:
    """F2, the owner's report: *"why does the sales page not pull the icons like you're
    able to do on sets and pricing?"* `#/revenue`'s `GET /skus/photos` gains a stock-photo
    fallback for a SKU with no own photographed copy on hand (D89 usually reclaimed it),
    off the SAME `StockImages` resolver Sets and Pricing already use — never a second
    resolver.

    THREE PARTS. `games.game_for_product_line` — the reverse lookup a Sales row's SKU needs,
    since it carries `product_line` text and no `game` key. `StockImages.url_for_product` —
    a SEALED product (no card number) resolving by name, Pokemon included, off the same
    cached tcgcsv group `url_for` already fetches. And `do_skus_photos` itself, end to end:
    the own photo wins, a single's SKU falls back through `url_for`, a sealed SKU falls
    back through `url_for_product`, and a genuine miss stays absent from both fields.
    """
    checks.note("")
    checks.note("SALES STOCK-PHOTO FALLBACK — game_for_product_line, url_for_product, GET /skus/photos (F2)")

    checks.equal(
        games.game_for_product_line("Pokemon"),
        "pokemon",
        "the real singles/sealed catalog wins over pokemon_code, which shares the same text",
    )
    checks.equal(
        games.game_for_product_line("One Piece Card Game"), "one_piece", "a clean match",
    )
    checks.equal(
        games.game_for_product_line("Nothing Registered Claims This"),
        None,
        "an unregistered product line is None, never a guess",
    )
    checks.equal(games.game_for_product_line(""), None, "a blank cell is None")

    def make_fetcher():
        def fetcher(url: str):
            if url.endswith("/categories"):
                return {"results": [
                    {"name": "Pokemon", "categoryId": 3},
                    {"name": "Riftbound League of Legends Trading Card Game", "categoryId": 89},
                ]}
            if url.endswith("/3/groups"):
                return {"results": [{"name": "Scarlet & Violet", "groupId": 501}]}
            if url.endswith("/3/501/products"):
                return {"results": [
                    {"imageUrl": "https://img/etb.jpg", "name": "Scarlet & Violet Elite Trainer Box", "productId": 900001},
                ]}
            if url.endswith("/89/groups"):
                return {"results": [{"name": "Vendetta", "groupId": 24698}]}
            if url.endswith("/89/24698/products"):
                return {"results": [
                    {
                        "imageUrl": "https://tcgplayer-cdn.tcgplayer.com/product/705996_200w.jpg",
                        "extendedData": [{"name": "Number", "value": "SP3/006"}],
                        "productId": 705996,
                    },
                    {"imageUrl": "https://img/rift-booster.jpg", "name": "Vendetta Booster Box", "productId": 900002},
                    # A NAME COLLISION (review round, 2026-09-27): two distinct products
                    # sharing one name in this same group. `url_for_product` must refuse
                    # rather than answer either one's photo.
                    {"imageUrl": "https://img/collide-a.jpg", "name": "Vendetta Booster Case", "productId": 900003},
                    {"imageUrl": "https://img/collide-b.jpg", "name": "Vendetta Booster Case", "productId": 900004},
                ]}
            raise AssertionError(f"unexpected fetch: {url}")
        return fetcher

    images = stockimages.StockImages(market=pricehistory.Market(cache_dir=None, fetcher=make_fetcher()))
    # `allow_pokemon=True`: THE ONE NAMED EXCEPTION `warm`'s own docstring argues for — see
    # `check_stock_images_pokemon_warm_refusal` below for the DEFAULT case (no exception),
    # which is finding 2's own proof.
    for pair in (("pokemon", "Scarlet & Violet"), ("riftbound", "Vendetta")):
        for thread in images.warm([pair], allow_pokemon=True):
            thread.join(timeout=5)

    checks.equal(
        images.url_for_product("Pokemon", "Scarlet & Violet", "Scarlet & Violet Elite Trainer Box"),
        "https://img/etb.jpg",
        "POKEMON SEALED resolves through tcgcsv — the vendored tree carries no sealed row "
        "at all, unlike a Pokemon CARD's own number",
    )
    checks.equal(
        images.url_for_product(
            "Riftbound League of Legends Trading Card Game", "Vendetta", "Vendetta Booster Box"
        ),
        "https://img/rift-booster.jpg",
        "a non-Pokemon sealed product resolves by name off the SAME cached group its "
        "singles already warmed",
    )
    checks.equal(
        images.url_for_product("Pokemon", "Scarlet & Violet", "No Such Product"),
        None,
        "a sealed-product NAME miss is None, never a guess",
    )
    checks.equal(
        images.url_for_product(
            "Riftbound League of Legends Trading Card Game", "Vendetta", "Vendetta Booster Case"
        ),
        None,
        "TWO PRODUCTS SHARING ONE NAME IN ONE GROUP answer None — never a guess at the "
        "first product a group happens to list (review round, 2026-09-27: a `setdefault` "
        "by-name dict answered the first one silently, breaking D301's own 'never a guess')",
    )

    with isolated_home():
        with Store().write() as snapshot:
            snapshot.inventory.ensure_box(1, name="skus-photos box")
            # A SOLD SKU the skus table no longer holds: only its order line names it.
            snapshot.ledger.ingest([
                order_store.OrderRecord(
                    source="TCGplayer",
                    number="GONE-1",
                    lines=[
                        order_store.OrderLine(
                            sku="gone-sku",
                            name="Pokemon - Scarlet & Violet: Scarlet & Violet Elite Trainer Box - Unopened",
                        )
                    ],
                )
            ])

        # OWN PHOTO WINS — a real on-hand, photographed card, over anything the SKU table
        # or the resolver could otherwise answer.
        capture_server.do_capture(capture_payload(1, capture_id="own-photo"))
        with Store().write() as snapshot:
            card = snapshot.inventory.get(master.position_key(1, 1))
            card.sku = "own-photo-sku"

        # A SINGLE with no own photo on hand at all — the SKU table's own `number` cell
        # routes through `url_for`, exactly as `#/pricing` and Sets already do.
        with Store().write() as snapshot:
            snapshot.skus.entries["single-sku"] = SkuRow(
                product_line="Riftbound League of Legends Trading Card Game",
                set_name="Vendetta",
                product_name="Ahri, Inquisitive",
                number="SP3/006",
                rarity="Rare",
                condition="Near Mint",
                grade=None,
                printing=None,
                first_seen=1_700_000_000,
                last_seen=1_700_000_000,
                source="t7-fixture",
                raw={},
            )
            # A SEALED SKU, no number at all — routes through `url_for_product` by name.
            snapshot.skus.entries["sealed-sku"] = SkuRow(
                product_line="Pokemon",
                set_name="Scarlet & Violet",
                product_name="Scarlet & Violet Elite Trainer Box",
                number="",
                rarity="",
                condition="",
                grade=None,
                printing=None,
                first_seen=1_700_000_000,
                last_seen=1_700_000_000,
                source="t7-fixture",
                raw={},
            )
            # A SKU no `skus` row and no on-hand copy names at all — a genuine miss.
            # (nothing to write — "miss-sku" is simply never seeded)
            # A SKU whose row exists but whose product line no game claims — also a miss.
            snapshot.skus.entries["unregistered-sku"] = SkuRow(
                product_line="Not A Real Product Line",
                set_name="Anywhere",
                product_name="Anything",
                number="1",
                rarity="",
                condition="",
                grade=None,
                printing=None,
                first_seen=1_700_000_000,
                last_seen=1_700_000_000,
                source="t7-fixture",
                raw={},
            )

        bare = answers(
            checks,
            lambda: capture_server.do_skus_photos(
                ["own-photo-sku", "single-sku", "sealed-sku", "miss-sku", "unregistered-sku"]
            ),
            "no resolver handed in, the route still answers",
        )
        if bare is not None:
            checks.equal(
                bare["stock_photos"], {},
                "no resolver, no stock photos — and no socket, the route's own bare posture",
            )
            checks.ok(
                "own-photo-sku" in bare["photos"],
                "the own photo still answers with no resolver at all",
            )

        threaded = answers(
            checks,
            lambda: capture_server.do_skus_photos(
                ["own-photo-sku", "single-sku", "sealed-sku", "miss-sku", "unregistered-sku"],
                images=images,
            ),
            "a resolver handed in, the route answers",
        )
        if threaded is not None:
            checks.ok(
                "own-photo-sku" in threaded["photos"] and "own-photo-sku" not in threaded["stock_photos"],
                "OWN PHOTO WINS — it never falls through to the resolver even though one "
                "is handed in",
            )
            checks.equal(
                threaded["stock_photos"].get("single-sku"),
                "https://tcgplayer-cdn.tcgplayer.com/product/705996_200w.jpg",
                "a SINGLE with no own photo falls back through url_for, by number",
            )
            checks.equal(
                threaded["stock_photos"].get("sealed-sku"),
                "https://img/etb.jpg",
                "a SEALED SKU (no number) falls back through url_for_product, by name — "
                "Pokemon included",
            )
            checks.equal(
                answers(
                    checks,
                    lambda: capture_server.do_skus_photos(["gone-sku"], images=images),
                    "a sold SKU with no skus row",
                )["stock_photos"].get("gone-sku"),
                "https://img/etb.jpg",
                "A SOLD SKU THE skus TABLE NO LONGER HOLDS resolves off its order line's name",
            )
            checks.equal(
                images.url_for_line_name(
                    "Pokemon - Scarlet & Violet: Scarlet & Violet Elite Trainer Box - Pokemon Center Exclusive"
                ),
                None,
                "a longer line name is a different variant: no shorter product's photo",
            )
            checks.ok(
                "miss-sku" not in threaded["photos"] and "miss-sku" not in threaded["stock_photos"],
                "a SKU with no on-hand copy and no skus-table row is absent from both "
                "fields, never a guess",
            )
            checks.ok(
                "unregistered-sku" not in threaded["photos"]
                and "unregistered-sku" not in threaded["stock_photos"],
                "a SKU whose product line no game claims is absent from both fields too",
            )


def check_stock_images_pokemon_warm_refusal(checks: Checks) -> None:
    """Finding 2, review round 2026-09-27: `warm_stock_images`'s startup pairs are every
    distinct `(game, set_name)` among IDENTIFIED CARDS, Pokemon singles included — `url_for`
    never reads this cache for a Pokemon CARD (it answers off the vendored tree instead), so
    warming it at startup was a real tcgcsv fetch, per Pokemon set the store holds, for
    nothing, on every restart. `warm()` refuses a Pokemon pair BY DEFAULT, restored here;
    only `_tcgcsv_name_lookup`'s own sealed-product lookup may ask for one, by naming
    `allow_pokemon=True` explicitly — this compares the two calls directly, which is the
    real mechanism `warm_stock_images` and `_tcgcsv_name_lookup` each choose between.
    """
    checks.note("")
    checks.note("POKEMON STARTUP WARM REFUSAL — warm(), allow_pokemon (F2, finding 2, review round 2026-09-27)")

    calls: List[str] = []

    def counting_fetcher(url: str):
        calls.append(url)
        if url.endswith("/categories"):
            return {"results": [{"name": "Pokemon", "categoryId": 3}]}
        if url.endswith("/3/groups"):
            return {"results": [
                {"name": "Scarlet & Violet", "groupId": 1},
                {"name": "Paldea Evolved", "groupId": 2},
                {"name": "Obsidian Flames", "groupId": 3},
            ]}
        if url.endswith("/3/1/products") or url.endswith("/3/2/products") or url.endswith("/3/3/products"):
            return {"results": []}
        raise AssertionError(f"unexpected fetch: {url}")

    # THREE DISTINCT POKEMON SETS — the shape `warm_stock_images` would build from a store
    # that has identified Pokemon cards across three sets, the case the review round asked
    # to be shown.
    pairs = [
        ("pokemon", "Scarlet & Violet"),
        ("pokemon", "Paldea Evolved"),
        ("pokemon", "Obsidian Flames"),
    ]
    images = stockimages.StockImages(market=pricehistory.Market(cache_dir=None, fetcher=counting_fetcher))

    # AFTER (the shipped default, no caller names an exception) — `warm_stock_images` calls
    # exactly this, unchanged by F2.
    default_threads = images.warm(pairs)
    for thread in default_threads:
        thread.join(timeout=5)
    checks.equal(
        len(default_threads), 0,
        "warm() schedules NOTHING for a Pokemon pair by default — 0 of 3 threads started",
    )
    checks.equal(
        len(calls), 0,
        f"and NO REQUEST reaches tcgcsv at all — measured {len(calls)} requests at startup, "
        "against 5 before this fix, below (the bug: every restart fetched every Pokemon "
        "set for a lookup url_for never makes)",
    )

    # BEFORE (what the bug did, and the one path that is STILL SUPPOSED to reach here — a
    # Pokemon SEALED lookup, `_tcgcsv_name_lookup`'s own named exception).
    forced_threads = images.warm(pairs, allow_pokemon=True)
    checks.equal(
        len(forced_threads), 3,
        "allow_pokemon=True is the one named exception, and schedules every pair asked",
    )
    for thread in forced_threads:
        thread.join(timeout=5)
    checks.equal(
        len(calls), 5,
        f"and THIS is what the bug did at every restart, unconditionally: measured "
        f"{len(calls)} real tcgcsv requests for 3 Pokemon sets (1 categories + 1 groups, "
        "both shared and cached after the first pair, + 1 products call per set) — 0 with "
        "the refusal restored, against 5 on a cold process before it was",
    )


def check_skus_photos_pending(checks: Checks) -> None:
    """a SKU whose catalogue group is still being fetched answers `pending`, apart
    from a final "no such image". The same ask, once the group has landed, answers the URL."""
    import threading

    checks.note("")
    checks.note("SKUS PHOTOS PENDING — a cold group answers pending, then a URL")
    gate = threading.Event()

    def slow_fetcher(url: str):
        if url.endswith("/categories"):
            return {"results": [{"name": "Pokemon", "categoryId": 3}]}
        if url.endswith("/3/groups"):
            return {"results": [{"name": "Scarlet & Violet", "groupId": 501}]}
        if url.endswith("/3/501/products"):
            gate.wait(timeout=10)
            return {"results": [
                {"imageUrl": "https://img/etb.jpg", "name": "Scarlet & Violet Elite Trainer Box", "productId": 900001},
            ]}
        raise AssertionError(f"unexpected fetch: {url}")

    images = stockimages.StockImages(market=pricehistory.Market(cache_dir=None, fetcher=slow_fetcher))
    with isolated_home():
        with Store().write() as snapshot:
            snapshot.skus.entries["sealed-sku"] = SkuRow(
                product_line="Pokemon", set_name="Scarlet & Violet",
                product_name="Scarlet & Violet Elite Trainer Box", number="", rarity="",
                condition="", grade=None, printing=None, first_seen=1_700_000_000,
                last_seen=1_700_000_000, source="t7-fixture", raw={},
            )
        cold = capture_server.do_skus_photos(["sealed-sku"], images=images)
        checks.equal(cold["pending"], ["sealed-sku"], "a cold group answers pending")
        checks.equal(cold["stock_photos"], {}, "and no URL yet")
        gate.set()
        for _ in range(100):
            if not images.group_pending("pokemon", "Scarlet & Violet"):
                break
            time.sleep(0.05)
        warm = capture_server.do_skus_photos(["sealed-sku"], images=images)
        checks.equal(warm["pending"], [], "a landed group is not pending")
        checks.equal(warm["stock_photos"].get("sealed-sku"), "https://img/etb.jpg", "and answers the URL")



# STOCK MIX, `GET /stock/mix` (docs/specs/sales-screen.md, Mix, checks 1 to 7). One home, `pipeline/stockmix.py`.
# BUILDER CONTRACT, wire names read here: top level `asOf`, `cards`; per card `game set rarity finish state box
# capturedWeek soldWeek sku price soldRecent`; `state` is `Sold`, `On hand` or `Not listed yet`; `price` is the
# SKU's market reading (number or numeric string, null if none); `soldRecent` is 1 under 14 days after `state_at`.
# Each check goes red on a server with no such route, by a failed status assertion first.

MIX_ROUTE = "/stock/mix"
MIX_CARD_KEYS = {
    "game", "set", "rarity", "finish", "state", "box", "capturedWeek", "soldWeek", "sku", "price", "soldRecent",
}


def _mix_sku(set_name="Origins", rarity="Rare") -> SkuRow:
    return SkuRow(
        product_line="Riftbound League of Legends Trading Card Game", set_name=set_name,
        product_name="Ahri", number="001", rarity=rarity, condition="Near Mint", grade=None,
        printing=None, first_seen=1_700_000_000, last_seen=1_700_000_000, source="t7-fixture", raw={},
    )


def _mix_iso(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) - delta).isoformat()


def _mix_fixture() -> None:
    """Five cards that count (listed on hand, two sold at 13 and 14 days, two unlisted) and two
    that never do (retired, moved). An order for S1 at a price far from its reading sits beside
    them, so a server that sums orders into the wire shows it."""
    with Store().write() as snapshot:
        inv = snapshot.inventory
        inv.ensure_box(1, name="Alpha")
        snapshot.skus.entries["S1"] = _mix_sku()
        snapshot.readings.entries["S1"] = Reading(market="2.50", at=1_700_000_000, source="t7", kind="run")

        def put(seed, **fields):
            card, _ = inv.allocate_capture(1, cid=fake_cid(f"mix-{seed}"))
            card.game = "riftbound"
            card.captured_at = "2026-09-16T12:00:00+00:00"
            for name, value in fields.items():
                setattr(card, name, value)
            return card

        put("hand", sku="S1", state=master.IDENTIFIED)
        put("sold13", sku="S1", state=master.SOLD, state_at=_mix_iso(timedelta(days=13)))
        put("sold14", sku="S1", state=master.SOLD, state_at=_mix_iso(timedelta(days=14)))
        put("claim", sku=None, state=master.CAPTURED, rarity_claim=["Rare", "Epic"], set_hint="Origins")
        put("noclaim", sku=None, state=master.CAPTURED, rarity_claim=[], metadata_finish=None)
        put("retired", sku="S1", state=master.RETIRED)
        put("moved", sku="S1", state=master.MOVED)
        snapshot.ledger.ingest([
            order_store.OrderRecord(
                source="TCGplayer", number="O-1", placed_at=_mix_iso(timedelta(days=2)),
                lines=[order_store.OrderLine(sku="S1", quantity=1, unit_price="9.99")],
            )
        ])


def _mix_get():
    """`(status, payload or None)` for one read of the route over a real in-process server."""
    httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
    thread = _spawn_server(httpd)
    try:
        status, body, _ = request(
            httpd.server_address[1], "GET", MIX_ROUTE, origin=capture_server.DEFAULT_ALLOWED_ORIGINS[0]
        )
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
    try:
        return status, json.loads(body)
    except (ValueError, TypeError):
        return status, None


def _mix_payload(checks: Checks):
    """The wire payload over the fixture, or `None` after a failed status or shape check."""
    with isolated_home():
        _mix_fixture()
        status, payload = _mix_get()
    if not checks.equal(status, 200, f"GET {MIX_ROUTE} answers 200"):
        return None
    if not checks.ok(isinstance(payload, dict) and isinstance(payload.get("cards"), list), "payload is {asOf, cards: [...]}"):
        return None
    return payload


def check_mix_leaves_out_retired_and_moved(checks: Checks) -> None:
    checks.note("")
    checks.note("STOCK MIX 1 — retired and moved cards are not on the wire")
    payload = _mix_payload(checks)
    if payload is None:
        return
    cards = payload["cards"]
    checks.equal(len(cards), 5, "five of seven cards count: retired and moved are left out")
    checks.equal(
        sorted(card["state"] for card in cards),
        ["Not listed yet", "Not listed yet", "On hand", "Sold", "Sold"],
        "states: one on hand, two sold, two not listed yet",
    )


def check_mix_wire_has_no_revenue_and_price_is_the_reading(checks: Checks) -> None:
    checks.note("")
    checks.note("STOCK MIX 2 — no revenue on the wire, a sold card's price is its market reading")
    payload = _mix_payload(checks)
    if payload is None:
        return
    checks.ok("revenue" not in payload, "no top-level revenue key")
    checks.ok(all("revenue" not in card for card in payload["cards"]), "no per-card revenue key")
    sold = [card for card in payload["cards"] if card.get("state") == "Sold"]
    checks.equal(len(sold), 2, "two sold cards")
    checks.ok(
        bool(sold) and all(card["price"] is not None and abs(float(card["price"]) - 2.5) < 1e-9 for card in sold),
        "a sold card's price is the 2.50 reading, never the 9.99 an order paid",
    )


def check_mix_unlisted_card_reads_its_claim(checks: Checks) -> None:
    checks.note("")
    checks.note("STOCK MIX 3 — an unlisted card counts by its claimed rarity")
    payload = _mix_payload(checks)
    if payload is None:
        return
    unlisted = [card for card in payload["cards"] if card["sku"] is None]
    checks.equal(
        sorted(card["rarity"] for card in unlisted), ["No claim", "Rare or Epic"],
        "claim joined with ' or ', an empty claim is 'No claim'",
    )
    claimed = [card for card in unlisted if card["rarity"] == "Rare or Epic"]
    checks.ok(bool(claimed) and claimed[0]["set"] == "Origins", "its set is the set hint")
    blank = [card for card in unlisted if card["rarity"] == "No claim"]
    checks.ok(bool(blank) and blank[0]["finish"] == "Unknown", "no metadata_finish reads 'Unknown'")


def check_mix_state_labels(checks: Checks) -> None:
    checks.note("")
    checks.note("STOCK MIX 4 — no SKU is 'Not listed yet', sold is 'Sold', the rest 'On hand'")
    payload = _mix_payload(checks)
    if payload is None:
        return
    cards = payload["cards"]
    unsold = [card for card in cards if card["state"] != "Sold"]
    checks.equal(sum(card["state"] == "Sold" for card in cards), 2, "state sold reads Sold")
    checks.ok(
        bool(unsold) and all((card["state"] == "Not listed yet") == (card["sku"] is None) for card in unsold),
        "a card with no SKU is Not listed yet",
    )
    checks.ok(
        any(card["state"] == "On hand" and card["sku"] == "S1" for card in cards),
        "a listed unsold card is On hand",
    )


def check_mix_sold_recent_edge(checks: Checks) -> None:
    checks.note("")
    checks.note("STOCK MIX 5 — soldRecent is 1 at 13 days and 0 at 14 days")
    payload = _mix_payload(checks)
    if payload is None:
        return
    cards = payload["cards"]
    checks.equal(
        sorted(card["soldRecent"] for card in cards if card["state"] == "Sold"), [0, 1],
        "13 days is recent, 14 is not",
    )
    checks.ok(all(card["soldRecent"] == 0 for card in cards if card["state"] != "Sold"), "a card that did not sell is never recent")


def check_mix_wire_allowlist(checks: Checks) -> None:
    checks.note("")
    checks.note("STOCK MIX 7 — no photograph or buyer field, only the allowed keys")
    payload = _mix_payload(checks)
    if payload is None:
        return
    checks.equal(set(payload), {"asOf", "cards"}, "top level is asOf and cards")
    extra = {key for card in payload["cards"] for key in set(card) - MIX_CARD_KEYS}
    checks.ok(not extra, "every card key is on the allowlist", f"extra: {sorted(extra)}")
    checks.ok(all(set(card) == MIX_CARD_KEYS for card in payload["cards"]), "every card carries all eleven keys")


def check_budget_row(checks: Checks) -> None:
    checks.note("")
    checks.note("STOCK MIX 6 — the read budget has a row, and its sql is constant at S and 2S")
    from harness.tests.t7 import read_budget

    checks.ok(MIX_ROUTE in read_budget.get_routes(), "do_GET serves '/stock/mix', so its budget row is measured")
    row = read_budget.BUDGET.get(MIX_ROUTE)
    checks.ok(row is not None, "BUDGET has a '/stock/mix' row")
    checks.ok(MIX_ROUTE in read_budget.ROUTE_URLS, "ROUTE_URLS names '/stock/mix'")
    if row is not None:
        checks.equal(row.get("status"), 200, "the row's fixture hits the 200 path")
        checks.equal(row.get("store_read"), 1, "one store read")
    checks.ok((MIX_ROUTE, "sql") not in read_budget.KNOWN_OVER, "sql is equal at S and 2S: no KNOWN_OVER entry")


def check_mix_listed_card_with_no_rarity_reads_unread(checks: Checks) -> None:
    checks.note("")
    checks.note("STOCK MIX 3b — a listed card whose SKU has no rarity or set reads Unread / No set yet, never its claim")
    with isolated_home():
        with Store().write() as snapshot:
            inv = snapshot.inventory
            inv.ensure_box(1, name="Alpha")
            snapshot.skus.entries["S9"] = _mix_sku(set_name="", rarity="")
            card, _ = inv.allocate_capture(1, cid=fake_cid("mix-unread"))
            card.game, card.sku, card.state = "riftbound", "S9", master.IDENTIFIED
            card.rarity_claim, card.set_hint = ["Epic"], "Origins"
        status, payload = _mix_get()
    if not checks.equal(status, 200, f"GET {MIX_ROUTE} answers 200") or not isinstance(payload, dict):
        return
    cards = payload.get("cards", [])
    checks.equal([c.get("rarity") for c in cards], ["Unread"], "a listed card with no SKU rarity reads Unread, not its claim")
    checks.equal([c.get("set") for c in cards], ["No set yet"], "a listed card with no SKU set reads No set yet, not its hint")


def check_inventory_copies_stock_image(checks: Checks) -> None:
    """`POST /inventory/copies` carries `image_url` on each card (D301), for the Orders walk's
    strip of thumbnails (`OrdersWalkPane.tsx:WalkStrip`): a hit is the resolver's hotlinked
    URL, a join miss is `None`, and a call with no resolver is `None` with no socket opened.

    THE RESOLVER IS THE ONE `StockImages`, handed in as `images=` exactly as
    `do_pipeline_sets` and `do_skus_photos` take it (`server/pipeline_routes.py:STOCK_IMAGES`
    at the HTTP dispatch). Its tcgcsv fetcher is stubbed and the cache is warmed and joined,
    so the answer is deterministic. A fetcher that raises on any other URL is the proof that
    no socket is reached: the bare call never constructs one, and a miss reads the cache only.
    """
    checks.note("")
    checks.note("INVENTORY COPIES — image_url on each card, hit, miss and bare (D301)")

    URL = "https://tcgplayer-cdn.tcgplayer.com/product/705996_200w.jpg"

    def fetcher(url: str):
        if url.endswith("/categories"):
            return {"results": [
                {"name": "Riftbound League of Legends Trading Card Game", "categoryId": 89},
            ]}
        if url.endswith("/89/groups"):
            return {"results": [{"name": "Vendetta", "groupId": 24698}]}
        if url.endswith("/89/24698/products"):
            return {"results": [{
                "imageUrl": URL,
                "extendedData": [{"name": "Number", "value": "SP3/006"}],
            }]}
        raise AssertionError(f"unexpected fetch: {url}")

    images = stockimages.StockImages(market=pricehistory.Market(cache_dir=None, fetcher=fetcher))
    for thread in images.warm([("riftbound", "Vendetta")]):
        thread.join(timeout=5)

    with isolated_home():
        with Store().write() as snapshot:
            inventory = snapshot.inventory
            inventory.ensure_box(1, name="walk thumbs box")
            for tag, sku, name, number in (
                ("hit", "8925700", "Ahri, Inquisitive", "SP3/006"),
                ("miss", "8925701", "Not In The Catalog", "SP3/999"),
            ):
                card, _ = inventory.allocate_capture(1, cid=fake_cid(f"copies-stock-{tag}"))
                card.sku = sku
                card.name = name
                card.number = number
                card.printed_total = "166"
                card.set_name = "Vendetta"
                card.game = "riftbound"
                card.state = master.IDENTIFIED

        wanted = {"skus": ["8925700", "8925701"]}
        threaded = answers(
            checks,
            lambda: capture_server.do_inventory_copies(wanted, images=images),
            "a resolver handed in, the route answers",
        )
        bare = answers(
            checks,
            lambda: capture_server.do_inventory_copies(wanted),
            "no resolver handed in, the route still answers",
        )

    if threaded is not None:
        by_sku = {card["sku"]: card for card in threaded["cards"].values()}
        checks.equal(
            by_sku["8925700"].get("image_url", "<absent>"),
            URL,
            "a card the resolver knows carries its hotlinked URL on `image_url`",
        )
        checks.equal(
            by_sku["8925701"].get("image_url", "<absent>"),
            None,
            "a JOIN MISS is None, never a guess and never an absent key",
        )
    if bare is not None:
        checks.equal(
            sorted(card.get("image_url", "<absent>") for card in bare["cards"].values() if card["sku"] == "8925700"),
            [None],
            "no resolver handed in, `image_url` is None on every card and no socket is opened",
        )


CHECKS = (
    check_pipeline_sets,
    check_stock_images,
    check_inventory_copies_stock_image,
    check_sales_stock_photo_fallback,
    check_stock_images_pokemon_warm_refusal,
    check_skus_photos_pending,
    check_mix_leaves_out_retired_and_moved,
    check_mix_wire_has_no_revenue_and_price_is_the_reading,
    check_mix_unlisted_card_reads_its_claim,
    check_mix_listed_card_with_no_rarity_reads_unread,
    check_mix_state_labels,
    check_mix_sold_recent_edge,
    check_mix_wire_allowlist,
    check_budget_row,
)
