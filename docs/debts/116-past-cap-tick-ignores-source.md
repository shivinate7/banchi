## DEBT116 — the send skips the cap check for any row marked ticked, typed prices too

**What.** The send's cap check skips every row the press marks `ticked: true`, whether it is a kept suggestion or a typed price. `server/send_routes.py` builds the ticked set in `_refuse_past_cap` from `payload["prices"]` without reading `source`. The screen sets `ticked` only on a past-cap suggestion, so no press sends a ticked typed price today.

- **Result:** a typed price far from the live price would skip the cap if a future screen or a hand-made request marked it ticked. The floor and the live-moved checks still apply.
- **Not fixed because** no client sends it, and the lane's review cap was reached with net safety value zero.
- **Closes when** only rows whose `source` is the kept-suggestion source can be ticked, with a typed-and-ticked case in `harness/tests/t7/one_list_wire.py`.
- **Points to** docs/specs/pricing-suggest.md ("Bigger moves show apart and need a tick") and queue item 112.

**Outcome at risk.** A typed price past the cap reaches TCGplayer without the cap's question.
