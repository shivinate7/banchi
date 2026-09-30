## 31 — The path guard never reads code, so a decision cited by path in a comment goes unchecked

`check_paths` (the `paths` row) is called only with markdown files. A decision cited by its filename in a code comment, as in `store/numbers.py` and `store/orders.py`, is never resolved, and a mistyped one is invisible. `decision ids in code` resolves a bare `D<n>` in `.py`, `.ts`, `.tsx`, `.css` and `.js`, and never reads the path around it. A dead path citation once shipped this way: a comment in `scripts/docs-audit.py` cited a decision file without its slug.

**Outcome at risk.** A dead path citation ships unnoticed.

**Closes when.** The remaining path citations in code become id citations (cite by id, never by path), and the `paths` row, or a sibling row, opens the file types that can carry one.
