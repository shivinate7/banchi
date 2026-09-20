## 31 — Twelve decisions are cited by path, one of them dead, and the path guard never reads code

Found sweeping for the rest of PR #424's defect. That defect turned a slug's path citation
into a path that never existed. RECORDED here, not fixed, on the owner's word, 2026-09-19.
The mass rewrite waits until the current batch of work merges and the tree is back on
`main`. This entry is the record. A finding that lives only in a pull request body is a
finding that is lost.

**What was measured.** Two shapes exist. Only the first is this repo's defect.

One slug-form path citation, and it is the worked example. `docs/specs/revenue-plan.md:139`
carried a path naming the price-history archive entry. That entry was still an unclaimed
slug. The claim ran on 2026-09-19 and allocated D219. The claim step rewrote the path by
substituting the token. That produced a path to a file that does not exist. The real file
keeps its slug tail after the number. The audit refused the claim commit and the merge
stopped. A person repaired that one line by hand, to cite D219 as an id. PR #424 fixes the
cause, so the next claim writes an id rather than a broken path.

TWELVE already-claimed, numbered-path citations sit across six files. This is a different,
older style. It names a real entry by its full `D<n>-<slug>.md` filename, not by its bare id:

    docs/specs/stable-card-id.md:764
    docs/specs/store-scaling/05-readings-writer.md:27, 41, 58, 490
    docs/specs/store-scaling/08-search-fts5.md:87, 93
    scripts/docs-audit.py:11689
    store/orders.py:181
    store/numbers.py:5

Eleven of these resolve. ONE IS DEAD. `scripts/docs-audit.py:11689` cites
`docs/decisions/D218.md`. That file does not exist. The real one is
`docs/decisions/D218-no-typed-interpunct-on-screen.md`. The citation dropped the descriptive
tail, the same shape PR #424's defect added one where none belonged, in reverse.

**Why the dead one was never caught, verified rather than assumed.** `make docs-audit`'s
`paths` row is `check_paths(report, docs, allowed)`. Every caller passes it `docs =
markdown_files()` (`scripts/docs-audit.py:379-380`, `_walk(ROOT, (".md",))`) or a `.md`
fixture. The four calls inside the row's own self-test do this too. No call anywhere in this
file hands it a `.py`, `.ts`, `.tsx`, `.css` or `.js` path. The rule is real. `check_paths` is
a real reader for it. The reader is wired to one file type only. A citation of the identical
shape, sitting in a comment in `scripts/docs-audit.py`, is invisible to its own audit. This is
not a gap in the rule. It is a gap in which files the reader opens.

This is narrower than `decision ids in code`, which already resolves a BARE `D<n>` citation
across `.py`, `.ts`, `.tsx`, `.css` and `.js` (`make docs-audit`'s own report: "citations in
.py, .ts, .tsx, .css and .js all resolve"). That check reads the token alone. It never reads
the path around it. A path-shaped citation is a different question it does not ask either.

**What closes this.** Two things. Neither is built here. This entry is the record. The work
is the owner's to schedule.

1. The twelve citations become id citations. PR #424 taught the claim step this same
   rewrite, for the future. This is the same rewrite, done once by hand, or by a small
   script, over the existing tree. It matches the rule this repo already holds: "Give each
   record its own file, one folder per kind. Cite by id, never by path."
   (`~/Developer/claude-settings/CLAUDE.md`). D160 applies the identical argument a second
   time.
2. The `paths` row, or a sibling row built for the purpose, learns to open the file types
   that can carry this citation. A repeat of `scripts/docs-audit.py:11689` is then caught on
   the day it is written. Nobody sweeps for it by hand again.

None of the six files above is `docs/decisions/`, `docs/DECISIONS.md` or `docs/map.py`. PR
#424's own change does not touch them. Leaving them as they are does not affect `repo map`'s
`governed_by` accounting.
