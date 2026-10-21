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

### 3.8 Out of bounds

- `search.cardladder.com` answers a Cloudflare challenge (403), with or without the token. Banchi
  never calls it. 3.2 and 3.3 return the sales that its `salesarchive` index would.
- Callables that write, sync or scrape are out of bounds: `httpbuildcollectioncard`,
  `httpSyncCardStats`, `httpRefreshCert`, `httpInitialSalesScrape` and the admin ones.

## 4. What the screen shows

### 4.1 The landing: one ledger

`#/slabs` lands on one table of every slab, the owner's pick of the five mockups (01 Ledger).
The columns, in the owner's order:

Pop, Graded, Rate, Top %, Best %, Grade, Set, Card, Var, Ask, Card Ladder, Conf, Last sale,
PSA 10, Raw NM, Slab vs raw, ×, Do.

- The default sort is ×, highest first. × is the slab's value divided by its raw NM price.
- The cert is hidden on screen. The buyer export keeps it.
- Names are short. A name carries no year. Set shows as a code (SFD, ME01, SV09, SWSH07, CRZ,
  MEP, OP14), with a JP or CN suffix. "Stamp" shows as "Stamped". A variation that names the
  product a card came from (box, collection, ETB, tin) shows as "P". Rarities are abbreviated.
- Last sale is the newest sale at the slab's grade, from the sales list in 3.2, sorted by date.
  It never comes from `lastSalePrice` in 3.4, because that field can trail by a sale.
- The detail opens the last five sales at the grade, the grade ladder and the sales speed per
  window. Each sale links to its listing.

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

### 4.7 Depends on the kit

Every control a thumb presses is 40px or more. The kit's controls are 34px or 28px today. The
fix goes into the kit, for every screen, as its own lane. `#/slabs` does not override it.

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
  last sale, the population at grade, the gem rate and the sales speed per window.
- `slab_sales`: each sale seen, keyed by the sale `id`. A sale Card Ladder later drops stays
  here.

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
4. The `#/slabs` screen, built on `<Page>` (D275, every screen inherits the page scaffold),
   from section 4. It waits on the kit lane in 4.7. The client's login errors name a Google host;
   the screen shows them as a sentence with no host name (D196, no user-visible string names a decision).
5. A launchd job for the daily sweep, like `make price-refresh-agent`. A Google error on the
   token exchange stops the sweep too, because the exchange host has no pace of its own.
6. The three checks that D-my-slabs-card-ladder names.

## 7. What stays unmeasured

- The safe call rate (section 5).
- The recent-sales ratio over `estimatedValue` (4.3). It was measured over `clValue` only.
- Whether `net`'s default attempt timeout holds for `httpprofile` (3.2), which can return about
  1,800 sales.
- Whether Card Ladder enforces an app check on these callables later. Today none is sent, and
  each call answers 200.
- How long a refresh token lives before Card Ladder signs the owner out.
- Whether a rotated public API key can be told from a bad token. Both answer a Google 4xx, and
  the client reads no body, so both read "copy it again".
- Why `estimatedValue` trails the newest sale, and by how long. One PSA 10 card showed it in
  its sales list. A Riftbound card's two last-sale fields also differ, but its sales list is
  unchecked. The cause is unmeasured.
