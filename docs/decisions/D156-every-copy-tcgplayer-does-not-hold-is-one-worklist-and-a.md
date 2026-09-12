## D156 — Every copy TCGplayer does not hold is one worklist, and a run stays open until the last of them has gone

**`#/pricing`'s default landing is every copy in every joined run that TCGplayer does not hold — across every run and every box — priced where prices are decided and sent by the one press that already writes one file across runs.** Built 2026-09-11, on the operator's report and their choice of shape.

Their words: *"how can i currently push more inventory of items that let's say were back in the capped system a while ago? I feel like there's no intuitive way currently to push more quantity, the only time it's intuitive to push supply is right when pricing a run, which shouldn't be the case"* — and, choosing between the shapes put to them: *"i need my runs more unified, so unsent copies worklist is the right direction."*

### What was structural about it

`emit` is run-scoped, and so was the only screen that reached it. `GET /pipeline/pricing` opened every run that still OWED something — `Decisions.blocking`'s two refusals, or never having emitted — and closed the rest. A run emitted under the old standing cap of four (D7, rewritten 2026-09-07) wrote `add 4 · backstock 3`, raised `pushed` to four, owed nothing, and closed with three copies still on the shelf. Nothing reopened it: the picker chip read *Answered*, the default landing left it out, and the three copies were reachable from no control in the product. **The moment a copy was held back on purpose was the moment it became unreachable.**

Opening the run by hand did not help either, and this is the half that made the first half invisible. The route merged rows off each run's `pricing.json`, a table `join` writes BEFORE the emit and `emit` never touches, so a re-opened run drew `4 of 7` for a card the press had already spent four of — the figure D86 recorded as *"reported here, corrected in `emit`"*. The screen said four, the press would have written three, and neither said the other was wrong.

### Measured, on the operator's store, 2026-09-11

Twelve joined runs, 2,535 cards, 492 listings. Two of the runs are over a drawer whose number was deleted and reused (D36) and are excluded by name.

| | under the old rule | now |
|---|---|---|
| runs on the default landing | 1 | **6** |
| unsent copies on it | 315 | **660** across 332 SKUs |
| runs closed while still holding unsent copies | **5**, holding **381** | 0 |
| SKUs whose every unsent copy was in a closed run | **91**, 262 copies | 0 |

Sixty of the 660 are under a deliberate hold (D49) and sink to the held tier as before; the press drops them by name. **The press's own plan over the same six runs — `merge.plan` off `resolve.load`, what `emit` writes — offers 600, and the route offers 600.** That agreement is the load-bearing fact of this entry and the harness case pins it: seven copies, a capped emit of four, the route says three, the next emit writes three.

The five runs the old rule had closed: `2026-08-24-box2-01` holding 148 unsent copies, `2026-09-01-box3-01` holding 150, `2026-09-11-box4-04` 47, `2026-09-11-box4-03` 32, `2026-08-31-box3-01` 4. Box 2 is the Pokemon bulk that was emitted once under the cap on 2026-08-24 and never looked at again.

### The four questions, answered

**Where it lives: `#/pricing`, and it is not a third door but the first one widened.** The operator's *"runs more unified"* is answered by a view that is not run-scoped at all, which is the opposite of putting it on `#/runs` — that screen is the run log and the money gate, and a run there is one box (D48). `#/inventory` is where cards ARE and never sends (D31). The ship bar, the cut-off, the cap field, the per-card quantity, the holds and the rule strip are all on `#/pricing`, and D105's rule decides it: a markdown lives where prices are decided, and so does a send. What changed is one word in the definition of *open* — a run is open while it owes something OR holds an unsent copy — and the default landing, which asks for the open runs, became the unsent worklist by that definition alone. `roster[].unsent` is the count; `owes` is untouched, so Home's *runs to price* still means what it meant.

**A row is a SKU, and its copies are on it.** The import file thinks in SKUs with a quantity (D7), and the row already draws every box a card sits in and the positions the photograph is addressed by. The Qty field's placeholder is the copies that can still go and its title says how many of the rest are already at TCGplayer. A per-copy row would draw seven rows for one line of the spreadsheet.

**It prices exactly as the screen always has, and invents nothing.** The corpus answers (D86) and the standing rule price every row; a hold sinks; a card with no market data and no answer is what `owes` already refuses the press for. A copy from a run joined three weeks ago carries that export's market price and says so — `read 3 weeks ago` on the row is the existing age, and *Join again* on `#/runs` is the existing refresh.

**What cannot go is named on the deck, with a door each.** `unreachable` on the wire: cards captured and never identified (214 on the operator's store), cards waiting in review (1), runs identified and never joined (2), runs over a reallocated drawer (2). Each is a link to the screen that moves it. A worklist that simply did not draw them would be the silent drop `CLAUDE.md` forbids, one register up — the operator counting a shelf against a screen and finding fewer.

### How the figure is live, and why it is not a third implementation

`server/pipeline_routes.py:_unsent_ledger` runs `cli/resolve.py`'s own functions over the store as it stands: `_live_by_sku` for each run's recorded export, newest reading per SKU (D87's rule); `_copies_out` for what TCGplayer holds; `_committed_keys` to spend that on positions, oldest capture first (D147); and the same set subtraction `SkuMatch.uncommitted_positions` makes. A copy in a terminal state is committed by the arm `load` uses for one. **This entry is built on top of D147 and not beside it**: the ledger reads the same `_committed_keys`, so its numbers were wrong until that ordering landed and are right by the same fix.

**A copy stamped since the join is counted, because the send counts it.** A review answer writes `sku` onto a record after `pricing.json` was written, and `load` adopts that identity on the next resolve; the ledger unions each SKU's table positions with every copy on hand carrying the SKU whose `run` is on screen, and the merged row draws those positions labelled off the live store. Measured: **74 copies** across the ten joinable runs were in no table and in the press.

**One `_copies_out` over the newest reading per SKU, where the send resolves one per leg.** That function walks every listing with two queries each — 0.9s per call on 492 listings — and ten legs put nine seconds in front of every reload. The one shape where the answers differ is two legs of one SKU whose OLDER export read higher than the newer, where `pipeline/merge.py:_merged_match` keeps the larger and calls that a stand-in in its own words; on a store that reconciles, the store's reading is newer than both files and the case does not arise.

**The key is read as stored and never realigned (D36)**, which is every other reader on this route's posture: `paperwork_for` hashes every photograph in a box to realign, and that is not a cost a reload may carry. The send realigns. **Measured residual: 2 of 332 SKUs differ from the press by one copy each**, both from a run whose identifications name a position its table does not — the receipt names what actually went.

### What it costs

**2.8s per load** on the operator's store, against ~0.3s before — `Rows.where` is a full pass over the loaded table per call and the ledger makes ~1,100 of them. Accepted for a screen that loads once and reloads on a press; a `sku` index over the loaded set is the fix and is named below rather than built here.

**`MAX_LEGS` is 16** on `POST /pipeline/emit`, and the default landing can now load more runs than one press accepts. The operator has ten joinable; one press clears the old-cap leftovers and the steady state is the runs of the last sitting or two. Named rather than raised: the bound is against a request nobody meant.

### What would reopen this

A marker that a copy reached an import file (D59, D147) — the committed set would then be READ and the ledger would stop inferring it. A `sku` index on `store/rows.py:Rows` — the 2.8s. A seventeenth open run. And realigning on the route, if the one-copy residual ever becomes a sentence somebody reads.
