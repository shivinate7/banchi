# D158 — Refuse where the damage is

**The primary checkout is where the damage lands, so the refusal is on serving there and not on the git command.** The primary checkout, `/Users/shivinate/Developer/banchi`, is the one that D138 (one process serves the product) keeps a supervisor alive out of over the owner's real store. An earlier design was written after `/Users/shivinate/Developer/banchi` was found standing on
`claude/env-key-rotation` with three live sessions in it. It shipped warnings at three moments
and ruled that **a warning is the ceiling**.

**It happened again the next night**, on `claude/debts-citation-repair`: a branch already merged
as pull request #282, already behind `origin/main`, with **four live sessions in the tree**. Told
about it, the owner expected a guard that ensures the primary checkout is always main. That is the reopening, and what it reopens is the ceiling —
not the readers.

### The guard goes at the damage, not at the git command

Its argument was: git has no `pre-checkout` hook, `post-checkout` runs after the switch has
already happened, therefore nothing can refuse. Every clause of that is true and the conclusion
does not follow, because **the thing worth refusing was never the checkout.**

**The harm is one process.** `make launch-agent` keeps a supervisor alive at login out of that
one directory, over the owner's real `inventory/store.sqlite`, and since D138 (one process serves the product) that process also
builds and serves the front end. So the branch decides which code photographs real cards into a
real store and which screens the owner is looking at while it happens. A person checking out a
branch to *read* it does no harm at all.
**A guard that refuses to SERVE puts the refusal on the damage and frees the checkout entirely.**
That is both stricter where it matters and looser where it is right that a session working in that
directory is normal.

### The two mechanisms that could not work, and one of them is measured

**`reference-transaction` cannot see this.** It was the obvious candidate. It is already armed
here. It already refuses local moves of `refs/heads/main`, per D42 (main moves only by pull
request). It is also the one hook that sees a ref move *before* it commits.
**Measured on this machine's git 2.39.3, it does not fire on a branch switch at all.**
`HEAD` is a SYMREF, and moving a symref is not a ref transaction:

```
git switch <existing branch>   fires nothing
git switch -c <new branch>     fires for refs/heads/<new>, never for the HEAD move
git checkout --detach          fires for HEAD, because a detached HEAD is a real ref update
git update-ref refs/heads/zzz  fires (the control)
```

So a guard built there would have been **silent through both observed incidents**, because each
was a switch to an existing named branch. It would have fired on `checkout --detach`, which is
neither of them. It is not merely the wrong place; it is blind to the case and noisy on the one that has
never happened. An earlier design rejected this hook for a different reason (that it would catch legitimate
worktree moves, which the primary/linked test disposes of); that reason was weak and the real
one is stronger.

**A louder `post-checkout` is a bandaid, and the owner's standing instruction names the class.**
The owner's standing instruction: resolve things by best practice, never by band-aid routes. The
warning already existed, already fired, and was already missed twice. Volume is not a mechanism.

### What is built: one refusal and two readers

**1. `scripts/serve.py:off_main` — the supervisor refuses to adopt this tree's code.** Four arms,
at exactly the four moments code is adopted and nowhere else:

- **the spawn** (`Supervisor.start()`) — the login path, because `make launch-agent`'s plist runs
  `serve.py run` directly and never goes through `make up`;
- **the reload** (`_restart_for`) — the observed case, a tree moving under a live supervisor;
- **the re-exec** — the same arm, and see the order below;
- **the build** (`_check_app`) — because the two watch sets are independent by design per D138
  (one process serves the product). A branch touching only `app/src` reaches no other arm, while
  being exactly what a person sees.

Plus `do_up`'s preflight, so `make up` refuses with a status rather than a ten-second timeout.

**IT STOPS NOTHING THAT IS ALREADY RUNNING, and that is the whole shape of it.** Every arm
refuses an *adoption*. A capture server already serving goes on serving the code it started with.
That is deliberately the same bargain, in deliberately the same words, that `_first_syntax_error` has
always made for a file that will not parse. Killing the owner's server to enforce a branch policy
would be the repair that cuts the write in flight, which is the 2026-09-04 incident
`refuse_unconfirmed` carries the account of.

**THE ORDER INSIDE `_restart_for` IS LOAD-BEARING AND IS THE SUBTLEST THING HERE.** That method
re-execs the supervisor into the `scripts/serve.py` **on disk**. A branch switch is precisely
how a *different* serve.py arrives, including one cut before this guard existed and carrying no
guard at all. Asked first, the question is answered by the image already running, which is main's,
**so a branch cannot ship the code that disables the guard against it.** Asked after the re-exec,
it would be answered by the branch's own copy, which is no guard. There is a self-test arm whose
fixture branch deletes the guard from its own serve.py for exactly this.

**2. The `post-checkout` hook is gone, on the owner's word** (remove the post-merge and
post-checkout warners). A branch switch prints nothing now. Nothing depends on it: the refusal in
part 1 is what protects the owner's store, and the two readers that remain are `make status`
under SERVING and `scripts/worktree-guard.sh` at session start. A cold start on a branch cut
before the refusal existed is served; the SessionStart reader and `make status` are the only
speakers there.

### It has an escape hatch, and that is a departure from the entry it is modelled on

`BANCHI_SERVE_MAIN=off`, printed in every refusal, as `BANCHI_MAIN=off`, `BANCHI_KILL=off`,
`BANCHI_REVERT=off` and `BANCHI_SUITE_LOCK=off` all are.
D140 (merge claims the decision number) is the merge's own stale-half guard, landed the same
night. It deliberately has none, on the ground that what it refuses
costs `git merge origin/main`: seconds, and the right thing to have done anyway.
**That reasoning does not carry here, and the difference is the point.**
There, the refused act had a
correct alternative one command away. Here the refused act is sometimes exactly what the owner
wants. The act is serving a branch against the real camera, the real store and the real rig.
**No other command in this repository achieves it.** A guard standing between a person and a
capability with no way through is a guard whose variable somebody invents in a week. Or worse,
it is a guard answered by unsetting `core.hooksPath`, which takes the refusals of D42 (main moves
only by pull request) and the three opsec rules with it.

### How often it fires in normal use: never, and that is checkable rather than hopeful

The steady state of the primary checkout is `main`, and on `main` this guard costs three file
reads and prints nothing. It fires **only** while that one directory stands on something else —
which is the defect, in both of the states it has actually been observed in. A linked worktree is
silent whatever branch it holds. ~30 of them on this machine are legitimately on feature branches.
They have their own stores and their own ports to be wrong on their own, per D43 (each checkout
gets its own port). The test is `server/ports.py:is_linked_worktree`, **called and not respelled**,
because that question must have exactly one answer in this repo.

Three states look like violations and are not. All three are silent, and all three are asserted.
They are a repository whose trunk is called something else, a tree with no `.git` at all, and
**CI**. In CI the checkout is a primary one standing on a detached HEAD, and is quiet because
`main` is not a local branch there. Nothing on the CI path starts a supervisor in any case: Playwright's `webServer` runs
`npm run dev`.

### Proved by reproducing both incidents, not by asserting about them

`scripts/serve-selftest.py` gains a real primary checkout — `git init`, a real `main`, real
branches — and runs a real supervisor in it. Only three files are tracked in that fixture, which
is the trick that makes it work. The switch has to CHANGE a watched file, or no reload is
scheduled and the guard is never reached. `server/capture_server.py` stands for the reload,
`app/src/App.tsx` for the build, and `scripts/serve.py` for the re-exec.

Both incidents are rebuilt rather than described. One is a tree moving under a live supervisor.
The other is a **cold start through `serve.py run`**, the way launchd starts it, which is not
`make up` and which is the shape the second incident was in. The rig stays up in the first and never opens a
port in the second, and `git switch main` recovers both with nothing else typed.

**Seventeen mutations on the first sweep: eleven caught, six survivors.**
**Sixteen of sixteen on the second, none surviving.**
The six are the whole argument for running one. The `main`-exists
gate, the packed-refs reader, the detached-HEAD naming, `start()`'s own arm, `_check_app`'s own arm
and a `git_dir.is_dir()` test were all deleted cleanly with every case still green. Five have an arm
now and the sixth is deleted. Two findings are worth keeping:

- **`start()` survived because `do_up` refused first.** Every end-to-end case went through
  `make up`, whose preflight fires before the supervisor exists. So the arm that covers a Mac
  booting with the tree parked on a branch, which is the second incident, was covered by nothing.
  The case that fixes it spawns `serve.py run` exactly as the plist does,
  **and had to send its stdout to the log file to see anything**: `log()` is a `print`,
  and the first draft sent a
  perfectly correct refusal to `/dev/null` and went red.
- **A `git_dir.is_dir()` test was written and is deleted.** The sweep showed it could not change
  a verdict in any arm. A linked worktree has already returned above it, and a tree with no
  `.git` reaches `_has_local_main`, which finds neither a loose ref nor a readable `packed-refs`.
  A line that cannot decide anything is a sentence about a guard rather than one. A sweep is the precedent for recording that rather than leaving it to be found.

The packed-refs survivor is the one that would have bitten in production. `git gc` moves `main`
out of `refs/heads/` on its own schedule, and a loose-refs-only reader would have gone quiet on
the owner's rig the first time it ran. The fixture packs the refs and asserts the loose ref is
really gone before asserting the answer, because a case that silently failed to pack would prove
nothing.

### What it cannot see, named rather than left to be found

**A cold start on a branch cut before this guard existed.** That branch's `serve.py` carries no
guard, launchd runs it, and it serves. Only the two readers speak, and both run after the fact. The hole shrinks on
its own, since every branch cut or merged after this carries the guard. It is also narrower than
it sounds. It needs the tree *parked* on such a branch across a restart. It is not closed, and
closing it properly would mean the plist executing through something outside the tree, which is a
larger change than the defect currently justifies.

**A branch that differs from main in nothing the supervisor watches is served, and correctly so.**
The arms fire where code is adopted, so a branch differing only under `docs/` never reaches one.
What is serving is main's code, byte for byte, for everything that runs. The *tree* is still
wrong, and the two readers are the ones whose subject that is.
**The refusal's subject is the code; theirs is the branch.**
Neither subsumes the other, which is why all three exist.

**And it does not decide that the tree should be put back.** `scripts/worktree-guard.sh` reports
and never switches, in as many words, and nothing here changes that. The owner may stand that
directory on anything they like; what they can no longer do by accident is serve it.