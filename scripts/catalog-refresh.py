#!/usr/bin/env python3
"""Refresh the vendored pokemontcg.io catalog snapshot (D15, build-order step 9, piece 1).

`vendor/pokemon-tcg-data/` is a committed copy of the maintainer's own
`PokemonTCG/pokemon-tcg-data` repository — `cards/en/*.json` (one file per set) and
`sets/en.json`, which is the only place `printedTotal` lives (D15's own argument for why a
snapshot is safe: this data is fixed the day a card is printed, so staleness has exactly one
form — a *new* set is missing — and that fails loudly rather than quietly).

`decks/` and the v1-conversion script are deliberately NOT vendored: nothing downstream of
this pipeline reads a decklist, and the join key this step exists to serve
(`pipeline.join.number_index_key`, applied to `cards[].number` and `sets[].printedTotal`)
touches only the two directories copied here. Narrower than the whole upstream tree on
purpose — see the decision entry this step wrote.

THIS TARGET WRITES, so it never gates a commit (D18) and runs only on the owner's word — it
is a `make catalog-refresh`, never a step inside `make check`. It shallow-clones upstream into
a throwaway directory, copies the two directories in, and records the upstream commit SHA in
`vendor/pokemon-tcg-data/SNAPSHOT.json` so a T1-shaped score (or, once built, a catalog-index
score) is attributable to a catalog revision, exactly as D15 asks.

    python3 scripts/catalog-refresh.py            # clone, diff, refresh, write SNAPSHOT.json
    python3 scripts/catalog-refresh.py --dry-run   # clone and report the diff, write nothing
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR_DIR = ROOT / "vendor" / "pokemon-tcg-data"
UPSTREAM_URL = "https://github.com/PokemonTCG/pokemon-tcg-data.git"
SNAPSHOT_FILE = VENDOR_DIR / "SNAPSHOT.json"

# What gets copied in, relative to the clone root. Nothing else in the upstream tree is
# read by anything downstream of this step.
COPY_ITEMS = [
    ("cards/en", "cards/en"),  # directory
    ("sets/en.json", "sets/en.json"),  # file
    ("README.md", "UPSTREAM-README.md"),  # file, renamed so it can't be mistaken for ours
]


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def clone_upstream(dest: Path) -> str:
    """Shallow-clone upstream into `dest`. Returns the commit SHA."""
    run(["git", "clone", "--depth", "1", "--quiet", UPSTREAM_URL, str(dest)])
    sha = run(["git", "-C", str(dest), "rev-parse", "HEAD"]).stdout.strip()
    return sha


def _iter_tracked_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path


def snapshot_manifest(root: Path):
    """{relative path: sha256} for every file under `root`, excluding SNAPSHOT.json itself."""
    out = {}
    for path in _iter_tracked_files(root):
        rel = path.relative_to(root).as_posix()
        if rel == "SNAPSHOT.json":
            continue
        out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def diff_manifests(before, after):
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(k for k in (set(before) & set(after)) if before[k] != after[k])
    return added, removed, changed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="clone and report the diff, write nothing")
    args = parser.parse_args(argv)

    before = snapshot_manifest(VENDOR_DIR) if VENDOR_DIR.exists() else {}

    with tempfile.TemporaryDirectory(prefix="pokemon-tcg-data-") as tmp:
        clone_dir = Path(tmp) / "clone"
        print(f"cloning {UPSTREAM_URL} (depth 1)...")
        sha = clone_upstream(clone_dir)
        print(f"upstream commit: {sha}")

        staging = Path(tmp) / "staging"
        staging.mkdir()
        for src_rel, dst_rel in COPY_ITEMS:
            src = clone_dir / src_rel
            dst = staging / dst_rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

        after = snapshot_manifest(staging)
        added, removed, changed = diff_manifests(before, after)

        print(f"files: {len(after)} ({len(added)} added, {len(removed)} removed, {len(changed)} changed)")
        for rel in added[:20]:
            print(f"  + {rel}")
        for rel in removed[:20]:
            print(f"  - {rel}")
        for rel in changed[:20]:
            print(f"  ~ {rel}")
        if len(added) > 20 or len(removed) > 20 or len(changed) > 20:
            print("  ... (truncated)")

        if args.dry_run:
            print("--dry-run: nothing written")
            return 0

        if VENDOR_DIR.exists():
            shutil.rmtree(VENDOR_DIR)
        VENDOR_DIR.mkdir(parents=True)
        for _src_rel, dst_rel in COPY_ITEMS:
            src = staging / dst_rel
            dst = VENDOR_DIR / dst_rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

        total_bytes = sum(p.stat().st_size for p in _iter_tracked_files(VENDOR_DIR))
        file_count = sum(1 for _ in _iter_tracked_files(VENDOR_DIR))
        snapshot = {
            "source": "https://github.com/PokemonTCG/pokemon-tcg-data",
            "commit": sha,
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "file_count": file_count,
            "total_bytes": total_bytes,
            "copied": [dst for _, dst in COPY_ITEMS],
        }
        SNAPSHOT_FILE.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {SNAPSHOT_FILE} — {file_count} files, {total_bytes} bytes, commit {sha}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
