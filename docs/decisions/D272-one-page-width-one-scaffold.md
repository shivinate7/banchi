# D272 — One page width, one scaffold

**This amends D197.** D197 fixed the left edge and let the width vary by screen. This removes the second half. There is one page width, 1600 px, and every screen must stay competent at every narrower width. The owner ruled both points.

**What D197 protected, and what protects it now.** D197 protected one left edge for every screen. That rule stands. `.bn-page` keeps `margin: 0`, and `app/tests/page-edge.spec.ts` still asserts the edge. What goes is D197's sentence that "a pricing table and a three-column inventory legitimately want different caps". Measured by the review (UX-144): three caps (1120, 1344 and 1600 px) gave three right edges, and at 1440 px Pricing stopped 84 px short of the screens beside it.

**The scaffold is `Page`, in `app/src/kit/Page.tsx`.** A new page must inherit the properties of the other pages, so the frame every page shares lives in one component:

- `<main class="bn-page" data-bn-page>` with one h1. The h1 is the route's `title ?? label`, read from `PageRouteContext`, which the shell provides.
- One width: `--bn-page-w`, fluid below it. A `Page` ignores `--bn-page-max`.
- One top gap: `--bn-page-top` (UX-133). It is 24 px, and 16 px below 768, the phone's own page inset.
- The page is the query container `bn-page`. A tier follows the column that the shell gave, not the window. At 720 px the owner's half-width Chrome window draws the desktop rail, and the column is not the phone's column.
- One place for the verdict (UX-068). One toolbar that folds as one unit.
- One status slot that holds its space (D118). One loading shape (UX-098). One empty state.
- `Section` draws an h2 (UX-095).

**A new screen is one `ROUTES` entry plus a view that returns `<Page>`.** A `Page` with no title and no route around it prints a console error in dev, because a page with no h1 looks correct.

**Why `[data-bn-page]` and not `.bn-page`.** Screens not yet on `Page` still draw a bare `.bn-page` and may set `--bn-page-max`. The one-width rule reads `[data-bn-page]`, so it reaches a screen when that screen moves onto `Page`, and not before. Each screen lane deletes its dead `--bn-page-max` when it moves. When the last screen moves, `--bn-page-max` and `--bn-page-w-rows` have no reader, and they go.

**Enforced by** `app/tests/scaffold.spec.ts` (the frame, per route and per width) and `make kit-adoption` (a routed view that skips `Page` fails).
