"""`pkmnscan reprice` — the live listings that are not selling, marked down and pushed back.

TWO PRESSES, BECAUSE THE OPERATOR ASKED FOR TWO. *"Export my live inventory back out (for
cards I have listed and aren't selling) and be able to mass re-edit the prices down (and then
reupload it back)."* `list` writes the worklist; `apply` reads it back and writes the upload.
Between them sits a spreadsheet, or nothing at all — the worklist arrives with a price already
proposed on every row, so the common case is download, glance, hand it straight back.

NOTHING IS DELETED AT TCGPLAYER AND NOTHING NEEDS TO BE. `pipeline/reprice.py`'s header
carries the measurements; the conclusion is that `TCG Marketplace Price` edits the live
listing in place and `Add to Quantity` is a DELTA against the quantity TCGplayer already
holds. So a markdown is a price-only push, `Add to Quantity` is 0 on every row of every file
this command writes, and the quantity is not a variable anywhere in this path.

BOTH HALVES PREVIEW BY DEFAULT, for `pkmnscan prices adopt`'s reason and one more. The reason
it shares: this moves numbers the operator cannot see the effect of until they are live. The
reason it does not: `apply --write` is the last press before bytes leave for a marketplace,
and the file it writes cannot be un-uploaded.

THE THREE FILES, and why the worklist is not the upload:

  worklist.csv   the stale rows, in export shape, price already proposed. What the operator
                 edits. Safe to upload by accident: every row carries `Add to Quantity` 0.
  manifest.json  what the export said, per SKU, INCLUDING THE ROW'S OWN BYTES.
  import.csv     what `apply` writes, built from the manifest's bytes with only the price
                 changed. This is the file that goes back to TCGplayer.

`apply` READS EXACTLY TWO CELLS out of whatever the operator hands back — `TCGplayer Id` and
`TCG Marketplace Price` — and takes every other byte from the manifest. A spreadsheet
reformats on open and on save, and none of that can reach TCGplayer through this path.

WHERE IT LIVES. `inventory/markdowns/<stamp>/`, under `inventory/` and never under `runs/`. A
run directory is one box's immutable input and is declared disposable; a markdown is
store-wide and is state — the corpus answers `apply` writes are the store's price for those
SKUs from then on, and the receipt is what explains them.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional

from cli import runs
from pipeline import corpus, decisions, pricing, reprice, tcgcsv
from store import files, master
from store.session import Store

DIRNAME = "markdowns"
WORKLIST = "worklist.csv"
IMPORT = "import.csv"
MANIFEST = "manifest.json"
#: Every live row the survey saw, with its verdict — what `#/pricing` draws as a lens. See
#: `_write_worklist` for why this is its own file rather than a wider manifest.
SURVEY = "survey.json"
REPORT = "report.txt"
RECEIPT = "receipt.txt"

#: How many rows of a block are printed before it is summarised. The report is read in a
#: terminal and in a `<pre>` on `#/runs`; a full store is 441 live rows.
SHOWN = 25


def _markdowns_dir() -> Path:
    return files.inventory_dir() / DIRNAME


#: How long after a publish TCGplayer's own live export cannot be trusted about the SKUs that
#: were published.
#:
#: MEASURED IN ONE DIRECTION ONLY, AND THIS CONSTANT SAYS SO. On 2026-09-06 a real publish was
#: confirmed at 19:25:32 — `Update: [Vilemaw / Marketplace]`, zero errors — and roughly FORTY
#: SECONDS later `Export From Live` still served the pre-publish price, while the seller
#: portal's own grid served the new one. So the lower bound is measured at ~40s. **When it
#: actually converges was never measured**, because measuring that costs another live price
#: change on the owner's real store.
#:
#: 15 MINUTES IS THEREFORE A CHOICE AND NOT A READING, and it is deliberately generous: what
#: it costs when too long is a reconcile the operator repeats later, and what it costs when
#: too short is a wrong number written into `live` — the field `cli/resolve.py:_copies_out`
#: treats as a floor that cannot be argued below. The two costs are not symmetric.
#:
#: HOW TO REPLACE IT WITH A MEASUREMENT: publish one SKU, then fetch the live export on a
#: fixed interval until its price agrees, and record the interval. That is a real experiment
#: and it belongs in `docs/specs/stale-listings.md` §6 beside the timeline that produced this.
PUBLISH_LAG_S = 15 * 60


def published_recently(now: Optional[datetime] = None, window_s: int = PUBLISH_LAG_S) -> Dict[str, str]:
    """SKUs published to TCGplayer inside the window, mapped to when.

    WHY THIS EXISTS. `Export From Live` is not read-your-writes (D106, measured): after a
    confirmed publish it goes on serving the OLD price for a while. `reconcile --live` writes
    the store's `live` field off that export and dates the reading by the FILE'S mtime — which
    is the fetch time, and so looks fresh. The content is stale and the timestamp says
    otherwise, so `Listing.live_reading` picks the export and the pre-publish figure wins.

    THE RECEIPT SAYS WHEN AND THE FILE SAYS WHICH. `push.json` carries `published_at`; the
    `import.csv` beside it carries the rows that went. Neither is re-derived from the store,
    so this cannot disagree with what was actually sent — and a markdown that was pushed but
    never published contributes nothing, because nothing about it reached the live export.

    IT NARROWS TO SKUS RATHER THAN BLOCKING THE RECONCILE. The rest of the store is not in
    doubt, and D87's own rule for a reading it will not take is to KEEP the stored value and
    NAME it in the report rather than to refuse the whole document. This is that rule, pointed
    at a second clock.
    """
    moment = now or datetime.now(timezone.utc)
    recent: Dict[str, str] = {}
    root = _markdowns_dir()
    if not root.is_dir():
        return recent
    for directory in root.iterdir():
        record = files.read_json(directory / "push.json", {}) or {}
        stamp = record.get("published_at")
        if not stamp:
            continue
        try:
            when = datetime.fromisoformat(str(stamp))
        except ValueError:
            # A receipt this cannot date is treated as RECENT, not as old. The whole point is
            # to refuse a figure we cannot vouch for, and an unparseable stamp is exactly that.
            when = moment
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if (moment - when).total_seconds() > window_s:
            continue
        for sku in _skus_in(directory / IMPORT):
            # NEWEST PUBLISH WINS, so a SKU published twice reports the stamp that matters.
            if sku not in recent or stamp > recent[sku]:
                recent[sku] = str(stamp)
    return recent


def _skus_in(path: Path) -> List[str]:
    """The `TCGplayer Id` column of one import file, or nothing if it is unreadable.

    UNREADABLE MEANS EMPTY AND NOT AN ERROR. This runs inside a reconcile the operator asked
    for; a markdown directory somebody half-deleted must not take the settlement down with it.
    """
    if not path.is_file():
        return []
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            return [
                (row.get(tcgcsv.SKU_COLUMN) or "").strip()
                for row in csv.DictReader(handle)
                if (row.get(tcgcsv.SKU_COLUMN) or "").strip()
            ]
    except (OSError, csv.Error, UnicodeDecodeError):
        return []


def _stamp() -> str:
    """A free `YYYYMMDD-HHMMSS`, advancing a second at a time until the directory is unclaimed.

    THE SHAPE IS AN ADDRESS AND MAY NOT GROW A SUFFIX. `server/pipeline_routes.py:_STAMP` and
    the five route patterns in `server/capture_server.py` all spell it `[0-9]{8}-[0-9]{6}`, so
    a `-2` on the end is a markdown no route can reach — the collision would stop being silent
    by becoming unaddressable, which is worse.

    WHY IT COLLIDES AT ALL: two `reprice list --write` calls inside one second resolve to one
    directory and the later manifest replaces the earlier, so the first worklist is judged
    against an offer that is no longer its own. It became easier to reach when an empty plan
    started writing too — the survey that proposes nothing is exactly the one an operator runs
    twice while widening `--days`.

    THE COST IS THAT A DIRECTORY CAN BE NAMED A FEW SECONDS AFTER THE MOMENT IT DESCRIBES, and
    the manifest's own `at` is the truth either way. A bound rather than a `while True`: a
    minute of collisions is not a busy operator, it is a clock that has stopped, and spinning
    silently is how that gets discovered much later.
    """
    now = datetime.now(timezone.utc)
    for step in range(60):
        stamp = (now + timedelta(seconds=step)).strftime("%Y%m%d-%H%M%S")
        if not (_markdowns_dir() / stamp).exists():
            return stamp
    raise ValueError(
        "no free markdown stamp within a minute of now — check the clock, and check "
        f"{_markdowns_dir()} for a directory named after the future."
    )


def _card_facts(inventory):
    """Per SKU: the oldest capture, and the newest sale.

    OVER EVERY CARD THAT EVER CARRIED THE SKU, DEPARTED ONES INCLUDED. A floor taken over
    on-hand copies alone moves forward as the oldest copy sells, so a listing would get
    younger the longer it sat there — the opposite of the thing being measured.

    THE CARD RECORDS AND NEVER THE EVENT LOG. Measured on the owner's store: one of the 193
    `sold` events carries no `sku` key, while all 186 cards in the `sold` state carry both a
    SKU and a `state_at`. A query over the log loses that copy silently, and a SKU whose only
    sale is invisible reads as "never sold" — which is the exact input this command marks a
    price down on.
    """
    oldest, sold = {}, {}
    for card in inventory.cards.values():
        sku = getattr(card, "sku", None)
        if not sku:
            continue
        captured = getattr(card, "captured_at", None)
        if captured and (sku not in oldest or str(captured) < oldest[sku]):
            oldest[sku] = str(captured)
        elif sku not in oldest:
            # A card with no capture stamp still proves the SKU is this store's. The key is
            # what sets `Candidate.held_here`, which is drawn evidence rather than a gate
            # since D109 — it was a terminal `not_this_store` refusal until then. The value
            # stays None, and with no sighting either `_before` refuses it as `too_young`,
            # which is the honest answer for a row nothing can date.
            oldest.setdefault(sku, None)
        if getattr(card, "state", None) == master.SOLD:
            at = getattr(card, "state_at", None)
            if at and (sku not in sold or str(at) > sold[sku]):
                sold[sku] = str(at)
    return oldest, sold


def _listing_facts(inventory):
    """Per SKU: the first sighting live, and when this store last set a price.

    THE LISTING RECORDS AND NEVER THE CARDS, which is the whole reason this is a second
    function rather than more of `_card_facts`. Every fact here is about what TCGplayer
    holds and what was done to it; `Listing` carries them for SKUs no card in this store has
    ever carried, which is precisely the set `_card_facts` cannot see and the set the
    membership gate used to refuse. A store whose reconcile has never run returns two empty
    maps and every caller falls back to the proxy, unchanged.
    """
    seen, priced = {}, {}
    for sku, listing in inventory.listings.items():
        first = getattr(listing, "first_seen_live", None)
        if first:
            seen[str(sku)] = str(first)
        at = getattr(listing, "priced_at", None)
        if at:
            priced[str(sku)] = str(at)
    return seen, priced


def _money(value) -> str:
    return f"${value:,.2f}" if isinstance(value, Decimal) else str(value)


def _rule_from(args) -> pricing.Rule:
    if getattr(args, "rule", None):
        return pricing.Rule.parse(args.rule)
    return pricing.Rule.parse(f"{pricing.RULE_UNDERCUT}:{args.percent}")


# ------------------------------------------------------------------------------- list


def _say_plan(plan, say, source, export, live_rows) -> None:
    asked = plan.asked
    say("")
    say(f"live export      {source['path']}")
    say(f"                 {source['mtime']}, sha256 {source['sha256'][:12]}")
    say(f"                 {len(export.rows)} row(s), {live_rows} live at TCGplayer")
    dated = getattr(plan, "dated", {}) or {}
    say(f"window           {asked['days']} day(s) — no sale here and listed since before "
        f"{str(asked['cut_off'])[:19]}")
    say(f"rule             {asked['rule']} off the {asked['basis']} price, "
        f"floored at {_money(Decimal(str(asked['floor'])))}")
    if asked["above_market"] is not None:
        say(f"                 and only where the asking price is more than "
            f"{Decimal(asked['above_market']).normalize()}% above TCG Market Price")

    # WHICH CLOCK DATED WHICH ROWS, ON EVERY REPORT, WHERE THE OPERATOR READS IT. D100's rule
    # is that a substitution nobody is told about is a lie. It printed the proxy paragraph
    # unconditionally, which was right while `Listing` had no first-listed stamp and is a lie
    # of its own now that some rows carry one — so the report counts and says.
    proxied = int(dated.get("ownership", 0))
    sighted = int(dated.get("sighting", 0))
    undatable = int(dated.get("neither", 0))
    if sighted or proxied or undatable:
        say("")
        if sighted:
            say(f"age              {sighted} row(s) dated by FIRST SIGHTING — when an export was "
                f"first seen")
            say("                 holding the SKU, which is the listing's own age.")
        if proxied:
            say(f"                 {proxied} row(s) fall back to OWNERSHIP — the oldest capture "
                f"of any card")
            say("                 carrying the SKU. A floor on the listing's age, never the age "
                "itself;")
            say("                 `pkmnscan reconcile --live --write` gives those rows a real "
                "one.")
        if undatable:
            say(f"                 {undatable} row(s) can be dated by neither and are reported "
                f"`too_young`")
            say("                 rather than priced on a guess.")

    say("")
    say(f"would mark down  {len(plan.rows)} SKU(s), {plan.copies} copy(ies)")
    if plan.rows:
        say(f"                 asking {_money(plan.asking_before)} -> "
            f"{_money(plan.asking_after)}  "
            f"(giving up {_money(plan.asking_before - plan.asking_after)})")
        say("")
        say("  copies  sku         asking      new   vs mkt   card")
        for row in plan.rows[:SHOWN]:
            margin = row.above_market
            say(f"  {row.live:>6}  {row.sku:<10}  {row.asking:>7.2f}  {row.proposed:>7.2f}  "
                f"{('+%d%%' % margin) if margin is not None else '     ':>6}   "
                f"{row.name[:38]} ({row.condition})")
        if len(plan.rows) > SHOWN:
            say(f"  ... and {len(plan.rows) - SHOWN} more")

    if plan.deferred:
        say("")
        say(f"below --limit    {len(plan.deferred)} SKU(s) qualified and were not taken, "
            f"ranked below the cut")
        for row in plan.deferred[:8]:
            say(f"                 {row.sku:<10} {row.name[:38]} "
                f"({_money(row.at_risk)} asking)")
        if len(plan.deferred) > 8:
            say(f"                 ... and {len(plan.deferred) - 8} more")

    skips = plan.skips()
    if skips:
        say("")
        say("not moving")
        for code, group in skips:
            say(f"  {reprice.SKIP_SENTENCE[code]:<38} {len(group):>5} SKU(s)   [{code}]")


def _cash(value) -> Optional[str]:
    """A figure as the string the wire carries, or None. Money is text, never a JSON float."""
    return None if value is None else str(value)


def _surveyed(row, standing: str) -> dict:
    """One candidate as `survey.json` holds it — every figure this path actually knows.

    THE FIGURES ARE COMPUTED HERE AND NEVER ON THE SCREEN. `above_market`, `at_risk`, `cut` and
    `given_up` are all arithmetic on money, and `app/src/Pricing.tsx` performs none: a price
    that goes through a JSON float comes back as binary floating point, and every comparison
    downstream is `Decimal`.

    `row` IS THE VERBATIM EXPORT ROW and is the reason this file can be addressed at all. It is
    what `_history_row`'s five identity cells are read out of, and what an upload's bytes come
    from — the same argument the manifest's own copy carries, one file over.
    """
    return {
        "sku": row.sku,
        "standing": standing,
        "skip": row.skip,
        "name": row.name,
        "condition": row.condition,
        "live": row.live,
        "asking": _cash(row.asking),
        "market": _cash(row.market),
        "above_market": _cash(row.above_market),
        "at_risk": _cash(row.at_risk),
        "proposed": _cash(row.proposed),
        # THE THREE PRESETS, PRICED SERVER-SIDE, EXACTLY AS A RUN'S `pricing.json` CARRIES THEM.
        # This was absent until 2026-09-07 and the client filled `presets: {}` for every lens
        # row, so pressing `Market −5%` there filled nothing, changed nothing the lens sends —
        # `apply` reads typed answers only — and still wrote `policy.rule` to the store,
        # silently repricing every future joined run. `pipeline/pricing.py` owns the arithmetic
        # so the two doors cannot compute a different number for one card.
        "presets": pricing.preset_prices(row.row),
        "cut": _cash(row.cut),
        "given_up": _cash(row.given_up),
        "owned_since": row.owned_since,
        # BOTH CLOCKS, NOT THE ONE THAT WON. The screen draws the age and has to be able to
        # say which it is looking at — a sighting is the listing's own age, an ownership
        # stamp is a floor on it, and a row carrying only the second must not be captioned as
        # though it carried the first.
        "listed_since": row.listed_since,
        # WHETHER ANY CARD HERE EVER CARRIED THIS SKU. Drawn as evidence beside the row and
        # never a gate: it stopped being a refusal on 2026-09-06. The screen uses it to
        # explain why a row has no thumbnail and no copies, which is a different sentence
        # from having none left.
        "held_here": row.held_here,
        "last_sold": row.last_sold,
        "priced_at": row.priced_at,
        "row": row.row,
    }


def _write_worklist(plan, source, say) -> Path:
    directory = _markdowns_dir() / _stamp()
    directory.mkdir(parents=True, exist_ok=True)

    rows = [
        tcgcsv.set_writable(
            row.row,
            add_to_quantity=reprice.ADD_TO_QUANTITY,
            marketplace_price=row.proposed,
        )
        for row in plan.rows
    ]
    # THE GATE, OVER THE BYTES ABOUT TO BE WRITTEN rather than over the intention. It runs on
    # the worklist too, and not only on the upload: a worklist is a 16-column export-shaped
    # file, so it is uploadable by accident, and the only thing that makes that harmless is
    # this being true of it as well.
    carried = reprice.check_quantities_zero(rows)
    if carried:
        raise ValueError(
            "refusing to write: rows carry a non-zero Add to Quantity: "
            + ", ".join(carried[:6])
        )
    tcgcsv.write_csv(directory / WORKLIST, tcgcsv.CANONICAL_HEADER, rows)

    manifest = {
        "kind": "markdown",
        "at": master.now(),
        "asked": plan.asked,
        "source": source,
        "skus": {
            row.sku: {
                "was": str(row.asking),
                "proposed": str(row.proposed),
                "live": row.live,
                "name": row.name,
                "condition": row.condition,
                "owned_since": row.owned_since,
                "last_sold": row.last_sold,
                # THE EXPORT'S OWN ROW, VERBATIM. What `apply` builds the upload out of, so
                # a spreadsheet's reformatting of the worklist can never reach TCGplayer.
                "row": row.row,
            }
            for row in plan.rows
        },
    }
    files.write_json(directory / MANIFEST, manifest)

    # THE SURVEY, WHICH IS A RECORD AND NOT AN OFFER — the fourth file, and D100 §5's own
    # distinction applied once more. `worklist.csv` offers rows to upload; `manifest.json`
    # records what the offer said; this records what the whole EXPORT said, so `#/pricing`
    # can draw every live listing and price one the rule declined to propose.
    #
    # IT IS A SEPARATE FILE AND NOT A WIDER MANIFEST, for two measured reasons. `_apply` reads
    # `manifest["skus"]` to build the upload's bytes, so leaving it alone is what keeps that
    # path provably untouched by this widening — every existing assertion in `check_markdown`
    # runs over byte-identical inputs. And `server/pipeline_routes.py:_markdown_summary` parses
    # the manifest for EVERY stamp to answer `GET /pipeline/markdowns`: at ~700 bytes a row a
    # wide manifest is ~530KB on the owner's export, so thirty markdowns would mean parsing
    # 16MB to draw a list.
    #
    # A LIST AND NOT A MAP, because the ORDER is the answer. `Plan.surveyed` walks the offer by
    # `at_risk`, then the deferred, then the refusals in `SKIP_ORDER`, so a screen drawing this
    # top to bottom draws what the terminal printed.
    files.write_json(
        directory / SURVEY,
        {
            "kind": "survey",
            "at": manifest["at"],
            "asked": plan.asked,
            "source": source,
            "counts": {
                "considered": plan.considered,
                "offered": len(plan.rows),
                "deferred": len(plan.deferred),
                "refused": sum(len(group) for group in plan.skipped.values()),
            },
            "skus": [_surveyed(row, standing) for row, standing in plan.surveyed()],
        },
    )
    say("")
    say(f"wrote            {directory / WORKLIST}")
    say(f"                 {directory / MANIFEST}")
    say(f"                 {directory / SURVEY}")
    return directory


def _list(args, say) -> int:
    path = Path(args.export)
    if not path.is_file():
        say(f"live export not found: {path}")
        return 1

    try:
        rule = _rule_from(args)
    except pricing.UnknownRule as exc:
        say(str(exc))
        return 1
    try:
        above = None if args.above_market is None else Decimal(str(args.above_market))
    except InvalidOperation:
        say(f"--above-market is {args.above_market!r}, which is not a number")
        return 1

    export = tcgcsv.read_export(path)
    source = runs.describe_source(path)
    snapshot = Store().read()
    owned_since, last_sold = _card_facts(snapshot.inventory)
    listed_since, listing_priced_at = _listing_facts(snapshot.inventory)

    try:
        book = corpus.Corpus.read()
    except decisions.MalformedDecisions as exc:
        say(f"{corpus.FILENAME} is unusable: {exc}")
        return 1
    # THE FLOOR IS THE STORE'S CUT-OFF AND IS READ HERE (D9, amended 2026-09-09). One figure:
    # `policy.threshold` is the market price at or above which a card earns a listing AND the
    # cheapest price this store lists anything at, so it is what a markdown may not go below.
    # `pipeline/reprice.py` defaults to D9's constant for a caller with no store; this is the
    # caller that has one. Unparseable is a refusal rather than a fallback — `check_threshold`
    # raises, `MalformedDecisions` is caught above it, and a bad figure silently reverting to
    # $0.40 is precisely the substitution this amendment exists to end.
    try:
        floor = pricing.check_threshold(book.policy_for()["threshold"])
    except pricing.InvalidThreshold as exc:
        say(f"{corpus.FILENAME}: {exc}")
        return 1
    held = [sku for sku, answer in book.answers.items() if answer.is_hold]
    priced_at = {
        sku: answer.at
        for sku, answer in book.answers.items()
        # `channel == "price"` IS THE HALF THAT WAS MISSING, and it is not belt-and-braces.
        # `cli/cmd_join.py` seeds `Answer(value=None, channel="unknown")` for every card the
        # catalog could not price — the ABSENCE of an answer, which is what makes `blocking`
        # refuse an emit. Now that `corpus.stamp_answers` dates answers written from
        # `#/pricing` too, a `not answer.is_hold` test alone would let an UNPRICED card read
        # as `priced_recently` and be refused a markdown for the wrong reason.
        if answer.at and answer.channel == "price" and not answer.is_hold
    }
    # THE LISTING'S OWN STAMP FILLS IN WHERE THE CORPUS HAS NOTHING TO SAY. A SKU no card
    # here carries gets no corpus answer (D103's refusal, and the reason `prices.json` never
    # became a second inventory), so before `Listing.priced_at` existed the ratchet was blind
    # on exactly the rows the membership gate used to hide — and a rule that cannot tell it
    # already marked a card down is one that marks it down again on every pass. The corpus
    # wins where both have a stamp: it is the answer this store DECIDED, and the listing's is
    # the record that a press happened.
    for sku, stamp in listing_priced_at.items():
        priced_at.setdefault(sku, stamp)

    plan = reprice.plan(
        export.rows,
        owned_since=owned_since,
        listed_since=listed_since,
        last_sold=last_sold,
        priced_at={} if args.again else priced_at,
        held=held,
        days=args.days,
        rule=rule,
        basis=args.basis,
        above_market=above,
        limit=args.limit,
        floor=floor,
    )
    live_rows = sum(
        1
        for row in export.rows
        if tcgcsv.parse_quantity(row.get(tcgcsv.LIVE_QUANTITY_COLUMN, "")) > 0
    )

    lines = []
    _say_plan(plan, lines.append, source, export, live_rows)
    for line in lines:
        say(line)

    if not plan.rows:
        say("")
        say("nothing to mark down. Every live row is named above — widen --days, lower")
        say("--above-market, or accept that nothing here has been sitting long enough.")
        # AND IT STILL WRITES, WHICH IS THE ONE PLACE THE LENS CHANGED THIS COMMAND'S SHAPE.
        # This used to return here, so a survey that proposed nothing left no directory at all
        # — and `#/pricing`'s lens is reached BY a stamp, on a screen whose whole premise is
        # that staleness is a filter rather than a gate. On the owner's own store `--days 10`
        # selects zero rows, so the most ordinary way to ask "show me everything" produced
        # nothing to address.
        #
        # THE DIRECTORY SHAPE IS INVARIANT: a header-only `worklist.csv` rather than no
        # worklist, so nothing downstream has to test for a file that is sometimes absent. It
        # is also still safe to upload by accident, being a file with no rows in it.
        if not args.write:
            return 0
    elif not args.write:
        say("")
        say(f"DRY RUN — nothing written. Re-run with --write to put the worklist in "
            f"{_markdowns_dir()}/,")
        say("then edit its `TCG Marketplace Price` column and hand it to `pkmnscan reprice apply`.")
        return 0

    try:
        directory = _write_worklist(plan, source, say)
    except (ValueError, tcgcsv.ReadOnlyColumn, tcgcsv.MalformedCsv) as exc:
        say(str(exc))
        return 1
    (directory / REPORT).write_text("\n".join(lines) + "\n", encoding="utf-8")
    say(f"                 {directory / REPORT}")
    say("")
    say("Edit the worklist's `TCG Marketplace Price` column — or do not, the prices above are")
    say(f"already in it — then: pkmnscan reprice apply {directory / WORKLIST}")
    return 0


# ------------------------------------------------------------------------------ apply


def _load_manifest(path: Path, override) -> Path:
    if override:
        return Path(override)
    return path.parent / MANIFEST


def _survey_beside(manifest_path: Path):
    """`survey.json`'s rows keyed by SKU, and the SKUs no price may be pushed for.

    Returns `({}, {})` where there is no survey, which is every markdown written before the
    lens existed — applying one of those worklists then reads exactly as it always did.

    THE BAR IS THE SURVEY'S OWN CODE, NOT A JUDGEMENT TAKEN HERE. `not_this_store` is the 33
    SKUs on the owner's export that TCGplayer lists and this store has never held; lowering one
    would move a listing this pipeline did not create and whose copies it cannot verify, which
    is outside the measurement D100's whole safety argument rests on. `sold_out` is a row the
    export carries with no live copies, so there is no listing for a price to edit. Both are
    drawn on the lens — omitting them would show 408 rows against an export the operator can
    see holds 441 — and neither is pushable.
    """
    path = manifest_path.parent / SURVEY
    if not path.is_file():
        return {}, {}
    try:
        payload = json.loads(path.read_text("utf-8"))
        rows = payload["skus"]
    except (OSError, ValueError, KeyError):
        # A SURVEY THAT CANNOT BE READ IS A SURVEY THAT IS NOT THERE. It is a record, and the
        # offer — which is what `apply` is really about — is in the manifest beside it. Losing
        # the lens's extra reach is not a reason to refuse an upload the manifest fully
        # describes.
        return {}, {}
    # PROJECTED INTO THE MANIFEST'S VOCABULARY, so `_apply` reads one shape and not two. The
    # survey calls the export's price `asking`, which is `Candidate`'s own word for it and the
    # right word on a screen drawing a live listing; the manifest calls it `was`, which is the
    # right word for a figure a lowering is judged against. The translation belongs here, at
    # the one seam, rather than in every reader.
    by_sku = {
        str(row.get("sku") or ""): {
            "was": row.get("asking"),
            "live": row.get("live"),
            "name": row.get("name"),
            "row": row.get("row"),
        }
        for row in rows
        if row.get("sku")
    }
    barred = {
        str(row.get("sku")): str(row.get("skip"))
        for row in rows
        if row.get("sku") and row.get("skip") in reprice.UNPRICEABLE_CODES
    }
    return by_sku, barred


def _apply(args, say) -> int:
    path = Path(args.worklist)
    if not path.is_file():
        say(f"worklist not found: {path}")
        return 1
    manifest_path = _load_manifest(path, args.manifest)
    if not manifest_path.is_file():
        say(f"no {MANIFEST} beside {path}")
        say("A worklist is judged against what the export said when it was written, so the")
        say("manifest is not optional. Keep the worklist in the directory `reprice list`")
        say("made, or point at the manifest with --manifest.")
        return 1
    try:
        manifest = json.loads(manifest_path.read_text("utf-8"))
        entries = manifest["skus"]
    except (OSError, ValueError, KeyError) as exc:
        say(f"{manifest_path} is unusable: {exc}")
        return 1

    # THE SURVEY WIDENS WHAT MAY BE PRICED; THE MANIFEST STILL SAYS WHAT WAS OFFERED. A row the
    # rule declined to propose — `near_market`, `too_young`, `priced_recently` — is a row the
    # lens draws and the operator may hand a price back for, and its bytes are on disk. What it
    # is NOT is part of the offer, so `offered=` keeps `dropped` measuring the worklist.
    #
    # OPTIONAL, AND ABSENT IS THE OLD BEHAVIOUR EXACTLY. A markdown written before this landed
    # has no `survey.json`, and applying its worklist must read the same as it always did.
    survey, unpriceable = _survey_beside(manifest_path)
    known = dict(entries)
    for sku, entry in survey.items():
        known.setdefault(sku, entry)

    # THE STORE'S FLOOR, READ NOW RATHER THAN OFF THE MANIFEST (D9, amended 2026-09-09). The
    # manifest records the figure the SURVEY was taken against; what a price may not go below
    # is the store's cut-off as it stands at the moment of the press, which is the figure the
    # operator has in front of them on `#/pricing`. Loosening the cut-off after a survey must
    # let the looser prices through — that is the whole shape of the defect this closes — and
    # tightening it must refuse them.
    try:
        floor = pricing.check_threshold(corpus.Corpus.read().policy_for()["threshold"])
    except (decisions.MalformedDecisions, pricing.InvalidThreshold) as exc:
        say(f"{corpus.FILENAME} is unusable: {exc}")
        return 1

    edited = tcgcsv.read_export(path)
    application = reprice.read_back(
        edited.rows,
        # A SURVEY ROW WITH NO ASKING PRICE CARRIES `None` AND IS DROPPED FROM `was` RATHER
        # THAN COERCED. `read_back` refuses an unparseable `was` as `not_in_worklist`, which is
        # the honest answer for a live row the export gave no price for: there is nothing to
        # judge a lowering against.
        {sku: entry["was"] for sku, entry in known.items() if entry.get("was") is not None},
        live={sku: int(entry.get("live") or 0) for sku, entry in known.items()},
        names={sku: str(entry.get("name") or "") for sku, entry in known.items()},
        offered=list(entries),
        unpriceable=unpriceable,
        floor=floor,
    )

    say("")
    say(f"worklist         {path}")
    say(f"                 {len(edited.rows)} row(s), judged against {manifest_path.name}")
    # THE FIGURE, ON THE REPORT, BESIDE THE COUNT IT EXPLAINS. `below_floor`'s sentence names
    # no number on purpose — see `pipeline/reprice.py:EDIT_SENTENCE` — so this line is the one
    # place the floor is printed, and it can only print the value actually used.
    say(f"                 floored at {_money(floor)} — the store's cut-off, "
        f"{corpus.FILENAME}'s `policy.threshold`")
    say(f"would upload     {len(application.edits)} SKU(s), {application.copies} copy(ies)")
    if application.edits:
        say(f"                 giving up {_money(application.given_up)} of asking value")
        # A RAISE IS SAID OUT LOUD, ON ITS OWN LINE, AND NEVER NETTED INTO THE FIGURE ABOVE
        # (D107). This command is called a markdown; a row inside it pointing the other way is
        # the one an operator most needs told, and `given_up` deliberately does not offset.
        if application.raised:
            say(f"                 {len(application.raised)} of them RAISED, adding "
                f"{_money(application.taken_on)} — the rule never proposes a raise, so these "
                f"are prices you typed")
        say("")
        say("  copies  sku         was       now   card")
        for edit in application.edits[:SHOWN]:
            arrow = "^" if (edit.cut or 0) < 0 else " "
            say(f"  {edit.live:>6}  {edit.sku:<10}  {edit.was:>6.2f}  {edit.now:>6.2f} {arrow} "
                f"{edit.name[:44]}")
        if len(application.edits) > SHOWN:
            say(f"  ... and {len(application.edits) - SHOWN} more")

    if application.dropped:
        say("")
        say(f"deleted from the worklist  {len(application.dropped)} SKU(s) — left alone, "
            f"which is what deleting a line means")

    if application.refused:
        say("")
        say("not uploading")
        for code in (
            reprice.UNCHANGED, reprice.BELOW_FLOOR, reprice.UNREADABLE,
            reprice.NOT_IN_WORKLIST, *reprice.UNPRICEABLE_CODES,
            reprice.RAISED, reprice.DUPLICATE,
        ):
            group = [e for e in application.refused if e.refusal == code]
            if group:
                say(f"  {reprice.EDIT_SENTENCE[code]:<44} {len(group):>5} SKU(s)   [{code}]")

    fatal = application.fatal
    if fatal:
        say("")
        say("REFUSED — the whole file, not the row:")
        for edit in fatal[:10]:
            say(f"  {edit.sku:<10} {reprice.EDIT_SENTENCE[edit.refusal or '']}")
        say("A duplicate SKU is undefined behaviour in a TCGplayer import (D7), and raising a")
        say("live price is the one thing this command promises never to do. Fix the worklist.")
        return 1

    if not application.edits:
        say("")
        say("nothing to upload.")
        return 0

    if not args.write:
        say("")
        say("DRY RUN — nothing written. Re-run with --write to put import.csv beside the")
        say("worklist. Every row of it carries `Add to Quantity` 0: it changes prices and")
        say("cannot change a quantity, so uploading it twice cannot double anything.")
        return 0

    # THE STALE-WRITE REFUSAL, AND IT RUNS BEFORE A SINGLE BYTE IS BUILT. `PUT /pricing` has
    # been guarded since D86 while this command — which read-modify-writes the same file from a
    # subprocess — was not, so a `#/pricing` tab open during an apply had its next keystroke
    # refused for a write it had made itself. Now that the press lives ON that screen, that is
    # the ordinary case rather than a race.
    #
    # ABSENT MEANS "DID NOT READ ONE", WHICH IS ALLOWED — the terminal user editing the file
    # and applying a worklist by hand, exactly the carve-out the route makes. The guard is for
    # a caller that DID read a revision and is now behind.
    #
    # AND IT REFUSES THE WHOLE FILE. The corpus is what `prices_for` will list this card at
    # from now on; an `import.csv` built against a corpus the operator cannot see is a file
    # that moves money on a decision nobody made.
    offered_revision = getattr(args, "corpus_revision", None)
    if offered_revision:
        current = corpus.revision()
        if current and offered_revision != current:
            say("")
            say("REFUSED — the pricing file changed since this was read: another tab, another")
            say("command, or an edit on disk. Nothing is written. Re-read and try again.")
            return 1

    originals = {sku: dict(entry["row"]) for sku, entry in known.items() if entry.get("row")}
    try:
        rows = reprice.import_rows(application.edits, originals)
    except (KeyError, ValueError) as exc:
        say(f"cannot build the upload: {exc}")
        return 1
    carried = reprice.check_quantities_zero(rows)
    if carried:
        say("REFUSED — rows carry a non-zero Add to Quantity: " + ", ".join(carried[:6]))
        say("This is the defect the whole command is shaped around; nothing is written.")
        return 1
    seen = set()
    for row in rows:
        sku = row[tcgcsv.SKU_COLUMN]
        if sku in seen:
            say(f"REFUSED — {sku} would be written twice (D7). Nothing is written.")
            return 1
        seen.add(sku)

    target = path.parent / IMPORT
    tcgcsv.write_csv(target, tcgcsv.CANONICAL_HEADER, rows)

    # THIS IS THE ROUND THE OWNER ASKED ABOUT — a SKU marked down a second, third or fourth
    # time. `edit.was` is the price this markdown replaces, already in hand from the
    # worklist's own manifest read, so `replaced` is never a guess or a second store lookup
    # (D243). `run` names the markdown by its own folder stamp, since a
    # reprice apply has no run directory of its own.
    with Store().write() as writable:
        for edit in application.edits:
            writable.postings.record(
                sku=edit.sku,
                price=tcgcsv.format_price(edit.now),
                source="reprice",
                run=path.parent.name,
                replaced=tcgcsv.format_price(edit.was) if edit.was is not None else None,
            )

    # THE ANSWER GOES IN THE CORPUS, KEYED BY SKU (D86). Without this the next `emit` over
    # another copy of the same card re-lists it at the rule price and quietly undoes the
    # markdown — the marked-down price is the store's price for that SKU from now on, not a
    # property of this file. `at` is what the ratchet reads next time: a SKU answered inside
    # the window is refused as `priced_recently` unless `--again`.
    #
    # THE STAMP GOES THROUGH `corpus.stamp_answers` RATHER THAN BEING SET HERE, so that this
    # command and `PUT /pricing` date an answer by one rule. Setting `at` inline was the only
    # place in the repo that ever wrote it, which is why `priced_recently` meant "marked down
    # recently" while D100 claimed it meant "priced recently, by any hand".
    before = corpus.Corpus.read()
    book = corpus.Corpus.read()
    stamp = master.now()
    for edit in application.edits:
        book.answers[edit.sku] = corpus.Answer(value=str(edit.now))
    corpus.stamp_answers(before, book, stamp)
    book.write()

    lines = [
        f"markdown applied {stamp}",
        f"worklist         {path}",
        f"import           {target}",
        f"rows             {len(rows)} SKU(s), {application.copies} copy(ies)",
        f"given up         {_money(application.given_up)} of asking value",
        f"raised           {len(application.raised)} SKU(s), adding "
        f"{_money(application.taken_on)}",
        "add to quantity  0 on every row — this file changes prices and no quantity",
        "",
    ] + [
        f"  {edit.sku:<10} {edit.was} -> {edit.now}"
        f"{'  RAISED' if (edit.cut or 0) < 0 else ''}  x{edit.live}  {edit.name}"
        for edit in application.edits
    ]
    (path.parent / RECEIPT).write_text("\n".join(lines) + "\n", encoding="utf-8")

    say("")
    say(f"wrote            {target}")
    say(f"                 {path.parent / RECEIPT}")
    say(f"                 {len(application.edits)} answer(s) into {corpus.FILENAME}")
    say("")
    say("Upload import.csv to TCGplayer through My Pricing. It carries `Add to Quantity` 0 on")
    say("every row, so it changes prices and cannot add, remove or delete a single copy.")
    return 0


def run(args, say) -> int:
    if args.reprice_command == "apply":
        return _apply(args, say)
    return _list(args, say)
