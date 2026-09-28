## DEBT-multi-agent-worktree-traps — Claude Code multi-agent and worktree session traps

Drafted from the 2026-09-27 memory migration. Working in this checkout, with multiple
concurrent sessions and worktrees, hit each trap below for real.

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
session registry, never "who stands in this tree."** A worktree made by hand, with `git
worktree add`, registers nowhere. A clean one reads as abandoned. This holds even while a
builder works in it, uncommitted, with its own servers and scratch renders. The janitor reaps
it anyway. The branch itself survives. The preview lists worktrees before branches. A `tail`
on the preview hides exactly that block. Never run `--confirm` while a hand-made worktree is
in use. Read the whole preview first. Prefer the Agent tool for worker worktrees, so they
register.

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
