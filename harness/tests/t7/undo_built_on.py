"""T7 group: undo until built on.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.
"""

from __future__ import annotations

import os
import re
import threading
import time

from datetime import datetime, timedelta, timezone
from pathlib import Path
from harness.tests import Checks
from cli import cmd_reprice, runs
from pipeline import corpus, tcgcsv
from server import capture_server, pipeline_routes
from store import db, files, master, photos
# `orders` is already `pipeline.orders` above. The store's ledger is a DIFFERENT module
# — the resolver computes and stores nothing, this one persists — so it takes an alias
# rather than shadowing the name half this file's order cases are written against.
from store import orders as order_store
from store.session import Store
from harness.tests.t7.common import (
    DUNSPARCE_SKU,
    FIXTURE_EXPORT,
    REPO_ROOT,
    RIFTBOUND_EXPORT,
    _bind,
    _refusal_text,
    answers,
    back_of,
    capture_payload,
    command,
    entry,
    isolated_home,
    quiet,
    refusal,
    run_photo,
    seam_run,
)

# ------------------------------------------------------------- undo, until it is built on


def _demo_seed_module():
    """`scripts/demo-seed.py`, loaded in this process. The filename carries a hyphen, so it
    is loaded by path. In-process on purpose: no third child process for this harness."""
    import importlib.util

    path = REPO_ROOT / "scripts" / "demo-seed.py"
    spec = importlib.util.spec_from_file_location("demo_seed_for_t7", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_undo_until_built_on(checks: Checks) -> None:
    """`docs/specs/undo.md` section 11, lane S: an undo has no clock and lasts until the
    next step is built on it. The server decides "built on", and refuses with a sentence.

    MUTATION-TESTED, one guard per block. Each block names the line whose removal turns it
    red: UN-7's two `sale_built_on` refusals, UN-8's `owed_entries`, UN-11's side file and
    its posting read, UN-14's history read, name check, newest check and divider check,
    UN-2's gap, its end, its transplant refusal, and UN-4's `log_states`.

    EVERY CALL AFTER A GUARD GOES THROUGH `answers` OR `refusal`, and every read of an answer
    is guarded, for `last_event`'s reason: a mutation must turn a NAMED check red, never raise
    a traceback that hides every check behind it.
    """
    checks.note("")
    checks.note("UNDO UNTIL BUILT ON — docs/specs/undo.md section 11, lane S")
    from dataclasses import asdict

    def field(body, name):
        return body.get(name) if isinstance(body, dict) else None

    # ------------------------------------------------ UN-7: a sale whose photo is cleared
    with isolated_home():
        capture_server.do_capture(capture_payload(5, capture_id="un7-photo"))
        with Store().write() as snapshot:
            snapshot.inventory.set_state("5/1", master.IDENTIFIED)
            _bind(snapshot, "5/1", "9191486")
        capture_server.do_mark_sold(5, 1, {})
        capture_server.do_reclaim_box_photos(5, {"confirm": True})
        refusal(
            checks,
            lambda: capture_server.do_mark_sold(5, 1, {"undo": True}),
            "sale_built_on",
            "UN-7: a sale whose photo was cleared is built on, and its undo refuses",
        )
        back = answers(
            checks,
            lambda: capture_server.do_mark_sold(5, 1, {"still_here": True}),
            "\"This card is still here\" answers on a sale that is built on",
        )
        checks.equal(
            (field(back, "state"), field(back, "still_here")),
            (master.IDENTIFIED, True),
            "and puts the card back to its earlier state anyway",
        )
        checks.equal(
            field(back, "order_effect"),
            "none",
            "the Opus review round's finding #4: no order ever held this copy, so the field "
            "that answers which of three things happened says so by name, not by a null "
            "that also means 'a shipped order got hand-filled instead'",
        )

    # ---------------------------------------- UN-7: a sale whose order has shipped
    with isolated_home():
        capture_server.do_capture(capture_payload(4, capture_id="un7-order"))
        with Store().write() as snapshot:
            snapshot.inventory.set_state("4/1", master.IDENTIFIED)
            _bind(snapshot, "4/1", "9191486")
            snapshot.ledger.ingest([
                order_store.OrderRecord(
                    source="TCGplayer",
                    number="UN7-1",
                    placed_at="2026-09-25T10:00:00.000+00:00",
                    status="Ready to Ship",
                    lines=[order_store.OrderLine(sku="9191486", quantity=1)],
                )
            ])
        key = order_store.order_key("TCGplayer", "UN7-1")
        target = [{"box": 4, "index": 1, "capture_id": "un7-order"}]
        capture_server.do_order_pull(
            {"source": "TCGplayer", "number": "UN7-1", "sku": "9191486", "targets": target}
        )
        with Store().write() as snapshot:
            record = snapshot.ledger.get(key)
            record.status = "Shipped - In Transit"
        refusal(
            checks,
            lambda: capture_server.do_order_pull({"undo": True, "targets": target}),
            "sale_built_on",
            "UN-7: once the order ships, the pull's own undo refuses",
        )
        refusal(
            checks,
            lambda: capture_server.do_mark_sold(4, 1, {"undo": True}),
            "sale_built_on",
            "and so does the card's own undo on #/inventory",
        )
        back = answers(
            checks,
            lambda: capture_server.do_mark_sold(4, 1, {"still_here": True}),
            "\"still here\" answers on a shipped order's card",
        )
        line = Store().read().ledger.recorded(key, "9191486")
        checks.equal(field(back, "state"), master.IDENTIFIED, "and puts the card back")
        checks.equal(
            (line.fulfilled, line.by_hand, "un7-order" in line.copies),
            (1, 1, False),
            "and the shipped order keeps its count (D212): the card's id comes off the line "
            "as a hand-fill, so pulling this card again is not refused as a double shipment",
        )
        checks.equal(
            field(back, "order_effect"),
            "filled_by_hand",
            "finding #4: the screen reads THIS field to say the order was hand-filled, "
            "rather than the ambiguous null `order_released` also answers for 'no order'",
        )

    # ------------------------------------------------ UN-8: a retired card leaves Review
    with isolated_home():
        capture_server.do_capture(capture_payload(8))
        with Store().write() as snapshot:
            snapshot.review.entries["8/1"] = entry(8, 1)

        def in_review() -> bool:
            return any(row["position"] == "8/1" for row in capture_server.do_queues()["review"])

        checks.ok(in_review(), "UN-8: a queued card is in Review")
        capture_server.do_retire(8, 1, {"reason": master.RETIRE_REASONS[0]})
        checks.ok(
            not in_review(),
            "UN-8: once retired, it leaves Review, and a reload does not bring it back",
        )
        capture_server.do_retire(8, 1, {"undo": True})
        checks.ok(in_review(), "and the retire undo brings it back with no second write")

    # ------------------------------------------------ UN-11: the clear outlives the toast
    with isolated_home():
        book = corpus.Corpus()
        book.answers = {"2000": corpus.Answer(value="4.50"), "2001": corpus.Answer(value="1.25")}
        book.write()
        cleared = pipeline_routes.do_pricing_clear({})
        checks.equal(cleared["count"], 2, "UN-11: a clear removes two typed prices")
        checks.equal(
            (pipeline_routes.do_pricing_corpus()["last_clear"] or {}).get("count"),
            2,
            "and the server keeps it, so a reload still offers the undo",
        )
        back = answers(
            checks,
            lambda: pipeline_routes.do_pricing_restore({"last_clear": True}),
            "the stored clear answers a restore",
        )
        checks.equal(
            sorted(field(back, "restored") or []), ["2000", "2001"], "and restores both"
        )
        checks.equal(
            pipeline_routes.do_pricing_corpus()["last_clear"],
            None,
            "and once restored there is nothing left to undo",
        )
        pipeline_routes.do_pricing_clear({})
        with Store().write() as snapshot:
            snapshot.postings.record(sku="2000", price="0.49", source="emit")
        checks.equal(
            pipeline_routes.do_pricing_corpus()["last_clear"],
            None,
            "UN-11: a send that carried a cleared SKU builds on the clear",
        )
        try:
            pipeline_routes.do_pricing_restore({"last_clear": True})
        except pipeline_routes.PipelineRefusal as caught:
            checks.equal(caught.code, "clear_built_on", "and the restore refuses it")
        else:
            checks.ok(False, "and the restore refuses it", "did not refuse")

    # ------------------------------------------------ a restore takes back only what was cleared
    # `POST /pricing/restore` once stored any value and date for a SKU the corpus did not hold,
    # so a hold with a forged `before.at` could arrive through it. It now accepts only the rows
    # the server's own stored clear holds, verbatim, and refuses the whole press otherwise.
    with isolated_home():
        first = "2026-09-01T10:00:00+00:00"
        book = corpus.Corpus()
        book.answers = {"2000": corpus.Answer(value="4.50", at=first), "2001": corpus.Answer(value="1.25", at=first)}
        book.write()
        taken = pipeline_routes.do_pricing_clear({})["cleared"]

        def refused(sent, label):
            try:
                pipeline_routes.do_pricing_restore({"answers": sent})
            except pipeline_routes.PipelineRefusal as caught:
                checks.equal(caught.code, "restore_not_cleared", label)
            else:
                checks.ok(False, label, "did not refuse")
            checks.equal(sorted(corpus.Corpus.read().answers), [], f"{label}: and it wrote nothing")

        refused({"2000": {"value": "4.50", "at": "2020-01-01T00:00:00+00:00"}}, "a forged date is refused")
        refused(
            {"2000": {"value": {"withheld": "bullish", "before": {"value": "4.50", "channel": "price", "at": "2020-01-01T00:00:00+00:00"}}}},
            "a hold is refused",
        )
        refused({"2999": {"value": "9.99"}}, "a SKU the clear did not take is refused")
        refused({**taken, "2999": {"value": "9.99"}}, "one foreign row refuses the whole press")
        back = pipeline_routes.do_pricing_restore({"answers": taken})
        checks.equal(sorted(back["restored"]), ["2000", "2001"], "the clear's own rows still come back")
        checks.equal(corpus.Corpus.read().answers["2000"].at, first, "verbatim, with their first date")

    # ------------------------------------------------ every clear keeps its undo, until built on
    # The owner's standing undo rule, "until it's built on". A second clear once replaced the
    # first, so the first clear's Undo refused while its toast was still up. The server keeps
    # every clear not yet restored, and each restore names its own.
    with isolated_home():
        first = "2026-09-01T10:00:00+00:00"
        book = corpus.Corpus()
        book.answers = {"3000": corpus.Answer(value="4.50", at=first), "3001": corpus.Answer(value="1.25", at=first)}
        book.write()
        one = pipeline_routes.do_pricing_clear({"skus": ["3000"]})
        two = pipeline_routes.do_pricing_clear({"skus": ["3001"]})
        checks.ok(one.get("clear_id") and two.get("clear_id") and one["clear_id"] != two["clear_id"], "two clears, two ids")
        checks.equal(
            (pipeline_routes.do_pricing_corpus()["last_clear"] or {}).get("id"),
            two["clear_id"],
            "the Restore notice offers the newest clear",
        )
        checks.equal(
            [row["id"] for row in pipeline_routes.do_pricing_corpus()["clears"]],
            [two["clear_id"], one["clear_id"]],
            "the Restore notice lists every kept clear, newest first (\"Anytime, from a history\")",
        )
        older = answers(
            checks,
            lambda: pipeline_routes.do_pricing_restore({"clear": one["clear_id"]}),
            "the older clear's Undo answers after a newer clear",
        )
        checks.equal(field(older, "restored"), ["3000"], "the older clear's Undo still works after a newer clear")
        checks.equal([row["id"] for row in corpus.read_clears()], [two["clear_id"]], "and only that clear is removed")
        newer = answers(
            checks,
            lambda: pipeline_routes.do_pricing_restore({"answers": two["cleared"], "clear": two["clear_id"]}),
            "the newer clear's Undo answers",
        )
        checks.equal(field(newer, "restored"), ["3001"], "then the newer one comes back too")
        checks.equal(corpus.read_clears(), [], "and no clear is left kept")
        back_first = corpus.Corpus.read().answers.get("3000")
        checks.equal(back_first and back_first.at, first, "each verbatim, with its first date")

    with isolated_home():
        book = corpus.Corpus()
        book.answers = {"3100": corpus.Answer(value="4.50"), "3101": corpus.Answer(value="1.25")}
        book.write()
        one = pipeline_routes.do_pricing_clear({"skus": ["3100"]})
        pipeline_routes.do_pricing_clear({"skus": ["3101"]})
        with Store().write() as snapshot:
            snapshot.postings.record(sku="3100", price="0.49", source="emit")
        try:
            pipeline_routes.do_pricing_restore({"answers": one["cleared"], "clear": one["clear_id"]})
        except pipeline_routes.PipelineRefusal as caught:
            checks.equal(caught.code, "clear_built_on", "a clear a send has built on refuses its Undo")
        else:
            checks.ok(False, "a clear a send has built on refuses its Undo", "did not refuse")
        checks.ok("3100" not in corpus.Corpus.read().answers, "and writes nothing")
        checks.equal(
            [row["count"] for row in pipeline_routes.do_pricing_corpus()["clears"]],
            [1],
            "a clear a send has built on is not offered, and the other one is",
        )
        checks.equal(
            sorted(pipeline_routes.do_pricing_restore({"last_clear": True})["restored"]),
            ["3101"],
            "the Restore notice skips the built-on clear and offers the newest it can still undo",
        )

    # ------------------------------------------------ an older clear never undoes a newer one
    # Clear A takes X at 5.00. The owner types 6.00. Clear B takes X at 6.00 and Y. Restoring A
    # first once put 5.00 back, so B's restore skipped X and the 6.00 was lost. A newer kept
    # clear holds the later answer, so A skips X and B brings back 6.00.
    with isolated_home():
        book = corpus.Corpus()
        book.answers = {"4000": corpus.Answer(value="5.00")}
        book.write()
        a = pipeline_routes.do_pricing_clear({"skus": ["4000"]})
        book = corpus.Corpus.read()
        book.answers["4000"] = corpus.Answer(value="6.00")
        book.answers["4001"] = corpus.Answer(value="3.00")
        book.write()
        b = pipeline_routes.do_pricing_clear({"skus": ["4000", "4001"]})
        first = answers(checks, lambda: pipeline_routes.do_pricing_restore({"clear": a["clear_id"]}), "clear A's restore answers")
        checks.equal(
            field(first, "skipped"),
            [{"sku": "4000", "reason": "newer_clear"}],
            "A skips X, because the newer clear B holds X's later answer, and says why",
        )
        checks.ok("4000" not in corpus.Corpus.read().answers, "and A does not put 5.00 back")
        checks.equal([row["id"] for row in corpus.read_clears()], [b["clear_id"]], "A is done: its X is B's to bring back")
        second = answers(checks, lambda: pipeline_routes.do_pricing_restore({"clear": b["clear_id"]}), "clear B's restore answers")
        checks.equal(sorted(field(second, "restored") or []), ["4000", "4001"], "B brings back X and Y")
        back = corpus.Corpus.read().answers.get("4000")
        checks.equal(back and back.value, "6.00", "and X is 6.00, the later answer, never the 5.00 A took")

    # ------------------------------------------------ a concurrent drop is a named skip, never a 500
    # `do_pricing_restore` reads `corpus.read_clears()` twice: once to resolve the named clear,
    # once more (below) to find every clear kept AFTER it. Between those two reads, a second
    # request for the SAME clear can finish first and drop it — `drop_clear` only runs once
    # every SKU the clear held is back, so the drop itself proves the SKU is already restored.
    # The old code built the "newer" slice with `kept[ids.index(stored["id"]) + 1:]`, which
    # calls `.index()` on the FULL LIST before its own `if stored["id"] in ids` guard ever
    # runs — a `ValueError` and a 500, not a refusal. Forced deterministically: the FIRST read
    # is answered with the pre-drop snapshot (so the named clear still resolves), the SECOND
    # with the real, post-drop list — the exact gap the race lands in, no thread needed.
    with isolated_home():
        book = corpus.Corpus()
        book.answers = {"9000": corpus.Answer(value="4.50")}
        book.write()
        one = pipeline_routes.do_pricing_clear({"skus": ["9000"]})
        clear_id = one["clear_id"]
        stale_kept = corpus.read_clears()  # still holds clear_id, the pre-drop snapshot
        # the concurrent request: it finishes first, restores "9000", and drops the clear.
        pipeline_routes.do_pricing_restore({"clear": clear_id})
        checks.equal(corpus.read_clears(), [], "the concurrent restore drops the clear entirely")
        checks.ok("9000" in corpus.Corpus.read().answers, "and puts the price back")

        real_read_clears = corpus.read_clears
        calls = {"n": 0}

        def racing_read_clears():
            calls["n"] += 1
            return stale_kept if calls["n"] == 1 else real_read_clears()

        corpus.read_clears = racing_read_clears
        try:
            back = answers(
                checks,
                lambda: pipeline_routes.do_pricing_restore({"clear": clear_id}),
                "T7-RACE: a second restore of a clear another request just dropped never raises",
            )
        finally:
            corpus.read_clears = real_read_clears
        checks.equal(
            field(back, "skipped"),
            [{"sku": "9000", "reason": "answered_since"}],
            "and names the skip rather than crashing on a stale id",
        )
        checks.equal(field(back, "restored"), [], "nothing restored twice")

    def put_price_with_retry(sku: str, value: str, attempts: int = 5) -> None:
        """`PUT /pricing`, adding one SKU, retried on `corpus_moved` — the real client's own
        recovery path (D103's "Reload before saving"), never a silent overwrite. A lock that
        forces two writers to serialize can still leave the second one holding a revision the
        first just moved — the lock's job is to stop a SILENT loss, not to stop the second
        writer from ever needing to look again."""
        for _ in range(attempts):
            current = pipeline_routes.do_pricing_corpus()
            document = current["corpus"]
            document["skus"][sku] = {"value": value}
            try:
                pipeline_routes.do_pricing_corpus_write(
                    {"corpus": document, "revision": current["revision"]}
                )
                return
            except pipeline_routes.PipelineRefusal as exc:
                if exc.code != "corpus_moved":
                    raise
        raise AssertionError(f"corpus_moved kept refusing {sku} after {attempts} attempts")

    # ------------------------------------------------ T7-RACE (pricing-corpus lock): the restore lost-update race
    # `do_pricing_restore`, `PUT /pricing`, `POST /pricing/clear` and both CLI writers
    # (`cli/cmd_join.py`, `cli/cmd_reprice.py`) now share ONE lock, `store/files.py:exclusive`,
    # around their whole read-modify-write. Before this fix, none of them took it, so a
    # `Corpus.read()` here, followed by another writer's whole `Corpus.write()` there, followed
    # by THIS call's own `write()`, would silently discard the other write. Forced with REAL
    # threads and the REAL flock, never a stubbed lock: `corpus.Corpus.read` is patched to
    # sleep, on the ONE call the restore makes, for exactly as long as that call now holds the
    # lock. Proven RED against a `.bak` copy of the pre-lock file, and proven GREEN here,
    # against the file as it stands, never `git checkout`.
    with isolated_home():
        book = corpus.Corpus()
        book.answers = {"7500": corpus.Answer(value="1.00")}
        book.write()
        clear_id = pipeline_routes.do_pricing_clear({"skus": ["7500"]})["clear_id"]

        real_corpus_read = corpus.Corpus.read
        seen = {"n": 0}
        paused = threading.Event()

        def racing_read(path=None):
            seen["n"] += 1
            result = real_corpus_read(path)
            if seen["n"] == 1:
                # THE RESTORE'S OWN READ — the one call `do_pricing_restore` makes, now
                # inside `files.exclusive`. Sleeping here holds the real flock.
                paused.set()
                time.sleep(0.2)
            return result

        corpus.Corpus.read = racing_read
        outcome: dict = {}
        try:
            def run_restore():
                outcome["restored"] = pipeline_routes.do_pricing_restore({"clear": clear_id})

            worker = threading.Thread(target=run_restore)
            worker.start()
            fired = paused.wait(timeout=5)
            # WRITER B, ON THIS THREAD, WHILE THE RESTORE SLEEPS INSIDE ITS LOCK. Unlocked,
            # this lands at once; locked, this call blocks here until the restore's
            # `with files.exclusive(...)` releases — never a hang, since it releases in ~0.2s.
            put_price_with_retry("7501", "3.25")
            worker.join(timeout=10)
        finally:
            corpus.Corpus.read = real_corpus_read

        checks.ok(fired, "T7-RACE: the restore's read fires before the wait times out")
        checks.ok(not worker.is_alive(), "T7-RACE: the restore finished")
        final = corpus.Corpus.read().answers
        checks.ok(
            "7501" in final and final["7501"].value == "3.25",
            "T7-RACE (pricing-corpus lock): PUT /pricing's edit survives a concurrent restore",
        )
        checks.ok(
            "7500" in final and final["7500"].value == "1.00",
            "and the restore's own answer still lands",
        )

    # ------------------------------------------------ T7-RACE (pricing-corpus lock): the same race, over a real join
    # The identical hazard, over `cli/cmd_join.py`'s own writer (D105's second unguarded
    # writer). `join` reads the corpus TWICE: once at the top, read-only, for the threshold
    # that shapes matching; once again, fresh, right before the write this lane put under the
    # lock. The second call is the one this test targets.
    with isolated_home():
        run_dir = runs.create("t7-b2race")
        capture_server.do_capture(capture_payload(1, game="riftbound"))
        with Store().write() as snapshot:
            snapshot.inventory.set_state("1/1", master.IDENTIFIED)
            snapshot.inventory.cards["1/1"].game = "riftbound"
        run_dir.write_identifications(
            {
                "prompt_fingerprint": "t7-b2race",
                "cards": {
                    "1/1": {
                        "photo": run_photo(1, 1),
                        "box": 1,
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

        real_corpus_read = corpus.Corpus.read
        seen = {"n": 0}
        paused = threading.Event()

        def racing_read(path=None):
            seen["n"] += 1
            result = real_corpus_read(path)
            if seen["n"] == 2:
                paused.set()
                time.sleep(0.2)
            return result

        corpus.Corpus.read = racing_read
        exit_codes: list = []
        try:
            def run_join():
                from cli import __main__ as cli_entry

                with quiet():
                    exit_codes.append(
                        cli_entry.main(["join", str(run_dir.directory), "--export", str(RIFTBOUND_EXPORT)])
                    )

            worker = threading.Thread(target=run_join)
            worker.start()
            fired = paused.wait(timeout=5)
            put_price_with_retry("8888", "4.50")
            worker.join(timeout=15)
        finally:
            corpus.Corpus.read = real_corpus_read

        checks.ok(fired, "T7-RACE: the join's second corpus read fires before the wait times out")
        checks.ok(not worker.is_alive(), "T7-RACE: the join finished")
        checks.equal(exit_codes, [0], "and it exited clean")
        final = corpus.Corpus.read().answers
        checks.ok(
            "8888" in final and final["8888"].value == "4.50",
            "T7-RACE (pricing-corpus lock): PUT /pricing's edit survives a concurrent join",
        )

    # ------------------------------------------------ T7-RACE (pricing-corpus lock): reprice apply's own
    # revision check, read again inside the lock
    # `cli/cmd_reprice.py:_apply`'s `--corpus-revision` guard used to run once, before the
    # import CSV was built and before the `Store().write()` block for the sale posting — both
    # of which take real time. A concurrent write that moved the revision in that gap passed
    # right by a check that had already run and would never run again. This is a different
    # shape from the other three: the write itself was always safe (a fresh read, its own
    # SKUs only), so nothing here can lose an edit — what could silently fail was the
    # OPERATOR'S "the pricing file changed, reload" refusal itself.
    #
    # Forced by making `corpus.revision()` answer the value it was offered on its first call
    # (so the early check passes), landing a real, unrelated corpus write of its own, then
    # answering fresh — the real, moved revision — on every later call. The fresh answer is
    # what the check now inside the lock reads.
    with isolated_home() as home:
        cards = [(3, 1, "Dunsparce", "120", "normal")]
        run_dir, _ = seam_run(checks, cards)
        book = corpus.Corpus()
        book.sub_threshold = "floor"
        book.write()
        command(checks, "emit", str(run_dir.directory))

        source = tcgcsv.read_export(FIXTURE_EXPORT)
        row = dict(source.by_sku()[DUNSPARCE_SKU])
        row[tcgcsv.LIVE_QUANTITY_COLUMN] = "2"
        row[tcgcsv.PRICE_COLUMN] = "2.0000"
        export = home / "live-b2race.csv"
        tcgcsv.write_csv(export, source.header, [row])

        command(checks, "reprice", "list", str(export), "--days", "7", "--percent", "10", "--write")
        directory = sorted((files.inventory_dir() / cmd_reprice.DIRNAME).iterdir())[-1]
        tcgcsv.write_csv(
            directory / cmd_reprice.WORKLIST,
            (tcgcsv.SKU_COLUMN, tcgcsv.PRICE_COLUMN),
            [{tcgcsv.SKU_COLUMN: DUNSPARCE_SKU, tcgcsv.PRICE_COLUMN: "1.50"}],
        )

        offered = corpus.revision()
        real_revision = corpus.revision
        seen = {"n": 0}

        def racing_revision(path=None):
            seen["n"] += 1
            if seen["n"] == 1:
                # THE EARLY CHECK'S OWN READ. Answer with the value it was handed, so that
                # check passes, then land a real, unrelated corpus edit before anything else
                # reads this file again — the concurrent write the early check cannot see.
                unrelated = corpus.Corpus.read()
                unrelated.answers["b2race-unrelated"] = corpus.Answer(value="9.99")
                unrelated.write()
                return offered
            return real_revision(path)

        corpus.revision = racing_revision
        try:
            from cli import __main__ as cli_entry

            with quiet() as said_buf:
                code = cli_entry.main(
                    [
                        "reprice", "apply", str(directory / cmd_reprice.WORKLIST), "--write",
                        "--corpus-revision", offered,
                    ]
                )
            said = said_buf.getvalue()
        finally:
            corpus.revision = real_revision

        checks.equal(
            seen["n"], 2,
            "T7-RACE: the revision is read twice — the early check, then the one this lane "
            "added inside the lock",
        )
        checks.equal(
            code, 1,
            "T7-RACE (pricing-corpus lock): reprice apply refuses when the revision moves during the run, "
            "not only when it has already moved at the start",
        )
        checks.ok(
            "REFUSED" in said and "pricing file changed" in said,
            "and names why", said,
        )
        checks.ok(
            DUNSPARCE_SKU not in corpus.Corpus.read().answers,
            "and the markdown's own answer is never written on top of the stale premise",
        )
        # LANE B3 (the pricing-corpus lock's own nesting risk, closed): the corpus check and the corpus write,
        # the posting, and `import.csv` now share ONE `Store().write()` hold. A refusal inside
        # it runs before any of the three exists, never after two of them are already on disk.
        target = directory / cmd_reprice.IMPORT
        checks.ok(
            not target.is_file(),
            "T7-RACE (pricing-corpus lock): and import.csv is never written on that same stale premise",
        )
        conn = db.connect(files.inventory_dir())
        try:
            stale_postings = [
                entry for entry in db.postings_for_sku(conn, DUNSPARCE_SKU)
                if entry["source"] == "reprice"
            ]
        finally:
            conn.close()
        checks.ok(
            not stale_postings,
            "and no reprice posting row lands on that same stale premise (`emit` already "
            "posted this SKU at the rule price, and that row is not this check's business)",
        )

        # THE ORDINARY CASE, RIGHT AFTER, WITH NO RACE: the same worklist, the real revision.
        # All three land, because the fix is one hold and not a smaller check.
        fresh_revision = corpus.revision()
        with quiet() as said_buf2:
            code2 = cli_entry.main(
                [
                    "reprice", "apply", str(directory / cmd_reprice.WORKLIST), "--write",
                    "--corpus-revision", fresh_revision,
                ]
            )
        said2 = said_buf2.getvalue()
        checks.equal(
            code2, 0, "T7-RACE (pricing-corpus lock): the ordinary apply, with no race, succeeds",
        )
        checks.ok(
            "wrote" in said2 and str(target) in said2,
            "and says it wrote import.csv, not only a silent exit 0", said2,
        )
        checks.ok(target.is_file(), "and writes import.csv")
        checks.equal(
            corpus.Corpus.read().answers[DUNSPARCE_SKU].value, "1.50",
            "and writes the corpus answer",
        )
        conn = db.connect(files.inventory_dir())
        try:
            landed_postings = [
                entry for entry in db.postings_for_sku(conn, DUNSPARCE_SKU)
                if entry["source"] == "reprice"
            ]
        finally:
            conn.close()
        checks.ok(landed_postings, "and writes the posting row")

    # ------------------------------------------------ T7-RACE (pricing-corpus lock): reprice apply's own
    # write, split the other way — a failure between the temp CSV and the corpus write
    # Round 1 (above) closed the revision race. Re-review found round 1's OWN write order
    # unsafe: `import.csv` went to its final name FIRST, then the corpus, both inside the
    # one hold. A caller that patched `write_csv` to raise during an ordinary apply got a
    # raw crash — no clean refusal, no import.csv, no posting — but the corpus already held
    # the markdown price. The next `emit` would sell at a price never sent or recorded.
    #
    # Round 2: `import.csv` now goes to a temp name first, the corpus write is the last step
    # that may still fail, and the rename happens only once it has. A failure there is
    # caught and refused in a sentence, never a raw traceback.
    with isolated_home() as home:
        cards = [(3, 1, "Dunsparce", "120", "normal")]
        run_dir, _ = seam_run(checks, cards)
        book = corpus.Corpus()
        book.sub_threshold = "floor"
        book.write()
        command(checks, "emit", str(run_dir.directory))

        source = tcgcsv.read_export(FIXTURE_EXPORT)
        row = dict(source.by_sku()[DUNSPARCE_SKU])
        row[tcgcsv.LIVE_QUANTITY_COLUMN] = "2"
        row[tcgcsv.PRICE_COLUMN] = "2.0000"
        export = home / "live-b3exc.csv"
        tcgcsv.write_csv(export, source.header, [row])

        command(checks, "reprice", "list", str(export), "--days", "7", "--percent", "10", "--write")
        exc_directory = sorted((files.inventory_dir() / cmd_reprice.DIRNAME).iterdir())[-1]
        tcgcsv.write_csv(
            exc_directory / cmd_reprice.WORKLIST,
            (tcgcsv.SKU_COLUMN, tcgcsv.PRICE_COLUMN),
            [{tcgcsv.SKU_COLUMN: DUNSPARCE_SKU, tcgcsv.PRICE_COLUMN: "1.50"}],
        )
        before_corpus = dict(corpus.Corpus.read().answers)

        real_write_csv = tcgcsv.write_csv

        def raising_write_csv(path, header, rows):
            raise OSError("T7-RACE (pricing-corpus lock): simulated write failure")

        from cli import __main__ as cli_entry

        tcgcsv.write_csv = raising_write_csv
        raised = None
        code3 = None
        try:
            with quiet() as said_buf3:
                try:
                    code3 = cli_entry.main(
                        [
                            "reprice", "apply", str(exc_directory / cmd_reprice.WORKLIST),
                            "--write",
                        ]
                    )
                except Exception as exc:  # the pre-fix crash this case proves against
                    raised = exc
            said3 = said_buf3.getvalue()
        finally:
            tcgcsv.write_csv = real_write_csv

        checks.ok(
            raised is None,
            "T7-RACE (pricing-corpus lock): a write failure between the temp CSV and the corpus write "
            "refuses cleanly, never a raw crash", repr(raised),
        )
        checks.equal(
            code3, 1,
            "and exits non-zero, which `do_markdown_apply` reads as nothing written",
        )
        checks.ok(
            said3 is not None and "REFUSED" in said3 and "Traceback" not in said3,
            "and prints a clean refusal sentence, never a raw traceback", said3,
        )
        temp_target = (exc_directory / cmd_reprice.IMPORT).with_name(
            f".{cmd_reprice.IMPORT}.{os.getpid()}.tmp"
        )
        checks.ok(not temp_target.exists(), "and leaves no temp file behind")
        checks.ok(
            not (exc_directory / cmd_reprice.IMPORT).is_file(),
            "and writes no import.csv",
        )
        checks.equal(
            dict(corpus.Corpus.read().answers), before_corpus,
            "and the corpus is unchanged",
        )
        conn = db.connect(files.inventory_dir())
        try:
            exc_postings = [
                entry for entry in db.postings_for_sku(conn, DUNSPARCE_SKU)
                if entry["source"] == "reprice"
            ]
        finally:
            conn.close()
        checks.ok(not exc_postings, "and no posting row lands")

    # ------------------------------------------------ T7-RACE (pricing-corpus lock): reprice apply's own
    # write, round 3 — a failure landing the file, AFTER the corpus already held the price
    # Round 2 (above) moved `import.csv`'s own write to a temp name, but still renamed it
    # into place LAST, after the corpus write, on the reasoning that `os.replace` on one
    # filesystem "is not expected to fail". Re-review made it fail: the corpus write had
    # ALREADY LANDED by the time the rename raised, so the operator saw a raw crash AND the
    # corpus held the markdown price with no file behind it — the same defect round 2 closed,
    # moved one step later.
    #
    # Round 3: the rename now runs BEFORE the corpus write, and a corpus-write exception
    # unlinks the file it just landed. A rename failure itself is caught the same way write_csv
    # failing already was: no corpus touched, temp file cleaned up, a clean refusal.
    with isolated_home() as home:
        cards = [(3, 1, "Dunsparce", "120", "normal")]
        run_dir, _ = seam_run(checks, cards)
        book = corpus.Corpus()
        book.sub_threshold = "floor"
        book.write()
        command(checks, "emit", str(run_dir.directory))

        source = tcgcsv.read_export(FIXTURE_EXPORT)
        row = dict(source.by_sku()[DUNSPARCE_SKU])
        row[tcgcsv.LIVE_QUANTITY_COLUMN] = "2"
        row[tcgcsv.PRICE_COLUMN] = "2.0000"
        export = home / "live-b3exc2.csv"
        tcgcsv.write_csv(export, source.header, [row])

        command(checks, "reprice", "list", str(export), "--days", "7", "--percent", "10", "--write")
        replace_directory = sorted((files.inventory_dir() / cmd_reprice.DIRNAME).iterdir())[-1]
        tcgcsv.write_csv(
            replace_directory / cmd_reprice.WORKLIST,
            (tcgcsv.SKU_COLUMN, tcgcsv.PRICE_COLUMN),
            [{tcgcsv.SKU_COLUMN: DUNSPARCE_SKU, tcgcsv.PRICE_COLUMN: "1.50"}],
        )
        before_corpus_r3 = dict(corpus.Corpus.read().answers)

        real_os_replace = os.replace

        # SELECTIVE ON PURPOSE: `Corpus.write()` ALSO calls `os.replace`, through
        # `store/files.py:write_atomic`, to land `prices.json` itself. A blanket patch fails
        # that call too, and — in round 2's own order (corpus write, THEN the CSV rename) —
        # the corpus's OWN replace sits inside round 2's try/except, so a blanket patch is
        # "caught" there and never reaches the CSV rename at all: a false green that proves
        # nothing about the defect this case exists to catch. Matching only the CSV's own
        # temp name reproduces the reviewer's exact call.
        def raising_replace(src, dst):
            if Path(src).name.startswith(f".{cmd_reprice.IMPORT}."):
                raise OSError("T7-RACE (pricing-corpus lock): simulated rename failure")
            return real_os_replace(src, dst)

        from cli import __main__ as cli_entry

        os.replace = raising_replace
        raised_r3 = None
        code4 = None
        try:
            with quiet() as said_buf4:
                try:
                    code4 = cli_entry.main(
                        [
                            "reprice", "apply", str(replace_directory / cmd_reprice.WORKLIST),
                            "--write",
                        ]
                    )
                except Exception as exc:  # round 2's own crash this case proves against
                    raised_r3 = exc
            said4 = said_buf4.getvalue()
        finally:
            os.replace = real_os_replace

        checks.ok(
            raised_r3 is None,
            "T7-RACE (pricing-corpus lock): a failure landing import.csv, after the corpus write, still "
            "refuses cleanly, never a raw crash", repr(raised_r3),
        )
        checks.equal(
            code4, 1,
            "and exits non-zero, which `do_markdown_apply` reads as nothing written",
        )
        checks.ok(
            said4 is not None and "REFUSED" in said4 and "Traceback" not in said4,
            "and prints a clean refusal sentence, never a raw traceback", said4,
        )
        replace_temp = (replace_directory / cmd_reprice.IMPORT).with_name(
            f".{cmd_reprice.IMPORT}.{os.getpid()}.tmp"
        )
        checks.ok(not replace_temp.exists(), "and leaves no temp file behind")
        checks.ok(
            not (replace_directory / cmd_reprice.IMPORT).is_file(),
            "and writes no import.csv",
        )
        checks.equal(
            dict(corpus.Corpus.read().answers), before_corpus_r3,
            "and the corpus is unchanged — round 2 would have failed this: `os.replace` "
            "raised AFTER `book.write()` had already landed the markdown price",
        )
        conn = db.connect(files.inventory_dir())
        try:
            replace_postings = [
                entry for entry in db.postings_for_sku(conn, DUNSPARCE_SKU)
                if entry["source"] == "reprice"
            ]
        finally:
            conn.close()
        checks.ok(not replace_postings, "and no posting row lands")

    # ------------------------------------------------ T7-RACE (pricing-corpus lock): reprice apply's own
    # write, round 4 — undo by restoring the corpus, never by deleting a file
    # Round 3 renamed the CSV into place FIRST, so a later corpus-write failure could "undo"
    # by unlinking `target`. Re-review found two holes. (a) `target` is a fixed name — a
    # SECOND apply over the same markdown lands its rename on the FIRST apply's real
    # `import.csv`, and unlinking to undo then destroys that earlier, real file. (b) the
    # cleanup unlinks had no guard of their own, so an unlink that itself raised propagated a
    # raw traceback past `cli/__main__.py:main`.
    #
    # Round 4: `os.replace(temp, target)` is the LAST step. If it fails, the corpus (already
    # written by then) is undone by writing its OWN PRE-IMAGE back — never by touching
    # `target`, which this branch never renamed into. Every cleanup step is its own try.
    with isolated_home() as home:
        cards = [(3, 1, "Dunsparce", "120", "normal")]
        run_dir, _ = seam_run(checks, cards)
        book0 = corpus.Corpus()
        book0.sub_threshold = "floor"
        book0.write()
        command(checks, "emit", str(run_dir.directory))

        source = tcgcsv.read_export(FIXTURE_EXPORT)
        row = dict(source.by_sku()[DUNSPARCE_SKU])
        row[tcgcsv.LIVE_QUANTITY_COLUMN] = "2"
        row[tcgcsv.PRICE_COLUMN] = "2.0000"
        export = home / "live-b3r4.csv"
        tcgcsv.write_csv(export, source.header, [row])

        command(checks, "reprice", "list", str(export), "--days", "7", "--percent", "10", "--write")
        r4_directory = sorted((files.inventory_dir() / cmd_reprice.DIRNAME).iterdir())[-1]
        worklist_path = r4_directory / cmd_reprice.WORKLIST
        earlier_target = r4_directory / cmd_reprice.IMPORT

        from cli import __main__ as cli_entry

        # THE FIRST, REAL APPLY — an earlier `import.csv` this whole case is built to
        # protect. Nothing here refuses a second apply over the same markdown (found by
        # re-review), so this file is exactly what a real second press would find.
        tcgcsv.write_csv(
            worklist_path,
            (tcgcsv.SKU_COLUMN, tcgcsv.PRICE_COLUMN),
            [{tcgcsv.SKU_COLUMN: DUNSPARCE_SKU, tcgcsv.PRICE_COLUMN: "1.50"}],
        )
        with quiet():
            first_code = cli_entry.main(["reprice", "apply", str(worklist_path), "--write"])
        checks.equal(first_code, 0, "T7-RACE (pricing-corpus lock) round 4: the first, real apply succeeds")
        earlier_bytes = earlier_target.read_bytes()
        earlier_corpus = dict(corpus.Corpus.read().answers)

        # CASE 1: THE FINAL REPLACE RAISES. A second apply, a different price, over the SAME
        # markdown — `os.replace` fails on its way to `target`, selectively, the same way
        # round 3's own case isolated the CSV's own temp name from `Corpus.write()`'s
        # internal rename.
        tcgcsv.write_csv(
            worklist_path,
            (tcgcsv.SKU_COLUMN, tcgcsv.PRICE_COLUMN),
            [{tcgcsv.SKU_COLUMN: DUNSPARCE_SKU, tcgcsv.PRICE_COLUMN: "1.25"}],
        )
        real_os_replace = os.replace

        def raising_replace_r4(src, dst):
            if Path(src).name.startswith(f".{cmd_reprice.IMPORT}."):
                raise OSError("T7-RACE (pricing-corpus lock) round 4: simulated rename failure")
            return real_os_replace(src, dst)

        os.replace = raising_replace_r4
        raised1 = None
        code_r4a = None
        try:
            with quiet() as said_buf_r4a:
                try:
                    code_r4a = cli_entry.main(
                        ["reprice", "apply", str(worklist_path), "--write"]
                    )
                except Exception as exc:
                    raised1 = exc
            said_r4a = said_buf_r4a.getvalue()
        finally:
            os.replace = real_os_replace

        checks.ok(
            raised1 is None,
            "T7-RACE (pricing-corpus lock) round 4, case 1: a final-replace failure, over an EARLIER "
            "real import.csv, still refuses cleanly", repr(raised1),
        )
        checks.equal(code_r4a, 1, "and exits non-zero")
        checks.ok(
            said_r4a is not None and "REFUSED" in said_r4a and "Traceback" not in said_r4a,
            "and prints a clean refusal, never a raw traceback", said_r4a,
        )
        temp_r4a = earlier_target.with_name(f".{cmd_reprice.IMPORT}.{os.getpid()}.tmp")
        checks.ok(not temp_r4a.exists(), "and leaves no temp file behind")
        checks.equal(
            earlier_target.read_bytes(), earlier_bytes,
            "and the EARLIER import.csv is byte-identical — round 3's own undo would have "
            "unlinked whatever sat at this name, real or not",
        )
        checks.equal(
            dict(corpus.Corpus.read().answers), earlier_corpus,
            "and the corpus is back to the first apply's own price, not the second's",
        )

        # CASE 2: THE CORPUS WRITE ITSELF RAISES, BEFORE THE REPLACE IS EVEN ATTEMPTED. The
        # earlier `import.csv` was never touched by this attempt at all — no rename ran — so
        # it must still be exactly the bytes the first apply wrote.
        tcgcsv.write_csv(
            worklist_path,
            (tcgcsv.SKU_COLUMN, tcgcsv.PRICE_COLUMN),
            [{tcgcsv.SKU_COLUMN: DUNSPARCE_SKU, tcgcsv.PRICE_COLUMN: "1.10"}],
        )
        real_corpus_write = corpus.Corpus.write

        def raising_corpus_write(self, path=None):
            raise OSError("T7-RACE (pricing-corpus lock) round 4: simulated corpus write failure")

        corpus.Corpus.write = raising_corpus_write
        raised2 = None
        code_r4b = None
        try:
            with quiet() as said_buf_r4b:
                try:
                    code_r4b = cli_entry.main(
                        ["reprice", "apply", str(worklist_path), "--write"]
                    )
                except Exception as exc:
                    raised2 = exc
            said_r4b = said_buf_r4b.getvalue()
        finally:
            corpus.Corpus.write = real_corpus_write

        checks.ok(
            raised2 is None,
            "T7-RACE (pricing-corpus lock) round 4, case 2: a corpus-write failure, before the replace "
            "is attempted, still refuses cleanly", repr(raised2),
        )
        checks.equal(code_r4b, 1, "and exits non-zero")
        checks.ok(
            said_r4b is not None and "REFUSED" in said_r4b and "Traceback" not in said_r4b,
            "and prints a clean refusal, never a raw traceback", said_r4b,
        )
        checks.equal(
            earlier_target.read_bytes(), earlier_bytes,
            "and the prior import.csv is byte-identical — the rename was never reached",
        )
        checks.equal(
            dict(corpus.Corpus.read().answers), earlier_corpus,
            "and the corpus is unchanged",
        )

        # CASE 3: THE FINAL REPLACE RAISES, AND THE CLEANUP UNLINK ALSO RAISES. Both the
        # rename and the temp-file cleanup that follows a failed rename fail. Still no raw
        # crash: each cleanup step is its own try (found by re-review's own case (b)).
        tcgcsv.write_csv(
            worklist_path,
            (tcgcsv.SKU_COLUMN, tcgcsv.PRICE_COLUMN),
            [{tcgcsv.SKU_COLUMN: DUNSPARCE_SKU, tcgcsv.PRICE_COLUMN: "1.05"}],
        )
        real_unlink = Path.unlink

        def raising_unlink_r4(self, *a, **kw):
            if self.name.startswith(f".{cmd_reprice.IMPORT}."):
                raise OSError("T7-RACE (pricing-corpus lock) round 4: simulated unlink failure")
            return real_unlink(self, *a, **kw)

        os.replace = raising_replace_r4
        Path.unlink = raising_unlink_r4
        raised3 = None
        code_r4c = None
        try:
            with quiet() as said_buf_r4c:
                try:
                    code_r4c = cli_entry.main(
                        ["reprice", "apply", str(worklist_path), "--write"]
                    )
                except Exception as exc:
                    raised3 = exc
            said_r4c = said_buf_r4c.getvalue()
        finally:
            os.replace = real_os_replace
            Path.unlink = real_unlink

        checks.ok(
            raised3 is None,
            "T7-RACE (pricing-corpus lock) round 4, case 3: the replace AND the cleanup unlink both "
            "fail, still no raw crash", repr(raised3),
        )
        checks.equal(code_r4c, 1, "and exits non-zero")
        checks.ok(
            said_r4c is not None and "REFUSED" in said_r4c and "Traceback" not in said_r4c,
            "and prints a clean refusal sentence, never a raw traceback", said_r4c,
        )

    # ------------------------------------------------ UN-14: a move, until either box changes
    with isolated_home():
        for _ in range(2):
            capture_server.do_capture(capture_payload(6))
        capture_server.do_capture(capture_payload(7))
        before = Store().read().inventory
        mover = before.cards["6/1"]
        neighbor = asdict(before.cards["6/2"])
        stayer = asdict(before.cards["7/1"])
        capture_server.do_move_card(6, 1, {"capture_id": mover.capture_id, "to_box": 7, **back_of(7)})
        undone = answers(
            checks,
            lambda: capture_server.do_move_card(6, 1, {"undo": True}),
            "UN-14: the move's undo answers",
        )
        after = Store().read().inventory
        home = after.cards.get("6/1")
        checks.equal(
            (field(undone, "to"), field(undone, "moved"), getattr(home, "state", None),
             getattr(home, "capture_id", None)),
            ("6/1", "7/2", mover.state, mover.capture_id),
            "and puts the card back at its own index",
        )
        checks.ok(
            "7/2" not in after.cards
            and asdict(after.cards["6/2"]) == neighbor
            and asdict(after.cards["7/1"]) == stayer,
            "and the transplant is gone, and nothing else in either box moved (D118)",
        )
        checks.equal(
            (getattr(home, "order", None), getattr(home, "order_key", None) is not None),
            (mover.order, True),
            "and the card's order key comes back too (D294), so it stands where it stood",
        )
        checks.equal(
            (getattr(home, "cid", None), getattr(home, "moved_from", "unset")),
            (mover.cid, None),
            "the card wears its own name again, and is no transplant",
        )
        capture_server.do_move_card(6, 1, {"capture_id": mover.capture_id, "to_box": 7, **back_of(7)})
        capture_server.do_mark_sold(6, 2, {})
        refusal(
            checks,
            lambda: capture_server.do_move_card(6, 1, {"undo": True}),
            "move_built_on",
            "UN-14: a sale in the old box builds on the move, and its undo refuses",
        )

    # ---------------------- UN-14: the store's own guards, under the route's history read
    with isolated_home():
        capture_server.do_capture(capture_payload(6))
        capture_server.do_capture(capture_payload(7))
        mover = Store().read().inventory.cards["6/1"]
        capture_server.do_move_card(6, 1, {"capture_id": mover.capture_id, "to_box": 7, **back_of(7)})
        capture_server.do_capture(capture_payload(7))
        with Store().write() as snapshot:
            checks.raises(
                master.CardDeparted,
                lambda: snapshot.inventory.unmove_card("6/1"),
                "UN-14: the store refuses a move undo once the transplant is not the newest",
            )
    with isolated_home():
        capture_server.do_capture(capture_payload(6))
        capture_server.do_capture(capture_payload(7))
        mover = Store().read().inventory.cards["6/1"]
        capture_server.do_move_card(6, 1, {"capture_id": mover.capture_id, "to_box": 7, **back_of(7)})
        capture_server.do_open_section(7, {})
        refusal(
            checks,
            lambda: capture_server.do_move_card(6, 1, {"undo": True}),
            "move_built_on",
            "UN-14: a divider put in behind the transplant builds on the move",
        )

    # ---------------- UN-14: a tombstone written before the key suffix still undoes
    with isolated_home():
        capture_server.do_capture(capture_payload(6))
        capture_server.do_capture(capture_payload(7))
        mover = Store().read().inventory.cards["6/1"]
        capture_server.do_move_card(6, 1, {"capture_id": mover.capture_id, "to_box": 7, **back_of(7)})
        with Store().write() as snapshot:
            snapshot.inventory.cards["6/1"].cid = f"{master.MOVED_CID_PREFIX}{mover.cid}"
        undone = answers(
            checks,
            lambda: capture_server.do_move_card(6, 1, {"undo": True}),
            "UN-14: a tombstone in the older `moved:<name>` form still undoes",
        )
        checks.equal(field(undone, "to"), "6/1", "and the card is back home")

    # ------------------ D83's chain: a move back, and a move on, write distinct tombstones
    with isolated_home():
        capture_server.do_capture(capture_payload(6))
        capture_server.do_capture(capture_payload(7))
        mover = Store().read().inventory.cards["6/1"]
        capture_server.do_move_card(6, 1, {"capture_id": mover.capture_id, "to_box": 7, **back_of(7)})
        back = answers(
            checks,
            lambda: capture_server.do_move_card(7, 2, {"capture_id": mover.capture_id, "to_box": 6, **back_of(6)}),
            "a transplant moves back to its first box without a UNIQUE clash on its name",
        )
        onward = answers(
            checks,
            lambda: capture_server.do_move_card(
                6, 2, {"capture_id": mover.capture_id, "to_box": 8, **back_of(8)}
            ),
            "and on to a third box",
        )
        cards = Store().read().inventory.cards
        tombstones = [cards[key].cid for key in ("6/1", "7/2", "6/2") if key in cards]
        checks.equal(
            (field(back, "to"), field(onward, "to"), getattr(cards.get("8/1"), "cid", None),
             len(set(tombstones))),
            ("6/2", "8/1", mover.cid, 3),
            "and the card keeps its own name (D172) while three tombstones stay distinct",
        )

    # ------------------------------------------------ UN-2: the sitting, off the store
    ts_gap = re.search(
        r"GAP_MINUTES = (\d+)",
        (REPO_ROOT / "app" / "src" / "storeHistory.ts").read_text(),
    )
    checks.equal(
        int(ts_gap.group(1)) if ts_gap else None,
        capture_server.SITTING_GAP_MINUTES,
        "UN-2: the server's sitting gap is the screen's own GAP_MINUTES",
    )
    with isolated_home():
        for _ in range(3):
            capture_server.do_capture(capture_payload(9))
        sitting = capture_server.do_capture_sitting()
        checks.equal(
            (sitting["open"], [row["key"] for row in sitting["cards"]]),
            (True, ["9/1", "9/2", "9/3"]),
            "UN-2: a reload reads the sitting back off the store, oldest first",
        )
        stale = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        with Store().write() as snapshot:
            for key in ("9/1", "9/2"):
                snapshot.inventory.cards[key].captured_at = stale
        checks.equal(
            [row["key"] for row in capture_server.do_capture_sitting()["cards"]],
            ["9/3"],
            "and a gap longer than the sitting's own ends the older sitting",
        )
        with Store().write() as snapshot:
            snapshot.inventory.cards["9/3"].captured_at = stale
        checks.equal(
            (lambda body: (body["open"], body["cards"]))(capture_server.do_capture_sitting()),
            (False, []),
            "and once the newest capture is older than the gap, the sitting has ended",
        )
        refusal(
            checks,
            lambda: capture_server.do_delete_card(9, 3),
            "capture_built_on",
            "UN-2: once its sitting has ended, the capture undo refuses, by the same rule",
        )
        checks.ok(
            "9/3" in Store().read().inventory.cards,
            "and the refused undo deleted nothing",
        )
        naive = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        with Store().write() as snapshot:
            card = snapshot.inventory.cards.get("9/3")
            if card is not None:
                card.captured_at = naive
        sitting = answers(
            checks,
            capture_server.do_capture_sitting,
            "UN-2: a captured_at with no zone reads as UTC and never raises",
        )
        checks.equal(field(sitting, "open"), True, "and it counts as the open sitting")

    # ---------------- UN-2: a moved card is not a capture, in the strip or in the undo
    with isolated_home():
        for _ in range(2):
            capture_server.do_capture(capture_payload(6))
        mover = Store().read().inventory.cards["6/1"]
        capture_server.do_move_card(6, 1, {"capture_id": mover.capture_id, "to_box": 7, **back_of(7)})
        checks.equal(
            [row["key"] for row in capture_server.do_capture_sitting()["cards"]],
            ["6/2"],
            "UN-2: the sitting leaves out the tombstone and the transplant",
        )
        said = _refusal_text(lambda: capture_server.do_delete_card(7, 1))
        checks.ok(
            said is not None and said[0] == "capture_built_on" and "moved here" in said[1],
            "and the capture undo refuses the transplant AS A MOVED CARD, rather than delete "
            "it: its own guard, not only the sitting's",
            f"refusal was: {said}",
        )
        checks.ok(
            "7/1" in Store().read().inventory.cards
            and photos.path(mover.cid, files.home()).is_file(),
            "and the moved card and its photograph are both still there",
        )

    # ------------------------------------ UN-4, and every reversal, on a fresh demo seed
    with isolated_home():
        seed = _demo_seed_module()
        with quiet():
            seed.build_store(force=True)
        cards = sorted(Store().read().inventory.cards.values(), key=lambda c: c.key)
        sold = [c for c in cards if c.state == master.SOLD]
        retired = [c for c in cards if c.state == master.RETIRED]
        moved = [c for c in cards if c.state == master.MOVED]
        trips = 0
        for card in sold:
            back = answers(
                checks,
                lambda card=card: capture_server.do_mark_sold(card.box, card.index, {"undo": True}),
                f"UN-4: the demo's sold {card.key} undoes",
            )
            capture_server.do_mark_sold(card.box, card.index, {}) if back else None
            trips += field(back, "state") == master.IDENTIFIED
        for card in retired:
            back = answers(
                checks,
                lambda card=card: capture_server.do_retire(card.box, card.index, {"undo": True}),
                f"UN-4: the demo's retired {card.key} undoes",
            )
            if back:
                capture_server.do_retire(card.box, card.index, {"reason": card.retire_reason})
            trips += field(back, "state") == master.IDENTIFIED
        checks.equal(
            (trips, len(sold) > 0, len(retired) > 0),
            (len(sold) + len(retired), True, True),
            "UN-4: every sold and retired card on a fresh demo seed undoes and redoes, "
            "because the seed logs the state lines a real card logs",
        )
        refusal(
            checks,
            lambda: capture_server.do_move_card(moved[0].box, moved[0].index, {"undo": True}),
            "move_built_on",
            "the demo's moved card has no real transplant, so its undo refuses and deletes "
            "no other card",
        )
        with Store().write() as snapshot:
            checks.raises(
                master.CardNotFound,
                lambda: snapshot.inventory.unmove_card(moved[0].key),
                "and the store's own name check refuses it too, under the route's history read",
            )
        live = next(c for c in cards if c.state == master.IDENTIFIED and c.box == 1)
        capture_server.do_move_card(1, live.index, {"capture_id": live.capture_id, "to_box": 2, **back_of(2)})
        undone = answers(
            checks,
            lambda: capture_server.do_move_card(1, live.index, {"undo": True}),
            "a fresh move on the demo undoes",
        )
        checks.equal(field(undone, "to"), live.key, "and the card is back at its own key")


CHECKS = (
    check_undo_until_built_on,
)
