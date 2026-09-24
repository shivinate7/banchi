## D194 — The visible word count on every owner screen may only go down, and the ceiling is a measurement rather than a guess

**The owner's ruling, 2026-09-13:** *"less text is always better than more."* Several sessions
are cutting copy across every screen at the same time, on that instruction alone — which is
exactly the shape "a rule with no reader is advice" already names for
`D196` and `D195`: a session under time pressure
cuts one screen's copy and leaves the next one exactly as wordy as it was, and nothing says so.

**This is deliberately blind to CONTENT and asserts only VOLUME.** `D196`
already reads every user-visible string for the wrong VOCABULARY — a decision citation, a
repository path, a pipeline-internal noun. This is not a second pass over the same ground: a
session that rewords "found no candidate rows for this card" down to "no match" is doing
exactly what the owner asked for, and a content-aware guard would have opinions about the
rewrite that this rule does not need to hold. Counting words is the one measurement that stays
true regardless of which words they are.

**A RATCHET, NOT A CEILING ANYONE CHOSE.** `app/tests/copy-budget.json` holds the word count
`app/tests/copy-budget.spec.ts` measured on this tree the day it was pinned — the exact number,
no slack added on top. Slack is how a ratchet leaks: a ceiling padded "for safety" is headroom
a later session spends without ever being asked to spend it. The only way a ceiling rises is
`node scripts/copy-budget.mjs --pin`, run by a person who is choosing to let an addition
through — never by the guard itself, and never automatically on a passing run.

**The region counted is `.bn-view`** — `App.tsx`'s own wrapper around `<route.view />`, and
nothing else: not the sidebar or rail, not the phone top bar or tab bar, not the offline
banner, the drawer, the command palette, the keys sheet or the toaster, all of which are
siblings of `.bn-view` and never inside it. That is a structural fact read off `App.tsx`, the
same region every route renders through, and it changes only when a screen's own copy does.

**Routes are discovered off `routesFromNav`**, the same argument `cursor.spec.ts`,
`wide.spec.ts`, `button-stack.spec.ts` and `page-edge.spec.ts` already make: a hand-typed
roster goes stale by going green, and a screen added to the sidebar next month is swept with no
edit to this guard. `#/fulfillment` is excluded — `docs/DESIGN.md`'s own Fulfillment floors
govern his screen, and this rule does not reach for a second authority over it.

**A found loading state is not a measured one.** The first build measured `#/inventory` at
either 156 or 158 words across runs, because `await expect(main).toBeVisible()` passes the
instant the shell paints "Reading the inventory…" — a real `<main>`, well before the mocked
store read resolves. The fix waits for `.bn-view`'s own text to stop changing (two reads 150ms
apart agreeing, capped at 4s) rather than trusting the first read taken the moment the element
exists — generic across all eleven routes, never a per-screen loading string this guard would
have to keep in step with.

### Mechanized

`app/tests/copy-budget.spec.ts`, run by `make design-check`. It renders every owner route at
1440 in the fixture `wide.spec.ts` and `phone.spec.ts` already use for a cross-route sweep
(`sealEveryTest({ store: true, cards: 122 })`), counts words in `.bn-view`'s stabilized
`innerText` (split on whitespace, drop a token with no letter — a bare number, a currency
figure, a lone dash), and asserts each route's count against `copy-budget.json`. The failure
message names the route, the measured count, the pinned ceiling, and the fix in one sentence.

`scripts/copy-budget.mjs --pin` re-measures and rewrites the ceiling file. It contains no
counting logic of its own — it sets `COPY_BUDGET_PIN=1` and runs the same spec through
Playwright, so the assert path and the pin path are one file exercising one measurement, and
the only thing that differs is what happens to the number once it is taken.

Mutation-tested: `COPY_BUDGET_MUTATE='#/pricing'` makes the spec inject a thirty-plus-word
sentence into that route's `.bn-view` via `page.evaluate` before counting — never by editing a
file under `app/src` — and the spec goes red naming exactly that route (91 words against a
ceiling of 46) while every other route stays under its own ceiling. Unset, the suite passes
clean.

### Not mechanized

**Whether an addition was worth its words.** The guard has no opinion on that; it only forces
the question into the open by failing until someone runs `--pin` on purpose, which is the
decision it exists to make un-skippable rather than the decision itself.

**Whether the pinned ceiling reflects the screen's real busiest state.** The fixture that
renders every route is a small, shared store (two boxes, four cards) rather than a bespoke
fixture per screen — `#/runs`, `#/orders`, `#/shipping`, `#/codes` and `#/graveyard` see no run,
order, export or departed record of their own in this fixture, so their pinned ceilings are
ceilings on a near-empty state for those five screens rather than the busiest one a real store
would draw. A route whose ceiling was pinned this way will need `--pin` again the day a fixture
gives it real rows to draw, and that is a known gap rather than a claim this file makes about
those five screens' real ceilings.

### Amended 2026-09-13 — the five under-fixtured routes get a checked-in populated seed

**The gap above is closed, not merely re-stated.** `app/tests/routeFixtures.ts` is a new,
shared module holding the fixture BUILDERS `run-panel.spec.ts`, `orders.spec.ts` and
`shipping.spec.ts` already had inline (`runRow`; `place`/`pick`/`line`/`order`/`payloadOf`;
`shippingRow`/`batchOf`) — moved rather than copied, so the shapes `copy-budget.spec.ts` renders
are the exact ones those three specs already prove correct — plus two fresh builders
(`codeEntry`/`codeLedgerOf`, `departedCard`) for `#/codes` and `#/graveyard`, which no existing
spec had seeded at all. Five `seedPopulated*` functions each register a `page.route` stub
carrying several real-shaped rows for one of the five routes, registered in the test body
AFTER `shell.ts:stubStore`'s own empty answer for the same path — Playwright matches
newest-first, so the richer response wins and every OTHER route those five screens read
(`/boxes`, `/games`, `/search`, `/inventory`, `/pipeline/submissions`) is still the small
store's ordinary answer, unchanged. `#/shipping` additionally needs the CSV drop zone driven
once, because that screen fetches nothing on mount (`shipping.spec.ts`'s own header) — a stub
alone does not populate it.

**The owner's own alternative was put and rejected.** The owner offered pinning the five
ceilings against the live `:8000` capture server's real store instead of building fixtures for
it. That was refused for one reason: a live number is not reproducible in CI — order numbers,
buyer names and run ids on the owner's real store change daily, so a ceiling pinned against it
would be a moving target no CI run could re-measure the same way twice, and the next `--pin`
would silently ratchet the ceiling to whatever that day's store happened to hold. That is the
opposite of a ratchet: D194's whole design is that the only way a ceiling rises is a person
choosing to run `--pin` on purpose, not the store's own drift. A CHECKED-IN fixture is
deterministic across every machine and every run, which is what a ratchet requires of the
thing it measures.

**Re-pinning once moved four ceilings up and one down, and every move is named here.** Left to
a diff alone it would just be numbers: `#/runs` fell from 68 to 63 — its populated list of real
run rows reads as fewer words than the empty-state prose it replaced. The other four rose
because a populated screen draws real content an empty one cannot: `#/orders` 82 to 84 (three
real orders, one short, one nameless), `#/shipping` 80 to 135 (a read export across all three
lanes), `#/codes` 35 to 139 (a tier table with real codes and one delivered lane), `#/graveyard`
21 to 66 (four departed rows across the three doors D83 names, one of them buried). None of the
four is copy creep — nothing under `app/src` changed — and `COPY_BUDGET_MUTATE='#/pricing'`
still fails naming exactly that route (91 words against a ceiling of 46) with every other
route, populated or not, staying under its own ceiling.

### Superseded 2026-09-23 — `D-text-shape-checks`

**This entry's whole mechanism is deleted.** The owner's ruling, 2026-09-23: kill the pinned
ceilings. His own words for why: *"I think we need to kill ceilings and instead just use a
different way."* A stagnant static pin was not what he wanted kept.
`app/tests/copy-budget.spec.ts`, `app/tests/copy-budget.json` and `scripts/copy-budget.mjs`
are gone.
`app/tests/routeFixtures.ts`'s populated-seed fixtures — the part of this entry that survives —
are now read by `app/tests/routeSweep.ts`, the one sweep the three text checks share.

**What is kept: the reasons a naive replacement would have been worse.** A blind word count
still cannot tell whether an addition was worth its words (see "Not mechanized" above). A
CHECKED-IN fixture is still the only reproducible thing to measure against. Both arguments
carry over unchanged into `D-text-shape-checks`.

**What is not kept: bounding VOLUME.** The replacement is three things, none of them a pinned
number: a repetition check (the same sentence on three or more repeating cards or rows, or one
number-plus-noun fact stated twice), a sentence-shape check (a sentence over 25 words, or a
caption repeating 60%+ of its own heading's words), and the text-density reviewer
(`scripts/text-density/`). That third piece stays a repeatable ON-DEMAND pass rather than a
gate (D18: it writes). See `D-text-shape-checks` for the full argument and the mechanism.
