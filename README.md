# PKMNSCAN

Bulk-list pre-sorted Pokémon TCG cards on TCGplayer with zero attention per card and
physical location tracking. Two tracks share one physical rig.

## Layout

```
CLAUDE.md                  always-on rules. Keep it short.
codes/CLAUDE.md            code-card track, auto-loaded in that directory
docs/DECISIONS.md          settled decisions + rationale (read on demand)
docs/CODES-DECISIONS.md    same, for the codes track
docs/GATES.md              gates, harness contract, build order
docs/DESIGN.md             design tokens, Fulfillment view constraints
.claude/skills/            on-demand domain knowledge (TCGplayer CSV schema)
.claude/settings.json      permissions + hooks
scripts/                   guard scripts, screenshot runner
fixtures/                  real TCGplayer exports — ground truth, never modified
```

## Start

```
cd pkmnscan
claude
```

Requires `ANTHROPIC_API_KEY` in your shell profile. If `claude` is missing:
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

## For anything larger

Start minimal and let Claude interview you before it plans:

> I want to build [the capture app / the batch script]. Interview me in detail using the
> AskUserQuestion tool. Ask about edge cases, UI/UX, and tradeoffs — don't ask obvious
> questions. Keep going until we've covered everything, then write a spec to
> docs/specs/<name>.md.

Then `/clear` and execute the spec in a clean session.

## iCloud

The project lives in iCloud Drive. The folder is pinned **Keep Downloaded**, which is what
makes git safe here — without it, macOS evicts cold files, and `.git` pack files are ideal
eviction candidates. Keep that pin on.

Pinning stops eviction, not upload. iCloud does not read `.gitignore`, so before build-order
step 8 brings in `node_modules` (tens of thousands of small files), exclude it from sync —
name it `node_modules.nosync` and symlink, or keep it outside the synced tree. The same
applies to `captures/` once it holds real card photos.

## Fixtures

- `fixtures/sv09_export_untouched.csv` — real TCGplayer Filtered CSV export (SV09,
  341 rows). Schema truth for the catalog join.
- `fixtures/staged-import-accepted.csv` — 2-row import file that TCGplayer's Import to
  Staged accepted verbatim (Gate A). Byte-format ground truth.

Both are read-only, enforced by hook and by `.claude/settings.json` deny rules.
