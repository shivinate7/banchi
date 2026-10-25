## DEBT98 — a fully answered selection reads "The free read is not set up"

**A selection whose cards all have answers draws "The free read is not set up, so every card goes to the second look." on the runs composer, with the index ready.** With no card left to send, `cli/cmd_identify.run` does not measure the free read. It prints "0 of 0" with its no-index word, `certain`. `app/src/RunsComposer.tsx` reads that word as "no index" and draws the sentence.

- **Result:** after the owner answers a whole selection, the quote says the free read is broken. It is not. No card is left to read.
- **Not fixed because** the text is wrong and no money or card is at risk: a selection with nothing to send sends nothing.
- **Closes when** a selection with nothing to send draws no setup sentence, and a case in `app/tests/run-panel.spec.ts` shows that, red on the old screen.
- **Points to** the free reader's spec, `docs/specs/identify-engine-pick.md`.

**Outcome at risk.** The owner reads a false setup problem about a ready free reader, and may distrust the quote or press Prepare for nothing.
