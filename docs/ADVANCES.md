# Proposed build directions

**Nothing in this file is a decision.** Each entry below is a candidate a review turned up on
2026-08-31 — one pass over the runs flow specifically (join logic, the pipeline API, the
`#/runs` screen), a second pass over the whole codebase's language and tooling choices.
Adopting one is a `docs/DECISIONS.md` entry with its own number, the way every other piece of
scope in this repo gets argued in first. This file is where a candidate waits until that
happens, or until someone reads it and says no.

**Grouped by what it would cost to act on, not by where it was found.** The first group is
cheap and local — a session could take one row and be done in an hour. The second needs a
decision before a line of code changes, because the fix touches more than the file it was
found in. The third is the negative space: options the review considered and argued against,
kept here so a later session does not re-propose them without re-deriving why they lost.

## 1 — Correctness risks, cheap and near-term

Each of these is a single finding in a single file. None needs a decision entry to fix; each
needs someone to pick it up.

- **`pipeline/join.py:1344-1356`** (`Catalog.candidates`) — set-hint narrowing returns the
  hint-matched candidate set as resolved without checking it collapsed to exactly one `Set
  Name`. A genuinely ambiguous multi-set collision inside the hinted set would silently skip
  the `SET_AMBIGUOUS` routing D76 exists to guarantee.
- **`pipeline/join.py:1192-1195`** (`_blank_number_by_name`) — the blank-Number index used for
  `pokemon_code`'s `name_only` matching is unfolded, unlike the folded D35 name index at
  `join.py:1189-1191`. A case or whitespace mismatch here produces a silent `no_catalog_row`
  with no fallback, the same failure shape D35 was written to close off everywhere else.
- **`server/pipeline_routes.py:2455-2497`**, calling into `:2297` — `do_pipeline_scope` reads
  and parses the identifications file twice inside one GET. The module's own docstring at
  `:2227-2230` says data is "lifted rather than recomputed"; this route does not follow its
  own rule.
- **`app/src/RunPanel.tsx:684-693`** vs **`:698-722`** — `detail` (run name, counts, console,
  the bypass-claim banner) clears only when `openRun` becomes `null`, never when it changes to
  a *different* run. Clicking another row can leave the previous run's numbers on screen,
  under a newly-highlighted row, until the next poll resolves — on the one screen where
  misreading which run's numbers you are looking at can spend money.
- **`app/src/RunPanel.tsx:873-888`** and **`app/src/BoxBrowse.tsx:1379`** — two independent
  global `window`-level arrow-key listeners, each guarded against form-field focus and neither
  guarded against a screen reader's browse-mode navigation. Same defect, found twice, which
  makes it a pattern rather than an oversight in one file.
- **`aria-live` appears zero times in `app/src`.** The equivalent implicit-live-region pattern
  (`role="alert"` / `role="status"`) is real and used deliberately in four files — `Codes.tsx`,
  `ReviewQueue.tsx` (twice, with an inline comment arguing the alert-vs-status choice),
  `CaptureScreen.tsx`, `ServerReloaded.tsx` — and never reached `RunPanel.tsx`'s comparable
  `-note` banners, which are visually identical to `ReviewQueue.tsx`'s.

## 2 — Structural directions, need a decision first

These cross more than one file or change a convention this repo has followed without
examining, so a fix here is scope, not a bug row.

**`server/capture_server.py` is 8,829 lines.** That is larger than `pipeline/join.py` (2,263)
and `server/pipeline_routes.py` (2,821) combined, and neither of those — already known as this
repo's god-files — was the largest backend file. No split is proposed here; the entry exists
so the next session that goes looking for the largest file in the backend does not have to
`wc -l` the whole tree to find it.

**Four frontend screens fuse data-fetching with rendering.** `CaptureScreen.tsx` (3,779
lines), `ReviewQueue.tsx` (3,475), `BoxBrowse.tsx` (3,155), `RunPanel.tsx` (2,311) each mix
polling, derived state, and JSX in one file. `app/src/server.ts` already centralizes every
`fetch` call in the app except these four files' direct calls — the seam that is missing is
between "fetch, poll, derive" and "render," not between the app and its API. The direction
this points to is a custom hook per screen (`useRunPanelData`, `useReviewQueueData`, and so
on), leaving the component file holding only JSX. Not proposed: a state-management library —
see §3.

**String-keyed `getattr`/`setattr` on dataclass fields bypasses whatever typing the dataclasses
provide.** `store/master.py:584,594-595,662-673,729` and `server/capture_server.py:2606-2609,
2813-2820,3491,6289` drive stage-counter manipulation off string constants
(`LISTING_STAGES`, `CLAIM_WIRE_NAMES`) via `getattr(card, field)` / `setattr(entry, stage, ...)`.
A typo'd field name is a silent no-op or a runtime `AttributeError`, and nothing in this repo's
toolchain would catch it before that happens, because of the next item.

**No `mypy` config exists anywhere in the repo, and unlike the absent Python linter — an
argued decision at `Makefile:450` — the absence of a type checker is not argued anywhere; it
is simply never mentioned.** Spot-checked type-hint coverage across ten files runs 60-100%
already (`store/orders.py` 27/27, `pipeline/join.py` 81/93, `server/capture_server.py`
119/142), so the marginal cost of adopting mypy is turning existing hints into a gate, not
writing new ones. This is the one item in this file with a plausible cheap first step:
`mypy --strict` on a single already-well-typed module (`store/orders.py` or `codes/qr.py`)
before deciding whether to widen it.

## 3 — Considered, not recommended

Kept so the reasoning survives, not just the conclusion.

- **A router library.** Routing is ~10 stable hash routes, already covered end to end by
  `app/tests/nav.spec.ts` and `app/tests/cursor.spec.ts`. The hand-rolled hash parser in
  `App.tsx` is small, has not drifted, and D51's Cmd-arrow behavior is built directly on top
  of it — a router migration would be a rewrite of working, tested surface for no defect it
  fixes.
- **A state-management library** (Redux, Zustand, React Query). 250 `useState` calls across
  `app/src` sound worse than they are, because `server.ts` already gives the app one seam for
  every network call. The actual gap identified in §2 is fetch/poll/derive fused with render
  inside four files — a library would not close that gap, a hook per screen would.
- **A component library or CSS framework.** Styling is already token-based and consistent
  (D50), spread across 26 CSS files with no drift found in this review. There is no evidence
  of the inconsistency a component library exists to solve.
