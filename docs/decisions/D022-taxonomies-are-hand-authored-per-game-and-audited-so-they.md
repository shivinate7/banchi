## D22 — Taxonomies are hand-authored per game, and audited so they cannot drift

`pipeline/games.py` holds one entry per game: the exact `Product Line` cell, the ordered `Rarity` cells, the finish enum, the finish→`Condition` map, and the rarity→finish matrix. Pure literals, importing nothing from this repo, so `scripts/docs-audit.py` can read it with `ast` **without running project code** — the same rule `docs/map.py` follows and the audit enforces on itself.

**Hand-authored, never generated.** Every field is ARGUMENT in D18's sense: a later session could reasonably disagree with the stack order of the rarities, or with which finishes a rarity is allowed to claim. D18's seam list stays empty and this entry is not a request to open it.

**Audited in the direction that can be proved.** The audit reads the committed exports and blocks on what is provably wrong — a rarity whose folded form matches an export string but whose raw form does not is a typo and can never false-positive; an export rarity accounted for by nothing is a gap. It only *asks* about the reverse, because absence from one set proves nothing: `Promo` and every pre-SV rarity are legitimately missing from an SV09 fixture.

**Rarity strings render verbatim, the way reason codes do.** A second friendly vocabulary is a thing nothing audits, and the drift D16 exists to catch.

**That state existed for two games and is now occupied by nobody** (measured 2026-08-23). The entry used to say it was "not yet established that TCGplayer carries Riftbound or One Piece as `Product Line` values at all", and that it was the highest-risk assumption in the design — because if it were false, D8 and D11 would have no data and the architecture would change shape. The owner exported all three. **TCGplayer carries both, on the identical 16-column header**, so the join is structurally valid for every product line. The exact cells, which nobody would have guessed:

    Pokemon
    Riftbound League of Legends Trading Card Game
    One Piece Card Game

**Every consumer still refuses on an empty vocabulary rather than falling back to Pokémon's.** A guessed rarity list is exactly what this repo refuses; an empty one that refuses loudly is strictly better than a plausible one that prices wrong. The state stays for the next game added — it is not deleted just because it is currently unoccupied.

**The superset rule collected its first evidence and won, and this is the paragraph to read before ever narrowing the matrix.** `finish_by_rarity["Rare"]` carried `normal` against an SV09 that stocks no plain Near Mint `Rare` — it was the authored-beyond-the-data example this entry and D23 both cited, and the standing temptation was to trim it to what one export proved. The wider Pokémon export stocks **60 plain-NM Rares** (Cosmic Eclipse 38, Crown Zenith 22). Narrowing it would have made two whole eras unclaimable, on a screen where the excluded chip is unselectable and the operator has no way to say what is true.

The canonical unproved case is therefore no longer `Rare`/`normal`. It is One Piece's `SR` and `TR`, authored with `normal` against an export of three sets out of many — and the audit asks about them as questions rather than blocking, which is the whole shape of the rule.

**A third state, `catalogued`, sits orthogonal to `unverified`** (added 2026-08-23 with the `misc` entry). The two describe opposite situations and must never share a flag:

- `catalogued: True, unverified: True` — a real product line nobody has an export for yet. **Temporary, with a remedy**: get the export. Refusing is right, because a guess becomes a price.
- `catalogued: False` — `misc`: the occasional Yu-Gi-Oh, Weiss Schwarz, foreign-language or Magic card, about 1% of stock. **Permanent, and correct.** No export is coming. It must NOT refuse, because refusing on every misc capture would make a legitimate part of the shelf read as a fault, and a real fault would then hide among them.

`misc` carries `product_line: None` rather than `""` — `None` is not a `str`, so the catalog's comparison can never be true, whereas `""` is both a value a row could carry and the value an unverified entry uses. It is captured and located like any card, takes **no identification call** (it is being handled by hand anyway), and carries a free-text operator note instead so it is findable by search. It sits outside D12 on two axes at once — foreign language breaks "English", and the other three are different product lines entirely.
