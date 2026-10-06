## DEBT86 — Capabilities written twice that have not drifted yet

**A whole-repo sweep found capabilities with more than one implementation whose copies still agree.** The hard rule "one home per capability" covers them. The server, pipeline and identify copies are closed. The app copies are next.

- **App:**
  - Percent formats in PriceMovers, PriceTrend and Revenue.
  - About 40 bare `toLocaleString()` calls beside the kit's fixed 'en-US'.
  - A hand-rolled `<details>` at 8 sites, because the kit has no disclosure.
- **Not fixed because** none gives a wrong answer today, and the drifted copies came first.
- **Closes when** each item calls its one home, or carries a written reason in the `capability homes` registry.

**Outcome at risk.** The next change to one copy leaves the other behind. That is how the free reader came to refuse 263 cards.
