import { useEffect, useRef, useState, type ReactNode } from 'react'

import type { Place, SearchGroup, SectionDetail } from './types'
import { PullConfirm } from './PullConfirm'
import { PositionBar } from './PositionBar'
import { PositionLabel } from './PositionLabel'
import { SearchField } from './SearchField'
import { CardLocations } from './CardLocations'
import { Button, EmptyState, Icon, Kbd, Lockup, Logo, Notice, Pill, Segmented, Stat, VARIANTS as LOGO_VARIANTS, type ButtonSize, type ButtonVariant, type IconName, type PillTone } from './kit'
import { MARKS } from './kit/markPalettes'
import { ICON_NAMES } from './kit/Icon'
import './Gallery.css'

/* THE KIT — every primitive Banchi is built from, on one page, so the tokens are looked at
 * rather than only written. `make screenshot` renders it and `make design-check` measures the
 * Fulfillment floors here. Nothing is wired to a server.
 *
 * THAT LAST SENTENCE WAS FALSE FOR THE ONE THING ON THIS PAGE MADE OF PIXELS, until 2026-09-06.
 * `CardLocations`'s Fulfiller skin draws an `<img>` per photo-bearing copy, and its source was
 * `photoUrl(box, index)` — so the sheet fetched whatever was in boxes 3, 4 and 7 of whichever
 * store answered the capture port, and showed different cards as those boxes changed. Two costs,
 * and the second is the serious one: the page whose entire purpose is being compared against a
 * reference (docs/DESIGN.md's mandatory loop) was the page nobody could reproduce, and a pooled
 * capture is a code card whose photograph is a bearer instrument (D24) that `make screenshot`
 * would have written into `captures/ui/`. `GET /photo/<box>/<index>` serves stored bytes and
 * does not know a code card from a Thievul; nothing filters it here.
 *
 * SO THE SHEET BRINGS ITS OWN IMAGE — `SPECIMEN_PHOTO` below, through `CardLocations`'s
 * `photoSrc` seam, which no screen in the product passes. What was NOT done is the one-line
 * version: setting `has_photo: false` on the four fixtures buys a closed sheet by deleting the
 * photo-bearing shell from the page whose job is to draw every shell, and
 * `app/tests/gallery.spec.ts` exists to refuse exactly that trade for the departed and pooled
 * rows. Both photo shells are still drawn here: four copies carry an image, two carry the
 * missing-photo sentence.
 *
 * The four pull-confirm specimens keep their `data-specimen` names and their order:
 * app/tests/pull-confirm.spec.ts measures the vertical gaps between exactly those. */

const noop = () => {}

// ---------------------------------------------------------------------------- fixtures

/* EVERY OVERRIDE THAT MOVES `index` MUST MOVE `slot` TOO, and three of them did not until
   2026-09-05. `slot` is the numerator of `#N of M` (D58) and `index` is the store key; the base
   below is internally consistent (card 40 is the 15th card of a section starting at 26), so an
   override setting `index: 12` and leaving `slot` alone drew `Box 7 · Section 1 · Card 12`
   over the caption `#40 of 62` — an impossible card, on the one sheet whose entire purpose is
   being looked at. Each fixture's `fraction` is what says which number is right. */
function place(over: Partial<Place>): Place {
  return {
    label: 'Box 3 · Section 2 · Card 15',
    box: 3,
    index: 40,
    slot: 40,
    section: 2,
    card: 15,
    box_name: 'ME01 commons',
    section_start: 26,
    section_end: 50,
    box_total: 250,
    box_closed: true,
    fraction: 0.16,
    ...over,
  }
}

const CLOSED_BOX = place({})
const OPEN_BOX = place({ label: 'Box 7 · Section 1 · Card 12', box: 7, index: 12, slot: 12, section: 1, card: 12, box_name: null, section_start: 1, section_end: null, box_total: 62, box_closed: false, fraction: 12 / 62 })
const SINGLE_SECTION = place({ label: 'Box 9 · Section 1 · Card 4', box: 9, index: 4, slot: 4, section: 1, card: 4, box_name: 'Bulk, unsorted', section_start: 1, section_end: null, box_total: 80, box_closed: true, fraction: 0.05 })
const NO_FRACTION = place({ label: 'Box 4 · Section 1 · Card 1', box: 4, index: 1, slot: 1, section: 1, card: 1, box_name: null, section_start: 1, section_end: null, box_total: 0, box_closed: false, fraction: null })
/* A COPY THAT HAS LEFT ITS BOX (D58, D68, D71), which is a ROW SHAPE and not a variation on a
   located one: `slot`, `section` and `card` are all null, because a card that has left is in no
   slot, and `join.departed_label` is what the server sends where a position label would be — the
   box it belongs to, the word, and the store key, since two departed copies of one card in one
   box were otherwise the identical string.
   `server.ts:isDeparted` reads the NULL SLOT BESIDE A REAL LABEL, so handing this fixture a
   numeric slot turns the departed row back into an ordinary one and the shell it draws
   (`is-gone is-nobar`) stops being rendered anywhere on this sheet — which is exactly what
   `app/tests/gallery.spec.ts` is here to refuse. */
const DEPARTED = place({ label: 'Box 3 · departed · B3 #31', box: 3, index: 31, slot: null, section: null, card: null, fraction: null })
/* A POOLED COPY (D24): a count, not a location. `located: false` is the whole of it — the block
   carries no label at all, so the row draws the game's own name where a position would be and
   `pooled · <key>` under it. A different game from every other fixture here on purpose: the
   pooled shape only ever arrives on a game whose registry entry says it is unlocated. */
const POOLED = place({ located: false, label: null, game: 'pokemon_code', game_display: 'Pokémon code cards', box: 12, index: 5, slot: null, section: null, card: null, box_name: null, section_start: 1, section_end: null, box_total: 0, box_closed: false, fraction: null })

/* BOX 3'S REAL TILING, so the two depth specimens below draw a strip of four chips rather than
   the three runs `spansOf` synthesises from a `Place` alone. `CLOSED_BOX` is card 40, the 15th
   of section 2 (26..50); `DEPARTED` left that same section. Named apart from this file's own
   `SECTIONS` nav table, which is a list of anchors and not of dividers. */
const BOX_SECTIONS: SectionDetail[] = [
  { section: 1, start: 1, end: 25, count: 25, name: null },
  { section: 2, start: 26, end: 50, count: 25, name: 'Rares' },
  { section: 3, start: 51, end: 120, count: 70, name: null },
  { section: 4, start: 121, end: 250, count: 130, name: null },
]

const GROUP: SearchGroup = {
  sku: '8421991',
  names: ['Thievul'],
  number: '108',
  printed_total: '198',
  number_display: '108/198',
  set_hint: 'me01',
  set: 'ME01: Mega Evolution',
  rarity: 'Rare',
  condition: 'Near Mint',
  listed: { pushed: 0, staged: 1, live: 2 },
  sold_here: 0,
  live_as_of: null,
  /* Four of the six copies below have not left by either door, and `listable` is the server's
     own `min(cap, on_hand)` — both move with the copies list rather than being typed beside it,
     so the header's figures and the rows it sits over cannot disagree on a sheet whose whole
     purpose is being looked at. */
  on_hand: 4,
  listable: 4,
  /* `capture_id` ON EVERY ROW BUT ONE, and the null is the specimen (D93): a record written
     before ids were kept cannot be aimed at, so the order walk draws a reason where the take
     would be. A gallery whose every copy carried one would never show that row. */
  copies: [
    { key: '3/40', state: 'identified', state_at: null, has_photo: true, capture_id: 'cap-3-40', place: CLOSED_BOX },
    { key: '7/12', state: 'identified', state_at: null, has_photo: true, capture_id: 'cap-7-12', place: OPEN_BOX },
    { key: '9/4', state: 'captured', state_at: null, has_photo: false, capture_id: null, place: SINGLE_SECTION },
    { key: '4/1', state: 'sold', state_at: null, has_photo: true, capture_id: 'cap-4-1', place: NO_FRACTION },
    { key: '3/31', state: 'sold', state_at: null, has_photo: true, capture_id: 'cap-3-31', place: DEPARTED },
    /* NO PHOTOGRAPH ON THE POOLED ROW, AND IT IS THE PRODUCT'S SHAPE RATHER THAN A MISSING
       FIXTURE. The opsec half of this reason moved on 2026-09-06 and is recorded rather than
       deleted: while the sheet drew `photoUrl`, a photographed pooled fixture would have put a
       live code card into `captures/ui/`, and that is now impossible for every row here at
       once — the image is `SPECIMEN_PHOTO` and the store is not asked. What is left is the
       reason that was always the stronger one: `app/tests/fulfillment.spec.ts` asserts a pooled
       card is never on the Fulfiller's screen at all, so a photographed pooled copy is a shape
       this product does not produce. The missing-photo sentence it draws instead is a real
       state. */
    { key: '12/5', state: 'identified', state_at: null, has_photo: false, capture_id: 'cap-12-5', place: POOLED },
  ],
}

/* A SKU-LESS GROUP, WHICH IS TWO REAL SHAPES AT ONCE (D119): the bag `do_search` returns for
   cards that matched a query and carry no SKU, and the one-copy group `Inventory.tsx:loneGroup`
   builds locally for a card the search cannot reach at all. Both draw a header with no live
   figure and no counts line, because `emit` has not written a listing record and every listing
   number would be a structural zero. `listable` is 1 and stays 1 — the server's own answer —
   which is why the SENTENCE is what the header drops rather than the figure.

   DELIBERATELY NO `currentKey`: `app/tests/gallery.spec.ts` counts `is-nobar` and `is-current`
   rows PAGE-WIDE, and its own comment argues that page-wide is the stronger claim. A located,
   non-departed, non-pooled, non-current copy adds to none of those counters. */
const LOOSE_GROUP: SearchGroup = {
  sku: null,
  names: [],
  number: null,
  printed_total: null,
  number_display: null,
  set_hint: null,
  set: null,
  rarity: null,
  condition: null,
  listed: { pushed: 0, staged: 0, live: 0 },
  sold_here: 0,
  live_as_of: null,
  on_hand: 1,
  listable: 1,
  copies: [
    { key: '5/9', state: 'captured', state_at: null, has_photo: true, capture_id: 'cap-5-9', place: OPEN_BOX },
  ],
}

/* THE SPECIMEN PHOTOGRAPH, and it is a drawing rather than a photograph on purpose.
 *
 * WHY IT IS BUNDLED: a data URI is a closed system — no origin, no port, no store, no server
 * that has to be up. `make screenshot` renders this page against `make dev` alone, and the
 * render is the same bytes in every checkout on every day, which is what makes comparing it
 * against `docs/design-refs/` the loop docs/DESIGN.md calls mandatory rather than a coin toss.
 *
 * WHY 9:16 AND NOT CARD-SHAPED: 2160x3840 is the rig's stored aspect, the same reasoning
 * `app/tests/review.spec.ts` states over its own fixture. `.card-locations-fulfiller
 * .card-locations-photo` is `aspect-ratio: 63/88` with `object-fit: cover`, so a real capture
 * is cropped to its middle 78.5% vertically and a card-shaped source would quietly show a crop
 * the product never performs. Everything drawn below sits inside that band.
 *
 * WHY IT NAMES ITS OWN COLORS. `tokens.css` is the only file in `app/` that may name one, and
 * this is the same exception `app/src/kit/markPalettes.ts` argues at D102: these are an
 * ILLUSTRATION's colors, not the interface's, and they must not follow the theme — the photo
 * sits on `--bn-stage-*` ground that is dark in light and dark alike, because the subject is a
 * photograph. `make docs-audit`'s `raw color` row cannot see it either way; its scope is
 * `app/src/*.css` and this is a `.ts` expression.
 *
 * AND WHY IT SAYS SO IN WORDS: a render of this page ends up in `captures/ui/`, and the one
 * thing a reader of that file must never have to wonder is whether they are looking at a real
 * card out of a real box. */
const SPECIMEN_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="2160" height="3840" viewBox="0 0 1080 1920">' +
  // The stand. `--bn-stage-bg-2`'s value, so the ground under this card is the same family the
  // product's own viewfinders and photo heroes are drawn on.
  '<rect width="1080" height="1920" fill="#171b25"/>' +
  // The card, at 63:88, inside the middle band `object-fit: cover` keeps.
  '<rect x="90" y="331" width="900" height="1257" rx="44" fill="#d7dae1" stroke="#aab0bd" stroke-width="6"/>' +
  '<rect x="134" y="375" width="812" height="1169" rx="26" fill="none" stroke="#b8bec9" stroke-width="5"/>' +
  '<rect x="186" y="427" width="708" height="86" rx="18" fill="#c3c8d2"/>' +
  '<rect x="186" y="551" width="708" height="668" rx="18" fill="#6f7f99"/>' +
  '<rect x="186" y="1257" width="708" height="58" rx="14" fill="#c3c8d2"/>' +
  '<rect x="186" y="1349" width="470" height="58" rx="14" fill="#c3c8d2"/>' +
  '<text x="540" y="915" text-anchor="middle" font-family="monospace" font-size="88" ' +
  'letter-spacing="10" fill="#eef0f4">SPECIMEN</text>' +
  '</svg>'

/** `encodeURIComponent` rather than base64, so the drawing above stays readable and editable in
 *  this file — a base64 blob is a color nobody can see and a rectangle nobody can move. */
const SPECIMEN_PHOTO = `data:image/svg+xml;utf8,${encodeURIComponent(SPECIMEN_SVG)}`

const SECTIONS: readonly { id: string; label: string; group: string }[] = [
  { id: 'color', label: 'Color', group: 'Foundations' },
  { id: 'type', label: 'Type', group: 'Foundations' },
  { id: 'space', label: 'Space & radius', group: 'Foundations' },
  { id: 'elevation', label: 'Elevation', group: 'Foundations' },
  { id: 'motion', label: 'Motion', group: 'Foundations' },
  { id: 'icons', label: 'Icons', group: 'Foundations' },
  { id: 'buttons', label: 'Buttons', group: 'Primitives' },
  { id: 'kbd', label: 'Keycaps', group: 'Primitives' },
  { id: 'pills', label: 'Pills & dots', group: 'Primitives' },
  { id: 'fields', label: 'Fields', group: 'Primitives' },
  { id: 'segmented', label: 'Segmented & tabs', group: 'Primitives' },
  { id: 'notice', label: 'Notice', group: 'Primitives' },
  { id: 'receipt', label: 'Receipt & toast', group: 'Primitives' },
  { id: 'empty', label: 'Empty state', group: 'Primitives' },
  { id: 'skeleton', label: 'Skeleton & progress', group: 'Primitives' },
  { id: 'data', label: 'Data', group: 'Primitives' },
  { id: 'surfaces', label: 'Surfaces & menu', group: 'Primitives' },
  { id: 'pull-confirm', label: 'Pull-confirm', group: 'Screen pieces' },
  { id: 'position', label: 'Position bar', group: 'Screen pieces' },
  { id: 'position-label', label: 'Position label', group: 'Screen pieces' },
  { id: 'search', label: 'Search field', group: 'Screen pieces' },
  { id: 'locations', label: 'Card locations', group: 'Screen pieces' },
]

const COLORS: readonly { name: string; token: string; ink?: boolean }[] = [
  { name: 'Page', token: '--bn-bg' },
  { name: 'Surface', token: '--bn-surface' },
  { name: 'Surface 2 · sunken', token: '--bn-surface-2' },
  { name: 'Surface 3 · hover', token: '--bn-surface-3' },
  { name: 'Ink', token: '--bn-ink', ink: true },
  { name: 'Ink 2', token: '--bn-ink-2', ink: true },
  { name: 'Ink 3', token: '--bn-ink-3', ink: true },
  { name: 'Ink 4', token: '--bn-ink-4', ink: true },
  { name: 'Line', token: '--bn-line' },
  { name: 'Line strong', token: '--bn-line-strong' },
  { name: 'Accent', token: '--bn-accent', ink: true },
  { name: 'Accent hover', token: '--bn-accent-hover', ink: true },
  { name: 'Accent press', token: '--bn-accent-press', ink: true },
  { name: 'Accent tint', token: '--bn-accent-tint' },
  { name: 'Live', token: '--bn-live', ink: true },
  { name: 'Live tint', token: '--bn-live-tint' },
  { name: 'OK', token: '--bn-ok', ink: true },
  { name: 'OK tint', token: '--bn-ok-tint' },
  { name: 'Warn', token: '--bn-warn', ink: true },
  { name: 'Warn tint', token: '--bn-warn-tint' },
  { name: 'Danger', token: '--bn-danger', ink: true },
  { name: 'Danger tint', token: '--bn-danger-tint' },
]

/* The text roles: one specimen each, named and labelled with the class that gives it. */
const TEXT_ROLES: readonly { cls: string; name: string; sample: string }[] = [
  { cls: 'bn-eyebrow', name: 'Eyebrow · mono caps', sample: 'Design system' },
  { cls: 'bn-label', name: 'Label · Inter caps', sample: 'This session' },
  { cls: 'bn-money', name: 'Money · tabular', sample: '$1,234.50' },
  { cls: 'bn-mono', name: 'Mono · machine strings', sample: '2026-09-02-box3-01' },
  { cls: 'bn-tnum', name: 'Tabular figures · Inter', sample: '1,625 cards · 443 SKUs' },
  { cls: 'bn-muted', name: 'Muted · ink-3', sample: 'Metadata and captions' },
  { cls: 'bn-faint', name: 'Faint · ink-4', sample: 'Disabled and dividers' },
]

const TYPE_SCALE: readonly { token: string; px: number; role: string }[] = [
  { token: '--bn-fs-5xl', px: 48, role: 'Home greeting' },
  { token: '--bn-fs-4xl', px: 36, role: 'Hero figure' },
  { token: '--bn-fs-3xl', px: 28, role: 'Page title' },
  { token: '--bn-fs-2xl', px: 22, role: 'Stat value · question' },
  { token: '--bn-fs-xl', px: 18, role: 'Section heading' },
  { token: '--bn-fs-lg', px: 16, role: 'Row primary' },
  { token: '--bn-fs-base', px: 14, role: 'Body' },
  { token: '--bn-fs-md', px: 13, role: 'Controls · table' },
  { token: '--bn-fs-sm', px: 12, role: 'Metadata' },
  { token: '--bn-fs-xs', px: 11, role: 'Label · pill' },
  { token: '--bn-fs-2xs', px: 10, role: 'Keycap · badge' },
]

const SPACES = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10'] as const
const RADII = ['xs', 'sm', '', 'lg', 'xl', '2xl', 'full'] as const
const VARIANTS: readonly ButtonVariant[] = ['default', 'primary', 'ghost', 'quiet', 'danger', 'danger-solid', 'ok']
const SIZES: readonly ButtonSize[] = ['sm', 'md', 'lg', 'xl']
const TONES: readonly PillTone[] = ['default', 'accent', 'ok', 'warn', 'danger', 'live']

// ------------------------------------------------------------------------- scaffolding

function Section({ id, title, lede, children }: { id: string; title: string; lede?: ReactNode; children: ReactNode }) {
  return (
    <section className="kit-section" id={`kit-${id}`} data-kit-section={id}>
      <header className="kit-section-head">
        <h2 className="bn-section-title">{title}</h2>
        {lede ? <p className="kit-section-lede">{lede}</p> : null}
      </header>
      {children}
    </section>
  )
}

function Spec({ name, label, note, wide, forcePressed, children }: { name?: string; label: string; note?: ReactNode; wide?: boolean; forcePressed?: boolean; children: ReactNode }) {
  return (
    <div className={`kit-spec${wide ? ' kit-spec-wide' : ''}`} data-specimen={name} data-force-state={forcePressed ? 'pressed' : undefined}>
      <div className="kit-spec-label bn-label">{label}</div>
      <div className="kit-spec-body">{children}</div>
      {note ? <p className="kit-spec-note">{note}</p> : null}
    </div>
  )
}

function Code({ children }: { children: ReactNode }) {
  return <code className="kit-code">{children}</code>
}

function FieldSpecimen({ persona }: { persona: 'owner' | 'fulfiller' }) {
  const [text, setText] = useState(persona === 'owner' ? 'thievul' : '')
  return <SearchField value={text} onChange={setText} persona={persona} />
}

function MotionDemo({ duration, ease }: { duration: string; ease: string }) {
  const [tick, setTick] = useState(0)
  return (
    <button type="button" className="kit-motion" onClick={() => setTick((n) => n + 1)} title="Play">
      <span key={tick} className="kit-motion-dot" style={{ animationDuration: `var(${duration})`, animationTimingFunction: `var(${ease})` }} />
      <span className="kit-motion-label">
        <span className="bn-mono">{duration.replace('--bn-', '')}</span>
        <span className="bn-mono kit-motion-ease">{ease.replace('--bn-', '')}</span>
      </span>
      <Icon name="play" size={12} className="kit-motion-play" />
    </button>
  )
}

function useActiveSection(): string | null {
  const [active, setActive] = useState<string | null>(null)
  useEffect(() => {
    const nodes = Array.from(document.querySelectorAll<HTMLElement>('[data-kit-section]'))
    if (nodes.length === 0) return
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
        const first = visible[0]
        if (first !== undefined) setActive((first.target as HTMLElement).dataset.kitSection ?? null)
      },
      { rootMargin: '-10% 0px -70% 0px', threshold: 0 },
    )
    for (const node of nodes) observer.observe(node)
    return () => observer.disconnect()
  }, [])
  return active
}

// -------------------------------------------------------------------------------- page

export function Gallery() {
  const active = useActiveSection()
  const scrolled = useRef(false)
  const jump = (id: string) => {
    scrolled.current = true
    document.getElementById(`kit-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  const groups = [...new Set(SECTIONS.map((s) => s.group))]

  return (
    <main className="gallery bn-page">
      <header className="bn-head kit-head">
        <div className="bn-head-text">
          <span className="bn-eyebrow">Design system</span>
          <h1 className="bn-title">
            <Icon name="grid" size={22} />
            Kit
          </h1>
          <p className="bn-lede">Every primitive the screens are built from, drawn from the tokens. Switch the theme in the nav to see both.</p>
        </div>
        <div className="bn-head-actions">
          <Pill tone="accent" mono>
            tokens.css
          </Pill>
          <Pill mono>kit.css</Pill>
          <Pill mono>kit/index.tsx</Pill>
        </div>
      </header>

      <div className="kit-layout">
        <nav className="kit-index" aria-label="Sections">
          {groups.map((group) => (
            <div key={group} className="kit-index-group">
              <div className="kit-index-label">{group}</div>
              {SECTIONS.filter((s) => s.group === group).map((s) => (
                <button key={s.id} type="button" className="kit-index-link" aria-current={active === s.id ? 'true' : undefined} onClick={() => jump(s.id)}>
                  {s.label}
                </button>
              ))}
            </div>
          ))}
        </nav>

        <div className="kit-sections">
          {/* ------------------------------------------------------------ foundations */}
          <Section
            id="mark"
            title="The mark"
            lede={<>Six locked marks, <Code>bluesteel</Code> the default. <Code>docs/specs/logo.md</Code> is the state of record and <Code>scripts/build-mark.mjs</Code> generates the geometry from that spec&rsquo;s own generator &mdash; nothing here is hand-drawn.</>}
          >
            <Spec
              label="The small cut · below 64px"
              wide
              note={<>What ships. Stroke 4.2, no taper, no <Code>feTurbulence</Code> &mdash; swept in section 11 at 16, 28, 32 and 44px, which is every size this app draws. The display cut&rsquo;s brackets are gone by 28px and its marbling loses to this flat prism gradient.</>}
            >
              <div className="kit-marks">
                {LOGO_VARIANTS.map((v) => (
                  <span key={v} className="kit-mark">
                    <Logo variant={v} size={56} />
                    <span className="kit-mark-name">{MARKS[v].label}</span>
                  </span>
                ))}
              </div>
            </Spec>
            <Spec
              label="The display cut · 64px and up"
              wide
              note={<>The holographic foil, drawn with a variable-width taper and a displacement map. Nothing in the product reaches this size; it is here so the cut that is locked can be looked at.</>}
            >
              <div className="kit-marks">
                {LOGO_VARIANTS.map((v) => (
                  <span key={v} className="kit-mark">
                    <Logo variant={v} size={96} />
                    <span className="kit-mark-name">{MARKS[v].label}</span>
                  </span>
                ))}
              </div>
            </Spec>
            <Spec
              label="Across its size range"
              wide
              note={<>40 is both crash pages, 44 the puller&rsquo;s header, and 16 to 32 the favicon&rsquo;s range. The whole shell draws the LOCKUP now &mdash; the sidebar at kanji 40, its rail and the phone bar as the empty slot at 32, the drawer at kanji 40 (sections 16 and 19) &mdash; so the sizes below 40 are specimens here rather than call sites. The mark is fixed dark in both themes on purpose &mdash; a light ground was derived and lost its silhouette (section 12).</>}
            >
              <div className="kit-marks kit-marks-tight">
                {[16, 26, 30, 32, 40, 44, 64].map((px) => (
                  <span key={px} className="kit-mark">
                    <Logo size={px} />
                    <span className="kit-mark-name">{px}px</span>
                  </span>
                ))}
              </div>
            </Spec>
          </Section>

          {/* ITS OWN SECTION, NOT A FOURTH SPEC INSIDE `mark`. Two tests in brand.spec.ts query
              `[data-kit-section="mark"] svg[width="56"|"96"]` and count feTurbulence and the set
              of stop-colors; a lockup inside that subtree at either width breaks both. */}
          <Section
            id="lockup"
            title="The lockup"
            lede="番地 over BANCHI inside the mark&rsquo;s own brackets — the expanded form, and the only place the product spells its name in two scripts. Every parameter was settled by forced choice over thirty-seven rounds (section 13); nothing here is drawn by hand."
          >
            <Spec
              label="At the sizes it is drawn"
              wide
              note={<>The sidebar draws it at kanji 40 &mdash; a 128&times;93 block in 212px (section 16). Below kanji 32 it is not drawn at all: 番&rsquo;s counters close before the bracket does (section 11). The type is OUTLINED, so no font ships and it cannot fall back to another face.</>}
            >
              <div className="kit-marks">
                {[32, 40, 56].map((px) => (
                  <span key={px} className="kit-mark">
                    <Lockup size={px} />
                    <span className="kit-mark-name">kanji {px}</span>
                  </span>
                ))}
              </div>
            </Spec>
            <Spec
              label="On the dark ground"
              wide
              note={<>Section 16 gives the bracket <Code>bluesteel</Code>&rsquo;s own four-stop chrome on dark, so the lockup and the rail mark are one object in one metal; on light it is flat ink. The roman sits at 0.45 of the ink &mdash; under this product&rsquo;s own floor for a word, argued in section 13 rather than overlooked.</>}
            >
              {/* a real dark island rather than a dark rectangle: `data-theme` flips the tokens
                  AND the bracket's fill, so this shows the treatment rather than a light lockup
                  sitting on a dark ground */}
              <div className="kit-marks kit-lockup-dark" data-theme="dark">
                <span className="kit-mark"><Lockup size={40} /></span>
              </div>
            </Spec>
          </Section>

          <Section id="color" title="Color" lede="Three registers: ink is what you read, line is what separates, brand is where to look. Indigo for action, vermilion for what is live.">
            <div className="kit-swatches">
              {COLORS.map((c) => (
                <div key={c.token} className="kit-swatch">
                  <span className="kit-swatch-chip" style={{ background: `var(${c.token})` }}>
                    {c.ink ? <span className="kit-swatch-sample" style={{ color: 'var(--bn-surface)' }}>Aa</span> : null}
                  </span>
                  <span className="kit-swatch-name">{c.name}</span>
                  <span className="kit-swatch-token bn-mono">{c.token}</span>
                </div>
              ))}
            </div>
          </Section>

          <Section id="type" title="Type" lede={<>Manrope for headings and big figures, Inter for everything, JetBrains Mono only for machine strings. Numbers in tables are Inter with <Code>tabular-nums</Code>.</>}>
            <div className="kit-faces">
              <div className="kit-face" style={{ fontFamily: 'var(--bn-font-display)', fontWeight: 800 }}>
                <span>Manrope</span>
                <span className="kit-face-role">display · headings, figures</span>
              </div>
              <div className="kit-face" style={{ fontFamily: 'var(--bn-font-ui)', fontWeight: 600 }}>
                <span>Inter</span>
                <span className="kit-face-role">ui · everything</span>
              </div>
              <div className="kit-face" style={{ fontFamily: 'var(--bn-font-mono)', fontWeight: 500 }}>
                <span>JetBrains Mono</span>
                <span className="kit-face-role">mono · SKUs, run names, codes, kbd</span>
              </div>
            </div>
            <div className="kit-type">
              {TYPE_SCALE.map((t) => (
                <div key={t.token} className="kit-type-row">
                  <span className="kit-type-meta">
                    <span className="bn-mono">{t.token.replace('--bn-fs-', '')}</span>
                    <span className="bn-mono kit-type-px">{t.px}px</span>
                    <span className="kit-type-role">{t.role}</span>
                  </span>
                  <span className="kit-type-sample" style={{ fontSize: `var(${t.token})`, fontFamily: t.px >= 22 ? 'var(--bn-font-display)' : 'var(--bn-font-ui)', fontWeight: t.px >= 22 ? 800 : t.px >= 16 ? 600 : 500 }}>
                    Every card has an address
                  </span>
                </div>
              ))}
            </div>
            <div className="kit-roles">
              {TEXT_ROLES.map((role) => (
                <div key={role.cls} className="kit-role">
                  <span className={`kit-role-sample ${role.cls}`}>{role.sample}</span>
                  <span className="kit-role-name">{role.name}</span>
                  <span className="kit-role-token bn-mono">.{role.cls}</span>
                </div>
              ))}
            </div>
          </Section>

          <Section id="space" title="Space & radius" lede="A 4px scale, and radii from 4px to a pill.">
            <div className="kit-spaces">
              {SPACES.map((s) => (
                <div key={s} className="kit-space">
                  <span className="kit-space-bar" style={{ width: `var(--bn-${s})` }} />
                  <span className="bn-mono kit-space-name">--bn-{s}</span>
                </div>
              ))}
            </div>
            <div className="kit-radii">
              {RADII.map((r) => (
                <div key={r || 'r'} className="kit-radius">
                  <span className="kit-radius-box" style={{ borderRadius: `var(--bn-r${r ? `-${r}` : ''})` }} />
                  <span className="bn-mono">--bn-r{r ? `-${r}` : ''}</span>
                </div>
              ))}
            </div>
          </Section>

          <Section id="elevation" title="Elevation" lede="Three shadows and an accent glow. Panels sit at 1, hover and dialogs rise.">
            <div className="kit-shadows">
              {['--bn-shadow-1', '--bn-shadow-2', '--bn-shadow-3', '--bn-shadow-accent'].map((s) => (
                <div key={s} className="kit-shadow" style={{ boxShadow: `var(${s})` }}>
                  <span className="bn-mono">{s.replace('--bn-', '')}</span>
                </div>
              ))}
            </div>
          </Section>

          <Section id="motion" title="Motion" lede="Three durations, three curves. Press a tile to play it. Everything the operator causes should be visible; reduced motion collapses all of it.">
            <div className="kit-motions">
              {['--bn-t-fast', '--bn-t', '--bn-t-slow'].map((d) =>
                ['--bn-ease', '--bn-ease-out', '--bn-ease-spring'].map((e) => <MotionDemo key={d + e} duration={d} ease={e} />),
              )}
            </div>
          </Section>

          <Section id="icons" title="Icons" lede={<>{ICON_NAMES.length} names on a 24 grid, 1.75 stroke, round joins. Never inline an <Code>&lt;svg&gt;</Code> in a screen — add a path here.</>}>
            <div className="kit-icons">
              {ICON_NAMES.map((name: IconName) => (
                <div key={name} className="kit-icon">
                  <Icon name={name} size={20} />
                  <span className="bn-mono">{name}</span>
                </div>
              ))}
            </div>
          </Section>

          {/* -------------------------------------------------------------- primitives */}
          <Section id="buttons" title="Buttons" lede="Seven variants, four sizes. Primary is the one thing to do; danger is red; money moments carry the figure in the label.">
            <div className="kit-grid">
              {VARIANTS.map((v) => (
                <Spec key={v} label={v}>
                  <div className="kit-row kit-row-wrap">
                    {SIZES.map((s) => (
                      <Button key={s} variant={v} size={s}>
                        {s}
                      </Button>
                    ))}
                  </div>
                  <div className="kit-row kit-row-wrap">
                    <Button variant={v} icon="check">
                      Icon
                    </Button>
                    <Button variant={v} kbd="S">
                      Key
                    </Button>
                    <Button variant={v} iconRight="arrowRight">
                      Right
                    </Button>
                    <Button variant={v} disabled>
                      Disabled
                    </Button>
                    <Button variant={v} busy>
                      Busy
                    </Button>
                  </div>
                </Spec>
              ))}
              <Spec label="shapes">
                <div className="kit-row kit-row-wrap">
                  <Button pill icon="camera">
                    Pill
                  </Button>
                  <Button variant="primary" pill>
                    Primary pill
                  </Button>
                  <Button iconOnly icon="refresh">
                    Reload
                  </Button>
                  <Button iconOnly variant="ghost" icon="x">
                    Close
                  </Button>
                  <Button iconOnly variant="primary" size="lg" icon="plus">
                    Add
                  </Button>
                </div>
                <Button variant="primary" block icon="dollar">
                  Push 12 listings · $184.20
                </Button>
              </Spec>
            </div>
          </Section>

          <Section id="kbd" title="Keycaps" lede="An hour in the review queue is a keyboard, so every choice shows its key. Hidden on coarse pointers.">
            <div className="kit-grid">
              <Spec label="kbd">
                <div className="kit-row kit-row-wrap">
                  <Kbd>1</Kbd>
                  <Kbd>S</Kbd>
                  <Kbd>Esc</Kbd>
                  <Kbd>↵</Kbd>
                  <span className="bn-kbd-group">
                    <Kbd>⌘</Kbd>
                    <Kbd>K</Kbd>
                  </span>
                  <span className="bn-kbd-group">
                    <Kbd>,</Kbd>
                    <Kbd>Q</Kbd>
                  </span>
                </div>
              </Spec>
              <Spec label="in a button · on accent">
                <div className="kit-row kit-row-wrap">
                  <Button kbd="R" icon="refresh">
                    Reload
                  </Button>
                  <Button variant="primary" kbd="↵">
                    Answer all 16
                  </Button>
                  <Button variant="quiet" kbd="X" icon="x">
                    Close
                  </Button>
                </div>
              </Spec>
              <Spec label="row keycap · 28px" note={<>The review queue's row keycap is the kit's <Code>.bn-kbd-lg</Code>.</>}>
                <div className="kit-row">
                  <kbd className="kit-keycap">1</kbd>
                  <kbd className="kit-keycap">2</kbd>
                  <kbd className="kit-keycap">3</kbd>
                  <kbd className="kit-keycap kit-keycap-blank">–</kbd>
                </div>
              </Spec>
            </div>
          </Section>

          <Section id="pills" title="Pills & dots" lede="Status in six tones. Live is vermilion and pulses.">
            <div className="kit-grid">
              <Spec label="tones">
                <div className="kit-row kit-row-wrap">
                  {TONES.map((t) => (
                    <Pill key={t} tone={t}>
                      {t}
                    </Pill>
                  ))}
                </div>
              </Spec>
              <Spec label="with icon · mono · outline">
                <div className="kit-row kit-row-wrap">
                  <Pill tone="ok" icon="check">
                    reconciled
                  </Pill>
                  <Pill tone="live" icon="dot">
                    live
                  </Pill>
                  <Pill tone="accent" mono>
                    SKU 8608000
                  </Pill>
                  <Pill outline>outline</Pill>
                  <Pill tone="warn" outline>
                    parked
                  </Pill>
                </div>
              </Spec>
              <Spec label="dots">
                <div className="kit-row kit-row-wrap">
                  <span className="bn-dot" /> default
                  <span className="bn-dot bn-dot-ok" /> ok
                  <span className="bn-dot bn-dot-warn" /> warn
                  <span className="bn-dot bn-dot-danger" /> danger
                  <span className="bn-dot bn-dot-accent" /> accent
                  <span className="bn-dot bn-dot-live" /> live
                </div>
              </Spec>
            </div>
          </Section>

          <Section id="fields" title="Fields" lede="34px controls, 40px large. Focus is the accent ring, product-wide.">
            <div className="kit-grid">
              <Spec label="input · with hint">
                <label className="bn-field">
                  <span className="bn-field-label">Box name</span>
                  <input className="bn-input" defaultValue="RB Epics" />
                  <span className="bn-field-hint">Names are unique; case is folded.</span>
                </label>
              </Spec>
              <Spec label="input-wrap · icon and key">
                <span className="bn-input-wrap">
                  <Icon name="search" size={16} />
                  <input className="bn-input" placeholder="Find a card" />
                  <Kbd>/</Kbd>
                </span>
              </Spec>
              <Spec label="select · textarea">
                <select className="bn-select" defaultValue="market">
                  <option value="market">Market price</option>
                  <option value="low">Lowest listing</option>
                </select>
                <textarea className="bn-textarea" defaultValue="Held back: bullish above $5." />
              </Spec>
              <Spec label="large · mono · disabled">
                <input className="bn-input bn-input-lg" placeholder="Type the name of the card" />
                <input className="bn-input bn-input-mono" defaultValue="2026-09-02-box6-01" />
                <input className="bn-input" defaultValue="Disabled" disabled />
              </Spec>
              <Spec label="checks">
                <div className="kit-row kit-row-wrap">
                  <label className="bn-check">
                    <input type="checkbox" defaultChecked /> Listed only
                  </label>
                  <label className="bn-check">
                    <input type="checkbox" /> Split by game
                  </label>
                </div>
              </Spec>
            </div>
          </Section>

          <Section id="segmented" title="Segmented & tabs" lede="Segmented for a mode; tabs for a view.">
            <div className="kit-grid">
              <Spec label="segmented">
                <Segmented
                  value="boxes"
                  onChange={noop}
                  options={[
                    { value: 'boxes', label: 'Boxes', icon: 'box' },
                    { value: 'cards', label: 'Cards', icon: 'layers' },
                    { value: 'pull', label: 'Pull', icon: 'hand', kbd: 'P' },
                  ]}
                  label="Mode"
                />
              </Spec>
              {/* S10: `.bn-seg`'s 3px padding put it at 34px beside 28px search/select
                  controls in the same row. `size="sm"` totals 28px (2px padding + a 24px
                  item), shown here beside a 28px `Button` so the two bottoms line up. */}
              <Spec name="seg-sm" label="segmented, sm, beside a 28px control">
                <div className="kit-row" style={{ alignItems: 'center' }}>
                  <Segmented
                    value="new"
                    onChange={noop}
                    options={[
                      { value: 'new', label: 'Newest' },
                      { value: 'old', label: 'Oldest' },
                    ]}
                    label="Sort"
                    size="sm"
                  />
                  <Button size="sm" icon="search">Search</Button>
                </div>
              </Spec>
              <Spec label="tabs">
                <div className="bn-tabs">
                  <button type="button" className="bn-tab" aria-selected="true">
                    <Icon name="inbox" size={14} /> Review <Pill tone="warn">12</Pill>
                  </button>
                  <button type="button" className="bn-tab">
                    <Icon name="flag" size={14} /> Parked <Pill>6</Pill>
                  </button>
                  <button type="button" className="bn-tab">
                    <Icon name="history" size={14} /> Answered
                  </button>
                </div>
              </Spec>
            </div>
          </Section>

          <Section id="notice" title="Notice" lede="Four tones; the code line is where the machine string goes.">
            <div className="kit-grid">
              <Spec label="info">
                <Notice title="The export is fetched to a scope this process names">Every card of this game carries a set hint, so the scope is one set.</Notice>
              </Spec>
              <Spec label="warn">
                <Notice tone="warn" title="Two runs are joined but neither is emitted">
                  Emit them together, so the live cap is spent once.
                </Notice>
              </Spec>
              <Spec label="danger · with code">
                <Notice tone="danger" title="The answer was refused" code="sku_not_a_candidate · Box 2 · Section 1 · Card 14">
                  The queue file was rewritten after this screen read it. Reload to see the rows the route will take.
                </Notice>
              </Spec>
              <Spec label="ok">
                <Notice tone="ok" title="Reconciled">
                  405 SKUs read a live count for the first time.
                </Notice>
              </Spec>
            </div>
          </Section>

          <Section id="receipt" title="Receipt & toast" lede="A receipt is an undo anchored beside the thing it undoes, draining over its window. A toast is the same shape, floating.">
            <div className="kit-grid">
              <Spec label="receipt · draining" wide>
                <div className="bn-receipt" style={{ ['--receipt-ms' as string]: '20000ms' }}>
                  <Icon name="check" size={16} style={{ color: 'var(--bn-ok)' }} />
                  <span className="bn-grow">
                    <strong>Answered as Near Mint Holofoil</strong>
                    <span className="bn-mono" style={{ display: 'block', fontSize: 11, opacity: 0.65 }}>
                      Box 2 · Section 1 · Card 14
                    </span>
                  </span>
                  <span className="bn-receipt-bar" />
                  <Button size="sm" icon="undo" kbd="U">
                    Undo
                  </Button>
                </div>
              </Spec>
              <Spec label="toast · receipt / ok / refusal" wide>
                <div className="kit-toasts">
                  <div className="bn-toast bn-toast-receipt">
                    <Icon name="undo" size={16} className="bn-toast-icon" />
                    <div className="bn-toast-text">
                      <div className="bn-toast-title">Marked sold</div>
                      <div className="bn-toast-body">Box 3 · Section 2 · Card 15</div>
                    </div>
                    <button type="button" className="bn-toast-action">
                      Undo <kbd className="bn-kbd">U</kbd>
                    </button>
                    {/* THE DISMISS IS PART OF THE COMPONENT AND THE SPECIMEN LEFT IT OUT (D117).
                        A sheet that draws a control's other half is the only place a floor over
                        the kit can be measured — `.bn-toast-close` was 24px and this page could
                        not say so, because nothing here drew one. */}
                    <button type="button" className="bn-toast-close" aria-label="Dismiss">
                      <Icon name="x" size={14} />
                    </button>
                  </div>
                  <div className="bn-toast bn-toast-ok">
                    <Icon name="check" size={16} className="bn-toast-icon" />
                    <div className="bn-toast-text">
                      <div className="bn-toast-title">Import file written</div>
                      <div className="bn-toast-body">437 copies · one file</div>
                    </div>
                  </div>
                  <div className="bn-toast bn-toast-refusal">
                    <Icon name="alert" size={16} className="bn-toast-icon" />
                    <div className="bn-toast-text">
                      <div className="bn-toast-title">The store is busy behind a running join</div>
                      <div className="bn-toast-body">store_busy</div>
                    </div>
                  </div>
                </div>
              </Spec>
            </div>
          </Section>

          <Section id="empty" title="Empty state" lede="A real sentence and one way onward. At zero it should feel like a reward.">
            <div className="kit-grid">
              <Spec label="empty" wide>
                <div className="bn-panel">
                  <EmptyState
                    icon="check"
                    title="All caught up."
                    body="You answered 16 cards in 4 min 12 s · 2 closed."
                    actions={
                      <>
                        <Button variant="primary" icon="tag" iconRight="arrowRight">
                          Price the answers
                        </Button>
                        <Button icon="play">Run another box</Button>
                      </>
                    }
                  />
                </div>
              </Spec>
            </div>
          </Section>

          <Section id="skeleton" title="Skeleton & progress" lede="Reserve the shape while the server answers; move the bar when the operator does.">
            <div className="kit-grid">
              <Spec label="skeleton">
                <div className="bn-skeleton" style={{ height: 22, width: '60%' }} />
                <div className="bn-skeleton" style={{ height: 14, width: '40%' }} />
                <div className="bn-skeleton" style={{ height: 56 }} />
                <div className="bn-skeleton" style={{ height: 56 }} />
              </Spec>
              <Spec label="progress · default and ok">
                <div className="bn-progress">
                  <span style={{ width: '34%' }} />
                </div>
                <div className="bn-progress bn-progress-ok">
                  <span style={{ width: '100%' }} />
                </div>
                <div className="kit-row">
                  <Stat value="16" label="answered" />
                  <Stat value="$184" label="to list" />
                  <Stat value="2" label="closed" />
                </div>
              </Spec>
              {/* S9: Inventory's own bar (`.browse-boxcell-bar`, 44x5, accent only) never
                  composes `-ok`, so it can never turn green at 100%. `bn-progress-sm` is the
                  same 5px height at the kit level, and it composes with `-ok` exactly like
                  the base size — proving the capability Inventory's hand-rolled bar lacks. */}
              <Spec name="progress-sm-done" label="progress, sm, at done">
                <div className="bn-progress bn-progress-sm" style={{ width: 44 }}>
                  <span style={{ width: '60%' }} />
                </div>
                <div className="bn-progress bn-progress-sm bn-progress-ok" style={{ width: 44 }}>
                  <span style={{ width: '100%' }} />
                </div>
              </Spec>
              {/* S9: the tile shipped one ratio, 22:12. `-sm` reads Orders' own 14:11
                  (`.orders-index-figure`); `-xs` reads Inventory's own 11:11, un-bolded
                  (`.browse-boxcell-count` beside `.browse-boxcell-meta`). */}
              <Spec name="stat-sizes" label="stat, sm and xs">
                <div className="kit-row kit-row-wrap">
                  <Stat value="16" label="answered" />
                  <Stat value="4" label="left" size="sm" />
                  <Stat value="662" label="on hand" size="xs" />
                </div>
              </Spec>
            </div>
          </Section>

          <Section id="data" title="Data" lede="Key/value pairs, a table, list rows. Numbers right-aligned and tabular.">
            <div className="kit-grid">
              <Spec label="kv">
                <dl className="bn-kv">
                  <dt>Card</dt>
                  <dd>Snorlax</dd>
                  <dt>Number</dt>
                  <dd className="bn-mono">014/132</dd>
                  <dt>Market</dt>
                  <dd className="bn-money">$84.50</dd>
                  <dt>Confidence</dt>
                  <dd>High</dd>
                </dl>
              </Spec>
              {/* S13: `.bn-truncate` was never used anywhere — 10 hand copies of the same
                  three properties exist instead, 4 of which also write their own
                  `min-width: 0`. Unchanged here: that turned out to be redundant rather than
                  a gap (see kit.css's own note), and this flex row proves `.bn-truncate`
                  clips exactly as written, with nothing added. */}
              <Spec name="truncate" label="truncate, in a flex row">
                <div className="kit-row" style={{ width: 160 }}>
                  <Icon name="box" size={16} />
                  <span className="bn-truncate" style={{ flex: '1 1 auto' }}>
                    A name much longer than the row beside it
                  </span>
                </div>
              </Spec>
              <Spec label="table" wide>
                <div className="bn-panel">
                  <table className="bn-table">
                    <thead>
                      <tr>
                        <th>Card</th>
                        <th>Condition</th>
                        <th>SKU</th>
                        <th className="num">Market</th>
                        <th className="num">Copies</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        ['Snorlax', 'Near Mint Holofoil', '8608002', '143.65', 1],
                        ['Charizard ex', 'Near Mint', '8607411', '12.00', 3],
                        ['Bidoof', 'Near Mint', '8601230', '0.12', 14],
                      ].map(([name, cond, sku, market, n]) => (
                        <tr key={String(sku)}>
                          <td>{name}</td>
                          <td>{cond}</td>
                          <td className="bn-mono">{sku}</td>
                          <td className="num">${market}</td>
                          <td className="num">{n}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Spec>
              <Spec label="list rows">
                <div className="bn-panel bn-list">
                  <button type="button" className="bn-list-row">
                    <Icon name="box" size={16} /> <span className="bn-grow">Box 3 · RB Epics</span> <Pill>723</Pill>
                  </button>
                  <button type="button" className="bn-list-row" aria-current="true">
                    <Icon name="box" size={16} /> <span className="bn-grow">Box 4 · WB1 R2</span> <Pill tone="accent">56</Pill>
                  </button>
                  <button type="button" className="bn-list-row">
                    <Icon name="box" size={16} /> <span className="bn-grow">Box 5 · UNL BBOX C/UC 1</span> <Pill>105</Pill>
                  </button>
                </div>
              </Spec>
            </div>
          </Section>

          <Section id="surfaces" title="Surfaces & menu" lede="A panel is raised, a well is sunken, a menu pops.">
            <div className="kit-grid">
              <Spec label="panel · head and body">
                <div className="bn-panel">
                  <div className="bn-panel-head">
                    <span className="bn-section-title">
                      <Icon name="history" size={16} /> Recent runs
                    </span>
                    <Button size="sm" variant="ghost" iconRight="arrowRight">
                      All runs
                    </Button>
                  </div>
                  <div className="bn-panel-body">Body text sits at 14px on the surface.</div>
                </div>
              </Spec>
              <Spec label="well · rule">
                <div className="bn-well">A sunken well for code or an inactive track.</div>
                <div className="bn-rule">or</div>
                <div className="bn-well bn-mono">banchi emit runs/2026-09-02-box6-01</div>
              </Spec>
              <Spec label="menu">
                <div className="bn-menu kit-menu-inline">
                  <div className="bn-menu-label">Box</div>
                  <button type="button" className="bn-menu-item">
                    <Icon name="divider" size={16} /> Put in a divider <Kbd>S</Kbd>
                  </button>
                  <button type="button" className="bn-menu-item">
                    <Icon name="tag" size={16} /> Set hint <Kbd>H</Kbd>
                  </button>
                  <div className="bn-menu-sep" />
                  <button type="button" className="bn-menu-item bn-menu-item-danger">
                    <Icon name="trash" size={16} /> Delete this box
                  </button>
                </div>
              </Spec>
            </div>
          </Section>

          {/* ------------------------------------------------------------ screen pieces */}
          <Section id="pull-confirm" title="Pull-confirm" lede="The one solid fill the Fulfiller ever sees. Three states, and the owner-side key hint.">
            <div className="kit-stack kit-stack-narrow">
              <Spec name="default" label="default · the Fulfillment case">
                <PullConfirm label="Pull this card" onConfirm={noop} />
              </Spec>
              <Spec name="pressed" label="pressed" forcePressed>
                <PullConfirm label="Pull this card" onConfirm={noop} />
              </Spec>
              <Spec name="disabled" label="disabled" note="Never appears in the Fulfillment view; that view has no disabled state.">
                <PullConfirm label="Pull this card" onConfirm={noop} disabled />
              </Spec>
              <Spec name="with-key" label="default + key hint · owner-side only">
                <PullConfirm label="Pull this card" onConfirm={noop} keyHint="↵" />
              </Spec>
            </div>
          </Section>

          <Section id="position" title="Position bar" lede={<>How far into its box a card sits. A closed box earns a percentage; an open one counts what is in it.</>}>
            <div className="kit-stack">
              <Spec name="bar-closed" label="closed box · 250 cards">
                <PositionBar place={CLOSED_BOX} />
              </Spec>
              <Spec name="bar-open" label="open box · the denominator still moves">
                <PositionBar place={OPEN_BOX} />
              </Spec>
              <Spec name="bar-single" label="one section · no dividers declared">
                <PositionBar place={SINGLE_SECTION} />
              </Spec>
              <Spec name="bar-unknown" label="no fraction · the server declined to say">
                <PositionBar place={NO_FRACTION} />
              </Spec>
              <Spec name="bar-fulfiller" label="the Fulfiller's density">
                <PositionBar place={CLOSED_BOX} persona="fulfiller" />
              </Spec>
              {/* THE COMPONENT'S PRIMARY DRAWING, WHICH THIS SHEET HAS NEVER SHOWN. Every
                  specimen above passes no `sectionDepth`, so the shape `#/inventory` actually
                  renders on every copy row — the section ruler over the demoted box strip —
                  existed on the kit sheet only inside the `locations` specimen, three sections
                  down and four rows deep. The five above are left exactly as they are: the
                  no-depth shape is real too, and it is what the Fulfiller draws. */}
              <Spec name="bar-depth" label="the section as the ruler · a divided box">
                <PositionBar place={CLOSED_BOX} sections={BOX_SECTIONS} sectionDepth />
              </Spec>
              <Spec name="bar-depth-gone" label="departed · the ruler stays and both marks leave it">
                <PositionBar place={DEPARTED} sections={BOX_SECTIONS} sectionDepth />
              </Spec>
            </div>
          </Section>

          <Section id="position-label" title="Position label" lede="One ranking, three flows: stacked, slot-led for a column, and run for a sentence.">
            <div className="kit-grid">
              <Spec label="stack · path-led">
                <div className="kit-poslabel" style={{ ['--pos-slot' as string]: '32px' }}>
                  <PositionLabel label="Box 3 · Section 2 · Card 15" />
                </div>
              </Spec>
              <Spec label="stack · slot-led">
                <div className="kit-poslabel" style={{ ['--pos-slot' as string]: '32px' }}>
                  <PositionLabel label="Box 3 · Section 2 · Card 15" lead="slot" />
                </div>
              </Spec>
              <Spec label="run · in a sentence">
                <p style={{ ['--pos-slot' as string]: '16px' }}>
                  The card is still at <PositionLabel label="Box 3 · Section 2 · Card 15" flow="run" />.
                </p>
              </Spec>
              <Spec label="departed">
                <div className="kit-poslabel" style={{ ['--pos-slot' as string]: '32px' }}>
                  <PositionLabel label="Box 3 · departed · B3 #31" />
                </div>
              </Spec>
            </div>
          </Section>

          <Section id="search" title="Search field" lede="The owner's carries a / hotkey and its chip; the Fulfiller's carries neither and keeps a visible label.">
            <div className="kit-stack">
              <Spec name="search-owner" label="owner · dense, with the key chip">
                <FieldSpecimen persona="owner" />
              </Spec>
              <Spec name="search-fulfiller" label="fulfiller · large, no keys">
                <FieldSpecimen persona="fulfiller" />
              </Spec>
            </div>
          </Section>

          <Section id="locations" title="Card locations" lede="One card and every row shape it draws: six copies — four in a box, one of those sold; one departed, and so in no slot at all; one pooled, which is a count rather than a place. The owner's spec names a current copy too, and that row is identical in shape to every other. Same group, same actions; the prop that differs is the persona.">
            <div className="kit-stack">
              <Spec
                name="locations-owner"
                label="owner · a bar on every row that has one"
                note="Two rows deliberately carry no bar: the pooled copy has no coordinate to draw and the departed one is in no slot at all. The copy the walk is standing on draws a bar like every other row — it carries a Viewing marker and a neutral rail, and nothing else (D119)."
              >
                {/* `.kit-copies` is a `copies` query container. Without it every
                    `@container copies` rule in CardLocations.css is dead here and this
                    specimen draws a layout no screen produces — see Gallery.css. */}
                <div className="kit-copies">
                  <CardLocations group={GROUP} persona="owner" onSell={noop} busyKey={null} soldKeys={new Set()} currentKey="7/12" />
                </div>
              </Spec>
              <Spec
                name="locations-owner-lone"
                label="owner · one copy, no SKU"
                note="A card the pipeline has never identified. The header drops the live figure and the Pushed / Staged / headroom line — with no SKU there is no listing record, every one of those numbers is a structural zero, and `Room for 1 more live` is a promise nothing can keep. `no SKU yet` in the meta line is the whole of what is left to say."
              >
                <div className="kit-copies">
                  <CardLocations group={LOOSE_GROUP} persona="owner" onSell={noop} busyKey={null} soldKeys={new Set()} />
                </div>
              </Spec>
              <Spec name="locations-fulfiller" label="fulfiller · every copy is its own card" note="The photograph is this sheet's own specimen, not a stored capture: nothing here asks the capture server, so the page renders the same in every checkout. Two copies carry no image and draw the missing-photo sentence, which is a real state.">
                <CardLocations
                  group={GROUP}
                  persona="fulfiller"
                  onSell={noop}
                  busyKey={null}
                  soldKeys={new Set()}
                  /* THE ONE CALL SITE OF `photoSrc` IN THIS PRODUCT. See the header. */
                  photoSrc={() => SPECIMEN_PHOTO}
                />
              </Spec>
            </div>
          </Section>
        </div>
      </div>
    </main>
  )
}
