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

NOTHING IS EVER SKIPPED. Every photograph in the directory comes out of this command as an
identification, a cache hit, or a named failure. That is v1 bug #5 stated as a property.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

import geometry
from cli import runs
from identify import batch, images, prompt, sidecar
from pipeline import games
from store import master
from store.session import Store

# Claude Haiku 4.5, halved for the Batch API's 50% discount (confirmed 2026-08-03):
#
#     base input  $1 / MTok  ->  $0.50
#     output      $5 / MTok  ->  $2.50
#
# The arithmetic is written out because the halving is the part that looks like a typo. Two
# columns of the price sheet are deliberately unused: prompt caching is not wired here, so
# no request pays a cache-write rate and none gets a cache-hit rate. The system prompt IS
# identical across every request in a batch and could in principle be cached — but images
# dominate the input (a 1568px card is several times the system prompt), so the saving is
# small and the complexity is not free. Recorded so a later session sees a decision rather
# than an oversight.
#
# An ESTIMATE, printed before you spend: it exists so that a mistyped directory of 40,000
# photos is visibly a different number from a box of 400. Not an invoice, and nothing
# reconciles against it.
INPUT_PER_MTOK = Decimal("0.50")
OUTPUT_PER_MTOK = Decimal("2.50")
PIXELS_PER_TOKEN = Decimal("750")
SYSTEM_TOKENS = 500
OUTPUT_TOKENS = 60

# What triggers which kind of retry (v2 §4.4, §4.5).
PLAIN_RETRY_STATUSES = ("errored", "expired", "canceled", "absent")
CROP_RETRY_STATUSES = ("malformed",)
WEAK_CONFIDENCE = "low"

DETECTED = "found"
NOT_DETECTED = "not_found"
NOT_ATTEMPTED = "not_attempted"

# The refusal code for a card whose sidecar names a game outside the registry. Its
# siblings — `unwritten_prompt`, `unknown_strategy` — live in `identify/batch.py`, where
# the transport answers them; this one is the command's own, because the transport never
# sees a game, only a strategy, and a card with no registry entry has not even that.
UNKNOWN_GAME = "unknown_game"


@dataclass
class Item:
    """One capture on its way through this command."""

    capture: sidecar.Capture
    prepared: Optional[images.Prepared] = None
    error: Optional[str] = None
    cached: bool = False
    stale_prompt: bool = False
    identification: Optional[dict] = None
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
    million = Decimal(1_000_000)
    cost = (
        Decimal(total_input) / million * INPUT_PER_MTOK
        + Decimal(OUTPUT_TOKENS * len(items)) / million * OUTPUT_PER_MTOK
    )
    return cost.quantize(Decimal("0.01"))


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

    item.detection = DETECTED
    regions = geometry.crop_regions(item.capture.photo, box, bands=bands)
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


def run(args, say) -> int:
    capture_dir = Path(args.capture_dir)
    store = Store()

    # ------------------------------------------------------------------ read the input
    captures = sidecar.scan(
        capture_dir, box=args.box, variant_default=getattr(args, "variant", None)
    )
    if not captures:
        say(f"no photographs under {capture_dir}")
        return 1

    items = [Item(capture=capture) for capture in captures]
    for item in items:
        _attach_registry(item)
        try:
            item.prepared = images.prepare(item.capture.photo, max_edge=args.max_edge)
        except images.ImageError as exc:
            item.error = str(exc)
            item.status = "unreadable"

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
        if item.prepared is None:
            continue
        entry = snapshot.cache.reusable(item.key, item.prepared.sha256)
        if entry is None:
            continue
        if item.key in stale_targets:
            item.retry_reasons.append("reidentify-stale")
            continue
        item.cached = True
        item.identification = dict(entry.identification)
        item.status = batch.SUCCEEDED
        expected = fingerprints.get(item.strategy)
        item.stale_prompt = expected is not None and entry.prompt_fingerprint != expected

    # A CARD NOBODY HAS A PROMPT FOR IS REFUSED HERE, BEFORE IT COSTS ANYTHING — the same
    # refusal, in the same words, that `identify/batch.py` would answer at submission. In
    # the preflight rather than left to the transport so that `--dry-run` shows it, and so
    # `to send` and the cost estimate count only what will actually be submitted. A
    # refused card keeps the NOTHING IS EVER SKIPPED property: it leaves this command as a
    # named failure bound for the main queue, never dropped — and never read with another
    # game's prompt (D21). A cached answer is left standing: already paid for, and refusing
    # it would answer a question about submission on a card that is not being submitted.
    for item in items:
        if item.cached or item.prepared is None:
            continue
        if item.strategy is None:
            item.status = UNKNOWN_GAME
            item.error = (
                f"game {item.game!r} is not in the registry — no prompt to read it with. "
                f"Fix the sidecar's `game`."
            )
            continue
        refusal = batch.prompt_refusal(_custom_id(item.key), item.strategy)
        if refusal is not None:
            item.status = refusal.status
            item.error = refusal.error

    to_send = [
        i
        for i in items
        if not i.cached and i.prepared is not None and i.status == "pending"
    ]
    unreadable = [i for i in items if i.prepared is None]
    no_position = [i for i in items if not i.capture.has_position]

    # ------------------------------------------------------------------------ preflight
    payload_bytes = sum(i.prepared.payload_bytes for i in to_send if i.prepared)
    chunks = max(1, -(-len(to_send) // batch.MAX_REQUESTS_PER_BATCH))
    say("")
    say(f"capture dir     {capture_dir}")
    say(f"photographs     {len(items)}")
    say(f"cache hits      {len(items) - len(to_send) - len(unreadable)}")
    say(f"to send         {len(to_send)}")
    say(f"payload         {payload_bytes / 1_000_000:.1f} MB in {chunks} batch chunk(s)")
    say(f"estimated cost  ${_estimate(to_send)}")
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
        # The preflight prints what will be sent, and a claim changes the user turn — so
        # a run with claims says so before it costs anything, the same as the set hint.
        say(f"rarity claims   {len(claimed)} card(s) carry a stack claim in the user turn")
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

    # ------------------------------------------------------------------------- the run
    run_dir = (
        runs.open_run(args.run_dir)
        if getattr(args, "run_dir", None)
        else runs.create(args.label or capture_dir.name)
    )
    run_dir.set(
        capture_dir=str(capture_dir),
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
            return 1
        _apply(items_by_key, result)
        usage_in += result.usage.input_tokens
        usage_out += result.usage.output_tokens

    # --------------------------------------------------------------------- retry rounds
    for attempt in range(1, args.retry_budget + 1):
        wanted = []
        crops = False
        for item in items:
            if item.cached or item.prepared is None:
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
        usage={"input_tokens": usage_in, "output_tokens": usage_out},
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
                "photo_sha256": item.prepared.sha256 if item.prepared else None,
            }
            for item in items
        },
    }
    run_dir.write_identifications(payload)

    disagreements: List[dict] = []
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
                        photo=str(item.capture.photo),
                        set_hint=item.capture.set_hint,
                        metadata_finish=item.capture.metadata_finish,
                        game=item.capture.game,
                        note=item.capture.note,
                    )
                )
            if item.identification is None or item.cached:
                continue
            if item.prepared is not None:
                clash = writable.cache.put(
                    item.key,
                    item.identification,
                    item.prepared.sha256,
                    # The hash of the profile that read THIS card. The default covers the
                    # one answer that can arrive without a strategy of its own: a
                    # reattached result for a card whose sidecar no longer names one,
                    # which `_collect` parsed under the default for the same reason.
                    fingerprints.get(item.strategy, fingerprint),
                )
                if clash:
                    disagreements.append(clash)
            if item.capture.has_position:
                writable.inventory.record_identification(
                    item.key,
                    name=item.identification.get("name"),
                    number=item.identification.get("number"),
                    printed_total=item.identification.get("printed_total"),
                    confidence=item.identification.get("confidence"),
                    run=run_dir.name,
                )

    # --------------------------------------------------------------------------- report
    answered = [i for i in items if i.identification is not None]
    failed = [i for i in items if i.identification is None]
    stale = [i for i in items if i.stale_prompt]
    not_detected = [i for i in items if i.detection == NOT_DETECTED]

    say("")
    say(f"identified      {len(answered)}/{len(items)}")
    say(f"tokens          in {usage_in}, out {usage_out}")
    if stale:
        say(f"older prompt    {len(stale)} answer(s) reused from a previous prompt "
            f"(recorded, not re-read — see v2 §4.6)")
    if not_detected:
        say(f"not detected    {len(not_detected)} card(s) could not be found in frame; "
            f"no crop retry was possible:")
        for item in not_detected:
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
    say("")
    say(f"next: pkmnscan join {run_dir.directory} --export <filtered-export.csv>")
    return 0
