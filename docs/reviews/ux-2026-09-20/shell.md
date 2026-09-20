# Shell (sidebar, rail, top bar, command palette, keyboard sheet, toasts, offline banner, error boundary)

Widths looked at: 1440, 1280, and a controlled 1000px test (see finding 1) — all via
`resize_window` + `getBoundingClientRect`/`getComputedStyle`, cross-checked against
`innerWidth` after every resize because the tool's viewport emulation did not always apply
reliably on the first call (see "What I could not check").
Themes looked at: dark (measured in depth), light (screenshotted earlier in this session at
1440 only, sidebar expanded state, looked correct — not re-measured numerically this pass).
No writes performed; the command palette and keyboard sheet were opened by dispatching
synthetic `KeyboardEvent`s from the page's own JS context (the Browser pane was hidden for
most of this pass, which blocks the `computer` tool's real key-press action but not
`window.dispatchEvent`) — both are pure client-side UI state, opening them writes nothing.

## Findings

1. **The sidebar's collapsed/expanded default is decided once, at first mount, from
   `window.innerWidth` — it is never re-evaluated if the window is resized afterward without
   a full reload.**
   What I saw / proved: with `localStorage['banchi.rail']` cleared (no stored preference),
   reloading at 1440px gives `data-rail = null` (expanded) — correct, since 1440 ≥ 1280.
   Without reloading, resizing the same live tab down to 1000px (well under the 1280
   threshold that a fresh mount would use to default to collapsed) leaves `data-rail` still
   `null` (still expanded). The rail never collapses on its own no matter how narrow the
   window gets, because nothing re-runs the check after mount.
   Where: `app/src/App.tsx:324-326` —
   ```
   function readRail(): boolean {
     return storedRail() ?? window.innerWidth < 1280
   }
   ```
   used as a `useState` lazy initializer at `app/src/App.tsx:1352`
   (`const [rail, setRail] = useState(readRail)`) — a lazy initializer runs exactly once, at
   mount, by React's own contract. There is no `resize` listener anywhere that re-derives
   `rail` from a new `window.innerWidth`.
   Severity: **high**, on its own merits as a design defect (independent of any written rule):
   a person who drags their browser narrower, undocks a side panel, or moves the window to a
   smaller external monitor expects the shell to adapt; instead it freezes at whatever
   density it started in until they either reload the whole app or reach for the manual `⌘.`
   toggle themselves. This is exactly backwards from every other responsive surface in the
   product (page width, tile counts, etc., all of which *do* react live to `resize`).
   Fix: add a `resize` listener that re-derives the rail state when the person has not made an
   explicit choice yet (i.e., only when `storedRail()` is `null` — once they've toggled it by
   hand, `rememberRail` should keep winning, which it already does).
   Recurs elsewhere? This is a single shell-level piece of state (`App.tsx`), so it affects
   every screen identically — Home, Capture, Runs, Review, and everything else all inherit
   whatever the rail's frozen value happens to be. It is the single highest-leverage fix in
   this slice: one function, one file, fixes all four screens' left-inset behavior at once.

2. **Command palette (`⌘K`) items are impeccably consistent: all 16 items across 5 groups are
   exactly 36.26px tall with 0px difference between icon and label baselines.**
   Measured: `.bn-cmdk-item` heights are `[36.26]` (a single unique value across all 16 rows —
   no variance at all). Icon-to-text vertical center difference measured on the first three
   items: `0, 0, 0` px. Group labels ("Go to", "Hand-off", "Appearance", "Help", "Developer")
   are all `10px`/`700`/uppercase/`1px` letter-spacing, identically. No defect found; recorded
   because this is exactly the kind of "icon not on the same baseline as its text" defect
   class called out in the brief, and the palette passes cleanly.

3. **Keyboard reference sheet (`?`) opens centered on the full viewport (not offset by the
   sidebar), matching the command palette's own centering.**
   Measured: sheet `x = 268.8`, `w = 902.4` at `innerWidth = 1440` → left margin = 268.8,
   right margin = 1440 − 268.8 − 902.4 = 268.8 — perfectly centered in the full window, sidebar
   included in the centering math rather than centered only in the content column. This is a
   legitimate design choice (a modal dims everything, sidebar included) and is applied
   consistently between the two overlays I opened (palette and keys sheet share the same
   centering behavior). No defect found.

4. **All shell-chrome hover transitions (sidebar nav links, the brand/logo tile, the topbar,
   the rail-toggle button) use a single consistent 120ms duration — no drift found.**
   Measured every `button`/`a` under `.bn-side` and `.bn-topbar`: every nav link, both ghost
   buttons, and the topbar brand tile report `0.12s, 0.12s, 0.12s[, 0.12s]`. The one outlier,
   `.bn-brand-slot`, animates `width, height` at `0.32s` — that's a size-morph animation (the
   logo's slot growing/shrinking with the rail), not a hover-color response, so it isn't
   comparable to the others and isn't flagged as an inconsistency.
   This is the same sweep that caught Home's three off-token hover speeds (see home.md finding
   1) — the shell itself has no such drift.

5. **Error boundary has two shapes as the codebase claims, read from source but not triggered
   live** (triggering a real crash was judged too invasive/unreliable to force safely against
   the owner's live store): the owner's shape (`app/src/App.tsx:363-370`, a card with the
   Banchi mark, an `h1.bn-title`, presumably "reload or home" per the two doors mentioned) and
   the Fulfiller's `plain` shape (`app/src/App.tsx:351-360`), which is a bare
   `<main className="crash-plain">` with exactly one button ("Open it again") and no brand,
   no error text, matching the described intent. I did not render either live, so I cannot
   confirm actual spacing, type sizes, or that the "reload or home" doors are actually two
   buttons rather than one plus a link — that detail is UNKNOWN from source alone.

6. **Server-state indicator ("Server online" / "Server offline" / "Checking server…") is a
   small dot + text in the sidebar footer** (`app/src/App.tsx:1202-1205`, duplicated at
   `:1335-1336` for a second placement I did not identify by screen). I saw "Checking server…"
   render briefly during a page reload in an earlier light-theme screenshot this session, and
   "Server online" (implied by no visible banner) throughout the rest — but I never saw
   "Server offline" or its associated offline banner live, since that requires the capture
   server to actually stop answering, which I must not induce.

7. **Toasts were not seen live.** `app/src/kit/toast.tsx` shows a consistent structure (icon,
   title, optional body, a dismiss button, and an optional drain-timer bar whose
   `animationDuration` is set inline per-toast from `ttlMs`), but every toast in this product
   is the result of some action completing — I did not trigger one, since every path I found
   to produce a toast is also a path that writes.

## What I could not check

- **The Browser pane was hidden for most of this pass** (a host-side state outside my
  control — I could front the tab but the pane itself would not composite frames), which
  blocked `computer.screenshot` and `computer.key`/`hover` for the bulk of the session. I
  substituted `window.dispatchEvent(new KeyboardEvent(...))` for opening the palette and keys
  sheet (confirmed working — both `defaultPrevented` and the resulting DOM node prove the
  real handler ran) and `getBoundingClientRect`/`getComputedStyle` for all measurement. This
  is precise for layout/timing/color facts, but it cannot see: rendering glitches, a font
  that silently fell back, an image that failed to decode, or the actual painted intermediate
  frame of a transition — those remain UNKNOWN, not confirmed clean.
- **`resize_window`'s emulation did not always apply on the first call this pass** — twice, a
  requested 1440×900 viewport did not take effect until I re-issued the call and confirmed
  `innerWidth` via JS. I adopted a "verify after resize" discipline for every measurement
  reported above, but any earlier reading in this conversation (before I adopted that
  discipline, e.g. in the very first exploratory pass) that was not re-verified this way
  should be treated with lower confidence than the numbers in this file.
- **Multiple agents share this browser context.** I saw tabs opened and closed by other
  sessions mid-pass (`tabId`s appearing and disappearing without my action, including one of
  my own tabs closing unexpectedly). I moved to a dedicated tab (`tab-5`) for all measurement
  in this file and did not touch any tab I did not open myself, but this means the shared
  browser's state (localStorage, current route) could have been touched between my calls by
  another agent — I did not detect this happening, but I cannot rule it out with certainty.
- **Mobile/tablet bottom tab bar, the phone drawer, and anything below 820px** — out of scope
  by the brief, not checked.
- **The offline banner's actual layout and copy**, and **toast stacking behavior with 2+
  toasts on screen at once**, are UNKNOWN — never triggered.
- **Light theme** was only screenshotted once, early in this session, for the expanded
  sidebar at 1440; the collapsed rail, the command palette, and the keys sheet were never
  seen in light theme at all this pass.
