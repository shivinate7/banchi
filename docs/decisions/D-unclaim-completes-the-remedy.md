## D-unclaim-completes-the-remedy — The remedy `stale_claims` names is a real command, and `stale_claims` learns to see the directory it moved into

**A documented remedy with no command behind it is not a remedy.** D140's amendment gave
`scripts/claim-ids.py --stale` a refusal for a claimed id that has gone stale — main
independently took the same number this branch already claimed — and its own text says what
to do about it: *"Put the id back to the slug form and let the merge allocate it again."*
Nothing performed that sentence. A human, or a session, had to hand-rename the entry's file,
hand-edit its heading back to a slug, and hand-find every citation of the stale number across
`CLAUDE.md`'s index, `docs/decisions/ORDER.json`, `docs/map.py`'s `governed_by` lists, and any
code comment — by hand, with a text editor, guessing at what needed to change. That is exactly
as error-prone as the problem D140 exists to delete from the forward direction: a person
deciding which occurrences of a number are the right ones to touch.

**It bit for real on 2026-09-12.** A coordinating session hit `stale_claim`'s refusal mid
conflict-resolution and, with no un-claim command to reach for, hand-picked new numbers
instead — one guess collided too, before landing on `D188`. That guessing is exactly what
D140 was built to remove, reached for because the remedy its own refusal names had never been
built.

### `scripts/claim-ids.py --unclaim <id>` is the exact inverse, reusing the forward grammar

It is built as the literal inverse of the forward substitution rather than a second
implementation: the same `(?<![-\w])...(?![-\w])` boundary `apply_to_text` uses, run with the
token and the replacement swapped. That reuse is load-bearing and not a style choice — this
repo was burned once already by `\b` matching a shorter slug INSIDE a longer one that extends
it (`claim-selftest.py`'s own boundary arm found the bug in the unmutated forward code), and a
hand-rolled reverse substitution would have had to remember that independently. Reusing the
grammar means it cannot forget it.

**A decision derives its own slug automatically; a codes id or a build step cannot.** A
decision's entry is a FILE, and `rename_claimed_entries` renames it rather than deleting it —
`D188-a-join-with-no-run-directory.md` still carries `a-join-with-no-run-directory` after the
heading itself has been overwritten with the number, so `--unclaim` reads the slug straight
back off the filename. `docs/CODES-DECISIONS.md` is one file for the whole codes corpus and
`docs/GATES.md`'s build order is one file for every step; neither gets a rename, so the
substitution that turns `C-<slug>` or `step <slug>` into a number is TOTAL — nothing anywhere
in the tree still spells the slug once it commits. `--unclaim` therefore takes `--to-slug` for
those two kinds, supplied by whoever still has it — their own commit that introduced the entry
names it, in the heading, before the claim ran.

### The safety gate compares CONTENT, not raw presence, or it would refuse its own worked example

The first design asked only "is this number on `ref` at all" and refused whenever it was. That
is wrong: the actual 2026-09-12 incident is precisely a branch whose own claimed number
collided with an UNRELATED entry that `ref` independently claimed at the same number — by
definition, `--unclaim`'s whole reason to exist is that the number IS already on `ref` when it
is needed. A flat presence refusal would have refused the one case this file was built to
answer. `same_entry_on_ref` compares the claimed HEADING LINE — this branch's own copy against
`ref`'s copy at that number — and refuses only when the two are identical, which is
`stale_claims`' own argument read backwards: unclaiming a number `ref` already carries AS THIS
SAME ENTRY would corrupt the citation main's own copy of it now depends on. A different entry
sharing the number by coincidence is not that danger; it is the collision the command exists
to fix, and reverting this branch's own file touches nothing of `ref`'s.

### `stale_claims` could not see the collision it exists to name

Reproducing the incident end to end found a second, independent bug: `stale_claims` reads
`root / "docs/DECISIONS.md"` and `git show <rev>:docs/DECISIONS.md"` directly for the decision
namespace, which has been a prose stub with no `## D<id>` heading at all since D160 split the
corpus into `docs/decisions/`. Every other per-kind reader in this file that needed the
decision corpus — `ceiling_at`, `pending`, `pending_at` — already special-cases `kind ==
"decision"` to read through `corpus_text`/`corpus_text_at`; `stale_claims` was the one that
never learned the split had happened, so it saw an empty set on every side of every comparison
and reported every decision collision as clean. `make claim-stale` — in `make check`, and the
CHEAP early warning `make merge`'s claim half asks for before every merge — has therefore been
silently unable to catch a decision-id collision since 2026-09-12, and the actual incident had
to be caught by `decision index`'s loud, late backstop instead: exactly the shape D140's own
docstring warns is "loud, late, and paid by whoever happened to merge second." Fixed by making
`stale_claims` read the corpus the same way its siblings already did; `corpus_text`/
`corpus_text_at` fall back to the flat file when there is no manifest, so this changes nothing
for a pre-split tree.

### What this does not change

Nothing about the FORWARD claim moves. `--unclaim` writes nothing that `perform()` would not
also touch on the way in, and the safety gate means it can never be pointed at a number that
already correctly belongs to main. It is reporting-and-repairing where the forward direction
is reporting-only (`--stale`/`--landed` still fix nothing themselves) because an un-claim, by
D140's own rule, has to happen BEFORE a merge — there is no equivalent constraint stopping this
one command from performing its own remedy locally, since nothing about a branch's own
not-yet-merged tree is protected the way main is.

### Reopening condition

If a fourth namespace ever needs claiming, it inherits `--to-slug` unless it grows a
per-entry file the way a decision has — in which case it should read its slug back
automatically, the way `find_decision_file` does, rather than asking a human to remember it.
