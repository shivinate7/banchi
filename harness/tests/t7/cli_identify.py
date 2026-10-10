"""T7 group: CLI seams, code ledger, identify, review, catalog, realignment, rescue, join.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.
"""

from __future__ import annotations

import json
import hashlib
import shutil
import tempfile
import time

from decimal import Decimal
from pathlib import Path
from harness.tests import Checks
from cli import cmd_reconcile, resolve, runs
from identify import batch, prompt, sidecar
from pipeline import games, join, livecheck, routing, tcgcsv, variant
# `pipeline.skus`, aliased — this module's own `skus` name would collide with
# `store.skus`'s `Skus`/`SkuRow` classes imported right below, and both are used by
# `_seed_sku_table` (identity-follows-sku.md §4.2's review round: a review answer now
# refuses a SKU the `skus` table does not already hold, so fixtures that answer a
# hand-built candidate seed the table first, through the real fold).
from pipeline import skus as sku_pipeline
from store.skus import SkuRow
from server import capture_server, pipeline_routes, ports, send_routes
from store import db, files, master
from store.session import Store
from harness.tests.t7.common import (
    CANDIDATES,
    FIXTURE_EXPORT,
    JPEG,
    NEVER_BOUND_IDENTITY_SNAPSHOT,
    REPO_ROOT,
    RIFTBOUND_EXPORT,
    _bind,
    _refusal_text,
    _seed_sku_table,
    answers,
    append_history,
    capture_payload,
    command,
    corrupt_history,
    entry,
    fake_cid,
    identifications_for,
    isolated_home,
    last_event,
    photo_of,
    quiet,
    refusal,
    seam_run,
    store_tables,
    write_export,
)


def _assert_identity_round_trip(checks: Checks, before: dict, after: dict, label: str) -> None:
    """identity-follows-sku.md §8, lane 3a review round: D28's "undo must be exact" — a
    forward write then its own undo must leave the card byte-identical to `before`, except
    `bound_at`, which `Inventory.restore_identity` re-stamps rather than restores verbatim
    (its own docstring, `Inventory.unbind_sku`'s established precedent: "a restore is
    itself an act happening now").
    """
    fields = [f for f in master.Inventory.IDENTITY_SNAPSHOT_FIELDS if f != "bound_at"]
    checks.equal(
        {f: after.get(f) for f in fields},
        {f: before.get(f) for f in fields},
        f"{label}: every identity and bookkeeping field except bound_at is restored "
        f"EXACTLY (D28: undo must be exact) — bound_by/identity_source/read_disputes "
        f"included, not only sku/condition/name/number/printed_total/set_name/rarity",
    )


def check_cli_seams(checks: Checks) -> None:
    """The wiring that feeds rules T3-T5 already check.

    `pipeline/` owns the decisions and is tested. What lives in `cli/` is which column a
    value is pulled from and how a record becomes an argument — and a wrong-but-valid input
    passes every existing test while changing every answer.
    """
    checks.note("")
    checks.note("COMMAND SEAMS — cli/resolve.py")

    # THE ONE WORTH THE WHOLE SECTION. routing.cheapest is checked by T4; what is checked
    # here is that the value handed to it comes from TCG Market Price. Reading Marketplace
    # or Low instead parses cleanly, passes T4, and routes every card in every run on a
    # number that is not the card's market price.
    rows = [
        {
            tcgcsv.MARKET_PRICE_COLUMN: "2.00",
            tcgcsv.LOW_PRICE_COLUMN: "0.01",
            tcgcsv.PRICE_COLUMN: "9.99",
        },
        {
            tcgcsv.MARKET_PRICE_COLUMN: "0.75",
            tcgcsv.LOW_PRICE_COLUMN: "0.02",
            tcgcsv.PRICE_COLUMN: "8.88",
        },
    ]
    checks.equal(
        resolve.cheapest_of(rows),
        Decimal("0.75"),
        "cheapest_of reads TCG Market Price — not Marketplace, not Low (D9)",
    )
    checks.ok(
        f"http://localhost:{ports.capture_port()}" in capture_server.DEFAULT_ALLOWED_ORIGINS,
        "AND THE CAPTURE PORT IS IN IT, which D138 made necessary and this list did not "
        "follow. The app is served from THIS process now, so the product's own page is "
        "same-origin with the server it writes to — and a browser sends `Origin` on a "
        "same-origin write. Naming only the dev port refused the owner's first real write "
        "from the built app: a box delete, 403 `origin_not_allowed`, 2026-09-11. Reads are "
        "ungated, so every screen drew correctly and only writing was broken, which is D43's "
        "own failure shape arriving at this control for the third time",
    )
    checks.ok(
        f"http://localhost:{ports.dev_port()}" in capture_server.DEFAULT_ALLOWED_ORIGINS,
        "and the DEV port stays beside it — `make dev` runs there against this server "
        "(D138), so dropping it would refuse every write from the development app while "
        "looking like a tidy-up",
    )

    blank = [{tcgcsv.MARKET_PRICE_COLUMN: "", tcgcsv.LOW_PRICE_COLUMN: "1.00"}]
    checks.ok(
        resolve.cheapest_of(blank) is None,
        "a blank market cell yields no price rather than zero (D9 no_market_data)",
    )

    # The candidate rows the review screen shows beside the photo (D4). Every key here is
    # read by a screen that does not exist yet, so the columns are the contract.
    candidate = resolve._candidate_rows(
        [
            {
                tcgcsv.SKU_COLUMN: "8608859",
                tcgcsv.NAME_COLUMN: "Articuno",
                tcgcsv.SET_COLUMN: "SV09",
                tcgcsv.NUMBER_COLUMN: "161/159",
                tcgcsv.CONDITION_COLUMN: "Near Mint Holofoil",
                tcgcsv.MARKET_PRICE_COLUMN: "4.20",
            }
        ]
    )
    checks.equal(
        sorted(candidate[0]),
        ["condition", "market", "name", "number", "set", "sku"],
        "a candidate row carries exactly the six fields the review screen reads",
    )
    checks.equal(candidate[0]["sku"], "8608859", "and the sku comes from TCGplayer Id")
    checks.equal(
        candidate[0]["market"], "4.20", "and market comes from TCG Market Price"
    )

    # `cli/resolve.py:load` whitelists the detected finish before handing it to the ladder.
    # If that whitelist and the enum drift, a valid finish is dropped on the floor and D3
    # rung 3 never fires — the cross-check that catches a mis-sorted card.
    #
    # THE CHECK HAS CHANGED SHAPE TWICE, BECAUSE THE DEFECT DID. It first looked for each
    # finish as a LITERAL in the source, which was right while `resolve.py` held its own copy
    # of the tuple. That copy went and the check became `finish in variant.FINISHES`.
    #
    # THEN THE ENUM STOPPED HAVING ONE HOME AND STARTED HAVING ONE PER GAME (2026-08-23), and
    # `variant.FINISHES` — Pokemon's three — became the WRONG thing for this seam to consult:
    # the model's `foil` on a Riftbound card fell out of a whitelist belonging to another
    # game and landed as `None`, losing rung 3's cross-check for every non-Pokemon card. The
    # silent drop this case exists to prevent, committed by the expression this case was
    # asserting. So the named single source is now `variant.vocabulary`, which reads the
    # game's own entry out of `pipeline/games.py`.
    #
    # What is asserted is unchanged in substance: the enum is NAMED rather than copied, and
    # no finish is spelled out beside it. T4 asserts the behaviour end to end against a
    # finish added to the registry at runtime, which is the half a source scan can never
    # reach.
    source = (REPO_ROOT / "cli" / "resolve.py").read_text("utf-8")
    checks.ok(
        "variant.vocabulary(game)" in source,
        "resolve.py tests the detected finish against THIS GAME's vocabulary, read from the "
        "registry, not against a second copy of the enum that nothing keeps in step",
        f"pokemon finishes are {variant.FINISHES}",
    )
    checks.ok(
        "finish in variant.FINISHES" not in source,
        "and the defective EXPRESSION is gone — it consulted Pokemon's enum for every game, "
        "which is the bug that lost rung 3 for Riftbound and One Piece. The token itself is "
        "allowed to survive in prose: the comment at that seam names the old test to explain "
        "what went wrong, and a check that forbade the words would forbid the explanation",
    )
    hardcoded = sorted(f for f in variant.FINISHES if f'"{f}"' in source or f"'{f}'" in source)
    checks.equal(
        hardcoded,
        [],
        "and no finish is spelled out in it at all — a literal is how the two drifted apart "
        "the first time",
    )

    # Which export a run joins against. The manifest remembers it so later commands do not
    # need it again; with neither flag nor memory the command refuses and says what to pass.
    with tempfile.TemporaryDirectory() as tmp:
        recorded = runs.Run(
            directory=Path(tmp), manifest={"export": {"path": f"{tmp}/sv09.csv"}}
        )
        checks.equal(
            resolve.export_for(recorded, None),
            Path(f"{tmp}/sv09.csv"),
            "export_for falls back to the export the manifest recorded",
        )
        checks.equal(
            resolve.export_for(recorded, f"{tmp}/other.csv"),
            Path(f"{tmp}/other.csv"),
            "and an explicit --export overrides it",
        )
        caught = checks.raises(
            runs.RunError,
            lambda: resolve.export_for(runs.Run(directory=Path(tmp), manifest={}), None),
            "a run with no export recorded and no flag REFUSES rather than guessing",
        )
        if caught is not None:
            checks.ok(
                "--export" in str(caught),
                "and the refusal names the flag to pass",
                f"message was: {caught}",
            )

# ------------------------------------------------------------------- the code ledger (C8)


def check_code_ledger(checks: Checks) -> None:
    """C8's dispute flow: the transcribed code beside the photograph it was read from.

    A LEDGER OF UNREDEEMED CODES IS A FILE OF BEARER INSTRUMENTS, and every string below is
    an INVENTED code shape in a scratch store — nothing here touches a real card, a real
    ledger, or a tracked file. Three seams, each asserted where it lives:
    `store/files.py:upsert_jsonl`, which keeps "one line per code card" literally true
    across re-identifications; `cli/cmd_identify.py:_code_ledger_lines`, which decides what
    earns a line and what is skipped BY NAME; and the record seam in `run`, which writes
    the PARSER's fields onto the card rather than the raw payload's keys — for a code card
    that is C8's whole mechanism, because the code lands in `number`, `number` is a column
    `GET /search` matches, and the dispute lookup is therefore the existing search.

    THE TRANSPORT IS A FAKE AND IT IS THE ONLY FAKE. `identify` is the one command that
    costs money, so `batch.run_batch` is swapped for a stub that answers each request under
    its own strategy — everything on either side of that seam is the real code: the sidecar
    scan, the cache, the record write, the ledger upsert. Nothing here submits anything.
    """
    checks.note("")
    checks.note("CODE LEDGER — store/files.py, cli/cmd_identify.py, GET /search")

    from cli import __main__ as cli_entry
    from cli import cmd_identify
    from identify import images as identify_images

    # 3-4-3-3, with a `?` for a character the model could not read and a lowercase letter
    # that `normalize_number` would have folded — the two properties the parser must keep.
    code = "GXR-7Q?d-K3M-9TT"

    # ------------------------------------------------------ upsert_jsonl, the index shape
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "codes.jsonl"
        first = [
            {"box": 9, "index": 1, "code": "AAA-1111-AAA-111"},
            {"box": 9, "index": 2, "code": "BBB-2222-BBB-222"},
            {"box": 10, "index": 1, "code": "CCC-3333-CCC-333"},
        ]
        files.upsert_jsonl(path, first, ("box", "index"))
        checks.equal(
            files.read_jsonl(path),
            first,
            "upsert_jsonl writes new keys in the order given",
        )
        corrected = {"box": 9, "index": 2, "code": "BBB-2222-BBB-999", "run": "second"}
        appended = {"box": 11, "index": 1, "code": "DDD-4444-DDD-444"}
        files.upsert_jsonl(path, [corrected, appended], ("box", "index"))
        checks.equal(
            files.read_jsonl(path),
            [first[0], corrected, first[2], appended],
            "a re-identified card REPLACES its own line IN PLACE — order kept, new keys "
            "appended — so `one line per code card` stays literally true and a lookup "
            "needs no last-line-wins rule",
        )
        checks.equal(
            len(path.read_text("utf-8").splitlines()),
            4,
            "four keys, four lines: the file is an INDEX, not a log",
        )
        before = path.read_bytes()
        files.upsert_jsonl(path, [corrected], ("box", "index"))
        checks.equal(
            path.read_bytes(), before, "and re-upserting the same line is idempotent"
        )

    # ------------------------------------------- _code_ledger_lines: what earns a line
    def code_item(photo: str, box, index, raw, *, parsed: bool) -> cmd_identify.Item:
        capture = sidecar.Capture(
            photo=Path(photo), box=box, index=index, set_hint="JTG", game="pokemon_code"
        )
        item = cmd_identify.Item(capture=capture, identification=raw)
        cmd_identify._attach_registry(item)
        if parsed and raw is not None:
            item.parsed = prompt.parse(dict(raw), item.strategy)
        return item

    fresh = code_item(
        "/caps/5-001.jpg",
        5,
        1,
        {"code": code, "name": "Journey Together", "confidence": "high"},
        parsed=True,
    )
    # `parsed` stays None on a cache hit — the payload was parsed on the run that paid for
    # it — so the cached card is the branch that re-parses under the card's own strategy.
    cached = code_item(
        "/caps/5-002.jpg",
        5,
        2,
        {"code": "MMM-5555-MMM-555", "name": "Surging Sparks", "confidence": "medium"},
        parsed=False,
    )
    broken = code_item(
        "/caps/5-003.jpg", 5, 3, {"code": "NNN-6666-NNN-666"}, parsed=False
    )
    blank = code_item(
        "/caps/5-004.jpg",
        5,
        4,
        {"code": "", "name": "Journey Together", "confidence": "low"},
        parsed=True,
    )
    homeless = code_item(
        "/caps/loose.jpg",
        None,
        None,
        {"code": "PPP-7777-PPP-777", "name": "", "confidence": "high"},
        parsed=True,
    )
    pokemon_item = cmd_identify.Item(
        capture=sidecar.Capture(photo=Path("/caps/5-006.jpg"), box=5, index=6),
        identification={"name": "Eiscue", "number": "044", "printed_total": "167"},
    )
    cmd_identify._attach_registry(pokemon_item)

    stamps = {"5/1": "2026-08-23T10:00:00.000Z", "5/2": "2026-08-23T10:00:01.000Z"}
    lines, skipped = cmd_identify._code_ledger_lines(
        [fresh, cached, broken, blank, homeless, pokemon_item],
        "run-t7",
        lambda key: stamps.get(key),
    )
    checks.equal(
        [(line["box"], line["index"], line["code"]) for line in lines],
        [(5, 1, code), (5, 2, "MMM-5555-MMM-555")],
        "a line per code the run holds: the fresh read AND the cached one — a cached "
        "card's answer was already paid for, and re-upserting its line is what heals a "
        "ledger file that was lost, since inventory/ is never in git and nothing else "
        "would re-create it",
    )
    if lines:
        checks.equal(
            lines[0],
            {
                "box": 5,
                "index": 1,
                "code": code,
                "name": "Journey Together",
                "photo": "/caps/5-001.jpg",
                "set_hint": "JTG",
                "captured_at": "2026-08-23T10:00:00.000Z",
                "confidence": "high",
                "run": "run-t7",
            },
            "and the line is the dispute flow's whole index entry — code text beside the "
            "position its photograph is keyed by, the `?` the model wrote for a doubtful "
            "character SURVIVING to the ledger, where it says exactly which character the "
            "owner's re-read should doubt",
        )
    checks.equal(len(skipped), 3, "three cards earn no line, each skipped BY NAME")
    for needle, why in (
        (
            "loose.jpg: no position",
            "a positionless card has no key to file a line under — and it is not "
            "silently dropped: it is already loudly queued as no_position, the stronger "
            "guarantee",
        ),
        (
            "5/4: the model read no code",
            "an empty transcription has nothing to look a dispute up by",
        ),
        (
            "5/3: cached answer does not parse",
            "a cached payload the profile's schema has moved under is named, never "
            "guessed at — re-identifying it is the remedy",
        ),
    ):
        checks.ok(any(needle in line for line in skipped), why, f"skipped: {skipped!r}")
    checks.ok(
        all("5/6" not in line for line in skipped),
        "and the Pokemon card is in NEITHER list — the ledger is pokemon_code's alone",
        f"skipped: {skipped!r}",
    )

    # --------------------------- the record seam and both ledger files, through `run`
    with isolated_home() as home:
        caps = Path(home) / "code-caps"
        caps.mkdir()
        # A DIFFERENT COLOUR EACH, because a card is named by the sha256 of its photograph
        # (D172) and `cards_cid` holds that name UNIQUE. Both were the same flat red, which
        # is two records carrying one name the moment `identify` writes them.
        for name, red in (("6-001.jpg", 200), ("6-002.jpg", 120)):
            identify_images.Image.new("RGB", (64, 89), (red, 40, 40)).save(
                caps / name, "JPEG"
            )
        (caps / "6-001.json").write_text(
            json.dumps(
                {"box": 6, "position": 1, "game": "pokemon_code", "set_hint": "JTG"}
            ),
            "utf-8",
        )
        (caps / "6-002.json").write_text(
            json.dumps({"box": 6, "position": 2, "game": "misc"}), "utf-8"
        )

        payload_by_strategy = {
            "pokemon_code_v1": {
                "code": code,
                "name": "Journey Together",
                "confidence": "high",
            },
            "misc_card_v1": {
                "name": "Dark Magician",
                "printed_id": "sdy-006",
                "detected_game": "yugioh",
                "language": "English",
                "confidence": "high",
            },
        }
        transported: list = []

        def fake_run_batch(requests, log=None, on_submit=None):
            outcomes = {}
            for request in requests:
                transported.append(request.custom_id)
                raw = dict(payload_by_strategy[request.strategy])
                outcomes[request.custom_id] = batch.Outcome(
                    request.custom_id,
                    batch.SUCCEEDED,
                    identification=prompt.parse(raw, request.strategy),
                )
            return batch.BatchRun(outcomes=outcomes)

        real_run_batch = cmd_identify.batch.run_batch
        cmd_identify.batch.run_batch = fake_run_batch
        try:
            with quiet():
                exit_code = cmd_identify.run(
                    cli_entry.build_parser().parse_args(["identify", str(caps), "--engine", "haiku"]),
                    lambda *a: None,
                )
            checks.equal(exit_code, 0, "`banchi identify` exits 0 over the stub transport")
            checks.equal(
                len(transported), 2, "which was asked for exactly the two photographs"
            )

            recorded = Store().read().inventory
            checks.equal(
                recorded.get("6/1").number,
                code,
                "THE RECORD SEAM WRITES THE PARSER'S FIELDS: a pokemon_code payload has "
                "no `number` key at all, and the transcribed `code` lands in Card.number "
                "with its `?` and its case exactly as transcribed — never "
                "normalize_number-folded, because there is no catalog key here and "
                "`exactly as printed` is the whole instruction the field was authored "
                "under",
            )
            checks.equal(
                recorded.get("6/1").printed_total,
                "",
                "and printed_total stays empty: no join key CAN be built from a "
                "redemption code, so has_number stays honestly False",
            )
            checks.equal(
                recorded.get("6/2").number,
                "sdy-006",
                "a misc payload lands its `printed_id` through the same seam, case kept "
                "— reading .get('number') off the raw payload instead would write a "
                "record only Pokemon's profile could ever fill",
            )

            standing = files.read_jsonl(files.codes_ledger_path())
            checks.equal(
                [(line["box"], line["index"], line["code"]) for line in standing],
                [(6, 1, code)],
                "the standing index holds ONE line — the code card's; the misc card is "
                "not the ledger's business",
            )
            run_dirs = [d for d in sorted(files.runs_dir().iterdir()) if d.is_dir()]
            run_copy = (
                files.read_jsonl(run_dirs[0] / files.CODES_LEDGER_NAME) if run_dirs else []
            )
            checks.equal(
                [(line["box"], line["index"], line["code"]) for line in run_copy],
                [(6, 1, code)],
                "and the run directory carries its own deletable copy — runs/ is "
                "derived, inventory/ is the master",
            )

            # The heal: C8's argument for including a cached card, run for real.
            files.codes_ledger_path().unlink()
            sent_before = len(transported)
            with quiet():
                exit_code = cmd_identify.run(
                    cli_entry.build_parser().parse_args(["identify", str(caps), "--engine", "haiku"]),
                    lambda *a: None,
                )
            checks.equal(exit_code, 0, "a second identify over the same directory exits 0")
            checks.equal(
                len(transported),
                sent_before,
                "and pays for NOTHING — every answer is a cache hit, so the transport is "
                "never called again",
            )
            healed = files.read_jsonl(files.codes_ledger_path())
            checks.equal(
                [(line["box"], line["index"], line["code"]) for line in healed],
                [(6, 1, code)],
                "yet the DELETED standing index is re-created whole from the cached "
                "answer, parsed again under the card's own strategy — the heal is why a "
                "cached code card is included at all",
            )
        finally:
            cmd_identify.batch.run_batch = real_run_batch

    # ------------------------------------------- the dispute lookup is GET /search
    with isolated_home():
        capture_server.do_capture(
            capture_payload(7, game="pokemon_code", set_hint="JTG")
        )
        capture_server.do_capture(capture_payload(7))
        with Store().write() as snapshot:
            pooled = snapshot.inventory.cards["7/1"]
            pooled.name = "Journey Together"
            pooled.number = code
            pooled.sku = "424242"
            # The recorded field nulled while the FILE stays on disk — the shape a record
            # written by `emit` rather than a capture has, and the case that tells the
            # stat apart from `bool(card.photo)`. With both set, a field-reading mutant
            # answers True for the wrong reason and the assertion below proves nothing.
            pooled.photo = None
            decoy = snapshot.inventory.cards["7/2"]
            decoy.sku = "555"
            decoy.name = "Eiscue"
            decoy.note = f"traded beside {code}"

        found = capture_server.do_search(code)["groups"]
        checks.equal(
            [group["sku"] for group in found],
            ["424242", "555"],
            "the exact code string RANKS ITS CARD FIRST — C8's lookup is the existing "
            "search with zero new UI, and exact-on-number outranks the substring match a "
            "chatty note also earns",
        )
        if len(found) == 2:
            group = found[0]
            checks.equal(
                group["number"],
                code,
                "the group answers the code as its number, `?` and case intact",
            )
            copy = group["copies"][0] if group["copies"] else {}
            checks.equal(copy.get("key"), "7/1", "with the code card as its one copy")
            checks.ok(
                copy.get("has_photo") is True,
                "which answers has_photo — the STAT, against a record whose photo field "
                "is null while the file is on disk, so the screen requests GET /photo "
                "and the owner is two taps from the re-read C8 exists for",
            )
            place = copy.get("place") or {}
            checks.ok(
                place.get("located") is False
                and place.get("label") is None
                and place.get("neighbors") is None
                and place.get("section_gaps") is None,
                "and a POOLED place — D24's ruling: a code card is a count, not a slot, "
                "so no label, no neighbors, no gaps, and null rather than zero for the "
                "gap count because `no section at all` is a different fact from `a "
                "countable section with no holes`",
                f"place: {place!r}",
            )
            checks.equal(
                place.get("game"),
                "pokemon_code",
                "stamped with its game, so the screen knows why there is no label",
            )

ONE_PIECE_EXPORT = (
    REPO_ROOT / "fixtures" / "onepiece_export_untouched.csv"
)

# --------------------------------------------------------------- the review catalog lookup


def check_review_catalog(checks: Checks) -> None:
    """GET /review/<box>/<index>/catalog and D77's answer path — the card with no rows.

    ITS OWN ISOLATED HOME, this file's standing lesson: it answers a card, which clears queue
    entries and writes history lines the blocks around it count over stores they build by hand.

    THE DEAD END THIS CLOSES. A queue entry with no candidates could not be answered at all —
    `do_review_answer` refuses it as `no_candidates` — so the only moves were skip, which
    writes nothing and asks again next session, and D37's stand-down, which closes the question
    rather than answering it. The row was usually in the export the whole time: box 1's
    `Master Yi, Wuju Master` was read as `Wuju Master`, dropping the champion, so no exact
    match could find it and the photograph was perfectly good.

    THE GUARD IS NARROWED, NOT REMOVED, AND THAT IS WHAT MOST OF THIS BLOCK ASSERTS. A bare
    SKU still refuses. The SKU is re-read out of THIS CARD'S OWN export inside the write
    lock, so an unknown one refuses and a condition the client invented is discarded rather
    than believed.

    D77 WIDENED WHICH ENTRIES THE FLAG REACHES, AND THIS BLOCK ASSERTS BOTH HALVES. It used
    to reach only an entry with NO candidates, on D77's reasoning that a card the pipeline
    found rows for already has its answer on screen. Box 3 card 66 was the counter-example
    and it was the only open entry in the owner's store: `Nasus, Ascended`, its number
    misread as `8/298` — a real key in that export, belonging to `Get Excited!` — so the
    entry carried two confident rows for a different card while the card's own row sat in
    the same file. What is asserted now is the pair that actually matters: an entry WITH
    rows accepts a catalog answer, and an entry WITH rows still refuses an UNFLAGGED SKU it
    was never offered.
    """
    checks.note("")
    checks.note("REVIEW CATALOG — GET /review/<box>/<index>/catalog, and D77's answer")

    with isolated_home() as home:
        # A run holding the riftbound export, exactly as an app-driven join leaves it: the
        # bytes INSIDE the run, and the manifest naming that copy.
        run_dir = home / "runs" / "2026-08-29-box1-01"
        run_dir.mkdir(parents=True)
        shutil.copy(RIFTBOUND_EXPORT, run_dir / "export.csv")
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "created_at": "2026-08-29T22:37:47+00:00",
                    "joined": True,
                    "exports": {"riftbound": {"path": str(run_dir / "export.csv")}},
                }
            )
        )

        for _ in range(3):
            capture_server.do_capture(capture_payload(1, game="riftbound"))
        with Store().write() as snapshot:
            for key in ("1/1", "1/2", "1/3"):
                snapshot.inventory.set_state(key, master.IDENTIFIED)
                snapshot.inventory.cards[key].game = "riftbound"
            # The live case: the champion dropped, no number read, no candidate rows.
            snapshot.inventory.cards["1/1"].run = "2026-08-29-box1-01"
            snapshot.review.upsert(
                entry(
                    1,
                    1,
                    candidates=[],
                    reason="no_catalog_row",
                    read={"name": "Wuju Master", "number": None},
                )
            )
            # Records no run at all — a card identified before `run` was written.
            snapshot.review.upsert(entry(1, 2, candidates=[], reason="no_catalog_row"))
            # Has candidates of its own, so the catalog path must never reach it.
            snapshot.inventory.cards["1/3"].run = "2026-08-29-box1-01"
            snapshot.review.upsert(entry(1, 3, market="12.00"))
            # identity-follows-sku.md §4.2's review round: a review answer now refuses a
            # SKU the `skus` table does not already hold. The REAL export this run was
            # joined against is right here, so the fixture seeds the table off the SAME
            # file through the real fold — a real fetch's own shape, not a synthetic one.
            sku_pipeline.apply_rows(
                tcgcsv.read_export(run_dir / "export.csv").rows, at=int(time.time()),
                source="export.csv", skus=snapshot.skus, events=snapshot.inventory.events,
            )

        # --- the lookup ---

        found = answers(
            checks,
            lambda: capture_server.do_review_catalog(1, 1, ""),
            "an empty query suggests from the card's own read, which is the arriving case",
        )
        if found is not None:
            names = [str(row["name"]) for row in found["rows"]]
            checks.ok(
                "Master Yi, Wuju Master" in names,
                "D77: the row the pipeline could not find is offered — the read dropped the "
                "champion, so only a substring match recovers it",
            )
            checks.equal(
                found["game"],
                "riftbound",
                "D77: and it is looked up as the game the CARD records, not the default",
            )

        typed = answers(
            checks,
            lambda: capture_server.do_review_catalog(1, 1, "191/219"),
            "a typed collector number searches the same export",
        )
        if typed is not None:
            checks.ok(
                any(str(row["number"]) == "191/219" for row in typed["rows"]),
                "D77: a number finds its row",
            )

        empty = answers(
            checks,
            lambda: capture_server.do_review_catalog(1, 1, "zzz not a card"),
            "a query matching nothing answers with no rows",
        )
        if empty is not None:
            checks.equal(
                (len(empty["rows"]), empty["found"]),
                (0, 0),
                "D77: and it does NOT guess — an empty result is an empty result",
            )

        refusal(
            checks,
            lambda: capture_server.do_review_catalog(9, 99, ""),
            "card_not_found",
            "a lookup for a card that does not exist refuses",
        )
        refusal(
            checks,
            lambda: capture_server.do_review_catalog(1, 2, ""),
            "no_run_recorded",
            "a card with no run has no export to look in, and says so rather than guessing "
            "which run on disk might have been the one",
        )

        # --- the answer, and the guard that stays standing ---

        refusal(
            checks,
            lambda: capture_server.do_review_answer(
                1, 1, {"sku": "9192027", "condition": "Near Mint Foil"}
            ),
            "no_candidates",
            "WITHOUT the flag a zero-candidate entry still refuses — D77 narrows this guard "
            "and does not remove it",
        )
        refusal(
            checks,
            lambda: capture_server.do_review_answer(
                1,
                1,
                {"sku": "0000000", "condition": "Near Mint Foil", "from_catalog": True},
            ),
            "sku_not_in_catalog",
            "a SKU the export does not carry refuses even WITH the flag — the row is re-read "
            "server-side, so this is never a free-text write",
        )

        before = Store().read().inventory.cards["1/1"].sku
        checks.ok(before is None, "and neither refusal wrote anything")
        before_catalog_answer = Store().read().inventory.identity_snapshot("1/1")

        answered = answers(
            checks,
            lambda: capture_server.do_review_answer(
                1,
                1,
                # A DELIBERATELY WRONG CONDITION. The server takes the row's own, so this is
                # discarded rather than validated — a client that sends the wrong one gets the
                # right one, which is what makes the SKU the only thing the request decides.
                {"sku": "9192027", "condition": "TOTAL NONSENSE", "from_catalog": True},
            ),
            "a catalog-verified row answers the card",
        )
        if answered is not None:
            checks.equal(
                answered["condition"],
                "Near Mint Foil",
                "D77: and the CONDITION comes off the export row, never off the request",
            )

        stored = Store().read()
        card = stored.inventory.cards["1/1"]
        checks.equal(
            (card.sku, card.condition),
            ("9192027", "Near Mint Foil"),
            "the pair lands on the card, which is what a later join reads back as D3 rung 0",
        )
        checks.equal(
            card.rarity,
            "Rare",
            "and rarity lands too, off the same catalog row — `_catalog_row` was missing "
            "the key `_candidate_rows` has carried since D213, so a `from_catalog` answer "
            "used to land `rarity = NULL` here exactly as an uncorrected `do_correct_answer` "
            "did (D252's amendment fixed both at their one shared root)",
        )
        checks.ok(
            stored.review.entries["1/1"].cleared_by_human,
            "and the queue entry is cleared, so the question stops being asked",
        )

        undone = answers(
            checks,
            lambda: capture_server.do_review_answer(1, 1, {"undo": True}),
            "the undo puts the from_catalog answer back",
        )
        if undone is not None:
            checks.equal(undone.get("undone"), True, "and it reports which direction it went")
        _assert_identity_round_trip(
            checks,
            before_catalog_answer,
            Store().read().inventory.identity_snapshot("1/1"),
            "the D77 from_catalog answer's own undo",
        )
        line = [
            event
            for event in Store().history()
            if event.get("event") == "answered" and event.get("position") == "1/1"
        ]
        checks.ok(
            bool(line) and line[-1].get("from_catalog") is True,
            "D77: the history line records that a HUMAN found this row rather than the "
            "pipeline — after the write there is no other evidence which happened",
        )

        # --- D77: an entry WITH rows, whose rows are the wrong card ---
        #
        # THIS BLOCK REPLACES AN ASSERTION THAT SAID THE OPPOSITE, and the reversal is the
        # whole of D77. It read: "an entry WITH candidates is unaffected by the flag: it
        # still answers only from the rows it was offered, which is the laundering guard D77
        # must not reach." That sentence conflated two guards. The laundering guard is that
        # no string a client sends becomes a listing on its own, and it is asserted twice
        # above and once again below — the SKU is re-read out of the card's own export and
        # the condition comes off that row. What the old assertion ALSO froze was that "the
        # pipeline offered rows" means "the pipeline was right", which box 3 card 66
        # falsified: `Nasus, Ascended` with its number misread as `8/298`, two confident
        # `Get Excited!` rows, and the card's real row in the same export.

        answered_over = answers(
            checks,
            lambda: capture_server.do_review_answer(
                1,
                3,
                {"sku": "9192027", "condition": "Near Mint Foil", "from_catalog": True},
            ),
            "D77: an entry WITH candidate rows can be answered from the catalog, because "
            "rows the pipeline offered can be the wrong card and only a human can see that",
        )
        if answered_over is not None:
            checks.equal(
                Store().read().inventory.cards["1/3"].sku,
                "9192027",
                "D77: and the row a human found is what lands, over the rows it was offered",
            )
            over_line = [
                event
                for event in Store().history()
                if event.get("event") == "answered" and event.get("position") == "1/3"
            ]
            checks.ok(
                bool(over_line) and over_line[-1].get("from_catalog") is True,
                "D77: the history line says a HUMAN found this row — the case that most "
                "needs saying, because here the pipeline had a confident offer and was "
                "overruled, and the old `not candidates` clause omitted the flag exactly "
                "here",
            )

        # --- and the guard that is NOT widened ---
        #
        # The flag is what widened; the offer did not. An answer that does not claim a human
        # went and found the row still may not name one the pipeline never proposed.
        # `reopen`, NOT a second `upsert`: that one refuses a position a human has cleared,
        # exactly so a later run cannot re-ask a settled question, and a test that reached
        # around the refusal would be asserting against a store no code path can produce.
        # This is D28's undo hole, used the way the undo uses it — the entry keeps the
        # candidate rows it was built with.
        with Store().write() as snapshot:
            snapshot.inventory.cards["1/3"].sku = None
            snapshot.inventory.cards["1/3"].condition = None
            checks.ok(
                snapshot.review.reopen("1/3"),
                "the answered entry reopens, which is what makes the next check a real one",
            )
        refusal(
            checks,
            lambda: capture_server.do_review_answer(
                1, 3, {"sku": "9192027", "condition": "Near Mint Foil"}
            ),
            "sku_not_a_candidate",
            "WITHOUT the flag an entry with rows still answers only from those rows — D77 "
            "widened which entries the flag reaches and not what an unflagged answer may say",
        )
        checks.ok(
            Store().read().inventory.cards["1/3"].sku is None,
            "and that refusal wrote nothing",
        )


def check_correct_answer(checks: Checks) -> None:
    """POST /inventory/<box>/<index>/correct — D252.

    THE SCENARIO THIS ROUTE WAS BUILT FOR, off the real fixture. A card answered onto the
    wrong catalog row, with the wrong SKU already pushed and live — `do_review_answer`'s own
    undo refuses `undo_too_late` at exactly this point, and until this route there was no
    other door. This section proves three things in order: the correction itself (the new row
    lands, the old one is released), that item 2 of the brief is answered by
    `pipeline/livecheck.py:compare` — D109's OWN `beyond` bucket, unmodified — rather than by a
    second mechanism, and the reversal.
    """
    checks.note("")
    checks.note("CORRECT A LISTED ANSWER — POST /inventory/<box>/<index>/correct")

    # Two real rows off the committed Riftbound export, not invented ones.
    old_sku, old_name, old_number = "8926937", "Acceptable Losses", "179/298"
    new_sku, new_name = "8925897", "Adaptatron"

    with isolated_home() as home:
        run_dir = home / "runs" / "2026-09-23-box4-01"
        run_dir.mkdir(parents=True)
        shutil.copy(RIFTBOUND_EXPORT, run_dir / "export.csv")
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "created_at": "2026-09-23T00:00:00+00:00",
                    "joined": True,
                    "exports": {"riftbound": {"path": str(run_dir / "export.csv")}},
                }
            )
        )

        for _ in range(3):
            capture_server.do_capture(capture_payload(4, game="riftbound"))
        with Store().write() as snapshot:
            for key in ("4/1", "4/2", "4/3"):
                snapshot.inventory.cards[key].game = "riftbound"
                snapshot.inventory.cards[key].run = "2026-09-23-box4-01"
            # 4/1 — answered wrong, already pushed AND live, and IN NO QUEUE — the exact
            # shape D28's undo refuses on and this route exists to reach anyway.
            # DIRECT FIELD WRITE, NOT `_bind`: `rarity` must stay unset going in — the
            # same "never carried a rarity at all" shape this function's undo checks
            # elsewhere. `bind_sku` always derives `rarity` alongside `sku`/`condition`.
            snapshot.inventory.set_state("4/1", master.IDENTIFIED)
            snapshot.inventory.cards["4/1"].sku = old_sku
            snapshot.inventory.cards["4/1"].condition = "Near Mint"
            snapshot.inventory.cards["4/1"].name = old_name
            snapshot.inventory.cards["4/1"].number = old_number
            snapshot.inventory.listing(old_sku, condition="Near Mint").set(
                master.PUSHED, 1
            )
            snapshot.inventory.listing(old_sku, condition="Near Mint").set(
                master.LIVE, 1
            )
            # 4/2 — captured, never identified. Nothing here to correct.
            # 4/3 — identified, then departed. A correction there is a different question.
            snapshot.inventory.set_state("4/3", master.IDENTIFIED)
            snapshot.inventory.cards["4/3"].sku = old_sku
            snapshot.inventory.cards["4/3"].condition = "Near Mint"
            snapshot.inventory.set_state("4/3", master.SOLD)

        refusal(
            checks,
            lambda: capture_server.do_correct_answer(9, 9, {"sku": new_sku}),
            "card_not_found",
            "a correction for a position with no record refuses — this route corrects a "
            "card that exists and never creates one",
        )
        refusal(
            checks,
            lambda: capture_server.do_correct_answer(4, 3, {"sku": new_sku}),
            "card_departed",
            "a correction on a SOLD card refuses — a departed card's SKU is a different, "
            "larger question this route does not attempt",
        )
        refusal(
            checks,
            lambda: capture_server.do_correct_answer(4, 2, {"sku": new_sku}),
            "not_identified",
            "a correction on a never-identified card refuses — that is do_review_answer's "
            "job, and this route has no wrong answer to correct",
        )
        refusal(
            checks,
            lambda: capture_server.do_correct_answer(4, 1, {"sku": "0000000"}),
            "sku_not_in_catalog",
            "an unknown sku refuses — D77's own guard, reused verbatim: the row is re-read "
            "server-side and never taken on the client's word",
        )
        refusal(
            checks,
            lambda: capture_server.do_correct_answer(4, 1, {"sku": old_sku}),
            "sku_unchanged",
            "choosing the row the card already carries refuses — there is nothing here to "
            "correct",
        )

        # THE REFUSAL NAMES THE CONFIRM PRESS ONLY WHERE THE SCREEN DRAWS IT. `CardHero.tsx`
        # draws "The listing is right" for an identified card whose identity is still the
        # camera's read. A bound card gets no such press, so its refusal must not name one.
        def unchanged_message() -> str:
            try:
                capture_server.do_correct_answer(4, 1, {"sku": old_sku})
            except capture_server.BadRequest as caught:
                return str(caught)
            return ""

        before_source = Store().read().inventory.cards["4/1"].identity_source
        bound_text = unchanged_message()
        checks.ok(
            "already lists as that" in bound_text and "The listing is right" not in bound_text,
            "sku_unchanged on a card whose identity is not the read names no confirm press",
            f"said: {bound_text!r}",
        )
        with Store().write() as snapshot:
            snapshot.inventory.cards["4/1"].identity_source = master.IDENTITY_READ
        read_text = unchanged_message()
        checks.ok(
            "The listing is right" in read_text,
            "sku_unchanged on a held card (identity_source read) names the confirm press",
            f"said: {read_text!r}",
        )
        place = join.said_place(Store().read().inventory, 4, 1)
        checks.ok(
            read_text.startswith(place)
            and "Box 4, card 1" not in read_text
            and "/inventory/" not in read_text
            and "\u00a7" not in read_text,
            "and it names the place the screens draw, never the store index, a route or a "
            "spec section",
            f"place: {place!r}, said: {read_text!r}",
        )
        with Store().write() as snapshot:
            snapshot.inventory.cards["4/1"].identity_source = before_source

        # ------------------------------------------------------------- the correction itself
        before_release = Store().read().inventory.listings[old_sku]
        checks.equal(
            (before_release.pushed, before_release.live),
            (1, 1),
            "before the correction: the wrong sku is pushed and live",
        )

        body = answers(
            checks,
            lambda: capture_server.do_correct_answer(4, 1, {"sku": new_sku}),
            "the correction succeeds even though the wrong sku is pushed and live — the "
            "exact case do_review_answer's own undo refuses",
        )
        if body is not None:
            checks.equal(body["sku"], new_sku, "and it reports the new sku")
            checks.equal(body["previous_sku"], old_sku, "and the sku it replaced")
            checks.equal(
                body["released"],
                {"pushed": 1},
                "and what Listing.release gave up on the old sku — least-committed-first, "
                "D34's own rule, so `pushed` goes before `live`",
            )
            checks.equal(
                body["restores_to"]["sku"],
                old_sku,
                "and what an undo would put back, since the NEW sku carries no hold yet",
            )

        card = Store().read().inventory.cards["4/1"]
        checks.equal(
            (card.sku, card.condition),
            (new_sku, "Near Mint"),
            "the new pair lands on the card",
        )
        checks.equal(
            card.name,
            new_name,
            "and the STORED NAME FOLLOWS THE CATALOG (owner's ruling) — it no longer says "
            "the wrong product's name",
        )
        checks.equal(
            card.rarity,
            "Uncommon",
            "and the STORED RARITY FOLLOWS THE CATALOG too — `_catalog_row` was missing "
            "the key `_candidate_rows` has carried since D213, so every correction used to "
            "land `rarity = NULL` whatever the chosen row's own Rarity cell said",
        )
        # STORED VERBATIM, NEVER SPLIT — RIFTBOUND IS A `printed_code` GAME. The reviewer
        # caught the first version of this fix treating every game as Pokemon's
        # `number_and_printed_total` shape: it split `056/298` into `("056", "298")`, which
        # broke the very thing `_key_printed_code` matches against (that function reads
        # `card.number` WHOLE and never consults `printed_total` at all) and wrongly
        # populated `number_key`, which `pipeline/pricearchive.py`'s own comment documents
        # as EMPTY BY DESIGN for a game with no denominator. All three real cards this
        # amendment was written for are Riftbound.
        checks.equal(
            (card.number, card.printed_total),
            ("056/298", None),
            "and the STORED NUMBER FOLLOWS THE CATALOG (the orchestrator's ruling, within "
            "D36, corrected on review) — the chosen row's own `056/298` cell, stored WHOLE "
            "because Riftbound's join key is `printed_code`, not composed from two halves — "
            "not the misread `179/298` left on the card by the wrong answer",
        )
        checks.equal(
            capture_server._card_number_key(card),
            "",
            "and `number_key` stays EMPTY — the documented shape for a `printed_code` game, "
            "never filled by a correction on one",
        )
        checks.equal(
            capture_server._number_display(card),
            "056/298",
            "and `number_display` still reads right — `join.display_number` falls back to "
            "the whole cell when `printed_total` is absent",
        )
        conn = db.connect(files.inventory_dir())
        checks.equal(
            conn.execute(
                "SELECT number_key, number_display FROM cards WHERE key = '4/1'"
            ).fetchone(),
            ("", "056/298"),
            "and the PERSISTED columns agree — `_card_columns` runs on every card write, "
            "this route's own included, so the derivation is not only correct in memory",
        )

        # THE RE-JOIN PROOF (item 3): a corrected Riftbound card's stored number still
        # matches its own export row through the REAL join-key function, `_key_printed_code`
        # — never re-derived here, called straight off `pipeline/join.py`, over the actual
        # export this run holds. This is what "the row this card now carries would survive a
        # fresh join" means, proved rather than asserted by shape alone.
        rejoin_catalog = join.Catalog.from_export(
            tcgcsv.read_export(run_dir / "export.csv"), "riftbound"
        )
        rejoin_key = join._key_printed_code(
            join.IdentifiedCard(
                position=None, name=card.name, number=card.number,
                printed_total=card.printed_total,
            )
        )
        rejoin_rows = rejoin_catalog.rows_for_key(rejoin_key) if rejoin_key else []
        checks.ok(
            any(str(row[tcgcsv.SKU_COLUMN]) == new_sku for row in rejoin_rows),
            "a fresh join over this run's own export, keyed off the corrected card's stored "
            "number through the real `_key_printed_code`, finds the same row the correction "
            "chose — the number this route wrote is not merely display-shaped right, it is "
            "JOIN-shaped right",
            f"rejoin_key={rejoin_key!r} rows={[row[tcgcsv.SKU_COLUMN] for row in rejoin_rows]}",
        )

        after_release = Store().read().inventory.listings[old_sku]
        checks.equal(
            (after_release.pushed, after_release.live),
            (0, 1),
            "and the OLD sku gave up exactly one pushed copy — least-committed-first left "
            "`live` untouched, because one copy was enough to cover the release",
        )
        checks.ok(
            new_sku not in Store().read().inventory.listings,
            "the NEW sku gets no listing record — choosing a catalog row is not pushing "
            "one, and nothing here duplicates what `emit` alone does",
        )

        line = last_event("4/1")
        checks.equal(
            line.get("event"),
            "sku_corrected",
            "the history line is its OWN event name, never `answered` — a correction is a "
            "different claim from an ordinary D4 answer",
        )
        checks.equal(
            line.get("restores_to", {}).get("sku"),
            old_sku,
            "and it carries the old pair, which is what the undo reads back",
        )

        # -------------------------------------------------------- item 2 of the brief itself
        #
        # PROVEN AGAINST THE REAL MODULE, NOT REINVENTED. `pipeline/livecheck.py:compare` is
        # what `banchi reconcile --live` calls — D109's own `beyond` bucket: "TCGplayer's
        # own quantity for a SKU this pipeline never sent — more than it sent". A live export
        # that still shows the old sku's copy (nobody has told TCGplayer yet) now reads as
        # exactly that, with no second mechanism built to say so.
        after = Store().read().inventory
        sold, hand, seen = cmd_reconcile._card_counts(after)
        report = livecheck.compare(
            [{"TCGplayer Id": old_sku, "Total Quantity": "1"}],
            after.listings,
            sold,
            hand,
            seen,
        )
        checks.ok(
            any(row.sku == old_sku for row in report.beyond),
            "the corrected-away sku reads as `beyond` on the very next live reconcile — "
            "TCGplayer still shows it, and nothing here sent it any more",
            f"beyond: {[row.sku for row in report.beyond]}",
        )
        checks.ok(
            not any(row.sku == old_sku for row in report.agreed + report.unexplained),
            "and it does not also read as agreed or unexplained — one bucket, one sentence",
        )

    # Fresh store for the undo path, so the sequencing above cannot leak into it.
    with isolated_home() as home:
        run_dir = home / "runs" / "2026-09-23-box4-01"
        run_dir.mkdir(parents=True)
        shutil.copy(RIFTBOUND_EXPORT, run_dir / "export.csv")
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "created_at": "2026-09-23T00:00:00+00:00",
                    "joined": True,
                    "exports": {"riftbound": {"path": str(run_dir / "export.csv")}},
                }
            )
        )
        capture_server.do_capture(capture_payload(4, game="riftbound"))
        with Store().write() as snapshot:
            snapshot.inventory.cards["4/1"].game = "riftbound"
            snapshot.inventory.cards["4/1"].run = "2026-09-23-box4-01"
            snapshot.inventory.set_state("4/1", master.IDENTIFIED)
            # DIRECT FIELD WRITE, NOT `_bind`: this card must carry no `rarity`/`number` at
            # all going in — "never carried a number or a rarity at all" is the exact shape
            # the undo assertion below checks the correction restores to. `bind_sku` always
            # derives both together with `sku`/`condition`, so it cannot build this state.
            snapshot.inventory.cards["4/1"].sku = old_sku
            snapshot.inventory.cards["4/1"].condition = "Near Mint"
            snapshot.inventory.cards["4/1"].name = old_name
            snapshot.inventory.listing(old_sku, condition="Near Mint").set(
                master.PUSHED, 1
            )

        refusal(
            checks,
            lambda: capture_server.do_correct_answer(4, 1, {"undo": True}),
            "not_corrected",
            "an undo where nothing was ever corrected refuses",
        )

        capture_server.do_correct_answer(4, 1, {"sku": new_sku})
        corrected_card = Store().read().inventory.cards["4/1"]
        checks.equal(
            (corrected_card.rarity, corrected_card.number, corrected_card.printed_total),
            ("Uncommon", "056/298", None),
            "before the undo: this card never carried a number or a rarity at all — "
            "answered wrong, never corrected before — and the correction still writes "
            "both from the chosen row, exactly as the identified-then-wrong card above did "
            "— stored WHOLE, Riftbound being `printed_code`",
        )

        undone = answers(
            checks,
            lambda: capture_server.do_correct_answer(4, 1, {"undo": True}),
            "the undo puts the correction back",
        )
        if undone is not None:
            checks.equal(undone["sku"], old_sku, "the old sku is restored")
        restored_card = Store().read().inventory.cards["4/1"]
        checks.equal(
            (restored_card.sku, restored_card.condition, restored_card.name),
            (old_sku, "Near Mint", old_name),
            "the whole pair — sku, condition and name — comes back",
        )
        checks.equal(
            (restored_card.rarity, restored_card.number, restored_card.printed_total),
            (None, None, None),
            "and rarity/number come back too, to exactly what they were before the "
            "correction — nothing here, since this card was never corrected before — "
            "restored VERBATIM rather than guessed, the same rule `_give_back_listing`'s "
            "own stamps follow",
        )
        restored_listing = Store().read().inventory.listings[old_sku]
        checks.equal(
            restored_listing.pushed,
            1,
            "and the released copy is handed back to the old sku's own record",
        )

        refusal(
            checks,
            lambda: capture_server.do_correct_answer(4, 1, {"undo": True}),
            "not_corrected",
            "a SECOND undo refuses — the card's own sku no longer matches the newest "
            "correction line, which is the ground truth this reversal reads rather than a "
            "flag",
        )

        # --------------------------------------------------------- undo_too_late, symmetric
        capture_server.do_correct_answer(4, 1, {"sku": new_sku})
        with Store().write() as snapshot:
            snapshot.inventory.listing(new_sku, condition="Near Mint").set(
                master.LIVE, 1
            )
        refusal(
            checks,
            lambda: capture_server.do_correct_answer(4, 1, {"undo": True}),
            "undo_too_late",
            "an undo refuses once the NEW sku is itself out of this Mac — the same guard "
            "do_review_answer's own undo checks, read on the card's current sku",
        )

        corrupt_history(position="4/1")
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_correct_answer(4, 1, {"undo": True}),
            "a log that will not read refuses rather than guessing a pair back",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None),
                "correction_origin_unknown",
                "in its own code",
            )

    # ------------------------------------------------- a Pokemon correction, split correctly
    #
    # Item 3's second half. Riftbound above proves the verbatim branch; this proves the
    # OTHER branch — `number_and_printed_total` — still splits, over the committed SV09
    # export, a real row.
    with isolated_home() as home:
        pokemon_sku, pokemon_name, pokemon_number = "8607459", "Accelgor", "013/159"
        wrong_sku = "8607749"  # Alolan Geodude, same export — a real row, just the wrong one
        run_dir = home / "runs" / "2026-09-23-box7-01"
        run_dir.mkdir(parents=True)
        shutil.copy(FIXTURE_EXPORT, run_dir / "export.csv")
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "created_at": "2026-09-23T00:00:00+00:00",
                    "joined": True,
                    "exports": {"pokemon": {"path": str(run_dir / "export.csv")}},
                }
            )
        )
        capture_server.do_capture(capture_payload(7, game="pokemon"))
        with Store().write() as snapshot:
            snapshot.inventory.cards["7/1"].game = "pokemon"
            snapshot.inventory.cards["7/1"].run = "2026-09-23-box7-01"
            # DIRECT FIELD WRITE, NOT `_bind`: `rarity` stays unset going in, matching this
            # function's other fixtures — `bind_sku` always derives it with `sku`/`condition`.
            snapshot.inventory.set_state("7/1", master.IDENTIFIED)
            snapshot.inventory.cards["7/1"].sku = wrong_sku
            snapshot.inventory.cards["7/1"].condition = "Near Mint"
            snapshot.inventory.cards["7/1"].name = "Alolan Geodude"
            snapshot.inventory.cards["7/1"].number = "044"
            snapshot.inventory.cards["7/1"].printed_total = "159"

        pokemon_body = answers(
            checks,
            lambda: capture_server.do_correct_answer(7, 1, {"sku": pokemon_sku}),
            "a Pokemon correction succeeds",
        )
        if pokemon_body is not None:
            checks.equal(pokemon_body["sku"], pokemon_sku, "and reports the new sku")
        pokemon_card = Store().read().inventory.cards["7/1"]
        checks.equal(
            (pokemon_card.name, pokemon_card.number, pokemon_card.printed_total),
            (pokemon_name, "013", "159"),
            "a `number_and_printed_total` game DOES split the composed cell — `013/159` "
            "becomes the pair `join_key` built it from, the branch Riftbound above must "
            "never take",
        )
        checks.equal(
            capture_server._card_number_key(pokemon_card),
            pokemon_number,
            "and `number_key` is populated here, unlike the Riftbound case — this is the "
            "game the field was designed for",
        )
        pokemon_catalog = join.Catalog.from_export(
            tcgcsv.read_export(run_dir / "export.csv"), "pokemon"
        )
        pokemon_rejoin_key = join._key_number_and_printed_total(
            join.IdentifiedCard(
                position=None, name=pokemon_card.name, number=pokemon_card.number,
                printed_total=pokemon_card.printed_total,
            )
        )
        pokemon_rejoin_rows = (
            pokemon_catalog.rows_for_key(pokemon_rejoin_key) if pokemon_rejoin_key else []
        )
        checks.ok(
            any(str(row[tcgcsv.SKU_COLUMN]) == pokemon_sku for row in pokemon_rejoin_rows),
            "and a fresh join over the corrected pair, through the real "
            "`_key_number_and_printed_total`, finds the same row",
        )

    # --------------------------------------------- item 4: a MISSING key is not a null claim
    #
    # The three real `sku_corrected` events on the owner's live store predate this fix and
    # carry no `number`/`printed_total` in `restores_to` at all — that route never touched
    # those fields until now. An undo reading a missing key as `None` would ERASE a real
    # number the old line was never responsible for losing. `append_history` hand-writes
    # exactly that pre-fix shape; no route on this branch can produce it any more.
    with isolated_home() as home:
        run_dir = home / "runs" / "2026-09-23-box4-01"
        run_dir.mkdir(parents=True)
        shutil.copy(RIFTBOUND_EXPORT, run_dir / "export.csv")
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "created_at": "2026-09-23T00:00:00+00:00",
                    "joined": True,
                    "exports": {"riftbound": {"path": str(run_dir / "export.csv")}},
                }
            )
        )
        capture_server.do_capture(capture_payload(4, game="riftbound"))
        with Store().write() as snapshot:
            snapshot.inventory.cards["4/1"].game = "riftbound"
            snapshot.inventory.cards["4/1"].run = "2026-09-23-box4-01"
            # DIRECT FIELD WRITE, NOT `_bind`: `rarity` stays unset, this function's own
            # recurring shape — `bind_sku` always derives it with `sku`/`condition`.
            snapshot.inventory.set_state("4/1", master.IDENTIFIED)
            snapshot.inventory.cards["4/1"].sku = new_sku
            snapshot.inventory.cards["4/1"].condition = "Near Mint"
            snapshot.inventory.cards["4/1"].name = new_name
            # WHATEVER THE CARD CARRIES NOW — this run wrote it after the hand-crafted
            # correction below, exactly as a real one-time repair or a later re-identify
            # would. The undo must leave it exactly here.
            snapshot.inventory.cards["4/1"].number = "999/999"

        append_history(
            [
                {
                    "at": master.now(),
                    "event": "sku_corrected",
                    "position": "4/1",
                    "sku": new_sku,
                    "condition": "Near Mint",
                    "set_name": None,
                    "rarity": None,
                    "name": new_name,
                    "restores_to": {
                        "sku": old_sku,
                        "condition": "Near Mint",
                        "set_name": None,
                        "rarity": None,
                        "name": old_name,
                        # NO "number" KEY. NO "printed_total" KEY. The pre-fix shape,
                        # verbatim — the three real lines on the owner's store look exactly
                        # like this.
                    },
                    "released": None,
                    "old_sku": old_sku,
                    "stamps": None,
                }
            ]
        )

        old_shape_undone = answers(
            checks,
            lambda: capture_server.do_correct_answer(4, 1, {"undo": True}),
            "an old-shape correction line (no number/printed_total in restores_to) still "
            "undoes",
        )
        if old_shape_undone is not None:
            checks.equal(
                old_shape_undone["sku"], old_sku, "the fields the old line DID record come back"
            )
        restored = Store().read().inventory.cards["4/1"]
        checks.equal(
            (restored.sku, restored.name),
            (old_sku, old_name),
            "sku and name restore normally — both were recorded on the old-shape line",
        )
        checks.equal(
            restored.number,
            "999/999",
            "but NUMBER IS UNTOUCHED — the old line never recorded what it replaced, and a "
            "MISSING key means leave the field exactly where it stands, never guess `None`",
        )


def check_correct_answer_live_release(checks: Checks) -> None:
    """POST /inventory/<box>/<index>/correct — the `live` stage of the release, and the
    stamps a round trip must not corrupt. D252, review round 2.

    `Listing.release`'s own rule is least-committed-first: `pushed`, then `staged`, then
    `live`. Every other case in `check_correct_answer` leaves `pushed` non-zero, so the
    release never reaches past it — `_give_back_listing`'s `master.LIVE` branch has never
    run. This fixture starts the old SKU at `pushed=0, staged=0, live=2`, so the ONE copy
    this correction gives up has nowhere else to come from.

    AND `release()` RESTAMPS `live_as_of` TO NOW WHEN IT TAKES FROM `live` — D34's own rule,
    "an observation made now, like a sale" — so the stamp the operator's ORIGINAL live
    reading carried is gone the moment the correction lands. The undo must not read that
    loss as further permission to restamp AGAIN to whatever "now" happens to be when the
    undo is pressed: `stamps` on the `sku_corrected` line carries the PRE-CORRECTION value,
    and `_give_back_listing` puts it back verbatim once the counts are restored.
    """
    checks.note("")
    checks.note("CORRECT A LISTED ANSWER — the live stage, and the stamp round trip")

    old_sku, new_sku = "8926937", "8925897"
    original_live_as_of = "2020-01-01T00:00:00+00:00"

    with isolated_home() as home:
        run_dir = home / "runs" / "2026-09-23-box5-01"
        run_dir.mkdir(parents=True)
        shutil.copy(RIFTBOUND_EXPORT, run_dir / "export.csv")
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "created_at": "2026-09-23T00:00:00+00:00",
                    "joined": True,
                    "exports": {"riftbound": {"path": str(run_dir / "export.csv")}},
                }
            )
        )
        capture_server.do_capture(capture_payload(5, game="riftbound"))
        with Store().write() as snapshot:
            snapshot.inventory.cards["5/1"].game = "riftbound"
            snapshot.inventory.cards["5/1"].run = "2026-09-23-box5-01"
            snapshot.inventory.set_state("5/1", master.IDENTIFIED)
            _bind(snapshot, "5/1", old_sku, game="riftbound")
            # `pushed` and `staged` are BOTH zero — the one copy the correction gives up can
            # only come from `live`, which is the branch under test.
            snapshot.inventory.listing(old_sku, condition="Near Mint").set(master.LIVE, 2)
            snapshot.inventory.listings[old_sku].live_as_of = original_live_as_of

        before = Store().read().inventory.listings[old_sku]
        checks.equal(
            (before.pushed, before.staged, before.live, before.live_as_of),
            (0, 0, 2, original_live_as_of),
            "before the correction: nothing pushed or staged, two copies live, an old reading",
        )

        body = answers(
            checks,
            lambda: capture_server.do_correct_answer(5, 1, {"sku": new_sku}),
            "the correction succeeds with nothing to release from pushed or staged",
        )
        if body is not None:
            checks.equal(
                body["released"],
                {"live": 1},
                "and `Listing.release` reached `live` — the branch `_give_back_listing` had "
                "never exercised",
            )

        after_release = Store().read().inventory.listings[old_sku]
        checks.equal(
            (after_release.pushed, after_release.staged, after_release.live),
            (0, 0, 1),
            "one live copy is given up, and nothing else moves",
        )
        checks.ok(
            after_release.live_as_of != original_live_as_of,
            "and `release()` restamped `live_as_of` to now — D34's own rule for a copy taken "
            "off `live`, unchanged by this correction",
        )

        undone = answers(
            checks,
            lambda: capture_server.do_correct_answer(5, 1, {"undo": True}),
            "the undo gives the live copy back",
        )
        restored = Store().read().inventory.listings[old_sku]
        checks.equal(
            (restored.pushed, restored.staged, restored.live),
            (0, 0, 2),
            "every count is restored exactly, live included",
        )
        checks.equal(
            restored.live_as_of,
            original_live_as_of,
            "and `live_as_of` is the PRE-CORRECTION stamp, not `release()`'s restamp and not "
            "a fresh `now` from the undo itself — a correct-then-undo round trip must not "
            "manufacture a reading nobody took, which is exactly what `staged_stale` and "
            "`reprice` would otherwise read as new evidence",
        )
        if undone is not None:
            checks.ok(True, "and the route itself answered")


def check_identity_binding(checks: Checks) -> None:
    """identity-follows-sku.md, lane 3a's own coverage. Every server writer that sets a SKU
    binds through `Inventory.bind_sku` — never `set_state` with an identity kwarg — the new
    confirm press and its undo, and how a `listing_disputed` answer routes on `#/review`.

    D252's own three checks (`check_correct_answer`, `check_correct_answer_live_release`,
    `check_catalog_set_rarity_match`, right beside this one) already prove
    `do_correct_answer`'s field values are unchanged now that it writes them through
    `bind_sku` — the point of THIS section is the bookkeeping those checks never looked at:
    `bound_by`, `identity_source`, and the `skus` table row each writer upserts before it
    binds.
    """
    checks.note("")
    checks.note("IDENTITY BINDING — every SKU writer through bind_sku "
                "(identity-follows-sku.md)")

    # ------------------------------------------------------ do_review_answer: bound_by=answer
    with isolated_home():
        capture_server.do_capture(capture_payload(60))
        with Store().write() as snapshot:
            snapshot.inventory.set_state("60/1", master.IDENTIFIED)
            snapshot.review.upsert(entry(60, 1))  # default candidates: both of CANDIDATES

        picked = CANDIDATES[0]

        # §4.2's review round: "no partial upsert into skus" — a review answer REFUSES a
        # SKU the table does not already hold, rather than inventing a partial row off the
        # candidate's own abbreviated shape. Checked BEFORE seeding, so this is a real red
        # rather than an assumed one.
        refusal(
            checks,
            lambda: capture_server.do_review_answer(
                60, 1, {"sku": picked["sku"], "condition": picked["condition"]}
            ),
            "sku_unknown",
            "answering a sku the `skus` table has never seen refuses — a review answer "
            "binds to a row the table ALREADY holds, never one it invents",
        )
        checks.ok(
            Store().read().inventory.cards["60/1"].sku is None,
            "and that refusal wrote nothing onto the card",
        )

        # THE TABLE IS SEEDED THE WAY A REAL FETCH OR `banchi skus adopt` WOULD FILL IT —
        # never by this route. `_seed_sku_table` folds through the real
        # `pipeline/skus.py:apply_rows`, the SAME fold `do_pipeline_export`/`do_live_export`
        # use (proved by `check_export_fetch`'s own two new assertions).
        with Store().write() as snapshot:
            _seed_sku_table(snapshot, CANDIDATES)

        answers(
            checks,
            lambda: capture_server.do_review_answer(
                60, 1, {"sku": picked["sku"], "condition": picked["condition"]}
            ),
            "and now that the table holds the row, an ordinary D4 answer succeeds",
        )
        card = Store().read().inventory.cards["60/1"]
        checks.equal(
            (card.sku, card.bound_by, card.identity_source),
            (picked["sku"], "answer", master.IDENTITY_SKU),
            "§4.1: the answer binds through `bind_sku`, and `bound_by`/`identity_source` "
            "say so — two fields no version of this route wrote before lane 3a",
        )
        checks.equal(
            card.name,
            picked["name"],
            "and the identity name follows the SKU rather than being left as the read "
            "(§4.2: the OLD route 'leaves name and number as the read')",
        )
        events = Store().history()
        checks.ok(
            any(
                e.get("event") == "sku_bound" and e.get("position") == "60/1"
                for e in events
            ),
            "bind_sku's own history line lands beside the route's",
        )
        checks.ok(
            any(
                e.get("event") == "answered" and e.get("position") == "60/1"
                for e in events
            ),
            "and the route's own `answered` line is UNCHANGED — every existing D4 reader "
            "still finds it",
        )

        # D28: UNDO MUST BE EXACT. The card started never-bound; its undo must restore
        # exactly that, through `Inventory.restore_identity` — no field-by-field code left
        # in `_reverse_answer` (review round, identity-follows-sku.md §8).
        answers(
            checks,
            lambda: capture_server.do_review_answer(60, 1, {"undo": True}),
            "the answer's own undo goes through",
        )
        _assert_identity_round_trip(
            checks,
            NEVER_BOUND_IDENTITY_SNAPSHOT,
            Store().read().inventory.identity_snapshot("60/1"),
            "do_review_answer's undo",
        )

    # ------------------------------------------------ do_review_group_answer: group_answer
    with isolated_home():
        for _ in range(3):
            capture_server.do_capture(capture_payload(61))
        cond = CANDIDATES[0]["condition"]
        with Store().write() as snapshot:
            for i in range(1, 4):
                snapshot.inventory.set_state(f"61/{i}", master.IDENTIFIED)
            for i, sku in ((1, "9201"), (2, "9202"), (3, "9203")):
                snapshot.review.upsert(
                    entry(61, i, candidates=[dict(CANDIDATES[0], sku=sku)])
                )
            _seed_sku_table(
                snapshot,
                [dict(CANDIDATES[0], sku=sku) for sku in ("9201", "9202", "9203")],
            )
        answers(
            checks,
            lambda: capture_server.do_review_group_answer(
                {
                    "answers": [
                        {"box": 61, "index": 1, "sku": "9201", "condition": cond},
                        {"box": 61, "index": 2, "sku": "9202", "condition": cond},
                        {"box": 61, "index": 3, "sku": "9203", "condition": cond},
                    ]
                }
            ),
            "a homogeneous group answers",
        )
        for i, sku in ((1, "9201"), (2, "9202"), (3, "9203")):
            card = Store().read().inventory.cards[f"61/{i}"]
            checks.equal(
                (card.sku, card.bound_by, card.identity_source),
                (sku, "group_answer", master.IDENTITY_SKU),
                f"§4.2: 61/{i} binds through `bind_sku(bound_by=group_answer)` too, one "
                f"bind per card, against the row the table already held",
            )

        # D28: undo must be exact — one member's own undo, per D29's shape (the write is
        # all-or-nothing, the reversal is per card, through `do_review_answer`).
        answers(
            checks,
            lambda: capture_server.do_review_answer(61, 1, {"undo": True}),
            "one group member's own undo goes through",
        )
        _assert_identity_round_trip(
            checks,
            NEVER_BOUND_IDENTITY_SNAPSHOT,
            Store().read().inventory.identity_snapshot("61/1"),
            "do_review_group_answer's per-card undo",
        )

    # ------------------------------------------------ do_correct_answer: bound_by=correction
    with isolated_home() as home:
        old_sku, new_sku = "8926937", "8925897"
        run_dir = home / "runs" / "2026-09-24-box62-01"
        run_dir.mkdir(parents=True)
        shutil.copy(RIFTBOUND_EXPORT, run_dir / "export.csv")
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "created_at": "2026-09-24T00:00:00+00:00",
                    "joined": True,
                    "exports": {"riftbound": {"path": str(run_dir / "export.csv")}},
                }
            )
        )
        capture_server.do_capture(capture_payload(62, game="riftbound"))
        with Store().write() as snapshot:
            snapshot.inventory.cards["62/1"].game = "riftbound"
            snapshot.inventory.cards["62/1"].run = "2026-09-24-box62-01"
            snapshot.inventory.set_state("62/1", master.IDENTIFIED)
            _bind(snapshot, "62/1", old_sku, game="riftbound")
        before_correction = Store().read().inventory.identity_snapshot("62/1")
        answers(
            checks,
            lambda: capture_server.do_correct_answer(62, 1, {"sku": new_sku}),
            "a correction succeeds",
        )
        card = Store().read().inventory.cards["62/1"]
        checks.equal(
            (card.bound_by, card.identity_source),
            ("correction", master.IDENTITY_SKU),
            "§4.2: `do_correct_answer` binds through `bind_sku(bound_by=correction)` too — "
            "the D252 field values themselves are proved unchanged by "
            "`check_correct_answer`, right beside this section",
        )
        checks.ok(
            Store().read().skus.entries.get(new_sku) is not None,
            "and the new row is upserted into the `skus` table before the bind — "
            "`do_correct_answer` is the one writer left that still fills the table, "
            "because it re-reads a real row off the export (D77) and folds it whole "
            "through `_fold_export_row`, never a partial one",
        )
        last = last_event("62/1")
        checks.equal(
            last.get("event"),
            "sku_corrected",
            "and `sku_corrected` is STILL the last event — bind_sku's own `sku_bound` line "
            "lands first, so `_reverse_correction`'s `last-event` reader is unaffected",
        )

        undone = answers(
            checks,
            lambda: capture_server.do_correct_answer(62, 1, {"undo": True}),
            "and its undo goes through `Inventory.restore_identity` (§8, review round) — "
            "no field-by-field code left in `_reverse_correction`",
        )
        if undone is not None:
            checks.equal(undone["sku"], old_sku, "the old sku is restored")
        _assert_identity_round_trip(
            checks,
            before_correction,
            Store().read().inventory.identity_snapshot("62/1"),
            "do_correct_answer's undo",
        )

    # ---------------------------------------------------- POST .../confirm and its undo (§8.1)
    with isolated_home():
        held_sku = "7000001"
        held_row = SkuRow(
            product_line="Riftbound League of Legends Trading Card Game",
            set_name="Origins",
            product_name="Master Yi, Wuju Master",
            number="191/219",
            rarity="Rare",
            condition="Near Mint",
            grade="Near Mint",
            printing=None,
            first_seen=1_700_000_000,
            last_seen=1_700_000_000,
            source="t7-fixture",
            raw={},
        )
        for _ in range(4):
            capture_server.do_capture(capture_payload(63))
        with Store().write() as snapshot:
            snapshot.skus.entries[held_sku] = held_row
            # 63/1 — the held card: a SKU already on it, a read that disputes it, and
            # `identity_source = read` — §7.3's own T5 shape ("write identity_source =
            # read. Leave every identity field exactly as it is today"). `hold_sku`, the
            # sanctioned writer for exactly this shape (§4.1), in place of the retired
            # `set_state(sku=...)` shortcut.
            snapshot.inventory.set_state("63/1", master.IDENTIFIED)
            snapshot.inventory.hold_sku(
                "63/1", held_sku, skus=snapshot.skus, read_disputes=True
            )
            snapshot.inventory.cards["63/1"].game = "riftbound"
            snapshot.inventory.cards["63/1"].read_name = "Yi, Ionia"
            # §3.1: "read: ...the identity fields equal the evidence fields" — a real held
            # card's `name` already equals its own `read_name`, so the fixture sets both
            # rather than leaving `name` at its default and asking the confirm's undo to
            # derive one restore_identity was never built to derive. `identity_source` and
            # `read_disputes` are already `hold_sku`'s own doing, above.
            snapshot.inventory.cards["63/1"].name = "Yi, Ionia"
            # 63/2 — never identified, for `not_identified`.
            # 63/3 — sold, for `card_departed`. `held_row`'s own row, already in the
            # table above — `bind_sku` directly rather than `_bind`, which would plant a
            # second, different fake row under the same `held_sku` key.
            snapshot.inventory.set_state("63/3", master.IDENTIFIED)
            snapshot.inventory.bind_sku(
                "63/3", held_sku, bound_by="answer", skus=snapshot.skus,
                number_strategy="printed_code",
            )
            snapshot.inventory.set_state("63/3", master.SOLD)
            # 63/4 — a SKU with no row in the table, for `sku_unknown`. DIRECT FIELD
            # WRITE: this is the one state neither `bind_sku` nor `hold_sku` can build —
            # both refuse `SkuUnknown` on a sku with no row, and this fixture needs the
            # card to already carry one anyway, to prove the route refuses it too.
            snapshot.inventory.set_state("63/4", master.IDENTIFIED)
            snapshot.inventory.cards["63/4"].sku = "7000404"
            snapshot.inventory.cards["63/4"].condition = "Near Mint"
            snapshot.inventory.cards["63/4"].game = "riftbound"

        refusal(
            checks,
            lambda: capture_server.do_confirm_identity(99, 99, {}),
            "card_not_found",
            "a confirm for a position with no record refuses",
        )
        refusal(
            checks,
            lambda: capture_server.do_confirm_identity(63, 3, {}),
            "card_departed",
            "a confirm on a sold card refuses — a departed card's identity is frozen (D134)",
        )
        refusal(
            checks,
            lambda: capture_server.do_confirm_identity(63, 2, {}),
            "not_identified",
            "a confirm on a card with no SKU refuses — there is no listing to confirm",
        )
        refusal(
            checks,
            lambda: capture_server.do_confirm_identity(63, 4, {}),
            "sku_unknown",
            "a confirm whose SKU is not in the `skus` table refuses rather than guessing",
        )
        refusal(
            checks,
            lambda: capture_server.do_confirm_identity(63, 1, {"sku": "anything"}),
            "field_not_settable",
            "confirm never takes a `sku` in the body — it confirms the card's own current "
            "one, or it is `do_correct_answer`'s job",
        )

        # identity-follows-sku.md §5.4/§8.1, review round: "Listed as"/"Read as" ride on
        # `GET /inventory/<box>` too — the route Details' initial render reads, before any
        # press. 63/1 is held: shown (`name`) equals the read by construction, so
        # `listing_differs` is the only one of the two that should be true here.
        before_box = capture_server.do_inventory_box(63)["cards"]["63/1"]
        checks.equal(
            before_box.get("listing"),
            {"name": "Master Yi, Wuju Master", "number": "191/219", "printed_total": None},
            "`_listing_decoration` reads the `skus` table off the card's own SKU and "
            "composes it exactly as `bind_sku` would",
        )
        checks.equal(
            before_box.get("listing_differs"),
            True,
            "and `listing_differs` is true — the listing's own name disputes the shown "
            "name (\"Yi, Ionia\" against \"Master Yi, Wuju Master\")",
        )
        checks.equal(
            before_box.get("reading_differs"),
            False,
            "while `reading_differs` is false — a held card's shown pair equals the read "
            "pair by construction, which is the fix for \"Read as\" repeating "
            "Card:/Number: word for word",
        )

        before_confirm = Store().read().inventory.identity_snapshot("63/1")
        confirmed = answers(
            checks,
            lambda: capture_server.do_confirm_identity(63, 1, {}),
            "confirming a held card succeeds",
        )
        if confirmed is not None:
            checks.equal(confirmed.get("confirmed"), True, "and it reports which direction")
            confirmed_card = confirmed.get("card") or {}
            checks.equal(
                confirmed_card.get("listing_differs"),
                False,
                "§5.4/§8.1: the confirm's own response carries `listing_differs` too, and "
                "it is now false — the identity equals the listing by construction "
                "(`bind_sku` wrote it off this same row)",
            )
            checks.equal(
                confirmed_card.get("reading_differs"),
                True,
                "while `reading_differs` turns true — the camera's read (\"Yi, Ionia\") "
                "still disagrees with the now-bound catalog name, exactly the case "
                "\"Read as\" exists for",
            )
        card = Store().read().inventory.cards["63/1"]
        checks.equal(
            (card.sku, card.bound_by, card.identity_source),
            (held_sku, "confirm", master.IDENTITY_SKU),
            "§8.1: `bind_sku(current sku, bound_by=confirm)` — the SKU never moves",
        )
        checks.equal(
            (card.name, card.number),
            ("Master Yi, Wuju Master", "191/219"),
            "and the identity now follows the table row — Riftbound's `printed_code` "
            "strategy stores the number verbatim",
        )

        refusal(
            checks,
            lambda: capture_server.do_confirm_identity(63, 1, {}),
            "already_confirmed",
            "confirming an already-SKU-bound card refuses — there is nothing left to do",
        )

        undone = answers(
            checks,
            lambda: capture_server.do_confirm_identity(63, 1, {"undo": True}),
            "the undo puts the confirm back",
        )
        if undone is not None:
            checks.equal(undone.get("undone"), True, "and it reports which direction")
            undone_card = undone.get("card") or {}
            checks.equal(
                undone_card.get("listing_differs"),
                True,
                "§5.4/§8.1: the undo's own response shows `listing_differs` back to true "
                "— the card is held again and the listing disputes the shown name",
            )
            checks.equal(
                undone_card.get("reading_differs"),
                False,
                "and `reading_differs` back to false — the shown pair equals the read "
                "pair again",
            )
        card = Store().read().inventory.cards["63/1"]
        checks.equal(
            (card.sku, card.identity_source, card.name),
            (held_sku, master.IDENTITY_READ, "Yi, Ionia"),
            "§8.1: the undo returns `identity_source` to `read` — the SKU stays exactly "
            "where it was (a confirm never moves it, so nothing here releases anything), "
            "and the name comes back off `read_name`",
        )
        _assert_identity_round_trip(
            checks,
            before_confirm,
            Store().read().inventory.identity_snapshot("63/1"),
            "do_confirm_identity's undo",
        )

        refusal(
            checks,
            lambda: capture_server.do_confirm_identity(63, 1, {"undo": True}),
            "not_confirmed",
            "a second undo refuses — the ground truth is the card's own `bound_by`, not a "
            "flag on an event",
        )

    # ------------------------------- a `listing_disputed` answer, routed inside do_review_answer
    with isolated_home():
        disputed_sku = "7100001"
        other_sku = "7100002"
        disputed_row = SkuRow(
            product_line="Riftbound League of Legends Trading Card Game",
            set_name="Origins", product_name="Jax, Icathia", number="1/14",
            rarity="Epic", condition="Near Mint", grade="Near Mint", printing=None,
            first_seen=1_700_000_000, last_seen=1_700_000_000, source="t7-fixture", raw={},
        )
        other_row = SkuRow(
            product_line="Riftbound League of Legends Trading Card Game",
            set_name="Origins", product_name="Jax, Unmatched", number="2/14",
            rarity="Epic", condition="Near Mint", grade="Near Mint", printing=None,
            first_seen=1_700_000_000, last_seen=1_700_000_000, source="t7-fixture", raw={},
        )
        for _ in range(2):
            capture_server.do_capture(capture_payload(64))
        with Store().write() as snapshot:
            snapshot.skus.entries[disputed_sku] = disputed_row
            snapshot.skus.entries[other_sku] = other_row
            for i in (1, 2):
                snapshot.inventory.set_state(f"64/{i}", master.IDENTIFIED)
                snapshot.inventory.bind_sku(
                    f"64/{i}", disputed_sku, bound_by="answer", skus=snapshot.skus,
                    number_strategy="printed_code",
                )
                snapshot.inventory.cards[f"64/{i}"].game = "riftbound"
                snapshot.inventory.cards[f"64/{i}"].read_name = "Jax, Icathia"
            disputed_candidates = [
                {
                    "sku": disputed_sku, "name": "Jax, Icathia", "set": "Origins",
                    "number": "1/14", "condition": "Near Mint", "market": "1.00",
                    "rarity": "Epic",
                },
                {
                    "sku": other_sku, "name": "Jax, Unmatched", "set": "Origins",
                    "number": "2/14", "condition": "Near Mint", "market": "1.00",
                    "rarity": "Epic",
                },
            ]
            snapshot.review.upsert(
                entry(
                    64, 1, reason=routing.LISTING_DISPUTED, candidates=disputed_candidates,
                )
            )
            snapshot.review.upsert(
                entry(
                    64, 2, reason=routing.LISTING_DISPUTED, candidates=disputed_candidates,
                )
            )

        # --------------------------------------------------------- "the listing is right"
        confirmed = answers(
            checks,
            lambda: capture_server.do_review_answer(
                64, 1, {"sku": disputed_sku, "condition": "Near Mint"}
            ),
            "§8.1: answering a `listing_disputed` entry with the card's OWN current sku "
            "confirms rather than re-answering",
        )
        if confirmed is not None:
            checks.equal(
                (confirmed.get("confirmed"), confirmed.get("corrected")),
                (True, False),
                "the response says which press this was",
            )
            checks.ok(
                confirmed.get("review_cleared"),
                "and the queue entry is cleared like any other answer",
            )
        card = Store().read().inventory.cards["64/1"]
        checks.equal(
            (card.bound_by, card.identity_source, card.name),
            ("confirm", master.IDENTITY_SKU, "Jax, Icathia"),
            "the same sku, bound through `bind_sku(bound_by=confirm)` — never `answer`",
        )

        # ------------------------------------------------- "the listing is the wrong card"
        before_disputed_correction = Store().read().inventory.identity_snapshot("64/2")
        corrected = answers(
            checks,
            lambda: capture_server.do_review_answer(
                64, 2, {"sku": other_sku, "condition": "Near Mint"}
            ),
            "§8.1: answering with any OTHER sku is the D252 correction, unchanged in "
            "meaning",
        )
        if corrected is not None:
            checks.equal(
                (corrected.get("confirmed"), corrected.get("corrected")),
                (False, True),
                "the response says which press this was",
            )
            checks.equal(
                corrected.get("previous_sku"), disputed_sku,
                "and it reports the sku it replaced, `do_correct_answer`'s own field",
            )
            checks.ok(
                corrected.get("review_cleared"),
                "and the queue entry is cleared here too",
            )
        card = Store().read().inventory.cards["64/2"]
        checks.equal(
            (card.sku, card.bound_by, card.name),
            (other_sku, "correction", "Jax, Unmatched"),
            "the card now carries the OTHER row, bound through "
            "`bind_sku(bound_by=correction)`",
        )
        last = last_event("64/2")
        checks.equal(
            last.get("event"),
            "sku_corrected",
            "and the same `sku_corrected` line `do_correct_answer` itself writes — the two "
            "doors write one shape, exactly as §8.1 says: unchanged in meaning",
        )
        undone = answers(
            checks,
            lambda: capture_server.do_correct_answer(64, 2, {"undo": True}),
            "and the SAME reversal `do_correct_answer` uses on `#/inventory` takes it back, "
            "because the two doors wrote the identical event shape",
        )
        if undone is not None:
            checks.equal(undone["sku"], disputed_sku, "the disputed sku is restored")
        _assert_identity_round_trip(
            checks,
            before_disputed_correction,
            Store().read().inventory.identity_snapshot("64/2"),
            "a listing_disputed correction's undo, through do_correct_answer",
        )

    # -------------------- §4, review round: a group answer refuses listing_disputed entries
    with isolated_home():
        held_sku_a = "7200001"
        held_row_a = SkuRow(
            product_line="Riftbound League of Legends Trading Card Game",
            set_name="Origins", product_name="Jax, Icathia", number="1/14",
            rarity="Epic", condition="Near Mint", grade="Near Mint", printing=None,
            first_seen=1_700_000_000, last_seen=1_700_000_000, source="t7-fixture", raw={},
        )
        for _ in range(3):
            capture_server.do_capture(capture_payload(65))
        with Store().write() as snapshot:
            snapshot.skus.entries[held_sku_a] = held_row_a
            for i in (1, 2):
                snapshot.inventory.set_state(f"65/{i}", master.IDENTIFIED)
                snapshot.inventory.hold_sku(f"65/{i}", held_sku_a, skus=snapshot.skus)
                snapshot.inventory.cards[f"65/{i}"].game = "riftbound"
                snapshot.inventory.cards[f"65/{i}"].read_name = "Jax, Icathia"
                snapshot.inventory.cards[f"65/{i}"].name = "Jax, Icathia"
            # 65/3, an ordinary metadata_detection_disagreement entry, offering the SAME
            # sku and condition — proving the `listing_disputed` refusal fires ahead of
            # the ordinary reasons/uniformity check (which this mixed-reason group would
            # also fail), never folded into `group_not_uniform`'s own findings.
            snapshot.inventory.set_state("65/3", master.IDENTIFIED)
            disputed_candidates = [
                {
                    "sku": held_sku_a, "name": "Jax, Icathia", "set": "Origins",
                    "number": "1/14", "condition": "Near Mint", "market": "1.00",
                    "rarity": "Epic",
                },
            ]
            snapshot.review.upsert(
                entry(65, 1, reason=routing.LISTING_DISPUTED, candidates=disputed_candidates)
            )
            snapshot.review.upsert(
                entry(65, 2, reason=routing.LISTING_DISPUTED, candidates=disputed_candidates)
            )
            snapshot.review.upsert(entry(65, 3, candidates=disputed_candidates))

        def member65(index: int) -> dict:
            return {"box": 65, "index": index, "sku": held_sku_a, "condition": "Near Mint"}

        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_review_group_answer(
                {"answers": [member65(1), member65(2), member65(3)]}
            ),
            "§4, review round: a group carrying a `listing_disputed` entry refuses — the "
            "confirm/correct decision is per card and a group write has no way to make it "
            "safely",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None), "group_listing_disputed",
                "refused by its own name, not folded into group_not_uniform",
            )
            checks.ok(
                "65/1" in str(caught) and "65/2" in str(caught) and "65/3" not in str(caught),
                "and it names the DISPUTED members only — 65/3 is an ordinary entry and "
                "was never the problem",
                str(caught),
            )
        checks.ok(
            Store().read().inventory.cards["65/1"].bound_by is None
            and Store().read().inventory.cards["65/2"].bound_by is None
            and Store().read().inventory.cards["65/3"].sku is None,
            "and nothing was written — not even the ordinary member, because the group is "
            "refused whole",
        )


def check_catalog_number_fields_round_trip(checks: Checks) -> None:
    """`join.catalog_number_fields`, round-tripped over every distinct `Number` cell in the
    four committed exports — item 2 of the review on the D252 amendment. `store/numbers.py:
    split_catalog_number` splitting every game's cell on the last `/` was the CRITICAL defect
    the review caught: Riftbound's 13 double-sided token cells (`T01 // T02`) would come out
    mangled, and every ordinary `printed_code` cell would wrongly fill `number_key`.

    NOT `inventory/.exports/*/…csv` — the owner's real cached exports, which this checkout
    does not carry and which the fence this task carries forbids reading from a live rig.
    The four committed fixtures are the portable, CI-safe stand-in the same fence permits:
    ground truth, never modified, present in every checkout. `docs/map.py`'s `fixtures/`
    entry says so.
    """
    checks.note("")
    checks.note("CATALOG NUMBER FIELDS — round-tripped, game-aware, over every committed "
                "export")

    wide_export = (
        REPO_ROOT / "fixtures" / "pokemon_wide_export_untouched.csv"
    )
    cases = (
        ("pokemon", FIXTURE_EXPORT),
        ("pokemon", wide_export),
        ("riftbound", RIFTBOUND_EXPORT),
        ("one_piece", ONE_PIECE_EXPORT),
    )
    total_checked = 0
    mangled = 0
    double_sided_seen = False
    for game, path in cases:
        export = tcgcsv.read_export(path)
        strategy = games.get(game)["join_key"]
        cells = {
            str(row.get(tcgcsv.NUMBER_COLUMN) or "").strip() for row in export.rows
        }
        cells.discard("")
        for cell in sorted(cells):
            if "//" in cell:
                double_sided_seen = True
            number, printed_total = join.catalog_number_fields(game, cell)
            total_checked += 1
            if strategy == "number_and_printed_total":
                # THE MATCH FOLD, `number_index_key`, NOT RAW STRING EQUALITY. The wide
                # Pokemon export itself carries 99 unpadded cells (`6/236`, SM Cosmic
                # Eclipse) — `number_index_key`'s own docstring measured them, on this
                # exact file, before this test existed. `join_key` always zero-pads, so
                # composing the split pair back reproduces the CANONICAL padded form,
                # `006/236`, never the raw cell for one of those 99 — and that is `join_key`
                # working as designed, not a round-trip failure. `number_index_key` is the
                # fold both sides of a real join already pass through, so it is the
                # correct equivalence here too.
                if join.number_index_key(
                    join.join_key(number, printed_total)
                ) != join.number_index_key(cell):
                    mangled += 1
                    checks.ok(
                        False,
                        f"{game} {cell!r} round-trips through join_key (via number_index_key)",
                        f"got number={number!r} printed_total={printed_total!r}",
                    )
            else:
                if (number, printed_total) != (cell, None):
                    mangled += 1
                    checks.ok(
                        False,
                        f"{game} {cell!r} stored verbatim, never split",
                        f"got number={number!r} printed_total={printed_total!r} — a "
                        f"`printed_code` game's cell must reach `card.number` exactly as "
                        f"the export wrote it",
                    )
    checks.equal(
        mangled,
        0,
        f"{total_checked} distinct Number cells across {len(cases)} committed exports, "
        f"0 mangled",
    )
    checks.ok(
        double_sided_seen,
        "including at least one double-sided token cell (Riftbound's `T02 // T03`) — the "
        "shape the review named by name",
    )
    checks.note(f"{total_checked} cells checked, {mangled} mangled")


def check_catalog_set_rarity_match(checks: Checks) -> None:
    """`server/capture_server.py:_catalog_matches` sees `Set Name`/`Rarity`
    (docs/specs/card-printings.md section 3a).

    THE REAL CASE, OFF THE COMMITTED EXPORT, NOT A HAND-BUILT ONE. `Calm Rune` in
    `fixtures/riftbound_export_untouched.csv` is wider than the owner's own quoted example —
    the loose `wanted in name` rung already recovers `Calm Rune (R02a)`, `(R02b)` and
    `(Alternate Art)` beside the plain product, which this file's own docstring argues for —
    so a bare `Calm Rune` query answers with 16 Near Mint rows across FIVE sets today, and
    that width is exactly why a set word could not narrow anything before this item.

    BOTH LOOSE-NAME DIRECTIONS ARE ASSERTED TOO, because a term-splitting rewrite that
    fixed the reported defect and broke the recovery this function was built for would be a
    real regression wearing a fix's clothes. `Wuju Master`/`Master Yi, Wuju Master` and
    `Master Yi, Tempered`/`Master Yi` are the docstring's own two cases, reproduced here as a
    fixture because the docstring's own measurement (490 of 494 epithets, 38 of 98 champion
    names) is over an export this harness does not carry — the two rows below are what makes
    the CLAIM checkable rather than merely quoted.
    """
    checks.note("")
    checks.note("CATALOG SET/RARITY MATCH — server/capture_server.py:_catalog_matches (3a)")

    export = tcgcsv.read_export(RIFTBOUND_EXPORT)
    catalog = join.Catalog.from_export(export, "riftbound")

    def matched(query: str):
        return capture_server._catalog_matches(catalog, "riftbound", query)

    unfiltered = matched("Calm Rune")
    checks.equal(
        sorted({row["set"] for row in unfiltered}),
        ["Origins", "Riftbound Organized Play Promotional Cards", "Spiritforged",
         "Unleashed", "Vendetta"],
        "the baseline, unchanged: a query with no set/rarity word answers from every "
        "`Calm Rune`-named row the loose name match already recovered, across five sets",
    )

    narrowed = matched("Calm Rune Spiritforged")
    checks.ok(
        len(narrowed) > 0 and len(narrowed) < len(unfiltered),
        "a set WORD APPENDED to the name query genuinely narrows — fewer rows than the "
        "unfiltered name match, never zero",
        f"unfiltered={len(unfiltered)} narrowed={len(narrowed)}",
    )
    checks.equal(
        {row["set"] for row in narrowed},
        {"Spiritforged"},
        "and EVERY surviving row is that one set — the word filters rather than being "
        "folded into the name test, where it used to change nothing at all",
    )

    bare_set = matched("Spiritforged")
    checks.ok(
        len(bare_set) > 0,
        "a BARE set word returns that set's rows rather than an empty list — the reported "
        "defect was `Spiritforged` alone finding nothing at all",
    )
    checks.ok(
        all(row["set"] == "Spiritforged" for row in bare_set),
        "and every row it returns really is that set — the filter, not a coincidence",
    )
    checks.ok(
        {row["sku"] for row in narrowed} <= {row["sku"] for row in bare_set},
        "and it is a SUPERSET of the name-narrowed answer — the bare set word browses the "
        "whole set, which includes every `Calm Rune` row the first case found",
    )

    # ---- multi-word sets, matched as a PHRASE — the hole a single-term test could not see.
    # Five of this export's twelve sets are multi-word, and `Calm Rune`'s own `Riftbound
    # Organized Play Promotional Cards` printing is exactly the shape that made six of the
    # owner's own Runes carry an UNREACHABLE row past the nine-digit cut: 16 candidates, the
    # multi-word set past row 9, and no typed word — one word at a time — ever narrowed it.
    promo_set = "Riftbound Organized Play Promotional Cards"
    promo_full = matched(f"Calm Rune {promo_set}")
    checks.ok(
        len(promo_full) > 0,
        "the FULL 5-word set name, typed after the name, is consumed as one phrase and "
        "narrows to that set rather than being ignored word by word",
        f"query: 'Calm Rune {promo_set}' -> {len(promo_full)} rows",
    )
    checks.equal(
        {row["set"] for row in promo_full},
        {promo_set},
        "and every surviving row really is that 5-word set",
    )
    checks.ok(
        len(promo_full) <= 9,
        "and the count a person can actually reach is under the nine-digit cut — this is "
        "the printing 3c found unreachable before phrase matching existed",
        f"count: {len(promo_full)}",
    )

    partial_word = matched("Calm Rune Promotional")
    checks.equal(
        {row["set"] for row in partial_word},
        {row["set"] for row in unfiltered},
        "A SINGLE WORD OF A MULTI-WORD SET IS NOT A MATCH — `Promotional` alone is not the "
        "set's own name, so it stays a name term and the query is unchanged; a phrase "
        "matcher that let a partial word narrow would be guessing at what was meant",
    )

    # `Ivern, Green Father` carries a real Secret Garden printing (2 words) beside its
    # Riftbound Organized Play Promotional Cards and Unleashed ones.
    ivern_unfiltered = matched("Ivern")
    ivern_narrowed = matched("Ivern Secret Garden")
    checks.ok(
        0 < len(ivern_narrowed) < len(ivern_unfiltered),
        "a 2-word set phrase (`Secret Garden`) narrows a real multi-printing card too — not "
        "just the 5-word promo set",
        f"unfiltered={len(ivern_unfiltered)} narrowed={len(ivern_narrowed)}",
    )
    checks.equal(
        {row["set"] for row in ivern_narrowed},
        {"Secret Garden"},
        "and only the Secret Garden row(s) survive",
    )

    # `Origins` is a real 1-word set on its own AND the first word of the real 3-word
    # `Origins: Proving Grounds` — longest match first is what keeps typing the short set
    # name from being swallowed by the long one, and vice versa.
    origins_bare = matched("Origins")
    origins_colon = matched("Origins: Proving Grounds")
    checks.ok(
        len(origins_bare) > 0 and len(origins_colon) > 0,
        "both spellings answer",
        f"Origins={len(origins_bare)} 'Origins: Proving Grounds'={len(origins_colon)}",
    )
    checks.equal(
        {row["set"] for row in origins_bare}, {"Origins"},
        "the bare word resolves to the SHORT set, not the long one it is also a prefix of",
    )
    checks.equal(
        {row["set"] for row in origins_colon}, {"Origins: Proving Grounds"},
        "and the full colon phrase resolves to the LONG set — longest match first is what "
        "keeps the two from colliding into one answer",
    )
    checks.ok(
        set(row["sku"] for row in origins_bare).isdisjoint(
            row["sku"] for row in origins_colon
        ),
        "and the two answers share no row — they are genuinely two different sets, not one "
        "query accidentally subsuming the other",
    )

    # ---- both loose-name directions, reproduced as a fixture (docstring's own two cases)

    epithet_rows = (
        {
            tcgcsv.SKU_COLUMN: "9990001",
            tcgcsv.NAME_COLUMN: "Master Yi, Wuju Master",
            tcgcsv.NUMBER_COLUMN: "045",
            tcgcsv.SET_COLUMN: "Origins",
            tcgcsv.RARITY_COLUMN: "Rare",
            tcgcsv.CONDITION_COLUMN: "Near Mint",
            tcgcsv.PRODUCT_LINE_COLUMN: str(games.require("riftbound")["product_line"]),
            tcgcsv.MARKET_PRICE_COLUMN: "1.00",
        },
        {
            tcgcsv.SKU_COLUMN: "9990002",
            tcgcsv.NAME_COLUMN: "Master Yi",
            tcgcsv.NUMBER_COLUMN: "046",
            tcgcsv.SET_COLUMN: "Origins",
            tcgcsv.RARITY_COLUMN: "Rare",
            tcgcsv.CONDITION_COLUMN: "Near Mint",
            tcgcsv.PRODUCT_LINE_COLUMN: str(games.require("riftbound")["product_line"]),
            tcgcsv.MARKET_PRICE_COLUMN: "1.00",
        },
    )
    epithet_export = tcgcsv.Export(
        header=tuple(epithet_rows[0].keys()), rows=epithet_rows
    )
    epithet_catalog = join.Catalog.from_export(epithet_export, "riftbound")

    def epithet_matched(query: str):
        return capture_server._catalog_matches(epithet_catalog, "riftbound", query)

    checks.equal(
        [row["sku"] for row in epithet_matched("Wuju Master")],
        ["9990001"],
        "THE EPITHET CASE STILL WORKS: `Wuju Master` (the champion dropped) still finds "
        "`Master Yi, Wuju Master` — `wanted in name`, unaffected by the set/rarity split "
        "because neither word folds to a known set or rarity",
    )
    checks.equal(
        [row["sku"] for row in epithet_matched("Master Yi, Tempered")],
        ["9990002"],
        "AND THE MIRROR CASE STILL WORKS: `Master Yi, Tempered` (a hallucinated suffix) "
        "still finds the shorter catalogued `Master Yi` — `name in wanted`, for the same "
        "reason",
    )


class _ClaimCard:
    """Everything `join.claim_matches`/`join.rank_by_claims` read off a card, duck-typed —
    `_catalog_matches`'s own `card` parameter never requires `store.master.Card` itself,
    only these four attributes."""

    def __init__(self, rarity_claim=None, metadata_finish=None, set_hint=None, game="riftbound"):
        self.rarity_claim = rarity_claim
        self.metadata_finish = metadata_finish
        self.set_hint = set_hint
        self.game = game


def check_catalog_claim_rank_and_no_cutoff(checks: Checks) -> None:
    """D23's amendment, 2026-09-24: `do_review_catalog` no longer cuts the wire response at
    nine, and its ranking puts the card's own claim-agreeing rows first — `4/383` on the
    owner's real store, over the SAME committed fixture `check_catalog_set_rarity_match`
    already reads.

    `GET /review/4/383/catalog?q=Calm%20Rune` found all 16 `Calm Rune` rows and returned 9,
    silently, before this fix — the owner's own report, and this file's real numbers.
    """
    checks.note("")
    checks.note(
        "D23 AMENDMENT — server/capture_server.py:_catalog_matches, no cutoff, claim rank"
    )

    catalog = join.Catalog.from_export(
        tcgcsv.read_export(RIFTBOUND_EXPORT), "riftbound"
    )

    unranked = capture_server._catalog_matches(catalog, "riftbound", "Calm Rune")
    checks.equal(
        len(unranked), 16,
        "EVERY MATCH IS RETURNED, not the old nine-row cut — the owner's own real count "
        "for this real query",
    )

    claimed_card = _ClaimCard(rarity_claim=("Showcase",))
    ranked = capture_server._catalog_matches(catalog, "riftbound", "Calm Rune", claimed_card)
    checks.equal(
        len(ranked), 16, "the claim ranks; it does not narrow — the same 16 rows either way"
    )
    checks.equal(
        [row.get("rarity") for row in ranked[:4]],
        ["Showcase"] * 4,
        "THE CLAIM-AGREEING ROWS LEAD — all four `Showcase` printings of `Calm Rune` "
        "ranked ahead of every Common, Promo and unclaimed row, none of which agree",
    )
    checks.ok(
        "9139842" in [row["sku"] for row in ranked[:4]],
        "and Spiritforged's own Showcase row — the real SKU the owner's case names — is "
        "one of the four",
    )
    checks.equal(
        {row["sku"] for row in unranked}, {row["sku"] for row in ranked},
        "ranking reorders; it drops nothing and adds nothing",
    )

    # `do_review_catalog` itself, over a real card carrying the claim, end to end.
    with isolated_home() as home:
        run_dir = home / "runs" / "2026-09-11-box4-01"
        run_dir.mkdir(parents=True)
        shutil.copy(RIFTBOUND_EXPORT, run_dir / "export.csv")
        (run_dir / "manifest.json").write_text(
            json.dumps({
                "created_at": "2026-09-11T00:00:00+00:00", "joined": True,
                "exports": {"riftbound": {"path": str(run_dir / "export.csv")}},
            })
        )
        for _ in range(1):
            capture_server.do_capture(capture_payload(4, game="riftbound"))
        with Store().write() as snapshot:
            snapshot.inventory.set_state("4/1", master.IDENTIFIED)
            card = snapshot.inventory.cards["4/1"]
            card.game = "riftbound"
            card.run = "2026-09-11-box4-01"
            card.rarity_claim = ["Showcase"]
            snapshot.review.upsert(
                entry(
                    4, 1, candidates=[], reason="set_ambiguous",
                    read={"name": "Calm Rune", "number": "R02"},
                )
            )

        wired = answers(
            checks,
            lambda: capture_server.do_review_catalog(4, 1, "Calm Rune"),
            "the live route, over a card carrying the claim",
        )
        if wired is not None:
            checks.equal(
                (wired["found"], len(wired["rows"]), wired["truncated"]),
                (16, 16, False),
                "16 found, all 16 on the wire, and truncated is false — under "
                "CATALOG_EGREGIOUS_LIMIT",
            )
            checks.equal(
                [row.get("rarity") for row in wired["rows"][:4]],
                ["Showcase"] * 4,
                "and the card's own stored claim ranks the search exactly as the direct "
                "call above did",
            )


def check_identify_preflight_stage(checks: Checks) -> None:
    """`identify` hashes before it decodes, and `Item.stage` is what makes that safe.

    THE REORDER. The cache is keyed by the photograph's sha256, and `images.prepare`
    computed that digest before opening the image — so decoding every photograph in order
    to ask a question the digest already answers was pure waste on every cache hit.
    `cli/cmd_identify.py` hashes, consults the cache, refuses what has no prompt, and only
    then crops and downscales what is actually being sent.

    THE HAZARD IT SHIPS WITH, WHICH IS WHY THIS CHECK EXISTS. `prepared is None` used to
    mean "this photograph could not be read" AND "there are nothing to send for this card"
    at the same time, because the two were the same set. Five loops tested it and a sixth
    site wrote `prepared.sha256` into the run payload. Hash-first makes a CACHE HIT
    unprepared too, so a reorder that left that test alone would have reported every
    healthy cached card as unreadable, counted it as neither hit nor miss, and written
    `photo_sha256: null` onto its record — where `cli/resolve.realign` reads a missing
    digest as `blind` and D36's realign can no longer re-bind the card to a slot. That is
    `CLAUDE.md`'s "Never silently drop a card", four different ways.

    So the assertions below are one per consumer of the sentinel, over a directory holding
    one of each outcome at once: two readable Pokemon cards, one file that is not an image,
    and one card naming a game no registry entry answers.
    """
    from cli import __main__ as cli_entry
    from cli import cmd_identify
    from identify import images as identify_images

    checks.note("")
    checks.note("IDENTIFY PREFLIGHT — hash, then cache, then prepare (Item.stage)")

    def spoken(lines, prefix):
        """The first preflight line starting with `prefix`. The operator's own view: these
        are the figures they read while deciding whether to spend, so they are what is
        asserted rather than an internal count nobody sees."""
        for line in lines:
            if line.startswith(prefix):
                return line
        return ""

    with isolated_home() as home:
        caps = Path(home) / "stage-caps"
        caps.mkdir()
        # Two readable cards, in a registered game.
        for index in (1, 2):
            identify_images.Image.new("RGB", (64, 89), (30, 90 + index, 200)).save(
                caps / f"4-00{index}.jpg", "JPEG"
            )
            (caps / f"4-00{index}.json").write_text(
                json.dumps({"box": 4, "position": index, "game": "pokemon"}), "utf-8"
            )
        # A file with a .jpg name that no decoder will take. Its BYTES hash perfectly well,
        # which is the whole point: hashing proves the file can be read, never that it is an
        # image, so this card leaves the send list at the prepare pass and not before it.
        (caps / "4-003.jpg").write_bytes(b"this is not a JPEG, it is a sentence\n")
        (caps / "4-003.json").write_text(
            json.dumps({"box": 4, "position": 3, "game": "pokemon"}), "utf-8"
        )
        # A game no registry entry answers: refused by name, before it costs a decode.
        identify_images.Image.new("RGB", (64, 89), (200, 40, 40)).save(
            caps / "4-004.jpg", "JPEG"
        )
        (caps / "4-004.json").write_text(
            json.dumps({"box": 4, "position": 4, "game": "tarot"}), "utf-8"
        )

        sent: list = []
        # HOW MANY PHOTOGRAPHS WERE ACTUALLY DECODED. The reorder's whole subject, and the
        # only thing about it a test can see: hash-first and prepare-everything produce
        # IDENTICAL outcomes — same submissions, same records, same report — and differ
        # only in how much work was done to reach them. Every other assertion here stayed
        # green when the prepare pass's own gate was deleted, so without this counter the
        # guard watches the sentinel and not the change the sentinel exists to make safe.
        decoded: list = []
        real_prepare = cmd_identify.images.prepare

        def counting_prepare(path, **kwargs):
            decoded.append(str(path))
            return real_prepare(path, **kwargs)

        def fake_run_batch(requests, log=None, on_submit=None):
            outcomes = {}
            for request in requests:
                sent.append(request.custom_id)
                outcomes[request.custom_id] = batch.Outcome(
                    request.custom_id,
                    batch.SUCCEEDED,
                    identification=prompt.parse(
                        {
                            "name": "Pikachu",
                            "number": "025",
                            "printed_total": "102",
                            "finish": "normal",
                            "confidence": "high",
                        },
                        request.strategy,
                    ),
                )
            return batch.BatchRun(outcomes=outcomes)

        real_run_batch = cmd_identify.batch.run_batch
        cmd_identify.batch.run_batch = fake_run_batch
        cmd_identify.images.prepare = counting_prepare
        try:
            first: list = []
            with quiet():
                code = cmd_identify.run(
                    cli_entry.build_parser().parse_args(
                        ["identify", str(caps), "--crop", "--engine", "haiku"]
                    ),
                    first.append,
                )
            checks.equal(code, 0, "a first `identify --crop` over the four exits 0")
            checks.equal(
                sorted(sent),
                ["4-2f-1", "4-2f-2"],
                "and submits exactly the two readable, registered cards — the non-image "
                "and the unregistered game are named, not sent. The ids are `_custom_id`'s "
                "hex escape of `4/1` and `4/2`, which is the seam the Batch API's "
                "`^[a-zA-Z0-9_-]+$` forced and not anything this check arranged",
            )
            checks.equal(
                spoken(first, "cache hits"),
                "cache hits      0",
                "on a cold store nothing is a cache hit. THIS LINE IS COUNTED, NOT "
                "SUBTRACTED: it read `len(items) - to_send - unreadable`, and a card "
                "refused for want of a prompt is neither — so every unregistered card in "
                "a directory was reported as a CACHE HIT on the one line an operator "
                "reads to decide whether the run is worth paying for",
            )
            checks.equal(
                spoken(first, "to send"), "to send         2", "two cards are going"
            )
            checks.equal(
                spoken(first, "unreadable"),
                "unreadable      1 — these are NOT sent and NOT dropped:",
                "and exactly ONE photograph is unreadable — the file that is not an image",
            )
            checks.equal(
                len(decoded),
                3,
                "THE FIRST PRESS DECODES THREE OF THE FOUR. The two it is sending, plus "
                "the non-image — whose bytes hashed and then would not open, which is the "
                "one thing hashing cannot answer for. The card naming an unregistered "
                "game is refused BEFORE the prepare pass and costs a hash and nothing "
                "else, where it used to be cropped and downscaled and then refused",
            )
            checks.ok(
                spoken(first, "crop").startswith(
                    "crop            to the detected card — "
                )
                and "of the 2 being sent" in spoken(first, "crop"),
                "THE CROP COUNTERS' DENOMINATOR IS THE SEND LIST AND THE LINE SAYS SO. "
                "They ran over every photograph in the directory while every photograph "
                "was prepared; hash-first prepares only what is going, so they now sum to "
                "`to send`. The phrase is on the line and not in a comment because a "
                "denominator that changes silently is a published measurement rotting",
                f"crop line: {spoken(first, 'crop')!r}",
            )

            # ------------------------------------------------ the second press pays nothing
            sent_after_first = len(sent)
            second: list = []
            with quiet():
                code = cmd_identify.run(
                    cli_entry.build_parser().parse_args(
                        ["identify", str(caps), "--crop", "--engine", "haiku"]
                    ),
                    second.append,
                )
            checks.equal(code, 0, "a second press over the same directory exits 0")
            checks.equal(
                len(sent),
                sent_after_first,
                "and pays for NOTHING — both answers are already in the store",
            )
            checks.equal(
                spoken(second, "cache hits"),
                "cache hits      2",
                "THE CACHE CONSULT READS THE DIGEST, NOT THE PREPARED BYTES. It skipped "
                "on `prepared is None`, which under hash-first is true of every card the "
                "store already owns — so that test would have skipped exactly the set "
                "this loop exists to find, and both cards would have been re-submitted "
                "and re-paid for",
            )
            checks.equal(
                spoken(second, "unreadable"),
                "unreadable      1 — these are NOT sent and NOT dropped:",
                "AND THE UNREADABLE ROSTER STILL NAMES ONE. This is the reorder's whole "
                "hazard in a single figure: `unreadable = [i for i in items if i.prepared "
                "is None]` would name THREE here — the one real failure plus both healthy "
                "cache hits — and on the operator's own last press it would have named "
                "464 cards that were never anything but fine",
            )
            checks.equal(
                spoken(second, "to send"),
                "to send         0",
                "nothing is left to send",
            )
            checks.equal(
                len(decoded) - 3,
                1,
                "AND THE SECOND PRESS DECODES EXACTLY ONE PHOTOGRAPH — the non-image it "
                "must try before it can call it unreadable. THIS IS THE WHOLE CHANGE. "
                "Before the reorder this press decoded all four, because the cache was "
                "consulted after the decode rather than before it, and the digest the "
                "consult needs was computed by `images.prepare` on its way past. On the "
                "operator's own last press that was 678 decodes to answer 214 questions, "
                "at 114.96 ms against 0.687 ms to hash: one dry-run leg of it took 79 s "
                "and now takes 24 s. No other assertion in this check can see it — "
                "hash-first and prepare-everything agree on every outcome and differ only "
                "in the work done to reach them",
            )

            # --------------------------------------------- what the run payload records
            run_dirs = sorted(d for d in files.runs_dir().iterdir() if d.is_dir())
            payload = json.loads(
                (run_dirs[-1] / "identifications.json").read_text("utf-8")
            )["cards"]
            checks.equal(
                sorted(payload),
                ["4/1", "4/2", "4/3", "4/4"],
                "every photograph in the directory is on the record — an identification, "
                "a cache hit or a named failure, never an absence",
            )
            checks.ok(
                all(payload[key]["cached"] for key in ("4/1", "4/2")),
                "the two answered cards are recorded as cache hits",
            )
            checks.ok(
                all(payload[key]["photo_sha256"] for key in ("4/1", "4/2")),
                "AND THEY CARRY THEIR DIGEST. `photo_sha256` read `item.prepared.sha256 "
                "if item.prepared else None`, and a cache hit is never prepared — so a "
                "naive reorder writes null here, and `cli/resolve.py:1108` puts every "
                "record without a digest into `blind`, where D36's realign can no longer "
                "re-bind the card to the slot it is in today",
                f"recorded: {[payload[k]['photo_sha256'] for k in ('4/1', '4/2')]!r}",
            )
            checks.ok(
                payload["4/3"]["photo_sha256"],
                "and so does the card that HASHED AND THEN FAILED TO DECODE — its bytes "
                "were readable, only not an image, so `blind` is strictly smaller than it "
                "was before the reorder rather than larger",
            )
            checks.equal(
                payload["4/3"]["status"],
                "unreadable",
                "which is still recorded `unreadable`: nothing on the wire moved for this",
            )
            checks.equal(
                payload["4/4"]["status"],
                cmd_identify.UNKNOWN_GAME,
                "and the unregistered game is still refused by name, never sent, never "
                "dropped — refused BEFORE the decode now, so it costs one hash",
            )
        finally:
            cmd_identify.batch.run_batch = real_run_batch
            cmd_identify.images.prepare = real_prepare


def check_review_stand_down(checks: Checks) -> None:
    """POST /review/<box>/<index>/stand-down — D37, closing a question without answering it.

    ITS OWN ISOLATED HOME, this file's standing lesson: it clears queue entries, and the
    blocks around it count entries and history lines over stores they build by hand.

    THE CONTROL docs/DESIGN.md ASKED FOR BY NAME. That file has carried Skip as an OPEN
    QUESTION since the review screen was built — *"the screen needs a real defer that records
    a reason, and that is a decision entry rather than a button"* — and the owner pulled the
    trigger on 2026-08-25 asking for a stand-down on a wasted position.

    THE ASSERTION THAT CARRIES THE FEATURE IS THAT THE CARD IS UNTOUCHED. An answer writes a
    SKU and a condition; a retirement writes a terminal state; this writes NEITHER, and if it
    ever does it has silently become one of the other two.
    """
    checks.note("")
    checks.note("STAND DOWN — POST /review/<box>/<index>/stand-down")

    with isolated_home():
        for _ in range(4):
            capture_server.do_capture(capture_payload(3))
        with Store().write() as snapshot:
            for key in ("3/1", "3/2", "3/3", "3/4"):
                snapshot.inventory.set_state(key, master.IDENTIFIED)
            snapshot.review.upsert(entry(3, 1, market="12.00"))
            # No candidates — the case that CANNOT be answered at all, and the one the owner
            # was looking at: a black frame, a hallucinated read, no catalog row.
            snapshot.review.upsert(
                entry(3, 2, candidates=[], reason="no_catalog_row")
            )
            # In both files, so the both-queues clearing is exercised.
            snapshot.review.upsert(entry(3, 3, market="12.00"))
            snapshot.parked.upsert(entry(3, 3, market="0.05"))
            # 3/4 is identified and in no queue at all.
            _seed_sku_table(snapshot, CANDIDATES)

        refusal(
            checks,
            lambda: capture_server.do_review_stand_down(3, 1, {}),
            "reason_required",
            "a stand-down with no reason refuses — docs/DESIGN.md asked for a defer that "
            "RECORDS a reason, so a reasonless one is not the feature",
        )
        refusal(
            checks,
            lambda: capture_server.do_review_stand_down(3, 1, {"reason": "because"}),
            "stand_down_reason_invalid",
            "a reason outside the vocabulary refuses rather than being recorded verbatim",
        )
        refusal(
            checks,
            lambda: capture_server.do_review_stand_down(
                3, 1, {"reason": "pulled"}
            ),
            "stand_down_reason_invalid",
            "and a RETIRE reason is refused here — those four say the card left inventory, "
            "which is the one thing a stand-down must never be recorded as",
        )
        refusal(
            checks,
            lambda: capture_server.do_review_stand_down(
                3, 1, {"reason": "wasted_position", "undo": True}
            ),
            "field_not_settable",
            "a reversal carrying a reason refuses rather than obeying with the reason ignored",
        )
        not_in_queue_text = _refusal_text(
            lambda: capture_server.do_review_stand_down(3, 4, {"reason": "not_listing"})
        )
        checks.ok(
            not_in_queue_text is not None
            and not_in_queue_text[0] == "not_in_queue"
            and not_in_queue_text[1].startswith(
                "Box 1, Section 1, Card 4 is in no queue file"
            )
            and "3/4" not in not_in_queue_text[1]
            and "box 3" not in not_in_queue_text[1].lower(),
            "a card in no queue has no question to stand down from, and the refusal NAMES "
            "THE PLACE — Section n, Card m — never the store key `3/4` "
            "(D259)",
            f"got {not_in_queue_text!r}",
        )

        # --- the write itself, on the card that cannot be answered --------------------
        before = Store().read().inventory.cards["3/2"]
        was = (before.state, before.sku, before.condition)

        body = capture_server.do_review_stand_down(3, 2, {"reason": "wasted_position"})
        checks.equal(body["stood_down"], True, "the stand-down reports itself")
        checks.equal(body["undone"], False, "and which direction it went")
        checks.equal(body["reason"], "wasted_position", "and echoes the reason recorded")
        checks.equal(
            body["queue_reason"],
            "no_catalog_row",
            "and the QUEUE's own reason beside the operator's — two different strings that "
            "both matter, and the pair is what makes the log answerable to 'which questions "
            "get waved off, and why'",
        )

        snapshot = Store().read()
        checks.ok(
            snapshot.review.entries["3/2"].cleared_by_human,
            "the entry is cleared, so `Queue.upsert` will not re-ask on any later run",
        )
        after = snapshot.inventory.cards["3/2"]
        checks.equal(
            (after.state, after.sku, after.condition),
            was,
            "AND THE CARD IS UNTOUCHED — no sku, no condition, no state. This is the whole "
            "feature: if this ever fails, a stand-down has quietly become an answer or a "
            "retirement",
        )
        checks.ok(
            any(
                event.get("event") == "stood_down" and event.get("position") == "3/2"
                for event in Store().history()
            ),
            "and a `stood_down` line is on the log — the only place the reason survives",
        )
        checks.ok(
            "stood_down" not in master.STATES,
            "`stood_down` is an event and never a state, which T7 asserts for every event "
            "name here: a state would make months of these parse as card states",
        )

        already_cleared_text = _refusal_text(
            lambda: capture_server.do_review_stand_down(3, 2, {"reason": "not_listing"})
        )
        checks.ok(
            already_cleared_text is not None
            and already_cleared_text[0] == "already_cleared"
            and already_cleared_text[1].startswith(
                "Box 1, Section 1, Card 2 has already been"
            )
            and "3/2" not in already_cleared_text[1],
            "a second stand-down refuses rather than re-writing a settled question, and "
            "the refusal names the place, never `3/2` (D259)",
            f"got {already_cleared_text!r}",
        )

        # --- both queues, one press ---------------------------------------------------
        capture_server.do_review_stand_down(3, 3, {"reason": "cannot_settle"})
        both = Store().read()
        checks.ok(
            both.review.entries["3/3"].cleared_by_human
            and both.parked.entries["3/3"].cleared_by_human,
            "a position held in BOTH files is cleared in both — clearing one would leave the "
            "screen still showing a card whose question is closed",
        )

        # --- the reversal --------------------------------------------------------------
        back = capture_server.do_review_stand_down(3, 2, {"undo": True})
        checks.equal(back["undone"], True, "the reversal reports itself")
        checks.ok(
            not Store().read().review.entries["3/2"].cleared_by_human,
            "and the entry is waiting again",
        )
        second_reversal_text = _refusal_text(
            lambda: capture_server.do_review_stand_down(3, 2, {"undo": True})
        )
        checks.ok(
            second_reversal_text is not None
            and second_reversal_text[0] == "not_stood_down"
            and second_reversal_text[1].startswith(
                "Box 1, Section 1, Card 2 is already waiting in its queue"
            )
            and "3/2" not in second_reversal_text[1],
            "a second reversal refuses — the first reopened the entry, so nothing has to "
            "remember that a reversal happened — and the refusal names the place, never "
            "`3/2` (D259)",
            f"got {second_reversal_text!r}",
        )

        # --- THE GUARD THAT MATTERS MOST -----------------------------------------------
        # An ANSWERED card must not be reopened through this control. Observed failing
        # against a draft whose reversal only checked `cleared_by_human`.
        answered = {"sku": CANDIDATES[1]["sku"], "condition": CANDIDATES[1]["condition"]}
        capture_server.do_review_answer(3, 1, answered)
        answer_guard_text = _refusal_text(
            lambda: capture_server.do_review_stand_down(3, 1, {"undo": True})
        )
        checks.ok(
            answer_guard_text is not None
            and answer_guard_text[0] == "not_stood_down"
            and answer_guard_text[1].startswith(
                "Box 1, Section 1, Card 1 was closed by an ANSWER"
            )
            and "3/1 is" not in answer_guard_text[1],
            "a card closed by an ANSWER refuses this reversal — taking back a real "
            "identification through the un-dismiss control is the one thing it must not "
            "do — and the refusal names the place, never the store key "
            "(D259)",
            f"got {answer_guard_text!r}",
        )
        still = Store().read().inventory.cards["3/1"]
        checks.equal(
            still.sku,
            answered["sku"],
            "and the answer is still on the card after that refusal",
        )


def check_run_realignment(checks: Checks) -> None:
    """D36 — a run's slot numbers are re-bound to the photographs they were taken from.

    ITS OWN ISOLATED HOME, which is this file's own lesson for the fourth time: this block
    writes photographs into a box, and the blocks above count records and history lines over
    boxes they build card by card.

    THE DEFECT: a run directory is immutable (`cli/runs.py`) and the store is not. D10 ruling 1
    lets a junk capture be deleted from the middle of a box, sliding every higher card down one
    slot; the store remaps records, photographs, sidecars and both queue files and writes a
    `renumbered` event. The run cannot be remapped — it is a record of a past event — so
    re-joining a box edited since it was identified paired every card with its NEIGHBOUR's
    slot, photograph and label. Measured on box 2, 2026-08-24: card `2/7` deleted, 537 cards
    shifted, and a re-join wrote all 47 queue entries one position off.

    Every case below was observed FAILING against the unguarded loader before it was kept.
    """
    def build(bodies, names):
        return {
            "cards": {
                f"2/{i}": {
                    "box": 2,
                    "index": i,
                    "photo": f"captures/cards/box2/{i:04d}.jpg",
                    "photo_sha256": hashlib.sha256(body).hexdigest(),
                    "identification": {"name": names[i], "confidence": "high"},
                }
                for i, body in bodies.items()
            }
        }

    with isolated_home() as home:
        box = home / "captures" / "cards" / "box2"
        box.mkdir(parents=True)
        bodies = {i: f"photo-of-card-{i}".encode() for i in (1, 2, 3, 4)}
        names = {1: "Alpha", 2: "Beta", 3: "Gamma", 4: "Delta"}
        for i, body in bodies.items():
            (box / f"{i:04d}.jpg").write_bytes(body)
        original = build(bodies, names)

        # 1. Nothing has moved: the payload comes back as the SAME OBJECT, which is what keeps
        #    a healthy run's join byte-for-byte identical.
        same, moved, departed, unverified = resolve.realign(original)
        checks.ok(same is original, "D36: an unmoved run's payload is returned untouched")
        checks.equal(moved, {}, "D36: and nothing is reported as moved")
        checks.equal(departed, [], "D36: and nothing as departed")
        checks.equal(unverified, [], "D36: and the box counts as verified")

        # 2. Card 2 is deleted mid-box and 3, 4 slide down — exactly D10 ruling 1.
        (box / "0002.jpg").write_bytes(bodies[3])
        (box / "0003.jpg").write_bytes(bodies[4])
        (box / "0004.jpg").unlink()
        rebound, moved, departed, unverified = resolve.realign(original)
        checks.equal(
            moved,
            {"2/3": "2/2", "2/4": "2/3"},
            "D36: cards behind a mid-box delete re-bind to the slot their photograph is in now",
        )
        checks.equal(
            departed, ["2/2"], "D36: and the deleted card is reported departed, not joined"
        )
        checks.equal(
            sorted(rebound["cards"]),
            ["2/1", "2/2", "2/3"],
            "D36: the rebound payload holds the surviving cards at their new slots",
        )
        checks.equal(
            rebound["cards"]["2/2"]["identification"]["name"],
            "Gamma",
            "D36: and the READ travels with its photograph — the whole point, since the old "
            "loader left Gamma's name on Beta's slot and Beta's photograph",
        )
        checks.equal(
            rebound["cards"]["2/2"]["index"],
            2,
            "D36: `index` is rewritten too, not only the key — the position label is built from it",
        )
        # OBSERVED FAILING FIRST, and found on the screen rather than here: the entry read
        # `Mewtwo ex` and rendered `0096.jpg`, a photograph of a different card. `queue_entry`
        # carries this path onto the queue entry verbatim and the review screen renders exactly
        # it, so a rebound record keeping its old path shows the slot's PREVIOUS occupant —
        # this function's own defect, surviving one field deeper.
        checks.equal(
            rebound["cards"]["2/2"]["photo"],
            "captures/cards/box2/0002.jpg",
            "D36: and so is `photo` — the review screen renders that path verbatim",
        )
        checks.equal(
            original["cards"]["2/3"]["index"], 3, "D36: and the run's own payload is not mutated"
        )

        # 3. One photograph at two slots is a question, not an answer.
        (box / "0004.jpg").write_bytes(bodies[3])
        try:
            resolve.realign(original)
            checks.ok(False, "D36: a duplicated photograph must refuse")
        except runs.RunError as refusal:
            checks.ok(
                "more than one slot" in str(refusal),
                "D36: a photograph at two slots refuses rather than picking one",
            )
        (box / "0004.jpg").unlink()

        # 4. A BOX WITH NO PHOTOGRAPHS IS UNVERIFIED, NOT EMPTIED. The first draft of this
        #    declared all 53 of box 1's cards departed, because box 1's photographs had been
        #    deleted while its records lived on — which inverts what the check means. Absence
        #    of photographs is absence of evidence, not evidence of absent cards.
        for photo in box.glob("*.jpg"):
            photo.unlink()
        blind, moved, departed, unverified = resolve.realign(original)
        checks.ok(
            blind is original, "D36: a box with no photographs on disk passes through untouched"
        )
        checks.equal(departed, [], "D36: and NONE of its cards are called departed")
        checks.equal(unverified, [2], "D36: the box is reported unverified instead")

        # 5. TWO RECORDS ON ONE SLOT REFUSE, and this is the disk check's missing twin.
        #    Case 3 above catches one PHOTOGRAPH at two slots. Nothing caught two RECORDS
        #    carrying one digest: both resolve through `at` to the same position and then
        #    collide in the rebuilt payload, where the second write wins.
        #
        #    OBSERVED FAILING FIRST, on exactly this fixture: two cards in, ONE card out,
        #    `departed` empty and nothing printed. A silent drop, inside the function written
        #    to prevent one, which `CLAUDE.md` forbids outright.
        #    A FRESH BOX inside the same home: box 2's photographs were deleted by case 4
        #    above, and re-creating them would re-open assertions already made over them.
        nine = home / "captures" / "cards" / "box9"
        nine.mkdir(parents=True)
        (nine / "0002.jpg").write_bytes(b"one-photo")
        digest = hashlib.sha256(b"one-photo").hexdigest()
        twins = {
            "cards": {
                "9/1": {"box": 9, "index": 1, "photo_sha256": digest, "photo": "a.jpg"},
                "9/3": {"box": 9, "index": 3, "photo_sha256": digest, "photo": "b.jpg"},
            }
        }
        try:
            resolve.realign(twins)
            checks.ok(False, "D36: two records landing on one slot must refuse")
        except runs.RunError as refusal:
            checks.ok(
                "more than one record" in str(refusal),
                "D36: two records claiming one slot refuse rather than one being dropped",
            )
            checks.ok("9/2" in str(refusal), "D36: and the contested slot is named")

        # 6. A POSITIONLESS KEY SURVIVES A REALIGN INSTEAD OF CRASHING IT.
        #    `identify/sidecar.py` keys a capture with no position as `file:<name>` — the
        #    documented shape for a directory of photographs with no sidecars. It is never
        #    in `by_box`, so it can never move, but the rebuild walks EVERY card: one
        #    stray key used to raise an unhandled ValueError the moment anything else in
        #    its box shifted, taking `join` and `emit` down for that run permanently.
        #    OBSERVED FAILING FIRST: `ValueError: not enough values to unpack`.
        stray = {
            "cards": {
                "file:stray.jpg": {"name": "Stray", "photo": "stray.jpg"},
                "9/1": {"box": 9, "index": 1, "photo_sha256": digest, "photo": "a.jpg"},
            }
        }
        out, moved, departed, unverified = resolve.realign(stray)
        checks.ok(
            "file:stray.jpg" in out["cards"],
            "D36: a positionless key passes through a realign untouched",
        )
        checks.equal(
            moved, {"9/1": "9/2"}, "D36: and the card that really moved is still re-bound"
        )


def check_reused_box_refusal(checks: Checks) -> None:
    """D36 (amended) — a run over a box whose number was deleted and reused is refused outright.

    THE CASE `check_run_realignment` CANNOT REACH, because `realign` never opens the store.
    Box 1 was deleted 2026-08-25 with 53 Pokemon cards and its number reused 2026-08-29 for
    133 Riftbound cards (`next_box_number`, D20 amended); `2026-08-22-box1-03` still describes
    the old drawer, none of its digests are among the new box's photographs, so `realign`
    answers `unverified` and passes the keys through — after which the loader reads the
    CURRENT box's records at those keys. Observed on the owner's store: the refusal that fired
    said *"this run holds 53 riftbound card(s) and no export covers that game"* over a Pokemon
    run, because the run predates D21's `game` field and the store rung read the Riftbound
    cards now sitting at its keys, and it sent the operator to change the game on live records
    that were never this run's.

    THE RULE IS `_box_name_for`'s (D56), hoisted to `store/master.py:box_disowns_run` and read
    off the store by `Inventory.box_disowns_run`: the registry entry was made AFTER the run
    started AND the box's cards came from somewhere else. `check_pipeline_routes` asserts the
    route half over the same rule; this asserts the refusal on both paths and through the
    command, the two honest pass-throughs, and the rule's branches directly.
    """
    checks.note("")
    checks.note("REUSED BOX NUMBER — a run over a reallocated box is refused (D36 amended)")

    from cli import __main__ as entry

    def payload_for(with_game: bool) -> dict:
        # Records at keys the NEW box also uses, photographed to bytes on no disk: `realign`
        # finds no `captures/cards/box1` and answers `unverified`, which is exactly the
        # pass-through the refusal has to fire in front of. `with_game=False` is the shape
        # of the real run — it predates D21, so the store rung decides its game.
        cards = {}
        for i, (name, number) in {1: ("Dunsparce", "120"), 2: ("Alpha", "001")}.items():
            record = {
                "box": 1,
                "index": i,
                "photo": f"captures/cards/box1/{i:04d}.jpg",
                "photo_sha256": hashlib.sha256(f"old-box-1-card-{i}".encode()).hexdigest(),
                "identification": {
                    "name": name,
                    "number": number,
                    "printed_total": "159",
                    "confidence": "high",
                    "finish": None,
                },
            }
            if with_game:
                record["game"] = "pokemon"
            cards[f"1/{i}"] = record
        return {"prompt_fingerprint": "t7-reused", "cards": cards}

    def says(caught, label: str, *needles: str) -> None:
        text = str(caught) if caught is not None else ""
        missing = [needle for needle in needles if needle not in text]
        checks.ok(not missing, label, f"missing {missing!r} in:\n{text}")

    other = "2026-08-29-box1-01"
    with isolated_home() as home:
        run = runs.create("box1")
        run.set(
            capture_dir=str(home / "captures" / "cards" / "box1"),
            created_at="2000-01-01T00:00:00+00:00",
        )
        run.write_identifications(payload_for(with_game=False))
        export = write_export(run.path("export.csv"))

        # An EMPTY box disowns nobody, even one registered after the run: the name-it-later
        # flow `check_pipeline_routes` asserts is the same flow for the join.
        with Store().write() as snapshot:
            snapshot.inventory.ensure_box(1)
        plan = resolve.exports_for(run, [str(export)])
        checks.equal(
            list(plan.by_game),
            ["pokemon"],
            "a box registered after the run but holding no cards is still this run's — an "
            "empty box is not evidence that the drawer changed",
        )

        # The number is reused: three Riftbound cards from another run, at the keys this
        # run's records also use. `ensure_box` stamped the entry above, well after 2000.
        with Store().write() as snapshot:
            for n in (1, 2, 3):
                card, _ = snapshot.inventory.allocate_capture(
                    1, capture_id=f"reused-{n}", game="riftbound", cid=fake_cid(f"reused-{n}")
                )
                snapshot.inventory.record_identification(
                    card.key,
                    name="Moonfall",
                    number="198/219",
                    printed_total="219",
                    confidence="high",
                    run=other,
                )
        born = Store().read().inventory.box(1).created_at
        checks.ok(
            isinstance(born, str) and born > "2000",
            "fixture: the registry entry is stamped after the run started",
            f"created_at: {born!r}",
        )

        # (a) THE REFUSAL, ON BOTH PATHS AND THROUGH THE COMMAND. The `exports_for` path is
        # the one that used to fire the misleading refusal: with no `game` on the records,
        # `_games_needed`'s store rung read `riftbound` off the foreign cards and refused for
        # want of a Riftbound export. It never gets there now.
        caught = checks.raises(
            runs.RunError,
            lambda: resolve.exports_for(run, [str(export)]),
            "a run over a box whose number was deleted and reused since is refused on the "
            "`exports_for` path, before the store rung reads a foreign card's game",
        )
        says(
            caught,
            "and the refusal names the box, the reuse, the registry stamp, the run whose "
            "cards are there now, and that nothing was touched",
            "box 1", "reused", str(born), other, "Nothing was joined",
        )
        checks.ok(
            caught is not None and "riftbound" not in str(caught),
            "and it is NOT the 'no export covers riftbound' refusal — that one blamed the "
            "operator's export for the store's reallocation",
            str(caught),
        )
        caught = checks.raises(
            runs.RunError,
            lambda: resolve.load(run, {"pokemon": export}),
            "and on `load` with a mapping handed straight in, which skips `exports_for`",
        )
        says(caught, "with the same sentence", "box 1", "reused", str(born), other)

        with quiet() as said:
            code = entry.main(["join", str(run.directory), "--export", str(export)])
        checks.equal(code, 1, "`banchi join` over that run exits 1")
        says(said.getvalue(), "and prints the refusal", "REFUSING", "reused", other)
        tables = store_tables()
        checks.equal(
            (tables["queues"], tables["listings"]),
            ([], []),
            "and both queues are empty and no listing was written — refused before anything "
            "was read at this run's keys, let alone written",
        )

        # (b) THE TWO HONEST PASS-THROUGHS. The records carry `game` now, so the store rung
        # is not consulted and the join can be shown to proceed.
        run.write_identifications(payload_for(with_game=True))
        with Store().write() as snapshot:
            snapshot.inventory.box(1).created_at = "1999-01-01T00:00:00+00:00"
        resolved = resolve.load(run, {"pokemon": export})
        checks.equal(
            resolved.unverified_boxes,
            [1],
            "a box registered BEFORE the run passes through as `unverified` — photographs "
            "missing, box unchanged: still the honest pass-through, and `unverified` still "
            "means what it meant",
        )
        with Store().write() as snapshot:
            snapshot.inventory.box(1).created_at = born
            snapshot.inventory.cards.get("1/1").run = run.name
        resolved = resolve.load(run, {"pokemon": export})
        checks.equal(
            resolved.unverified_boxes,
            [1],
            "and a box holding this run's cards is this run's drawer, however young the "
            "registry entry — the card set is what carries it",
        )

    # (c) THE RULE ITSELF, branch by branch, with the stamps the real case carries.
    ran = "2026-08-22T22:40:24+00:00"
    made = "2026-08-29T21:32:35.944+00:00"
    for label, args, expected in (
        ("an empty box disowns nobody", (made, [], "r", ran), False),
        ("a box holding this run's cards is its own", (made, [other, "r"], "r", ran), False),
        ("an unparseable registry stamp abstains", ("last week", [other], "r", ran), False),
        ("an absent run stamp abstains", (made, [other], "r", None), False),
        ("born before the run, holding others' cards: still its own", (ran, [other], "r", made), False),
        ("born after the run AND holding only others' cards: disowned", (made, [other], "r", ran), True),
    ):
        checks.equal(master.box_disowns_run(*args), expected, f"box_disowns_run: {label}")


def check_box_true_index(checks: Checks) -> None:
    """A box has a TRUE INDEX that is never reused, and a run over a deleted drawer says so.

    THE OWNER'S REPORT, 2026-09-11, VERBATIM: *"im seeing that i deleted an old box 1, started
    writing into a new box (now new box 1) and if i go on say my runs tab it shows that i'd run
    a 'Box 1' run a long time ago etc. it's confusing."* Their ruling in the same breath: *"box
    #s as indexes should be immutable so if i delete a box # that deleted box's index # is not
    deleted, like box # and index # should not be the same thing, a box needs an index # not
    visible anywhere in the app thats a true index rather than cheaply using boxes as an
    index."*

    THE FIXTURE IS THEIR OWN STORE'S SHAPE, which D36 records: box 1 held 53 Pokemon cards on
    2026-08-22 and box 1 has held 133 Riftbound cards since 2026-08-29. It is built here rather
    than described, because every claim below is about what happens when one number names two
    drawers and no smaller fixture has two drawers in it.

    IT IS NOT `check_reused_box_refusal` AGAIN. That block asserts the older rule — the stamp
    and the card set — which reasons from the SHAPE of the evidence and must abstain when it
    cannot tell. This asserts the identity that makes the same question a lookup, and the two
    coexist on purpose: every run on the owner's machine predates the id, so the older rule is
    what answers their actual complaint and both arms are exercised here against one store.

    WHAT IT DELIBERATELY DOES NOT ASSERT: that the NUMBER stops being reused. D20 hands out the
    lowest free integer and that stays correct — a physical drawer relabelled 1 really is box 1
    — so the reuse is asserted as a REQUIREMENT below rather than guarded against.
    """
    checks.note("")
    checks.note("BOX TRUE INDEX — the drawer's identity outlives its number (D145)")

    OLD_RUN, NEW_RUN = "2026-08-22-box1-03", "2026-08-29-box1-01"

    def manifest(name: str, created: str, bid) -> None:
        directory = files.runs_dir() / name
        directory.mkdir(parents=True, exist_ok=True)
        scope = {"box": 1, "whole_box": True, "cards": None}
        if bid is not None:
            scope["bid"] = bid
        files.write_json(
            directory / "manifest.json",
            {
                "created_at": created,
                "capture_dir": str(files.home() / "captures/cards/box1"),
                "scope": scope,
                "collected": True,
                "joined": True,
            },
        )

    with isolated_home():
        # --- the drawer that is about to depart ------------------------------------------
        with Store().write() as snapshot:
            inventory = snapshot.inventory
            old = inventory.ensure_box(1, name="Pokemon shakedown")
            old.created_at = "2026-08-22T09:00:00+00:00"
            for n in range(53):
                card, _ = inventory.allocate_capture(1, cid=fake_cid(f"shakedown-{n}"))
                card.game, card.run = "pokemon", OLD_RUN
            old_bid = old.bid
        checks.equal(old_bid, 1, "the first drawer in an empty store is index 1")
        manifest(OLD_RUN, "2026-08-22T10:12:00+00:00", old_bid)

        # --- the deletion, exactly as `do_delete_box` performs it -------------------------
        with Store().write() as snapshot:
            inventory = snapshot.inventory
            for key in [k for k, c in inventory.cards.items() if int(c.box) == 1]:
                del inventory.cards[key]
            entry = inventory.boxes.pop("1")
            inventory._log(
                "box_deleted", None, box=1, bid=entry.bid, name=entry.name, cards=53, buried=0,
            )

        # --- the replacement, allocated the lowest free NUMBER (D20) ----------------------
        with Store().write() as snapshot:
            inventory = snapshot.inventory
            number = inventory.next_box_number()
            checks.equal(
                number,
                1,
                "THE NUMBER IS STILL REUSED, AND THAT IS THE REQUIREMENT RATHER THAN THE BUG "
                "(D20): a physical drawer relabelled 1 really is box 1, and the owner did not "
                "ask for monotonic numbers. Making this 2 would be 'fixing' the complaint by "
                "changing what the operator reads off the shelf",
            )
            new = inventory.ensure_box(number, name="RB Epics")
            new.created_at = "2026-08-29T14:00:00+00:00"
            for n in range(133):
                card, _ = inventory.allocate_capture(number, cid=fake_cid(f"epics-{n}"))
                card.game, card.run = "riftbound", NEW_RUN
            new_bid = new.bid
        manifest(NEW_RUN, "2026-08-29T15:00:00+00:00", new_bid)

        checks.equal(
            new_bid,
            2,
            "AND THE INDEX IS NOT. The deleted drawer's 1 is spent forever — `next_box_id` is "
            "a high-water mark over a counter a deletion cannot lower, which is D10's rule for "
            "the card index inside a box and the one thing `next_box_number` above is "
            "deliberately not",
        )

        snapshot = Store().read()
        checks.equal(
            snapshot.inventory.box_by_id(old_bid),
            None,
            "the departed drawer's index resolves to nothing — an id answers about ONE drawer "
            "for the life of the store, so None is 'that drawer is gone' and never 'look again "
            "under another key'",
        )
        checks.equal(
            snapshot.inventory.box_by_id(new_bid).name,
            "RB Epics",
            "and the live one resolves to the drawer that was given it",
        )
        checks.equal(
            snapshot.inventory.box(1).bid,
            new_bid,
            "while the NUMBER 1 resolves to whichever drawer is wearing it today — the two "
            "questions are different and now have different keys (D58, one register up)",
        )

        # --- what the runs tab draws ------------------------------------------------------
        names = pipeline_routes._box_names()
        old_row = pipeline_routes._summary(files.runs_dir() / OLD_RUN, names)
        new_row = pipeline_routes._summary(files.runs_dir() / NEW_RUN, names)

        checks.equal(
            [old_row["box"], old_row["box_bid"], old_row["box_former"], old_row["box_name"]],
            [1, old_bid, True, "Pokemon shakedown"],
            "THE COMPLAINT, ANSWERED: the old run still names box 1 — its directory, its "
            "photographs and every refusal about it do — and the wire now says that drawer is "
            "not the box 1 on the shelf, and what it was called. `runBoxLabel` draws `Box 1 "
            "(deleted) · Pokemon shakedown`",
        )
        checks.equal(
            old_row["box_name"],
            "Pokemon shakedown",
            "and the departed drawer's name comes off its own `box_deleted` history line, not "
            "off the registry — there is no registry entry left. D56 forbids STORING a name on "
            "a run because a live name is editable; a deleted drawer's last name cannot be "
            "edited, so it is a fact rather than a stale copy",
        )
        checks.equal(
            [new_row["box"], new_row["box_bid"], new_row["box_former"], new_row["box_name"]],
            [1, new_bid, False, "RB Epics"],
            "AND THE CURRENT RUN IS UNTOUCHED — same number, same screen, no marker, and its "
            "name still joined live off the registry (D56). A fix that marked both would have "
            "traded one confusing row for two",
        )

        # --- the arm the owner's own machine actually takes --------------------------------
        manifest(OLD_RUN, "2026-08-22T10:12:00+00:00", None)
        legacy = pipeline_routes._summary(files.runs_dir() / OLD_RUN, names)
        checks.equal(
            [legacy["box_bid"], legacy["box_former"], legacy["box_name"]],
            [None, True, None],
            "A RUN WRITTEN BEFORE THE ID EXISTS IS STILL CAUGHT, by the older rule "
            "(`box_disowns_run`, D36/D56) — which is EVERY RUN ON THE OWNER'S MACHINE, "
            "including the one that produced the report. It can say THAT the drawer departed "
            "and not WHICH, so there is no name to recover and `Box 1 (deleted)` is the whole "
            "of what it draws",
        )

        # --- the join refuses on the id, where there is one --------------------------------
        inventory = Store().read().inventory
        checks.ok(
            inventory.box_disowns_run(1, OLD_RUN, "2026-08-22T10:12:00+00:00", bid=old_bid)
            is not None,
            "`Inventory.box_disowns_run` refuses on the ID OUTRIGHT where run and box both "
            "carry one — a decision, not the inference the older rule has to make, so "
            "`cli/resolve.py:refuse_reallocated` refuses this join (D36 amended)",
        )
        checks.ok(
            inventory.box_disowns_run(1, NEW_RUN, "2026-08-29T15:00:00+00:00", bid=new_bid)
            is None,
            "and it passes the drawer's OWN run through on the same comparison — the id arm "
            "has exactly two answers and neither is an abstention",
        )
        checks.ok(
            inventory.box_disowns_run(1, OLD_RUN, "2026-08-22T10:12:00+00:00") is not None,
            "with no id passed, the older rule decides, unchanged: the registry entry is "
            "younger than the run and the box's 133 cards are all another run's",
        )


def check_emit_buried_box(checks: Checks) -> None:
    """An emit over a buried box refuses and creates no card (2026-09-27 incident).

    THE CASE: a run over box 3 was joined, then box 3 was deleted (its cards buried, its
    registry row gone). `Inventory.box_disowns_run` used to answer None for a box with no row,
    so the emit upserted a ghost card per position and sent phantom copies. Asserted: the
    deletion record refuses the run on both branches (bid, time), the single and the merged
    path refuse, a position the store holds no card at is refused, the Send screen's mapping
    shows the owner one plain sentence, and a card that MOVED to another live box still sends.
    (D36, D145.)
    """
    checks.note("")
    checks.note("EMIT OVER A BURIED BOX — refused, and no ghost card is born")

    cards = [(3, 1, "Dunsparce", "120", "normal"), (3, 2, "Dunsparce", "120", "normal")]

    def bury(inventory, *, log: bool) -> None:
        for key in [k for k, c in inventory.cards.items() if int(c.box) == 3]:
            del inventory.cards[key]
        entry = inventory.boxes.pop("3")
        if log:
            inventory._log("box_deleted", None, box=3, bid=entry.bid, name=entry.name,
                           cards=2, buried=2)

    def owner_sentence(said: str) -> str:
        refused = send_routes._empty_send_refusal(said, [], "sent", 1)
        return str(refused.args[-1]) if refused.args else str(refused)

    # --- both branches of `box_disowns_run`, on the rule itself ---------------------------
    with isolated_home():
        inventory = Store().read().inventory
        gone = [{"event": "box_deleted", "box": 3, "bid": 7, "at": "2026-09-16T02:00:00+00:00"}]
        checks.ok(
            inventory.box_disowns_run(3, "r", "2026-09-01T00:00:00+00:00", bid=7, deleted=gone)
            is not None,
            "bid branch: the run's drawer index equals the deleted drawer's — refused",
        )
        checks.ok(
            inventory.box_disowns_run(3, "r", "2026-09-01T00:00:00+00:00", bid=8, deleted=gone)
            is None,
            "bid branch: a different drawer's index is not the deleted one — passes",
        )
        checks.ok(
            inventory.box_disowns_run(3, "r", "2026-09-01T00:00:00+00:00", deleted=gone)
            is not None,
            "time branch: no index anywhere, deleted after the run started — refused",
        )
        checks.ok(
            inventory.box_disowns_run(3, "r", "2026-09-20T00:00:00+00:00", deleted=gone)
            is None,
            "time branch: deleted BEFORE the run started — not this run's drawer, passes",
        )
        checks.ok(
            inventory.box_disowns_run(3, "r", "2026-09-01T00:00:00+00:00") is None,
            "and with no deletion record and no row the rule still abstains, as before",
        )

    # --- the single path, through the Send screen's mapping -------------------------------
    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        with Store().write() as snapshot:
            bury(snapshot.inventory, log=True)
        said = command(checks, "emit", str(run_dir.directory), exits=1)
        sentence = owner_sentence(said)
        checks.ok(
            run_dir.name in sentence and "box 3" in sentence and "nothing was sent" in sentence
            and "REFUSING" not in sentence,
            "a run over a deleted box refuses, and the Send screen shows ONE plain sentence "
            "naming the run and the box",
            sentence,
        )
        checks.equal(len(Store().read().inventory.cards), 0, "and no card was created")

    # --- the merged path (what Send runs): one good run, one over the buried box ----------
    with isolated_home():
        good, _ = seam_run(checks, [(4, 1, "Articuno", "161", None)])
        bad, _ = seam_run(checks, cards)
        with Store().write() as snapshot:
            bury(snapshot.inventory, log=True)
        before = len(Store().read().inventory.cards)
        said = command(checks, "emit", str(good.directory), str(bad.directory), exits=1)
        checks.ok(
            bad.name in owner_sentence(said) and "box 3" in owner_sentence(said),
            "the merged emit refuses the whole send on the buried run, same sentence",
            said,
        )
        checks.equal(
            len(Store().read().inventory.cards), before,
            "and the merged refusal created no card and stamped nothing",
        )

    # --- a position with no card, in a live box -------------------------------------------
    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        with Store().write() as snapshot:
            bury(snapshot.inventory, log=False)
            snapshot.inventory.ensure_box(3)
        said = command(checks, "emit", str(run_dir.directory), exits=1)
        sentence = owner_sentence(said)
        checks.ok(
            "Box 3, card 1" in sentence and "3/1" not in sentence and "nothing was sent" in sentence,
            "a position with no card refuses, named as a place ('Box 3, card 1'), never a key",
            sentence,
        )
        checks.equal(len(Store().read().inventory.cards), 0, "and no card was created")

    # --- the moved card still sends -------------------------------------------------------
    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        with Store().write() as snapshot:
            snapshot.inventory.ensure_box(4)
            snapshot.inventory.move_card("3/1", 4)
        said = command(checks, "emit", str(run_dir.directory))
        checks.ok(
            "pushed" in said and "REFUSING" not in said,
            "a run over box 3 whose card moved to box 4 still sends: nothing here may refuse "
            "a card that is where the store says it is",
            said,
        )


def check_rescue_stranded_run(checks: Checks) -> None:
    """The one-time repair for a run D36 refuses, and the binding that ends the class.

    THE CASE, MEASURED ON THE OWNER'S STORE 2026-09-12 AND REPRODUCED HERE IN MINIATURE.
    `2026-08-29-box1-01` read 133 cards out of box 1. On 2026-09-11 the operator MOVED 99 of
    them into box 3 (D83) — `1/1 -> 3/724` through `3/822` — then deleted box 1, which buried
    the 133 source records (D134), and box 1's number was reused the same evening. So the run
    describes a drawer that no longer exists, `refuse_reallocated` refuses its join forever,
    and 99 identified cards carrying a SKU each were reachable from no press in the product.
    `check_reused_box_refusal` above asserts the refusal; this asserts the way out of it.

    IT IS `realign`'s MECHANISM WITH ONE RESTRICTION LIFTED, AND THAT RESTRICTION IS RIGHT
    WHERE IT IS. `cli/resolve.py:realign` looks for a record's photograph only in the boxes
    THE RUN NAMES, because a join must never follow a card into a drawer nobody asked it
    about. `rescue` searches every live drawer — safe only because it is an explicit operator
    act, previews first, and produces a NEW run rather than changing what a join does. The
    digest rules are `realign`'s unchanged: a digest on two records or on two photographs is a
    question, not a slot, and refuses the whole run.

    AND IT BINDS THE NEW RUN TO THE DRAWER'S `bid` (D145), which is what stops the class
    recurring: box 3 may be deleted and its number reused tomorrow, and the rescue run will
    still say which drawer it was over.
    """
    checks.note("")
    checks.note("RESCUE — a stranded run's cards, re-addressed to where they are now")

    from cli import __main__ as entry
    from cli import cmd_rescue

    def hush(*_args) -> None:
        """A `say` that says nothing: these cases assert the RETURN, not the report."""

    def photo(home, box: int, index: int, body: bytes) -> str:
        directory = home / "captures" / "cards" / f"box{box}"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{index:04d}.jpg").write_bytes(body)
        return hashlib.sha256(body).hexdigest()

    def stranded_payload(digests: dict) -> dict:
        """Two records still describing box 1, exactly as the run wrote them."""
        cards = {}
        for i, (name, number) in {1: ("Dunsparce", "120"), 2: ("Articuno", "145")}.items():
            cards[f"1/{i}"] = {
                "box": 1,
                "index": i,
                "photo": f"captures/cards/box1/{i:04d}.jpg",
                "photo_sha256": digests[i],
                "game": "pokemon",
                "identification": {
                    "name": name,
                    "number": number,
                    "printed_total": "159",
                    "confidence": "high",
                    "finish": None,
                },
            }
        return {"prompt_fingerprint": "t7-rescue", "cards": cards}

    def says(caught, label: str, *needles: str) -> None:
        text = str(caught) if caught is not None else ""
        missing = [needle for needle in needles if needle not in text]
        checks.ok(not missing, label, f"missing {missing!r} in:\n{text}")

    def run_count() -> int:
        return len([d for d in files.runs_dir().iterdir() if d.is_dir()])

    class Args:
        def __init__(self, run_dir, write=False):
            self.run_dir = str(run_dir)
            self.write = write

    other = "2026-09-11-box1-01"

    def reuse_box_one(snapshot, how_many: int = 2) -> None:
        """Box 1's number, reused for somebody else's cards — the reallocation itself."""
        snapshot.inventory.ensure_box(1)
        for n in range(1, how_many + 1):
            card, _ = snapshot.inventory.allocate_capture(
                1, capture_id=f"foreign-{n}", cid=fake_cid(f"foreign-{n}")
            )
            snapshot.inventory.record_identification(
                card.key, name="Moonfall", number="198/219",
                printed_total="219", confidence="high", run=other,
            )

    # ------------------------------------------------------------------ the whole repair
    with isolated_home() as home:
        # The cards are in box 3 now, at 3/2 and 3/3 — the same BYTES the run recorded a
        # digest for, under new names at new indices in a different drawer. Nothing but those
        # bytes ties the run's records to them.
        moved = {1: photo(home, 3, 2, b"rescue-card-one"), 2: photo(home, 3, 3, b"rescue-card-two")}
        run = runs.create("box1")
        run.set(
            capture_dir=str(home / "captures" / "cards" / "box1"),
            created_at="2026-08-29T22:37:47+00:00",
            model="claude-haiku-4-5-20251001",
            rule="match",
            flags={"max_edge": 1200},
            joined=True,
            emitted={"pushed": 133},
        )
        run.write_identifications(stranded_payload(moved))
        export = write_export(run.path("export.csv"))

        with Store().write() as snapshot:
            snapshot.inventory.ensure_box(3, name="RB Epics")
            # THE TWO RESCUED CARDS ARE NAMED BY THE PHOTOGRAPHS THE RUN READ (D172), which
            # is what makes this block exercise the store-backed digest map rather than the
            # glob the refusal cases below still fall back to. `cards.cid` IS the digest —
            # `cli/resolve.py:_photo_digests` reads the column and puts each row to its file
            # — so a destination card wearing an invented name would match nothing, and the
            # rescue would refuse a run it is supposed to repair. 3/1 keeps an invented name
            # and no photograph: it is the card that is simply not in this run.
            for n, cid in ((1, fake_cid("dest-1")), (2, moved[1]), (3, moved[2])):
                snapshot.inventory.allocate_capture(
                    3, capture_id=f"dest-{n}", game="pokemon", cid=cid
                )
            reuse_box_one(snapshot)

        box3_bid = Store().read().inventory.box(3).bid
        checks.ok(
            isinstance(box3_bid, int) and box3_bid > 0,
            "fixture: box 3 carries a true index (D145)",
            f"bid: {box3_bid!r}",
        )
        checks.raises(
            runs.RunError,
            lambda: resolve.exports_for(run, [str(export)]),
            "fixture: the join refuses this run, which is what makes it stranded",
        )

        # (a) THE PREVIEW PRESSES NOTHING.
        before = run_count()
        with quiet() as said:
            code = cmd_rescue.run(Args(run.directory), print)
        checks.equal(code, 0, "`banchi rescue` previews and exits 0")
        checks.equal(
            run_count(), before,
            "and writes no run directory — the preview is the default and it presses nothing",
        )
        preview = said.getvalue()
        for needle in ("stranded", "2 card(s), all in box 3", "1/1 -> 3/2", "1/2 -> 3/3"):
            checks.ok(needle in preview, f"the preview names {needle!r}", preview)
        checks.ok(
            f"bid           {box3_bid}" in preview,
            "and it names the drawer's true index before anything is written",
            preview,
        )

        # (b) THE WRITE, AND WHAT IT PRODUCES.
        with quiet():
            code = cmd_rescue.run(Args(run.directory, write=True), print)
        checks.equal(code, 0, "`--write` exits 0")
        checks.equal(run_count(), before + 1, "and creates exactly one run directory")
        rescued = [
            runs.open_run(d)
            for d in sorted(files.runs_dir().iterdir())
            if d.is_dir() and d.name != run.directory.name
        ][0]
        checks.equal(
            rescued.manifest.get("scope"),
            {"box": 3, "whole_box": False, "cards": 2, "bid": box3_bid},
            "THE SCOPE IS THE DRAWER THE CARDS ARE IN, WITH ITS TRUE INDEX ON IT (D145) — "
            "which is the whole reason this run can never become the thing it was derived "
            "from, whatever number that drawer wears later",
        )
        checks.equal(
            rescued.manifest.get(cmd_rescue.RESCUED_FROM),
            run.name,
            "and it names the run it came from, which is the only thing that tells a rescue "
            "run from an ordinary one",
        )
        checks.equal(
            [rescued.manifest.get("joined"), rescued.manifest.get("emitted")],
            [None, None],
            "WHAT IS CARRIED IS THE READING AND WHAT IS DROPPED IS THE SOURCE'S OWN ACTS — a "
            "copied `joined`/`emitted` would claim this run had spent money and sent a file",
        )
        checks.equal(
            rescued.manifest.get("model"),
            "claude-haiku-4-5-20251001",
            "while the reading itself carries over: these are the same answers, re-addressed",
        )
        checks.equal(
            sorted(rescued.read_identifications()["cards"]),
            ["3/2", "3/3"],
            "every record is re-keyed to the position its PHOTOGRAPH is at now — D36's own "
            "sentence, applied across drawers instead of within one",
        )
        checks.equal(
            [
                rescued.read_identifications()["cards"]["3/2"][field]
                for field in ("box", "index", "photo_sha256", "rescued_from_position")
            ],
            [3, 2, moved[1], "1/1"],
            "with the address moved, the DIGEST kept — it is the same bytes and the basis the "
            "record was matched on — and where it came from recorded on the record",
        )
        checks.equal(
            sorted(run.read_identifications()["cards"]),
            ["1/1", "1/2"],
            "AND THE SOURCE RUN IS UNTOUCHED. `cli/runs.py`'s first sentence is that a run is "
            "an immutable input; the repair derives a second run rather than editing the "
            "record of what was read",
        )

        # (c) THE RESCUE RUN JOINS, WHICH IS THE POINT.
        plan = resolve.exports_for(rescued, [str(export)])
        checks.equal(
            list(plan.by_game),
            ["pokemon"],
            "and the rescue run passes `refuse_reallocated` — not by weakening it, but "
            "because `scope.bid` matches box 3's own and there is nothing left to infer",
        )

        # (d) SAFE TO RUN TWICE.
        with quiet() as said:
            code = cmd_rescue.run(Args(run.directory, write=True), print)
        checks.equal(code, 0, "a second `--write` exits 0")
        checks.equal(
            run_count(), before + 1,
            "and writes NOTHING — an identical rescue already exists, so the command is "
            "re-runnable rather than a directory generator",
        )
        checks.ok(
            "already rescued" in said.getvalue(),
            "and says so by name rather than silently doing nothing",
            said.getvalue(),
        )

        # (e) A HEALTHY RUN IS REFUSED. Rescuing one would put a second run over the same
        # positions in runs/, which is the shape D86 measured a capped send over.
        caught = checks.raises(
            runs.RunError,
            lambda: cmd_rescue.run(Args(rescued.directory), hush),
            "a run the store still reads as its own is refused rather than duplicated",
        )
        says(caught, "and the refusal says so and names the join", "not stranded", "join")

        # (f) THE ID IS THE WHOLE ARM, PROVED BY MOVING NOTHING ELSE. Box 3 is deleted and its
        # number reused: same number, same cards at the same keys, same registry stamp — the
        # ONE thing that changes is the drawer's identity. The older inference rule cannot see
        # this at all, because the box still holds this run's own cards.
        with Store().write() as snapshot:
            snapshot.inventory.box(3).bid = box3_bid + 50
        checks.ok(
            Store().read().inventory.box_disowns_run(
                3, rescued.name, rescued.created_at, bid=box3_bid
            )
            is not None,
            "A DRAWER THAT SWAPPED ITS IDENTITY UNDER A RUN IS REFUSED ON THE ID ALONE — the "
            "number, the cards and the registry stamp are all unchanged, so this is the case "
            "the timestamp-and-card-set rule structurally cannot reach. This is what the run "
            "carrying a `bid` buys",
        )
        checks.ok(
            Store().read().inventory.box_disowns_run(3, rescued.name, rescued.created_at)
            is None,
            "and with no id passed the older rule abstains towards the box being the run's "
            "own, which is correct of it and is exactly why the id has to be recorded",
        )

        # AND A RESCUE OF A RESCUE IS REACHABLE, so it must not collide with itself: the
        # manifest it derives from already carries this command's own three keys.
        before = run_count()
        with quiet():
            code = cmd_rescue.run(Args(rescued.directory, write=True), print)
        checks.equal(code, 0, "a stranded RESCUE run is itself rescuable")
        checks.equal(run_count(), before + 1, "and writes one more run directory")
        again = [
            runs.open_run(d)
            for d in sorted(files.runs_dir().iterdir())
            if d.is_dir() and d.name not in (run.directory.name, rescued.directory.name)
        ][0]
        checks.equal(
            [
                again.manifest.get(cmd_rescue.RESCUED_FROM),
                again.manifest.get("rescued_cards"),
                (again.manifest.get("scope") or {}).get("bid"),
            ],
            [rescued.name, 2, box3_bid + 50],
            "naming the run it came from, counting its own cards, and taking the drawer's NEW "
            "id — not the one it was derived from",
        )

    # ------------------------------------------------------------------ the refusals
    with isolated_home() as home:
        # ONE RECORD'S DIGEST ON TWO PHOTOGRAPHS: a digest that names two slots is a question.
        # The two records carry DIFFERENT digests on purpose — the payload half of the rule is
        # the case below, and a fixture where both records share one digest fires that instead.
        body = b"rescue-ambiguous"
        digests = {1: photo(home, 3, 2, body), 2: photo(home, 3, 4, b"rescue-unique")}
        photo(home, 3, 3, body)
        run = runs.create("box1")
        run.set(created_at="2026-08-29T22:37:47+00:00")
        run.write_identifications(stranded_payload(digests))
        with Store().write() as snapshot:
            snapshot.inventory.ensure_box(3)
            reuse_box_one(snapshot)
        before = run_count()
        caught = checks.raises(
            runs.RunError,
            lambda: cmd_rescue.run(Args(run.directory, write=True), hush),
            "a digest on two photographs refuses the whole run — `realign`'s rule, unchanged",
        )
        says(caught, "and says it is a question rather than a slot", "two photographs", "guessing")
        checks.equal(run_count(), before, "and nothing is written")

    with isolated_home() as home:
        # ONE DIGEST ON TWO RECORDS — the payload half of the same rule, which is where
        # `realign` found a silent drop.
        one = hashlib.sha256(b"rescue-same-record").hexdigest()
        photo(home, 3, 2, b"rescue-same-record")
        run = runs.create("box1")
        run.set(created_at="2026-08-29T22:37:47+00:00")
        run.write_identifications(stranded_payload({1: one, 2: one}))
        with Store().write() as snapshot:
            snapshot.inventory.ensure_box(3)
            reuse_box_one(snapshot)
        caught = checks.raises(
            runs.RunError,
            lambda: cmd_rescue.run(Args(run.directory, write=True), hush),
            "and a digest carried by two RECORDS refuses too, before any photograph is read",
        )
        says(caught, "naming what it refuses", "more than one record")

    with isolated_home() as home:
        # THE CARDS ARE SPREAD ACROSS TWO DRAWERS. D180 keeps a run to one box.
        digests = {1: photo(home, 3, 2, b"split-a"), 2: photo(home, 4, 20, b"split-b")}
        run = runs.create("box1")
        run.set(created_at="2026-08-29T22:37:47+00:00")
        run.write_identifications(stranded_payload(digests))
        with Store().write() as snapshot:
            snapshot.inventory.ensure_box(3)
            snapshot.inventory.ensure_box(4)
            reuse_box_one(snapshot)
        before = run_count()
        caught = checks.raises(
            runs.RunError,
            lambda: cmd_rescue.run(Args(run.directory, write=True), hush),
            "cards spread across two drawers refuse — a rescue that wrote one run over "
            "several would be a cart nobody has argued for (D180)",
        )
        says(caught, "and names both drawers", "3, 4")
        checks.equal(run_count(), before, "and nothing is written")

    with isolated_home():
        # NOTHING ON A SHELF — the owner's OTHER reallocated run, `2026-08-22-box1-03`, whose
        # 53 cards went with box 1 on 2026-08-25. There is nothing to repair, and the warning
        # `_on_hand_by_run` feeds says so rather than counting it as stranded stock.
        digests = {
            1: hashlib.sha256(b"gone-a").hexdigest(),
            2: hashlib.sha256(b"gone-b").hexdigest(),
        }
        run = runs.create("box1")
        run.set(created_at="2026-08-22T22:40:24+00:00")
        run.write_identifications(stranded_payload(digests))
        with Store().write() as snapshot:
            reuse_box_one(snapshot)
        caught = checks.raises(
            runs.RunError,
            lambda: cmd_rescue.run(Args(run.directory, write=True), hush),
            "a stranded run whose cards have all left the store is refused rather than "
            "rescued into an empty run — measured: `2026-08-22-box1-03` is exactly this",
        )
        says(caught, "and says the cards have left", "nothing on a shelf")

        with quiet() as said:
            code = entry.main(["rescue", str(run.directory)])
        checks.equal(code, 1, "`banchi rescue` is a real subcommand and exits 1 on a refusal")
        checks.ok("REFUSING" in said.getvalue(), "printing the refusal", said.getvalue())


def check_rescue_discharges_stranded_count(checks: Checks) -> None:
    """A rescued run stops counting as stranded on `#/pricing`.

    `banchi rescue` (D36's own repair, asserted above) re-addresses a stranded run's cards
    to a new, joinable run over the drawer they are actually in — the fix `#/pricing`'s own
    tooltip sends the operator to. It never edits the STRANDED run's manifest or the store's
    `cards.run` column (`cli/cmd_rescue.py`: a rescue derives a second run rather than
    changing the record of what was read), so `_on_hand_by_run` went on counting the same
    cards under the old run's identity forever, and `GET /pipeline/pricing`'s
    `unreachable.reallocated` kept naming a run the operator had already repaired.

    This asserts `do_pipeline_worklist` subtracts every JOINED rescue's own `rescued_cards`
    from the stranded figure (summed, since a run can be rescued more than once), names the
    rescue in `rescued_by`, and — the case that matters as much as the discharge itself —
    does NOT subtract while the rescue is unjoined, because an unjoined rescue's cards are
    not on any worklist yet.
    """
    checks.note("")
    checks.note("RESCUE DISCHARGES THE COUNT — a joined rescue drops the stranded figure")

    from cli import cmd_rescue

    with isolated_home():
        # THE RUN'S OWN NAME IS WHAT `cards.run` MUST MATCH — `runs.create` timestamps it,
        # so it is captured here rather than assumed, and every card below is stamped with
        # the name this run actually got.
        old_run = runs.create("box1")
        OLD_RUN = old_run.directory.name

        # box 1 — the stranded drawer, five cards, all this run's.
        with Store().write() as snapshot:
            inventory = snapshot.inventory
            old = inventory.ensure_box(1, name="Pokemon shakedown")
            old.created_at = "2026-08-22T09:00:00+00:00"
            moved_keys = []
            for n in range(5):
                card, _ = inventory.allocate_capture(1, cid=fake_cid(f"stranded-{n}"))
                card.game, card.run = "pokemon", OLD_RUN
                moved_keys.append(card.key)
            old_bid = old.bid

        old_run.set(
            capture_dir=str(files.home() / "captures/cards/box1"),
            created_at="2026-08-29T22:37:47+00:00",
            scope={"box": 1, "whole_box": True, "cards": None, "bid": old_bid},
            joined=True,
        )

        # box 3 — the drawer all five cards are ACTUALLY in now (D83: moved, not sold or
        # retired). `cards.run` still names `OLD_RUN`: a move changes where a card is,
        # never who read it, which is exactly what makes it stranded rather than gone, and
        # it is also what frees box 1's number to be reused (`next_box_number` counts a
        # card's own `box` column, not only the registry).
        with Store().write() as snapshot:
            inventory = snapshot.inventory
            dest = inventory.ensure_box(3, name="RB Epics")
            dest.created_at = "2026-08-29T14:00:00+00:00"
            dest_bid = dest.bid
            for key in moved_keys:
                inventory.cards.get(key).box = 3

        # THE DELETION AND THE REALLOCATION (D36 — the owner's own store's shape): box 1's
        # registry entry goes, and its NUMBER — never its identity — comes back for an
        # unrelated drawer, the whole reason a run's `bid` and not its box number is what
        # says whether it departed.
        with Store().write() as snapshot:
            inventory = snapshot.inventory
            entry = inventory.boxes.pop("1")
            inventory._log(
                "box_deleted", None, box=1, bid=entry.bid, name=entry.name, cards=0, buried=0,
            )
            number = inventory.next_box_number()
            checks.equal(number, 1, "fixture: box 1's number is free again and reused first")
            reused = inventory.ensure_box(number, name="Someone else's drawer")
            reused.created_at = "2026-09-01T00:00:00+00:00"

        def reallocated_row(payload: dict) -> dict:
            return next(
                r for r in payload["unreachable"]["reallocated"] if r["run"] == old_run.directory.name
            )

        # (a) BEFORE ANY RESCUE — the full on-hand count, no rescue named.
        before = pipeline_routes.do_pipeline_worklist([])
        row = reallocated_row(before)
        checks.equal(
            (row["cards"], row.get("rescued"), row.get("rescued_by")),
            (5, 0, []),
            "before a rescue exists, the stranded run reports every card it still holds and "
            "names no rescue",
        )

        # (b) A RESCUE RUN, over the drawer the cards actually landed in (box 3), JOINED.
        rescue_run = runs.create("box3-rescue")
        rescue_run.set(
            capture_dir=str(files.home() / "captures/cards/box1"),
            created_at="2026-09-13T00:00:00+00:00",
            scope={"box": 3, "whole_box": False, "cards": 3, "bid": dest_bid},
            joined=True,
            **{cmd_rescue.RESCUED_FROM: old_run.directory.name},
            rescued_cards=3,
            rescued_left_behind=2,
        )
        after = pipeline_routes.do_pipeline_worklist([])
        row = reallocated_row(after)
        checks.equal(
            (row["cards"], row["rescued"], row["rescued_by"]),
            (2, 3, [rescue_run.directory.name]),
            "AFTER A JOINED RESCUE the stranded figure drops by exactly what the rescue "
            "carried away, and the row names which run took it",
        )

        # (c) AN UNJOINED RESCUE DOES NOT DISCHARGE ANYTHING — its cards are not on any
        # worklist yet, so dropping the stranded count here would be the false relief this
        # fix must not introduce.
        rescue_run.set(joined=False)
        still = pipeline_routes.do_pipeline_worklist([])
        row = reallocated_row(still)
        checks.equal(
            (row["cards"], row["rescued"], row["rescued_by"]),
            (5, 0, []),
            "an unjoined rescue is invisible to this count — the stranded run reads exactly "
            "as it did before any rescue existed",
        )


def check_rescue_route(checks: Checks) -> None:
    """`POST /pipeline/runs/<name>/rescue` — the CLI reached from a screen, D145.

    `check_rescue_stranded_run` above asserts `cmd_rescue.run` itself; this is the route that
    makes it reachable from `#/runs` at all, and it is not the same shape as every other free
    step. `do_queue_refresh` and `do_pipeline_step` return `console` verbatim (D33) because
    stdout is the one description of what a free command did — but the owner ruled, 2026-09-13,
    that raw machine text may never reach a screen, not even behind a disclosure, and
    `cmd_rescue`'s own sentences carry backticked `banchi …` invocations and decision numbers
    that are exactly the class `no mechanism on screen` refuses. So this route is the deliberate
    exception: it parses `cmd_rescue`'s stdout into a small structured shape, writes the raw
    text to a log file under the run's own directory, and returns no `console` field at all.

    RED TODAY: `pipeline_routes.do_run_rescue` does not exist until this PR.
    """
    checks.note("")
    checks.note("RESCUE ROUTE — POST /pipeline/runs/<name>/rescue, structured and never verbatim")

    def photo(home, box: int, index: int, body: bytes) -> str:
        directory = home / "captures" / "cards" / f"box{box}"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{index:04d}.jpg").write_bytes(body)
        return hashlib.sha256(body).hexdigest()

    def stranded_payload(digests: dict) -> dict:
        cards = {}
        for i, (name, number) in {1: ("Dunsparce", "120"), 2: ("Articuno", "145")}.items():
            cards[f"1/{i}"] = {
                "box": 1,
                "index": i,
                "photo": f"captures/cards/box1/{i:04d}.jpg",
                "photo_sha256": digests[i],
                "game": "pokemon",
                "identification": {
                    "name": name,
                    "number": number,
                    "printed_total": "159",
                    "confidence": "high",
                    "finish": None,
                },
            }
        return {"prompt_fingerprint": "t7-rescue-route", "cards": cards}

    def run_count() -> int:
        return len([d for d in files.runs_dir().iterdir() if d.is_dir()])

    with isolated_home() as home:
        moved = {
            1: photo(home, 3, 2, b"rescue-route-card-one"),
            2: photo(home, 3, 3, b"rescue-route-card-two"),
        }
        run = runs.create("box1")
        run.set(
            capture_dir=str(home / "captures" / "cards" / "box1"),
            created_at="2026-08-29T22:37:47+00:00",
            model="claude-haiku-4-5-20251001",
            rule="match",
            flags={"max_edge": 1200},
            joined=True,
            emitted={"pushed": 133},
        )
        run.write_identifications(stranded_payload(moved))

        with Store().write() as snapshot:
            snapshot.inventory.ensure_box(3, name="RB Epics")
            for n, cid in ((1, fake_cid("dest-route-1")), (2, moved[1]), (3, moved[2])):
                snapshot.inventory.allocate_capture(
                    3, capture_id=f"dest-route-{n}", game="pokemon", cid=cid
                )
            snapshot.inventory.ensure_box(1)
            card, _ = snapshot.inventory.allocate_capture(
                1, capture_id="foreign-route-1", cid=fake_cid("foreign-route-1")
            )
            snapshot.inventory.record_identification(
                card.key, name="Moonfall", number="198/219",
                printed_total="219", confidence="high", run="2026-09-11-box1-01",
            )

        box3_bid = Store().read().inventory.box(3).bid

        # (a) THE PREVIEW: `ok:true`, `wrote:false`, and nothing new under `runs/`.
        before = run_count()
        preview = pipeline_routes.do_run_rescue(run.name, {})
        checks.equal(preview["ok"], True, "the preview exits 0")
        checks.equal(preview["wrote"], False, "and reports nothing written")
        checks.equal(run_count(), before, "and creates no run directory")
        checks.ok(
            "console" not in preview,
            "NO RAW STDOUT ON THE WIRE — the owner's 2026-09-13 ruling, and the whole reason "
            "this route exists apart from `do_pipeline_step`",
            preview,
        )
        checks.equal(
            preview["counts"]["rebound"], 2,
            "the structured count agrees with the CLI's own report: 2 cards found",
        )
        checks.equal(
            preview["destination"], {"box": 3, "box_name": "RB Epics"},
            "and names the drawer they are in now",
        )
        log_path = files.runs_dir() / preview["log"]
        checks.ok(
            log_path.is_file() and "1/1 -> 3/2" in log_path.read_text("utf-8"),
            "the raw report lands on disk, under the run's own directory, where a person at "
            "the machine — never a screen — can read it",
            preview,
        )

        # (b) THE WRITE: a new run directory, named on the response.
        wrote = pipeline_routes.do_run_rescue(run.name, {"write": True})
        checks.equal(wrote["ok"], True, "the write exits 0")
        checks.equal(wrote["wrote"], True, "and reports a write")
        checks.equal(run_count(), before + 1, "and creates exactly one new run directory")
        checks.ok(
            isinstance(wrote["new_run"], str) and (files.runs_dir() / wrote["new_run"]).is_dir(),
            "and names the new run, which is the sheet's way back in (`onOpenRun`)",
            wrote,
        )
        rescued = runs.open_run(files.runs_dir() / wrote["new_run"])
        checks.equal(
            rescued.manifest.get("scope"),
            {"box": 3, "whole_box": False, "cards": 2, "bid": box3_bid},
            "the written run is the byte-identical scope `cmd_rescue.run` itself writes — "
            "the route adds a parse, never a second decision",
        )
        checks.ok(
            "console" not in wrote,
            "the write's response carries no raw stdout either",
            wrote,
        )

        # (c) RE-PREVIEWING AFTER THE WRITE names the already-rescued run and writes nothing.
        again = pipeline_routes.do_run_rescue(run.name, {})
        checks.equal(again["ok"], True, "re-previewing after a write still exits 0")
        checks.equal(again["already_rescued"], wrote["new_run"], "and names the existing rescue")
        checks.equal(run_count(), before + 1, "and writes no second run directory")

        # (d) A REFUSAL — the source run itself, which is not stranded (its own box is live).
        healthy = runs.create("box3")
        healthy.set(created_at="2026-08-29T22:37:47+00:00")
        healthy.write_identifications({"prompt_fingerprint": "t7-rescue-route-healthy", "cards": {}})
        refused = pipeline_routes.do_run_rescue(healthy.name, {})
        checks.equal(refused["ok"], False, "a healthy run's rescue refuses")
        checks.equal(refused["reason"], "not_stranded", "and the reason is read off the CLI's own report")
        checks.ok(
            "console" not in refused,
            "a refusal carries no raw stdout either — the log file is the only place it goes",
            refused,
        )


def check_rescue_json_reasons(checks: Checks) -> None:
    """Every reason `cmd_rescue.run --json` can return, pinned against the REAL condition.

    THE COORDINATOR'S OWN FINDING: `_parse_rescue_console` (the substring parser this PR
    replaced) had six branches and only `not_stranded` was ever exercised by anything —
    reword a sentence in `cli/cmd_rescue.py` tomorrow and five reasons silently become the
    wrong code or none at all, with every check green. `--json` (D210) makes
    the command say its own answer rather than have a route guess at it from prose, and this
    is where each of the six codes gets proven against the actual condition that produces it
    — a healthy run, a run whose cards have all left, cards split across two drawers, a
    digest on two photographs, a digest on two records, and a store-backed join's own output
    directory — never a fixture that hands the parser a string.

    EVERY CASE GOES THROUGH `entry.main`, THE REAL CLI ENTRY POINT — never `cmd_rescue.run`
    called directly — so the reason travels through the same argparse `--json` flag a
    terminal or `server/pipeline_routes.py:do_run_rescue` would use.
    """
    checks.note("")
    checks.note("RESCUE --json — every reason code, pinned against the real condition")

    from cli import __main__ as entry

    def photo(home, box: int, index: int, body: bytes) -> str:
        directory = home / "captures" / "cards" / f"box{box}"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{index:04d}.jpg").write_bytes(body)
        return hashlib.sha256(body).hexdigest()

    def stranded_payload(digests: dict) -> dict:
        cards = {}
        for i, (name, number) in {1: ("Dunsparce", "120"), 2: ("Articuno", "145")}.items():
            cards[f"1/{i}"] = {
                "box": 1,
                "index": i,
                "photo": f"captures/cards/box1/{i:04d}.jpg",
                "photo_sha256": digests[i],
                "game": "pokemon",
                "identification": {
                    "name": name,
                    "number": number,
                    "printed_total": "159",
                    "confidence": "high",
                    "finish": None,
                },
            }
        return {"prompt_fingerprint": "t7-rescue-json", "cards": cards}

    def reuse_box_one(snapshot) -> None:
        snapshot.inventory.ensure_box(1)
        card, _ = snapshot.inventory.allocate_capture(
            1, capture_id="reason-foreign", cid=fake_cid("reason-foreign")
        )
        snapshot.inventory.record_identification(
            card.key, name="Moonfall", number="198/219",
            printed_total="219", confidence="high", run="2026-09-11-box1-01",
        )

    def rescue_json(run_dir) -> dict:
        """Run the real CLI, real `--write`, real `--json`, and return the one parsed line."""
        with quiet() as said:
            code = entry.main(["rescue", str(run_dir), "--write", "--json"])
        lines = [line for line in said.getvalue().splitlines() if line.strip().startswith("{")]
        checks.ok(len(lines) == 1, f"exactly one JSON line printed (exit {code})", said.getvalue())
        return json.loads(lines[-1]) if lines else {}

    # ------------------------------------------------------------ not_stranded
    with isolated_home() as home:
        healthy = runs.create("box3")
        healthy.set(created_at="2026-08-29T22:37:47+00:00")
        healthy.write_identifications(stranded_payload(
            {1: hashlib.sha256(b"healthy-1").hexdigest(), 2: hashlib.sha256(b"healthy-2").hexdigest()}
        ))
        # The run says box 1, and box 1 is a live drawer the store still reads as this run's
        # own — no `box_disowns_run` sentence, so nothing is stranded.
        with Store().write() as snapshot:
            snapshot.inventory.ensure_box(1)
        report = rescue_json(healthy.directory)
        checks.equal(report.get("reason"), "not_stranded", "a healthy run reports not_stranded")

    # ------------------------------------------------------------ none_on_shelf
    with isolated_home() as home:
        digests = {
            1: hashlib.sha256(b"gone-json-a").hexdigest(),
            2: hashlib.sha256(b"gone-json-b").hexdigest(),
        }
        run = runs.create("box1")
        run.set(created_at="2026-08-22T22:40:24+00:00")
        run.write_identifications(stranded_payload(digests))
        with Store().write() as snapshot:
            reuse_box_one(snapshot)
        report = rescue_json(run.directory)
        checks.equal(report.get("reason"), "none_on_shelf", "cards that have all left the store report none_on_shelf")
        checks.equal(report.get("counts", {}).get("rebound"), 0, "and rebound is 0")

    # ------------------------------------------------------------ spread_across_boxes
    with isolated_home() as home:
        digests = {1: photo(home, 3, 2, b"split-json-a"), 2: photo(home, 4, 20, b"split-json-b")}
        run = runs.create("box1")
        run.set(created_at="2026-08-29T22:37:47+00:00")
        run.write_identifications(stranded_payload(digests))
        with Store().write() as snapshot:
            snapshot.inventory.ensure_box(3)
            snapshot.inventory.ensure_box(4)
            reuse_box_one(snapshot)
        report = rescue_json(run.directory)
        checks.equal(report.get("reason"), "spread_across_boxes", "cards split across two drawers report spread_across_boxes")

    # ------------------------------------------------------------ digest_ambiguous_on_disk
    with isolated_home() as home:
        body = b"rescue-json-ambiguous"
        digests = {1: photo(home, 3, 2, body), 2: photo(home, 3, 4, b"rescue-json-unique")}
        photo(home, 3, 3, body)
        run = runs.create("box1")
        run.set(created_at="2026-08-29T22:37:47+00:00")
        run.write_identifications(stranded_payload(digests))
        with Store().write() as snapshot:
            snapshot.inventory.ensure_box(3)
            reuse_box_one(snapshot)
        report = rescue_json(run.directory)
        checks.equal(
            report.get("reason"), "digest_ambiguous_on_disk",
            "a digest on two photographs on disk reports digest_ambiguous_on_disk",
        )
        checks.equal(report.get("counts", {}).get("ambiguous"), 1, "naming the one record it touches")

    # ------------------------------------------------------------ digest_twice_in_run
    with isolated_home() as home:
        one = hashlib.sha256(b"rescue-json-same-record").hexdigest()
        photo(home, 3, 2, b"rescue-json-same-record")
        run = runs.create("box1")
        run.set(created_at="2026-08-29T22:37:47+00:00")
        run.write_identifications(stranded_payload({1: one, 2: one}))
        with Store().write() as snapshot:
            snapshot.inventory.ensure_box(3)
            reuse_box_one(snapshot)
        report = rescue_json(run.directory)
        checks.equal(
            report.get("reason"), "digest_twice_in_run",
            "one digest carried by two records in the RUN itself reports digest_twice_in_run",
        )
        checks.equal(report.get("counts", {}).get("ambiguous"), 1, "naming the one digest")

    # ------------------------------------------------------------ no_identifications
    with isolated_home() as home:
        # THE REACHABLE CONDITION: a store-backed join's own output directory (D188) —
        # `banchi join --keys` writes a run with a report and a pricing table but never
        # `identifications.json`, because there was no frozen snapshot to write one from.
        box, index = 5, 1
        while Store().read().inventory.next_index(box) <= index:
            capture_server.do_capture(capture_payload(box))
        key = master.position_key(box, index)
        with Store().write() as snapshot:
            snapshot.inventory.record_capture(
                master.Card(box=box, index=index, photo=str(photo_of(box, index)))
            )
            snapshot.inventory.record_identification(
                key, name="Dunsparce", number="120", printed_total="159",
                confidence="high", run="an-earlier-run",
            )
        export = write_export(home / "export.csv")
        with quiet():
            code = entry.main(["join", "--keys", key, "--export", str(export)])
        checks.equal(code, 0, "the store-backed join itself exits 0")
        created = [d for d in files.runs_dir().iterdir() if d.is_dir()]
        checks.equal(len(created), 1, "and creates exactly one run directory")
        report = rescue_json(created[0])
        checks.equal(
            report.get("reason"), "no_identifications",
            "a store-backed join's own output directory reports no_identifications",
        )


def check_store_backed_join(checks: Checks) -> None:
    """PR G — `join` without a run directory, reading identifications straight off the store.

    THE PLAN'S OWN NAMED RISK, SETTLED FIRST. `cli/resolve.py:store_payload` is a NEW loader,
    built to answer for a run's `identifications.json` field for field. The surest way to trust
    it is to build one run and one store that describe the SAME three cards the same way —
    `identifications_for`'s own shape, mirrored onto the store through `record_capture` and
    `record_identification`, which is the ordinary writer `cli/cmd_identify.py` uses rather
    than a hand-poked field — load one through `resolve.load` and the other through
    `resolve.load_from_store`, and require every `SkuMatch` and every queue entry the two
    produce to compare EQUAL by dataclass equality: every field, not the ones this test
    happened to think of.

    THE REPLAY BRANCH (D36), THE OTHER WAY ROUND. `load`'s run is REPLAYED and reconciled
    against the store (`realign`, `refuse_reallocated`); `load_from_store` has no frozen
    snapshot to reconcile, so it never calls either — asserted directly below, because a
    loader that silently started calling them over a live read would be re-hashing every
    photograph in the box for nothing.
    """
    checks.note("")
    checks.note("STORE-BACKED JOIN (PR G) — `resolve.load_from_store`, and `join --keys`")

    from cli import __main__ as entry
    from cli import cmd_rescue

    cards = [
        (5, 1, "Dunsparce", "120/159", None),
        (5, 2, "Dunsparce", "120/159", "reverse_holo"),
        (5, 3, "Articuno", "161/159", "holo"),
    ]
    keys = [master.position_key(box, index) for box, index, *_ in cards]

    with isolated_home() as home:
        for box, index, *_ in cards:
            while Store().read().inventory.next_index(box) <= index:
                capture_server.do_capture(capture_payload(box))

        # A run's frozen `identifications.json`, describing three cards — `identifications_for`'s
        # own shape. Created BEFORE the store write below so the store's own `run` stamp can
        # name it: `refuse_reallocated` (D36) refuses a run whose keys are stamped by some
        # OTHER run, on purpose (`check_reused_box_refusal` exercises exactly that refusal),
        # and this fixture wants the ORDINARY case — the store and the run agreeing — not it.
        run_dir = runs.create("t7-store-parity")
        run_dir.write_identifications(identifications_for(cards))
        export = write_export(run_dir.path("export.csv"))

        # The store's own reading, written through the ordinary writers `identify` uses —
        # never a `Card` field poked directly — so this fixture exercises the real path.
        with Store().write() as snapshot:
            for box, index, name, number, finish in cards:
                key = master.position_key(box, index)
                snapshot.inventory.record_capture(
                    master.Card(
                        box=box,
                        index=index,
                        photo=str(photo_of(box, index)),
                        metadata_finish=finish,
                    )
                )
                snapshot.inventory.record_identification(
                    key,
                    name=name,
                    number=number,
                    printed_total="159",
                    confidence="high",
                    detected_finish=finish,
                    run=run_dir.name,
                )

        via_file = resolve.load(run_dir, {"pokemon": export})
        via_store = resolve.load_from_store(run_dir, keys, {"pokemon": export})

        checks.equal(
            set(via_store.matches), set(via_file.matches),
            "the store loader matches the same SKUs the file loader does",
        )
        for sku in via_file.matches:
            checks.equal(
                via_store.matches.get(sku), via_file.matches[sku],
                f"SkuMatch for {sku} agrees FIELD BY FIELD between `load` and "
                f"`load_from_store` (dataclass equality, not a hand-picked subset)",
            )
        checks.equal(
            via_store.failures, via_file.failures,
            "no pre-join failures on either path",
        )
        checks.equal(
            via_store.not_joined, via_file.not_joined,
            "nothing held out of the catalog on either path",
        )
        checks.equal(
            via_store.photos, via_file.photos,
            "the same photo path per position on both paths",
        )
        checks.equal(
            via_store.realigned, {},
            "the store path never realigns — there is no frozen snapshot to reconcile",
        )
        checks.equal(via_store.departed, [], "and never marks a card departed")
        checks.equal(via_store.unverified_boxes, [], "and never marks a box unverified")

        main_file, parked_file = resolve.entries_for(via_file)
        main_store, parked_store = resolve.entries_for(via_store)

        def entry_shape(one):
            # `first_seen` is stamped to "now" by each loader's own pass and is not a fact
            # about the card — excluded here for the reason `check_review_answer` excludes
            # timestamps elsewhere in this file, never because the rest of the shape may drift.
            return (
                one.position, one.box, one.index, one.label, one.photo, one.read,
                one.confidence, one.reason, one.candidates, one.market,
            )

        checks.equal(
            [entry_shape(e) for e in main_store],
            [entry_shape(e) for e in main_file],
            "the main review queue entry the ambiguous Dunsparce card earns is identical "
            "on both paths, candidates and all",
        )
        checks.equal(
            [entry_shape(e) for e in parked_store],
            [entry_shape(e) for e in parked_file],
            "and the parked queue agrees too (empty on this fixture)",
        )

        # ---------------------------------------------------- a card the store never saw
        caught = checks.raises(
            runs.RunError,
            lambda: resolve.store_payload(["999/999"], Store().read().inventory),
            "a key with no card at all is REFUSED, never silently dropped or matched to "
            "the wrong card (`CLAUDE.md`'s standing rule)",
        )
        checks.ok(
            caught is not None and "999/999" in str(caught),
            "and the refusal names the key",
            str(caught) if caught else "",
        )

        # ------------------------------------------------- a real, positioned, unidentified card
        capture_server.do_capture(capture_payload(5))
        blank_key = master.position_key(5, 4)
        payload = resolve.store_payload([blank_key], Store().read().inventory)
        checks.equal(
            payload["cards"][blank_key]["identification"], None,
            "a captured-but-never-identified card gets a real record with `identification: "
            "None` — never refused and never silently skipped, so `_resolve`'s existing "
            "`if not identification` branch routes it to the main queue exactly as an "
            "`identify` failure would",
        )
        checks.equal(
            payload["cards"][blank_key]["box"], 5, "and it still carries its real position"
        )

    # -------------------------------------------------------------- the CLI: `join --keys`
    with isolated_home() as home:
        for box, index, *_ in cards:
            while Store().read().inventory.next_index(box) <= index:
                capture_server.do_capture(capture_payload(box))
        with Store().write() as snapshot:
            for box, index, name, number, finish in cards:
                key = master.position_key(box, index)
                snapshot.inventory.record_capture(
                    master.Card(
                        box=box,
                        index=index,
                        photo=str(photo_of(box, index)),
                        metadata_finish=finish,
                    )
                )
                snapshot.inventory.record_identification(
                    key,
                    name=name,
                    number=number,
                    printed_total="159",
                    confidence="high",
                    detected_finish=finish,
                    run="an-earlier-run",
                )
        export = write_export(home / "export.csv")
        keys_arg = ",".join(keys)

        with quiet() as said:
            code = entry.main(["join", "some-run-dir", "--keys", keys_arg, "--export", str(export)])
        checks.equal(
            code, 1,
            "naming a run directory AND --keys together is refused rather than guessed at",
        )
        checks.ok("both" in said.getvalue().lower(), "and says so", said.getvalue())

        with quiet() as said:
            code = entry.main(["join", "--export", str(export)])
        checks.equal(code, 1, "naming NEITHER is refused rather than reading the whole store")
        checks.ok(
            "--keys" in said.getvalue(), "and names the flag that would fix it", said.getvalue()
        )

        def run_names() -> set:
            root = files.runs_dir()
            return {d.name for d in root.iterdir() if d.is_dir()} if root.is_dir() else set()

        before = run_names()
        with quiet() as said:
            code = entry.main(
                ["join", "--keys", keys_arg, "--export", str(export), "--dry-run"]
            )
        checks.equal(code, 0, "a store-backed dry run exits 0")
        checks.equal(
            run_names(), before,
            "and creates NO run directory at all — `_preview`'s own \"no manifest\" line "
            "would otherwise be false the moment `runs.create` ran ahead of it",
        )
        checks.ok(
            "no manifest" in said.getvalue(),
            "and the preview still says so", said.getvalue(),
        )

        with quiet() as said:
            code = entry.main(["join", "--keys", keys_arg, "--export", str(export)])
        checks.equal(code, 0, "the real store-backed join exits 0")
        created = run_names() - before
        checks.equal(len(created), 1, "and creates exactly one new run directory")
        new_run = runs.open_run(files.runs_dir() / next(iter(created)))
        checks.equal(
            new_run.manifest.get("selection"), {"keys": sorted(keys)},
            "the manifest records the selection that was asked for, `identify`'s own style",
        )
        checks.ok(
            not new_run.path(runs.IDENTIFICATIONS).is_file(),
            "and NEVER writes `identifications.json` — there was no snapshot to freeze",
        )
        checks.ok(
            new_run.path(runs.PRICING).is_file() and new_run.path(runs.REPORT).is_file(),
            "and DOES write this join's own report and pricing table, exactly like a "
            "run-directory join does",
        )

        # ------------------------------------------- `_phase` must not read this run as "not
        # started" (D188 footnote). `collected` is never written on a store-backed join, and
        # `_phase` used to gate every stage past "ready"/"identify" on `collected` alone, so
        # this run's badge would read "Not started" beside a real `joined: True` and real
        # `counts.skus` on disk — the exact "one badge, one set of files, disagreeing" defect.
        phase = pipeline_routes._phase(new_run.manifest, live=False)
        checks.ok(
            phase not in ("ready", "identify"),
            "a store-backed join's phase is never `ready`/`identify` — `joined` alone is "
            "sufficient evidence identification happened, by either of D188's two loaders",
            phase,
        )

        # ------------------------------------------------- rescue refuses this run by name
        caught = checks.raises(
            runs.RunError,
            lambda: cmd_rescue.run(
                type("Args", (), {"run_dir": str(new_run.directory), "write": False})(),
                lambda *_: None,
            ),
            "`banchi rescue` refuses a store-backed join's own output directory rather "
            "than crashing on a missing `identifications.json` or treating it as an "
            "ordinary un-stranded run",
        )
        checks.ok(
            caught is not None and "store-backed join" in str(caught),
            "and names WHY — this directory was never an `identify` run",
            str(caught) if caught else "",
        )


def check_run_binds_to_bid(checks: Checks) -> None:
    """A run records its drawer's TRUE INDEX from every path that starts one (D145).

    THE HALF THE RUN OBJECT NEVER ADOPTED. The route has written `bid` into the scope block
    since D145, so a run started from `#/runs` is bound. A run started in a TERMINAL had no
    `scope` block at all, and `_run_box` fell back to parsing the box number out of the capture
    directory's NAME — so `cli/resolve.py:refuse_reallocated` had nothing to compare and the
    older inference rule decided every one of them. This asserts the CLI half, which was the
    last creation path that could still produce a run nobody can bind.

    THERE IS ONE DERIVATION NOW AND THIS CASE DRIVES IT (D180). The message
    below used to read *"the shape `_resolve_scope` writes on the route"* about a call into the
    CLI's own copy — two implementations of one block, asserted to agree by prose in each
    pointing at the other. `pipeline/selection.py:scope_block` is the single reader and both
    callers adapt to it, so the agreement is structural and this case covers both.

    AND `whole_box` IS COUNTED RATHER THAN COMPARED TO A PATH. It used to be
    `capture_dir == captures/cards/boxN`, which stopped being answerable when `--box` became a
    filter over a scan of the whole capture root — the path is the ROOT now, not the drawer. So
    it asks the question the field has always meant: did this run read every photograph the
    drawer holds? The fixture below therefore has to put real files in the drawer, which is
    also what makes the assertion worth more than the path compare was.

    AND THE WARNING COUNTS CARDS RATHER THAN RUNS. `_on_hand_by_run` is what lets
    `#/pricing` say "99 in 1 run over a deleted box" instead of "1 run over a deleted box" —
    the same sentence the owner's store was printing for one run holding 99 sellable cards
    and another holding none.
    """
    checks.note("")
    checks.note("RUN -> BID — every path that starts a run records the drawer's true index")

    from cli import cmd_identify

    class FakeItem:
        def __init__(self, box):
            self.capture = sidecar.Capture(photo=Path("x.jpg"), box=box, index=1)

    with isolated_home() as home:
        with Store().write() as snapshot:
            snapshot.inventory.ensure_box(3, name="RB Epics")
            snapshot.inventory.ensure_box(4)
        inventory = Store().read().inventory
        bid3 = inventory.box(3).bid
        bid4 = inventory.box(4).bid
        checks.ok(bid3 != bid4, "fixture: two drawers, two ids", f"{bid3} vs {bid4}")

        own = home / "captures" / "cards" / "box3"
        own.mkdir(parents=True, exist_ok=True)
        # THE DRAWER HOLDS TWO PHOTOGRAPHS, which is what makes `whole_box` answerable at all
        # now: it is a count against the drawer's own directory rather than a comparison against
        # the path the command was pointed at.
        for index in (1, 2):
            (own / f"{index:04d}.jpg").write_bytes(JPEG)
        checks.equal(
            cmd_identify._scope_for([FakeItem(3), FakeItem(3)], inventory),
            {"box": 3, "whole_box": True, "cards": None, "bid": bid3},
            "a terminal run that read BOTH of box 3's photographs records the box, "
            "`whole_box`, and THE DRAWER'S TRUE INDEX — through the one derivation the route "
            "uses, so a preflight's preview and the manifest a press writes cannot disagree",
        )
        checks.equal(
            cmd_identify._scope_for([FakeItem(3)], inventory),
            {"box": 3, "whole_box": False, "cards": 1, "bid": bid3},
            "AND ONE OF THE TWO IS NOT THE WHOLE BOX, so the count is the cards rather than "
            "null. This is the arm the path compare could not answer: under a selection the "
            "scan root is `captures/cards` for a press aimed at one drawer, so `capture_dir == "
            "captures/cards/box3` was never going to be true again",
        )
        (own / "0003.jpg").write_bytes(JPEG)
        checks.equal(
            cmd_identify._scope_for([FakeItem(3), FakeItem(3)], inventory)["whole_box"],
            False,
            "and a third photograph appearing in the drawer makes the same two cards NOT the "
            "whole box — the field is about the drawer's contents and says so",
        )
        (own / "0003.jpg").unlink()
        checks.equal(
            cmd_identify._scope_for([FakeItem(3), FakeItem(4)], inventory),
            None,
            "A RUN WHOSE CAPTURES NAME TWO BOXES GETS NO SCOPE RATHER THAN A GUESSED ONE. "
            "That was D180's rule and it is the part of that entry the selection keeps: a scope "
            "naming one of two drawers would be a claim about cards it is wrong about, and "
            "`2026-08-29-box1-01` — 99 cards the path calls box 1, all in box 3 — is the cost",
        )
        checks.equal(
            cmd_identify._scope_for([FakeItem(9)], inventory),
            {"box": 9, "whole_box": False, "cards": 1, "bid": None},
            "and a box the registry has never seen gets a scope with NO id rather than a "
            "refusal — a run with no id is read by the older rule, which is the arm that has "
            "always worked. Its drawer has no directory either, so it is not a whole box: "
            "nothing can say it was",
        )
        checks.equal(
            cmd_identify._scope_for([], inventory),
            None,
            "no captures, no box, no scope",
        )

    # ------------------------------------------------------------------ the warning's figure
    with isolated_home():
        with Store().write() as snapshot:
            snapshot.inventory.ensure_box(1)
            for n in range(1, 5):
                card, _ = snapshot.inventory.allocate_capture(
                    1, capture_id=f"count-{n}", cid=fake_cid(f"count-{n}")
                )
                snapshot.inventory.record_identification(
                    card.key, name="Moonfall", number="198/219",
                    printed_total="219", confidence="high", run="stranded-run",
                )
        with Store().write() as snapshot:
            # Straight at the field: this case is about the COUNT, and `do_mark_sold`'s own
            # refusals and undo are `check_mark_sold`'s subject.
            snapshot.inventory.cards.get("1/4").state = master.SOLD
        counted = pipeline_routes._on_hand_by_run(
            Store().read().inventory, ["stranded-run", "no-such-run"]
        )
        checks.equal(
            counted.get("stranded-run"),
            3,
            "A RUN'S FIGURE IS WHAT THE STORE STILL HOLDS, NOT WHAT THE RUN READ — four cards "
            "identified, one sold, three on hand. Counted off the CARDS because that is the "
            "number a warning about stranded stock has to carry",
        )
        checks.equal(
            counted.get("no-such-run"),
            None,
            "and a run holding nothing is absent rather than zero, which is what lets the "
            "screen drop a false alarm without dropping a card",
        )


def check_printed_code_profiles(checks: Checks) -> None:
    """`riftbound_card_v1` and `one_piece_card_v1`: the wiring, and the one seam that lies.

    WHAT THIS ASSERTS AND WHAT IT CANNOT. It asserts that a model answer shaped like these
    two profiles' schemas survives every hop between the API and a catalog row — the
    parser, the raw payload written into `identifications.json`, `cli/resolve.py`'s read of
    that payload, the per-game join key, and the fold on both sides of the match. It says
    NOTHING about whether a model can read a Riftbound or One Piece card, because this
    repo holds no photograph of either: there is no eval set, no T1 score, and no accuracy
    figure for either profile. Same standing as T6's synthetic composites — self-consistent
    over a wider range than the evidence covers.

    THE SEAM THAT LIES IS THE FIELD NAME, and it is why this section reaches all the way to
    a real export instead of stopping at `parse`. `cli/resolve.py` reads the RAW model
    payload back out of the run — `identification.get("number")` — and never calls
    `prompt.parse`. So a schema that called this field `printed_code`, or copied misc's
    `printed_id`, would parse perfectly, write a perfectly good record, and then hand the
    join a card with no number at all: every card in the run back as `no_catalog_row`,
    blaming the export. Nothing short of the round trip below can see that, and the
    temptation to rename the field is permanent, because `printed_code` is what the
    registry's `join_key` calls the same idea one file over.

    THE EXPORTS ARE THE REAL ONES AND THE PRICES ARE WHY. Every identifier below is a cell
    that exists, and the pairs are chosen so that dropping a single character lands on a
    different real SKU at a different real price: `066a/298` ($8.89) against `066/298`,
    `303*/298` ($3,420.28) against `303/298` ($384.31). An invented fixture would assert
    that this code is consistent with itself.
    """
    checks.note("")
    checks.note("PRINTED-CODE PROFILES — identify/prompt.py, cli/resolve.py, the join key")

    # ------------------------------------------------- the registry <-> profile seam
    #
    # BOTH DIRECTIONS, because the two files are reconciled at import in one direction only
    # (a registry name with no profile stops the process; a profile no entry names does
    # not). The half that is not checked at import is the half asserted here: the entry
    # still names the profile that was written FOR it.
    for game, strategy in (
        ("riftbound", "riftbound_card_v1"),
        ("one_piece", "one_piece_card_v1"),
    ):
        entry = games.get(game)
        checks.equal(
            entry["prompt"],
            strategy,
            f"the {game} registry entry names {strategy} — it said `unwritten` until "
            "2026-08-23, and asking for it refused rather than reading the card with "
            "another game's prompt",
        )
        chosen = prompt.profile(strategy)

        # D3 rung 3's enum, PER GAME. `variant.FINISHES` is Pokemon's three, and reading it
        # for another game was a real bug fixed in four places on 2026-08-23. Asserted as an
        # exact set rather than by naming `normal`/`foil`, so that widening the registry
        # entry widens this without anyone remembering to.
        offered = chosen.schema["properties"]["finish"]["enum"]
        checks.equal(
            sorted(offered),
            sorted(set(entry["finishes"]) | {prompt.UNKNOWN_FINISH}),
            f"{strategy}'s finish enum is exactly {game}'s own finishes plus `unknown` — "
            "read from the registry entry, never from variant.FINISHES",
        )
        checks.ok(
            not ({"holo", "reverse_holo"} & set(offered)),
            "and it offers no Pokemon-only finish: a `reverse_holo` here would be a "
            "condition string neither game's export carries",
            f"enum was {offered!r}",
        )
        # The prompt text and the schema enum are two statements of one fact, and only the
        # schema is machine-read. A finish the model is allowed to return but is never told
        # about is a member nothing will ever produce.
        for finish in entry["finishes"]:
            checks.ok(
                f"\n  {finish}" in chosen.system,
                f"and {game}'s `{finish}` is described in the system prompt as well as "
                "allowed by the schema — an enum member the prompt never mentions is a "
                "member the model has no reason to choose",
                f"not found in {strategy}'s system prompt",
            )

        # THE FIELD NAME, asserted at the schema before the round trip asserts it in anger.
        checks.equal(
            sorted(chosen.schema["required"]),
            ["confidence", "finish", "name", "number"],
            f"{strategy} asks for FOUR fields and calls the identifier `number` — the key "
            "cli/resolve.py reads off the raw payload",
        )
        checks.ok(
            "printed_total" not in chosen.schema["properties"],
            "and `printed_total` is absent rather than blank: a game keyed by "
            "printed_code has no denominator half, and _key_printed_code never reads "
            "one in either direction",
            f"properties were {sorted(chosen.schema['properties'])!r}",
        )

        # D23's clause lost its A/B on Pokemon for $0.17 and is off in production; shipping
        # it new on a game with no eval set would be unmeasurable by construction. Asserted
        # through `user_text` rather than only on the field, because the field is only half
        # the promise — the other half is that a claim supplied anyway renders nothing.
        checks.equal(chosen.rarity_clause, "", f"{strategy} carries no rarity clause")
        checks.equal(
            prompt.user_text(rarity_claim=("Common", "Rare"), strategy=strategy),
            chosen.user,
            "and a rarity claim supplied anyway renders NOTHING — the turn is byte-for-"
            "byte the unclaimed one",
        )
        # `crop_bands: ()` — nobody has measured where either game puts a title or a
        # number, so the retry turn must not name a band the cropper will never cut.
        checks.equal(tuple(entry["crop_bands"]), (), f"{game} claims no crop bands")
        for band in ("title band", "collector number", "number is printed"):
            checks.ok(
                band not in chosen.user_with_crops,
                f"and {strategy}'s crop-retry turn does not name a `{band}` it cannot "
                "be sent — it describes enlarged views of the same card and nothing more",
                f"turn was: {chosen.user_with_crops!r}",
            )

    # `unwritten` NAMES NOBODY NOW AND STILL REFUSES. This is the case that stops a later
    # session deleting the strategy as dead: it is what the NEXT game registered here lands
    # on, and its refusal is the only thing between that game and Pokemon's contract.
    checks.ok(
        all(entry["prompt"] != prompt.UNWRITTEN for entry in games.GAMES),
        "no registry entry names `unwritten` any more",
        f"still named by: {[e['key'] for e in games.GAMES if e['prompt'] == prompt.UNWRITTEN]!r}",
    )
    checks.equal(
        prompt.PROFILES.get(prompt.UNWRITTEN, "missing"),
        None,
        "and it is kept anyway, mapped to None — the honest value for the next game, "
        "unlike `operator_note`, which named a state the product does not have and was "
        "deleted",
    )
    refusal = checks.raises(
        prompt.UnwrittenPrompt,
        lambda: prompt.profile(prompt.UNWRITTEN),
        "asking for it still refuses BY NAME rather than falling through",
    )
    if refusal is not None:
        checks.ok(
            "do not read this game with another game's prompt" in str(refusal),
            "and the refusal still says what the alternative would cost",
            f"message was: {refusal}",
        )

    # ------------------------------------------------------ the parsers, field by field
    #
    # `066a/298` and `T02 // T03` are the two shapes a fold or a tidy-up would break, and
    # both are asserted through `parse` rather than by reading the schema: the parser is
    # where a later session would reach for `normalize_number`, which upper-cases and
    # strips a leading `#`.
    riftbound_read = prompt.parse(
        {
            "name": "Ahri, Alluring",
            "number": "066a/298",
            "finish": "foil",
            "confidence": "high",
        },
        "riftbound_card_v1",
    )
    checks.equal(
        [riftbound_read.name, riftbound_read.number, riftbound_read.printed_total],
        ["Ahri, Alluring", "066a/298", ""],
        "the identifier lands WHOLE in `number`, case and letter suffix untouched, and "
        "`printed_total` is empty — a half this game does not have rather than one we "
        "failed to read",
    )
    checks.equal(
        riftbound_read.detected_finish,
        "foil",
        "and `foil` survives the parser's whitelist, which is this game's enum and not "
        "Pokemon's",
    )
    checks.equal(
        riftbound_read.has_number,
        False,
        "has_number is False, which is the honest answer to the question it asks: no "
        "number/total key CAN be built for a printed_code game",
    )
    checks.equal(
        prompt.parse(
            {
                "name": "Bird // Buff",
                "number": "T02 // T03",
                "finish": "unknown",
                "confidence": "medium",
            },
            "riftbound_card_v1",
        ).number,
        "T02 // T03",
        "a double-sided token keeps the SPACES around its `//` — number_index_key folds "
        "zeros and case and nothing else, so `T02//T03` would fold to `T2//T3` and match "
        "nothing",
    )
    checks.equal(
        prompt.parse(
            {"name": "x", "number": "y", "finish": "unknown", "confidence": "low"},
            "one_piece_card_v1",
        ).detected_finish,
        None,
        "`unknown` maps to None — D3's no-signal case, not a manufactured disagreement",
    )
    checks.equal(
        prompt.parse(
            {
                "name": "Monkey.D.Luffy",
                "number": "ST26-005",
                "finish": "foil",
                "confidence": "high",
            },
            "one_piece_card_v1",
        ).name,
        "Monkey.D.Luffy",
        "and a dotted, unspaced One Piece name survives verbatim — normalize_name folds "
        "case, accents, apostrophes and dashes and does NOT fold a full stop, so a "
        "respaced `Monkey D. Luffy` would never compare equal to what the card prints",
    )
    for strategy in ("riftbound_card_v1", "one_piece_card_v1"):
        checks.raises(
            prompt.MalformedIdentification,
            lambda s=strategy: prompt.parse(
                {
                    "name": "x",
                    "number": "y",
                    "finish": "reverse_holo",
                    "confidence": "high",
                },
                s,
            ),
            f"{strategy} REFUSES a Pokemon finish rather than dropping it to None — a "
            "silent drop here would lose rung 3's cross-check with nothing on screen",
        )
        checks.raises(
            prompt.MalformedIdentification,
            lambda s=strategy: prompt.parse(
                {"name": "x", "number": "y", "finish": "normal", "confidence": "sure"}, s
            ),
            "and an out-of-enum confidence too — routing reads that field",
        )
        checks.raises(
            prompt.MalformedIdentification,
            lambda s=strategy: prompt.parse(
                {"name": "x", "printed_code": "y", "finish": "normal", "confidence": "high"},
                s,
            ),
            "and a payload naming the identifier `printed_code` is a MISSING KEY, loudly "
            "— never a card read with an empty number",
        )

    # ------------------------------ the round trip: raw payload -> resolve -> a real row
    #
    # THE CASE THIS SECTION EXISTS FOR. The payload written into `identifications.json` is
    # `Identification.raw` — the model's own keys — and `cli/resolve.py` reads them back
    # without parsing. Every pair below is chosen so that one dropped character lands on a
    # different real SKU: the fold forgives zero padding and case and forgives nothing else.
    plans = (
        (
            "riftbound",
            RIFTBOUND_EXPORT,
            (
                ("066a/298", "Ahri, Alluring", "foil"),
                # The same card written unpadded. number_index_key strips leading zeros
                # from every digit run on BOTH sides, so this must aggregate onto the SKU
                # above rather than miss — which is why neither prompt demands padding.
                ("66a/298", "Ahri, Alluring", "foil"),
                ("303*/298", "Ahri, Nine-Tailed Fox", "foil"),
            ),
            {
                "8926002": ("066a/298", "Near Mint Foil", 2),
                "8927897": ("303*/298", "Near Mint Foil", 1),
            },
        ),
        (
            "one_piece",
            ONE_PIECE_EXPORT,
            (
                ("OP15-079", "Absalom", "normal"),
                ("op15-79", "Absalom", "normal"),
                ("P-105", "Sabo", "foil"),
            ),
            {
                "9196764": ("OP15-079", "Near Mint", 2),
                "9194101": ("P-105", "Near Mint Foil", 1),
            },
        ),
    )
    for game, export, reads, expected in plans:
        strategy = str(games.get(game)["prompt"])
        with isolated_home() as home:
            run = runs.Run(directory=home, manifest={})
            cards = {}
            for index, (number, name, finish) in enumerate(reads, start=1):
                parsed = prompt.parse(
                    {
                        "name": name,
                        "number": number,
                        "finish": finish,
                        "confidence": "high",
                    },
                    strategy,
                )
                cards[f"7/{index}"] = {
                    "box": 7,
                    "index": index,
                    "game": game,
                    "photo": f"captures/box7/{index:04d}.jpg",
                    # RAW, exactly as `cli/cmd_identify.py` writes it: `item.identification
                    # = dict(outcome.identification.raw)`. Writing the parsed fields here
                    # instead would test a seam the pipeline does not have.
                    "identification": dict(parsed.raw),
                }
            run.write_identifications({"cards": cards})
            report = resolve.load(run, {game: Path(export)}).joins[game].report

        checks.equal(
            report.cards_in, len(reads), f"{game}: every card reached the {game} catalog"
        )
        checks.equal(
            {
                sku: (
                    match.row[tcgcsv.NUMBER_COLUMN],
                    match.condition,
                    len(match.positions),
                )
                for sku, match in report.matches.items()
            },
            expected,
            f"{game}: the model's raw `number` reached a REAL export row through "
            "cli/resolve.py without being parsed on the way — the seam that would have "
            "silently returned no_catalog_row for the whole run if this field were named "
            "`printed_code`",
        )

    # The negative that gives the round trip its meaning: one character dropped is a
    # different card at a different price, and the pipeline does not smooth it over.
    with isolated_home() as home:
        run = runs.Run(directory=home, manifest={})
        run.write_identifications(
            {
                "cards": {
                    f"8/{index}": {
                        "box": 8,
                        "index": index,
                        "game": "riftbound",
                        "photo": f"captures/box8/{index:04d}.jpg",
                        "identification": dict(
                            prompt.parse(
                                {
                                    "name": "Ahri, Nine-Tailed Fox",
                                    "number": number,
                                    "finish": "foil",
                                    "confidence": "high",
                                },
                                "riftbound_card_v1",
                            ).raw
                        ),
                    }
                    for index, number in enumerate(("303*/298", "303/298"), start=1)
                }
            }
        )
        starred = resolve.load(run, {"riftbound": RIFTBOUND_EXPORT}).joins["riftbound"]
    prices = {
        match.row[tcgcsv.NUMBER_COLUMN]: match.market_price
        for match in starred.report.matches.values()
    }
    checks.equal(
        sorted(prices),
        ["303*/298", "303/298"],
        "the asterisk is not decoration: `303*/298` and `303/298` are two different real "
        "SKUs and both are found",
    )
    checks.ok(
        prices.get("303*/298") != prices.get("303/298"),
        "and they are not the same card — a model that reads the asterisk as a footnote "
        "mark lands on a real row for a real card that is not the one in its hand",
        f"prices were {prices!r}",
    )

# ---------------------------------------------------------------------- command refusals


def check_cli_refusals(checks: Checks) -> None:
    """Commands refuse and say what to edit. They never ask.

    `cli/__main__.py` opens with the rule: the pipeline runs unattended, so a command that
    cannot proceed refuses rather than prompting. A prompt in this process is not a bad
    user experience, it is a batch run stopped forever with nobody watching.
    """
    checks.note("")
    checks.note("COMMAND REFUSALS — cli/__main__.py")

    from cli import __main__ as entry

    # TEN SINCE 2026-09-12, and `scan` is still the only one that is free AND writes to a
    # CARD. `prices` writes the CORPUS — `prices adopt` previews unless given `--write`, and
    # `prices show` reads. `reprice` writes the corpus too, on `apply --write` and nowhere else
    # (D100); both of its subcommands preview by default, and neither touches a card. `rescue`
    # writes a RUN DIRECTORY on `--write` and nothing else — never the store, and never the run
    # it is given. `queue` is the newest and is the other free writer: `queue refresh`
    # re-resolves every open entry store-wide and rewrites the QUEUES on `--write`, which is a
    # question rather than a price or a copy — it spends no money, moves no quantity, and
    # cannot reach a `cleared_by_human` entry at all. Still an exact match rather than a
    # superset check: the point of this line is that a command cannot appear in the dispatch
    # without somebody editing this list, and a membership test would let one arrive unnoticed
    # — which matters most for a command that touches the store, as `scan` does. It EARNED that
    # twice in one day: `rescue` and `queue` landed hours apart and each side of the merge
    # counted eight.
    #
    # `cards` IS THE TENTH AND IT ARRIVED WITH D172. Two of its three subcommands write
    # nothing ever — `cards name` is a census and `cards audit` asks whether every card's
    # name still resolves to its photograph — and the third, `cards photos`, is the one
    # thing in this dispatch that moves 4.45 GB that cannot be re-taken, previewing by
    # default and verifying every file against a digest before its old copy is removed.
    #
    # `readings` IS THE ELEVENTH, AND IT ARRIVED WITH D189. `readings adopt`
    # writes the cached market-reading table on `--write` and nowhere else, and `readings
    # show` only reads. Unlike every other writer in this list it holds no operator
    # judgement at all — it is a mechanical newest-wins fold of two files already on disk —
    # so it is the one command here that previews by habit rather than because a real
    # decision hides inside it.
    #
    # `archive` IS THE TWELFTH, AND IT ARRIVED WITH D219. `archive
    # sweep` writes the price-history archive on `--write` and nowhere else, and `archive
    # show` only reads. Unlike `readings adopt`, `sweep --write` is never a full replace —
    # a bucket a pass does not mention survives, because the source's own 357-day window
    # means it may be the only copy of that observation left anywhere.
    #
    # `skus` IS THE THIRTEENTH, AND IT ARRIVED WITH LANE 0 OF
    # `docs/specs/identity-follows-sku.md` (owner's ruling, 2026-09-24: "yes I'd been saying
    # we build this"). `skus adopt` writes the store-owned SKU table on `--write` and
    # nowhere else. Unlike every other writer here, it never fully replaces and never
    # deletes — `store/skus.py`'s own argument, `price_history`'s shape and not
    # `readings`'s — so a SKU an export no longer lists keeps its row.
    checks.equal(
        sorted(entry.COMMANDS),
        ["archive", "boxes", "cards", "emit", "identify", "join", "match", "prices", "queue",
         "readings", "reconcile", "reprice", "rescue", "scan", "skus"],
        # `boxes` IS THE FOURTEENTH (D259): `boxes names` gives every
        # unnamed box its stored default name. Previews by default; `--write` is one transaction.
        # `match` IS THE FIFTEENTH (D2, the owner picks the engine): `match status` is free and
        # `match prepare` is the free reader's one-time setup. Nothing starts it but the owner's press.
        "fifteen commands are registered, and only fifteen",
    )

    # No command may read stdin. Asserted against the source of every module the dispatch
    # can reach, because the failure is not visible until an unattended run hangs.
    root = REPO_ROOT
    prompting = []
    for module in sorted((root / "cli").glob("*.py")):
        text = module.read_text("utf-8")
        for needle in ("input(", "getpass", "sys.stdin.read"):
            if needle in text:
                prompting.append(f"{module.name}: {needle}")
    checks.equal(prompting, [], "no command reads from stdin — NO INTERACTIVE PROMPTS, ever")

    with isolated_home():
        missing = Path(files.home()) / "no-such-run"
        for argv, label in (
            (["join", str(missing)], "join"),
            (["emit", str(missing)], "emit"),
            (["reconcile", str(missing), str(missing / "staged.csv")], "reconcile"),
        ):
            with quiet() as said:
                code = entry.main(argv)
            checks.equal(code, 1, f"{label} on an absent run directory exits 1, never raises")
            checks.ok(
                str(missing) in said.getvalue(),
                f"and {label} names the path it could not use",
                f"said: {said.getvalue().strip()!r}",
            )

    # A MANIFEST WHOSE EXPORT HAS GONE. `2026-08-22-box1-03` recorded its export under
    # `~/Downloads`, where it no longer is, and the refusal said `export not found: <path>`
    # and nothing else — the one `exports_for` refusal with no remedy in it, beside three
    # siblings that each name what to do next.
    with isolated_home() as home:
        gone = runs.create("gone-export")
        gone.write_identifications({"prompt_fingerprint": "t7", "cards": {}})
        gone.set(exports={"pokemon": {"path": str(home / "Downloads" / "export.csv")}})
        with quiet() as said:
            code = entry.main(["join", str(gone.directory)])
        checks.equal(code, 1, "join over a manifest whose recorded export is gone exits 1")
        text = said.getvalue()
        checks.ok(
            "--export" in text and "#/runs" in text and "manifest" in text,
            "and the refusal says the manifest recorded it, and names both remedies — "
            "`--export` and the fetch on #/runs",
            f"said: {text.strip()!r}",
        )

    # argparse exits 2 on a usage error, and that is the right code — it is a different
    # failure from a run that could not proceed, and a caller scripting these needs to tell
    # them apart.
    for argv, label in (
        ([], "no subcommand"),
        (["join", "run", "--basis", "nonsense"], "an invalid --basis choice"),
    ):
        try:
            with quiet():
                entry.build_parser().parse_args(argv)
            checks.ok(False, f"{label} is refused by the parser", "parsed without error")
        except SystemExit as caught:
            checks.equal(caught.code, 2, f"{label} exits 2 (usage), not 1")

    # ---------------------------------- `identify` WITH NO PATH IS NO LONGER A USAGE ERROR
    #
    # AND THAT IS THE ONE THING THIS CHANGE COULD HAVE DONE QUIETLY. `capture_dir` was a
    # required positional, so `./banchi identify "$DIR"` with `$DIR` unset exited 2 from
    # argparse; under `nargs="*"` it is an empty list, which is a selection naming nothing,
    # which is EVERY PHOTOGRAPH IN THE STORE — a paid store-wide submission from a typo.
    #
    # THE GUARD MOVED RATHER THAN GOING, and it moved a layer down because that is where the
    # question can be asked at all: argparse cannot see that `--box 3` also names cards. So the
    # command refuses a selection that names NOTHING unless `--all` is typed, and exits 1 —
    # a refusal to proceed, which is a different failure from a usage error and scripts need
    # to tell them apart. The screen does not refuse it: it has the free preflight and a
    # confirm in front of it, and a terminal has a newline.
    with isolated_home():
        parsed = entry.build_parser().parse_args(["identify"])
        checks.equal(
            (parsed.capture_dir, getattr(parsed, "all", None)),
            ([], False),
            "`identify` with no path PARSES now — the positional is a list, and the refusal "
            "below is a layer down where the selection flags can be seen too",
        )
        with quiet() as said:
            code = entry.main(["identify", "--engine", "haiku"])
        checks.equal(code, 1, "and naming nothing exits 1 — a refusal, not a usage error")
        checks.ok(
            "--all" in said.getvalue(),
            "NAMING THE FLAG, which is the whole of the guard: the operator is told the word "
            "to type rather than left to discover that silence meant everything",
            f"said: {said.getvalue().strip()!r}",
        )
        with quiet() as said:
            code = entry.main(["identify", "--all", "--dry-run", "--engine", "haiku"])
        checks.equal(
            code,
            1,
            "and `--all` over an EMPTY store is refused as an empty selection rather than "
            "submitting nothing and reporting success",
        )


def check_identify_dry_run_is_cheap_and_never_under(checks: Checks) -> None:
    """Check cost (`identify --dry-run`) decodes nothing, never quotes under the real send,
    and a keyed selection reads only its own sidecars.

    THE MONEY GATE. The preflight is the quote the operator confirms a paid press against, so
    the estimate may be cheaper to make than the real send but never smaller than it. Measured:
    a dry run decodes and crops every photograph just to quote a cost (15.6 to 19.8 s).
    Three claims, one fixture: 4 large photographs in box 5, 26 small ones in box 6.
    """
    import base64
    import io
    import random
    from decimal import Decimal

    from cli import __main__ as cli_entry
    from cli import cmd_identify
    from identify import images as identify_images

    checks.note("")
    checks.note("IDENTIFY DRY RUN: decodes nothing, never under the real send, reads its own sidecars")

    minted = iter(range(10_000))

    def jpeg(size):
        rng = random.Random(next(minted))
        block = [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(size[0] * size[1] // 16)]
        image = identify_images.Image.new("RGB", size)
        image.putdata((block * 16)[: size[0] * size[1]])
        out = io.BytesIO()
        image.save(out, "JPEG", quality=90)
        return base64.b64encode(out.getvalue()).decode("ascii")

    def line(lines, prefix):
        return next((x for x in lines if x.startswith(prefix)), "")

    with isolated_home():
        for _ in range(4):
            capture_server.do_capture({"box": 5, "image": jpeg((1900, 2600))})
        for _ in range(26):
            capture_server.do_capture({"box": 6, "image": jpeg((120, 168))})

        # The legacy root exists on every real store; `Selection.roots` lists it first and the
        # command refuses a root that is missing, so the fixture makes it.
        files.home().joinpath("captures", "cards").mkdir(parents=True, exist_ok=True)

        decoded: list = []
        real_prepare = cmd_identify.images.prepare
        real_located = cmd_identify.images.prepare_located

        def counting_prepare(path, **kwargs):
            decoded.append(str(path))
            return real_prepare(path, **kwargs)

        def counting_located(path, **kwargs):
            decoded.append(str(path))
            return real_located(path, **kwargs)

        reads: list = []
        real_read = sidecar.read_sidecar

        def counting_read(path):
            reads.append(str(path))
            return real_read(path)

        sent_bytes: list = []

        def fake_run_batch(requests, log=None, on_submit=None):
            sent_bytes.extend(len(base64.b64decode(r.data_b64)) for r in requests)
            return batch.BatchRun(outcomes={})

        real_run_batch = cmd_identify.batch.run_batch
        cmd_identify.images.prepare = counting_prepare
        cmd_identify.images.prepare_located = counting_located
        sidecar.read_sidecar = counting_read
        cmd_identify.batch.run_batch = fake_run_batch
        try:

            def press(*extra):
                lines: list = []
                with quiet():
                    cmd_identify.run(
                        cli_entry.build_parser().parse_args(
                            ["identify", "--engine", "haiku", "--crop", *extra]
                        ),
                        lines.append,
                    )
                return lines

            # 1. a dry run decodes nothing
            dry = press("--box", "5", "--dry-run")
            checks.equal(
                len(decoded),
                0,
                "A DRY RUN DECODES NOTHING: it quotes from a payload size estimated off the "
                "file, not from a decode-and-crop pass over every photograph",
            )
            checks.ok("to send         4" in dry, "and the dry run still counts 4 to send", f"{dry}")

            # 2. the quote is never under what a real send builds
            real = press("--box", "5")
            real_bytes = sum(sent_bytes)
            checks.ok(
                len(sent_bytes) == 4 and real_bytes > 0,
                "the real send builds 4 requests",
                f"{sent_bytes}",
            )
            quoted = Decimal(line(dry, "estimated cost").split("$")[-1] or "0")
            truth = Decimal(line(real, "estimated cost").split("$")[-1] or "0")
            checks.ok(
                quoted >= truth,
                "THE DRY-RUN COST IS NEVER UNDER THE REAL SEND'S COST",
                f"dry ${quoted} < real ${truth}",
            )
            mb = float(line(dry, "payload").split()[1])
            checks.ok(
                mb >= round(real_bytes / 1_000_000, 1),
                "and the dry-run payload is never under the bytes the real send builds",
                f"dry {mb} MB < real {real_bytes} bytes",
            )

            # 3. a keyed selection reads only its own sidecars
            reads.clear()
            keys = ["6/1", "6/2"]
            press(*[a for k in keys for a in ("--keys", k)], "--dry-run")
            checks.ok(
                0 < len(reads) <= len(keys) + 2,
                "A KEYED SELECTION READS ABOUT k SIDECARS, NEVER N",
                f"read {len(reads)} sidecars for {len(keys)} keys in a store of 30",
            )
        finally:
            cmd_identify.images.prepare = real_prepare
            cmd_identify.images.prepare_located = real_located
            sidecar.read_sidecar = real_read
            cmd_identify.batch.run_batch = real_run_batch


def check_run_and_preview_share_locate_card(checks: Checks) -> None:
    """D125: a paid run and the crop preview cut with `identify.images.prepare_located`.

    The finder is stubbed, never the model: `locate_card` answers a dfine box we choose and
    `detect_card` answers a different one, so each assertion names which finder it reached.
    The batch is faked, so nothing is paid for.
    """
    from unittest import mock

    from PIL import ImageDraw

    from cli import __main__ as cli_entry
    from cli import cmd_identify
    from identify import images
    from server import pipeline_routes

    geo = images.geometry
    size = (1500, 2600)
    base = dict(angle=0.0, fill=1.0, aspect=0.714)
    # A card-shaped box that IS the card, and one cut out of its flat interior (refused).
    good = dict(left=0.2, top=0.19, right=0.87, bottom=0.73)
    inner = dict(left=0.35, top=0.40, right=0.45, bottom=0.52)

    def photograph(path):
        frame = images.Image.new("RGB", size, (26, 28, 32))
        ImageDraw.Draw(frame).rectangle((300, 500, 1300, 1896), fill=(238, 232, 214))
        frame.save(path, format="JPEG", quality=92)

    def fake_run_batch(requests, log=None, on_submit=None):
        return batch.BatchRun(
            outcomes={
                r.custom_id: batch.Outcome(
                    r.custom_id,
                    batch.SUCCEEDED,
                    identification=prompt.parse(
                        {
                            "name": "Pikachu",
                            "number": "025",
                            "printed_total": "102",
                            "finish": "normal",
                            "confidence": "high",
                        },
                        r.strategy,
                    ),
                )
                for r in requests
            }
        )

    def scenario(located, detected):
        """-> (box the run cut with, the preview's sample, the frame's box)."""
        cut: list = []
        real_prepare = images.prepare

        def spying_prepare(path, **kwargs):
            cut.append(kwargs.get("crop_box"))
            return real_prepare(path, **kwargs)

        with isolated_home() as home:
            caps = Path(home) / "captures" / "cards" / "box3"
            caps.mkdir(parents=True)
            photograph(caps / "0001.jpg")
            (caps / "0001.json").write_text(
                json.dumps({"box": 3, "index": 1, "position": 1, "game": "pokemon"}), "utf-8"
            )
            with mock.patch.object(geo, "locate_card", lambda *a, **k: located), mock.patch.object(
                geo, "detect_card", lambda *a, **k: detected
            ), mock.patch.object(cmd_identify.batch, "run_batch", fake_run_batch), mock.patch.object(
                images, "prepare", spying_prepare
            ):
                with quiet():
                    code = cmd_identify.run(
                        cli_entry.build_parser().parse_args(["identify", str(caps), "--crop", "--engine", "haiku"]),
                        lambda line: None,
                    )
                checks.equal(code, 0, "the run exits 0")
                run_cut = list(cut)  # the run's calls only; the preview's come after
                sample = pipeline_routes.do_pipeline_crop_preview(
                    {"box": 3, "crop": True, "max_edge": 1200}
                )["sample"]
            return run_cut, sample

    # 1. The run cuts at locate_card's dfine box, padded 4% a side.
    dfine = geo.CardBox(method="dfine", **base, **good)
    tone = geo.CardBox(method="tone", **base, left=0.25, top=0.21, right=0.83, bottom=0.71)
    cut, sample = scenario(dfine, tone)
    checks.equal(
        [b.method for b in cut if b is not None],
        ["dfine"],
        "a run crops with locate_card's box: the one prepare call carries the dfine box, "
        "not detect_card's",
    )
    cw, ch = (good["right"] - good["left"]) * size[0], (good["bottom"] - good["top"]) * size[1]
    left, top, right, bottom = images.crop_rect(size, cut[-1])
    checks.ok(
        abs((right - left) - cw * 1.08) < 2 and abs((bottom - top) - ch * 1.08) < 2,
        "and it cuts at that rect with the 4% dfine pad a side",
        f"{right - left:.0f}x{bottom - top:.0f} against {cw * 1.08:.0f}x{ch * 1.08:.0f}",
    )
    # 3. The preview draws the rect the run cut.
    checks.equal(
        tuple(sample["rect"]),
        (left, top, right, bottom),
        "the preview's rect equals the run's crop_rect for the same photograph",
    )
    checks.equal(sample["method"], "dfine", "and the preview names the same finder")

    # 2. A refused dfine box falls back to detect_card's box, in the run and the preview.
    bad = geo.CardBox(method="dfine", **base, **inner)
    probe = images.Image.new("RGB", size, (26, 28, 32))
    ImageDraw.Draw(probe).rectangle((300, 500, 1300, 1896), fill=(238, 232, 214))
    checks.ok(
        images.crop_refusal(probe, bad) is not None and images.crop_refusal(probe, tone) is None,
        "fixture: the dfine box is refused and the fallback box is accepted",
    )
    cut, sample = scenario(bad, tone)
    checks.ok(
        bool(cut) and cut[-1] is not None and cut[-1].method == "tone",
        "a refused dfine box falls back: the run's last cut is detect_card's box",
        str([b and b.method for b in cut]),
    )
    checks.equal(
        (sample["method"], tuple(sample["rect"] or ())),
        ("tone", tuple(images.crop_rect(size, tone))),
        "and the preview ends on detect_card's box and rect too",
    )


CHECKS = (
    check_cli_seams,
    check_code_ledger,
    check_identify_preflight_stage,
    check_identify_dry_run_is_cheap_and_never_under,
    check_run_and_preview_share_locate_card,
    check_review_stand_down,
    check_review_catalog,
    check_correct_answer,
    check_correct_answer_live_release,
    check_identity_binding,
    check_catalog_number_fields_round_trip,
    check_catalog_set_rarity_match,
    check_catalog_claim_rank_and_no_cutoff,
    check_run_realignment,
    check_reused_box_refusal,
    check_box_true_index,
    check_emit_buried_box,
    check_rescue_stranded_run,
    check_rescue_discharges_stranded_count,
    check_rescue_route,
    check_rescue_json_reasons,
    check_store_backed_join,
    check_run_binds_to_bid,
    check_printed_code_profiles,
    check_cli_refusals,
)
