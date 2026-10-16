## D124 — Fonts are vendored; the suite allows two ports

**Built 2026-09-08.** `app/index.html` carried a `preconnect` pair and a
`fonts.googleapis.com` stylesheet for Inter, Manrope and JetBrains Mono. The three families are
now six `woff2` binaries under `app/src/fonts/`. `app/src/fonts.css` declares them. `app/tests/shell.ts`
grew a second seal that refuses any request leaving this machine.

### What was actually wrong, stated at its real size

**Not a live fire, and it is worth saying so before the argument.** No failure in a ten-run survey of `make design-check` was traced to a font fetch. `&display=swap` is why. A fetch that fails paints the fallback and moves on. So the failure mode is a DEGRADED measurement rather than a hung one.

What it cost is an **undeclared outside dependency in the suite that decides the design floors**.
`app/tests/fontsReady.ts:settleFonts` awaits `document.fonts.ready` and is called
by nearly every one of the browser tests. Every test gets a fresh browser context. So one suite
run reached the public internet on the order of a thousand times. A DNS stall and a slow render
are the same red. The cases that would feel it first are the ones measuring type. `brand.spec.ts` measures lockup geometry. `inventory.spec.ts` prices a column against a mono advance. Those are the cases whose verdicts nobody can reproduce from the tree alone.

**`app/tests/shell.ts` was already the file about exactly this and could not see it.** Its seal
matches on `CAPTURE_ORIGIN`, a port; a font request is a different origin entirely. D43's argument applies to `fonts.gstatic.com` as squarely as it applied to the owner's capture server. That argument is that a verdict that depends on a process outside the checkout is not a verdict. The second case had been sitting under the first the whole time.

### The bytes are Google's, which is the only reason no measurement moved

Each file was fetched from `fonts.gstatic.com` through the same `css2` request `index.html` used
to make. Every declaration in `fonts.css` is copied from that response verbatim. That covers family,
style, weight, `unicode-range`, and subset ORDER.

**A re-cut from upstream, or an `@fontsource` package, would have been a different binary**.
Every type assertion in `app/tests/` would have been re-litigating itself against a
face nobody had compared. The debts record would have gained a section instead of losing one.

**Measured rather than asserted.** 55 advance widths were read in one Chromium. They cover three families, every weight each family ships, and five samples including a `latin-ext` string and a CJK-fallback string. Each was read against both the local faces and the Google ones under aliased family names.
**0 differing, to below a thousandth of a pixel.** `brand.spec.ts` is 20 of 20 green.

### Three properties of the vendored CSS that are not cosmetic

**The weights stay discrete.** Google serves ONE variable `woff2` per family per subset.
It points four `@font-face` blocks at it, each pinning a single weight. For Inter, that is 7 files
answering 28 declarations. Collapsing those to one `font-weight: 400 700` range is smaller CSS, and it
is a different product. Four rules in `app/src` ask for `font-weight: 650`. That resolves against
discrete faces to 700, and against a range to an actual 650.

**`latin-ext` is declared before `latin`.** Their ranges overlap at U+0304, U+0308 and U+0329.
The last declaration wins. Reversing them pulls three combining marks out of a 48KB file into
an 85KB one.

**The URLs are relative.** `make demo-static` builds under a `/<repo>/` base and a site-absolute
`/fonts/…` is right at `/` and 404s there. That is the trap `public/manifest.webmanifest` already
records. Files under `app/public/` are copied verbatim and would have hit it. Files under
`app/src/` are hashed and rebased by Vite. They were, checked against a `DEMO_BASE=/banchi/` build.

**Two subsets of the seven, measured.** Every non-ASCII codepoint `app/src` renders is in `latin`.
Any other one is outside all seven, and it already fell back (`← → ⇧ ⌘ ≥ ─ │`, and `番地`, which no Latin face
has ever carried). `Δ` and `Σ` appear only in comments. `latin-ext` is kept anyway, because card names
arrive from TCGplayer rather than from this repo. Cyrillic, greek and vietnamese are dropped. That
is 22 declarations over 6 files instead of 70 over 19.
**Dropping a subset cannot move a metric** — the glyphs a kept subset draws come from the same
binary.

### The seal is an allow-list, and that is the part worth arguing

Vendoring the faces UNDOES the dependency. It does not stop the next person adding one. The undoing would be invisible when they did. That is the whole reason `app/tests/shell.ts` exists in the shape it does, rather than as a comment asking people not to leak.

**`sealOutside` refuses every port but this checkout's two.** It is registered before `sealCapture`, so
it is the last resort under every stub. It is recorded in a `WeakMap` and asserted empty in
`afterEach`, exactly like the first seal.

**A block-list naming `fonts.googleapis.com` was refused**, . This repo has a receipt for that
shape. A dry-run guard built as a block-list of guessed endpoint names failed open. It let a
real TCGplayer Staged import through. What the suite is entitled to talk to is knowable and short.
What it might one day be pointed at is not.

**The port is the test, not the hostname**, for the reason `CAPTURE_ORIGIN` already gives.
`server.ts` composes its base from `location.hostname`. So the same page opened at `banchi.lan`
asks a different host on the same two ports. Both are still this Mac.

**Proved by mutation, because a new sweep that goes green proves nothing.** Re-adding a
Google Fonts `<link>` to `index.html` fails all 20 `brand.spec.ts` cases, each naming the URL and the
two `woff2` requests behind it.

### What this does not touch

**The two logo working files still fetch from Google.** The line is whether anything
RENDERS them. That was verified rather than assumed. `scripts/build-mark.mjs` reads `small-cut.html` as
TEXT and evaluates its drawing block against a `window` stub. `build-lockup.mjs` reads `lockup-core.js`.
Nothing in this repo opens either in a browser, so a slow CDN cannot move a verdict. That is the whole difference from the suite.

**`font-display: swap` is kept**, so `fontsReady.ts` keeps its job. Self-hosting does not close
the swap window — it makes the thing being waited for local.
