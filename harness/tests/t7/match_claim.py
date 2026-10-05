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

import contextlib

import numpy as np
from unittest import mock

from harness.tests import Checks
from identify import match

EPIC, SHOWCASE = "Epic", "Showcase"
SAME_NAME = ("Vex, Gloomist", "Vex, Gloomist (Alternate Art)")
OTHER_NAME = ("Vex, Gloomist", "Kai, Dawnblade")


def _read(names, rarities, cosines, claim, numbers=("7", "7", "7", "7"), sets=("Set", "Set", "Set", "Set"),
          card_types=None):
    """One `Result` for one card against a pool whose cosine to the photo is `cosines`."""
    dim = 4
    vectors = np.zeros((len(cosines), dim), np.float32)
    vectors[:, 0] = cosines
    rows = [("riftbound", sets[i], f"p{i}", numbers[i]) for i in range(len(cosines))]
    pool = match.Pool(vectors, rows, list(names), ["10"] * len(rows), set(), ("Set",))
    pool.rarities = list(rarities)
    if card_types is not None:
        pool.card_types = list(card_types)  # the catalogue's `Card Type` cell, parallel to rows
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
    checks.ok(not weak.accepted and weak.code is not None, "a claim never lifts a floor under FLOOR_MIN", f"{weak.code}")


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


# ---------------------------------------------------------------- the four free-reader rules
# INTERFACE ASSUMED (the builder may rename, then re-point here): `Pool.card_types`, parallel to
# `rows` ("Battlefield" marks a battlefield, tcgcsv's `Card Type` extended cell); and
# `match.unreleased_sets(game)`, the set names with no stock photo yet, which `Index.pool` leaves
# out of `Pool.blocked`. Every accept carries its own `Result.code`.

CARDS = ("Vex, Gloomist", "Kai, Dawnblade", "Ari, Stormcaller")


def _plain(cosines, card_types=None, claim=None, rarities=("Rare", "Epic", "Rare")):
    return _read(CARDS, rarities, cosines, claim, numbers=("7", "8", "9"), card_types=card_types)


def _accepted(checks, codes, key, result, label):
    checks.ok(result.accepted, label, f"code={result.code}")
    checks.ok(bool(result.code), f"{label}: the accept names its reason", f"{result.code}")
    codes[key] = result.code


def check_rule1_claim_narrows(checks: Checks, codes=None) -> None:
    codes = {} if codes is None else codes
    near = [0.90, 0.88, 0.70]  # A leads, B is a near-tie
    _accepted(checks, codes, "claim", _plain(near, claim=["Epic"], rarities=("Epic", "Rare", "Rare")),
              "a claim that removes the near-tie competitor accepts the top-1")
    flipped = _plain(near, claim=["Epic"], rarities=("Rare", "Epic", "Rare"))
    checks.ok(not flipped.accepted, "a claim whose narrowed winner is not the top-1 refuses", f"{flipped.code}")
    none = _plain(near, claim=None, rarities=("Epic", "Rare", "Rare"))
    checks.ok(not none.accepted, "no claim leaves the near-tie refused", f"{none.code}")
    weak = _plain([0.60, 0.58, 0.50], claim=["Epic"], rarities=("Epic", "Rare", "Rare"))
    checks.ok(not weak.accepted, "a claim never lifts a weak floor", f"{weak.code}")


def check_rule2_battlefield(checks: Checks, codes=None) -> None:
    codes = {} if codes is None else codes
    bf, unit = ("Battlefield", "Unit", "Unit"), ("Unit", "Unit", "Unit")
    _accepted(checks, codes, "battlefield", _plain([0.50, 0.38, 0.20], bf), "battlefield, margin 0.12, floor 0.50, accepts")
    for label, cos, types in (
        ("battlefield margin 0.08 refuses", [0.50, 0.42, 0.20], bf),
        ("battlefield floor 0.40 refuses", [0.40, 0.28, 0.20], bf),
        ("a non-battlefield at floor 0.50 refuses", [0.50, 0.38, 0.20], unit),
    ):
        got = _plain(cos, types)
        checks.ok(not got.accepted, label, f"{got.code}")


def check_rule3_clear_winner(checks: Checks, codes=None) -> None:
    codes = {} if codes is None else codes
    _accepted(checks, codes, "clear", _plain([0.72, 0.63, 0.50]), "margin 0.09 at floor 0.72 accepts")
    low_margin = _plain([0.72, 0.65, 0.50])
    checks.ok(not low_margin.accepted, "margin 0.07 at floor 0.72 refuses", f"{low_margin.code}")
    low_floor = _plain([0.69, 0.60, 0.50])
    checks.ok(not low_floor.accepted, "margin 0.09 at floor 0.69 refuses", f"{low_floor.code}")


def _index_read(tmp, unreleased, status="no_photo"):
    """A real `Index`: the right card in `Set`, and a no-photo printing of the same name in `Future`."""
    import pathlib

    index = match.Index(pathlib.Path(tmp) / "index.sqlite")
    index.meta("model_sha256", match.MODEL_SHA256)
    good = np.array([1, 0, 0, 0], np.float32).tobytes()
    far = np.array([0.5, 0.8, 0, 0], np.float32).tobytes()
    rows = (("Set", "p0", "7", "Vex, Gloomist", "ok", good), ("Set", "p2", "9", "Kai, Dawnblade", "ok", far),
            ("Future", "p1", "7", "Vex, Gloomist (Alternate Art)", status, None))
    for set_name, pid, number, name, status, blob in rows:
        index.db.execute("insert into vec(game,set_name,product_id,number,name,url,status,note,vec,at) "
                         "values('riftbound',?,?,?,?,'',?,'',?,'')", (set_name, pid, number, name, status, blob))
    index.db.commit()  # the real `unreleased_sets` reads the file on its own connection
    request = match.Request("k", "photo.jpg", "riftbound", "tcg")
    if unreleased is None:  # the REAL `unreleased_sets`, with no release dates (the mirror is offline)
        stock = mock.Mock()
        stock.catalog_published.return_value = {}
        gate = [mock.patch.object(match, "_stock_images", lambda: stock),
                mock.patch.object(match, "index_path", lambda: index.path)]
    else:
        gate = [mock.patch.object(match, "unreleased_sets", lambda _game: unreleased, create=True)]
    with contextlib.ExitStack() as stack:
        for patch in gate + [mock.patch.object(match, "_crop", lambda *_a: object()),
                             mock.patch.object(match, "embed", lambda *_a: np.array([[1, 0, 0, 0]], np.float32)),
                             mock.patch.object(match, "_resolve_pool", lambda *_a: (("Set", "Future"), None, "")),
                             mock.patch.object(match, "SERVED_GAMES", ("riftbound",))]:
            stack.enter_context(patch)
        result = match._read_chunk([request], index, None, 0.716, lambda _m: None)[0]
    index.close()
    return result


def check_rule4_unreleased_sets(checks: Checks, codes=None) -> None:
    import tempfile

    codes = {} if codes is None else codes
    with tempfile.TemporaryDirectory() as tmp:
        fresh = _index_read(tmp, {"Future"})
    _accepted(checks, codes, "unreleased", fresh, "a no-photo printing in an unreleased set trips no guard")
    with tempfile.TemporaryDirectory() as tmp:
        released = _index_read(tmp, set())
    checks.ok(not released.accepted and released.code == match.UNREAD_LOOKALIKE,
              "a no-photo printing in a released set still trips the guard", f"{released.code}")


def check_unreleased_fallback_needs_no_photo_rows(checks: Checks) -> None:
    """No dates: only a set with no row at all, or only `no_photo` rows, may count as unreleased.
    A released set whose rows are all `unreadable` or `no_url` (a transient failure) is not."""
    import tempfile

    for status in ("unreadable", "no_url"):
        with tempfile.TemporaryDirectory() as tmp:
            got = _index_read(tmp, None, status)
        checks.ok(not got.accepted and got.code == match.UNREAD_LOOKALIKE,
                  f"no dates, a set of only {status} rows: its look-alike still trips the guard", f"{got.code}")


def check_claim_as_bare_string(checks: Checks) -> None:
    """A `rarity_claim` that arrives as one string is one cell, never a substring pool."""
    near = [0.90, 0.88, 0.70]
    got = _plain(near, claim="Epic Showcase", rarities=("Epic", "Rare", "Rare"))
    checks.ok(not got.accepted, 'claim "Epic Showcase" (a bare string) does not fit an "Epic" printing', f"{got.code}")
    star = _plain(near, claim="Epic", rarities=("Epic", "Epic Showcase", "Rare"))
    checks.ok(star.accepted, 'claim "Epic" (a bare string) is one cell and removes "Epic Showcase"', f"{star.code}")


def check_accept_reasons_distinct(checks: Checks) -> None:
    codes: dict = {}
    scratch = Checks()
    for fn in (check_rule1_claim_narrows, check_rule2_battlefield, check_rule3_clear_winner, check_rule4_unreleased_sets):
        fn(scratch, codes)
    every = list(codes.values()) + [match.ACCEPT_CLAIM]
    checks.ok(len(codes) == 4 and all(every) and len(set(every)) == len(every),
              "each rule's accept carries its own reason code", f"{codes}")


CHECKS = (check_claim_settles_printing, check_claim_never_guesses, check_claim_round_two, check_claim_four_candidates,
          check_rule1_claim_narrows, check_rule2_battlefield, check_rule3_clear_winner, check_rule4_unreleased_sets,
          check_unreleased_fallback_needs_no_photo_rows, check_claim_as_bare_string, check_accept_reasons_distinct)
