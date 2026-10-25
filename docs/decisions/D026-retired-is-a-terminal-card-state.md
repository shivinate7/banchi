## D26 — Retired is a terminal card state

**A card that leaves without a sale takes the terminal state `retired`, sibling of `sold`, with a reason (`pulled`, `damaged`, `lost`, `given_away`).** It keeps its record, leaves its gap permanent and is reversible (`POST /inventory/<box>/<index>/retire`, `restores_to`). A sale refuses a retired card (`card_retired`). It is not the tombstone D10 refused, because undo would invent a third thing the store must explain. This is a real card that has left. One more reason exists that a person never picks: `empty_slot`, written only by `identify` when a card's photograph is dark and its best match is weak (the card is captured, or an earlier paid run filed it identified with no name, and no person has answered it) (`Inventory.retire_empty_slot`). `Inventory.retire` and the retire route refuse it, and its event names the p99 and the best match.

The state is `retired`, not `removed`, because `removed` is already a history event name. T7 asserts no event name is a member of `master.STATES`, and `_state_before_sale` filters history against that tuple. A state called `removed` would make old undo events parse as states.

A bad photo is replaced in place: `POST /inventory/<box>/<index>/photo` replaces the bytes and rebuilds the sidecar. It leaves the record untouched and never involves the allocator. It appends a `reshot` history line carrying both capture ids. The control sits on the pull preview, where a bad photo is found. It is a file input because that screen has no camera.

Out of scope: a returned or canceled sale (`sold` is terminal), and one damaged copy among several (D7 makes copies fungible, and a damaged copy is exactly the one that is not).
