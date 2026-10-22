"""Run directories and `manifest.json`.

A run is an IMMUTABLE INPUT, not state. Everything that costs money or carries a decision —
the identification cache, the inventory, the standing queues — lives in the master store, so
deleting `runs/2026-08-03-box3-01/` costs nothing but the paperwork. That property is worth
defending: it is what makes it safe to re-run anything.

The manifest records what a run was, in enough detail to explain a result months later:
which capture directory, which export (path, mtime, sha256), which prompt, which flags,
which batch ids, what it cost. The batch ids are written BEFORE the first poll — see
`identify.batch.run_batch`'s `on_submit` — because an id you persist after the poll is an id
you do not have when the poll is the thing that died.
"""

from __future__ import annotations

import contextlib
import copy
import fcntl
import hashlib
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pipeline import games
from store import clock, files

MANIFEST = "manifest.json"
# The per-run flock a manifest write holds. Apart from any press's own lock (`match.lock`): this one guards one read-modify-write.
MANIFEST_LOCK = "manifest.lock"
IDENTIFICATIONS = "identifications.json"
DECISIONS = "decisions.json"
# A LEGACY ANSWER FILE, RETIRED (D86, amended 2026-09-02). `banchi prices adopt --write`
# folds a run's `decisions.json` into `inventory/prices.json` and then renames it to this, so
# the run keeps the bytes it was priced with and `join`/`emit` stop refusing on it. The
# suffix is what drops it out of `server/pipeline_routes.py:_DOWNLOADABLE`, whose pattern
# ends in `\.(csv|txt|json|log)$` — so it leaves the run panel's file list with no route
# change, which is the whole reason it is a suffix and not a directory.
DECISIONS_ADOPTED = DECISIONS + ".adopted"
REPORT = "report.txt"
# The per-SKU pricing table `join` writes beside the report (D86). Data rather than prose,
# because a screen reads it: `report.txt` is written for a person and cannot be parsed back
# without inventing a format nothing owns. `_DOWNLOADABLE` already matches `.json`, so it
# also appears in the run panel's file list with no route change.
PRICING = "pricing.json"
RECONCILE = "reconcile.txt"
IMPORT_LISTED = "import-listed.csv"
IMPORT_SUBTHRESHOLD = "import-subthreshold.csv"
# ONE FILE OVER A WHOLE SEND (D86). The owner's ask, in their words: *"i frankly want one
# export csv from the emit no per run nonsense and/or multi csvs"*. Written into the NEWEST run
# of the send rather than into a directory of its own, because `GET /pipeline/runs/<n>/file`
# already serves a run's artefacts and a new home would need a new route to be reachable at
# all — which `CLAUDE.md`'s route-is-not-a-feature rule would then make a second job.
#
# `--split-games` PUTS THE PER-GAME NAMES BACK, and that flag exists because one question here
# is genuinely unanswered: `import_listed_name` below has said since it was written that nobody
# has established whether Import to Staged accepts a file spanning two `Product Line`s, and
# `fixtures/staged-import-accepted.csv` proves it for one line only. The owner asked for one
# file and said they would test it. This is the one-flag way back if the portal refuses.
IMPORT_MERGED = "import.csv"


def import_merged_name(game: Optional[str] = None) -> str:
    """The merged import file, for a whole send. Suffixed only when games are kept apart."""
    return IMPORT_MERGED if game is None else f"import-{game}.csv"


def import_listed_name(game: str) -> str:
    """The listed import file for one game. One import file per game, never mixed.

    Nobody has established that TCGplayer's Import to Staged accepts a file spanning two
    `Product Line`s, and `fixtures/staged-import-accepted.csv` proves it for one line only
    — so each game gets its own file, which is correct under either answer. The default
    game keeps the un-suffixed name every earlier run wrote: its files stay byte-identical
    and stay found by anything that already knows the name.
    """
    return IMPORT_LISTED if game == games.DEFAULT_GAME else f"import-listed-{game}.csv"


def import_subthreshold_name(game: str) -> str:
    """The sub-threshold import file for one game. Same rule as `import_listed_name`."""
    return (
        IMPORT_SUBTHRESHOLD
        if game == games.DEFAULT_GAME
        else f"import-subthreshold-{game}.csv"
    )


def retire_decisions(directory: Path) -> Path:
    """Move a run's legacy `decisions.json` aside as `decisions.json.adopted`. Never overwrites.

    `os.replace`, so the bytes are the file's own and nothing is re-serialised. A run that has
    already been retired once — adopted, hand-restored, adopted again — gets `.adopted-2`,
    `-3` and so on rather than losing the earlier copy: the file is the record of what the run
    was priced with, and a migration that overwrote a record would be the data move nobody
    watched that `cli/cmd_prices.py` exists to avoid.
    """
    directory = Path(directory)
    source = directory / DECISIONS
    target = directory / DECISIONS_ADOPTED
    suffix = 1
    while target.exists():
        suffix += 1
        target = directory / f"{DECISIONS_ADOPTED}-{suffix}"
    os.replace(source, target)
    return target


class RunError(RuntimeError):
    """The run directory is missing or is not one."""


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _slug(text: str) -> str:
    kept = [c.lower() if c.isalnum() else "-" for c in str(text).strip()]
    slug = "".join(kept).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "run"


def sha256_of(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stale_runs(opened: List["Run"], overrides=None) -> Dict[str, date]:
    """`{run name: US Central day}` for each run whose prices come from an export older than today.

    THE PRICES A SEND USES ARE THE EXPORT'S (D166): `overrides` when `emit` was handed files,
    otherwise the files the run's join recorded. The day is the oldest file's own mtime, its
    fetch time. A file that is missing is left out: `emit` names it itself. A run that recorded
    no export is left out too, because `emit` refuses it.
    """
    today = clock.central_day(clock.now())
    out: Dict[str, date] = {}
    for run in opened:
        paths = [Path(p) for p in overrides] if overrides else list(run.exports_by_game.values())
        stamps = [path.stat().st_mtime for path in paths if path.is_file()]
        if stamps:
            day = clock.central_day(datetime.fromtimestamp(min(stamps), timezone.utc))
            if day < today:
                out[run.name] = day
    return out


def describe_source(path) -> Dict[str, Any]:
    """Path, mtime, age and sha256 of an input file. WARN ONLY — never a refusal.

    A stale export is a judgment call the operator can make for themselves, and a hard stop
    on a snapshot's age blocks a legitimate run for a reason that is already on the screen.

    `mtime` IS TO THE MILLISECOND, for `store/master.py:now`'s reason one register over: it
    is the time an export's `Total Quantity` was read, and `Listing.live_reading` weighs it
    against `live_as_of`, which `now()` stamps to the millisecond. Truncated to the second it
    read as OLDER than a store stamp taken earlier in the same second, so a file written
    right after a sale lost to the sale — a coin flip inside every second, and in a fixture
    a certainty. `datetime.fromisoformat` reads both forms, so every manifest on disk still
    parses.
    """
    path = Path(path)
    stat = path.stat()
    modified = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
    return {
        "path": str(path),
        "mtime": modified.isoformat(timespec="milliseconds"),
        "age_days": (datetime.now(timezone.utc) - modified).days,
        "sha256": sha256_of(path),
        "bytes": stat.st_size,
    }


def _merge(base: Any, new: Any, disk: Any) -> Any:
    """Three-way merge of one manifest value: what this caller changed (`base` -> `new`) laid over
    what another process wrote since (`disk`). A dict merges key by key and a list of scalars by
    member, so a key a peer added survives, and a member leaves only when this caller removed it.
    A scalar this caller changed wins. Anything else (a list of dicts) this caller wrote wins."""
    if isinstance(new, dict) and isinstance(disk, dict):
        base = base if isinstance(base, dict) else {}
        out = dict(disk)
        for key in new:
            if key not in base or new[key] != base[key]:
                out[key] = _merge(base.get(key), new[key], disk.get(key)) if key in disk else new[key]
        for key in base:
            if key not in new:
                out.pop(key, None)
        return out
    if isinstance(new, list) and isinstance(disk, list):
        try:
            base = base if isinstance(base, list) else []
            gone = {x for x in base if x not in new}
            have = set(disk)
            return [x for x in disk if x not in gone] + [x for x in new if x not in base and x not in have]
        except TypeError:  # an unhashable member: this caller's list stands
            return new
    return new


@dataclass
class Run:
    directory: Path
    manifest: Dict[str, Any] = field(default_factory=dict)
    # What the manifest held when this object last read or wrote the disk: `save` writes only the
    # fields that differ from it, so a stale copy cannot overwrite a field a peer changed.
    _base: Dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._base = copy.deepcopy(self.manifest)

    # ------------------------------------------------------------------------- paths

    def path(self, name: str) -> Path:
        return self.directory / name

    @property
    def name(self) -> str:
        return self.directory.name

    @property
    def manifest_path(self) -> Path:
        return self.path(MANIFEST)

    # ----------------------------------------------------------------------- manifest

    @contextlib.contextmanager
    def _locked(self):
        """THE ONE HOME of a manifest write's exclusion: a blocking flock on `manifest.lock`, held
        only for one read-modify-write. A process that dies releases it."""
        self.directory.mkdir(parents=True, exist_ok=True)
        with open(self.directory / MANIFEST_LOCK, "a+") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield

    def refresh(self) -> None:
        """Read the manifest again from the disk, dropping this object's unsaved edits."""
        disk = files.read_json(self.manifest_path, {}) or {}
        self.manifest.clear()
        self.manifest.update(disk)
        self._base = copy.deepcopy(disk)

    def save(self, *explicit: str) -> None:
        """Write this object's changes over the manifest as it stands on disk, under the lock.

        THE CAUSE OF A LOST FIELD WAS A WHOLE-DICT WRITE: a press holding an older copy saved it over
        a field the sweep worker had just written (`joined`, a card key). Now the disk is read again,
        only the fields that differ from `_base` (or are named in `explicit`) are laid over it
        (`_merge`), and the result is written atomically. A key leaves only when this caller removed it."""
        with self._locked():
            self._write(explicit)

    def _write(self, explicit) -> None:
        """The read-modify-write itself. The caller holds `_locked`."""
        disk = files.read_json(self.manifest_path, {}) or {}
        out = dict(disk)
        for key, value in self.manifest.items():
            if key in explicit or key not in self._base or value != self._base[key]:
                out[key] = _merge(self._base.get(key), value, disk[key]) if key in disk else value
        for key in self._base:
            if key not in self.manifest:
                out.pop(key, None)
        out["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        files.write_json(self.manifest_path, out)
        self.manifest.clear()
        self.manifest.update(out)
        self._base = copy.deepcopy(out)

    def set_unless_joined(self, **values) -> bool:
        """Compare-and-set under the manifest lock: write `values` with `joined=False` only if the
        disk's run is not `joined`. False, and nothing written, when a press joined it first."""
        with self._locked():
            if (files.read_json(self.manifest_path, {}) or {}).get("joined"):
                self.refresh()
                return False
            self.manifest.update(values, joined=False)
            self._write((*values, "joined"))
        return True

    def set(self, **values) -> None:
        """Update manifest fields and flush immediately.

        Flushed on every set rather than at the end, because the two things most worth
        having after a crash — the batch ids and the capture directory — are exactly the
        things a deferred write loses. The fields named here are written even where they equal
        this object's copy (a deliberate `joined=False`); the rest of the disk is kept.
        """
        self.manifest.update(values)
        self.save(*values)

    # ------------------------------------------------------------------ the emit record

    @property
    def emitted(self) -> dict:
        """What this run has written into import files, tolerantly.

        One reader, because the shape has grown: `2026-08-22-box1-03` predates `pushed_skus`
        and every run before an emit has no key at all. Callers that ask "has this emitted"
        must go through `emitted_skus` rather than testing this dict for truthiness — a
        record naming nothing is not an emit, and `reconcile` refuses on exactly that.
        """
        return dict(self.manifest.get("emitted") or {})

    @property
    def emitted_skus(self) -> List[str]:
        """Every SKU this run has ever sent, across all its emits. Empty means never."""
        record = self.emitted
        return list(record.get("listed") or []) + list(record.get("sub_threshold") or [])

    def record_emit(self, *, listed, sub_threshold, pushed: int) -> None:
        """Merge one emit's output into the record. D54: a re-emit ADDS; it never subtracts.

        `Run.set` writes the fields it names over the disk's manifest (`_merge`), so this
        record's own union is named, and here: a scalar a caller sets replaces, a list unions.

        THE UNION IS NOT TIDINESS; `reconcile` IS WHY. It passes these SKUs to
        `join.reconcile_import`, which reports BOTH directions — so after
        emit → import → re-emit → import, a record holding only the last delta puts every
        SKU from the first import into `rows_without_cards`, and reconcile prints "something
        else wrote it" about rows it wrote itself. The union is what makes the round trip
        mean anything across more than one emit.

        A SKU WITHHELD AFTER BEING EMITTED STAYS IN THE UNION, deliberately: it was sent, its
        copies are at `pushed`, and the staged export will carry it.

        `pushed` accumulates because it is a quantity of copies and quantities sum.
        `pushed_skus` is DERIVED from the lists rather than accumulated beside them, so it
        cannot come to disagree with them — D86 Part One's rule applied to this record.
        """
        record = self.emitted
        merged_listed = list(record.get("listed") or [])
        merged_listed += [s for s in listed if s not in merged_listed]
        merged_sub = list(record.get("sub_threshold") or [])
        merged_sub += [s for s in sub_threshold if s not in merged_sub]
        self.set(
            emitted={
                "listed": merged_listed,
                "sub_threshold": merged_sub,
                "pushed": int(record.get("pushed") or 0) + pushed,
                "pushed_skus": len(set(merged_listed) | set(merged_sub)),
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "emits": int(record.get("emits") or 0) + 1,
            }
        )

    def add_batch_id(self, batch_id: str) -> None:
        ids = list(self.manifest.get("batch_ids") or [])
        if batch_id not in ids:
            ids.append(batch_id)
        self.set(batch_ids=ids)

    @property
    def batch_ids(self) -> List[str]:
        return list(self.manifest.get("batch_ids") or [])

    @property
    def collected(self) -> bool:
        return bool(self.manifest.get("collected"))

    @property
    def created_at(self) -> Optional[str]:
        """When this run directory was made — the manifest's own stamp: UTC, to the second."""
        return self.manifest.get("created_at")

    @property
    def exports_by_game(self) -> Dict[str, Path]:
        """The exports this run last joined against, keyed by game.

        `exports` is the recorded shape: {game: source-dict}, one file per game. A run
        written before it existed carries the old scalar `export`, and that is READ as the
        default game's file — the backfill happens here, at the read, and is never written
        back: an old manifest is a record of what an old run was, and rewriting it to the
        new shape would forge a claim (`exports` says the game mapping was VERIFIED off the
        files' own `Product Line` cells) that the old join never made.
        """
        recorded = self.manifest.get("exports")
        if isinstance(recorded, dict):
            return {
                game: Path(source["path"])
                for game, source in recorded.items()
                if isinstance(source, dict) and source.get("path")
            }
        legacy = self.manifest.get("export") or {}
        if legacy.get("path"):
            return {games.DEFAULT_GAME: Path(legacy["path"])}
        return {}

    @property
    def export_path(self) -> Optional[Path]:
        """The default game's export — the only game a scalar-era caller can mean.

        Kept alongside `exports_by_game` because the scalar question is still a real one
        ("which file did this run price Pokemon against?") and because the old manifests
        that only answer this question are still on disk.
        """
        source = self.manifest.get("export") or {}
        if source.get("path"):
            return Path(source["path"])
        return self.exports_by_game.get(games.DEFAULT_GAME)

    @property
    def capture_dir(self) -> Optional[Path]:
        value = self.manifest.get("capture_dir")
        return Path(value) if value else None

    @property
    def submitted(self) -> Optional[List[str]]:
        """Every position key this run's identification payload names, if the manifest says.

        A CHEAP READ, WHICH IS THE WHOLE REASON THIS EXISTS: a manifest is a few hundred
        bytes and `identifications.json` can be megabytes, so a caller that only wants "which
        keys did this run cover" — `cli/cmd_identify.py:_run_keys_of`, answering `--run <name>`
        — no longer has to open the larger file to find out. `None` on a run written before
        `identify` started recording `submitted` (2026-09-12); a caller that needs the keys of
        such a run falls back to `read_identifications()`.
        """
        value = self.manifest.get("submitted")
        return list(value) if isinstance(value, list) else None

    # --------------------------------------------------------------- run-local files

    @property
    def store_backed(self) -> bool:
        """No frozen `identifications.json`, but a key selection: its cards live in the store."""
        keys = (self.manifest.get("selection") or {}).get("keys")
        return bool(keys) and not self.path(IDENTIFICATIONS).exists()

    def read_identifications(self) -> Dict[str, Any]:
        payload = files.read_json(self.path(IDENTIFICATIONS))
        keys = (self.manifest.get("selection") or {}).get("keys")
        if payload is None and keys:
            # A store-backed run (sweep, `join --keys`) holds no frozen copy: read the store's
            # CURRENT cards for its keys (D65). Lazy import: `cli.resolve` imports this module.
            from cli import resolve
            from store.session import Store

            return resolve.store_backed_payload(self, Store().read().inventory)
        if payload is None:
            raise RunError(
                f"{self.path(IDENTIFICATIONS)} does not exist — run `banchi identify` first"
            )
        return payload

    def write_identifications(self, payload: Dict[str, Any]) -> None:
        files.write_json(self.path(IDENTIFICATIONS), payload)

    def write_text(self, name: str, text: str) -> Path:
        target = self.path(name)
        files.write_atomic(target, text.encode("utf-8"))
        return target


def create(label: str, root: Optional[Path] = None) -> Run:
    """`runs/<YYYY-MM-DD>-<label>-<nn>`, with `nn` the next free ordinal for that day."""
    base = Path(root) if root else files.runs_dir()
    base.mkdir(parents=True, exist_ok=True)
    prefix = f"{_stamp()}-{_slug(label)}-"
    used = {
        entry.name[len(prefix) :]
        for entry in base.iterdir()
        if entry.is_dir() and entry.name.startswith(prefix)
    }
    ordinal = 1
    while f"{ordinal:02d}" in used:
        ordinal += 1
    directory = base / f"{prefix}{ordinal:02d}"
    directory.mkdir(parents=True)
    run = Run(directory=directory, manifest={"created_at": datetime.now(timezone.utc)
                                             .isoformat(timespec="seconds")})
    run._base = {}
    run.save()
    return run


def open_run(path) -> Run:
    directory = Path(path)
    if len(directory.parts) == 1 and not directory.is_dir():  # a bare run name
        directory = files.runs_dir() / directory
    if not directory.is_dir():
        raise RunError(f"not a run directory: {directory}")
    manifest = files.read_json(directory / MANIFEST)
    if manifest is None:
        raise RunError(f"{directory} has no {MANIFEST} — is it a run directory?")
    return Run(directory=directory, manifest=manifest)


def latest(root: Optional[Path] = None) -> Optional[Run]:
    base = Path(root) if root else files.runs_dir()
    if not base.is_dir():
        return None
    candidates = sorted(
        (d for d in base.iterdir() if d.is_dir() and (d / MANIFEST).is_file()),
        key=lambda d: d.name,
    )
    return open_run(candidates[-1]) if candidates else None
