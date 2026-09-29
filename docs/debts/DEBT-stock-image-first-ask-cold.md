## DEBT-stock-image-first-ask-cold — the first ask for a cold catalog group answers nothing

`StockImages._tcgcsv_name_lookup` (and `url_for_line_name`) return `None` while the background
tcgcsv fetch for a group is pending. `#/revenue` asked once, so a sealed or dropped SKU in a
group not warmed at start drew "No photo found" until a reload.

**Stopgap:** `app/src/Revenue.tsx` asks a still-missing SKU once more after 5 seconds. It
covers a fetch that finishes in that window, and nothing slower.

**Cause, unfixed:** the route has no way to say "pending" apart from "no such image". A fix
would add that state to the wire (`pending` per SKU) so the client polls until it clears.
