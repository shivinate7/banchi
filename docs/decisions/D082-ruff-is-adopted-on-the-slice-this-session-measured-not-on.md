## D82 — Ruff is adopted on the slice this session measured, not on what it enables by default

**Adopted 2026-09-01, closing the question `make lint` left open since it was narrowed to JavaScript.**
Python has no linter here. `docs/specs/audit-retirement.md` §9 already set the format for
answering that kind of question — run the tool on this repo, read the findings, then decide
— and this entry is that format applied to the one row that section left as "unmade."

**Zero-config `ruff check .` found 2,131 things on this tree, and 79% of it was one wrong assumption.**
1,051 `UP006`, 479 `UP045` and 148 `UP035` findings — 1,678 of 2,131 — are
pyupgrade rewriting `Dict`/`List`/`Optional[X]` to PEP 585/604 syntax. `requirements.txt`'s
zxing-cpp comment already says why that matters: this repo runs Python 3.9.6, pinned,
load-bearing. `X | None` outside a deferred annotation is a runtime `TypeError` on 3.9, and
ruff's own zero-config default assumes a newer interpreter — it marked most of those
rewrites "safe" until told otherwise. Telling it `target-version = "py39"` flips the split:
of 1,965 pyupgrade-family findings, safe-fixable drops from 1,798 to 264 and unsafe rises
from 169 to 1,701 — ruff itself stops trusting the rewrite once it knows the truth. The
codebase already defends itself here (57 of 63 files under the audited packages carry
`from __future__ import annotations`; the 6 that do not are empty `__init__.py` stubs), but
a bare `ruff check .` followed by `--fix` would have spent that discipline for nothing.

**The measured signal, once the version is told the truth, is pyflakes plus a validated slice of bugbear and flake8-simplify.**
Not ruff's ~900 default-enabled rules. Pyflakes and
basic pycodestyle (`E4`, `E7`, `E9`, `F`) came back with 29 findings, every one read by
hand: dead imports, extraneous `f""` prefixes, unused test-local variables, two ambiguous
`l` names, one `lambda`-assignment, and two `Optional`/`Tuple` names used in an annotation
without being imported — shielded from a live `NameError` by the same deferred-annotations
discipline above, but real hygiene gaps. Zero were false positives; zero were live bugs.
Bugbear plus flake8-simplify (`B`, `SIM`) came back with 39, and this is where the tool's
blind spots showed up before they shipped:

- `SIM115` flagged every `open()` this repo deliberately keeps past its own function's
  return — the `flock` handle a lock holds open for the caller's whole critical section
  (`store/files.py`), and the log handle handed to a detached `subprocess.Popen` that
  outlives the spawning function (`scripts/serve.py`, twice). The rule has no way to see
  either invariant; both are now a per-line `# noqa: SIM115` naming it.
- `B023` flagged a closure over a loop variable in a concurrency test
  (`harness/tests/t7_store_and_seams.py`) where the closure is started and joined within
  the same iteration, before the next one rebinds what it captured — bugbear's documented
  blind spot for a closure consumed synchronously rather than escaping the loop.
- `SIM118` is the one that actually broke something. It flagged six `for game in
  games.keys()` calls in `cli/resolve.py` as the dict idiom `key in dict.keys()`, and
  `games` there is the `pipeline.games` MODULE, not a dict — `keys()` is a real function
  it exports, unrelated to `dict.keys`. Applying the suggested rewrite (`for game in
  games`) parses fine and fails at runtime: `TypeError: 'module' object is not iterable`,
  three tests deep into `make harness` (T3, T4, T7), through `cli/cmd_join.py` ->
  `cli/resolve.py:games_claimed`. Ruff has no type information here — it pattern-matches
  the syntax `x in y.keys()` regardless of what `y` actually is. Caught by running the
  harness before calling the fix done, not by anything ruff itself could have said;
  reverted, and the six sites carry `# noqa: SIM118` naming the module.

**The ruling: `ruff.toml` pins `target-version = "py39"` and selects exactly `E4`, `E7`, `E9`, `F`, `B`, `SIM`.**
Never ruff's own defaults, and never `--fix` on this codebase without a
harness run after. `make lint` runs it alongside eslint, gated by the same shape of guard
`NPM_GUARD` already used (`RUFF_GUARD`, `requirements.txt`), so a missing dependency fails
loudly rather than letting `make check` go green having checked nothing. `--fix` is not
wired anywhere, matching D18: nothing that writes may run on the path that decides whether
a commit proceeds, and this repo has now measured, on its own tree, that an automated
rewrite here is not a decision to make blind.

**What this does not cover.** The other ~890 rule categories ruff enables by default —
everything outside pyflakes, bugbear and flake8-simplify — are unmeasured against this
repo and stay off. Widening the selection is a repeat of this same process: run it, read
every finding by hand, and record what is real before it gates anything.

---
