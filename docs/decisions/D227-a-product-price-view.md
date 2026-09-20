## D227 — A route, not a lens, and never one line for two kinds of observation

**THE VIEW.** One page per product, deep-linkable. It shows what that product has been
selling for. It marks the owner's own sales on it. `docs/specs/revenue-plan.md` section 3
and `docs/specs/revenue-next.md`'s "The per product view comes second" set the twelve
constraints. This entry argues two of them. Whether this is a route or a lens on
`#/revenue`. And how the market series and the owner's own fills are kept apart on screen.

### A route, not a lens

D103 gave the stale-listing markdown a lens on `#/pricing` rather than a route of its own.
The argument was that reading one export file is kinship of implementation. The screen that
already reads that file is where the sheet belongs. The same test refuses the lens here.

`#/revenue` reads orders. This view reads `store/pricearchive.py`. On a cache miss it reads
`pipeline/pricehistory.py`'s live endpoint. That is a different source entirely, reached by
SKU rather than by name. D212 makes the SKU the grain here, never a name — a name can cover
more than one printing. A `?sku=` lens on `#/revenue` would mean that screen's own component
tree fetching from a second, unrelated source under one path. That is the seam D103 avoided.
It kept the markdown ON the screen whose own file it already reads. Here the two screens do
not share a file at all.

The route is also the one address that can be pasted cleanly. A lens on
`#/revenue?sku=…` still carries every one of that screen's own controls — period, sort,
search, month strip — in its own query keys. A link into a single SKU would either collide
with them or need a modal to suppress the whole retrospective underneath it. That is the
same crowding D100's `#/runs` sheet was moved off of, one level up. A standalone route has
none of that. `#/product?sku=…` is the whole page. Nothing else competes for the query
string. It is a route a person opens on its own — from a bookmark, a note, an order line —
not only from `#/revenue`.

**Off-nav, not off-limits.** `#/fulfillment` and `#/gallery` already show a route need not
be a nav row to be a real, registered destination (`OFF_NAV` in `App.tsx`). This route earns
the same treatment for the same reason. It is not a screen a person browses to cold. It is a
screen a person arrives at from somewhere else, by SKU. `OFF_NAV` is where that kind of
registered-but-not-listed destination already lives.

**The link that was not built, and why.** `app/src/Revenue.tsx` was being edited by another
branch at the moment this route was built. The brief's own fence named the smallest
acceptable change to that file: "the smallest possible link, or add none." No link was
added. The route's own SKU field is the control a person who lands here cold actually finds.
`?sku=<id>` is the deep link for a caller that already knows the SKU. A row on `#/revenue`
can point at it with one `href`, added the day that file is free to touch again. Recorded
here so it does not read as an oversight. The capability exists and is reachable through its
own control. Only the second, easier entrance from `#/revenue` is deferred. That is a
live-editing conflict, not a design decision.

### Two kinds of observation, archive-first, and no second network policy

`docs/specs/revenue-next.md` states the rule. The market series is an aggregate over many
transactions this store never saw. The owner's own fills are exact — a price, a quantity, a
date, each one real. They may never be drawn as one continuous series. This entry's own
contribution is where that split falls on the READ side, given the archive
`D219` built.

- A SKU `pkmnscan archive sweep` has already visited answers straight off
  `store/pricearchive.py`. No socket opens. `D219` states the archive
  never deletes a row. This is a complete answer, not a stale one, for as long as a press
  has kept the archive current.
- A SKU the archive has never swept falls through to `pipeline/pricehistory.py:Market` —
  the same live reader `#/pricing`'s own panel already calls (D62). One reader, two callers,
  never a second implementation.
- Neither path writes. `pkmnscan archive sweep` stays the one press that folds a live read
  back into the table. That is `D219`'s own ruling, restated rather
  than reopened here.

The screen never merges the two kinds of observation into one number or one line. The
market series draws as a broken polyline. It gaps at any bucket with no price, inherited
from `PriceHistory.tsx:sparkSegments` rather than rebuilt. The owner's own fills draw as
individual marks, at their own true date and price, in the one accent this design system
allows. A fill is never colored by whether it beat or missed the market. D62 already rules
direction a sign and a word, never a color. A fill against a bucket is not even a
direction. It is two facts placed near each other. A caption beside every chart states the
bucket width now in force. That width is a property of when the report is read, not of the
sale.

### What is out of scope here

Cost basis is out of scope, along with a counterfactual re-priced at today's figure. So is
any verdict comparing a fill to its bucket. All three are
`docs/specs/revenue-plan.md` section 1's questions, not this entry's. This view draws two
kinds of observation side by side. It states their limits. It computes no comparison between
them.
