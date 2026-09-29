## D55 — Strip a glued set code only after a miss

**A set code the model glued onto the number (`UNL - 120/219`, `UNL / 120/219`) is removed by its shape, and only after the exact key has missed.** The read was right about the card and wrong about the field, and the separator is arbitrary (`•` and `-` in one box). Enumerating separators loses, and `rsplit("/")` over `120/219` yields `219`, another card's identifier.

- **The rule describes a set code, anchored at the front:** two to five letters, no digits, then one separator. Over every distinct `Number` cell in both games keyed this way (1,237 Riftbound, 396 One Piece) it matches none. Letters only keeps `T02 // T03`, `SP3/006` and `303*/298`. At least two keeps One Piece's 16 `P-044` cells. At most five stops it eating a name handed in by mistake.
- **It is the ladder's second rung,** `pipeline/join.py:_walk`'s `_repair_set_code`, asked only when the key found no rows. A card that joins cleanly never reaches it, however a future export spells its cells. The worst a wrong repair does is miss again and fall through to where the card was going. `KeyStrategy` carries `repair`, so it is one rung and not one per game. Pokemon declares none.
- **It reports as `code~:`, not `code:`.** The count of how often the model ignores its own prompt would otherwise be invisible. It does not reach the queue entry, since a repaired card no longer queues.
- **A recovered number beats the name rung.** The name rung only queues (D35), because the number was the field that could not be read. Here it was read correctly, so the repaired join lists the card.

Reopen if the rate does not fall (the fix is then the prompt in `identify/prompt.py`) or for a code with no separator (`UNL120/219`), which needs a catalog check and a bolder rule.
