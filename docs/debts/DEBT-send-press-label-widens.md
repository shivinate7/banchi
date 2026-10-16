## DEBT-send-press-label-widens — the send press widens when the worklist lands

**The send press's label grows when the worklist lands.** The pending bar's press reads "Send to TCGplayer". The loaded press reads "Send All N SKUs to TCGplayer", and it is longer with price changes or live moves. `.send-press` is `flex: 0 1 auto`.

- **Result:** Download and Refresh shift right at landing, and a long label can wrap them to a new line. D313 forbids a move the person did not make. This is read from the code. It is unmeasured.
- **Not fixed because** the label's count is not known until the worklist lands.
- **Closes when** the press holds one width from first paint (for example, a width reserved for its longest label), and a test compares the doors' positions pending and loaded.
- **Points to** D277 (Pricing lists all rows; the slim bar's three tiles), D313 (nothing on screen moves unless the person moved it).

**Outcome at risk.** The doors move beside the person's pointer as the screen loads, and no check measures them.
