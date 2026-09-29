## D199 — Joined counts as identified

**A run's phase reads `joined` as sufficient evidence that identification happened.** `server/pipeline_routes.py:_phase` gated every stage past `ready` and `identify` on `manifest.get("collected")` alone, and `collected` is written only by the camera, batch and collect path. A store-backed join (D188) writes `joined: True`, real `counts.skus` and a `pricing.json`, and never `collected`. So the run panel badged such a run "Not started" beside 42 joined SKUs, because the badge and the SKU stats were gated on different fields.

- **`_phase`'s first branch gates on `collected or joined`.** `joined=True` is written only after a `Resolved` exists, and a `Resolved` from either loader cannot exist without identification, frozen or live. The widening only pulls a run past the old gate and never adds one behind it, so an un-joined run still falls through to `join`.
- **The fix lives in `_phase` and nowhere else.** The badge, the stage bar and `RunsStage.stageOf` all derive from it. Teaching each client that joined implies past identify is the same rule written twice (D16).
- **The guard is `check_store_backed_join`,** which asserts `_phase(new_run.manifest, live=False)` is neither `ready` nor `identify` on the store-backed run's own manifest. It is red on the unfixed tree.
- `ready` and `identify` still conflate "nothing submitted" with "a batch is mid-flight". Naming which is worth doing when someone finds it load-bearing.
