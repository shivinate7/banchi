"""Transport — the Anthropic **Message Batches API**. The only file here that talks out.

CLAUDE.md: "Batch API, not sequential calls. v1 claimed Batch and shipped real-time."
That bug is structural, not a lapse of attention, so the fix is structural too: this
module exposes exactly one entry point, `run_batch`, and it has no per-card request path
to quietly fall back to. There is no `identify_one`. Every caller — harness T1 today,
build-order step 4's batch script next — submits a whole run and waits.

The three calls that make it a batch, and the only three Anthropic calls in this repo:

    client.messages.batches.create(requests=[...])   submit every card at once
    client.messages.batches.retrieve(batch_id)       poll until processing_status ended
    client.messages.batches.results(batch_id)        stream results back

Results arrive in ANY order, so they are keyed by `custom_id` and never by position.
Every submitted id is accounted for in the returned mapping — a card that errored, was
cancelled, or expired comes back as an `Outcome` carrying the reason, because the hard
rule is that nothing is silently dropped.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterator, List, Optional, Sequence

import envfile
from identify import prompt

# Batch limits are 100k requests / 256MB per batch. Both are held well clear: a full-set
# run is a few hundred images, and the byte cap is what actually binds once base64 image
# data is in the payload.
MAX_REQUESTS_PER_BATCH = 1_000
MAX_PAYLOAD_BYTES = 180 * 1024 * 1024

DEFAULT_POLL_SECONDS = 15
DEFAULT_TIMEOUT_SECONDS = 3_600  # most batches land in minutes; the API's own cap is 24h

SUCCEEDED = "succeeded"


class BatchError(RuntimeError):
    """The batch could not be run at all — no credentials, SDK missing, timed out."""


@dataclass(frozen=True)
class ImageRequest:
    """One card to identify. `custom_id` is the caller's key and comes back unchanged."""

    custom_id: str
    media_type: str
    data_b64: str
    set_hint: Optional[str] = None  # D2: optional accelerator, identification works without

    @property
    def payload_bytes(self) -> int:
        return len(self.data_b64)


@dataclass(frozen=True)
class Outcome:
    """What came back for one `custom_id`. Exactly one of the two fields is set."""

    custom_id: str
    status: str
    identification: Optional[prompt.Identification] = None
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.identification is not None


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, message) -> None:
        usage = getattr(message, "usage", None)
        if usage is None:
            return
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0


@dataclass
class BatchRun:
    outcomes: Dict[str, Outcome] = field(default_factory=dict)
    batch_ids: List[str] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    elapsed_seconds: float = 0.0

    @property
    def succeeded(self) -> List[Outcome]:
        return [o for o in self.outcomes.values() if o.ok]

    @property
    def failed(self) -> List[Outcome]:
        return [o for o in self.outcomes.values() if not o.ok]


def _client(api_key: Optional[str] = None):
    """Import the SDK late so a missing dependency reports as a message, not a traceback."""
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - environment problem, not logic
        raise BatchError(
            "the `anthropic` package is not installed — run `make venv`"
        ) from exc

    if not api_key:
        envfile.load()  # ANTHROPIC_API_KEY may live in .env; a real env var still wins

    try:
        return anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    except Exception as exc:
        raise BatchError(f"could not construct the Anthropic client: {exc}") from exc


def build_request(item: ImageRequest) -> dict:
    """One entry in the batch. Image block before text — vision reads better that way."""
    return {
        "custom_id": item.custom_id,
        "params": {
            "model": prompt.MODEL,
            "max_tokens": prompt.MAX_TOKENS,
            "system": prompt.SYSTEM_PROMPT,
            # Structured outputs: the response is guaranteed to match SCHEMA, so the
            # parser handles surprises rather than tolerating slop.
            "output_config": {
                "format": {"type": "json_schema", "schema": prompt.SCHEMA}
            },
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": item.media_type,
                                "data": item.data_b64,
                            },
                        },
                        {"type": "text", "text": prompt.user_text(item.set_hint)},
                    ],
                }
            ],
        },
    }


def _chunks(items: Sequence[ImageRequest]) -> Iterator[List[ImageRequest]]:
    """Split only when a batch would exceed a hard API limit. Usually yields one chunk."""
    current: List[ImageRequest] = []
    size = 0
    for item in items:
        too_many = len(current) >= MAX_REQUESTS_PER_BATCH
        too_big = current and size + item.payload_bytes > MAX_PAYLOAD_BYTES
        if too_many or too_big:
            yield current
            current, size = [], 0
        current.append(item)
        size += item.payload_bytes
    if current:
        yield current


def _text_of(message) -> str:
    for block in getattr(message, "content", []) or []:
        if getattr(block, "type", None) == "text":
            return block.text
    raise prompt.MalformedIdentification("response carried no text block")


def _collect(client, batch_id: str, run: BatchRun) -> None:
    for entry in client.messages.batches.results(batch_id):
        custom_id = entry.custom_id
        kind = entry.result.type
        if kind != SUCCEEDED:
            detail = getattr(getattr(entry.result, "error", None), "type", kind)
            run.outcomes[custom_id] = Outcome(custom_id, kind, error=str(detail))
            continue
        message = entry.result.message
        run.usage.add(message)
        try:
            identification = prompt.parse(_text_of(message))
        except prompt.MalformedIdentification as exc:
            run.outcomes[custom_id] = Outcome(custom_id, "malformed", error=str(exc))
            continue
        run.outcomes[custom_id] = Outcome(custom_id, SUCCEEDED, identification=identification)


def run_batch(
    items: Sequence[ImageRequest],
    *,
    api_key: Optional[str] = None,
    client=None,
    poll_seconds: int = DEFAULT_POLL_SECONDS,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    log: Optional[Callable[[str], None]] = None,
) -> BatchRun:
    """Identify every image in one submission. Blocks until the batch ends.

    Returns an `Outcome` for every `custom_id` submitted, whatever happened to it.
    """
    say = log or (lambda _message: None)
    run = BatchRun()
    if not items:
        return run

    seen = set()
    for item in items:
        if item.custom_id in seen:
            raise BatchError(f"duplicate custom_id {item.custom_id!r}")
        seen.add(item.custom_id)

    client = client or _client(api_key)
    started = time.monotonic()

    for chunk in _chunks(items):
        requests = [build_request(item) for item in chunk]
        try:
            batch = client.messages.batches.create(requests=requests)
        except Exception as exc:
            raise BatchError(f"batch create failed: {exc}") from exc

        run.batch_ids.append(batch.id)
        say(f"submitted {len(requests)} requests as {batch.id}")

        deadline = time.monotonic() + timeout_seconds
        status = batch.processing_status
        while status != "ended":
            if time.monotonic() > deadline:
                raise BatchError(
                    f"{batch.id} still {status} after {timeout_seconds}s — "
                    f"results stay retrievable for 29 days, so re-run to pick them up"
                )
            time.sleep(poll_seconds)
            batch = client.messages.batches.retrieve(batch.id)
            if batch.processing_status != status:
                status = batch.processing_status
                say(f"{batch.id} {status}")

        counts = batch.request_counts
        say(
            f"{batch.id} ended — {counts.succeeded} succeeded, {counts.errored} errored, "
            f"{counts.canceled} canceled, {counts.expired} expired"
        )
        _collect(client, batch.id, run)

    # Closure: everything submitted is accounted for, matched or reported.
    for item in items:
        if item.custom_id not in run.outcomes:
            run.outcomes[item.custom_id] = Outcome(
                item.custom_id, "absent", error="no result returned for this request"
            )

    run.elapsed_seconds = time.monotonic() - started
    return run
