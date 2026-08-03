"""Cache one T1 identification run so `make harness` stays a check, not a bill.

The harness must be cheap enough to run before every commit — that is the whole reason
the project can be driven unattended. A Batch API round trip per invocation would make
it something you skip, and a skipped check is worse than a slow one.

So a run is keyed by everything that could change its answer: the prompt contract
fingerprint (model, system prompt, both user turns, schema), the fixture fingerprint
(exactly which cards, with which labels), and whether set hints were supplied. Change any
of those and the key changes and the batch re-runs. Change nothing and T1 re-scores the
stored answers offline, which is also what makes the committed score in
`harness/results/` reproducible rather than a snapshot of one afternoon's API mood.

`PKMNSCAN_RERUN_T1=1` forces a fresh submission regardless.

Gitignored, like the images: it is derived data, reproducible from the API, and the
artefact worth committing is the score in `harness/results/`, not the raw responses.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from identify import batch, prompt

CACHE_DIR = Path(__file__).resolve().parents[2] / "harness" / ".cache" / "t1"


def cache_key(prompt_id: str, fixture_id: str, set_hint_mode: str) -> str:
    payload = "|".join([prompt_id, fixture_id, set_hint_mode])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _path(key: str) -> Path:
    return CACHE_DIR / "{0}.json".format(key)


def forced() -> bool:
    return os.environ.get("PKMNSCAN_RERUN_T1") == "1"


def load(key: str) -> Optional[Dict[str, object]]:
    """The stored run, with outcomes rebuilt through the live parser.

    Re-parsing rather than storing parsed fields is deliberate: a parser change has to
    re-prove itself against the stored raw responses instead of inheriting yesterday's
    verdict.
    """
    path = _path(key)
    if not path.is_file():
        return None
    try:
        stored = json.loads(path.read_text("utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    outcomes: Dict[str, batch.Outcome] = {}
    for custom_id, record in (stored.get("outcomes") or {}).items():
        status = record.get("status", "absent")
        if status != batch.SUCCEEDED:
            outcomes[custom_id] = batch.Outcome(
                custom_id, status, error=record.get("error")
            )
            continue
        try:
            identification = prompt.parse(record["raw"])
        except (prompt.MalformedIdentification, KeyError) as exc:
            outcomes[custom_id] = batch.Outcome(custom_id, "malformed", error=str(exc))
            continue
        outcomes[custom_id] = batch.Outcome(
            custom_id, batch.SUCCEEDED, identification=identification
        )

    run = batch.BatchRun(
        outcomes=outcomes,
        batch_ids=list(stored.get("batch_ids") or []),
        usage=batch.Usage(
            input_tokens=int((stored.get("usage") or {}).get("input_tokens", 0)),
            output_tokens=int((stored.get("usage") or {}).get("output_tokens", 0)),
        ),
        elapsed_seconds=float(stored.get("elapsed_seconds") or 0.0),
    )
    return {"run": run, "submitted_at": stored.get("submitted_at", "unknown")}


def save(key: str, run: batch.BatchRun) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    outcomes = {}
    for custom_id, outcome in run.outcomes.items():
        record: Dict[str, object] = {"status": outcome.status}
        if outcome.identification is not None:
            record["raw"] = outcome.identification.raw
        if outcome.error:
            record["error"] = outcome.error
        outcomes[custom_id] = record

    path = _path(key)
    path.write_text(
        json.dumps(
            {
                "submitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "batch_ids": run.batch_ids,
                "elapsed_seconds": round(run.elapsed_seconds, 1),
                "usage": {
                    "input_tokens": run.usage.input_tokens,
                    "output_tokens": run.usage.output_tokens,
                },
                "outcomes": outcomes,
            },
            indent=2,
            sort_keys=True,
        ),
        "utf-8",
    )
    return path
