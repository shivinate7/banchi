## D284 — Three checks replace one ceiling, and none of them is a pinned number

**The rule.** The owner, 2026-09-23: kill the pinned word ceilings. His own words: "I think we need to kill ceilings and instead just use a different way." He did not want a stagnant static pin. This entry supersedes D194 and its mechanism, `app/tests/copy-budget.spec.ts`. See D194's own "Superseded" note for what carries over.

**Three things replace it. None of them counts words.** A repetition check. A sentence-shape check. A density pass that a session runs on demand. The pass prints a cut table and is never a gate (D18: it writes).

**Repetition, two shapes.** The first shape is one sentence of four or more words, drawn on three or more elements. The elements share one base class: a card, a row, an entry. A base class is a class token with its BEM modifier cut off. A state token (`is-open`, `has-photo`) is never one. So a card with a modifier still groups with its plain siblings. TXT-01 is the case this shape was built for: "Cards only, and under $50." on 166 Envelope cards. The second shape is a number-plus-noun fact stated twice, in two different prose blocks on one screen. TXT-25 is that case.

**Sentence shape, two shapes.** The first is a single sentence over 25 words. TXT-13's 52-word run-on is the case this was measured against. The second is a caption under a heading, with 60% or more of its own words already in the heading's. When the heading sits alone in a `<header>`, the search continues after the `<header>`. TXT-10 is that case. A heading of one token is excluded: most routes' own H1 is one word, and a caption that names the screen is topical, not repetition.

**Where they live.** `app/tests/textShape.ts:measureTextShape` is the one measurement. `app/tests/text-shape.spec.ts` runs it. A "prose block" is the 2026-09-23 density review's own ruler: a block element that holds six or more visible words. The repeated-fact check reads only prose blocks. So a data column ("3 boxes" on ten unrelated rows) never trips it.

### One sweep, one state, for every text check

**The three rendered-text specs share one sweep, `app/tests/routeSweep.ts:sweepEveryRoute`.** They are `text-shape.spec.ts`, `machine-words.spec.ts` and `money-face.spec.ts`. The sweep reads every route at 1440 and at 390. At 1440 it harvests the routes off the nav. At 390 it harvests them off the phone drawer, because the nav links are hidden under 768px. It appends `#/product` with a SKU. That route is off-nav, and without a SKU it draws only a search.

**The fixture is deterministic.** It is `sealEveryTest({ store: true, cards: 122 })` plus every seed in `app/tests/routeFixtures.ts:POPULATED_ROUTE_SEEDS`. The sweep registers every seed once, before the first navigation. Nothing in either fixture is random. The first build said the fixture was "seeded-random". That was false. The variation it saw had two causes. First, each seed was registered when the sweep reached its own route, so the handlers piled up in nav order. A screen drawn before `#/orders` at 1440 read an empty ledger, and the same screen at 390 read a full one. Second, the specs measured before the screen had loaded.

**A screen is read only once it is loaded.** `routeSweep.ts:openSettled` waits for five things. `.bn-shell[data-route]` names the route. Exactly one `.bn-view` exists. Nothing is `[aria-busy="true"]`. No `fetch` or `xhr` read is open, and none starts. `.bn-view`'s text holds still. All of these hold together for 450ms. A screen that never settles fails the run and names the route and its last reads. The open-read count is necessary, because `#/inventory`'s "Reading the inventory…" has no `aria-busy`. It was measured on 2026-09-24, with every inventory read held for 900ms. A text-stability wait alone read that route at 4 words. The full wait read the painted 197.

**The wait found a request loop on `#/orders`.** With `shell.ts:stubStore`'s empty `POST /orders/picks` answer, `#/orders` asked for the same keys again and again: 4,934 requests in 10 seconds, measured 2026-09-24. A real server leaves out a key that the ledger no longer holds. So the loop can happen in the product too. The seeded orders seed now answers every key it holds, as the real route does. A request loop fails every run, because a read that starts inside the quiet window resets it. Proved: with the empty answer back, the sweep failed 3 runs of 3 on `#/orders`.

**What no sweep reads.** Only each route's landing state, plus the one export `#/shipping` gets and the SKU `#/product` opens with. No sheet, modal, popover, toast, drawer or palette is opened, so their copy is never read. Each check reads `.bn-view` alone, so the sidebar, the phone bars and the banner are never read. `#/fulfillment` and `#/gallery` are excluded. The Fulfiller's screen has its own floors (`docs/DESIGN.md`). The kit sheet draws repeated specimens and real pipeline words on purpose. It documents the kit to a builder, not the product to the owner.

### Three pending lists, each keyed to the finding

**A shrinking pending list, never a count.** Each spec reads its own list. Each spec fails on a finding its list does not name. It also fails on a listed entry that matches nothing this run: a stale entry. A lane that fixes its screen deletes its own entries in the same commit. The shape follows `scripts/kit-adoption-allow.json`, under the owner's Q3 ruling.

**Each list is keyed to the finding, so an entry excuses one finding and no other.** A new finding on a route that already has an entry is red.

- `app/tests/text-shape-allow.json`: route -> assertion -> finding key -> lane. The finding key is the finding's own text: the repeated sentence, the repeated fact ("4 copies"), the first 80 characters of a long sentence or of a caption.
- `app/tests/machine-words-allow.json`: route -> word or path -> lane. There is no wildcard route.
- `app/tests/money-face-allow.json`: route -> amount -> lane. The amount is the figure as the screen draws it ("$4.20", "$50").

**Mutation-tested, each through `page.evaluate`, never by an edit under `app/src`.** Each hook injects a finding that no real screen draws. So each proof also shows that a new finding on a listed route is red.

- `TEXT_SHAPE_MUTATE='#/'` trips all four text-shape assertions on `#/`. Its three cards differ by a modifier class, and its heading sits alone in a `<header>`.
- `MACHINE_WORDS_MUTATE='#/capture'` draws "the resolver".
- `MONEY_FACE_MUTATE='#/shipping'` draws `$987.65` in Inter.

**What neither text-shape check can see.** Whether a repeated sentence is redundant, or two separate facts that share four words. Whether a long sentence is dense because it must be, or because nobody cut it. Both checks force the question into the open. Neither one answers it.

### The rendered-text machine-words check (D196's own gap)

**A second check reads what the browser paints, over the same word list.** `scripts/docs-audit.py`'s `no mechanism on screen` row reads `app/src`'s JSX literals through an AST walk. It cannot see a server response relayed verbatim, the demo's own fixture text, or a string composed at runtime. `app/tests/machine-words.spec.ts` reads `.bn-view`'s rendered `innerText` instead.

**One word list, `scripts/machine-words.json`, read by both checks.** It held seven entries. It now holds seventeen. Ten are new, on the owner's own instruction to grow the list. They are `emit`, `sub-threshold`, `index`, `span`, `parked`, `Pushed`, `Staged`, `make demo`, `/pipeline/` and `manual:c`. The browser matches a bare word only where no LETTER touches it on either side. So `emit` does not match inside `emitted`. The Python row uses `\b`, and the browser cannot. `innerText` joins two adjacent spans with no space. `#/orders` draws "Pushed 0Staged 0", and `\bStaged` never matches after the digit. On 2026-09-24 the letter boundary found `Staged` on `#/orders` and `index` on `#/codes` ("Box 12index 1"). `\b` missed both. A phrase with a space, or a path-shaped entry, is matched as a plain literal. `scripts/browser-scope.py`'s `SCOPE` names the word list, so a change to it runs the browser matrix on CI.

**A request-path shape is checked too.** It reads `repoTopDirs` in `scripts/machine-words.json`, the same list the Python path check reads.

**A closed `<details>` needs no special case.** `D269` moved a code or a server path behind a closed `<details>`. The UA stylesheet hides all of it but the summary. So `innerText` reads exactly what the owner sees.

**The two machine-word lists stay separate on purpose.** `scripts/machine-words-allow.json` is the AST row's list, keyed by file. The browser list is keyed by route, because rendered text carries no source file.

### The rendered-page money check (D221)

**A third check reads every visible dollar figure against the mono face.** The owner ruled on 2026-09-23, after he saw both options drawn. Money is mono everywhere, inputs and chips included. A check refuses a dollar figure drawn any other way. `app/tests/moneyFace.ts:scanMoneyFace` runs through `app/tests/money-face.spec.ts`. It matches `$1.23`, `$66,334.71`, `+$1.20`, `−$0.35` and a whole-dollar `$50` in `.bn-view`. It reads each match's resolved `font-family`, not a class name, because the rule is visual. A form field is read as money when its value has cents or a `$`, or its placeholder has a `$`.

### The on-demand density pass

**`make text-density` prints a cut table off the same sweep.** It runs `app/tests/text-shape.spec.ts` with `TEXT_DENSITY=1`, one worker, and the `line` reporter. In that mode the spec writes each route's measurement to `.serve/text-density.json` and asserts nothing. `scripts/text-density/density.mjs` prints the table from that file. So the pass reads the same populated fixture and the same loaded screens as the gates, at 1440 and 390. The checkout's own store does not matter. The command-line reporter replaces the config's reporters, so the pass never writes `.serve/design-check.json`. It is not in `make check` or `make design-check`.

**What the table shows.** For each route and width it shows the view's word count and the largest prose blocks with their word counts. Then it lists every repeated sentence, repeated fact, sentence over 25 words, and caption that repeats its heading. `ARGS="--route '#/pricing' --top 8"` narrows it. The skill `.claude/skills/text-density/SKILL.md` says how to read it.

**Why an on-demand pass, and not a ratchet.** A ratchet needs a stable measurement to hold against. Whether an addition was worth its words is a judgement, not an arithmetic fact. The owner ruled to stop pinning it. The pass is a tool a session reaches for, not a number nobody re-derives.

### Pending, for other lanes

**Findings the checks list, each for the lane that owns the screen.**

- `sales`: `#/revenue` draws a 28-word sentence ("0 lines were marked refunded or canceled during fulfilment and left out…") and draws `$3.31` in Manrope.
- `product`: `#/product` draws a 26-word sentence ("Reported precision decays over time for a fixed sale…").
- `home`: `#/` states "4 copies" in two prose blocks.
- `orders`: `#/orders` re-asks `POST /orders/picks` without end for a key the answer leaves out (`Orders.tsx:fetchMissingPicks`). Every answer makes a new `detail` map, which makes the fetch effect run again.
- `shipping`: `#/shipping` draws `$4.20`, `$12.40`, `$18.00` and `$50` in Inter.
- `capture`, `b-runs`, `inventory`, `library`: the machine words in `app/tests/machine-words-allow.json`.

**Stale `copy-budget` comments outside this lane's files.** Each names the deleted spec, its ceiling file, or its pin script as if they were live.

- `orders`: `app/src/Orders.tsx`'s comment above the buyer-list re-sort names the ceiling file and `node scripts/copy-budget.mjs --pin`. `app/tests/orders.spec.ts`'s fixture header names `copy-budget.spec.ts` as a reader.
- `sales`: `app/src/Revenue.tsx` cites a cost measured by `copy-budget.spec.ts`.
- `docs-sweep`: `app/tests/shipping.spec.ts`'s fixture header and `app/tests/phone.spec.ts`'s populated-graveyard comment each name `copy-budget.spec.ts` as a reader.

The decision entries and reviews that name `copy-budget` are history, and stay as written.
