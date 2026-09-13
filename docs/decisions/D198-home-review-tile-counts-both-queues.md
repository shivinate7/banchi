## D198 — Home's Review tile reads the same total `#/review` draws, never `review` alone

**The report, 2026-09-13:** Home's Review stage tile said "0 · nothing waiting" and painted
green while `#/review` itself showed "Card 1 of 1 · 1 parked" — the same store, two screens
disagreeing about whether anything needed the operator's attention.

**Root cause.** `app/src/Home.tsx`'s Review tile keyed its whole sentence — figure, note and
tone — off `review === 0` alone, reading only the main queue's count off `GET /status`. A
parked entry is not nothing: `store/queues.py`'s own `STAND_DOWN_REASONS` comment and
`ReviewQueue.tsx` both treat it as a live, answerable question — low-value, explicit, worked
last rather than never — and Review's own headline (`total = everyone.length + done`, where
`everyone` is `review` and `parked` merged by position) counts it every time, drawing
`counts.parked` beside the headline whenever it is nonzero. `/status` was never wrong —
`server/capture_server.py:_queue_depth` answers each queue's own depth correctly and
per-queue, by design, so a corrupt `review.json` cannot hide `parked`. The defect was entirely
in how `Home.tsx` combined two numbers it already had.

**The fix.** The tile's figure is now `review + parked` — the same total `#/review`'s headline
reaches in steady state, where `store/queues.py:apply_run` keeps a position out of both files
at once. The transient overlap `ReviewQueue.tsx:oneCardPerPosition` dedupes against is not
observable from `/status` alone and is not worth a second `/queues` fetch on Home just to
dedupe a state that is already rare — a named, accepted imprecision rather than a silent
mismatch. The note never says "nothing waiting" and the tone is never `'ok'` (green) while
either queue holds an open entry: both must read zero for the calm state, mirroring
`#/review`'s own "Card N of M · Y parked" shape.

**This is CLAUDE.md's own front-end rule, applied to one tile.** "Every figure on Home is the
one that stage's own screen draws, read from the same source" (`#/` section) — Home was
computing a second, narrower vocabulary for "does Review need attention" instead of reading
Review's own answer.

**Guard.** `app/tests/nav.spec.ts:"the Review tile never says nothing waiting while a card is
parked"` stubs `GET /status` with `queues: { review: 0, parked: 1 }` and asserts the tile's
text never contains "nothing waiting", its figure is not `'0'`, and it never carries the
`home-stage-ok` tone class. Red on the unfixed tree (figure `'0'`); green after.

**What this does not touch.** `app/src/standing.ts`'s top banner has the identical shape of
gap — a parked-only state falls through toward "Clear — nothing is owed anywhere" without
naming the parked card — and is deliberately left alone here: whether the standing SENTENCE
should promote a parked-only state above "Clear" is a judgment call, since parked is
deliberately the low-priority, bulk-lot-bound queue and "Clear" may be intentionally true from
that banner's point of view even while this tile is not. Flagged for the owner rather than
decided.
