# Fulfillment (`#/fulfillment`) — UX review

## Coverage
- Widths: 1440x900, 1280x860 (desktop only, per brief).
- Themes: light (default) and dark (forced via `document.documentElement.setAttribute('data-theme','dark')` — no in-screen toggle exists on this shell-less screen, so this is the same mechanism the app's own toggle uses).
- States reached: empty-orders landing state ("No orders are waiting..."), box-browse list, expanded box disclosure with card rows, single-card detail panel (photo + "Where to find it" + position bar + "Pull this card" step). Both 1440 and 1280 use the >=1100px two-column card layout (440px photo column).
- States NOT reached: an open-orders "Cards to pull today" hero, the receipt/undo sheet after a pull, the "Marked sold" second step, multi-order walk, search-results view (typed a query but it did not land in the input in the shared browser — see "What I could not check"), the "no photograph" and "trouble" states, the disabled Pull-confirm state (kit says it never appears here, so this is expected).
- Method: CSSOM measurement via JavaScript (`getBoundingClientRect`, `getComputedStyle`) cross-checked against `app/src/Fulfillment.css`, plus screenshots where the Browser pane was displayed.

## Findings

1. **Position caption sits above its own track, contradicting the file's own layout comment.**
   What I saw: in the card panel, "Card 1 of 542" (the `.position-bar-text`) renders ABOVE the rounded progress track, not below it.
   Where: `app/src/Fulfillment.css:759-794` (`.ff .position-bar-fulfiller`); the file's own preceding comment at line 759-761 describes the intended drawing as "a rounded track ... and the caption under the track." The rule that produces the observed order is `.ff .position-bar-fulfiller > .position-bar-text-box { order: 0; align-self: flex-start; }` (line 794), which places the text-box before the track in visual order because the track carries no explicit `order`.
   Severity: nit. It is a legible, common pattern (label above a progress bar), so it is not a usability problem on its own — flagged because the shipped layout does not match the sentence written to justify it, which is a sign the rule was edited after the comment and nobody reconciled them.
   Fix: either add `order: 1` to the track so the caption truly sits under it (matching the comment), or rewrite the comment to say "caption above the track."
   Recurs: no — this is the only position-bar-fulfiller instance on this screen.

2. **`.ff-step` ("Pull this card") is the loudest element on the card panel by size, yet is styled as the quiet/outline variant.**
   What I saw: a 600×64px, 22px/700-weight button with only a 2px inset border (`box-shadow: inset 0 0 0 2px var(--bn-ink)`) and a surface background — no fill, no accent color — as the single call to action on a screen built for someone under time pressure who is not supposed to "read twice."
   Where: `app/src/Fulfillment.css:841-860` (`.ff-step`).
   Severity: medium. The brief's own framing — "whether a stressed person can use it without reading twice" — is exactly what a low-contrast, unfilled 64px button works against: an outline button reads as secondary/optional at a glance, and this is the only action on the card. Every other "loud" primitive in the product (`.bn-btn-primary`, `.ff-start`) uses a solid fill for the one thing to do.
   Fix: give `.ff-step` a solid fill (ink or accent) so its visual weight matches its role as the only action, reserving the current outline treatment for a true secondary action if one is ever added beside it.
   Recurs: the same quiet treatment appears on `.ff-quiet`/`.ff-back` (line 340-363), which is correct there (those really are secondary "Back"/"Try again" actions) — so the inconsistency is specific to `.ff-step` being visually secondary despite being the only thing to press.

3. **Box list rows and "Or look through a box" disclosure rows are visually identical to a plain white background — 1px hairline `--bn-line` (8% black) is the only separation from the `--bn-bg` page.**
   What I saw: `.ff-box` panels sit on `--bn-bg` (`#f4f5f8`) with `background: var(--bn-surface)` (`#ffffff`) and `box-shadow: var(--bn-shadow-1)` only (`0 1px 2px rgba(15,18,23,.05), 0 0 0 1px rgba(15,18,23,.05)`) — a hairline at roughly 5% black opacity. At arm's length (the screen's own design goal, per DESIGN.md's Fulfillment floors this review is told to ignore, but the same physical fact holds on merit alone) this is a very faint edge between a white card and a near-white page.
   Where: `app/src/Fulfillment.css:515-522` (`.ff-box`), and the same shadow on `.ff-order` (467-474) and `.ff-more` (1017-1024).
   Severity: nit. Measured contrast of the shadow's outer ring against the page is far below any text threshold (it's a boundary line, not a text run), but it is worth flagging because it's the same softness that ordinary panels use, and this screen is specifically supposed to read fast under stress. The 5 boxes in the list on the empty-orders screen do stack legibly because of the row `min-height: 76px` and internal contrast, so this is a nit, not a usability blocker.
   Fix: consider `--bn-shadow-2` (which adds a real drop shadow, not just a 1px ring) for list containers on this screen specifically, to give the row grouping more separation.
   Recurs: yes, same treatment on Owner-side panels throughout the product (this is the system default, see `system.md`).

4. **Box number chip and card-name/count text baseline centers align correctly, but only because both blocks happen to sum to matching heights — this is coincidental, not composed.**
   What I saw: `.ff-box-num` is a 48×48px chip; the adjacent text stack (`.ff-box-name` 22px/700 + `.ff-box-count` 20px/400) totals 501.49–556.09 = 54.6px of visual content, centered inside the 78.59px-tall row at the same vertical center as the 48px chip (measured: chip center y=528.79, text-stack center y=528.79 — exact match). Both are centered independently by `align-items:center` on the flex row, so they're correct by construction, not by height-matching accident. No defect — recorded here because it was checked, not assumed, per the instruction to measure rather than eyeball.
   Where: `app/src/Fulfillment.css:524-554`.
   Severity: n/a (verified correct, not a finding — left in for completeness of what was checked).

5. **The "look through a box" section icon (a small boxed glyph) sits noticeably smaller and more muted than the section heading beside it, while `.ff-h2-icon` (a different, 32×32px rounded-square icon chip used elsewhere in this same file) is the "real" heading-icon pattern.**
   What I saw: `.ff-browse-lede`'s preceding heading uses a bare icon (no chip, no background) directly inline with "Or look through a box" text, while `.ff-h2` (used for "Pulled today" and "Orders to fill" headings, per the CSS) wraps its icon in a 32×32px rounded chip (`.ff-h2-icon`, `border-radius:10px`, `background: var(--bn-surface-2)`).
   Where: `app/src/Fulfillment.css:136-158` (`.ff-h2`/`.ff-h2-icon`) versus the box-browse heading markup (not class-named the same in the CSS — the "Or look through a box" row does not appear to use `.ff-h2` at all based on the DOM text scrape, which showed a bare package icon before the heading).
   Severity: nit. Two heading styles for what is functionally the same kind of section label ("what group of cards is this") is an inconsistency a user won't consciously notice, but it means the screen has two heading systems instead of one.
   Fix: use `.ff-h2`/`.ff-h2-icon` for the box-browse heading too, for one heading language on this screen.
   Recurs: could not fully confirm the exact class on the box-browse heading without reading `Fulfillment.tsx`'s JSX directly for that row; flagged as observed-not-code-confirmed.

6. **Dark theme: the `.ff-step` outline button's 2px inset border color is `--bn-ink` (near-white, `#eef0f4`), which — combined with the small 64px height and full 600px width — draws as a very bright, thin rectangle around a near-black interior.** This was verified NOT to be a background-fill bug (computed `background-color` is confirmed `rgb(20,23,28)`, i.e. `--bn-surface`, matching the light-theme structure) — but the visual result in dark mode is a much higher-contrast outline than the light-theme version (light: 2px `--bn-ink` `#0f1217` border on a `#ffffff` surface = a dark line on white, common; dark: 2px near-white border on near-black = a bright halo). The two themes do not read as "the same button, different palette" — dark mode's version reads noticeably more like an alert/focus outline than a normal button.
   Where: `app/src/Fulfillment.css:841-860`.
   Severity: nit (this is a byproduct of finding 2 — once `.ff-step` gets a solid fill, this stops being an issue in both themes).
   Recurs: n/a.

7. **`.ff-empty-art`, `.ff-photo-missing`, and `.ff-today-none-icon` each define their own circular/rounded icon-badge treatment locally in this file** (44px circle with `--bn-ok-tint`/`--bn-ok`, 72px rounded-square with `--bn-accent-tint`/`--bn-accent`, and an inset-bordered rounded rect respectively) **rather than reusing one shared "icon badge" primitive.** The kit (`kit.css`) has `.bn-empty-art` (56×56px, `border-radius: var(--bn-r-xl)`, `background: var(--bn-accent-tint)`) which is almost exactly what `.ff-empty-art` reinvents at a different size (72px) with no other difference.
   Where: `app/src/Fulfillment.css:391-399` (`.ff-empty-art`) vs `app/src/kit.css:653-662` (`.bn-empty-art`).
   Severity: medium (this is a duplicate-primitive finding of the kind the brief asks to be weighted like a system defect, since it's the same shape solved twice a few files apart).
   Fix: give the kit's `.bn-empty-art` a size modifier (e.g. `.bn-empty-art-lg`) instead of Fulfillment re-declaring the same rule at a bespoke size.
   Recurs: see `system.md` for the full duplicate-primitive inventory across the app.

## What I could not check
- The open-orders "today" hero (`.ff-today`, `.ff-today-figure`, `.ff-start`) — the owner's live store currently has zero open orders, so this state (arguably the most important state on the screen — it is literally the reason the screen exists) was UNREACHABLE from data. UNKNOWN, not verified.
- The search-results state (typing a card name and seeing `CardLocations` results in the fulfiller skin) — a click in the shared Browser pane landed on a different agent's tab mid-session (see below) and I could not safely re-attempt a raw keystroke sequence into the search input afterward without risking further interference; the card-detail view was reached instead via the box-browse path, which exercises the same result-card component so the coverage gap is partial, not total. UNKNOWN for the pure search path specifically.
- The receipt/undo sheet (`.ff-sheet`, `.ff-receipt`, `.ff-undo`, the draining timer bar) — reaching it requires pressing "Pull this card," which WRITES to the store (claims a card), so it was correctly not pressed per the safety fence. UNKNOWN.
- The "Marked sold" second step (`.ff-pulled`, `.ff-trouble`) — same reason, gated behind a write. UNKNOWN.
- Screenshots for large parts of this session: the Browser pane was hidden for most of the run (shared with other agents in this worktree), so most 1280px and dark-theme verification after the first screenshots relied on CSSOM measurement rather than visual confirmation. Values reported above are measured, not eyeballed, but anything requiring an actual pixel-level visual read (anti-aliasing, gradient banding, subpixel rendering) is UNKNOWN for the 1280px and dark passes.
- 900px–1099px transitional width (the file's own comment describes a carefully-measured 900px breakpoint for the two-column card layout) was not explicitly checked — out of scope per the brief (desktop 1440/1280 only) but noted since the CSS comment implies real risk there.
- One incident: a `computer` click/type call without an explicit `tabId` landed on `tab-2`, another agent's active Pricing-screen tab, and typed one character ("a") into whatever had focus there before I noticed and corrected to always pass `tabId` explicitly. I read that tab afterward and saw no evidence of a submitted write (the page still showed its normal Pricing content), but I am flagging this transparently rather than omitting it.
