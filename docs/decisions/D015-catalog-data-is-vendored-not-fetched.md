## D15 — Catalog data is vendored, not fetched

The pokemontcg.io dataset is a committed snapshot of the maintainer's own `PokemonTCG/pokemon-tcg-data` repo. Nothing calls `api.pokemontcg.io` at runtime. Zero rate limits, zero latency, zero dependency on someone else's uptime. Build-order step 9 — after Gate B, because no production code reads this data today.

**Why a snapshot is safe here, when a pricing snapshot would not be.** D8 routes every price through the TCGplayer export, and the raw repo carries no price block at all. What is left — set ids, collector numbers, printedTotal, names, rarity — is fixed the day a card is printed. Staleness therefore has exactly one form: a *new* set is missing. That fails loudly as an unknown set id, never quietly as a wrong price. Refresh is a `make` target run monthly that records the upstream commit SHA, so a T1 score is attributable to a catalog revision.

**SQLite, not Postgres.** ~20k rows, read-only after load, one machine. Every Postgres advantage is absent: no concurrent writers (D13's two devices share one truth *through* the capture server, so there is still one writer), no network access, no indexing at a scale SQLite strains at. Against that it adds a service that must be running for `make harness` to pass — the exact class of dependency this entry deletes. `sqlite3` is stdlib, so `requirements.txt` keeps its property of naming what it deliberately omits.

**Card records carry no nested `set` object.** Unlike the API response, the set is implied by the *filename*, and `printedTotal` lives only in `sets/en.json`. The join key is `zfill(3)(number) + "/" + printedTotal`, so joining card→set by filename is the one detail a loader must get right. There is no `tcgplayer` block either; see D8 for why that is fine.

**The image mirror's path is a knob, because of its size.** A full mirror is ~16.7 GB (measured: 834 KB average across 197 hires PNGs) against the 160 MB of eval images held today, which is large enough that which disk it lands on is a choice worth having. Path is overridable through `PKMNSCAN_IMAGE_MIRROR`; `harness/images/` moves with it rather than being left behind as a second copy. Mirroring at all is the point — `images.pokemontcg.io` is the piece most likely to throttle or disappear, and it is the one piece the JSON repo does not cover.

**Mirror scope is a knob with a default, not a constant.** Full catalog is the default. D12 scopes the product to SWSH/SV, which would cut the mirror to under a third (~4.8 GB) — recorded so that narrowing it later is a decision rather than an oversight.

**Upstream publishes no license file.** Private, single-operator use only. Recorded so no later session assumes redistribution rights that were never granted.

**A defect this erases.** The current fetch requests `pageSize=250` with no pagination loop, but sv1 has 258 cards, sv4 266, sv8 252 — and the banked `sv1.json` holds exactly 250 records, so sv1 is truncated today. Low severity: the manifest pins the selection, so committed scores stay reproducible and the effect is sampling bias rather than a wrong number. A local file has no page size.
