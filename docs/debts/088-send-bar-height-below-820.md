## DEBT88 — the sticky send bar's height below an 820 column is unmeasured

**The send bar's height below an 820 column is unmeasured.** At about 700 wide, the tiles wrap to 2+1, so the sticky bar grows by one tile row. Its height is unmeasured.

- **Result:** a taller sticky bar stays on screen at about 700 wide. No measure says how much of the list it leaves.
- **Not fixed because** the phone-width specs are off (DEBT77, every phone-width spec is off). No spec runs the layout below 820, so the height has no check.
- **Closes when** a spec measures the bar's height below 820 at each width the screen ships in. Or DEBT77 closes, and the phone-width specs run over the bar.
- **Points to** D277 (Pricing lists all rows; the slim bar's three tiles), DEBT77 (every phone-width spec is off).

**Outcome at risk.** A taller sticky bar can crowd the list on a narrow screen, and no spec sees its height.
