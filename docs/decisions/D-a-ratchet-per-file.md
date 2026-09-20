## D-a-ratchet-per-file — The prose ratchet is pinned per file, because a repo-wide number is one every merge takes from somebody

**AMENDS D226, WHICH IS OTHERWISE UNCHANGED.** The vendored linter, the four error rules, the
four exemption classes, the survey floor and the ruler all stay exactly as that entry settled
them. Only the ratchet's SCOPE moves. The measurement it takes is the same measurement.

**REPORTED BY THE OWNER, 2026-09-19.** The ratchet forced three re-pins in one evening. Not
one of them was caused by the branch's own prose. Each was caused by an unrelated merge.

### The premise that failed

`scripts/ste-ratchet.json` pinned three things, and all three are whole-repo scalars. A total
of every error in the tree. A count for each of the four rules. A ratio for each of six
buckets, one of them the whole repo.

Every branch in flight has to write those numbers. Any merge that touches markdown anywhere
moves them. So a branch that was correct when it was written is wrong by the time it lands,
through nothing it did. The branch that merges second pays, every time.

This is the same shape as the decision-id race the same evening produced.
**A whole-repo scalar makes every branch a party to every other branch's merge.**
The argument is written once, there. See that entry for the id half.

### Why the id answer does not transfer, and what does

A decision number has to be unique across the whole repo. Its answer is genuinely global. The
merge is the only place that can know it, which is why claiming one costs a commit, a push
and a wait for checks. That machinery is justified because nothing cheaper is correct.

A prose ratio is not like that. It is a **sum**, and a sum can be cut into pieces. Each file's
ratio is a pure function of that file's own text. Nothing outside the file can move it.

So the pin becomes a map with one entry per tracked markdown file. Two branches editing
different files write different keys and never meet.

### What is gated, and what is only read

**Gated: each file's own ratio, against its own pinned ceiling.** That is the whole gate.

**Read and printed, gated by nothing: every repo-wide figure.**
The total, the four per-rule counts and the six bucket ratios are all still measured. The row
prints them on every run, beside the survey floor. They pin nothing. A number every branch
has to write down is a number every merge takes from somebody.

The ruler is still errors per thousand words, not a raw count. D226 measured why. A count
tracks how long a document is, at r = 0.898 against entry size. The ratio tracks how tight its
prose is, at r = 0.0020. A file that grows by a well written section gains words and no
errors, so its ratio falls and the ratchet stays silent. The file's own error count and word
count ride along in the pin as receipts. Neither is gated.

### Two states that are deliberately not failures

**A file the pin has never seen is accepted, and named.**
A ratchet says a number may only go down. A file that did not exist has no number to go down
from. Refusing it would force a re-pin on every branch that adds a document. That is the cost
this amendment exists to remove. The row prints which files those were, so the looseness is never silent.

**A pin whose file is gone is not a failure either.**
The branch deleted the file, which is a fall to nothing. `scripts/ste-ratchet-pin.py --pin`
prunes the key the next time a person runs it. Until then the stale key gates nothing and forces no re-pin.

### The residual cost, measured rather than claimed

Two branches, each tightening a different file and each adding a new document, merge with no
conflict. Measured against the real 363-file pin on 2026-09-19, with `git merge-file`.

Two cases still conflict, and both are correct.

- **Two branches change the same file's pin.**
  That is a real disagreement about one file. Git raises it where the writer already was.
- **Two branches add new documents whose paths sort next to each other.**
  Git conflicts on adjacent insertions. No text format for a sorted map avoids this. It is
  one conflict in one hunk. The old shape guaranteed a re-pin for any markdown change
  anywhere.

### The old pin shape is refused rather than honoured

A pin file carrying `total`, `by_code` and `ratio_per_1k_words` reads as no pin at all. The
row then fails as `unpinned` and says to re-pin once. Accepting it silently would gate on the
exact scalar this amendment removes.

### Proved by mutation

`scripts/docs-audit.py --self-test` carries the verdict arithmetic, and five mutations each
turn one arm red and no others.

- Ratchet on the raw error count instead of the ratio. Red on a file that grew by two thirds,
  gained eight errors, and whose ratio fell.
- Judge every file against the loosest pinned ratio rather than its own. Red on a file pinned
  tighter than another in the same repo.
- Treat a file with no pin as a rise against zero. Red on the accepted new document.
- Treat a pin whose file is gone as a rise. Red on the deleted document.
- Accept the old repo-wide pin shape. Red on the reader's own refusal.
