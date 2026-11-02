---
paths:
  - "app/**"
---

# The front end

Vite + React 19 + TypeScript over the capture server and nothing else, save one Bluetooth link to the dispenser (D316 (A Capture button starts and stops)). No pipeline logic in the
browser. No second store. No auth. `app/src/server.ts` is the only client-call file.
`app/src/types.ts` is the only wire-shape file.

## The screens

`ROUTES` in `app/src/App.tsx` is the one table of screens. Read counts and the off-nav set from it,
never from prose. The `route rosters` row of `make docs-audit` reconciles README's route table with
it. `#/fulfillment` is the Fulfiller's whole product, with no shell (D5, two personas).

- **A new screen is one `ROUTES` entry plus a view that returns `<Page>`** (D275, every screen inherits
  the page scaffold). `make kit-adoption` fails a view that skips `<Page>` or hand-rolls a kit
  primitive. `app/tests/scaffold.spec.ts` asserts the frame at 1440, 820, 720 and 390. Exceptions
  live in `scripts/kit-adoption-allow.json`, a list that only shrinks. A lane that moves a
  screen onto `Page` deletes its entries in the same commit.
- `#/orders` and `#/shipping` are two stages of one screen (`OrdersHub`), joined client-side on order number.
- `#/inventory` is the one owner-side view of stored cards (D31, one owner-side view). `#/boxes` and `#/pull` are not routes.
  Sold cards are hidden by default (D132, sold is folded away). Order under a search is frozen once taken, and a sale
  may not re-rank it (D181, the order is taken once).
- `#/runs` is off-nav and opens Review's runs sheet (D291, the fold).
- `#/product` is off-nav and deep-linked by SKU (D227, a route not a lens).
- `#/revenue` is a nav row on purpose (D214, gross-revenue retrospective). It is gross only, leaves out canceled orders and never claims profit.

## The design system

`app/src/tokens.css` is the only file in `app/` that names a color. `app/src/kit/markPalettes.ts`
is the one exception (D102, mark palette). It is generated, never hand-edited. Every token is `--bn-*`.
The legacy aliases at the foot of tokens.css are dead. A new rule may not read one.

- **Both themes are real.** A screen not looked at in dark is not verified. The `raw color` row of `make docs-audit` reads for hex literals.
- **Type has three roles.** `--bn-font-display` (Manrope, headings), `--bn-font-ui` (Inter),
  `--bn-font-mono` (JetBrains Mono, machine strings only: SKUs, run names, reason codes, key caps,
  card numbers). Tables use Inter tabular-nums. Money uses `.bn-money` (D221, money stays mono), asserted by
  `app/tests/text-checks.spec.ts`. Body is 14px.
- **The kit is `app/src/kit/` and `app/src/kit.css`.** `#/gallery` renders it. Reach for the kit before
  you write a primitive.
- **Register.** Sentences on screen, not machine strings. Enum values are labeled. An empty state is a
  sentence and one action. No user-visible string names a decision, a path or a pipeline noun (D196, no user-visible string may name a decision).
  The `no mechanism on screen` row of `make docs-audit` enforces it.
- **No typed middle dot or bullet (U+00B7, U+2022) in a user-visible string** (D218, a typed dot is a defect).
  CSS draws the separator. The `typed interpunct` row of `make docs-audit` enforces it, with a shrinking list (D280, lists of offenders).
- **Text shape is three checks, none a count** (D284, three checks replace one ceiling):
  all in `app/tests/text-checks.spec.ts`, one sweep. Each reads
  a shrinking allow list in `app/tests/`, keyed to the finding.
- **The mark is generated** (D102, the mark has its own palette). `scripts/build-mark.mjs` writes it. Never put a `border-radius` on it.
- **`base.css` sets four floors** (D50, feedback is the product's; D118, a press changes what is on screen):
  cursor, response, press and stability. `app/tests/cursor.spec.ts` and `app/tests/inventory.spec.ts` assert them.
- **Nothing on screen moves unless the person moved it** (D313 (Nothing on screen moves unless the)). A loading area holds its
  loaded size from the first paint, by construction and never by a tuned pixel. `app/tests/stability.spec.ts`
  asserts it, one row per case, over every nav screen read from `ROUTES`, plus the Fulfiller's.
- **One left edge, and only width varies** (D197, a page is anchored to the shell inset). `.bn-page` margin is `0`.
  `app/tests/page-edge.spec.ts` asserts it.
- **Same-role stacked buttons share a width** (D195, same-role buttons share a width). `app/tests/button-stack.spec.ts` asserts it.
- **Three silent motion rules.** A component's own `transition` replaces the floor's, so name every animated
  property. `background-image` cannot animate, so use an inset `box-shadow`. The press dip is `translate`.
  A screen's own emphasis is `transform: scale()`, never `translateY`. A control may not ease its own `:active` movement.
- **Motion is tokens.** Durations and easing are tokens. List rows stagger off `--bn-stagger`.
  `prefers-reduced-motion` is honored. Only loops that carry meaning keep turning.

## The shell

`App.tsx` is a hand-written hash router and the shell. It renders for every screen except the
Fulfiller's. The shell has these parts:

- A sidebar that folds to a rail (⌘.), a top bar and bottom tab bar on phones.
- A command palette (⌘K, the only way to `#/gallery`), `,` then a letter to jump, ⌘←/⌘→ to step the workflow ring.
- A keyboard sheet on `?`. A new key binding is not done until it is in `SHORTCUTS` (`app/src/App.tsx`).
- An error boundary per route. The Fulfiller's `plain` variant offers one button and no error text.
- A toast stack, an offline banner and the document title.

## Verifying a screen

- `cd app && npx tsc --noEmit` prints nothing.
- Look at it at 1440 and 820, in both themes. Look at 390 only on an owner phone report.
  The specs that assert phone layout are off by the owner's word: DEBT77 (every phone-width spec is off). One switch turns them back on:
  `PHONE_SPECS_ON` in `app/tests/phoneSwitch.ts`.
- Anything a thumb presses is 40px or more.
- `make design-check` asserts `docs/DESIGN.md`'s Fulfillment floors in a real browser.
