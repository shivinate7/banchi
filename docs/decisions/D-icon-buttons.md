## D-icon-buttons — A common, repeated action is an icon with a required label, and a press that spends money or cannot be undone keeps its words

**The owner's ruling, 2026-09-24, ICONOGRAPHY.** Verbatim:

> i saw that retire got converted into an icon and its made me feel that there should be more
> iconography overall

The record is `docs/reviews/ux-2026-09-20/` (`RULINGS.md`, "ICONOGRAPHY"). Retire
(`app/src/Inventory.tsx`) already carried an icon-only control. An earlier ruling
(2026-09-20, "clearer icon only") gave it the `archive` glyph and a name. Seeing it done made
the owner ask for the pattern everywhere.

`docs/specs/iconography.md` is the detail. It carries the rule in full, the per-lane map of
every press in the code, the icon set, its collisions, and the risks. Read it first. This
entry is the ruling, the words-vs-icon split, and what the kit lane built and checked.

### The rule: words or icon

A common, repeated action becomes an icon button. Each carries a tooltip and an accessible
name. The list: Mark sold, Undo, Retire, Edit, Delete, Copy, Download, Open, Close, Filter,
Sort, and any action of the same kind.

A press that spends money or cannot be undone keeps its words: Send, Identify, Stand down,
and any press of the same kind. This is not a size or frequency split. Send is common too,
and it still keeps its word. What decides is the cost of a misread, not how often a control
is pressed.

`docs/specs/iconography.md` section 2 is the full seven-step order this resolves to,
including the Fulfiller exemption, the phone edge cases, and the dense-row limits.

### What is built

**`IconButton`** (`app/src/kit/index.tsx`). One primitive: an icon and a `label` prop.
`label` is required. An icon with no word is a guess, not a control. TypeScript refuses a
call site that omits it. `label` is the tooltip text, and the accessible name unless a
longer `name` overrides it for a dense row ("Undo the sale at Section 2, Card 5").

Two nested boxes. The outer `<button>` is the hit area: `min-width`/`min-height: 40px`
always, at every size. The inner face is the visual glyph, 28px at rest, so a packed row
stays dense while the target stays reachable. It reuses `.bn-btn` rather than a second
stylesheet. So it inherits the D117 thumb floor and the D50 cursor/response/press floors for
free — `button` is a bare-tag selector in `base.css`.

The tooltip (`.bn-icon-tip`, `app/src/kit.css`) is CSS only. `position: absolute` sits off
`.bn-btn`'s own `position: relative`, so showing it never moves anything else (D118). It
shows on real `:hover`, on `:focus-visible`, and on a touch long-press. It never shows on a
plain mouse `:focus`, so a click does not leave it stuck open. It is `aria-hidden`: the
accessible name is the button's own `aria-label`, never the tooltip's text.

`tone="danger"`, `pressed` (a toggle of one act, off the same pair `Chip` reads), `busy`, and
`badge` (a small count at the corner, `position: absolute`, never moving the layout) round
out the props. `docs/specs/iconography.md`'s "What IconButton carries" names each one.

Eight icons were added to `app/src/kit/Icon.tsx`, in the same 24-unit, 1.75-stroke idiom as
the rest: `sold`, `pencil`, `eraser`, `eyeOff`, `sortAsc`, `sortDesc`, `moveTo`, `grip`.
`ICON_MEANINGS` gained a row for these and for every other icon the vocabulary draws on.
`kit-adoption` fails a commit that drops one of these rows, or names a vocabulary icon
`PATHS` does not draw (`iconMeaningsGap`, self-tested both ways).

Every state is rendered on `#/gallery`, under "Icon button", between "Buttons" and "Keycaps".

**Seven kit-owned controls converted**, per `docs/specs/iconography.md`'s own list. The
overlay Close, the Toaster dismiss, the FacetChip clear, the SearchField clear,
`ReloadButton`, the compact `FilterBar` trigger, and `SortControl`'s direction toggle. The
sort key stays in words (the owner's word on the UX-214 conflict). Only the direction became
`sortAsc`/`sortDesc`, its words moved to the tooltip and the accessible name.

### The check

**`kit-adoption`'s `R2-icon-only-button` rule** (`scripts/kit-adoption.mjs`) refuses three
shapes outside `app/src/kit/`, the Fulfiller's files, and Gallery:
- (a) `iconOnly` on `Button`, read by presence, never by its value.
- (b) A native `<button>` or inline `<svg>` whose only child is an icon.
- (c) A `Button` whose literal label starts with a vocabulary verb, when its `variant`
  cannot be shown to always be `primary` or `danger-solid`.

Clause (c) reads `variant` statically. A dynamic variant, like Inventory's `primary ? …`,
must split into two JSX branches. Only then can the check prove it worded — a screen lane's
own work, not this entry's.

This rule is born on `ux/kit-icons`. It lists its own first offenders under the kit-adoption
ratchet's one exception: 26 files, in `scripts/kit-adoption-allow.json` under lane `icons`.
From here the list only shrinks. `make kit-adoption-selftest` proves the rule in both
directions, including the Fulfiller and Gallery exemptions and the svg case.

### What is not this lane's job

Converting a screen's existing control to `IconButton` is each screen lane's own work, on
`ux/kit-icons` merged in, per the wave-2 brief (`BUILD-BRIEF.md`, "Wave 2: ICONS"). This
entry, and `docs/specs/iconography.md`, name the words-or-icon call for every press the map
found. They do not choose it a second time per screen. That call is settled here.
