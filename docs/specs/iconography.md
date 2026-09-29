# Iconography

**Status: BUILT.** D288 (repeated actions are labeled icons) records the ruling. This file is
the detail: the rule, the icon set, the collisions that were fixed, and the risks. `IconButton`
and the icon vocabulary are in `app/src/kit/`, and `make kit-adoption` enforces the rule.
Section numbers are stable ids, because code cites them.

Key: **WORDS** means that the press keeps its words. **ICON** means that it becomes an
`IconButton` with a required label. A glyph arrow (for example `x → trash`) means that the press
keeps its words and only its glyph changes.

## 2. The rule

Apply these steps in order. The first match wins.

1. **Fulfiller route** (`persona: 'fulfiller'`: `Fulfillment.tsx`, `PullConfirm.tsx` and
   `CardLocations:FulfillerCard`). WORDS always.
   - DESIGN.md sets these floors: text 20px or more, targets 44px or more (IconButton is 40),
     and gaps 12px or more. It also sets a contrast floor of 7:1, a banned-word list, and an
     undo on every mark-sold.
   - A touch screen shows no tooltip. The Fulfiller is retired and not technical. The words
     must teach.
2. **Money, TCGplayer or no way back.** The press spends money, writes to TCGplayer, or no
   undo can reverse it. WORDS. Examples: Send, Identify, Spend, Stand down, Reserve, Release a
   claim, Rebind, Take back, Delete permanently. `danger-solid` is always WORDS.
3. **A fact on the face.** The face carries a count, a price, a name, a box, or a current
   value or state (a filter value, a sort key). WORDS.
4. **The only primary in its sector.** Examples: a page primary, an empty-state door, a
   notice's recovery ("Try again"), a sheet or wizard footer, a decision pair (Cancel, Not
   now, Back). WORDS.
5. **Other word-only controls.** A menu item, a tab, a segmented option, a chip, a link or
   press inside a sentence, a skip link. WORDS.
6. **The verb is in the vocabulary**, and no step above matches. ICON through `IconButton`.
   - Mark sold → sold
   - Undo → undo
   - Retire → archive
   - Edit or Rename → pencil
   - Delete, Forget or Remove → trash
   - Clear typed values (undoable) → eraser
   - Copy → copy
   - Download a file to disk → download
   - Open elsewhere → external
   - Close, Dismiss, or clear one value → x
   - Filter → filter, with a badge
   - Sort direction → sortAsc or sortDesc
   - Reload → refresh
   - Manage or Options → settings
   - More → more
   - Move to a box → moveTo
   - Hold or Release → lock or unlock
   - Reveal or Hide → eye or eyeOff
   - Collapse, expand, previous or next → chevrons
   - Search → search
   - Drag → grip
7. **Anything else.** WORDS. To make a new icon press, add a path and an `ICON_MEANINGS` row
   first. A new meaning gets a new path.

Edge cases:
- **The only primary in its sector.** The same verb is ICON in a row and WORDS when it is the
  only primary. Inventory's row "Mark sold" is ICON. The phone bar "Mark sold" is WORDS. A
  list of per-row primaries is not "the only primary". Each row's press is ICON and does not
  use the primary tone.
- **Meaning changes by state.** Use one footprint (D118).
  - A toggle of one act (Hold/Release, Reveal/Hide, Collapse/Expand) uses `pressed`. Change
    the label and the icon together, never the icon alone.
  - When the act itself changes (Mark sold, then Undo — Value my stock, then Refresh), decide
    each state by the rule. Reserve the wider slot.
  - Copy: the name stays "Copy …". The glyph can show check for 2s. A polite status says
    "Copied".
- **Dense row versus alone.**
  - A press repeated per item (row, table, walk, list) is ICON. The same verb alone (empty
    state, notice, toast, sheet footer) is WORDS.
  - A row holds 3 IconButtons at most. Put the 4th and later presses in a `more` menu with
    words.
  - In a row, the accessible name carries the object ("Undo the sale at Section 2, Card 5").
    The tooltip stays short.
  - A receipt's Undo is ICON, because the receipt sentence teaches. A toast action is WORDS,
    because the kit label is generic and the toast is short-lived.
- **Phone widths (below 640).** No hover, so no tooltip on its own.
  - The kit shows the tooltip on hover, on keyboard focus, and on a long press.
  - A Banchi-specific glyph (sold, archive, moveTo, eraser, lock) goes only where a sentence,
    pill or heading near it names the act. If nothing names it, the press goes into the `more`
    menu with words.
  - The hit area is 40px at every width (UX-267).
- **Destructive but undoable.** It never uses `trash` and never uses danger tone. Clear typed
  uses eraser. Retire uses archive, opens its reason panel, and follows UX-252.
- **Destructive, with no undo.** The trash ICON only opens a ConfirmSheet. The confirm
  press is WORDS. A cheap loss with a way to redo it (Forget an in-memory file) can be a trash
  ICON with danger tone that acts at once.
- **Keycap.** It goes in the tooltip, after the label ("Undo U"), never on the face
  (UX-145, UX-040).

### The kit check

`R2-icon-only-button` in `scripts/kit-adoption.mjs`. Outside `app/src/kit/**`, the Fulfiller
files and Gallery, it refuses three things:
- (a) `iconOnly` on `Button`.
- (b) A raw `<button>` or inline `<svg>` whose only child is an icon.
- (c) A `Button` whose literal label starts with a vocabulary verb, when its variant is not
  `primary` or `danger-solid`. The vocabulary: Mark sold, Undo, Retire, Edit, Rename, Delete,
  Forget, Copy, Download, Open as page, Close, Dismiss, Reload, Manage, Options.

The check reads `variant` statically. A dynamic variant, like Inventory's `primary ? …`, must
split into two JSX branches before the check can prove it worded. The violations that exist
are on the shrinking offender list, under lane `icons`.

**Clause (c)'s declared exception.** A vocabulary-verb
label with no provably worded variant has a second door. A literal `words="<reason>"` on the
`Button` itself excuses it. Its values are `kit/index.tsx`'s `WordsReason` type, mirrored in
`scripts/kit-adoption.mjs`'s `WORDS_REASONS`:

| `words` value | This section's rule |
|---|---|
| `irreversible` | rule 2: money, TCGplayer, or no way back |
| `fact-on-face` | rule 3: the face carries a count, a price, a name, a box, or a current value |
| `only-primary` | rule 4: the only primary in its sector |
| `word-only-control` | rule 5: a menu item, a tab, a chip, a link, or a press inside a sentence |
| `not-in-vocabulary` | rule 7: the leading word matches a vocabulary verb by text, not by its meaning here |

This is a STATED reason at the press, never an allow-list entry. A reviewer reads why beside
the code. It survives the press moving files, where an allow-list entry, keyed to a path, does
not. `words` is read only by the check. It never reaches the DOM and changes nothing on
screen. An unrecognized value excuses nothing.

Two presses use it today. Capture's "Clear the setup" is `not-in-vocabulary`, because "Clear" matches
the vocabulary's word and not its "clear typed values, undoable" meaning. It resets the whole rig.
SubmissionClaims' "Release N cards" is `irreversible`, because a paid identification claim cannot be
undone. The door replaces gaming the variant proof, which is what moving a press to `danger-solid`
just to pass the check would be.

### What IconButton carries, beyond the brief's first cut

- `kbd`, drawn in the tooltip.
- `pressed`, for a toggle of one act.
- `busy`, a spinner in the same footprint.
- `badge`, a count.
- An optional longer accessible `name`, apart from the tooltip `label` (UX-271).
- An anchor form: `href` (plus `target`/`rel`) renders an `<a>` instead of a `<button>`, same
  face, hit area, tooltip and accessible name (section 6).
- A visual face of 28px in dense rows, at a hit area of 40px or more, every width.
- The tooltip on hover, on keyboard focus, and on a touch long-press.
- Seven kit controls moved onto it: overlay Close, the Toaster dismiss, the FacetChip clear,
  and the SearchField clear. Also ReloadButton, the compact FilterBar trigger, and the
  SortControl direction. The sort KEY stays in words. Only the direction became
  sortAsc/sortDesc, per the owner's word on the UX-214 conflict below.

## 3. Icons to add, and collisions

**Eight paths were added, each with an `ICON_MEANINGS` row:**
- `sold`: a round seal with $, for Mark sold and the Sold pill. It is not `tag` (Pricing) and
  not bare `dollar` (Sales).
- `pencil`: Edit or Rename.
- `eraser`: clear typed values, undoable.
- `eyeOff`: Hide.
- `sortAsc` and `sortDesc`.
- `moveTo`: an arrow into a bracket. It draws no box: `box`, `package` and `archive` are
  already box shapes.
- `grip`: six dots.

`ICON_MEANINGS` also gained a row for every OLD icon the rule now draws on: `x`, `check`,
`eye`, `lock`, `external`, `download`, `settings` and `hand`. It also covers every other
icon step 6 above names. `make kit-adoption`'s own check fails a commit that drops one of
these rows, or that names a vocabulary icon `PATHS` does not draw.

**Collisions to fix, by owner lane. This is the record of what changed and why, for the lane
that owns the screen:**
- `x` as a write:
  - Capture "Remove just this card" → trash.
  - Review "Close" (it stands a question down) → words, no glyph.
- `undo` where the press is not an undo:
  - Review "Back to rows" → arrowLeft.
  - Pricing "Follow the store again" → no glyph.
  - Orders `It isn't shipping` → no glyph.
  - Markdown "Discard staged" → no glyph.
- `trash` on an undoable clear: Pricing "Clear typed" and ClearPrices → eraser.
- `check` and `hand` as Mark sold: Inventory and Orders PickLine → sold. `check` on the
  irreversible "Stand down" (Orders, x2) → drop it.
- `lock` as Hide: Codes, 3 places → eyeOff. `lock` now means only seal or hold.
- `tag` and `wand` as manual edits: BoxOps Rename, Name sections and Set claims, and CardOps
  Correct claims → pencil. `wand` stays for "let Banchi check again".
- `package` as Move to box (BoxOps) → moveTo.
- `download` as a TCGplayer fetch: RunPanel, Markdown and LiveReconcile → refresh. `download`
  names a file saved to disk.
- `upload` as "Check what is live" (Runs.tsx) → refresh.
- `history` as price history: the Pricing row and the drawer tab → chart. This follows UX-118.
- `external` as the departed badge (BoxBrowse) and `eye` as "Viewing" — the inventory lane
  fixes these (UX-222, UX-221).
- `pin` as Keep open (PriceHistory) → words. `pin` names a pick location.
- `refresh` as a reset: Capture "Clear the setup" → eraser.
- **Retire against Delete.** There is no collision today. `archive` is not `trash`. They stay
  apart.

## 4. Risks

1. **Orders Mark sold as an icon, with a broken Undo.** Undo on Orders refuses today (UX-195,
   HOR-07). The fix is in the later undo session. **The owner accepted this risk**: Orders'
   PickLine and RowAction convert to `sold` now, ahead of that fix.
2. **D118 slot sizes.** Inventory reserves 137x28 for the Mark sold and Retire pair. Two
   40x40 targets make each row 12px taller. That fights UX-206 and UX-169, which want a
   taller walk. `IconButton`'s own answer: draw the face at 28px, extend the hit area to
   40px. Where two hit areas overlap in a dense row, that is the inventory lane's own call.
3. **No tooltips on touch.** On a phone, sold, archive, moveTo and eraser have no visible name
   at rest. Apply the phone edge case in section 2: `IconButton`'s long-press.
4. **Findings this conflicts with:**
   - **UX-214 (FLT-19), answered by the owner.** The sort KEY stays in words, never hidden in
     an icon. The direction becomes the glyph, its words moved to the tooltip and the
     accessible name.
   - **UX-108 (shipping).** It asks for "a verb and its object" and names "Forget". As an
     icon, "Forget this file" moves to the tooltip only.
   - **UX-145.** The keycap stays after the label, but the label is now the tooltip. R and U
     leave the face. The keys sheet still lists them.
   - **UX-099.** Danger tone and ask-first must follow kit-frame's one rule for destructive
     presses. An icon adds no second pattern.
   - These findings agree with the plan: UX-056, UX-267, UX-118, UX-221, UX-222 and UX-232
     (it stays words).
   - This map does not claim UX-195, UX-249, UX-252 or UX-204. The icon does not fix those.
     They belong to the undo session.
5. **Screen readers.** A walk with 30 buttons all named "Mark sold" repeats names (UX-271).
   Every row `IconButton` needs the object in its `name`.
6. **Tests.** A spec that finds a button by its visible text (`hasText`, `text=`, the
   demo-coverage spec) will break on a converted control. Find it by its role and name.
7. **Discoverability of Manage.** Manage becomes an icon. The Orders fetch lives inside that
   sheet today (UX-193). The orders lane must move the fetch out first (HOR-05).
8. **Box-shaped glyphs.** `box`, `package` and `archive` already look alike. A box-shaped
   `moveTo` would be a fourth, and they blur at 14px. `moveTo` draws no box.

Rationale for the ruling itself, the words-vs-icon split, and the check's own build: see
D288.

## 6. The anchor form

The kit had no icon-only link. A screen that needed one reached for `window.open` in an `onClick`,
which is a link wearing a button's clothes. It loses middle-click, and the browser's own
right-click "Open link in new tab" and "Copy link".

The fix is a second form of the same primitive and not a second component. `IconButton` takes
`href`, plus `target` and `rel`. When `href` is set, it renders an `<a>` and not a `<button>`.
Both forms share these:
the classes, the inline face size (`FACE_PX[size]`), the `::before` 40px hit area, the tooltip
and the accessible name (`aria-label={name ?? label}`). `.bn-icon-btn` is a class selector, so one
stylesheet rule covers both elements. No `transform` sits in the hit area or in the tooltip's
positioning. The centering rule is keyed to a class and never to `button` or `a`. A native `<a href>` is already
keyboard-operable, so no keydown handler exists. `type`, `disabled` and the other button-only
attributes are spread only onto the `<button>` branch. The anchor form drops them silently, so
none lands as an invalid DOM attribute.

`app/tests/icon-button.spec.ts` proves the anchor form against `#/gallery`. `R2-icon-only-button`
accepts it without a code change, because the rule never scans the `<IconButton>` tag itself. A
self-test names the anchor form, so a later edit cannot flag it by accident.
