# p-trust-further

# Every Upload Has a Reverse: worked out

## 1. Core loop, from the owner's view
**Before an upload.** The owner builds the listing file as they do today. Before they can download it, a check screen compares it with the last file they uploaded. The screen holds back the file until each flagged row has a choice made on it. The owner downloads the file, uploads it on the marketplace, and comes back to tap "uploaded". The system cannot see the upload itself, so it only learns of it from that tap.
**After an upload.** The version is saved with its time and every row that changed. When the next orders export comes in, it is checked against that version. A sale at less than half the market price, at a price this upload set, raises a single alert that names the version.
**The night they need the reverse.** The owner opens the upload history, picks the bad upload, and taps "make reverse". The system builds a file that puts back the old price only for cards whose price is still the one that upload set. That reverse file then goes through the same check as any other upload. The owner uploads it, taps "uploaded", and the reverse is recorded as an upload in its own right.

## 2. States a screen must show
1. **Clean upload:** "312 changes, none look wrong", then a summary (180 up, 132 down, middle change 4%) and one download button.
2. **Upload with a few outliers:** those cards first, sorted by dollars at risk. Each row shows the old price, the new price, the market price and recent sales. Each row has three choices: keep new, use old, use market. The download unlocks once every row has a choice.
3. **High-value price cut:** a card above the value line, dropping by more than a set share, gets its own confirm. The owner retypes the new price. It cannot be included in a "keep all", and it always sits at the top.
4. **Upload history:** one row per version, showing time, number of changes, flags kept, sold since, and state (downloaded / uploaded / reversed by / reverse of).
5. **Reverse where some cards sold since:** "restores 309 of 312". It lists 3 cards that sold at the bad price, each with the gap to market. It lists 0 cards changed by a later upload; those are left alone and named, never overwritten.
6. **Reverse of a reverse:** this is a plain reverse whose source happens to be a reverse. Each row says "reverse of reverse of upload from [time]". It re-applies the original changes, and the bad prices are flagged again unless the owner kept them on purpose the first time.

## 3. Which outliers it flags, and how it avoids crying wolf
Flags, each set off by dollars at risk and never by percent alone:
- **Decimal slip:** the new price is the old price times or divided by 10 or 100.
- **Under market:** the new price is below half the market price, and the gap is above a dollar floor, so a $0.10 card at $0.04 is quiet.
- **Slab priced like a raw card:** a graded card set below the raw card's market price.
- **Loss after fees:** the price nets below zero once marketplace fees are taken out.
- **Wrong column:** most of the file changes at once. This shows as one flag on the whole file, not 3,000 flags.

Holding down false alarms:
- Raises are never flagged. The worst case is that a card does not sell.
- A kept outlier is remembered: the same card at the same price is not flagged again until the market moves.
- A card with no market data is a count line, not a warning.
- The screen shows at most 10 flags, ranked by dollars at risk; the rest sit behind a count.
- Each rule tracks how often the owner keeps what it flagged. A rule kept more than 4 times in 5 gets its threshold raised.

## 4. Smallest first version worth shipping
- Compare against the last file downloaded, with the "uploaded" tap.
- Three rules only: decimal slip, under market, and the high-value cut confirm.
- Keep every file. The history is a plain list.
- "Make reverse" leaves out cards sold since (taken from the latest orders export) and cards changed later.
- Reverse of a reverse comes free because a reverse is an ordinary upload. The after-upload alert, slab and fee rules, and memory of kept outliers wait for a later version.

## 5. One measure that says it worked
Count sales at under half market price whose price came from an upload and was never flagged and kept. The target is zero a month. Read it from each orders export.

## 6. Questions only the owner can answer
1. Does a live price ever change outside these files, for example by an edit on the marketplace site or an automatic repricing rule? If yes, the comparison must run against a listings export, not against the last file.
2. When a bad price has already sold, do you honor the sale or cancel the order? If you cancel, the reverse screen should list those orders. Cancelling may cost you seller standing; I don't know the marketplace's rule.
3. What dollar value makes a card "high value" for the separate confirm, and does every slab count no matter its price?
