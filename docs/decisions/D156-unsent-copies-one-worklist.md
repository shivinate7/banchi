## D156 — Every unsent copy is one worklist

**`#/pricing`'s default landing is every copy in every joined run that TCGplayer does not hold.** That covers every run and every box. The copies are priced where prices are decided, and one press that already writes one file across runs sends them.

The operator reported that the only intuitive way to push supply was when pricing a run. Pushing older inventory from a capped run had no clear path. The operator then chose the shape: runs should be more unified, so unsent copies go on one worklist.

### What was structural about it

`emit` is run-scoped, and so was the only screen that reached it. `GET /pipeline/pricing` opened every run that still OWED something. Those were the two refusals in `Decisions.blocking`, or a run that had never emitted. It closed the rest. A run emitted under the old standing cap of four (D7, rewritten later) wrote `add 4 · backstock 3`. It raised `pushed` to four and owed nothing. So it closed with three copies still on the shelf. Nothing reopened it. The picker chip read *Answered*, the default landing left it out, and the three copies were reachable from no control in the product. **A copy held back on purpose became unreachable.**

Opening the run by hand did not help, and this half hid the first. The route merged rows from each run's `pricing.json`. `join` writes that table BEFORE the emit, and `emit` never changes it. So a re-opened run drew `4 of 7` for a card the press had already spent four of. D86 recorded this as "reported here, corrected in `emit`". The screen said four. The press would have written three. Neither said the other was wrong.

### Measured on the operator's store

Twelve joined runs, 2,535 cards, 492 listings. Two runs sit over a drawer whose number was deleted and reused (D36). They are excluded by name.

| | under the old rule | now |
|---|---|---|
| runs on the default landing | 1 | **6** |
| unsent copies on it | 315 | **660** across 332 SKUs |
| runs closed while still holding unsent copies | **5**, holding **381** | 0 |
| SKUs whose every unsent copy was in a closed run | **91**, 262 copies | 0 |

Sixty of the 660 are under a deliberate hold (D86). They sink to the held tier as before, and the press drops them by name. **The press's own plan over the same six runs offers 600, and the route offers 600.** `merge.plan`, read off `resolve.load`, is what `emit` writes. That agreement is the load-bearing fact of this entry. The harness case pins it. Seven copies, a capped emit of four: the route says three, and the next emit writes three.

Five runs closed under the old rule. Each lists its unsent copies:

- `2026-08-24-box2-01`: 148. Box 2 is the Pokemon bulk. It was emitted once under the cap and never looked at again.
- `2026-09-01-box3-01`: 150.
- `2026-09-11-box4-04`: 47.
- `2026-09-11-box4-03`: 32.
- `2026-08-31-box3-01`: 4.

### The four questions, answered

**Where it lives: `#/pricing`. It is the first door widened, not a third door.** The operator asked for runs to be more unified. The answer is a view that is not run-scoped. That is the opposite of putting it on `#/runs`. That screen is the run log and the money gate. A run there is one box (D180). `#/inventory` is where cards are, and it never sends (D31). The ship bar, the cut-off, the cap field, the per-card quantity, the holds and the rule strip all live on `#/pricing`. D105's rule decides it: a markdown lives where prices are decided, and so does a send.

A run waiting at phase join is on no worklist until it joins. The price refresh joins each one (`do_run_match`), so its cards land here. One rule changed. A run is open while it owes something OR holds an unsent copy. The default landing asks for open runs, so it became the unsent worklist by that definition alone. `roster[].unsent` is the count. `owes` is unchanged, so Home's "runs to price" keeps its meaning.

**A row is a SKU, and its copies sit on it.** The import file counts by SKU with a quantity (D7). The row already draws every box a card sits in. It also draws the positions that address its photograph. The Qty field's placeholder shows the copies that can still go. Its title says how many of the rest are already at TCGplayer. A row per copy would draw seven rows for one line of the spreadsheet.

**It prices exactly as the screen always has, and it invents nothing.** The corpus answers (D86), and the standing rule prices every row. A hold sinks. A card with no market data and no answer is what `owes` already refuses the press for. A copy from a run joined three weeks ago carries that export's market price, and the row says so. "read 3 weeks ago" is the existing age. "Join again" on `#/runs` is the existing refresh.

**What cannot go is named on the deck, with a door for each.** The wire field `unreachable` lists four kinds. Cards captured and never identified: 214 on the operator's store. Cards waiting in review: 1. Runs identified and never joined: 2. Runs over a reallocated drawer: 2. Each is a link to the screen that moves it. A worklist that left them out would be the silent drop that `CLAUDE.md` forbids, one level up. The operator would count a shelf against a screen and find fewer cards than exist.

### How the figure is live, and why it is not a third implementation

`server/pipeline_routes.py:_unsent_ledger` runs `cli/resolve.py`'s own functions over the store as it stands. It uses `_live_by_sku` for each run's recorded export, newest reading per SKU (D87's rule). It uses `_copies_out` for what TCGplayer holds. It uses `_committed_keys` to spend that on positions, oldest capture first (D147). It applies the same set subtraction that `SkuMatch.uncommitted_positions` applies. A copy in a terminal state is committed by the arm that `load` uses for one.

**This entry is built on top of D147, not beside it.** The ledger reads the same `_committed_keys`. Its numbers were wrong until that ordering landed, and they are right by the same fix.

**A copy stamped after the join is counted, because the send counts it.** A review answer writes `sku` onto a record after `pricing.json` was written. `load` adopts that identity on the next resolve. The ledger unions each SKU's table positions with every copy on hand that carries the SKU and whose `run` is on screen. The merged row draws those positions, labelled from the live store. Measured: **74 copies** across the ten joinable runs were in no table and in the press.

**One `_copies_out` runs over the newest reading per SKU.** The send resolves one reading per leg. That function walks every listing with two queries each. That is 0.9s per call on 492 listings. Ten legs would put nine seconds in front of every reload. The answers differ in one shape: two legs of one SKU. The older export read higher than the newer. `pipeline/merge.py:_merged_match` keeps the larger and calls that a stand-in. On a store that reconciles, the store's reading is newer than both files, and the case does not arise.

**The key is read as stored and never realigned (D36).** Every other reader on this route shares that posture. `paperwork_for` hashes every photograph in a box to realign. A reload cannot carry that cost. The send realigns. **Measured residual: 2 of 332 SKUs differ from the press by one copy each.** Both come from a run whose identifications name a position its table does not. The receipt names what actually went.

### What it costs

**2.8s per load** on the operator's store, against about 0.3s before. `Rows.where` is a full pass over the loaded table per call. The ledger makes about 1,100 calls. That is accepted for a screen that loads once and reloads on a press. A `sku` index over the loaded set is the fix. It is named below, not built here.

**`MAX_LEGS` is 16** on `POST /pipeline/emit`. The default landing can now load more runs than one press accepts. The operator has ten joinable runs. One press clears the old-cap leftovers, and the steady state is the runs of the last sitting or two. The bound is kept, not raised. It guards against a request nobody meant.

### What would reopen this

A marker that a copy reached an import file (D59, D147). The committed set would then be READ, and the ledger would stop inferring it. A `sku` index on `store/rows.py:Rows` for the 2.8s. A seventeenth open run. Realigning on the route, if the one-copy residual ever becomes a sentence somebody reads.

### Amendment, `D277`

The per-run box and run span on an ordinary row is hidden behind a per-table Compare toggle. A row whose copies are over the cap keeps its warning, whatever the toggle says. That is the "what cannot go is named on the deck, with a door for each" case, which stays named. The counts above do not change. The ledger, the figures and what the worklist offers are untouched. Only whether the per-row provenance text is always drawn has changed.
