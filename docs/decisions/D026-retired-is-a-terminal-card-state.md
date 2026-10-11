## D26 — Retired is a terminal card state

**A card that leaves without a sale takes the terminal state `retired`, sibling of `sold`, with a reason (`pulled`, `damaged`, `lost`, `given_away`).** It keeps its record, leaves its gap permanent and is reversible (`POST /inventory/<box>/<index>/retire`, `restores_to`). A sale refuses a retired card (`card_retired`). It is not the tombstone D10 refused. That was undo inventing a third thing the store must explain. This is a real card that has left.

The state is `retired` and not `removed` because `removed` is already a history event name. T7 asserts no event name is a member of `master.STATES`, and `_state_before_sale` filters history against that tuple. A state called `removed` would make old undo events parse as states.

A bad photograph is replaced in place: `POST /inventory/<box>/<index>/photo` replaces the bytes and rebuilds the sidecar. It leaves the record untouched and never involves the allocator. It appends a `reshot` history line carrying both capture ids. The control is on the pull preview, where a bad photo is discovered, and it is a file input because that screen has no camera.

Out of scope: a returned or canceled sale (`sold` is terminal), and one damaged copy among several (D7 makes copies fungible, and a damaged copy is exactly the one that is not).
