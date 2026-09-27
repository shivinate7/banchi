## 47 — the demo's network guard blocks the stock images the demo now loads on purpose

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
