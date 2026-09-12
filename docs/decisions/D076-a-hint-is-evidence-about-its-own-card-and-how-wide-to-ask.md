## D76 — A hint is evidence about its own card, and how wide to ask is a per-game rule

**A set filter needs the box to be unanimous, and the game decides whether to narrow at all.** Built 2026-08-31.

D65 scoped the export by the set hints the box's own cards carry. The reasoning — widening is always safe, narrowing is not — is right, and the rule built from it counted the wrong thing.

### The defect

**It gathered the hints that existed and never counted the cards carrying none.** A set of hint strings has already forgotten how many cards there were, so `hints` was non-empty and the fetch narrowed, whatever fraction of the box had spoken.

**One hinted card in a 200-card run scoped the whole export to that one set.** Reproduced before the fix on a synthetic Riftbound run: `SetNameIds` came back `["77"]`, 199 cards had no catalog row to match, and each would have queued `no_catalog_row`.

**Nothing could see it.** The fetch reported success. D65's own positive check passed, correctly — it asks whether the sets that were asked for arrived, and Origins did arrive. The check cannot ask about sets nobody requested, which is exactly the failure. The receipt named the scope only after the file was on disk.

**The owner hit it on a box sorted by rarity.** Some cards carried a set hint, most carried only a rarity claim, and the expectation was the whole category — which for that game is the correct answer for a second reason, below.

### Unanimity, not presence

**A hint is evidence about the card that carries it and about no other card.** So a set filter is legal only where every card of the game in the run carries a hint and every hint resolved. Anything less widens to the category and says which condition failed.

**`server/pipeline_routes.py:_scope_counts` returns counts rather than a set of strings**, because `cards` and `hinted` are the two numbers the rule turns on and the old shape could not answer the question. One counter serves both the fetch and the preview, so the panel cannot describe a scope different from the one the button sends — the rule `_parse_preflight` already follows about not recomputing a figure the operator is reading.

### How wide to ask is per-game

**`export_scope` in `pipeline/games.py`, and only `riftbound` earns `category`.** The committed export is the entire English catalogue in one 10,078-row, 1.6 MB file, so there is nothing a set filter buys there and a real hazard in spending one.

**Every other game keeps `sets`, and the default is `sets`** — the value that cannot be wrong by omission, since it still widens unless the cards are unanimous. `one_piece` is the likely next `category` and stays `sets` until a whole-category download is measured, on the same asymmetry that module already uses to decide how far a matrix may be narrowed: its committed export is three sets out of many.

**`pokemon` is not a candidate.** 220 sets in the live category picker, and the widest file this repo holds is four of them.

**The audit row is blocking and provable from the literal**: the value is one the registry publishes, and `category` cannot be authored for an entry naming no `tcgplayer_category_id`.

### Three voices, and the screen says which one spoke

**The operator outranks the game, and the game outranks the cards.** Explicit `set_ids` is somebody making the claim about the box that the inference was trying to reconstruct, so it narrows a box carrying no hint at all; `scope` picks the axis; the registry rule is next; the cards' unanimity is last.

**`GET /pipeline/runs/<name>/scope` draws the lever's position before it is pulled.** Free, presses nothing, and takes the same three fields the fetch takes. It answers a mixed-game run with a LIST where `POST .../export` refuses `game_required`, because a screen that must ask which game cannot draw the picker from a route that refuses without one.

**It degrades the way `GET /tcg/sets` does.** Resolving a hint needs the portal, so a stale cookie leaves `asked` null with the reason named — and the counts, the game's rule and the reason it would widen are local and still draw.

**`asked.reason` is on the receipt as well as on the control**, because a scope is only correctable by somebody who can see which voice chose it, and a receipt reporting the scope without the reason is what let the one-hinted-card narrowing read as a correct answer.

### What was deliberately not surfaced beside it

**`--rule` and `--basis` stay off `#/runs`.** D49 makes `decisions.json` the one place a pricing answer is written and `#/pricing` the press that writes it; `check_pricing_presets` exists because a second place to say `rule` already produced 48 cards about to list at a price nobody had chosen. A third would be that defect by a third road.

**`--review-below-confidence` is surfaced**, because it is a routing question rather than a pricing one, it is written nowhere else, and it was reachable only from a terminal.

### Three fields of the request are instructions, and they are guarded as such

**`ExcludeListos` is `True` — listings with photos are excluded.** The owner's standing instruction, 2026-08-31, and it stands on that rather than on an argument this repo can check.

**What the flag does to the file is NOT measured, and the entry says so rather than reasoning past it.** The name is read off the portal's own bundle and nothing here has run the same request both ways to see what moves. The plausible mechanism — a seller-photo listing is usually a specific copy at a premium, so excluding them changes what the low-price columns aggregate — is a guess, and the export carries four price columns (`TCG Market Price`, `TCG Direct Low`, `TCG Low Price With Shipping`, `TCG Low Price`) that are TCGplayer's own, with no published rule for which listings feed them. Recorded as an open measurement rather than dressed as a finding: one authenticated fetch each way, diffed, would settle it.

**It shipped `False`, and no decision ever chose that.** D65 captured the request body off the owner's own browser submit, so this field arrived carrying whatever the Pricing tab's checkbox happened to be set to that day. Eleven of the fourteen fields are transcription of somebody else's form; three are decisions, and they were sitting among the eleven with a comment beside each.

**Nothing downstream could ever have caught it, which is what makes it a guard rather than a comment — and is also why the mechanism above is unmeasured.** D64 measured `Photo URL` empty in all eleven exports, filtered and unfiltered: this axis leaves no trace in the file it narrows, so the file cannot be read for what the flag did to it. A wrong value gives a clean join, a clean reconcile and a green `make check`, indefinitely. The same blindness is what makes the guard necessary and the measurement expensive.

**So the three are hoisted into `STANDING_FILTERS` and spread last**, where a re-capture of the portal's body cannot silently paste over them, and `scripts/docs-audit.py`'s `export request` row blocks the commit on any value that has moved — naming the instruction rather than the literal, because somebody who has just changed a value already knows what the literal is. T7 asserts all three on the wire, which is the half a literal check cannot reach.

**The first fetch after this lands will refuse `export_narrower`, correctly.** It removes rows a previous export carried, which is the guard doing its job; `accept_narrower` is the honest answer once, and the baseline moves with it (retired 2026-09-02).

**The rarity and condition axes stay unspent.** `Scope` carries `rarity_ids` and `condition_ids` and both remain empty: D64 measured that a condition filter thins a number's rows and that D3 rung 2 then decides a card from whichever row survived, and a rarity claim is per-card and would inherit the exact partial-claim defect this entry fixes.

---


