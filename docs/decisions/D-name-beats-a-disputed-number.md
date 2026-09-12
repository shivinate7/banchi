## D-name-beats-a-disputed-number — The name decides a disputed number, and both readings reach the screen

**The owner was working a 48-card review queue and reached a card whose photograph plainly reads `Deathgrip`, `SFD · 163/221`.** The screen's headline was *"Is this the right card at
all?"*, the reason `name_disputed`, and the only row it offered was **Blood Money 162/221** —
the card it had just finished telling them was wrong. Pressing `L` and typing the name the
model had already read showed `Deathgrip · Spiritforged · 163/221` as the top hit.

> *"i'm still dealing with this point of frustration"* — *"and i had to click L to see this
> option -- the initial suggestion is just [the wrong card]"* — *"so annoying"*

**Then, on being asked which signal should win:** *"and i mean frankly, it could've suggested
both, say hard bargain and factory recall both on the same page."* And on the rung below it:
*"Release them when the name resolves to exactly one card."*

### The measurement, over every such card the store has ever recorded

| read name | read number | the name's real number | what the pipeline offered |
|---|---|---|---|
| Deathgrip | 162/221 | 163/221 | Blood Money |
| Hard Bargain | 135/221 | 136/221 | Factory Recall |
| Not So Fast | 046/221 | 045/221 | Poro Snax |
| Irelia, Blade Dancer | 190/221 | 195/221 | Forgefire Cape |
| Wizened Elder | 045/298 | 065/298 | Defy |
| Confront | 139/298 | 129/298 | Cithria of Cloudfield |
| Emperor's Divide | 061/221 | 043/221 | Aspiring Engineer |
| Reckoner's Arena | 061/298 | 286/298 | Poro Herder |
| Aspirant's Climb | 061/298 | 276/298 (+ a promo 276a) | Poro Herder |

**Nine of nine: the NAME was right and the NUMBER was wrong.** Eight of the nine names answer
exactly one card; the ninth answers one card printed in two sets. The pipeline offered a
different card every single time. Seven have since been answered by hand, and in
**seven of seven the operator chose a row the name finds**.

**The rung below it says the same thing 212 times.** `number_unread_name_matched` — D35's
fallback, where the number could not be read and the name found the row — has fired **212**
times on this store. Every one was answered by a human. **In 212 of 212 the human chose exactly the SKU the entry was already holding.** Not one disagreed.

### Why the caution was aimed at the wrong signal

**A card name is a long, distinctive string.** Misreading one into ANOTHER VALID CARD NAME is
vanishingly rare, and when it fails it usually fails into nothing — which is visible.
**A collector number is three glyphs**, and a single bad digit lands on a real row for a real
card, so its failure mode is a confident wrong answer that looks exactly like a right one.
D35 saw this clearly and wrote it down: *"The name is the more reliable field, which is the
argument for the whole rung."* D146 measured the same shape from the other side — box 1's
`1/51` read `Irelia, Blade Dancer` at `190/221`, which is `Forgefire Cape`, `Epic`, exactly
the rarity claimed, so nothing was flagged and the wrong card was listed.

**So D35's diagnosis was right and its trigger was wired to the wrong event.** It fires only
on an EMPTY number lookup — *"A number that matches rows is never second-guessed"* — and
emptiness is the failure that was already visible. The invisible one is a number that lands
on a real row for a different card, and the name is the only other thing read off that
photograph that can contradict it.

**WHAT FALLS is the blanket in D35's *"may never list a card on its own"*.** That was the
owner's ruling of 2026-08-24 and it is the owner's ruling of 2026-09-12 that replaces it,
on 212 answers none of which disagreed with the machine.

**WHAT SURVIVES is the caution itself, now aimed.** D35 distrusted the name as a WEAK signal,
and a name answering SEVERAL cards is exactly that — still queued, with its photograph, as it
always was. `Aspirant's Climb` is printed in Origins at `276/298` and again as a promo at
`276a/298`; no claim about a stack can say which is in the box. **Also untouched:** the name
is never a KEY (`CLAUDE.md`'s rule stands — the number is tried first and wins wherever
nothing contradicts it), and both sides still pass through `join.name_index_key`, which folds
away the embedded number that makes `Delibird - 105/132` and `Nickit` share one column.

### What the ladder does now

**Two conditions, and both must hold before anything is released:** the name answers exactly
one CARD — `(Set Name, folded Number)`, so finishes beneath one card are not a question —
and the ladder settles the finish from that card's own claim. Either one failing means a
human looks.

- **`name_disputed`** — where both hold, the name's row IS the answer and the card is listed.
  Where they do not, the entry carries **both readings**, the name's rows first, each stamped
  `found_by` so the screen can say which signal argued for which. That is the owner's own
  shape: *"it could've suggested both."*
- **`number_unread_name_matched`** — where the name answers one card, the card is listed.
  Where it answers several, it queues exactly as before.

**Replayed against the store, through each run's own export:** `name_disputed` 8 listed and 1
queued (the promo); `number_unread_name_matched` 201 listed and 11 queued. **209 released, and 209 of 209 match the SKU the human chose. Zero disagreements.**

**Nothing is guessed and nothing is dropped.** `pipeline/join.py:name_alternatives` decides
nothing — it offers rows — and the release gate is two facts about the evidence rather than a
preference for one field. `distinct_cards` is the test that keeps it honest.

### The group offer clustered on a word a rule had already fixed

**The owner, in the same session:** *"i also somehow had to still claim items in bulk that
they're near mint rather than it being default."*

`ReviewQueue.tsx:groupOffer` clustered on `only.condition`, and the route's own uniformity
check required one condition STRING. `Near Mint` and `Near Mint Foil` are
**one grade and two finishes**. Of the 52 entries the owner's runs generated on 2026-09-12, **40 offered exactly one row and every one of those rows was Near Mint** — 21 plain, 19 foil. Times three reason
codes, that is up to six presses to confirm a grade **D137** fixes by rule.

**Both sides cluster on the GRADE now.** The finish is not what a group decides: each member
is answered with its own row, whose finish the ladder chose from that card's own claim before
the route was reached. The grade is read off the registry on the server
(`_condition_grade`) and recognised by spelling on the client (`gradeOf`), which fails towards
NOT grouping — so the client can only ever offer a subset of what the route accepts, which is
the property `groupOffer`'s own comment demands. **Sealed product still refuses**: `Unopened`
is a different grade, not a different finish. The confirm panel stops asking for the grade at
all, because a rule already answered it.

### Two findings that were not defects, and one that is

**Reported: `rarity` is null on every candidate, and the candidate path is not narrowed to Near Mint.** Both are true of the payloads and false of the code. Grouped by the entry's own
`first_seen`, over the whole store:

| entries first seen | carry `rarity` | non-Near-Mint conditions |
|---|---|---|
| 2026-09-12 | 70 of 70 | none |
| 2026-09-11 | 5 of 1259 | 852 rows |
| 2026-08-25 … 09-02 | 0 of 339 | 80 rows |

Every entry written today carries rarity and is Near Mint only. `_candidate_rows` has emitted
`rarity` since 2026-09-11 and `Catalog.from_export` has narrowed since D137 landed the same
day. **The `Calm Rune` payload that prompted the report is `first_seen: 2026-09-11`**, written
the day before both, and `app/src/types.ts` already documents that absence as ordinary.
**Nothing was changed for either**; changing working code to fix a stale reading would have
been the defect.

**What IS real is why those payloads cannot improve: 513 of 565 entries are frozen at the code that wrote them.** `queues.upsert` is reached only from `queues.apply_run`, a join is
scoped to a run, and a run is scoped to a box — so an entry whose run has moved on is never
re-resolved by anything. The two reports above are that one fault wearing two faces.

### What is NOT built, and is recorded here rather than left to be rediscovered

None of these are started. Each is its own change with its own route, screen and tests, and
half-building any of them would be worse than naming them.

1. **A store-wide queue refresh.** Every open entry re-resolved against a current export,
   independent of any run — `reconcile --live` (D87) is the precedent and the same argument.
   It must never re-queue a `cleared_by_human` entry; D28's undo is the only door back.
2. **The answer does not fold through.** Answering the queue writes the SKU; the pricing
   table is written by `join`, so the operator must go to `#/runs` and press a step. The
   owner: *"after finishing review queue having to do 'join' again, is so fucking
   unintuitive."* `D156`'s `_unsent_ledger` re-derives from the live store rather than from
   the join's table, and that is the shape to look at first.
3. **99 identified, SKU'd cards are unreachable.** Run `2026-08-29-box1-01` is refused by
   `refuse_reallocated` (D36) because box 1 was deleted and its number reused. The cards are
   in box 3 at indices 724–822, a gap no live run covers. The upstream fault is that a run is
   bound to a box NUMBER; **D145** landed `bid` — allocated once, never reused — for this
   exact class, and the run object never adopted it. The owner: *"the PROBLEM IS UPSTREAM ...
   there shouldn't have been this mistaken path."* A `bid` binding protects runs made after
   D145 only; a drawer deleted before it has no bid to recover, so the 99 need a one-time
   rescue keyed on the cards' own `(box, idx)` and digest.
4. **A mass-clear for typed prices.** 428 answers in the corpus, 269 of them from 2026-09-07.
   The owner chose a button over auto-expiry: *"Just give me a mass-clear button."*

### The thesis, in the owner's words

> *"Boxes were just over used / referenced too much of a crutch."*

The box was the only handle the code had, so everything grabbed it — runs, joins, queue
entries, exports — and none of those are about a drawer. Every finding above is one shape:
**the pipeline collects evidence, discards it, asks a human to supply it again, cannot revisit its own answer when it learns better, and does not act on the answer when it gets one.** This entry is the concrete instance; the general fix is a separate pass and will
reopen D48.

### Coverage

T3 carries the ladder — the release, the two-card name that is still queued, the unsettled
finish that is still queued, the `found_by` stamp, and `distinct_cards` asserted directly
because a single-set fixture cannot reach its set half. T7 carries the group grade in both
directions. **Mutation-tested, twenty arms, nineteen caught.** The one survivor is proved
unreachable rather than unguarded — `name_disputes` makes the two row sets disjoint by
construction, so deleting the de-duplication filter is a no-op — and it is kept for the
reason `name_corroborates` keeps its blank-read line.

**One arm found a real hole, which is the argument for running them at all.** The release
gate first read `len(alternatives) == 1`, and a single row means two different things: the
ladder narrowed a stack to one, or the name answered a card the export stocks in ONE finish
and the ladder REFUSED it. `Alcremie ex` is the second on the committed fixture — one
`Near Mint Holofoil` row, `metadata_not_stocked` under a `normal` claim — so the gate read a
refusal as an answer and would have listed the card on a finish the ladder had just
rejected. `CLAUDE.md`'s first hard rule, broken by a boolean that counted rows instead of
asking. `NameSide.settled` carries the ladder's own answer now, and T3 holds that case.
