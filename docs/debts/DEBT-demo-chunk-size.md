## DEBT-demo-chunk-size — The public demo's first screen waits on a 75 MB chunk

**The demo's `demoServer` chunk is about 75 MB, and Home shows skeletons until it has arrived and evaluated.** Every read waits on it, because `server.ts`'s `request()` imports it before answering. On the CI runner it took about 15 s. A visitor on a slow link waits on the same skeletons.

- **Measured limit.** At 4x CPU throttle, first screen drawn in 4.0 s before the clone was removed and 2.9 s after. Of that, the chunk's transfer is about 0.5 s and its JSON parse about 0.2 s unthrottled. On the CI runner the wait reached about 15 s (one failed run, two traces). Unmeasured on a slow network.
- **Not fixed because splitting the recording per route is its own change.** `demoServer.ts` reads the recording synchronously through `doc()`. Heavy keys (`/pipeline/pricing`, `/pipeline/holdings-value`) are over half the bytes and the first screen needs none of them, but lazy loading them means async reads throughout.
- **Closes when** the first screen's data is under a stated size and its first paint is under a stated time, both asserted by a check.

**Outcome at risk.** A reviewer opening the demo sees skeletons for many seconds.
