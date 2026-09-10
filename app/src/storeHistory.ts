import type { InventoryCard, ServerStatus } from './types'

/* THE STORE'S OWN HISTORY — what the library is, and how it was made.
 *
 * Two things live here: how a SITTING is recovered from the card map, and how a sitting
 * becomes the geometry the foot of the Home hero draws. Both are policy and both were
 * measured rather than chosen; the numbers are in `docs/specs/home-hero.md`.
 *
 * ─── THE UNIT IS A SITTING, NOT A DAY AND NOT A RUN ─────────────────────────────────────────
 *
 * A DAY is wrong because the operator shoots across midnight in UTC: on the owner's store two
 * of six sittings land on a different local day than their UTC day, so every bucket would move
 * with the timezone, and one real UTC day held two sittings 18 hours apart.
 *
 * A RUN is wrong for three separate reasons. Three of the owner's nine runs share one
 * `created_at` — one send over three boxes, drawn as three points in time. `created_at` is the
 * IDENTIFY date, not the capture date. And `counts.cards_in` is not what a run photographed:
 * `pipeline/join.py` builds it as `len(cards)` over the run's whole `identifications.json`, so
 * it is the box's running total, rewritten on every re-join — the owner's nine manifests sum to
 * 1,908 against 1,625 real records.
 *
 * A SITTING is recovered from `captured_at`, which the store stamps per card in
 * `store/master.py:record_capture` and which is present on every one of those 1,625 records.
 *
 * GAP_MINUTES is 30 because the answer does not move: 5 min gives 12 sittings, 15 gives 7, and
 * 30 / 60 / 120 / 240 all give 6. A threshold sitting in the middle of a four-fold plateau is
 * a measurement rather than a preference. */
export const GAP_MINUTES = 30

/** The rig's own measured cadence — `docs/specs/motion-trigger.md`, 0.6095 s a card — as an
 *  hourly rate. It is the ribbon's ceiling because it is a PHYSICAL fact about the machine
 *  rather than a maximum chosen to make the drawing look full. */
export const RIG_CEILING_PER_HOUR = 3600 / 0.6095

const GONE = new Set(['sold', 'retired', 'moved'])

export type Sitting = {
  /** ISO of the first and last card in the sitting. */
  readonly from: string
  readonly to: string
  readonly cards: number
  /** How many of that sitting's cards have since left by any door. */
  readonly sold: number
  /** The box most of that sitting went into. A sitting can span boxes; this names the bulk. */
  readonly box: number | null
  readonly minutes: number
  /** Cards an hour. Null where the sitting has no measurable duration — a one-card sitting
   *  spans zero time, and a rate of Infinity is not a reading. Never substitute a zero. */
  readonly rate: number | null
}

/** Cluster the card map into sittings, oldest first. */
export function sittings(cards: Record<string, InventoryCard> | null, gapMinutes = GAP_MINUTES): Sitting[] {
  if (cards === null) return []
  const stamped = Object.values(cards)
    .filter((c) => typeof c.captured_at === 'string' && c.captured_at !== '')
    .map((c) => ({ at: Date.parse(c.captured_at as string), card: c }))
    .filter((c) => Number.isFinite(c.at))
    .sort((a, b) => a.at - b.at)
  if (stamped.length === 0) return []

  const gap = gapMinutes * 60_000
  const groups: (typeof stamped)[] = [[stamped[0]!]]
  for (let i = 1; i < stamped.length; i += 1) {
    const prev = stamped[i - 1]!
    const here = stamped[i]!
    if (here.at - prev.at > gap) groups.push([])
    groups[groups.length - 1]!.push(here)
  }

  return groups.map((group) => {
    const minutes = (group[group.length - 1]!.at - group[0]!.at) / 60_000
    const boxes = new Map<number, number>()
    for (const g of group) boxes.set(g.card.box, (boxes.get(g.card.box) ?? 0) + 1)
    let box: number | null = null
    let best = 0
    for (const [b, count] of boxes) if (count > best) [box, best] = [b, count]
    return {
      from: new Date(group[0]!.at).toISOString(),
      to: new Date(group[group.length - 1]!.at).toISOString(),
      cards: group.length,
      sold: group.filter((g) => GONE.has(g.card.state)).length,
      box,
      minutes,
      /* A sitting with no measurable span has no rate. `null`, never a zero and never a
         division by nothing — the drawing renders it as a tick with no block. */
      rate: minutes > 0 ? (group.length / minutes) * 60 : null,
    }
  })
}

/* ─── THE RIBBON ────────────────────────────────────────────────────────────────────────────
 *
 * Each block is as WIDE as the minutes that sitting took and as TALL as the cards an hour it
 * ran at, so its AREA is its card count — `minutes × rate ÷ 60 = cards` is an identity, which
 * is what lets the marks still sum to the figure printed above them while the height carries
 * something the figure does not.
 *
 * THE AXIS IS CUMULATIVE MINUTES AT THE RIG, not the calendar. On the owner's store 113
 * minutes of work are spread across 9.4 days, so a calendar axis puts every block at 0.84% of
 * the width — 2.1px at the widest and 0.04px at the newest. The calendar is not dropped: it is
 * demoted to the RUG below the rule, where a constant-size tick is the only mark that survives
 * that scale. Neither axis is asked to do the other's job.
 *
 * THE WINDOW IS BOUNDED so the drawing never grows with history: a plinth for everything older
 * and the last `WINDOW` sittings at their real proportions. Nine marks at six sittings and
 * nine marks at two hundred. */
export const WINDOW = 8

export type Block = {
  readonly key: string
  /** All four in the 0..`VIEW_W` / 0..`BAND_H` space of the drawn viewBox. */
  readonly x: number
  readonly y: number
  readonly w: number
  readonly h: number
  /** 0..1 of the rig ceiling — the pace ramp's mix, and redundant with `h` on purpose so a
   *  reader who cannot separate the hues loses nothing. */
  readonly pace: number
  readonly newest: boolean
  /** Set where the sitting has no measurable duration: there is no block, only a tick. */
  readonly durationless: boolean
  readonly sitting: Sitting
}

export type Tick = { readonly key: string; readonly x: number; readonly newest: boolean }

export type Ribbon = {
  readonly blocks: readonly Block[]
  readonly ticks: readonly Tick[]
  /** Cards in the sittings older than the window, and how many there are. Null when the
   *  window covers everything, in which case no plinth is drawn. */
  readonly plinth: { readonly cards: number; readonly sittings: number } | null
  readonly minutes: number
  readonly days: number
  readonly from: string | null
}

export const VIEW_W = 620
export const BAND_H = 40

export function ribbon(all: readonly Sitting[]): Ribbon | null {
  if (all.length === 0) return null
  const shown = all.slice(-WINDOW)
  const older = all.slice(0, all.length - shown.length)
  const totalMinutes = shown.reduce((s, x) => s + x.minutes, 0)

  /* Widths are shares of the shown window's minutes. A window of durationless sittings has no
     width to share out at all, and draws as ticks alone rather than as a division by zero. */
  let x = 0
  const blocks: Block[] = shown.map((s, i) => {
    const w = totalMinutes > 0 ? (s.minutes / totalMinutes) * VIEW_W : 0
    const pace = s.rate === null ? 0 : Math.min(1, s.rate / RIG_CEILING_PER_HOUR)
    const h = pace * BAND_H
    const block: Block = {
      key: s.from,
      x,
      y: BAND_H - h,
      w,
      h,
      pace,
      newest: i === shown.length - 1,
      durationless: s.rate === null,
      sitting: s,
    }
    x += w
    return block
  })

  /* The rug is the real calendar over the shown window. One sitting has no span to divide, so
     its single tick sits at the right-hand end where the newest mark belongs. */
  const t0 = Date.parse(shown[0]!.from)
  const t1 = Date.parse(shown[shown.length - 1]!.from)
  const span = t1 - t0
  const ticks: Tick[] = shown.map((s, i) => ({
    key: s.from,
    x: span > 0 ? ((Date.parse(s.from) - t0) / span) * (VIEW_W - 3) : VIEW_W - 3,
    newest: i === shown.length - 1,
  }))

  return {
    blocks,
    ticks,
    plinth: older.length > 0 ? { cards: older.reduce((s, x2) => s + x2.cards, 0), sittings: older.length } : null,
    minutes: totalMinutes,
    days: span > 0 ? span / 86_400_000 : 0,
    from: all[0]!.from,
  }
}

/* ─── THE DEMO'S HISTORY MULTIPLIER ─────────────────────────────────────────────────────────
 *
 * THIS IS THE ONE FIGURE IN THIS PRODUCT THAT IS NOT READ FROM THE STORE. It exists only in a
 * `VITE_DEMO=1` build: everywhere else `__BN_DEMO__` folds to the literal `false` and Rollup
 * deletes the branch, so an ordinary build cannot reach it and `inflate` is the identity.
 *
 * WHY IT EXISTS. The published demo store holds 122 cards. At any cadence the rig can actually
 * run — between the 0.6095 s a card `docs/specs/motion-trigger.md` measures and the ~4.2 s a
 * card the owner's real store averages — 122 cards is EIGHT MINUTES of work, and a front page
 * whose headline figure is eight minutes undersells the product to a stranger who has never
 * seen it. The honest fix is a bigger demo store, and it was costed: ~3.8 KB of recorded
 * bundle and ~34 KB of photograph per card, because `scripts/demo-record.py:copy_photos`
 * writes one file per card INDEX and D52 makes that URL name a photograph rather than a
 * shareable image. Real-store scale is ~55 MB of published copies of 132 source pictures. The
 * owner chose the fiction over the megabytes, on 2026-09-09 and with that trade stated.
 *
 * IT SCALES CARDS AND MINUTES BY THE SAME FACTOR, WHICH IS THE WHOLE TRICK. `rate` is
 * cards ÷ minutes, so a common factor cancels out of it entirely: every block keeps the height
 * it has today, the widths were always SHARES of the window's minutes and so never moved
 * either, and `minutes × rate ÷ 60 = cards` still holds. The drawing is the one it draws now,
 * relabelled. Scaling minutes ALONE is what this avoids — height IS the rate, so it flattens
 * all six blocks from ~8px to under 1px and destroys the thing it was meant to dress up.
 *
 * WHAT IT DOES NOT TOUCH: the present. `onHand`, the box count and every panel below the foot
 * are the store's own, because they are drawn twice on one screen and two figures from one
 * store may not disagree with each other four inches apart. What is inflated is HISTORY —
 * cards ever photographed, cards ever sold, and how long each sitting took — which is the
 * clause a viewer cannot cross-check against anything else on the page.
 *
 * 13 puts the demo at ~1.8 hours over six sittings and ~1,573 cards, which is within a few
 * percent of the owner's real store (1,625 cards, 113 minutes, six sittings). It is a
 * multiplier rather than a target so the two halves of the sentence cannot drift apart when
 * the seed's card counts next change.
 */
export const DEMO_HISTORY_SCALE = 13

/** The sittings a demo build draws. The identity everywhere else. */
export function inflate(all: readonly Sitting[]): readonly Sitting[] {
  if (__BN_DEMO__) {
    return all.map((s) => ({
      ...s,
      cards: s.cards * DEMO_HISTORY_SCALE,
      sold: s.sold * DEMO_HISTORY_SCALE,
      minutes: s.minutes * DEMO_HISTORY_SCALE,
      /* Untouched on purpose, and not recomputed: a common factor cancels out of
         cards ÷ minutes, so re-deriving it here could only introduce float drift. */
      rate: s.rate,
    }))
  }
  return all
}

/** Everything this store has ever photographed.
 *
 *  `status.cards` counts records and is already on Home's critical path; `states.moved` is
 *  D83's departure door, which writes a tombstone in the source box AND a transplant in the
 *  destination, so the move must come back off. This is deliberately NOT `Σ boxes[].cards`,
 *  which counts both halves of every move and is silently high, and not
 *  `Σ on_hand + sold + retired` either, which sums a nullable field — `on_hand` is null exactly
 *  when a box could not be counted, and a sum with a null in it is not a sum. */
export function photographed(status: ServerStatus): number {
  return status.cards - (status.states.moved ?? 0)
}
