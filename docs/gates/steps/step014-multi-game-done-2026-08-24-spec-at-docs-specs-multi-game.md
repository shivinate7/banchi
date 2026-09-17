14. ~~**Multi-game**~~ — **done 2026-08-24.** Spec at `docs/specs/multi-game.md`. four capture choices plus `misc`, per D21-D25. Landed: the vendored
    registry with four real TCGplayer exports behind it, four audit rows, per-game dispatch,
    and `game` through all ten capture hops with the picker on the capture bar.

    **Every step is now built** (2026-08-23): step 5's rarity claim end to end, step 6's
    repeatable `--export` with per-game catalogs and one import file per game (D25), step 7's
    pooled non-located inventory and both opsec discharges, step 8's rarity clause — built
    behind its A/B flag, MEASURED, and switched off because it lost (holdout 0.9706 → 0.9559,
    $0.17; the numbers are in the T1 section above) — and step 9's per-game finalization:
    `riftbound_card_v1` and `one_piece_card_v1` exist, are registered, are dispatched to by
    the registry and carry parsers.

    **`pokemon_card_v1` did not move: `1ef974bf511d`, unchanged.** `prompt_fingerprint` hashes
    ONE profile's fields, so adding sibling profiles incurs no T1 re-measurement and none is
    owed. The new siblings hash to `2bd952abb691` and `615e974828b5`.

    **The trap that step 9 nearly walked into is worth keeping.** Both new games name their
    identifier field `number`, including Riftbound, whose field study had proposed
    `printed_code`. `cli/resolve.py` reads the RAW payload out of `identifications.json` and
    never calls `prompt.parse`, so a differently-named field would have parsed cleanly,
    recorded cleanly, and handed the join a card with `number=None` — `no_catalog_row` for
    every card in the run, blaming the export. `misc` gets away with `printed_id` only because
    `is_catalogued` diverts it before that read. The seam is now asserted end to end.

    **What no amount of code can close: neither game has met a card.** The store holds zero
    Riftbound and zero One Piece records, so every claim about those two prompts is a claim
    about a CSV and a schema, not about a photograph. Same standing as T6's synthetic
    composites before Gate B.
