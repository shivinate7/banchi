"""Reading a capture directory: photos, their JSON sidecars, and the position.

A CARD IS NEVER SKIPPED. That is the whole shape of this module. v1 bug #5 was a pipeline
that silently skipped identified cards and reported nothing, so every degraded case here has
a named outcome that ends in the card being processed and recorded:

  sidecar present and valid          normal path
  sidecar missing or malformed, but  position recovered from the filename and treated as
  the filename carries the position  EQUIVALENT — the same server writes both, so it is the
                                     same claim from the same source, not a lesser one
  no position recoverable at all     still identified, then routed to the main review queue
                                     flagged `no_position`

A missing set hint or a missing variant toggle is not a problem at all. D3's rung 2 exists
for exactly that card, and D2 calls the set hint an optional accelerator.

A MISSING `game` IS NOT A PROBLEM EITHER, AND IT IS NOT THE SAME KIND OF ABSENCE. D21 is
explicit that D3's null-means-no-claim does not transfer: a null finish is meaningful
because a ladder infers a finish underneath it, and nothing infers a game. So an absent
`game` is not "no claim" — it is a sidecar written before the field existed, every one of
which is a Pokemon card, and `Capture.game_or_default` backfills it at the read. A game
string the registry does not know is a different case and IS a problem: it is reported and
carried forward unchanged, never dropped, because a dropped one would read as absent and
backfill to Pokemon.

`--variant` FILLS GAPS AND NEVER OVERRIDES (D3 rung 1). It supplies the finish for photos
whose sidecar records none, and is ignored for photos that carry one. The toggle is a claim,
and a flag that could replace it across a whole run is exactly what would stop it being one.
The case the flag exists for is the capture app not existing yet: a directory with no
sidecars at all, where every card stocked in more than one finish would otherwise cost a
review-queue tap. There is nothing to override in that case, which is the point.

FILENAME CONVENTION, since it is load-bearing for the recovery path above:

    captures/box3/0017.jpg      box from the directory, index from the stem
    captures/box3-0017.jpg      both from the stem
    captures/anything/0017.jpg  index only; box has to come from the sidecar or --box

The box marker is matched first and removed, and the index is the last run of digits in what
is left — so `box3-0017` cannot read its own box number as an index, which is the one way
this gets quietly wrong.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from pipeline import games, variant

PHOTO_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")
SIDECAR_SUFFIX = ".json"

# Source of the position, reported so a run can be read for how much of it was recovered
# rather than declared.
FROM_SIDECAR = "sidecar"
FROM_FILENAME = "filename"
FROM_NOWHERE = "none"

_BOX_RE = re.compile(r"box[\s_-]*(\d+)", re.IGNORECASE)
_DIGITS_RE = re.compile(r"(\d+)")

# Sidecar keys, with the aliases a hand-written or older file might use.
_INDEX_KEYS = ("position", "index", "card")
_BOX_KEYS = ("box",)
_HINT_KEYS = ("set_hint", "set", "hint")
_VARIANT_KEYS = ("variant", "metadata_finish", "finish")
# One spelling and no aliases, unlike the two above. Those carry aliases because sidecars
# written by hand and by older tools exist; nothing has ever written a `game` key under
# another name, and inventing spellings for a field on its first day is how a vocabulary
# nothing audits gets started.
_GAME_KEYS = ("game",)
# Same rule as `game`, first day, one spelling.
_RARITY_CLAIM_KEYS = ("rarity_claim",)
_NOTE_KEYS = ("note",)


@dataclass(frozen=True)
class Capture:
    """One photograph, and everything the pipeline knows about it before identification."""

    photo: Path
    sidecar: Optional[Path] = None
    box: Optional[int] = None
    index: Optional[int] = None
    set_hint: Optional[str] = None
    metadata_finish: Optional[str] = None
    # THE RAW CLAIM, NOT THE BACKFILLED ONE. `None` means the sidecar named no game, which
    # is every file written before D21; `game_or_default` is where the substitution happens
    # and it is a property so the substitution is visible at the point of the read.
    #
    # THE DISTINCTION IS NOT COSMETIC AND IT IS NOT D3's. A `metadata_finish` of None is
    # meaningful because a ladder infers a finish underneath it; nothing infers a game. What
    # this None is for is the other direction: `cli/cmd_identify.py` re-records the card from
    # this object, and a backfilled `pokemon` written back through that path would be a
    # write-side default — turning "nobody was asked" into "the operator said Pokemon" on
    # disk, permanently, on the first identify run. D21 forbids exactly that.
    #
    # An unregistered string is kept here as-is rather than dropped, with a problem noted.
    # Dropping it would fall back to `None`, which backfills to Pokemon — a Riftbound card
    # priced off a Pokemon export, which is the one outcome `games.get`'s docstring is
    # written to prevent.
    game: Optional[str] = None
    # D23's multi-select stack claim: the exact `Rarity` cells the operator said this
    # card's stack holds, validated against the game's own vocabulary at the read — which
    # is why `game` is read FIRST in `load`. None is no claim and narrows nothing; unlike
    # `game`, dropping a bad member here is SAFE, because no claim is the compatibility
    # default rather than a silent Pokemon. A tuple for the same reason the dataclass is
    # frozen.
    rarity_claim: Optional[Tuple[str, ...]] = None
    # Free text the operator typed AFTER the capture, describing a card the pipeline will
    # never identify. Read back only so a re-record carries it; nothing here parses it.
    note: Optional[str] = None
    source: str = FROM_NOWHERE
    problem: Optional[str] = None
    # True when `metadata_finish` came from `--variant` rather than from the sidecar. The
    # ladder treats both identically (D3 rung 1 is one rung), but the run report says how
    # many cards took the flag — a number worth seeing before trusting a whole box to it.
    variant_from_flag: bool = False

    @property
    def has_position(self) -> bool:
        return self.box is not None and self.index is not None

    @property
    def game_or_default(self) -> str:
        """The game to process this card as — D21's READ-SIDE BACKFILL, and nothing else.

        A sidecar written before `game` existed names none, and every one of those is a
        Pokemon card. The substitution is here, at the read, rather than in `load` or in the
        dataclass default, so that a caller writing the claim back can still tell the two
        apart — which is the whole reason `game` is Optional a few lines up.
        """
        return self.game or games.DEFAULT_GAME

    @property
    def key(self) -> str:
        """Stable id for the batch and the cache. Falls back to the filename when there is
        no position, so a positionless card still has something to be keyed by — it must
        still be identified, and results come back keyed by whatever was sent."""
        if self.has_position:
            return f"{self.box}/{self.index}"
        return f"file:{self.photo.name}"

    @property
    def describe(self) -> str:
        where = self.key if self.has_position else f"{self.photo.name} (no position)"
        extra = f" [{self.problem}]" if self.problem else ""
        return f"{where}{extra}"


def _first(payload: dict, keys: Sequence[str]):
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return payload[key]
    return None


def _as_int(value) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _check_variant(value, game: Optional[str]):
    """(claim, problem) — the sidecar's finish claim, read defensively and PER GAME.

    IT READ `variant.FINISHES` — POKEMON'S THREE — FOR EVERY GAME, and it was read BEFORE
    the game key, while `_check_rarity_claim` directly below it carries a comment saying
    that exact order is load-bearing. The finish has the same per-game vocabulary and obeyed
    neither rule: a Riftbound sidecar recording `foil` had its claim silently dropped and
    reported as "outside ('normal', 'holo', 'reverse_holo')" — an enum belonging to another
    game. D3 rung 1's whole argument is that the toggle is a CLAIM the ladder trusts; a
    reader that discards it for the wrong game's vocabulary defeats the rung entirely.

    IT IS STILL SINGLE-VALUED HERE, DELIBERATELY, and that is a split rather than an
    oversight. D3 rung 1 was amended the same day to make the claim a SET, and this reader
    is one of five places that has to move for that — with `store/master.py`, the capture
    route, the capture screen's Finish track and the tests that assert a bare `"holo"`. They
    move together or the record and the sidecar disagree about the shape of a claim, which
    is the one disagreement `record_capture` cannot survive. A list is already accepted and
    reduced to its first member below, so a sidecar written by a newer client is not
    misread in the meantime.

    The three game cases are `_check_rarity_claim`'s, for its reasons: a registered game
    checks membership, an unregistered one keeps members verbatim (its own problem is
    already recorded and the join refuses the card by name), and no game at all checks
    against `games.DEFAULT_GAME` — D21's read-side backfill, the game the card will be
    processed as.

    An empty claim, or one whose every member dropped, is None: no claim, and rungs 2 and 3
    stay live.
    """
    if value is None:
        return None, None
    if isinstance(value, str):
        members = [value]
    elif isinstance(value, (list, tuple)):
        members = list(value)
    else:
        return None, f"variant {value!r} is not a finish or a list of finishes"

    cleaned = [str(item).strip().lower() for item in members if str(item).strip()]
    if not cleaned:
        return None, None

    # `games.get`, NOT `variant.vocabulary`. The latter goes through `games.require`, which
    # refuses a game whose vocabulary is empty (D22) — and that refusal is right for a
    # pipeline consumer and wrong for this reader, which cannot tell an UNREGISTERED game
    # from a registered one with no finishes. Reaching the same `except` for both made
    # `misc` return a tuple where every other path returns a string, which is a type leak a
    # caller finds later and at a distance. Split here: unregistered keeps its member
    # verbatim, and `misc` — registered, authoring no finishes — drops with a problem, which
    # is what the capture route already answers for a finish sent under it.
    try:
        entry = games.get((game or games.DEFAULT_GAME).strip().lower())
    except games.UnknownGame:
        return cleaned[0], None
    stocked = tuple(entry["finishes"])

    kept = [item for item in stocked if item in cleaned]
    dropped = [item for item in cleaned if item not in stocked]
    problem = None
    if dropped:
        problem = (
            f"variant {', '.join(repr(d) for d in dropped)} is outside "
            + (f"{entry['display']}'s finishes {stocked}" if stocked
               else f"{entry['display']}, which stocks no finishes at all")
        )
    # FIRST MEMBER IN THE GAME'S OWN ENUM ORDER, not the file's — see the docstring for why
    # this is not a tuple yet. Enum order rather than file order so the reduction is stable:
    # a two-member claim reduced by the order somebody happened to type it would resolve
    # differently for the same claim written twice.
    return (kept[0] if kept else None), problem


def _check_rarity_claim(value, game: Optional[str]):
    """(claim, problem) — the sidecar's `rarity_claim`, read defensively.

    Modelled on `_check_variant`: an invalid member is DROPPED WITH A PROBLEM RECORDED,
    never coerced to the nearest valid one. The shapes a hand-written sidecar produces are
    handled ahead of the membership check, and the first one is the classic bug this
    function exists to refuse: `"rarity_claim": "Common"` is ONE rarity, and iterating the
    string would make it six letters, none of which is a rarity, all of which would be
    dropped — a claim silently erased by its own reader.

    `game` MUST ALREADY BE READ — the vocabulary is per-game, which is why `load` reads the
    game key first. Three cases:

      registered game     members are checked against its `rarities`; outsiders drop with a
                          problem. `rarities_not_claimed` is deliberately not consulted —
                          `Code Card` is a real cell and never a stack claim (D22).
      unregistered game   membership cannot be checked, so members are kept verbatim with
                          no further problem — the game's own problem is already recorded,
                          and the join refuses the whole card by name before any claim is
                          consulted.
      no game (None)      D21's read-side backfill applies at the read, so members are
                          checked against `games.DEFAULT_GAME`'s vocabulary — the same game
                          the card will be processed as.

    An empty claim — `[]`, or every member dropped — is None: no claim, narrows nothing.
    """
    if value is None:
        return None, None
    if isinstance(value, str):
        members = [value]
    elif isinstance(value, (list, tuple)):
        members = list(value)
    else:
        return None, f"rarity_claim {value!r} is not a list of rarity strings"

    cleaned = [str(item).strip() for item in members if str(item).strip()]
    if not cleaned:
        return None, None

    try:
        entry = games.get((game or games.DEFAULT_GAME).strip().lower())
    except games.UnknownGame:
        return tuple(cleaned), None

    vocabulary = tuple(entry["rarities"])
    kept = tuple(item for item in cleaned if item in vocabulary)
    dropped = [item for item in cleaned if item not in vocabulary]
    problem = None
    if dropped:
        problem = (
            f"rarity_claim {', '.join(repr(d) for d in dropped)} not in "
            f"{entry['key']}'s rarities"
        )
    return (kept or None), problem


def _check_game(value) -> Optional[str]:
    """A game outside the registry is a problem to report, never a value to coerce.

    Modelled on `_check_variant` and tested against `pipeline/games.py` rather than a
    literal tuple, for the reason `cli/resolve.py` gives about `variant.FINISHES`: the
    registry has one home, and a copy of its keys written here could not be kept in step
    with it. Registered but unverified games (`riftbound`, `one_piece`) pass — whether a
    game can be PROCESSED is `games.require`'s question and belongs to the consumer, not to
    a reader whose only job is to say what the file claims.
    """
    if value is None:
        return None
    text = str(value).strip().lower()
    try:
        games.get(text)
    except games.UnknownGame:
        return None
    return text


def position_from_path(path: Path, root: Optional[Path] = None):
    """(box, index) recovered from the filename and its directories, either may be None."""
    stem = path.stem
    box = None

    match = _BOX_RE.search(stem)
    if match:
        box = _as_int(match.group(1))
        stem = stem[: match.start()] + stem[match.end() :]

    if box is None:
        # Walk up from the photo, stopping at the capture root so a directory called
        # `box-of-junk` three levels above cannot supply a box number.
        for parent in path.parents:
            if root is not None and parent == Path(root).parent:
                break
            found = _BOX_RE.search(parent.name)
            if found:
                box = _as_int(found.group(1))
                break
            if root is not None and parent == Path(root):
                break

    digits = _DIGITS_RE.findall(stem)
    index = _as_int(digits[-1]) if digits else None
    return box, index


def read_sidecar(path: Path):
    """(payload, problem). A malformed sidecar is a problem, never an exception."""
    try:
        payload = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"sidecar unreadable: {exc}"
    if not isinstance(payload, dict):
        return None, "sidecar is not a JSON object"
    return payload, None


def load(
    photo: Path,
    root: Optional[Path] = None,
    box: Optional[int] = None,
    variant_default: Optional[str] = None,
) -> Capture:
    """One capture, with the position resolved through the table in the module docstring."""
    sidecar_path = photo.with_suffix(SIDECAR_SUFFIX)
    payload = None
    problems: List[str] = []

    if sidecar_path.is_file():
        payload, problem = read_sidecar(sidecar_path)
        if problem:
            problems.append(problem)
    else:
        sidecar_path = None

    sidecar_box = sidecar_index = None
    set_hint = metadata_finish = game = rarity_claim = note = None
    if payload is not None:
        sidecar_box = _as_int(_first(payload, _BOX_KEYS))
        sidecar_index = _as_int(_first(payload, _INDEX_KEYS))
        raw_hint = _first(payload, _HINT_KEYS)
        set_hint = str(raw_hint).strip() if raw_hint is not None else None
        raw_game = _first(payload, _GAME_KEYS)
        game = _check_game(raw_game)
        if raw_game is not None and game is None:
            problems.append(f"game {raw_game!r} is not in {games.keys()}")
            # KEPT, NOT DROPPED, and this is the one place in this module where a rejected
            # value survives its own rejection. A dropped game reads as an ABSENT one, and
            # an absent one backfills to Pokemon — so a typo'd or future game would be
            # joined against a Pokemon export and priced off it. Carrying the string forward
            # means the consumer's `games.get` refuses by name instead.
            game = str(raw_game).strip().lower()
        # AFTER `game`, NEVER BEFORE IT: a claim's vocabulary is the game's, so the order
        # of these reads is load-bearing. BOTH claims obey it now — the finish was read
        # three lines above the game key until 2026-08-23 and was checked against Pokemon's
        # enum whatever game the sidecar named. See `_check_variant`.
        raw_variant = _first(payload, _VARIANT_KEYS)
        metadata_finish, variant_problem = _check_variant(raw_variant, game)
        if variant_problem:
            problems.append(variant_problem)
        raw_claim = _first(payload, _RARITY_CLAIM_KEYS)
        rarity_claim, claim_problem = _check_rarity_claim(raw_claim, game)
        if claim_problem:
            problems.append(claim_problem)
        raw_note = _first(payload, _NOTE_KEYS)
        # No enum to check it against — it is prose. Trimmed to nothing is nothing.
        note = str(raw_note).strip() or None if raw_note is not None else None

    # `--variant` fills a gap; it never replaces a recorded toggle. The `is None` test is
    # the whole guarantee, so it is one line and it is here rather than at the call site.
    variant_from_flag = False
    if metadata_finish is None and variant_default is not None:
        metadata_finish, flag_problem = _check_variant(variant_default, game)
        variant_from_flag = metadata_finish is not None
        if flag_problem:
            problems.append(flag_problem)

    file_box, file_index = position_from_path(photo, root=root)

    resolved_box = sidecar_box if sidecar_box is not None else (file_box or box)
    resolved_index = sidecar_index if sidecar_index is not None else file_index

    if sidecar_box is not None or sidecar_index is not None:
        source = FROM_SIDECAR
    elif resolved_box is not None and resolved_index is not None:
        source = FROM_FILENAME
        problems.append("position recovered from the filename")
    else:
        source = FROM_NOWHERE

    if resolved_box is None or resolved_index is None:
        resolved_box = resolved_index = None
        problems.append("no position recoverable")

    return Capture(
        photo=photo,
        sidecar=sidecar_path,
        box=resolved_box,
        index=resolved_index,
        set_hint=set_hint,
        metadata_finish=metadata_finish,
        game=game,
        rarity_claim=rarity_claim,
        note=note,
        source=source if resolved_box is not None else FROM_NOWHERE,
        problem="; ".join(problems) if problems else None,
        variant_from_flag=variant_from_flag,
    )


def scan(
    directory,
    box: Optional[int] = None,
    variant_default: Optional[str] = None,
) -> List[Capture]:
    """Every photo under `directory`, in filename order. Sidecars are found beside them."""
    root = Path(directory)
    if not root.is_dir():
        raise FileNotFoundError(f"capture directory not found: {root}")
    photos = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in PHOTO_SUFFIXES
    )
    return [
        load(photo, root=root, box=box, variant_default=variant_default)
        for photo in photos
    ]
