## D25 — The join partitions by game

**The catalog join partitions by game. It reads each export's `Product Line` column and never infers the game from a filename.** Map each file to games, then invert to game to files. Each game must map to exactly one file.

- `--export` is repeatable.
- An `--export` file whose `Product Line` cells match no registered game refuses by name. Accepting a file and silently not using it is the silent-drop shape the hard rules forbid.
- Catalogs are built per game and never merged. A merged `_by_number` reports cross-game collisions through `colliding_keys` as if they were cross-set collisions. They are different faults with different remedies: a set hint fixes one, and nothing fixes the other.
- `Catalog.from_export` filters to the game's `product_line` and, where set, its `product_line_rarities`. It reports the drop count. It refuses if the filter leaves zero rows, since zero rows means the wrong file was given. That is the one case where continuing is worse than stopping.
- One import file per game. Whether TCGplayer's Import to Staged accepts a file spanning two `Product Line`s is unknown. `fixtures/staged-import-accepted.csv` proves it for one line only. Per-game files are correct under either answer.
- Refusals exit 1, write nothing, touch no queue, and never prompt. Two cases refuse: two files claim one game, or a game in the run has no export. The second names up to eight positions and points at the `PUT` correction route. The check runs before any catalog is built, so a refused run costs nothing.
- Verified: on a single-export Pokemon run, join and emit stdout, the report, both import files and `decisions.json` were byte-identical before and after the change.
