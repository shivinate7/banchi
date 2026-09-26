# The public demo, and why it is not a fork

**COVERAGE WIDENED 2026-09-24**: photographs, undo, facet counts, the order walk, a typed
search, the graveyard, the price histories and the value bands (§3, §5, §8, §8a).

**STATUS, 2026-09-13: BUILT and LIVE.** `make demo` / `demo-seed` / `demo-record` /
`demo-static` / `demo-preview` / `demo-freshness` are all real, all re-runnable, and the
published page (`shivinate7.github.io/banchi`) is rebuilt by `.github/workflows/demo.yml` on
every push to `main` that touches what it is built from. This file is that argument's home —
it existed only as prose inside `CLAUDE.md`'s command reference until this entry, verified
against the code rather than carried forward from memory. **Re-verified against the tree
on 2026-09-19** before landing: every mechanism below still holds, and three figures that
had drifted since the first draft — `request()`'s line, the `app/src` line count and
`capture_server.py`'s size — were re-measured rather than carried.

Governed by D42 (a workflow may publish but never move `main`), D18 (a generator may write;
nothing that writes may gate a commit — every `demo-*` target is off the commit path for this
reason), D70 (a live code card is a bearer instrument, which is why `demo-assets/`'s
photographs must be QR-cleared before they can be tracked at all), and D102/D94 (the mark and
the brand the published page carries are the same generated ones the real app draws).

---

## 1. Why not a fork

The product this repo builds is one Vite/React front end talking to one Python capture
server over one HTTP boundary. `app/src/server.ts`'s `request()` (line ~624) is the **only**
place a client call is made — every one of the client's exported functions funnels through
it — and `app/src/server.ts:photoUrl()` (line ~334) is the **only** place a photograph is
addressed. Both were read and confirmed current as of this entry.

That means a demo differs from the real product in exactly two functions: what `request()`
resolves to, and what a photograph URL points at. Forking the app to build a public copy
would duplicate the other 55,000-odd lines under `app/src` (`wc -l` over `app/src/**/*.{ts,tsx}`,
re-measured 2026-09-19: 55,428) to carry none of the actual difference, and would diverge from the real
app on the next commit that touched either copy and not the other — this repo's history moves
fast enough that a maintained fork was never a serious option.

**UNVERIFIED, carried from the original design conversation rather than re-derived here:**
earlier drafts of this argument cited "38,705 lines" and "134 commits landed in the three
days before this was built" as the measurements that closed the fork question. Neither figure
was reproduced for this entry — the line count above is a fresh, larger measurement of a
later tree, and the commit-velocity claim was not re-run at all. Treat both
historical figures as illustrative rather than load-bearing.

## 2. What differs, and the three-way split

`scripts/demo-seed.py`'s own module docstring states the split in these terms, and it still
governs the architecture even though one clause of it (§6) is now stale:

- **REAL** — the catalogue. Every curated card is drawn from a real TCGplayer export under
  `fixtures/`: real SKUs, real names, real numbers, real market prices. The pipeline join
  that resolves a card against those exports, and the pricing arithmetic downstream of it,
  run for real — nothing about the numbers a viewer sees on `#/pricing` is invented.
- **INVENTED** — which of those cards sits in which box at which index, what has sold, what
  is held back, and who it shipped to. None of it describes a physical object; it exists to
  make the store look worked rather than freshly built.
- **SYNTHETIC**, as originally designed — the photographs, to be drawn by a `card_image()`
  function so that neither somebody else's card art nor a picture of the owner's desk would
  reach a published page.

## 3. The photographs are no longer synthetic, and the docstring is stale about it

**Verified against the code, and the correction this entry exists partly to record:**
`scripts/demo-seed.py` has no `card_image()` function today — it was searched for and is not
present. The `Row` class that replaced it (see the file's own comment: *"The demo drew its own
cards until 2026-09-06 and could caption them anything; real photography cannot"*) reads a
curated manifest of **real photographs** instead: `demo-assets/cards.json` holds 132 entries
(measured 2026-09-13, matching the Makefile's `DEMO_PHOTO_COUNT ?= 132`), each pairing one of
the owner's own real card photographs with the identification it actually received.

This is `demo-assets/` — the **one** tracked-image exception in this repo, and it is safe to
track only because of what curates it. `make demo-photos SOURCE=<checkout>` (`scripts/demo-photos.py`)
reads a real store's photographs and **refuses any photograph a QR decodes out of, at full
resolution, before the downscale** — because a live code card's whole identity is that QR
(D70), and a bearer instrument published to strangers is a defect this repo will not ship.
`demo-seed.py` then refuses to run at all without that curated manifest present.

**The second check reads the published bytes (2026-09-24).** `scripts/demo-record.py:copy_photos`
copies each card's photograph from the card record's own `photo` field. Before this date it
walked `captures/cards/box*/`. The seed stopped writing that folder when the photographs moved
under the card's own name (D172, D183), so every build published 0 photographs. Now the
recorder decodes each photograph it copies with `codes/qr.py`. If a QR decodes on one, it
refuses the whole copy and writes nothing. It never prints the payload. A store of cards that
copies 0 photographs is also a refusal. `python3 scripts/demo-record.py --self-test` proves the
QR refusal on a throwaway store with a synthetic symbol. A copy of the recorder with the refusal
removed fails 2 of its 3 cases. The seed's docstring no longer says SYNTHETIC. It was corrected
on the same date.

So the SYNTHETIC row above is superseded by fact: the photographs a viewer sees are real,
curated, and QR-cleared, not drawn. The REAL / INVENTED split still holds exactly as designed;
what moved from SYNTHETIC to a fourth, curated-real category is the photography alone, and
`make docs-audit` has no row watching this drift because nothing before this entry recorded
the original claim anywhere but a stale docstring comment.

## 4. The seed is deterministic, and refuses a real store

`scripts/demo-seed.py` seeds one RNG from a fixed constant (`SEED = 20260906`) and stamps
every record as an offset from one fixed clock (`NOW = 2026-09-06T14:30:00Z`), so an unchanged
tree rebuilds the store byte-identically and a rebuild is not a diff nobody can read.

**It refuses to touch a store that already holds cards unless `--force` says so** — verified
in the file's own docstring and invoked exactly that way by `make demo-seed`
(`PKMNSCAN_HOME=$(DEMO_HOME) $(PYTHON) scripts/demo-seed.py --force`, `DEMO_HOME ?= demo`).
`PKMNSCAN_HOME` unset means the checkout's own store, which is somebody's real one (D43); the
seed's refusal is that same rule applied to a script that would otherwise overwrite it.

Identification is the one step of the real pipeline that costs money, so it is the only step
the seed fakes: it writes `identifications.json` in exactly the shape a real `pkmnscan
identify` run leaves behind — a shape `cli/resolve.py` documents as an explicitly supported
input ("a hand-made or recovered identifications file"). Everything after that runs for real:
`make demo-seed`'s recipe itself runs `./pkmnscan join` twice against
`fixtures/riftbound_export_untouched.csv`, so the catalogue lookup, the variant ladder, the
cap arithmetic and `pricing.json` are the pipeline's own output over real fixture data, never
a fixture pretending to be one.

## 5. The bundle, and why it never touches the owner's server

`make demo-record` (`scripts/demo-record.py`) spawns its **own** capture server over the demo
store, on its own port, sweeps every GET the client can build against the parameter space the
seeded store actually holds, records every 200 response into `app/demo/bundle.json` plus the
photographs Vite will bundle, and stops that server again. It never starts, restarts, or binds
`make up`'s port — which in the main checkout is the owner's live process over their real
inventory (D43, D53). A 404 recorded here means the path is not a read this demo replays, not
that a read failed.

**What the sweep records, since 2026-09-24.** The first sweep left whole screens refusing, so a
reviewer could not tell a demo gap from a product defect. `sweep_coverage` adds these reads:

- `/graveyard`, `/inventory/recent` at Home's own depth, and `/pipeline/submissions`.
- Every `/boxes` facet filter the three menus can make (D213), each facet unset or one value.
- Each value band (`top`, `bottom`, `gaps`) whole, once per box. The browser cuts the page.
- `/pipeline/holdings-value` for each range, and `/pipeline/price-now` for each SKU.
- `/pipeline/products/<sku>/history` for each SKU, when the server can answer it.
- Three POST routes that only read: `/inventory/copies` per SKU, `/orders/picks` per order,
  and `/orders/walk-plan` for every set of orders a person can tick. Seven orders give 127
  sets. The recorder refuses more than seven.

Measured 2026-09-24, with the recorded price histories: 786 recorded routes, 9.0 MB of JSON on
disk. The walk plans are 1.5 MB of it. The built `demoServer` chunk is 5.3 MB, and 364 KB after
gzip compression. A POST read is keyed
`POST <path> <body>`, with the body's keys sorted (`demo-record.py:post_key`).

**Every box has a name.** The owner ruled that a box number is never shown. So the seed refuses
a box with no name, and two boxes with one name (D20).

`app/src/demoServer.ts` is what a published build plays the recording back through. Its own
header, read in full for this entry, states the mechanism precisely: `server.ts`'s single
`request()` reaches it through a dynamic `import()` gated on `if (DEMO)`, and every screen, the
kit, the shell, the router and the keyboard map are **the same code** the owner runs at the
desk — only the wire is frozen.

## 6. `VITE_DEMO` is a build-time constant, not a runtime flag

**Verified in `app/vite.config.ts` line 88**: `__BN_DEMO__: JSON.stringify(process.env.VITE_DEMO
=== '1')`. This is a compile-time literal substitution, not an environment read at run time. An
ordinary build (`VITE_DEMO` unset) folds `__BN_DEMO__` to the literal `false`; Rollup then dead-
code-eliminates the `if (DEMO)` branch in `server.ts` entirely, so neither `demoServer.ts` nor
the recorded bundle it imports (`#demo-bundle`) is ever emitted into a real build's chunks. A
runtime flag — reading an environment variable or a query parameter at load time — was
deliberately rejected: a UI that could answer from the wrong store at runtime is exactly D43's
subject, generalized from "which checkout's store" to "which store, real or recorded, this
bundle can possibly reach." A build-time constant makes the two cases structurally different
artifacts rather than one artifact with a mode switch.

`make demo-static` is the recipe that sets it: `cd app && VITE_DEMO=1 DEMO_BASE=$(DEMO_BASE)
npx vite build --outDir ../dist-demo --emptyOutDir` (Makefile, verified).

## 7. `DEMO_BASE` — where the bundle believes it is served from

GitHub Pages serves a project site at `/<repo>/`, never at `/`. A Vite build with no `base`
override assumes `/`, and every asset reference 404s the moment such a build is placed under a
subpath — a failure invisible on `localhost` and only visible once published.
`.github/workflows/demo.yml`'s build step derives this from the repository name itself —
`make demo-static DEMO_BASE="/${GITHUB_REPOSITORY#*/}/"` — so a repository rename cannot leave
a stale path baked into the artifact; the Makefile's own `DEMO_BASE ?= /$(DEMO_REPO)/` default
is a fallback for a hand-run build and is allowed to be stale by design, exactly as the
Makefile's own comment already states for a related target. `make demo-preview` serves
`dist-demo/` through `vite preview` with the same `--base`, so a link that resolves in preview
resolves published.

## 8. What a published page genuinely cannot do, refused by name

`app/src/demoServer.ts`'s `CANNOT` table (verified in full) refuses seven paths, each with the
reason on it, rather than failing silently or looking broken:

| Path prefix | Refusal code | Reason |
|---|---|---|
| `/pipeline/identify` | `demo_costs_money` | identification is a paid Batch API call against Claude |
| `/pipeline/emit` | `demo_no_export` | needs a live TCGplayer export this demo has no copy of |
| `/pipeline/reconcile-live` | `demo_no_export` | needs a My Pricing export from a signed-in account |
| `/pipeline/live-export` | `demo_no_session` | needs a signed-in TCGplayer session |
| `/orders/fetch` | `demo_no_session` | needs a signed-in TCGplayer session |
| `/capture` | `demo_no_camera` | writes a photograph to a disk this demo has none of |
| `/codes/scan` | `demo_no_camera` | reads QR codes off photographs on disk |

Each refusal is thrown as a real `ServerError` in the server's own envelope, so a screen draws
it exactly the way it draws a real refusal — the viewer sees a true sentence about the product
rather than a broken button.

**Reads are recorded; writes are real, within reason.** A demo where every press is inert
argues against the product it demonstrates, so the presses that carry the product's own
claim — the sale, the review answer, the stand-down, a price, a hold, a rename, a divider —
are implemented against a **mutable, in-memory copy** of the recording (`structuredClone`d
once at load). Press one and the store visibly changes underneath: the counters, the queues
and the box walk all answer differently afterward, exactly as they do at the desk. Nothing is
persisted — a reload starts the demo over, which is the right behavior for a stranger clicking
a shared link, and no attempt is made to write any of it back.

`demoServer.ts`'s own comment states the boundary this deliberately does not cross: **it does
not re-implement the server.** `server/capture_server.py` is over thirteen thousand lines, and a
second copy of its rules in TypeScript would be a copy that drifts — the exact defect this
repo refuses everywhere else, in `CLAUDE.md`'s own words about the join key and the pricing
answer alike. What exists instead is a patch per write: the documents a real press would have changed,
changed by hand. Anything subtler than that is a refusal, never a guess.

**The screen is told one sentence.** Every refusal says "Not in this demo." (TXT-46). The code
under it names which refusal it was. The reasons in the table above are for the reader of
`demoServer.ts`, not for the screen.

### What the demo answers, since 2026-09-24

- **One canonical key per read.** A GET is its path plus its query pairs, sorted and
  re-encoded on both sides. So a filter the screen builds in another order still finds its
  recording.
- **Re-sliced, never invented.** Copies, picks, today's price and trends are recorded one
  member at a time. The browser merges the members the screen asks for. The server answers a
  subset exactly as it answers the whole, and each route's own docstring says so. A value band
  is recorded whole and cut into the page the screen asks for, with the demo's own cursor.
- **A typed search** uses `kit/match.ts:filterByQuery`, the one matcher the owner ruled every
  search follows, over the search groups the server composed. It does not copy the server's
  ranking. Groups come back in name order.
- **A walk plan** is the recording for exactly the ticked set. A set the recording does not
  hold is refused.
- **Undo.** A sale, a retirement, a review answer and a stand-down answer `restores_to`, and
  `{"undo": true}` reverses each one.
- **A state change reaches every document that holds the card**: the whole-store read, the
  box read, the recent deck, the search groups, the copies and the walk copies. It also moves
  the box counters on every `/boxes` row and each search group's `on_hand`.

### What a press does NOT reach, on purpose

- **The place labels.** D58 renumbers the cards after a sale on the next read. The demo does
  not recompose a label. That matches the owner's "nothing jumps" ruling for a press, and the
  next load of the published page is a reload, which starts it over.
- **The graveyard and the walk plans.** A card sold in the demo does not appear in the
  graveyard, and a recorded walk plan still lists it.
- **The order ledger.** The pull, the close and the fill each write it, and its arithmetic is
  server logic. All three are refused.
- **A typed catalog lookup on Review.** Only the empty lookup a card opens with could be
  recorded, and the demo's queued cards carry no run, so even that one refuses.
- **The shipping export on Home and Orders.** The Shipping stage reads the recorded export
  when it opens, and holds it in the browser's memory. Home and the Orders tab say "no
  export" until then. The fix is in `OrdersShipStage.tsx`, not here.

### The price histories are recorded once, on the owner's Mac

**The owner's ruling (2026-09-24).** Every price history this product draws is read from
`infinite-api.tcgplayer.com`. That host refuses the honest User-Agent (D216), and the owner
allows the browser signature from the owner's own machine only. So CI never fetches a history.
`make demo-histories` records them on the owner's Mac, when the owner chooses:

    PKMNSCAN_TCG_USER_AGENT="<the browser's User-Agent>" make demo-histories

- It reads every demo card that a committed export can place, over all four ranges
  (`pipeline/pricehistory.py:RANGES`). It writes a NEW directory,
  `fixtures/demo-price-history/<date>/`, and refuses if that directory exists. So a fixture is
  never modified.
- Each file is one product and one range, the endpoint's answer verbatim except that `result`
  keeps only the SKUs the demo holds. `index.json` maps each SKU to its product.
- Before it writes, every key of every answer is checked against an allow list of public market
  figures (`scripts/demo-histories.py:ALLOWED_RESULT` and `ALLOWED_BUCKET`). A key outside the
  list refuses the whole run. The User-Agent is never written.
- Without `PKMNSCAN_TCG_USER_AGENT` it refuses, and names the variable.

Measured on the first run, 2026-09-24: 92 SKUs read, 368 files, 0 refused, 3.2 MB. The 40
Pokemon cards in `demo-assets/` have no row in a committed export, so none of them has a
history.

**Two readers, both on the newest directory.** The seed writes the price archive (D219) through
the real `pipeline/pricearchive.py:sweep`, with a `FixtureMarket` in the network's place. So
`#/product` and "Value my stock" draw real ranges. The recorder copies the files into the demo
home's own market cache (`demo-record.py:warm_history_cache`), stamped at record time. So the
per-run price history on `#/pricing` and the trend strip answer from them, and no history
request leaves the build. The product lookup still asks the public tcgcsv mirror for a product
number. That mirror answers the honest User-Agent. The demo never draws an invented price.

## 8a. The coverage spec

`app/tests/demo-coverage.spec.ts` reads the BUILT artifact, `dist-demo/`. It serves the files
on this checkout's own origin under the demo's base path, as a static host would. It checks
that every recorded card has its photograph in the build. It checks that each screen draws its
photographs with a 200. It presses Mark sold then Undo, a Game pick, a typed search and a
review answer with its undo. It opens the order walk, the graveyard, product history, the
value band and "Value my stock". No screen may draw "Not in this demo." on arrival.

Every screen is reached from the demo's root, by the sidebar or by a control on the screen.
The one typed link is `#/product?sku=…`, because D227 makes that view a deep link and no screen
links to it yet.

Run `make demo-static` first. Without `dist-demo/` the cases skip, with that reason.
`DEMO_REQUIRED=1` makes a missing build a failure. Set `DEMO_PREVIEW_URL` to a running
`make demo-preview` to read every file from the preview server instead. Measured 2026-09-24:
18 of 18 pass on this tree. With `DEMO_REQUIRED=1` and no build, 18 of 18 fail.

**CI runs both guards before it publishes.** `.github/workflows/demo.yml` runs
`python3 scripts/demo-record.py --self-test` and then this spec with `DEMO_REQUIRED=1`, after
`make demo-static` and before the upload. A red step stops the job, so nothing is published.
No workflow calls `make demo-histories`.

## 9. No secret can reach a published page, and it is checked against the artifact

Vite inlines only environment variables prefixed `VITE_` into a client bundle. **Verified**:
`.env.example` carries `ANTHROPIC_API_KEY`, `POKEMONTCG_API_KEY`, `TCGPLAYER_STORE_COOKIE`,
`PKMNSCAN_TCG_SELLER_KEY`, `PKMNSCAN_TCG_USER_AGENT` and `PKMNSCAN_LAN_NAME` — every secret
this repo defines — and not one of them carries the `VITE_` prefix. So a public build cannot
leak one by the naming convention alone.

That property is asserted over the built artifact rather than merely trusted.
`.github/workflows/demo.yml`'s "Prove nothing private reached the bundle" step greps
`dist-demo/` for two independent shapes after the build completes: any `/Users/` or `/home/`
path (a machine-local leak — `scripts/demo_scrub.py:audit` is the recorder's own first line of
defense, and this CI check re-examines the artifact rather than trusting an earlier pass over it),
and a **secret value**, never a secret's name — an `sk-ant-` key body, or a
`TCGAuthTicket...=<value>` assignment. Verified in the workflow: this is a deliberate, recorded
correction. The first version matched the bare strings `ANTHROPIC_API_KEY` and
`TCGPLAYER_STORE_COOKIE`, and its very first run blocked the publish on a recorded server
refusal that *named* the missing variable — the opposite of a leak. A guard that fires on the
word for a secret keeps firing on documentation and refusals until somebody disables it, which
is the same argument this repo makes everywhere else about a guard nobody trusts. The step also
prints what it matched, so a real failure does not require reproducing the build by hand to
diagnose.

## 10. Freshness has no gate, on purpose

`make demo-freshness` (`scripts/demo-freshness.py`) compares a digest of `app/src/types.ts` and
`app/src/server.ts` against what `app/demo/bundle.json` was recorded against. **It is not in
`make check`.** Nothing derived from the demo is committed — `app/demo/bundle.json` is built
fresh by CI on every push to `main` that touches the paths `.github/workflows/demo.yml` lists
(`app/**`, `server/**`, `store/**`, `pipeline/**`, `cli/**`, `identify/**`, `geometry/**`,
`codes/**`, `fixtures/**`, `demo-assets/**`, every script under `scripts/` whose name starts
with `demo-` or `demo_`, `Makefile`, the workflow file itself) — so the published copy
cannot go stale. What `demo-freshness` is
for is a local one: a `make demo-preview` running against a recording made before your last
edit, which this command catches without needing a `make check` failure to do it.

## 11. What republishes, and why nothing is ever queued

`concurrency: {group: demo-pages, cancel-in-progress: true}` (verified in the workflow) means
a newer push cancels a build already in flight rather than queuing behind it — a queued build
of older code has nothing to offer once newer code is already on `main`, so the last push is
the only result anybody wants. The job reads the repo and writes to GitHub Pages; it has no
permission to write to the repository itself, so it cannot move `main` and is not a second way
around D42.

## 12. A second, small, real box — opt-in, additive, and off by default

**Built 2026-09-25, on the owner's ruling: "copy paste some data that we already have so it
is not empty in demo... touch / break nothing."** `make demo-seed` on its own stays
byte-identical to before this section existed. Nothing above §11 changed.

`PKMNSCAN_DEMO_EXTRA_REAL=1` is a target-specific Make variable on `demo-static` and
`demo-record`. It reaches `demo-seed` only through that chain. When set, it makes
`scripts/demo-seed.py:add_extra_real_boxes()` run. That function runs in its own
`store.write()`. It runs after the deterministic base store is already committed. It can
only add: one more box, its cards, and a listing row per SKU. No order is written. Buyers
and orders stay invented, on the owner's own ruling.

**Two scripts, run once by hand, against a READ-ONLY COPY of the owner's store, never the
owner's own checkout:**

- `scripts/extract_real_facts.py` writes `demo-assets/real-facts.json`. It holds a typed
  price per SKU, from `prices.json`. It keeps a price only for a SKU a vendored fixture also
  prices, so a mismatch is checkable against the demo's own real arithmetic. It holds a
  short list of real sale lines per SKU: `unit_price` and the order's `placed_at`, never a
  buyer, an order number, or an address. It holds a `pin_skus` list naming specific real
  cards worth surfacing — a $5+ card, a 25%+ typed-price mismatch, a real foil/normal pair.
- `scripts/demo-extra-real.py` curates a second manifest and photograph set:
  `demo-assets/extra/cards.json` and `demo-assets/extra/photos/`. It reuses
  `demo-photos.py`'s QR clearance and crop, loaded by path rather than copied. The same
  positive decode test runs on every candidate. It never picks a SKU the default 132-card
  `demo-assets/cards.json` already curated. `cards.cid` is UNIQUE on the photograph's own
  digest (D172), and the two manifests draw from the same real store.

**Measured on the first real run:** 60 photographs, 1.6 MB, 0 QR refusals. 18 real typed
prices reached the corpus. 26 cards were marked `sold` with a real sale date. This stays
well under the ~20 MB budget. `make demo-determinism-selftest` and a bare `make demo-seed`
are unaffected. The diff against the file before this section is purely additive: two new
functions, roughly 70 lines, plus eight lines wired into `main()`.

**The box carries a neutral name, and so does the section.** Review round 2026-09-25: the
box was first named after the owner directly, and the owner renamed it. It is `Demo Box`
now. Its one section carries no name at all. `Section 1` reads with nothing after it,
exactly how an undeclared section reads everywhere else in this product (D10). No screen,
tooltip, or title in the built demo may say whose cards these are.
`grep -rio owner app/demo/bundle.json dist-demo/` finds nothing about this box. The only
hits anywhere in the built JS and CSS are React's own `ownerDocument` DOM property and an
unrelated `search-field-owner` class name.

**The curator's own QR clearance is not the gate. The commit is.** Review round
2026-09-25: a reviewer committed a synthetic, decodable QR JPEG into
`demo-assets/extra/photos/`. The pre-commit hook let it through. The hook matched the
PATH and never opened the file. It trusted the two curator scripts to be the only
writers, rather than checking. `scripts/qr-clear-check.py` closes that gap.
`scripts/githooks/pre-commit` now re-decodes every STAGED image under
`demo-assets/photos/` and `demo-assets/extra/photos/` with `codes/qr.py`. It reads the
staged blob, never the working-tree file, and refuses on the first decode it finds, naming
the file. `PKMNSCAN_QR=off` is the bypass, in the shape every other opsec rule in this hook
already uses.
