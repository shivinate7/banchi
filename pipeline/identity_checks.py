"""Four stored-data checks the owner took whole, from the archive-refusal-mechanization analysis (PR #444, unmerged)'s
own class 1 through class 4. Each one reads a card's already-stored fields — `name`,
`number`, `set_name` — and needs no catalogue and no network. Each is a REVIEW SIGNAL, never
a repair: D234's own worked example is a genuine secret rare that a denominator or
digit-count check would ALSO flag, correctly, because the check can only say "uncommon for
this set, look at the photo," never "wrong." `CLAUDE.md`'s own boundary — two agreeing
signals release a claim (D146), one disagreeing signal never resolves one on its own — is
why nothing here writes a card.

PURE FUNCTIONS OVER PLAIN DATA, NO STORE IMPORT. Every check takes an iterable of
`CardRecord` and returns a list of `Flag`. `cli/cmd_cards.py`'s new `checks` subcommand is
the one caller that reads the real store and hands it rows shaped this way, through the
same `_read_only`/raw-`sqlite3` door `name` and `audit` already use — this module never
opens a database and is exercised in tests with nothing but literal tuples.

WHY THESE FOUR AND NOT THE FIFTH THE ANALYSIS ALSO MEASURED. A blank number is common in
every Riftbound set this store holds (3.6% to 11%, measured in the cited entry) and most
resolve fine on name alone. A check that fires on one in ten cards that are actually fine is
spent (`CLAUDE.md`'s cry-wolf rule) — so blankness is deliberately absent here. The SKU
self-contradiction check (two copies of one SKU disagreeing about the card's number) is a
different, more speculative build, kept separate on the owner's own ruling; it lives in
`pipeline/sku_contradictions.py`, not here.

Cites D146, D173, D234, the archive-refusal-mechanization analysis, D-archive-store-checks (this
module's own decision entry).
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from store.numbers import strip_set_code

# Class 1 — a name too long to be a card name at all. Measured over the owner's store,
# 3,510 names: the next-longest real name is 35 characters; the one known defect is 152.
# Sixty sits in the 117-character gap between them — well above every name this store has
# ever held, well below the one that is not a name at all. Not tuned to the defect's own
# length: a threshold set AT 152 would catch only cards at least that long, which is one
# fewer subject than a threshold that catches anything unreasonable.
LONG_NAME_THRESHOLD = 60

# Class 4's cutoff. `difflib.get_close_matches`'s own default (0.6) is far too loose for
# card names — it would match unrelated short names by chance. 0.82 is the ratio the cited
# analysis measured against the owner's store: tight enough that `Grandmaster at Arms` and
# `Jax, Grandmaster at Arms` still register (a champion's short title against its own full
# name, the archive-refusal-mechanization analysis's own "resolved fine" case), loose enough to catch a
# single glued letter (`Shadbow`/`Shadow`).
NAME_MATCH_CUTOFF = 0.82

# A clean `NNN/NNN` or bare `NNN` shape, after `strip_set_code` has removed a glued set
# prefix. Anything that does not match this — two slashes, a bullet, a plus sign — is a
# different, messier defect than classes 2 and 3 name, and is left for a human rather than
# forced through a denominator or digit-count comparison that was never built for it.
_CLEAN_NUMBER = re.compile(r"^(\d+)(?:/(\d+))?$")


@dataclass(frozen=True)
class CardRecord:
    """The five stored fields these checks read. `key` is whatever the caller uses to name
    a position — `cards audit`'s own `(box, index)` string, a SKU, anything unique enough to
    report back. Nothing here is written to.
    """

    key: str
    name: Optional[str] = None
    number: Optional[str] = None
    set_name: Optional[str] = None
    sku: Optional[str] = None
    game: Optional[str] = None


@dataclass(frozen=True)
class Flag:
    """One card, one reason, one sentence a human can act on without re-deriving it."""

    key: str
    check: str
    detail: str


def flag_long_names(
    cards: Iterable[CardRecord], threshold: int = LONG_NAME_THRESHOLD
) -> List[Flag]:
    """Class 1. A name longer than `threshold` is rules text or a transcription error, not
    a title. No grouping, no catalogue — a plain length comparison per card.
    """
    out: List[Flag] = []
    for card in cards:
        name = card.name or ""
        if len(name) > threshold:
            out.append(
                Flag(
                    card.key,
                    "long_name",
                    f"name is {len(name)} characters, over the {threshold}-character "
                    f"threshold: {name[:80]!r}{'…' if len(name) > 80 else ''}",
                )
            )
    return out


def _numbers_by_set(cards: Iterable[CardRecord]) -> Dict[str, List[CardRecord]]:
    by_set: Dict[str, List[CardRecord]] = {}
    for card in cards:
        set_name = (card.set_name or "").strip()
        number = (card.number or "").strip()
        if not set_name or not number:
            continue
        by_set.setdefault(set_name, []).append(card)
    return by_set


def flag_denominator_outliers(cards: Iterable[CardRecord]) -> List[Flag]:
    """Class 2. This store does not carry a set's own printed total. The total is implied
    by the denominator every OTHER card of that set already carries — the dominant
    denominator, by count. A card whose denominator disagrees is a candidate for review,
    never an auto-repair (D234's `133/132` counter-example applies here as much as it
    applies at the archive).
    """
    out: List[Flag] = []
    for set_name, in_set in _numbers_by_set(cards).items():
        denom_counts: Dict[str, int] = {}
        parsed = []
        for card in in_set:
            match = _CLEAN_NUMBER.match(strip_set_code(card.number))
            if not match or not match.group(2):
                continue
            denom = match.group(2)
            denom_counts[denom] = denom_counts.get(denom, 0) + 1
            parsed.append((card, denom))
        if len(denom_counts) <= 1:
            continue
        dominant = max(denom_counts, key=lambda d: denom_counts[d])
        for card, denom in parsed:
            if denom != dominant:
                out.append(
                    Flag(
                        card.key,
                        "denominator_outlier",
                        f"{card.number!r} in {set_name!r}: denominator {denom!r} against "
                        f"this set's dominant {dominant!r} ({denom_counts[dominant]} of "
                        f"{sum(denom_counts.values())} numbered cards)",
                    )
                )
    return out


def flag_digit_count_outliers(cards: Iterable[CardRecord]) -> List[Flag]:
    """Class 3. A number whose numerator carries more digits than the set's own dominant
    digit count — `0934` where every other card in the set reads three digits. Cheaper than
    class 2: no denominator needed, a plain digit-count comparison over the set's own
    numerators. Only MORE digits than the dominant count is flagged — fewer digits is a
    different, shorter-read defect this check was not built for.
    """
    out: List[Flag] = []
    for set_name, in_set in _numbers_by_set(cards).items():
        length_counts: Dict[int, int] = {}
        parsed = []
        for card in in_set:
            match = _CLEAN_NUMBER.match(strip_set_code(card.number))
            if not match:
                continue
            numerator = match.group(1)
            length_counts[len(numerator)] = length_counts.get(len(numerator), 0) + 1
            parsed.append((card, numerator, len(numerator)))
        if not length_counts:
            continue
        dominant_len = max(length_counts, key=lambda length: length_counts[length])
        for card, _numerator, length in parsed:
            if length > dominant_len:
                out.append(
                    Flag(
                        card.key,
                        "digit_count_outlier",
                        f"{card.number!r} in {set_name!r}: {length} digits against this "
                        f"set's dominant {dominant_len} ({length_counts[dominant_len]} of "
                        f"{sum(length_counts.values())} numbered cards)",
                    )
                )
    return out


def flag_near_duplicate_names(
    cards: Iterable[CardRecord], cutoff: float = NAME_MATCH_CUTOFF
) -> List[Flag]:
    """Class 4. A captured name compared only against every OTHER distinct name this store
    already holds in the SAME set — no catalogue, no network, just `cards.name` against
    itself. A close match one edit away is a likely misread, but it is still routed to a
    human rather than substituted: a set can legitimately hold two names one letter apart
    (an errata, a champion's short title beside its own full name).
    """
    out: List[Flag] = []
    by_set: Dict[str, List[CardRecord]] = {}
    for card in cards:
        set_name = (card.set_name or "").strip()
        name = (card.name or "").strip()
        if not set_name or not name:
            continue
        by_set.setdefault(set_name, []).append(card)

    for set_name, in_set in by_set.items():
        distinct_names = sorted({card.name.strip() for card in in_set})
        for card in in_set:
            name = card.name.strip()
            others = [n for n in distinct_names if n != name]
            matches = difflib.get_close_matches(name, others, n=1, cutoff=cutoff)
            if matches:
                out.append(
                    Flag(
                        card.key,
                        "near_duplicate_name",
                        f"{name!r} in {set_name!r} is one edit from {matches[0]!r}, a "
                        "different name this store already holds in the same set",
                    )
                )
    return out


#: Every check, in the order the archive-refusal-mechanization analysis (PR #444, unmerged) numbers its classes.
ALL_CHECKS = {
    "long_name": flag_long_names,
    "denominator_outlier": flag_denominator_outliers,
    "digit_count_outlier": flag_digit_count_outliers,
    "near_duplicate_name": flag_near_duplicate_names,
}


def run_all(cards: Iterable[CardRecord]) -> Dict[str, List[Flag]]:
    """Every check, run once over the same card list. `cards` is consumed once per check
    when it is a generator, so a caller passing a generator gets nothing from the second
    check onward — always pass a list or tuple.
    """
    cards = list(cards)
    return {name: check(cards) for name, check in ALL_CHECKS.items()}
