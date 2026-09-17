### Box 2 — 544 cards, and the first ground truth about finish detection. 2026-08-24

Not a gate. The largest run this project has done, and the first with the owner confirming
what the cards actually are.

**Identification: 544/544, zero errored.** 539 high confidence, 5 medium, none low after one
3-card retry. 114 distinct names. Cropped to the detected card at max-edge 1200. Billed
1,315,698 input and 20,698 output tokens — **$0.71**, against a $0.62 estimate; `SYSTEM_TOKENS`
was 500 where the real turn is ~1,000, and is now the measured figure.

**Finish detection is wrong on 42% of a box whose truth is known.** The owner, after the run:
*"all of the cards provided in box 2 were normal by the way no reverse holo / foils etc"*.
Every capture carried the claim `normal`, and every card was in fact normal. Detection said:

| detected | cards | |
|---|---|---|
| `normal` | 208 | correct |
| `unknown` | 106 | honest non-answer |
| `holo` | 151 | **wrong** |
| `reverse_holo` | 79 | **wrong** |

**230 of 544 wrong — 42%.** Gate B measured 30% on 53 cards and called it systematic sheen
under the rig's lighting; this is the same finding at ten times the sample with the owner
supplying ground truth rather than a per-card ruling.

**It is not noise, and the A/B proves something worse than bias.** Forty of these cards were
also identified at max-edge 900 in a separate run: **19 of the 40 disagreed with themselves on
`finish` between two resolutions of the same photograph**. A signal that changes when the
downscale changes is not measuring foil.

**What it costs is D3 rung 3's whole purpose.** Rung 3 cross-checks the capture toggle against
detection, and a disagreement routes to review. On this box that is 230 cards queued against a
claim that was right every time. D29's group answer cannot absorb them — it requires one shared
candidate, and 230 cards are 230 different catalog rows. This is the paragraph to read before
joining a box shot on this rig.

**The remedy the owner chose, the same day: `join --bypass`** (D3, amended). Rung 3 is
switched off for a run wherever a finish claim exists, so the claim resolves the card and the
disagreement is never raised. Measured against this box with `join --dry-run`, which walks the
ladder twice and writes nothing: **256 cards would queue, 209 of them clear by the claim, and
47 remain** — all `no_catalog_row`, and all of them the crop-damaged reads (38 blank numbers,
9 wrong Pokedex-style numbers) that the flat-pad bug produced before it was fixed. Those 47
have no claim to fall back on, which is exactly where the flag stops.
