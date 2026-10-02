# The public demo, and why it is not a fork

The published page (`shivinate7.github.io/banchi`) is the real front end playing back a recorded
wire. `.github/workflows/demo.yml` rebuilds it on every push to `main` that touches what it is
built from.

**The published store is a mirror and not an invention (D295, §13).** `make demo-static` installs
a scrubbed recording of the owner's own real store from `demo-assets/mirror/`. `demo-seed`,
`demo-record` and `demo` still work as a generator anyone can run on demand. They are not what
gets published. §§2-6 and §12 describe that generator. §§1, 5-11 and 13 hold for the published
build.

Governing decisions:

- D42: a workflow may publish and never moves `main`.
- D18: a generator may write, and nothing that writes may gate a commit. Every `demo-*` target is
  off the commit path.
- D70: a live code card is a bearer instrument. `demo-assets/`'s photographs must be QR-cleared
  before they can be tracked at all.
- D102 and D94: the mark and the brand on the published page are the same generated ones the real
  app draws.

---

## 1. Why not a fork

The product is one Vite/React front end talking to one Python capture server over one HTTP
boundary. `app/src/server.ts`'s `request()` is the only place a client call is made. Every
exported client function funnels through it. `photoUrl()` in the same file is the only place a
photograph is addressed.

A demo therefore differs from the real product in exactly two functions: what `request()`
resolves to, and what a photograph URL points at. A fork would duplicate all of `app/src` to
carry none of that difference. It would diverge from the real app on the next commit that touched
one copy and not the other.

## 2. What differs, and the three-way split (the seed generator)

`scripts/demo-seed.py`'s module docstring states the split:

- **REAL:** the catalog. Every curated card is drawn from a real TCGplayer export under
  `fixtures/`: real SKUs, names, numbers and market prices. The pipeline join and the pricing
  arithmetic run for real. Nothing about the numbers on `#/pricing` is invented.
- **INVENTED:** which of those cards sits in which box at which index, what has sold, what is
  held back, and who it shipped to. None of it describes a physical object. It makes the store look
  worked and not freshly built.
- **CURATED-REAL:** the photographs (§3).

## 3. The photographs are real, curated and QR-cleared

`scripts/demo-seed.py`'s `Row` class reads a curated manifest of real photographs.
`demo-assets/cards.json` holds 132 entries (`DEMO_PHOTO_COUNT`). Each pairs one of the owner's
card photographs with the identification it actually received. `demo-seed.py` refuses to run
without that manifest.

`demo-assets/` is the one tracked-image exception in this repo. It is safe to track only because
of what curates it. `make demo-photos SOURCE=<checkout>` (`scripts/demo-photos.py`) reads a real
store's photographs. It refuses any photograph that a QR decodes out of, at full resolution and
before the downscale. A live code card's whole identity is that QR (D70).

There are three checks, each on a different artifact:

- The curator refuses a decodable photograph before it is written.
- `scripts/demo-record.py`'s `copy_photos` copies each card's photograph from the card record's own
  `photo` field. It decodes each one with `codes/qr.py`. If a QR decodes on any of them, it
  refuses the whole copy and writes nothing. It never prints the payload. A store that copies no
  photographs is also a refusal. `python3 scripts/demo-record.py --self-test` proves the refusal on
  a throwaway store with a synthetic symbol.
- `scripts/githooks/pre-commit` runs `scripts/qr-clear-check.py` on every staged image (D303). It
  reads the staged blob and not the working-tree file. It refuses on the first decode and names the
  file. `PKMNSCAN_QR=off` bypasses it once.

## 4. The seed is deterministic, and refuses a real store

`scripts/demo-seed.py` seeds one RNG from a fixed constant (`SEED`) and stamps every record as an
offset from one fixed clock (`NOW`). An unchanged tree rebuilds the store byte-identically.

It refuses to touch a store that already holds cards unless `--force` says so. `make demo-seed`
passes `--force` with `PKMNSCAN_HOME=$(DEMO_HOME)` (`DEMO_HOME ?= demo`). An unset `PKMNSCAN_HOME`
means the checkout's own store, which is somebody's real one (D43).

Identification is the one step of the real pipeline that costs money, so it is the only step the
seed fakes. It writes `identifications.json` in the shape a real `pkmnscan identify` run leaves.
`cli/resolve.py` documents that shape as a supported input. Everything after runs for real.
`make demo-seed` runs `./pkmnscan join` against `fixtures/riftbound_export_untouched.csv`, so the
catalog lookup, the variant ladder and the cap arithmetic are the pipeline's own output.

## 5. The bundle, and why it never touches the owner's server

`make demo-record` (`scripts/demo-record.py`) spawns its own capture server over the demo store,
on its own port. It sweeps every GET the client can build against the parameter space the store
holds. It records every 200 response into `app/demo/bundle.json`, plus the photographs Vite
bundles, and it stops that server. It never starts, restarts or binds `make up`'s port, which in
the main checkout is the owner's live process over their real inventory (D43, D138). A 404
recorded here means the path is not a read this demo replays.

`sweep_coverage` records these reads:

- `/graveyard`, `/inventory/recent` at Home's own depth, and `/pipeline/submissions`.
- Every `/boxes` facet filter the three menus can make (D213), each facet unset or one value.
- Each value band (`top`, `bottom`, `gaps`) whole, once per box. The browser cuts the page.
- `/pipeline/holdings-value` for each range, `/pipeline/price-now` for each SKU, and `/pipeline/movers` once.
- `/pipeline/products/<sku>/history` for each SKU, when the server can answer it.
- Three POST routes that only read: `/inventory/copies` per SKU, `/orders/picks` per order, and
  `/orders/walk-plan`. A POST read is keyed `POST <path> <body>` with the body's keys sorted
  (`demo-record.py`'s `post_key`).

Every box has a name. The seed refuses a box with no name and two boxes with one name (D20).

`app/src/demoServer.ts` plays the recording back. `server.ts`'s single `request()` reaches it
through a dynamic `import()` gated on `if (DEMO)`. Every screen, the kit, the shell, the router and
the keyboard map are the same code the owner runs at the desk. Only the wire is frozen.

## 6. `VITE_DEMO` is a build-time constant, not a runtime flag

`app/vite.config.ts` defines `__BN_DEMO__` as `JSON.stringify(process.env.VITE_DEMO === '1')`. That is a compile-time literal. An ordinary build folds it to `false`. Rollup then removes the `if (DEMO)` branch in `server.ts`. So neither `demoServer.ts` nor the recorded bundle (`#demo-bundle`) is ever emitted into a real build's chunks.

A runtime flag was rejected. A UI that could answer from the wrong store at run time is D43's
subject, generalized from "which checkout's store" to "which store, real or recorded, this bundle
can possibly reach". A build-time constant makes the two cases structurally different artifacts
and not one artifact with a mode switch.

`make demo-static` sets it: `cd app && VITE_DEMO=1 DEMO_BASE=$(DEMO_BASE) npx vite build --outDir
../dist-demo --emptyOutDir`.

## 7. `DEMO_BASE` — where the bundle believes it is served from

GitHub Pages serves a project site at `/<repo>/` and never at `/`. A Vite build with no `base`
override assumes `/`, so every asset reference 404s under a subpath. That failure is invisible on
`localhost`.

`.github/workflows/demo.yml` derives the base from the repository name:
`make demo-static DEMO_BASE="/${GITHUB_REPOSITORY#*/}/"`. A repository rename then cannot leave a
stale path in the artifact. The Makefile's `DEMO_BASE ?= /$(DEMO_REPO)/` is a fallback for a
hand-run build and may go stale. `make demo-preview` serves `dist-demo/` through `vite preview`
with the same `--base`, so a link that resolves in preview resolves published.

## 8. What a published page cannot do, refused by name

`app/src/demoServer.ts`'s `CANNOT` table refuses seven paths, each with its reason:

| Path prefix | Refusal code | Reason |
|---|---|---|
| `/pipeline/identify` | `demo_costs_money` | identification is a paid Batch API call against Claude |
| `/pipeline/emit` | `demo_no_export` | needs a live TCGplayer export this demo has no copy of |
| `/pipeline/reconcile-live` | `demo_no_export` | needs a My Pricing export from a signed-in account |
| `/pipeline/live-export` | `demo_no_session` | needs a signed-in TCGplayer session |
| `/orders/fetch` | `demo_no_session` | needs a signed-in TCGplayer session |
| `/capture` | `demo_no_camera` | writes a photograph to a disk this demo has none of |
| `/codes/scan` | `demo_no_camera` | reads QR codes off photographs on disk |

Each refusal is a real `ServerError` in the server's own envelope, so a screen draws it the way it
draws a real refusal. Every refusal says "Not in this demo." (TXT-46). The code under it names which
refusal it was. The reasons in the table are for the reader of `demoServer.ts` and not for the
screen.

**Reads are recorded. Writes are real, within reason.** A demo where every press is inert argues
against the product. The presses that carry the product's claim are implemented against a mutable,
in-memory copy of the recording (`structuredClone`d once at load). Those presses are the sale, the
review answer, the stand-down, a price, a hold, a rename and a divider. Press one and the store
changes underneath: the counters, the queues and the box walk all answer differently afterward.
Nothing persists. A reload starts the demo over, which is right for a stranger clicking a shared
link.

`demoServer.ts` does not re-implement the server. A second copy of `server/capture_server.py`'s
rules in TypeScript would drift. What exists is a patch per write: the documents a real press would
change, changed by hand. Anything subtler is a refusal and never a guess.

### What the demo answers

- **One canonical key per read.** A GET is its path plus its query pairs, sorted and re-encoded on
  both sides. A filter the screen builds in another order still finds its recording.
- **Re-sliced, never invented.** Copies, picks, today's price and trends are recorded one member at
  a time. The browser merges the members the screen asks for. A value band is recorded whole and cut
  into the page the screen asks for, with the demo's own cursor.
- **A typed search** uses `kit/match.ts`'s `filterByQuery`, the one matcher every search follows,
  over the search groups the server composed. It does not copy the server's ranking. Groups come
  back in name order.
- **A walk plan** is the recording for exactly the ticked set. A set the recording does not hold is
  refused.
- **Undo.** A sale, a retirement, a review answer and a stand-down answer `restores_to`, and
  `{"undo": true}` reverses each one.
- **A state change reaches every document that holds the card.** Those documents are the whole-store read, the box read, the recent deck, the search groups, the copies and the walk copies. A state change also moves the box counters on every `/boxes` row and each search group's `on_hand`.

### What a press does not reach, on purpose

- **The place labels.** D58 renumbers cards after a sale on the next read. The demo does not
  recompose a label.
- **The graveyard and the walk plans.** A card sold in the demo does not appear in the graveyard,
  and a recorded walk plan still lists it.
- **The order ledger.** The pull, the close and the fill each write it, and its arithmetic is server
  logic. All three are refused.
- **A typed catalog lookup on Review.** Only the empty lookup a card opens with could be recorded,
  and the demo's queued cards carry no run, so even that one refuses.
- **The shipping export on Home and Orders.** The Shipping stage reads the recorded export when it
  opens and holds it in the browser's memory. Home and the Orders tab say "no export" until then.
  The fix is in `OrdersShipStage.tsx`.

### The price histories are recorded once, on the owner's Mac

Every price history this product draws comes from `infinite-api.tcgplayer.com`. That host refuses
the honest User-Agent (D216). The owner allows the browser signature from the owner's own machine
only. So CI never fetches a history. `make demo-histories` records them on the owner's Mac, when the
owner chooses:

    PKMNSCAN_TCG_USER_AGENT="<the browser's User-Agent>" make demo-histories

- It reads every demo card that a committed export can place, over all four ranges
  (`pipeline/pricehistory.py`). It writes a new directory, `fixtures/demo-price-history/<date>/`,
  and refuses if that directory exists. A fixture is never modified.
- Each file is one product and one range: the endpoint's answer verbatim, except that `result` keeps
  only the SKUs the demo holds. `index.json` maps each SKU to its product.
- Before it writes, every key of every answer is checked against an allow list of public market
  figures (`scripts/demo-histories.py`'s `ALLOWED_RESULT` and `ALLOWED_BUCKET`). A key outside the
  list refuses the whole run. The User-Agent is never written.
- Without `PKMNSCAN_TCG_USER_AGENT` it refuses and names the variable.

The 40 Pokemon cards in `demo-assets/` have no row in a committed export, so none of them has a
history.

Two readers use the newest directory. The seed writes the price archive (D219) through the real
`pipeline/pricearchive.py`'s `sweep`, with a `FixtureMarket` in the network's place. `#/product` and
"Value my stock" then draw real ranges. The recorder copies the files into the demo home's market
cache (`demo-record.py`'s `warm_history_cache`). The per-run price history on `#/pricing` and the
trend strip then answer from them, and no history request leaves the build. The demo never draws an
invented price.

## 8a. The coverage spec

`app/tests/demo-coverage.spec.ts` reads the built artifact, `dist-demo/`. It serves the files on
this checkout's own origin under the demo's base path, as a static host would. It checks these
things:

- Every recorded card has its photograph in the build.
- Each screen draws its photographs with a 200.
- Mark sold then Undo, a Game pick, a typed search and a review answer with its undo all work.
- The order walk, the graveyard, product history, the value band and "Value my stock" open.
- No screen draws "Not in this demo." on arrival.

Every screen is reached from the demo's root, by the sidebar or by a control on the screen. The one
typed link is `#/product?sku=…`, because D227 makes that view a deep link and no screen links to it.

Run `make demo-static` first. Without `dist-demo/` the cases skip, with that reason.
`DEMO_REQUIRED=1` makes a missing build a failure. Set `DEMO_PREVIEW_URL` to a running
`make demo-preview` to read every file from the preview server.

CI runs both guards before it publishes. `.github/workflows/demo.yml` runs
`python3 scripts/demo-record.py --self-test` and then this spec with `DEMO_REQUIRED=1`, after
`make demo-static` and before the upload. A red step stops the job. No workflow calls
`make demo-histories`.

## 9. No secret can reach a published page, and it is checked against the artifact

Vite inlines only environment variables prefixed `VITE_` into a client bundle. `.env.example` names
every secret this repo defines, and none carries the `VITE_` prefix. So a public build cannot leak
one by the naming convention alone.

The property is also asserted over the built artifact. The "Prove nothing private reached the
bundle" step in `.github/workflows/demo.yml` greps `dist-demo/` for two shapes after the build:

- A `/Users/` or `/home/` path, which is a machine-local leak. `scripts/demo_scrub.py`'s `audit` is
  the recorder's own first line of defense, and this grep re-examines the artifact.
- A secret value and never a secret's name: an `sk-ant-` key body, or a `TCGAuthTicket...=<value>`
  assignment.

A guard that matches a secret's name keeps firing on documentation and on refusals that name the
missing variable. Somebody then disables it. The step prints what it matched, so a real failure
needs no local rebuild to diagnose.

## 10. There is no freshness guard

Nothing derived from the demo is committed. CI builds the bundle fresh on every push to `main` that
touches the paths `.github/workflows/demo.yml` lists. The published copy therefore cannot go stale.
`demo-freshness` and `demo-determinism` are retired (D295): the published mirror never reads
`app/demo/bundle.json`, so those guards tested only the invented seed's own recorder.

## 11. What republishes, and why nothing is ever queued

`concurrency: {group: demo-pages, cancel-in-progress: true}` means a newer push cancels a build in
flight and does not queue behind it. A queued build of older code has nothing to offer once newer
code is on `main`. The job reads the repo and writes to GitHub Pages. It has no permission to write
to the repository, so it cannot move `main` and is not a second way around D42.

### 11a. Dispatching `demo.yml` on a branch is a safe dry run

`demo.yml` triggers on a push to `main` only. A PR never runs it. Dispatch it by hand on a feature
branch instead: `gh workflow run demo.yml --ref <branch>`. The `github-pages` environment names a
deployment-branch policy of `main` alone (unverified from this repo). The `build` job then runs in
full, and the environment refuses `deploy` before `actions/deploy-pages` loads.

Read the `build` job's own conclusion and never the run's overall one. The run reads red because
the environment refused `deploy`, not because anything failed. To see what got packaged, download
the artifact: `gh run download <id> -R shivinate7/banchi -n github-pages -D <dir>`.

## 12. A second, small, real box — opt-in, additive, and off by default

`make demo-seed` on its own is unchanged by this section. `PKMNSCAN_DEMO_EXTRA_REAL=1` is a
target-specific Make variable that `demo-record` sets. It makes `scripts/demo-seed.py`'s
`add_extra_real_boxes()` run. That function runs in its own `store.write()`, after the deterministic
base store is committed. It only adds: one box, its cards, and a listing row per SKU. No order is
written. Buyers and orders stay invented.

Two scripts run once by hand, against a read-only copy of the owner's store and never the owner's
own checkout:

- `scripts/extract_real_facts.py` writes `demo-assets/real-facts.json`. It holds a typed price per
  SKU from `prices.json`, kept only for a SKU that a vendored fixture also prices. It holds a short
  list of real sale lines per SKU: `unit_price` and the order's `placed_at`, never a buyer, an order
  number or an address. It holds a `pin_skus` list of real cards worth surfacing.
- `scripts/demo-extra-real.py` curates `demo-assets/extra/cards.json` and
  `demo-assets/extra/photos/`. It reuses `demo-photos.py`'s QR clearance and crop, loaded by path.
  It never picks a SKU that `demo-assets/cards.json` already curated. `cards.cid` is UNIQUE on the
  photograph's own digest (D172), and both manifests draw from the same real store.

The box is named `Demo Box`. Its one section carries no name, so `Section 1` reads with nothing
after it, as an undeclared section reads everywhere else (D10). No screen, tooltip or title in the
built demo may say whose cards these are.

The curator's QR clearance is not the gate. The commit is. A hook that matched only the path once
let a decodable synthetic QR JPEG into `demo-assets/extra/photos/`. §3's `qr-clear-check.py` closes
that gap.

## 13. The store is a mirror, not an invention (D295)

The owner's ruling was "full mirror is fine". Photos are capped "to just 512mb". Every name reads
"Jane Doe N", and every address reads "123 Demo Way". D295 carries every quote in full. This
section is the mechanism. D295 is the decision.

`demo-static` depends on `demo-mirror-install`. The build step is unchanged: `VITE_DEMO=1 npx vite
build` (§6). Every reader downstream of `app/demo/bundle.json` is unchanged too: `demoServer.ts`
and the coverage spec (§8a). Only the bundle's source changed.

Three commands, three machines:

- `make demo-mirror SOURCE=<checkout>` runs on the owner's Mac only. It reads a `.backup` copy of
  the real `store.sqlite`, scrubs the copy, records the result offline, and writes the scrubbed
  output to the tracked `demo-assets/mirror/`.
- `make demo-mirror-rebuild` runs on the owner's Mac. It iterates on the scrub or the recorder
  without reading the real store again.
- `make demo-mirror-install` runs in CI and anywhere else. It reads no store and contacts no
  network. It copies the committed `demo-assets/mirror/` into `app/demo/` and
  `app/public/demo/photos/`.

**The one check is the owner's own ruling and not a CI gate.** `demo-mirror.py`'s
`assert_scrubbed()` runs once, on the owner's Mac, before anything is committed. It is a plain
`assert` over the finished recording and the shipping export. Every buyer name must match
`^Jane Doe \d+$`. Every address field must be blank or exactly "123 Demo Way". The workflow does not
repeat it.

**The mirror refreshes daily and merges itself.** `make demo-mirror-agent` installs a launchd job
on the owner's Mac (main tree only). `scripts/demo-mirror-daily.py` cuts a throwaway worktree from
fresh origin/main, runs `demo-mirror`, and stops quietly when `demo-assets/mirror/` is unchanged.
A scrub failure or any error publishes nothing and logs why to `~/.pkmnscan/demo-mirror-daily.log`.
Otherwise it opens a PR from `demo/mirror-refresh` and merges it on green CI, with no word asked.
**A PR auto-merges on green CI only under three conditions** (D295, D42). Its head is
`demo/mirror-refresh`. This script opened it after the scrub assert and the fence. Its whole diff
is under `demo-assets/mirror/`.
The fence refuses a path outside it, a rename from outside, and a non-regular file. It also refuses
a PR head that differs from the local HEAD it fenced. A red PR, or one a day old, on that branch
is closed first. A lock file stops two runs from overlapping.

**The store never leaves the Mac.** `demo-mirror/`, the raw snapshot, is gitignored. Its comment in
`.gitignore` records why. `demo-assets/mirror/`, the scrub's output, is the one thing committed. It
stands on the same footing as `demo-assets/photos/` and `demo-assets/extra/photos/`: a tracked
exception this repo allows only because of what curates it. `scripts/githooks/pre-commit`
re-decodes every staged image for a QR before it lets a commit through (D70, D303).

**The walk-plan sweep records singles.** A real store's open orders make a powerset that no constant can reach: 71 open orders is 2^71 sets. Only an open order can ever be ticked. Every caller of `walkPlan` sends open keys alone (`Fulfillment.tsx`, `Orders.tsx`, D97, D220). So the recorder reads the recorded `/orders` GET and keeps the open keys. It records every single open order, plus the one full "walk all" set that every screen asks for whole. It never records a merge or a subset in between. `demoServer.ts`'s `walkPlan` refuses an unrecorded set with the demo's one honest notice (D269, TXT-46) and never fabricates a plan. A partial selection (some orders, not all, not one) is the one gap this recording leaves on purpose.

**Open.** `ux/stock-images` is a separate lane that may put stock image URLs on route responses.
This section does not depend on it. Proving the mirror deterministic means reading the real store
twice, and nothing does that yet.
