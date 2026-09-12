## D120 — The shell speaks one brand at every width, and the phone bar is a rail

**Built 2026-09-07, on the owner's instruction, after they asked what the mobile build gets wrong.**
The 2026-09 rebuild put the lockup in the desktop sidebar
(D102, `docs/specs/logo.md` §16) and left the phone chrome exactly as it was before the lockup
existed. Nothing was decided about the phone; it simply was not asked about.

**SO THE PRODUCT WORE TWO BRANDS, AND WHICH ONE YOU SAW DEPENDED ON HOW WIDE THE WINDOW WAS.**
Above 1023px: 番地 over BANCHI, in the mark's own brackets. Below 768px: a `Logo` tile beside a
Manrope wordmark in the top bar, and the same tile beside a wordmark AND the tagline in the More
drawer — three brand objects in one shell. On dark the bar's tile is a dark superellipse on
`--bn-surface-glass` over a near-black page and very nearly disappears, which is the failure §16
gave the sidebar's bracket a chrome gradient to avoid, at a size where it is worse.

**THE LOCKUP CANNOT GO IN THE TOP BAR, AND THE ARITHMETIC WAS ALREADY WRITTEN DOWN.** Its floor
is kanji 32 (§11), which is a 102 × 75 block; `--bn-topbar-h` is 52px. That is the same refusal
the 64px rail takes and the same measurement behind it — 番's counters close at about kanji 30,
before the roman gives out and long before the bracket does. A bar tall enough for it is 84px,
which is 10% of an 844px viewport spent on a brand row on every screen; considered, refused.

**SO THE BAR DRAWS WHAT THE RAIL DRAWS, AND THAT IS NOT A NEW RULING.** §18 settled the same
question for the browser tab on the owner's own instruction — *"the tab should be what the
collapsed sidebar is"* — citing §1: *"with the card removed the same brackets become an empty
slot, which is the in-product mark."* The phone bar is the rail's case one breakpoint down, so it
takes the rail's drawing and the rail's paint. Unlike the tab's flat gold, it is an in-app surface
and keeps `--bn-lockup-metal`, which `kit.css` resolves per theme.

**AND THE DRAWER IS THE SIDEBAR AT A PHONE'S WIDTH** — same nav, same groups, same foot, one tap
away instead of always on — so it draws the sidebar's brand at the sidebar's number. Kanji 40 was
taken over 32 by forced choice, drawn in the real drawer at 390 and 320 in both themes: both fit,
both leave the nav clear of a scroll, and 40 is the sidebar's own value, so there is one number rather
than two to keep in step.

**ONE DRAWING, THREE SURFACES, NO BRANCH.** `BrandSlot` in `app/src/App.tsx` is rendered by all
three; `--bn-brand-open` is inherited and `App.css` sets it to 0 on `.bn-topbar-brand`; the morph
reads the slot's own width, so the bar gets the rail end from one declaration. `Lockup` did not
change for any of this, which is what D102's generated geometry bought.

**`every card has an address` LEFT THE PRODUCT, AS THE RULING AND NOT A SIDE EFFECT.**
§16's rule is that the lockup replaces the mark, the wordmark and the tagline together;
the drawer was the tagline's last home, since the sidebar dropped it when the lockup landed and
`#/gallery` uses it only as a type specimen. The owner ruled to let it go. Home's lede still ends
*"Every one has an address."*, which is the sentence a person actually reads and is bound to the
count in front of it. `.bn-brand-text`, `.bn-brand-name` and `.bn-brand-tag` are deleted.

**THE DRAWER'S SERVER LINE GAINED THE CARD COUNT** the sidebar has always drawn. It said only
`Server online` here, so a phone could not see how big the store it was answering for was.

**WHY NOTHING CAUGHT ANY OF THIS.** `app/tests/nav.spec.ts` scopes itself to `.bn-side` on
purpose; `app/tests/cursor.spec.ts` harvests its routes from `.bn-side a.bn-nav-link`, which is
`display: none` below 768, so that file cannot run at a phone width even in principle; and of
twenty specs only `app/tests/fulfillment.spec.ts` sets a phone viewport at all. The shell had no
test at any width. `app/tests/brand.spec.ts` covers the phone bar and the drawer now, and carries
the size floor §15 asked for and nothing built — `Lockup` refuses below `LOCKUP_FLOOR = 32`.

**WHAT IS NOT DECIDED HERE.** The owner-side thumb floor across the screens is a separate pass
and a separate PR: `.bn-check` renders a ~20px target at 390 from the kit, and about two dozen
screen-level controls hard-code a height instead of reading `--bn-control-h*`. This entry is the
brand only.

**What would reopen this:** a top bar tall enough for a kanji-32 lockup, or a compact horizontal
cut of the lockup that fits 52px — which would be new §13 work, not a size change.