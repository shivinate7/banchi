## D50 — Interactive feedback belongs to the product

**Cursor and hover feedback are set once in `base.css` for every control kind.** Each screen does not set them.

The owner reported that the cursor did not change correctly. The owner then granted hover darkening, edits to the fixed palette, and a guard for interactive feedback.

**The palette is locked. This is the first token added against the lock.** `docs/DESIGN.md` records that the owner chose every value from rendered alternatives. `--field-hover` was measured, and the owner granted it against the lock. A later session must read it as a grant with a reason, not as drift.

**The defect was not mainly about color. The premise had to be corrected first.** The first count found 39 interactive elements with no reachable `cursor` rule. That is true of the CSS, but most of those elements are `<a href>` and `<input type="text">`. The user agent already answers those correctly. The real concentration was the disabled state. No per-file rule covered it. Of 65 control shapes, 41 had a wrong cursor. 30 clickable controls showed `pointer` while they refused the click. 7 text fields showed `text` while they refused input. 2 `<select>` controls showed `default`. 2 buttons showed `default` while disabled, where 18 siblings showed `not-allowed`. Missing `:focus-visible` was **zero**. `base.css` already had a global ring.

**The default lives in the reset, not in a note asking each screen to remember.** Six stylesheets declared no cursor at all. Their authors had no reason to consider it. `base.css` now covers `button`, `select`, the three toggle input kinds, `[role='button']`, a label that owns a toggle, and the disabled state. The focus ring already works this way. `app/eslint.config.js` does too. **A rule in one file guards one file.**

**The floor's guarantee comes from cascade order, not specificity.** The first draft said every rule had specificity (0,0,1). That is false for eight of the eleven selectors. `input[type='checkbox']` is (0,1,1), `[role='button']` is (0,1,0), and the disabled state is (0,1,1). The behavior was correct anyway. `main.tsx` imports `base.css` before every component sheet, so a tie goes to the component. The comment was corrected. Preserve the import order. If `base.css` loads after a component sheet, the floor inverts.

**The disabled state outranks a rest-state class on purpose.** `button:disabled` at (0,1,1) beats a bare `.foo { cursor: pointer }` at (0,1,0). A screen that needs a different disabled cursor adds its own class.

**The token is `--field-hover`, #6B6E73. `--muted` was refused on contrast.** `--field` is 3.36:1, the faintest edge WCAG 1.4.11 permits, so a text field had no hover response. `--muted` needs no grant, but it fails. **The test is contrast against `--ink`, not against the ground.** Every focus treatment on these controls is an ink `outline`. A hover border must differ from focus.

```
--field   #8C8C8C   5.93:1 against ink   rest, and no hover response at all
this      #6B6E73   3.89:1 against ink   1.52x the rest edge, still clearly not focus
--muted   #4E5157   2.50:1 against ink   2.37x the rest edge, and reads as focus
```

On surface, bg and hover, the token measures 5.12, 4.99 and 4.69:1. That clears WCAG 1.4.11's 3:1 on all three grounds. **It works with focus.** Hover darkens the border. Focus draws an outline outside it. A control that is both shows both.

**The token has one job.** `--field-hover` reaches the seven typed-into controls only. Buttons already lift to `--hover`. The token adds no second hover ground. It carries no text and is never a background, so `docs/DESIGN.md`'s rule that every text token clears 7:1 still holds.

**One rest-state change came with it. The owner can overrule it.** `CaptureScreen.css`'s `.capture-entrybox` used `--line` (1.24:1). Every other typed-into box used `--field`. The token missed this control. The box now uses `--field`, which applies the existing `docs/DESIGN.md` rule. The border is darker at rest, on the screen the owner uses most.

**The guard is a spec.** Nothing in `app/tests/` checked cursors, so `make design-check` stayed green through the whole defect. `app/tests/cursor.spec.ts` checks the classes across every route. A clickable reads `pointer`. A disabled control reads `not-allowed`. A text field reads `text`. The spec does not pin a selector list, so a new button without a cursor fails it.

**The spec checks the rule, not a fixed roster.** D38 draws the same line for the copies row. A pinned count passes after the defect moves somewhere else. The spec finds controls itself.

**The ROUTES list had the same flaw for two days.** `app/tests/cursor.spec.ts` first shipped with seven hand-typed hashes. D69 added `#/orders` and `#/shipping` that day, and D70 added `#/codes`. None reached the list, so three screens went unchecked and `make design-check` stayed green. A missing route does not fail a pinned list. It only skips that route. Repaired in a later change. The spec reads the nav strip, which `App.tsx` builds from the same table it routes from. `#/codes` showed `default` on disabled buttons, which is the 30-of-41 class. Where a pinned list is intended, `app/tests/nav.spec.ts`'s Cmd-arrow ring (D51) for example, `scripts/docs-audit.py`'s `route rosters` row checks the list against `App.tsx` at commit.

**No `:active` pass was the first decision. It was struck on the owner's instruction.** The reason given was that only three files had one. By then it was 16 files and 29 rules, with no floor and no guard. The churn it predicted arrived anyway, one sheet at a time, with press values from `scale(0.9)` to `scale(0.995)`. Nothing reconciled them. The reflow risk is answered below. No hover state may change `border-width`, `padding`, `font-size` or `font-weight`. **D28's defect was the review queue moving under a finger that was already moving toward a target.** A hover that reflows repeats that defect in small. The first check found zero reflow offenders on seven routes. That check ran against an empty store, so it missed rules on controls that did not render. A second check read all 64 `:hover` rules in all 26 sheets under `app/src/`. It found zero offenders, and it supersedes the first.

**Amended: the response floor.** The title of this entry finally reached `base.css`. The owner said hover felt unintuitive, and named the sidebar's rail toggle. That control is `.bn-brand`. It declared `border: 0` and painted a hover background with **no `transition`**. Its 109px slab appeared in one frame. The nav links beneath it faded a smaller pill over 120ms. A hard edge with no ease, under a moving pointer, reads as a wrong border.

**The same control had a second fault. D110 is the other half.** The hover slab used `var(--bn-surface-3)`. It measured **ΔL\* 8.67** against the sidebar ground. A row on a panel measures 4.00. The slab was more than twice the product's hover step, and it read as selection. D110 sets the value: one alpha token over any ground. This amendment sets the timing. **Neither works alone.** Without D110, the floor eases an oversized slab into place. Without the floor, a correct step still snaps. Measured in both themes after the merge, the two work together. `transparent` is `rgba(0,0,0,0)`, and interpolation is premultiplied. So the RGB channel stays constant and only alpha ramps. Light goes `0.02 → 0.027 → 0.03`, and dark goes `0.027 → 0.035 → 0.04`. No flash appears.

**This entry covers feedback for each control. Only the cursor had reached the floor.** `cursor` was set once for every control kind. Each hover response was left to whichever sheet wrote a `transition`. Most did. The ones that did not looked broken rather than plain.

**Measured before any change.** The check hovered all 315 controls on the eleven routes against `shell.ts`'s shared store, after each transition finished:

    respond to the pointer   293 of 315
      eased                  276      (270 at --bn-t-fast, 6 at 200ms)
      SNAPPED                 17      six classes in five sheets
    no response at all        22      9 of them the CURRENT page's nav link

**Ten of the seventeen snapping controls were `.bn-brand`, once per route.** The response floor reduced the snapping count to **0 of 294** in one block, with no edit to any screen.

**Method note: sample a hover only after the transition ends.** During a transition, `getComputedStyle` returns the animated value. At t=0 that is the old value. A sample taken then reads every eased control as unchanged. The first pass gave the inverse of the truth.

**`a` is in the response floor and not in the cursor floor.** This is the one place the two selector lists differ. A bare `<a href>` never had a cursor defect, because the user agent answers it. The user agent gives it no transition, so a link with a hover color snaps unless a sheet adds one. `.home-more` on Home was two of the seventeen. **The user agent sets the cursor, but time still needs a rule.**

**Four properties are eased, and the omissions are the argument.** The floor eases `background-color`, `border-color`, `color` and `box-shadow`. All four repaint, and none moves a target. `transform`, `padding`, `width` and `font-size` are left out, because a hover must not reflow. `transition: all` would ease all of them the first time a screen touched one. `opacity` is left out because mount and unmount animations already own it. The guarantee comes from cascade order, as with the cursor floor. `main.tsx` imports `base.css` first. A `transition: none` in a screen's own rule is the only exception needed.

**The guard found five more defects that the floor cannot reach.** `app/tests/cursor.spec.ts` now reads the CSSOM instead of hovering. It reported five `.parent:hover .child` rules. Each repaints a descendant: `.home-deck-card`, `.capture-k`, `.position-run`, `.review-caption-go`, `.kit-icon`. A hover check samples the element under the pointer, so it misses these. They are decoration, not controls, so the floor does not cover them. Each keeps its own transition in its own sheet. The guard also caught a bad fix from this session. A `transition` added at the top of `.kit-icon` was overridden by a second `transition` lower in the same rule.

**The guard reads the CSSOM because hovering sees less.** A hover check finds only what this store draws, and it takes about 100s with one worker. Reading `document.styleSheets` finds every `:hover` rule in every sheet. There are 164 such rules in 31 sheets now. Deleting the floor turns the case red with 8 rules named.

**The press floor was built on the owner's instruction.** The owner questioned the deferral, asked why it should be declined, and gave permission to change the settled entry. The struck paragraph above stays visible, because its reason is worth keeping.

**Measured before any change, over the 311 enabled controls on the eleven routes:** **121 pressed and 190 did not.** The largest silent group was every `.bn-nav-link` in the sidebar, the primary navigation. `.bn-brand` was silent too. After the floor: **317 of 317**. Disabled controls still refuse to move.

**`translate`, not `transform`, makes this floor possible.** The individual transform property composes with `transform` and does not replace it. A blanket rule therefore cannot erase a control's own rotation or scale. That objection would sink a press floor written with `transform`. Before the floor was written, one control had a rest `transform` (`.pull-confirm`). No control used `translate`. No control is a non-replaced inline element. So the property was free and applies to all of them.

**The reflow risk is answered here.** `translate` is composited. A pressed control moves nothing around it, so D28's defect cannot happen. The response floor uses the same test. `padding` and `font-size` fail it, and `translate` passes.

**The two vocabularies meet at one seam, and the guard enforces it.** `translate` is the product's 1px dip. `transform: scale()` is a screen's own emphasis. Six rules wrote the dip as `transform: translateY(1px)`. Each would have doubled the floor to 2px. All six moved to `translate` and kept their scale. `.pull-confirm` was found by the guard. It must write the dip twice. `[data-force-state='pressed']` holds the gallery's pressed look still. That is not `:active`, so the floor cannot reach it.

**1px matches a value the product already used.** `kit.css` pressed `.bn-btn`, `.bn-chip` and `.bn-seg-item` by 1px, and three screens copied it. The value was not missing. A single place for it was missing. The `scale()` values stay separate. They range from 0.9 to 0.995 and show per-control emphasis. The Fulfiller's value is the largest, because that screen is a touch screen. No value in `docs/DESIGN.md`'s Fulfillment table changes. `.pull-confirm` keeps its position. `transform` on `:active` already replaced the hover lift, so its net position is unchanged.

**The press is not transitioned.** This is the one place the press floor and the response floor differ. A press must show on the frame the button goes down. A transition on `translate` would add 120ms between finger and feedback. A 1px press that the user starts is not motion in the sense `prefers-reduced-motion` covers. That block leaves it alone, as it always left the kit's press rules.

**A disabled control does not move.** A control that refuses the click must not move under the pointer. The cursor floor's disabled arm makes the same claim with `not-allowed`. That class held 30 of the original 41 defects. A press floor that moved disabled controls would repeat the defect. Mutation tests confirm it both ways. Deleting the floor fails 7 of 12 shapes. Deleting the disabled arm fails 4.

**A screen that needs no dip writes `translate: none`.** That is one property and one comment. `.fulfillment-row`, `.ff-row` and `.runs-box` each took it. Each had opted out with `transform: none`. That stopped working once the dip moved to another property. **An opt-out written for one property is lost when the mechanism moves to another.** Any floor of this kind carries that risk.

**The inert controls went to the owner as images, and the owner ruled on them.** The paragraph that followed was restored by PR #192 the same day it was written. D133 holds the account. 22 controls gave no hover response. That was two separate faults. Rendering both at 3x, beside their unhovered states, separated them.

**The current page's nav link, 9 of the 22, now responds.** The rule was not missing. `.bn-nav-link:hover` is (0,2,0), and `.bn-nav-link[aria-current='page']` is (0,2,0). The tie went to source order, so selection beat hover. **A rule that loses a tie looks correct in the stylesheet.** The fix adds D110's alpha over the selection tint. That is one step, in the color the row already has.

**The selected tab stays inert, by decision. The owner chose that from the images.** `:hover` sets `--bn-ink`, and a selected tab is already `--bn-ink`. Nothing is left to change. A fix needs a new property, and the only option is a background. These tabs have no ground. A plate under the pointer would change their character more than it helps. The ruling sits beside the rule in `kit.css`.

**The first fix snapped. That result matters for later work.** The obvious way to put an alpha over a background is a flat one-color `linear-gradient` as a second background layer. The first fix did that. It passed review and the guard. **`background-image` cannot animate.** A change from `none` to a gradient is discrete, so it repainted in one frame. That reintroduced the defect the response floor removes. Sampling during the transition found it. Reading the code did not.

**The guard had a hole of the same shape. The hole is closed.** `eased()` maps the `background` shorthand to `background-color`. It found that property eased and passed, but the property that changed was `background-image`. **A guard that cannot see the changed property has the same hole as a roster that lost a route.** A `:hover` rule that paints a gradient, `url()` or `image-set` is now named as a failure. The working fix is an inset `box-shadow` with a spread larger than the row. It has the same alpha and ground, and it animates.

**A component's own `transition` replaces the floor's.** It does not add to it. The shadow still snapped until `box-shadow` was named in `.bn-nav-link`'s own list. This holds for every screen that sets a transition. The floor is a default, not a guarantee.

**Measured after the fix: 15 controls inert, down from 22. 310 of 325 respond.** Left inert: the selected tab and segment, which the owner ruled on. Four `.search-field-input`s, whose wrapper carries the response. Single rows. No one has argued that any of these is wrong.

**This entry is reopened by a screen that needs a different response.** The floor yields to a class, by design. A real exception needs one rule and one comment that says why. A screen that sets no response at all is the failure the guard exists to stop. A spec that skips routes has removed this entry's protection without any argument.
