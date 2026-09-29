# Banchi

Photograph a box of trading cards. Get a TCGplayer import file back. Know where every card is.

Banchi is a one-seller tool for a TCGplayer store (Pokemon, One Piece, Riftbound).
It is the working tool of one seller. No card needs more than a photo from a person. Banchi
(番地) means lot number. Each card has an address: box, section, position. When an order
arrives, Banchi says which box to open and where the card sits.

[Live demo](https://shivinate7.github.io/banchi/): the real app on recorded answers from a
scrubbed copy of a store. It reaches no real store.

## How it works

Capture, then identify, join, review and price, emit, reconcile.

1. **Capture.** A browser screen and camera photograph each card. Offline and cheap.
2. **Identify.** Claude Haiku reads the photos in one Batch API call (D2). This is the only
   step that spends money, and the app asks first.
3. **Join.** Each card resolves to one SKU against your TCGplayer Filtered Export.
4. **Review and price.** You see only the cards the join could not settle.
5. **Emit.** One import CSV for TCGplayer's Import to Staged.
6. **Reconcile.** Banchi reads what TCGplayer staged and records what is live.

Capture and paid work are separate phases (D1, two-phase architecture). The store is one
SQLite file, `inventory/store.sqlite` (D88). Cost per card: see
[Gate C](docs/gates/gate-runs/GateC-note1-the-per-run-reading-900-against-1200-priced-and-powered.md).

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

| Screen | Route | What it is for |
|---|---|---|
| Home | `#/` | What the store waits on, in one sentence, and one action |
| Capture | `#/capture` | The live camera, the pile's claims, undo and the motion trigger |
| Review | `#/review` | One card at a time, photo first. Starts the identify run |
| Pricing | `#/pricing` | Every unsent copy, one row for each SKU, with holds |
| Orders | `#/orders` | Open orders by buyer, and the walk to each copy |
| Shipping | `#/shipping` | TCGplayer's shipping export, sorted into envelopes |
| Sales | `#/revenue` | Gross revenue by month, and search by card name |
| Inventory | `#/inventory` | The box walk: search, copies and box operations |
| Graveyard | `#/graveyard` | Every card that left a box. Read-only. |
| Codes | `#/codes` | Code cards: the QR ledger and the hand-off (dormant) |
| Cards to pull | `#/fulfillment` | The Fulfiller's screen, no shell. Off-nav. |
| Kit | `#/gallery` | The design system, rendered. Off-nav, from the command palette. |
| Product history | `#/product` | One product's market history and your sales of it. Off-nav, deep-linked by SKU. |
| Runs | `#/runs` | Off-nav. A link into Review's runs sheet. |

`⌘K` opens the command palette. `?` lists the shortcuts.

Every step also runs from the terminal. `./pkmnscan --help` lists the commands. Commands
that write show a preview first. Add `--write` to apply.

```sh
./pkmnscan identify --dry-run <capture-dir>   # check everything, spend nothing
./pkmnscan identify <capture-dir>             # COSTS MONEY
./pkmnscan join     <run-dir>
./pkmnscan emit     <run-dir> [<run-dir> ...] # one import CSV across runs
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

- **Gates A, B and C passed** in July and August 2026. Gate B ran 53 real cards end to end.
  Records: [`docs/GATES.md`](docs/GATES.md).
- **Guards run on every commit** through `make docs-audit`: the docs against the code,
  design tokens, route rosters, decision ids, and opsec rules for code-card photos.
- **Tests:** [`docs/TESTS.md`](docs/TESTS.md) says what each test protects.

## More

- [`CLAUDE.md`](CLAUDE.md): the full command list and the working rules.
- [`docs/decisions/`](docs/decisions/): each settled decision. `make map ARGS=D<n>` prints one.
- [`docs/specs/`](docs/specs/): the spec for each feature.
- [`docs/DESIGN.md`](docs/DESIGN.md): the limits on the Fulfiller's screen.

No license file: default copyright applies.
