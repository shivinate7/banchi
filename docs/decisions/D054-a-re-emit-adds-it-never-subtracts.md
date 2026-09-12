## D54 — A re-emit adds; it never subtracts

**Built 2026-08-30, and it was a live data-loss bug that every check in this repo passed.** Pressing `emit` twice on one run destroyed its output: the good `import-listed.csv` was overwritten with a **header-only file**, and `manifest["emitted"]` was rewritten as `{"listed": [], "sub_threshold": [], "pushed": 0, "pushed_skus": 0}` — after which `reconcile` refused **"this run has emitted nothing — run `pkmnscan emit` first"** on a run that had emitted perfectly an hour ago, with its CSV already imported to TCGplayer.

**The mechanism, because it is one line and three instances.** `cli/cmd_emit.py:_game_only` derived its SKU set from PRICES, which do not change between emits, while `pipeline/join.py:import_rows` drops every SKU whose `add_to_quantity` is 0. `_write` then decides whether to open a file **from that set**, and `tcgcsv.render` emits the header before it iterates rows — so an empty row list produces a valid CSV of nothing, on top of the file the operator was told to import.

**Three things drop a SKU after `_game_only` and it knew about one:**

1. a **withheld** SKU (D49) — subtracted since 2026-08-29, which is the instance D49 closed;
2. a **`no_market_data` SKU answered `"unlisted"`** — `prices_for` drops it and nothing subtracted it. **This one fires on a FIRST emit**, for a game whose only above-threshold entries are unpriced-and-unlisted;
3. **`add_to_quantity == 0`**, every copy already committed — which is every SKU on a re-emit, and is the one that destroyed the file.

A fix that special-cased the third would have left the second standing. **So the rule is stated over the class:**

> **`emit` never opens an import file for writing until it has at least one row for it. What it writes is always the DELTA — the copies not already sent — and it says so.**

`_game_only` now takes `prices_for`'s own output and intersects it with the matches whose `add_to_quantity` is above zero. That set is *by construction* the row set `import_rows` will produce, so `only` stopped being an estimate. `pipeline/join.py:write_import` is split out of `emit_import` so rows can be looked at before a file handle opens; `emit_import`'s signature and behavior are unchanged, because T3 calls it in six places.

**Rewriting the file identically was considered and is refused, and this is the load-bearing half.** To do it, `emit` would have to exclude this run's own contribution from `cli/resolve.py:_committed_keys` so its copies became uncommitted again — which is exactly the state that produced the Gate B defect this repo already paid for, where a post-import re-emit **re-counted 37 copies into the files**. TCGplayer's Import to Staged *adds* quantity, so a file repeating already-imported rows double-stages them, and **nothing in this pipeline can know whether the operator imported the first file.** That is `reconcile`'s job and it is D34's argument: no export this pipeline reads can assert what TCGplayer is holding.

**No refusal. Exit 0.** `emit` is documented free and re-runnable and T7 calls a re-emit *"the ordinary thing to do after editing a review"*; a non-zero exit becomes `ok: false` on `POST /pipeline/runs/<name>/emit` and would draw a failure for a run in a perfectly good state; and a refusal is the "emit once, ever" outcome that the legitimate cases — lifting a hold, answering a `no_market_data` SKU, setting `sub_threshold` — all forbid.

**The no-op branch says the thing the operator needs, and nothing else did.** An operator who changes `sub_threshold` from `"floor"` to a flat price after emitting and presses again used to get a destroyed file and a cheerful summary. They now get told, in words, that every copy this run matched is already at `pushed`, that the file is unchanged from the earlier emit, and that **a price changed after an emit cannot travel this road** — the copies have already been sent under the old answer. It does not print `next: import`, because there is nothing new to import.

**`emitted` is a union across emits, via a named `Run.record_emit`.** `Run.set` stays replace-not-merge — `set(collected=…)`, `set(joined=…)` and `set(batch_ids=…)` all depend on that, and a global merge would be a wide silent change for one field's problem.

**The union is not tidiness, and `reconcile` is why.** It passes these SKUs to `join.reconcile_import`, which reports in **both directions** — so after emit → import → re-emit → import, a record holding only the last delta puts every SKU from the first import into `rows_without_cards`, and reconcile prints *"something else wrote it"* about rows it wrote itself. `pushed` accumulates because it is a quantity of copies and quantities sum; **`pushed_skus` is DERIVED from the lists rather than accumulated beside them**, so it cannot come to disagree with them — D49 Part One's rule applied to this record. A SKU withheld *after* being emitted stays in the union, deliberately: it was sent, its copies are at `pushed`, and the staged export will carry it.

**`_phase` is hardened independently, and that is belt to this braces.** It tested the `emitted` dict for truthiness, and `{"listed": [], ...}` is a truthy dict — so a run whose record had been blanked read `reconcile` on the panel while `reconcile` itself refused. It now asks whether the record names a SKU, through `Run.emitted_skus`. **No run on disk was ever in the corrupted state, so there is no migration** — but a hand-edited manifest, or one written by an older checkout, must not send the operator to a step that will turn them away.

**The T7 assertion that guarded this never measured its own message, and that is the finding worth more than the fix.** It read `len(read_export(IMPORT_LISTED).rows) == 0` under the message *"the file holds no zero row"*. **"The file holds 0 rows" is satisfied identically by the emitter correctly omitting a zero-quantity row and by the emitter overwriting two good rows with a bare header.** A test whose pass condition is met equally by a behavior and by that behavior's catastrophic opposite is not testing the behavior, and the destruction lived behind it for as long as it existed. T3 carried the same blindness in its full-cycle case.

Both now assert **byte equality of the file across the two emits** — byte and not row, because a rewritten empty file is a valid CSV of nothing and a row count cannot tell that from the rows never having existed. The original no-zero-row claim is kept and asserted where it is observable.

**And nothing had ever asserted the manifest after a second emit.** That is why this survived: every assertion in T7's re-emit block was about the STORE, and the store side was already safe — its idempotence lives in `cli/resolve.py:_committed_keys` and was pinned. The record beside it, which `reconcile` reads, was pinned by nothing. It is now, along with the end-to-end nobody had written: `emit → join → emit → reconcile`, **which would have caught this in one line**.

**Observed failing first, six assertions**, before a line of `cli/` was touched: the file's bytes (three lines to one), the surviving quantities, the manifest's SKU list (`[]` against both), the `next: import` line still telling the operator to import a file just destroyed, `reconcile` exiting 1, and the copies never reaching `staged`. The union was separately mutation-tested by making `record_emit` replace rather than merge, and it went red naming the delta alone.

**What would reopen this: a staged quantity `emit` could read.** The whole reason a re-emit may not rewrite the file is that nothing here knows what TCGplayer received. If `reconcile` were ever pointed at a fresh Export From Staged and allowed to set counts absolutely — the change D34 names and nobody has argued — then `emit` could compute the true outstanding delta per SKU rather than inferring it from `_committed_keys`, and rewriting the whole file would become the honest thing to do.

---