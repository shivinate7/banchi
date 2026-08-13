import type { ReactNode } from 'react'
import { PullConfirm } from './PullConfirm'
import './Gallery.css'

/* Every state of step 6's component on one page.
 *
 * docs/DESIGN.md: "Claude Code writes CSS it has never looked at, so a layout that is
 * technically correct can still be broken." This page is what gets looked at — by
 * `make screenshot` into captures/ui/, and by `make design-check`, which asserts the
 * Fulfillment floors the render cannot prove on its own.
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

export function Gallery() {
  return (
    <main className="gallery">
      <h1 className="gallery-title">Pull-confirm, three states</h1>
      <p className="gallery-lede">
        Build-order step 6's one component, built against the tokens locked 2026-08-12. The
        solid fill is legal here because there is exactly one thing to do. Floors asserted in{' '}
        <code>app/tests/pull-confirm.spec.ts</code>, never in this page's prose.
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
    </main>
  )
}
