"""T9 — The motion trigger against real recorded rig sessions.

NEW 2026-08-31, with D81, and it exists because of one fact: `app/tests/motion.spec.ts` and
`app/tests/motion-live.spec.ts` were GREEN through all three versions of the card-present
gate, including the two that were losing cards. They could not have failed. Both draw their
own frames — synthetic arrays, a flat canvas fill — so they can only ever prove the machine
agrees with the test's own idea of a card. Until this file, nothing in the repo had ever put
the motion machine in front of a photograph.

The traces in `harness/traces/` are the only real-rig evidence this subsystem has: five
armed sessions across four rig states, saved from the HUD by the owner. Each carries every
frame's (t, d, luma) and the exact watch-region pixels of every verdict, which is what makes
a refusal re-scorable years later.

WHAT IS ASSERTED, AND THE TWO KINDS ARE NOT EQUALLY VALUABLE:

    the SEPARATION   a claim about photographs. An empty stand sits within 2 luma levels of
                     its own baseline and a card sits 17 or more away, on every rig here.
                     If this fails, something physical changed. It is what earns the test.

    the CROSS-RIG    a claim that no brightness CONSTANT can gate presence: the empty stand
    OVERLAP          on one rig is dimmer than the dimmest card on another. This is the
                     receipt for D81 and it can never stop being true of these files.

    the COUNTS       a claim about the replay's arithmetic. A tripwire for someone moving
                     `stillK` or `presenceK` without re-scoring. Legitimately updatable —
                     but as a decision, with the sweep re-run, never as a reflex.

WHAT A GREEN T9 DOES NOT MEAN. It does not mean the trigger works at the rig today. These
are five recordings of four rig states, and a sixth rig can differ from all of them — the
same honest limit T6 and T8 carry, in the same words. What it does mean is that the machine
still tells a card from an empty stand on every session anybody has ever recorded.

NO CARD IS IDENTIFIABLE IN THESE FILES and no code card is in them. A stored frame is 1,064
luma cells at 38x28 — the watch region, quantised — which cannot carry a readable QR, and
every session here is the singles feeder. T8's rule that no code-card photograph may ever be
tracked is untouched.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import statistics
from pathlib import Path

from harness.tests import Checks, Result

NAME = "T9"
DESCRIPTION = "Motion trigger against five recorded rig sessions"
PASS_CRITERIA = (
    "on every saved trace an empty stand sits within 2 of its own baseline and every card "
    "sits 17 or more away; the dimmest card on one rig is dimmer than the empty stand on "
    "another, so no brightness constant separates them; and the adaptive thresholds reach "
    "at least as many verdicts as the hand-tuned constants did live on all five"
)

# NAMED LITERALLY, resolved against the repo root, rather than composed out of `parent`
# hops. `make docs-audit`'s `tested_by reach` row asks that a test naming a component in the
# map name it in CODE — a composed path is invisible to a parse, and a docstring mention is
# prose. The map claims `harness/traces/` is tested by T9; this line is what makes that
# claim checkable rather than asserted.
ROOT = Path(__file__).resolve().parent.parent.parent
TRACES = ROOT / "harness/traces"


def _label(path: str) -> str:
    """The session's timestamp, for a check line. `harness/traces/motion-trace-<stamp>.json`
    is precise and unreadable in a column of assertions."""
    return Path(path).stem.replace("motion-trace-", "")[:19]

# THE ANSWER KEY, AND ITS PROVENANCE IS THE WHOLE POINT. Every verdict frame in all five
# traces was rendered and inspected on 2026-08-31 (`scripts/score-trace.py contact`). Only
# ONE trace contains a genuinely empty stand — the reference rig's first 5.2 seconds, before
# the feeder started — and every other verdict frame in every trace has a card in it,
# INCLUDING all 38 that the live gate refused as an empty stand.
#
# This key is written down rather than inferred because inferring it is exactly the mistake
# D81 exists to end: the 2026-08-29 fix derived its "empty stand" brightness table from
# twenty frames that were photographs of real cards, because a refusal was read as evidence
# about what was on the stand. A verdict is the machine's opinion; it is never a label.
REFERENCE = "harness/traces/motion-trace-2026-08-23T03-09-19-299Z.json"
EMPTY_BEFORE_MS = 5200

# What the machine did live, per trace, and what it should do now. The live counts are
# history and cannot change; the adaptive counts are this build's and may, deliberately.
# `arrival` is WHEN THE FIRST NEW SCENE REACHED THE LENS, read off the contact sheets on
# 2026-08-31 and written down for the same reason the labels above are. Everything before it
# is the arm-time scene or a re-settle of it, which the machine refuses BY CONSTRUCTION —
# the baseline is at zero distance from itself — and counting those as missed cards would be
# reading a correct refusal as a fault, the mirror of the mistake D81 is about. A clock
# threshold is used rather than "whatever the gate let through" because the gate is what is
# on trial here and may not supply its own answer key.
# KEYED BY FULL REPO-RELATIVE PATH rather than by basename, for two reasons that turned out
# to be the same reason. `make docs-audit`'s `tested_by reach` row asks a test to name the
# component it claims to cover in CODE, and a bare filename names nothing a parse can
# resolve. And an answer key is a set of labels attached to specific files: the moment it is
# keyed by something ambiguous, it is one careless copy away from labelling the wrong
# session, which is the whole failure D81 is about.
EXPECTED = {
    "harness/traces/motion-trace-2026-08-23T02-49-55-745Z.json": {"live": 72, "adaptive": 86, "arrival": 4000},
    "harness/traces/motion-trace-2026-08-23T03-09-19-299Z.json": {"live": 86, "adaptive": 86, "arrival": 15000},
    "harness/traces/motion-trace-2026-08-29T21-34-14-525Z.json": {"live": 20, "adaptive": 20, "arrival": 9000},
    "harness/traces/motion-trace-2026-08-29T21-38-29-293Z.json": {"live": 15, "adaptive": 15, "arrival": 12000},
    "harness/traces/motion-trace-2026-09-01T03-06-14-582Z.json": {"live": 24, "adaptive": 24, "arrival": 4000},
}


def _scorer():
    """The offline scorer, imported rather than reimplemented.

    `scripts/score-trace.py` is what a session runs by hand over a trace the owner hands
    back, and a second copy of the replay living here would drift from it silently — which
    is the failure this whole test is about, one level up. The hyphen in the filename is why
    this is importlib rather than an import statement."""
    path = Path(__file__).resolve().parent.parent.parent / "scripts" / "score-trace.py"
    spec = importlib.util.spec_from_file_location("score_trace", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cells(encoded: str) -> list[int]:
    return list(base64.b64decode(encoded))


def _distance(a: list[int], b: list[int]) -> float:
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def run() -> Result:
    checks = Checks()
    score = _scorer()

    traces = {
        path.relative_to(ROOT).as_posix(): json.loads(path.read_text())
        for path in sorted(TRACES.glob("*.json"))
    }
    checks.equal(sorted(traces), sorted(EXPECTED), "all five recorded sessions are present")
    if sorted(traces) != sorted(EXPECTED):
        return checks.result()

    # ---- the separation, on the one trace that contains a real empty stand ----------
    reference = traces[REFERENCE]
    baseline = _cells(reference["keyframes"][0]["frame"])
    empty = [_cells(k["frame"]) for k in reference["keyframes"] if k["t"] <= EMPTY_BEFORE_MS]
    empty += [_cells(e["frame"]) for e in reference["events"] if "no-card" in e["event"]]
    cards = [_cells(e["frame"]) for e in reference["events"] if e["event"] == "fire"]

    empty_far = max(_distance(frame, baseline) for frame in empty)
    card_near = min(_distance(frame, baseline) for frame in cards)
    checks.ok(
        empty_far <= 2.0,
        f"an empty stand stays within 2.0 of its own baseline ({len(empty)} frames, worst {empty_far:.2f})",
        "the presence gate's whole premise: nothing on the stand means nothing has changed",
    )
    checks.ok(
        card_near >= 17.0,
        f"every card on that rig sits 17 or more from it ({len(cards)} fires, closest {card_near:.2f})",
    )
    checks.ok(
        card_near > empty_far * 8,
        f"and the two populations are {card_near / max(empty_far, 0.01):.0f}x apart, not adjacent",
    )

    # ---- the cross-rig overlap: why no CONSTANT can do this job ---------------------
    empty_bright = max(score._quantile([float(v) for v in frame], 0.9) for frame in empty)
    dimmest = min(
        (score._quantile([float(v) for v in _cells(event["frame"])], 0.9), name, event["t"])
        for name, trace in traces.items()
        if name != REFERENCE
        for event in trace["events"]
    )
    # WRITTEN BACKWARDS THE FIRST TIME, and this test caught it: the dimmest card is not
    # dimmer than the empty stand, it is FOUR LEVELS BRIGHTER — which is the whole point.
    # Two populations four levels apart admit no threshold with margin on both sides, and
    # the constant that was in the tree sat well above the dimmer one.
    gap = dimmest[0] - empty_bright
    checks.ok(
        0 < gap <= 10,
        f"the dimmest card on another rig ({dimmest[0]:.0f}) is only {gap:.0f} levels above "
        f"this rig's empty stand ({empty_bright:.0f}) — adjacent, not separable",
        "this is D81's receipt. If it ever fails, the traces changed, not the code.",
    )
    checks.ok(
        dimmest[0] < 90,
        "and the floor that was in the tree (90) sat ABOVE that card, inside the card population",
    )

    # ---- what the constant in the tree before D81 actually cost ---------------------
    #
    # TWO NUMBERS, AND THEY ARE NOT THE SAME NUMBER — the distinction this test exists to
    # keep honest. 38 real cards were refused across three live sessions, by TWO versions of
    # the gate: 20 and 13 under the mean, 5 under the bright quantile. Re-scored through the
    # version that was in the tree on 2026-08-31, 18 of them would still be refused; the
    # 2026-08-29 quantile change rescued one session of three and left the other two broken,
    # which is the clearest statement available that a better constant was not a fix.
    # Every refusal in the corpus EXCEPT the reference trace's one genuine empty stand at
    # arm time, which is the only correct refusal anywhere in these five files.
    live_refused = sum(
        1
        for name, trace in traces.items()
        for e in trace["events"]
        if name != REFERENCE and "no-card" in e["event"]
    )
    still_refused = sum(
        1
        for name, trace in traces.items()
        for e in trace["events"]
        if name != REFERENCE
        and score._quantile([float(v) for v in _cells(e["frame"])], 0.9) < 90
    )
    checks.equal(live_refused, 38, "38 real cards were refused live, across three sessions")
    checks.equal(still_refused, 18, "18 of them would still be refused by a floor of 90")

    # ---- every card clears the distance gate, on every rig --------------------------
    for name in sorted(traces):
        trace = traces[name]
        rows = score._rows(trace)
        typical = max(1.0, statistics.median(d for _t, d, _b, _l in rows))
        floor = max(score.PRESENCE_MIN, score.PRESENCE_K * typical)
        base = _cells(trace["keyframes"][0]["frame"])
        distances = [(e["t"], _distance(_cells(e["frame"]), base)) for e in trace["events"]]
        # The arm-time scene IS the baseline, so it is at zero distance BY CONSTRUCTION and
        # is refused correctly. Only verdicts on a scene that arrived later are cards the
        # machine owed a fire to.
        arrivals = [(t, d) for t, d in distances if t > EXPECTED[name]["arrival"]]
        missed = [(round(t / 1000, 1), round(d, 2)) for t, d in arrivals if d < floor]
        checks.ok(
            not missed,
            f"{_label(name)}: every card presented after arming clears the floor "
            f"({len(arrivals)} verdicts, floor {floor:.2f})",
            f"below the floor: {missed}",
        )

    # ---- the tripwire: the replay still reaches what the sweep said it would --------
    for name in sorted(traces):
        rows = score._rows(traces[name])
        verdicts, _band = score._replay(rows)
        expected = EXPECTED[name]
        checks.equal(
            len(verdicts),
            expected["adaptive"],
            f"{_label(name)}: adaptive replay reaches {expected['adaptive']} verdicts "
            f"(the constants reached {expected['live']} live)",
        )
        checks.ok(
            len(verdicts) >= expected["live"] - 1,
            f"{_label(name)}: and that is at or above what the hand-tuned constants scored",
        )

    return checks.result(
        f"{len(traces)} recorded sessions, {sum(len(t['events']) for t in traces.values())} verdicts"
    )
