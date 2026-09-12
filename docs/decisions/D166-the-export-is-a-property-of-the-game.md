## D166 — The catalogue export is a property of the game, and the box never chose its scope

**Built 2026-09-12, from a measurement of the owner's own `runs/` after they re-joined the store.** Seven Riftbound catalogue fetches went out in nine minutes, five of them inside eighteen seconds, and five of the seven downloaded bytes this machine already had.

```
07:41:07  1,733,052 B  929bc425  runs/2026-09-01-box3-01/
07:41:33  1,733,052 B  65eb9273  runs/2026-08-30-box3-01/
07:41:37  1,733,052 B  65eb9273  runs/2026-08-31-box3-01/
07:41:42  1,733,052 B  65eb9273  runs/2026-09-01-box4-01/
07:41:46  1,733,052 B  65eb9273  runs/2026-09-11-box4-03/
07:41:51  1,733,052 B  65eb9273  runs/2026-09-11-box4-04/
07:49:50  1,733,052 B  df21a601  runs/2026-09-12-box4-01/
```

**Measured across the whole of `runs/` the same day: 19 exports, 27.1 MB, 13 distinct — 9.0 MB in 6 redundant copies.** And the shape of those six is the finding, not the size: **5 of the 6 are CROSS-RUN.**

### The dedupe was real and it was looking in the wrong place

`server/pipeline_routes.py` has deduped identical bytes since 2026-09-02, by computing the digest before composing the name and then searching for a file already carrying it. The search was `directory.glob(...)` — **the RUN's own directory.** So a fetch could only ever see the copies that one run had made, and every other run's identical file was invisible to it by construction. The one within-run pair on disk (`2026-08-31-box3-01`, two byte-identical 366 KB exports 29 seconds apart) predates that fix and is the defect it was built for; the five that matter were never reachable from where it was looking.

### The box was never the unit, and the real rules say so

Run store-wide against the owner's store on 2026-09-12: pokemon is **543 of 543 cards hinted `ME01`**, so D76's unanimity rule narrows it to one set; riftbound's `export_scope` is `category`, so it takes the whole category regardless of its 700 unhinted cards. **Two requests for the entire store — identical to what any per-box join produces, because `Scope.category_id` is scalar and `cli/resolve.py:exports_for` maps game to exactly one file.** There is no third axis a per-drawer copy was ever cutting on.

So the export moves to `inventory/.exports/<game>/`, which is the shape `inventory/.live/` already had and is kept for `LIVE_DIR`'s reason: the file is the evidence for the reading a run was joined against, so it is never swept.

### Three parts, and only the third one can be seen by a test of the answer

1. **The file lands in the game's directory**, not the run's. `store/files.py:EXPORTS_DIRNAME` holds the name, because the server writes the file and `cli/resolve.py` reads a run's record of one back — and the server imports the cli, never the reverse.
2. **The dedupe searches that whole directory**, digest first and then a full byte compare. 32 bits of digest is a name, not a proof.
3. **A press whose game already holds a covering, recent export opens no socket at all.** This is the half that removes the seven requests rather than the six files, and `EXPORT_REUSE_S` is 900 — sized to a sitting and not to a reading, because an export IS a reading and `describe_source`'s mtime is when it was taken. `refresh: true` forces the socket open and the receipt says `reused` with the file's age either way.

**A wider file serves a narrower need and never the reverse.** A file fetched for the whole category covers every set in it; one fetched for `{A}` does not cover `{A, B}`, and the missing set would queue every card in it as `no_catalog_row` — D76's defect arriving through a different door.

**And a reuse does NOT touch the mtime, which is the one asymmetry in this entry that could have gone silently wrong.** A re-fetch of identical bytes really is a fresh observation and is touched; a reuse observed nothing, and dating a reading nobody took would let a stale export outrank a newer sale through `Listing.live_reading`.

### AN OUTCOME ASSERTION CANNOT SEE A SAVING, so the check counts requests

A reuse and a fetch produce the same file, the same rows, the same SKUs, the same receipt figures and the same join. **Every figure on the receipt is identical; the only difference is whether a socket was opened.** So `harness/tests/t7_store_and_seams.py` asserts on `stub["posted"]` — a second run over the same game must add **zero** POSTs — and the dedupe arm deliberately forces the fetch so that it exercises the digest lookup rather than the reuse. This is PR A's arm 9 generalised: deleting its work-saving gate left every other assertion green, because the two paths agreed on every outcome.

**Four pre-existing checks had to start forcing the fetch, and that is a finding rather than an inconvenience.** `sent()` and the three cookie-rotation cases assert on what reached the SOCKET. Under reuse they would have read the previous request's body — or no body at all — and reported it as the scope this run implies. **The saving hiding the assertion is the same error as the assertion being unable to see the saving, pointed the other way.**

### And a FILE COUNT cannot prove the dedupe either, which took a mutation to find

**Deleting the digest lookup outright left all 88 checks green.** The name is `stamp-digest`, so identical bytes inside one second compose the identical path and `write_bytes` OVERWRITES rather than adds — and the whole block runs inside one second on this machine (measured: three files all stamped at the same second). Every count reads the same whether the lookup happened or not.

**That is T7's own same-second collision, showing up as a hole in the test rather than in the product.** The arm survived not because the dedupe is unimportant but because the instrument could not see it — the same class of error as an outcome assertion over a saving, one register down.

**The assertion is the receipt's own file name now, against a held file whose stamp cannot collide:** rename it into the past, re-fetch the same bytes, and the press must answer with the renamed file. That is the digest lookup and nothing else, and no clock can make it pass by accident.

**The measuring instrument had the same disease, and this is where it is written down.** My first mutation runner read an EMPTY stdout as a pass, and so reported a caught arm as a survivor: the probe had died and said nothing, and silence scored as success. Twelve arms, twelve caught, no survivors and no equivalent mutants — but only after the runner stopped treating no answer as a good one.

### D65 and D76 — the argument holds, the denominator widens later, and the new risk is measured

**D76's unanimity rule is untouched.** What this entry changes is where the file lives, not how the scope is decided. The denominator widening — from *the cards in this box* to *the cards being joined* — belongs to the selection and arrives with it.

**But the cost of a widening was never priced, and it is much closer to the wall than `MAX_BYTES`'s own comment believed.** One deliberate fetch of the whole Pokemon category, 2026-09-12:

| scope | bytes | rows | of `MAX_BYTES` |
|---|---|---|---|
| `ME01` alone, what 543 cards name | 238,482 | — | 0.7% |
| the whole Pokemon category | **32,629,598** | 222,849 | **97.24%** |

**903 KB of headroom, and a widening is 137x.** At the category's own average of 148 KB per set that is about six Pokemon set releases from `tcg_export.fetch` refusing outright — and `MAX_BYTES`'s comment still says *"the widest export this project has read is ~1.5 MB"*, which is a true statement about what has been read and a badly misleading one about what can be asked for.

**This is a live hazard on the current tree and not only a future one.** A pokemon run with partial hints widens to `category` today, under D76's own correct rule, and fetches 31.12 MB.

**So the widening is made visible three ways, and a hard refusal of a file that works today is deliberately NOT one of them.**

- `GET /pipeline/runs/<name>/scope` — which exists precisely to draw this before the press and stays a press-nothing preview — carries `width`: the measured bytes, the cap, the headroom, and whether the figure is the WIDE one. **It is answerable only because the exports are per-game now**; per-run copies gave every drawer its own unrelated sample and no one of them was the game's.
- The fetch's own receipt carries the same block, measured off the file that just landed.
- **`tcg_export_too_large` now says why it went wide.** The transport's sentence blames the download and hands the operator nothing; the actionable half is that the scope widened, which cards did it, and that hinting them or naming the sets is the remedy.

**A hard refusal was considered and declined**, and this is the half to overrule if the owner disagrees: a 31.12 MB pokemon export parses, joins and is correct today, so refusing it would be a regression in the name of a future one. What is refused instead is silence.

### And a figure nobody can see is not a warning, so it is on the screen

**The hard rule is what settled this, and it is not a follow-up.** *"A route is not a feature. Nothing is built until it is reachable from a screen."* The three visible facts here are new on the wire, so leaving them there would have made this a server-only capability wearing a receipt.

`app/src/RunPanel.tsx` — the screen that already draws `asked` and the fetch receipt — gains three sentences and nothing else. No new control, no new CSS, no new route: the scope line says what the press would weigh when the scope is wide and near the cap, and whether the press will open a socket at all; the receipt says **Export reused** rather than **Export fetched**, with the reading's age and the remedy.

**`Export reused` is the whole point of that word.** Every other figure on that receipt — file, rows, SKUs, sets, conditions — is byte-identical between a reuse and a fetch. An operator told *"fetched"* about a reading taken twenty minutes ago has been told something untrue by a receipt that is otherwise entirely correct.

**And a narrow measurement is deliberately NOT drawn beside a widened scope.** 238 KB is the truth about one set and a lie about the category; `width.widened` is what separates them, and a spec reads that field so the distinction cannot quietly collapse.

**The guards had to be written to see a MISSING field, and that is the defect this nearly shipped with.** `undefined !== null` is true, so a `!== null` guard would have thrown on every client — and every stubbed spec — written before this landed. Five cases cover it, one of them asserting that the panel's own untouched stub still draws the sentence and neither addition.

**Two of those cases were green over the wrong page first.** A `page.route` registered above `open()` is silently shadowed, because Playwright's last matching route wins: the two that read a figure failed on the panel-wide riftbound payload, and the one asserting an ABSENCE *passed* while reading it. A guard must see its subject, and an absence assertion is the shape that hides it best.

### The manifest is the only link back, so the digest is load-bearing

`cli/cmd_join.py` records `exports = {game: describe_source(file)}` — path, mtime, age, **sha256** and bytes — and that record was almost decorative while the file sat inside the run. It is not now: the path is the only way back to a file that lives somewhere several runs share, and **a shared directory is exactly where a path can change under a run that a run-local copy never could.**

So `exports_for` recovers a recorded export by its digest when the path has moved, matching the **full** sha256 and never merely the game — a fallback to *"some export of this game"* would join a run against a newer reading in silence, which is the hazard this move creates. A run whose file is gone entirely refuses exactly as it did, now naming the digest it looked for.

**And the refusal's own sentence was false the moment the file moved.** It promised that a fetch *"writes it into the run directory where it cannot go missing"*. It writes it into `inventory/.exports/<game>/` and the sentence says so.

### What is NOT in this entry

**The selection, `_resolve_scope`, `_busy_run`, `Leg`/`MAX_LEGS` and `--box` are all untouched.** A run is still scoped to one box and nothing downstream has learnt a new shape; what changed is where one file is kept and how many times it is downloaded.

**The 19 exports already inside the owner's run directories are not moved and not deleted.** A run directory is an immutable input, and a run joined against a file inside it keeps that file and that answer — so `_find_fetched` looks there FIRST, and the legacy location is where those files are rather than a fallback.

**Two presses racing one game can still each write a stamped name for one digest.** Bounded, benign — the byte compare means neither file is wrong — and not worth a lock on a directory that is deliberately outside the store transaction (D88).
