## 14 — A pooled card reaches the pricing table and the box walk, and `located` suppresses the label everywhere and the photograph nowhere

Code cards are dormant, and this is what arms on the day one is photographed. A `pokemon_code` card (`located: False`, `catalogued: True`, `join_key: name_only`, `prompt: pokemon_code_v1` in `pipeline/games.py`) goes through `identify`, `join` and `emit` like any singles card, and `cli/cmd_identify.CODE_GAME` names it. Its photograph lands in `captures/cards/box<n>/` beside every located card's.

`located: false` suppresses the position label and bar on every owner screen and the photograph on none. `PricingSku.positions` (`app/src/types.ts`) is `{box, index, label, cid?, capture_id?}` with no `located` and no `game`, so `#/pricing` cannot filter. `server/pipeline_routes._relabel_positions` fixed the caption only.

| screen | state |
|---|---|
| `#/inventory` | draws pooled photographs on purpose: the `Pooled` shelf is the owner's one view of stored cards (D31), and the owner ruled the photograph stays |
| `#/pricing` | draws them in row thumbnails and the drawer |
| `#/` | `Home.deckFromCards` filters on photo, capture time, state and name, not on `located` |
| `#/runs` | the crop-preview sample (`do_pipeline_crop_preview`) is picked from the box's whole capture directory with no game filter |

`#/fulfillment` drops a pooled copy outright and a titled test asserts it. That is the one exclusion a photograph cannot get past.

**Outcome at risk.** Once a real code card is photographed, `#/`, `#/runs` and `#/pricing` draw it on screens the owner did not choose for it. No real code card has been through this pipeline, so nothing draws one today.

**Closes when.** Deferred until the owner starts code cards. Build the filters when the code-card feature leaves DORMANT (CLAUDE.md's Code cards section), before the first code card is photographed: `PricingSku.positions` carries `located`, `Home.deckFromCards` tests the game and the crop-preview sample filters by game, each with a `never`-titled test. Or `pipeline/games.py` or `cli/resolve.py` makes "a pooled card never joins" true. `CLAUDE.md` saying so does not.
