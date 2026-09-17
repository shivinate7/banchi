## 4 — Criteria and evidence: nine ways a row goes quiet

Recorded 2026-08-11. **One file (`scripts/docs-audit.py`) and one spec
(`docs/specs/criteria-binding.md`), so this parallelizes as a focused pass and not across
agents.** Re-checked 2026-08-30: `EVIDENCE_SOURCES` is still three bare literals nothing
resolves.

- **`criteria evidence` can go silent.** If the score file's `test` value stops matching the
  filename-derived key, the row compares nothing and still reports `gate field published`.
  Trigger is narrow — hand-editing `NAME` in `harness/tests/t1_id_eval.py` — but there is no
  ADVISORY downgrade for the "could not look" state. First thing to build in
  `docs/specs/criteria-binding.md`, because the threshold fix walks straight into it.
- **It never opens the value it names.** `holdout_accuracy: null` — a run that measured
  nothing — still reports `gate field published`.
- **`Pass:` matching is narrow and one-sided.** `startswith("Pass:")` misses `**Pass**:`, the
  spelling `docs/GATES.md` itself uses; absence is deliberately not a finding, so a bolded
  stale claim is exempt. Both comparison legs are containment, so `docs/GATES.md` may publish
  a *longer* threshold than the test enforces and stay green.
- **The number leg is substring containment.** `"0.9"` is contained in `"0.95"`, so a loosened
  threshold satisfies the check against an unchanged doc.
- **`EVIDENCE_SOURCES` is three unvalidated path literals.** Nothing resolves them, so renaming
  any of the three silently retires the `evidence freshness` row.
- **The evidence glob assumes one convention.** `t1*.json` — a score file named otherwise is
  invisible rather than a finding, while the summary claims coverage across all registered
  tests.
- **`harness/results/` filenames encode the hint mode but not the split**, so a tune-only run
  overwrites the committed holdout score.
- **A partial `make audit-history` replay exits 0** and silently deflates every per-check total,
  with no denominator on any row.
- **An empty requested split raises `ZeroDivisionError`** in `harness/tests/t1_id_eval.py`
  instead of reporting a clean failure.

### ~~Three more ways, found by a suite that could not miss~~ — CLOSED 2026-09-05

**Found by asking a re-proof what it had not covered, which is the only reason they were
found.** Fifty mutations were re-run against `1f2ab49` and every one still went red naming its
defect — a perfect score, and the completeness critic's own verdict on it was that *a suite that
never misses is not measuring detection, it is restating the implementation*. Each mutation had
been derived by reading the guard it tested, so each was that guard's own inverse. The three
below were then found by asking a different question: not *does the guard fire on the edit it
describes*, but *can the thing it pins be wrong while it says ok*. All three were reproduced by
hand before being believed.

- **`server concurrency` passed while both its constants were INVERTED.** The row read a figure
  out of `server/capture_server.py` and then asked only whether that number appeared anywhere in
  section 11 — `re.search(rf"\b{value}\b", section)`. Section 11 publishes about fifty-five
  distinct bare integers (every sweep column, every latency, every thread count), so almost any
  retune lands on one it already says for another reason. Measured: `CaptureHandler.timeout` set
  to 4 and `REQUEST_SLOTS` to 15 — swapped, the document wrong about both, the pool sized at the
  value §11 itself calls within noise of no bound at all — and the row reported `ok`. **Fixed by
  requiring the ATTRIBUTED form**: `_CONCURRENCY_FACTS` now carries a doc-side anchor per fact
  and compares the value the section attributes to that fact against the code's. It landed RED,
  because §11 had never stated `REQUEST_SLOTS = 4` in any attributable form at all — only as a
  bolded column heading in the sweep table — so the section gained the sentence it was missing.
  The swap now names both figures and both values.

- **`logo parity` did not read a third of the file it exists for.** Section 9's locked-set table
  names each mark's bracket as a WORD — `chrome`, `pale gold`, `rose` — and resolves it in a
  second table three lines below. The row compared `prism`, `ground` and `base` and skipped the
  word, so **24 of the 72 hexes in `app/src/kit/markPalettes.ts` were compared against nothing**
  — in the one file CLAUDE.md's color rule takes an exception for. Measured: changing bluesteel's
  `#B8C8D8` to `#B8C8D9` left `logo parity`, `raw color` AND `design tokens` all green, so an
  unapproved color could reach the app past every reader that rule has. Its docstring claimed the
  opposite in so many words. **Fixed by parsing the legend** (`_S9_BRACKET`) and resolving the
  name to its four stops; the row now reports 72 hexes and a bracket name section 9 fails to
  publish is a third kind of finding rather than a silent skip.

- **`detector standing` was green while section 6 contradicted itself.** The section states the
  corpus size twice and the decline count twice, eight lines apart, and `_DETECT_CLAIMS` pinned
  one copy of each. Measured: setting the twin to 1,620 against a guarded 1,625, and the heading
  to 61 frames against a guarded 59, left the row reporting `ok`. **A pinned figure with an
  unpinned twin is worse than no pin**, because it licenses the belief that the section is
  reconciled. Both twins are pinned now and the row reports 8 figures.

**What this says about the method, and it is the part worth keeping.** Mutation-proving a guard
with the mutation its own author wrote tells you the guard is wired up. It cannot tell you the
guard is asking the right question — for that the mutation has to come from somewhere else. Two
of these three were found by an adversarial pass whose whole brief was *what did this miss*, and
the third by that pass reading a check's docstring against what the check actually does.

---
