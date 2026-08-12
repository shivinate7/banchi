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
drawings of a specification, and step 7 builds the real thing from the doc, not from this
markup.

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
