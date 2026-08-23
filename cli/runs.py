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

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pipeline import games
from store import files

MANIFEST = "manifest.json"
IDENTIFICATIONS = "identifications.json"
DECISIONS = "decisions.json"
REPORT = "report.txt"
RECONCILE = "reconcile.txt"
IMPORT_LISTED = "import-listed.csv"
IMPORT_SUBTHRESHOLD = "import-subthreshold.csv"


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


def describe_source(path) -> Dict[str, Any]:
    """Path, mtime, age and sha256 of an input file. WARN ONLY — never a refusal.

    A stale export is a judgment call the operator can make for themselves, and a hard stop
    on a snapshot's age blocks a legitimate run for a reason that is already on the screen.
    """
    path = Path(path)
    stat = path.stat()
    modified = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
    return {
        "path": str(path),
        "mtime": modified.isoformat(timespec="seconds"),
        "age_days": (datetime.now(timezone.utc) - modified).days,
        "sha256": sha256_of(path),
        "bytes": stat.st_size,
    }


@dataclass
class Run:
    directory: Path
    manifest: Dict[str, Any] = field(default_factory=dict)

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

    def save(self) -> None:
        self.manifest["updated_at"] = datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        )
        files.write_json(self.manifest_path, self.manifest)

    def set(self, **values) -> None:
        """Update manifest fields and flush immediately.

        Flushed on every set rather than at the end, because the two things most worth
        having after a crash — the batch ids and the capture directory — are exactly the
        things a deferred write loses.
        """
        self.manifest.update(values)
        self.save()

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

    # --------------------------------------------------------------- run-local files

    def read_identifications(self) -> Dict[str, Any]:
        payload = files.read_json(self.path(IDENTIFICATIONS))
        if payload is None:
            raise RunError(
                f"{self.path(IDENTIFICATIONS)} does not exist — run `pkmnscan identify` first"
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
    run.save()
    return run


def open_run(path) -> Run:
    directory = Path(path)
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
