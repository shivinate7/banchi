## D133 — A branch is judged by what it lands, and a file put back the way main had it is refused unless the branch says so

**Settled 2026-09-11, on the owner's instruction, after D119's deletion was found undone.**
The commit that undid it was about something else.

### What happened, in commits

`4bf5a44` (PR #218, D119, 2026-09-07) deleted `LocationCard` from `app/src/Inventory.tsx` and
re-pointed the two specs that had asserted it. The next commit on main's first-parent line is
the merge of PR #221, "The cap is a ceiling on copies live" (`121cfe5`, 2026-09-08), and what
that merge brought onto main included the PRE-deletion copy of nine front-end files #218 had
touched — the component, its stylesheet, `CardLocations.*`, `Gallery.*`, `BoxBrowse.css` and
both specs. `9439765`, the commit inside it, is a single-parent commit on top of the #218
merge whose diff on those files is, line for line, the reverse of `4bf5a44`. Its message names
none of them. The mechanism, reconstructed: the #221 session merged main into its branch,
resolved by keeping `ours`, and squashed onto main as one commit; the PR lists a merge commit
(`e2b9b4f`) that is not an ancestor of what landed.

**Every guard the deletion had lived in the files that came back**, so every guard came back
with the thing it guarded against. `make check` was green on both sides, the Playwright suite
was green on both sides, and three days later D132's session found the component, read the
owner's screenshot of it as a wish, and wrote that down. PR #246 re-applied the deletion and
added the `recorded deletions` audit row — a hand-written table of symbols a decision says are
gone — which covers a deletion a session remembers to register and nothing else.

### The ruling

**A branch is judged by what it would land on main, not by its own commits.** The #221 shape
has a merge-base AFTER the commit it reverses — the branch merged main and kept ours — so
`origin/main..HEAD` shows a tidy cap-wording change and only the landing diff shows the revert.
`scripts/revert-audit.py branch` reads `git merge-tree --write-tree origin/main HEAD` and diffs
origin/main against that tree, which is exactly what the PR page shows and what the merge
button would do; when the merge conflicts it falls back to the branch's diff off the merge-base
and says so. On GitHub, a pull-request checkout IS that merge, so the CI job reads `HEAD`
against `origin/<base>` and compares the same two things.

**A file whose whole change is the exact reverse of a commit main already carries is refused**
unless a commit on the branch names the file. Two detectors, both exact:

- **whole-file** — the change takes the file from blob `a` to blob `b`, and a commit within
  main's last sixty first-parent commits took it from `b` to `a`. By object id; no diff is
  read. A file deleted that a recent commit created counts, because a keep-ours merge deletes
  every file main added.
- **hunk** — a `-U0` hunk of the change is, line for line, the reverse of a hunk an earlier
  commit in that window introduced on the same file. Whitespace-only hunks are dropped. A
  merge on the first-parent line is compared as what it brought onto main, and the branch
  commits inside it that touched the file are named beside it, because the merge is never the
  commit a person would cite.

**Refused** means: every hunk the change makes to the file is such a reversal, or the whole
file is restored. **A partial reversal beside real edits is a note and never a refusal** — a
line changed and changed back inside a rewrite is ordinary work, and a guard that refused it
would be switched off within the week. **Declared** means a commit message on the branch names
the file — its path, its basename or its stem. `git revert` exists, D125's crop came off four
screens on the owner's word (PR #233), and D119 itself was re-applied by reversing #221; each of
those is a reversal somebody meant, and the cost of meaning it is one file name in one commit
message. `PKMNSCAN_REVERT=off` runs nothing and is printed in every refusal, on the same terms
as `PKMNSCAN_MAIN=off`.

**It runs three times, for D42's reason: the local and the remote halves fail separately.**
`make revert-guard` in `check` and `ci-check`; `scripts/githooks/pre-push` on
every branch push, before the branch becomes a PR; and its own job in
`.github/workflows/check.yml`, so a refusal is a named red check on the PR rather than one line
inside `ci-check`'s output. It writes nothing, needs python3 and git, and with no `origin/main`
in reach — a fixture clone — it allows and says so.

**`make revert-selftest` proves it by rebuilding the sequence**: a throwaway origin, a deletion
merged as #218 was, a branch cut from before it that merges main with `-s ours` and is squashed
onto main with a message naming nothing. The fixture asserts its own arming — the squashed
branch really does carry the pre-deletion blob — then asserts the refusal, the history walk
naming both the merge and the deleting commit inside it and reading `D1` out of the reverted
decision text, a clean branch allowed, a partial reversal noted and allowed, a declared
restoration allowed, a silent restoration refused at hunk level after main has moved the file
again, the escape hatch honoured and named, and main itself landing nothing. Mutation-tested, three arms:
with the whole-file detector disabled the #221 case stays refused on the hunk detector and the
history case fails; with the hunk detector disabled the silent restoration and the partial case
both fail; with `entire` made to return true for a partial hit, the partial case fails.

### The 2026-09-11 walk over main, and what it found

`scripts/revert-audit.py history` is the same engine over every commit on main's first-parent
line — 367 commits, window 60 — and it reports every reversal whose commit message does not
name the file. **Fifty-two file-level reversals across eighteen commits**, every one read on
both sides rather than trusted to the diff arithmetic. Fifty of them are reversals somebody
meant, and the record already says so: #221 undoing #218 (the case above); #246 undoing #221
(the re-application, D119 amended) and #244's `indexNote` (D132 amended the same day); #233
undoing #231 on five files (D125 amended, §7 reopened); #222 removing the
`cap_the_store` helper #216 had added to T7 (`policy.live_cap` was deleted, D7); #176 removing
`RailMark`'s export while deleting `RailMark.tsx` itself; #164 removing four
`docs-audit-allow.txt` lines that each said "delete when built"; #145 moving `review.spec.ts`'s
`/status` stub into the shared seal; #114's overhaul removing the T6 order walk (D96) and
retiring comments whose code fixes survive — `Pricing.tsx` still reads the hash in its
`useState` initialiser; and six pre-PR commits where one author iterated on their own previous
commit, all of whose reversals were later re-applied or were D31's own deletions.

**One is real and unrecorded.** `5b79982` (PR #192, "t1-fingerprints", D112) put back the
paragraph of D50 that PR #191 (`efc2444`, the same day) had replaced — this entry said D110
until the restoration, because the lost text cites D110: eight paragraphs
recording the owner's 2026-09-07 ruling on the 22 inert controls — the current page's nav link
now responds, the selected tab stays inert by their choice from the images, the first fix
snapped because `background-image` does not animate, and `cursor.spec.ts`'s guard gained a
reader for gradients by name. The code survived in full: `App.css`'s
`.bn-nav-link[aria-current='page']:hover`, the gradient test in `cursor.spec.ts`, and the
ruling's comment in `kit.css`. **The decision does not.** D50 at HEAD says the current page's
hover is "a design question for the owner rather than a defect" — a question the owner
answered four days ago, whose answer is now recorded only in a stylesheet comment. What the
screen does is right; what the record says about it is a day old. Not fixed here: the owner's
call, one branch, restoring the text of `efc2444` into D50 as an amendment dated to both
days.

The seven files D119's own re-application (`521dbfd`) put back in `Inventory.tsx`,
`inventory.spec.ts`, `Gallery.tsx` and `docs/map.py` are partial — 19 of 21, 43 of 58, 3 of 4,
3 of 9 — because #246 also moved on from what #218 had; they are the same event read from the
other side.

### What it cannot see, named rather than papered over

- **A reversal older than the window.** Sixty first-parent commits is about twelve days of
  this repository's history; a branch a fortnight stale that merges main keeping ours reverses
  commits the guard no longer looks at. `--window 0` is unbounded for a one-off audit and is
  not the default, because the walk has to finish on every push.
- **A reversal re-worded on the way back.** A line changed as well as restored is a new edit,
  and the guard is exact on purpose: a similarity threshold is a dial, and every dial on a gate
  gets turned until the gate is quiet.
- **A reversal whose hunk a neighbouring edit widened.** #221 also put back D119's rows in
  `docs/map.py` and `docs/DEBTS.md`, and the guard does not report them: the branch's own D7
  edits sat on adjacent lines, so the reversed lines and the new ones share one hunk and the
  hunk is no longer the reverse of anything. A containment test — the reversed hunk found as a
  contiguous run inside a larger one — was built and measured against the same history:
  seventy-nine additional hits, every one a coincidence of code moved within a rewrite, and the
  map rows still not among them. It was not kept. The whole-file detector is the answer to the
  common form of this: a keep-ours merge restores the whole blob, and a blob is compared by id.

### Amended 2026-09-11, the same day: the walk was put to the owner, one reversal at a time

**Every reversal above was read to the owner in plain English and ruled on**, so none of it is
re-litigated. Their standing instruction from that interview binds every future pass:
*"I need you to tell me these in english, the terminology of codes is for your ease."* A PR
number, a decision number or a file name is not an answer they can rule on.

**Restored, on their word: D50's lost paragraphs.** `efc2444`'s eight paragraphs are back in
D50, dated to both days, on `claude/d50-amendment-restored`. The commit names the file, which is
this entry's own declaration rule, and the guard passed it.

**Kept, on their word, each one presented and not overturned:** the location panel stays
deleted and each row names its box once (#246); the crop stays off the four screens (#233); the
separate rail icon stays gone and the logo morphs into the bracket as the sidebar collapses
(#176); the four allow-list placeholders stay deleted (#164); the Review screen's per-file
`/status` stub stays folded into the shared seal — they asked what keeping it costs, and the
answer recorded is *nothing*, against a weaker second copy (#145); the Codes screen's box load
stays as the redesign wrote it (#136); the "Fetch anyway" buttons stay as rebuilt (#110); the
iCloud-era `node_modules` shortcut stays untracked (#9); the six pre-PR self-reworks stand.

**Kept, with the owner correcting this record's framing of it (#114, D96).** This entry and
D96 describe the retired order walk as "the walk picking for me" and its replacement as one
copy at a time. Their words on 2026-09-11: *"It's still a guided walk, it's just I get to pick
from all the copies rather than just spoonfed one specific copy to go find."* The walk through
the boxes on `#/orders` IS guided; what changed is who chooses the copy. Read D96 with that
sentence beside it.

**Kept, and it surfaced a loss the walk did not find (#222, D7).** The standing cap's removal
stands. But their words: *"I actually found I can no longer select quantities to sell at all,
which wasn't the goal. Yes I wanted caps eliminated at the store level, but I still wanted to be
able to select quantities to list if on a case-by-case basis I want to, and I've somehow lost
that functionality."* D7 says `--cap` and a field on `#/pricing`'s ship bar are that control;
the owner cannot find or use it. Out of this walk's scope and handed to its own task rather than
guessed at here — it is a D7 question, and the first step is to look at the screen with them.

**Two spellings of one word, ruled on rather than kept (#110, D60).** `_artefacts` flipped
between spellings in this file across two PRs and the owner ruled: standardise repo-wide. Its own
task, under D60, which already rules American for the loaded docs.
