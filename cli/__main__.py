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
    cmd_emit,
    cmd_identify,
    cmd_join,
    cmd_prices,
    cmd_queue,
    cmd_reconcile,
    cmd_reprice,
    cmd_rescue,
    cmd_scan,
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

    # ----------------------------------------------------------------------------- join
    joined = sub.add_parser("join", help="resolve against the export. Free, re-runnable.")
    joined.add_argument("run_dir", help="run directory from `identify`")
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
    "queue": cmd_queue.run,
    "reprice": cmd_reprice.run,
    "rescue": cmd_rescue.run,
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
