## 39 — the public demo refuses every box map move

**The gap.** The public demo has a stub server (`app/src/demoServer.ts`) with no handler for the box map
routes. The Shelf's confirm is `POST /boxes/sections/move-batch` (`moveSectionsBatch` in
`app/src/BoxShelf.tsx`), and its undo is `POST /boxes/sections/undo`. The older
`POST /boxes/<box>/sections/move` and `POST /boxes/<box>/cards/move` have no handler either. So a move pressed on the demo's Shelf is refused.

**What it costs.** A visitor to the demo sees the Shelf but cannot try a move. Nothing on the
owner's own store changes.

**Why it is not fixed.** The box map lane deferred it. The demo spec (`docs/specs/demo.md`) says
what the published page refuses, and a refused write is its normal shape.

**The fix, not built.** Record a move and its undo in the demo bundle, the way `make demo-record`
records the other routes. Or name the refusal on the Shelf in the demo build.

Cites D264 (a section moves whole).
