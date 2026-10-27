# My Slabs

**STATUS: PARTLY BUILT.** Governed by D320 (My Slabs reads
Card Ladder with the owner's own login). The decision carries the argument and the bounds. This
file carries every point the owner's token can read, what each returns, and the build plan.
Built: add, list, detail and remove (`POST /slabs`, `GET /slabs`, `GET /slabs/<grader>/<cert>`,
`DELETE /slabs/<grader>/<cert>`), the Card Ladder client, the three store tables, the `#/slabs`
screen and the three checks that D320 names. Not built: the daily sweep (its route and its
launchd job) and the 4.2 buyer export. Both wait for the owner's word.

---

## 1. What it does

The owner gives Banchi a slab's cert number and grader: one at a time, or a file. Banchi reads
that slab from Card Ladder with the owner's login. It shows the slab's value, its last sale, its
sales list, its population and its grade ladder. Once a day it reads every slab again and keeps a
snapshot, so the screen can show how each value moves.

Input files are the grader's own exports. A CGC invoice CSV keeps the cert in an unnamed sixth
column. A Beckett grading order is a PDF with a `Graded Serial No.` column. A plain CSV with
`Cert #` and `Grader` columns also works.

## 2. The login

`CARDLADDER_REFRESH_TOKEN` in the gitignored `.env` holds the owner's Firebase refresh token. The
server posts it to `securetoken.googleapis.com/v1/token` with Card Ladder's public web API key.
The answer holds a one-hour `id_token` and the owner's `user_id`. Each call sends
`Authorization: Bearer <id_token>`. The server refreshes the ID token before it expires.

The owner copies the token by hand, in the DevTools Console on `app.cardladder.com`. It is the
`stsTokenManager.refreshToken` field of the record in IndexedDB `firebaseLocalStorageDb`. The
owner pastes it into `.env` as `CARDLADDER_REFRESH_TOKEN=<token>` and restarts nothing: the
next add reads it. A missing or failed token shows one plain sentence on screen, such as "Card
Ladder needs you to sign in again.", and never the key's name (D196, no user-visible string
names a decision). These steps are where the owner finds the key.

## 3. Every point the token can read

Each row below was called once from this Mac with the owner's token, and answered 200. The
callables live at `https://us-central1-cardladder-71d53.cloudfunctions.net/<name>`. Each takes a
POST body `{"data": {...}}` and answers `{"result": {...}}`.

### 3.1 `httpcertlookup` — the slab itself

Input: `{cert, grader, includeProfile: true}`. The grader is `psa`, `beckett`, `sgc` or `cgc`.
Card Ladder maps `bgs` and `bvg` to `beckett`.

Returns:

- Identity: `cert`, `grader`, `subGrader`, `graderId`, `profileId`, `label`.
- Grade: `grade` (a code such as `g10p`, `g9_5`, `g10b`), `qualifierType`, `autographGrade`.
- Subgrades for Beckett: `subGrades.{centering, corners, edges, surface}`.
- `dateGraded`, `lastUpdated`, `source`.
- `population`: the count at this slab's grade.
- `profile`: `category`, `year`, `set`, `subject`, `number`, `variation`, `graderList`,
  `totalPopulation`, `totalGems`, `gemRate`, and the pop report.
- The pop report is `profile.graders.<grader>.grades`: a count at every grade, half grades and
  `auth` included. `qualifierGrades` holds the qualified counts.

### 3.2 `httpprofile` — the whole card, every grade

Input: `{profileId}`. One call per physical card.

Returns:

- `sales`: the card's whole sales history, across graders and grades. One PSA card returned
  1,792 sales. Each has `id`, `itemId`, `title`, `seller`,
  `image`, `thumbnail`, `platform`, `listingType`, `price`, `date`, `url`, `grader`, `grade`,
  `memberVerified`, `cardId`.
- `graders[].grades[]`, the grade ladder. Each row has `grade`, `label`, `clValue`,
  `clValueConfidence`, `price`, `lastSold`, `power` and `value`.
- `totalPopulation`, `totalGems`, `gemRate`, and per grader the same three.
- `index`: the market index Card Ladder assigns, such as One Piece.

A profile is per grader: `cgc-…`, `psa-…`. `hasMatches` was false on every slab sampled, so a
CGC slab's profile holds no PSA 10 value.
- `image` and `comboImages`, one image per grader and grade.

### 3.3 `httpprofilesales` — sales at this slab's grade

Input: `{cert, grader, grade}`. Returns `totalHits` and up to 20 `sales`. Each sale adds to the
3.2 fields: the sold slab's own `cert` and `slabSerial`, the seller's `feedback`, `ebayGraded`,
`ebayGrader`, `gemRateId`, `cardDescription` and `condition`.

### 3.4 `httpcardestimate` — Card Ladder's value and sales speed

Input: `{profileId, grader, grade, description, qualifierType, autographGrade}`.

Returns `estimatedValue`, `confidence`, `lastSalePrice`, `lastSaleDate`, `index`, `indexId`,
`indexPercentChange`, and sales speed per window. Each of `twoWeekData`, `oneMonthData`,
`oneQuarterData`, `sixMonthData` and `oneYearData` holds a `velocity` and an `averagePrice`.

### 3.5 `httpsaleprofile` — one sale in detail

Input: `{saleId}`, a sale `id` from 3.2. Returns `sale`, `card`, `index`, `profile`,
`population` and `guideValue`. `guideValue` holds `value`, `confidence`, `indexPercentChange`
and `source`.

### 3.6 `httpIndexFromDescription` — the card's market index

Input: `{description}`. Returns the index `label`, `indexId`, and `dailySalesTotal`: total sales
money per day for that index. This is market context, not a slab's price.

### 3.7 Firestore, over REST

Base: `https://firestore.googleapis.com/v1/projects/cardladder-71d53/databases/(default)/documents`.

- `profiles/{profileId}`: the card's profile document.
- `users/{uid}`: the owner's account settings.
- `users/{uid}/collections`: the owner's Card Ladder collections.
- `users/{uid}/collections/{id}/collection_cards`: each slab the owner added in Card Ladder,
  with `cert`, `grader`, `grade`, `currentValue`, `estimatedCurrentValue`, `stats`, `pop`,
  `investment`, `priceMovement` and more.
- `cards`: a query on `profileId` answered 200 with no document for an archive-only card.
  Reads of `cards/{id}` and `cards/{id}/sales` for a card with a card page are unproven.

### 3.8 Never called

- Banchi never calls `search.cardladder.com`. 3.2 and 3.3 return the sales that its
  `salesarchive` index would.
- Banchi never calls callables that write, sync or scrape: `httpbuildcollectioncard`,
  `httpSyncCardStats`, `httpRefreshCert`, `httpInitialSalesScrape` and the admin ones.

## 4. What the screen shows

### 4.1 The landing: one ledger

`#/slabs` lands on one table of every slab, the owner's pick of the five mockups (01 Ledger).
The columns, in the owner's order:

Pop, Graded, Rate, Top %, Best %, Grade, Set, Card, Var, Ask, Card Ladder, Conf, Last Sale,
PSA 10, Raw NM, Slab vs Raw, ×, Do.

- The default sort is ×, highest first. × is the slab's value divided by its raw NM price.
  A row with no × sorts after every row with one. Ties, and rows with no ×, fall back to the
  Card Ladder value, highest first, and a slab with no sales at its grade comes last.
- All 18 headers show, in the owner's order, while a route cannot fill some of them. Such a
  cell holds a typed dash (D218, a typed dot is a defect). Each column keeps its width
  whether it is empty or full (D313, nothing on screen moves unless the person moved it).
- The table scrolls sideways inside its own frame when it is wider than the page, at 820
  for example. The page itself never scrolls sideways.
- The cert is hidden on screen. The buyer export keeps it.
- Names are short. A name carries no year. Set shows as a code (SFD, ME01, SV09, SWSH07, CRZ,
  MEP, OP14), with a JP or CN suffix. "Stamp" shows as "Stamped". A variation that names the
  product a card came from (box, collection, ETB, tin) shows as "P". Rarities are abbreviated.
- Last Sale is the newest sale at the slab's grade, from the sales list in 3.2, sorted by date.
  It never comes from `lastSalePrice` in 3.4, because that field can trail by a sale.
- A press on a row's card opens its detail in a side sheet from the right, the owner's pick
  over a row that opens in place. The ledger behind it never moves. The sheet's sections, in
  order: Worth, Sales at the grade (the last five, each with its platform when it has one,
  linked to its listing), Sales speed per window, Population at the grade, the grade ladder
  with this grade marked, and Snapshots. Remove sits in the sheet's footer, never on a row.

### 4.2 The buyer export: through a check step

The export goes through a check step (05 Offer's). The owner sees what the file will hold before
it is written. The file holds the on-screen columns plus the cert.

### 4.3 The value, and when it is trusted

The slab's value is Card Ladder's estimate: `estimatedValue` from 3.4, with its `confidence`.
The screen also shows `clValue` from the grade ladder, each with its source, so the owner sees
when the two differ.

**Why the two values differ.** On one PSA 10 card, `clValue` equalled the newest sale at the
grade. `estimatedValue` and its `lastSalePrice` equalled the sale before it. The last six sales
spread across about half the newest price. So `clValue` moves with each single sale, and
`estimatedValue` trails it.

The value is not trusted when any of these holds:

- Confidence is 2 or less. Confidence runs 1 to 5. The owner ruled this cutoff.
- The value is more than 2 times the highest of the last five sales at the grade.
  The owner ruled this ratio. Evidence below.
- The value is exactly $100 with $0 profit. That is the collection placeholder, not a price.

An untrusted value is replaced by the median of the last five sales at the grade. A slab with no
sale at its grade shows "no sales" and no value.

**The recent-sales check, its evidence.** Measured once, over the prototype's data: 414 slabs
with confidence 3 or more and at least one sale at the grade. This used the ladder's `clValue`,
not `estimatedValue`; the ratio needs a second look once 3.4 is read for every slab.

| Value above | the median of the last 5 | the highest of the last 5 |
|---|---|---|
| 1.25 × | 105 slabs | 50 |
| 1.5 × | 72 | 30 |
| 2 × | 30 | 9 |
| 3 × | 8 | 2 |

The highest sale is the safer base. A value that tracks a rising newest sale stays trusted:
Hop's Zacian ex at $44 against sales of $41, $10.05 and $7.20 is 4.4 times the median but 1.07
times the highest. Ogerpon ex (Hearthflame Mask) at $238 against $116.40 and $26.40 is 2.04 times
the highest, so 2 × catches it, narrowly. 2 × also catches Dragonair at $262 against sales of $45
to $79. 1.5 × would catch 30 slabs. Raikou V, at 1.5, sits on that line.

### 4.4 The sell rule

Ask is the larger of the trusted value and raw NM. Each slab lands in one bucket:

- Sell as slab: the trusted value is at or above raw NM.
- Price at raw: the trusted value is below raw NM.
- Can't compare: one of the two is missing.

### 4.5 Population

Each count is per grader, from 3.1's pop report.

- Graded: every slab of that card at that grader, minus Authentic and Altered.
- Rate: the share at this slab's grade.
- Top %: the share at or above this slab's grade.
- Best %: the share at the highest grade reached. For Beckett that is Black Label, when one exists.

### 4.6 The other prices and their sources

- Raw NM: tcgcsv, through `pipeline/pricehistory.Market`. A second-look match takes the same
  number and name, with the variant words exactly equal.
- JP and CN raw prices: a one-time PriceCharting web check.
- PSA 10: PriceCharting, accepted only when the page's TCGplayer id equals ours. Card Ladder has
  no cross-grader PSA 10 (3.2).
- Population and confidence: Card Ladder, 3.1 and 3.2.

### 4.7 Control sizes come from the kit

Every control a thumb presses is 40px or more. The kit meets that on touch: the
`(max-width: 767px), (hover: none) and (pointer: coarse)` block in `app/src/tokens.css` raises
`--bn-control-h-sm`, `--bn-control-h` and `--bn-control-h-lg` to 40, 42 and 46px. With a mouse
they stay 28 and 34px, as on every other screen. `#/slabs` uses the kit's sizes and overrides
none of them.

### 4.8 The screen's rules

These hold until a later route changes them.

- The screen computes no trust verdict, because the browser holds no pipeline logic. It shows
  Card Ladder's estimate and the ladder value, each with its source.
- Remove acts at once. Its receipt carries Undo, which adds the slab again and restores its
  first date. An Undo that Card Ladder refuses, a rate limit included, shows "The slab was not
  put back." It never fails without a word.
- Two short sentences carry their reason in hover text: "The slab was not put back." for a
  refused Undo, and "No estimate without a sale." in Worth for a slab with no sales. The reason
  also shows on keyboard focus and on a tap, not only under a mouse. It names no mechanism (D196,
  no user-visible string may name a decision).
  - Undo's reason says why the add-back failed, for example that Card Ladder could not be read
    just now or hit today's limit, so the owner should try later. Each reason is true for its
    refusal code. A refusal with no true reason shows no reason.
  - The no-sale reason says the slab has never sold at its grade, so Card Ladder gives no
    estimate.
- A rate limit is a refusal, never a retry: its sentence says to try again tomorrow and offers
  no Retry.
- The grader list on screen copies `store/slabs.GRADERS`, because no route sends it yet. A
  check fails when the two differ.
- A slab with no label never shows its cert. The screen writes its own receipt sentence then.
- A login refusal says what to do in plain words, such as "Card Ladder needs you to sign in
  again." It never names the settings key (section 2 does).
- The detail's Sales speed section heads its count column "Sales", not "Velocity". The numbers
  line up under their headings.
- Sales speed shows the windows Card Ladder returns: two weeks, one month, three months, six
  months and one year (`_WINDOWS` in `server/slabs_routes.py`). Card Ladder has no 7-day window,
  and the screen never invents one.
- Each sale row in Sales at the grade shows the sale's platform (eBay, Goldin and others) when
  the sale carries one. The route sends it as `platform`, a field of each sale in 3.2. A sale
  with no platform shows none.
- The screen's nav key is `l`.

### 4.9 The screen's parts and states

- **Ledger cells.** Money shows in the kit's money face (D221, money stays mono). Numbers sit
  right. Conf shows a word: 1 Very low, 2 Low, 3 Fair, 4 Good, 5 High, and 2 or less is drawn
  as a warning. A slab with no sale at its grade shows "No sales" in its Card Ladder cell and
  leaves Conf and Last Sale empty. The Card cell is the button that opens the detail.
- **Header.** The title is "Slabs". The line under it counts the slabs and those that never
  sold at their grade. The actions are Reload and "Add a Slab".
- **Detail sheet.** Its title is the row's label. Under it: the grader and grade, and the day
  the slab joined the list. Worth shows the estimate and the ladder value, each with its
  confidence and source. A sale with no link shows no link. While the detail loads, every
  section holds its loaded shape, and the two sections of unknown length come last, so arrival
  only grows downward (D313, nothing on screen moves unless the person moved it). Esc closes
  the sheet, and focus goes back to the row's Card button.
- **Add sheet.** A cert field and a grader list. Add stays off while the cert is empty. While
  the read runs, Add is busy and a line says the read takes a while. A success closes the sheet
  and shows the receipt sentence the route sent. A refusal shows its sentence in the sheet, or
  as a toast when the sheet has closed. A double press sends one request.
- **Remove.** It sits in the detail sheet's footer. It is off while this tab has an add in
  flight. A double press sends one request.
- **Empty.** "No slabs yet", one sentence, and the add button. The header's add button hides
  while the list is empty.
- **Loading and failure.** The list loads as skeleton rows under a header that keeps its shape.
  A failed list read shows its sentence with Retry, except a rate limit (4.8).

## 5. Pacing

Measured once: about 15 calls in about 30 seconds drew `Too many requests. Please wait a minute
and try again.` Calls spaced 3 seconds apart drew a refusal after about 8 calls. Calls spaced 8
seconds apart held for about 600 calls. A faster safe rate is unmeasured.

A slab costs three calls: 3.1, 3.2 and 3.4. Slabs of one card share the 3.2 call. The sweep
spaces calls 8 seconds apart, so 100 slabs take at most 40 minutes. A refusal stops the sweep for
the day and names the slabs still unread. The next day's sweep starts with them.

## 6. Daily snapshots

The store gets three tables (D88, SQLite and one transaction per write):

- `slabs`: cert, grader, `profileId`, identity, subgrades, and the date the owner added it.
- `slab_snapshots`: one row per slab per day. It holds both values and their confidence, the
  last sale, the population at grade, the gem rate, the sales speed per window and the grade
  ladder from that read. The detail shows the newest snapshot's ladder.
- `slab_sales`: each sale seen, keyed by the sale `id`. A sale Card Ladder later drops stays
  here.

`store/slabs.py` holds them. The rules the build chose:

- A slab added again keeps its first added date, profile, identity and subgrades.
- A second snapshot on one day replaces that day's row.
- A sale that two slabs read is one row, linked to both.
- Money is stored as text. Step 3 converts Card Ladder's numbers at the route.
- Sale dates are text and sort as ISO strings. A sale with any other date is refused before
  the write. Card Ladder's date format is unmeasured.
- A slab's sales are read through an indexed link table, one row per slab and sale.
- The slab row keeps a copy of its newest snapshot, so the list reads `slabs` once and never
  the snapshots, which grow by one row per slab per day. One store method writes a snapshot,
  and it updates that copy in the same write. Every snapshot writer, the sweep included, calls
  that method. An older snapshot never replaces a newer copy. A source check refuses any other
  writer in Python. It cannot see raw SQL, so a migration that inserts snapshots also updates
  the copy.
- A slab with no sale at its grade stores no value, never a number.

## Build plan

Kind: build. Platform: macOS, over the capture server.

1. `pipeline/cardladder.py`: the token exchange, the call allow list as one constant and the
   pacing. Add one function per read point in section 3.
   Every call sends through D319's home, `net.open`, with idempotent=False and no redirect
   followed. `net.open` hands back every HTTP status, so the client reads a 429 and a rejected
   token itself. A Google 400 reads "copy it again" (section 2). A Google 429 is not worded as
   Card Ladder's.
2. The three store tables and their writes.
3. Routes for add, list, detail and sweep, with client functions in `app/src/server.ts`.
   Add, list and detail are built: `POST /slabs`, `GET /slabs`, `GET /slabs/<grader>/<cert>`,
   with one Card Ladder client per server process. The sweep route waits for the owner's word.
   The owner ruled a way back: `DELETE /slabs/<grader>/<cert>` and its client function remove
   the slab and its sale links. Its snapshots and its sales stay, so adding it again undoes the
   remove and its history returns. The owner ruled that the undo restores the first added date,
   and the receipt says "restored". The date comes from the oldest snapshot. Add is the only
   writer of a slab, and it writes the first snapshot in the same write, so that snapshot
   exists. A sale that the new read no longer lists stays in the store, unlinked.
   A failed read writes no snapshot: a same-day snapshot replaces every field, so a failed call
   stored as empty would erase a good value. The store replaces a re-read sale whole, so the
   route merges the new read into the stored sale first, and fields only 3.3 returns are kept.
   Card Ladder's numbers become text money at the route. The store refuses a sale date that is
   not text, so the route turns any other date form into an ISO date first.
4. The `#/slabs` screen, built on `<Page>` (D275, every screen inherits the page scaffold),
   from section 4, with the kit's control sizes (4.7). It builds the 4.1 ledger and its
   detail, and add and remove controls, on the routes of step 3 only. The 4.2 buyer export
   and the sweep wait for the owner's word. The client's login errors name a Google
   host; the screen shows them as a sentence with no host name (D196, no user-visible string
   names a decision).
   The busy refusal says a slab is being added, even when a second remove caused it. So the
   remove control waits for its answer, and a double press never sends a second remove.
5. A launchd job for the daily sweep, like `make price-refresh-agent`. A Google error on the
   token exchange stops the sweep too, because the exchange host has no pace of its own.
6. The three checks that D320 names. All three are built:
   - The callable allow list is `cardladder.ALLOWED_CALLABLES`, which `Client.call` reads.
   - `scripts/cardladder-selftest.py`'s `case_refuse_host` proves a request to
     `search.cardladder.com` is refused before the transport.
   - `app/tests/slabs.spec.ts` proves a slab with no sale shows "No sales".

## 7. What stays unmeasured

- The safe call rate (section 5).
- The recent-sales ratio over `estimatedValue` (4.3). It was measured over `clValue` only.
- Whether `net`'s default attempt timeout holds for `httpprofile` (3.2), which can return about
  1,800 sales.
- How long a refresh token lives before Card Ladder signs the owner out.
- Whether a rotated public API key can be told from a bad token. Both answer a Google 4xx, and
  the client reads no body, so both read "copy it again".
- Why `estimatedValue` trails the newest sale, and by how long. One PSA 10 card showed it in
  its sales list. A Riftbound card's two last-sale fields also differ, but its sales list is
  unchecked. The cause is unmeasured.
- The unit of `velocity` in the sales speed (3.4). The screen shows the number under the
  label "Sales" with no unit.
