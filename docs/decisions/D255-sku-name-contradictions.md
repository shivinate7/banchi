## D255 — One SKU, two stored names: the sibling check D242 cannot see

**AMENDED, MERGED (`D-identity-follows-the-sku`, ruling 6).** This class read "the card's own
stored name." That is no longer the read, once a card is bound. `cards identity`, one report,
reads `read_*` against the SKU table instead, and excludes any card a human bound. D242 merges
into the same report. The owner's own word: *"Merge them."*

**What this builds.** `pipeline/sku_name_contradictions.py` and `pkmnscan cards sku-names`
find every card whose own stored `name` disagrees with the product name of its SKU. The
comparison runs against the newest cached export per game
(`inventory/.exports/<game>/*.csv`). Read-only. No network, ever. There is no `--resolve`
flag, unlike D242's own sibling check.

**The mirror image of D242.** D242 finds one SKU carrying two disagreeing stored NUMBERS.
This finds one SKU carrying a stored NAME that disagrees with the SKU's own product NAME.
The number agrees here — one SKU, one number claim — and the name does not. D242's own
class needs the numbers to disagree. It never sees this class. A card can sit under exactly
the right number and the wrong product, with nothing about its number to raise it.

**Reuses `pipeline.join.name_disputes`, never a second similarity rule.** That function is
D146's own name-agreement test. This module never restates its tolerance
(`NAME_DISPUTE_SIMILARITY`), which a sibling session was fitting concurrently. The check
asks one question per card. Does the model's own stored name disagree with the `Product
Name` cell of the export row this card's SKU currently points at? `name_disputes` tests
this by containment, then by ratio. Never by exact equality.

**Measured read-only on the owner's store.** 62 identified cards and 6 sold cards disagree.
Examples: `4/176` "Daisy!" under the "Lilting Lullaby" SKU. `1/75` "Tideturner" under
"Kog'Maw, Caustic". `1/499` "Diana, Mount Targon" under "Diana, Lunari", which may be a
legitimate variant. D240's own worked example names this exact pair, from the join-time
direction. **This check reports. It never decides.**

**Three honest verdicts, `cards audit`'s own shape (D172), with one amendment.** Pass, fail,
`not known` — never a silent pass over zero rows. `not known` names one of three reasons.
No cached export exists for the card's game. The SKU is absent from that export. Or the
card's own stored name is blank.

UNLIKE `cards audit`, one card's `not known` never suppresses another card's real
`dispute`. `audit`'s subject is one whole-store binary fact, and folding every doubt into
one verdict is right for that check. This check's subject is independent per card. The
overall verdict answers a narrower question: was anything checked, and did any checked
card disagree? It does not ask whether the whole store's answer is trustworthy. A card
with no SKU at all is a fourth, prior case, counted separately. There is no product claim
yet to disagree with.

**The likely-right SKU is ranked, never picked.** For a disputed card, every export row
whose `Product Name` folds exactly (`name_index_key`) to the card's own stored name is a
candidate. Where more than one exists, `rank_candidates` breaks the tie. It uses only the
capture-time claims the card already carries: `set_hint` (`pipeline.setnames.resolve`),
`rarity_claim`, and `metadata_finish` (`pipeline.variant`'s own condition map). Never a new
name comparison. A claim the card does not carry contributes nothing, never a penalty.

**A small, local catalog, deliberately not `pipeline.join.Catalog`.** That class narrows to
the game's Near Mint (plus sealed) conditions, for the listing path's own reason (D137). A
diagnostic report about which SKU a card is filed under must not lose a real, currently
listed SKU over a different condition. This module's own `Catalog` indexes every row,
whatever the condition, by SKU and by folded name.

**What proves it.** `scripts/sku-name-contradictions-selftest.py`, 26 assertions, literal
`tcgcsv.Row` fixtures. No store and no network. It proves agreement (no finding), a dispute
with the real alternative proposed, and a sold card's own section. It proves the three
`not_known` reasons, the one-bad-card-never-hides-another-finding amendment, the
Near-Mint-blind lookup, and the `set_hint` tie-break. A mutation arm proves the reuse
matters. An exact-equality resolver, this module's tempting first shape, wrongly flags a
legitimate short-title variant. `Repair Specialist` beside `Zaun, Repair Specialist` is the
real, `name_disputes`-backed check's own correct pass.

**What this does not do.** Write a card. Apply a repair. Queue anything, the same gap D242
names and leaves open, for the same reason. `store/queues.py:Queue.upsert` refuses to
re-queue an already-answered position (D167). Touch `pipeline/join.py`, which a sibling
session was editing concurrently. Fetch a fresh export, or open any socket at all.

Governs `pipeline/sku_name_contradictions.py`, `cli/cmd_sku_name_contradictions.py`, and
`cli/cmd_cards.py`'s `sku-names` dispatch entry. Cites D146, for name agreement as a
release signal — `name_disputes` is reused verbatim. Cites D239, the four approved
stored-data checks this is a sibling of. Cites D240, which measured the same defect class
from the join-time side, and named the tolerance this module reuses rather than
re-derives. Cites D242, the sibling this module is modelled on: read-only, three verdicts,
and a ranked-never-picked report.
