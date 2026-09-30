## 26 — The Intelligent Mail barcode encoder is written, correct against the Postal Service's own examples, and parked on a branch

Branch `claude/tcgtracking-in-house-a7cb43`, commit `c9391e1fcc90b7e1d1dabf2c359c986a87ee59a3`, on origin. It holds `pipeline/imb.py` (USPS-B-3200 Rev H steps 1 to 6, importing `typing` only), `harness/tests/t10_imb.py` (T10, 42 checks transcribed from the specification's worked examples, passing on the branch and on a main it was replayed over) and the wiring in `harness/run.py`, `docs/GATES.md`, `docs/map.py` and `CLAUDE.md`. `scripts/docs-audit-allow.txt` carries the two paths and `T10`, and the audit fails the moment a path resolves.

It is parked and not landed because no screen reaches it: step 13 (track back) and step 14 (tell buyer) in `docs/specs/order-pipeline.md` are missing. A green T10 does not mean an envelope gets scanned. The encoder models neither Mailer ID registration nor Informed Visibility, on purpose. `mailer_id` has no default, a service type code that asks for tracing is needed (STID 300 encodes correctly and reports nothing), and a serial allocator is state that belongs beside the order ledger.

**Outcome at risk.** The branch is the only copy. Deleting it loses the work.

**Closes when.** The owner makes step 13 live work and a Mailer ID is registered to an Informed Visibility subscription. On revival, recount the harness tests from `harness/run.py`'s `TESTS` and not from either side of a `CLAUDE.md` conflict.
