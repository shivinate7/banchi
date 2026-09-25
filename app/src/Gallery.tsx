import { useEffect, useRef, useState, type ReactNode } from 'react'

import type { Place, SearchGroup, SectionDetail } from './types'
import { PullConfirm } from './PullConfirm'
import { PositionBar } from './PositionBar'
import { PositionLabel } from './PositionLabel'
import { SearchField } from './SearchField'
import { CardLocations } from './CardLocations'
import {
  Button, Chip, ConfirmSheet, EmptyState, Icon, IconButton, Kbd, Loading, Lockup, Logo, Modal, Money, Notice, Page, Pill, Popover, Refusal, ReloadButton, Retry,
  KeyHint, Section, Segmented, Select, Sheet, Stat, StatusSlot, Toolbar, Verdict, VARIANTS as LOGO_VARIANTS,
  type ButtonSize, type ButtonVariant, type IconName, type PillTone,
} from './kit'
import { MARKS } from './kit/markPalettes'
import { ICON_MEANINGS, ICON_NAMES } from './kit/Icon'
import { DataSpecimens } from './kit/data.specimens'
import { FilterSpecimens } from './kit/filters.specimens'
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
   override setting `index: 12` and leaving `slot` alone drew `Box 7, Section 1, Card 12`
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
   place it left (the fixture below keeps the older dotted form, which the label reader still
   reads). Two departed copies of one card at one place may read the same (the owner's ruling,
   2026-09-24).
   `server.ts:isDeparted` reads the NULL SLOT BESIDE A REAL LABEL, so handing this fixture a
   numeric slot turns the departed row back into an ordinary one and the shell it draws
   (`is-gone is-nobar`) stops being rendered anywhere on this sheet — which is exactly what
   `app/tests/gallery.spec.ts` is here to refuse. */
const DEPARTED = place({ label: 'Box 3 · departed · B3 #31', box: 3, index: 31, slot: null, section: null, card: null, fraction: null })
/* A POOLED COPY (D24): a count, not a location. `located: false` is the whole of it — the block
   carries no label at all, so the row draws the game's own name where a position would be and
   `pooled, <key>` under it. A different game from every other fixture here on purpose: the
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
  { id: 'page', label: 'Page', group: 'Foundations' },
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
  { id: 'failure', label: 'Refusal & retry', group: 'Primitives' },
  { id: 'overlays', label: 'Sheets & popovers', group: 'Primitives' },
  { id: 'receipt', label: 'Receipt & toast', group: 'Primitives' },
  { id: 'empty', label: 'Empty state', group: 'Primitives' },
  { id: 'skeleton', label: 'Skeleton & progress', group: 'Primitives' },
  { id: 'data', label: 'Data', group: 'Primitives' },
  { id: 'surfaces', label: 'Surfaces & menu', group: 'Primitives' },
  { id: 'data-kit', label: 'Money, filters & links', group: 'Primitives' },
  { id: 'pull-confirm', label: 'Pull-confirm', group: 'Screen pieces' },
  { id: 'position', label: 'Position bar', group: 'Screen pieces' },
  { id: 'position-label', label: 'Position label', group: 'Screen pieces' },
  { id: 'search', label: 'Search field', group: 'Screen pieces' },
  { id: 'locations', label: 'Card locations', group: 'Screen pieces' },
]

const COLORS: readonly { name: string; token: string; ink?: boolean }[] = [
  { name: 'Page', token: '--bn-bg' },
  { name: 'Surface', token: '--bn-surface' },
  { name: 'Surface 2, sunken', token: '--bn-surface-2' },
  { name: 'Surface 3, hover', token: '--bn-surface-3' },
  { name: 'Ink', token: '--bn-ink', ink: true },
  { name: 'Ink 2', token: '--bn-ink-2', ink: true },
  { name: 'Ink 3', token: '--bn-ink-3', ink: true },
  /* no "Aa" sample: ink-4 is for icons, separators and edges, never for a word */
  { name: 'Ink 4, not for text', token: '--bn-ink-4' },
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
  { cls: 'bn-eyebrow', name: 'Eyebrow, mono caps', sample: 'Design system' },
  { cls: 'bn-label', name: 'Label, Inter caps', sample: 'This session' },
  { cls: 'bn-money', name: 'Money, tabular', sample: '$1,234.50' },
  { cls: 'bn-mono', name: 'Mono, machine strings', sample: '2026-09-02-box3-01' },
  { cls: 'bn-tnum', name: 'Tabular figures, Inter', sample: '1,625 cards, 443 SKUs' },
  { cls: 'bn-muted', name: 'Muted, ink-3', sample: 'Metadata and captions' },
  { cls: 'bn-faint', name: 'Faint, the faintest a word goes: ink-3', sample: 'The lightest word' },
]

const TYPE_SCALE: readonly { token: string; px: number; role: string }[] = [
  { token: '--bn-fs-5xl', px: 48, role: 'Home greeting' },
  { token: '--bn-fs-4xl', px: 36, role: 'Hero figure' },
  { token: '--bn-fs-3xl', px: 28, role: 'Page title' },
  { token: '--bn-fs-2xl', px: 22, role: 'Stat value, question' },
  { token: '--bn-fs-xl', px: 18, role: 'Section heading' },
  { token: '--bn-fs-lg', px: 16, role: 'Row primary' },
  { token: '--bn-fs-base', px: 14, role: 'Body' },
  { token: '--bn-fs-md', px: 13, role: 'Controls, table' },
  { token: '--bn-fs-sm', px: 12, role: 'Metadata' },
  { token: '--bn-fs-xs', px: 11, role: 'Label, pill' },
  { token: '--bn-fs-2xs', px: 10, role: 'Keycap, badge' },
]

const SPACES = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10'] as const
const RADII = ['xs', 'sm', '', 'lg', 'xl', '2xl', 'full'] as const
const VARIANTS: readonly ButtonVariant[] = ['default', 'primary', 'ghost', 'quiet', 'danger', 'danger-solid', 'ok']
const SIZES: readonly ButtonSize[] = ['sm', 'md', 'lg', 'xl']
const TONES: readonly PillTone[] = ['default', 'accent', 'ok', 'warn', 'danger', 'live']

// ------------------------------------------------------------------------- scaffolding

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

/* THE PAGE SCAFFOLD'S PARTS, drawn one by one. The page itself is `Page`: this sheet is one. */
const LONG_ANSWER =
  'The box you pressed is closed, so no divider can go into it now. Open it again from the ' +
  'capture screen first, then press here once more. Every card already in it stays exactly ' +
  'where it is, and nothing about its sections changes until you open it.'

/* THE KIT'S SELECT, never the operating system's menu: the owner's own gripe. */
function SelectSpecimen() {
  const [from, setFrom] = useState<'market' | 'low'>('market')
  return (
    <Select
      label="Price from"
      value={from}
      onChange={setFrom}
      options={[
        { value: 'market', label: 'Market price' },
        { value: 'low', label: 'Lowest listing' },
      ]}
    />
  )
}

function ScaffoldSpecimens() {
  const [said, setSaid] = useState<'none' | 'short' | 'long'>('none')
  const [sort, setSort] = useState<'new' | 'old'>('new')
  const [find, setFind] = useState('')
  return (
    <div className="kit-grid">
      <Spec name="verdict" label="verdict: where things stand" wide>
        <Verdict>12 cards are waiting to be priced.</Verdict>
      </Spec>
      <Spec name="toolbar" label="toolbar: folds as one unit" wide>
        <Toolbar label="Specimen filters">
          <SearchField persona="owner" value={find} onChange={setFind} placeholder="Find a card" label="Find a card" controlHeight="bar" />
          <Chip pressed>Unsold</Chip>
          <Chip>Sold</Chip>
          <Segmented
            value={sort}
            onChange={setSort}
            label="Sort"
            options={[
              { value: 'new', label: 'Newest' },
              { value: 'old', label: 'Oldest' },
            ]}
          />
        </Toolbar>
      </Spec>
      <Spec name="status-slot" label="status slot: holds its space" wide>
        <div className="kit-row kit-row-wrap">
          <Button size="sm" onClick={() => setSaid('short')} data-kit-answer="short">
            Press for an answer
          </Button>
          <Button size="sm" onClick={() => setSaid('long')} data-kit-answer="long">
            Press for a long answer
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setSaid('none')}>
            Clear
          </Button>
        </div>
        <StatusSlot>
          {said === 'short' ? (
            <Refusal title="This box is closed." code="box_closed" detail="POST /boxes/3/sections">
              Open it first.
            </Refusal>
          ) : said === 'long' ? (
            <Refusal title="This box is closed." code="box_closed" detail="POST /boxes/3/sections refused: the box is closed">
              {LONG_ANSWER}
            </Refusal>
          ) : null}
        </StatusSlot>
        <div className="bn-list-row kit-under-slot" data-kit-under-slot="">
          <Icon name="box" size={16} /> <span className="bn-grow">The row under the slot does not move</span>
        </div>
      </Spec>
      <Spec name="section" label="section: an h2 with its count" wide>
        <Section title="Recent boxes" count={3} actions={<Button size="sm" variant="ghost">All boxes</Button>}>
          <p className="bn-read">A part of a page. Its title is a heading a screen reader can jump to.</p>
        </Section>
      </Spec>
      <Spec name="loading" label="loading: rows, for a list" wide>
        <Loading rows={3} />
      </Spec>
      <Spec name="loading-cards" label="loading: cards, for a grid" wide>
        <Loading shape="cards" rows={4} />
      </Spec>
      <Spec name="loading-summary" label="loading: a summary band, for a screen that opens on figures" wide>
        <Loading shape="summary" />
      </Spec>
    </div>
  )
}

/* TWO SHAPES FOR "THAT DID NOT WORK", AND THE ONE RELOAD. */
function FailureSpecimens() {
  const [trying, setTrying] = useState(false)
  const [reloading, setReloading] = useState(false)
  const pulse = (set: (v: boolean) => void) => {
    set(true)
    window.setTimeout(() => set(false), 1600)
  }
  return (
    <div className="kit-grid">
      <Spec name="refusal" label="refusal: no retry">
        <Refusal title="This cannot be done in the demo." code="demo_read_only">
          Selling and pricing a card do work here.
        </Refusal>
      </Spec>
      <Spec name="retry" label="retry: shows that it is trying">
        <Retry title="The server did not answer." code="unreachable" busy={trying} onRetry={() => pulse(setTrying)} />
      </Spec>
      <Spec name="reload" label="reload: one place, one key">
        <div className="kit-row">
          <ReloadButton busy={reloading} onReload={() => pulse(setReloading)} hotkey={false} />
        </div>
      </Spec>
    </div>
  )
}

/* THE KIT'S OVERLAYS. One header, one Close, focus kept inside and given back. */
function OverlaySpecimens() {
  const [sheet, setSheet] = useState(false)
  const [modal, setModal] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const [pop, setPop] = useState(false)
  const [layered, setLayered] = useState(false)
  const [busyOpen, setBusyOpen] = useState(false)
  const [writing, setWriting] = useState(false)
  const write = () => {
    setWriting(true)
    window.setTimeout(() => {
      setWriting(false)
      setBusyOpen(false)
    }, 1500)
  }
  const [second, setSecond] = useState(false)
  const anchor = useRef<HTMLButtonElement>(null)
  return (
    <div className="kit-grid">
      <Spec name="overlays" label="sheet, modal, confirm, popover, two layers" wide>
        <div className="kit-row kit-row-wrap">
          <Button onClick={() => setSheet(true)} data-kit-open="sheet">
            Open a sheet
          </Button>
          <Button onClick={() => setModal(true)} data-kit-open="modal">
            Open a modal
          </Button>
          <Button variant="danger" onClick={() => setConfirm(true)} data-kit-open="confirm">
            Delete 3 cards
          </Button>
          <Button ref={anchor} iconRight="chevronDown" onClick={() => setPop((v) => !v)} aria-expanded={pop} data-kit-open="popover">
            Open a popover
          </Button>
          <Button variant="danger" onClick={() => setBusyOpen(true)} data-kit-open="busy-confirm">
            Delete 3 cards, slowly
          </Button>
          <Button onClick={() => setLayered(true)} data-kit-open="layered">
            Open two layers
          </Button>
        </div>
        <Sheet
          open={sheet}
          onClose={() => setSheet(false)}
          title="Set a hint"
          icon="tag"
          footer={
            <>
              <Button variant="primary" onClick={() => setSheet(false)}>
                Save
              </Button>
              <Button variant="ghost" onClick={() => setSheet(false)}>
                Cancel
              </Button>
            </>
          }
        >
          <Section title="The hint">
            <label className="bn-field">
              <span className="bn-field-label">Set</span>
              <input className="bn-input" defaultValue="ME01" data-autofocus="" />
            </label>
          </Section>
          {/* A CONFIRM OPENED FROM INSIDE AN OPEN SHEET — the second scrimmed layer a static
              per-class z-index cannot order against the first (a review finding, 2026-09-23):
              its own scrim has to sit above THIS sheet's panel, not merely above THIS sheet's
              own scrim. `gallery.spec.ts` asserts it. */}
          <div className="kit-row">
            <Button variant="danger" onClick={() => setConfirm(true)} data-kit-open="confirm-in-sheet">
              Delete while editing
            </Button>
          </div>
        </Sheet>
        <Modal open={modal} onClose={() => setModal(false)} title="One decision" footer={<Button onClick={() => setModal(false)}>Done</Button>}>
          <p className="bn-read">A modal stops the page for one decision.</p>
        </Modal>
        <Modal open={layered} onClose={() => setLayered(false)} title="The first layer">
          <div className="bn-stack">
            <p className="bn-read">A second layer opens over this one. Escape closes the top one first.</p>
            {/* A second paragraph, deliberately: both modals share the same fixed width (kit.css),
                so nothing but content height tells them apart, and one line of body text each
                left them the same height — no margin `gallery.spec.ts`'s own scrim-order test
                could probe. This one is genuinely taller than the layer opened over it. Never
                the words "second layer" here — `hasText` matches either modal on that phrase. */}
            <p className="bn-read">It stays taller than what opens over it, on purpose, so there is a real strip of it that stays uncovered.</p>
            <div className="kit-row">
              <Button onClick={() => setSecond(true)} data-kit-open="second">
                Open a second layer
              </Button>
            </div>
          </div>
        </Modal>
        <Modal open={second} onClose={() => setSecond(false)} title="The second layer">
          <div className="bn-stack">
            <p className="bn-read">Focus stays here until this layer closes.</p>
            <div className="kit-row">
              <Button onClick={() => setSecond(false)}>Done</Button>
            </div>
          </div>
        </Modal>
        <ConfirmSheet open={busyOpen} busy={writing} onClose={() => setBusyOpen(false)} onConfirm={write} title="Delete 3 cards?" confirmLabel="Delete 3 cards">
          <p className="bn-read">While it deletes, nothing closes this.</p>
        </ConfirmSheet>
        <ConfirmSheet open={confirm} onClose={() => setConfirm(false)} onConfirm={() => setConfirm(false)} title="Delete 3 cards?" confirmLabel="Delete 3 cards">
          <p className="bn-read">This cannot be undone. The photographs go too.</p>
        </ConfirmSheet>
        <Popover open={pop} onClose={() => setPop(false)} anchor={anchor} label="Specimen menu">
          <button type="button" className="bn-menu-item" onClick={() => setPop(false)}>
            <Icon name="divider" size={16} /> Put in a divider
          </button>
          <button type="button" className="bn-menu-item" onClick={() => setPop(false)}>
            <Icon name="tag" size={16} /> Set a hint
          </button>
        </Popover>
      </Spec>
    </div>
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
    <Page className="gallery" title="Kit" icon="grid" lede="Every primitive the screens are built from, drawn from the tokens.">
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
            id="kit-mark" data-kit-section="mark" className="kit-section"
            title="The mark"
            lede="Six marks. Bluesteel is the default."
          >
            <Spec
              label="The small cut, below 64px"
              wide
              note="What the app draws, at every size it draws."
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
              label="The display cut, 64px and up"
              wide
              note="The foil cut. Nothing in the app draws it this large."
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
              note="Dark in both themes."
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
            id="kit-lockup" data-kit-section="lockup" className="kit-section"
            title="The lockup"
            lede="番地 over BANCHI, inside the mark's brackets."
          >
            <Spec
              label="At the sizes it is drawn"
              wide
              note="The sidebar draws it at 40. Never below 32."
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
              note="On dark, the bracket takes the mark's metal."
            >
              {/* a real dark island rather than a dark rectangle: `data-theme` flips the tokens
                  AND the bracket's fill, so this shows the treatment rather than a light lockup
                  sitting on a dark ground */}
              <div className="kit-marks kit-lockup-dark" data-theme="dark">
                <span className="kit-mark"><Lockup size={40} /></span>
              </div>
            </Spec>
          </Section>

          <Section id="kit-page" data-kit-section="page" className="kit-section" title="Page" lede="Every screen is a Page: one width, one top gap, one h1, and these parts.">
            <ScaffoldSpecimens />
          </Section>

          <Section id="kit-color" data-kit-section="color" className="kit-section" title="Color" lede="Three registers: ink is what you read, line is what separates, brand is where to look. Indigo for action, vermilion for what is live.">
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

          <Section id="kit-type" data-kit-section="type" className="kit-section" title="Type" lede={<>Manrope for headings and big figures, Inter for everything, JetBrains Mono only for machine strings. Numbers in tables are Inter with <Code>tabular-nums</Code>.</>}>
            <div className="kit-faces">
              <div className="kit-face" style={{ fontFamily: 'var(--bn-font-display)', fontWeight: 800 }}>
                <span>Manrope</span>
                <span className="kit-face-role">display, headings, figures</span>
              </div>
              <div className="kit-face" style={{ fontFamily: 'var(--bn-font-ui)', fontWeight: 600 }}>
                <span>Inter</span>
                <span className="kit-face-role">ui, everything</span>
              </div>
              <div className="kit-face" style={{ fontFamily: 'var(--bn-font-mono)', fontWeight: 500 }}>
                <span>JetBrains Mono</span>
                <span className="kit-face-role">mono, SKUs, run names, codes, kbd</span>
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
            <div className="kit-headings" data-specimen="heading-scale">
              <div className="kit-heading-row">
                <span className="bn-title kit-heading-h1">Page title</span>
                <span className="bn-mono kit-type-px">h1, --bn-fs-h1</span>
              </div>
              <div className="kit-heading-row">
                <span className="bn-h2">A section</span>
                <span className="bn-mono kit-type-px">h2, --bn-fs-h2</span>
              </div>
              <div className="kit-heading-row">
                <span className="bn-h3">A part of a section</span>
                <span className="bn-mono kit-type-px">h3, --bn-fs-h3</span>
              </div>
              <div className="kit-heading-row">
                <span className="bn-read">A sentence a person must read is 13px or more.</span>
                <span className="bn-mono kit-type-px">--bn-fs-read</span>
              </div>
              <div className="kit-heading-row">
                <span className="bn-label">A label</span>
                <span className="bn-mono kit-type-px">--bn-fs-label</span>
              </div>
            </div>
          </Section>

          <Section id="kit-space" data-kit-section="space" className="kit-section" title="Space & radius" lede="A 4px scale, and radii from 4px to a pill.">
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

          <Section id="kit-elevation" data-kit-section="elevation" className="kit-section" title="Elevation" lede="Three shadows and an accent glow. Panels sit at 1, hover and dialogs rise.">
            <div className="kit-shadows">
              {['--bn-shadow-1', '--bn-shadow-2', '--bn-shadow-3', '--bn-shadow-accent'].map((s) => (
                <div key={s} className="kit-shadow" style={{ boxShadow: `var(${s})` }}>
                  <span className="bn-mono">{s.replace('--bn-', '')}</span>
                </div>
              ))}
            </div>
          </Section>

          <Section id="kit-motion" data-kit-section="motion" className="kit-section" title="Motion" lede="Three durations, three curves. Press a tile to play it.">
            <div className="kit-motions">
              {['--bn-t-fast', '--bn-t', '--bn-t-slow'].map((d) =>
                ['--bn-ease', '--bn-ease-out', '--bn-ease-spring'].map((e) => <MotionDemo key={d + e} duration={d} ease={e} />),
              )}
            </div>
          </Section>

          <Section id="kit-icons" data-kit-section="icons" className="kit-section" title="Icons" lede={<>{ICON_NAMES.length} icons on a 24 grid. One icon, one meaning.</>}>
            <div className="kit-icons">
              {ICON_NAMES.map((name: IconName) => (
                <div key={name} className="kit-icon">
                  <Icon name={name} size={20} />
                  <span className="bn-mono">{name}</span>
                </div>
              ))}
            </div>
            <dl className="bn-kv kit-meanings" data-specimen="icon-meanings">
              {Object.entries(ICON_MEANINGS).map(([name, meaning]) => (
                <div key={name} className="kit-meaning">
                  <dt>
                    <Icon name={name as IconName} size={16} /> <span className="bn-mono">{name}</span>
                  </dt>
                  <dd>{meaning}</dd>
                </div>
              ))}
            </dl>
          </Section>

          {/* -------------------------------------------------------------- primitives */}
          <Section id="kit-buttons" data-kit-section="buttons" className="kit-section" title="Buttons" lede="Seven variants, four sizes. Primary is the one thing to do; danger is red; money moments carry the figure in the label.">
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
                  Push 12 listings, $184.20
                </Button>
              </Spec>
            </div>
          </Section>

          <Section
            id="kit-icon-button"
            data-kit-section="icon-button"
            className="kit-section"
            title="Icon button"
            lede="A common, repeated action becomes an icon with a required label: the accessible name and the tooltip, never one or the other (owner's ruling, 2026-09-24). A press that spends money or cannot be undone keeps its words. docs/specs/iconography.md is the rule."
          >
            <div className="kit-grid">
              <Spec label="the vocabulary">
                <div className="kit-row kit-row-wrap">
                  <IconButton icon="sold" label="Mark sold" />
                  <IconButton icon="undo" label="Undo" />
                  <IconButton icon="archive" label="Retire" />
                  <IconButton icon="pencil" label="Edit" />
                  <IconButton icon="trash" label="Delete" tone="danger" />
                  <IconButton icon="eraser" label="Clear" />
                  <IconButton icon="copy" label="Copy" />
                  <IconButton icon="download" label="Download" />
                  <IconButton icon="external" label="Open" />
                  <IconButton icon="x" label="Close" />
                  <IconButton icon="filter" label="Filter" />
                  <IconButton icon="sortAsc" label="Low to high" />
                  <IconButton icon="sortDesc" label="High to low" />
                  <IconButton icon="moveTo" label="Move to a box" />
                  <IconButton icon="grip" label="Drag to reorder" />
                </div>
              </Spec>
              <Spec label="sizes" note="40px hit area at every size — only the 28-to-40px face shrinks, for a packed row.">
                <div className="kit-row kit-row-wrap">
                  {SIZES.map((s) => (
                    <IconButton key={s} icon="undo" label={`Undo (${s})`} size={s} />
                  ))}
                </div>
              </Spec>
              <Spec label="pressed, busy, badge and a longer name" note="Rest, hover, keyboard focus and a touch long-press draw the tooltip the same way — the check is what a browser actually shows, not a class this page could fake.">
                <div className="kit-row kit-row-wrap">
                  <IconButton icon="lock" label="Hold" pressed />
                  <IconButton icon="filter" label="Filters" badge={3} />
                  <IconButton icon="refresh" label="Reload" busy />
                  <IconButton icon="trash" label="Delete" tone="danger" disabled />
                  <IconButton icon="undo" label="Undo" kbd="U" name="Undo the sale at Section 2, Card 5" />
                </div>
              </Spec>
              <Spec
                label="the anchor form"
                note="`href` (plus `target`/`rel`) renders an `<a>` with the same face, hit area, tooltip and accessible name — an icon-only control that opens another route keeps the browser's own middle-click, right-click and copy-link, which a `window.open` in an `onClick` cannot give."
              >
                <div className="kit-row kit-row-wrap">
                  <IconButton icon="external" label="Cards to pull" href="#/fulfillment" target="_blank" rel="noreferrer" />
                </div>
              </Spec>
            </div>
          </Section>

          <Section id="kit-kbd" data-kit-section="kbd" className="kit-section" title="Keycaps" lede="A keycap sits after its label. On a touch screen a key hint leaves as a whole phrase.">
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
              <Spec name="keyhint" label="key hint: the phrase leaves with its keys">
                <p className="bn-read">
                  <KeyHint>
                    Press <Kbd>,</Kbd> then a letter to jump anywhere.
                  </KeyHint>
                </p>
              </Spec>
              <Spec label="in a button, on accent">
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
              <Spec label="row keycap, 28px" note="A target a finger lands on. It stays on a touch screen.">
                <div className="kit-row">
                  <kbd className="kit-keycap">1</kbd>
                  <kbd className="kit-keycap">2</kbd>
                  <kbd className="kit-keycap">3</kbd>
                  <kbd className="kit-keycap kit-keycap-blank">–</kbd>
                </div>
              </Spec>
            </div>
          </Section>

          <Section id="kit-pills" data-kit-section="pills" className="kit-section" title="Pills & dots" lede="Status in six tones. Live is vermilion and pulses.">
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
              <Spec label="with icon, mono, outline">
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

          <Section id="kit-fields" data-kit-section="fields" className="kit-section" title="Fields" lede="34px controls, 40px large. Focus is the accent ring, product-wide.">
            <div className="kit-grid">
              <Spec label="input, with hint">
                <label className="bn-field">
                  <span className="bn-field-label">Box name</span>
                  <input className="bn-input" defaultValue="RB Epics" />
                  <span className="bn-field-hint">Names are unique; case is folded.</span>
                </label>
              </Spec>
              <Spec label="input-wrap, icon and key">
                {/* A search box is `SearchField` (the toolbar specimen above). The wrap is for a
                    field that is not one: Capture's section note is the real case. */}
                <span className="bn-input-wrap">
                  <Icon name="list" size={16} />
                  <input className="bn-input" placeholder="A note for this section" aria-label="Section note" />
                  <Kbd>N</Kbd>
                </span>
              </Spec>
              <Spec label="select, textarea">
                <SelectSpecimen />
                <label className="bn-field">
                  <span className="bn-field-label">Note</span>
                  <textarea className="bn-textarea" defaultValue="Held back: bullish above $5." />
                </label>
              </Spec>
              <Spec label="large, mono, disabled">
                <label className="bn-field">
                  <span className="bn-field-label">Card name</span>
                  <input className="bn-input bn-input-lg" placeholder="Type the name of the card" />
                </label>
                <label className="bn-field">
                  <span className="bn-field-label">Run</span>
                  <input className="bn-input bn-input-mono" defaultValue="2026-09-02-box6-01" />
                </label>
                <label className="bn-field">
                  <span className="bn-field-label">Disabled</span>
                  <input className="bn-input" defaultValue="Not editable" disabled />
                </label>
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

          <Section id="kit-segmented" data-kit-section="segmented" className="kit-section" title="Segmented & tabs" lede="Segmented for a mode; tabs for a view.">
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
                <div className="bn-tabs" role="tablist" aria-label="Queue">
                  <button type="button" role="tab" className="bn-tab" aria-selected="true">
                    <Icon name="inbox" size={14} /> Review <Pill tone="warn">12</Pill>
                  </button>
                  <button type="button" role="tab" className="bn-tab" aria-selected="false" tabIndex={-1}>
                    <Icon name="flag" size={14} /> Parked <Pill>6</Pill>
                  </button>
                  <button type="button" role="tab" className="bn-tab" aria-selected="false" tabIndex={-1}>
                    <Icon name="check" size={14} /> Answered
                  </button>
                </div>
              </Spec>
            </div>
          </Section>

          <Section id="kit-notice" data-kit-section="notice" className="kit-section" title="Notice" lede="Four tones. The machine's own words sit behind What the server said.">
            <div className="kit-grid">
              <Spec label="info">
                <Notice title="The export is fetched to a scope this process names">Every card of this game carries a set hint, so the scope is one set.</Notice>
              </Spec>
              <Spec label="warn">
                <Notice tone="warn" title="Two runs are joined but neither is emitted">
                  Emit them together, so the live cap is spent once.
                </Notice>
              </Spec>
              <Spec name="notice-said" label="danger, with what the server said">
                <Notice tone="danger" title="The answer was refused" code="sku_not_a_candidate" detail="POST /review/2/14/answer">
                  The queue changed after this screen read it. Reload to see it as it is now.
                </Notice>
              </Spec>
              <Spec label="ok">
                <Notice tone="ok" title="Reconciled">
                  405 SKUs read a live count for the first time.
                </Notice>
              </Spec>
            </div>
          </Section>

          <Section id="kit-failure" data-kit-section="failure" className="kit-section" title="Refusal & retry" lede="A refusal offers no retry. A retry shows that it is trying.">
            <FailureSpecimens />
          </Section>

          <Section id="kit-overlays" data-kit-section="overlays" className="kit-section" title="Sheets & popovers" lede="One header, one Close. Focus stays inside and goes back where it was.">
            <OverlaySpecimens />
          </Section>

          <Section id="kit-receipt" data-kit-section="receipt" className="kit-section" title="Receipt & toast" lede="A receipt is an undo anchored beside the thing it undoes, draining over its window. A toast is the same shape, floating.">
            <div className="kit-grid">
              <Spec label="receipt, draining" wide>
                <div className="bn-receipt" style={{ ['--receipt-ms' as string]: '20000ms' }}>
                  <Icon name="check" size={16} style={{ color: 'var(--bn-ok)' }} />
                  <span className="bn-grow">
                    <strong>Answered as Near Mint Holofoil</strong>
                    <span className="bn-mono" style={{ display: 'block', fontSize: 11, opacity: 0.65 }}>
                      Box 2, Section 1, Card 14
                    </span>
                  </span>
                  <span className="bn-receipt-bar" />
                  <Button size="sm" icon="undo" kbd="U">
                    Undo
                  </Button>
                </div>
              </Spec>
              <Spec label="toast, receipt / ok / refusal" wide>
                <div className="kit-toasts">
                  <div className="bn-toast bn-toast-receipt">
                    <Icon name="undo" size={16} className="bn-toast-icon" />
                    <div className="bn-toast-text">
                      <div className="bn-toast-title">Marked sold</div>
                      <div className="bn-toast-body">Box 3, Section 2, Card 15</div>
                    </div>
                    <button type="button" className="bn-toast-action">
                      Undo <kbd className="bn-kbd">U</kbd>
                    </button>
                    {/* THE REAL MARKUP, NOT A REDRAWN COPY (round 2's own finding): a hand-rolled
                        <button> here could not catch the contrast regression `Toaster` itself
                        had — the dismiss glyph inherited the wrong colour and axe never saw a
                        real `.bn-icon-btn` to measure. `IconButton` is what `kit/toast.tsx`
                        actually renders. */}
                    <IconButton icon="x" label="Dismiss" size="sm" className="bn-toast-close" />
                  </div>
                  <div className="bn-toast bn-toast-ok">
                    <Icon name="check" size={16} className="bn-toast-icon" />
                    <div className="bn-toast-text">
                      <div className="bn-toast-title">Import file written</div>
                      <div className="bn-toast-body">437 copies, one file</div>
                    </div>
                  </div>
                  <div className="bn-toast bn-toast-refusal">
                    <Icon name="alert" size={16} className="bn-toast-icon" />
                    <div className="bn-toast-text">
                      <div className="bn-toast-title">The store is busy</div>
                      <div className="bn-toast-body">Try again in a moment.</div>
                    </div>
                  </div>
                </div>
              </Spec>
            </div>
          </Section>

          <Section id="kit-empty" data-kit-section="empty" className="kit-section" title="Empty state" lede="A real sentence and one way onward. At zero it should feel like a reward.">
            <div className="kit-grid">
              <Spec label="empty" wide>
                <div className="bn-panel">
                  <EmptyState
                    icon="check"
                    title="All caught up."
                    body="You answered 16 cards in 4 min 12 s, 2 closed."
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

          <Section id="kit-skeleton" data-kit-section="skeleton" className="kit-section" title="Skeleton & progress" lede="Reserve the shape while the server answers; move the bar when the operator does.">
            <div className="kit-grid">
              <Spec label="skeleton">
                <div className="bn-skeleton" style={{ height: 22, width: '60%' }} />
                <div className="bn-skeleton" style={{ height: 14, width: '40%' }} />
                <div className="bn-skeleton" style={{ height: 56 }} />
                <div className="bn-skeleton" style={{ height: 56 }} />
              </Spec>
              <Spec label="progress, default and ok">
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

          <Section id="kit-data" data-kit-section="data" className="kit-section" title="Data" lede="Key/value pairs, a table, list rows. Numbers right-aligned and tabular.">
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
              <Spec name="table" label="table" wide>
                <div className="bn-panel kit-table-scroll" role="region" aria-label="Table specimen" tabIndex={0}>
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
                        ['Snorlax', 'Near Mint Holofoil', '8608002', 143.65, 1],
                        ['Charizard ex', 'Near Mint', '8607411', 12, 3],
                        ['Bidoof', 'Near Mint', '8601230', 0.12, 14],
                      ].map(([name, cond, sku, market, n]) => (
                        <tr key={String(sku)}>
                          <td>{name}</td>
                          <td>{cond}</td>
                          <td className="bn-mono">{sku}</td>
                          <td className="num">
                            <Money value={Number(market)} />
                          </td>
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
                    <Icon name="box" size={16} /> <span className="bn-grow">Box 3, RB Epics</span> <Pill>723</Pill>
                  </button>
                  <button type="button" className="bn-list-row" aria-current="true">
                    <Icon name="box" size={16} /> <span className="bn-grow">Box 4, WB1 R2</span> <Pill tone="accent">56</Pill>
                  </button>
                  <button type="button" className="bn-list-row">
                    <Icon name="box" size={16} /> <span className="bn-grow">Box 5, UNL BBOX C/UC 1</span> <Pill>105</Pill>
                  </button>
                </div>
              </Spec>
            </div>
          </Section>

          <Section id="kit-surfaces" data-kit-section="surfaces" className="kit-section" title="Surfaces & menu" lede="A panel is raised, a well is sunken, a menu pops.">
            <div className="kit-grid">
              <Spec label="panel, head and body">
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
              <Spec label="well, rule">
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

          <Section id="kit-data-kit" data-kit-section="data-kit" className="kit-section" title="Money, filters & links" lede="Money, counts, dates, filters, sort, and the links that open a product or an order.">
            <DataSpecimens />
          </Section>

          <Section id="kit-filtering" data-kit-section="filtering" className="kit-section" title="Filter bar" lede="One filter bar, one hide toggle, one sortable table header, and the match highlight — composed from the pieces above.">
            <FilterSpecimens />
          </Section>

          {/* ------------------------------------------------------------ screen pieces */}
          <Section id="kit-pull-confirm" data-kit-section="pull-confirm" className="kit-section" title="Pull-confirm" lede="The one solid fill the Fulfiller ever sees. Three states, and the owner-side key hint.">
            <div className="kit-stack kit-stack-narrow">
              <Spec name="default" label="default, the Fulfillment case">
                <PullConfirm label="Pull this card" onConfirm={noop} />
              </Spec>
              <Spec name="pressed" label="pressed" forcePressed>
                <PullConfirm label="Pull this card" onConfirm={noop} />
              </Spec>
              <Spec name="disabled" label="disabled" note="Never drawn for the Fulfiller.">
                <PullConfirm label="Pull this card" onConfirm={noop} disabled />
              </Spec>
              <Spec name="with-key" label="default + key hint, owner-side only">
                <PullConfirm label="Pull this card" onConfirm={noop} keyHint="↵" />
              </Spec>
            </div>
          </Section>

          <Section id="kit-position" data-kit-section="position" className="kit-section" title="Position bar" lede={<>How far into its box a card sits. A closed box earns a percentage; an open one counts what is in it.</>}>
            <div className="kit-stack">
              <Spec name="bar-closed" label="closed box, 250 cards">
                <PositionBar place={CLOSED_BOX} />
              </Spec>
              <Spec name="bar-open" label="open box, the denominator still moves">
                <PositionBar place={OPEN_BOX} />
              </Spec>
              <Spec name="bar-single" label="one section, no dividers declared">
                <PositionBar place={SINGLE_SECTION} />
              </Spec>
              <Spec name="bar-unknown" label="no fraction, the server declined to say">
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
              <Spec name="bar-depth" label="the section as the ruler, a divided box">
                <PositionBar place={CLOSED_BOX} sections={BOX_SECTIONS} sectionDepth />
              </Spec>
              <Spec name="bar-depth-gone" label="departed, the ruler stays and both marks leave it">
                <PositionBar place={DEPARTED} sections={BOX_SECTIONS} sectionDepth />
              </Spec>
            </div>
          </Section>

          <Section id="kit-position-label" data-kit-section="position-label" className="kit-section" title="Position label" lede="One ranking, three flows: stacked, slot-led for a column, and run for a sentence.">
            <div className="kit-grid">
              <Spec label="stack, path-led">
                <div className="kit-poslabel" style={{ ['--pos-slot' as string]: '32px' }}>
                  <PositionLabel label="Box 3 · Section 2 · Card 15" />
                </div>
              </Spec>
              <Spec label="stack, slot-led">
                <div className="kit-poslabel" style={{ ['--pos-slot' as string]: '32px' }}>
                  <PositionLabel label="Box 3 · Section 2 · Card 15" lead="slot" />
                </div>
              </Spec>
              <Spec label="run, in a sentence">
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

          <Section id="kit-search" data-kit-section="search" className="kit-section" title="Search field" lede="The owner's carries a / hotkey and its chip; the Fulfiller's carries neither and keeps a visible label.">
            <div className="kit-stack">
              <Spec name="search-owner" label="owner, dense, with the key chip">
                <FieldSpecimen persona="owner" />
              </Spec>
              <Spec name="search-fulfiller" label="fulfiller, large, no keys">
                <FieldSpecimen persona="fulfiller" />
              </Spec>
            </div>
          </Section>

          <Section id="kit-locations" data-kit-section="locations" className="kit-section" title="Card locations" lede="One card and every row shape it draws, for the owner and for the Fulfiller.">
            <div className="kit-stack">
              <Spec
                name="locations-owner"
                label="owner, a bar on every row that has one"
                note="The pooled and departed copies draw no position."
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
                label="owner, one copy, no SKU"
                note="A card not yet identified draws no listing figures."
              >
                <div className="kit-copies">
                  <CardLocations group={LOOSE_GROUP} persona="owner" onSell={noop} busyKey={null} soldKeys={new Set()} />
                </div>
              </Spec>
              <Spec name="locations-fulfiller" label="fulfiller, every copy is its own card" note="A drawn specimen, not a stored photograph.">
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
    </Page>
  )
}
