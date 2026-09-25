## D-ratchets-become-offender-lists — The typed-dot count and the prose ratio become lists of offenders, and no count is pinned

**The rule.** On 2026-09-23 the owner retired D194's word ceiling, because he did not want to keep a "stagnant static pin". D-text-shape-checks carried out that ruling. On 2026-09-24 the owner extended the ruling to the two other pinned counts. This entry replaces both.

- D218's typed-dot ratchet. `make docs-audit`'s `typed interpunct` row failed only when the COUNT of typed dots rose past a pinned number.
- D229's per-file prose ratchet. `make docs-audit`'s `ste ratchet` row failed only when a file's error RATIO rose past its own pinned number. D229 amended D226, so the ratchet half of D226 goes too.

This entry supersedes the ratchet parts of D218, D226 and D229. Each of those entries carries a "Superseded" note that names what stays.

### What a count could not see

A count passes a new defect when an old one goes in the same change. Fix one typed dot and type a new one, and the count holds still. Rewrite one bad sentence and write a new one, and the ratio can fall. The pin reported "no change" on both. The owner wanted the new defect to fail.

A pin also needs a person to move it. The old scripts wrote a new number on request, and nothing asked why. That is the "stagnant static pin" the owner refused.

### What replaces each pin

Each rule keeps its reader and gains a shrinking list of offenders. The shape is `scripts/kit-adoption-allow.json`'s: file, then rule, then entries, with the lane that owes the fix.

- **Typed dots.** `scripts/typed-interpunct-allow.json` lists each offending string in each file, as `scripts/user-strings.mjs` extracts it. The rule key is `interpunct`. D218's two extractor widenings stay exactly as they were.
- **Prose.** `scripts/ste-offenders.json` lists each offending sentence in each markdown file, under the rule it breaks. The rules are the four ERROR-severity codes of the vendored linter. D226's four exemption classes stay exactly as they were.

**The key is the offender, never a number.** A typed-dot entry is `<scope>: <string>`. The scope is the named function, class, arrow binding or module-level constant around the string. A nested scope is named with the scope around it, as `Outer.helper`. So one entry excuses one string in one place, and a bare `·` typed in another component is a new offender. A prose entry is a hash of the sentence and a short label. The label helps the person who rewrites the sentence. Only the hash is compared. An offender that occurs twice in one file is listed twice. So a copy of a listed offender needs its own entry and cannot hide behind the first.

### Three failures, and none of them is a count

1. **An offender the list does not name.** This includes a new offender in a file the list already names. A listed file excuses its listed strings and sentences, and nothing else.
2. **A stale entry.** A listed entry that matches nothing now shows that the fix landed. The lane deletes the entry in the same commit. `make offenders-prune` does the delete (see below).
3. **Growth.** Each row reads its list as it stood at the merge-base with `origin/main`. It uses `git merge-base` and `git show`, two reads, so D18 holds. An entry that the old list did not hold is refused. The one exception is a rule that the merge-base does not define: a rule born on the branch may list its first offenders. If a rule that the merge-base defines is gone at HEAD, all growth is refused. Otherwise a renamed rule could bring back every old offender as new. The read fails open, and prints why, when there is no merge-base or no list at the merge-base.

Growth is counted over the whole list, not per file. So `git mv` moves a file's entries and adds nothing. A listed sentence copied into a second file is growth, because the sentence now occurs one more time.

A typed dot's growth is counted by its string, without its scope. The scope stays in the unlisted and stale check. So a function rename moves its entries, the way a file rename does. The rename is red until the entries are re-keyed to the new name. After the re-key, the row passes, because the same strings occur the same number of times. The pruner does not re-key a scope, because it cannot tell a rename from a move. The re-key is a hand edit, and the diff shows it.

### A new file starts clean

D229 accepted a new file at its own ratio. Its reason was cost: refusing the file forced a re-pin on every branch that added a document. There is no pin now, so that cost is gone.

A new file is not in the list at the merge-base. So any entry for it is growth, and the row refuses it. The one exception is a sentence that left another file in the same branch. The author of a new document is writing it now, so the author can fix its prose at no extra cost. A new component with a typed dot follows the same rule.

### A sentence keeps its identity through the edits that do not change its prose

The prose list must survive the work that touches markdown without a change to what it says.

- **A reflow.** Whitespace is collapsed before the hash. Three readers see one line at a time. The vendored linter masks a code span per line. The `decision citation` and `VS Code` exemptions read the finding's own line. So before the hash, the lines that one such span runs across are joined into one line (`join_span_breaks` in `scripts/ste_measure.py`). Each reader then sees the whole span. The same sentence then gives the same findings and the same hash, wherever its line breaks fall.
- **An edit inside a code span.** The hash reads the linter's own masked text, where a code span is one placeholder. This holds for a code span that crosses a line break too.
- **A claim.** `make merge` turns each slug into a number, in every file, in the commit that merges it (D140). The hash folds every decision id first, so the claim moves no identity. The claim also renames a slug entry's file. So a decision entry is keyed by the tail of its file name, `docs/decisions/*-<slug>.md`, which holds no id for the claim to rewrite.

Any other edit to an offending sentence gives it a new identity. So a lane that edits a listed sentence must also fix it. The old entry goes stale, and the new text cannot be listed, because that is growth.

### What the lists hold on the day they are born

Both lists were seeded from the offenders on the integration branch on 2026-09-24, measured, not typed.

- **Typed dots:** 47 strings in 3 files. `Gallery.tsx` holds 45, owned by `kit-frame`. `PositionBar.tsx` holds 1, owned by `locating`. `RunsComposer.tsx` holds 1, owned by `b-runs`. Each was keyed again with its scope on the day the scope joined the key. The 47 strings are the same.
- **Prose:** 11,387 sentences in 358 files, all owned by `docs-sweep`. The row still prints the repo-wide ratio beside the survey's floor from `docs/specs/ste-false-positives.md`, and gates neither.

The prose list was seeded again on the day the code-span join landed. The first seed held 11,399 sentences in 357 files. The join changed 50 files. Some sentences lost a finding that sat inside a code span. Others found a finding the per-line mask had hidden. One file gained its first listed sentence. The seed count is the finding count: `ste_measure.measure` over the tracked markdown names 11,387 offenders, and the list holds 11,387 entries.

The prose list is about 1.1 MB. That is the true size of an identity for each offender, and a count is smaller only because it names nothing. It shrinks as `docs-sweep` rewrites sentences.

### The stale-only pruner

A stale entry must be deleted, and the prose list holds more than 14,000 lines of hashes. A hand delete is slow, and a merge conflict in it is worse. `make offenders-prune` (`scripts/offenders-prune.py`) does two edits and no others.

- **It deletes a stale entry.** It deletes one occurrence for each occurrence that the tree no longer has.
- **It re-keys a renamed file.** A listed file key that names no file today moves to the one new path that git's rename detection names. It reads `git diff -M` from the merge-base with `origin/main`. A rename onto a key that the list already holds is refused and named.

It never adds an entry. It refuses to write a plan that holds any identity more often than the list that it read. A list that is not JSON, such as one with merge-conflict markers, is not pruned. The pruner prints the recipe and writes nothing: keep either side's list whole, then run the pruner. That works because the list only shrinks. It reads with the rows' own functions, imported, so the pruner and the gate cannot disagree about what is stale. It previews by default, and `ARGS=--write` applies. It is on no hook and in no `make check`, because D18 says "A generator may write. Nothing that writes may gate a commit." It writes a data file under `scripts/`, as `scripts/line-anchors-pin.py` does. So it opens no seam in D18's list, which governs the prose files that agents read as argument. `make offenders-prune-selftest` proves it.

The rows read tracked files only. `markdown_files()` in `scripts/docs-audit.py` reads the index in staged mode and `git ls-files` otherwise. So a scratch `.md` file that git does not track never fails `make docs-audit`.

### What this cannot see

- A label can drift from its sentence when a claim rewrites the label's text. Only the hash is compared, so the drift is harmless.
- A slug entry whose file name is longer than its slug keys to a different tail after the claim. None exists today.
- A decision cited by its path in plain prose, outside a code span, changes its text at the claim. The fold does not reach it. The repo rule is to cite by id, never by path.
- D218's own gaps stay: a separator built without `.join`, a CSS `content:` string, and server-side Python strings.
- Only code spans, decision citations and `VS Code` are joined across a line break. A link, an HTML tag or a URL that crosses a line break is still masked one line at a time. So a reflow into or out of such a construct can still change a sentence's hash.
- A code span is paired as the linter pairs it: each backtick opens or closes one span. A double-backtick span that holds a single backtick is read wrong on every layout alike, so it moves no identity.
- A typed dot moved to another place inside the same named function stays excused. The scope is the function, never the line, because a line number rots on the next edit above it.
- A typed dot moved to another function, with its entry re-keyed by hand, passes. Growth drops the scope so that a rename can pass, and a move looks the same. The row is red until the hand re-key, and the re-key is in the diff.
- Two helpers with one name, in two sibling blocks of the same function, share one scope.
- The pruner cannot re-key a rename that git does not see. That includes a plain `mv` that is not staged, and a move with too large an edit for rename detection. The old entries then go stale and are deleted, and the new file's offenders stay unlisted.
- A markdown file that git does not track is not read until `git add`. The pre-commit hook reads the index, so a commit still carries every file it names.

### Mechanism

`make docs-audit`'s `typed interpunct` and `ste offenders` rows, in `scripts/docs-audit.py`. `scripts/ste_measure.py` names each prose offender. `python3 scripts/docs-audit.py --self-test` proves each failure red in memory. It proves a new offender in a listed file, a stale entry, growth under an existing rule, and a brand-new file. It also proves that a move, a reflow, a code-span edit and a claim change nothing. The reflow cases include a code span that crosses a line break, split both ways, in a paragraph, a blockquote and a list item. They also include a break inside a decision citation and inside `VS Code`. It proves that a function rename is not growth once its entries are re-keyed. It proves that a bare `·` moved to another component is red, and that a scratch markdown file is not read.

`scripts/typed-interpunct.json`, `scripts/typed-interpunct-pin.mjs`, `scripts/ste-ratchet.json` and `scripts/ste-ratchet-pin.py` are deleted.

### Pinned counts this entry does not reach

Two more per-file pins remain, and the owner's ruling did not name them. `make docs-audit`'s `line anchor ratchet` row pins a count of line anchors per file (D229's shape). `make token-literal-check` pins literal counts per file (D256). Each could take the same list shape. That is the owner's call.
