# Banchi

Banchi (番地, "lot number") takes photos of trading cards you keep in boxes. It lists them on
TCGplayer, prices them, and tells you which box to open when one sells. It is for one seller
with sorted singles: Pokemon, One Piece and Riftbound.

The first result: `make up` prints a link. Open it to see the app, where your boxes and cards show.

Status: working, built for one store. The code-card feature is dormant.

[Live demo](https://shivinate7.github.io/banchi/): the real app on recorded answers. It
reaches no real store ([`docs/specs/demo.md`](docs/specs/demo.md)).

## Quick start

You need Python 3.12, Node.js 22, `make` and `git`.

```sh
git clone https://github.com/shivinate7/banchi.git pkmnscan
cd pkmnscan
make hooks                  # arm the git hooks, once per clone
make venv                   # Python packages into .venv
npm --prefix app ci         # front-end packages
cp .env.example .env        # add ANTHROPIC_API_KEY
make up                     # serve the app; open the link it prints
```

CI runs the installs, with `pip install -r requirements.txt` for `make venv`, and runs
`npm --prefix app ci`. It does not run `make hooks` (it arms a local clone), `make up` (it
needs a free port) or `cp .env.example .env` (it needs your key).

## Usage

`make up` serves the app and its API on one port. There is no login: it is for your own desk
and network. `?` in the app lists the keyboard shortcuts.

<!-- gen:routes -->
| Screen | Route | Note |
|---|---|---|
| Home | `#/` |  |
| Capture | `#/capture` |  |
| Review | `#/review` |  |
| Pricing | `#/pricing` |  |
| Orders | `#/orders` |  |
| Shipping | `#/shipping` |  |
| Sales | `#/revenue` |  |
| Inventory | `#/inventory` |  |
| Graveyard | `#/graveyard` |  |
| Codes | `#/codes` |  |
| Cards to pull | `#/fulfillment` | Off-nav |
| Kit | `#/gallery` | Off-nav |
| Product history | `#/product` | Off-nav |
| Runs | `#/runs` | Off-nav |
<!-- /gen -->

Each screen's spec is in [`docs/specs/`](docs/specs/). Every step also runs from the terminal.
`./pkmnscan --help` lists the commands. A command that writes shows a preview first, and you
add `--write` to apply it.

```sh
./pkmnscan identify --dry-run <capture-dir>   # check everything, spend nothing
./pkmnscan identify <capture-dir>             # COSTS MONEY
./pkmnscan join     <run-dir>
./pkmnscan emit     <run-dir> [<run-dir> ...] # one import CSV across runs
```

**If you delete `inventory/`, you lose every answer you paid for.** Git does not track it.
`PKMNSCAN_HOME` moves it.

## Configuration

[`.env.example`](.env.example) lists each key and says which are required. Without a TCGplayer
cookie, every step still works through file download and upload.

## Development

```sh
make worktree-setup   # first, in a new git worktree: venv, cache, own ports
make dev              # Vite with hot reload, beside `make up`
make harness          # the verification tests
make ci-check         # what a fresh clone can prove
make check            # the whole suite; `make explain` lists it
```

CI runs `make harness` and `make ci-check`, and a browser run of `make design-check`. It does
not run `make worktree-setup` or `make dev`, which need your machine, or `make check`: CI runs
`make ci-check` in its place.

Main moves by pull request only (D42, main moves by pull request). `make docs-audit` checks
this file against the code: paths, make targets, commands, route table and decision ids.

The name Banchi belongs to the app. The checkout, CLI, packages, store and routes keep
`pkmnscan` (D94, Banchi is the product's name).

## More

- [`CLAUDE.md`](CLAUDE.md): the rules agents work by, and the command list.
- [`docs/decisions/`](docs/decisions/): each settled decision. `make map ARGS=D<n>` prints one.
- [`docs/specs/`](docs/specs/): the spec for each feature.
- [`docs/DESIGN.md`](docs/DESIGN.md): the design tokens.
- [`docs/TESTS.md`](docs/TESTS.md): what each test protects.

## License

No license file. Default copyright applies.
