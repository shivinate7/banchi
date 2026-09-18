"""ONE ANSWER TO "DOES THIS HINT NAME THIS SET", FOR THE FETCH AND FOR THE JOIN.

There were two, and they disagreed. `server/tcg_export.py:match_sets` decided which sets the
export is SCOPED to; `pipeline/join.py:set_matches` decided which candidate rows a colliding
key NARROWS to. Same question, different rules: the fetch had a prefix rule and raw
case-folding, the join had `sv09` == `sv9` and matched either side of the colon. So a hint
could scope the export correctly and then fail to disambiguate the very rows it fetched — and
the capture screen's verdict, which predicts the fetch, said nothing about the second half.

TWO DEFECTS THIS FIXES, BOTH MEASURED BEFORE IT WAS WRITTEN:

  * `set_matches` is PAIRWISE — hint against one name — so it cannot see that four sets
    answered. `SV` matches `SV: Prismatic Evolutions`, `SV: Paldean Fates`, `SV: Scarlet &
    Violet 151` and `SV: Shrouded Fable`, and `join.py` handed all four sets' rows back as a
    confident narrowing with no `set_ambiguous`. A card that had earned a review got a
    four-set pile instead. Resolution is set-wise here for exactly that reason: ambiguity is
    a state this module can be in, and it answers `None`.

  * A three-letter set code resolved nowhere. `SFD` for `Spiritforged` widened the export to
    all of Riftbound; `pipeline/games.py:set_aliases` carried a hand-authored row per code and
    had four in total. See `ABBREVIATION` below for what replaced that.

AMBIGUITY IS A MISS, NEVER A GUESS. Both callers already treat it that way and both are
right to: the fetch widens to the whole category, which is slower and cannot miss a card, and
the join sends the card to review with its photo (D2, D3). Picking one of two sets would scope
an export to a set the box may not be in, or list a card as the wrong printing.

THE MATCHING LADDER ITSELF (`fold`, `sides`, `tail`, `candidates`, `resolve`) IS STILL STDLIB
ONLY, with no import from this repo at module load — `server/tcg_export.py` calls it with
names and aliases already in hand and stays dependency-free for that reason, unchanged by
what follows.

`known_sets`/`resolve_for_game`, ADDED FOR
D-the-set-is-a-stored-fact-and-the-hint-was-never-one,
ARE THE ONE EXCEPTION, and they import lazily, inside the function body, precisely so
loading this module for the pure ladder above still costs nothing. They read
`inventory/.exports/<game>/` off disk to complete a hint AT THE WRITE without a network call
— see their own docstrings for why a write path degrades to the raw hint rather than fetching
or refusing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

# A set code is short. Four is the longest TCGplayer publishes as a colon prefix (`SWSH`,
# `ME01`) and the longest the community uses (`OGN`, `SFD`, `PFL`). The cap is what keeps
# ABBREVIATION off misspelled NAMES: measured against the real Riftbound list, an uncapped
# subsequence rule silently resolved `Spiritfoged`, `Vendeta` and `Orgins` to their intended
# sets — which sounds like a feature until you notice it also destroys the capture screen's
# typo warning, because then almost every string "names a set". A hint long enough to be a
# name is judged as a name.
CODE_MAX = 4

# AND THREE IS THE SHORTEST. Every code published for either game is three characters or
# more — the Riftbound list at riftboundsymbols.com and the Pokemon one at limitlesstcg.com
# agree on that — and two letters run in order through so many names that the rule stops
# discriminating. The floor costs no real code and narrows the loosest rule here.
#
# IT IS NOT WHAT SAVES `SP`, and the difference is worth reading. `SP` is Riftbound's Special
# collection, TCGplayer does not list that set, and `SP` resolves to `Spiritforged` — by the
# PREFIX rule, which has answered that way since before this module existed and still does.
# That is the wrong-set failure the docstring bounds to "the operator's own set is missing
# from TCGplayer's list", found in the wild rather than reasoned about, and it is older than
# the abbreviation rule rather than caused by it. Left alone deliberately: narrowing prefix
# would take `UNL` and `VEN` with it, and both are real codes for sets TCGplayer does list.
CODE_MIN = 3


def fold(name: str) -> str:
    """Lowercase, drop everything that is not a letter or digit, unpad each digit run.

    Lifted verbatim from `pipeline/join.py:normalize_set`, which stays as the join's own
    spelling of it. `sv09` and `sv9` fold together because pokemontcg.io writes the unpadded
    form and TCGplayer the padded one; without that they never compare equal.
    """
    text = str(name or "").strip().lower()
    out: List[str] = []
    digits: List[str] = []
    for char in text:
        if char.isdigit():
            digits.append(char)
            continue
        if digits:
            out.append(str(int("".join(digits))))
            digits = []
        if char.isalnum():
            out.append(char)
    if digits:
        out.append(str(int("".join(digits))))
    return "".join(out)


def sides(name: str) -> Tuple[str, ...]:
    """The whole label and each side of its colon, folded. `SV09: Journey Together` answers
    to `SV09`, to `Journey Together` and to itself — the operator labelled the divider with
    whichever one they had to hand."""
    parts = [name] + str(name or "").split(":")
    return tuple(dict.fromkeys(f for f in (fold(p) for p in parts) if f))


def tail(name: str) -> str:
    """The set's own name with any TCGplayer block code taken off the front.

    `SV05: Temporal Forces` -> `temporalforces`. ABBREVIATION runs over this rather than over
    the whole label because the codes people actually type are built from the name: `TEF` from
    Temporal Forces, `JTG` from Journey Together, `MEG` from Mega Evolution. Against the whole
    label every one of those would have to start with `sv` or `me` and none of them does.
    """
    text = str(name or "")
    return fold(text.split(":", 1)[1] if ":" in text else text)


def _prefix_ok(needle: str, folded: str) -> bool:
    """Is `needle` a prefix of `folded`, stopping short of splitting a number?

    A TRUNCATED WORD IS STILL THAT WORD; A TRUNCATED NUMBER IS A DIFFERENT NUMBER. `unl` is
    Unleashed and `sv` is every SV set, but `sv1` is NOT `SV19` — which is the case
    `harness/tests/t3_join_coverage.py` has asserted since before this module existed, and the
    one the plain prefix rule the fetch shipped with gets wrong. The join never had a prefix
    rule to get it wrong with; unifying the two is what makes the guard necessary here.
    """
    if not needle or not folded.startswith(needle):
        return False
    rest = folded[len(needle):]
    return not (needle[-1].isdigit() and rest[:1].isdigit())


def _abbreviates(needle: str, name: str) -> bool:
    """Is `needle` a set code for `name` — its letters, in order, anchored on the first?

    `SFD` -> Spiritforged, `OGN` -> Origins, `VEN` -> Vendetta, `JTG` -> Journey Together.
    Those four are codes with a source: the owner types them, or they were already
    hand-authored in `pipeline/games.py:set_aliases`.
    There is no rule that derives the ONE official code from a name: `PAL` is the first three
    letters of Paldea, `TEF` is two-plus-one, `SFD` is a squeeze. Rather than guess which
    generator a set used, this accepts every ordered squeeze and lets ambiguity throw out the
    ones that answer to more than one set.

    IT IS THE LAST RULE TRIED, so it can never take a hint that already resolves. That
    ordering is what bounds the damage: measured against the real Riftbound and SV set lists,
    the only way this returns the WRONG set is for the operator's own set to be missing from
    TCGplayer's list entirely — if their set is there, the code either finds it or ties with
    another and ties widen.
    """
    if not needle or not (CODE_MIN <= len(needle) <= CODE_MAX):
        return False
    body = tail(name)
    if not body or body[0] != needle[0]:
        return False
    rest = iter(body[1:])
    return all(char in rest for char in needle[1:])


def candidates(
    hint: str,
    names: Sequence[str],
    aliases: Optional[Dict[str, str]] = None,
) -> Tuple[str, ...]:
    """Every set in `names` this hint could mean, by the first rule that answers at all.

    RULE ZERO is the game's alias table (D22, hand-authored), which rewrites a hint to another
    HINT rather than to a set, so the shape rules below still do the matching. It survives
    ABBREVIATION for the pairings no shape rule reaches — a code naming a set whose TCGplayer
    label is in a different vocabulary entirely.

      label          a hint equal to the whole set name
      side           a hint equal to either side of its colon
      prefix         a hint the label starts with, not splitting a number
      abbreviation   a short hint whose letters run in order through the set's own name

    LABEL AND SIDE ARE TWO TIERS, NOT ONE, AND THE ORDER IS LOAD-BEARING. `Origins` is a set,
    and it is also the left side of `Origins: Proving Grounds` — collapsed into one tier they
    tie, and a hint naming a base set exactly resolves to nothing. Whole-label equality is
    tried alone first so that a set can always be named by its own name.
    """
    table = {fold(k): str(v) for k, v in (aliases or {}).items()}
    raw = str(hint or "").strip()
    needle = fold(table.get(fold(raw), raw))
    if not needle:
        return ()

    rows = [(name, sides(name)) for name in names]
    for rule in (
        lambda name, _folded: fold(name) == needle,
        lambda name, folded: needle in folded,
        lambda name, folded: any(_prefix_ok(needle, one) for one in folded),
        lambda name, _folded: _abbreviates(needle, name),
    ):
        found = tuple(dict.fromkeys(name for name, folded in rows if rule(name, folded)))
        if found:
            return found
    return ()


def resolve(
    hint: str,
    names: Sequence[str],
    aliases: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """The one set this hint names, or `None` for blank, no match, or more than one."""
    found = candidates(hint, names, aliases)
    return found[0] if len(found) == 1 else None


# --------------------------------------------------------------------- write-time completion
#
# D-the-set-is-a-stored-fact-and-the-hint-was-never-one, "the remaining hole": completion is
# offered on Enter by `app/src/setHint.ts` and enforced nowhere. Everything below runs the
# same ladder AT THE WRITE, against whatever export this game already has on disk — never
# fetched, because a write path must not open a socket to store a string, and the export the
# capture screen's own vocabulary is drawn from (`GET /tcg/sets`) is one degradation of the
# same source: a live category listing. `inventory/.exports/<game>/` is the local copy of
# that same vocabulary, one step further degraded (it can be stale or absent) and zero
# network calls away, which is the trade a write path takes and a read of the hint field
# never has to.


def _export_dir(game: str) -> Path:
    """`inventory/.exports/<game>/` — `store/files.py`'s own name for it, read here rather
    than imported from `server/pipeline_routes.py`, which is a route module and not a shared
    home for a path fragment."""
    from store import files

    return files.inventory_dir() / files.EXPORTS_DIRNAME / str(game)


def known_sets(game: str) -> Tuple[str, ...]:
    """Every distinct `Set Name` across every export this game has on disk, in no particular
    order, or empty when the game has never been fetched — the honest Pokemon answer today
    (D-the-set-is-a-stored-fact-and-the-hint-was-never-one's own measurement: 0 of 542).

    EVERY FILE UNDER THE DIRECTORY, NOT ONE. `inventory/.exports/<game>/` can hold more than
    one CSV over a store's life — a narrower fetch today, a wider one last month — and a set
    released since the older file was written would be invisible to a hint typed today if
    only the newest file answered. A card resolving against the union is never worse than
    resolving against one file, and `pipeline/join.py`'s own `Catalog.from_export` is built
    against exactly one export per run for an unrelated reason (which row is authoritative
    for a JOIN) that does not apply to a plain vocabulary lookup.

    A FILE THAT WILL NOT PARSE IS SKIPPED, NEVER RAISED. This is a convenience for a write
    path that must not refuse a capture over a stray or half-written file in a directory it
    does not own the writing of.
    """
    from pipeline import tcgcsv

    directory = _export_dir(game)
    if not directory.is_dir():
        return ()
    names: Dict[str, None] = {}
    for path in sorted(directory.glob("*.csv")):
        try:
            export = tcgcsv.read_export(path)
        except (OSError, tcgcsv.MalformedCsv):
            continue
        for row in export.rows:
            name = str(row.get(tcgcsv.SET_COLUMN) or "").strip()
            if name:
                names.setdefault(name, None)
    return tuple(names)


def resolve_for_game(hint: str, game: str) -> Optional[str]:
    """`resolve`, sourced from whatever this game's own export already holds on disk.

    NEVER FETCHES, NEVER REFUSES. `None` means "nothing to complete this with" — no export
    for the game, or a hint that does not resolve against what is there — and every caller's
    rule is the same one D65 already applies to the fetch itself: an unresolved hint is kept
    exactly as typed, never replaced with a guess and never a reason to refuse the write.
    """
    text = str(hint or "").strip()
    if not text:
        return None
    names = known_sets(game)
    if not names:
        return None
    from pipeline import games

    aliases = (games.get(game) or {}).get("set_aliases")
    return resolve(text, names, aliases)
