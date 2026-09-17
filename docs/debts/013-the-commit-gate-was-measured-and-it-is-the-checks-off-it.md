## 13 — The commit gate was measured, and it is the checks OFF it that are worth knowing about

**Measured 2026-09-05 against `82bdb78`. Not a debt so much as the answer to one**, kept because
the question kept being asked and answered by inspection.

**The question.** A mutation re-proof had shown fifty guards going red under
`python3 scripts/docs-audit.py` — the whole-tree form, which is what `make check` runs. The
commit gate runs a different form: `scripts/githooks/pre-commit` calls
`python3 scripts/docs-audit.py --staged`, blocks on exit 1 and PRINTS-AND-ALLOWS on exit 2. In
staged mode every read, existence check and directory listing is redirected to the git INDEX. So
a guard can be perfectly live under `make check` and still stop nobody committing, and only one
of the fifty had ever been shown to block a real commit.

**The answer: 41 mutations, staged into the index, and NOT ONE was weaker under `--staged`.**
38 blocked the commit outright. Where the two forms differed at all, `--staged` was the STRICTER
one — `enter_staged_mode` redirects content, existence, listing and globbing together, and the
comment above it says why: mixing index content with worktree existence "audits a tree that will
never be committed". It holds under test. **The index-redirection layer is not where the holes
are.**

**And one commit was actually refused, which nothing had done before.** `PASS_CRITERIA` lowered
from `holdout_accuracy >= 0.95` to `>= 0.9`, staged, `git commit` attempted with the hooks armed:
`FAIL pass criteria`, exit 1, `COMMIT BLOCKED: the markdown disagrees with the code`, `HEAD`
unmoved. The money gate cannot be lowered past this hook by accident.

### The four that do not block, and why each is right

- **`UNPRICEABLE_REASONS <= ROUTING_REASONS`** (`pipeline/routing.py`) is a module-level `assert`.
  The commit path executes zero product code by construction — `docs-audit.py` reads Python as
  TEXT and AST and imports only stdlib, `sigil-check.py` imports four stdlib modules — so a
  runtime assert *cannot* gate a commit here. It gates the TURN instead: `make harness` will not
  even collect, so `make check` and the Stop hook catch it immediately and loudly.
- **`CAPTURE_CLAIM_FIELDS <= Card.__annotations__`** (`store/master.py`) is an import-time
  `RuntimeError`, same shape and same disposition. **§3 names this binder and reads as though the
  hop is closed; at commit time it is not**, and that implication is stated here rather than left
  to be rediscovered.
- **A failing `sigil-check.py --self-test` warns and allows**, which `scripts/githooks/pre-commit`
  argues in its own comment — *"a broken checker is not evidence that a screen is wrong, and
  blocking on one would make the bypass habitual"*, the same rule the auditor applies to exit 64.
  Checked rather than assumed: `make sigil-check` runs the self-test WITHOUT a `-` prefix, so a
  broken pattern fails `make check` and blocks the turn one gate later.
- **One roster entry was mis-paired**, not a guard that failed: `check_detector_standing` never
  opens `docs/DECISIONS.md`, and its docstring says D75's corpus is deliberately out of scope.

**Two corrections to the run that produced this, because a measurement is worth what its errors
are worth.** First, the earlier fifty-of-fifty included at least one verdict attributed to the
wrong guard: the subset `assert` never went red under the full audit either, so what that agent
watched fail was `reason emissions`, a different row. Second, the adversarial pass that reviewed
this run raised two further defects and NEITHER survived checking — it reported D75's 867-frame
figure as contradicting itself across files (all ten mentions agree, 867 photographs, three
boxes) and the sigil check's blocking half as vacuously green (it scans 62 files, finds nothing
because there is nothing to find, and two `sigil-ok` exemptions carry their reasons).

### What is genuinely open

**Eight rows are green over nothing when no markdown is staged.** `check_paths`,
`check_make_targets`, `check_pkmnscan_commands`, `check_harness_tests`, `check_decision_ids`,
`check_env_vars`, `check_doc_hygiene` and `check_positional_references` take the narrowed `docs`
list, and all eight read doc→code. Commit no markdown and they print `ok` over an empty subject —
`paths 0 references resolve` against 1,856 whole-tree, and the make-targets row 0 against 315. **The
narrowing is right** (a doc→code row has nothing to say about docs you did not touch) **and the
word `ok` is what is wrong with it**: a row that checked nothing reads exactly like a row that
checked everything and was satisfied. `check_pkmnscan_commands` already shows the way out — it
splits itself, using `docs` for "does this reference resolve" and `all_docs` for "is this
documented anywhere". Saying `0 of 1,856 in scope` instead of `ok` would cost nothing and is not
done here only because it touches eight rows and their published counts.


---
