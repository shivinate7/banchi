# The Banchi mark

**Status: DIRECTION LOCKED, NOT BUILT.** `docs/specs/logo/banchi-icon.svg` is the chosen icon.
Nothing under `app/` has been touched: `app/src/kit/index.tsx:258` (`Logo`) and
`app/public/favicon.svg` still hold the placeholder, a geometric **B** in a rounded square with a
vermilion dot.

## 1. What is locked

**Silver chrome.** A quintic-superellipse tile in cool near-black, two chrome brackets holding a
slate card with a blue-steel holographic surface.

| | |
| --- | --- |
| Tile | `#1E232B` → `#080B0F`, plus a white sheen at 8% over the top third |
| Brackets | chrome gradient `#FFFFFF` → `#B8C8D8` → `#F2F8FF` → `#8FA4B8` at 120° |
| Card | `#5A6E80` under a blue-steel prism `#E4EEF8 #B0C8E0 #7F9FC0 #F2F8FF #6086AC` at 110° |
| Holo | `feTurbulence` fractal noise, base frequency `0.035 0.09`, four octaves, **seed 29**, displaced by 26, at 72% |

**The seed is part of the design.** The holo is procedural, so a different seed is a different
drawing. 29 is the roll that was chosen.

## 2. The geometry is derived, not drawn

Every number falls out of a published rule. Nothing here was nudged by eye.

| step | value | source |
| --- | --- | --- |
| Tile corner radius | 22.37% of width, quintic superellipse | Apple's icon shape |
| Largest inscribed square | 100 · 2^(−1/5) = 87.055 | the biggest square inside that superellipse |
| Mark box | 87.055 × 20/24 × 0.92 = **66.742** | Material live area, at 92% for air |
| Unit *u* | B / 12 = **5.562** | Material's 2-of-24 stroke — sets stroke **and** gap |
| Card | **31.78 × 44.49**, ratio 5:7 | a 63 × 88 mm trading card |
| Card radius | 1.602 (5.04% of width) | 3.175 mm on 63 mm |
| Bracket radius | card + e = **9.945** | the concentric rule, r = R − p |
| Arms | one third of the expanded rect | — |

**Optical centering needs no fudge**: brackets on opposite corners plus a centred card give the
mark 180° rotational symmetry, so its centroid is already the tile's centre.

## 3. What was tried and rejected

Recorded so none of it is re-proposed. Two whole directions and roughly a hundred and eighty
drawings.

**Flat monochrome maker's marks.** A tray read as a bar chart; a segmented ring read as a life
preserver; a chamfered slab with knockouts read as a floppy disk. Only a framed plate had usable
bones.

**Rendered graphite objects.** Rejected by the owner as *too formal, too monotone, too
AI-generated* — each defect traceable to a line of the brief that produced it. **The cause: the
register was taken from the codebase and imposed on the brand.** CLAUDE.md is dense and rigorous,
so the mark was made dense and rigorous. The product sells trading cards, which is a hobby.

**Pastel pixel art.** Five passes. Killed by two facts: nine cells cannot work at 32px, and a
pastel tile under pastel content has no figure-ground separation at any size.

**Method note.** Every interview question in this file's history was written with its own options,
so the answer space belonged to whoever wrote them. Both real turning points — *pastel bit style* and
*make it shiny* — came from the owner typing past the options. **Offer renders to react to, not
menus to pick from.**

## 4. What the sheets in `logo/` show

- `pass-gold-silver-on-black.png` — nine gold prisms, then patterns, card bases, seeds, brackets
  and ground depths; then seven silvers with the same sweeps. **Gold is the stronger family**
  because it has a hue for the turbulence to modulate; silver is a lightness ramp and flattens.
  Silver was chosen anyway, on the owner's call.
- `pass-brackets.png` — seven sweeps on the bracket alone. The findings that bind: chroma has a
  ceiling around .09 before the bracket competes with the card; below L .80 on a dark ground the
  bracket stops framing; **a dark bracket cannot work on this tile at all**; and a bracket with
  its own gradient reads as metal catching the same light as the card, which is why chrome won.

## 5. Two artifacts, and only one exists

| | the tile | the bare mark |
| --- | --- | --- |
| Where | favicon, home screen, dock, avatar | sidebar, print, one color, on a page |
| What | this SVG | the same geometry cropped to its own bounding box, **54.04 × 66.74** |
| Status | **locked** | **not made** |

The bare mark needs one value swapped for dark grounds — the bracket goes light — and it loses
the holo entirely in one flat ink. That is normal for a logo system, and it means the thing
stamped on a packing slip is a flatter object than the thing in the dock.

## 6. Still open

- **The bare mark**, per section 5.
- **A drawn wordmark.** "Banchi" is set in Manrope today. It should follow the icon, not run
  beside it.
- **Lockup rules** — clear space, minimum size.
- **Whether the sidebar takes the tile or the bare mark.** Decide by looking at the rail.
- **How the SVG ships.** It uses `feTurbulence`, which renders in browsers but can be dropped by
  a favicon pipeline that rasterizes oddly. The shipped icon may need to be exported bitmaps per
  size rather than a live SVG.
