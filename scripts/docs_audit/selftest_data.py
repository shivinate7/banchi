"""Fixture lines the path-extractor self-test cases read."""

from __future__ import annotations

# ------------------------------------------------------------------------- self-test

# Every string here is real prose from this repo's markdown that a naive path extractor
# eats. The check that this audit is not vacuously green.
NON_PATHS = [
    "secret rares where the number exceeds the denominator (`161/159`)",
    "Modern era only (SWSH/SV), English, all Near Mint",
    "T1's key misses (`051/197` for `031/197`, `271/167` for `211/167`)",
    "Resolve normal / reverse holo / holo per card, in order:",
    '`zfill(3)(number) + "/" + printedTotal`, built from pokemontcg.io data',
    "a committed snapshot of the maintainer's own `PokemonTCG/pokemon-tcg-data` repo",
    "Claude Code is available at claude.ai/code in the browser",
    "`printedTotal` lives only in `sets/en.json`",
    "One file per run: `t1-<UTC date>.json`, carrying the overall accuracy",
    "The capture server serves stored photos at `GET /photo/<box>/<position>`",
    # THE ROUTES WHOSE FIRST SEGMENT IS A REAL PACKAGE, which is the case the placeholder
    # rule above cannot save because there is no placeholder in them. `POST
    # /pipeline/identify` was read as the file `pipeline/identify` and blocked a commit on
    # 2026-08-24 for describing a route correctly; `_ROUTE` is what fixed it, and these are
    # the lines that keep it fixed. Both directions matter: a route is dropped, and the
    # module of the same name in ordinary prose is still found (see REAL_PATHS).
    "- **One route spends and is named for it** — `POST /pipeline/identify`. It refuses",
    "`GET /pipeline/runs/<name>/file` — one artefact's bytes, for download",
    "`GET /pipeline/pricing` — one worklist over several runs",
    "`DELETE /inventory/<box>/<index>` — D10's hard delete of a record",
    # THE SAME ROUTES AS CODE SPELLS THEM, 2026-09-12: a quoted string beginning with a
    # slash, in a fenced block that mirrors the dispatcher. `_QUOTED_ROUTE` is what drops
    # them; the module of the same name unquoted is still found (REAL_PATHS below).
    'if path == "/pipeline/value":',
    "  return (await request(`/pipeline/value?${query.toString()}`, NO_CACHE)) as ValuePage",
    "  page.route('/pipeline/pricing', handler)",
    "Refill on later imports as `Add to Quantity = min(cap - live, backstock)`",
    "The repo sits under `~/Library/Mobile Documents/com~apple~CloudDocs/`",
    "Free at https://dev.pokemontcg.io and sent to api.pokemontcg.io only",
]

# The `@` of a Claude Code import is part of the extracted token; resolve_candidate strips
# it. Kept that way so a finding quotes the doc as written rather than a normalised form.
REAL_PATHS = [
    ("see @docs/DESIGN.md before proposing", "@docs/DESIGN.md"),
    ("`harness/run.py` holds the registry", "harness/run.py"),
    ("Enforced by `scripts/githooks/pre-commit`.", "scripts/githooks/pre-commit"),
    ("`fixtures/sv09_export_untouched.csv` — real export", "fixtures/sv09_export_untouched.csv"),
    ("permissions live in `.claude/settings.json`", ".claude/settings.json"),
    ("Rationale: @../docs/specs/code-cards.md", "@../docs/specs/code-cards.md"),
    ("`docs/specs/batch-script.md` — the four commands", "docs/specs/batch-script.md"),
    # THE OTHER HALF OF THE ROUTE RULE. `_ROUTE` drops a slash-path only when an HTTP method
    # stands in front of it, and this is what proves the rule stayed narrow: the same
    # package name in ordinary prose, and even a route path mentioned WITHOUT its method,
    # are still extracted and still checked.
    ("the seam lives in `server/pipeline_routes.py` and refuses", "server/pipeline_routes.py"),
    ("read `pipeline/games.py` for which strategy a game uses", "pipeline/games.py"),
]
