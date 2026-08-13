import tseslint from 'typescript-eslint'

/* eslint, flat config. Build-order step 7a item 6.
 *
 * This file exists for two rules. `docs/DECISIONS.md`'s v1 bug table names "lint rule"
 * as the guard on bugs 2 and 3, and from the day that table was written until this file
 * landed, neither guard existed. A table that names a control which is not there is
 * worse than one that admits there is none: the next session reads the column and stops
 * looking.
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
 *    argument D16 makes about `--no-verify`, applied one target over. The two rules
 *    below are the ones worth stopping a build for.
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

/* Both messages name the bug number, what it broke, and where the ruling lives. A rule
 * whose message reads "Unexpected use of restricted syntax" is a rule the next person
 * deletes to get their build green, because nothing on screen tells them what it cost
 * last time. Consts rather than repeated literals: each guard needs two selectors for
 * esquery's sake and is composed into two config blocks below, so a hand-copied message
 * would have four places to drift between.
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
      /* Parser only. No `projectService`, so no type information: neither rule needs a
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
      'no-restricted-syntax': ['error', ...FACING_MODE_RULES, ...SPLIT_COMMA_RULES],
    },
  },
  {
    /* The one exception, named rather than generalised. `parseRgb` in this spec splits
     * the `rgb(20, 64, 175)` string `getComputedStyle` returns — three numbers between
     * literal parens, no quoting, no field that can contain a comma, and nothing a CSV
     * library would parse better. The selector cannot tell that apart from a CSV line,
     * because syntactically it is not.
     *
     * Scoped to the single file, and only the split guard is dropped: `facingMode` still
     * errors here. The general form — turning the rule off for `tests/**` — was declined,
     * since a later spec reading a fixture export is exactly the CSV parsing this guards.
     *
     * This belongs at the call site as an `eslint-disable-next-line` carrying the same
     * reason, where a reader of that function sees it; it is here because that file was
     * owned by another session when this landed. Moving it means deleting this block.
     * Delete it outright if that spec stops parsing colours.
     */
    files: ['tests/pull-confirm.spec.ts'],
    rules: {
      'no-restricted-syntax': ['error', ...FACING_MODE_RULES],
    },
  },
)
