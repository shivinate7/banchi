## 3 — The claim chain

**Three entries. The first two overlap in files; none is parallel with another.**

### A capture-time claim crosses ten hops and nothing binds them together

Recorded 2026-08-22 from the multi-game work (D21-D25). Each operator claim is one value
carried by hand through independent restatements; the chain is the finding:

1. `app/src/CaptureScreen.tsx` — the control and its client state
2. `app/src/types.ts` — the shape the wire speaks
3. `app/src/server.ts` — the body `POST /capture` sends
4. `server/capture_server.py` — the route pulling the field off it
5. `server/capture_server.py:sidecar_payload` — the JSON beside the photo
6. `server/capture_server.py:PUT_FIELDS` — what the correction route may change
7. `store/master.py:Card` — the dataclass field
8. `store/master.py:Inventory.parse` — the reload filter
9. `store/master.py:allocate_capture` — the keyword pass-through
10. `identify/sidecar.py` then `pipeline/join.py` — the consumer that reads the claim

**Hops 4-10 were bound on 2026-08-23** by `CAPTURE_CLAIM_FIELDS`, which drives
`record_capture`'s upsert, `allocate_capture`'s pass-through, `sidecar_payload` (via
`CLAIM_WIRE_NAMES`) and `PUT_FIELDS` (derived, no longer a literal), with an import-time
assertion that every name is declared on `Card`. T7's `check_capture_claim_chain` iterates the
tuple, so a new claim is covered the day it is added.

**What is still unbound.** The three app-side hops, permanently: no Python constant reaches a
`.tsx`, and `make typecheck` sees a field *added* to `app/src/types.ts`, never one omitted.
And **a fourth restatement** — `cli/cmd_identify.py` builds a `master.Card(...)` literally
rather than through `allocate_capture`, so it carries the claim names by hand. Correct today,
unbound tomorrow; the site says so in a comment. **That one IS closable** and is the only
tractable half.

**Cost, and it is paid at the wrong moment.** Every symptom appears at the far end — a claim
missing from a sidecar, a finish reverting after a correction — and debugging starts at the
screen. Gate B's six defects included one of this family: review answers written by a route
nothing on the join path consumed, which took a real run to find.

### The operator's `note` never reaches the model

`identify/prompt.py:user_text` takes `set_hint`, `with_crops`, `strategy` and `rarity_claim`.
It takes no note. The note is carried faithfully everywhere else — `identify/sidecar.py`
reads it, `cli/cmd_identify.py` records it, `CAPTURE_CLAIM_FIELDS` keeps it — and the one
consumer that could act on it never sees it. **It is the whole point of the field for `misc`**,
the game naming a card the model most needs help with, where the note stands in for a set hint
that does not exist.

**Why not threaded through `set_hint`.** That rides on templates the file owns
(`user_with_hint`, `hint_clause`), and smuggling a note down that path tells the model the note
is a stack label. Doing it properly means `Profile` growing a note clause and `user_text` a
parameter — a prompt-contract change with its own fingerprint questions, since
`prompt_fingerprint` hashes both user turns and T1's recorded scores are evidence about the
bytes that exist today.

### `app/src/readiness.ts` is a second `blocking`, and nothing reconciles the two

`app/src/readiness.ts:owed` is a second implementation of `pipeline/decisions.py:blocking` so
`#/pricing`'s ready line settles on the keystroke that satisfies it, with no round trip — D54's
choice, and the right one for a line whose whole value is that it is instant. **Its header
claimed an `emit readiness` row in `scripts/docs-audit.py` and a Makefile target,
`readiness-agreement`, until 2026-09-02, and neither has ever existed.** `OWED_REASONS` was shaped as a flat
literal for a parser nobody wrote.

**What it costs.** The two can disagree and nothing says so: when `blocking` gains a refusal,
the line keeps saying *Pricing is answered* while `emit` refuses, and the operator learns it
from the emit's stdout. The one live defense is the roster on `GET /pipeline/pricing`, which
asks the Python that actually refuses — so a chip and the line can disagree, and the chip is
the one that is right.

**Why not fixed.** The honest check reconciles a vocabulary — `OWED_REASONS` against the
reasons `blocking` can return — and `blocking` builds its reasons as sentences rather than off
a tuple, so the row needs a roster the Python does not publish. That is cluster 1's decision
again, asked of one more module. Until it is settled the header says nothing audits it, which
is the claim this file exists to keep true.

### ~~The eleventh hop is the fixtures, and adding `product` broke four tests nothing runs~~ — CLOSED 2026-09-05

**The chain above has one more hop than it lists, and D101 walked ten of the eleven.** Adding
`product` to `GameRegistry`, to `do_put_box_claims` and to `BoxOps`'s claim editor was correct
everywhere the list names. What it did not touch is the STUBBED COPY OF THE WIRE that every
browser spec carries — `app/tests/inventory.spec.ts`'s `GAMES`, and the same fixture in
`capture-undo.spec.ts` and `capture-claims.spec.ts` — none of which grew `products` or
`product_game`.

**What that cost, measured on `46160bf` before anything here was changed: 8 of 78 cases in
`inventory.spec.ts` failed, and the suite took 58s instead of 18s** because six of them were
30-second timeouts. `BoxOps` wrote the missing `products` — `undefined` — over the `[]` its
state starts as, the next read of `productList.length` threw inside the editor's render, and
the subtree left the DOM. Playwright reported `element was detached from the DOM` and named
nothing else. Four of the eight are the box-claims cases: **the tests over the very control
D101 added were the ones it broke.**

**It merged green, and the reason is structural.** `app/tests/` runs under `make design-check`
alone, which is deliberately off the commit path — `make check` runs the nine Python tests, the
audit, lint and the typecheck, and none of them starts a browser. So the failure was invisible
to everything a session or a hook looks at, and it stayed invisible for as long as nobody
happened to run the browsers.

**Fixed in three places, and only one of them is the fixtures.**

- `app/src/BoxOps.tsx` writes `registry.products ?? []` and `registry.product_game ?? null`.
  The comment three lines above it already promised exactly this — *"A registry that answered
  no products is the same 'not drawn'"* — and the code did not keep the promise. An older
  server is the real shape this defends against; a stub is how it was found.
- The three `GAMES` fixtures carry both fields.
- **All three are annotated `: GameRegistry`, and that is the guard.** They were object
  literals handed to `route.fulfill` through `JSON.stringify`, so nothing had ever compared
  them to the type they imitate. `app/tsconfig.json` includes `tests`, so the annotation puts
  them behind `make check`'s typecheck — **on the commit path**, where the browsers are not.
  Mutation: delete `products` from the fixture and `tsc --noEmit` reports
  `Property 'products' is missing in type ... but required in type 'GameRegistry'`. The next
  field added to that wire is a failed commit rather than a silent crash.

After it: **111 of 111 across the four spec files, then 163 of 163 across six.**

**What is NOT closed.** Two `/games` stubs remain untyped inline literals — `nav.spec.ts:114`
and `run-panel.spec.ts:411`, both `{ games: [] }` — and they are left that way on purpose:
their point is a registry that answered nothing, which is a state worth stubbing, and the
`?? []` above is what makes it safe.

**And the general form stands.** Six of the eighteen spec files now import their fixtures'
types from `app/src/types.ts` — these three, plus `orders`, `pricing` and `shipping`, which had
done it from the start and are the reason it was already this repo's habit rather than a new
idea. **Twelve do not**, so
the next field added to a wire can do this again in any of them. The remedy is the same
annotation, one file at a time; it is a session's work rather than a decision, and what makes
it worth doing is that the annotation moves the failure onto the commit path, where nothing
else about these tests is.

---
