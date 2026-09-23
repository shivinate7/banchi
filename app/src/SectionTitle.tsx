import type { SectionTitleParts } from './position'

/** ONE SECTION TITLE, IN TWO PARTS, FOR EVERY BOX-WALK LIST (`#/inventory`'s shelf and
 *  `#/orders`' walk). When the column is too narrow, the NAME is the part cut short and the COUNT
 *  always stays whole: the count is the one fact a hand checks against the rows under it, and a
 *  title that cuts it says nothing a row can be checked against.
 *
 *  The comma rides the count's own span, so the element's text is `sectionTitleText`'s whole
 *  sentence, exactly, and the comma is never cut away from the count it introduces. A comma is
 *  punctuation in a real sentence, never a typed separator dot (D218). */
export function SectionTitle({ parts }: { parts: SectionTitleParts }) {
  return (
    <span className="browse-secttitle">
      <span className="browse-secttitle-head">{parts.head}</span>
      {parts.count === null ? null : <span className="browse-secttitle-count">, {parts.count}</span>}
    </span>
  )
}
