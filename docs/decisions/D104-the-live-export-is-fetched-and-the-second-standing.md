## D104 — The live export is fetched, and the second standing instruction is a second constant

**The operator's own live listings are fetched from TCGplayer by a press, at `MyInventory: True`, behind a second guarded constant.** Built 2026-09-06 on the owner's instruction — they were shown that the markdown sheet's step 1 happened entirely off this machine and asked for it in one word: *"Fetch the export for me."*

That word is the authority `server/tcg_export.py`'s own comment requires. `MyInventory` had been `False` since D65 with a note saying the field is the CATALOGUE rather than the operator's listings, *"which is useless to a join whose whole job is listing cards that are not"* — true of the run path, and the exact inverse of what a markdown wants.

### Two literals, because they are two instructions about two documents

`STANDING_FILTERS` does not move. `LIVE_FILTERS` sits beside it holding the live fetch's own three, and `make docs-audit`'s `export request` row reads **both**.

**A parameter would have been fewer lines and is the wrong shape.** These are standing instructions, hoisted out of `Scope.model` in the first place because a body captured off the portal's own submit gets re-captured, and a re-capture pastes over every field it touches. One dict with a flag puts both instructions at one call site, where an edit to either reads as an edit to both. Two literals cannot be confused, and the row now asserts something **no single-dict loop could**: that they DISAGREE on `MyInventory`, and that neither is a reference to the other. That cross-check exists because the likeliest future edit is somebody folding two near-identical dicts into one.

**`LiveScope` is a second type rather than a `Scope` with defaults**, and the measurement decides it. The owner's real My Pricing download of 2026-09-01 is **759 rows across six product lines** — Riftbound 400, Pokemon 314, One Piece 41, YuGiOh 2, Card Sleeves 1, Playmats 1 — while `Scope.category_id` is a scalar. Expressing "all of them" by looping that scalar over the registry's three ids would have silently omitted the other three.

**The eleven transcribed fields are duplicated rather than shared.** That body is a capture, and two independent copies is what makes a re-capture of one *visible as a difference* from the other. A shared helper would let one paste move both — which is the failure hoisting exists to prevent.

**The transport is not duplicated.** `_post_export` is extracted and both fetches call it, because the redirect rule is the part that would rot in a copy: one hop is followed, the cookie is not re-sent across a host change, a chain is refused. A second implementation of that would be a second place to get it wrong on the one call in this repo carrying the operator's session.

### `CategoryId: "0"` is the unmeasured field, and its failure is loud

Nothing in this repo has sent it. `["0"]` is how the portal spells "all of them" for every LIST field — the `ids()` helper carries D65's most expensive finding, that an empty array answers `System Error` — and this is the scalar spelling of the same idea. The evidence that *some* cross-category value exists is the owner's own file: 759 rows over six product lines from one download.

**What makes it shippable rather than a guess is that it cannot fail quietly.** A malformed body comes back as HTTP 200 carrying an HTML page titled `System Error`, which `_check_body` already names `tcg_request_rejected` with the sentence *"the session is fine — this is the export request itself being malformed"*. The failure this project cannot survive is a silent narrowing — a smaller, perfectly parseable CSV with listings missing — and that is precisely what this one is not.

**If it is refused, the fallback is named and not built.** A loop over the registry's three `tcgplayer_category_id`s would silently omit YuGiOh, Card Sleeves and Playmats, so it is a branch to argue when the first press answers, never to build speculatively.

### Every narrowing axis is the portal's all-row, and that rule decides `ExcludeListos`

**On the live path an all-row the portal REJECTS fails loudly; a narrowed value that is wrong fails silently.** A rejection is `System Error` as a 200 carrying HTML, which `_check_body` already names `tcg_request_rejected`. A wrong narrowing is a smaller, perfectly parseable CSV with listings missing, on a document nothing downstream can audit. So every axis here — `CategoryId`, `SetNameIds`, `RarityIds`, `ConditionIds`, `LanguageIds` — is `0`, including `LanguageIds` where the catalogue path's proven `["1"]` is the *worse* choice precisely because English-only fails quietly.

**`ExcludeListos` is FALSE here and TRUE on the catalogue, and that is not a repeal.** The 2026-08-31 instruction sits on `STANDING_FILTERS` and does not move. On the catalogue the flag excludes OTHER sellers' photo listings, which is noise to a join. On My Pricing every row IS the operator's own listing, so the same value has the opposite effect.

**Measured on their own file rather than read off the field name**, which is exactly what `tcg_export.py`'s comment forbids. Their My Pricing download of 2026-09-01 carries four rows with a `Photo URL`, and all four are **live**:

| sku | live | asking | |
|---|---|---|---|
| C-4619147 | 6 | $20.49 | Paramount War - Booster Pack |
| C-4669926 | 3 | $27.00 | Double Pack Set Vol. 11 |
| **C-4654187** | 1 | **$7,000.00** | **Kai'Sa, Daughter of the Void (Signature)** |
| C-4619603 | 37 | $11.39 | Spiritforged - Booster Pack |

**`True` would make the lens silently omit the most valuable listing in the store**, and a 37-copy line beside it. D64's finding that `Photo URL` is empty in all eleven *catalogue* exports is what would make it permanent — this is that same fact from the other side, and it is why the eleven-export measurement does not transfer to this document.

**The audit row asserts the disagreement, on both fields.** `STANDING_FILTERS` and `LIVE_FILTERS` must differ on `MyInventory` and on `ExcludeListos`; agreement means one request has taken the other's instruction, and no single-dict loop could catch it.

**`_live_shortfall` returns None today and exists anyway.** Nothing is narrowed, so there is nothing to say — and the field is the guard against the day somebody narrows an axis and the omission is silent forever. A sentence and not a count, because the file cannot report its own omissions, which is the whole reason it is needed.

### One fetch, two consumers, one reading

The file is kept under `inventory/.live/` and named, and `POST /pipeline/markdowns` and `POST /pipeline/reconcile-live` both accept `fetched: <name>` in place of an upload. An operator who marks down and then reconciles is acting on **one** reading rather than two downloads taken minutes apart — which matters most on the reconcile, the press that writes `live` for every SKU in the store.

**Both routes refuse a request carrying both a fetch and an upload.** Guessing would pick the wrong one half the time, and the two documents can be minutes apart.

**The upload is not a fallback and does not appear on failure.** It is a door that was always open, because an operator with a download in hand should not have to fetch again and a dead cookie must not be a dead end.

**Nothing is swept.** `inventory/.live/` accumulates one file per fetch, deliberately: the file is the evidence for the reading the store wrote off it, which is `do_pipeline_export`'s rule for a run's own exports one directory over. `inventory/` is gitignored wholesale.

### What is not known

**The fetch is measured and works.** 2026-09-06, against the owner's account: 128,700 bytes, **759 rows across six product lines, 388 live rows, 1,021 live copies, 4 photo rows** — the same content as the download they took by hand the same day. That was the first press, and it answers what this entry originally recorded as owed.

**What is still unknown is everything downstream of it.** No file this pipeline writes has been uploaded to TCGplayer; `docs/specs/stale-listings.md` §6's three questions are untouched by this work.

**A fetched file's mtime is its FETCH time**, and `Listing.observe_live` arbitrates readings by that. A response TCGplayer served from a cache is therefore dated fresher than the reading it contains. `do_pipeline_export` carries the identical exposure today; this doubles it onto a store-wide surface. Named, not solved.

### What would reopen this

*The first fetch*, whose three answers belong in the spec's §6. *The owner's ruling on `ExcludeListos`*, which is one constant and one audit expectation. *A `CategoryId: "0"` refusal*, which makes the per-category loop a real question rather than a speculative one. *A live fetch that is slow enough to matter* — it holds one of `REQUEST_SLOTS = 4` for up to 120s, and `docs/DEBTS.md` §11 is the argument about what not to do about that.
