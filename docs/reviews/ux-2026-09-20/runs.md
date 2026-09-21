# Runs (`#/runs`)

Widths looked at: 1440 (measured in depth; also screenshotted earlier in this session, dark
and light). 1280 not independently re-measured this pass — UNKNOWN beyond the earlier
qualitative screenshot pass (dark and light, both looked correctly reflowed, no overflow
seen by eye).
Themes looked at: dark (measured + screenshotted earlier), light (screenshotted earlier only,
not re-measured numerically this pass).
Store state: real run list (17 runs), one run selected to load its detail pane. No join/emit/
reconcile/identify pressed.

## Findings

1. **Header title uses the same 28px/800-weight scale as every other `PageHeader`-based
   screen (Review, Pricing, Codes, Graveyard, Shipping, Revenue) — confirmed identical, not
   just visually similar.**
   Measured: `.bn-head .bn-title` on Runs is `28px`/`800`; the same selector on Review is
   `28px`/`800` (measured directly, see review.md). No defect; recorded because a heading-size
   mismatch was one of the explicit things to hunt for, and this pair is clean.

2. **Header action buttons (Reload / Reconcile the store / Identify cards) sit at a uniform
   8px gap from each other, and all three share the same 34px height and 8px border-radius.**
   Measured: reload button x=493.9 w=34, Reconcile button starts at 535.9 (gap = 535.9 −
   493.9 − 34 = 8.0px exactly), Identify cards starts at 722.3 (gap = 722.3 − 535.9 − 178.4 =
   8.0px exactly). All three: height 34px, border-radius 8px, font-size 13px. No defect;
   recorded for completeness.

3. **Every run row's status bar (the thin progress strip under each run's name) repeats at an
   exact 81.5px vertical rhythm with a fixed 288px width, for at least 10 consecutive rows.**
   Measured y-steps: 285.3 → 366.8 → 448.3 → 529.8 → 611.3 → 692.8 → 774.3 → 855.8 → 937.3 →
   1018.8, every gap exactly 81.5px. No defect; recorded for completeness — this is exactly
   the kind of "uneven gaps in a row" defect class the brief asked me to hunt for, and I did
   not find one here.

4. **Sidebar rail-collapse-on-resize bug (see shell.md finding 1) also governs Runs' left
   inset**, same as every other screen — not re-described here in full.

## What I could not check

- **1280 width was not re-measured this pass with the JS instrumentation** used on Home/
  Capture/Review — I relied on the earlier-session screenshot pass (dark and light, both
  looked correctly laid out with no overflow), which is a lower bar of evidence than the
  measured numbers reported above for 1440. Treat 1280 findings for Runs as UNKNOWN at the
  measured-pixel level, confirmed only qualitatively.
- **Light theme was not re-measured numerically** this pass; only the earlier qualitative
  screenshot (looked correct: same layout, tokens swapped, no obvious broken contrast).
- **The run detail pane's own internal layout** (once a run is selected — join/emit buttons,
  the file list, the console log) was only spot-checked for the presence of a detail view; I
  did not measure its headings, button gaps, or icon alignment in the same depth as the list
  and header. UNKNOWN at pixel level.
- **The composer (Identify cards) and Reconcile-the-store dialogs** were not opened, since
  both are the entry points to money-spending or store-wide-write flows — opening the dialog
  itself is likely safe (no write until confirmed) but I judged it not worth the risk this
  pass given the explicit fence against pressing anything that writes, and did not verify
  where the safe/unsafe line inside that dialog actually falls. UNKNOWN.
- **Hover states on run rows and header buttons** were not sampled at the hover midpoint
  (Browser pane hidden most of this pass); only `transitionDuration` was measured (all clean,
  120ms, no drift found — see the cross-screen sweep noted in shell.md and home.md).
