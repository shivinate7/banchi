# Glossary

One word per meaning, in every layer: screen, help text, docs, code, wire, store and command
line. This file is the home of the owner's terminology rulings. A word not here keeps its
plain English meaning. TCGplayer's own column, file and button names stay as TCGplayer spells
them.

The terms are grouped by the stage of the work, in order: capture, read, match to product,
price, post to TCGplayer, sell and ship, and boxes. Words that every stage uses come last.

A row with no tag is the owner's ruling. A row tagged **fixed** keeps the owner's word, and this
rework corrected what it means to match the code. A row tagged **new** is proposed by this
rework. Fixed and new rows wait for the owner's word.

The **Retired** column lists exact phrases, matched without case, never bare words. Bare words
like "read", "live" or "pushed" are correct in their own meaning, so a check must never refuse
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
| Read | The step that looks at each photo and says which card it shows: its name, collector number and set. A read is one reader's answer for one photo, and the word has no other meaning. The Free Reader reads first. The Paid Reader reads the cards it does not accept. Only the Paid Reader costs money. A run then matches by itself (D321, every identify run joins itself). It replaces Identify and Identified. | Match; Counted; Market Price; Photo Settings | `only step that spends money`; `Identify it first` |
| Not read yet | A Captured card: no reader has answered for it. Its name shows in muted italic. | Read, not matched | `Not Looked at Yet` |
| Free Reader | The image reader on this Mac. It compares a photo with TCGplayer's Stock Photos and reports the closest card. It costs nothing, and it cannot tell foil from normal. Switch: "Free read in background". Setup press: "Set up free reader". Its tooltip says "Marqo-B". | Paid Reader | `Background Match`; `Prepare matching`; `Refresh stock photos`; `Match to stock photos`; `Rig switch`; `Matched Free`; `Matching now` |
| Accepted (**new**) | The Free Reader is sure of a card: its best Stock Photo beats the next one by the accept margin and clears the score floor (`match.MARGIN_MIN`, `match.FLOOR_MIN`). Only an accepted card gets a free read. | Threshold; Matched | `accuracy threshold` |
| Free read | One read from the Free Reader for one photo. | Paid read | |
| Paid read | One read from the Paid Reader for one photo. | Free read | |
| Paid Reader | Claude, which reads photos in a paid batch. It reads the cards the Free Reader does not accept, and it also reports the finish. Its tooltip says "Claude Haiku", with no version. | Free Reader | `Paid Look`; `second look`; `Read from the photo`; `Claude Haiku 4.5` |
| Paid read batch | One batch of paid reads sent to Claude. Its pill while out: "Paid read out". | Post | `Nothing in this send was paid` |
| Waiting for a paid read (**new**) | A Captured card the Free Reader tried and did not accept. The next Read press gives it to the Paid Reader. | Reader failed; Waiting for you | |
| Reader failed (**fixed**) | The Free Reader crashed on this card's photo. The card leaves the background queue until the photo is taken again or the model changes. A Read press can still read it. | Waiting for a paid read | |
| Photo Settings | The crop and size of each photo the Paid Reader gets. | Read | |
| Stock Photo | TCGplayer's product image. Always says "stock". | Card photo | |

## Match to product

| Term | Means | Not to be confused with | Retired |
|---|---|---|---|
| Match | The step that finds the SKU for each read card in the Product List, by its collector number. The key is per game. Product Name is only a last resort (D35, an unreadable number falls back to the name). A run matches by itself when its read ends. Free. Button: "Match again". | Read; At Market; search | `Join again`; `Join with an export`; `Match the store` |
| Matched | A card with a SKU. Its name shows in normal ink. | Read, not matched | |
| Read, not matched | A card with a read and no SKU. Its name shows in the warning color. The reason, such as "Set not downloaded", shows on hover. | Not read yet; Disputed | |
| Not matched yet (**fixed**) | A card with no SKU: not read yet, or read and not matched. | Disputed | |
| Disputed | A card whose read (name or collector number) disagrees with its SKU. A card whose SKU is disputed keeps its read as its identity (stored `identity_source` `read`). | Not matched yet | |
| SKU (**new**) | TCGplayer's id for one Product in one condition and finish: the `TCGplayer Id` column. A matched card carries one. | Product; Key | |
| Product | One TCGplayer catalog card: name, set and number. A card's SKU belongs to one Product. | Live; Printing | `Listed as` |
| Product List | The game's Filtered CSV from TCGplayer. Match reads it, and it carries the Market Price (D166, the catalog export belongs to the game). | Live Listings File; Staged File | |
| Collector Number | The number printed on the card. | Card 17; Key | |
| Printing | A card's appearance in one set. | Product, TCGplayer's catalog entry for it; TCGplayer's own "Printing" field, which is Finish | |
| Review | The screen, and both of its piles. | To Review | |
| To Review | Review's main pile: cards that owe an answer. | Parked | `main queue` |
| Parked (**fixed**) | Review's low-value pile: cards whose cheapest possible SKU is under the Threshold. You owe them no answer. Bulk Lots is their exit (D9, one price line). | To Review | |
| Waiting for you | A Review card that needs your answer. A paid read waits here when it names a different printing from the Free Reader's pick, or is not sure. | Withheld; Waiting for a paid read | `held for you`; `held for review` |
| Answered | You picked a card's SKU from the candidates Review offered. The card is matched to it. | Closed; Skipped | |
| Closed | You ended a Review question without an answer. A reason line says whether the card was kept or retired. Kept: it stays as it was, for one of three reasons (Wasted position, Cannot settle it, Not listing it; D37, a stand-down writes nothing). Retired: it leaves its box. Can be undone. | Answered; Skipped; Retired; the camera's "Closed" on Capture | `Stand down`; `stood down`; `answered, left alone`; `left in place` |
| Skipped | A Review card you put off with S. It comes back in this sitting. | Closed | |

## Price

| Term | Means | Not to be confused with | Retired |
|---|---|---|---|
| Threshold (**fixed**) | The store's one price line (`policy.threshold`). A card whose Market Price is at or above it is priced by the Price Rule. A card under it goes out at the Flat Price. No rule or price change may set a price under it (D9, one price line). | Envelope Limit; Move Size; Accepted | `the cut-off`; `cut-off price`; `Cut-off changed`; `Cut-off for this run`; `price floor`; `labor bar`; `import-listed.csv`; `import-subthreshold.csv` |
| Flat Price (**new**) | The one price every card under the Threshold goes out at (`policy.sub_threshold`). By default it is the Threshold. | Threshold; Market Price | |
| Price Rule (**new**) | How the store prices a card at or above the Threshold: At Market, or a percent under or over the Market Price or TCG Low. | Price change | |
| At Market | The Price Rule that lists at the Market Price (stored rule `match`). | Match | `Match market` |
| Market Price | TCGplayer's Market Price for a SKU, as last downloaded (D189, the market reading is a table). | Read; Counted | |
| Move Size | The price change that makes a Product a mover (`movers.THRESHOLD`). | Threshold | |
| Withheld | A SKU you chose to keep out of every Post, on Pricing, with a reason: bullish, keeping it, or a later batch. | Trimmed; Reserved for order; Disputed; Counted as listed; Removed by you | `held back` |
| Price Book | `prices.json`, the store's one pricing answer (D86, one pricing file for the store). | Run Price Table | `no prices file yet` |
| Run Price Table | A run's `pricing.json`. | Price Book | |

## Post to TCGplayer

| Term | Means | Not to be confused with | Retired |
|---|---|---|---|
| Post | The one press that puts copies up for sale on TCGplayer. It reads what is live, trims, uploads the Import File and makes it live (D273, one press posts listings live). It may also carry price changes for cards already live. Button: "Post 3 copies and 2 price changes". The warning's "Post Anyway" replaces "Send Anyway". "Nothing to post" replaces "Nothing to send", and "Price and post" replaces "Price and send". | Paid read batch; Price change | `Price and send`; `Send Anyway`; `Nothing to send`; `listed-only` |
| Price change | A row that changes the price of a card already live, and adds no copy. The Live tab's Post carries only these. | Post; Price Rule | |
| Trimmed | Copies a Post left out because TCGplayer already had them: "Trimmed: TCGplayer already had them". | Withheld; Removed by you | |
| Counted as posted | A copy the store wrote into an Import File, by a Post or a download. It may not be on TCGplayer yet. | Live; Not found yet | |
| Counted as listed | A box's copies the store counts as listed: posted, staged or live. Button: "Stop counting as listed". It changes nothing at TCGplayer (D34, a box releases only its own copies). | Live | `Listing-held`; `Release the listing hold` |
| Not found yet (**new**) | Copies counted as posted that no check has found live at TCGplayer. Button: "Take them back": the copies go back on the list for the next Post. | Counted as posted; Removed by you | |
| Removed by you (**new**) | Copies a check saw live that later left TCGplayer with no sale and no open order: you took them down by hand. No Post includes them until you press "Take them back". Its own Undo reverses it (D273, its hand-removal rule). | Withheld; Not found yet; Taken out | |
| Live | Copies on sale at TCGplayer now: the last Live Listings File's figure, less the copies sold here since (D115, the reading is the export, with later sales beside it). | Running; Counted as posted | |
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
| Lock (**fixed**) | What a Read press or a Post puts on the cards it covers while it runs, so a second press cannot pay for or post them twice (D174, a paid press claims its cards atomically). | Claims | `release the claim` |
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
- **Read, then Match.** Identify retires as a screen word. `banchi identify` and the stored
  state `identified` are renamed in a later phase. A read is one reader's answer for one photo.
- **The two readers are the Free Reader and the Paid Reader.** Their tooltips say "Marqo-B" and
  "Claude Haiku", with no version.
- **Withheld is the word for a SKU you keep out.** No meaning of "held" remains in this file.
- **Review ends a question as Answered, Closed or Skipped.** A closed card's reason line says
  whether it was kept or retired.
- **Post replaces Send everywhere** for the listing press: screen, help, docs, command flags,
  routes and stored names.
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
- **Split files are `import-above-threshold.csv` and `import-below-threshold.csv`.** The flag
  `--listed-only` becomes `--above-threshold-only`.
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

## Code map

This map lists the names that change when the code adopts the terms above. A rename lane works
through its rows as a find-and-replace, and its reviewer checks the lane row by row. The owner's
sign-off on this file approves every New name below, except the rows marked UNDECIDED.

Rename by meaning, never by word. Where one old name carries two meanings, each meaning has its
own row. "Names with two meanings", after the tables, tells you which is which.

- **Layer** is one of these:
  - screen: text on a screen.
  - help: command help text and the keyboard sheet.
  - docs: Markdown, and prose in code comments.
  - code: a name inside one program.
  - wire: a JSON field, a refusal code, a run command or a TypeScript wire type.
  - route: a server path.
  - stored: a value, a key, a table or a folder on disk.
  - file: a module or a file name.
  - CLI: a command, a flag, a make target or text that a command prints.
- **New name** follows the code's own casing: snake_case in Python, camelCase in TypeScript and
  kebab-case for command flags. A note in parentheses says why a name avoids the obvious one.
  These words mark special rows:
  - **migrates**: a stored value. The upgrade step rewrites it after a backup and an undo exist,
    and readers accept both spellings (Rulings, "Stored values are rewritten").
  - **keep**: a ruling keeps the name. The row names the ruling.
  - **cannot move**: the row says why, in one line.
  - **delete**: the ruling removes the thing, so it gets no new name.
  - **UNDECIDED**: the owner decides. Do not rename it yet.
- **Where** is a `module.symbol`, a module or a file, never a line.
- **Count** is the number of lines that match Name today, in the tracked files outside
  `fixtures/`, `vendor/`, `demo-assets/` and this file, counted before this map was added. An
  identifier counts as a whole word (`git grep -w`), a phrase as exact text (`git grep -F`), and a
  quoted value in either quote. † means the count reads only some files, or leaves some out, so
  that another meaning of the word is not counted. "—" means no count.
- A count is the size of the job, not a list to replace blindly. Before a lane starts, it counts
  its rows again. After the lane, its reviewer counts again: each renamed row reads 0, except the
  lines that a keep row, a cannot-move row or "Names with two meanings" keeps.

### Capture renames

| Term | Layer | Name today | New name | Where | Count |
|---|---|---|---|---|---|
| Captures stopped | screen | "Captures are paused" | "Captures stopped" | CaptureScreen | 25 |
| Captures stopped | screen | "Resume captures" | "Start captures again" | dealer.SAID_DROPPED | 11 |
| Claims | screen | "Set Claims" | "Claims" | BoxOps, the claim editor title | 1 |
| Finish | wire | `metadata_finish` | `finish` | photos.CLAIM_WIRE_NAMES | 236 |
| Finish | stored | `"variant"` (the finish claim's sidecar and request key) | `"finish"`, migrates | photos.CLAIM_WIRE_NAMES; sidecar | 21 † |
| Finish | file | `variant` (the finish ladder's module, D3) | `finish_ladder` | pipeline/variant.py | 303 |
| Finish | code | `variant_from_flag` | `finish_from_flag` | sidecar | 12 |
| Finish | code | `LogoVariant`, `LOGO_VARIANTS`, `DEFAULT_VARIANT` (the mark's style, not a card) | UNDECIDED: a style like the kit Button prop, but no ruling keeps it | kit; markPalettes; rarityMarks | 26 |
| Finish | code | `variant_default` | `finish_default` | sidecar | 13 |
| Finish | code | `resolvedVariant` | `resolvedFinish` | BoxBrowse | 5 |
| Finish | code | `chosenVariant`, `setChosenVariant` | `chosenFinish`, `setChosenFinish` | BoxBrowse | 9 |
| Finish | code | `variant` (the kit Button's prop) | keep: ruling "The kit Button's variant prop stays" | kit/Button | — |
| Finish | file | `variant` (TCGplayer's field in fixtures/) | keep: ruling "Variant retires", which spares fixtures, and fixtures are never modified | fixtures/ | — |
| Photos Folder | CLI | `capture-dir` | `photos-dir` | cli/__main__.py | 15 |

### Read renames

| Term | Layer | Name today | New name | Where | Count |
|---|---|---|---|---|---|
| Read | CLI | `banchi identify` | `banchi read` | cli/__main__.py | 64 |
| Read | file | `cmd_identify` | `cmd_read` | cli/cmd_identify.py | 348 |
| Read | file | `identify/` (the package of both readers) | `reader/` | identify/ | 318 |
| Read | route | `/pipeline/identify` | `/pipeline/read` | pipeline_routes.do_pipeline_identify | 54 |
| Read | code | `do_pipeline_identify` | `do_pipeline_read` | cli_identify | 11 |
| Read | wire | `"identify"` (run command and step) | `"read"` | RunsStage.COMMANDS; cli/__main__.py | 68 |
| Read | screen | "Identify" | "Read" | RunsStage.STAGES; RunPanel.TITLES | 5 |
| Read | stored | `"identified"` (card state) | `"read"`, migrates | master.IDENTIFIED; cardState.IDENTIFIED | 187 |
| Read | code | `IDENTIFIED` | `READ` | master.IDENTIFIED; cardState.IDENTIFIED | 192 |
| Read | screen | "Identified" | "Read" | cardState.STATE_WORDS | 1 |
| Read | code | `record_identification` | `record_read` | master.Inventory | 116 |
| Read | stored | `identifications` (the cache table of reads) | `reads`, migrates | cache.Cache | 196 |
| Read | file | `identifications.json` (a run's reads) | `reads.json`, migrates | runs.RunDir | 83 |
| Read | code | `write_identifications` | `write_reads` | runs.RunDir | 47 |
| Read | code | `read_identifications` | `load_reads` | runs.RunDir | 27 |
| Read | code | `IdentifiedCard` | `ReadCard` | join.IdentifiedCard | 92 |
| Read | stored | `"identification_failed"` (review reason) | `"paid_read_failed"`, migrates | routing.IDENTIFICATION_FAILED | 6 |
| Read | code | `IDENTIFICATION_FAILED` | `PAID_READ_FAILED` | routing.IDENTIFICATION_FAILED | 9 |
| Read | code | `identification` (the bare word, meaning a read) | `read` | cmd_identify; resolve; master; cmd_cards.SOURCE_ORDER | 450 |
| Card ID | help | "identification checks" (D239's stored-data checks, not a read; the make target already says identity-checks) | "identity checks" | cli/__main__.py; cmd_cards; Makefile | 4 |
| Read | help | "captured, identified, sold, retired" | "captured, read, sold, retired" | cli/__main__.py | 1 † |
| Read | help | "run directory from `identify`" | "run directory from `read`" | cli/__main__.py | 2 † |
| Free Reader | help | "default: marqo-b, the free stock-photo reader" | "default: free, the Free Reader" | cli/__main__.py | 1 † |
| Read | code | `never_identified`, `not_identified`, `unidentified` | `never_read`, `not_read`, `unread` | capture_server | 46 |
| Read | code | `reidentify`, `reidentify_stale` | `reread`, `reread_stale` | cmd_identify | 15 |
| Not read yet | screen | "Not Looked at Yet" | "Not read yet" | ReviewBand.COUNTS | 2 |
| Free Reader | wire | `"marqo-b"` (engine) | `"free"`, migrates in cache rows and run manifests | cache.ENGINE_MATCHER; engines.Engine | 97 |
| Free Reader | code | `ENGINE_MATCHER` | `ENGINE_FREE` | cache.ENGINE_MATCHER | 18 |
| Free Reader | code | `matcher` (meaning the Free Reader) | `free_reader` | identify/; cmd_match; server/match.py | 58 † |
| Free Reader | file | `match` (the Free Reader's module) | `free_reader` | identify/match.py | 251 |
| Free Reader | file | `matchconst` | `free_reader_const` | identify/matchconst.py | 28 |
| Free Reader | file | `sweep` (the Free Reader's background module) | `background` | identify/sweep.py | 75 |
| Free Reader | CLI | `banchi match` | `banchi free-reader` | cli/__main__.py; cmd_match | 22 |
| Free Reader | file | `cmd_match` (the Free Reader's setup) | `cmd_free_reader`; it moves before cmd_join takes cmd_match | cli/cmd_match.py | 41 |
| Free Reader | CLI | `--sweep` | `--background` | cmd_match; sweep | 16 |
| Free Reader | code | `sweep_worker` | `background_worker` | cmd_match.sweep_worker | 13 |
| Free Reader | route | `/pipeline/match` (with /prepare and /sweep) | `/pipeline/free-reader` (with /prepare and /background) | pipeline_routes.do_pipeline_match | 82 |
| Free Reader | code | `do_pipeline_match`, `do_pipeline_match_sweep`, `do_pipeline_match_sweep_set`, `do_pipeline_match_prepare` | `do_free_reader`, `do_free_reader_background`, `do_free_reader_background_set`, `do_free_reader_prepare` | pipeline_routes | 15 |
| Free Reader | code | `getMatchState`, `getMatchSweep`, `setMatchSweep`, `prepareMatch` | `getFreeReaderState`, `getFreeReaderBackground`, `setFreeReaderBackground`, `prepareFreeReader` | server.ts | 23 |
| Free Reader | wire | `MatchState`, `MatchSweep`, `MatchSweepDetail`, `MatchSweepCard` | `FreeReaderState`, `FreeReaderBackground`, `FreeReaderBackgroundDetail`, `FreeReaderBackgroundCard` | types.ts | 44 |
| Free Reader | stored | `"match_sweep"` (the switch's meta key) | `"free_reader_background"`, migrates | db.MATCH_SWEEP | 2 |
| Free Reader | code | `MATCH_SWEEP` | `FREE_READER_BACKGROUND` | db.MATCH_SWEEP | 10 |
| Free Reader | code | `match_sweep_on`, `set_match_sweep` | `free_reader_background_on`, `set_free_reader_background` | pipeline_routes | 9 |
| Free Reader | file | `match-sweep` (.serve/match-sweep.json, .log, -inflight.json; inventory/match-sweep.lock) | `free-reader-background`, migrates | sweep | 50 |
| Free Reader | file | `match-prepare.json` | `free-reader-prepare.json`, migrates | match.progress_path | 3 |
| Free Reader | CLI | `match-selftest` (make target) | `free-reader-selftest` | Makefile | 29 |
| Free Reader | code | `held_promo_games` | `unread_promo_games` | match.held_promo_games | 14 |
| Free Reader | wire | `"promo_held"`, `UNREAD_PROMO_HELD` (the reason code for a promo set the Free Reader skips) | `"promo_not_read"`, `UNREAD_PROMO` | match.UNREAD_PROMO_HELD | 8 |
| Free Reader | code | `matcher_pick`, `MatcherPick` | `free_pick`, `FreePick` | engine_pick | 38 |
| Free Reader | code | `reread_matcher`, `rereadMatcher`, `setRereadMatcher` | `reread_free`, `rereadFree`, `setRereadFree` | RunsComposer | 41 |
| Free Reader | code | `MATCHER_NAME_TOOLTIP` | `FREE_READER_TOOLTIP`, with the value "Marqo-B" | engines.MATCHER_NAME_TOOLTIP | 16 |
| Free Reader | screen | "Background Match" | "Free read in background" | CaptureScreen | 8 |
| Free Reader | screen | "Prepare matching" | "Set up free reader" | RunsComposer | 11 |
| Free Reader | screen | "Refresh stock photos" | "Set up free reader" | RunsComposer | 1 |
| Free Reader | screen | "Match to stock photos" | "Free Reader" | RunsComposer | 7 |
| Free Reader | screen | "Matched Free" | "Read free" | ReviewBand.COUNTS | 2 |
| Free Reader | screen | "Matching now" | "Reading now" | ReviewBand | 1 |
| Free Reader | docs | "Rig switch" | "Free read in background" | CLAUDE.md; cmd_match | 5 |
| Accepted | docs | "accuracy threshold" | "accept margin" | D2 | 2 |
| Reader failed | wire | `aside` (cards the Free Reader crashed on) | `reader_failed` (MatchState.state already has failed) | sweep.aside; types.MatchSweep | 26 † |
| Reader failed | screen | "set aside" (a Free Reader crash) | "Reader failed" | ReviewBand | 1 † |
| Paid Reader | wire | `"haiku"` (engine) | `"paid"`, migrates in cache rows and run manifests | cache.ENGINE_HAIKU; engines.Engine | 34 |
| Paid Reader | CLI | `--engine haiku` | `--engine paid` | cli/__main__.py | 13 |
| Paid Reader | code | `ENGINE_HAIKU` | `ENGINE_PAID` | cache.ENGINE_HAIKU | 18 |
| Paid Reader | code | `HAIKU_NAME_TOOLTIP` | `PAID_READER_TOOLTIP`, with the value "Claude Haiku" | engines.HAIKU_NAME_TOOLTIP | 12 |
| Paid Reader | screen | "Claude Haiku 4.5" | "Claude Haiku" | engines.HAIKU_NAME_TOOLTIP | 2 |
| Paid Reader | stored | `second_look` (run manifest, cache marker, card field) | `paid_read`, migrates | cmd_identify; join.default_router | 89 |
| Paid Reader | stored | `"second_look_unsure"` (review reason) | `"paid_read_unsure"`, migrates | routing.SECOND_LOOK_UNSURE | 4 |
| Paid Reader | code | `SECOND_LOOK_UNSURE` | `PAID_READ_UNSURE` | routing.SECOND_LOOK_UNSURE | 11 |
| Paid Reader | stored | `second_look_held`, `second_look_main`, `second_look_parked` (run counts) | `paid_read_waiting`, `paid_read_to_review`, `paid_read_parked`, migrates | cmd_join.record_join | 6 |
| Paid Reader | code | `held_second_look` | `paid_read_marker` | cmd_identify.Item | 5 |
| Paid Reader | code | `_second_look_record`, `second_looked`, `_second_look_code`, `second_look_measured`, `second_look_counts`, `_second_look_where` | `_paid_read_record`, `paid_read_done`, `_paid_read_code`, `paid_read_measured`, `paid_read_counts`, `_paid_read_where` | cmd_identify; cmd_join | 29 |
| Paid Reader | screen | "second look", "Second look" | "paid read" | RunsComposer; RunPanel; reasons.ts | 16 † |
| Paid Reader | screen | "Waiting for a Paid Look" | "Waiting for a paid read" | ReviewBand.COUNTS | 3 |
| Paid Reader | screen | "Read from the photo" | "Paid Reader" | RunsComposer | 8 |
| Paid read batch | screen | "Not read" (the pill while a batch is out) | "Paid read out" | RunsStage | 1 † |
| Paid read batch | screen | "Nothing in this send was paid" | "Nothing in this batch was paid" | RunsComposer | 1 |
| Paid read batch | code | `to_send`, `RunSend` (the cards a Read press gives the Paid Reader) | UNDECIDED: the Post ruling covers the listing press only, and "sent to Claude" is still open | cmd_identify; types.RunSend | 82 |
| Paid Reader | code | the prompt text that prompt_fingerprint hashes | keep: T1 pins the hash (t1_id_eval.PROMPT_FINGERPRINT), and a change needs a paid re-measurement | identify/prompt.py | — |
| Photo Settings | code | `DEFAULT_READING` | `DEFAULT_PHOTO_SETTINGS` | RunsComposer.DEFAULT_READING | 4 |

### Match to product renames

| Term | Layer | Name today | New name | Where | Count |
|---|---|---|---|---|---|
| Match | CLI | `banchi join` | `banchi match` | cli/__main__.py | 44 |
| Match | help | "store-backed join" | "store-backed match" | cli/__main__.py | 2 † |
| Match | file | `cmd_join` | `cmd_match`, after the Free Reader leaves it | cli/cmd_join.py | 134 |
| Match | file | `join` (the Match step's module) | `match` | pipeline/join.py | 1077 |
| Match | wire | `"join"` (run command and step; also the stored bound_by act) | `"match"`; bound_by migrates | RunsStage.COMMANDS; pipeline_routes.FREE_STEPS; master.BOUND_BY_ACTS | 150 |
| Match | stored | `joined` (run manifest flag) | `matched`, migrates after the old manifest matched moves to read_free | cmd_join.record_join | 704 |
| Match | code | `join_batch` | `match_batch` | join.join_batch | 104 |
| Match | code | `record_join` | `record_match` | cmd_join.record_join | 14 |
| Match | code | `_join_now` | `_match_now` | cmd_identify._join_now | 7 |
| Match | code | `join_key`, `JOIN_KEY_STRATEGIES` | `match_key`, `MATCH_KEY_STRATEGIES` | numbers.join_key; join.JOIN_KEY_STRATEGIES | 178 |
| Match | code | `JoinReport`, `NotJoined`, `not_joined`, `PreJoinFailure`, `GameJoin`, `game_join` | `MatchReport`, `NotMatched`, `not_matched`, `PreMatchFailure`, `GameMatch`, `game_match` | join; cmd_join; resolve | 170 |
| Match | wire | `nothing_to_join` | `nothing_to_match` | cmd_join | 24 |
| Match | code | `str.join`, `os.path.join`, `JoinedStr`, `JoinLiteral`, `CommaJoin` | cannot move: Python's and the scanners' own names, not the Match step | everywhere | 1233 |
| Match | screen | "Join again" | "Match again" | RunPanel | 17 |
| Match | screen | "Join with an export" | "Match with a Product List" | RunPanel | 1 |
| Matched | stored | `matched` (run manifest: the Free Reader's accepted count) | `read_free`, migrates | cmd_identify; RunPanel.matchReceipt | 18 |
| Matched | wire | `matched_here`, `matched_keys` (the Free Reader's accepted cards) | `read_free_here`, `read_free_keys` | pipeline_routes.do_pipeline_match_sweep; types.MatchSweep | 42 |
| Matched | code | `matchReceipt` (what the Free Reader did) | `freeReadReceipt` | RunPanel.matchReceipt | 2 |
| Disputed | code | `hold_sku` | `bind_disputed_sku` | master.Inventory | 48 |
| Disputed | code | `held_review_candidates` | `disputed_review_candidates` | identity_binding.held_review_candidates | 9 |
| Disputed | code | `held_review_entry` | `disputed_review_entry` | identity_binding.held_review_entry | 9 |
| Product | screen | "Listed as" | "Product" | CardHero.listedAsFact | 14 |
| Product | wire | `listing`, `listing_differs` (on a card: its SKU's catalog name and number) | `product`, `product_differs` | types.InventoryCard; capture_server | 35 |
| Read | wire | `reading_differs` (the read disputes the card's shown name or number) | `read_differs` | types.InventoryCard; CardHero | 29 |
| Product List | stored | `.exports` (inventory/.exports/<game>/) | `.product-lists`, migrates | games; pipeline_routes | 96 |
| Product List | wire | `export_needs_hint` | `product_list_needs_hint` | games.export_needs_hint | 42 |
| To Review | code | `MAIN` (the To Review queue) | `TO_REVIEW` | queues.MAIN | 24 |
| To Review | CLI | "main queue" | "to review" | cmd_identify._held_now; cmd_queue | 56 |
| Waiting for you | CLI | "held for review" | "waiting for you" | cmd_identify._held_now | 19 |
| Waiting for you | code | `_held_now` | `_waiting_now` | cmd_identify._held_now | 5 |
| Waiting for you | screen | "held for you" | "Waiting for you" | ReviewQueue | 1 |
| Closed | route | `/review/<box>/<index>/stand-down` | `/review/<box>/<index>/close`; a retire stays on /retire | capture_server.do_review_stand_down | 10 |
| Closed | code | `do_review_stand_down` | `do_review_close` | capture_server.do_review_stand_down | 15 |
| Closed | code | `STAND_DOWN_REASONS`, `check_stand_down_reason`, `UnknownStandDownReason` | `REVIEW_CLOSE_REASONS`, `check_review_close_reason`, `UnknownReviewCloseReason` (orders already own CLOSE_REASONS) | queues.STAND_DOWN_REASONS | 16 |
| Closed | code | `standDown`, `undoStandDown`, `StandDownReason`, `StandDownResult`, `onStandDown`, `'stand_down'` (a close choice) | `closeReview`, `undoCloseReview`, `ReviewCloseReason`, `ReviewCloseResult`, `onCloseReview`, `'close'` (dialogs already own onClose) | server.ts; types.ts; ReviewQueue | 26 † |
| Closed | stored | `stood_down` (event) | `review_closed`, migrates (a sealed box's state is already closed) | capture_server.do_review_stand_down | 28 |
| Closed | screen | "Stand down" (the Close dialog's group) | "Kept" | ReviewQueue | 1 † |
| Closed | screen | "left in place" (the reason line) | "Kept" | ReviewQueue | 3 † |
| Closed | stored | `cleared_by_human` (answered or closed) | UNDECIDED: no glossary word covers both | queues.QueueEntry | 169 |
| Skipped | code | `deferred` (cards skipped this sitting) | `skipped` | ReviewQueue | 8 † |
| Review queue order | code | `sort_key` (QueueEntry.sort_key: the order of a review queue) | `queue_order`; it moves before the Sort Key takes sort_key | queues.sort_key | 18 |

### Price renames

| Term | Layer | Name today | New name | Where | Count |
|---|---|---|---|---|---|
| Threshold | code | `DEFAULT_CUTOFF` | `DEFAULT_THRESHOLD` | corpus.DEFAULT_CUTOFF | 12 |
| Threshold | screen | "Cut-off", "cut-off" (the store's price line) | "Threshold" | Pricing; standing | 54 † |
| Threshold | code | `cutoff`, `CUTOFF` (TS names for the store's price line) | `threshold`, `THRESHOLD` | Pricing; standing | 3 † |
| Threshold | docs | "cut-off" | "Threshold" | docs/ | 48 † |
| Threshold | wire | `below_floor`, `BELOW_FLOOR`, `REFUSED_BELOW_FLOOR` | `below_threshold`, `BELOW_THRESHOLD`, `REFUSED_BELOW_THRESHOLD` | pricing; reprice; sendguard | 31 |
| Threshold | code | `clamp_floor` | `clamp_threshold` | pricing.clamp_floor | 12 |
| Threshold | code | `pricing.THRESHOLD`, `pricing.FLOOR` | cannot move: the ruling deletes both constants, and every caller reads the store's Threshold | pricing | 40 |
| Threshold | wire | `"listable"` (the bucket at or above) | `"above_threshold"` | Pricing; pipeline_routes | 21 |
| Threshold | wire | `"under_cut_off"` (a Post row's reason code) | `"below_threshold"` | SendCard; cmd_emit | 11 |
| Threshold | wire | `under_cutoff` (a count of cards under the line) | `below_threshold` | types.ts; value | 16 |
| Threshold | wire | `"sub_threshold"` (the bucket under) | `"below_threshold"` (the join report's below_threshold and the split file already say below) | Pricing; pipeline_routes | 16 |
| Threshold | CLI | `--listed-only`, `listed_only` | `--above-threshold-only` | cli/__main__.py; cmd_emit | 62 |
| Threshold | file | `import-listed.csv` | `import-above-threshold.csv`, migrates | cmd_emit | 25 |
| Threshold | file | `import-subthreshold.csv` | `import-below-threshold.csv`, migrates | cmd_emit | 15 |
| Threshold | docs | "labor bar" | delete: the ruling removes the bar | D9; pricing | 9 |
| Flat Price | stored | `sub_threshold` (policy key) | `flat_price`, migrates | corpus.Policy | 41 |
| Flat Price | stored | `"floor"` (flat at the Threshold) | `"threshold"`, migrates | decisions.FLOOR_CHOICE; readiness.FLOOR_CHOICE | 62 |
| Flat Price | code | `FLOOR_CHOICE` | `THRESHOLD_CHOICE` | decisions.FLOOR_CHOICE; readiness.FLOOR_CHOICE | 24 |
| At Market | stored | `"match"` (price rule) | `"at_market"`, migrates | pricing.RULE_MATCH | 16 † |
| At Market | code | `RULE_MATCH` | `RULE_AT_MARKET` | pricing.RULE_MATCH | 17 |
| At Market | stored | `market_match` (preset key) | `at_market`, migrates | cmd_join.PRESETS; Pricing.PRESETS | 17 |
| At Market | screen | "Match market" | "At Market" | Pricing.PRESETS | 10 |
| Move Size | code | `movers.THRESHOLD` | `MOVE_SIZE` | movers.THRESHOLD | 2 † |
| Envelope Limit | code | `TRACKING_THRESHOLD` | `ENVELOPE_LIMIT` | shipping.TRACKING_THRESHOLD | 4 |
| Envelope Limit | code | `THRESHOLD` (OrdersShipStage's $50 line) | `ENVELOPE_LIMIT` | OrdersShipStage | 4 † |
| Threshold | code | `THRESHOLD` (ReviewQueue's copy of pricing.THRESHOLD) | cannot move: the ruling deletes it, and Review's color bands read the store's Threshold | ReviewQueue | 5 † |
| Envelope Limit | wire | `value_at_threshold`, `VALUE_AT_THRESHOLD` | `value_at_envelope_limit`, `VALUE_AT_ENVELOPE_LIMIT` | shipping.VALUE_AT_THRESHOLD | 29 |
| Market Price | stored | `readings`, `readings_sources` (tables) | `market_prices`, `market_price_sources`, migrates | db; readings | 567 |
| Market Price | CLI | `banchi readings` | `banchi market-prices` | cli/__main__.py | 24 |
| Market Price | help | "the cached market-reading table" | "the cached market price table" | cli/__main__.py | 1 † |
| Market Price | file | `cmd_readings`, `readings` (the module) | `cmd_market_prices`, `market_prices` | cli/cmd_readings.py; pipeline/readings.py | 55 |
| Market Price | code | `_readings`, `readings_for_rows`, `readings_walk` | `_market_prices`, `market_prices_for_rows`, `market_prices_walk` | pipeline_routes._readings; readings | 113 |
| Withheld | screen | "held back" (a SKU you keep out) | "withheld" | Pricing; Gallery | 4 † |
| Withheld | CLI | `--held` (banchi prices show) | `--withheld` | cli/__main__.py; cmd_prices | 19 |
| Withheld | help | "list every card held back" | "list every withheld card" | cli/__main__.py | 1 † |
| Withheld | code | `HOLD_SHORT`, `heldReason`, `filterHeld`, `setFilterHeld` | `WITHHOLD_SHORT`, `withheldReason`, `filterWithheld`, `setFilterWithheld` | Pricing | 14 |
| Withheld | code | `is_hold`, `hold_lost`, `_hold_before` (a price answer that withholds) | `is_withheld`, `withheld_lost`, `_withheld_before` | corpus.Answer | 23 |
| Withheld | code | `holdFor`, `setHoldFor`, `holdButtons` | `withholdFor`, `setWithholdFor`, `withholdButtons` | Pricing | 18 |
| Withheld | wire | `held` (Pricing's progress count, and the data-answer and data-tile value) | `withheld` | Pricing | 36 † |
| Withheld | stored | `"unlisted"` (withheld with no reason) | UNDECIDED: a withheld record carries a reason, and this one has none | standing.isWithheld | 19 † |
| On hand | code | `holdings`, `held_market_cutoff`, `build_holdings_report` (a SKU with a copy on hand) | `on_hand`, `on_hand_top_price`, `build_on_hand_report` | pipeline/holdings.py | 132 |
| On hand | wire | `held_market_readings` | `on_hand_market_prices` | pipeline_routes; types.InventoryCard | 5 |
| On hand | route | `/pipeline/holdings-value` | `/pipeline/on-hand-value` | pipeline_routes; server.getHoldingsValue | 14 |

### Post to TCGplayer renames

| Term | Layer | Name today | New name | Where | Count |
|---|---|---|---|---|---|
| Post | route | `/pipeline/send`, `/pipeline/sends` | `/pipeline/post`, `/pipeline/posts` | send_routes.do_send | 56 |
| Post | route | `/pipeline/markdowns/<stamp>/send` | `/pipeline/markdowns/<stamp>/post` | send_routes | 8 |
| Post | file | `send_routes` | `post_routes` | server/send_routes.py | 435 |
| Post | code | `do_send`, `do_sends` | `do_post`, `do_posts` | send_routes | 129 |
| Post | code | `push_to_staged` (the upload of an Import File to Staged) | `post_to_staged` | tcg_import.push_to_staged | 11 |
| Post | file | `sendguard` | `postguard` | pipeline/sendguard.py | 48 |
| Post | stored | `inventory/sends/` | `inventory/posts/`, migrates | send_routes | 2 |
| Post | code | `sends_dir`, `SENDS_DIR` | `posts_dir`, `POSTS_DIR` | send_routes | 41 |
| Post | CLI | `--send-dir` | `--post-dir` | cmd_emit | 4 |
| Post | help | "read just before this send" | "read just before this post" | cli/__main__.py | 1 † |
| Post | stored | `"sending"` (receipt phase) | `"posting"`, migrates | send_routes.PHASE_SENDING | 30 |
| Post | code | `PHASE_SENDING` | `PHASE_POSTING` | send_routes.PHASE_SENDING | 6 |
| Post | stored | `"send"` (receipt kind) | `"post"`, migrates | send_routes; SendCard | 15 † |
| Post | file | `SendCard` | `PostCard` | app/src/SendCard.tsx | 18 |
| Post | code | `sendCopies`, `sendsStatus`, `takeBackSend`, `dismissSendWarning`, `sendFileUrl`, `sendMarkdown` | `postCopies`, `postsStatus`, `takeBackPost`, `dismissPostWarning`, `postFileUrl`, `postMarkdown` | server.ts | 19 |
| Post | wire | `SendSummary`, `SendsStatus`, `SendTrim` | `PostSummary`, `PostsStatus`, `PostTrim` | types.ts | 34 |
| Post | code | `refresh_before_send`, `send_in_progress`, `send_unknown`, `EmptySend`, `MAX_SEND_QUANTITY`, `sendAnyway`, `lastSend` | `refresh_before_post`, `post_in_progress`, `post_unknown`, `EmptyPost`, `MAX_POST_QUANTITY`, `postAnyway`, `lastPost` | pipeline_routes; send_routes; decisions; SendCard | 62 |
| Post | wire | `nothing_to_send` | `nothing_to_post` | send_routes; reprice | 19 |
| Post | wire | `send_held` (a Post that waits on the live check) | `post_waiting` | send_routes; SendCard | 10 |
| Post | screen | "Send", "Sending" (the listing press) | "Post", "Posting" | SendCard; RunsStage.STAGES; Pricing | 31 † |
| Post | code | `send_response`, `send_header`, `send_error`, `end_headers` (http.server) | cannot move: Python's standard library names them | capture_server | 62 |
| Post | screen | "Send Anyway" | "Post Anyway" | SendCard | 11 |
| Post | screen | "Price and send" | "Price and post" | RunPanel.TITLES | 4 |
| Post | screen | "Nothing to send" | "Nothing to post" | SendCard | 2 † |
| Lock | file | `sendclaims` | `postlocks` | store/sendclaims.py | 21 |
| Lock | stored | `send_claims` (table) | `post_locks`, migrates | sendclaims | 76 |
| Lock | code | `SendClaim`, `SendClaims`, `SendClaimRefused` | `PostLock`, `PostLocks`, `PostLockRefused` | sendclaims | 29 |
| Lock | CLI | `--send-claim` | `--post-lock` | cmd_emit | 4 |
| Lock | code | `UnreadableClaim`, `releaseUnreadableClaim`, `restoreUnreadableClaim` | `UnreadableLock`, `releaseUnreadableLock`, `restoreUnreadableLock` | server.ts; types.ts | 23 |
| Counted as posted | stored | `pushed` (a SKU's copies written into an Import File) | `posted`, migrates | master.Listing | 279 † |
| Counted as posted | stored | `PUSHED` (a v1 card state) | cannot move: v1 files on disk carry it, and the reader accepts both | master.LEGACY_STATES | 51 |
| Waiting to compare | screen | "Written" (run pill) | "Waiting to compare" | RunsStage | 1 † |
| Counted as listed | screen | "Listing-held" | "Counted as listed" | BoxOps | 1 |
| Counted as listed | screen | "Release the listing hold" | "Stop counting as listed" | BoxOps | 6 |
| Counted as listed | code | `_listing_hold` | `_counted_as_listed` | capture_server._listing_hold | 32 |
| Counted as listed | wire | `still_held` (release plan and receipt) | `still_counted` | master.Listing; capture_server | 23 |
| Removed by you | stored | `held_copies` | `removed_copies`, migrates | master.Listing | 19 |
| Removed by you | stored | `unheld` (receipt field) | `taken_back_removed`, migrates | send_routes.do_unhold | 46 |
| Removed by you | route | `/pipeline/held/<sku>/unhold`, `/pipeline/held/<sku>/hold` | `/pipeline/removed/<sku>/take-back`, `/pipeline/removed/<sku>/undo` | send_routes.do_unhold; send_routes.do_rehold | 9 |
| Removed by you | code | `do_unhold`, `do_rehold`, `_hold_removed`, `unholdCopies`, `reholdCopies` | `do_take_back_removed`, `do_undo_take_back`, `_mark_removed`, `takeBackRemoved`, `undoTakeBack` | send_routes; server.ts | 30 |
| Removed by you | screen | "Unhold" | "Take them back" | Pricing | 3 † |
| Trimmed | screen | "held back: TCGplayer already had them" | "Trimmed: TCGplayer already had them" | SendCard.TrimList | 4 |
| Running | wire | `live` (a run's process is running) | `running` | types.RunSummary | 9 † |
| Counted | code | `readingAgo`, `readingBound`, `readingDays`, `readingExact`, `ReadingAge`, `STALE_READING_DAYS`, `staleReading` | `countedAgo`, `countedBound`, `countedDays`, `countedExact`, `CountedAge`, `STALE_COUNTED_DAYS`, `staleCounted` (orderView already owns staleCount) | cardState; CardLocations | 45 |
| Counted | screen | "read {ago}", "not read yet" (the age of a live figure) | "counted {ago}", "Not counted yet" | CardLocations.ReadingAge | 1 † |
| Check what is live | CLI | `banchi reconcile --live` | UNDECIDED: check-live is close to the live-check route | cmd_reconcile | 17 |
| Check what is live | route | `/pipeline/reconcile-live` | UNDECIDED, as the row above | pipeline_routes.do_reconcile_live | 11 |
| Check what is live | screen | "Match the store" | "Update store counts" | LiveReconcile | 5 |
| Check what is live | screen | "Store reconciled" | "Store counts updated" | LiveReconcile | 1 |
| Compare | CLI | `banchi reconcile <run-dir>` | `banchi compare` | cmd_reconcile | 12 |
| Compare | wire | `"reconcile"` (run command and step) | `"compare"` | RunsStage.COMMANDS; pipeline_routes.FREE_STEPS | 45 † |
| Live beyond on hand | CLI | `--phantoms` | `--live-beyond-on-hand` | cmd_reconcile | 11 |

### Sell and ship renames

| Term | Layer | Name today | New name | Where | Count |
|---|---|---|---|---|---|
| Reserved for order | screen | "Held for order" | "Reserved for order" | Orders | 1 |
| Reserved for order | wire | `held_by` (PickRow: a copy already recorded against an order line) | `reserved_by` | types.PickRow; capture_server | 30 |

### Boxes renames

| Term | Layer | Name today | New name | Where | Count |
|---|---|---|---|---|---|
| Box | screen | "Pick the drawer" | "Pick the box" | CaptureScreen | 1 |
| Box | screen | "Fewest drawers" | "Fewest boxes" | Orders | 12 |
| Card 17 | wire | `slot` (Place.slot and PlaceNeighbor.slot: the count in the section) | `number_in_section` (PickRow.card_number is the Collector Number) | types.Place; join.Position | 70 † |
| Collector Number | wire | `card_number` (PickRow: the printed number) | `collector_number` | types.PickRow; Orders | 22 |
| Card 17 | docs | "slot numbers are not the truth" | "the Key is not the place" | CLAUDE.md | 5 |
| Sort Key | stored | `ord` (cards column) | `sort_key`, migrates | db, schema 13 | 7 † |
| Sort Key | wire | `order` (Card.order, a fraction) | `sort_key` | master.Card; types.InventoryCard | 13 † |
| Sort Key | code | `order_key` (master.Card's property: the fraction) | `sort_key` | master.Card | 6 |
| Map | code | `BoxShelf` | `BoxMap` | app/src/BoxShelf.tsx | 13 |
| Map | help | "on the Shelf" | "on the Map" | App.SHORTCUTS | 6 |
| Deleted Boxes | screen | "Deleted boxes shelf" | "Deleted Boxes" | BoxShelf | 41 |
| On hand | screen | "On Your Shelf" | "On hand" | PriceFacts | 2 |
| On hand | screen | "In stock" | "On hand" | Orders; BoxBrowse | 3 † |
| Taken out | stored | `"pulled"` (retire reason) | `"taken_out"`, migrates | master.RETIRE_REASONS; cardState.RETIRE_REASONS | 17 |
| Taken out | screen | "Removed" (the label of pulled) | "Taken out" | cardState.RETIRE_REASONS | 1 |
| Taken out | screen | "Pulled" (the Close dialog's label) | "Taken out" | ReviewQueue.CLOSE_CHOICES | 1 |

### Across the app renames

| Term | Layer | Name today | New name | Where | Count |
|---|---|---|---|---|---|
| Phone width | docs | "PHONE THRESHOLD" (a comment: the phone layout's width) | "PHONE WIDTH" | Orders | 2 † |
| Panel | help | "queue drawer" | "queue panel" | App.SHORTCUTS | 2 |
| Card ID | CLI | `banchi cards name` | `banchi cards ids` | cmd_cards | 3 |
| Card ID | code | `UnnamedCard` | `NoCardId` | master.UnnamedCard | 6 |
| Lock | code | `SubmissionClaims`, `releaseSubmission`, `ClaimRelease` (the Paid Reader's lock) | `SubmissionLocks`, `releaseSubmissionLock`, `LockRelease` | submissions; server.ts | 24 |
| Lock | screen | "release the claim" | "release the lock" | capture_server | 2 |
| Archive sweep | CLI | `banchi archive sweep` (the price-history sweep) | keep: ruling "banchi archive sweep keeps its name" | cmd_pricearchive | 24 |
| Catalog | docs | "`catalogue`" | "catalog" | docs; comments | 553 |
| Finish | docs | "PRINTING" (Normal / Foil, TCGplayer's subTypeName) | "finish" | pricehistory | 3 |

### Names with two meanings

Each line names the meanings that share an old name, and how to tell them apart. A meaning that
stays keeps its name.

- `match`: the Free Reader (`identify/match.py`, `cmd_match`, `banchi match`, `/pipeline/match`,
  `MatchState`) moves to free reader names. Then the Match step takes `match`. The route
  `/pipeline/runs/<name>/match` already means the Match step. The price rule `"match"` is At
  Market. The search matcher of D271 (every search uses one matcher) and `difflib.SequenceMatcher`
  stay.
- `matched`: the run manifest's count of the Free Reader's accepted cards, with `matched_here` and
  `matched_keys`, becomes `read_free`. On screen, "Matched" means that a card has a product, and
  it stays.
- `join`: the Match step (`pipeline/join.py`, `cmd_join`, the `"join"` command). `str.join`,
  `os.path.join` and the scanners' `JoinedStr` stay. A call on a string or a path is never the
  Match step.
- `identification`: a read, in most files. In `banchi cards checks` (D239, four stored-data
  checks) it means the identity checks.
- `read`: the new card state `"read"` and `identity_source` `"read"` (a card bound by its read)
  are two fields. Tell them apart by the field name. The `UNREAD_*` reason codes are reads, and
  stay.
- `sweep`: the Free Reader's background (`identify/sweep.py`, `--sweep`, `MATCH_SWEEP`) becomes
  background. `banchi archive sweep` stays.
- `held` and `hold`: each glossary meaning has its own rows: Withheld, Counted as listed, Removed
  by you, Disputed, Waiting for you, Reserved for order, Trimmed, On hand, and the promo sets that
  the Free Reader skips. Plain-English holds stay: a screen area that holds its size (`useHeld`,
  D313, nothing on screen moves unless the person moved it) and a held restart (`held_since`).
  Never replace "hold" as a bare word: `threshold` contains it.
- `send`: the listing press becomes Post. The Paid Reader's batch (`to_send`, `RunSend`) is
  UNDECIDED. The `http.server` methods (`send_response`, `send_header`, `send_error`) stay.
- `post` and `posting`: `post` is also an HTTP POST. D243 (a posted price is recorded once)
  already calls a price that reached an Import File a posting, in `cmd_emit`. That is the same
  meaning as Post, so the receipt phase `"posting"` agrees with it.
- `claim`: Claims, a card's set and finish claims (BoxOps, `photos.CLAIM_WIRE_NAMES`), stay. The
  post lock (`send_claims`) and the Paid Reader's lock (`SubmissionClaims`) become Lock. Port-slot
  claims (`scripts/port-slots.py`) and photo reclaim (D89, a sold card's photograph is reclaimed
  on purpose) stay.
- `reading`: Market Price (the `readings` tables, `banchi readings`), Counted (the age of a live
  figure, `readingAgo`), Photo Settings (`DEFAULT_READING`) and a read (`reading_differs`).
- `cutoff` and `cut_off`: only the store's price line becomes Threshold. These are dates and
  stay: reprice's `cut_off`, the Free Reader's `cutoff_day` and the orders backlog's
  `_reconcile_cutoff`. `NAME_MATCH_CUTOFF` (a name-match score) stays. `held_market_cutoff` is
  On hand's top price.
- `floor`: the Threshold (`clamp_floor`, `below_floor`, the `"floor"` choice) becomes threshold.
  The Free Reader's `FLOOR_MIN` and the design floors (D50, feedback is the product's) stay.
- `THRESHOLD`: `pricing.THRESHOLD` and ReviewQueue's copy go. `movers.THRESHOLD` becomes Move
  Size, and OrdersShipStage's `THRESHOLD` becomes Envelope Limit.
- `stand_down`: Review's Close. An order line's stand-down (D113, a line closes three ways) stays,
  and it owns `CLOSE_REASONS`.
- `closed`: Review's Closed, a sealed box's state `closed` and the camera's closed state on
  Capture. The Review event becomes `review_closed`.
- `variant`: Finish. The kit Button's prop stays. `LogoVariant` is UNDECIDED. `invariant`
  contains the word.
- `order` and `order_key`: `Card.order` and `master.Card`'s `order_key` are the Sort Key. A
  buyer's order stays: `store/orders.order_key`, `ResolvedLine.order` and the Fulfillment screen.
- `sort_key`: today it is the order of a review queue (`queues.sort_key`). It becomes
  `queue_order` first, so that the Sort Key can take the name.
- `slot` and `card_number`: `Place.slot` is Card 17, and becomes `number_in_section`.
  `PickRow.card_number` is the Collector Number. `EMPTY_SLOT`, `REQUEST_SLOTS`, `PHOTO_SLOTS` and
  port slots stay.
- `live`: `RunSummary.live` becomes Running. Copies live on TCGplayer stay, and so does
  `/pipeline/live-check`. `reconcile --live` is UNDECIDED.
- `reconcile`: Compare (`banchi reconcile <run-dir>`, the `"reconcile"` step). `reconcile --live`
  is UNDECIDED. `--phantoms` is Live beyond on hand. The orders backlog reconcile
  (`/orders/reconcile-backlog`) stays.
- `pushed`: Counted as posted (`Listing.pushed`). `push_to_staged` becomes `post_to_staged`. A
  local `pushed` in ReviewQueue is another word.
- `aside`: Reader failed (`sweep.aside`). Other "set aside" text keeps its plain meaning.
- `listing`: on a card, `listing` is its Product. The `Listing` class (`master.Listing`, a SKU's
  copies) stays.
- `product`: on a card it becomes the Product. On a code card, `product` is the sealed product
  that a stack came out of, and it stays while code cards are dormant.
- `sub_threshold`: the bucket becomes `below_threshold`, and the policy key becomes `flat_price`.
  The key lives in `corpus.Policy` and `prices.json`. The bucket is a value in the pricing payload.
- `free` and `paid`: the engine values `"free"` and `"paid"` are new. `FREE_STEPS` (steps that cost
  nothing) and the money word "paid" stay. Only the `engine` field holds a reader.

### Do not replace inside

These names contain an old word and are not renames: `identifier`, `identity` and `identity_*`
(Card ID, not a read), `threshold` (contains "hold"), `invariant` (contains "variant"),
`threading` and `ThreadingHTTPServer` (contain "reading"), `SequenceMatcher`, `unread` and
`UNREAD_*`. Match whole words only (`git grep -w`).

### Rename order

Some old names pass to a new meaning. Those renames go in this order, in separate merges:

1. The Free Reader leaves `match` first: its module, `cmd_match`, `banchi match`, `/pipeline/match`
   and the `Match*` wire types. Then the Match step takes `match`: `pipeline/join.py`, `cmd_join`
   and `banchi join`.
2. The manifest's `matched` (the Free Reader's count) becomes `read_free`. Then `joined` becomes
   `matched`.
3. `queues.sort_key` becomes `queue_order`. Then the Sort Key takes `sort_key`.
4. `pricing.THRESHOLD`, `pricing.FLOOR` and ReviewQueue's copy go, and `movers.THRESHOLD`,
   `TRACKING_THRESHOLD` and OrdersShipStage's `THRESHOLD` get their new names. Then the cut-off and
   floor names become threshold, and every threshold left in code is the store's price line.

### Not yet mapped

The tables above hold the names that each term's inventory found, and the names next to them. A
scan for compound names that contain an old word found more. Some of them are other words that
contain the old word, for example `ThreadingHTTPServer`, `isIdentifier` or `useHeld`. Before a lane
renames a name from this list, it adds the name to the tables above as a row, and the reviewer
checks that row like the others.

| Old word | Names not in a row | Lines | The five largest |
|---|---|---|---|
| send | 142 | 770 | `send_portal`, `sendPosts`, `SENDS_NONE`, `sendSummary`, `_banner_send` |
| identify, identification | 59 | 334 | `isIdentifier`, `IDENTIFICATIONS`, `IDENTIFY`, `MalformedIdentification`, `identify_images` |
| second look | 7 | 22 | `secondLookRows`, `SECOND_LOOK_ENTRY`, `secondLook`, `check_second_look_routing`, `check_second_look_agreement` |
| marqo, haiku | 3 | 20 | `marqo_tip`, `haiku_tip`, `check_haiku_press_never_sends_an_empty_slot` |
| matcher | 13 | 45 | `matcher_read`, `SequenceMatcher`, `_fake_matcher`, `matcherRead`, `matcher_run` |
| sweep | 62 | 252 | `routeSweep`, `sweepEveryRoute`, `engine_sweep`, `EXCLUDED_FROM_SWEEP`, `sweepOn` |
| join | 83 | 322 | `JOINED`, `t3_join_coverage`, `JOINS`, `leave_joined`, `openJoinOptions` |
| cut-off | 16 | 36 | `DID_YOU_MEAN_CUTOFF`, `_reconcile_cutoff`, `cutoff_in_future`, `CutoffPanel`, `check_catalog_claim_rank_and_no_cutoff` |
| stand down | 18 | 64 | `not_stood_down`, `onStandDownOrder`, `_reverse_stand_down`, `standDowns`, `standDownCall` |
| held, hold | 142 | 586 | `holdNow`, `held_out`, `useHeld`, `held_sku`, `photoHeld` |
| reading | 77 | 471 | `live_reading`, `atReading`, `card_reading`, `ThreadingHTTPServer`, `READINGS` |
