4. ~~Batch script v2: Batch API, variant ladder, catalog join, real CSV library~~ — code
   done 2026-08-03, spec at `docs/specs/batch-script.md`, harness green at T1–T6.
   `./banchi identify | join | emit | reconcile`. **This line read "not yet run against a
   real card" until 2026-08-22**. Gate B put 53 through all four commands. It reconciled back in two clean round trips with zero unmatched in either direction. The run found
   defects in this step's own code that no fixture could: the Batch API refusing the store's `box/index` as a `custom_id`. `cmd_join` leaving a re-routed position's stale entry in the queue it left. Review answers nothing on the join path ever read back (now rung 0 of the ladder). A post-import re-emit that double-counted staged copies. The harness still
   exercises this step against fixtures and synthetic images only; the run itself is in the
   Gate B section above.