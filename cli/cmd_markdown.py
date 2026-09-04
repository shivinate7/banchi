"""`pkmnscan markdown <my-pricing.csv>` — mark down the listings that are not selling (D94).

PREVIEWS BY DEFAULT, for `reconcile --live`'s reason aimed at money instead of at quantities:
it decides what every stale listing will be asking, over the whole store at once, and a
re-price nobody read is how a wrong number becomes the new floor. `docs/DECISIONS.md`'s Someday
entry deferred this feature with the shape it would have to take — *"a free preflight showing
exactly which prices would change and by how much, and a confirm that is not a default"* — and
this is that preflight and that confirm.

THE OPERATOR'S OWN EXPORT IS BOTH HALVES OF THE ROUND TRIP. It says which SKUs are live
(`Total Quantity`), what each is currently asking (`TCG Marketplace Price`), and what the
market says (`TCG Market Price`) — so "export my inventory back out" is a file the operator
already downloads for `reconcile --live`, and nothing new has to be stored to know the old
price. The store supplies the half the export cannot: how long a card has been held, and
whether any copy of it has sold.

IT TALKS TO NOTHING. The upload back to TCGplayer stays a manual step the operator performs,
deliberately: this writes a CSV and stops.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, Optional, Tuple

from cli import runs
from pipeline import corpus as corpus_mod
from pipeline import decisions as decisions_mod
from pipeline import join, pricing, reprice, tcgcsv
from store import files, master
from store.session import Store

#: `<YYYY-MM-DD>-<HHMMSS>`. Sorts chronologically, carries no run label, and is the directory
#: name the route hands back so a download needs no second lookup.
STAMP_FORMAT = "%Y-%m-%d-%H%M%S"

IMPORT_NAME = "markdown.csv"
REPORT_NAME = "markdown.txt"
RECEIPT_NAME = "manifest.json"


def _store_facts(inventory) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, int], set]:
    """Per SKU: oldest capture, most recent sale, copies on hand, and every SKU ever seen.

    ONE INDEXED PASS AND NO CARD OBJECTS. `Rows.select` reads the four columns
    `store/db.py:TABLES` already indexes on `cards`, which is what makes this affordable
    against a store of any size — building 1,625 `Card`s to read four fields off each is the
    cost D88 moved the store to SQLite to stop paying.

    `ages` IS OVER EVERY CARD THAT EVER CARRIED THE SKU, INCLUDING DEPARTED ONES, and that is
    the correctness point rather than an optimisation. A floor computed over on-hand copies
    moves forward as the oldest copy sells, so a listing would get YOUNGER the longer it sat
    and fall out of the sweep exactly when it most belongs in it.

    `last_sold` COMES FROM THE CARDS AND NOT FROM THE EVENT LOG. `state_at` on a sold card is
    when the sale was recorded, and reading it here costs one indexed column; the log would
    cost a full scan plus a JSON extract per row, and one of the 193 `sold` events on the
    owner's store carries no `sku` key at all, which a naive log query answers by returning
    nothing. The measured difference is one SKU out of 87.

    `seen` IS WIDER THAN THE LISTING LEDGER, exactly as `cmd_reconcile._card_counts` says: a
    card can carry a SKU that was never pushed, and judging "listed outside pkmnscan" against
    the ledger would accuse the operator of every one of them.
    """
    ages: Dict[str, str] = {}
    last_sold: Dict[str, str] = {}
    on_hand: Dict[str, int] = {}
    seen: set = set()
    for _key, (sku, state, captured_at, state_at) in inventory.cards.select(
        ("sku", "state", "captured_at", "state_at")
    ):
        if not sku:
            continue
        sku = str(sku)
        seen.add(sku)
        if captured_at and (sku not in ages or str(captured_at) < ages[sku]):
            ages[sku] = str(captured_at)
        if state == master.SOLD and state_at:
            if sku not in last_sold or str(state_at) > last_sold[sku]:
                last_sold[sku] = str(state_at)
        elif state not in master.TERMINAL_STATES:
            on_hand[sku] = on_hand.get(sku, 0) + 1
    return ages, last_sold, on_hand, seen


def _money(value: Optional[Decimal]) -> str:
    return "-" if value is None else tcgcsv.format_price(value)


def _report(plan: reprice.Plan, source: dict, rule, basis: str, days: int,
            above_market: Optional[Decimal], limit: Optional[int]) -> list:
    """The whole report as lines. Composed once, printed and written verbatim.

    THE SCREEN RENDERS THIS STRING AND NOTHING ELSE (D33), so it is the only place the
    old-and-new pair is drawn and there is no second renderer to disagree with it — D67's
    rule for a number composed twice, applied to a number that moves money.

    THE HEADER NAMES THE RULE AND THE BASIS ON PURPOSE. `#/runs` deliberately carries no
    `--rule` or `--basis` control (D49), so this sentence is how the operator reads the policy
    being applied, and it is on screen before the control that applies it exists.
    """
    out = []
    out.append("")
    out.append("live export      {0}".format(source["path"]))
    out.append("                 {0}, sha256 {1}".format(
        source["mtime"], source["sha256"][:12]))
    out.append("                 {0} row(s), {1} with a live quantity".format(
        plan.scanned, plan.live_rows))
    policy = "rule={0} basis={1} window={2}d floor=${3}".format(
        rule, basis, days, tcgcsv.format_price(pricing.FLOOR))
    if above_market is not None:
        policy += " above-market={0}%".format(above_market)
    if limit is not None:
        policy += " limit={0}".format(limit)
    out.append("policy           {0}".format(policy))
    out.append("age              time since the OLDEST copy of the SKU was photographed here "
               "— how long")
    out.append("                 it has been owned, which is the nearest thing the store can "
               "say to how")
    out.append("                 long it has been listed (D94).")
    out.append("")

    if plan.candidates:
        out.append("markdown         {0} SKU(s), {1} copy(ies), ${2} off the asking total"
                   .format(len(plan.candidates), plan.copies,
                           tcgcsv.format_price(plan.off)))
        out.append("")
        out.append("  {0:>6} {1:>10} {2:>8} {3:>8} {4:>8} {5:>7} {6:>4}  card".format(
            "copies", "sku", "asking", "new", "market", "drift", "age"))
        for row in plan.candidates:
            drift = "-" if row.drift_pct is None else "{0:+.1f}%".format(row.drift_pct)
            age = "-" if row.age_days is None else "{0}d".format(row.age_days)
            label = "{0} · {1}".format(row.name, row.condition).strip(" ·")
            out.append("  {0:>6} {1:>10} {2:>8} {3:>8} {4:>8} {5:>7} {6:>4}  {7}".format(
                row.live, row.sku, _money(row.listed), _money(row.new),
                _money(row.market), drift, age, label[:44]))
    else:
        out.append("markdown         nothing to mark down under this window and rule.")

    if plan.truncated:
        out.append("")
        out.append("held back by --limit  {0} SKU(s), {1} copy(ies) — the rows below the cut, "
                   "by value".format(
                       len(plan.truncated), sum(row.live for row in plan.truncated)))
        out.append("  {0}".format(
            "  ".join(row.sku for row in plan.truncated[:12])
            + ("  ..." if len(plan.truncated) > 12 else "")))

    named = [reason for reason in reprice.REASON_ORDER if plan.skipped.get(reason)]
    if named:
        out.append("")
        out.append("not marked down")
        for reason in named:
            rows_ = plan.skipped[reason]
            out.append("  {0:<18} {1} SKU(s) — {2}".format(
                reprice.REASON_HEADING[reason], len(rows_), _NOTE[reason]))
            if reason in _NAME_EVERY_ONE:
                out.append("      {0}".format(
                    "  ".join(row.sku for row in rows_[:12])
                    + ("  ..." if len(rows_) > 12 else "")))

    at_risk = plan.at_risk
    if at_risk:
        out.append("")
        out.append("a later emit would undo {0} of these".format(len(at_risk)))
        out.append("  Under the live cap with backstock behind them, so the next `emit` writes "
                   "a row at the")
        out.append("  rule price. The markdown is written to the corpus, which outranks the "
                   "rule — clear the")
        out.append("  answer on #/pricing to give one its rule price back.")
        out.append("      {0}".format(
            "  ".join(row.sku for row in at_risk[:12])
            + ("  ..." if len(at_risk) > 12 else "")))
    return out


#: One sentence per skipped population. They are here rather than in `pipeline/reprice.py`
#: because they are report copy, and that module is the decision.
_NOTE = {
    reprice.REASON_SOLD_OUT:
        "a price, but no copies for sale. Nothing to mark down until they are re-listed.",
    reprice.REASON_SOLD_RECENTLY:
        "sold inside the window. Working; the price is left alone.",
    reprice.REASON_TOO_YOUNG:
        "held for less than the window. No chance to sell yet.",
    reprice.REASON_NOT_DRIFTED:
        "priced within --above-market of the market. The price is not the problem.",
    reprice.REASON_HELD:
        "held back in the corpus AND live at TCGplayer. A hold is a deliberate "
        "\"not this one\"; these are listed.",
    reprice.REASON_MARKED_DOWN_RECENTLY:
        "already marked down inside the window. --again to do it anyway.",
    reprice.REASON_NOT_A_MARKDOWN:
        "the rule does not lower the price — at the floor, or the basis is above the asking "
        "price. Never raised.",
    reprice.REASON_NO_LISTED_PRICE:
        "live, with no asking price this export can read.",
    reprice.REASON_NO_BASIS_PRICE:
        "the basis column is blank, so the rule has nothing to apply to.",
    reprice.REASON_QUANTITY_NOT_ZERO:
        "the export row already carries `Add to Quantity`. Re-download it.",
    reprice.REASON_NOT_THIS_STORE:
        "live at TCGplayer, and no card here carries the SKU. Left alone — this pipeline did "
        "not put it there.",
}

#: Populations small enough and surprising enough to name every member of.
_NAME_EVERY_ONE = frozenset({
    reprice.REASON_HELD,
    reprice.REASON_MARKED_DOWN_RECENTLY,
    reprice.REASON_QUANTITY_NOT_ZERO,
})


def _rule_from(args) -> str:
    """`--percent` and `--rule` are one setting, and only one may be given.

    `--percent 10` is the screen's whole vocabulary and spells `undercut:10`; `--rule` is the
    CLI's power form and reaches `markup:` and `match`, which the screen deliberately cannot.
    Accepting both would make the file the operator gets depend on which one this function
    happened to prefer.
    """
    if args.percent is not None and args.rule is not None:
        raise ValueError(
            "give --percent or --rule, not both: --percent 10 is --rule undercut:10"
        )
    if args.percent is not None:
        return "{0}:{1}".format(pricing.RULE_UNDERCUT, args.percent)
    if args.rule is not None:
        return str(args.rule)
    raise ValueError(
        "how far down? Give --percent PCT (10 means 10% off what you are asking) or "
        "--rule undercut:PCT. There is no default: no number in this repo derives one."
    )


def run(args, say) -> int:
    path = Path(args.live_export)
    if not path.is_file():
        say("live export not found: {0}".format(path))
        return 1

    try:
        rule = _rule_from(args)
        pricing.Rule.parse(rule)
    except ValueError as exc:
        say(str(exc))
        return 1

    above_market = None
    if args.above_market is not None:
        try:
            above_market = Decimal(str(args.above_market))
        except InvalidOperation:
            say("--above-market wants a percentage, e.g. --above-market 10")
            return 1

    try:
        export = tcgcsv.read_export(path)
        # DUPLICATE SKUs REFUSED AT READ, before a single price is computed. An import file
        # with two rows for one `TCGplayer Id` is undefined behaviour at TCGplayer, and an
        # export carrying one would produce exactly that.
        export.by_sku()
    except tcgcsv.MalformedCsv as exc:
        say("that file is not a TCGplayer export: {0}".format(exc))
        return 1

    try:
        book = corpus_mod.Corpus.read()
    except decisions_mod.MalformedDecisions as exc:
        say("{0} cannot be read: {1}".format(files.prices_path(), exc))
        say("Fix the file, or `pkmnscan prices show` to see what parses.")
        return 1

    source = runs.describe_source(path)
    snapshot = Store().read()
    ages, last_sold, on_hand, seen = _store_facts(snapshot.inventory)

    held = {sku for sku, answer in book.answers.items() if answer.is_hold}
    marked_down = {
        sku: answer.marked_down
        for sku, answer in book.answers.items()
        if answer.marked_down
    }

    try:
        plan = reprice.select(
            export.rows,
            ages=ages,
            last_sold=last_sold,
            on_hand=on_hand,
            seen=seen,
            held=held,
            marked_down={} if args.again else marked_down,
            rule=rule,
            days=args.days,
            now=str(source["mtime"]),
            basis=args.basis,
            above_market=above_market,
            limit=args.limit,
        )
    except pricing.UnknownBasis as exc:
        say("--basis {0}".format(exc))
        return 1

    lines = _report(plan, source, rule, args.basis, args.days, above_market, args.limit)
    for line in lines:
        say(line)

    if not plan.candidates:
        # NO FILE AT ALL, EVER, and this is D54's rule rather than a tidiness preference:
        # `tcgcsv.write_csv` emits the header before it iterates, so an empty list produces a
        # valid CSV of nothing that is indistinguishable on disk from a file whose rows were
        # never written — and catastrophic when it lands where the operator was told to find
        # an import.
        say("")
        say("Nothing to mark down. No file written, with or without --write.")
        return 0

    if not args.write:
        say("")
        say("DRY RUN — nothing written. {0} SKU(s) would be re-priced and {1} copy(ies) "
            "affected.".format(len(plan.candidates), plan.copies))
        say("`Add to Quantity` is 0 on every row, so this changes prices and adds no copies:")
        say("it cannot breach the live cap, marks no card sold, and moves no `live` count.")
        say("Re-run with --write to produce the import CSV.")
        return 0

    try:
        rows = reprice.rows(plan)
    except reprice.NotAdditive as exc:
        say("")
        say("REFUSED, and nothing was written: {0}".format(exc))
        return 1

    stamp = datetime.now(timezone.utc).strftime(STAMP_FORMAT)
    directory = files.markdowns_dir() / stamp
    directory.mkdir(parents=True, exist_ok=True)

    # THROUGH `join.write_import` AND NEVER A WRITER OF ITS OWN. It carries the duplicate-SKU
    # gate and `tcgcsv.write_csv`'s byte format — the header unquoted, every field quoted,
    # CRLF — which is the format `fixtures/staged-import-accepted.csv` proves TCGplayer took.
    # It reads `catalog` only for `.header`, and an `Export` has one.
    import_path = directory / IMPORT_NAME
    join.write_import(export, import_path, rows)

    text = "\n".join(lines)
    (directory / REPORT_NAME).write_text(text + "\n", encoding="utf-8")

    receipt = reprice.receipt(plan, source, rule, args.basis, args.days)
    receipt["stamp"] = stamp
    receipt["import"] = IMPORT_NAME
    files.write_json(directory / RECEIPT_NAME, receipt)

    # THE CORPUS LAST, AFTER THE FILE IS ON DISK. If the write fails, the store still says the
    # old price and the operator can re-run; the other order would leave the store claiming a
    # markdown that no file ever carried.
    at = master.now()
    for candidate in plan.candidates:
        previous = book.answers.get(candidate.sku)
        book.answers[candidate.sku] = corpus_mod.Answer(
            value=tcgcsv.format_price(candidate.new),
            at=at,
            from_run=previous.from_run if previous is not None else None,
            channel="price",
            # WHAT IT WAS ASKING, AND IT SURVIVES A SECOND MARKDOWN. `previous.was` is kept
            # rather than overwritten by the intermediate price, so `was` is what the card was
            # asking before this pipeline started moving it — which is the number an operator
            # undoing a ratchet actually wants.
            was=(previous.was if previous is not None and previous.was
                 else tcgcsv.format_price(candidate.listed)),
            marked_down=at,
        )
    written_corpus = book.write()

    say("")
    say("wrote            {0}".format(import_path))
    say("                 {0} row(s), `Add to Quantity` 0 on every one".format(len(rows)))
    say("receipt          {0}".format(directory / REPORT_NAME))
    say("corpus           {0} — {1} answer(s), {2} marked down now".format(
        written_corpus, len(book.answers), len(plan.candidates)))
    say("")
    say("Upload {0} to TCGplayer. Nothing here has told them anything.".format(IMPORT_NAME))
    say("No card is marked sold, no `live` count moved, and no copies were added.")
    return 0
