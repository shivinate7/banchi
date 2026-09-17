## D125 — The photograph is cropped to the card, the focus is derived from the reading, and a reading that cannot be believed is a refusal

**Settled 2026-09-09, on the owner's instruction to take §7.** That section had
been open on the ground that its two fixes — `object-fit: contain` and a server-side crop — traded
legibility against coverage in opposite directions, and that one of them moved a published floor.
**Neither is what landed.** The thing that closed the argument was built for something else in
the meantime: `POST /pipeline/crop-preview`, `kit/index.tsx:cropStyle` and `.bn-crop` already
shipped on `#/` and on `#/pricing`'s row thumbnails. A third fix existed and no entry named it.

### What was actually wrong, which was two defects wearing one description

**§7 described a tree a week out of date in both directions.** Reading it rather than the code
would have produced the wrong change.

- **`#/inventory` was letterboxing and is not any more.** `53f5eff`, 2026-09-07, moved the rule to
  `.browse-photo-frame .browse-photo` — (0,2,0), which beats `.bn-photo img`'s (0,1,1). D38's
  `cover` is back in force there and §7's second sub-entry describes what that commit fixed.
- **The bars moved to `#/pricing`.** `.pricing-photo-frame` sets an aspect and a cap and no
  `object-fit`, so the kit's `contain` applied. Measured on the screen: a 340x476 window drawing a
  2160x3840 frame, **36.1px of ground down each side**, 10.6% of the width twice over. Nobody
  chose it; it arrived with `.bn-photo` in the Banchi rebuild, the same way and in the same week
  `#/inventory` lost `cover`.
- **`cover` clips the card, which is the defect §7 was opened for and is not the same defect.**
  48 of 48 sampled box-3 frames lost an edge, 34 at the bottom, worst 333px — the corner the
  collector number and the set line print in.

**One mechanism answers both**, which is why they are one entry: a photograph framed on the
card cannot letterbox and cannot clip.

### The rule, and the two screens it deliberately does not reach

**Crop where the photograph is shown to LOCATE or PRICE a card.**
**Keep the whole frame where it is shown to JUDGE the card or to CHECK THE RIG.** So: the `#/inventory` preview, the `#/pricing`
drawer and its thumbnails, the sell-confirm, the Home hero, the Fulfiller's pull preview. Not:

- **`#/review`**, whose photograph carries no `object-fit` on purpose — `ReviewQueue.css:189`,
  *"The `<img>` box IS the drawn image — so the loupe maps the pointer to a natural pixel with no
  letterbox arithmetic."* Cropping puts letterbox arithmetic back inside a loupe built to avoid
  it, on the screen where D32 keeps the whole frame because a card is being judged.
- **The capture screen's undo thumbnail**, which exists to say the last shot landed right.
  Cropping to the detected card hides the failure it is there to reveal — the card drifting out of
  the stand — and would fire a request per shot at a 623 ms feeder cadence.

### The Fulfiller's screen was the one real question, and it was answered by measuring

D32 keeps the whole frame where a photograph is matched to a physical slot, and D31 says his
floors are not a session's to reopen. Both survive:

- **The floor is on painted SIZE, and the crop only makes the card bigger in the same box.**
  §7 already records that a floor on size cannot see whether the
  card is inside what was drawn, and this is that gap being paid rather than widened.
- **Measured on his screen at the worst geometry §7 recorded** — a card with its bottom edge at
  98% of the frame — **`cover` cut 68px off the bottom of the card in a 440x615 box.** The
  collector number is printed in the panel beside the photograph, in the line he is checking
  against. The one comparison that screen exists to allow was the thing being clipped.
- **The slot is matched by the position label, in 32px type, not by the stand in the photograph.**

### The focus is derived, because a constant is wrong and was wrong here first

`cropStyle` takes a `focus` — where the window sits on the reading. **The first build of this used a constant per window,**
**and that is a bug rather than a simplification.** A window at a card's own 63/88 holds a WHOLE
card, and where that card sits inside the reading varies per photograph: the
detector's rectangle runs 0.55 to 0.60 wide-to-tall against a card's 0.716, the surplus being the
stand's strip below the card, and only its TOP tracks the card reliably (721 against 741 on box 3).
So `kit/index.tsx:wholeCardFocus` computes it — the card is about `rw / cardAspect` tall from the
rectangle's top, and half of that is where the window's centre belongs.

**The rectangle is clamped to the frame first, and that is not defensive tidying.**
**Real readings overrun it.** `[240, 1051, 1649, 3020]` on box 6 — a figure this repo already had written down —
ends 231px below a 3840px frame. Unclamped, the overrun is counted as stand to be dropped and the
window rides up off the card.

**THE THUMBNAILS KEEP THEIR CONSTANT AND THAT IS NOT AN INCONSISTENCY.** 0.34 was chosen by
looking at eight real rows because at 36x48 the whole card cannot fit and something must be
chosen; the derived figure answers a different question — *where is the card* — which only has an
answer when the card fits.

### A reading that cannot be believed is a refusal, and this is the half that was found by breaking it

`wholeCardFocus` returns `null` for a rectangle running more than a sixth of the frame past its
edge, and every caller treats that exactly as it treats `crop_refused`: no inline style at all,
the element's own framing untouched, the screen identical to what shipped.

**It exists because the failure was reproduced.** On frames with the card sitting low, the
detector answered `[216, 1718, 1530, 3553]` — 1,431px past the bottom of a 3840px frame, having
also missed the card's top by 427px. Cropped to it, the card went further out of view than no crop
at all. **A crop is only ever as good as the reading behind it.**
**A screen that trusts a bad one is worse than a screen that never asked.**

**THE THRESHOLD IS THIN EVIDENCE AND IS NAMED AS SUCH**: three good readings and one bad one. It
is a floor under a known failure mode, not a tuned value, and the first real rig photograph that
trips it is the measurement that should replace it.

**AND THE FIRST BUILD OF THE REFUSAL DID NOT REFUSE.** Passing `cropStyle(crop, focus ?? undefined)`
let the parameter's own `= 0.34` default take over, so an unbelievable reading produced a crop
style with the flag that positions it withheld — an inline width and transform with none of the
rules that make them mean anything. It rendered as a sliver in a corner. **A fallback spelled as a default value is not a fallback** —
and the shape of that is worth more than the fix.

### The fetching is one machine now, in `app/src/cardCrop.ts`

`kit/index.tsx` holds the geometry and its own comment says why the fetching is not there: *"the
hero asks once for one card, the worklist asks for the rows a scroll brings into view, and those
are policies, not geometry."* That was right while there were two screens. At five it is one
module with both policies, one cache for the whole app, and the four findings the policy is made
of written down once — one card per call, strictly serial, observer-gated for lists, answered once
per session — instead of being copied to a fifth caller that would carry none of them.

**URGENT JUMPS THE LINE, AND THE BOX WALK IS WHY.** `#/inventory` steps card by card under an
arrow key, and auto-repeat is faster than the ~115ms a reading costs. FIFO answers the card the
operator is LOOKING AT last — about eleven seconds after they stop moving on a hundred-card walk.
Every screen drawing ONE photograph asks urgently and supersedes its own previous card, so the
backlog cannot grow with the length of the walk; a list's observer-driven rows keep the plain end.

### The specificity trap is stated once, in the kit, because this is the third time

`.bn-photo img` is (0,1,1) and `.bn-crop` was (0,1,0), and every screen reaches its own photograph
through a (0,2,0) descendant selector. Written naively the crop LOSES to all of them on `height`,
and the failure is silent and specific: the inline width still applies, the screen's `height: 100%`
still applies, and `object-fit: fill` then stretches the photograph across a box of the wrong
shape. Measured before it was fixed — a 2160x3840 frame drawn into 360x452, which is a squashed
card, not a cropped one, **and it looked enough like a small card to pass a glance.**

**`aspect-ratio` goes with the height, for the same reason.** `.fulfillment-photo` and
`.card-locations-photo` both put `aspect-ratio: 63/88` on the `<img>`, correctly, because the
`<img>` WAS the window before the crop existed. The cropped state clears it.

**So the kit states it at (0,2,1) and no screen has to know.** `.browse-photo` lost `cover` to the
kit in the rebuild, `#/pricing`'s drawer was still losing it a week later, and this is the crop
losing to the screens. **Specificity that has to be re-derived at each call site is the defect.**

### AMENDED 2026-09-10, AT THE RIG: THE CROP LANDS INSTANTLY, AND THE EASE STAYS WHERE IT WAS WRITTEN

**The owner walked a box with this and the word for it was motion sickness.** `.bn-crop`'s cropped
state carried `transition: width, transform` over `--bn-t-slow`, inherited from the block as it
shipped for the Home hero, and every screen this entry added picked it up.

**The transition was right for exactly one case.** This entry did not notice it was leaving it on
everything else. The hero is one photograph resolving once on load, and easing into its crop reads as the page
arriving. Everything else here is a REPEAT: the reading is asynchronous, so a card draws under its
own framing and adopts the crop about 115ms later — and eased, that is a zoom-and-pan fired again
on every step of the `#/inventory` walk and on every thumbnail an observer pulls into the pricing
worklist. Stepping a box became a succession of swoops, each one driven by network timing rather
than by anything the operator did.

**A crop that lands instantly reads as the photograph having always been framed that way**, which
is what it is. `.browse-photo`'s existing fade is untouched and is doing the job of covering the
swap — a fade is not movement, which is the distinction `docs/DESIGN.md` already draws.

**The ease is scoped to `.home-deck-photo` rather than deleted**, so the case it was written for
keeps it and the next screen to draw a cropped photograph inherits the instant behaviour and has
to ask for motion deliberately. **That is the general lesson and it is not about this transition**:
a value tuned for a screen that resolves ONCE becomes a different thing entirely on a screen that
resolves PER ROW, and moving a rule into a shared kit block is exactly the move that makes the
change invisible.

### REVERTED 2026-09-10 ON FOUR SCREENS, BY THE OWNER, AFTER USING IT

**The owner walked a box with it and asked for it back out**, in those words: *"yeah i hate it,
undo the crop on the screens that just added it"*. So the crop is gone from the four this entry added it to — the
`#/inventory` preview, the `#/pricing` drawer, the sell-confirm and the Fulfiller's pull preview —
and stays on the two that had it before, the Home hero and the pricing worklist's row thumbnails.

**THE ENTRY IS KEPT RATHER THAN DELETED.** The measurements in it are still true, and the
conclusion drawn from them was not this session's to reach. `cover` really does clip 48 of 48 sampled
box-3 frames; it really did cut 68px off the card's bottom on the Fulfiller's screen. What this
entry got wrong is the inference that removing the clipping was worth what it cost — a photograph
that moves under you as a reading lands, on every card of a walk.
**The clipping is a defect you can measure; the crop is a defect you can feel.**
The second one is the one being used.
§7 is reopened on exactly that basis.

**ONE THING IS DELIBERATELY NOT REVERTED.** `#/pricing`'s drawer does not go back to what it was.
Its original state was the kit's `contain` — 36.1px of ground down each side of a 340px window,
which is the black-bars defect that started all of this and which nobody ever chose. It is set to
`object-fit: cover` in `Pricing.css` explicitly, which is D38's answer stated rather than
inherited. Reverting a change is not the same as restoring a bug that predated it.

**What comes out with the four:** `kit:wholeCardFocus`, whose only callers they were, plus the
kit rules that existed for them alone — `aspect-ratio: auto` for an `<img>` that was its own
window, and the `min-height` floor for a published painted-size minimum. Rules kept past the thing
that needed them are rules citing measurements nothing runs. `app/src/cardCrop.ts` STAYS: the two
surviving screens are its callers, and it is where the fetch policy is written down once.

**The refusal guard goes with them and its finding does not.** A rectangle that overruns its frame
by a sixth is still a rectangle nothing should be framed on — measured at 1,431px of overrun on a
3840px frame, having also missed the card's top by 427px. Nothing reads that today. Anyone who
puts a crop back on a walk needs it before they need anything else in this entry.

### What this does not do

**It does not touch the review queue, the capture screen, or the sidecar.** §7 costed a server-side
crop and asked where the rectangle would live; the answer is that it does not need to live
anywhere. The reading is fetched free at read time, cached for the session, and forgotten — so
there is no capture-write change and no backfill over every photograph on disk.

**It does not make `detect_card` better.** Every screen here is one refusal away from exactly what
it drew before, which is the property that makes this safe to ship against a detector measured on
one rig on one afternoon.
