## D-product-view-hybrid — One product view, two frames, and the trap it had is fixed first

**This amends D227 and D62.** The owner's ruling, 2026-09-23 interview: HYBRID. One product
view. It opens as a sheet from every product name. `#/product?sku=` stays as the page and the
deep link. A deliberation (`review/product-deliberation.md`, checkout `agent-a8629e07d130bc86a`
at `89544e01`) laid out three options. A: link every name to the route. B: fold every view into
one sheet, and retire the route. H: one component, two frames. It recommended H. The owner
picked it.

**What D227 protected, and what protects it now.** D227's sentence: "The capability exists and
is reachable through its own control." Measured by the deliberation: zero inbound links on 14
routes. The palette also drops an off-nav route. `ProductLink` (`kit/data.tsx`, wave 0) is the
control now. It opens the sheet where one is registered, and the page where none is. So the
capability is reachable from every screen that draws a product name. No route change is
needed. D227's own argument for the address is kept: a pasteable link, a bookmark, an order
line. The route stays, unchanged in what it answers.

**What D62 protected, and what protects it now.** D62 drew the price-history panel beside the
hold on `#/pricing`, not on `#/inventory`'s card panel. A read cost 1.3s, at a public mirror. A
panel that fired on the pointer or the arrow keys would spend both, on every move. That
premise moved for a swept SKU: `getProductHistory` reads the archive first (D219), and the
read is local. What D62 still protects holds unchanged here: no request per arrow key, and a
press or a hold rather than follow-focus. `ProductHistoryView` fetches once per `sku`. It
fetches on mount, or on a printing switch, never on a hover or a keystroke.

**One component, drawn by two frames.** `ProductHistoryView({ sku, onSwitchSku })` in
`app/src/ProductHistory.tsx` is the body. It draws the market chart per range, the legend,
which printing this is, and the owner's own fills, split at `history_begins`. Two callers draw
it. Neither duplicates its fetch or its layout:

- `ProductHistory()` — the routed PAGE at `#/product?sku=`, adopting the kit's `Page`. Its own
  control is a name field (`SearchField` + `useSearch`, the forgiving matcher,
  D-one-forgiving-search-matcher). The deep link is the door for someone who did not arrive
  from a product name already on screen.
- `ProductSheet` — registered with `registerSheet('product', ProductSheet)` (`kit/sheets.ts`).
  So `openSheet('product', { sku })` — what every `ProductLink` press calls — opens this view
  over whatever screen the owner is already on. Its footer carries "Open as page". That sets
  the hash to `sheetHref('product', { sku })`, and closes the sheet. It lands on the same
  route the deep link would.

**This lane builds step 1, and half of step 2.** The deliberation's step 1 was the trap fix,
the extraction, and the doors from a product name. Step 2 was the sheet frame, and folding
`PriceHistory.tsx`'s drawer body into this view. `ProductSheet` above IS the sheet frame. So
step 2's frame half lands here too. **The drawer itself is NOT folded.** `PriceHistory.tsx`
keeps drawing its own compact panel on `#/pricing`, unchanged in shape, per the lane brief ("do
not fold the drawer"). Folding the drawer into this view waits for the Pricing re-interview
(`b-pricing`, released after this lane). The drawer's own word budget, and its `T`-peek
gesture, are that screen's own questions. This lane does not guess them. This lane's only edit
to `PriceHistory.tsx` is its kit-adoption entry. The hand-rolled `$` strings became the kit's
`Money`. The hand-rolled loading skeleton became the kit's `Loading`. A formatting fix, never a
layout or content change.

**The trap, fixed first.** On `#/product?sku=X`, the first nav press out used to put the owner
back on an empty `#/product`. `ProductHistory`'s own `hashchange` listener read `sku` off
whatever hash the address bar held next. That included a hash this screen no longer owned. It
then set `sku` to `''`. The `writeSkuToHash` effect then rewrote that new hash back to
`#/product`. Both functions now check `ownsHash(window.location.hash)` first. A hash that does
not start with `#/product` is never read, and never written over. Evidence of the original
defect: `review/shots/product/trap-1440-light-after-nav.png`, `review/scripts/prod-trap.mjs`.

**Printings are separately identifiable (owner ruling, 2026-09-23).** A product name can cover
more than one SKU — a foil and a normal printing of one card (D212). `ProductHistoryView` reads
every other SKU sharing the loaded product's exact name. It asks the same forgiving search the
name field already uses (`GET /search`). It never asks a second endpoint. It draws them as a
row of chips beside the header, pressed on the one currently drawn. One press switches to
another. It never pools two SKUs into one chart. Switching printings replaces which SKU is
read. It works the same way choosing a different search result does.

**Not mechanized.** Whether `ProductLink`'s door reads as reachable is a claim about a person.
CLAUDE.md already marks that claim unmechanizable for D227. Its own words: "a machine cannot
know which screen a human would look for a capability on." `make design-check` is the nearest
check that can see it. It stays off the commit path, by that entry's own argument.
