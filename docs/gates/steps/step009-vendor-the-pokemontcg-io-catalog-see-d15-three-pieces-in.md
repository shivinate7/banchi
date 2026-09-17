9. **Vendor the pokemontcg.io catalog** — see D15. Three pieces, in order, and it stays in
    this list because the third is not done:

    - **BUILT.** Snapshot `PokemonTCG/pokemon-tcg-data` into the repo, at
      `vendor/pokemon-tcg-data/` — 176 files (`cards/en/*.json` + `sets/en.json`),
      26,520,219 bytes, upstream commit `8b4e387930ead7be6595b4d4c59b7ba7a3a79f08`, recorded
      in `SNAPSHOT.json`. `make catalog-refresh` (`scripts/catalog-refresh.py`) is the target
      that re-clones and refreshes it. Narrower than the whole upstream tree on purpose —
      `decks/` and the v1-conversion script are not vendored, because nothing downstream of
      this step reads a decklist. The "183 files, 27.4 MB" figure above this line was this
      step's own estimate of the whole upstream tree, written before the fetch; the number
      moved because the tree grew and because this snapshot deliberately copies a narrower
      slice of it.
    - **BUILT.** The SQLite index — `vendor/pokemon-tcg-data/catalog.sqlite`, built by
      `make catalog-index` (`scripts/catalog-index.py`). Cards join to sets by *filename* —
      `printedTotal` is only in `sets/en.json`, and it is half the join key. Measured: 174
      sets, 20,444 cards, zero card files naming a set absent from `sets/en.json`. Guarded
      red-first by `make catalog-index-selftest`, against a throwaway two-set fixture rather
      than the real snapshot. `pipeline/catalog.py` is the read-only reader; nothing in
      `pipeline/join.py` calls it, and the runtime join's matching is unchanged — see the
      decision entry below for why wiring it into a screen is a separate, unbuilt task (D46).
    - **RECORDED, NOT FILLED.** The image mirror from `images.pokemontcg.io`:
      `scripts/catalog-image-mirror.py` builds the manifest from the vendored snapshot (no
      network) and implements a rate-limited, resumable, per-file-skip downloader.
      Destination is overridable by `PKMNSCAN_IMAGE_MIRROR` (D15); unset, it defaults to
      `harness/images/`. **Only `--dry-run` has ever run on this checkout**: 20,444 files,
      ~14.18 GB extrapolated from a 200-image HEAD sample (2026-09-13) — the same order of
      magnitude as D15's own ~16.7 GB estimate from a 197-image sample. `harness/images/` is
      untouched. Filling ~14-17 GB for real is the owner's disk to spend and nothing here
      reaches for it automatically.

    Deliberately after Gate B: no production code reads this data. `harness/eval/fixtures.py`
    is the only consumer, step 4's batch script does not depend on it, and a warm harness run
    already makes zero network calls. **Retiring the retry/backoff scaffolding in that file
    was NOT done this pass** — it is T1's own live-fetch fallback, D112-shaped (a banked
    `manifest.json`, a `scorer_fingerprint()`, a HOLDOUT/TUNE split hashed per card id), and
    swapping its source needs its own measurement that the vendored 150-card selection matches
    what was banked, or the fingerprint check silently starts comparing against a different
    population. Left open rather than done quietly; see
    D206.
