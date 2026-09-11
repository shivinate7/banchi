"""T9 — The motion trigger against real recorded rig sessions.

NEW 2026-08-31, with D81, and it exists because of one fact: `app/tests/motion.spec.ts` and
`app/tests/motion-live.spec.ts` were GREEN through all three versions of the card-present
gate, including the two that were losing cards. They could not have failed. Both draw their
own frames — synthetic arrays, a flat canvas fill — so they can only ever prove the machine
agrees with the test's own idea of a card. Until this file, nothing in the repo had ever put
the motion machine in front of a photograph.

The traces in `harness/traces/` are the only real-rig evidence this subsystem has: ten
armed sessions saved from the HUD by the owner — FIVE recorded under the brightness floor
D81 replaced, THREE recorded on 2026-09-01 under the distance gate that replaced it,
which is what convicted the stillness rule and the presence floor in D84, and TWO recorded
on 2026-09-11 over a re-arranged feeder with a beat and no rest, which convicted the settle
rule itself and are what the cadence trigger (D130) was built on. Each carries every
frame's (t, d, luma), v2 adding dBase, and the exact watch-region pixels of every verdict,
which is what makes a refusal re-scorable years later.

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

    the D84 PAIR     over the three 2026-09-01 21:xx sessions only: that the presence floor
                     refuses the two settles that photographed the bare stand and passes
                     every card, and that a card which never completes a settle is
                     REPORTED. Those two were the defects; this is what says they stay
                     fixed. A stall is asserted as a count AND a time, because "some stall
                     fired" would pass on a stall in the wrong place.

WHAT A GREEN T9 DOES NOT MEAN. It does not mean the trigger works at the rig today. These
are ten recordings of a handful of rig states, and the next rig can differ from all of
them — the same honest limit T6 and T8 carry, in the same words. What it does mean is that the machine
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
DESCRIPTION = "Motion trigger against ten recorded rig sessions"
PASS_CRITERIA = (
    "on every saved trace an empty stand sits within 2 of its own baseline and every card "
    "sits 17 or more away; the dimmest card on one rig is dimmer than the empty stand on "
    "another, so no brightness constant separates them; the adaptive thresholds reach at "
    "least as many verdicts as the hand-tuned constants did live on all ten; and on the "
    "three sessions D84 was derived from, the presence floor refuses both settles that "
    "photographed the bare stand while a card that never settles is reported as a stall; "
    "and on the two 2026-09-11 sessions the settle rule fired five times each on a feeder "
    "with a 0.87 s beat and no rest, the receipt the cadence trigger (D130) was built on"
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

# THE PRE-D81 CORPUS, and it is named because one claim below is HISTORY rather than a
# property. "38 real cards were refused live" is a receipt for what the brightness floor
# cost, and only these five sessions were ever recorded under that floor. The 2026-09-01
# 21:xx sessions ran on the distance gate, where a `suppressed:no-card` is the gate working
# correctly on the bare stand — summing across corpora would turn a fixed receipt into a number
# that grows every time a trace is banked, which is a claim about nothing.
PRE_D81 = {
    "harness/traces/motion-trace-2026-08-23T02-49-55-745Z.json",
    "harness/traces/motion-trace-2026-08-23T03-09-19-299Z.json",
    "harness/traces/motion-trace-2026-08-29T21-34-14-525Z.json",
    "harness/traces/motion-trace-2026-08-29T21-38-29-293Z.json",
    "harness/traces/motion-trace-2026-09-01T03-06-14-582Z.json",
}

# THE THREE SESSIONS D84 WAS DERIVED FROM, with what each one cost before it. 93 seconds of
# feeding, 69 fires, and the two defects the entry is about: two photographs of the bare
# stand, and four cards fed and never photographed at all. `plate_fires` is when the live
# gate fired on the arm-time scene; `stalls` is what the corrected clock reports, and every
# one of those times sits on a card that was in the watch region and never settled.
D84 = {
    "harness/traces/motion-trace-2026-09-01T21-10-36-920Z.json": {
        "plate_fires": [12.4], "stalls": [14.1],
    },
    "harness/traces/motion-trace-2026-09-01T21-14-34-791Z.json": {
        "plate_fires": [5.4], "stalls": [],
    },
    "harness/traces/motion-trace-2026-09-01T21-16-13-772Z.json": {
        "plate_fires": [], "stalls": [8.6],
    },
}

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
    # The three D84 sessions. `adaptive` is under the SHIPPED rule — `stillFrames` of the
    # last `stillWindow`. The consecutive rule these replaced scored 47, 14 and 11 on the
    # same rows, and the one extra verdict in the first is the card at 14.49 s that sat
    # motionless for 500 ms while its every other frame landed in the Schmitt band.
    #
    # `arrival` is EARLIER than the first fire in the first two, deliberately and by this
    # key's own definition: the 12.4 s and 5.4 s verdicts are re-settles of the arm-time
    # scene, which is why the floor may refuse them without that being a missed card.
    "harness/traces/motion-trace-2026-09-01T21-10-36-920Z.json": {"live": 46, "adaptive": 48, "arrival": 13000},
    "harness/traces/motion-trace-2026-09-01T21-14-34-791Z.json": {"live": 13, "adaptive": 14, "arrival": 5700},
    "harness/traces/motion-trace-2026-09-01T21-16-13-772Z.json": {"live": 10, "adaptive": 11, "arrival": 8400},
}


# THE TWO SESSIONS THAT CONVICTED THE SETTLE RULE ITSELF (D130), 2026-09-11, and a THIRD
# corpus rather than two more rows above, because the claim they carry is the opposite one.
# The owner re-arranged the feeder; it now puts a card down every 0.867 s (29 luma cycles,
# p10 0.85, p90 0.92) and never lets one sit still — the longest run of frames under tLo per
# card has a median of ONE. Every fire the settle machine made reached disk and photographed
# a card; it made FIVE on each session, against 29 and ~21 cards fed. That is the receipt this
# corpus keeps: the settle rule, on a feeder with a beat and no rest, photographs about one
# card in six, and no threshold recovers it (`score-trace.py sweep`: 9 of 29 at best). The
# cadence machine built on them is replayed and pinned in `app/tests/cadence.spec.ts` — a
# TypeScript machine with no Python mirror, which is why its counts are asserted there and not
# here. `cycles` is the luma-crossing count read off each trace; `feeding` is when the first
# card reached the lens, read off `dBase` crossing the floor.
CADENCE = {
    "harness/traces/motion-trace-2026-09-11T01-48-49-706Z.json": {"fires": 5, "cycles": 29, "feeding": 31500},
    "harness/traces/motion-trace-2026-09-11T01-51-27-783Z.json": {"fires": 5, "cycles": 34, "feeding": 13500},
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
    checks.equal(sorted(traces), sorted(set(EXPECTED) | set(CADENCE)),
                 "all ten recorded sessions are present")
    checks.equal(sorted(PRE_D81 | set(D84) | set(CADENCE)), sorted(set(EXPECTED) | set(CADENCE)),
                 "and every one is in exactly one corpus — the brightness floor's, D84's, or D130's")
    if sorted(traces) != sorted(set(EXPECTED) | set(CADENCE)):
        return checks.result()

    # ---- D130: what the settle rule scores on a feeder with a beat and no rest ------
    #
    # A RECEIPT, NOT A TARGET. These counts may never go UP under the settle rule without
    # somebody explaining how a machine that fires on stillness found some on frames whose
    # quiet runs are one frame long; and the separation below still has to hold on them,
    # because presence is the one thing the cadence machine borrows from the settle machine.
    for name in sorted(CADENCE):
        trace = traces[name]
        key = CADENCE[name]
        fired = [e for e in trace["events"] if e["event"] == "fire"]
        checks.equal(
            len(fired), key["fires"],
            f"{_label(name)}: the settle trigger fired {key['fires']} times live on ~{key['cycles']} cards",
        )
        rows = score._rows(trace)
        feeding = [d for t, d, _b, _l in rows if t >= key["feeding"]]
        # The beat, read the same way the cadence machine reads it: the cycles the luma makes.
        crossings = sum(
            1 for (_t0, _d0, _b0, l0), (_t1, _d1, _b1, l1) in zip(rows, rows[1:])
            if _t1 >= key["feeding"] and l0 >= 170 > l1
        )
        checks.equal(
            crossings, key["cycles"],
            f"{_label(name)}: the region's luma cycles {crossings} times while feeding (a card every "
            f"{(rows[-1][0] - key['feeding']) / max(crossings, 1) / 1000:.2f} s)",
        )
        quiet_share = sum(1 for d in feeding if d < 3.5) / max(len(feeding), 1)
        checks.ok(
            quiet_share < 0.25,
            f"{_label(name)}: under a quarter of feeding frames are under tLo ({quiet_share:.0%}) — "
            f"the feeder never lets a card sit, which is why a settle rule cannot fire on it",
        )
        base = _cells(trace["keyframes"][0]["frame"])
        for event in fired:
            distance = _distance(_cells(event["frame"]), base)
            checks.ok(
                distance >= 17.0,
                f"{_label(name)} {event['t'] / 1000:.1f}s: the fired frame is a card ({distance:.1f} from baseline)",
            )

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
        if name in PRE_D81 and name != REFERENCE and "no-card" in e["event"]
    )
    still_refused = sum(
        1
        for name, trace in traces.items()
        for e in trace["events"]
        if name in PRE_D81
        and name != REFERENCE
        and score._quantile([float(v) for v in _cells(e["frame"])], 0.9) < 90
    )
    checks.equal(live_refused, 38, "38 real cards were refused live, across three sessions")
    checks.equal(still_refused, 18, "18 of them would still be refused by a floor of 90")

    # ---- every card clears the distance gate, on every rig --------------------------
    # The cadence corpus (D130) is graded in its own block above; these are the presence
    # checks keyed by EXPECTED, which is the settle corpus.
    for name in sorted(EXPECTED):
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

    # ---- D84: the two defects, on the three sessions that convicted them ------------
    #
    # ASSERTED BY TIME, NOT BY COUNT, and that is the whole design of this block. "two fires
    # are refused now" would pass just as happily if the floor had climbed far enough to
    # refuse two CARDS instead, which is D81's failure with the sign flipped. Naming the
    # second is what makes the check about the right two frames.
    for name in sorted(D84):
        trace = traces[name]
        rows = score._rows(trace)
        base = _cells(trace["keyframes"][0]["frame"])
        typical = max(1.0, statistics.median(d for _t, d, _b, _l in rows))
        floor = max(score.PRESENCE_MIN, score.PRESENCE_K * typical)
        refused = [
            round(event["t"] / 1000, 1)
            for event in trace["events"]
            if event["event"] == "fire" and _distance(_cells(event["frame"]), base) < floor
        ]
        checks.equal(
            refused,
            D84[name]["plate_fires"],
            f"{_label(name)}: the floor ({floor:.1f}) refuses exactly the settles that "
            f"photographed the bare stand, and nothing else that fired",
        )
        _verdicts, _band, stalls = score._replay(rows)
        checks.equal(
            [round(at / 1000, 1) for at in stalls],
            D84[name]["stalls"],
            f"{_label(name)}: and a card that never completes a settle is REPORTED — the "
            f"silent loss D84 is about, made loud",
        )

    # THE OTHER HALF OF A STALL BEING USEFUL: that it is quiet when nothing is wrong. Five
    # earlier sessions, 217 verdicts, several hundred good captures between them — the
    # corrected clock must not fire on any of it, or the HUD learns to be ignored and the
    # signal is worth nothing on the day it matters.
    noise = {
        _label(name): [round(at / 1000, 1) for at in score._replay(score._rows(traces[name]))[2]]
        for name in sorted(PRE_D81)
    }
    checks.ok(
        not any(noise.values()),
        f"and it stays silent across all five earlier sessions ({sum(len(t['events']) for n, t in traces.items() if n in PRE_D81)} verdicts)",
        f"stalled on: { {k: v for k, v in noise.items() if v} }",
    )

    # ---- the tripwire: the replay still reaches what the sweep said it would --------
    for name in sorted(EXPECTED):
        rows = score._rows(traces[name])
        verdicts, _band, _stalls = score._replay(rows)
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
