# Graveyard

Status: the tab is deleted (direction A, the owner's word: "A: delete the tab"). D134 (a departed
record is buried) point 5 says where its records live now. The shelf is built.

## What the tab did, and where each job lives now

| Job | Home |
|---|---|
| Sold history: which copies sold | Sales' sold list (what sold, for how much, with a photograph, `Latest` sort). Inventory with `In stock only` off (which copy, which box, which slot). |
| Retired cards: what was taken out and why | Inventory with `In stock only` off. The box summary counts them. |
| Records from deleted boxes | Inventory's `Deleted boxes` shelf. Built. See below. |
| Moved cards | The card itself. Inventory's card pane says where it came from (`CardHero.movedFromFact`). |
| Bring a card back | Inventory's card pane holds the undo (D57, mark sold is one press and undoable). A buried record cannot come back (D134, "What is lost"). |

## The Deleted boxes shelf

- It is the last cell in Inventory's box rail, beside the two pseudo shelves (pooled, no box). It
  shows only when a box was deleted with a sold or retired record in it. Under a search or a facet
  pick it is not offered, since a buried record is not a live card. A walk never opens on it. Only
  a press lands there.
- Its walk (`app/src/DeletedBoxes.tsx`, `DeletedWalk`) groups the records by the box they sat in,
  each group in slot order, with Inventory's own walk classes. `In stock only` does not apply,
  because every record on the shelf has left.
- A press on a record opens `CardHero.CardPane`, handed a card built from the record
  (`DeletedPane`). The facts beside the photograph slot say how it left and when. They also name
  the box it sat in, when the box was deleted, and when the card was captured. A card with a SKU
  links to its price history (`#/product`).
- The photograph slot says once that the photograph went with the box (`PhotoPanel`'s `gone`).
  The pane has no card actions and no Details disclosure.
- It reads `GET /graveyard?buried=1`, which answers the records of deleted boxes alone and builds
  no standing row. No new route. A failed read draws a Notice with Try again.
- The screen waits for that read before it draws the rail, so the shelf never arrives late and
  moves the walk (D313). A store with no box on hand still draws the rail for its shelf, and opens
  on it when it is the only one. The arrow keys step the records as they step a box's walk.
- Leaving the shelf for a box holds the shelf, dimmed, until that box answers (D313).
- `Manage box`'s delete panel and receipt name the shelf, and count only sold and retired records.
  A moved tombstone is buried too. A moved card is alive elsewhere, so the shelf never shows it.

## The old address

`#/graveyard` is not a route. An old link or bookmark lands on the not-found page, which offers Home
and Inventory. A redirect was not built. The owner is the only reader of the old address. A
redirect keeps a `ROUTES` entry, a README row and a roster for a screen that is gone.

## Dropped with the tab

- One list of every departure, newest first.
- The Order column. 82 of 1,183 sold rows carried one, as a clipped machine string.
- Retired cards in one place across boxes.
- The count that disagreed with Home. Only Home's count is left.

## Open

- The shelf is not in the URL, so a link cannot open it. D285 (view state lives in the URL) has not
  been applied to it.
