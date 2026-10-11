## D60 — Docs cite; identifiers use American spelling

**The referenced docs are read on demand, not loaded in full. Their prose is dense American technical English.** The owner ruled that the prose be rewritten denser.

`CLAUDE.md` `@`-referenced the decisions file, `docs/GATES.md` and `docs/DESIGN.md`. All four entered context in every checkout, on every turn. That measured 635,411 bytes, about 165,000 tokens.

**The `@`-references are gone.** Rewriting twenty entries moved the four docs from 635,411 to 627,725 bytes. That is about 2,000 tokens. These files are ~85% identifiers, paths, measurements and dates. Only ~15% is rhetorical framing. Dropping the prefix moves the figure to **~7,700 tokens**. The two are not close enough to argue about.

**What replaces the load.** `scripts/decision-context.py` names the governing decisions before any edit under the mapped directories. That covers the edit path. The conversational path (an architecture question with no file open) is covered by the rendered index, `make map ARGS=--decisions`.

**The index is a table of contents, never a substitute for the entry.** `CLAUDE.md` still says to read the entry before proposing an architecture change. That costs a `Read` now, where it cost nothing before. That is the trade. The file is one tool call away rather than already present.

**The cite rule is narrowed, not kept whole.** The old rule assumed that the cited entry was already in context. It no longer is, so a reader who follows a citation pays a `Read`. The rule becomes: **do not re-derive a cited entry's reasoning, but do say how it bears here.** An entry must still stand up read alone.

### The rule

- **An entry opens with a bold sentence stating its ruling.** One line, over twelve characters, ending in a period.
- **American standard technical English.** Declarative. No rhetorical framing, no declamatory capitals, no chains of em-dash asides.
- **Structure carries what signposting used to.** Headings, tables and lists.
- **Quote the owner only as evidence, never as decoration.**
- **Cite, do not restate.**

### Why the opening sentence is a rule and not a preference

`scripts/decision-context.py` builds each entry's summary from its bold runs. It ranks sentences ahead of labels and takes the first three. An entry that opens with a title or cross-reference gives the hook little to read.

That hook reads per line. A bold run split across a wrap is invisible to it. These documents wrap at 96 columns, so a long bold run can be lost silently, with `make docs-audit` green throughout. Short single-line bold sentences prevent that.

### Cite, do not restate

**A short citation does real work in one clause and is kept.** *D10 makes their gaps permanent* and *D18's rule: it writes* are the form.

**Cut the paragraph that re-argues an entry it cites.** Keep how a cited rule bears on this entry. Cut the re-derivation of why that rule exists.

**Two limits on cutting one.** A removed citation must leave at least one `D<n>` token wherever `docs/map.py` names the entry in `governed_by`. It must not remove the last mention the audit resolves.

### The structural invariants

**Breaking the hook is silent, and breaking the audit is loud. So the silent half needs a guard.** `scripts/prose-guard.py` is that guard. It is wired into `scripts/docs-audit.py` as the `decision structure` row.

These are frozen, because a parser reads them. The `## D<n> — <title>` heading, with its dash separator. `docs/GATES.md`'s seven pass-criteria sentences, word for word. Its `### Tn` headings. Its `Gate X … PASSED` heading lines, and every line there beginning with a digit and a period. `docs/DESIGN.md`'s `## Tokens` heading, with the first fenced block under it, and its two parenthesized reason-code lists.

**Three phrasings fail a commit, and they are easy to write by accident.** A sentence naming an audit row by its position rather than its label. An unbalanced fence, which reclassifies every later prose line as code. And an ordinary English phrase beginning *make* placed inside backticks, which reads as a Makefile target.

### Evidence is never reworded

**`docs/GATES.md`'s gate sections are exempt from this entry.** That file rules that its numbers are evidence about a run on a date. They are never rewritten. Gate A, Gate B, Box 2 and Gate C stay as written.

### The budget

**A new entry's size is reported.** A rewrite alone does not hold the budget. Growth comes from new entries, so each one's size is printed.

`entry budget` is **advisory**. It prints and allows. A long entry is a judgement call, not something provably wrong. D16's test for what may block applies. A blocking row here would teach `--no-verify`, which takes the three opsec rules with it.

### What this is not

**It is editing for concision, not generation.** D18's seam list stays empty, and this does not open it. Nothing here is derived from a constant, and no argument is computed.

**It is not license to cut reasoning.** D16 forbids editing a document to satisfy a gate. The budget row is advisory, so it can never become one.

**What would reopen this: a session that reasons from the index alone.** The index names every entry and argues none of them. If decisions start being cited from their titles, or re-litigated because nobody opened the entry, the answer is not a longer index. The answer is a louder instruction, and `CLAUDE.md` is where it would go.

### Identifiers are spelled American, repo-wide

**Identifiers use American spelling.** Comments, docstrings, string literals and markdown outside the four docs this entry governs are not rewritten. The owner ruled this during the D133 reversal interview. The trigger was `server/pipeline_routes.py:_artefacts`, found beside docs this entry rules American. The walk also found the decisions file flipping between the two spellings across PRs #65 and #110.

**Measured before the ruling, over 291 tracked source and markdown files:** 1,580 British spellings in 198 files. Of these, 869 are in comments and docstrings across 169 files. 289 are in markdown across 23. 119 are in identifiers across 24. The rest are in string literals. The American side already held wherever the language itself has a say: 1,405 `color` and 463 `center` in CSS, 951 `fulfill`, 868 `catalog`.

**Why the ruling stopped at identifiers.** Mixed spelling in prose costs nothing at read time. A model reads `artefact` and `artifact` as one word. A grep does not. A search for `artifact` never found `_artefacts`. A search for `fulfillment` in the store never found the `fulfilment` table. Such a search returns half the sites and looks complete. That hazard exists only for names, so names are what the ruling covers. The full sweep was declined by name. It would touch 198 files against five open PRs and sixteen live worktrees. It would also rewrite text in this file and in `docs/GATES.md`, whose only job is to be a record.

**Two names are out of scope, by name, with the reason recorded.** `fulfilment` is a table in `inventory/store.sqlite` and the ledger payload key the legacy-JSON migration reads (D88). `catalogued` is the game registry key in `pipeline/games.py`. It is a field on the wire in `GET /games`, and the stem of the `not_catalogued` reason code. A rename of either is a migration, not a spelling. Their relatives (`is_catalogued`, `NotCatalogued`, `_parse_fulfilment`) stay with them, so no file is split between spellings. `aria-labelledby` is the platform's own name and is allow-listed for the same reason.

**The reader is the `identifier spelling` row, which blocks, in `scripts/docs-audit.py`.** It reads every tracked `.py`, `.ts`, `.tsx`, `.mjs`, `.sh` and `.css`. It blanks comments, docstrings, strings, template literals, regex literals and JSX text, byte for byte, before reading a token. It names the American form in every finding. Its -ise stems are a closed list, because an open pattern flags `raise`, `Promise` and `otherwise`. A miss is the cheaper error on a blocking row. `SPELLING_ALLOWED` is the allow-list, each entry a name with its reason. It is mutation-tested under `--self-test`, in both directions per language. A British name is found in each of the six file kinds. The same word in a comment, a string, a regex, JSX text or a docstring is not. A template literal's `${}` is read. A generic parameter list is not mistaken for a tag. An allow-listed stem passes, and the tree is clean.

**What landed with it.** The 119 identifiers renamed in place across 24 files include `_artefacts` to `_artifacts`, `summarise` to `summarize`, and `humanise` to `humanize`. They also include `_normalise_origin`, the `cancelled` flags, and the test locals. The three documents that named `_artefacts` followed it.

### Vale is retired

The owner ruled Vale retired (L3) and American spelling kept in docs-audit. The `identifier spelling` row reads code only. It does not read markdown prose for spelling. That half is lane L2's work, and it waits on the owner. Until L2 lands, markdown prose has no spelling reader.

### The index is rendered, not hand-typed

**CLAUDE.md's hand-typed index is retired. `make map ARGS=--decisions` replaces it.** A hand-typed index drifts as the corpus grows. A rendered view cannot drift, because no second copy of the corpus's headings exists to disagree with it. `scripts/index-decisions.py` no longer writes CLAUDE.md at merge time. It only folds a claimed branch's entry into `docs/decisions/ORDER.json`, the manifest half a rendered view still needs. No `docs-audit` row checks the index now, since there is no second copy left to check.

The conversational-path argument above is unchanged. Only its premise moved: the index is now a command, not a paragraph in this file.

---

Prose is measured in errors per 1,000 words, never bytes. The linter is vendored, not symlinked.
