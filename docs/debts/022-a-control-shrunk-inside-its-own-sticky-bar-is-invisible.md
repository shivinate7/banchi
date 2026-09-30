## 22 — A control shrunk inside its own sticky bar is invisible to the thumb-floor sweep

`app/tests/phone.spec.ts` decides a probe landed on the control with `owns = t.contains(n) || n.contains(t) || chrome(n)`. The `n.contains(t)` clause (the probe landed on the control's own ancestor) lets a 22px tick answer at 46px through a padded wrapper, and it is load-bearing for the hit-area method (D117). So shrinking `.browse-boxchip` to 20px lands its corner probes on `.browse-mobilebar`, the sticky bar that contains it, and the suite stays green.

The centre hit-test no longer forgives `chrome(n)` (`centreOwns`), so a control genuinely behind fixed chrome now fails. Only the ancestor clause is open. The `mode === 'box'` sweep on `#/gallery` asserts the box outright and catches a shrunken kit component.

**Outcome at risk.** A screen-level control shrunk below the 40px thumb floor inside its own sticky ancestor bar ships.

**Closes when.** The clause narrows (say, to ancestors that are not scroll-independent furniture), measured across every owner route.
