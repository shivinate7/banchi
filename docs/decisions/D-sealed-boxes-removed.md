## D-sealed-boxes-removed — A box has no lid and no capacity, and every sealed box becomes an ordinary box

**The owner's ruling, 2026-09-25**, verbatim: "what was the point of sealed boxes? lets kill
this".

### Why the seal existed, and why it protects nothing now

D20 (a box is an object, and its capacity is retroactive) added the seal. Sealing froze a box's
`capacity` at its fill. The reason was a figure: "#40 of 250" had to stay true next week, so
the denominator could not grow. D58 (a card's number counts the cards in the box, not the
slots) took the denominator off capacity. Every number now counts the cards on hand. D58
itself recorded that `capacity` kept only one job, "it records how full the box got", and that
no figure divides by it. So the seal refused captures, dividers and moves to protect a number
that nothing drew.

### What is removed

- **The store.** `Box.state`, `Box.capacity` and `Box.closed_at`. `BOX_OPEN`, `BOX_CLOSED`,
  `BOX_STATES`, `check_box_state`, `BoxClosed`, `Inventory.close_box` and `reopen_box`. The
  boxes table no longer names a `state` column.
- **The refusals.** A capture, a divider and a move no longer refuse `box_closed`.
- **The routes.** `PUT /boxes/<box>` no longer takes `state`, and a body that sends one is
  refused as a field that does not exist. `GET /boxes` no longer answers `state` or
  `capacity`. A place block no longer carries `box_closed`.
- **The screens.** Manage box loses "Seal box", "Re-open box" and "Sealed at". The box's
  identity line loses the "sealed" pill. The Inventory rail, Home, Capture and the Shelf lose
  their lock and their "Sealed" words.

### Capacity: removed, with no reader left

The only writer of `capacity` was `close_box`. It had three readers: the census note "sealed at
N", the "Sealed at" figure in Manage box, and the `capacity` on the box row. All three were
about the seal. No figure divides by it since D58. So `capacity` is removed with the seal.

### Existing stores

Schema 13's second step, `store/db.py:_open_every_box`, removes `state`, `capacity` and
`closed_at` from every box payload and empties the old `state` column. Every sealed box becomes
an ordinary box. The step was proved on a copy of the demo store. Its one sealed box
(`RB Epics`, sealed at 34) came out with none of the three keys, and every box read back. The
step is idempotent. The history keeps its old `box_closed` and `box_reopened` lines, and
nothing writes them any more.

### What it amends

D20's seal and its retroactive capacity. D58's sentence that `capacity` keeps its D20 job.
D10's `box_closed` refusal on a new section.
