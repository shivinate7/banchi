# Banchi

Banchi (番地, "lot number") takes photos of trading cards you keep in boxes. It lists them on
TCGplayer, prices them, and tells you which box to open when one sells. It is for one seller
with sorted singles. [`pipeline/games.py`](pipeline/games.py) lists the games.

The first result: `make up` prints a link. Open it to see the app, where your boxes and cards show.

Status: working, built for one store. The code-card feature is dormant.

[Live demo](https://shivinate7.github.io/banchi/): the real app on recorded answers. It
reaches no real store ([`docs/specs/demo.md`](docs/specs/demo.md)).

## Quick start

You need `make`, `git`, and the Python and Node.js versions that CI pins in
[`check.yml`](.github/workflows/check.yml).

```sh
git clone https://github.com/shivinate7/banchi.git banchi
cd banchi
make hooks                  # arm the git hooks, once per clone
make venv                   # Python packages into .venv
npm --prefix app ci         # front-end packages
cp .env.example .env        # add ANTHROPIC_API_KEY
make up                     # serve the app; open the link it prints
```

[`check.yml`](.github/workflows/check.yml) shows what CI runs from these steps.

## Usage

`make up` serves the app. There is no login: it is for your own desk and network. `?` in the app lists the keyboard shortcuts (`SHORTCUTS` in
[`app/src/keys.ts`](app/src/keys.ts)).

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
| Codes | `#/codes` |  |
| Cards to pull | `#/fulfillment` | Off-nav |
| Kit | `#/gallery` | Off-nav |
| Product history | `#/product` | Off-nav |
| Runs | `#/runs` | Off-nav |
<!-- /gen -->

Each screen's spec is in [`docs/specs/`](docs/specs/). Every step also runs from the terminal.
`./banchi --help` lists the commands, and `<command> --help` lists its flags.
A command that writes shows a preview first; add `--write` to apply it. The command list in
[`CLAUDE.md`](CLAUDE.md) says which commands write.

```sh
./banchi identify --dry-run <capture-dir>   # check everything, spend nothing
./banchi identify <capture-dir>             # COSTS MONEY
./banchi join     <run-dir>
./banchi emit     <run-dir> [<run-dir> ...] # one import CSV across runs
```

**If you delete `inventory/`, you lose every answer you paid for.** Git does not track it.
`BANCHI_HOME` moves it.

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

[`check.yml`](.github/workflows/check.yml) shows what CI runs.

Main moves by pull request only (D42, main moves by pull request). `make docs-audit` checks
this file against the code: paths, make targets, commands, route table and decision ids.

The name Banchi belongs to the app. The checkout, CLI, packages, store and routes keep
`banchi` (D94, Banchi is the product's name).

## More

- [`CLAUDE.md`](CLAUDE.md): the rules agents work by, and the command list.
- [`docs/decisions/`](docs/decisions/): each settled decision. `make map ARGS=D<n>` prints one.
- [`docs/specs/`](docs/specs/): the spec for each feature.
- [`docs/DESIGN.md`](docs/DESIGN.md): the design tokens.
- [`docs/TESTS.md`](docs/TESTS.md): what each test protects.

## License

No license file. Default copyright applies.
