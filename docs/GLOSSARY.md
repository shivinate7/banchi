# Glossary

One word per meaning, in every layer: screen, help text, docs, code, wire, store and command
line. This file is the home of the owner's terminology rulings. A word not here keeps its
plain English meaning. TCGplayer's own column, file and button names stay as TCGplayer spells
them.

The terms are grouped by the stage of the work, in order: capture, read, match to product,
price, list on TCGplayer, sell and ship, and boxes. Words that every stage uses come last.

A row with no tag is the owner's ruling. A row tagged **fixed** keeps the owner's word, and this
rework corrected what it means to match the code. A row tagged **open** carries the recommended
word for the owner's numbered note on the earlier draft. A row tagged **new** is proposed by this
rework. Fixed, open and new rows wait for the owner's word.

The **Retired** column holds exact phrases, matched without case, never bare words. Bare words
like "read", "held" or "pushed" are correct in their own meaning, so a check must never refuse
them. **NOT MECHANIZED:** no `make docs-audit` row reads this column yet. A machine would have to
read the Retired column of every table below and refuse each phrase in screen strings, help
text, docs and code, outside this file.

## Capture

| Term | Means | Not to be confused with | Retired |
|---|---|---|---|
| Captured (**fixed**) | A card state: photographed, and no reader has answered for it yet. Its name shows as Not read yet. The card leaves this state when its read is recorded. | Photographed | `Cards captured`; `Sold of captured` |
| Photographed | The lifetime count of cards photographed. | Captured | |
| Paused | The motion trigger, turned off by you. | Captures stopped | |
| Captures stopped | A fault halt. Button: "Start captures again". | Paused | `Captures are paused`; `Resume captures` |
| Photos Folder | `photos/`, where card photos live. | Legacy Captures; screenshots | |
| Legacy Captures | `captures/cards/`, the old photo folder. | Photos Folder | |
| Claims (**fixed**) | Your labels on a card: game, set hint, finish, rarity and a note. | Lock | `Set claims` |
| Finish (**fixed**) | Normal, holo or reverse holo for Pokemon. Normal or foil for Riftbound and One Piece. A misc card has none. | Rarity; Printing | |
| Rarity | The printed rarity, such as hyper rare. As a claim, it catches a misread (D23, a rarity claim catches misreads). | Finish | |

## Read

| Term | Means | Not to be confused with | Retired |
|---|---|---|---|
| Read (**open**: notes 1, 4) | The step that looks at each photo and says which card it shows: its name, collector number and set. Also one such answer, "a read". The Free Reader reads first. The paid read reads the cards it does not accept. Only the paid read costs money. A run then matches by itself (D321, every identify run joins itself). It replaces Identify and Identified. | Match; Counted; Market Price; Photo Settings | `only step that spends money`; `Identify it first` |
| Not read yet | A Captured card: no reader has answered for it. Its name shows in muted italic. | Read, not matched | `Not Looked at Yet` |
| Free Reader (**open**: note 2) | The image reader on this Mac. It compares a photo with TCGplayer's Stock Photos and reports the closest card. It costs nothing, and it cannot tell foil from normal. Switch: "Free read in background". Setup press: "Set up free reader". Its tooltip names the model. | Paid read | `Background Match`; `Prepare matching`; `Refresh stock photos`; `Match to stock photos`; `Rig switch`; `Matched Free`; `Matching now` |
| Accepted (**new**) | The Free Reader is sure of a card: its best Stock Photo beats the next one by the accept margin and clears the score floor (`match.MARGIN_MIN`, `match.FLOOR_MIN`). Only an accepted card gets a free read. | Threshold; Matched | `accuracy threshold` |
| Free read | One read from the Free Reader for one photo. | Paid read | |
| Paid read (**open**: notes 2, 3) | One read of a photo by Claude, sent in a batch and paid for. It also reports the finish. The tooltip says "Claude Haiku", with no version. | Free read | `Paid Look`; `second look`; `Read from the photo`; `Claude Haiku 4.5` |
| Paid read batch | One batch of paid reads sent to Claude. Its pill while out: "Paid read out". | List | `Nothing in this send was paid` |
| Waiting for a paid read (**new**) | A Captured card the Free Reader tried and did not accept. The next Read press sends it to the paid read. | Reader failed; Waiting for you | |
| Reader failed (**fixed**) | The Free Reader crashed on this card's photo. The card leaves the background queue until the photo is taken again or the model changes. A Read press can still read it. | Waiting for a paid read | |
| Photo Settings | The crop and size a paid read sends. | Read | |
| Stock Photo | TCGplayer's product image. Always says "stock". | Card photo | |

## Match to product

| Term | Means | Not to be confused with | Retired |
|---|---|---|---|
| Match (**open**: note 1) | The step that finds the SKU for each read card in the Product List, by its collector number. The key is per game. Product Name is only a last resort (D35, an unreadable number falls back to the name). A run matches by itself when its read ends. Free. Button: "Match again". | Read; At Market; search | `Join again`; `Join with an export`; `Match the store` |
| Matched | A card with a SKU. Its name shows in normal ink. | Read, not matched | |
| Read, not matched | A card with a read and no SKU. Its name shows in the warning color. The reason, such as "Set not downloaded", shows on hover. | Not read yet; Disputed | |
| Not matched yet (**fixed**) | A card with no SKU: not read yet, or read and not matched. | Disputed | |
| Disputed | A card whose read (name or collector number) disagrees with its SKU. A card held on a disputed SKU keeps its read as its identity (stored `identity_source` `read`). | Not matched yet | |
| SKU (**new**) | TCGplayer's id for one Product in one condition and finish: the `TCGplayer Id` column. A matched card carries one. | Product; Key | |
| Product | One TCGplayer catalog card: name, set and number. A card's SKU belongs to one Product. | Live; Printing | `Listed as` |
| Product List | The game's Filtered CSV from TCGplayer. Match reads it, and it carries the Market Price (D166, the catalog export belongs to the game). | Live Listings File; Staged File | |
| Collector Number | The number printed on the card. | Card 17; Key | |
| Printing | A card's appearance in one set. | Product, TCGplayer's catalog entry for it; TCGplayer's own "Printing" field, which is Finish | |
| Review | The screen, and both of its piles. | To Review | |
| To Review | Review's main pile: cards that owe an answer. | Parked | `main queue` |
| Parked (**fixed**) | Review's low-value pile: cards whose cheapest possible SKU is under the Threshold. You owe them no answer. Bulk Lots is their exit (D9, one price line). | To Review | |
| Waiting for you | A Review card that needs your answer. A paid read waits here when it names a different printing from the Free Reader's pick, or is not sure. | Withheld; Waiting for a paid read | `held for you`; `held for review` |
| Answered (**open**: note 7) | You picked a card's SKU from the candidates Review offered. The card is matched to it. | Closed; Skipped | |
| Closed (**open**: note 7) | You ended a Review question without an answer. "Keep the card": it stays as it was, for one of three reasons (Wasted position, Cannot settle it, Not listing it; D37, a stand-down writes nothing). Or retire it. Can be undone. | Answered; Skipped; Retired; the camera's "Closed" on Capture | `Stand down`; `stood down`; `answered, left alone` |
| Skipped (**new**) | A Review card you put off with S. It comes back in this sitting. | Closed | |

## Price

| Term | Means | Not to be confused with | Retired |
|---|---|---|---|
| Threshold (**fixed**) | The store's one price line (`policy.threshold`). A card whose Market Price is at or above it is priced by the Price Rule. A card under it goes out at the Flat Price. No rule or price change may set a price under it (D9, one price line). | Envelope Limit; Move Size; Accepted | `the cut-off`; `cut-off price`; `Cut-off changed`; `Cut-off for this run`; `price floor`; `labor bar`; `import-listed.csv`; `import-subthreshold.csv` |
| Flat Price (**new**) | The one price every card under the Threshold goes out at (`policy.sub_threshold`). By default it is the Threshold. | Threshold; Market Price | |
| Price Rule (**new**) | How the store prices a card at or above the Threshold: At Market, or a percent under or over the Market Price or TCG Low. | Price change | |
| At Market | The Price Rule that lists at the Market Price (stored rule `match`). | Match | `Match market` |
| Market Price | TCGplayer's Market Price for a SKU, as last downloaded (D189, the market reading is a table). | Read; Counted | |
| Move Size | The price change that makes a Product a mover (`movers.THRESHOLD`). | Threshold | |
| Withheld (**open**: note 6) | A SKU you chose to keep out of every List press, on Pricing, with a reason: bullish, keeping it, or a later batch. | Trimmed; Reserved for order; Disputed; Counted as listed; Removed by you | `held back` |
| Price Book | `prices.json`, the store's one pricing answer (D86, one pricing file for the store). | Run Price Table | `no prices file yet` |
| Run Price Table | A run's `pricing.json`. | Price Book | |

## List on TCGplayer

| Term | Means | Not to be confused with | Retired |
|---|---|---|---|
| List (**open**: note 8) | The one press that puts copies up for sale on TCGplayer. It reads what is live, trims, uploads the Import File and makes it live (D273, one press sends listings live). It may also carry price changes for cards already live. Button: "List 3 copies, change 2 prices". The warning's "List anyway" replaces "Send Anyway". | Paid read batch; Price change; Product List | `Price and send`; `Send Anyway`; `Nothing to send`; `listed-only` |
| Price change | A row that changes the price of a card already live, and adds no copy. The Live tab's press sends only these. | List; Price Rule | |
| Trimmed | Copies the List press left out because TCGplayer already had them: "Trimmed: TCGplayer already had them". | Withheld; Removed by you | |
| Counted as listed (**open**: note 8) | Copies of a SKU the store counts as at TCGplayer or on their way: written into an Import File, staged, or live. A count only; TCGplayer may differ. A box's button "Stop counting as listed" lowers it and changes nothing at TCGplayer (D34, a box's holds release against its own copies). | Live; Not found yet | `Listing-held`; `Release the listing hold` |
| Not found yet (**new**) | Copies counted as listed that no check has found live at TCGplayer. Button: "Take them back". | Counted as listed; Removed by you | |
| Removed by you (**new**) | Copies a check saw live that later left TCGplayer with no sale and no open order: you took them down by hand. No List press sends them again until you press "Unhold" (D273, its hand-removal rule). | Withheld; Not found yet; Taken out | |
| Live | Copies TCGplayer holds for sale now: the last Live Listings File's figure, less the copies sold here since (D115, the reading is the export, with later sales beside it). | Running; Counted as listed | |
| Counted | When the store last wrote a SKU's live figure: "counted 3 days ago", "Not counted yet". | Read; Market Price | |
| Check what is live | The store against the Live Listings File. Writes the live figures. Button: "Update store counts". | Compare | `Store reconciled` |
| Compare | A run's Import File against the Staged File. Read-only. | Check what is live | |
| Waiting to compare | A run whose Import File is written and not yet compared with the Staged File. | Not found yet | |
| Live beyond on hand | Products live on TCGplayer beyond the copies on hand. | Removed by you | |
| Import File | The file a run writes for TCGplayer's import. | Product List | |
| Staged File | TCGplayer's Export From Staged file. | Import File | |
| Live Listings File | TCGplayer's My Pricing export: what is live now. | Product List | |

## Sell and ship

| Term | Means | Not to be confused with | Retired |
|---|---|---|---|
| Order | A buyer's order. | Sort Key | |
| Sold (**fixed**) | A buyer bought it, as the order ledger records. Home's sold link must show this count and open Sales. | Sold on Banchi | |
| Sold on Banchi | The store's own sold flag on a card. It can lag a sale or be set by hand. | Sold | |
| Sales | The order ledger, and its screen. Gross only (D214, Sales shows gross, never profit). | Sold on Banchi | |
| Pull | An order pick, which sells the copy. | Taken out | |
| Reserved for order | A copy set aside for a buyer's order. | Withheld | `Held for order` |
| Shipping File | TCGplayer's shipping export of open orders. | Product List | |
| Envelope Limit (**fixed**) | The order value at or above which TCGplayer requires tracking (`shipping.TRACKING_THRESHOLD`). | Threshold | |

## Boxes

| Term | Means | Not to be confused with | Retired |
|---|---|---|---|
| Box | A container of cards, shown and addressed by its unique name (D20, a box is an object with a name; D259, boxes show names only). | Panel | `Pick the drawer`; `Fewest drawers` |
| Box Number (**new**) | A box's number inside the store (`--box N`). It is the lowest free number, so a deleted box's number is used again. Never shown. | Box ID; Card 17 | |
| Box ID | A box's never-reused id (`bid`, `--bid N`). Runs and buried cards point to it. Never shown (D145, a box's bid is a hidden identity). | Box Number | |
| Section (**new**) | A run of cards in a box, started by a divider. You put a divider in with S on Capture (D10, the inventory model). | Box; Card 17 | |
| Card 17 (**fixed**) | A card's count within its section. Card 1 is at the far back, and the count starts again at each divider. When a card ahead of it leaves, the count closes up (D260, card numbers count within a section). | Collector Number; Key | `slot numbers are not the truth` |
| Key (**fixed**) | A card's stored place in the store, which never moves. Never shown: it stays on the wire and in the route path (D259, boxes show names only). | Card 17; SKU | |
| Sort Key | A card's place in its box's order (`Card.order`, a fraction). Placing or moving a card changes it; the Key stays (D294, each card carries a fraction order key). | Order; Key | |
| Map | The view of boxes. | | `on the Shelf`; `Deleted boxes shelf` |
| Deleted Boxes | Boxes deleted and kept for a way back. | Map | |
| On hand | Copies in boxes now. Bare "stock" is never used. | Photographed; Live | `In stock`; `On Your Shelf` |
| Retired (**new**) | A card that left its box without a sale: Taken out, Damaged, Lost or Given away. Its record stays (D26, retired is a terminal card state). | Closed; Sold; Moved | |
| Taken out (**fixed**) | The retire reason for a card taken out of its box by hand (stored `pulled`). | Pull | |
| Moved (**new**) | A card that went to another box. Its old place keeps a record (D83, moved is a third way a card leaves). | Retired | |

## Across the app

| Term | Means | Not to be confused with | Retired |
|---|---|---|---|
| Name | The printed card name. | Card ID | |
| Card ID | A card's stable id (`cid`). | Name; Key; SKU | |
| Lock (**fixed**) | What a Read press or a List press puts on the cards it covers while it runs, so a second press cannot pay for or list them twice (D174, a paid press claims its cards atomically). | Claims | `release the claim` |
| Running | A process that is running. | Live | |
| Panel | A slide-out part of the screen, the phone's included. | Box | `queue drawer` |
| Catalog | One spelling. | | `catalogue` |
| Card Data | The vendored Pokemon card data (D15, the catalog is vendored, not fetched). | Product List | |
| Image Mirror | The local copy of the Card Data's card images, filled by hand (`make catalog-mirror`). The read-accuracy test (T1) reads it. | Stock Photo | |

## Words that keep another meaning

These words also name something else, and that use stays:

- `variant`: the kit Button's `variant` prop (a style), and TCGplayer's own `variant` field in
  `fixtures/` (fixtures are never modified).
- "sweep": `banchi archive sweep`, the price-history sweep.
- "matcher": the search matcher of D271 (every search uses one matcher).
- (**new**) "floor": the design floors (D50, feedback is the product's) and the Free Reader's
  score floor. The price floor is the Threshold.
- (**new**) "Product": the code-card claim for the sealed product a stack came out of. Code
  cards are out of scope while dormant.

## Rulings

- Every untagged term in the tables above is the owner's ruling. A **fixed** term keeps the
  owner's word, with its meaning corrected to the code.
- **Open for the owner:** notes 1 and 4 (Read and Match; Identify retires), notes 2 and 3 (Free
  Reader and paid read), note 6 (Withheld), note 7 (Answered, Closed) and note 8 (List, and
  Counted as listed with it). The rows tagged **new** wait for the owner's word too.
- **Every layer is renamed, in phases:** screen, help, docs, code, wire, stored values and
  command names. The phased plan lives with the orchestrator.
- **"Variant" retires.** Finish is normal, holo or reverse holo for Pokemon, and normal or foil
  for Riftbound and One Piece. Rarity is hyper rare and the like.
- **"Parked" and "Staged" leave the machine-word list** (`scripts/machine-words.json`),
  amending D196 (no screen text names a mechanism) and D284 (three text checks).
- **Stored values are rewritten.** A backup and an undo are built before the first rewriting
  upgrade step. Readers accept both spellings for old run folders, the events log and sidecars.
- **Code `join` becomes `match`**, after the Free Reader leaves the name `match`.
- **Threshold is the one price-line word.** Cut-off retires. (**new**) Code names that say threshold
  for another line rename with the code: `movers.THRESHOLD` (Move Size) and
  `shipping.TRACKING_THRESHOLD` (Envelope Limit).
- **One Threshold, no labor bar.** The fixed $0.40 constants and the below-bar warning go.
  Every caller reads the store's Threshold, and Review's color bands follow it. (**new**)
  Review's parking (`routing.route`) is one such caller. D9 (the cut-off is also the price floor) is
  rewritten in place.
- **A split send writes `import-above-threshold.csv` and `import-below-threshold.csv`.**
  `banchi archive sweep` keeps its name: it is the only sweep once the Free Reader's loop is renamed.
- **Match state shows as text color, never a pill.** Matched names use normal ink; read but not
  matched use the warning color; not read yet use muted italic. The reason (for example
  "Set not downloaded") shows only on hover over the row.
- **Named things take Title Case**: Product List, Staged File, Box ID. In these tables that means
  files, images, folders, data sets, screens, Review's piles, the Free Reader, ids and named
  settings. Card states, acts and button
  text keep sentence case. That boundary is **new**.
- **Route paths are wire**, and rename with their fields.
- **The kit Button's `variant` prop stays**: it is a style, not a card.
- **Code cards are out of scope** while the feature is dormant.
- **Old command names refuse and print the new name.** No alias. The command-rename merge
  comes with a planned server restart.
