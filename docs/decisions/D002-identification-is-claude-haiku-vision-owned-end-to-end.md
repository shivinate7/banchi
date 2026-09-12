## D2 — Identification is Claude Haiku vision, owned end to end

**Identification is Claude Haiku vision over the Batch API, owned end to end.** OCR was researched and rejected at ~85–90% accuracy. Perceptual hashing is deferred to v2 as a cross-check. Haiku costs ~$5–15 per 10k cards via the Batch API, which is negligible. The set hint is an optional accelerator recorded in the capture app: identification works without it, better with it.

**TCGplayer Scan & Identify was evaluated and rejected as a pipeline component.** It is UI-only with no API contract, inserts a manual browser step into an autonomous flow, does not guarantee per-image to position mapping, and couples identification to one platform. No integration code is written, ever.

**It is also not a precondition for anything** (changed 2026-08-03). It was previously the required next step whenever T1 scored below the floor, which put a manual browser session on the critical path between a red harness and any attempt to fix it — the tail wagging the dog. A sub-floor T1 is now worked directly. Scan & Identify is parked in the Someday list as an optional reference point: it answers *is this task hard, or is our prompt weak?*, which is worth knowing eventually and worth nothing urgently.

Evaluate any future third-party integration on: API or UI? Does it return the data the core depends on? Does the cost it replaces matter? Does it add a manual step? Does it couple us to one platform?
