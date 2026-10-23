## DEBT-empty-slot-check-decodes-all — the empty-slot check decodes every uncached photo at full size

**The empty-slot check decodes each photograph that has no cached answer, at full size, before the quote is printed.** `cli/cmd_identify.run` calls the check in `identify/match.py` (`empty_slot`) on each of them. The check runs before the dry-run quote can skip it, so a dry run pays for the whole pass. On 2,500 new cards the pass takes 100 to 300 s.

- **Result:** a dry run over a large new box waits for minutes before it prints a quote. The screen's quote waits with it.
- **Not fixed because** the check is correct and catches the empty slots it was built for. Only its cost is wrong.
- **Closes when** the dry run no longer decodes each uncached photograph at full size. A reduced decode, or no check in the dry run, would do. A measured dry run over 2,500 uncached photographs takes a few seconds. The check keeps its result on the stored photographs, with no false catch.
- **Points to** D1 (capture is dumb, batch identifies later). The check is a free step that runs before any paid send.

**Note: card 2/95.** Haiku named a black photograph "Mewtwo ex" at high confidence. The owner says the card was not a Mewtwo. The dark check before any paid send now catches this class: a dark photograph is queued as an empty slot and is not sent.

**Outcome at risk.** The owner waits minutes for a quote on every large new box, and may press without one.
