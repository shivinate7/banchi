"""T7 group: inventory facets, box routes and search, box names and claims, sections.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sqlite3

from http import HTTPStatus
from harness.tests import Checks
from cli import resolve
from pipeline import join
from server import capture_server
from store import db, files, master
from store.session import Store
from harness.tests.t7.common import (
    QuietHandler,
    _spawn_server,
    capture_payload,
    error_code,
    fake_cid,
    isolated_home,
    photo_of,
    refusal,
    request,
)

# ---------------------------------------------------------------- D213's inventory filter


def check_inventory_filter_facets(checks: Checks) -> None:
    """D213 — the game/set/rarity filter on `#/inventory`, built on `GET /boxes`.

    `_card_facets` AND `_box_row`'s OWN `matches` ARE THE TWO HALVES: the first is the
    vocabulary a dropdown is populated from, the second is what tells the box rail which
    boxes the CURRENT filter actually touches. Both ride on the one route `#/inventory`
    already polls, per the decision's own ruling that a second route would repeat D192's
    argument against a second fetch.

    THE UNCLASSIFIED BUCKET IS THE CASE THIS TEST EXISTS TO PROVE. D213's own standing rule
    is that a card the pipeline could not classify is never dropped, applied to a filter —
    so a card with no set on file has to be REACHABLE under `set=` (the wire's spelling of
    "no set"), not merely counted.
    """
    checks.note("")
    checks.note("D213 — GAME/SET/RARITY FACETS AND THE INVENTORY FILTER")

    with isolated_home():
        with Store().write() as snapshot:
            inv = snapshot.inventory
            # Box 1: two Riftbound cards, one classified and one not.
            rift_a, _ = inv.allocate_capture(1, game="riftbound", cid=fake_cid("facet-rift-a"))
            inv.cards[rift_a.key].set_name, inv.cards[rift_a.key].rarity = "Unleashed", "Rare"
            rift_b, _ = inv.allocate_capture(1, game="riftbound", cid=fake_cid("facet-rift-b"))
            inv.cards[rift_b.key].set_name, inv.cards[rift_b.key].rarity = None, None
            # Box 2: one Pokemon card, also unclassified — the store's real shape (D213's
            # own measurement: every Pokemon card in the owner's store carries no set).
            poke, _ = inv.allocate_capture(2, game="pokemon", cid=fake_cid("facet-poke"))
            inv.cards[poke.key].set_name, inv.cards[poke.key].rarity = None, None

        # --- the vocabulary, off the store alone — never a hardcoded list -----------------
        answer = capture_server.do_boxes()
        facets = answer["facets"]
        checks.equal(
            sorted(row["game"] for row in facets["games"]),
            ["pokemon", "riftbound"],
            "GET /boxes answers with the game vocabulary this store actually holds, derived "
            "from the cards table and not from a fixed list",
        )
        rift_sets = {row["set"]: row["count"] for row in facets["sets"]["riftbound"]}
        checks.equal(
            rift_sets,
            {"Unleashed": 1, None: 1},
            "and Riftbound's set menu counts the classified card AND the null bucket — the "
            "unclassified card is a row in this menu, never an omission",
        )
        checks.equal(
            {row["set"]: row["count"] for row in facets["sets"]["pokemon"]},
            {None: 1},
            "Pokemon's own menu is one row, all of it unclassified — the shape D213 measured "
            "on the owner's store (no Pokemon export has ever been fetched)",
        )
        checks.equal(
            {row["rarity"]: row["count"] for row in facets["rarities"]["riftbound"]},
            {"Rare": 1, None: 1},
            "and rarity gets the same null bucket, off the same read",
        )

        # --- `matches` is ABSENT with no filter, so the box rail's plain count is untouched
        by_box = {row["box"]: row for row in answer["boxes"]}
        checks.ok(
            "matches" not in by_box[1] and "matches" not in by_box[2],
            "with no filter active, `matches` is not on the row at all — the box rail's "
            "'N on hand' stays what it always was for a screen that never turned the filter on",
        )

        # --- filtering by game narrows, across BOTH boxes at once ------------------------
        by_game = capture_server.do_boxes(game="riftbound")
        matches = {row["box"]: row["matches"] for row in by_game["boxes"]}
        checks.equal(
            matches,
            {1: 2, 2: 0},
            "game=riftbound matches both of box 1's cards and none of box 2's Pokemon card — "
            "the filter narrows the WHOLE STORE'S box rail, not one box at a time",
        )

        # --- the unclassified bucket is REACHABLE, never dropped -------------------------
        unclassified = capture_server.do_boxes(game="riftbound", set_name=None)
        matches = {row["box"]: row["matches"] for row in unclassified["boxes"]}
        checks.equal(
            matches,
            {1: 1, 2: 0},
            "game=riftbound AND set=<none> matches box 1's UNCLASSIFIED card and nothing "
            "else — D213's own standing rule (never drop a card silently) applied to a "
            "filter, proven on the exact card the decision was measured against",
        )

        # --- a real value still narrows correctly, and combines with rarity --------------
        combined = capture_server.do_boxes(game="riftbound", set_name="Unleashed", rarity="Rare")
        matches = {row["box"]: row["matches"] for row in combined["boxes"]}
        checks.equal(
            matches,
            {1: 1, 2: 0},
            "game+set+rarity together match only the one fully-classified card — every "
            "active facet is ANDed, not the last one applied winning",
        )

        # --- S3, THE OPUS REVIEW, 2026-09-25: A DIMENSION IS NEVER COUNTED UNDER ITS OWN
        # FILTER. `_card_facets` builds `sets_filters`/`rarities_filters` by EXCLUDING the
        # dimension's own key (`_other("game", "set_name")`, `_other("game", "rarity")`) —
        # every earlier assertion in this function reads `facets["sets"]`/`["rarities"]`
        # only with NO filter active at all, so a mutant that dropped that exclusion (making
        # the set menu narrow itself to whatever set is picked) went undetected: "picking
        # rarity first and set second gives the identical counts as the reverse" is a claim
        # this function had never once put a live `set_name`/`rarity` filter beside a
        # `facets` read to test.
        set_filtered = capture_server.do_boxes(game="riftbound", set_name="Unleashed")
        checks.equal(
            {row["set"]: row["count"] for row in set_filtered["facets"]["sets"]["riftbound"]},
            {"Unleashed": 1, None: 1},
            "with `set=Unleashed` ACTIVE, the SET menu still lists both sets — a dimension "
            "never narrows its own menu, or picking one set would erase every other choice "
            "from the dropdown that offered it",
        )
        checks.equal(
            {row["rarity"]: row["count"] for row in set_filtered["facets"]["rarities"]["riftbound"]},
            {"Rare": 1},
            "and the RARITY menu still follows the set filter as an ORDINARY other-facet — "
            "narrowed to only `set=Unleashed`'s own card the same way `matches` is, "
            "dropping the unclassified card's None-rarity bucket because IT carries no "
            "set at all — an other-facet obeys every active filter but its own",
        )
        rarity_filtered = capture_server.do_boxes(game="riftbound", rarity="Rare")
        checks.equal(
            {row["rarity"]: row["count"] for row in rarity_filtered["facets"]["rarities"]["riftbound"]},
            {"Rare": 1, None: 1},
            "and the reverse: with `rarity=Rare` ACTIVE, the RARITY menu still lists both "
            "rarities — the same dimension-never-counts-itself rule from the other side",
        )
        checks.equal(
            {row["set"]: row["count"] for row in rarity_filtered["facets"]["sets"]["riftbound"]},
            {"Unleashed": 1},
            "while the SET menu (an ordinary other-facet under `rarity=Rare`) narrows to "
            "just the classified card — the null-set card is Rare too but has no `set` to "
            "list, so it drops out of the SET bucket the same way any other-facet narrows",
        )

        # --- clearing the filter restores everything ------------------------------------
        cleared = capture_server.do_boxes()
        checks.ok(
            all("matches" not in row for row in cleared["boxes"]),
            "and calling with no filter keywords at all returns to the unfiltered shape — "
            "the same route, the same rows, nothing left over from the last question asked",
        )

        # --- UX-210: hide_sold narrows both `matches` and `facets`, ANY ORDER of the OTHER
        # active filters, the owner's own measured shape ("9 matches" against a 7-row walk,
        # a games total of 122 that was every card ever captured). Three more Riftbound
        # cards in box 1, one departed by each of the three doors, added here rather than
        # in the setup above so the first half of this test stays the ground D213 was
        # originally measured against.
        #
        # F4, round-3 Opus review, 2026-09-25: SOLD ALONE IS NOT ENOUGH. D132 hides every
        # DEPARTED card, not sold alone, and the fixture before this fix carried only a
        # SOLD card — a mutant narrowing S3's fix back to `state == master.SOLD` (instead
        # of `state in master.TERMINAL_STATES`) stayed GREEN, because a retired or moved
        # card was never in this fixture to leak through. `rift_d` (RETIRED) and `rift_e`
        # (MOVED) are that mutant's own counter-example: both carry the SAME set/rarity as
        # `rift_c`, so every assertion below that stayed unchanged by adding `rift_c` alone
        # now ALSO has to stay unchanged with two more departed cards added, or the mutant
        # shows through as a wrong number.
        with Store().write() as snapshot:
            rift_c, _ = snapshot.inventory.allocate_capture(1, game="riftbound", cid=fake_cid("facet-rift-sold"))
            snapshot.inventory.cards[rift_c.key].set_name = "Unleashed"
            snapshot.inventory.cards[rift_c.key].rarity = "Rare"
            snapshot.inventory.set_state(rift_c.key, master.SOLD)
            rift_d, _ = snapshot.inventory.allocate_capture(1, game="riftbound", cid=fake_cid("facet-rift-retired"))
            snapshot.inventory.cards[rift_d.key].set_name = "Unleashed"
            snapshot.inventory.cards[rift_d.key].rarity = "Rare"
            snapshot.inventory.set_state(rift_d.key, master.RETIRED)
            rift_e, _ = snapshot.inventory.allocate_capture(1, game="riftbound", cid=fake_cid("facet-rift-moved"))
            snapshot.inventory.cards[rift_e.key].set_name = "Unleashed"
            snapshot.inventory.cards[rift_e.key].rarity = "Rare"
            snapshot.inventory.set_state(rift_e.key, master.MOVED)

        no_hide = capture_server.do_boxes(game="riftbound")
        checks.equal(
            {row["box"]: row["matches"] for row in no_hide["boxes"]},
            {1: 5, 2: 0},
            "before this fix's toggle: game=riftbound counts the sold, retired AND moved "
            "cards too — a departed card is still on hand as far as a bare game filter is "
            "concerned",
        )
        with_hide = capture_server.do_boxes(game="riftbound", hide_sold=True)
        checks.equal(
            {row["box"]: row["matches"] for row in with_hide["boxes"]},
            {1: 2, 2: 0},
            "and with hide_sold=True EVERY departed copy drops out of `matches` — sold, "
            "retired AND moved, not sold alone — while `cards`/`sold` (D58's own promise) "
            "are untouched",
        )
        checks.equal(
            capture_server.do_boxes()["boxes"][0]["sold"],
            1,
            "and the plain `sold` count on the unfiltered row still counts only the sold "
            "one — hide_sold narrows `matches` and `facets` alone, never the box's own "
            "census, and retired/moved have their own separate counters",
        )
        hidden_facets = capture_server.do_boxes(hide_sold=True)["facets"]
        rift_games = {row["game"]: row["count"] for row in hidden_facets["games"]}
        checks.equal(
            rift_games["riftbound"], 2,
            "and the GAMES facet drops every departed card — sold, retired and moved — "
            "before this fix it summed every card ever captured regardless of Hide sold, "
            "which is the owner's own 'Pokémon (37) + Riftbound (85) = 122, every card "
            "ever captured' measurement",
        )
        combined_hide = capture_server.do_boxes(rarity="Rare", hide_sold=True)
        checks.equal(
            {row["game"]: row["count"] for row in combined_hide["facets"]["games"]},
            {"riftbound": 1},
            "filters compose in ANY ORDER: rarity=Rare picked before hide_sold gives the "
            "identical games count as hide_sold picked first — one live Rare Riftbound "
            "card, and the sold, retired AND moved Rare ones all excluded — a "
            "`state == SOLD` mutant would count `rift_d`/`rift_e` here too and answer 3",
        )

        # --- the wire itself: `?set=` (blank) means the unclassified bucket, not "unset" --
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = _spawn_server(httpd)
        try:
            status, raw, _ = request(port, "GET", "/boxes?game=riftbound&set=")
            checks.equal(status, 200, "GET /boxes?game=riftbound&set= answers 200")
            body = json.loads(raw)
            matches = {row["box"]: row.get("matches") for row in body["boxes"]}
            checks.equal(
                matches,
                {1: 1, 2: 0},
                "and on the wire, a BLANK `set` param reaches `do_boxes` as `set_name=None` "
                "— the unclassified bucket, not 'no set filter' — because `keep_blank_values`"
                " is what tells the two apart",
            )

            status, raw, _ = request(port, "GET", "/boxes")
            checks.equal(
                status,
                200,
                "and a bare GET /boxes, with no query string at all, still answers 200",
            )
            body = json.loads(raw)
            checks.ok(
                all("matches" not in row for row in body["boxes"]),
                "with `facets` still riding along even though nothing is being filtered",
            )
            checks.ok(
                "facets" in body and "games" in body["facets"],
                "and the facets block reaches the wire under the same key `do_boxes` returns "
                "in-process",
            )
        finally:
            httpd.shutdown()
            thread.join()


def check_inventory_facet_cells(checks: Checks) -> None:
    """FLT-09 — `#/inventory`'s filters work in any order, so `GET /boxes` ships the cells.

    `facet_cells` groups every card by box, game, set, rarity and whether it left. The screen
    folds them for every count under the OTHER picks and Hide sold. So the cells must keep the
    null bucket, split a sold copy from a live one, and add up to every card in the store.
    """
    checks.note("")
    checks.note("FLT-09 — GET /boxes CARRIES THE FACET CELLS")

    with isolated_home():
        with Store().write() as snapshot:
            inv = snapshot.inventory
            a, _ = inv.allocate_capture(1, game="riftbound", cid=fake_cid("cell-a"))
            inv.cards[a.key].set_name, inv.cards[a.key].rarity = "Unleashed", "Rare"
            b, _ = inv.allocate_capture(1, game="riftbound", cid=fake_cid("cell-b"))
            inv.cards[b.key].set_name, inv.cards[b.key].rarity = "Unleashed", "Rare"
            inv.cards[b.key].state = master.SOLD
            c, _ = inv.allocate_capture(2, game="pokemon", cid=fake_cid("cell-c"))
            inv.cards[c.key].set_name, inv.cards[c.key].rarity = None, "Rare"
            # N1: `gone_states` NAMES ALL THREE OF D26/D83's DOORS, and until this the fixture
            # only ever walked one of them through — a regression narrowing `gone_states` to
            # `{SOLD}` alone would still pass every check above. Own boxes, so each is its own
            # cell rather than folding into `b`'s.
            d, _ = inv.allocate_capture(3, game="riftbound", cid=fake_cid("cell-d"))
            inv.cards[d.key].set_name, inv.cards[d.key].rarity = "Unleashed", "Rare"
            inv.cards[d.key].state = master.RETIRED
            e, _ = inv.allocate_capture(4, game="riftbound", cid=fake_cid("cell-e"))
            inv.cards[e.key].set_name, inv.cards[e.key].rarity = "Unleashed", "Rare"
            inv.cards[e.key].state = master.MOVED

        cells = capture_server.do_boxes()["facet_cells"]
        seen = sorted(
            (cell["box"], cell["game"], cell["set"], cell["rarity"], cell["gone"], cell["count"])
            for cell in cells
        )
        checks.equal(
            seen,
            [
                (1, "riftbound", "Unleashed", "Rare", False, 1),
                (1, "riftbound", "Unleashed", "Rare", True, 1),
                (2, "pokemon", None, "Rare", False, 1),
                (3, "riftbound", "Unleashed", "Rare", True, 1),
                (4, "riftbound", "Unleashed", "Rare", True, 1),
            ],
            "one cell per box, game, set, rarity and gone: the sold, retired and moved copies "
            "are each their own cell, and the Pokemon card with no set keeps a null set rather "
            "than being dropped",
        )
        checks.equal(
            sum(cell["count"] for cell in cells),
            5,
            "and the cells add up to every card in the store, so no count on the screen can "
            "miss one",
        )
        rare_live = sum(
            cell["count"] for cell in cells if cell["rarity"] == "Rare" and not cell["gone"]
        )
        checks.equal(
            rare_live,
            2,
            "Rarity 'Rare' with no game picked and Hide sold on counts two cards across two "
            "games: a rarity is reachable before a game, which the per-game menu could not say",
        )

# ---------------------------------------------------------------- box routes and search


def check_box_routes_and_search(checks: Checks) -> None:
    """D20's four routes — the three that own a box, and the read that finds a card.

    `check_boxes_and_listings` ABOVE ASSERTS THE STORE; THIS ASSERTS THE ROUTES. They are
    different questions and the difference is T7's whole subject: `close_box` freezing
    capacity is a rule, and `PUT /boxes/<box>` refusing to be handed one is wiring. A rule
    that is right behind a route nobody can reach correctly is still a box counted against
    the wrong denominator on the only screen that could repair it.

    THE UNREGISTERED BOX IS THE CASE TO KEEP. Until D20 a box existed only because a card
    named one, so every box captured before the registry has no entry — and a read that
    listed the registry alone would hide exactly those, on the screen built to fix them.
    """
    checks.note("")
    checks.note("BOX ROUTES AND SEARCH — server/capture_server.py")

    with isolated_home():
        for _ in range(3):
            capture_server.do_capture(capture_payload(8))
        # A box that holds cards and has NO registry entry. `allocate_capture` calls
        # `ensure_box`, so this shape cannot be reached through the front door any more —
        # which is precisely why it is built by hand: every box filled before D20 is in it,
        # and there is no other way left to produce one.
        with Store().write() as snapshot:
            del snapshot.inventory.boxes["8"]

        listed = {row["box"]: row for row in capture_server.do_boxes()["boxes"]}
        # Guarded, for the reason `Checks` collects failures instead of stopping at the
        # first: a missing row here would take the twenty checks behind it down with a
        # KeyError, and the state of everything behind a failure is what a harness is for.
        if checks.ok(
            8 in listed,
            "GET /boxes lists a box that holds cards but has no registry entry — the union, "
            "not the registry, so no box captured before D20 is invisible",
        ):
            checks.equal(
                ["state" in listed[8], "capacity" in listed[8], listed[8]["sections"]],
                [False, False, []],
                "and it renders undeclared, with no lid and no capacity: a box has neither "
                "since `D299`",
            )
            checks.equal(
                [listed[8]["cards"], listed[8]["fill"], listed[8]["next_index"]],
                [3, 3, 4],
                "with its fill and next index read the same way every other box's are",
            )

        # --- POST creates, and refuses to be an upsert -----------------------------------
        status, created = capture_server.do_create_box(
            {"box": 9, "name": "ME01 commons", "sections": [1, 31]}
        )
        checks.equal(status, HTTPStatus.CREATED, "POST /boxes answers 201")
        checks.equal(
            [created["box"], created["name"], created["cards"]],
            [9, "ME01 commons", 0],
            "and a box can be created EMPTY — D20's whole reason for existing, since a "
            "mistyped box number was previously caught only by `new_box` after a photo "
            "had already been written into it",
        )
        refusal(
            checks,
            lambda: capture_server.do_create_box({"box": 9}),
            "box_exists",
            "and a second POST refuses as box_exists rather than upserting — a quiet "
            "success here would rename box 9 while the operator believed they were adding one",
        )
        refusal(
            checks,
            lambda: capture_server.do_create_box({"box": 10, "capacity": 250}),
            "field_not_settable",
            "capacity is not a creation field: nobody knows a box's capacity when they "
            "start filling it, and a guess accepted here is inherited by every fraction "
            "drawn from that box (D20)",
        )

        # --- PUT changes the three things a human decides, and nothing else --------------
        refusal(
            checks,
            lambda: capture_server.do_put_box(9, {"capacity": 250}),
            "field_not_settable",
            "and PUT refuses `capacity`: a box has none (`D299`)",
        )
        refusal(
            checks,
            lambda: capture_server.do_put_box(9, {"box": 11}),
            "field_not_settable",
            "and refuses `box`: a body that could change a box NUMBER would be a renumber, "
            "which D10 forbids outright",
        )
        refusal(
            checks,
            lambda: capture_server.do_put_box(99, {"name": "nowhere"}),
            "box_not_found",
            "and a box number nothing in this store has ever seen refuses as box_not_found",
        )
        adopted = capture_server.do_put_box(8, {"name": "pre-registry"})
        checks.equal(
            adopted["name"],
            "pre-registry",
            "but the unregistered box is ADOPTED rather than refused: GET /boxes lists it, "
            "so refusing here would put a dead rename control on a live row",
        )

        # --- NO SEAL (`D299`, the owner's ruling of 2026-09-25) ----------
        # "what was the point of sealed boxes? lets kill this". Red before the removal: the
        # PUT sealed box 8, and the capture into it was refused `box_closed`.
        refusal(
            checks,
            lambda: capture_server.do_put_box(8, {"state": "closed"}),
            "field_not_settable",
            "a box has no lid: PUT refuses `state` as a field it does not have",
        )
        status, _ = capture_server.do_capture(capture_payload(8))
        checks.ok(
            int(status) in (200, 201),
            "and a capture into any box is taken: there is no sealed box to refuse it",
            f"status {status}",
        )
        checks.ok(
            not hasattr(master, "BoxClosed") and not hasattr(master.Inventory, "close_box"),
            "and the store has no seal left to reach: no `BoxClosed`, no `close_box`",
        )

    # --- GET /search: D7's SKU -> positions map, finally served to a screen -------------
    with isolated_home():
        for _ in range(3):
            capture_server.do_capture(capture_payload(8, set_hint="me01"))
        capture_server.do_capture(capture_payload(8, game="misc"))
        capture_server.do_put_card(8, 4, {"note": "blue-eyes, japanese"})
        with Store().write() as snapshot:
            for key in ("8/1", "8/2", "8/3"):
                card = snapshot.inventory.cards[key]
                card.sku = "555"
                card.name = "Eiscue"
                card.number = "044"
                card.printed_total = "167"
                card.condition = "Near Mint"
            snapshot.inventory.listing("555", condition="Near Mint").live = 2
            snapshot.inventory.set_state("8/3", master.SOLD)

        for blank in ("", "   ", "\t\n"):
            refusal(
                checks,
                lambda q=blank: capture_server.do_search(q),
                "query_required",
                f"a search for {blank!r} refuses as query_required — clearing the box is "
                "not a request for every card in the store",
            )

        # F6, round-3 Opus review, 2026-09-25: NO QUERY MAY 500. A NUL byte truncates the
        # C string sqlite3's driver binds while Python's own `len()` still sees the whole
        # thing, and the mismatch surfaced as an uncaught `OperationalError` from deep
        # inside `_fts_query`'s own MATCH — `q=%00` and `q=a%00b` both 500'd. Asserted
        # in-process first (the refusal itself), then over a real socket (F6's own report
        # named the WIRE route, `GET /search?q=%00`) so a future regression cannot hide
        # behind an in-process call that never reaches the real query-string decode.
        for nul_query in ("\x00", "a\x00b"):
            refusal(
                checks,
                lambda q=nul_query: capture_server.do_search(q),
                "query_invalid",
                f"a search for {nul_query!r} refuses as query_invalid rather than 500ing",
            )

        # AND OVER THE REAL SOCKET, the shape F6's own report named — a query STRING with
        # a percent-encoded NUL, decoded by `parse_qs` the same way a browser's own request
        # would arrive.
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = _spawn_server(httpd)
        try:
            for wire_query in ("/search?q=%00", "/search?q=a%00b"):
                status, body, _ = request(port, "GET", wire_query)
                checks.equal(
                    status, 400, f"GET {wire_query} answers 400, never 500",
                )
                checks.equal(
                    error_code(body), "query_invalid",
                    f"and GET {wire_query} names the refusal",
                )
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

        found = capture_server.do_search("eiscue")["groups"]
        if checks.equal(
            [group["sku"] for group in found],
            ["555"],
            "a name finds the SKU, and the answer is the SKU rather than the card — D7's "
            "map, which has existed in the store since the store did and reached no screen",
        ):
            group = found[0]
            checks.equal(
                [copy["key"] for copy in group["copies"]],
                ["8/1", "8/2", "8/3"],
                "with every copy at its own position, in box-walk order, the sold one "
                "included",
            )
            checks.equal(
                group["on_hand"],
                2,
                "and `on_hand` EXCLUDES the sold copy while `copies` still lists it: a sale "
                "leaves a permanent gap that the operator still needs to see (D10)",
            )
            checks.ok(
                "cap" not in group,
                "AND THERE IS NO `cap` ON THE WIRE (D7, amended 2026-09-08). The field carried "
                "the store's standing bound, which is deleted — a wire field for a rule that "
                "no longer exists is a claim with no reader and no way of being contradicted "
                "(D80). Asserted as an absence rather than a null, because a null would leave "
                "every screen still deciding what to draw for it",
            )
            # THE SHELF IS THE ONLY BOUND NOW, and this field is what says so. It was
            # `min(cap, on hand)` while a cap existed, and the pair was on the wire so a
            # screen could draw either the rule or what the rule permitted here. The screen
            # drew the bare `cap` as the denominator of `listed N of ...` until 2026-08-25, so
            # a card the owner had one of read `listed 0 of 4` — three copies of headroom that
            # do not exist. That defect cannot recur: there is one field and it is the shelf.
            checks.equal(
                group["listable"],
                2,
                "and `listable` is what the SHELF holds — two copies on hand, so the most "
                "this SKU can ever have live is two, and the screen cannot promise a playset "
                "the boxes do not hold",
            )
            checks.equal(
                group["listed"],
                {
                    stage: (2 if stage == master.LIVE else 0)
                    for stage in master.LISTING_STAGES
                },
                "listing counts come out as zeros rather than nulls for the stages nothing "
                "has reached: 'nothing was emitted' is a fact, not an absence",
            )

        by_note = capture_server.do_search("japanese")["groups"]
        checks.equal(
            [copy["key"] for group in by_note for copy in group["copies"]],
            ["8/4"],
            "a card the pipeline never identified is found BY ITS NOTE — it has no name, "
            "no number and no SKU, so the note is the only thing it can be found by, and "
            "leaving it out of the search would make the field write-only",
        )
        checks.equal(
            [group["sku"] for group in by_note],
            [None],
            "and it groups under a null SKU, which sorts last: a bag of cards, not a product",
        )
        checks.equal(
            [group["sku"] for group in capture_server.do_search("044/167")["groups"]],
            ["555"],
            "and the join key itself is searchable — it is the string the run report and "
            "the queue file both print, so it is what gets pasted into a search box",
        )

        # --- D67: the group agrees on what the SCREEN draws, not on what the model typed ---
        #
        # THE LIVE SHAPE, WITH THE STORE'S OWN NUMBERS BEHIND IT. Five copies of Moonfall carry
        # three spellings of one identifier — `198/219` twice, `UNL • 198/219` and
        # `UNL - 198/219` once each — because D55's repair fires on the JOIN and nothing had
        # ever applied it to a screen. `_agreed` therefore returned None, correctly, and the
        # group lost its number row while every copy's own row showed its own variant. All
        # three glued here so the case cannot pass on a surviving clean copy.
        with Store().write() as snapshot:
            for key, glued in (
                ("8/1", "UNL \u2022 044"),
                ("8/2", "UNL - 044"),
                ("8/3", "UNL / 044"),
            ):
                snapshot.inventory.cards[key].number = glued

        mixed = capture_server.do_search("eiscue")["groups"][0]
        checks.equal(
            mixed["number"],
            None,
            "the RAW field still disagrees and is still None — `_agreed` is unchanged, and "
            "a number lifted off whichever copy the dict yielded first is still refused",
        )
        checks.equal(
            mixed["number_display"],
            "044/167",
            "and the group can speak again, because all three copies say the same thing once "
            "the set code the model glued on is off the front of it (D67)",
        )
        checks.equal(
            [group["sku"] for group in capture_server.do_search("044/167")["groups"]],
            ["555"],
            "AND WHAT THE SCREEN DREW IS STILL SEARCHABLE, which is the side effect the fix "
            "had to close: not one copy stores `044/167` any more, so a raw-only match would "
            "answer nothing for a string the copies list had just printed",
        )
        checks.equal(
            capture_server.do_inventory()["cards"]["8/1"]["number"],
            "UNL \u2022 044",
            "the RECORD is untouched — D36 keeps the read as the model returned it, and a "
            "store tidied at read time cannot report the prompt being ignored",
        )
        checks.equal(
            capture_server.do_inventory()["cards"]["8/1"]["number_display"],
            "044/167",
            "and the decoration rides beside it, wire-only, in the shape `label` already takes",
        )
        row_inventory = Store().read().inventory
        checks.equal(
            capture_server._card_row(
                row_inventory, 8, 1, row_inventory.cards["8/1"]
            )["number_display"],
            "044/167",
            "AND `_card_row` DECORATES IT TOO, so a screen holding a write's answer against a "
            "row of `GET /inventory` compares field for field — the property that file's own "
            "docstring promises, one field wider. Called directly because the four routes that "
            "return it are the review and undo routes, whose own fixtures are three sections "
            "down and have no numbered card in them",
        )
        checks.equal(
            capture_server._match_rank(
                Store().read().inventory.cards["8/1"], "044/167"
            ),
            capture_server._RANK_EXACT_NUMBER,
            "and typing what the screen drew is an EXACT number match, not a substring one: "
            "the raw field still contains the display form so a fold-less build still FINDS "
            "the card, and ranks it below every name prefix on the page — the rank is where "
            "this is observable, which is why it is asserted and not the group's presence",
        )

        # A GAME THAT PRINTS NO DENOMINATOR, WHICH IS 174 OF THE OWNER'S 676 NUMBERED RECORDS.
        # The store writes `""` there and two client copies of this composition tested
        # `printed_total === null` alone, one line below testing `number` for null OR blank —
        # so a quarter of the store rendered `198/219/`, a separator with nothing behind it.
        with Store().write() as snapshot:
            snapshot.inventory.cards["8/1"].printed_total = ""
        checks.equal(
            capture_server.do_inventory()["cards"]["8/1"]["number_display"],
            "044",
            "an empty `printed_total` is an ABSENT denominator and not half of one: no "
            "trailing separator, on the game that never prints one",
        )


def check_search_fts5(checks: Checks) -> None:
    """Store-scaling item 8: `do_search` reads an FTS5 index, and the walk is deleted.

    THE PROPERTY UNDER TEST IS THE SAME ONE `check_box_routes_and_search` ALREADY PROVES —
    every existing assertion there (`eiscue`, `japanese`, `044/167`, the D67 mixed-number
    case) passes unmodified against this rewrite, which is what proves the CANDIDATE SET
    changed and the ANSWER did not. This function proves the three properties that are new:
    multi-word any-order matching, prefix matching from a word's start, and that the index
    tracks every write shape the ordinary application makes, plus the migration that seeds
    it for a store that predates it.

    MID-WORD MATCHING WAS AN ACCEPTED LOSS AND IS NOT ONE ANY MORE (the owner's ruling,
    2026-09-25: "Add mid-word search"). D271's one matcher wins over this item's own
    prefix-only trade-off. `server/capture_server.py:_fts_substring_candidates` is a
    fourth candidate source, a plain SQL `LIKE '%term%'` scan, measured first on a
    synthetic 2,500-card store before it shipped
    (`docs/decisions/D271-every-search-uses-one-matcher.md` carries the numbers). The
    `midword` case below now asserts the FOUND direction.

    ORDINARY WRITES EXERCISE `cards_fts_ad` THEN `cards_fts_ai`, NEVER `cards_fts_au` —
    THIS WAS NOT WHAT store/db.py's OWN COMMENT NEXT TO THE THIRD TRIGGER PREDICTS, AND IT
    IS WORTH RECORDING HERE SO A FUTURE SESSION DOES NOT "FIX" THE MISSING COVERAGE BY
    DELETING THE TRIGGER. `store/db.py:flush_rows` clears every touched key with a real
    `DELETE` before it re-inserts it (its own docstring: "the first pass clears every key
    the second pass will write"), for a reason that has nothing to do with search — the
    UNIQUE `cards_cid` index needs the transient collision room. So a rename through
    `Store().write()` is a real SQL DELETE followed by a real SQL INSERT, never an UPDATE,
    and SQLite allocates the INSERT a fresh rowid. Measured directly: renaming a card left
    its own rowid 2 for a table of three and the row came back at rowid 4. The three-trigger
    shape is still correct SQLite practice (a genuine `UPDATE` — which this migration's own
    backfill loop and `scripts/cid-selftest.py`'s raw-SQL manipulations both perform — needs
    `cards_fts_au`, and an external-content table with only two of the three triggers is a
    documented way to corrupt the shadow index), so all three stay; this comment is the
    record of WHERE each one is actually reached, because "AU fires on every rename" was
    the wrong prediction to build a mutation arm on.
    """
    checks.note("")
    checks.note("SEARCH — server/capture_server.py:do_search, store/db.py:_add_search_index")

    with isolated_home():
        # --- multi-word, any order --------------------------------------------------
        capture_server.do_capture(capture_payload(1))
        with Store().write() as snapshot:
            card = snapshot.inventory.cards["1/1"]
            card.name = "Charizard"
            card.set_hint = "Base Set"

        forward = [g["sku"] for g in capture_server.do_search("base charizard")["groups"]]
        backward = [g["sku"] for g in capture_server.do_search("charizard base")["groups"]]
        checks.ok(
            forward and forward == backward,
            "multi-word search finds the same group regardless of word order — the "
            "property the owner chose FTS5 over LIKE for",
            f"forward={forward!r} backward={backward!r}",
        )

        # --- prefix from a word's start, and mid-word matching (MID-WORD, 2026-09-25) ---
        prefix = [g["sku"] for g in capture_server.do_search("chariz")["groups"]]
        midword = [g["sku"] for g in capture_server.do_search("izard")["groups"]]
        checks.ok(
            bool(prefix),
            "a partial word typed from its start still hits ('chariz' finds Charizard)",
        )
        checks.ok(
            bool(midword) and midword == prefix,
            "and a mid-word fragment DOES too ('izard' finds Charizard) — the owner "
            "reversed the earlier trade-off ('Add mid-word search'); measured first on a "
            "synthetic 2,500-card store, never this repo's own, before it shipped "
            "(docs/decisions/D271-every-search-uses-one-matcher.md)",
            f"midword={midword!r} prefix={prefix!r}",
        )

        # --- the index tracks capture, sale, box moves and rename -----------------------
        capture_server.do_capture(capture_payload(2))
        with Store().write() as snapshot:
            card = snapshot.inventory.cards["2/1"]
            card.name = "Blastoise"
            card.sku = "9001"
        checks.equal(
            [g["sku"] for g in capture_server.do_search("blastoise")["groups"]],
            ["9001"],
            "a freshly captured, freshly named card is findable — the AI trigger fired",
        )

        with Store().write() as snapshot:
            snapshot.inventory.set_state("2/1", master.SOLD)
        checks.equal(
            [g["sku"] for g in capture_server.do_search("blastoise")["groups"]],
            ["9001"],
            "and STILL findable once sold — `do_search` does not filter on state, matching "
            "the walk's own behavior, and the delete-then-reinsert `flush_rows` performs "
            "for the state change did not lose the row",
        )

        with Store().write() as snapshot:
            snapshot.inventory.cards["2/1"].name = "Blastoise EX"
        renamed = capture_server.do_search("blastoise")["groups"]
        checks.equal(
            [g["sku"] for g in renamed], ["9001"],
            "a renamed card is still found by the word it shares with its old name",
        )
        checks.ok(
            renamed and renamed[0]["names"] == ["Blastoise EX"],
            "and the group's own name is the NEW one, not a stale copy of the old",
            f"names={renamed[0]['names'] if renamed else None!r}",
        )

    # --- a dedicated, deterministic proof that `cards_fts_ad` is load-bearing -----------
    #
    # THE PLAIN SKU/NAME ASSERTIONS ABOVE CANNOT SEE A DISABLED `cards_fts_ad`, AND THIS
    # WAS MEASURED RATHER THAN ASSUMED — the original draft of this function asserted
    # exactly those two things and both stayed GREEN with the trigger's body commented
    # out. `do_search`'s `JOIN cards ON cards.rowid = cards_fts.rowid` silently drops an
    # orphaned `cards_fts` row whose rowid `cards` no longer has, which is the ordinary
    # case right after a rename (SQLite hands the re-inserted row a FRESH rowid — see this
    # function's own docstring). The defect only becomes VISIBLE once that freed rowid is
    # reused, at which point the orphan's stale tokens and the new row's tokens are BOTH
    # indexed under one docid — measured directly: a single-card store's rename reused
    # rowid 1 for the new row, and with `cards_fts_ad` disabled a search for the CARD'S OLD
    # NAME matched it. So this sub-case pins down the one condition (a store with exactly
    # one card, so the freed rowid is deterministically the very next one issued) where the
    # defect is guaranteed to surface, rather than depending on incidental rowid reuse.
    with isolated_home():
        capture_server.do_capture(capture_payload(9))
        with Store().write() as snapshot:
            snapshot.inventory.cards["9/1"].name = "Gyarados"

        with Store().write() as snapshot:
            snapshot.inventory.cards["9/1"].name = "Magikarp"

        conn = sqlite3.connect(str(files.inventory_dir() / "store.sqlite"))
        try:
            stale = conn.execute(
                "SELECT rowid FROM cards_fts WHERE cards_fts MATCH '\"gyarados\"*'"
            ).fetchall()
            fresh = conn.execute(
                "SELECT rowid FROM cards_fts WHERE cards_fts MATCH '\"magikarp\"*'"
            ).fetchall()
        finally:
            conn.close()
        checks.equal(stale, [], "the pre-rename name no longer matches anything at all")
        checks.ok(bool(fresh), "and the post-rename name does")

    # --- the migration seeds the index for rows that predate it -----------------------
    with isolated_home():
        capture_server.do_capture(capture_payload(5))
        with Store().write() as snapshot:
            card = snapshot.inventory.cards["5/1"]
            card.name = "Venusaur"
            card.number = "003"
            card.printed_total = "102"
            card.sku = "7777"

        # Roll the physical store back to looking like it predates item 8: drop the FTS
        # table and its triggers, blank the two derived columns, and re-stamp schema 6 —
        # the state `_ensure_schema`'s NEW-STORE branch would never have produced without
        # this item, and the state every real store on disk was in before this migration
        # ran on it.
        store_path = str(files.inventory_dir() / "store.sqlite")
        conn = sqlite3.connect(store_path, isolation_level=None)
        try:
            conn.execute("DROP TRIGGER IF EXISTS cards_fts_ai")
            conn.execute("DROP TRIGGER IF EXISTS cards_fts_ad")
            conn.execute("DROP TRIGGER IF EXISTS cards_fts_au")
            conn.execute("DROP TABLE IF EXISTS cards_fts")
            for shadow in ("cards_fts_data", "cards_fts_idx", "cards_fts_docsize", "cards_fts_config"):
                conn.execute(f"DROP TABLE IF EXISTS {shadow}")
            conn.execute("UPDATE cards SET number_key = NULL, number_display = NULL")
            conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('schema', '6')")
        finally:
            conn.close()

        # PROVE THE SETUP ITSELF, BEFORE ASKING `do_search` ANYTHING — a raw read, not
        # through the application. `do_search`'s OWN FIRST LINE (`Store().read()`) opens a
        # `db.connect()` that runs `_ensure_schema`/`_upgrade` transparently, so by the time
        # `do_search` could answer at all, the migration has already run; there is no
        # observable "before" through the application API, and asserting `do_search` finds
        # nothing here would be asserting an artifact of call order, not of the migration.
        conn = sqlite3.connect(store_path)
        try:
            pre_stamp = conn.execute("SELECT value FROM meta WHERE key = 'schema'").fetchone()
            pre_fts = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name = 'cards_fts'"
            ).fetchone()
        finally:
            conn.close()
        checks.equal(pre_stamp, ("6",), "the store really is stamped as predating item 8")
        checks.ok(pre_fts is None, "and really has no search index yet")

        # The next open runs `_upgrade`, which is what `do_search` itself triggers via
        # `Store().read()` -> `db.connect`. No explicit migration call: this is the same
        # path an operator's ordinary next request takes after a `git pull`.
        checks.equal(
            [g["sku"] for g in capture_server.do_search("venusaur")["groups"]],
            ["7777"],
            "and after the migration seeds it (triggered by the very next read), the "
            "pre-existing card is findable by name",
        )
        checks.equal(
            [g["sku"] for g in capture_server.do_search("003/102")["groups"]],
            ["7777"],
            "and by its composed number key, backfilled from `number`/`printed_total` "
            "through `pipeline/join.py` rather than left null",
        )

    # --- `cards_fts_au` is reached by a raw SQL UPDATE, not by the ordinary write path --
    #
    # NO ORDINARY APPLICATION WRITE EVER FIRES `cards_fts_au` — MEASURED, NOT ASSUMED. This
    # function's own docstring explains why (`flush_rows` deletes before every upsert), and
    # every OTHER sub-case above genuinely goes through `Store().write()`, so none of them
    # exercises this trigger. What DOES perform a genuine `UPDATE cards ... WHERE key = ?`
    # with no preceding delete: `store/db.py:_add_search_index`'s own backfill loop (which
    # runs before `cards_fts` exists, so it cannot be what proves this trigger works either)
    # and `scripts/cid-selftest.py`'s raw-SQL manipulations (`_unname`, `_add_card_ids`).
    # Reproduced here directly, the same way: a raw `UPDATE cards SET name = ?` on an
    # ALREADY-migrated store, bypassing the ORM entirely.
    with isolated_home():
        capture_server.do_capture(capture_payload(10))
        with Store().write() as snapshot:
            snapshot.inventory.cards["10/1"].name = "Gyarados"
        conn = sqlite3.connect(str(files.inventory_dir() / "store.sqlite"), isolation_level=None)
        try:
            conn.execute("UPDATE cards SET name = ? WHERE key = ?", ("Magikarp", "10/1"))
        finally:
            conn.close()
        conn = sqlite3.connect(str(files.inventory_dir() / "store.sqlite"))
        try:
            stale = conn.execute(
                "SELECT rowid FROM cards_fts WHERE cards_fts MATCH '\"gyarados\"*'"
            ).fetchall()
            fresh = conn.execute(
                "SELECT rowid FROM cards_fts WHERE cards_fts MATCH '\"magikarp\"*'"
            ).fetchall()
        finally:
            conn.close()
        checks.equal(
            stale, [],
            "a raw SQL UPDATE (never touching `Store().write()`) still retires the old "
            "name from the index — `cards_fts_au` fired, which nothing else here exercises",
        )
        checks.ok(fresh, "and the new name is indexed")

    # --- the migration survives a kill mid-way -----------------------------------------
    with isolated_home():
        capture_server.do_capture(capture_payload(6))
        store_path = str(files.inventory_dir() / "store.sqlite")
        conn = sqlite3.connect(store_path, isolation_level=None)
        try:
            conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('schema', '6')")
            conn.execute("DROP TRIGGER IF EXISTS cards_fts_ai")
            conn.execute("DROP TRIGGER IF EXISTS cards_fts_ad")
            conn.execute("DROP TRIGGER IF EXISTS cards_fts_au")
            conn.execute("DROP TABLE IF EXISTS cards_fts")
            for shadow in ("cards_fts_data", "cards_fts_idx", "cards_fts_docsize", "cards_fts_config"):
                conn.execute(f"DROP TABLE IF EXISTS {shadow}")
        finally:
            conn.close()

        conn = sqlite3.connect(store_path, isolation_level=None)
        raised = False
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("ALTER TABLE cards ADD COLUMN cids8_probe TEXT")
            raise RuntimeError("simulated -9 mid-migration")
        except RuntimeError:
            raised = True
            with contextlib.suppress(Exception):
                conn.execute("ROLLBACK")
        finally:
            conn.close()
        checks.ok(raised, "the simulated kill actually interrupted the migration")

        conn = sqlite3.connect(store_path)
        try:
            stamp = conn.execute("SELECT value FROM meta WHERE key = 'schema'").fetchone()
            columns = {r[1] for r in conn.execute("PRAGMA table_info(cards)").fetchall()}
        finally:
            conn.close()
        checks.equal(stamp, ("6",), "the schema stamp is untouched by the rolled-back attempt")
        checks.ok(
            "cids8_probe" not in columns,
            "and the ALTER did not survive either — the whole step is one transaction",
        )

        # The next open completes cleanly, exactly like every other numbered step here —
        # `do_search` itself is what triggers it, via `Store().read()` -> `db.connect`.
        capture_server.do_search("nothing in particular")
        conn = sqlite3.connect(store_path)
        try:
            stamp = conn.execute("SELECT value FROM meta WHERE key = 'schema'").fetchone()
            has_fts = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name = 'cards_fts'"
            ).fetchone()
        finally:
            conn.close()
        checks.equal(stamp, (str(db.SCHEMA_VERSION),), "and lands on the current schema")
        checks.ok(has_fts is not None, "with the search index built")


def check_inventory_box_route(checks: Checks) -> None:
    """D192/item 2: `GET /inventory/<box>` reads one box, never the store.

    THE PROOF IS `Rows.loaded_count`, NOT A TIMING. A wall-clock assertion is what
    a `.backup`-copy measurement is for, run by hand against
    the owner's real store; a harness test needs to be true on every machine and every CI
    runner, so it asserts what the route BUILT rather than how long it took. `Rows` already
    tracks this for exactly this reason (D88) — see `check_store_of_record` for the
    precedent.
    """
    checks.note("")
    checks.note("PER-BOX READ — server/capture_server.py:do_inventory_box (item 2)")

    with isolated_home():
        for at in range(1, 21):
            capture_server.do_capture(capture_payload(1, capture_id=f"a{at}", set_hint="sv9"))
        for at in range(1, 6):
            capture_server.do_capture(capture_payload(2, capture_id=f"b{at}", set_hint="sv9"))

        payload = capture_server.do_inventory_box(1)
        checks.equal(
            set(payload["cards"].keys()),
            {f"1/{n}" for n in range(1, 21)},
            "GET /inventory/1 returns exactly box 1's twenty cards",
        )
        checks.ok(
            all(row["box"] == 1 for row in payload["cards"].values()),
            "and every row decorates as box 1 — none of box 2's five leaked in",
        )

        after = Store().read()
        checks.ok(
            not after.inventory.cards.complete and after.inventory.cards.loaded_count <= 20,
            f"and it built {after.inventory.cards.loaded_count} card objects reading box 1 "
            "of a 25-card store, not the store's 25 — a fresh `Store().read()` proves the "
            "PREVIOUS read's session is gone and this is a clean instrument",
        )

        # An empty, never-captured box answers with nothing rather than refusing. Done
        # BEFORE the corruption below, which — once written — takes every box's read down
        # (see the note on that assertion), including this one.
        empty = capture_server.do_inventory_box(999)
        checks.equal(
            empty["cards"], {}, "box 999, never captured into, answers an empty map"
        )

        # VERIFIED AGAINST THE TREE, AND THE OPPOSITE OF WHAT THIS ITEM'S PLAYBOOK CLAIMED:
        # a record ANYWHERE that will not coerce still takes every box's read down, because
        # `_positions_in`'s own docstring says its refusal fires "ANYWHERE in the store" and
        # its NULL-column pass is a genuinely unscoped query — the same rule
        # `next_index`/`allocate_capture` have always had. `records_in`'s row-BUILDING query
        # (`self.cards.where(box=box)`) is box-scoped; its REFUSAL, inherited from
        # `_positions_in`, is not. `do_inventory_box`'s own docstring now carries the
        # correction; `_positions_in` itself is untouched (this item's own "Do not touch"
        # section), so this is named as an existing, inherited limitation rather than fixed
        # here. Done last in this check because it leaves the store corrupted.
        with Store().write() as snapshot:
            snapshot.inventory.cards["2/1"].box = "not-a-box"  # type: ignore[assignment]
        caught = checks.raises(
            master.BadPosition,
            lambda: capture_server.do_inventory_box(1),
            "and a record ANYWHERE with a non-coercible box still raises out of THIS route "
            "too, for every box asked about — `do_inventory` never hits this because it "
            "never calls `_positions_in`; a future item narrowing that refusal to the box "
            "asked about is named in the PR rather than attempted here",
        )
        checks.ok(
            caught is None or "2/1" in str(caught),
            "and the refusal names the corrupt record, exactly as `next_index` already does",
        )


def check_rows_scoped_after_full_load(checks: Checks) -> None:
    """D192/item 2: `where()`/`select()` cost what the index costs, even after this
    session's own `Rows` has been fully materialised. The mechanism is `store/rows.Rows`'s `__len__` own
    cost; this pins it so a later change to `Rows` cannot
    reopen it silently.
    """
    checks.note("")
    checks.note("ROWS SCOPED AFTER A FULL LOAD — store/rows.py (item 2)")

    with isolated_home():
        for at in range(1, 11):
            capture_server.do_capture(capture_payload(1, capture_id=f"a{at}", set_hint="sv9"))
        for at in range(1, 6):
            capture_server.do_capture(capture_payload(2, capture_id=f"b{at}", set_hint="sv9"))

        session = Store().read()
        before = sorted(card.key for card in session.inventory.cards.where(box=1))

        # Force the degrade condition: materialise every row in THIS session, the way
        # `to_payload()` does for `do_inventory` and the way any other handler that calls
        # `.values()`/`.items()` on `cards` would.
        session.inventory.to_payload()
        checks.ok(
            session.inventory.cards.complete,
            "the whole-store call set `_complete`, which is the condition this test exists "
            "to exercise",
        )

        after = sorted(card.key for card in session.inventory.cards.where(box=1))
        checks.equal(
            after, before,
            "and a scoped `where(box=1)` on the SAME session still returns exactly box 1's "
            "cards after a full load — correctness survives the degrade condition",
        )

        # THE PART THAT PROVES THE FIX, NOT JUST CORRECTNESS: a session that touched nothing
        # answers a scoped query with an empty `_touched` set, so the fallback's extra pass
        # costs nothing proportional to the store. A session that HAS written something is
        # exercised separately below.
        checks.equal(
            len(session.inventory.cards._touched), 0,
            "and this read-only session touched nothing, so `where()`'s post-source pass "
            "had nothing of the store's own size to scan — the loaded_count above already "
            "proves the source's index (not a loaded_dict scan) answered the query",
        )
        checks.ok(
            session.inventory.cards.loaded_count == 15,
            "loaded_count is 15 (all captured cards) because `to_payload()` forced the full "
            "load ABOVE — this number does not fall after the fix; what changes is that the "
            "SUBSEQUENT `where()` call above did not have to re-filter it by hand, which "
            "`_touched` being empty is what proves",
        )

        # --- a session that WRITES, then queries, must still see its own write -----------
        # VERIFIED AGAINST THE TREE, CORRECTING THE PLAYBOOK'S OWN SKETCH: `Card.key` is a
        # COMPUTED PROPERTY of `(box, index)` (`store/master.Card`'s `key`), so moving "2/1"
        # into box 1 while keeping its index at 1 makes its `.key` recompute to "1/1" —
        # colliding with box 1's own real card at index 1, which is why the playbook's
        # original sketch (assert `"2/1" in moved_in`) can never pass: nothing in `_loaded`
        # is ever keyed "2/1" once the mutation lands, and a live `move_card` (D83) never
        # reuses an index for exactly this reason — it always allocates a FRESH one in the
        # destination. Box 3 holds no card here, so moving into it at the same index (1)
        # exercises the same `_touched` mechanism with no collision.
        with Store().write() as snapshot:
            snapshot.inventory.cards.to_dict()  # force _complete inside the transaction too
            card = snapshot.inventory.cards["2/1"]
            card.box = 3  # move it into an EMPTY box's own index space, in memory, uncommitted
            snapshot.inventory.cards["2/1"] = card
            moved_in = sorted(c.key for c in snapshot.inventory.cards.where(box=3))
            checks.ok(
                "3/1" in moved_in,
                "and a row this transaction just wrote is found by a scoped query even "
                "though the source's own index still says box 2 — `_touched` is what "
                "catches it, not a re-scan of everything loaded",
            )
            moved_out = sorted(c.key for c in snapshot.inventory.cards.where(box=2))
            checks.ok(
                "3/1" not in moved_out and "2/1" not in moved_out,
                "and it no longer answers for box 2, which is the same `_touched` re-check "
                "the other direction",
            )

        # --- AN IN-PLACE MUTATION THAT NEVER GOES THROUGH `__setitem__` MUST STILL BE SEEN
        # --- BY A SAME-SESSION SCOPED QUERY, AFTER A FULL LOAD. `_touched` alone cannot prove
        # this — `store/master.py:set_state`, `record_identification` and
        # `store/submissions.py:release`/`attach_run` all write by mutating the object's
        # attributes directly, exactly as `Rows`'s own docstring documents as a supported
        # write path ("a caller that got an object back and mutated it is writing to the same
        # object the flush will read"). This is not hypothetical: `release()`'s in-place
        # `claim.state = STATE_RELEASED` broke a real same-session re-query
        # (`submission-selftest.py:case_resume_releases_only_its_own`) the first time this
        # fix was written to trust `_touched` alone, before `where()`/`select()` were
        # corrected to re-validate every candidate the source query returns against the LIVE
        # object rather than trusting either the source's stale row or `_touched`'s narrower
        # bookkeeping.
        with Store().write() as snapshot:
            snapshot.inventory.cards.to_dict()  # force _complete inside this transaction too
            card = snapshot.inventory.cards["1/1"]
            checks.ok(
                card.state == master.CAPTURED,
                "card 1/1 starts CAPTURED, the state `check_state`/`set_state`'s own indexed "
                "column reads before any mutation",
            )
            card.state = master.SOLD  # mutated IN PLACE, never reassigned through __setitem__
            still_captured = snapshot.inventory.cards.where(state=master.CAPTURED)
            checks.ok(
                "1/1" not in {c.key for c in still_captured},
                "and a same-session `where(state=CAPTURED)` no longer answers for it — the "
                "in-place mutation is not `_touched`, so this is proven only by re-validating "
                "the source's own candidates against the live object, not by trusting either "
                "side blindly",
            )
            # A ROW MUTATED IN PLACE INTO A NEW MATCH IS FOUND. `where` evaluates every
            # loaded row live, so `state=SOLD` answers for "1/1" although the source's own
            # index never held that value on disk. Pinned so a regression to trusting the
            # source's candidates alone goes red here.
            now_sold = snapshot.inventory.cards.where(state=master.SOLD)
            checks.ok(
                "1/1" in {c.key for c in now_sold},
                "and it DOES answer for its new state: a row mutated in place into a match "
                "the source's own index cannot see is still found",
            )


def check_inventory_recent_route(checks: Checks) -> None:
    """D192/item 2: `GET /inventory/recent` — Home's hero deck — is a lean top-K read over
    `Inventory.newest_captured`/`Rows.top`, in `do_inventory`'s own per-card shape, and it
    skips exactly what `Home.tsx:deckFromCards` would skip: unidentified, photo-less and
    departed cards.
    """
    checks.note("")
    checks.note("RECENT DECK ROUTE — server/capture_server.py:do_inventory_recent (item 2)")

    with isolated_home():
        for at in range(1, 6):
            capture_server.do_capture(capture_payload(1, capture_id=f"a{at}", set_hint="sv9"))
        with Store().write() as snapshot:
            # Name three of the five (identification's own field, never a capture claim) so
            # the deck has real candidates — `do_capture` alone never sets `name`.
            for n in (1, 2, 3):
                card = snapshot.inventory.cards[f"1/{n}"]
                card.name = f"Card {n}"
                snapshot.inventory.cards[f"1/{n}"] = card

        payload = capture_server.do_inventory_recent(2)
        checks.equal(
            sorted(payload["cards"].keys()), ["1/2", "1/3"],
            "the two NEWEST named, photographed, on-hand cards — captured in order 1..5, so "
            "3 and 2 are the newest of the three that were named",
        )
        checks.equal(
            payload["cards"]["1/3"]["name"], "Card 3",
            "and the full per-card shape rides along — not a narrower DTO — because "
            "`deckFromCards` reads `name`, `number_display` and the finish claim, none of "
            "which a `{key, box, index, cid, name}` shape could carry",
        )

        # A sold card is skipped even though it is otherwise the newest named candidate.
        capture_server.do_mark_sold(1, 3, {})
        after_sale = capture_server.do_inventory_recent(2)
        checks.equal(
            sorted(after_sale["cards"].keys()), ["1/1", "1/2"],
            "and a sold card never reaches the deck — `deckFromCards`'s own `gone` filter, "
            "restated server-side so a sale does not have to be re-filtered by every screen "
            "that reads this route",
        )

        empty = capture_server.do_inventory_recent(5)
        checks.equal(
            sorted(empty["cards"].keys()), ["1/1", "1/2"],
            "an unnamed or unidentified capture (1/4, 1/5) never displaces a real card, "
            "however deep the deck asks",
        )

def check_inventory_history_route(checks: Checks) -> None:
    """`GET /inventory/history` answers every card's `captured_at`, `box` and `state`, never
    a top-K: Home's history ribbon clusters sittings from it, and a deck-sized sample reads
    any store as one sitting."""
    checks.note("")
    checks.note("HISTORY ROUTE — server/capture_server.py:do_inventory_history")
    with isolated_home():
        for at in range(1, 7):
            capture_server.do_capture(capture_payload(1, capture_id=f"h{at}", set_hint="sv9"))
        cards = capture_server.do_inventory_history()["cards"]
        checks.equal(len(cards), 6, "every captured card, not a deck-sized sample")
        checks.equal(
            sorted(cards["1/1"]), ["box", "captured_at", "state"],
            "three fields a card and nothing else",
        )

# -------------------------------------------------------------------------- place block


def check_box_names(checks: Checks) -> None:
    """A name is how a box is ADDRESSED now, so it is unique, it is logged, and it can stand
    in for a number nobody wants to type.

    ITS OWN `isolated_home`, this file's own repeated lesson. Every case here writes boxes,
    and `check_box_routes_and_search` counts them; the mass-select block and the starvation
    block were both first written into somebody else's fixture and both failed on the
    fixture rather than on the code.

    WHAT CHANGED AND WHY IT NEEDED COVERAGE. `Box.name` existed from D20 and nothing checked
    it — right while the NUMBER was the identifier, because a duplicate name cost a confusing
    row and nothing else. The capture screen now finds a box by name, which makes a second
    "commons" an ambiguous physical address, and makes a rename relabel every card in the box
    the way a moved divider relabels every card behind it. `server/capture_server.py` had
    recorded the missing event as a known gap in `do_put_box`'s own docstring, with the right
    reason for leaving it — "a name is a label, not a claim the pipeline spends money
    against". That sentence is what stopped being true.
    """
    checks.note("")
    checks.note("BOX NAMES — store/master.py, server/capture_server.py")

    with isolated_home():
        # --- a name alone is a complete creation -----------------------------------------
        named = capture_server.do_create_box({"name": "ME01 commons"})[1]
        checks.equal(
            [named["box"], named["name"]],
            [1, "ME01 commons"],
            "POST /boxes with a NAME and no number takes the lowest free number — the "
            "owner's ask, in their words: the primary key is something they do not care "
            "about, and the label is what they work in",
        )
        second = capture_server.do_create_box({"name": "mega pulls"})[1]
        checks.equal(
            second["box"],
            2,
            "and the next one takes the next free number rather than a high-water mark: a "
            "box number names a physical object nobody types any more, so there is no gap "
            "for a mark to protect",
        )
        refusal(
            checks,
            lambda: capture_server.do_create_box({}),
            "box_or_name_required",
            "a body with neither refuses: it does not describe a box, and inventing both "
            "halves of an object nobody named is how a registry fills with rows no one meant",
        )

        # --- uniqueness, folded and stripped ---------------------------------------------
        # THE STORE'S EXCEPTION, NOT THE ROUTE'S CODE, and the difference is the one this
        # file already draws for `BoxClosed`: `store/master.py` raises and `_dispatch` is
        # what turns it into `name_taken`, so an in-process call asserts the rule while the
        # socket case asserts what a client is told. The rule is the half that protects the
        # data, and it is the half that would be lost if the check moved into the route.
        checks.raises(
            master.BoxNameTaken,
            lambda: capture_server.do_create_box({"name": "  ME01 Commons "}),
            "a duplicate name refuses even folded and padded — `Commons` and `commons ` are "
            "one box to a person at a shelf, and a store that took both would enforce a "
            "rule nobody can see",
        )
        checks.equal(
            len(capture_server.do_boxes()["boxes"]),
            2,
            "and the refusal wrote nothing: two boxes, not three",
        )

        # --- a rename logs both names ----------------------------------------------------
        before = len(Store().history())
        capture_server.do_put_box(1, {"name": "ME01 commons, tray 2"})
        renamed = [e for e in Store().history() if e["event"] == "box_renamed"]
        checks.equal(
            [len(renamed), renamed[-1]["name_from"], renamed[-1]["name_to"]],
            [1, "ME01 commons", "ME01 commons, tray 2"],
            "a rename appends `box_renamed` carrying BOTH names — `resectioned`'s sibling "
            "one scale up, because the label a rename moves is every card in the box",
        )
        checks.equal(
            len(Store().history()) - before,
            1,
            "and exactly one event: the rename, not a rename plus a box_created from the "
            "`ensure_box` the route calls on its way to it",
        )

        # --- a no-op rename is not a rename ----------------------------------------------
        steady = len(Store().history())
        capture_server.do_put_box(1, {"name": "ME01 commons, tray 2"})
        checks.equal(
            len(Store().history()),
            steady,
            "re-sending a box its own name writes NO event — a log line for a request that "
            "changed nothing is a rename that never happened, and history is read as the "
            "record of what did",
        )
        checks.equal(
            capture_server.do_put_box(1, {"name": "ME01 commons, tray 2"})["name"],
            "ME01 commons, tray 2",
            "and it does not conflict with ITSELF: the uniqueness check skips the box being "
            "written, which is the shape a screen that PUTs its whole form back produces",
        )

        # --- clearing stores the default name ---------------------------------------------
        # A box is shown by its name only (D259), so a clear cannot
        # leave it with none: it stores the default `Box <count+1>`, the orchestrator's call
        # on the locating review, 2026-09-24 — ANOTHER ORCHESTRATOR CALL, 2026-09-24, AMENDS
        # THE COUNT: the box being cleared is already in the registry when this runs, and its
        # own row does not count toward `<count+1>` any more than its own name counts as
        # taken. One box stands beside it here, so the default is `Box 2`, not `Box 3`.
        cleared = capture_server.do_put_box(1, {"name": None})
        checks.equal(
            cleared["name"],
            "Box 2",
            "`{name: null}` clears the name — the shape a cleared text field sends, and a "
            "legitimate edit rather than a refusal. One OTHER box stands (`mega pulls`), so "
            "it stores `Box 2`: the box being cleared does not count itself",
        )
        cleared_event = [e for e in Store().history() if e["event"] == "box_renamed"][-1]
        checks.equal(
            [cleared_event["name_from"], cleared_event.get("name_to")],
            ["ME01 commons, tray 2", "Box 2"],
            "and the clear is logged like any other rename, with both names on the line: "
            "after this write there is no other evidence the box was ever called anything, "
            "so what the line carries is the whole record",
        )
        freed = capture_server.do_create_box({"name": "ME01 commons, tray 2"})[1]
        checks.equal(
            freed["box"],
            3,
            "and the freed name is claimable again — uniqueness is over what is CURRENTLY "
            "held, not over every name a store has ever seen",
        )

        # --- the allocator sees cards, not just the registry -----------------------------
        with Store().write() as snapshot:
            checks.equal(
                snapshot.inventory.next_box_number(),
                4,
                "next_box_number skips every number the registry holds",
            )
        for _ in range(2):
            capture_server.do_capture(capture_payload(7))
        with Store().write() as snapshot:
            # The pre-D20 shape: a box that holds cards and has no registry entry. It cannot
            # be reached through the front door any more, which is exactly why it is built by
            # hand — every box filled before the registry existed is in it.
            del snapshot.inventory.boxes["7"]
        with Store().write() as snapshot:
            taken = snapshot.inventory.next_box_number()
        checks.equal(
            taken,
            4,
            "and it skips a number held by CARDS with no registry entry — handing that one "
            "out again would put two boxes' photographs in one directory",
        )


def check_box_claims(checks: Checks) -> None:
    """PUT /inventory/<box> — the box-level claim apply, the owner's ask of 2026-08-23.

    THE CARD ROUTE ONE SEGMENT BROADER: same `PUT_FIELDS` vocabulary, same decoders, same
    per-game validators, same `corrected` line — applied to every eligible card in a box,
    all-or-nothing (D29's group shape). What this section works hardest is the boundary:
    a refused call changes NOTHING, terminal records are skipped and named, and a mixed
    box (legal, D21) is judged per card against each card's own game unless this call
    sets one.
    """
    checks.note("")
    checks.note("BOX-LEVEL CLAIMS — PUT /inventory/<box>")

    with isolated_home():
        for _i in range(1, 6):
            capture_server.do_capture(capture_payload(6))
        with Store().write() as snapshot:
            snapshot.inventory.set_state("6/2", master.IDENTIFIED)
            snapshot.inventory.set_state("6/4", master.SOLD)
            snapshot.inventory.retire("6/5", "damaged")
            # A mixed box, which D21 makes legal — the case the per-game judging exists for.
            snapshot.inventory.cards["6/3"].game = "riftbound"

        refusal(
            checks,
            lambda: capture_server.do_put_box_claims(6, {}),
            "nothing_to_apply",
            "a bulk apply carrying no claim refuses — an empty sweep over a box is a "
            "client error, not a no-op success",
        )
        refusal(
            checks,
            lambda: capture_server.do_put_box_claims(6, {"state": "sold"}),
            "field_not_settable",
            "claims ONLY: state has its own routes and its own rulings, and the "
            "vocabulary check keeps it out of this body",
        )
        refusal(
            checks,
            lambda: capture_server.do_put_box_claims(99, {"set_hint": "sv9"}),
            "box_not_found",
            "an unknown box refuses",
        )
        refusal(
            checks,
            lambda: capture_server.do_put_box_claims(6, {"game": "yugioh"}),
            "game_invalid",
            "and an unregistered game refuses through the same decoder the card route uses",
        )

        # The mixed-box refusal: `reverse_holo` is Pokemon's cell and not Riftbound's, the
        # body names no game, so the claim is judged against EACH card's own game — and
        # one rejection refuses the WHOLE call, naming the card.
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_put_box_claims(6, {"variant": "reverse_holo"}),
            "a claim one card's game does not stock refuses the whole call — a sweep that "
            "corrected only the cards that fit leaves a box nobody asked for",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None), "claim_not_stocked_by_game", "in its own code"
            )
            checks.ok(
                "Section 1, Card 3" in str(caught) and "card 3:" not in str(caught),
                "naming the card whose game rejected it, in the SAME SHAPE a card row "
                "reads — Section n, Card m, never the bare store index "
                "(D259)",
                f"message was: {caught}",
            )
            # THE LISTED CARD MATCHES ITS OWN LABEL — a second code path, `said_place`,
            # answers the same numbers for the same index.
            checks.equal(
                join.said_place(Store().read().inventory, 6, 3),
                "Box 1, Section 1, Card 3",
                "cross-checked against `said_place` for the same index",
            )
        checks.ok(
            all(
                c.metadata_finish is None
                for c in Store().read().inventory.cards.values()
            ),
            "and the refusal changed nothing on any card",
        )

        # The same claim WITH the game set: judged once against the game THIS call sets
        # (`do_put_card`'s judged_against rule at box scale), applied to every eligible
        # card, terminal records skipped and named.
        body = capture_server.do_put_box_claims(
            6, {"game": "pokemon", "variant": "reverse_holo", "set_hint": "sv9"}
        )
        checks.equal(
            (body["eligible"], body["applied"], body["skipped_terminal"]),
            (3, 3, 2),
            "the receipt counts what was eligible, what moved, and what was left alone",
        )
        checks.equal(
            body["skipped"],
            [{"index": 4, "state": "sold"}, {"index": 5, "state": "retired"}],
            "and NAMES the skipped terminal records — their record is history (D10, D26), "
            "and a bulk sweep is exactly the indiscriminate write they deserve protection "
            "from; the card route stays the deliberate one-position door",
        )
        after = Store().read().inventory
        # A LIST ON THE RECORD, and the list is the point rather than a spelling change.
        # `store/master.py:Card.metadata_finish` is a list because `to_payload` calls
        # `asdict` and JSON has to round-trip it unchanged; the two frozen carriers
        # downstream (`sidecar.Capture`, `join.IdentifiedCard`) hold tuples for the opposite
        # reason, and this test asserts both shapes in their own places on purpose.
        checks.ok(
            all(
                (after.cards[f"6/{i}"].game, after.cards[f"6/{i}"].metadata_finish)
                == ("pokemon", ["reverse_holo"])
                for i in (1, 2, 3)
            ),
            "every eligible card carries the claims now — including the one whose game "
            "this same call corrected, judged against the game as set",
        )
        checks.ok(
            after.cards["6/4"].metadata_finish is None
            and after.cards["6/5"].metadata_finish is None,
            "and the sold and retired records are untouched",
        )
        sidecar_now = json.loads(
            capture_server.sidecar_path(photo_of(6, 1)).read_text("utf-8")
        )
        checks.ok(
            sidecar_now.get("variant") == ["reverse_holo"]
            and sidecar_now.get("game") == "pokemon",
            "the sidecar is rewritten for a changed card — the correction has to reach "
            "the file `identify` actually reads, or D3 rung 1 never hears it",
            f"sidecar was: {sidecar_now}",
        )
        bulk_lines = [
            e
            for e in Store().history()
            if e.get("event") == capture_server.CORRECTED and "bulk" in e
        ]
        checks.ok(
            len(bulk_lines) == 3
            and all(e.get("bulk") == 3 and "changed" in e for e in bulk_lines),
            "one `corrected` line per changed position, tagged `bulk` with the sweep's "
            "size — D29's group tag, so the log tells one sweep from three hand edits",
            f"lines were: {bulk_lines!r}",
        )
        second = capture_server.do_put_box_claims(
            6, {"game": "pokemon", "variant": "reverse_holo", "set_hint": "sv9"}
        )
        checks.ok(
            second["applied"] == 0 and second["unchanged"] == 3,
            "restating the same claims applies nothing — a no-op writes no history and "
            "churns no sidecars",
        )
        checks.equal(
            len(
                [
                    e
                    for e in Store().history()
                    if e.get("event") == capture_server.CORRECTED and "bulk" in e
                ]
            ),
            3,
            "and the log gained no new lines for it",
        )
        checks.ok(
            after.cards["6/2"].state == master.IDENTIFIED
            and after.cards["6/4"].state == master.SOLD,
            "no card moved state — this route corrects claims and nothing else",
        )

    # --- `indices`: the owner's mass-select, 2026-08-23 ------------------------------------
    # ITS OWN HOME, deliberately. The block above counts history lines over a box it built
    # card by card, so a sweep run against that same fixture moves numbers it asserts —
    # which is how this section first failed. A selection test needs its own box more than
    # it needs the mixed-game one above.
    #
    # ON THE ROUTE RATHER THAN AS N CARD CALLS. A client loop over `PUT /inventory/<box>/
    # <index>` would be N requests with N chances to half-apply — the seventh refusing on a
    # per-game vocabulary while the first six are already written, which is exactly the
    # partial sweep this route's all-or-nothing exists to prevent.
    with isolated_home():
        for _ in range(5):
            capture_server.do_capture(capture_payload(8))

        refusal(
            checks,
            lambda: capture_server.do_put_box_claims(8, {"indices": [], "set_hint": "x"}),
            "indices_invalid",
            "AN EMPTY SELECTION REFUSES RATHER THAN MEANING THE WHOLE BOX — the two read "
            "alike and are opposite intents, and an emptied selection widening to every "
            "card in the box is the accident worth a refusal of its own",
        )
        refusal(
            checks,
            lambda: capture_server.do_put_box_claims(8, {"indices": 3, "set_hint": "x"}),
            "indices_invalid",
            "and a bare number is not a selection",
        )
        refusal(
            checks,
            lambda: capture_server.do_put_box_claims(8, {"indices": [1, 0], "set_hint": "x"}),
            "indices_invalid",
            "and neither is a card number below one",
        )

        def hints():
            return [
                Store().read().inventory.cards[f"8/{i}"].set_hint for i in range(1, 6)
            ]
        before = hints()
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_put_box_claims(
                8, {"indices": [1, 99], "set_hint": "swept"}
            ),
            "a selection naming a card the box does not hold refuses the WHOLE call — a "
            "selection is a statement about a set, and an operator wrong about one member "
            "may be wrong about which box they are looking at",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None), "card_not_found", "in its own code"
            )
            where = join.said_place(Store().read().inventory, 8)
            checks.ok(
                # D196 (UX-208's carried refusal-leak item): the raw "box/index" key used
                # to ride the message ("holds no card at 3, 7"). `said_place` names the
                # box the same way a card row does, and `place_within_box` never spells
                # the missing index as a store key.
                where in str(caught) and "8/99" not in str(caught),
                "and the message names the box the said way, never the raw box/index "
                "key",
                f"message was: {caught}",
            )
            checks.ok(
                # The PR 2 integration review: `place_within_box` fell back to "card 99" for
                # an index the box does not hold, the raw store index again. A card that is
                # not here has no place to name, so the count is said instead.
                "1 of the cards you named is not in" in str(caught) and "99" not in str(caught),
                "and a card the box does not hold is counted plainly, with no raw index",
                f"message was: {caught}",
            )
        checks.equal(
            hints(),
            before,
            "and it wrote NOTHING on the way to that refusal — card 1 was a valid member "
            "and is untouched, which is the all-or-nothing this route promises everywhere",
        )

        narrowed = capture_server.do_put_box_claims(
            8, {"indices": [1, 3], "set_hint": "picked"}
        )
        narrowed = narrowed[-1] if isinstance(narrowed, tuple) else narrowed
        checks.equal(
            [narrowed["eligible"], narrowed["applied"]],
            [2, 2],
            "a selection narrows the sweep to exactly its members — two of the box's five "
            "cards, not the box",
        )
        checks.equal(
            hints(),
            ["picked", None, "picked", None, None],
            "and card 2 — eligible, in the box, simply NOT SELECTED — is untouched, which "
            "is the whole difference between a mass-select and a bulk apply",
        )

        whole = capture_server.do_put_box_claims(8, {"set_hint": "everything"})
        whole = whole[-1] if isinstance(whole, tuple) else whole
        checks.equal(
            whole["eligible"],
            5,
            "OMITTING `indices` still means the whole box — the compatibility guarantee "
            "that makes the selection strictly additive to the route that shipped without it",
        )


def check_place_neighbors(checks: Checks) -> None:
    """D58's digital half on the wire: `neighbors` and `section_gaps` in the place block.

    `Card 17` IS THE SEVENTEENTH CARD YOU CAN COUNT, WHICH IS D58 AND IS THE REVERSE OF WHAT
    THIS PARAGRAPH SAID UNTIL D92. It read "the seventeenth SLOT, not the seventeenth card
    you can count", which was true when D58 wrote it and was made false on 2026-08-30 by the
    entry that answered D58. Every sale and every retirement leaves a permanent gap in the
    INDEX (D10) and the label closes over it, so what diverges behind a gap is the label and
    the store key — not the label and the hand. D58's ruling still stands and its reason
    moved: a located place block carries the nearest NON-TERMINAL records on either side, and
    how many permanent holes this card's own section holds. Asserted on `GET /inventory`'s
    rows — the route the app polls — because the block is wire-only and the wire is the only
    place the claim exists.

    BOTH NUMBERS RIDE EACH NEIGHBOUR SINCE D92, and the assertions below pin them together on
    purpose. This fixture's box already separates them — a sale at 2 and a retirement at 4
    make index 3 the second card and index 5 the third — so an implementation that sent the
    key twice, or the count twice, cannot pass.

    THE CONSTRUCTION UNDER TEST IS "RECORDS, NOT INDICES", read from three sides. A
    terminal record is skipped as a landmark and counted as a hole — one ruling, two
    directions. An unallocated index is neither: no record means no card was ever there,
    so a declared section running past the fill adds nothing to the count. And a pooled
    record is skipped BY RULING rather than by state (D24) — it has no slot to leave a
    hole in, whatever state it is in.

    THE DEGRADE CASE IS THE ONE THAT MATTERS, and it is this section's half of the
    corrupt-record case `check_server_routes` arms. "Between Mantine and Thievul" is a
    position claim somebody counts slots against, so a walk that skipped an unreadable
    record would keep the sentence rendering while possibly naming the wrong neighbor —
    the exact failure a position label may never cause, one hop removed. The decoration
    therefore degrades WHOLE and STORE-WIDE, and costs nobody their label.
    """
    checks.note("")
    checks.note("PLACE BLOCK — neighbors and section gaps (D58), server/capture_server.py")

    with isolated_home():
        # --- a gapped box tells the truth ------------------------------------------------
        # Five captures, then a sale at 2 and a retirement at 4 — both through their own
        # routes, so the states are the ones the store writes and not hand-set strings.
        # Card 1 gets a name on the store directly: `name` is an identification result,
        # not a capture claim — it is deliberately absent from `PUT_FIELDS` — so there is
        # no route that sets it by hand, and the join that would is not in this fixture.
        for _ in range(5):
            capture_server.do_capture(capture_payload(4))
        with Store().write() as snapshot:
            snapshot.inventory.cards["4/1"].name = "Mantine"
        capture_server.do_mark_sold(4, 2, {})
        capture_server.do_retire(4, 4, {"reason": "damaged"})

        rows = capture_server.do_inventory()["cards"]
        checks.equal(
            rows["4/3"]["place"]["neighbors"],
            {
                "prev": {"index": 1, "slot": 1, "name": "Mantine", "unread": 0},
                "next": {"index": 5, "slot": 3, "name": None, "unread": 1},
            },
            "a card between two gaps names the nearest NON-TERMINAL record — the sold card "
            "at 2 and the retired card at 4 are skipped, never named: a departed card cannot "
            "be the thing you count from (D58) — and each side carries BOTH numbers (D92): "
            "the store key and D58's count, which this box has already pulled apart. `next` "
            "IS THE UNREAD CARD AT 5, `unread: 1`: an unread card counts as a neighbor (D260, "
            "LOC-28)",
        )
        checks.equal(
            rows["4/3"]["place"]["section_gaps"],
            2,
            "and the same two records are COUNTED as this section's holes — skipped as a "
            "landmark and counted as a gap are one ruling read from two sides",
        )
        checks.equal(
            rows["4/1"]["place"]["neighbors"]["prev"],
            None,
            "the first card in a box answers `prev: null` — the box's edge, never a guess "
            "past it",
        )
        checks.equal(
            rows["4/5"]["place"]["neighbors"]["next"],
            None,
            "and the newest answers `next: null` the same way",
        )
        checks.equal(
            rows["4/5"]["place"]["neighbors"]["prev"],
            {"index": 3, "slot": 2, "name": None, "unread": 1},
            "AN UNREAD CARD IS A NEIGHBOUR (D260, LOC-28): the card next to this one is the "
            "neighbor, read or not, said as `an unread card`, never `with 1 unidentified "
            "card in between`. THE "
            "TWO NUMBERS STILL DIVERGE AND ARE STILL PINNED TOGETHER (D92): the card at "
            "index 3 is the SECOND card in this box",
        )
        checks.equal(
            [
                rows["4/3"]["place"]["neighbors"]["prev"]["unread"],
                rows["4/3"]["place"]["section_gaps"],
            ],
            [0, 2],
            "and `unread` COUNTS ON-HAND CARDS AND NEVER THE DEPARTED ONES: card 3 reaches "
            "Mantine across a sold record at 2 and answers 0, while the same two departed "
            "records are its section's gaps. The box closed up over them (D58), so they lie "
            "between nothing",
        )

        # --- a sold card is not a landmark, and the sale is what proves it ---------------
        # THE OWNER ASKED THIS QUESTION OF A REAL SCREEN (2026-09-07) — "sold cards should
        # anyway not be in the before/after" — reading a `#270` in the ladder as a departed
        # card that had leaked in. It had not: the ladder had never named one, and the
        # figure was an unnamed LIVE card, which is what D260 above is about. This case is
        # the claim they could not see, made in the one place it can be seen: a card is
        # named as a landmark, then SOLD through its own route, and the neighbor that used
        # to name it must move to the next named card rather than keep pointing at it.
        capture_server.do_capture(capture_payload(6))
        capture_server.do_capture(capture_payload(6))
        capture_server.do_capture(capture_payload(6))
        with Store().write() as snapshot:
            snapshot.inventory.cards["6/1"].name = "Mantine"
            snapshot.inventory.cards["6/2"].name = "Thievul"
        before_sale = capture_server.do_inventory()["cards"]["6/3"]["place"]["neighbors"]
        checks.equal(
            before_sale["prev"],
            {"index": 2, "slot": 2, "name": "Thievul", "unread": 0},
            "with every card on hand, card 3's `prev` is the card next to it — the "
            "landmark this case is about to sell",
        )
        capture_server.do_mark_sold(6, 2, {})
        checks.equal(
            capture_server.do_inventory()["cards"]["6/3"]["place"]["neighbors"]["prev"],
            {"index": 1, "slot": 1, "name": "Mantine", "unread": 0},
            "AND SELLING IT MOVES THE LANDMARK RATHER THAN NAMING A SOLD CARD. Thievul is "
            "not in that drawer any more, so a sentence naming him sends a hand to a slot "
            "the card has left (D58) — the walk names Mantine, who has closed up to be "
            "the card in front (D58), and `unread` stays 0 because a departed card lies "
            "between nothing at all",
        )

        # --- a run of unread cards is one neighbor, with its count ----------------------
        # Box 8: Mantine, then three cards nothing has named, then this card, then Thievul.
        # The owner's words for the run are "N unread cards", so `unread` is the length of the
        # run, counted from the neighbor outward to the next named card.
        for _ in range(6):
            capture_server.do_capture(capture_payload(8))
        with Store().write() as snapshot:
            snapshot.inventory.cards["8/1"].name = "Mantine"
            snapshot.inventory.cards["8/5"].name = "Charizard"
            snapshot.inventory.cards["8/6"].name = "Thievul"
        run = capture_server.do_inventory()["cards"]["8/5"]["place"]["neighbors"]
        checks.equal(
            run,
            {
                "prev": {"index": 4, "slot": 4, "name": None, "unread": 3},
                "next": {"index": 6, "slot": 6, "name": "Thievul", "unread": 0},
            },
            "THREE UNREAD CARDS IN A ROW ARE THE NEIGHBOUR TOWARD THE BACK, SAID AS `3 unread "
            "cards`: `prev` is the adjacent card, and `unread: 3` is the run up to Mantine",
        )
        checks.equal(
            capture_server.do_inventory()["cards"]["8/2"]["place"]["neighbors"]["next"],
            {"index": 3, "slot": 3, "name": None, "unread": 2},
            "and the run is counted from the neighbor outward, not from the box's start: "
            "card 2's front side holds two unread cards before Charizard",
        )

        # --- a divider typed ahead of the fill takes the captures ---------------------------
        # The owner's ruling, 2026-09-26 (D10): a section is where captures go once it exists.
        # So a divider declared far past the fill, `[1, 51]` on an empty box, is an empty last
        # section, and every capture goes INTO it. Section 1 stays empty. `section_gaps`
        # still counts terminal RECORDS only, so the sold card is the one gap.
        capture_server.do_create_box({"box": 5, "sections": [1, 51]})
        for _ in range(5):
            capture_server.do_capture(capture_payload(5))
        capture_server.do_mark_sold(5, 2, {})
        place = capture_server.do_inventory()["cards"]["5/3"]["place"]
        checks.equal(
            (place["section"], place["slot"]),
            (2, 2),
            "a divider typed ahead of the fill takes the captures: card 3 stands in section 2, "
            "as its second card once card 2 has sold (D58)",
        )
        checks.equal(
            [
                d["count"]
                for b in capture_server.do_boxes()["boxes"] if b["box"] == 5
                for d in b["sections_detail"]
            ],
            [0, 4],
            "and section 1 holds nothing: no capture went in front of the typed divider",
        )
        checks.equal(
            place["section_gaps"],
            1,
            "and an index with no record adds NOTHING to the gap count: only the sold record "
            "at 2 is a gap",
        )

        # --- an unallocated tail is not a gap --------------------------------------------
        # The same divider far past the fill, TYPED AFTER THE CAPTURES: section 1 of box 9
        # runs to index 50 while the box holds five cards. `section_gaps` counts terminal
        # RECORDS, not unoccupied indices — that an empty tail adds nothing is the
        # CONSTRUCTION, not a bounds check, and this is the box that would catch the bounds
        # check creeping back in.
        capture_server.do_create_box({"box": 9})
        for _ in range(5):
            capture_server.do_capture(capture_payload(9))
        capture_server.do_put_box(9, {"sections": [1, 51]})
        capture_server.do_mark_sold(9, 2, {})
        place = capture_server.do_inventory()["cards"]["9/3"]["place"]
        # 49, ONE DEPARTED CARD AND NOT A LOST PLAN. The divider is declared at index 51 and
        # the box has sold one card, so it stands in front of the FIFTIETH card rather than
        # the fifty-first slot. `Position._divider` keeps the other 45 slots counting for
        # one card each.
        checks.equal(
            place["section_end"],
            49,
            "a divider typed past the fill still carries its unfilled slots — the block says "
            "the section ends at 49, one short of the declared 50, because one card has left "
            "the box in front of it (D58)",
        )
        checks.equal(
            place["section_gaps"],
            1,
            "and the 45 unallocated indices behind it add NOTHING to the gap count: an "
            "index with no record is a card that was never captured, not a hole where one "
            "used to be — only the sold record at 2 is a gap",
        )

        # --- pooled: no section is not "no holes" ----------------------------------------
        # A code card captured into the same box burns index 6 as a KEY — the photo and
        # sidecar are named after it — but it has no slot, so its block carries the pooled
        # nulls and the located cards' sentences never mention it.
        capture_server.do_capture(capture_payload(4, game="pokemon_code"))
        # NAMED, AND THAT IS LOAD-BEARING SINCE D260. The walk now passes over an unnamed
        # card as well as a pooled one, so an unnamed code card would be skipped for either
        # reason and the case below could no longer tell the two rulings apart. Named, the
        # only thing keeping it out of card 5's sentence is D24.
        with Store().write() as snapshot:
            snapshot.inventory.cards["4/6"].name = "Rare Candy"
        pooled = capture_server.do_inventory()["cards"]["4/6"]["place"]
        checks.ok(
            not pooled["located"],
            "a pokemon_code card's place block answers located: false (D24)",
        )
        checks.equal(
            [pooled["neighbors"], pooled["section_gaps"]],
            [None, None],
            "and its `neighbors` and `section_gaps` are both null — NULL AND NOT ZERO, "
            "because zero would claim a countable section with no holes, and 'no section "
            "at all' is a different fact from 'no holes in it'",
        )
        # Retired, so that being skipped by RULING is distinguishable from being skipped
        # by state: a terminal pooled record is what a state-only walk would count.
        capture_server.do_retire(4, 6, {"reason": "given_away"})
        rows = capture_server.do_inventory()["cards"]
        checks.equal(
            rows["4/5"]["place"]["neighbors"]["next"],
            None,
            "a pooled record is never named as anyone's neighbor — card 5's `next` is "
            "still the box's edge, not the code card whose index happens to be 6",
        )
        checks.equal(
            rows["4/3"]["place"]["section_gaps"],
            2,
            "and never counted as anyone's gap, even retired: it is skipped by RULING, "
            "not by state — a card with no slot cannot leave a hole in one (D24)",
        )

        # --- the degrade rule: whole, store-wide, and never a guess ----------------------
        # The other half of the corrupt-record case `check_server_routes` arms. The walk
        # reads every record's own `box` and `index`, so it is armed here in a THIRD box —
        # the store-wide claim is the claim, and a same-box corruption could not test it.
        capture_server.do_capture(capture_payload(7))
        intact = capture_server.do_inventory()["cards"]["4/3"]["place"]
        with Store().write() as snapshot:
            snapshot.inventory.cards["7/1"].box = "seven"
        rows = capture_server.do_inventory()["cards"]
        degraded = rows["4/3"]["place"]
        checks.equal(
            [degraded["neighbors"], degraded["section_gaps"]],
            [None, None],
            "one record whose box will not coerce nulls the decoration for a card in a "
            "DIFFERENT box: skipping the unreadable record would keep the sentence "
            "rendering while possibly naming the wrong neighbor, and 'between X and Y' "
            "is a position claim somebody counts slots against",
        )
        checks.equal(
            [rows["5/3"]["place"]["neighbors"], rows["5/3"]["place"]["section_gaps"]],
            [None, None],
            "and the degrade is STORE-WIDE, not per-box — box 5 loses its sentences to "
            "box 7's record too, because a walk that cannot read one record cannot vouch "
            "for any neighbor it names anywhere",
        )
        # THE LABEL NOW DEGRADES WITH THE DECORATION AND IT USED NOT TO, which is the one
        # place D58 is visible in this file's degrade story and the reversal of what this
        # case asserted. It required the label, section, card and section_start to survive
        # a corrupt record in a DIFFERENT box, on the ground that "a label needs only this
        # record's own two integers and the layout". Both halves of that ground are gone:
        # the number is now a count of the cards on hand in this box, so it needs the walk,
        # and the walk is what the corrupt record broke. `located` is the one field that
        # survives, because whether this game has slots at all is a registry question and
        # not a counting one.
        checks.equal(
            [
                degraded["located"],
                degraded["label"],
                degraded["section"],
                degraded["card"],
                degraded["section_start"],
            ],
            [True, None, None, None, None],
            "the label and every number drawn from it degrade WITH the walk (D58): they "
            "count the cards in the box, and one record in the store could not be counted",
        )
        checks.ok(
            intact["label"] is not None and intact["card"] is not None,
            "where the intact read a moment earlier answered all of them — so this is the "
            "walk failing, not the box being unlabellable",
        )
        # `section_end` WAS IN THAT LIST AND CAME OUT ON 2026-08-29, which is the one place
        # deleting the 25-card default is visible in this file's degrade story. Box 4
        # declares no layout, so it used to get a 25-card window that needed no count at all
        # and survived anything; it is ONE section now, and one section's end IS the box's
        # end — `_denominator`, the number that degrades. So this field follows the count and
        # the four above do not, and that split is the assertion rather than a caveat on it:
        # a label is built from this record's own two integers and the layout, and a number
        # derived from a whole-store scan cannot honestly outlive the scan.
        checks.equal(
            [degraded["section_end"], degraded["box_total"]],
            [None, 0],
            "and `section_end` degrades WITH the denominator, because an undeclared box's "
            "one section ends where the box does — the same degrade `fraction` takes, and "
            "not the label's",
        )
        # [6, 6] UNTIL D58 AND [3, 3] SINCE. Box 4 holds six records: two terminal (the two
        # this section already counts as its gaps), one pooled code card that never had a
        # slot at all (D24), and three cards. The fill was the denominator and the cards on
        # hand are — which is D58's arithmetic seen from the box rather than from a card,
        # and it counts BOTH exclusions because both are answers to "what would a person
        # opening this box count".
        checks.equal(
            [intact["section_end"], intact["box_total"]],
            [3, 3],
            "where an intact read says that section ends at the CARDS ON HAND: no divider "
            "is invented past the cards that exist (D10, amended), and no slot is counted "
            "for a card that has left (D58)",
        )
        checks.ok(
            "label" not in rows["4/3"],
            "and the flat label on the row degrades with the block rather than falling "
            "back to an index-space one — omitted exactly as a record whose box will not "
            "coerce has always been, so `positionLabel` answers null and no screen is "
            "handed a number from the numbering system this change replaced",
        )

# ---------------------------------------------------- D58: the numbers count the cards


def check_box_claim_product(checks: Checks) -> None:
    """`product` travels the box route too — the claim `BOX_CLAIM_FIELDS` accepted and dropped.

    THE SHAPE OF THE DEFECT, because it is the one a receipt cannot show you. `PUT_FIELDS` is
    derived from `master.CAPTURE_CLAIM_FIELDS` and `BOX_CLAIM_FIELDS` is derived from
    `PUT_FIELDS`, so when D70 added `product` on 2026-08-30 both tuples grew on their own.
    `_reject_unknown` therefore ACCEPTED the key, the `any(field in payload ...)` guard passed
    it, and only the hand-written decode table — which had no `product` branch — decided
    whether anything happened. Nothing did. The route answered 200 with `"applied": 0`, which
    is the same sentence it says when the box already carries the claim.

    NO CHECK COULD HAVE CAUGHT IT, because none sent the field: every `do_put_box_claims` call
    in this file sent `set_hint`, `game` or `variant`. The card route's decode table has had
    the branch since the day the claim landed, so the two tables disagreed for six days behind
    a comment reading "the same decode table as `do_put_card`, phase for phase".

    WHY IT MATTERS OFF THIS SCREEN: `#/codes` will not tier a held code without a product
    claim, and D70 makes the product the difference between a premium code and a penny lot.

    MUTATION IT IS KEPT FOR: delete the `if "product" in payload:` branch from
    `do_put_box_claims`. `applied` drops to 0 and every record's `product` stays None — which
    is precisely what the tree did before 2026-09-05.
    """
    checks.note("")
    checks.note("BOX-LEVEL CLAIMS — the product claim (D70/C10)")

    with isolated_home():
        for _i in range(1, 4):
            capture_server.do_capture(capture_payload(7))

        body = capture_server.do_put_box_claims(7, {"product": "etb"})
        checks.equal(
            (body["eligible"], body["applied"]),
            (3, 3),
            "the box route APPLIES a product claim — it accepted the key and moved nothing "
            "until 2026-09-05, answering 200 `applied: 0` like a box that already agreed",
        )
        after = Store().read().inventory
        checks.ok(
            all(after.cards[f"7/{i}"].product == "etb" for i in (1, 2, 3)),
            "and every eligible card carries it on the record, which is what `#/codes` "
            "reads to tier a held code",
        )

        # THE VOCABULARY IS STILL THE VOCABULARY. `_optional_product` is not scoped to a game
        # (there is one game that carries products), but it is still a closed list, and the
        # box route has to refuse outside it exactly as the card route does — otherwise the
        # fix has bought a wider door rather than the same one.
        refusal(
            checks,
            lambda: capture_server.do_put_box_claims(7, {"product": "not_a_product"}),
            "product_invalid",
            "a product outside `codes/products.py` refuses the whole call",
        )
        checks.ok(
            all(
                Store().read().inventory.cards[f"7/{i}"].product == "etb"
                for i in (1, 2, 3)
            ),
            "and the refusal changed nothing — D29's all-or-nothing shape holds for this "
            "claim like every other",
        )

        # Absent means NO CLAIM, never a clear: the same rule the capture route states.
        capture_server.do_put_box_claims(7, {"set_hint": "sv9"})
        checks.ok(
            all(
                Store().read().inventory.cards[f"7/{i}"].product == "etb"
                for i in (1, 2, 3)
            ),
            "a later call that does not mention `product` leaves it alone",
        )


def check_box_names_and_place_labels(checks: Checks) -> None:
    """A box is shown by its name, and a place label is box name, section and card in section.

    THE OWNER'S RULINGS OF 2026-09-23, both argued in their own entries:
    D259 (the box number never reaches a screen; an unnamed box gets the
    stored name `Box <count+1>`; the boxes that had no name are backfilled `Box <number>`) and
    D260 (the card number restarts at every divider). Four parts:
    the label's shape, where a departed card says it was, the default name at creation, and the
    backfill as a previewed, idempotent, one-transaction write.
    """
    checks.note("")
    checks.note("BOX NAMES AND PLACE LABELS — D259")

    # --- the label's shape -------------------------------------------------------------------
    view = join.BoxView(sections=(1, 6), occupied=(1, 2, 3, 4, 6, 7, 8), departed=(5,),
                        name="Mixed Singles")
    live = view.at(7, 7)
    checks.equal(
        live.label,
        "Mixed Singles, Section 2, Card 2",
        "a place label is the box's NAME, the section, and the card counted within its "
        "section: index 7 is the second card behind the divider at index 6",
    )
    typed = [
        text for text in (live.label, view.at(7, 5).label, join.where_phrase("pokemon", view.at(7, 5)))
        if "\u00b7" in text or "\u2022" in text
    ]
    checks.equal(
        typed,
        [],
        "no place label, departed label or report phrase TYPES a middle dot or bullet (D218)",
    )
    checks.ok(
        "7" not in live.label.replace("Card 2", ""),
        "and the box NUMBER is nowhere in a named box's label",
        live.label,
    )
    checks.equal(
        join.Position(7, 1).label,
        "Box 7, Section 1, Card 1",
        "a caller with no registry to ask gets `Box <number>`, which is exactly the name the "
        "backfill stores for that box, so the two cannot come to spell it differently",
    )

    # --- where a departed card was ----------------------------------------------------------
    departed = view.at(7, 5)
    checks.equal(
        (departed.slot, departed.card, departed.section, departed.was_card, departed.label),
        (None, None, 1, 5, "Mixed Singles, Section 1, Card 5"),
        "A DEPARTED CARD NAMES THE PLACE IT LEFT, IN ITS OWN SECTION. Index 5 was the last "
        "card of section 1 (the divider is at index 6), so it reads Section 1, Card 5: the "
        "number it would take going back. Counted in the slot space it would read Section 2, "
        "the next divider's number, which is the defect this guards",
    )
    checks.equal(
        join.where_phrase("pokemon", departed),
        "formerly at Mixed Singles, Section 1, Card 5",
        "and a report sentence about it is in the past tense",
    )

    with isolated_home():
        # --- the default name at creation --------------------------------------------------
        capture_server.do_create_box({"box": 4})
        inventory = Store().read().inventory
        checks.equal(
            inventory.box(4).name,
            "Box 1",
            "A BOX CREATED WITH NO NAME GETS THE STORED NAME `Box <count+1>`: the first box is "
            "`Box 1` whatever its number (4)",
        )
        capture_server.do_create_box({"name": "Box 3"})
        capture_server.do_create_box({"box": 9})
        inventory = Store().read().inventory
        checks.equal(
            [(entry.box, entry.name) for entry in sorted(inventory.boxes.values(), key=lambda e: e.box)],
            [(1, "Box 3"), (4, "Box 1"), (9, "Box 4")],
            "WHEN `Box <count+1>` IS TAKEN, THE NEXT FREE NAME IS USED. Two boxes stand, so the "
            "third is `Box 3`, but the owner named box 1 `Box 3` by hand: box 9 gets `Box 4`, "
            "and names stay unique (D20)",
        )

        # THE DEFAULT GOES THROUGH THE SAME UNIQUE-NAME CHECK AS A TYPED NAME. The default is
        # chosen free, and the check is what proves it: a default that clashes is refused,
        # never stored beside the box that already answers to it.
        real_default = master.Inventory.default_box_name
        master.Inventory.default_box_name = lambda self, count=None, number=None: "Box 1"
        try:
            with Store().write() as snapshot:
                clash = checks.raises(
                    master.BoxNameTaken,
                    lambda: snapshot.inventory.ensure_box(20),
                    "a default name that another box already has is REFUSED at creation: the "
                    "default path takes the same unique-name check a typed name takes",
                )
                if clash is None:
                    snapshot.inventory.boxes.pop("20", None)
        finally:
            master.Inventory.default_box_name = real_default
        checks.equal(
            Store().read().inventory.box(20),
            None,
            "and the refused box is not registered",
        )
        for _ in range(3):
            capture_server.do_capture(capture_payload(4))
        capture_server.do_put_box(4, {"name": "Rares"})
        checks.equal(
            capture_server.do_inventory()["cards"]["4/2"].get("label"),
            "Rares, Section 1, Card 2",
            "and a rename reaches every label at once: the name is joined at read time",
        )

        # --- clearing a name stores the default -------------------------------------------
        # The orchestrator's call on the locating review: a cleared name is the default name
        # `Box <count+1>`, the next free one, never a bare number drawn at render time.
        capture_server.do_put_box(4, {"name": ""})
        checks.equal(
            Store().read().inventory.box(4).name,
            "Box 5",
            "CLEARING A BOX'S NAME STORES THE DEFAULT NAME. Three boxes stand, so the default "
            "is `Box 4`, which box 9 has: the next free one, `Box 5`, is stored",
        )
        cleared = [e for e in Store().history() if e.get("event") == "box_renamed"
                   and e.get("box") == 4 and e.get("name_from") == "Rares"]
        checks.equal(
            [e.get("name_to") for e in cleared],
            ["Box 5"],
            "and the clear lands as one `box_renamed` line naming the stored default",
        )
        before_events = len(Store().history())
        capture_server.do_put_box(9, {"name": None})
        checks.ok(
            Store().read().inventory.box(9).name == "Box 4"
            and len(Store().history()) == before_events,
            "a box that already carries `Box <count+1>` keeps it when cleared, and nothing is "
            "logged: its own name is not taken from it",
            Store().read().inventory.box(9).name,
        )

        # --- the backfill ------------------------------------------------------------------
        # A store from before the ruling: registered boxes with no name.
        # `set_name` no longer stores None (a cleared name is the default), so a legacy box is
        # made by writing the row's name away directly, the shape a store from before the
        # ruling holds.
        with Store().write() as snapshot:
            snapshot.inventory.box(4).name = None
            snapshot.inventory.box(9).name = None
        capture_server.do_capture(capture_payload(5))
        with Store().write() as snapshot:
            # Box 5 came from a capture, which now names it; unname it to stand for a legacy box.
            snapshot.inventory.box(5).name = None
        before = Store().read().inventory
        plan = before.box_name_plan()
        checks.equal(
            plan,
            [(4, "Box 4"), (5, "Box 5"), (9, "Box 9")],
            "the backfill PLANS `Box <number>` for every unnamed box, today's number, so "
            "nothing visible changes and the drawers' physical labels still match",
        )
        checks.equal(
            [Store().read().inventory.box(n).name for n in (4, 5, 9)],
            [None, None, None],
            "and a plan writes nothing: the preview is a read",
        )

        said: list = []
        from cli import cmd_boxes  # noqa: E402 — the CLI seam, imported where it is exercised

        cmd_boxes.run(argparse.Namespace(boxes_action="names", write=False), said.append)
        checks.ok(
            Store().read().inventory.box(4).name is None and any("box 4 -> Box 4" in line for line in said),
            "`pkmnscan boxes names` with no flag PREVIEWS: it prints the plan and writes nothing",
            "\n".join(said),
        )
        said.clear()
        cmd_boxes.run(argparse.Namespace(boxes_action="names", write=True), said.append)
        after = Store().read().inventory
        checks.equal(
            [after.box(n).name for n in (1, 4, 5, 9)],
            ["Box 3", "Box 4", "Box 5", "Box 9"],
            "`--write` names every unnamed box and leaves a named one alone",
        )
        renamed = [e for e in Store().history() if e.get("event") == "box_renamed"
                   and e.get("name_from") is None and e.get("box") in (4, 5, 9)]
        checks.equal(
            sorted(e.get("box") for e in renamed if str(e.get("name_to", "")).startswith("Box ")),
            [4, 5, 9],
            "each name goes through `set_name`, so each lands with its `box_renamed` line",
        )
        said.clear()
        cmd_boxes.run(argparse.Namespace(boxes_action="names", write=True), said.append)
        checks.ok(
            Store().read().inventory.box_name_plan() == []
            and any("already has a name" in line for line in said),
            "A SECOND PASS CHANGES NOTHING: the backfill is idempotent",
            "\n".join(said),
        )

    with isolated_home():
        # A clash: `Box <number>` already belongs to another box, named that way by hand.
        capture_server.do_create_box({"box": 1, "name": "Box 2"})
        capture_server.do_create_box({"box": 2})
        with Store().write() as snapshot:
            snapshot.inventory.box(2).name = None
        checks.equal(
            Store().read().inventory.box_name_plan(),
            [(2, "Box 3")],
            "WHEN `Box <number>` IS ANOTHER BOX'S NAME, the backfill plans the next free one: "
            "names stay unique (D20), and no box is renamed to make room",
        )

    with isolated_home():
        # --- a refusal names the place the way a card row does -----------------------------
        # The orchestrator's call on the locating review, 2026-09-24: a server refusal that
        # names a card says the box's NAME, the section and the card within the section,
        # through the one helper (`join.said_place`), and never the box number or the store
        # index. A refusal reaches a screen as a toast. The error code does not change.
        capture_server.do_create_box({"box": 7, "name": "Rares"})
        for _ in range(4):
            capture_server.do_capture(capture_payload(7))
        # DIVIDERS AFTER THE CAPTURES (D10, the owner's ruling of 2026-09-26): a divider
        # typed ahead of the fill takes the next captures, so a layout is declared
        # over cards that are already in the box.
        capture_server.do_put_box(7, {"sections": [1, 3]})
        capture_server.do_mark_sold(7, 4, {})
        try:
            capture_server.do_mark_sold(7, 4, {})
            said_sold = None
        except capture_server.BadRequest as caught:
            said_sold = caught
        checks.ok(
            said_sold is not None
            and said_sold.code == "already_sold"
            and str(said_sold).startswith("Rares, Section 2, Card 2 is already sold")
            and "7/" not in str(said_sold) and "Box 7" not in str(said_sold)
            and "card 4" not in str(said_sold),
            "A REFUSAL ABOUT A CARD SAYS THE BOX'S NAME, SECTION AND CARD IN THE SECTION. Index "
            "4 is the second card behind the divider at index 3: `Rares, Section 2, Card 2`. "
            "The code stays `already_sold`, and neither the box number nor the index is said",
            f"refusal: {getattr(said_sold, 'code', None)}: {said_sold}",
        )
        # A STORE REFUSAL ABOUT A BOX SAYS ITS NAME. This read the sealed-box refusal until
        # `D299`; a second divider in front of nothing is the same shape.
        said_empty = ""
        try:
            with Store().write() as snapshot:
                snapshot.inventory.open_section(7)
                snapshot.inventory.open_section(7)
        except Exception as caught:  # noqa: BLE001 — the message is what is read here
            said_empty = str(caught)
        checks.ok(
            "of Rares holds nothing yet" in said_empty and "box 7" not in said_empty.casefold(),
            "and a store refusal about a box says its name, `Rares`, never `box 7`",
            said_empty,
        )
        checks.equal(
            (
                join.said_place(Store().read().inventory, 7),
                join.said_place(Store().read().inventory, 7, 99),
            ),
            ("Rares", "Rares"),
            "the helper says the box alone for no index, and for an index that holds no card "
            "(a place with no card has no section or card number to say)",
        )

    with isolated_home():
        # A clash must not push a box off a name that was free for it. Box 1 was named `Box 4`
        # by hand; boxes 4 and 5 have no name. Box 5's own `Box 5` is free, so it keeps it,
        # and only box 4, the one that clashes, moves to the next free name.
        capture_server.do_create_box({"box": 1, "name": "Box 4"})
        capture_server.do_create_box({"box": 4})
        capture_server.do_create_box({"box": 5})
        with Store().write() as snapshot:
            snapshot.inventory.box(4).name = None
            snapshot.inventory.box(5).name = None
        checks.equal(
            Store().read().inventory.box_name_plan(),
            [(4, "Box 6"), (5, "Box 5")],
            "EVERY UNNAMED BOX GETS ITS OWN `Box <number>` FIRST, WHERE IT IS FREE, and only then "
            "are the clashes resolved: a clash never shifts a later box off its own free name",
        )


def check_consolidated_numbering(checks: Checks) -> None:
    """A card's number is its place among the cards IN the box, not among the slots. D58.

    THE PROPERTY, AND IT IS ONE SENTENCE: sell card 17 and the card behind it becomes card
    17. `docs/specs/order-flow.md` §4.1 says what that replaces — *"`Card 17` is the
    seventeenth slot, not the seventeenth card you can count"* — and D58 has been waiting
    since 2026-08-23 for a physical marker to explain the difference to whoever is holding
    the box. There is nothing left to explain.

    THE STORED INDEX NEVER MOVES AND THAT IS ASSERTED HERE TOO. This is a rendering change:
    no photograph is renamed, no queue entry re-keyed, no history line changes subject, and
    `next_index` is the high-water mark it has always been. D10's permanent gap survives
    intact in the one place it was ever load-bearing — the allocator — which is why the two
    hardest cases in this file (`check_allocator`'s and `check_mark_sold`'s) are untouched
    by all of this.

    THE SECTION HALF IS THE HALF THAT IS EASY TO GET WRONG, so it is asserted from both
    sides: a sale in an EARLIER section must leave a later section's card numbers alone,
    and a sale in the SAME section in front of a card must move it by one. Mapping only the
    cards and not the dividers would pass the second and fail the first, and a build that
    mapped neither would pass the first and fail the second.
    """
    checks.note("")
    checks.note("D58 — THE NUMBER COUNTS THE CARDS IN THE BOX")

    with isolated_home():
        # Two sections, six cards each: [1, 7] over twelve.
        capture_server.do_create_box({"box": 3})
        for _ in range(12):
            capture_server.do_capture(capture_payload(3))
        # DIVIDERS AFTER THE CAPTURES (D10, the owner's ruling of 2026-09-26): a divider
        # typed ahead of the fill takes the next captures, so a layout is declared
        # over cards that are already in the box.
        capture_server.do_put_box(3, {"sections": [1, 7]})
        # THE LABEL SAYS THE BOX'S NAME (D259), and a box created with
        # no name carries its stored default. Read back, so this check is about numbering.
        box_title = Store().read().inventory.box(3).name

        def label(index: int) -> object:
            return capture_server.do_inventory()["cards"][f"3/{index}"].get("label")

        def place(index: int) -> dict:
            return capture_server.do_inventory()["cards"][f"3/{index}"]["place"]

        checks.equal(
            [label(1), label(7), label(12)],
            [
                f"{box_title}, Section 1, Card 1",
                f"{box_title}, Section 2, Card 1",
                f"{box_title}, Section 2, Card 6",
            ],
            "a box nothing has left renders exactly as it did before D58 — the two spaces "
            "coincide until the first departure, which is what makes this additive",
        )

        # --- a departure in section 1 -----------------------------------------------------
        capture_server.do_mark_sold(3, 3, {})
        checks.equal(
            label(4),
            f"{box_title}, Section 1, Card 3",
            "SELL CARD 3 AND THE CARD BEHIND IT BECOMES CARD 3 — the whole of D58 in one "
            "assertion, and the sentence `docs/specs/order-flow.md` §4.1 says could not "
            "be true while a label named a slot",
        )
        checks.equal(
            label(7),
            f"{box_title}, Section 2, Card 1",
            "AND SECTION 2 IS UNDISTURBED: a sale in an earlier section moves the divider "
            "and the cards behind it by the same one, so the number WITHIN a section is "
            "the difference between two things that both moved. Mapping the cards and not "
            "the dividers would read `Card 2` here",
        )
        checks.equal(
            [place(4)["slot"], place(4)["index"], place(7)["slot"], place(7)["index"]],
            [3, 4, 6, 7],
            "and `slot` and `index` are both on the wire and both true: the number a "
            "person counts to, and the store key every write still aims by",
        )
        checks.equal(
            capture_server.do_inventory()["cards"]["3/3"].get("label"),
            f"{box_title}, Section 1, Card 3",
            "the DEPARTED card's label keeps the PLACE it left: the box's name, its section, "
            "and the number it would take going back (the owner's ruling, "
            "D259). No word says it left and no store key is "
            "printed; the screen draws a mark for that, off `slot` being null",
        )
        checks.equal(
            place(3)["label"],
            join.departed_label(box_title, 1, 3),
            "and its block says so through the one composer that owns a departed label",
        )
        checks.equal(
            [place(3)["slot"], place(3)["card"], place(3)["fraction"]],
            [None, None, None],
            "with every number that would have counted it null rather than stale",
        )

        # --- a departure in the SAME section, in front ------------------------------------
        capture_server.do_mark_sold(3, 8, {})
        checks.equal(
            label(9),
            f"{box_title}, Section 2, Card 2",
            "a sale in this card's OWN section and in front of it moves it by one — the "
            "other half of the pair, and the half a build that mapped nothing would pass",
        )
        checks.equal(
            label(4),
            f"{box_title}, Section 1, Card 3",
            "while section 1 is untouched by a sale behind it: the map runs one way",
        )

        # D68: TWO DEPARTED RECORDS IN ONE BOX ARE TWO ROWS, NOT ONE ROW TWICE. Both draw the
        # same box and the same word, so before the store key was appended they were the
        # identical string — the owner read that as `I'm seeing two box 1's`, and on his store
        # 11 of 12 departed records sit in a group that does it. Asserted as an inequality
        # rather than against the literals above it, because what the label must guarantee is
        # that no two records ever share one.
        checks.equal(
            [label(3), label(8)],
            [f"{box_title}, Section 1, Card 3", f"{box_title}, Section 2, Card 2"],
            "two departed records in two sections each name the place they left, counted in "
            "their own section; `Place.slot` stays null for both, and it is the mark a screen "
            "draws off that null, never a word, that says they left",
        )

        # --- the index never moved --------------------------------------------------------
        inventory = Store().read().inventory
        checks.equal(
            inventory.next_index(3),
            13,
            "AND NOT ONE INDEX MOVED. `next_index` is the high-water mark it always was, "
            "so D10's permanent gap is intact where it was ever load-bearing — this is a "
            "rendering, and the allocator never heard about it",
        )
        checks.ok(
            photo_of(3, 4).is_file()
            and inventory.get("3/4") is not None
            and inventory.get("3/3") is not None,
            "the photograph is at the slot it was written to, and both records survive: "
            "no rename, no re-key, no migration",
        )

        # --- retired counts the same as sold ----------------------------------------------
        capture_server.do_retire(3, 5, {"reason": "damaged"})
        checks.equal(
            label(6),
            f"{box_title}, Section 1, Card 4",
            "a RETIRED card is counted out exactly as a sold one is — `master.TERMINAL_"
            "STATES` is the pair, and both mean the card is not in the box any more",
        )

        # --- the box's own numbers follow -------------------------------------------------
        row = capture_server.do_boxes()["boxes"][0]
        checks.equal(
            [row["on_hand"], row["cards"], row["fill"], row["next_index"]],
            [9, 12, 12, 13],
            "`on_hand` is what the box HOLDS and the three beside it are unchanged: "
            "`cards` counts records, `fill` is the high-water mark, and `BoxOps` still "
            "greps those two to `inventory.json`",
        )
        checks.equal(
            place(12)["box_total"],
            row["on_hand"],
            "and the denominator on a card's block is the same number as the box row's — "
            "one walk, two renderers, which is what `_denominator` used to buy by being "
            "one function",
        )
        checks.equal(
            [(d["section"], d["start"], d["end"], d["count"]) for d in row["sections_detail"]],
            [(1, 1, 4, 4), (2, 5, 9, 5)],
            "and `sections_detail` is in the same space as the labels, so the dividers "
            "editor seeds with the numbers the screen is showing",
        )

        # --- the editor round-trips through the inverse -----------------------------------
        # What the field would show, sent straight back: the store must be unchanged, which
        # is the only property that makes a count-space editor safe over an index-space
        # store. Mutation-tested by sending the RAW `sections` instead, which moves it.
        before = list(Store().read().inventory.sections_for(3))
        capture_server.do_put_box(3, {"sections": [d["start"] for d in row["sections_detail"]]})
        checks.equal(
            list(Store().read().inventory.sections_for(3)),
            before,
            "the layout the editor was seeded with, sent back unchanged, leaves the STORE "
            "unchanged — `join.divider_index` is `Position._divider` run backwards and the "
            "round trip is exact",
        )

        # Moving a divider one card later lands one index later, not one card later.
        capture_server.do_put_box(3, {"sections": [1, 6]})
        checks.equal(
            list(Store().read().inventory.sections_for(3)),
            [1, 9],
            "and a divider moved to the 6th CARD is stored at the INDEX THAT CARD SITS AT "
            "— 9, not 6, because three cards in front of it have left. That is the index "
            "`open_section` would have written had the operator pressed `S` there, so a "
            "divider typed in and a divider put in at the feeder are the same number",
        )
        capture_server.do_put_box(3, {"sections": before})

        # --- an emptied section keeps its number ------------------------------------------
        for index in (7, 9, 10, 11, 12):
            if Store().read().inventory.get(f"3/{index}").state == master.CAPTURED:
                capture_server.do_mark_sold(3, index, {})
        row = capture_server.do_boxes()["boxes"][0]
        checks.equal(
            [(d["section"], d["count"]) for d in row["sections_detail"]],
            [(1, 4), (2, 0)],
            "a section every card has left keeps its NUMBER and reports zero: the divider "
            "is still in the plastic, and renumbering the sections behind it would send "
            "someone to the wrong one",
        )

        # --- the report and the screen spell one address ----------------------------------
        # THE LOAD-BEARING CASE. `cli/resolve.py:box_views` and `_Places._walk` are two
        # implementations of one walk, in one language but in two modules that cannot import
        # each other's caching, and a card's number is now a property of the whole box — so
        # a reporter that renders without the walk answers in the numbering system D58
        # replaced and prints it beside a screen that does not. Same shape `make
        # port-agreement` uses for the other pair that must agree.
        #
        # It also fixes a defect OLDER than D58, which is why the box here declares a layout:
        # every `Position` built in `cli/resolve.py` used to pass no layout at all, so a
        # box-2 queue entry read `Section 1 · Card 300` where the app read `Section 4 · Card
        # 48`. Nothing had ever compared the two.
        views = resolve.box_views(Store().read().inventory)
        checks.equal(
            [views[3].at(3, i).label for i in (4, 6)],
            [label(4), label(6)],
            "THE RUN REPORT AND THE SCREEN RENDER ONE ADDRESS — two walks, in two modules, "
            "asserted equal on real cards rather than trusted",
        )
        checks.equal(
            views[3].at(3, 3).label,
            place(3)["label"],
            "including for a departed card, where the two could most easily disagree",
        )
        checks.equal(
            views[3].on_hand,
            row["on_hand"],
            "and they count the same cards on hand — the denominator is the same walk",
        )

# ------------------------------------------------------------- boxes, listings, migration


def check_section_names(checks: Checks) -> None:
    """D132 — a section can be named, and the name follows its divider.

    THE BODY SPEAKS ORDINALS AND THE STORE KEEPS DIVIDER INDICES, exactly the split
    `do_put_box` already makes for `sections`. What is asserted is the round trip through both
    renderers — `sections_detail[].name` on the box row and `place.section_name` on every card
    in the section — and the two edges: an ordinal past the layout refuses by name, and a
    blank clears. Then the divider moves and the name is still on the section that starts at
    that index, because that is the physical fact: the label is on the plastic divider.
    """
    checks.note("")
    checks.note("D132 — A SECTION CAN BE NAMED, AND THE NAME FOLLOWS ITS DIVIDER")

    with isolated_home():
        capture_server.do_create_box({"box": 3})
        for _ in range(12):
            capture_server.do_capture(capture_payload(3))
        # DIVIDERS AFTER THE CAPTURES (D10, the owner's ruling of 2026-09-26): a divider
        # typed ahead of the fill takes the next captures, so a layout is declared
        # over cards that are already in the box.
        capture_server.do_put_box(3, {"sections": [1, 7]})

        row = capture_server.do_put_box(3, {"section_names": {"2": "Rares"}})
        checks.equal(
            [(d["section"], d["name"]) for d in row["sections_detail"]],
            [(1, None), (2, "Rares")],
            "PUT /boxes/<box> with `section_names` keyed by ordinal names that section on "
            "`sections_detail`, and an unnamed one stays null rather than blank",
        )
        cards = capture_server.do_inventory()["cards"]
        checks.equal(
            (cards["3/3"]["place"]["section_name"], cards["3/9"]["place"]["section_name"]),
            (None, "Rares"),
            "and every card's place block carries its own section's name, joined at read "
            "time like `box_name` (D56) — nothing is written onto the card",
        )

        # An ordinal the layout does not reach is a typo, not a declaration.
        try:
            capture_server.do_put_box(3, {"section_names": {"5": "Nope"}})
            checks.equal(True, False, "naming section 5 of a two-section box is refused")
        except capture_server.BadRequest as exc:
            checks.equal(exc.code, "section_unknown", "naming section 5 of a two-section box is refused, as `section_unknown`")
        checks.equal(
            [d["name"] for d in capture_server.do_boxes()["boxes"][0]["sections_detail"]],
            [None, "Rares"],
            "and the refusal wrote nothing",
        )

        # The name is on the DIVIDER. Moving the divider one card later keeps the name on the
        # section that starts there; a layout that drops the divider drops the name with it.
        row = capture_server.do_put_box(3, {"sections": [1, 8]})
        checks.equal(
            [(d["section"], d["start"], d["name"]) for d in row["sections_detail"]],
            [(1, 1, None), (2, 8, "Rares")],
            "a moved divider carries its name — the label is on the plastic, not on a number",
        )
        row = capture_server.do_put_box(3, {"section_names": {"2": "  "}})
        checks.equal(
            [d["name"] for d in row["sections_detail"]],
            [None, None],
            "and a blank clears it, the shape a cleared text field sends",
        )
        named = [e for e in Store().history() if e["event"] == "section_named"]
        checks.equal(
            len(named),
            2,
            "two writes changed a name and two `section_named` events carry the maps "
            "before and after — the refusal wrote none, and the divider move is on its own "
            "`resectioned` line rather than a second event",
        )
        checks.equal(
            (named[0]["names_from"], named[0]["names_to"]),
            ({}, {"2": "Rares"}),
            "the event carries both maps, by ordinal, so the trail says what a section was called",
        )


def check_open_section(checks: Checks) -> None:
    """`POST /boxes/<box>/sections` — D10's divider, opened one at a time at the rig.

    THE ROUTE THE DECISION ENTRY HAD ALREADY DESCRIBED. D10 has said since 2026-08-23 that a
    box's dividers are "set by a **New section** control on the capture screen at the moment
    the real divider goes in", and until 2026-08-29 the only way to declare one was to type a
    whole layout into a field on `#/inventory`. This is that control's half of the wire.

    THE INDEX IS THE THING TO TEST, because it is the only thing the route decides. There is
    no index in the request — the store reads its own high-water mark inside the lock — so
    the case that matters is a box with a GAP in it, where a count and a high-water mark give
    different answers and only one of them is where the operator's hand will put the next
    card.

    ITS OWN ISOLATED HOME, which is this file's own repeated lesson: `check_boxes_and_listings`
    counts history lines over boxes it builds card by card, and a `resectioned` event written
    into its store would fail that section on this section's fixture.
    """
    checks.note("")
    checks.note("OPEN SECTION — server/capture_server.py, store/master.py (D10 amended)")

    with isolated_home():
        capture_server.do_create_box({"box": 4, "name": "S key"})
        with Store().write() as snapshot:
            for index in range(1, 41):
                snapshot.inventory.record_capture(
                    master.Card(box=4, index=index, cid=fake_cid(f"skey-4-{index}"))
                )

        before = capture_server.do_boxes()["boxes"][0]
        checks.equal(
            before["sections"],
            [],
            "the box starts undeclared — no divider exists because nobody has put one in",
        )
        checks.equal(
            [(d["section"], d["start"], d["end"], d["count"]) for d in before["sections_detail"]],
            [(1, 1, 40, 40)],
            "and it renders as ONE section holding all forty cards, not as two of 25 "
            "(D10, amended 2026-08-29 — the 25-card default is deleted)",
        )

        row = capture_server.do_open_section(4, {})
        checks.equal(
            row["sections"],
            [1, 41],
            "one press puts a divider in front of the NEXT card — and materialises the "
            "implicit first one, because `check_sections` requires a layout to start at 1 "
            "and there is no card before the front of a box",
        )
        checks.equal(
            [(d["section"], d["start"], d["count"]) for d in row["sections_detail"]],
            [(1, 1, 40), (2, 41, 0)],
            "the answer carries the SERVER's own spans, which is what the receipt on the "
            "capture screen reads — the app does no section arithmetic",
        )
        checks.equal(
            join.Position(4, 41, (1, 41)).label,
            "Box 4, Section 2, Card 1",
            "so the next card captured is card 1 of section 2",
        )

        # THE HIGH-WATER MARK, WHICH IS THE WHOLE REASON THE ROUTE TAKES NO INDEX. Box 6
        # holds four records at 1, 2, 3 and 7 — a shape D10 makes ordinary, since every sale
        # and every retirement leaves a permanent gap. A count says the next card is 5. The
        # allocator says 8, and the allocator is the one that is right about where the hand
        # will put it, so a divider anywhere else would sit in front of a card that never
        # arrives. Observed failing against a count before this case was kept.
        with Store().write() as snapshot:
            for index in (1, 2, 3, 7):
                snapshot.inventory.record_capture(
                    master.Card(box=6, index=index, cid=fake_cid(f"gaps-6-{index}"))
                )
        checks.equal(
            capture_server.do_open_section(6, {})["sections"],
            [1, 8],
            "THE DIVIDER GOES AT `next_index`, NOT AT COUNT + 1 — a box with gaps in it "
            "would otherwise be divided in front of a card that will never be captured",
        )

        # THE STORE RAISES AND `_dispatch` NAMES THE CODE, so each refusal is asserted
        # twice: the exception here, and the string a client is actually told, on a socket
        # at the bottom of this section. That is the split `check_box_routes_and_search`
        # already draws for the sealed box, and it exists because an in-process call proves
        # nothing about the half that reaches a screen.
        checks.raises(
            master.SectionEmpty,
            lambda: capture_server.do_open_section(4, {}),
            "a second press with nothing captured between refuses: the section you just "
            "opened is still empty, so the divider asked for is already there",
        )
        checks.equal(
            capture_server.do_boxes()["boxes"][0]["sections"],
            [1, 41],
            "and the refusal moved nothing — no second divider, no rewritten layout",
        )

        refusal(
            checks,
            lambda: capture_server.do_open_section(4, {"at": 41}),
            "field_not_settable",
            "a body naming an index is refused rather than obeyed: the index is the "
            "store's to read, and a client that could send one could send a stale one",
        )

        # A DECLARED DIVIDER PAST THE FILL is legal (`_section_spans` renders it with a
        # count of zero). It is an empty last section, so under the owner's ruling of
        # 2026-09-25 ("Into the empty section (Recommended)", D10) S refuses it as
        # `section_empty`, and the next capture goes INTO it, behind the divider.
        with Store().write() as snapshot:
            snapshot.inventory.record_capture(
                master.Card(box=5, index=1, cid=fake_cid("section-ahead-5-1"))
            )
        capture_server.do_put_box(5, {"sections": [1, 51]})
        checks.raises(
            master.SectionEmpty,
            lambda: capture_server.do_open_section(5, {}),
            "a divider already declared past the next card is an empty section, so S "
            "refuses it the way it refuses a second press",
        )

        refusal(
            checks,
            lambda: capture_server.do_open_section(77, {}),
            "box_not_found",
            "and a box nothing in this store has ever seen is not divided into existence",
        )

        # ONE EVENT NAME, NOT TWO. `set_sections` already logs `resectioned` with both
        # layouts, which is everything a reader wants, and this store has been bitten by a
        # new name before: D26 records the day a state and a history event sharing a word
        # made months-old undo lines parse as states.
        events = [e for e in Store().history() if e.get("event") == "resectioned"]
        checks.equal(
            [(e.get("box"), e.get("sections_from"), e.get("sections_to")) for e in events],
            [(4, [], [1, 41]), (6, [], [1, 8]), (5, [], [1, 51])],
            "every press appends `resectioned` carrying both layouts — the same line the "
            "dividers editor writes, so history has one vocabulary for one fact",
        )
        checks.ok(
            all(e.get("event") not in master.STATES for e in events),
            "and the event name is not a card state, which is the trap D26 fell into",
        )
        checks.ok(
            all("position" not in e for e in events),
            "and carries no position: a divider is not at one, and a null there would read "
            "as a lost card",
        )

        # ------------------------------------------------------------------ on the wire
        #
        # THE PATH AND THE CODES, which are the whole of what a client sees. `do_*` calls
        # above prove the behaviour; only a socket proves that `POST /boxes/6/sections`
        # reaches it and that the store's refusals arrive as distinct strings
        # rather than as one 500. `app/src/server.ts:openSection` branches on them.
        # Card 8 of box 6, so the section opened at 8 above holds something and the wire
        # press below is a real one rather than the replay refusal.
        capture_server.do_capture(capture_payload(6))

        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = _spawn_server(httpd)
        try:
            status, body, _ = request(port, "POST", "/boxes/6/sections", payload={})
            checks.equal(
                (status, json.loads(body)["sections"]),
                (200, [1, 8, 9]),
                "the route is reachable at the path the client uses, and answers with the "
                "box row so the capture screen can redraw the box it is shooting",
            )
            for box, code, label in (
                (6, "section_empty", "a replayed press is a 409 `section_empty`"),
                (5, "section_empty", "a divider ahead of the next card is 409 `section_empty`"),
            ):
                status, body, _ = request(port, "POST", f"/boxes/{box}/sections", payload={})
                checks.equal(
                    (status, error_code(body)),
                    (409, code),
                    label + " — each in its own code, because these strings reach a screen",
                )
        finally:
            httpd.shutdown()
            thread.join(timeout=5)


def check_card_decoration_one_home(checks: Checks) -> None:
    """One card, one decoration: every route that serves a card record yields the same
    number display, listing facts and place label, and a `places.of` failure behaves the same
    in all five (the card still arrives, undecorated by place, and nothing raises).
    """
    from dataclasses import asdict  # noqa: F401 - parity with the routes under test
    from pipeline.skus import SkuRow  # noqa: F401

    checks.note("")
    checks.note("CARD DECORATION — five routes, one answer")

    sku = "7000001"
    with isolated_home():
        capture_server.do_capture(capture_payload(1))
        with Store().write() as snapshot:
            from store.skus import SkuRow as Row
            snapshot.skus.entries[sku] = Row(
                product_line="Riftbound League of Legends Trading Card Game", set_name="Origins",
                product_name="Master Yi, Wuju Master", number="191/219", rarity="Rare",
                condition="Near Mint", grade="Near Mint", printing=None,
                first_seen=1_700_000_000, last_seen=1_700_000_000, source="t7-fixture", raw={},
            )
            snapshot.inventory.set_state("1/1", master.IDENTIFIED)
            snapshot.inventory.hold_sku("1/1", sku, skus=snapshot.skus, read_disputes=True)
            card = snapshot.inventory.cards["1/1"]
            card.game, card.name, card.number, card.printed_total = "riftbound", "Yi, Ionia", "7", "219"

        def routes():
            snap = Store().read()
            card = snap.inventory.cards["1/1"]
            return {
                "inventory": lambda: capture_server.do_inventory()["cards"]["1/1"],
                "box": lambda: capture_server.do_inventory_box(1)["cards"]["1/1"],
                "recent": lambda: capture_server.do_inventory_recent(5)["cards"]["1/1"],
                "copies": lambda: capture_server.do_inventory_copies({"skus": [sku]})["cards"]["1/1"],
                "card_row": lambda: capture_server._card_row(snap.inventory, 1, 1, card, snap.skus),
            }

        def outcome(fn):
            try:
                return fn()
            except Exception as caught:  # noqa: BLE001 - any raise is the finding
                return {"raised": type(caught).__name__}

        fields = ("number_display", "listing", "listing_differs", "reading_differs", "label", "section", "place")
        got = {name: outcome(fn) for name, fn in routes().items()}
        base = {f: got["box"].get(f) for f in fields}
        checks.ok(base["listing"] is not None and base["label"], "the reference card carries listing facts and a label", str(base))
        for name, record in got.items():
            checks.equal({f: record.get(f) for f in fields}, base, f"{name} yields the same decoration as the box route")

        real = capture_server._Places.of
        def broken(self, box, index):
            raise ValueError("bad position")
        capture_server._Places.of = broken
        try:
            failed = {name: outcome(fn) for name, fn in routes().items()}
        finally:
            capture_server._Places.of = real
        for name, record in failed.items():
            checks.ok(
                "raised" not in record and "place" not in record and record.get("number_display") == base["number_display"],
                f"{name}: a `places.of` failure leaves the card undecorated by place and raises nothing",
                str(record.get("raised") or sorted(record)),
            )


def check_terminal_states_one_home(checks: Checks) -> None:
    """`_facet_cells` marks a card gone by `master.TERMINAL_STATES`, never a copy of it: a
    terminal state added to that tuple is honoured."""
    checks.note("")
    checks.note("TERMINAL STATES — facet cells follow master.TERMINAL_STATES")

    real = master.TERMINAL_STATES
    with isolated_home():
        capture_server.do_capture(capture_payload(1))
        master.TERMINAL_STATES = (*real, "lost")
        try:
            with Store().write() as snapshot:
                snapshot.inventory.cards["1/1"].state = "lost"
            cells = capture_server.do_boxes()["facet_cells"]
        finally:
            master.TERMINAL_STATES = real
    checks.equal(
        [(c["box"], c["gone"], c["count"]) for c in cells], [(1, True, 1)],
        "a card in a state added to TERMINAL_STATES counts as gone in the facet cells",
    )


CHECKS = (
    check_inventory_filter_facets,
    check_inventory_facet_cells,
    check_box_routes_and_search,
    check_search_fts5,
    check_inventory_box_route,
    check_rows_scoped_after_full_load,
    check_inventory_recent_route,
    check_inventory_history_route,
    check_box_names,
    check_box_claims,
    check_box_claim_product,
    check_place_neighbors,
    check_open_section,
    check_section_names,
    check_consolidated_numbering,
    check_box_names_and_place_labels,
    check_card_decoration_one_home,
    check_terminal_states_one_home,
)
