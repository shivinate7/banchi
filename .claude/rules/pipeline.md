---
paths:
  - "pipeline/**"
  - "cli/**"
  - "identify/**"
---

# The pipeline, the CLI and the paid read

`./banchi <command> --help` prints each command's flags and what it costs. `identify` costs money: run `--dry-run` first.
The free verbs besides `join` and `emit` are `./banchi scan <capture-dir>` (code cards only), `./banchi rescue <run-dir>`,
`./banchi prices adopt`, `./banchi readings adopt`, `./banchi archive sweep`, `./banchi queue refresh` and `./banchi reconcile`.
Each command's `--help` says what it writes.

- **The join key is per game and normalized on both sides** (`pipeline/games.py`,
  `pipeline/join.py:number_index_key`). Never join on Product Name. D35 (Product Name join) allows it only as a last
  resort, when the number key finds nothing. A name that resolves to one card is listed. A name that resolves to
  more than one queues for review. `zfill` is composition only, never matching.
- **A run's slot numbers are not the truth. The photograph is** (D36, the store says which slot).
  `cli/resolve.py:realign` re-binds records. It refuses on ambiguity and on a reallocated box.
- Only two columns are ever written: `Add to Quantity`, `TCG Marketplace Price`. `TCGplayer Id` is never modified.
- **No duplicate SKU rows in an import file.** Aggregate by SKU. `Add to Quantity` equals the copy count. There is no standing
  cap (D7, duplicates aggregate by SKU). A send may ask for one (`emit --cap N`) or for a quantity (`emit --quantity SKU=N`).
  `uncommitted_positions` stops a copy going out twice.
- **`emit` over several runs writes one file, and a cap is spent once** (D86, one pricing file for the store; `pipeline/join.py:add_to_quantity`).
  `#/pricing` lands on every unsent copy in the store (D156, one worklist), read live.
- **A card's number counts the cards in the box, not the slots** (D58, a card's number counts the cards). The stored index never moves. A departed card
  renders `pipeline/join.departed_label`.
- **A set hint on some cards narrows nothing** (D76, how wide to ask is per game). Widening needs every card hinted and
  every hint resolved. A Pokemon run that would widen is refused (`export_needs_hint` in `pipeline/games.py`, D170, a Pokemon run names its sets)
  unless the operator named `set_ids` or `scope`. A widening is never silent: every fetch carries a `width` block.
  Fix an unhinted card in Manage box, under Set claims.
- **The catalog export belongs to the game, not the drawer** (D166, the catalog export is a property of the game). It lands in `inventory/.exports/<game>/`.
  A covering export downloaded on the same US Central day is reused. `refresh: true` forces a new one; 900 s (`REFRESH_DEBOUNCE_S`) is only the double-press guard on a finished "Refresh now".
  A send whose runs' prices come from an export older than today (US Central) refreshes them first, or stops and says why.
- **The pricing answer is one file, keyed by SKU** (D86, one file for the store): `pipeline/corpus.py` over
  `inventory/prices.json`. `policy.threshold` is also the floor, and the owner sets it. Its default is $0.49 (`pipeline/corpus.py:DEFAULT_CUTOFF`). `sub_threshold` also defaults to $0.49, a default and not the floor (D9, threshold and floor).
  `banchi prices adopt` migrates legacy run files. `join` and `emit` refuse over an unadopted one.
- **The free reader sets itself up** (D301, stock photos are hotlinked, never mirrored). `match prepare` downloads the pinned model file
  and reads each stock photo once, and `serve` starts it whenever the store holds a card from an unread set. Env `BANCHI_AUTO_SETUP=on`
  forces auto-start. Unset, it is refused when `CI` or `BANCHI_HARNESS` is set (`make harness` sets it) and in a linked worktree.
  `match --sweep` is the background reader's watcher: it never spends, reads even mid-feed, and is off until the Capture screen's Rig switch is on.
  The runs sheet's Prepare press is a manual refresh.
