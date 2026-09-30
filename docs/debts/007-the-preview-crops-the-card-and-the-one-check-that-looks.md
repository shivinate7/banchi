## 7 — The preview crops the card, and the one check that looks at a photo cannot see it

The `#/inventory` preview, the sell confirmation and the Fulfiller's pull preview clip the photograph to the frame instead of cropping to the card (D125 keeps the crop on `#/` and on `#/pricing`'s row thumbnails only, through `POST /pipeline/crop-preview`, `kit/index.tsx:cropStyle` and `.bn-crop`). Measured: 48 of 48 sampled box-3 frames clipped, worst 333px off the bottom, and 68px off the card's bottom edge on the Fulfiller's screen at the worst geometry.

`make design-check` stays green because `docs/DESIGN.md`'s floor is on painted size (`>= 320px` on the short edge). Under `cover` the frame fills the box by construction, so a floor on size is not a floor on content.

The crop is only as good as its reading. D125's client-side refusal (a rectangle overrunning its frame by more than a sixth is not believed, and every caller falls back to the plain photograph) rests on three good readings and one bad one. The first real rig photograph that trips it should replace that threshold.

**Outcome at risk.** A person confirms a sale or a pull without seeing the card's bottom edge, where its number and rarity sit.

**Closes when.** A Playwright row asks whether the card is inside what was drawn (it needs `detect_card`, which is slower than the suite and can refuse), or the crop lands invisibly (D125 costs the options).
