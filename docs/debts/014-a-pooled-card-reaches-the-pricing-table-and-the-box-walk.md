## 14 — A pooled card reaches the pricing table and the box walk, and `located` suppresses the label everywhere and the photograph nowhere

**Asked and answered 2026-09-05, on the render-conditions question `make docs-audit`'s
`views exposure` row defers to D24's owner.** The row's own sentence offers three discharges —
drop the manifest line, prove the screen pooled-free the way `app/tests/fulfillment.spec.ts`
does, or take the ruling to the owner. This is that third one, with the trace behind it.

**THE ANSWER IS YES, AND NOTHING FILTERS IT.** A `located: false` card carries a real `box` and
`index` into `pricing.json`, into the cross-run worklist, into `#/inventory`'s walk and into
`#/`'s hero deck, and every one of those screens draws `photoUrl(box, index)` off it. The
exposures are real. They are not formalities.

**THE RULING CAME BACK THE SAME DAY, and it is two answers rather than one** — see "The
recommendation" below. `#/inventory` keeps its pooled photographs and loses its render;
`#/`, `#/runs` and `#/pricing` keep both, recorded and unfixed, until a real code card exists.

### The premise that was assumed, and why it is false

`CLAUDE.md` says code cards go through `./pkmnscan scan` — QR, free, no model call — rather than
`identify` / `join` / `emit`, which reads as though a pooled card never reaches a pricing row.
That is true of the QR path and it is not a filter, because the registry gives `pokemon_code`
a full singles-track profile:

| field | `pipeline/games.py` | consequence |
|---|---|---|
| `located` | `False` (`pipeline/games.GAMES`) | no label, no slot |
| `catalogued` | `True` (`pipeline/games.GAMES`) | passes the only join-path filter there is |
| `join_key` | `name_only` (`pipeline/games.GAMES`) | a real strategy, not `not_joined` |
| `prompt` | `pokemon_code_v1` | it is submitted to the paid Batch |

`pipeline/join.JOIN_KEY_STRATEGIES` routes `name_only` to a working `KeyStrategy`; the entry beside it,
`NOT_JOINED: None` in the same table, is what a game that never joins looks like, and
`misc` is its only holder (`pipeline/games.GAMES`). And `identify` does not merely tolerate a
code card — `cli/cmd_identify.CODE_GAME` names `CODE_GAME = "pokemon_code"` and
`cli/cmd_identify._code_ledger_lines` builds C8's code ledger out of code cards that went through the
paid run. **The singles pipeline has a code-card lane by design.**

`codes/__init__.py` states the schema half in as many words: no second capture path, the same
server, the same store, "`located: False` is the whole of the schema difference".

### The chain, end to end

1. **Capture.** `server/capture_server.py`'s `photo_path(box, index)` has no game
   dimension. A code card's photograph lands in `captures/cards/box<n>/<index>.jpg` beside
   every located card's.
2. **Scope.** A run's scope is the whole box directory (`server/pipeline_routes.py`) or a
   symlink set keyed by index alone (`server/pipeline_routes.py`). No game is consulted.
3. **Join.** The one exclusion on the resolve path is `games.is_catalogued`
   (two call sites in `cli/resolve.py`), and `pokemon_code` is catalogued.
   the pooled skip in `cli/resolve.box_views` is inside `box_views`, a **label renderer**, not a run
   filter.
4. **The table.** `cli/cmd_join.py` writes `positions: [{box, index, label}]` for every
   matched SKU across every game join, with no `located` test.
5. **The merge.** `server/pipeline_routes.py` de-duplicates positions across runs on
   `(box, index)` and never asks whether one is located.
6. **The screen.** `app/src/Pricing.tsx` draws a thumbnail per row and
   the full-size photo in the drawer, both off `positions[n]`.

**IT HAS ALREADY HAPPENED, AND THE REPO SAYS SO IN THE PAST TENSE.**
`server/pipeline_routes.py` records that pooled cards "do reach a join and did land in
this table wearing `Box N · Section N · Card M`", and
`harness/tests/t7_store_and_seams.py` asserts it as a live property today. What that fix
changed was the **caption**: `_relabel_positions` swaps `Position.label` for `join.place_text`
and, in its own words in `server/pipeline_routes._relabel_positions`, leaves `box` and `index` travelling
"exactly as stored" — which are the two integers `photoUrl` is aimed by.

### The pattern, stated once

**`located: false` suppresses the position label and the position bar on every owner screen,
and the photograph on none of them.** Four call sites, one shape:

- `app/src/Inventory.tsx` draws the pooled sentence in place of a label; the retire
  dialog's `<img>` in the same file is unguarded, and its `located` test suppresses only `PositionBar`.
- `app/src/CardLocations.tsx` drops the bar for a pooled copy; the `<img>` above it
  is unguarded.
- `app/src/position.ts` returns null for a pooled place. It sat inside
  `app/src/PositionBar.tsx` until 2026-09-06, when the position arithmetic moved out of the
  component so React Refresh could update it in place; the guard itself is unchanged.
- two places in `server/capture_server.py` serve a pooled row
  "undecorated but not bare" — no flat `label`, and `box`, `index` and `photo` all present.

The wire makes the client-side version of this hard on purpose and by accident:
`app/src/types.ts` types a position as `{box, index, label}` with **no `located` and no
`game`**, so `#/pricing` could not filter what it draws even if it wanted to — the only pooled
signal reaching it is a string inside `label`.

### Per screen

| route | verdict | evidence |
|---|---|---|
| `#/inventory` | **live, and deliberate** | `app/src/BoxBrowse.tsx` gives pooled cards their own `Pooled` shelf and a `Pooled · <game>` section header; `PhotoPanel` draws its `photoUrl` checking only `photo === null` and `photo_reclaimed_at`. The screen is BUILT to walk them. |
| `#/pricing` | **live** | the chain above. Also: `app/src/Pricing.tsx` starts `picked` empty, which D86 defines as "every open run", so the manifest's no-`?run=` render draws the worklist and its thumbnails, not a picker. |
| `#/` | **live, and the weakest link** | `app/src/Home.deckFromBoxes` builds `photoUrl` from a box's `next_index` high-water mark and consults no card record at all, so `located` is not knowable there. `app/src/Home.deckFromCards`'s second pass filters on photo, capture time, state and name — not on `located` — though `InventoryCard` carries both `game` and `place`. |
| `#/runs` | **real reach, gated render** | `app/src/RunsComposer.tsx` draws the crop-preview sample, and `server/pipeline_routes.py` picks it out of the box's whole capture directory with no game filter. **Three gates hold in a bare render** and this entry first said "live" without them: the composer is a modal (`app/src/RunsComposer.tsx`), `stage` opens on `'boxes'`, and the preview is not even fetched unless `scoped`. `scripts/views.txt` states them; the reach is real and the screenshot is not the way it leaks. |
| `#/gallery` | **formality, genuinely discharged** | `app/src/Gallery.tsx` replaced `photoUrl` with `SPECIMEN_PHOTO` through `CardLocations`'s `photoSrc` seam on 2026-09-06, and its pooled fixture carries `has_photo: false`. The reach `_photo_reach` still reports is through that seam. |

**`app/tests/inventory.spec.ts` does not answer this**, though it reasons about pooled
boxes: its subject is a box with `fill: 0` in the box REGISTRY, which is how a box of code
cards looks in the shelf LIST. The cards themselves are on the `Pooled` shelf, drawn in full.

### Why it is latent rather than live today

`docs/specs/code-cards.md` §8.1: **no real code card has ever been through this pipeline**, and
every decode number in that spec is synthetic. So the store holds no pooled capture and no
render can contain one. What arms every row of the table above at once is the owner
photographing their first box of code cards — which is what `#/codes` exists for, and a moment
they choose rather than stumble into.

### The recommendation

**Do not weaken `_pooled_exclusion_evidence`.** The tightening — a `test(...)` whose title
names `pooled` and claims `never` — is the correct reading, and this trace is why: the loose
form bought `#/inventory` and `#/pricing` with incidental prose on two screens that draw pooled
photographs in fact. `app/tests/pricing.spec.ts` matched on `located` **inside the word
RELOCATED**, and `app/tests/inventory.spec.ts` on a `pokemon_code` fixture belonging to
`#/codes`. An exemption bought by a word is worse than no exemption.

**IT LANDED (PR #148, merged 2026-09-05), AND THE LIST IT PRODUCED IS THE ONE THIS ENTRY
PREDICTED.** Four questions where there were two: `#/gallery`, `#/`, `#/runs` and `#/pricing`.
`#/inventory` is absent because its line was dropped, not because it was exempted.

**One shape already exists and it is the one to copy.** `app/src/Fulfillment.tsx` drops a pooled
copy from the view outright — at three places in `app/src/Fulfillment.tsx` — rather than
suppressing its label, and `app/tests/fulfillment.spec.ts` asserts it in a titled test. That is
the only exclusion in the product that a photograph cannot get past.

**Three answers are available per screen, and they are not the same answer:**

1. **`#/gallery`** — nothing to decide, and it is now the cheapest row on the list. The screen
   genuinely cannot fetch a stored photograph (`SPECIMEN_PHOTO` through `CardLocations`'s
   `photoSrc` seam), so a `never`-titled test over a fact that already holds retires the
   question honestly. `app/tests/gallery.spec.ts` already tests the pooled row; what it lacks
   is a title that makes the claim.
2. **`#/`, `#/runs`, `#/pricing`** — these draw pooled photographs incidentally, and none of the
   three has a reason to. The cheapest honest fix is a filter at the source: a `located` field
   on `PricingSku.positions` (the wire cannot express the fact today), a `game` test in
   `deckFromCards` plus a card-record consult in `deckFromBoxes`, and a game filter on the
   crop-preview sample. Each is small and each earns a `never`-titled test.
3. **`#/inventory`** — the only one that was a real question, **and it is answered.** Its
   `Pooled` shelf is a designed feature: the owner's one view of stored cards (D31) showing
   every card, including the pooled ones. Filtering the photograph there removes something
   built on purpose.

   **RULED 2026-09-05, by the owner, asked directly whether that shelf is worth looking at:
   yes.** So the photograph stays exactly as it is and the RENDER goes — `scripts/views.txt`
   no longer lists `#/inventory`, which is the `views exposure` row's own first discharge
   ("drop this line") taken on purpose rather than as a dodge. The screen is unchanged; what
   changed is that `make screenshot` no longer walks it.

   **The cost is named rather than waved past.** `#/inventory` is the densest screen in the
   product — three columns at 1440, a stack at 390 — and it is now the only owner screen with
   no automated render. Verifying it means opening it by hand at the three widths in both
   themes, per `CLAUDE.md`'s `## Verifying a screen`. Pointing `make screenshot` back at it
   re-arms the leak.

**THE OTHER THREE ARE RECORDED AND NOT BUILT, ALSO ON THE OWNER'S WORD (2026-09-05).** Asked
whether to filter `#/`, `#/runs` and `#/pricing` now, the answer was to keep the writeup and
build nothing. That is a defensible call while §8.1 holds — there is no pooled capture to
leak — and it is a **dated** one: the day a real code card is photographed, those three
screens start drawing it and this paragraph is the thing that was decided against. The
options above are costed and ready; none of them is more than a small filter and a test.

**What is NOT recommended is the sentence that makes all of this go away**: "code cards go
through `scan`, so no pooled card is ever joined". It reads as a design constraint and it is
not enforced anywhere — the registry, `cli/cmd_identify.CODE_GAME` and
`harness/tests/t7_store_and_seams.py` each contradict it. If the owner wants it to be
true, the place to make it true is `pipeline/games.py` or `cli/resolve.py`, not `CLAUDE.md`.
