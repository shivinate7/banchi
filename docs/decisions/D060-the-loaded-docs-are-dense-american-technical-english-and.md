## D60 — The @-loaded docs are dense American technical English, and an entry cites rather than restates

**The three referenced docs are read on demand rather than loaded in full, and their prose is dense American technical English.** Built 2026-08-30, on the owner's instruction to rewrite the prose denser; amended the same day when the measurement showed where the cost actually was.

`CLAUDE.md` `@`-references `docs/DECISIONS.md`, `docs/GATES.md` and `docs/DESIGN.md`, so all four enter context in every checkout, on every turn, before a word of work. Measured the day this landed: **635,411 bytes, roughly 165,000 tokens.**

**The `@`-references are gone, and that is the amendment.** They stayed at first, on the owner's call and against the alternative of an index. What changed is the measurement: rewriting twenty entries moved the four docs 635,411 -> 627,725 bytes, about 2,000 tokens, because these files are ~85% identifiers, paths, measurements and dates and only ~15% rhetorical framing. Dropping the prefix moves the same figure to **~7,700 tokens**, and the two are not close enough to argue about.

**What replaces the load, because a session must not fly blind.** `scripts/decision-context.py` already names the governing decisions before any edit under the mapped directories, and D60's own reflow is what made it see every bold in the file. That covers the edit path. The conversational path — an architecture question with no file open — is covered by the index in `CLAUDE.md`: 60 lines, 3,929 bytes, one line per entry.

**The index is a table of contents and never a substitute for the entry.** `CLAUDE.md` still says to read the entry itself before proposing an architecture change, and that instruction now costs a `Read` where it used to cost nothing. That is the trade, stated plainly: the file is one tool call away rather than already present.

**`decision index` is a blocking audit row, because an index that has drifted is worse than none.** It is believed — D17's argument for auditing `docs/map.py` exactly as hard as it is trusted. It compares ids, titles and order against the headings, which are the source. Mutation-tested three ways: a drifted title, a dropped entry, and a new heading nobody indexed.

**It is not a generator and does not open D18's seam list.** The row computes what the index should say and compares; it never writes. That is D18's own write-time versus check-time split with only the check half built, and the seam list stays empty.

**Cite-don't-restate loses its premise and is narrowed rather than kept.** That rule rested on the cited entry being already in context, which is now false — a reader who follows a citation pays a `Read`. In practice little moves, because the pass that landed was overwhelmingly register rather than deletion: no entry had its argument cut in favor of a pointer. What the rule becomes is the weaker and more honest form — **do not re-derive a cited entry's reasoning, but do say how it bears here**, which is the half that was doing the work anyway. An entry must still stand up read alone.

### The rule

- **An entry opens with a bold sentence stating its ruling.** One line, over twelve characters, ending in a period.
- **American standard technical English.** Declarative. No rhetorical framing, no declamatory capitals, no chains of em-dash asides.
- **Structure carries what signposting used to.** Headings, tables and lists.
- **The owner is quoted as evidence, never as decoration.**
- **Cite, do not restate.**

### Why the opening sentence is a rule and not a preference

`scripts/decision-context.py` builds each entry's summary from its bold runs, ranking sentences ahead of labels and taking the first three. Measured before this landed: **36 of 59 entries led with a ruling, 16 led with a cross-reference or an amendment note, and 7 gave the hook nothing but their title** — D1, D4, D5, D6, D8, D11 and D14.

**That hook reads per line, so a bold run split across a wrap is invisible to it.** These documents wrap at 96 columns, and **270 bold runs — 20% of all 1,318 — were lost that way**, silently, with `make docs-audit` green throughout. Short single-line bold sentences are what fix it.

### Cite, do not restate

**A short citation does real work in one clause and is kept.** *D10 makes their gaps permanent* and *D18's rule: it writes* are the form.

**What goes is the paragraph that re-argues an entry it cites.** Measured at **94 paragraphs over 600 bytes, 77,811 bytes**, across 433 cross-references. Keep how a cited rule bears on this entry; cut the re-derivation of why that rule exists.

**Two limits on cutting one.** A removed citation must leave at least one `D<n>` token wherever `docs/map.py` names the entry in `governed_by`, and must not remove the last mention the audit resolves.

### The structural invariants

**Breaking the hook is silent and breaking the audit is loud, so the silent half is the one that needs a guard.** `scripts/prose-guard.py` is that guard, wired into `scripts/docs-audit.py` as the `decision structure` row.

Frozen because a parser reads them: the `## D<n> — <title>` heading with its dash separator; `docs/GATES.md`'s seven pass-criteria sentences, word for word; its `### Tn` headings, its `Gate X … PASSED` heading lines and every line there beginning with a digit and a period; `docs/DESIGN.md`'s `## Tokens` heading with the first fenced block under it, and its two parenthesized reason-code lists.

**Three phrasings fail a commit and are easy to write by accident.** A sentence naming an audit row by its position rather than its label. An unbalanced fence, which reclassifies every later prose line as code. And an ordinary English phrase beginning *make* placed inside backticks, which reads as a Makefile target.

### Evidence is never reworded

**`docs/GATES.md`'s gate sections are exempt from this entry.** That file rules that its numbers are evidence about a run on a date and are never rewritten, and this rewrite does not touch Gate A, Gate B, Box 2 or Gate C.

### The budget

**A rewrite alone does not hold, which is why the size of a new entry is reported.** Growth over the two days before this landed was **+45,580 and +44,460 tokens**, and **80% of it was new entries** — 21 of them, averaging 11.6KB. A 49% cut is spent in under two days at that rate.

`entry budget` is **advisory**, printing and allowing. A long entry is a judgement call rather than something provably wrong, which is D16's test for what may block; and a blocking row here would teach `--no-verify`, which takes the three opsec rules with it.

### What this is not

**It is editing for concision, not generation.** D18's seam list stays empty and this does not open it. Nothing here is derived from a constant, and no argument is computed.

**It is not license to cut reasoning.** D16 forbids editing a document to satisfy a gate, and the budget row is advisory so that it can never become one.

**What would reopen this: a session that reasons from the index alone.** The index names 60 entries and argues none of them. If decisions start being cited from their titles — or worse, re-litigated because nobody opened the entry — the honest answer is not a longer index but a louder instruction, and `CLAUDE.md` is where it would go.

### Amended 2026-09-11 — every identifier is American, and prose outside these four docs is not governed

**Every identifier in the repository is spelled American; comments, docstrings, string literals and markdown outside the four docs this entry already governs are left as they are.** Ruled by the owner on 2026-09-11 during the D133 reversal interview, after `server/pipeline_routes.py:_artefacts` was found beside docs this entry rules American, and after the walk found `docs/DECISIONS.md` itself flipping the word between the two spellings across PRs #65 and #110.

**Measured before the ruling, over 291 tracked source and markdown files.** 1,580 British spellings in 198 files: 869 in comments and docstrings across 169 files, 289 in markdown across 23, 119 in identifiers across 24, and the rest in string literals. The American side already held wherever the language itself has a say — 1,405 `color` and 463 `center` in CSS, 951 `fulfill`, 868 `catalog`.

**Why the ruling stopped at identifiers.** The owner's question was whether standardizing had value at all, the worry being that mixed spelling might one day confuse a model reading the code. It does not: a model reads `artefact` and `artifact` as one word, so mixed prose costs nothing at read time. A grep does not. A search for `artifact` never found `_artefacts`, and a session reading `Fulfillment.tsx` and then searching the store for `fulfillment` never found the `fulfilment` table — a search that returns half the sites and looks complete. That hazard exists only for names, so names are what the ruling covers. The full sweep was declined by name: 198 files against five open PRs and sixteen live worktrees, and a rewrite of text in this file and in `docs/GATES.md` whose only job is to be a record.

**Two names are out of scope, by name, with the reason recorded.** `fulfilment` is a table in `inventory/store.sqlite` and the ledger payload key the legacy-JSON migration reads (D88). `catalogued` is the game registry key in `pipeline/games.py`, a field on the wire in `GET /games`, and the stem of the `not_catalogued` reason code. A rename of either is a migration, not a spelling. Their relatives — `is_catalogued`, `NotCatalogued`, `_parse_fulfilment` — stay with them so no file is split between spellings. `aria-labelledby` is the platform's own name and is allow-listed for the same reason.

**The reader is `identifier spelling`, a blocking row in `scripts/docs-audit.py`.** It reads every tracked `.py`, `.ts`, `.tsx`, `.mjs`, `.sh` and `.css`; blanks comments, docstrings, strings, template literals, regex literals and JSX text byte for byte before a token is read; and names the American form in every finding. Its -ise stems are a closed list, because an open pattern flags `raise`, `Promise` and `otherwise`, and a miss is the cheaper error on a row that blocks. `SPELLING_ALLOWED` is the allow-list, each entry a name with its reason. Vale's `AmericanSpelling` rule keeps its advisory watch over markdown and is unchanged. Mutation-tested under `--self-test`, in both directions per language: a British name is found in each of the six file kinds, the same word in a comment, a string, a regex, JSX text and a docstring is not, a template literal's `${}` is read, a generic parameter list is not mistaken for a tag, an allow-listed stem passes, and the tree is clean.

**What landed with it.** The 119 identifiers renamed in place across 24 files — `_artefacts` to `_artifacts`, `summarise` to `summarize`, `humanise` to `humanize`, `_normalise_origin`, the `cancelled` flags, the test locals — and the three documents that named `_artefacts` following it.

---
