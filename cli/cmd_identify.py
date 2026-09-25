"""`pkmnscan identify <capture-dir>` — the only command that costs money.

Because it costs money, everything that can be checked for free is checked first and
printed before a single byte is submitted: card count, payload size, batch chunks, estimated
cost, prompt fingerprint, and how many answers the cache already owns. `--dry-run` does all
of it and stops — so a mistyped directory, a malformed sidecar, and an unreadable photo all
surface for nothing.

RESUME BEATS RESUBMIT. Batch results stay retrievable for 29 days, so a run whose script
died mid-poll already owns its answers. Re-running reattaches by default; `--force-resubmit`
pays again on purpose, which is what you want after a prompt change and never otherwise.

RETRY, THEN CROP RETRY. A card that errored, expired, was cancelled or came back malformed
is re-sent within `--retry-budget` (default 1). A card that came back `low` confidence or
malformed is re-sent WITH CROPS: the card found in the frame, deskewed, plus enlarged title
and number bands. A `025` rendered 40px wide is a coin flip; the same digits at 600px are
not. If the card cannot be found in the frame there is no crop retry at all — cropping blind
produces a miss indistinguishable from a bad read — and the failure is named in the report so
a systematic rig problem reads as a pattern rather than as scattered bad luck.

HASH, THEN CACHE, THEN PREPARE — in that order, since 2026-09-12. The cache is keyed by the
photograph's sha256, which is a property of the bytes on disk, so consulting it needs no
decode at all. Every photograph is hashed (0.687 ms), the store is asked what it already
owns, and only what is left is cropped and downscaled (114.96 ms). Both figures measured on
this machine over box 4's own 678 JPEGs at the operator's flags. One dry-run leg of that
directory went from 79 s to 26 s and submitted the same 214 cards.

NOTHING IS EVER SKIPPED. Every photograph in the directory comes out of this command as an
identification, a cache hit, or a named failure. That is v1 bug #5 stated as a property —
and `Item.stage` is what keeps it true through the reorder above, because `prepared is None`
used to mean "unreadable" and now also means "the store already answered this one". See the
STAGE_* constants.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import geometry
from cli import runs
from identify import batch, cost, images, prompt, sidecar
from pipeline import games
from pipeline import join
from pipeline import selection as selection_mod
from store import files as store_files
from store import master
from store import submissions
from store.session import Store

# THE RATES MOVED TO `identify/cost.py` ON 2026-09-11, and nothing about them changed. They
# went because `server/pipeline_routes.py` needed them to report what a finished run cost and
# could not import this module for them: its own rule is stdlib-only at module scope, and this
# file reaches geometry, PIL and sqlite. `identify/cost.py` is dependency-free and is now the
# only place in this repo that multiplies a token count by a rate.
#
# An ESTIMATE, printed before you spend: it exists so that a mistyped directory of 40,000
# photos is visibly a different number from a box of 400. Not an invoice, and nothing
# reconciles against it. That is what the three constants below are for — the rates above it
# are what the run is BILLED at, which is a different number and is recorded rather than
# guessed.
PIXELS_PER_TOKEN = Decimal("750")
# MEASURED, NOT ASSUMED, as of 2026-08-23. This read 500 and was wrong by about half: box 2's
# 544-card run billed 1,315,698 input tokens — 2,419 per card — against roughly 1,416 of image
# at that configuration, leaving ~1,000 tokens of system and user turn. The estimate came in at
# $0.62 against an actual $0.71, 15% low.
#
# The docstring above is right that this is an estimate and not an invoice, and nothing
# reconciles against it. But it is the number somebody reads while deciding whether to spend,
# so a bias that runs consistently in the cheap direction is the wrong bias to leave in place.
# One real run is better evidence than the round number that was here.
#
# It is Pokemon's turn that was measured. `misc` and the code-card profile carry different
# prompts and are not separately measured; per-profile overhead is the refinement to reach for
# if a run of those ever misses by enough to matter.
SYSTEM_TOKENS = 1000
OUTPUT_TOKENS = 60

# What triggers which kind of retry (v2 §4.4, §4.5).
PLAIN_RETRY_STATUSES = ("errored", "expired", "canceled", "absent")
CROP_RETRY_STATUSES = ("malformed",)
WEAK_CONFIDENCE = "low"

DETECTED = "found"
NOT_DETECTED = "not_found"
NOT_ATTEMPTED = "not_attempted"
# A card was found and the box was not fit to cut to — `images.crop_refusal` said so. A
# THIRD state rather than `NOT_DETECTED`, because the two ask for different things: not_found
# is a photograph to look at, unfit is a detector that answered confidently and wrongly.
UNFIT_CROP = "unfit_crop"

# How many of the guard's refusals the preflight prints in full before it summarises. Enough
# to see the pattern — one bad frame reads as a card that moved, five in a row reads as the
# rig — and few enough that a box where the guard fires on everything cannot bury the
# figures above it.
UNFIT_CROPS_SHOWN = 5

# The refusal code for a card whose sidecar names a game outside the registry. Its
# siblings — `unwritten_prompt`, `unknown_strategy` — live in `identify/batch.py`, where
# the transport answers them; this one is the command's own, because the transport never
# sees a game, only a strategy, and a card with no registry entry has not even that.
UNKNOWN_GAME = "unknown_game"

# ------------------------------------------------------------------- the preflight stage
#
# WHERE A PHOTOGRAPH STOPPED BEFORE ANY MONEY WAS SPENT, and the sentinel that made the
# hash-first reorder safe. Read the reorder first, at the top of `run`.
#
# Until 2026-09-12 this command prepared EVERY photograph and then consulted the cache, so
# `prepared is None` carried two meanings at once that could not come apart: "this
# photograph could not be read" AND "there are no bytes to send for this card". Five loops
# tested it — the cache consult, the prompt refusal, the `to_send` filter, the `unreadable`
# roster, and the retry rounds — and a sixth site wrote `item.prepared.sha256` into the run
# payload.
#
# Hashing before preparing breaks that equivalence: a CACHE HIT is never prepared, so
# `prepared is None` would be true of it too, and every one of those six sites would then
# answer for the cards it exists to process — the `unreadable` roster in particular would
# name 464 healthy cards on the operator's own last press. That is the one failure mode
# `CLAUDE.md` forbids outright ("Never silently drop a card"), so the reorder does not ship
# with the old test reordered. It ships with this field.
#
# ONE FIELD, THREE CLAUSES RETIRED. The old send filter read
# `not i.cached and i.prepared is not None and i.status == "pending"` — not cached, readable,
# not refused. Those are the three ways out of the preflight and they are now three values
# of one field, which is why this is a simplification rather than a new concept.
#
# WHY NOT `Item.status`: that field is the MODEL's answer, or the transport's refusal to ask
# for one (`succeeded`, `errored`, `expired`, `malformed`, `unwritten_prompt`,
# `unknown_game`). It is written into `identifications.json` and read downstream. This field
# is this command's own account of how far a photograph got before a byte was submitted.
# They answer different questions, and nothing on the wire moves because of this one.
STAGE_PENDING = "pending"  # undecided; once the preflight is over, this IS the send list
STAGE_CACHED = "cached"  # the store already owns this answer — never prepared, never sent
STAGE_UNREADABLE = "unreadable"  # the bytes would not hash, or would not decode
STAGE_REFUSED = "refused"  # no prompt to read it with — named, not sent, not dropped


def _selection_from(args) -> selection_mod.Selection:
    """The CLI's spelling of one selection. `pipeline/selection.py` does every check.

    THE SAME OBJECT THE WIRE PARSES, AND THE SAME READER. `parse` validates a JSON payload and
    this validates argparse's output, and both end at `selection.check` — so a cross-term rule
    (a section needs a box; a box and an id are two answers to one question) holds on both
    surfaces because it is written once. Two validators agreeing by accident is the shape D43's
    port bug had.

    `--keys` IS REPEATABLE AND COMMA-SPLIT, which is one flag for both habits: `--keys 3/1,3/2`
    and `--keys 3/1 --keys 3/2` are the same selection. Splitting here rather than in the module
    keeps the wire's `keys` a plain array — a comma inside a JSON string would be a second
    encoding of a list that JSON can already express.
    """
    raw_keys = getattr(args, "keys", None)
    keys = None
    if raw_keys:
        keys = [
            part.strip()
            for chunk in raw_keys
            for part in str(chunk).split(",")
            if part.strip()
        ]
    return selection_mod.check(
        selection_mod.Selection(
            paths=tuple(str(p) for p in (getattr(args, "capture_dir", None) or ())),
            state=selection_mod._state_of(args.state) if getattr(args, "state", None) else None,
            box=_numbers(getattr(args, "box", None), "box"),
            bid=_numbers(getattr(args, "bid", None), "bid"),
            section=(
                selection_mod._positives(args.section, "section")[0]
                if getattr(args, "section", None)
                else None
            ),
            game=selection_mod._game_of(args.game) if getattr(args, "game", None) else None,
            since=selection_mod._since_of(args.since) if getattr(args, "since", None) else None,
            keys=selection_mod._keys_of(keys) if keys else None,
            run=selection_mod._run_of(args.run) if getattr(args, "run", None) else None,
        )
    )


def _numbers(raw, term: str):
    """`--box 3 --box 5` and `--box 3,5` are the same selection. One flag, both habits.

    SPLIT HERE AND NOT IN THE MODULE, for `--keys`' reason: the wire's `box` is a JSON array,
    and a comma inside a JSON string would be a second encoding of a list JSON can already
    express. The module takes the list; argparse's job is to produce one.
    """
    if not raw:
        return None
    values = [
        int(part.strip())
        for chunk in (raw if isinstance(raw, list) else [raw])
        for part in str(chunk).split(",")
        if part.strip()
    ]
    return selection_mod._positives(values, term) if values else None


def _run_keys_of(name: str, say) -> List[str]:
    """Every position key a run's own answers name. `--run <name>`'s reader.

    THE MANIFEST FIRST, AND `identifications.json` ONLY WHERE IT PREDATES `submitted`. A run
    written since 2026-09-12 carries its own key list in the manifest — a few hundred bytes —
    so this no longer has to open the (potentially megabyte-sized) identifications file just
    to answer "which keys". `Run.submitted` is `None` for an older run, and this falls back
    to the file exactly as it always did.

    A RUN WITH NO ANSWERS NAMES NO CARD, and it says so rather than selecting nothing in
    silence: `identifications.json` goes through `write_atomic`, so it is absent or whole, and
    absent means that run has not collected yet. Selecting zero cards from it would refuse one
    step later with the selection's own sentence, which blames the terms for a missing file.
    """
    try:
        run = runs.open_run(name)
    except Exception as exc:  # noqa: BLE001
        say(f"--run {name}: {exc}")
        return []
    submitted = run.submitted
    if submitted is not None:
        return sorted(submitted)
    try:
        payload = run.read_identifications()
    except Exception as exc:  # noqa: BLE001
        say(f"--run {name}: {exc}")
        return []
    cards = payload.get("cards")
    return sorted(cards) if isinstance(cards, dict) else []


def _recorded_dir(roots: Sequence[Path]) -> Optional[str]:
    """What goes in the manifest's `capture_dir`: the ONE root, or nothing.

    NEVER A JOINED STRING AND NEVER THE FIRST OF SEVERAL. `Run.capture_dir` is typed
    `Optional[Path]` and absence already means "this run does not say" to every reader of it;
    the first of three roots would be a path that looks authoritative and describes a third of
    the run. The full list is in the manifest's `selection` block, which is where a reader that
    wants all of them should look.

    IT HAS NO PYTHON READER LEFT. It was the input to `server/pipeline_routes.py:_run_box`'s
    path arm, which this entry deletes for being confidently wrong on two of this store's runs,
    and it is on the wire for a person to read.
    """
    return str(roots[0]) if len(roots) == 1 else None


def _default_label(selection: selection_mod.Selection, roots: Sequence[Path]) -> str:
    """What a run is CALLED when `--label` did not say. Still the directory name where there is one.

    A PATH KEEPS ITS BASENAME, which is what `capture_dir.name` gave every run before this and
    is what every run directory on this store is named after. A selection with no path is named
    for its narrowest term instead, and a press over everything is `store`. Nothing reads this
    back — `_run_box` reads the scope block and no longer parses a name — so it is a handle for
    a person and is allowed to be short.
    """
    if len(roots) == 1 and selection.paths:
        return roots[0].name
    if selection.box:
        return f"box{selection.box}"
    if selection.bid:
        return f"drawer{selection.bid}"
    if selection.run:
        return f"rerun-{selection.run}"
    if selection.game:
        return str(selection.game)
    if selection.state:
        return str(selection.state)
    if selection.keys:
        return f"cards{len(selection.keys)}"
    return "store"


def _scope_for(items: List["Item"], inventory: master.Inventory) -> Optional[dict]:
    """What this run is over, in the shape the screen's own press records — WITH THE BID.

    THE DERIVATION MOVED TO `pipeline/selection.py:scope_block` AND THIS IS THE ADAPTER. It was
    a second implementation of what `server/pipeline_routes.py` wrote for a pressed run, and the
    only thing holding the two together was a comment in each pointing at the other — T7's own
    assertion message says *"the shape `_resolve_scope` writes on the route"* about a call into
    this function. One derivation, two callers, and the agreement is structural now.

    THE CAPTURE DIRECTORY IS NO LONGER AN ARGUMENT, because `whole_box` no longer asks whether
    the run was pointed AT the drawer. Under a selection the path is the scan ROOT and the
    drawer is a filter, so `capture_dir == captures/cards/box3` stopped being answerable —
    `scope_block` counts instead: did this run read every photograph the drawer holds? That is
    the question the field has always meant, and it is right for a press over the store that
    swept up all of box 3 as well as for one aimed at it.

    THE BOX STILL COMES FROM THE SIDECARS AND NOT FROM THE PATH, and two boxes still get NO
    scope rather than a guessed one. That was D48's rule and it is the one part of that entry
    this change keeps: a scope block naming one of two drawers would be a claim about cards it
    is wrong about, and the run that produced this function — `2026-08-29-box1-01`, whose 99
    cards are all in box 3 — is what a guess costs.
    """
    return selection_mod.scope_block(
        [item.capture for item in items],
        home=store_files.home(),
        inventory=inventory,
    )


@dataclass
class Item:
    """One capture on its way through this command."""

    capture: sidecar.Capture
    prepared: Optional[images.Prepared] = None
    # WHERE THIS PHOTOGRAPH STOPPED IN THE PREFLIGHT — see the STAGE_* constants above for
    # why this exists and what `prepared is None` used to be asked to mean on its own.
    stage: str = STAGE_PENDING
    # THE DIGEST OF THE FILE ON DISK, CARRIED APART FROM `prepared`, and the reason is
    # `cli/resolve.py:1108`. D36's realign builds its `verifiable` map out of the run
    # payload's `photo_sha256` and drops every record without one into `blind` — a card it
    # can no longer re-bind to a slot. `prepared.sha256` was the only source for that field,
    # so hash-first would have written `None` for every cache hit and blinded 464 of the 678
    # records on the operator's last press. Hashing is now its own step, so the digest
    # belongs to the item and not to the bytes that were sent.
    #
    # It is `None` in exactly one case now, where it used to be `None` in two: a file whose
    # bytes could not be READ at all. A photograph that hashed and then failed to DECODE
    # keeps its digest, so `blind` is strictly smaller than it was.
    photo_sha256: Optional[str] = None
    error: Optional[str] = None
    cached: bool = False
    stale_prompt: bool = False
    identification: Optional[dict] = None
    # THE SAME ANSWER TWICE, AND BOTH ARE NEEDED. `identification` is the model's RAW
    # payload — what the cache stores, what the run's identifications.json records, and
    # therefore per-profile in shape (`number` for Pokemon, `printed_id` for misc, `code`
    # for a code card). `parsed` is that payload already read through the profile's own
    # parser by `identify/batch.py`, which is the ONE place the per-profile key mapping
    # lives — so everything downstream of collection that wants "the fields the record
    # carries" reads this and never re-implements a mapping per strategy. None whenever
    # `identification` is None, and ALSO for a cache hit, whose payload was parsed on the
    # run that paid for it and is not re-parsed on a run that did not.
    parsed: Optional[prompt.Identification] = None
    status: str = "pending"
    detection: str = NOT_ATTEMPTED
    retries: int = 0
    retry_reasons: List[str] = field(default_factory=list)
    # THE GAME THIS CARD IS PROCESSED AS, and its registry entry. `game` is D21's read-side
    # BACKFILLED key — `capture.game_or_default` — because this is a read and the backfill
    # belongs at the read; the run payload below still records the sidecar's RAW claim, so a
    # file that predates the field stays distinguishable from one that chose Pokemon.
    #
    # `entry` IS `None` FOR A GAME NOBODY REGISTERED, and that is a state rather than a
    # failure to tidy away. `identify/sidecar.py` deliberately keeps an unrecognised string
    # instead of dropping it — a dropped game reads as an absent one and backfills to
    # Pokemon — so this is where that string stops. Everything downstream branches on `entry
    # is None` and refuses by name.
    game: str = games.DEFAULT_GAME
    entry: Optional[dict] = None
    strategy: Optional[str] = None

    @property
    def key(self) -> str:
        return self.capture.key

    @property
    def confidence(self) -> Optional[str]:
        return (self.identification or {}).get("confidence")

    @property
    def weak(self) -> bool:
        return self.confidence == WEAK_CONFIDENCE


def _estimate(items: List[Item]) -> Decimal:
    total_input = 0
    for item in items:
        if item.prepared is None:
            continue
        width, height = item.prepared.sent_size
        total_input += int(Decimal(width * height) / PIXELS_PER_TOKEN) + SYSTEM_TOKENS
    # QUANTIZED HERE AND NOT IN `cost.usd`, so the printed line is unchanged to the byte:
    # `server/pipeline_routes.py:_ESTIMATE` is a regex over `^estimated cost\s+\$([0-9.]+)$`
    # and `app/tests/run-panel.spec.ts`'s fixture is that exact layout.
    return cost.usd(total_input, OUTPUT_TOKENS * len(items)).quantize(Decimal("0.01"))


def _custom_id(key: str) -> str:
    """The store's key, translated for the Batch API's `custom_id` — and ONLY for it.

    The API enforces `^[a-zA-Z0-9_-]{1,64}$`, and the store's position key is `box/index`
    (`sidecar.py:key`), so the very first real submission this repo ever made — Gate B,
    2026-08-22, 53 captures — was refused whole for the slash. T1 never saw it: eval ids
    are hyphenated card ids, and the shakedown stopped at `--dry-run`, which builds
    everything and submits nothing.

    Translate at this seam rather than change the key: `3/7` is load-bearing in the
    store, the cache, the queues and the join. The encoding is deterministic, so a
    resumed run recomputes the same ids it submitted (RESUME BEATS RESUBMIT above), and
    `_apply`'s lookup dict is built through this same function, so nothing ever decodes.
    Illegal characters become `-xx-` hex; a result over the API's 64-char cap — reachable
    only through the `file:` fallback key, never through a position — keeps its head and
    takes a digest tail, trading reversibility nothing needs for uniqueness the batch
    does."""
    safe = "".join(
        ch if (ch.isascii() and ch.isalnum()) or ch in "_-" else f"-{ord(ch):02x}-"
        for ch in key
    )
    if len(safe) > 64:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        safe = safe[:48] + digest
    return safe


def _requests(items: List[Item], with_crops: bool, say) -> List[batch.ImageRequest]:
    """Batch requests for the items that still need sending, each under its own strategy.

    An item with no strategy at all — an unregistered game — is never built into a
    request: the refusal loop in `run` has already named it `unknown_game`, and a request
    without a real strategy could only be submitted under some other game's prompt.

    THE `prepared is None` TEST HERE IS NOT `Item.stage`'S BUSINESS and is deliberately
    left alone. This function is handed the list it is to build requests for, so it is
    asserting its CALLER's contract — every item in `to_send` was prepared by the pass that
    produced it — rather than asking where a photograph got to. `_estimate` is the same
    shape for the same reason. Both would be wrong to read `stage`: an item is not
    excluded from a batch because of where it stopped, it is excluded because it was never
    handed here.
    """
    out: List[batch.ImageRequest] = []
    for item in items:
        if item.prepared is None or item.strategy is None:
            continue
        regions: List[batch.Attachment] = []
        if with_crops:
            regions = _crop_attachments(item, say)
        out.append(
            batch.ImageRequest(
                custom_id=_custom_id(item.key),
                media_type=item.prepared.media_type,
                data_b64=item.prepared.data_b64,
                set_hint=item.capture.set_hint,
                # D23's stack claim is DELIBERATELY NOT SENT TO THE MODEL. The claim still
                # does jobs 1 and 2 — the ladder cross-check reads it off the sidecar and
                # the capture screen narrows chips with it — but the prompt clause (job c)
                # was measured on 2026-08-23 with best-case claims (each card's true rarity,
                # $0.17, harness/results/t1-rarity.json) and it LOST on every axis the
                # Someday entry said to watch: holdout 0.9706 -> 0.9559, high-confidence
                # misses 5 -> 7, and the finish distribution hardened (unknown 27 -> 5)
                # against the carve-out sentence telling it not to — which is rung 3's one
                # signal being made more decisive exactly when it is wrong. Re-enable by
                # passing `rarity_claim=item.capture.rarity_claim` here, and only with a
                # rig-photo measurement that says otherwise; PKMNSCAN_T1_RARITY=1 is the
                # instrument.
                rarity_claim=None,
                regions=regions,
                strategy=item.strategy,
            )
        )
    return out


def _crop_attachments(item: Item, say) -> List[batch.Attachment]:
    """Enlarged bands for a crop retry, or none when the card cannot be found.

    None is a real answer here, not a degraded one: §4.5 rung 3 says a card that cannot be
    located goes to a human rather than being cropped on a guess.

    THE TWO REGISTRY FIELDS THIS FUNCTION EXISTS TO READ, wired 2026-08-23. Both were
    authored, audited and consumed by nobody, while this function asked the geometry package
    for whatever it decided on its own:

      card_aspect   the shape `detect_card` gates on. It defaulted to the detector's own
                    63x88mm constant, which is right for all four catalogued games and is
                    `None` for `misc` — a population printed at two different sizes. `None`
                    raises `UnknownCardShape`, caught below with every other `GeometryError`,
                    so a misc card gets no crop retry and goes to a human. That is the
                    cheapest possible refusal: the card is being handled by hand anyway.
      crop_bands    which bands to cut. `None` meant "all of them", so `pokemon_code`,
                    `riftbound`, `one_piece` and `misc` — every one of which claims NO bands,
                    because nobody has measured where those cards print a title or a number —
                    would have had Pokemon's rectangles cut over them and sent as evidence.
    """
    if item.entry is None:
        item.detection = NOT_DETECTED
        say(
            f"  {item.key}: game {item.game!r} is not in the registry — no shape to detect "
            f"with and no bands to cut, so no crop retry. Fix the sidecar's `game`."
        )
        return []

    bands = tuple(item.entry["crop_bands"])
    try:
        box = geometry.detect_card(item.capture.photo, aspect=item.entry["card_aspect"])
    except geometry.GeometryError as exc:
        item.detection = NOT_DETECTED
        say(f"  {item.key}: detection unavailable — {exc}")
        return []

    if box is None:
        item.detection = NOT_DETECTED
        say(f"  {item.key}: card not found in the frame — no crop retry")
        return []

    # THE SAME GUARD THE FIRST READING USES, over the same box, for a sharper reason. A retry
    # is what happens after a reading came back malformed or unsure, and the bands it attaches
    # are cut out of THIS rectangle — so a box that is really the card's rules-text panel
    # sends an enlarged picture of the rules text and calls it the collector number. That is
    # the retry answering confidently about nothing, which §4.5 rung 3 sends to a human
    # instead.
    try:
        unfit = images.crop_refusal(
            item.capture.photo, box, aspect=item.entry["card_aspect"]
        )
    except images.ImageError as exc:
        unfit = f"the photograph could not be re-read to check the crop — {exc}"
    if unfit is not None:
        item.detection = UNFIT_CROP
        say(f"  {item.key}: the detected box is not the card — {unfit} No crop retry.")
        return []

    item.detection = DETECTED
    regions = geometry.crop_regions(
        item.capture.photo, box, bands=bands, aspect=item.entry["card_aspect"]
    )
    attachments = []
    # The registered card first and then the game's own bands, in the registry's order. For
    # `pokemon` that is card, title, number — byte-identical to the fixed triple this loop
    # used to walk, which is why nothing about a Pokemon retry moves.
    for name in (geometry.REGION_CARD,) + bands:
        region = regions.get(name)
        if region is None:
            continue
        prepared = images.prepare_region(region)
        attachments.append(
            batch.Attachment(
                media_type=prepared.media_type, data_b64=prepared.data_b64
            )
        )
    return attachments


def _attach_registry(item: Item) -> None:
    """Resolve the card's game to its registry entry, once, before anything reads a field.

    NEVER COERCED AND NEVER DEFAULTED PAST THE BACKFILL. `games.get` raises rather than
    handing back Pokemon, which is the one outcome D21 spends a paragraph forbidding — so an
    unregistered string leaves `entry` as None and every reader below refuses by name. The
    sidecar has already recorded the same string as a `problem`, and the preflight prints the
    count, so the card is visible three times before a byte is submitted.
    """
    item.game = item.capture.game_or_default
    try:
        item.entry = games.get(item.game)
    except games.UnknownGame:
        item.entry = None
        item.strategy = None
        return
    item.strategy = str(item.entry["prompt"])


def _game_lines(items: List[Item]) -> List[str]:
    """The per-game preflight block: what each group is, and what will be done to it.

    WORTH ITS SIX LINES BECAUSE THIS COMMAND IS THE ONE THAT SPENDS MONEY, and until now its
    preflight could not tell a box of Pokemon from a box of Yu-Gi-Oh. D21 makes mixed boxes
    legal on purpose; a preflight that prints one card count for a mixed directory is
    reporting on a run it has not actually described.
    """
    grouped: Dict[str, List[Item]] = {}
    for item in items:
        grouped.setdefault(item.game, []).append(item)

    lines = []
    for game in sorted(grouped):
        group = grouped[game]
        entry = group[0].entry
        if entry is None:
            lines.append(
                f"  {game:<14} {len(group):>4}  NOT IN THE REGISTRY — no prompt, no card "
                f"shape, no catalog. Fix the sidecar's `game`."
            )
            continue
        bands = ",".join(entry["crop_bands"]) or "none"
        aspect = entry["card_aspect"]
        lines.append(
            f"  {game:<14} {len(group):>4}  prompt={entry['prompt']} "
            f"aspect={'none' if aspect is None else aspect} bands={bands} "
            f"{'joins a catalog' if entry['catalogued'] else 'never joins'}"
        )
    return lines


def _apply(items_by_key: Dict[str, Item], run_result: batch.BatchRun) -> None:
    for key, outcome in run_result.outcomes.items():
        item = items_by_key.get(key)
        if item is None:
            continue
        item.status = outcome.status
        if outcome.identification is not None:
            item.identification = dict(outcome.identification.raw)
            item.parsed = outcome.identification
        else:
            item.error = outcome.error


def _needs_retry(item: Item):
    """(retry?, crop?, reason). Crop retry is for a bad READ; plain retry is for no read."""
    if item.status in PLAIN_RETRY_STATUSES:
        return True, False, item.status
    if item.status in CROP_RETRY_STATUSES:
        return True, True, item.status
    if item.identification is not None and item.weak:
        return True, True, "low_confidence"
    return False, False, ""


# ---------------------------------------------------------------- the code ledger (C8)

# The registry key for the one game whose identifications are transcribed codes. A
# LITERAL, not read off some entry attribute, because "which game feeds the code ledger"
# is C8's own ruling rather than a property any registry field carries — the same way
# `pipeline/games.DEFAULT_GAME` names Pokemon by its key.
CODE_GAME = "pokemon_code"


def _code_ledger_lines(items: List[Item], run_name: str, captured_at_of):
    """(lines, skipped): one C8 ledger line per code card this run holds a code for.

    THE LINE IS THE DISPUTE FLOW'S INDEX ENTRY — code text beside the position its
    photograph is keyed by — so a line is written exactly when there is a code to look up:

      - a code card with no position is already a named failure (`no_position`, main
        queue); there is no key to file its line under, and it is not silently dropped —
        it is loudly queued, which is the stronger guarantee.
      - an empty transcription is a card the model saw no code on. Nothing to look a
        dispute up by, so no index entry; the empty read still stands in the run payload
        and on the record like any other, and `skipped` names the position.
      - a CACHED code card is included: its answer was paid for on an earlier run, and
        re-upserting the same line is idempotent while also healing a ledger file that
        was lost — `inventory/` is never in git, so nothing else would re-create it. The
        cached payload is parsed here under the card's own strategy; one that no longer
        parses (a profile's schema moved under it) is skipped BY NAME rather than
        guessed at, and re-identifying it is the remedy.

    `captured_at` comes off the store record rather than the sidecar, because the record
    is where capture time has lived since the server first stamped it and this function
    runs inside the same locked session that just upserted the record.
    """
    lines: List[dict] = []
    skipped: List[str] = []
    for item in items:
        if item.game != CODE_GAME or item.identification is None:
            continue
        if not item.capture.has_position:
            skipped.append(f"{item.capture.photo.name}: no position to key the line by")
            continue
        parsed = item.parsed
        if parsed is None:
            try:
                parsed = prompt.parse(
                    item.identification, item.strategy or prompt.DEFAULT_PROFILE
                )
            except (prompt.MalformedIdentification, LookupError) as exc:
                skipped.append(f"{item.key}: cached answer does not parse — {exc}")
                continue
        if not parsed.number:
            skipped.append(f"{item.key}: the model read no code off this card")
            continue
        lines.append(
            {
                "box": item.capture.box,
                "index": item.capture.index,
                "code": parsed.number,
                "name": parsed.name or None,
                "photo": str(item.capture.photo),
                "set_hint": item.capture.set_hint,
                "captured_at": captured_at_of(item.key),
                "confidence": parsed.confidence,
                "run": run_name,
            }
        )
    return lines, skipped


def _adopt_cached(item: Item, entry, fingerprints: Dict[str, str]) -> None:
    """Take an answer the store already owns onto this item. NOT a cache read — the caller did
    that and hands the entry in.

    IT IS A FUNCTION BECAUSE IT HAS TWO CALLERS, and the second one is the reason the first was
    extracted (D174). The consult pass below reads the cache once, minutes
    and thousands of file reads before the claim is written; `claim_or_refuse` reads it AGAIN
    inside the transaction it writes the claim in, and a key that became a hit in between is
    dropped from the claim. A card dropped there would otherwise be submitted with nothing
    holding it, and reporting it as a failure instead would be an `identification_failed` queue
    entry for a card whose answer is sitting in the store. So the narrowing adopts the answer,
    through this, and the two paths cannot drift.

    `parsed` IS LEFT None ON PURPOSE, which is `Item.parsed`'s own rule: a cache hit's payload
    was parsed on the run that paid for it and is not re-parsed on a run that did not.
    """
    item.cached = True
    item.stage = STAGE_CACHED
    item.identification = dict(entry.identification)
    item.status = batch.SUCCEEDED
    expected = fingerprints.get(item.strategy)
    item.stale_prompt = expected is not None and entry.prompt_fingerprint != expected


def _give_back_unspent(claim, run_dir, store, say) -> bool:
    """Release this run's claim IF it can be proved nothing was submitted. Returns whether it did.

    THE ONE PLACE A CLAIM IS RELEASED WITHOUT ITS ANSWERS BEING BANKED, and it is safe for
    exactly one reason: `run_dir.batch_ids` is empty. `batch.run_batch` records every batch id
    through `on_submit` AS IT SUBMITS, so no id means no chunk ever reached the API and there is
    nothing in flight to collect. An empty id list is proof of an unspent press in a way a
    caught exception is not.

    WHY THIS IS NOT A `finally`. A submission that fails PART WAY through has ids recorded and
    batches paid for, keeping for 29 days — so the exception alone cannot tell an unspent press
    from a half-spent one, and releasing on the exception would hand the operator a green button
    over an invoice already rung up. The ids can.

    WHAT IT IS FOR is the ordinary self-inflicted failure: a missing or bad API key, on the
    first press of a fresh checkout. Without it, that press leaves a drawer's worth of cards
    claimed by a run that spent nothing, and every later press is refused until somebody goes
    and releases it on `#/runs` — a stuck claim earned by a typo in `.env`.
    """
    if claim is None:
        return False
    if run_dir.batch_ids:
        # Something WAS submitted. The claim stands, and the run is resumable — which is the
        # case `--run-dir` exists for, and `claim_or_refuse`'s `resuming` lets it re-claim.
        say(
            f"claim           {len(claim.keys)} card(s) STAY held under {claim.receipt}: "
            f"{len(run_dir.batch_ids)} batch(es) were submitted and are not collected. "
            f"Resume with --run-dir {run_dir.directory}, or release the claim on #/runs."
        )
        return False
    with store.write() as giving:
        freed = giving.submissions.release(claim.receipt, submissions.BY_RUN)
    say(
        f"claim           {len(claim.keys)} card(s) released ({claim.receipt}) — no batch was "
        f"submitted, so nothing was spent and nothing is being held"
    )
    return freed is not None


def _read_disputes_for(writable, key: str, read_name) -> Optional[bool]:
    """`read_disputes` for one `record_identification` call
    (docs/specs/identity-follows-sku.md §4.1, §4.2: "On a SKU-bound card the identity stays,
    and the caller recomputes read_disputes") — `record_identification` cannot compute this
    itself, because `store/` imports neither `pipeline/join` nor `pipeline/games` (D63).

    `None` — LEAVE THE STORED FLAG ALONE — for a card with no binding yet: there is no SKU
    row to compare the fresh read against, and `record_identification`'s own docstring is
    explicit that a caller with no fresh answer must not overwrite a real flag with a stale
    `False`. A BOUND card is checked against its own SKU row's `raw` payload
    (`store/skus.py:SkuRow.raw` — "the WHOLE CSV row, verbatim", the one
    `tcgcsv.Row`-shaped thing this table keeps), never against an export file — the same
    rule `bind_sku` itself follows (§3.2: "READS THE SKU'S ROW FROM `skus`... NEVER FROM AN
    EXPORT FILE").

    Pulled out of the write loop so it is a function with an answer, not a fact only provable
    by running the whole batch-collect machinery — `scripts/identity-cli-selftest.py` calls
    it directly, on a plain `Inventory`/`Skus` pair, the way
    `scripts/identity-store-selftest.py` proves `bind_sku` itself.
    """
    card = writable.inventory.cards.get(key)
    if card is None or card.identity_source != master.IDENTITY_SKU or not card.sku:
        return None
    row = writable.skus.entries.get(str(card.sku))
    if row is None:
        return None
    return join.name_disputes(read_name, [row.raw])


def run(args, say) -> int:
    store = Store()

    # ------------------------------------------------------ WHICH CARDS, BEFORE ANY OTHER WORK
    #
    # THE SELECTION IS RESOLVED FIRST AND EVERY LATER PASS WALKS WHAT IT LEFT, which is the
    # whole point of doing it here rather than anywhere more convenient. `--box 3` over the
    # store's own capture root scans 2,535 photographs and narrows to 678 — and the passes
    # below are the expensive ones: hashing is 0.687 ms per photograph and crop-and-prepare is
    # 114.96 ms (D163's measurements). A filter applied after the hash loop would scan the same
    # files and hash 1,857 of them for nothing; a filter applied after the prepare pass would
    # be three and a half minutes of nothing. D163 is the same lesson one step down.
    try:
        selection = _selection_from(args)
    except selection_mod.SelectionError as exc:
        say(f"refused: {exc}")
        return 1
    if not selection.named and not getattr(args, "all", False):
        # THE TERMINAL DEFAULT IS REFUSE-AND-NAME-THE-FLAG, and the route's is not, which is
        # argued in `Selection.named`. `./pkmnscan identify "$DIR"` with `$DIR` unset used to be
        # an argparse error; under a list positional it is an empty selection, and the one thing
        # this change must not do quietly is turn that typo into a paid store-wide submission.
        say("refused: this names no cards. Give a path, a selection flag, or `--all`.")
        say("         `--all` is every photograph in the store and is a word you type.")
        return 1

    roots = selection.roots(store_files.home())
    captures = []
    for root in roots:
        try:
            captures += sidecar.scan(
                root,
                box=getattr(args, "assume_box", None),
                variant_default=getattr(args, "variant", None),
            )
        except FileNotFoundError:
            say(f"no capture directory at {root}")
            return 1
    scanned = len(captures)

    inventory = None
    if selection.needs_store:
        # ONE SNAPSHOT FOR THE FILTER, and a second one is taken after the hash pass for the
        # cache — deliberately, rather than reusing this. The cache consult must see the store
        # as it is when the send list is decided, and `Inventory.in_state` here is a full-table
        # pass that a drawer press never pays at all (`needs_store` is four terms, and `box`,
        # `game` and `keys` are none of them).
        inventory = store.read().inventory
    try:
        captures = selection_mod.narrow(
            selection,
            captures,
            inventory=inventory,
            run_keys=lambda name: _run_keys_of(name, say),
        )
    except selection_mod.SelectionError as exc:
        say(f"refused: {exc}")
        return 1

    if not captures:
        try:
            selection_mod.refuse_empty(selection, scanned)
        except selection_mod.SelectionError as exc:
            say(f"{exc}")
        return 1

    items = [Item(capture=capture) for capture in captures]

    # ------------------------------------------------------- HASH, THEN CACHE, THEN PREPARE
    #
    # THE ORDER IS THE POINT, and it was the other way round until 2026-09-12. This loop used
    # to run `geometry.detect_card` and `images.prepare` over every photograph in the
    # directory, and the cache was consulted afterwards — so the decode was pure waste on
    # every card the store already owned an answer for.
    #
    # `store.cache.reusable(key, photo_sha256)` needs the DIGEST and nothing else, and
    # `images.prepare` computed that digest before opening the image anyway. So the decode
    # was never an input to the question being asked.
    #
    # MEASURED ON THIS MACHINE, box 4's own 678 JPEGs at the operator's flags
    # (`--crop --max-edge 1200`), page cache warm for both so neither gets the cold-read
    # penalty: 114.96 ms per photograph to crop+prepare against 0.687 ms to hash. 167x.
    # That press walked 678 photographs and submitted 214, and it walked them TWICE, because
    # `server/pipeline_routes.py:_preflight_leg` shells `identify --dry-run` first. One leg
    # of it took 79 s before this change and 26 s after; hashing all 2,535 photographs in
    # the store — 4.4 GB — takes 2.89 s.
    #
    # A PHOTOGRAPH THAT HASHES IS NOT YET A PHOTOGRAPH THAT DECODES, which is why the send
    # list is re-filtered after the prepare pass below: `sha256_of` proves the bytes can be
    # read, never that they are an image.
    for item in items:
        _attach_registry(item)
        try:
            item.photo_sha256 = images.sha256_of(item.capture.photo)
        except OSError as exc:
            # THE BYTES COULD NOT BE READ AT ALL — a deleted file, a bad permission, a
            # disconnected volume. This used to reach the operator as a bare OSError out of
            # `images.prepare`, which calls `sha256_of` OUTSIDE its own try, so the command
            # died on the first such file and said nothing about the other 677. Now it is a
            # named failure bound for the main queue, like every other one here.
            item.error = f"{item.capture.photo}: {exc}"
            item.status = "unreadable"
            item.stage = STAGE_UNREADABLE

    # ------------------------------------------------------------------ consult the cache
    snapshot = store.read()
    # ONE FINGERPRINT PER PROFILE, LOOKED UP BY EACH CARD'S OWN STRATEGY. Both halves of
    # the paragraph that stood here moved together, as it said they must: the transport
    # carries a strategy per request now, so the cache is judged per profile too — every
    # comparison and every write below uses the hash of the profile that reads THAT card,
    # because a misc answer measured against Pokemon's contract is stale forever against a
    # prompt it was never read with. `fingerprint` alone stays run-wide: the DEFAULT
    # profile's hash, the manifest's and the report's headline, and the recorded contract
    # for the one answer that can arrive for a card without a strategy of its own (see the
    # cache write). A strategy the dispatch refuses has no hash here — nothing is
    # submitted under it, so there is no contract to record.
    fingerprint = prompt.prompt_fingerprint()
    fingerprints: Dict[str, str] = {}
    for item in items:
        if item.strategy is None or item.strategy in fingerprints:
            continue
        try:
            fingerprints[item.strategy] = prompt.prompt_fingerprint(item.strategy)
        except LookupError:  # unwritten or unregistered — refused below, never hashed
            continue
    queued = set(snapshot.review.entries) | set(snapshot.parked.entries)
    current_by_key = {
        item.key: fingerprints[item.strategy]
        for item in items
        if item.strategy in fingerprints
    }
    stale_targets = (
        set(snapshot.cache.weak_and_uncleared(current_by_key, queued))
        if args.reidentify_stale
        else set()
    )

    for item in items:
        # THE DIGEST, NOT THE PREPARED BYTES. This read `item.prepared.sha256` and skipped on
        # `prepared is None`; under hash-first that test would have skipped every card whose
        # answer the store already owns, which is exactly the set this loop exists to find.
        if item.photo_sha256 is None:
            continue
        entry = snapshot.cache.reusable(item.key, item.photo_sha256)
        if entry is None:
            continue
        if item.key in stale_targets:
            item.retry_reasons.append("reidentify-stale")
            continue
        _adopt_cached(item, entry, fingerprints)

    # A CARD NOBODY HAS A PROMPT FOR IS REFUSED HERE, BEFORE IT COSTS ANYTHING — the same
    # refusal, in the same words, that `identify/batch.py` would answer at submission. In
    # the preflight rather than left to the transport so that `--dry-run` shows it, and so
    # `to send` and the cost estimate count only what will actually be submitted. A
    # refused card keeps the NOTHING IS EVER SKIPPED property: it leaves this command as a
    # named failure bound for the main queue, never dropped — and never read with another
    # game's prompt (D21). A cached answer is left standing: already paid for, and refusing
    # it would answer a question about submission on a card that is not being submitted.
    for item in items:
        # STILL UNDECIDED ONLY — one clause where there were two. `cached or prepared is
        # None` meant "not a cache hit, and readable"; a card refused here is now refused
        # BEFORE it is prepared, so it costs no decode either.
        if item.stage != STAGE_PENDING:
            continue
        if item.strategy is None:
            item.status = UNKNOWN_GAME
            item.stage = STAGE_REFUSED
            item.error = (
                f"game {item.game!r} is not in the registry — no prompt to read it with. "
                f"Fix the sidecar's `game`."
            )
            continue
        refusal = batch.prompt_refusal(_custom_id(item.key), item.strategy)
        if refusal is not None:
            item.status = refusal.status
            item.stage = STAGE_REFUSED
            item.error = refusal.error

    # ------------------------------------------------------------- prepare what is going
    #
    # THE ONLY PHOTOGRAPHS THAT ARE DECODED, and the whole saving. Everything above answered
    # from the digest, so what is left is the cards this run is actually paying to read.
    #
    # THE CROP COUNTERS MOVED WITH IT, DELIBERATELY, AND THEIR DENOMINATOR IS ON THE LINE.
    # They used to run over every photograph in the directory because every photograph was
    # prepared; they now run over the send list, because a crop that is never made is not a
    # crop. That is the same rule the counters were already written to — "COUNTED OFF WHAT
    # WAS ACTUALLY MADE, not off what was asked for" — carried one step further. The
    # preflight line below therefore says `of the N being sent` in so many words: a counter
    # whose denominator changed without a sentence is how a published measurement rots.
    cropped = 0
    unfit: List[Item] = []
    for item in items:
        if item.stage != STAGE_PENDING:
            continue
        try:
            # CROP TO THE DETECTED CARD BEFORE THE DOWNSCALE, when asked for. Local, free and
            # deterministic — `geometry.detect_card` is the same border search T6 covers and
            # Gate B's photographs proved, with no model call and no network.
            #
            # A REFUSAL FALLS BACK TO THE WHOLE FRAME rather than failing the card. Detection
            # answers `None` when it cannot find a card (T6: "'Not found' must be a refusal,
            # never a guess"), and the honest response to that is to send what we always sent
            # — the run costs a little more and reads exactly as it would have.
            box = None
            if args.crop:
                try:
                    box = geometry.detect_card(item.capture.photo)
                except Exception:
                    box = None
            item.prepared = images.prepare(
                item.capture.photo, max_edge=args.max_edge, crop_box=box
            )
            # COUNTED OFF WHAT WAS ACTUALLY MADE, not off what was asked for. `prepare`
            # applies `images.crop_refusal` and can decline a box detection did return —
            # a rectangle inside the card, which crops the collector number away — so a
            # counter incremented beside `detect_card` above would report a crop that
            # never happened. Three outcomes, and the preflight names all three.
            if box is not None:
                if item.prepared.crop_refused is None:
                    cropped += 1
                else:
                    unfit.append(item)
        except images.ImageError as exc:
            # HASHED AND STILL UNREADABLE. The bytes were there to digest and are not an
            # image the decoder will take — a truncated write, a renamed non-image. The
            # digest it already carries stays on the record, which is why this card is no
            # longer `blind` to D36's realign the way it was before the reorder.
            item.error = str(exc)
            item.status = "unreadable"
            item.stage = STAGE_UNREADABLE

    # ONE FIELD, AFTER THE PREPARE PASS. A card that failed to decode has just left
    # `STAGE_PENDING`, so this filter must be read here and not before it.
    to_send = [i for i in items if i.stage == STAGE_PENDING]
    unreadable = [i for i in items if i.stage == STAGE_UNREADABLE]
    no_position = [i for i in items if not i.capture.has_position]

    # ------------------------------------------------------------------------ preflight
    payload_bytes = sum(i.prepared.payload_bytes for i in to_send if i.prepared)
    chunks = max(1, -(-len(to_send) // batch.MAX_REQUESTS_PER_BATCH))
    say("")
    # WHAT THIS PRESS IS OVER, IN THE SENTENCE EVERY OTHER SITE USES. It said `capture dir` and
    # one path, which under a selection would be the scan root — `captures/cards` for a press
    # over box 3 — and therefore the least informative true line available. The sentence is
    # `Selection.sentence`, composed once so the report, the refusals and the screen cannot
    # describe one press three ways. `scanned` beside it is what the terms narrowed FROM, which
    # is the figure that says whether a selection did any narrowing at all.
    say(f"selection       {selection.sentence()}")
    if scanned != len(items):
        say(f"scanned         {scanned} photograph(s), narrowed to {len(items)}")
    say(f"photographs     {len(items)}")
    # COUNTED, NOT SUBTRACTED, and that is a repair the sentinel paid for. This read
    # `len(items) - len(to_send) - len(unreadable)`, and a card refused for want of a prompt
    # is neither of those — so every `unknown_game` and `unwritten_prompt` card in a
    # directory was reported to the operator as a CACHE HIT, on the one line they read to
    # decide whether the run is worth paying for. There is now a value that means cache hit.
    say(f"cache hits      {len([i for i in items if i.stage == STAGE_CACHED])}")
    say(f"to send         {len(to_send)}")
    say(f"payload         {payload_bytes / 1_000_000:.1f} MB in {chunks} batch chunk(s)")
    say(f"estimated cost  ${_estimate(to_send)}")
    if args.crop:
        # NAMED IN THE PREFLIGHT because it changes the bytes, and the preflight's whole job
        # is to say what is about to be sent. A refusal count of anything but zero is worth
        # seeing before spending: it means some cards are going as whole frames at whole-frame
        # cost, which is safe but is not what was asked for.
        #
        # TWO KINDS OF REFUSAL, AND THEY ARE NOT THE SAME FACT. Detection refusing means no
        # card was found in the frame and the operator should look at the photograph. The
        # guard refusing means a card WAS found and the box was not fit to cut to — a
        # rectangle inside the card, which is a detector finding rather than a rig one. A
        # single "sent whole" figure covering both would point at the wrong thing.
        #
        # THE DENOMINATOR IS THE SEND LIST AND THE LINE SAYS SO. It was every photograph in
        # the directory until 2026-09-12, because every photograph was prepared; hash-first
        # prepares only what is going, so these three figures now sum to `to send` and not to
        # `photographs`. The phrase `of the N being sent` is on the line rather than in a
        # comment on purpose — this is the figure an operator reads while deciding to spend,
        # and a denominator that changed silently is a published measurement rotting.
        not_found = len(to_send) - cropped - len(unfit)
        say(f"crop            to the detected card +{images.CROP_PAD*100:.0f}% "
            f"— {cropped} cropped of the {len(to_send)} being sent"
            + (f", {not_found} sent whole (no card found)" if not_found else "")
            + (f", {len(unfit)} sent whole (box unfit to crop to)" if unfit else ""))
        # THE REASON, PER CARD, BEFORE ANY MONEY. `crop_refusal` writes a sentence rather
        # than a flag precisely so it can be read here; a count alone would tell the operator
        # that something was refused and nothing about what to do next.
        for item in unfit[:UNFIT_CROPS_SHOWN]:
            say(f"                {item.key}: {item.prepared.crop_refused}")
        if len(unfit) > UNFIT_CROPS_SHOWN:
            say(f"                and {len(unfit) - UNFIT_CROPS_SHOWN} more like it")
    say(
        f"prompt          {fingerprint}  (crop retry {prompt.retry_fingerprint()}, "
        f"rarity clause {prompt.rarity_fingerprint()})"
    )
    for name in sorted(fingerprints):
        if name != prompt.DEFAULT_PROFILE:
            say(f"                {fingerprints[name]}  ({name})")
    say(f"model           {prompt.MODEL}")
    say("games")
    for line in _game_lines(items):
        say(line)

    # THE REFUSALS, ON SCREEN BEFORE ANY MONEY — standing where the `prompt mismatch`
    # warning stood until 2026-08-23, the day `ImageRequest` grew a strategy and the
    # comparison that warning printed stopped being true, which is how it promised to
    # retire. Two codes, two remedies, and the closing report counts every one of them
    # among the failures bound for the main queue: refused is not dropped.
    refused = [
        i
        for i in items
        if i.status in (batch.UNWRITTEN_PROMPT, batch.UNKNOWN_STRATEGY)
    ]
    unregistered = [i for i in items if i.status == UNKNOWN_GAME]
    if refused:
        names = ", ".join(sorted({str(i.strategy) for i in refused}))
        say(
            f"no prompt       {len(refused)} card(s) name {names}, which no profile in "
            f"identify/prompt.py answers — refused by name, NOT sent, NOT dropped. Write "
            f"the prompt, or fix the sidecar's `game`."
        )
    if unregistered:
        say(
            f"unknown game    {len(unregistered)} card(s) name a game not in the registry "
            f"— refused as {UNKNOWN_GAME}, NOT sent, NOT dropped. Fix the sidecar's `game`."
        )
    if unreadable:
        say(f"unreadable      {len(unreadable)} — these are NOT sent and NOT dropped:")
        for item in unreadable:
            say(f"                  {item.capture.photo.name}: {item.error}")
    if no_position:
        say(f"no position     {len(no_position)} -> main review queue, flagged no_position")
    recovered = [i for i in items if i.capture.source == sidecar.FROM_FILENAME]
    if recovered:
        say(f"position from filename: {len(recovered)}")
    claimed = [i for i in items if i.capture.rarity_claim]
    if claimed:
        # THIS LINE SAID "in the user turn" AND THAT STOPPED BEING TRUE the day the clause was
        # switched off. The preflight exists to say what a run is about to send before it
        # costs anything, so a stale sentence here is worse than no sentence: it describes
        # spending that is not happening, in the one place a reader checks precisely because
        # they are deciding whether to spend.
        #
        # What is true now: the claim is on the card, it is NOT in the prompt (see
        # `rarity_claim=None` above and the measurement cited there), and it still does its
        # other two jobs — the ladder cross-check at join time, and the chip narrowing on the
        # capture screen. Both happen without the model ever seeing it.
        say(
            f"rarity claims   {len(claimed)} card(s) carry a stack claim — NOT sent to the "
            f"model (measured and switched off); used by the ladder cross-check at join"
        )
    if getattr(args, "variant", None):
        flagged = [i for i in items if i.capture.variant_from_flag]
        kept = [
            i
            for i in items
            if i.capture.metadata_finish is not None and not i.capture.variant_from_flag
        ]
        say(
            f"--variant        {args.variant}: filled {len(flagged)} card(s) with no "
            f"recorded toggle; left {len(kept)} recorded toggle(s) alone"
        )
    say(f"store           {snapshot.queue_summary}")
    say("")

    if args.dry_run:
        say("--dry-run: nothing submitted, nothing written.")
        return 0

    # ------------------------------------------------------- claim what is about to be bought
    #
    # THE LAST FREE ACT BEFORE THE MONEY, AND THE ONLY THING THAT STOPS A DOUBLE INVOICE
    # (D174). Everything above this line is reads and decodes; everything below it can spend.
    # It is now the ONLY guard of any kind: `server/pipeline_routes.py:_busy_run` compared BOX
    # numbers, there is no longer a box on that route to compare, and a press over a pile
    # spanning two drawers was invisible to it in both directions anyway. Keyed by the cards
    # rather than by the drawer, in the one command every press goes through — the screen's, a
    # terminal's and an agent's.
    #
    # THE CHECK AND THE WRITE ARE ONE TRANSACTION AND THE SEND LIST IS RECOMPUTED INSIDE IT.
    # `to_send` was decided by the consult pass above, against a snapshot read before the
    # prepare pass — on 678 photographs that is a minute of decoding ago. Two presses can both
    # reach here believing they are first, so the intersection is computed against claims read
    # under the lock and the row is written before it is released. See `store/submissions.py`.
    claim = None
    if to_send:
        with store.write() as claiming:
            claim, conflicts = claiming.submissions.claim_or_refuse(
                {item.key: item.photo_sha256 for item in to_send},
                claiming.cache,
                # THE DELIBERATE RE-READS, WHICH ARE CACHE HITS BY CONSTRUCTION. Without this
                # the recompute would drop every `--reidentify-stale` target from the claim and
                # the run would submit cards nothing was holding.
                force=stale_targets,
                # A RESUME IS THIS RUN CONTINUING. `--run-dir` re-enters a run that already
                # claimed these cards, so its own stale claim is the first thing this would
                # collide with; naming it releases that run's claims and nobody else's.
                resuming=(Path(args.run_dir).name if getattr(args, "run_dir", None) else None),
                capture_dir=_recorded_dir(roots),
            )
            if conflicts:
                # NOTHING WAS WRITTEN, so leaving the block commits nothing — `Rows.changes()`
                # finds no diff. The refusal is the answer and the run is not created: a press
                # refused here has cost a preflight and not a run directory.
                say("")
                say("refused: these cards are already claimed by a live submission.")
                say(f"  {submissions.conflict_sentence(conflicts)}")
                say("")
                say(
                    "Two live batches over one card is two invoices for one answer. Watch that "
                    "run, or release its claim on #/runs if its holder is gone."
                )
                return 1
        if claim is None:
            # THE RECOMPUTE EMPTIED THE SEND LIST: every card this press was going to buy
            # became a cache hit while it was preparing, which means another run finished and
            # banked the answers. Nothing is claimed because nothing is being bought.
            say("")
            say(
                f"every one of the {len(to_send)} card(s) this run was going to send is now "
                f"answered in the store — another run banked them while this one was preparing. "
                f"Nothing is being submitted."
            )
            for item in to_send:
                entry = store.read().cache.reusable(item.key, item.photo_sha256 or "")
                if entry is not None:
                    _adopt_cached(item, entry, fingerprints)
            to_send = [i for i in items if i.stage == STAGE_PENDING]
        elif len(claim.keys) != len(to_send):
            # NARROWED, NOT REFUSED. Same cause as above and a partial version of it: the cards
            # the recompute dropped take the answer the store now owns, and the send list
            # becomes exactly what was claimed — which is the property the claim's whole
            # meaning rests on, asserted here rather than assumed.
            held = set(claim.keys)
            adopted = 0
            for item in list(to_send):
                if item.key in held:
                    continue
                entry = store.read().cache.reusable(item.key, item.photo_sha256 or "")
                if entry is None:
                    continue
                _adopt_cached(item, entry, fingerprints)
                adopted += 1
            to_send = [i for i in items if i.stage == STAGE_PENDING]
            say("")
            say(
                f"claim           {len(claim.keys)} card(s) held under {claim.receipt}; "
                f"{adopted} dropped from the send — answered in the store since the preflight"
            )
        else:
            say(f"claim           {len(claim.keys)} card(s) held under {claim.receipt}")

    # ------------------------------------------------------------------------- the run
    run_dir = (
        runs.open_run(args.run_dir)
        if getattr(args, "run_dir", None)
        else runs.create(args.label or _default_label(selection, roots))
    )
    # THE SCOPE, WITH THE BOX'S TRUE INDEX IN IT (D145). Written before anything is
    # submitted, so a run that dies mid-batch still records which drawer it was over.
    scope = _scope_for(items, snapshot.inventory)
    if scope is not None:
        run_dir.set(scope=scope)
    # AND WHAT WAS ASKED FOR, BESIDE WHAT WAS FOUND. `scope` answers which drawer this run's
    # cards are in and is derived from the cards; this answers what the press named, which no
    # reader can reconstruct — a press over the store that swept up only box 3 and a press aimed
    # at box 3 leave the same `scope` and different selections.
    run_dir.set(selection=selection.describe())
    # AND WHAT WAS ACTUALLY SUBMITTED FOR IDENTIFICATION, BESIDE BOTH OF THOSE. `selection`
    # is the query and `scope` is the drawer it turned out to touch; neither says which
    # position keys were actually SENT to the model this run — a cache-hit-heavy selection
    # can process 678 cards and send 214, and nothing before this recorded that 214 anywhere
    # a caller could read without opening `identifications.json`. `to_send` is already final
    # here: the claim negotiation above (D174) has already narrowed it against cards another
    # run banked in the meantime, so this is the same list that is about to be billed, not an
    # earlier guess at it.
    #
    # WRITTEN BEFORE ANYTHING IS SUBMITTED, like `scope` above: a run that dies mid-batch
    # still records what it was over. `Run.submitted` is the cheap reader — a manifest read
    # rather than the (potentially large) identifications file — and `_run_keys_of` below
    # reads it first so a `--run <name>` selection term no longer has to open that file to
    # learn a run's own keys.
    run_dir.set(submitted=sorted(item.key for item in to_send))
    run_dir.set(
        capture_dir=_recorded_dir(roots),
        prompt_fingerprint=fingerprint,
        retry_fingerprint=prompt.retry_fingerprint(),
        rarity_fingerprint=prompt.rarity_fingerprint(),
        model=prompt.MODEL,
        flags={
            "max_edge": args.max_edge,
            "retry_budget": args.retry_budget,
            "reidentify_stale": bool(args.reidentify_stale),
            "force_resubmit": bool(args.force_resubmit),
            "variant": getattr(args, "variant", None),
        },
    )
    say(f"run             {run_dir.directory}")

    # THE CLAIM LEARNS ITS RUN'S NAME, and this is the second of the two tiny transactions
    # `Submissions.attach_run` argues for. It cannot be folded into the claim above: the claim
    # has to be written BEFORE `runs.create`, or a press refused on intersection leaves an
    # empty run directory on `#/runs`. This write failing is harmless — the claim still holds,
    # still blocks and still releases; the screen just draws it without a run name.
    if claim is not None:
        with store.write() as naming:
            naming.submissions.attach_run(claim.receipt, run_dir.name)

    # Keyed by the SUBMITTED id, not the store key: outcomes come back named by
    # custom_id, and building the lookup through the same translation is what lets
    # `_apply` stay a plain dict.get with nothing to decode.
    items_by_key = {_custom_id(item.key): item for item in items}
    usage_in = usage_out = 0

    existing = run_dir.batch_ids
    if existing and not run_dir.collected and not args.force_resubmit:
        say(f"reattaching to {len(existing)} unfinished batch(es) — results keep for 29 days")
        try:
            result = batch.collect_batches(
                existing,
                # {custom_id: strategy}, recomputed from the same sidecars that built the
                # submission — the encoding is deterministic, which is what RESUME BEATS
                # RESUBMIT relies on. An id outside the mapping parses under the default
                # profile, the only contract an untagged request can have been sent as.
                strategies={
                    _custom_id(item.key): item.strategy
                    for item in items
                    if item.strategy is not None
                },
                log=say,
            )
        except batch.BatchError as exc:
            say(f"reattach failed: {exc}")
            _give_back_unspent(claim, run_dir, store, say)
            return 1
        _apply(items_by_key, result)
        usage_in += result.usage.input_tokens
        usage_out += result.usage.output_tokens
    elif to_send:
        try:
            result = batch.run_batch(
                _requests(to_send, with_crops=False, say=say),
                log=say,
                on_submit=run_dir.add_batch_id,
            )
        except batch.BatchError as exc:
            say(f"identification did not run: {exc}")
            _give_back_unspent(claim, run_dir, store, say)
            return 1
        _apply(items_by_key, result)
        usage_in += result.usage.input_tokens
        usage_out += result.usage.output_tokens

    # --------------------------------------------------------------------- retry rounds
    for attempt in range(1, args.retry_budget + 1):
        wanted = []
        crops = False
        for item in items:
            # ONLY WHAT THIS RUN SENT CAN BE RE-SENT. `cached or prepared is None` said the
            # same thing by naming two of the three ways out; under hash-first a refused card
            # and a cache hit are both unprepared, so the field says it directly. A card that
            # came back errored is still `STAGE_PENDING` — the stage is where the PREFLIGHT
            # left it, and the model's answer is `status`.
            if item.stage != STAGE_PENDING:
                continue
            retry, crop, reason = _needs_retry(item)
            if retry:
                item.retries = attempt
                item.retry_reasons.append(reason)
                wanted.append(item)
                crops = crops or crop
        if not wanted:
            break
        say("")
        say(f"retry {attempt}/{args.retry_budget}: {len(wanted)} card(s) "
            f"({', '.join(sorted({r for i in wanted for r in i.retry_reasons}))})")
        requests = _requests(wanted, with_crops=crops, say=say)
        if not requests:
            break
        try:
            result = batch.run_batch(requests, log=say, on_submit=run_dir.add_batch_id)
        except batch.BatchError as exc:
            say(f"retry failed: {exc}")
            break
        _apply(items_by_key, result)
        usage_in += result.usage.input_tokens
        usage_out += result.usage.output_tokens

    run_dir.set(
        collected=True,
        usage={
            "input_tokens": usage_in,
            "output_tokens": usage_out,
            # WHAT IT COST, AT THE RATES IN FORCE THE DAY IT RAN. `cli/runs.py`'s header has
            # said since it was written that this manifest records "what it cost", and
            # docs/specs/batch-script.md's file map says the same — both were true of the
            # TOKENS and of nothing else, so a screen could report 290,470 tokens and no
            # figure. `server/pipeline_routes.py:_usage` fills this in for a run that
            # predates the field, and never over one that carries it: a recorded figure is
            # evidence and a computed one is an opinion about evidence.
            "cost_usd": cost.recorded(usage_in, usage_out),
        },
    )

    # --------------------------------------------------------------------------- record
    payload = {
        "prompt_fingerprint": fingerprint,
        "cards": {
            item.key: {
                "photo": str(item.capture.photo),
                "box": item.capture.box,
                "index": item.capture.index,
                "set_hint": item.capture.set_hint,
                "metadata_finish": item.capture.metadata_finish,
                # D23's stack claim as it was SENT — the validated tuple, post
                # vocabulary check, because this is the record of what the model was
                # told. The raw sidecar string survives in `sidecar_problem` when the
                # two differ.
                "rarity_claim": item.capture.rarity_claim,
                # THE RAW CLAIM, NOT `game_or_default`. This payload is the run's record of
                # what the sidecars said, and a backfilled `pokemon` written here would make
                # a run against sidecars predating D21 indistinguishable from one where the
                # operator chose Pokemon on every card. `cli/resolve.py` applies the backfill
                # at the read, which is where D21 puts it.
                "game": item.capture.game,
                # RESOLVED, unlike `game` above, which is the sidecar's raw claim: this is
                # the strategy the card was processed under, because "which contract read
                # it" is the question a later re-read asks. None == refused, nothing read it.
                "strategy": item.strategy,
                "note": item.capture.note,
                "variant_from_flag": item.capture.variant_from_flag,
                "position_source": item.capture.source,
                "sidecar_problem": item.capture.problem,
                "status": item.status,
                "error": item.error,
                "cached": item.cached,
                "stale_prompt": item.stale_prompt,
                "detection": item.detection,
                "retries": item.retries,
                "retry_reasons": item.retry_reasons,
                "identification": item.identification,
                # THE ITEM'S OWN DIGEST, NOT THE PREPARED BYTES'. This read
                # `item.prepared.sha256 if item.prepared else None`, and under hash-first a
                # cache hit is never prepared — so that expression would have written `None`
                # for 464 of this directory's 678 records, and `cli/resolve.py:1108` puts
                # every record without a digest into `blind`, where D36's realign can no
                # longer re-bind it to a slot. Same value, read off the step that computes it.
                "photo_sha256": item.photo_sha256,
            }
            for item in items
        },
    }
    run_dir.write_identifications(payload)

    disagreements: List[dict] = []
    released_keys = 0
    with store.write() as writable:
        for item in items:
            if item.capture.has_position:
                writable.inventory.record_capture(
                    # THE CLAIM LIST IS RESTATED HERE — the fourth restatement, and the one
                    # `store/master.py:CAPTURE_CLAIM_FIELDS` cannot reach, because this
                    # builds a `Card` rather than calling `allocate_capture`. Every value is
                    # the sidecar's raw claim: `record_capture` skips a None, so a sidecar
                    # that names no game leaves the record's game alone rather than writing
                    # a Pokemon into it, which is D21's write-side-default prohibition.
                    master.Card(
                        box=item.capture.box,
                        index=item.capture.index,
                        # THE CARD'S NAME, AND THIS SITE IS ONE OF THE THREE `store/master.py`
                        # CALLS "a seam to watch rather than a guarantee" (D172). A position
                        # the store has never seen is BORN here rather than at
                        # `allocate_capture` — an ordinary case, which `cli/cmd_emit.py`'s own
                        # comment names — and `record_capture` refuses a nameless new card, so
                        # without this line `identify` over such a directory refuses outright.
                        #
                        # `item.photo_sha256` IS THE RIGHT VALUE AND NOT MERELY AN AVAILABLE
                        # ONE: it is `images.sha256_of(item.capture.photo)`, set for every item
                        # before the cache is consulted, which is exactly D172's definition —
                        # the sha256 of the photograph the store held when the id was issued,
                        # read off the disk. Free here; the digest is already computed.
                        cid=item.photo_sha256,
                        photo=str(item.capture.photo),
                        set_hint=item.capture.set_hint,
                        # LIST, NOT THE READER'S TUPLE, and this conversion is load-bearing
                        # rather than cosmetic. The claim is a set since D3 rung 1's
                        # amendment; `identify/sidecar.py:Capture` holds it as a tuple
                        # because that dataclass is frozen, and `store/master.py:Card` holds
                        # a LIST because `to_payload` calls `asdict` — which PRESERVES a
                        # tuple, so a tuple assigned here would be written to
                        # `inventory.json` as an array and reload as a list, leaving
                        # `to_payload` and `parse` no longer each other's inverse. Both
                        # dataclasses say so at the field. `record_capture` skips a falsy
                        # claim, so `None` still leaves the record's own claim alone.
                        metadata_finish=(
                            None
                            if item.capture.metadata_finish is None
                            else list(item.capture.metadata_finish)
                        ),
                        game=item.capture.game,
                        note=item.capture.note,
                    )
                )
            if item.identification is None or item.cached:
                continue
            # THE DIGEST GATES THE CACHE WRITE, not the prepared bytes. An entry is keyed by
            # the photograph it answers for, so a card with no digest has nothing to key on
            # — and a card with a digest but no `prepared` cannot reach here anyway, because
            # it was never sent and so has no `identification`. Reading the digest keeps the
            # write's precondition and the write's payload the same fact.
            if item.photo_sha256 is not None:
                clash = writable.cache.put(
                    item.key,
                    item.identification,
                    item.photo_sha256,
                    # The hash of the profile that read THIS card. The default covers the
                    # one answer that can arrive without a strategy of its own: a
                    # reattached result for a card whose sidecar no longer names one,
                    # which `_collect` parsed under the default for the same reason.
                    fingerprints.get(item.strategy, fingerprint),
                )
                if clash:
                    disagreements.append(clash)
            if item.capture.has_position and item.parsed is not None:
                # THE PARSED FIELDS, NOT THE RAW PAYLOAD'S KEYS. The raw payload is
                # per-profile in shape — a misc card answers `printed_id`, a code card
                # answers `code` — and reading `.get("number")` off it wrote a record
                # only Pokemon's profile could ever fill. The parser is where each
                # profile already says which of its fields is the name and which is the
                # identifier, so the record reads the parser's answer: for a code card
                # that is C8's whole mechanism — the transcribed code lands in `number`,
                # which is the column `GET /search` matches, and the dispute lookup is
                # the existing search. For a Pokemon card the values differ from the raw
                # keys only by the parser's own hygiene (strip, `#`-removal, case fold
                # on confidence), which is what the join reads anyway.
                writable.inventory.record_identification(
                    item.key,
                    name=item.parsed.name,
                    number=item.parsed.number,
                    printed_total=item.parsed.printed_total,
                    confidence=item.parsed.confidence,
                    run=run_dir.name,
                    # THE RAW `finish` KEY, WHICH IS WHAT `cli/resolve.py:load` READS. The
                    # parsed fields above are the parser's hygiene applied to the model's
                    # answer; this one has no parsed twin, and `load` takes it off the
                    # identification dict exactly like this before handing it to
                    # `_detected` — so the store and the run record now carry one value,
                    # read the same way. Interpreting it here would put the per-game finish
                    # whitelist in a second place; `_detected` applies it at the point of
                    # use and this line stores the raw answer unchanged.
                    detected_finish=(item.identification or {}).get("finish"),
                    read_disputes=_read_disputes_for(
                        writable, item.key, item.parsed.name
                    ),
                )

        # C8's ledger, in the same locked session that recorded the cards it indexes.
        # TWO COPIES WITH TWO JOBS: `inventory/codes.jsonl` is the standing index the
        # dispute lookup reads — upserted by position, so "one line per code card" stays
        # literally true across re-identifications — and the run directory's copy is this
        # run's export, written whole beside identifications.json, deletable with the run
        # (runs/ is derived; inventory/ is the master). BOTH live under paths .gitignore
        # already covers, which was verified before a byte was written: a ledger of
        # unredeemed codes never reaches a commit.
        ledger_lines, ledger_skipped = _code_ledger_lines(
            items,
            run_dir.name,
            lambda key: getattr(writable.inventory.cards.get(key), "captured_at", None),
        )
        if ledger_lines:
            store_files.upsert_jsonl(
                store_files.codes_ledger_path(), ledger_lines, ("box", "index")
            )
        if ledger_lines or ledger_skipped:
            store_files.write_atomic(
                Path(run_dir.directory) / store_files.CODES_LEDGER_NAME,
                "".join(
                    json.dumps(line, sort_keys=True) + "\n" for line in ledger_lines
                ).encode("utf-8"),
            )

        # THE CLAIM IS GIVEN BACK BY THE SAME COMMIT THAT BANKS WHAT IT BOUGHT
        # (D174). Both, or neither: the cards stop being held at the exact
        # moment the answers they paid for become the cache entries that make a second press
        # free. A `finally` here would be the defect — this command can die between submitting
        # a batch and collecting it, and the batch is paid for and keeps for 29 days, so a
        # claim released on the way out of a crash is a green button over an invoice that has
        # already been rung up. A run that does not reach this line KEEPS its claim, and the
        # release control on `#/runs` is the named way out.
        if claim is not None:
            freed = writable.submissions.release(claim.receipt, submissions.BY_RUN)
            if freed is not None:
                released_keys = len(freed.keys)

    # --------------------------------------------------------------------------- report
    answered = [i for i in items if i.identification is not None]
    failed = [i for i in items if i.identification is None]
    stale = [i for i in items if i.stale_prompt]
    not_detected = [i for i in items if i.detection == NOT_DETECTED]
    unfit_crops = [i for i in items if i.detection == UNFIT_CROP]

    say("")
    say(f"identified      {len(answered)}/{len(items)}")
    say(f"tokens          in {usage_in}, out {usage_out}")
    # THE RATES ARE NAMED ON THE LINE so the figure explains itself and nobody reads it as an
    # invoice. It cannot collide with the preflight's own line, which `_ESTIMATE` anchors at
    # `^estimated cost`.
    say(f"cost            ${cost.usd(usage_in, usage_out).quantize(Decimal('0.01'))} "
        f"at ${cost.INPUT_PER_MTOK}/${cost.OUTPUT_PER_MTOK} per MTok")
    if ledger_lines:
        say(
            f"code ledger     {len(ledger_lines)} line(s) -> "
            f"{store_files.codes_ledger_path()} (standing index, upserted by position) "
            f"and {Path(run_dir.directory) / store_files.CODES_LEDGER_NAME}"
        )
    for reason in ledger_skipped:
        say(f"                  no ledger line: {reason}")
    if stale:
        say(f"older prompt    {len(stale)} answer(s) reused from a previous prompt "
            f"(recorded, not re-read — see v2 §4.6)")
    if not_detected:
        say(f"not detected    {len(not_detected)} card(s) could not be found in frame; "
            f"no crop retry was possible:")
        for item in not_detected:
            say(f"                  {item.key} {item.capture.photo.name}")
    if unfit_crops:
        # KEPT APART FROM `not detected`, because they ask for different things. A card
        # nothing could find is a photograph to look at; a card whose box the guard refused
        # is a detector that answered confidently and wrongly, and a run full of these is a
        # rig finding rather than a scatter of bad frames.
        say(f"unfit crop      {len(unfit_crops)} card(s) were located and the box was not "
            f"the card, so no crop retry was sent:")
        for item in unfit_crops:
            say(f"                  {item.key} {item.capture.photo.name}")
    if disagreements:
        say(f"disagreements   {len(disagreements)} human-cleared answer(s) the model now "
            f"reads differently. The human answer stands:")
        for clash in disagreements:
            say(f"                  {clash['position']}: human {clash['human']} vs "
                f"model {clash['model']}")
    if failed:
        say(f"failed          {len(failed)} card(s) go to the main queue as "
            f"identification_failed — never dropped:")
        for item in failed:
            say(f"                  {item.key} {item.status}: {item.error}")
    if claim is not None:
        # THE WORK, NOT THE OUTCOME. A guard whose figures are never printed is a guard nobody
        # can tell is armed — the addendum to the hash-first PR records deleting its gate and
        # watching every outcome stay green. So the press says how many cards it held and that
        # it gave them back, and `make submission-selftest` asserts both figures.
        say(f"claim           {released_keys} card(s) released ({claim.receipt})")
    say("")
    say(f"next: pkmnscan join {run_dir.directory} --export <filtered-export.csv>")
    return 0
