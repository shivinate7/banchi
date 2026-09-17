## D75 — A detector that cannot say "wrong" is asked a second question, and the crop is refused rather than trusted, and the shape correction reaches both crop paths

**`geometry.detect_card` answers "not found" honestly and has no way to answer "found the wrong thing", so the crop path asks the frame instead: a crop under 30% of it that keeps under half its detail is not cut, and the whole frame is sent.** Ruled 2026-08-31, from the owner's own screenshot of `#/runs` drawing a crop rectangle over a card's rules-text panel and reporting it as the payload.

**Numbered D75 because D74 was taken while this branch was open** — `origin/main` carries "a document is checked as a document" at that number, merged 2026-08-30. D72's rule applies to a renumbering, and this is not one: nothing was published at D74 here to move.

### What was measured

Not a guess about the detector, and not a tuned constant. `detect_card` was run over **all 867 photographs in the owner's three real boxes** — box 1 (133 Riftbound), box 2 (543 Pokemon), box 3 (191 Riftbound) — with the crop rectangle `identify/images.py:crop_rect` would cut from each.

**It returned a box for every one of the 867 and refused none.** Nine were wrong, all in box 3, and every one of them the same shape: a card-shaped rectangle **inside** the card — the rules-text panel, the artwork frame — carrying a card's aspect, a passing border score and nothing to distinguish it from a hit. Two of the nine are the frames in the owner's screenshots.

The probe that decided the design is that on those nine **the whole card is not among the candidate rectangles at all**. The largest candidate on `box3/0024` is 0.21 of the frame against a card filling roughly half of it: those cards sit in a stand with a stack behind them, so the card's outer border is against another card rather than against a ground, and the strongest four straight edges in the frame are the ones printed on it. **This is therefore a refusal and not a detector fix.** Re-scoring, preferring the outermost candidate, or widening the peak search cannot choose a rectangle that was never a candidate.

### Why two measurements and not one number

On the padded rectangle that is actually cut:

| | area of the frame | detail the crop keeps |
|---|---|---|
| 858 correct | 0.300 – 0.988 | 0.438 – 0.995 |
| 9 wrong | 0.068 – 0.270 | 0.152 – 0.435 |

**Neither column separates them on its own.** On area the gap is 0.270 to 0.300, and box 1's smallest correct crop sits **exactly** on 0.300 — box 1 is shot further back and its correct crops are genuinely small, the same size as box 3's wrong ones. On detail the gap is 0.435 to 0.438, under a percent. A threshold in either gap is a number fitted to 867 frames from one rig, and this repo has a name for that: a margin that is exactly sufficient on the worst frame measured is not a margin.

So the rule is an **AND**, and each leg covers the other's boundary. Over the measured set it refuses all 9 wrong crops and **none** of the 858 correct ones, and the legs are doing separate work — 27 correct crops fall under the detail line and are kept by the area leg.

**The second axis is detail rather than a tighter aspect gate, because detail is what is unmistakably true of the failure.** The rest of the card is still outside the crop: sharp, structured, and thrown away. A crop of the subject keeps the subject. It is a ratio over the same absolute-luminance-gradient signal `geometry/detect.py`'s border search is built on, so the guard and the detector read the same picture, and a dark backdrop or a busy tray cancels out of the numerator and denominator together.

**A plain floor was tried and taken out**, and it is recorded because it is the guard a person reaches for first. "Refuse anything under 10% of the frame, whatever else is true" catches nothing the AND does not — every one of the nine is under both lines — and it has a case where it is simply wrong: T6's own `_scene(scale=0.55)` is a small card correctly found on a plain mat, 8% of the frame, keeping 94% of its detail. A second rule that adds no catch and subtracts a correct crop is not redundancy.

### Erring toward refusal is the cheap direction

This is what lets a threshold sit near a boundary at all, and it is `geometry/detect.py`'s own argument read one register up. **A refusal sends the whole frame**: more image tokens, the reading every run made before `--crop` existed, and a correct answer. **A false accept sends a picture with the collector number cut out of it** and gets a confident answer about nothing — the failure D23 says no confidence threshold catches, and the one `card_rect`'s aspect correction was written for after box 2 sent 544 cards under a flat pad and 38 came back with no number at all.

### Where it lives, and what it is not allowed to be

`identify/images.py:crop_refusal`, called from `prepare` — **the one place the bytes are made** — so nothing downstream can hold a box that was declined and cut with it anyway. `card_crop` and `crop_rect` are untouched: they remain the pure cut and the pure rectangle, and T6's identity between them still holds.

**It returns a sentence, never a flag**, because every caller has to say this out loud and none of them can explain a true-or-false:

- `Prepared.crop_refused` carries it, so a run cannot report itself as having cropped while sending whole frames.
- The preflight prints the count **apart from** `no card found` and then the reasons themselves, before any money. The two are not the same fact: nothing found is a photograph to look at, and a box refused is a detector that answered confidently and wrongly.
- `#/runs` draws no rectangle and shows the sentence under the picture, which is the same treatment `band_absent` gets and for the same reason — the pipeline's words, not the screen's summary of them.
- The closing report lists them under `unfit crop`, kept apart from `not detected`.

**The crop-retry path gets the same guard, for a sharper reason.** A retry happens after a reading came back malformed or unsure, and its bands are cut out of this rectangle — so a box that is really the rules-text panel sends an enlarged photograph of rules text and calls it the collector number. §4.5 rung 3 sends that card to a human instead.

### What this does not establish

**One rig, one day, 867 frames.** What is established is that these two numbers separate these two populations. What is **not** established is a rate at which detection goes wrong: nine is nine of the owner's own boxes, not a percentage of anything, and every one of them is Riftbound in a stand with a stack behind it. Read it exactly the way `docs/GATES.md` says to read the border search's 53/53 — that number is a rate at which the card is FOUND, and a wrong box and a right one both count as found, which is why it could stand for eight days beside this.

### Amended the same day: the correction was on one crop path and not the other

**A second defect on the same path, found by another session tracing how `identify` recovers a badly-cropped card, and routed here by the owner.** `card_rect`'s aspect correction — restore the height a real card of this width would have, because the border search comes back systematically short at the number end — was applied to the primary image `--crop` sends and to the run panel's band preview, and **not** to `geometry/crop.py:registered_card`, out of which every crop-retry band is cut as a fraction.

**It was reported as read off the code and not observed. It is observed now.** Over box 2's 543 photographs the registered card's aspect ran to a median of **0.789** against a real card's 0.716 — the same 0.790 median `card_rect` already recorded — which puts `NUMBER_BAND`'s bottom edge at **0.953 of a card-shaped rectangle at the median and 0.935 at worst**. On **`box2/0340.jpg`**, whose box bottom sits at 0.756 of the frame where its neighbors sit at 0.805, the number band contained the weakness/resistance/retreat row and **no collector number at all**. That is the last automatic rung enlarging the wrong strip to 600px and answering confidently — the `0342` failure mode again, reached from the retry rather than from the first pass.

**The fix is one computation, not a second copy**, which is the rule `crop_rect`'s own docstring states. The correction moved down into `geometry.corrected_bounds` with its whole argument, because `geometry/` may not import `identify/` and that layering is exactly why the retry path could not reach it. `identify/images.py:card_rect` is now a delegate and keeps its name: several entries cite it, and renaming it to save one line would move a docstring they point at.

**Clamped to the canvas in `registered_card`**, because the correction only grows and a card near the frame's edge would otherwise be cut against nothing and padded black — a black bar pretending to be cardboard moves every band below it.

**What the fix does not do.** It is **symmetric**, so a box short only at the bottom — which `box2/0340.jpg` is — recovers half its deficit and no more. `CardBox` reports no per-edge confidence, and attributing the whole correction downward would be inventing a fact; the entry this amends is the one that already says so. 0340's number went from outside the band to inside it at the band's edge, and sixteen box-2 bands sampled evenly across the run all contain their number after the change.

**BUILT**: `geometry.corrected_bounds` and both callers through it, the aspect wired from the registry to `crop_regions`, and T6's regression case — which is a real one: a box 10% short at the bottom holds 0.088 of the number box in its band before the fix, under T6's 0.10 floor, and 0.157 after.

**BUILT**: `crop_refusal` and `detail_share`, the guard inside `prepare`, the guard on the crop-retry path, the two figures the preflight prints and its reasons, the closing report's `unfit crop`, `crop_refused` on the preview wire, and the sentence rendered on `#/runs`. **RECORDED**: this entry, the two populations in `identify/images.py` beside the constants, and the gates corpus's `T6` entry. **NEITHER**: any change to `geometry/detect.py`, a rate for how often it is wrong, and a second detection method for a card whose border is against another card — which is the only thing that would actually recover those nine crops rather than decline them.

**What would reopen this: a rig whose correct crops are genuinely small.** Both numbers are fractions of the frame, and a camera moved back far enough would put correct crops under both lines and send every card whole. That costs money rather than accuracy, and the figure the preflight prints is what would say so — a nonzero `box unfit to crop to` on a box where the crops look right is this entry asking to be re-measured.

---
