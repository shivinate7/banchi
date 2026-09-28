## DEBT-git-and-gh-cli-traps — git and gh CLI traps hit from this checkout

Drafted from the 2026-09-27 memory migration. Each trap below was hit for real, on this
machine, in this checkout, and cost a session real time before it was named.

**`git push` fails with HTTP 400 on a pack over 1 MiB, from this Mac.** Apple Git 2.39.3
switches to chunked transfer encoding past `http.postBuffer`'s 1 MiB default. Something on the
network path rejects it: `send-pack: unexpected disconnect`. The pack uploads in full first,
then the 400 lands. That reads like corruption. It is not. `git ls-remote origin` coming back
empty is the tell that nothing landed. Fix: `git config http.postBuffer 524288000`, before
pushing any repo of real size on this machine. It is a per-repo setting. A fresh clone needs
it again.

**`gh api <path> -f key=value` is not a read.** Any `-f`/`-F` field makes `gh` default the
method to POST, silently. On this Mac, a POST to an endpoint that answers no POST does not
error fast. It hangs past a 120s tool timeout. It leaves a background process to reap. That
reads as a network problem. It is a malformed request. Fix: put query parameters in the path,
as a query string — `gh api 'repos/{owner}/{repo}/commits/<sha>/check-runs?per_page=100'` —
or pass `--method GET` explicitly.

**`gh pr list --author '@me'` returns other sessions' PRs.** Every session on this machine
commits as the same git user. Every session authenticates as the same GitHub account. `@me`
filters nothing useful here. Identify a session's own PR by branch name instead.

**Never leave `main` checked out in a worktree.** It changes which local-half command `make
merge` picks. That silently changes behavior for every other session sharing this clone.
Branch off `main` at once if a `git checkout` lands there.

**A hand-resolved merge conflict needs the full `make docs-audit`, never a syntax check.** A
splice recipe — take main's side, append only the branch's new lines — is correct for one
shape only: a pure addition of new, disjoint lines. It breaks two other ways.

First: a JSON array can miss a trailing comma after a hand-spliced append.
`docs/decisions/ORDER.json`'s last entry has none. `git checkout --theirs` on that file whole
is usually the safer move.

Second: a REWRITE, not an addition, produces a silent duplicate. Both sides can independently
reword one shared paragraph. The splice then keeps both full paragraphs. That is
syntactically fine. It is semantically wrong. Each paragraph reads correctly alone. A visual
check misses it. Only the full `make docs-audit` caught it here, at once. The `check census`
row found it. A targeted grep alone would not have. Neither would `ast.parse` alone.

Before trusting a splice on any conflict: ask whether the two sides say the same thing, in
different words. Ask this rather than assuming new, disjoint content. For a rewrite, find the
real canonical source. A live `Makefile` target list is one example. Write one correct
version from it. Discard both stale copies.

**Batching several reviewed PRs into one integration PR** hit three traps. `push-every-pass`
and `integration-merge-check-cadence` extend the practice. These traps still apply to it.

- Two branches can each independently claim the same `## D<n>`. Un-claim both back to `##
  D-<slug>` first. One claim at merge then numbers everything.
- Three branches can append a test at the same point in one spec file. A three-way merge's
  own brace-matching will not survive that. Rebuild the file from the base branch instead,
  plus each branch's pure appends.
- A `docs/map.py` `governed_by` list conflict keeps both sides' decision slugs. It never picks
  one side.
