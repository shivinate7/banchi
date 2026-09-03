import { useState, type ReactNode } from 'react'

import type { Place, SearchGroup } from './types'
import { PullConfirm } from './PullConfirm'
import { PositionBar } from './PositionBar'
import { SearchField } from './SearchField'
import { CardLocations } from './CardLocations'
import './Gallery.css'

/* Every state of the shared components on one page.
 *
 * docs/DESIGN.md: "Claude Code writes CSS it has never looked at, so a layout that is
 * technically correct can still be broken." This page is what gets looked at — by
 * `make screenshot` into captures/ui/, and by `make design-check`, which asserts the
 * Fulfillment floors the render cannot prove on its own.
 *
 * IT STARTED AS STEP 6'S ONE COMPONENT AND IS NOW THE PAGE FOR ALL OF THEM. The pull-confirm's
 * four specimens are unchanged and keep their `data-specimen` names, because
 * app/tests/pull-confirm.spec.ts selects on exactly those and measures the vertical gaps
 * between them — new specimens go in their own containers below rather than between, so that
 * test keeps measuring the row it was written about.
 *
 * NOTHING HERE IS WIRED TO A SERVER, and the search-and-sell components are the first ones
 * where that shows. The fixtures below are invented: no run has produced a `GET /search`
 * answer, and the Fulfiller's photos resolve to `GET /photo/...` on a capture server this page
 * does not require, so they fail to load and the copy card draws its missing-photo sentence
 * instead. That is a real state worth having on the page — it is what he sees when a photo was
 * undone out from under a card — and it is the only one this render can show.
 */

type SpecimenProps = {
  name: string
  caption: string
  note?: string
  /** Gallery-only: holds :active still so it can be screenshotted and measured. */
  forcePressed?: boolean
  children: ReactNode
}

function Specimen({ name, caption, note, forcePressed, children }: SpecimenProps) {
  return (
    <section data-specimen={name} data-force-state={forcePressed ? 'pressed' : undefined}>
      <div className="specimen-caption">{caption}</div>
      {children}
      {note === undefined ? null : <p className="specimen-note">{note}</p>}
    </section>
  )
}

// Nothing here is wired to anything. The gallery proves the component renders and
// measures up; what a press actually does arrives with step 7's pull modal.
const noop = () => {}

/* ---------------------------------------------------------------------------- fixtures ----
 *
 * Hand-built, and in the server's own field names so that comparing this page against a real
 * `GET /search` is a read rather than a translation — the rule types.ts states for the wire
 * types themselves.
 *
 * THE NUMBERS ARE CHOSEN TO MAKE ONE DISTINCTION VISIBLE and not to look plausible: a closed
 * box knows its size and gets a percentage, an open box does not and never claims one. That is
 * the whole reason PositionBar exists, and a gallery of four bars that all say the same thing
 * would prove nothing about it.
 */

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

const OPEN_BOX = place({
  label: 'Box 7 · Section 1 · Card 12',
  box: 7,
  index: 12,
  section: 1,
  card: 12,
  box_name: null,
  section_start: 1,
  section_end: null,
  box_total: 62,
  box_closed: false,
  fraction: 12 / 62,
})

/* D10: an empty divider list means undeclared, and the 25-rule renders it — so the server
 * still sends a section, and a box the operator has not divided arrives as one span with no
 * end. One segment, which is what an undivided box is, and not an error. */
const SINGLE_SECTION = place({
  label: 'Box 9 · Section 1 · Card 4',
  box: 9,
  index: 4,
  section: 1,
  card: 4,
  box_name: 'Bulk, unsorted',
  section_start: 1,
  section_end: null,
  box_total: 80,
  box_closed: true,
  fraction: 0.05,
})

/* The refusal case. `fraction: null` is the server declining to say, and types.ts is explicit
 * that it is not zero — a marker at zero points at the front of the box, which is a specific
 * and wrong place to send somebody, and it looks exactly like a correct answer. */
const NO_FRACTION = place({
  label: 'Box 4 · Section 1 · Card 1',
  box: 4,
  index: 1,
  section: 1,
  card: 1,
  box_name: null,
  section_start: 1,
  section_end: null,
  box_total: 0,
  box_closed: false,
  fraction: null,
})

const GROUP: SearchGroup = {
  sku: '8421991',
  names: ['Thievul'],
  number: '108',
  printed_total: '198',
  /* What the server composes and the screen draws (D67). Spelled out rather than derived: the
     gallery is a fixture of the WIRE, and a field it computed for itself would stop being one. */
  number_display: '108/198',
  set_hint: 'me01',
  condition: 'Near Mint',
  listed: { pushed: 0, staged: 1, live: 2 },
  /* Four copies, three on hand: D7 counts UNSOLD positions here while `copies` carries the
     sold one as well, because D10 keeps a sold record at a permanent gap. The two numbers
     disagreeing is the contract, not a fixture mistake. */
  on_hand: 3,
  cap: 4,
  /* min(cap, on_hand) — the fixture exists to draw the case where the SHELF binds rather than
     the cap, which is most of the store and was the bug: `of 4` on three copies. */
  listable: 3,
  /* `capture_id` ON EVERY ROW BUT ONE, and the null is the specimen (D93): a record written
     before ids were kept cannot be aimed at, so the order walk draws a reason where the take
     would be. A gallery whose every copy carried one would never show that row. */
  copies: [
    { key: '3/40', state: 'identified', state_at: null, has_photo: true, capture_id: 'cap-3-40', place: CLOSED_BOX },
    { key: '7/12', state: 'identified', state_at: null, has_photo: true, capture_id: 'cap-7-12', place: OPEN_BOX },
    { key: '9/4', state: 'captured', state_at: null, has_photo: false, capture_id: null, place: SINGLE_SECTION },
    { key: '4/1', state: 'sold', state_at: null, has_photo: true, capture_id: 'cap-4-1', place: NO_FRACTION },
  ],
}

/* The field is controlled, so a specimen of it needs somewhere for the text to live. Local to
 * this page: a gallery is the one place in the app where a component's state has no owner
 * above it. */
function FieldSpecimen({ persona }: { persona: 'owner' | 'fulfiller' }) {
  const [text, setText] = useState(persona === 'owner' ? 'thievul' : '')
  return <SearchField value={text} onChange={setText} persona={persona} />
}

export function Gallery() {
  return (
    <main className="gallery">
      <h1 className="gallery-title">Component gallery</h1>
      <p className="gallery-lede">
        The components the screens are built out of, against the tokens locked 2026-08-12.
        Floors are asserted in <code>app/tests/pull-confirm.spec.ts</code>, never in this page's
        prose.
      </p>

      <h2 className="gallery-heading">Pull-confirm, three states</h2>
      <p className="gallery-lede">
        Build-order step 6's one component. The solid fill is legal here because there is
        exactly one thing to do.
      </p>

      <div className="gallery-specimens">
        {/* Captions name the state and nothing else. The contrast ratios are published in
            docs/DESIGN.md and asserted in the spec; a third copy here would be a number
            nothing checks, sitting on the one screen that looks authoritative. */}
        <Specimen name="default" caption="default · the Fulfillment case">
          <PullConfirm label="Pull this card" onConfirm={noop} />
        </Specimen>

        <Specimen name="pressed" caption="pressed" forcePressed>
          <PullConfirm label="Pull this card" onConfirm={noop} />
        </Specimen>

        <Specimen
          name="disabled"
          caption="disabled"
          note="Never appears in the Fulfillment view — that view has no disabled state at all."
        >
          <PullConfirm label="Pull this card" onConfirm={noop} disabled />
        </Specimen>

        <Specimen
          name="with-key"
          caption="default + key hint · owner-side only"
          note="The Fulfiller's screens are touch and show no keys, so the chip is omitted there. docs/design-refs/locked.html draws it on all three pull-confirm states; the doc wins and the sheet is stale."
        >
          <PullConfirm label="Pull this card" onConfirm={noop} keyHint="↵" />
        </Specimen>
      </div>

      <h2 className="gallery-heading">Position bar, four boxes</h2>
      <p className="gallery-lede">
        How far into its box a card sits. The distinction the whole component exists for is
        between the first two: a closed box knows its size and earns a percentage, an open one
        does not and says <code>so far</code> instead.
      </p>

      <div className="gallery-specimens gallery-specimens-wide">
        <Specimen
          name="bar-closed"
          caption="closed box · 250 cards, 10 sections"
          note="Three segments and two ticks, which are the only boundaries a single Place states. The full tiling needs sections_detail off GET /boxes — see spansOf for why it is not derived from this section's width."
        >
          <PositionBar place={CLOSED_BOX} />
        </Specimen>

        <Specimen
          name="bar-open"
          caption="open box · the denominator still moves"
          note="No percentage, by rule. The same card would read 30% today and 12% next week without having moved."
        >
          <PositionBar place={OPEN_BOX} />
        </Specimen>

        <Specimen
          name="bar-single"
          caption="one section · a box with no dividers declared"
          note="D10: an empty divider list means undeclared and the 25-rule renders it. One segment is a real box, not a missing answer."
        >
          <PositionBar place={SINGLE_SECTION} />
        </Specimen>

        <Specimen
          name="bar-unknown"
          caption="no fraction · the server declined to say"
          note="Empty track and a sentence. Null is not zero: a marker at zero points at the front of the box, which is a specific and wrong place to send somebody."
        >
          <PositionBar place={NO_FRACTION} />
        </Specimen>

        <Specimen
          name="bar-fulfiller"
          caption="the Fulfiller's density · same markup, same sentence"
        >
          <PositionBar place={CLOSED_BOX} persona="fulfiller" />
        </Specimen>
      </div>

      <h2 className="gallery-heading">Search field, both personas</h2>
      <p className="gallery-lede">
        The owner's carries a <code>/</code> hotkey and shows its chip; the Fulfiller's carries
        neither, and its label is visible because a placeholder disappears exactly when somebody
        unsure would want to re-read it.
      </p>

      <div className="gallery-specimens gallery-specimens-wide">
        <Specimen name="search-owner" caption="owner · dense, with the key chip">
          <FieldSpecimen persona="owner" />
        </Specimen>

        <Specimen name="search-fulfiller" caption="fulfiller · large, no keys">
          <FieldSpecimen persona="fulfiller" />
        </Specimen>
      </div>

      <h2 className="gallery-heading">Card locations, both personas</h2>
      <p className="gallery-lede">
        One card, four copies, one of them sold. Same group, same order, same actions — the
        prop that differs is <code>persona</code>.
      </p>

      <div className="gallery-specimens gallery-specimens-wide">
        <Specimen
          name="locations-owner"
          caption="owner · a bar on every row, never on hover"
          note="The owner ruled against hover: how far into the box is the thing he opened the screen for, and a fact you have to point at is a fact you compare one at a time."
        >
          <CardLocations
            group={GROUP}
            persona="owner"
            onSell={noop}
            busyKey={null}
            soldKeys={new Set()}
          />
        </Specimen>

        <Specimen
          name="locations-fulfiller"
          caption="fulfiller · every copy is its own card"
          note="Photos resolve against the capture server, which this page does not require — so they fail to load here and each card draws its missing-photo sentence. That is the state he sees when a photo was undone out from under a card."
        >
          <CardLocations
            group={GROUP}
            persona="fulfiller"
            onSell={noop}
            busyKey={null}
            soldKeys={new Set()}
          />
        </Specimen>
      </div>
    </main>
  )
}
