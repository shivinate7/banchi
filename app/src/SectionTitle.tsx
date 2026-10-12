import type { SectionTitleParts } from './position'

/** ONE SECTION TITLE FOR EVERY BOX-WALK LIST (`#/inventory`'s shelf and `#/orders`' walk).
 *
 *  THE NAME IS WHOLE AND THE COUNT IS SAID ONCE (LOC-21, UX-223). The section's name is the label
 *  on the physical divider, so it wraps rather than being cut (`BoxBrowse.css`). Both lists draw
 *  the section's count in a pill beside this title, so the title's own count is spoken and not
 *  drawn: it rides `.bn-sr`, and the element's text is still `sectionTitleText`'s whole sentence
 *  for a screen reader and for a spec. A comma is punctuation in a real sentence, never a typed
 *  separator dot (D218). */
export function SectionTitle({ parts }: { parts: SectionTitleParts }) {
  return (
    <span className="browse-secttitle">
      <span className="browse-secttitle-head">{parts.head}</span>
      {parts.count === null ? null : <span className="browse-secttitle-count bn-sr">, {parts.count}</span>}
    </span>
  )
}
