# p-local-further

# Away Case: the deeper version

The rule underneath it all: **once a card leaves its slot, Banchi always knows where it is, and each channel sees that card as either for sale or not.**

## 1. The core loop
- **Thursday, packing.** The owner picks what goes: by set, by price, the slabs, or a decklist. Banchi gives one pull list in box and section order. Each card the Fulfiller pulls is checked off into a case slot, such as "Case A, page 3, pocket 7." The owner chooses when the online listings come down (section 3).
- **Saturday, the table.** On the iPad, the case is a grid of photos laid out like the binder. Search or scan finds a card's pocket in seconds.
- **A sale.** They tap the card, then Sold, and enter the price paid. The card is out of stock everywhere, and a receipt line is written with time, price and cash or card.
- **An online order for a case card.** It lands on the Fulfiller's pick list as "In Away Case A, page 3, with the owner." The owner's phone shows it with one choice: hold it for shipping, or say it already sold at the table.
- **Sunday, coming home.** "Come home" lists every unsold card in its old box, section and slot. Banchi also writes the listing file that puts the unsold cards back online. The trip closes only when every card is accounted for: sold, put back, held for an order, or missing.

## 2. The states
1. **Packing list.** The pull list in walking order, with a running count and total value. A card that cannot be found in its slot is marked Not found and stays home. Nothing is dropped without being named.
2. **Table view.** A binder-shaped grid with a price on each card. It works offline and catches up when the network returns, because a convention hall's network may be poor.
3. **Sale at the table.** One card or several. The price is pre-filled and can be changed. Undo works until the trip closes. If they sell a card they think came from the case but it is not on the list, Banchi flags it at once and does not guess.
4. **Online order for a case card.** A banner on both the owner's and the Fulfiller's screens. Banchi records the owner's choice: hold for shipping, or already sold. It never decides by itself which channel gets the card.
5. **Come-home put-back list.** Sorted by box and section so the Fulfiller walks each box once. Each card shows a thumbnail and its exact slot. Putting a card back restores it to the shelf, and the returning listing file is produced.
6. **Missing from the case.** A card that was packed but is neither sold nor in its pocket. It sits in a "Missing" bucket with its photo and last known place. It stays off the online listings until it is found or written off. It never silently goes back online.

## 3. The window, handled honestly
The listings go up as files, so between pulling a card and the next upload, the card may still be for sale online. Banchi should show that window, not hide it:
- **Pull at packing** (the safest choice). Packing ends by producing a "remove these" listing file. Until the owner confirms it was uploaded, every case card wears an "Online: still live" badge.
- **Keep listings live** (more reach, some risk). The badge stays on all weekend, and each online order for a case card is caught in state 4.
- In both modes, a timestamp on the trip shows when the last file was uploaded. The owner then knows exactly how long the window has been open.
- Unknown: whether the owner can upload a file from the iPad at the table, and how long the marketplace takes to apply an upload. Both decide how wide the real window is.

## 4. The smallest first version
- The case is one more location. Packing produces a pull list from a hand-picked set of cards and a "remove these" listing file.
- At the table, a card can be marked Sold or left alone. Offline sync is not in this version: on a show day with no network, the sales are entered in the evening.
- Come home produces the put-back list and the "return these" listing file.
- Left out: the scan at the table, the binder-shaped grid, the phone prompt for online orders (the Fulfiller's pick list shows "in Away Case" instead), and the money totals.

## 5. One measure
**Oversells per trip:** cancelled or refunded online orders whose card was in the Away Case. The target is zero. Price and sales numbers come later. This one says whether the feature does its single job.

## 6. Questions for the owner
1. When an online order arrives for a card in the case, which channel should win by default: the online buyer, or the table until the trip closes?
2. Should the default be to pull listings at packing, or to keep them live and accept the window?
3. What should a table price be: the market price, the market price minus the fees saved, or a price the owner sets for the trip?
