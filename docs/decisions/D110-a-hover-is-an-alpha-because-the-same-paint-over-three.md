## D110 — A hover is an alpha, because the same paint over three grounds is three different hovers

**Built 2026-09-06, on the owner's question about the dark sidebar** — *"is that lighter grayish
one favorable to you?"* The answer is no, and the interesting part is that the lighter one is not
the element the question looked like it was about.

**Dark had two hover values on ONE ground, and nothing recorded why.** `.bn-nav-link:hover`
carried a dark-only override to `--bn-surface`; the brand row directly above it and the footer
buttons directly below it took `--bn-surface-3`, the value every other hover in the product used.
Three controls in one column, one ground, two paints.

**Measured in CIE L\*, which is the currency here.** A hex delta says nothing about a step the
eye can see, and at these luminances it says less than nothing. A sweep of every hover target on
every screen found exactly three grounds under them: the sidebar `--bn-surface-2` #090b0e, a
panel `--bn-surface` #14171c, and the page `--bn-bg` #0c0e12 (which carries one target,
`.kit-index-link` on `#/gallery`). Painting `--bn-surface-3` #1b1f26 over those three is:

```
ground                        today            white 4%
sidebar  --bn-surface-2      ΔL*  8.67         ΔL* 3.61
page     --bn-bg             ΔL*  7.70         ΔL* 4.22
panel    --bn-surface        ΔL*  4.00         ΔL* 4.51
                             spread 4.67       spread 0.90
```

**So the token was never the problem and the sidebar was never a taste question.** ΔL* 4.00 on a
panel — the table rows and list rows the operator sweeps a pointer across all day — is a good
hover, and nobody has complained about it. The same name on the sidebar is 8.67, more than
double, and it reads as SELECTION rather than hover: in the rendered before/after it competes
with the accent tint two rows below it, which is the one thing in that column that is supposed
to be the brightest. **The lighter grey is right where it is and wrong where it was looked at**,
and one value cannot be both.

**The nav-link override was therefore correct, and incomplete.** At ΔL* 4.66 it is within half a
point of the panel step — somebody tuned it for the darker ground and shipped it. What they could
not do was generalise it, because an opaque hover has to know what it is sitting on, and a
stylesheet rule does not.

**An alpha does not have to know.** `--bn-hover` is `white 4%` in dark and `ink 3%` in light; it
composites against whatever is beneath it, so one name is one perceived step on every ground and
the per-element compensation disappears. This is not a new idea in this system — the three
`--bn-line` tokens are already ink at an alpha, and `docs/DESIGN.md` already says of them *"they
ride the ground."* Hover is the same argument, applied to the surface instead of the hairline.
**D50 settled the principle** — an interactive element's feedback is the product's, not each
stylesheet's — and this is the value that principle was missing.

**THE FAMILIES ARE TWO, AND THE SPLIT IS A FACT ABOUT THE ELEMENT RATHER THAN ITS STYLESHEET.**
An alpha REPLACES a resting background rather than layering on it, so it is correct only where
the element rests transparent. That is the honest boundary, and it was checked element by element
against the live DOM rather than assumed:

- **A surface lit under the pointer** — rests transparent, reads `--bn-hover`. 31 rules: the nav,
  the brand, the footer buttons, `.bn-table tbody tr`, `.bn-list-row`, `.bn-menu-item`,
  `.pricing-row`, and the screen-level rows.
- **An object that paints its own ground** — a button, a chip, a raised card — lifts from its OWN
  colour and keeps `--bn-surface-3` or `--bn-btn-bg-hover`. 12 rules, and every one of them
  independently carries a `transform: translateY(-1px)` or a shadow, which is the same claim
  made a second way: these are raised things, not lit surfaces.

The two families agree perceptually without being forced to — family B's step from `--bn-surface`
to `--bn-surface-3` is ΔL* 4.00, which is where family A now sits. The button's own step is 5.76
and is deliberately left stronger.

**What it cost light: nothing measurable, and it fixed one thing.** On `#ffffff` — where every
light hover except one lands — `ink 3%` resolves to #f8f8f8 against today's #f7f8fa, ΔL* −2.42
against −2.44, and `--bn-ink-3` on the hovered row reads 4.55:1 in both. On the page ground
today's value went the WRONG WAY: `--bn-surface-3` is LIGHTER than `--bn-bg`, so that hover was
ΔL* +1.02 and effectively invisible. It is a real −2.44 now.

**Contrast was checked on every hovered surface rather than argued from the direction of travel.**
Dark improves on the sidebar and the page (the new value is darker than the one it replaces) and
moves by −0.06 for `--bn-ink-3` on a panel, 4.81:1 → 4.75:1. No text in the product sits on a
page-ground hover except `.kit-index-link`, which is `--bn-ink` at 16:1.

**Three dark-only overrides are deleted, not replaced.** `.bn-nav-link` is the one this started
from. The other two are `.capture-row` and `.capture-opt`, which in dark hovered DOWN to
`--bn-surface-2` — a sink to below the page ground, drawn as dark holes punched in a panel, and
looked at in the browser before it was called wrong.

**What is NOT settled**: `--bn-btn-bg-hover` stays a hand-picked #262b34 in dark. A button rests
on its own paint, so the same alpha trick does not reach it, and giving family B a
lift-from-my-own-ground token is a second change with its own measurement to do. It is named here
so the next session does not read this entry as covering it.
