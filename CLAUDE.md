# PKMNSCAN

Bulk-list pre-sorted Pokémon TCG singles on TCGplayer with zero attention per card and
physical location tracking. Two tracks share one rig: singles (this file) and code cards
(`code-card-fork/CLAUDE.md`, auto-loaded in that directory).

**Current gate: C.** Gate A passed 2026-07-26; Gate B passed 2026-08-22 with 53 real
cards end to end — the first numbers this project has about cards rather than about
itself are in that gate's section. Nothing on the deferred list, ever, until Gate C.
See @docs/GATES.md.

## Commands

```
make status         # where you are: next step, gate, T1 score, branch. Start here.
make harness        # all seven verification tests; the Stop hook runs it at turn end
make dev            # Vite app on :5173. Blocks — background it.
make server         # Python capture server on :8000. Blocks — background it.
make screenshot     # renders scripts/views.txt to captures/ui/. Needs `make dev` running.
make design-check   # DESIGN.md's Fulfillment floors, asserted in a browser
make lint           # eslint over app/: no facingMode, no split(","). JS only, no Python linter.
make check          # harness + docs-audit + lint + typecheck — no stubs left in it

./pkmnscan identify <capture-dir>   # submit, wait, collect, cache. COSTS MONEY. --dry-run first.
./pkmnscan join     <run-dir>       # resolve against the export. Free, re-runnable.
./pkmnscan emit     <run-dir>       # write import CSVs. Free, re-runnable.
./pkmnscan reconcile <run-dir> <staged-export.csv>
```

## Things you will get wrong without being told

- **Join key** = `zfill(3)(number) + "/" + printedTotal`. The shape is pokemontcg.io's
  schema (`printedTotal` is their field name), but at runtime both values come from the
  identification and match against the export's `Number` column — nothing in the pipeline
  calls that API. Never join on Product Name — it inconsistently embeds numbers.
- **Only two columns are ever written**: `Add to Quantity`, `TCG Marketplace Price`.
  `TCGplayer Id` is never modified. Everything else round-trips byte-identical.
- **Batch API, not sequential calls.** v1 claimed Batch and shipped real-time. Model:
  `claude-haiku-4-5-20251001`.
- **Real CSV libraries only** — PapaParse (JS), `csv` (Python). Never `split(",")`.
- **Not a Claude artifact**: no `window.storage`, no `localStorage`, no
  `facingMode: "environment"`. Inventory state is server-side JSON; camera uses a
  device picker. Two devices share one truth.
- **Never emit duplicate SKU rows** in an import file — undefined behavior. Aggregate
  by SKU with `Add to Quantity` = copy count, capped at 4 live.
- **The app has six screens and six routes** — five the owner's, one the Fulfiller's. The
  shell renders no nav over the Fulfiller's, because `docs/DESIGN.md`'s constraints table
  forbids any route *out* of it, and the owner's nav would fail four other rows of the same
  table on its own. Not-rendered rather than hidden: not focusable, not reachable by a screen
  reader, not one specificity change from coming back.

Deeper schema facts (Condition strings, secrets like `161/159`, blank-Number rows,
apostrophes in names) live in the `tcgplayer-csv` skill. It loads on demand.

## Hard rules

- Never guess an identification, a variant, or a price. Ambiguity goes to the review
  queue with its photo. Never silently drop a card.
- Never write output before reporting unmatched rows in both directions.
- No new surface area until the current gate passes.
- No manual third-party UI step inside the autonomous pipeline. External tools without
  an API contract can be benchmarks, never components.
- **Opsec, repo-wide**: a live unredeemed code card is a bearer instrument. No code-card
  photo in a listing, README, screenshot, or commit. Enforced by pre-commit hook.

## Working agreement

- Run `make harness` before you tell me something works. Show me the output, not a claim.
- Read @docs/DECISIONS.md before proposing an architecture change. Every entry there is
  settled; if you want to reopen one, say which entry and why, and wait for me.
- Report format: result first, then files touched, then risks. No task restatement, no
  summary of what I asked for.
- When compacting: preserve the fixture schema facts, every `make` command, the current
  gate, and the list of modified files. Drop exploration narration.

## Map

- `docs/map.py` — the repo as data: what is built, what is TBD, and which decisions govern
  each file. **Read this before editing anything under `app/`, `server/`, `pipeline/`,
  `identify/`, `store/`, `geometry/` or `cli/`** — every entry there is settled and
  re-litigating one wastes a session. Audited by `make docs-audit`, so it cannot quietly go
  stale: adding a file under any of those without an entry fails the commit.
- @docs/DECISIONS.md — settled decisions and why. Read before redesigning.
- @docs/GATES.md — gates, harness contract, build order.
- `docs/DEBTS.md` — known gaps in the verification tooling, deliberately unfixed. Read it
  before treating a green `make docs-audit` as coverage: it means the checks that exist,
  passed. Nothing in it blocks anything; it exists so no session rediscovers it by surprise.
- `docs/specs/batch-script.md` — the four commands, storage, routing, pricing. Built.
- `docs/specs/capture-app.md` — step 7. 7a (capture screen, undo, pull preview, one new
  server route) was built to it. 7b (review queue, Fulfillment view, inventory view,
  mark-sold, three more server routes) was built 2026-08-13 ahead of Gate B at the owner's
  explicit instruction; that schedule question is settled, and the spec's sections 0 and 9
  are marked overtaken rather than left reading as a prohibition over built code.
  **Gate B ran those screens on 2026-08-22 and most of the doubt is gone**: the capture
  screen drove a real feeder session, the review queue held 16 real entries and the owner
  answered every one, and the pull preview found a stored photo at its physical location.
  §10.2's measurements were taken and live in `docs/GATES.md`'s Gate B section.
  **Two things are still unexercised and its STATUS section names them**: the Fulfillment
  view against a real order, and the review screen's price-banded hierarchy against a
  mixed-value lot — that run's queue was uniformly sub-threshold, $0.04 to $0.40.
- @docs/DESIGN.md — design tokens and the Fulfillment view's hard constraints.
- `code-card-fork/CLAUDE.md` — the code-card track. Separate schema, separate channel.
- `fixtures/` — real TCGplayer exports. Ground truth. Never modify.
