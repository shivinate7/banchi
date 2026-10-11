21. ~~**The store of record is SQLite, and a sold card's photograph is reclaimed**~~ —
    **done 2026-09-01.** D88 and D89. One SQLite file replaces the five JSON documents and the history log. Every `Store.write()` is one transaction over every table. A session loads only the rows it names. Measured on a synthetic 100,000-card copy of the owner's store, a capture's store cycle went from ~4.4 s under the JSON files to ~3 ms. That cycle builds one card object. The owner's real store migrated without loss in 0.13 s. D89
    adds the third shape between capture-undo and the terminal states — record kept,
    photograph reclaimed, digest kept — reachable from `#/inventory`'s box operations. **What
    this step did NOT do**: the 2,000-card probe that decides whether the 100k run is worth making is physical work at the rig. It has not been run. Nothing here measures the pile.
