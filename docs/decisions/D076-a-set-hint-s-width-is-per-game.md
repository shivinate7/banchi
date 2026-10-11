## D76 — A set hint's width is per-game

**A set filter needs the box to be unanimous, and the game decides whether to narrow at all.** D65 scoped the export by the set hints the box's cards carry. Widening is always safe. Narrowing is not. That reasoning holds, but the rule built from it counted the wrong thing.

### The defect

The rule gathered the hints that existed and never counted the cards with none. A set of hint strings has forgotten how many cards there were. So any hint narrowed the fetch, whatever fraction of the box had spoken. One hinted card in a 200-card run scoped the export to one set. Reproduced on a synthetic Riftbound run: `SetNameIds` came back `["77"]`. 199 cards had no catalog row, so each would have queued `no_catalog_row`.

Nothing could see it. The fetch reported success. D65's positive check passed, correctly, since it asks whether the requested sets arrived. It cannot ask about sets nobody requested, and that is the failure. The receipt named the scope only after the file was on disk.

A box sorted by rarity showed the same gap. Most cards carried only a rarity claim. For that game the category is the correct answer, for a second reason below.

### Unanimity, not presence

**A hint is evidence about the card that carries it and about no other card.** So a set filter is legal only where every card of the game in the run carries a hint, and every hint resolved. Anything less widens to the category and says which condition failed.

**`server/pipeline_routes.py:_scope_counts` returns counts rather than a set of strings.** The old shape could not answer the question. `cards` and `hinted` are the two numbers the rule turns on. One counter serves both the fetch and the preview. So the panel cannot describe a scope other than the one the button sends. `_parse_preflight` already follows that rule: never recompute a figure the operator is reading.

### How wide to ask is per-game

**`export_scope` in `pipeline/games.py`, and only `riftbound` earns `category`.** The committed export is the entire English catalogue in one 10,078-row, 1.6 MB file. A set filter buys nothing there, and spending one carries a real hazard.

**Every other game keeps `sets`, and the default is `sets`.** `sets` is the value that cannot be wrong by omission. It still widens unless the cards are unanimous. `one_piece` is the likely next `category`. It stays `sets` until a whole-category download is measured. The module uses the same asymmetry to decide how far a matrix may narrow. Its committed export is three sets out of many.

**`pokemon` is not a candidate.** It has 220 sets in the live category picker. The widest file this repo holds is four of them.

**The audit row is blocking and provable from the literal.** The value is one the registry publishes. `category` cannot be authored for an entry naming no `tcgplayer_category_id`.

### Three voices, and the screen says which one spoke

**The operator outranks the game, and the game outranks the cards.** Explicit `set_ids` is somebody making a claim about the box. The inference was trying to reconstruct that claim. So it narrows a box carrying no hint at all. `scope` picks the axis. The registry rule is next. The cards' unanimity is last.

**`GET /pipeline/runs/<name>/scope` draws the lever's position before it is pulled.** It is free and presses nothing. It takes the same three fields the fetch takes. It answers a mixed-game run with a LIST. `POST .../export` refuses `game_required`. A screen that must ask which game cannot draw the picker from a route that refuses without one.

**It degrades the way `GET /tcg/sets` does.** Resolving a hint needs the portal. So a stale cookie leaves `asked` null, with the reason named. The counts, the game's rule and the reason it would widen are local. They still draw.

**`asked.reason` is on the receipt as well as on the control.** Only someone who sees which voice chose a scope can correct it. A receipt that reports the scope without the reason let the one-hinted-card narrowing read as correct.

### What was deliberately not surfaced beside it

**`--rule` and `--basis` stay off `#/runs`.** D86 makes `decisions.json` the one place a pricing answer is written. `#/pricing` is the press that writes it. `check_pricing_presets` exists because a second place to say `rule` already produced 48 cards about to list at a price nobody had chosen. A third place would repeat that defect.

**`--review-below-confidence` is surfaced.** It is a routing question, not a pricing one. It is written nowhere else, and it was reachable only from a terminal.

### Three fields of the request are instructions, and they are guarded as such

**`ExcludeListos` is `True`: listings with photos are excluded.** The owner ruled this a standing instruction. The entry rests on that ruling, not on an argument this repo can check.

**What the flag does to the file is NOT measured.** The entry says so rather than reasoning past it. The name is read off the portal's own bundle. Nothing here has run the same request both ways. The mechanism is a guess. A seller-photo listing is usually a specific copy at a premium. So excluding them changes what the low-price columns aggregate. The export carries four price columns: `TCG Market Price`, `TCG Direct Low`, `TCG Low Price With Shipping`, `TCG Low Price`. They are TCGplayer's own, with no published rule for which listings feed them. This is an open measurement, not a finding. One authenticated fetch each way, diffed, would settle it.

**It shipped `False`, and no decision chose that.** D65 captured the request body from the owner's own browser submit. So this field arrived carrying whatever the Pricing tab's checkbox was set to that day. Eleven of the fourteen fields transcribe somebody else's form. Three are decisions, sitting among the eleven with a comment beside each.

**Nothing downstream could catch it. That is why the guard is needed and the measurement is expensive.** D65 measured `Photo URL` empty in all eleven exports, filtered and unfiltered. This axis leaves no trace in the file it narrows, so the file cannot show what the flag did. A wrong value gives a clean join, a clean reconcile and a green `make check`, indefinitely.

**So the three are hoisted into `STANDING_FILTERS` and spread last.** A re-capture of the portal's body cannot silently paste over them. `scripts/docs-audit.py`'s `export request` row blocks the commit on any value that has moved. It names the instruction rather than the literal. Somebody who has just changed a value already knows the literal. T7 asserts all three on the wire. That is the half a literal check cannot reach.

**The first fetch after this lands will refuse `export_narrower`, correctly.** It removes rows a previous export carried, which is the guard working. `accept_narrower` is the honest answer once. The baseline moves with it (retired).

**The rarity and condition axes stay unspent.** `Scope` carries `rarity_ids` and `condition_ids`, and both remain empty. D65 measured that a condition filter thins a number's rows. D3 rung 2 then decides a card from whichever row survived. A rarity claim is per-card, so it would inherit the partial-claim defect this entry fixes.
