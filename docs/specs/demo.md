# The public demo, and why it is not a fork

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
