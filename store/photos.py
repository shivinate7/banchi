"""Where a card's photograph lives, and the only module permitted to compose that path.

THE PHOTOGRAPH IS STORED UNDER THE CARD'S NAME, NOT UNDER ITS ADDRESS. `docs/specs/
stable-card-id.md` §0 is the argument and `D-a-number-a-person-reads-is-never-a-key` is the
ruling; the one-sentence form is that `(box, index)` was doing three jobs at once — the
card's identity, the filename of its photograph, and the address a human reads off a shelf —
and filing the bytes under a number that moves is what made all three of D172 §7's structural
hazards possible.

    BEFORE   <home>/captures/cards/box3/0017.jpg      the address is the filename
    AFTER    <home>/photos/6b/6b1cf2fd…jpg            the card's own name is the filename

THREE PROPERTIES FOLLOW AND THE THIRD IS WHAT THE CHANGE IS WORTH:

  a renumber is a no-op        the photographs of the cards behind a deleted one are not
                              named after their indices, so there is nothing to rename.
                              Measured on the owner's box 2: 537 renames and 537 rewritten
                              sidecars, now 0
  a move is a field update     the path contains no box, so a card crossing drawers moves
                              no bytes
  a capture CANNOT overwrite   `cards_cid` holds the name UNIQUE and `path` is a pure
  another's photograph         function of it, so two cards cannot compose one path. D172
                              §7 item 3's overwrite of an irreplaceable photograph is
                              ABSENT rather than defended against, and its three open
                              questions are answered by there being no birth address at all

IT IS OUTSIDE `captures/`, AND THAT IS LOAD-BEARING RATHER THAN TIDY.
`server/pipeline_routes.py:_scopes_root` already argues this exact point for scope
directories: `identify.sidecar.scan` walks its root recursively and turns every
photo-suffixed file into a capture and therefore a PAID Batch request. A content-addressed
store under `captures/cards/` would be swept by any run pointed at the directory above it,
and every card in it would be submitted twice and billed twice. So this is a sibling of
`captures/`, `.scopes/`, `runs/` and `inventory/` — gitignored on `inventory/`'s reason
rather than a weaker one, because it holds the real photographs.

THE SHARD IS TWO HEX WIDE AND IT IS THE ONE NUMBER HERE THAT IS A GUESS. 256 buckets holds
2,535 photographs at ~10 per directory and 100,000 at ~390. Nothing measures the
alternative because nothing in this pipeline ever LISTS that directory: every read is a
direct open by name, and the one walk that exists (`survey`) is for reporting.

THE LEGACY ADDRESS IS READ UNTIL THE STORE SAYS THE MOVE IS DONE, AND NEVER AFTER.
`meta.photos_relocated` is the gate. `find` tries the card's name and then, only while the
gate is unset, the address it used to be filed under — so a resumable move of 4.45 GB can be
interrupted without any screen going dark, and the fallback cannot quietly become a
permanent second lookup. `make status` reports the residue for as long as one exists.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from store import files

# The content store's own root, and the two suffixes a card's pair is written under.
DIRNAME = "photos"
PHOTO_SUFFIX = ".jpg"
SIDECAR_SUFFIX = ".json"
SHARD = 2

# The legacy layout, kept as a derivation because `find` still reads it during the move and
# the relocation has to know where to look. `INDEX_PAD` is 4 for the reason
# `capture_server.photo_path` gives: `sidecar.scan` sorts by path string.
LEGACY_CAPTURES_DIRNAME = "captures"
LEGACY_CARDS_DIRNAME = "cards"
INDEX_PAD = 4

# THE FOUR SHAPES A `cid` COMES IN (D172), and the two of them that name a photograph.
# `<64 hex>` is a card named by the photograph the store held at issue; `<64 hex>-<n>` is the
# nth card whose bytes are identical to an earlier card's. `moved:<…>` is a D83 tombstone and
# `nophoto:<box>/<index>@<stamp>` is a card with no photograph and no digest anywhere — those
# two name no file and `path` refuses them rather than composing a name that cannot exist.
_PHOTO_CID_RE = re.compile(r"^(?P<digest>[0-9a-f]{64})(?:-(?P<n>[1-9][0-9]*))?$")
MOVED_PREFIX = "moved:"
NOPHOTO_PREFIX = "nophoto:"


class UnnamedPhotograph(ValueError):
    """A path was asked for a cid that names no photograph — a tombstone, or `nophoto:`."""


def is_photo_cid(cid: Optional[str]) -> bool:
    """Does this cid name a photograph? The one predicate that tells shapes 1 and 2 from 3
    and 4, and the one every caller should use instead of testing a prefix by hand.

    A NULL IS NEVER ONE OF THE FOUR AND IS NEVER A PHOTOGRAPH EITHER. D172 is explicit that
    a NULL here cannot distinguish "no photograph was found" from "this migration did not
    look", so it answers False and the caller's own report says which of the two it meant.
    """
    return bool(cid) and _PHOTO_CID_RE.match(cid) is not None


def digest_of(cid: Optional[str]) -> Optional[str]:
    """The 64 hex a photograph cid is built on, with any `-<n>` suffix stripped, or None.

    THE SUFFIX IS NOT PART OF THE DIGEST AND THE AUDIT DEPENDS ON THAT. Two cards holding
    byte-identical photographs get `X` and `X-2`; both files hash to `X`, so an audit
    comparing `sha256(file)` against the raw cid would report the second as a mismatch
    forever. That population is 0 today — 2,535 distinct digests, 0 duplicates — which is
    exactly why this has to be written down rather than discovered.
    """
    match = _PHOTO_CID_RE.match(cid or "")
    return match.group("digest") if match else None


def root(home: Optional[Path] = None) -> Path:
    """`<home>/photos`. Moves with `PKMNSCAN_HOME`, as the rest of the store does (D43)."""
    return (Path(home) if home is not None else files.home()) / DIRNAME


def path(cid: str, home: Optional[Path] = None) -> Path:
    """`<home>/photos/6b/6b1cf2fd….jpg` — a pure function of the card's name.

    Refuses a cid that names no photograph, rather than composing a path for a tombstone.
    That refusal is the reason two cards can never collide: the name is UNIQUE on `cards`
    and this is a function of it alone, so there is no second input to get wrong.
    """
    if not is_photo_cid(cid):
        raise UnnamedPhotograph(
            f"{cid!r} names no photograph. `moved:` and `nophoto:` cids are records of a "
            "card that has one somewhere else or none at all — ask `find` instead."
        )
    return root(home) / cid[:SHARD] / f"{cid}{PHOTO_SUFFIX}"


def sidecar_path(cid: str, home: Optional[Path] = None) -> Path:
    """The claims file beside the photograph, under the same name.

    IT TRAVELS WITH THE PHOTOGRAPH AND ITS `index` IS A HISTORICAL FACT, not an address. The
    index a capture claimed never changes; the index the card is AT is derived, and a run's
    view materializes it fresh (`server/pipeline_routes.py`). That split is what retires the
    537 sidecar rewrites a renumber used to pay.
    """
    return path(cid, home).with_suffix(SIDECAR_SUFFIX)


def legacy_path(box, index, home: Optional[Path] = None) -> Path:
    """`<home>/captures/cards/box3/0017.jpg` — where photographs were filed before §0.

    Kept as a derivation and not as a compatibility shim: `find` reads it during the move,
    and the relocation has to know the name it is moving away from.
    """
    base = (Path(home) if home is not None else files.home())
    return (
        base / LEGACY_CAPTURES_DIRNAME / LEGACY_CARDS_DIRNAME / f"box{int(box)}"
        / f"{int(index):0{INDEX_PAD}d}{PHOTO_SUFFIX}"
    )


def legacy_box_dir(box, home: Optional[Path] = None) -> Path:
    base = (Path(home) if home is not None else files.home())
    return base / LEGACY_CAPTURES_DIRNAME / LEGACY_CARDS_DIRNAME / f"box{int(box)}"


def find(
    cid: Optional[str],
    box=None,
    index=None,
    *,
    relocated: bool = False,
    home: Optional[Path] = None,
) -> Optional[Path]:
    """The photograph's path on disk, or None where there is no file at either name.

    THE CARD'S NAME FIRST, THE OLD ADDRESS SECOND, AND THE SECOND ONE IS GATED. `relocated`
    is `meta.photos_relocated`, and once it is set the legacy address is never consulted —
    so the fallback is a migration window rather than a permanent second lookup, and an
    unfinished move shows up as a counted residue instead of as a lookup that quietly
    always works.

    A cid naming no photograph still gets the legacy branch, because that is exactly the
    card whose bytes may be sitting at its old address: a `nophoto:` name was issued when
    nothing could be found, and a later reading may find something.
    """
    if is_photo_cid(cid):
        candidate = path(cid, home)
        if candidate.is_file():
            return candidate
    if not relocated and box is not None and index is not None:
        legacy = legacy_path(box, index, home)
        if legacy.is_file():
            return legacy
    return None


def find_sidecar(
    cid: Optional[str],
    box=None,
    index=None,
    *,
    relocated: bool = False,
    home: Optional[Path] = None,
) -> Optional[Path]:
    """`find` for the claims file. Same gate, same order."""
    if is_photo_cid(cid):
        candidate = sidecar_path(cid, home)
        if candidate.is_file():
            return candidate
    if not relocated and box is not None and index is not None:
        legacy = legacy_path(box, index, home).with_suffix(SIDECAR_SUFFIX)
        if legacy.is_file():
            return legacy
    return None


def sha256_of(target: Path) -> str:
    """The digest of a file on disk, read in chunks.

    CHUNKED RATHER THAN `read_bytes()` BECAUSE THE CORPUS IS 4.45 GB AND THIS RUNS OVER ALL
    OF IT. A whole-file read per photograph peaks at ~1.9 MB, which is nothing; the reason
    is the relocation's verify step, which hashes every destination immediately after
    linking it and would otherwise hold a second copy of each photograph in memory while
    the page cache still holds the first.
    """
    digest = hashlib.sha256()
    with open(target, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_of_bytes(blob: bytes) -> str:
    """The digest of bytes already in RAM — what the shutter and the re-shoot both use.

    `do_capture` has the decoded blob in memory before it takes the store lock, so a card's
    name costs ZERO extra I/O at the moment it is born. That is the whole reason the shutter
    can never reach the refusal in `record_capture`.
    """
    return hashlib.sha256(blob).hexdigest()


# ------------------------------------------------------------------- writing and moving


def write(cid: str, blob: bytes, home: Optional[Path] = None) -> Path:
    """Put a photograph at its card's name and return the path.

    NO EXISTENCE CHECK, AND NONE IS NEEDED — which is the difference between this and the
    hazard it replaces. `files.write_atomic` does no existence check either, and under the
    old layout that was how one remove followed by one capture could compose a path a live
    card's photograph still occupied. Here a name collision would require two cards to hold
    one `cid`, which `cards_cid` refuses. Writing the same name twice means writing the same
    card twice, and the bytes are the same bytes.
    """
    target = path(cid, home)
    target.parent.mkdir(parents=True, exist_ok=True)
    files.write_atomic(target, blob)
    return target


def write_sidecar(cid: str, payload: dict, home: Optional[Path] = None) -> Path:
    target = sidecar_path(cid, home)
    target.parent.mkdir(parents=True, exist_ok=True)
    files.write_json(target, payload)
    return target


def unlink(target: Optional[Path]) -> bool:
    """Remove a file, tolerating its absence. True when something was actually removed."""
    if target is None:
        return False
    try:
        target.unlink()
        return True
    except FileNotFoundError:
        return False


def adopt(source: Path, cid: str, home: Optional[Path] = None) -> str:
    """Move ONE photograph from wherever it is to its card's name, verified, resumably.

    Returns one of `already`, `moved`, or raises. The verdict is a word rather than a bool
    because the caller reports a census and "nothing needed doing" must never be spelled the
    same way as "work was done" — `docs/specs/stable-card-id.md` §6 is that rule and PR A's
    arm 9 is where this repo learned it.

    A HARD LINK, THEN A RE-HASH, THEN THE UNLINK — AND THE ORDER IS THE WHOLE ARGUMENT.
    A rename is atomic and cheaper to reason about, and it is also the one form where the
    verification happens AFTER the only other copy is gone. Between the link and the unlink
    there are two names for one inode and no second copy of the bytes, and the digest is
    re-read from the NEW name before the old one is dropped. Killed anywhere in that window
    the bytes exist under at least one name, and a re-run resolves it: the destination is
    already correct, so the leftover source is simply removed. There is no state this can
    stop in that a re-run does not finish, and none in which a photograph exists under no
    name at all — which is the property that matters, because the corpus cannot be re-taken.

    IT REFUSES RATHER THAN MOVING A FILE THAT IS NOT THE CARD'S. A source whose bytes do not
    hash to the card's name is the one genuinely wrong case, and filing it under that name
    would make the store agree with itself about something false. It stays where it is.
    """
    target = path(cid, home)
    want = digest_of(cid)
    if target.is_file():
        if sha256_of(target) == want:
            # The destination is already this card's photograph. A leftover source is the
            # footprint of an interrupted run and is removed, which is step 5 finishing.
            if source.is_file() and not source.samefile(target):
                unlink(source)
            return "already"
        raise files.StoreError(
            f"{target} exists and does not hash to {cid}. Refusing to overwrite a "
            "photograph that cannot be re-taken; nothing was moved."
        )
    found = sha256_of(source)
    if found != want:
        raise files.StoreError(
            f"{source} hashes to {found} and the card is named {cid}. Refusing to file it "
            "under a name it does not have; nothing was moved."
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError:
        # A cross-device store, or a filesystem with no hard links. Copy, then verify, then
        # unlink — the same three steps with the same ordering, paying the bytes.
        files.write_atomic(target, source.read_bytes())
    if sha256_of(target) != want:
        unlink(target)
        raise files.StoreError(
            f"{target} did not hash to {cid} after the link. The source is untouched."
        )
    unlink(source)
    return "moved"


def adopt_sidecar(source: Path, cid: str, home: Optional[Path] = None) -> str:
    """`adopt` for the claims file, and deliberately WITHOUT the digest check.

    A sidecar has no recorded digest to check against — it is a few hundred bytes of the
    operator's own claims, rewritten in place by three routes over the life of a card. So it
    is linked and unlinked without an oracle, and a failure here is reported and never
    fatal: `identify.sidecar.scan` keys on the PHOTOGRAPH, so a missing sidecar costs the
    recovery path in that module's own docstring — the position comes from the filename —
    and never a card.
    """
    target = sidecar_path(cid, home)
    if target.is_file():
        if source.is_file() and not source.samefile(target):
            unlink(source)
        return "already"
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError:
        files.write_atomic(target, source.read_bytes())
    unlink(source)
    return "moved"


# ------------------------------------------------------------------------- reporting


def survey(home: Optional[Path] = None) -> Tuple[int, int]:
    """`(photographs, bytes)` in the content store. The one walk in this module.

    For `make status` and the audit's summary line, never for a lookup.
    """
    base = root(home)
    if not base.is_dir():
        return 0, 0
    count = total = 0
    for shard in base.iterdir():
        if not shard.is_dir():
            continue
        for entry in shard.iterdir():
            if entry.suffix == PHOTO_SUFFIX and entry.is_file():
                count += 1
                total += entry.stat().st_size
    return count, total


def stored_names(home: Optional[Path] = None) -> List[str]:
    """Every photograph's name in the content store, from the filenames alone.

    FREE, BECAUSE THE FILENAME IS THE NAME. Under the old layout the equivalent map cost a
    full read of every photograph — `cli/resolve.py:_photo_digests` measured box 2's 543
    files at 997 MB and 0.56 s. Here it is a directory walk, and it is what finds a
    photograph that no card claims.
    """
    base = root(home)
    if not base.is_dir():
        return []
    out: List[str] = []
    for shard in sorted(base.iterdir()):
        if not shard.is_dir():
            continue
        for entry in sorted(shard.iterdir()):
            if entry.suffix == PHOTO_SUFFIX and entry.is_file():
                out.append(entry.stem)
    return out
