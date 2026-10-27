## DEBT92 — the tile lead check fails a proper noun after the first word

**What.** The sentence check on a tile's lead fails a capital after the first word. `sentenceProblems` in `app/tests/copyRules.ts` grades `.bn-tile-lead` as a sentence. A proper noun later in the lead, such as "Sent to Pokemon", reads as a casing error.

- **Result:** a correct lead that names a game or a store fails the copy sweep. No lead holds one today.
- **Not fixed because** no lead needs it yet, and `copy-casing-allow.json` can excuse one when it comes. `tests/unit/copy-rules.unit.ts` also has no case for `sentenceProblems`, so the sweep is its only guard.
- **Closes when** `sentenceProblems` knows the product's proper nouns and a unit case pins it true and false.
- **Points to** D277 (Pricing lists all rows; the slim bar's three tiles), D196 (no user-visible string names a mechanism).

**Outcome at risk.** A right sentence on screen fails a check, and the fix becomes an allow-list entry rather than a rule.
