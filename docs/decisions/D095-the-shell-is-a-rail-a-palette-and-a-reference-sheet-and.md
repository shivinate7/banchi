## D95 — The shell is a rail, a palette and a reference sheet, and the Fulfiller's crash has no door out

**The owner's nav became a collapsible sidebar with a command palette over it, the phone got a tab bar and a drawer, and the Fulfiller got a crash page that offers no way out of his view.** Built 2026-09-03 with D94. `App.tsx`'s `ROUTES` table is still the one roster and every route is still registered in it; what changed is how a person reaches one.

**The table holds eleven routes and `#/` changed meaning.** `#/` is a new Home screen, Capture moved to `#/capture`, and `#/gallery` is labelled "Kit". Main's table held ten with Capture at the root. Routes carry a `group` — `home`, `work`, `sell`, `library` — and the nav draws them in that order under those headings, which is the workflow (capture, runs, review, pricing, then orders and shipping, then inventory and codes) made visible instead of a flat list a newcomer has to infer an order from. `OFF_NAV` names the one group the nav deliberately omits, `aside`, holding the Fulfiller's screen and the kit; it is a constant because `scripts/docs-audit.py`'s `route rosters` row reads it, and without it that row can only conclude two routes have gone unreachable.

**Recounting is owed, and this entry is not the place it lands.** Moving Capture off the root and adding Home changes every published route count and every spec that pins `#/` as the capture screen. `CLAUDE.md`, `README.md` and `docs/map.py` carry the counts the `route census` row reconciles, and `app/tests/nav.spec.ts` and `app/tests/cursor.spec.ts` carry the pinned rosters; all of them are owed a recount from the table, never an increment, which is the instruction that entry already gives.

### Three shells for three widths, and one of them is nothing at all

**A 236px sidebar at 1024px and up, collapsing to a 64px icon rail on `⌘.`**, remembered per device in `localStorage` under `banchi.rail` (D27). **A 52px top bar and a 64px bottom tab bar below 768px**, the tabs being the four routes that carry `tab: true` — Capture, Review, Orders, Inventory — with everything else behind a left drawer. **And nothing on the Fulfiller's route**, which is unchanged: `CHROME_FREE` holds his persona and the shell renders no nav at all for it, not-rendered rather than hidden, as it was before.

### The palette and the sheet replace hunting for a binding

**`⌘K` opens a command palette** over every route, every screen's own verbs as search keywords, the theme and rail toggles, the hand-off that opens the Fulfiller's screen in a new tab, and the kit. It is additive: the `,` leader chord is unchanged and every screen keeps the letter it had, with `h` added for Home, and `⌘←`/`⌘→` still step the nav strip in the order it is drawn, which is D51 and is untouched.

**`?` opens one keyboard reference sheet listing every binding in the product**, in eleven sections — anywhere, jumping, the palette, and one for each screen that has keys of its own. The owner chose this over restoring the inline `⌘←`/`⌘→` key hints the rebuild had dropped, in those terms: a single place that is complete beats a hint on one screen that is not. The inline hints stay deleted. The failure this closes is the one the old hint had — a binding drawn beside the two controls it happened to sit near, and eight screens' worth of keys documented nowhere a person could look.

### The Fulfiller's crash page, and why it is a separate page

**A screen that throws is caught by an error boundary, and the boundary draws two different pages.** The owner's is the ordinary one: the logo, the error's own message, a reload and a link home. The Fulfiller's carries his floors — 20px body, 44px targets — a sentence saying nothing is lost, and exactly one control, which reopens the screen he is on.

**It offers no route out, because `docs/DESIGN.md`'s constraints table forbids one and a crash is not an exemption from it.** That table's `Destructive actions` row reads *zero reachable from this view*, and the view is his whole product. A crash is the moment he is most likely to press whatever is offered, so it is the moment the rule matters most rather than least. Before this the shared boundary wrapped his screen too and drew a "Go home" link into the owner's side at 14px — a door into the pipeline, below his type floor, reachable only by the screen breaking. This is D5's two-personas rule and D31's *the Fulfiller does not get a vote* applied to the error path, which is the path neither of them had thought about.

### What is not built

**The crash pages are asserted by nothing.** `make design-check` walks the Fulfillment view's floors on a screen that renders, and no test throws inside it to see what the boundary draws. A spec that mounts a deliberately-throwing child on `#/fulfillment` and asserts the absence of any link is the reader this needs, and it is named here rather than claimed.

---
