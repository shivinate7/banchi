## 32 — The archive sweep is scheduled, and only runs on a day the Mac is on

**What.** `banchi archive sweep` has no timer of its own (D224). The daily price job runs it, once per US Central day, in the first job run of that day, on the owner's word. launchd runs a job missed in sleep when the Mac wakes. A day the Mac stays off all day runs no sweep. The job also runs at login (`RunAtLoad`), so a Mac that was off at the job's hour sweeps when it is next on. D219 (the price archive never deletes) governs what a sweep stores. D222 (the host throttles this client) sets its pace.

**Outcome at risk.** Price history goes unarchived on a day the Mac is off all day. Nothing on a screen says so beyond the `archive` step in the `#/pricing` note.

**Closes when.** The owner rules that a missed day is fine, or the sweep moves to a host that is always on.
