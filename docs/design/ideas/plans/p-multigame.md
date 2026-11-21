# p-multigame

**Direction 1**

**Name:** Game profile with a calibration run

**The idea:** Put everything that is specific to one game into one profile: card size, card back, how set numbers are written, finish kinds, languages, rarity names and the marketplace category. A new game goes live only after a calibration stack of about 50 cards passes. The run scores the profile on how many cards it names correctly, how many go to review, what each card costs to identify, and how many get a price.

**Who it helps:** The owner. Adding a game becomes "fill in a profile and feed 50 cards", not a code fork.

**Why now:** With one game, the game-specific parts are still easy to find. Once a second game is added with if-branches, every later game costs twice the work.

**Rough shape:**
- The owner picks "Add game", fills the profile, and feeds a mixed calibration stack.
- The rig reads the card back for free, before the paid identify step. This sorts game and language, so a wrong-game card never costs a paid read.
- A report card shows auto-named %, review %, cost per card and price coverage, each against a pass bar.
- The profile goes live only when every bar passes. Until then its cards wait in the review queue.

**Risk:** A profile designed from one game takes that game's shape and breaks on the third game.

**Direction 2**

**Name:** Trial shelf with a payback meter

**The idea:** Choose the second game with data, not taste. List a small lot (about 300 cards) of each candidate game from one trial section, and track each one's net return per box section per month. The test: does it beat the weakest section of the current game?

**Who it helps:** The owner. It answers "which game second" and "does it pay" with one number.

**Why now:** Box space (6 boxes) and Fulfiller minutes are the scarce resources, and capital is still small. A wrong second game takes shelves and attention that the current game earns on.

**Rough shape:**
- Three kinds of candidate:
  - The current game in a second language: same rig, sizes and catalog shape.
  - A standard-size game with clean set numbering.
  - The biggest single market, which has the most printing variants and so the most identify mistakes.
- Each candidate gets one line: sell-through, margin after fees and identify cost, Fulfiller minutes per order, and review-queue rate.
- A candidate graduates when its net return beats the weakest current section for two cycles. Otherwise it is sold off as a lot and closed.

**Risk:** At a median of 3 orders a day, 300 cards make a thin sample. Show the spread, not just the average.

**Direction 3**

**Name:** Mixed boxes, picking that ignores the game

**The idea:** The rig already knows where each card is, so a box does not need to be one game. New-game cards go into sections with free space, and the pick walk runs in box, section and position order whatever the game. Each pick shows the stored photo with a colour band for its game, plus a pack note when the size or sleeve differs.

**Who it helps:** The Fulfiller. Their walk and their screen look the same whether the store sells one game or three.

**Why now:** Boxes are unevenly full (545 to 732 cards). Giving a new game its own boxes adds walking and half-empty boxes at the stage where every box counts.

**Rough shape:**
- The shelving step puts the new lot into the free gaps and prints new divider labels in the game's colour.
- The pick list shows the photo, a colour band and a size note ("small card: small sleeve").
- Off-size games get their own sections, never mixed inside one section.
- A printable box map lists each section's contents, as the fallback when the Mac is down.

**Risk:** Mixed boxes break the owner's by-set mental model, so a manual audit or restock without the system gets harder.

**Bet:** Build the trial shelf first. It decides whether a second game pays, and which one, before money goes into the profile system. Its two real candidate games then shape the profile from evidence, not from guesses.
