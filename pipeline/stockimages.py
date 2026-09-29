"""Stock card images: `(game, set_name, number)` -> a hotlinked photo URL, or `None`.

`docs/specs/stock-images.md` is the spec — read it first. This module is a thin resolver,
never a mirror (the owner's own call): it answers with a URL on someone else's CDN and never
downloads or stores the bytes. A join miss answers `None`, never a guess (`CLAUDE.md`'s hard
rule against guessing an identification, applied here to a photo instead of a name).

TWO SOURCES, ONE PER PRODUCT LINE. Riftbound and One Piece go through `tcgcsv.com`, reusing
`pipeline/pricehistory.py:Market` for the categories/groups/products walk that module already
built and caches — a second HTTP client here would be the workaround `CLAUDE.md` says to
check for a primitive before writing. Pokemon goes through the vendored
`vendor/pokemon-tcg-data/` tree (D15) instead of `api.pokemontcg.io`, and that is a deliberate
departure from this feature's own research notes, not an oversight: the research found the
live API at 100% coverage for one set; a live check made while building this (2026-09-26)
found it answering HTTP 500/502 on every query, including the exact one the research recorded
working. The vendored snapshot carries the SAME `images.pokemontcg.io` CDN URLs, verbatim,
committed and refreshed on demand by `make catalog-refresh` — no network call, no flakiness,
and nothing to stub in a test. DEBT44 records the live API as the future path once the
vendored tree lags a new set, and why this module does not depend on it today.

SEVERAL SKUS SHARE ONE URL, ON PURPOSE (the owner's own addition, mid-build): a foil and a
normal printing of one card are the same physical product to both catalogs, so both resolve to
the same image. This module never dedupes a caller's rows over that — it only ever answers the
question it is asked, one `(game, set_name, number)` at a time.

CACHED PER GROUP OR SET, NEVER PER CARD: one fetch (tcgcsv) or one file read (Pokemon) answers
every card in it, so a screen asking about the second card of a set already open costs nothing
more.

THE TCGCSV WALK NEVER RUNS ON A REQUEST THREAD (the review, 2026-09-26, measured: a cold
`/pipeline/sets` costs ~2s, and four cold requests filled every `REQUEST_SLOTS` and made an
unrelated fifth wait 1.8s). `url_for` for Riftbound/One Piece reads `_cache` ONLY. A miss or a
stale entry schedules `_warm_one` on a background thread (`warm`, below) and answers with
whatever is cached right now — `None` on a cold key, the last-known URL on a stale one — never
blocking for the fetch. `warm` is the one scheduling primitive: `server/capture_server.py`
calls it once at server start with every `(game, set_name)` pair the store holds, and
`_tcgcsv_lookup` calls it again, inertly, on every read past the key's own TTL — the SAME
mechanism serves the start-up prime and the periodic refresh, so there is no second, polling
thread to keep in step with it. `warm` REFUSES A POKEMON PAIR BY DEFAULT, and that default
still matters: a Pokemon CARD's number reads local disk in well under a millisecond and was
never the slow one this exists for, so warming it at startup would be a real fetch for
nothing (measured, 2026-09-27 review: 5 wasted requests for 3 Pokemon sets on this
checkout's own test fixture — 1 categories, 1 groups, 3 products — against 0 with the
refusal restored). A Pokemon SEALED PRODUCT (F2, below) is a different question the
vendored tree cannot answer at all, and reaches this cache too — but only reactively,
through `_tcgcsv_name_lookup`'s own named exception, never at startup.

SEALED PRODUCT (F2, 2026-09-27): a Sales row can carry no card number at all — a booster box,
an ETB. `url_for_product` answers that question by PRODUCT NAME instead of number, off the
SAME cached tcgcsv group `url_for` already fetched (`_ImageIndex.by_name`, built in the same
walk as `by_number`), and it takes `product_line` text directly rather than a `game` key —
`games.game_for_product_line` is the one join the caller (`do_skus_photos`, which reads a
`SkuRow` and has no `game` field) needs to reach it.
"""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Dict, Iterable, List, NamedTuple, Optional, Set, Tuple

from pipeline import games as game_registry
from pipeline import join
from pipeline.pricehistory import (
    CATALOG_HOST,
    EXTENDED_NUMBER,
    PriceHistoryError,
    Market,
    ProductIndex,
    extended,
)

# A SHORT TTL, NEVER `pricehistory.CATALOG_TTL_SECONDS` (which is infinite): that constant is
# right for the archive sweep's own products list, which barely moves. This resolver's whole
# reason to exist is fresh art on a screen the owner is looking at right now, so it asks
# tcgcsv again well within one sitting rather than trusting a fetch from days ago forever.
TCGCSV_TTL_SECONDS = 3600.0

VENDOR_ROOT = Path(__file__).resolve().parent.parent / "vendor" / "pokemon-tcg-data"

POKEMON_KEY = "pokemon"

# A STORE'S OWN `set_name` OFTEN CARRIES A COMMUNITY CODE THE VENDORED TREE DOES NOT
# (measured on a real-store copy, the review round: "ME01: Mega Evolution" against the
# vendored set's plain "Mega Evolution", 0 of 542 Pokemon rows resolving before this).
# `pipeline/join.py:normalize_set` is NOT touched for this — that fold drives the pricing
# join (D25) and D22's own taxonomies, and this resolver is neither. The prefix is stripped
# here, once, and only as a SECOND try after the unstripped name has already missed, so a
# set genuinely named "SM - Celestial Storm" (a real hyphen, not a code colon) still matches
# on its first try.
_CODE_PREFIX = re.compile(r"^[^:]+:\s*")

# A RAW ON-HAND NUMBER SOMETIMES CARRIES SPACES AROUND THE SLASH ("019 / 166"). This used to
# need a lookup-only fold ahead of `join.number_index_key`, because that function used to keep
# whitespace verbatim. The owner's ruling 2026-09-27 ("Fold in the shared key") moved the fold
# into `number_index_key` itself, which now strips ALL whitespace in the cell — a superset of
# the slash-only fold this module used to do. Call it directly.


class _PokemonImages:
    """`set_name` -> `number` -> image URL, off the vendored pokemon-tcg-data tree (D15).

    NO NETWORK, EVER. `vendor/pokemon-tcg-data/sets/en.json` and `cards/en/<id>.json` are
    committed files, and both already carry the exact CDN URLs `api.pokemontcg.io` answers
    with — this class only ever reads disk. Cached by the file's own mtime, so a
    `make catalog-refresh` while the server is up is picked up on the next request rather
    than needing a restart, and nothing here needs a TTL to go stale by.
    """

    def __init__(self, root: Path = VENDOR_ROOT) -> None:
        self._root = root
        self._set_ids: Optional[Dict[str, str]] = None
        # `id -> the catalogue's own name`, loaded in the same pass as `_set_ids` — the
        # reverse of that mapping, so `display_name` answers the vendored tree's OWN
        # string rather than re-deriving one from whatever the store happened to send.
        self._names_by_id: Dict[str, str] = {}
        self._numbers: Dict[str, Dict[str, str]] = {}
        self._numbers_mtime: Dict[str, float] = {}

    def _set_ids_by_name(self) -> Dict[str, str]:
        if self._set_ids is None:
            path = self._root / "sets" / "en.json"
            try:
                rows = json.loads(path.read_text("utf-8"))
            except (OSError, ValueError):
                rows = []
            ids: Dict[str, str] = {}
            names: Dict[str, str] = {}
            for row in rows:
                if not row.get("id") or not row.get("name"):
                    continue
                set_id = str(row["id"])
                ids[join.normalize_set(str(row["name"]))] = set_id
                names[set_id] = str(row["name"])
            self._set_ids = ids
            self._names_by_id = names
        return self._set_ids

    def _numbers_for(self, set_id: str) -> Dict[str, str]:
        path = self._root / "cards" / "en" / f"{set_id}.json"
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return {}
        if self._numbers_mtime.get(set_id) != mtime:
            try:
                rows = json.loads(path.read_text("utf-8"))
            except (OSError, ValueError):
                rows = []
            index: Dict[str, str] = {}
            for row in rows:
                url = (row.get("images") or {}).get("small")
                number = row.get("number")
                if url and number:
                    index.setdefault(join.number_index_key(number), str(url))
            self._numbers[set_id] = index
            self._numbers_mtime[set_id] = mtime
        return self._numbers.get(set_id, {})

    def _set_id_for(self, set_name: str) -> Optional[str]:
        ids = self._set_ids_by_name()
        set_id = ids.get(join.normalize_set(set_name))
        if set_id is not None:
            return set_id
        stripped = _CODE_PREFIX.sub("", set_name, count=1)
        if stripped == set_name:
            return None
        return ids.get(join.normalize_set(stripped))

    def url_for(self, set_name: str, number: str) -> Optional[str]:
        set_id = self._set_id_for(set_name)
        if set_id is None:
            return None
        return self._numbers_for(set_id).get(join.number_index_key(number))

    def display_name(self, set_name: str) -> Optional[str]:
        """The vendored tree's OWN name for `set_name`, resolved the SAME two-try order
        `_set_id_for` already uses for the photo: the unstripped name first, and the
        community code prefix stripped only when the unstripped name has already missed.

        THIS IS WHY A BLIND STRIP IS WRONG, AND WHY THIS METHOD EXISTS (the review round,
        2026-09-27): a store's own `set_name` is sometimes a real name that HAPPENS to
        carry a colon — "Celebrations: Classic Collection" is a real Pokemon set — and a
        client that stripped `^[^:]+:\\s*` unconditionally turned it into "Classic
        Collection". Trying the unstripped name against the catalogue FIRST, exactly as
        the image join does, means a colon that is not a code prefix never gets touched;
        the stripped form is only ever consulted once the direct name has already missed.

        `None` on a join miss — the caller keeps the store's own name, never a guess."""
        set_id = self._set_id_for(set_name)
        if set_id is None:
            return None
        self._set_ids_by_name()  # ensures `_names_by_id` is loaded
        return self._names_by_id.get(set_id)


class _ImageIndex(NamedTuple):
    """One tcgcsv group's products, indexed for a photo lookup two ways.

    `by_number` is a single card's key, as `_fetch_tcgcsv` always built — `setdefault`,
    first-product-wins, same posture as before. `products`/`urls_by_product_id` are F2's own
    addition (the owner: *"why does the sales page not pull the icons"*), for a SEALED
    product — a booster box, an ETB — which carries no card number at all.

    A NAME LOOKUP REUSES `pricehistory.ProductIndex.find` RATHER THAN A SECOND AMBIGUITY
    RULE (review round, 2026-09-27): a first build kept a `by_name: Dict[str, str]` here,
    `setdefault`, first-wins — the SAME shape `by_number` uses. That is wrong for a name:
    `ProductIndex.build`/`.find` already answer `None` when more than one product in a group
    shares a name (D35's shape, the blank-`Number` rung), and a `setdefault` copy of that
    same ambiguity silently answered the FIRST product's photo instead of refusing — D301's
    own rule, "a miss answers `None`, never a guess", broken by a second, worse copy of logic
    that already existed. `products` is built straight off the SAME payload `by_number`
    reads; `urls_by_product_id` is the only new index — a `productId`, unambiguous by
    definition, is never the thing two products can collide on, so it needs no ambiguity
    rule of its own. `_tcgcsv_name_lookup` composes the two: `products.find("", name)` for
    the id, this dict for the URL.
    """

    by_number: Dict[str, str]
    products: ProductIndex
    urls_by_product_id: Dict[int, str]


class StockImages:
    """One server process's resolver, ONE INSTANCE FOR THE PROCESS'S LIFE.

    A caller that constructs a fresh one per request gets no caching at all — `market`
    defaults to `cache_dir=None` (in-memory only), which is exactly the cache this class's
    OWN instance is for. `server/pipeline_routes.py:STOCK_IMAGES` is that one instance; a
    harness test that calls a route function directly passes no resolver at all (the
    functions default to `None` and answer every `image_url` as `None`), so no test opens a
    socket.
    """

    def __init__(
        self,
        market: Optional[Market] = None,
        pokemon: Optional[_PokemonImages] = None,
        ttl: float = TCGCSV_TTL_SECONDS,
    ) -> None:
        self._market = market if market is not None else Market(cache_dir=None)
        self._pokemon = pokemon if pokemon is not None else _PokemonImages()
        self._ttl = ttl
        # `(game, set_name) -> (fetched_at, _ImageIndex)`. Keyed on the
        # STORE's own pair rather than on `(categoryId, groupId)`: resolving those two hops
        # is itself part of the slow walk, so a cache keyed past them would still make the
        # request thread do that part synchronously. `_lock` guards this dict and `_pending`
        # together — both are read and written from request threads AND from the background
        # workers `warm` starts.
        self._cache: Dict[Tuple[str, str], Tuple[float, _ImageIndex]] = {}
        self._pending: Set[Tuple[str, str]] = set()
        self._lock = threading.Lock()
        # `Market` (`pipeline/pricehistory.py`) documents no thread safety of its own —
        # `_memory` and `_indexes` are plain dicts. `warm()` starts one daemon thread PER
        # `(game, set_name)` pair, all sharing this one `_market`, so two pairs warmed at
        # once could corrupt each other's read of it (a `RuntimeError` from a dict mutated
        # mid-iteration, uncaught by the `except` below because it is neither
        # `PriceHistoryError` nor `KeyError`) — found by `D301`'s own build:
        # every pair warmed at once left EVERY entry `None` forever, because a `_warm_one`
        # that raises never reaches its own `finally`-shaped cleanup and the pair stays
        # `_pending` (never retried). Background work only, never the request thread `warm`
        # itself never blocks — serializing it here costs nothing `url_for` can feel.
        self._market_lock = threading.Lock()

    def _fetch_tcgcsv(self, game: str, set_name: str) -> _ImageIndex:
        """The blocking walk: category, group, products. Called ONLY from a background
        thread (`_warm_one`) — never from `url_for`, `url_for_product`, `_tcgcsv_lookup` or
        `_tcgcsv_name_lookup`, which is the whole point of this split.
        """
        try:
            with self._market_lock:
                product_line = str(game_registry.get(game)["product_line"])
                category_id = self._market.category_id(product_line)
                group_id = self._market.group_id(category_id, set_name)
                # SAME SLUG `pipeline/pricehistory.py:Market.products` ALREADY USES for
                # this exact URL (D301) — the archive sweep's own disk
                # cache (`cli/cmd_pricearchive.py`) already answers this on the owner's
                # Mac, so this reads that primitive rather than warming a second, private
                # copy of it.
                payload = self._market.get(
                    f"{CATALOG_HOST}/tcgplayer/{category_id}/{group_id}/products",
                    f"tcgcsv/{category_id}/{group_id}/products",
                    self._ttl,
                )
        except (PriceHistoryError, KeyError):
            return _ImageIndex(
                by_number={}, products=ProductIndex(by_number={}, by_name={}), urls_by_product_id={}
            )
        results = payload.get("results") or ()
        by_number: Dict[str, str] = {}
        urls_by_product_id: Dict[int, str] = {}
        for product in results:
            url = product.get("imageUrl")
            if not url:
                continue
            number = extended(product, EXTENDED_NUMBER)
            if number:
                # `setdefault`: the first product a group lists for a number wins. A SECOND
                # product sharing a number would be two physical cards this resolver cannot
                # tell apart from a `(set, number)` pair alone — the same ambiguity
                # `ProductIndex.find` refuses on, here just kept rather than raised, because
                # a photo miss costs a blank tile and not a wrong listing.
                by_number.setdefault(join.number_index_key(number), str(url))
            try:
                product_id = int(product["productId"])
            except (KeyError, TypeError, ValueError):
                continue
            # KEYED ON `productId`, NEVER ON NAME: a `productId` is unique by definition, so
            # this dict alone can never be the thing that answers a wrong picture — the
            # ambiguity a shared NAME can raise is `products.find`'s question, not this one's.
            urls_by_product_id.setdefault(product_id, str(url))
        # SAME PAYLOAD, A SECOND WALK — `ProductIndex.build` derives its own `by_number`/
        # `by_name` from `results` again rather than being handed the loop above's output,
        # so this class's own ambiguity rule (`find`, D35's shape) is reused verbatim rather
        # than re-encoded from a dict this module built by hand.
        return _ImageIndex(
            by_number=by_number,
            products=ProductIndex.build(results),
            urls_by_product_id=urls_by_product_id,
        )

    def _warm_one(self, game: str, set_name: str) -> None:
        """One background fetch, and the only place `_cache`/`_pending` are written.

        `_pending` IS ALWAYS CLEARED, even on an exception `_fetch_tcgcsv` did not expect —
        a pair stuck `_pending` forever is a pair `warm()` never schedules again (D-demo-
        stock-images: this is what turned one race into a PERMANENT cold cache).
        """
        index = _ImageIndex(
            by_number={}, products=ProductIndex(by_number={}, by_name={}), urls_by_product_id={}
        )
        try:
            index = self._fetch_tcgcsv(game, set_name)
        finally:
            with self._lock:
                self._cache[(game, set_name)] = (time.time(), index)
                self._pending.discard((game, set_name))

    def warm(
        self, pairs: Iterable[Tuple[str, str]], *, allow_pokemon: bool = False
    ) -> List[threading.Thread]:
        """Schedule a background fetch for every `(game, set_name)` pair not already fresh.

        THE ONE SCHEDULING PRIMITIVE, called two ways. `server/capture_server.py:serve`
        calls it once at process start with every pair the store holds, so an operator's
        first request after a restart can already be warm. `_tcgcsv_lookup` calls it again
        on every read of a key whose entry has aged past `self._ttl` — the SAME check
        (`fresh`, below) decides both, so there is no second, polling thread's schedule to
        keep in step with this one.

        RETURNS THE THREADS IT STARTED, for a caller that wants to `.join()` them — the
        production caller (`serve`) never does, and a harness test does, which is what
        makes the warm deterministic there without a sleep.

        STILL NEVER SCHEDULES POKEMON BY DEFAULT, and this default is load-bearing rather
        than a leftover (review round, 2026-09-27, caught before merge): a Pokemon CARD's
        number reads local disk in `_PokemonImages` and never reaches this cache, so warming
        it would be a real tcgcsv fetch for a lookup `url_for` never makes.
        `server/pipeline_routes.py:warm_stock_images`'s startup pairs are every distinct
        `(game, set_name)` among IDENTIFIED CARDS — Pokemon singles included, one request per
        distinct Pokemon set the store holds, on every restart, for nothing. Measured on this
        checkout's own harness fixture (`check_stock_images_pokemon_warm_refusal`): 3
        Pokemon sets among on-hand cards, 5 real tcgcsv requests at startup with the skip
        removed (1 categories, 1 groups, 3 products), 0 with it back.

        `allow_pokemon=True` IS THE ONE NAMED EXCEPTION, and only `_tcgcsv_name_lookup` below
        passes it: a Pokemon SEALED PRODUCT (no number) has no vendored source at all and
        answers only through `url_for_product`'s tcgcsv walk (F2, `docs/decisions/
        D301-stock-images.md`'s amendment). `warm_stock_images`'s startup pairs come from
        `inventory.cards` alone (D299: sealed product is never captured, so it is never in
        that table) and never pass this flag, so a Pokemon sealed lookup is warmed only
        reactively, on the request that actually asks for one — never at startup.
        """
        started: List[threading.Thread] = []
        now = time.time()
        for game, set_name in pairs:
            if not game or not set_name or (game == POKEMON_KEY and not allow_pokemon):
                continue
            key = (game, set_name)
            with self._lock:
                entry = self._cache.get(key)
                fresh = entry is not None and (now - entry[0]) <= self._ttl
                if fresh or key in self._pending:
                    continue
                self._pending.add(key)
            thread = threading.Thread(target=self._warm_one, args=(game, set_name), daemon=True)
            thread.start()
            started.append(thread)
        return started

    def _tcgcsv_lookup(self, game: str, set_name: str, number: str) -> Optional[str]:
        """`_cache` ONLY — never the fetch. Schedules a background refresh on a cold or
        stale key and answers with whatever is on hand right now: `None` on cold, the
        last-known index on stale (serve-stale-while-revalidate, so a set that resolved
        once does not flicker back to no photo every time its hour runs out).
        """
        with self._lock:
            entry = self._cache.get((game, set_name))
        self.warm([(game, set_name)])
        if entry is None:
            return None
        return entry[1].by_number.get(join.number_index_key(number))

    def _tcgcsv_name_lookup(self, game: str, set_name: str, product_name: str) -> Optional[str]:
        """`_tcgcsv_lookup`'s twin for a SEALED product: same cache entry, same
        cold/stale/fresh posture, `ProductIndex.find` instead of a number-keyed dict.

        `find("", product_name)` IS THE AMBIGUITY REFUSAL, REUSED RATHER THAN RETYPED
        (review round, 2026-09-27): an empty `number` sends every real card straight past
        the number rung — `join.number_index_key("")` folds to `""`, which `find` treats as
        no key to look up — onto the SAME name rung a blank-`Number` row already uses (D35's
        shape). Two products sharing a name in one group there means `len(hits) != 1`, which
        `find` answers `None` for — never a guess at the first one.
        """
        with self._lock:
            entry = self._cache.get((game, set_name))
        # `allow_pokemon=True`: THE ONE CALLER THAT MAY WARM A POKEMON PAIR — see `warm`'s
        # own docstring for why the default refuses one and why this call is the exception.
        self.warm([(game, set_name)], allow_pokemon=True)
        if entry is None:
            return None
        product_id = entry[1].products.find("", product_name)
        if product_id is None:
            return None
        return entry[1].urls_by_product_id.get(product_id)

    def url_for(self, game: str, set_name: str, number: str) -> Optional[str]:
        """The image for one card, or `None` on a join miss, a cold cache, or an
        unreachable catalogue — NEVER raises and NEVER blocks on a network call. A tcgcsv
        fetch that fails answers `None` exactly like a miss — `#/pricing` and Inventory's
        Sets view both draw fine with no photo, and a public mirror having a bad moment
        must not take either screen down with it (the same posture `_history_unreachable`
        already gives the price-history panel).
        """
        if not game or not set_name or not number:
            return None
        if game == POKEMON_KEY:
            return self._pokemon.url_for(set_name, number)
        return self._tcgcsv_lookup(game, set_name, number)

    def url_for_product(
        self, product_line: str, set_name: str, product_name: str
    ) -> Optional[str]:
        """The image for a SEALED product (F2, no card number) — a booster box, an ETB.

        `#/revenue`'s own gap, the owner's report: *"why does the sales page not pull the
        icons like you're able to do on sets and pricing?"* Sales asks `GET /skus/photos`
        with a SKU only, which carries `product_line` (a tcgcsv-style cell, `pipeline/skus.
        py`) and `set_name` — never a `game` key. `games.game_for_product_line` is the one
        reverse lookup that turns that text back into a registry key.

        POKEMON SEALED RESOLVES THROUGH TCGCSV TOO, unlike a Pokemon CARD. `url_for` sends
        `game == POKEMON_KEY` to the vendored tree, which is singles-only — there is no
        sealed row in `vendor/pokemon-tcg-data/` for a booster box to match. So this method
        never branches on `POKEMON_KEY` at all; every catalogued game, Pokemon included,
        answers through `_tcgcsv_name_lookup`.

        `None` on an unregistered product line, a join miss, a cold cache, or an
        unreachable catalogue — never a guess, and never blocks on a network call, same as
        `url_for`.
        """
        if not product_line or not set_name or not product_name:
            return None
        game = game_registry.game_for_product_line(product_line)
        if game is None:
            return None
        return self._tcgcsv_name_lookup(game, set_name, product_name)

    def display_name(self, game: str, set_name: str) -> Optional[str]:
        """The catalogue's own clean name for a set, when this resolver can name one.

        POKEMON ONLY: the community code-prefix convention this exists to strip
        ("ME01: Mega Evolution") was measured on Pokemon rows alone; Riftbound and One
        Piece set names already arrive clean, so there is nothing here for them to
        resolve — the same asymmetry `url_for` already has between `_pokemon.url_for`
        and `_tcgcsv_lookup`. `None` on a join miss or an unnamed game, never a guess —
        the caller (`do_pipeline_sets`) keeps the store's own `set_name` in that case."""
        if not game or not set_name or game != POKEMON_KEY:
            return None
        return self._pokemon.display_name(set_name)
