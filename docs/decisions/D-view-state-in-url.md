## D-view-state-in-url — A screen's filter, sort, search and hide state lives in the URL

**The owner's ruling, 2026-09-23 (FLT-11).** Filter memory lives in the URL, on every screen.
A link carries it. A bookmark carries it. Back restores it.

One mechanism answers this, in `kit/viewState.ts`. Every value a screen keeps as view state
lives in the query string of the screen's own hash. `#/inventory?game=pokemon&game=riftbound`
is the shape. A reload re-reads it. A copied link carries it whole. A route change — a link
`App.tsx:go` makes — leaves a place for the Back button to return to.

Repeated keys carry a multi-value facet, never a joined string.
`?game=pokemon&game=riftbound` is the shape. `?game=pokemon,riftbound` is not. A person can
read a URL like this. A person can edit it by hand. It never collides with a value that holds
the joining character itself.

A write from this module replaces the current history entry. It never pushes a new one. A
filter picked, a column sorted, or a letter typed into search, is not a new place to visit. It
is the screen the owner already has open, filled in further. Pushing a history entry per
keystroke would make the Back button retype the owner's own search, one character at a time.

The record of the review is `docs/reviews/ux-2026-09-23/`, lens `filtering.md`.

### The premise that no longer holds

FLT-11 found five different answers, on seven screens. Sales kept everything in the URL.
Orders kept Status, sort and Hide-never-seen in `localStorage`, and forgot its own first
select and its own search. Inventory kept only Hide sold. Pricing's run scope reset to the
newest run on every reload. Review, Graveyard and Shipping kept nothing at all.

No single decision set this. D217 (Sales becomes a tool) made the URL that screen's own copy
of its state. D209 put Orders' view in `localStorage`, on D142's own precedent — the setup
outlives the browser. Two rulings gave two mechanisms, on two screens. Five screens carried
neither.

### What D209's `localStorage` choice protected, and what protects it now

D142 protects a capture setup across sessions, on one device: the box, the game, the set hint.
That subject is a fact about the machine, not about one screen's current view. It is untouched
here.

D209 borrowed that same reasoning for Orders' own filter state. Filter state is a fact about
what the owner is LOOKING AT, not about the device. A `localStorage` copy of it cannot be
linked, and cannot be shared. It also fails a plainer test. A screen loads with the LAST
SAVED filter, not the one in the URL the owner just opened. Moving that one screen's memory to
the URL is this entry's own scope. D209's sort-toggle behavior, and its D132 fold timing, are
both untouched.

### What is built

- `useViewQuery()`. The current route's query string, read live. It changes on every write
  this module makes, and on `hashchange` (Back, Forward, a typed URL).
- `patchViewQuery(patch)`. One merge into the current query string. A `null` value removes a
  key. An array value writes one repeated key per entry.
- `useViewParam`, `useViewFlag`, `useFacetParams`, `useSortParam`. Typed hooks over the above,
  for a plain string, a boolean flag, a `FilterBar`'s `FilterValue`, and a `SortControl`'s
  `SortValue`. A value at its own default writes no key, so a screen at rest keeps a clean URL.

### What is still open

- **Which screen adopts which hook, and under which query keys.** This entry builds the
  mechanism. A screen lane wires its own filters, sort and search to it in wave 2.
- **The `CLAUDE.md` storage-key roster.** The owner's ruling moves filter memory off
  `localStorage`, screen by screen, as each screen lane adopts this file. The roster itself
  changes in `docs-sweep`, per the addendum.
