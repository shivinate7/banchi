## DEBT-demo-pull-flake — the demo's "Cards to pull" photograph case can fail on a slow runner

`app/tests/demo-coverage.spec.ts`, case "Cards to pull draws its photographs", failed once in CI
(run 36807030451, attempt 1) and passed on a rerun.

**Cause, as far as known:** the Fulfiller window asks for no photograph until the demo's 75 MB
`demoServer` chunk has arrived and parsed. On a loaded runner, that takes seconds. The case
started to watch for photograph responses too late, and it reloaded the window, which loads the
chunk a second time.

**What is done:** the work is on branch `fix/demo-pull-photo-flake`. It is not merged and has no PR.
- 421b01b9: `DEMO_CPU_THROTTLE=<rate>` slows the window. At rate 20, the case failed 30 of 30
  on the old code.
- c74964be: the fix. It listens for responses on the context, before the window opens, and it
  drops the reload. It also raises the poll to 45 s. That raise is a bandaid on top of the fix.
- 54c8feaf: unproven and never run. It replaces the CPU throttle with `DEMO_CHUNK_DELAY_MS`,
  which holds back the chunk itself, so the failure repeats the same way on every run.

**Why it is not fixed:** the owner stopped the lane, by the owner's word. A rerun clears the flake.

**Closes when:** the delay repro is red on main and the fix is green 30 of 30 under it. The full
demo spec must also pass, and the branch must merge. Decide then whether the 45 s poll can come
back down.
