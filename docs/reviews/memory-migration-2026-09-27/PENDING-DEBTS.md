# Pending debts, drafted from the memory migration, not yet numbered

Five findings below are DEBT-shaped. Each is a tool, environment or verification trap, still
true. None has a home in `docs/debts/` yet. `docs/debts/` has no merge-time claim mechanism
the way `docs/decisions/` does. `scripts/debts_corpus.py`'s own docstring says a new finding
gets the next free number by hand. Several PR 4B lanes are in flight on this integration
branch. Hand-picking the next free number here risks the same collision D-number entries once
hit, before D140. This file holds each entry fully drafted, ready to drop in.

**To land one:** copy its body into a new file in `docs/debts/`, at the next free number. Add
that filename to `docs/debts/ORDER.json`. Delete its section here. Run `make debts-selftest`.

---

## A — git and gh CLI traps hit from this checkout

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
merge` picks. That silently changes behaviour for every other session sharing this clone.
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

---

## B — Claude Code multi-agent and worktree session traps, working in this checkout

**The Browser pane does not repaint while hidden.** Anything reached by scrolling —
`scrollIntoView`, `window.scrollTo`, `computer{action:"scroll"}` — comes back as a blank
screenshot. The scroll action itself can time out, with "The Browser pane is currently
hidden." Fix: grow the viewport to hold the whole document, with `resize_window`. Do this
rather than scrolling to a target. Measure `document.documentElement.scrollHeight` first.

A `zoom` action with a `region` is not supported here. It returns the full screenshot instead.
Magnify the real element in place with `javascript_tool` instead.

Manual pixel coordinates sit in the screenshot's own frame. A `ref` click reports
full-resolution coordinates. Do not mix the two.

A theme cross-fade makes a mid-transition screenshot lie. A button renders as a solid block,
with no label. Wait 3-5s after any theme change. Set the theme through `localStorage`, then
reload. Writing `data-theme` directly leaves React's own state stale.

**Message a live peer session directly, when a change here affects another in-flight
branch.** Do not open with a PR comment. This machine runs one Claude session per worktree.
`ListAgents` plus `SendMessage` reaches a live peer in seconds. A PR comment waits for a
human. That human must read it, then relay it. It can land after the PR already merged. Fall
back to a PR comment only once no worktree holds that branch.

**`preview_start`, inside a worktree, can serve the MAIN checkout instead.** It runs the
launch command from the session's own launch directory. That is not the worktree the session
moved into. So `npm run dev --prefix app` can resolve `app/` against the main tree. It then
reads the main tree's own `vite.config.ts`. It binds the main checkout's own port. It serves
the main checkout's own source — silently.

The tell: `curl -s localhost:<port>/src/<a file you just edited>.ts | grep <your new
symbol>`. Zero means that the preview points at somebody else's checkout. Prefer `make dev`,
run over Bash from the actual worktree, when this matters.

A subagent's own `preview_start` can also return a server on the orchestrating session's own
checkout and port. It gets attributed to the agent's own session id. The result carries no
PID. So an agent cannot tell a fresh server from an inherited one. Brief a worktree agent to
use `make dev` over Bash instead. If it still ends up holding a wrong-tree `serverId`, have
it report the id, port and cwd. Never have it guess whether stopping the server is safe.

**Before reporting work destroyed, check for a branch holding it first.** A clean tree, after
a peer session moves `HEAD`, can mean two very different things. It can mean discarded work.
It can also mean work already committed, to a branch you do not stand on. On a machine
running many concurrent sessions, the second case is the ordinary one. Run `git branch -a
--contains <sha>`, or `git log --all --oneline -- <path>`, before telling anyone work was
lost.

**A command's byte count is not its token cost.** The Bash tool persists large output to a
file. It shows only a roughly 2 KB preview of the FIRST bytes. A 2.7 MB output and a 52 KB
output both persist the same way. Never infer a token cost from a byte count alone. Probe the
tool's real behaviour on a known size first. A verdict printed last, in a long run, costs an
extra turn to find.

**`scripts/janitor.py --confirm`'s liveness oracle is the home directory's own Claude
session registry, never "who stands in this tree."** A worktree made by hand, with `git worktree add`, registers nowhere.
A clean one reads as abandoned. This holds even while a builder works in it, uncommitted,
with its own servers and scratch renders. The janitor reaps it anyway. The branch itself
survives. The preview lists worktrees before branches. A `tail` on the preview hides exactly
that block. Never run `--confirm` while a hand-made worktree is in use. Read the whole
preview first. Prefer the Agent tool for worker worktrees, so they register.

**An isolated agent's own worktree can vanish out from under a resumed session.**
`isolation: 'worktree'` auto-cleans a tree the Agent tool judges unchanged. This can fire on
a RESUMED agent mid-run. It can fire on a builder that already pushed. It can fire on a
reviewer launched with no `isolation: 'worktree'` at all — which then runs, and edits, in the
orchestrator's own checkout. Once the tree is gone, `git` inside that path resolves to the
owner's primary checkout. A write from the "resumed" agent can land there. It can even switch
that checkout's own branch. A `git worktree add` recovery can itself be refused.
`guard-shell.py` resolves "this checkout" from the agent's own launch directory.

The fix that works: stand the dead agent down. Spawn a FRESH `isolation: 'worktree'` agent on
the pushed branch instead. Paste any needed measurement into its brief. Do not resume the old
one. Give every reviewer, not only every builder, `isolation: 'worktree'`.

**A subagent-model override, in `.claude/settings.local.json`, cannot clear from inside the
session that is running.** Claude Code holds the file in memory. It rewrites the file on
save. A Bash edit that removes `CLAUDE_CODE_SUBAGENT_MODEL`/`_FORCE` appears to work. The
keys then reappear, within the same call. The auto-mode classifier also refuses a direct
edit to that file, as self-modification. Ask the person to drop the keys instead. Or use
`PKMNSCAN_DOCS=off`, on the one commit that needs the `subagent override` row skipped. Never
try to clear the row from inside the session that set it.

**A session-level STE lint hook, on Write/Edit, lints the WHOLE resulting file, never the
text being inserted.** Say a governed file already carries error-severity findings anywhere
— `CLAUDE.md` is the case that happened. Then every Write/Edit against that file gets
refused. The refusal lists line numbers the edit never touched. That reads like a complaint
about the edit. It is not one. Lint the snippet standalone first, with `python3
scripts/ste/ste_lint.py <tmpfile>`. That confirms your own prose is clean. If the whole file
is not clean, ask first. Only route around the hook, with a Bash heredoc, inside a session
explicitly chartered to cure rot.

---

## C — a guard or probe can pass for the wrong reason

A catalogue of shapes. Each produced a confident wrong "green" in this repo. Kept together
because the failure mode repeats, across very different tools.

1. **The fixture never drew the control under test.** A case guarded on `if (await
   bar.count())`. The seeded store never loaded a run that would render the bar at all. The
   assertion inside never ran. The case still reported green.
2. **The probe only measured the fold.** `elementFromPoint` answers about the current
   viewport alone. A sweep that never scrolls tests only the first screenful, of a page that
   runs to 13,000px.
3. **The client under the assertion discards the evidence.** `http.client` already zeroes a
   HEAD response's read length, before a byte is read. So `checks.equal(body, b"")` passed
   against a server mutated to write a full body on HEAD. The library between the assertion
   and the wire answered the question by itself. Read raw bytes off the socket instead, when
   the assertion is genuinely about what went out on the wire.
4. **A restarting counter, or a hand-written literal in a fixture, survives the exact
   mutation an arm exists to catch.** Build a decoy in a regression arm with the SAME
   generating function the real code uses. Never a typed-in value.
5. **A per-run fixture races a MACHINE-WIDE resource it treats as private.** One example: a
   fixed process name, resolved through a global `pgrep -f`. Another: a "free" port, found by
   probing a range instead of binding port 0. On a machine running many concurrent
   worktrees, another session's identically-named process — or the same probed port — makes
   the guard correctly refuse. That reddens the one arm that must never fail. The fix makes
   collision impossible: a `<role>-<mktemp>-<pid>` name, a kernel-assigned port read back. It
   never adds a lock. Fixtures never "take turns" either — that would block one tree's suite
   on another's unrelated commit. `pgrep -fc` is not a count, on BSD. It returns 0 and reads
   as "no orphans." Count with `pgrep -f ... | wc -l` instead.
6. **A citation-checking probe that tokenizes the citation itself scores a hit off the
   subject's own filename.** A citation naming a pipeline module by path and line yields the
   token "join." That token then "verifies" against almost any line of that same module. Exclude every token derived
   from the subject's own path and stem, before matching. Count "names no real identifier" as
   NOT CHECKABLE, never as a pass. Measured here: 38% of one corpus's "hits" were this
   artifact alone.
7. **A Playwright geometry sweep, green locally and red on CI, is usually a sampling
   artifact.** It is rarely a real defect. Scan every whole-pixel scroll offset instead of
   reaching for CSS. Say it passes at most offsets, with one consecutive failing band. That
   means that a sticky or fixed ancestor covers the control. This happens at one exact scroll
   stop, on the runner's own font metrics. Passing at zero offsets is the real,
   scroll-invariant case. A sweep that steps in large viewport fractions can sample a long
   page at only two points. A wide failing band can then misread as a knife-edge flake. It is
   the opposite: more fragile, not less.
8. **Reading a retained Playwright trace by its request timeline alone upgrades a theory to
   an unearned certainty.** Decode the actual fulfilled response bodies first. They live in
   the trace's `test.trace` JSONL, as `before` events. Playwright's own array-failure output
   is a DIFF, never a positional list. A `-` line is expected-only. A `+` line is
   received-only. The two are aligned between each other. Three sessions here misread it as
   positional. Each chased a bug that did not exist.
9. **A test that mutates its own stub AFTER a `click()` races the browser.** `click()`
   resolves on dispatch. It never waits for the app's own re-read to complete. The shape only
   sometimes produces a wrong answer, so no static check can flag it. Move the mutation into
   the WRITE route's own handler instead. Order it after the row's fetch, before the re-read.
   Moving it earlier than the press breaks the case a different way. `await
   page.waitForTimeout(300)`, between the click and the mutation, turns a latent race into a
   deterministic red — for diagnosis only. Never commit it.
10. **Four mutation arms can all go green over one row, for three unrelated reasons at
    once.** It may be the walk's current row. Or this screen just sold it. Or the ranking is
    frozen by it. A case aimed at the fold or the freeze alone must act on a MID-list row.
    That row must be none of those three. Otherwise every arm proves the same easy reason,
    regardless of what the code under test does.
11. **A mutation run owns the whole working tree for its duration.** A `git stash`, even of
    an unrelated file, fired mid-run once. It let a background Playwright run restore a
    mutated file. That run then reported a false PASS — the same dev server serves the whole
    `app/src`. Never commit, stash, check out, or edit anything, while a mutation run is in
    flight.
12. **A dry-run guard, built from a deny-list of guessed endpoint names, fails OPEN.**
    Blocking POSTs by function names, read out of a bundle's JavaScript, let a real 100-row
    TCGplayer Staged import through. The real wire endpoint names matched no guessed name.
    The guard logged nothing. For any dry run against a live account: invert it. Block every
    non-GET by default. Allow only calls already observed and judged safe. Verify the guard
    actually fires, by driving one harmless write through it first.
13. **`make check` measured red at `reap-selftest`, on `origin/main` itself, on
    2026-09-12.** Standalone, the same target passed 31/31, on the same tree. Nobody
    re-verified this after that date. Before assuming a red `check` in this lane is your own
    fault, run the same target set on a detached checkout of `origin/main`. `check` stops at
    the first failure. `reap-selftest` sits 11th of the aggregate. A red there silently skips
    `lint`, `typecheck`, and everything after it.

---

## D — code-side mechanization left open after PR #379 / PR #380

`docs-audit` mechanizes claims written in markdown. Two rounds — PR #379, PR #380,
2026-09-17 — extended that to claims written in code. Four new `docs-audit` rows landed.
Route reachability landed. `make mutate-guards`/`make mutate-anchors` landed. Four items
stayed open, named in both PRs, and stay open as of this migration.

1. **Nothing reconciles the shell-clause NUMERAL in `CLAUDE.md`'s prose, against
   `scripts/guard-shell.py`'s own `CLAUSES` table.** The `env names` `docs-audit` row checks
   the escape-hatch NAMES, never the count. The Makefile has already once said "FIVE," while
   the guard carried eight.
2. **`reap-selftest.sh` has no arm that exercises an UNKNOWN verdict.** That is a real,
   untested branch, in the guard that decides whether to kill a process. It was found because
   a mutation introduced there SURVIVED, on the corpus's first run.
3. **`make mutate-guards` covers five guards, not the fourteen that carry a hand-written arm
   count in prose.** `make mutate-anchors` only proves the five it already has stay anchored.
   A reworded guard, among the other nine, can still drift silently.
4. **The Vite side of the `dist path agreement` `docs-audit` row is uncovered.** Closing it
   needs its own Node-side target. `docs-audit` itself sits on the commit path. It runs with
   a bare `python3`.

Also left open, from the same measurement sweep, never separately actioned: 73 `docs-audit`
rows carry no negative arm, meaning no fixture proven red. Six measured constants inside
code — store size and similar — drift against the real world. They never drift against the
tree. Nothing catches them going stale.

---

## E — `_copies_out` and `_committed_keys` cost a full-table pass per call

`cli/resolve.py:_copies_out` walks every listing — 492 on the owner's store. It runs
`positions_for_sku` plus `copies_not_sold`, per SKU. `store/rows.py:Rows.where` is a pass
over the whole loaded table, on every call. So one `_copies_out` costs roughly 0.9-1.2s. One
`_committed_keys` costs roughly 0.75s.

A route that calls either per-run, rather than once, adds real seconds to a reload. PR #284
(2026-09-11) hit this directly. A per-run call put 9.6s in front of every `#/pricing`
reload. Folding the readings newest-per-SKU, and calling once, brought that down to 2.8s.

Also still true: `pricing.json`'s `add_to_quantity`/`committed`/`listing` fields are the
JOIN's own snapshot, from whenever it last ran. `emit` never rewrites them. Any screen figure
claiming "what can still go out" must re-derive against the live store, on every read. Or it
lies, from the moment after the first `emit`.

**Not built:** a `sku` index on `Rows`. That index is the named fix for the underlying cost.
Until it lands, any new caller of `_copies_out`/`_committed_keys` must call it once per
request. It must run over the narrowed set of SKUs in hand, never inside a per-run loop.
