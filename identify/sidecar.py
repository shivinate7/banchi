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
from typing import List, Optional, Sequence

from pipeline import variant

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


@dataclass(frozen=True)
class Capture:
    """One photograph, and everything the pipeline knows about it before identification."""

    photo: Path
    sidecar: Optional[Path] = None
    box: Optional[int] = None
    index: Optional[int] = None
    set_hint: Optional[str] = None
    metadata_finish: Optional[str] = None
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


def _check_variant(value) -> Optional[str]:
    """A finish outside the enum is a problem to report, never a value to coerce."""
    if value is None:
        return None
    text = str(value).strip().lower()
    return text if text in variant.FINISHES else None


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
    set_hint = metadata_finish = None
    if payload is not None:
        sidecar_box = _as_int(_first(payload, _BOX_KEYS))
        sidecar_index = _as_int(_first(payload, _INDEX_KEYS))
        raw_hint = _first(payload, _HINT_KEYS)
        set_hint = str(raw_hint).strip() if raw_hint is not None else None
        raw_variant = _first(payload, _VARIANT_KEYS)
        metadata_finish = _check_variant(raw_variant)
        if raw_variant is not None and metadata_finish is None:
            problems.append(f"variant {raw_variant!r} is outside {variant.FINISHES}")

    # `--variant` fills a gap; it never replaces a recorded toggle. The `is None` test is
    # the whole guarantee, so it is one line and it is here rather than at the call site.
    variant_from_flag = False
    if metadata_finish is None and variant_default is not None:
        metadata_finish = _check_variant(variant_default)
        variant_from_flag = metadata_finish is not None

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
