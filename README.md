# Banchi

Bulk-list pre-sorted TCG singles on TCGplayer with zero attention per card, and know
where every card physically is. The name is 番地, a lot number, an address for a thing.
Every card in the store gets one: box, section, card.

**Live demo:** https://shivinate7.github.io/banchi/ — a static build over recorded data.
No server, no login, nothing it does can reach a real store.

## How it works

1. **Capture** — a rig photographs each card as it comes off the sorting pile.
2. **Identify** — Claude Haiku vision reads the photos in batches and returns a name,
   set, and number for each card.
3. **Join** — those answers are matched against a TCGplayer Filtered CSV export, the
   catalog's own source of truth.
4. **Price** — a person decides each unsent card's price, or holds it back, once.
5. **Send** — one press writes the listing file TCGplayer's Import to Staged accepts.
6. **Fulfill** — orders come in, get pulled from the physical boxes, and ship.

## The screens

Fourteen screens — home, capture, review, pricing, orders, shipping, sales, inventory,
graveyard, codes, cards to pull, kit, product history, runs. All fourteen open at a hash,
all fourteen routed. Ten sit in the nav. Four are off-nav on purpose: reached by a deep
link, the command palette, or a redirect into another screen's own sheet (see
`app/src/App.tsx`'s `ROUTES` table).

The Fulfiller's view opens without the shell — the other thirteen carry it.

```
Home           what the store is waiting on, one action, the library as a picture
Capture        live camera capture, box and set setup, undo
Review         one card at a time, photo first, and the pipeline runs live here
Pricing        every unsent copy, one row per SKU, the rows that need a decision on top
Orders         every open order, grouped by buyer
Shipping       the shipping export, routed into lanes
Sales          gross-revenue retrospective — no fees, no cost basis, no profit
Inventory      the box walk: search, copies, box operations
Graveyard      every departed card, sold or retired — read-only
Codes          the code-card track (dormant, see below)
Cards to pull  the Fulfiller's whole product, no shell
Kit            the component sheet, from the command palette only
Product history one product's market history, opened by SKU
Runs           a link to Review's own runs sheet
```

## Quickstart

```
make hooks           # once per clone: arms the git hooks
make worktree-setup  # once per fresh worktree
make up              # the server, one process, one port
make harness         # the verification suite
make check           # harness plus every doc and guard audit
```

See `CLAUDE.md` for the full command list and every flag.

## Stack

A Python capture server, one SQLite store, and a Vite + React 19 + TypeScript front end.
No pipeline logic in the browser, no second store, no auth.

## Where to read more

| Topic | Where |
|---|---|
| Rules, commands, everything an agent needs | `CLAUDE.md` |
| The repo as data, what is built and what is open | `docs/map.py` (`make map`) |
| Settled decisions and why | `docs/decisions/` |
| Interviewed specs for larger builds | `docs/specs/` |
| Known gaps in the verification tooling | `docs/debts/` |
| The Fulfiller screen's hard constraints | `docs/DESIGN.md` |

## The name

Only the app is named Banchi. Everything beneath it — the checkout, the CLI, the Python
packages, the store on disk, every wire route — keeps its old name, `pkmnscan` (D94).

## Code cards

Code cards are a dormant feature. The rig, the ledger and the QR decode all work and stay
in the build, but the owner has not run this feature yet (see `CLAUDE.md`'s
"Code cards" section).
