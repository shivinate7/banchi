# Shipping, envelope labels: design notes

Lane kind: informed. Mockup: `shipping-labels.html`. Spec: `docs/specs/order-pipeline.md`,
sections "The TCGTracking pipe (D326)", "T4" and "T5". Decision D326 (the server calls
TCGTracking). The frame draws my pick. The Options panel under it draws each alternative, and
each has a control that hides it. The Orders half is `orders-labels.html`.

Deep links: `#s=rest`, `#s=reading`, `#s=preview`, `#s=again`, `#s=nokey`, `#s=progress`,
`#s=stopping`, `#s=stopped`, `#s=receipt`, `#s=partial`, `#s=labels`, `#s=checking`, `#s=reprint`, `#s=nofile`. Add `&w=820`
and `&t=dark` (or `abyssal-bloom`, `carnival-midway`). With no `t`, the page follows
`prefers-color-scheme`. `&h=P1,H1` hides options. Images: `shipping-labels/<state>-<width>-<theme>.png`.

Component: `OrdersShipStage.ShipStage`, the Ship stage of the Orders hub at `#/shipping`. The CSS
is the repo's own sheets, inlined at the time of drawing, with `Shipping.css`. The proposed rules
are at the end, under "PROPOSED". A dashed gray outline marks what exists today; a dashed accent
outline marks what this design adds.

## The step

1. **The Envelope labels card sits in the file row, between the export and the Pirate Ship
   import** (`ShipStage`'s `.shipping-files`). Lane order: envelope before parcel. Gain: the step
   is where the other file steps are. Loss: three cards in the row at 1440; at 820 the row stacks
   to one column, as it does today. Pick: yes.
2. **Make Labels is a default button; Download stays the primary one** (option C1 swaps them).
   Make Labels only opens a free preview, and Download is today's primary act. Pick: no swap.
3. **The preview is a sheet, 560 px wide** (option P1 draws it inline). A sheet keeps the lanes
   still; an inline panel pushes them down by fifteen rows. The kit sheet is 420 px; a row needs
   the order, cards, value, the switch and the row's answer. Pick: sheet.

## The money gate

4. **The preview is free, and the confirm is absent until it answers** (spec T4). While it reads,
   the foot holds an empty slot the size of the confirm (`bn-slot`), so the foot does not grow.
5. **The summary shows the count to label, the count held back, the envelope and "Fee per your
   TCGTracking account."** (owner ruling, D326 item 109). Every state's summary sits in one grid
   cell, so the list under it never moves (D313, nothing moves unless the person moved it).
6. **Insurance is a switch on each row, off by default** (D326 item 110). The confirm sends the
   orders whose switch is on as `insured`. After the confirm the switches are off, with the
   choice still shown.
7. **Pick (b): held back is one line per reason, with the orders it covers under it** (option H1
   is one row per order). Gain: three parcel orders read as one sentence, not the same sentence
   three times. Loss: a single order's reason is one step from its number. The sentences, keyed
   by the preview row's `reason` code:
   - `parcel`: "3 orders go in a parcel, so they ship with the Pirate Ship file."
   - `needs_a_look`: "1 order needs a look first. Banchi cannot tell envelope from parcel."
   - `no_full_street`: "1 order has no full street address in the export. Fix it on
     TCGplayer, then read the export again."
   - `already_labelled`: "6 orders have a label already, so they are not bought twice." (`#s=again`)

   An unknown code shows "This order cannot get a label here." with the code behind "What the
   server said".
8. **No key or no shipper number: the preview says why, and the confirm is absent**
   (`#s=nokey`). The preview carries `key_present` and `shipper_present`; when either is false,
   the summary says so and the foot offers Read Again, the free preview again:
   - no key: "Banchi has no TCGTracking key on this Mac, so it cannot buy labels. Add the key to
     Banchi's settings file, then press Read Again. Nothing is bought."
   - no shipper number: "Banchi has no shipper number for your TCGTracking account, so it cannot
     buy labels. Add it to Banchi's settings file, then press Read Again. Nothing is bought."

   The confirm can still be refused, if the settings change between the two presses. The
   sentences then:
   - `tracking_key_missing` or `tracking_shipper_missing`: the two sentences above, opening with
     "Nothing was bought."
   - `tracking_auth_rejected`: "Nothing was bought. TCGTracking did not accept the key. Check it
     in your TCGTracking account, then press Make 15 Labels again."
   - `tracking_invalid`: on that order's row, "Refused"; in the receipt, "TCGTracking refused
     this order's details, so no label was bought for it."
   - `tracking_rate_limited`: the partial receipt's sentence (`#s=partial`).

   Each puts the server's words behind "What the server said".

## Making the labels

9. **Pick (a): progress is read from the store's label list during the press.** While the
   confirm is open, the screen reads `GET /shipping/labels` once a second and stops when the
   confirm answers. Each label row carries `status`, `pending` or `made`. A `pending` row says
   "Making" (the live dot), and only a `made` row says "Made", so "Made" never lights before the
   label is bought. These reads happen only during the person's own press; scans are never read
   on a timer. Option Q1 sends one confirm per order instead: no new field, but the
   stop at the first error becomes a second home in the screen. Pick: the list read.
10. **Close is off while labels are made, with its reason on hover.** The receipt must land on
    the sheet that asked for it. A disabled button takes no focus, so the builder ties the reason
    to the button with `aria-describedby`, as `pricing-owed-notes.md` item 6 does.
11. **Stop After This Label sends `POST /shipping/batches/<b>/labels/stop`.** The house rule is
    that long work shows a Stop; fifteen creates, one at a time, take more than a few seconds.
    Pressed (`#s=stopping`), it turns its ring in its own place and the line says "Stopping once
    the label being made is done." The label being made finishes, so nothing is left half
    bought. The confirm then answers with the stopped receipt (`#s=stopped`): "Stopped after 6
    labels, as you asked. 9 were not tried. Make the Other 9 asks for those only, and the 6 made
    are not bought twice." Info tone, not warn: nothing went wrong.

## The receipt

12. **All made (`#s=receipt`): one sentence, Print All 15 Labels, and Reprint on each row.**
    Print All opens `GET /shipping/batches/<b>/labels/pdf`, one file with every label made from
    this export so far, in a new tab where the browser prints it. Option R1 drops Reprint from the
    receipt.
13. **Stopped early (`#s=partial`): made, refused and not tried show on each row.** Make the Other
    9 opens a new preview over the rest only (`#s=again`), where the 6 made are held back with
    their own sentence.
14. **Reprint, against `GET /shipping/labels/<order>/pdf`.** It sits at the end of each made row on
    the receipt and on each row of the Labels list. It is an icon button, the printer icon, 40 px:
    the word "Reprint" on fifteen rows is the same label fifteen times (the house rule: a label
    shows once on a screen). Its tooltip is "Reprint", and its name to a screen reader is "Reprint
    the label for order N". Loss: the act is one hover from its word; Print All, in words, sits
    under the same rows. States, all in one cell, so the row keeps its size (`#s=reprint`):
    - idle: the printer icon;
    - opening: the ring turns in the button's own place until the file answers, then the file
      opens in a new tab, where the browser prints it;
    - failed: the scan line's place says "Banchi could not open this label's file. Nothing was
      bought.", and the button reads "Try Again" in the same place.

    It costs nothing. The route returns the stored file (`pdf_base64` on the label row), and at
    most TCGTracking's free re-render. It never creates a label.

## Tracking back

15. **The Labels list is read from the store and sits last on the page** (spec T5). The sample
    list shows 7 rows only; its figures do not add up with the card's. "Made Oct 25" reads
    `made_at`, "Last scan" and "Held Up" by days read `scanned_at`, and "Scans were last checked"
    reads `checked_at`. A label that
    lands moves nothing above it. Delivered labels fold under "Show 12 Delivered" (option F1 shows
    every label). The list is on the page with no export read (`#s=nofile`).
16. **Check Scans is one press, on demand.** Its answer lands on the line under the title, in a
    line held from the first paint. The order of rows does not change on a check. With no key it
    says "Nothing was checked. Banchi has no TCGTracking key on this Mac." on that same line.
17. **Pick (c): six scan words.** "Not Checked" (before the first check), "No Scan Yet", "On Its
    Way", "Delivered", "Held Up" (warn: the label service names a problem, or no new scan in 3
    days), and "Unclear" (warn: a status Banchi has no word for, with its words behind "What the
    server said"). Each maps from the label service's own status. That vocabulary is unmeasured
    until the first live lookup. The mapping has one home, shared with Orders.
18. **Option W1, a label word on each envelope-lane row too.** The word then shows twice on one
    screen. Pick: no.

## Words that change

19. **The no-export note is no longer true** (`ShipStage`, the note under the drop). It says
    "Nothing is saved". After D326 the store keeps each envelope order's address and its label.
    New: "Banchi keeps each envelope order's address, so it can make the label. The file is
    forgotten after 30 minutes. No buyer info shows here." **Owner grant: yes**, because it changes a sentence the owner
    reads as a promise.

## Kit gaps (described, not built)

20. **A switch.** No kit primitive exists. `BoxOps.css` has `.boxops-check`, and
    `CaptureScreen.tsx` draws its own `role="switch"`. Proposed: a kit `Switch`, a checkbox with
    `role="switch"`, 36 by 20 px, its knob 16 px, accent when on, its hit area padded to 40 px,
    with a label for screen readers. The mockup's `.labels-switch` is the shape.
21. **A printer icon.** `kit/Icon.tsx` has none. Proposed path, 24 grid, stroke 1.75: the paper
    tray on top, the body, and the sheet coming out at the foot, as the mockup's `printer` icon
    draws it. One meaning: print a label file.

## Needs wire field (the contract does not carry these)

- `envelope` on the preview: the envelope size the summary shows. Without it, the builder leaves
  the Envelope line out.
