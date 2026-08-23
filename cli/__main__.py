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

from cli import cmd_emit, cmd_identify, cmd_join, cmd_reconcile, runs  # noqa: E402
from identify import images  # noqa: E402
from pipeline import pricing, routing, variant  # noqa: E402
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

    # ------------------------------------------------------------------------- identify
    identify = sub.add_parser(
        "identify", help="submit, wait, collect, cache. THE ONE THAT COSTS MONEY."
    )
    identify.add_argument("capture_dir", help="directory of photos + JSON sidecars")
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

    # ----------------------------------------------------------------------------- emit
    emit = sub.add_parser("emit", help="write the import CSVs. Free, re-runnable.")
    emit.add_argument("run_dir")
    _pricing_arguments(emit)

    # ------------------------------------------------------------------------ reconcile
    reconcile = sub.add_parser(
        "reconcile", help="confirm what TCGplayer actually staged"
    )
    reconcile.add_argument("run_dir")
    reconcile.add_argument("staged_export", help="TCGplayer's Export From Staged download")

    return parser


COMMANDS = {
    "identify": cmd_identify.run,
    "join": cmd_join.run,
    "emit": cmd_emit.run,
    "reconcile": cmd_reconcile.run,
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
