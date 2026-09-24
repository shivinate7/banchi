# Design

**Banchi.** 番地 — a lot number, the address of a thing. Every card in this store has one:
box → section → card. The product is named after the idea it is built on, and the system
below is built around the three registers that idea needs: **ink**, what you read; **line**,
what separates; **brand**, where to look.

Two audiences, two standards. The owner's screens are a tool — dense is fine. The
Fulfiller's screens are the entire product for a retired, non-technical user, and "if a
flow needs explaining twice, redesign the flow" is a real requirement with no way to check
itself. So it is written below as numbers.

**This file was rewritten on 2026-09-03 for the Banchi front end, and it describes what is
in the tree rather than what was locked in 2026-08-12.** The palette that interview chose —
`#FCFCFD`, Cabinet Grotesk, Atkinson Hyperlegible, Martian Mono, one radius, light only — no
longer renders anywhere in `app/`. It is not marked historical here; it is gone, because a
token block a reader might mistake for the current one is worse than no block at all. The
two arguments that outlived it are kept and re-stated where they now apply: a palette is
chosen against a rendered card rather than described in prose, and a token nobody can argue
with is a token the next session will quietly replace.

## Tokens

`app/src/tokens.css` is the only file in `app/` allowed to write a color, and **D94 is the
decision entry behind everything in this section.** Everything else paints from these names.
They are grouped by the JOB rather than by the value, they all carry the `--bn-` prefix, and
every one of them has a light value and a dark value under one name.

```
NEUTRALS                        light        dark
--bn-bg                         #f4f5f8      #0c0e12     the page
--bn-surface                    #ffffff      #14171c     raised: panels, rows, cards
--bn-surface-2                  #eceef2      #090b0e     sunken: wells, code, inactive tracks
--bn-surface-3                  #f7f8fa      #1b1f26     an object that paints its own ground,
                                                         lifted: a chip, a card, a raised row
--bn-surface-glass              white .72    #14171c .72 the sticky bars, over blur
--bn-hover                      ink 3%       white 4%    the pointer is over this surface. An
                                                         alpha, so it rides the ground — a
                                                         surface that rests TRANSPARENT only

INK
--bn-ink                        #0f1217      #eef0f4     body text, headings, money
--bn-ink-2                      #3b414b      #b9bfc9     secondary text, a value in a key/value row
--bn-ink-3                      #666c76      #838b98     metadata, captions, placeholders. Light
                                                         value darkened 2026-09-20: the old
                                                         #6b7280 measured 4.43:1 on --bn-bg and
                                                         4.16:1 on --bn-surface-2, failing this
                                                         row's own job at 4.5:1. #666c76 clears
                                                         both (4.85:1, 4.55:1).
--bn-ink-4                      #6b717b      #7c8492     icons, separators, disabled, the lightest
                                                         word. 4.51:1 on --bn-bg light, 5.13:1 dark.
                                                         Raised 2026-09-23 (UX-047): #7f8791 was
                                                         3.33:1 and #707886 4.04:1 on the surface,
                                                         both under 4.5:1 for words people read

LINE                            (all three are ink at an alpha, so they ride the ground)
--bn-line                       ink 8%       white 8%    the hairline. Every separation.
--bn-line-strong                ink 16%      white 16%   the boundary of a control you type into
--bn-line-focus                 accent 55%   accent 60%  a field that has focus
--bn-field-edge                 #878d97      #626977     the edge of a field or a checkbox, at 3:1
                                                         on its ground in both themes (UX-094;
                                                         --bn-line-strong is 1.41:1 on white)

BRAND
--bn-accent                     #3d5af1      #7f90ff     action: buttons, links, selection, focus
--bn-accent-hover               #2f4bd9      #93a2ff
--bn-accent-press               #2540c2      #6b7dfa
--bn-accent-tint                accent 10%   accent 14%  a lit row, a ghost button's hover
--bn-accent-tint-2              accent 18%   accent 24%  selection, a focused field's halo
--bn-on-accent                  #ffffff      #0c0e12     label on an accent fill. Never a ground.
--bn-live                       #d63d2b      #ff6a58     vermilion: the logo dot, a live camera,
                                                         a capture. 4.6:1 as text on the light page
--bn-live-tint                  live 12%     live 16%

SEMANTIC                        (the kit paints these as TEXT — pills, buttons — over their tint)
--bn-ok / --bn-ok-tint          #15803d 5.0:1             #3ddc84
--bn-warn / --bn-warn-tint      #b45309 5.0:1             #f5a524
--bn-danger / --bn-danger-tint  #b91c1c 6.5:1             #ff5c5c
--bn-money                      = ink in both themes: money is not a color, it is a weight
PILL INKS                       a tone's word on that tone's tint, at 4.5:1 over --bn-bg,
                                --bn-surface and --bn-surface-2 in light (UX-047). Dark reads
                                the tone ink itself, which already clears 5:1 on its tint.
--bn-pill-ink-ok                #11733a
--bn-pill-ink-warn              #a14b09
--bn-pill-ink-live              #b33020
--bn-pill-ink-accent            = --bn-accent-hover light, = --bn-accent dark
--bn-pill-ink-danger            = --bn-danger in both themes

ELEVATION                       (three steps, each a hairline ring plus a shadow, so a panel
                                 is separated in dark where a 1px line alone disappears)
--bn-shadow-1                   a resting panel, a button
--bn-shadow-2                   a menu, a photo frame, a raised card
--bn-shadow-3                   a dialog, a sheet
--bn-shadow-accent              the one glow: a primary button under the pointer
--bn-btn-bg / -hover / -shadow  the default button's ground, a token rather than a rule so dark
                                can lift a button off a panel of its own color

TYPE                            Manrope 500-800 · Inter 400-700 · JetBrains Mono 400-600
--bn-font-display               Manrope        headings, figures, the page title
--bn-font-ui                    Inter          every sentence, every label, every control
--bn-font-mono                  JetBrains Mono EVERY NUMBER AND EVERY MACHINE STRING
--bn-fs-2xs … --bn-fs-5xl       10 11 12 13 14 16 18 22 28 36 48   (base is 14)
--bn-tracking-caps  0.06em      the one tracking a word may take: uppercase metadata
--bn-tracking-tight -0.02em     display sizes only. A FIGURE IS NEVER TRACKED. Was -0.015em;
                                moved 2026-09-20 to the value 36 untokened call sites already
                                carried as a raw literal — one intent, one number now.
--bn-lh-tight       1.1         a hero figure or a headline set close (covers 1, 1.05, 1.1, 1.15)
--bn-lh-snug        1.25        UI labels, controls, table rows (covers 1.2, 1.25, 1.3)
--bn-lh-base        1.4         body default (covers 1.35, 1.4, 1.45)
--bn-lh-relaxed     1.55        long-form, wrapped sentences (covers 1.5, 1.55, 1.6)
                                Named 2026-09-20 over 15 shipped literals; no line-height
                                token existed before. Values only — call sites still read
                                their own hand-typed number until a sweep moves them.

SPACING                         --bn-1 … --bn-10 = 4 8 12 16 20 24 32 40 48 64
--bn-0-5     2px                micro-spacing below --bn-1's 4px floor, named 2026-09-20 (68
                                uses shipped untokened)
--bn-0-75    3px                micro-spacing, named 2026-09-20 (11 uses shipped untokened)
--bn-1-5     6px                micro-spacing, named 2026-09-20 (77 uses shipped untokened)
RADIUS                          --bn-r-xs 4 · -sm 6 · --bn-r 8 · -lg 12 · -xl 16 · -2xl-sm 18 · -2xl 22 · -full
                                -2xl-sm named 2026-09-20: 18px split the xl/2xl gap at 9 call
                                sites independently before this row existed.

MOTION                          --bn-t-fast 120ms · --bn-t 200ms · --bn-t-slow 320ms
--bn-ease                       cubic-bezier(.2,0,0,1)     the default
--bn-ease-out                   cubic-bezier(0,0,.2,1)     something arriving
--bn-ease-spring                cubic-bezier(.34,1.4,.44,1) a chevron, a check, a dialog
--bn-stagger 30ms · --bn-stagger-cap 12   one cadence for every list
--bn-t-draw 480ms · --bn-t-emphasis 600ms · --bn-t-pulse 1.8s · --bn-t-spin 0.7s
--bn-disabled 0.45              the one opacity a disabled pressable wears

NOT PAINT                       (two colours the reader never sees as colour, named so they
                                 are not hex literals in a stylesheet)
--bn-mask                       #000000      the opaque end of a `mask-image` gradient. A mask
                                             carries ALPHA and no colour, so this is black in
                                             both themes by definition rather than by choice
--bn-flash                      #ffffff      the capture flash overlay. White in both themes
                                             for the reason a shutter is: it reads as light
                                             rather than as a surface, and a dark flash is not
                                             a flash

STAGE — DARK IN BOTH THEMES     the viewfinder and the photo heroes
--bn-stage-bg #0c0e12 · -bg-2 #171b25 · -surface #1b2029 · -ink #eef0f4
--bn-stage-accent #7f90ff · -hover #93a2ff · -press #6b7dfa · -on-accent #0c0e12
--bn-stage-ok #3ddc84 · -warn #f5a524 · -danger #ff5c5c · -live #ff6a58

SHELL                           --bn-sidebar-w 236 · --bn-rail-w 64 · --bn-topbar-h 52
--bn-control-h 34 · -lg 40 · -sm 28      → 42 · 46 · 40 under a coarse pointer
PAGE WIDTH                      --bn-page-w 1600 · -rows 1344
                                a CAP, not a breakpoint: 1536 and 1280 of content
--bn-page-top                   = --bn-6 (24). The one gap above every `Page`'s title (UX-133).
                                A `Page` reads --bn-page-w alone; -rows is for the screens
                                not yet on `Page` (D-one-page-width)

TYPE ROLES                      aliases onto the scale, never new sizes (UX-067, UX-115)
--bn-fs-h1                      = --bn-fs-3xl (28)  the page title, `.bn-title`
--bn-fs-h2                      = --bn-fs-xl (18)   a section, `.bn-h2`
--bn-fs-h3                      = --bn-fs-lg (16)   a part of a section, `.bn-h3`, an overlay title
--bn-fs-read                    = --bn-fs-md (13)   the floor for a sentence a person must read
--bn-fs-label                   = --bn-fs-xs (11)   a caps label, a pill. Never a sentence
```

**Three registers, and the third one is two colors rather than one.** `--bn-accent` is
indigo and means *press this*; `--bn-live` is vermilion and means *this is happening now* —
a camera that is open, a capture landing, a run going. Nothing else may use vermilion, and
the reason is the one thing the old palette got right about a single accent: a color that
means two things means neither.

**A tint is the color at an alpha, never a second hex**, so every tint rides its own theme's
ground and there is no second value to keep in step. The same is true of all three line
weights: they are ink at 8% and 16% in light, white at 8% and 16% in dark.

**`--bn-stage-*` is dark in BOTH themes, and that is a deliberate exception to everything
above.** A viewfinder and a photograph of a card are looked at, not read; a light chrome
around a dark frame is glare in the one place the operator is judging an image. Those tokens
therefore do not flip, and a screen drawing on the stage uses the stage's own accent and ink
rather than the page's.

**The legacy aliases at the foot of the file are a migration seam that is already spent**
(D94). The old sheet exported `--ink`, `--muted`, `--line`, `--accent`, `--field`, `--display`,
`--util`, `--s1`…`--s8` and `--radius`; keeping them live is what let every screen re-skin the
day the token file landed and then be rebuilt one at a time. **Measured 2026-09-03: not one
file under `app/src` reads a legacy name, against 255 uses of `var(--bn-ink)` alone.**
They are dead code kept for one commit, deliberately not deleted in the change that emptied
them — a token file and thirty stylesheets moving together is a revert nobody can take apart —
and a new rule may not read one.

**`--bn-control-h*` is raised by the POINTER, not by the width.** The media query is
`(max-width: 767px), (hover: none) and (pointer: coarse)`, because an iPad in portrait is
820px wide and all thumb, and a thumb needs 40px whatever the viewport says.

**`scripts/docs-audit.py`'s `design tokens` row reads the block above, and what it locks is
stated here rather than left to be inferred.** It was a stale READER for a day — it parsed
hex-and-name rows, three typeface rows, one spacing row and one radius row, a format that
stopped existing when this system landed, and it read zero tokens and failed. Worse than empty,
it merged every `:root` in `tokens.css` into one dictionary, so a dark value silently overwrote
its light one; under a system where every colour has both, that is a check that could not have
been right even with a working parser.

It now keeps the two themes apart and compares them separately. **It locks every `--bn-` name**:
a token declared in the stylesheet that this block does not name fails the commit, and so does a
name here that nothing renders. **It compares a value only where this block states a hex** —
31 of them, across both themes. An alpha (`ink 8%`), an alias (`= ink in both themes`), a
duration, an easing curve and a shadow are named and checked for existence, and their values are
locked nowhere a script can read; `docs/DEBTS.md` carries that gap rather than this row implying
a coverage it does not have. **The row is still not to be satisfied by respelling the palette —
that is D16's forbidden direction.** What changed is which side was wrong.

## Light and dark are both first class

**The theme is `data-theme` on `<html>`, and nothing else.** `app/src/kit/index.tsx` holds
`readTheme`/`applyTheme`; `app/src/App.tsx` follows the system until a choice is stored and
remembers the choice in `localStorage` under `banchi.theme`. That key is device-local by
nature, like the camera's `deviceId`, and is not inventory — the rule it must not break is
that nothing about a card or the store lives in browser storage.

**Dark redefines the surfaces, the inks, the three lines, the brand, the semantics, the
shadows and the button ground. It redefines nothing else**, so no component sheet ever learns
which theme it is in. A rule that needs to know has got the token wrong.

**The flip is one mechanism for the whole page.** The toggle stamps
`html[data-theme-switching]` for `--bn-t-slow` and `app/src/base.css` eases background,
color, border, shadow, fill and stroke together, then the attribute comes off and components
keep their own transitions. A cross-fade on `<body>` alone was measured as a two-speed flip —
dark panels on a light ground for a third of a second.

**Dark is not a filter over light, and three families are drawn rather than derived.** The
accent lightens (`#3d5af1` → `#7f90ff`) because an indigo that carries white text on paper
cannot carry dark text on a near-black ground; `--bn-on-accent` inverts with it; and the
elevation set stops being a shadow and becomes a shadow plus a white ring, because a drop
shadow separates nothing on a black page.

**The contrast rule is stated per role now, and it is weaker than the one it replaces.** The
2026-08-12 palette's rule was "every token that carries text clears 7:1 on every ground it
sits on", and this palette does not: `--bn-ink-4` is 3.6:1 in light and is the floor a
*word* may sit at rather than a caption, and `--bn-ok`/`--bn-warn` are 5.0:1 as text on
their own tint. What the rule became:

- **Data-bearing text is `--bn-ink-3` or darker.** A price, a count, a position, a name, a
  reason code. `--bn-ink-4` is for icons, separators, disabled controls and a word that is
  decoration.
- **The Fulfiller's 7:1 floor is unchanged and is the one that is asserted.**
  `app/tests/fulfillment.spec.ts` computes every ratio from the *rendered* colors, so a
  token edited without being argued here breaks a test rather than a promise.
- **Nothing measures the owner's screens, in either theme, and nothing measures dark at
  all.** No Playwright spec sets `data-theme`. That is the honest state of it: dark is
  first-class in the tokens and unasserted in the suite, and a session that adds a
  dark-theme assertion is closing a real gap rather than gilding one.

## The kit

`app/src/kit.css` and `app/src/kit/` hold the primitives every screen is built from (D94).
The class prefix is `bn-`. Load order is fixed in `app/src/main.tsx` — tokens, then base, then
the kit — so a screen sheet outranks the kit by arriving after it: **a screen may refine a
button and never has to redraw one.**

| Primitive | Use it for | Not for |
|---|---|---|
| `Button` | anything that acts. `primary` is the one solid accent fill on a screen; `ghost` for a control beside content; `quiet` for a sunken control; `danger` for a destructive verb, `danger-solid` only where the destruction is the screen's whole purpose; `ok` for a confirming verb | a link that navigates and writes nothing |
| `Chip` | choose one of a set, or filter a list. Pressed is ink-on-page, not accent | a button with a rounded corner |
| `Pill` | a state, a count, a lane — something the row IS | anything pressable |
| `Kbd` | the key that does this thing, owner-side only | the Fulfiller's screens, which are touch |
| `PageHeader` | every owner screen's first element: eyebrow, title, lede, actions | a panel heading — that is `.bn-section-title` |
| `EmptyState` | a list with nothing in it, saying what would put something there | an error |
| `Notice` | a refusal, a warning, a standing condition, with the server's own code under it | a receipt of something that worked — that is a toast |
| `Segmented` | two to four exclusive views of the same thing | navigation between screens |
| `Stat` | one figure with its label, on a dashboard row | a value in a key/value list (`.bn-kv`) |
| `Logo` | the mark, in the shell and on the crash page | decoration inside a screen |
| `.bn-code` | a machine string under its human label — a reason code, a SKU, a key | a number a person reads, which is `.bn-mono` |
| `.bn-panel` / `.bn-well` | a raised group / a sunken one (a log, a paste box) | nesting one in itself |
| `.bn-scrim` + `.bn-dialog` / `.bn-sheet` | something over the page | anything that could be a section of the page |
| `.bn-photo` / `.bn-crop` | a photograph of a card. `.bn-crop` is the other half of `cropStyle` | a decorative image |
| `useLeave` | keeping an overlay mounted one beat so it can animate out | delaying a write |
| `cropStyle` | turning `POST /pipeline/crop-preview`'s rectangle into a picture of the card rather than of the stand | deciding WHEN to ask for one — that is a screen's policy |

**The icon set is 73 paths in `app/src/kit/Icon.tsx`**, on a 24-unit grid at 1.75 stroke with
round caps and joins, drawn in one idiom so the whole product speaks a single line weight.
They inherit `currentColor` and are `aria-hidden`, so an icon is never the accessible name of
anything. **Add an icon by adding a path**; a screen that draws its own `<svg>` inline is the
drift the file exists to prevent, and `ICON_NAMES` is what draws the whole set on
`#/gallery`.

**Every primitive is on one page, at `#/gallery`.** It is the kit rather than a component
sheet now, it is reachable from the command palette (never the nav), `make screenshot`
renders it, and `app/tests/pull-confirm.spec.ts` measures three of the Fulfillment floors on
its pull-confirm specimens.

## Motion, and what a control owes the person pressing it

**The motion rule is in `kit.css`'s own header because it is a correctness rule, not a
taste.** An enter animation ends at the element's OWN resting style and is always
`backwards` — never `both`, never `forwards`. A finished `both` holds its last frame
applied over every author rule, so a `:hover` transform on that element is dead and the
element becomes a containing block for `position: fixed` descendants. `forwards` is right in
exactly one place: `[data-leaving]`, where the node is about to unmount and should hold its
vanished state until it does.

- **One cadence for every list.** `.bn-stagger` reads `--i` off each child and waits
  `min(i, 12) × 30ms`, so the arithmetic leaves the JSX and no two lists disagree.
- **120 / 200 / 320ms.** A hover or a color is `--bn-t-fast`; something that moves is
  `--bn-t`; something that arrives over the page is `--bn-t-slow`.
- **`prefers-reduced-motion` is honoured, with four exemptions that are named.** The busy
  ring, the skeleton shimmer, the live dot and the capture spinners keep turning at 1.4s
  rather than freezing: a ring stopped at a partial arc reads as a disabled button, and a
  frozen shimmer reads as broken content.
- **One focus ring, product-wide** — a 2px accent outline at 2px offset, keyboard only, set
  once in `base.css`. A field takes its own: accent border plus a 3px tint halo.
- **The cursor floor is in `base.css` and is one specificity**, so every per-screen choice
  outranks it and nothing global can take a cursor away from a stylesheet that named one.
- **A receipt is a toast; a refusal is a toast that does not leave.** `kit/toast.tsx` has
  four kinds: `receipt` carries the way back and expires with its undo window, `status` and
  `ok` expire, and `refusal` stays until it is dismissed, because the server's own message is
  the one thing a person may need to read twice. **Nothing demands an acknowledgement to
  dismiss** — that ban is in "What this is not" below and it survives the rebuild.
- **An overlay owes the keyboard three things**: focus lands inside it, Tab stays inside it,
  and focus returns to the control that opened it. `InventoryOverlay.tsx` does this for the
  inventory screen's four kinds and `runsOverlay.ts` for the two runs overlays. That there
  are two of them is a debt, written down in `docs/map.py`: it wants to be one kit `Dialog`.
- **Same-role buttons stacked in one sector share a width** (`D195`):
  the widest sibling's own intrinsic width, left-aligned, never the sector's full width and
  never a hard-coded pixel. `.bn-actions-stack` in `kit.css` is the wrapper form; the capture
  block's `.capture-block-list` is the cross-row form for buttons that each live in their own
  list row. Asserted in a real browser by `app/tests/button-stack.spec.ts`, which discovers
  its subjects rather than reading a declared class — the same argument the cursor floor
  already makes.

## Layout, density, and the widths this was drawn at

**One system, two densities.** Owner screens use the small end of the spacing scale; the
Fulfillment view uses 24-64 and the floors in the constraints table below. Same tokens, same
three faces, same kit. The alternative — two deliberately different visual worlds — was
considered and rejected: it doubles the token surface and gives two components to keep in
sync, and the Fulfillment constraints are already expressible as a floor applied to a subset
of routes.

**Page chrome is the kit's now, and the four numbers this file used to publish are retired.**
They read: 16px of padding on all four sides, a 20px display title sharing its line with the
controls, a one-line lede, and the first row of real content within 150px of the top. What is
in the tree instead is `.bn-page` (24px top, 32px sides, 64px foot; 16px sides on a phone)
and `PageHeader` — an eyebrow, a `--bn-fs-3xl` title, a one-line lede at the body size, and
the actions pinned to the TITLE row by a 19px offset so the primary button lands at the same
y whether the lede is zero, one or two lines. The half of the old rule that survives is the
half that paid: **the title, the counts and the controls share one line**, and a screen that
stacks a title block above a control bar has invented 45px of chrome nobody argued for.

**Every screen shares one left edge, and only its width may vary** (`D197`).
`.bn-page`'s `margin` is `0`, never `0 auto`: a screen's own `--bn-page-max` narrows the page
from the shell's own left inset, it does not re-center a shrunken column inside a wider one.
A lower cap used to move a screen's whole gutter toward the middle of the space the shell
handed it, which put `#/pricing`'s content some 330px right of `#/review`'s at the same
window width — asserted now by `app/tests/page-edge.spec.ts`.

**Retiring those numbers is a real loss and it is recorded rather than argued away.** They
were written after the Inventory screen was measured spending 240px — 27% of a 1440x900
viewport — on chrome before its first card. Nothing mechanical enforced them then and nothing
does now; `scripts/docs-audit.py` cannot see a padding, and the Playwright specs measure the
Fulfillment view, which this section does not govern. A screen that drifts back to a 32px
page header will do it silently.

**The shell is three shells, one per width (D95), and one of them is nothing at all.** A
236px sidebar at 1024px and up, collapsing to a 64px icon rail on `⌘.` and remembered per
device under `banchi.rail`; a 52px top bar and a 64px bottom tab bar below 768px, the tabs
being the four routes that carry `tab: true` and everything else behind a left drawer; and no
chrome at all on the Fulfiller's route — not-rendered rather than hidden. `⌘K` opens the
command palette over any of them and `?` opens the one keyboard reference sheet, which is
where a binding is documented now that the inline key hints are gone.

**The widths this build was walked at are 390, 820 and 1440.** A phone, an iPad in portrait,
and the owner's Mac. **820 is the width that catches the mistake**: it is above every phone
breakpoint and all thumb, which is why the control heights follow the pointer instead.

**Every width the shell reacts at is named below, and `make docs-audit`'s `breakpoints` row
reads this block.** It replaced a sentence that published two counts — "54 media blocks hang
on the first and six on the second" — where the six was seven. A count beside a list is the
drift this file exists about, so the counts now live in the row's summary, taken at run time.

**The form: a `min-width` is the step, and a `max-width` is the step MINUS ONE.** That is what
keeps a width from being both a floor and a ceiling, and it stops one edge being spelled two
ways. Before this was written, four edges were spelled twice — 559/560, 639/640, 899/900,
1099/1100 — and three integers were used on both sides. None of it was a rendering defect,
because the sheets that disagreed drew different screens; it was a vocabulary nobody could
read, and therefore one no guard could enforce.

```
LADDER          the shared vocabulary. Any sheet may use these.
  480           the narrow phone
  560           the wide phone: a receipt, a box bar and a hero fold here
  640           the phone/tablet seam
  768           the tablet, and the shell's own rail boundary
  900           a two-column body becomes one, ahead of the tablet step
  1024          the desk: at and above this the sidebar is 236px, or 64px railed
  1280          the wide desk

REFINEMENTS     a width ONE screen reflows at for a reason of its own, named with the sheet
                that owns it. A refinement no sheet uses is a number nobody chose.
  700           Fulfillment — paired with a landscape/short-height query: the landing
                column widens past `--ff-col` on a phone laid flat, rather than staying
                centered under dead margin on both sides
  1100          Codes — the board loses its third column · Fulfillment — the wide column
  1200          ReviewQueue — the card's photo column steps down
  1320          ReviewQueue — the queue rail becomes a sheet, beside the RAIL
  1360          CaptureScreen — the hero must not be the narrowest column
  1500          ReviewQueue — the queue rail becomes a sheet, beside the SIDEBAR

CONTAINER       widths measured against a COLUMN rather than the window, so they are not on
                the ladder and carry no step arithmetic: a `pane` of 640px and a viewport of
                640px are different quantities. Each is named with its container and sheet.
  copies  470   CardLocations — the marker's track stops being 110px and starts being ~285
  copies  479   CardLocations — the identity keeps every character, the stage triple drops
  copies  619   CardLocations — the address takes the whole line
  pane    479   BoxBrowse — the fact grid goes to one column
  pane    559   BoxBrowse — the photograph stops short of the full width
  pane    560   BoxBrowse — the photo/copies band splits in two
  pane    760   BoxBrowse — the fact grid goes to two columns
  value   469   ValueBands — the bar stops being sticky and the cause row loses its third column
  value   619   ValueBands — the row becomes a card: the address takes its own line
  value   760   ValueBands — the drawer grid goes to one column and the row gives up its gaps
  page    1099  Pricing — the ship bar's key legend takes a line of its own
  pricing 599   Pricing — the row becomes a card
  pricing 880   Pricing — the deck takes two columns
  pricing 939   Pricing — the row becomes a compact two-line row
  pricing 1040  Pricing — the DIRECT column joins the table
  (unnamed) 520, 640   RunPanel — the run detail's own steps, on `.runs-detail`
  bn-page 640   kit — a `Page`'s toolbar folds into equal cells, and its actions take a line

COLUMN-BLIND    a sheet allowed to ask the VIEWPORT a question at or above 1024, with why.
  Fulfillment.css   `persona: 'fulfiller'` draws no shell (D5), so the viewport IS its column
```

**Above 1024, prefer a cap or a container to a viewport width.** Every screen but the
Fulfiller's is drawn inside `.bn-shell-main`, which is the viewport minus 236px — or minus
64px when the rail is collapsed. Those differ by 172px, wider than the gap between two ladder
steps, so a `min-width: 1024px` fires in a 788px column and in a 960px one and cannot tell
them apart. `--bn-page-w` and `--bn-page-w-rows` are the caps; `@container` is the tier
switch. The `breakpoints` row asks this as a QUESTION rather than blocking on it, because
whether a given rule is asking the wrong thing needs a reading of what it does.

**None of this reaches `#/fulfillment`.** That view keeps the 24-64 end of the scale and
every floor in the constraints table, and those floors win wherever the two could be read as
disagreeing.

## The address is drawn, not printed

**The position bar carries TWO SCALES, and they must be distinguishable at a glance.**
Added 2026-08-23 on the owner's ask — *"not only its location at the box level but section
level"*, then *"while retaining box depth too"*. The box scale answers how far into the box
to put your thumb (D20's original argument); the section scale answers where you are inside a
divider. They routinely disagree: a card reading `#51 of 53` draws hard right at box scale
and is `Card 1` of section 3 — the very front — at section scale. Both are true, and a person
walking to a box needs the first to get near it and the second to land on it.

**THE SECTION IS THE RULER AND THE BOX IS THE MARGIN NOTE, AND THAT ORDER WAS REVERSED ON
2026-09-11** (D155, on the owner's *"the interface/view of the box is nicer
than section"*). The section is a graduated 26px ruler with a fill, a pin that crosses it and
its own bounds written inside its two ends; the box is an 8px strip of chips beneath it. The
argument is resolution: at the 580px bar this screen draws, the box track is **1.45px a card**
and the mark's own footprint covers about 7.6 of them, while the caption above it already says
`#51 of 53 · 96% in` exactly — and the section scale is 6.8 to 82.9px a card.

Three cues separate them, and none is a new color: the two are **26px against 8px**, a caret on
the box chip indents the ruler beneath it, and the ruler's caption opens with the section number
where the box caption opens with `#`. Each scale keeps exactly one of the two ornaments — the
ruler has graduations and no chips, the strip has chips and no graduations — so they cannot be
confused at any width. The marker convention is the server's own `fraction`, so a card at the
front of both sits at the front of both.

**This paragraph said "8px against 16px" until that day, and the tree had shipped 12px since the
rebrand.** `app/tests/inventory.spec.ts` carried the identical stale 16 in its own comment: two
documents agreeing on a number neither of them read.

**The section denominator says which kind it is** — `slots` for a settled divider, `so far`
for the growing last section of an open box. That rule is D20's, argued there; it is repeated
in the caption because the number is small and the operator is already at the right box, which
is exactly when a silently switching denominator is easiest to miss.

**In an UNDECLARED box the two scales say the same thing, and that is the truth rather than a
redundancy to design away** (2026-08-29, D10 amended). Such a box has one section — the box —
so both tracks draw the same marker over the same denominator and both say `so far`. What
they said before was worse: the section scale was measured against a divider at every 25th
card that nobody had put in, so `Card 6 of 25 slots` was drawn under a box holding 133 cards
and no dividers at all. Two tracks agreeing is a box nobody has divided yet; the second track
earns its height the moment somebody presses `S`.

**AND THIS PARAGRAPH WAS DESCRIBING SOMETHING THE CODE DID NOT DO, FROM THE DAY IT WAS WRITTEN
UNTIL 2026-09-11** (D155). `PositionBar` gated the second scale on
`spans.length > 1`, and `spansOf` returns exactly ONE span for an undeclared box — so the box
this paragraph is about drew one track, not two. The gate is deleted. It could not survive the
flip in any case: with the ruler promoted, keeping it would have left the owner's largest
undivided box drawing only the 8px strip — the biggest box on the smallest picture. The cost is
real and is named in the entry: such a box now spends 26px saying one fact twice.

**`pipeline/join.py:Position.label` is the record; HOW A SCREEN DRAWS IT IS A VIEW (D41).**
The owner: *"i didn't ever like the dot theme to separate"*. The interpuncts are deleted
rather than restyled — the box and section become a tracked muted stack and the card number
a figure beside them — and the server still emits the identical string, which travels
verbatim on `aria-label`.

- **A tracked key is a word, never a figure.** `--bn-tracking-caps` on `BOX` / `SECTION` /
  `CARD`. Every NUMBER keeps `letter-spacing: 0`, because the mono face is fixed-advance and
  tracking a figure is what the mono rule exists to prevent.
- **Every owner site sets ONE number, `--pos-slot`, and the path and the key derive from
  it.** Six sites set it today, and the figures moved with the rebuild: the `#/inventory`
  band at 40px (36 when the column narrows), the retire dialog at 28, the capture stage at
  28, the copies list at 22, an order's pick row at 22, and `#/review`'s caption at 15. The
  warning this list used to carry is still the reason it is per-site: 44px down a seven-copy
  list cost +86px and dropped a copy below the fold.
- **A label with no figure is still ranked, and it is the FIGURE that goes (D71).** A
  departed card's label ends on a state where a slot number would be (`Box 3 · departed`).
  The state and the store key ride the path as one more key/value pair, the number column is
  drawn empty, and the reserve holds the whole slot column so a figure-less row's path starts
  at the same x as every other. As a singleton the path re-ranks to
  `clamp(11px, 0.45em, 20px)`, because with no figure the path is the payload. What renders
  whole is a label naming no position at all — the pooled row, where there is no coordinate
  to rank.
- **The Fulfiller's sites are not owner sites and never take it.** His labels stay plain text
  under `app/tests/fulfillment.spec.ts`'s 32px tabular floor, and the guard is that his
  components do not import `PositionLabel` — not a selector prefix, which is the thing a
  refactor drops. Every selector in `PositionLabel.css` is `.position-*`, which exists in the
  DOM only where that component rendered it.

**Mono carries every number and every machine string.** Positions, prices, collector numbers,
counts, ages, SKUs, reason codes — `--bn-font-mono`, with `tnum` and `zero` set in `base.css`
so a figure never changes width between cards. The body face is reserved for sentences a
human reads. This one rule does more than any other to keep the thing from reading as a
newspaper.

## What this is not

**Not Collectr, not Discogs, not LibraryThing.** Three cataloguing tools that became
spreadsheets: dense gray tables, everything at one weight, no hierarchy between a $12 card
and a 15-cent one. This is the failure mode with a face on it, and it is worth naming
because the review queue *is* a list of hundreds of rows and will drift there by default.

**Not NYT/FT.** No newspaper coding: no high-contrast serif display, no editorial column
measure, no warm-paper ground. An earlier pass landed there — warm cream, rust accent,
Fraunces — and was rejected as too sanitized-professional for what this is. The register is
tech-forward: mono carrying the metadata, saturated accent rather than muted earth,
hairlines rather than air.

**No confirm dialog on a reversible action.** No "are you sure", no success acknowledgement
to dismiss, no list → detail → back loop in the review queue. Answering a card writes the
answer and advances. Undo covers the mistake; a dialog only makes the ninety-nine correct
answers cost two taps each.

**"Undo covers the mistake" was not true on the review queue, and D28 is the repair.** That
clause is what this whole rule rests on — and on the one screen it matters most,
`store/queues.py:Queue.upsert` refuses to re-queue a position a human has cleared, so there
was no undo to cover anything. A single unmodified digit wrote a SKU onto a real card,
permanently, while mark-sold — which is reversible — had a photo to confirm against, a
two-step control and a twenty-second window. The reversible action carried three guards and
the irreversible one carried none.

**AND THE OTHER HALF OF THAT CORRECTION LANDED ON 2026-08-30 (D57), WHICH IS WHY THE SENTENCE
ABOVE IS PAST TENSE ON THE OWNER'S SCREEN.** D28 gave the irreversible action an undo and left
the reversible one carrying three guards, because taking a press off mark-sold was not what it
was asked to do. The owner asked for it directly: *"single tap immediately marks it as sold,
with the button changing to undo afterwards."* On `#/inventory` the sale writes on one press
now, and the way back is an `Undo` in the copy row plus the receipt that outlives it — which is
this rule as written, applied at last to the most reversible write in the product. The
photograph it used to confirm against is on the same screen, in the card band, at 449x627.
**`#/fulfillment` keeps all three guards**, and the table below still asserts its undo.

D28 fixes the premise rather than the rule: the review answer gets the same twenty-second
undo, and the candidate list stops moving between cards so the slip is rarer to begin with.

**Both halves are built as of 2026-08-23.** The layout half first (a measured 538px round-trip
under the finger became zero), then the undo: the answer route goes both ways with an `undo`
flag exactly as mark-sold does, `restores_to` is read off the card inside the lock before the
overwrite, and the screen draws a per-answer receipt with `U` on the newest. **The receipt is
not the "acknowledgement to dismiss" this rule bans** — it demands nothing, blocks nothing,
expires by itself at twenty seconds, and answering the next card never waits on it. What the
rule banned was a step between the operator and the next card; the receipt is a way back that
sits beside the flow rather than in it.

One inherited limit, recorded where a future reader will wonder: **the sixteen Gate B answers
predate the route logging `restores_to`, so they are not reversible** — an undo on any of them
refuses `answer_origin_unknown` rather than guessing. The window exists for answers written
from 2026-08-23 on.
**A confirm dialog was considered and refused again** — one key per card is the property this
rule exists to protect, and requiring a modifier or an Enter would have doubled the keystrokes
on the screen the owner spends the most hours in. Genuinely destructive actions may still gate — but per the
table below, none of those are reachable from the Fulfillment view at all.

**Capture undo is the stated exception, and it gets no dialog either** (settled 2026-08-13).
D10 makes undo a hard delete of the record, the sidecar and the photo, with no backup — so
it is simultaneously the remedy this rule relies on and the one irreversible action in the
app. Those two facts point opposite ways and the ruling is: one tap, no dialog.

The reasoning matters more than the ruling, because the reasoning is what stops a later
session from "fixing" it. **The deleted photo is of a card that is still physically in your
hand**, so the remedy for a wrong undo is to photograph it again. That bounds the loss in a
way a wrong pull or a wrong sale is not bounded, and the "genuinely destructive actions may
still gate" clause above is about those. A dialog on the screen the owner spends the most
hours in would also make the common case — one blurry photo, caught instantly — cost two
actions, which is the thing this whole rule exists to prevent.

Rejected and worth naming: confirming only on a *second consecutive* undo, which protects
against a held key walking backwards through good cards at the cost of one more state to
explain. If that ever happens in practice, it is the fix to reach for first.

**THE CONTROL IS A STACK OF TEN SINCE 2026-08-29 (owner, D10), AND THE NO-DIALOG RULE SURVIVES
IT BY DRAWING A NUMBER.** The capture screen lists the session's ten most recent captures into
the current box, newest first, each row its own control: `U` and the trigger still mean the
top one, and row N undoes N — that card and everything captured after it. The exception above
is argued for ONE card, on the ground that its photograph is of a card still within reach of
the hand that fed it, and that argument does not stretch to five. What replaces it is not a
confirm but a number: every row draws how many cards its press removes, before the press, so
the thing a dialog would have said afterwards is on screen beforehand. It is the same
instrument D33's money gate uses — make the number impossible not to have seen — at a much
smaller register.

This says nothing about the Fulfiller's undo on mark-sold, which is a different control
with its own row in the table below.

**Deliberately not banned, so that no later session reinstates these as rules from an
earlier draft of this file:** card-grid layouts, drop shadows and gradients were each
offered as blanket negative constraints and each declined — and the first two are now in
the product on purpose. Separation is `--bn-line` where a hairline is enough and
`--bn-shadow-1` to `-3` where a thing sits over another thing, which is a positive spec and
what a later session should argue with; the elevation set exists because a 1px hairline
separates nothing on a dark page. What is still refused is the panel header strip: a tinted
bar carrying each panel's name and queue depth was built, looked at, and rejected. Do not
add one, and do not write a rule about it either.

## The review queue — BUILT 2026-08-13. Description, except where marked.

**This section specified a screen that now exists, and reads as a description of it.**
`app/src/ReviewQueue.tsx` and `app/src/ReviewQueue.css` render it at `#/review`.

**WHAT WAS RE-CHECKED AGAINST THE TREE ON 2026-09-03, WHEN THE FRONT END WAS REBUILT, AND WHAT
WAS NOT.** Re-checked and repaired: the token names this section used to quote, the reason-code
vocabulary, the price-band citations, and the photograph's cap variable. Read as still true and
NOT re-measured: every pixel figure below, all of which were taken at 1440x900 against a
populated queue before the rebuild, on a screen this checkout's empty store cannot draw (D43).
A session that opens this screen over a real queue should re-measure them and say so here. Read every
statement below as *does* and hold it against the screen — one card at a time, photo first,
photo beside the choices above 900px; the sentence; the candidate rows with their keys; the human label over the
machine string; a type scale that steps down with the price and a parked row dimmed rather
than merely lower. The old header said "NONE OF THIS IS BUILT" and told you to read every
line as *shall*; it survived the screen by one commit, which is exactly the drift it was
written to prevent, pointing the other way.

**Built met a real queue at Gate B (2026-08-22), and this paragraph previously said it
never had.** The run put real entries in both queue files, the owner answered 16 of them
on this screen through the answer route, and the §10.2 measurements were taken —
the gates corpus's `GateB` record holds them. What that run could *not* test is the one
number called out below: its queue was uniformly sub-threshold commons, so the
price-banded type hierarchy has still never seen the mixed-value list it was designed
for. The rest of this section now describes a screen that has done its job once.

**What is still written forward, each marked where it stands rather than only here**: the
price band edges the type scale cuts on, the reason labels, and Skip — a control this
section never specified and which is recorded below as an open question rather than
retrofitted into a decision. One paragraph also records where the built screen deliberately
stops short of what this section asks: keys are drawn on the first nine candidates only.

The hardest screen in the product and the one the owner spends hours in, so its shape is
part of the design and not left to step 7.

**One card at a time, photo first — with one narrow exception since D29.** A
queue where every entry shares a reason code AND offers the same single candidate may be
answered as a group. Gate B is the evidence D4 did not have: 16 of 53 entries, every one the
same reason, detection agreeing with itself across every duplicate pair — one systematic fact
about the rig's lighting, sixteen identical taps. Anything looser stays one card at a time,
because a bulk write over cards a human has not compared is exactly what D4 exists to prevent.

**The group confirm (D29, built 2026-08-23) is this screen's one solid fill, and the fill
rule survives it**: the fill means "exactly one thing to do", and D29's eligibility — one
shared reason, one candidate per card, one condition — is precisely what reduces the state to
one action, so there is no second answer for the fill to be biased against. Reason chips in
the rail filter the worklist; `G` opens the group
offer, Enter confirms over the grid of photographs — the grid IS the confirmation — and `U`
reverses the whole group.

Photo as large as the viewport allows, then one sentence naming what the system found, then
the candidate rows with their prices. Answering advances immediately.

**"NO LEFT/RIGHT SPLIT" WAS THIS SECTION'S RULE AND IS REVERSED ABOVE 900px, ON THE OWNER'S
APPROVAL OF 2026-08-24 AND ON A MEASUREMENT THIS FILE NEVER HAD.** The sentence that stood
here — *"No left/right split, so the same layout works on a laptop and a phone"* — bought one
layout for two devices, and the price is now known. Measured in a browser at 1440x900 against
a populated queue: the photograph draws **244x432, which is 8.1% of the viewport**, on the one
screen whose whole job is looking at a photograph; the candidate rows begin at y=721 and the
third is **cut off by the fold**; the pending worklist starts 234px below it; one card costs
**2,356px of scroll**; and **752px — 52% of the width — is empty** beside all of it.

**The empty column is not waste sitting next to a small photograph. It is the CAUSE of it.**
The photograph's height cap exists precisely because everything stacks in one column and the
sentence plus the first candidate must stay in view. Put the choices beside the photograph and
the cap stops having anything to buy.

**The phone keeps the single column, byte for byte.** The split is a desktop layout and
nothing below 900px is re-tuned — which is what preserves the half of the old rule that was
actually about the phone. What the old sentence got wrong was treating one layout for both as
free; it was being paid for by the laptop, in the currency this screen exists to spend.

**The height cap is REBASED, not retired.** Retiring it was the instruction and it is refused:
the cap is ONE variable that the photograph's `max-height` and the frame that reserves its
space both read, and *their being the same expression is what makes D28's reservation exact*.
Deleting the variable deletes the reservation. Its value moved from `48vh` to the height that
is actually left. **It is `--rv-photo-h` in `app/src/ReviewQueue.css` since the 2026-09
rebuild** — renamed with the sheet, still one variable, and re-based per breakpoint: the stage
width is derived FROM it (`* 0.5625`, a card's aspect) rather than beside it, which is the
same argument one register further on.

**"As large as the viewport allows" replaced "full width at the top" on 2026-08-13, after
building it.** Full column width is right on a phone and wrong on a laptop: a card is 63×88,
so at a 656px column it draws over 900px tall, and the sentence and the first candidate — the
two things you are comparing the photo *against* — fall off the screen. The first
implementation instead centred the image inside a full-width panel, which drew a correct
photograph beside an equal area of empty surface inside one border, and looked like a bug.

So the rule is a cap on **height**, with width free to bind first: on a phone the column is
narrow and the photo is genuinely full width; on a laptop the height cap keeps the sentence
and a candidate visible beneath it. The number is a judgement and lives in
`app/src/ReviewQueue.css` rather than here — what this section fixes is that the photo is the
largest thing on the screen and that what you compare it to stays in view with it. This is a
judging screen: the photograph has to be big enough to settle whether the foil matches the
toggle, which is the disagreement that put the card in this queue.

**Worked expensive-first — and the sentence that used to follow this one was already false
before the split touched it.** `store/queues.py:sort_key` gained a **starvation tier ahead of
price** on 2026-08-24: an entry past `STARVATION_DAYS` outranks every priced card, oldest
first, because an unpriced `no_catalog_row` has no market and sorted last *permanently* — box
2 left 47 entries queued, counted and unreachable. `bandOf` is price-only and cannot see that
tier, so the five type-size bands render a sort the queue no longer has.

**The bands were not retired, and this paragraph said they were.** Corrected 2026-08-25 after
reading the screen rather than this file, and re-derived on 2026-09-03 after the rebuild moved
every line: `bandOf` is live at `app/src/ReviewQueue.tsx:340`, applied as `data-band` on every
rail row at `:2239`, and the sizes are the only `font-size` those spans have
(`app/src/ReviewQueue.css:740-746`) — FOUR of the five bands, since `mid` deliberately sets
nothing and renders at the row's own size. The worklist was not
retired either — it BECAME the rail. So what is true is narrower and worse than a retirement:
**the five bands still render, and they render a sort the queue only partly has.** That is an
unrepaired mismatch, open as of today, not a completed removal. What DOES discharge "the
ordering is visible" alongside them is honest about the tier `bandOf` cannot see: the card head
carries how long this card has waited, and the rail's reason chips carry counts computed over
the whole queue. A band scale in answer order would render a price sort
the list does not have, which is the same bias this file rejects for the candidate rows.

**The band edges are still the one number on this screen nobody has measured, and Gate B is
why that sentence had to be rewritten rather than deleted.** They are marked as an
assumption at the place they are cut as well as here. They are multiples of D9's $0.40
threshold, so they follow it if it moves — the same instinct D9 applies to its own
sub-threshold bands — but the multiples are a guess at a price distribution that, as of
Gate B, still does not exist. Unpriced is deliberately not the bottom band:
`pipeline/routing.py` holds that no price is not a low price, so drawing it smallest would
teach the eye the opposite of what routing decided.

**The measurement was taken on 2026-08-22 and it came back degenerate.** §10.2 item 3 was
the named instrument and it fired: the whole run priced **$0.04 to $0.40, median ~$0.10**,
and the queue's spread matched the run's. Every card landed in one band, so the type scale
was never asked to separate anything. That is a real result and it is not the one this
paragraph needed — a distribution with no top cannot redraw edges that exist to distinguish
a $3 card from a $300 one. The measurement is therefore still owed, and it now has a
precondition rather than a pointer: **a mixed-value lot**, not merely another run. Recorded
this way because "§10.2 item 3 will redraw them" was true when written, has been executed,
and would otherwise read to the next session as still-pending work that is in fact already
spent.

**Accent does two jobs at two weights, and the heavy one has a rule.**

- *Outline and text weight* — the system is unsure. The reason chip, and each of the two
  conflicting claims in the sentence. This is the common case.
- *Solid fill* — there is exactly one thing to do. Pull-confirm, mark-sold.

**Read that second example as the FULFILLER's mark-sold since 2026-08-30 (D57).** His is a
`PullConfirm` and still carries the fill; the owner's writes on one press from a quiet row
control, and `#/inventory` draws no solid fill at all now that its confirm panel is gone. That is
this rule satisfied rather than bent — it says where a fill MAY go, never that a screen must have
one, and `#/runs` has drawn none since it existed.

**A screen with two answers gets no fill.** This is the rule, and it exists because every
alternative is biased. Filling the pricier candidate teaches the queue to drift toward
over-listing, against the whole point of `pipeline/variant.py` treating the capture toggle
as a claim worth preserving. Filling the toggle's answer is defensible on D3 grounds but
makes the fill mean two different things on two screens. Reserving it for single-action
screens means its meaning never has to be learned twice, and it is why the Fulfiller's
pull-confirm is the loudest thing he ever sees.

**The third fill in the product is the run panel's spend button** (D33, 2026-08-24; on
`#/runs` since D39), and it is listed here so a later session reading the rule does not find it
as an unexplained exception. `app/src/RunPanel.tsx` draws exactly one solid fill: the control
that starts a paid identification run. **The screen around it draws none** — `Runs.css` says so
in its own comment, because a box picker with thirteen chips is the definition of a screen with
more than one answer. It satisfies the rule literally rather than by argument — the
button **does not exist** until the free preflight has answered, and at the moment it is
drawn the card count and the estimate are on screen directly above it and the only remaining
action is to spend or not to. Every other control on that panel is an outline, including all
three free steps, because a free re-runnable step is never the only thing to do.

**Absent, not disabled, and that distinction is the load-bearing half.** A disabled button is
one attribute away from being pressable, and that attribute is what a later refactor removes
without noticing; an element that is not rendered has to be deliberately re-added.
`app/tests/run-panel.spec.ts` asserts the absence rather than the disablement for exactly
that reason.

**THE SAME SHAPE NOW GUARDS A CLAIM RATHER THAN AN INVOICE (D34, 2026-08-24), AND IT IS NOT A
THIRD FILL.** The listing-release control on the box header is an outline like every other
control in `BoxOps`, so the fill rule above is untouched — what it borrows is the *sequencing*:
a free `GET /boxes/<box>/listings` is fetched when the panel opens, and the button that asserts
"TCGplayer holds none of these" does not exist until that has answered. The reason is the one
this paragraph already gives, and the failure it was written against is on the record: the first
build reported which OTHER boxes a release reached in the receipt, i.e. after the write. The
plan now names the SKUs, the copy counts, the other boxes and whether the box will actually be
freed, above the control. `app/tests/inventory.spec.ts` asserts the absence, not the
disablement.

**The panel must say when a release will NOT free the box.** D34 budgets each SKU by the calling
box's own copies, so a shared SKU leaves a remainder and the delete goes on refusing — correct,
intended, and the one outcome a person reads as a broken gate if nothing says otherwise. That
sentence is drawn before the press and repeated in the receipt.

**The panel is NOT folded, and none of the Fulfillment floors reach it.** It is an owner
surface at the 4–16 end of the scale. This paragraph used to argue the fold on `BoxOps`'
measured grounds — ~250px, reached once a box, above the card detail on the screen whose
question is *where is this card* — and the owner overruled it: *"both box and run, i don't
want click in functionality, i want their buttons just there."* D33 carries the argument.

**What replaces the fold's saving is the panel's own MEASURE, and this sentence has now been
rewritten three times.** It first read *the ROW*: `.browse-boxrun` put the run panel and `BoxOps`
side by side at `1fr 1fr` beneath the card, so the pair cost one panel's height instead of two.
Then the pair stood in a third COLUMN beside the card, where it cost the card's column nothing at
all. Then the BOX left that column for the walk's, because the left column IS the box and the
panel was re-listing sections the walk already draws (D38).

**Then the column itself went (2026-08-26), and the reason is the one axis none of the three
rewrites had checked.** A grid row is as tall as its tallest cell, and this panel shared row 1 with
the card while the card's own copies were row 2 — so the copies began wherever the console ended:
y=938 with it closed and **y=1599 with a run picked**, 1039px of white below the card on a 2214px
page. The answer to *where is this card* was positioned by a panel about something else, at an
unbounded height. The panel became the last row of the content column, at the full width, drawing
**625px closed against 799** and **1143px open against 1461** — no code change, because 1024px
unwraps its head, its notes and its free steps.

**AND THEN THE PANEL LEFT THE SCREEN (D39, 2026-08-29), WHICH IS WHERE FOUR RELOCATIONS INSIDE
ONE ROUTE WERE ALWAYS HEADED.** The owner gave the pipeline `#/runs`. Every measurement above
stands as evidence about the days it was taken and none of it is rewritten; what it adds up to is
the finding — the tallest thing this product draws was being fitted into a column whose question
is *where is this card*, and each fix moved it somewhere that was better on one axis. What
remains here is `BoxRuns`: one row saying whether anything is running over this box, and the
control that hands the ticked selection over. **It must never become two rows**, for the reason
the whole sequence above documents.

**AND ON 2026-08-29 IT MOVED AGAIN, TO THE HEADER ROW, WHICH IS THIS FILE'S OWN RULE APPLIED TO
IT (D40).** The page-chrome section above says the title "shares a line with the screen's controls
and counts" and that "the first row of real content sits within 150px of the top of the viewport".
A box's run state and a link to `#/runs` are a count and a control, and in the content column that
line was missing this file's floor by 1014-1422px — its y was set by the copy count and by whether
the claims editor happened to be open, measured at 1164 on a six-copy card and 1572 on an
eleven-copy one. In the header it is at y=62 on every card, and the never-two-rows rule stops
being a promise and becomes structural: on a shared line it cannot wrap without moving the whole
page, so `BoxRuns.css` sets `flex-wrap: nowrap` there and says why.

**One rule of this section moved with it and one did not.** `#/runs` is a route of its own and
takes the kit's page chrome like every other owner screen — `.bn-page` and `PageHeader`, with the
scope and the controls on the title row — which is where the four published numbers this file
used to carry (16px, a 20px title, a one-line lede, first content inside 150px) went; see
"Layout, density, and the widths this was drawn at" above for what replaced them and what that
cost. The density paragraph below is unchanged and still describes the panel.

**The density this section describes is kept and is no longer forced.** Step titles at the
section rank rather than a second page title, and controls at the kit's own `--bn-control-h`
rather than a height this screen invents — all of it was right on its own terms, and none of it
was only a consequence of a 370px track.

**Nothing folds, which is the half the owner ruled on.** No disclosure, no cap, no internal
scroller; every step head and note draws in every state and the spend button is still absent
rather than disabled until its preflight has answered. What changed is reading order, and
`app/tests/run-panel.spec.ts` asserts the ruling as an absence — `<details>` and `<summary>` at
zero inside the panel — which is the one form of it no future relocation can quietly falsify.

**Reason codes: human label large, machine string small beneath it.** The pipeline defines
fifteen strings and the screen labels FOURTEEN of them — six from the variant ladder in
`pipeline/variant.py`
(`no_catalog_row`, `metadata_not_stocked`,
`detected_finish_not_stocked`, `ambiguous_no_signal`, `duplicate_condition`, and D23's
`rarity_claim_mismatch`, the stack claim contradicting every candidate row) and EIGHT from
routing in `pipeline/routing.py` (`low_confidence`, `no_position`, `identification_failed`,
`set_ambiguous`, `card_not_detected`, `no_market_data`, `name_disputed` — the name read off
the photograph matching none of the rows its number found, which is D23's cross-check run
backwards and the only signal that catches a confidently misread number — and D35's
`number_unread_name_matched` — the only reason the JOIN writes over a successful ladder
resolution, keeping that row so the entry offers exactly one candidate, which is what makes a
queue of them one D29 group. It is *not* the only reason sitting on a card the ladder resolved:
`low_confidence` and `no_market_data` do too, and the difference is that they reach
`routing.route` still resolved and are re-routed there, where this one arrives already
un-resolved). Showing only a friendly label
creates a second vocabulary that nothing audits — the drift D16 exists to catch — and
leaves no way to get from what you saw on screen to what the pipeline actually said.
Showing only the raw string is honest and unreadable. Both, at two sizes, costs one line of
chrome and keeps the string greppable across the screen, the run report and `review.json`.
**Owner-side only**: the Fulfillment banned-word list forbids this register entirely.

**The seventh ladder reason is retired, and its label is kept (owner, 2026-09-03).**
`metadata_detection_disagreement` — the finish toggle and the photograph reading each other's
opposite — was the most-fired reason this queue has ever seen, 16 of 53 at Gate B, and the
answer was the same catalog row either way. The owner dropped the question rather than the
data: `pipeline/variant.py` still defines the string, nothing on any screen asks about it, and
`app/src/reasons.ts` keeps the label in `RETIRED_REASON_LABELS`, read after the live map, so a
QUEUE ENTRY WRITTEN BEFORE THE RETIREMENT still renders a name rather than its machine string.
A code that ever comes back is live again by being moved back into the live map, not by
somebody remembering that list exists. The list above is the live vocabulary and this file's
half of the reconciliation `scripts/docs-audit.py`'s `reason codes` row performs.

**Twelve of the thirteen labelled reasons can reach this screen. `no_market_data` cannot, and
this paragraph used to say otherwise.** It is not a queue reason: `pipeline/routing.py` makes it the fourth
destination beside listed, main and parked, and `pipeline/join.py` writes a queue entry only
for `routing.MAIN` and `routing.PARKED` — so a card with a blank or $0.00 market cell is
priced by hand on `#/pricing` (`inventory/prices.json`, D9/D86) and never appears here. The screen carries a label
for it all the same, which is right: one line of a lookup table is cheaper than a bare
machine string rendered the first time routing ever queues one. The claim to keep out of
this file is the count — fourteen are defined, thirteen are labelled, twelve are reachable,
and the three numbers answer three different questions.

**Every choice shows its key, and the built screen draws nine of them.** Owner-side, an hour
in the queue is a keyboard and not a mouse, and the keyboard hint is what the
no-confirm-dialog decision looks like in the markup. The Fulfiller's screens are touch and
show none. Recorded as a deviation rather than folded into the sentence above:
`app/src/ReviewQueue.tsx` keys candidates on the digits, because the choice *is* a numbered
list and any other mapping is a second thing to learn — which stops at nine, since a tenth
needs a modifier or a two-key sequence. Rows past the ninth draw no chip rather than a chip
that does nothing. A card with ten candidate rows is rare enough that reaching for the mouse
is the right cost; a real queue full of them is the argument for reopening this.

**THE CAPTURE SCREEN STOPPED AT NINE ON THIS PARAGRAPH'S AUTHORITY AND NO LONGER DOES
(owner, 2026-08-24).** `app/src/CaptureScreen.tsx:Opt` cited the rule above in as many
words — rows past the ninth draw no chip rather than a chip that does nothing — and drew
Pokemon's last four rarities keyless: `Special Illustration Rare`, `Hyper Rare`, `Secret
Rare` and `Rainbow Rare` were mouse-only, on the screen the owner shoots a box from at a
623 ms cadence. `OPTION_KEYS` there is now digits, then `0`, then the letters that screen
has not already spent.

**What the borrowed rule got wrong is one clause: "a tenth needs a modifier or a two-key
sequence".** A tenth needs `0`, and an eleventh needs a letter, and both are one unmodified
press. That was worth an escape hatch on the review queue, where a candidate list is
per-card and a tenth row is rare; it was never worth four permanently unreachable rows in a
vocabulary `pipeline/games.py` authors by hand and the operator claims every stack.

**The review queue is deliberately NOT changed with it, so the two screens disagreeing is a
ruling rather than drift.** Its list is candidate catalog rows — variable per card, ordered
by the pipeline, and its digits are the numbered list they name. The capture screen's is a
fixed authored vocabulary in stack order, where position 11 is `Hyper Rare` on every card
of every run, so a letter there is learned once and not re-read per card. If a real queue
turns up full of ten-candidate cards, the paragraph above is still the one to reopen, and
`OPTION_KEYS` is then the thing to reach for rather than a second alphabet.

**The alphabet SKIPS rather than shadows, and that is the half a later session must not
tidy.** The capture screen has spent eleven letters: `b h r f g v o t` are its fields, and
`c u s` are its three ACTS — the shutter, the undo, and D10's divider. (It read *ten* between
2026-08-25 and 2026-08-29, and the count has been eleven, ten and eleven again for two
different reasons. `n` left when D20's amendment merged away the Box field's second input,
and `s` arrived when the owner asked for `S` to open a section and moved the set hint to `h`.
The two cancel exactly, and `h` sorts after `e`, so the option rows draw on the same letters
they always did — the first thirteen keys are `1234567890ade` through all three counts, which
is why `app/tests/capture-claims.spec.ts` stayed green across both changes.) A literal `a`–`z`
puts `Rainbow Rare` on `c`. Neither resolution
of that collision is safe: whichever act wins, the other looks like it fired, silently, one
card at a time. So the gaps at `b` and `c` are the design, and they cost nothing to read
because every row draws its own key in its chip. `app/tests/capture-claims.spec.ts` asserts
the skip — the negative case, because nothing in the type system or the render says it.

**The question below is closed as of 2026-08-25 — D37 is the decision entry it asked for.**
This section said the screen "needs a real defer that records a reason, and that is a decision
entry rather than a button", and named counting skips as the measurement that would settle it.
The owner asked for the defer directly instead: *"why can't i mark something as known skip
kinda like a stand down on the flag i get that this is a wasted position"*.

`X` now raises a panel offering a **stand-down** — three reasons, `cleared_by_human` set, and
the card itself untouched — beside D26's **retirement**, whose route existed with no control on
this screen. The mid-box delete is deliberately not there: it renumbers every card behind the
one being deleted, which would re-point the worklist the panel is drawn from, and it is the one
operation here with no undo. D37 carries the whole argument.

**THE ZERO-CANDIDATE CARD IS NO LONGER A DEAD END (D46, 2026-08-29), AND THE COPY THAT SAID IT
WAS IS GONE.** That arm of the screen drew one paragraph: the only move was to skip, and the way
out was a command in a terminal. Both halves had gone stale — D37 had put a stand-down on this
very screen and the copy never mentioned it, and the row the pipeline missed was usually sitting
in the export the whole time. The screen now looks the card up in the export it was joined
against, suggests on arrival from the card's own read, and offers a search by name, collector
number or SKU.

**Those rows go where the candidate rows go, and are answered on the same digits.** Not a panel
beneath them: nothing may come between the sentence and the rows, and these ARE the rows — found
by a lookup rather than by the join. One vocabulary, because whether the pipeline or the catalog
found a row is not something the finger needs to know. The search field is the one control on
this screen that takes typing, so it carries the kit's field boundary — `--bn-line-strong`, the
weight the token block reserves for something you type into, rather than the `--bn-line`
hairline that separates — and `isEditableTarget` is what stops a typed digit from answering the
card.

**Skip survives, narrowed and no longer load-bearing.** It is still the only move that writes
nothing, which is right for a card the owner intends to come back to this session; what it is
no longer is the ONLY move for a card that can never be answered. The paragraphs below are left
standing because their reasoning is what produced D37, and because the measurement they ask for
is still owed — the stand-down's recorded reason is now the instrument that takes it.

**Skip is an OPEN QUESTION, not a decision.** The built screen carries a control this section
never asked for: Skip, on `S`, which moves the current card to the back of this session's
worklist. The owner never chose it, so it is recorded here as a question rather than left
undocumented on the screen this file specifies hardest — and recorded as a question rather
than written up as a decision, because inventing the owner's reasoning after the fact is how
a build's convenience becomes a settled rule nobody argued for.

It exists because two kinds of card cannot be answered at all, and without a way past them
the queue stops dead on the first one. An entry with no candidate rows is refused by
`POST /review/<box>/<index>/answer` as `no_candidates` — it needs another photograph or
another identification run, not an answer. And a card the owner is not ready to rule on has
no other move, because the only write this screen can make is final:
`store/queues.py:Queue.upsert` refuses to re-queue a position a human has cleared,
deliberately, so that an answer outlives the question.

Skipping writes nothing — the entry stays open in its file, the run report still counts it,
and a reload forgets every skip. That is the half worth defending: a skip that persisted
would be a third state between open and answered, the same tombstone shape D10 refuses for
undo, and it would have to be cleared by something.

**Gate B was named as what settles this and it did not settle it — the measurement was
missed, not taken.** §10.2 item 1 asked for queue depth and got it (16 of 53), but nothing
recorded how many of those 16 were skipped before being answered, and the owner answered all
16 in one sitting. So the control is exactly as unsettled as it was, minus one opportunity.
Written down rather than left pointing at a gate that has passed: the next real queue
session is the instrument, and **counting skips has to be decided on before it rather than
noticed afterwards**, which is the mistake this paragraph is a record of. If nothing is ever
skipped, delete the control. If most of a queue is, the screen needs a real defer that
records a reason, and that is a decision entry rather than a button.

**Mono carries all metadata.** Reason codes, set and collector number, age, counts,
positions and prices are utility face, uppercase, tracked. The body face is reserved for
sentences a human reads. This one rule does more than any other to keep the thing from
reading as a newspaper.

## Fulfillment view — hard constraints, assert these in a test

The agent cannot see its own output, so these are Playwright assertions, not prose.

**All ten rows run, against the view itself, and every one was re-checked against the tree
on 2026-09-03.** `app/tests/fulfillment.spec.ts` asserts every row of the table below on the
Fulfillment view; `app/tests/pull-confirm.spec.ts` keeps three of them on the kit's
pull-confirm. `make design-check` runs both. Every contrast ratio is computed from the
*rendered* colors rather than compared against a number published here, so a token edited in
`app/src/tokens.css` without being re-argued in this file has to break something — which is
the only reason the Banchi palette could be swapped underneath this view at all.

**The assertion count was published here and is not any more.** It read "30 assertions,
observed passing 2026-08-13" and was still saying 30 when the suite had grown to 64 — restated
wrongly in five files at once. D18's test decides it: a count is verifiable and there is
nothing in it a later session could reasonably disagree with, so it is not load-bearing prose
and the honest fix is to stop publishing it rather than to keep it fresh. `npx playwright test`
owns the number. The two places `docs/GATES.md` still says "16 of 30" and "30 of 30" are
deliberately left alone — they sit inside a dated account of the hours 7b shipped unwired, and
renumbering evidence to match a later tree is the one thing a record may never do.

The spec asserts the view is on screen before it measures anything, and that is not defensive
padding: it is what caught 7b shipping unwired, failing 16 of 30 on an unregistered route
rather than reporting nine confident measurements of whatever Vite serves for a hash it does
not recognize.

Two things this does not cover. The requirement under the table rather than in it — D5's "if
a flow needs explaining twice, redesign the flow" — has no instrument but the Fulfiller
filling a real order, and no order has been pulled. And none of this is a harness test: the
contract in `docs/GATES.md` is nine Python tests run at turn end, and this runs a browser.

| Constraint | Assertion |
|---|---|
| Body text | `font-size >= 20px` on every text node in the view |
| Body color | every text run, against its OWN rendered ground — this is measured per run now and is no longer a property the palette guarantees globally (see "Light and dark are both first class") |
| Position label | `font-size >= 32px`, tabular figures |
| Card photograph | `>= 320px` on the short edge, at desktop and at phone width |
| Tap targets | `>= 44 x 44 px`, `>= 12px` apart |
| Contrast | `>= 7:1` for body text (WCAG AAA — assume reading glasses and a bright room) |
| Destructive actions | zero reachable from this view; assert no route to settings or import |
| Undo | present on every mark-sold, `>= 10s` window |
| Two-step pull | the sale control may occupy no part of the pull control's footprint, and begins below where it ended |
| Jargon | copy passes a banned-word list: SKU, CSV, import, sync, batch, queue, staged |

**The numbers in that table are the spec's own constants** — `BODY_FLOOR` 20, `PLACE_FLOOR`
32, `PHOTO_FLOOR` 320, `TARGET_FLOOR` 44, `GAP_FLOOR` 12, `CONTRAST_FLOOR` 7,
`UNDO_FLOOR_MS` 10_000 — and the spec runs the photograph and the floors at two viewports,
1280x900 and 375x812. The built undo window is 20 seconds, twice the floor, and it is the
same number `#/inventory` and `#/orders` use.

**Two of those floors were broken by the rebuild and fixed in the same session, and both
failures were geometry rather than color.**

- **The photograph's column is 320px, NOT 300.** `app/src/Fulfillment.css` had it at
  `minmax(0, 300px)` above 768px, chosen so the text column would end near the photograph's
  foot. It bought that tidiness by painting the one thing he checks before pulling 20px under
  the floor in the table above. The tidiness is not a trade this view is allowed to make.
- **The action block reserves 152px — 64 + 24 + 64 — from the start, and grows downward.**
  It holds one 64px control before the pull and two after it, the acknowledgement and the
  sale, `--bn-6` apart. Left to size itself it grew by 88px on the press, the grid re-laid
  out around the taller block, and the whole block travelled UP the page: measured at 768px
  and above, `Pull` at {624, 920, 356x64} and `Mark it sold` at {624, 926, 356x64} — six
  pixels apart with identical heights, so the second control landed on the first one's
  rectangle. A finger that pressed twice, which is the ordinary response to a button that
  did not seem to react, SOLD THE CARD. Anchoring alone does not fix it, because the movement
  came from the block changing size: reserving both steps means the block is the same size
  before and after, nothing reflows, and the sale can only ever appear below the
  acknowledgement. `align-self: start` is the other half — the wide-screen rule sets the
  block's row and must never set `end`. This is the displacement guard the two-step exists to
  be, defeated by geometry rather than by logic, and the table's "Two-step pull" row is what
  now catches it.

Default view on the Fulfiller's device. Sorted in box-walk order. Photo-confirm before each
pull. One-tap mark-sold.

**"One-tap mark-sold" has been the written spec since this file existed and the OWNER's screen
only became it on 2026-08-30 (D57).** Recorded here rather than left as a coincidence, because
the sentence reads as a Fulfilment-only line and is not: it is this section's own no-confirm
rule stated for the write it applies to hardest. His view reaches it by a different road — his
one tap is the SECOND step, after `Pull`, and the two are measured apart in
`app/tests/fulfillment.spec.ts` because a double-tap once sold a card whose photo he never saw.
That two-step is not the confirm dialog the rule bans; it is a displacement guard, and it stays.

## The pull-confirm — the one control that is purely his

Step 6 locked a palette on 2026-08-12 and built one component against it, on the argument
that catching a gap on one component is far cheaper than after ten screens. The palette is
gone and the component is not: `app/src/PullConfirm.tsx` and `app/src/PullConfirm.css` are
still the Fulfiller's pull button, still the only solid fill he ever sees, and still the
thing `app/tests/pull-confirm.spec.ts` measures on `#/gallery`. What it is built against
now:

```
fill        --bn-accent-press in light, --bn-accent-hover in dark
            — the one accent step that clears 7:1 under --bn-on-accent in each theme (8.1:1)
label       --bn-on-accent, 22px, weight 700, the UI face
box         min-height 64px, min-width 44px, radius 16px, --bn-shadow-2 + --bn-shadow-accent
hover       lift 1px, shadow to --bn-shadow-3. The color does not move.
pressed     translateY(1px) scale(.985), brightness .92 in light / 1.08 in dark
disabled    owner-side only; this view has no disabled state at all
```

**Hover and press change the shadow, the lift and the brightness — never the color.** That
is what makes the measured ratio the ratio on screen in every state, which is the property
the spec depends on: it computes the contrast from the rendered fill of each specimen rather
than from a number published here. `--pc-on` is the only ink in the file, so the key hint's
border is drawn from it and follows it through both themes.

**Both findings from building it before any screen still hold, and both are now enforced
rather than remembered.** The label had to be 20px or more because the constraints table puts
that floor on every text node in his view and a button label is a text node — it is 22px, and
the spec asserts the floor. And the key chip does not belong on this control: "every choice
shows its key" is an owner-side rule, `keyHint` renders nothing when omitted, and the spec
asserts its absence by default.

**`docs/design-refs/locked.html` and `rejected.html` draw the 2026-08-12 palette and no
longer draw this product.** They are a record of that interview — the two findings above were
found by disagreeing with them — and they are not a reference for anything built today. The
reference is `#/gallery`.

## The screenshot loop is mandatory

`make screenshot` renders the key views to `captures/ui/`. Claude Code writes CSS it has
never looked at, so a layout that is technically correct can still be broken. Every UI
change: render, screenshot, compare against the reference and the table above, fix, repeat.
Two or three rounds gets to a production layout; zero rounds gets the generic default.

Give it a real visual reference before it codes. An adjective like "clean" produces the
average of everything the model has seen. A screenshot produces something specific — which
is why the tokens above are hex values and typeface names rather than words like "warm" or
"technical", and why they were chosen against a rendered card rather than described.

**The reference is `#/gallery`, and it is in the build for this reason.** A component sheet
that the app renders is a component sheet that cannot go stale — which is exactly what
happened to `docs/design-refs/locked.html`, a static drawing of a palette this product no
longer has. Hex values substitute for color; they do not substitute for layout or density,
and those are most of what a reference carries, which is why the kit page draws every
primitive in every state rather than listing their names.

**The gallery is not a substitute for looking at a real screen over a real store.** The
rebuild was walked at 390, 820 and 1440 in both themes, and this checkout's store is empty
(D43) — so a disabled control, a long box name and a seven-copy card are states no worktree
can render for you. That is how the two Fulfillment floors above were broken and found: by
pressing the buttons at 1280 with a card on screen.

## Copy rules

Active voice. The button says exactly what happens. An action keeps its name through the
whole flow: the button that says "Pull" produces a confirmation that says "Pulled."
Name things by what the Fulfiller controls, never by how the system is built — he has
orders and cards, not SKUs and rows. Errors say what happened and what to do next.

The owner's screens are the exception and only the exception: there, the pipeline's own
reason strings are shown verbatim beneath their labels, because being able to grep what you
saw is worth more to the person debugging a run than a consistent register is.

Mechanized past the reason-string exception: `scripts/docs-audit.py`'s `no mechanism on
screen` row (D196) refuses a decision citation, a repository path, or a
pipeline-internal noun in any other user-visible string in `app/src`.

Less text is always better than more, and it is a ratchet rather than an opinion: a route's
visible word count may only go down. Mechanized by `app/tests/copy-budget.spec.ts`
(D194), run by `make design-check`, against the ceilings pinned in
`app/tests/copy-budget.json`.
