## DEBT55 — the audit self-test crashes when app/node_modules is missing

**Symptom.** `make audit-self-test` in a tree with no `app/node_modules` ends in
`KeyError: 'Two.tsx'` and a Python traceback, where it should report the toolchain as unknown.

**Measured.** Reproduced in a fresh worktree of the branch that fixed the two `docs-audit`
rows for a missing toolchain. Running `make worktree-setup` there, which installs
`app/node_modules`, turned the same target green ("self-test clean").

**Cause.** The self-test's fixture section calls `_run_user_strings` over a throwaway tree.
That call returns None when `node` or `app/node_modules/typescript` is absent. The
self-test's `ok(...)` for that call records the failure and carries on. Later lines index the
result by fixture file name and raise on the empty answer.

**Same class as the fix that left it.** A read that could not run is unknown, never broken.
The two live `docs-audit` rows now say so. The self-test does not. It was left alone
deliberately, so that branch stayed to the rows and the provisioning path.
