"""`decisions.json` — the pricing decision, as a file rather than as a flag.

D9 forbids the pipeline from guessing what happens to a sub-threshold card. That could have
been a `--sub-threshold` flag, and it deliberately is not: build-order step 7 puts a React
screen in front of the same choice, and a flag would make that screen a second code path
reimplementing a decision the CLI already knows how to make. A file makes it an editor for
a contract that already exists.

`join` writes this file pre-filled with every SKU that needs an answer and the run-wide
choice UNSET. You edit it; `emit` reads it and refuses to write while anything is still
unanswered. Nothing here is ever defaulted on your behalf — that is the entire point.

MERGE, NEVER CLOBBER. `join` is free and re-runnable (v2 §2), so it will be re-run after a
review is cleared or an export is refreshed, and a re-run that overwrote this file would
silently discard the decisions you made between the two. So a second write adds newly
discovered SKUs, preserves every existing value, and reports what it added. The same
instinct as "a human-cleared identification is permanent" in §4.6: a human answer outranks
a machine's willingness to ask again.

Two answers are not the same as no answer, and the distinction is the whole reason `emit`
can refuse:

  null        nobody has decided. `emit` refuses.
  "unlisted"  decided: leave it out of the import file. `emit` proceeds.

Shape:

    {
      "rule": "match",              // match | undercut:PCT | markup:PCT
      "basis": "market",            // market | low
      "sub_threshold": null,        // "floor" | {"flat": "0.25"} — MUST be set
      "overrides": {"8823901": "0.35"},
      "no_market_data": {"8823944": null}
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional

from pipeline import pricing

FILENAME = "decisions.json"

FLOOR_CHOICE = "floor"
FLAT_KEY = "flat"

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

# Keys the writer emits to explain the file to whoever opens it. JSON has no comments, and
# `.claude/settings.json` already establishes the `_`-prefixed convention in this repo.
_NOTE = "_note"
_NOTES = {
    "rule": "match | undercut:PCT | markup:PCT",
    "basis": "market (TCG Market Price) | low (TCG Low Price)",
    "sub_threshold": (
        'REQUIRED before emit: "floor" for every sub-threshold card at the $0.40 floor, '
        'or {"flat": "0.25"} for a price chosen for this run.'
    ),
    "overrides": "Per-SKU price. Works above or below the threshold.",
    "no_market_data": (
        "The catalog has no price for these. Give each a price, or \"unlisted\" to leave "
        "it out of the file. null means undecided and emit will refuse."
    ),
}


class MalformedDecisions(ValueError):
    """The file is not the contract this module reads."""


def _price(value, label: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise MalformedDecisions(f"{label}: {value!r} is not a price") from exc


def _parse_sub_threshold(value) -> Optional[pricing.Disposition]:
    """`None` means unset, which is not an error here — it is what `emit` refuses on."""
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

    IT LIVES IN THE RUN AND DIES WITH IT. `decisions.json` is per-run (`cli/runs.py`), so a
    hold survives every re-join of its own run — which is where it does its work, since a box
    is identified once and re-joined many times — and a SECOND run over the same box starts
    with none. That is a real limit rather than an oversight; the screen says so in words and
    D49 records the durable-home options it deliberately did not build.
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
        # OMITTED RATHER THAN WRITTEN EMPTY, so a re-join cannot accrete `"note": ""` on every
        # held SKU forever — `join` is free and re-runnable and rewrites this file every time.
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
            sub_threshold=_parse_sub_threshold(payload.get("sub_threshold")),
            overrides=overrides,
            no_market_data=unpriced,
        )

    @classmethod
    def read(cls, path) -> "Decisions":
        path = Path(path)
        try:
            payload = json.loads(path.read_text("utf-8"))
        except json.JSONDecodeError as exc:
            raise MalformedDecisions(f"{path}: {exc}") from exc
        return cls.parse(payload)

    # --------------------------------------------------------------------- writing

    def to_payload(self) -> dict:
        if self.sub_threshold is None:
            sub = None
        elif self.sub_threshold.kind == pricing.FLAT_FLOOR:
            sub = FLOOR_CHOICE
        else:
            sub = {FLAT_KEY: str(self.sub_threshold.price)}

        return {
            _NOTE: _NOTES,
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

    def write(self, path) -> None:
        Path(path).write_text(
            json.dumps(self.to_payload(), indent=2) + "\n", "utf-8"
        )

    # --------------------------------------------------------------------- merging

    def add_unpriced(self, skus) -> List[str]:
        """Record SKUs the catalog has no price for. Existing answers are never touched."""
        added = []
        for sku in skus:
            if sku not in self.no_market_data:
                self.no_market_data[sku] = None
                added.append(sku)
        return added

    def prune(self, known_skus) -> List[str]:
        """Drop `no_market_data` entries for SKUs this run does not contain.

        Only unanswered (`null`) entries are dropped. An answered one is kept even when the
        SKU is absent, because a card that failed to identify this run will identify next
        run, and re-asking a question you already answered is the merge failure this class
        exists to avoid.
        """
        known = set(known_skus)
        stale = [
            sku
            for sku, value in self.no_market_data.items()
            if sku not in known and value is None
        ]
        for sku in stale:
            del self.no_market_data[sku]
        return stale

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
                f'{{"{FLAT_KEY}": "0.25"}} in {FILENAME}'
            )
        if self.unanswered:
            reasons.append(
                f"{len(self.unanswered)} SKU(s) with no market price are unanswered in "
                f'{FILENAME}: give each a price or "{pricing.UNLISTED}" '
                f"({', '.join(self.unanswered[:6])})"
            )
        return reasons

    @property
    def warnings(self) -> List[str]:
        """Deliberate choices worth restating at the moment a file is written."""
        out = []
        sub = self.sub_threshold
        if (
            sub is not None
            and sub.kind == pricing.FLAT_PRICE
            and sub.price < pricing.FLOOR
        ):
            out.append(
                f"sub_threshold is ${sub.price}, below the ${pricing.FLOOR} floor — "
                f"deliberate, since it is written in {FILENAME}, but D9 says a sale there "
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
                f"{len(below)} per-SKU override(s) below the ${pricing.FLOOR} floor: "
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

    def stale_overrides(self, known_skus) -> List[str]:
        """Price overrides naming a SKU this run does not contain.

        REPORTED, NEVER DROPPED. `prune`'s rule is about an UNANSWERED entry and an override is
        an answer — but a stale one is a hard refusal at emit time (`sku_dispositions names
        SKUs not in this batch`) naming a bare SKU with no card, no name and no box, and any
        of a retirement, a mid-box delete, a narrower export or a re-routed review can produce
        one. Naming them is what lets a screen offer to clear them.

        Holds are not included, because `dispositions()` excludes them and they cannot refuse.
        """
        known = set(known_skus)
        return sorted(sku for sku in self.dispositions() if sku not in known)

    def watches(self, matches) -> List[str]:
        """Withheld SKUs whose market price has passed the number the operator named.

        BUILT RATHER THAN DEFERRED, and the argument that nearly deferred it is worth keeping
        because it was wrong in an instructive way: a watch looked pointless on the grounds
        that it can only fire while somebody is already looking at the price. They are not. A
        re-join is driven from `#/runs` (D39), `join` is free and re-runnable precisely so it
        can be pointed at a REFRESHED export, and that is the only moment a market price has
        moved and therefore the only moment a watch has anything to say.

        A method and not a `warnings` entry: `warnings` is a zero-argument property and cannot
        see a price. `matches` is `{sku: SkuMatch}`, the same shape `stale_overrides` is given
        the keys of.
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
