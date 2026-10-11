## D76 — A set hint's width is per-game

**A set filter needs the box to be unanimous, and the game decides whether to narrow at all.** Built 2026-08-31.

D65 scoped the export by the set hints the box's own cards carry. The reasoning — widening is always safe, narrowing is not — is right, and the rule built from it counted the wrong thing.

### The defect

**It gathered the hints that existed and never counted the cards carrying none.** A set of hint strings has already forgotten how many cards there were. So `hints` was non-empty, and the fetch narrowed, whatever fraction of the box had spoken.

**One hinted card in a 200-card run scoped the whole export to that one set.** Reproduced before the fix on a synthetic Riftbound run. `SetNameIds` came back `["77"]`. 199 cards had no catalog row to match. Each would have queued `no_catalog_row`.

**Nothing could see it.** The fetch reported success. D65's own positive check passed, correctly — it asks whether the sets that were asked for arrived, and Origins did arrive. The check cannot ask about sets nobody requested, which is exactly the failure. The receipt named the scope only after the file was on disk.

**The owner hit it on a box sorted by rarity.** Some cards carried a set hint. Most carried only a rarity claim. The expectation was the whole category. For that game, that is the correct answer for a second reason, below.

### Unanimity, not presence

**A hint is evidence about the card that carries it and about no other card.** So a set filter is legal only where every card of the game in the run carries a hint and every hint resolved. Anything less widens to the category and says which condition failed.

**`server/pipeline_routes.py:_scope_counts` returns counts rather than a set of strings**. The old shape could not answer the question. `cards` and `hinted` are the two numbers the rule turns on. One counter serves both the fetch and the preview. So the panel cannot describe a scope different from the one the button sends. That is the rule `_parse_preflight` already follows, about not recomputing a figure the operator is reading.

### How wide to ask is per-game

**`export_scope` in `pipeline/games.py`, and only `riftbound` earns `category`.** The committed export is the entire English catalogue in one 10,078-row, 1.6 MB file. So there is nothing a set filter buys there. There is also a real hazard in spending one.

**Every other game keeps `sets`, and the default is `sets`**. `sets` is the value that cannot be wrong by omission. It still widens unless the cards are unanimous. `one_piece` is the likely next `category`. It stays `sets` until a whole-category download is measured. That is the same asymmetry the module already uses to decide how far a matrix may be narrowed. Its committed export is three sets out of many.

**`pokemon` is not a candidate.** 220 sets in the live category picker, and the widest file this repo holds is four of them.

**The audit row is blocking and provable from the literal**: the value is one the registry publishes. `category` cannot be authored for an entry naming no `tcgplayer_category_id`.

### Three voices, and the screen says which one spoke

**The operator outranks the game, and the game outranks the cards.** Explicit `set_ids` is somebody making the claim about the box that the inference was trying to reconstruct. So it narrows a box carrying no hint at all. `scope` picks the axis. The registry rule is next. The cards' unanimity is last.

**`GET /pipeline/runs/<name>/scope` draws the lever's position before it is pulled.** It is free and presses nothing. It takes the same three fields the fetch takes. It answers a mixed-game run with a LIST. `POST .../export` refuses `game_required`. A screen that must ask which game cannot draw the picker from a route that refuses without one.

**It degrades the way `GET /tcg/sets` does.** Resolving a hint needs the portal. So a stale cookie leaves `asked` null, with the reason named. The counts, the game's rule and the reason it would widen are local. They still draw.

**`asked.reason` is on the receipt as well as on the control**. It is there because only someone who sees which voice chose a scope can correct it. A receipt that reports the scope without the reason is what let the one-hinted-card narrowing read as a correct answer.

### What was deliberately not surfaced beside it

**`--rule` and `--basis` stay off `#/runs`.** D86 makes `decisions.json` the one place a pricing answer is written. `#/pricing` is the press that writes it. `check_pricing_presets` exists because a second place to say `rule` already produced 48 cards about to list at a price nobody had chosen. A third would be that defect by a third road.

**`--review-below-confidence` is surfaced**, because it is a routing question rather than a pricing one. It is written nowhere else. It was reachable only from a terminal.

### Three fields of the request are instructions, and they are guarded as such

**`ExcludeListos` is `True` — listings with photos are excluded.** The owner's standing instruction, 2026-08-31, and it stands on that rather than on an argument this repo can check.

**What the flag does to the file is NOT measured, and the entry says so rather than reasoning past it.** The name is read off the portal's own bundle. Nothing here has run the same request both ways to see what moves. The plausible mechanism is a guess. A seller-photo listing is usually a specific copy at a premium. So excluding them changes what the low-price columns aggregate. The export carries four price columns: `TCG Market Price`, `TCG Direct Low`, `TCG Low Price With Shipping`, `TCG Low Price`. They are TCGplayer's own, with no published rule for which listings feed them. Recorded as an open measurement rather than dressed as a finding. One authenticated fetch each way, diffed, would settle it.

**It shipped `False`, and no decision ever chose that.** D65 captured the request body off the owner's own browser submit. So this field arrived carrying whatever the Pricing tab's checkbox happened to be set to that day. Eleven of the fourteen fields are transcription of somebody else's form. Three are decisions. They were sitting among the eleven, with a comment beside each.

**Nothing downstream could ever have caught it, which is what makes it a guard rather than a comment — and is also why the mechanism above is unmeasured.** D65 measured `Photo URL` empty in all eleven exports, filtered and unfiltered: this axis leaves no trace in the file it narrows, so the file cannot be read for what the flag did to it. A wrong value gives a clean join, a clean reconcile and a green `make check`, indefinitely. The same blindness is what makes the guard necessary and the measurement expensive.

**So the three are hoisted into `STANDING_FILTERS` and spread last**. A re-capture of the portal's body cannot silently paste over them. `scripts/docs-audit.py`'s `export request` row blocks the commit on any value that has moved. It names the instruction rather than the literal. Somebody who has just changed a value already knows what the literal is. T7 asserts all three on the wire. That is the half a literal check cannot reach.

**The first fetch after this lands will refuse `export_narrower`, correctly.** It removes rows a previous export carried, which is the guard doing its job. `accept_narrower` is the honest answer once. The baseline moves with it (retired 2026-09-02).

**The rarity and condition axes stay unspent.** `Scope` carries `rarity_ids` and `condition_ids`, and both remain empty. D65 measured that a condition filter thins a number's rows. D3 rung 2 then decides a card from whichever row survived. A rarity claim is per-card. It would inherit the exact partial-claim defect this entry fixes.

---


