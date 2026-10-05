"""The free reader: match a card's photograph to the stock photos of the cards it could be.

`docs/specs/identify-engine-pick.md` is the design and D2 carries the owner's ruling. The
engine is Marqo ecommerce-B's IMAGE tower, exported to ONNX and run on onnxruntime (the app's
one model runtime). A photograph and a stock photo are each one 768-number fingerprint, and the
nearest stock fingerprints are the candidates.

IT NEVER GUESSES. A card is ACCEPTED only when every rule below holds. Any other card is NOT
ACCEPTED: this module writes no identification for it. The caller sends it to a second look by
the paid read in the same press, and that answer goes to the review queue beside the matcher's
top pick (the owner's flow: the free reader first, the paid read only on the low-confidence
cards, a human last).

  accept rule     the margin M (best minus second cosine) is at least `MARGIN_MIN` AND the
                  floor S (best cosine) is at least `FLOOR_MIN`. Both were fit on the spike's
                  500 photographs. The margin floor is the owner's ruling (0.05: cards under it get the second
                  look). The held-out check (`scripts/match-heldout.py`) measured it at 0 wrong.
  look-alike      a printing with no stock image loses to its same-name twin (measured: 96 of
  guard           the wrong answers accepted in the absent-photo test were same-name siblings).
                  So a best answer that shares a card name with a no-image printing in the pool
                  is left unread, whatever M and S say.
  the pool        a hinted card matches against its hinted set. An unhinted card matches
                  against every non-promo set of its game in the index. A Pokemon card with no
                  hint is never read (D170: a Pokemon run names its sets), and no hint is
                  borrowed from a neighbour (D76: a hint is evidence about the card that
                  carries it). A card hinted into a promo set is never read: the owner's rule.

THE INDEX IS DERIVED DATA AND LIVES BESIDE THE STORE, NOT IN IT (`inventory/fingerprints.
sqlite`). It holds one vector per stock image and NO image byte: the bytes are read once, in
memory, and dropped (D301's one named exception). It is keyed by game, set and product id, and
it records the model file's sha256, so an index built by another model file is refused rather
than mixed. Wiping it loses nothing that cannot be rebuilt, which is why it needs no schema
step in the store of record (D88).

THE MODEL FILE IS A RELEASE ASSET WITH A PINNED SHA-256, downloaded only on the owner's
Prepare press (`download_model`, below). This module never fetches one on its own.

STDLIB ONLY AT IMPORT. numpy, Pillow and onnxruntime load inside the functions that need
them, so a process that imports this module to read `status()` or a constant (the capture
server, the preflight) pays for none of them.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import random
import re
import sqlite3
import threading
import time
from datetime import datetime, timezone
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Dict, Iterable, List, NamedTuple, Optional, Sequence, Set, Tuple

from store import files as store_files
from identify.matchconst import MODEL_BYTES, MODEL_FILENAME, MODEL_SHA256, SERVED_GAMES  # noqa: F401
from store.cache import ENGINE_MATCHER as ENGINE

# ------------------------------------------------------------------------ the rules

# THE ACCEPT RULE. One home. Fit on the spike's 500 photographs (margin alone filters almost
# nothing; with the floor, 0 wrong of 459 accepted, 91.8% accepted) and NOT yet confirmed on
# photographs the spike never saw.
MARGIN_MIN = 0.05
# THE SHARE OF CARDS THE READER DOES NOT ACCEPT, used for a quote that is not measured. The
# held-out check's 3,001 store photographs measured 37.5 percent at this margin, with a 95 percent
# upper bound of 39.2. The figure is rounded UP to 0.40 so an estimate never understates the
# second look's cost. The quote says "estimated" whenever it is used.
UNACCEPTED_SHARE = 0.40
# A dry run over more cards than this does not run the matcher. The request that asked for the
# quote waits for the dry run, the matcher costs 50 to 90 ms a card, and a long selection would
# hold a request slot for minutes. The press itself always counts for real, in its own child.
MEASURE_MAX = 200
FLOOR_MIN = 0.755
TOP_N = 3


# The reasons a card is left unread. Each is a stable code the run record and the screen read.
UNREAD_GAME = "game_not_served"
UNREAD_NO_INDEX = "no_index"
UNREAD_INDEX_STALE = "index_stale"
UNREAD_NO_HINT = "pokemon_needs_a_set"
UNREAD_HINT = "set_not_resolved"
UNREAD_PROMO = "promo_set"
UNREAD_PROMO_HELD = "promo_held"
UNREAD_NOT_INDEXED = "set_not_indexed"
UNREAD_NO_CARD = "no_card_found"
UNREAD_UNREADABLE = "photo_unreadable"
UNREAD_LOOKALIKE = "lookalike_guard"
UNREAD_MARGIN = "margin_too_small"
UNREAD_FLOOR = "match_too_weak"
# An ACCEPTED read's reason, not an unread one: the margin was thin between two printings of one
# card and the card's own rarity claim fit exactly one of them (`_settled_by_claim`).
ACCEPT_CLAIM = "printing_settled_by_claim"
# Three more accepts below the baseline rule, each measured on 2,953 paid-identified cards with 0
# new errors (docs/specs/identify-engine-pick.md, section 3). `_verdict` tries them in a fixed
# order: baseline, claim settles a printing, clear winner, battlefield. `_read_chunk` then tries
# the claim narrowing the field.
ACCEPT_CLEAR = "clear_winner"
ACCEPT_BATTLEFIELD = "battlefield_margin"
ACCEPT_NARROWED = "narrowed_by_claim"
# Rule 4: the guard did not hold the card only because the same-name printing is unreleased.
ACCEPT_UNRELEASED = "unreleased_twin"
# Rule 3: any card with a wide gap and a middling floor.
CLEAR_MARGIN_MIN = 0.08
CLEAR_FLOOR_MIN = 0.70
# Rule 2: a battlefield is printed sideways and scores low against its upright stock photo, so
# its floor is lower and its margin higher.
BATTLEFIELD_MARGIN_MIN = 0.10
BATTLEFIELD_FLOOR_MIN = 0.45
BATTLEFIELD_TYPE = "Battlefield"  # tcgcsv's `Card Type` cell

# ------------------------------------------------------------------------ the model file

# The IMAGE tower of Marqo ecommerce-B (92.9 M parameters), fp32. Exported by
# `scripts/export-matcher-model.py`, published as a release asset on shivinate7/banchi, and
# pinned here by size and SHA-256. A different file is a different model: the index refuses it.
MODEL_RELEASE_TAG = "matcher-model-1"
MODEL_URL = (
    "https://github.com/shivinate7/banchi/releases/download/"
    f"{MODEL_RELEASE_TAG}/{MODEL_FILENAME}"
)
DIM = 768
INPUT_SIZE = 224
# Marqo-B's own normalisation. Resize to 224 by 224 with a bicubic filter, scale to 0..1,
# subtract 0.5, divide by 0.5, channel axis first. The parity script proves this matches torch.
NORM_MEAN = 0.5
NORM_STD = 0.5


def model_path() -> Path:
    return store_files.inventory_dir() / "models" / MODEL_FILENAME


def index_path() -> Path:
    return store_files.inventory_dir() / "fingerprints.sqlite"


def progress_path() -> Path:
    """Where `pkmnscan match prepare` writes its progress, read by the runs sheet."""
    return store_files.inventory_dir() / "match-prepare.json"


def sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# THE VERDICT OF ONE HASH, keyed by what the file is on disk: path, size and modification time.
# `GET /pipeline/match` is polled every few seconds and the model is 372 MB, so hashing it on every
# call held a request slot for the whole read. A file replaced in place changes its size or its
# mtime, and the download renames a new file in, so a changed file is always hashed again.
_verdicts: Dict[Tuple[str, int, int], bool] = {}


def model_ready(path: Optional[Path] = None) -> bool:
    """True when the model file is on disk, the pinned size, and the pinned hash."""
    target = path or model_path()
    try:
        stat = target.stat()
        if stat.st_size != MODEL_BYTES:
            return False
        key = (str(target), stat.st_size, stat.st_mtime_ns)
        if key not in _verdicts:
            _verdicts.clear()  # one file matters at a time: the cache never grows
            _verdicts[key] = sha256_of_file(target) == MODEL_SHA256
        return _verdicts[key]
    except OSError:
        return False


# ------------------------------------------------------------------------ names

_PAREN = re.compile(r"\s*[\(\[].*?[\)\]]")


def card_name(name: str) -> str:
    """The card's name with any parenthesised variant suffix removed and typography folded,
    so "Vex, Gloomist" and "Vex, Gloomist (Alternate Art)" are one card for the guard."""
    from identify import prompt

    return prompt.normalize_name(_PAREN.sub("", name or ""))


def is_promo_set(set_name: str) -> bool:
    return "promo" in (set_name or "").lower()


ALL_GAMES = "*"


def held_promo_games() -> Set[str]:
    """The games in which the store holds a promo printing, by one query on `cards.set_name`.

    THE PROMO GUARD (spec section 2). Organized Play promos repeat main-set numbers, so a held
    promo could be matched to its main-set twin. For a game named here the pool is not complete:
    an unhinted card of that game is not accepted. A store that does not exist holds nothing. A
    store that cannot be read is treated as holding a promo in every game (`ALL_GAMES`), never as
    holding none. A card whose `set_name` was never filled in cannot be seen by this query."""
    from store import db

    try:
        conn = db.open_read_only(db.path(store_files.inventory_dir()))
    except FileNotFoundError:
        return set()
    except Exception:  # noqa: BLE001 - an unreadable store must not read as a clean one
        return {ALL_GAMES}
    try:
        rows = conn.execute(
            "select distinct coalesce(game, 'pokemon') from cards "
            "where lower(set_name) like '%promo%' and state not in ('sold', 'retired', 'moved')"
        ).fetchall()
        return {str(r[0]) for r in rows}
    except Exception:  # noqa: BLE001
        return {ALL_GAMES}
    finally:
        conn.close()


# ------------------------------------------------------------------------ the download


class ModelDownloadError(RuntimeError):
    """The model file could not be fetched or did not match its pin. The message is plain."""


def download_model(
    dest: Optional[Path] = None,
    url: str = MODEL_URL,
    *,
    progress: Callable[[int, int], None] = lambda _done, _total: None,
    opener: Callable[..., "object"] = urllib.request.urlopen,
) -> Path:
    """Fetch the pinned model file. ONLY ON THE OWNER'S PREPARE PRESS: nothing in this module
    calls it, and the CLI reaches it only through `match prepare`.

    The bytes go to a `.part` file, are checked against `MODEL_BYTES` and `MODEL_SHA256`, and
    only then renamed into place, so a half file or a wrong file is never the model. A failed
    check deletes the part and says so."""
    target = Path(dest) if dest is not None else model_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    digest = hashlib.sha256()
    done = 0
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "banchi-matcher-model/1"})
        with opener(request, timeout=60) as response, open(part, "wb") as handle:
            total = int(response.headers.get("Content-Length") or MODEL_BYTES)
            for block in iter(lambda: response.read(1 << 20), b""):
                handle.write(block)
                digest.update(block)
                done += len(block)
                progress(done, total)
            handle.flush()
            os.fsync(handle.fileno())
    except urllib.error.HTTPError as exc:
        part.unlink(missing_ok=True)
        raise ModelDownloadError(
            f"The model file could not be downloaded: the server answered {exc.code}. "
            "The release that holds it may not be published yet."
        ) from exc
    except Exception as exc:
        part.unlink(missing_ok=True)
        raise ModelDownloadError(f"The model file could not be downloaded: {type(exc).__name__}.") from exc
    if done != MODEL_BYTES or digest.hexdigest() != MODEL_SHA256:
        part.unlink(missing_ok=True)
        raise ModelDownloadError(
            "The downloaded file is not the model Banchi expects (wrong size or checksum), so it was thrown away."
        )
    os.replace(part, target)
    return target


# The fixed synthetic images the parity check embeds: structured enough to light every part of
# the graph, deterministic, and no photograph of a card.
PARITY_IMAGES = 50
PARITY_SEED = 20261003


def parity_images() -> List["object"]:
    import numpy as np
    from PIL import Image

    rng = np.random.RandomState(PARITY_SEED)
    out = []
    for n in range(PARITY_IMAGES):
        height, width = 300 + 7 * n, 210 + 5 * n
        y, x = np.mgrid[0:height, 0:width]
        frame = np.zeros((height, width, 3), np.float32)
        for channel in range(3):
            fx, fy, phase = rng.uniform(0.002, 0.04), rng.uniform(0.002, 0.04), rng.uniform(0, 6.28)
            frame[..., channel] = 127 + 120 * np.sin(fx * x + fy * y + phase)
        top, left = rng.randint(0, height // 2), rng.randint(0, width // 2)
        frame[top : top + height // 3, left : left + width // 3] = rng.uniform(0, 255, 3)
        frame += rng.normal(0, 6, frame.shape)
        out.append(Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8), "RGB"))
    return out


# ------------------------------------------------------------------------ the index

_SCHEMA = """
create table if not exists meta(k text primary key, v text);
create table if not exists vec(
  game text, set_name text, product_id text, number text, name text, url text,
  status text, note text, vec blob, at text,
  primary key(game, set_name, product_id));
create table if not exists sets(
  game text, set_name text, source text, set_id text,
  numbered int, unnumbered int, planned_at text,
  primary key(game, set_name));
"""

# A row's status. `ok` carries a vector. The others carry none, and every one of them is a
# printing the guard reads by NAME.
S_OK = "ok"
S_NO_URL = "no_url"  # the catalogue lists the product with no image URL
S_NO_PHOTO = "no_photo"  # the URL answers 403/404/410: CloudFront's answer for a missing file
S_UNREADABLE = "unreadable"  # a transient failure, retried on the next press
NO_IMAGE = (S_NO_URL, S_NO_PHOTO, S_UNREADABLE)


class IndexError_(RuntimeError):
    """The index cannot be used, and the message says why in the operator's terms."""


@dataclass
class Pool:
    """The fingerprints a card is matched against, and the names the guard blocks."""

    vectors: "object"  # numpy [n, DIM] float32
    rows: List[Tuple[str, str, str, str]]  # (game, set_name, product_id, number), parallel to vectors
    names: List[str]
    printed: List[str]
    blocked: Set[str]
    sets: Tuple[str, ...]
    # Each printing's catalogue `Rarity`, parallel to `rows`. None until a thin margin needs it;
    # `_pool_rarities` then reads it from `StockImages.catalog_products`, the one home, so the
    # fingerprint index stays as it is and no re-prepare is forced.
    rarities: Optional[List[str]] = None
    # Each printing's catalogue `Card Type`, parallel to `rows`, filled with `rarities` by the one read.
    card_types: Optional[List[str]] = None
    # Every no-photo printing the guard holds, `(set_name, product_id, name)`. `blocked` holds its names.
    blocked_rows: List[Tuple[str, str, str]] = field(default_factory=list)
    unreleased_names: Set[str] = field(default_factory=set)  # names of no-photo printings in unreleased sets
    cells: Optional[Dict[Tuple[str, str], Tuple[str, str]]] = None  # `{(set, product id): (rarity, card type)}`, read once


class Index:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path is not None else index_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), check_same_thread=False)
        self.db.executescript(_SCHEMA)
        self._lock = threading.Lock()

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> "Index":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def meta(self, key: str, value: Optional[str] = None) -> Optional[str]:
        with self._lock:
            if value is None:
                row = self.db.execute("select v from meta where k=?", (key,)).fetchone()
                return row[0] if row else None
            self.db.execute("insert or replace into meta values(?,?)", (key, value))
            self.db.commit()
            return value

    def set_names(self, game: str) -> List[str]:
        return [r[0] for r in self.db.execute("select set_name from sets where game=? order by set_name", (game,))]

    def pool(self, game: str, set_names: Sequence[str]) -> Pool:
        import numpy as np

        vectors: List["object"] = []
        rows: List[Tuple[str, str, str, str]] = []
        names: List[str] = []
        printed: List[str] = []
        blocked: Set[str] = set()
        blocked_rows: List[Tuple[str, str, str]] = []
        unreleased_names: Set[str] = set()
        unreleased: Optional[Set[str]] = None  # read once, and only when a no-photo row needs it
        for set_name in set_names:
            for pid, number, name, status, blob in self.db.execute(
                "select product_id, number, name, status, vec from vec where game=? and set_name=?",
                (game, set_name),
            ):
                if status == S_OK and blob:
                    vectors.append(np.frombuffer(blob, dtype=np.float32))
                    rows.append((game, set_name, pid, number))
                    names.append(name)
                    printed.append(self._printed(game, set_name))
                elif status in NO_IMAGE:
                    if unreleased is None:
                        unreleased = unreleased_sets(game)
                    if set_name in unreleased:  # an unreleased set has no photo yet, which is no look-alike
                        unreleased_names.add(card_name(name))
                    else:
                        blocked.add(card_name(name))
                        blocked_rows.append((set_name, pid, name))
        matrix = np.stack(vectors).astype(np.float32) if vectors else np.zeros((0, DIM), np.float32)
        return Pool(matrix, rows, names, printed, blocked, tuple(set_names),
                    blocked_rows=blocked_rows, unreleased_names=unreleased_names)

    _printed_cache: Dict[Tuple[str, str], str] = {}

    def _printed(self, game: str, set_name: str) -> str:
        key = (game, set_name)
        if key not in self._printed_cache:
            row = self.db.execute(
                "select v from meta where k=?", (f"printed:{game}:{set_name}",)
            ).fetchone()
            self._printed_cache[key] = row[0] if row else ""
        return self._printed_cache[key]

    def counts(self) -> Dict[str, int]:
        found = dict(self.db.execute("select status, count(*) from vec group by 1").fetchall())
        found["sets"] = self.db.execute("select count(*) from sets").fetchone()[0]
        return found


def status(index: Optional[Index] = None, model: Optional[Path] = None) -> Dict[str, object]:
    """What the screen and the preflight show, free and with no model loaded.

    `ready` is the one word the picker reads: the model file is the pinned one, an index exists,
    and the index was built by that same file."""
    target = model or model_path()
    present = target.exists()
    ok = model_ready(target) if present else False
    out: Dict[str, object] = {
        "model_present": present,
        "model_ok": ok,
        "model_bytes": MODEL_BYTES,
        "index_present": False,
        "index_current": False,
        "ready": False,
    }
    own = index
    path = index_path()
    if own is None and not path.exists():
        return out
    try:
        own = own or Index(path)
        counts = own.counts()
        out["index_present"] = counts.get(S_OK, 0) > 0
        out["index_current"] = own.meta("model_sha256") == MODEL_SHA256
        out["fingerprints"] = counts.get(S_OK, 0)
        out["no_image"] = sum(counts.get(s, 0) for s in NO_IMAGE)
        out["sets"] = counts.get("sets", 0)
        out["ready"] = bool(ok and out["index_present"] and out["index_current"])
    except sqlite3.DatabaseError:
        pass
    return out


# ------------------------------------------------------------------------ the embedder

_session_lock = threading.Lock()
_sessions: Dict[str, object] = {}


def _session(path: Path):
    key = str(path)
    with _session_lock:
        if key not in _sessions:
            import onnxruntime as ort

            options = ort.SessionOptions()
            options.intra_op_num_threads = 4
            _sessions[key] = ort.InferenceSession(key, options, providers=["CPUExecutionProvider"])
        return _sessions[key]


def preprocess(image):
    """One PIL image to the model's input: [3, 224, 224] float32. A landscape image (a
    battlefield card) is turned upright first, the rule the index applies to stock photos."""
    import numpy as np
    from PIL import Image

    rgb = image.convert("RGB")
    if rgb.width > rgb.height:
        rgb = rgb.rotate(90, expand=True)
    array = np.asarray(rgb.resize((INPUT_SIZE, INPUT_SIZE), Image.BICUBIC), np.float32) / 255.0
    return ((array - NORM_MEAN) / NORM_STD).transpose(2, 0, 1)


def embed(images: Sequence, path: Optional[Path] = None):
    """`[n, 768]` float32, each row unit length. The model's own graph ends in the L2 norm."""
    import numpy as np

    session = _session(path or model_path())
    batch = np.stack([preprocess(image) for image in images]).astype(np.float32)
    return session.run(None, {"pixels": batch})[0].astype(np.float32)


# ------------------------------------------------------------------------ reading cards


@dataclass(frozen=True)
class Request:
    key: str
    photo: Path
    game: str
    strategy: str
    set_hint: Optional[str] = None
    rarity_claim: Optional[Sequence[str]] = None  # the card's own `rarity_claim` cells


@dataclass
class Result:
    key: str
    accepted: bool
    payload: Optional[dict] = None  # the identification dict, in the card's own strategy's shape
    code: Optional[str] = None  # why it was left unread
    detail: str = ""
    margin: Optional[float] = None
    floor: Optional[float] = None
    candidates: List[dict] = field(default_factory=list)


def _crop(photo: Path, aspect: float):
    """The card alone, in the box's own orientation, cut by `images.card_box_for`, the one guarded
    box the preview uses, then `registered_card`. None when no card is found."""
    import geometry
    from geometry import crop as geometry_crop
    from identify import images

    image = geometry.detect.open_image(photo)
    box = images.card_box_for(photo, aspect=aspect)
    if box is None:
        return None
    return geometry_crop.registered_card(image, box, aspect, keep_orientation=True)


def _base_number(number: str) -> str:
    """A collector number without its alt-art letter or its denominator: `087a/219` and `087/219`
    are one card's two printings. Falls back to the shared fold when no digit leads."""
    from pipeline import join

    found = re.match(r"\s*0*(\d+)", number or "")
    return found.group(1) if found else join.number_index_key(number)


def _stock_images():
    from cli.cmd_pricearchive import market_cache_dir
    from pipeline import pricehistory
    from pipeline.stockimages import StockImages

    return StockImages(market=pricehistory.Market(cache_dir=market_cache_dir()))


def unreleased_sets(game: str) -> Set[str]:
    """The sets whose printings have no stock photo YET, so a no-photo row in one is no look-alike.
    The ONE home of "unreleased". The catalogue's release date decides when it has one: a set
    dated after today. Without dates (Pokemon, or a catalogue that cannot answer), a set is
    unreleased when it holds no photographed row and no row that failed to fetch (a transient failure never skips the guard). Any failure answers the
    empty set, and the guard then stays on."""
    try:
        dated = _stock_images().catalog_published(game)
        if dated:
            today = datetime.now(timezone.utc).date().isoformat()
            return {name for name, published in dated.items() if published[:10] > today}
        if not index_path().exists():
            return set()
        db = sqlite3.connect(f"file:{index_path()}?mode=ro", uri=True)
        try:
            return {
                r[0] for r in db.execute(
                    "select set_name from vec where game=? group by set_name having sum(status in (?,?,?))=0",
                    (game, S_OK, S_UNREADABLE, S_NO_URL)
                )
            }
        finally:
            db.close()
    except Exception:
        return set()


def _pool_cells(pool: Pool, game: str) -> Dict[Tuple[str, str], Tuple[str, str]]:
    """`{(set, product id): (rarity, card type)}` for the pool's sets, read once from
    `StockImages.catalog_products`, the one catalogue reader. A set the catalogue cannot answer
    leaves its printings out, and they read as blank."""
    if pool.cells is None:
        stock = _stock_images()
        pool.cells = {}
        for set_name in pool.sets:
            try:
                listed = stock.catalog_products(game, set_name)
            except Exception:  # a catalogue that cannot answer is a refusal, never a crash
                listed = None
            for product in (listed[0] if listed else ()):
                pool.cells[(set_name, product.product_id)] = (product.rarity, product.card_type)
    return pool.cells


def _pool_rarities(pool: Pool, game: str) -> List[str]:
    """`pool.rarities`, filled once. A blank rarity never matches a claim."""
    if pool.rarities is None:
        cells = _pool_cells(pool, game)
        pool.rarities = [cells.get((row[1], row[2]), ("", ""))[0] for row in pool.rows]
    return pool.rarities


def _pool_card_types(pool: Pool, game: str) -> List[str]:
    """`pool.card_types`, filled once from the same read."""
    if pool.card_types is None:
        cells = _pool_cells(pool, game)
        pool.card_types = [cells.get((row[1], row[2]), ("", ""))[1] for row in pool.rows]
    return pool.card_types


def _settled_by_claim(request: "Request", pool: Pool, order, sims) -> Optional[int]:
    """The pool index of the printing the claim picks, or None. Only when the top two are one
    card (same name, base number and set), both rarities are known, and the claim fits exactly
    one. A third candidate within `MARGIN_MIN` of the pick that is another card, or may also fit
    the claim, refuses. The fit test is `variant.rarity_filter`, where a blank rarity may fit."""
    from pipeline import tcgcsv, variant

    claim = request.rarity_claim
    if not claim or len(order) < 2:
        return None
    top = [int(order[0]), int(order[1])]

    def card(i: int):
        return (card_name(pool.names[i]), _base_number(pool.rows[i][3]), pool.rows[i][1])

    if card(top[0]) != card(top[1]):
        return None
    rarities = _pool_rarities(pool, request.game)
    if not all(rarities[i] for i in top):
        return None
    fits = [i for i in top if variant.rarity_filter([{tcgcsv.RARITY_COLUMN: rarities[i]}], claim)]
    if len(fits) != 1:
        return None
    pick = fits[0]
    for k in order[2:]:
        other = int(k)
        if float(sims[pick]) - float(sims[other]) >= MARGIN_MIN:
            break  # sorted: every later candidate is further away
        if card(other) != card(pick) or variant.rarity_filter(
            [{tcgcsv.RARITY_COLUMN: rarities[other] or ""}], claim
        ):
            return None
    return pick


class _Verdict(NamedTuple):
    pick: int
    code: Optional[str]  # an accept's own reason; None for the baseline accept
    refusal: Optional[str]  # an UNREAD_* code, or None when accepted
    detail: str
    margin: float
    floor: float


def _verdict(request: "Request", pool: Pool, sims, order, blocked: Set[str]) -> _Verdict:
    """The accept rule over one ordered field. The order is fixed: look-alike guard, baseline
    margin (a thin one may be settled by the claim), baseline floor, then the two rules below it,
    clear winner and battlefield. The first that holds names the accept."""
    best = int(order[0])
    floor = float(sims[best])
    margin = floor - float(sims[int(order[1])]) if len(order) > 1 else floor
    if card_name(pool.names[best]) in blocked:
        detail = f"{pool.names[best]} shares its name with a printing that has no stock photo"
        return _Verdict(best, None, UNREAD_LOOKALIKE, detail, margin, floor)
    pick, code = best, None
    if margin < MARGIN_MIN:
        settled = _settled_by_claim(request, pool, order, sims)
        if settled is None:
            return _Verdict(best, None, UNREAD_MARGIN, f"margin {margin:.4f} is under {MARGIN_MIN}", margin, floor)
        pick, code = settled, ACCEPT_CLAIM
        floor = float(sims[pick])  # the floor is the chosen printing's own score
    if floor >= FLOOR_MIN:
        if code is None and card_name(pool.names[best]) in pool.unreleased_names:
            code = ACCEPT_UNRELEASED
        return _Verdict(pick, code, None, "", margin, floor)
    if code is None and margin >= CLEAR_MARGIN_MIN and floor >= CLEAR_FLOOR_MIN:
        return _Verdict(pick, ACCEPT_CLEAR, None, "", margin, floor)
    if (code is None and margin >= BATTLEFIELD_MARGIN_MIN and floor >= BATTLEFIELD_FLOOR_MIN
            and _pool_card_types(pool, request.game)[pick] == BATTLEFIELD_TYPE):
        return _Verdict(pick, ACCEPT_BATTLEFIELD, None, "", margin, floor)
    return _Verdict(pick, None, UNREAD_FLOOR, f"best match {floor:.4f} is under {FLOOR_MIN}", margin, floor)


def _narrowed(request: "Request", pool: Pool, sims, order) -> Optional[_Verdict]:
    """Rule 1. The card's rarity claim only REMOVES competitors from the pool's own field (every
    set of an unhinted game, the hinted set otherwise). The answer is the narrowed field's
    verdict, taken only when its winner is the unnarrowed top-1, whose own rarity is known and
    fits. A printing of unknown rarity may fit, so it stays a competitor (and its no-photo twin
    stays in the guard). Returns None when the claim cannot narrow."""
    from pipeline import tcgcsv, variant

    claim = request.rarity_claim
    if not claim:
        return None
    rarities = _pool_rarities(pool, request.game)

    def fits(rarity: str) -> bool:
        return bool(variant.rarity_filter([{tcgcsv.RARITY_COLUMN: rarity or ""}], claim))

    best = int(order[0])
    if not rarities[best] or not fits(rarities[best]):
        return None
    cells = _pool_cells(pool, request.game)
    blocked = {card_name(name) for set_name, pid, name in pool.blocked_rows if fits(cells.get((set_name, pid), ("", ""))[0])}
    verdict = _verdict(request, pool, sims, [int(i) for i in order if fits(rarities[int(i)])], blocked)
    if verdict.refusal is not None or verdict.pick != best:
        return None
    return verdict._replace(code=ACCEPT_NARROWED)


def _resolve_pool(
    index: Index, game: str, hint: Optional[str], promo_games: Set[str] = frozenset()  # type: ignore[assignment]
) -> Tuple[Optional[Tuple[str, ...]], Optional[str], str]:
    """`(set names, None, "")` or `(None, code, detail)`. The pool rules in the header."""
    from pipeline import games, setnames

    names = index.set_names(game)
    if not names:
        return None, UNREAD_NO_INDEX, f"the index holds no {game} set"
    text = (hint or "").strip()
    if text:
        aliases = (games.get(game) or {}).get("set_aliases")
        found = setnames.resolve(text, names, aliases)
        if found is None:
            # THE HINT IS OFTEN A COMMUNITY CODE ("ME01") THAT THE INDEX'S OWN NAME OMITS: the
            # index holds the catalogue's name ("Mega Evolution"), TCGplayer's export holds
            # "ME01: Mega Evolution". Resolve against the names the game's exports already
            # carry (D213, never fetched), then bring the answer to the index's own spelling.
            known = setnames.known_sets(game)
            full = setnames.resolve(text, known, aliases) if known else None
            if full is not None:
                found = full if full in names else None
                if found is None and game == "pokemon":
                    from pipeline.stockimages import _PokemonImages

                    shown = _PokemonImages().display_name(full)
                    found = shown if shown in names else None
        if found is None:
            return None, UNREAD_HINT, f"the set hint {text!r} does not name one set in the index"
        if is_promo_set(found):
            return None, UNREAD_PROMO, f"{found} is a promo set"
        return (found,), None, ""
    if game == "pokemon":
        return None, UNREAD_NO_HINT, "a Pokemon card with no set hint is never read"
    if game in promo_games or ALL_GAMES in promo_games:
        return None, UNREAD_PROMO_HELD, f"the store holds a promo {game} card, so an unhinted card cannot be matched safely"
    pool = tuple(n for n in names if not is_promo_set(n))
    if not pool:
        return None, UNREAD_NO_INDEX, f"the index holds only promo sets for {game}"
    return pool, None, ""


def _payload(strategy: str, product: Tuple[str, str, str, str], name: str, printed: str, extra: dict) -> dict:
    """The identification dict in the shape the card's own strategy parses. Pokemon splits the
    collector number; Riftbound and One Piece carry the whole printed identifier in `number`.
    `finish` is `unknown` always: a stock photo cannot show foil, so the finish ladder (D3)
    decides on the capture claim and the catalogue."""
    _game, _set, _pid, number = product
    body = {"name": name, "number": number, "finish": "unknown", "confidence": "high"}
    if strategy == "pokemon_card_v1":
        body["printed_total"] = printed
    body.update(extra)
    return body


CHUNK = 32


def read(
    requests: Sequence[Request],
    index: Index,
    model: Optional[Path] = None,
    aspect: float = 0.716,
    log: Callable[[str], None] = lambda _m: None,
    promo_games: Optional[Set[str]] = None,
) -> List[Result]:
    """One `Result` per request, in order. Accepted or not accepted, never guessed.

    IN CHUNKS OF `CHUNK`, BECAUSE A CROP IS A FULL-RESOLUTION IMAGE (about 9 MB decoded) and a whole
    box held at once is gigabytes. Each chunk is cropped, embedded and ranked, then released."""
    out: List[Result] = []
    promos = held_promo_games() if promo_games is None else promo_games
    for start in range(0, len(requests), CHUNK):
        out.extend(_read_chunk(requests[start : start + CHUNK], index, model, aspect, log, promos))
    return out


def _read_chunk(
    requests: Sequence[Request],
    index: Index,
    model: Optional[Path],
    aspect: float,
    log: Callable[[str], None],
    promo_games: Set[str] = frozenset(),  # type: ignore[assignment]
) -> List[Result]:
    import numpy as np

    out: Dict[str, Result] = {}
    current = index.meta("model_sha256") == MODEL_SHA256
    pending: List[Tuple[Request, Tuple[str, ...], "object"]] = []
    for request in requests:
        if isinstance(request.rarity_claim, str):  # the one entry: a bare string is one cell, never a substring pool
            request = replace(request, rarity_claim=[request.rarity_claim])
        if request.game not in SERVED_GAMES:
            out[request.key] = Result(request.key, False, code=UNREAD_GAME, detail=f"the matcher serves {', '.join(SERVED_GAMES)}")
            continue
        if not current:
            out[request.key] = Result(request.key, False, code=UNREAD_INDEX_STALE, detail="the index was built by another model file")
            continue
        sets, code, detail = _resolve_pool(index, request.game, request.set_hint, promo_games)
        if sets is None:
            out[request.key] = Result(request.key, False, code=code, detail=detail)
            continue
        try:
            card = _crop(request.photo, aspect)
        except Exception as exc:  # an unreadable photograph is a named card, never a crash
            out[request.key] = Result(request.key, False, code=UNREAD_UNREADABLE, detail=str(exc)[:120])
            continue
        if card is None:
            out[request.key] = Result(request.key, False, code=UNREAD_NO_CARD, detail="no card was found in the photograph")
            continue
        pending.append((request, sets, card))

    if pending:
        vectors = embed([card for _r, _s, card in pending], model)
        pools: Dict[Tuple[str, Tuple[str, ...]], Pool] = {}
        for (request, sets, _card), vector in zip(pending, vectors):
            pool_key = (request.game, sets)
            if pool_key not in pools:
                pools[pool_key] = index.pool(request.game, sets)
            pool = pools[pool_key]
            if len(pool.rows) == 0:
                out[request.key] = Result(request.key, False, code=UNREAD_NO_INDEX, detail="the pool holds no fingerprint")
                continue
            sims = pool.vectors @ vector
            order = np.argsort(-sims)
            candidates = [
                {
                    "product_id": pool.rows[int(i)][2],
                    "set": pool.rows[int(i)][1],
                    "number": pool.rows[int(i)][3],
                    "name": pool.names[int(i)],
                    "cosine": round(float(sims[int(i)]), 4),
                }
                for i in order[:TOP_N]
            ]
            verdict = _verdict(request, pool, sims, order, pool.blocked)
            if verdict.refusal is not None:
                narrowed = _narrowed(request, pool, sims, order)
                if narrowed is not None:
                    verdict = narrowed
            if verdict.refusal is not None:
                out[request.key] = Result(
                    request.key, False, code=verdict.refusal, detail=verdict.detail,
                    margin=verdict.margin, floor=verdict.floor, candidates=candidates,
                )
                continue
            pick, code, margin, floor = verdict.pick, verdict.code, verdict.margin, verdict.floor
            payload = _payload(
                request.strategy, pool.rows[pick], pool.names[pick], pool.printed[pick],
                {
                    "engine": ENGINE,
                    "product_id": pool.rows[pick][2],
                    "set": pool.rows[pick][1],
                    "margin": round(margin, 4),
                    "floor": round(floor, 4),
                    "candidates": candidates,
                    "model_sha256": MODEL_SHA256,
                    **({"settled_by": "rarity_claim"} if code in (ACCEPT_CLAIM, ACCEPT_NARROWED) else {}),
                    **({"accept_rule": code} if code else {}),
                },
            )
            out[request.key] = Result(request.key, True, payload=payload, code=code, margin=margin, floor=floor, candidates=candidates)
    return [out[r.key] for r in requests]


# ------------------------------------------------------------------------ the preflight


def preflight(
    requests: Sequence[Request],
    index: Optional[Index] = None,
    model: Optional[Path] = None,
    promo_games: Optional[Set[str]] = None,
) -> Dict[str, object]:
    """What a matcher press would do BEFORE any photograph is decoded or any vector made.
    Free. It counts the cards the pool rules already leave unread; the margin, the floor and
    the guard act on the best answer, so they cannot be counted until the read."""
    summary: Dict[str, object] = {"cards": len(requests), "can_read": 0, "unread": {}, "state": status(index, model)}
    unread: Dict[str, int] = {}
    if not summary["state"]["ready"]:  # type: ignore[index]
        unread["not_ready"] = len(requests)
        summary["unread"] = unread
        return summary
    own = index or Index()
    promos = held_promo_games() if promo_games is None else promo_games
    for request in requests:
        if request.game not in SERVED_GAMES:
            unread[UNREAD_GAME] = unread.get(UNREAD_GAME, 0) + 1
            continue
        sets, code, _detail = _resolve_pool(own, request.game, request.set_hint, promos)
        if sets is None:
            unread[str(code)] = unread.get(str(code), 0) + 1
        else:
            summary["can_read"] = int(summary["can_read"]) + 1  # type: ignore[call-overload]
    summary["unread"] = unread
    return summary


# ------------------------------------------------------------------------ building the index


def fetch_bytes(
    url: str,
    *,
    attempts: int = 6,
    gap: float = 0.2,
    gate: Optional[threading.Lock] = None,
    clock: Optional[List[float]] = None,
    opener: Callable[..., "object"] = urllib.request.urlopen,
) -> Tuple[Optional[bytes], Optional[str]]:
    """`(bytes, None)` or `(None, cause)`. One polite read: a global gap between request
    starts, a retry with backoff, Retry-After honoured. 403, 404 and 410 are an answer, not a
    failure: the CDN says the file is not there (`no_photo`)."""
    delay = 1.0
    cause = "unreadable"
    headers = {"User-Agent": "banchi-fingerprint-index/1 (owner-run, polite, one read per image)"}
    for _attempt in range(attempts):
        if gate is not None and clock is not None:
            with gate:
                wait = clock[0] + gap - time.time()
                if wait > 0:
                    time.sleep(wait)
                clock[0] = time.time()
        try:
            with opener(urllib.request.Request(url, headers=headers), timeout=30) as response:
                return response.read(), None
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404, 410):
                return None, f"http_{exc.code}"
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            time.sleep(float(retry_after) if retry_after and retry_after.isdigit() else delay)
            cause = f"http_{exc.code}"
        except Exception as exc:  # network, timeout, TLS: retried, then named
            time.sleep(delay)
            cause = type(exc).__name__
        delay = min(delay * 2, 16) + random.random() * 0.3
    return None, cause


@dataclass
class BuildReport:
    sets: int = 0
    products: int = 0
    embedded: int = 0
    no_image: int = 0
    unreadable: int = 0
    skipped: int = 0
    unresolved: List[str] = field(default_factory=list)


def build_index(
    index: Index,
    targets: Iterable[Tuple[str, str]],
    stock,
    model: Optional[Path] = None,
    *,
    workers: int = 3,
    fetch: Callable[[str], Tuple[Optional[bytes], Optional[str]]] = None,  # type: ignore[assignment]
    progress: Callable[[int, int, str], None] = lambda _d, _t, _m: None,
    log: Callable[[str], None] = lambda _m: None,
) -> BuildReport:
    """Read every missing or changed stock image of every target set once, in memory, and
    store the vectors. Resumable: an `ok` row with an unchanged URL and an unchanged model is
    skipped, so a stopped run carries on and a refresh reads only what is new. A row with no
    photo is asked again every press, because a set that has just released gains its images.

    `stock` is a `pipeline.stockimages.StockImages`. `targets` is `(game, set_name)` pairs."""
    from PIL import Image

    target_model = model or model_path()
    sha = MODEL_SHA256 if model is None else sha256_of_file(target_model)
    have = index.meta("model_sha256")
    if have and have != sha:
        raise IndexError_(
            "the fingerprints were built by another model file. A model change rebuilds every fingerprint: "
            "clear them first."
        )
    index.meta("model_sha256", sha)
    index.meta("built_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    index.meta("preprocess", f"resize {INPUT_SIZE}x{INPUT_SIZE} bicubic, /255, (x-{NORM_MEAN})/{NORM_STD}, CHW; landscape stock turned upright")

    report = BuildReport()
    plan: List[Tuple[str, str, "object"]] = []
    seen_sets: Set[Tuple[str, str]] = set()
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for game, set_name in targets:
        listed = stock.catalog_products(game, set_name)
        if listed is None:
            report.unresolved.append(f"{game} | {set_name}")
            continue
        products, unnumbered = listed
        canonical = canonical_set(stock, game, set_name)
        if (game, canonical) in seen_sets:
            continue
        seen_sets.add((game, canonical))
        source = "vendored" if game == "pokemon" else "tcgcsv"
        index.db.execute(
            "insert or replace into sets values(?,?,?,?,?,?,?)",
            (game, canonical, source, "", len(products), unnumbered, now),
        )
        if game == "pokemon" and products:
            index.meta(f"printed:{game}:{canonical}", products[0].printed_total)
        done = {
            pid: (status_, url)
            for pid, status_, url in index.db.execute(
                "select product_id, status, url from vec where game=? and set_name=?", (game, canonical)
            )
        }
        report.sets += 1
        for product in products:
            report.products += 1
            if done.get(product.product_id) == (S_OK, product.url):
                report.skipped += 1
                continue
            if not product.url:
                index.db.execute(
                    "insert or replace into vec values(?,?,?,?,?,?,?,?,?,?)",
                    (game, canonical, product.product_id, product.number, product.name, "", S_NO_URL, None, None, now),
                )
                report.no_image += 1
                continue
            plan.append((game, canonical, product))
    index.db.commit()

    gate = threading.Lock()
    clock = [0.0]
    reader = fetch or (lambda url: fetch_bytes(url, gate=gate, clock=clock))

    def one(entry):
        game, set_name, product = entry
        raw, cause = reader(product.url)
        if raw is None:
            return entry, None, cause
        try:
            image = Image.open(io.BytesIO(raw))
            image.load()
            return entry, preprocess(image), None  # the bytes die here, in memory
        except Exception as exc:
            return entry, None, "decode_" + type(exc).__name__

    total = len(plan)
    batch: List[Tuple[tuple, "object"]] = []

    def flush() -> None:
        import numpy as np

        if not batch:
            return
        session = _session(target_model)
        array = np.stack([x for _e, x in batch]).astype(np.float32)
        vectors = session.run(None, {"pixels": array})[0].astype(np.float32)
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        for (entry, _x), vector in zip(batch, vectors):
            game, set_name, product = entry
            index.db.execute(
                "insert or replace into vec values(?,?,?,?,?,?,?,?,?,?)",
                (game, set_name, product.product_id, product.number, product.name, product.url, S_OK, None, vector.tobytes(), stamp),
            )
        index.db.commit()
        report.embedded += len(batch)
        batch.clear()

    with ThreadPoolExecutor(max(1, workers)) as pool:
        for count, (entry, array, cause) in enumerate(pool.map(one, plan), 1):
            game, set_name, product = entry
            if array is not None:
                batch.append((entry, array))
                if len(batch) >= 16:
                    flush()
            else:
                status_ = S_NO_PHOTO if cause in ("http_403", "http_404", "http_410") else S_UNREADABLE
                if status_ == S_NO_PHOTO:
                    report.no_image += 1
                else:
                    report.unreadable += 1
                log(f"{status_}: {game} | {set_name} | {product.number} {product.name} | {cause}")
                index.db.execute(
                    "insert or replace into vec values(?,?,?,?,?,?,?,?,?,?)",
                    (game, set_name, product.product_id, product.number, product.name, product.url, status_, cause, None, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
                )
                index.db.commit()
            progress(count, total, f"{set_name}")
    flush()
    return report


RECHECK_ROWS_PER_PASS = 20  # one weekly pass asks the oldest this many rows, so a big backlog drains over passes
# ponytail: `vec.note` doubles as the retry class (an answer from the CDN waits a week, any other cause a day); a column for the next-ask time if a third wait is needed.
_ANSWERED = ("http_403", "http_404", "http_410")  # the CDN's answer for a missing file: the row waits a week
_NETWORK = ("URLError", "timeout", "TimeoutError")  # the network is down: the pass ends at once


def _stamp_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def recheck_no_photo(
    stock,
    *,
    fetch: Callable[[str], Tuple[Optional[bytes], Optional[str]]] = None,  # type: ignore[assignment]
    model: Optional[Path] = None,
    days: int = 7,
) -> BuildReport:
    """One free weekly pass: ask again the `no_photo` and `no_url` rows last asked over `days` days ago, the oldest
    `RECHECK_ROWS_PER_PASS` by `vec.at`. Never an `ok` row, never a whole set. A `no_url` row's set has its catalogue
    listing read once for a URL. A row that now has an image is fingerprinted. A row the CDN or the catalogue
    answered for (403, 404, 410, or a listing with no URL) gets `at` set to now and waits another week. Any other
    failure (5xx, 429, decode) is transient: it sets `at` to now and `note` to the cause, and a row with such a note
    is asked again after one day, not seven. A network failure (`URLError`, timeout), returned or raised, ends the
    pass at once and writes nothing for that row. A set whose listing could not be read leaves its rows undated.
    Nothing spends.

    Locking: no write transaction is open across a fetch. Each result is one short write on its own connection,
    after a re-read of the row: a row that is `ok` by then (a Prepare finished mid-look) is left alone.
    The pass holds the Prepare's own running record (`prepare_pid`) for its whole length, so one Prepare runs at a
    time and the sweep's tried marks made meanwhile are `building` marks, dropped when the pass ends.
    That is how a miss is never stamped with the post-gain `index_stamp` against a pool loaded before the gain.
    The caller (`pipeline_routes.recheck_stock_photos`) checks that no Prepare runs. Nothing here does, so a direct call
    over a running Prepare would overwrite its record.
    # ponytail: the check and the record write are two steps with no lock; a Prepare started in that gap is not
    # stopped, and both write whole rows, so the cost is a repeat read."""
    from PIL import Image

    report = BuildReport()
    if not index_path().exists():
        return report
    target_model = model or model_path()
    sha = MODEL_SHA256 if model is None else sha256_of_file(target_model)
    cutoff = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - days * 86400))
    cutoff_day = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 86400))
    gate = threading.Lock()
    clock = [0.0]
    reader = fetch or (lambda url: fetch_bytes(url, gate=gate, clock=clock))
    record = {"state": "running", "phase": "recheck", "done": 0, "total": 0, "message": "Checking printings with no photo", "pid": os.getpid(), "at": time.time()}
    store_files.write_json(progress_path(), record)
    try:
        with Index() as index:
            have = index.meta("model_sha256")
            if have and have != sha:
                raise IndexError_("the fingerprints were built by another model file. Clear them first.")
            old = index.db.execute(
                "select game, set_name, product_id, number, name, url, status from vec where status in (?,?) and "
                "((note is not null and note not in (?,?,?) and at < ?) or ((note is null or note in (?,?,?)) and at < ?)) "
                "order by at, product_id limit ?",
                (S_NO_PHOTO, S_NO_URL, *_ANSWERED, cutoff_day, *_ANSWERED, cutoff, RECHECK_ROWS_PER_PASS),
            ).fetchall()
        listed: Dict[Tuple[str, str], Optional[Dict[str, str]]] = {}
        for game, set_name in sorted({(r[0], r[1]) for r in old if r[6] == S_NO_URL}):
            products = stock.catalog_products(game, set_name)  # one catalogue read per affected set
            listed[(game, set_name)] = None if products is None else {p.product_id: p.url for p in products[0]}
        report.sets = len({(r[0], r[1]) for r in old})

        def write(row, sql: str, args: tuple) -> None:
            with Index() as index:
                current = index.db.execute(
                    "select status from vec where game=? and set_name=? and product_id=?", (row[0], row[1], row[2])
                ).fetchone()
                if current and current[0] != S_OK:
                    index.db.execute(sql, args + (row[0], row[1], row[2]))
                    index.db.commit()

        gained: List[Tuple[tuple, str, "object"]] = []
        for row in old:
            url = row[5]
            if row[6] == S_NO_URL:
                found = listed[(row[0], row[1])]
                if found is None:
                    # the listing could not be read: the same one-day transient clock, so the set is not read again every look
                    write(row, "update vec set note=?, at=? where game=? and set_name=? and product_id=?", ("catalog_unreadable", _stamp_now()))
                    continue
                url = found.get(row[2]) or ""
            report.products += 1
            if not url:
                report.no_image += 1
                write(row, "update vec set url='', status=?, note=null, at=? where game=? and set_name=? and product_id=?", (S_NO_URL, _stamp_now()))
                continue
            try:
                raw, cause = reader(url)
            except (urllib.error.URLError, TimeoutError) as exc:
                raw, cause = None, type(exc).__name__
            if cause in _NETWORK:
                # the pass ends, and this row is dated on the one-day clock so a dead URL does not block the rows behind it
                write(row, "update vec set note=?, at=? where game=? and set_name=? and product_id=?", (cause, _stamp_now()))
                break
            array = None
            if raw is not None:
                try:
                    image = Image.open(io.BytesIO(raw))
                    image.load()
                    array = preprocess(image)
                except Exception as exc:  # noqa: BLE001
                    cause = "decode_" + type(exc).__name__
            if array is not None:
                gained.append((row, url, array))
            elif cause in _ANSWERED:
                report.no_image += 1
                write(row, "update vec set url=?, status=?, note=?, at=? where game=? and set_name=? and product_id=?", (url, S_NO_PHOTO, cause, _stamp_now()))
            else:
                report.unreadable += 1  # transient: dated now with its cause, so the oldest-first order moves on and it returns in a day
                write(row, "update vec set note=?, at=? where game=? and set_name=? and product_id=?", (str(cause), _stamp_now()))
        if gained:
            import numpy as np

            vectors = _session(target_model).run(None, {"pixels": np.stack([a for _r, _u, a in gained]).astype(np.float32)})[0].astype(np.float32)
            for (row, url, _a), vector in zip(gained, vectors):
                write(row, "update vec set url=?, status=?, note=null, vec=?, at=? where game=? and set_name=? and product_id=?", (url, S_OK, vector.tobytes(), _stamp_now()))
                report.embedded += 1
    finally:
        mine = store_files.read_json(progress_path(), None)
        if isinstance(mine, dict) and mine.get("pid") == os.getpid() and mine.get("state") == "running":
            store_files.write_json(progress_path(), {**record, "state": "done", "at": time.time()})
    return report


def targets_for(stock, store_pairs: Iterable[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """The sets to fingerprint: every `(game, set)` the store holds cards for, plus every
    Riftbound set. Only the served games."""
    wanted: List[Tuple[str, str]] = []
    seen: Set[Tuple[str, str]] = set()
    for game, set_name in store_pairs:
        if game in SERVED_GAMES and set_name and (game, set_name) not in seen:
            seen.add((game, set_name))
            wanted.append((game, set_name))
    for set_name, _group_id in stock.catalog_sets("riftbound"):
        if ("riftbound", set_name) not in seen:
            seen.add(("riftbound", set_name))
            wanted.append(("riftbound", set_name))
    return wanted


def canonical_set(stock, game: str, set_name: str) -> str:
    """The name `build_index` stores a set under: the catalogue's own, else the store's."""
    return (stock.display_name(game, set_name) if game == "pokemon" else None) or set_name


def unread_targets(stock, store_pairs: Iterable[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """`targets_for` minus the sets the fingerprint index already holds, compared by canonical name."""
    with Index() as index:
        held = {(g, n) for g, n in index.db.execute("select game, set_name from sets")}
    return [t for t in targets_for(stock, store_pairs) if (t[0], canonical_set(stock, *t)) not in held]


def prepare_pid() -> Optional[int]:
    """The pid of a running `match prepare`, or None. It reads the progress file the child
    writes, so a prepare started by a server that has since restarted still counts."""
    try:
        record = json.loads(progress_path().read_text("utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict) or record.get("state") != "running":
        return None
    pid = record.get("pid")
    if not isinstance(pid, int):
        return None
    if pid == os.getpid():
        return pid  # the server's own placeholder, written before the spawn: alive, and no ps needed
    # `kill -0` succeeds on a zombie, so ask for the state: an exited child is not running.
    try:
        state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, timeout=2).stdout.strip()
    except Exception:  # noqa: BLE001  any ps failure, however it shows, falls back to the alive check
        try:
            os.kill(pid, 0)  # ps unavailable: the old alive check beats a 500 on a polled route
        except OSError:
            return None
        return pid
    if not state or state.startswith("Z"):
        return None
    return pid


def index_stamp() -> str:
    """Changes when the index gains a set or a fingerprint. A card tried before its set or photo was read is tried again.
    Reads the file directly, so a missing index is "0" and nothing is created."""
    try:
        db = sqlite3.connect(f"file:{index_path()}?mode=ro", uri=True)
    except sqlite3.Error:
        return "0"
    try:
        return str(db.execute("select count(*) from sets").fetchone()[0]) + ":" + str(
            db.execute("select count(*) from vec where status=?", (S_OK,)).fetchone()[0]
        )
    except sqlite3.Error:
        return "0"
    finally:
        db.close()
