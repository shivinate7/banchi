# Design

Two audiences, two standards. The owner's screens are a tool — dense is fine. The
Fulfiller's screens are the entire product for a retired, non-technical user, and "if a
flow needs explaining twice, redesign the flow" is a real requirement with no way to check
itself. So it is written below as numbers.

## Lock tokens before building any screen

Fill this in before step 7 of the build order, then build **one** component against it
(the pull-confirm button in default / pressed / disabled) and look at it. Catching a gap on
one component is far cheaper than after ten screens.

```
Color      — 4–6 named hex values. Not a purple-to-indigo gradient.
Display    — one characterful face, used with restraint.
Body       — one complementary face. Not Inter.
Utility    — one face for positions and counts. Tabular figures required:
             "Box 3 · Section 2 · Card 17" must not shift width between cards.
Spacing    — one scale.
Radius     — one value.
```

**Negative constraints carry as much weight as positive ones.** Write down what this is
not: no card-grid dashboard, no soft drop shadows, no three-column feature row. Without
them the model fills the gap with the statistical center of its training data, and that
center has a recognizable face.

## Fulfillment view — hard constraints, assert these in a test

The agent cannot see its own output, so these are Playwright assertions, not prose:

| Constraint | Assertion |
|---|---|
| Body text | `font-size >= 20px` on every text node in the view |
| Position label | `font-size >= 32px`, tabular figures |
| Card photo in pull modal | `>= 320px` on the short edge |
| Tap targets | `>= 44 x 44 px`, `>= 12px` apart |
| Contrast | `>= 7:1` for body text (WCAG AAA — assume reading glasses and a bright room) |
| Destructive actions | zero reachable from this view; assert no route to settings or import |
| Undo | present on every mark-sold, `>= 10s` window |
| Jargon | copy passes a banned-word list: SKU, CSV, import, sync, batch, queue, staged |

Default view on the Fulfiller's device. Sorted in box-walk order. Photo-confirm before each
pull. One-tap mark-sold.

## The screenshot loop is mandatory

`make screenshot` renders the key views to `captures/ui/`. Claude Code writes CSS it has
never looked at, so a layout that is technically correct can still be broken. Every UI
change: render, screenshot, compare against the reference and the table above, fix, repeat.
Two or three rounds gets to a production layout; zero rounds gets the generic default.

Give it a real visual reference before it codes. An adjective like "clean" produces the
average of everything the model has seen. A screenshot produces something specific.

## Copy rules

Active voice. The button says exactly what happens. An action keeps its name through the
whole flow: the button that says "Pull" produces a confirmation that says "Pulled."
Name things by what the Fulfiller controls, never by how the system is built — he has
orders and cards, not SKUs and rows. Errors say what happened and what to do next.
