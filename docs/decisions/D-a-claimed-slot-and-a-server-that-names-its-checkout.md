## D-a-claimed-slot-and-a-server-that-names-its-checkout — A checkout claims its port slot once, and a reused server must name its checkout

**Amends D43, the port follows the store, and D-no-git-no-live-port, a copied tree never gets the live port.** D43 promised that every checkout has its own ports. It delivered a hash of the path into 300 slots. A hash does not know which slots other checkouts hold. Now two things are true. A linked checkout CLAIMS a slot once, in one machine-wide registry, and keeps it. And a test run that reuses a dev server refuses to run unless that server names THIS checkout. The primary checkout is unchanged: it keeps 8000 and 5173 and claims nothing.

**The incident, 2026-09-24.** Two live worktrees, `jovial-banach-362f31` and `agent-a591036a4885f7533`, both derived dev port 5218 and the same capture port. A lane in one tree ran `make design-check`. Playwright's `webServer` found 5218 already serving the OTHER tree's Vite. It reused that server (`reuseExistingServer: true`) and tested the wrong code. The run was green. `app/playwright.config.ts` said reuse was "safe only because the port is per-checkout". That premise was false.

**Why collisions are likely, measured.** On 2026-09-24, 44 folders were under `.claude/worktrees/` on this Mac. For n paths in 300 slots, the chance of at least one shared slot is 1 − ∏(1 − i/300) for i < n. That is about 87% for 35 paths and about 96% for 44. `app/devPort.ts` said "a couple of percent". That number was for a handful of trees.

**The options, and the choice.**

- **(c) Identity before reuse. BUILT.** This is the minimum: a test run must never pass against another tree's code, whatever the ports. `app/checkoutIdentity.ts` adds a Vite plugin that answers `GET /__checkout` with the checkout's resolved path. It is also Playwright's `globalSetup`. Playwright starts or reuses the `webServer` BEFORE `globalSetup` runs, so the check asks the server that is actually there. The run stops unless that server names this checkout. No answer, or an answer that is not JSON, is a refusal: an older Vite's 404 and another program both fail. The refusal names both paths and the remedy. `PKMNSCAN_CHECKOUT_IDENTITY=off` skips it, and the refusal prints that.
- **(b) A machine-wide registry. BUILT.** `scripts/port-slots.py claim` writes `~/.pkmnscan/port-slots.json` (`PKMNSCAN_SLOT_REGISTRY` overrides), beside D122's suite lock. `server/ports.py:slot_for` and `app/devPort.ts:slotFor` read it before the hash. They never write it.
- **(a) Probe the port at serve time and step or refuse. NOT BUILT as a standing rule.** A step at every derivation makes the port depend on which servers run at that moment. `vite.config.ts`, `playwright.config.ts` and the Python server read the port at different times, so they could disagree. `strictPort` could then not tell "someone else is here" from "I moved". D43 rejected an allocator for that reason, and the reason still holds. A refusal that names the holder does exist in part: `vite.config.ts`'s `strictPort` refuses a busy port, and (c) names the foreign checkout. The probe is used ONCE, inside a claim, where its answer is recorded and then stops moving.

**How a claim picks a slot**, under one `flock`:

1. Entries whose path is no longer a directory are dropped. A removed worktree frees its slot.
2. A checkout that holds a slot keeps it. D43's outcome, "the same worktree answers the same port on every run", holds.
3. A new claim starts at the path's hash slot. A tree whose slot nobody contested keeps the port it always had. The claim steps past a slot that another checkout claimed, or whose dev or capture port another checkout's server holds now. A port that THIS checkout's own server holds does not count against it: the Vite names this checkout at `/__checkout`, or `lsof` shows the listener's working directory inside this checkout.

**Where claims run.** `make dev`, `make server`, `make up`, `make design-check`, `make design-check-quiet` and `make worktree-setup` claim first, through the Makefile's `PORT_CLAIM`. A claim that cannot be made fails open and says so. The ports then fall back to the hash, as before this entry, and (c) still refuses a foreign server. So a registry problem never stops `make dev`.

**What each part protects.**

- (c) protects the verdict. A green run proves this checkout's code, or the run does not happen.
- (b) protects D43's outcome, one store per checkout: the app in tree A must not read or write tree B's store through a shared capture port. Playwright seals the capture port, so (c) does not cover a person using `make dev`. (b) does, for every checkout that claimed.

**Known limits, recorded.**

- A tree that runs code older than this entry does not read the registry. It keeps its hash slot. A claimed tree can share a slot with it until it updates. (c) still refuses a test run in the new tree. The claim steps past such a tree's slot only while its server is up.
- The capture server does not answer `/__checkout`. The claim identifies a capture-port holder by `lsof` only. Where `lsof` is missing, an unknown holder counts as another checkout's, so the claim steps away from it. That can move a tree off its own slot once. It never puts two trees on one slot.
- More than 300 live linked checkouts leave no free slot. The claim then says so and the hash answers.

**The reader.** `make port-slots-selftest`, in `make check` and `make ci-check`, never in the commit hook (D18). It forces two throwaway trees into one hash slot. It picks a slot whose ports are free, so it never reaches a real checkout's server. It starts a real Vite in tree B and runs a real Playwright in tree A.

- With nothing claimed, tree A's run must refuse tree B's server by name. With the `globalSetup` line removed, the run passes against tree B's server: the incident, red. With the plugin removed from `vite.config.ts`, the refusal no longer names tree B and the own-slot run fails: red.
- After both claim, A and B hold different slots. `server/ports.py` and a copy of `app/devPort.ts` answer the same ports. A second claim does not move A. With the step past a held port removed from the claim, this arm goes red.
- The same Playwright run in tree A then starts A's own Vite and passes.
- A removed tree's slot is freed. A damaged registry reads as nothing claimed, on both sides.

`make port-agreement` also compares both languages over one temporary registry with a claimed entry.
