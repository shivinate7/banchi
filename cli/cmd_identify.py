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

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

import geometry
from cli import runs
from identify import batch, images, prompt, sidecar
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


def _requests(items: List[Item], with_crops: bool, say) -> List[batch.ImageRequest]:
    """Batch requests for the items that still need sending."""
    out: List[batch.ImageRequest] = []
    for item in items:
        if item.prepared is None:
            continue
        regions: List[batch.Attachment] = []
        if with_crops:
            regions = _crop_attachments(item, say)
        out.append(
            batch.ImageRequest(
                custom_id=item.key,
                media_type=item.prepared.media_type,
                data_b64=item.prepared.data_b64,
                set_hint=item.capture.set_hint,
                regions=regions,
            )
        )
    return out


def _crop_attachments(item: Item, say) -> List[batch.Attachment]:
    """Enlarged bands for a crop retry, or none when the card cannot be found.

    None is a real answer here, not a degraded one: §4.5 rung 3 says a card that cannot be
    located goes to a human rather than being cropped on a guess.
    """
    try:
        box = geometry.detect_card(item.capture.photo)
    except geometry.GeometryError as exc:
        item.detection = NOT_DETECTED
        say(f"  {item.key}: detection unavailable — {exc}")
        return []

    if box is None:
        item.detection = NOT_DETECTED
        say(f"  {item.key}: card not found in the frame — no crop retry")
        return []

    item.detection = DETECTED
    regions = geometry.crop_regions(item.capture.photo, box)
    attachments = []
    for name in (geometry.REGION_CARD, geometry.REGION_TITLE, geometry.REGION_NUMBER):
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
        try:
            item.prepared = images.prepare(item.capture.photo, max_edge=args.max_edge)
        except images.ImageError as exc:
            item.error = str(exc)
            item.status = "unreadable"

    # ------------------------------------------------------------------ consult the cache
    snapshot = store.read()
    fingerprint = prompt.prompt_fingerprint()
    queued = set(snapshot.review.entries) | set(snapshot.parked.entries)
    stale_targets = (
        set(snapshot.cache.weak_and_uncleared(fingerprint, queued))
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
        item.stale_prompt = entry.prompt_fingerprint != fingerprint

    to_send = [i for i in items if not i.cached and i.prepared is not None]
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
    say(f"prompt          {fingerprint}  (crop retry {prompt.retry_fingerprint()})")
    say(f"model           {prompt.MODEL}")
    if unreadable:
        say(f"unreadable      {len(unreadable)} — these are NOT sent and NOT dropped:")
        for item in unreadable:
            say(f"                  {item.capture.photo.name}: {item.error}")
    if no_position:
        say(f"no position     {len(no_position)} -> main review queue, flagged no_position")
    recovered = [i for i in items if i.capture.source == sidecar.FROM_FILENAME]
    if recovered:
        say(f"position from filename: {len(recovered)}")
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

    items_by_key = {item.key: item for item in items}
    usage_in = usage_out = 0

    existing = run_dir.batch_ids
    if existing and not run_dir.collected and not args.force_resubmit:
        say(f"reattaching to {len(existing)} unfinished batch(es) — results keep for 29 days")
        try:
            result = batch.collect_batches(existing, log=say)
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
                    master.Card(
                        box=item.capture.box,
                        index=item.capture.index,
                        photo=str(item.capture.photo),
                        set_hint=item.capture.set_hint,
                        metadata_finish=item.capture.metadata_finish,
                    )
                )
            if item.identification is None or item.cached:
                continue
            if item.prepared is not None:
                clash = writable.cache.put(
                    item.key,
                    item.identification,
                    item.prepared.sha256,
                    fingerprint,
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
