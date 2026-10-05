"""T7 group: price history and its routes.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.
"""

from __future__ import annotations

import contextlib
import io
import json
import http.server
import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import envfile

from decimal import Decimal
from pathlib import Path
from harness.tests import Checks
from cli import cmd_reprice, runs
from pipeline import pricehistory, tcgcsv
from server import capture_server, pipeline_routes
from store import files, master
from store.session import Store
from harness.tests.t7.common import (
    REPO_ROOT,
    RIFTBOUND_EXPORT,
    _spawn_server,
    capture_payload,
    command,
    isolated_home,
    run_photo,
)

# ------------------------------------------------------------------ price history (D8, D86)


# Named as relative paths rather than assembled from segments, which is T2's shape and is
# what `scripts/docs-audit.py`'s `tested_by reach` row can actually see: it parses this file
# for a string under `fixtures/`, and a path built out of `/ "fixtures" /` is invisible to it.
# The audit is right to insist — `fixtures/` holds no Python, so a literal is the only
# evidence that a test reaches it at all.
TCGCSV_PRODUCTS_FIXTURE = "fixtures/tcgcsv_riftbound_unleashed_products.json"

TCGCSV_PRICES_FIXTURE = "fixtures/tcgcsv_riftbound_unleashed_prices.json"

PRICE_HISTORY_FIXTURE = "fixtures/tcgplayer_price_history_vilemaw_month.json"

TCGCSV_PRODUCTS = REPO_ROOT / TCGCSV_PRODUCTS_FIXTURE

TCGCSV_PRICES = REPO_ROOT / TCGCSV_PRICES_FIXTURE

PRICE_HISTORY = REPO_ROOT / PRICE_HISTORY_FIXTURE


def _riftbound_row(sku: str) -> tcgcsv.Row:
    """One row of the committed Riftbound export, by SKU. Raises if it is not there.

    The rows under test are LIFTED rather than written, so both halves of the join below are
    ground truth and neither was authored to agree with the other. It raises rather than
    answering None because a typo here would otherwise read as a join failure in the module,
    which is the wrong file to go and look in.
    """
    export = tcgcsv.read_export(RIFTBOUND_EXPORT)
    for row in export.rows:
        if row.get(tcgcsv.SKU_COLUMN) == sku:
            return row
    raise AssertionError(f"{RIFTBOUND_EXPORT.name} carries no SKU {sku}")


def _seed_market_cache(directory, product_id: int, month: dict, annual: dict) -> None:
    """Warm `Market`'s on-disk cache so the route below opens no socket.

    THE SLUGS ARE `Market`'s OWN AND ARE WRITTEN HERE BY HAND, which is the one thing in this
    block that could rot: a rename there makes this seed miss, the route fetches, and
    `urlopen` — patched to raise — takes the case red rather than letting it quietly reach the
    network. That is the failure mode wanted. A seed that silently stopped seeding would turn
    an offline test into an online one, which is the thing `check_price_history` says the
    harness must never do.
    """
    at = time.time()
    for slug, payload in (
        ("tcgcsv/categories", {"results": [{"categoryId": 89,
                                            "name": "Riftbound League of Legends Trading Card Game"}]}),
        ("tcgcsv/89/groups", {"results": [{"groupId": 24560, "name": "Unleashed"}]}),
        ("tcgcsv/89/24560/products", json.loads(TCGCSV_PRODUCTS.read_text("utf-8"))),
        (f"history/{product_id}-month", month),
        (f"history/{product_id}-annual", annual),
    ):
        path = directory / f"{slug}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"fetched_at": at, "payload": payload}), "utf-8")


def check_history_route(checks: Checks) -> None:
    """`GET /pipeline/runs/<name>/history` — D278's route, and the reading it serves.

    OFFLINE, AND NOT MERELY BY HABIT. `check_price_history` above states why the harness may
    not reach a third party: it runs behind the Stop hook at the end of every turn, so a case
    that opened a socket would put a stranger's uptime on the path that decides whether work
    is done and would hammer a free public mirror once per turn. That section can simply pass
    a fetcher; this one cannot, because the ROUTE constructs its own `Market`. So the cache is
    seeded from committed fixtures and `urlopen` is patched to raise — belt and braces, and
    the braces are what makes it a guarantee rather than an intention.

    WHAT THIS COVERS THAT `check_price_history` CANNOT: that the route reads its export row
    off the RUN rather than from anywhere else, that each refusal carries its own code, and
    that the payload a screen casts is the shape `app/src/types.ts` declares. The module's own
    section owns the arithmetic; this owns the seam.

    THE ASCENDING ASSERTION IS THE ONE THAT WOULD FAIL SILENTLY. `infinite-api` sends buckets
    newest-first and `Series.parse` sorts them; a route that passed the wire order through
    would draw every rising card falling, with no exception and nothing on screen to see. It
    is asserted here as well as in the module because this is the payload the screen actually
    reads — the sort could be correct in `pipeline/` and undone by a serializer.
    """
    checks.note("")
    checks.note("PRICE HISTORY ROUTE — D278's seam, offline against committed fixtures")

    month = json.loads(PRICE_HISTORY.read_text("utf-8"))
    # THE SAME CAPTURE SERVES BOTH RANGES, and it is the honest thing to do rather than
    # inventing a weekly fixture: what this section asserts about `annual` is that a SECOND
    # range is fetched, keyed separately and reported separately. The buckets' width is the
    # endpoint's business and `check_price_history` owns the arithmetic over them.
    annual = json.loads(PRICE_HISTORY.read_text("utf-8"))

    with isolated_home():
        run_dir = runs.create("t7-history")
        for _ in range(1):
            capture_server.do_capture(capture_payload(7, game="riftbound"))
        with Store().write() as snapshot:
            snapshot.inventory.set_state("7/1", master.IDENTIFIED)
            snapshot.inventory.cards["7/1"].game = "riftbound"
        run_dir.write_identifications(
            {
                "prompt_fingerprint": "t7-history",
                "cards": {
                    "7/1": {
                        "photo": run_photo(7, 1),
                        "box": 7,
                        "index": 1,
                        "set_hint": None,
                        # THE FINISH CLAIM IS REQUIRED HERE AND THAT IS THE LADDER WORKING.
                        # Every Vilemaw row in the riftbound export is a Foil — Near Mint
                        # through Damaged — so a card with no claim reaches five candidates
                        # and D3 routes it `ambiguous_no_signal` rather than guessing a
                        # condition. That is the correct outcome and it leaves no SKU to read
                        # a history for, so this card carries the toggle an operator sets on
                        # the stack.
                        "metadata_finish": "foil",
                        "status": "ok",
                        "error": None,
                        "identification": {
                            "name": "Vilemaw",
                            "number": "060/219",
                            "printed_total": "219",
                            "confidence": "high",
                            "finish": "foil",
                        },
                    }
                },
            }
        )
        # A REAL JOIN, so `pricing.json` is written by `cli/cmd_join.py` rather than by this
        # file. The row the route reads is therefore the row that command stores — which is
        # the whole reason the route needs no export of its own, and the one coupling worth
        # asserting against the real writer instead of a hand-made fixture.
        command(checks, "join", str(run_dir.directory), "--export", str(RIFTBOUND_EXPORT))
        name = run_dir.directory.name

        _seed_market_cache(pipeline_routes.market_cache_dir(), 684125, month, annual)

        real_urlopen = urllib.request.urlopen

        def no_sockets(*args, **kwargs):  # noqa: ANN001, ANN003
            raise AssertionError("the history route opened a socket in the harness")

        urllib.request.urlopen = no_sockets
        try:
            answer = pipeline_routes.do_pipeline_history(name, "9189317")
            checks.ok(True, "a warm cache answers without opening a socket")

            checks.equal(answer["sku"], "9189317", "the payload names the SKU asked for")
            checks.equal(answer["product_id"], 684125, "and the productId the walk resolved")
            checks.equal(answer["name"], "Vilemaw", "the card's name comes off the run's table")
            # THE EXPORT'S OWN FIGURE, CARRIED SO THE PANEL CAN DRAW IT BESIDE THE READING.
            # `snap.market` is what `cli/cmd_join.py` stored out of the export, so asserting
            # it here is asserting the route reads the RUN rather than re-deriving a price.
            checks.ok(
                answer["market"] is not None,
                "and the export's own market price, for the panel to draw beside it",
            )
            checks.equal(answer["never_sold"], False, "a card with sales is not `never_sold`")

            ranges = [r["range"] for r in answer["ranges"]]
            checks.equal(
                ranges,
                list(pricehistory.DEFAULT_RANGES),
                "both ranges are served, finest first, in DEFAULT_RANGES order",
            )

            recent = answer["ranges"][0]
            starts = [p["at"] for p in recent["points"] if p["at"]]
            checks.equal(
                starts,
                sorted(starts),
                "THE BUCKETS ARE ASCENDING — the wire order is newest-first, and passing it "
                "through would draw every rising card falling",
            )
            # And the fixture really is the other way round on disk, so the assertion above is
            # about the ROUTE sorting rather than about the endpoint having changed its mind.
            raw = [b["bucketStartDate"] for b in month["result"][0]["buckets"]]
            checks.ok(
                raw != sorted(raw),
                "and the committed fixture is newest-first on disk, so that was a real sort",
            )

            checks.ok(recent["vwap"] is not None, "the anchor is present")
            checks.ok(
                recent["bound"] is not None
                and recent["bound"]["width_of_vwap"] is not None
                and recent["bound"]["width_of_low"] is not None,
                "and the bound names BOTH denominators, per `Bound`'s own rule",
            )
            checks.ok(
                "window" in recent["momentum"],
                "momentum carries the window it was measured over",
            )
            checks.ok(
                isinstance(recent["liquidity"], int),
                "liquidity is the endpoint's own total rather than a recomputation",
            )

            # MONEY IS A STRING ON THIS WIRE. `cli/cmd_join.py` writes every figure in
            # `pricing.json` this way for the reason `pipeline/pricing.py` computes in
            # `Decimal`: a price through a JSON float comes back as binary floating point.
            checks.ok(
                all(
                    isinstance(v, str)
                    for v in (recent["vwap"], recent["bound"]["low"], recent["bound"]["high"])
                ),
                "and every figure crosses the wire as a string, never a float",
            )

            # A SECOND PRESS IS FREE, which is what makes the panel's toggle affordable.
            pipeline_routes.do_pipeline_history(name, "9189317")
            checks.ok(True, "and a second read is served from the same warm cache")

            # ------------------------------------------- the batched read (D277)
            #
            # THE SAME WARM CACHE AND THE SAME SOCKET BAN. `readings_for_rows` walks the
            # identical `Market`, so a batch that opened a connection would trip `no_sockets`
            # above — which is what makes this a seam test rather than a network test.
            batch = pipeline_routes.do_pipeline_trends(name)
            checks.equal(batch["asked"], 1, "the batch walks the run's own table")
            checks.equal(batch["skipped"], 0, "and skips nothing while no row is at the cap")
            checks.equal(batch["refused"], {}, "no refusals over a row the single route reads")
            strip = batch["skus"].get("9189317")
            checks.ok(strip is not None, "the SKU the single route answers is in the batch too")
            checks.equal(
                [r["range"] for r in strip["ranges"]],
                list(pricehistory.DEFAULT_RANGES),
                "both ranges, finest first, in the same order the panel draws",
            )
            # THE ASCENDING ASSERTION AGAIN, ON THE OTHER PAYLOAD. It is the failure with no
            # symptom — a rising card drawn falling — and `_history_spark` is a second
            # serializer over the same buckets, so asserting it once upstream proves nothing
            # about this one.
            spark = strip["ranges"][0]
            checks.equal(
                [v for v in spark["points"] if v is not None],
                [p["market"] for p in answer["ranges"][0]["points"] if p["market"] is not None],
                "and the strip's points are the panel's own bucket prices, in the same order",
            )
            # NO MONEY ON THIS PAYLOAD, WHICH IS D277's RULE AS A TEST RATHER THAN A PARAGRAPH.
            # The row draws this one column from the field a listing price is typed into, so
            # every figure it carries is dimensionless or a date. A later session adding `vwap`
            # here would be reopening D8 by widening a serializer.
            checks.equal(
                sorted(spark),
                ["fraction", "from", "points", "range", "to"],
                "the strip carries a span, a fraction and the shape — and nothing else",
            )

            # AN EXPLICIT LIST IS THE CHUNK, and it is what makes the strip fill in waves.
            picked = pipeline_routes.do_pipeline_trends(name, ["9189317"])
            checks.equal(list(picked["skus"]), ["9189317"], "an explicit ?sku= asks for that row")
            # BOTH DIRECTIONS, WHICH IS CLAUDE.md's HARD RULE. A SKU this run never matched is
            # NAMED with the reason rather than dropped — silence would look to the screen like
            # a mirror that had nothing to say about a real card, and leave the row reading
            # `reading…` for the rest of the session.
            named = pipeline_routes.do_pipeline_trends(name, ["9189317", "1"])
            checks.ok(
                "1" in named["refused"] and "1" not in named["skus"],
                "a SKU this run never matched comes back refused, never absent",
            )

            # ------------------------------------- the same two readings, addressed at a
            # ------------------------------------- markdown instead of a run (D103)
            #
            # ONE IMPLEMENTATION, TWO ADDRESSES. The catalogue walk reads five identity cells
            # off a verbatim export row, and a My Pricing export carries all five — so what a
            # markdown needed was an ADDRESS, not a second reader. Asserted against the SAME
            # warm cache and under the SAME socket ban: if these routes had grown their own
            # `Market` or their own cache key, `no_sockets` would fire.
            source = tcgcsv.read_export(RIFTBOUND_EXPORT)
            live_row = dict(source.by_sku()["9189317"])
            live_row[tcgcsv.LIVE_QUANTITY_COLUMN] = "1"
            live_row[tcgcsv.PRICE_COLUMN] = "9.0000"
            live_path = files.inventory_dir() / "live-history.csv"
            tcgcsv.write_csv(live_path, source.header, [live_row])
            command(checks, "reprice", "list", str(live_path), "--days", "7", "--write")
            stamp = sorted((files.inventory_dir() / cmd_reprice.DIRNAME).iterdir())[-1].name

            # THE CARD WAS CAPTURED A MOMENT AGO, so the rule refuses it `too_young` and it is
            # in no worklist. Reading its history anyway is the lens working: a row the rule
            # declined to propose is a row the operator can still look at and price.
            surveyed = json.loads(
                (files.inventory_dir() / cmd_reprice.DIRNAME / stamp / cmd_reprice.SURVEY)
                .read_text("utf-8")
            )
            checks.equal(
                [(r["sku"], r["standing"]) for r in surveyed["skus"]],
                [("9189317", "refused")],
                "the survey holds the refused row, which is the row the reading is about",
            )

            from_markdown = pipeline_routes.do_markdown_history(stamp, "9189317")
            checks.equal(
                (
                    from_markdown["sku"],
                    from_markdown["product_id"],
                    [r["range"] for r in from_markdown["ranges"]],
                ),
                (answer["sku"], answer["product_id"], [r["range"] for r in answer["ranges"]]),
                "A MARKDOWN'S READING IS THE RUN'S READING. Same SKU, same resolved product, "
                "same ranges in the same order — one body under two addresses",
            )
            checks.ok(
                from_markdown.get("markdown") == stamp and "run" not in from_markdown,
                "and it names the DOCUMENT it came from under `markdown`, never a stamp sent "
                "back in a field called `run` for the client to decode",
            )
            spark_md = pipeline_routes.do_markdown_trends(stamp, ["9189317"])
            checks.equal(
                spark_md["skus"]["9189317"]["ranges"],
                picked["skus"]["9189317"]["ranges"],
                "and the strip is the run's strip, bucket for bucket",
            )
            try:
                pipeline_routes.do_markdown_trends(stamp)
                checks.ok(False, "the markdown strip refuses an empty list", "it answered")
            except pipeline_routes.PipelineRefusal as refusal:
                checks.equal(
                    refusal.code,
                    "skus_required",
                    "AN UNFILTERED WALK IS REFUSED HERE AND ALLOWED ON A RUN, and the "
                    "difference is size: a survey is the whole live inventory, ~441 rows, "
                    "about 5.5 minutes at a public mirror — which would make D278's press "
                    "meaningless rather than merely slow",
                )
            try:
                pipeline_routes.do_markdown_history(stamp, "1")
                checks.ok(False, "the markdown route refuses a SKU it never saw", "it answered")
            except pipeline_routes.PipelineRefusal as refusal:
                checks.equal(
                    refusal.code,
                    "sku_not_in_markdown",
                    "a SKU this markdown never surveyed refuses by its own name, mirroring "
                    "`sku_not_in_run` — the address is checked, which a run-free route "
                    "taking the cells on a query string could not do",
                )

            # THE AT-CAP SKIP, on the owner's instruction of 2026-08-31: a row this run can add
            # nothing for is not a decision anyone is waiting on. Written into the stored table
            # rather than faked, because `at_cap` is `cli/cmd_join.py`'s own field and the whole
            # safety of the filter is that it is the SAME field the list groups those rows
            # under — two readers of one fact rather than two rules kept in step.
            table = run_dir.directory / runs.PRICING
            stored = json.loads(table.read_text("utf-8"))
            for entry in stored["skus"]:
                entry["at_cap"] = True
            table.write_text(json.dumps(stored), "utf-8")

            capped = pipeline_routes.do_pipeline_trends(name)
            checks.equal(capped["asked"], 0, "a row at the cap is not asked about")
            checks.equal(capped["skipped"], 1, "and the skip is COUNTED, never silent")
            checks.equal(capped["skus"], {}, "so the batch reads nothing")
            # AND IT STAYS REACHABLE, which is what makes the default safe rather than a rule
            # about the SKU. `T` reads any one of them and so does a named ?sku=.
            asked = pipeline_routes.do_pipeline_trends(name, ["9189317"])
            checks.ok(
                "9189317" in asked["skus"],
                "but naming it overrides the skip — a caller that names a row has decided",
            )
            checks.equal(
                pipeline_routes.do_pipeline_history(name, "9189317")["sku"],
                "9189317",
                "and `T` still reads an at-cap row through the single route",
            )
            stored = json.loads(table.read_text("utf-8"))
            for entry in stored["skus"]:
                entry["at_cap"] = False
            table.write_text(json.dumps(stored), "utf-8")

            for sku, code, why in (
                ("", "sku_required", "no SKU at all"),
                ("1", "sku_not_in_run", "a SKU this run never matched"),
            ):
                try:
                    pipeline_routes.do_pipeline_history(name, sku)
                    checks.ok(False, f"the route refuses {why}", "it answered instead")
                except pipeline_routes.PipelineRefusal as refusal:
                    checks.equal(refusal.code, code, f"the route refuses {why} as `{code}`")

            try:
                pipeline_routes.do_pipeline_history("2026-01-01-nope-01", "9189317")
                checks.ok(False, "the route refuses an unknown run", "it answered instead")
            except pipeline_routes.PipelineRefusal as refusal:
                checks.equal(refusal.code, "no_such_run", "the route refuses an unknown run")

            # A `misc` CARD HAS NO CATALOGUE AND THAT IS D22 RATHER THAN A GAP. Checked by
            # rewriting the stored row's product line, because the refusal is about the CELL —
            # a line no registered, catalogued game names has no category to look up, and
            # `misc` carries `product_line: None` by construction.
            table = run_dir.directory / runs.PRICING
            stored = json.loads(table.read_text("utf-8"))
            for entry in stored["skus"]:
                entry["row"][tcgcsv.PRODUCT_LINE_COLUMN] = "Yu-Gi-Oh!"
            table.write_text(json.dumps(stored), "utf-8")
            try:
                pipeline_routes.do_pipeline_history(name, "9189317")
                checks.ok(False, "an uncatalogued product line refuses", "it answered instead")
            except pipeline_routes.PipelineRefusal as refusal:
                checks.equal(
                    refusal.code,
                    "not_catalogued",
                    "an uncatalogued product line refuses as `not_catalogued`, before any fetch",
                )

            # THE BATCH REPORTS THE SAME FACT WITHOUT RAISING, and that difference is the
            # design rather than an inconsistency. One SKU asked about is one answer, so a
            # refusal is the answer; forty-six asked about is forty-six answers, and one
            # uncatalogued card must not cost the other forty-five their reading. Same
            # sentence, different envelope.
            uncatalogued = pipeline_routes.do_pipeline_trends(name)
            checks.equal(uncatalogued["skus"], {}, "the batch reads nothing uncatalogued")
            checks.ok(
                "D22" in (uncatalogued["refused"].get("9189317") or ""),
                "and names it per SKU, citing the entry that makes it permanent, without "
                "raising over the rows beside it",
            )

            # AND A RUN WITH NO PRICING TABLE REFUSES BY NAME. `join` is what writes it, so
            # this is the run that predates the file or has never been joined — the same
            # refusal `do_pipeline_pricing` makes, because it is the same missing file.
            table.unlink()
            try:
                pipeline_routes.do_pipeline_history(name, "9189317")
                checks.ok(False, "a run with no pricing table refuses", "it answered instead")
            except pipeline_routes.PipelineRefusal as refusal:
                checks.equal(
                    refusal.code,
                    "pricing_not_written",
                    "a run with no pricing table refuses as `pricing_not_written`",
                )

            # THE BATCH RAISES HERE AND DOES NOT RETURN AN EMPTY ANSWER, which is the one place
            # it is right for it to raise: there is no table to walk, so there are no SKUs to
            # report either way, and `{}` would read as a run whose every card is at the cap.
            try:
                pipeline_routes.do_pipeline_trends(name)
                checks.ok(False, "the batch refuses a run with no table", "it answered instead")
            except pipeline_routes.PipelineRefusal as refusal:
                checks.equal(
                    refusal.code,
                    "pricing_not_written",
                    "and the batch refuses it by the same name rather than answering empty",
                )
        finally:
            urllib.request.urlopen = real_urlopen


def check_history_blocked_route(checks: Checks) -> None:
    """A 403 refuses as `history_blocked`, and `PKMNSCAN_TCG_USER_AGENT` reaches the wire
    (D216).

    ITS OWN RUN, ITS OWN ENVIRONMENT ISOLATION — `check_export_fetch`'s reason applies again:
    a stray real `.env` on this machine must never leak into what this block asserts, and
    this key is exactly the kind of value that would.

    STILL NO SOCKET, TO A THIRD PARTY OR OTHERWISE. `urllib.request.urlopen` is patched to
    RAISE the 403 itself, in-process, so `pipeline/pricehistory.py`'s real `fetch_json` runs
    its real exception handling — this is not a stand-in for `Blocked`, it is `Blocked` —
    while the patched function also RECORDS the header it was handed, which is the one thing
    a fixture dictionary could not prove: that `server/pipeline_routes.py:_history_user_agent`
    actually reaches the request `pricehistory.py` sends.

    THE CATALOG HOPS ARE SEEDED AND THE HISTORY HOP IS NOT, on purpose — seeding all five
    slugs the way `_seed_market_cache` does would answer everything from disk and never call
    `fetch_json` at all. Leaving `history/<id>-month` and `-annual` cold is what forces the
    walk through the one impure function this block needs to inspect.
    """
    checks.note("")
    checks.note(
        "HISTORY ROUTE BLOCKED — a 403 is `history_blocked`, and the override reaches the "
        "wire (D216)"
    )

    keys = ("PKMNSCAN_TCG_USER_AGENT", envfile.FROM_FILE_ENV)
    previous = {name: os.environ.get(name) for name in keys}
    os.environ.pop("PKMNSCAN_TCG_USER_AGENT", None)

    env_before = (envfile.ENV_FILE, set(envfile._from_file), envfile._loaded)
    envfile.ENV_FILE = Path(tempfile.gettempdir()) / "t7-history-blocked-no-such.env"
    envfile._from_file.clear()
    os.environ.pop(envfile.FROM_FILE_ENV, None)
    envfile._loaded = False

    seen_agents: list = []
    real_urlopen = urllib.request.urlopen

    def blocked_urlopen(request, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        seen_agents.append(request.get_header("User-agent"))
        raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, io.BytesIO(b""))

    with isolated_home():
        run_dir = runs.create("t7-history-blocked")
        for _ in range(1):
            capture_server.do_capture(capture_payload(7, game="riftbound"))
        with Store().write() as snapshot:
            snapshot.inventory.set_state("7/1", master.IDENTIFIED)
            snapshot.inventory.cards["7/1"].game = "riftbound"
        run_dir.write_identifications(
            {
                "prompt_fingerprint": "t7-history-blocked",
                "cards": {
                    "7/1": {
                        "photo": run_photo(7, 1),
                        "box": 7,
                        "index": 1,
                        "set_hint": None,
                        "metadata_finish": "foil",
                        "status": "ok",
                        "error": None,
                        "identification": {
                            "name": "Vilemaw",
                            "number": "060/219",
                            "printed_total": "219",
                            "confidence": "high",
                            "finish": "foil",
                        },
                    }
                },
            }
        )
        command(checks, "join", str(run_dir.directory), "--export", str(RIFTBOUND_EXPORT))
        name = run_dir.directory.name

        # ONLY THE CATALOG HOPS ARE WARM. The history slug is deliberately absent, so
        # `Market.history` reaches `self._fetch(url)` — the real `fetch_json` — rather than
        # answering from disk.
        directory = pipeline_routes.market_cache_dir()
        at = time.time()
        for slug, payload in (
            ("tcgcsv/categories", {"results": [{"categoryId": 89,
                                                "name": "Riftbound League of Legends Trading "
                                                        "Card Game"}]}),
            ("tcgcsv/89/groups", {"results": [{"groupId": 24560, "name": "Unleashed"}]}),
            ("tcgcsv/89/24560/products", json.loads(TCGCSV_PRODUCTS.read_text("utf-8"))),
        ):
            path = directory / f"{slug}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"fetched_at": at, "payload": payload}), "utf-8")

        urllib.request.urlopen = blocked_urlopen
        try:
            try:
                pipeline_routes.do_pipeline_history(name, "9189317")
                checks.ok(False, "a 403 refuses rather than answering", "it answered instead")
            except pipeline_routes.PipelineRefusal as refusal:
                checks.equal(
                    refusal.code,
                    "history_blocked",
                    "A 403 FROM infinite-api REFUSES AS `history_blocked` — never folded "
                    "into `history_unreachable`, whose whole meaning (D278) is that nothing "
                    "is wrong with the run",
                )
                checks.ok(
                    "browser signature" in str(refusal),
                    "...and the refusal NAMES THE REMEDY, the browser signature setting, in plain words (D171, D196)",
                    str(refusal),
                )
            checks.ok(
                bool(seen_agents) and seen_agents[-1] == pricehistory.USER_AGENT,
                "WITH NOTHING SET, the request that reached the (patched) socket carried "
                "the module's own honest default",
                seen_agents,
            )

            # THE OVERRIDE, SET LIVE — `get_live` is what `_history_user_agent` reads, so a
            # value that appears in `.env` after the process started still takes effect,
            # the same guarantee D65 built `_agent()` on.
            os.environ["PKMNSCAN_TCG_USER_AGENT"] = "pkmnscan-t7-browser-stand-in/1"
            try:
                pipeline_routes.do_pipeline_history(name, "9189317")
                checks.ok(False, "still 403, still refuses", "it answered instead")
            except pipeline_routes.PipelineRefusal as refusal:
                checks.equal(
                    refusal.code,
                    "history_blocked",
                    "...still `history_blocked` once the override is set — the stub still "
                    "answers 403 regardless of who is asking",
                )
            checks.equal(
                seen_agents[-1],
                "pkmnscan-t7-browser-stand-in/1",
                "AND WITH THE OVERRIDE SET, THE HEADER CHANGES — `PKMNSCAN_TCG_USER_AGENT` "
                "reaches the request through `server/pipeline_routes.py:_history_user_agent`, "
                "not only through `pipeline/pricehistory.py`'s own default",
            )
        finally:
            urllib.request.urlopen = real_urlopen
            envfile.ENV_FILE, restore_from_file, envfile._loaded = env_before
            envfile._from_file.clear()
            envfile._from_file.update(restore_from_file)
            for env_name, value in previous.items():
                if value is None:
                    os.environ.pop(env_name, None)
                else:
                    os.environ[env_name] = value


def check_price_history(checks: Checks) -> None:
    """`pipeline/pricehistory.py` — the sku -> productId walk, and the readings over it.

    OFFLINE, ALWAYS. Every assertion below runs against two committed fixtures and a
    fetcher this section supplies, so the harness opens no socket — which is not a style
    preference. This test runs behind the Stop hook at the end of every turn, and a case
    that reached a third party's server would put a stranger's uptime on the path that
    decides whether work is done, and would hammer a free public mirror once per turn.
    `fetch_json` is the only impure function in that module for exactly this reason.

    WHAT IS REAL HERE AND WHAT IS CONSTRUCTED, because the two prove different things and
    the file should not have to be read to tell them apart.

      REAL       `fixtures/tcgcsv_riftbound_unleashed_products.json`, a verbatim slice of
                 tcgcsv's Unleashed products, and
                 `fixtures/tcgplayer_price_history_vilemaw_month.json`, a verbatim capture
                 of the endpoint's answer for productId 684125. These carry the SHAPE — the
                 numbers arriving as strings, `"0"` written into a bucket that sold nothing,
                 and the buckets arriving NEWEST FIRST — and no invented payload would have
                 any of those wrong in the same way.
      CONSTRUCTED The arithmetic. A real series' VWAP is a number nobody can check by hand,
                 so every metric below is asserted against small literal buckets whose
                 answer is computable in the assertion's own label. A fixture cannot tell a
                 correct weighted mean from a plausible one.

    THE CASE THAT WOULD FAIL SILENTLY IS THE BUCKET ORDER, and it is why the real capture is
    committed rather than described. The endpoint sends newest-first; `momentum` subtracts
    one end of the list from the other; so a parser that trusted the wire order would report
    every rising card as falling, with no exception, no missing field and nothing on screen
    to see. The fixture is asserted to be newest-first ON DISK and the parse is asserted to
    be oldest-first, so the day the endpoint changes its mind the first assertion goes red
    and says so, rather than the second one quietly starting to pass for a new reason.

    WHAT THIS SECTION DOES NOT COVER, named so a green harness is not misread: whether the
    endpoint is still public, whether tcgcsv still mirrors these groups, and whether the
    figures are right. All three are facts about someone else's server on the day you ask,
    and no committed fixture can hold them. What is asserted is that the walk, the parse and
    the arithmetic are what this repo says they are.
    """
    checks.note("")
    checks.note("PRICE HISTORY — pipeline/pricehistory.py, the catalog walk and the readings")

    products_fixture = TCGCSV_PRODUCTS
    history_fixture = PRICE_HISTORY
    checks.ok(products_fixture.exists(), f"{products_fixture.name} is committed")
    checks.ok(history_fixture.exists(), f"{history_fixture.name} is committed")
    checks.ok(TCGCSV_PRICES.exists(), f"{TCGCSV_PRICES.name} is committed")
    if not all(f.exists() for f in (products_fixture, history_fixture, TCGCSV_PRICES)):
        return

    products_payload = json.loads(products_fixture.read_text("utf-8"))
    history_payload = json.loads(history_fixture.read_text("utf-8"))
    prices_payload = json.loads(TCGCSV_PRICES.read_text("utf-8"))

    # ------------------------------------------------------------------ the join, on real bytes
    #
    # The rows are lifted out of the committed Riftbound export by SKU rather than written
    # here, so the two halves of the join are both ground truth and neither was authored to
    # agree with the other. `_riftbound_row` refuses a SKU the export does not carry, which
    # is what stops a typo here from reading as a join failure there.
    index = pricehistory.ProductIndex.build(products_payload["results"])

    vilemaw = _riftbound_row("9189317")
    checks.equal(
        index.find(vilemaw[tcgcsv.NUMBER_COLUMN], vilemaw[tcgcsv.NAME_COLUMN]),
        684125,
        "Vilemaw 060/219 resolves to productId 684125 — the verification case, export row "
        "to mirror product, with nothing fetched",
    )
    moonfall = _riftbound_row("9191486")
    checks.equal(
        index.find(moonfall[tcgcsv.NUMBER_COLUMN], moonfall[tcgcsv.NAME_COLUMN]),
        684527,
        "Moonfall 198/219 resolves to productId 684527",
    )

    # `number_index_key` ON BOTH SIDES, which is the rule this join borrows and the one that
    # was a silent zero-join in `pipeline/join.py` before D-era `number_index_key` existed.
    # The mirror writes `060/219`; an export or a model that wrote `60/219` is the same card,
    # and a match that required the padding would miss every one of them.
    checks.equal(
        index.find("60/219", "Vilemaw"),
        684125,
        "an unpadded `60/219` finds the same product as `060/219` — number_index_key folds "
        "both sides, which is what stops a padding difference being a whole-set miss",
    )

    # THE NAME RUNG, on the case it actually serves. Measured across all four committed
    # exports, every one of the 355 products it resolves carries a BLANK `Number` — sealed
    # product, code cards and DON!! cards, which print no collector number at all. Not one
    # row WITH a number has ever fallen through to it.
    checks.equal(
        index.find("", "Unleashed - Booster Pack"),
        678149,
        "a blank-Number row resolves by name — the rung's whole domain, and the reason it "
        "is reached last rather than not at all",
    )

    # AND IT REFUSES RATHER THAN GUESSING. Constructed, because the real mirror carries no
    # such collision in this group and this is precisely the case that must not be left to
    # whether one ever turns up.
    twins = pricehistory.ProductIndex.build([
        {"productId": 1, "name": "Twin", "extendedData": [{"name": "Number", "value": "007/219"}]},
        {"productId": 2, "name": "Twin", "extendedData": [{"name": "Number", "value": "007/219"}]},
    ])
    checks.equal(
        twins.find("007/219", "Twin"),
        None,
        "two products sharing a number AND a name answer None — a refusal a caller can act "
        "on, never the first of two, which is geometry.detect_card's rule for the same reason",
    )
    tiebreak = pricehistory.ProductIndex.build([
        {"productId": 1, "name": "Alpha", "extendedData": [{"name": "Number", "value": "007/219"}]},
        {"productId": 2, "name": "Beta", "extendedData": [{"name": "Number", "value": "007/219"}]},
    ])
    checks.equal(
        tiebreak.find("007/219", "Beta"),
        2,
        "two products sharing a number are told apart by name — the tiebreak, which is why "
        "the name is consulted before the refusal rather than only after it",
    )

    # THE GLUED-SET-CODE REPAIR, REACHED ON A MISS BEFORE THE NAME RUNG
    # (D234). `pipeline/join.py:_walk` has always tried
    # `_repair_set_code` before falling to the name rung; `ProductIndex.find` did not, so a
    # Riftbound read glued a set code onto the front of (`SFD • 013/221`,
    # `SPD 208/221`) refused here even though the SAME shape resolves cleanly in the real
    # listing join. Both separator shapes D55/D67 cover, over a constructed group that
    # mirrors the real refusal (`Blast Cadet` `013/221` in `Spiritforged`).
    # TWO products, and the query's NAME MATCHES NEITHER — so the name rung (which would
    # otherwise resolve a single-product index by name alone, hiding whether the number
    # repair ever ran) answers empty, and only the repaired NUMBER can find the row.
    spiritforged = pricehistory.ProductIndex.build([
        {"productId": 701, "name": "Blast Cadet",
         "extendedData": [{"name": "Number", "value": "013/221"}]},
        {"productId": 703, "name": "Warden's Bulwark",
         "extendedData": [{"name": "Number", "value": "099/221"}]},
    ])
    checks.equal(
        spiritforged.find("SFD • 013/221", "No Such Name"),
        701,
        "a dot-glued set code (`SFD • 013/221`) is repaired and resolves off the NUMBER "
        "alone, with a name that matches nothing in the index — the real refused shape from "
        "the 2026-09-20 archive sweep, and proof the name rung is not what answered it",
    )
    checks.equal(
        spiritforged.find("SPD 999/221", "No Such Name"),
        None,
        "a space-glued set code against a group that does not carry 999/221 still refuses — "
        "the repair tries the stripped key, it does not manufacture a row",
    )
    checks.equal(
        pricehistory.ProductIndex.build([
            {"productId": 702, "name": "Forge of the Flint",
             "extendedData": [{"name": "Number", "value": "208/221"}]},
            {"productId": 704, "name": "Another Card",
             "extendedData": [{"name": "Number", "value": "017/221"}]},
        ]).find("SPD 208/221", "No Such Name"),
        702,
        "and the SAME space-glued shape resolves off the number once the group actually "
        "carries 208/221 — the other real refused shape from that sweep, a plain space with "
        "no punctuation at all, which `store/numbers.py:_SET_CODE_PREFIX` did not match "
        "before this widening",
    )
    checks.equal(
        pricehistory.ProductIndex.build([
            {"productId": 1, "name": "Alpha", "extendedData": [{"name": "Number", "value": "013/221"}]},
        ]).find("013/221", "Alpha"),
        1,
        "MUTATION GUARD: a number that already matches is never handed to the repair — an "
        "unglued number behaves exactly as before",
    )

    # ------------------------------------------ D254: a caller
    # that already has a productId in hand — the archive's own already-verified answer for
    # this SKU, `store/pricearchive.py:Bucket.product_id` — skips resolving the row at all.
    # The owner's ruling (2026-09-23) closed a session's earlier attempt to weigh a card's
    # own READ name against the number it found: the reviewer's re-measurement found 15 of
    # 20 new refusals had a correct old answer and 1 of 29 flips was wrong, because a
    # Riftbound "Champion, Title" card's read NAME is the unreliable field, not the number.
    # The fix is to never ask the card at all — resolve by the SKU, never by a read field —
    # and `pipeline/pricearchive.py:resolve_by_sku`/`merged_export_rows_by_sku` carry that;
    # this proves the primitive they are built on, in `Market` itself, with no store and no
    # `pipeline/pricearchive.py` import at all.
    #
    # PROVEN WITH NO NETWORK AND NO CACHE, THE ROW ITSELF UNRESOLVABLE ON PURPOSE. A `Product
    # Line` no registry names would raise `NotResolvable` the moment `category_id` ran, and
    # `ranges=()` means `self.history` is never reached either — so a reading that succeeds
    # here, over this row, is proof the whole resolution walk was skipped, not proof it
    # happened to succeed.
    unresolvable_row = {
        tcgcsv.PRODUCT_LINE_COLUMN: "Not A Real Product Line",
        tcgcsv.SET_COLUMN: "Not A Real Set",
        tcgcsv.NUMBER_COLUMN: "999/999",
        tcgcsv.NAME_COLUMN: "Not A Real Name",
        tcgcsv.SKU_COLUMN: "9999999",
        tcgcsv.CONDITION_COLUMN: "Near Mint",
    }

    def _no_network(url):
        raise AssertionError(f"MUTATION: the network was reached at {url!r}")

    skip_market = pricehistory.Market(fetcher=_no_network)
    verified_reading = skip_market.reading_for_row(
        unresolvable_row, ranges=(), product_id=555
    )
    checks.equal(
        verified_reading.product_id, 555,
        "reading_for_row(product_id=555) trusts the given id as-is, over a row that would "
        "otherwise refuse — the archive-verified tier, D254",
    )
    checks.equal(
        verified_reading.series, {},
        "and asks for nothing over an empty ranges tuple — nothing here proves the walk "
        "ran and merely returned this id anyway",
    )
    batch_readings, batch_refusals = skip_market.readings_for_rows(
        [unresolvable_row], ranges=(), product_ids={"9999999": 777}
    )
    checks.equal(
        batch_readings["9999999"].product_id, 777,
        "readings_for_rows(product_ids=...) honours a verified id the same way, per SKU",
    )
    checks.ok(
        not batch_refusals,
        "and never refuses a row it was never asked to resolve",
        batch_refusals,
    )
    # MUTATION GUARD: the identical row, with NO verified id offered, refuses exactly as it
    # always has — proves the skip above is conditional on being HANDED an id, never a
    # general relaxation of `product_id_for_row`'s own refusal. A DIFFERENT market, whose
    # fetcher answers an ordinary empty catalogue rather than asserting on any call —
    # `product_id_for_row` DOES have to reach it here, legitimately, to fail on "no such
    # category" rather than on this test's own network trap.
    refusing_market = pricehistory.Market(fetcher=lambda url: {"results": []})
    raised = checks.raises(
        pricehistory.NotResolvable,
        lambda: refusing_market.reading_for_row(unresolvable_row, ranges=()),
        "MUTATION GUARD: the same row with no product_id given still refuses — "
        "product_id_for_row runs exactly as before when nothing was verified",
    )
    checks.ok(
        raised is not None and "Not A Real Product Line" in str(raised),
        "and the refusal names the row's own unresolvable Product Line, the ordinary "
        "resolution failure, proving product_id_for_row is what ran",
    )

    # A groups list cached before a set released: a miss refetches once and resolves; a set
    # missing from both still refuses.
    def _catalog(groups):
        def fetch(url):
            if url.endswith("/tcgplayer/categories"):
                return {"results": [{"categoryId": 3, "name": "Pokemon"}]}
            if url.endswith("/groups"):
                return {"results": groups()}
            raise AssertionError(url)
        return fetch

    old_groups = [{"groupId": 1, "name": "Old Set"}]
    live_groups = old_groups
    cache_home = Path(tempfile.mkdtemp())
    pricehistory.Market(
        cache_dir=cache_home, fetcher=_catalog(lambda: live_groups), courtesy_delay=0
    ).group_id(3, "Old Set")
    live_groups = old_groups + [{"groupId": 2, "name": "New Set"}]
    new_market = pricehistory.Market(
        cache_dir=cache_home, fetcher=_catalog(lambda: live_groups), courtesy_delay=0
    )
    checks.equal(
        new_market.group_id(3, "New Set"), 2,
        "a set missing from the cached groups list resolves after one refetch, no cache deletion",
    )
    checks.raises(
        pricehistory.NotResolvable,
        lambda: new_market.group_id(3, "Never Released"),
        "a set missing from the fresh list too still refuses",
    )
    requests_before = new_market.requests
    checks.raises(
        pricehistory.NotResolvable,
        lambda: new_market.group_id(3, "Never Released"),
        "and asks again for nothing: one refetch per instance, never one per card",
    )
    checks.equal(new_market.requests, requests_before, "the second miss spent no request")

    # Products miss, a failing host, and an empty refetch, on the same stubbed catalogue.
    live = {"groups": old_groups, "products": [{"productId": 10, "name": "Alpha"}], "fail": False}

    def _mirror(url):
        if live["fail"]:
            raise pricehistory.Unreachable("stub host down")
        if url.endswith("/tcgplayer/categories"):
            return {"results": [{"categoryId": 3, "name": "Pokemon"}]}
        if url.endswith("/groups"):
            return {"results": live["groups"]}
        return {"results": live["products"]}

    def _row(card):
        return {"Product Line": "Pokemon", "Set Name": "Old Set", "Number": "", "Product Name": card}

    products_home = Path(tempfile.mkdtemp())
    pricehistory.Market(cache_dir=products_home, fetcher=_mirror, courtesy_delay=0).product_id_for_row(_row("Alpha"))
    live["products"] = [{"productId": 10, "name": "Alpha"}, {"productId": 11, "name": "Bravo"}]
    checks.equal(
        pricehistory.Market(cache_dir=products_home, fetcher=_mirror, courtesy_delay=0).product_id_for_row(_row("Bravo")),
        11,
        "a card added to a cached product list resolves after one refetch",
    )
    live["fail"] = True
    down = pricehistory.Market(cache_dir=products_home, fetcher=_mirror, courtesy_delay=0)
    for card in ("Nope 1", "Nope 2", "Nope 3", "Nope 4", "Nope 5"):
        with contextlib.suppress(pricehistory.NotResolvable, pricehistory.Unreachable):
            down.product_id_for_row(_row(card))
    checks.equal(down.requests, 1, "a failing refetch makes exactly one request across many cards")
    live["fail"] = False
    live["products"] = []
    empty = pricehistory.Market(cache_dir=products_home, fetcher=_mirror, courtesy_delay=0)
    checks.raises(
        pricehistory.NotResolvable,
        lambda: empty.product_id_for_row(_row("Nope 6")),
        "a card in neither list still refuses",
    )
    checks.equal(
        pricehistory.Market(cache_dir=products_home, fetcher=_no_network, courtesy_delay=0).product_id_for_row(_row("Bravo")),
        11,
        "an empty refetch leaves the old cache intact, so a cached card still resolves",
    )

    # An EXPIRED groups cache (two days old): a failing host serves the old list in one
    # request; an empty payload does not replace it.
    clock = {"t": 1_000_000.0}
    aged_home = Path(tempfile.mkdtemp())
    live["fail"], live["products"] = False, [{"productId": 10, "name": "Alpha"}]
    live["groups"] = old_groups
    pricehistory.Market(
        cache_dir=aged_home, fetcher=_mirror, courtesy_delay=0, now=lambda: clock["t"]
    ).group_id(3, "Old Set")
    clock["t"] += 2 * 24 * 60 * 60
    live["fail"] = True
    aged = pricehistory.Market(
        cache_dir=aged_home, fetcher=_mirror, courtesy_delay=0, now=lambda: clock["t"]
    )
    resolved = [aged.group_id(3, "Old Set") for _ in range(20)]
    checks.equal(
        (resolved[-1], aged.requests), (1, 1),
        "an expired groups cache and a failing host: the old set still resolves, in 1 request across 20 cards",
    )
    live["fail"], live["groups"] = False, []
    emptied = pricehistory.Market(
        cache_dir=aged_home, fetcher=_mirror, courtesy_delay=0, now=lambda: clock["t"]
    )
    checks.equal(emptied.group_id(3, "Old Set"), 1, "an expired cache and an empty payload: the old list still resolves")
    checks.equal(
        pricehistory.Market(cache_dir=aged_home, fetcher=_no_network, courtesy_delay=0, now=lambda: 1_000_001.0).group_id(3, "Old Set"),
        1,
        "and the empty payload was never stored",
    )

    # ---------------------------------------------------------------- the parse, on real bytes
    #
    # THE ORDER ASSERTION IS THE POINT OF COMMITTING THIS FILE. Both halves, so a change
    # upstream is a red fixture rather than a quietly-passing parser.
    raw_buckets = history_payload["result"][0]["buckets"]
    checks.ok(
        raw_buckets[0]["bucketStartDate"] > raw_buckets[-1]["bucketStartDate"],
        "the endpoint's own bytes are NEWEST FIRST — asserted on the fixture, so the day "
        "that changes this goes red instead of the parser silently agreeing for a new reason",
    )

    series = pricehistory.parse_history(history_payload, 684125, "month")
    checks.equal(
        sorted(series),
        ["9189317", "9189318"],
        "one product's answer carries every condition of the card, keyed by skuId — which "
        "is what makes the last hop exact rather than a variant-string match",
    )

    near_mint = series["9189317"]
    starts = [b.start for b in near_mint.buckets]
    checks.ok(
        starts == sorted(starts),
        "Series.buckets is ASCENDING after parse — momentum subtracts one end from the "
        "other, so the wire order would invert every reading's sign with nothing to see",
    )
    checks.equal(
        (near_mint.total_quantity_sold, near_mint.total_transaction_count),
        (642, 528),
        "the endpoint's own totals are carried, not recomputed from the buckets",
    )
    checks.equal(
        near_mint.condition,
        "Near Mint",
        "the condition string comes off the result rather than being matched against",
    )

    # `"0"` IS NOT A PRICE, AND THE FIXTURE HOLDS BOTH SHAPES — which was found by writing
    # this assertion against the wrong SKU. The Near Mint card sold on all 30 days of the
    # capture, so it exercises nothing here; the Lightly Played one beside it sold on 16 and
    # its 14 quiet days each write `"0"` into low and high beside a real standing
    # `marketPrice` of $19.54. Reading those zeros as prices drags every weighted mean
    # below toward zero, which is the defect, and only the quiet card can see it.
    checks.equal(
        len([b for b in near_mint.buckets if not b.sold]),
        0,
        "the Near Mint card sold on every day of the capture — recorded because it is why "
        "the zero-price case below is asserted on its Lightly Played sibling instead",
    )
    lightly_played = series["9189318"]
    quiet = [b for b in lightly_played.buckets if not b.sold]
    checks.equal(len(quiet), 14, "...and the Lightly Played card has 14 days that sold nothing")
    checks.ok(
        all(b.low is None and b.high is None for b in quiet),
        "a bucket that sold nothing has NO low and NO high — the endpoint writes \"0\" "
        "there, and D9's rule is that a missing price is unknown rather than cheap",
    )
    checks.ok(
        all(b.market is not None for b in quiet),
        "...and it keeps its standing marketPrice, which is why `sold` filters the means "
        "rather than the parse dropping the bucket",
    )

    # ------------------------------------------------------------- the arithmetic, constructed
    #
    # Hand-computable on purpose. Two buckets, 10 units at $10 and 30 units at $20: the
    # weighted mean is (100 + 600) / 40 = $17.50 and the unweighted mean is $15.00, so a
    # build that forgot to weight lands on a different number rather than a rounder one.
    def bucket(day: int, market, quantity: int, low=None, high=None, transactions: int = 0):
        return {
            "bucketStartDate": f"2026-08-{day:02d}",
            "marketPrice": market,
            "quantitySold": str(quantity),
            "transactionCount": str(transactions or quantity),
            "lowSalePrice": low if low is not None else "0",
            "highSalePrice": high if high is not None else "0",
        }

    def made(buckets, sold=None, txn=None):
        return pricehistory.Series.parse(
            {
                "skuId": "1",
                "variant": "Foil",
                "condition": "Near Mint",
                "language": "English",
                "totalQuantitySold": str(sum(int(b["quantitySold"]) for b in buckets) if sold is None else sold),
                "totalTransactionCount": str(txn if txn is not None else 1),
                "buckets": buckets,
            },
            product_id=1,
            range_="month",
        )

    weighted = made([
        bucket(1, "10.00", 10, low="9.00", high="11.00"),
        bucket(2, "20.00", 30, low="18.00", high="24.00"),
    ])
    checks.equal(
        weighted.vwap,
        Decimal("17.50"),
        "vwap weights by quantity — (10x$10 + 30x$20) / 40 = $17.50, where the unweighted "
        "mean is $15.00, so a build that forgot the weights lands somewhere else",
    )
    bound = weighted.bound
    checks.equal(
        (bound.low, bound.high),
        (Decimal("15.75"), Decimal("20.75")),
        "the bound weights low and high the same way — (10x$9 + 30x$18)/40 and "
        "(10x$11 + 30x$24)/40",
    )
    checks.ok(
        bound.low <= weighted.vwap <= bound.high,
        "the point estimate lies inside its own bound — the sanity check the bound exists "
        "to be, and the one thing about it that is a result",
    )
    checks.equal(
        (bound.width_of_vwap, bound.width_of_low),
        (Decimal("0.2857"), Decimal("0.3175")),
        "both widths are named and both are reported — one card is honestly '29% wide' and "
        "'32% wide', and a bare percentage invites the two to be read as a disagreement",
    )
    checks.equal(
        weighted.dispersion,
        Decimal("5.00"),
        "dispersion is the volume-weighted within-bucket spread — (10x$2 + 30x$6)/40 — "
        "which measures sellers disagreeing on one day, not the range moving",
    )

    # A BUCKET THAT SOLD NOTHING CONTRIBUTES NOTHING, asserted by adding one carrying a
    # market price far off the mean. It is the same series otherwise, so any drift in these
    # numbers is the filter failing rather than the arithmetic.
    with_quiet = made([
        bucket(1, "10.00", 10, low="9.00", high="11.00"),
        bucket(2, "20.00", 30, low="18.00", high="24.00"),
        bucket(3, "99.00", 0),
    ])
    checks.equal(
        with_quiet.vwap,
        Decimal("17.50"),
        "a $99 bucket that sold nothing moves the vwap not at all — it carries TCGplayer's "
        "opinion, and weighting an opinion equally with a transaction is the defect",
    )
    checks.equal(
        with_quiet.latest_market,
        Decimal("99.00"),
        "...and `latest_market` still reports it, because that is the figure the export's "
        "own standing `TCG Market Price` column is comparable to",
    )

    # NO SALES IS None AND NEVER ZERO. D9 is emphatic that a missing price is an unknown
    # price rather than a low one, and $0.00 is the reading that hands a chase card away at
    # the floor.
    silent = made([bucket(1, "10.00", 0), bucket(2, "10.00", 0)])
    checks.equal(silent.vwap, None, "a series with no sales has no vwap — None, never $0.00")
    checks.equal(silent.bound, None, "...and no bound, for the same reason")
    checks.equal(silent.dispersion, None, "...and no dispersion")

    # MOMENTUM: POSITIVE IS RISING. Two windows of one, $10 then $20.
    rising = made([bucket(1, "10.00", 5), bucket(2, "20.00", 5)])
    move = rising.momentum(window=1)
    checks.equal(
        (move.early, move.late, move.change, move.fraction),
        (Decimal("10.00"), Decimal("20.00"), Decimal("10.00"), Decimal("1.0000")),
        "momentum reads early -> late and POSITIVE IS RISING — the one fact a signed number "
        "has to carry, and the one the wire's bucket order would have inverted",
    )
    checks.equal(
        rising.momentum(window=5).change,
        None,
        "a series with fewer sold buckets than one window answers None on both ends — it "
        "may not compare a window against itself and report zero as a measurement",
    )

    # LIQUIDITY AND UNITS PER TRANSACTION are the endpoint's totals, not a recount.
    dealt = made([bucket(1, "10.00", 100)], sold=1763, txn=1455)
    checks.equal(dealt.liquidity, 1763, "liquidity is the range's own total, unrecomputed")
    checks.equal(
        dealt.units_per_transaction,
        Decimal("1.212"),
        "units per transaction is 1763/1455 — the number that says whether the D7 live cap "
        "of four is binding on this card or nowhere near it",
    )
    checks.equal(
        made([bucket(1, "10.00", 0)], sold=0, txn=0).units_per_transaction,
        None,
        "no transactions is None rather than a division by zero",
    )

    # ------------------------------------------------------- the wire, with a fetcher we own
    #
    # `result: null` IS WHAT AN UNKNOWN PRODUCT ANSWERS, at HTTP 200. Measured. A caller
    # that checked the status and iterated the result raises a TypeError on a typo'd id and
    # reads it as a bug in the reader; an empty mapping is the honest answer and is the same
    # one a real product with no sales gives.
    checks.equal(
        pricehistory.parse_history({"count": 0, "result": None}, 1, "month"),
        {},
        "an unknown productId answers HTTP 200 with `result: null` — parsed as no series, "
        "never as an exception",
    )

    checks.raises(
        pricehistory.UnknownRange,
        lambda: pricehistory.history_url(684125, "week"),
        "`week` is refused by name — it is not a range, it is an HTTP 400, and a range that "
        "silently returned nothing would read as a card with no sales",
    )
    checks.ok(
        pricehistory.history_url(684125, "annual").endswith(
            "/price/history/684125/detailed?range=annual"
        ),
        "the history URL is the endpoint this module documents",
    )

    # THE WHOLE WALK, with every fetch answered from the committed fixtures. This is the
    # only place the three catalog hops and the SKU pick are exercised together, and it is
    # the shape a caller actually uses.
    served = {
        "https://tcgcsv.com/tcgplayer/categories": {
            "results": [
                {"categoryId": 89, "name": "Riftbound League of Legends Trading Card Game"},
                {"categoryId": 3, "name": "Pokemon"},
            ]
        },
        "https://tcgcsv.com/tcgplayer/89/groups": {
            "results": [{"groupId": 24560, "name": "Unleashed"}]
        },
        "https://tcgcsv.com/tcgplayer/89/24560/products": products_payload,
        pricehistory.history_url(684125, "month"): history_payload,
    }
    asked = []

    def serve(url: str) -> dict:
        asked.append(url)
        if url not in served:
            raise pricehistory.Unreachable(f"the harness serves no {url}")
        return served[url]

    with isolated_home() as home:
        cache_dir = home / "market"
        market = pricehistory.Market(
            cache_dir=cache_dir, fetcher=serve, courtesy_delay=0
        )
        reading = market.reading_for_row(vilemaw, ranges=("month",))
        checks.equal(
            (reading.sku, reading.product_id),
            ("9189317", 684125),
            "the walk carries the row's OWN TCGplayer Id through and picks it out of the "
            "product's answer by its number — no variant or condition string is matched",
        )
        checks.equal(
            reading.of("month").condition,
            "Near Mint",
            "...and the series it picked is this SKU's, not the Lightly Played one beside it",
        )
        checks.equal(
            market.category_id("Riftbound League of Legends Trading Card Game"),
            89,
            "the category is resolved BY NAME off the `Product Line` cell games.py already "
            "authors — a table of integers here would be a second per-game fact in a second "
            "file, and it would fail separately from the export rather than with it",
        )

        first_pass = len(asked)
        checks.ok(first_pass == 4, f"the walk cost four requests, not more ({first_pass})")

        # ONE REQUEST ANSWERS A WHOLE GROUP, which is the only shape the host offers — there
        # is no per-product price route — and is why a second card in the same set is free.
        served["https://tcgcsv.com/tcgplayer/89/24560/prices"] = prices_payload
        before_prices = len(asked)
        group_prices = market.prices(89, 24560)
        checks.equal(
            len(asked) - before_prices,
            1,
            "one request prices the whole group, and asking again costs nothing",
        )
        market.prices(89, 24560)
        checks.equal(len(asked) - before_prices, 1, "...asserted by asking twice")
        checks.equal(
            group_prices[(684125, "Foil")].market,
            Decimal("23.8"),
            "...and the reader answers through the same cache as the catalog hops",
        )

        # THE CACHE IS ON REAL DISK AND A SECOND MARKET READS IT. The in-memory dict would
        # pass a same-object re-read while the file was never written, which is the version
        # of this that looks green and saves nothing.
        # The baseline is taken HERE rather than reused from `first_pass`, because anything
        # added between the two would make this assertion fail for a reason that has nothing
        # to do with the cache — which it did, the moment the prices case above landed.
        before_repeat = len(asked)
        again = pricehistory.Market(cache_dir=cache_dir, fetcher=serve, courtesy_delay=0)
        repeat = again.reading_for_row(vilemaw, ranges=("month",))
        checks.equal(
            len(asked),
            before_repeat,
            "a second Market over the same cache directory fetches NOTHING — the cache is "
            "on disk, not in one object's memory",
        )
        checks.equal(
            repeat.of("month").vwap,
            reading.of("month").vwap,
            "...and answers the same reading",
        )

        # A CORRUPT ENTRY IS A CACHE MISS, NEVER A REFUSAL. This directory is derived and
        # deletable by construction, so the only honest response to bytes we cannot read is
        # to go and ask again.
        # The `next(...)` and the try/except are not defensive padding: a build that never
        # wrote the cache has no file to corrupt and a build that raises on one propagates
        # out of the section, and in both cases the assertion that should have reported the
        # defect is the one that never runs. Reporting beats aborting in a suite whose whole
        # job is to say what state everything is in.
        cached_files = sorted(cache_dir.rglob("*.json"))
        if not checks.ok(bool(cached_files), "the cache wrote files to look at"):
            return
        cached_files[0].write_text("{not json", "utf-8")
        third = pricehistory.Market(cache_dir=cache_dir, fetcher=serve, courtesy_delay=0)
        before = len(asked)
        try:
            third.reading_for_row(vilemaw, ranges=("month",))
            refetched = len(asked) > before
        except Exception as exc:  # noqa: BLE001 - the raise IS the defect being asserted
            refetched = False
            checks.note(f"re-reading a corrupt cache raised {type(exc).__name__}: {exc}")
        checks.ok(
            refetched,
            "a corrupt cache file is re-fetched rather than raising — the directory is "
            "derived, so unreadable bytes are a miss and not a fault",
        )

        # BOTH DIRECTIONS, WHICH IS CLAUDE.md's HARD RULE. A row this cannot resolve is
        # named with the reason, never dropped — the promise JoinReport already makes about
        # a card that finds no catalog row, applied to a reader that will one day feed a
        # screen.
        stranger = dict(vilemaw)
        stranger[tcgcsv.SKU_COLUMN] = "9999999"
        stranger[tcgcsv.NUMBER_COLUMN] = "999/219"
        stranger[tcgcsv.NAME_COLUMN] = "Nothing By This Name"
        readings, refusals = pricehistory.Market(
            cache_dir=cache_dir, fetcher=serve, courtesy_delay=0
        ).readings_for_rows([vilemaw, stranger], ranges=("month",))
        checks.equal(
            sorted(readings),
            ["9189317"],
            "a batch answers the rows it could resolve",
        )
        checks.equal(
            sorted(refusals),
            ["9999999"],
            "...and NAMES the one it could not, rather than dropping it — a silent drop is "
            "what CLAUDE.md forbids in as many words",
        )
        checks.ok(
            "Nothing By This Name" in refusals.get("9999999", ""),
            "...and the refusal says which card and why",
            refusals.get("9999999", ""),
        )

    # ------------------------------------------------ tcgcsv /prices: current, and NOT SKU-level
    #
    # A SEPARATE CAPABILITY WITH A HARD LIMIT, and the limit is what these cases are for. The
    # host also serves current prices per group, which maps onto columns the export already
    # has — so the only thing it buys is RECENCY, and the only way it can mislead is by being
    # read as SKU-level. It is not: `subTypeName` is the PRINTING.
    prices = pricehistory.parse_prices(prices_payload)

    # THE KEY IS COMPOSITE AND THE FIXTURE PROVES IT NEEDS TO BE. Arena Kingpin (685942) is
    # stocked in both printings at different prices, so a productId-only key would keep
    # whichever row came last and silently price a Normal card as a Foil.
    def printing_market(product_id: int, printing: str):
        # `.get` rather than `[]`: a build that dropped the printing from the key is exactly
        # what this case exists to catch, and it must REPORT that rather than raise a KeyError
        # partway through the section and take the assertions after it down.
        row = prices.get((product_id, printing))
        return None if row is None else row.market

    checks.equal(
        (printing_market(685942, "Foil"), printing_market(685942, "Normal")),
        (Decimal("0.11"), Decimal("0.08")),
        "one product carries a Foil row AND a Normal row at different prices — which is why "
        "the key is (productId, printing) and not productId",
    )
    checks.equal(
        printing_market(684125, "Foil"),
        Decimal("23.8"),
        "Vilemaw's current market comes off the printing row",
    )

    # A NULL IS NOT A ZERO. `directLowPrice` arrives as JSON null on every row of this
    # fixture, and D9's rule decides it: a missing price is an unknown price, not a low one.
    # $0.00 here is what would undercut a card to the floor against a direct low that does
    # not exist.
    checks.ok(
        all(row.direct_low is None for row in prices.values()),
        "a null directLowPrice parses to None, never Decimal(0) — the same rule that keeps "
        "an empty market cell out of the sub-threshold bucket",
    )

    # THE ABSENCE IS THE ASSERTION. This payload carries no `TCGplayer Id` and no
    # `Total Quantity` — the SKU D11's import matches on and the live quantity D7's cap is
    # measured against — so it can supplement an export and can never replace one. Asserted
    # on the raw payload rather than on the parse, because the parse could not show it.
    fields = {key for row in prices_payload["results"] for key in row}
    checks.ok(
        tcgcsv.SKU_COLUMN not in fields and tcgcsv.LIVE_QUANTITY_COLUMN not in fields,
        "the prices payload carries neither the SKU nor the live quantity — the two columns "
        "the listing path is built on, and the reason this never replaces an export",
        str(sorted(fields)),
    )
    checks.equal(
        sorted({row["subTypeName"] for row in prices_payload["results"]}),
        ["Foil", "Normal"],
        "`subTypeName` is the PRINTING and never the condition — Vilemaw is five export rows "
        "by condition against one row here, so this can only ever speak for Near Mint",
    )

    # `misc` HAS NO CATALOG AND THEREFORE NO HISTORY, and the predicate says so before the
    # walk rather than raising inside it. D22 gives that game `product_line: None` by
    # construction, so there is no cell to look a category up by.
    checks.ok(
        pricehistory.catalogued_row(vilemaw),
        "a Riftbound row is catalogued — its Product Line cell is one games.py authors",
    )
    checks.ok(
        not pricehistory.catalogued_row({tcgcsv.PRODUCT_LINE_COLUMN: "Yu-Gi-Oh!"}),
        "a product line no registered game names is not catalogued — D22's `misc` case, "
        "answered where the caller can act on it rather than inside the walk",
    )

    # ---------------------------------- the escape hatch, and the named block (D-tcg-
    # ---------------------------------- price-history-user-agent-block)
    #
    # A REAL SOCKET, BUT NEVER A THIRD PARTY. Everything above is offline by a fetcher
    # function, which is the right shape for the WALK — but the property under test here is
    # the HEADER `fetch_json` actually puts on the wire and the EXCEPTION it raises on a
    # 403, and no fixture dictionary can stand in for either. So this block starts its own
    # `http.server` on loopback and stops there — never `tcgcsv.com`, never `infinite-api`.
    agent_seen = {"value": None}
    stub = {"mode": "ok"}

    class Agent(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # noqa: A003
            pass

        def do_GET(self):  # noqa: N802
            agent_seen["value"] = self.headers.get("User-Agent")
            if stub["mode"] == "blocked":
                self.send_response(403)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if stub["mode"] == "boom":
                self.send_response(500)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            body = b'{"ok": true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    agent_server = http.server.HTTPServer(("127.0.0.1", 0), Agent)
    _spawn_server(agent_server)
    agent_url = f"http://127.0.0.1:{agent_server.server_address[1]}/"

    checks.equal(
        pricehistory.fetch_json(agent_url),
        {"ok": True},
        "fetch_json with no override still answers — the default holds when nothing sets it",
    )
    checks.equal(
        agent_seen["value"],
        pricehistory.USER_AGENT,
        "...and the header the server actually SAW is the module's own honest string, not "
        "a claim about it — a WAF's answer is measured off the header, not off this docstring",
    )

    pricehistory.fetch_json(agent_url, user_agent="pkmnscan-t7-probe/1")
    checks.equal(
        agent_seen["value"],
        "pkmnscan-t7-probe/1",
        "AN EXPLICIT user_agent REPLACES THE DEFAULT — the same shape `Market`'s own "
        "`cache_dir` argument already takes, per that class's header: passed in, never "
        "discovered, because this module may not read `.env` for itself",
    )

    stub["mode"] = "blocked"
    try:
        pricehistory.fetch_json(agent_url, user_agent="pkmnscan-t7-secret-agent/1")
        checks.ok(False, "a 403 refuses rather than answering", "it answered")
    except pricehistory.Blocked as exc:
        checks.equal(
            agent_seen["value"],
            "pkmnscan-t7-secret-agent/1",
            "the override still reached the wire — the host refused it, not this module",
        )
        checks.ok(
            "browser signature" in str(exc),
            "A 403 RAISES `Blocked` AND NAMES THE REMEDY — the browser signature setting, so a "
            "refusal that reaches a caller says what to do next (D171)",
            str(exc),
        )
        checks.ok(
            "pkmnscan-t7-secret-agent" not in str(exc),
            "...and NEVER ECHOES THE VALUE presented — the message names the KNOB, never "
            "what was turned",
            str(exc),
        )
        checks.ok(
            not isinstance(exc, pricehistory.Unreachable),
            "...and `Blocked` is a SIBLING of `Unreachable`, never a subclass — "
            "`history_unreachable`'s whole meaning (D278) is that nothing is wrong with the "
            "run, and a 403 says the opposite: the client presenting itself is declined",
        )
    except pricehistory.Unreachable:
        checks.ok(False, "a 403 must be `Blocked`, never fold into `Unreachable`", "it did")

    # A DIFFERENT REFUSAL IS STILL `Unreachable`, UNCHANGED — asserted so a change that made
    # every status `Blocked` would go red here rather than passing by never being tried.
    stub["mode"] = "boom"
    try:
        pricehistory.fetch_json(agent_url)
        checks.ok(False, "a 500 refuses rather than answering", "it answered")
    except pricehistory.Unreachable:
        checks.ok(True, "...and a 500 is still `Unreachable` — only a 403 gets its own name")
    except pricehistory.Blocked:
        checks.ok(False, "a 500 must not be reported as `Blocked`", "it was")


def check_product_sheet_unsent_sku(checks: Checks) -> None:
    """`GET /pipeline/products/<sku>/history` for a SKU the worklist shows but no card carries.

    A card joined to a SKU has an empty `cards.sku` until emit or confirm stamps it. The
    product row must then come from the `skus` table; a SKU in no table still refuses.
    """
    from harness.tests.t7.common import _seed_sku_table
    from store.pricearchive import Bucket

    checks.note("")
    checks.note("PRODUCT SHEET — a SKU in the skus table that no card carries yet opens")
    with isolated_home():
        capture_server.do_capture(capture_payload(7, game="riftbound"))
        with Store().write() as snapshot:
            _seed_sku_table(snapshot, [{
                "sku": "7700001", "name": "Unsent Test Dragon", "set": "Test Set",
                "number": "001", "condition": "Near Mint Foil",
            }], product_line="Riftbound")
            bucket = Bucket("7700001", 4242, "month", 1, "2026-09-10", "0.50", 5, 2, None, None, 0)
            snapshot.archive.upsert({"7700001:month:2026-09-10": bucket})
            checks.ok(all(not c.sku for c in snapshot.inventory.cards.values()),
                      "fixture: no card carries the SKU")
        try:
            got = pipeline_routes.do_product_history("7700001")
        except pipeline_routes.PipelineRefusal as exc:
            got = {"refused": exc.code}
        checks.ok(got.get("name") == "Unsent Test Dragon" and "Foil" in str(got.get("condition")),
                  f"a catalogued SKU no card carries answers with its catalog row, got {got.get('refused') or got.get('name')}")
        try:
            pipeline_routes.do_product_history("9999999")
            code = None
        except pipeline_routes.PipelineRefusal as exc:
            code = exc.code
        checks.ok(code == "sku_unknown", "a SKU in no table still refuses sku_unknown")


CHECKS = (
    check_price_history,
    check_history_route,
    check_history_blocked_route,
    check_product_sheet_unsent_sku,
)
