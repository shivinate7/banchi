## D25 — The join partitions by game, and `Product Line` becomes a real reader

**The catalog join partitions by game, reading each export's `Product Line` column rather than inferring anything from a filename.** Built 2026-08-23, with the acceptance test this entry implies passed literally: a single-export Pokemon run was captured before the change and re-run after, and every output — join stdout, emit stdout, report, both import files, `decisions.json` — diffed byte-identical. One addition beyond this entry, flagged rather than slipped in: an `--export` file whose `Product Line` cells match no registered game refuses by name, because accepting and silently not using a file is the silent-drop shape the hard rules forbid.

`--export` is repeatable. **Never infer the game from a filename**: read each file's `Product Line` column, map file to games, then invert to game to files, which must be exactly one.

**This corrects a claim this file used to make.** The Deferred entry said the catalog join was *product-line-agnostic*. Measured, it was product-line **blind** — `Product Line` was declared in `CANONICAL_HEADER` and read by nothing, so two exports concatenated would have cross-joined in silence. Blind is not agnostic.

**Catalogs are built per game and never merged.** A merged `_by_number` would report cross-*game* collisions through `colliding_keys` as though they were the cross-*set* collisions that report is actually about — different faults with different remedies, since a set hint fixes one and nothing fixes the other.

`Catalog.from_export` filters to the game's `product_line` and, where set, its `product_line_rarities`, **reports the drop count, and refuses if the filter leaves zero rows** — which means the wrong file, and is the one case where continuing is worse than stopping.

**One import file per game.** Nobody has established whether TCGplayer's Import to Staged accepts a file spanning two `Product Line`s, and `fixtures/staged-import-accepted.csv` proves it for one line only. Per-game files are correct under either answer, so the question does not need settling first.

**Refusals exit 1, write nothing, touch no queue, and never prompt.** Two cases: two files claiming one game, and a game present in the run with no export — the second names up to eight positions and points at the `PUT` correction route. The check runs before any catalog is built, so a run that will refuse costs nothing.
