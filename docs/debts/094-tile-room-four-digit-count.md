## DEBT94 — a five-digit count can wrap a tile note and grow the send bar

**What.** The send bar's tile rooms are sized for four wide digits. `Pricing.tsx:ROOM_COUNT` is `'8888'`, and each tile's room is written before any count is known. A count of five digits can wrap a note one line past its room.

- **Result:** the send bar grows in height when a note wraps. The page moves under the person. D313 forbids that (nothing on screen moves unless the person moved it).
- **Not fixed because** the reach is unmeasured. No one has measured whether a store holds a count past four digits. The four-digit room is a deliberate shortcut, marked `ponytail:` at `ROOM_COUNT`.
- **Closes when** a test at a five-digit count keeps each note on one line and the bar at its height. Or a store measure shows no count reaches five digits.
- **Points to** D277 (Pricing lists all rows; the slim bar's three tiles), D313 (nothing on screen moves unless the person moved it).

**Outcome at risk.** On a store with a five-digit count, the send bar grows and the page moves under the person.
