# The capture server

- **The capture server is threaded.** It is `class CaptureServer(ThreadingHTTPServer)` in
  `server/capture_server.py`, with `request_queue_size = 128` and `CaptureHandler.timeout = 15`.
  `REQUEST_SLOTS = 4` bounds executing requests. `PHOTO_SLOTS = 4` bounds `/photo/` and `/assets/`
  GETs and the cheap lock-free reads in `PHOTO_LANE_EXACT`, `/status` first (refusal `photo_busy`). The pool is safe over HTTP/1.1 only because every response sends
  `Connection: close` (DEBT11, a parked writer still holds a request slot). A burst of clients kills it.
  The `server concurrency` row of `make docs-audit` reads these figures.

# The pipeline and the store

- **The join key is per game and normalized on both sides** (`pipeline/games.py`,
  `pipeline/join.py:number_index_key`). Never join on Product Name. D35 (Product Name join) allows it only as a last
  resort, when the number key finds nothing. A name that resolves to one card is listed. A name that resolves to
  more than one queues for review. `zfill` is composition only, never matching.
- **A run's slot numbers are not the truth. The photograph is** (D36, the store says which slot).
  `cli/resolve.py:realign` re-binds records. It refuses on ambiguity and on a reallocated box.
- **No duplicate SKU rows in an import file.** Aggregate by SKU. `Add to Quantity` equals the copy count. There is no standing
  cap (D7, duplicates aggregate by SKU). A send may ask for one (`emit --cap N`) or for a quantity (`emit --quantity SKU=N`).
  `uncommitted_positions` stops a copy going out twice.
- **A card's number counts the cards in the box, not the slots** (D58, a card's number counts the cards). The stored index never moves. A departed card
  renders `pipeline/join.departed_label`.
- **A set hint on some cards narrows nothing** (D76, how wide to ask is per game). Widening needs every card hinted and
  every hint resolved. A Pokemon run that would widen is refused (`export_needs_hint` in `pipeline/games.py`, D170, a Pokemon run names its sets)
  unless the operator named `set_ids` or `scope`. A widening is never silent: every fetch carries a `width` block.
  Fix an unhinted card in Manage box, under Set claims.
- **The catalog export belongs to the game, not the drawer** (D166, the catalog export is a property of the game). It lands in `inventory/.exports/<game>/`.
  A covering export downloaded on the same US Central day is reused. `refresh: true` forces a new one; 900 s (`REFRESH_DEBOUNCE_S`) is only the double-press guard on a finished "Refresh now".
- **The pricing answer is one file, keyed by SKU** (D86, one file for the store): `pipeline/corpus.py` over
  `inventory/prices.json`. `policy.threshold` is also the floor, and the owner sets it. Its default is $0.49 (`pipeline/corpus.py:DEFAULT_CUTOFF`). `sub_threshold` also defaults to $0.49, a default and not the floor (D9, threshold and floor).
  `banchi prices adopt` migrates legacy run files. `join` and `emit` refuse over an unadopted one.
- **The store of record is one SQLite file** (D88, SQLite and one transaction per write). `inventory.json` is
  legacy and read by nothing.
- **A sold card's photograph is reclaimed on purpose** (D89, reclaimed on purpose): `POST /boxes/<box>/photos/reclaim` deletes sold
  photographs and keeps every record.
- **`emit` over several runs writes one file, and a cap is spent once** (D86, one pricing file for the store; `pipeline/join.py:add_to_quantity`).
  `#/pricing` lands on every unsent copy in the store (D156, one worklist), read live.
- **No automatic sectioning** (D10, inventory model). A divider is put in with `S` on the capture screen
  (`store/master.py:open_section`, inside the store lock).
- **A box is addressed by name, and names are unique** (D20, a box is an object). `Box.bid` is a never-reused
  index drawn on no screen (D145, a box has an index nobody sees). A run records `bid`, never the name (D56, a run names the drawer).
