## D187 — A claim checks whether the slug is already claimed, not only whether the number is free

`make claim-ids`'s `plan()` allocates `max(ceiling_at(ref)) + 1` for every unclaimed
`## D-<slug>` heading in the branch's own working tree. That answers "what number is free
on `ref`" and nothing else — it never asks whether `ref` has *already resolved this exact
slug* under some other number, via a branch that took a different path to main.

**This is exactly the shape #330 hit on 2026-09-12.** The per-file unclaimed-slug path sat
stranded (D42's build order, `#322`) and unclaimed on `main` for a stretch; #329's repair
claimed it as `D185` and merged. #330 was cut from a commit *before* that repair, and never
merged `origin/main` back into itself before running `make merge`. Its own claim step read
`ceiling_at(origin/main)` fresh, correctly found the very next number free, and renamed the SAME unclaimed
file to it — producing a rename/rename collision `stale_claims` cannot see (no number
#330 added was ever taken on `origin/main`; the number it picked was free the whole time) that surfaced
only as a GitHub merge conflict, after the claim commit had already been pushed.

`stale_claims` answers "a number THIS BRANCH ALREADY CLAIMED, taken again" — it needs the
branch to have claimed first. The gap here is upstream of that: a slug the branch has **not**
claimed yet, that main has already claimed under a different number.

**The fix**: `duplicate_pending()` in `scripts/claim-ids.py` reads `origin/main`'s
`docs/decisions/` tree via `git ls-tree`, strips the `D<n>-` / `D-` prefix off every claimed
and pending filename down to the slug text, and refuses — in both `--stale` and the write
path — when a pending slug's text matches an already-claimed file on `ref`. The message
names the number it was already claimed under and says to merge main and drop the branch's
stale copy, never to mint a second number for it.

**Scoped to `decision` only.** `codes` and `step` slugs are headings inside one shared file
apiece, never a filename of their own — the rename ambiguity this closes cannot arise for
either, and `decision index`/`id claims` already watch the shared-file kinds for the ordinary
two-number collision.

**What this does not fix**: a branch can still be arbitrarily behind `origin/main` on
everything else. This closes the one gap that was silent — a duplicate claim that neither
`stale_claims` nor a green `--stale` run could see — not the general "merge main before you
claim" hygiene, which `make merge`'s own dirty-tree and D151 checks already cover elsewhere.

Proved in `scripts/claim-selftest.py`: two branches cloned from one shared unclaimed slug,
one claims and pushes to main first, the other — never merging that back — is refused by
name, with the number already taken, on both `--stale` and `--write`; confirmed to fail
without the fix (mints a second number silently) before the fix landed.
