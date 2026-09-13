#!/usr/bin/env python3
"""Fill the pokemontcg.io image mirror (D15, build-order step 9, piece 3).

Manifest-driven, resumable, rate-limited. The manifest is derived from the vendored catalog
(`vendor/pokemon-tcg-data/cards/en/*.json`) — no network call is needed to build it, only to
fill what it names. Every row is one card's HIRES image (`images.large` in the source JSON,
D15's own `IMAGE_SIZE = "large"` choice, matched to `harness/eval/fixtures.py`'s), because the
834 KB/image measurement D15 cites and the ~16.7 GB extrapolation both name the hires size —
mirroring the small size too would be a second, unmeasured number.

Destination is `PKMNSCAN_IMAGE_MIRROR` (read through `envfile`, exactly as
`harness/eval/fixtures.py` reads it — same knob, same reason: a mirror path is a fact about
one machine's disk, D15 argues for a knob because of the mirror's size, and a real environment
variable still wins over a stored default). Unset, it defaults to `harness/images/` — D15's
own instruction to move that directory's role here rather than leave a second copy standing.

RESUMABLE: a destination file that already exists and is non-empty is skipped without a
request, which is the whole of what makes an interrupted run cheap to continue. A STATE FILE
(`<dest>/.mirror-state.json`) records, per card id, the last HTTP status and byte count seen,
so a `--dry-run` (or a real fill) can report progress across runs without re-deriving it.

RATE-LIMITED: `MIN_INTERVAL_S` between requests, sleeping rather than bursting — this host,
`images.pokemontcg.io`, is the one piece of the catalog D15 says is "most likely to throttle
or disappear", so the downloader is the one piece of this step built to survive that.

    python3 scripts/catalog-image-mirror.py --dry-run
        HEAD-samples up to 200 images (rate-limited), prints the manifest's file count and
        the byte total extrapolated from the sample's average Content-Length. WRITES NOTHING
        under the mirror destination — the manifest itself is written next to the vendored
        snapshot, which is not the destination.

    python3 scripts/catalog-image-mirror.py
        Fills the mirror for real. NOT RUN BY THIS STEP — see the decision entry for why: the
        dry run's own extrapolation is large enough (~16.7 GB) that filling it is the owner's
        call, on their own disk, not a default a `make` target reaches for silently.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import envfile  # noqa: E402

VENDOR_DIR = ROOT / "vendor" / "pokemon-tcg-data"
MANIFEST_PATH = VENDOR_DIR / "image-manifest.json"
USER_AGENT = "pkmnscan-catalog-image-mirror/1.0 (+build-order step 9, piece 3)"
HTTP_TIMEOUT = 20
MIN_INTERVAL_S = 0.25  # rate limit: ~4 req/s, gentle on a CDN that is the one piece of this catalog not vendored
DRY_RUN_SAMPLE_CAP = 200


def mirror_dir() -> Path:
    """Where the mirror lives — the same knob and the same default `harness/eval/fixtures.py`
    reads (D15): `PKMNSCAN_IMAGE_MIRROR` if set, else `harness/images/`."""
    raw = envfile.get("PKMNSCAN_IMAGE_MIRROR")
    if raw:
        return Path(os.path.expandvars(os.path.expanduser(raw)))
    return ROOT / "harness" / "images"


def build_manifest() -> List[Dict[str, str]]:
    """One row per card's hires image, read from the vendored snapshot. No network."""
    cards_dir = VENDOR_DIR / "cards" / "en"
    rows: List[Dict[str, str]] = []
    for path in sorted(cards_dir.glob("*.json")):
        set_id = path.stem
        cards = json.loads(path.read_text(encoding="utf-8"))
        for c in cards:
            images = c.get("images") or {}
            url = images.get("large")
            if not url:
                continue
            card_id = c.get("id")
            ext = url.rsplit(".", 1)[-1]
            rows.append({
                "id": card_id,
                "set_id": set_id,
                "url": url,
                "dest": f"{card_id}.{ext}",
            })
    return rows


def write_manifest(rows: List[Dict[str, str]]) -> None:
    MANIFEST_PATH.write_text(json.dumps({"count": len(rows), "rows": rows}, indent=2), encoding="utf-8")


def load_manifest() -> List[Dict[str, str]]:
    if not MANIFEST_PATH.exists():
        rows = build_manifest()
        write_manifest(rows)
        return rows
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return data["rows"]


def _head(url: str) -> Optional[int]:
    """Content-Length of `url`, or None on any failure. Never raises — a flaky sample point
    is dropped from the average rather than aborting the whole sample."""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            length = resp.headers.get("Content-Length")
            return int(length) if length is not None else None
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError):
        return None


def dry_run(rows: List[Dict[str, str]], sample_cap: int = DRY_RUN_SAMPLE_CAP) -> Dict[str, object]:
    """HEAD a rate-limited SAMPLE of the manifest and extrapolate the total. Writes nothing
    under the mirror destination — only reads over the network."""
    sample = rows[:: max(1, len(rows) // sample_cap)][:sample_cap] if rows else []
    sizes = []
    for i, row in enumerate(sample):
        if i:
            time.sleep(MIN_INTERVAL_S)
        size = _head(row["url"])
        if size is not None:
            sizes.append(size)

    if sizes:
        avg = sum(sizes) / len(sizes)
        extrapolated = avg * len(rows)
    else:
        avg = 0.0
        extrapolated = 0.0

    return {
        "manifest_files": len(rows),
        "sampled": len(sample),
        "sampled_ok": len(sizes),
        "avg_bytes": avg,
        "extrapolated_total_bytes": extrapolated,
        "extrapolated_total_gb": extrapolated / (1024 ** 3),
    }


def fill(rows: List[Dict[str, str]], dest: Path) -> Dict[str, int]:
    """Actually download. Resumable (skip a non-empty existing file), rate-limited."""
    dest.mkdir(parents=True, exist_ok=True)
    state_path = dest / ".mirror-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}

    skipped = downloaded = failed = 0
    for i, row in enumerate(rows):
        out = dest / row["dest"]
        if out.exists() and out.stat().st_size > 0:
            skipped += 1
            continue
        if i:
            time.sleep(MIN_INTERVAL_S)
        req = urllib.request.Request(row["url"], headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                data = resp.read()
            out.write_bytes(data)
            state[row["id"]] = {"status": 200, "bytes": len(data)}
            downloaded += 1
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            state[row["id"]] = {"status": getattr(exc, "code", None) or -1, "bytes": 0}
            failed += 1
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    return {"skipped": skipped, "downloaded": downloaded, "failed": failed}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sample-cap", type=int, default=DRY_RUN_SAMPLE_CAP)
    args = parser.parse_args(argv)

    rows = load_manifest()
    dest = mirror_dir()

    if args.dry_run:
        report = dry_run(rows, sample_cap=args.sample_cap)
        print(f"manifest: {report['manifest_files']} files")
        print(f"sampled: {report['sampled']} (of which {report['sampled_ok']} answered a HEAD)")
        print(f"average size: {report['avg_bytes']:.0f} bytes")
        print(
            f"extrapolated total: {report['extrapolated_total_bytes']:.0f} bytes "
            f"(~{report['extrapolated_total_gb']:.2f} GB)"
        )
        print(f"destination (not written): {dest}")
        print("--dry-run: nothing written under the mirror destination")
        return 0

    print(f"filling {dest} from {len(rows)} manifest rows...")
    stats = fill(rows, dest)
    print(f"skipped {stats['skipped']}, downloaded {stats['downloaded']}, failed {stats['failed']}")
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
