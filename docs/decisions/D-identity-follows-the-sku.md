## D-identity-follows-the-sku — Identity follows the SKU

**The argument.** A card carries two kinds of fact. What the camera read. What the card IS.
Before this entry, both lived in the same five fields — `name`, `number`, `printed_total`,
`rarity`, `set_name`. A SKU binding never overwrote them. So a card's drawn identity stayed
the model's own guess forever. That held even after a human, a join or a correction settled
which real listing the card is. Measured: 64 SKU-bound cards draw a name their own listing
disputes. 241 draw a number. 147 of those came from one route alone, `do_review_answer`. The
fix is not a smarter guess. It is a rule. Once a card is bound to a SKU, its identity is the
SKU's, not the camera's. `docs/specs/identity-follows-sku.md` is the full spec, with every
measurement. This entry is its record.

**The layers.** A real card sits under four layers, each narrower than the one above it.

1. **Product** — a name, in a set, at a number. `Mind Rune` in `Vendetta`.
2. **Printing** — one visual treatment of that product. Foil, holo, reverse holo, or plain.
3. **Grade** — the condition a physical copy is in. Five grades this store has ever seen:
   Near Mint, Lightly Played, Moderately Played, Heavily Played, Damaged. (Plus `Unopened`,
   sealed product's own one condition, outside this ladder.)
4. **SKU** — one TCGplayer id. It names exactly one product, one printing, one grade. It is
   the floor of the stack. Everything else derives from it, never guessed above it.

A card's identity is the SKU's identity. It is read straight off that floor, the moment a SKU
binds.

**The one writer.** `Inventory.bind_sku`/`unbind_sku` (lane 1) choose or undo a binding.
`Inventory.restore_identity` (lane 3a review) puts one back exactly, for D28's undo.
`Inventory.hold_sku` (this lane) is the fourth. The SKU is known. The card's own read disputes
it. The identity stays the read, not the row nothing trusts yet. All four live in
`store/master.py`, and nowhere else.

**Seven writers are sanctioned, not four.** Two more keep writing directly, and each one was
already argued in the code before this lane touched it. `record_identification` is continuous
with `bind_sku`, in its own words — "the same writer... the moment a binding exists." `set_state`
is a flagged, temporary deviation. It waits on a later lane to trim its five identity
parameters. `move_card` is the seventh. It is D83's tombstone clear, unrelated to choosing an
identity, and unchanged by this lane. `make docs-audit`'s new `identity writers` row reads all
seven off `store/master.py`'s own `IDENTITY_WRITERS` constant, never a copy of it. It fails a
commit that assigns `sku`, `condition`, `name`, `number`, `printed_total`, `rarity` or
`set_name` anywhere else under `server/`, `store/`, `pipeline/`, `cli/`, `codes/` or
`scripts/`. Its `IDENTITY_WRITERS_ALLOWED` exception list is empty and pinned at zero. Lane 7
pinned two entries there, both `cli/cmd_cards.py`'s `_variants`. That press is now retired,
as the spec's own plan said. It refuses, names `cards identity`, and writes nothing.

**`read_*` is evidence, and only evidence.** `read_name`, `read_number`, `read_printed_total`
hold what the camera saw. They are written unconditionally, on every identification. They are
never searched. They are never shown as the card's identity once a binding exists. Only the
next identification of the SAME photograph ever rewrites them. A SKU-bound card's screen
identity comes from the SKU table. An unbound or held card's screen identity equals its
`read_*` — there is nothing else to show.

**`bound_at` never means "currently bound."** It is a timestamp of the last write to that one
field. Nothing more. `identity_source` is the only field that says whether a card is bound
right now. `unbind_sku(sku=None)` and `hold_sku` both restamp `bound_at`. Both also set
`identity_source = IDENTITY_READ`. That is the exact shape an undo, or a hold, produces. The
card is NOT bound, and `bound_at` still holds a fresh, non-null time. `store/master.py`'s own
`Card` dataclass carries this rule beside the field. Read `bound_at` only beside
`identity_source`. Never read it alone.

**Amendments.** D213 widens from `set_name`/`rarity` to the whole identity group. D239's
caller now builds off `read_*`. D242 and D255 merge into one report, `cards identity`. Each
original class becomes empty by construction. A bound card's stored number or name can no
longer disagree with its own SKU. Neither one is stored independently of it any more.
D252 amends its route to one `bind_sku` call, instead of seven hand-written fields. D253 keeps
its agreement rule. It retires `set_state`'s `name` parameter and `JoinReport.name_corrections`.
D254 amends tier (b) to read the SKU table. Each of the seven carries its own note, added by
this lane, citing this entry.

**The rollout runbook.** Four steps. Each needs the owner's own word before the next one runs.

1. **Merge** this lane's PR, and every lane before it, to main.
2. **`./pkmnscan skus adopt --write`, at once.** Until this runs, every Review answer refuses
   with `sku_unknown`. `bind_sku` reads the SKU table before it writes anything. An empty
   table means that every SKU is unknown to it.
3. **The replay, for the owner to read.** `scripts/identity-replay.py`, on a copy of the real
   store. Nothing here writes. The owner reads its own table before step 4 touches real cards.
4. **`./pkmnscan cards identity --write`.** The one-time migration. It binds every card that
   derives, and holds the rest. It opens a review entry for a held card still `identified`
   (D167/D4's own protection against re-asking an already-cleared position).

No step here runs on its own. Each one waits for the owner to say go.

Governs `store/master.py` (`IDENTITY_FIELDS`, `IDENTITY_WRITERS`, `Inventory.hold_sku`),
`scripts/docs-audit.py` (the `identity writers` row), `scripts/demo-seed.py`,
`cli/cmd_cards.py`, `cli/archive_review.py`, `scripts/demo-determinism.py`,
`.github/workflows/demo.yml`, and `scripts/checks.py`. Cites D213, D239, D242, D252, D253,
D254 and D255 — each amended, as above. Cites D172 (the first photograph is the name), D173
(a rule that can be enforced is enforced), D18 (a generator may write, and nothing that writes
may gate a commit), and D140 (a number is claimed at merge, never guessed on a branch).
