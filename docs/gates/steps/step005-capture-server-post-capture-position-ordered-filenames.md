5. ~~Capture server: `POST /capture`, position-ordered filenames, JSON sidecars (position,
   box, set hint, variant), `/status`, `GET /photo/<box>/<position>`, `GET`/`PUT` inventory
   state shared across devices.~~ — done 2026-08-11, spec at `docs/specs/capture-server.md`.
   Positions are allocated inside the store lock by `allocate_capture`. **T7 reaches it as
   of 2026-08-13**: every route, every named refusal, and the sidecar seam read back through
   the reader `identify` uses. This line said the opposite for two days — the step shipped
   with nothing under `harness/tests` importing `server`, `store` or `cli` — and the claim
   outlived the gap it described. What T7 still does not assert is in `docs/DEBTS.md`, and
   is now three named cases rather than a whole package.
   The server has grown well past the five routes this line was written about: `DELETE
   /inventory/<box>/<index>` arrived with step 7a's undo; `GET /queues`, `POST
   /review/<box>/<index>/answer` and `POST /inventory/<box>/<index>/sold` with 7b; and
   `GET /search`, `GET /boxes`, `POST /boxes` and `PUT /boxes/<box>` with the order flow.
   Each came with its own T7 cases on the day it landed. **The count is deliberately not
   published here.** It said "nine" while the server served thirteen, and it was restated in
   three files at once — a verifiable fact with nothing in it a later session could disagree
   with, which by D18's test means it is not load-bearing prose and should not be maintained.
   `server/capture_server.py`'s own header is the register.