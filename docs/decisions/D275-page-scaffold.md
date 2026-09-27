## D275 — Every screen inherits the page scaffold, and a shrinking list holds the exceptions

**The rule.** The owner, 2026-09-23: "say a new page in the sidebar gets built tomorrow, it should be able to autocall/inherit the properties of the other pages". D272 put those properties in one component, `Page` in `app/src/kit/Page.tsx`. A screen inherits them only if it renders `Page`. D173 says a rule that a machine can enforce must be enforced by a machine. This entry is the mechanism.

**A new screen is one `ROUTES` entry plus a view that returns `<Page>`.**

**Two checks, one static and one in a browser.**

- `make kit-adoption` (`scripts/kit-adoption.mjs`) reads the TypeScript AST, like `scripts/user-strings.mjs`. R1: every `ROUTES` view renders `<Page>` from `./kit` or `./kit/Page`. The reader follows a JSX tag into a local component, or into a component from another screen file, at any depth. It reads named and default imports. So `Shipping`, which renders `OrdersHub` from `Orders.tsx`, passes when `OrdersHub` renders `<Page>`. There is no depth cap. A cap and a shared visited set together made the answer depend on JSX order. The visited set alone stops a cycle. R2: outside `app/src/kit/`, no screen hand-rolls a primitive that the kit owns. The rule refuses a dialog role, a native `<dialog>`, a search input, a raw `<select>` and a kit-reserved class name. It refuses a hand-rolled date format, which includes `toLocaleString` with date options. It refuses a hand-rolled dollar amount: a `$` before a template or JSX value, `'$' + x`, or a currency `Intl.NumberFormat`. Some of these are heuristics, and the script's header states the edge of each. For example, a text input counts as a search input only when its placeholder or label names a search (`search`, `find`, `filter` or `look up`).
- `app/tests/scaffold.spec.ts` reads `ROUTES` through the same reader (`kit-adoption.mjs --routes`). It measures each route at 1440, 820, 720 and 390. It asserts one `[data-bn-page]` and one visible h1 with the route's `title ?? label`. It asserts a max-width of `--bn-page-w`, an h1 gap of `--bn-page-top`, and no sideways scroll. It also asserts the palette's "Go to" group and a keyboard-sheet entry for each route. It asserts one fixed tab title, "番地 " and the screen name in lowercase, such as "番地 pricing". Home's title is "番地 home". The title does not alternate and carries no "— Banchi". That is the owner's ruling of 2026-09-23. The spec reads the title on a fake clock every half second for 30 seconds, with normal motion and with reduced motion. One read under reduced motion never saw the old alternation. A `max-width` that is not a length, such as `none`, fails the width check. Two fixture tests prove that the width and title checks fail on their defects. `make design-check` runs the spec. Because the spec reads `scripts/kit-adoption.mjs` and the allow list, both files are in the browser scope (D141). So a change to either one runs the browser suite on CI.

**Three home files, and one specimen sheet.** A rule that points at a primitive cannot forbid that primitive. `app/src/SearchField.tsx` draws the one search input, `app/src/dates.ts` the one date format and `app/src/money.ts` the one money format. Each is exempt from its own rule only. `app/src/Gallery.tsx` is the kit's specimen sheet. It draws each kit class raw so a person can see it, so it is exempt from the class rule only. R1 and the other R2 rules still apply to it.

**The exceptions are a shrinking offender list, never a pinned count.** This is the owner's ruling on Q3, 2026-09-23. `scripts/kit-adoption-allow.json` holds two blocks. `static` is file -> rule -> lane, read by the static check. `runtime` is route -> assertion -> lane, read by the spec. The lane is the lane that owes the fix. Both readers fail on a violation that the list does not name. Both also fail on an entry that no longer matches a violation, which is a stale entry. A lane that moves a screen onto `Page` deletes that screen's entries in the same commit. A stale-entry check cannot stop a branch from adding an entry. So `make kit-adoption` also reads the list at the merge-base with `origin/main`, with plain git reads. It fails on any key in either block that the list there does not hold. So every rule that exists at the merge-base only shrinks. There is one exception, the orchestrator's call of 2026-09-23 (option b). A new key is allowed when its rule is not defined at the merge-base, which means that the rule was born on the branch. A new rule finds offenders that nobody could list before the rule existed. The check reads the definitions at the merge-base and does not guess them. For `static` it reads the keys of `RULES` in `scripts/kit-adoption.mjs`. For `runtime` it reads `PER_ROUTE` and `SHELL_WIDE` in `app/tests/scaffold.spec.ts`. It prints each allowed key, with the rule that allowed it and why. A definition that the check cannot read allows nothing. The exception holds only while every rule that the merge-base defines still exists at HEAD (option a, 2026-09-23). If a branch removes or renames a rule, the check refuses all growth and names the missing rule. Without this, a rename such as `R2-money` to `R2-cash` would pass as a new rule and bring the old debts back. After the branch merges, the new rule exists at every later merge-base, so it only shrinks too. The check fails open, and prints why, when there is no merge-base or no list at the merge-base. The branch that creates the list is the one case where every entry is new. That branch is the guards lane, where the list was born. It is the one place the list grew. An entry covers every occurrence of its rule in its file. It is a debt per file, not a count.

**What the shell owes is on the same list.** The palette, the keyboard sheet and the document title are the shell lane's work. Their failing routes are entries with lane `shell`. Nothing is skipped. The list gets shorter when the shell lands.

**The Fulfiller's screen has a named exemption, not an allow entry.** An allow entry is a debt that a lane must pay. An exemption is a ruling that an assertion does not apply. D5 gives the Fulfiller a screen with no shell and no brand, and `docs/DESIGN.md` sets its own floors. So a `persona: 'fulfiller'` route is exempt from `width`, `top` and `title`. It is still held to `page`, `h1` and `scroll`. The exemption is `EXEMPT` in the spec, with each reason beside it. The spec refuses an allow entry for an exempt assertion.

**AMENDED 2026-09-25: Home's h1 stays the greeting, and the Fulfiller's screen gets a `Page` variant instead of an allow entry.**

*Home's h1.* Home's hero draws the greeting ("Good morning.") as its h1. The route's own title
is "Home". So `scaffold.spec.ts`'s text match failed at every width, and the allow list carried
an entry for it (lane `home`). The follow-up lane after PR 2 raised the question. It named D121,
the hero's own greeting, as the reason a quick fix was not safe. The owner's ruling, 2026-09-25:
"yeah just keep the greeting". The lane also proposed a hidden "Home" h1 beside the visible
greeting. That option was declined in the same round. The document title already reads "番地
home". No screen reader here depends on a second, unseen h1.

The text match is now a named exemption. It is `H1_TEXT_EXEMPT` in `app/tests/scaffold.spec.ts`,
keyed by route path, not by persona. Home still draws exactly one visible h1, the same rule
every route holds to. Only the comparison against `title ?? label` is skipped for Home.
`h1Failure`, the pure judge behind the assertion, carries its own unit test. It checks a
non-Home mismatch, an empty h1, and a doubled h1. Each stays red, so the exemption cannot widen
to cover a defect on another screen.

The allow list's `"/" -> "h1"` entry is deleted. It is no longer a debt: the assertion no longer
expects Home's h1 to equal its title. The `"/" -> "top"` entry is a separate question and stays.
The hero pushes the h1 well past `--bn-page-top`, and the owner has not ruled on the hero's own
layout.

*The Fulfiller's screen.* `#/fulfillment` carried three allow entries. `R1`: it rendered its own
`<main>`, never `<Page>`. `R2-class`: it wrote the kit-reserved `bn-empty-art`/`bn-empty-well`
class names raw. The 2026-09-20 system review had promoted those two classes out of this same
screen. `page`: no `[data-bn-page]` reached the browser at all.

The ruling keeps the screen's own header and its own h1. D5 gives it no shell, so a second h1
inside `Page`'s own header would be a duplicate. The ruling exempts the screen from the kit's
page width and top gap, which `EXEMPT` already covered for it.

`Page` gained two props for this. `header={false}` skips `Page`'s own `<header>`, so the
screen's own header and h1 in `children` are the only ones drawn. `width={false}` skips the
kit's width, top gap and enter animation. It sets `data-bn-page-width="auto"`, read by a new
rule in `kit.css`. The enter animation moves by `transform`. This screen's sheet and zoomed
photo are `position: fixed` children of the page element. A transformed ancestor would break
their reach past the page. `Page` still renders `data-bn-page=""` either way, so the `page`
assertion holds.

Fulfillment's two reserved-class usages became local `ff-empty-art`/`ff-empty-well` classes,
with the same CSS declarations. A screen outside the kit may not write a kit-reserved name
(R2-class). D5's whole point is that this screen owns its own chrome. Un-sharing these two
classes back into `Fulfillment.css` follows that ruling, rather than working around it.

The `R1`, `R2-class` and `page` entries are deleted from `scripts/kit-adoption-allow.json`, in
the same commit as the fix. That is D275's own rule.

*Capture's top gap.* `#/capture` also carried a `top` entry. The screen keeps its own page pad
smaller than the kit's, so the viewfinder stays above the fold. A layout exists that keeps
both. `.capture.bn-page`'s padding-top moved from a flat 12px to `var(--bn-page-top)`. That
token is 24px on a desktop window and 16px on a phone, the same drop `tokens.css` already gives
every other screen below 768px.

Two places tracked the old flat value, and both moved with it. `--cap-chrome`, the calc() this
screen's own desktop stage height reads, had `var(--bn-3)` as its first term. It now reads
`var(--bn-page-top)`. The fold math this screen already carries for `--cap-head-h` stays exact.
The phone layout's own `.capture-stage` height is a separate, hand-measured `clamp()` budget,
built from real DOM rects rather than a formula. Its two constants (366px, 218px) moved by the
same 4px the phone pad grew by. This was confirmed against the real DOM at 390x754, 390x667,
390x844, 720x900 and 820x1180. No width in that set overflows the fold, and the shutter stays
clear of the fixed tab bar in each. The `top` entry is deleted from
`scripts/kit-adoption-allow.json`.

**What neither check can see.** A class name, role or type that reaches JSX through a variable. A view that picks its component at run time (`const V = a ? A : B`). A view that renders `<Page>` on one branch and something else on another. R1 asks only whether the view reaches `<Page>`. The spec measures only the state that its fixtures build.

**Where they run.** Both write nothing (D18). The self-test builds its fixtures as in-memory maps. It also reads the repository: one case runs `git merge-base` and `git show` to read the committed list and rules at HEAD. Those reads write nothing. `kit-adoption` and `kit-adoption-selftest` are in `make check` and `make ci-check`, not the git hook, because they need `app/node_modules`. Neither is on the `guard-scope.py` roster. D247 says that a new guard self-test is not scoped until someone adds it by hand. It also says that which targets to gate is a product judgement. This self-test takes under a second, so there is no reason to gate it.
