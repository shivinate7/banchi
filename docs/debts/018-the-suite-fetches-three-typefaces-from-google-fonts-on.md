## 18 — ~~The suite fetches three typefaces from Google Fonts on every page load~~ — CLOSED 2026-09-08

**Found 2026-09-08 while surveying `make design-check`'s flake rate, and closed by D124 in the
same change** — so it was never a standing debt, and it is written down here because the survey
that found it is the kind of reading this file exists to preserve.

**What it was.** `app/index.html` carried a `preconnect` pair and a `fonts.googleapis.com`
stylesheet pulling Inter (400/500/600/700), Manrope (500/600/700/800) and JetBrains Mono
(400/500/600). `app/tests/fontsReady.ts:settleFonts` awaits `document.fonts.ready` and is called
by nearly every one of the 461 browser tests; every test gets a fresh browser context, so **one
suite run reached the public internet on the order of a thousand times**.
`app/tests/shell.ts:sealEveryTest` did not cover it and could not: its seal matches on
`CAPTURE_ORIGIN`, this checkout's capture port, and a font request is a different origin.

**What it cost, stated honestly, which is the reason it was recorded rather than merely fixed.**
**No failure in the ten-run survey was traced to it.** `&display=swap` degrades a failed fetch
into a paint in the fallback face, so this was never a hang and never a live fire. What it was is
an undeclared outside dependency in the suite that decides whether the design floors hold — a DNS
stall and a slow render are the same red — and the cases that would feel it first are the ones
measuring type: `brand.spec.ts` measures lockup geometry, `inventory.spec.ts` prices a column
against a mono advance.

**What closed it.** Six `woff2` binaries under `app/src/fonts/`, declared by `app/src/fonts.css`,
plus `sealOutside` in `app/tests/shell.ts` — an allow-list of this checkout's two ports, so a
re-introduced remote face fails the suite by name instead of quietly undoing the fix. The bytes
are the ones `fonts.gstatic.com` was serving, which is why nothing measured moved: 55 advance
widths compared local against Google in one browser, 0 differing, and `brand.spec.ts` 20 of 20.
D124 carries the argument and the three non-obvious properties of the CSS.

**WHAT IS NOT CLOSED, AND THE FIRST DRAFT OF THIS PARAGRAPH GOT ONE OF THEM WRONG.** It named
three groups of doc sheets as equally not worth vendoring, on the ground that vendoring "would
duplicate the binaries". That is true of two of them and false of the third, which was already
reaching into `app/src` by relative path.

**Closed with the rest: `docs/specs/box-drawings/sheet.html`.** It wanted the same three
families at the same weights and already `<link>`ed `../../../app/src/tokens.css`, so pointing it
at `../../../app/src/fonts.css` beside that line cost **no bytes and no new binary**. Checked the
way a person opens it — from a `file://` URL, where a font load is not the same thing it is over
https: all faces resolve locally, no request leaves, nothing fails.

**Still on Google, and deliberately.** `docs/design-refs/*.html` wants **ten families** — 782 KB
of `latin`+`latin-ext` over 26 files, before Cabinet Grotesk from **Fontshare**, a second CDN
under a licence that is not OFL and would have to be read first — for archived drawings of a
palette this product no longer paints. `docs/specs/logo/sheets/*.html` wants IBM Plex Sans JP, a
CJK face, for sheets that are opened by hand. **Nothing renders either group on any gate**, and
that was verified rather than assumed: `scripts/build-mark.mjs` reads `small-cut.html` as TEXT
and evaluates its drawing block against a `window` stub, `build-lockup.mjs` reads a `.js`, and
`docs-audit`'s `lockup params` compares declared holds as text. A fetch cannot move a verdict
there; it can only show a person a fallback face, which is visible and self-correcting.
`docs/design-refs/README.md` already records that. **The app now LOADS nothing from outside
the origin it came from, and `app/tests/` asserts that on every case.** The one external URL left
in `app/src` is an `href` in `Markdown.tsx` pointing at TCGplayer's pricing admin — a link the
operator presses, not a resource the page fetches, and `sealOutside` would catch it the moment it
became one.
