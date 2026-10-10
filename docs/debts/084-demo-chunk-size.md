## DEBT84 — The public demo's first screen is heavier than its budget

**The demo fetches each screen's recorded data when the screen asks (`docs/specs/demo.md`, "Fetched per screen"), and Home's first load is still 8.3 MB decoded against the budget asserted in `app/tests/demo-coverage.spec.ts`.** Before the split the `demoServer` chunk was 86 MB raw and Home's first load was 87.9 MB.

- **Measured.** Home's own reads are `/pipeline/pricing` 4.2 MB and `/orders` 1.5 MB. The app shell is about 1.6 MB and the index 0.44 MB. The 8.5 MiB budget (8.9 MB) holds with these reads whole, with little room. Unmeasured on a slow network.
- **Not fixed because** Home's tiles read whole worklists. A leaner read is a change to a wire route, or a slim recording Home asks for by name. Neither is the demo's to invent.
- **Closes when** the first screen's data is under the budget the check asserts, or the owner rules a budget the measured split meets.

**Outcome at risk.** A reviewer opening the demo sees skeletons for many seconds.
