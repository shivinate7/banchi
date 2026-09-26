## D288 — A common, repeated action is an icon with a required label, and a press that spends money or cannot be undone keeps its words

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
call site that omits it. `label` is the tooltip text. It is also the accessible name, unless
a longer `name` overrides it for a dense row ("Undo the sale at Section 2, Card 5"). `name`
must contain `label` (WCAG 2.5.3, Label in Name, added in round 2). A dev-mode
`console.error` names the call site that breaks this.

**The visual box is the face**, 28px at rest, sized per `size` in the component itself. The
40px thumb floor (D117) is a `::before` pseudo-element instead, `max(40px, 100%)`, centred
over the real box. This is round 2's own fix. The first cut made the outer box the 40px
floor. That broke FLT-24, one control height in a field row. It grew `SearchField` on the
first keystroke (D118, measured 40px to 42px). It also read wrong against `.bn-sort-dir`'s
own field-edge floor. The pseudo-element expands the clickable region without existing in
layout, the way `base.css` never lets `:hover`/`:active` move anything. `IconButton` reuses
`.bn-btn` rather than a second stylesheet. So it inherits the D50 cursor, response and press
floors for free. `button` is a bare-tag selector in `base.css`.

**Neither the pseudo nor `.bn-fchip-clear` may centre itself with `transform`.** Verification
found a real Chromium hit-test gap. A `translate(-50%, -50%)` centring promotes the element
onto its own compositor layer. A real click landing past the element's own box, inside that
layer, does not always reach it. `document.elementFromPoint` at the same point reads it fine.
Measured on `.bn-fchip-clear` (round 2's first draft, `top: 50%; transform: translateY(-50%)`)
and separately on `.bn-icon-btn::before`'s own reach past a narrow face. Both are now centred
by inset alone. The pseudo uses `min(0px, calc((100% - 40px) / 2))` on all four sides.
`.bn-fchip-clear` uses `top: 0; bottom: 0; margin: auto 0`. Same box, no transform, no layer
to mis-hit.

**The tooltip stays a DOM child of the button**, never a portal. `app/tests/icon-button.spec.ts`
finds it with `button.querySelector('.bn-icon-tip')`. Its position changed in round 2. It is
now `position: fixed`, computed by a `reposition()` call on pointer-enter, focus, and the
long-press timer. `reposition()` measures against the true viewport. It clamps inside it, and
flips below the button when there is no room above. This is why `.bn-sheet`'s own
`overflow: hidden` no longer clips the overlay Close tooltip. Round 2 measured the tip's own
top landing at -14px before this fix. Visibility is still CSS. `:hover` is now under
`@media (hover: hover)`, so a touchscreen tap does not leave a phantom hover once the finger
lifts, round 2's own finding. `:focus-visible` (never a plain mouse `:focus`) and
`[data-tip-open]` (for a long-press) are unchanged. The long-press that opens the tooltip
also calls `preventDefault()` on its own `touchend` now. So it never also presses the button
under it. Round 2 measured a click firing once the touch that revealed "Delete" lifted.

`tone="danger"`, `pressed` (a toggle of one act, off the same pair `Chip` reads), `busy`, and
`badge` round out the props. `badge` draws a small count at the corner. It is
`position: absolute`, so its arrival never moves the layout. Its own accessible name is the
caller's `name`, since the badge itself is `aria-hidden`. `kbd` also sets
`aria-keyshortcuts` on the button now. In round 1, the key lived only in the `aria-hidden`
tooltip. `docs/specs/iconography.md`'s "What IconButton carries" names each prop.

**The Fulfiller gets words for the overlay Close.** This is round 2, the orchestrator's
ruling, option a, per spec rule 1. `PageRoute` (`app/src/kit/Page.tsx`) now carries
`persona`. A Sheet or Modal is portalled. So `OverlayFrame` reads persona from context, not
from where it sits in the DOM. A portal does not break React context. The Fulfiller's Close
is a plain worded `Button`, at a literal 20px (`.bn-overlay-close-worded`, kit.css). That
floor is DESIGN.md's, not `--ff-fs-base` — that token is `Fulfillment.css`'s own, and this
button is the shared kit's, drawn under any Fulfiller overlay.

Verification found the context read was reaching nobody. The Fulfiller's own route renders
outside the shell (D5), through a SEPARATE branch in `App.tsx` that never wrapped its view in
`PageRouteContext.Provider`. So `usePageRoute()` read `null` there, and every overlay opened
from that screen — the "?" keyboard sheet among them — drew the icon-only Close no matter the
persona. Fixed by giving that branch the same provider the chromed one already carries.

Eight icons were added to `app/src/kit/Icon.tsx`, in the same 24-unit, 1.75-stroke idiom as
the rest: `sold`, `pencil`, `eraser`, `eyeOff`, `sortAsc`, `sortDesc`, `moveTo`, `grip`. Three
were redrawn in round 2, after a magnified review. `sold` read as a loose squiggle, not a
dollar seal. `grip`'s dots were zero-length, under 1.2px at 16px, and invisible. `sortAsc`
and `sortDesc` drew all three bars nearly the same width, which read as no order at all. They
now taper narrow-to-wide (ascending) and wide-to-narrow (descending) under the arrow, the
common convention. `moveTo` read as the standard "sign in" glyph, a three-sided bracket. It
is now an arrow toward a single destination line. `ICON_MEANINGS` gained a row for these, and
for every other icon the vocabulary draws on. `kit-adoption` fails a commit that drops one of
these rows. It also fails one that names a vocabulary icon `PATHS` does not draw
(`iconMeaningsGap`, self-tested both ways).

Every state is rendered on `#/gallery`, under "Icon button", between "Buttons" and "Keycaps".
The gallery's own toast specimen was hand-rolled with a raw `<button>`. Round 2 found this is
why `axe` never caught the toast contrast regression below. It now renders the real
`IconButton`, the same markup `kit/toast.tsx` does.

**Seven kit-owned controls converted**, per `docs/specs/iconography.md`'s own list. They are
the overlay Close, the Toaster dismiss, the FacetChip clear, the SearchField clear,
`ReloadButton`, the compact `FilterBar` trigger, and `SortControl`'s direction toggle. The
sort key stays in words, the owner's word on the UX-214 conflict. Only the direction became
`sortAsc`/`sortDesc`. Its words moved to the tooltip and the accessible name. Each control
carried its own pre-conversion CSS: a bordered field look, a second count pill, a second
hover paint. All of it was dead weight fighting `IconButton`'s own box. Round 2 deleted it
rather than patching around it. Two defects were only visible once it was gone. The Toaster
dismiss glyph was 1.83:1 in light theme, because `.bn-icon-face`'s own fixed colour, the old
two-box shape, beat `.bn-toast-close`'s `color: inherit`. `.bn-filterbar-trigger`'s
active-count badge no longer reached a screen reader at all. The badge is `aria-hidden`, and
the button's own text used to carry it. `FilterBar` now passes a `name` prop stating the
label and the count when one is active.

### The check

**`kit-adoption`'s `R2-icon-only-button` rule** (`scripts/kit-adoption.mjs`) refuses three
shapes outside `app/src/kit/`, the Fulfiller's files, and Gallery:
- (a) `iconOnly` on `Button`, read by presence, never by its value. This now includes a
  spread, `{...{ iconOnly: true }}` (round 2).
- (b) A `<button>`, or an `<a role="button">`, whose whole visible content resolves to
  nothing but an icon: an `<Icon>`, an `<svg>`, or a bare `×`, `✕` or `✖`. This reaches
  through a wrapper element, a `{<Icon/>}` expression, or a ternary of two icons, a chevron
  toggle. It also fires on one with no visible content at all, carrying only an
  `aria-label`. Round 2 rebuilt this clause. The first cut dropped every `{expression}`
  sibling before counting children. So `<Icon/>{label}`, a real word beside the glyph, read
  as icon-only. A real word anywhere in the content now clears it, even one this reader
  cannot itself read, a bare `{expression}`.
- (c) A `Button` whose literal label starts with a vocabulary verb, when its `variant`
  cannot be shown to always be `primary` or `danger-solid`. The verb list gained Hold,
  Release, Reveal, Hide and Clear in round 2. Matching is now case-insensitive. The label
  reader now reads through `{'Undo'}` and `Undo {n}`, not only plain text. Round 2 also
  rebuilt the variant reader. The general `literalsOf` silently drops an unresolvable branch
  of a `??`, `||`, `&&` or ternary. It reports only the literal side it found. So
  `variant={x ?? 'primary'}` and `variant={c && 'primary'}` both read as safely `'primary'`.
  The clause's own reader treats one unresolved branch, on either side of any of the three
  operators, as making the whole expression unresolved. Unknown means not provably worded.

Clause (c) still reads `variant` statically. A dynamic variant, like Inventory's
`primary ? …`, must split into two JSX branches. Only then can the check prove it worded — a
screen lane's own work, not this entry's.

This rule is born on `ux/kit-icons`. It lists its own first offenders under the kit-adoption
ratchet's one exception: 27 files, in `scripts/kit-adoption-allow.json` under lane `icons`.
**The list is keyed file to rule, not file to occurrence** (round 2's own finding). One entry
excuses every violation of that rule in that file. So a new icon-only control, added to an
already-listed file, passes silently. It stays silent until the file's other violations are
fixed and the entry is removed. This is how the list was built before this lane, under
D275. It is not a gap this entry opened. From here the list
only shrinks. `make kit-adoption-selftest` proves the rule in both directions. That covers
the Fulfiller and Gallery exemptions, the svg and role="button" cases, and the review's own
evasion fixtures (`SD/review/kit-icons/evade.mjs`), kept as permanent cases.

**`app/tests/icon-button.spec.ts`** is the browser half, added in round 2. It checks six
things:
- the 40px hit area reaches past the visual face
- the tooltip shows on hover and focus, and hides after a click
- showing it moves nothing else (D118)
- the overlay Close tooltip is not clipped by a sheet, at 1440 or at 390
- a long-press does not also press the button
- the toast dismiss glyph clears 4.5:1 in both themes

`make design-check` runs it.

**Round 3 (`ux/kit-tighten`) added the anchor form.** `IconButton` now takes `href`, plus
`target` and `rel`. It then renders an `<a>`, not a `<button>`. Same face, same `::before`
40px hit area, same tooltip, same accessible name. No `transform`. The round-2 centering rule
carries over untouched. It is keyed to a class, not to a tag. The cause: Orders' "Cards to
pull" needed `window.open` in an `onClick`. No icon-only link existed in the kit. That loses
middle-click. It also loses the browser's own "Open link in new tab" and "Copy link".
`app/tests/icon-button.spec.ts` gained three cases for it. The `<a>` carries the given `href`,
`target` and `rel`. Keyboard Enter follows it. Its face, hit area and tooltip match the button
form. `scripts/kit-adoption.mjs`'s `R2-icon-only-button` needed no code change. It scans
hand-rolled `<button>`/`<a role="button">` shapes, never the `<IconButton>` tag itself. It
gained a self-test naming the anchor form explicitly, so a later edit cannot start flagging it
by accident. `docs/specs/iconography.md` section 6 carries the full argument. Orders.tsx is
untouched. Its own "Cards to pull" is already a real, worded `<a href>`. It sits outside this
rule's reach either way.

### What is not this lane's job

Converting a screen's existing control to `IconButton` is each screen lane's own work, on
`ux/kit-icons` merged in, per the wave-2 brief (`BUILD-BRIEF.md`, "Wave 2: ICONS"). This
entry, and `docs/specs/iconography.md`, name the words-or-icon call for every press the map
found. They do not choose it a second time per screen. That call is settled here.
