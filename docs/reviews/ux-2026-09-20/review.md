# Review (`#/review`)

Widths looked at: 1440 (measured in depth; screenshotted earlier in this session, dark only).
1280 not measured this pass — UNKNOWN.
Themes looked at: dark (measured + screenshotted). Light not reached — UNKNOWN.
Store state: real queue, one `set_ambiguous` card open with 5 candidate rows. No answer
pressed, no skip, no re-check.

## Findings

1. **The pipeline's internal reason code is printed on screen, in a visible monospace chip,
   right next to its own human-readable translation — twice in the file.**
   What I saw: below the question "Which set is it from?", the sentence "Two sets share this
   number" is immediately followed by a small chip reading `set_ambiguous` in JetBrains Mono,
   11px, `rgb(131,139,152)` (the muted-ink token), inside a `background: var(--bn-surface-2)`
   pill with 2px/6px padding and `border-radius: var(--bn-r-xs)`.
   Where: `app/src/ReviewQueue.tsx:1685` (`<span className="review-code">{offer.reason}</span>`,
   the group/bulk-answer header) and `:1846` (`<span className="review-code" title="Reason
   code">{entry.reason}</span>`, the single-card header). Styling at
   `app/src/ReviewQueue.css:390-400`.
   Judging this purely as a designer, with no reference to any written rule: this is a raw
   enum value — `set_ambiguous`, and elsewhere `low_confidence`, `rarity_claim_mismatch`,
   `name_disputed` — shown to the person doing the work, immediately after a sentence that
   already told them the same thing in plain English. It reads like a leftover debug label.
   It also comes free in the visible-word budget: cutting it is a pure subtraction, no
   trade-off.
   Severity: medium (it's not broken, it's just unpolished — a sentence-then-jargon-code
   pairing that no other screen in the app repeats).
   Fix: delete the `<span className="review-code">…</span>` nodes, or, if the code is useful
   for support/debugging, move it into the existing `title="Reason code"` tooltip only (drop
   it from the visible flow) or gate it behind a small "Details" disclosure.
   Recurs elsewhere? Checked: this exact pattern (`review-code` class) exists in only this one
   file; grep across `app/src/*.tsx` for the class found no other screen using it. Isolated to
   Review.

2. **Question title (22px/800) and its reason-code sub-line sit in the same content column,
   x=719.5, both spanning w=688.5 — perfectly left-aligned to each other.** Measured directly.
   No defect; recorded for completeness (checked because "a heading that is 15 vs 16px" and
   similar alignment slips were explicitly called out as things to hunt for).

3. **The gap between the plain-text reason sentence and the reason-code chip is 8px, not 0,**
   despite the chip's own computed `margin-left: 0px` — the 8px comes from an implicit
   whitespace text node between the two JSX children (a newline + indentation in the source
   collapsing to one rendered space). Measured via a `Range` around the text node: text ends
   at x=888.58, chip starts at x=896.58. Not a defect — flagging only so a later reviewer
   does not waste time re-deriving where an "unexplained" 8px comes from.

4. **Candidate rows (the 5 alternate-set options) are a uniform 62px tall, with the name/meta
   text block consistently inset 54px from the row's own left edge** (773.5 − 719.5).
   Measured directly on the first row; not cross-checked against all 5 rows individually, but
   no visual irregularity seen in the earlier screenshot. Recorded as checked-but-shallow.

## What I could not check

- **1280 width** was not reached this pass for Review. UNKNOWN.
- **Light theme** was not reached this pass for Review. UNKNOWN.
- **The group/bulk-answer view** ("Answer all N together?") was read from source
  (`app/src/ReviewQueue.tsx:1670-1695`) to confirm the same `review-code` pattern exists there,
  but I did not navigate to a live group state to see it rendered and measure it — the store's
  current queue only offered a single ambiguous card, not a same-reason cluster. Confirmed in
  code, not confirmed on screen.
- **Answering, skipping, or re-checking a card** was not exercised — all three would write to
  the owner's real queue.
- **The five candidate rows' individual hover/press states**, and the "Up next" side rail's
  own internal spacing, were not measured beyond the one row reported in finding 4.
