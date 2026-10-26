## DEBT99 — the empty-slot check still pays for an entropy decode of every uncached photo

**The empty-slot check decodes each photograph that has no cached answer before the dry-run quote is printed.** `cli/cmd_identify.run` calls the check in `identify/match.py` (`empty_slot`) on each of them. The check runs before the dry-run quote can skip it, so a dry run pays for the whole pass. `luminance_p99` now decodes a JPEG at half scale (a JPEG draft), no longer at full size. Half scale is the finest reduction that keeps a dark card with thin white lines from counting as an empty slot: 1/4 and 1/8 fail it.

- **Result:** a dry run over a large new box still waits for the decode pass before it prints a quote. The pass is shorter than it was, not short.
- **Not fixed because** the draft alone does not reach the target. On a synthetic 12 MP JPEG a decode takes 67 ms at full size and 36 ms at half scale. Entropy decoding is the floor, and a draft cannot go below it. At that rate 2,500 photographs take about 90 s. This is unmeasured on real rig photographs.
- **Closes when** a measured dry run over 2,500 uncached photographs takes a few seconds. The remaining remedy is to cache the result per photograph, so each photograph is decoded once and never again. The check keeps its result on the stored photographs, with no false catch.
- **Points to** D1 (capture is dumb, batch identifies later). The check is a free step that runs before any paid send.

**Note: card 2/95.** Haiku named a black photograph "Mewtwo ex" at high confidence. The owner says the card was not a Mewtwo. The dark check before any paid send now catches this class: a dark photograph is queued as an empty slot and is not sent.

**Outcome at risk.** The owner waits minutes for a quote on every large new box, and may press without one.
