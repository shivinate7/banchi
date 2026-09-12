#!/usr/bin/env python3
"""Re-score a saved motion trace offline — docs/specs/motion-trigger.md §4 step 5, in code.

THE PROMISE THIS DISCHARGES. The trace has existed since 2026-08-23 and the spec has said
since then that handing one to a session makes the tuning happen offline, "period, jitter,
t_move/t_still measured rather than derived, and the gates re-scorable against different
thresholds without another rig trip". Three sessions did exactly that by hand, and the
third one found that the second one's fix had been validated against MISLABELLED frames —
twenty photographs of real cards had been read as an empty stand and then used to derive
the empty stand's brightness. A scoring pass nobody can run twice the same way is how that
happens. This is that pass, written down.

WHAT IT ANSWERS, in the order the questions actually get asked:

    summary    what the machine did live: verdicts, fires, refusals, cadence, noise
    presence   would the CURRENT presence gate have fired on each verdict's own pixels
    sweep      what the stillness thresholds would have scored across a parameter grid
    stalls     every episode the rescue could not save, with its brightness against this
               session's own fired cards — a reading, and `stalls` says why it is not a verdict
    camera     what the CAMERA did, as opposed to what the cards did: how the frames were
               paced, how bright the plate is and therefore what one exposure step would
               cost, whether the still-frame floor is noise or the whole picture moving
    contact    write the verdict frames out as a PNG contact sheet, so a human can see
               whether the frames the machine called empty have a card in them

The last one is not a nicety. Every numeric claim about "empty stand" in this repo's
history came from someone assuming a refusal meant an empty stand; the only thing that
settles it is looking.

    scripts/score-trace.py summary  <trace.json> [more.json ...]
    scripts/score-trace.py presence <trace.json>
    scripts/score-trace.py sweep    <trace.json> [more.json ...]
    scripts/score-trace.py stalls   <trace.json> [more.json ...]
    scripts/score-trace.py camera   <trace.json> [more.json ...]
    scripts/score-trace.py contact  <trace.json> <out.png>

TRACE VERSIONS. v1 rows are [t, d, luma]; v2 rows (D81) are [t, d, dBase, luma]. Read
through `_rows` and never by index, or a v2 trace reads as a rig with no light in it.

numpy is used where it is present and not required: `summary` and `presence` run on the
standard library alone, because the machine they describe is 300 lines of arithmetic and a
tuning instrument that cannot run on a plain checkout is a tuning instrument nobody runs.
`contact` needs Pillow and says so rather than failing obscurely.
"""

from __future__ import annotations

import base64
import json
import math
import statistics
import sys
from pathlib import Path

# The machine's own defaults, mirrored. NOT imported — app/src/motion.ts is TypeScript and
# this is the offline half; `make docs-audit`'s `motion params` row is what keeps the two
# honest, so a constant moved in one place and not the other fails a commit.
STILL_K = 2.0
MOVE_K = (2.0 * 16) / 9
D_SEED = 2.25
D_FLOOR = 1.0
NOISE_WINDOW_MS = 8000.0
STILL_FRACTION_MIN = 0.3
REST_QUANTILE = 0.25
STILL_FRAMES = 1
STILL_WINDOW = 3
REFRACTORY_MS = 250.0
PRESENCE_K = 3.0
PRESENCE_MIN = 16.0
RESCUE_K = 4 / 3
RESCUE_AFTER = 0.6
MAX_MOVE_MS = 1250.0

# NOT A MIRRORED PARAMETER, and it is read by `camera` alone. An exposure change of E stops
# multiplies scene luminance by 2**E; the stream is display-referred, so the 8-bit code is
# luminance ** (1 / GAMMA_DISPLAY) and the code therefore scales by 2 ** (E / GAMMA_DISPLAY).
# 2.2 is the sRGB-ish assumption rather than a measurement — the bracket 1.9 to 2.4 moves a
# 1/3 EV step on the corpus's median plate over 18.7 to 23.3, which crosses every gate this
# tool compares it against at every value in the bracket, so the conclusion does not rest on
# the number. NOTHING GATES ON IT: `camera` prints a reading.
GAMMA_DISPLAY = 2.2


def _load(path: str) -> dict:
    data = json.loads(Path(path).read_text())
    if data.get("kind") != "pkmnscan-motion-trace":
        raise SystemExit(f"{path}: not a pkmnscan motion trace")
    return data


def _rows(trace: dict) -> list[tuple[float, float, float | None, float]]:
    """(t, d, dBase, luma) per frame. dBase is None on a v1 trace, which predates it."""
    out = []
    if trace.get("version", 1) >= 2:
        for t, d, dbase, luma in trace["frames"]:
            out.append((t, d, dbase, luma))
    else:
        for t, d, luma in trace["frames"]:
            out.append((t, d, None, luma))
    return out


def _cells(b64: str) -> list[int]:
    return list(base64.b64decode(b64))


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int((len(ordered) - 1) * q)))]


def _mad(a: list[int], b: list[int]) -> float:
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def _replay(rows, still_k=STILL_K, move_k=MOVE_K, d_seed=D_SEED):
    """The stillness half of MotionMachine, over (t, d) alone.

    Only frames the machine already calls STILL feed the noise estimate — motion.ts's
    `noiseWindowMs` carries the argument, and dropping that condition here would score a
    machine nobody is running. UNLESS THE STILL POPULATION IS A MINORITY OF THE WINDOW
    (D131): under `STILL_FRACTION_MIN` of all frames, the ratchet has lost the still level
    and `REST_QUANTILE` of every frame in the window stands in for it, `t_hi` keeping its
    ratio. Mirrors `trackNoise` exactly; the bright-lamp sessions are where it decides.

    STILLNESS IS `STILL_FRAMES` OF THE LAST `STILL_WINDOW` (D84), completing only on a
    frame that is itself quiet, and the stall clock is cleared by a COMPLETED SETTLE rather
    than by any quiet frame. Both halves have to mirror motion.ts exactly or this scorer
    grades a machine nobody is running — `make docs-audit`'s `motion params` row is what
    stops the two drifting.

    AND AN EPISODE PAST `RESCUE_AFTER` x `MAX_MOVE_MS` TAKES `RESCUE_K` x t_lo AS ITS BAR,
    window requirement dropped with it — the rescue. `rescueK` in motion.ts carries the
    derivation; the short form is that 4/3 is the geometric centre of the Schmitt band and
    the window is what refused nine of fourteen measured misses on frames already called
    quiet. The age gate is not decoration: retiring the window from the first frame of an
    episode takes this corpus's double count from 2 to 21.

    Returns (verdicts, (tLo min, tLo max), stalls, rescues)."""
    window: list[tuple[float, float]] = []
    everything: list[tuple[float, float]] = []
    d_typical = d_seed
    t_lo, t_hi = d_typical * still_k, d_typical * move_k
    judged, refractory = False, 0.0
    marks: list[bool] = []
    moving_since: float | None = None
    stall_flagged = False
    verdicts: list[float] = []
    stalls: list[float] = []
    rescues: list[float] = []
    lows: list[float] = []

    def stall(now: float) -> None:
        nonlocal moving_since, stall_flagged
        if moving_since is None:
            moving_since = now
        if not stall_flagged and now - moving_since > MAX_MOVE_MS:
            stall_flagged = True
            stalls.append(now)

    for index, (now, d, dbase, _luma) in enumerate(rows[1:], start=1):
        # THE FRACTION IS TAKEN OVER FRAMES WITH A CARD IN VIEW (D131): an empty stand is
        # still on every frame, and a window that had just watched thirty seconds of it
        # called the first cards a still majority for six seconds after feeding began. A v1
        # trace carries no dBase and counts every frame; the machine's own gate is
        # `presenceFloor`, which on every session here is PRESENCE_MIN.
        present = dbase is None or dbase >= PRESENCE_MIN
        if d < t_lo:
            window.append((now, d))
        everything.append((now, d, present))
        while window and now - window[0][0] > NOISE_WINDOW_MS:
            window.pop(0)
        while everything and now - everything[0][0] > NOISE_WINDOW_MS:
            everything.pop(0)
        if index % 10 == 0 and len(window) >= 25:
            in_view = [value for _, value, seen in everything if seen]
            still_in_view = sum(1 for value in in_view if value < t_lo)
            rest = (
                max(D_FLOOR, _quantile(in_view, REST_QUANTILE))
                if len(in_view) >= 25 and still_in_view / len(in_view) < STILL_FRACTION_MIN
                else None
            )
            # A rest must be smaller than a card arriving: a quantile at or above the
            # presence floor is a motion level, and the ratchet keeps the word.
            if rest is not None and rest < PRESENCE_MIN:
                d_typical = rest
                t_lo, t_hi = rest, max(rest * (move_k / still_k), rest + 1)
            else:
                d_typical = max(D_FLOOR, statistics.median(value for _, value in window))
                t_lo, t_hi = d_typical * still_k, d_typical * move_k
        lows.append(t_lo)
        if d > t_hi:
            marks, judged = [], False
            stall(now)
            continue
        quiet = d < t_lo
        marks.append(quiet)
        del marks[:-STILL_WINDOW]
        ordinary = quiet and len(marks) >= STILL_WINDOW and sum(marks) >= STILL_FRAMES
        rescued = (
            not ordinary
            and moving_since is not None
            and now - moving_since >= RESCUE_AFTER * MAX_MOVE_MS
            and d < t_lo * RESCUE_K
        )
        if not (ordinary or rescued):
            stall(now)
            continue
        moving_since, stall_flagged = None, False
        if judged or now < refractory:
            continue
        judged = True
        refractory = now + REFRACTORY_MS
        verdicts.append(now)
        if rescued:
            rescues.append(now)
    return verdicts, ((min(lows), max(lows)) if lows else (0.0, 0.0)), stalls, rescues


def _presentations(rows, t_hi: float, merge_ms: float = 300.0) -> list[float]:
    """Distinct card presentations: rising crossings of tHi, merged if close together.

    A card's motion crosses tHi more than once — the 2026-09-01 trace counts 32 raw
    crossings for 25 presentations — so an unmerged count reads as missed cards that were
    never there. The merge window is under half the measured feeder period (623 ms)."""
    out: list[float] = []
    above = False
    for t, d, _dbase, _luma in rows:
        if d > t_hi and not above and (not out or t - out[-1] >= merge_ms):
            out.append(t)
        above = d > t_hi
    return out


def summary(paths: list[str]) -> None:
    for path in paths:
        trace = _load(path)
        rows = _rows(trace)
        params = trace["params"]
        # A cadence trace (D130) nests the settle machine's parameters under `motion`; the
        # replay below is the SETTLE rule's and says so, so a cadence trace's live verdicts
        # and the replayed ones are two different machines' opinions of the same frames.
        trigger = trace.get("trigger", "motion")
        params = params.get("motion", params)
        d_values = [d for _t, d, _b, _l in rows]
        lumas = [luma for _t, _d, _b, luma in rows]
        duration = rows[-1][0] / 1000
        events = trace["events"]
        kinds: dict[str, int] = {}
        for event in events:
            kinds[event["event"]] = kinds.get(event["event"], 0) + 1
        t_hi_live = params.get("tHi") or (params["dSeed"] * params["moveK"])
        presented = _presentations(rows, t_hi_live)
        replayed, (lo, hi), stalls, rescues = _replay(rows)
        print(f"{Path(path).name}   v{trace.get('version', 1)}   trigger {trigger}")
        print(f"  {duration:6.1f}s  {len(rows):5d} frames  {len(rows) / duration:5.1f} fps")
        print(f"  live params   {params}")
        print(f"  live verdicts {len(events):4d}   {kinds}")
        print(f"  presentations {len(presented):4d}   (motion bursts above the live tHi)")
        print(f"  replayed      {len(replayed):4d}   under today's adaptive SETTLE form, tLo {lo:.2f}-{hi:.2f}")
        print(f"  of those      {len(rescues):4d}   RESCUED — taken under `rescueK` x tLo, not off a completed settle")
        print(f"  stalls        {len(stalls):4d}   at {[round(t / 1000, 1) for t in stalls]}")
        print(f"  d      median {statistics.median(d_values):5.2f}  p99 {_quantile(d_values, 0.99):6.2f}")
        print(f"  luma   min {min(lumas):5.1f}  median {statistics.median(lumas):6.1f}  max {max(lumas):6.1f}")
        print()


def presence(path: str) -> None:
    """Re-run the presence gate over every verdict's own pixels.

    The baseline is taken the way the machine takes it — the first keyframe, which is the
    watch region as it stood when the trigger was armed. THE OUTPUT IS A PROPOSAL, NOT A
    FINDING: whether a refused frame had a card in it is settled by `contact`, by looking."""
    trace = _load(path)
    rows = _rows(trace)
    d_values = [d for _t, d, _b, _l in rows]
    d_typical = max(D_FLOOR, statistics.median(d_values))
    floor = max(PRESENCE_MIN, PRESENCE_K * d_typical)
    baseline = _cells(trace["keyframes"][0]["frame"])
    print(f"{Path(path).name}  baseline = keyframe at t={trace['keyframes'][0]['t']:.0f}ms")
    print(f"  d typical {d_typical:.2f}  ->  presence floor {floor:.2f}")
    passes = 0
    for event in trace["events"]:
        cells = _cells(event["frame"])
        distance = _mad(cells, baseline)
        verdict = "CARD " if distance >= floor else "empty"
        if distance >= floor:
            passes += 1
        print(
            f"  {event['t'] / 1000:7.1f}s  live {event['event']:20s}"
            f"  dbase {distance:7.2f}  p90 {_quantile([float(v) for v in cells], 0.9):5.1f}"
            f"  -> {verdict}"
        )
    live_fires = sum(1 for e in trace["events"] if e["event"] == "fire")
    print(f"  {passes} of {len(trace['events'])} verdicts pass the distance gate; the live gate fired {live_fires}")


def sweep(paths: list[str]) -> None:
    """What the stillness thresholds would score across a grid, on every trace at once.

    ONE TRACE CANNOT CHOOSE A PARAMETER. The 2026-08-23 retune was swept over one run and
    the value it picked was right for that rig; the point of a grid over ALL the traces is
    to land in the middle of a plateau rather than on the edge of a peak."""
    loaded = []
    for path in paths:
        trace = _load(path)
        rows = _rows(trace)
        t_hi_live = trace["params"].get("tHi") or (trace["params"]["dSeed"] * trace["params"]["moveK"])
        loaded.append((Path(path).name, rows, len(_presentations(rows, t_hi_live)), len(trace["events"])))
    print("presentations:", {name: p for name, _r, p, _l in loaded})
    print("live verdicts:", {name: verdict for name, _r, _p, verdict in loaded})
    for still_k in (1.4, 1.6, 1.8, 2.0, 2.2, 2.5):
        scored = [len(_replay(rows, still_k, still_k * 16 / 9, 4.5 / still_k)[0]) for _n, rows, _p, _l in loaded]
        meets = all(v >= live - 1 for v, (_n, _r, _p, live) in zip(scored, loaded))
        print(f"  stillK={still_k:.1f}  {scored}  {'meets live everywhere' if meets else ''}")


def stalls(paths: list[str]) -> None:
    """Every episode the rescue could not save, with the brightness the operator asked about.

    WHY THIS IS A READING AND NOT A CLASSIFIER, which is the finding rather than the excuse.
    The owner's diagnosis of the 2026-09-11 misses was specular glare — a mirror flash off a
    tilted card — and the obvious next step is a `stalled:flare` verdict. Three candidate
    discriminators were measured over this whole corpus and every one of them failed:

        SATURATION      the share of watch-region cells at 250 or above is ~0 on every stall
                        frame here, worst 6 cells of 1064. That is not evidence of no glare:
                        each cell averages ~3,600 sensor pixels, so a fully clipped streak
                        on the sensor reaches the trace as a cell reading 214. The instrument
                        destroys the evidence before the file is written.
        SPIKE SHAPE     a flash should be brief, so peak / own-median bright quantile over
                        the episode ought to separate. It goes the wrong way: stall episodes
                        read 1.19 median where episodes ending in a FIRE read 1.36.
        ABSOLUTE LEVEL  "brighter than any card this session fired on" flags 6 of the 11
                        surviving stalls — and 14% to 55% of the ordinary episodes too.

    So this prints the number and names nothing. The peak against the session's own fired
    cards is exactly the comparison the owner made by eye off a contact sheet; a verdict
    string asserting `flare` would be this repo's own `cardLumaFloor` mistake in a third
    costume — a brightness compared against a line that does not separate the populations."""
    for path in paths:
        trace = _load(path)
        rows = _rows(trace)
        verdicts, _band, stalled, _rescues = _replay(rows)
        fired = {round(t, 1) for t in verdicts}
        lit = [luma for t, _d, _b, luma in rows if round(t, 1) in fired]
        if not lit:
            print(f"{Path(path).name}: no fires to compare against")
            continue
        median = statistics.median(lit)
        print(f"{Path(path).name}   {len(stalled)} stalls, {len(verdicts)} fires")
        print(f"  a fired card's bright quantile: median {median:.0f}, "
              f"p90 {_quantile(lit, 0.9):.0f}, max {max(lit):.0f}")
        for at in stalled:
            window = [
                (d, luma) for t, d, _b, luma in rows if at - MAX_MOVE_MS <= t <= at
            ]
            peak = max(luma for _d, luma in window)
            quietest = min(d for d, _luma in window)
            print(f"  {at / 1000:7.1f}s  quietest frame d {quietest:6.2f}   "
                  f"peak bright quantile {peak:5.0f} = {peak / max(median, 1):.2f}x this "
                  f"session's median card")


def camera(paths: list[str]) -> None:
    """What the CAMERA did, as opposed to what the cards did.

    D81 made every threshold a multiple of something the session measures, which buys
    portability to a new rig and buys with it a new exposure: a camera setting that DRIFTS
    mid-session moves the baseline the thresholds were derived from, and no constant in
    `motion.ts` can defend against that. This reads the four things a trace can say about
    the lens that took it.

        DELIVERY     the modal frame interval and the share of gaps long enough to be a
                     dropped frame. `stillWindow` is a FRAME COUNT, so the rate sets how
                     much TIME a settle needs and how much of a card's rest is sampled.
        PLATE        the watch region's median level with nothing on the stand, and what
                     ONE exposure step would therefore move it by. The step is
                     multiplicative in code space (2 ** (EV / GAMMA_DISPLAY)), so a bright
                     plate pays more for the same step than a dark one.
        STILL FLOOR  `typ`, and the LAG-1 SPATIAL CORRELATION of the still-frame delta
                     field. Independent noise correlates at ~0 cell to cell; flicker, an AE
                     micro-adjustment or a lamp ripple move neighbours together. Which of
                     the two it is decides whether gain or the lamp is the lever.
        PRESENCE     the idle stand against the quietest card the session fired on — D84's
                     first and third quantities, re-derived per session. The SECOND, the
                     worst approach, is deliberately absent: separating a hand from a card
                     needs the pixels, and `contact` is where that is settled.
    """
    pooled_gap: list[float] = []
    pooled_corr: list[float] = []
    for path in paths:
        trace = _load(path)
        rows = _rows(trace)
        gaps = [rows[i][0] - rows[i - 1][0] for i in range(1, len(rows))]
        period = statistics.median(gaps)
        dropped = sum(max(0, round(gap / period) - 1) for gap in gaps)
        still = [d for _t, d, _b, _l in rows if d < D_SEED * STILL_K]
        typical = max(D_FLOOR, statistics.median(still)) if still else float("nan")

        keyframes = trace["keyframes"]
        plate = statistics.median(_cells(keyframes[0]["frame"]))
        print(f"{Path(path).name}   v{trace.get('version', 1)}")
        print(f"  delivery   {1000 / period:5.1f} fps   modal gap {period:.1f} ms   "
              f"{dropped} gap(s) long enough to be a dropped frame "
              f"({dropped / len(rows) * 100:.2f}% of frames)")
        print(f"  plate      level {plate:.0f}   one exposure step moves the watch region:")
        for stop, label in ((1 / 3, "1/3 EV"), (1 / 2, "1/2 EV"), (1.0, "1 EV")):
            lifted = [min(255.0, v * 2 ** (stop / GAMMA_DISPLAY)) for v in _cells(keyframes[0]["frame"])]
            moved = _mad(_cells(keyframes[0]["frame"]), lifted)
            floor = max(PRESENCE_MIN, PRESENCE_K * typical) if typical == typical else PRESENCE_MIN
            reads = "A CARD" if moved >= floor else ("motion" if moved >= typical * STILL_K else "nothing")
            print(f"               {label:6s}  ->  {moved:6.2f}   reads as {reads}"
                  f"   (tLo {typical * STILL_K:.2f}, presence floor {floor:.2f})")

        lag_x, lag_y = _still_correlation(trace, rows)
        pooled_corr += [c for c in (lag_x, lag_y) if c == c]
        pooled_gap.append(period)
        shape = "independent cell to cell" if abs(lag_x) < 0.1 and abs(lag_y) < 0.1 else "CORRELATED — the whole picture is moving"
        print(f"  stillfloor typ {typical:.2f}   tLo {typical * STILL_K:.2f}   "
              f"lag-1 spatial correlation {lag_x:+.3f} x / {lag_y:+.3f} y   {shape}")

        fires = [e for e in trace["events"] if e["event"].startswith("fire")]
        baseline = _cells(keyframes[0]["frame"])
        distances = [_mad(_cells(e["frame"]), baseline) for e in fires]
        idle = [b for _t, _d, b, _l in rows[1:] if b is not None]
        if distances and idle:
            quiet = [b for b in idle if b < PRESENCE_MIN]
            print(f"  presence   idle stand {statistics.median(quiet):.2f} "
                  f"(p99 {_quantile(quiet, 0.99):.2f})   quietest fired card {min(distances):.2f}"
                  f"   floor {PRESENCE_MIN:.2f}")
        else:
            print("  presence   not readable — this v1 trace predates the presence gate (D81), "
                  "so no baseline travels with it")
        print()
    if len(paths) > 1 and pooled_corr:
        print(f"POOLED  modal gap {statistics.median(pooled_gap):.1f} ms "
              f"= {1000 / statistics.median(pooled_gap):.1f} fps   "
              f"lag-1 correlation p50 {statistics.median(pooled_corr):+.3f}")


def _still_correlation(trace: dict, rows) -> tuple[float, float]:
    """Lag-1 spatial correlation of the delta field, over QUIET keyframe pairs only.

    Quiet is: no verdict fell between the two keyframes and no frame between them reached
    the seeded tLo. That selection is circular for a claim about how BIG the still floor
    is — it picks the quiet stretches — and is not circular for a claim about its SHAPE,
    which is all this is used for."""
    x0, y0, x1, y1 = trace["grid"]["roi"]
    width = x1 - x0
    keyframes = trace["keyframes"]
    events = [e["t"] for e in trace["events"]]
    across: list[float] = []
    down: list[float] = []
    for index in range(1, len(keyframes)):
        start, end = keyframes[index - 1]["t"], keyframes[index]["t"]
        if any(start <= at <= end for at in events):
            continue
        between = [d for t, d, _b, _l in rows if start <= t <= end]
        if not between or max(between) >= D_SEED * STILL_K:
            continue
        before = _cells(keyframes[index - 1]["frame"])
        after = _cells(keyframes[index]["frame"])
        delta = [b - a for a, b in zip(before, after)]
        height = len(delta) // width
        across.append(_pearson(
            [delta[r * width + c] for r in range(height) for c in range(width - 1)],
            [delta[r * width + c + 1] for r in range(height) for c in range(width - 1)],
        ))
        down.append(_pearson(
            [delta[r * width + c] for r in range(height - 1) for c in range(width)],
            [delta[(r + 1) * width + c] for r in range(height - 1) for c in range(width)],
        ))
    across = [v for v in across if v == v]
    down = [v for v in down if v == v]
    if not across:
        return float("nan"), float("nan")
    return statistics.median(across), statistics.median(down)


def _pearson(left: list[int], right: list[int]) -> float:
    n = len(left)
    ml, mr = sum(left) / n, sum(right) / n
    sl = math.sqrt(sum((v - ml) ** 2 for v in left))
    sr = math.sqrt(sum((v - mr) ** 2 for v in right))
    if sl == 0 or sr == 0:
        return float("nan")
    return sum((a - ml) * (b - mr) for a, b in zip(left, right)) / (sl * sr)


def contact(path: str, out: str) -> None:
    """Every verdict's frame as one PNG, labelled with its live event and its statistics.

    THE ONLY THING THAT SETTLES WHAT A FRAME CONTAINS. Two of this repo's presence-gate
    fixes were derived from frames nobody looked at, and the second one was measured
    against twenty photographs of real cards that had been filed as an empty stand."""
    try:
        from PIL import Image, ImageDraw  # noqa: PLC0415
    except ImportError:
        raise SystemExit(
            "contact needs Pillow: pip install pillow (or use the repo venv)"
        ) from None
    trace = _load(path)
    x0, y0, x1, y1 = trace["grid"]["roi"]
    width, height = x1 - x0, y1 - y0
    items = trace["events"]
    scale, columns = 5, 6
    tile_w, tile_h = width * scale, height * scale + 16
    rows_n = (len(items) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * tile_w, rows_n * tile_h), (20, 20, 24))
    draw = ImageDraw.Draw(sheet)
    for index, event in enumerate(items):
        cells = _cells(event["frame"])
        image = Image.frombytes("L", (width, height), bytes(cells))
        image = image.resize((tile_w, tile_h - 16), Image.NEAREST).convert("RGB")
        cx, cy = (index % columns) * tile_w, (index // columns) * tile_h
        sheet.paste(image, (cx, cy + 16))
        fired = event["event"] == "fire"
        draw.text(
            (cx + 3, cy + 3),
            f"{index} {event['t'] / 1000:.1f}s {'FIRE' if fired else 'REFUSED'}"
            f" p90={int(_quantile([float(v) for v in cells], 0.9))}",
            fill=(120, 255, 120) if fired else (255, 120, 120),
        )
    sheet.save(out)
    print(f"{out}  {sheet.size[0]}x{sheet.size[1]}  {len(items)} verdicts")


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    command, rest = argv[1], argv[2:]
    if command == "summary":
        summary(rest)
    elif command == "presence":
        presence(rest[0])
    elif command == "sweep":
        sweep(rest)
    elif command == "stalls":
        stalls(rest)
    elif command == "camera":
        camera(rest)
    elif command == "contact":
        if len(rest) != 2:
            raise SystemExit("contact takes <trace.json> <out.png>")
        contact(rest[0], rest[1])
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
