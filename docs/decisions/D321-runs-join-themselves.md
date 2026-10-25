## D321 — Every identify run joins itself at its end

Kind: build
Plan: docs/specs/batch-script.md#47-a-run-joins-itself (python)
Plan: docs/specs/batch-script.md#47-a-run-joins-itself (web)

**The owner ruled it.** At its end, every identify run, paid or free, joins itself. A sweep already does this. A run no longer waits for a press to finish.

**A join that fails is visible.** If the join does not run, or is refused, the run stays at the join step. The run's summary says the join did not run, and says why. The answers stay banked. The summary says the cards are held until the join. A press on the join step stays. It repeats a join that failed or never started.

**The join is the screen's own match, and it costs nothing.** The join helper in `cli/cmd_identify.py` (`_join_now`) takes the path that the screen's automatic match takes. If the game holds an export fetched on the same US Central day, it reuses that export. If not, it fetches one (D166, the catalog export belongs to the game). Then it joins. It adds no second join and no second fetch. The sweep and the join command both record a join through `cli/cmd_join.record_join`. After the join, a second helper in `cli/cmd_identify.py` (`_held_now`) reads the queues back. It says where the store holds the cards: held for review, in the main queue, parked, or settled. A test run is not joined. A run directory outside the store's runs folder is not joined. The run says so.

**The run-start export prefetch is removed.** At the start of the read, it fetched the game's export in a background thread. It took its scope from identifications, and none exist at run start. The fetch was refused every time and could never work. The join now gets the export at the end of the run.

**Open: the card state `read`.** The owner ruled a new card state, `read`. A card is `read` after Haiku has answered and before the join has run. It sits between `captured` and `identified`. It is ruled and not built. Until it is built, no card carries it and no screen names it. The builder checks two name clashes. T7 asserts that no history event name is a card state (D26, retired is a terminal card state). `store/master.IDENTITY_READ` already uses `read` as a value of `Card.identity_source`, a different field.

**Governing.**

- D1 (capture is dumb, batch identifies later): the join is a batch step. It moves from a press to the end of the batch run. Capture is unchanged.
- D33 (every pipeline step is reachable from a screen): join stays its own step with its own control. It stays free and can be run again. The identify run is a second caller of it, not a second copy.
- D166 (the catalog export belongs to the game): the run gets the export through the one path that entry defines.

**Outcome protected.** A run that ends with its answers banked and no join leaves its cards unpriced until someone presses. The owner should not have to know that a run is half done.
