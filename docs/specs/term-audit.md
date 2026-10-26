# Banchi terminology audit

Point: 25 clashes confirmed. Worst: "Match" covers three steps, and the free reader has 11 names. Seven are pure rename-the-screen jobs. Four need your ruling first (list at the end). All checks are on origin/main.

1. **Match.** "Match" means the join step, the free image read, a live store check, the `match` price rule and the search ranker.
 Where: RunPanel.tsx ("Matched N cards free … waiting to be matched", one sentence, two steps); RunPanel.tsx step "Match" but  button "Join again"; LiveReconcile.tsx "Match the store".
 Proposed: "Match" = the join step only ("Match again", "Match with an export…"). Image read = "free read" (see 2). Live check button = "Update store counts". Price rule = "At market" on screen. Search = "search".
 Size: small. Screen and records only. Code keeps `join`, `match`, `RULE_MATCH`, `banchi match`. Renaming the CLI is medium and your call.
2. **Free reader.** One on-Mac image reader has 11 names: free reader, matcher, marqo-b, "Match to stock photos", "Background Match", "Prepare matching", "Refresh stock photos", fingerprints, background reader, sweep, "Rig switch".
 Where: CaptureScreen.tsx "Background Match" inside the "Rig" card; CLAUDE.md and cli/cmd_match.py say "Rig switch" (no control has that label); RunsComposer.tsx.
 Proposed: thing = "free reader", one answer = "free read". Switch "Free read in background". One setup press "Set up free reader" (first time and refresh). "N stock photos ready". "Sweep" alone is banned.
 Size: medium. About 10 screen strings, 2 doc lines, CLI messages. No wire or store change. Code keeps `marqo-b`, `matcher`, `fingerprints`, `match --sweep`.
3. **Paid read.** One paid Claude read has 6 names: paid read, second look, paid look, "Read from the photo", Haiku, press.
 Where: ReviewBand.tsx "Waiting for a Paid Look"; RunsComposer.tsx "Read from the photo"; engines.ts tooltip "Claude Haiku 4.5" vs identify/prompt.py `claude-haiku-5-5` (app/tests/run-panel.spec.ts pins 4.5).
 Proposed: "paid read" only. Engine option "Paid read". Band "Waiting for the paid read". "Second look" is no longer a name. Model name: unmeasured. prompt.py says the banked T1 score is Haiku 4.5, so the tooltip may be on purpose. Your ruling needed. D2 (identify is Haiku vision) has a title that says Haiku does all, but its body says the owner picks free or paid. Retitle it.
 Size: small. Strings and one test only.
4. **Identify.** The run panel calls Identify "the only step that spends money", but the default reads free first. "Identified" means two things.
 Where: RunPanel.tsx vs  ("Both are free for cards already read"); cli/__main__.py "THE ONE THAT COSTS MONEY" vs  default marqo-b; capture_server.py says a card the reader already answered "carries no SKU yet … Identify it first".
 Proposed: "Identify" = whole step, free first. Only the paid read costs money. Card state "Identified" = reader answered. New word "Matched" = has a SKU. Refusals say "Match it first" or "Answer it in Review".
 Size: small to medium. Strings only. State codes and `identify` keep. D321 (runs join themselves) already sets identified before the join.
5. **Held.** "Held" names eight states with eight different fixes.
 Where: Pricing.tsx "{n} held back" (your choice) beside the send guard's "held back" (SendCard.tsx, automatic); BoxOps.tsx "Listing-held"/"Release the listing hold" vs Pricing.tsx "Release"; cli/cmd_identify.py and  (two meanings in one report).
 Proposed: "Held back" = Pricing choice only. Guard trim = "Trimmed: TCGplayer already had them". Review `held for you` (ReviewQueue.tsx) = "Waiting for you". Orders.tsx "Held for order" = "Reserved for order". Disputed SKU (cmd_cards.py) = "Disputed". Box = "Still listed"; the box action word needs your ruling (what it does at TCGplayer is unknown).
 Size: medium. Screen and records only. Code keeps `held`, `withheld`, `held_copies`, `still_held`, `hold_sku`.
6. **Read.** "Read" means one answer for a photo, a price snapshot, the age of a listing count, a press setting, and stored `identity_source=read`.
 Where: CardLocations.tsx "read {ago}"/"not read yet"; RunsStage.tsx pill "Not read" (batch out, not collected); store/master.py IDENTITY_READ; RunsComposer.tsx DEFAULT_READING (crop and size).
 Proposed: "read" = one answer for one photo. Price snapshot = "market price" (CLI `readings` keeps). Count age = "counted 3 days ago"/"Not counted yet". Pill = "Paid read out". Press setting = "Photo settings". Prose calls `identity_source=read` "disputed". Also delete docs/specs/batch-script.md (lists a `read` card state as open); D321:15 says it was dropped.
 Size: medium. Stored `read` value and `read_name` fields keep (renaming them is large).
7. **Cut-off.** One price line has 5 names and 2 defaults. Other lines share the words.
 Where: pipeline/pricing.py THRESHOLD 0.40,  FLOOR 0.40, vs corpus.py DEFAULT_CUTOFF "0.49"; server/pipeline_routes.py sends one value as both "threshold" and "floor"; ReviewQueue.tsx hard-codes 0.4.
 Proposed: "Cut-off" only (D9: cut-off is also the price floor). Flat price = sub_threshold's value. Shipping $50 line (shipping.py) = "envelope limit". Movers 10% (movers.py) = "move size". "Parked under the threshold" → "Parked under the cut-off".
 Size: screen small; the duplicate wire field and constants are medium. Unmeasured: does Review parking follow an edited cut-off? Your ruling needed.
8. **Review queue / parked / answered.** "Review queue" means both piles or only the main one. "Answered" is printed for a person's pick and for a stand-down.
 Where: RunPanel.tsx ("See N parked in the review queue") vs BoxBrowse.tsx ("Waiting in the {parked} queue"); cli/cmd_identify.py "main queue"; cli/cmd_queue.py "answered, left alone"; store/queues.py (one flag, two meanings).
 Proposed: "Review" = screen and both piles. "To review" = main pile (CLI "main queue" → "to review"). "Parked" = low-value pile, no answer owed. ReviewBand.tsx "set aside" → "Reader failed". "Answered" = a person picked. "Stood down" = closed, card unchanged.
 Size: small to medium. Code keeps MAIN, PARKED and the `cleared_by_human` flag (stored).
9. **Send.** "Send" means a paid read batch, the listing press, and a price-change upload. "Pushed" and "Written" say a copy left when it may not have.
 Where: RunsComposer.tsx "Nothing in this send was paid for" and SubmissionClaims.tsx (paid) vs send_routes.py (listings, D273: one press sends listings live); cmd_emit.py "pushed N" while  says import by hand; RunsStage.tsx pill "Written".
 Proposed: "Send" = listing press only. Paid batch = "paid read batch". Emit text = "wrote the import file". `pushed` = "counted as sent". Pill "Written" → "Waiting to compare". Markdown = "price change" (SendCard.tsx already says so; server refusals say "Markdown 2026…").
 Size: small to medium. Stored stage `pushed` and class `Send` keep.
10. **Export.** "Export" means four different TCGplayer files plus a run's output file.
 Where: RunPanel.tsx ("Join with an export…"); LiveReconcile.tsx ("My Pricing"); RunFiles.tsx ("CSV export"); pipeline_routes.py says "the Pricing tab" (TCGplayer's tab, not our #/pricing).
 Proposed: "Product list" (Filtered CSV, per game, D166: export belongs to the game); "Live listings file" (My Pricing); "Staged file" (Export From Staged); "Shipping file"; run output "Import file". TCGplayer's own button names stay as TCGplayer spells them.
 Size: medium. Screen and docs only. Code keeps `export`.
11. **Catalog.** "Catalog" means the vendored Pokemon data, TCGplayer's product list, and the 16.7 GB image mirror. It is also spelled the British way, with "-ue".
 Where: pipeline/catalog.py; D166 ("catalog export"); app/src/server.ts matchRun (British spelling in its message); CLAUDE.md `make catalog-mirror`.
 Proposed: "Card data" = vendored data. "Product list" = TCGplayer's. "Image mirror" = mirror. One spelling: "catalog".
 Size: small. Docs and comments only. Make targets keep.
12. **Photos.** The card photo files have 5 names; "photo" also means a stock photo.
 Where: store/photos.py DIRNAME "photos" (current) vs pipeline/selection.py CAPTURES (legacy) vs `<capture-dir>` in cli/__main__.py; `captures/ui/` is screenshots; RunsComposer.tsx step "Photos" holds the free-read pick, which sends no photo.
 Proposed: "photos folder" = `photos/`. `captures/cards/` = "legacy captures". "Stock photo" always has "stock". Composer step "Photos" → "Reader". CLI argument `<capture-dir>` → help says "folder of photos".
 Size: small. Strings and help. A run pointed at the wrong folder is the real harm (store/photos.py warns it bills every photo-suffixed file).
13. **Card number.** "Number" means the printed collector number, the count in the box ("Card 17"), the stored key, and "slot".
 Where: CLAUDE.md "slot numbers are not the truth" (means the stored index) vs  "number counts the cards, not the slots" (D58); app/src/types.ts Place.slot (the count); BoxOps "A section starts at a card number".
 Proposed: "Card 17" = count in box. "Collector number" = printed. "Key" (B3 #27) = stored index. Ban prose "slot" (except EMPTY_SLOT). Card.order (sort) vs order_key (buyer's order) get separate words: "sort key" and "order".
 Size: docs and strings small; wire `slot`, `order`, `order_key` rename is large. Keep.
14. **Box.** "Box", "drawer", `--bid`, "box number" and "true index" name one container.
 Where: CaptureScreen.tsx "Pick the drawer in front of you."; Orders.tsx "Fewest drawers" then  "across N boxes"; cli/cmd_rescue.py (box 1's number was reused).
 Proposed: "Box" everywhere. "Box id" = `bid`, never shown. App.tsx "queue drawer" → "queue panel".
 Size: small. Strings and CLI help. `--box 3` vs `--bid 3` stay; the glossary says why.
15. **Captured / on hand.** "Captured" is a card state and a lifetime count. One number is "on hand", "Stored" and "In stock".
 Where: mixPivot.ts "Cards captured"/"Sold of captured"; BoxOps.tsx "on hand" and  "Stored", same panel; PriceFacts.tsx "On Hand".
 Proposed: "Captured" = state pill only. Lifetime = "Photographed" (Home already says it). "On hand" = in boxes now (replaces Stored, In stock). Bare "stock" = never.
 Size: small. Strings only.
16. **Listed / live.** "Listed as" is the bound SKU. "Listed" is copies live. `--listed-only` is above the cut-off. "Live" has 4 more meanings.
 Where: CardHero.tsx "Listed as" and  "Listed"; cli/__main__.py `--listed-only`; types.ts RunSummary.live (a process is running) vs Listing.live (copies).
 Proposed: "Product" = the SKU bound ("Listed as" → "Product"). "Live" = copies on TCGplayer now. `--listed-only` help = "above-cut-off rows". Run process = "running".
 Size: small. Flag, file `import-listed.csv`, and wire `live` keep.
17. **Claim.** "Claim" means the operator's card labels, a paid-press lock, a port slot, and a listing count.
 Where: BoxOps.tsx "Set Claims" holding "Set Hint"; SubmissionClaims.tsx; capture_server.py "release the claim on Runs first".
 Proposed: "Claims" = operator's statements (game, finish, rarity, set hint); "Set claims" retires. Paid-press lock = "lock".
 Size: small. Code keeps `claim`, `set_hint`.
18. **Paused.** "Paused" is a trigger you chose and a fault halt. Both say "Resume".
 Where: CaptureScreen.tsx "Pause motion — Space"/"Resume motion";  "Captures are paused. Resume them above."; dealer.ts SAID_DROPPED.
 Proposed: "Paused" = trigger only. Fault = "Stopped". Unmeasured: does "Resume motion" clear a fault halt? Your ruling needed.
 Size: small. Strings only.
19. **Sold / Sales.** Home's "N sold" links to a screen built from the order ledger.
 Where: Home.tsx (comment says "different universes on purpose"); MixView.tsx Page "Sales".
 Proposed: "Sold" = cards marked sold in the store. "Sales" = order ledger. The link says "Sales" and shows its own number.
 Size: small.
20. **Pulled.** The same retire code shows as "Pulled" and as "Removed". "Pull" also means an order pick that sells.
 Where: ReviewQueue.tsx "Pulled"; cardState.ts "Removed" (same `pulled`); App.tsx "Cards to Pull".
 Proposed: retire reason = "Taken out" on both screens (Review reads RETIRE_REASONS). "Pull" = order pick only (D90: a pull sells the copy).
 Size: small. Stored `pulled` keeps.
21. **Name.** "Name" is the printed name, and also the card id (`cid`). `UnnamedCard` means no cid.
 Where: store/master.py; CLAUDE.md `banchi cards name`; types.ts says "two boxes may carry the same name", but D20 (a box is an object) and BoxNameTaken refuse duplicates.
 Proposed: "Name" = printed. `cid` = "card id". Fix the types.ts comment.
 Size: small. CLI `cards name` rename is medium.
22. **Price files.** `prices.json` (store book), `pricing.json` (run table), `decisions.json` (retired) and `my-pricing.csv` read alike.
 Where: pipeline_routes.py "no prices file yet" (means pricing.json); D76 says `decisions.json` is where answers are written, but D86 (one pricing file for the store) retired it.
 Proposed: "price book" = prices.json. "Run price table" = pricing.json. Fix D76.
 Size: small. Filenames keep.
23. **Shelf.** The view is "Map". The shortcut sheet says "the Shelf". "Deleted boxes shelf" and "On Your Shelf" are different things.
 Where: BoxShelf.tsx "Map"; App.tsx "on the Shelf"; PriceFacts "On Your Shelf".
 Proposed: "Map" everywhere. "Deleted boxes". "On Your Shelf" → "On hand".
 Size: small. Component `BoxShelf` keeps.
24. **Reconcile.** `reconcile` is a read-only compare in one mode and a ledger write in another. The screen has three names.
 Where: cmd_reconcile.py (`--live --write`); RunPanel.tsx "Compare…"; LiveReconcile.tsx "Check what is live",  "Store reconciled".
 Proposed: "Compare" = run vs staged file (read-only). "Check what is live" = store vs live listings file, writes counts. `--phantoms` = "Live beyond on hand".
 Size: small. Strings and CLI help.
25. **Printing.** "Printing" means a set appearance and also the Normal/Foil finish.
 Where: cli/resolve.py ("a distinct Set Name"); pipeline/pricehistory.py ("subTypeName is the PRINTING (Normal / Foil)").
 Proposed: "Printing" = card in a set. "Finish" = Normal/Foil/holo. "Variant" retires.
 Size: small. Comments and docs.

Counts: 25 clashes. 22 are renames of strings, docs or comments only. 3 touch code or the wire (7, 13, 22 if filenames moved). None needs stored data to change in the proposals. Spot-checked on origin/main: 22 of 25 had at least one cited string or line confirmed (the rest rest on two or more finders). Needs your ruling: model name (3), cut-off defaults 0.40 vs 0.49 (7), box action word (5), "Resume motion" (18).

Glossary draft (term | means | not to be confused with):

| Term | Means | Not |
|---|---|---|
| Match | the join step: attach each card to a TCGplayer product | free read; the `match` price rule |
| Free read | one answer from the free reader (on-Mac, no cost) | paid read |
| Paid read | the paid Claude batch read of a photo | Identify (whole step) |
| Identify | the whole first step: free read, then paid read for the rest | the paid read alone |
| Identified / Matched | reader answered / has a SKU | each other |
| Cut-off | the price line below which cards get the flat price and park | envelope limit, move size |
| Held back | a SKU you kept out of every send | Trimmed, Reserved, Disputed |
| Review / To review / Parked | the screen and both piles / main pile / low-value pile | each other |
| Answered / Stood down | a person picked / closed, no change | each other |
| Send | the listing press | paid read batch; price change |
| Product list | the game's Filtered CSV | Live listings file, Staged file |
| On hand | copies in boxes now | Photographed (ever) |
| Card 17 / Collector number / Key | box count / printed / stored index | each other |
| Box / Box id | a container / never-reused `bid` | drawer (retired) |
| Product / Live | the bound SKU / copies on TCGplayer now | each other |
| Claims / Lock | operator's card labels / paid-press hold | each other |
| Paused / Stopped | trigger you set / fault halt | each other |
| Sold / Sales | marked sold in store / order ledger | each other |

Dropped (not found on origin/main): Pricing.tsx "readings not matched" and "wait on a re-link"; BoxOps.tsx stat "Captured"; RunPanel.tsx "Take a new reading" claim (not re-checked, so unconfirmed). The `Pricing.tsx "Which live listings to show"` string was not re-checked either.
