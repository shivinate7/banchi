"""The identification contract — prompt, schema, parser. Pure: no network, no SDK.

Everything the model is told and everything we accept back lives here, so
`prompt_fingerprint()` can hash the whole contract into each T1 result file. Change a
word of the prompt or a key of the schema and the fingerprint changes, which is what
makes "rerun after any prompt change" (docs/GATES.md) enforceable rather than a habit.

FIVE PROFILES, AND NONE OF THEM IS ANOTHER ONE WITH FIELDS BLANKED OUT.
`pokemon_card_v1` is the contract T1 scores and the one everything below describes.
`misc_card_v1` reads the ~1% of the shelf that is a Magic, Yu-Gi-Oh, Weiss Schwarz or
foreign-language card: its own system prompt, its own schema, its own parser, because those
cards do not print a `number/total` pair, do not carry the finishes `pipeline/variant.py`
knows about, and do not share a rarity vocabulary. `pokemon_code_v1` is C8's image-to-text
step: it TRANSCRIBES a code card's printed redemption code rather than identifying a
catalog entry, because the ledger the fork exports is only worth keeping if the string
beside each photograph is what a model actually read off it. `riftbound_card_v1` and
`one_piece_card_v1` arrived on 2026-08-23 and are the subject of their own section below:
two games whose export is measured, whose card has never been photographed, and whose
identifier is ONE string rather than Pokemon's two halves. `pipeline/games.py` says
which profile reads which game; this module holds the profiles and never guesses between
them. **A misc card IS identified and IS submitted to the Batch API** — the owner's
correction of 2026-08-23 — and what it never does is join a catalog.

**NOTHING BELOW EXCEPT `pokemon_card_v1` HAS EVER BEEN SCORED, AND THE TWO NEWEST HAVE
NEVER MET A CARD AT ALL.** T1 measures one profile against 150 labelled images; there is
no eval set for any of the others, and for Riftbound and One Piece this repo holds zero
photographs, zero identifications and zero joins. Read every claim in those two sections
as a claim about a CSV file and about what the cardboard is believed to print — never as
an accuracy number. A green harness says these profiles are WIRED, not that they READ.

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
from typing import Any, Dict, Optional, Sequence, Tuple

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


# ------------------------------------------------------------------ the code contract
#
# C8'S IMAGE-TO-TEXT STEP, RATIFIED BY THE OWNER 2026-08-23. A buyer says a code did not
# work; the owner looks the code up, opens the photograph it was read from, and re-reads it
# by eye — because the likeliest failure is this very step, and C6 already rules the remedy
# (replace, don't refund). This profile is the step that flow re-checks, so its one job is
# a transcription honest enough to be worth re-checking: the printed code, exactly as
# printed, with every uncertainty MARKED rather than papered over.
#
# TRANSCRIPTION, NOT IDENTIFICATION, and the schema is built for the difference:
#
#   `code`      one string, verbatim. The card prints four hyphen-separated groups of
#               uppercase letters and digits (lengths 3, 4, 3, 3 — C1), and the layout is
#               told to the model as an ANCHOR, never as a correction: a printed string
#               that does not fit the shape is reported as printed, because "fixing" a
#               code to fit is inventing a bearer instrument. An illegible character
#               comes back as `?` — outside the code alphabet, so unambiguous, and
#               per-character, so the owner re-reading by eye knows WHICH character was
#               doubtful instead of just that one was. A guessed character is the exact
#               failure the dispute flow exists to catch, so the schema gives the model a
#               way to not guess.
#   `name`      the plain-English set/product line printed at the bottom (C1 calls it the
#               secondary cross-check, and that is all it is asked to be) — wanted because
#               the owner sorts code boxes by set, and legible often enough to be worth a
#               field. It maps onto `Identification.name`, which is also the field the
#               `name_only` join strategy reads — where it matches no export row and
#               surfaces through T3's bidirectional reporting rather than joining wrong,
#               since `pipeline/join.py`'s blank-number lookup is exact-name.
#   no finish   same argument as misc's, one line shorter: the registry's `pokemon_code`
#               entry stocks `normal` alone, so there is no question to ask.
#
# THE QR CODE IS DELIBERATELY NOT ASKED ABOUT. The fork's C2 architecture decodes it
# locally and deterministically; asking a vision model to read a QR is asking it to guess
# at a job a library does exactly. This profile reads the HUMAN-readable printing, which
# is what the QR-less dispute lookup and the printed-code re-read both need.

# The placeholder the model writes for a character it cannot read. Outside the printed
# code's own alphabet (uppercase letters, digits, hyphens), so a transcription carrying
# one can never be mistaken for a clean read — and `?` survives verbatim through the
# record and the search, where a partial code still narrows a dispute lookup.
CODE_UNREADABLE_CHAR = "?"

CODE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "code": {
            "type": "string",
            "description": (
                "The redemption code exactly as printed, hyphens included. Write ? in "
                "place of each character you cannot read. Empty if no code is visible."
            ),
        },
        "name": {
            "type": "string",
            "description": (
                "The set or product name printed in plain English at the bottom of the "
                "card, exactly as printed. Empty if not legible."
            ),
        },
        "confidence": {
            "type": "string",
            "enum": list(CONFIDENCE_LEVELS),
            "description": "How legible the printed code was.",
        },
    },
    "required": ["code", "name", "confidence"],
    "additionalProperties": False,
}

CODE_SYSTEM_PROMPT = """\
You transcribe Pokemon Trading Card Game code cards from a photograph of the card front.

A code card carries a QR code and, printed near it, a redemption code: four groups of
uppercase letters and digits separated by hyphens - three characters, then four, then
three, then three. Your job is the printed text. Ignore the QR code itself; it is decoded
by other means. One card per image.

Nothing downstream corrects your transcription. It is next read by a human only when a
buyer disputes the code, so an invented character is worse than an admitted gap: a
plausible wrong character is exactly the failure that human is looking for.

code
  The redemption code, exactly as printed - every character in its printed case, hyphens
  where the card prints them. Do not add, drop or reorder characters, and do not adjust
  what you see to fit the shape described above: if the printing does not fit it, report
  what is printed. For each character you cannot read with certainty, write ? in its
  place instead of choosing the likeliest character. If no code is visible at all,
  return "".

name
  The set or product name printed in plain English at the bottom of the card, exactly as
  printed, punctuation and dashes included. If it is not legible, return "".

confidence
  high    Every character of the code was clearly legible.
  medium  You read the whole code, but some characters were hard to make out.
  low     You could not read parts of the code, or you are unsure of several characters.

Report only what is printed. Never invent a character you cannot read.\
"""

_CODE_USER_TEXT = "Transcribe this code card."
_CODE_USER_TEXT_WITH_HINT = (
    "Transcribe this code card. The box it came from is labelled {hint}, which is a hint "
    "about the set and may be wrong - trust the card over the label."
)
_CODE_HINT_CLAUSE = (
    " The box it came from is labelled {hint}, which is a hint about the set and may be "
    "wrong - trust the card over the label."
)
# REACHABLE, unlike misc's: the registry's `pokemon_code` entry carries a real
# `card_aspect` (a code card is standard card stock), so `geometry.detect_card` can find
# it and a weak read gets a crop retry. The entry claims NO bands — nobody has measured
# where the code is printed relative to the frame — so the retry carries the registered,
# deskewed card alone, and this turn describes exactly that.
_CODE_USER_TEXT_WITH_CROPS = (
    "Transcribe this code card. The first image is the whole card. The images after it "
    "are enlarged views of the SAME card, not different cards. Read the code from "
    "whichever image shows it most clearly."
)


# ------------------------------------------------- the two printed-code contracts
#
# Riftbound and One Piece, written 2026-08-23. Both games had a measured export, a measured
# rarity vocabulary and a two-finish enum in `pipeline/games.py`, and both still named
# `unwritten` — so asking for either one's prompt refused by name rather than falling
# through to Pokemon's. That refusal was correct and these two profiles are what replaces
# it. `unwritten` itself stays, because it is still the right answer for the NEXT game.
#
# WHAT IS MEASURED AND WHAT IS NOT, BEFORE ANYTHING ELSE IN THIS SECTION IS READ.
# Everything below about the export — the identifier shapes, their counts, which cells
# collide, what a fold does to a key — is measured over
# `fixtures/riftbound_export_untouched.csv` (10,078 rows) and
# `fixtures/onepiece_export_untouched.csv` (3,622 rows, THREE SETS out of many, marked
# partial). Everything below about the CARD — where a title sits, whether a set code is
# printed beside the number, whether a treatment is visible at all — is BELIEF. No card of
# either game has been photographed, identified or joined by this project, so there is no
# accuracy number for either profile and there cannot be one until a real photograph
# exists. Both system prompts are therefore written REGION-NEUTRALLY: neither says where on
# the card to look, because copying Pokemon's "across the top of the card" would be
# inventing the one fact nobody has.
#
# ONE STRING, NEVER TWO HALVES, AND THE FIELD IS NAMED `number`. Two separate decisions
# that look like one:
#
#   ONE STRING   Both registry entries carry `join_key: "printed_code"`, and
#                `pipeline/join.py:_lookup_printed_code` matches `card.number` against the
#                export's `Number` cell VERBATIM — it never consults `printed_total`,
#                because "reaching for one would invent half a key". Riftbound's cells are
#                mostly Pokemon-shaped (`179/298`, 8,670 rows) and 450 of them are not
#                (`R04`, `T03`, `T02 // T03`); One Piece has no denominator anywhere
#                (`OP15-079`, `P-105`). A two-field schema would split the first shape
#                happily and then invent a denominator for the second — and a per-game
#                strategy has nowhere to put a fallback. This module's own header already
#                makes the general form of the argument for `misc`: "asking for two halves
#                of a thing that is one string invites the model to invent a split, and a
#                split is what a parser waiting to disagree with the catalog looks like".
#
#   NAMED `number`   THE HIGHEST-CONSEQUENCE LINE IN THIS SECTION, and it is not obvious
#                from anything nearby. `cli/resolve.py` reads the RAW model payload back out
#                of a run's `identifications.json` — `identification.get("number")`,
#                `.get("printed_total")`, `.get("finish")`, `.get("name")`,
#                `.get("confidence")` — and never calls `parse`. Calling this field
#                `printed_code`, or copying `misc`'s `printed_id`, would make that read
#                return None, drop every card to the blank-`Number` name path, and bring the
#                WHOLE RUN back as `no_catalog_row` — a miss that blames the export, which
#                `pipeline/join.py` calls the worst shape a join failure can take because
#                the report points away from the bug. `misc` gets away with `printed_id`
#                only because it is not catalogued and is diverted before that read; these
#                two are catalogued and are not. T7 asserts the seam end to end against the
#                real export rather than trusting this paragraph.
#
# `printed_total` IS NOT IN EITHER SCHEMA. Not a blank we failed to read: a half neither
# game has. Riftbound prints a denominator on most cards but it is part of the one printed
# string, not a second field to be matched separately; One Piece prints none at all. The
# parser sets `printed_total=""` — `misc`'s and `pokemon_code`'s shape exactly — so
# `has_number` is False, which is the honest answer to the question it asks: no
# `number/total` join key CAN be built for these games.
#
# NOT `normalize_number`-FOLDED, AND THE FOLD THAT MATTERS RUNS ELSEWHERE.
# `pipeline/join.py:number_index_key` folds BOTH SIDES of the match: it strips leading zeros
# from every digit run and upper-cases. So `66/298` already matches `066/298`, and
# `op15-079` already matches `OP15-079` — zero padding and letter case are free, and the
# prompts say so rather than demanding a padding the model would have to invent digits to
# supply. What that fold does NOT forgive is a changed character: the letter suffix
# (`066a/298` is a different card from `066/298`), the asterisk (`303*/298` is a different
# card from `303/298`), the `/`, the hyphen, and the spaces around `//` in `T02 // T03`.
# Those are what the prompts spend their rules on. Folding here would buy the join nothing
# and would cost the record its "exactly as printed" property — `record_identification`
# writes the PARSER's `number` onto the card, and that string is what the review screen and
# `GET /search` put in front of a human.
#
# `rarity_clause=""` FOR BOTH, AND THAT IS AN ARGUED CHOICE RATHER THAN AN UNFINISHED ONE.
# D23's clause was BUILT for Pokemon, measured for $0.17, and LOST on every watched axis —
# holdout 0.9706 -> 0.9559, high-confidence misses 5 -> 7, and the finish distribution
# hardened against the clause's own carve-out sentence. It is switched off in production.
# Shipping it NEW on a game with no eval set at all would be spending the opposite of what
# that measurement bought: an unmeasurable change on top of an unmeasured prompt. The
# claim's other two jobs — the ladder cross-check and the chip narrowing — are unaffected
# and need nothing from this module.
#
# TWO FIELDS WERE CONSIDERED FOR THESE SCHEMAS AND ARE DELIBERATELY ABSENT. Both are
# recorded here rather than left to be re-invented, and both need the owner's ruling before
# anyone adds them, because each is new surface area rather than a wiring detail:
#
#   `set` / `set_name`   NEVER. 174 Riftbound join keys reach rows in more than one set —
#                        `247/298` is a $0.29 Origins card AND a $2,739 promo — and the
#                        catalog already resolves that from the sidecar's set hint or
#                        reviews it as `set_ambiguous`. A model-volunteered set would break
#                        that tie by guessing, silently, at three orders of magnitude. This
#                        one is not an open question; it is a refusal.
#   `art_treatment`      OPEN, AND IT IS THE OWNER'S CALL. One Piece's collisions are the
#                        argument: 197 of 395 distinct printed codes map to 2-3 products,
#                        103 of them separable by NOTHING in the export but a parenthetical
#                        in `Product Name` — `OP15-118` is Enel at $9.73, Enel (Alternate
#                        Art) at $27.08 and Enel (Manga) at $1,051.34. Today all of them
#                        land on `duplicate_condition` and go to review, which is the ladder
#                        refusing rather than coin-flipping, and is safe. Against adding it:
#                        nothing downstream reads it (the ladder filters on rarity and
#                        finish only, and there is no treatment claim at capture), several
#                        of the treatments are provenance rather than art and may not be
#                        readable at all, and a field no consumer reads is a field nothing
#                        keeps honest. It would land on `raw` like `misc`'s `detected_game`
#                        — greppable in `identifications.json`, read by no screen. That is a
#                        real precedent and a real argument; it is also a schema change with
#                        a new failure mode, so it belongs in its own step with the ladder
#                        filter it implies, not slipped into v1.

# THE FINISH ENUM COMES FROM EACH GAME'S OWN REGISTRY ENTRY, READ ONCE AT IMPORT, AND NEVER
# FROM `variant.FINISHES`. That constant is Pokemon's three, and reading it for another game
# was a real bug — the same one `cli/resolve.py` and `pipeline/variant.py` each carried on
# 2026-08-23: a Riftbound `foil` fell out of a whitelist that had nothing to do with the
# game and landed as None, losing rung 3's cross-check for every card of every non-Pokemon
# game. One read, bound to one name, used by BOTH the schema the model is sent and the
# whitelist the answer is checked against — so the two can never disagree with each other,
# which is the failure mode a second literal would introduce.
RIFTBOUND_GAME = "riftbound"
ONE_PIECE_GAME = "one_piece"

RIFTBOUND_FINISHES: Tuple[str, ...] = tuple(games.get(RIFTBOUND_GAME)["finishes"])
ONE_PIECE_FINISHES: Tuple[str, ...] = tuple(games.get(ONE_PIECE_GAME)["finishes"])


# --------------------------------------------------------------------- riftbound
#
# THE NAME IS NOT A JOIN KEY HERE AND IS ASKED FOR ANYWAY. `_lookup_printed_code` falls to
# the blank-`Number` name path only when the identifier is empty, and the only blank-`Number`
# rows in this catalogue are 88 sealed-product rows, which are never captured. So `name`
# earns its slot for two other jobs: it is the string the review queue puts beside the
# photograph and `GET /search` substring-matches, and it is an INDEPENDENT second read of the
# same card — the thing that catches a garbled identifier, which is the failure class T1's
# recorded Pokemon misses actually have (`051/197` for `031/197`: right name, wrong digits,
# high confidence, no threshold fires).
#
# WHICH IS WHY THE PROMPT SPENDS SO MANY WORDS ON THE EPITHET. 550 of 1,552 products are
# `Champion, Epithet`, and the comma clause is the ONLY thing separating the fourteen
# distinct Ahri products from each other. A title cut back to `Ahri` names all fourteen.
#
# AND WHY IT FORBIDS THE TREATMENT WORDS BY NAME. 391 products carry a TCGplayer
# parenthetical — `(Alternate Art)`, `(Overnumbered)`, `(Signature)`, `(Metal)`,
# `(Prize Wall)`, `(Best Of)`, `(Top 8)` — which are catalogue vocabulary and almost
# certainly printed nowhere on the card. A model asked for "the name as catalogued" will
# manufacture them; one asked for "exactly as printed" will not. Four products go the other
# way and embed their own collector number in the `Product Name` (`Recruit (271) // Buff`),
# which is the live specimen behind CLAUDE.md's "never join on Product Name" — and the
# reason the prompt also says not to put the identifier in the title.
#
# THE LANDSCAPE PARAGRAPH IS THE ONE PIECE OF THIS PROMPT MOST WORTH CHECKING ON THE FIRST
# REAL PHOTOGRAPH. Origins 275/298-298/298 are 24 consecutive location cards — battlefields
# — and battlefields are printed in landscape, so roughly one card in twelve of a booster
# set arrives rotated a quarter turn in a portrait rig. The rig's per-device rotation
# corrects the portrait cards and leaves these wrong by 90 degrees, and a sideways frame is
# exactly what cost Gate B 45 of 53 cards with "names and numbers both garbled". UNMEASURED:
# no Riftbound card has been photographed. Telling the model the card may be rotated costs
# two sentences and is the cheapest available hedge against the highest-value unknown here.

RIFTBOUND_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": (
                "Card title exactly as printed, including any comma and epithet. Empty if "
                "no title is legible."
            ),
        },
        "number": {
            "type": "string",
            "description": (
                "The collector identifier exactly as printed, as ONE string — keep any "
                "letter suffix, any asterisk, the slash, and the spaces around a double "
                "slash. Empty if the card prints none."
            ),
        },
        "finish": {
            "type": "string",
            "enum": list(RIFTBOUND_FINISHES) + [UNKNOWN_FINISH],
            "description": "Foil treatment visible in this image, or unknown.",
        },
        "confidence": {
            "type": "string",
            "enum": list(CONFIDENCE_LEVELS),
            "description": "How legible the title and the identifier were.",
        },
    },
    "required": ["name", "number", "finish", "confidence"],
    "additionalProperties": False,
}

RIFTBOUND_SYSTEM_PROMPT = """\
You identify Riftbound: League of Legends Trading Card Game singles from a photograph of
the card front.

Read the card in the image and report what is printed on it. One card per image.

Some cards in this game are printed in LANDSCAPE rather than portrait. The photograph is
taken through a fixed portrait rig, so a landscape card reaches you rotated a quarter turn.
Read it as a rotated card rather than assuming you are looking at something else.

name
  The card's title, exactly as printed. Many titles are a champion and an epithet joined by
  a comma - "Ahri, Alluring", "Kai'Sa, Survivor", "Miss Fortune, Bounty Hunter". KEEP THE
  COMMA AND THE EPITHET. They are what separates one champion's cards from each other, and
  a title cut back to the champion's name alone names several different cards at once.
  Keep the rest of the punctuation too: apostrophes ("Zhonya's Hourglass"), exclamation
  marks ("Get Excited!"), hyphens ("Thousand-Tailed Watcher"), colons. A double-sided card
  prints two titles joined by a double slash - write it with a space either side, "Bird //
  Buff". Some titles are a single short word, such as "Buff" or "Smite"; that is ordinary.
  Do not add the set name, the rarity, the card type, the domain, or a description of the
  artwork, and do not put the collector identifier in the title. In particular do not add a
  treatment word such as "Alternate Art", "Overnumbered", "Signature", "Metal" or "Prize
  Wall" - those are catalogue labels, they are not printed on the card, and one added to
  the title makes it match nothing.
  If no title is legible, return "".

number
  The collector identifier, exactly as printed, AS ONE STRING. This game prints it in
  several shapes and every one of them goes in this single field, unsplit:
    179/298      a number over a set total
    066a/298     the same, with a letter suffix
    303*/298     the same, with an asterisk
    SP3/006      a prefixed number over a total
    R04          a rune: a letter and digits, with no total at all
    T03          a token, likewise
    T02 // T03   a double-sided token: two groups joined by a double slash
  Four rules, and each of them changes which card this is:
    - Keep a letter suffix. "066a/298" is a different card from "066/298".
    - Keep an asterisk. It is part of the identifier, not a footnote mark.
    - Keep the spaces either side of "//" on a double-sided token.
    - A left number LARGER than the total is correct and ordinary - "303/298" is a real
      card. Never adjust one side to make it agree with the other.
  Do not supply a total the card does not print: "R04" is complete as it stands, and
  "R04/298" is a card that does not exist. Do not add a set code printed elsewhere on the
  card. Leading zeros do not matter, so do not add or remove one to make an identifier look
  right - report the digits the card shows.
  If the card prints no identifier at all, return "".

finish
  normal   Flat, non-foil card stock across the entire card.
  foil     A foil, holographic or metallic treatment you can see on this card.
  unknown  You cannot tell from this image.
  There is no reverse holo in this game; those are the only two finishes it has.
  Judge only from foil texture, glare, or sheen you can actually see. Flat, evenly lit
  artwork with no foil signal either way is "unknown". Do not infer the finish from the
  card's rarity, its artwork, or how a card of this kind is usually printed - a guess
  here is worse than an admission, because a later step trusts this field to catch
  mis-sorted cards.

confidence
  high    You can read both the title and the identifier clearly.
  medium  One of the two is partly obscured, but you are reasonably sure of it.
  low     You are guessing at either field.

Report only what is printed. Never invent a card you cannot read.\
"""

_RIFTBOUND_USER_TEXT = "Identify this card."
_RIFTBOUND_USER_TEXT_WITH_HINT = (
    "Identify this card. The stack it came from is labelled {hint}, which is a hint "
    "about the set and may be wrong - trust the card over the label."
)
_RIFTBOUND_HINT_CLAUSE = (
    " The stack it came from is labelled {hint}, which is a hint about the set and may "
    "be wrong - trust the card over the label."
)
# NO TITLE OR NUMBER BANDS NAMED, because the registry entry claims none: nothing has
# measured where a Riftbound card puts either, and a band described to the model that the
# cropper never cut would be a promise the images do not keep. Same shape as
# `pokemon_code`'s turn, for the same reason.
_RIFTBOUND_USER_TEXT_WITH_CROPS = (
    "Identify this card. The first image is the whole card. The images after it are "
    "enlarged views of the SAME card, not different cards. Read each field from whichever "
    "image shows it most clearly."
)


# --------------------------------------------------------------------- one piece
#
# THE NAME DOES MORE WORK HERE THAN IN RIFTBOUND, and one population depends on it entirely:
# 547 rows of this export carry a blank `Number`, of which 530 are DON!! cards, and
# `_lookup_printed_code` falls to the name path for exactly those. That fallback is an EXACT
# match on the raw `Product Name`, and TCGplayer names those products after their artwork —
# `DON!! Card (Luffy)`, `DON!! Card (Boa Hancock) (Gold)` — a string the card does not print.
# So every DON!! card will come back unmatched and be reported in both directions. That is
# honest rather than broken (a wrong join would be worse), but it is an EXPECTED POPULATION
# and not a surprise, and it is written here so the first real run does not read it as a
# defect.
#
# THREE DISAMBIGUATOR CONVENTIONS, NONE OF THEM PRINTED ON THE CARD. 495 of 702 products
# carry a parenthetical, in three inconsistent forms: `Brook (OP15-022)`, `Basil Hawkins -
# OP07-029 (Reprint)`, `Uta (061) (Manga)`. They exist because 56 base names appear at more
# than one printed code — Brook alone at five. The card prints `Brook`. A model asked for
# "the catalogue name" will reconstruct one of these three forms; one asked for the printed
# name will not, and the code below is what separates them anyway.
#
# TWO PRINTING CONVENTIONS THAT LOOK LIKE TYPOS AND ARE NOT, both called out in the prompt
# because `normalize_name` will not save us: it folds case, accents, apostrophes, dashes and
# whitespace runs, and it does NOT touch full stops. So `Monkey D. Luffy` never equals
# `Monkey.D.Luffy` (51 products print the dotted, unspaced form), and a respaced
# `Eustass "Captain" Kid` never equals the printed `Eustass"Captain"Kid`. On the DON!! name
# path that is a miss; everywhere else it is the review queue's eyeball comparison failing
# on a card that was actually read correctly.
#
# THE SET HINT IS WORTH LESS HERE THAN ANYWHERE ELSE, and the hint clause says so. The
# export's `Set Name` is the TCGplayer PRODUCT the card was sold in, not the set code
# printed on it: `Premium Booster -The Best- Vol. 2` alone holds cards numbered from 29
# different set codes. Only 2 of 197 colliding numbers span more than one `Set Name`, so the
# hint is close to worthless as a tiebreaker — and a model told the label is the set will
# "correct" a printed `OP01` to match a stack labelled for a Premium Booster. The clause
# therefore warns that the two disagree ordinarily.

ONE_PIECE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": (
                "Card title exactly as printed, with nothing added in parentheses. Empty "
                "if no title is legible."
            ),
        },
        "number": {
            "type": "string",
            "description": (
                "The printed card code exactly as printed, as ONE string, with its hyphen "
                "where the card prints one. Empty if the card prints none."
            ),
        },
        "finish": {
            "type": "string",
            "enum": list(ONE_PIECE_FINISHES) + [UNKNOWN_FINISH],
            "description": "Foil treatment visible in this image, or unknown.",
        },
        "confidence": {
            "type": "string",
            "enum": list(CONFIDENCE_LEVELS),
            "description": "How legible the title and the printed code were.",
        },
    },
    "required": ["name", "number", "finish", "confidence"],
    "additionalProperties": False,
}

ONE_PIECE_SYSTEM_PROMPT = """\
You identify One Piece Card Game singles from a photograph of the card front.

Read the card in the image and report what is printed on it. One card per image.

name
  The card's title, exactly as printed. Copy the characters the card shows and nothing
  else. Three conventions in this game look like mistakes and are not:
    - Names joined by full stops with no spaces around them - "Monkey.D.Luffy",
      "Edward.Newgate", "Marshall.D.Teach". Write them exactly that way; do not respace
      one to "Monkey D. Luffy".
    - Names carrying quotation marks with no spaces around them, as in Eustass"Captain"Kid.
    - Long sentence titles on event and stage cards - "Would You Let Me Eat the Flame-Flame
      Fruit?". A title in this game is not necessarily short.
  Do not add anything the card does not print. In particular do not append the card's code
  to its title, and do not add a word such as "Reprint", "Alternate Art", "Manga", "Dash
  Pack" or "SP" - those are catalogue labels rather than printed titles, and one added to
  the title makes it match nothing. Several different cards genuinely share one printed
  title; that is expected, and the code below is what separates them.
  If no title is legible, return "".

number
  The card's printed code, exactly as printed, AS ONE STRING. It is a set code, a hyphen
  and a three-digit index - "OP15-079", "EB04-042", "ST26-005", "PRB02-014" - or, on a
  promo, a single letter, a hyphen and three digits: "P-105".
  THE HYPHEN IS THE PART THAT MATTERS. Write one hyphen exactly where the card prints one.
  "OP15 079", "OP15/079" and "OP-15-079" are all wrong, and none of them will match
  anything. Leading zeros and letter case do not matter - "OP15-79" and "op15-079" are
  read the same as "OP15-079" - so never add or remove a zero to make a code look right.
  This game prints NO card-count denominator anywhere: there is no "/" in the code and no
  set total to report, and you must not supply one.
  A card carries several other numbers - a cost, a power in thousands such as 5000, a
  counter value such as +1000, and on a leader card a life value. The code is the only
  letters-then-hyphen-then-digits string on the card. Use the shape above to FIND it, never
  to correct it: if what is printed does not fit that shape, report what is printed.
  Some cards in this game print no code at all. If this one prints none, return "".

finish
  normal   Flat, non-foil card stock across the entire card.
  foil     A foil, holographic or metallic treatment you can see on this card.
  unknown  You cannot tell from this image.
  There is no reverse holo in this game; those are the only two finishes it has.
  Judge only from foil texture, glare, or sheen you can actually see. Flat, evenly lit
  artwork with no foil signal either way is "unknown". Do not infer the finish from the
  card's rarity, its artwork, or how a card of this kind is usually printed - a guess
  here is worse than an admission, because a later step trusts this field to catch
  mis-sorted cards.

confidence
  high    You can read both the title and the printed code clearly.
  medium  One of the two is partly obscured, but you are reasonably sure of it.
  low     You are guessing at either field.

Report only what is printed. Never invent a card you cannot read.\
"""

_ONE_PIECE_USER_TEXT = "Identify this card."
_ONE_PIECE_USER_TEXT_WITH_HINT = (
    "Identify this card. The stack it came from is labelled {hint}, which is a hint about "
    "the set and may be wrong - trust the card over the label. In this game the label "
    "often names the product the cards were sold in rather than the set code printed on "
    "them, so the two disagreeing is ordinary and is not a reason to change what you read."
)
_ONE_PIECE_HINT_CLAUSE = (
    " The stack it came from is labelled {hint}, which is a hint about the set and may be "
    "wrong - trust the card over the label. In this game the label often names the product "
    "the cards were sold in rather than the set code printed on them, so the two "
    "disagreeing is ordinary and is not a reason to change what you read."
)
# As Riftbound's: the registry claims no bands, so the retry carries the registered card
# alone and this turn describes exactly that.
_ONE_PIECE_USER_TEXT_WITH_CROPS = (
    "Identify this card. The first image is the whole card. The images after it are "
    "enlarged views of the SAME card, not different cards. Read each field from whichever "
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

POKEMON_CODE_V1 = Profile(
    model=MODEL,
    max_tokens=MAX_TOKENS,
    system=CODE_SYSTEM_PROMPT,
    user=_CODE_USER_TEXT,
    user_with_hint=_CODE_USER_TEXT_WITH_HINT,
    user_with_crops=_CODE_USER_TEXT_WITH_CROPS,
    hint_clause=_CODE_HINT_CLAUSE,
    # One rarity in the whole game (`Code Card` — the registry entry's entire vocabulary),
    # so a stack claim can disambiguate nothing: there is nothing else the card could be.
    # No clause, however loudly a claim is supplied; same posture as misc's.
    rarity_clause="",
    schema=CODE_SCHEMA,
)

RIFTBOUND_CARD_V1 = Profile(
    model=MODEL,
    max_tokens=MAX_TOKENS,
    system=RIFTBOUND_SYSTEM_PROMPT,
    user=_RIFTBOUND_USER_TEXT,
    user_with_hint=_RIFTBOUND_USER_TEXT_WITH_HINT,
    user_with_crops=_RIFTBOUND_USER_TEXT_WITH_CROPS,
    hint_clause=_RIFTBOUND_HINT_CLAUSE,
    # Empty, and argued at length in this profile's section above: D23's clause was
    # measured on Pokemon and lost, and this game has no eval set to measure a new one
    # against. `user_text` renders no claim however loudly one is supplied.
    rarity_clause="",
    schema=RIFTBOUND_SCHEMA,
)

ONE_PIECE_CARD_V1 = Profile(
    model=MODEL,
    max_tokens=MAX_TOKENS,
    system=ONE_PIECE_SYSTEM_PROMPT,
    user=_ONE_PIECE_USER_TEXT,
    user_with_hint=_ONE_PIECE_USER_TEXT_WITH_HINT,
    user_with_crops=_ONE_PIECE_USER_TEXT_WITH_CROPS,
    hint_clause=_ONE_PIECE_HINT_CLAUSE,
    rarity_clause="",
    schema=ONE_PIECE_SCHEMA,
)

# ONE STRATEGY NAME NOW NAMES NO PROFILE, WHERE THERE USED TO BE TWO.
#
#   unwritten       nobody has written this game's prompt YET. A gap with a fix. It named
#                   `riftbound` and `one_piece` until 2026-08-23, when both got the profiles
#                   above; it names NOBODY today, and it stays anyway — it is the right
#                   answer for the next game added, and its refusal is what stops that game
#                   falling through to Pokemon's prompt, which fits every call and reads
#                   every card wrong.
#
#                   IT IS KEPT UNCLAIMED WHERE `operator_note` WAS DELETED UNCLAIMED, and the
#                   difference is not inconsistency. Deleting `operator_note` deleted a STATE
#                   the product does not have — a game never sent to the model — along with
#                   an exception nothing could raise and a predicate that could only answer
#                   True. `unwritten` describes a state the product will certainly be in
#                   again the moment a sixth game is registered, and its refusal is
#                   reachable, tested, and the only thing standing between that game and
#                   another game's contract.
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
    "pokemon_code_v1": POKEMON_CODE_V1,
    "riftbound_card_v1": RIFTBOUND_CARD_V1,
    "one_piece_card_v1": ONE_PIECE_CARD_V1,
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


def _parse_code(payload: Dict[str, Any]) -> Identification:
    """`pokemon_code_v1`'s answer: the transcribed code, carried in `number`.

    `number` IS THE DECISION, AND HERE IS THE ARGUMENT FOR IT. The code has to land on the
    card record for C8's lookup to be two taps, and `record_identification` writes exactly
    four columns: `name`, `number`, `printed_total`, `confidence`. Of those, `number` is
    the one `GET /search` both substring-matches and ranks EXACT on — so the code landing
    there makes the dispute lookup the existing search with zero new UI: type the code,
    get the card, tap its photo. And it is free for this game: `pokemon_code`'s join
    strategy is `name_only`, so nothing ever composes a `number/printed_total` key from
    these fields — `printed_total` stays "" and `has_number` stays False, which is
    correct, because no join key CAN be built from a redemption code. A new column on the
    record was the alternative, and it would fork every reader of the record to serve a
    string that fits an existing column's contract ("the identifier printed on the card")
    exactly.

    NOT `normalize_number`-FOLDED, for misc's reason verbatim: upper-casing and
    `#`-stripping are decoration-removal against a catalog key, there is no catalog key
    here, and "exactly as printed" is the whole instruction this field was authored
    under. Surrounding whitespace is as far as it goes — a `?` written for an illegible
    character survives to the record, where a partial code still narrows a lookup.

    `name` is the printed set line, same field on the card the owner sorts code boxes
    by. It reaches the record and the search like any identification's name; if a join
    ever runs over a code card it matches no export row exactly and surfaces through the
    unmatched report rather than joining wrong.
    """
    return Identification(
        name=str(payload["name"]).strip(),
        number=str(payload["code"]).strip(),
        printed_total="",
        detected_finish=None,
        confidence=_confidence_of(payload),
        raw=payload,
    )


def _parse_printed_code(payload: Dict[str, Any], finishes: Tuple[str, ...]) -> Identification:
    """Riftbound's and One Piece's answer: ONE printed identifier, carried in `number`.

    ONE BODY FOR TWO GAMES, WHICH IS NOT THE SAME AS ONE PROFILE FOR TWO GAMES. The two
    system prompts are different documents and are meant to stay different — they describe
    different identifier shapes, different name conventions and different hazards. What is
    genuinely shared is the SHAPE of the answer: four keys, one of which is an identifier
    that is already one string. Writing that mapping twice would be two places for the
    `printed_total=""` rule to drift apart.

    `finishes` IS PASSED IN RATHER THAN LOOKED UP, and it is the same tuple the caller's
    schema enum was built from. That is the whole reason this cannot disagree with the
    contract the model was sent: one read of one registry entry feeds both. Never
    `variant.FINISHES` — that is Pokemon's three, and reading it here would reject the very
    finish these games' own registry entries author.

    THE MAPPING, AND WHERE EACH FIELD GOES:

      name            as printed, stripped. Same field, same meaning.
      number          the WHOLE printed identifier. It is named `number` in the schema for
                      the reason this module's printed-code section states at length:
                      `cli/resolve.py` reads that key off the RAW payload and never calls
                      `parse`, so any other name silently turns the run into
                      `no_catalog_row`.
      printed_total   "" — a half neither game has, not a half we failed to read.
                      `has_number` is therefore False, which is the honest answer: no
                      `number/total` key CAN be built for a game keyed by `printed_code`.
      detected_finish the model's read, kept only if this game stocks it, with `unknown`
                      mapped to None so `variant.resolve` sees D3's no-signal case rather
                      than a manufactured disagreement.

    NOT `normalize_number`-FOLDED, for misc's and the code card's reason plus one of its
    own. Case and zero padding are already folded on BOTH SIDES by
    `pipeline/join.py:number_index_key`, so folding here buys the join nothing — while
    `record_identification` writes this exact string onto the card, where the review queue
    and `GET /search` show it to a human. `normalize_number` would also strip a leading
    `#`, which is decoration on a Pokemon collector number and would be a real printed
    character here. Surrounding whitespace is as far as it goes.
    """
    finish = str(payload["finish"]).strip().lower()
    if finish == UNKNOWN_FINISH:
        detected: Optional[str] = None
    elif finish in finishes:
        detected = finish
    else:
        raise MalformedIdentification(
            f"finish {finish!r} outside the enum {finishes}"
        )

    return Identification(
        name=str(payload["name"]).strip(),
        number=str(payload["number"]).strip(),
        printed_total="",
        detected_finish=detected,
        confidence=_confidence_of(payload),
        raw=payload,
    )


def _parse_riftbound(payload: Dict[str, Any]) -> Identification:
    """`riftbound_card_v1`'s answer, checked against Riftbound's own finish enum."""
    return _parse_printed_code(payload, RIFTBOUND_FINISHES)


def _parse_one_piece(payload: Dict[str, Any]) -> Identification:
    """`one_piece_card_v1`'s answer, checked against One Piece's own finish enum."""
    return _parse_printed_code(payload, ONE_PIECE_FINISHES)


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
    "pokemon_code_v1": _parse_code,
    "riftbound_card_v1": _parse_riftbound,
    "one_piece_card_v1": _parse_one_piece,
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
