## D65 — The export is asked for, and the box's own claims are the scope

**The export request names what it wants, so completeness stops being an inference.** Built 2026-08-30.

D64 fetched whatever the portal's saved filter last produced and then tried to judge it. This names a category and a set in the request, so the file is complete within that scope by construction.

### D64 shipped against the wrong endpoint

**`/Admin/Pricing/DownloadMyExportCSV` ignores every parameter, measured across eight spellings that returned byte-identical output.** It is a different, unscoped endpoint that serves the saved filter. It entered D64 as a verified fact, it does return a CSV, and that is how it survived.

**What the Export Filtered CSV button sends is `POST /admin/pricing/downloadexportcsv`**, captured off the wire in the owner's browser. The scope travels in the body, which is why every query string was ignored.

### The body was guessed wrong five times

**Captured by intercepting the portal's own form submit rather than inferred from its bundle.** The bundle gives the field names; it does not give the types, and the types are the part that matters.

| field | inferred | actual |
|---|---|---|
| `PricingType` | `1` | `"Pricing"` |
| `CategoryId` | `89` | `"89"` |
| `SetNameIds` for all | `[]` | `["0"]` |
| `PriceToCompare` | `null` | `3` |
| `ExportLowestListingNotMe` | `false` | `true` |

**Every value is a string, and "all of them" is `["0"]` rather than the empty list.** `0` is the "All Set Names" row's own id, so the portal asks for a filter matching everything rather than for no filter.

**Two fields are never negotiable.** `MyInventory: false` makes it the catalog rather than the operator's current listings, which is what a join exists to add to. `PrintingIds: ["0"]` is All Printings, because a number stocked in several finishes must arrive with all of them or D3 rung 2 decides it from whichever survived.

### The guard flips from a delta to a positive check

**D64 compared a fetch against the run's previous export because nothing better was available.** Three filters narrow an export independently and one leaves no trace in it, so completeness could not be read off the contents.

**A scope this process named can be checked against what arrived.** The question becomes "did I get the sets I asked for", which the file answers. `export_scope_incomplete` refuses rather than warns: a set asked for and absent means every card in it queues as `no_catalog_row`, a whole box silently, from a fetch that reported success.

**There never was a delta guard on the upload path, and the fetch path's was retired 2026-09-02** (D64, amended): the positive check is the whole guard.

### The scope is the claims the operator already made

**A card carries its game and, where the operator set one, a set hint.** A box captured as Riftbound/Unleashed already says which category and which set its export needs, so nothing new is asked of them.

**`match_sets` reads a hint against TCGplayer's own set names in three rules** — case-folded equality, then prefix, then the name's leading token before a colon. Measured on the two the store holds: `UNL` resolves to `Unleashed`, and `ME01` resolves to `ME01: Mega Evolution` across 220 Pokemon sets.

**Substring is deliberately not one of the rules.** `Origins` appears inside `Origins: Proving Grounds`, so a substring test makes every hint naming a base set ambiguous with its own sub-sets and resolves nothing.

**An ambiguous hint matches nothing and the fetch widens to the whole category.** Widening is slower and always correct; narrowing onto a set the box is not in is not. Riftbound entire is 10,118 rows against Unleashed's 2,201, and that is the whole price of being wrong in the safe direction.

### One category per fetch

**`CategoryId` is scalar in the portal's own request, so a mixed-game run fetches once per game.** The request takes `game` and refuses `game_required` when a run holds more than one, naming them. The join composes what the fetches leave behind.

### A refusal that blamed the operator's credential

**The portal answers a malformed request with HTTP 200 carrying an HTML page titled `System Error`, and D64 read any HTML as a login page.** Five different bad bodies were each reported as `tcg_session_expired`, which sends the operator to re-copy a cookie that was working. `tcg_request_rejected` now says the session is fine and the defect is here.

### What it costs

**The category ids are registry data that only the portal knows.** `tcgplayer_category_id` sits beside `product_line` in `pipeline/games.py` — Pokemon 3, One Piece 68, Riftbound 89 — because the two are independent identifiers for the same thing and neither derives from the other.

**This module now makes two calls rather than one.** `getjsonfilters?categoryId=N` reads the vocabulary; without a category it returns one "All Set Names" row and nothing else, which is why it takes the argument.

**The hint vocabulary is not TCGplayer's, and a table is the only bridge.** Measured against the live category lists: `UNL`, `ME01`, `SV05` and `SV09` resolve by shape, while `OGN`, `MEG`, `TEF` and `JTG` — the community short codes — resolve to nothing and widen to every set in the category.

**No derivation rule reaches them.** `MEG` is not a prefix, an initialism or a colon-token of `ME01: Mega Evolution`, and `TEF` is none of those for `SV05: Temporal Forces`. So `set_aliases` sits in the registry beside the game's other hand-authored vocabulary, which is D22's rule for exactly this.

**It is deliberately partial and maps a code to another HINT rather than to an id.** There is no machine-readable source for community codes, so it covers what the owner types and grows as they type more; and resolving `MEG` to `ME01` lets the three shape rules do the matching without the table repeating a full set name that TCGplayer may re-word. An absent alias costs a wider export, never a wrong one.

### The whitelist at capture time

**The capture screen offers the real set names, so a new hint is exact by construction.** `GET /tcg/sets` serves the game's vocabulary and the hint field is a `datalist` over it, with the alias codes listed beside the names so the field is searchable by either.

**A datalist rather than a select, because the rig may not be constrained.** It suggests without restricting: free text still works, and an empty list is indistinguishable from the control before this entry.

**Every failure answers 200 with an empty list and a reason.** No cookie, no network, the portal down — the operator keeps typing. D19 measures this screen's cadence in milliseconds and a hint field that would not open because an autocomplete failed is a worse product than one with no autocomplete.

**And the reason is drawn, because degrading to empty is correct and degrading invisibly is not.** The first build carried the reason on the response and threw it away, so an expired session and a game with no sets produced the identical empty list and silence was the only signal. The session case names `.env`, since it is the one the operator can act on. It stays a note: the field takes text exactly as before.

**`#/runs` already said so and the capture screen did not**, which is the asymmetry worth recording. The fetch refuses with `tcg_session_expired` and the screen renders the sentence verbatim with no control, because re-copying a cookie happens outside the app. The capture screen had no equivalent, and the hint field is the surface an operator touches long before they ever press Fetch.

**The load follows the field being OPEN, not the row being tapped**, which was a real defect caught by its own test. `H` opens the field from the key handler and never reaches the row's `onToggle`, so hanging the load there left the list empty for every operator using the keyboard — which on this screen is all of them.

**`match_sets` stays regardless.** 677 of the store's cards already carry free-text hints and those runs must keep joining; an exact hint costs the matcher nothing, because rule one matches and the other two never run.

### The field had rules and drew none of them (amended 2026-08-31)

**A `datalist` offers a vocabulary and says nothing about the string actually typed.** That is the whole of the defect the owner reported: the hint became a whitelist field above, and the control still looked like the free-text box it replaced. `Spiritforge` and `Spiritforged` are indistinguishable at the rig. They part company an hour of captures later at the fetch — one scopes the export to that set, the other resolves to nothing and widens to the category — and the operator learns which they typed from a row count on a different screen.

**So the field says which of the two it is, while it is being typed.** `app/src/setHint.ts` resolves the hint against the vocabulary the field is already offering and answers in five states: `blank`, `unchecked`, `matched` (with the set, and whether the hint IS its name), `ambiguous`, `unmatched`.

**Two registers, because the Box field beside it already has two.** A terse meta pinned to the right of the entry for the state — that field's own `next 60` / `new box` — and a sentence under the field for what the state means. Nothing here is a new shape; it is the screen's existing grammar applied to the one other free-text field on it.

**It judges and never refuses, which is the rule above unamended.** Every string can still be stored, `unmatched` included; the sentence says what will happen to the hint rather than asking for a different one. Accent at text weight, which is `docs/DESIGN.md`'s "the system is unsure" job — never a halt outline, because nothing is halted.

**`unchecked` is a first-class verdict and the reason the feature is safe.** No cookie, no network, the list not yet fetched: the screen says it cannot tell rather than accusing the operator of a typo it has no way to see. The at-rest row is silent in that state too. An empty vocabulary already had to leave the field working; now it also has to leave it quiet.

**Enter completes a hint that resolved but is not the set's name.** An alias, a prefix or a colon-code scopes the export correctly and is still not the string `pipeline/join.py:set_matches` wants at join time — that matcher folds and compares, with no prefix rule to save it. The keystroke that leaves the field is therefore the one that makes the stored hint exact, which is what "exact by construction" above promised and the `datalist` alone never delivered. It completes nothing that did not resolve.

**The copy is asserted against the original, because a verdict gets trusted where silence did not.** `scripts/set-hint-agreement.py` runs `app/src/setHint.ts` under node against `server/tcg_export.py:match_sets` over 22 hints drawn from this entry's own measured vocabulary, and compares the one fact both stake a claim on: did this hint resolve, and to which set. A screen that says MATCHED where the fetch misses is worse than the field was before this section. This is `scripts/port-agreement.py`'s shape one decision over, and it is off the commit path for the same reason: it runs node.

**What the two sides may still differ on is the shape of a MISS, deliberately.** `match_sets` returns one "missed" list; the screen splits it into `ambiguous` and `unmatched`, because "two sets answer to that — `Origins` and `Origins: Proving Grounds`" is an instruction and "no match" is not. The agreement check reduces both to resolved-or-not, which is the claim that has to hold.


### There were two matchers, and a set code resolved to neither (amended 2026-08-31)

**The paragraph above about Enter completing a hint is overtaken, and the sentence that overtook it is the point.** It said an alias or a prefix "is still not the string `pipeline/join.py:set_matches` wants at join time", and that was true: this repo answered *does this hint name this set* in two places, by two different rules. The fetch had a prefix rule and raw case-folding. The join folded `sv09` and `sv9` together and matched either side of a colon. So a hint could scope the export correctly and then fail to narrow the very rows it had fetched, and the verdict this entry added to the capture screen predicted only the first half of that.

**One ladder now, in `pipeline/setnames.py`, read by both.** Whole label, then either colon side, then a guarded prefix, then an abbreviation. `server/tcg_export.py:match_sets` keeps only what is genuinely its own — mapping a resolved name back to the portal's set id, and dropping the `All Set Names` row before resolution rather than after, since dropped after it makes a real set look ambiguous.

**Merging them fixed a defect that was live and had nothing to do with set codes.** `set_matches` is PAIRWISE — one hint against one name — so it cannot see how many sets answered. Four did: `SV` matches `SV: Prismatic Evolutions`, `SV: Paldean Fates`, `SV: Scarlet & Violet 151` and `SV: Shrouded Fable`, and `Catalog.candidates` handed all four sets' rows back as a confident narrowing with no `set_ambiguous` and no review. Resolution is set-wise now and answers `None` on a tie, so that card reaches a human with its photo (D2, D3). `set_matches` survives as the yes/no question T3 asks of one pair, delegating to the shared ladder.

**A set code is derived from the set's own name, not looked up.** The letters of a short hint, in order, anchored on the first, running through the name with any block code taken off the front: `SFD` finds Spiritforged, `OGN` Origins, `VEN` Vendetta, `TEF` Temporal Forces, `JTG` Journey Together. There is no rule that yields the ONE official code — `TEF` is two letters of Temporal plus one of Forces, `SFD` is a squeeze of a single word, `OGN` skips two letters and keeps a third — so every ordered squeeze is accepted and ambiguity throws out the ones answering to more than one set.

**THE RULE NEVER HAS TO KNOW WHICH SQUEEZE IS OFFICIAL, AND THAT IS THE PROPERTY THAT SAVED THIS SECTION FROM ITS AUTHOR.** An earlier draft named `VDT` as Vendetta's code. It is not; `VEN` is, and `VDT` was a session pattern-matching three consonants out of a set name and then citing itself. Because the rule accepts every ordered squeeze, both strings resolve to Vendetta and no code changed — but the entry asserted a fact about the world that nothing had checked, which is precisely what D22 exists to stop, and it did so two paragraphs after arguing that scraping was unnecessary because no source had to be trusted.

**The alternative was scraping a code table, and BOTH halves of the argument against it were wrong.** The claim was that a scrape yields only *code to community name*, and that the second hop — community name to TCGplayer's own label — is published nowhere. It is published: `https://tcgcsv.com/tcgplayer/<category>/groups` serves TCGplayer's own group names, unauthenticated, and this repo already vendors fixtures from that host. Measured against it on 2026-08-31, the derivation covers **6 of 7 Riftbound codes and 13 of 22 Pokémon SV01-onwards codes**. It is a good reduction of the table, not a replacement for it, and the session that argued otherwise had never looked at a full-size vocabulary.

**Three of the four hand-authored alias rows are dead and the fourth is load-bearing** — `TEF`, `JTG` and `OGN` derive; `MEG` does not, because `ME: Mega Evolution Promo`, `ME01: Mega Evolution` and `MEE: Mega Evolution Energies` all answer to it and a tie widens. An earlier draft of this paragraph called all four dead, having measured against an eight-set list assembled by hand; against TCGplayer's real 29 SV/ME sets that is false. The dead rows are kept anyway: D22 makes the table the owner's, and a row costs a dictionary lookup.

**Every miss at full scale is a TIE, and not one code resolved to the wrong set.** Nine Pokémon codes and one Riftbound code need a row, and each is a code answering to two or more sets — `PAL` to Paldea Evolved and Paldean Fates, `MEG` to the three Mega Evolution groups, `SCR` to Stellar Crown and the four `Scarlet & Violet` ones. That is the failure this rule was designed to have: the export widens, which is slower and cannot miss a card.

**Two guards, both measured before either rule was written.** The abbreviation is capped at four characters, because uncapped it silently resolves `Spiritfoged`, `Vendeta` and `Orgins` to their intended sets — which sounds like a feature until you notice almost every string then "names a set" and the typo warning this section added never fires again. And a prefix may not split a number: `unl` is Unleashed and `sv` is every SV set, but `sv1` is not `SV19`, which `harness/tests/t3_join_coverage.py` asserted long before the two matchers met.

**What bounds the damage is the rule's position and the game picker, and the measurement says so — but read what the measurement was over.** The abbreviation is tried last, so it can never take a hint that already resolves. Against the real committed export lists, judged within the game the operator has already chosen, thirteen of thirteen strings resolved to the intended set and none resolved wrongly. **Seven of those thirteen are codes with a source** — typed by the owner, or already hand-authored in `set_aliases`, or carried by store records. **The other six were chosen by the session to exercise the rule's shapes** and are not evidence that anybody types them. The number is a claim about the MATCHER and not about the vocabulary; a claim about the vocabulary needs the owner or the rig, and this entry does not make one. The only way it returns the WRONG set is for the operator's own set to be missing from TCGplayer's list — if their set is there, the code either finds it or ties with another, and a tie widens. An earlier draft of this section quoted a one-in-twelve error rate; that number was measured across games, typing Pokémon codes at a Riftbound vocabulary, which the game picker makes unreachable. It is recorded here because the wrong measurement nearly bought a worse design.

**Measured at full size on 2026-08-31, after this entry twice recorded a number taken off the fixtures.** TCGplayer lists 12 Riftbound groups and 29 Pokémon SV/ME ones. Ties do become commoner with scale, exactly as predicted, and the failure that grows is the rule declining to fire rather than answering wrongly — the wrong-set count at full size is zero. What the fixtures could not have shown is how MUCH commoner: nine of twenty-two Pokémon codes tie, which is what turns the hand-authored table from a legacy into a live requirement.

**One wrong answer does exist, and it is older than the abbreviation rule.** `SP` is Riftbound's Special collection, TCGplayer lists no such set, and `SP` resolves to `Spiritforged` by the PREFIX rule — which has answered that way since `match_sets` shipped. It is left alone: narrowing prefix would take `UNL` and `VEN` with it, and both are real codes for sets TCGplayer does list.
---
