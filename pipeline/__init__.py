"""Pipeline logic under test by the harness.

Pure functions over data — no network, no Batch API, no filesystem beyond explicit paths.
Build-order step 5's batch script wires the Anthropic Batch API on top of this; the
harness (T2-T4) exercises it directly. Keeping it here rather than inside harness/ is
deliberate: the harness tests the pipeline, so the pipeline cannot live inside the
harness.

  tcgcsv   read/write TCGplayer Filtered CSV, byte format preserved
  variant  the D3 variant-resolution ladder
  pricing  D9 threshold and floor
  join     catalog join, SKU aggregation, bidirectional unmatched reporting
"""
