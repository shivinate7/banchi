# PKMNSCAN

Bulk-list pre-sorted Pokémon TCG cards on TCGplayer with zero attention per card and
physical location tracking. Two tracks share one physical rig.

## Layout

```
CLAUDE.md                  always-on rules. Keep it short.
code-card-fork/CLAUDE.md   code-card track, auto-loaded in that directory
docs/map.py                the repo as data: built vs TBD, and what governs each file
docs/DECISIONS.md          settled decisions + rationale (read on demand)
docs/CODES-DECISIONS.md    same, for the codes track
docs/GATES.md              gates, harness contract, build order
docs/DESIGN.md             design tokens, Fulfillment view constraints
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
store/                     the master store: inventory, cache, standing queues
server/                    capture server: /capture, /status, /photo, inventory state,
                           and the pipeline seam — the one place a route can spend money
app/                       the web app. Vite + React + TS. Nine screens — capture, runs,
                           review queue, pricing, orders, shipping, inventory,
                           Fulfillment, component gallery — all nine routed. See "The
                           app" below.
harness/                   T1-T7. The Stop hook runs `make harness` at every turn end.

runs/                      per-run inputs and outputs. Derived; safe to delete.
inventory/                 the master store on disk. Real, local, never in git.
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

`make status` first, especially after time away: it prints the next build-order step, the
last T1 score and the branch — all read from the repo, none of it written
down anywhere a person has to remember to update. Stdlib only, so it works before
`make venv` and without an API key.

Requires `ANTHROPIC_API_KEY`, either exported in your shell profile or set in `.env`
(gitignored) — a real environment variable wins over `.env`. If `claude` is missing:
`npm install -g @anthropic-ai/claude-code`

## Session 1 — scaffolding

Run `/context` first and confirm CLAUDE.md loaded. Then, in plan mode:

> Read CLAUDE.md and docs/GATES.md. We are at build-order step 2. Build only
> the scaffolding: the Makefile with every command in CLAUDE.md wired up, the screenshot
> script, and a harness skeleton where all four tests exist and exit 1. No feature code.
> Show me the plan before writing anything.

The harness must exist and fail before anything makes it pass. That is the whole point.

## Session 2 — the harness

Fresh session, `/clear` first.

> Read docs/GATES.md. Implement harness tests T1–T4 to their stated pass thresholds.
> `make harness` must exit 0 only when all four pass. Commit the T1 accuracy score to
> harness/results/. Show me the output, not a summary.

The harness is seven tests now: batch script v2 added T5 (pricing) and T6 (geometry),
and T7 reaches `store/`, `server/` and `cli/` — the packages the first six never touched.

## The pipeline

Four commands, because a batch takes minutes to hours and the pricing decision needs a
human. One blocking command would put a person in the middle of a poll loop.

```
./pkmnscan identify   <capture-dir>                   submit, wait, collect. COSTS MONEY.
./pkmnscan join       <run-dir> --export <export.csv> resolve against the export. Free.
./pkmnscan emit       <run-dir>                       write import CSVs. Free.
./pkmnscan reconcile  <run-dir> <staged-export.csv>   confirm what TCGplayer staged.
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

**Since 2026-08-24 none of this needs a terminal.** `#/inventory` carries a folded Runs panel
over the same four commands: a free preflight that prints the card count and the estimate, a
two-step confirm before anything is spent, the three free steps, every command's stdout shown
verbatim, and the import CSVs as downloads. D33 is the decision; the panel is the answer to
the one thing Gate B could not close — *emit's import files existed only as filenames in
terminal output the owner never saw.*

Between `join` and `emit` you edit the run's `decisions.json`: what happens to sub-threshold
cards, and a price for anything the catalog has no price for. `emit` refuses to write until
both are answered — see D9. It is a file rather than a flag so the step 7 screen becomes an
editor for the same contract instead of a second code path.

The master store lives in `inventory/`, overridable with `PKMNSCAN_HOME`. Deleting a run
directory costs nothing; deleting the store costs every answer you have paid for.

## The app

Build-order step 7, both halves built 2026-08-13. It is a browser front end over the capture
server and nothing else: no pipeline logic, no second store, no auth, no login.

```
capture        live camera, box / game / set hint / finish / rarity, undo, motion trigger
runs           the pipeline: preflight, the money gate, join / emit / reconcile, downloads
review queue   one card at a time, photo first — the answer writes and advances
pricing        the hand-pricing worklist, one row per SKU, and D49's deliberate holds
orders         which copies this buyer gets and where they are, out of the order ledger
shipping       which envelope an order goes in, out of TCGplayer's own shipping export
inventory      the box walk, and everything that hangs off it: search, a card's copies
               and its sale, and the box's own operations
Fulfillment    the second persona's whole product: pull, photo-confirm, mark sold
gallery        step 6's component sheet, rendered by the build so it cannot go stale
```

**THIS LIST CARRIED FIVE ENTRIES AND WAS MISSING TWO SCREENS THAT ALREADY EXISTED**, `runs`
and `pricing`, from the days D39 and D49 routed them until D69 repaired it on 2026-08-30. It
is the sixth place this repo's screen count has been wrong, and CLAUDE.md's own warning —
that the count has been wrong more often than right and that nothing checks it — is what
found it. Restored first, then extended: nine entries, counted off `app/src/App.tsx`'s
`ROUTES` table rather than added to whatever the last number was.

**It was six until D31.** `#/boxes` and `#/pull` were separate routes over the same 767
records, and the owner named the problem: they read as three instances of one thing. They are
modes of `#/inventory` now — *"it's basically find a card in a box-based system if anything"*
— with the box walk as the spine and search narrowing it rather than replacing it.

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

All nine open at a hash, and the Fulfillment view opens **without the nav strip** the other
eight carry — that view's row in `docs/DESIGN.md`'s constraints table requires no route out of
it, and a strip of links to the capture screen's hard-delete undo is exactly the route it
forbids. `docs/map.py`'s `app/` entry is the current account of what each file does.

**They were built ahead of Gate B at the owner's explicit instruction**, against their own
spec's schedule — a question since settled rather than an outstanding deviation. What it
cost used to be that the screens displayed data no run had ever produced. **Gate B ran them
on 2026-08-22**: the capture screen drove a real feeder session, the review queue held 16
real entries and every one was answered through the answer route, and the pull preview (now
the inventory walk's card detail) found a stored photo at its physical location. Two things are still unexercised and
`docs/specs/capture-app.md`'s STATUS section names them — the Fulfillment view against a
real order, and the review screen's price bands against a mixed-value lot, that run having
priced $0.04 to $0.40 end to end.

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
