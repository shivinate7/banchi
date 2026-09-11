# BANCHI

Bulk-list pre-sorted TCG singles on TCGplayer with zero attention per card, and know where
every card physically is. Two tracks share one rig: singles (this file) and code cards
(`code-card-fork/CLAUDE.md`, auto-loaded in that directory).

**Codex reads this same file, not a copy of it (D135).** `AGENTS.md` at the root and
`code-card-fork/AGENTS.md` are relative symlinks to the `CLAUDE.md` beside each, and
`.agents/skills` is a directory symlink to `.claude/skills` — one edit reaches both tools'
readers, because a copy is a fork with a diff nobody watches and a symlink has no diff to
drift. `.codex/hooks.json` is tracked beside `.claude/settings.json` and names the same
hooks by the same scripts; `make docs-audit`'s `codex hooks` row reconciles the two rosters
in both directions and fails a commit that adds a hook to one tool and not the other.
`.codex/config.toml` is the one file of the three Codex left that stays untracked — a
shell-environment policy, machine-local the same way `.claude/settings.local.json` is.

## The name is the app's, and nothing beneath it

**Banchi** — 番地, a lot number, the address of a thing — is the name of the PRODUCT a person
looks at: the web app under `app/`. Every card in the store has an address (box → section →
card), and the app is named after that idea.

**Everything under the app keeps the name it has always had.** Renaming any of it is a
defect, not a follow-up:

- the checkout's own directory (`~/Developer/pkmnscan`), and the CLI `./pkmnscan` with
  every subcommand
- the Python packages — `server/ store/ pipeline/ identify/ geometry/ codes/ cli/`
- the store on disk (`inventory/store.sqlite`), `PKMNSCAN_HOME`, and every route on the wire
- `PKMNSCAN_MAIN=off`, the git hooks' escape hatch, printed in every refusal
- the harness, the fixtures, `docs/`, and `make` itself

**THE GITHUB REPOSITORY IS THE ONE EXCEPTION, AND IT IS THE OWNER'S OWN CHANGE.** It was
renamed `shivinate7/pkmnscan` -> `shivinate7/banchi` on 2026-09-06, deliberately, and this
list named the repository among the things that keep the old name until that day. **The
LOCAL directory is not renamed** and neither is anything else above: `git remote -v` points
at `banchi.git`, `~/Developer/pkmnscan` is still the checkout, and the two disagreeing is
correct rather than half-finished. GitHub redirects the old name, so an old clone URL and
every link in a merged PR still resolve.

**It reached one derived thing and one only, and that was already guarded**: GitHub Pages
serves a project site at `/<repo>/`, so the demo moved to `shivinate7.github.io/banchi/`.
`.github/workflows/demo.yml` derives `DEMO_BASE` from the repository name for exactly this
reason, in a comment written before the rename happened, and the published demo followed it
by itself. The Makefile's default is a fallback for a hand-run build and is stale by design
rather than by oversight — override it, or let CI derive it.

The rest of the rename is a front-end fact and it reaches exactly these places:
`app/index.html`'s title and meta, the brand block in `app/src/App.tsx`'s sidebar, the
document title per screen, the `banchi.*` keys in `localStorage`, and the copy on every
screen. **Nothing on the wire changed.** A session that "finishes" the rename by touching
`server/` or `store/` has moved the store of record for a word.

**The gating system is retired as of 2026-08-23.** Gate A passed 2026-07-26; Gate B passed
2026-08-22 with 53 real cards end to end — the first numbers this project has about cards
rather than about itself are in that gate's section; Gate C passed 2026-08-22 with two
85-card feeder runs. No gate is current, nothing is blocked behind one, and the deferred
list is open.

**`docs/GATES.md` is now a record of runs, not a schedule.** Its sections are the only
place this project writes down what it has actually measured — 53 cards end to end, finish
detection false-positive at 30%, `detect_card` at 0 of 53 and then 53 of 53, a 623 ms
feeder cadence. **Those numbers are evidence and are never rewritten to match a later
tree.** What was retired is the gate as a *control*: the blocking, the sequencing, and the
"current gate" a session had to look up before it was allowed to build. See docs/GATES.md.

## Commands

```
make hooks          # arm the git hooks (glob-installed from scripts/githooks/, so this line
                    #   never has to be recounted). Once per clone — core.hooksPath never
                    #   travels. post-merge/post-checkout print a `make hooks` reminder the
                    #   moment a pull or branch switch makes the installed copy stale — before
                    #   this, that was visible only in `make status`, easy to miss right when
                    #   it happens.
make worktree-setup # in a fresh git worktree, FIRST. venv + T1's banked cache; neither
                    #   is tracked, so neither travels. Skipping it fails T1/T6/T7 with
                    #   three errors that never mention the worktree. The Browser pane's
                    #   port is NOT among them any more: the SessionStart hook writes
                    #   `.claude/launch.json` from this checkout's own slot before any work
                    #   starts, so a worktree can no longer preview the MAIN tree (D43).
make status         # where you are: next step, T1 score, branch. Start here.
make map            # docs/map.py RENDERED — the file is 2,700 lines and had no human view
                    #   at all until 2026-08-31 (D80), which is how a whole section of it
                    #   sat wrong for three weeks. ARGS=<package|path|D<n>|--stale>;
                    #   `--stale` ranks entries whose FILE has moved since the prose about
                    #   it did, which is the one drift no audit row can decide.
make harness        # all NINE verification tests; the Stop hook runs it at turn end. It said
                    #   seven until 2026-08-31 — `t8_codes.py` landed with the code-card track
                    #   and nothing counts these either (see the route-count warning below).
                    #   T9 landed the same day: the first test here whose inputs are
                    #   RECORDINGS OF THE RIG (`harness/traces/`) rather than frames a test
                    #   drew for itself. It exists because both Playwright specs over the
                    #   motion trigger stayed green while 38 real cards were refused as an
                    #   empty stand (D81). RECOUNT from `harness/run.py`'s TESTS list.
make up             # THE server, detached — ONE PROCESS AS OF 2026-09-11 (D138). The capture
                    #   server serves `app/dist/` beside the API, so the app and the wire are
                    #   one origin on one port, and `:5173` belongs to `make dev` alone.
                    #   It RELOADS ITSELF when you edit Python under
                    #   server/ store/ pipeline/ cli/ identify/ geometry/ codes/, and REBUILDS
                    #   THE APP when you edit under app/src or app/public — two watch sets,
                    #   two actions, and neither can trigger the other: a `.tsx` save never
                    #   bounces the server a rig is capturing with.
                    #   A BUILD IS 1.2s AND THE OLD BUNDLE ANSWERS THROUGHOUT. The swap is two
                    #   renames through a sibling of `app/dist`, because `vite build` empties its own
                    #   output directory first — in place, every asset would 404 for the
                    #   second it takes. A FAILED BUILD CHANGES NOTHING: the last bundle that
                    #   compiled goes on serving and `make status` says so, which is the parse
                    #   pre-check's rule applied to the other language.
                    #   `npm ci` runs itself when the lock file's CONTENT moves, so a pull is
                    #   fully self-applying. Not its mtime — git rewrites those on checkout,
                    #   and a branch switch would spend thirty seconds re-installing a tree
                    #   that was already current.
                    #   The SUPERVISOR reloads itself too, by re-exec, when one of the four
                    #   files it is made of changes (D53) — so nothing here goes stale on a
                    #   `git pull`. The Makefile is not one of them: nothing reads it at run
                    #   time.
                    #   Prints ONE link. `make down` stops it; `make up ARGS=--restart`
                    #   bounces it.
                    #   Do NOT run it alongside `make server` — the second loses, loudly
                    #   (EADDRINUSE), which is deliberate: a server that quietly moved would
                    #   serve a DIFFERENT store (D43). `make dev` alongside is FINE and is the
                    #   point — the supervisor no longer holds :5173.
make launch-agent   # start at login, so the link is always live. MAIN TREE ONLY — it refuses
                    #   in a worktree, whose plist would outlive the worktree. ARGS=--remove.
                    #   THE DOCK APP IS A CLIENT OF THIS AND NEVER A SECOND COPY OF IT (D108):
                    #   Chrome's `Install page as app` over http://localhost:8000 writes a real
                    #   bundle with its own icon, window and ⌘-Tab entry, on the same engine and
                    #   the same profile — so the camera grant and the rig's 4K carry unchanged.
                    #   A wrapper that also started the server would be D53's two-supervisor
                    #   defect with a GUI in front of it. There is no `make` target: the install
                    #   is one press in Chrome, once, and `app/public/manifest.webmanifest` is
                    #   the part of it that lives here.
make dev            # Vite with HOT RELOAD. :5173 in the main tree, its own port in a worktree.
                    #   Blocks. It runs BESIDE `make up` since D138 and talks to that server
                    #   over the same store — the supervisor stopped holding this port, so the
                    #   refusal that used to stand here is gone. `make server` is still refused.
make server         # Python capture server. :8000 in the main tree, its own port in a
                    #   worktree — it prints which, and whose store it is serving. Blocks.
make screenshot     # renders scripts/views.txt to captures/ui/. Needs `make dev` running.
                    #   IT CAN FAIL FOR THE RIGHT REASON SINCE 2026-09-07. Until then the only
                    #   failure was an empty file, so a render MISSING AN ELEMENT — a valid,
                    #   plausible-looking PNG — passed, and a session looked at an incomplete
                    #   page and called a screen fine. Each manifest line may name the elements
                    #   its render must prove it drew; the renderer hides one, captures again,
                    #   and refuses the render when not a pixel changed.
                    #   AND IT RENDERS THE TREE IT IS RUN FROM, since the same day (D43).
                    #   scripts/views.txt names the main checkout's :5173 as a CONVENTION —
                    #   a tracked file cannot name a port derived from one directory's path —
                    #   and the script reads `server/ports.py:dev_port` and substitutes a
                    #   worktree's own before rendering. Before this, `make screenshot` in a
                    #   worktree photographed the MAIN tree's app over the owner's real store
                    #   and the renders looked entirely correct.
make design-check   # DESIGN.md's Fulfillment floors, asserted in a browser. IT TAKES A
                    #   MACHINE-WIDE LOCK FIRST, AND IT IS THE ONE THING D43 COULD NOT MAKE
                    #   PER-CHECKOUT (D122): every tree has its own ports and its own store,
                    #   and the CPU is shared. This is the target that spends all of it —
                    #   `fullyParallel` at half the cores, each worker a Chromium context over
                    #   its own Vite server. Two trees running it at once starve each other and
                    #   BOTH report failures that are not in the code: 18 of them on
                    #   2026-09-07, all 52 green on a re-run alone.
                    #   IT REFUSES rather than queues, naming the tree that holds the lock, and
                    #   exits 75 so a refusal can never read as a failing suite. `ARGS=--wait`
                    #   queues instead and says so every thirty seconds — a silent wait reads
                    #   as a hang, which is the other half of what that session hit.
                    #   `PKMNSCAN_SUITE_LOCK=off` runs it anyway, and is printed in every
                    #   refusal. `make harness` and `make check` deliberately do NOT take it;
                    #   docs/DEBTS.md §16 is why, and which half of that is measured.
                    #   `PW_ARGS=<flags>` REACHES PLAYWRIGHT AND `ARGS` NEVER DOES (D136): the
                    #   `--` on each side keeps them apart. CI runs this as three shards of one
                    #   worker each — `PW_ARGS="--shard=1/3 --workers=1"` — because one runner
                    #   ran all 481 cases on one worker in 15 minutes; on the rig it is for one
                    #   spec (`PW_ARGS=tests/brand.spec.ts`). NEVER RAISE THE WORKER COUNT TO GO
                    #   FASTER: docs/DEBTS.md §11's one-in-thirteen red has "the suite around
                    #   it" as its only known mechanism.
                    #   AND IT LEAVES A VERDICT, WHICH IS HOW A SESSION WAITS FOR IT. 89-175s
                    #   measured across five runs, against a 120s tool timeout — so a session
                    #   ALWAYS backgrounds it, and the answer is a file rather than the
                    #   stream. `.serve/design-check.json` holds the verdict, the counts, and
                    #   every failing title with its location and error, no ANSI and no NUL
                    #   bytes. Read it ONCE when the run lands. It says `"verdict": "running"`
                    #   from the moment the suite starts, so a reader can tell STILL GOING
                    #   from DIED — a file still saying that after the process has exited
                    #   means the run died between the two writes (a crashed worker, an OOM,
                    #   a kill). NO FILE AT ALL means the run never reached Playwright's
                    #   config: an unloadable config, a missing toolchain, the lock refusing
                    #   it, or — the one case where the process is still ALIVE — `ARGS=--wait`
                    #   still queued behind another tree's fleet, which is why the rule is to
                    #   read the file when the run EXITS and not before. The other three are
                    #   LOUD — a refusal prints and exits 75 — and
                    #   the target deletes the file first so none of them can ever show you
                    #   the LAST run's pass, which is the only silent one of the four.
                    #   Measured: a dead `webServer` and an unparseable spec both land a real
                    #   `fail` with 0/0 counts, their own recognisable signature.
                    #   AND DO NOT POLL FOR IT. A backgrounded command re-invokes the session
                    #   when it EXITS, so the sequence is: background it, do other work, read
                    #   the file once when the notification lands. An `until` loop over this
                    #   file buys nothing and produces one notification per poll, none of
                    #   which carry the result.
                    #   NEVER PIPE IT THROUGH `tail`: `... | tail -N > file` writes NOTHING
                    #   until the process exits, because tail buffers its whole input — so
                    #   the obvious "run it and read the tail" gives an empty file for the
                    #   entire run and no way to tell it from a dead one. Those two traps
                    #   together cost a session about a dozen turns on 2026-09-07, before the
                    #   owner killed the background tasks by hand.
                    #   IT IS GUARDED TWICE, BECAUSE THE NAMES AND THE BEHAVIOUR FAIL
                    #   SEPARATELY. `make docs-audit`'s `verdict file` row reconciles the
                    #   reporter's own RESULT_FILE against the config's reporter list, both
                    #   recipes' `rm -f`, and the path named here — three of those four come
                    #   apart SILENTLY, and the worst hands a session a STALE `pass`.
                    #   `make verdict-selftest` RUNS the reporter, copied into a throwaway
                    #   tree, over one passing and one failing spec: verdict, counts, failing
                    #   title, and no ANSI or NUL in the error. That one catches a
                    #   @playwright/test bump moving the Reporter API, where every name stays
                    #   right and every count goes wrong. Both mutation-tested — five arms and
                    #   four. AND IT ASSERTS THE FAILING LINE, NOT ONLY THE FILE (D129): under
                    #   Node 25, 1.55.1 reported `test.location` short and a verdict pointed a
                    #   session 35 lines into the wrong test. 1.58.0 is the floor that counts
                    #   it right for an ESM spec and is the pin; this arm sees a bump bring it back.
                    #   It launches NO BROWSER and NO DEV SERVER, so it is in `check`
                    #   and `ci-check` and takes no lock.
                    #   ON CI IT RUNS ONLY WHEN THE CHANGE REACHES WHAT A BROWSER DRAWS (D141).
                    #   `.github/workflows/check.yml` gates its three-shard matrix on a pull
                    #   request by `scripts/browser-scope.py`, whose list is DERIVED from what
                    #   this target loads — `app/**`, the traces `cadence.spec.ts` reads off
                    #   disk, this recipe's own text, the lock script, and the gate's two files.
                    #   `server/` is deliberately out: `sealEveryTest` means this suite cannot
                    #   see a server change. The list has a reader before it has a filter —
                    #   `make docs-audit`'s `browser scope` row, both directions — because a
                    #   filter that is too narrow silently stops testing something and the
                    #   green is believed. A push to main is never skipped by it; D136's
                    #   gate, on the tree, is the only one that acts there. Replayed over
                    #   main's last 14 merges the night it landed: 9 skip, 5 run.
                    #   `python3 scripts/browser-scope.py classify --base origin/main` says
                    #   what CI will do with this branch; `history 20` replays main.
make design-check-quiet  # the same run with the 450-line progress stream dropped. Same tests,
                    #   same verdict file, and THE SAME MACHINE-WIDE LOCK — a quiet variant
                    #   that skipped it would be D122's starvation reachable by typing a
                    #   different target name. The progress is only useful to a human watching
                    #   live and is what makes a captured log unreadable.
make suite-lock-selftest # the lock, exercised by violating it — including a holder killed with
                    #   -9, which is the whole argument for `flock` over a pidfile. In `check`,
                    #   never in the git hook. `PKMNSCAN_LOCK_DIR` sends it at a throwaway
                    #   directory so it never takes the real lock.
make demo           # seed a demo store and record the wire into a fixture bundle.
                    #   THE PRODUCT, SHAREABLE, WITHOUT A FORK. This app makes exactly ONE
                    #   `fetch` (`server.ts:request`) and addresses every photograph through
                    #   one `photoUrl`, so a demo differs from the real thing in TWO
                    #   FUNCTIONS. A fork would duplicate 38,705 lines to carry none of the
                    #   difference, and would diverge the same week — 134 commits landed in
                    #   the three days before this was built. What differs is DATA.
                    #   REAL: the catalogue (every card is a `fixtures/` row) and the whole
                    #   pipeline after `identify` — both runs are JOINED FOR REAL against
                    #   the real exports, so `pricing.json` is the pipeline's own arithmetic.
                    #   The seed fakes only `identify`, the one step that costs money, by
                    #   writing the `identifications.json` a run leaves behind — a hand-made
                    #   one is a case `cli/resolve.py` names as supported.
                    #   INVENTED: which card is in which box, what sold, what shipped. No
                    #   real store is read; `inventory/` has never been in git.
                    #   SYNTHETIC: the photographs, drawn by `demo-seed.py:card_image`.
                    #   Neither real card art nor a picture of the owner's desk belongs in
                    #   something published to strangers.
make demo-seed      # the store alone. Deterministic from one seeded RNG, so an unchanged
                    #   tree rebuilds byte-identically and CI does not churn the repo.
                    #   REFUSES with PKMNSCAN_HOME unset — that default is a real store.
make demo-record    # the bundle alone. Spawns ITS OWN capture server on its own port and
                    #   stops it again, so it never touches `make up` — which on the main
                    #   checkout is the owner's live process over their real inventory.
make demo-static    # the two above, then a static build to `dist-demo/`. VITE_DEMO=1 is a
                    #   BUILD-TIME constant: an ordinary build carries neither the demo
                    #   module nor its ~470 KB bundle, and a runtime flag was refused
                    #   because a UI answering from the wrong store is D43's whole subject.
                    #   DEMO_BASE=<path> is where it will be served from — GitHub Pages puts
                    #   a project site under `/<repo>/`, and a bundle built for `/` 404s
                    #   every asset there while working perfectly on localhost.
make demo-preview   # serve `dist-demo/` exactly as a static host would, base path and all.
make demo-freshness # whether the bundle still matches the wire it recorded. ON NO GATE:
                    #   nothing derived is committed and CI rebuilds it from source on every
                    #   push (`.github/workflows/demo.yml`), so the published copy cannot be
                    #   stale. What is left is a local preview serving a recording that
                    #   predates your last edit.
                    #   WRITES ARE REAL, WITHIN REASON. The sale, the review answer, the
                    #   stand-down, the price, the hold, the rename and the divider all
                    #   write to a mutable copy of the recording — a demo where every button
                    #   is inert argues against the product. What CANNOT exist on a static
                    #   page is refused BY NAME with the reason on it: identification is a
                    #   paid Batch API call, the export fetch and the order sync need a
                    #   signed-in TCGplayer session, capture needs a camera and a disk.
                    #   NO API KEY REACHES A PUBLISHED PAGE and none is asked for. Vite
                    #   inlines only `VITE_`-prefixed variables and no secret in
                    #   `.env.example` carries that prefix, so a public build cannot leak
                    #   one — a property of a naming convention, which is why CI asserts it
                    #   over the built artefact rather than trusting it.
make lint           # eslint over app/ (guards a bug earned, see app/eslint.config.js) plus ruff over
                    #   the Python packages, scoped to a slice measured against this tree (D82) —
                    #   never ruff's own defaults, never --fix. Config: ruff.toml.
make check          # harness + docs-audit + audit-self-test + githooks-selftest +
                    #   merge-selftest + revert-selftest + claim-selftest + claim-stale +
                    #   revert-guard +
                    #   janitor-selftest + reap-selftest + suite-lock-selftest +
                    #   serve-selftest +
                    #   verdict-selftest + port-agreement + set-hint-agreement +
                    #   screen-freshness + sigil-check + ignore-check + lint +
                    #   vale + typecheck.
                    #   THIS LIST IS CHECKED NOW —
                    #   `make docs-audit`'s `check census` row reconciles it and `make help`'s
                    #   against the recipe, and it earned the row: help said five of these
                    #   for months while this line said eleven, and nothing compared them.
                    #   `make explain` is the same list with what each row is worth.
                    #   NEITHER THIS NOR `make harness` HAS design-check's WAITING PROBLEM,
                    #   measured 2026-09-07 in a worktree: 17s and 13s, both well inside one
                    #   tool call, so run them in the foreground and read the output. What
                    #   `check` is is LONG — ~3,000 lines — and the two rows that matter are
                    #   at the end, since it stops at the first failing target. For the
                    #   docs-audit half alone, `python3 scripts/docs-audit.py --json` prints
                    #   the rows and the exit code as one object instead of ~100 lines of
                    #   render, which is what grepping `^  FAIL` was approximating.
make explain        # what `make check` runs: gates, commit path, writes, toolchain.
                    #   ARGS=<target> for one entry in full. A parallel declaration in
                    #   `scripts/checks.py`, deliberately NOT the driver — a registry that
                    #   drove the suite could silently stop running a check; this one can
                    #   only lie, and three audit rows catch it lying.
make screen-freshness # every server write in app/src has a way back: a re-read, an
                    #   invalidation signal, or a reason in the code why none is owed.
                    #   Needs node, so it is in `check` and never in the git hook.
                    #   Finds nothing today — it guards write number 39.
make audit-self-test # the checker checks itself. In `check`, never in the git hook (D16/D18).
make icloud-sweep   # iCloud conflict copies (`foo 2.py`). ARGS=--delete removes the
                    #   byte-identical ones; a DIFFERING copy is only ever reported (D44).
make reap           # STOP WHAT THIS SESSION STARTED, AND NOTHING ELSE (D127). Previews;
                    #   `ARGS=--confirm` presses. `ARGS="port:5484 --confirm"` for one port,
                    #   `match:vite` for a pattern, `pid:N` for one process.
                    #   REACH FOR THIS INSTEAD OF `pkill -f` AND `lsof -ti tcp:N`, both of which
                    #   are MACHINE-WIDE and both of which killed somebody else's process on
                    #   2026-09-10: the first also matched the owner's live capture server over
                    #   their real store, the second also matched the desktop app's network
                    #   helper, which was merely a CLIENT of the port.
                    #   IT SIGNALS ONLY WHAT IS RUNNING UNDER THIS CHECKOUT and PRINTS what it
                    #   refused, which is the half a `pkill` that quietly does the right thing on
                    #   a good day can never do.
                    #   AND YOU DO NOT HAVE TO REMEMBER ANY OF THAT. `scripts/reap.py --hook` is
                    #   a PreToolUse hook on Bash: it RESOLVES a kill's real targets — running
                    #   pgrep and lsof itself, read-only — and refuses the command when one of
                    #   them does not live here. So `pkill -f capture_server.py` is ALLOWED when
                    #   the only match is yours. `PKMNSCAN_KILL=off` runs it anyway and is
                    #   printed in every refusal.
                    #   Not in `make check` and not in the git hook, for `janitor`'s reason.
make reap-selftest  # the guard, proved by pointing it at what it must not kill: a throwaway
                    #   checkout, a real socket with a real client on it, and both 2026-09-10
                    #   incidents reproduced rather than asserted about. In `check`, never in the
                    #   git hook. Mutation-tested — thirteen arms.
make janitor        # WHAT A FINISHED SESSION LEFT BEHIND, and what is safe to reap (D111).
                    #   Previews; `ARGS=--confirm` presses. TIER 1 goes without asking because
                    #   it cannot be live — a process whose own script has been deleted, a
                    #   registration git itself disowns, a husk directory nothing is running
                    #   under. TIER 2 waits for your word: a merged branch no tree holds, a
                    #   worktree with no session in it.
                    #   LIVENESS IS READ, NOT GUESSED. The console app's own per-session
                    #   records — one JSON per pid, in a `sessions` directory under the
                    #   user's `~/.claude` — say which tree each running session is
                    #   standing in; mtimes and
                    #   `git status` cannot tell an idle tree from a busy one, and on
                    #   2026-09-06 two trees with zero dirty files switched branches while
                    #   they were being measured.
                    #   IT NEVER TOUCHES: the default branch, a branch that is unmerged AND on
                    #   no remote, a tree with a live session, a tree with uncommitted work, or
                    #   the main checkout's server — which D53 means to outlive every session.
                    #   Not in `make check` and not in the git hook, for `icloud-sweep`'s
                    #   reason: with it, the only two targets here that can delete a file.
make janitor-selftest # the sweep against a throwaway clone. In `check`, never in the git hook.
make janitor-install # COPY THE SWEEP OUT OF THE TREE, SO EVERY REPO REACHES IT (D111).
                    #   A user-level hook — the settings file in the user's own `~/.claude`,
                    #   not this repo's — applies to every session in every project, but the
                    #   command it names has to exist with no
                    #   checkout in sight — so `janitor.py` and `session-teardown.sh` are
                    #   COPIED, exactly as `make hooks` copies the git hooks out of the tree
                    #   rather than pointing at it. It prints the two hook stanzas to paste.
                    #   THE COPY CAN GO STALE, WHICH IS THE SAME BARGAIN `make hooks` MAKES,
                    #   and `make status` compares it byte for byte and says so — the copy your
                    #   other repos run is otherwise not the copy this tree tests. One press
                    #   per machine, and again whenever either file changes here.
make githooks-selftest # D42's guard over main, proved in a throwaway repo. Never in the git hook.
make lan-check      # IS THE OWNER'S LAN URL STILL GOOD? `http://pkmnscan.lan:8000`, from
                    #   the phone. Two of the six things holding it up are on their UniFi and
                    #   this repo does not touch them (D43); the other four are here.
                    #   IT PRESSES A WRITE, because that is the only row that can tell:
                    #   reads are ungated and writes are origin-checked, so a
                    #   `PKMNSCAN_LAN_NAME` missing from `.env` leaves every screen rendering
                    #   and the whole inventory drawing while capture, undo, mark-sold and the
                    #   claim editor all answer 403. Looking at the app proves nothing.
                    #   Writes NOTHING to press it: the origin gate runs ahead of the body
                    #   reader, so a bodiless POST separates the two refusals without opening
                    #   the store. Reaches the network, so it is deliberately NOT in
                    #   `make check`, which answers from the tree alone — and D18 is not why,
                    #   since nothing here writes.
make merge-selftest # the merge wrapper's local half, against a throwaway origin, clone and
                    #   worktree. Its FOOTGUN case is the one that matters: main checked out
                    #   nowhere while another tree sits on a branch BEHIND its upstream, where
                    #   the wrong command advances that branch and no hook says a word.
make revert-guard   # DOES THIS BRANCH PUT A FILE BACK THE WAY MAIN HAD IT BEFORE A COMMIT
                    #   MAIN ALREADY CARRIES? (D133). PR #221 landed from a tree still holding
                    #   the pre-#218 copy of ten files and D119's deletion came back with every
                    #   guard that asserted it, under a message about `--cap` wording. This
                    #   reads what the branch would LAND on origin/main — the clean merge's
                    #   tree, so a keep-ours merge squashed into one commit reads the same as
                    #   the PR — and refuses a file whose whole change is the exact reverse of
                    #   a commit in main's last 60, when no commit on the branch names that
                    #   file. A reversal you MEAN is one sentence: name the file in a commit
                    #   message. A partial reversal beside real edits is a `note`, never a
                    #   refusal. Runs in `check`, in pre-push on every branch push, and as its
                    #   own job on the PR. `PKMNSCAN_REVERT=off` runs nothing, printed in every
                    #   refusal. WHAT IT CANNOT SEE is in D133 by name: a reversal older than
                    #   the window, one re-worded on the way back, and one whose hunk a
                    #   neighbouring edit widened — the last is how #221's map rows escaped it,
                    #   and a containment test that would have caught them produced 79
                    #   coincidences of moved code on this history, so it was not kept.
                    #   `python3 scripts/revert-audit.py history` is the same engine over main's
                    #   whole first-parent line; the 2026-09-11 walk is in D133.
make revert-selftest # the guard, proved by rebuilding #218 and #221 in a throwaway repo.
                    #   In `check`, never in the git hook.
make claim-ids      # WHAT THE MERGE WILL ALLOCATE FOR THIS BRANCH'S SLUG IDS. A branch does
                    #   NOT take a decision number (D140): the allocation's only
                    #   input is what main has taken, and that is not knowable until the merge.
                    #   So a branch writes its entry's heading as a two-segment slug, cites it everywhere, and
                    #   `make merge` substitutes the number against main as it stands THEN.
                    #   Same for the code-card track's `C-` entries and for the build order,
                    #   whose unclaimed step wears a `0.` marker carrying its slug in backticks
                    #   because markdown has no list marker that can hold one.
                    #   `max + 1`, NEVER the lowest free id — D80 culled step 12 and rules the
                    #   hole correct, and reusing it would resurrect every `step 12` in the tree
                    #   onto a step that is not the one meant. It also keeps a sorted
                    #   `governed_by` list sorted across the claim.
                    #   Previews; `ARGS=--write` performs it. Reach for it by hand only to LOOK;
                    #   the merge runs it for you.
make claim-stale    # HAS A NUMBER THIS BRANCH ALREADY CLAIMED BEEN TAKEN BY MAIN SINCE?
                    #   (D140, amended 2026-09-11.) The claimer above is a NO-OP once a branch
                    #   has claimed — no slug is left, so it says `nothing to do`, which is a
                    #   true statement about slugs and an incomplete one about safety. This
                    #   takes every allocated id the branch ADDS since its merge base with
                    #   `origin/main` — decision, code-card `C`, build-order step — and asserts
                    #   each is still free on that ref.
                    #   IT REPORTS AND NEVER REPAIRS. An un-claim has to happen BEFORE a merge
                    #   and never after: once main is merged in, a substitution on that token
                    #   reaches main's own copy of the entry too. It names the collision, says
                    #   what the id would become, and exits 3.
                    #   NO NETWORK AND NO `gh` — the local ref is enough, and D140 rejects
                    #   reading open pull requests deliberately. It does not need them: the
                    #   case that bites is the one where the other branch has already LANDED.
                    #   Writes nothing, so it gates: in `check`, in `ci-check`, and `make merge`
                    #   asks for it before every merge — that last is the authoritative run,
                    #   because the fetch above it makes the answer current. It can only ever
                    #   UNDER-report against a stale ref, never over-report, and a clone with no
                    #   `origin/main` is allowed and says so.
                    #   It happened TWICE on 2026-09-11 (#262/#265, then #265/#270), caught
                    #   both times by a person reading PR titles. `decision index` is still the
                    #   backstop; this is the earlier, cheaper warning.
make claim-selftest # the claimer, proved where it can be wrong: a throwaway repository in which
                    #   MAIN MOVES underneath the branch — and, since D140's amendment, in which
                    #   main takes a number the branch had already claimed. In `check`, never in
                    #   the git hook.
make merge          # merge a PR and move main onto it — BOTH HALVES, on your word (D42).
                    #   IT CHECKS FOR A STALE CLAIM BEFORE ANYTHING ELSE (D140, amended):
                    #   a number this branch claimed that main has taken since is REFUSED here,
                    #   in preview as well as on the press, and nothing is rewritten for you.
                    #   IT CLAIMS THIS BRANCH'S IDS FIRST, AND WAITS (D140): it
                    #   substitutes, commits to the PULL REQUEST's branch, pushes, and watches
                    #   that commit's checks to completion before merging — so nothing main has
                    #   never run CI over reaches main. It REFUSES if this checkout is not
                    #   standing on the PR's own head branch, or if the tree is dirty: the claim
                    #   is a commit, and it would otherwise land on whatever is checked out.
                    #   `--no-claim` skips it, for a claim already pushed by hand.
                    #   ARGS=<n> previews and presses nothing; ARGS="<n> --confirm" performs it.
                    #   A bare `make merge` refuses: there is no default PR and will not be one.
                    #   IT DELETES THE HEAD BRANCH AFTERWARDS (2026-09-05) — on origin always,
                    #   and here only when no worktree holds it and it is an ancestor of main.
                    #   Until then it deleted neither, and 125 merged PRs had left 85 branches
                    #   on origin and 106 in this clone. It is NOT `--delete-branch`: that flag
                    #   would switch this tree's branch out from under the local half.

./pkmnscan scan     <capture-dir>   # CODE CARDS ONLY. Read the QR codes into the ledger.
                                   #   FREE — no model call, no network. The QR IS the code.
./pkmnscan identify <capture-dir>   # submit, wait, collect, cache. COSTS MONEY. --dry-run first.
./pkmnscan join     <run-dir>       # resolve against the export. Free, re-runnable.
                                   #   --dry-run  preview both queues, write nothing
./pkmnscan emit     <run-dir> [<run-dir> ...]
                                   # write ONE import CSV, `import.csv`. Free, re-runnable.
                                   #   ONE PRESS WRITES ONE SPREADSHEET (D99) — across runs,
                                   #   across games, and across the listed/sub-threshold
                                   #   split, which was two files per game per run until
                                   #   2026-09-03. THERE IS NO STANDING CAP as of
                                   #   2026-09-07 (D7, rewritten): every copy a run holds that
                                   #   TCGplayer does not already have goes out, and a bound
                                   #   is something ONE SEND asks for with `--cap`. When one
                                   #   is asked for it is spent ONCE across everything the
                                   #   press writes (D86): `add_to_quantity` is per-run
                                   #   against a GLOBAL cap, so N separate emits over one SKU
                                   #   is an over-push. Measured at the old cap of 4: three
                                   #   separate emits over three real runs wrote 2 SKUs past
                                   #   it; one merged emit wrote 0.
                                   #   WHAT STOPS A COPY BEING SENT TWICE IS NOT THE CAP and
                                   #   never was — `uncommitted_positions` is, and it is
                                   #   untouched. Uncapped, six copies with three already live
                                   #   offer THREE.
                                   #   --cap N            hold this SKU to at most N copies
                                   #                      LIVE, counting what is already out
                                   #                      — a SKU at or over N adds nothing
                                   #                      and the report says by how much.
                                   #                      Omit for no cap, the default
                                   #   --quantity SKU=N   put exactly N copies of THIS card in
                                   #                      the file this press (D7, amended
                                   #                      2026-09-11): a SEND QUANTITY, not a
                                   #                      ceiling — bounded by the copies on hand
                                   #                      that are not already listed, never by
                                   #                      what TCGplayer holds. Repeat per card;
                                   #                      0 sends none of it without a hold. The
                                   #                      Qty field on every `#/pricing` row is
                                   #                      the same answer, spent by the write.
                                   #   --listed-only      above-threshold rows only (a filter,
                                   #                      not a split — the rest wait)
                                   #   --split-threshold  the old pair back: import-listed.csv
                                   #                      and import-subthreshold.csv
                                   #   --split-games      one file per game
./pkmnscan prices   adopt [--write] # fold every run's legacy decisions.json into the corpus.
                                   #   Previews by default; newest-wins, and it NAMES the holds
                                   #   a later price replaced rather than counting them.
./pkmnscan prices   show [--held]   # what the corpus holds. `--held` is the cross-run view of
                                   #   what is held back — D49 named its absence, D62 repeated
                                   #   it, and it is one line now that the answers are one file.
./pkmnscan reconcile <run-dir> <staged-export.csv>   # one import, one Export From Staged
./pkmnscan reconcile --live <my-pricing.csv> [--write]
                                   # THE WHOLE STORE against one live export (D87). Previews
                                   #   by default. Reports BOTH directions — copies this
                                   #   pipeline sent that TCGplayer no longer holds, and SKUs
                                   #   it holds that were never sent from here.
                                   #   WHAT IT WRITES IS `live`, AND THE COUNTER IT CLEARS
                                   #   (D115). `live` is the export's READING; a sale no
                                   #   longer edits it but counts beside it in
                                   #   `sold_here`, and what a screen draws is the
                                   #   difference. This clears that counter where it
                                   #   adopts a reading taken after those sales — which
                                   #   is why the order stopped mattering: mark sold
                                   #   whenever, reconcile whenever. `pushed` is
                                   #   the cumulative record of what was sent, and
                                   #   `cli/resolve.py:_copies_out` already corrects a stuck
                                   #   one against the physical ceiling. Nothing had ever
                                   #   written `live`: 405 of 443 SKUs read 0 while carrying
                                   #   pushed copies, so the cap arithmetic saw 93 live copies
                                   #   where there were 1,079.
                                   #   IT NOW RECORDS SKUS TCGPLAYER HOLDS THAT THIS STORE
                                   #   NEVER SENT (D109), where it used to name them and drop
                                   #   them: `live` and a first sighting are written, `pushed`
                                   #   and `staged` stay 0 because this pipeline sent none of
                                   #   it. Before this, 0 of 443 listing records had no card
                                   #   behind them while the export carried 28 live SKUs that
                                   #   did — so nothing could date a listing, nothing stopped
                                   #   a rule marking the same one down every pass, and a copy
                                   #   selling was invisible.
                                   #   It moves QUANTITIES and marks no card sold (D7).
                                   #   A reading OLDER than the store's own `live_as_of` is
                                   #   kept, not written, and named in the report — the
                                   #   same rule `join` applies (D87 amended 2026-09-02).
                                   #   Reachable on `#/runs`, under the run panel.

./pkmnscan reprice  list <my-pricing.csv> [--days N] [--percent P] [--write]
                                   # WHICH LIVE LISTINGS ARE NOT SELLING, and what each would
                                   #   be re-priced to (D100). Free, re-runnable, previews.
                                   #   `--write` writes a WORKLIST — the stale rows in export
                                   #   shape, with a price already proposed on every one — into
                                   #   `inventory/markdowns/<stamp>/`. It is uploaded nowhere.
                                   #   The age it ranks on is how long the card has been OWNED,
                                   #   because `Listing` has no first-listed stamp; every
                                   #   report names the substitution in its own header.
                                   #   --days N          the window: nothing sold here inside
                                   #                     it, and OWNED since before it
                                   #   --percent P       cut off the asking price (default 10)
                                   #   --above-market P  only listings asking more than P%
                                   #                     above `TCG Market Price`
                                   #   --limit N         the N rows worth the most; rest named
                                   #   --again           override the ratchet. IT NOW COVERS
                                   #                     HAND-PRICING TOO: `corpus.stamp_answers`
                                   #                     dates every price the screen writes, so
                                   #                     a card priced on `#/pricing` yesterday
                                   #                     is refused `priced_recently` today —
                                   #                     which is what D100 always claimed and
                                   #                     never did (D103).
./pkmnscan reprice  apply <worklist.csv> [--corpus-revision <digest>] [--write]
                                   # The edited worklist back; `--write` produces `import.csv`,
                                   #   which is what you upload through My Pricing.
                                   #   NOTHING IS EVER DELETED AT TCGPLAYER TO LOWER A PRICE.
                                   #   `TCG Marketplace Price` edits the live listing in place —
                                   #   282 of 288 live SKUs carry exactly the price this
                                   #   pipeline last wrote — and `Add to Quantity` is a DELTA:
                                   #   72,701 real export rows carry "0", 649 of them on rows
                                   #   TCGplayer reported LIVE. Every row of every file this
                                   #   command writes carries 0, so uploading one twice is a
                                   #   no-op. That is not true of an `emit` file: nine SKUs on
                                   #   this store sit at 2 x pushed - sold because one was.
                                   #   Only `TCGplayer Id` and `TCG Marketplace Price` are read
                                   #   out of the file you hand back; every other byte comes
                                   #   from the manifest, so a spreadsheet cannot corrupt it.
                                   #   `--corpus-revision` refuses the WHOLE file if
                                   #   `inventory/prices.json` moved since the caller read it.
                                   #   Omit it to say "did not read one", which is the terminal
                                   #   user. It exists because this command writes the corpus
                                   #   from a subprocess and `emit` never did, so a `#/pricing`
                                   #   tab open during an apply had its next keystroke refused
                                   #   for a write it had just made (D103). THE SHEET IS NOW
                                   #   MOUNTED INSIDE THAT TAB (D105), so the digest travels as
                                   #   a prop and the host adopts what the apply produced.
                                   #   Reachable on `#/pricing`, from a header button — a modal
                                   #   and not a route, which D100's own §5 records as a choice
                                   #   rather than the nav measurement it started as. It sat on
                                   #   `#/runs` beside the store-wide reconcile until 2026-09-06
                                   #   because both read one export, which is kinship of
                                   #   IMPLEMENTATION; a markdown decides a PRICE, so it lives
                                   #   where prices are decided (D105). The reconcile did NOT
                                   #   move: it writes `live` onto the store's own records,
                                   #   which is a fact about inventory.
                                   #   AND ON `#/pricing` AS A LENS (D103), which is the same
                                   #   screen and no longer a second one:
                                   #   `reprice list --write` leaves a
                                   #   `survey.json` holding every live row with its verdict,
                                   #   and `#/pricing?markdown=<stamp>` prices them in the same
                                   #   UI a run is priced in — charts, presets, holds, the
                                   #   keyboard walk. `--write` writes that directory even when
                                   #   the rule proposes nothing, because the lens is reached BY
                                   #   a stamp. TWO DOORS REACH IT and neither is a URL you type:
                                   #   the worklist step's primary press, and a `Price these`
                                   #   button on every history row that has a survey.
```

## The front end

Vite + React 19 + TypeScript over the capture server and nothing else: no pipeline logic in
the browser, no second store, no auth, no login. `app/src/server.ts` is the only place a
client call is written and `app/src/types.ts` the only place the wire's shapes are declared.

### The screens

**The app has twelve screens and twelve routes** — eleven the owner's, one the Fulfiller's.
`app/src/App.tsx`'s `ROUTES` table is the count. **Recount from the table; never increment a
sentence**, and see "the census" below for what enforces that.

```
#/             Home           the product as a picture: ONE RANKED SENTENCE saying what the
                              store is waiting on (D121, `standing.ts` — and the null invariant
                              in it is the load-bearing part), one action, then the library
                              drawn as the work that made it — sittings clustered from
                              `captured_at`, each block as wide as its minutes and as tall as
                              its cards an hour, so its area is its card count. Then the
                              six-stage spine (Capture → Runs → Review → Pricing → Orders →
                              Shipping) with the live figure under each stage, the boxes, the
                              runs.
                              Every figure is the one that stage's own screen draws, read from
                              the same source, so Home can never be a step ahead of it.
#/capture      Capture        live camera; box / game / set hint / finish / rarity; undo;
                              the motion trigger and its tuning. THE SETUP IS REMEMBERED ON
                              THE DEVICE (D142) — all six survive a closed browser, the box
                              list is ordered the way the inventory rail is (most recently
                              reached for, then fullest, then the number), one press clears
                              the lot with an undo on the receipt, and the box is named
                              rather than numbered
#/runs         Runs           the pipeline: the free preflight, the two-step money gate, join /
                              emit / reconcile, the run log, and the import CSVs as downloads
#/review       Review         one card at a time, photo first — the answer writes and advances
#/pricing      Pricing        the hand-pricing worklist, one row per SKU, the rule strip, and
                              D49's deliberate holds. TWO SOURCES (D103): the joined runs, and —
                              at `#/pricing?markdown=<stamp>` — the operator's whole LIVE
                              inventory out of a My Pricing export, where staleness is a filter
                              rather than a gate and the press writes a price-only `import.csv`.
                              THE LIVE BOOK IS A ONE-PRESS DOOR (D109): with no joined runs this
                              screen used to offer only "Go to Runs" — sending the operator away
                              from 387 live listings because none came out of a camera here. It
                              leads with "Price my live listings", which opens the sheet with the
                              fetch already running. A listing this store never photographed is
                              PRICEABLE there, and the field's ghost is the price you are asking
                              NOW, so the first digit typed replaces it whole.
                              THE CUT-OFF IS THE SAME CONTROL ON BOTH DOORS (D103, amended
                              2026-09-07). `CutoffPanel`, `policy.threshold` and `bucketAt` are
                              shared; the ONLY difference is when the figure is spent — `emit`
                              prices a run's cheap half at write time, and a lens has no emit, so
                              the press writes real answers in one act with one reversal.
                              A SOLD-OUT ROW IS NOT SURVEYED at all: 372 of the owner's 759 rows,
                              which can never be priced. The EXPORT still carries them, because
                              `reconcile --live` reads a zero quantity to see a SKU sell out.
                              THE SHEET THAT MAKES ONE IS HERE TOO (D105), off the header —
                              read an export, write a worklist, price it without changing screen
#/orders       Orders         which copies this buyer gets and where they are, ranked by how
                              many of them sit in one box, pulled one copy at a time
#/shipping     Shipping       which envelope an order goes in, out of TCGplayer's own shipping
                              export, in three lanes
#/inventory    Inventory      the box walk and everything that hangs off it: search, a card's
                              copies and its sale, and the box's own operations. SOLD IS
                              HIDDEN BY DEFAULT (D132): one `Hide sold` chip folds departed
                              rows out of the walk and the copies list, or sinks them under
                              the live ones. The address leads with the box's NAME and the
                              rail orders boxes by when this browser last opened them; a
                              section can be named from the Manage box sheet.
#/graveyard    Graveyard      every departed card, sold or retired or moved (D134) — merged
                              from two sources, a record still standing in a box nobody has
                              deleted and a `buried` history line for one whose box was.
                              Read-only: nothing here can be undone, and nothing here prices
#/codes        Codes          the code-card track: read a box's QRs into the ledger, the lanes
                              the pile is tiered into, and a lane handed to a buyer
#/fulfillment  Cards to pull  the second persona's whole product: pull, photo-confirm, mark
                              sold. Rendered with NO shell at all.
#/gallery      Kit            the component sheet, rendered by the build so it cannot go stale
```

**`#/orders` and `#/shipping` are two stages of one screen and two routes.** `Orders.tsx`
exports `OrdersHub`, `Shipping.tsx` does nothing but point the second route at it with
`stage="ship"`, and the Ship stage's own body lives in `OrdersShipStage.tsx`. Two routes
rendering one hub, joined by a stage strip and a client-side join on order number — nothing
is written across the seam. This is not D31's defect returning: D31 deleted two routes drawing
the same records with no relationship between them; these are two stages of one sale, and each
is a real destination the nav, the palette and `,O` / `,S` all reach.

**`#/inventory` is the one owner-side view of stored cards** (D31). `#/boxes` and `#/pull` are
not routes and never come back; the box walk is the spine and search narrows it. The box's own
operations — rename, dividers, seal, claims, the mid-box remove, the box delete, and D89's
photo reclaim — are in its **Manage box** sheet.

**Two routes are deliberately not in the nav** and `OFF_NAV` in `App.tsx` declares it rather
than leaving it implied: the Fulfiller's screen, reached from the sidebar foot and the palette
because it opens in its own tab, and the kit, reached from the palette only. Both are
registered routes and both must stay reachable. `scripts/docs-audit.py`'s `route rosters` row
reads that constant; deleting it turns a passing check into a false alarm.

**The census.** Every published route or screen count in this file, in `README.md` and in
`docs/map.py` is reconciled against the `ROUTES` table by `make docs-audit`'s `route census`
row, and every spec's pinned roster by `route rosters`. Both are MECHANICAL and both fail a
commit. They exist because this count was wrong seven times in three files with nothing
reading it, and because the TESTS had the same disease — a sweep over "every route" off a
hand-typed list of hashes silently walked the routes it had. `app/tests/cursor.spec.ts` reads
the nav strip now. The census also refuses to go quiet: a claim reworded past the pattern
watching it is reported as an unwatched sentence.

### The design system

`app/src/tokens.css` is the system, and **it is the only file in `app/` that may name a
color — with one argued exception.** `app/src/kit/markPalettes.ts` holds the six locked marks'
sixty hexes (D102): they are an *illustration's* colors, locked by `docs/specs/logo.md` §9, and
they must NOT be theme-overridable, which is what moving them into `tokens.css` would invite.
That file is generated, never hand-edited, and `make docs-audit`'s `logo parity` row reconciles
it against §9 in both directions — because `raw color` cannot see it at all, its scope being
`app/src/*.css` and never a `.ts`. **An exception with no reader is how a rule stops being one.** Every token is `--bn-*` — color, type, spacing, radius, elevation, motion, the
shell's own metrics. **Write new CSS with `--bn-*`.**

**The legacy aliases at the foot of that file are a migration seam that is already spent, and
this paragraph said the opposite until 2026-09-07.** It said the old names — `--ink`, `--muted`,
`--line`, `--s1…`, `--r`, `--util` — "survive so no stylesheet was orphaned", which read as a
live dependency; `app/src/tokens.css`'s own header went further and said forty stylesheets read
them. **Measured across all 102 files under `app/src`: not one reads any of the twenty-four,
against 266 uses of `var(--bn-ink)` alone.** `docs/DESIGN.md` has recorded this correctly since
2026-09-03 and both of these had drifted from it. They are kept rather than deleted, which is
that file's stated call — and **a new rule may not read one.**

**Both themes are real.** Light is the default; `:root[data-theme='dark']` redefines every
surface and ink together, `app/index.html` applies a stored choice before first paint, and the
toggle stamps `data-theme-switching` on `<html>` so the whole page cross-fades as one
mechanism rather than panel by panel. A screen that has not been LOOKED AT in dark is not
verified; a hard-coded color is invisible in light and wrong in dark, which is why
`make docs-audit`'s `raw color` row reads the stylesheets for hex literals.

**The stage tokens are dark in both themes** — `--bn-stage-*`, for viewfinders and photo
heroes, where the ground is dark because the subject is a photograph.

**Type has three roles, and all three are served from this checkout** (D124, 2026-09-08 —
`app/src/fonts.css`, the one file in `app/` carrying an `@font-face`; nothing the app loads
leaves the origin it came from, and `app/tests/shell.ts:sealOutside` is what keeps that true).
`--bn-font-display` (Manrope) for headings and big figures,
`--bn-font-ui` (Inter) for everything, `--bn-font-mono` (JetBrains Mono) for machine strings
only — SKUs, run names, reason codes, key caps, card numbers. Numbers in tables are Inter with
`font-variant-numeric: tabular-nums`, not mono. Body is 14px.

**The kit is `app/src/kit/` and `app/src/kit.css`**, and `#/gallery` renders all of it. The
components are `Button`, `Kbd`, `Pill`, `Chip`, `PageHeader`, `EmptyState`, `Notice`,
`Segmented`, `Stat`, `Logo` and `Icon`, plus `kit/toast.tsx`'s global toast stack; the classes
are the `.bn-*` set (`.bn-page`, `.bn-panel`, `.bn-well`, `.bn-table`, `.bn-list`,
`.bn-dialog`, `.bn-sheet`, `.bn-receipt`, `.bn-skeleton`, and the rest). **Reach for the kit
before writing a primitive**, and when it genuinely lacks one, build it with a screen-prefixed
class and say so — a fourth hand-rolled button is how a design system dies.

**Register.** Sentences on screen, not machine strings; the pipeline's own string stays
available on hover and in the run log. Enum values are labelled, never printed raw
(`premium` → `Premium`). Empty states are a real sentence and one action. Danger is red, money
moments are deliberate and carry the figure in the label, success is green, live is vermilion.
An icon never appears alone without an accessible name.

**The mark is generated, and it has two optical cuts** (D102). `Logo` renders
`docs/specs/logo.md`'s locked set — six variants, `bluesteel` the default — and
`scripts/build-mark.mjs` writes its geometry, its palettes and `app/public/favicon.svg` by
reading that spec's own generator. **Nothing about the mark is hand-drawn in `app/`, and nothing
is hand-edited**: change the spec, re-run the script. It picks its cut off `size`, and **every
call site in this product is below the 64px boundary**, so the small cut is what ships and the
display cut exists to be looked at on `#/gallery`. It is fixed dark in both themes on purpose —
a light ground was derived and lost its silhouette at every size the app draws (§12). **Never
put a `border-radius` on it**: the tile is a superellipse and a CSS radius clips it twice.

**`base.css` ANSWERS WHAT A CONTROL DOES UNDER THE POINTER AND THE FINGER, IN THREE FLOORS, SO A
SCREEN NEVER HAS TO.** D50 is the entry and `app/tests/cursor.spec.ts` is the guard — every one
of these is mutation-tested, so deleting a floor turns `make design-check` red rather than going
quietly green. **A FOURTH FLOOR IS BELOW THEM AND IS NOT IN THIS FILE**, because it cannot be
written as a rule: see "a press may not move what is around it" after the three:

- **cursor** — a clickable says `pointer`, a text field `text`, and anything DISABLED says
  `not-allowed`. That last arm was 30 of the 41 defects the floor was built for.
- **response** — a control that answers the pointer EASES into it, over `background-color`,
  `border-color`, `color` and `box-shadow`. Measured 2026-09-06: 17 of 293 responding controls
  snapped, ten of them the sidebar's rail toggle.
- **press** — a control answers the finger too: `translate: 0 1px`, and never when it is
  disabled. Measured the same day: 190 of 311 controls were silent under a press.

- **stability** — a press changes WHAT IS ON THE SCREEN and never where the rest of it is (D118).
  This one is a rule rather than a declaration: the movement it forbids is caused by the panel a
  write lands in, not by a stylesheet, so `base.css` cannot supply it and two guards enforce it
  instead. `cursor.spec.ts` reads every `:hover` / `:active` / `:focus` rule for a layout property
  and every `:active` rule that eases the movement it makes; `inventory.spec.ts` presses
  `Mark sold` and requires that nothing outside the card panel moved, that the page did not change
  height or scroll, and that the panel holds one height for the whole box walk. **A slot whose
  control becomes its own result reserves the tallest of its states** — the location card's action
  slot holds a 40px button pair, a 50px receipt and a 22px pill, and floors at `max()` of the
  tokens they are built from. Measured before it existed: one `Mark sold` collapsed the panel 98px
  and moved 131 elements, and stepping the walk moved 39, 66 or 98px depending on the two cards.

**Three things follow, and getting any of them wrong is silent:**

**A component's own `transition` REPLACES the floor's, it does not add to it.** Declare one and
every property that screen animates must be named in it — this cost a real defect on
`.bn-nav-link`, whose new hover snapped because `box-shadow` was missing from a list it already
had. Nothing warns you; the rule just does not animate.

**`background-image` is not animatable, so a hover may never composite a layer with a
gradient.** Interpolation from `none` to a gradient is DISCRETE: the paint lands in one frame
however it is transitioned. Compositing an alpha over an existing ground is an inset
`box-shadow` at a spread larger than the element. This shipped wrong once and the guard was
green through it; the guard reads for it by name now.

**The press dip is `translate` and a screen's own emphasis is `transform: scale()`** — two
properties on purpose, because they COMPOSE. Spelling the dip as `transform: translateY(1px)`
silently doubles it to 2px, which six rules were doing. And an opt-out must be written in the
property the floor actually uses: three rules opting out with `transform: none` were silently
repealed the day the dip moved to `translate`.

**A CONTROL MAY NOT EASE THE MOVEMENT ITS OWN `:active` RULE MAKES** (D118). The dip lands on the
frame the finger goes down; a squeeze on a 120ms transition beside it is one gesture on two
clocks, which is what a press reads as janky. Three rules were doing it — `.bn-btn`,
`.pull-confirm` and the phone tab bar's icon. A control that legitimately eases a `transform` for
a HOVER lift keeps it and names its repaints inside the `:active` rule instead, leaving the
movement out of that list.

**Motion is part of the system, not decoration.** Durations and easing curves are tokens; the page
enters, list rows stagger off `--bn-stagger`, selection changes and receipts and progress
animate, buttons press. `app/src/base.css` honours `prefers-reduced-motion` and keeps turning
only the loops that carry meaning — a busy ring, a skeleton, a live dot. Never let motion be
the only carrier of information.

### The shell

`App.tsx` is a hand-written hash router and the whole chrome. Read it as the shell: twelve
hash routes, no routing library, no nested routes, one table. Every screen renders inside it
except the Fulfiller's:

- **A sidebar that collapses to a rail** on wide windows — 236px or 64px, ⌘. toggles it, the
  choice is remembered in `banchi.rail`. Ten nav items in four groups; the brand, the
  hand-off link, the palette, the theme toggle and the capture server's own state sit in the
  foot.
- **A top bar and a bottom tab bar on phones**, with the rest of the screens in a left drawer
  behind More.
- **A command palette on ⌘K**, the only control that opens `#/gallery`. It searches each
  route's own `keywords`, so a screen is findable by the verbs it holds.
- **`,` then a letter jumps anywhere**, with an on-screen which-key overlay and a one-second
  window. ⌘← / ⌘→ step the workflow ring in the order the nav draws it (D51).
- **A keyboard reference sheet on `?`**, and from the palette. It lists every binding in the
  product grouped by where it applies, and each group says in a sentence that a screen's keys
  are dead while another screen is open. `?` is the only unmodified key the shell takes and it
  yields to typing — `app/src/keys.ts` makes that judgement for every handler in the app. The
  inline ⌘←/⌘→ key caps are deliberately not drawn anywhere; this sheet is the one reference,
  so **a new binding is not done until it is in `SHORTCUTS`.**
- **An error boundary per route, in two shapes.** The owner's crash page offers a reload and a
  way home. The Fulfiller's — the `plain` variant — offers ONE button that reopens the screen
  he is on, at his floors, with no brand mark and no error text, because `docs/DESIGN.md`'s
  constraints table forbids a route out of his view and a crash is the moment he is most
  likely to press whatever is offered.
- **A toast stack**, an offline banner for the capture server, and the document title.

The Fulfiller's route is `persona: 'fulfiller'`, and `hasChrome` renders none of the above for
it. Not-rendered rather than hidden: not focusable, not reachable by a screen reader, not one
specificity change from coming back.

### Verifying a screen

A screen is not finished because it compiles.

- `cd app && npx tsc --noEmit` prints nothing.
- **Look at it at 1440, 820 and 390**, the three widths this build was verified at, **in both
  themes**. No horizontal page scroll at 390.
- Anything a thumb presses is 40px or more. The control-height tokens raise themselves under
  767px and on a coarse pointer, so do not hand-roll a mouse-sized control on a phone.
- `make design-check` asserts `docs/DESIGN.md`'s Fulfillment floors in a real browser — 20px
  body, 32px position labels, 320px photograph, 44px targets, 7:1 contrast, no jargon, no
  route out. **Those floors serve a real person and are not part of any redesign.**

## Things you will get wrong without being told

- **The capture server is ALREADY THREADED, nothing bounds it, and it is NOT YOURS TO RESTART.**
  `server/capture_server.py` serves on `class CaptureServer(ThreadingHTTPServer)` — one thread per
  keep-alive CONNECTION, unbounded. `request_queue_size = 128` bounds the accept backlog and not the
  thread count, and `CaptureHandler.timeout = 15` reaps only IDLE connections. So **a burst of
  concurrent clients is what kills it**, and `make design-check` is the burst: measured at 80
  Playwright browsers, 969 threads in ten minutes, 338% CPU, answering nothing.

  **`ThreadingHTTPServer` is therefore not the fix — it is the cause.** A session on 2026-09-04
  diagnosed a wedge from `.serve/*.log` without opening the file, told the owner the server was
  single-threaded, and proposed the class it has been built on since the beginning. The real fix is
  a bounded worker pool and it is not a swap; `docs/DEBTS.md` §11 has the whole argument, the three
  measurements, and why a pool over keep-alive starves.

  **Both bounds landed 2026-09-04, and the second one is the pool.** `REQUEST_SLOTS = 4` caps how
  many requests EXECUTE at once — the interpreter, which is what ran out — and
  `CaptureServer.process_request` submits to a `ThreadPoolExecutor(REQUEST_SLOTS)` so THREADS are
  capped too. **Every response sends `Connection: close`**, which is what makes a worker's life one
  REQUEST rather than one connection and is the only reason a pool is safe over HTTP/1.1: remove it
  and four idle connections hold all four workers, and `make harness` does not fail, it HANGS.
  Measured at 150 connections: 45.5 requests/sec and 5 threads, against 45.6 and 153 with the
  semaphore alone.
  **Measured on the owner's store on their word**: the collapse reproduces at 150 connections (a
  single probe request took 18s, and failed outright at 300), and the sweep is MONOTONIC — less
  concurrency is strictly better, 53 rps at one slot against 11.9 unbounded. `4` is not the peak;
  it keeps 82% of it and leaves three slots when one is blocked on the store lock for its 30s.
  **Less is more here, which is the opposite of the intuition that first sized this at 12** — a
  value the sweep puts within noise of no bound at all. §11 has the tables.

  **`make launch-agent` keeps that process alive at login over the owner's real store**, so the
  thing on `:8000` in the main checkout is theirs. Run the full suite ONCE at the end rather than
  after every edit, and **never `make up ARGS=--restart` / `make down` / `make up` to fix a
  wedge** — `down` and a restarting `up` refuse there without `--confirm`, and the refusal is
  the answer, not an obstacle. The drain is 40s and a kill past it cuts a write in flight; that same session did
  exactly that and crashed Python out from under the owner mid-use.

- **The join key is PER-GAME, and matching is normalized on both sides.** Pokemon composes
  `zfill(3)(number) + "/" + printedTotal` — the shape is pokemontcg.io's schema (`printedTotal`
  is their field name), but at runtime both values come from the identification and match
  against the export's `Number` column; nothing in the pipeline calls that API. One Piece
  carries no denominator at all (`OP15-079`) and matches the printed identifier verbatim;
  Riftbound does too, because 450 of its rows are denominator-less promos. `pipeline/games.py`
  says which strategy a game uses.

  **`zfill` is the COMPOSITION form only — never the matching form**, and getting that wrong
  was a real silent zero-join: the catalog indexed `Number` verbatim while the key padded it,
  so an export writing `39/236` was never found by a key built as `039/236`. 950 rows joined
  nothing and reported `no_catalog_row`, which blames the export. Both sides now go through
  `pipeline/join.py:number_index_key`. **Never join on Product Name as the KEY — it
  inconsistently embeds numbers** (`Delibird - 105/132` and `Nickit` sit in one column of one
  export). D35 narrows this rather than repealing it: the name is permitted as a LAST RESORT
  that fires only where the number key found nothing, folds the embedded number away on both
  sides through `pipeline/join.py:name_index_key`, and **may never list a card on its own** —
  it queues for review under `number_unread_name_matched`.
- **A run directory's slot numbers are not the truth; the photograph is** (D36). A run is
  immutable and the store is not, so a mid-box delete (D10 ruling 1) slides every higher card
  down one and the run keeps describing the box as it was. `cli/resolve.py:realign` re-binds
  every record to the slot its `photo_sha256` is at now, before anything reads a position.
  It refuses on an ambiguous digest, on two records carrying one digest, and on a
  digest-less record in a box that has moved; it reports a box it cannot check against its
  photographs as unverified rather than treating its cards as gone. **A box whose number was
  deleted and reused after the run is refused outright** (D36 amended) — box 1 held 53 Pokemon
  cards on 2026-08-22 and 133 Riftbound cards since 2026-08-29 — by
  `cli/resolve.py:refuse_reallocated`, on `store/master.py:box_disowns_run`, the rule the
  route already withheld a box's name by (D56): `realign` reads photographs and not the store,
  and passed such a run through as unverified onto another drawer's records.
- **Only two columns are ever written**: `Add to Quantity`, `TCG Marketplace Price`.
  `TCGplayer Id` is never modified. Everything else round-trips byte-identical.
- **Batch API, not sequential calls.** v1 claimed Batch and shipped real-time. Model:
  `claude-haiku-4-5-20251001`.
- **EVERY CHECKOUT HAS ITS OWN STORE AND ITS OWN PORTS, AND THE FIRST HALF HAS ALWAYS BEEN
  TRUE** (D43). `store/files.py:home()` defaults to the checkout the code runs from, so a
  worktree's `inventory/`, `runs/` and `captures/` are its own — usually empty. The ports
  follow it now: the main tree keeps `:5173` and `:8000`, and a linked worktree derives both
  from one slot off its path (`app/devPort.ts` and `server/ports.py`, kept in step by
  `make port-agreement`).

  **What this prevents is data loss, not a busy port.** While the port was the constant 8000
  in every tree, whichever server won the bind answered every tree's UI — so a branch could
  drive the owner's real 767-card inventory, or, worse, the MAIN tree's capture screen could
  be answered by a worktree's server and write real card photographs into a directory that is
  deleted with the branch.

  `make status` prints this tree's ports and says when it is a worktree; the SessionStart
  guard prints them before any work starts; `make server` prints them and names the store it
  is about to serve. **If you are looking at an empty inventory in a worktree, that is
  correct** — the real one is the main checkout's.
- **Real CSV libraries only** — PapaParse (JS), `csv` (Python). Never `split(",")`.
- **Not a Claude artifact**: no `window.storage`, no `facingMode: "environment"`, and nothing
  about a card or the inventory in `localStorage`. Inventory state is server-side, in the
  store; the camera uses a device picker. Two devices share one truth.

  **Nine keys are stored on the device, and each is a fact about THIS machine rather than
  about a card**: `banchi.capture.deviceId` and `banchi.capture.rotation`
  (`app/src/useCamera.ts` — which camera and which way up, meaningless on another machine),
  `banchi.theme`, `banchi.rail`, `banchi.orders.fetch-filter`, `banchi.inventory.hide-sold`,
  `banchi.box-recency` and `banchi.capture.setup` (`app/src/deviceMemory.ts` — how this
  browser is dressed, which order statuses this device bothers fetching (D114), whether the
  inventory walk folds sold rows away, when THIS browser last reached for each box, and the
  setup the operator last worked at), and `banchi.orders.last-check` (`app/src/Orders.tsx` —
  when THIS device last checked TCGplayer, so a fetch receipt can say what is new since; the
  owner ruled it belongs there on 2026-09-03). None of them is a card, a position or an order.

  **TWO OF THE NINE ARRIVED ON 2026-09-11 AND ONE OF THOSE IS A RENAME**
  (D142). `banchi.capture.setup` is the box, game, set hint, finish, rarity
  and product the operator last chose — six values that were `sessionStorage` under D27 until
  the owner overruled the session scope, in ONE document because they are one habit, the
  argument `banchi.orders.fetch-filter` already makes for its own two fields.
  `banchi.box-recency` is `banchi.inventory.box-recency` renamed: the capture screen's box
  list now sorts on it too, so the name had stopped saying what the fact is — which drawer
  this operator's hand is in — and started saying which screen happened to write it. **No
  migration, D27's own rule**: what a browser held under the old spelling is abandoned, which
  costs one sitting of the fallback order (fullest, then number) until the first box is
  opened or captured into.

  **This sentence said FOUR and listed five, from 2026-09-03 until 2026-09-06**, and it named
  the wrong two files for the theme and the rail — `kit/index.tsx` and `App.tsx` are where
  those preferences are USED, and `deviceMemory.ts` is the module that exists to hold them,
  created for that reason by the lint rule below. Both errors are the shape this repo makes
  mechanical rather than hand-corrects: `make docs-audit`'s `storage keys` row reconciles the
  count, the roster and the files this paragraph names against `app/src`, in both directions.

  **A SEPARATE STORE HOLDS TWO MORE, AND THEY ARE NOT THESE.** D27's carve-out is
  `sessionStorage` — `banchi.session.captureId`, the in-flight id of a capture whose response
  was lost, and D39's handoff `banchi.run-scope`. A new tab is a new shift and closing the
  browser ends one, and for these two that is the POINT rather than an accident: a restored
  `captureId` is a banner asking the operator to re-feed a card that was recorded yesterday,
  and the honest answer to it burns a position under D10's high-water mark.

  **IT HELD EIGHT UNTIL 2026-09-11.** Six of the capture screen's seven — `banchi.session.box`,
  `.setHint`, `.finish`, `.game`, `.rarityClaim` and `.product` — moved to the device
  (D142), on the owner's report that a shift ends when they stop feeding
  cards rather than when a tab closes. `captureId` did not, and it is the one the carve-out
  was always about: a stale SETTING is a claim on screen that is one press from being right,
  and a stale in-flight id is a request for a card nobody is holding.

  **EVERY BROWSER-STORAGE KEY IS `banchi.*`, AS OF 2026-09-06** (D27, amended). Ten of the
  thirteen keys there were then were `pkmnscan.*` until that day — not by a rule, but because that is what a key
  written before the rebrand got — and the owner renamed them **with no migration**, having
  declined a read-time fallback on the ground that a fallback can never safely be deleted
  afterwards. The old values are abandoned in place. **This does not reopen D94**, which is
  about the checkout, the CLI, the packages, the store, the wire and `PKMNSCAN_HOME`: a
  storage key is a name this product writes and no other program reads, which is what
  separates it from every item on that list. What it cost is in D27 by name — two presses on
  the rig, six on an open capture tab, and one key (`captureId`) whose loss D27 itself says
  can burn a position if a capture was in flight at the moment the new build loaded.

  **The rule has a reader now.** `app/eslint.config.js`'s `no-restricted-syntax` bans
  `localStorage` across `app/`, with `useCamera.ts` and `deviceMemory.ts` exempted by name and
  a handful of argued call sites carrying an inline disable: `Orders.tsx`'s two, and the specs
  that seed or read back the very key they are about. A guard
  that is routinely disabled inline is one the next person disables without reading, so the
  exemptions are few and each one says why beside the key. **The lint rule matches the STORE
  and not the key**, so it can say nothing about which keys exist or what they are called;
  that is what the `storage keys` audit row is for.
- **Never emit duplicate SKU rows** in an import file — undefined behavior. Aggregate
  by SKU with `Add to Quantity` = copy count. **THERE IS NO STANDING CAP ON THAT COUNT AS OF
  2026-09-07** (D7, rewritten): every copy the run holds that TCGplayer does not already have
  goes out. The operator retired both of D7's reasons for the playset bound by name — an
  envelope-buster order, and how many copies a spike sells at a stale price — and the answer
  to each was *"neither still applies"*.

  **A cap is now something a SEND asks for**: `emit --cap N`, and the field beside the other
  emit options on `#/pricing`'s ship bar. **AND A QUANTITY IS SOMETHING A SEND ASKS FOR PER
  CARD** (D7, amended 2026-09-11, on the owner's report that they could *"no longer select
  quantities to sell at all"*): `emit --quantity SKU=N`, and the Qty field on every `#/pricing`
  row. That one is a SEND QUANTITY and not a ceiling — 2 sends two whatever TCGplayer holds,
  bounded by the copies on hand that are not already listed; 0 sends none without a hold — and
  it is spent by the write, so nothing standing changes. The two compose to the tighter. **`policy.live_cap` IS DELETED as of 2026-09-08** —
  `--cap` is the only place a cap is named, and a store still holding the key is refused by
  name rather than silently uncapped. `policy.per_run` survives for its other four keys.
  It was a promise D7 made and nothing built until 2026-09-06: the parameter was threaded
  through `SkuMatch`, `join` and `resolve.load` from the start and no caller ever passed
  anything but the module default. `pipeline/pricing.py:LIVE_QUANTITY_CAP` is still 4 and is
  now the figure the press OFFERS, never one a send inherits.

  **WHAT THE CAP WAS NEVER DOING IS STOPPING A COPY BEING SENT TWICE**, which is what makes
  removing it safe: `add_to_quantity`'s own docstring separates the two jobs, and
  `uncommitted_positions` — the half that does that job — is untouched. Measured on the
  harness: uncapped, a SKU with six copies of which three are already live offers **3**, not
  six.
- **The pipeline is reachable from a screen as of 2026-08-24** (D33), **and lives on `#/runs`
  since 2026-08-29** (D39). Not folded (D33, amended): a free preflight, a two-step money gate
  with no typing, the three free steps, every command's stdout verbatim, and the import CSVs as
  downloads. `server/pipeline_routes.py` is its own module because it is the one part of the
  server that can cause money to be spent — one route does, it is named for it, and it refuses
  without an explicit `confirm`. Everything else there is free and re-runnable.

  **A run's scope is a box, or cards ticked inside one, and only ONE of those is answered on
  `#/runs`.** The box has a picker there. The ticked selection has no second mass-select and
  never will: `#/inventory` keeps the only one and hands it over through
  `app/src/runHandoff.ts`. Anything that rebuilds a selection on the runs screen has recreated
  the disagreement D33 named and D39 was built to avoid.
- **A card's number counts the cards in the box, not the slots** (D58). Sell card 17 and the
  card behind it becomes card 17, on every screen and in every report — the box closes up, and
  the section boundaries move with it so `Section N · Card M` is countable on both axes. **The
  STORED index never moves**: it is the `/inventory/<box>/<index>` path, the `<index>.jpg` the
  photograph is named after, and what every write aims by, and `next_index` is the high-water
  mark D10 has always made it. `Place.slot` is the number a person counts to and `Place.index`
  is the key; they differ by the cards that have left in front of this one. A departed card is
  in no slot and renders `join.departed_label` — `Box 3 · departed` — rather than the number
  that now belongs to its successor. `pipeline/join.py:Position` is still the only label
  formula; what it gained is the box's occupancy. **The dividers editor speaks the same space**
  and `do_put_box` maps it back through `join.divider_index` before the store sees an index.

- **A SET HINT ON SOME CARDS NARROWS NOTHING, AND HOW WIDE TO ASK IS A PER-GAME RULE** (D76).
  The Filtered Export is fetched to a scope this process names (D65), and the scope is decided
  by three voices in order: an explicit `set_ids` from the operator, then the game's own
  `export_scope` in `pipeline/games.py` — `category` for riftbound, whose whole 10,078-row
  English catalogue is one file, `sets` everywhere else — then the run's cards. **The cards may
  narrow only when they are UNANIMOUS**: every card of that game carrying a hint, and every
  hint resolving. D65's first build collected the hints that existed and never counted the
  cards carrying none, so one hinted card in a 200-card box scoped the whole export to one set
  and the other 199 queued `no_catalog_row` behind a fetch that reported success.

  `GET /pipeline/runs/<name>/scope` draws all of it before the button is pressed and presses
  nothing; `#/runs` renders it, and `asked.reason` says which voice chose. **`--rule` and
  `--basis` are deliberately NOT on that screen** — D49 makes ONE FILE the place a pricing
  answer is written and `#/pricing` the press that writes it. That file is
  `inventory/prices.json` since D86's amendment, not `runs/<n>/decisions.json`; the ruling is
  unchanged and the file moved.

- **THE PRICING ANSWER IS ONE FILE FOR THE WHOLE STORE, KEYED BY SKU** (D86, amended
  2026-09-02 on the owner's question). `pipeline/corpus.py` over `inventory/prices.json` holds
  every listing answer — a price, or a hold with its reason, watch and note — plus the standing
  `rule`/`basis`/`sub_threshold`. A run directory carries NO pricing answer any more.
  **`sub_threshold` has a default — flat $0.49** (`pipeline/corpus.py:DEFAULT_SUB_THRESHOLD`;
  D9 amended 2026-09-02), applied where the key is absent or null and written on the next
  save, so a fresh store's first emit is not refused for want of an answer already given once.

  **`policy.threshold` IS THE FLOOR AS WELL, AND THERE IS NO `policy.floor`** (D9, amended
  2026-09-09). Three roles, one figure: the market price at or above which a card earns a
  listing, the price the cheap half goes out at, and **the price no rule and no markdown may go
  below**. `pipeline/join.py:SkuMatch.list_price` clamps at `SkuMatch.threshold`, `prices_for`
  resolves a legacy `"floor"` disposition at it, and `cli/cmd_reprice.py` hands it to
  `reprice.plan` and `reprice.read_back`. **`pipeline/pricing.py:FLOOR` is now only two things**
  — the default for a caller with no store behind it, and the **labor bar** the two
  `Decisions.warnings` name, which is what D9's $60/hr derivation actually is.

  **D9 said "both configurable" and only the threshold ever was.** What the gap cost, on the
  owner's real store: the cut-off said $0.29, `reprice apply` refused **293 of 354 rows** as
  `below_floor` against the constant, and `import.csv` carried **49 SKUs** — with all 342 answers
  already written into `prices.json`, so the screen, the corpus and the receipt agreed the work
  was done while the spreadsheet TCGplayer reads carried a seventh of it. Pointed the other way
  the same gap priced a card the operator's own cut-off calls listable ABOVE its market —
  market $0.32, `match`, clamped to $0.40. **A separate floor key is coherent only when it
  equals the cut-off**, so it could only ever be set wrong; D99's ruling on the other pair is
  the same ruling.

  **Why it moved: a run's `decisions.json` held two different kinds of fact.** `rule`, `basis`
  and `sub_threshold` are arguably properties of the lot (D48); `overrides` and
  `no_market_data` are properties of the CARD (D7 — *"price is per-SKU and shared across
  copies"*). Stored per run, one card carried one answer per drawer it had been photographed
  in: **66 SKUs, 8 answered twice, 3 of those a `withheld` hold answered by a later price** —
  SKU 9191210 held bullish above $5 out of box 3 and listed at $3.45 out of box 4 the next day,
  drawn as an ordinary row with no note anywhere.

  **The migration is `pkmnscan prices adopt` and it previews first.** Newest-wins, and it names
  the holds a later price replaced rather than counting them. `--write` RETIRES each folded
  file to `decisions.json.adopted`, and a re-adopt over answered SKUs retires without `--force`.
  **A legacy run file is never read as a fallback** — that would put the duplication back on
  the first re-join of an old run — so `join` and `emit` refuse UNCONDITIONALLY, before
  anything is read or written, with a sentence naming `prices adopt --write`. That refusal was
  gated on an EMPTY corpus until 2026-09-02, and eight files on the owner's store sat ignored
  behind it.

  **What is per-run still: a POLICY override**, `Corpus.overrides`, for the lot that genuinely
  wants its own `sub_threshold`. Nothing writes one today; D86 names that as a reopening
  condition rather than leaving it to be discovered.

- **THE STORE OF RECORD IS ONE SQLITE FILE, AND `inventory.json` IS A LEGACY FILE READ BY
  NOTHING** (D88, 2026-09-01). `inventory/store.sqlite` holds cards, boxes, listings, the
  identification cache, both standing queues, the order ledger and the history, one table
  each, and every `Store.write()` is ONE transaction over all of them — the five-file torn set
  `store/session.py` spent a week calling "a decision nobody has argued" cannot happen
  now. `Snapshot` is still the API and `inventory.cards` is still a dict to every caller
  (`store/rows.py`), but a session bound to the database loads only the rows a method names:
  a capture into a 100,000-card store builds ONE card object and commits in ~3 ms, where the
  JSON cycle took ~4 s. **The first open of a legacy store migrates it** — without loss, under
  the lock, moving the six JSON files to `inventory/legacy-json/` with a receipt — and a JSON
  file left beside the database is never a fallback (D86's rule): `make status` reports one.
  Look at the store with the `sqlite3` CLI; the owner ruled no JSON export target is wanted.
  What is NOT in the transaction is what never was: photographs, sidecars and `codes.jsonl`,
  written inside the flock, which is why the flock survives.

- **A SOLD CARD'S PHOTOGRAPH IS RECLAIMED ON PURPOSE, AND THAT IS A THIRD SHAPE** (D89).
  Capture-undo deletes the record and the photograph (D10); `sold` and `retired` keep both
  (D26). `POST /boxes/<box>/photos/reclaim` deletes the photographs of a box's SOLD cards and
  keeps every record, each carrying `photo_sha256` and `photo_reclaimed_at` from then on. Sold
  only: a retired card's photograph is what lets the retirement be questioned, and a card on
  hand needs its photograph for the pull preview. The control is in `#/inventory`'s **Manage
  box** sheet, gated like the box delete and shaped like the listing release — the free count
  (`GET /boxes/<box>/photos`) is on screen before the control that fires exists. What it gives
  up is named: D36's realign can no longer re-bind THOSE cards by digest, which is right for
  cards that have left the box, and the digest on the record is what the history keeps.
- **`emit` OVER SEVERAL RUNS WRITES ONE FILE, AND A CAP IS SPENT ONCE ACROSS THEM** (D86).
  `pipeline/join.py:add_to_quantity` spends `live_cap - copies_out` per RUN against a cap that
  is GLOBAL, so runs joined before either emitted each believe the whole cap is theirs. This is
  D59's defect one register up — that entry fixed the per-BOX version inside one join, and the
  per-RUN version survived it because nothing had ever looked at two runs together.

  **The heading said THE cap until 2026-09-07 and now says A cap** (D7, rewritten): with no
  standing bound this arithmetic does not run at all, and a merged send is still one file for
  the OTHER reason D86 gives — `pipeline/merge.py` dedupes the union of positions on
  `(box, index)`, so a card in three boxes is one row. The moment a send asks for `--cap N`
  the paragraph above is live again, and `cli/cmd_emit.py:_cap_for` applies that one figure to
  every leg for exactly this reason.

  **Measured at the old standing cap of 4, from an identical cleared ledger over three real
  runs**: three separate emits wrote 6 files, 511 copies and **2 SKUs past it** — the same two
  that sit at `pushed: 6` in the store today. One merged emit wrote 1 file, 437 copies and
  **none**. **A merged file can never be a concatenation of the per-run CSVs.**

- **There is no automatic sectioning, and `CARDS_PER_SECTION` NO LONGER EXISTS** (D10,
  amended 2026-08-29 by the owner). A box's sections are the dividers somebody put in it and
  nothing else: an undeclared box renders as ONE section, `card` is the index, and
  `pipeline/join.py:Position.layout` falls back to `(1,)` — the divider at the front of every
  box. The 25-cards-per-divider default that used to render an undeclared box is deleted, so
  **the labels of every undeclared box moved once, deliberately** (the owner's box 1: 133
  cards, no dividers, drawn as six sections until this landed).

  **A divider is put in from the capture screen with `S`, at the moment the real one goes into
  the box** — `POST /boxes/<box>/sections`, which takes NO index because
  `store/master.py:open_section` reads `next_index` inside the store lock. The set hint moved
  to `H` to free the letter. A whole layout is still typed on `#/inventory`'s dividers editor;
  neither path ever invents a divider.

- **A box is addressed by its name, and names are unique** (D20, amended 2026-08-25). The
  capture screen's Box field is ONE free-text control searching number and name together, and a
  new box is created by name — `store/master.py:next_box_number` allocates the lowest free
  integer inside the lock, so there is no number to mistype and `new_box`'s typo guard is
  history. A duplicate name refuses `BoxNameTaken` / 409 `name_taken`; comparison folds case
  and strips, storage is verbatim. **`next_box_number` is deliberately NOT D10's high-water
  mark** — that rule governs the card index inside a box and nothing else. The name never
  enters `Position.label`: `app/tests/fulfillment.spec.ts` floors that label and D31 keeps the
  spec unweakened, so the name travels as `box_name` beside it instead.

  **A run carries the name the same way, and it is joined at read time** (D56). Every run on
  the wire has `box` and `box_name`, put there by `server/pipeline_routes.py:_summary` — the
  box from the manifest's scope or from its capture directory, the name from the registry as
  it stands right now. **Never write a name into a run directory**: a rename relabels every
  card in the box on every screen that draws one, and `cli/runs.py` makes a run an immutable
  input, so a stored name would be an answer nobody could correct. `app/src/runScope.ts` is
  the one place the client reads either — `Box 3 · RB Epics`, and `Box 3` ALONE where the box
  has no name, because a name is optional and a placeholder would draw a fault where there is
  none.

Deeper schema facts (Condition strings, secrets like `161/159`, blank-Number rows,
apostrophes in names) live in the `tcgplayer-csv` skill. It loads on demand.

## Hard rules

- **A route is not a feature. Nothing is built until it is reachable from a screen.**
  A capability that exists only in `server/` is not done, is not "landed", and must never be
  reported as either. Done means the whole chain: the route, a client function in
  `app/src/server.ts`, a control on the screen a human would look for it on, and — where it
  writes — its receipt and its way back. If a session ships the server half, the remaining
  half is not a follow-up, it is the unfinished part of the same task, and the session says
  so in those words.

  **The owner's instruction, 2026-08-23, after finding three tested routes no screen could
  reach**: box delete, mid-box delete-with-reindex, and retroactive box-level claims all
  existed with full T7 coverage and *zero* client functions. `make harness` was green,
  `make check` was green, and none of it could be used.

  This is the repo's own recorded failure repeating. `docs/GATES.md` step 7 tells it at
  length: 7b shipped with three screens missing from `App.tsx`'s ROUTES table while harness,
  lint, typecheck and docs-audit were all green, and only `make design-check` — which is
  deliberately NOT on the commit path — could tell. The finding it recorded then is the
  reason this rule exists now: **nothing on the path that decides whether a commit proceeds
  looks at whether a human can reach the thing you built.** So it has to be a rule someone
  reads, because it is not a check anything runs.

  Corollary for the report format below: a wrap-up that says BUILT about a server-only
  capability is wrong, not merely incomplete. It goes under NEITHER until a screen reaches
  it.

- Never guess an identification, a variant, or a price. Ambiguity goes to the review
  queue with its photo. Never silently drop a card.
- Never write output before reporting unmatched rows in both directions.
- Scope is argued, not gated. New surface area needs a reason and a decision entry — it no
  longer needs a gate to pass first, because none is open. This rule used to read "No new
  surface area until the current gate passes."
- No manual third-party UI step inside the autonomous pipeline. External tools without
  an API contract can be benchmarks, never components.
- **Opsec, repo-wide**: a live unredeemed code card is a bearer instrument. No code-card
  photo in a listing, README, screenshot, or commit. Enforced by pre-commit hook.
- **A screen answers to the system.** New CSS reads `--bn-*` tokens and never names a color;
  a primitive the kit already has is not rewritten in a screen sheet; a screen is verified at
  1440, 820 and 390, in light and in dark, before it is called done. **`docs/DESIGN.md` is
  where that system is written down, and it describes this tree** — it was rewritten for Banchi
  on 2026-09-03, its token block is the `--bn-*` set, and `make docs-audit`'s `design tokens`
  row locks every name in both directions. These two paragraphs said the opposite until
  2026-09-07: that the block recorded a palette the app no longer paints and that the audit
  "says so on every run". It does not, and did not — the row prints `ok` and has since the
  rewrite. **A claim that a check is red is worth checking against the check.**
- **Main moves by pull request. A session never commits to it and never pushes it.**
  Work goes on a branch, the branch is pushed, `gh pr create` opens the PR, and it is merged on
  GitHub. `main` then advances in this clone by `git pull` and no other way.

  **A session merges on the owner's word, on GitHub and in this clone, as one operation**
  (D42, amended twice 2026-08-30). Explicit and per-instruction. **The test is whether the
  owner NAMED THE ACT** — "merge", "merge it", "merge to main" all are the word; "ship it",
  "land it", "looks good" and an approving review are not, because they approve the work
  without naming the operation.

  **One word, both halves, and a session does not stop in between to ask again**: `gh pr merge`,
  then the local fast-forward. If the second half fails, report it as an incomplete operation
  rather than re-asking for permission.

  **`make merge ARGS="<n> --confirm"` is that whole operation**, and `ARGS=<n>` alone previews
  it and presses nothing (D42, amended 2026-09-01). It does the GitHub half, fetches origin,
  asserts the merged commit is on `origin/main` — allow rule 3, checked BEFORE anything moves
  rather than discovered when the hook refuses — and then picks between the two local forms
  below by asking git rather than by remembering. **It automates the lookup and never the
  decision**: a bare `make merge` refuses, and the word is still yours.

  **The two commands stay written out here on purpose.** A wrapper that becomes the only way
  anybody knows the answer is a worse outcome than the one it fixed, and when it is not what
  you want, this is what you type.

  **The local half is two states, and one question tells them apart.** Ask which working tree,
  if any, holds main — a clone running several worktrees is in either state on any given day,
  and the command that is right in one is refused in the other:

  ```bash
  git worktree list --porcelain | awk '/^worktree /{w=$2} /^branch refs\/heads\/main$/{print w}'
  ```

  **Nothing printed — main is checked out nowhere.** Two commands, never the combined refspec
  alone: that form moves `refs/heads/main` and `refs/remotes/origin/main` in ONE transaction,
  which leaves the hook judging the move against the origin/main it is about to replace.

  ```bash
  git fetch origin && git fetch origin main:main
  ```

  **A path printed — main is checked out there.** The form above is what git itself refuses
  against a branch somebody is standing on (`fatal: refusing to fetch into branch
  'refs/heads/main' checked out at …`), and that refusal is GIT's rather than the hook's, so
  `PKMNSCAN_MAIN=off` answers nothing. Pull in that tree instead:

  ```bash
  git -C <that path> pull --ff-only
  ```

  **Never run that one without asking the question first.** It is correct only while main is the
  branch in that tree; run blind while the main working tree sits on a feature branch, it
  fast-forwards THAT branch, moves no protected ref, and so trips no hook.

  **It arms nothing.** `reference-transaction`'s allow rule 3 has always permitted a move to a
  commit origin already has, and a merged PR is exactly that commit — so this decides who runs
  an already-permitted move, not which moves run. **`PKMNSCAN_MAIN=off` is not what a session
  reaches for to do this**; a session typing that variable is doing something else.

  **This is enforced, not asked for** (D42): `scripts/githooks/reference-transaction` refuses
  any local move of `refs/heads/main` and `scripts/githooks/pre-push` refuses any push to it,
  both armed by `make hooks`. The escape hatch is `PKMNSCAN_MAIN=off` and it is printed in
  every refusal — reach for it rather than for `core.hooksPath`, which would take the three
  opsec rules down with it.

  **Why it is a hook and not a line in this file**: it already was a line nobody had written,
  and main moved under three live worktrees twice on 2026-08-29 — once by a local
  fast-forward, once by a direct push. A refusal is not a bug report: it means put the work
  on a branch.

  **GITHUB'S OWN BRANCH PROTECTION IS ON AS OF 2026-09-06, and the hooks did not become
  redundant** (D42 amended). It was unavailable when D42 was written — 403, free plan,
  private repo — and the owner's upgrade to Pro turned it on: a PR is required, force-push
  and deletion are refused, and `enforce_admins` is true, so it binds the owner too. The
  escape hatch is now a deliberate settings change rather than an env var.

  **The two guards catch different halves, which D42 predicted in as many words.** Branch
  protection bites at `git push` — it would have caught the second incident and been SILENT
  through the first, because a local fast-forward moves `refs/heads/main` without touching the
  remote, and every session cut from main is already on a different history by then. The
  `reference-transaction` hook is the only thing that sees that. So: the remote gate is real
  now and the local one is still the only cover for the local half.
## Working agreement

- Run `make harness` before you tell me something works. Show me the output, not a claim.
- **Show me the screen before you tell me it looks right.** Render it at 1440, 820 and 390 in
  both themes and look at the images. A screenshot you did not open is not verification, and
  the one thing a typecheck cannot tell you is whether the thing is any good.
- Read docs/DECISIONS.md before proposing an architecture change. Every entry there is
  settled; if you want to reopen one, say which entry and why, and wait for me.
- Report format: result first, then files touched, then risks. No task restatement, no
  summary of what I asked for.
- **Design work is repo work.** A design, a parameter derivation, or a determination that
  exists only in the conversation is NOT done — it lands in `docs/specs/` or a decision
  entry in the same session that produced it, or it is declared abandoned. The session
  that designed the motion trigger spent its tokens twice because the design lived in
  chat while the repo still said "not built, not specified"; this rule is that session's
  receipt. Corollary: **every wrap-up states what is BUILT, what is RECORDED, and what is
  NEITHER** — the same specified/built/validated vocabulary the gates already use, applied
  to the report itself. "Solved" with no bucket named is the phrasing this repo does not
  accept.
- When compacting: preserve the fixture schema facts, every `make` command, and the list of
  modified files. Drop exploration narration.

## Map

- `docs/map.py` — the repo as data: what is built, what is TBD, and which decisions govern
  each file. **Read this before editing anything under `app/`, `server/`, `pipeline/`,
  `identify/`, `store/`, `geometry/` or `cli/`** — every entry there is settled and
  re-litigating one wastes a session. Audited by `make docs-audit`, so it cannot quietly go
  stale: adding a file under any of those without an entry fails the commit.

  **`make map` is how you look at it, and there was no way to until 2026-08-31** (D80). At
  2,700 lines and ~56,000 tokens a Read of the whole file spends a fifth of a context
  window, so in practice it was written constantly and read never — 75 commits touched it on
  2026-08-30 alone. That asymmetry is not academic: its `COMPONENTS` section, which three
  consumers read, was measured at **142 of 155 entries written at or after the file they
  describe last moved**, while `TRACKS`, which NOTHING read, was wrong in two ways for three
  weeks. **A section of this file with no consumer is now a failed commit** — `make
  docs-audit`'s `map sections` row — because a claim with no reader has no way of ever being
  contradicted. `build order mirror` reconciles the step ids against `docs/GATES.md`'s two
  lists, per list and in both directions — a claim the map's header had made since
  2026-08-04 with nothing verifying it.

  **The build order is two lists, `SHIPPED` and `OPEN`, and it was one numbered list telling
  a lie its own shape forced on it until 2026-08-31** (D80). Rendered the only way a numbered
  list can be, `make status` said *"Build step 9 of 15"* — while 13, 14 and 15 were done, 9
  had been deferred by choice for a week, and everything from D34 onward had landed under no
  step at all. Every row was true; the sequence the numbering implied was not. `SHIPPED` is ordered
  by the date work landed, `OPEN` is **not ordered and has no `next`** — ranking two open
  items is yours, and "exactly one step is next" is what forced a false answer to it.
  **`n` is a stable id, never renumbered**: 218 references to `step <n>` live in this tree,
  74 of them `step 7`, and a renumber leaves every one pointing at a real step that is not
  the one meant — which nothing can detect, because a stale number still resolves. Steps 16
  to 19 were added for work that had landed with no step, and **step 12 was culled**, the
  only row ever removed: it named no deliverable and its "only then" pointed at the retired
  gating system.
- docs/DECISIONS.md — settled decisions and why. Read before redesigning.

  **These three are NOT `@`-loaded, and that is deliberate (D60).** At 627KB they cost
  ~163,000 tokens in every session before a word of work, and a session needs one entry
  at a time. Two mechanisms answer that without loading the file: `scripts/decision-context.py`
  names the governing decisions before any edit under the mapped directories, and the index
  below says what exists. **Read the entry itself before proposing an architecture change** —
  the index is a table of contents, never a substitute for the argument in the entry.

```
D1   Two-phase architecture
D2   Identification is Claude Haiku vision, owned end to end
D3   Variant resolution ladder
D4   Review queue is digital-only
D5   Two personas
D6   Photo service and pull preview
D7   Duplicates aggregate by SKU at join time
D8   Pricing source is the TCGplayer Filtered CSV export itself
D9   Threshold and floor are both $0.40
D10  Inventory model
D11  Listing path is a catalog join, never a from-scratch CSV
D12  Scope
D13  Stack
D14  Two tracks, one rig
D15  Catalog data is vendored, not fetched
D16  The docs are checked mechanically; the prose is checked by asking
D17  The repo describes itself in `docs/map.py`, and the map is audited
D18  A generator may write. Nothing that writes may gate a commit.
D19  Motion capture: live fire behind the seam, a trace for tuning, video for neither
D20  A box is an object, and its capacity is retroactive
D21  Game is a per-card claim, not a mode
D22  Taxonomies are hand-authored per game, and audited so they cannot drift
D23  The rarity claim does three jobs, and one of them pays for the feature
D24  Code cards are pooled inventory, not located
D25  The join partitions by game, and `Product Line` becomes a real reader
D26  A card leaves inventory by a state — `retired` — and a bad photo is replaced in place
D27  Session state is device-local and may be persisted
D28  The review answer gets an undo window, and the list stops moving under it
D29  A homogeneous queue may be answered as a group
D30  The physical convention for a gap
D31  One owner-side view of stored cards, and the Fulfiller does not get a vote on it
D32  The pixel budget is spent on the card, not the desk
D33  The pipeline is reachable from a screen, and one route can spend
D34  A listing hold is released against the releasing box's own copies
D35  A number that cannot be read falls back to the name, and the card still faces a human
D36  The run says what the model read; the store says which slot it is in
D37  A queued question can be closed without answering it, and the card is left alone
D38  The photograph is sized by the rows beside it, and the box and the runs get the third column
D39  The pipeline gets a route, and the selection is handed to it
D40  The screen is three columns: the box, the card, and where its copies are
D41  The address is a rank, not a list, and the separator is deleted rather than replaced
D42  main moves by pull request, and the guard is local because the server-side one is not for sale
D43  the port follows the store, because the store was already per-checkout
D44  an iCloud conflict copy is refused at the commit and never deleted on a guess
D45  The copies list is a way back into the walk, and the filter yields to the jump
D46  A card the pipeline could not place is offered the catalog, and a human may point at a row
D47  A tracked symlink is a path baked into the tree, and a checkout will spend a directory to place one
D48  A send is a cart of boxes; a run is still one box
D49  The pricing answer is one file, and a card can be held back on purpose
D50  An interactive element's feedback is the product's, not each stylesheet's
D51  Cmd-arrow steps the strip in the order it is drawn, and it is the one modifier the shell takes
D52  The photo URL names a photograph, because a slot's occupant changes under it
D53  One link, always live, and the restart discipline becomes machinery
D54  A re-emit adds; it never subtracts
D55  A set code the model glued on is removed by shape, and only after the key has missed
D56  A run names the drawer it was over, and the name is joined at read time
D57  The sale is one press, and the button becomes the way back
D58  A card's number counts the cards in the box, not the slots
D59  The live cap is a per-SKU quantity, and a count of one run's positions was answering for it
D60  The @-loaded docs are dense American technical English, and an entry cites rather than restates
D61  The shipping lane is three lanes, and the third answer is "I cannot tell"
D62  The price history is reachable, and it is drawn beside the hold rather than beside the location
D63  The order ledger is two maps, and the sync writes only one of them
D64  The Filtered Export is fetched, and completeness is a delta rather than a claim
D65  The export is asked for, and the box's own claims are the scope
D66  The order screen comes before the transport, and the shipping lane needs neither
D67  The number a screen draws is composed once, and the set code D55 strips for the key is stripped for the eye
D68  A departed card's label names the record, because two of them in one box were the same string
D69  The order screen and the shipping lane get a route each, and the transport was measured before it was written
D70  The QR is the whole identification, the product is a claim, and the card is destroyed
D71  A card with no slot is ranked like every other, and it is the figure that goes
D72  A renumbered entry takes its citations with it, and the branch's own history is what says one moved
D73  The boot header says the code changed, nothing says the data did, and only one of those is a citation error
D74  A document is checked as a document, and every markdown file is linted rather than the four a session loads
D75  A detector that cannot say "wrong" is asked a second question, and the crop is refused rather than trusted, and the shape correction reaches both crop paths
D76  A hint is evidence about its own card, and how wide to ask is a per-game rule
D77  The pipeline's rows can be the wrong card, so the export is reachable from every entry — asked for, never offered unasked
D78  A run's reason for adding nothing is a heading, the rows under it sink, and a hold sinks on the reopening
D79  The reading goes on every row, because the operator answered D62's own measurement
D80  A section with no reader is deleted or given one, the build order stops pretending to be a sequence, and the map gets a view a person can use
D81  The presence gate is a distance from this session's own baseline, and the stillness thresholds are multiples of what this session measures
D82  Ruff is adopted on the slice this session measured, not on what it enables by default
D83  A card leaves a box through a third door: moved, not sold or retired
D84  A settle is a count over a window, the stall clock is cleared by a settle, and the presence floor is sized to a hand
D85  The corner is settled by geometry, and a variable nothing sets is not a fallback
D86  The pricing answer is one file for the store, and the worklist spans runs
D87  The reconcile is store-wide, and what it writes is `live`
D88  The store of record is SQLite, and a write is one transaction
D89  A sold card's photograph is reclaimed on purpose, and the record keeps its digest
D90  The envelope is the unit of the write, and an order drives the walk as a mode of the inventory screen
D91  The window is the range, the status is the filter, and the operator picks it from what the wire returned
D92  A bare `#` is the count, the key carries a sigil, and the check is what keeps them apart
D93  The copies panel is the picker, and a full line refuses the take
D94  Banchi is the product's name, and `--bn-*` is the vocabulary every screen speaks
D95  The shell is a rail, a palette and a reference sheet, and the Fulfiller's crash has no door out
D96  The screens answer to the owner's interview, and main's history is not the authority
D97  The copy map ranks and never picks, and a line says what remains
D98  The cheap-card figure is the control, the floor choice is retired, and a run may still differ from the store
D99  The cut-off is a figure the operator sets, and one press writes one spreadsheet
D100 Nothing is deleted to lower a price, the quantity is not a variable, and the age is a proxy that says so
D101 A claim a screen names is a claim a screen can fix, and the derived tuple outran its decoder
D102 The mark is an illustration with its own palette, and the spec is its store of record
D103 Staleness is a filter and not a gate, the record holds every live row, and the file that leaves the machine stays narrow
D104 The live export is fetched, and the second standing instruction is a second constant
D105 The markdown lives where prices are decided, and one file may not have two unguarded writers
D106 The push and the publish are two presses, and the second one is the only thing here a buyer can see
D107 The rule only ever marks down; the operator may point either way
D108 The dock app is the page Chrome already renders, and the manifest is what makes it one
D109 A price is a fact about a listing, and the store remembers listings it never photographed
D110 A hover is an alpha, because the same paint over three grounds is three different hovers
D111 Cleanup is a sweep, not a step in the merge, and liveness is read rather than guessed
D112 The labels are tracked, the images are not, and an unmoved measurement is asserted rather than re-derived
D113 A line closes three ways, and only one of them claims a copy went
D114 The status requirement is answered by a remembered tick, not by an echo of the preview
D115 The reading is what the export said, and what has sold since is counted beside it
D116 A card nobody has named is not a landmark, and the distance is what keeps the skip honest
D117 The thumb floor is the kit's, the measurement is the hit area, and a phone-width spec is what reads it
D118 A press changes what is on the screen, never where the rest of it is
D119 The copy the walk stands on is a row like every other, and the receipt lands where the sale was pressed
D120 The shell speaks one brand at every width, and the phone bar is a rail
D121 The front page says what is owed, and the library is drawn as the work that made it
D122 The suite takes a machine-wide lock, because the CPU is the one thing a checkout cannot have its own of
D123 Above the desk a screen asks its column, and browser zoom is not the lever it looks like
D124 The faces are vendored, and the suite's allow-list is two ports
D125 The photograph is cropped to the card, the focus is derived from the reading, and a reading that cannot be believed is a refusal
D126 The demo inflates its own history, and the present is left alone
D127 A session may stop what it started, and the checkout is what decides which that is
D128 The key listener is attached before the paint, because a press answers to what is on the screen and not to the render before it
D129 The verdict's line is fixed by the first Playwright that counts it right, and the rig's Node is not the thing that moves
D130 A feeder that never rests gets a second trigger, and the beat is measured not typed
D131 The ratchet gets an escape, a settle is one quiet frame of three, and the beat is the backstop
D132 Sold is folded away by default, the address leads with the name, the rail is ordered by the hand, and a section can be named
D133 A branch is judged by what it lands, and a file put back the way main had it is refused unless the branch says so
D134 A departed record is buried, not kept; the box goes; and the graveyard is where the departed are read
D135 Codex reads the same rules a Claude Code session does, through three symlinks and one reconciled hook roster
D136 The suite is sharded and never widened, a sleep is a wait and not an assertion, and a tree that passed is not tested twice
D137 The catalog is Near Mint by rule, because it was only ever Near Mint by accident of the file
D138 One process serves the product, Vite compiles and never serves, and the build is the server's job
D139 Which branch the primary checkout stands on is a fact about the live rig, and a warning is the ceiling
D140 The number is claimed at the merge, because what main has taken is not knowable before it
D141 The browser matrix runs when the change reaches what a browser draws, and the path list has a reader
D142 The setup outlives the browser, the box list is ordered by the hand, and one value stays on the old clock
D143 The claim reads the checked-out tree, so which tree that is must be established before anything reads it
D-settle-rescue  A card that will not settle is photographed off the quietest frame it manages, and there is one trigger again
```

**THE GAP THIS LIST CARRIED BETWEEN D116 AND D118 IS CLOSED, AND IT CLOSED THE WAY IT SAID IT
WOULD.** D118 was numbered while three branches were in flight over the two numbers above D115:
two worktrees both claimed the lower one, main took one of those on 2026-09-07, and a third held
the one between — which existed in no tree that could be read from main and so could not be named
in this list without citing a heading `docs/DECISIONS.md` did not have. D117 is that third, and
it arrives with this branch and slots into its own gap rather than appending after D119, because
`decision index` reconciles this list against the headings IN ORDER. **The rule that produced all
of it is the one this repo has always kept: renumber your own, never another's** — and the other
of the two branches did exactly that, moving up rather than taking a number main had since
filled.

**D90 to D93 are MAIN's and arrived with the merge**, and three of the four are recorded here
without being adopted: the envelope walk and the copies picker were declined in favor of this
product's own per-copy walk and copy map, and the card-number sigil is deferred. D96 carries the
owner's reasoning for each. **D99 is numbered where it is because main took D90 while this branch
was open** — the rule is renumber your own, never another's.

- docs/GATES.md — gates, harness contract, `## What shipped` and `## What is open` (D80).
- `docs/DEBTS.md` — known gaps in the verification tooling, deliberately unfixed. Read it
  before treating a green `make docs-audit` as coverage: it means the checks that exist,
  passed. Nothing in it blocks anything; it exists so no session rediscovers it by surprise.
- `docs/specs/order-pipeline.md` — steps 8 to 14: an order arrives, a card is pulled, an
  envelope is stamped, tracking goes back. Every number in it was
  measured rather than carried forward — section 6 names what it could not check. **Those numbers
  are perishable and the file says so**: the store moved three times in two days, and §1 carries
  all three snapshots rather than the latest. Finding one stale means the store moved.
  **Steps 8 to 12 are BUILT as of 2026-08-30 (D69)**: `#/orders` resolves an order to the copies
  that fill it and pulls them, `#/shipping` routes a real export into three lanes, both reachable
  from the nav, and `server/order_transport.py` fetches this account's own orders over the cookie
  session D69 measured — `search` has run authenticated and returned three real orders.
  **THE LEDGER HOLDS 20 REAL ORDERS as of 2026-09-02**, and the store of record is
  `inventory/store.sqlite`'s `orders` table (D88) rather than `inventory/orders.json`. This
  pointer said that file "has still never held a real one" until 2026-09-05, which was true when
  written and wrong on both counts by the time it was read — the ledger filled, and the file it
  named had already stopped being the store. What it was right about stands: "pulls a real order
  out of the ledger" was a screen's capability read as a history, and all forty-two sales in §1's
  measurement went through `#/inventory` instead. **§3's T2b — the Rubber Stamp fill,
  `POST /shipping/batches/<batch>/stamps` — is BUILT as of 2026-09-05**, route, client and a
  control beside the download on `#/shipping`; the label in the operator's hand is the pick
  instruction. It fills all three corners or none and stamps what is still OWED rather than what
  has been pulled, which matters because D58 closes a box up behind a departed card, so an index
  stamped after the sale names a different card. Eight of those 20 orders hold more than three
  copies and so get no stamps at all; the spec's §T2b carries that measurement and names the
  register change it argues for. **Steps 13 and 14 — the shipped status
  and the tracking write-back — are NEITHER.** Their two endpoints were seen on the wire and deliberately not built. It said
  "Recorded, not built" and named three unreachable modules under `pipeline/` until D66's build
  order was discharged. **§3's T6 — an order DRIVING the inventory walk, with the envelope as the
  unit of the write — is SUPERSEDED** (D96 amended 2026-09-04), and its code is deleted:
  `POST /orders/fill`, `do_order_fill`, `app/src/orderWalk.ts`,
  `app/src/OrderWalkBanner.tsx`/`.css` and harness T7's `check_order_fill` are all gone, 1,484
  lines that were main's build and were reachable from no screen here. That section is kept as
  the record of what main made, not as a description of this tree. **The want it served is still
  met, in the shape the owner ruled for** — *"I don't want the walk picking for me"*: the per-copy
  press, from an order's own panel or from the cross-order pass through the drawers (`#/orders`,
  "Walk the boxes"), which sorts by the same `(box, index)` and leaves the choice of copy to the
  operator (D93, D97). It is a second form of step 11 rather than a fifteenth step and gets no
  build-order row. **This pointer said T6 was BUILT with the envelope as the unit of the write
  until 2026-09-05**, three days after that code was deleted — the drift the `work item standing`
  audit row now catches.
  Not `docs/specs/order-flow.md`, the sell path.
- `docs/specs/code-cards.md` — the code-card track end to end: the QR decode (BUILT, and
  measured at 140/140 physically-possible frames with zero mis-reads), the ledger (BUILT),
  the product claim that retires C2's OCR (BUILT), and the channel decision (RECORDED, and
  NOT executed — every researched venue came back marginal). Read its §8 before trusting a
  number: no real code card has ever been through this pipeline.
- `docs/specs/stale-listings.md` — the live listings that are not selling, marked down and
  pushed back (D100). SPECIFIED and BUILT, NOT VALIDATED: two commands, four routes, a screen
  and a harness block, and **no file it writes has ever been uploaded to TCGplayer**. Read its
  §2 before touching this path — the deletion question is answered there from 72,701 real
  export rows, and the doubling it is shaped to prevent already happened on this store. Read
  §3 before trusting the age it ranks on: it is how long the card has been OWNED, because
  `Listing` has no first-listed stamp and `live_as_of` is absent from all 443 stored payloads.
  §5 is the one section the Banchi rebuild moved — the screen is a modal now and the pixel
  measurement that refused it a route is history — and §6 names the three things the first
  real upload would measure.
- `docs/specs/batch-script.md` — the four commands, storage, routing, pricing. Built.
- `docs/specs/one-process.md` — D138's plan: the capture server serves `app/dist/` beside the
  API, the supervisor runs `vite build` when the source is newer than the bundle, and `restart`
  folds into `up`. SPECIFIED 2026-09-11, NOT BUILT. Three PRs in its §9;
  read its §5 before the reinstall, because the port change resets the camera grant and every
  `localStorage` key once.
- `docs/specs/capture-app.md` — step 7. 7a (capture screen, undo, pull preview, one new
  server route) was built to it. 7b (review queue, Fulfillment view, inventory view,
  mark-sold, three more server routes) was built 2026-08-13 ahead of Gate B at the owner's
  explicit instruction; that schedule question is settled, and the spec's sections 0 and 9
  are marked overtaken rather than left reading as a prohibition over built code.
  **Gate B ran those screens on 2026-08-22 and most of the doubt is gone**: the capture
  screen drove a real feeder session, the review queue held 16 real entries and the owner
  answered every one, and the pull preview found a stored photo at its physical location.
  §10.2's measurements were taken and live in `docs/GATES.md`'s Gate B section.
  **Two things are still unexercised and its STATUS section names them**: the Fulfillment
  view against a real order, and the review screen's price-banded hierarchy against a
  mixed-value lot — that run's queue was uniformly sub-threshold, $0.04 to $0.40.
- `docs/specs/motion-trigger.md` — Gate C's auto-capture: built and self-tested 2026-08-22,
  tuned at the rig 2026-08-23, confirmed live at 85/85 on box 95, **rebuilt on
  measurements 2026-08-31 (D81)**, **corrected on three more 2026-09-01 (D84)**, and given
  **the ratchet's escape and the rescue 2026-09-11 (D131 and the rescue's own entry)**. Its §4
  is the rig protocol and its §7 is the rescue; D19, D81, D84 and D131 are the decisions.
  Read its STATUS before treating a green `make design-check` as evidence about the feeder —
  the TRIGGER half of Gate C is confirmed and the PIPELINE half is not: box 95's 85 records
  are all still `captured`, and no run directory exists for that box.

  **EVERY THRESHOLD IS A MULTIPLE OF SOMETHING THE SESSION MEASURED, and the constants that
  preceded them were portable to exactly one rig.** The card-present gate was a brightness
  against the constant 90; across four saved traces an empty stand reads 57 and a real card
  on another rig reads 61, so no constant separates them, and that one **refused 38 real
  cards as an empty stand, silently** across three sessions — 18 of them still refused after
  the 2026-08-29 "fix", which changed which brightness statistic the constant was compared
  against and rescued one session of three. Presence is the distance from the watch region as it
  stood when the trigger was armed — empty stand 1.1–1.4, cards 17–167 — and `tLo`/`tHi` ride
  the session's own median still-frame difference. The seed reproduces the hand-tuned
  4.50/8.00 exactly, so the 85/85 run is not re-litigated.

  **THE FIRST THREE SESSIONS RUN ON THAT MACHINE COST TWO JUNK PHOTOGRAPHS AND FOUR SILENTLY
  LOST CARDS, ALL IN THE FIRST TWO SECONDS AFTER ARMING** (D84). A settle is now `stillFrames`
  of the last `stillWindow` and not a consecutive run — a two-frame alternation defeats a run
  absolutely, and one did, on a card sitting motionless for 500 ms. The stall clock is cleared
  by a COMPLETED settle and not by any quiet frame, which is why `stalled` never fired across
  those four. **`presenceMin` is 16.0 and it BINDS**, so the sentence above is no longer true
  of the presence floor: what that floor has to clear is the operator's HAND arriving with the
  first card (8–11 on this rig), and no session statistic measures how big a hand is in frame.
  D84 records that as a debt rather than a design, and names the three quantities that
  re-derive it on a new rig — the idle stand, the worst approach, the quietest card.

  **A SECOND TRIGGER LANDED 2026-09-11 FOR A FEEDER THAT NEVER RESTS (D130), AND WAS DELETED
  THE SAME DAY.** The settle trigger fired on 5 of 29 real cards on a re-arranged rig; a
  beat-locked cadence machine replayed 27/29 against it. The owner retired it that evening —
  *"motion is better. always."* — once the settle machine reached those cards on its own.
  **THERE IS ONE TRIGGER AND ONE ONLY**, and a session proposing a second reads D130's
  deletion note first. The sessions recorded under it stay banked in `harness/traces/`,
  because a recording is evidence about a rig rather than about a trigger.

  **THE SETTLE TRIGGER WAS FIXABLE AFTER ALL, WHICH D130 SAID IT WAS NOT (D131, the same
  night, on the owner's refusal).** The rest existed at d 5-8 under the bright lamp; the noise
  tracker's ratchet — still frames defined only by frames already under `tLo` — could lower
  its idea of still and never raise it, and sat under the rest. It has an ESCAPE now: still
  frames under 30% of the frames with a card in view hand the still level to the 25th
  percentile of all of them, and a settle is one quiet frame of the last three. Zero verdicts
  change on the eight earlier sessions.
  The HUD's `escape` count says when the ratchet was overruled. **Confirmed at the rig the same
  night**: two boxes, 70/~75 and 51/~54, two stalls each, no double — ~97% from 17%.

  **AND A CARD THAT WILL NOT SETTLE IS PHOTOGRAPHED RATHER THAN DROPPED, WHICH IS THE OWNER'S
  OWN COMPLAINT ANSWERED**: *"it's really bad when the cards are coming a little slower or
  aren't landing perfectly"*. Six more sessions that evening, 268 photographs against 20
  stalls. Every stall episode's quietest frame sits 1.02–1.25x `tLo`, and NINE of the first
  fourteen are UNDER it — frames the machine had already called still, refused by
  `stillWindow` alone because the card landed one or two frames after its transit ended.
  **The rescue**: past `rescueAfter` (0.60) x `maxMoveMs`, a frame under `rescueK` (4/3,
  which is `sqrt(moveK/stillK)` — the Schmitt band's geometric centre) settles the episode,
  window requirement dropped with it, and fires `fire:rescued`. **Presence, novelty and the
  refractory are NOT relaxed**, so a rescue can photograph neither an empty stand nor the same
  card twice. 268 -> 295 photographs, 20 -> 7 stalls, and **the eight earliest sessions do not
  move** — the half the sweep was constrained by. A step and not a ramp: retiring the window
  from the first frame of an episode takes the corpus's double count from 2 to 20-55.
  **And a stall is a SENTENCE on the stage now**, with a `Set aside` press, rather than a
  number inside a collapsed disclosure. **NOT VALIDATED AT THE RIG** — the replay says the
  machine fires on more cards; only the JPEGs say whether they are readable, and §7 is that
  run's checklist.

  **THERE IS NO `stalled:flare`, AND THAT IS A FINDING.** The remaining misses are bright, and
  three candidate glare discriminators were measured across the whole corpus: saturation reads
  ~0 on every stall frame (a 38x28 cell averages ~3,600 sensor pixels, so a clipped streak
  arrives as 214 — the instrument destroys the evidence), a spike-shape ratio goes the wrong
  way (1.19 for stalls against 1.36 for fires), and "brighter than any card this session fired
  on" flags 14-55% of ordinary episodes too. `scripts/score-trace.py stalls` prints the
  reading and names nothing. **The fix for glare is optical** — lamp off-axis, diffuser,
  polariser — and a session that tries to threshold its way out of it should read D81 first.

  **`scripts/score-trace.py` is how a trace is scored, and it is not optional reading before
  changing a number here.** `summary`, `presence`, `sweep`, `stalls` and `contact` — the last one draws
  every verdict's frame, because the 2026-08-29 fix derived its "empty stand" brightnesses
  from twenty photographs of real cards nobody had looked at. **Arm on an empty stand**: what
  is in the watch region at arm time is what the session will call nothing. **And the trace is
  not the whole answer** — D84's four lost cards were only provable by downsampling the run's
  own JPEGs to the trace's 38x28 watch region and matching them frame against photograph. A
  trace says what the machine decided; only the photographs say what was there.
- `docs/DESIGN.md` — **two halves, and only one of them still describes this tree.** The
  Fulfillment view's hard constraints table is live, binding and asserted in a browser by
  `make design-check`: 20px body, 32px position labels, a 320px photograph, 44px targets, 7:1
  contrast, no jargon, and no route out of that view. **The token block beside it is live
  too**, and this pointer called it stale until 2026-09-07: it is the `--bn-*` set, rewritten
  for Banchi on 2026-09-03, and `make docs-audit`'s `design tokens` row reconciles it against
  `app/src/tokens.css` in both directions on every run — green, not red. That row locks every
  token NAME and the hex VALUES; the scale numbers beside them are prose, which `docs/DEBTS.md`
  carries as an open gap.
- `code-card-fork/CLAUDE.md` — the code-card track. Separate schema, separate channel.
- `fixtures/` — real TCGplayer exports. Ground truth. Never modify.
