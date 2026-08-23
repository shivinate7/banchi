"""The identification contract — prompt, schema, parser. Pure: no network, no SDK.

Everything the model is told and everything we accept back lives here, so
`prompt_fingerprint()` can hash the whole contract into each T1 result file. Change a
word of the prompt or a key of the schema and the fingerprint changes, which is what
makes "rerun after any prompt change" (docs/GATES.md) enforceable rather than a habit.

TWO PROFILES, AND THE SECOND ONE IS NOT THE FIRST ONE WITH FIELDS BLANKED OUT.
`pokemon_card_v1` is the contract T1 scores and the one everything below describes.
`misc_card_v1` reads the ~1% of the shelf that is a Magic, Yu-Gi-Oh, Weiss Schwarz or
foreign-language card: its own system prompt, its own schema, its own parser, because those
cards do not print a `number/total` pair, do not carry the finishes `pipeline/variant.py`
knows about, and do not share a rarity vocabulary. `pipeline/games.py` says which profile
reads which game; this module holds the profiles and never guesses between them. **A misc
card IS identified and IS submitted to the Batch API** — the owner's correction of
2026-08-23 — and what it never does is join a catalog.

The rest of this header is about `pokemon_card_v1`. Two of its shapes deserve a note:

`finish` carries an `unknown` member the other three do not share. D3 rung 3 runs
detection as a cross-check even when capture-time metadata exists, and `variant.resolve`
already models "no detection signal" as `detected_finish=None` with its own review
reason (`AMBIGUOUS_NO_SIGNAL`). Forcing a three-way guess would manufacture
disagreements out of flat lighting and send correctly-sorted cards to review. So the
model is given a way to say it cannot see foil, and `parse` maps it to None.

`number` and `printed_total` come back as two separate strings, never as one "161/159"
field. The join key is built by `pipeline.join.join_key`, which zero-pads the left half
only; splitting on a delimiter the model chose is a parser waiting to disagree with the
catalog. Secret rares — number larger than the denominator — are ordinary here.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence

from pipeline import games, variant

# CLAUDE.md pins the model. Batch API only — see identify/batch.py.
MODEL = "claude-haiku-4-5-20251001"

# One small JSON object. Structured outputs make the shape a guarantee, so this only has
# to cover the object itself.
MAX_TOKENS = 512

UNKNOWN_FINISH = "unknown"

CONFIDENCE_LEVELS = ("high", "medium", "low")

SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "Card title exactly as printed, punctuation and suffix included.",
        },
        "number": {
            "type": "string",
            "description": "Left half of the collector number, as printed. Empty if absent.",
        },
        "printed_total": {
            "type": "string",
            "description": "Right half of the collector number, as printed. Empty if absent.",
        },
        "finish": {
            "type": "string",
            "enum": list(variant.FINISHES) + [UNKNOWN_FINISH],
            "description": "Foil treatment visible in this image, or unknown.",
        },
        "confidence": {
            "type": "string",
            "enum": list(CONFIDENCE_LEVELS),
            "description": "How legible the title and collector number were.",
        },
    },
    "required": ["name", "number", "printed_total", "finish", "confidence"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """\
You identify Pokemon Trading Card Game singles from a photograph of the card front.

Read the card in the image and report what is printed on it. One card per image.

name
  The card's title, exactly as printed across the top of the card. Keep suffixes that
  are part of the title - "ex", "V", "VMAX", "VSTAR", "Radiant", "Tera". Keep
  punctuation, including apostrophes and ampersands: "Boss's Orders", "Iono's
  Bellibolt ex", "Team Rocket's Mewtwo ex". Do not add the set name, the rarity, the
  evolution stage, or the HP.

number and printed_total
  The collector number is printed in a bottom corner as "number/total". Report the two
  halves separately, each exactly as printed - if the card reads "025/198" then number
  is "025", not "25". On a secret rare the number is LARGER than the total, for example
  "161/159". That is correct and ordinary. Never adjust one half to make it agree with
  the other, and never infer a total you cannot read.
  If the card prints no collector number at all, return "" for both.

finish
  normal        Flat, non-foil card stock across the entire card.
  holo          The illustration window is foil; the surrounding card body is not.
  reverse_holo  The card body and border are foil; the illustration window is not.
  unknown       You cannot tell from this image.
  Judge only from foil texture, glare, or sheen you can actually see. Flat, evenly lit
  artwork with no foil signal either way is "unknown". Do not infer the finish from the
  card's rarity, its artwork, or how a card of this kind is usually printed - a guess
  here is worse than an admission, because a later step trusts this field to catch
  mis-sorted cards.

confidence
  high    You can read both the title and the collector number clearly.
  medium  One of the two is partly obscured, but you are reasonably sure of it.
  low     You are guessing at either field.

Report only what is printed. Never invent a card you cannot read.\
"""

_USER_TEXT = "Identify this card."
_USER_TEXT_WITH_HINT = (
    "Identify this card. The stack it came from is labelled {hint}, which is a hint "
    "about the set and may be wrong - trust the card over the label."
)

_HINT_CLAUSE = (
    " The stack it came from is labelled {hint}, which is a hint about the set and may "
    "be wrong - trust the card over the label."
)
_USER_TEXT_WITH_CROPS = (
    "Identify this card. The first image is the whole card. The images after it are "
    "enlarged crops of the SAME card: the title band across the top, and the band along "
    "the bottom where the collector number is printed. Read each field from whichever "
    "image shows it most clearly. The crops are enlargements, not different cards, and "
    "the bands are cut loosely, so a crop may include parts of the card either side of "
    "the field you are reading."
)

# D23 job (c): the operator's per-stack rarity claim, rendered per card in the USER turn —
# never the system prompt, because a claim is a fact about one card's stack, not about the
# task. Appended to whichever turn was built (plain, hinted, crops), and ONLY when a claim
# exists: with no claim the built prompt is byte-identical to what it always was, which is
# what keeps `prompt_fingerprint` at the hash T1 asserts.
#
# THE LAST SENTENCE IS THE LOAD-BEARING ONE. `SYSTEM_PROMPT` already says "Do not infer
# the finish from the card's rarity" — that instruction is what keeps D3 rung 3 an
# independent signal, and a rarity clause without the explicit carve-out is exactly the
# careless clause D23 warns "makes it do exactly that". The claim may disambiguate the
# printed rarity symbol; it may never leak into `finish`.
_RARITY_CLAUSE = (
    " The stack this card came from is claimed to hold only these rarities: {rarities}. "
    "Use it to disambiguate the rarity symbol if one is printed and legible. It says "
    "nothing about the finish — judge `finish` only from foil you can actually see."
)


# ------------------------------------------------------------------ the misc contract
#
# THE OWNER'S CORRECTION, 2026-08-23: *"i also want misc identified and submitted to batch
# api -- i never said i didnt"*. `misc` was built to take no identification call at all,
# with the operator's free-text note standing in for one. The note stays and is ADDITIONAL;
# it was never offered as a substitute for reading the card. What `misc` still never does is
# JOIN — `pipeline/games.py` keeps `catalogued: False` and `join_key: "not_joined"`, because
# there is no Magic or Yu-Gi-Oh export here to match a row against.
#
# A SECOND PROFILE RATHER THAN POKEMON'S REUSED, and the schema is the whole argument. This
# one profile has to read a Magic card, a Yu-Gi-Oh card, a Weiss Schwarz card and a
# foreign-language printing of anything, so it may assume none of Pokemon's shape:
#
#   no `printed_total`   Only some games print `number/total` at all. Magic does; Yu-Gi-Oh
#                        prints a set code and an index (`LOB-EN005`) with no denominator,
#                        and Weiss prints a compound code (`FS/S64-E003S`). Asking for two
#                        halves of a thing that is one string invites the model to invent a
#                        split, and a split is what `identify/prompt.py`'s own header
#                        warns about for Pokemon: "splitting on a delimiter the model chose
#                        is a parser waiting to disagree with the catalog". So ONE field,
#                        verbatim, whatever shape the game prints it in.
#   no `finish`          D3 rung 3 cross-checks a DETECTED finish against a capture-time
#                        claim — against `pipeline/games.py`'s per-game finish enum. The
#                        `misc` entry's `finishes` is empty, deliberately, because there is
#                        no finish vocabulary that means the same thing across four games.
#                        Asking for a finish here would be asking a question the registry
#                        says this game does not answer, and nothing downstream could read
#                        the answer.
#   no rarity            Same reason one layer up: `rarities` is empty by decision, and a
#                        rarity word means something different in each of these games.
#
# WHAT IT ASKS FOR INSTEAD IS WHAT ALL FOUR POPULATIONS ACTUALLY PRINT: a name, one
# identifier string, which game the card is from, and what language it is printed in.

# The `detected_game` enum. NOT REGISTRY KEYS, AND THE FIELD IS NAMED SO THAT NOBODY READS
# THEM AS ONE — the same distinction `detected_finish` draws against `metadata_finish`. The
# registry's answer for every card this profile reads is `misc`, permanently; this field is
# the model's read of what the cardboard is, which is a different question. In particular a
# foreign-language Pokemon card answers `pokemon` here and is still `misc` there, and that
# is the case the two vocabularies exist to keep apart. Never feed this value to
# `games.get()`.
#
# `other` AND `unknown` ARE TWO DIFFERENT ANSWERS, exactly as `finish`'s `unknown` is not a
# fourth finish: `other` says the card was legible and is something none of the four named
# games covers; `unknown` says it could not be told. Collapsing them would turn "I read a
# Digimon card" into "I could not read this", which sends a fine card to a human for nothing.
MISC_GAMES = ("magic", "yugioh", "weiss_schwarz", "pokemon", "other", "unknown")

UNKNOWN_LANGUAGE = "unknown"

MISC_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": (
                "Card title exactly as printed, in the script it is printed in. Empty if "
                "no title is legible."
            ),
        },
        "printed_id": {
            "type": "string",
            "description": (
                "Every identifier printed on the card, as one verbatim string. Empty if "
                "the card prints none."
            ),
        },
        "detected_game": {
            "type": "string",
            "enum": list(MISC_GAMES),
            "description": "Which game this card is from, or unknown.",
        },
        "language": {
            "type": "string",
            "description": (
                "Language of the card's own printed text, named in English, or "
                f"{UNKNOWN_LANGUAGE!r}."
            ),
        },
        "confidence": {
            "type": "string",
            "enum": list(CONFIDENCE_LEVELS),
            "description": "How legible the title and the printed identifier were.",
        },
    },
    "required": ["name", "printed_id", "detected_game", "language", "confidence"],
    "additionalProperties": False,
}

MISC_SYSTEM_PROMPT = """\
You identify trading cards that are not part of a catalogue we hold, from a photograph of
the card front. They come from several different games and several different languages -
Magic: The Gathering, Yu-Gi-Oh!, Weiss Schwarz, and foreign-language printings of any game
including Pokemon.

Read the card in the image and report what is printed on it. One card per image.

Nothing downstream matches your answer against a catalogue, so nothing can correct a guess.
An answer you are unsure of is worth less than saying you are unsure.

name
  The card's title, exactly as printed, IN THE SCRIPT IT IS PRINTED IN. Do not translate
  it, do not transliterate it, do not expand an abbreviation and do not abbreviate a full
  word. Keep punctuation and any suffix that is part of the title. If no title is legible,
  return "".

printed_id
  Any identifier printed on the card, exactly as printed, as ONE string - keep its
  punctuation, its set code and any prefix or suffix. These games print it in different
  places and different shapes: "LOB-EN005", "FS/S64-E003S", "268/287", "SV1a 073/078",
  "T2-05". Copy the whole string you can see. Do not split it into parts, do not reorder
  it, and never fill in a piece you cannot read. If the card prints no identifier at all,
  return "".

detected_game
  magic          Magic: The Gathering
  yugioh         Yu-Gi-Oh!
  weiss_schwarz  Weiss Schwarz
  pokemon        Pokemon, in any language
  other          You can tell what this card is, and it is none of the four above
  unknown        You cannot tell what game this card is from
  Judge from what is printed and from the card's layout. "other" and "unknown" are
  different answers and both are wanted: "other" means the card was legible and is
  something else, "unknown" means you could not tell. Do not pick one of the four named
  games because the card resembles it.

language
  The language of the card's own printed text, named in English - "English", "Japanese",
  "German", "Korean". If you cannot tell, return "unknown".

confidence
  high    You can read both the title and the printed identifier clearly.
  medium  One of the two is partly obscured, but you are reasonably sure of it.
  low     You are guessing at either field.

Report only what is printed. Never invent a card you cannot read.\
"""

_MISC_USER_TEXT = "Identify this card."
_MISC_USER_TEXT_WITH_HINT = (
    "Identify this card. The stack it came from is labelled {hint}, which is a hint and "
    "may be wrong - trust the card over the label."
)
_MISC_HINT_CLAUSE = (
    " The stack it came from is labelled {hint}, which is a hint and may be wrong - trust "
    "the card over the label."
)
# WRITTEN, AND CURRENTLY UNREACHABLE, AND THAT IS SAID HERE RATHER THAN LEFT TO BE
# DISCOVERED. A crop retry needs `geometry.detect_card` to have found the card, and the
# `misc` entry's `card_aspect` is None — so detection refuses before any band is cut. The
# turn is authored anyway because `Profile` is data and a field left blank is a field that
# reads as an oversight; it also says nothing about title or number BANDS, since `misc`
# claims none and a retry here would carry the registered card alone.
_MISC_USER_TEXT_WITH_CROPS = (
    "Identify this card. The first image is the whole card. The images after it are "
    "enlarged crops of the SAME card, not different cards. Read each field from whichever "
    "image shows it most clearly."
)


# ------------------------------------------------------------------ per-game dispatch
#
# `pipeline/games.py` says WHICH prompt reads a card, by name — `pokemon_card_v1` on the
# `pokemon` entry, `unwritten` on the games whose prompt has never been written. It cannot
# hold the prompt itself, because the registry has to stay `ast.literal_eval`-safe so
# `scripts/docs-audit.py` can read it without importing project code (D22). So the name
# lives there and the thing it names lives here, in the module that owns the contract.
#
# A PROTOCOL OR AN ABC PER GAME WAS CONSIDERED AND REJECTED. There is not one anywhere in
# `identify/`, `pipeline/` or `geometry/` today, and it would move Pokemon's prompt out of
# the module that hashes it into a subclass somewhere else — away from the literal the
# fingerprint is computed over, which is the one thing that must stay obvious. A dict from
# a registry name to a value in the consuming module is also the only shape the audit can
# check: it reads both sides with `ast` and compares two sets of strings.
#
# THE FINGERPRINT IS HASHED OVER ONE PROFILE'S FIELDS, UNDER THE SAME KEYS AS BEFORE, and
# a sibling profile added here can never move it. That is not politeness — `docs/GATES.md`
# requires T1 be re-measured after any prompt change, and a re-measurement costs money. The
# assertion lives in `harness/tests/t1_id_eval.py`, where a moved hash fails the harness
# rather than being noticed in a diff.


@dataclass(frozen=True)
class Profile:
    """Everything one game's identification call is made of.

    Fields, not methods. A profile is data the way a registry entry is data; the behaviour
    that reads it — `user_text`, `prompt_fingerprint`, `identify/batch.py` — stays in one
    place rather than being spread across one implementation per game.
    """

    model: str
    max_tokens: int
    system: str
    user: str
    user_with_hint: str
    user_with_crops: str
    hint_clause: str
    # D23's rarity-claim clause, or "" for a game with no rarity vocabulary to claim from.
    # A fragment like `hint_clause`, appended to whichever turn was built. NOT hashed by
    # `prompt_fingerprint` — see `rarity_fingerprint` for why, and for what pins it.
    rarity_clause: str
    schema: Dict[str, Any]


POKEMON_CARD_V1 = Profile(
    model=MODEL,
    max_tokens=MAX_TOKENS,
    system=SYSTEM_PROMPT,
    user=_USER_TEXT,
    user_with_hint=_USER_TEXT_WITH_HINT,
    user_with_crops=_USER_TEXT_WITH_CROPS,
    hint_clause=_HINT_CLAUSE,
    rarity_clause=_RARITY_CLAUSE,
    schema=SCHEMA,
)

MISC_CARD_V1 = Profile(
    model=MODEL,
    max_tokens=MAX_TOKENS,
    system=MISC_SYSTEM_PROMPT,
    user=_MISC_USER_TEXT,
    user_with_hint=_MISC_USER_TEXT_WITH_HINT,
    user_with_crops=_MISC_USER_TEXT_WITH_CROPS,
    hint_clause=_MISC_HINT_CLAUSE,
    # `misc` has no rarity vocabulary (`pipeline/games.py` declares it empty), so the
    # sidecar reader drops every member of a claim before it could reach this profile.
    # An empty clause records that as the profile's own property rather than leaving it
    # to be inferred from the registry: this game takes no rarity clause.
    rarity_clause="",
    schema=MISC_SCHEMA,
)

# ONE STRATEGY NAME NOW NAMES NO PROFILE, WHERE THERE USED TO BE TWO.
#
#   unwritten       nobody has written this game's prompt YET. A gap with a fix — `riftbound`
#                   and `one_piece` have exports now and still have no prompt. Asking for it
#                   is a refusal, because the alternative is falling through to Pokemon's,
#                   which fits every call and reads every card wrong.
#
# THE ONE THAT LEFT WAS `operator_note`, AND IT LEFT BECAUSE THE OWNER SAID SO. It named a
# game deliberately never sent to the model, with the operator's free-text note standing in
# for the identification, and `misc` was its only claimant. The owner's correction on
# 2026-08-23 was *"i also want misc identified and submitted to batch api -- i never said i
# didnt"* — the note is ADDITIONAL, and always was. `misc` now names `misc_card_v1` above.
#
# IT WAS DELETED RATHER THAN LEFT STANDING UNCLAIMED, and that is a judgement worth showing
# rather than a tidy-up. What would have remained is a strategy no entry can name, a
# `NotIdentifiable` exception nothing can raise, and an `identifies()` predicate that can
# only ever answer True — three pieces of machinery kept honest by nothing, describing a
# state the product does not have. That is the same defect the registry's own audit refuses
# in a game entry ("a field no consumer reads is a field nothing keeps honest"), and there is
# no reason it should be legal one file over. If a game is ever ruled never-identified again,
# this is four lines to restore and the argument for it will be on the record.
#
# `PROFILES` STILL MAPS TO `Optional[Profile]` for `unwritten` alone. The Optional is not
# left over: it is what makes "no prompt written" a value the dispatch can hold and refuse
# on, rather than a missing key indistinguishable from a typo.
UNWRITTEN = "unwritten"

PROFILES: Dict[str, Optional[Profile]] = {
    "pokemon_card_v1": POKEMON_CARD_V1,
    "misc_card_v1": MISC_CARD_V1,
    UNWRITTEN: None,
}

# The profile T1 scores, named by the registry rather than written out again here. A literal
# `"pokemon_card_v1"` in this line would be a second decision that has to agree with the
# `pokemon` entry's `prompt` field — the exact two-independent-decisions shape T1's own
# `gated_split` comment says to watch for.
DEFAULT_PROFILE: str = str(games.get(games.DEFAULT_GAME)["prompt"])


class UnknownProfile(KeyError):
    """A prompt strategy outside `PROFILES`. Never coerced to the Pokemon one."""


class UnwrittenPrompt(LookupError):
    """A registry entry naming `unwritten`: this game has no prompt yet."""


# `NotIdentifiable` STOOD HERE AND IS GONE WITH `operator_note` — see the note above
# `PROFILES`. It was raised for a game the owner had ruled was never sent to the model, and
# the owner's correction is that no game is. An exception nothing can raise is worse than no
# exception, because a reader takes it as evidence of a state the product has.


# EVERY STRATEGY NAME IN THE REGISTRY MUST HAVE AN ENTRY HERE, checked at import so a name
# added to `pipeline/games.py` stops the process next to the mismatch rather than at
# whichever call happens to reach for it first. Same seam, same reasoning and the same
# failure mode as `pipeline/variant.py`'s finish-enum reconciliation.
#
# THE CHECK RUNS ONE WAY ONLY, and that asymmetry is deliberate. A profile here that no
# registry entry names is a strategy authored AHEAD of its game, and blocking on it would
# mean these two files could only ever change together, in one commit, by one person. A
# registry name with NO profile is the direction that breaks a run — and it has now caught
# two. The first was `operator_note`, arriving in the registry while this dispatch called
# the same idea `not_identified`. The second was `misc_card_v1`, arriving in the registry
# while this profile was still being written: the process stopped at import, next to both
# names, rather than at whichever misc card first reached for a prompt.
_unhandled = [name for name in games.PROMPT_STRATEGIES if name not in PROFILES]
if _unhandled:  # pragma: no cover - import-time contract, not a branch under test
    raise RuntimeError(
        "identify/prompt.py:PROFILES has no entry for "
        + ", ".join(repr(name) for name in _unhandled)
        + ", which pipeline/games.py lists in PROMPT_STRATEGIES. Add a Profile (or an "
        "explicit None with a comment saying which kind of nothing it is) — never let a "
        "game fall through to another game's prompt."
    )


# `identifies()` STOOD HERE AND IS GONE, for the reason the note above `PROFILES` gives at
# length. It answered "does this strategy send a card to the model at all?", and with
# `operator_note` removed the only answer it can give is True. A predicate with one reachable
# answer is not a branch, it is a claim — and the claim it would carry is that some game
# somewhere is never identified, which is the sentence the owner corrected.
#
# WHAT REPLACED IT AS THE CHEAP PRE-CHECK IS `profile()` ITSELF, catching `UnwrittenPrompt`.
# There is no third thing to remember: a caller either has a profile to send or has a named
# refusal saying why not.


def profile(strategy: str = DEFAULT_PROFILE) -> Profile:
    """The profile named by a registry entry's `prompt` field, or a refusal that says which.

    Two refusals rather than one, because the remedy differs: register the name, or write the
    prompt. There used to be a third — `operator_note`, "this game is never sent to the
    model" — and the owner's correction of 2026-08-23 deleted the state, not just the branch.
    """
    if strategy not in PROFILES:
        raise UnknownProfile(
            f"{strategy!r} is not a prompt strategy; known: {', '.join(sorted(PROFILES))}. "
            "Add it to PROMPT_STRATEGIES in pipeline/games.py and give it a Profile here."
        )
    found = PROFILES[strategy]
    if found is None:
        raise UnwrittenPrompt(
            f"no prompt has been written for {strategy!r}. Write one in identify/prompt.py "
            "and register it in PROFILES; do not read this game with another game's prompt."
        )
    return found


def user_text(
    set_hint: Optional[str] = None,
    with_crops: bool = False,
    strategy: str = DEFAULT_PROFILE,
    rarity_claim: Optional[Sequence[str]] = None,
) -> str:
    """The per-image turn. The set hint is an optional accelerator (D2), never required.

    `rarity_claim` is D23's stack claim, already validated against the game's own
    vocabulary at the sidecar read. Rendered as one clause appended to whichever turn was
    built, and ONLY when a claim exists — no claim builds the exact bytes this function
    built before the parameter existed, which is the compatibility guarantee the T1
    fingerprint assertion holds. A profile with an empty `rarity_clause` renders no claim
    however loudly one is supplied.
    """
    chosen = profile(strategy)
    if with_crops:
        text = chosen.user_with_crops
        if set_hint:
            text += chosen.hint_clause.format(hint=set_hint)
    elif set_hint:
        text = chosen.user_with_hint.format(hint=set_hint)
    else:
        text = chosen.user
    if rarity_claim and chosen.rarity_clause:
        text += chosen.rarity_clause.format(rarities=", ".join(rarity_claim))
    return text


def prompt_fingerprint(strategy: str = DEFAULT_PROFILE) -> str:
    """Stable hash of the contract T1 SCORES: model, prompt, both user turns, schema.

    ONE PROFILE'S FIELDS, UNDER THE KEYS THIS FUNCTION HAS ALWAYS USED. The strategy name is
    not hashed and neither is any sibling profile, so `pokemon_card_v1` reads `1ef974bf511d`
    after the per-game dispatch exactly as it did before it. That is the proof the refactor
    changed nothing, and `harness/tests/t1_id_eval.py` asserts the literal — the alternative
    is a re-measurement that costs money to learn nothing.

    The crop-retry turn is deliberately NOT in here, and the omission is the same argument
    v2 §4.6 makes about not invalidating the production cache on a prompt change. T1 never
    sends crops — it scores one flat render per card — so a reworded crop-retry turn cannot
    move a T1 number by a single card. Folding it in would invalidate every cached run and
    charge for a re-measurement of something that did not change. `retry_fingerprint`
    records it separately, so it is still pinned; it just does not pretend to gate a score
    it has no bearing on.
    """
    chosen = profile(strategy)
    payload = json.dumps(
        {
            "model": chosen.model,
            "max_tokens": chosen.max_tokens,
            "system": chosen.system,
            "user": chosen.user,
            "user_with_hint": chosen.user_with_hint,
            "schema": chosen.schema,
        },
        sort_keys=True,
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def retry_fingerprint(strategy: str = DEFAULT_PROFILE) -> str:
    """Stable hash of the crop-retry turn, recorded in the run manifest."""
    chosen = profile(strategy)
    payload = json.dumps(
        {"user_with_crops": chosen.user_with_crops, "hint_clause": chosen.hint_clause},
        sort_keys=True,
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def rarity_fingerprint(strategy: str = DEFAULT_PROFILE) -> str:
    """Stable hash of the rarity-claim clause (D23), pinned beside the score it can move.

    DELIBERATELY NOT FOLDED INTO `prompt_fingerprint`, and the reason is that function's
    own discipline read in the other direction: with no claim present the built prompt is
    byte-identical to the contract `1ef974bf511d` was measured under, so the hash of that
    contract must not move — and adding a key to its payload moves it unconditionally,
    re-submitting 150 images to re-measure a default path that did not change.

    The precedent copied is `retry_fingerprint`, the module's existing shape for a turn
    variant added after the contract froze: pinned under its own name, and folded into
    exactly the things it can change. Unlike the crop turn, this clause CAN move a T1
    number — but only in the claimed configuration, so `harness/tests/t1_id_eval.py`
    folds this hash into that configuration's cache key (a reworded clause invalidates
    the claimed run and leaves the default run warm), and `cli/cmd_identify.py` records
    it in the run manifest so a production run says which clause wording its claimed
    cards were read under.
    """
    chosen = profile(strategy)
    payload = json.dumps(
        {"rarity_clause": chosen.rarity_clause},
        sort_keys=True,
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


class MalformedIdentification(ValueError):
    """The model returned something the schema should have made impossible."""


@dataclass(frozen=True)
class Identification:
    """One model answer, normalized into the fields `join.IdentifiedCard` consumes."""

    name: str
    number: str
    printed_total: str
    detected_finish: Optional[str]  # None == the model saw no foil signal (D3 rung 3)
    confidence: str
    raw: Dict[str, Any]

    @property
    def has_number(self) -> bool:
        return bool(self.number and self.printed_total)


def _confidence_of(payload: Dict[str, Any]) -> str:
    confidence = str(payload["confidence"]).strip().lower()
    if confidence not in CONFIDENCE_LEVELS:
        raise MalformedIdentification(f"confidence {confidence!r} outside the enum")
    return confidence


def _parse_pokemon(payload: Dict[str, Any]) -> Identification:
    """`pokemon_card_v1`'s answer. Byte-for-byte what `parse` did before it dispatched."""
    finish = str(payload["finish"]).strip().lower()
    if finish == UNKNOWN_FINISH:
        detected = None
    elif finish in variant.FINISHES:
        detected = finish
    else:
        raise MalformedIdentification(f"finish {finish!r} outside the enum")

    return Identification(
        name=str(payload["name"]).strip(),
        number=normalize_number(payload["number"]),
        printed_total=normalize_number(payload["printed_total"]),
        detected_finish=detected,
        confidence=_confidence_of(payload),
        raw=payload,
    )


def _parse_misc(payload: Dict[str, Any]) -> Identification:
    """`misc_card_v1`'s answer, mapped onto the same three carried fields.

    ONE `Identification` TYPE, NOT ONE PER GAME, because everything downstream of here —
    the run payload, the inventory record, the review screen's `read` block — is written
    against these fields. A second dataclass would fork every one of those readers to serve
    ~1% of the shelf.

    THE MAPPING, AND WHERE EACH FIELD GOES:

      name            as printed, stripped. Same field, same meaning.
      number          the WHOLE `printed_id`, because for these games there is no left half.
      printed_total   "" — not a blank we failed to read, but a half the card does not have.
                      `has_number` is therefore False for every misc card, which is correct:
                      it asks whether a `number/total` join key can be built, and none can.
      detected_finish None. `pipeline/games.py`'s `misc` entry declares an empty finish enum,
                      so this profile never asks for one; there is no signal to carry and
                      D3's ladder is never walked for a card that never joins.

    `detected_game` AND `language` ARE CARRIED ON `raw` AND NOWHERE ELSE, said plainly
    because it is a real limit rather than an oversight. `raw` is written verbatim into the
    run's `identifications.json`, so both are recorded and greppable; no screen reads them
    yet, and giving them dataclass fields that only one profile ever fills would be a
    Pokemon-shaped record growing a Yu-Gi-Oh-shaped hole.

    NOT FOLDED, WHERE POKEMON'S IS. `normalize_number` upper-cases and strips a leading `#`,
    which is decoration-removal against a catalog key. There is no catalog key here — the
    string's only job is to be read by a human — and "exactly as printed" is the whole
    instruction this field was authored under. Stripping surrounding whitespace is as far as
    that permits going.
    """
    detected_game = str(payload["detected_game"]).strip().lower()
    if detected_game not in MISC_GAMES:
        raise MalformedIdentification(f"detected_game {detected_game!r} outside the enum")

    return Identification(
        name=str(payload["name"]).strip(),
        number=str(payload["printed_id"]).strip(),
        printed_total="",
        detected_finish=None,
        confidence=_confidence_of(payload),
        raw=payload,
    )


# WHICH PARSER READS WHICH PROFILE'S ANSWER. A third dispatch table beside `PROFILES` and
# `BAND_PROFILES`, and it earns its place: the two schemas do not share a required key list,
# so one parser cannot serve both without asking "is this field present?" of every field —
# which is the shape that reads a missing `printed_total` as an unread one.
#
# A PARSER IS NOT A `Profile` FIELD, and that is deliberate. `Profile` is data the way a
# registry entry is data; hanging a callable off it would make the thing the fingerprint is
# hashed over partly behaviour, and `prompt_fingerprint` would then either hash a function
# object (unstable) or quietly skip a field (a contract change nothing records).
_PARSERS = {
    "pokemon_card_v1": _parse_pokemon,
    "misc_card_v1": _parse_misc,
}

# Every strategy that HAS a profile must have a parser, checked at import for the reason the
# `PROFILES` reconciliation above gives. `unwritten` is exempt by construction: it has no
# profile, so nothing can be submitted under it and no answer can come back to parse.
_unparsed = [
    name for name, found in PROFILES.items() if found is not None and name not in _PARSERS
]
if _unparsed:  # pragma: no cover - import-time contract, not a branch under test
    raise RuntimeError(
        "identify/prompt.py:_PARSERS has no parser for "
        + ", ".join(repr(name) for name in _unparsed)
        + ", which has a Profile and can therefore be submitted. Write the parser — an "
        "answer that comes back with nothing able to read it is a paid call thrown away."
    )


def parse(payload: Any, strategy: str = DEFAULT_PROFILE) -> Identification:
    """Turn one structured-output response into an `Identification`.

    Structured outputs already guarantee the shape, so anything caught here is a real
    surprise and is raised rather than patched over.

    `strategy` DEFAULTS TO POKEMON'S SO THE OLD ONE-ARGUMENT CALL IS UNCHANGED, and that is
    a transitional default rather than a permanent one. `identify/batch.py` still calls
    `parse(text)` with no strategy, because `ImageRequest` carries no strategy either — the
    transport sends one profile for the whole run today. Until that seam moves, a misc answer
    reaching this function without its strategy fails as `missing keys: number,
    printed_total, finish`, which is a loud named failure rather than a card read as
    something it is not. That is the right failure to have while the wiring is half-built.
    """
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise MalformedIdentification(f"not JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise MalformedIdentification(f"expected an object, got {type(payload).__name__}")

    chosen = profile(strategy)  # raises on an unknown or unwritten strategy, by name
    reader = _PARSERS[strategy]

    missing = [key for key in chosen.schema["required"] if key not in payload]
    if missing:
        raise MalformedIdentification(f"missing keys: {', '.join(missing)}")

    return reader(payload)


_APOSTROPHES = "‘’ʼ´`"
_DASHES = "‐‑‒–—―−"
_NAME_NOISE = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """Fold the differences that are typography, not identity.

    Case, accents (Flabebe / Flabébé), curly vs straight apostrophes, en/em dashes, and
    runs of whitespace. Everything else is left alone: "Iron Valiant ex" and "Iron
    Valiant" are different cards and must not compare equal.
    """
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    for ch in _APOSTROPHES:
        text = text.replace(ch, "'")
    for ch in _DASHES:
        text = text.replace(ch, "-")
    return _NAME_NOISE.sub(" ", text).strip().lower()


def normalize_number(number: Any) -> str:
    """Strip decoration only. Zero-padding is `join.join_key`'s job, not ours."""
    text = str(number if number is not None else "").strip()
    return text.lstrip("#").strip().upper()
