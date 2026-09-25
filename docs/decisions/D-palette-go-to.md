## D-palette-go-to — The palette is "Go to", it lists every screen and finds cards, and the rail starts at 640

**The owner's ruling, 2026-09-23.** The palette is relabelled honestly, as "Go to". It lists every
screen, the off-nav ones included. It finds cards. The drawer and the palette hold focus, and
"More" is lit when the screen is behind it. This amends D95 (the shell is a rail, a palette and a
reference sheet). It records only what the shell lane of the 2026-09-23 overhaul adds. The
drawer's foot is D-drawer-foot-joins-the-list. The tab title and the page scaffold are
D-page-scaffold. The 720 ruling is D-one-page-width.

### The premises that no longer held

- D95 built the palette's screen list from `nav` routes only. So `#/product` had no door at all
  (UX-003), and the palette answered "Nothing matches" for "product".
- The sidebar labelled the palette "Search", and it found screens and verbs only. A typed card
  name answered "Nothing matches" (UX-022, FLT-28).
- D95 drew the phone chrome below 768. The owner's half-width Chrome window is about 720, so it
  got the phone's bars on a desk.

### What is built

- **"Go to".** The palette is the kit's `Modal`, with the title "Go to". Its Screens group is
  every `ROUTES` row, in table order. The Fulfiller's row opens his screen in a new tab, as the
  sidebar does, because his screen has no way back. The kit, Product history and Cards to pull
  are all in it.
- **Cards.** From two typed characters, the palette asks the existing `GET /search` through
  `useSearch`. It shows at most eight cards that have a SKU. A card opens with
  `openSheet('product', {sku})`: a registered product sheet opens over the page, and with none,
  `#/product?sku=` opens. A refused search hides the Cards group and shows one line. In the
  published demo, that line is "Card search is not in this demo." Elsewhere it is "Card search
  did not answer."
- **One stack of layers.** The palette, the keyboard sheet and the drawer are the kit's `Modal`
  and `Sheet`. So each one holds focus, takes Escape from the one stack and gives focus back
  (UX-014, UX-156). An option is not a Tab stop: the field names it with
  `aria-activedescendant`. The `,` chord, the Cmd-arrow step and `?` do nothing while any layer
  is open (`overlayOpen()`).
- **One door to the drawer.** The phone's top bar lost its Menu button. "More" in the tab bar is
  the one door, and it is lit (`aria-current`) when the screen is behind it (UX-046, UX-072).
- **The rail starts at 640.** The desktop rail now covers 640 to 1023, so 720 is a desk. The
  phone chrome is below 640. `App.tsx`'s `TABLET_RAIL` and `App.css` name the same edge, and
  `scripts/js-breakpoints.py` checks that they agree. From 640 up, `App.css` sets
  `--bn-topbar-h` and `--bn-tabbar-h` to zero. So a screen's own phone rule at 767 leaves no gap
  for a bar that the shell does not draw.
- **The keyboard sheet is derived from `ROUTES`.** A route carries its own keys (`Route.keys`).
  The jump group lists every route: its `,` letter, or the palette for a route with none. The
  sheet opens on its keys, with no paragraph about itself (UX-119). ReloadButton's `R` is a row.
- **A skip link, and focus after a navigation (UX-092).** The first Tab stop is "Skip to the
  screen". After a navigation, focus that sits in the chrome or on nothing moves to the new
  screen's heading.

### What proves it

`app/tests/nav.spec.ts` adds a `ROUTES` row that the repo does not have. It does this in the
browser, and changes only the one served `App.tsx` response. With no other edit, the row gets
its nav link, palette entry, jump entry, own keys, tab title and page scaffold. The same file
asserts the focus trap on the palette, the keyboard sheet and the drawer. It also asserts the
card search, the refused search, the gated keys, the skip link and "More".
`app/tests/scaffold.spec.ts` reads the palette's Screens group for every route.

### What is not built

- The demo's own `/search` answer is the demo lane's. Until it lands, the published demo shows
  the refusal line.
- The kit's modal and sheet still rise from the bottom below 768, their own edge. Moving that
  edge to 640 is a kit change.
