## D222 — The press paces itself on a measurement, and names a throttle

**MEASURED AGAINST THE OWNER'S REAL STORE, 2026-09-19, WITH A WORKING USER-AGENT.** 914
SKUs, 4 ranges, 28,350 buckets written. Only 206 of 914 SKUs answered. The other 689 were
refused with HTTP 403. A retest by hand, minutes later, used the same working agent.
Product 652771 had answered HTTP 200 earlier in the same session. It now answered 403. So
did every other product tried. The host throttled the client partway through the burst.
Nothing about the request changed. Only the volume already sent did.

This is the NORMAL case for this press, not an exception. A throttle after roughly 800
requests is close to certain over a 3,656-request pass at the old pace. Resuming without
re-fetching (D224) is the difference between finishing and never
finishing.

### A 403 after success this pass is named for what it is

`pipeline/pricehistory.py:Blocked`'s message tells the operator to set
`PKMNSCAN_TCG_USER_AGENT`. That is the right remedy for a 403 with no earlier success this
pass. It is the wrong remedy once this pass already read other SKUs with the same agent.
Every one of the 689 refused lines carried that message on 2026-09-19. Each one sent the
operator to fix something the run had already disproved.

`pipeline/pricearchive.py:classify_refusals` tells the two cases apart. It cannot change
`Blocked`'s exception type. That file is outside this task's fence. So it matches the fixed
substring `Blocked` always raises with: `"answered HTTP 403"`. Given evidence this pass
already read something successfully, it rewrites the message to name a throttle. It leaves
the User-Agent alone. With no such evidence, the message stays exactly as `Blocked` phrased
it. There is no evidence yet that authorization is not the real problem.

### The pace is measured, and never guessed

Guessing a request rate risks the same throttle again. It can also waste time going slower
than the host would tolerate. Neither serves the operator.
`pipeline/pricearchive.py:measured_pace` reads what THIS pass actually survived instead. It
counts how many requests, over how many seconds, before the first throttle signal arrived.
It doubles that observed interval (`THROTTLE_BACKOFF_FACTOR`). The rate just measured is
the rate that got this session blocked. It is not a rate proven safe.

That factor is argued, not proven optimal. This module has no way to learn the host's real
limit except by testing it. A constant typed with no real number behind it is exactly the
guessing this entry exists to replace.

### One backoff, then a clean stop

On the first throttle signal this pass, `cli/cmd_pricearchive.py:_sweep` rebuilds its
`Market` at the newly measured pace. It keeps going. If the very next chunk is also
throttled, the press stops there. It does not hammer a host that has already refused it
twice at two paces. Every chunk already committed stays committed
(D224). The measured pace is saved to `throttle-pace.json`, beside the
market cache. The next press starts from real evidence, not the naive constant.

### What was measured, and what to expect from a re-run

This entry can state the shape of the fix. It cannot state a specific safe rate. That
number belongs to the host. Only a live run against it produces one.
`scripts/pricearchive-selftest.py` proves the arithmetic. `measured_pace`'s doubling and
`load_pace`/`save_pace`'s round trip are both covered. It also proves the message rewrite
fires only with real evidence of success, never before it. The owner's next
`archive sweep --write` will report the actual measured pace in its own output. That is the
number this entry deliberately does not invent.

### What this does not touch

`pipeline/pricehistory.py:Blocked` and its message are unchanged. This entry only
classifies a string it already produces. It never edits the file that raises it.

No retry loop sleeps and re-tries the same request inside one attempt. This repo's own
shell guard already refuses that shape elsewhere, under `PKMNSCAN_WAIT`. A wait that cannot
see its own outcome is not a mechanism. Stopping the pass is the mechanism instead. Letting
the operator re-run `archive sweep --write` is the other half.
D224 is what makes that re-run cheap.
