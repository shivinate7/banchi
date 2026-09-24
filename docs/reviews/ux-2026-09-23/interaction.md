# Interaction and feedback

Lens 4. Target: the published demo `https://shivinate7.github.io/banchi/`, driven by headless Chromium from Playwright 1.58.0.

Routes come from `app/src/App.tsx` `ROUTES`: `/`, `/capture`, `/runs`, `/review`, `/pricing`, `/orders`, `/shipping`, `/revenue`, `/inventory`, `/graveyard`, `/codes`, `/fulfillment`, `/gallery`, `/product`.

Shots are in INT screenshot, not kept.
Scripts and raw measurements are in INT scratch file, not kept. The main files are `states-light.json`, `states-dark.json`, `press-1440.json`, `press-390.json`, `keyboard.json`, `loading-1440-light.json` and `flow-*.log`.

How I measured:

- **Hover, focus, pressed.** `states.mjs` reads the computed style of each visible control in `.bn-view`, up to 3 per class signature. It reads the style at rest, under a real mouse hover, and with `:focus-visible` and `:active` forced through CDP. It waits 350 ms for each transition.
- **Shifts.** `press.mjs` loads the route fresh for each button, link, summary or checkbox. It records the document-space rect of every element, presses, waits 900 ms and records again. It reports every element outside the control, its ancestors and any new dialog that moved more than 1 px. I ignore moves of the sticky shell that come only from page scroll.
- **Loading.** The demo answers in-process (`demoServer.ts`, a 45-135 ms `setTimeout`). No network request exists to intercept. So `loading.mjs` intercepts the `demoServer-*.js` bundle and replaces that delay with 2000 ms.

## Control inventory

Legend: H = hover changes. F = visible focus ring on keyboard focus. P = pressed dip (`translate: 0 1px`, plus `scale(.99)` on `bn-btn`). "None" shows that nothing changes. For overlays, "Esc" tells if Escape closes it, and "return" tells if focus goes back to the opener.

| Route | Control | Kind | States seen (1440, light) |
|---|---|---|---|
| shell | Sidebar nav link (`bn-nav-link`) | link | H bg and ink. F outline 2 px accent. P dip |
| shell | Collapse the sidebar (brand) | button | H bg. F. P dip |
| shell | Search ⌘K, Dark mode (`bn-btn-ghost`) | button | H bg and ink. F. P dip and scale |
| shell | Command palette | sheet, not `aria-modal` | Opens on ⌘K and on Search. Esc closes it. Focus goes to body, not to Search. Tab leaves it (4 of 20 stops) |
| shell | Keyboard sheet `?` | sheet | Opens on every owner route. Focus goes to its search field. Esc closes it |
| shell | Phone drawer (Menu) | sheet | Focus stays on Menu. Esc closes it and focus is on Menu. A backdrop tap closes it and focus goes to body |
| shell | Toast (`bn-toast`) | receipt | Dark card, bottom right, with Undo and ×. Seen on Capture (Clear the setup) and Pricing (Release) |
| `/` | Standing row "Cannot be filled" | link | H shadow and underline. F. P dip |
| `/` | Start capturing (`bn-btn-primary lg`) | button | H bg and glow. F. P dip, scale, darker |
| `/` | Stage tiles (6) | link | H shadow and lift. F. P dip |
| `/` | Deck picture | link | H none. F. P dip |
| `/` | Box rows, run rows | link | H bg. F. P dip |
| `/capture` | Box field row (`capture-row-lg`) | toggle | H none. F. P dip. Opens inline with focus in its search field |
| `/capture` | Set hint, Rarity, Finish, Game, Camera, Rotation, Trigger rows | toggle | H bg. F. P dip. Set hint opens with focus in its field. The others open with focus on body |
| `/capture` | Capture card (`bn-btn-primary xl`) | button | H bg and glow. F. **P: darker only, no dip** |
| `/capture` | Open the camera, Pick a box (`bn-btn-sm`) | button | H bg. F. P dip and scale |
| `/capture` | New section, Clear the setup | button | Disabled at rest (cursor not-allowed). Clear gives a toast with Undo |
| `/capture` | Tuning | summary | H bg and ink. F. P dip |
| `/runs` | Reload boxes and runs (icon, ghost) | button | H bg. F. P dip. **No busy state during a 2 s reload** |
| `/runs` | Reconcile the whole store | button, opens a right sheet | H bg. F. P dip. The sheet is `aria-modal` and keeps Tab. Esc and return work |
| `/runs` | Identify cards | button, opens a centred modal | H bg and glow. F. P. The modal has a stepper and keeps Tab. Esc and return work |
| `/runs` | Run row | toggle (selects) | H bg. F. P dip. Selected: accent bar and tint |
| `/runs` | Step rows (Identify, Join, Emit, Reconcile) | toggle (accordion) | Opens in place |
| `/pricing` | Find by value, Mark down stale, Clear typed (`bn-btn`) | button | H bg. F. P dip and scale |
| `/pricing` | Mark down stale | right sheet | Keeps Tab. Esc and return work. The dismiss word is "Not now" |
| `/pricing` | Clear typed | right sheet | **Tab leaks (10 of 20 stops outside).** Esc closes it. **Focus goes to body.** The dismiss word is "Cancel". The destructive button is red |
| `/pricing` | Runs picker | popover, not modal | Tab walks into the page. Esc and return work |
| `/pricing` | Reload R | button | H. F. P. Disabled with a spinner while it reads |
| `/pricing` | Cut-off field | field | H bg. F: tint ring (box-shadow), no outline |
| `/pricing` | Rule presets (Match market and others) | toggle (segmented) | The selected item has no hover. The others: H ink. F. P dip |
| `/pricing` | Qty field (`bn-input`) | field | H border. F border and ring |
| `/pricing` | Price field (`pricing-input`) | field | H none. F ring on the wrapper. **9 px wide at 1280 px and wider** (INT-01) |
| `/pricing` | Photo thumb, history, hold (icon, ghost, sm) | button | H. F. P |
| `/pricing` | Hold panel | popover | Focus goes to "Bullish". Esc closes it. **Focus goes to the price field, not to Hold** |
| `/pricing` | Compare, Holding, Load trends | toggle | H. F. P. Each one lays the table out again (INT-19) |
| `/pricing` | Write the import file (`bn-btn-primary lg`) | button | H. F. P dip and scale |
| `/pricing` | "14 never identified", "9 in review" | link | H none. F. P dip |
| `/shipping` | Orders and Shipping stage tabs (`bn-tab`) | link (tab) | H ink. F. P dip |
| `/shipping` | Forget (`bn-btn-danger`) | button | H bg. F. P. **No confirmation** |
| `/shipping` | Fill pick locations, Download | button, link | H. F. P |
| `/shipping` | Lane chips Envelope and Parcel | toggle (fold) | H shadow. F ring. P dip and scale |
| `/shipping` | Lane chip "Needs a look" | toggle (fold) | H shadow. **F: no visible ring.** P |
| `/revenue` | Period segmented control, sort headers | toggle | H ink. F. P dip. Each one writes the URL |
| `/revenue` | Month rows | toggle (filter) | H bg. F. P dip |
| `/revenue` | Search (`SearchField`) | field | `/` puts focus in it. F ring on the wrapper. × clears it. Esc removes focus and keeps the text |
| `/revenue` | Row disclosure | toggle | H bg and ink. F. P dip. Focus stays on it and the label changes to "Hide …" |
| `/revenue` | Compare to today's market, Value my stock (ghost, sm) | button | H. F. P. After Value my stock, **focus goes to body** |
| `/graveyard` | Reload (icon, ghost), Try again | button | H. F. P. **No visible answer to a press** |
| `/codes` | Reload (icon, ghost) | button | H. F. P. **No busy state** |
| `/codes` | Read a box | button, opens a right sheet | The sheet is `aria-modal`. **Tab leaks (18 of 20 stops).** Esc and return work. Icon-tile header, inline actions, no footer |
| `/codes` | Go to capture (empty-state action) | button | H. F. P |
| `/fulfillment` | Search (`SearchField`, 60 px) | field | F ring on the wrapper. **`/` does not put focus in it** |
| `/fulfillment` | Box headers | toggle (accordion) | H bg. F. P dip |
| `/gallery` | Kit index, button matrix, motion swatches | button | Every `bn-btn` variant: H. F. P dip and scale |
| `/product` | SKU field (`bn-input`) and `Look up` | field and button | H border. F border and ring. Enter submits. `Look up` with an empty field does nothing |

Where the same kind of control behaves differently:

- Capture card is the only primary button with no press dip.
- "Needs a look" is the only lane chip with no focus ring.
- The Capture Box row is the only capture row with no hover.
- Five overlays show three trap behaviours and three focus-return behaviours (INT-06, INT-07).
- Reload buttons show a busy state on Pricing and Review only (INT-12).
- Search has three forms: `SearchField` with `/` on Sales, `SearchField` with a dead `/` on Fulfillment, and a plain field with a button on Product (INT-25).

## Grade matrix

| Route | Grade | One-line reason |
|---|---|---|
| `/` | B | Clear hover, focus and press on every tile. While loading, tiles say "no boxes yet" and "no export read yet" (INT-13) |
| `/capture` | D | A refused shot adds a Recent tile. New section prints a raw JS error. The refusal banner pushes the Capture button down 123 px (INT-02, INT-03, INT-04) |
| `/runs` | B | Both overlays keep and return focus well. The reload has no busy state. The refusal prints a raw code (INT-12, INT-08) |
| `/review` | HELD | Main state. Not graded |
| `/pricing` | F | At 1280 px and wider, the price field is 9 px wide and shows "$ 1" for $13.11 (INT-01). The U key, the Clear typed sheet and the presets also fail (INT-11, INT-06, INT-19) |
| `/orders` | HELD | Main state. Not graded |
| `/shipping` | C | Forget has no confirmation. A refusal pushes the page 123 px. "Needs a look" has no focus ring. The loading frame draws the empty drop zone (INT-17, INT-10, INT-16, INT-13) |
| `/revenue` | B | Search, `/`, Esc and URL state are solid. Error notices push the table 112 px and print raw URLs. Value my stock loses focus (INT-10, INT-08, INT-07) |
| `/inventory` | HELD | Main state. Not graded |
| `/graveyard` | C | In the demo, the only state is an error. It looks like a neutral empty state and names a repo command. Try again gives no answer (INT-09, INT-08, INT-26) |
| `/codes` | C | A good empty state. The Read a box sheet lets Tab into the page behind it. A refusal pushes the form 103 px. The reload has no busy state (INT-06, INT-10, INT-12) |
| `/fulfillment` | B | Large targets and a real empty sentence. The listed `/` key does nothing. A failed search gives a remedy that cannot work (INT-24, INT-31) |
| `/gallery` | B | Every button variant shows all three states. The kit has no sheet or dialog primitive, so each screen builds its own (INT-18) |
| `/product` | D | No screen, nav entry or palette command leads to it. `Look up` on an empty field does nothing. Its error prints a raw path (INT-30, INT-25, INT-08) |

## Findings

### INT-01 The price field shows only the first digit of the price at desktop widths
- Severity: S1
- Screens: `/pricing`
- Where: 1280, 1440 and 1920 px, light and dark (dark measured at 1440). At 1024 px and narrower the field is correct.
- Repro: open `#/pricing` at 1440x900. Read the LISTS AT column of the "Above the cut-off" table.
- Seen: the price `<input>` is 8.5 px wide inside its pill. For the value 13.11 it draws "$ 1". For 2.52 it draws "$ 2", and every cheap row reads "$ 0". So the whole column reads as whole dollars. After I typed 9.99 the row read "$ 9". At 820 and 1024 px the same field is 65 px wide and draws "$ 13.11". Measured and seen.
- Shot: INT-01, screenshot not kept.
- Direction: the owner can read the full price at every width. It is the one number on this screen that decides money.
- Component: `app/src/Pricing.tsx`, the SKU row in the desktop table layout. The field is `input.pricing-input` inside `.pricing-field`, with `flex: 1 1 auto` and `min-width: 0`.
- Annotation: no decision covers this. D221 (money stays mono) rules the face of a dollar figure, not the width of its field. The 2026-09-20 review (`ux-2026-09-20/pricing.md`) did not log it.

### INT-02 A refused capture adds a Recent tile, but the banner says that the card was not recorded
- Severity: S2
- Screens: `/capture`
- Where: 1440, light (seen). Other sizes not checked.
- Repro: `#/capture`. Press "Open the camera". Pick a box (B, then ↓ and Enter). Press C.
- Seen: a red banner says "Captures are paused — the card was not recorded". At the same time the RECENT strip shows a new "B1 #42" tile with a blue U badge. Its caption says that U undoes the newest. Then U says "Undid 0 of 1." The screen says two opposite things about one shot.
- Shot: INT-02, screenshot not kept.
- Direction: a shot that the server refused never looks like a shot that landed. Show it as failed, or do not show it.
- Component: `app/src/CaptureScreen.tsx` `CaptureScreen`, the paused banner and the RECENT strip.
- Annotation: no decision covers this. D164 (the undo stack is the sitting) rules what U undoes, not how a refused shot draws.

### INT-03 New section prints a raw JavaScript exception
- Severity: S2
- Screens: `/capture`
- Where: 1440, light
- Repro: `#/capture`. Open the camera, pick box 1 and press C (refused). Then press S or "New section".
- Seen: a red line under the button says "Cannot read properties of undefined (reading 'length')". The demo's own notice tells the owner that dividers "write for real — try those", so this path is one the demo invites. The owner cannot act on a TypeError string.
- Shot: INT-03, screenshot not kept.
- Direction: a failed divider says what failed and what to do next. The text of a client crash never reaches the screen.
- Component: `CaptureScreen.tsx`, the New section handler and its inline error line. The answer shape can come from `demoServer.ts` `openSection`.
- Annotation: no decision covers this.

### INT-04 The capture refusal banner pushes the whole screen down 123 px, the Capture button too
- Severity: S2
- Screens: `/capture`
- Where: 1440, light
- Repro: as INT-02. Press C when the capture is refused.
- Seen: a banner appears above the page header. The header, the RUN card and the Capture card button all move down: the header moves from y 43 to y 166. The next press at the same place hits a different control. At this moment the operator's hand is on the rig.
- Shot: INT-04, screenshot not kept.
- Direction: a refusal during capture does not move the controls under the hand. Give it a reserved place, or draw it over the page.
- Component: `CaptureScreen.tsx`, the paused banner at the top of the view.
- Annotation: violates D118 (a press changes what is on the screen, never where the rest of it is).

### INT-05 Opening the Box field moves the Capture button 202 px (258 px on a phone)
- Severity: S3
- Screens: `/capture`
- Where: 1440 and 390, light
- Repro: `#/capture`. Press B, or press "Pick a box" in the BEFORE YOU CAN CAPTURE block.
- Seen: the Box row opens inline with a search field and four boxes. The Capture card button, the blocker and "Pick a box" itself move down 202 px at 1440 and 258 px at 390. Set hint moves the rows below it 95 px. Rarity moves them 420 px, and 576 px at 390. The shifts are measured. The open Box field is seen.
- Shot: INT-05, screenshot not kept.
- Direction: choosing a box does not move the button that the owner presses next. Open the choice over the stack, or keep the Capture button where it was.
- Component: `CaptureScreen.tsx` `Row` and `OpenField` for the Box, Set hint and Rarity fields.
- Annotation: violates D118 (a press changes what is on the screen, never where the rest of it is). An inline field that pushes the next control is the case D118 measured on Inventory.

### INT-06 Two modal sheets and the palette let Tab walk into the page behind them
- Severity: S3
- Screens: `/codes`, `/pricing`, shell
- Where: 1440, light
- Repro: on `#/codes`, put focus on "Read a box" and press Enter. Press Tab 20 times. Do the same with "Clear typed" on `#/pricing` and with the sidebar Search.
- Seen: Read a box has `aria-modal="true"`, but 18 of 20 Tab stops land on the sidebar and page behind the scrim. Clear typed: 10 of 20. The command palette: 4 of 20. Identify cards, Reconcile the whole store and Mark down stale keep all 20 stops inside. So one kind of overlay has two keyboard behaviours. Measured, not seen.
- Shot: INT-06, screenshot not kept.
- Direction: every overlay that blocks the page keeps keyboard focus inside itself until it closes, the same way on every screen.
- Component: `app/src/Codes.tsx` local `Sheet`. `app/src/ClearPrices.tsx`. `app/src/App.tsx` `CommandPalette`.
- Annotation: no decision covers this. D95 (the shell is a rail, a palette and a reference sheet) builds the palette but rules no focus behaviour for it or for any sheet.

### INT-07 When an overlay closes, focus often drops instead of going back to its opener
- Severity: S3
- Screens: shell, `/pricing`, `/capture`, `/revenue`, `/graveyard`
- Where: 1440, light
- Repro: open each overlay from its button, then press Escape.
- Seen:
  - Palette opened from Search: focus goes to body. If Tab moved first, focus goes to a nav link.
  - Clear typed: focus goes to body.
  - Hold panel: focus goes to the price field, not to the Hold button.
  - Set hint on Capture: focus goes to body.
  - Value my stock on Sales and Try again on Graveyard: the screen replaces the pressed button, and focus goes to body.
  - Identify, Reconcile, Mark down, the Runs picker and Read a box return focus correctly.
  - After a route change, focus is on body on every screen.

  Measured, not seen.
- Shot: INT-07, screenshot not kept.
- Direction: after a sheet, panel or press closes, focus is where the owner left it, on every screen.
- Component: `App.tsx` `CommandPalette`. `ClearPrices.tsx`. `Pricing.tsx` hold panel. `CaptureScreen.tsx` `OpenField`. `Revenue.tsx` shelf. `Graveyard.tsx` error state.
- Annotation: no decision covers this.

### INT-08 Error and refusal states print raw server strings: machine codes, URL paths and a repo command
- Severity: S3
- Screens: `/runs`, `/pricing`, `/capture`, `/codes`, `/shipping`, `/revenue`, `/product`, `/graveyard`
- Where: all
- Repro, any of these:
  - `#/runs`, Reconcile the whole store, then Fetch my live listings.
  - `#/pricing`, Write the import file.
  - `#/revenue`, Compare to today's market.
  - `#/product?sku=999999999`.
  - `#/graveyard`.
- Seen:
  - Each refusal adds a mono line with the machine code, for example `demo_no_session`, `demo_read_only`, `demo_no_camera` or `demo_not_recorded`.
  - Some print the request path, for example "/pipeline/products/999999999/history". One prints "GET /pipeline/price-now?sku=9027180&sku=…" with a dozen SKUs.
  - Graveyard, Product, Sales and price history print "Rebuild it with `make demo`".
  - The words come from the demo. But the screens draw the message and code that arrive, verbatim, so a real server's raw text reaches the owner the same way.
- Shot: INT-08, screenshot not kept.
- Direction: a refusal is one sentence and one way forward. Codes and paths stay behind a disclosure, as Capture's "What the server said" already does.
- Component: the shared refusal `Notice` with its `code` line (`app/src/kit/index.tsx` `Notice`), used by `LiveReconcile.tsx`, `Pricing.tsx`, `Codes.tsx`, `Shipping.tsx`, `Revenue.tsx` and `ProductHistory.tsx`. Also `Graveyard.tsx` `EmptyState`.
- Annotation: violates D196 (no user-visible string may name a decision, a repository path, or a pipeline-internal noun). The `make demo` text and the `/pipeline/…` paths come from the server, so the `no mechanism on screen` audit row cannot see them.

### INT-09 Each screen puts its refusal in a different place and style
- Severity: S3
- Screens: `/capture`, `/runs`, `/pricing`, `/codes`, `/shipping`, `/revenue`, `/product`, `/graveyard`
- Where: 1440, light
- Repro: cause each refusal in INT-08.
- Seen:
  - Capture: a full-width red banner above the page header, with a Resume button.
  - Identify: an orange warning in the modal's side pane, "What this reading sends".
  - Reconcile: a red notice below the controls.
  - Codes: a red notice with × at the top of the sheet, above the form.
  - Pricing: a red notice inside the sticky write bar, which grows upward over the table.
  - Shipping: a red block above the file panels.
  - Sales: a red notice below the shelf toolbar.
  - Product: a red notice under the field.
  - Graveyard: a neutral empty-state card with an accent-blue icon. It does not look like an error.
  - Only Codes lets the owner dismiss the notice. Only Capture offers a next step.
- Shot: INT-09, screenshot not kept.
- Direction: one refusal shape, next to the control that caused it, with the same tone and the same next step on every screen.
- Component: per screen, as in INT-08.
- Annotation: no decision covers this.

### INT-10 A refusal or result notice pushes the page under the pointer
- Severity: S3
- Screens: `/shipping`, `/codes`, `/revenue`, `/pricing`
- Where: 1440 and 390, light
- Repro and seen (`press.mjs` shifts, confirmed in the shots):
  - `#/shipping`, Forget or Fill pick locations: 4,164 elements move down 123 px at 1440 and 162 px at 390, the pressed button too.
  - `#/codes`, Read a box, then Read the box: the form and the pressed button move down 103 px.
  - `#/revenue`, Compare to today's market: the product table moves down 112 px, at 1440 and at 390.
  - `#/pricing`, Write the import file: the sticky bar grows upward over the rows.
- Shot: INT-10, screenshot not kept.
- Direction: a press answers in place. The control and the rest of the screen stay where they were.
- Component: `Shipping.tsx` file panel. `Codes.tsx` `Sheet`. `Revenue.tsx` compare notice.
- Annotation: violates D118 (a press changes what is on the screen, never where the rest of it is).

### INT-11 On Pricing, U works only in a price field, but the "Undo U" button stays on screen
- Severity: S3
- Screens: `/pricing`
- Where: 1440, light
- Repro: `#/pricing`. Type 9.99 in the first price and press Enter. Press Escape, which the sheet says will "leave the field". Press U.
- Seen: nothing happens, and the value stays 9.99. The toolbar still shows "Undo U". U works only while a price field has focus, and the toolbar button always works. The `?` sheet does say "Everything but R and T is pressed inside a price field". But the keycap next to Undo shows U with no condition. On Capture, U works with focus anywhere.
- Shot: INT-11, screenshot not kept.
- Direction: the key drawn next to Undo does what it shows from anywhere on the screen. Or the keycap shows only where the key works.
- Component: `Pricing.tsx`, the row key handler and the toolbar Undo button.
- Annotation: no decision covers this. The `?` sheet's Pricing note is the only record of the rule.

### INT-12 Reload buttons show a busy state on two screens and nothing on three
- Severity: S3
- Screens: `/runs`, `/graveyard`, `/codes`, against `/pricing` and `/review`
- Where: 1440, light, with answers delayed 2 s
- Repro: load `#/runs` with the delayed demo and wait for the list. Press the reload icon and look at 400 ms.
- Seen: on Runs, Graveyard and Codes the icon stays enabled, shows no spinner, and the content does not change for 2 s. On Pricing and Review the button is disabled and spins. The R key reloads on Pricing and Review only, as the `?` sheet lists. On Runs, Graveyard and Codes, R does nothing (measured).
- Shot: INT-12, screenshot not kept.
- Direction: every reload shows that it is reading, the same way. Every screen with a reload answers the same key.
- Component: the icon `Button` with `icon="refresh"` in `Runs.tsx`, `Graveyard.tsx` and `Codes.tsx`.
- Annotation: no decision covers this.

### INT-13 While loading, screens state an empty store as fact
- Severity: S3
- Screens: `/`, `/shipping`, `/pricing`, `/capture`
- Where: 1440, light, with answers delayed 2 s
- Repro: load each route with the delayed demo and look at 350 ms.
- Seen:
  - Home: the Capture tile says "no boxes yet" and the Shipping tile says "no export read yet". The Pricing and Orders tiles say "reading…".
  - Shipping: the full empty state, "Drop the Export Shipping file here", and a "No export" badge on the tab. Then it changes to 331 loaded orders, and the whole layout jumps.
  - Pricing: the green "Saved" pill shows before anything is read.
  - Capture: "No box yet" and "— next index", with no reading indicator.
- Shot: INT-13, screenshot not kept.
- Direction: until the answer arrives, a screen says that it is reading. It never says "none" or "saved".
- Component: `Home.tsx` stage tiles. `Shipping.tsx` first state. `Pricing.tsx` save pill.
- Annotation: no decision covers this. D171 (a refusal that reaches nobody did not happen) names the same class for sessions: a reader that cannot tell "nothing is wrong" from "nothing is known yet".

### INT-14 Loading takes four forms, and the Pricing header changes shape when the data arrives
- Severity: S3
- Screens: all routes that load data
- Where: 1440, light, with answers delayed 2 s
- Seen:
  - Skeleton rows: Home lists, Runs, Pricing, Graveyard, Codes.
  - Only a text line: Sales, "Reading your orders…".
  - A spinner and a sentence: Fulfillment, "Getting the cards."
  - Nothing: Capture, Shipping, Product.
  - On Pricing, the toolbar is in the title row while it loads. After the load it moves below a new subtitle and progress bar, and all content under the title jumps.
- Shot: INT-14, screenshot not kept.
- Direction: one loading style, and a loading frame with the same shape as the loaded screen.
- Component: per screen.
- Annotation: no decision covers this.

### INT-15 No skip link: each screen starts 15 Tab stops into the sidebar, and a route change leaves focus behind
- Severity: S3
- Screens: all owner routes
- Where: 1440, light
- Repro: load `#/` fresh. Press Tab and count the stops before the first control of the screen.
- Seen: 15 sidebar stops come first: the brand toggle, 11 links, Cards to pull, Search and Dark mode. No "skip to content" link exists. After Enter on a sidebar link, focus stays on that link. After a `,` chord, focus goes to body. The `?` sheet says that Banchi "is meant to be driven from the keyboard", but the screen's own controls are the slowest to reach.
- Shot: INT-15, screenshot not kept.
- Direction: after any navigation, one key press reaches the screen's first control.
- Component: `App.tsx` shell (`Sidebar` and `.bn-view`).
- Annotation: no decision covers this. D201 (a route change lands at the top) rules scroll position, not focus.

### INT-16 The "Needs a look" lane chip has no focus ring
- Severity: S3
- Screens: `/shipping`
- Where: 1440, light (seen). In dark, measured the same.
- Repro: `#/shipping`. Tab to the lane chips.
- Seen: Envelope and Parcel draw a 2 px accent ring. "Needs a look" keeps only its dashed orange border, and nothing shows that it has focus.
- Shot: INT-16, screenshot not kept.
- Direction: every chip shows focus the same way.
- Component: `app/src/Shipping.tsx`, `.shipping-chip-unjudged`.
- Annotation: no decision covers this. D50 (an interactive element's feedback is the product's) sets cursor, hover and press floors, and no focus floor.

### INT-17 Destructive presses follow three different patterns
- Severity: S3
- Screens: `/shipping`, `/pricing`, `/capture`
- Where: 1440, light
- Repro and seen:
  - `#/shipping`, Forget: a red danger button that drops the loaded export. It acts at once, with no confirmation. The demo refuses the write, so I cannot tell if an undo follows.
  - `#/pricing`, Clear typed: a sheet that asks first, with the count on a red button ("Clear 21 typed prices") and a line that says Undo is on the receipt.
  - `#/capture`, Clear the setup: no confirmation, then a toast with Undo.
  - `#/pricing`, Release on a held row: no confirmation, then a toast with Undo.
- Shot: INT-17, screenshot not kept.
- Direction: one rule for which presses ask first and which offer Undo after, applied to every press that removes something.
- Component: `Shipping.tsx` Forget. `ClearPrices.tsx`. `CaptureScreen.tsx` clear. `Pricing.tsx` release.
- Annotation: caused by D142 (the setup outlives the browser) for the Capture half: it rules no dialog and a receipt toast with Undo. D168 (a typed price is cleared by a press) rules the Clear typed sheet. No decision covers Forget. The three rulings were made one screen at a time, and no rule joins them.

### INT-18 Overlays come in four designs, with different headers, dismiss words and first focus
- Severity: S3
- Screens: `/runs`, `/pricing`, `/codes`
- Where: 1440, light
- Seen:
  - Identify cards: a centred modal with a stepper and a footer (Cancel, Continue). First focus is on the dialog container.
  - Reconcile, Mark down stale and Clear typed: a right sheet with an eyebrow, a title and ×. First focus is on the sheet. The footer says "Not now" on Mark down and "Cancel" on Clear typed. Reconcile has no footer.
  - Read a box: a right sheet with an icon-tile header and no eyebrow. Its actions are inline and it has no footer. First focus is on the box select.
  - The Runs picker and Hold: popovers.
  - The kit on `#/gallery` has no sheet or dialog primitive. Codes has its own `Sheet` component.
- Shot: INT-18, screenshot not kept.
- Direction: one sheet, one modal and one popover from the kit, each with the same header, dismiss word and first focus.
- Component: `RunsComposer.tsx`, `LiveReconcile.tsx`, `Markdown.tsx`, `ClearPrices.tsx`, `Codes.tsx` `Sheet`.
- Annotation: no decision covers this.

### INT-19 The Pricing view toggles lay the whole table out again
- Severity: S3
- Screens: `/pricing`
- Where: 1440 and 390, light
- Repro and seen (`press.mjs`):
  - Match market to Market −5% or TCG Low −1%: every row moves 2 px (1,016 elements), because the rule caption changes height.
  - Load trends: the table moves down 50 px and the QTY column moves 140 px left. At 390 the rows move 75 px.
  - Custom: the rule sentence moves 458 px right. At 390 the table moves down 130 px.
  - Compare: LISTS AT and the row actions move 160 to 224 px right. A new column can explain that one.
  - Give this run its own cut-off: the run card header moves up 29 px. At 390, 1,098 elements move 8 to 17 px.
- Shot: INT-19, screenshot not kept.
- Direction: a preset or a trend load does not move the row that the owner is reading.
- Component: `Pricing.tsx` preset control, `.pricing-rule-says`, trend loader.
- Annotation: violates D118 (a press changes what is on the screen, never where the rest of it is).

### INT-20 Release moves the row away from the pointer
- Severity: S3
- Screens: `/pricing`
- Where: 1440, light
- Repro: `#/pricing`, the "Held back from this run" group. Press the open lock (Release) on Astral Heron.
- Seen: the row leaves the held group and 658 elements move. The header counts change width ("8 nothing to add" moves 95 px). The toast "Released Astral Heron … Undo U" is good. But the next row slides under the pointer.
- Shot: INT-20, screenshot not kept.
- Direction: a released row stays in place until the owner leaves it, as the frozen order on Inventory already does.
- Component: `Pricing.tsx` held section.
- Annotation: violates D118 (a press changes what is on the screen, never where the rest of it is). D181 (the order is taken once, and a sale may not retake it) already solves the same problem on Inventory.

### INT-21 An Undo button appears in the Pricing toolbar after the first write and pushes Holding left
- Severity: S4
- Screens: `/pricing`
- Where: 1440, light
- Repro: type a price and press Enter.
- Seen: "Undo U" appears between Holding and Load trends. Holding moves about 90 px left.
- Shot: INT-21, screenshot not kept.
- Direction: keep a place for Undo, or show it disabled from the start.
- Component: `Pricing.tsx`, the right part of the toolbar.
- Annotation: violates D118 (a press changes what is on the screen, never where the rest of it is).

### INT-22 The Capture card button has no press dip
- Severity: S4
- Screens: `/capture`
- Where: 1440, light and dark (`:active` forced)
- Seen: when pressed, Capture card only gets darker. Every other `bn-btn` dips 1 px and scales to .99, and so does the same primary xl button in the kit. The button that the owner presses most gives the weakest answer.
- Shot: INT-22, screenshot not kept.
- Direction: the Capture button answers a press like every other button.
- Component: `CaptureScreen.css`, the capture button's own `:active` or `transition` rule.
- Annotation: violates D50 (an interactive element's feedback is the product's). D50 lets a screen opt out with `translate: none` and a comment. `CaptureScreen.css` has neither, so the loss looks accidental.

### INT-23 The Box row on Capture has no hover, but the rows below it do
- Severity: S4
- Screens: `/capture`
- Where: 1440, light and dark
- Seen: Set hint, Rarity, Finish and the Rig rows get a tint on hover. The Box row (`capture-row-lg`) is the first control in the card, and it does not.
- Shot: INT-23, screenshot not kept.
- Direction: the same row gets the same hover.
- Component: `CaptureScreen.tsx` `Row`, the large variant.
- Annotation: violates D50 (an interactive element's feedback is the product's).

### INT-24 The listed `/` key does nothing on Fulfillment, and the Fulfiller cannot open `?`
- Severity: S3
- Screens: `/fulfillment`
- Where: 1440, light
- Repro: `#/fulfillment`. Click the page background and press `/`.
- Seen: focus stays on body, and typed text goes nowhere. The shortcuts table has a Fulfillment group: "/ Jump into the search field" and "Esc Close the enlarged photograph". The `?` sheet does not open on this screen, because it has no shell. So the group shows only on the owner's screens, under "Show every screen's shortcuts". On Sales the same `SearchField` answers `/`.
- Shot: INT-24, screenshot not kept.
- Direction: the key works for the Fulfiller, or it leaves the list.
- Component: `app/src/Fulfillment.tsx` search, and the `SHORTCUTS` fulfillment group in `App.tsx`.
- Annotation: caused by D5 (two personas), which gives the Fulfiller no shell and so no `?` sheet. The dead `/` key is not covered by any decision.

### INT-25 Product's search is a different pattern, and it ignores an empty press
- Severity: S4
- Screens: `/product`
- Where: 1440, light
- Repro: `#/product`. Press `Look up` with the field empty.
- Seen: nothing happens. No message shows, and focus does not move. The field is a plain `bn-input` with a separate `Look up` button. Unlike `SearchField` on Sales and Fulfillment, it has no `/` key, no × and no icon.
- Shot: INT-25, screenshot not kept.
- Direction: one search field on every screen. An empty press tells the owner what to type.
- Component: `app/src/ProductHistory.tsx`.
- Annotation: no decision covers this. D227 (a product price view) chose the route, not its search field.

### INT-26 On Graveyard, Try again and Reload give no visible answer
- Severity: S4
- Screens: `/graveyard`
- Where: 1440, light
- Repro: `#/graveyard`. Press Try again.
- Seen: the same error draws again with no state between, and focus goes to body. The owner cannot tell if the press happened.
- Shot: INT-26, screenshot not kept.
- Direction: a retry shows that it is trying.
- Component: `app/src/Graveyard.tsx`, the error `EmptyState`.
- Annotation: no decision covers this.

### INT-27 Capture fields do not agree on where focus goes when they open
- Severity: S4
- Screens: `/capture`
- Where: 1440 and 390, light
- Repro: `#/capture`. Press each row in the STACK and RIG cards.
- Seen: Box and Set hint put focus in their text field. Rarity, Finish, Game, Camera, Rotation and Trigger open with focus on body. Their options are then available only by number keys or the mouse.
- Shot: INT-27, screenshot not kept.
- Direction: an open field puts focus on its first choice.
- Component: `CaptureScreen.tsx` `OpenField` and `Opt`.
- Annotation: no decision covers this.

### INT-28 The phone menu leaves focus on the Menu button
- Severity: S4
- Screens: shell at 390
- Where: 390, light
- Repro: `#/` at 390x844. Press Menu.
- Seen: the drawer opens, but focus stays on Menu behind the scrim. Esc closes it and focus is on Menu, which is correct. A tap on the backdrop closes it and focus goes to body.
- Shot: INT-28, screenshot not kept.
- Direction: the drawer takes focus when it opens, as the `?` sheet does.
- Component: `App.tsx` `Drawer`.
- Annotation: no decision covers this.

### INT-29 On a phone, the Pricing price field is below the thumb floor
- Severity: S3
- Screens: `/pricing`, `/shipping`
- Where: 390, light
- Repro: `#/pricing` at 390x844.
- Seen: every price field is 27 px tall and Compare is 34 px. On 12 of 14 routes, no control is under 40 px. On Shipping, "What this file does not carry" is 18 px tall. Measured, not seen.
- Shot: INT-29, screenshot not kept.
- Direction: every control that a thumb presses meets the same floor.
- Component: `Pricing.tsx`, the row price field at the phone breakpoint. `Shipping.tsx`, the summary.
- Annotation: violates D117 (the thumb floor is the kit's, and the measurement is the hit area).

### INT-30 No screen, nav entry or palette command leads to Product history
- Severity: S2
- Screens: `/product`, shell palette, every screen that shows a SKU
- Where: 1440, light
- Repro: open the palette (⌘K) and type "product" or "sku". Then look for a link to `#/product` on every route, in the expanded Sales rows and in the Pricing history panel.
- Seen: the palette says "Nothing matches “product”." and gives nothing for "sku". No anchor on any route points at `#/product`. The Sales rows and the Pricing history panel show the SKU (for example "sku 9027180") but do not link to it. The route exists, but the owner reaches it only by typing the URL.
- Shot: INT-30, screenshot not kept.
- Direction: every place that names a product can open its history, and the palette finds it by name.
- Component: `App.tsx` palette `goTo` list (built from `ROUTES.filter((r) => r.nav)`). `Revenue.tsx` rows. `Pricing.tsx` history panel.
- Annotation: caused by D227 (a product price view). Its section "The link that was not built, and why" left out the link from Sales because another branch was editing `Revenue.tsx`. That premise is stale: the route shipped and no link followed. It also breaks the hard rule that a route is not a feature until a screen reaches it. The palette leaves it out because D95 (the shell is a rail, a palette and a reference sheet) builds "Go to" from `nav` routes only.

### INT-31 A failed Fulfillment search gives a remedy that cannot work
- Severity: S3
- Screens: `/fulfillment`
- Where: 1440, light
- Repro: `#/fulfillment`. Click the search field and type "zzzqqq".
- Seen: "The search did not finish. Type the name again." Typing again gives the same line. The screen hides why the search failed. It never says "no card by that name". So "type again" sends the Fulfiller around a loop.
- Shot: INT-31, screenshot not kept.
- Direction: a failed search says whether nothing matched or the search could not run, and offers a step that helps.
- Component: `app/src/Fulfillment.tsx` search result state.
- Annotation: no decision covers this.

### INT-32 "Waiting on the capture server" shows while the shell says "Server online"
- Severity: S3
- Screens: `/pricing?band=top` (Find by value)
- Where: 1440, light
- Repro: `#/pricing`, press Find by value.
- Seen: the notice says "The store could not be read. Waiting on the capture server." The sidebar in the same view says "Server online · 122 cards". The actual cause is a missing answer, not a missing server. The primary blue Try again button here does not match the secondary Try again buttons on Graveyard and in the price history panel.
- Shot: INT-32, screenshot not kept.
- Direction: an error names its real cause, and the same retry looks the same on every screen.
- Component: `app/src/ValueBands.tsx` failure `Notice`.
- Annotation: no decision covers this.

### INT-33 On a phone, opening one Sales row moves the columns of every row
- Severity: S3
- Screens: `/revenue`
- Where: 390, light
- Repro: `#/revenue` at 390x844. Press the disclosure on Premonition ("Show the orders behind Premonition").
- Seen: the Copies, Gross and Last sold columns move 21 px right in every row of the table (227 elements), not only below the opened row. At 1440 only the rows below move down, which is expected. Measured, not seen.
- Shot: INT-33, screenshot not kept.
- Direction: opening a row does not change the column widths of the rows around it.
- Component: `app/src/Revenue.tsx`, the product table and its disclosure row.
- Annotation: violates D118 (a press changes what is on the screen, never where the rest of it is).

## Held-screen notes

Main state. Check again after the merge.

- `#/orders`: stepping into Orders with ⌘→ from Pricing, or with any Home link to Orders, selects a buyer and writes `?buyer=…` into the URL. It also shows a status line: "Showing only the copies this order was offered — not every copy in the store". So arrival by the ring is never neutral.
- `#/orders`: the filter select and the search field show focus as a tint ring (box-shadow) with no outline. The Pricing and Product fields do the same, so this is consistent. Noted only.
- `#/inventory`: the search field has `outline: none` and puts the ring on the `SearchField` wrapper, the same as Sales. Consistent. Noted only.
- `#/review`: its Reload is disabled and spins. With Pricing, it is the only screen that does. INT-12 asks the others to do the same.
- The ⌘→ ring stops at Codes and does not wrap. ⌘← on Home does nothing.

## What I could not check

- **Real-server writes.** The undo after Shipping's Forget, the result of Fill pick locations, and each write that the demo refuses: identify, emit, live reconcile, live export, order fetch, capture and code scan. I graded only how the refusal draws.
- **Dark theme.** I measured states on 8 routes only (`states-dark.json`: `/`, `/capture`, `/runs`, `/pricing`, `/shipping`, `/revenue`, `/codes`, `/product`). The flags match light. All overlay, toast and refusal screenshots are light only. INT-01 is confirmed in dark by measurement.
- **820 px.** I ran presses at 1440 and 390 only. At 820 I measured the price field, which is correct there.
- **390 presses** ran on 7 routes and up to 20 controls per route (`press-390.json`). Other routes at 390 have only the target-size check.
- **Touch gestures.** Press-and-hold T for history, and swipe, were not exercised. Hover at 390 has no meaning, so I did not grade it.
- **`prefers-reduced-motion`.** Not checked in this lens.
- **The live camera.** The demo camera draws a black frame, so the motion trigger was not exercised.
- **Screen readers.** I read DOM focus and roles only, not announcements.
