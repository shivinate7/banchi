# Identify

Prompt, Batch API transport, sidecars, image prep.

## Code files

- `identify/__init__.py` — Makes `identify` a package.
- `identify/batch.py` — Batch API submit/poll/collect.
  - Decisions: `D2`, `D23`, `D21`, `D319`
- `identify/cost.py` — The price sheet, and the ONE place it is applied — the preflight's estimate before a send, the collect's record of what the send used, and server/pipeline_routes.py:_usage filling the figure in for a run written before the field existed.
- `identify/images.py` — Downscale, encode, hash a photograph for the API, and refuse a crop that is not the card.
  - Decisions: `D125`, `D23`
- `identify/match.py` — The free reader (D2, the owner picks the engine per run): a photograph and each stock photo become one `768`-number fingerprint (Marqo ecommerce-B's image tower, ONNX, on onnxruntime), and the nearest stock fingerprints are the candidates.
  - Decisions: `D319`, `D213`
- `identify/matchconst.py` — The few constants the background reader's watcher needs (served games, the model pin, the store's home), standard library only, because the watcher cannot import the `store` package (about `17` MB).
- `identify/prompt.py` — The identification prompt and its fingerprint.
  - Decisions: `D23`, `D3`, `D22`
- `identify/sidecar.py` — Reading a capture directory: photos, JSON sidecars, position.
  - Decisions: `D3`, `D21`, `D23`, `D22`
- `identify/sweep.py` — The background reader's watcher (`banchi match --sweep`): a small idle process on the standard library and sqlite only.
