## D-reasoning-is-not-screen-copy — A decision's argument is not screen copy, and a note about zero does not draw

**The owner's rulings, 2026-09-23.** Seven decisions put part of their own argument on the
owner's screen. The owner ruled on all seven.

- Six notes go, entirely: D100's age note, D168's clear rule, D134's "Read-only", D70's "the QR
  is the code", D102's sweep history on the Kit, and D86's migration note.
- D225's two notes on Sales draw only when their count is above 0, as "3 refunded lines left
  out".

The record of the review is `docs/reviews/ux-2026-09-23/`, lens `density.md`. The owner also
ruled to cut every line the density lens proposed, about 4,200 words. This entry covers only
the lines a decision required.

### The premise that no longer holds

Each decision assumed that its argument helps the owner when it is restated on the screen. The
density lens measured the cost. The lines repeat a fact the screen already shows, or explain a
mechanism the owner does not act on.

| Decision | The line on screen | Finding |
|---|---|---|
| D100 (the age is a proxy that says so) | A 52-word note on how a listing's age is dated, in the Mark-down sheet | TXT-13 |
| D168 (a typed price is cleared by a press) | "Nothing expires on its own — an answer stands until you clear it." | TXT-14 |
| D134 (the graveyard is where the departed are read) | "Read-only." on a screen with no edit control | TXT-38 |
| D70 (the QR is the whole identification) | "Free — the QR is the code." | TXT-39 |
| D102 (the mark's spec is its store of record) | Ten history notes, 436 words, and two repository paths on the Kit | TXT-44 |
| D86 (the pricing answer is one file for the store) | "one answer for the whole store now" | TXT-20 |
| D225 (a sales truth) | Two sentences about zero on Sales, every day | TXT-36 |

### What each decision protected, and what protects it now

**The mechanisms stay. Only the sentences go.**

- **D100** protects one outcome: nobody reads the proxy age as a real listing age. The report's
  own header and the harness block keep the proxy statement. The screen paragraph goes. The
  browser spec that asserts it must change in the same commit. On the screen, nothing replaces
  it. The owner accepted that cost.
- **D168** protects a typed price that nothing clears by time. The press is scoped, counted and
  reversible without the sentence.
- **D134** protects a record of every departed card. A screen with no edit control already reads
  as read-only.
- **D70** protects an identification that makes no model call. The Codes feature is dormant.
- **D102** protects one store of record for the mark. `docs/specs/logo.md` holds the sweep
  history. The Kit draws the mark, not its history. D196 (no user-visible string names a
  repository path) removes the two paths anyway.
- **D86** protects one pricing answer for the store. The migration ended. The word "now" has
  no reader.
- **D225** protects two outcomes. The owner knows that refunds and cancellations are left out.
  The builder can see that the mechanism is wired. A note that draws when its count is above 0
  keeps the first. A browser spec with a refunded line in its fixture keeps the second. That
  check belongs in a test, not on the owner's screen.

### Who builds each part

NOT BUILT. The kit-frame lane removes D102's notes. The library lane removes D134's and D70's
lines. The sales lane builds D225's rule. D100's and D168's lines sit in Pricing sheets, so the
pricing lane removes them. The Live tab replaces the Mark-down sheet in that lane. D86's line
sits on the run page, so the runs lane removes it. The owner released both lanes.
