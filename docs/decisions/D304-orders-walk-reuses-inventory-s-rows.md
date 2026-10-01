## D304 — Orders walk reuses Inventory's rows

The owner's answers, 2026-09-27, to the drift findings against D220 (Orders is
inventory's screen with orders in the rail, and the walk is a mode of it) and D274 (Orders
and Shipping are two sidebar rows with no tabs, and the walk gets the full height). This entry records only what was decided.

**Q1, the desk layout.** Layout R: three columns at 1000px of column and up. Inventory's
rail frame holds the buyers, sticky, fit to the window. The walk column holds the order
panel, the strip and the walk list, on the page's own scroll. The card pane is sticky. This
replaces D274's single-rail shape (HOR-03, HOR-14). The walk was 96px tall in a 300px
column. It is now the tallest thing on the screen, the shape D274 wanted but could not fit.

**Q2, the buyer list's own scroll.** The buyer list scrolls inside its own sticky rail, the
way `#/inventory`'s box list does. **This amends D274's HOR-33 finding**, which ruled one
page scroll for the buyer list, the walk and the page together. Layout R gives the rail its
own column. So it can scroll on its own again.

**Q2b, the buyer rows.** The list is one kit card, `#/inventory`'s own `bn-panel`. A buyer
row carries the name and the owed count and no status chip, because the Show facet is where a
state is picked and a chip on every row is noise. The list is one flat list with no Ready or Not
ready groups, and the Walk press sits on its own row above it (the owner's rulings). The Show facet says each word one way: Flagged is a product the store has never seen or a sealed product (the store does not hold sealed), Short is a known product with no copy left, and Partly picked is a buyer with some
copies already pulled; Home's Cannot be filled press opens all three.

**Q3, the row detail.** Full detail on every pick row: box, section and card, the section
strip, the ruler, and the neighbor names, on every copy row. Each row reuses
`CardLocations` rather than a walk-only row. This restores D220's original
point 3. The built screen had shipped a `WalkList` that drew only the slot number and the
name.

**Q4, the phone.** The walk, with the card in a sheet. A tap on a walk row opens the card.
The buyer shows before the photograph. This keeps D274's built walk mode (`?walk=1`). It
does not revert to the card-then-walk order the first mockup drew. The walk is what a hand
steps through at the shelf.

**Q5, the walk order.** Density first, box name breaks a tie. The owner asked whether the
walk already sorted by density. They were right to ask. D220's own owner quote says it should.
`pipeline/walkplan.py`'s built `plan` sorts by `walk_order`, the hidden box NUMBER, never by
density or name. The fix keeps `walk_order` for the solver's own determinism (`_dominated`,
`_greedy`, `solve`). It changes only `plan`'s drawn-order key, to `(pooled flag, density,
name key of inventory.box_title(box), section)`. Density comes first, as the spec defines it.
The box name, in natural order, breaks a tie only (D259, a box is shown only by its name). The final re-sort by the hidden box number is deleted.

**Q6, the pane's card facts.** The hero head only, D274's own shape. No Details fold sits on
this screen. Below the head goes every on-hand copy of the card, in Inventory's own copies
list, with the walk's chosen copy first (D212, every copy is fungible). The owner's own
words:

```
we don't need details on this screen
```

This keeps D274's amendment. The card's details table stays on `#/inventory` alone.

**Q7, the mockups.** The PNGs stay outside the repository. `scripts/githooks/pre-commit`
refuses any image outside the demo photo folders. A code-card photo is a bearer instrument,
and the guard carves out no exception for a review mockup.

**Hide picked, lane E's own ruling, folded in here because lane A builds on top of it.** The
owner's own words:

```
The press folds picked rows
```

A press folds every row picked so far. It is a press, never a live filter. A sale that
lands while Hide picked is on leaves that row in place. It folds only at the next press or
the next load. This is D263's ruling 2 (a sold row folds on the next load, never at once),
read onto the Hide picked control and not only onto Mark sold. D118 (a press changes what is
on the screen, never where the rest of it is) is why a fold may not run off a write it did
not cause.

### What this replaces, and why

D220 built a walk-only pane and a walk-only row (`OrdersWalkPane.tsx`). The screen had to
ship before the shared components existed to reuse. D274 then narrowed the layout to fit
those thin rows into one rail column, and ruled one page scroll. Splitting the buyer list's
own scroll out only mattered once a pick row was allowed to be this tall. Both rulings
protected a real outcome at the time, built out of what existed then. Neither survives Q3's
full-detail row, which needs Inventory's own width and Inventory's own rail.

This entry does not repeal D220 or D274's own arguments. The walk stays a mode of
Inventory's screen. The pane stays reused, never forked. The two-sidebar-rows shape stays.
It resolves the open questions the drift findings raised against them, on the owner's own
word, on 2026-09-27.

### What is still open

The lane plan (`orders-a/PLAN.md`, lanes A1 through A6) is not built by this entry. This
entry is the design record the lanes build from. `docs/specs/order-walk-plan.md` §16 points
here for the design, and holds the sort-order argument's own detail.

**Amended 2026-09-29 (owner's word, A1).** Under a search, a tie on section density now breaks by the box's natural name, the same as the Orders walk. The no-search order is unchanged. `docs/specs/order-walk-plan.md` §17 states how each screen ranks a search.
