"""T7 group: the capture's rarity claim settles which PRINTING of one card the free reader accepts.

Owner's ruling: when the top two candidates are the SAME card (same name once a parenthesised
suffix goes, same number, different product) and `rarity_claim` equals the rarity of exactly one
of the two printings, the reader accepts that printing. Same shape as `variant.resolve` picking a
finish from a claim. Never a guess: different cards, a claim that fits neither or both printings,
no claim, and a floor under `FLOOR_MIN` all stay refused.

INTERFACE THESE CHECKS ASSUME (the builder may rename, then re-point here):
`match.Request.rarity_claim` (a sequence of `Rarity` cells, like `Card.rarity_claim`) and
`match.Pool.rarities`, parallel to `Pool.rows`. Scores are stubbed: no model, no photo.
"""

from __future__ import annotations

import numpy as np
from unittest import mock

from harness.tests import Checks
from identify import match

EPIC, SHOWCASE = "Epic", "Showcase"
SAME_NAME = ("Vex, Gloomist", "Vex, Gloomist (Alternate Art)")
OTHER_NAME = ("Vex, Gloomist", "Kai, Dawnblade")


def _read(names, rarities, cosines, claim, numbers=("7", "7", "7", "7"), sets=("Set", "Set", "Set", "Set")):
    """One `Result` for one card against a pool whose cosine to the photo is `cosines`."""
    dim = 4
    vectors = np.zeros((len(cosines), dim), np.float32)
    vectors[:, 0] = cosines
    rows = [("riftbound", sets[i], f"p{i}", numbers[i]) for i in range(len(cosines))]
    pool = match.Pool(vectors, rows, list(names), ["10"] * len(rows), set(), ("Set",))
    pool.rarities = list(rarities)
    index = mock.Mock()
    index.meta.return_value = match.MODEL_SHA256
    index.pool.return_value = pool
    request = match.Request("k", "photo.jpg", "riftbound", "tcg")
    object.__setattr__(request, "rarity_claim", claim)
    one = np.zeros((1, dim), np.float32)
    one[0, 0] = 1.0
    with mock.patch.object(match, "_crop", lambda *_a: object()), \
            mock.patch.object(match, "embed", lambda *_a: one), \
            mock.patch.object(match, "_resolve_pool", lambda *_a: (("Set",), None, "")), \
            mock.patch.object(match, "SERVED_GAMES", ("riftbound",)):
        return match._read_chunk([request], index, None, 0.716, lambda _m: None)[0]


def _chose(result, product_id):
    return bool(result.accepted and result.payload and result.payload.get("product_id") == product_id)


def check_claim_settles_printing(checks: Checks) -> None:
    tight = [0.90, 0.88]  # margin 0.02, under MARGIN_MIN
    base_first = _read(SAME_NAME, (EPIC, SHOWCASE), tight, [SHOWCASE])
    checks.ok(_chose(base_first, "p1"), "claim Showcase picks the Showcase printing",
              f"accepted={base_first.accepted} code={base_first.code}")
    epic = _read(SAME_NAME, (EPIC, SHOWCASE), [0.88, 0.90], [EPIC])
    checks.ok(_chose(epic, "p0"), "claim Epic picks the base printing (even when it ranks second)",
              f"accepted={epic.accepted} code={epic.code}")


def check_claim_never_guesses(checks: Checks) -> None:
    tight = [0.90, 0.88]
    diff = _read(OTHER_NAME, (EPIC, SHOWCASE), tight, [SHOWCASE], numbers=("7", "8"))
    checks.ok(not diff.accepted, "two different cards stay refused despite a matching claim", f"{diff.code}")
    neither = _read(SAME_NAME, (EPIC, SHOWCASE), tight, ["Rare"])
    checks.ok(not neither.accepted, "a claim that fits neither printing stays refused", f"{neither.code}")
    both = _read(SAME_NAME, ("Rare", "Rare"), tight, ["Rare"])
    checks.ok(not both.accepted, "a claim that fits both printings (foil vs non-foil) stays refused", f"{both.code}")
    none = _read(SAME_NAME, (EPIC, SHOWCASE), tight, None)
    checks.ok(not none.accepted, "no claim stays refused", f"{none.code}")
    weak = _read(SAME_NAME, (EPIC, SHOWCASE), [0.70, 0.68], [SHOWCASE])
    checks.ok(not weak.accepted and weak.code != None, "a claim never lifts a floor under FLOOR_MIN", f"{weak.code}")


def check_claim_round_two(checks: Checks) -> None:
    """Four paths that accepted a wrong card (review of the first build)."""
    tight = [0.90, 0.88]
    blank = _read(SAME_NAME, (EPIC, ""), tight, [EPIC])
    checks.ok(not blank.accepted, "a blank rarity on the other printing may fit, so refuse", f"{blank.code}")
    missing = _read(SAME_NAME, (EPIC, None), tight, [EPIC])
    checks.ok(not missing.accepted, "a missing rarity on the other printing may fit, so refuse", f"{missing.code}")
    low = _read(SAME_NAME, (EPIC, SHOWCASE), [0.77, 0.74], [SHOWCASE])
    checks.ok(not low.accepted, "the floor applies to the chosen printing's own score", f"{low.code}")
    other3 = _read(SAME_NAME + ("Kai, Dawnblade",), (EPIC, SHOWCASE, EPIC), [0.90, 0.89, 0.88], [SHOWCASE],
                   numbers=("7", "7", "9"))
    checks.ok(not other3.accepted, "a different card within the margin of the pick refuses", f"{other3.code}")
    third = _read(SAME_NAME + ("Vex, Gloomist (Overnumbered)",), (EPIC, SHOWCASE, SHOWCASE), [0.90, 0.89, 0.88], [SHOWCASE])
    checks.ok(not third.accepted, "a third printing that also fits the claim refuses", f"{third.code}")
    reprint = _read(SAME_NAME, (EPIC, SHOWCASE), tight, [SHOWCASE], sets=("Set A", "Set B", "Set A"))
    checks.ok(not reprint.accepted, "a cross-set reprint is not the same card", f"{reprint.code}")


def check_claim_four_candidates(checks: Checks) -> None:
    """A rival past the third candidate still refuses: the third is the same card and does not fit."""
    names = SAME_NAME + ("Vex, Gloomist (Showcase)", "Kai, Dawnblade")
    cos = [0.90, 0.89, 0.88, 0.87]
    other = _read(names, (EPIC, SHOWCASE, "Rare", EPIC), cos, [SHOWCASE], numbers=("7", "7", "7", "9"))
    checks.ok(not other.accepted, "a fourth candidate that is another card, within the margin, refuses", f"{other.code}")
    fits = _read(names, (EPIC, SHOWCASE, "Rare", SHOWCASE), cos, [SHOWCASE], numbers=("7", "7", "7", "7"))
    checks.ok(not fits.accepted, "a fourth printing that also fits the claim, within the margin, refuses", f"{fits.code}")


CHECKS = (check_claim_settles_printing, check_claim_never_guesses, check_claim_round_two, check_claim_four_candidates)
