## D166 — The export belongs to the game

**Measured from the owner's `runs/` after the store was re-joined.** Seven Riftbound catalog fetches went out in nine minutes. Five went out inside eighteen seconds. Five of the seven downloaded bytes this machine already had.

```
07:41:07  1,733,052 B  929bc425  runs/2026-09-01-box3-01/
07:41:33  1,733,052 B  65eb9273  runs/2026-08-30-box3-01/
07:41:37  1,733,052 B  65eb9273  runs/2026-08-31-box3-01/
07:41:42  1,733,052 B  65eb9273  runs/2026-09-01-box4-01/
07:41:46  1,733,052 B  65eb9273  runs/2026-09-11-box4-03/
07:41:51  1,733,052 B  65eb9273  runs/2026-09-11-box4-04/
07:49:50  1,733,052 B  df21a601  runs/2026-09-12-box4-01/
```

**Across all of `runs/`: 19 exports, 27.1 MB, 13 distinct. That is 9.0 MB in 6 redundant copies.** **5 of the 6 are CROSS-RUN.**

### The dedupe was real, and it looked in the wrong place

`server/pipeline_routes.py` has deduped identical bytes since the dedupe was added. It computes the digest before it composes the name. Then it searches for a file that already carries that digest. The search was `directory.glob(...)`, which covers **the run's own directory.** So a fetch could see only copies that one run had made. Every other run's identical file was invisible by construction. The one within-run pair on disk (`2026-08-31-box3-01`: two byte-identical 366 KB exports, 29 seconds apart) predates that fix. The five cross-run copies were never reachable from where the search looked.

### The box was never the unit, and the real rules say so

Run store-wide against the owner's store, pokemon has **543 of 543 cards hinted `ME01`**. D76's unanimity rule narrows it to one set. riftbound's `export_scope` is `category`. It takes the whole category, regardless of its 700 unhinted cards. **That is two requests for the entire store.** It is identical to what any per-box join produces. `Scope.category_id` is scalar, and `cli/resolve.py:exports_for` maps each game to exactly one file. No third axis exists that a per-drawer copy was cutting on.

So the export moves to `inventory/.exports/<game>/`. That is the shape `inventory/.live/` already had, kept for `LIVE_DIR`'s reason. The file is the evidence for the reading a run was joined against, so it is never swept.

### Three parts. Only the third can be seen by a test of the answer.

1. **The file lands in the game's directory,** not the run's. `store/files.py:EXPORTS_DIRNAME` holds the name. The server writes the file. `cli/resolve.py` reads a run's record of one back. The server imports the cli, never the reverse.
2. **The dedupe searches that whole directory.** It uses the digest first, then a full byte compare. 32 bits of digest is a name, not a proof.
3. **If a game already holds a covering, recent export, the press opens no socket.** This half removes the seven requests, not just the six files. `EXPORT_REUSE_S` is 900, sized to a sitting, not to a reading. An export IS a reading, and `describe_source`'s mtime records the time it was taken. The receipt says `reused` with the file's age. `refresh: true` forces the socket open either way.

**A wider file serves a narrower need, never the reverse.** A file fetched for the whole category covers every set in it. A file fetched for `{A}` does not cover `{A, B}`. The missing set would queue every card in it as `no_catalog_row`. That is D76's defect arriving through a different door.

**A reuse does NOT touch the mtime.** A re-fetch of identical bytes is a fresh observation, so it is touched. A reuse observed nothing. Dating a reading nobody took would let a stale export outrank a newer sale through `Listing.live_reading`.

### An outcome assertion cannot see a saving, so the check counts requests

A reuse and a fetch produce the same file, the same rows, the same SKUs, the same receipt figures and the same join. **Every figure on the receipt is identical.** The only difference is whether a socket opened. So `harness/tests/t7/pipeline_fetch.py` asserts on `stub["posted"]`. A second run over the same game must add **zero** POSTs. The dedupe arm forces the fetch on purpose, so it exercises the digest lookup and not the reuse. This is PR A's arm 9, generalised. Deleting its work-saving gate left every other assertion green, because the two paths agreed on every outcome.

**Four pre-existing checks had to start forcing the fetch. That is a finding, not an inconvenience.** `sent()` and the three cookie-rotation cases assert on what reached the socket. Under reuse they would read the previous request's body, or no body at all. They would report that as the scope this run implies. **A saving that hides an assertion is the same error as an assertion that cannot see a saving, pointed the other way.**

### A file count cannot prove the dedupe either. A mutation showed it.

**Deleting the digest lookup outright left all 88 checks green.** The name is `stamp-digest`. So identical bytes inside one second compose the identical path, and `write_bytes` OVERWRITES rather than adds. The whole block runs inside one second on this machine. Three files were all stamped at the same second. Every count reads the same whether the lookup happened or not.

**That is T7's own same-second collision, showing up as a hole in the test rather than in the product.** The arm survived because the instrument could not see the dedupe, not because the dedupe is unimportant. It is the same class of error as an outcome assertion over a saving, one register down.

**The assertion is now the receipt's own file name, against a held file whose stamp cannot collide.** Rename it into the past, re-fetch the same bytes, and the press must answer with the renamed file. That is the digest lookup and nothing else. No clock can make it pass by accident.

**The measuring instrument had the same fault.** The first mutation runner read an EMPTY stdout as a pass. So it reported a caught arm as a survivor. The probe had died and said nothing, and silence scored as success. Twelve arms, twelve caught, no survivors and no equivalent mutants. That held only after the runner stopped treating no answer as a good one.

### D65 and D76: the argument holds, the denominator widens later, and the new risk is measured

**D76's unanimity rule is untouched.** This entry changes where the file lives, not how the scope is decided. The denominator widening, from *the cards in this box* to *the cards being joined*, belongs to the selection and arrives with it.

**The cost of a widening was never priced. It is much closer to the wall than `MAX_BYTES`'s own comment believed.** One deliberate fetch of the whole Pokemon category:

| scope | bytes | rows | of `MAX_BYTES` |
|---|---|---|---|
| `ME01` alone, what 543 cards name | 238,482 | — | 0.7% |
| the whole Pokemon category | **32,629,598** | 222,849 | **97.24%** |

**903 KB of headroom, and a widening is 137x.** At the category's average of 148 KB per set, about six Pokemon set releases would make `tcg_export.fetch` refuse outright. The `MAX_BYTES` comment says the widest export read is about 1.5 MB. That is true of what has been read. It misleads about what can be asked for.

**This is a live hazard on the current tree, not only a future one.** A pokemon run with partial hints widens to `category` today, under D76's correct rule. It fetches 31.12 MB.

**So the widening is made visible three ways. A hard refusal of a file that works today is deliberately NOT one of them.**

- `GET /pipeline/runs/<name>/scope` draws this before the press. It stays a press-nothing preview. It carries `width`: the measured bytes, the cap, the headroom, and whether the figure is the WIDE one. **It is answerable only because the exports are per-game now.** Per-run copies gave every drawer its own unrelated sample, and none was the game's.
- The fetch's own receipt carries the same block, measured off the file that just landed.
- **`tcg_export_too_large` now says why it went wide.** The transport's sentence blamed the download and gave the operator nothing. The actionable part: the scope widened, which cards did it, and hinting them or naming the sets is the remedy.

**A hard refusal was considered and declined.** Overrule this if the owner disagrees. A 31.12 MB pokemon export parses, joins and is correct today. Refusing it would be a regression in the name of a future one. What is refused instead is silence.

### A figure nobody can see is not a warning, so it is on the screen

**The hard rule settled this.** A route is not a feature. Nothing is built until a screen reaches it. Left on the wire, the three new facts would make this a server-only capability wearing a receipt.

`app/src/RunPanel.tsx`, the screen that already draws `asked` and the fetch receipt, gains three sentences and nothing else. There is no new control, no new CSS and no new route. The scope line says what the press would weigh. It says so when the scope is wide and near the cap. It also says whether the press opens a socket at all. The receipt says **Export reused** rather than **Export fetched**, with the reading's age and the remedy.

**`Export reused` is the whole point of that word.** Every other receipt figure (file, rows, SKUs, sets, conditions) is byte-identical between a reuse and a fetch. An operator told "fetched" about a reading taken twenty minutes ago has been told something untrue, by a receipt that is otherwise correct.

**A narrow measurement is deliberately NOT drawn beside a widened scope.** 238 KB is the truth about one set, and a lie about the category. `width.widened` separates them. A spec reads that field, so the distinction cannot quietly collapse.

**The guards had to see a MISSING field. That is the defect this nearly shipped with.** `undefined !== null` is true, so a `!== null` guard would throw on every client. That includes every stubbed spec written before this landed. Five cases cover it. One asserts that the panel's own untouched stub still draws the sentence, and neither addition.

**Two of those cases were green over the wrong page first.** A `page.route` registered above `open()` is silently shadowed, because Playwright's last matching route wins. The two that read a figure failed on the panel-wide riftbound payload. The one asserting an ABSENCE passed while reading it. A guard must see its subject. An absence assertion is the shape that hides this best.

### The manifest is the only link back, so the digest is load-bearing

`cli/cmd_join.py` records `exports = {game: describe_source(file)}`. That record holds the path, mtime, age, **sha256** and bytes. It was almost decorative while the file sat inside the run. It is not now. The path is the only way back to a file that lives somewhere several runs share. **A shared directory is exactly where a path can change under a run that a run-local copy never could.**

So `exports_for` recovers a recorded export by its digest when the path has moved. It matches the **full** sha256, never merely the game. A fallback to "some export of this game" would join a run against a newer reading in silence. That is the hazard this move creates. A run whose file is gone entirely refuses as before, now naming the digest it looked for.

**The refusal's own sentence became false when the file moved.** It promised that a fetch "writes it into the run directory where it cannot go missing." The fetch now writes into `inventory/.exports/<game>/`, and the sentence says so.

### What is NOT in this entry

**The selection, `_resolve_scope`, `_busy_run`, `Leg`/`MAX_LEGS` and `--box` are untouched.** A run is still scoped to one box, and nothing downstream has learnt a new shape. What changed is where one file is kept, and how many times it is downloaded.

**The 19 exports already inside the owner's run directories are not moved or deleted.** A run directory is an immutable input. A run joined against a file inside it keeps that file and that answer. So `_find_fetched` looks there first. The legacy location is where those files are, not a fallback.

**Two presses racing one game can each write a stamped name for one digest.** That is bounded and benign. The byte compare means neither file is wrong. It is not worth a lock on a directory that is deliberately outside the store transaction (D88).
