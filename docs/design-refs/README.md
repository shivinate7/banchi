# Design references

Two rendered sheets behind the token block in `docs/DESIGN.md`, committed 2026-08-12.

| File | What it is |
|---|---|
| `locked.html` | The chosen design, drawn: palette, spacing scale, the three faces, the review queue's disagreement screen, the queue list, and step 6's pull-confirm in all three states. |
| `rejected.html` | The alternatives that lost, each with the verdict on it: two grounds, three display faces, the panel header strip, both solid-fill rules, and two reason-code treatments. |

Open them in a browser. They are static — no build step, no server.

## Why these are in the repo

`docs/DESIGN.md` argues that a screenshot beats an adjective, and that an agent given
"clean" produces the average of everything it has seen. A file that makes that argument
while its own visual references live in a scratchpad directory contradicts itself the
moment the session ends. Hex values substitute for colour; they do not substitute for
layout, density, or the difference between a queue row and a spreadsheet row.

`rejected.html` earns its place separately. A negative constraint that a later session
cannot *see* reads as taste, and taste gets overturned by the first person with different
taste. "Not NYT/FT" is an argument once you have looked at the version that was.

## What these are not

**Not a source of truth.** `docs/DESIGN.md` is. If a value here disagrees with the doc, the
doc is right and this directory is stale. Nothing reads these files programmatically and
`scripts/docs-audit.py` does not check the hex values inside them, so that staleness will
not announce itself — treat a token change in the doc as a change here too.

**Not the app.** No component in `pkmnscan` imports anything from this directory. These are
drawings of a specification, and `app/` builds the real thing from the doc, not from this
markup.

## Known disagreements with the doc

Found 2026-08-12 by building step 6's component from `docs/DESIGN.md` and comparing. Listed
rather than patched: these sheets record what was rendered and chosen during the interview,
and editing them afterwards would turn a record into a second draft. `docs/DESIGN.md` wins
both, per the rule above.

- **`locked.html` draws the pull-confirm label at 18px** (`.btn`, `font-size: 18px`). The
  Fulfillment constraints table puts a 20px floor on every text node in that view, and a
  button label is a text node. The component is built at 20px and
  `app/tests/pull-confirm.spec.ts` asserts it.
- **`locked.html` draws a `↵` key chip on all three pull-confirm states.** "Every choice
  shows its key" is an owner-side rule — the doc says the Fulfiller's screens are touch and
  show none, and the pull-confirm is his. The component takes `keyHint` as optional and
  renders no chip without it.

Both were invisible while the tokens were prose and a drawing. That is the argument for
build-order step 6 existing at all, and it is worth knowing that the step paid out on its
first component.

- **`locked.html` predates `field`, added to the palette 2026-08-26.** This is a MISSING token
  rather than a disagreeing one, which is a different kind of staleness and worth naming
  separately: the two entries above are places the sheet is WRONG and the doc wins, and this is
  a place the sheet is INCOMPLETE. `field` is `#8C8C8C`, the boundary of a control you type
  into, and it is the only colour in the palette that exists for a contrast criterion rather
  than for the interview — `docs/DESIGN.md` carries the argument and the render that refused
  the whole-palette version of it. Nothing audits these sheets, by the rule at the top of this
  file, so this line is what stops the omission being discovered by someone drawing a field
  from the wrong reference.

## Two constraints that shaped them

**No card photographs.** `scripts/githooks/pre-commit` blocks any image staged outside
`captures/` — the code-card opsec rule, which is deliberately blunt about file extensions
rather than clever about content. The cards in both sheets are therefore synthetic
rectangles at `geometry/detect.py`'s `CARD_ASPECT` (63/88), with a title band and an art
window standing in for what `geometry/crop.py` cuts. The choosers these were distilled from
did use a real eval image, and the ground was judged against it; that comparison happened
and is not reproducible here. Embedding the same bytes as a data URI would have passed the
hook while committing exactly what it exists to stop, so it was not done.

**Webfonts load from two CDNs.** Cabinet Grotesk comes from Fontshare, Atkinson Hyperlegible
and Martian Mono from Google Fonts. Offline, both sheets fall back to system faces and
everything except the typography still reads correctly. Self-hosting is a step 7 question,
tied to the Fontshare licence that `docs/DESIGN.md` flags as unread.
