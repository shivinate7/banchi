## D108 — The dock app is the page Chrome already renders, and the manifest is what makes it one

**Banchi goes in the dock as an installed web app on the engine it already runs on. Nothing is wrapped, nothing is bundled, and the capture server stays a launch agent.** Investigated 2026-09-06 from the owner asking for "a proper app in the Mac dock rather than a URL in a browser tab".

### What "feels real" decomposes into, and what already answered each

Five things, and four of them were already true or one click away:

- **Its own dock icon, its own ⌘-Tab entry.** Chrome's *Install page as app* writes a real bundle to `~/Applications/Chrome Apps.localized/` with its own `CFBundleIdentifier`, its own `CFBundleName` and its own `app.icns`. Verified by inspection of `My Hue.app`, a Chrome-installed app already on this Mac — not from documentation.
- **Its own window, no browser chrome.** Measured on this machine in a throwaway profile: an app-mode window reports `display-mode: standalone`, `outerWidth === innerWidth` (no side chrome at all) and a 32px frame, which is the title bar and nothing else.
- **It remembers its size.** Measured: resized to 1512x780, Chrome quit, relaunched — 1512x780 came back. Position is remembered too, clamped to the screen.
- **The camera.** Unchanged, because the engine is unchanged. This is the whole argument and it is in the next section.
- **Always live.** `make launch-agent` already does this and D53 argued the shape. Nothing here touches it.

### The camera is why this is not an open question

**`app/src/useCamera.ts` asks for 3840x2160 `ideal` over a Cam Link with `deviceId: {exact}`, and the rig has only ever been proven on Chromium.** An installed web app is the same Chromium, the same profile and the same origin, so there is nothing to re-prove: `http://localhost:5173` is a secure context, the permission grant lives in the profile's content settings, and the installed bundle points at that same profile — `My Hue.app`'s `CrAppModeUserDataDir` names the default profile's `Web Applications` directory, which is what makes the grant carry. Measured in a *fresh* profile the state is `prompt`, which is the same statement from the other side: the grant is per profile, and the owner's profile already has it.

**Every other host re-opens a question this one never asks.** `MIN_WIDTH`/`MIN_HEIGHT` is 1280x720 and it is a hard floor, so a host that could not clear 720p would fail loudly — but a host that settled on 1920x1080 would pass the floor and be **four times worse than the rig can produce, silently**. That is the failure `useCamera.ts`'s own header is written against, and it is the reason engine changes are not a free variable here.

### Rejected: Safari's Add to Dock

It produces the same thing — a real bundle, own icon, own window — and it is one click, so it was the closest competitor rather than an also-ran. **It is WebKit.** Two unknowns ride on that and neither is worth carrying for a dock icon that Chrome gives for free: this app has never been rendered in Safari at all (`make design-check` and every spec run on Chromium), and the Cam Link's 4K mode under WebKit's `getUserMedia` is unmeasured — the silent-1080p case above. Cheap to try later as a *second* app; not the one to depend on.

### Rejected: Tauri and Electron

- **Tauri is WebKit** (`WKWebView`), so it inherits Safari's unknowns *and* adds a Rust toolchain this machine does not have — `cargo` and `rustc` are both absent — to a repo whose stated invariant is that the capture server must never need `make venv`.
- **Electron is Chromium**, so the camera would be fine, and that is the only thing it gets right. It is 150-250MB, a second build pipeline, and a wrapper large enough to be tempted into owning the server — see below. It buys a dock icon that already costs nothing.

**Neither was built and neither should be without a reason this entry does not have.** What would reopen it: wanting the app when Chrome is uninstalled, wanting a signed artifact to hand to a second person, or the page needing something a browser will not give it.

### The server stays a launch agent, and a wrapper owning it would be D53's own defect

**A wrapper that also starts the capture server is a second answer to a solved problem, and this repo has already measured what that costs.** D53 records it: `make launch-agent` bootstrapped a second supervisor whose capture child could not bind, gave up after five retries, and overwrote `supervisor.pid` with its own pid — *"Two supervisors: one serving, one supervising nothing, and the pidfile naming the wrong one."* A wrapper process holding a third opinion about who owns `:8000` would reproduce that with a GUI in front of it. The dock app is a **client**. It opens a URL; the launch agent keeps the URL answering.

**What that leaves honest: if the supervisor is down, the dock icon opens Chrome's error page.** The window is the app's, the error is the browser's, and there is nothing in the product to say so. That is the one place this shape is visibly a web app, and it is accepted rather than unnoticed — `KeepAlive` makes it rare and D53's fast-failure cap makes it possible.

### What actually changed in the repo

**The manifest, which was an icon manifest and is now also an install manifest.** It was written so `apple-touch-icon` had a raster to point at; being installable was never its job, and it was wrong for it in one way that no check could see.

**Every URL in it was site-absolute, and that is measurably broken at any base but `/`.** Measured against the published demo on 2026-09-06: `https://shivinate7.github.io/pkmnscan/manifest.webmanifest` answers 200, and inside it `"/icon-192.png"` resolves to `https://shivinate7.github.io/icon-192.png` — **404**, while the file it means is served one directory down under the demo base — and `start_url: "/"` resolves to a 404 as well. Vite rebases the `<link rel="manifest">` address and copies `app/public/` **verbatim**, so this is the one file in that directory that has to carry its own base and did not. Relative URLs (`.`, `icon-192.png`) resolve against the manifest's own address and are therefore correct at both: at the root they are byte-for-byte what the absolute forms meant, and under the demo base they are what the absolute forms failed to mean. Verified under a simulated base directory: `start_url`, `scope` and all three icons 200.

**`launch_handler: {client_mode: "focus-existing"}`** is the line that is about the dock rather than about correctness. Clicking a dock icon focuses the window that is open; without it a second press opens a second window, which is the tell that separates an app from a shortcut. `focus-existing` and not `navigate-existing` because a press mid-review should return to the review, not to Home.

**`id`** decouples the app's identity from `start_url`, so changing where it opens later does not orphan an installed copy. **`scope`** is the default made explicit, and correct under a base for the same reason `start_url` is.

**The colors were considered and left alone.** `background_color` is `#0c0e12`, which is the dark ground, while the app's default theme is light — so a light-theme launch flashes dark for the moment before first paint. A manifest holds one value and cannot be media-queried, so changing it trades that flash for the same flash in the other theme. `app/index.html` already carries two `<meta name="theme-color">` entries, one per scheme, which is the accurate statement in the one place that can make it.

### What is NOT done, and is a spec question rather than an oversight

**The icon is edge-to-edge and macOS app icons are not.** Chrome will build `app.icns` from `icon-512.png`, which is the mark's superellipse tile filling the frame; Apple's icon grid insets the artwork and uses its own corner curve, so Banchi will read slightly larger in the dock than its neighbors. **This is not fixed here on purpose.** `docs/specs/logo.md` is the mark's store of record (D102), nothing in `app/` may hand-draw it, and the padding and corner geometry a macOS icon wants are a locked-geometry question for that spec — not a value to re-derive in a manifest. `scripts/build-mark.mjs --icons` writes 180, 192 and 512; a 1024 with the Apple grid applied would be the change, and it belongs in the spec's own section.

### Amended 2026-09-06 — the icon was built, and the light/dark question is section 12's

**The macOS grid was the one thing this entry left undone, and the owner asked for it same day.**
`docs/specs/logo.md` section 17 now locks it: **824pt of artwork on a 1024pt canvas**,
which is not a convention this project adopted but what the neighbors measurably already are —
Safari, Mail and Calculator all read **exactly 80.47%** solid off their shipped `.icns` on this
Mac, and the mark read 100%. That is 24% wider and 55% more area than everything beside it.

**The whole manifest set is inset, not only the largest**, because Chrome builds the installed
app's `.icns` by resizing that set and a set disagreeing with itself would pad the dock icon at
one size and not the next. `favicon.svg` left the icon list for the same reason — `sizes: "any"`
made a full-bleed entry a candidate at every size — and is still the tab icon by `<link
rel="icon">`. `icon-180.png` is untouched: iOS masks a full-bleed square itself.

**Nothing redraws the mark.** The inset is applied by drawing it smaller on a transparent
canvas; section 3's geometry is locked and `make docs-audit`'s new `mac icon grid` row
reconciles `MAC_GRID` against section 17 in both directions, plus the manifest's set against the
generator's. Proved by falsification before it was trusted: drifting the constant to 800/1024
fails it, and putting `favicon.svg` back in the icon list fails it.

**A dark-mode dock icon was asked about and is refused twice over.** macOS 26 does support
per-appearance app icons, but they are an Icon Composer `.icon` asset in a native bundle and
Chrome writes a plain `.icns`; a manifest icon takes no media query either.
**The design half had already ruled** — section 12 derived a light ground and rejected it, *"an object, not an ink
color: an app icon on a phone home screen does not invert when the phone does"* — so this is
section 12's to reopen, on a sheet, and the platform limit is downstream of that rather than a
reason to revisit it.

**Still not done, and now written down rather than noticed: the shadow.** Every system icon
measured carries a drop shadow out to 87.5% and the mark carries none, so it sits flatter on the
dock's shelf. Section 17 names what would settle it — a sweep at 128, 64 and 32px against the
same three icons — rather than a value typed into a generator.

### Amended 2026-09-11 — the URL is `:8000`, and a port is part of an origin (D138)

**The installed app would be created from `http://localhost:8000` now**, because the capture server serves the page itself and `:5173` belongs to `make dev`. Everything above is unchanged: the same Chrome, the same profile, the same manifest — which is already relative and needed no edit — and the same argument that the dock app is a CLIENT and never a second supervisor.

**And no dock app has ever been installed, which this amendment first said the opposite of.** Checked on the owner's Mac 2026-09-11: `~/Applications/Chrome Apps.localized/` holds `My Hue.app` and nothing else — the very bundle this entry inspected to prove the mechanism. So this entry is an investigation that was never acted on, the owner's own words are *"I never had/used a dock app"*, and the install below is a FIRST one, optional, rather than a repair the port move forces. The entry is otherwise unaffected: what it measured about Chrome, the profile and the camera is all still true of whoever presses it first.

**What the move costs is two resets, and it costs them WITH OR WITHOUT the dock app, which is the part that matters.** The owner opens this product in an ordinary Chrome tab at `http://localhost:5173`; a browser origin is scheme, host AND port, so `:8000` is a different origin to that tab just as it would be to an installed app:

- **The camera grant prompts once more.** This entry measured that the grant lives in the profile's content settings, which is true and is keyed by origin — so the rig re-grants on first open. One press.
- **Every `localStorage` key resets once** (D27): the capture screen's remembered camera and rotation, the theme, the rail, and the two order keys. The rig re-picks its camera and its rotation, which is the only one of the six that costs a moment. This is D27's rename cost repeated, and the same ruling applies for a better reason — a fallback ACROSS origins is not merely undesirable, it is impossible.

**Move between shifts rather than mid-capture**, for the reason D27 names by name: `banchi.session.captureId` is `sessionStorage` and a capture in flight when the tab closes can burn a position.

### What would reopen this

*A second person needing the app*, which wants something signed and installable rather than a click in one profile. *Chrome going away* on this machine. *The page needing a capability a browser withholds* — a real filesystem, a background process, a global hotkey. *The demo being meant to install*, which it is not: the manifest is correct there now, but a demo with no server behind it is a page to look at.
