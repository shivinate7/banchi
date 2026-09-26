# Iconography for Banchi wave 2

This is the map for the ICONOGRAPHY ruling (D288). It covers
every press in the code at the time it was written, about 340 `<Button>` sites and 150 raw
`<button>` sites. `D288.md` cites this file. Read that entry first for the ruling
itself. This file is the detail: the rule, the icon set, and the risks.

Key to the columns in every table below:
- **Add** means that the kit lane must add the icon to `ICON`.
- **yes** means that the icon is already in `ICON`.
- **–** means that the press keeps its words.
- A glyph arrow (for example `x → trash`) means that the press keeps its words. Its glyph
  changes to fix a collision (section 3).

## 1. Tables per lane

Each row is one press in the code, as it stood when this map was written. A screen lane
converts its own rows on `ux/kit-icons` merged in, per the wave-2 brief.

### Kit (the `ux/kit-icons` lane converts these — they are kit files)
| Press (visible text) | Component | Decision | Icon | In ICON? |
|---|---|---|---|---|
| Close | kit/overlay.tsx:OverlayFrame | ICON | x | yes |
| {confirmLabel} | kit/overlay.tsx:ConfirmSheet | WORDS: the decision press | – | – |
| Cancel | kit/overlay.tsx:ConfirmSheet | WORDS: decision pair | – | – |
| Clear (inside "12 of 40, filtered by …") | kit/data.tsx:FilterCount | WORDS: inside a sentence | – | – |
| Select face | kit/data.tsx:PickTrigger | WORDS: shows a value | – | – |
| (x on a chip) "Clear {facet}" | kit/data.tsx:FacetChip | ICON (hand-rolled today) | x | yes |
| Clear all | kit/data.tsx:FilterChips | WORDS: a clear for the whole bar names its scope | – | – |
| Sort key select | kit/data.tsx:SortControl | WORDS: shows a value (UX-214) | – | – |
| "Low to high" / "High to low" | kit/data.tsx:SortControl | ICON, one toggle; the glyph changes by state | sortAsc / sortDesc | Add |
| Filters + count (compact bar) | kit/filters.tsx:FilterBar | ICON with a badge | filter | yes |
| Hide X + count | kit/filters.tsx:HideToggle | WORDS: states a set and a count (UX-211) | – | – |
| Column name + arrow | kit/filters.tsx:SortHeader | WORDS: the column name is the face | – | – |
| {action.label} (for example Undo) | kit/toast.tsx:Toaster | WORDS: generic label, one action in a short-lived toast, no tooltip on touch | – | – |
| Dismiss (x) | kit/toast.tsx:Toaster | ICON | x | yes |
| Try again | kit/index.tsx:Retry | WORDS: recovery, alone | – | – |
| Reload + R | kit/index.tsx:ReloadButton | ICON, key R in the tooltip (UX-056) | refresh | yes |
| Segmented options | kit/index.tsx:Segmented | WORDS: values | – | – |
| Chip | kit/index.tsx:Chip | WORDS: values | – | – |
| Clear search (x) | SearchField.tsx:SearchField | ICON (hand-rolled today) | x | yes |
| {submitLabel} | SearchField.tsx:SearchField | WORDS: form submit | – | – |

### Shell
| Press | Component | Decision | Icon | In ICON? |
|---|---|---|---|---|
| Open it again | App.tsx:focusScreen | WORDS: recovery, alone | – | – |
| Reload this screen | App.tsx:focusScreen | WORDS: recovery, alone | – | – |
| Show every screen's keys | App.tsx:KeysSheet | WORDS: link in a sheet | – | – |
| Wordmark + chevron (collapse the sidebar) | App.tsx:Sidebar | Keep: the face is the wordmark, not an icon | – | – |
| Go to ⌘K | App.tsx:Sidebar | WORDS: labelled row in the nav foot | – | – |
| Light mode / Dark mode | App.tsx:Sidebar | WORDS: labelled row in the nav foot | – | – |
| Go to (phone) | App.tsx:PhoneBar | ICON | search | yes |
| More | App.tsx:TabBar | WORDS: tab item (UX-046) | – | – |
| Theme row | App.tsx:Drawer | WORDS: drawer row | – | – |
| Skip to the screen | App.tsx:App | WORDS: skip link | – | – |
| Retry | App.tsx:App | WORDS: recovery, alone | – | – |

### Home
| Press | Component | Decision | Icon | In ICON? |
|---|---|---|---|---|
| Start capturing / Photograph the first box | Home.tsx:Home | WORDS: the only primary (D121 KEEP) | – | – |
| Standing rows, box rows, run rows, "more" links | Home.tsx:Home | WORDS: links that name their target | – | – |

### Capture
| Press | Component | Decision | Icon | In ICON? |
|---|---|---|---|---|
| Picker rows, fields, options, track cells | CaptureScreen.tsx:Row/OpenField/Opt/Track | WORDS: values | – | – |
| Resume captures | CaptureScreen.tsx:CaptureScreen | WORDS: only primary | – | – |
| Open the camera (x2) | CaptureScreen.tsx:CaptureScreen | WORDS: only primary | – | – |
| Reopen the camera (x2) | CaptureScreen.tsx:CaptureScreen | WORDS: recovery, alone | – | – |
| Re-baseline (x2) | CaptureScreen.tsx:CaptureScreen | WORDS: not in the vocabulary; the face carries a fact | – | – |
| Set aside | CaptureScreen.tsx:CaptureScreen | WORDS: not in the vocabulary | – | – |
| Save trace + "N frames" | CaptureScreen.tsx:CaptureScreen | WORDS: the face carries a count | – | – |
| Save note | CaptureScreen.tsx:CaptureScreen | ICON (move to IconButton) | check | yes |
| Shutter | CaptureScreen.tsx:CaptureScreen | WORDS: only primary | – | – |
| {blocker.fix.label} | CaptureScreen.tsx:CaptureScreen | WORDS: the fix names itself | – | – |
| New section | CaptureScreen.tsx:CaptureScreen | WORDS: not in the vocabulary | – | – |
| Identify {box} on Runs | CaptureScreen.tsx:CaptureScreen | WORDS: names the box; leads to a money press | – | – |
| Undo strip thumbnail (U, 2, 3…) | CaptureScreen.tsx:CaptureScreen | Keep: the photo is the face | – | – |
| Remove just this card (x) | CaptureScreen.tsx:CaptureScreen | ICON, danger tone, 40px target, glyph `x → trash` | trash | yes |
| Cancel / Remove this card | CaptureScreen.tsx:CaptureScreen | WORDS: decision pair | – | – |
| Ask again (x2) | CaptureScreen.tsx:CaptureScreen | WORDS: recovery, alone | – | – |
| Rig disclosure | CaptureScreen.tsx:CaptureScreen | WORDS: disclosure | – | – |
| Clear the setup | CaptureScreen.tsx:CaptureScreen | WORDS: not in the vocabulary, glyph `refresh → eraser` | eraser | Add |
| Release N cards | SubmissionClaims.tsx:SubmissionClaims | WORDS: paid-reading claim, cannot be undone | – | – |

### Sales
| Press | Component | Decision | Icon | In ICON? |
|---|---|---|---|---|
| Value my stock | Revenue.tsx:Revenue | WORDS; dies when "On the shelf loads on arrival" lands | – | – |
| Refresh (after the load) | Revenue.tsx:Revenue | ICON through ReloadButton hotkey={false} | refresh | yes |
| Month bars | Revenue.tsx:Revenue | WORDS: data | – | – |
| Clear (beside "Sep only") | Revenue.tsx:Revenue | ICON, "Clear the month" | x | yes |
| Compare to today's market | Revenue.tsx:Revenue | WORDS: not in the vocabulary | – | – |
| Sort headers | Revenue.tsx:Revenue | WORDS through the kit SortHeader | – | – |
| Row expand chevron | Revenue.tsx:Revenue | ICON (hand-rolled today) | chevronRight / chevronDown | yes |
| Show all (direction B, top N) | Revenue.tsx (new) | WORDS: the face carries a count | – | – |

### Shipping
| Press | Component | Decision | Icon | In ICON? |
|---|---|---|---|---|
| Forget this export (empty state) | OrdersShipStage.tsx:ShipStage | WORDS: alone in an empty state | – | – |
| Forget (file card) | OrdersShipStage.tsx:ShipStage | ICON, danger tone, "Forget this file" (UX-108 risk) | trash | yes |
| Read another file | OrdersShipStage.tsx:ShipStage | WORDS: the card's main action | – | – |
| Fill / Refill pick locations | OrdersShipStage.tsx:ShipStage | WORDS: UX-108 wants a verb and its object | – | – |
| Lane chips | OrdersShipStage.tsx:ShipStage | WORDS: values | – | – |

### Library
| Press | Component | Decision | Icon | In ICON? |
|---|---|---|---|---|
| Reload | Graveyard.tsx:Graveyard | ICON through ReloadButton | refresh | yes |
| Try again (x2) | Graveyard.tsx:Graveyard | WORDS: recovery, alone | – | – |
| Close | Codes.tsx:Sheet | ICON, through the kit Sheet | x | yes |
| Reveal / Hide | Codes.tsx:CodeBlock | ICON, pressed state, glyph `lock → eyeOff` | eye / eyeOff | yes / Add |
| Copy all / Copied | Codes.tsx:CodeBlock | ICON; the name stays and a status says "Copied" | copy | yes |
| Download .txt | Codes.tsx:CodeBlock | ICON, "Download the codes" | download | yes |
| Copy path / Copied | Codes.tsx:ManifestPath | ICON | copy | yes |
| Dismiss | Codes.tsx:Codes | ICON | x | yes |
| Reload | Codes.tsx:Codes | ICON through ReloadButton | refresh | yes |
| Read a box | Codes.tsx:Codes | WORDS: only primary | – | – |
| Try again (x2) | Codes.tsx:Codes | WORDS: recovery | – | – |
| Go to capture | Codes.tsx:Codes | WORDS: empty-state door | – | – |
| Review duplicates | Codes.tsx:Codes | WORDS: disclosure with a count | – | – |
| Code + eye row toggle | Codes.tsx:Codes | Keep: the code is the face; glyph `lock → eyeOff` | eyeOff | Add |
| Set the product | Codes.tsx:Codes | WORDS: only primary in the row | – | – |
| Fix on Inventory | Codes.tsx:Codes | WORDS: names the destination | – | – |
| Apply to N | Codes.tsx:Codes | WORDS: count | – | – |
| Show fewer / Show all N | Codes.tsx:Codes | WORDS: count | – | – |
| Codes / Lots tabs | Codes.tsx:Codes | WORDS: tabs | – | – |
| Build a lot | Codes.tsx:Codes | WORDS: not in the vocabulary | – | – |
| State and lane chips | Codes.tsx:Codes | WORDS: values | – | – |
| Reveal codes / Hide codes | Codes.tsx:Codes | ICON, pressed state | eye / eyeOff | yes / Add |
| Clear filters (x2) | Codes.tsx:Codes | WORDS: a clear for the whole bar | – | – |
| Preview / Preview the {lane} lane | Codes.tsx:Codes | WORDS: sheet decision | – | – |
| Read the box / Plan the lot | Codes.tsx:Codes | WORDS: only primary | – | – |
| Reserve N codes — cannot be undone (x2) | Codes.tsx:Codes | WORDS: irreversible | – | – |
| Listing / Packing slip / Manifest | Codes.tsx:Codes | WORDS: tabs | – | – |
| Task tiles | Codes.tsx:TaskCard | WORDS: tiles | – | – |

### Inventory
| Press | Component | Decision | Icon | In ICON? |
|---|---|---|---|---|
| Mark sold (row, sm) | Inventory.tsx:Action | ICON | sold | Add |
| Mark sold (phone bar, primary lg) | Inventory.tsx:Action | WORDS: only primary in its sector | – | – |
| Retire (row, iconOnly today) | Inventory.tsx:Action | ICON (move to IconButton) | archive | yes |
| Retire (phone bar) | Inventory.tsx:Action | ICON: secondary beside the primary | archive | yes |
| Undo (row receipt, U) | Inventory.tsx:Action | ICON, U in the tooltip | undo | yes |
| Undo (phone bar, beside "Marked sold.") | Inventory.tsx:Action | ICON: the sentence teaches | undo | yes |
| Retire reasons | Inventory.tsx:RetirePanel | WORDS: the reason is the write | – | – |
| Cancel | Inventory.tsx:RetirePanel | WORDS: decision pair | – | – |
| Move (new per copy row, UX-244) | Inventory.tsx:Action | ICON | moveTo | Add |
| Address "Walk to …" | CardLocations.tsx:OwnerRows | WORDS: the place is the face | – | – |
| Mark sold (default row) | CardLocations.tsx:OwnerRows | ICON | sold | Add |
| Variant tiles | BoxBrowse.tsx:VariantChooser | WORDS: photo and name | – | – |
| Collapse / Expand the box rail | BoxBrowse.tsx:BoxBrowse | ICON (move to IconButton) | chevronLeft / chevronRight | yes |
| Clear filter (rail) | BoxBrowse.tsx:BoxBrowse | WORDS: FilterBar clear | – | – |
| Box rows, collapsed-rail tiles, phone box chip | BoxBrowse.tsx:BoxBrowse | WORDS: names | – | – |
| Manage | BoxBrowse.tsx:BoxBrowse | ICON, "Manage this box" | settings | yes |
| clear (ticks, "3 ticked · clear") | BoxBrowse.tsx:BoxBrowse | WORDS: inside a status line | – | – |
| expand all / collapse all + N sections | BoxBrowse.tsx:BoxBrowse | WORDS: count | – | – |
| tick shown / untick shown | BoxBrowse.tsx:BoxBrowse | WORDS: says the outcome | – | – |
| Capture into box X / Capture a card / Capture your first card | BoxBrowse.tsx:BoxBrowse | WORDS: names the box, or only primary | – | – |
| Clear the search / Clear the filter (empty states) | BoxBrowse.tsx:BoxBrowse | WORDS: alone in an empty state | – | – |
| Section headers, walk rows | BoxBrowse.tsx:BoxBrowse | WORDS | – | – |
| Try again | BoxBrowse.tsx:BoxBrowse | WORDS: recovery | – | – |
| Search cards (phone) | BoxBrowse.tsx:BoxBrowse | ICON | search | yes |
| Previous card / Next card | BoxBrowse.tsx:BoxBrowse | ICON (hand-rolled today) | chevronLeft / chevronRight | yes |
| {label} re-shoot | BoxBrowse.tsx:ReshootControl | WORDS: not in the vocabulary | – | – |
| Card actions | BoxBrowse.tsx:CardOps | ICON | more | yes |
| Correct claims | BoxBrowse.tsx:CardOps | WORDS: menu item, glyph `wand → pencil` | pencil | Add |
| Re-read the inventory / Bring this card back / Remove this card… | BoxBrowse.tsx:CardOps | WORDS: menu items | – | – |
| Close | BoxBrowse.tsx:CardOps | ICON | x | yes |
| Cancel / Remove this card and slide the box down | BoxBrowse.tsx:CardOps | WORDS: irreversible | – | – |
| Op tiles (Rename, Edit sections, Name sections, Set claims, Move to box; Seal and Re-open removed by D-sealed-boxes-removed) | BoxOps.tsx:Op | WORDS: settings tiles carry a value; glyphs `tag → pencil`, `wand → pencil`, `package → moveTo` | pencil, moveTo | Add |
| Close | BoxOps.tsx:BoxOps | ICON | x | yes |
| Cancel / Save name / Move / Save names / Check this layout / Back / Save sections / Apply to {scope} | BoxOps.tsx | WORDS: form footers | – | – |
| All settings | BoxOps.tsx:EditorFrame | WORDS: back with a destination | – | – |
| Claim chips | BoxOps.tsx:ClaimEditor | WORDS: values | – | – |
| TCGplayer holds none of these — release | BoxOps.tsx:ReleaseListings | WORDS: store write | – | – |
| Delete N photographs / Delete box permanently | BoxOps.tsx:ReclaimPhotos/DeleteBox | WORDS: irreversible | – | – |
| Photo | CardHero.tsx:PhotoPanel | Keep: the photo is the face | – | – |
| Wrong card? | CardHero.tsx:ListingCorrection | WORDS: a question (UX-243) | – | – |
| Close | CardHero.tsx:ListingCorrection | ICON | x | yes |
| Close photo (inline svg) | InventoryOverlay.tsx:Overlay | ICON (it breaks DESIGN.md's no-inline-svg rule today) | x | yes |

### Orders
| Press | Component | Decision | Icon | In ICON? |
|---|---|---|---|---|
| Stop | Orders.tsx:FetchReceipt | WORDS: stops a TCGplayer fetch | – | – |
| Fetch the rest / Fetch the next N | Orders.tsx:FetchReceipt | WORDS: count | – | – |
| Count them again / Every status / Fetch these N | Orders.tsx:StatusPicker | WORDS: counts or only primary | – | – |
| {statusSummary} | Orders.tsx:OrdersHub | WORDS: shows a value (becomes FilterBar) | – | – |
| Read this paste / Fetch from TCGplayer / Fetch two years | Orders.tsx:OrdersHub | WORDS: TCGplayer reads, not in the vocabulary | – | – |
| Stand down N orders (x2) | Orders.tsx:BacklogPrompt/ReconcileBacklogPanel | WORDS: irreversible; drop the `check` glyph | – | – |
| Try again (x2) / Fetch from TCGplayer | Orders.tsx:PullStage/OrderDetail | WORDS: recovery or only primary | – | – |
| Clear search / Show all open | Orders.tsx:PullStage | WORDS: alone in an empty state | – | – |
| Tick shown / Untick shown | Orders.tsx:PullStage | WORDS: reword per UX-232 ("Walk all N buyers") | – | – |
| Collapse / Expand the buyer rail | Orders.tsx:PullStage | ICON | chevronLeft / chevronRight | yes |
| Sections toggle, buyer tiles, phone buyer chip, BuyerRow | Orders.tsx | WORDS: names, counts or values | – | – |
| Read it again | Orders.tsx:PullStage | WORDS: inside a sentence | – | – |
| Skip to cards | Orders.tsx:PullStage | WORDS: skip link | – | – |
| Manage | Orders.tsx:OrderPanel | ICON, "Manage this buyer's orders" | settings | yes |
| I already sent it / these N; final stand-down with the figure | Orders.tsx:LineStandDown | WORDS: stand down | – | – |
| `It isn't shipping` | Orders.tsx:LineStandDown | WORDS; drop the `undo` glyph | – | – |
| Sealed product | Orders.tsx:LineStandDown | WORDS | – | – |
| Undo — not sealed | Orders.tsx:LineStandDown | ICON, "Undo: not sealed" | undo | yes |
| Line unfold | Orders.tsx:OrderLineRow | WORDS: text face | – | – |
| Order number chip | Orders.tsx:PickLine | WORDS: the face is the number | – | – |
| Mark sold (x per pick) | Orders.tsx:PickLine | ICON, not primary tone; glyph `hand → sold`. Risk 4.1: the undo session must land first, and the owner accepted this risk | sold | Add |
| Walk rows | OrdersWalkPane.tsx:WalkList | WORDS | – | – |
| Mark sold | OrdersWalkPane.tsx:RowAction | ICON | sold | Add |
| Undo | OrdersWalkPane.tsx:RowAction | ICON | undo | yes |

### Review (the Runs files are here — Runs folds into Review)
| Press | Component | Decision | Icon | In ICON? |
|---|---|---|---|---|
| Answer all N together (header and GroupConfirm) | ReviewQueue.tsx | WORDS: count; a write | – | – |
| One at a time | ReviewQueue.tsx:GroupConfirm | WORDS: decision pair | – | – |
| Re-check every waiting card / Re-check all | ReviewQueue.tsx:ReviewQueue | WORDS: not in the vocabulary | – | – |
| Reload the queue (header) | ReviewQueue.tsx:ReviewQueue | ICON through ReloadButton | refresh | yes |
| Queue N | ReviewQueue.tsx:ReviewQueue | WORDS: count | – | – |
| Reason chips / Every reason / Show every reason | ReviewQueue.tsx:ReviewQueue | WORDS: values or a clear for the whole bar | – | – |
| Clear skips | ReviewQueue.tsx:Tray | WORDS: inside a notice sentence | – | – |
| Undo (receipt) | ReviewQueue.tsx:Tray | ICON, U in the tooltip | undo | yes |
| Reload the queue (notice) | ReviewQueue.tsx:RefusalNotice | WORDS: recovery | – | – |
| Dismiss | ReviewQueue.tsx:RefusalNotice | ICON | x | yes |
| Undo (session rows) | ReviewQueue.tsx:SessionList | ICON | undo | yes |
| N more | ReviewQueue.tsx:SessionList | WORDS: count | – | – |
| Price the answers / Run another box | ReviewQueue.tsx:Done | WORDS: only primary, money path | – | – |
| Skip | ReviewQueue.tsx:Card | WORDS: decision bar | – | – |
| Search the export / Back to rows | ReviewQueue.tsx:Card | WORDS; glyph `undo → arrowLeft` | arrowLeft | yes |
| Close (close the question) | ReviewQueue.tsx:Card | WORDS at every width; drop `x` and drop iconOnly on the phone | – | – |
| Candidates / close reasons | ReviewQueue.tsx:CandidateButton/ClosePanel | WORDS: the answer is the write | – | – |
| Cancel (x) | ReviewQueue.tsx:ClosePanel | ICON, "Close the panel" | x | yes |
| Search | ReviewQueue.tsx:CatalogPanel | WORDS: submit | – | – |
| Close the queue / Close | ReviewQueue.tsx:Waiting/QueueRefresh | ICON | x | yes |
| Not now / Apply the refresh | ReviewQueue.tsx:QueueRefresh | WORDS: decision pair | – | – |
| Reload boxes and runs | Runs.tsx:Runs | ICON through ReloadButton | refresh | yes |
| Check what is live | Runs.tsx:Runs | WORDS; glyph `upload → refresh` | refresh | yes |
| Identify cards / Identify a box / Spend $X and identify N / Stop asking under $X | Runs*.tsx | WORDS: money | – | – |
| Copy / Copied | RunsLog.tsx:LogWell | ICON | copy | yes |
| Log and preflight disclosures, stage steps, box and run rows | RunsLog/RunsComposer/RunPanel | WORDS | – | – |
| Close / Dismiss (x3) | RunsComposer/RunPanel/RunRescue | ICON | x | yes |
| The card before / after this one | RunsComposer.tsx:RunsComposer | ICON (move to IconButton) | chevronLeft / chevronRight | yes |
| Go to capture / Go to inventory / Identify every box instead | RunsComposer.tsx | WORDS: doors | – | – |
| Cancel / Next: photos / Cards / Check cost / Photos / Not now / Watch the run | RunsComposer.tsx | WORDS: wizard footer | – | – |
| All runs / Rebind / Rebind these cards / Open that run / Open the new run | RunPanel/RunRescue | WORDS: destination or irreversible | – | – |
| Try again / Preview / Join again | RunPanel.tsx:RunPanel | WORDS | – | – |
| Fetch from TCGplayer | RunPanel.tsx:RunPanel | WORDS; glyph `download → refresh` | refresh | yes |
| Options | RunPanel.tsx:RunPanel | ICON | settings | yes |

### Pricing (b-pricing — product sheet files are here too)
| Press | Component | Decision | Icon | In ICON? |
|---|---|---|---|---|
| Find by value / Mark down stale | Pricing.tsx:Pricing | Dies (value goes to Inventory sort; mark-down becomes the "Live" tab, WORDS) | – | – |
| Clear typed | Pricing.tsx:Pricing | ICON, not danger; glyph `trash → eraser` | eraser | Add |
| Runs N ▾ / Holding N | Pricing.tsx:Pricing | WORDS: count | – | – |
| Reload | Pricing.tsx:Pricing | ICON through ReloadButton | refresh | yes |
| Empty-state doors (Read a fresh export, Price my live listings, Go to Runs, See what you already own, Show everything unsent, Pick a run, Runs) | Pricing.tsx | WORDS: doors | – | – |
| Re-read the pricing file, losing what is unsaved here | Pricing.tsx:Pricing | WORDS: loses work | – | – |
| Undo U | Pricing.tsx:Pricing | ICON, fixed slot (UX-135), U in the tooltip | undo | yes |
| Load trends / Compare | Pricing.tsx:Pricing | WORDS: UX-108 wants a verb and its object | – | – |
| Price history (row) | Pricing.tsx:Pricing | ICON; glyph `history → chart` | chart | yes |
| Hold / Release (row) | Pricing.tsx:Pricing | ICON, pressed state | lock / unlock | yes |
| History / Photo drawer tabs | Pricing.tsx:Pricing | WORDS: tabs; glyph `history → chart` | – | – |
| Close (drawer header, x2) | Pricing.tsx:Pricing | ICON | x | yes |
| Close (drawer footer) | Pricing.tsx:Pricing | Delete: one Close per overlay | – | – |
| Next copy | Pricing.tsx:Pricing | WORDS | – | – |
| Send N … | Pricing.tsx / SendCard.tsx | WORDS: money | – | – |
| Download the file instead | Pricing.tsx / SendCard.tsx | WORDS: the named alternative to a money press | – | – |
| Cut-off panel presses (Price N under the line, Make them both $X, Pick a run, Give this run its own cut-off) | Pricing.tsx:CutoffPanel | WORDS: facts | – | – |
| Follow the store again | Pricing.tsx:CutoffPanel | WORDS; drop the `undo` glyph | – | – |
| Hold reasons / Cancel / Hold it | Pricing.tsx:HoldPanel | WORDS | – | – |
| Dismiss | SendCard.tsx:TakenBackWarning | ICON | x | yes |
| Take N copies back / Check what is live / Write the file | SendCard.tsx | WORDS: store write or unique job | – | – |
| Markdown sheet presses | Markdown.tsx | Die with the sheet (Q6); Close is ICON x until then; "Discard staged" drops `undo` | – | – |
| Close | LiveReconcile.tsx / ClearPrices.tsx | ICON | x | yes |
| Fetch my live listings | LiveReconcile.tsx | WORDS; glyph `download → refresh` | refresh | yes |
| Not now / Match the store / Cancel | LiveReconcile / ClearPrices | WORDS: decision pair | – | – |
| Clear N typed prices | ClearPrices.tsx | WORDS: count; glyph `trash → eraser` | eraser | Add |
| ValueBands presses | ValueBands.tsx | Die (they move to the Inventory sort) | – | – |
| Try again | PriceHistory.tsx | WORDS | – | – |
| Close | PriceHistory.tsx | ICON | x | yes |
| Keep open | PriceHistory.tsx | WORDS; drop `pin` — `pin` names a pick location | – | – |
| Open as page | ProductHistory.tsx:ProductSheet | ICON | external | yes |

### Box map (new BoxShelf.tsx, from boxmap-deliberation.md)
| Press | Component | Decision | Icon | In ICON? |
|---|---|---|---|---|
| Shelf / Walk view switch | Inventory.tsx | WORDS: segmented | – | – |
| Section pick-up handle | BoxShelf:Compartment | ICON, "Move section {name}" | grip | Add |
| Section menu | BoxShelf:Compartment | ICON | more | yes |
| Move to… (menu item) | BoxShelf:Compartment | WORDS: menu item | – | – |
| Destination box rows, + New box | BoxShelf | WORDS: names | – | – |
| Put here / Cancel (touch bar) | BoxShelf | WORDS: decision pair | – | – |
| Undo U (receipt) | BoxShelf:Receipt | ICON: the receipt sentence teaches | undo | yes |
| Done (receipt) | BoxShelf:Receipt | WORDS | – | – |
| Rename section | BoxShelf:Compartment | ICON | pencil | Add |

### Fulfillment (the rule does not apply here)
| Press | Component | Decision | Icon | In ICON? |
|---|---|---|---|---|
| Pull this card (x2) | Fulfillment.tsx | WORDS: Fulfiller | – | – |
| Undo | Fulfillment.tsx | WORDS: Fulfiller (undo floor) | – | – |
| Try again (x2) / Back to the cards / N more / Show all owed | Fulfillment.tsx | WORDS: Fulfiller | – | – |
| Show every card (x in the search field, 44px) | Fulfillment.tsx | Keep: the field-clear pattern meets the 44px floor already | – | – |
| PullConfirm | PullConfirm.tsx | WORDS: Fulfiller | – | – |

## 2. The rule

Apply these steps in order. The first match wins.

1. **Fulfiller route** (`persona: 'fulfiller'`: `Fulfillment.tsx`, `PullConfirm.tsx` and
   `CardLocations:FulfillerCard`). WORDS always.
   - DESIGN.md sets these floors: text 20px or more, targets 44px or more (IconButton is 40),
     and gaps 12px or more. It also sets a contrast floor of 7:1, a banned-word list, and an
     undo on every mark-sold.
   - A touch screen shows no tooltip. The Fulfiller is retired and not technical. The words
     must teach.
2. **Money, TCGplayer or no way back.** The press spends money, writes to TCGplayer, or no
   undo can reverse it. WORDS. Examples: Send, Identify, Spend, Stand down, Reserve, Release a
   claim, Rebind, Take back, Delete permanently. `danger-solid` is always WORDS.
3. **A fact on the face.** The face carries a count, a price, a name, a box, or a current
   value or state (a filter value, a sort key). WORDS.
4. **The only primary in its sector.** Examples: a page primary, an empty-state door, a
   notice's recovery ("Try again"), a sheet or wizard footer, a decision pair (Cancel, Not
   now, Back). WORDS.
5. **Other word-only controls.** A menu item, a tab, a segmented option, a chip, a link or
   press inside a sentence, a skip link. WORDS.
6. **The verb is in the vocabulary**, and no step above matches. ICON through `IconButton`.
   - Mark sold → sold
   - Undo → undo
   - Retire → archive
   - Edit or Rename → pencil
   - Delete, Forget or Remove → trash
   - Clear typed values (undoable) → eraser
   - Copy → copy
   - Download a file to disk → download
   - Open elsewhere → external
   - Close, Dismiss, or clear one value → x
   - Filter → filter, with a badge
   - Sort direction → sortAsc or sortDesc
   - Reload → refresh
   - Manage or Options → settings
   - More → more
   - Move to a box → moveTo
   - Hold or Release → lock or unlock
   - Reveal or Hide → eye or eyeOff
   - Collapse, expand, previous or next → chevrons
   - Search → search
   - Drag → grip
7. **Anything else.** WORDS. To make a new icon press, add a path and an `ICON_MEANINGS` row
   first. A new meaning gets a new path.

Edge cases:
- **The only primary in its sector.** The same verb is ICON in a row and WORDS when it is the
  only primary. Inventory's row "Mark sold" is ICON. The phone bar "Mark sold" is WORDS. A
  list of per-row primaries is not "the only primary". Each row's press is ICON and does not
  use the primary tone.
- **Meaning changes by state.** Use one footprint (D118).
  - A toggle of one act (Hold/Release, Reveal/Hide, Collapse/Expand) uses `pressed`. Change
    the label and the icon together, never the icon alone.
  - When the act itself changes (Mark sold, then Undo — Value my stock, then Refresh), decide
    each state by the rule. Reserve the wider slot.
  - Copy: the name stays "Copy …". The glyph can show check for 2s. A polite status says
    "Copied".
- **Dense row versus alone.**
  - A press repeated per item (row, table, walk, list) is ICON. The same verb alone (empty
    state, notice, toast, sheet footer) is WORDS.
  - A row holds 3 IconButtons at most. Put the 4th and later presses in a `more` menu with
    words.
  - In a row, the accessible name carries the object ("Undo the sale at Section 2, Card 5").
    The tooltip stays short.
  - A receipt's Undo is ICON, because the receipt sentence teaches. A toast action is WORDS,
    because the kit label is generic and the toast is short-lived.
- **Phone widths (below 640).** No hover, so no tooltip on its own.
  - The kit shows the tooltip on hover, on keyboard focus, and on a long press.
  - A Banchi-specific glyph (sold, archive, moveTo, eraser, lock) goes only where a sentence,
    pill or heading near it names the act. If nothing names it, the press goes into the `more`
    menu with words.
  - The hit area is 40px at every width (UX-267).
- **Destructive but undoable.** It never uses `trash` and never uses danger tone. Clear typed
  uses eraser. Retire uses archive, opens its reason panel, and follows UX-252.
- **Destructive, with no undo.** The trash ICON only opens a ConfirmSheet. The confirm
  press is WORDS. A cheap loss with a way to redo it (Forget an in-memory file) can be a trash
  ICON with danger tone that acts at once.
- **Keycap.** It goes in the tooltip, after the label ("Undo U"), never on the face
  (UX-145, UX-040).

### The kit check

`R2-icon-only-button` in `scripts/kit-adoption.mjs`. Outside `app/src/kit/**`, the Fulfiller
files and Gallery, it refuses three things:
- (a) `iconOnly` on `Button`.
- (b) A raw `<button>` or inline `<svg>` whose only child is an icon.
- (c) A `Button` whose literal label starts with a vocabulary verb, when its variant is not
  `primary` or `danger-solid`. The vocabulary: Mark sold, Undo, Retire, Edit, Rename, Delete,
  Forget, Copy, Download, Open as page, Close, Dismiss, Reload, Manage, Options.

The check reads `variant` statically. A dynamic variant, like Inventory's `primary ? …`, must
split into two JSX branches before the check can prove it worded. The violations that exist
today are on the shrinking offender list, under lane `icons`. Rule (c) is born on this branch.
It may add keys under the only-shrinks exception `scripts/kit-adoption.mjs` already carries.

**Clause (c)'s declared exception** (the coordinator's ruling, 2026-09-25). A vocabulary-verb
label with no provably worded variant has a second door. A literal `words="<reason>"` on the
`Button` itself excuses it. Its values are `kit/index.tsx`'s `WordsReason` type, mirrored in
`scripts/kit-adoption.mjs`'s `WORDS_REASONS`:

| `words` value | This section's rule |
|---|---|
| `irreversible` | rule 2: money, TCGplayer, or no way back |
| `fact-on-face` | rule 3: the face carries a count, a price, a name, a box, or a current value |
| `only-primary` | rule 4: the only primary in its sector |
| `word-only-control` | rule 5: a menu item, a tab, a chip, a link, or a press inside a sentence |
| `not-in-vocabulary` | rule 7: the leading word matches a vocabulary verb by text, not by its meaning here |

This is a STATED reason at the press, never an allow-list entry. A reviewer reads why beside
the code. It survives the press moving files, where an allow-list entry, keyed to a path, does
not. `words` is read only by the check. It never reaches the DOM and changes nothing on
screen. An unrecognized value excuses nothing.

Found live, the day this door was built: Capture's "Clear the setup" (`not-in-vocabulary` —
"Clear" matches the vocabulary's word, not its "clear typed values, undoable" meaning. It
resets the whole rig) and SubmissionClaims' "Release N cards" (`irreversible` — a paid
identification claim, cannot be undone). Shipping's "Forget this export" names the
`only-primary` case: alone in an empty state. It had already moved to `danger-solid` only to
pass the check, not because that variant fit. Gaming the variant proof is exactly what this
door replaces. These three presses adopt `words` in their own lanes, once `ux/kit-tighten`
merges. This branch names them here. It does not edit files those lanes own.

### What IconButton carries, beyond the brief's first cut

- `kbd`, drawn in the tooltip.
- `pressed`, for a toggle of one act.
- `busy`, a spinner in the same footprint.
- `badge`, a count.
- An optional longer accessible `name`, apart from the tooltip `label` (UX-271).
- An anchor form: `href` (plus `target`/`rel`) renders an `<a>` instead of a `<button>`, same
  face, hit area, tooltip and accessible name (round 3, below).
- A visual face of 28px in dense rows, at a hit area of 40px or more, every width.
- The tooltip on hover, on keyboard focus, and on a touch long-press.
- Seven kit controls moved onto it: overlay Close, the Toaster dismiss, the FacetChip clear,
  and the SearchField clear. Also ReloadButton, the compact FilterBar trigger, and the
  SortControl direction. The sort KEY stays in words. Only the direction became
  sortAsc/sortDesc, per the owner's word on the UX-214 conflict below.

## 3. Icons to add, and collisions

**Eight paths were added, each with an `ICON_MEANINGS` row:**
- `sold`: a round seal with $, for Mark sold and the Sold pill. It is not `tag` (Pricing) and
  not bare `dollar` (Sales).
- `pencil`: Edit or Rename.
- `eraser`: clear typed values, undoable.
- `eyeOff`: Hide.
- `sortAsc` and `sortDesc`.
- `moveTo`: an arrow into a bracket. It draws no box: `box`, `package` and `archive` are
  already box shapes.
- `grip`: six dots.

`ICON_MEANINGS` also gained a row for every OLD icon the rule now draws on: `x`, `check`,
`eye`, `lock`, `external`, `download`, `settings` and `hand`. It also covers every other
icon step 6 above names. `make kit-adoption`'s own check fails a commit that drops one of
these rows, or that names a vocabulary icon `PATHS` does not draw.

**Collisions to fix, by owner lane. This is the record of what changed and why, for the lane
that owns the screen:**
- `x` as a write:
  - Capture "Remove just this card" → trash.
  - Review "Close" (it stands a question down) → words, no glyph.
- `undo` where the press is not an undo:
  - Review "Back to rows" → arrowLeft.
  - Pricing "Follow the store again" → no glyph.
  - Orders `It isn't shipping` → no glyph.
  - Markdown "Discard staged" → no glyph.
- `trash` on an undoable clear: Pricing "Clear typed" and ClearPrices → eraser.
- `check` and `hand` as Mark sold: Inventory and Orders PickLine → sold. `check` on the
  irreversible "Stand down" (Orders, x2) → drop it.
- `lock` as Hide: Codes, 3 places → eyeOff. `lock` now means only seal or hold.
- `tag` and `wand` as manual edits: BoxOps Rename, Name sections and Set claims, and CardOps
  Correct claims → pencil. `wand` stays for "let Banchi check again".
- `package` as Move to box (BoxOps) → moveTo.
- `download` as a TCGplayer fetch: RunPanel, Markdown and LiveReconcile → refresh. `download`
  names a file saved to disk.
- `upload` as "Check what is live" (Runs.tsx) → refresh.
- `history` as price history: the Pricing row and the drawer tab → chart. This follows UX-118.
- `external` as the departed badge (BoxBrowse) and `eye` as "Viewing" — the inventory lane
  fixes these (UX-222, UX-221).
- `pin` as Keep open (PriceHistory) → words. `pin` names a pick location.
- `refresh` as a reset: Capture "Clear the setup" → eraser.
- **Retire against Delete.** There is no collision today. `archive` is not `trash`. They stay
  apart.

## 4. Risks

1. **Orders Mark sold as an icon, with a broken Undo.** Undo on Orders refuses today (UX-195,
   HOR-07). The fix is in the later undo session. **The owner accepted this risk**: Orders'
   PickLine and RowAction convert to `sold` now, ahead of that fix.
2. **D118 slot sizes.** Inventory reserves 137x28 for the Mark sold and Retire pair. Two
   40x40 targets make each row 12px taller. That fights UX-206 and UX-169, which want a
   taller walk. `IconButton`'s own answer: draw the face at 28px, extend the hit area to
   40px. Where two hit areas overlap in a dense row, that is the inventory lane's own call.
3. **No tooltips on touch.** On a phone, sold, archive, moveTo and eraser have no visible name
   at rest. Apply the phone edge case in section 2: `IconButton`'s long-press.
4. **Findings this conflicts with:**
   - **UX-214 (FLT-19), answered by the owner.** The sort KEY stays in words, never hidden in
     an icon. The direction becomes the glyph, its words moved to the tooltip and the
     accessible name.
   - **UX-108 (shipping).** It asks for "a verb and its object" and names "Forget". As an
     icon, "Forget this file" moves to the tooltip only.
   - **UX-145.** The keycap stays after the label, but the label is now the tooltip. R and U
     leave the face. The keys sheet still lists them.
   - **UX-099.** Danger tone and ask-first must follow kit-frame's one rule for destructive
     presses. An icon adds no second pattern.
   - These findings agree with the plan: UX-056, UX-267, UX-118, UX-221, UX-222 and UX-232
     (it stays words).
   - This map does not claim UX-195, UX-249, UX-252 or UX-204. The icon does not fix those.
     They belong to the undo session.
5. **Screen readers.** A walk with 30 buttons all named "Mark sold" repeats names (UX-271).
   Every row `IconButton` needs the object in its `name`.
6. **Tests.** A spec that finds a button by its visible text (`hasText`, `text=`, the
   demo-coverage spec) will break on a converted control. Find it by its role and name.
7. **Discoverability of Manage.** Manage becomes an icon. The Orders fetch lives inside that
   sheet today (UX-193). The orders lane must move the fetch out first (HOR-05).
8. **Box-shaped glyphs.** `box`, `package` and `archive` already look alike. A box-shaped
   `moveTo` would be a fourth, and they blur at 14px. `moveTo` draws no box.

Rationale for the ruling itself, the words-vs-icon split, and the check's own build: see
D288.

## 5. Round 2: an independent review, and what it found

An Opus review of the built kit found real defects this map's own risks did not name. Its
full report and probes are kept at `SD/review/kit-icons/`. D288
has the built fix for each one:
- the hit area moved off the visual box onto a `::before` pseudo-element (FLT-24, D118)
- the tooltip's position moved to a viewport-clamped `position: fixed` (the overlay Close
  clipping, and the viewport-edge case)
- a long-press no longer also presses the button
- the Fulfiller's overlay Close is now worded (spec rule 1)
- clauses (b) and (c) of the kit check were rebuilt against a set of evasion fixtures, kept
  as permanent self-tests

`app/tests/icon-button.spec.ts` is the new browser proof.

## 6. Round 3: the anchor form

**The cause: the kit had no icon-only link.** The Orders review (`ux/kit-tighten`, round 2)
found "Cards to pull" reaching for `window.open` in an `onClick`. It opens `#/fulfillment` in
a new tab. `IconButton` rendered only a `<button>`. So the screen could not reach for a kit
link. A real `<a href>` gives middle-click for free. It also gives the browser's own
right-click "Open link in new tab" and "Copy link". `window.open` gives none of these. A
`<button onClick={() => window.open(...)}>` is a link wearing a button's clothes. The loss is
exactly that gap.

**The fix is a second form of the same primitive, not a second component.** `IconButton` now
takes `href`, plus `target` and `rel`. When `href` is set, it renders an `<a>`, not a
`<button>`. Both forms share the same `classes`. Both share the same inline face size
(`FACE_PX[size]`). Both share the same `::before` 40px hit area, the same tooltip, and the
same accessible name (`aria-label={name ?? label}`). `.bn-icon-btn` is a class selector, not a
tag selector. One stylesheet rule already covers both elements. No `transform` sits anywhere
in the hit area or the tooltip's own positioning. The round-2 centering rule carries over to
the anchor untouched. It is keyed to a class, never to `button` or `a`. A native `<a href>` is
already keyboard-operable. Enter activates it on its own. No keydown handler was added.

`type`, `disabled` and the other button-only attributes in `IconButtonProps`' `rest` are only
spread onto the `<button>` branch. They mean nothing on an `<a>`. The anchor form drops them
silently, rather than letting them land as invalid DOM attributes.

`app/tests/icon-button.spec.ts` proves it against `#/gallery`'s new "the anchor form" specimen:
`IconButton icon="external" label="Cards to pull" href="#/fulfillment" target="_blank" rel=
"noreferrer"`. It renders an `<a>` carrying the given `href`, `target` and `rel`. Keyboard
Enter follows it, read as a `page.context().waitForEvent('page')` popup. Its face, hit area
and tooltip match the `Retire` button specimen, exactly.

**`scripts/kit-adoption.mjs`'s `R2-icon-only-button` already accepted this, with no code
change.** The rule scans hand-rolled `<button>` and `<a role="button">` elements. It also
scans the kit's own `<Button iconOnly>` and vocabulary-verb shapes. It never scans the
`<IconButton>` tag itself. That tag is the sanctioned primitive, whatever props it carries.
What changed is a self-test naming the anchor form by name. A later edit to the rule cannot
start flagging it by accident:
`<IconButton icon="x" label="Open" href="#/y" target="_blank" rel="noreferrer" />` is now
asserted green, beside the existing bare-button case.

**Orders.tsx is untouched.** `app/src/Orders.tsx`'s "Cards to pull" is already a hand-rolled
`<a className="bn-btn orders-handoff" href="#/fulfillment" target="_blank" rel="noopener">`.
It carries real visible text — "Cards to pull" between two icons. It is a real link already,
and not icon-only. So `R2-icon-only-button` never reached it either way. It was not this
round's subject. The primitive was missing, and this round built the primitive.
