# Multi-game (build-order step 14)

`docs/GATES.md` named step 14. D21 through D25 carry the rulings. This file carries the
argument and the list of things a later session must not undo.

**The most valuable part is section 2.** Real TCGplayer exports refuted four assumptions that
were about to be built on. Three of them were the owner's own. Each would have failed quietly.
A wrong `Product Line` string joins to no row at all. A rarity that nobody prints cannot be
selected on a screen. That is the whole case for D22's refusal to author a vocabulary from
memory.

---

## STATUS

**BUILT.**

- The vendored registry in `pipeline/games.py`, with four real exports behind it.
- Four audit rows over the registry (section 6).
- Per-game dispatch for the join key, the prompt, the crop bands and the card shape.
- The `game` claim, carried through every hop from the capture screen to the join. The
  picker is on the capture bar, and `GET /games` serves the registry to it.

**Section 9 scoped five jobs, and all five shipped.** They are the rarity claim (D23), the
multi-export join (D25), pooled non-located inventory (D24), two opsec discharges, and per-game
prompts. Each section keeps its argument.

**One job was measured and lost.** The rarity clause in the prompt was built and tested against
best-case claims. Holdout fell and high-confidence misses rose. It is switched off:
`cli/cmd_identify.py` passes `rarity_claim=None`, and the comment there gives the numbers. The
rarity claim still does its other two jobs (9.1). Re-enable the clause only with a rig-photo
measurement that says otherwise. `PKMNSCAN_T1_RARITY=1` is the instrument
(`harness/tests/t1_id_eval.py`).

**What has met a real card.** Nothing here. The identification measurements ran on Pokemon
cards through a pipeline that had no `game` field. No Riftbound, One Piece or misc card has been
photographed, identified or joined in a measured run. Every claim below about those games is a
claim about a CSV file, not about a photograph. Whether that has changed on the owner's rig:
unmeasured here.

---

## 1. Scope, and the axis this is not

D14 has a mode toggle, and it is **not this one**. D14's axis is the *track*: singles or codes,
two schemas, two sales channels, two fulfilment stories on one rig. `game` is the *product* axis
inside a track. `pokemon_code` sits at the intersection. It is a Pokemon product line, captured
on the singles rig, and disposed of down the codes track. That is why both axes exist.

The step covers five capture choices: `pokemon`, `pokemon_code`, `riftbound`, `one_piece` and
`misc`. It covers the registry that describes them, the dispatch that reads it, and the join
partitioning that follows.

---

## 2. The ground truth from the exports

Four committed exports share one 16-column header, byte for byte.

    fixtures/sv09_export_untouched.csv           Pokemon, SV09 alone
    fixtures/pokemon_wide_export_untouched.csv   Pokemon, four sets across three eras
    fixtures/riftbound_export_untouched.csv      the whole English Riftbound catalog
    fixtures/onepiece_export_untouched.csv       One Piece, three sets (PARTIAL)

**The shared header is the finding that makes the architecture survive.** D22 named it the
highest-risk assumption: TCGplayer might not carry Riftbound or One Piece as `Product Line`
values at all. It does. The catalog join is structurally valid for every product line, and the
per-game work is vocabulary, not architecture.

**Which export is complete decides how far a matrix may narrow.** The Riftbound file is the
entire English catalog, so "no plain row exists for this rarity" is a statement about the
game. The One Piece file is three sets out of many, so the same observation is a statement about
three sets.

### 2.1 `Product Line` is not what anybody would guess

    Pokemon
    Riftbound League of Legends Trading Card Game
    One Piece Card Game

A shortened form joins to no row at all. It is not an error, a mismatch report or a partial
result. `Catalog.from_export` filters to the game's `product_line`, and a wrong string filters
every row out. D25 makes this the one case where the join refuses instead of continuing,
because a zero-row catalog looks exactly like an empty run.

### 2.2 `rune` is not a rarity, and `Showcase` is the alt-art treatment

- `rune` appears in no `Rarity` cell in the English catalog.
- `alt art` is not a rarity. It is what `Showcase` IS, for example `Ahri, Alluring (Alternate
  Art)` at `066a/298`.
- The real cells are Common, Uncommon, Rare, Showcase, Promo, Epic and TCGplayer's literal
  string `None`.

`Showcase` is the one rarity in that file that the data supports narrowing. Every Showcase
product is stocked in foil grades only, with no plain Near Mint row. The file is the complete
English catalog, so "no plain Showcase is printed" is a statement about the game.
`finish_by_rarity["Showcase"]` is `("foil",)`. Every other Riftbound rarity stocks both finishes
and is authored with both.

**The residual risk is named.** A complete catalog is complete on the day it was pulled. A
future set could print a plain Showcase. The `matrix superset` row blocks the moment an export
proves one. The fix is to widen that line. That is the audit doing its job. It is not a reason
to widen ahead of the evidence and spend the only narrowing that the data supports.

### 2.3 Riftbound and One Piece share a condition vocabulary. Pokemon does not

The `Condition` column of both games is the five grades crossed with `{"", " Foil"}`, plus
`Unopened`. There are two finishes and no reverse holo.

    riftbound   normal -> "Near Mint"   foil -> "Near Mint Foil"
    one_piece   normal -> "Near Mint"   foil -> "Near Mint Foil"
    pokemon     normal -> "Near Mint"   holo -> "Near Mint Holofoil"
                reverse_holo -> "Near Mint Reverse Holofoil"

A screen must offer the chosen game's own finish chips. Riftbound prints no `holo` or
`reverse_holo`, and the server refuses them. `app/src/types.ts` types the finish as `string` on purpose. A union of every game's finishes
would type a Riftbound `reverse_holo` as legal. That is the same defect in a wider hat. The
server validates the claim against the chosen game's own list and answers `variant_invalid`.
The app's job is to offer the right chips, not to prove them in the type system.

### 2.4 One Piece carries no denominator

    OP15-079   EB04-042   ST26-005   PRB02-014   P-105

The number is a set code, a hyphen and a three-digit index, printed on the card as the export
writes it. There is no `printedTotal` in this game. So the composed key (zero-fill the number,
append a slash and the printed total) cannot match it. That forced `join_key` to become a
per-game strategy. The registry names `printed_code` for One Piece. The identification returns
one string, and the join matches it against the export's `Number` cell verbatim.

Blank `Number` rows are not an exception. They are `DON!!` cards and sealed product.
`pipeline/join.py` falls to the name path whenever the identification carries no number.

**Riftbound needs the same strategy for a different reason.** Most Riftbound numbers are
Pokemon-shaped (`179/298`, `066a/298`, `303*/298`, `SP3/006`). Some carry no denominator: `R04`,
`R04a`, `T03`, `T02 // T03`. A per-game field that holds one strategy has nowhere to put a
fallback. Matching the printed identifier verbatim covers both shapes, because the catalog keys
on the `Number` cell verbatim. It also keeps the suffix. `066a/298` is a different card from
`066/298`, and any normalization that folds the letter silently merges two SKUs.

### 2.5 Two smaller findings

**`DON!!` carries punctuation, and it is part of the cell.** Nothing folds, strips or
normalizes it. The audit's fold check exists to catch a session that tidies it to `DON`.

**Sealed product is accounted for differently in each game, and both are correct.** Pokemon's
sealed rows carry a blank `Rarity`. A blank is not a vocabulary item, and the audit skips a
row with no rarity. Writing `""` into the rarity tuple would invent a rarity nobody prints.
Riftbound's and One Piece's sealed rows carry the literal string `None`. That is a cell, so it
needs accounting, and both entries list it as not claimed.

---

## 3. `game` is a per-card claim, not a mode (D21)

### 3.1 The picker is on the capture bar

It sits beside Box, Set hint and Finish. It is not on the app shell. `game` joins the claim
family. It is client state, resent with every capture, and written to the record and the
sidecar.

**Mixed boxes are legal. That is not a concession. It is what makes the claim a claim.** A
shell-level mode would make the game a property of the session. The first time a Riftbound card
turned up in a Pokemon box, the operator would have to lie or stop.

### 3.2 Required, defaulting to `pokemon`, and D3's null does not transfer

The finish claim's `null` is meaningful, because a ladder underneath it infers a finish from
evidence. **No ladder infers a game.** A missing game is not "no claim". It is "no export", and
every consumer would have nothing to join against.

So the claim requires the field. The picker always has an answer and always sends it.
`DEFAULT_GAME` is a **read-side backfill** for records written before the field existed. It is
applied where such a record is read, and never where one is written. `Card.game` in
`store/master.py` is `Optional` for that reason. The registry's `get` takes no default. A
caller that wants the backfill asks for `DEFAULT_GAME` by name, where the substitution is
visible. A default inside the accessor would turn every unknown key into Pokemon. The first
symptom would be a Riftbound card priced off a Pokemon export.

The server draws the same line with two codes.

    game_invalid      the string is not a game at all: a typo, or a client written
                      against an older registry
    game_unverified   the game is registered and nobody has seen a TCGplayer export for it

Absent is not refused. Absent is a sidecar written before the field existed.

### 3.3 The tuple that binds the store's hops

A capture-time claim crosses many independent restatements between the control and the
consumer. Two of them fail silently. `Inventory.parse` filters on the card dataclass's
annotations, so an undeclared field is dropped on reload. A literal tuple in `record_capture`
would let a new claim survive a first capture and be discarded by every re-record.

`store/master.py:CAPTURE_CLAIM_FIELDS` is one tuple that the places read. T7 asserts that the
settable set is every capture claim, in the order the store names them. `game` and the misc
`note` both ride it.

**The debt is narrowed, not closed.** The app-side hops stay hand-carried. No Python constant
can reach a `.tsx`. `make typecheck` sees a field added to `app/src/types.ts`. It never sees one
omitted from it (`docs/debts/`).

---

## 4. The registry (D22)

### 4.1 Pure literals, read with `ast`

`pipeline/games.py` holds one entry per game and imports nothing from this repo. So
`scripts/docs-audit.py` reads it with `ast.literal_eval` without running project code. Two rules
follow.

- **No name from the module may appear inside a registry literal.** `"normal"` is written out
  in both the finish tuple and the condition map, because `literal_eval` cannot resolve a name.
- **No function object may sit in an entry.** `join_key` and `prompt` are strategy names, which
  are strings from closed vocabularies in the same file. The consumer holds the dispatch from a
  name to a callable, where a reader can see it.

The vocabularies live beside the entries, so the audit can reconcile every entry against them.
A typo in one entry's `join_key` is then provable. Otherwise a join would quietly match
nothing.

**Every field is hand-authored, never generated.** It is ARGUMENT in D18's sense. A later
session could reasonably disagree with the stack order of the rarities or with which finishes a
rarity may claim.

### 4.2 `catalogued` and `unverified` are orthogonal

There are three states. The two that look alike have opposite remedies.

- `catalogued: True, unverified: False` is measured. An export was read, and the vocabulary was
  authored from its cells. This is every real game.
- `catalogued: True, unverified: True` is a real TCGplayer product line whose export nobody has
  seen. It is temporary, and the fix is to get the export. Every consumer refuses, because a
  guessed rarity list is what D22 refuses. No entry is in this state today. The state stays,
  because the next game added starts there.
- `catalogued: False` is `misc`. It is permanent and correct. There is no single `Product Line`
  to read, and no export is coming.

If the two shared a flag, every misc capture would read as a fault. A real fault would then hide
among the working 1% of the shelf.

The refusals mirror it. One exception is for a game with no catalog that will never have one.
That is a caller bug: branch on the predicate before the join. One is for a game that waits on
an export, which is a gap with a fix. One handler for both would let an unmeasured game hide
behind the working 1%.

### 4.3 Stack order, and where it is an admission

`rarities` is in stack order, not export order, because the capture screen renders it and the
operator holds a sorted pile. Each entry argues its order from something other than taste.

**Pokemon.** Common, Uncommon and Rare interleave with the in-set hits by their own sets'
numbering. `Secret Rare` and `Rainbow Rare` are appended, and that is the one place the order is
an admission. They are SM and SWSH era secrets. No set in a committed export carries both an
SV Hyper Rare and an SM Secret Rare. So no numbering orders the two eras.

**Riftbound.** It uses the game's own ascending ladder, and the row counts fall along it.
Showcase and Promo are appended, because neither is a rung. One is a treatment across the
ladder, and the other is a distribution channel. Ordering them against the rungs would invent a
rank that the game does not have.

**One Piece is less measured, and says so.** C, UC, R, SR and SEC are the game's published
ladder. Unlike Riftbound, the row counts do not corroborate it, because the file is three sets
and a partial export cannot rank rarities by frequency. So the ladder comes from the game, and
`TR` above `SEC` is the thinnest claim in the entry. `L` and `DON!!` are card types and `PR` is
a channel, so all three are appended.

---

## 5. The superset rule

This is the argument that a later session will most want to undo.

### 5.1 Why unselectable is only safe over a superset

D23 makes the capture screen render a finish chip that a rarity claim excludes as
**unselectable, not hidden**. The operator sees what the claim cost, and takes it back by
clearing the rarity. That is safe only while `finish_by_rarity` is a superset of reality.

A matrix narrowed to one export's observations makes a legitimate stack unclaimable. The chip is
grayed out, and the operator has no way to say what is true. The screen has decided that the
card in the operator's hand does not exist. **The superset rule and unselectable must never be
separated.**

### 5.2 Widen to what the printing admits

`finish_by_rarity["Rare"]` for Pokemon carries `normal`, though SV09 stocks no plain Near Mint
`Rare` row. It is authored beyond that one export on purpose. The wider Pokemon export stocks
plain Near Mint Rare rows in more than one era. Trimming the line to one export would make
those eras of plain `Rare` unclaimable.

The principle: **widen to every finish that the rarity's own printing admits. Narrow only where
the printing forbids it.**

- A main-set rarity sits in the reverse-holo slot and can be pulled plain. It claims all three
  finishes.
- A hit above the set is foil by definition and is not printed in the reverse slot. It claims
  `holo` alone. Widening it to `normal` would go past what the cardboard allows. It would buy no
  safety and leave the feature with no narrowing at all.
- Pokemon `Common` and `Uncommon` also claim `holo`, because the Prismatic Evolutions pattern
  cards (Poke Ball and Master Ball) stock Near Mint Holofoil rows for them.

### 5.3 The live unproved case asks, and does not block

The canonical unproved pair is One Piece's `SR` and `TR`. They are authored with `normal`
against an export of three sets out of many. In that file both are stocked in foil grades only.

Riftbound's `Showcase` was narrowed on the same observation. The asymmetry is deliberate,
because that file is the whole English catalog and this one is partial. "No plain SR in three
sets" is a fact about three sets. So `SR` and `TR` are the live example of the superset. They
are authored beyond the evidence and reported by the `game coverage` row as a question that
blocks nothing. If a fuller One Piece export ever shows `SR` foil-only across the catalog,
narrowing it becomes the same argument that Showcase already won.

---

## 6. The four audit rows

The rows are named, not numbered (D16). Each is deterministic. Each reads the committed exports.

- **`game vocabulary`** blocks. Some entry's `rarities` or `rarities_not_claimed` accounts for
  every rarity cell in every export. Every authored rarity's raw form appears in an export. A
  rarity whose folded form matches an export string and whose raw form does not is a typo. It
  can never false-positive, so it blocks.
- **`game coverage`** is advisory. It asks about the reverse direction: a finish that a matrix
  allows and no export in view stocks. Absence from one set proves nothing, because `Promo` and
  every pre-SV rarity are legitimately missing from an SV09 fixture. So the row prints and
  allows. Section 5.3 is why its One Piece questions are the rule working.
- **`matrix superset`** blocks in one direction only. It blocks on an **observed** rarity and
  finish pair that the matrix is missing. It only asks about the excess. Widening is legal and
  narrowing is loud.
- **`join key shape`** blocks. It checks the composed-key games against the export's actual
  `Number` cells. It would have caught D25's real defect had it existed earlier.

`PKMNSCAN_EXPORTS` widens the advisory row and nothing else. It holds colon-separated paths to
extra exports that the repo cannot carry. A path that does not resolve is skipped in silence,
and nothing read through it can fail a commit. A gate that a file on one person's disk can break
gets switched off. A gate that needs such a file has already switched itself off for everybody
else.

---

## 7. Per-game dispatch

The registry says *what*, by name. Four consumers say *how*. Each dispatch maps a strategy name
to an implementation. It is checked at import against the registry's vocabulary. A name added
in one place stops the process next to the mismatch, not at whichever call reaches it first.

**Join key.**

- `number_and_printed_total` is the composed key.
- `printed_code` matches the printed identifier verbatim.
- `name_only` is the blank-`Number` path.
- `not_joined` is a game that never reaches a catalog. It is a **named value, not an empty
  string**, so a consumer that dispatches on it refuses and does not fall through.

**Prompt.** `pokemon_card_v1` is the fingerprint that T1 scores against. `pokemon_code_v1`,
`riftbound_card_v1`, `one_piece_card_v1` and `misc_card_v1` are its siblings. `misc_card_v1`
comes from what a Magic, Yu-Gi-Oh, Weiss Schwarz or foreign-language card carries, not from
Pokemon's shape with the fields left blank. `unwritten` is the honest value for a game whose
prompt has never been written. Asking for it is a refusal. The alternative is Pokemon's prompt,
which fits every call and reads every card wrong. No entry holds `unwritten` today.

**The import check runs one way, on purpose.** A profile with no registry claimant is a strategy
authored ahead of its game. Blocking on it would force the registry and the dispatch to change
together in one commit. A registry name with no profile is the direction that breaks a run. It
stops at import with both names in the message.

**A strategy that no game claims does not stand.** It is a dead field, and this registry is
audited to prevent those. `misc` is identified and submitted to the batch API like any game. Its
free-text note is an addition, never a substitute for reading the card.

**Crop bands.** A band profile is a *selection*, not a rectangle. A card is 63x88mm whatever is
printed on it. The only per-game question is which bands are worth cutting. `pokemon` claims
`("title", "number")`. Every other entry claims none, because nothing has measured where a
Riftbound, One Piece, Yu-Gi-Oh or Weiss Schwarz card puts its title or identifier. A band
claimed without that measurement is cut over the wrong pixels. An export cannot answer this.

**Card shape.** `card_aspect` is the ratio that `geometry/detect.py` gates on.
`cli/cmd_identify.py` passes it in. It is not a module constant. `misc` carries `None`, and
**`None` refuses**. A detector with no aspect to check accepts any rectangle. `None` means a
human should look, and never that the code guessed. The cost is one lost crop retry on the
small share of stock that a person handles anyway. The alternative is a confident crop of the
stand, the desk or the next card along.

Pokemon's `0.716` is rounded on purpose. 63/88 is 0.7159, so the authored value moves the gate
by about 1e-4 relative against a tolerance of 0.15. Writing the fraction out would put
arithmetic in a file that must stay `literal_eval`-safe.

---

## 8. `misc`: the third state, and why it is not a gap

`misc` is the occasional Yu-Gi-Oh, Weiss Schwarz, foreign-language or Magic card. It is captured,
**located** and **identified** like any other card. It carries a free-text operator note typed at
capture, so search can find it later. Then it stops at the catalog.

**`product_line` is `None`, not `""`, and the type is the point.** No single cell exists,
because the entry spans four populations. Inventing a string would be the guess D22 refuses.
`None` is not a `str`, so the catalog's comparison can never be true for it under any export.
`""` is both a value that a malformed row could carry and the value that an unverified entry
uses. Using it would collapse two states on the one field that most needs to tell them apart.

**It is `located: True`. That field separates it from `pokemon_code`.** Both are outside the
join. Only one is outside the box.

**It sits outside D12 on two axes.** A foreign-language printing breaks "English". Magic,
Yu-Gi-Oh and Weiss Schwarz are different product lines, not a different era of this one. D12 is
not reopened. This entry is the explicit carve-out. It earns it by never reaching the pricing or
listing path where D12's Near Mint hardcode lives.

**Identification and catalog membership are different questions.** The predicate that a caller
branches on before the join answers only whether a TCGplayer export exists to match a row
against. It says nothing about identification.

---

## 9. The five jobs, and the argument behind each

All five are built. The sections keep the arguments that the code does not state.

### 9.1 The rarity claim, end to end (D23)

The capture screen offers a multi-select rarity claim, scoped by the chosen game. It does two
jobs today.

**1. Cross-check: the `rarity_claim_mismatch` review reason.** The variant ladder emits it, not
routing. Routing answers "is this trusted enough to list?". The ladder answers "which row is
this?". It filters candidate rows to the claimed rarities and reviews when nothing survives.
This is filter-then-contradict, because on a multi-set collision the filter breaks a
`duplicate_condition` tie for free.

**This is the job that pays.** T1's recorded misses are confident answers with the name right
and the digits wrong. No confidence threshold fires on those. A rarity contradiction does.

**Rung 0 must not consult the claim.** A human looked at the photograph beside the candidate
rows, and that outranks a claim about the stack it came from. The failure that taught this is
on the record: answered cards re-derived their disagreement and re-parked on every join.

**2. Narrow the finish chips.** The chips offered are the **union** of the matrix over the
claimed rarities. It is a union and not an intersection, because a Common and Rare stack
legitimately holds both plain Commons and holo Rares. Three rules each stop a specific harm.

- An empty rarity claim narrows nothing. That keeps the feature strictly additive.
- It never auto-selects, not even when one finish is left. Ladder rung 2 already resolves a
  holo-only Double Rare for free, and a manufactured claim would make rung 2 unreachable.
- Excluded chips are rendered unselectable, not hidden. That is safe only over a superset
  (section 5).

**3. The prompt clause** is off (9.4).

### 9.2 The multi-export join (D25)

`--export` is repeatable. **Never infer the game from a filename.** Read each file's `Product
Line` column and map file to games. Then invert to game to files, which must be exactly one.

**The join reads the `Product Line` column.** An export is never taken as product-line
agnostic. Two exports concatenated without that read would cross-join in silence.

**Catalogs are built per game and never merged.** A merged number index would report
cross-*game* collisions as though they were the cross-*set* collisions that the collision report
is about. They are different faults with different remedies. A set hint fixes one, and nothing
fixes the other.

**Refusals exit 1, write nothing, touch no queue and never prompt.** There are two cases: two
files that claim one game, and a game in the run with no export. The second names positions and
points at the correction route. The check runs before any catalog is built, so a run that will
refuse costs nothing.

**`emit` writes one import file across runs and games.** Two `Product Line`s in one file is
untested against TCGplayer's Import to Staged. The accepted fixture proves one line only. A
merged file whose games carry different export headers is refused. `--split-games` writes one
file per game, and it is the one-flag way back if the portal refuses a mixed file
(`cli/cmd_emit.py`).

### 9.3 Pooled, non-located inventory (D24), and two opsec discharges

A code card has no box, section or card position. It is a count. An index is acceptable as a
key, because the photo and sidecar are named after it on disk. It is not meaningful, because the
physical card is disposed of once the code is extracted.

**The seam is the one registry flag.** `located: False` means the position label is never
rendered. That covers the review queue, a run report and the pull preview. Non-located cards
never enter the Fulfillment view or the pull flow, because there is nothing to walk to.
`app/tests/fulfillment.spec.ts` asserts that a pooled card never reaches the Fulfiller's screen.
D24 asks for the assertion to be part of the work, not something added afterwards.

**Quantity is the unit, and the pipeline already computes it.** D7 aggregates by SKU with the
copy count. Surface it. Do not build a second inventory.

**Disposal is a terminal state.** A code card whose code has been extracted leaves inventory
permanently. The record is kept and the gap is permanent, which is `sold`'s shape. The store's
terminal states are `sold`, `retired` and `moved`. D26 landed as `retired`, and
`docs/specs/order-flow.md` section 10.1 tells it. Whether the codes track uses `retired` for
disposal: unmeasured here.

**Two opsec triggers fired with this work.** D16 said: revisit the opsec guard before the codes
track handles real cards. The recorded failure was over-triggering, because the guard blocked
placeholders in prose about the code format. So the fix is a narrower pattern, never a toggle.
`scripts/guard-opsec.sh` carries it. And `scripts/views.txt` may never name a URL whose render
can contain a code card.

### 9.4 The rarity clause in the prompt

The clause was scoped to the user turn, because it is per-card, so that it could not poison D3
rung 3. The system prompt says "Do not infer the finish from the card's rarity". A careless
clause makes it do exactly that, and poisons the one signal that catches a mis-sorted card.
`identify/prompt.py` keeps `_RARITY_CLAUSE`, and the measurement switched it off (STATUS).

**Ship a prompt change alone.** A prompt change and an accuracy measurement in one commit cannot
say which one moved the number.

### 9.5 Per-game finalization

Riftbound and One Piece have prompts (`riftbound_card_v1`, `one_piece_card_v1`), exports and
vocabularies. They claim no crop bands. Nothing has photographed a card of either game, so
nothing has measured where either puts its title or its identifier. Identification accuracy for
either game is unmeasured.

---

## 10. What is asserted, and what is merely consistent

**Proved by the exports.** The shared 16-column header. The three `Product Line` cells. Every
rarity string. The two condition vocabularies. The absence of a denominator in One Piece. The
plain Near Mint Pokemon Rares. The foil-only Showcase products.

**Authored beyond the exports, on purpose, and audited in the direction that can be proved.**
Every `finish_by_rarity` row wider than what an export stocks (section 5).

**Taken from the games and not measured.** One Piece's rarity ladder, and the relative rank of
`TR`.

**Not evidence at all.** Every claim about how a Riftbound or One Piece card photographs. The
card shapes are properties of cardboard. The crop bands are empty for exactly this reason.
Identification accuracy for either game is unmeasured.

---

## 11. What a later session must not undo

- **Do not narrow `finish_by_rarity` to one export's observations.** Unselectable becomes a
  trap (section 5.2).
- **Do not shorten a `product_line` cell.** A wrong string joins to no row at all, silently.
  The Riftbound one is not guessable.
- **Do not normalize `DON!!`, and do not fold a rarity suffix.** `066a/298` is a different card
  from `066/298`.
- **Do not give `misc` a `product_line` string.** `None` is not a `str`, and that property does
  the work.
- **Do not collapse `catalogued` and `unverified`.** They have opposite remedies (section 4.2).
- **Do not merge per-game catalogs, and do not infer a game from a filename** (section 9.2).
- **Do not put a name from the module inside a registry literal, or a callable in an entry.**
  The audit reads the file with `ast` and must never run it.
- **Do not let the rarity claim reach ladder rung 0.** Do not ship a prompt clause in the same
  step as a measurement.
- **Do not restore `operator_note` or any strategy that no game claims** (section 7).
