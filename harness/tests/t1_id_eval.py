"""T1 — Ground-truth ID eval.

Official card images from pokemontcg.io across SV-era sets — sample size and set count
are EVAL_IMAGE_TARGET and MIN_EVAL_SETS below — identified through the
Anthropic Batch API, scored against the API records that supplied them. The API record
IS the label, so there is no hand-labelling step and no way for the answer key to drift
from the images.

Pass: holdout_accuracy >= 0.95.

A card counts as correct when BOTH halves of what the join actually consumes are right:

  name        normalized for typography only (case, accents, curly apostrophes, dashes).
              "Iron Valiant ex" and "Iron Valiant" stay different cards.
  join key    `pipeline.join.join_key(number, printed_total)` — the real function, not a
              re-implementation. Scoring the key rather than the two fields separately
              means T1 measures the thing that decides whether a card finds its catalog
              row, and a model that reads "25" where the card prints "025" is correctly
              scored as right, because zero-padding is the key builder's job.

Known blind spot (docs/GATES.md): official API images are flat renders with no foil
texture, so T1 CANNOT validate the `finish` field. Gate B did that job on 2026-08-22, on
all 53 real photographs rather than the ~10 planned, and the answer was a 30% false
positive rate — 16 normals read as foil, systematically, under the rig's lighting. T1 is
still blind to it and will stay green while that rate is anything at all.
Rather than leave that implicit, the prompt lets the model answer `unknown` and
the results file records the finish distribution — so a green T1 alongside nothing but
`unknown` finishes reads as "variant detection untested", which is the truth, instead of
looking like variant detection working.

Cost and time: the run is cached by prompt fingerprint + fixture fingerprint (see
`harness/eval/runcache.py`), so a normal `make harness` re-scores stored responses
offline and makes no API call. Editing the prompt changes the fingerprint and re-submits
automatically; `PKMNSCAN_RERUN_T1=1` forces it.

Below the floor, tune the prompt directly — nothing external gates that (changed
2026-08-03; the Scan & Identify comparison is parked in DECISIONS.md's Someday list). The
one discipline that does apply: never tune against the cards you then score on. Fixing the
specific images that failed and re-measuring on the same set produces a number that says
nothing about the next card, which is the only thing the number is for.
"""

from __future__ import annotations

import json
import os
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from harness.eval import fixtures, runcache
from harness.tests import Checks, Result
from identify import batch, prompt
from pipeline import join

NAME = "T1"
DESCRIPTION = "Ground-truth ID eval against pokemontcg.io images"
PASS_CRITERIA = "holdout_accuracy >= 0.95"

ID_ACCURACY_FLOOR = 0.95
MIN_EVAL_SETS = 3
EVAL_IMAGE_TARGET = 150

RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"

# D2 — the set hint is an optional accelerator recorded at capture, and identification
# has to work without it. T1 scores the unhinted path so the number is the floor, not the
# best case. Flip with PKMNSCAN_T1_SET_HINT=1 to measure what the hint is worth.
SET_HINT_ENV = "PKMNSCAN_T1_SET_HINT"

# Restrict a run to one split. Prompt iteration uses `tune` — it halves the upload and,
# more importantly, keeps the holdout from being consulted on every attempt, which is
# itself a slow way of fitting to it.
SPLIT_ENV = "PKMNSCAN_T1_SPLIT"

# The holdout's card-level failures are deliberately NOT printed. The gate is the holdout
# score; the moment the tuner can read which holdout cards failed, the holdout has become
# tuning data and the number stops measuring generalisation. Details still go to the
# results JSON so a human can inspect them — that is the human's call to make, not the
# tuner's. Set this to opt in explicitly.
REVEAL_ENV = "PKMNSCAN_T1_REVEAL_HOLDOUT"


class Score:
    """One card's verdict, kept alongside enough context to explain a miss."""

    __slots__ = ("card", "outcome", "name_ok", "key_ok")

    def __init__(self, card, outcome, name_ok: bool, key_ok: bool):
        self.card = card
        self.outcome = outcome
        self.name_ok = name_ok
        self.key_ok = key_ok

    @property
    def correct(self) -> bool:
        return self.name_ok and self.key_ok

    @property
    def expected_key(self) -> str:
        return join.join_key(self.card.number, self.card.printed_total)

    @property
    def actual_key(self) -> Optional[str]:
        ident = self.outcome.identification
        if ident is None or not ident.has_number:
            return None
        return join.join_key(ident.number, ident.printed_total)

    def explain(self) -> str:
        ident = self.outcome.identification
        if ident is None:
            return "{0}  {1}: {2}".format(
                self.card.card_id, self.outcome.status, self.outcome.error or "no result"
            )
        parts = []
        if not self.name_ok:
            parts.append("name {0!r} != {1!r}".format(ident.name, self.card.name))
        if not self.key_ok:
            parts.append("key {0} != {1}".format(self.actual_key, self.expected_key))
        return "{0}  {1}  ({2})".format(
            self.card.card_id, "; ".join(parts), ident.confidence
        )


def _set_hint_mode() -> str:
    return "set_hint" if os.environ.get(SET_HINT_ENV) == "1" else "none"


def _image_requests(cards, hint_mode: str) -> List[batch.ImageRequest]:
    import base64

    requests = []
    for card in cards:
        requests.append(
            batch.ImageRequest(
                custom_id=card.card_id,
                media_type=card.media_type,
                data_b64=base64.standard_b64encode(card.path.read_bytes()).decode("ascii"),
                set_hint=card.set_name if hint_mode == "set_hint" else None,
            )
        )
    return requests


def _score(cards, run: batch.BatchRun) -> List[Score]:
    scores = []
    for card in cards:
        outcome = run.outcomes.get(
            card.card_id,
            batch.Outcome(card.card_id, "absent", error="no result returned"),
        )
        ident = outcome.identification
        if ident is None:
            scores.append(Score(card, outcome, False, False))
            continue
        name_ok = prompt.normalize_name(ident.name) == prompt.normalize_name(card.name)
        key_ok = ident.has_number and join.join_key(
            ident.number, ident.printed_total
        ) == join.join_key(card.number, card.printed_total)
        scores.append(Score(card, outcome, name_ok, bool(key_ok)))
    return scores


def _per_set(scores: List[Score]) -> "OrderedDict[str, Dict[str, object]]":
    buckets: "OrderedDict[str, Dict[str, object]]" = OrderedDict()
    for score in scores:
        bucket = buckets.setdefault(
            score.card.set_id,
            {"set_name": score.card.set_name, "total": 0, "correct": 0},
        )
        bucket["total"] = int(bucket["total"]) + 1
        if score.correct:
            bucket["correct"] = int(bucket["correct"]) + 1
    for bucket in buckets.values():
        bucket["accuracy"] = round(int(bucket["correct"]) / int(bucket["total"]), 4)
    return buckets


def _write_results(payload: dict, hint_mode: str) -> Tuple[Path, bool]:
    """One file per configuration. The suffix matters: a hinted run and an unhinted run
    are different measurements, and letting them share a filename means whichever ran
    last silently becomes 'the' committed score.

    The filename carries no date, and that is the fix for a hole the rule below had from
    the start: the dedupe compares against the file it is about to write, so a new UTC
    date meant a new filename, a missing file, and an unconditional write. One measurement
    accumulated one file per day the harness ran — 2026-08-03 and 2026-08-04 were committed
    as byte-identical twins. The date lives in `generated_at` inside the payload; git holds
    the history, which is what "so regressions are visible in the diff" always meant.

    Returns (path, wrote). A cached re-scoring recomputes nothing, so it must not dirty
    a committed score: if the only field that would change is `generated_at`, the file
    is left exactly as it was. Otherwise every `make harness` produces a one-line diff
    on a tracked file, and the log stops being able to tell a real re-measurement from
    a timestamp bump — which is the one question `harness/results/` exists to answer.

    The comparison covers everything else in the payload, `batch_ids` and `usage`
    included, so the discrimination lands where it should: replaying cached responses
    reproduces those byte for byte, while a fresh submission carries new batch ids and
    is written even if the accuracy happens to come out identical. The kept timestamp is
    the one from the run that actually produced the number, which is the more truthful
    of the two anyway."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "" if hint_mode == "none" else "-{0}".format(hint_mode)
    path = RESULTS_DIR / "t1{0}.json".format(suffix)

    if path.exists():
        try:
            existing = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            existing = None  # unreadable or corrupt: overwrite it, that IS a change
        if isinstance(existing, dict) and _same_measurement(existing, payload):
            return path, False

    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")
    return path, True


def _same_measurement(existing: dict, payload: dict) -> bool:
    """Everything but `generated_at`. A timestamp is not a finding."""
    return {k: v for k, v in existing.items() if k != "generated_at"} == {
        k: v for k, v in payload.items() if k != "generated_at"
    }


def run() -> Result:
    checks = Checks()
    notes: List[str] = []
    say = notes.append

    hint_mode = _set_hint_mode()

    try:
        cards = fixtures.load(log=say)
    except fixtures.FixtureError as exc:
        return Result(False, "eval images unavailable: {0}".format(exc))

    if not cards:
        return Result(False, "eval images unavailable: fixture set is empty")

    wanted = os.environ.get(SPLIT_ENV, "").strip().lower()
    if wanted in (fixtures.TUNE, fixtures.HOLDOUT):
        cards = [card for card in cards if card.split == wanted]
        say("restricted to the {0} split: {1} images".format(wanted, len(cards)))
    elif wanted:
        return Result(
            False,
            "{0}={1!r} is not a split — use {2!r} or {3!r}".format(
                SPLIT_ENV, wanted, fixtures.TUNE, fixtures.HOLDOUT
            ),
        )

    prompt_id = prompt.prompt_fingerprint()
    fixture_id = fixtures.fixture_fingerprint(cards)
    key = runcache.cache_key(prompt_id, fixture_id, hint_mode)

    cached = None if runcache.forced() else runcache.load(key)
    if cached is not None:
        run_result: batch.BatchRun = cached["run"]  # type: ignore[assignment]
        source = "cached run {0}".format(cached["submitted_at"])
    else:
        try:
            run_result = batch.run_batch(_image_requests(cards, hint_mode), log=say)
        except batch.BatchError as exc:
            return Result(
                False,
                "identification did not run: {0}\n"
                "      T1 needs an Anthropic key: export ANTHROPIC_API_KEY, or put\n"
                "      ANTHROPIC_API_KEY=sk-ant-... in .env (gitignored).\n"
                "      Nothing is scored without it — a skipped eval must not read "
                "as a pass.".format(exc),
            )
        runcache.save(key, run_result)
        source = "fresh batch {0}".format(", ".join(run_result.batch_ids) or "?")

    scores = _score(cards, run_result)
    correct = sum(1 for score in scores if score.correct)
    total = len(scores)
    accuracy = correct / total
    per_set = _per_set(scores)
    finishes = Counter(
        (score.outcome.identification.detected_finish or prompt.UNKNOWN_FINISH)
        if score.outcome.identification
        else "no-result"
        for score in scores
    )

    by_split = {
        name: [s for s in scores if s.card.split == name]
        for name in (fixtures.TUNE, fixtures.HOLDOUT)
    }
    split_stats = {
        name: {
            "images": len(group),
            "correct": sum(1 for s in group if s.correct),
            "accuracy": round(sum(1 for s in group if s.correct) / len(group), 4)
            if group
            else None,
        }
        for name, group in by_split.items()
    }
    # WHICH SPLIT THE GATE READS IS DECIDED ONCE, HERE, AND EVERY OTHER MENTION DERIVES
    # FROM IT. Not a style preference — this line and the two that report it used to name
    # `fixtures.HOLDOUT` independently, so moving the gate to the tune half left `gated_on`
    # saying "holdout", the tune accuracy stored under `holdout_accuracy`, and stdout still
    # printing "<- the gate" beside the holdout row. Three published surfaces agreeing with
    # each other and none of them with the code. Anything that records or labels the gate
    # reads `gated_split`, so a change here cannot leave a stale label behind.
    #
    # THE RULE FOR SPOTTING THE NEXT ONE, because this class has now survived two fixes
    # that each added a reference instead of removing one: repeated reads of a single name
    # are fine — a change tracks everywhere. The defect is two independent DECISIONS that
    # must agree. `ARTICUNO` used in fourteen assertions is one name; a selection saying
    # HOLDOUT and a label saying HOLDOUT are two decisions, and only one of them moves.
    gated_split = fixtures.HOLDOUT
    holdout = split_stats[gated_split]
    # The gate reads the holdout. A run that did not score the holdout cannot clear it —
    # a partial run is a development convenience, never a verdict.
    gate_accuracy = holdout["accuracy"]

    payload = {
        "test": NAME,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": prompt.MODEL,
        "transport": "anthropic.messages.batches",
        "prompt_fingerprint": prompt_id,
        "fixture_fingerprint": fixture_id,
        "set_hint_mode": hint_mode,
        "image_count": total,
        "set_count": len(per_set),
        "split_requested": os.environ.get(SPLIT_ENV, "all"),
        "splits": split_stats,
        "gated_on": gated_split,
        "holdout_accuracy": gate_accuracy,
        "overall_accuracy": round(accuracy, 4),
        "accuracy_floor": ID_ACCURACY_FLOOR,
        "passed": gate_accuracy is not None and gate_accuracy >= ID_ACCURACY_FLOOR,
        "per_set": per_set,
        "name_correct": sum(1 for score in scores if score.name_ok),
        "join_key_correct": sum(1 for score in scores if score.key_ok),
        "finish_distribution": dict(sorted(finishes.items())),
        "finish_note": (
            "T1 cannot validate `finish` — official API images are flat renders with no "
            "foil texture. Gate B measured it on real photos 2026-08-22: 16 of 53 normals "
            "read as foil, a 30% false-positive rate under the rig's lighting. T1 stays "
            "green regardless. See docs/GATES.md."
        ),
        "batch_ids": run_result.batch_ids,
        "usage": {
            "input_tokens": run_result.usage.input_tokens,
            "output_tokens": run_result.usage.output_tokens,
        },
        # Split apart, because they are read by different people for different reasons.
        # `tune_misses` is what prompt work is allowed to look at. `holdout_misses` is
        # recorded so a human can audit a regression, and is never printed to stdout —
        # see REVEAL_ENV.
        "tune_misses": [
            s.explain() for s in by_split[fixtures.TUNE] if not s.correct
        ],
        "holdout_misses": [
            s.explain() for s in by_split[fixtures.HOLDOUT] if not s.correct
        ],
    }
    results_path, results_written = _write_results(payload, hint_mode)

    for line in notes:
        checks.note(line)
    checks.note("")
    checks.note(
        "{0} images · {1} sets · {2} · prompt {3} · fixtures {4} · set hint: {5}".format(
            total, len(per_set), prompt.MODEL, prompt_id, fixture_id, hint_mode
        )
    )
    checks.note(source)
    checks.note("")
    for set_id, bucket in per_set.items():
        checks.note(
            "{0:<8} {1:<22} {2:>2}/{3:<2}  {4:.3f}".format(
                set_id,
                str(bucket["set_name"])[:22],
                bucket["correct"],
                bucket["total"],
                bucket["accuracy"],
            )
        )
    checks.note(
        "{0:<8} {1:<22} {2:>3}/{3:<3} {4:.3f}".format(
            "all sets", "", correct, total, accuracy
        )
    )
    checks.note("")
    for name in (fixtures.TUNE, fixtures.HOLDOUT):
        stat = split_stats[name]
        marker = "  <- the gate" if name == gated_split else ""
        checks.note(
            "{0:<8} {1:<22} {2:>3}/{3:<3} {4}{5}".format(
                name,
                "",
                stat["correct"],
                stat["images"],
                "{0:.3f}".format(stat["accuracy"]) if stat["accuracy"] is not None else "  n/a",
                marker,
            )
        )
    checks.note("")
    checks.note(
        "name only {0}/{1} · join key only {2}/{3}".format(
            payload["name_correct"], total, payload["join_key_correct"], total
        )
    )
    checks.note(
        "finish detected: {0}   (T1 blind spot — see docs/GATES.md)".format(
            ", ".join("{0} {1}".format(k, v) for k, v in sorted(finishes.items()))
        )
    )
    if payload["tune_misses"]:
        checks.note("")
        checks.note("tune misses ({0}) — prompt work reads these:".format(
            len(payload["tune_misses"])
        ))
        for miss in payload["tune_misses"]:
            checks.note("  " + miss)
    holdout_misses = payload["holdout_misses"]
    if holdout_misses:
        checks.note("")
        if os.environ.get(REVEAL_ENV) == "1":
            checks.note("holdout misses ({0}) — REVEALED, this run is now tuning data:".format(
                len(holdout_misses)
            ))
            for miss in holdout_misses:
                checks.note("  " + miss)
        else:
            checks.note(
                "holdout misses: {0} — card detail withheld on purpose. It is in the "
                "results JSON for a human; reading it to fix the prompt turns the "
                "holdout into tuning data and voids the number.".format(
                    len(holdout_misses)
                )
            )
    checks.note("")

    checks.ok(
        len(per_set) >= MIN_EVAL_SETS,
        "sampled {0} sets (spec: >= {1})".format(len(per_set), MIN_EVAL_SETS),
    )
    checks.ok(
        total >= EVAL_IMAGE_TARGET,
        "{0} images scored (spec: >= {1})".format(total, EVAL_IMAGE_TARGET),
        "a partial run cannot clear the gate — drop {0} to score everything".format(
            SPLIT_ENV
        ),
    )
    checks.ok(
        not run_result.failed,
        "every submitted image returned a result",
        "\n".join(
            "{0}: {1}".format(o.custom_id, o.error) for o in run_result.failed[:10]
        ),
    )
    checks.ok(
        gate_accuracy is not None and gate_accuracy >= ID_ACCURACY_FLOOR,
        "holdout accuracy {0} >= {1}".format(
            "{0:.4f}".format(gate_accuracy) if gate_accuracy is not None else "not measured",
            ID_ACCURACY_FLOOR,
        ),
        "tune against the tune split only — the holdout is the measurement, not the "
        "target (docs/GATES.md T1)",
    )
    # The results file is tracked, so a re-scoring that recomputes nothing must leave it
    # alone — otherwise every harness run puts a timestamp diff in the log and a real
    # re-measurement stops being visible among them. Checked here rather than left to
    # `git status`, because the whole point is that nobody has to notice.
    checks.ok(
        _same_measurement(payload, {**payload, "generated_at": "1970-01-01T00:00:00+00:00"}),
        "a timestamp alone is not a new measurement",
    )
    checks.ok(
        not _same_measurement(payload, {**payload, "holdout_accuracy": -1.0}),
        "...but a changed score is, and rewrites the file",
    )
    checks.note(
        "score {0} {1}".format(
            "written to" if results_written else "unchanged, already at",
            results_path.relative_to(RESULTS_DIR.parents[1]),
        )
    )

    return checks.result()
