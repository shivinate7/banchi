## 32 — A nightly sweep that a throttle stops still ends the job with exit 0

The daily price job runs `archive sweep --write` after its refresh (D224). A second throttle stops the sweep and keeps every bucket it wrote (D222), and the job still ends 0, by the owner's default. Only the job log and a `archive` step in the `#/pricing` note's file say so. `#/pricing` draws a step's sentence only when the whole refresh failed, so on the screen a stopped night looks like a finished one.

**Outcome at risk.** The archive stops growing on nights when the host throttles, and nobody sees it until they read the log.

**Closes when.** `#/pricing` shows the archive step's sentence when it stopped early, or the owner rules that the log is enough.
