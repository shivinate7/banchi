# Known gaps, deliberately unfixed

Findings recorded rather than repaired. Each says what is wrong, what it costs, and why it is
not fixed. This file exists so a green `make docs-audit` is not read as "the auditor is
complete" — it means the checks that exist, passed.

Not a backlog to burn down on sight. An entry leaves when someone argues it should, the way
`docs/DECISIONS.md` entries are argued.

**Grouped by the work that would close them, not by when they were found** (2026-08-30). The
old chronological order hid the fact that five separate entries were one defect, and put two
one-line UI questions eleven sections apart. Each cluster names what unblocks it.

**Swept 2026-08-30**, from 1,401 lines. The majority was closure narrative for defects nobody
can hit any more; it is in git. Every surviving entry was re-checked against the tree, and
**three were wrong**:

- `check dispatch` said `--self-test` is "on no gate at all: not the pre-commit hook, not
  `make check`". `make check` has run `audit-self-test` since 2026-08-24 — recorded 900 lines
  further down in this same file.
- The `fixtures/` entry called a commit-time byte check "the tractable route, named rather
  than built". `scripts/githooks/pre-commit` has done exactly that since the repo's first
  commit.
- The registry table claimed six fields were read by nothing. Five now have consumers.

**The lesson, which is this file's own failure mode turned on itself:** an entry naming a
residue is a claim about the code, and no row of `make docs-audit` reads a claim made here. A
cluster is worth what a human re-checking it is worth, and that had not happened in
seventeen days.

---

## 1 — The reverse direction: five checks walk docs→code and never back

**One defect, five sites.** Each row proves everything *published* is consistent, and none can
see something real that was never published.

| check | what is invisible | live example |
|---|---|---|
| `tested_by reach` | a module a test exercises, carrying no claim | `store/cache.py` |
| `env vars` | a real variable documented nowhere | `PKMNSCAN_ALLOWED_ORIGINS` |
| `reason codes` | a reason the pipeline emits and nothing publishes | `rarity_claim_mismatch` |
| the game registry | a field whose consumer arrived, roster unstruck | five of six, silently |
| `governed_by` | the map may know less than the code, never more | three illustrative citations |

**THE BLOCKER IS ONE DECISION, AND IT IS THE SAME ONE FIVE TIMES.** Finding "a real
environment variable", "a reason rather than a ladder stage", "a module a test covers" each
needs a heuristic, and D16 puts a heuristic on a *blocking* row out of bounds — a row that
guesses and stops commits is how a gate gets switched off. The honest options are an
**advisory severity** or an **explicit roster the module publishes**.

**THE ROSTER OPTION IS NOW COSTED, BECAUSE IT WAS TAKEN FOR ONE OF THE FIVE (2026-09-05).**
`pipeline/variant.py:LADDER_REASONS` and `pipeline/routing.py:ROUTING_REASONS` publish the
thirteen review reasons, and `reason emissions` is a set comparison rather than a guess. The
whole cost was **two tuples and one runtime assertion** — no new concept, no severity change,
and `UNPRICEABLE_REASONS` had already made the idiom native to that file. Cheaper than the
paragraph above assumed.

**Two of the five are closed, by different means, and the difference is the useful part.**
`env names` needed no roster at all: `PKMNSCAN_*` is an exact naming convention, so the code
side is *already* enumerable and only the direction was missing. Reasons had no such
convention — `variant.py` spells finishes, ladder stages and reasons identically, eight of its
fourteen constants being non-reasons — so there the set had to be declared. **Ask which case
you have before reaching for a tuple:** where a convention already enumerates the set, a
roster is ceremony; where it does not, a roster is the only honest answer.

**What is still open is the other three**, and one of them may not want this shape at all: a
roster of "modules a test covers" would be a second place to maintain what `tested_by` already
says. **Fanning agents at these five separately produces five different answers to that one
question.** Settle it in a decision entry first; afterwards they are five independent edits in
five different modules.

**`tested_by`.** 39 claims, every cited test reaches the package it names. `store/cache.py` is
reached by T7 through a session, asserts nothing of its own, carries no claim, and
`docs/map.py` says so at the entry. `store/queues.py` was the second case until 2026-08-22,
when `check_queue_supersede` began asserting `queues.apply_run` and the entry gained the claim
it had earned — **nothing detected that; a human did.** Closing it means ruling that "a test
imports it" equals "a test covers it", which is what the row's own name refuses to say.

**`env vars`.** Walks docs→code only. Found 2026-08-23 by a test author, not by the audit:
`PKMNSCAN_ALLOWED_ORIGINS` — the allowlist standing between an unrelated browser tab and a
hard delete — existed for a day and a half documented nowhere while the row read "all real".
So did `PKMNSCAN_EXPORTS`. **The part worth keeping is the comment that sat above one of
them**, asserting in prose that the variable was documented the same day and that a blocking
check would fail a commit otherwise. Both halves false, the second about the very mechanism it
invoked. That comment is a correction now, kept where the next person looks.

**`reason codes`.** Four reconciliations, all starting from the labels or the doc. Found
2026-08-23 live: `rarity_claim_mismatch` was defined in `pipeline/variant.py`, emitted by the
ladder, carried by neither `REASON_LABELS` nor `docs/DESIGN.md` — and the row read **green**.
Had it fired, the queue would have drawn a bare machine string, the exact outcome the two-size
label rule exists to prevent. The fifth direction needs telling a reason from a ladder stage
by walking the AST for `Resolution(stage=REVIEW, reason=NAME)` — deterministic and
blocking-grade, but coupled to that call shape; or the roster `pipeline/routing.py` already
half has in `UNPRICEABLE_REASONS`. The row reads **14 enumerated, 14 labelled** on 2026-08-30:
twelve when the defect was live, thirteen after the hand repair, fourteen now. Every move was
made correctly by a session that remembered.

**The registry.** Four audit rows sweep `pipeline/games.py` and every one compares it against
the *exports*. Nothing compares it against the *code*, so a field can be perfectly consistent
and entirely inert — **and can stop being inert without anything saying so.** Re-walked
2026-08-30:

| field | 2026-08-23 | 2026-08-30 |
|---|---|---|
| `located`, `card_aspect`, `crop_bands` | closed | closed |
| `finish_by_rarity` | nothing | **`app/src/CaptureScreen.tsx` unions it over the claimed rarities. D23's chip narrowing is built** |
| `product_line` | nothing | **`pipeline/join.py`, `cli/resolve.py`, `pipeline/pricehistory.py`. D25's "real reader" is built** |
| `product_line_rarities` | nothing | **`pipeline/join.py` narrows a claimant's rows by it** |
| `rarities` | emptiness guard only | **validated at `identify/sidecar.py`, checked at `server/capture_server.py`, rendered as the stack claim** |
| `prompt` (per-card) | nothing | **still nothing — see cluster 3** |

D22 says "a field no consumer reads is a field nothing keeps honest". The correction is that
nothing kept the roster of unread fields honest either.

**`governed_by`.** Enforced one way: the map may not know less than the code's own citations,
and may say anything beyond them. Three files are listed under decisions they do not implement
— `scripts/docs-audit.py` names `D2` in a comment about citations, `scripts/decision-context.py`
names `D2` and `D3` as worked examples. Each is labelled as such in the map; the expensive side
would be the rule guessing which citations count.

---

## 2 — The map's reach

**Unblocked and small. Cluster 1's `governed_by` row belongs here too; it is filed there
because it shares that cluster's decision.**

### The orphan rule cannot see an extensionless file, and those are the three enforcement seams

`scripts/docs-audit.py:scan_plan` rejects any `source_suffixes` member not starting with a
dot, so no declaration can reach a filename without an extension. Recorded 2026-08-13 as a
thought experiment — *"creating a second extensionless hook beside it — a `pre-push`, say —
left the row reading `ok repo map` at exit 0."*

**D42 then committed that exact file.** `scripts/githooks/pre-push` and
`scripts/githooks/reference-transaction` arrived 2026-08-29 and the rule was silent for both;
they are in `docs/map.py` by hand and nothing would have failed had the author forgotten. The
same commit added `scripts/githooks-selftest.sh` one directory up, which carries a declared
suffix and duly **failed the commit** until it was described. **One commit, both outcomes: the
rule's coverage is decided by whether a filename happens to have a dot in it.**

**What it now protects is what moves the priority.** The unscanned directory held one file
when this was written. ~~It holds three — `pre-commit`, `pre-push`, `reference-transaction`~~ —
**it holds five.** `post-merge` and `post-checkout` arrived afterwards with the `make hooks`
staleness reminder, and neither was written into `docs/map.py`. So the sentence below —
*"a fourth sibling's arrival is not [caught]"* — was not a prediction. It was already a
description of what had happened, and it happened twice more before anyone counted.

**That half is closed as of 2026-09-05.** `scripts/docs-audit.py:check_hook_roster` compares
the directory against the `scripts/` entry's `modules` in both directions and blocks.

**A SECOND, WORSE HOLE IN THE SAME DIRECTORY WAS FOUND WHILE CLOSING THE FIRST.** `make hooks`
COPIES these files into `.git/hooks-armed`, and nothing kept the copy in step — so the armed
`pre-commit` sat **four days** behind a merged sigil check (D92) and every commit in this
clone skipped it while reporting clean. Worse than an unlisted hook, because the reminder that
was supposed to catch it already existed: `post-merge` and `post-checkout` print one, and it
fires only on pull or branch switch and scrolls away. `pre-commit` now compares its own armed
copy against **main** before any other rule, and **`PKMNSCAN_HOOKS=off`** is its bypass.

**Why main and not the working tree**, since the tree is the obvious comparison: a branch
legitimately editing a hook differs from its armed copy by definition, so a tree comparison
fires constantly, and the one command that silences it — `make hooks` — installs that branch's
UNMERGED hooks as the gate for every worktree in the clone. That is a worse outcome than the
staleness. So it blocks only where the armed copy is behind main *and* this tree matches main,
which is precisely where the fix it prints is safe. It is
deliberately NOT the widening this section proposes below: the suffix rule is doing real work
everywhere else — it is what keeps `views.txt` and a stray `README` from being conscripted into
demanding entries — and repealing it repo-wide to repair one directory is the larger change.
One directory's roster against one directory's entries.

**What is still open here is the general rule, not the hooks.** A sixth enforcement seam
somewhere else with no extension is still invisible, and `check_hook_roster` will not see it,
because it looks in exactly one place.

**The fix exists a few hundred lines away.** `code_haystack()` reaches that same file by
handing `_walk` the whole filename as a suffix. Not done because it changes what
`source_suffixes` means; `docs/map.py` records the hole at the `scripts/` entry.

### An entry proves a file is described, never that the description is true

165 hand-written lines. A `does` describing the wrong file passes exactly as well, and there
is no equivalent fix — an import is in a parse or it is not, a sentence about what a file does
is neither. Two specifics: **a stale cross-reference in prose is invisible to every row** (the
two orphan-rule entries each described the other's coverage, written in one run by different
hands, and nothing would ever have told either); and **`.json` is deliberately outside `app/`'s
suffixes**, since including it would conscript `app/package-lock.json` — so `app/package.json`,
holding the npm scripts `make lint`, `make typecheck` and `make design-check` all run through,
has no entry.

---

## 3 — The claim chain

**Three entries. The first two overlap in files; none is parallel with another.**

### A capture-time claim crosses ten hops and nothing binds them together

Recorded 2026-08-22 from the multi-game work (D21-D25). Each operator claim is one value
carried by hand through independent restatements; the chain is the finding:

1. `app/src/CaptureScreen.tsx` — the control and its client state
2. `app/src/types.ts` — the shape the wire speaks
3. `app/src/server.ts` — the body `POST /capture` sends
4. `server/capture_server.py` — the route pulling the field off it
5. `server/capture_server.py:sidecar_payload` — the JSON beside the photo
6. `server/capture_server.py:PUT_FIELDS` — what the correction route may change
7. `store/master.py:Card` — the dataclass field
8. `store/master.py:Inventory.parse` — the reload filter
9. `store/master.py:allocate_capture` — the keyword pass-through
10. `identify/sidecar.py` then `pipeline/join.py` — the consumer that reads the claim

**Hops 4-10 were bound on 2026-08-23** by `CAPTURE_CLAIM_FIELDS`, which drives
`record_capture`'s upsert, `allocate_capture`'s pass-through, `sidecar_payload` (via
`CLAIM_WIRE_NAMES`) and `PUT_FIELDS` (derived, no longer a literal), with an import-time
assertion that every name is declared on `Card`. T7's `check_capture_claim_chain` iterates the
tuple, so a new claim is covered the day it is added.

**What is still unbound.** The three app-side hops, permanently: no Python constant reaches a
`.tsx`, and `make typecheck` sees a field *added* to `app/src/types.ts`, never one omitted.
And **a fourth restatement** — `cli/cmd_identify.py` builds a `master.Card(...)` literally
rather than through `allocate_capture`, so it carries the claim names by hand. Correct today,
unbound tomorrow; the site says so in a comment. **That one IS closable** and is the only
tractable half.

**Cost, and it is paid at the wrong moment.** Every symptom appears at the far end — a claim
missing from a sidecar, a finish reverting after a correction — and debugging starts at the
screen. Gate B's six defects included one of this family: review answers written by a route
nothing on the join path consumed, which took a real run to find.

### The operator's `note` never reaches the model

`identify/prompt.py:user_text` takes `set_hint`, `with_crops`, `strategy` and `rarity_claim`.
It takes no note. The note is carried faithfully everywhere else — `identify/sidecar.py`
reads it, `cli/cmd_identify.py` records it, `CAPTURE_CLAIM_FIELDS` keeps it — and the one
consumer that could act on it never sees it. **It is the whole point of the field for `misc`**,
the game naming a card the model most needs help with, where the note stands in for a set hint
that does not exist.

**Why not threaded through `set_hint`.** That rides on templates the file owns
(`user_with_hint`, `hint_clause`), and smuggling a note down that path tells the model the note
is a stack label. Doing it properly means `Profile` growing a note clause and `user_text` a
parameter — a prompt-contract change with its own fingerprint questions, since
`prompt_fingerprint` hashes both user turns and T1's recorded scores are evidence about the
bytes that exist today.

### `app/src/readiness.ts` is a second `blocking`, and nothing reconciles the two

`app/src/readiness.ts:owed` is a second implementation of `pipeline/decisions.py:blocking` so
`#/pricing`'s ready line settles on the keystroke that satisfies it, with no round trip — D54's
choice, and the right one for a line whose whole value is that it is instant. **Its header
claimed an `emit readiness` row in `scripts/docs-audit.py` and a Makefile target,
`readiness-agreement`, until 2026-09-02, and neither has ever existed.** `OWED_REASONS` was shaped as a flat
literal for a parser nobody wrote.

**What it costs.** The two can disagree and nothing says so: when `blocking` gains a refusal,
the line keeps saying *Pricing is answered* while `emit` refuses, and the operator learns it
from the emit's stdout. The one live defense is the roster on `GET /pipeline/pricing`, which
asks the Python that actually refuses — so a chip and the line can disagree, and the chip is
the one that is right.

**Why not fixed.** The honest check reconciles a vocabulary — `OWED_REASONS` against the
reasons `blocking` can return — and `blocking` builds its reasons as sentences rather than off
a tuple, so the row needs a roster the Python does not publish. That is cluster 1's decision
again, asked of one more module. Until it is settled the header says nothing audits it, which
is the claim this file exists to keep true.

### ~~The eleventh hop is the fixtures, and adding `product` broke four tests nothing runs~~ — CLOSED 2026-09-05

**The chain above has one more hop than it lists, and D101 walked ten of the eleven.** Adding
`product` to `GameRegistry`, to `do_put_box_claims` and to `BoxOps`'s claim editor was correct
everywhere the list names. What it did not touch is the STUBBED COPY OF THE WIRE that every
browser spec carries — `app/tests/inventory.spec.ts`'s `GAMES`, and the same fixture in
`capture-undo.spec.ts` and `capture-claims.spec.ts` — none of which grew `products` or
`product_game`.

**What that cost, measured on `46160bf` before anything here was changed: 8 of 78 cases in
`inventory.spec.ts` failed, and the suite took 58s instead of 18s** because six of them were
30-second timeouts. `BoxOps` wrote the missing `products` — `undefined` — over the `[]` its
state starts as, the next read of `productList.length` threw inside the editor's render, and
the subtree left the DOM. Playwright reported `element was detached from the DOM` and named
nothing else. Four of the eight are the box-claims cases: **the tests over the very control
D101 added were the ones it broke.**

**It merged green, and the reason is structural.** `app/tests/` runs under `make design-check`
alone, which is deliberately off the commit path — `make check` runs the nine Python tests, the
audit, lint and the typecheck, and none of them starts a browser. So the failure was invisible
to everything a session or a hook looks at, and it stayed invisible for as long as nobody
happened to run the browsers.

**Fixed in three places, and only one of them is the fixtures.**

- `app/src/BoxOps.tsx` writes `registry.products ?? []` and `registry.product_game ?? null`.
  The comment three lines above it already promised exactly this — *"A registry that answered
  no products is the same 'not drawn'"* — and the code did not keep the promise. An older
  server is the real shape this defends against; a stub is how it was found.
- The three `GAMES` fixtures carry both fields.
- **All three are annotated `: GameRegistry`, and that is the guard.** They were object
  literals handed to `route.fulfill` through `JSON.stringify`, so nothing had ever compared
  them to the type they imitate. `app/tsconfig.json` includes `tests`, so the annotation puts
  them behind `make check`'s typecheck — **on the commit path**, where the browsers are not.
  Mutation: delete `products` from the fixture and `tsc --noEmit` reports
  `Property 'products' is missing in type ... but required in type 'GameRegistry'`. The next
  field added to that wire is a failed commit rather than a silent crash.

After it: **111 of 111 across the four spec files, then 163 of 163 across six.**

**What is NOT closed.** Two `/games` stubs remain untyped inline literals — `nav.spec.ts:114`
and `run-panel.spec.ts:411`, both `{ games: [] }` — and they are left that way on purpose:
their point is a registry that answered nothing, which is a state worth stubbing, and the
`?? []` above is what makes it safe.

**And the general form stands.** Six of the eighteen spec files now import their fixtures'
types from `app/src/types.ts` — these three, plus `orders`, `pricing` and `shipping`, which had
done it from the start and are the reason it was already this repo's habit rather than a new
idea. **Twelve do not**, so
the next field added to a wire can do this again in any of them. The remedy is the same
annotation, one file at a time; it is a session's work rather than a decision, and what makes
it worth doing is that the annotation moves the failure onto the commit path, where nothing
else about these tests is.

---

## 4 — Criteria and evidence: nine ways a row goes quiet

Recorded 2026-08-11. **One file (`scripts/docs-audit.py`) and one spec
(`docs/specs/criteria-binding.md`), so this parallelizes as a focused pass and not across
agents.** Re-checked 2026-08-30: `EVIDENCE_SOURCES` is still three bare literals nothing
resolves.

- **`criteria evidence` can go silent.** If the score file's `test` value stops matching the
  filename-derived key, the row compares nothing and still reports `gate field published`.
  Trigger is narrow — hand-editing `NAME` in `harness/tests/t1_id_eval.py` — but there is no
  ADVISORY downgrade for the "could not look" state. First thing to build in
  `docs/specs/criteria-binding.md`, because the threshold fix walks straight into it.
- **It never opens the value it names.** `holdout_accuracy: null` — a run that measured
  nothing — still reports `gate field published`.
- **`Pass:` matching is narrow and one-sided.** `startswith("Pass:")` misses `**Pass**:`, the
  spelling `docs/GATES.md` itself uses; absence is deliberately not a finding, so a bolded
  stale claim is exempt. Both comparison legs are containment, so `docs/GATES.md` may publish
  a *longer* threshold than the test enforces and stay green.
- **The number leg is substring containment.** `"0.9"` is contained in `"0.95"`, so a loosened
  threshold satisfies the check against an unchanged doc.
- **`EVIDENCE_SOURCES` is three unvalidated path literals.** Nothing resolves them, so renaming
  any of the three silently retires the `evidence freshness` row.
- **The evidence glob assumes one convention.** `t1*.json` — a score file named otherwise is
  invisible rather than a finding, while the summary claims coverage across all registered
  tests.
- **`harness/results/` filenames encode the hint mode but not the split**, so a tune-only run
  overwrites the committed holdout score.
- **A partial `make audit-history` replay exits 0** and silently deflates every per-check total,
  with no denominator on any row.
- **An empty requested split raises `ZeroDivisionError`** in `harness/tests/t1_id_eval.py`
  instead of reporting a clean failure.

### ~~Three more ways, found by a suite that could not miss~~ — CLOSED 2026-09-05

**Found by asking a re-proof what it had not covered, which is the only reason they were
found.** Fifty mutations were re-run against `1f2ab49` and every one still went red naming its
defect — a perfect score, and the completeness critic's own verdict on it was that *a suite that
never misses is not measuring detection, it is restating the implementation*. Each mutation had
been derived by reading the guard it tested, so each was that guard's own inverse. The three
below were then found by asking a different question: not *does the guard fire on the edit it
describes*, but *can the thing it pins be wrong while it says ok*. All three were reproduced by
hand before being believed.

- **`server concurrency` passed while both its constants were INVERTED.** The row read a figure
  out of `server/capture_server.py` and then asked only whether that number appeared anywhere in
  section 11 — `re.search(rf"\b{value}\b", section)`. Section 11 publishes about fifty-five
  distinct bare integers (every sweep column, every latency, every thread count), so almost any
  retune lands on one it already says for another reason. Measured: `CaptureHandler.timeout` set
  to 4 and `REQUEST_SLOTS` to 15 — swapped, the document wrong about both, the pool sized at the
  value §11 itself calls within noise of no bound at all — and the row reported `ok`. **Fixed by
  requiring the ATTRIBUTED form**: `_CONCURRENCY_FACTS` now carries a doc-side anchor per fact
  and compares the value the section attributes to that fact against the code's. It landed RED,
  because §11 had never stated `REQUEST_SLOTS = 4` in any attributable form at all — only as a
  bolded column heading in the sweep table — so the section gained the sentence it was missing.
  The swap now names both figures and both values.

- **`logo parity` did not read a third of the file it exists for.** Section 9's locked-set table
  names each mark's bracket as a WORD — `chrome`, `pale gold`, `rose` — and resolves it in a
  second table three lines below. The row compared `prism`, `ground` and `base` and skipped the
  word, so **24 of the 72 hexes in `app/src/kit/markPalettes.ts` were compared against nothing**
  — in the one file CLAUDE.md's color rule takes an exception for. Measured: changing bluesteel's
  `#B8C8D8` to `#B8C8D9` left `logo parity`, `raw color` AND `design tokens` all green, so an
  unapproved color could reach the app past every reader that rule has. Its docstring claimed the
  opposite in so many words. **Fixed by parsing the legend** (`_S9_BRACKET`) and resolving the
  name to its four stops; the row now reports 72 hexes and a bracket name section 9 fails to
  publish is a third kind of finding rather than a silent skip.

- **`detector standing` was green while section 6 contradicted itself.** The section states the
  corpus size twice and the decline count twice, eight lines apart, and `_DETECT_CLAIMS` pinned
  one copy of each. Measured: setting the twin to 1,620 against a guarded 1,625, and the heading
  to 61 frames against a guarded 59, left the row reporting `ok`. **A pinned figure with an
  unpinned twin is worse than no pin**, because it licenses the belief that the section is
  reconciled. Both twins are pinned now and the row reports 8 figures.

**What this says about the method, and it is the part worth keeping.** Mutation-proving a guard
with the mutation its own author wrote tells you the guard is wired up. It cannot tell you the
guard is asking the right question — for that the mutation has to come from somewhere else. Two
of these three were found by an adversarial pass whose whole brief was *what did this miss*, and
the third by that pass reading a check's docstring against what the check actually does.

---

## 5 — The departed card on screen

**Unblocked, two files, parallel with everything.** Both are D68's residue.

### ~~The copies list says the state twice on every departed row~~ — CLOSED 2026-09-05

**The Banchi rebuild closed this and nobody came back to say so.** `app/src/Inventory.tsx`'s
`Action` returns `primary || copy.state !== 'sold' ? <Pill>Sold</Pill> : null`, and the same
shape for `retired` — so a NON-primary copy whose state is already `sold` draws nothing, which
is exactly the departed row in the copies list. The comment above it states the reasoning:
a copy row's own state pill says the word once the re-read lands, so only the location card and
an optimistic sale still in flight draw one here. The per-call-site fix this item asked for is
what shipped, and the D57 ruling it was waiting on was answered by building it.

**The original entry is kept below** because its argument is still the reason the code is
shaped this way, and because a reader who greps for the duplication should find out where it
went rather than finding nothing.

### ~~The copies list says the state twice on every departed row~~ (the original entry)

Each departed row draws the word twice at 11px about 40px apart: `.card-locations-state` in
`app/src/CardLocations.tsx`, which is `copy.state` verbatim, and `app/src/Inventory.tsx:Action`'s
fallback, which prints the same word for the door the copy left by. **They can never disagree,
because the second is derived from the first** — `sold`/`sold`, `retired`/`retired` — which is
what makes it a duplication rather than two facts that coincide. Confirmed unchanged
2026-08-30.

**Why it is a question and not a wire.** The state span is the pipeline's own word on the
screen where grepping what you saw is worth a machine string. The action slot is D57's — it
becomes `Undo` for twenty seconds after a sale, and the word is the fallback. And `Action`'s
**other** call site, the lone-copy branch, has no state span beside it, so nulling the fallback
loses the fact on the 92% of the store with no group. The honest fix is per-call-site and it is
a D57 ruling. **The Fulfiller's skin already does the other thing** (`sold ? null :`), so the
two skins disagree today.

### ~~The component gallery has no departed case~~ — CLOSED 2026-09-05

`app/src/Gallery.tsx` now carries `DEPARTED` (`slot: null`) and `POOLED` (`located: false`)
fixtures and draws both in the copies group, and `app/tests/gallery.spec.ts` asserts the
departed row's classes, its single state pill and its empty action cell. Proven by mutation:
give `DEPARTED` a numeric slot and `isDeparted` goes false, the classes drop, the count goes
to zero.

**One clause of the original was wrong and is corrected rather than carried over.** It
described the departed rendering as "plain label, demoted store key, absent bar" — the absent
bar named code that no longer exists. The rendering is a plain label and a `.is-nobar` row.

**The general point stands and is not closed**: nothing checks that the gallery is COMPLETE.
Two cases were added because someone noticed they were missing; a third omission would be just
as invisible. A docs-audit row would be the wrong instrument — re-implementing `isDeparted` in
Python goes green against a fixture that renders nothing — so this stays a thing a person
notices.

### ~~The gallery drew the rows in a layout no screen produces~~ — CLOSED 2026-09-05

**Found by looking at the sheet at 390, which is the only way it could have been found.** The
two fixtures above were added and asserted, and both were drawn in the wrong shape.
`app/src/CardLocations.css` answers to `@container copies` in four places, and the widest is
not the interesting one: `(max-width: 619px)` is the entire narrow layout — the address on its
own line, the state and the action beneath it — which that file's own comment calls *"most of
the time, because the pane is one column of a three-column screen"*.

**`container-name: copies` was established in exactly one place in this app**, `Inventory.css`'s
`.inventory-detail`, the pane beside the photograph. `#/gallery` is not inside it, so all four
rules were dead on the sheet and the specimen drew the base grid at every width. At 390 the
address collapsed to one word a line and `ME01 commons` clipped to `M…`; the header's SKU line
truncated for the same reason. **The product cannot produce that shape at any width**, which
makes it the same defect the item above is about, one level down: the row was on the page, and
it was the wrong row.

`app/src/Gallery.tsx` wraps the owner specimen in `.kit-copies`, a `copies` query container
declared in `Gallery.css`. **Owner only, deliberately** — every `@container copies` rule is
scoped to `.card-locations-owner`, and the Fulfiller's skin establishes no such container in the
product either, so naming one on that specimen would invent a context that view does not have.

**Guarded, and observed red.** `app/tests/gallery.spec.ts` sets a 400px viewport and compares
the row's computed `grid-template-areas` against the narrow form. Comparing the resolved
cascade rather than asserting a class is the point: a class can be present while the rule that
reads it never matches, and that was the defect. Mutation: drop `container-name` from
`.kit-copies` and it reports `"place state action" "bar bar bar"` — the base grid — while the
four class-based cases beside it stay green, which is why they could not have caught this.

**What is NOT closed is the general form of it.** Nothing checks that a component rendered on
the sheet is rendered in a context resembling the one it ships in. `copies` was found because
someone looked; `pane` (`BoxBrowse.css`) and `pricing` (`Pricing.css`) are two more named
containers, and whether any specimen of theirs is on this sheet at all has not been asked.

### ~~One of the four `copies` bands cannot fire in the product, and it misses by four pixels~~ — CLOSED 2026-09-05

**Found while checking the fix above, and NOT fixed — the remedy is a design decision.**
`CardLocations.css:233` opens `@container copies (min-width: 760px)`, the widest layout, where
the position bar moves up into the row: `'place bar state action'`. Measured on this tree at
viewport widths of 1440, 1920 and 2560, `.inventory-detail` — the only element in this app that
establishes the `copies` container — is **608px, 756px and 756px**. It does not grow past 756
because the chain above it is fixed: `.bn-page` caps at 1600, `.browse-body` takes 1536 as
`300px + 1fr` with a 20px gap, and `.browse-band`'s `minmax(220px, 34%) minmax(0, 1fr)` leaves
the pane 756.164px at every width beyond that. **So that rule is unreachable, by four pixels,
at every viewport a person can open.**

The product's copies pane is in the NARROW band at 1440 (608px), which is the CSS comment's own
claim — *"most of the time, because the pane is one column of a three-column screen"* — measured
rather than asserted for the first time here.

**Three remedies, and the owner picked the third after seeing both layouts rendered.** The rule
is DELETED, and a comment carrying these measurements stands where it was.

**The renders are why, and they reversed the recommendation.** Forced to 820px the unreachable
layout squeezes the position bar into a narrow middle column between the address and the two
controls, with `#40 of 250 · 16% in` above it and `Section 2 · card 15 of 25 slots` below it, all
inside that column. The band that actually ships gives the bar the full width of the row. **The
design nobody had ever seen was the worse one**, so lowering the threshold would have put a
downgrade on screen at 1920 and up — which is what the first draft of this entry was leaning
toward before anyone looked. Deleting it loses nothing that was ever on screen and removes the
only breakpoint in that file with no measurement behind it.

**What a session must still NOT do is retune a number here quietly.** The three surviving bands
— 479, 619 and 470 — each carry their measurement in a comment, and the pane's 608-to-756 range
is now written down beside them.

---

## 6 — Measured against one rig, or not at all

**Blocked on the owner, not on code.**

### The border search is measured against one rig, on one day

`geometry/detect.py`'s tone path scored **0 of 53** against the Gate B photographs on
2026-08-22; a border search was added that finds 53/53, covered by T6's `_rig_scene`.

**The synthetic case reproduces a mechanism, not a photograph.** `_rig_scene` is built from the
measured numbers — border-ring sides 33 / 65 / 82 / 66, artwork spanning 88 to 231 — and does
make the tone path refuse for the reason the rig makes it refuse. It is still a drawing. There
is no rig photo in this repo and cannot be: `captures/` is gitignored twice, once under an
opsec heading. **The harness can prove the mechanism and can never prove the lighting.**

**The 53 are one sample of one rig state** — one camera position, one lamp, one afternoon, one
set. A second lighting setup, a sleeved card, a foil under raking light or a black-bordered card
on a dark mat are all untested. 53 is a great deal more than zero; it is not a detection rate.

**What would close it**: a second physical run under deliberately different lighting, scored
through `detect_card` and committed the way T1's score is. That needs a ruling on **where rig
photographs may live**, given the opsec rule keeping `captures/` out of git.

**~~Not blocking anything — `detect_card` was never reached in anger.~~ That was false when it
was written and is much more false now.** `detect_card` has three production call sites —
`cli/cmd_identify.py:267`, `cli/cmd_identify.py:488` and `server/pipeline_routes.py:933` — so
every card that goes through `identify`, by command or by the route the runs screen presses, is
cropped by it. The clause read as though the detector were a thing the harness exercises and
the product does not. It is on the identify path, which is the path that costs money.

**And it has now been run over the owner's whole corpus**: 1,625 photographs across six boxes,
in the subsection below. What is still unmeasured is not whether it RUNS but whether what it
returns is the card — see D75's own warning, and `harness/results/detect.json`'s
`not_measured` field, which says in the file itself that no wrongness rate is in it.

### The re-measurement, 2026-09-05, and the 59 frames nobody has looked at

**`scripts/score-detect.py` exists now, so the paragraph above is re-runnable rather than a
one-off.** Over all 1,625 photographs in the owner's six boxes, `detect_card` returned a box
for every one and refused none, and the crop guard declined 59 — `harness/results/detect.json`.

**The declines are entirely boxes 3 and 4** (42 of 723, and 17 of 56). Boxes 5 and 6 were
captured after D75's fitting too and decline NONE, so the departure is not the rig moving,
which is the first thing a jumping rate would otherwise suggest.

**Both constants still sit exactly on the sample, and that is the finding.** Box 1's smallest
crop is `area 0.3002` against a `SMALL_CROP_AREA` of `0.30` — a margin of two ten-thousandths
— and box 1's `detail min` is `0.4376`, BELOW a `MIN_CROP_DETAIL` of `0.50`, so its crops
survive on the area leg alone. D75 wrote both down as fitted facts; this is the first time
they have been checked since, and both reproduce to the digit.

**WHAT IS STILL NOT MEASURED IS THE ONLY THING THAT MATTERS FOR CORRECTNESS.** A decline is the
SAFE direction — the whole frame is sent, which costs tokens and returns a correct answer. A
false ACCEPT is the dangerous one, and no count in that file can see it: a small crop that is
the whole card shot from far back is indistinguishable from a crop of the card's rules-text
panel to every statistic the script produces. **The 59 declined frames are named by box and
filename in the score file and have not been looked at.** Settling them is an eye pass over 59
photographs and nothing else will do it.

### What T7 leaves uncovered in `server/`

- **Twenty-way contention.** T7 runs two and four simultaneous captures, matching D5's two
  devices. The twenty-way case is what found `request_queue_size` at its default of 5 — 8
  served, 12 reset by the OS — and re-running it every turn buys nothing the smaller case does
  not. If that constant is ever lowered, nothing will notice.
- **The bare-interpreter start.** The server runs on system `python3` with no venv, which is
  what makes `python3` rather than `$(PYTHON)` correct in the Makefile. T7 imports the module
  under whichever interpreter runs the harness, so it cannot see this.

Both cost more at every turn end than they can return.

---

## 7 — The preview crops the card, and the one check that looks at a photo cannot see it

**Blocked on a ruling, not on code.** Found 2026-08-31 by the owner, on the screen, looking at
cards photographed the night before.

### `object-fit: cover` is centred on the frame, and the card is not

Five stylesheets draw a stored photograph into a `63 / 88` box under `object-fit: cover`:
`app/src/BoxBrowse.css` (the `#/inventory` preview), `app/src/Inventory.css` (sell-confirm),
`app/src/CardLocations.css`, `app/src/Fulfillment.css` and `app/src/Pricing.css`. The frames are
2160x3840 — aspect 0.5625 — and the box is 0.7159, so `cover` scales to the width and keeps
**10.71% to 89.29% of the frame height, 411px discarded at each end**. Default `object-position`
is `50% 50%`, so the window is nailed to the centre of the FRAME whatever the card is doing.

**The slack was always about three points wide and D32 measured it without anyone reading it that
way.** That entry records cards filling 61–72% of the frame height; against a 78.57% window a
perfectly centred card has 3.3 to 8.8 points of frame height per side before an edge goes.

**Measured, 48 box-3 frames sampled evenly, `detect_card` at 48/48 with zero refusals:**

| | |
|---|---|
| card top | 2.0% .. 71.9% (window opens at 10.71%) |
| card bottom | 73.2% .. 98.0% (window closes at 89.29%) |
| clipped at the bottom | 34 of 48 |
| clipped at the top | 16 of 48 |
| worst bottom loss | 333px of cardboard |

Bottom loss is what gets noticed because the collector number and the set line print there. The
survey passed `card_rect`'s corrected box at the default 0.716; three frames were checked
against the photographs by eye and the rest were not, so the per-frame rows are indicative and
the counts are the claim.

### The `#/inventory` preview does the OTHER thing, and the declaration saying otherwise is dead

**`app/src/BoxBrowse.css`'s `object-fit: cover` has no effect, so that preview letterboxes
today.** The frame is `className="bn-photo browse-photo-frame"` and `app/src/kit.css`'s
`.bn-photo img { object-fit: contain }` has specificity (0,1,1) against `.browse-photo`'s
(0,1,0). There is no `@layer` anywhere in `app/src` and no `!important` on `object-fit`, so
nothing rescues it. Identical on main.

**That silently reversed D38 on the owner's most-used preview** — an entry that argues in
writing that "`object-fit: cover` stays" — and shrank the card to show the desk around it.
Nobody chose it; the Banchi rebuild introduced `.bn-photo` and the older, less specific rule
stopped applying without failing.

**It is recorded here rather than fixed in the same breath** because the section above costs
out both behaviours and the choice between them is D38's owner's, not a session's. What has
changed is that the tree is no longer doing what D38 says it does, so the question is now
which of the two to KEEP rather than whether to change anything.

### Why `make design-check` is green over it

`docs/DESIGN.md`'s floor is `>= 320px` on the short edge of the pull-modal photo, asserted at
`app/tests/fulfillment.spec.ts`. Its `paintedPhoto` helper resolves `object-fit` properly —
`cover`, `contain`, `scale-down`, `none` and `fill` each get their own scale — so it measures how
large the photograph is **drawn**. It has no way to ask whether the CARD is inside what was
drawn, and under `cover` it never can: the frame fills the box by construction, so the painted
short edge IS the box and the row passes at exactly the moment the card is being cut. **A floor
on size is not a floor on content**, and this is the second time that distinction has cost
something here — the same helper's own comment draws it, about a broken image that still has a
layout box.

Closing it needs the thing the assertion does not have: where the card is. `detect_card` answers
that, and putting a detector behind a Playwright row buys a check that is slower than the suite
it joins and can refuse. Not costed.

### Neither fix is a stylesheet edit, which is why this is recorded

**`object-fit: contain` fails the floor it would have to clear.** `.fulfillment-photo` is
`min(360px, 100%)` at `63 / 88`, so 360 x 503; `contain` scales by
`min(360/2160, 503/3840)` = 0.131 and paints **283px** on the short edge, under the 320 floor.
Computed from the helper's own formula rather than observed in a run. The box would have to reach
407px to hold the floor and it is capped at 360, so `contain` is unavailable on the Fulfiller's
screen without reopening that row of the constraints table — which D31 says is not his to
reopen. On the owner's screens nothing checks it, and the cost there is size: the frame draws at
78.6% of the box width and the card lands at 63–69% of it, against 80–88% today.

**The server crop is mostly wiring and four open questions.** `identify/images.py:crop_rect` is
already extracted so a second caller can draw the rectangle the pipeline cuts, and
`POST /pipeline/crop-preview` already detects and serves for `#/runs`; a third caller of the same
function is D32's own rule rather than an exception to it. What is not answered:

- **Latency forces a cache.** D32 measured ~115ms per card for the crop preview. `GET /photo` is
  hit on every arrow-key step of the browse walk and auto-repeat is faster than that; the runs
  panel bought its way out with a 140ms debounce and a photo route cannot debounce.
- **The rect has no home.** A capture sidecar is `{box, game, index, rarity_claim}` today. Adding
  the rectangle makes this a capture-write change plus a backfill over every photograph already
  on disk.
- **D32 enumerated the consumers that keep the whole frame** — the review queue photograph a
  human judges foil against, the pull preview matched to a physical slot, the re-shoot comparison
  — and the browse preview is on that list. Per-request cropping honours *in memory, never on
  disk*, and still needs an amendment saying why identifying a card differs from judging one.
  `app/src/ReviewQueue.css` deliberately sets no `object-fit` and should keep the frame either
  way.
- **A refusal renders as today.** `detect_card` returning `None` means the whole frame, which is
  the clipping. So the crop narrows the case `contain` answers and does not remove it.

**Not blocked on the games registry.** `card_aspect` is 0.716 for `pokemon`, `pokemon_code`,
`riftbound` and `one_piece`; only `misc` is `None`, which `detect_card` refuses by contract. Box
3 is Riftbound, so the box this was found on is not the blocked case.

**Why it stays open**: the two fixes trade legibility against coverage in opposite directions and
one of them moves a published floor. That is a decision entry, not an edit, and the owner has not
made it.

---

## 8 — Recorded and correctly unfixed

**No work proposed. Here so a green run is not read as a promise none of these exists.**

### The supervisor's four gaps (D53)

It said "Three" over four bullets from the day it was written until 2026-08-30 — the swap gap
was appended without the lead-in being re-read, which is cluster 2's defect at the scale of one
word.

- **A request accepted but not yet inside `_dispatch` is uncounted by the drain.** Window is
  microseconds; closing it means reimplementing `handle_one_request` in the file that most wants
  to stay boring.
- **The parse pre-check catches syntax errors only.** `scripts/serve.py` refuses to restart into
  a file that does not `compile()`. An `ImportError` or module-scope `NameError` still kills the
  new child and **there is no rollback** — the last-good process is already gone. Containment is
  the fast-failure cap: after five quick deaths it stops respawning, keeps watching, and says so.
  Fixing it properly means the socket-passing design D53 names and rejects for v1.
- **The reload notice has no automated case, and three attempts to write one are why.**
  `ServerReloaded` renders nothing until the boot header CHANGES between two responses. A stub
  over `app/tests/fulfillment.spec.ts`'s helpers did not win the route, `route.fetch()` fails
  outright, and a body-stubbing version left too few requests to produce a second header. **Two
  attempts PASSED against a build with the notice rendered unconditionally** — vacuous — and
  were deleted, because a case that cannot fail is a green row asserting nothing. What IS
  verified: the header observed reaching the browser cross-origin over the real server (eight
  responses carrying `X-Pkmnscan-Boot`), and the notice photographed appearing on `#/inventory`
  after a real restart and NOT on `#/fulfillment`. What guards it structurally is `hasChrome`,
  the nav's own condition, which `fulfillment.spec.ts:noWayOut` already covers.
- **The swap gap.** Between the old child exiting and the new one binding a request gets
  `ECONNREFUSED`, and `app/src/server.ts` deliberately has no retry, so it surfaces as
  `unreachable`. Tens of milliseconds. Named in D53 with the fix considered and declined.

### A Playwright line number is not a line in the file

Playwright strips the TypeScript and reports against the generated file, so a spec loses the
lines its type-only constructs occupied and gains the lines its long ones are re-broken into.
**Wrong for nearly every test in the suite** — 254 of 256 at `3ca904e`, 257 of 259 later —
checked by walking `--reporter=json`'s location for all of them. Measured with a probe: a test
on source line 24 with nothing above it reported 23; the same test on line 27 under a 22-line
`type` block reported 3. Clearing `$TMPDIR/playwright-transform-cache-501` changes nothing.
**Cost: a citation nobody can follow** — a session opening the file at it lands on unrelated
code, silently, because the line is real and the file is right. Grep the TITLE instead; the
reporter prints that too and it is exact. Nothing to fix at 1.55.1; the remedy is to stop
writing the number down.

**The same shape in the docs, and `doc hygiene` sees only its provable half.** Docs carry 52
resolvable `path:line` citations. D74's row catches one failure — a number past the end of its
file — and there are none today. **The common case is invisible**: a citation whose file is
long enough but whose line has moved, which is exactly what `ReviewQueue.css:47` became when
the comment it named slid to line 57. Nothing distinguishes that from a correct citation
without knowing what the line should say. **The remedy is the same one this entry already
gives** — cite the identifier, not the number — and the 2026-08-30 prose sweep applied it
where it rewrote a citation rather than adding a check that cannot exist.

### What is not closed about the `make design-check` flakes

Three flakes were reproduced and fixed 2026-08-30 — a `toBeVisible()` timeout answered by
`expect: { timeout: 15_000 }` in `app/playwright.config.ts`, a two-layout subtraction in
`app/tests/inventory.spec.ts` answered by reading both tops in one `page.evaluate`, and a
snapshot race in `app/tests/shipping.spec.ts` answered by `toHaveText`. None weakened an
assertion.

**A starved rig is not a slow one, and no wait answers it.** At 40 workers against 12 CPU hogs
— 4x oversubscription on a 15-core machine — a context can fail to render at all: with the
allowance at 120s, 10 of 80 still failed and one took 122 seconds. At that load the suite also
loses `app/tests/fulfillment.spec.ts` on `main.fulfillment`, `app/tests/capture-claims.spec.ts`
on the Finish row, and `app/tests/capture-undo.spec.ts` on a capture that never landed — it
expects `Card 10` and the newest is `Card 9`, a **dropped press** rather than a slow one and the
only one a longer wait could never answer. **None of it is reachable from `make design-check`,
which runs 7 workers here.**

**One sighting is unexplained**: at 15 workers, before either fix, `app/tests/cursor.spec.ts`
failed once in nine runs. Its message was not captured.

**Three non-retrying reads remain**, all in `app/tests/inventory.spec.ts`, of the eight
originally counted. None has been observed failing, and `expect(await …innerText())` is a
narrower hazard than the list form that broke. **Two comparisons in the geometry case still
pair an early read with a late one** and are left alone — 8px of declared slack against a
measured 0, and a 41px column gap. A case is not improved by rewriting assertions that have not
failed.

**Two numbers were published against runs nobody read.** A commit message said "design-check
257" when the run was 255 passed and 1 failed and the true count was 256; and the entry above
said five non-retrying reads when there were three. The suite is **264 cases** as this is
written, which is the same lesson a third time: a count recorded here is stale the week after.

### `make check` is not automatic

`--self-test` had been RED for some time — a `tested_by reach` case pinned to T3, T3 began
importing `store`, and the case asserting a false claim stopped catching one — while
`make docs-audit` stayed green and so did every commit, because **nothing ran it**. Closed
2026-08-24: the case moved to T5 and states its requirement in the comment, and `make check`
runs `audit-self-test`.

**Deliberately NOT in the git hook** — D18, not taste: `--self-test` is the one mode of that
script that writes, and nothing that writes may run on the path deciding whether a commit
proceeds.

**Residual:** the Stop hook runs `make harness`, not `make check`, so a red self-test surfaces
only when somebody asks — the same standing `githooks-selftest`, `port-agreement`,
`ignore-check`, `vale` and `lint` all have. And **`--self-test` does not drive a real git
index**: the index-mode primitives have cases, but no case exercises the staged blob. It bites
hardest on `check dispatch`, whose whole subject under `--staged` is the blob. Driven by hand
at integration, and by hand is where it stays.

**`check dispatch` also cannot see its own unwiring.** Delete its call from `audit()` and every
other row prints green, the run exits 0, and the row is absent. A detector cannot detect its own
absence, so there is a root to the recursion: unwire anything else and the commit fails, unwire
*this* and only `--self-test` catches it. Related: **called is not run, and run is not looked** —
a dispatched check returning before its `report.add` prints no row, which `check_raw_color` does
when `app/src/` is absent. And **`scripts/status.py` is not in `INVOKERS`**, so `audit invocation`
does not see its call; it would find nothing if it did, since that row reads flags off a literal
command line and `status.py` builds argv as a list.

### The `fixtures/` guard is one tool wide at write time

`.claude/settings.json` denies `Write(./fixtures/**)` and `Edit(./fixtures/**)`. **Bash is
not**, so a `python3 -c`, a heredoc, `cp` or `sed -i` goes past it silently. Measured by
walking through it: the session that built `fixtures/orders-shipping.csv` wrote it with a
script and only discovered the rule afterwards, when a `Write` into the same directory was
denied. **The guard did not participate in the decision at all.**

**The commit-time half is armed and always was.** `scripts/githooks/pre-commit` refuses any
staged modification under `fixtures/` via `--diff-filter=MDR` — which is the add-vs-modify
distinction the deny rule blurs and this entry once proposed as unbuilt. **So the cost this
entry priced cannot happen**: a modification that never reaches a commit never reaches a later
week. The residue is a confusing half-hour, not lost ground truth — a Bash write lands in the
tree immediately, so `make harness` can go red before anything tries to commit.

**Why the write-time half stays open.** A deny list cannot see what a script writes at run
time, and a pattern broad enough — denying `python3`, or shell redirection — takes
`make harness`, `make check` and `scripts/docs-audit.py` down with it. Same trade D16 refuses
for `--no-verify`. **Not the same gap as the PII one**: this repo has no secret scanning either
(the hook's only content rule is the code-card regex), so a fixture carrying buyer names commits
clean. That is about what is *inside* a file; this is about *which tool* wrote it.

### Nothing in the product SHOWS the history, and it is a table now, not `history.jsonl`

**Two corrections, 2026-09-05.** D88 moved the store of record into `inventory/store.sqlite`,
so the history is a TABLE and the filename this heading carried is the legacy one — a JSON file
left beside the database is never a fallback, which is the rule that makes the old name
actively misleading rather than merely dated.

**And the sole-reader claim was wrong in four places, this being the fourth.**
There are three readers — `_answer_origin`, `_origin` and `_reverse_stand_down` — and
`_state_before_sale` is none of them: it is handed a sequence of events and scans it, and it
has a twin, `_state_before_retirement`, that scans the same way. The other three instances were
corrected first; this one survived because it is on a line wrap in the reverse word order, and
the guard that now catches it (`scripts/docs-audit.py:check_sole_reader`) had to be widened
twice to see it. That widening is the useful part of this entry: a checker over prose that
reads one line at a time is checking typography, not sentences.

The three writes that changed no state — a correction, a capture undo, a review answer — all
leave a row as of 2026-08-13, asserted by `check_history` in
`harness/tests/t7_store_and_seams.py`. No route serves it and no screen shows it, and every
scanner filters positively against `master.STATES`, so all three are inert to them by
construction. The audit value is a person with a text editor, which is what an audit
trail is for — but **a line that stops being written is invisible to everything except T7.**
Two by choice: a `PUT` changing no value logs nothing, so a silent sidecar repair leaves no
trace; and the vocabulary lives in two places (`master.STATES` and `SERVER_EVENTS`), so a
reader has to know both.

### D60's guards see tokens, never arguments

`scripts/prose-guard.py` is the only thing comparing two versions of a doc, and it compares
HARD TOKENS — backticked identifiers, paths, decision ids, measurements, dates. **A rewrite
keeping every backtick and losing the reason an entry exists passes silently.** That is the
residual risk of the whole D60 exercise and nothing mechanical can close it: judging whether a
paragraph still carries its argument is D16's layer 3, a model reading prose, deliberately never
a gate. `--facts` is on no gate either — it needs a BEFORE, which exists only while a rewrite is
in flight. The two rows that DO gate, `decision structure` and `entry budget`, check the tree as
it stands and cannot see what a change removed.

### Two documents outran the code

- `docs/specs/audit-retirement.md` restates a check roster and a count the shipped registry no
  longer matches, and `CLAUDE.md` tells sessions to read specs as settled. It needs a status
  line naming which premises failed under execution — **not** a corrected number, which would
  only reset the clock: the restatement is the defect.
- `.claude/commands/docs-audit.md` says exit 2 means the coupling question, but the command it
  prints in step 1 runs without `--staged`, and coupling only runs under `--staged`.

### The second fenced block in `docs/DESIGN.md` is not read

`design tokens` reconciles the `## Tokens` fence against `app/src/tokens.css` both ways, and
`raw color` now blocks a hex anywhere in `app/src/*.css` — which closed the sharper half, the
`#ffffff` in `app/src/PullConfirm.css` that survived a design review and two integration passes.
What is left is a document disagreeing with itself: step 6's three button states restate five of
these hexes in a second fence nothing reads. Left out because D18's instinct is that deleting a
restatement may be the right answer, and that argument belongs in `docs/DESIGN.md`. The sheets
in `docs/design-refs/` stay unchecked for a settled reason — they are drawings of the spec and
are allowed to lose to it.

### `design tokens` locks names for every token and values for only the hexes

Named 2026-09-03, when the row was rewritten for the `--bn-` system. It compares a VALUE only
where `docs/DESIGN.md`'s block states a hex literal — 31 of 100 declared tokens. The other 69 are
checked for existence in both directions and their values are locked nowhere: an alpha of another
token (`ink 8%`), an alias (`--bn-money` = ink in both themes), a duration, an easing curve, a
shadow, a control height.

**That is a real gap and not a shrug, and the shape of it matters.** The dangerous drift this row
exists to catch is a value nobody chose rendering perfectly, and a wrong `cubic-bezier` or a
wrong shadow is exactly that. What stops it being closed by writing more hexes into the document
is that most of these are not hexes: `--bn-line` is *ink at 8%* by design, and spelling its two
rendered values out would create the second source of truth the tint was invented to avoid — the
light and dark values would then have to be kept in step by hand, which is the defect, not the
fix.

**What would close it**: a reader that resolves `color-mix()` and `rgba()` against the token they
reference and compares the resolved value, which is a small CSS color engine and was judged not
worth building for 69 tokens. Until then the row's summary line says how many hexes it compared,
so a green row cannot be read as full coverage.

## 9 — The sigil check matches text, so a renamed local walks past it

`make sigil-check` (D92) refuses a bare `#` composed from an expression naming `index`, which is
what keeps D58's count and the store key from being spelled the same way on one screen. It reads
SOURCE TEXT. `const n = side.index` on one line and `#{n}` on the next is a violation it cannot
see, and so is any indirection through a helper, a destructure or a prop rename.

**Its bypass is `PKMNSCAN_SIGIL=off`**, spelled the way `PKMNSCAN_DOCS=off`, `PKMNSCAN_GATE=off`
and `PKMNSCAN_MAIN=off` already are, and printed in every refusal for D42's reason: a guard with no
visible way past it gets disarmed at the config instead, and a disarmed `core.hooksPath` takes the
three opsec rules with it. The per-line form is `sigil-ok: <why>`, which is the better escape
because it argues the exception in the file next to the code rather than turning the whole check
off for a commit.

**The fix that could not be evaded was considered and rejected on blast radius.** A nominal type
over the two numbers — branding `slot` and `index` so the compiler refuses the swap — is the real
answer, and `slot` and `index` are plain numbers across the whole wire contract and forty call
sites. That is a refactor much larger than the bug, and D92 took the cheap check that runs on
every commit over the expensive one nobody would finish.

**What made the ceiling tolerable was where the mistake usually happens.** All four sites the
check found on its first run compose the `#` and the field on ONE line, at the point of render,
because that is what drawing a number looks like. The paragraph here used to end *"the evasion is
available and has never been taken"*, and it was wrong on the day it was written.

**THE TRIGGER HAS FIRED — one violation shipped through the gap, and was found by reading rather
than by running anything (2026-09-04, D92 amended).** `CaptureScreen.tsx` drew
`#{slotNumber(target)}` on every undo thumbnail, and `slotNumber` returned `String(target.index)`
whenever the target carried no rendered label — which is the target `undoStack` composes from the
server's high-water mark after any reload mid-run. The `#` and the field were three functions
apart, so the check read `slotNumber(target)`, found no `index` in it, and passed. It was green
over that line from the day it was written until the sweep D92 deferred was carried out.

**What that changes and what it does not.** It does not change what the check is worth on the
lines it can see: it read 61 files and the sweep found nothing it had missed except this one. It
does mean the nominal type this entry calls *the real answer* now has a shipped defect behind it
rather than a hypothetical, and D92's rejection of it on blast radius was made without one. That
is the owner's call and nobody else's; recording it is what this file is for.

**The cheap partial was taken first, on the owner's ruling (2026-09-04).** Asked whether the
nominal type should be argued now or the guard shipped first, the owner chose the guard. So the
check reads a second pattern: the word form, `Card {…index}`, which is the same claim as `#{…index}`
in the register a screen reader speaks. **It was measured before it was written rather than adopted
on the argument that it sounded cheap** — over every `.ts`/`.tsx` in `app/src` it returns four
violations and nothing else, all four in `RunsComposer.tsx`, and the eight legitimate `Card {…}`
renders standing in the tree fall outside it on the `index` requirement alone. Those eight are
self-test cases now, so the false-positive rate that made it adoptable is asserted rather than
remembered. **The four it found had shipped**: two of them `aria-label`s, on a panel whose figure
names a photograph the run is about to pay to have read.

**What the second pattern does NOT do is close this section.** It is the same text match one word
wider. `const n = side.index` then `Card {n}` walks past both patterns exactly as it walked past
one, and the ceiling this section was opened about is where it was. What changed is that the
sweep D92 deferred is no longer the only thing standing between this class and a screen — for the
two spellings the product actually uses. **Until the nominal type is ruled on, a green run means
"no figure is drawn over a field literally named index on that line, in either of two spellings",
which is more than it meant and still less than it sounds like, and the sweep that catches the rest
is a person reading `app/src` and asking of each figure what number it is.**

**Two the sweep can see and neither pattern can, left deliberately.** `Pricing.tsx:2641` draws
`` `no label · ${photoAt.box}/${photoAt.index}` `` and `Orders.tsx:1205` draws
`` `box ${target.box}, index ${target.index}` ``. Both spell the key in prose with no figure at
all, so no sigil rule reaches them and none should — naming the index *as* the index is the one
thing that is never the confusion. They are here because they are the shape a future reader will
check this file about.

## 10 — An order arriving mid-pass is walked but never counted, and a tab outlives its sitting

`WalkView`'s figure counts the orders THIS PASS has completed — `OrdersHubStore.walkKeys`, frozen when
the walk is entered and cleared by a fetch or by a capture-server restart (D96, amended 2026-09-04).
Two things it still cannot say, both deliberate and both reachable on the owner's store. **A third —
that a restarted server ends the pass — was one of them and is closed**; it is kept below because the
three attempts it took are the useful part.

**An order that arrives after the press is walked but never counted.** The screen re-reads after every
pull, so a new order joins `walk.rows` and the operator pulls its copies like any other — and the pill
goes on describing the pass they started rather than the work now in front of them. The head beside it
is the figure that moves, which is why this is a gap and not a lie: *"4 still to pull across 3 open
orders"* is always current. Counting arrivals would make the figure a different one — progress against
a moving target — and that is a design question, not a fix.

**And the pass is held for as long as the tab is.** `HubState` lives as long as the tab by its own
argument, and `mode` already survives an Orders → Shipping → Orders detour under it, so `walkKeys` does
too. A tab left open overnight keeps a figure describing a sitting that ended, and nothing on screen
says so. `onFetch` clears it, which is the boundary the operator actually draws — but only if they
press it. **The fix that would close this is a clock, and this repo does not put one in the client**
(`store/orders.py` records the one deliberate exception and argues it at length), so the honest
alternatives are an explicit *end this pass* control nobody has asked for, or leaving it here.

**A capture-server restart DOES end it now, closed 2026-09-05.** `onServerBoot` clears `walkKeys`
beside the shipping batch: a server that restarted may have taken orders since, so a figure counted
against the old set describes a sitting that is over — and unlike a stale batch it is not visibly
broken, it is a smaller number that looks fine.

**The reason this took three attempts is worth more than the fix, because it was never the code.**
The first two blamed the boot header: `app/tests/orders.spec.ts` stubs only the four `/orders*`
routes, so `/status`, `/games` and `/boxes` reach the real capture server with a boot id of their own,
and that was recorded here as a hazard for every spec. **It is not one.** `server.ts:noteBoot`
early-returns on an absent header and says why in its own comment — *"far more likely in a test — a
stubbed route, and inventing a reload from a missing header would make every spec that stubs the wire
report one"* — and the real server's id is CONSTANT while it runs. The listener fires only when two
different non-empty ids alternate, which is what the investigation's own experimental stub
introduced. The hazard was manufactured and then filed as the repo's.

**What actually defeated it was a catch-all route that forwarded a write.** The stub rewriting the
header matched by PORT and therefore also caught `POST /orders/pull`, which `route.fetch()` sent to
the real capture server. It was refused there — a fixture's order does not exist in a real store — so
`pullCopy` threw, `onPull` never reached its re-read, and the payload never moved. The case failed
for a reason that had nothing to do with what it tested, **and a write came one refusal away from
landing on a live store.** The rewrite is GET-only now and says so at the line.

**The case that closed it carries its own vacuity guard.** A third order stays open through the
restart, because with only two the second pull leaves nothing open, `buildWalk` returns no rows, and
`WalkView` draws its EmptyState before the head — the figure would be absent because the whole head
is. Proven by removing the third order AND the clear together: the case still passes. Observed
failing with the clear removed, and with the boot id held constant, both at `Expected 0, Received 1`.

**And `onServerBoot` is exercised on purpose at last.** No spec drove the boot header before this one,
so the listener — including D73's shipping-batch clear, which throws away real state — had never been
tested at all.

**Why the remaining gap is not fixed.** The mid-pass arrival was surfaced by an adversarial review of
the change that introduced the figure, before it shipped, rather than found afterwards — and it is the
figure being narrower than the screen rather than wrong about what it counts.

## 11 — The capture server bounds concurrent requests, not threads, and a Playwright fleet is what finds out

`server/capture_server.py` serves on `class CaptureServer(ThreadingHTTPServer)` with
`request_queue_size = 128`. **`request_queue_size` bounds the ACCEPT BACKLOG, not the thread count**:
once a connection is accepted it gets a thread of its own, `daemon_threads` is true so `socketserver`
does not even record it, and `protocol_version` is HTTP/1.1 — so that thread lives for the whole
keep-alive CONNECTION rather than for one request. Nothing anywhere bounds how many of those exist.

**`CaptureHandler.timeout = 15` is not that bound and does not claim to be.** It is a socket timeout,
so it reaps a thread parked on `readline` for a request that is never coming — every connection a
closed tab leaves behind. Its own comment states what it does not fix, and it is right: an ACTIVE
connection performs socket operations, so no idle timeout touches it.

**Measured three times on this machine, and the third was avoidable.** (A fourth attempt, the load
sweep that was supposed to size the bound below, reproduced nothing — see what is still owed.)

1. **1,178 handler threads alive at 1,318% CPU**, twice in one working day, every one blocked in
   `PyEval_AcquireThread` — waiting for the interpreter lock, not for the store — with the process
   holding its port and answering nothing. This is what bought `timeout = 15`.
2. **80 Playwright browsers under `make design-check`: 969 threads inside ten minutes at 338% CPU**,
   measured immediately after that landed, which is how we know the idle timeout does not cover it.
3. **2026-09-04, a session's own doing.** It ran `make design-check` about eight times against the
   owner's live server while also driving it from hand-rolled Playwright scripts, then ran
   `make restart`. The supervisor's drain — `DRAIN_GRACE_SECONDS`, which is
   `store/files.py:LOCK_TIMEOUT_SECONDS` (30) plus ten — expired with requests still in flight, and
   it killed the server outright: *"capture server did not stop within 40s — killing it. a request in
   flight was cut."* That crashed Python out from under the owner mid-use. No data was lost.

**`make design-check` is therefore a known trigger, not a surprise.** The suite is not the thing to
give up — it is the verification this repo runs on. What follows from this section is narrower and
sharper: **do not restart the owner's capture server to fix it.** `make launch-agent` keeps that
process alive at login over a real store; a wedge is survivable and a kill with a write in flight
is the thing that is not. Run the full suite once at the end rather than after every edit, prefer the
Browser pane over hand-rolled scripts against the live app, and when a browser page must be closed,
navigate it to `about:blank` first — a page closed mid-response leaves the handler writing to a dead
socket, which is why `.serve/capture.log` holds thousands of `BrokenPipeError` traces.

**The FIRST of two bounds landed 2026-09-04, and it is narrower than this section's title.**
`REQUEST_SLOTS` and a `threading.BoundedSemaphore` around `_dispatch` cap how many requests EXECUTE
at once, which is the resource the measurements above say ran out — the interpreter, not sockets and
not threads.

~~A connection parked between keep-alive requests holds no slot, so the idle-worker question a real
pool has to answer never arises here.~~ **That sentence was overtaken thirty lines below, in the
same section, on the same day.** The pool landed too, and the idle-worker question is exactly what it
had to answer — the answer being `Connection: close` on every response, which makes a worker's life
one REQUEST rather than one connection. Both bounds are in the tree: the semaphore still caps
execution, and `CaptureServer.process_request` submits to a `ThreadPoolExecutor(REQUEST_SLOTS)` so
threads are capped too. Read this paragraph as the account of the first bound and the one below as
the account of the second; neither replaced the other.

**`REQUEST_SLOTS = 4`, and this line exists because the sweep table below could not carry that
claim.** The table publishes the whole sweep — 1, 2, 3, **4**, 6, 8, 12, 24, 48, unbounded — so
the live value appears there only as a bolded column heading among nine others. `make
docs-audit`'s `server concurrency` row compared the code's figure against *anything* the section
said, and a bare `4` in a row of slot counts satisfied it. Measured 2026-09-05: swapping the two
constants — `CaptureHandler.timeout` to 4 and `REQUEST_SLOTS` to 15 — left this document wrong
about both, sized the pool at the value this section calls within noise of no bound at all, and
the row still reported `ok`. The row now demands the attributed form, which is this sentence, and
the same is already true of `request_queue_size = 128` and `CaptureHandler.timeout = 15` above.

The slot is taken *before* `_inflight_enter`, deliberately: a request
queued for one has not started and cannot finish, and counting it would make the supervisor's drain
wait out its grace on work that is not happening and then kill it — the incident above, one layer
down. The wait is `files.LOCK_TIMEOUT_SECONDS` (30) and the refusal is `server_busy`, beside
`store_busy`; 30 sits inside the 40s drain by construction, so a queued request always resolves one
way or the other before the drain gives up.

**Measured on the owner's own store, 2026-09-04, on their explicit word** — 1,625 cards, 20 orders,
read-only routes throughout (`/orders`, `/boxes`, `/search`, `/status`; no captures, no writes), 150
concurrent keep-alive connections, 20s per run. The first attempt at this used a scratch store and
proved nothing, because every endpoint there answers in under ten milliseconds and nothing contends
the interpreter. `/orders` on a real store resolves every open order against the whole inventory, and
that is the load this failure needs.

**The collapse reproduces, and the figure that shows it is not throughput.** A single probe request —
one connection, one `GET /status`, the shape of a person pressing something while the fleet runs:

| connections | served | errors | probe |
|---|---|---|---|
| 50 | 199 | 0 | **6.5s** |
| 150 | 216 | 132 | **18.2s** |
| 300 | 187 | 44,267 | **failed outright** |

That is section 11's *"holding the port and answering nothing"*, reproduced on demand. Thread count
peaked at 153 for 150 connections and fell back to 3 within twenty seconds of the load stopping —
**so `CaptureHandler.timeout = 15` does exactly what it claims**, and what accumulates under load is
active connections, which no idle timeout can touch.

**The sweep, at 150 connections, and it has no plateau — it is monotonic.**

| `REQUEST_SLOTS` | 1 | 2 | 3 | **4** | 6 | 8 | 12 | 24 | 48 | unbounded |
|---|---|---|---|---|---|---|---|---|---|---|
| requests/sec | 53.0 | 51.1 | 46.3 | **43.5** | 32.8 | 21.9 | 17.4 | 16.6 | 15.3 | 11.9 |
| probe p50 | 3.3s | 3.4s | 3.6s | **4.2s** | 5.9s | 9.6s | 14.0s | 16.7s | 11.4s | 12.9s |
| errors | 0 | 0 | 0 | **0** | 0 | 2 | 7 | 21 | 121 | 90 |

**Less concurrency is strictly better here, which is what GIL-bound work looks like** and is the
opposite of the intuition that sized the first guess at 12 — a value this table puts within noise of
the unbounded server it was meant to improve on.

**So the benchmark says 1 and the value is 4, and the difference is a hazard the benchmark cannot
see.** A request that blocks on the store lock HOLDS ITS SLOT for up to `LOCK_TIMEOUT_SECONDS` — the
30s a capture legitimately waits out behind a running `./pkmnscan identify`. At 1 slot a single such
writer stalls every read on the server; at 2 it takes two. Four keeps 82% of the best throughput
measured and leaves three slots when one is blocked. **That half is reasoned rather than measured**,
because measuring it means firing real captures at the owner's store while its lock is held, and this
section exists to say that is not something a session does on its own.

**What is proven besides the numbers is the mechanism**, by
`harness/tests/t7_store_and_seams.py:check_request_slots`: with more callers than slots, exactly
`REQUEST_SLOTS` execute, the queue is not counted as in flight, and every slot is given back. It was
observed failing twice — with the semaphore removed, and with the slot taken after the in-flight count
rather than before it.

**What the SEMAPHORE does not do is reduce thread count**, and the sweep says so in its own column:
153 threads at every value. Threads park on it instead of thrashing the interpreter, which is the
point, but they are still created.

**So the pool landed too, and this section's title is finally wrong in the right direction.**
`CaptureServer.process_request` submits to a `ThreadPoolExecutor(REQUEST_SLOTS)` instead of spawning
a thread per connection, and **every response sends `Connection: close`** — which is what makes a
worker's life one REQUEST rather than one connection, and therefore what makes a pool safe here at
all. Measured on the owner's store at 150 concurrent connections, against the semaphore alone:

| | requests/sec | probe p50 | peak threads |
|---|---|---|---|
| semaphore only | 45.6 | 3.84s | **153** |
| pool + `Connection: close` | 45.5 | 3.94s | **5** |

Identical within noise on both throughput and responsiveness, and the thread count is the whole
difference. The cost is a TCP handshake per request: microseconds on localhost, a millisecond or two
to a phone, against a capture cadence of ~600 ms per card.

**Where the header is sent from is part of the guarantee, and it moved on 2026-09-05.** It was
sent from `_send`, which is not every response: `_photo`'s 304 branch answers a conditional GET by
hand — `send_response`, the ETag headers, `end_headers` — and never touches `_send`. With
`Cache-Control: no-cache` making 304 the normal answer on a revisit, four concurrent revalidations
held all four workers until the 15s reap. It is sent from **`end_headers`** now, which every
response reaches by construction, so a new route cannot answer without it. That is the difference
between an invariant and a convention, and the convention had already been broken once by the route
that needed it most.

**The starvation this section warned about is real, and removing `Connection: close` demonstrates
it.** With keep-alive restored and the pool kept, four idle connections hold all four workers and
every other caller waits forever: `make harness` does not fail, it **HANGS**. That is worth stating
precisely — the failure mode of a pool over keep-alive is a deadlock, not a slowdown, which is why
the two changes are one change and neither ships without the other.

**`CaptureHandler.timeout = 15` is now unreachable and is kept anyway.** It bounds a thread parked on
`readline` for a request that is not coming, and no connection survives long enough to park.
`protocol_version` is one edit from making it matter again, and a guard that costs nothing is cheaper
than rediscovering why it was deleted.

**The semaphore stays, and it is not a second mechanism for one job.** With one request per worker the
pool size is also the bound on concurrent execution, so `REQUEST_SLOTS` never blocks today. It is the
INVARIANT rather than the implementation: on the day keep-alive returns, the pool bounds threads and
the semaphore is the only thing still bounding execution. T7 asserts both, and both were observed
failing — the pool removed gives 10 threads for 10 callers, and the semaphore removed lets every
caller execute at once.

**So the real bound on thread COUNT is still open, and a worker pool is still what it needs.**

**The reason a pool is not a swap is written down rather than left to be rediscovered.** A pool of N converts unbounded degradation into back pressure: connection
N+1 waits in the accept queue instead of taking a thread. But over HTTP/1.1 keep-alive **a worker
held by an idle connection is a worker serving nobody**, so N idle browser tabs starve a pool of N
completely, and closing that needs one of: `Connection: close`, which throws away the thing
keep-alive is for; an idle timeout tight enough to free workers faster than tabs accumulate, which
is a constant with no safe value on a rig this repo already argues about elsewhere; or an event loop
where a connection is not a worker, which is a rewrite of the handler. **And refusing connections
rather than queueing them is already known to be dangerous here** — `CaptureServer`'s own docstring
records 20 simultaneous captures with 8 served and 12 reset by the OS. A dropped capture is one the
operator sees fail and retries; a pool must not make that the normal case.

**Why this section exists at all, which is the part worth keeping.** Every fact above was already in
the tree, in two comments inside `server/capture_server.py`. On 2026-09-04 a session diagnosed this
failure from `.serve/supervisor.log` and `.serve/capture.log` without opening that file, told the
owner the server was single-threaded, and then proposed `ThreadingHTTPServer` as the fix — the class
it has been built on all along. **Nothing that session did read would have corrected it**: `CLAUDE.md`
said nothing about concurrency, and `docs/map.py`'s entry for the file describes route shapes by
deliberate choice. Knowledge reachable only from inside the file it is about is knowledge a session
diagnosing from the outside will not have. `make docs-audit`'s `server concurrency` row now pins the
class, the timeout and the backlog in this section against the code, so a future worker pool cannot
land while this section still describes threads.

## 12 — Ten decision entries are over budget on purpose, and the budget was the thing that had drifted

`scripts/docs-audit.py`'s `entry budget` row reports entries larger than `ENTRY_BUDGET`. It reported
**21** until 2026-09-05 and reports **10** now, and the difference is not that anything was cut.

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

## 13 — The commit gate was measured, and it is the checks OFF it that are worth knowing about

**Measured 2026-09-05 against `82bdb78`. Not a debt so much as the answer to one**, kept because
the question kept being asked and answered by inspection.

**The question.** A mutation re-proof had shown fifty guards going red under
`python3 scripts/docs-audit.py` — the whole-tree form, which is what `make check` runs. The
commit gate runs a different form: `scripts/githooks/pre-commit` calls
`python3 scripts/docs-audit.py --staged`, blocks on exit 1 and PRINTS-AND-ALLOWS on exit 2. In
staged mode every read, existence check and directory listing is redirected to the git INDEX. So
a guard can be perfectly live under `make check` and still stop nobody committing, and only one
of the fifty had ever been shown to block a real commit.

**The answer: 41 mutations, staged into the index, and NOT ONE was weaker under `--staged`.**
38 blocked the commit outright. Where the two forms differed at all, `--staged` was the STRICTER
one — `enter_staged_mode` redirects content, existence, listing and globbing together, and the
comment above it says why: mixing index content with worktree existence "audits a tree that will
never be committed". It holds under test. **The index-redirection layer is not where the holes
are.**

**And one commit was actually refused, which nothing had done before.** `PASS_CRITERIA` lowered
from `holdout_accuracy >= 0.95` to `>= 0.9`, staged, `git commit` attempted with the hooks armed:
`FAIL pass criteria`, exit 1, `COMMIT BLOCKED: the markdown disagrees with the code`, `HEAD`
unmoved. The money gate cannot be lowered past this hook by accident.

### The four that do not block, and why each is right

- **`UNPRICEABLE_REASONS <= ROUTING_REASONS`** (`pipeline/routing.py`) is a module-level `assert`.
  The commit path executes zero product code by construction — `docs-audit.py` reads Python as
  TEXT and AST and imports only stdlib, `sigil-check.py` imports four stdlib modules — so a
  runtime assert *cannot* gate a commit here. It gates the TURN instead: `make harness` will not
  even collect, so `make check` and the Stop hook catch it immediately and loudly.
- **`CAPTURE_CLAIM_FIELDS <= Card.__annotations__`** (`store/master.py`) is an import-time
  `RuntimeError`, same shape and same disposition. **§3 names this binder and reads as though the
  hop is closed; at commit time it is not**, and that implication is stated here rather than left
  to be rediscovered.
- **A failing `sigil-check.py --self-test` warns and allows**, which `scripts/githooks/pre-commit`
  argues in its own comment — *"a broken checker is not evidence that a screen is wrong, and
  blocking on one would make the bypass habitual"*, the same rule the auditor applies to exit 64.
  Checked rather than assumed: `make sigil-check` runs the self-test WITHOUT a `-` prefix, so a
  broken pattern fails `make check` and blocks the turn one gate later.
- **One roster entry was mis-paired**, not a guard that failed: `check_detector_standing` never
  opens `docs/DECISIONS.md`, and its docstring says D75's corpus is deliberately out of scope.

**Two corrections to the run that produced this, because a measurement is worth what its errors
are worth.** First, the earlier fifty-of-fifty included at least one verdict attributed to the
wrong guard: the subset `assert` never went red under the full audit either, so what that agent
watched fail was `reason emissions`, a different row. Second, the adversarial pass that reviewed
this run raised two further defects and NEITHER survived checking — it reported D75's 867-frame
figure as contradicting itself across files (all ten mentions agree, 867 photographs, three
boxes) and the sigil check's blocking half as vacuously green (it scans 62 files, finds nothing
because there is nothing to find, and two `sigil-ok` exemptions carry their reasons).

### What is genuinely open

**Eight rows are green over nothing when no markdown is staged.** `check_paths`,
`check_make_targets`, `check_pkmnscan_commands`, `check_harness_tests`, `check_decision_ids`,
`check_env_vars`, `check_doc_hygiene` and `check_positional_references` take the narrowed `docs`
list, and all eight read doc→code. Commit no markdown and they print `ok` over an empty subject —
`paths 0 references resolve` against 1,856 whole-tree, and the make-targets row 0 against 315. **The
narrowing is right** (a doc→code row has nothing to say about docs you did not touch) **and the
word `ok` is what is wrong with it**: a row that checked nothing reads exactly like a row that
checked everything and was satisfied. `check_pkmnscan_commands` already shows the way out — it
splits itself, using `docs` for "does this reference resolve" and `all_docs` for "is this
documented anywhere". Saying `0 of 1,856 in scope` instead of `ok` would cost nothing and is not
done here only because it touches eight rows and their published counts.


---

## 14 — A pooled card reaches the pricing table and the box walk, and `located` suppresses the label everywhere and the photograph nowhere

**Asked and answered 2026-09-05, on the render-conditions question `make docs-audit`'s
`views exposure` row defers to D24's owner.** The row's own sentence offers three discharges —
drop the manifest line, prove the screen pooled-free the way `app/tests/fulfillment.spec.ts`
does, or take the ruling to the owner. This is that third one, with the trace behind it.

**THE ANSWER IS YES, AND NOTHING FILTERS IT.** A `located: false` card carries a real `box` and
`index` into `pricing.json`, into the cross-run worklist, into `#/inventory`'s walk and into
`#/`'s hero deck, and every one of those screens draws `photoUrl(box, index)` off it. The
exposures are real. They are not formalities.

### The premise that was assumed, and why it is false

`CLAUDE.md` says code cards go through `./pkmnscan scan` — QR, free, no model call — rather than
`identify` / `join` / `emit`, which reads as though a pooled card never reaches a pricing row.
That is true of the QR path and it is not a filter, because the registry gives `pokemon_code`
a full singles-track profile:

| field | `pipeline/games.py` | consequence |
|---|---|---|
| `located` | `False` (`pipeline/games.py:446`) | no label, no slot |
| `catalogued` | `True` (`pipeline/games.py:461`) | passes the only join-path filter there is |
| `join_key` | `name_only` (`pipeline/games.py:449`) | a real strategy, not `not_joined` |
| `prompt` | `pokemon_code_v1` | it is submitted to the paid Batch |

`pipeline/join.py:1039` routes `name_only` to a working `KeyStrategy`; the entry beside it,
`NOT_JOINED: None` at `pipeline/join.py:1040`, is what a game that never joins looks like, and
`misc` is its only holder (`pipeline/games.py:736`). And `identify` does not merely tolerate a
code card — `cli/cmd_identify.py:397` names `CODE_GAME = "pokemon_code"` and
`cli/cmd_identify.py:426` builds C8's code ledger out of code cards that went through the
paid run. **The singles pipeline has a code-card lane by design.**

`codes/__init__.py` states the schema half in as many words: no second capture path, the same
server, the same store, "`located: False` is the whole of the schema difference".

### The chain, end to end

1. **Capture.** `server/capture_server.py:1034`'s `photo_path(box, index)` has no game
   dimension. A code card's photograph lands in `captures/cards/box<n>/<index>.jpg` beside
   every located card's.
2. **Scope.** A run's scope is the whole box directory (`server/pipeline_routes.py:275`) or a
   symlink set keyed by index alone (`server/pipeline_routes.py:220`). No game is consulted.
3. **Join.** The one exclusion on the resolve path is `games.is_catalogued`
   (`cli/resolve.py:689`, `cli/resolve.py:1384`), and `pokemon_code` is catalogued.
   `cli/resolve.py:404`'s pooled skip is inside `box_views`, a **label renderer**, not a run
   filter.
4. **The table.** `cli/cmd_join.py:194` writes `positions: [{box, index, label}]` for every
   matched SKU across every game join, with no `located` test.
5. **The merge.** `server/pipeline_routes.py:1836` de-duplicates positions across runs on
   `(box, index)` and never asks whether one is located.
6. **The screen.** `app/src/Pricing.tsx:764` draws a thumbnail per row and
   `app/src/Pricing.tsx:2637` the full-size photo in the drawer, both off `positions[n]`.

**IT HAS ALREADY HAPPENED, AND THE REPO SAYS SO IN THE PAST TENSE.**
`server/pipeline_routes.py:1470` records that pooled cards "do reach a join and did land in
this table wearing `Box N · Section N · Card M`", and
`harness/tests/t7_store_and_seams.py:11336` asserts it as a live property today. What that fix
changed was the **caption**: `_relabel_positions` swaps `Position.label` for `join.place_text`
and, in its own words at `server/pipeline_routes.py:1458`, leaves `box` and `index` travelling
"exactly as stored" — which are the two integers `photoUrl` is aimed by.

### The pattern, stated once

**`located: false` suppresses the position label and the position bar on every owner screen,
and the photograph on none of them.** Four call sites, one shape:

- `app/src/Inventory.tsx:654` draws the pooled sentence in place of a label; the retire
  dialog's `<img>` at `app/src/Inventory.tsx:836` is unguarded, and the `located` test at
  `app/src/Inventory.tsx:849` suppresses only `PositionBar`.
- `app/src/CardLocations.tsx:547` drops the bar for a pooled copy; the `<img>` at
  `app/src/CardLocations.tsx:530` above it is unguarded.
- `app/src/PositionBar.tsx:111` returns null for a pooled place.
- `server/capture_server.py:2295` and `server/capture_server.py:2569` serve a pooled row
  "undecorated but not bare" — no flat `label`, and `box`, `index` and `photo` all present.

The wire makes the client-side version of this hard on purpose and by accident:
`app/src/types.ts:1630` types a position as `{box, index, label}` with **no `located` and no
`game`**, so `#/pricing` could not filter what it draws even if it wanted to — the only pooled
signal reaching it is a string inside `label`.

### Per screen

| route | verdict | evidence |
|---|---|---|
| `#/inventory` | **live, and deliberate** | `app/src/BoxBrowse.tsx:79` gives pooled cards their own `Pooled` shelf and `app/src/BoxBrowse.tsx:115` a `Pooled · <game>` section header; `PhotoPanel` draws `app/src/BoxBrowse.tsx:1771`'s `photoUrl` checking only `photo === null` and `photo_reclaimed_at`. The screen is BUILT to walk them. |
| `#/pricing` | **live** | the chain above. Also: `app/src/Pricing.tsx:782` starts `picked` empty, which D86 defines as "every open run", so the manifest's no-`?run=` render draws the worklist and its thumbnails, not a picker. |
| `#/` | **live, and the weakest link** | `app/src/Home.tsx:125` builds `photoUrl` from a box's `next_index` high-water mark and consults no card record at all, so `located` is not knowable there. `app/src/Home.tsx:156`'s second pass filters on photo, capture time, state and name — not on `located` — though `InventoryCard` carries both `game` and `place`. |
| `#/runs` | **live** | `app/src/RunsComposer.tsx:692` draws the crop-preview sample, and `server/pipeline_routes.py:917` picks it out of the box's whole capture directory with no game filter. |
| `#/gallery` | **formality, genuinely discharged** | `app/src/Gallery.tsx` replaced `photoUrl` with `SPECIMEN_PHOTO` through `CardLocations`'s `photoSrc` seam on 2026-09-06, and its pooled fixture carries `has_photo: false`. The reach `_photo_reach` still reports is through that seam. |

**`app/tests/inventory.spec.ts:4357` does not answer this**, though it reasons about pooled
boxes: its subject is a box with `fill: 0` in the box REGISTRY, which is how a box of code
cards looks in the shelf LIST. The cards themselves are on the `Pooled` shelf, drawn in full.

### Why it is latent rather than live today

`docs/specs/code-cards.md` §8.1: **no real code card has ever been through this pipeline**, and
every decode number in that spec is synthetic. So the store holds no pooled capture and no
render can contain one. What arms every row of the table above at once is the owner
photographing their first box of code cards — which is what `#/codes` exists for, and a moment
they choose rather than stumble into.

### The recommendation

**Do not weaken `_pooled_exclusion_evidence`.** The tightening on PR #148 — a `test(...)` whose
title names `pooled` and claims `never` — is the correct reading, and this trace is why: the
loose form buys `#/inventory` and `#/pricing` with incidental prose (`app/tests/pricing.spec.ts`
mentions `located` once, about a departed record; `app/tests/inventory.spec.ts` mentions
`pokemon_code` in a `#/codes` fixture) on two screens that draw pooled photographs in fact.
An exemption bought by a word is worse than no exemption.

**One shape already exists and it is the one to copy.** `app/src/Fulfillment.tsx` drops a pooled
copy from the view outright — `app/src/Fulfillment.tsx:272`, `:437`, `:545` — rather than
suppressing its label, and `app/tests/fulfillment.spec.ts` asserts it in a titled test. That is
the only exclusion in the product that a photograph cannot get past.

**Three answers are available per screen, and they are not the same answer:**

1. **`#/gallery`** — nothing to decide. Write the `never`-titled test over the existing
   `SPECIMEN_PHOTO` fact and the row goes quiet honestly.
2. **`#/`, `#/runs`, `#/pricing`** — these draw pooled photographs incidentally, and none of the
   three has a reason to. The cheapest honest fix is a filter at the source: a `located` field
   on `PricingSku.positions` (the wire cannot express the fact today), a `game` test in
   `deckFromCards` plus a card-record consult in `deckFromBoxes`, and a game filter on the
   crop-preview sample. Each is small and each earns a `never`-titled test.
3. **`#/inventory`** — the only one that is a real question. Its `Pooled` shelf is a designed
   feature: the owner's one view of stored cards (D31) showing every card, including the
   pooled ones. Filtering the photograph there removes something built on purpose. The
   alternatives are to leave it exposed and drop the manifest line (so `make screenshot` never
   renders it), or to gate the photograph on the shelf rather than on the row. **This is the
   ruling that is D24's owner's to make, and this entry does not make it.**

**What is NOT recommended is the sentence that makes all of this go away**: "code cards go
through `scan`, so no pooled card is ever joined". It reads as a design constraint and it is
not enforced anywhere — the registry, `cli/cmd_identify.py:397` and
`harness/tests/t7_store_and_seams.py:11336` each contradict it. If the owner wants it to be
true, the place to make it true is `pipeline/games.py` or `cli/resolve.py`, not `CLAUDE.md`.
