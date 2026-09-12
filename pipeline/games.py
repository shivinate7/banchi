"""The per-game taxonomy registry (D22). One entry per capture choice, hand-authored.

Five games, because the capture screen offers five claims (D21): `pokemon`, `riftbound`,
`one_piece`, `pokemon_code`, `misc`. An entry holds the exact `Product Line` cell, the
ordered `Rarity` cells, the finish enum, the finish -> `Condition` map, the rarity ->
finish matrix, and the handful of per-game facts the rest of the pipeline would otherwise
have hardcoded for Pokemon: which join key applies, which prompt reads the card, which crop
bands `geometry/crop.py` cuts, what shape `geometry/detect.py` looks for, and whether the
card is located at all (D24).

PURE LITERALS, IMPORTING NOTHING FROM THIS REPO. `scripts/docs-audit.py` reads the
registry with `ast.literal_eval` rather than importing it, exactly as it reads
`docs/map.py`, because an audit must not run project code. Two consequences that a later
session will otherwise undo by accident:

  - No name from this module may appear *inside* a registry literal. `"normal"` is written
    out in `finishes` and in `condition_by_finish` rather than referenced, because
    `literal_eval` cannot resolve a name.
  - No function object may sit in an entry. `join_key` and `prompt` are STRATEGY NAMES —
    strings drawn from the vocabularies below — and the dispatch from a name to a callable
    belongs in the consumer, where a reader can see it.

HAND-AUTHORED, NEVER GENERATED. Every field is ARGUMENT in D18's sense: a later session
could reasonably disagree with the stack order of the rarities, or with which finishes a
rarity may claim. D18's seam list stays empty and this file is not a request to open it.
What the audit does instead is check the authoring against the committed exports in the
one direction that is provable — see `scripts/docs-audit.py`'s `game vocabulary`,
`game coverage`, `matrix superset` and `join key shape` rows.

RARITY STRINGS ARE THE EXPORT'S OWN CELLS, VERBATIM, the way reason codes are. A second
friendly vocabulary is a thing nothing audits, which is the drift D16 exists to catch.

THREE STATES, NOT TWO, AND THEY MUST NEVER COLLAPSE INTO EACH OTHER. An entry is in
exactly one of them, and `catalogued` plus `unverified` name which:

  - `catalogued: True, unverified: False` — MEASURED. An export was read and the
    vocabulary authored from its cells. `pokemon`, `pokemon_code`, `riftbound`,
    `one_piece`.
  - `catalogued: True, unverified: True` — NOT YET MEASURED. A real TCGplayer product line
    whose export nobody has seen. Temporary, with a known fix: get the export. Every
    consumer refuses, because a guessed rarity list is exactly what D22 refuses and an
    empty one that refuses loudly is strictly better than a plausible one that prices
    wrong. No entry is in this state today, and the state stays because the next game
    added will start there.
  - `catalogued: False` — NO CATALOG, PERMANENTLY. `misc`. Not a gap and not pending:
    there is no single `Product Line` to read, no export coming, and the correct answer is
    that we know we do not know. This is why it cannot share `unverified`'s flag — if it
    did, every misc capture would read as a fault, and every real unmeasured game would
    hide among ~1% of the shelf.

The distinction is worth the extra field because the two states have opposite remedies. An
`unverified` game is fixed by measuring. `misc` is already correct.

`pipeline/variant.py` derives its finish enum and condition map from the `pokemon` entry.
That derivation is the proof the entry is right: it produces byte-identical values, so T3
and T4 pass untouched.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple


class UnknownGame(KeyError):
    """A game key outside the registry.

    Never coerced to a default and never silently mapped to `pokemon`. Same house rule as
    `pipeline/variant.py`'s `UnknownFinish` — "guess once and it prices wrong" — and it
    lands harder here, because guessing the game guesses the whole export.
    """


class EmptyVocabulary(ValueError):
    """A registry entry that has no rarities to work from and is waiting for an export.

    Raised by `require`, which is the accessor every consumer should reach for. `get`
    returns the entry as authored, so that a screen can render an unmeasured game as a
    known but unavailable choice; `require` is the one that says "this game cannot be
    processed", which is the only honest answer while `unverified` is True.

    A GAP WITH A FIX. The remedy is an export. Contrast `NotCatalogued`, where there is no
    remedy because nothing is missing.
    """


class NotCatalogued(ValueError):
    """A game that has no catalog to join against, permanently — `catalogued: False`.

    NOT AN EMPTY VOCABULARY, AND THE TWO MUST NEVER BE CAUGHT AS ONE THING. `misc` spans
    Magic, Yu-Gi-Oh, Weiss Schwarz and foreign-language printings at once, so there is no
    single `Product Line` cell to filter an export by, no rarity ladder that means the same
    thing across all four, and no export that would settle it. That is the finished answer,
    not a measurement somebody owes.

    Reaching this exception is a CALLER BUG, not a data gap, and that is the whole
    difference. A misc card is captured, located and IDENTIFIED like any other card and then
    stops at the catalog — so nothing on its real path asks this module for a vocabulary.
    Branch on `is_catalogued` before the join rather than catching this after it; the
    exception exists so that a caller which skipped that branch stops here, beside the
    reason, instead of quietly joining a Yu-Gi-Oh card against a Pokemon export.

    IT IS THE JOIN'S PREDICATE AND NOT IDENTIFICATION'S, corrected 2026-08-23. This
    docstring used to say "gets no identification call" in the same breath as "never enters
    the join", which read as one fact and is two — and the first half was never the owner's
    ruling. `cli/resolve.py` is the caller that branches: it holds an uncatalogued card out
    of the join and records it, having already sent it to the model like everything else.
    """


# --------------------------------------------------------------------- vocabularies
#
# The three closed sets an entry's strategy fields draw from. They live here rather than in
# the consumers because `scripts/docs-audit.py` reconciles every entry against them with
# `ast` and no import — a typo in one entry's `join_key` is then provable rather than
# discovered at runtime by a join that quietly matched nothing.

# How a card's identification finds its catalog row.
#
# `number_and_printed_total` is CLAUDE.md's join key, `zfill(3)(number) + "/" +
# printedTotal`: the identification returns the two halves separately and the key is
# composed here. `printed_code` is the opposite shape — the identification returns ONE
# string, the identifier exactly as printed on the card, and it is matched against the
# export's `Number` cell verbatim. `name_only` is the blank-`Number` path
# `pipeline/join.py` already walks. `not_joined` is a game that never reaches a catalog at
# all, and it is a named value rather than an empty string so that a consumer dispatching
# on it refuses rather than falling through.
JOIN_KEY_STRATEGIES = (
    "number_and_printed_total",
    "printed_code",
    "name_only",
    "not_joined",
)

# Which prompt reads the card. `pokemon_card_v1` is `identify/prompt.py`'s `SYSTEM_PROMPT`
# and the fingerprint T1 scores against. `misc_card_v1` is its sibling for the `misc` entry:
# a schema built from what a Magic, Yu-Gi-Oh, Weiss Schwarz or foreign-language card
# actually carries, rather than Pokemon's shape with the Pokemon-shaped fields left blank.
# `unwritten` is not a placeholder to be tidied away later — it is the honest value for a
# game whose prompt has never been written, and it is named so that a consumer dispatching
# on it refuses instead of falling through to Pokemon's. AS OF 2026-08-23 NO ENTRY NAMES
# IT, because `riftbound` and `one_piece` — its only two claimants — got real profiles that
# day. It stays regardless: the next game registered here starts in exactly this state, and
# the refusal is the only thing standing between that game and another game's contract.
# That is NOT the case that deleted `operator_note` below; see the paragraph after this one
# for the difference, which is that `operator_note` named a state the product does not have
# while this one names a state it will certainly be in again.
#
# THERE WAS A THIRD VALUE HERE, `operator_note`, AND ITS REMOVAL IS THE OWNER'S CORRECTION
# RATHER THAN A TIDY-UP (2026-08-23). It named a game deliberately never sent to the model,
# reasoning that a misc card is handled by hand anyway. The owner's ruling is the opposite:
# *"i also want misc identified and submitted to batch api -- i never said i didnt"*. The
# free-text operator note stays and is ADDITIONAL — it was never offered as a substitute for
# reading the card. Once `misc` names a real prompt, no entry named `operator_note` at all,
# which left a strategy no game could claim, an exception nothing could raise and a
# predicate that could never answer False: the exact dead-field shape this registry is
# audited to prevent, authored into the vocabulary itself.
#
# WHAT MISC STILL NEVER DOES IS JOIN, and that is untouched. `catalogued: False` and
# `join_key: "not_joined"` mean what they always meant: there is no Magic or Yu-Gi-Oh export
# here, so there is no row to match and no price to read. IDENTIFICATION AND CATALOG
# MEMBERSHIP ARE DIFFERENT QUESTIONS, and the value removed above is the evidence that one
# flag had quietly been answering both.
PROMPT_STRATEGIES = (
    "pokemon_card_v1",
    "misc_card_v1",
    # C8's transcription contract: the printed redemption code EXACTLY as printed, plus
    # the set line the owner sorts code boxes by. NOT the fork's identification
    # architecture — C2's QR/OCR path answers "which product is this", and this profile
    # answers "what code is printed here", which is the image-to-text step the dispute
    # flow re-checks by eye when a buyer says a code did not work (C6 rules the remedy).
    "pokemon_code_v1",
    # WRITTEN 2026-08-23, AND THEY ARE WHY `unwritten` NOW NAMES NOBODY. Both games print
    # ONE collector identifier rather than Pokemon's two halves — which is the same fact
    # their `join_key: "printed_code"` records one field down — so each has its own schema
    # asking for that string whole, its own two-finish enum read from its own entry below,
    # and its own parser. NEITHER HAS EVER READ A CARD: no Riftbound or One Piece card has
    # been photographed by this project, so these two names buy a WIRED path and not a
    # measured one. See identify/prompt.py's printed-code section.
    "riftbound_card_v1",
    "one_piece_card_v1",
    "unwritten",
)

# The crop-retry regions `geometry/crop.py` cuts, by its own names (`REGION_TITLE`,
# `REGION_NUMBER`). An entry may name a subset; it may not invent one, because a band this
# list does not contain is a band nothing knows how to cut.
CROP_BAND_NAMES = ("title", "number")

# ------------------------------------------- how wide this game's export is fetched (D76)
#
# WHICH AXIS THE FETCH IS ALLOWED TO NARROW ON, PER GAME. D65 scoped
# `POST /admin/pricing/downloadexportcsv` by the set hints the box's own cards carry, on the
# reasoning that widening is always safe and narrowing is not. The reasoning is right; the
# rule built from it was too eager. It collected the hints that EXISTED and never counted the
# cards that carried none — so one hinted card in a 200-card box scoped the export to that
# one set, and the other 199 queued as `no_catalog_row` behind a fetch that reported success
# and a positive check that passed, because the set asked for did arrive.
#
# The narrowing is worth having where a category is too large to take whole, and it is worth
# NOTHING where the whole catalogue already fits in one file. That is a per-game fact, it is
# measured, and the measurements are the committed exports named under GAMES below:
#
#   riftbound   10078 rows, 1.6 MB — the ENTIRE English catalogue, in one file
#   one_piece    3622 rows, 580 KB — three sets, and nothing about the category refused
#   pokemon      NOT measured whole — 220 sets in the live category picker, and the widest
#                file this repo holds (7802 rows, 1.1 MB) is four sets of it
#
# `category` IS A CLAIM THAT THE WHOLE CATEGORY IS FETCHABLE and may only be authored against
# a measurement like the first two. `sets` is the default and the safe one: it narrows only
# where every card in the run carries a hint AND every hint resolved, and widens to the whole
# category otherwise. A game with no `tcgplayer_category_id` has no export to scope and names
# neither.
#
# THE OPERATOR OVERRIDES THIS PER FETCH, which is the half that makes it a default rather
# than a policy — `server/pipeline_routes.py:_scope_for_run` takes `scope` and `set_ids` from
# the request, and `#/runs` draws both beside the fetch button.
EXPORT_SCOPES = ("category", "sets")
DEFAULT_EXPORT_SCOPE = "sets"

# The read-side backfill for records written before `game` existed, and NOTHING ELSE.
# D21 is explicit that the field is required and that D3's null-means-no-claim does not
# transfer: `FinishClaim`'s null is meaningful because a ladder infers a finish underneath
# it, and there is no ladder that infers a game. A missing game is not "no claim", it is
# "no export". So this constant is legal where an old record is read and illegal where a
# new one is written.
DEFAULT_GAME = "pokemon"


# --------------------------------------------------------------------- the registry
#
# GROUND TRUTH IS THE COMMITTED EXPORTS, MEASURED RATHER THAN REMEMBERED. Four files, one
# 16-column header shared byte for byte by all of them — which is the finding that makes
# D11's catalog join structurally valid for all three product lines rather than a Pokemon
# thing three games have to be bent into:
#
#   fixtures/sv09_export_untouched.csv           341 rows, Pokemon, SV09 alone
#   fixtures/pokemon_wide_export_untouched.csv  7802 rows, Pokemon, 4 sets across 3 eras
#   fixtures/riftbound_export_untouched.csv    10078 rows, the whole English Riftbound catalogue
#   fixtures/onepiece_export_untouched.csv      3622 rows, One Piece, 3 sets (PARTIAL)
#
# WHICH EXPORT IS COMPLETE DECIDES HOW FAR A MATRIX MAY BE NARROWED, and that asymmetry is
# used deliberately below. The Riftbound file is the entire English catalogue per the
# owner, so "no plain row exists for this rarity" is a statement about the game. The One
# Piece file is three sets out of many, so the same observation is a statement about three
# sets and nothing more.
#
# `rarities` IS IN STACK ORDER, NOT EXPORT ORDER, because the capture screen renders it and
# the operator is holding a sorted pile.
#
# ------------------------------ THE MATRIX IS A SUPERSET, AND THAT IS LOAD-BEARING -------
#
# D23 gives the reason and it is the whole argument for `finish_by_rarity`: the capture
# screen renders a finish chip excluded by a rarity claim as UNSELECTABLE rather than
# hidden, so the operator can see what the claim cost. That is safe ONLY while this matrix
# is a superset of reality. A matrix narrowed to one export's observations makes a
# legitimate stack UNCLAIMABLE, with the chip greyed out and no way for the operator to say
# what is true — a screen that has decided the card in your hand does not exist.
#
# THE RULE JUST COLLECTED ITS FIRST PIECE OF EVIDENCE, AND IT VINDICATED THE WIDENING.
# `finish_by_rarity["Rare"]` carried `normal` against SV09, which stocks no plain Near Mint
# `Rare` row — authored beyond the evidence on purpose, and cited in D22, D23 and
# `docs/map.py` as THE example of a deliberate superset. The wider Pokemon export now
# stocks 60 of them (SM Cosmic Eclipse 38, SWSH Crown Zenith 22). Narrowing that entry to
# SV09's observations would have made two whole eras of plain `Rare` unclaimable. The live
# example of an unproved pair has moved to `one_piece`, where `SR` and `TR` appear
# foil-only in a partial export and are authored with `normal` anyway.
#
# IF ANYONE EVER NARROWS THIS TO ONE EXPORT'S OBSERVATIONS, UNSELECTABLE BECOMES A TRAP.
# The `matrix superset` audit row blocks on an observed pair this matrix is missing and only
# *asks* about the excess, which is the asymmetry that keeps the widening legal and the
# narrowing loud.

GAMES = (
    {
        "key": "pokemon",
        "display": "Pokémon",
        "product_line": "Pokemon",
        # TCGplayer's own category id for that product line, read off the Pricing tab's
        # category picker on 2026-08-30. It is what `POST /admin/pricing/downloadexportcsv`
        # scopes on (D65), and it is NOT derivable from `product_line` — the two are
        # independent identifiers for the same thing and only the portal knows the pairing.
        "tcgplayer_category_id": 3,
        # THE CODES THE OPERATOR TYPES, MAPPED TO THE NAMES TCGPLAYER USES (D65). These are
        # two different vocabularies and no string rule bridges them: `MEG` is the community
        # short code for the set TCGplayer calls `ME01: Mega Evolution`, and `TEF` is theirs
        # for `SV05: Temporal Forces`. Measured 2026-08-30 against the live category list —
        # TCGplayer-style codes (`ME01`, `SV05`, `SV09`) already resolve by shape and need no
        # entry here; the three-letter ones resolve to nothing without it and the fetch
        # silently widens to all 220 Pokemon sets.
        #
        # HAND-AUTHORED AND DELIBERATELY PARTIAL, which is D22's rule for a per-game
        # vocabulary. There is no machine-readable source for community set codes, so this
        # covers what the owner actually types and grows as they type more. An absent alias
        # costs a wider export, never a wrong one.
        #
        # The VALUE is matched against TCGplayer's set name by the same three rules a typed
        # hint takes, so `MEG -> ME01` works without repeating the full name here.
        "set_aliases": {
            "MEG": "ME01",
            "TEF": "SV05",
            "JTG": "SV09",
        },
        # No `product_line_rarities`: `pokemon` is the unrestricted claimant of the
        # `Pokemon` line. Narrowing it to the thirteen below would drop the `Code Card`
        # rows out of the Pokemon catalog, and those rows are the blank-`Number` case
        # `pipeline/join.py`'s name fallback already resolves and T3 already asserts.
        #
        # STACK ORDER, ARGUED FROM SET NUMBERING RATHER THAN FROM TASTE. Common, Uncommon,
        # Rare and the in-set hits interleave through the main body of a set, so their
        # order is the conventional ladder; everything above them is ordered by its own
        # set's numbering, which is the only non-opinion available:
        #
        #   Holo Rare      in-set, the SM/SWSH-era holo of a main-set rare (CE 16-204,
        #                  CZ 16-143), so it sits directly on top of `Rare`
        #   Double Rare    in-set, the SV-era hit (SV07 1-128, SV09 11-121)
        #   Radiant Rare   in-set, the SWSH-era hit (CZ 20-105) — same rung as Double Rare,
        #                  a different era, and no set carries both
        #   ACE SPEC Rare  top of the numbered set, below the secrets (SV07 134-142 of 142,
        #                  Prismatic 116-131 of 131)
        #   Illustration Rare 160-170, Ultra Rare 171-181, Special Illustration Rare
        #                  182-187, Hyper Rare 188-190 — SV09's own numbering
        #
        # `Secret Rare` and `Rainbow Rare` are appended rather than interleaved, and that is
        # the one place this order is an admission instead of a measurement: they are
        # SM/SWSH-era secrets (CE 237-271 and 249-262 against a printedTotal of 236), no set
        # in any committed export carries both an SV `Hyper Rare` and an SM `Secret Rare`,
        # so there is no numbering that orders the two eras against each other. Within their
        # own era they are in their own set's order.
        "rarities": (
            "Common",
            "Uncommon",
            "Rare",
            "Holo Rare",
            "Double Rare",
            "Radiant Rare",
            "ACE SPEC Rare",
            "Illustration Rare",
            "Ultra Rare",
            "Special Illustration Rare",
            "Hyper Rare",
            "Secret Rare",
            "Rainbow Rare",
        ),
        # A real cell of this Product Line that is never a stack claim here. `Code Card`
        # is a Pokemon RARITY and not a separate Product Line — all of its rows sit
        # inside the Pokemon export — so `Product Line` alone cannot partition the
        # registry, and the pair (product_line, Rarity) is the key. The game that claims
        # it is `pokemon_code` below.
        #
        # SEALED PRODUCT IS NOT LISTED HERE AND DOES NOT NEED TO BE. The 132 booster boxes,
        # blisters and Elite Trainer Boxes in the wider export carry a BLANK `Rarity` cell,
        # and a blank is not a vocabulary item — the audit skips a row with no rarity, so
        # there is nothing to account for. Writing `""` into this tuple would invent a
        # rarity nobody prints. Riftbound and One Piece are the contrast: their sealed rows
        # carry the literal string `None`, which is a cell and therefore does need
        # accounting.
        "rarities_not_claimed": ("Code Card",),
        "finishes": ("normal", "holo", "reverse_holo"),
        "condition_by_finish": {
            "normal": "Near Mint",
            "holo": "Near Mint Holofoil",
            "reverse_holo": "Near Mint Reverse Holofoil",
        },
        # THE PRINCIPLE: widen to every finish the rarity's own printing admits, narrow only
        # where the printing forbids it. A main-set rarity sits in the reverse-holo slot and
        # can be pulled plain, so it claims all three. A hit above the set is foil by
        # definition and is not printed in the reverse slot, so it claims `holo` alone —
        # widening those to `normal` would be widening past what the cardboard allows, which
        # buys no safety and empties the feature of any narrowing at all.
        #
        # `Common` and `Uncommon` carry `holo` because SV: Prismatic Evolutions stocks 79
        # and 46 Near Mint Holofoil rows for them — the Poke Ball and Master Ball pattern
        # cards. Those were the two pairs `matrix superset` blocked on the day the wider
        # export landed, and they are exactly the case that row exists for: a real stack the
        # matrix would have rendered unclaimable.
        "finish_by_rarity": {
            "Common": ("normal", "holo", "reverse_holo"),
            "Uncommon": ("normal", "holo", "reverse_holo"),
            "Rare": ("normal", "holo", "reverse_holo"),
            # Holo by name; the reverse-holo printing is stocked as well (41 rows — SM
            # Cosmic Eclipse 22, SWSH Crown Zenith 19). Zero plain Near Mint rows in any
            # committed export, and there cannot be one: a card called a holo rare that is
            # not foil is not this rarity.
            "Holo Rare": ("holo", "reverse_holo"),
            "Double Rare": ("holo",),
            "Radiant Rare": ("holo",),
            "ACE SPEC Rare": ("holo",),
            "Illustration Rare": ("holo",),
            "Ultra Rare": ("holo",),
            "Special Illustration Rare": ("holo",),
            "Hyper Rare": ("holo",),
            "Secret Rare": ("holo",),
            "Rainbow Rare": ("holo",),
        },
        # D76. `sets` because a whole-category fetch is not what this game wants: 220 sets
        # in the live picker, and the widest Pokemon file this repo holds is four of them.
        # So the fetch narrows — but only where every card in the run carries a hint and
        # every hint resolved, which is the condition D65's first build did not check.
        #
        # THE WHOLE CATEGORY IS MEASURED NOW, and this comment said it was not until
        # 2026-09-12 — see `export_category_bytes` below, which is what changed.
        "export_scope": "sets",
        # THE WHOLE CATEGORY, WEIGHED. One forced fetch, 2026-09-12: 32,629,598 B over
        # 222,849 rows — 97.24% of `server/tcg_export.py:MAX_BYTES`, 903 KB of headroom —
        # against 238,482 B for the one set the owner's 543 Pokemon cards all name. A
        # widening is 137x here and it lands two per cent short of the ceiling the fetch is
        # refused past.
        #
        # THIS IS THE EVIDENCE FOR THE FIELD BELOW AND IT IS AUDITED TO TRAVEL WITH IT.
        # `export_needs_hint` is a judgement about a number, so the number is written down
        # beside it rather than left in a commit message; `scripts/docs-audit.py`'s
        # `games registry` row refuses the boolean on an entry that names no measurement.
        "export_category_bytes": 32629598,
        # D76 SAID A WIDENING IS ALWAYS SAFE. For this category it is 903 KB from a refusal,
        # so "safe" has a measured boundary now and this is where that boundary is written
        # down: a run of this game whose own cards widened the scope is REFUSED rather than
        # quietly spent, because one unhinted card is all it takes — the unanimity rule
        # widens the moment the box stops agreeing.
        #
        # NOT A RULE ABOUT THE SHUTTER, and that is the whole of the design. D65 and
        # `app/src/setHint.ts` both say the rig does not stop for an autocomplete, and a
        # capture that refused mid-feeder at a 623 ms cadence would be a card on the floor —
        # a physical card in the drawer with no record, which renumbers every card behind it.
        # The refusal is at the fetch, where the width is actually spent; the capture screen
        # NOTES it and never blocks.
        #
        # `pokemon_code` SHARES THIS CATEGORY AND DELIBERATELY DOES NOT CARRY THIS FIELD.
        # See its own entry: it joins by name, so a set filter buys it nothing, and a hint
        # it cannot supply is not a hint it can be refused for.
        "export_needs_hint": True,
        "located": True,
        "join_key": "number_and_printed_total",
        "prompt": "pokemon_card_v1",
        "crop_bands": ("title", "number"),
        # 63x88mm. `geometry/detect.py:CARD_ASPECT` computes the ratio the detector gates
        # on; this field is the per-game statement of the same physical fact, and it exists
        # because a game with a differently sized card would need one.
        #
        # READ AS OF 2026-08-23 by `cli/cmd_identify.py`, which hands it to
        # `geometry.detect_card`. Until then it was authored, audited and consumed by
        # nothing, while the detector gated on its own module constant — a field kept honest
        # by the audit and by no behaviour. THE ROUNDING IS DELIBERATE AND HARMLESS: 63/88 is
        # 0.715909…, so threading this value moves the gate by 1.3e-4 relative against a
        # tolerance of 0.15. Writing the fraction out here instead would put arithmetic in a
        # file that must stay `ast.literal_eval`-safe.
        "card_aspect": 0.716,
        "catalogued": True,
        "unverified": False,
    },
    {
        "key": "pokemon_code",
        "display": "Pokémon code cards",
        # Same Product Line as `pokemon`, narrowed by rarity. This is what
        # `product_line_rarities` is for, and it is why the registry cannot be partitioned
        # on `Product Line` alone.
        "product_line": "Pokemon",
        # TCGplayer's own category id for that product line, read off the Pricing tab's
        # category picker on 2026-08-30. It is what `POST /admin/pricing/downloadexportcsv`
        # scopes on (D65), and it is NOT derivable from `product_line` — the two are
        # independent identifiers for the same thing and only the portal knows the pairing.
        "tcgplayer_category_id": 3,
        "product_line_rarities": ("Code Card",),
        "rarities": ("Code Card",),
        "rarities_not_claimed": (),
        "finishes": ("normal",),
        "condition_by_finish": {"normal": "Near Mint"},
        "finish_by_rarity": {"Code Card": ("normal",)},
        # D24, the owner's ruling: a code card has no box, section or card position. It is
        # a count. An index is still allocated because the photo and sidecar are named
        # after it, but `Position.label` is never rendered for one and it never enters the
        # pull flow or the Fulfillment view — there is nothing to walk to. This flag is the
        # concrete form of D14's "two tracks, one rig".
        # D76. `sets`, and it is the same Pokemon category as above. Code cards rarely carry
        # a set hint, so in practice this widens — which is correct and is what it already
        # did; what changed is that a single hinted card can no longer narrow it.
        "export_scope": "sets",
        # AND IT CARRIES NO `export_needs_hint`, DELIBERATELY, THOUGH IT IS CATEGORY 3 AND SO
        # SITS ON THE SAME 97.24% CLIFF THE ENTRY ABOVE MEASURES.
        #
        # A hint is refusable only where a hint would have narrowed the fetch. This game's
        # `join_key` is `name_only` — the blank-`Number` rows — so a set filter buys the
        # MATCH nothing, and the set is not something a code card reliably prints for the
        # operator to read off. Demanding one here would be friction with no narrowing at
        # the end of it, which is exactly the argument `riftbound` wins its `category` on.
        #
        # SO THE CLIFF STAYS REACHABLE ON THIS TRACK, AND THAT IS A NAMED GAP RATHER THAN AN
        # OVERSIGHT. What covers it is what covered it before: the width is drawn on
        # `GET /pipeline/runs/<name>/scope` before the press, and `_too_large_sentence` says
        # the scope is why if the download is ever refused. Closing it needs a narrower
        # transport — a paged or streamed fetch — not a claim the operator cannot make.
        "located": False,
        # Code cards are the blank-`Number` rows. The name fallback is not a degraded path
        # here, it is the only key there is.
        "join_key": "name_only",
        # C8's ledger starts here: this profile transcribes the printed redemption code
        # exactly as printed, and the extracted code lands on the card record so the
        # dispute lookup is the existing search — type the code, get the card, tap the
        # photo. The fork's QR/OCR path (C2) still owns product identification; this
        # prompt owns the image-to-text step that path does not cover.
        "prompt": "pokemon_code_v1",
        # `geometry/crop.py`'s bands are cut for a collector number and a title. A code
        # card has neither in those places, so it claims none rather than claiming a band
        # that would be cut over the wrong pixels.
        "crop_bands": (),
        "card_aspect": 0.716,
        "catalogued": True,
        "unverified": False,
    },
    {
        "key": "riftbound",
        "display": "Riftbound",
        # THE CELL, VERBATIM, AND IT IS NOT "Riftbound". Measured off all 10078 rows of
        # fixtures/riftbound_export_untouched.csv, every one of which carries this string.
        # A shortened form here would filter an export to zero rows, which under D25 is the
        # one case where the join refuses instead of continuing.
        "product_line": "Riftbound League of Legends Trading Card Game",
        # See `pokemon` for what this is. Riftbound is 89.
        "tcgplayer_category_id": 89,
        # See `pokemon` for what this is. Riftbound's community codes; `UNL` already
        # resolves by prefix and needs no entry.
        "set_aliases": {
            "OGN": "Origins",
        },
        # Seven cells; six are claimed. Counts across the whole English catalogue:
        # Common 2850, Uncommon 2625, Rare 1310, Showcase 1305, Promo 1090, Epic 765,
        # None 133.
        #
        # STACK ORDER. Common, Uncommon, Rare, Epic is the game's own ascending ladder, and
        # the export's own row counts fall monotonically along it (2850 > 2625 > 1310 >
        # 765), which is what a rarity ladder looks like from the outside. `Showcase` and
        # `Promo` are appended because neither is a rung: Showcase is a TREATMENT that cuts
        # across the ladder (its 261 products run from number 007 to 310 and include plain
        # `###/###`, `###a/###`, `###*/###` and `R##a` shapes alike), and Promo is a
        # DISTRIBUTION CHANNEL. Ordering them against the four rungs would be inventing a
        # rank the game does not have; ordering them after it says they are orthogonal.
        #
        # THE OWNER'S GUESS BEFORE THE EXPORT WAS READ IS RECORDED BECAUSE ONE PART OF IT
        # WAS SIMPLY NOT THERE: "common/uncommon/rare/epic/alt art/showcase/rune". `rune`
        # appears in no `Rarity` cell in the catalogue, and `alt art` is not a rarity either
        # — it is what `Showcase` IS, e.g. `Ahri, Alluring (Alternate Art)` at `066a/298`.
        # This is the entry that most justifies D22's refusal to author a vocabulary from
        # memory.
        "rarities": (
            "Common",
            "Uncommon",
            "Rare",
            "Epic",
            "Showcase",
            "Promo",
        ),
        # `None` is TCGplayer's literal string for a product that has no rarity, and it is
        # accounted for rather than claimed. 85 products: 73 sealed (Booster Display,
        # Booster Pack, Event Kit, Vault Bundle) and 12 double-sided token cards numbered
        # `T02 // T03`. Neither is a stack anyone sorts — sealed product is never captured,
        # and a token has no rarity to claim. Leaving it unclaimed costs nothing, because
        # D23 makes an empty rarity claim narrow nothing.
        "rarities_not_claimed": ("None",),
        # TWO FINISHES, NOT THREE. There is no reverse holo in this game. The whole
        # catalogue's `Condition` column is the five D12 grades crossed with {"", " Foil"},
        # plus `Unopened`.
        "finishes": ("normal", "foil"),
        "condition_by_finish": {
            "normal": "Near Mint",
            "foil": "Near Mint Foil",
        },
        # `Showcase` IS THE ONE NARROWING IN THIS FILE, AND IT IS NARROWED ON A COMPLETE
        # CATALOGUE. All 261 Showcase products are stocked in Foil grades only — 1305 rows,
        # zero plain `Near Mint`. That is not one export's sample: the file is the entire
        # English catalogue, so "no plain Showcase is printed" is a statement about the
        # game rather than about a set. Every other rarity here stocks both finishes and is
        # authored with both.
        #
        # THE RESIDUAL RISK IS NAMED RATHER THAN WAVED AWAY: a complete catalogue is
        # complete as of the day it was pulled, and a future set could print a plain
        # Showcase. `matrix superset` blocks the moment an export proves one, and the fix
        # is to widen this line — which is the audit doing the job it exists for, not a
        # reason to widen pre-emptively and spend the only narrowing the data supports.
        "finish_by_rarity": {
            "Common": ("normal", "foil"),
            "Uncommon": ("normal", "foil"),
            "Rare": ("normal", "foil"),
            "Epic": ("normal", "foil"),
            "Showcase": ("foil",),
            "Promo": ("normal", "foil"),
        },
        # D76, AND THE ONE ENTRY THAT EARNS `category`. The file named at the top of this
        # module — fixtures/riftbound_export_untouched.csv, 10078 rows, 1.6 MB — is the
        # ENTIRE English catalogue in one download, per the owner. So there is nothing for a
        # set filter to buy here and a real hazard in spending one: a box sorted by rarity
        # rather than by set carries hints on some cards and none on the rest, and narrowing
        # on the few would drop the many. Always fetch the whole category.
        "export_scope": "category",
        "located": True,
        # `printed_code`, NOT `number_and_printed_total`, AND THE 450 PROMO AND TOKEN ROWS
        # ARE WHY. Most of this catalogue is Pokemon-shaped — 9540 of 10078 rows carry a
        # denominator (`179/298`, `066a/298`, `303*/298`, `SP3/006`) — but 450 do not:
        # `R04`, `R04a`, `R04b`, `R04c`, `T03`, `T02 // T03`. A composed
        # `number + "/" + printedTotal` key can never match those, and a per-game field
        # holding one strategy has nowhere to put a fallback.
        #
        # Matching the printed identifier verbatim covers both shapes at once, because
        # `Catalog._by_number` already keys on the export's `Number` cell verbatim. It also
        # preserves the suffix for free, which matters: `066a/298` is a different card from
        # `066/298`, and any normalisation that folds the letter silently merges two SKUs.
        "join_key": "printed_code",
        # WRITTEN 2026-08-23; this line said `unwritten` until then and asking for it
        # refused by name. `identify/prompt.py:RIFTBOUND_CARD_V1` asks for the identifier
        # WHOLE — one field, letter suffix and asterisk and the spaces around `//` all
        # kept — which is the same fact `join_key` above records, seen from the model's
        # side. The prompt is WIRED and UNMEASURED: no Riftbound card has ever been
        # photographed, so there is no accuracy figure for it and the crop bands below
        # stay empty for exactly the same missing photograph.
        "prompt": "riftbound_card_v1",
        # `geometry/crop.py`'s bands are fractions measured on a Pokemon card. Nothing has
        # measured where a Riftbound card puts its title or its number, and a band claimed
        # without that measurement is cut over the wrong pixels — the same refusal
        # `pokemon_code` makes, for the same reason. An export cannot answer this, so no
        # export will ever fill it in.
        "crop_bands": (),
        # The one fact about this game that was never in doubt: a standard 63x88mm card,
        # which is a property of the cardboard rather than of anything TCGplayer publishes.
        "card_aspect": 0.716,
        "catalogued": True,
        "unverified": False,
    },
    {
        "key": "one_piece",
        "display": "One Piece",
        # Verbatim off all 3622 rows of fixtures/onepiece_export_untouched.csv.
        "product_line": "One Piece Card Game",
        # See `pokemon` for what this is. One Piece is 68.
        "tcgplayer_category_id": 68,
        # Ten cells; nine are claimed. Counts across the three sets in the file: C 920,
        # R 780, SR 545, DON!! 530, UC 465, PR 160, SEC 120, L 80, None 17, TR 5.
        #
        # STACK ORDER, AND IT IS LESS MEASURED THAN THE OTHER TWO, WHICH IS SAID PLAINLY.
        # C/UC/R/SR/SEC is the game's published ladder, and unlike Riftbound the row counts
        # DO NOT corroborate it: `R` (780) outnumbers `UC` (465) here, because the file is
        # three sets and one of them is a chase-heavy Premium Booster. A partial export
        # cannot rank rarities by frequency, so this ladder is taken from the game and the
        # counts are recorded as what they are — not evidence. `TR` (Treasure Rare) is
        # placed above `SEC` as the scarcest tier on one product in this file, which is the
        # thinnest claim in this entry. `L` (Leader) and `DON!!` are CARD TYPES rather than
        # rungs, and `PR` is a distribution channel, so all three are appended after the
        # ladder for the same reason Riftbound's Showcase and Promo are.
        #
        # `DON!!` CARRIES PUNCTUATION AND IT IS PART OF THE CELL. Nothing here folds, strips
        # or normalises it — the string is joined on and rendered verbatim, and the audit's
        # fold check exists precisely to catch a session that "tidies" it to `DON`.
        "rarities": (
            "C",
            "UC",
            "R",
            "SR",
            "SEC",
            "TR",
            "L",
            "PR",
            "DON!!",
        ),
        # 17 rows, all `Unopened`: Dash Packs, Booster Boxes, Double Pack Sets. Same
        # treatment as Riftbound's `None` and for the same reason.
        "rarities_not_claimed": ("None",),
        # The same two finishes as Riftbound, from the same measured `Condition` vocabulary:
        # five grades x {"", " Foil"} plus `Unopened`. No reverse holo.
        "finishes": ("normal", "foil"),
        "condition_by_finish": {
            "normal": "Near Mint",
            "foil": "Near Mint Foil",
        },
        # EVERY RARITY CLAIMS BOTH FINISHES, INCLUDING THE TWO THE EXPORT SHOWS AS
        # FOIL-ONLY, AND THE ASYMMETRY WITH RIFTBOUND IS DELIBERATE. `SR` (109 products) and
        # `TR` (1 product) are stocked in Foil grades only in this file. Riftbound's
        # `Showcase` was narrowed on exactly that observation — but that file is the whole
        # English catalogue and this one is three sets out of many, marked partial by the
        # owner. "No plain SR in three sets" is a fact about three sets.
        #
        # So these two are THE live example of D23's superset: authored beyond the evidence,
        # reported by `game coverage` as a question, and blocking nothing. If a fuller One
        # Piece export ever shows SR foil-only across the catalogue, narrowing it becomes
        # the same argument Showcase already won.
        "finish_by_rarity": {
            "C": ("normal", "foil"),
            "UC": ("normal", "foil"),
            "R": ("normal", "foil"),
            "SR": ("normal", "foil"),
            "SEC": ("normal", "foil"),
            "TR": ("normal", "foil"),
            "L": ("normal", "foil"),
            "PR": ("normal", "foil"),
            "DON!!": ("normal", "foil"),
        },
        # D76. `sets`, and NOT `category`, on the same asymmetry this module already uses to
        # decide how far a matrix may be narrowed: the committed One Piece export is three
        # sets out of many, so nothing here has measured the whole category. It is the most
        # likely next `category` — 3622 rows for three sets suggests a small catalogue — and
        # it stays `sets` until a whole-category download says so.
        "export_scope": "sets",
        "located": True,
        # NO DENOMINATOR ANYWHERE IN THIS CATALOGUE, so `number_and_printed_total` is not
        # merely a poor fit — it is unmatchable, and `printed_total` is a field with no
        # referent for this game. The `Number` cells are `OP15-079`, `EB04-042`,
        # `ST26-005`, `PRB02-014`, `P-105`: a set code, a hyphen and a three-digit index,
        # printed on the card exactly as the export writes it.
        #
        # The 547 blank-`Number` rows are not an exception to this. 530 are `DON!!` cards
        # and 17 are sealed, and `pipeline/join.py` already falls to the name path whenever
        # the identification carries no number — the same blank-`Number` fallback T3
        # asserts for Pokemon code cards. `printed_code` describes how the other 3075 rows
        # are keyed; it does not have to describe the blank ones.
        "join_key": "printed_code",
        # WRITTEN 2026-08-23, as Riftbound's was. `identify/prompt.py:ONE_PIECE_CARD_V1`
        # asks for the printed code as ONE string with its hyphen intact — there is no
        # denominator in this game to be a second half of, which is the same fact
        # `join_key` records. Its prompt is deliberately REGION-NEUTRAL about where the
        # title sits: Pokemon's says "across the top of the card" and a One Piece card is
        # believed to print its name at the bottom of the artwork, and BELIEVED is the
        # whole of it — nobody has photographed one.
        "prompt": "one_piece_card_v1",
        # As Riftbound: nothing has measured this game's title or number placement.
        "crop_bands": (),
        "card_aspect": 0.716,
        "catalogued": True,
        "unverified": False,
    },
    {
        "key": "misc",
        "display": "Misc",
        # THE OWNER'S RULING: the occasional Yu-Gi-Oh, Weiss Schwarz, foreign-language or
        # Magic the Gathering card, estimated at ~1% of stock. Captured, located AND
        # IDENTIFIED like any other card, and carrying a free-text note typed by the operator
        # at capture as well, so it is findable by search later.
        #
        # THE NOTE IS ADDITIONAL, NOT A SUBSTITUTE, and this entry said the opposite until
        # 2026-08-23. It read "given NO IDENTIFICATION CALL — it would cost money on a card
        # being handled by hand anyway", which was an inference laid on top of the owner's
        # actual choice; his correction was *"i also want misc identified and submitted to
        # batch api -- i never said i didnt"*. The cost argument was never his and does not
        # survive D2's arithmetic anyway: at ~$5–15 per 10k cards, 1% of a shelf is cents.
        #
        # `catalogued: False`, AND THAT IS NOT `unverified: True` WEARING A DIFFERENT NAME.
        # An unverified game is a measurement somebody owes: get the export, author the
        # entry, clear the flag. This entry is already correct and always will be. If the
        # two shared a flag, every misc capture would read as a fault and every genuinely
        # unmeasured game would hide among 1% of the shelf — so they are different fields
        # and `unverified` is False here.
        #
        # `product_line` IS `None`, NOT `""`, AND THE TYPE IS THE POINT. There is no single
        # cell: this entry spans Magic, Yu-Gi-Oh, Weiss Schwarz and foreign-language
        # printings at once, and inventing a string would be exactly the guess D22 refuses.
        # `None` is not a `str`, so `Catalog.from_export`'s `Product Line` comparison can
        # never be true for it under any export — where `""` is a string that a malformed
        # row could conceivably carry, and is also the value an unverified entry uses, which
        # would collapse the two states on the one field that most needs to tell them apart.
        #
        # IT SITS OUTSIDE D12 ON TWO AXES AT ONCE, said here so no later reader has to
        # notice the contradiction themselves: a foreign-language printing breaks "English",
        # and Magic, Yu-Gi-Oh and Weiss Schwarz are different product lines entirely, not a
        # different era of this one. D12 is not being reopened — this entry is the explicit
        # carve-out, and it earns it by never reaching the pricing or listing path where
        # D12's Near Mint hardcode lives.
        "product_line": None,
        # Empty BY DECISION, not pending. There is no rarity ladder that means the same
        # thing across four games, and D23 already makes an empty rarity claim narrow
        # nothing — so the capture screen simply offers no rarity chips here.
        "rarities": (),
        "rarities_not_claimed": (),
        # No vocabulary to offer, so no condition string either. Nothing is being withheld
        # until an export arrives; there is nothing to withhold.
        "finishes": (),
        "condition_by_finish": {},
        "finish_by_rarity": {},
        # A physical card in a box like any other. D10 in full: sequential position at
        # capture, never renumbered, the label rendered everywhere. This is the field that
        # separates `misc` from `pokemon_code` — both are outside the join, only one is
        # outside the box.
        "located": True,
        # Never joins, never reaches an import file. `not_joined` is a named strategy rather
        # than an empty string so that a consumer dispatching on `join_key` has something to
        # match and refuse on.
        "join_key": "not_joined",
        # A MISC CARD IS IDENTIFIED LIKE ANY OTHER CARD AND GOES TO THE BATCH API. This
        # line said `operator_note` — a strategy meaning "never sent to the model" — until
        # the owner corrected it on 2026-08-23: *"i also want misc identified and submitted
        # to batch api -- i never said i didnt"*. The free-text note is ADDITIONAL and
        # always was; nothing about it implied the card goes unread.
        #
        # ITS OWN PROFILE, NOT POKEMON'S, and that is the whole reason this is a second
        # strategy rather than `pokemon_card_v1` reused. A Yu-Gi-Oh card has no
        # `printed_total`, a Weiss Schwarz card has no Pokemon rarity, and none of the four
        # populations here declares the finish enum D3 rung 3 cross-checks — this entry's
        # own `finishes` is empty, so asking for a finish would be asking a question the
        # registry says the game does not answer. `identify/prompt.py:MISC_CARD_V1` asks
        # instead for what every one of them prints: a name, an identifier, which game it
        # is, and what language it is in.
        "prompt": "misc_card_v1",
        # Identified, but still no bands. `geometry/crop.py`'s rectangles are fractions
        # measured on a Pokemon card, and nothing has measured where a Yu-Gi-Oh or Weiss
        # Schwarz card puts its name or its code — the same refusal `riftbound` and
        # `one_piece` make. It is also moot while `card_aspect` is None: detection refuses
        # first, so no crop retry is reached to cut a band for.
        "crop_bands": (),
        # `None` because there is no single answer and a guess would be worse than a blank.
        # Magic and Weiss Schwarz are 63x88mm (0.716) and Yu-Gi-Oh is 59x86mm (0.686);
        # picking either would be authoring a number nobody measured for the card in hand.
        #
        # THIS FIELD IS NOW READ, AND `None` IS A REFUSAL RATHER THAN A BLANK.
        # `cli/cmd_identify.py` passes it to `geometry.detect_card`, which raises
        # `UnknownCardShape` rather than detecting without a shape gate: a detector with no
        # aspect to check accepts any rectangle, and `detect_card`'s contract is that None
        # means a human should look and never that it guessed. The cost is one lost crop
        # retry on ~1% of stock that is being handled by hand anyway; the cost of the
        # alternative is a confident crop of the stand, the desk, or the next card along.
        "card_aspect": None,
        "catalogued": False,
        "unverified": False,
    },
)


# ----------------------------------------------------------------------- accessors


def keys() -> Tuple[str, ...]:
    """Every game key, in registry order — which is the order a picker should render."""
    return tuple(str(entry["key"]) for entry in GAMES)


def get(key: str) -> Dict[str, object]:
    """The entry for `key`, or raise. NEVER A DEFAULT AND NEVER A FALLBACK.

    A caller that wants the backfill for a record written before the field existed asks for
    `DEFAULT_GAME` by name, at the point of the read, where the substitution is visible. A
    default inside this function would make every unknown key silently become Pokemon, and
    the first symptom would be a Riftbound card priced off a Pokemon export.
    """
    for entry in GAMES:
        if entry["key"] == key:
            return entry
    raise UnknownGame(f"{key!r} is not a registered game; known: {', '.join(keys())}")


def is_catalogued(key: str) -> bool:
    """Whether this game has a TCGplayer catalog to join against at all.

    THE PREDICATE TO BRANCH ON BEFORE THE JOIN, and the reason `require` is not the first
    thing a caller reaches for. A `misc` card is captured, located, noted and identified like
    any other card and then stops at the catalog — no join, no import row — so the branch
    belongs where that path ends, not inside an exception handler after something already
    tried to price it.

    IT SAYS NOTHING ABOUT IDENTIFICATION, and it used to be read as though it did. This
    docstring listed "no identification" first among what a misc card does not get; that was
    never the owner's ruling, and `misc` now names a real prompt strategy. The question this
    predicate answers is whether there is a TCGplayer export to match a row against, and
    that is the only question it has ever been able to answer.
    """
    return bool(get(key)["catalogued"])


def export_scope(key: str) -> str:
    """How wide this game's Filtered Export is fetched — `category` or `sets` (D76).

    DEFAULTS TO `sets`, WHICH IS THE ONE THAT CANNOT BE WRONG BY OMISSION. `sets` still
    widens to the whole category unless the run's cards unanimously ask for a narrower file,
    so a game added to this registry without the field behaves exactly as D65 did — a larger
    download where the category is small, never a file narrower than the cards support.
    `category` is the claim that has to be measured, and only `riftbound` has the measurement.

    A GAME OUTSIDE THE REGISTRY ANSWERS THE DEFAULT RATHER THAN RAISING, unlike `get`. The
    caller is deciding how wide to ask, not what a card IS, and the safe answer to "how wide"
    for a game nobody authored is the wider one. `get`'s no-fallback rule is about the second
    question and is untouched.
    """
    try:
        entry = get(key)
    except UnknownGame:
        return DEFAULT_EXPORT_SCOPE
    scope = str(entry.get("export_scope") or DEFAULT_EXPORT_SCOPE)
    return scope if scope in EXPORT_SCOPES else DEFAULT_EXPORT_SCOPE


def export_needs_hint(key: str) -> bool:
    """Must this game's cards name their set before its export may be fetched?

    THE CLIFF THIS ANSWERS FOR, MEASURED 2026-09-12. The whole Pokemon category is
    32,629,598 B — 97.24% of `server/tcg_export.py:MAX_BYTES`, 903 KB of headroom — against
    238,482 B for the one set the owner's 543 Pokemon cards name. D76's rule is that a set
    filter needs the box to be UNANIMOUS, so ONE unhinted card widens the fetch by 137x and
    lands it two per cent short of the ceiling the transport refuses past. D76 wrote that a
    widening is always safe, and for this category it is not.

    SO THE GAME THAT CANNOT AFFORD A WIDENING SAYS SO, and `_scope_for_run` refuses a run
    whose own cards caused one. The other three voices are untouched: an operator naming
    sets or asking for `category` outranks this exactly as it outranks the unanimity rule
    (D76), and a game whose `export_scope` IS `category` never reaches the question.

    FALSE BY OMISSION, AND THAT IS THE SAFE DIRECTION HERE — the opposite of
    `export_scope`'s. A game nobody has weighed gets the behaviour it has always had: it
    widens, and the width is drawn on the preview before the press. Refusing on an
    unmeasured game would strand real cards on a guess, which is the one thing a rule about
    not spending money must not do.

    IT IS NOT DERIVED FROM `export_scope`, AND THREE OF THE FOUR ENTRIES ARE WHY. `sets` is
    the default and is carried by `pokemon_code` and `one_piece` as well — the first joins
    by name on the SAME category-3 cliff and can narrow nothing, the second is a small
    catalogue nobody has measured. A predicate off `export_scope` would refuse both for a
    measurement neither has.

    A GAME OUTSIDE THE REGISTRY ANSWERS FALSE rather than raising, for `export_scope`'s
    reason: the caller is deciding how wide to ask, not what a card IS.
    """
    try:
        entry = get(key)
    except UnknownGame:
        return False
    return bool(entry.get("export_needs_hint"))


def export_category_bytes(key: str) -> Optional[int]:
    """What this game's whole TCGplayer category weighs, if anything ever measured it.

    THE EVIDENCE FOR `export_needs_hint`, AND IT IS A SEPARATE FIELD ON PURPOSE. The
    boolean is a judgement about this number; keeping the number beside it means the
    judgement can be re-made by somebody reading the entry rather than archaeology through
    a commit message. `scripts/docs-audit.py`'s `games registry` row refuses the boolean on
    an entry that names no measurement, so the two cannot come apart.

    NULL IS "NOBODY HAS WEIGHED IT", never zero. Three of the four catalogued entries are
    null and the sentences this feeds say so rather than printing a figure they do not have.
    """
    try:
        entry = get(key)
    except UnknownGame:
        return None
    measured = entry.get("export_category_bytes")
    return int(measured) if isinstance(measured, int) and measured > 0 else None


def require(key: str) -> Dict[str, object]:
    """`get`, plus D22's refusal — in whichever of its two forms applies.

    The accessor every pipeline consumer should use for anything that would otherwise have
    to invent a rarity list, a finish enum or a condition string. It refuses loudly so that
    the alternative — quietly borrowing Pokemon's, which fits and is wrong — never becomes
    reachable. `get` is for a screen that wants to render a known-but-unavailable choice.

    TWO REFUSALS, BECAUSE THEY MEAN OPPOSITE THINGS. `NotCatalogued` says this game has no
    catalog and never will, so the caller is on a path a misc card should never have
    reached — check `is_catalogued` first. `EmptyVocabulary` says an entry is waiting for an
    export, which is a gap with a fix. Catching them as one thing would let a real
    unmeasured game hide behind the 1% of the shelf that is working as designed.
    """
    entry = get(key)
    if not entry["catalogued"]:
        raise NotCatalogued(
            f"game {key!r} has no catalog to join against, permanently — it spans several "
            "product lines at once, so there is no `Product Line` cell to filter an export "
            "by and no export that would settle it. This is not a missing measurement. "
            "Branch on games.is_catalogued() before the join; a card of this game is "
            "captured, located, noted and identified, and then goes no further."
        )
    if not entry["rarities"]:
        raise EmptyVocabulary(
            f"game {key!r} has no authored rarities"
            + (" (unverified: no export has been seen)" if entry["unverified"] else "")
            + ". Author its vocabulary in pipeline/games.py against a real export; do not "
            "fall back to another game's."
        )
    return entry
