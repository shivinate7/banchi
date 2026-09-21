# Desktop UI/UX review, 2026-09-20

Sixteen per-screen logs from four agents working in parallel against the owner's live
server on :8000. Read-only: nothing was pressed that writes, no server was restarted.

## The standard these were written to

The owner's instruction was to judge the UI **purely on its own merits**. The agents were
told to ignore `docs/`, every decision entry, every D-number and the word-count ratchet,
and to treat a defect as a defect even where a rule produced it. A recommendation here may
therefore contradict a settled decision. That is deliberate and is the owner's call to
weigh, not a mistake in the report.

They were also told that every pixel counts and that a nit is weighted as heavily as a
large finding, so the volume of small items is intentional.

## The files

| File | Covers |
| --- | --- |
| `system.md` | The design system judged as a system: type scale, spacing, color ramp with measured contrast, radii, shadows, motion, interaction states, duplicated primitives |
| `shell.md` | Sidebar, rail, top bar, command palette, keyboard sheet, toasts, offline banner, error boundaries |
| `kit.md` | The component sheet at `#/gallery` and every primitive on it |
| `home.md` `capture.md` `runs.md` `review.md` | Owner screens |
| `inventory.md` `orders.md` `shipping.md` `graveyard.md` | Owner screens |
| `pricing.md` `sales.md` `product.md` `codes.md` | Owner screens |
| `fulfillment.md` | The Fulfiller's shell-less screen |

## Before you rank anything, read this

1. **Coverage is uneven and each file names its own gaps.** Two agents lost the browser
    pane partway through. 1440/dark is measured throughout; 1280 and light theme are
    measured in some files and UNKNOWN in others. Every file ends with a
    "What I could not check" section. An UNKNOWN is not a pass.
2. **Severity labels are not in one format across the four agents.** The counts cannot be
    tallied mechanically as they stand. Re-tally by hand.
3. **Mobile was out of scope.** Desktop only, 1440 and 1280.
4. **Findings are not deduplicated across files.** Several recur — the undefined custom
    properties appear in at least four.

## The one thing that already looks settled

Five CSS custom properties are referenced and never defined, so they resolve to nothing
and the rule is dropped silently:

| Property | Referenced at | Effect |
| --- | --- | --- |
| `--bn-r-md` | `app/src/CaptureScreen.css:154` | corner radius lost |
| `--bn-radius-md` | `app/src/OrdersWalkPane.css:15` | corner radius lost |
| `--bn-well` | `app/src/Pricing.css:835` | pill loses its muted ground |
| `--bn-muted` | `app/src/Pricing.css:836` | pill text renders full strength |
| `--bn-border` | `app/src/ProductHistory.css:75` | `border-style: none`, panels near-invisible in light theme |

Confirmed live, not read off the stylesheet. A linter that fails a build on a `var()` with
no definition and no fallback would have caught all five, and nothing in the repo reads for
this today.
