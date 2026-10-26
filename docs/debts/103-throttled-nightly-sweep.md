## DEBT103 — A nightly sweep that stops still ends the job with exit 0

The daily price job runs `archive sweep --write` after its refresh (D224). A second throttle or a host that refused from the first sku stops the sweep. It keeps every bucket it wrote (D222) and records a failed `archive` step. The job still ends 0, by the owner's default. `#/pricing` draws a step's sentence only when the whole refresh failed, so on the screen a stopped night looks like a finished one.

**Outcome at risk.** The archive stops growing on nights when the host throttles, and nobody sees it until they read the job log.

**Closes when.** `#/pricing` shows the archive step's sentence when it stopped early, or the owner rules that the log is enough.

**Two known limits.** A pass where every sku is refused for a reason other than a 403 (offline, a server error) ends ok, so the day's sweep is spent and nothing more is read until tomorrow. A failed refresh repeats all four refresh steps at every start of the job and skips the sweep until the refresh succeeds.
