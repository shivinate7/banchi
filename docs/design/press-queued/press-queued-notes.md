# Press taken, queued: one shared state

Mockup: `press-queued.html` in this folder. Designer kind: informed. It opens from disk.
Deep links take `#s=<sending|queued|undone>&o=<hourglass|clock|ring>&w=<row|toast>&t=<light|dark>`, plus `l=0`
(labels off: the true geometry) and `h=<keys>` (hidden options).
Sections: the walk row, a kit `Button` queued, a fit check on Inventory, and the words.
Focus ids for the waiting page: `o=hourglass`, `o=clock` and `o=ring` focus `queued-undo`. `w=row` focuses
`queued-note-0`. `w=toast` focuses `queued-toast`. The kit Button's queued state is `queued-send`.
Widths: the walk's copy column is drawn at 495px for 1440 and 368px for 820. Both widths were read off walk
screenshots that another session left in the scratchpad, from an unknown head. They were not measured on this head.
The one-column walking layout at 820 gives a wider column, so 368px is the tight case. The send bar frames (1100px
and 692px) are not taken from a screen. They show the kit Button alone. Both themes draw from a copy of
`app/src/tokens.css`. The glyphs are copied from `app/src/kit/Icon.tsx`, except the new hourglass.

Governing: D-press-queued-state (a taken press answers at once), D50 (a press shows on its frame), D118 (a press
moves nothing), D128 (a key press answers on screen), `docs/specs/undo.md` section 10.

1. **The primitive: extend `Button` and `IconButton`, and add one words part.** The Explore pass recommended a
   `queued` value on the kit `busy` prop. I keep that, with three changes.
   - The prop becomes `busy?: boolean | 'queued'`, and the DOM gets `data-busy="queued"`. Today's
     `data-busy={busy ? 'true' : undefined}` would turn `'queued'` into `'true'` and draw the ring, so the emit
     must pass the value through. The ring rules match only `'true'`.
   - A queued face is not disabled. It sets `aria-busy="true"` and `aria-disabled="true"`, and refuses a click
     (`pointer-events: none`), so a second press queues nothing (undo.md section 10). It never sets `disabled`,
     because `disabled` paints `--bn-disabled` (0.45) and reads as refused.
   - Words that show on screen. SendCard's `'waiting'` words sit in a `bn-sr` span that no one sees. That fails
     D128 and the ruling. A kit `QueuedNote` draws the mark and one sentence, with `role="status"`, and the press
     points at it with `aria-describedby`.
   Reuses: `Button`/`IconButton` and their `busy` prop; the corner placement of `.bn-icon-count` (absolute, outside
   the flow); `Icon`; `toast` kind `status` (item 4 only).
   Gain: one prop, one attribute value and one part serve every screen. Loss: every `busy` call site that also
   passes `disabled={busy}` must leave `disabled` off while queued. Pick: this form.

2. **The look: the label stays and a badge arrives.** The face keeps its label (words or glyph) at full strength,
   and its own paint. A static badge, 18px, sits on the top-right corner: an accent disc with the mark in
   `--bn-on-accent`, ringed in the ground it sits on. A frameless face (`ghost`, a bare `IconButton`) takes its hover
   ground (`--bn-accent-tint`) while queued, so the badge has a frame to sit on. The walk's Undo keeps its outline
   frame. Busy hides the label behind a ring, but queued keeps the label. That is the difference a person reads:
   "this press is taken" against "this press is running". The state arrives on the press's own frame with no
   transition (D50).
   Measured in the mockup (labels off), the walk row is 180.8px tall in all three states at both widths. Nothing
   moves (D118).
   Pick: as drawn.

3. **The mark.** Three options, each with a Hide control:
   - Hourglass badge (`o=hourglass`). A new icon path, `queued`, meaning "a press taken and waiting its turn". It is
     static and cannot read as a spinner. It needs a path in `app/src/kit/Icon.tsx` and a line in `ICON_MEANINGS`.
     It is drawn at the set's 1.75 stroke. At 12px in the 18px disc it reads as an hourglass when magnified, but
     at 1x it is small. If the builder finds it unclear, the badge glyph goes to 14px in a 20px disc.
   - Clock badge (`o=clock`). No new path. But `clock` already means a time span on the same screen: the fetch
     press "Last two years" and the "since" chip in `RunsComposer` (one icon, one meaning, UX-118).
   - Frozen ring (`o=ring`). The busy ring, stopped. DESIGN.md's motion section already rejects this: "a ring
     stopped at a partial arc reads as a disabled button". It hides the label too. Drawn so it can be culled.
   Pick: the hourglass badge. Owner grant: no (a new path is a kit addition the builder makes).

4. **Where the words go.** Two options, each with a Hide control:
   - Beside the press (`w=row`). In the walk this is the row's action foot, right of the Undo frame, on the same 40px
     line. At 368px it fits with 17px to spare. At 495px the spare is 144px. The answer lands where the press
     was (UX-058).
   - Status toast (`w=toast`). The toast stack is always on screen. But the answer lands away from the press, and at
     820 the toast stack covers the row's foot (seen on the walk render).
   Pick: beside the press. One case needs the toast: the owner steps to another card and then presses `U`. The sold
   row is unmounted, so nothing beside it can show. Then the screen sends the same words as a `status` toast.
   A builder must add that fallback, or `U` still shows nothing in that case.

5. **The words.** Exact strings:
   - Template beside the press: "Waits for <the write ahead> to save." The press names itself, so the note does not
     repeat it.
   - Template away from the press (toast title): "<Press> waits for <the write ahead> to save". The body is the
     place, from `sayPlace`.
   - Walk, `U` while the sale saves: "Waits for the sale to save."
   - Toast form: "Undo waits for the sale to save", with the body "Binder A, Section 2, Card 14".
   - After the undo runs, unchanged: toast "Pull undone", with the body "<place> holds <name> again." (`onWalkUndo`
     in `Orders.tsx`). The row gets Mark Sold back, with the reverse bills (`MarkSoldButton`).
   - Pricing Send: "Waits for your prices to save." Departs from: `SendCard`'s `doing`, which says "Saving your
     prices…" to a screen reader only.
   "Save" is the screen's own word ("Saving your prices"). No mechanism word, such as line, queue or write, is
   shown (D196).
   Pick: as listed.

6. **The walk's three states**, from `RowAction` and the line in `OrdersWalkPane.tsx`:
   - Sending (Today): the Undo shows the ring and its glyph is hidden. In this window the row's Undo cannot be
     pressed: `IconButton` carries `bn-btn`, so `[data-busy='true']` sets `pointer-events: none`, and `RowAction`
     passes `disabled={busy}`. So `U` is the only press here. The brief said the row's Undo could also be pressed.
     That is a correction, not a change.
   - Queued undo (New): the glyph is back, the badge is on, and the words are beside it. Builder note:
     `receiptOf` maps `undoAfter` to phase `'undoing'`, and `RowAction` reads `'undoing'` as busy. So the row
     cannot tell "queued behind the sale" from "undo running" today. It needs one more phase, or `undoAfter` on the
     receipt. Queued draws while the sale is out. The ring draws once the undo itself is out.
   - Undone (Today): Mark Sold returns, and the receipt toast says what happened. The badge and words leave on the
     same frame.

7. **A second `U` while queued.** Today it does nothing (undo.md section 10). With this state, the badge and words
   are already on screen. The second press sets the status text again, so a screen reader hears it again. Nothing
   else changes, and nothing more is queued.
   Owner grant: yes. Section 10's sentence "`U` waits and does nothing" changes to "`U` shows the queued state".
   That is a spec edit, outside the design folder.

8. **Second users: presses that drop today.** Inventory `doSell` and `doUndo` (`if (busyKey !== null) return`),
   Fulfillment `doUndo`, BoxShelf undo, and ReviewQueue undo each return early while another write is out. Nothing
   shows. The section "Fit check" draws Inventory's copy row with its Undo queued. It is the same `CardLocations`
   row, the same kit state, and the template words "Waits for the last sale to save." Not built.
   Departs from: each early return above. Using the state there turns a drop into a queue, which is a behavior
   change, not a restyle. SendCard's `'waiting'` phase already queues, and adopts the state with no behavior change.
   Owner grant: yes, for turning each drop into a queue.

9. **Critique** (impeccable, single context, because a designer has no sub-agent tool). Fixed: the mockup's tags
   moved from 10px to 11px, the mockup's tabs got an inset, and section titles got the tight tracking. Not fixed
   (outside scope): the ruler's 10px tick figures and BACK/FRONT, which copy the product's `PositionBar` at
   `--bn-fs-2xs`. Not fixed (false alarm): "cramped padding" on the mockup's segmented tabs and on the dashed
   Today/New outlines, which are annotations. Open: the badge sits outside its box, as `.bn-icon-count` does. A
   container with `overflow: hidden` close to a queued press would clip it. In the walk the row does not clip.
