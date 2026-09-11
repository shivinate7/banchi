"""The pricing decision, parsed — the corpus's parser, and the shape one run is priced with.

D9 forbids the pipeline from guessing what happens to a sub-threshold card. That could have
been a `--sub-threshold` flag, and it deliberately is not: a screen (`#/pricing`) sits in
front of the same choice, and a flag would make that screen a second code path
reimplementing a decision the CLI already knows how to make. A DOCUMENT makes it an editor
for a contract that already exists.

THE DOCUMENT IS `inventory/prices.json` (`pipeline/corpus.py`, D86) AND NOT A RUN FILE. This
module owns what an answer MEANS: `pipeline/corpus.py` projects the store-wide corpus into
one `Decisions` per run through `parse`, and `GET /pipeline/runs/<name>/pricing` answers a
screen with `to_payload` of exactly that projection. Nothing here reads or writes a file.

Two answers are not the same as no answer, and the distinction is the whole reason `emit`
can refuse:

  null        nobody has decided. `emit` refuses.
  "unlisted"  decided: leave it out of the import file. `emit` proceeds.

Shape, as the corpus projects it for a run:

    {
      "rule": "match",                     // match | undercut:PCT | markup:PCT
      "basis": "market",                   // market | low
      "sub_threshold": {"flat": "0.49"},   // "floor" | {"flat": "0.25"} — the store default
                                           // is flat $0.49 (D9, amended 2026-09-02)
      "overrides": {"8823901": "0.35"},
      "no_market_data": {"8823944": null}
    }
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional

from pipeline import pricing

FLOOR_CHOICE = "floor"
FLAT_KEY = "flat"
# WHERE THE POLICY LIVES, for the sentences below that name it. A string here rather than
# `corpus.FILENAME` because `pipeline/corpus.py` imports this module, so this one cannot
# import it back; the path is `store/files.py:prices_path()`'s, spelled for a person.
POLICY_FILE = "inventory/prices.json"

# ------------------------------------------------------------------------ withholding (D49)
#
# THE OWNER'S WORDS: "say i'm bullish on the price going up, and don't want to list any right
# now", and then "definitely want someway of flagging that i'm intentionally holding this card".
# Note "any" — the hold covers every copy, which it must: D7 makes copies fungible and the price
# per SKU, so a withhold cannot be per copy either.
#
# `withheld` AND NOT `held`, AND THE RENAME IS D26's. `store/master.py:Listing.held` already
# means copies TCGPLAYER is holding — the opposite direction — and `_listing_hold` in the
# capture server means a box may not be deleted. D26 renamed `removed` to `retired` for exactly
# this reason: a state that shares a word with an existing one makes both unreadable.
WITHHELD_KEY = "withheld"
NOTE_KEY = "note"
WATCH_KEY = "watch_above"

# HAND-AUTHORED IN D22'S SENSE, and deliberately disjoint from the two vocabularies this could
# be confused with: `master.RETIRE_REASONS` (the CARD left inventory) and
# `queues.STAND_DOWN_REASONS` (the QUESTION was closed). No word appears in two of the three.
#
# `next_batch` rather than the obvious `not_yet`, because `not_listing` is already a stand-down
# reason and the two would read as one word at the 10px a machine string is drawn at.
WITHHOLD_REASONS = ("bullish", "keeping", "next_batch")

# A bare `"unlisted"` in `overrides` is a withhold that carries no reason, and never invents
# one. That spelling exists because it is what a terminal user types and because `no_market_data`
# has accepted it since D9 — a second word for one idea is the drift D16 exists to catch.
UNSPECIFIED = ""


class MalformedDecisions(ValueError):
    """The file is not the contract this module reads."""


def _price(value, label: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise MalformedDecisions(f"{label}: {value!r} is not a price") from exc


def parse_live_cap(value) -> Optional[int]:
    """The cap ONE SEND asked for, as an integer of at least 1, or `None` for no cap.

    THIS VALIDATES A FLAG AND NO LONGER A STORED KEY (D7, amended 2026-09-08). `policy.live_cap`
    is deleted: the standing bound the operator retired on 2026-09-07 survived as a policy key
    for a day, silently answering four on any store whose corpus had ever been saved. The only
    caller now is `cli/cmd_emit.py:_cap_for`, over `--cap N`.

    IT IS A CEILING ON COPIES LIVE, not a send quantity — `pipeline/join.py:add_to_quantity`
    spends `live_cap - copies_out`, so a SKU already at or over the figure adds nothing and
    the report says by how much.

    REFUSED RATHER THAN CLAMPED where it is present and unusable, the same rule
    `check_threshold` follows: a value of `"four"` or `0` is somebody who meant something this
    cannot do. Zero in particular would emit nothing for every SKU and read as a silent
    pipeline rather than as a setting — omit the flag if the answer is "do not bound me".
    """
    if value is None:
        return None
    try:
        cap = int(str(value).strip())
    except (TypeError, ValueError):
        raise MalformedDecisions(f"--cap must be a whole number of copies, got {value!r}") from None
    if cap < 1:
        raise MalformedDecisions(
            f"--cap must be at least 1, got {cap} — omit the flag for no cap at all"
        )
    return cap


#: The most copies one `--quantity` may name. Nothing physical bounds it — the shelf does, at
#: emit time — but the figure reaches a child process's argv from a request, and an unbounded
#: integer there is an argv a request controls. Three digits is what the screen's field takes.
MAX_SEND_QUANTITY = 999


def parse_send_quantities(pairs) -> Dict[str, int]:
    """`--quantity SKU=N`, repeated, as SKU -> N (D7, amended 2026-09-11).

    A SEND QUANTITY, NOT A CEILING. `N` is how many copies of that card THIS press puts in the
    file, bounded at emit time by the copies on hand that are not already listed — never by
    what TCGplayer holds. `0` is allowed and means none of this card this press; it is not a
    hold and is remembered nowhere.

    REFUSED RATHER THAN CLAMPED where a pair is unusable, `parse_live_cap`'s rule: a SKU that
    is not a TCGplayer id, a figure that is not a whole number, a negative one, or the same SKU
    named twice with two answers is somebody who meant something this cannot do. An empty or
    absent list is the ordinary answer — every copy that can go, goes.
    """
    asked: Dict[str, int] = {}
    for pair in pairs or ():
        text = str(pair).strip()
        sku, sep, figure = text.partition("=")
        sku = sku.strip()
        if not sep or not sku.isdigit():
            raise MalformedDecisions(
                f"--quantity takes SKU=N with a numeric TCGplayer id, got {text!r}"
            )
        try:
            count = int(figure.strip())
        except ValueError:
            raise MalformedDecisions(
                f"--quantity {sku}: N must be a whole number of copies, got {figure.strip()!r}"
            ) from None
        if count < 0 or count > MAX_SEND_QUANTITY:
            raise MalformedDecisions(
                f"--quantity {sku}: N must be between 0 and {MAX_SEND_QUANTITY}, got {count}"
            )
        if sku in asked and asked[sku] != count:
            raise MalformedDecisions(
                f"--quantity names {sku} twice, as {asked[sku]} and {count} — say it once"
            )
        asked[sku] = count
    return asked


def parse_sub_threshold(value) -> Optional[pricing.Disposition]:
    """`None` means unset, which is not an error here — it is what `blocking` refuses on.

    PUBLIC BECAUSE THE CORPUS VALIDATES WITH IT AT READ TIME (`pipeline/corpus.py:Corpus.parse`),
    so a malformed policy refuses where a command already catches `MalformedDecisions` rather
    than in the middle of an `emit`. From the CLI the `None` branch is unreachable now — the
    corpus applies its default before this is called — and it stays because T5 pins the
    parser's contract independently of who calls it.
    """
    if value is None:
        return None
    if value == FLOOR_CHOICE:
        return pricing.flat_floor()
    if isinstance(value, dict) and FLAT_KEY in value:
        # A flat price typed into this run's decision file IS the deliberate act that
        # `pricing.flat_price` guards against doing by accident, so the guard is waived
        # here and the number is reported instead — see `Decisions.warnings`.
        return pricing.flat_price(
            _price(value[FLAT_KEY], "sub_threshold.flat"), allow_below_floor=True
        )
    raise MalformedDecisions(
        f'sub_threshold: expected null, "{FLOOR_CHOICE}" or {{"{FLAT_KEY}": "0.25"}}, '
        f"got {value!r}"
    )


@dataclass(frozen=True)
class Withheld:
    """One SKU the operator is deliberately not listing, and why.

    NOT A RETIREMENT, NOT A STAND-DOWN, NOT A SALE, and the boundary is worth having in one
    place. D26's `retired` says the CARD left inventory: it takes a terminal state, its slot
    becomes a permanent gap, and it is gone. D37's stand-down says the QUESTION was closed:
    it writes `cleared_by_human` on a queue entry and nothing at all to the card. A withhold
    writes neither. The card does not move, does not change state, keeps its slot, keeps its
    photograph, and is sellable the moment the hold is lifted — what is refused is the
    LISTING, for this run, and nothing else.

    IT IS A CORPUS ROW KEYED BY SKU AND IT OUTLIVES EVERY RUN (D86). A hold used to live in
    the run's own file and die with it, so a second run over the same box started with none —
    the limit D49 recorded and the one that put three deliberate holds under a later price.
    It is one answer for the store now: every run over the card is held until the hold is
    lifted on `#/pricing`, and `pkmnscan prices show --held` is the cross-run view of what is
    being held.
    """

    reason: str = UNSPECIFIED
    note: str = ""
    watch_above: Optional[Decimal] = None

    def to_json(self):
        """Back to the file. The bare form round-trips BYTE-IDENTICALLY, deliberately: a hold
        typed by hand as `"unlisted"` must not silently become an object on the next join."""
        if not self.reason and not self.note and self.watch_above is None:
            return pricing.UNLISTED
        out = {WITHHELD_KEY: self.reason}
        if self.watch_above is not None:
            out[WATCH_KEY] = str(self.watch_above)
        # OMITTED RATHER THAN WRITTEN EMPTY, so a save cannot accrete `"note": ""` on every
        # held SKU forever — the corpus is rewritten on every `#/pricing` save and every join.
        if self.note:
            out[NOTE_KEY] = self.note
        return out

    @property
    def describe(self) -> str:
        parts = [WITHHELD_KEY + (f":{self.reason}" if self.reason else "")]
        if self.watch_above is not None:
            parts.append(f"watch>${self.watch_above}")
        if self.note:
            parts.append(self.note)
        return " ".join(parts)


def _withheld(value, label: str) -> Withheld:
    """A withhold out of either accepted shape: the bare string, or the object with a reason.

    A DICT WAS ALREADY A CLEAN REFUSAL AND NOT A TRACEBACK, which is what makes this a strict
    widening: before this, a dict reached `_price`, `Decimal(str({...}))` raised
    `InvalidOperation`, and the `except` below it turned that into `MalformedDecisions`.
    """
    if not isinstance(value, dict):
        return Withheld()
    reason = value.get(WITHHELD_KEY, UNSPECIFIED)
    if reason not in WITHHOLD_REASONS + (UNSPECIFIED,):
        raise MalformedDecisions(
            f"{label}: {reason!r} is not one of {', '.join(WITHHOLD_REASONS)}"
        )
    note = value.get(NOTE_KEY) or ""
    if not isinstance(note, str):
        raise MalformedDecisions(
            f"{label}.{NOTE_KEY}: expected a string, got {note!r}"
        )
    watch = value.get(WATCH_KEY)
    return Withheld(
        reason=reason,
        note=note.strip(),
        watch_above=None if watch is None else _price(watch, f"{label}.{WATCH_KEY}"),
    )


@dataclass
class Decisions:
    """One run's pricing decision. `path` is where it round-trips."""

    rule: pricing.Rule = pricing.MATCH
    basis: str = pricing.BASIS_MARKET
    sub_threshold: Optional[pricing.Disposition] = None
    # A PRICE OR A `Withheld`, which is the exact widening `no_market_data` already
    # carries on the line below: that field has held `None | UNLISTED | Decimal` since D9.
    overrides: Dict[str, object] = field(default_factory=dict)
    no_market_data: Dict[str, object] = field(default_factory=dict)

    # --------------------------------------------------------------------- reading

    @classmethod
    def parse(cls, payload: dict) -> "Decisions":
        if not isinstance(payload, dict):
            raise MalformedDecisions(
                f"expected an object, got {type(payload).__name__}"
            )

        overrides: Dict[str, object] = {}
        for sku, value in (payload.get("overrides") or {}).items():
            # `null` IS DROPPED AND NEVER ROUND-TRIPS, which is how a screen CLEARS a price or
            # a hold: write `null`, and the next join tidies the key away. There is deliberately
            # no delete verb anywhere for this.
            if value is None:
                continue
            if isinstance(value, dict) or str(value).strip().lower() == pricing.UNLISTED:
                overrides[str(sku)] = _withheld(value, f"overrides.{sku}")
            else:
                overrides[str(sku)] = _price(value, f"overrides.{sku}")

        unpriced: Dict[str, object] = {}
        for sku, value in (payload.get("no_market_data") or {}).items():
            if value is None:
                unpriced[str(sku)] = None
            elif str(value).strip().lower() == pricing.UNLISTED:
                unpriced[str(sku)] = pricing.UNLISTED
            else:
                unpriced[str(sku)] = _price(value, f"no_market_data.{sku}")

        return cls(
            rule=pricing.Rule.parse(payload.get("rule", pricing.RULE_MATCH)),
            basis=pricing.check_basis(payload.get("basis", pricing.BASIS_MARKET)),
            sub_threshold=parse_sub_threshold(payload.get("sub_threshold")),
            overrides=overrides,
            no_market_data=unpriced,
        )

    # --------------------------------------------------------------------- the wire shape

    def to_payload(self) -> dict:
        """This decision as the document a screen reads — `GET /pipeline/runs/<name>/pricing`.

        THE BARE FORMS ROUND-TRIP BYTE-IDENTICALLY, deliberately: a hold typed by hand as
        `"unlisted"` comes back as `"unlisted"` and a price as the string it was typed as, so
        a screen drawing this beside the corpus draws the same spelling the file holds.
        """
        if self.sub_threshold is None:
            sub = None
        elif self.sub_threshold.kind == pricing.FLAT_FLOOR:
            sub = FLOOR_CHOICE
        else:
            sub = {FLAT_KEY: str(self.sub_threshold.price)}

        return {
            "rule": str(self.rule),
            "basis": self.basis,
            "sub_threshold": sub,
            # `sorted()` OVER A MIXED-VALUE DICT IS SAFE: it compares the tuples and reaches
            # the second element only on a first-element tie, and dict keys are unique. So a
            # `Withheld` beside a `Decimal` never has to be ordered against one.
            "overrides": {
                sku: (value.to_json() if isinstance(value, Withheld) else str(value))
                for sku, value in sorted(self.overrides.items())
            },
            "no_market_data": {
                sku: (None if value is None else str(value))
                for sku, value in sorted(self.no_market_data.items())
            },
        }

    # --------------------------------------------------------------------- checking

    @property
    def unanswered(self) -> List[str]:
        return sorted(sku for sku, value in self.no_market_data.items() if value is None)

    def blocking(self, sub_threshold_skus) -> List[str]:
        """Why `emit` must refuse, in the order a human would want to read it."""
        reasons = []
        if self.sub_threshold is None and list(sub_threshold_skus):
            reasons.append(
                f"{len(list(sub_threshold_skus))} sub-threshold SKU(s) and "
                f'sub_threshold is still null — set it to "{FLOOR_CHOICE}" or '
                f'{{"{FLAT_KEY}": "0.49"}} under policy in {POLICY_FILE}, or on #/pricing'
            )
        if self.unanswered:
            reasons.append(
                f"{len(self.unanswered)} SKU(s) with no market price are unanswered in "
                f'{POLICY_FILE}: give each a price or "{pricing.UNLISTED}" on #/pricing '
                f"({', '.join(self.unanswered[:6])})"
            )
        return reasons

    @property
    def warnings(self) -> List[str]:
        """Deliberate choices worth restating at the moment a file is written.

        THE TWO PRICE WARNINGS NAME D9's $0.40 AS A LABOR BAR AND NOT AS THE FLOOR (D9,
        amended 2026-09-09). The clamp moved to the store's own cut-off and this figure did
        not: it is the $60/hr derivation — ~20s a pull, 0.8675 x $0.40 clears it — which is a
        fact about the operator's hour rather than about their policy, so a store that sets its
        cut-off below it is told once and never refused. Calling it "the floor" here while the
        floor was $0.29 would have made both sentences false, which is the drift the rename
        closes; a `Decisions` has no store behind it and could not read the real floor anyway.
        """
        out = []
        sub = self.sub_threshold
        if (
            sub is not None
            and sub.kind == pricing.FLAT_PRICE
            and sub.price < pricing.FLOOR
        ):
            out.append(
                f"sub_threshold is ${sub.price}, below D9's ${pricing.FLOOR} labor bar — "
                f"deliberate, since it is written in {POLICY_FILE}, but D9 says a sale there "
                f"loses money including labor"
            )
        # `isinstance` GUARD, AND IT IS A CRASH FIX RATHER THAN TIDINESS. This comparison ran
        # over every override value, so the first re-join after a hold was set would compare a
        # `Withheld` against a `Decimal` and raise `TypeError` out of a property — from inside
        # `join`, which is the free re-runnable command an operator presses without thinking.
        below = sorted(
            sku
            for sku, value in self.overrides.items()
            if isinstance(value, Decimal) and value < pricing.FLOOR
        )
        if below:
            out.append(
                f"{len(below)} per-SKU override(s) below D9's ${pricing.FLOOR} labor bar: "
                f"{', '.join(below[:6])}"
            )
        unlisted = sorted(
            sku for sku, value in self.no_market_data.items()
            if value == pricing.UNLISTED
        )
        if unlisted:
            out.append(
                f"{len(unlisted)} unpriced SKU(s) deliberately left unlisted: "
                f"{', '.join(unlisted[:6])}"
            )
        # A WARNING AND NOT A BLOCKER, because `blocking` refuses on the ABSENCE of an answer
        # and a withhold is an answer. `cli/cmd_emit.py` prints this at the moment an import
        # file is committed, which is the moment a person can still change their mind.
        held = self.withheld()
        if held:
            out.append(
                f"{len(held)} SKU(s) withheld — every copy stays unlisted and no row is "
                "written: "
                + ", ".join(
                    f"{sku} ({value.reason or 'no reason'})"
                    for sku, value in sorted(held.items())[:6]
                )
            )
        return out

    @property
    def describe(self) -> str:
        sub = "UNSET" if self.sub_threshold is None else self.sub_threshold.describe
        # THREE COUNTS RATHER THAN ONE, because `overrides` now holds two different answers
        # and this line is what an operator reads to check the file. One number covering both
        # would say "12 overrides" over eight prices and four holds, which is the one thing
        # this line exists to make checkable.
        return (
            f"rule={self.rule} basis={self.basis} sub_threshold={sub} "
            f"overrides={len(self.dispositions())} withheld={len(self.withheld())} "
            f"no_market_data={len(self.no_market_data)}"
        )

    def dispositions(self) -> Dict[str, pricing.Disposition]:
        """`overrides` PRICES, in the shape `join.prices_for` consumes.

        WITHHOLDS ARE DELIBERATELY ABSENT FROM THIS MAPPING, AND THAT IS LOAD-BEARING RATHER
        THAN TIDY. `cli/cmd_emit.py` refuses the whole run when this mapping names a SKU the
        batch does not hold, and `pipeline/join.py:prices_for` refuses again per game. A
        withheld SKU is precisely the SKU most likely to go stale — it was withheld BECAUSE it
        is not being listed — so letting holds reach those two checks would mean the act of
        holding a card back eventually breaks `emit` for the entire run, with no control
        anywhere able to clear it. Keeping them out is what makes a hold survivable.
        """
        return {
            sku: pricing.flat_price(value, allow_below_floor=True)
            for sku, value in self.overrides.items()
            if not isinstance(value, Withheld)
        }

    def withheld(self) -> Dict[str, "Withheld"]:
        """The SKUs held out of this run's import files, by SKU."""
        return {
            sku: value
            for sku, value in self.overrides.items()
            if isinstance(value, Withheld)
        }

    def watches(self, matches) -> List[str]:
        """Withheld SKUs whose market price has passed the number the operator named.

        BUILT RATHER THAN DEFERRED, and the argument that nearly deferred it is worth keeping
        because it was wrong in an instructive way: a watch looked pointless on the grounds
        that it can only fire while somebody is already looking at the price. They are not. A
        re-join is driven from `#/runs` (D39), `join` is free and re-runnable precisely so it
        can be pointed at a REFRESHED export, and that is the only moment a market price has
        moved and therefore the only moment a watch has anything to say.

        A method and not a `warnings` entry: `warnings` is a zero-argument property and cannot
        see a price. `matches` is `{sku: SkuMatch}`, `cli/resolve.py:Resolved.matches`.
        """
        out: List[str] = []
        for sku, value in sorted(self.withheld().items()):
            if value.watch_above is None or sku not in matches:
                continue
            match = matches[sku]
            market = match.market_price
            if market is None or market < value.watch_above:
                continue
            out.append(
                f"{sku} {match.name} — market ${market} is past the "
                f"${value.watch_above} you set"
            )
        return out
