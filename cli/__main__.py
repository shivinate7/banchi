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
    cmd_reconcile,
    cmd_reprice,
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
    identify.add_argument("capture_dir", help="directory of photos + JSON sidecars")
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
    identify.add_argument(
        "--box", type=int, help="box number for photos whose position has no box"
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
    "reprice": cmd_reprice.run,
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
