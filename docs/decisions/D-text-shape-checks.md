## D-text-shape-checks — Three checks replace one ceiling, and none of them is a pinned number

**The rule.** The owner, 2026-09-23: kill the pinned word ceilings. His own words: "I think we need to kill ceilings and instead just use a different way." He did not want a stagnant static pin. This entry supersedes D194 and its mechanism, `app/tests/copy-budget.spec.ts`. See D194's own "Superseded" note for what carries over.

**Three things replace it. None of them counts words.** A repetition check. A sentence-shape check. The text-density reviewer, kept as a repeatable pass a session runs on demand. It is never a gate (D18: it writes).

**Repetition, two shapes.** The same sentence of four or more words, drawn on three or more elements that share one class — a card, a row, an entry. TXT-01 is the case this shape was built for: "Cards only, and under $50." on 166 Envelope cards. The lane header already says it once. The second shape is a number-plus-noun fact stated twice, in two different prose blocks on one screen. TXT-25 is that case. Home's "Behind that" line repeated the stage strip's own figures below it.

**Sentence shape, two shapes.** A single sentence over 25 words. TXT-13's 52-word run-on is the case this was measured against. The second shape is a caption under a heading, with 60% or more of its own words already in the heading's. TXT-10 is that case: "Pricing is answered." under a heading that says the same thing a different way. A heading of one token is excluded from this second shape. Most routes' own H1 is one word — "Pricing", "Shipping". A caption that merely names the screen is topical, not repetition.

**Where they live.** `app/tests/textShape.ts` holds the one measurement, `measureTextShape`. `app/tests/text-shape.spec.ts` runs it through `page.evaluate`. The function is self-contained. Playwright serialises it by `toString()`, so it may not close over anything outside itself. A "prose block" is the 2026-09-23 density review's own ruler: a block element holding six or more visible words. The repeated-fact check reads only prose blocks. An ordinary data column, "3 boxes" on ten unrelated rows, never trips it.

**The fixture is populated, and the sweep runs at two widths.** `sealEveryTest({ store: true, cards: 122 })` plus `app/tests/routeFixtures.ts`'s `POPULATED_ROUTE_SEEDS`. These are D194's own fixtures, moved rather than rebuilt. A repeated sentence over real rows is exactly the defect an empty-ish screen cannot draw. The sweep runs at 1440 and at 390. `routesFromNav` cannot run under 768px. The 390 pass harvests its roster off the phone drawer instead, on `phone.spec.ts:phoneRoutes`'s own shape. Each spec keeps its own local copy of that harvest; that file belongs to the shell lane, not this one.

**`#/gallery` is excluded, by name.** The argument is the same one `no mechanism on screen`'s own exemption already makes for that route. The kit's specimen sheet draws many repeated example states on purpose. It documents the kit to a builder, not the product to the owner. Measured: eleven "every card has an address" rows and three "#40 of 250" position-bar specimens, none of them a real repetition defect.

**A shrinking pending list, never a count.** `app/tests/text-shape-allow.json` holds route -> assertion -> the lane that owes the fix. The shape is `scripts/kit-adoption-allow.json`'s own, under the owner's Q3 ruling. The spec fails on a hit the list does not name. It also fails on a listed entry that matches nothing this run — a stale entry. A lane that fixes its screen deletes its own entry in the same commit. The list is never a number to hold a screen under. It is one line per real, named finding.

**Mutation-tested.** `TEXT_SHAPE_MUTATE=<hash>` injects the same sentence into three fresh elements inside that route's `.bn-view`. It runs through `page.evaluate`, never by editing a file under `app/src`. `TEXT_SHAPE_MUTATE='#/shipping' npx playwright test tests/text-shape.spec.ts` fails, naming `#/shipping` and the injected sentence. Unset, the suite passes.

**What neither check can see.** Whether a repeated sentence is actually redundant, or two separate facts that share four words. Whether a long sentence is dense because it must be, or because nobody trimmed it. Both checks force the question into the open. Neither one answers it. That is the same shape D194's own ratchet held for volume, carried over here for shape.

### The rendered-text machine-words check (D196's own gap)

**A second, separate check reads what the browser paints, over the same word list.** `scripts/docs-audit.py`'s `no mechanism on screen` row reads `app/src`'s JSX literals through an AST walk. It cannot see a server response relayed verbatim, the demo's own fixture text, or a string composed at runtime. `app/tests/machine-words.spec.ts` reads `.bn-view`'s rendered `innerText` instead. It reads every populated route, at 1440 and 390.

**One word list, `scripts/machine-words.json`, read by both checks.** It held seven entries. It now holds seventeen. Ten are new, on the owner's own instruction to grow the list: `emit`, `sub-threshold`, `index`, `span`, `parked`, `Pushed`, `Staged`, `make demo`, `/pipeline/` and `manual:c`. A bare identifier-shaped word is wrapped in `\b` on both sides. So `emit` does not match inside `emitted`, and `Staged` does not match inside `unstaged`. A phrase with a space, or a path-shaped entry carrying a `/`, is matched as a plain literal instead. `\b` either side of a `/` checks the wrong transition. It would refuse to match at the position the entry exists to catch.

**A request-path shape is checked too.** It reads the same repo-top-dirs list `scripts/docs-audit.py`'s own path check reads, held once in `scripts/machine-words.json`'s `repoTopDirs`. So the Python check and the browser check cannot drift apart on what counts as a path.

**`Notice`'s `code` prop stays structurally un-extracted by the AST walk, unchanged.** `D-notice-detail` moved a code or a server path behind a closed `<details>`, "What the server said". A closed `<details>` renders nothing but its summary. The UA stylesheet sets `display: none` on the rest. So `innerText` — never `textContent` — already reads exactly what the owner sees, with no special-casing needed.

**`#/gallery` is excluded from this check too, the identical argument.** The kit sheet illustrates real pipeline vocabulary on purpose. A `banchi emit runs/2026-09-02-box6-01` example line documents the mechanism. It does not leak it.

**A second shrinking pending list, keyed by route rather than file.** `app/tests/machine-words-allow.json` is that list. Rendered text carries no source file, so route is the closest stable key. `scripts/machine-words-allow.json` is the AST check's own list, keyed by file, unchanged in shape. The two lists are separate on purpose. A hit in one does not imply a hit in the other, because the two checks read different things.

### The rendered-page money check (D221)

**A third check, in the same file family, reads every visible dollar figure against the mono face.** The owner, 2026-09-23, after seeing both options drawn: mono everywhere, inputs and chips included. Plus a check that refuses a dollar figure drawn any other way. `app/tests/moneyFace.ts:scanMoneyFace` runs through `app/tests/money-face.spec.ts`. It matches `$1.23`, `$66,334.71`, `+$1.20` and `−$0.35` shaped text in `.bn-view`. Each match's ancestor's resolved `font-family` is read through `getComputedStyle`. A resolved style is checked rather than a class name, because the requirement is visual. A descendant that inherits the mono face without carrying `.bn-money` itself still satisfies D221.

**Inputs and chips are checked too.** A form control's typed value is never a text node. It needs its own pass. Every visible `<input>` and `<textarea>` whose value or placeholder reads as a dollar figure is checked the same way.

**A third shrinking pending list, keyed by route alone.** `app/tests/money-face-allow.json` holds it, one level deep, not route -> amount -> lane. The fixture's own seeded card weights and prices are random. The specific figure a route draws can change from run to run. Keying on the amount would make the pending list flake with the fixture, not with the product. Keying on the route is what the orchestrator's own "shrinking allow list by file -> lane" instruction names.

**Mutation-tested.** `MONEY_FACE_MUTATE=<hash>` injects a `$4.20` span styled in Inter, through `page.evaluate`, never by editing `app/src`. `MONEY_FACE_MUTATE='#/pricing' npx playwright test tests/money-face.spec.ts` fails, naming `#/pricing` and the figure.

### The on-demand text-density pass

**The third piece of the owner's ruling is a repeatable reviewer, not a gate.** `scripts/text-density/` holds it. `make text-density` runs it, against this checkout's own dev server. The port is derived through `app/devPort.ts`, the way every other tool in this repo derives it. It is never a hardcoded URL, and never the published demo. It is not in `make check`. D18 forbids a writing check from gating a commit, and this tool writes a report. It has a skill, `.claude/skills/text-density/SKILL.md`, so a future session can run it without rediscovering the 2026-09-23 review's own method.

**What it measures.** The same "prose block" ruler the repeated-fact check above uses: a block element with six or more visible words. It also measures a whole-page word count, above the fold and below, and a per-route breakdown a session can read as a cut table. It renders nothing and asserts nothing. Its output is a table for a person to read, the way the 2026-09-23 density review's own findings (`docs/reviews/ux-2026-09-23/density.md`) were read by hand.

**Why an on-demand tool, and not a ratchet.** A ratchet needs a stable measurement to hold steady against. Word density is exactly what D194's "Not mechanized" section already named as unmeasurable in the general case. Whether an addition was worth its words is a judgement call, not an arithmetic fact. The owner's own ruling was to stop pretending it could be pinned. The review stays a tool a session reaches for, rather than a number nobody re-derives.
