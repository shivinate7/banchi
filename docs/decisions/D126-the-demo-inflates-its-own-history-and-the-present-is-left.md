## D126 — The demo inflates its own history, and the present is left alone

**Built 2026-09-09, on the owner's instruction and against the recommendation recorded below.**
`app/src/storeHistory.ts:DEMO_HISTORY_SCALE` multiplies the HISTORY clause of Home's foot in a
`VITE_DEMO=1` build and nowhere else. Two separate things landed in the same session and only
the second is a fiction; keeping them apart is the point of this entry.

### First, a real defect: the demo store had never sat down at a rig

`scripts/demo-seed.py` stamped each box's `captured_at` evenly across the box's own age —
`stamp(age - offset * (age / len(rows)) * 0.8)`. Box 1's 42 cards landed **eleven hours apart**.
`storeHistory.ts` clusters at a 30-minute gap, so all 122 cards clustered **alone**: 122
sittings, every one spanning zero time, every `rate` null, every block `durationless`. The
ribbon drew six ticks and no rectangles at all.

**The drawing was never wrong.** It was correctly reporting a store whose capture history, as
recorded, was 122 instants. A session looking at the blank band and reaching for `Ribbon` would
have been editing the one part of this that was working.

Each box now carries `sittings` — `(days_ago, cards, seconds_per_card)` — and `capture_stamps`
walks it. The cadences lie between the rig's measured 0.6095 s a card
(`docs/specs/motion-trigger.md`, which is also the ribbon's ceiling) and the ~4.2 s a card the
owner's real store averages, and they VARY between sittings on purpose: a ribbon whose blocks
are all one height carries nothing the printed card count does not already say. The jitter draws
from `random.Random(SEED + box)` and not the caller's stream, because `state_for` draws from
that one and borrowing it would silently re-deal which cards are sold.

Six sittings, 8.2 minutes, blocks at pace 0.10–0.22. All of that is honest.

### Then the fiction, and what it was weighed against

Eight minutes is what 122 cards ARE at any cadence the machine can run, and a front page whose
headline figure is eight minutes undersells the product to a stranger who has never seen it.

**The honest fix is a bigger demo store, and it was costed rather than dismissed.** Seeded at
700 cards with photographs allowed to repeat — which is realistic, D7 being entirely about
duplicates aggregating by SKU — the store reads 50 minutes at unchanged paces. Real-store scale
is ~1,600 cards and ~1.9 hours, which is within a few percent of the owner's own 1,625 cards and
113 minutes over six sittings. What it costs:

| cards | reads as | published photographs | bundle |
|---|---|---|---|
| 122 | 8 min | 4.2 MB | 2.1 MB |
| 700 | 50 min | ~24 MB | ~4.4 MB |
| ~1,600 | ~1.9 h | ~55 MB | ~8 MB |

Bundle at ~3.8 KB a card, measured off the recorded routes: 1,232 bytes in the inventory
route plus ~2.5 KB across the three recorded pricing-worklist variants.
**The photographs are the real bill, and D52 is why they cannot be shared.**
`photoUrl` composes `/photo/<box>/<index>`, so
`demo-record.py:copy_photos` writes one file per card INDEX with no dedupe, and 1,600 cards
means 1,600 copies of 132 source pictures. Nothing TRACKED grows — `demo-assets/` stays 132
files and 4.5 MB, and the multiplication happens in `dist-demo/`, which CI builds and Pages
serves.

**The recommendation was the bigger store. The owner took the fiction over the megabytes**, with
the disagreement below stated in advance. That is the decision this entry records.

### It scales cards and minutes by the same factor, which is the whole trick

`rate` is cards ÷ minutes, so a common factor **cancels out of it entirely**. Every block keeps
the height it has; the widths were always SHARES of the window's minutes and so never moved
either; `minutes × rate ÷ 60 = cards` still holds. Measured before and after at a multiplier of
13: all six blocks byte-identical at 75.3/7.7, 82.8/5.5, 116.7/8.9, 45.2/5.4, 219.6/3.9,
80.3/6.9. **The drawing is the one it already drew, relabelled.**

**Scaling minutes ALONE is what this avoids**, and it is the obvious first attempt. Height IS
the rate, so ×13 on time alone flattens all six blocks from ~8px to under 1px — it destroys the
drawing in the act of dressing up the sentence.

13 is a multiplier and not a target so the two halves of the sentence cannot drift apart when
the seed's card counts next change.

### What is NOT scaled, and why that line is where it is

**History is inflated; the present is not.** Cards ever photographed, cards ever sold, and each
sitting's size and duration move. `onHand` and the box count stay the store's own, because the
boxes panel four inches below draws those same two figures from the same store.
**Two figures from one store may not disagree on one screen.**

The departed count is then DERIVED rather than scaled —
`everSold = total − onHand − retired × SCALE` — so `photographed − on hand − retired − sold` is
still zero at any multiplier. The sentence stays arithmetically true to itself: a store that
photographed 1,573, holds 100 and has sold 1,447 is a coherent store.

### What still disagrees, named so nobody repairs it by accident

This is a lie and it has seams. They are acceptable, not invisible:

- the **Boxes panel's** per-box `sold` figures sum to 19, not 1,447
- the **sidebar foot** says `122 cards`, being a present figure from `/status`
- `#/inventory` walks 122 real cards

None is reachable in one glance from the foot, which is why the line was drawn at history rather
than sprayed across the sum. **A session finding one of these has found this entry, not a bug.**

### A total time at the rig was built and then withdrawn

**Offered, looked at, and declined by the owner on 2026-09-09.** The foot prints the NEWEST
sitting's duration and has never printed a total, so the literal request — "shows activity like
x amount of hours spent" — had no clause to land in. One was written: `spent(minutes)` and an
`in <duration>` clause summing every sitting, ungated, reading `1.9 hours` off the owner's own
113 measured minutes and `1.8 hours` off the demo's inflated ones.

**It was NOT part of the fiction**, which is why it was offered separately and why the offer
named the distinction: on the real store it is a true figure the store has always had and never
shown. The owner was asked whether to keep it in both, gate it to the demo, or drop it, with the
consequence of the third stated in advance, and **chose to drop it from both.**

**This product therefore prints no total time anywhere, by decision rather than omission.**
The only duration on the screen is the newest sitting's — `234 cards into Box 4 in 14 minutes`
in the demo, `18 cards ... in 64 seconds` before the multiplier. A later session proposing to
add one is re-opening this paragraph, not filling a gap.

### It is confined, and a normal build cannot reach it

`__BN_DEMO__` is the bare identifier `vite.config.ts` folds to a literal, and the guard is
written as an `if` for the reason `demoFlag.d.ts` gives. `inflate` is the identity everywhere
else.
**Measured on an ordinary build: zero references to `DEMO_HISTORY_SCALE` in the output.**
`storeHistory.ts` and `Home.tsx` are the only two files that know, and `sittings`,
`ribbon` and `photographed` are all still pure.

### Reopening

**A bigger demo store retires this outright**, and that is the preferred end. Set the seed's
counts, let `pick_rows` repeat a photograph once the manifest is spent, and delete
`DEMO_HISTORY_SCALE` — the ribbon needs no change, because the multiplier never touched its
geometry. The question that decides it is whether ~55 MB of published photographs is worth
paying, and it is the owner's to answer twice.