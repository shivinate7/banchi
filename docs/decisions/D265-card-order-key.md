## D265 — A card's place in its box is an order key apart from its stored index

**The owner's ruling, 2026-09-23, in the box map interview.** A section drops before or after
any section of another box. Sections reorder within a box. That is all the owner ruled on
placement.

**The order key is the orchestrator's inference and design, not the owner's ruling.** The
orchestrator read the placement ruling as needing a per-card order key, and recorded that it
needs its own decision. This entry records that inference, its design, and what is open. The
owner has not seen the design.

The spec is `docs/specs/box-map.md`. The section object is the entry with slug
`a-section-is-an-object`.

### The premise that no longer holds

Today a card's place in its box IS its stored index. The walk reads index order. `Position`
in `pipeline/join.py` derives every label from it. A section's bounds are a list of divider
indices, such as `[1, 31, 56]` (D10, the inventory model). The store can only append. A moved
card gets the destination's `next_index`, which is the back.

So "index order is box order" held while cards only arrived at the back. Once a section can
land between two others, it does not hold.

### Why the stored index still never moves

D10 says positions are never renumbered. D58 (a card's number counts the cards, not the slots)
costed a moving index and rejected it on four measurements. Queue entries, the identification
cache, listing holds and every write's aim use the index. A moving index would rewrite all of
them. None of that changed.

**The stored index stays the identity that writes aim by. It never moves.**

### The proposed design

Each card gets an order key beside its index. The walk, the labels and the section bounds read
the key. A move before or after a section changes keys only. The index, the photograph (filed
by `cid` since D183, the photograph is stored under the card's name), the queue and the holds stay as they are.

What it protects: the outcome D10 and D58 protect, a key that never changes under anything that
addresses it. It adds the freedom the owner asked for.

### What is open

The shape of the key is not decided. The builder brings options to the owner with measurements:

- **The form.** A sortable fraction between two neighbors, integers with gaps, or an order
  within the section object. Each costs something different on a long box.
- **The dividers.** A divider list of indices cannot describe a section that lands between two
  others. Dividers may need to key by order key, or the section object may hold its own cards.
- **The migration.** The first key for every card is its index. That gives today's order with
  no visible change.
- **The label formula.** `Position` is the one place that composes a label. It must read the key
  and nothing else.

### What is built

RECORDED as a proposal, NOT BUILT. The owner's word on the design comes before the build. It comes before the box map's placement slice. It needs two harness cases.
A key migration changes no label. A placement between two sections renumbers only the cards it
should.
