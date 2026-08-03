# PKMNSCAN

Bulk-list pre-sorted Pokémon TCG singles on TCGplayer with zero attention per card and
physical location tracking. Two tracks share one rig: singles (this file) and code cards
(`codes/CLAUDE.md`, auto-loaded in that directory).

**Current gate: B.** Gate A passed 2026-07-26. Nothing on the deferred list, ever, until
Gate C. See @docs/GATES.md.

## Commands

<!-- FILL THESE IN AS THEY EXIST. An empty command block is the #1 CLAUDE.md failure. -->

```
make harness        # all four verification tests; MUST exit 0 before any commit
make dev            # Vite app on :5173
make server         # Python capture server on :8000
make screenshot     # renders key views to captures/ui/ for visual review
make check          # harness + lint + typecheck
```

## Things you will get wrong without being told

- **Join key** = `zfill(3)(number) + "/" + printedTotal`, built from pokemontcg.io data.
  Never join on Product Name — it inconsistently embeds numbers.
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

- @docs/DECISIONS.md — settled decisions and why. Read before redesigning.
- @docs/GATES.md — gates, harness contract, build order.
- @docs/DESIGN.md — design tokens and the Fulfillment view's hard constraints.
- `codes/CLAUDE.md` — the code-card track. Separate schema, separate channel.
- `fixtures/` — real TCGplayer exports. Ground truth. Never modify.
