### T6 — Card geometry

New with batch script v2. The crop-retry path in §4.5 is only as good as its ability to
find the card in the frame, and a wrong crop produces a miss indistinguishable from a bad
read — so detection gets its own failing test name.

Synthetic composites only: a card rectangle rendered onto a background at a **known**
offset, scale and rotation, so the answer key is exact. No rig photo exists in this repo.

- **Pass**: detected rectangle within tolerance across the sweep; bands contain their
  target; no card -> not found; a ground the tone path cannot segment is still found by its
  borders; the cut and the rectangle the run panel draws are one computation; a box that is
  a rectangle inside the card is refused before it can be cut to
- The sweep is offset, scale and rotation. "Bands" are the title band and the number
  corner, and each must contain its target region. "Not found" must be a refusal, never a
  guess.
- **The blind spot this section warned about was measured on 2026-08-22, and it read
  zero.** `detect_card` found the card in **0 of the 53 Gate B photographs**. The paragraph
  below is left standing because it was right; what follows is what it was right about.

  The cause is not a constant. The card sits in a clear stand on a wood desk with a dark
  backdrop above, and its own artwork spans 88 to 231 against a border-ring median of 64,
  so there is no threshold between the two failures: at the adaptive threshold (88.5, which
  the bright card itself sets through the 99th-percentile term) 29% of the card is cut out
  of its own mask and `MIN_FILL` refuses 52 of 53; at `MIN_DELTA` alone the desk grain and
  the stand are foreground too, the box grows to the whole frame, and area and aspect refuse
  all 53. A planar background fit and a bottom-band background were both measured and both
  still find nothing.

  **T6 could not have caught it, and that is the part worth keeping.** `_scene` paints one
  flat color behind a uniformly bright card — precisely the premise the tone path assumes —
  so the test constructed the one condition under which the method works. A green harness
  was not wrong; it was answering a question nobody had asked it.

  It was latent rather than active: `detect_card` is reached only from the crop-retry path
  (`cli/cmd_identify.py`), and Gate B identified 53/53 at high confidence with zero retries,
  so it never ran. The cost is that the crop-retry rescue is inert on this rig — a weak read
  would get `card_not_detected` and go to a human instead of being retried on an enlarged
  number crop.

  **Fixed 2026-08-22 by a second method, not by moving a threshold.** `geometry/detect.py`
  gains a border search that runs only after the tone path refuses: four long straight
  luminance edges whose spacing matches a card, assuming nothing about what is behind them.
  It finds 53/53 on the Gate B photographs, and `CardBox.method` says which path answered so
  a run report cannot confuse the two. The tone path and its gates are unchanged.

  The regression case is `_rig_scene` in the test: the same synthetic card on a textured,
  unevenly lit ground with artwork running down to the background level, built from the
  measured ring values. It reproduces the mechanism rather than the photograph, because
  `captures/` is gitignored and this repo still holds no rig photo.
- **What is still not evidence.** The border search is measured against 53 photographs of
  one rig in one lighting state on one day. That is 53 more than this section could claim
  before, and it is still not a detection rate. Treat it as T1's finish blind spot is
  treated: recorded here so a green harness cannot be misread.
- **The border search's own failure mode was measured on 2026-08-31, and it is not
  "not found" (D75).** Over all 867 photographs in the owner's three real boxes — box 1 (133
  Riftbound), box 2 (543 Pokemon), box 3 (191 Riftbound) — `detect_card` returned a box for
  **every one and refused none**, and **nine of them were wrong**: a card-shaped rectangle
  inside the card, the rules-text panel or the artwork frame, returned with a card's aspect
  and a passing border score. The 53/53 above is a rate at which the card is FOUND and says
  nothing about this, because a wrong box and a right one both count as found.

  On the padded rectangle that is actually cut, the two populations are `0.300-0.988` of the
  frame with `0.438-0.995` of its detail for the 858 correct, and `0.068-0.270` with
  `0.152-0.435` for the nine wrong. Neither column separates them alone — box 1's smallest
  correct crop sits exactly on 0.300 and the detail gap is under a percent — so
  `identify/images.py:crop_refusal` is an AND of both, and it refuses all nine and none of
  the 858. The check here asserts its SHAPE on a synthetic inner rectangle, not that rate;
  the rate is one rig on one day and is recorded in the source beside the constants.
