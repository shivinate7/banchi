"""One forgiving matcher, ported from `app/src/kit/match.ts` (the owner's ruling, 2026-09-23,
FLT-06/04): name words in any order, card numbers with or without leading zeros, a hyphen
standing for the slash, accents folded, punctuation folded, SKUs and box names.

THE RULES ARE STATED IN `kit/match.ts`'S OWN DOCSTRING AND ARE NOT RESTATED HERE. This module
is a same-behaviour port, not a second design — `scripts/match-selftest.py` proves the two
agree by running every row of `app/src/kit/match.cases.json` (the case table the filtering
lane writes) through both. Where the two disagree, this file is wrong; fix it here, never the
case table.

STDLIB ONLY. `unicodedata` gives NFKC/NFKD and combining-mark removal without the `regex`
package's `\\p{L}`/`\\p{N}` classes — `requirements.txt`'s own "Deliberately absent" section is
the standing reason no dependency is added for this. `str.isalpha()` is Unicode-aware in
Python and stands in for `\\p{L}` closely enough, matching `kit/match.ts`'s own `\\p{L}` (its
`NUMBER_SHAPE`/etc. carry the `u` flag, which widens `\\p{L}` to every Unicode letter). DIGITS
ARE THE ONE PLACE THAT SUBSTITUTION BREAKS (S4, the Opus review, 2026-09-25): `str.isdigit()`
and Python's bare `\\d` are BOTH Unicode-aware, but JS's `\\d` is not — it is always `[0-9]`,
`u` flag or not, because JS's Unicode regex mode widens `\\p{...}` property escapes and does
nothing to `\\d` itself. So every digit test in this file (`_has_digit`, `_DIGITS_ONLY`,
`_SKU_SHAPE`, `_HYPHEN_BETWEEN_DIGITS`, and the two digit runs inside `_drop_leading_zeros`/
`_number_shape_ok`) is deliberately ASCII-only (`_ASCII_DIGITS`, or a `[0-9]` character class
rather than `\\d`), even though nothing else here is. `str.isalnum()` (used only inside
`fold_text`, never for a digit-specific decision) stands in for `\\p{L}`/`\\p{N}` combined, and
is left Unicode-aware on purpose — it is what a query keeps rather than what it treats as a
number, so the same asymmetry does not apply to it.

A KNOWN, UNFIXED GAP THE ASCII FIX DOES NOT TOUCH: `kit/match.ts:foldText` deletes every
Unicode MARK outright (`.replace(/\\p{M}+/gu, '')`), whatever its combining class. This
file's own mark strip (`unicodedata.combining(ch) != 0`, inside `fold_text`) removes only a
mark with a NON-ZERO canonical combining class — a genuine COMBINING mark, the kind NFKD
produces for an accent. A mark whose class IS zero ("ccc-0", a SPACING mark, e.g. Devanagari's
own vowel signs) is not a combining mark by that test, so it survives to the next step
instead — and since a Mark character is never `str.isalnum()`, that step folds it into a
WORD BREAK (one space) rather than deleting it, splitting a word the JS side would have kept
joined. No case in `app/src/kit/match.cases.json` has ever needed a ccc-0 mark folded, so
this is recorded rather than chased: `docs/decisions/D271-one-forgiving-search-matcher.md`
carries it.

USED TWO WAYS. `scripts/match-selftest.py` calls `match_query` directly against the generic
`MatchFields` shape (text/numbers/skus/boxes), the same contract `kit/match.ts` takes.
`server/capture_server.py:_match_rank` calls the lower-level `fold_text`/`canonical_number`
primitives on the SIX fields it has always ranked (name, number, sku, set_hint, note, the
composed key), because that function keeps its own three-tier rank (exact number, name
prefix, substring) rather than a plain boolean — `do_search`'s sort order depends on the
three tiers staying distinct, which a single `match_query() -> bool` cannot express.

PURE. No I/O, no store, no network — the same function answers in a script and in the server.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, Iterable, List, Optional, Sequence, TypedDict, Union

Number = Union[str, int, float, None]


class MatchFields(TypedDict, total=False):
    """One row a search may match, grouped by how each field is compared — the same shape
    `app/src/kit/match.ts`'s own `MatchFields` type declares."""

    text: Sequence[Optional[str]]
    numbers: Sequence[Optional[str]]
    skus: Sequence[Number]
    boxes: Sequence[Dict[str, object]]


_APOSTROPHES = re.compile(r"['’ʼ`´]")
# ASCII DIGITS ONLY (S4, the Opus review, 2026-09-25), MATCHING `\d` ON THE OTHER SIDE.
# `app/src/kit/match.ts`'s own `\d` is JS regex syntax, which is ALWAYS `[0-9]` — the `u`
# flag on `NUMBER_SHAPE`/`SKU_SHAPE`/`DIGITS`/`HAS_DIGIT` widens `\p{L}` to every Unicode
# letter, but it does nothing to `\d`, which JS has no Unicode-digit mode for at all.
# Python's bare `\d` (no `re.ASCII`) and `str.isdigit()` are both Unicode-aware — `"५"`
# (Devanagari digit five, U+096B) is `True` on both and NFKC leaves it untouched (it is not
# a compatibility decomposition of an ASCII digit, unlike a full-width `５`, which NFKC
# already folds before either side ever sees it) — so a query built from a real Unicode
# digit would have canonicalized as a number on the SERVER and stayed inert TEXT in the
# BROWSER: the one place this repo's own two-implementation contract could silently break.
_ASCII_DIGITS = "0123456789"
_DIGITS_ONLY = re.compile(r"^[0-9]+$")
_ZEROS_ONLY = re.compile(r"^0+$")
_SKU_SHAPE = re.compile(r"^[0-9]{3,}$")
_HYPHEN_BETWEEN_DIGITS = re.compile(r"([0-9])-(?=[0-9])")


def fold_text(value: str) -> str:
    """Rule 1: NFKC, NFKD, no combining marks, lower case, no apostrophes, every other run of
    non-alphanumeric characters becomes one space, trimmed."""
    value = unicodedata.normalize("NFKC", str(value))
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = _APOSTROPHES.sub("", value)
    out: List[str] = []
    spaced = False
    for ch in value:
        if ch.isalnum():
            out.append(ch)
            spaced = False
        elif not spaced:
            out.append(" ")
            spaced = True
    return "".join(out).strip()


def compact_text(value: str) -> str:
    """Rule 1's compact form: the fold with no spaces."""
    return fold_text(value).replace(" ", "")


def _has_digit(value: str) -> bool:
    return any(ch in _ASCII_DIGITS for ch in value)


def _has_letter(value: str) -> bool:
    return any(ch.isalpha() for ch in value)


def _drop_leading_zeros(part: str) -> str:
    """The zeros in front of the first digit run go, stopping at the last digit: `054` is
    `54`, `tg05` is `tg5`, and a run of zeros alone (`000`) keeps its last one (`0`), because
    that last zero has no digit after it to license stripping it too — the same lookahead
    `kit/match.ts:dropLeadingZeros` reads off its own regex."""
    i = 0
    n = len(part)
    while i < n and part[i].isalpha():
        i += 1
    letters = part[:i]
    j = i
    while j < n - 1 and part[j] == "0" and part[j + 1] in _ASCII_DIGITS:
        j += 1
    return letters + part[j:]


def _hyphen_to_slash(value: str) -> str:
    """A hyphen directly between two digits may stand for the collector-number slash:
    `054-132` reads the same as `054/132`."""
    return _HYPHEN_BETWEEN_DIGITS.sub(r"\1/", value)


def canonical_number(value: str) -> str:
    """Rule 4: a collector number's canonical form. `054/132` and `54/132` are both `54/132`."""
    value = unicodedata.normalize("NFKC", str(value))
    return "/".join(_drop_leading_zeros(compact_text(part)) for part in value.split("/"))


def _number_shape_ok(part: str) -> bool:
    """One side of `NUMBER_SHAPE`: 0-6 leading letters, one or more digits, 0-2 trailing
    letters — nothing else."""
    i = 0
    n = len(part)
    letters = 0
    while i < n and part[i].isalpha() and letters < 6:
        i += 1
        letters += 1
    if i < n and part[i].isalpha():
        return False
    digits_start = i
    while i < n and part[i] in _ASCII_DIGITS:
        i += 1
    if i == digits_start:
        return False
    trailing = 0
    while i < n and part[i].isalpha() and trailing < 2:
        i += 1
        trailing += 1
    if i < n and part[i].isalpha():
        return False
    return i == n


def _is_number_shape(value: str) -> bool:
    parts = value.split("/")
    if len(parts) > 2:
        return False
    return all(_number_shape_ok(part) for part in parts)


class _NumberParts(TypedDict):
    whole: str
    first: str
    second: Optional[str]


class _Prepared(TypedDict):
    folded: List[str]
    compact: List[str]
    words: List[Dict[str, str]]
    numbers: List[_NumberParts]
    skus: List[str]


def _number_parts(canon: str) -> _NumberParts:
    if "/" in canon:
        first, second = canon.split("/", 1)
        return {"whole": canon, "first": first, "second": second}
    return {"whole": canon, "first": canon, "second": None}


def _present(values: Optional[Iterable]) -> List:
    return [v for v in (values or []) if v is not None and v != ""]


def _prepare(fields: MatchFields) -> _Prepared:
    box_names = [b.get("name") for b in (fields.get("boxes") or []) if b.get("name")]
    text_values = [str(t) for t in _present(fields.get("text"))] + [str(n) for n in box_names]
    folded = [f for f in (fold_text(t) for t in text_values) if f]
    compact = [f.replace(" ", "") for f in folded]
    words: List[Dict[str, str]] = []
    for one in folded:
        for word in one.split(" "):
            if word and _DIGITS_ONLY.match(word):
                words.append({"raw": word, "bare": _drop_leading_zeros(word)})
    numbers: List[_NumberParts] = []
    for raw_number in _present(fields.get("numbers")):
        canon = canonical_number(str(raw_number))
        if canon:
            numbers.append(_number_parts(canon))
    skus = [str(sku).strip() for sku in _present(fields.get("skus"))]
    return {"folded": folded, "compact": compact, "words": words, "numbers": numbers, "skus": skus}


def _number_match(raw: str, numbers: Sequence[_NumberParts]) -> bool:
    """Rule 4, for one raw token (a leading `#` or `/` allowed)."""
    if not numbers:
        return False
    if raw.startswith("/"):
        second = canonical_number(raw[1:])
        if not _has_digit(second) or "/" in second:
            return False
        return any(n["second"] == second for n in numbers)
    bare = raw[1:] if raw.startswith("#") else raw
    if not _has_digit(bare):
        return False
    forms = {canonical_number(bare), canonical_number(_hyphen_to_slash(bare))}
    for form in forms:
        if not _is_number_shape(form):
            continue
        whole = "/" in form
        if any(n["whole"] == form or (not whole and n["first"] == form) for n in numbers):
            return True
    return False


def _sku_match(raw: str, skus: Sequence[str]) -> bool:
    return bool(_SKU_SHAPE.match(raw)) and any(sku.startswith(raw) for sku in skus)


def _digit_word_match(word: str, words: Sequence[Dict[str, str]]) -> bool:
    """Rule 7's digits-only word: the start of a digits-only text word, as written or with
    the zeros in front of both dropped."""
    if _ZEROS_ONLY.match(word):
        return any(w["raw"].startswith(word) for w in words)
    bare = _drop_leading_zeros(word)
    if word != bare:
        return any(w["raw"].startswith(word) or w["bare"] == bare for w in words)
    return any(w["bare"].startswith(bare) for w in words)


def _text_match(raw: str, row: _Prepared) -> bool:
    words = [w for w in fold_text(raw).split(" ") if w]
    if not words:
        return False

    def word_ok(word: str) -> bool:
        if _DIGITS_ONLY.match(word):
            return _digit_word_match(word, row["words"])
        return any(word in field for field in row["folded"])

    if all(word_ok(w) for w in words):
        return True
    compact = "".join(words)
    return _has_letter(compact) and any(compact in field for field in row["compact"])


def _token_match(raw: str, row: _Prepared) -> bool:
    """Rules 4 to 7 for one token alone."""
    if _sku_match(raw, row["skus"]):
        return True
    if _number_match(raw, row["numbers"]):
        return True
    if raw.startswith("/"):
        return False
    return _text_match(raw, row)


def _pair_match(left: str, right: str, row: _Prepared) -> bool:
    """Rule 3: two neighbouring tokens that match together as one card number."""
    if left.startswith("/") or right.startswith("/") or right.startswith("#"):
        return False
    return _number_match(f"{left}/{right}", row["numbers"]) or _number_match(
        f"{left}{right}", row["numbers"]
    )


def _cover(tokens: Sequence[str], row: _Prepared) -> bool:
    """Rule 3: can every token be covered, in order, by the single-token rule or the
    pair rule?

    MEMOIZED ON `at` (F1, the Opus review, 2026-09-25). The un-memoized version tries
    BOTH the single-token branch and the pair branch at every position, and each branch
    recurses into the rest of the tokens — the same sub-problem (`at+1` from the single
    branch consuming one token, and again from wherever the pair branch's own single-try
    lands two tokens later) gets solved again from scratch every time a caller reaches it
    by a different path, which is exactly what makes Fibonacci's own recursion
    exponential. Measured: `("132 " * 27 + "/132 /999")` against a card whose number is
    `132/132` took 3.9s at 26 terms, uncached. `at` alone decides the rest of the answer
    — `tokens` and `row` are fixed for the one `match_query` call this closes over — so a
    dict keyed on `at` turns the call tree back into a line: at most `len(tokens) + 1`
    distinct calls, never two of the same `at` doing the work twice.
    """
    memo: Dict[int, bool] = {}

    def cover(at: int) -> bool:
        if at in memo:
            return memo[at]
        if at >= len(tokens):
            memo[at] = True
            return True
        one = tokens[at]
        result = False
        if _token_match(one, row) and cover(at + 1):
            result = True
        if not result and at + 1 < len(tokens):
            two = tokens[at + 1]
            if _pair_match(one, two, row) and cover(at + 2):
                result = True
        memo[at] = result
        return result

    return cover(0)


_EDGE_PUNCT_KEEP = "#/"


def _strip_edge_punctuation(token: str) -> str:
    """The punctuation a token loses at its ends. `#` and `/` survive in front (rule 4)."""
    start = 0
    n = len(token)
    while start < n and not (token[start].isalnum() or token[start] in _EDGE_PUNCT_KEEP):
        start += 1
    end = n
    while end > start and not token[end - 1].isalnum():
        end -= 1
    return token[start:end]


def query_tokens(query: str) -> List[str]:
    """Rule 2: the raw tokens of a query."""
    query = unicodedata.normalize("NFKC", str(query)).replace(",", " ")
    raw_tokens = [t for t in re.split(r"\s+", query) if t]
    tokens = [_strip_edge_punctuation(t) for t in raw_tokens]
    return [t for t in tokens if t not in ("", "#", "/")]


def match_query(query: str, fields: MatchFields) -> bool:
    """Does this row match this query? Every token must match, in any order (rules 2 to 7)."""
    tokens = query_tokens(query)
    if not tokens:
        return True
    return _cover(tokens, _prepare(fields))
