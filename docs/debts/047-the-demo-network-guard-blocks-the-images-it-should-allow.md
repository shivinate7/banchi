## 47 — ~~the demo's network guard blocks the stock images the demo now loads on purpose~~ — CLOSED 2026-09-27, fixed as recommended

**The finding.** Since PR #476, the published demo loads Riftbound and One Piece stock images
from `tcgplayer-cdn.tcgplayer.com`, as the live app does. The demo coverage spec's network
guard refuses every outside host. So PR #477 routed those image requests to a local stub image
in the test, to make the publish pass.

**Why this is a debt.** The guard's premise changed. A request to the TCGplayer image host is
now the intended behavior, not a leak. The stub hides that behavior from the test. The right
test allows that one image host by name, and still refuses every other outside host.

**The owner's words (2026-09-27, verbatim).** `isn't that a scenario of revising the test like the test is the wrong test to keep now? save that as part of our deferred debts to address tests`.

**What would close it.** The demo coverage spec gets an allow list that names only the
TCGplayer image host. A case goes red on any other outside host. Remove the stub. Close it with
DEBT45 (no page lists what each test protects), in the same pass over the tests.

**Closed by the fix this entry recommended**, in the test-audit lanes (lane L6,
`docs/reviews/test-audit-2026-09-27/PLAN.md`, item S5). `app/tests/shell.ts`'s own `isOutside`
and `sealOutside` took a per-spec `allowHosts` list. A spec asks for it through
`sealEveryTest({ allowOutside: [...] })`. Every host it does not name stays refused. The default
seal every OTHER spec imports is unchanged. That is what keeps this from being the
widened-default fix this entry itself warned against.

`app/tests/demo-coverage.spec.ts` now calls
`sealEveryTest({ allowOutside: ['tcgplayer-cdn.tcgplayer.com'] })`. It no longer routes that
host to a local stub. The one-pixel PNG and its `beforeEach` are gone. The real request reaches
the real host. A Playwright trace of the same run proves it. `GET
https://tcgplayer-cdn.tcgplayer.com/product/...jpg` answers 200 from CloudFront. That happens in
the same run the demo's own screens are graded in.

`the seal still refuses a host that is not on the allow list` (same file) reads `isOutside`
directly. `tcgplayer-cdn.tcgplayer.com` passes. `example.com` does not. This is a direct read of
the predicate, not a live request to a second host. A browser case that drove one through the
real page would trip `sealEveryTest`'s own leak assertion by design. That is the wrong test to
write against a guard built to fail loudly.

Not closed with DEBT45 in the same pass. DEBT45's own renderer (lane L9) is a separate, larger
build that lane L6 does not touch. This entry closes on its own.
