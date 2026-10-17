# My Slabs

**STATUS: SPECIFIED. Nothing is built.** Governed by D-my-slabs-card-ladder (My Slabs reads
Card Ladder with the owner's own login). The decision carries the argument and the bounds. This
file carries every point the owner's token can read, what each returns, and the build plan.

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
`stsTokenManager.refreshToken` field of the record in IndexedDB `firebaseLocalStorageDb`. A
token that fails the exchange shows one sentence on screen and one action: copy it again.

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

### 3.8 Out of bounds

- `search.cardladder.com` answers a Cloudflare challenge (403), with or without the token. Banchi
  never calls it. 3.2 and 3.3 return the sales that its `salesarchive` index would.
- Callables that write, sync or scrape are out of bounds: `httpbuildcollectioncard`,
  `httpSyncCardStats`, `httpRefreshCert`, `httpInitialSalesScrape` and the admin ones.

## 4. What the screen shows

One row per slab: the card, the grade, the cert, and the two values with their sources. The
values are `clValue` from the grade ladder and `estimatedValue` from 3.4. The row also shows
the newest sales at the slab's grade, with date and platform, and the population at the grade.

The newest sale comes from the sales list in 3.2, sorted by date. It never comes from
`lastSalePrice` in 3.4, because that field can trail by a sale. The row shows the last five
sales at the grade, so that one outlier does not read as the price.

**Why the two values differ.** On one PSA 10 card, `clValue` equalled the newest sale at the
grade. `estimatedValue` and its `lastSalePrice` equalled the sale before it. The last six sales
spread across about half the newest price. So `clValue` is the fresher value, and it moves with
each single sale. `estimatedValue` trails it. The screen shows both, as D-my-slabs-card-ladder
(My Slabs reads Card Ladder with the owner's own login) requires.

A slab with no sale at its grade shows "no sales". It never shows Card Ladder's index-on-cost
number. The detail opens the sales list, the grade ladder and the sales speed per window. Each
sale links to its listing.

## 5. Pacing

Measured once: about 15 calls in about 30 seconds drew `Too many requests. Please wait a minute
and try again.` Calls spaced 3 seconds apart drew no refusal over 11 calls. The safe rate is
otherwise unmeasured.

A slab costs three calls: 3.1, 3.2 and 3.4. Slabs of one card share the 3.2 call. The sweep
spaces calls 3 seconds apart, so 100 slabs take about 15 minutes. A refusal stops the sweep for
the day and names the slabs still unread. The next day's sweep starts with them.

## 6. Daily snapshots

The store gets three tables (D88, SQLite and one transaction per write):

- `slabs`: cert, grader, `profileId`, identity, subgrades, and the date the owner added it.
- `slab_snapshots`: one row per slab per day. It holds both values and their confidence, the
  last sale, the population at grade, the gem rate and the sales speed per window.
- `slab_sales`: each sale seen, keyed by the sale `id`. A sale Card Ladder later drops stays
  here.

## Build plan

Kind: build. Platform: macOS, over the capture server.

1. `pipeline/cardladder.py`: the token exchange, the call allow list as one constant and the
   pacing. Add one function per read point in section 3.
2. The three store tables and their writes.
3. Routes for add, list, detail and sweep, with client functions in `app/src/server.ts`.
4. The `#/slabs` screen, built on `<Page>` (D275, every screen inherits the page scaffold).
5. A launchd job for the daily sweep, like `make price-refresh-agent`.
6. The three checks that D-my-slabs-card-ladder names.

## 7. What stays unmeasured

- The safe call rate (section 5).
- Whether Card Ladder enforces an app check on these callables later. Today none is sent, and
  each call answers 200.
- How long a refresh token lives before Card Ladder signs the owner out.
- Why `estimatedValue` trails the newest sale, and by how long. One PSA 10 card showed it in
  its sales list. A Riftbound card's two last-sale fields also differ, but its sales list is
  unchecked. The cause is unmeasured.
