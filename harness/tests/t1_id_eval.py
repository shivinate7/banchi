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
offline and makes no API call.

NOTHING HERE EVER SUBMITS ON ITS OWN, and this paragraph used to say the opposite —
"editing the prompt changes the fingerprint and re-submits automatically", which was
already false when it was written, because the fingerprint check in `run()` refuses
instead. A cache miss of ANY cause now refuses the same way: a moved prompt, a fresh git
worktree that `harness/.cache/` did not travel to, a cleared cache. `PKMNSCAN_RERUN_T1=1`
is the one way a submission happens, because this test runs under the Stop hook at the end
of every turn and a turn end must not be able to spend money.

Two A/B knobs, both off by default so the gate scores the floor: `PKMNSCAN_T1_SET_HINT=1`
(D2 — what is the set hint worth) and `PKMNSCAN_T1_RARITY=1` (D23 job (c) — what is the
rarity-claim clause worth, with the fixture's own rarity as a perfectly-sorted one-element
claim). Each writes its own results file; see RARITY_ENV below for the both-directions
warning a claimed run must be read under.

Below the floor, tune the prompt directly — nothing external gates that (changed
2026-08-03; the Scan & Identify comparison is parked in DECISIONS.md's Someday list). The
one discipline that does apply: never tune against the cards you then score on. Fixing the
specific images that failed and re-measuring on the same set produces a number that says
nothing about the next card, which is the only thing the number is for.
"""

from __future__ import annotations

import hashlib
import inspect
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

# THE FINGERPRINT THE COMMITTED SCORE WAS MEASURED UNDER, asserted as a literal rather than
# recomputed, because a check that recomputes both sides of a comparison proves nothing.
# `harness/results/t1.json` records this same string beside `holdout_accuracy`; the two are
# one measurement, and a run whose prompt hashes to anything else is scoring a different
# contract than the number in that file.
#
# IT IS HERE TO MAKE A REFACTOR CHEAP AND A PROMPT CHANGE DELIBERATE. Per-game prompt
# dispatch moved `SYSTEM_PROMPT`, both user turns and the schema into a `Profile` and moved
# nothing else; this line is what proves the "and moved nothing else" half, at no cost. It
# is NOT an argument against changing the prompt — docs/GATES.md says to rerun after any
# prompt change, and doing so means editing this constant to the new hash in the same commit
# as the re-measured `harness/results/t1.json`. What it stops is the OTHER thing: a wording
# tidy nobody meant as a change, silently invalidating every cached run and re-submitting
# 150 images at the end of a turn.
PROMPT_FINGERPRINT = "1ef974bf511d"

RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"

# D2 — the set hint is an optional accelerator recorded at capture, and identification
# has to work without it. T1 scores the unhinted path so the number is the floor, not the
# best case. Flip with PKMNSCAN_T1_SET_HINT=1 to measure what the hint is worth.
SET_HINT_ENV = "PKMNSCAN_T1_SET_HINT"

# D23 job (c) — the rarity-claim clause, A/B-gated the same shape as the set hint. Flip
# with PKMNSCAN_T1_RARITY=1: every card is claimed as its OWN true rarity from the fixture
# record, a one-element list — a perfectly sorted stack, the best case the feature can
# ever see. The default run stays claimless, so the gate keeps scoring the floor.
#
# WATCH BOTH DIRECTIONS (DECISIONS.md, Someday): a clause that raises accuracy but also
# raises confidence on wrong answers is a bad trade, because it converts review-queue
# taps into silently mislisted cards. That is why a claimed run's results file records
# `miss_confidence` beside its accuracy — the second number is the price of the first.
RARITY_ENV = "PKMNSCAN_T1_RARITY"

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


def _rarity_on() -> bool:
    return os.environ.get(RARITY_ENV) == "1"


def _config(hint_mode: str, rarity_on: bool) -> str:
    """The configuration name: cache-key component and results-file suffix in one.

    "none" and "set_hint" are the two names that already exist and must not move — they
    are baked into banked cache keys and the committed results filenames. A claimed run
    appends "rarity", so each combination keeps GATES.md's rule: one file per
    configuration, never shared, no date in the name.
    """
    parts = [] if hint_mode == "none" else [hint_mode]
    if rarity_on:
        parts.append("rarity")
    return "-".join(parts) or "none"


def _image_requests(cards, hint_mode: str, rarity_on: bool) -> List[batch.ImageRequest]:
    import base64

    requests = []
    for card in cards:
        requests.append(
            batch.ImageRequest(
                custom_id=card.card_id,
                media_type=card.media_type,
                data_b64=base64.standard_b64encode(card.path.read_bytes()).decode("ascii"),
                set_hint=card.set_name if hint_mode == "set_hint" else None,
                # The card's own true rarity as a one-element claim — see RARITY_ENV. A
                # fixture record with no rarity string claims nothing, which is also what
                # production does for a card with no claim in its sidecar.
                rarity_claim=(card.rarity,) if rarity_on and card.rarity else None,
            )
        )
    return requests


def _miss_confidence(scores: List[Score]) -> Dict[str, int]:
    """How confident the model was on the cards it got WRONG. The second axis of the
    rarity A/B: an accuracy gain paid for with more high-confidence misses is the trade
    DECISIONS.md's Someday entry warns about, and it is invisible in the accuracy alone."""
    counter = Counter(
        score.outcome.identification.confidence
        if score.outcome.identification
        else "no-result"
        for score in scores
        if not score.correct
    )
    return dict(sorted(counter.items()))


def scorer_fingerprint() -> str:
    """Stable hash of the code that turns banked answers into the committed number.

    WHY THIS EXISTS, AND IT IS THE THING THAT LETS THE REPLAY STOP RUNNING. Between two turns
    nothing about this test can change except its inputs and its arithmetic. The prompt and the
    fixture set already have fingerprints; the ARITHMETIC did not, so re-deriving the score on
    every run was the only thing standing between an edited scorer and a stale committed number.
    Hashing it makes that guard explicit and free — a replay proves the same fact once, and
    afterwards the fingerprints prove it costs nothing (D112).

    THE SOURCE OF THESE FUNCTIONS, NOT OF THE FILE. Hashing the module would make every comment
    edit in it demand a fresh $-costing measurement, which is the trap `prompt_fingerprint`
    already documents avoiding for the crop-retry turn. What is hashed is exactly what decides a
    verdict: the per-card comparison, the per-set aggregation, the holdout split, and the floor
    the gate reads.
    """
    parts = [
        inspect.getsource(_score),
        inspect.getsource(_per_set),
        inspect.getsource(Score.correct.fget),
        repr(ID_ACCURACY_FLOOR),
    ]
    payload = "\n".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]


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


def _write_results(payload: dict, config: str) -> Tuple[Path, bool]:
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
    suffix = "" if config == "none" else "-{0}".format(config)
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


def _banked_result(config: str = "none") -> Optional[dict]:
    """The committed measurement for this configuration, or None if there is not one."""
    suffix = "" if config == "none" else "-{0}".format(config)
    path = RESULTS_DIR / "t1{0}.json".format(suffix)
    if not path.is_file():
        return None
    try:
        found = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    return found if isinstance(found, dict) else None


def run() -> Result:
    checks = Checks()
    notes: List[str] = []
    say = notes.append

    hint_mode = _set_hint_mode()
    rarity_on = _rarity_on()
    config = _config(hint_mode, rarity_on)

    # FIRST, BEFORE ANY IMAGE IS LOADED AND LONG BEFORE ANYTHING COULD BE SUBMITTED. The
    # cache key is built from this hash, so a moved fingerprint is a guaranteed cache miss
    # and a guaranteed re-submission — at the end of every turn, under the Stop hook. Checked
    # up here, the answer is free; checked after `run_batch`, the money is already spent.
    if not checks.equal(
        prompt.prompt_fingerprint(), PROMPT_FINGERPRINT, "the scored prompt is unmoved"
    ):
        return checks.result(
            "  the prompt changed and no re-measurement was recorded.\n"
            "       Rerun deliberately (docs/GATES.md), then set PROMPT_FINGERPRINT to the\n"
            "       new hash in the same commit as the new harness/results/t1.json.\n"
            "       Stopping here rather than re-submitting 150 images on a cache miss."
        )

    # THE COMMITTED MEASUREMENT, ASSERTED WITHOUT RE-DERIVING IT. Between two turns nothing
    # here can change but the prompt, the fixture set and the arithmetic — the model is pinned,
    # the answers are banked, the labels are tracked. All three now have fingerprints, so when
    # they agree with what `harness/results/t1.json` was generated under, replaying the cache
    # can only reproduce the number already committed beside them. It ran on every turn under
    # the Stop hook and produced the same 2026-08-23 figure every time, at the price of needing
    # a 133M image mirror to be present at all (D112).
    #
    # THIS IS NOT A SKIP AND MUST NOT READ AS ONE. Nothing is assumed: three hashes are compared
    # and the committed result is held to its own floor. A mismatch on any of them falls through
    # to the real replay below, which is where the money and the images are.
    banked = None if runcache.forced() else _banked_result(config)
    cards = fixtures.labels()
    if banked is not None and cards is not None:
        fixture_now = fixtures.fixture_fingerprint(cards)
        scorer_now = scorer_fingerprint()
        agreed = (
            banked.get("fixture_fingerprint") == fixture_now
            and banked.get("scorer_fingerprint") == scorer_now
            and banked.get("prompt_fingerprint") == PROMPT_FINGERPRINT
        )
        if agreed:
            checks.equal(fixture_now, banked["fixture_fingerprint"], "the eval set is unmoved")
            checks.equal(scorer_now, banked["scorer_fingerprint"], "the scorer is unmoved")
            floor = float(banked.get("accuracy_floor", ID_ACCURACY_FLOOR))
            holdout = banked.get("holdout_accuracy")
            checks.ok(
                isinstance(holdout, (int, float)) and holdout >= floor,
                "the committed holdout clears its floor ({0} >= {1})".format(holdout, floor),
            )
            say("replayed nothing: prompt, eval set and scorer all agree with")
            say("harness/results/t1.json, generated {0}".format(banked.get("generated_at")))
            say("{0} images · {1} · holdout {2}".format(
                banked.get("image_count"), banked.get("model"), holdout))
            say("re-measure deliberately: PKMNSCAN_RERUN_T1=1 make harness (docs/GATES.md)")
            return checks.result()

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
    # The claimed configuration folds the clause's own fingerprint into its key, so a
    # reworded clause invalidates the claimed run's cache and leaves the default (and
    # hinted) runs warm — the same reason the prompt fingerprint is in the key at all.
    rarity_id = prompt.rarity_fingerprint() if rarity_on else ""
    key = runcache.cache_key(prompt_id, fixture_id, hint_mode, extra=rarity_id)

    cached = None if runcache.forced() else runcache.load(key)
    if cached is not None:
        run_result: batch.BatchRun = cached["run"]  # type: ignore[assignment]
        source = "cached run {0}".format(cached["submitted_at"])
    elif not runcache.forced():
        # A COLD CACHE DOES NOT SUBMIT. The guard above this function's fixture load makes
        # exactly this argument — "a guaranteed cache miss and a guaranteed re-submission —
        # at the end of every turn, under the Stop hook" — and then guards ONE cause of a
        # cold cache, a moved prompt fingerprint. There are others, and they are not
        # hypothetical: `harness/.cache/` is gitignored, so it does not travel to a git
        # worktree, and a fresh worktree with a key in the environment would submit 150
        # images at the end of every turn until one run happened to warm it. Found on
        # 2026-08-29 in exactly that state; nothing was spent only because that worktree
        # also lacked the key, which is luck rather than a design.
        #
        # So the rule is the cause-independent one the comment above was already reaching
        # for: replaying is automatic, SUBMITTING IS AN ACT. `PKMNSCAN_RERUN_T1=1` is that
        # act and already existed — this branch does not invent a flag, it stops the flag
        # from being bypassable by an empty directory. Every legitimate path is unchanged:
        # forced still submits, a warm cache still replays, and the only behaviour that
        # goes away is the one nobody ever chose.
        return Result(
            False,
            "no cached run for this configuration, and a cold cache does not submit.\n"
            "      Replaying is free and automatic; submitting ~150 images is not, so it\n"
            "      is never something a Stop hook does on its own.\n"
            "      If this is a git worktree, it is missing harness/.cache/ — copy it from\n"
            "      the main working tree (`make worktree-setup`) rather than paying twice\n"
            "      for an answer this machine already has.\n"
            "      To genuinely re-measure, PKMNSCAN_RERUN_T1=1 make harness — deliberately,\n"
            "      and per docs/GATES.md commit the new harness/results/t1.json with it.",
        )
    else:
        try:
            run_result = batch.run_batch(
                _image_requests(cards, hint_mode, rarity_on), log=say
            )
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
        "scorer_fingerprint": scorer_fingerprint(),
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
    if rarity_on:
        # The claimed configuration's own record: which clause wording it ran under, what
        # was claimed, and the both-directions number — accuracy is above, and this is
        # what it cost in confidence-on-misses. Keys added ONLY in this configuration, so
        # the default file (the committed score) keeps its exact shape and a warm
        # re-scoring of it stays byte-identical.
        payload["rarity_claim_mode"] = "true_rarity"
        payload["rarity_fingerprint"] = rarity_id
        payload["rarity_claimed"] = sum(1 for card in cards if card.rarity)
        payload["miss_confidence"] = {
            name: _miss_confidence(group) for name, group in by_split.items()
        }
    results_path, results_written = _write_results(payload, config)

    for line in notes:
        checks.note(line)
    checks.note("")
    checks.note(
        "{0} images · {1} sets · {2} · prompt {3} · fixtures {4} · set hint: {5}".format(
            total, len(per_set), prompt.MODEL, prompt_id, fixture_id, hint_mode
        )
    )
    if rarity_on:
        checks.note(
            "rarity claims: true rarity on {0}/{1} cards · clause {2} · this is the "
            "A/B configuration, not the gate's floor".format(
                payload["rarity_claimed"], total, rarity_id
            )
        )
        checks.note(
            "miss confidence — {0}".format(
                "; ".join(
                    "{0}: {1}".format(
                        name,
                        ", ".join(
                            "{0} {1}".format(k, v) for k, v in dist.items()
                        )
                        or "no misses",
                    )
                    for name, dist in payload["miss_confidence"].items()
                )
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
