import tseslint from 'typescript-eslint'

/* eslint, flat config. Build-order step 7a item 6.
 *
 * `docs/DECISIONS.md`'s v1 bug table names "lint rule" as the guard on bugs 2 and 3, and
 * from the day that table was written until this file landed, neither guard existed. A
 * table that names a control which is not there is worse than one that admits there is
 * none: the next session reads the column and stops looking.
 *
 * THE RULES THAT ARE NOT FROM THAT TABLE ARE THE POINT RATHER THAN THE EXCEPTION. The two
 * above are v1 bugs, carried into this repo as history. The two-argument `.then` is a bug
 * this repo found in itself: Fulfillment.tsx hit it, wrote a paragraph naming the symptom,
 * fixed its own copy — and the same call shape stayed live in four other places for ten
 * days, because a paragraph in one file guards one file. That is the whole principle the
 * v1 rules already stand on, applied to a bug young enough that nothing had got round to
 * writing it down as a rule. A bug becomes a rule here.
 *
 * THE STORAGE RULE IS THE SAME MOVE MADE BEFORE THE BUG, which is new and worth naming.
 * D27 opened `sessionStorage` to the capture screen's own scratch state, narrowly, against
 * a repo-wide ban on browser storage that is really a ban on a second inventory. A carve-out
 * that lives only in prose is one every later session has to re-derive from `CLAUDE.md`'s
 * one-line rule and get right; the failure it invites — a card, a position, anything the
 * server owns, written into a browser store — is D13's two devices quietly disagreeing about
 * where a card is, which nothing downstream would report. So the boundary is a selector, and
 * the file that has argued its way past it is named.
 *
 * Deliberately no shared preset — not `tseslint.configs.recommended`, not
 * `eslint.configs.recommended`. Three reasons, because inheriting a preset is the
 * default and declining one has to be argued:
 *
 *  - Overlap. `app/tsconfig.json` runs strict with `noUnusedLocals`,
 *    `noUnusedParameters` and `noUncheckedIndexedAccess`, and tsc runs on every write
 *    through `scripts/typecheck-hook.py` as well as in `make typecheck`. The half of a
 *    recommended preset that is truth-shaped is already checked by something that runs
 *    more often than this does.
 *  - Precedent. `docs/specs/audit-retirement.md` section 9 rejected markdownlint-cli2 on
 *    565 findings, 91.7% of them one line-length rule: "syntax, never truth". A preset
 *    adopted without reading its findings first is the same purchase.
 *  - Cost of a red target. `make lint` is a prerequisite of `make check`. A check that
 *    goes red over a style opinion is a check people learn to route around — the
 *    argument D16 makes about `--no-verify`, applied one target over. The rules
 *    below are the ones worth stopping a build for, and each of them names what it cost
 *    the last time it was not there.
 *
 * Adopting a preset later is a decision made by running it and reading the output, not a
 * line someone adds because it is what the tseslint README shows.
 *
 * `typescript-eslint` is here for its parser: without it `.ts`/`.tsx` do not parse at
 * all, and the device picker these rules guard is `.tsx`. The umbrella package rather
 * than the bare `@typescript-eslint/parser` because the preset question above is left
 * open, and reopening it should not also be a dependency change.
 *
 * eslint is pinned to 9.x. 10 is out and `typescript-eslint` 8 supports both; there is
 * no rule here that needs anything 10 added, and a major bump is worth making on
 * purpose rather than collecting one on the first clean install after this commit.
 *
 * Nothing here writes. `npm run lint` carries no `--fix`, because `make lint` runs
 * inside `make check`: D18 forbids anything that writes from running on the path that
 * decides whether work is done. Fixing is a separate invocation a human types.
 */

/* Every message names what the rule is about, what it broke or would break, and where the
 * ruling lives — a bug number for the two from the v1 table, a decision id for the two that
 * are this repo's own. A rule whose message reads "Unexpected use of restricted syntax" is a
 * rule the next person deletes to get their build green, because nothing on screen tells
 * them what it cost last time. Consts rather than repeated literals: each guard needs two
 * selectors for esquery's sake and is composed into three config blocks below, so a
 * hand-copied message would have several places to drift between.
 */
const FACING_MODE =
  'v1 bug 3: `facingMode` broke desktop camera selection — a desktop browser has no ' +
  'front/back to choose between, so the constraint selects nothing or the wrong device. ' +
  'Pick the camera by deviceId with a device picker. See the v1 bug table at the end of ' +
  'docs/DECISIONS.md, and D13.'

const SPLIT_COMMA =
  'v1 bug 2: naive `split(",")` CSV parsing. TCGplayer export fields are quoted and ' +
  'contain commas (product names do), so this silently shreds rows and the damage ' +
  'surfaces as a wrong listing, not as an error. Use a real CSV library — PapaParse in ' +
  'JS, `csv` in Python. See CLAUDE.md and the v1 bug table at the end of docs/DECISIONS.md.'

/* Matched by name anywhere, not by the shape of a getUserMedia call. Constraints get
 * assembled in a variable and spread in later, so a selector anchored to
 * `navigator.mediaDevices.getUserMedia(...)` misses the `const c = { facingMode: ... }`
 * two lines above it. The word has no legitimate use in this repo, which is what makes
 * the broad selector safe — there is nothing here for it to be a false positive against.
 *
 * Two selectors because they catch different spellings: `Identifier` covers
 * `{ facingMode: x }` and `c.facingMode`; `Literal` covers `{ "facingMode": x }` and
 * `c["facingMode"]`, which the first is blind to.
 */
const FACING_MODE_RULES = [
  { selector: 'Identifier[name="facingMode"]', message: FACING_MODE },
  { selector: 'Literal[value="facingMode"]', message: FACING_MODE },
]

/* Regex on the argument, not an exact `","`, so `split(", ")` and `split(/,/)` are
 * caught too — those are the same bug wearing a coat, and an exact-match selector would
 * report the honest spelling and wave the sloppy one through. Second selector is the
 * regex-literal form, where the comma lives in `arguments.0.regex.pattern` and never in
 * `value`.
 */
const SPLIT_COMMA_RULES = [
  {
    selector: 'CallExpression[callee.property.name="split"][arguments.0.value=/,/]',
    message: SPLIT_COMMA,
  },
  {
    selector: 'CallExpression[callee.property.name="split"][arguments.0.regex.pattern=/,/]',
    message: SPLIT_COMMA,
  },
]

const TWO_ARG_THEN =
  '`.then(ok, fail)` does not cover its own success handler. Anything the success ' +
  'handler throws — walking a response body that is not the shape the screen expects ' +
  'is the usual one — becomes an unhandled rejection instead of reaching the failure ' +
  'handler beside it, so the screen shows no failure and offers no control to press. ' +
  'Measured: "the screen sat on \'Getting the cards.\' for the rest of the morning with ' +
  'no failure shown and no control to press." Write `.then(ok).catch(fail)`, which ' +
  'catches both and makes an unreadable body fail the same way a dead server does. ' +
  'See the loader in app/src/Fulfillment.tsx.'

/* Anchored on the ARITY and not on what the second argument looks like, because arity is
 * the defect. `.then(ok, fail)` is wrong whether the second argument is an arrow, a named
 * function or a variable, and there is no two-argument `.then` this repo wants: the
 * one-argument form and `.catch` cover every case between them.
 *
 * `callee.property.name` matches `p.then(a, b)` and nothing else, which is the honest
 * limit of this rule. `Promise.prototype.then.call(p, a, b)` and a destructured `then`
 * both slip past it, and neither is a shape anything in this app writes — a selector wide
 * enough to catch them would also fire on every unrelated `then` identifier in the tree.
 * The other two rules take the opposite trade for the opposite reason: `facingMode` has no
 * legitimate use here at all, so matching it by name anywhere is free.
 *
 * ONE SELECTOR, WHERE THE OTHER TWO GUARDS NEED TWO EACH. Nothing about this shape has a
 * second spelling: the member access cannot be written as a string subscript and still be
 * a call to `.then`, and the argument count is not something a literal can disguise.
 */
const TWO_ARG_THEN_RULES = [
  {
    selector: 'CallExpression[callee.property.name="then"][arguments.length=2]',
    message: TWO_ARG_THEN,
  },
]

const LOCAL_STORAGE =
  '`localStorage` survives closing the browser, and D27 permits it for exactly two things: ' +
  'the remembered camera and the photo rotation, both facts about THIS MACHINE, both in ' +
  'app/src/useCamera.ts, neither of which can take a photograph on its own. Everything else ' +
  'the capture screen remembers is a claim about the stack currently at the lens — the box, ' +
  'the set hint, the finish, the game, the in-flight capture id — and those belong in ' +
  '`sessionStorage`, where a new tab is a new shift and closing the browser ends one. ' +
  'Nothing about a card, a position or the inventory goes in either: D13 puts that one ' +
  'truth on the Mac so two devices cannot disagree about where a card is, which is what ' +
  "CLAUDE.md's ban on browser storage has always been about. See D27 for the permitted keys."

/* Two selectors, the same pair the facingMode guard needs and for the same reason:
 * `Identifier` covers `window.localStorage` and a bare `localStorage`, `Literal` covers
 * `window["localStorage"]`, which the first is blind to.
 *
 * MATCHED BY STORE, NOT BY KEY, and that is the honest limit of this rule. The permitted keys
 * are named in D27 and declared in one object in app/src/CaptureScreen.tsx, but a selector
 * cannot read them: `useCamera.ts` passes its keys as consts — `getItem(ROTATION_KEY)` — so
 * the argument is an Identifier with no `value` to test, and a rule that only caught inline
 * string literals would wave through the exact spelling this file already uses. So the store
 * is banned outright and the one file that has argued its way to an exception is named below.
 *
 * The same limit again, stated so nobody reads this guard as more than it is: it says nothing
 * about `sessionStorage`. A card written there would pass. What stops that is the key list
 * being declared in one place with the rule beside it, and a reviewer reading the diff — the
 * same last link D16 leaves in the chain for the docs audit. */
const LOCAL_STORAGE_RULES = [
  { selector: 'Identifier[name="localStorage"]', message: LOCAL_STORAGE },
  { selector: 'Literal[value="localStorage"]', message: LOCAL_STORAGE },
]

export default tseslint.config(
  {
    /* node_modules is ignored by flat config already. These three are build and test
     * output that `.gitignore` also excludes — linting a Playwright report is linting
     * the record of one run. */
    ignores: ['dist/**', 'test-results/**', 'playwright-report/**'],
  },
  {
    files: ['**/*.ts', '**/*.tsx', '**/*.js'],
    languageOptions: {
      /* Parser only. No `projectService`, so no type information: no rule here needs a
       * type to fire, and type-aware linting would make `make lint` a second full
       * compile of a tree `make typecheck` has already compiled. */
      parser: tseslint.parser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    rules: {
      /* `no-restricted-syntax` rather than a custom plugin rule. A custom rule means a
       * plugin package or a local rule module plus a `plugins` entry in this file, and
       * buys nothing here: esquery expresses both shapes directly, and the message field
       * carries everything a rule's `meta.messages` would. */
      'no-restricted-syntax': [
        'error',
        ...FACING_MODE_RULES,
        ...SPLIT_COMMA_RULES,
        ...TWO_ARG_THEN_RULES,
        ...LOCAL_STORAGE_RULES,
      ],
    },
  },
  {
    /* The second exception, and the fourth rule's whole reason for having a shape rather
     * than being a ban. `useCamera.ts` is where D27's carve-out was argued informally before
     * it was a decision — the remembered deviceId and the photo rotation, both of which that
     * file justifies at length beside the keys themselves. They are facts about the machine
     * this browser is running on: meaningless on the Fulfiller's laptop, actively wrong if
     * shared, and neither is about a card.
     *
     * SCOPED TO THE ONE FILE, and only the storage guard is dropped: `facingMode` in
     * particular still errors here, which matters more in this file than anywhere else in
     * the repo, since it is the file that would be tempted. Every guard this block does not
     * name has to be re-listed, which is the cost of `no-restricted-syntax` taking one array
     * per config block — and the right cost, for the reason the block below gives.
     *
     * A blanket ban was the alternative and it is worse in the direction that matters: it
     * would have to be switched off with an inline disable comment at four call sites, and a
     * guard that is routinely disabled inline is one the next person disables without
     * reading. Naming the file keeps the exception in one place a reviewer can see whole. */
    files: ['src/useCamera.ts'],
    rules: {
      'no-restricted-syntax': [
        'error',
        ...FACING_MODE_RULES,
        ...SPLIT_COMMA_RULES,
        ...TWO_ARG_THEN_RULES,
      ],
    },
  },
  {
    /* The one exception, named rather than generalised. `parseRgb` in this spec splits
     * the `rgb(20, 64, 175)` string `getComputedStyle` returns — three numbers between
     * literal parens, no quoting, no field that can contain a comma, and nothing a CSV
     * library would parse better. The selector cannot tell that apart from a CSV line,
     * because syntactically it is not.
     *
     * Scoped to the single file, and only the split guard is dropped: `facingMode` and the
     * two-argument `.then` both still error here. Every guard this block does not name has
     * to be re-listed below, which is the cost of `no-restricted-syntax` taking one array
     * per config block rather than merging them — and it is the right cost, because a guard
     * silently disappearing from an exception block is exactly the kind of hole this file
     * exists to close. The general form — turning the rule off for `tests/**` — was
     * declined, since a later spec reading a fixture export is exactly the CSV parsing this
     * guards.
     *
     * This belongs at the call site as an `eslint-disable-next-line` carrying the same
     * reason, where a reader of that function sees it; it is here because that file was
     * owned by another session when this landed. Moving it means deleting this block.
     * Delete it outright if that spec stops parsing colours.
     */
    files: ['tests/pull-confirm.spec.ts'],
    rules: {
      'no-restricted-syntax': [
        'error',
        ...FACING_MODE_RULES,
        ...TWO_ARG_THEN_RULES,
        ...LOCAL_STORAGE_RULES,
      ],
    },
  },
)
