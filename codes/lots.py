"""Building a sellable lot out of the ledger, and the three artefacts a sale needs.

A LOT IS SCOPED TO A BOX, AND THAT IS THE WHOLE DESIGN. The obvious shape — "reserve any
1,000 sellable bulk codes" — is broken for a PHYSICAL sale and broken in a way that is
invisible until a buyer complains. The ledger would commit codes A through J while the
operator, standing at a shelf, physically grabs a different thousand cards; the buyer then
receives cardboard whose codes are not the ones reserved against their order, and the ledger
is confidently wrong about both. There is no packing discipline that fixes it, because the
cards are indistinguishable by eye.

So the lot's scope is the same scope a run has: a box. The pull instruction becomes "take
box 12", the reserved codes are exactly the codes on the cards in box 12, and the two cannot
drift because neither is chosen independently of the other. That the cards keep a `box` and
an `index` at all is D24's own concession — it hides `Position.label` for a pooled card, it
does not take the position away, and this module is the first thing to need it back.

A COUNT-SCOPED LOT IS STILL OFFERED, and it is correct for exactly one case: a DIGITAL sale,
where nothing is pulled and the codes travel on their own. `scope="count"` refuses to be
used for a physical lot for the reason above, rather than trusting the caller to remember.

A PHYSICAL LOT TAKES THE WHOLE BOX OR IT IS REFUSED, which is the same rule one step along.
A lot that took 1,000 of a box's 1,003 cards would produce a perfectly correct ledger and a
packing slip reading "Box 12, 1000 card(s)" — and the operator, holding that slip and that
box, ships 1,003. `plan` refuses instead and names the strays by index, because "pull all of
them except these three" is not an instruction anybody executes reliably against a thousand
identical pieces of cardboard.

THAT CHECK ASKS WHAT IS IN THE BOX, NOT WHAT IS SELLABLE FROM IT, and the difference is two
classes of card that would otherwise ride along unseen: a code with no product claim, which
every lot filter drops on purpose, and a code already reserved to ANOTHER lot, which would
then be shipped to two buyers. Only `delivered` means the cardboard has actually left.

THE ARTEFACTS ARE THREE, BECAUSE THREE DIFFERENT PEOPLE READ THEM:

    listing.txt    the seller, once, when creating the listing. Title and description.
    manifest.txt   the BUYER, and it is the product. One code per line, nothing else.
    packing.txt    the operator, at the shelf. What to physically pull, and the count to
                   verify against before the parcel is sealed.

EVERY ONE OF THESE CARRIES LIVE CODES OR NAMES THE BOX THAT DOES, so the directory they are
written to is gitignored whole, exactly like `inventory/` and `runs/`. A lot is derived and
deletable — the ledger is the truth about what is reserved — which is `runs/`-shaped rather
than `inventory/`-shaped, and that is why it gets its own top-level directory rather than a
corner of the master store.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from codes import ledger, products
from store import files as store_files

LOTS_DIRNAME = "lots"

LISTING = "listing.txt"
MANIFEST = "manifest.txt"
PACKING = "packing.txt"
RECEIPT = "lot.json"

# How the lot chose its codes.
SCOPE_BOX = "box"
SCOPE_COUNT = "count"
SCOPES = (SCOPE_BOX, SCOPE_COUNT)

# How the buyer receives them. `physical` REQUIRES a box scope — see the module header.
DELIVERY_PHYSICAL = "physical"
DELIVERY_DIGITAL = "digital"
DELIVERIES = (DELIVERY_PHYSICAL, DELIVERY_DIGITAL)

# Where a lot is going. Recorded rather than acted on: nothing in this repo talks to either
# marketplace, and the venue only ever decides what the listing text says. The operator
# ruled out every other channel on 2026-08-30 (see docs/specs/code-cards.md).
VENUES = ("ebay", "tcgplayer", "other")

# `lot-2026-08-30-box12`. Kept to this alphabet so it is safe as a directory name and safe
# to paste into a marketplace's order reference field, which is where it has to survive.
_SLUG_SAFE = re.compile(r"[^a-z0-9-]+")


class LotError(RuntimeError):
    """A lot could not be built. Nothing is reserved when this is raised."""


def lots_dir():
    return store_files.home() / LOTS_DIRNAME


def lot_dir(lot_id: str):
    return lots_dir() / lot_id


def slug(text: str) -> str:
    cleaned = _SLUG_SAFE.sub("-", str(text).strip().lower()).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned or "lot"


@dataclass
class Lot:
    """One built lot. `codes` are already reserved by the time this exists."""

    lot_id: str
    scope: str
    delivery: str
    venue: str
    box: Optional[int]
    codes: List[str]
    products_in: List[Dict[str, object]] = field(default_factory=list)
    sets_in: List[str] = field(default_factory=list)
    note: str = ""

    @property
    def count(self) -> int:
        return len(self.codes)


def _sellable(entries, *, box: Optional[int], premium: Optional[bool]):
    """The pool a lot may draw from. `held` only — a reserved code is somebody else's."""
    out = []
    for entry in entries:
        if not entry.sellable:
            continue
        if box is not None and entry.box != box:
            continue
        if premium is not None and products.is_premium(entry.product) != premium:
            continue
        # A code with NO product claim is excluded from every lot, for the reason
        # `server/codes_routes._pool` gives at length: treating an unclaimed code as bulk is
        # right most of the time, and the times it is wrong a premium code leaves in a penny
        # lot and nobody ever finds out.
        if not entry.product:
            continue
        out.append(entry)
    return out


def plan(
    entries,
    *,
    scope: str,
    delivery: str,
    box: Optional[int] = None,
    count: Optional[int] = None,
    premium: Optional[bool] = False,
) -> Tuple[List[ledger.Entry], Dict[str, object]]:
    """What a lot WOULD take. Reserves nothing; raises rather than partially filling.

    THE PHYSICAL/BOX COUPLING IS ENFORCED HERE, not documented and hoped for. A physical lot
    whose codes were chosen by count would ship cards whose codes are not the ones reserved
    (module header), so it is refused outright — the caller cannot opt out by passing the
    right-looking arguments.
    """
    if scope not in SCOPES:
        raise LotError(f"scope was {scope!r}; use one of {', '.join(SCOPES)}")
    if delivery not in DELIVERIES:
        raise LotError(f"delivery was {delivery!r}; use one of {', '.join(DELIVERIES)}")
    if delivery == DELIVERY_PHYSICAL and scope != SCOPE_BOX:
        raise LotError(
            "a PHYSICAL lot must be scoped to a box. Chosen by count, the codes reserved "
            "and the cards pulled off the shelf are two different thousand cards, and the "
            "buyer gets codes that were never committed to them."
        )
    if scope == SCOPE_BOX and box is None:
        raise LotError("a box-scoped lot needs a box number")

    pool = _sellable(entries, box=box if scope == SCOPE_BOX else None, premium=premium)

    if scope == SCOPE_BOX:
        taking = pool if count is None else pool[:count]
        if count is not None and len(pool) < count:
            raise LotError(
                f"box {box} holds {len(pool)} sellable code(s), {count} asked for — "
                "nothing was reserved"
            )
        if not taking:
            # AN EMPTY POOL IS NOT AN EMPTY BOX, and saying only the first is how an
            # operator gets told "no sellable codes" while looking at a full box. The
            # commonest causes are a box already committed to another lot and a box of
            # unclaimed codes, and each has a different remedy — so the message names what
            # is actually in there rather than what is missing from it.
            present = [
                e for e in entries if e.box == box and e.state != ledger.DELIVERED
            ]
            if present:
                blocked: Dict[str, int] = {}
                for e in present:
                    if e.state == ledger.RESERVED:
                        reason = f"reserved to {e.order_id}"
                    elif e.state == ledger.DEAD:
                        reason = f"dead ({e.dead_reason})"
                    elif not e.product:
                        reason = "no product claim"
                    elif premium is not None and products.is_premium(e.product) != premium:
                        reason = (
                            "premium, and this lot is bulk" if products.is_premium(e.product)
                            else "bulk, and this lot is premium"
                        )
                    else:
                        reason = "not sellable"
                    blocked[reason] = blocked.get(reason, 0) + 1
                detail = "; ".join(f"{n} {why}" for why, n in sorted(blocked.items()))
                raise LotError(
                    f"box {box} holds {len(present)} card(s), and none of them can enter "
                    f"this lot: {detail}. Nothing was reserved."
                )
            raise LotError(
                f"box {box} holds no codes at all. Scan it first, or check the box number."
            )
        if delivery == DELIVERY_PHYSICAL:
            # A PHYSICAL LOT TAKES THE WHOLE BOX OR IT IS REFUSED, and this is the check
            # that makes the packing instruction true rather than nearly true.
            #
            # THE BUG IT EXISTS TO STOP WAS REAL AND WAS FOUND BY READING A GENERATED SLIP.
            # A box of 1,003 cards — 1,000 boosters, two Pokemon Center ETB codes and one
            # card nobody had claimed — produced a lot of 1,000 and a slip that said "Box
            # 12, 1000 card(s)". Every filter had worked perfectly. The operator, handed
            # that slip and a box, ships 1,003 cards, and two of the three strays list at
            # roughly 46x a booster.
            #
            # "Pull all of them except these three" is not an instruction a human executes
            # reliably against a thousand identical pieces of cardboard, so it is not
            # offered. The remedy named below is physical and unambiguous: move the strays
            # out of the box, or give the unclaimed ones a product, and build again.
            # WHAT IS PHYSICALLY IN THE BOX, not what is sellable out of it. The first
            # version of this check asked `_sellable` and so missed two whole classes of
            # card that are nonetheless sitting in the box and would go in the parcel:
            #   - a code with NO product claim, which `_sellable` filters out on purpose;
            #   - a code already RESERVED TO ANOTHER LOT, which would be shipped twice.
            # `delivered` is the one state that means the cardboard has genuinely left.
            chosen = {id(e) for e in taking}
            left = [
                e for e in entries
                if e.box == box and e.state != ledger.DELIVERED and id(e) not in chosen
            ]
            if left:
                def _why(e):
                    if e.state == ledger.RESERVED:
                        return f"already reserved to {e.order_id}"
                    if e.state == ledger.DEAD:
                        return f"dead ({e.dead_reason})"
                    if not e.product:
                        return "no product claim"
                    return products.display(e.product)

                detail = ", ".join(
                    f"{e.index} ({_why(e)})"
                    for e in sorted(left, key=lambda x: (x.index or 0))[:12]
                )
                more = "" if len(left) <= 12 else f", and {len(left) - 12} more"
                raise LotError(
                    f"box {box} physically holds {len(left)} card(s) this lot would NOT "
                    f"take, so 'pull box {box}' would ship them anyway: index {detail}"
                    f"{more}. A physical lot is the whole box or it is nothing — move those "
                    "cards out of the box, give the unclaimed ones a product claim, or "
                    "settle the ones already reserved elsewhere, and build again. Nothing "
                    "was reserved."
                )
    else:
        if count is None:
            raise LotError("a count-scoped lot needs a count")
        if len(pool) < count:
            raise LotError(
                f"{count} asked for, {len(pool)} sellable — nothing was reserved"
            )
        taking = pool[:count]

    by_product: Dict[str, int] = {}
    sets: Dict[str, int] = {}
    for entry in taking:
        by_product[entry.product or products.UNCLAIMED] = (
            by_product.get(entry.product or products.UNCLAIMED, 0) + 1
        )
        if entry.set_hint:
            sets[entry.set_hint] = sets.get(entry.set_hint, 0) + 1

    summary = {
        "count": len(taking),
        "box": box,
        "scope": scope,
        "delivery": delivery,
        "by_product": sorted(
            (
                {
                    "product": key,
                    "display": products.display(key),
                    "premium": products.is_premium(key),
                    "count": n,
                }
                for key, n in by_product.items()
            ),
            key=lambda r: (not r["premium"], -int(r["count"])),
        ),
        "sets": sorted(({"set": k, "count": n} for k, n in sets.items()),
                       key=lambda r: -int(r["count"])),
        "premium_in_lot": sum(1 for e in taking if products.is_premium(e.product)),
    }
    return taking, summary


def build(entries, *, lot_id: str, scope: str, delivery: str, venue: str,
          box: Optional[int] = None, count: Optional[int] = None,
          premium: Optional[bool] = False, buyer: Optional[str] = None) -> Lot:
    """Reserve the lot's codes against `lot_id`. Mutates `entries`; the caller writes.

    ALL OR NOTHING, through `plan` raising before a single reservation happens. The caller
    holds the store lock and writes the ledger, exactly as every other write under the store
    does — putting a lock in here would give the store two locking disciplines.
    """
    if venue not in VENUES:
        raise LotError(f"venue was {venue!r}; use one of {', '.join(VENUES)}")
    taking, summary = plan(
        entries, scope=scope, delivery=delivery, box=box, count=count, premium=premium
    )
    for entry in taking:
        ledger.reserve(entries, entry.code, order_id=lot_id, buyer=buyer)
    return Lot(
        lot_id=lot_id,
        scope=scope,
        delivery=delivery,
        venue=venue,
        box=box,
        codes=[e.code for e in taking],
        products_in=list(summary["by_product"]),
        sets_in=[str(r["set"]) for r in summary["sets"]],
    )


# ------------------------------------------------------------------------- the artefacts

def listing_text(lot: Lot) -> str:
    """Title and description, for the seller to paste once.

    DELIBERATELY PLAIN, AND IT MAKES NO CLAIM THIS REPO CANNOT SUPPORT. It does not say
    "unused", "unscanned" or "guaranteed" — those are the conventions the research found
    correlate with sales, and every one of them is a claim about codes nobody here has
    validated. There is no non-consuming way to check a Pokemon code, so a guarantee printed
    by a program would be a guarantee the program has no basis for. The operator may add one
    knowingly; the generator will not add one on their behalf.
    """
    n = lot.count
    sets = ", ".join(lot.sets_in[:6]) if lot.sets_in else "mixed"
    if len(lot.sets_in) > 6:
        sets += f", +{len(lot.sets_in) - 6} more"
    delivered = (
        "Physical cards shipped." if lot.delivery == DELIVERY_PHYSICAL
        else "Codes delivered as a message. No physical cards shipped."
    )
    lines = [
        f"TITLE:  {n}x Pokemon TCG Live Code Cards - {sets}",
        "",
        "DESCRIPTION:",
        f"  {n} Pokemon Trading Card Game Live code cards.",
        f"  Sets: {sets}.",
        f"  {delivered}",
        "",
        "  Product mix:",
    ]
    for row in lot.products_in:
        lines.append(f"    {row['count']:>5}  {row['display']}")
    lines += [
        "",
        "  Codes are sold as-is. Each code redeems once, in Pokemon TCG Live.",
        "",
        f"  Lot reference: {lot.lot_id}",
    ]
    if lot.delivery == DELIVERY_PHYSICAL:
        lines += [
            "",
            "NOTE TO SELLER — not for the listing:",
            "  Shipping the physical cards is what restores eBay's Item Not Received",
            "  protection; it does NOT protect against Item Not As Described, which is the",
            "  dispute code cards actually attract. Do not also message the codes: a buyer",
            "  who redeems from the message can file INAD and return the redeemed cards.",
        ]
    return "\n".join(lines) + "\n"


def manifest_text(lot: Lot) -> str:
    """The buyer's copy. One code per line and nothing else.

    NO HEADER, NO COUNT, NO COMMENTARY, because this file is pasted whole into a message or
    attached as-is, and anything that is not a code is something the buyer has to strip.
    """
    return "".join(code + "\n" for code in lot.codes)


def packing_text(lot: Lot) -> str:
    """What the operator does at the shelf."""
    lines = [
        f"LOT {lot.lot_id}",
        f"  venue     {lot.venue}",
        f"  delivery  {lot.delivery}",
        f"  codes     {lot.count}",
        "",
    ]
    if lot.delivery != DELIVERY_PHYSICAL:
        lines += [
            "DIGITAL LOT — nothing to pull, nothing to pack.",
            f"  Send {MANIFEST} to the buyer. The cards stay where they are.",
            "",
        ]
    else:
        lines += [
            "PULL",
            f"  Box {lot.box} — THE WHOLE BOX. {lot.count} card(s).",
            "",
            "  Every sellable code in this box is in this lot; that is enforced when the lot",
            "  is built, so there is nothing in the box to leave behind and nothing to sort.",
            "",
            "  COUNT THEM BEFORE THE PARCEL IS SEALED. A card left behind is a code the buyer",
            "  paid for and did not receive; a card added is a code sold twice.",
            "",
            "POSTAGE",
            "  ~1.78 g and 0.305 mm per card, so this lot is roughly",
            f"  {lot.count * 1.78 / 1000:.2f} kg and {lot.count * 0.305 / 10:.1f} cm of stack.",
            "  Under 0.25 inch total and 15 cards or fewer: eBay Standard Envelope, $0.78.",
            "  Anything thicker: USPS Ground Advantage. A 1,000-card lot is ~3.75 lb.",
            "",
        ]
    if lot.products_in:
        lines.append("MIX")
        for row in lot.products_in:
            mark = "PREMIUM  " if row["premium"] else "         "
            lines.append(f"  {mark}{row['count']:>5}  {row['display']}")
        lines.append("")
    premium = [r for r in lot.products_in if r["premium"]]
    if premium:
        lines += [
            "!! THIS LOT CONTAINS PREMIUM CODES.",
            "   A premium code lists at roughly 46x a booster code. Selling one inside a",
            "   bulk lot is the single most expensive mistake on this track. Check that",
            "   this was deliberate before you ship.",
            "",
        ]
    lines += [
        "AFTER THE SALE",
        "  Mark the codes delivered once the buyer has them, so a later re-scan cannot",
        "  return them to stock.",
    ]
    return "\n".join(lines) + "\n"


def write_artefacts(lot: Lot) -> Dict[str, str]:
    """Write the three files plus a machine-readable receipt. Returns {name: path}."""
    directory = lot_dir(lot.lot_id)
    directory.mkdir(parents=True, exist_ok=True)
    written = {}
    for name, text in (
        (LISTING, listing_text(lot)),
        (MANIFEST, manifest_text(lot)),
        (PACKING, packing_text(lot)),
    ):
        target = directory / name
        store_files.write_atomic(target, text.encode("utf-8"))
        written[name] = str(target)
    receipt = {
        "lot_id": lot.lot_id,
        "scope": lot.scope,
        "delivery": lot.delivery,
        "venue": lot.venue,
        "box": lot.box,
        "count": lot.count,
        "by_product": lot.products_in,
        "sets": lot.sets_in,
        "built_at": ledger.now(),
    }
    store_files.write_json(directory / RECEIPT, receipt)
    written[RECEIPT] = str(directory / RECEIPT)
    return written


def read_lots() -> List[dict]:
    """Every built lot's receipt, newest first. Never reads a manifest — codes stay put."""
    directory = lots_dir()
    if not directory.is_dir():
        return []
    out = []
    for child in sorted(directory.iterdir(), reverse=True):
        receipt = child / RECEIPT
        if receipt.is_file():
            payload = store_files.read_json(receipt, default=None)
            if payload:
                out.append(payload)
    return out
