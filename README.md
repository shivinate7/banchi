# BANCHI

Bulk-list pre-sorted Pokémon / One Piece / Riftbound TCG singles on TCGplayer with zero
attention per card, and know where every card physically is. Two tracks share one physical rig.

**Banchi** — 番地, a lot number, the address of a thing — is the app: every card in the store
has an address, box → section → card. The name is the front end's and nothing else's. The
repository, the CLI (`./pkmnscan`), the Python packages, the store on disk and every route on
the wire keep the names they have always had, and renaming any of them is a defect.

## Layout

```
CLAUDE.md                  always-on rules. Keep it short.
code-card-fork/CLAUDE.md   code-card track, auto-loaded in that directory
docs/map.py                the repo as data: built vs TBD, and what governs each file.
                           `make map` renders it; `make map ARGS=--stale` ranks the
                           entries whose file has outrun the prose about it.
docs/DECISIONS.md          settled decisions + rationale (read on demand)
docs/CODES-DECISIONS.md    same, for the codes track
docs/GATES.md              gates, harness contract, what shipped and what is open
docs/DESIGN.md             the Fulfillment view's hard constraints. Its token block
                           predates Banchi; app/src/tokens.css is the system now.
docs/specs/                interviewed specs, executed in a clean session
.claude/skills/            on-demand domain knowledge (TCGplayer CSV schema)
.claude/commands/          /docs-audit — prose vs code, proposes, never commits
.claude/settings.json      permissions + hooks
scripts/                   guard scripts, screenshot runner, docs-audit.py, status.py
fixtures/                  real TCGplayer exports — ground truth, never modified

pkmnscan                   the CLI. `./pkmnscan --help`
cli/                       argument parsing and sequencing. No rules live here.
pipeline/                  CSV, variant ladder, pricing, join, routing, decisions
identify/                  prompt, Batch API transport, sidecars, image prep
geometry/                  find the card in the frame; crop-retry bands
store/                     the master store: inventory, cache, standing queues, the order
                           ledger and the history — one SQLite file since D88
server/                    capture server: /capture, /status, /photo, inventory state,
                           and the pipeline seam — the one place a route can spend money
app/                       Banchi. Vite + React 19 + TS. Eleven screens — home, capture,
                           runs, review, pricing, orders, shipping, inventory, codes,
                           cards to pull, kit — all eleven routed. See "The app" below.
app/src/tokens.css         the design system: --bn-* tokens, light and dark
app/src/kit.css, kit/      the component kit every screen is built from
harness/                   T1-T9. The Stop hook runs `make harness` at every turn end.

runs/                      per-run inputs and outputs. Derived; safe to delete.
inventory/                 the master store on disk: store.sqlite, and legacy-json/ for
                           the JSON files it was migrated from. Real, local, never in git.
```

## Start

```
cd pkmnscan
make hooks
make status
claude
```

`make hooks` once per clone, and it is the one step here that cannot be automated away.
`core.hooksPath` lives in `.git/config`, which is never pushed — so a fresh clone carries
`scripts/githooks/pre-commit` as a tracked file with nothing pointing at it, and the opsec
rules it enforces are off. That failure is silent: nothing prints, nothing exits 1, and the
commit that leaks a live code looks like every commit before it. `make status` prints an
`Git hooks` line so an unarmed clone says so, rather than being found out by a leak.

`make status` first, especially after time away: it prints what has shipped and what is
open, the last T1 score and the branch — all read from the repo, none of it written
down anywhere a person has to remember to update. Stdlib only, so it works before
`make venv` and without an API key.

Requires `ANTHROPIC_API_KEY`, either exported in your shell profile or set in `.env`
(gitignored) — a real environment variable wins over `.env`. If `claude` is missing:
`npm install -g @anthropic-ai/claude-code`

**In a fresh git worktree, `make worktree-setup` FIRST.** The venv and T1's banked cache are
untracked, so neither travels, and skipping it fails three harness tests with errors that
never mention the worktree.

## The pipeline

Four commands, because a batch takes minutes to hours and the pricing decision needs a
human. One blocking command would put a person in the middle of a poll loop.

```
./pkmnscan scan       <capture-dir>                   code cards: read the QRs. FREE.
./pkmnscan identify   <capture-dir>                   submit, wait, collect. COSTS MONEY.
./pkmnscan join       <run-dir>                       resolve against the export. Free.
                        --dry-run  preview both queues, write nothing
                        --bypass   trust the finish claim over the photo (D3)
./pkmnscan emit       <run-dir> [<run-dir> ...]        write ONE import CSV. Free.
                        several runs -> ONE file, cap spent once across them (D86)
                        --listed-only  above-threshold rows only
                        --split-games  one file per game, if the portal refuses one
./pkmnscan prices     adopt [--write]                 fold the legacy per-run answers into
                                                      inventory/prices.json. Previews first.
./pkmnscan prices     show [--held]                   the corpus, and what is held back.
./pkmnscan reconcile  <run-dir> <staged-export.csv>   confirm what TCGplayer staged.
./pkmnscan reconcile  --live <my-pricing.csv>         the WHOLE store against one live
                        export, both directions. Previews; --write settles `live`.
```

`identify --dry-run` does everything except the API call, so a mistyped directory, a
malformed sidecar and an unreadable photo all surface for nothing. `join` and `emit` cost
nothing and are re-runnable, so fixing a review or changing a price is free.

**`join` has two flags worth knowing.** `--dry-run` walks the ladder twice — once trusting
the capture-time finish claim over a disagreeing photo and once not — diffs the two queues by
reason code, and returns before the first write. `--bypass` is the trusting half, kept for a
run rather than made a default: *where a finish claim exists, the photo may not contradict it,
though it may still choose inside a multi-finish one.* A card with no claim is untouched,
because there is nothing to resolve it by. It exists because box 2 measured detection wrong on
**42% of a box whose truth the owner confirmed** — see `docs/GATES.md` and D3.

**None of this needs a terminal.** `#/runs` is the pipeline on a screen: a free preflight that
prints the card count and the estimate, a two-step confirm before anything is spent, the three
free steps, every command's stdout shown verbatim, and the import CSVs as downloads. D33 is
the decision and D39 gave it the route.

**The pricing answer is not in the run directory.** `inventory/prices.json` holds every
listing answer for the whole store, keyed by SKU — a price, or a deliberate hold with its
reason — plus the standing rule and basis, and `#/pricing` is where a person writes one. A
run's `decisions.json` is a legacy file that `join` and `emit` refuse to read as a fallback;
`pkmnscan prices adopt` migrates it and previews first. D49 made the answer one file, D86 made
it one file for the store.

The master store lives in `inventory/`, overridable with `PKMNSCAN_HOME`. Deleting a run
directory costs nothing; deleting the store costs every answer you have paid for.

## The app

A browser front end over the capture server and nothing else: no pipeline logic, no second
store, no auth, no login. Two personas — the owner, who gets ten dense working screens, and
the Fulfiller, a retired non-technical relative who gets one big-type touch screen.

```
home           the product as a picture: the six-stage spine with a live figure under each
               stage, the boxes, the recent runs, and one action
capture        live camera, box / game / set hint / finish / rarity, undo, motion trigger
runs           the pipeline: preflight, the money gate, join / emit / reconcile, downloads
review         one card at a time, photo first — the answer writes and advances
pricing        the hand-pricing worklist across runs, one row per SKU, and D49's holds
orders         which copies this buyer gets and where they are, ranked by how many of them
               sit in one box, pulled one copy at a time
shipping       which envelope an order goes in, out of TCGplayer's own shipping export
inventory      the box walk, and everything that hangs off it: search, a card's copies
               and its sale, and the box's own operations
codes          the code-card track: read a box's QRs into the ledger, the two lanes the
               pile is tiered into, and a lane handed to a buyer against a named order
cards to pull  the Fulfiller's whole product: pull, photo-confirm, mark sold
kit            the component sheet, rendered by the build so it cannot go stale
```

**This list is counted off `app/src/App.tsx`'s `ROUTES` table and never incremented.** The
published screen count in this file, in CLAUDE.md and in `docs/map.py` was wrong seven times
with nothing reading it — five places at once, then a fenced list here missing two screens
that already existed, then `#/codes` reaching the table and neither. `make docs-audit`'s
`route census` row reconciles every one of them against that table now, and a route added
without recounting fails the commit.

**`#/orders` and `#/shipping` are two stages of one hub** — `Orders.tsx` exports it,
`Shipping.tsx` points the second route at it — and `#/inventory` is the one owner-side view of
stored cards, with the box walk as its spine and search narrowing it rather than replacing it
(D31; `#/boxes` and `#/pull` are gone and do not come back).

All eleven open at a hash, and the Fulfiller's view opens **without the shell** the other
ten carry — its row in `docs/DESIGN.md`'s constraints table requires no route out of it, and a
strip of links to the capture screen's hard-delete undo is exactly the route it forbids. Not
hidden: not rendered, so it is not focusable, not reachable by a screen reader, and not one
specificity change from coming back.

**The shell** is a sidebar that collapses to a 64px rail on wide windows, a top bar and a
bottom tab bar on phones with the rest behind a drawer, a command palette on ⌘K, `,` then a
letter to jump anywhere, ⌘← / ⌘→ to step the workflow ring, and a keyboard reference sheet on
`?` that lists every binding in the product. A screen crash is caught per route; the
Fulfiller's crash page has one button and no way out of his view.

**`make up` is how you run it.** It starts both servers detached, prints the link to bookmark,
and — the half worth having — **restarts the capture server by itself whenever you edit Python**
under `server/`, `store/`, `pipeline/`, `cli/`, `identify/` or `geometry/`. `docs/GATES.md`
records what that replaces: a run whose timestamps came from a server started before the fix
that was written for it. `make down` stops both; `make launch-agent` starts them at login, from
the main checkout only.

`make dev` and `make server` still run the two halves in the foreground, one terminal each, and
neither watches anything — use them when you want a server you are looking at. Running either
beside `make up` fails loudly rather than quietly moving to another port, because a server that
moved would be serving a **different** store (D43). `make screenshot` renders `scripts/views.txt`
into `captures/ui/`, and `make design-check` asserts `docs/DESIGN.md`'s Fulfillment floors in a
real browser.

**Gate B ran these screens on 2026-08-22** and most of the doubt about them is gone: the capture
screen drove a real feeder session, the review queue held 16 real entries and every one was
answered through the answer route, and the pull preview found a stored photo at its physical
location. Two things are still unexercised and `docs/specs/capture-app.md`'s STATUS section
names them — the Fulfillment view against a real order, and the review screen's price bands
against a mixed-value lot, that run having priced $0.04 to $0.40 end to end.

## The design system

Every color, size, radius, shadow and duration in the app is a `--bn-*` token in
`app/src/tokens.css`, and that is the only file in `app/` allowed to name a color.

- **Two themes, both real.** Light is the default; `:root[data-theme='dark']` redefines every
  surface and ink together. A stored choice is applied before first paint, otherwise the
  system's. A screen that has not been looked at in dark is not verified.
- **Three type roles.** Manrope for headings and big figures, Inter for everything, JetBrains
  Mono for machine strings only — SKUs, run names, reason codes, key caps.
- **One kit.** `app/src/kit/` and `app/src/kit.css` hold the buttons, pills, fields, panels,
  tables, notices, empty states, sheets, dialog boxes and toasts every screen is assembled from.
  `#/gallery` renders all of it, so it cannot go stale.
- **Verified at 1440, 820 and 390**, in both themes, with no horizontal page scroll at 390 and
  40px minimum touch targets on a coarse pointer.

The one part of the app the redesign did not touch is the Fulfiller's floors: 20px body, 32px
position labels, a 320px photograph, 44px targets, 7:1 contrast, no jargon, no route out.
Those serve a real person and `make design-check` asserts them in a browser.

## How this was built

The harness came before the features: T1–T4 existed and exited 1 before anything made them
pass, which is the whole point. It is nine tests now — the batch script added T5 (pricing) and
T6 (geometry), T7 reaches `store/`, `server/` and `cli/`, T8 is the code-card track, and T9 is
the first test here whose inputs are recordings of the rig rather than frames a test drew for
itself. Recount from `harness/run.py`'s `TESTS` list.

## For anything larger

Start minimal and let Claude interview you before it plans:

> I want to build [the capture app / the batch script]. Interview me in detail using the
> AskUserQuestion tool. Ask about edge cases, UI/UX, and tradeoffs — don't ask obvious
> questions. Keep going until we've covered everything, then write a spec to
> docs/specs/<name>.md.

Then `/clear` and execute the spec in a clean session.

## Fixtures

- `fixtures/sv09_export_untouched.csv` — real TCGplayer Filtered CSV export (SV09,
  341 rows). Schema truth for the catalog join.
- `fixtures/staged-import-accepted.csv` — 2-row import file that TCGplayer's Import to
  Staged accepted verbatim (Gate A). Byte-format ground truth.

Both are read-only, enforced by hook and by `.claude/settings.json` deny rules.
