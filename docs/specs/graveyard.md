# Graveyard

Status: built as D134 (a departed record is buried) point 5 describes, less the Moved tab. The
rethink below is open. The owner picks a direction. Nothing here repeals D134.

## Rethink: keep, slim or delete the tab

The owner's ruling for this pass: "rethink only, and in that rethink part of the choices can
very much be that this is unnecessary to keep as a tab".

### What a blind review found

- Rows are inert. A row opens nothing.
- The Order column is a clipped machine string. Only 82 of 1,183 sold rows carry one.
- The "Its box was deleted" pill is clipped.
- Sold rows repeat Sales with less: no price, no photograph.
- The sold count disagrees with Home: 1,183 here, 1,145 there. The 38 extra rows sold from boxes
  that were deleted later. Home counts standing boxes only.
- The filter and the search are not in the URL (D285, view state lives in the URL).

Counts are from the demo mirror, which is the scrubbed real store (D295, the public demo is the
scrubbed real store): 1,199 rows. 1,145 sold and 15 retired sit in boxes that still stand. 38 sold
and 1 retired survive only as burial lines. Retire reasons: 11 pulled, 4 lost, 1 given away.

### The jobs it does today

| Job | Who needs it | Where else it is already done |
|---|---|---|
| Sold history: which copies sold | Owner, looking back | Sales' sold list (what sold, for how much, with a photograph, `Latest` sort). Inventory with `In stock only` off (which copy, which box, which slot). Inventory search names a sold-out best match (the top-tier notice). |
| Retired cards: what was taken out and why | Owner, after a loss or a pull | Inventory with `In stock only` off, for the 15 in standing boxes. Box summary counts them. |
| Records from deleted boxes | Owner, after `Delete box` | Nowhere. Only this screen reads the burial lines. 39 rows. |
| Moved cards | Owner, finding a card that moved | Already left this screen (the UX review's graveyard ruling). Inventory's card pane says where it came from (`CardHero.movedFromFact`). |
| Bring a card back | Owner, after a wrong sale or retire | Never done here. Inventory's card pane holds the undo (D57, mark sold is one press and undoable). A buried record cannot come back (D134, "What is lost"). |

So one job has no other home: the 39 records whose box was deleted. That is the outcome D134
protected: a departed card's history is not lost when its box goes.

### Direction A: delete the tab

Remove `#/graveyard` from `ROUTES`, with its nav row and the `g` hotkey. Each job moves:

| Job | New home |
|---|---|
| Sold history | Sales' sold list, unchanged. Inventory with `In stock only` off, unchanged. |
| Retired cards | Inventory with `In stock only` off, unchanged. |
| Records from deleted boxes | A `Deleted boxes` shelf at the foot of Inventory's box rail, beside the two pseudo shelves that exist now (pooled, no box). Its walk lists the records grouped by the box they sat in. A press opens a record pane: name, number, set, condition, how and when it left, the box and when it was deleted, a link to that card's price history (`#/product`). It says once that the photograph went with the box. |
| Moved cards | Unchanged. |
| Bring a card back | Unchanged. |

`Manage box`'s delete panel and receipt name the `Deleted boxes` shelf, not the graveyard. The
shelf reads the burial half of `GET /graveyard`. No new route.

- **Drops:** one list of every departure, newest first. The Order column. Retired cards in one
  place across boxes.
- **What still protects D134's outcome:** the burial line is unchanged, and the shelf reads it
  where the owner already looks for where a card is.
- **Gains:** one fewer nav row. The count disagreement goes, because only Home's count is left.
- **Images:** `A-inventorydeleted-*`, `A-inventory-*` (`In stock only` off), `A-sales-*` (Latest).

### Direction B: an off-nav log of what nothing else shows

Keep the route, off-nav, the same shape as `#/product` (D227, a route not a lens). Retitle it
"Retired and deleted". It lists only retired cards and records from deleted boxes: 54 rows. Sold
rows in standing boxes leave, because Sales and Inventory hold them. Inventory's box rail gets
one quiet link at its foot, with the count. The palette still reaches it.

Rows open something: a standing record opens Inventory on that card, a buried one opens its
price history. A standing row shows its photograph. The Order column goes. Filter and search
live in the URL.

- **Drops:** sold rows. The nav row.
- **What still protects D134's outcome:** the log itself, one link from Inventory.
- **Gains:** a short list a person can read. The count disagreement goes.
- **Images:** `B-graveyard-*`, `B-inventory-*`.

### Direction C: keep the tab, fixed

Keep every row and the nav row. Fix the review's findings in place:

- Rows open the card, as in B. Standing rows show their photograph.
- The Order column goes. The deleted-box fact is a second line under the box name, not a pill.
- A fourth filter, `From deleted boxes`, so the 39 can be found.
- The lede gives the standing sold count, which is Home's figure, so the two agree.
- Filter and search live in the URL.

- **Drops:** the Order column, and nothing else.
- **What still protects D134's outcome:** the screen, unchanged in scope.
- **Gains:** least change. Keeps the "history log" the owner asked for in D134.
- **Images:** `C-graveyard-*`, `C-graveyarddeleted-*`.

### Recommendation

A. 97% of the rows repeat a screen that does the job better. The 39 rows that do not are a fact
about where a card was, and Inventory is the screen for where a card is. If the owner wants the
single history list D134 quoted ("I just need a history log"), B keeps it at the lowest cost.

The owner picks. The pick then amends D134 point 5.

### Records to fix whichever direction wins

- D134 point 5 lists five filter tabs (All, Sold, Retired, Moved, Buried) and calls it the
  twelfth route. Three tabs ship, and route counts are read from `ROUTES`.
- `docs/map.py`'s `src/Graveyard.tsx` entry cites `positionOf` and `storeKey.ts:storeKeyText`
  and the `B9 #3` form. D259 (boxes show names only) replaced them.
- D259's "What is still open" bullet and `CardHero.movedFromFact`'s comment cite
  `Graveyard.tsx:movedToName`. It is gone, and moved rows no longer reach this screen.
- `docs/specs/box-map.md`, "Open": "A 40-card move adds 40 rows". A move adds no row here now.
- `BoxOps.DeleteBox`'s notice counts moved records among the "departed records" it will bury.
  Moved records are buried but never shown. Its receipt names "the graveyard", which A and B
  rename.
