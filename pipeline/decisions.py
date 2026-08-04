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


@dataclass
class Decisions:
    """One run's pricing decision. `path` is where it round-trips."""

    rule: pricing.Rule = pricing.MATCH
    basis: str = pricing.BASIS_MARKET
    sub_threshold: Optional[pricing.Disposition] = None
    overrides: Dict[str, Decimal] = field(default_factory=dict)
    no_market_data: Dict[str, object] = field(default_factory=dict)

    # --------------------------------------------------------------------- reading

    @classmethod
    def parse(cls, payload: dict) -> "Decisions":
        if not isinstance(payload, dict):
            raise MalformedDecisions(
                f"expected an object, got {type(payload).__name__}"
            )

        overrides: Dict[str, Decimal] = {}
        for sku, value in (payload.get("overrides") or {}).items():
            if value is None:
                continue
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
            "overrides": {
                sku: str(price) for sku, price in sorted(self.overrides.items())
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
        below = sorted(
            sku for sku, price in self.overrides.items() if price < pricing.FLOOR
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
        return out

    @property
    def describe(self) -> str:
        sub = "UNSET" if self.sub_threshold is None else self.sub_threshold.describe
        return (
            f"rule={self.rule} basis={self.basis} sub_threshold={sub} "
            f"overrides={len(self.overrides)} no_market_data={len(self.no_market_data)}"
        )

    def dispositions(self) -> Dict[str, pricing.Disposition]:
        """`overrides` in the shape `join.prices_for` consumes."""
        return {
            sku: pricing.flat_price(price, allow_below_floor=True)
            for sku, price in self.overrides.items()
        }
