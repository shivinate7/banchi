# Glossary

One word per meaning, in every layer: screen, help text, docs, code, wire, store and command
line. This file is the home of the owner's terminology rulings. A word not here keeps its
plain English meaning.

The `retired phrases` row of `make docs-audit` reads the **Retired** column below. A retired
phrase is an exact phrase, matched without case, never a bare word. Bare words like "read",
"held" or "pushed" are correct in their own meaning, so the row never refuses them.

## Terms

| Term | Means | Not to be confused with | Retired |
|---|---|---|---|
| Match | The step that attaches each card to a TCGplayer product, by collector number against the product list. Button: "Match again". | Free read; the At market price rule; search | `Join again`; `Join with an export`; `Match the store` |
| Matched | A card that has a product attached. | Identified | |
| Not matched yet | A card with no product attached (stored identity source `read` today). | Disputed | |
| Free reader | The on-Mac image reader that compares a photo to stock photos. Costs nothing. Switch: "Free read in background". Setup press: "Set up free reader". | Paid read | `Background Match`; `Prepare matching`; `Refresh stock photos`; `Match to stock photos`; `Rig switch` |
| Free read | One answer from the free reader for one photo. | Paid read | |
| Paid read | One answer from the paid Claude batch read of a photo. The tooltip says "Claude Haiku", with no version. | Identify | `Paid Look`; `second look`; `Read from the photo`; `Claude Haiku 4.5` |
| Paid read batch | One batch of paid reads sent to Claude. Its pill while out: "Paid read out". | Send | `Nothing in this send was paid` |
| Identify | The whole first step: free read first, then the paid read for the rest. Only the paid read costs money. | The paid read alone | `only step that spends money` |
| Identified | The reader answered for a card. | Matched | |
| Read | One answer for one photo, free or paid. | Market price; counted | `not read yet` |
| Market price | A price snapshot for a product. | Read | |
| Counted | When a listing count was last taken: "counted 3 days ago", "Not counted yet". | Read | |
| Photo settings | The crop and size a paid read sends. | Read | |
| Disputed | A card whose photo read argues with its bound product. | Not matched yet | |
| Cut-off | The store's one price line (`policy.threshold`). At or above it a card earns a listing; below it the card goes out at the flat price and parks; no rule or price change may set a price under it. | Envelope limit; move size | `under the threshold` |
| Envelope limit | The order value above which a shipment needs tracking. | Cut-off | |
| Move size | The price change that counts a product as a mover. | Cut-off | |
| At market | The price rule that lists at the market price. | Match | |
| Held back | A product you chose to keep out of every send, on Pricing. | Trimmed; Reserved for order; Disputed; Counted as listed | `held for you`; `Held for order` |
| Trimmed | Copies the send guard removed because TCGplayer already had them: "Trimmed: TCGplayer already had them". | Held back | |
| Waiting for you | A Review card that needs your answer. | Held back | |
| Reserved for order | A copy set aside for a buyer's order. | Held back | |
| Counted as listed | A box's copies the store counts as listed. Button: "Stop counting as listed". It changes nothing at TCGplayer (D34, a box's holds release against its own copies). | Live | `Listing-held`; `Release the listing hold` |
| Review | The screen, and both of its piles. | To review | |
| To review | Review's main pile: cards that owe an answer. | Parked | `main queue` |
| Parked | Review's low-value pile: no answer owed. | To review | |
| Reader failed | A card no reader could answer. | Parked | |
| Answered | A person picked an answer for a card. | Stood down | `answered, left alone` |
| Stood down | A Review entry closed with the card unchanged. | Answered | |
| Send | The press that sends listings live to TCGplayer. | Paid read batch; price change | |
| Counted as sent | A copy the store has written to an import file. It may not be on TCGplayer yet. | Live | |
| Waiting to compare | A run whose import file is written and not yet compared with the staged file. | Counted as sent | |
| Price change | An upload that changes prices on live listings. | Send | |
| Import file | The file a run writes for TCGplayer's import. | Product list | |
| Product list | The game's Filtered CSV from TCGplayer, the source a Match reads. | Live listings file; staged file | |
| Live listings file | TCGplayer's My Pricing export: what is live now. | Product list | |
| Staged file | TCGplayer's Export From Staged file. | Import file | |
| Shipping file | TCGplayer's shipping export of open orders. | Product list | |
| Catalog | One spelling. | | `catalogue` |
| Card data | The vendored Pokemon card data. | Product list | |
| Image mirror | The local copy of card images. | Stock photo | |
| Photos folder | `photos/`, where card photos live. | Legacy captures; screenshots | |
| Legacy captures | `captures/cards/`, the old photo folder. | Photos folder | |
| Stock photo | TCGplayer's product image. Always says "stock". | Card photo | |
| Card 17 | A card's count in its box. | Collector number; key | `slot numbers are not the truth` |
| Collector number | The number printed on the card. | Card 17 | |
| Key | A card's stored index, which never moves. | Card 17 | |
| Sort key | The order cards are listed in. | Order | |
| Order | A buyer's order. | Sort key | |
| Box | A container of cards, addressed by its unique name. | Panel | `Pick the drawer`; `Fewest drawers` |
| Box id | A box's never-reused index (`bid`), never shown on screen. | Box name | |
| Panel | A slide-out part of the screen, the phone's included. | Box | `queue drawer` |
| Captured | A card state: photographed, not yet sent. | Photographed | `Cards captured`; `Sold of captured` |
| Photographed | The lifetime count of cards photographed. | Captured | |
| On hand | Copies in boxes now. Bare "stock" is never used. | Photographed | `In stock`; `On Your Shelf` |
| Product | The TCGplayer product bound to a card. | Live | `Listed as` |
| Live | Copies on TCGplayer now. | Running; counted as listed | |
| Running | A process that is running. | Live | |
| Claims | Your labels on a card: game, finish, rarity, set hint. | Lock | `Set claims` |
| Lock | A hold on a paid press so it runs once. | Claims | `release the claim` |
| Paused | The motion trigger, turned off by you. | Captures stopped | |
| Captures stopped | A fault halt. Button: "Start captures again". | Paused | `Captures are paused`; `Resume captures` |
| Sold | A buyer bought it, as the order ledger records. Home's link shows this count and opens Sales. | Sold on Banchi | |
| Sold on Banchi | The store's own sold flag on a card. It can lag a sale or be set by hand. | Sold | |
| Sales | The order ledger, and its screen. | Sold on Banchi | |
| Taken out | A card retired from its box. | Pull | |
| Pull | An order pick, which sells the copy. | Taken out | |
| Name | The printed card name. | Card id | |
| Card id | A card's stable id (`cid`). | Name | |
| Price book | `prices.json`, the store's one pricing answer. | Run price table | `no prices file yet` |
| Run price table | A run's `pricing.json`. | Price book | |
| Map | The view of boxes. | | `on the Shelf`; `Deleted boxes shelf` |
| Deleted boxes | Boxes deleted and kept for a way back. | Map | |
| Compare | A run's import file against the staged file. Read-only. | Check what is live | |
| Check what is live | The store against the live listings file. Writes counts. Button: "Update store counts". | Compare | `Store reconciled` |
| Live beyond on hand | Products live on TCGplayer beyond the copies on hand. | | |
| Printing | A card's appearance in one set. | Finish | |
| Finish | Normal, holo or reverse holo. | Rarity | |
| Rarity | Hyper rare, and the like: a card claim. | Finish | |

## Words that keep another meaning

These words also name something else, and that use stays: the kit Button's `variant` prop
(a style); TCGplayer's own `variant` field in `fixtures/` (fixtures are never modified);
`banchi archive sweep` (the price-history sweep); the search matcher of D271 (search).

## Rulings

- Every term in the table above is the owner's ruling.
- **Every layer is renamed, in phases:** screen, help, docs, code, wire, stored values and
  command names. The phased plan lives with the orchestrator.
- **"Variant" retires.** Finish is normal, holo or reverse holo. Rarity is hyper rare and the like.
- **"Parked" and "Staged" leave the machine-word list** (`scripts/machine-words.json`),
  amending D196 (no screen text names a mechanism) and D284 (three text checks).
- **Stored values are rewritten.** A backup and an undo are built before the first rewriting
  upgrade step. Readers accept both spellings for old run folders, the events log and sidecars.
- **Code `join` becomes `match`**, after the free reader leaves the name `match`.
- **One cut-off, no labour bar.** The fixed $0.40 constants and the below-bar warning go.
  Every caller reads the store's cut-off, and Review's colour bands follow it. D9 (the
  cut-off is also the price floor) is rewritten in place.
- **Route paths are wire**, and rename with their fields.
- **The kit Button's `variant` prop stays**: it is a style, not a card.
- **Code cards are out of scope** while the feature is dormant.
- **Old command names refuse and print the new name.** No alias. The command-rename merge
  comes with a planned server restart.
