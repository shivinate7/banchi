# Known gaps, deliberately unfixed

Each file here is one finding. A finding is recorded and not repaired. It says what is wrong,
what it costs, and why nobody fixed it. A green `make docs-audit` means only that the checks
which exist have passed. These entries name what those checks do not cover.

This is not a backlog to burn down on sight. An entry leaves when someone argues that it
should, or when its gap closes. A closed entry is deleted, and history lives in version
control. A number is never reused, so the gaps in the sequence are deleted entries: 5, 10, 12,
13, 15, 17, 18, 21, 24, 28, 29, 35, 36, 37, 42, 45, 47, 49, 51, 52, 53, 54, 55, 56, 57, 78, 79, 80 and 81.

## How to find one

- **By id.** A file is named `<zero-padded number>-<slug>.md`, and a glob sorts it into
  corpus order. Entry 11 is `011-...`. Cite an entry as `DEBT<n>`, never by path and never as
  a bare `§<n>`.
- **By the index below.** `make docs-audit` reconciles it against the files, in both
  directions.

## How to add one

A branch writes `DEBT-<slug>.md` under this folder. The file starts with
`## DEBT-<slug> — <title>`, and the branch cites it as `DEBT-<slug>`. `make merge` claims the
number, renames the file, rewrites every citation, and rewrites the index. A branch never picks
its own number.

## Index

```
DEBT1 The reverse direction: two checks walk docs→code and never back
DEBT2 The map's reach
DEBT3 The claim chain
DEBT4 Criteria and evidence: four ways a row goes quiet
DEBT6 T7 leaves two capture-server facts unchecked
DEBT7 The preview crops the card, and the one check that looks at a photo cannot see it
DEBT8 Recorded and correctly unfixed
DEBT9 The sigil check matches text, so a renamed local walks past it
DEBT11 A writer parked on the store lock still holds a request slot, and the heavy lock-free reads wait behind it
DEBT14 A pooled card reaches the pricing table and the box walk, and `located` suppresses the label everywhere and the photograph nowhere
DEBT16 The browser fleet is locked and the rest of the load is not, and only one of those was measured
DEBT19 The revert guard is exact, and three shapes of reversal walk past it
DEBT20 Two liveness oracles read a pid, and a recycled one lies to both
DEBT22 A control shrunk inside its own sticky bar is invisible to the thumb-floor sweep
DEBT23 A sale fixture that moves after the press is only wrong sometimes, so no check can flag it
DEBT25 A cited number still resolves when it is the wrong one, and no check can read what a sentence is about
DEBT26 The Intelligent Mail barcode encoder is written, correct against the Postal Service's own examples, and parked on a branch
DEBT27 `Fulfillment.tsx`'s store-wide `GET /inventory` browse is argued and left
DEBT30 The copies panel flash guard is shelved, on the owner's own word
DEBT31 The path guard never reads code, so a decision cited by path in a comment goes unchecked
DEBT32 The archive sweep stays a press, and the owner intends to schedule it eventually
DEBT33 An answered queue entry can never resurface, even when it is wrong
DEBT34 Categories and products never expire, on a membership claim this store cannot re-check on its own
DEBT39 the public demo refuses every box map move
DEBT40 a divider save can move a divider past departed records
DEBT41 Pricing never offers "Make this the rule"
DEBT43 the merge-speed guard counts SQLite ticks only, and a pure-Python loop is invisible to it
DEBT44 pokemontcg.io is deprecated (ends 2027-03-01), and `pipeline/stockimages.py` does not call it today
DEBT46 a search with a typo finds nothing, and no near match is offered
DEBT48 code-side mechanization left open
DEBT50 git and gh CLI traps hit from this checkout
DEBT58 the Lane H palette record is on a branch, not in main
DEBT59 an unreadable live claim has no way out on screen
DEBT60 the demo builds with Hide unpullable forced off
DEBT61 eight build proposals are still open
DEBT62 the demo photos are about 180 MB of plain git, and the owner wants them in Git LFS
DEBT63 T1 has never been compared with TCGplayer Scan & Identify
DEBT64 the collector number is not cross-checked against the local catalog
DEBT65 the number-corner crop is sent only on a retry
DEBT66 no perceptual-hash cross-check on identification
DEBT67 capture photographs exist in one place
DEBT68 the posted-price history has no screen
DEBT69 prices are not refreshed on a schedule, and nothing says which SKUs moved
DEBT70 realized prices inform no listing rule
DEBT71 the value of the set hint is asserted, not measured
DEBT72 PKMNVAULT, Supabase and eBay are unbuilt
DEBT73 the Mac dock icon has no drop shadow, and none was tried
DEBT74 the mark's four HELD base parameters were never compared
DEBT75 the first ask for a cold catalog group answers nothing
DEBT76 the walk's card sheet on a phone has no Mark sold
DEBT77 every phone-width spec is off
DEBT82 The Fulfiller's boxes slide once when the Pick list lands
```
