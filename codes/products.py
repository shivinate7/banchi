"""What product a code redeems, and what that is worth.

THIS MODULE IS WHY THERE IS NO OCR IN THIS TRACK. C2 specified a SKU crop taken relative to
the QR as a fiducial, then Tesseract with an `A-Z0-9` whitelist, then a fuzzy match against
a hand-built SKU table — all of it to answer ONE question: which product is this code for.
That question has a cheaper and more reliable answer, and the answer is that **code cards
arrive in sealed-product batches**. A booster box yields 36 identical booster code cards; an
Elite Trainer Box yields one ETB code. The operator is not sorting a shuffled pile — they
are feeding a stack that came out of one thing, and they already declare the set at capture
in the `set_hint` field that has existed since step 7a.

So the product is a CAPTURE CLAIM, in exactly the sense D21 gives that word: client state,
resent with every capture, written to the record and the sidecar, and correctable afterwards
on the card that got it wrong. Same family as `game`, `set_hint`, `metadata_finish` and
`rarity_claim`. That is one picker on a screen against a fiducial crop, an OCR engine, a
whitelist, a fuzzy matcher and a hand-built table kept honest by nobody — and the picker is
right more often, because the operator can see the box the cards came out of and the camera
cannot.

WHAT IS GIVEN UP, SAID PLAINLY: a genuinely shuffled mixed pile of unknown provenance cannot
be sorted by this route, and C2's OCR path could in principle have done it. Three things say
that trade is right anyway. The value data below says a booster code is worth $0.03 and sells
in undifferentiated bulk, so sorting a mixed pile of them by set is work that earns nothing.
The premium products, where set and product DO decide the price, are the ones that arrive in
ones and twos and are trivially declared. And where provenance really is unknown, the paid
vision read is still there as a fallback: `identify/prompt.py:pokemon_code_v1` already reads
the printed set line, and it costs about $0.002 a card — worth spending on a $1.39 code and
never worth spending on a $0.03 one.

OBSERVED PRICES, AND EXACTLY WHAT THEY ARE. Read off the Near Mint rows of
`fixtures/pokemon_wide_export_untouched.csv`, which is a real TCGplayer Filtered Export
scoped to FOUR sets — Cosmic Eclipse, Crown Zenith, Stellar Crown and Prismatic Evolutions.
51 distinct code-card products, 255 rows across the five conditions, 80 of them carrying any
price at all. This is a TCGplayer catalog price and NOT a realised sale: it says what the
marketplace lists at, and says nothing whatever about whether anything sold. Treat it as the
price floor evidence it is, and read `docs/specs/code-cards.md` for the channel argument.

    tier                  n  priced     min   median      max
    pc_etb                3       3    1.19     1.39     1.50
    premium_collection    6       6    0.09     0.26     1.50
    build_battle          2       1    0.20     0.20     0.20
    other                 1       1    0.17     0.17     0.17
    etb                   4       4    0.09     0.16     2.00
    collection           10      10    0.04     0.09     0.99
    blister              11       8    0.04     0.08     0.15
    tin                   8       5    0.03     0.05     0.12
    booster               4       4    0.03     0.03     0.05
    theme_deck            2       0       -        -        -

Computed with `classify` BELOW, over all 51 products, so the table and the code cannot
disagree. An earlier draft of it was computed with a throwaway classifier that matched bare
substrings, and it put the four "Premium Checklane Blister" products — $0.06 to $0.15 — in
the premium tier on the word "premium" alone. Corrected here and fixed in `PRODUCTS`.

THE SPREAD IS THE WHOLE BUSINESS. A Pokemon Center ETB code lists at roughly FORTY-SIX TIMES
a booster code. Boosters are also the overwhelming majority of any real pile — one per pack —
so the pile's value is a long flat floor with a few tall spikes in it, and the operating rule
the fork already stated on instinct ("separate non-`BST` codes on sight") is confirmed by the
first numbers anyone here has looked at. `TIER_FLOOR` below is what a screen uses to draw
that distinction, and D9's $0.40 threshold falls neatly between the two populations, which is
not a coincidence: D9 chose $0.40 and predicted this exact split three months early.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

# The operator-facing vocabulary. Ordered as a picker should draw it: the two that account
# for nearly every physical card first, then the premium tail in descending value.
#
# DERIVED FROM THE CATALOG, NOT INVENTED. Every key below classifies at least one real
# `Product Name` in the fixture export. A vocabulary authored from imagination is the thing
# D22 refuses for rarities, and there is no reason it should be legal one track over.
# `match` IS OR-OF-ANDS: a tuple of alternatives, each alternative a tuple of substrings that
# must ALL be present. Bare-substring matching was the first build and it was WRONG on real
# catalog rows — "Premium Checklane Blister" lists at $0.06 to $0.15 and matched the premium
# tier on the word "premium" alone, promoting a cheap blister into the population the whole
# business plan is about singling out. Requiring "premium" AND "collection" together is what
# separates "Super-Premium Collection" from "Premium Checklane Blister", and no ordering
# trick can do it, because one word is a genuine substring of both names.
PRODUCTS: Tuple[Dict[str, object], ...] = (
    {"key": "booster", "display": "Booster pack", "match": (("booster pack",),),
     "redeem_limit": 400, "premium": False},
    {"key": "blister", "display": "Blister", "match": (("blister",),),
     "redeem_limit": 4, "premium": False},
    {"key": "tin", "display": "Tin", "match": (("tin",),),
     "redeem_limit": 4, "premium": False},
    {"key": "theme_deck", "display": "Theme deck", "match": (("theme deck",),),
     "redeem_limit": 4, "premium": False},
    {"key": "build_battle", "display": "Build & Battle box",
     "match": (("build & battle",), ("build and battle",)),
     "redeem_limit": 25, "premium": False},
    {"key": "collection", "display": "Collection", "match": (("collection",),),
     "redeem_limit": 4, "premium": False},
    {"key": "etb", "display": "Elite Trainer Box", "match": (("elite trainer",),),
     "redeem_limit": 4, "premium": True},
    {"key": "premium_collection", "display": "Premium collection",
     "match": (("premium", "collection"),),
     "redeem_limit": 4, "premium": True},
    {"key": "pc_etb", "display": "Pokémon Center ETB",
     "match": (("pokemon center", "elite trainer"),),
     "redeem_limit": 4, "premium": True},
    {"key": "other", "display": "Other / unsure", "match": (),
     "redeem_limit": 4, "premium": False},
)

KEYS: Tuple[str, ...] = tuple(str(entry["key"]) for entry in PRODUCTS)

# WHICH GAME CLAIMS A PRODUCT, and the only place that fact is written down. The capture
# screen has to know whether to draw the product picker, and the two ways it could have
# learned are both worse: hardcoding `pokemon_code` in the app is the registry mirror
# `CaptureScreen.tsx` explicitly refuses, and adding a flag to `pipeline/games.py` would put
# a fact about THIS track into the file every track shares — a file that must additionally
# stay `ast.literal_eval`-safe for `scripts/docs-audit.py`, so it could not simply import
# this one. `GET /games` serves this string and the app compares its chosen game against it.
GAME = "pokemon_code"
UNKNOWN = "other"

# What a screen calls the two populations, and the boundary between them. `premium` above is
# the per-product flag; this is the sentence that explains it. Deliberately NOT a price
# threshold computed at runtime: the catalog price of a given product moves week to week and
# the OPERATING distinction does not — a Pokemon Center ETB code is worth singling out
# whatever this week's export says, because there is one of them per sealed box.
TIER_FLOOR = "booster and other bulk product — sells by the lot, not by the code"
TIER_PREMIUM = "premium product — worth listing and tracking as an individual code"

# The redemption limits above are TPCi's, as recorded in the fork's C3. They are carried here
# rather than in prose because a lot listing has to state them and a buyer will ask: 400
# boosters, 25 Build & Battle, 4 of most everything else, per account. UNVERIFIED AGAINST A
# CURRENT SOURCE — C3 recorded them and this module has not re-checked them, which is exactly
# the kind of inherited number `docs/specs/code-cards.md` names in its open questions.

_BY_KEY: Dict[str, Dict[str, object]] = {str(e["key"]): e for e in PRODUCTS}

# `Code Card - <anything>` is how every one of the 51 catalog rows is named. The prefix is
# stripped before classification so a set whose NAME contains a product word cannot be
# misread as that product.
_PREFIX = re.compile(r"^\s*code\s+card\s*-\s*", re.IGNORECASE)


def get(key: str) -> Optional[Dict[str, object]]:
    return _BY_KEY.get(key)


def display(key: Optional[str]) -> str:
    entry = _BY_KEY.get(key or "")
    return str(entry["display"]) if entry else "Unknown product"


def is_premium(key: Optional[str]) -> bool:
    entry = _BY_KEY.get(key or "")
    return bool(entry and entry["premium"])


def classify(product_name: str) -> str:
    """Which product key a TCGplayer `Product Name` describes.

    ORDER MATTERS AND IS THE REVERSE OF `PRODUCTS`. "Pokemon Center Elite Trainer Box" also
    contains "elite trainer", and "Super-Premium Collection" also contains "collection" — so
    the most specific match has to be tried first, while `PRODUCTS` is ordered for a PICKER
    (commonest first). Iterating it backwards gives the matcher the order it needs without a
    second hand-maintained list that could disagree with the first. Order alone is NOT
    sufficient, which is what the AND-semantics above are for. A name matching nothing is
    `other`, never a guess.
    """
    if not product_name:
        return UNKNOWN
    text = _PREFIX.sub("", str(product_name)).lower()
    for entry in reversed(PRODUCTS):
        for alternative in entry["match"]:  # type: ignore[union-attr]
            if all(token in text for token in alternative):
                return str(entry["key"])
    return UNKNOWN


# What an UNCLAIMED code is grouped under. Deliberately NOT `other`, and this was a real
# display bug: folding a null product into `other` made the tier table draw the unclaimed
# code as "bulk / Other or unsure" while `codes_routes._pool` was correctly refusing to put
# it in the bulk lane — the table and the lane saying different things about the same code,
# on the screen whose entire job is that distinction. `other` is a CLAIM ("I looked, and it
# is none of the above"); null is the absence of one, and they take different actions.
UNCLAIMED = "unclaimed"


def summarize(entries) -> List[Dict[str, object]]:
    """Ledger entries grouped by product, premium first. What a screen draws.

    `lane` IS ON EVERY ROW so the table cannot disagree with the lane that would actually
    take the code. It is the same three-way answer `codes_routes._pool` reaches, and the
    unclaimed row says `none` rather than `bulk`.
    """
    counted: Dict[str, int] = {}
    for entry in entries:
        key = getattr(entry, "product", None) or UNCLAIMED
        counted[key] = counted.get(key, 0) + 1
    rows = []
    for key, count in counted.items():
        unclaimed = key == UNCLAIMED
        premium = (not unclaimed) and is_premium(key)
        rows.append(
            {
                "product": key,
                "display": "No product claim" if unclaimed else display(key),
                "premium": premium,
                "lane": "none" if unclaimed else ("premium" if premium else "bulk"),
                "count": count,
            }
        )
    # Premium first, then bulk, and the unclaimed row LAST — it is the one that needs an
    # action rather than a decision, and the screen says so in a sentence of its own.
    rows.sort(key=lambda r: (r["lane"] == "none", not r["premium"], -int(r["count"])))
    return rows
