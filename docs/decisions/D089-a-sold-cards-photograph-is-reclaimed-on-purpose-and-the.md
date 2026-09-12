## D89 — A sold card's photograph is reclaimed on purpose, and the record keeps its digest

**`POST /boxes/<box>/photos/reclaim` deletes the photographs of a box's sold cards, keeps every record, and writes the photograph's digest onto the record before the bytes go.** Built 2026-09-01, the second of the two things the owner's 100k plan named as blocking the run. Photographs measure ~1.8 MB each — `captures/` is 2.7 GB for ~1,560 cards — so 100,000 cards is ~176 GB, and if ~95% sell or go out as bulk and are reclaimed per batch, the retained set is ~9 GB. The owner's ruling: **records are permanent, photographs are disposable once a card is sold through.**

### The operation did not exist, and it is a third shape

`_unlink` ran only in the capture-undo path, which deletes the RECORD as well (D10). `sold` and `retired` both keep the photograph (D26). Record kept, photograph reclaimed is the shape between them, and it is a new one rather than a softening of either: D10's undo is a card that was never captured, D26's states are a card that left with its evidence intact, and this is a card that left and whose evidence is now the digest rather than the bytes.

**Sold only, and the boundary is the store's.** A retired card's photograph is what lets the retirement be questioned later — D26 says so — and a card on hand needs its photograph for the pull preview (D6). `Inventory.record_photo_reclaimed` refuses any state but `sold` with `CardNotSold`, so a caller that bypassed the route cannot reclaim a photograph a screen still needs; the route filters to sold cards with a photograph on disk before it asks. The sidecar stays: it is the operator's claims, a few hundred bytes, and `identify.sidecar.scan` keys on the photograph, so a sidecar with none beside it is inert.

### What the record keeps, and what D36 gives up

**`photo_sha256` and `photo_reclaimed_at` are set together, by this operation and nothing else, and are null while the file is on disk.** While the photograph exists the file is the fact, and a copy of its digest on the record would be a second thing to keep true through D26's re-shoot. Once the bytes are gone the digest is the only trace of what was photographed. The `photo` path is kept too, so `photo: null` goes on meaning "never photographed" — `emit` records such cards — and a screen that finds `photo_reclaimed_at` set draws *reclaimed*, which is a different fact from *missing*: one is a store that gave something up on purpose, the other is a store that lost something. `BoxBrowse`'s photo panel says which, with the stamp and the digest.

**D36 made the photograph the truth and `photo_sha256` the binding between a run and a slot**; a box whose sold photographs are gone can no longer be re-bound that way FOR THOSE CARDS. That is given up here deliberately, for cards that have left the box, and it costs less than it reads: `cli/resolve.py:realign` reads a reclaimed card as *departed* — the digest on the run record is on no photograph in a box whose other photographs are present — which is the truth, it sold. T7 holds that outcome. A box reclaimed whole reads as *unverified* and passes through, which is D36's existing answer for a box with nothing to check against.

### It gates, and it is shaped like the release rather than the delete

There is no undo — the bytes are gone and the card is not in your hand — so this sits with the whole-box delete under `docs/DESIGN.md`'s *"genuinely destructive actions may still gate"* clause. The gate is D34's preflight shape: `GET /boxes/<box>/photos` answers the free count — sold cards whose photograph is on disk, the bytes they hold, the cards already reclaimed, and the on-hand photographs a reclaim does NOT touch — and the control that fires **does not exist** until it has answered, absent rather than disabled. Both presses name the box. `confirm: true` on the wire, for the release's reason: the route's whole content is a person's decision that these photographs are disposable, and a request must say so on purpose. A second press meets `nothing_to_reclaim` rather than a silent zero.

**Reachable**: `#/inventory`'s box operations, above the delete and below the release, drawn only for a box holding a sold card. The route, the client functions, the control, the receipt naming every key, and the panel's reclaimed sentence all landed together, which is `CLAUDE.md`'s route-is-not-a-feature rule observed rather than owed.

### What is not built

**No store-wide reclaim.** The plan's own shape is per batch — reclaim as each 5,000-card lot sells through, so the peak stays near 9 GB rather than climbing to 176 — and a box is the batch this product has. A whole-store press is one loop over `GET /boxes` away if the per-box gesture turns out to be resented, and the history of the box delete says what a resented gate becomes.

**No probe of the pile.** Neither this entry nor D88 measures whether the 100,000 cards are worth scanning; the 2,000-card probe that decides it is work at the rig, and it needs none of this — at 2,000 cards the JSON store was 25 ms. This is the second half of the plan built ahead of the first, on the owner's instruction to execute the plan end to end, and it is recorded that way rather than as the probe having been done.

---
