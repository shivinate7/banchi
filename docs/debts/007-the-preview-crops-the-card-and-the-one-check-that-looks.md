## 7 — The preview crops the card, and the one check that looks at a photo cannot see it

**REOPENED 2026-09-10.** It was closed the day before by cropping the photograph to the card
(D125), and the owner reverted that on four of the six screens after using it: a photograph that
re-frames itself as a reading lands is worse, in use, than one that clips. **So the clipping is
back on the `#/inventory` preview, the sell-confirm and the Fulfiller's pull preview**, at the
figures this section already measured — 48 of 48 sampled box-3 frames, worst 333px off the bottom,
and 68px off the card's bottom edge on the Fulfiller's screen at the worst geometry.

**THE LETTERBOX HALF IS FIXED AND STAYS FIXED, AND IT IS A DIFFERENT DEFECT FROM THE CLIPPING.**
`#/pricing`'s drawer was drawing 36.1px of ground down each side of a 340px window because
`.pricing-photo-frame` set no `object-fit` and inherited the kit's `contain`. That is now stated
as `cover` in `Pricing.css`. Nobody ever chose the bars; they arrived with `.bn-photo` in the
Banchi rebuild. **Reverting a change is not restoring a bug that predated it.**

**WHAT IS ACTUALLY OPEN HERE IS NARROWER THAN IT WAS**, and the crop is no longer a candidate fix
without a way to make it land invisibly. D125 has the costed options and the two hazards found by
building it; the reversal paragraph in that entry has the reason it is not the answer.



**The argument this section was open on — that the two available fixes traded
legibility against coverage in opposite directions, and that one of them moved a published floor —
was true when it was written and had been overtaken by machinery built for another screen:
`POST /pipeline/crop-preview`, `kit/index.tsx:cropStyle` and `.bn-crop` already shipped on `#/`
and on `#/pricing`'s row thumbnails. A third fix existed and this section did not name it. D125
carries the whole argument; what is kept here is what the section got WRONG, because the shape of
that is the reusable part.

**IT DESCRIBED A TREE A WEEK OUT OF DATE, IN BOTH DIRECTIONS, AND ACTING ON IT WOULD HAVE PRODUCED
THE WRONG CHANGE.**

- It said `#/inventory` letterboxes. It had stopped: `53f5eff`, 2026-09-07, moved the rule to
  `.browse-photo-frame .browse-photo` at (0,2,0), which beats `.bn-photo img`'s (0,1,1).
- It did not say `#/pricing` letterboxes, and it did. `.pricing-photo-frame` sets an aspect and a
  cap and no `object-fit`, so the kit's `contain` applied — **measured on the screen at 36.1px of
  ground down each side of a 340px window**, 10.6% of the width twice over. The identical defect,
  by the identical route, one screen over.
- It listed `app/src/Pricing.css` among five stylesheets drawing `object-fit: cover`. That file
  contains no `object-fit` at all; the leak there is the absence of one.

**A DEBT ENTRY IS A MEASUREMENT WITH A DATE ON IT, AND THIS ONE READ AS A DESCRIPTION OF THE
PRESENT.** Nothing reconciled its claims against the stylesheets it named — `raw color` reads
those files for hex literals and no row reads them for the property this section is about. The
measurements it took are unaffected and are carried into D125: 48 of 48 sampled box-3 frames
clipped, 34 at the bottom, worst 333px.

**WHAT IT WAS RIGHT ABOUT, AND WHAT STILL IS NOT COVERED.** `make design-check` was green over all
of it, and the reason it gave is exact and still stands: `docs/DESIGN.md`'s floor is `>= 320px` on
the short edge of the pull-modal photo, `paintedPhoto` measures how large the photograph is DRAWN,
and **a floor on size is not a floor on content**. Under `cover` the frame fills the box by
construction, so the painted short edge IS the box and the row passes at exactly the moment the
card is being cut. The crop does not close that gap — it pays it once, on the screens it reaches.
Nothing in the suite asks whether the card is inside what was drawn, and closing it needs
`detect_card` behind a Playwright row: slower than the suite it joins, and able to refuse. Still
not costed.

**AND THE CROP IS ONLY EVER AS GOOD AS THE READING BEHIND IT.** D125's client-side refusal — a
rectangle overrunning its frame by more than a sixth is not believed, and every caller falls back
to what shipped — is a floor under a failure that was reproduced, not a tuned threshold. It rests
on three good readings and one bad one. **The first real rig photograph that trips it is the
measurement that should replace it**, and until one does, the honest reading of this is that the
fallback is well tested and the threshold is not.
