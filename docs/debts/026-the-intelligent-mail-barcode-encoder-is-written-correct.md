## 26 — The Intelligent Mail barcode encoder is written, correct against the Postal Service's own examples, and parked on a branch

**The owner's ruling, 2026-09-11**: *"How can we keep the code and shelve it? I don't want to land
it, I don't want it lost."* This section is the shelf record. It is here rather than in
`docs/DECISIONS.md` because no architecture was decided — a body of work was set down where it can
be found again, which is what this file is for.

### Where it is

| | |
|---|---|
| branch | `claude/tcgtracking-in-house-a7cb43` |
| commit | `c9391e1fcc90b7e1d1dabf2c359c986a87ee59a3` |
| on origin | yes, checked rather than assumed — `git ls-remote origin claude/tcgtracking-in-house-a7cb43` answers with that SHA |

`git show c9391e1` is the whole of it: 582 insertions across six files, two of them new.

- **`pipeline/imb.py`, 314 lines.** USPS-B-3200 Rev H steps 1 through 6 — four data fields to the
  65-bar string a barcode font prints, as six named functions so a wrong one is named by the test
  that fails. It imports `typing` and nothing from this repo. No network, no account, no
  credential, no per-piece fee, and nothing in it can spend money.
- **`harness/tests/t10_imb.py`, 186 lines.** T10.
- The wiring, which is the other 82 lines: `harness/run.py` registers T10, and `docs/GATES.md`,
  `docs/map.py` and `CLAUDE.md` describe it.

**The branch is pushed, so the work survives a disk wipe and not merely a deleted worktree.** That
is the fact this whole section rests on: a shelf record that does not say where the code is has
shelved nothing. It is worth knowing how close it came — the commit is a rescue, made when the two
files were found untracked in a worktree that was about to be removed, reachable from no ref at
all.

`scripts/docs-audit-allow.txt` carries both new paths, because the `paths` row is MECHANICAL and
these two files deliberately do not exist here. Those lines are self-cleaning: the audit fails the
moment either path resolves, so reviving the code forces this section to be rewritten rather than
left behind to go stale.

### Why it is parked rather than landed

**Not because it is broken.** The measurement is below.

`docs/specs/order-pipeline.md`'s STATUS table reads **step 13 track back: missing** and **step 14
tell buyer: missing, deferred behind 13**, and its step 12 row records that the tcgtracking call
still does not exist. This encoder is the arithmetic half of step 13. The other half is account
state this repo does not hold: a barcode produces scan events only if mail processing equipment
reads it AND the Mailer ID it carries is registered to somebody's Informed Visibility
subscription. `imb.py` models neither, on purpose — `mailer_id` is an argument with no default,
on the ground that an invented MID either belongs to somebody else or to nobody, and the first is
somebody else's scan data.

**So landing it would land a module no screen can reach**, which `CLAUDE.md`'s first hard rule
refuses to call done and whose corollary files under NEITHER. Parking it is the honest form of
that same judgement, and the owner's ruling is what settles it either way.

### What was and was not verified

**T10 asserts against a published external specification, not against its own output.** Every
expected value is transcribed from USPS-B-3200 Rev H, Appendix C, Tables 13 to 16 — the Postal
Service's own worked examples, carrying their own answers. Four vectors share one tracking code
and differ only in routing length, which is what exercises all four legal routing shapes rather
than one; each is asserted at every intermediate step — binary data, FCS, codewords, characters,
and the 65-bar string — rather than on the final string alone, so a failure names which of the six
steps broke. The bar map, the one table nothing generates, is separately checked for being a
bijection over all 130 character-bit positions, which is what catches a transcription typo as a
typo instead of as "the answer is wrong".

**It passes. Measured 2026-09-11**, two ways, by extracting `c9391e1` into throwaway trees outside
the repo and calling `run()` directly:

| tree | result |
|---|---|
| the branch's own | **42 checks, 42 pass** |
| current `origin/main`, with the two files dropped in | **42 checks, 42 pass** |

The second is the one worth having: it says the test still runs against today's `harness/tests`
helpers and not only against the ones it shipped beside. Both on Python 3.9.6, this machine's.
**The rescue commit says in its own message that the harness was not run and the encoder was not
checked against the spec.** It has been now, and that is the one thing this section adds to it.

**What a green T10 does not mean, in the test's own words: it does not mean an envelope gets
scanned.** No barcode from this module has ever been printed. No envelope carrying one has ever
been mailed. The four vectors use the specification's own example Mailer ID, which is why they may
only ever be a test — there is no MID here, and USPS publishes no test value for live mail. The
encoder is arithmetic and T10 is arithmetic about arithmetic. Everything between the 65-bar string
and a scan event is unmeasured, and none of it is in this code.

### What reviving it would cost

**The encoder itself: nothing measurable.** It is a pure function over digits importing nothing
from this tree, so main has no surface to have moved under it — which the second row above is the
evidence for, 540 commits after its merge base.

**The wiring has drifted, and by exactly one file.** The merge base is `f721b72`, 2026-09-02;
`origin/main` is 540 commits ahead of it. A read-only `git merge-tree` of the branch against
current main conflicts in **`CLAUDE.md` alone** — `docs/GATES.md`, `docs/map.py` and
`harness/run.py` all auto-merge. The conflict is the harness count: the branch rewrites "all NINE
verification tests" to TEN inside a paragraph main has since rewritten for other reasons. Recount
from `harness/run.py`'s `TESTS` list, which holds nine today, rather than trusting either side of
that conflict — it is the same instruction that paragraph already carries.

**What needs re-measuring is all on the account side and none of it in the code**: a Mailer ID
assigned through the Business Customer Gateway, an Informed Visibility subscription for it to
report into, a service type code that actually asks for tracing — the module notes that STID 300
is correctly encoded and reports nothing — and a serial allocator, which `imb.py` deliberately
does not hold, on the ground that a serial must be unique per piece within a MID or two envelopes
report as one. That last one is state, and it belongs beside the order ledger rather than in an
encoder.

### What would reopen it

**The owner saying so, and step 13 becoming live work rather than a missing row.** The concrete
precondition is the Mailer ID: until one is registered to an Informed Visibility subscription, this
encoder can be perfectly correct and still report nothing, which is exactly the state it is in
today. Nothing else here is blocked on anything.

**The number may move, and nothing allocates it.** This entry was written as 25 and renumbered
when PR #282 took that number while this branch was open — the rule working rather than a
collision, and the same one `docs/DECISIONS.md` keeps: renumber your own, never another's. 26 is
what was next on 2026-09-11.
