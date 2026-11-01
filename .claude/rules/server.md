---
paths:
  - "server/**"
---

# The capture server

- **The capture server is threaded.** It is `class CaptureServer(ThreadingHTTPServer)` in
  `server/capture_server.py`, with `request_queue_size = 128` and `CaptureHandler.timeout = 15`.
  `REQUEST_SLOTS = 4` bounds executing requests. `PHOTO_SLOTS = 4` bounds `/photo/` and `/assets/`
  GETs and the cheap lock-free reads in `PHOTO_LANE_EXACT`, `/status` first (refusal `photo_busy`). The pool is safe over HTTP/1.1 only because every response sends
  `Connection: close` (DEBT11, a parked writer still holds a request slot). A burst of clients kills it. Run the full
  suite once, at the end.
  The `server concurrency` row of `make docs-audit` reads these figures.
