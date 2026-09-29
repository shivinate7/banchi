## D309 — An empty state fills the frame to one cap, centered

**Ruling (owner).** The empty and lone states of the plain screens (Orders, Review, Shipping) fill
the page frame up to one shared cap, centered. Home keeps its own layout by owner exemption.

**Home.** `--bn-empty-w` is 960px, in `app/src/tokens.css`. `.bn-empty-frame` in `app/src/kit.css` reads it.
A screen adds the class to its empty or lone block and keeps no `max-width` of its own.
Body copy inside keeps its `ch` measure.

**Why.** `.shipping-empty` capped at 880px left a band 260px wide at 1440 and 720px wide at 2000.
Three screens each carried their own cap (880, 720, 720), so no two agreed.

**Check.** `app/tests/shipping-width.spec.ts` measures the block against the frame at 1440, 820 and 2000.
