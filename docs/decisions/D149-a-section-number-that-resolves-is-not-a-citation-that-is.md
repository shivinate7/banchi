## D149 — A section number that resolves is not a citation that is right, and no check can read what a sentence is about

**Seven citations across five files named §11 for a record that has only ever been in section 8.** Repaired by hand 2026-09-11. The repair is two characters per site; what is decided here is that **no `docs-audit` row will be built to catch the next one**, and the measurement behind that.

### The five files, and the two that were nearly broken with them

Wrong, all citing section 11 for the one-in-thirteen `design-check` flake, which is section 8's: `CLAUDE.md:174`, `Makefile:835`, `.github/workflows/check.yml:81` and `:246`, and `docs/DECISIONS.md:9522`, `:9553` (D136) and `:10084` (D141).

**Nine other sites cite section 11 and are RIGHT** — not merely untouched: every one is about the capture server's concurrency, which is what section 11 is. They are `CLAUDE.md:916` and `:932`, `docs/DECISIONS.md:6111`, `docs/map.py:2483`, `harness/tests/t7_store_and_seams.py:21593`, `scripts/docs-audit.py:2456` and `:2509`, `scripts/serve.py:1393`, and `server/capture_server.py:10196` and `:11049`. **A blanket find-and-replace would have broken nine to fix seven**, and not one of the nine quotes anything distinctive, so nothing in the text separates them from the wrong ones. The repair was per-site and subject-checked.

**The count was wrong three times before it was right, and every miss was a search pattern too narrow.** Five sites, from a `§`-only search over three globs. Then seven, by searching both spellings over the whole tree — `Makefile:835` and `docs/DECISIONS.md:10084` say `section 11` and a `§`-scoped search cannot see them. Then a reviewer put the population at nine and the correct sites at two, from `DEBTS\.md ?(§|section )11` — which requires nothing between the filename and the reference and so misses every site spelling it `` §11 ``, backticks included.

**The population is 16, and the pattern that finds all of it is `DEBTS\.md`? ?(§|section )11`** — seven wrong, nine correct, the nine being `CLAUDE.md:916` and `:932`, `docs/DECISIONS.md:6111`, `docs/map.py:2483`, `harness/tests/t7_store_and_seams.py:21593`, `scripts/docs-audit.py:2456` and `:2509`, `scripts/serve.py:1393`, and `server/capture_server.py:10196` and `:11049`. **A citation of this file is spelled three ways** — `§11`, `section 11`, and either of those behind a backticked filename — which is worth more to the next session than the count is, because the count is what three searches got wrong.

### It was copied, not renumbered, and only one of those argues for a row

The obvious hypothesis is D80's: a section was renumbered and every citation went stale pointing at a real section. **It is not what happened, and the history settles it rather than suggesting it.** The flake record entered `docs/DEBTS.md` in `86e70c2` already under §8, on a tree where §11 was already the capture-server section. Across every revision of that file, §11 has carried two wordings of one subject and the flake record has only ever been in §8. The first wrong citation and three copies landed in ONE commit, `e06eb8a` (D136), across three files; `bc39785` (D141) copied it into two more and the Makefile took it from the same source.

**That file does not renumber, and section 15 is the proof**: closed 2026-09-07 by deleting the heading and leaving 16 to 24 in place. So a renumber guard — the row this would otherwise argue for — would have caught none of the seven, and the hazard it guards is structurally absent in the one file at issue.

**What this was instead is a copying failure**, and the reason it survived is that a wrong section number *still resolves*: section 11 is a coherent thing for a CI comment about worker counts to cite. It is `docs/map.py`'s rule about step ids — *"a renumber leaves every one pointing at a real step that is not the one meant — which nothing can detect"* — reaching a second file by a second route.

### Why no row, measured

A row would have to decide what a sentence is ABOUT. The nearest mechanical proxy is the discipline §1 already established when `server concurrency` passed with both its constants inverted: require an **attributed form**, and compare a phrase the citation quotes against the section it names. **Measured over all 38 citations of a `docs/DEBTS.md` section in this tree, 15 files and 11 sections: four carry a double-quoted span at all, two of those are really quotations, one resolves true, and the rule would have caught one of the seven while raising three false alarms** — the other spans being a code flag, an f-string fragment and a slice of the checker's own error text. This repo's prose cites by narrating, not by quoting.

**And the most-repeated token cannot be matched literally**: five of the seven say `one-in-thirteen`; the file spells it `1 in 13` in a table cell, so a containment test flags the REPAIRED text too. The remaining option is a hand-maintained (phrase → section) list, which is section 4's subject — a claim whose reader is itself unread — and is not built. Recorded in §25 rather than half-built, which is the ruling the owner asked for by name.

### One reader was made whole, and it did get a guard — over shape, not over meaning

`scripts/docs-audit.py:_debts_section` matches `## <n> — ` and returns None otherwise, and **both** its consumers tolerate a None — one with `or ""`, one with an early return. So sections 20 to 24, written `## <n>. `, were not a failure anywhere: they were five of that file's twenty-three live sections **silently not existing**, with every row green throughout. The headings are normalized here.

**`make docs-audit`'s `debts headings` row is the guard that keeps them that way**, and it can be built for exactly the reason the citation-subject row cannot: a heading either parses or it does not. It refuses a heading that is not `## <n> — <title>` and a section number used twice, the second being the same defect wearing a different hat — `_debts_section` returns the first match, so the second section is unreachable. Mutation-tested with four arms: the dotted form, a duplicate number, a number with no title, and an en-dash for the em-dash. All four fire; the baseline is clean.

### A probe that cannot express a failure is the purest form of this

**This entry's own verification had the defect the entry is about, and it took two rounds to see.** The first probe read `r['name']` and `r['status']` where `scripts/docs-audit.py --json` emits `label`, `severity` and `findings`. Every row therefore read as ok, the audit was reported clean three times, and the reading was worth nothing — `make check`'s exit code was the only real signal in play. Re-running it with the right keys immediately surfaced a genuine `repo map` finding the broken probe had been hiding.

**That is worse than a check with a gap, and it is the same shape as the five unreadable headings above.** A guard that is too narrow measures something adjacent to what it claims. A probe keyed to fields that do not exist measures NOTHING, and nothing renders as clean — which is why `_debts_section` returning None for an unparseable heading was never a failure anywhere, and why three separate searches for these citations each reported a population smaller than the real one and each read as complete. **A pattern that finds nothing reports nothing, and nothing reads as green.** The countermeasure is the one this repo already applies to its rows and did not apply to a throwaway probe: make it fail once, on purpose, before believing it.

**This is the distinction the whole entry turns on.** A guard over a document's SHAPE is mechanical and cheap. A guard over what a sentence MEANS is neither, and the measurement above is what that costs. The first is built; the second is recorded and declined.
