"""Ground-truth eval images from pokemontcg.io. Downloaded once, then cached forever.

The API record IS the label (docs/GATES.md T1) — `name`, `number`, and
`set.printedTotal` come back in the same response as the image URL, so there is no
hand-labelling step to get wrong or to redo.

Cached under `harness/images/`, which is gitignored: these are reproducible from a
public API, they are large, and committing them would put ~50 binaries in every clone to
save one HTTP call. The manifest next to them records the selection and the labels, and
a rerun that finds a matching manifest with every file present makes NO network calls at
all. `PKMNSCAN_REFRESH_IMAGES=1` forces a re-fetch.

Selection is deterministic — cards sorted by collector number, then sampled at an even
stride. That spreads the sample across the print run rather than clustering on the low
numbers, so commons, rares, and the secret rares past the denominator are all
represented, and two runs a week apart score the same cards.

Every card also carries a `split`: TUNE or HOLDOUT, decided by hashing its id. Prompt
work is done against TUNE failures only, and the gate reads the HOLDOUT score. Without
that separation, fixing the handful of images that failed and re-scoring the same set
reports a number that says nothing about the next card — which is the only thing the
number is for, since production has no answer key.

Works keyless — the rate limits cover a 50-image harness — but reads
`POKEMONTCG_API_KEY` from the environment or `.env` when present, which is what makes
set-scale processing viable. The key raises the rate limit; it does not stop the endpoint
returning transient 5xx, so `_fetch` retries regardless.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import envfile

API_ROOT = "https://api.pokemontcg.io/v2"
IMAGE_SIZE = "large"  # ~600x825 — well inside the vision cap, and the small one is mush
USER_AGENT = "pkmnscan-harness/1.0 (+T1 ground-truth eval)"
HTTP_TIMEOUT = 30
# The endpoint returns 500 in bursts lasting tens of seconds — observed answering 500
# five times running, then 200. Five quick attempts covered ~15s and lost a whole
# download to it. This budget covers ~70s per URL.
HTTP_ATTEMPTS = 8
HTTP_BACKOFF_CAP = 20.0

# The free key from dev.pokemontcg.io (build-order step 10, done 2026-08-03). Read from
# the environment or `.env`. Sent to the API host only, never to the image CDN.
API_KEY_ENV = "POKEMONTCG_API_KEY"

# WHERE THE MIRROR LIVES, AND IT IS A KNOB BECAUSE OF ITS SIZE (D15). `PKMNSCAN_IMAGE_MIRROR`
# has been documented since build-order step 9 was written and read by nothing until 2026-08-30,
# when D46 made moving it the remedy rather than a preference: this repository is inside iCloud
# Drive, and 133 MB of derived binaries syncing there is what produced the conflict copies D44
# refuses at the commit.
#
# THE DEFAULT IS UNCHANGED, so a tree that sets nothing behaves exactly as it always did — which
# is what keeps every banked score comparable across the change. An empty value reads as unset
# rather than as the current directory: `Path("")` is `.`, and silently mirroring into the CWD is
# the kind of wrong nobody would look for.
#
# EXPANDED BUT NOT RESOLVED. `~` and `$VARS` are what a person types in a shell profile; a
# symlink in the path is deliberately left alone, because resolving it here would make the
# stored manifest name a path the operator did not write.
#
# THROUGH `envfile` AND NOT `os.environ`, so `.env` is a place to set it. That file is this
# repo's existing per-machine location — gitignored, and PER CHECKOUT, which is the property
# that matters here: a mirror path is a fact about one machine's disk and a worktree that
# inherited one from a tree it does not share would be worse than having none. A real
# environment variable still wins, which is what `envfile.get` already guarantees.
_MIRROR = envfile.get("PKMNSCAN_IMAGE_MIRROR")
IMAGES_DIR = (
    Path(os.path.expandvars(os.path.expanduser(_MIRROR)))
    if _MIRROR
    else Path(__file__).resolve().parents[2] / "harness" / "images"
)
MANIFEST = IMAGES_DIR / "manifest.json"
SETS_DIR = IMAGES_DIR / ".sets"  # per-set API responses, banked so a flake is resumable

_MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


@dataclass(frozen=True)
class SetSpec:
    set_id: str
    count: int


# 150 images across 10 SV-era sets (D12 scope: modern era, English), spanning the whole
# era from the 2023 base set to Journey Together — which is also the set the committed
# TCGplayer fixture was exported from, so T1 and T3 look at the same product line.
#
# 150 rather than 50 because one card was two percentage points at n=50 and the
# confidence interval was roughly +/-6, which made 0.94 and 0.96 indistinguishable. Ten
# sets rather than three because card layout is a per-set decision: one set with an
# unusual template can otherwise dominate the score.
EVAL_SETS: Tuple[SetSpec, ...] = (
    SetSpec("sv1", 15),  # Scarlet & Violet
    SetSpec("sv2", 15),  # Paldea Evolved
    SetSpec("sv3", 15),  # Obsidian Flames
    SetSpec("sv3pt5", 15),  # 151
    SetSpec("sv4", 15),  # Paradox Rift
    SetSpec("sv5", 15),  # Temporal Forces
    SetSpec("sv6", 15),  # Twilight Masquerade
    SetSpec("sv7", 15),  # Stellar Crown
    SetSpec("sv8", 15),  # Surging Sparks
    SetSpec("sv9", 15),  # Journey Together — the fixture export's set
)

TUNE = "tune"
HOLDOUT = "holdout"

# Cards whose failures were already inspected before the split existed (the 2026-08-03
# n=50 run). A holdout you have already looked at is not a holdout, so these are pinned
# to the tuning half rather than left to the hash. Add to this list rather than quietly
# reasoning that one lookup "probably didn't matter".
SEEN_BEFORE_SPLIT = frozenset({"sv3pt5-61", "sv3pt5-171", "sv4-235"})


def split_of(card_id: str) -> str:
    """Which half a card belongs to. Deterministic from the id — no stored state, no
    shuffle seed to lose, and the same answer on any machine at any time."""
    if card_id in SEEN_BEFORE_SPLIT:
        return TUNE
    digest = hashlib.sha256(("pkmnscan-t1-split/" + card_id).encode("utf-8")).hexdigest()
    return TUNE if int(digest[:8], 16) % 2 == 0 else HOLDOUT


class FixtureError(RuntimeError):
    """The eval images could not be assembled. T1 reports it; it never guesses around it."""


@dataclass(frozen=True)
class EvalCard:
    """One labelled image. Every field but `image` is ground truth from the API."""

    card_id: str
    set_id: str
    set_name: str
    name: str
    number: str
    printed_total: str
    rarity: str
    image: str  # filename, relative to IMAGES_DIR
    media_type: str

    @property
    def path(self) -> Path:
        return IMAGES_DIR / self.image

    @property
    def split(self) -> str:
        return split_of(self.card_id)


def spec_key(sets: Sequence[SetSpec] = EVAL_SETS) -> Dict[str, object]:
    return {
        "api": API_ROOT,
        "image_size": IMAGE_SIZE,
        "sets": [[s.set_id, s.count] for s in sets],
    }


def api_key() -> str:
    """The pokemontcg.io key, from the environment or `.env`. Empty means keyless."""
    return envfile.get(API_KEY_ENV)


def _headers(url: str) -> Dict[str, str]:
    """Auth the API, not the CDN. images.pokemontcg.io serves files and takes no key;
    sending one there is a credential leaked to a host that never asked for it."""
    headers = {"User-Agent": USER_AGENT}
    key = api_key()
    if key and url.startswith(API_ROOT):
        headers["X-Api-Key"] = key
    return headers


def _fetch(url: str) -> bytes:
    """GET with backoff. The API returns transient 5xx often enough that a single-shot
    fetch fails the harness for reasons that have nothing to do with the code under
    test — observed sv4 answering 500, 500, then 200 within a minute. A key raises the
    rate limit; it does not make the endpoint stop flaking, so the retry stays."""
    last = ""
    delay = 1.0
    for attempt in range(1, HTTP_ATTEMPTS + 1):
        request = urllib.request.Request(url, headers=_headers(url))
        try:
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            last = "HTTP {0} {1}".format(exc.code, exc.reason)
            # 4xx other than rate limiting is a bad request; retrying cannot fix it.
            if exc.code < 500 and exc.code != 429:
                break
        except Exception as exc:  # timeouts, DNS, reset connections
            last = str(exc)
        if attempt < HTTP_ATTEMPTS:
            time.sleep(delay)
            delay = min(delay * 2, HTTP_BACKOFF_CAP)
    raise FixtureError("{0} -> {1} (after {2} attempts)".format(url, last, HTTP_ATTEMPTS))


def _get_json(url: str) -> dict:
    try:
        return json.loads(_fetch(url).decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise FixtureError("{0} -> malformed JSON: {1}".format(url, exc)) from exc


def _get_bytes(url: str) -> bytes:
    return _fetch(url)


def _number_sort_key(number: str) -> Tuple[str, int, str]:
    """Sort "9" before "10", and keep lettered subsets (TG01, GG05) in their own run."""
    digits = "".join(ch for ch in number if ch.isdigit())
    prefix = "".join(ch for ch in number if not ch.isdigit())
    return (prefix, int(digits) if digits else 0, number)


def _stride(seq: Sequence[dict], count: int) -> List[dict]:
    """Evenly spaced sample. Distinct indices whenever count <= len(seq)."""
    total = len(seq)
    if count >= total:
        return list(seq)
    return [seq[index * total // count] for index in range(count)]


def _set_cards(set_id: str) -> List[dict]:
    """Every card record for one set, banked to disk on first success.

    Ten sets means ten chances for a flaky endpoint to abort the whole download, and
    without this a failure on the fourth set threw away the first three. Each set is
    cached raw — before filtering or sampling — so a re-run resumes instead of restarting,
    and so changing the sampling rule costs no network at all.
    """
    cached = SETS_DIR / "{0}.json".format(set_id)
    if cached.is_file():
        try:
            records = json.loads(cached.read_text("utf-8"))
            if records:
                return records
        except (json.JSONDecodeError, OSError):
            pass  # corrupt bank, re-fetch below

    query = urllib.parse.urlencode(
        {
            "q": "set.id:{0}".format(set_id),
            "pageSize": 250,
            "select": "id,name,number,rarity,images,set",
        }
    )
    payload = _get_json("{0}/cards?{1}".format(API_ROOT, query))
    records = payload.get("data") or []
    if not records:
        raise FixtureError(
            "set {0!r} returned no cards — check the id against {1}/sets".format(
                set_id, API_ROOT
            )
        )
    SETS_DIR.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps(records), "utf-8")
    return records


def _fetch_set(spec: SetSpec) -> List[dict]:
    cards = _set_cards(spec.set_id)
    usable = [
        card
        for card in cards
        if card.get("number")
        and (card.get("images") or {}).get(IMAGE_SIZE)
        and (card.get("set") or {}).get("printedTotal")
    ]
    if len(usable) < spec.count:
        raise FixtureError(
            "set {0!r} has {1} usable cards, need {2}".format(
                spec.set_id, len(usable), spec.count
            )
        )

    usable.sort(key=lambda card: _number_sort_key(str(card["number"])))
    return _stride(usable, spec.count)


def _to_eval_card(card: dict) -> Tuple[EvalCard, str]:
    """The labelled record, plus the URL it downloads from (which is not part of the label)."""
    url = card["images"][IMAGE_SIZE]
    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
    media_type = _MEDIA_TYPES.get(suffix)
    if media_type is None:
        raise FixtureError("card {0}: unsupported image type {1!r}".format(card["id"], suffix))
    return (
        EvalCard(
            card_id=card["id"],
            set_id=card["set"]["id"],
            set_name=card["set"].get("name", card["set"]["id"]),
            name=card["name"],
            number=str(card["number"]),
            printed_total=str(card["set"]["printedTotal"]),
            rarity=card.get("rarity") or "",
            image="{0}{1}".format(card["id"], suffix),
            media_type=media_type,
        ),
        url,
    )


def _read_manifest() -> Optional[dict]:
    if not MANIFEST.is_file():
        return None
    try:
        return json.loads(MANIFEST.read_text("utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _cached(sets: Sequence[SetSpec]) -> Optional[List[EvalCard]]:
    manifest = _read_manifest()
    if not manifest or manifest.get("spec") != spec_key(sets):
        return None
    try:
        cards = [EvalCard(**record) for record in manifest["cards"]]
    except (KeyError, TypeError):
        return None
    if len(cards) != sum(s.count for s in sets):
        return None
    if not all(card.path.is_file() and card.path.stat().st_size > 0 for card in cards):
        return None
    return cards


def load(
    sets: Sequence[SetSpec] = EVAL_SETS,
    *,
    refresh: Optional[bool] = None,
    log=None,
) -> List[EvalCard]:
    """Labelled eval images, downloading only when the cache does not already answer."""
    say = log or (lambda _message: None)
    if refresh is None:
        refresh = os.environ.get("PKMNSCAN_REFRESH_IMAGES") == "1"

    if not refresh:
        cached = _cached(sets)
        if cached is not None:
            say("{0} images cached in {1}".format(len(cached), IMAGES_DIR))
            return cached

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    say("pokemontcg.io: {0}".format("keyed" if api_key() else "keyless (rate-limited)"))
    pairs: List[Tuple[EvalCard, str]] = []
    for spec in sets:
        say("fetching {0} ({1} cards) from pokemontcg.io".format(spec.set_id, spec.count))
        pairs.extend(_to_eval_card(card) for card in _fetch_set(spec))

    for index, (card, url) in enumerate(pairs, start=1):
        if card.path.is_file() and card.path.stat().st_size > 0:
            continue
        card.path.write_bytes(_get_bytes(url))
        say("  downloaded {0}/{1}  {2}".format(index, len(pairs), card.card_id))

    cards = [card for card, _url in pairs]
    MANIFEST.write_text(
        json.dumps(
            {"spec": spec_key(sets), "cards": [asdict(card) for card in cards]},
            indent=2,
            sort_keys=True,
        ),
        "utf-8",
    )
    say("{0} images in {1}".format(len(cards), IMAGES_DIR))
    return cards


def fixture_fingerprint(cards: Sequence[EvalCard]) -> str:
    """Hash of the exact image set, so a changed selection invalidates a cached run."""
    payload = json.dumps(
        sorted(
            [card.card_id, card.name, card.number, card.printed_total] for card in cards
        ),
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
