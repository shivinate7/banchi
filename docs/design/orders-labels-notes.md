# Orders, the label word: design notes

Lane kind: informed. Mockup: `orders-labels.html`. Spec: `docs/specs/order-pipeline.md`, section
"T4" ("`#/orders` may show a status word only", D69, the order screen and its lanes) and "T5". The Shipping half, where labels are
made and scans are checked, is `shipping-labels.html`. The frame draws my pick. The Options panel
under it draws each alternative, and each has a control that hides it.

Deep links: `#s=none`, `#s=made`, `#s=moving`, `#s=delivered`, `#s=held`, `#s=several`,
`#s=parcel`, `#s=manage`, `#s=order`. Add `&w=820` and `&t=dark` (or `abyssal-bloom`,
`carnival-midway`). With no `t`, the page follows `prefers-color-scheme`. `&h=O1,O2` hides options.
The element that carries the choice has the id `label-word`. Images:
`orders-labels/<state>-<width>-<theme>.png`.

Components: `Orders.OrderPanel` (the buyer's panel at the top of the walk), `Orders.ManagePanel`
(the Manage sheet's order lines) and `Orders.OrderDetail` (one order, opened in Manage). The CSS
is the repo's own sheets, inlined at the time of drawing, with `Orders.css`. The headline, the
filter bar, the walk and the card pane are plain stand-ins: this design does not change them.

1. **One word per order, from the store's label row, joined on the order number.** The screen
   reads `GET /shipping/labels` with the orders, the way `OrdersHub` joins the shipping lanes
   (`lanesByOrder`). Gain: the word is in the first paint, so it never grows the facts row after
   it lands (D313, nothing moves unless the person moved it). Loss: one more read when Orders loads. Pick: yes.
2. **The words are Shipping's, in this screen's casing.** "Label made", "On its way",
   "Delivered", "Held up". Shipping's "Not Checked" and "No Scan Yet" both read "Label made"
   here, and "Unclear" reads "Label made" too: the detail lives on Shipping. Orders' pills are in
   sentence case (`STATUS_PILL`: "Partly picked"), so the words are too. The mapping from the
   label service's status has one home, shared with Shipping.
3. **No word for an order with no label row** (`#s=none`), **and none for a parcel or undecided
   order** (`#s=parcel`). Pirate Ship labels are not read back.
4. **The buyer panel: the word sits after the status pill** (`OrderPanel`'s
   `.orders-panel-facts`, `#s=made` to `#s=held`). The status pill and the word are wrapped
   together, so the figures keep their line. Tones: "On its way" accent, "Delivered" ok, "Held
   up" warn with the alert icon, "Label made" plain.
5. **A buyer with several orders: a count, not a word** (`#s=several`). "2 of 3 labeled". If any
   order is held up, the panel says "1 held up" in warn instead, because that is the one to act
   on. When every order has a label and none is held up, the panel shows the word of the order
   furthest behind.
6. **Manage, the order lines** (`ManagePanel`, `#s=manage`): each line's detail gains its word
   after the status: "Done, on its way". An order with no label keeps today's detail.
7. **Manage, one order** (`OrderDetail`'s `.orders-order-side`, `#s=order`): lane, status, then the
   word.
8. **Option O1: the word on each buyer row.** Seen without opening a buyer. `BuyerRow`'s own
   comment records the owner's ruling: no status chip on a row. Pick: no.
9. **Option O2: a Show choice per label word.** Finds every held-up order at once. Four more
   choices in a facet that holds eight, and Shipping's Labels list already sorts these. Pick: no.
10. **Option O3: the word replaces the lane pill once a label exists.** One pill fewer. Loses the
    lane word that the order's head shows today. Pick: no.
11. **Option O4: the word in the walk's done line.** It shows only when every card is sold. Pick:
    no.
12. **Nothing here acts.** The owner still marks orders shipped on TCGplayer (D326 item 108), and
    Reprint and Check Scans stay on Shipping. The word is the only label fact on Orders.

Needs wire field: none. The word reads the listing's order, its `status` and its stored scan
answer. A `pending` row draws no word: only a `made` label is a label.
