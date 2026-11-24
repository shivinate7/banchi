# Fulfillment: the queued Undo

Mockup: `fulfillment-queued.html` in this folder. Designer kind: informed. It opens from disk.
The frame is the screen at the page's own width: render it at 1440 or 820. Both widths draw a 720px column
(the card view 1080px) and a 680px sheet, so the Undo geometry is the same at both.
Deep links: `#s=<rest|sheet|handoff|row|skipped>&t=<light|dark>&wq=<right|left>&wr=<head|strip>&b=<kit|ff>&x=<cancel|run>&r=<plain|ring>`,
plus `l=0` (labels off: the true geometry) and `h=<keys>` (hidden options).
Focus ids for the waiting page, per option: `wq` (with `s=sheet`) focuses `sheet-note-right` and `sheet-note-left`.
`wr` (with `s=row`) focuses `row-note-head` and `row-note-strip`. `b` (with `s=sheet`) focuses `sheet-undo`. `x` (with
`s=skipped`) focuses `skip-list`, where Glimmer Fox comes back only under `x=run`. `r` (with `s=row`) focuses `run-plain`
and `run-ring`. The row's queued Undo is `row-undo`.
Tokens: a copy of `app/src/tokens.css`, light and dark. The rules are copied from `app/src/Fulfillment.css` and
`app/src/kit.css`, in that load order. The kit Button measurements come from a scratch page that loaded the real
`kit.css` and then `Fulfillment.css`.

Governing: D329 (a taken press answers at once, one shared state), D050 (a press shows on its frame), D118 (a press
moves nothing), D313 (nothing moves unless the person moved it), DESIGN.md's Fulfillment floors (20px text, 7:1,
44px targets, no "queue" on screen), and the D329 design in `press-queued-notes.md` (the kit `busy="queued"` and `QueuedNote`).

1. **Moving onto the kit `Button` changes today's look, so the normal state keeps today's look by override.**
   Measured with `bn-btn` added and nothing else:
   - `ff-undo`: the kit's 1px border (2px wider) and box shadow at rest. On hover, `.bn-btn:hover` (two classes)
     outranks `.ff-undo`, which sets no hover ground. The ink fill turns to `--bn-btn-bg-hover` and the `--bn-bg`
     label disappears, in both themes.
   - `ff-done-undo`: the label drops from 20px to 13px, under the view's 20px floor. It also gains the ring, the border
     and the kit's 0.99 press squeeze.
   - Both: the `icon` prop draws a 16px glyph. Today's glyphs are 22px and 18px.
   Fix, in `Fulfillment.css` (builder): `.bn-btn.ff-undo, .bn-btn.ff-done-undo` set `border: 0`, `box-shadow: none`,
   `height: auto` and `font-size: var(--ff-fs-base)`, and each sets its own hover ground. The glyph stays a child
   `<Icon size={22|18}>`, not the `icon` prop. The mockup's "NEW: what Fulfillment.css adds" block holds the rules.
   The kit's press squeeze stays, because the press floor is the product's (D050).
   Departs from: `ff-done-undo`, which has no press squeeze today. Pick: as drawn.

2. **The queued face.** It is the kit's `busy="queued"` as built: the label and the ink fill stay, and a static mark sits on
   the corner. The press is refused, and it is not `disabled`, so it is not dimmed. DESIGN.md says this view has no
   disabled state; the queued face sets `aria-disabled` but paints at full strength. Grep found no
   `fulfillment.spec.ts` assertion on `aria-disabled` in the view. The mark is `aria-hidden`; the words carry the state.

3. **The mark's size.** Two options, each with a Hide control:
   - Kit size (`b=kit`): 18px disc, 12px glyph. It is the same on every screen, but small beside a 56px pill read at arm's length.
   - Larger mark (`b=ff`): 24px disc, 16px glyph, scoped to `.fulfillment`. It is the same primitive at this view's
     scale, as the view's 20px type already is.
   Pick: larger mark. It is a size override, not a second primitive (D329).

4. **The receipt's words.** They go in the strip the receipt already keeps above its content for the X
   (`.ff-receipt`'s top padding, 44px plus gaps). Positioned absolutely, they change no height, so
   `--ff-sheet-h` and the page under the sheet stay put. At 20px they fit at both widths. Two options:
   - Above the Undo (`wq=right`): right-aligned, ending 12px before the X, over the Undo. The words sit next to the press.
   - Above the receipt words (`wq=left`): at the text column's left edge. They read as part of the receipt, farther from the press.
   Rejected: the empty clock row under the Undo, and the receipt's note line. Each one grows the sheet on the press (D118).
   Pick: above the Undo.

5. **A Pulled today row's words.** The row has no free room. Its Undo already wraps to a second line when the row has an
   order number, and inline words would add a third line and push every row below (D118, D313). Two options:
   - Pulled today's heading line (`wr=head`): right-aligned on the 32px heading line, absolutely positioned outside the
     `h2`. There is room at both widths. The mark shows which row.
   - The sheet's top strip (`wr=strip`): always on screen. But it sits on another card's receipt, so it must name the
     card, and a long card name is cut with an ellipsis.
   Pick: the heading line. Its loss: on a long Pulled today list, a row far below the heading has its words off
   screen, and only the mark shows at the press.

6. **The words.** The view bans "queue" on screen, and none of these words uses it.
   - Behind a sale: "Waits for the sale to save."
   - Behind another undo: "Waits for the other undo to save."
   - Heading line: "Undo waits for the other undo to save"
   - Sheet strip: "Undo for <name> waits for the other undo to save"
   Size and color: `--ff-fs-base` (20px) in `--bn-ink-2`, with the mark at 20px in `--bn-accent`. Computed (WCAG) from
   the tokens: ink-2 on `--bn-surface` (the sheet) is 10.3:1 light and 9.7:1 dark; on `--bn-bg` (the heading line) 9.4:1
   light and 10.4:1 dark. The view's floor is 7:1. The kit `QueuedNote` is 13px,
   so `.fulfillment .bn-queued-note` needs a size override (builder).

7. **The hand-off is the common case, not an edge.** `doSell` calls `remember` only after the sale lands. So the reader
   marks Tidepool Newt sold, then presses U or the receipt's Undo. The target is Glimmer Fox, the newest standing receipt,
   and its Undo goes queued on the sheet (`s=sheet`). When the sale lands, Tidepool Newt takes the sheet, Glimmer Fox drops
   to Pulled today, and its undo runs at once (`s=handoff`). The queued flag must key on the card, not the control: if
   the row draws before the undo starts, that row's Undo shows queued.

8. **An undo that is running.** Two options:
   - As today (`r=plain`): no ring. A press on it sends nothing.
   - Ring (`r=ring`): the kit's `busy`. The ring on the ink pill needs `--bn-bg`, because the kit's `--bn-ink-3` is about
     3.4:1 there (builder).
   Departs from: `doUndo`, which shows nothing while it runs. Pick: as today, since it is not in this lane's scope.

9. **Skipped: the X pressed while the Undo waits.** This is the one way the receipt can be gone on this screen.
   Dismissing filters the sale out of `sales`. A second U on a queued receipt queues nothing (item 7 of
   `press-queued-notes.md`). Two options:
   - Close skips the undo (`x=cancel`), the plan's rule: no write. The face, the mark and the words leave with the
     receipt, and no new words appear. Glimmer Fox stays sold. It is not in Pulled today and not back in the list,
     and nothing on screen says so. On this screen a sale that should have been undone leaves the card sold while it sits in the binder.
   - Close keeps the undo (`x=run`): the X hides the receipt. The press was taken first, so the undo runs when the sale
     lands, and the card comes back to the list. `doUndo` takes the card, not the receipt, so it can still run.
     Its loss: from the X until the sale lands, the press still waits, but its mark and words left with the receipt,
     and the screen has no toasts. For that interval nothing answers on screen, which D329 asks against.
   Rejected: dimming the X while queued (the view has no disabled state), and a sentence in `ff-trouble` (it is in the
   flow and moves the page).
   Pick: close keeps the undo. Departs from: the plan's skip rule. Owner grant: yes.

10. **U's target right after a sale.** U pressed while Tidepool Newt's sale saves undoes Glimmer Fox, the older sale, not
    the one just pressed. That is today's target, and the plan keeps it. The mark names Glimmer Fox while it is queued,
    but once Glimmer Fox drops to Pulled today, nothing on screen names it until the row leaves.
    Departs from: nothing. This is a question, not a change. Owner grant: yes, for whether U should wait for the
    new sale and undo that instead.

11. **The big photo hides the sheet** (`data-zoom`, `visibility: hidden`). A U pressed while the photo is open queues
    on a receipt no one can see, and the hidden live region is not announced. The mark and the words show when the
    photo closes. Not drawn. Builder note.

12. **Critique** (impeccable, degraded: single context, because a designer has no sub-agent tool; no browser overlay,
    because the pane cannot script a local file). Fixed: the striped photo placeholder is now flat `--bn-surface-2`.
    False alarms, kept: the low-contrast hover sample in the kit check (it is the defect, drawn on purpose); cramped
    padding on the mockup's tabs and dashed Today/New outlines (annotations); "Undo" repeated (hidden per-state
    variants and the comparison grid); Inter (the repo's UI face); 1.2 leading on the one-line words (the `.ff-h2` value).
    Kept as notes: the heading-line words' loss (item 5) and the silent skip under `x=cancel` (item 9). Outside scope:
    the receipt's place wraps inside a part ("Card" then "14" on the next line), because `.ff-receipt-place` parts do
    not hold together. That is today's product, and it needs a `white-space: nowrap` in `Fulfillment.css`.
