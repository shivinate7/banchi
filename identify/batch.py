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

Each request names the prompt profile that reads it (`strategy`), so one batch may
legally mix games (D21). A strategy `prompt.profile` cannot answer is refused per item
BEFORE submission, under its own status code — never submitted under another game's
prompt, which comes back confident and wrong, and never dropped, which breaks the rule
above. A refused card is an `Outcome` like any other, so the caller's report counts it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterator, List, Mapping, Optional, Sequence

import envfile
from identify import prompt

# Batch limits are 100k requests / 256MB per batch. Both are held well clear: a full-set
# run is a few hundred images, and the byte cap is what actually binds once base64 image
# data is in the payload.
MAX_REQUESTS_PER_BATCH = 1_000
MAX_PAYLOAD_BYTES = 180 * 1024 * 1024

DEFAULT_POLL_SECONDS = 15
DEFAULT_TIMEOUT_SECONDS = 3_600  # most batches land in minutes; the API's own cap is 24h

# NAMED HERE RATHER THAN LEFT TO THE SDK'S OWN READ OF THE ENVIRONMENT, so the one place this
# product resolves a paid credential is greppable. `_client` says why it is resolved at all.
API_KEY_ENV = "ANTHROPIC_API_KEY"

SUCCEEDED = "succeeded"

# The two refusal codes for a request whose strategy names no usable profile. Statuses
# rather than exceptions, because a refused card must come out of the run the way every
# card does — as an `Outcome` under its `custom_id`, counted in the report — never as a
# crash that takes the rest of the batch with it, and never as a silent omission.
UNKNOWN_STRATEGY = "unknown_strategy"
UNWRITTEN_PROMPT = "unwritten_prompt"


class BatchError(RuntimeError):
    """The batch could not be run at all — no credentials, SDK missing, timed out."""


@dataclass(frozen=True)
class Attachment:
    """An extra image in the same request — a crop-retry region (v2 §4.5)."""

    media_type: str
    data_b64: str


@dataclass(frozen=True)
class ImageRequest:
    """One card to identify. `custom_id` is the caller's key and comes back unchanged.

    `regions` is empty on the normal path. On a crop retry it carries the enlarged bands
    alongside the full image — still ONE request for the card, so there is still no
    per-card call path here, only a request that happens to have more pictures in it.
    """

    custom_id: str
    media_type: str
    data_b64: str
    set_hint: Optional[str] = None  # D2: optional accelerator, identification works without
    # D23's stack claim, travelling exactly as the set hint does: per card, optional, and
    # rendered by `prompt.user_text` only when present. Validated against the game's own
    # vocabulary at the sidecar read, so what arrives here is already legal to render.
    rarity_claim: Optional[Sequence[str]] = None
    regions: Sequence[Attachment] = ()
    # WHICH PROFILE READS THIS CARD. Per request, because game is a per-card claim (D21)
    # and a batch may legally mix them. The default is the Pokemon profile, so a caller
    # that predates the field — harness T1 builds requests without it — submits exactly
    # what it always submitted. `run_batch` refuses, by name and per item, any strategy
    # `prompt.profile` cannot answer; nothing falls through to another game's prompt.
    strategy: str = prompt.DEFAULT_PROFILE

    @property
    def payload_bytes(self) -> int:
        return len(self.data_b64) + sum(len(r.data_b64) for r in self.regions)

    @property
    def with_crops(self) -> bool:
        return bool(self.regions)


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
    """Import the SDK late so a missing dependency reports as a message, not a traceback.

    THE KEY IS RESOLVED HERE AND PASSED EXPLICITLY, THROUGH `envfile.get_live` (2026-09-11).
    This called `envfile.load()` and then constructed with no key at all, leaving the SDK to
    read `os.environ` itself — which made the value this process was started with the only
    value it could ever use. The key EXPIRES, and the operator replaces it in `.env`: on
    2026-09-11 the owner did exactly that and both `./pkmnscan identify` and the `#/runs` press
    kept failing with the dead one until `make down` / `make up`. `get_live` re-reads the file
    on every construction, which is what makes the paste enough.

    THE PRECEDENCE IS UNCHANGED and is `get_live`'s own: an explicit `api_key` argument wins —
    the harness and `run_batch`'s callers pass one — then a real environment variable, so CI
    still needs no file, then `.env`.

    AN UNRESOLVED KEY STILL CONSTRUCTS WITH NO KEY rather than refusing here, because the SDK's
    own missing-key error is the message `harness/tests/t1_id_eval.py` quotes, and a second
    refusal in front of it would be this module answering for a state it cannot see: a key
    placed some other way the SDK knows about is not this function's to reject.
    """
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - environment problem, not logic
        raise BatchError(
            "the `anthropic` package is not installed — run `make venv`"
        ) from exc

    key = api_key or envfile.get_live(API_KEY_ENV)

    try:
        return anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
    except Exception as exc:
        raise BatchError(f"could not construct the Anthropic client: {exc}") from exc


def _image_block(media_type: str, data_b64: str) -> dict:
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": data_b64},
    }


def _message(exc: BaseException) -> str:
    """`KeyError.__str__` reprs its argument; a refusal should read as it was written."""
    return str(exc.args[0]) if exc.args else str(exc)


def prompt_refusal(custom_id: str, strategy: str) -> Optional[Outcome]:
    """The named refusal for a strategy no profile answers, or None when it is sendable.

    Checked BEFORE submission, per item, because both alternatives are worse: submitting
    under another game's prompt returns a confident wrong answer no threshold fires on,
    and dropping the card breaks the rule that nothing is silently dropped. The error
    text is the dispatch's own message, which already says what to do next.
    `cli/cmd_identify.py` calls this too, so its preflight refuses in the same words the
    transport would.
    """
    try:
        prompt.profile(strategy)
    except prompt.UnknownProfile as exc:
        return Outcome(custom_id, UNKNOWN_STRATEGY, error=_message(exc))
    except prompt.UnwrittenPrompt as exc:
        return Outcome(custom_id, UNWRITTEN_PROMPT, error=_message(exc))
    return None


def build_request(item: ImageRequest) -> dict:
    """One entry in the batch. Image blocks before text — vision reads better that way.

    Everything model-facing comes off the profile `item.strategy` names — model, token
    cap, system prompt, user turn, schema — never off `prompt`'s module attributes, which
    is what once sent every card in a batch under Pokemon's prompt whatever its game.
    `prompt.profile` raises by name on a strategy it cannot answer; `run_batch` refuses
    those per item before anything reaches here.
    """
    chosen = prompt.profile(item.strategy)
    content = [_image_block(item.media_type, item.data_b64)]
    content += [_image_block(r.media_type, r.data_b64) for r in item.regions]
    content.append(
        {
            "type": "text",
            "text": prompt.user_text(
                item.set_hint,
                with_crops=item.with_crops,
                strategy=item.strategy,
                rarity_claim=item.rarity_claim,
            ),
        }
    )
    return {
        "custom_id": item.custom_id,
        "params": {
            "model": chosen.model,
            "max_tokens": chosen.max_tokens,
            "system": chosen.system,
            # Structured outputs: the response is guaranteed to match the profile's
            # schema, so the parser handles surprises rather than tolerating slop.
            "output_config": {
                "format": {"type": "json_schema", "schema": chosen.schema}
            },
            "messages": [{"role": "user", "content": content}],
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


def _collect(
    client, batch_id: str, run: BatchRun, strategies: Mapping[str, str]
) -> None:
    """`strategies` maps `custom_id` to the strategy the request was built under, so each
    answer is read by the parser of the profile that produced it. An id the mapping does
    not cover parses under the default profile — the only thing an untagged request can
    ever have been submitted as — and a misc answer landing there fails loudly as missing
    keys rather than being read as a Pokemon card."""
    for entry in client.messages.batches.results(batch_id):
        custom_id = entry.custom_id
        kind = entry.result.type
        if kind != SUCCEEDED:
            detail = getattr(getattr(entry.result, "error", None), "type", kind)
            run.outcomes[custom_id] = Outcome(custom_id, kind, error=str(detail))
            continue
        message = entry.result.message
        run.usage.add(message)
        strategy = strategies.get(custom_id, prompt.DEFAULT_PROFILE)
        # A paid answer whose CLAIMED strategy the dispatch refuses — reachable only on a
        # reattach whose caller supplied one — keeps its named refusal rather than
        # crashing the collection: re-running would buy the answer again to hit it again.
        refusal = prompt_refusal(custom_id, strategy)
        if refusal is not None:
            run.outcomes[custom_id] = refusal
            continue
        try:
            identification = prompt.parse(_text_of(message), strategy)
        except prompt.MalformedIdentification as exc:
            run.outcomes[custom_id] = Outcome(custom_id, "malformed", error=str(exc))
            continue
        run.outcomes[custom_id] = Outcome(custom_id, SUCCEEDED, identification=identification)


def _await_end(
    client,
    batch_id: str,
    poll_seconds: int,
    timeout_seconds: int,
    say: Callable[[str], None],
):
    """Poll one batch until the API says it ended. Returns the final batch object."""
    deadline = time.monotonic() + timeout_seconds
    batch = client.messages.batches.retrieve(batch_id)
    status = batch.processing_status
    while status != "ended":
        if time.monotonic() > deadline:
            raise BatchError(
                f"{batch_id} still {status} after {timeout_seconds}s — "
                f"results stay retrievable for 29 days, so re-run to pick them up"
            )
        time.sleep(poll_seconds)
        batch = client.messages.batches.retrieve(batch_id)
        if batch.processing_status != status:
            status = batch.processing_status
            say(f"{batch_id} {status}")
    return batch


def _say_counts(batch, say: Callable[[str], None]) -> None:
    counts = getattr(batch, "request_counts", None)
    if counts is None:
        return
    say(
        f"{batch.id} ended — {counts.succeeded} succeeded, {counts.errored} errored, "
        f"{counts.canceled} canceled, {counts.expired} expired"
    )


def collect_batches(
    batch_ids: Sequence[str],
    *,
    strategies: Optional[Mapping[str, str]] = None,
    api_key: Optional[str] = None,
    client=None,
    poll_seconds: int = DEFAULT_POLL_SECONDS,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    log: Optional[Callable[[str], None]] = None,
) -> BatchRun:
    """REATTACH to batches already submitted, and collect them.

    Results stay retrievable for 29 days, so a run whose script died mid-poll owns answers
    it has already paid for. Re-submitting would buy them a second time — which is why the
    ids are written to the manifest BEFORE the first poll, and why this exists to pick them
    up. Still no per-card path: this collects whole batches, same as `run_batch`.

    `strategies` is `{custom_id: strategy}` for the requests those batches carried, so
    each answer is parsed by the profile that produced it. Left None — or missing an id —
    the default profile reads it, which is the only thing an untagged request can ever
    have been submitted as.
    """
    say = log or (lambda _message: None)
    run = BatchRun()
    if not batch_ids:
        return run

    client = client or _client(api_key)
    started = time.monotonic()
    for batch_id in batch_ids:
        say(f"reattaching to {batch_id}")
        batch = _await_end(client, batch_id, poll_seconds, timeout_seconds, say)
        run.batch_ids.append(batch_id)
        _say_counts(batch, say)
        _collect(client, batch_id, run, strategies or {})
    run.elapsed_seconds = time.monotonic() - started
    return run


def run_batch(
    items: Sequence[ImageRequest],
    *,
    api_key: Optional[str] = None,
    client=None,
    poll_seconds: int = DEFAULT_POLL_SECONDS,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    log: Optional[Callable[[str], None]] = None,
    on_submit: Optional[Callable[[str], None]] = None,
) -> BatchRun:
    """Identify every image in one submission. Blocks until the batch ends.

    Returns an `Outcome` for every `custom_id` submitted, whatever happened to it.

    `on_submit` is called with each batch id the instant the API returns it and BEFORE the
    first poll. That ordering is the whole point: a script that dies during a four-hour
    poll must be able to reattach rather than pay again, and an id persisted after the poll
    is an id you do not have when you need it.
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

    # THE REFUSALS, BEFORE THE CLIENT EXISTS. A request whose strategy no profile answers
    # is excluded from submission under its own status code — never sent under another
    # game's prompt, never dropped. Checked ahead of `_client` so a run of nothing but
    # refusals answers without credentials or the SDK, exactly like an empty one.
    sendable: List[ImageRequest] = []
    for item in items:
        refusal = prompt_refusal(item.custom_id, item.strategy)
        if refusal is None:
            sendable.append(item)
        else:
            run.outcomes[item.custom_id] = refusal
    strategies = {item.custom_id: item.strategy for item in sendable}

    if sendable:
        client = client or _client(api_key)
    started = time.monotonic()

    for chunk in _chunks(sendable):
        requests = [build_request(item) for item in chunk]
        try:
            batch = client.messages.batches.create(requests=requests)
        except Exception as exc:
            raise BatchError(f"batch create failed: {exc}") from exc

        run.batch_ids.append(batch.id)
        if on_submit is not None:
            on_submit(batch.id)
        say(f"submitted {len(requests)} requests as {batch.id}")

        batch = _await_end(client, batch.id, poll_seconds, timeout_seconds, say)
        _say_counts(batch, say)
        _collect(client, batch.id, run, strategies)

    # Closure: everything submitted is accounted for, matched or reported.
    for item in items:
        if item.custom_id not in run.outcomes:
            run.outcomes[item.custom_id] = Outcome(
                item.custom_id, "absent", error="no result returned for this request"
            )

    run.elapsed_seconds = time.monotonic() - started
    return run
