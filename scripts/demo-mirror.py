#!/usr/bin/env python3
"""Build the public demo as a mirror of the owner's real store, with every person scrubbed.

THE OWNER'S RULING (2026-09-26, D295): "full mirror is fine", with the photograph
payload capped "to just 512mb", and "all names be Jane Doe and all addresses be 123 Demo Way".
Names are numbered, "Jane Doe N", because `#/orders` groups by buyer. So this replaces the
invented store (`demo-seed.py`) as what the published page shows. docs/specs/demo.md §13.

THE OWNER'S STORE NEVER LEAVES THIS MAC. The input is a `.backup` copy under `demo-mirror/`,
which is gitignored. What is committed is only this script's scrubbed OUTPUT, under
`demo-assets/mirror/`: the recorded bundle and the QR-cleared photographs. CI cannot read the
owner's Mac, so it installs that committed output and builds the page (`--install`).

    python3 scripts/demo-mirror.py --source ~/Developer/pkmnscan   # snapshot, then build
    python3 scripts/demo-mirror.py                                  # build from the snapshot
    python3 scripts/demo-mirror.py --install                        # CI: committed -> app/

THE SCRUB IS BY CONSTRUCTION, NOT BY SEARCH. The order ledger holds one fact about a person,
the buyer's display name (`store/orders.py:OrderRecord.buyer`, D193). Every one is overwritten.
The store holds no address, email or phone. The one file with addresses is TCGplayer's
shipping export, which is not in the store at all, so this script WRITES one for the mirror's
open orders, with every street "123 Demo Way" and every city, state and zip blank. One plain
assert over the finished bundle and that file is the only check (the owner's ruling).

NOTHING HERE CONTACTS A NETWORK OR SPENDS MONEY. The recorder runs its server `--offline`.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import importlib.util
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

SNAPSHOT = REPO_ROOT / "demo-mirror"          # gitignored: the owner's real data
OUT = REPO_ROOT / "demo-assets" / "mirror"    # tracked: the scrubbed output only
APP_BUNDLE = REPO_ROOT / "app" / "demo" / "bundle.json"
APP_PHOTOS = REPO_ROOT / "app" / "public" / "demo" / "photos"

# The owner's cap on the published photographs, in bytes.
PHOTO_BUDGET = 512 * 1024 * 1024

NAME = "Jane Doe %d"
NAME_RE = re.compile(r"^Jane Doe \d+$")
ADDRESS = "123 Demo Way"
# The wire keys that carry a street. None exists on the wire today (`types.ts`), so the
# assert below is also what fails if one is ever added unscrubbed.
ADDRESS_KEYS = {"address", "address1", "address2", "street"}

# The side files a store keeps beside `store.sqlite`, copied whole. Each is catalogue or
# listing data (TCGplayer's public columns) or the owner's own prices; none names a person.
SIDE_FILES = ("prices.json",)
SIDE_DIRS = (".exports", ".live")

# `cli/cmd_pricearchive.py`'s own cache directory, `inventory/.market-cache` — the freshest,
# most complete tcgcsv cache on the owner's Mac, since the archive sweep runs often. Copied
# to `.cache/market` at the HOME ROOT (`server/pipeline_routes.py:market_cache_dir()`,
# D301), which is where `STOCK_IMAGES`' own `Market` looks — the same
# directory `scripts/demo-record.py:warm_history_cache` already treats as the demo home's
# one Market cache, for price histories.
# Copying it is what lets the offline recorder answer Riftbound/One Piece `image_url` at
# all, with no network call (D295 stays true: nothing here fetches, this only copies what
# the owner's own `archive sweep` already fetched).
MARKET_CACHE_SOURCE = "inventory/.market-cache"
MARKET_CACHE_DEST = ".cache/market"


# ------------------------------------------------------------------------------ snapshot


def snapshot(source: Path) -> None:
    """Copy the owner's store into `demo-mirror/`, reading it and writing nothing to it.

    `sqlite3`'s own backup, over a READ-ONLY open (`mode=ro`), the same as the shell's
    `.backup`: a consistent copy of a live WAL database, which a plain file copy is not.
    """
    live = source / "inventory" / "store.sqlite"
    if not live.is_file():
        raise SystemExit("no store at %s" % live)
    if SNAPSHOT.exists():
        shutil.rmtree(SNAPSHOT)
    (SNAPSHOT / "inventory").mkdir(parents=True)
    reader = sqlite3.connect("file:%s?mode=ro" % live, uri=True)
    writer = sqlite3.connect(str(SNAPSHOT / "inventory" / "store.sqlite"))
    with writer:
        reader.backup(writer)
    reader.close()
    writer.close()
    for name in SIDE_FILES:
        if (source / "inventory" / name).is_file():
            shutil.copyfile(source / "inventory" / name, SNAPSHOT / "inventory" / name)
    for name in SIDE_DIRS:
        if (source / "inventory" / name).is_dir():
            shutil.copytree(source / "inventory" / name, SNAPSHOT / "inventory" / name)
    if (source / MARKET_CACHE_SOURCE).is_dir():
        shutil.copytree(source / MARKET_CACHE_SOURCE, SNAPSHOT / MARKET_CACHE_DEST)
    if (source / "runs").is_dir():
        shutil.copytree(
            source / "runs", SNAPSHOT / "runs", ignore=shutil.ignore_patterns("*.pid"),
        )
    (SNAPSHOT / "SOURCE").write_text(str(source.resolve()) + "\n")
    print("snapshot  %s -> %s" % (live, SNAPSHOT.relative_to(REPO_ROOT)))


# ---------------------------------------------------------------------------- the people


def jane_does(orders) -> Dict[str, str]:
    """Every distinct buyer -> "Jane Doe N", N by the buyer's first order, oldest first.

    Stable across rebuilds for every buyer already seen: a later order only ever adds a
    higher N. Ties break on the order key, so the numbering is a function of the ledger.
    """
    names: Dict[str, str] = {}
    for record in sorted(orders, key=lambda r: (r.placed_at or r.first_seen or "", r.key)):
        if record.buyer and record.buyer not in names:
            names[record.buyer] = NAME % (len(names) + 1)
    return names


def write_shipping_export(home: Path, orders) -> int:
    """TCGplayer's shipping export for the mirror's Ready to Ship orders, scrubbed.

    The real export is a list of home addresses and is never read. This one is written from
    the ledger: the order's number, date, item count and value are the mirror's own, and the
    person is "Jane Doe N" at "123 Demo Way". City, state and zip are blank.
    """
    header = [
        "Order #", "FirstName", "LastName", "Address1", "Address2", "City", "State",
        "PostalCode", "Country", "Order Date", "Product Weight", "Shipping Method",
        "Item Count", "Value Of Products", "Shipping Fee Paid", "Tracking #", "Carrier",
    ]
    rows = []
    for record in sorted(orders, key=lambda r: r.key):
        if record.status != "Ready to Ship":
            continue
        first, _, last = (record.buyer or NAME % 0).partition(" ")
        count = sum(max(0, int(line.quantity)) for line in record.lines)
        value = sum(
            (Decimal(str(line.unit_price or 0)) * int(line.quantity) for line in record.lines),
            Decimal("0"),
        )
        rows.append([
            record.number, first, last, ADDRESS, "", "", "", "", "US",
            (record.placed_at or "")[:10], "0.00", "Standard (7-10 days)",
            str(count), "%.2f" % value, "0.00", "", "",
        ])
    out = io.StringIO()
    writer = csv.writer(out, quoting=csv.QUOTE_ALL, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    (home / "shipping-export.csv").write_text(out.getvalue(), encoding="utf-8")
    return len(rows)


# ------------------------------------------------------------------------ the photographs


def _curator():
    """`demo-photos.py`, loaded by path (the hyphen blocks an import), for its QR check and crop."""
    spec = importlib.util.spec_from_file_location(
        "demo_photos_module", REPO_ROOT / "scripts" / "demo-photos.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def prepare_photo(job: Tuple[str, str, str]) -> Tuple[str, str, int]:
    """One photograph: QR-checked at FULL resolution, then cropped and written. In a worker.

    Returns `(key, verdict, bytes)`. `verdict` is "ok" or "qr". A QR photograph is never
    written, and its payload is never returned: a live code is a bearer instrument (D70).
    """
    key, source, target = job
    curator = _curator()
    if curator.carries_a_qr(Path(source)) is not None:
        return key, "qr", 0
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    curator.cropped(Path(source)).save(
        target, "JPEG", quality=curator.QUALITY, optimize=True,
    )
    return key, "ok", Path(target).stat().st_size


def build(home: Path, jobs: int) -> None:
    """The demo home, from the snapshot: the store copied and scrubbed, photographs cropped."""
    if not (SNAPSHOT / "inventory" / "store.sqlite").is_file():
        raise SystemExit(
            "no snapshot in %s. Run with --source <checkout> first."
            % SNAPSHOT.relative_to(REPO_ROOT)
        )
    source = Path((SNAPSHOT / "SOURCE").read_text().strip())
    if home.exists():
        shutil.rmtree(home)
    shutil.copytree(SNAPSHOT / "inventory", home / "inventory")
    if (SNAPSHOT / "runs").is_dir():
        shutil.copytree(SNAPSHOT / "runs", home / "runs")
    if (SNAPSHOT / MARKET_CACHE_DEST).is_dir():
        shutil.copytree(SNAPSHOT / MARKET_CACHE_DEST, home / MARKET_CACHE_DEST)

    os.environ["PKMNSCAN_HOME"] = str(home)
    from store import Store, photos

    with Store().write() as snap:
        names = jane_does(snap.ledger.orders.values())
        for record in snap.ledger.orders.values():
            record.buyer = names.get(record.buyer) if record.buyer else None
        shipped = write_shipping_export(home, snap.ledger.orders.values())

        # THE SELECTION RULE, under the 512 MB cap: cards still on hand first, then the rest,
        # each by (box, index). Every photograph is taken until the next would pass the cap.
        relocated = bool(getattr(snap.inventory, "photos_relocated", None))
        order = sorted(
            snap.inventory.cards.values(),
            key=lambda c: (c.state in ("sold", "retired", "moved"), int(c.box), int(c.index)),
        )
        work: List[Tuple[str, str, str]] = []
        for card in order:
            found: Optional[Path] = None
            if not card.photo_reclaimed_at and photos.is_photo_cid(card.cid):
                found = photos.find(
                    card.cid, card.box, card.index, relocated=relocated, home=source,
                )
            card.photo = None
            if found is not None:
                work.append((card.key, str(found), str(photos.path(card.cid, home))))

        results: Dict[str, Tuple[str, int]] = {}
        with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as pool:
            for key, verdict, size in pool.map(prepare_photo, work, chunksize=8):
                results[key] = (verdict, size)

        spent, kept, refused, over = 0, 0, [], 0
        for key, _source, target in work:
            verdict, size = results[key]
            card = snap.inventory.cards[key]
            if verdict == "qr":
                refused.append(key)
                continue
            if spent + size > PHOTO_BUDGET:
                over += 1
                Path(target).unlink()
                continue
            spent += size
            kept += 1
            card.photo = str(Path(target).relative_to(home))

    print("scrubbed  %d buyers -> Jane Doe 1..%d" % (len(names), len(names)))
    print("shipping  %d Ready to Ship order(s) at %s" % (shipped, ADDRESS))
    print("photos    %d kept, %.1f MB, %d over the cap, %d refused for a QR"
          % (kept, spent / 1048576.0, over, len(refused)))
    for key in refused:
        print("          QR refused: card %s (payload not printed)" % key)


# -------------------------------------------------------------------------- record + commit


def record(home: Path) -> None:
    """The ordinary recorder, over the mirror home, with its server offline."""
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "demo-record.py"),
         "--home", str(home), "--offline"],
        check=True,
    )


def drop_stale_positions(bundle: Path, home: Path) -> int:
    """A `positions` entry whose (box, index) no longer holds ANY card is dropped, in place.

    THE GAP THIS CLOSES. `server/pipeline_routes.py:_relabel_positions`'s own docstring says
    it plainly: a pricing run's `box`/`index` "travel exactly as stored" and are never
    re-bound — only the CAPTION is re-rendered. A run whose box was later fully emptied (or
    renumbered) still carries the old position, and `Pricing.tsx`/`Fulfillment.tsx` build an
    `<img src={photoUrl(box, index)}>` for it unconditionally. On a LIVE store this is a real,
    pre-existing gap `pkmnscan rescue` exists to close by hand — but nobody can run `rescue`
    against a frozen demo bundle, so a stale position here is a 404 a reviewer sees FOREVER.

    MEASURED, 2026-09-27: `2026-09-01-box5-01`'s pricing table names 98 positions in box 5,
    which the current store holds zero cards in at all (fully emptied since that run). One
    of them, box 5 index 88, is what a real demo build 404'd on.

    NEVER TOUCHES A LIVE STORE — this runs once, here, over the recorded bundle.json a demo
    build is about to publish, never over `server/pipeline_routes.py`'s own live response.
    """
    from store import Store  # imported late: needs PKMNSCAN_HOME, already set by build()

    existing = {
        (int(card.box), int(card.index)) for card in Store().read().inventory.cards.values()
    }
    payload = json.loads(bundle.read_text("utf-8"))
    dropped = 0

    def walk(value):
        nonlocal dropped
        if isinstance(value, dict):
            positions = value.get("positions")
            if isinstance(positions, list):
                kept = [
                    at for at in positions
                    if not (
                        isinstance(at, dict)
                        and isinstance(at.get("box"), int)
                        and isinstance(at.get("index"), int)
                    )
                    or (int(at["box"]), int(at["index"])) in existing
                ]
                dropped += len(positions) - len(kept)
                value["positions"] = kept
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    if dropped:
        bundle.write_text(json.dumps(payload), "utf-8")
    return dropped


def assert_scrubbed(bundle: Path, shipping: Path) -> None:
    """THE ONE CHECK: every name is "Jane Doe N" and every address is "123 Demo Way"."""
    bad: List[str] = []

    def walk(value) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                lowered = str(key).lower()
                if lowered in ("buyer", "buyername") and item is not None \
                        and not NAME_RE.match(str(item)):
                    bad.append("buyer")
                if lowered in ADDRESS_KEYS and item not in (None, "", ADDRESS):
                    bad.append(lowered)
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(json.loads(bundle.read_text()))
    with shipping.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if not NAME_RE.match("%s %s" % (row["FirstName"], row["LastName"])):
                bad.append("shipping name")
            if row["Address1"] != ADDRESS or row["Address2"]:
                bad.append("shipping address")
            if row["City"] or row["State"] or row["PostalCode"]:
                bad.append("shipping city/state/zip")
    # The values are never printed: a failure here may be a real person's name.
    assert not bad, "refusing: %d field(s) are not the scrubbed form: %s" % (
        len(bad), ", ".join(sorted(set(bad))))


# THE OWNER'S CHOICE, 2026-09-27: GitHub refuses a blob over 100 MB outright, and the
# recording's own `responses` map had already grown past that on its own (measured: 101.3 MB
# pretty-printed, 72.5 MB compact). `chunk_responses` splits it into files a plain `git push`
# accepts with real margin — never a fixed file COUNT, which would either waste chunks on a
# small demo or silently stop being enough once the store grows again. `app/src/demoServer.ts`
# reads every chunk back with `import.meta.glob`, which needs no manifest and no fixed count:
# it matches whatever files are on disk at build time.
CHUNK_BYTES = 40 * 1024 * 1024
BUNDLE_DIRNAME = "bundle"
APP_BUNDLE_DIR = APP_BUNDLE.parent / BUNDLE_DIRNAME


def chunk_bundle(bundle_path: Path, out_dir: Path) -> List[str]:
    """`bundle_path`'s `responses`, repacked as compact JSON files each under `CHUNK_BYTES`.

    `wire` rides in `chunk-0.json` only — the one field `demoServer.ts` also reads, and
    small enough that duplicating it into every chunk would buy nothing. `photos` and
    `routes` are the RECORDER's own report (this script's stdout already prints them) and
    are not shipped: no reader in `app/` names either key, and repeating a store-sized
    figure once per chunk would cost real bytes for a number the app never asks for.
    """
    data = json.loads(bundle_path.read_text("utf-8"))
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    chunks: List[Dict[str, object]] = [{}]
    sizes = [0]
    for key, value in data["responses"].items():
        size = len(json.dumps({key: value}, separators=(",", ":")))
        if sizes[-1] + size > CHUNK_BYTES and chunks[-1]:
            chunks.append({})
            sizes.append(0)
        chunks[-1][key] = value
        sizes[-1] += size
    names: List[str] = []
    for index, chunk in enumerate(chunks):
        payload: Dict[str, object] = {"responses": chunk}
        if index == 0:
            payload["wire"] = data.get("wire", "")
        name = "chunk-%d.json" % index
        (out_dir / name).write_text(json.dumps(payload, separators=(",", ":")), "utf-8")
        names.append(name)
    return names


def merge_chunks(chunk_dir: Path) -> Dict[str, object]:
    """The inverse of `chunk_bundle` — every chunk's `responses` folded into one dict, for
    the one reader that still wants a single file, `app/tests/demo-coverage.spec.ts`: it
    does not need to learn the chunked shape, only `app/src/demoServer.ts` does.
    """
    merged: Dict[str, object] = {"responses": {}, "wire": ""}
    for name in sorted(p.name for p in chunk_dir.glob("chunk-*.json")):
        chunk = json.loads((chunk_dir / name).read_text("utf-8"))
        merged["responses"].update(chunk.get("responses") or {})  # type: ignore[attr-defined]
        if chunk.get("wire"):
            merged["wire"] = chunk["wire"]
    return merged


def commit_output() -> None:
    """The recorder's output, into the one tracked place CI installs it from."""
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    names = chunk_bundle(APP_BUNDLE, OUT / BUNDLE_DIRNAME)
    shutil.copytree(APP_PHOTOS, OUT / "photos")
    total = sum(p.stat().st_size for p in (OUT / "photos").rglob("*.jpg"))
    if total > PHOTO_BUDGET:
        raise SystemExit("refusing: %.1f MB of photographs is over the 512 MB cap"
                         % (total / 1048576.0))
    bundle_bytes = sum((OUT / BUNDLE_DIRNAME / name).stat().st_size for name in names)
    print("committed-ready  %s  (bundle %d chunk(s), %.1f MB, photos %.1f MB)" % (
        OUT.relative_to(REPO_ROOT), len(names), bundle_bytes / 1048576.0,
        total / 1048576.0))


def install() -> None:
    """CI: the committed mirror, into where the build reads it. Reads no store."""
    chunk_dir = OUT / BUNDLE_DIRNAME
    if not chunk_dir.is_dir() or not any(chunk_dir.glob("chunk-*.json")):
        raise SystemExit("no committed mirror at %s" % OUT.relative_to(REPO_ROOT))
    APP_BUNDLE.parent.mkdir(parents=True, exist_ok=True)
    if APP_BUNDLE_DIR.exists():
        shutil.rmtree(APP_BUNDLE_DIR)
    shutil.copytree(chunk_dir, APP_BUNDLE_DIR)
    # RECONSTRUCTED, NEVER THE SOURCE OF TRUTH — `app/src/demoServer.ts` reads the chunks
    # directly (`import.meta.glob`). This single file exists only because
    # `app/tests/demo-coverage.spec.ts` already reads one path and does not need to learn
    # the chunked shape too.
    APP_BUNDLE.write_text(json.dumps(merge_chunks(chunk_dir)), "utf-8")
    if APP_PHOTOS.exists():
        shutil.rmtree(APP_PHOTOS)
    shutil.copytree(OUT / "photos", APP_PHOTOS)
    print("installed the committed mirror -> app/demo/, app/public/demo/photos/")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", help="a checkout whose store to snapshot first")
    parser.add_argument("--home", default=os.environ.get("DEMO_HOME", "demo"))
    parser.add_argument("--install", action="store_true", help="CI: install the committed output")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    args = parser.parse_args()
    if args.install:
        install()
        return 0
    if args.source:
        snapshot(Path(args.source).expanduser())
    home = (REPO_ROOT / args.home).resolve()
    build(home, args.jobs)
    record(home)
    dropped = drop_stale_positions(APP_BUNDLE, home)
    if dropped:
        print("positions %d stale (box, index) pair(s) dropped, no longer any card there"
              % dropped)
    assert_scrubbed(APP_BUNDLE, home / "shipping-export.csv")
    commit_output()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
