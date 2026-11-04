---
paths:
  - "server/**"
---

# The capture server

- **The capture server is threaded. Restart it only after the owner says yes.** It is `class CaptureServer(ThreadingHTTPServer)` in
  `server/capture_server.py`, with `request_queue_size = 128` and `CaptureHandler.timeout = 15`.
  `REQUEST_SLOTS = 4` bounds executing requests. `PHOTO_SLOTS = 4` bounds `/photo/` and `/assets/`
  GETs and the cheap lock-free reads in `PHOTO_LANE_EXACT`, `/status` first (refusal `photo_busy`). The pool is safe over HTTP/1.1 only because every response sends
  `Connection: close` (DEBT11, a parked writer still holds a request slot). A burst of clients kills it. Run the full
  suite once, at the end. Ask the owner before `make up ARGS=--restart`, `make down` or `make up`, and name the reason.
  The `server concurrency` row of `make docs-audit` reads these figures.
- **A checkout claims its port slot once** (D43, the port follows the store). The slot lives in `~/.banchi/port-slots.json`
  (`scripts/port-slots.py`). A test run refuses a reused dev server that does not name this checkout
  (`app/checkoutIdentity.ts`, D261, a checkout claims its port slot). `make port-agreement` keeps `app/devPort.ts` and `server/ports.py` in step.
- **A sold card's photograph is reclaimed on purpose** (D89, reclaimed on purpose): `POST /boxes/<box>/photos/reclaim` deletes sold
  photographs and keeps every record.
- **The pipeline is reachable from a screen** (D33, reachable from a screen). It lives in Review's runs sheet. A run's scope is a selection
  (D180, a press names the cards): `pipeline/selection.py` is one grammar for the screen, the route and the CLI.
