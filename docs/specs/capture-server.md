# Capture server — execution spec (build-order step 5)

Planning output of the 2026-08-11 workflow review; owner-approved. The executing session
implements from this file, top to bottom, and asks nothing. Every judgment call below is
already made; deviating from one is an owner conversation, not an implementation choice.

Scope: the capture server, the position allocator it needs, one settled decision, and two
cleanup sweeps that must land first. `make harness` must be green before and after every
commit in this plan.

**Read `docs/specs/audit-retirement.md` section 10 before section 1 here, and read its
accuracy note.** Its mechanical figures held under execution and its runtime claims did
not. The same discipline applies to this file: every line number and signature below was
read from source on 2026-08-11 and re-verified by a second pass, but verify before
building on one.

---

## 0. The rules this session runs under

Two owner constraints, settled. Neither is a preference.

**0.1 — Nothing in this plan edits `scripts/docs-audit.py`. Ever.** If the audit blocks,
the fix is the map or the doc it names, never the auditor. If a finding is a false
positive, record it in `docs/DEBTS.md` and work around it. The reason is on the record in
D16: an agent that can edit the docs to satisfy its own gate will do exactly that, and
each edit will look reasonable. The generalisation is D18. This session is the first in
the project's history to touch the auditor's subject matter without touching the auditor,
and that is the point — the repo spent a full day and eighteen commits on the auditor and
its docs, nine of them on that file alone, and shipped no product code.

**0.2 — `store/` and `cli/` have zero harness coverage, `server/` will be the third, and
this session does not fix that.** Verified: no module under `harness/tests/` imports
`store` or `cli`. That is 2,509 lines, about 40% of product code, including the package
the capture server writes through. The mitigation is honesty, not coverage: the capture
server says so in its own module docstring, and `docs/map.py` stops implying otherwise
Leave lines 37-38 exactly as they are. Insert a blank line and this blockquote after line 38, before "### 0.3":

> **Status, 2026-08-13:** T7 exists and is registered, and it reaches `store/`, `server/`
> and `cli/` — added through exactly the process the batch-script spec's §11 demands:
> argued first, the contract in `docs/GATES.md` amended, every published count reconciled
> in the same commit. All three references in the paragraph above have since moved. D16's
> paragraph was reworded to make its argument without naming a number, so it no longer
> rejects the id by name; the allowlist line that recorded why self-cleaned away the day
> the name came true, which is precisely what that mechanism is for; and
> `server/capture_server.py` now says T7 reaches it, where the docstring this paragraph
> cites once said the opposite. The instruction is left standing as the record of what
> this session was told.
T7 — D16 rejected that id by name and `scripts/docs-audit-allow.txt` records why.

### 0.3 — Writing docs in this repo without blocking your own commit

Empirically verified 2026-08-11 against a scratch copy of the tree, not read off a doc.
The pre-commit hook runs three opsec rules and then the audit in staged mode; exit 1
blocks.

| Construct | Result |
|---|---|
| A path whose first segment is an existing top-level directory, and which does not exist | **BLOCKS** |
| The same path in plain prose, no backticks | **BLOCKS** — backticks are irrelevant to the paths row |
| The same path inside a fenced block, or inside a `#` comment in one | **BLOCKS** — fences are scanned line by line |
| A path under a gitignored tree — `captures/`, `inventory/`, `runs/`, `harness/images/` | **Free.** Gitignored targets are skipped, which is why every capture path below is safe |
| Any path under `server/` | **Free today.** `server` is not yet a top-level name, so the candidate is never resolved at all |
| `pkg/module.name` where the module exists but defines no `name` | **BLOCKS** — the dotted form is read as an attribute claim, so it is a promise the code must already keep |
| `make <target>` inside backticks or a fence, target absent from the Makefile | **BLOCKS** |
| `pkmnscan <verb>` inside backticks or a fence, verb outside the four registered ones | **BLOCKS** |
| The phrase "check" or "checks" followed by 1–2 digits | **BLOCKS**, and there is no allowlist for a phrase. Name a row by its printed label instead |
| A decision id with no heading, or a test id outside the registered set | **BLOCKS** |
| An env var not already present in the code | **BLOCKS**. "Present" means it already appears in a `.py` file, the Makefile, `.env.example`, a script under `scripts/`, the pre-commit hook, or a `.claude` settings file. Grep before naming one — the set is larger than it looks |
| An uppercase alphanumeric 3-4-3-3 hyphen group anywhere | **BLOCKS** — the code-card opsec rule, and it fires *before* the audit, so the message will not mention the docs |
| 20 or more staged lines under `pipeline/`, `identify/`, `geometry/`, `store/` or `cli/` without `docs/specs/batch-script.md` also staged | **Advisory (exit 2)** — prints and allows. Section 5's allocator crosses that threshold, so expect it |

**The escape route for a path you cannot avoid naming**, in order: write it without a
slash ("the position allocator in the store package"); or add a `path  # reason` line to
`scripts/docs-audit-allow.txt` in the same commit, which self-cleans because the audit
blocks the day the file arrives; or defer the reference to the commit that creates it.

**Sequencing rule that falls out of the above, and the single most likely way to waste an
hour: keep the spec-and-cleanup commits free of any file under `server/`.** The moment
one is staged, `server` becomes a top-level name, every other `server/` path in this file
starts being resolved, and the `server/` entry in `docs/map.py` — currently `planned` —
fails the repo map row. Section 6's commit is where all of that lands together.

Pre-flight is `make docs-audit` (whole tree) before staging, then `git add`, then the
hook. The two disagree in both directions and the whole-tree run is the stricter one.

---

## 1. Order of operations

Items are named; do them in this order. Sizes are the diff, not the thinking.

| order | item | size | waits for |
|---|---|---|---|
| 0 | photo-layout-ruling | 3 doc lines | — |
| 1 | false-claim-sweep | 6 edits, 5 files | — |
| 2 | hook-deletion | 2 edits + 2 debts entries | — |
| 3 | allocator | ~25 lines in one built module | — |
| 4 | capture-server | ~400 lines, new directory | 0, 3 |
| 5 | map-flip | ~15 lines | 4, same commit |

Items 0–2 are independent of each other and of the server. They are first because each
one is a false sentence in a file an agent reads as ground truth, and the execution
session is about to become the agent that reads them.

---

## 2. photo-layout-ruling

`POST /capture`'s first line of work is deciding where a photo goes, and the repo
currently answers that three incompatible ways:

- D13, `docs/DECISIONS.md:169`: photos on Mac disk, *organized by set*.
- D6, `docs/DECISIONS.md:86`: photos are *already position-keyed on disk*.
- `identify/sidecar.py:26`, the code that actually reads them: box-keyed,
  `captures/box3/0017.jpg`.

**Ruled: box-keyed.** The reader already parses it and D6's own route,
`GET /photo/<box>/<position>`, already assumes it. Set-keyed cannot serve that route
without a lookup the server has no table for, and it cannot exist at capture time anyway
— the set is not known until identification runs, which is D1's whole point.

Two edits, one commit:

- **`docs/DECISIONS.md:169`** — strike "organized by set". D13's sentence becomes:

  > Inventory state is server-side JSON on the Mac, read and written through the capture
  > server, so the owner's and Fulfiller's devices share one truth. Photos on Mac disk,
  > box-keyed by capture position — see D6.

- **`docs/DECISIONS.md:86`** — delete the word "already", which is false: `captures/`
  holds an empty `ui/` and nothing else. The sentence becomes:

  > Photos are position-keyed on disk — this is display, not new storage.

Rewriting in place is what D16 requires of a decisions entry; do not append a history
note.

---

## 3. false-claim-sweep

Four copies of one false sentence, plus the map's coverage claim. All in files an agent
reads as ground truth, which is why this is not a tidy-up.

### 3.1 — The harness does not gate commits

`grep -c harness scripts/githooks/pre-commit` returns 0. The pre-commit hook runs three
opsec rules and the docs audit. The harness runs from `scripts/stop-gate.sh` at turn end.
Four files say otherwise:

| file | current text | replacement |
|---|---|---|
| `docs/map.py:162` | ``"does": "T1-T6. `make harness` must exit 0 before any commit.",`` | ``"does": "T1-T6. The Stop hook runs it at every turn end; the pre-commit hook does not.",`` |
| `CLAUDE.md:14` | `make harness        # all six verification tests; MUST exit 0 before any commit` | `make harness        # all six verification tests; the Stop hook runs it at turn end` |
| `README.md:29` | ``harness/                   T1-T6. `make harness` must exit 0 before any commit.`` | ``harness/                   T1-T6. The Stop hook runs it at every turn end.`` |
| `Makefile:20` | `T1-T6 verification tests. Must exit 0 before any commit.` | `T1-T6 verification tests. Run at turn end by the Stop hook.` |

Preserve column alignment in all four; `CLAUDE.md:14` and `README.md:29` sit inside fenced
blocks whose columns are load-bearing for readability, and `Makefile:20` begins with a
tab that make requires.

**Do not touch these three, which are true and say something else:**
`docs/GATES.md:5-7` ("Nothing is 'done' until it exits 0 and you have seen the output") is
a working rule addressed to the operator, and no hook can check the second half.
`CLAUDE.md`'s working agreement ("Run `make harness` before you tell me something works")
is the same rule and is also true. `harness/eval/runcache.py:3` states a cost requirement
on the harness, not an enforcement claim.

**The replacement wording is itself conditional and that is accepted.** `stop-gate.sh`
disarms on `PKMNSCAN_GATE=off`, on a missing harness target, on a missing tests directory,
and while any test still carries its not-implemented marker. Saying so in four one-line
fields would cost more than it buys; the script's own `--status` flag is the authority.

### 3.2 — The map's one false coverage claim

`docs/map.py:153` claims `store/queues.py` is `tested_by: ["T3", "T4"]`. Nothing under
`harness/` imports `store`.

The audit cannot catch this: its repo map row validates only that the cited test id is
registered in the harness registry (`scripts/docs-audit.py:1278`). It never checks that
the test reaches the module. So the field is unenforced in both directions, and this
entry would have audited clean forever.

**Audited, all 11 entries, 2026-08-11: ten are true, one is false.** The field is
accurate because of who wrote it, not because of anything checking it. There are also
exactly two silent omissions — `identify/sidecar.py` is exercised by t4 and
`pipeline/decisions.py` by t5, and neither carries the field.

Three edits:

- **`docs/map.py:153`** — strike `tested_by` from the queues entry. Omission is the file's
  existing convention for an uncovered module: 15 of its 25 module entries already omit
  the field. Do not invent an `untested: True` key.
- **`docs/map.py`, the `store/` component entry** — add the honest fact once, on the
  package, between `governed_by` and `modules`, matching the layout the `cli/` entry
  already uses:

  ```python
  "note": "no harness test reaches this package — nothing under harness/ imports "
          "store. `built` above means the code exists, not that it is covered; "
          "docs/DEBTS.md records why that is not being fixed before step 5.",
  ```

  > **Status, 2026-08-13:** that note was written and has since been replaced. T7 reaches
  > `store/` and `server/`, so the sentence it instructed is no longer true and the map
  > says something else now. The instruction is left as the record of what this session
  > did; read `docs/map.py` for what the entry currently says. The convention the bullet
  > above establishes — omit `tested_by` rather than invent a key for "uncovered" — still
  > holds, and `store/queues.py` and `store/cache.py` still omit it.

- **`docs/map.py:75`, the status legend** — currently `built    code exists and the
  harness covers it`. That is the sentence the false claim generalises from, and it is
  wrong for `cli/` too. Replace with: `built    code exists. tested_by names the harness
  tests that reach it, where any do.`

**Do not add `tested_by` to the two omissions.** The field is unvalidated either way, and
completing it by hand builds a more detailed unenforced claim — the exact shape D17 warns
about when it says an index that drifts is worse than none because it is believed. If the
field is ever to be trusted it needs a checker, and a checker is out of scope here and
forbidden by 0.1 anyway.

---

## 4. hook-deletion

### 4.1 — The edits

**`.claude/settings.json`** — delete the `PostToolUse` block whole, including its trailing
comma. It runs `make lint typecheck 2>&1 | tail -20` after every Write and Edit. Because
`make lint` exits 1 make aborts, so `typecheck` never runs at all; because of the pipe the
hook's own exit is 0, so it never blocks. Net effect: five lines of failure text after
every edit, meaning nothing, teaching every session that hook output is noise.

`grep -rn PostToolUse` outside `docs/specs/` returns exactly one hit — the block itself.
No doc claims lint or typecheck runs after an edit, so the deletion falsifies nothing.
Confirm the JSON still parses: the preceding array is already comma-terminated, and the
`Stop` key becomes the last member of the hooks object.

**`.claude/settings.json`, `permissions.allow`** — remove `Bash(make check)`, add
`Bash(make status)` and `Bash(make docs-audit)`. `make check` can never exit 0 while lint
and typecheck are stubs, and nothing automated invokes it, so the grant is a prompt for a
command that cannot succeed. `make status` is what `README.md` and `CLAUDE.md` both tell a
cold session to run first and it was not granted. `make docs-audit` is read-only and this
plan runs it repeatedly.

Do not add `Bash(make audit-history)`: it is a deliberate, slow, once-in-a-while
diagnostic, and a standing grant invites it into routine use, which is against the spirit
of `docs/specs/audit-retirement.md` section 7's rule that it informs retirement arguments
and never makes one.

`Bash(npm run lint)` stays, though it is in the same can-never-succeed category today —
there is no `package.json`. It becomes true at step 7 and removing it is churn.

`.claude/settings.local.json` defines no hooks and grants neither of the two additions, so
there is no duplicate to reconcile.

**Do not leave a `_removed_PostToolUse_note` key behind**, even though the file carries two
such note keys already. The debts entry below is the single record, and keeping it single
is what makes its own claim checkable.

### 4.2 — Two entries for `docs/DEBTS.md`

Match the file's voice: heading, body, a **Cost** line, a **Why not fixed** line. Widen the
file's framing first — its opening scopes it to the audit-retirement review, and both
entries below come from step-5 spec work instead. `docs/DEBTS.md:11-15` re-pins it harder
than the opening sentence does, so both need the widening or neither.

> ### The post-edit hook channel is gone, and step 7 is when it should come back
>
> `.claude/settings.json` used to run `make lint typecheck` after every Write and Edit.
> Both targets exit 1 by design (`Makefile:3` — a target that exits 0 with nothing to run
> is a lie), and under one make invocation the abort on lint meant typecheck never ran.
> Five lines of failure after every edit, blocking nothing, from 2026-08-03 until it was
> deleted on 2026-08-11.
>
> Deleted rather than repointed. Repointing it at the harness costs far more output per
> edit for a check the Stop hook already runs at turn end, and dropping lint's exit 1
> would make `make check` green by lying.
>
> **Cost**: there is now no automatic post-edit signal at all. Zero today, because there
> was nothing behind the channel. Real at build-order step 7, when TypeScript arrives and
> `make typecheck` starts meaning something.
>
> **Why not fixed**: there is nothing to point it at yet. Step 7 should re-add it — at the
> typecheck target alone, not at the composite — rather than rediscovering the question.

> ### `tested_by` in the repo map is an unenforced claim
>
> The repo map row validates only that a cited test id is registered in the harness
> registry (`scripts/docs-audit.py:1278`). It never checks the test reaches the module.
> Audited 2026-08-11: ten of eleven entries were true, one was false — `store/queues.py`
> claimed T3 and T4 while nothing under `harness/` imports `store` at all — and two
> modules that *are* exercised carry no entry. The false line was struck; the field is
> still unenforced in both directions.
>
> Underneath it: `store/` and `cli/` have zero harness coverage. 2,509 lines, about 40% of
> product code, including the package the capture server writes through.
>
> **Cost**: the map can claim coverage that does not exist, in the file D17 argues must be
> audited exactly as hard as it is trusted. The claim is believed precisely because the
> map is otherwise reliable.
>
> **Why not fixed**: a real checker means resolving each test's imports and asserting the
> module is reached — new machinery in the auditor, which the step-5 plan forbids by name,
> and which is the same instinct that spent a full day and eighteen commits on the auditor
> and its docs. The honest interim is the legend fix and this entry.

---

## 5. allocator

D10 says "sequential position assigned at capture". Nothing implements it: a grep for
`next_index`, `next_position` and `allocate` across `store/`, `cli/`, `pipeline/` and
`identify/` returns zero matches. This is the one piece of real engineering in step 5 and
the smoke test exercises it twenty times.

### 5.1 — Where it lives, and its shape

`store/master.py`, on `Inventory`, beside `record_capture`. Not on the session object,
which holds the lock and the atomic replace and no domain logic at all, and not in the
server, which must stay a transport.

**Allocation folds into the write. Do not ship a public "what is next" that a caller then
passes back in.**

```python
def allocate_capture(self, box, *, capture_id=None, photo=None,
                     set_hint=None, metadata_finish=None):
    """Assign the next index in `box` and record the card. Returns (card, created).

    Takes no index: there is no parameter through which a stale read can enter a
    write. `created` is False only when `capture_id` replays a capture already
    recorded.
    """

def next_index(self, box):
    """The index allocate_capture would assign. DISPLAY ONLY — status, run reports."""
```

The argument is already written in `store/__init__.py:22-27`: two writers each reading,
each modifying, each writing back means the second silently erases the first, so the write
re-reads inside the lock, and "re-reading is the half that actually matters". A public
`next_index` fed back into a write is that lost update with a network round trip and a
human hand in the middle of it. Both devices display "next: 17", both post, and the second
lands in `record_capture`'s existing-record branch — which copies the incoming photo, set
hint **and recorded variant** onto the incumbent and returns it, with no log and nothing
reported. One physical card gone from inventory. Note the variant overwrite specifically:
D3 rung 1 forbids even `--variant` replacing a recorded toggle, and that branch does
exactly that to a card which may already be identified.

**Honest limit, state it in the docstring rather than claiming a guarantee:**
`record_capture` remains public and still takes a `Card` carrying an explicit box and
index, because two CLI call sites depend on it — `cli/cmd_identify.py:394` and
`cli/cmd_emit.py:191`. The safety here is that the server never calls it, not that the
seam is absent.

**`capture_id` needs somewhere to live, and today there is nowhere.** `Card` has no such
field, and `Inventory.parse` filters every record through `Card.__annotations__`, so an
unknown key is silently dropped on reload — a retry guard that forgets across a restart is
not a guard. Add `capture_id: Optional[str] = None` to the `Card` dataclass. It is
additive and backward-compatible: existing records load with `None`, and the filter means
old files need no migration. This is the one sanctioned edit to a built module's data
shape in this plan; it is justified because the alternative is a guard that does not hold,
and it is small enough to review in one line.

### 5.2 — The rule

**`next = 1 + max(index of every card in that box, over all states, default 0)`.** A
high-water mark. Not count+1, not first-free.

Indices are 1-based and that is forced, not chosen: section and card are derived from the
index, so index 0 labels a slot that does not exist. **The arithmetic used to be spelled out
here as `(index - 1) // 25 + 1` and `(index - 1) % 25 + 1`, and D10's amendment made that a
special case rather than the rule** — dividers are declared per box now, and the fixed
25-card window is only what a box that declares none renders with. `pipeline/join.py:Position`
is the formula; this file names it and does not restate it.

*count+1* agrees with the high-water mark for sold cards — nothing deletes a record, `sold`
is a state — and fails the moment anything does delete one, silently, through the upsert
branch described above. *first-free* contradicts D10 in its own words: sold cards leave
permanent gaps, and the next captured card goes on the end of the stack because that is
where the operator's hand puts it.

**Coerce every field you compare or compute on.** `Inventory.parse` reconstructs cards
straight from JSON with no coercion at all and there is no post-init hook, while
`position_key` coerces with `int()`. So a record whose box was written as a string is
invisible to a bare `c.box == box` filter and the allocator hands out an occupied index —
and coercing only the box is not enough, because that same record's `index` is also still
a string and the high-water arithmetic then fails on it. Filter on
`int(c.box) == int(box)` **and** take the maximum over `int(c.index)`. A record whose
index will not parse is a refusal naming the position, not an exception escaping inside
the lock.

Related, and worth knowing before you meet it: `Card` declares `box` and `index` as
required fields with no defaults, so a record missing either raises from `Inventory.parse`
and takes down `Store.read()` — which means every route, not just the write path. Do not
add a repair path for it; just know that a hand-edited inventory file fails loudly and at
the front door.

### 5.3 — Sections, and the constant

Do not write a new formula or a new constant. `pipeline/join.py:Position` derives section,
card and the label, and the server calls it — now with the box's own divider layout, since
D10's amendment made sections per-box: `Position(box, index, sections)`. `CARDS_PER_SECTION`
survives in that file as the default for a box that has declared no layout, which is what
keeps every label written before boxes existed byte-identical.

There is no cycle: `pipeline`, `identify` and `geometry` import `store` nowhere. And the
label is the one part of this path with harness coverage — `harness/tests/t3_join_coverage.py`
asserts the rendered label verbatim — so re-deriving it inside the server would move a
covered line into the directory that by 0.2 has none.

### 5.4 — Edge cases

**Empty box**: `default=0` yields 1. No branch, no error.

**A box that does not exist**: creation is implicit, and it stays implicit even though a box
is now an object. **This paragraph used to read "there is no box object anywhere in `store/`,
only a flat dict keyed by box and index", and D20 built one** — `store/master.py:Box`, with a
name, a divider layout, an open/closed lid and a capacity frozen at sealing. D20 quotes this
very sentence as the state it was correcting, so it is rewritten here rather than left to
contradict the entry that cites it.

What did not change is that capture never demands a registry entry first: `allocate_capture`
calls `ensure_box`, which creates an unnamed, undeclared, open box if the registry has never
seen the number. Requiring registration would make the registry a second thing to keep in
step with the cards, and the v1 migration produces exactly this shape, so the two paths
cannot diverge. A **sealed** box is the one case that refuses — `BoxClosed`, checked before
an index is computed, because capacity was frozen at the fill and one more card would falsify
every fraction drawn from it.

The hazard that creates is a typo: `box=33` for a card going into box 3 is a valid int, a
new box, index 1, a real photo, and a real listing, and nothing downstream can tell. The
allocator reports it for free — when the computed index is 1 the box is new — and the
response carries that fact so the app can require a confirmation on the first capture into
a box. It catches the first typo only; a repeated typo into the same phantom box returns
index 2 and looks ordinary. Record that limit, do not paper over it.

**Undo is not step 5.** The step 5 line in `docs/GATES.md` does not contain it; the step 7
line does. Do not build a void route, and do not add void fields to the card record.

Note for whoever builds it, because the allocator's shape already constrains the answer:
under a high-water mark, an undo that *deletes* the record reuses the index and an undo
that *tombstones* burns it. That is a live disagreement — reuse keeps index and physical
slot aligned when the card never entered the box, burning avoids ever pointing an old
index at a new card — and D10 speaks only to renumbering, not to reuse. Settle it at step
7 with the capture app's actual undo window in hand, not now.

---

## 6. capture-server

### 6.1 — Framework: stdlib, decided

`server/capture_server.py`, running `http.server.ThreadingHTTPServer`. No addition to
`requirements.txt`.

`requirements.txt` is `anthropic`, `Pillow`, `numpy` and a block naming what it
deliberately omits — D15 makes that its job, so every addition is a recorded decision.
`Makefile:44-47` sets the rule this inherits: a step-away tool that needs `make venv`
first is not a step-away tool, which is why the audit and status targets run bare
`python3`. `make server` is the same kind of tool, started by the owner and reached by a
non-technical Fulfiller. The load is two devices on a LAN. Python is 3.9.6, so write for
3.9: `from __future__ import annotations`, no `X | None`, no `match`.

### 6.2 — The module docstring carries the contract

At the density of `store/__init__.py`, and it must state three things the map cannot:

1. The route list and status codes.
2. That every write goes through the store session and the server never touches disk state
   directly.
3. **That nothing tests this file.** Per 0.2, verbatim in the docstring: no harness test
   reaches `server/`, `store/` or `cli/`, so a green harness says nothing about this
   module.

### 6.3 — The sidecar contract, which is the part that can fail silently

The server writes; `identify/sidecar.py` reads. One-way, no test on either side, and a
mismatch surfaces at identification time, which is when money is spent.

**The capture root is `captures/cards/`, not `captures/`.** This matters more than it
looks. `scripts/screenshot.sh:24` writes UI renders as `.png` into `captures/ui/`, and the
scanner walks its root recursively and turns every photo-suffixed file it finds into a
capture and therefore a paid Batch request. Rooting at `captures/` would bill every
screenshot the first time someone ran both tools. Nothing today defines a capture-root
constant; define one in the server module, put nothing else beneath it, and leave `ui/` as
a sibling. `captures/` stays gitignored, so nothing here needs a new ignore rule.

**Filename**: `captures/cards/box<N>/<index padded to 4>.jpg`, sidecar alongside with a
`.json` suffix. Lowercase `box`, no separator, no dots or suffixes in the stem. The reader
matches and removes the box marker first, then takes the *last* run of digits in what is
left — so a stem like `0017.2` parses as index 2. Zero-pad to 4 because the scanner sorts
by path string. One extension only, `.jpg`, so the photo route can find a file from box
and index alone — which means the client posts JPEG bytes and the server verifies the
magic bytes and refuses anything else. It must not convert: re-encoding at capture time is
forbidden by 6.6, and writing a PNG under a `.jpg` name is the kind of lie that surfaces
three steps downstream.

**Keep it flat.** No section directories, no date directories between the capture root and
`box<N>/`.

**The money rule: nothing else with a photo suffix may ever be written under the capture
root.** No thumbnails, no previews, no `-original` copies.

**JSON keys — write these three, exactly:**

```json
{"box": 3, "index": 17, "set_hint": "SV09: Journey Together", "variant": "reverse_holo"}
```

- `box` is read from the `box` key only.
- `index` is the accepted name for the position. **`position` is an alias for the same
  integer** — a trap worth naming, because `store/master.py`'s `position_key` returns the
  string `"3/17"` for the same concept. Writing `{"position": "3/17"}` fails the integer
  coercion and falls back to filename recovery. On its own that fallback is reported. But
  every sidecar this spec writes also carries `box`, and with a valid `box` present the
  reader takes the sidecar branch on the box alone: the capture is labelled as having come
  from its sidecar while the index in fact came from the filename, and no problem is
  recorded at all. **That is the real reason never to write `position`** — the mistake is
  undetectable in exactly the configuration the server produces. Write `index`, an int.
- `set_hint` accepts `set_hint`, `set` or `hint`; write `set_hint`.
- `variant` accepts `variant`, `metadata_finish` or `finish`; write `variant`, and only a
  member of the finish enum — a value outside it is reported as a problem, never coerced.
- Omit `set_hint` and `variant` entirely when the toggles are unset. The reader treats a
  null and an absent key identically, so this costs nothing either way; write neither, so
  the file records only claims the operator actually made.

A missing or malformed sidecar is explicitly *not* a failure — the reader recovers the
position from the filename and treats it as equivalent, because the same server writes
both. That is a safety net, not a licence to skip the file.

### 6.4 — Routes

The surface is the step 5 line in `docs/GATES.md` and nothing else:

> 5. Capture server: `POST /capture`, position-ordered filenames, JSON sidecars (position,
>    box, set hint, variant), `/status`, `GET /photo/<box>/<position>`, `GET`/`PUT`
>    inventory state shared across devices.

Port 8000, matching what `make server` already prints. JSON in, JSON out, except the photo
bytes.

**Overtaken in one detail on 2026-08-29 (D43): 8000 is the MAIN checkout's port, not every
checkout's.** The store has always defaulted to the checkout the code runs from, so each git
worktree has its own inventory — and a shared port meant whichever server won the bind
answered every tree's UI, in one direction driving the owner's real inventory from a branch
and in the other writing real capture photographs into a directory deleted with it. A linked
worktree now derives its own port; the main tree is unchanged, so this line stays true where
anyone reading this spec is standing. `server/ports.py` holds the derivation.

**`POST /capture`** — `application/json` with base64 image bytes, not multipart: the stdlib
has no multipart parser worth using on the path that allocates positions, and base64 costs
33% on a LAN. Body carries `box` (required), `image` (required), optional `set_hint`,
`variant`, `capture_id`. There is no server-side "current box" — box, hint and variant are
client state resent on every capture, which is the only way two devices share one truth
without a session. Returns 201 with box, index, the rendered position label, and whether
the box was new.

`capture_id` is the retry guard. Wifi blips between commit and response, the app retries,
and without it a second index is burnt and one physical card holds two records. Replay
lookup is a linear scan over the card dict — fine at this scale, say so in a comment — and
two cards carrying the same id is a refusal, matching the package's temperament of
refusing rather than coercing.

**`GET /status`** — lock-free, side-effect-free. Counts, the next index per known box, and
whether the store directory exists. **Do not probe the lock**: the only primitive exposed
is an acquire, and taking it to report on it makes a read route a writer.

**`GET /photo/<box>/<position>`** — the photo bytes, 404 when absent. D6's route, and the
review queue and pull modal both reuse it.

**`GET /inventory` and `PUT /inventory/<box>/<position>`** — the shared-truth route. `GET`
returns the whole card map. `PUT` is per-position and takes one card's mutable fields; it
is deliberately *not* a whole-document replace, which would have to rebuild every card
from a client's stale snapshot and is the lost update of 5.1 with a bigger blast radius.

`PUT` must not create cards. `record_capture`'s first branch fires when the key is absent
and creates a new card from whatever it is given, so a `PUT` naming a position that does
not exist would invent one — it does land in the history file as a capture event, but the
caller gets a success and nothing flags it. Guard on the key existing and refuse
otherwise. The inverse is also true: the existing-record branch does *not* log, so a
legitimate correction leaves no history entry. Record that as a known gap rather than
adding a log call to an uncovered module. Settable at step 5: `set_hint` and `variant` —
and note neither can be *cleared* back to "no claim" through this path, because that
branch only assigns when the incoming value is not None.

**Uniform error body**, because step 7 surfaces these strings and `docs/DESIGN.md`'s copy
rule reaches them: what happened, and what to do next. Reserve 500 for bugs; every
anticipated condition gets its own code.

**CORS**: the step 7 app is a different origin and the Fulfiller's device is on the LAN.
No credentials ever, answer preflight. No auth and no TLS — LAN tool, two known devices,
D13 and D5. State that as a decision so nobody adds a login screen.

**"Allow any origin" was this spec's instruction and it opened a hole; corrected
2026-08-23.** Reads still allow any origin, so `GET /photo/<box>/<index>` stays embeddable —
the review queue and the pull preview both depend on that. **The three mutating verbs do
not.** With `Access-Control-Allow-Origin: *` advertised alongside `DELETE`, any page open in
the owner's browser could preflight and then send `DELETE /inventory/3/17`, which is D10's
hard delete of the record, the sidecar and the photo with no backup. Nothing read `Origin`.
That is a CSRF hole rather than a missing login, and the fix is an allowlist rather than the
auth this section rightly still refuses.

**An absent `Origin` is allowed to write, and that is load-bearing.** A browser page cannot
omit the header; `curl`, `./pkmnscan` and the harness all do. Requiring it would kill every
command-line path in the project at once — measured, not assumed: mutating the check to
require the header turns eleven T7 assertions red, eight of them in the concurrency section
that sends no origin at all.

**`PKMNSCAN_ALLOWED_ORIGINS`** extends the two defaults — `http://localhost:5173` and
`http://127.0.0.1:5173` — and cannot replace them. Comma- or whitespace-separated; entries
are lowercased and lose a trailing slash, because that is what a human types. A port is
never defaulted in, so `http://localhost` and `http://localhost:80` are different and the
error is toward refusing. **`*` is not a wildcard here**: the list is compared by exact
string, so setting the variable to `*` refuses everything rather than re-opening the hole —
asserted in T7, because a wildcard sneaking back through configuration would undo the whole
control silently.

### 6.5 — Concurrency

`store/__init__.py:19-20` already rules it: the server is a second writer, not a second
owner. Concretely — the server holds no authoritative copy of anything between requests.
No cache, no dirty set, no periodic flush.

1. Reads take no lock, and the session's read already takes none. There is no shared mode
   — the lock is exclusive only — so adding one would serialise both devices' polling
   behind every write, and a read that lost the race would stall for the full 30-second
   timeout and then raise. Not a deadlock; just the worst available way to answer a poll.
2. Every write goes through the session's write context and nothing else.
3. Nothing is written when an exception escapes the block — the writes happen after the
   yield. Do not catch-and-continue inside it; swallowing an error there commits a partial
   mutation. Know the limit: the guarantee is per *file*. The session replaces four JSON
   files and appends history after the yield, each atomically, so a crash between two of
   those replaces leaves the set inconsistent. Nothing here makes that more likely — just
   do not write code that assumes a transaction.
4. Allocation happens inside the same lock as the record. Non-negotiable, per 5.1.
5. Never hold the lock across a network wait. Decode the whole body first, then open the
   session for the writes.
6. No background threads mutate the store.

The lock is an `flock` on a fresh handle per call, so two threads in one process contend
exactly as two processes do — which is correct, and means a threading server needs no
extra in-process lock. One caveat pointing the other way: the atomic replace names its
temporary file by process id, not thread id, so two threads writing at once would collide
on a single temp path. The lock is what prevents that, which is a further reason nothing
may write outside it.

### 6.6 — What this session must not build

No UI, no HTML, no bundle — the app is step 7 on its own port. No camera code, no device
picker. No auto-capture or motion state machine — Gate C. No detection, cropping,
downscaling or re-encoding at capture time — that is batch-time work. No identification:
no API key read, no Batch call, the server never spends money. No pricing, no CSV, no
join, no catalog. No mark-sold, no pull, no Fulfillment routes. No undo route. No
review-queue clearing — the queues only grow until step 7, and `store/queues.py` says that
is correct. No writes to the answer cache. No re-shoot route. No SQLite — D13 settles
inventory as JSON, and D15's SQLite is the catalog at step 9. No renumbering, compaction
or gap-filling: D10, and it is the one operation that would make the history file lie.

And per 0.1: no edits to `scripts/docs-audit.py`, for any reason.

### 6.7 — What to settle while building

**`make server` blocks.** Every other target returns. A foreground server is conventional
and correct, but an agent that runs it in the foreground hangs its own turn, because the
Stop hook runs the harness at turn end and never gets there. Keep it foreground; say in
the help text that agents background it.

---

## 7. map-flip

Lands in the same commit as section 6, and only then — per 0.3, this is the commit where
`server/` becomes a real top-level name.

- Flip the `server/` entry from `planned` to `built`, and give it a `modules` list. Note
  the orphan rule only scans a component that *has* one, so adding the list is what puts
  the new package under the rule at all.
- Add D10 to the entry's `governed_by`, and D7 if the code cites it. D17 requires
  `governed_by` to be a superset of the decision ids the file's own comments name, and the
  repo map row enforces that direction.
- Move step 5 to `done` and step 6 to `next` in the build order. Exactly one step is
  `next` and the audit enforces it.
- `docs/GATES.md`'s build order is the other half of that pair; the two disagreeing is
  what one commit on 2026-08-11 already had to fix.
- The allocator goes in the existing `store/master.py`, so the store entry's `modules` list
  needs no new member.

Expect the audit to walk you through anything missed here: it produces one blocking
finding at a time, each naming the file to fix.

---

## 8. What this plan does not do

- It adds no harness coverage. 0.2.
- It adds no checker for `tested_by`. Section 3.2 and 0.1.
- It builds no undo. Section 5.4.
- It does not fill in `docs/DESIGN.md`. That is step 6, its token block is still a
  template with no values, and it is owner input rather than agent work — worth starting
  in parallel with this plan, because Gate B runs through it.
