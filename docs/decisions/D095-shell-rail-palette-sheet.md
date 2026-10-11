## D95 — The shell is rail, palette, reference sheet

**The owner's nav became a collapsible sidebar with a command palette over it.** The phone gets a tab bar and a drawer. The Fulfiller gets a crash page that offers no way out of his view. Built with D94. `App.tsx`'s `ROUTES` table is still the one roster, and every route is still registered in it. What changed is how a person reaches one.

**The table holds eleven routes, and `#/` changed meaning.** `#/` is a new Home screen. Capture moved to `#/capture`, and `#/gallery` is labelled "Kit". Main's table held ten with Capture at the root. Routes carry a `group`: `home`, `work`, `sell` or `library`. The nav draws them in that order under those headings. The order is the workflow: capture, runs, review, pricing, then orders and shipping, then inventory and codes. `OFF_NAV` names the one group the nav omits, `aside`. It holds the Fulfiller's screen and the kit. It is a constant because `scripts/docs-audit.py`'s `route rosters` row reads it. Without it, that row can only conclude that two routes are unreachable.

**Recounting is owed, and this entry is not where it lands.** Moving Capture off the root and adding Home changes every published route count. It also changes every spec that pins `#/` as the capture screen. `CLAUDE.md`, `README.md` and `docs/map.py` carry the counts the `route census` row reconciles. `app/tests/nav.spec.ts` and `app/tests/cursor.spec.ts` carry the pinned rosters. All of them are owed a recount from the table, never an increment.

### Three shells for three widths, and one of them is nothing at all

**A 236px sidebar at 1024px and up.** It collapses to a 64px icon rail on `⌘.`. The rail state is remembered per device in `localStorage` under `banchi.rail` (D27). **Below 768px, a 52px top bar and a 64px bottom tab bar.** The tabs are the four routes with `tab: true`: Capture, Review, Orders and Inventory. Everything else sits behind a left drawer. **The Fulfiller's route has no nav.** `CHROME_FREE` holds his persona, and the shell renders no nav for it. It is not rendered rather than hidden, as before.

### The palette and the sheet replace hunting for a binding

**`⌘K` opens a command palette.** It covers every route and every screen's own verbs as search keywords. It also covers the theme and rail toggles, the hand-off that opens the Fulfiller's screen in a new tab, and the kit. It is additive. The `,` leader chord is unchanged, and every screen keeps its letter. `h` is added for Home. `⌘←` and `⌘→` still step the nav strip in the order it is drawn (D51, untouched).

**`?` opens one keyboard reference sheet.** It lists every binding in the product, in eleven sections. The sections are anywhere, jumping, the palette, and one for each screen with keys of its own. The owner ruled the sheet over restoring the inline `⌘←` and `⌘→` hints the rebuild had dropped. A single complete place beats a hint on one screen that is not complete. The inline hints stay deleted. The sheet closes the failure the old hint had. A binding was drawn beside the two controls it sat near, and eight screens' keys were documented nowhere a person could look.

### The Fulfiller's crash page, and why it is a separate page

**An error boundary catches a screen that throws, and it draws two different pages.** The owner's page is the ordinary one: the logo, the error's own message, a reload and a link home. The Fulfiller's page keeps his floors: 20px body and 44px targets. It has a sentence saying nothing is lost, and exactly one control, which reopens the screen he is on.

**It offers no route out.** `docs/DESIGN.md`'s constraints table forbids one, and a crash is not an exemption. That table's `Destructive actions` row reads *zero reachable from this view*. The view is his whole product. A crash is when he is most likely to press whatever is offered, so the rule matters most there. The shared boundary used to wrap his screen too. It drew a "Go home" link into the owner's side at 14px. That was a door into the pipeline, below his type floor, reachable only when the screen broke. This applies D5's two-personas rule and D31's *the Fulfiller does not get a vote* to the error path.

### What is not built

**No test asserts the crash pages.** `make design-check` walks the Fulfillment view's floors on a screen that renders. No test throws inside it to see what the boundary draws. A spec that mounts a deliberately throwing child on `#/fulfillment` and asserts no link is present would close the gap. It is named here, not claimed.
