# Banchi

Photograph a box of trading cards (Pokemon, One Piece, Riftbound). Banchi (番地, "lot number")
lists them on TCGplayer, prices them, and tells you which drawer to open when one sells.

[Live demo](https://shivinate7.github.io/banchi/): the real app on recorded answers from a
scrubbed copy of a store. It reaches no real store, and CI checks the published build for
secrets ([`docs/specs/demo.md`](docs/specs/demo.md)).

## The flow

| Stage | What it does | Powered by |
|---|---|---|
| Capture | A browser camera photographs each card into a box and section. | [`docs/specs/capture-app.md`](docs/specs/capture-app.md) |
| Identify | Claude Haiku reads every photo in one Message Batches call. The only step that spends money, and the app asks first. | [`identify/batch.py`](identify/batch.py) |
| Join | Each card resolves to one SKU against the pokemontcg.io catalog and your TCGplayer export. Doubtful cards wait for you, photo first. | [`pipeline/join.py`](pipeline/join.py), [`pipeline/catalog.py`](pipeline/catalog.py) |
| Price | One pricing answer per SKU for the whole store, a market reading, and a price-history archive. | [`pipeline/corpus.py`](pipeline/corpus.py), [`pipeline/readings.py`](pipeline/readings.py), [`pipeline/pricearchive.py`](pipeline/pricearchive.py) |
| Send | One press reads what is live, trims doubles, pushes to staged, then makes it live. Every send leaves a receipt. | [`server/send_routes.py`](server/send_routes.py), [`server/tcg_import.py`](server/tcg_import.py) |
| Reprice | Finds live listings that are not selling and re-prices them in bulk. | [`pipeline/reprice.py`](pipeline/reprice.py) |
| Sell | Fetches your orders from TCGplayer. Sales shows gross revenue by month. | [`server/order_transport.py`](server/order_transport.py) |
| Pick | Ticked orders become the fewest drawers to open, and each copy shows where it sits. | [`pipeline/walkplan.py`](pipeline/walkplan.py) |
| Ship | The shipping export splits into envelope and parcel lanes, with a Pirate Ship import sheet. | [`pipeline/shipping.py`](pipeline/shipping.py), [`pipeline/pirateship.py`](pipeline/pirateship.py) |

The store is one SQLite file, `inventory/store.sqlite`. Capture and paid work are separate
phases. Cost per card:
[Gate C](docs/gates/gate-runs/GateC-note1-the-per-run-reading-900-against-1200-priced-and-powered.md).

### TCGplayer, live

Set `TCGPLAYER_STORE_COOKIE` in `.env` (see `.env.example`). It is a secret. Git ignores the
file, and the app never logs it or writes it into a run. With it, Banchi:

- pulls your live pricing export ([`server/tcg_export.py`](server/tcg_export.py));
- fetches your orders;
- pushes imports to staged and moves them live.

Without it, every step still works through file download and upload. Other outbound calls:
Anthropic (identify), pokemontcg.io (catalog), tcgcsv.com and TCGplayer's price-history
endpoint (market history).

## Quick start

Needs a Mac, Python 3.12 on the PATH, Node.js 22, `make` and `git`.

```sh
git clone https://github.com/shivinate7/banchi.git pkmnscan
cd pkmnscan
make hooks                  # arm the git hooks, once per clone
make venv                   # Python packages into .venv
npm --prefix app ci         # front-end packages
cp .env.example .env        # add ANTHROPIC_API_KEY; the file explains each key
make up                     # serve the app; open the link it prints
```

Run `make hooks`. Without it, a commit can leak a live code card. `make status` shows the
state of the hooks, the branch and the next step.

## Use it

`make up` starts one server. It serves the API and the built app on one port. There is no
login: it is for your own desk and network. Every route is in `app/src/App.tsx`'s `ROUTES`.

| Screen | Route | What it does |
|---|---|---|
| Home | `#/` | Ranks what the store waits on and states the top item in one sentence, with one action. |
| Capture | `#/capture` | In auto mode, fires the shutter when a card settles in frame. Keeps setup across browser resets. Undoes per sitting. `S` cuts a section as the card enters the box. |
| Review | `#/review` | Shows one card at a time, photo first. Prices the Identify run before it spends. "Check first" opens a composer that picks which cards to identify before anything is spent. |
| Pricing | `#/pricing` | Merges every unsent copy into one worklist keyed by SKU, rows that need you on top, and one Send bar. A Live tab re-prices stale listings and never deletes one to do it. |
| Orders | `#/orders` | Groups open orders by buyer. Solves the pick list as the fewest drawers to open across the ticked orders, and holds that order still while positions refresh. |
| Shipping | `#/shipping` | Routes each order to an envelope or a tracked parcel, by value and by contents. |
| Sales | `#/revenue` | Shows a verdict, a month strip and a search by card name. Gross only, canceled excluded. |
| Inventory | `#/inventory` | Addresses each card by box, section and position. A card's number counts the cards in the box, not the slots. A search keeps its order while you sell. Sold cards stay hidden. Box operations sit in one sheet. |
| Graveyard | `#/graveyard` | Lists every card that left, with its old address and photo. Read-only. |
| Codes | `#/codes` | Reads code-card QRs into a ledger. A QR that does not decode stops the line. Dormant. |
| Cards to pull | `#/fulfillment` | The Fulfiller's own screen: large type, no shell, one button on a crash. Off-nav. |
| Kit | `#/gallery` | Renders the design system from the build, in light and dark. Off-nav, from the command palette. |
| Product history | `#/product` | Draws one product's market history beside your own sales of it. Off-nav, deep-linked by SKU. |
| Runs | `#/runs` | Off-nav. A link into Review's runs sheet. |

`⌘K` opens the command palette. `?` lists the shortcuts. 

Every step also runs from the terminal. `./pkmnscan --help` lists the commands. Commands
that write show a preview first. Add `--write` to apply.

```sh
./pkmnscan identify --dry-run <capture-dir>   # check everything, spend nothing
./pkmnscan identify <capture-dir>             # COSTS MONEY
./pkmnscan join     <run-dir>
./pkmnscan emit     <run-dir> [<run-dir> ...] # one import CSV across runs
./pkmnscan archive  sweep                     # price-history archive, previews first
./pkmnscan reprice  list <my-pricing.csv>     # live listings that are not selling
```

**If you delete `inventory/`, you lose every answer you paid for.** Git does not track it.
`PKMNSCAN_HOME` moves it.

## Development

Stack: Vite, React 19, TypeScript over a threaded Python capture server. No pipeline logic
in the browser. Map of the code: `make map`.

```sh
make worktree-setup   # first, in a new git worktree: venv, cache, own ports (D43)
make dev              # Vite with hot reload beside `make up`
make harness          # the ten verification tests
make ci-check         # what a fresh clone can prove. Runs in CI.
make check            # everything the hooks and CI enforce
```

Main moves by pull request only (D42). `make merge ARGS=<n>` previews a merge.

The name Banchi belongs to the app. The packages, CLI, store and wire keep `pkmnscan`
(D94, the name stops at the app).

## Proof

- **Guards run on every commit and in CI** through `make docs-audit`: the docs against the code,
  design tokens, route rosters, decision ids, and opsec rules for code-card photos.
- **Tests:** [`docs/TESTS.md`](docs/TESTS.md) says what each test protects.
- **Gates:** [`docs/GATES.md`](docs/GATES.md) records the runs on real cards.

## More

- [`CLAUDE.md`](CLAUDE.md): the full command list and the working rules.
- [`docs/decisions/`](docs/decisions/): each settled decision. `make map ARGS=D<n>` prints one.
- [`docs/specs/`](docs/specs/): the spec for each feature.
- [`docs/DESIGN.md`](docs/DESIGN.md): the design tokens, and the limits on the Fulfiller's screen.

No license file: default copyright applies.
