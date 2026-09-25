"""Argument parsing and dispatch. Every default here is a number from the spec, not a taste.

NO INTERACTIVE PROMPTS, anywhere, ever. The pipeline has to run unattended, so a command
that cannot proceed refuses and says what to edit — it never asks. That is why the pricing
decision is a file: a question you can answer later is compatible with an unattended run in
a way that a question you must answer now is not.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cli import (  # noqa: E402
    cmd_boxes,
    cmd_cards,
    cmd_emit,
    cmd_identify,
    cmd_join,
    cmd_pricearchive,
    cmd_prices,
    cmd_queue,
    cmd_readings,
    cmd_reconcile,
    cmd_reprice,
    cmd_rescue,
    cmd_scan,
    cmd_skus,
    runs,
)
from identify import images  # noqa: E402
from pipeline import pricing, reprice as reprice_rules, routing, variant  # noqa: E402
from store import files as store_files  # noqa: E402


def _say(message: str = "") -> None:
    print(message)


def _pricing_arguments(parser: argparse.ArgumentParser) -> None:
    """Shared by join and emit. emit prefers what the manifest recorded; these are seeds."""
    parser.add_argument(
        "--export",
        action="append",
        help="TCGplayer Filtered CSV (All Printings). Repeatable, one file per game: "
        "each file answers for the games its own Product Line column carries — never "
        "its filename. Recorded per game in the manifest by `join`.",
    )
    parser.add_argument(
        "--rule",
        default=pricing.RULE_MATCH,
        help="match | undercut:PCT | markup:PCT  (default: match)",
    )
    parser.add_argument(
        "--basis",
        default=pricing.BASIS_MARKET,
        choices=list(pricing.BASES),
        help="which column the rule is applied to (default: market). The D9 threshold "
        "always reads TCG Market Price regardless.",
    )
    parser.add_argument(
        "--review-below-confidence",
        default=routing.CONFIDENCE_LOW,
        choices=list(routing.REVIEW_BELOW_CHOICES),
        help="route resolved cards at or below this confidence to a queue "
        "(default: low; `none` disables confidence routing)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pkmnscan",
        description="Bulk-list Pokemon TCG singles on TCGplayer. Batch script v2.",
        epilog=f"store: ${store_files.HOME_ENV} or the repo root",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ----------------------------------------------------------------------------- scan
    #
    # BEFORE `identify` IN THIS FILE BECAUSE IT COMES BEFORE IT IN THE WORK, and because a
    # reader scanning the subcommand list should meet the free one first. For code cards it
    # is not merely first, it is usually the whole of identification: the QR carries the
    # redemption code, so there is nothing left for a model to read.
    scan = sub.add_parser(
        "scan",
        help="read the QR codes off a directory of code-card photos. FREE — no model call.",
    )
    scan.add_argument("capture_dir", help="directory of photos + JSON sidecars")
    scan.add_argument(
        "--box",
        type=int,
        help="box number for photos whose sidecar and filename carry none",
    )
    scan.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be written to the ledger and write nothing",
    )

    # ------------------------------------------------------------------------- identify
    identify = sub.add_parser(
        "identify", help="submit, wait, collect, cache. THE ONE THAT COSTS MONEY."
    )
    # THE POSITIONAL IS A LIST NOW, AND IT MEANS EXACTLY WHAT IT ALWAYS MEANT: the positions
    # whose photographs are under these paths, resolved through `sidecar.scan` unchanged. What
    # is new is that there may be none of them, in which case the selection flags below say
    # which cards — and `--all` says every one in the store.
    #
    # `nargs="*"` IS WHY `--all` HAS TO EXIST. `./pkmnscan identify "$DIR"` with `$DIR` unset was
    # an argparse error and is now an empty list, so the one thing this change could quietly do
    # is turn a typo into a paid store-wide submission. It refuses instead and names the flag.
    identify.add_argument(
        "capture_dir",
        nargs="*",
        help="directories of photos + JSON sidecars. Omit to select with the flags below.",
    )
    identify.add_argument(
        "--all",
        action="store_true",
        help="every photograph in the store. Required to say so: with no paths and no "
        "selection flag this command refuses rather than submitting everything.",
    )
    # ------------------------------------------------------- the selection (D180)
    #
    # ONE OBJECT, AND `pipeline/selection.py` IS THE READER FOR BOTH SURFACES. Every flag here
    # is a name the store already has for a group of cards, and every one NARROWS — so the order
    # they are given in cannot change the answer.
    identify.add_argument(
        "--state",
        help="only cards the store has in this state (captured, identified, sold, retired, "
        "moved). `captured` is the cards that have never been identified.",
    )
    # REPEATABLE AND COMMA-SPLIT, because one press on this store has named three drawers
    # (2026-09-01: boxes 3, 4 and 5 in one send). A filter naming three values is still one
    # selection and one run — which is less work than the three runs that press produced.
    identify.add_argument(
        "--box",
        action="append",
        help="only cards whose SIDECAR records this box (not the path). Comma-separated or "
        "repeatable, so `--box 3,5` is one selection over two drawers.",
    )
    identify.add_argument(
        "--bid",
        action="append",
        help="only cards in the drawer with this true index (D145) — fixed at creation and "
        "never handed back out, unlike the box number. Comma-separated or repeatable.",
    )
    identify.add_argument(
        "--section",
        type=int,
        help="only cards between these dividers in the box (D10). Needs --box or --bid.",
    )
    identify.add_argument("--game", help="only cards claiming this game (D21)")
    identify.add_argument(
        "--since",
        help="only cards captured at or after this ISO-8601 instant — the sitting, as a bound",
    )
    identify.add_argument(
        "--keys",
        action="append",
        help="only these cards, as `box/index` position keys, comma-separated. Repeatable.",
    )
    identify.add_argument(
        "--run", help="only the cards this run's own answers name"
    )
    identify.add_argument(
        "--crop",
        action="store_true",
        help="crop each photo to the detected card before downscaling. Local and free "
             "(geometry.detect_card, no model call); a frame where detection refuses is "
             "sent whole. Spends the pixel budget on the card instead of the desk.",
    )
    identify.add_argument("--label", help="run label (default: the capture dir's name)")
    identify.add_argument(
        "--run-dir", help="resume into an existing run instead of creating one"
    )
    # RENAMED FROM `--box`, AND IT IS NOT THE SAME JOB WEARING A LONGER NAME. This FILLS a gap:
    # `sidecar.scan(box=...)` supplies a box for a photograph whose sidecar and filename carry
    # none, which is the no-card-is-lost path for a pile somebody dropped on the desk. `--box`
    # above FILTERS on what each capture recorded. Two opposite jobs under one name is how a
    # press aimed at box 3 quietly relabels an unpositioned photograph as box 3 — so the fill
    # keeps the verb and the filter keeps the noun.
    #
    # IT HAS FIRED ON 0 OF 2,535 CAPTURES on the operator's store (measured 2026-09-12: every
    # one resolved from a sidecar, none from a filename and none from nowhere). It is kept for
    # the pile the store has never seen, which is the one case that cannot be recovered any
    # other way.
    identify.add_argument(
        "--assume-box",
        type=int,
        dest="assume_box",
        help="box number for photos whose sidecar and filename carry NONE. Fills gaps; it is "
        "not a filter — see --box.",
    )
    identify.add_argument(
        "--variant",
        choices=list(variant.FINISHES),
        help="finish for photos whose sidecar records none. FILLS GAPS ONLY — a recorded "
        "capture toggle is never overridden (D3 rung 1). For a directory with no sidecars "
        "at all, which is every directory until the capture app exists.",
    )
    identify.add_argument(
        "--max-edge",
        type=int,
        default=images.MAX_EDGE,
        help=f"downscale the longest edge (default: {images.MAX_EDGE}; larger is billed "
        f"and then discarded by the API)",
    )
    identify.add_argument(
        "--retry-budget",
        type=int,
        default=1,
        help="per-card retries after a batch failure or a weak read (default: 1)",
    )
    identify.add_argument(
        "--force-resubmit",
        action="store_true",
        help="pay again for a batch already submitted. Results keep for 29 days, so the "
        "default is to reattach and collect.",
    )
    identify.add_argument(
        "--reidentify-stale",
        action="store_true",
        help="re-read weak, uncleared answers that came from an older prompt",
    )
    identify.add_argument(
        "--dry-run",
        action="store_true",
        help="everything except the API call",
    )

    # --------------------------------------------------------------------------- rescue
    # THE REPAIR FOR A RUN D36 REFUSES. Free, re-runnable and preview-first: it reads
    # photographs and the store, and with `--write` it creates a SECOND run directory. It
    # never edits the run it is given — `cli/runs.py`'s first sentence is that a run is an
    # immutable input — and it refuses a run that is not stranded.
    rescue = sub.add_parser(
        "rescue",
        help="re-address a stranded run's cards to where they are now. Free, previews.",
    )
    rescue.add_argument("run_dir", help="the run a join refuses over a reallocated box")
    rescue.add_argument(
        "--write",
        action="store_true",
        help="create the rescue run. Previews without it, and writes nothing at all.",
    )
    # D210. OFF BY DEFAULT — a terminal's report is unchanged whether or not
    # this is passed. When it is, one extra line of compact JSON is printed alongside the
    # ordinary prose (`_report_line` in cmd_rescue.py), naming the reason code, the counts,
    # the destination and whether an identical rescue already exists — the machine-readable
    # answer `server/pipeline_routes.py:do_run_rescue` reads, in place of matching substrings
    # out of the sentences above it.
    rescue.add_argument(
        "--json",
        action="store_true",
        help="also print one line of machine-readable JSON. The prose is unchanged either way.",
    )

    # ---------------------------------------------------------------------------- boxes
    # A BOX IS SHOWN BY ITS NAME (D-a-box-is-shown-by-its-name). `names` is the one-time
    # backfill that gives every unnamed box the stored name `Box <number>`. Previews by default.
    boxes = sub.add_parser(
        "boxes",
        help="box names: give every unnamed box its stored default name. Previews.",
    )
    boxes_sub = boxes.add_subparsers(dest="boxes_action")
    boxes_names = boxes_sub.add_parser(
        "names",
        help="name every unnamed box `Box <number>`, in one transaction. Previews by default.",
    )
    boxes_names.add_argument(
        "--write", action="store_true", help="actually write; previews without it"
    )

    # ---------------------------------------------------------------------------- cards
    # THE CARD'S STABLE NAME (D172). Two of the three subcommands write nothing EVER, and
    # `name` and `audit` open the store read-only without `db.connect` — that function is
    # the single entry to the store and it always calls `_ensure_schema`, so a preview
    # routed through it would PERFORM the migration it claims to be previewing.
    cards = sub.add_parser(
        "cards",
        help="the card's stable name: preview it, audit it, move the photographs.",
    )
    cards_sub = cards.add_subparsers(
        dest="cards_action",
        metavar="<name|audit|checks|identity|contradictions|sku-names|photos|variants>",
    )
    cards_sub.add_parser(
        "name",
        help="what the naming sees and what it would do. Read-only, writes nothing.",
    )
    cards_audit = cards_sub.add_parser(
        "audit",
        help="does every card's name still resolve to its photograph? Read-only. Three "
        "verdicts: pass, fail, and `not known`.",
    )
    cards_audit.add_argument(
        "--verbose",
        action="store_true",
        help="list the excused cards as well as counting them.",
    )
    cards_checks = cards_sub.add_parser(
        "checks",
        help="four stored-data identification checks (D239): a name too "
        "long to be a name, a denominator that disagrees with its set, more digits than "
        "the set has cards, a name one edit from a sibling in the same set. Read-only "
        "review signals, never repairs, never a catalogue call.",
    )
    cards_checks.add_argument(
        "--verbose",
        action="store_true",
        help="list every flagged card as well as counting them.",
    )
    cards_identity = cards_sub.add_parser(
        "identity",
        help="docs/specs/identity-follows-sku.md §5.5/§7 (lane 2): the migration's own "
        "classifier and the merged `contradictions`/`sku-names` report — every card's "
        "class (T1-T6, sku_unknown), the store's own audit, and the name/number "
        "contradiction halves. Previews by default; `--write` performs the one-time "
        "migration — held cards never change identity.",
    )
    cards_identity.add_argument(
        "--write",
        action="store_true",
        help="bind every deriving class (T1, T2, T3, T4u) to its SKU's own identity, hold "
        "the rest (T4s, T5), and open a review entry for every held card that is "
        "identified. Re-runnable: a card already correctly bound is skipped.",
    )
    cards_contradictions = cards_sub.add_parser(
        "contradictions",
        help="RETIRED (§5.5) — subsumed by `cards identity`. Prints one line naming it "
        "and exits.",
    )
    cards_contradictions.add_argument(
        "--verbose",
        action="store_true",
        help="list every disagreeing SKU as well as counting them.",
    )
    cards_contradictions.add_argument(
        "--resolve",
        action="store_true",
        help="ask the live catalogue to settle the SKUs that share a denominator. Costs "
        "one request per distinct (game, set) among them. Without this, no socket opens.",
    )
    cards_sku_names = cards_sub.add_parser(
        "sku-names",
        help="RETIRED (§5.5) — subsumed by `cards identity`. Prints one line naming it "
        "and exits.",
    )
    cards_sku_names.add_argument(
        "--verbose",
        action="store_true",
        help="list every ranked alternative and every not-known card, rather than "
        "counting them.",
    )
    cards_photos = cards_sub.add_parser(
        "photos",
        help="move the corpus off the legacy (box, index) address onto the card's own "
        "name. Previews by default; resumable and verified per card.",
    )
    cards_photos.add_argument(
        "--write",
        action="store_true",
        help="perform the move. Without it nothing is touched. Safe to interrupt: each "
        "card is linked, re-hashed at its new name, and only then unlinked at the old one.",
    )
    cards_photos.add_argument(
        "--limit",
        type=int,
        help="stop after this many cards. For a first pass over a large corpus.",
    )
    cards_variants = cards_sub.add_parser(
        "variants",
        help="RETIRED into `cards identity --write`. Prints one line, writes nothing, "
        "and exits 2.",
    )
    # KEPT so an operator who types the old `--write` reaches the one line that names the
    # replacement, rather than an argparse error that names nothing.
    cards_variants.add_argument("--write", action="store_true", help=argparse.SUPPRESS)

    # ----------------------------------------------------------------------------- join
    joined = sub.add_parser("join", help="resolve against the export. Free, re-runnable.")
    # OPTIONAL, AS OF PR G. A run directory from `identify` still works exactly as before —
    # the FILE path, replayed and reconciled against the store (D36's `realign`). Omit it and
    # name `--keys` instead for a STORE-BACKED join: cards this pipeline already identified,
    # read straight off the store at press time, with no run directory required to have
    # produced them. `identify`'s own selection went the same way under D180; this is the
    # join side of that generalization.
    joined.add_argument(
        "run_dir",
        nargs="?",
        help="run directory from `identify`. Omit and pass --keys for a store-backed join.",
    )
    joined.add_argument(
        "--keys",
        action="append",
        help="join these cards straight from the store, as `box/index` position keys, "
        "comma-separated. Repeatable. Only with no run directory.",
    )
    joined.add_argument(
        "--label",
        help="the run directory a store-backed join writes its own report and pricing "
        "table into (default: store). Only with no run directory.",
    )
    _pricing_arguments(joined)
    joined.add_argument(
        "--dry-run",
        action="store_true",
        help="report what WOULD queue and write nothing. Free and side-effect-free: no "
        "queues, no inventory/prices.json change, no report, no manifest.",
    )

    # ----------------------------------------------------------------------------- emit
    emit = sub.add_parser("emit", help="write the import CSVs. Free, re-runnable.")
    # ONE RUN OR SEVERAL (D86). `nargs="+"` rather than a `--runs` flag, because the argument
    # has always been the run and a send of one must keep reading exactly as it did — every
    # existing invocation, harness case and doc line is a list of one.
    emit.add_argument("run_dir", nargs="+")
    emit.add_argument(
        "--listed-only",
        action="store_true",
        help="above-threshold rows only, so the valuable cards can be staged first",
    )
    emit.add_argument(
        "--split-games",
        action="store_true",
        help="one file per game, if Import to Staged refuses a multi-Product-Line file",
    )
    # THE SECOND AXIS, AND IT IS A SPLIT RATHER THAN A FILTER. `--listed-only` above drops
    # the sub-threshold rows; this one files them separately, which is what `emit` did by
    # default until the owner asked for one spreadsheet. The two compose: both flags together
    # write the listed file and say how many rows are waiting for a later press.
    emit.add_argument(
        "--split-threshold",
        action="store_true",
        help="the old pair back: import-listed.csv above the D9 threshold and "
        "import-subthreshold.csv below it, instead of one import.csv",
    )
    # THE CAP, ASKED FOR PER SEND (D7, rewritten 2026-09-07). There is no standing bound any more:
    # every copy this run holds that TCGplayer does not already have goes out, and this is how
    # an operator says otherwise for ONE press. It is on `emit` and not on `join` because emit
    # is what writes the file — `join` reports what the shelf holds, and a cap named at join
    # time would be a promise a later emit could quietly break.
    emit.add_argument(
        "--cap",
        type=int,
        metavar="N",
        help="hold this SKU to at most N copies LIVE at TCGplayer, counting what is already "
        "out — a SKU at or over N adds nothing and the report says by how much. Omit for no "
        "cap, which is the default since the standing bound was retired",
    )
    # A QUANTITY FOR ONE CARD, THIS PRESS ONLY (D7, amended 2026-09-11, on the operator's
    # ruling). A send quantity and not a ceiling: `--quantity 8608859=2` puts two copies of
    # that SKU in the file whatever TCGplayer already holds, bounded by the copies on hand
    # that are not already listed. Repeatable, one SKU each; `0` sends none of that card
    # without holding it. The Qty field on every `#/pricing` row is the same answer.
    emit.add_argument(
        "--quantity",
        action="append",
        metavar="SKU=N",
        help="put exactly N copies of this SKU in the file this press, bounded by the copies "
        "on hand that are not already listed; 0 sends none of it. Repeat per card. A card "
        "not named sends every copy that can go",
    )
    # THE DOUBLE-SEND GUARD (`D-one-press-sends-and-makes-live`). A live export fetched
    # moments before this press: every row is trimmed so that TCGplayer's live quantity plus
    # the copies added never exceeds the copies on hand, and every trim is named. It only
    # ever takes copies OUT of the file. `pipeline/sendguard.py` has the arithmetic.
    emit.add_argument(
        "--live-guard",
        metavar="LIVE_EXPORT",
        help="a live export (My Pricing, all printings) read just before this send: no row "
        "may leave TCGplayer holding more copies than are on hand. Trims are named",
    )
    # THE MIXED SEND (the owner's ruling, 2026-09-24: "Allow mixed"). With `--live-guard`, a card
    # already live that this press adds no copy of, and whose price the SCREEN NAMED (round 6),
    # gets a price-only row: Add to Quantity 0. `pipeline/sendguard.py:price_changes`.
    emit.add_argument(
        "--reprice-live",
        metavar="NAMED_PRICES",
        help="with --live-guard: a JSON list of {sku, price, was} the screen named. Each named "
        "card already live that this press adds no copy of gets a price-only row (Add to "
        "Quantity 0). A price the list does not name is never written. Each is named",
    )
    # THE PRESS'S OWN FILE AND ITS CLAIM (`D-one-press-sends-and-makes-live`, round 2). Given by
    # `server/send_routes.py` only: the file goes into the press's own directory rather than
    # the run's, so two presses can never read each other's file, and the SKUs it adds are
    # claimed in the same store write that counts them sent (`store/sendclaims.py`).
    emit.add_argument("--send-dir", metavar="DIR", help=argparse.SUPPRESS)
    emit.add_argument("--send-claim", metavar="STAMP", help=argparse.SUPPRESS)
    emit.add_argument("--claim-holder", type=int, metavar="PID", help=argparse.SUPPRESS)
    _pricing_arguments(emit)

    # ------------------------------------------------------------------------ reconcile
    reconcile = sub.add_parser(
        "reconcile", help="confirm what TCGplayer actually staged"
    )
    # ONE RUN, OR THE WHOLE STORE (D87). The positionals stay exactly as they were — every
    # invocation, harness case and doc line written before this is a run and a staged export —
    # and `--live` is the store-wide mode, which needs neither.
    reconcile.add_argument("run_dir", nargs="?")
    reconcile.add_argument(
        "staged_export", nargs="?", help="TCGplayer's Export From Staged download"
    )
    reconcile.add_argument(
        "--live",
        help="a full live export (My Pricing): reconcile every SKU in the store against it",
    )
    reconcile.add_argument(
        "--write",
        action="store_true",
        help="with --live: settle the ledger. Previews without it.",
    )

    # --------------------------------------------------------------------------- queue
    #
    # THE STANDING QUEUES, RE-RESOLVED STORE-WIDE. `upsert` refreshes an entry and is reached
    # only from a join, a join is scoped to a run and a run to a box — so an entry whose box
    # holds no live run froze at the code that wrote it. Previews by default for
    # `reconcile --live`'s reason: it rewrites every open entry at once.
    queue = sub.add_parser(
        "queue", help="the standing review queues: re-resolve every open entry"
    )
    queue_sub = queue.add_subparsers(dest="queue_command")
    refreshing = queue_sub.add_parser(
        "refresh",
        help="re-resolve every OPEN entry against a current export. Free, re-runnable.",
    )
    refreshing.add_argument(
        "--export",
        action="append",
        metavar="FILE.CSV",
        help="an export to resolve against; repeat for several. Defaults to the ones the "
        "joined runs recorded, newest per game.",
    )
    refreshing.add_argument(
        "--write",
        action="store_true",
        help="apply the refresh. Previews without it.",
    )

    # -------------------------------------------------------------------------- prices
    #
    # THE CORPUS, AND THE ONE-TIME FOLD THAT FILLS IT (D86). `adopt` previews by default
    # because it is a data move with a real decision inside it — 8 SKUs on this machine are
    # answered twice and 3 of the pairs are a hold against a later price — and a migration
    # nobody watched is how those three would have gone quiet a second time.
    prices = sub.add_parser("prices", help="the pricing corpus: adopt the run files, or read it")
    prices_sub = prices.add_subparsers(dest="prices_command")
    adopt = prices_sub.add_parser(
        "adopt",
        help="fold every run's legacy decisions.json into inventory/prices.json and retire it",
    )
    adopt.add_argument("--write", action="store_true", help="actually write; previews without it")
    adopt.add_argument(
        "--force",
        action="store_true",
        help="fold the run files OVER answers the corpus already holds — the file's answer "
        "wins where they differ. Never needed to retire files whose answers the corpus "
        "already has.",
    )
    show = prices_sub.add_parser("show", help="what the corpus holds")
    show.add_argument("--held", action="store_true", help="list every card held back")

    # ----------------------------------------------------------------------- readings
    #
    # THE CACHED MARKET-READING TABLE, AND THE WALK THAT FILLS IT (D189).
    # `_readings()` in server/pipeline_routes.py used to walk every run's `pricing.json` and
    # the newest live export on every `GET /pipeline/value`; `adopt` runs that same walk once
    # and writes what it found into `readings`, which is a plain SELECT from there on. It
    # previews by default for the reason every other free, re-runnable command here does —
    # `join`, `reconcile`, `reprice list` — never because there is a judgement call inside it:
    # unlike `prices adopt`, nothing here overrides an operator's own answer.
    readings = sub.add_parser(
        "readings",
        help="the cached market-reading table: fold the two sources in, or look at it",
    )
    readings_sub = readings.add_subparsers(dest="readings_command")
    readings_adopt = readings_sub.add_parser(
        "adopt",
        help="walk every run's pricing.json and the newest live export, and cache the "
        "newest reading per SKU",
    )
    readings_adopt.add_argument(
        "--write", action="store_true", help="actually write; previews without it"
    )
    readings_sub.add_parser("show", help="what the table holds, and which files it last read")

    # ----------------------------------------------------------------------------- skus
    #
    # THE STORE-OWNED SKU TABLE (docs/specs/identity-follows-sku.md §3.2, lane 0 — owner's
    # ruling, 2026-09-24: "yes I'd been saying we build this"). `adopt` is the one-time
    # backfill over every export already cached on disk; a fetch route folds one export in
    # as it arrives, in a later lane. Previews by default, `readings adopt`'s own shape —
    # though UNLIKE `readings adopt` this is a FOLD onto whatever the table already holds,
    # never a full replace: `store/skus.py`'s whole argument is that this table never
    # deletes a row.
    skus = sub.add_parser(
        "skus",
        help="the store-owned TCGplayer SKU table: fold every export already on disk in",
    )
    skus_sub = skus.add_subparsers(dest="skus_command")
    skus_adopt = skus_sub.add_parser(
        "adopt",
        help="walk every cached export (.exports/<game>/*.csv, .live/*.csv) and fold what "
        "it says into the table",
    )
    skus_adopt.add_argument(
        "--write", action="store_true", help="actually write; previews without it"
    )

    # ------------------------------------------------------------------------- archive
    #
    # THE PRICE-HISTORY ARCHIVE (D219, `docs/specs/revenue-plan.md` §4).
    # The source endpoint's window is 357 days and slides; `sweep` is the one press that
    # reads it and keeps what it found past that ceiling. Previews by default, like
    # `readings adopt`, though for the same weaker reason: nothing here overrides an
    # operator's own answer. UNLIKE `readings adopt`, `--write` never clears a row a pass
    # did not mention — see `store/pricearchive.py`'s module docstring.
    archive = sub.add_parser(
        "archive",
        help="the price-history archive: sweep the live endpoint into it, or look at it",
    )
    archive_sub = archive.add_subparsers(dest="archive_command")
    archive_sweep = archive_sub.add_parser(
        "sweep",
        help="read every range for every sku this store has sold or holds, and archive "
        "what came back — never deleting a bucket a pass did not mention",
    )
    archive_sweep.add_argument(
        "--write", action="store_true", help="actually write; previews without it"
    )
    archive_show = archive_sub.add_parser(
        "show", help="what the archive holds, and which ranges were last swept"
    )
    archive_show.add_argument(
        "--sku", help="also print one sku's own buckets, across every range archived"
    )

    # ------------------------------------------------------------------------- reprice
    #
    # THE LIVE LISTINGS THAT ARE NOT SELLING, MARKED DOWN AND PUSHED BACK (D100). Two
    # subcommands rather than one press with a percentage, because the operator's own
    # sentence has two halves — export the stale rows out, mass re-edit them down — and a
    # spreadsheet is how a person does the second one. `list` writes the worklist with a
    # price already proposed on every row, so handing it straight back is also the flow.
    #
    # BOTH PREVIEW BY DEFAULT. `apply --write` is the last press before bytes leave for a
    # marketplace, and the file it writes cannot be un-uploaded.
    reprice = sub.add_parser(
        "reprice",
        help="mark down live listings that are not selling. Free, re-runnable, previews.",
    )
    reprice_sub = reprice.add_subparsers(dest="reprice_command", required=True)

    listing = reprice_sub.add_parser(
        "list",
        help="which live listings are stale, and what each would be re-priced to",
    )
    listing.add_argument("export", help="TCGplayer's My Pricing export, all printings")
    listing.add_argument(
        "--days",
        type=int,
        default=7,
        help="the window: no copy sold here inside it, and owned since before it "
        "(default: 7). Ownership age is a PROXY for listing age — the report says so.",
    )
    markdown_size = listing.add_mutually_exclusive_group()
    markdown_size.add_argument(
        "--percent",
        default="10",
        help="cut this much off the asking price (default: 10). Validated by "
        "`pricing.Rule.parse`, which is what refuses a negative or a 100.",
    )
    markdown_size.add_argument(
        "--rule",
        help="the power form: match | undercut:PCT | markup:PCT. `--percent` is this "
        "flag's common case spelled the way the screen spells it.",
    )
    listing.add_argument(
        "--basis",
        default=reprice_rules.BASIS_ASKING,
        choices=list(reprice_rules.BASES),
        help="which column the rule is applied to (default: asking — the operator's own "
        "live price, which is meaningful on a live row and blank almost everywhere else, "
        "which is why it is NOT one of pricing.BASES)",
    )
    listing.add_argument(
        "--above-market",
        help="only listings asking more than this percentage above TCG Market Price. The "
        "one term here that says WHY a card is not selling rather than only that it has not.",
    )
    listing.add_argument(
        "--limit",
        type=int,
        help="take only the N rows carrying the most asking value. The rest are named.",
    )
    listing.add_argument(
        "--again",
        action="store_true",
        help="mark down a SKU this store already answered inside the window. Without it "
        "`undercut:10` run daily compounds to -52%% in a week, every run justified.",
    )
    listing.add_argument(
        "--write",
        action="store_true",
        help=f"write the worklist into inventory/{cmd_reprice.DIRNAME}/. Previews without it.",
    )

    applying = reprice_sub.add_parser(
        "apply",
        help="read the edited worklist back and write the price-only import CSV",
    )
    applying.add_argument("worklist", help="the worklist, edited or not")
    applying.add_argument(
        "--manifest",
        help=f"the {cmd_reprice.MANIFEST} to judge it against (default: beside the worklist)",
    )
    applying.add_argument(
        "--corpus-revision",
        help="the digest of inventory/prices.json this caller last read. Refuses the WHOLE "
        "file if the corpus has moved since. Omit it to say 'I did not read one', which is "
        "the terminal user applying a worklist by hand and is allowed.",
    )
    applying.add_argument(
        "--write",
        action="store_true",
        help="write import.csv and record the prices. Previews without it.",
    )

    return parser


COMMANDS = {
    "scan": cmd_scan.run,
    "identify": cmd_identify.run,
    "join": cmd_join.run,
    "emit": cmd_emit.run,
    "reconcile": cmd_reconcile.run,
    "prices": cmd_prices.run,
    "readings": cmd_readings.run,
    "skus": cmd_skus.run,
    "archive": cmd_pricearchive.run,
    "queue": cmd_queue.run,
    "reprice": cmd_reprice.run,
    "rescue": cmd_rescue.run,
    "cards": cmd_cards.run,
    "boxes": cmd_boxes.run,
}


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return COMMANDS[args.command](args, _say)
    except runs.RunError as exc:
        _say(str(exc))
        return 1
    except FileNotFoundError as exc:
        _say(str(exc))
        return 1
    except KeyboardInterrupt:  # pragma: no cover
        _say("")
        _say("interrupted. Batch ids are in the manifest — re-run to reattach and collect.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
