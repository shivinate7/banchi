# Multi-game — execution spec (build-order step 14)

Written 2026-08-23, behind a step already part-landed, for the reason
`docs/specs/order-flow.md` gives about itself: `docs/GATES.md` named step 14 and pointed at
nothing. D21 through D25 carry the rulings; this file carries the argument, the measurements
that produced it, and the list of things a later session must not undo.

**The most valuable thing in this file is section 2.** Three real TCGplayer exports arrived and
refuted four assumptions that were about to be built on. Every one of them was a reasonable
guess, three of them were the owner's own, and each would have failed quietly rather than
loudly — a wrong `Product Line` string joins to no row at all, and a rarity nobody prints
cannot be selected on a screen. That is the whole case for D22's refusal to author a
vocabulary from memory, and it is written out rather than summarised.

---

## STATUS — 2026-08-23

**BUILT.** The vendored registry in `pipeline/games.py` with four real exports behind it; four
audit rows over it; per-game dispatch for the join key, the prompt, the crop bands and the card
shape; the `game` claim carried through every hop from the capture screen to the join, with the
picker on the capture bar and `GET /games` serving the registry to it. `make docs-audit` is
clean but for two advisory questions, which section 6 explains and which are the rule working
rather than a defect.

**Section 9 scoped five jobs and all five shipped** (corrected 2026-08-25): the rarity claim
end to end (D23); the multi-export join (D25), proven byte-identical on a single-export
Pokemon run; pooled non-located inventory (D24) — `pipeline/games.py` carries
`"located": False` on `pokemon_code` and `app/tests/fulfillment.spec.ts` asserts a pooled card
never reaches the Fulfiller's screen; both opsec discharges — `scripts/guard-opsec.sh`
re-enabled with D16's narrowed pattern, and `scripts/views.txt` naming no code-card-renderable
URL; and per-game finalization as prompts, `riftbound_card_v1` and `one_piece_card_v1` written,
registered and dispatched to. That section keeps each argument.

**One of the five was measured and lost, and the measurement is the point.** The rarity
clause in the prompt was built, A/B'd for $0.17, and **switched off**: holdout fell 1.5
points and high-confidence misses rose by two. `docs/GATES.md`'s T1 section has the numbers,
and they are cited at the switch itself.

**WHAT HAS MET A REAL CARD.** Nothing here. Gate B ran 53 Pokémon cards through a pipeline that
had no `game` field in it. No Riftbound card, no One Piece card and no misc card has been
photographed, identified or joined. Every claim below about those three games is a claim about a
CSV file, not about a photograph.

---

## 1. Scope, and the axis this is not

D14 already has a mode toggle and it is **not this one**. D14's axis is the *track* — singles
versus codes, two schemas, two sales channels, two fulfilment stories sharing one rig. `game` is
the *product* axis inside a track. `pokemon_code` sits at the intersection and is the reason both
axes have to exist: it is a Pokémon product line, captured on the singles rig, disposed of down
the codes track.

The step covers five capture choices — `pokemon`, `pokemon_code`, `riftbound`, `one_piece`,
`misc` — the registry that describes them, the dispatch that reads it, and the join partitioning
that follows.

---

## 2. The measured ground truth

Four committed exports, one 16-column header shared byte for byte by all of them:

    fixtures/sv09_export_untouched.csv           341 rows, Pokemon, SV09 alone
    fixtures/pokemon_wide_export_untouched.csv  7802 rows, Pokemon, 4 sets across 3 eras
    fixtures/riftbound_export_untouched.csv    10078 rows, the whole English Riftbound catalogue
    fixtures/onepiece_export_untouched.csv      3622 rows, One Piece, 3 sets (PARTIAL)

**The shared header is the finding that makes the architecture survive.** D22 recorded, before
the exports arrived, that it was "not yet established that TCGplayer carries Riftbound or One
Piece as `Product Line` values at all", and named that as the highest-risk assumption in the
design — because if it were false, D8 and D11 would have no data and the whole shape would have
to change. It is true. The catalog join is structurally valid for every product line, and the
per-game work below is vocabulary rather than architecture.

**Which export is complete decides how far a matrix may be narrowed**, and that asymmetry is used
deliberately throughout. The Riftbound file is the entire English catalogue per the owner, so "no
plain row exists for this rarity" is a statement about *the game*. The One Piece file is three
sets out of many, so the same observation is a statement about *three sets*.

### 2.1 — `Product Line` is not what anybody would have guessed

    Pokemon
    Riftbound League of Legends Trading Card Game
    One Piece Card Game

Nobody would have written the middle one from memory, and **a shortened form joins to no row at
all**. That is the failure mode worth dwelling on: it is not an error, not a mismatch report, not
a partial result. `Catalog.from_export` filters to the game's `product_line`, and a wrong string
filters 10,078 rows down to zero. D25 makes that the one case where the join refuses instead of
continuing, precisely because a zero-row catalog otherwise looks exactly like an empty run.

### 2.2 — `rune` is not a rarity, and `Showcase` is the alt-art treatment

The owner's guess before the export was read is recorded in the registry because part of it was
simply not there: *"common/uncommon/rare/epic/alt art/showcase/rune"*.

- **`rune` appears in no `Rarity` cell in the entire English catalogue.**
- **`alt art` is not a rarity either — it is what `Showcase` IS**, e.g. `Ahri, Alluring
  (Alternate Art)` at `066a/298`.

The real cells are seven, six of them claimed: Common 2850, Uncommon 2625, Rare 1310, Showcase
1305, Promo 1090, Epic 765, and TCGplayer's literal string `None` at 133.

**And `Showcase` turned out to be the one rarity in this whole file the data supports narrowing.**
All 261 Showcase products are stocked in Foil grades only — 1305 rows, zero plain `Near Mint`.
Because the file is the complete English catalogue, "no plain Showcase is printed" is a statement
about the game rather than about a set. Every other Riftbound rarity stocks both finishes and is
authored with both.

**The residual risk is named rather than waved away**: a complete catalogue is complete as of the
day it was pulled, and a future set could print a plain Showcase. The `matrix superset` row blocks
the moment an export proves one, and the fix is to widen that line — which is the audit doing its
job, not a reason to widen pre-emptively and spend the only narrowing the data supports.

### 2.3 — Riftbound and One Piece share a condition vocabulary; Pokémon is the odd one out

Both games' `Condition` columns are the five grades crossed with `{"", " Foil"}`, plus `Unopened`.
**Two finishes, not three. There is no reverse holo in either game.**

    riftbound   normal -> "Near Mint"   foil -> "Near Mint Foil"
    one_piece   normal -> "Near Mint"   foil -> "Near Mint Foil"
    pokemon     normal -> "Near Mint"   holo -> "Near Mint Holofoil"
                reverse_holo -> "Near Mint Reverse Holofoil"

This is the assumption whose refutation cost the most in the app. `app/src/types.ts` typed the
finish as a literal union of Pokémon's three strings, which was correct while Pokémon was the only
game and became a defect the moment it was not: a screen typed against it silently kept drawing
Pokémon's chips whatever game was chosen, offering `holo` and `reverse_holo` for Riftbound —
strings that game does not print and the server refuses. **Reported from the rig, not from a
test.**

It was widened to `string` deliberately rather than to a union of every game's finishes. A union
of all of them would type a Riftbound `reverse_holo` as legal, which is the same defect wearing a
wider hat; the server validates the claim against the chosen game's own list and answers
`variant_invalid`, and the app's job is to offer the right chips rather than to prove them in the
type system.

### 2.4 — One Piece carries no denominator at all

    OP15-079   EB04-042   ST26-005   PRB02-014   P-105

A set code, a hyphen, a three-digit index, printed on the card exactly as the export writes it.
**There is no `printedTotal` anywhere in this game**, so `CLAUDE.md`'s composed join key — zero-fill
the number, append a slash and the printed total — is not merely a poor fit. It is unmatchable, and
`printed_total` is a field with no referent for One Piece.

That is what forced `join_key` to become a per-game strategy rather than a constant. The registry
names `printed_code` for One Piece: the identification returns one string and it is matched against
the export's `Number` cell verbatim.

The 547 blank-`Number` rows are not an exception. 530 are `DON!!` cards and 17 are sealed, and
`pipeline/join.py` already falls to the name path whenever the identification carries no number —
the same blank-`Number` fallback T3 asserts for Pokémon code cards. `printed_code` describes how
the other 3,075 rows are keyed; it does not have to describe the blank ones.

**Riftbound needed the same strategy for a different reason**, and that is worth keeping because it
is the case that proves `printed_code` is not a One Piece special case. Most of Riftbound is
Pokémon-shaped: 9,540 of 10,078 rows carry a denominator (`179/298`, `066a/298`, `303*/298`,
`SP3/006`). But 450 do not — `R04`, `R04a`, `R04b`, `R04c`, `T03`, `T02 // T03` — and a per-game
field holding one strategy has nowhere to put a fallback. Matching the printed identifier verbatim
covers both shapes at once, because the catalog already keys on the export's `Number` cell
verbatim. It preserves the suffix for free, which matters: `066a/298` is a different card from
`066/298`, and any normalisation that folds the letter silently merges two SKUs.

### 2.5 — Two smaller findings that will otherwise be rediscovered

**`DON!!` carries punctuation and it is part of the cell.** Nothing folds, strips or normalises it;
the string is joined on and rendered verbatim. The audit's fold check exists precisely to catch a
session that tidies it to `DON`.

**Sealed product is accounted for differently in each game, and both are correct.** Pokémon's 132
booster boxes, blisters and Elite Trainer Boxes carry a **blank** `Rarity` cell, and a blank is not
a vocabulary item — the audit skips a row with no rarity, so there is nothing to account for, and
writing `""` into the rarity tuple would invent a rarity nobody prints. Riftbound's and One Piece's
sealed rows carry the literal string `None`, which *is* a cell and therefore does need accounting;
both entries list it as not claimed.

---

## 3. `game` is a per-card claim, not a mode — D21

### 3.1 — The picker is on the capture bar, beside Box, Set hint and Finish

Not on the app shell. `game` joins the claim family and behaves exactly like the others: client
state, resent with every capture, written to the record and to the sidecar.

**Mixed boxes are therefore legal, and that is not a concession — it is what makes the claim a
claim.** A shell-level mode would make the game a property of the *session*, and the first time a
Riftbound card turned up in a Pokémon box the operator would have to either lie or stop.

### 3.2 — Required, defaulting to `pokemon`, and D3's null does not transfer

Worth stating because the two look identical and are not. The finish claim's `null` is meaningful
because there is **a ladder underneath it** that infers a finish from evidence — catalog rows,
detection, a human. **There is no ladder that infers a game.** A missing game is not "no claim"; it
is "no export", and every consumer below would have nothing to join against.

So the field is required of the claim — the picker always has an answer and always sends it — and
`DEFAULT_GAME` is a **read-side backfill** for records written before the field existed, applied
where such a record is read and never where one is written. `store/master.py:Card.game` is
`Optional` for exactly that reason, and the registry's `get` takes no default at all: a caller that
wants the backfill asks for `DEFAULT_GAME` by name, at the point of the read, where the substitution
is visible. A default inside the accessor would make every unknown key silently become Pokémon, and
the first symptom would be a Riftbound card priced off a Pokémon export.

The server draws the same line in its refusals, and the two codes are deliberately different:

    game_invalid      the string is not a game at all — a typo, or a client written against
                      an older registry
    game_unverified   the game is registered and nobody has seen a TCGplayer export for it

Absent is not refused. Absent is a sidecar written before the field existed.

### 3.3 — Ten hops, and the tuple that now binds three of them

`docs/DEBTS.md` recorded, while this work was being planned, that a capture-time claim crosses ten
independent restatements between the control and the consumer, and that **two of them fail
silently**: `Inventory.parse` filters on the card dataclass's annotations, so an undeclared field is
dropped on reload; and `record_capture`'s upsert copied a literal three-name tuple, so a fourth
claim would survive a first capture and be discarded by every re-record.

The recommended fix landed with this step. `store/master.py:CAPTURE_CLAIM_FIELDS` is one tuple read
by the places that restated it, and T7 asserts the settable set is every capture claim in the order
the store names them. `game` and the misc `note` both ride it.

**The debt is narrowed, not closed, and the remaining gap is named here rather than discovered
later as an over-claim.** The three app-side hops stay hand-carried whatever the store does: no
Python constant can reach a `.tsx`, and `make typecheck` sees a field *added* to `app/src/types.ts`
and never one omitted from it.

---

## 4. The registry — D22

### 4.1 — Pure literals, read with `ast`, and the two rules that follow

`pipeline/games.py` holds one entry per game and imports nothing from this repo, so
`scripts/docs-audit.py` reads it with `ast.literal_eval` **without running project code** — the same
rule `docs/map.py` follows and the audit enforces on itself. Two consequences a later session will
otherwise undo by accident:

- **No name from the module may appear inside a registry literal.** `"normal"` is written out in
  both the finish tuple and the condition map rather than referenced, because `literal_eval` cannot
  resolve a name.
- **No function object may sit in an entry.** `join_key` and `prompt` are **strategy names** —
  strings drawn from closed vocabularies in the same file — and the dispatch from a name to a
  callable belongs in the consumer, where a reader can see it.

The vocabularies live beside the entries rather than in the consumers so that the audit can
reconcile every entry against them: a typo in one entry's `join_key` is then *provable*, rather than
discovered at runtime by a join that quietly matched nothing.

**Hand-authored, never generated.** Every field is ARGUMENT in D18's sense — a later session could
reasonably disagree with the stack order of the rarities, or with which finishes a rarity may claim.
D18's seam list stays empty and this file is not a request to open it.

### 4.2 — `catalogued` and `unverified` are orthogonal, and must never share a flag

Three states, and the two that look alike have **opposite remedies**:

- `catalogued: True, unverified: False` — measured. An export was read and the vocabulary authored
  from its cells. All four real games.
- `catalogued: True, unverified: True` — a real TCGplayer product line whose export nobody has
  seen. **Temporary, with a known fix: get the export.** Every consumer refuses, because a guessed
  rarity list is exactly what D22 refuses and an empty one that refuses loudly is strictly better
  than a plausible one that prices wrong. **No entry is in this state today, and the state stays**
  because the next game added starts there.
- `catalogued: False` — `misc`. **Permanent, and correct.** There is no single `Product Line` to
  read, no export coming, and the honest answer is that we know we do not know.

If the two shared a flag, every misc capture would read as a fault — and a real fault would then
hide among the ~1% of the shelf that is working exactly as designed. That is the whole argument for
the extra field.

The refusals mirror it: one exception for a game with no catalog and never will have (a **caller
bug** — branch on the predicate before the join) and one for a game waiting on an export (a **gap
with a fix**). Catching them as one thing would let a genuinely unmeasured game hide behind the
working 1%.

### 4.3 — Stack order, and where it is an admission rather than a measurement

`rarities` is in **stack order, not export order**, because the capture screen renders it and the
operator is holding a sorted pile. Each entry argues its order from something other than taste:

**Pokémon** interleaves Common/Uncommon/Rare and the in-set hits by their own sets' numbering — Holo
Rare sits directly on Rare, Double Rare and Radiant Rare are the SV- and SWSH-era in-set hits at the
same rung in different eras, ACE SPEC sits at the top of the numbered set below the secrets, and
Illustration/Ultra/Special Illustration/Hyper follow SV09's own numbering. **`Secret Rare` and
`Rainbow Rare` are appended rather than interleaved, and that is the one place the order is an
admission**: they are SM/SWSH-era secrets, no set in any committed export carries both an SV Hyper
Rare and an SM Secret Rare, so there is no numbering that orders the two eras against each other.

**Riftbound** uses the game's own ascending ladder, and the export's row counts fall monotonically
along it (2850 > 2625 > 1310 > 765), which is what a rarity ladder looks like from the outside.
Showcase and Promo are appended because neither is a rung — one is a treatment cutting across the
ladder, the other a distribution channel — and ordering them against the four rungs would invent a
rank the game does not have.

**One Piece is less measured than the other two, and says so plainly.** C/UC/R/SR/SEC is the game's
published ladder, and unlike Riftbound the row counts **do not corroborate it**: `R` (780)
outnumbers `UC` (465), because the file is three sets and one of them is a chase-heavy Premium
Booster. A partial export cannot rank rarities by frequency, so the ladder is taken from the game
and the counts are recorded as what they are — not evidence. `TR` above `SEC` is the thinnest claim
in the entry. `L` and `DON!!` are card *types* and `PR` is a channel, so all three are appended.

---

## 5. THE SUPERSET RULE — the argument a later session will most want to undo

### 5.1 — Why unselectable is only safe over a superset

D23 makes the capture screen render a finish chip excluded by a rarity claim as **unselectable
rather than hidden**, so the operator can see what the claim cost them and take it back by clearing
the rarity. That is safe **only** while `finish_by_rarity` is a superset of reality.

A matrix narrowed to one export's observations makes a legitimate stack **unclaimable**, with the
chip greyed out and no way for the operator to say what is true — a screen that has decided the card
in your hand does not exist. **The superset rule and unselectable must never be separated.**

### 5.2 — The vindication: 60 plain-NM Rares

`finish_by_rarity["Rare"]` carried `normal` against an SV09 that stocks no plain Near Mint `Rare`
row. It was authored beyond the evidence on purpose and cited in D22, D23 and `docs/map.py` as *the*
example of a deliberate superset — and the standing temptation was to trim it to what the one
available export proved.

**The wider Pokémon export stocks 60 of them**: Cosmic Eclipse 38, Crown Zenith 22. Narrowing that
line would have made **two whole eras of plain `Rare` unclaimable** on a screen where the excluded
chip is unselectable.

The general principle the entry now states: **widen to every finish the rarity's own printing admits,
narrow only where the printing forbids it.** A main-set rarity sits in the reverse-holo slot and can
be pulled plain, so it claims all three. A hit above the set is foil by definition and is not printed
in the reverse slot, so it claims `holo` alone — widening those to `normal` would be widening past
what the cardboard allows, which buys no safety and empties the feature of any narrowing at all.

Two further pairs were caught by the audit the day the wider export landed: Pokémon `Common` and
`Uncommon` with `holo`, because SV: Prismatic Evolutions stocks 79 and 46 Near Mint Holofoil rows for
them — the Poké Ball and Master Ball pattern cards. Real stacks the matrix would have rendered
unclaimable.

### 5.3 — The live unproved case has moved, and it asks rather than blocks

The canonical unproved pair is no longer `Rare`/`normal`. It is **One Piece's `SR` and `TR`**,
authored with `normal` against an export of three sets out of many. In that file `SR` (109 products)
and `TR` (1 product) are stocked in Foil grades only.

Riftbound's `Showcase` was narrowed on exactly that observation — and the asymmetry is deliberate,
because that file is the whole English catalogue and this one is three sets marked partial by the
owner. **"No plain SR in three sets" is a fact about three sets.**

So those two are the live example of the superset: authored beyond the evidence, reported by the
`game coverage` row as a **question**, blocking nothing. If a fuller One Piece export ever shows `SR`
foil-only across the catalogue, narrowing it becomes the same argument Showcase already won.

---

## 6. The four audit rows

Named rather than numbered, per D16. Each is deterministic and each reads the committed exports.

**`game vocabulary`** — blocking. Every rarity cell in every export is accounted for by some entry's
`rarities` or `rarities_not_claimed`, and every authored rarity's raw form appears in an export. A
rarity whose *folded* form matches an export string but whose raw form does not is a typo and can
never false-positive, so it blocks.

**`game coverage`** — advisory. It asks about the reverse direction: a finish a matrix allows that no
export in view stocks. **Absence from one set proves nothing** — `Promo` and every pre-SV rarity are
legitimately missing from an SV09 fixture — so this row prints and allows. It currently asks two
questions, both about One Piece's `SR` and `TR`, and section 5.3 is why that is the rule working.

**`matrix superset`** — blocking in one direction only. It blocks on an **observed** rarity/finish
pair the matrix is missing, and only *asks* about the excess. That asymmetry is the whole shape of
the rule: widening is legal and narrowing is loud.

**`join key shape`** — blocking. It checks the composed-key games against the export's actual
`Number` cells, which is the row that would have caught D25's real defect had it existed earlier.

`PKMNSCAN_EXPORTS` widens the advisory row and nothing else: colon-separated paths to extra exports
the repo cannot carry, so their coverage questions get asked. **A path that does not resolve is
skipped in silence, and nothing read through it can fail a commit** — a gate that a file on one
person's disk can break is a gate that gets switched off, and a gate that *needs* such a file has
already switched itself off for everybody else.

---

## 7. Per-game dispatch

The registry says *what*, by name; four consumers say *how*. Each dispatch is a mapping from a
strategy name to an implementation, checked at import against the registry's vocabulary so that a
name added in one place stops the process next to the mismatch rather than at whichever call happens
to reach for it first.

**Join key.** `number_and_printed_total` is the composed key; `printed_code` matches the printed
identifier verbatim; `name_only` is the blank-`Number` path the join already walked; `not_joined` is
a game that never reaches a catalog. `not_joined` is a **named value rather than an empty string**,
so a consumer dispatching on it refuses rather than falling through.

**Prompt.** `pokemon_card_v1` is the fingerprint T1 scores against. `misc_card_v1` is its sibling: a
schema built from what a Magic, Yu-Gi-Oh, Weiss Schwarz or foreign-language card actually carries,
rather than Pokémon's shape with the Pokémon-shaped fields left blank. `unwritten` is **not a
placeholder to be tidied away** — it is the honest value for a game whose prompt has never been
written, and asking for it is a refusal, because the alternative is falling through to Pokémon's,
which fits every call and reads every card wrong.

**The check runs one way only, and the asymmetry is deliberate.** A profile with no registry claimant
is a strategy authored ahead of its game, and blocking on that would mean the registry and the
dispatch could only ever change together, in one commit, by one person. A registry name with **no**
profile is the direction that breaks a run — and it caught one within the hour it was written, twice:
once when a name arrived in the registry under a different spelling in the dispatch, and once when
`misc_card_v1` landed in the registry before its profile existed. Both stopped at import with both
names in the message.

**A strategy name was deleted rather than left standing unclaimed, and that is a judgement worth
showing.** `operator_note` named a game deliberately never sent to the model, and `misc` was its only
claimant. The owner's correction on 2026-08-23 — *"i also want misc identified and submitted to batch
api -- i never said i didnt"* — left a strategy no game could claim, an exception nothing could raise
and a predicate that could never answer False: **the exact dead-field shape this registry is audited
to prevent, authored into the vocabulary itself.** The free-text note stays and is *additional*; it
was never offered as a substitute for reading the card.

**Crop bands.** A band profile is a *selection*, not a rectangle. There is deliberately no per-game
rectangle: a card is 63x88mm whatever is printed on it, and the only per-game question is which bands
are worth cutting. `pokemon` claims the title and the number; every other entry claims **none**,
because nothing has measured where a Riftbound, One Piece, Yu-Gi-Oh or Weiss Schwarz card puts its
title or its identifier, and a band claimed without that measurement is cut over the wrong pixels. An
export cannot answer this, so no export will ever fill it in.

**Card shape.** `card_aspect` is the ratio `geometry/detect.py` gates on, passed in by
`cli/cmd_identify.py` rather than read from a module constant. `misc` carries `None`, and **`None`
refuses**: a detector with no aspect to check accepts any rectangle, and the contract is that `None`
means a human should look — never that it guessed. The cost is one lost crop retry on ~1% of stock
that is being handled by hand anyway; the cost of the alternative is a confident crop of the stand,
the desk, or the next card along.

The rounding in Pokémon's `0.716` is deliberate and harmless: 63/88 is 0.715909…, so threading the
authored value moves the gate by about 1.3e-4 relative against a tolerance of 0.15. Writing the
fraction out would put arithmetic in a file that must stay `literal_eval`-safe.

---

## 8. `misc` — the third state, and why it is not a gap

The occasional Yu-Gi-Oh, Weiss Schwarz, foreign-language or Magic card. About 1% of stock. Captured,
**located** and **identified** like any other card, carrying a free-text operator note typed at
capture so it is findable by search later, and then it stops at the catalog.

**`product_line` is `None`, not `""`, and the type is the point.** There is no single cell — the entry
spans four populations at once — and inventing a string would be exactly the guess D22 refuses.
`None` is not a `str`, so the catalog's comparison can never be true for it under any export, where
`""` is both a value a malformed row could carry and the value an unverified entry uses. Using `""`
would collapse the two states on the one field that most needs to tell them apart.

**It is `located: True`, and that is the field separating it from `pokemon_code`.** Both are outside
the join; only one is outside the box.

**It sits outside D12 on two axes at once**, said here so no later reader has to notice the
contradiction themselves: a foreign-language printing breaks "English", and Magic, Yu-Gi-Oh and Weiss
Schwarz are different product lines entirely, not a different era of this one. **D12 is not being
reopened** — this entry is the explicit carve-out, and it earns it by never reaching the pricing or
listing path where D12's Near Mint hardcode lives.

**Identification and catalog membership are different questions**, and one flag had quietly been
answering both. The predicate a caller branches on before the join answers whether there is a
TCGplayer export to match a row against, and that is the only question it has ever been able to
answer. It says nothing about identification, and it used to be read as though it did.

---

## 9. The five jobs this file scoped, and the argument behind each

**All five are built.** The heading read "NOT BUILT" until 2026-08-30, by which point every
item under it had shipped and the STATUS section above was carrying a paragraph-long
correction to say so. The sections are kept for their arguments — the superset rule, the
rung-0 prohibition, the union-not-intersection rule for finish chips — none of which the
code states.

### 9.1 — The rarity claim, end to end (D23) — the job that pays

A multi-select rarity claim on the capture screen, scoped by the chosen game. It does three things,
in order of what they are worth.

**1. Cross-check — the `rarity_claim_mismatch` review reason.** Emitted in the **variant ladder**,
not in routing: routing answers *"is this trusted enough to list?"* and the ladder answers *"which
row is this?"*. It filters candidate rows to the claimed rarities and reviews when nothing survives —
filter-then-contradict, because on a multi-set collision the filter breaks a `duplicate_condition`
tie for free.

**This is the job that pays.** T1's recorded misses are `051/197` for `031/197` and `271/167` for
`211/167` — *confident* answers, name right, digits wrong. **No confidence threshold fires on those.
A rarity contradiction does.**

**Rung 0 must not consult it.** A human who looked at the photograph beside the candidate rows
outranks a claim about the stack it came from, and the failure that taught this is on the record:
sixteen answered cards re-deriving their disagreement and re-parking on every join.

**2. Narrow the finish chips.** Offered is the **union** of the matrix over the claimed rarities —
union, not intersection, because a Common+Rare stack legitimately holds both plain-NM Commons and
holo Rares. Three rules, each stopping a specific harm: an empty rarity claim **narrows nothing**
(the compatibility guarantee that makes the feature strictly additive); it **never auto-selects**,
not even when one finish is left, because ladder rung 2 already resolves a holo-only Double Rare for
free and a manufactured claim would make rung 2 unreachable for every card this rig sees; and
**excluded chips are rendered unselectable, not hidden** — which is only safe over a superset
(section 5).

**3. Prompt injection**, section 9.4.

### 9.2 — The multi-export join (D25)

`--export` becomes repeatable. **Never infer the game from a filename**: read each file's `Product
Line` column, map file → games, then invert to game → files, which must be exactly one.

**This corrects a claim `docs/DECISIONS.md` used to make.** The Deferred list said the catalog join
was "product-line-agnostic". Measured, it was product-line **blind** — the column was declared in the
canonical header and read by nothing, so two exports concatenated would have cross-joined in silence.
Blind is not agnostic.

**Catalogs are built per game and never merged.** A merged number index would report cross-*game*
collisions through the collision report as though they were the cross-*set* collisions that report is
actually about — different faults with different remedies, since a set hint fixes one and nothing
fixes the other.

**One import file per game.** Nobody has established whether Import to Staged accepts a file spanning
two product lines, and the accepted fixture proves it for one line only. Per-game files are correct
under either answer, so the question does not need settling first.

**Refusals exit 1, write nothing, touch no queue, and never prompt.** Two cases: two files claiming
one game, and a game present in the run with no export — the second names positions and points at the
correction route. The check runs **before any catalog is built**, so a run that will refuse costs
nothing.

### 9.3 — Pooled, non-located inventory (D24), and two opsec discharges

A code card has **no box, section or card position**. It is a count. An index is acceptable as a key
— it is what the photo and sidecar are named after on disk — but it is not meaningful, because the
physical cards are disposed of once the code is extracted.

**The seam is the one registry flag.** `located: False` means the position label is **never rendered**
— not in the review queue, not in a run report, not in the pull preview — and non-located cards never
enter the Fulfillment view or the pull flow, because there is nothing to walk to. D24 asks for that
last part to be **asserted in `app/tests/fulfillment.spec.ts` rather than left to prose**, and today
it WAS neither until 2026-08-23, when the flag gained its consumers and the assertion landed —
42 Fulfillment tests including "a pooled card is never on his screen". The
assertion is part of the work, not a thing to add afterwards.

**Quantity is the unit, and the pipeline already computes it.** D7 aggregates by SKU with the copy
count. Surface it; do not build a second inventory.

**Disposal is a terminal state shared with D26's `removed`.** A code card whose code has been
extracted leaves inventory permanently — record kept, gap permanent, exactly `sold`'s shape. **Build
them as one state, not two**, and read `docs/specs/order-flow.md` section 10.1 first, because that
name is already taken by a history event.

**Two opsec triggers fire with this work and must be discharged in the same commit.** The `PreToolUse`
opsec guard has been disabled since 2026-08-03, and D16 says in writing *"Revisit before the codes
track handles real cards."* This work makes that condition true. The recorded failure was
**over-triggering** — it blocked placeholders in prose about the code format — so the fix is a
narrower pattern, never a toggle. And `scripts/views.txt` may never name a URL whose render can
contain a code card.

### 9.4 — The rarity clause into the prompt, in its own step

In the user turn, because it is per-card, and scoped so it cannot poison D3 rung 3. The system prompt
already says *"Do not infer the finish from the card's rarity"*, and a careless clause makes it do
exactly that — poisoning the one signal that catches a mis-sorted card.

Gated behind `PKMNSCAN_T1_RARITY` for an A/B, the same shape as the set-hint knob, and **shipped in
its own step so the fingerprint moves once, deliberately, with a re-measured T1.** That sequencing is
the whole of why it is separate from 9.1: a prompt change and an accuracy measurement in the same
commit cannot say which one moved the number.

### 9.5 — Per-game finalization

Riftbound and One Piece have exports and vocabularies and **no prompt**. Their `prompt` field says
`unwritten` and asking for it refuses. Nothing has photographed a card of either game, so nothing has
measured where either puts its title or its identifier, which is why both claim no crop bands. Those
are the same gap seen from two sides and they close together or not at all.

---

## 10. What is asserted, and what is merely consistent

The honest boundary, in the terms `docs/GATES.md` uses for T6's synthetic composites.

**Proved by the exports**: the shared 16-column header; the three `Product Line` cells; every rarity
string; the two condition vocabularies; the absence of a denominator in One Piece; the 60 plain-NM
Rares; the 261 foil-only Showcase products; the counts quoted throughout.

**Authored beyond the exports, deliberately, and audited in the direction that can be proved**: every
`finish_by_rarity` row wider than what an export stocks. Section 5.

**Taken from the games rather than measured**: One Piece's rarity ladder, and the relative rank of
`TR`.

**Not evidence at all**: every claim about how a Riftbound or One Piece card *photographs*. No card of
either game has been through this rig. The card shapes are properties of cardboard; the crop bands are
deliberately empty for exactly this reason; and identification accuracy for either game is unmeasured
and unmeasurable until a prompt exists.

---

## 11. What a later session must not undo

- **Do not narrow `finish_by_rarity` to one export's observations.** Unselectable becomes a trap, and
  section 5.2 is what it cost the one time it was nearly done.
- **Do not shorten a `product_line` cell.** A wrong string joins to no row at all, silently, and the
  Riftbound one is not guessable.
- **Do not normalise `DON!!`, and do not fold a rarity suffix** — `066a/298` is a different card from
  `066/298`.
- **Do not give `misc` a `product_line` string.** `None` is not a `str`, and that is the property
  doing the work.
- **Do not collapse `catalogued` and `unverified`.** Opposite remedies; section 4.2.
- **Do not merge per-game catalogs**, and do not infer a game from a filename. Section 9.2.
- **Do not put a name from the module inside a registry literal, or a callable in an entry.** The
  audit reads the file with `ast` and must never run it.
- **Do not let the rarity claim reach ladder rung 0**, and do not ship the prompt clause in the same
  step as the claim.
- **Do not restore `operator_note` or any strategy no game claims.** Section 7.
