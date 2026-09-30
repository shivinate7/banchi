## 1 — The reverse direction: two checks walk docs→code and never back

Two audit rows prove that what is published is consistent. Neither can see a real thing that was never published.

- **`tested_by reach`.** A claim proves only that the cited test's import graph contains the top-level package the entry lives in. It does not prove the test imports the module or that any assertion depends on it. `from pipeline import join` satisfies every entry in `pipeline/` at once.
- **`governed_by`.** The map may not know less than the code's own citations, and may say more. An entry can list a decision its file does not implement. Telling which citations count needs a guess, and D16 keeps a guess off a blocking row.

**Outcome at risk.** A green row reads as coverage. A module a test reaches without covering, or a decision listed without being implemented, passes.

**Closes when.** A decision rules that "a test imports it" does or does not mean "a test covers it", and settles whether `governed_by` may be checked from the map side.
