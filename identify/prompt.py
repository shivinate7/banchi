"""The identification contract — prompt, schema, parser. Pure: no network, no SDK.

Everything the model is told and everything we accept back lives here, so
`prompt_fingerprint()` can hash the whole contract into each T1 result file. Change a
word of the prompt or a key of the schema and the fingerprint changes, which is what
makes "rerun after any prompt change" (docs/GATES.md) enforceable rather than a habit.

Two shapes deserve a note:

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
from typing import Any, Dict, Optional

from pipeline import variant

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


def user_text(set_hint: Optional[str] = None, with_crops: bool = False) -> str:
    """The per-image turn. The set hint is an optional accelerator (D2), never required."""
    if with_crops:
        text = _USER_TEXT_WITH_CROPS
        return text + _HINT_CLAUSE.format(hint=set_hint) if set_hint else text
    if set_hint:
        return _USER_TEXT_WITH_HINT.format(hint=set_hint)
    return _USER_TEXT


def prompt_fingerprint() -> str:
    """Stable hash of the contract T1 SCORES: model, prompt, both user turns, schema.

    The crop-retry turn is deliberately NOT in here, and the omission is the same argument
    v2 §4.6 makes about not invalidating the production cache on a prompt change. T1 never
    sends crops — it scores one flat render per card — so a reworded crop-retry turn cannot
    move a T1 number by a single card. Folding it in would invalidate every cached run and
    charge for a re-measurement of something that did not change. `retry_fingerprint`
    records it separately, so it is still pinned; it just does not pretend to gate a score
    it has no bearing on.
    """
    payload = json.dumps(
        {
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
            "system": SYSTEM_PROMPT,
            "user": _USER_TEXT,
            "user_with_hint": _USER_TEXT_WITH_HINT,
            "schema": SCHEMA,
        },
        sort_keys=True,
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def retry_fingerprint() -> str:
    """Stable hash of the crop-retry turn, recorded in the run manifest."""
    payload = json.dumps(
        {"user_with_crops": _USER_TEXT_WITH_CROPS, "hint_clause": _HINT_CLAUSE},
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


def parse(payload: Any) -> Identification:
    """Turn one structured-output response into an `Identification`.

    Structured outputs already guarantee the shape, so anything caught here is a real
    surprise and is raised rather than patched over.
    """
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise MalformedIdentification(f"not JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise MalformedIdentification(f"expected an object, got {type(payload).__name__}")

    missing = [key for key in SCHEMA["required"] if key not in payload]
    if missing:
        raise MalformedIdentification(f"missing keys: {', '.join(missing)}")

    finish = str(payload["finish"]).strip().lower()
    if finish == UNKNOWN_FINISH:
        detected = None
    elif finish in variant.FINISHES:
        detected = finish
    else:
        raise MalformedIdentification(f"finish {finish!r} outside the enum")

    confidence = str(payload["confidence"]).strip().lower()
    if confidence not in CONFIDENCE_LEVELS:
        raise MalformedIdentification(f"confidence {confidence!r} outside the enum")

    return Identification(
        name=str(payload["name"]).strip(),
        number=normalize_number(payload["number"]),
        printed_total=normalize_number(payload["printed_total"]),
        detected_finish=detected,
        confidence=confidence,
        raw=payload,
    )


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
