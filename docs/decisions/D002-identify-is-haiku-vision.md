## D2 — Identification is Haiku vision, end to end

**Identification is Claude Haiku vision over the Batch API, owned end to end. The owner picks the engine for each run.** The default pick is the free read. The owner's word: *"i think i should be able to pick if i want it processed by haiku or marqo-b"*.

The second engine is a stock-photo matcher. It runs an open image-embedding model (Marqo ecommerce-B on onnxruntime). It ranks a card's photo against the stock photos of the cards the run could hold. `docs/specs/identify-engine-pick.md` is the design. It is built in the runs sheet and the identify command.

**Both engines are owned in this repo. Both write the same record.** A run, its collect, its join and its emit are one path for either engine (D180, a press names the cards it covers; D33, every pipeline step is reachable from a screen). The pick is one term of the press and one field of the run record.

**The matcher never guesses, and Haiku reads only the cards it does not accept.** The owner's word: *"we have the free one do all first and then for those it finds under a threshold of accuracy they get a second look by haiku and then it reaches my queue. so haiku isnt on all of them just the low con"*. One press runs the matcher over every selected card. It accepts a card only when the margin is at least 0.05 (the owner: *"maybe those under .05 get a haiku auto pass"*), the floor holds, the best answer shares no card name with a printing that has no stock image, and the pool is complete. Every other card goes to a Haiku batch in the same press. Haiku's answer is never saved on its own. It goes to the review queue with the photo, Haiku's answer and the matcher's top pick. The quote names the free count, the second-look count and the cost before any spend, and the press needs the paid confirm (D180).

**What stays true of Haiku.** OCR was researched and rejected at about 85-90% accuracy. Haiku costs about a tenth of a cent a card through the Batch API. That is negligible, so cost is not the reason the matcher exists. The set hint is an optional accelerator that the capture app records. Identification works without it, and better with it.

**The free read may also run in the background.** It reads captured cards that have no answer. It writes one identification row and never changes card state. It never spends: a card it cannot accept waits for a press. A paid press over cards it matched asks every time, and the default answer is skip. The design is `docs/specs/identify-engine-pick.md`, section 8.

**Haiku does two things the matcher cannot.** It reads the printed collector number. It reports a finish, which feeds D3 (variants resolve by a fixed ladder).

**TCGplayer Scan & Identify was evaluated and rejected as a pipeline component.** It is UI-only with no API contract. It inserts a manual browser step into an autonomous flow. It does not guarantee a per-image mapping to position. It couples identification to one platform. No integration code is written, ever.

**It is also not a precondition for anything.** A sub-floor T1 is worked directly. Scan & Identify is parked in the Someday list as an optional reference point. It answers one question: is the task hard, or is our prompt weak? That is worth knowing eventually and worth nothing urgently.

**Perceptual hashing stays rejected as an engine.** Measured on 500 real photographs, a 256-bit perceptual hash ranks the right card first for 51% of them. The matcher does so for 99%. Nothing here adds a hash layer (DEBT66, no perceptual-hash cross-check).

Evaluate any future third-party integration on five questions. Is it an API or a UI? Does it return the data the core depends on? Does the cost it replaces matter? Does it add a manual step? Does it couple us to one platform?
