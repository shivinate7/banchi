# Pocket Verdict: design notes

At a card show the owner holds one card to the phone and gets Buy under $X, Pass or Too many, worked out offline from their own store's sell speed and fees.
Each buy they log goes on a "bought today" list, and back home that list becomes the next capture batch, already priced.

**Tap through.** Open `pocket-verdict.html` from disk. Use the state picker above the phones, or tap inside a phone: Going Out, then Start Scanning, then a card in the Sample tray, then Log Buy, then Done, and Today. Each state has a deep link, `#state=<name>`, for these states: going-out, syncing, ready, scan, buy, pass, toomany, notrecognised, typein, snapped, logbuy, slab, slab-thin, lot-ask, lot, lot-end, bought-today and synced. Add `&t=dark` or `&t=light` to force a theme. Leave it off and the page follows the system. `&v=card` and `&tm=hide` show the other options. Each option has a Hide control (`&h=v:card`).

**Sizes.** Neither Duo pose has a size in `layout.json`, and no Apple page gives one. The mockup draws both poses at stand-in sizes, 390x844 folded and 740x844 unfolded, from one CSS block. The unfolded pose has its own layout: the scan pane sits beside Today, a list sits beside its detail, and the setup sits beside the snapshot list. The page fits at 1440 and at 820 with no horizontal scroll.

**Nearest specs**
- `capture-app` §9 (what the app may not build). Departs from: the app does no pricing and keeps no second store. The phone keeps an offline copy of the store and gives a price. Owner grant: yes.
- `capture-app` §2.1 (no CSV import; every state change belongs to a command). Departs from: a capture batch is started on the Mac only. A list from the phone becomes the batch. Owner grant: yes.
- `my-slabs` §4.3 (a slab's value from an online read per cert, with trust rules). Departs from: the online read per cert. The phone reads the grade label and uses graded sales from the snapshot. Fewer than about 3 sales gives a range and no price.
- `stale-listings` §3 (the three tests for "not selling"). Departs from: that report is made after the fact. Here the expected wait is a forecast made before buying.

**Design choices**
1. **The verdict fills the screen below the camera, in one colour per verdict:** green for Buy, amber for Too many, grey for Pass, and an outline with no fill when no price is given. Gain: the owner can read it at arm's length. Loss: the camera view shrinks to about a third of the screen. Pick: Full field. The other option is Card over camera (`#verdict`).
2. **The Buy figure is 80 pt.** No Dynamic Type style is this large (Large Title is 34). In code it scales with `@ScaledMetric`. Gain: it is the number they haggle against. Loss: it is not a system style.
3. **Pass shows no figure, and an outlined verdict never does.** The figure on a Pass would be the price after fees, and it could read as an offer. Not recognised and Thin data show no price, by the hard rule against guessing a price. Gain: no false offer. Loss: they cannot see how far below the floor a card falls.
4. **Too many, the price for one more copy.** Price dropped shows it at Title 1 size, smaller than a Buy figure. Price hidden shows none (`#toomany-price`). Gain of dropped: it still answers "at $0.50?". Loss: it can still read as a buy. Pick: Price dropped.
5. **Log Buy opens a sheet with a number pad.** The sheet shows Cancel on the leading edge and Done on the trailing edge, as the HIG Sheets page says. It shows the paid price, the margin left and the budget left after. Swipe up opens it too. Gain: the budget is checked before the buy. Loss: one extra tap per buy.
6. **Three tabs: Scan, Today and Going Out.** The main actions sit in the thumb zone, above the floating tab bar. The budget left is a pill on the camera that opens Today.
7. **Haptics.** Buy gives one firm tap. Pass gives a soft double tap. Too many also gives the soft double tap: the plan names no haptic for it, so this is my choice.
8. **Every write has a way back.** Copying has Stop. Each row on Today has Remove from Today. Sent home has Undo Send.
9. **The Sample tray is for the mockup only.** It picks which card the camera reads. A phone never shows it.

**Owner questions (from the plan)**
1. What margin and what longest wait make a buy worth it? The mockup uses 25% and 90 days as samples.
2. May the phone reach the home Mac from a show, or must it work fully offline? The mockup draws fully offline.
3. In a lot, does an unrecognised card count as $0, or at a flat bulk rate they choose? The mockup draws $0.

**Apple pages read 2026-11-21, each answered 200:** HIG Layout (it no longer lists device sizes), Typography (the default Dynamic Type table), Accessibility and Buttons (44x44 pt), Sheets, Tab bars and Toolbars.

**Screens.** `pocket-verdict-light.png`: native, and the Buy field and the actions read clearly. `pocket-verdict-dark.png`: native. The green field holds contrast, but the bezel almost vanishes against the dark page.
