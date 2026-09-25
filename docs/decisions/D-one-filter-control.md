## D-one-filter-control — One filter bar, everywhere a list is filtered

**The owner's rulings, 2026-09-23.** The owner's own gripe, on Inventory:

```
I hate how on the inventory screen I have to filter by game first, then set, then rarity and
only IN THAT ORDER.
```

A second gripe, on Orders:

```
the filters aren't even the same widths and in fact clicking status on the orders opens the mac
default os filtering. the filtering themselves also are occasionally word heavy.
```

And, naming the base to build from:

```
our captures screen has a pretty decent ui already made for filtering/selecting options.
```

So: one filter bar, `kit/filters.tsx:FilterBar`. It is built on Capture's own picker pattern.
It uses kit-data's own `Select`, `FilterChips` and `SortControl`. It opens the kit's own panel.
It never opens the OS menu. It carries every facet a screen needs, in any order. It has:

- a count per option, under the other active filters, with a zero drawn rather than hidden,
- a single-choice facet and a multi-choice facet marked differently,
- a clear per facet, and ONE clear-all: the count line's. `FilterChips`' own "Clear all" is
  not drawn inside a bar, so two never sit side by side,
- no order lock, and no facet that wipes another's choice,
- one control height across the whole bar,
- ONE WIDTH for every facet trigger in one bar: the widest any of them needs, in one shared
  grid track. A pick never changes it (D118). This is the orchestrator's call on the owner's
  gripe, which named the width difference itself,
- "N of M" drawn by construction. The bar's own `FilterCount` line is not something a screen
  can leave out. It names every narrowing: each pick, the search's words, and the hide toggle
  while it hides a row,
- a popover in a wide bar, and one sheet behind a single "Filters" trigger in a narrow one.
  The bar measures ITS OWN width (a container query), not the window's. So Inventory's
  268-300px rail gets the compact trigger on a desk. The trigger's badge counts only what
  differs from the screen at rest. A Hide sold that is on by default (D132) is not counted,
- a slot beside the search for one control of the screen's own (the rail's collapse press),
  and the search's busy and failure states from `useSearch`.

The counts come from one helper, `kit/facets.ts:countFacets`. Each option counts the rows the
list would show under the OTHER active facets. The screen's own search and hide toggle apply
too. `withCounts` takes the same answer from the server.

One quiet `HideToggle` replaces three shapes with one. It is a field-edged control of the
bar's own height. Its check mark fills with the accent when on, and a count sits beside its
words. It replaces "Hide sold"'s black pill, "Hide never-seen SKUs"' bare checkbox, and
"Holding"'s dimming chip. A pressed `Chip` was tried first, and the review refused it. It
filled black in light and white in dark: the heaviest object in the bar, for a state that is
on by default.

One `SortHeader` marks the active table column in two channels. The label goes to full ink
weight. The one chevron that is ever drawn belongs to it too. The old pattern drew a chevron on
every header, and only `aria-sort` said which one was real. `SortHeader` is the `<th>` itself,
and `aria-sort` sits on it, never on the button inside. Each column has its own first
direction: a name starts A to Z.

The record of the review is `docs/reviews/ux-2026-09-23/`, lens `filtering.md`.

### The premises that no longer hold

**D213's set dropdown, on Inventory.** D213 chose a native `<select>`. Its reason was
"standardization across card games." The filtering lens found a problem. Set and Rarity are
`disabled` until Game is chosen (FLT-09). The code also resets Set and Rarity on every Game
change (`BoxBrowse.tsx:setGameFilter`). That confirms the owner's own "game first" complaint.
D213's aim is kept. Its native-select mechanism is not. `FilterBar`'s facets are the kit's own
picker. They never disable each other.

**D220's Status select and toolbar, on Orders.** D220 was amended on 2026-09-19, to a native
dropdown, "on the owner's word." It put Status, Sort and Hide-unknown in one strip. The owner
has now seen the result. He dislikes it (gripe 3). The block holds four controls, four widths
and two heights (FLT-24). Status opens the operating system's own menu. The kit's picker never
does that.

**D132 and D209's separate toggles.** D132 drew "Hide sold" as a pill with a count. D209 drew
"Hide never-seen SKUs" as a plain checkbox with none. Two entries chose two shapes for one
idea. That is FLT-16's own finding.

**No decision set one filter control for the app.** FLT-15 found one idea drawn four ways:
"pick a category and see how many." A native select, a segmented bar, a chip strip and a set
of toggle cards each carried its own clear action, in its own place.

### What the old choices protected, and what protects it now

D213's dropdown protected one thing: a control that reads the same for every card game.
`FilterBar`'s facets keep that. One shape, driven by data, serves Game, Set, Rarity, or any
other facet a screen hands it. D220's strip protected another thing: fitting Status, Sort and
a toggle onto one line. `FilterBar` keeps that on the desk. On the phone it folds the same
controls behind one trigger, instead of breaking D195 (same-role controls share a width) the
way the four-width strip did.

### What is still open

- **Which facets each screen passes, and in what order.** This entry builds the bar. A screen
  lane wires its own facets to it in wave 2. It is not bound to Inventory's old
  Game/Set/Rarity roster, if a screen's own filters differ.
- **The exact word for "Any."** Each screen may need its own: a set, a status, a lane. That is
  a wave-2 question, not this entry's.

### What the inventory lane built (2026-09-24)

- **Inventory's rail uses the bar.** Game, Set and Rarity each take several picks, in any
  order. No pick clears another. The picks live in the URL.
- **The counts come from one read.** `GET /boxes` sends `facet_cells`: the store's cards,
  grouped by box, game, set, rarity and whether they left. The screen folds them with
  `kit/facets.ts:countFacets`. So a pick asks the server nothing. Each count follows the
  other picks and Hide sold. The unclassified value is the blank pick, `?set=`.
- **A popover on a desk.** `FilterBar` takes `compact="popover"`. A narrow bar on a desk then
  opens its facets under the Filters press, not in a sheet at the far right of the window. The
  phone keeps the sheet. In the popover bar the Filters press shares the search's line.
