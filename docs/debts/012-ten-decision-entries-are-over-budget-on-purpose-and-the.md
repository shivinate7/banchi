## 12 — Ten decision entries are over budget on purpose, and the budget was the thing that had drifted

`scripts/docs-audit.py`'s `entry budget` row reports entries larger than `ENTRY_BUDGET`. It reported
**21** until 2026-09-05 and reports **10** now, and the difference is not that anything was cut.
**Re-measured 2026-09-13: the row reports 18**, not 10 — eight more entries crossed the same
fixed budget as the corpus kept growing, which is the row doing exactly the job this section
already describes rather than a new defect.

**The constant had stopped tracking the thing it is derived from.** Its own comment defines it as
twice the median entry, measured at 6,374 on the day it was set. Measured today with
`prose-guard.entries()` — which counts CHARACTERS, so a byte count taken with `.encode()` reads three
entries higher and is the wrong ruler — the median over 100 entries is **7,718**, so twice it is
**15,437**. The corpus grew 21% and the ceiling did not, so the row was reporting against a rule it
had stopped implementing. Re-derived, with both dates kept in the comment, because a ceiling that has
moved with no record of it is one nobody can argue with.

**The ten that remain were then classified rather than trimmed, and none of them is over for the
reason the row exists to catch.** D32 16,391 · D38 20,441 · D42 20,296 · D43 16,530 · D49 18,705 ·
D53 20,913 · D58 17,658 · D65 19,041 · D86 22,670 · D90 20,301.

The row's stated theory is that *"an entry at twice the median is one that should have cited a
neighbor instead of re-arguing it"*. That theory was right twice: D92 and D96 were brought under in
exactly that way, by deleting passages that re-derived D58's slot/index split and the open/done rule
and citing instead. **It does not hold for these ten.** Their largest paragraphs were read: most cite
no other entry at all, and the two that cite heavily — D38's claim inventory and D58's
consequence list — are doing precisely what D60 asks, naming a neighbor and saying what changes
under it, wrapped around measurements (*"`rarity_claim` is set on 543 of 543 records"*). There is no
re-derivation to remove. What is there is many measured findings in one entry, and CLAUDE.md rules
those are evidence and are never rewritten to match a later tree.

**So the honest state is that the row is now measuring length rather than diagnosing a defect**, for
these ten. It stays as an `ask` and is not blocking, which is the right severity for a question. What
would close this section is not a trim: it is either a second signal that separates "long because it
re-derives" from "long because it measured a lot" — a citation-density heuristic was considered and is
the kind of guess D16 keeps off a blocking row — or a ruling that some entries are allowed to be long
and should say so in their own first line.

---
