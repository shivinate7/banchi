## D280 — Offender lists replace pinned counts

**Ruling: no pinned count survives in the docs audit. Each rule keeps its reader and gains a shrinking list of offenders.** The owner retired D284's word ceiling, because a pin that no person moves goes stale. D284 carried out that ruling. The owner then applied it to the other pinned counts. This entry replaces them all. It supersedes the ratchet parts of D218 and D60. Each of those entries names what stays.

- D218's typed-dot ratchet. The `typed interpunct` row failed only when the count of typed dots rose past a pinned number.
- The per-file prose ratchet. The `ste ratchet` row failed only when a file's error ratio rose past its own pin. It amended D60, so the ratchet half of D60 goes too.
- The line-anchor pin (D245). See "The line-anchor pin becomes a list" below.

### Why a count fails

A count passes a new defect when an old one leaves in the same change. Fix one typed dot and type a new one, and the count holds still. Rewrite one bad sentence and write a new one, and the ratio can fall. The pin reported "no change" on both. The owner wanted the new defect to fail. A pin also needs a person to move it. The old scripts wrote a new number on request, and nothing asked why.

### What replaces each pin

Each list has the shape of `scripts/kit-adoption-allow.json`: file, then rule, then entries, with the lane that owes the fix.

- **Typed dots.** `scripts/typed-interpunct-allow.json` lists each offending string in each file, as `scripts/user-strings.mjs` extracts it. The rule key is `interpunct`. D218's two extractor widenings stay as they were.
- **Prose.** The prose list is cut. See "The prose list is cut" below.

**The key is the offender, never a number.** A typed-dot entry is `<scope>: <string>`. The scope is the named function, class, arrow binding or module-level constant around the string. A nested scope is named with the scope around it, as `Outer.helper`. One entry excuses one string in one place. A bare `·` typed in another component is a new offender. An offender that occurs twice in one file is listed twice, so a copy needs its own entry.

### The three failures

1. **An offender the list does not name.** This includes a new offender in a file the list already names. A listed file excuses its listed strings and nothing else.
2. **A stale entry.** A listed entry that matches nothing shows the fix landed. The lane deletes the entry in the same commit. The `make offenders-prune` command does the delete (see below).
3. **Growth.** Each row reads its list as it stood at the merge-base with `origin/main`. It uses `git merge-base` and `git show`, two reads, so D18 holds. An entry that the old list did not hold is refused. The exception is a rule that the merge-base does not define. A rule born on the branch may list its first offenders. If a rule the merge-base defines is gone at HEAD, all growth is refused. Otherwise a renamed rule could bring back every old offender as new. The read fails open, and prints why, when there is no merge-base or no list at the merge-base.

Typed-dot growth is counted per file, by the string without its scope. A dot string is short and repeats across files. Counted over the whole list, a dot fixed in one file would excuse the same string elsewhere. That includes a new file. So each file at HEAD is compared with its own path at the merge-base. The row maps a renamed file back to its old path through git's rename pairs. It reads `git diff -M --name-status` from the merge-base, using `offenders-prune.py`'s own `git_renames`. That is a read, so D18 holds. The scope stays in the unlisted and stale check. So a function rename moves its entries, as a file rename does. The rename is red until the entries are re-keyed to the new name. After the re-key, the row passes, because the same strings occur the same number of times. The pruner does not re-key a scope, because it cannot tell a rename from a move. The re-key is a hand edit, and the diff shows it.

### A new file starts clean

A new file is not in the list at the merge-base. So any entry for it is growth, and the row refuses it. The one exception is a sentence that left another file in the same branch. A new component with a typed dot has no exception. A file that git renamed is not new. Its entries map back to the old path.

### A sentence keeps its identity through edits that do not change its prose

- **A reflow.** Whitespace collapses before the hash. The vendored linter masks a code span per line. The `decision citation` and `VS Code` exemptions read the finding's own line. So before the hash, the lines that one such span runs across join into one line (`join_span_breaks` in `scripts/ste_measure.py`). The same sentence then gives the same findings and the same hash, wherever its line breaks fall.
- **An edit inside a code span.** The hash reads the linter's masked text, where a code span is one placeholder. This holds for a code span that crosses a line break too.
- **A claim.** `make merge` turns each slug into a number, in every file, in the commit that merges it (D140). The hash folds every decision id first, so the claim moves no identity. The claim also renames a slug entry's file. A decision entry is keyed by the tail of its file name, `docs/decisions/*-<slug>.md`, which holds no id for the claim to rewrite.

Any other edit to an offending sentence gives it a new identity. So a lane that edits a listed sentence must also fix it. The old entry goes stale. The new text cannot be listed, because that is growth.

### What the lists held on the day they were born

Each list was seeded from the offenders on the integration branch, measured, not typed.

- **Typed dots:** 47 strings in 3 files. `Gallery.tsx` holds 45, owned by `kit-frame`. `PositionBar.tsx` holds 1, owned by `locating`. `RunsComposer.tsx` holds 1, owned by `b-runs`. Each was keyed again with its scope when the scope joined the key. The 47 strings are unchanged.

### The stale-only pruner

A stale entry must be deleted. The lists hold thousands of hashes, so a hand delete is slow, and a merge conflict in one is worse. `make offenders-prune` (`scripts/offenders-prune.py`) makes two edits and no others.

- **It deletes a stale entry.** It deletes one occurrence for each occurrence the tree no longer has.
- **It re-keys a renamed file.** A listed file key that names no file today moves to the one new path git's rename detection names. It reads `git diff -M` from the merge-base with `origin/main`. A rename onto a key the list already holds is refused and named.

It never adds an entry. It refuses to write a plan that holds any identity more often than the list it read. A list that is not JSON, such as one with merge-conflict markers, is not pruned. The pruner prints the recipe and writes nothing. The recipe: keep either side's list whole, then run the pruner. That works because the list only shrinks. The pruner reads with the rows' own functions, so the pruner and the gate agree on what is stale. It previews by default. `ARGS=--write` applies. It is on no hook and in no `make check`, because D18 says a generator may write and nothing that writes may gate a commit. It writes data files under `scripts/` only, so it opens no seam in D18's list. `make offenders-prune-selftest` proves it.

The rows read tracked files only. `markdown_files()` in `scripts/docs_audit/core.py` reads the index in staged mode and `git ls-files` otherwise. A scratch `.md` file that git does not track never fails `make docs-audit`.

### What this cannot see

- A label can drift from its sentence when a claim rewrites the label's text. Only the hash is compared, so the drift is harmless.
- A slug entry whose file name is longer than its slug keys to a different tail after the claim. None exists today.
- A decision cited by its path in plain prose, outside a code span, changes its text at the claim. The fold does not reach it. The repo rule is to cite by id, never by path.
- D218's own gaps stay: a separator built without `.join`, a CSS `content:` string, and server-side Python strings.
- Only code spans, decision citations and `VS Code` join across a line break. A link, an HTML tag or a URL that crosses a line break is still masked one line at a time. So a reflow into or out of such a construct can change a sentence's hash.
- A code span is paired as the linter pairs it: each backtick opens or closes one span. A double-backtick span that holds one backtick is read wrong on every layout alike, so it moves no identity.
- A typed dot moved to another place inside the same named function stays excused. The scope is the function, never the line, because a line number rots on the next edit above it.
- A typed dot moved to another function in the same file, with its entry re-keyed by hand, passes. Growth drops the scope so a rename can pass, and a move looks the same. The row is red until the hand re-key, and the re-key is in the diff.
- A file rename that git does not see reads as a new file. That includes a plain `mv` that is not staged. The row then refuses its entries as growth, until the rename is staged. It fails closed.
- A prose sentence fixed in one file still excuses the same sentence, with the same hash, in another file. Prose growth stays whole-list, so a moved paragraph adds nothing.
- Two helpers with one name, in two sibling blocks of the same function, share one scope.
- A file split in two gives git one rename pair, so the second new file reads as new. A typed dot moved into it is refused as growth, even with its entry moved. It fails closed.
- The pruner cannot re-key a rename that git does not see. That includes an unstaged plain `mv`, and a move with too large an edit for rename detection. The old entries go stale and are deleted, and the new file's offenders stay unlisted.
- `kit-adoption.mjs` needs `python3` for its growth check. If the helper cannot run, the check refuses all growth. It fails closed.
- If `scripts/docs-audit.py` cannot load the helper, the offender rows do not compare growth. They fail open and print why, as they do with no merge-base.
- A line anchor inside a code fence is listed too. The rule counts every anchor, as its pin did.
- A markdown file that git does not track is not read until `git add`. The pre-commit hook reads the index, so a commit still carries every file it names.

### Mechanism

`make docs-audit`'s `typed interpunct` and `line anchor offenders` rows, in `scripts/docs-audit.py`. `scripts/only_shrinks.py` decides growth for both and for `make kit-adoption`. `python3 scripts/only_shrinks.py --self-test` proves it. `python3 scripts/docs-audit.py --self-test` proves each failure red in memory. It covers a new offender in a listed file, a stale entry, growth under an existing rule, and a brand-new file. It also proves that a move, a reflow, a code-span edit and a claim change nothing. The reflow cases include a code span that crosses a line break, split both ways, in a paragraph, a blockquote and a list item. They include a break inside a decision citation and inside `VS Code`. A function rename is not growth once its entries are re-keyed. A bare `·` moved to another component is red. A scratch markdown file is not read.

`scripts/typed-interpunct.json`, `scripts/typed-interpunct-pin.mjs`, `scripts/ste-ratchet.json` and `scripts/ste-ratchet-pin.py` are deleted.

### The line-anchor pin becomes a list

D245's `line anchor ratchet` row pinned a count of line anchors per file. The owner ruled to convert both of the last pins. The row is now `line anchor offenders`, over an offender list. The pin's file is deleted.

- **An entry is the anchor as written**, `path:N` or `path:N-M`, once per occurrence. An edit elsewhere in the file, or a reflow, does not touch it.
- **A claim moves nothing.** A decision entry's number is folded out of the document's own file key, as the prose list folded it. It is folded out of an anchor's decision path too, so both read `docs/decisions/*-<slug>.md`.
- **A new line number is a new identity.** The old entry goes stale, and the new anchor cannot be listed, because that is growth. The fix is a symbol, a section or a decision id.
- **Growth is counted over the whole list.** A paragraph moved to another file carries its anchors and adds nothing. A new file starts clean.

The list was seeded from the tree on the day of the ruling: 777 anchors in 44 files, all owned by `docs-sweep`. The retired pin held the same 777 over the same 44 files. `scripts/line-anchors.json` and `scripts/line-anchors-pin.py` are deleted. `make offenders-prune` covers the new list.

`make token-literal-check` still pins literal counts per file (D256). Another session owns that conversion.

### One helper decides "only shrinks"

Three copies of the only-shrinks rules existed: `scripts/kit-adoption.mjs` and two rows in `scripts/docs-audit.py`. A fix to one did not reach the others. One Python module holds them now: `scripts/only_shrinks.py`.

- `list_at_merge_base` reads a list as it stood at the merge-base with `origin/main`. It fails open and returns the reason. On request it also returns other files from the same commit.
- `growth` counts each `(rule, identity)` pair that HEAD holds more often than the merge-base. It refuses the pair under a rule the merge-base defines. It allows the pair under a rule born on the branch. It refuses all growth when a rule the merge-base defines is missing at HEAD, or when a rule set cannot be read.

**Why one Python helper and not one per language.** Two implementations need a shared fixture to prove they agree. A fixture proves agreement only on the cases it holds. The next fix still has to be made twice. One implementation cannot drift from itself. The cost is small. `kit-adoption.mjs` already runs `git` as a child process. Every place that runs `make check` has `python3`. So the `.mjs` runs `python3 scripts/only_shrinks.py base` and `growth` as commands and reads JSON back. It keeps only what is its own: the keys a block holds, and the rule ids its source defines.

Each caller still decides what an identity is, and so whether growth counts per file. The prose and line-anchor lists count over the whole list. The typed-dot list puts the file in the identity. The kit list keys one entry per file and rule.

### The prose list is cut

**Ruling (test-audit plan, row 92): cut the `ste offenders` row and its list.** The write-time STE hook lints new prose. The hook makes a prose list unneeded. The `ste offenders` row, `scripts/ste-offenders.json` and `scripts/docs-audit.py:check_ste_offenders` are deleted. D60 is amended to match.

A third list stays. `scripts/markdown-spelling-allow.json` covers the `identifier spelling` row's markdown half (D60). It has the same shape as the other lists: file, then lane, then SPELLING, then the British word, lower-cased, once per occurrence. `make offenders-prune` covers all three lists. A new file starts clean. Never add an entry to excuse new prose.

Offender lists, never a repo-wide count. A shared number is one every merge takes from somebody.

### What the STE ruler rests on

A survey classified a stratified sample of the linter's findings over the tracked markdown, by hand, against a rule stated before judging. It measured 10,077 findings in 610,723 words: STE001 7,162, STE006 2,638, STE007 130, STE008 147. That is 16.50 per thousand words, unfiltered.

- **Measured gotcha.** Passing several files to the linter in one call does not drop the per-finding `path` key. The measure still runs one file per call, because it needs each finding's source line.
- **Classification.** A finding is GENUINE when a person rewriting the prose would fix it with no loss of information. It is ARTIFACT when the writer cannot change the construct without losing information or misquoting a source. The ARTIFACT cases are these:
  - (a) A table cell or row.
  - (b) A verbatim quotation of the owner or a cited source.
  - (c) An enumeration whose length is the list's.
  - (d) Decision-citation shorthand, such as `(D31; ...)`.
  - (e) A false match on a proper noun containing the trigger (`VS Code` against `vs`).
  - (f) An under-fenced shell example.

  It is BORDERLINE when defensible either way, such as `via` and bare `vs` in ordinary prose.
- **The floor.** Extrapolated from the sample, no density threshold below about 2.24 findings per thousand words can be met on this corpus. With the borderline calls counted against the writer, the figure is about 2.71. Many findings are not prose defects. STE008 is the starkest: at least 93% of its sampled findings sit inside quotations of the owner's own words.
- **Exemption classes, four built.**
  1. A markdown table row, exempt for STE006, STE007 and STE008, as the linter already exempts it for the sentence-level rules.
  2. A verbatim quotation of a person's words: a blockquote line, or a span wrapped in `*"..."*`. About 89% of the STE008 sample.
  3. Decision-citation shorthand: a parenthetical whose first token matches `\(D\d+[,;]`.
  4. An enumeration collapsed into one paragraph: three or more semicolons, or three or more comma-separated items after a colon. This is a proxy, not a recognition. It is flagged and never auto-exempted, because some long enumerations should become bullet lists. It stays a named gap.
  5. A false match on a two-word proper noun (`VS Code`). A bug, not a judgment.
- **Already exempt in the linter:** fenced code, frontmatter, bare URLs, links and backtick spans. A backtick span still counts as one word toward sentence length, so a long run of short identifiers can trip STE001. Indented code, list items and blockquotes are linted like prose.
