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
server/                    capture server: /capture, /status, /photo, inventory state
app/                       the web app. Vite + React + TS. One component so far.
harness/                   T1-T6. The Stop hook runs `make harness` at every turn end.

runs/                      per-run inputs and outputs. Derived; safe to delete.
inventory/                 the master store on disk. Real, local, never in git.
```

## Start

```
cd pkmnscan
make status
claude
```

`make status` first, especially after time away: it prints the next build-order step, the
open gate, the last T1 score and the branch — all read from the repo, none of it written
down anywhere a person has to remember to update. Stdlib only, so it works before
`make venv` and without an API key.

Requires `ANTHROPIC_API_KEY`, either exported in your shell profile or set in `.env`
(gitignored) — a real environment variable wins over `.env`. If `claude` is missing:
`npm install -g @anthropic-ai/claude-code`

## Session 1 — scaffolding

Run `/context` first and confirm CLAUDE.md loaded. Then, in plan mode:

> Read CLAUDE.md and docs/GATES.md. We are pre-Gate-B, at build-order step 2. Build only
> the scaffolding: the Makefile with every command in CLAUDE.md wired up, the screenshot
> script, and a harness skeleton where all four tests exist and exit 1. No feature code.
> Show me the plan before writing anything.

The harness must exist and fail before anything makes it pass. That is the whole point.

## Session 2 — the harness

Fresh session, `/clear` first.

> Read docs/GATES.md. Implement harness tests T1–T4 to their stated pass thresholds.
> `make harness` must exit 0 only when all four pass. Commit the T1 accuracy score to
> harness/results/. Show me the output, not a summary.

The harness is six tests now: batch script v2 added T5 (pricing) and T6 (geometry).

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

Between `join` and `emit` you edit the run's `decisions.json`: what happens to sub-threshold
cards, and a price for anything the catalog has no price for. `emit` refuses to write until
both are answered — see D9. It is a file rather than a flag so the step 7 screen becomes an
editor for the same contract instead of a second code path.

The master store lives in `inventory/`, overridable with `PKMNSCAN_HOME`. Deleting a run
directory costs nothing; deleting the store costs every answer you have paid for.

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
