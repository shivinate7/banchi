# The Vault Tripwire: notes on the mockup

After each price read, a card whose price crosses the value line, or jumps with sales behind it, is held off TCGplayer at once.
The owner sees only the few cards that crossed. Uploads leave held cards out. A vault card's pick line is gold for the Fulfiller.

**Click through.** Open `vault-tripwire.html` from disk. The State bar holds every state of plan section 2; each is a deep link
`#state=<name>`: `mixed`, `normal`, `crossed-up`, `confirmed` (press Moved), `crossed-down` (press Returned), `reversed`, `too-late`,
`upload-refused`, `upload-hard`, `budget`, `line` (live backtest: move the slider), `pick`. Add `&t=dark` or `&t=light`,
`&hide=<option>` to cull one, `&notes=off` to hide the Today:/New: tags. Plan: `p-slabs-further.md`, round one `p-slabs.md`.

**Where it lives.** Reached from Pricing, a lens like the markdown lens (D103). Nearest spec: `docs/specs/pricing-suggest.md` (Needs you, the $25 value line, 9a option 3). The pick line extends `#/fulfillment`.
- Departs from: pricing-suggest section 9a, which picked "cut drift as a tool" — this adds a watch that holds a live listing.
- Departs from: pricing-suggest's value line, which only parks a card in Needs you — the line now holds the listing, and gains an exit line.
- Departs from: Fulfillment's box-walk order — a gold line sorts first (Gold Ticket, round one).
- Departs from: the plan's word "pull" — the repo says price read, and "pull" is the Fulfiller's word for taking a card.

**Design choices** (option key in brackets; one press in the cull strip hides it)
1. A lens on Pricing, not a new screen. Gain: one home with the value line and the send. Lose: Pricing grows a lens. Pick: lens.
2. Price ruler per row [`ruler`]: line, exit gap, old price (ring), new (dot). Gain: why, at a glance. Lose: 224px. Pick: keep.
3. Hold happens at once; Hold / Reprice in Bulk / Dismiss, Hold pressed. Gain: nothing sells stale. Lose: a held card earns nothing.
4. The move is a step inside the row: Moved, then the vault price field. Gain: no second screen. Lose: a long row. Pick: keep.
5. A checked silence, with the highest bulk card on the ruler. Gain: silence reads as checked. Lose: a panel on an idle day.
6. Too many rows draws "the line looks too low", not a longer list. Gain: the budget of 5 shows. Lose: one more notice.
7. Line panel as a side sheet with a live backtest [`backtest`]. Gain: the owner sees the cost of a line before setting it.
   Lose: sample data until real reads exist. **Owner grant: yes** — it reuses Pricing's $25 value line as the entry and adds an exit.
8. The measure line [`measure`]: stale-price sales, dollars lost, dismiss rate. Gain: the target, zero, is on screen. Lose: a line.
9. Too-late row with Cancel the Sale / Honour the Sale [`late`]. **Owner grant: yes** (question 2). Pick: Honour pressed as default.
10. Gold pick line [`packing` hides the packing list]: gold edge and tint, every word in ink so the 7:1 floor holds; a star flag
   for colour-blind eyes; "Vault, Slot V-14" at 40px (34px at 820); four packing items at 20px. No gold token exists; it paints
   `--bn-warn`. A `--bn-gold` token would be a token-file change, outside the design folder.

**Owner questions carried from the plan**
1. What loss on one card hurts enough to act on? That sets the line ($X) and the jump floor ($Z).
2. When a card already sold at the stale price, cancel or honour the sale? Cancelling may hurt seller standing.
3. Where does the vault live (binder, slab box, a drawer), and will you move cards by hand, a few a week?

**Verdicts** (headless Chromium, `#state=mixed`; `pick` and `line` also checked at 820 dark)
- 1440 light: pass. Rows, ruler, steps and tiles align; nothing clips. Screenshot `vault-tripwire-1440-light.png`.
- 820 dark: pass. Rail shell, rows fold to five lines, line sheet covers the page, gold card keeps the slot in the first screen. `vault-tripwire-820-dark.png`.
All data is made up. Fonts fall back to system faces: the file loads nothing from the network.
