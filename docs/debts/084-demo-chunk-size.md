## DEBT84 — The public demo's first screen sits just under its byte budget, and its time on a slow network is unmeasured

**What.** The demo fetches each screen's recorded data when the screen asks (`docs/specs/demo.md`, "Fetched per screen"). Home's first load is 8.32 MB decoded, under `HOME_FIRST_LOAD_BUDGET_BYTES` (8.5 MiB) in `app/tests/demo-coverage.spec.ts`. Before the split, the `demoServer` chunk was 86 MB raw and Home's first load was 87.9 MB.

- **Measured.** Home's own reads are `/pipeline/pricing` 4.2 MB and `/orders` 1.5 MB. The app shell is about 1.6 MB and the index 0.44 MB. The budget (8.9 MB) was set just above the measured 8.32 MB, so it has little room. The test says to lower it, never raise it. Unmeasured on a slow network.
- **Not fixed because** Home's tiles read whole worklists. A leaner read is a change to a wire route, or a slim recording Home asks for by name. Neither is the demo's to invent.
- **Closes when** Home's first load is timed on a throttled network and the owner rules the time enough.

**Outcome at risk.** A reviewer opening the demo on a slow network may see skeletons for several seconds. Unmeasured.
