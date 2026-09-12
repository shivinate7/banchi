## D85 — The corner is settled by geometry, and a variable nothing sets is not a fallback

**Built 2026-09-01, from a screenshot the owner sent while pricing box 4.** The pricing screen
had gone to pieces under them mid-run: stray letters strewn across the ship bar, the emit
receipt and the card rows drawn through each other. Reproduced exactly against a copy of
`runs/2026-09-01-box4-01`, then measured rather than eyeballed.

### What was actually wrong

`bbf7e11` (merged to main 2026-09-01 as [#95]) reordered the pricing row and moved `T` and `H`
into the row's left gutter — which is the **bottom-left corner of the screen**, and three other
things already lived there: `.pricehistory` and `.pricing-photo`, both `position: fixed` at
`z-index: 20`, and `.pricing-ship`, `position: sticky` at `z-index: 10`. That commit noticed the
first collision and settled it with a stacking order, raising the two buttons to `z-index: 21`
so the panels could not swallow their clicks.

**It inverted the defect instead of removing it.** At 21 the buttons draw over the panels *and*
over the ship bar. Hit-testing an 8px lattice on the real screen:

| | points a hidden `.pricing-row` answered for |
|---|---|
| inside the ship bar, receipt up | **48** |
| inside an open reading | **143** |

Those are not cosmetic. `elementFromPoint` at the bar's left edge returned a scrolled-away
row's `H` — so a press aimed at the bar took a **hold** on a card nobody could see, and a hold
writes `decisions.json`.

### Ruling 1 — four things wanted one corner, and a stacking order cannot arbitrate that

Whichever element wins a `z-index` contest, something a hand is aiming at stops answering.
There is no ordering of these four that is correct, because all four are simultaneously
visible and all four are pressed. The contest was run once and produced a worse screen than
not running it.

**So the overlap is removed rather than ordered.** `.pricing` publishes
`--pricing-gutter` — the page's padding plus the two button columns and their gaps, composed
from the same `--pricing-btn` the grid template reads — and both fixed panels start there. No
panel is ever over a `T` or an `H`, and the buttons carry no `position` and no `z-index` at
all. **The absence is the fix**; a row's controls stack like everything else in the document.

Derived and never typed: a hand-written `104px` is the two-declarations-that-must-agree drift
`Pricing.css` already refuses for its grid template, arrived at from the other end.

### Ruling 2 — `--pricing-ship-h` is measured, because a fallback is not a value

D54 positioned both panels above the ship bar with
`bottom: calc(var(--pricing-ship-h, 64px) + var(--s4))`.
**Nothing has ever set `--pricing-ship-h`.**
Three declarations across two stylesheets read it; `getComputedStyle`
returned the empty string. Every one took the `64px` fallback, against a bar that measures
**125px closed and 433px with an emit receipt up**.

Wrong in the direction that buries the bar's own sub-threshold controls — `At the $0.40
floor`, `A flat price`, and the flat input — under the reading panel. Those are the answer
`emit` refuses to run without. All three took no press at all: hit-testing each one's own
centre returned `.pricehistory`.

`Pricing.tsx` now publishes the bar's measured height from a `ResizeObserver`. The bar grows
when the receipt lands, when a refusal is drawn, and when the window narrows enough to wrap
its rows — none of which re-renders the component, so a one-shot measurement at mount would be
wrong and would report as green.

**The panel shrinks rather than overlapping when the bar is tall.** `PriceHistory.css`'s
`max-height` already subtracted `--pricing-ship-h` and had nothing to subtract; with a real
value it does what it was written to do. That is the right trade: a reading is a transient
overlay, and the run's answer controls are not.

### Ruling 3 — the missing check was geometric, and it is asked by hit-testing

`app/tests/pricing.spec.ts` was **56 passed** on the broken screen. Typecheck green, lint
green, `make check` green. Every case in it was still true: they assert text, grid templates
and row heights, and none of those moved.

Three cases were added and each was **run against the pre-fix tree and failed** — 48
punctures, 143 punctures, and a published height that was the empty string.

They hit-test rather than compare rectangles, and that distinction is the entry's point.
`fulfillment.spec.ts:648` has an `overlaps()` helper and it is deliberately not reused here:
two boxes intersecting is the normal, correct state of an overlay above a list. The fault was
never the intersection — it was **who answered inside it**. `elementFromPoint` asks what a
hand aiming at a pixel actually reaches, which is the property that broke, and it is
indifferent to how a later change breaks it: a stacking order, an anchor, or a width.

**What would reopen this:** a fifth thing wanting the bottom-left corner. The gutter has room
for the panels and the bar and nothing else, and the answer would not be another offset — it
would be moving one of them to a corner it can have alone.

[#95]: https://github.com/shivinate7/pkmnscan/pull/95

---
