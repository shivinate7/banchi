# Identify

Prompt, Batch API transport, sidecars, image prep.

## Code files

- `identify/__init__.py` — Makes `identify` a package.
- `identify/batch.py` — Batch API submit/poll/collect.
  - Decisions: `D2`, `D23`, `D21`, `D319`
  - Tested by: `harness/tests/t1_id_eval.py`
- `identify/cost.py` — The price sheet, and the ONE place it is applied — the preflight's estimate before a send, the collect's record of what the send used, and server/pipeline_routes.py:_usage filling the figure in for a run written before the field existed.
  - Decisions: `D2`, `D33`
  - Tested by: `harness/tests/t7/emit_pricing.py`
- `identify/images.py` — Downscale, encode, hash a photograph for the API, and refuse a crop that is not the card.
  - Decisions: `D125`, `D23`, `D2`, `D75`
  - Tested by: `harness/tests/t6_geometry.py`
- `identify/match.py` — The free reader (D2, the owner picks the engine per run): a photograph and each stock photo become one `768`-number fingerprint (Marqo ecommerce-B's image tower, ONNX, on onnxruntime), and the nearest stock fingerprints are the candidates.
  - Decisions: `D319`, `D213`, `D2`, `D3`, `D76`, `D88`, `D170`, `D301`
- `identify/matchconst.py` — The few constants the background reader's watcher needs (served games, the model pin, the store's home), standard library only, because the watcher cannot import the `store` package (about `17` MB).
  - Decisions: `D2`, `D43`
- `identify/prompt.py` — The identification prompt and its fingerprint.
  - Decisions: `D23`, `D3`, `D22`, `D2`
  - Tested by: `harness/tests/t1_id_eval.py`
- `identify/sidecar.py` — Reading a capture directory: photos, JSON sidecars, position.
  - Decisions: `D3`, `D21`, `D23`, `D22`, `D2`, `D10`, `D183`
- `identify/sweep.py` — The background reader's watcher (`banchi match --sweep`): a small idle process on the standard library and sqlite only.
  - Decisions: `D1`, `D2`, `D76`, `D88`, `D170`, `D273`, `D305`
