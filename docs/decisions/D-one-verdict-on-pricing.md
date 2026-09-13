## D-one-verdict-on-pricing — Pricing states its verdict once, and the worklist discloses progressively

**The owner's two rulings, batch 4 (2026-09-13).**

**Ruling A: one verdict, the headline.** `#/pricing` stated readiness in three places at once —
the headline deck (`PricingVerdict`/`ReadyPanel`, "Ready to write" / "Not ready yet" plus a
`.pricing-verdict-says` sentence, a four-chip `.pricing-meter` bar, and `.pricing-verdict-fine`),
and the single-run ship bar's own `pricing-ship-verdict` button — a second Ready/Not-yet
`bn-pill` plus a `.pricing-ready` span that recomputed and restated the exact same
standing/typed/held sentence, with a `showDeck` press that scrolled back to the headline it was
duplicating. Two accounts of the same figures is how one of them goes stale first.

The fix: the four count chips (`.pricing-meter`/`.pricing-meter-keys` inside `ReadyPanel`) are
deleted — `.pricing-verdict-says` already states every figure they carried, once, in prose. The
single-run ship bar's `pricing-ship-verdict` button, its pill, its restated sentence and the
`showDeck` walk-back are deleted outright. The bar is now the press and its two controls: the
cut-off split checkbox, the cap field, and the primary Write button — no status text, no pill,
no back-to-top control. The merged-run bar and the lens bar keep their own `.pricing-ready
pricing-ship-says` sentences unchanged — those are MECHANISM explanations (what the merge
dedupes, what a markdown write does), never a second readiness verdict, and the brief's "no
restated status" was never about them.

`LiveVerdict`'s own three-part key strip (a *different* headline, for the live-inventory lens,
not "Ready to write") is untouched — it was never the ruling's subject, and `.pricing-meter-keys`
CSS stays because that component still draws it, without a bar beside it.

**Ruling B: the worklist row discloses progressively.** A row drew, unconditionally, up to four
of five badges (live-count, box/run-span, an over-cap claim sentence, a withheld-note quote) plus
all four SNAPS reference cells (Market/Low/+Ship/Direct). The default row now shows: the card
identity, the Qty field, the price field, one market figure (Market only), the live-count badge,
the withheld-note badge when present, and the over-cap warning badge when present — always,
regardless of any toggle.

**Behind a per-section "Compare" toggle** (one control per `pricing-section`, not per row — 400+
rows would each carry their own toggle state otherwise; `compareOn: Record<string, boolean>`
keyed by `section.bucket`): the Low/+Ship/Direct SNAPS cells, and the plain box/run-span text
("Box N · M runs") when it is not carrying an over-cap warning.

**The over-cap warning itself (`sku.over_cap === true`) is never gated by Compare** — D156
already promises "what cannot go is named on the deck, with a door each," and an over-cap row
is exactly that case; hiding it behind a toggle would be hiding a refusal.

**`l`/`s`/`d` act only while Compare is on for that row's section; `m` always works.** D118
forbids a press moving what's around it; a key reaching a figure the operator cannot currently
see is the same defect one register down, and D49's whole argument for a closed keyboard
alphabet — "a letter is unambiguously a command" — breaks when the command reaches an invisible
column even though it never touches D49's literal prohibition. `onKey`'s `SNAPS.find` branch now
refuses `l`/`s`/`d` when `compareOn[sku.bucket]` is false; `m` is unconditional.

**"Nothing loaded." now waits for the fetch.** `chrome`'s scope caption drew "Nothing loaded."
unconditionally whenever `loaded.length === 0`, including while `loading` was `true` and
`SkeletonRows` was on screen below it — asserting a completed, empty answer during a request that
had not finished. It now renders `null` while `loading`, matching D156's own caption branches
(scopeName/run/box), which already return `null` rather than a placeholder string when a fact
isn't known yet.

**The stranded-run tooltip stopped naming a CLI command.** `UnreachableLine`'s reallocated-run
badge said `` Run `pkmnscan rescue` to rebind it `` — a repository-internal command name in a
seller-facing string, which `no mechanism on screen` already forbids in spirit even though this
particular string is a `title` tooltip rather than a rendered label. It now says "Drawer number
reused since this run — rebind it from the run's row on Runs," naming the screen rather than the
shell command.

**The cut-off strip's four words got a visible legend (plan 3 Group J #23).** The
`.pricing-scope-progress` span's `typed`/`held`/`on the rule`/`cheap` breakdown was a `title`
attribute — hover-only, invisible without a mouse. A `.pricing-scope-legend` paragraph, reached
by `aria-describedby`, now spells the four words out once, visibly, beside the figures; the
figures and their split are unchanged.

**One un-wrapping metadata line was the page's own horizontal scrollbar (mobile finding #6).**
`.pricing-live`'s `white-space: nowrap` held "· 3 live · read 1 day ago · 5 when read, 2 sold
since" on one line regardless of the row's width, pushing the whole page 8px past a 390px phone
and 265px past a 768px tablet. It wraps now (`white-space: normal; flex-wrap: wrap`).

**The 390 ship bar stacks, full width.** `.pricing-ship-act`'s children wrapped unpredictably by
label length at narrow widths — exactly how a control clips (mobile finding #1, the walkthrough's
originally-flagged defect). Under `max-width: 1023px` the controls now stack in a fixed column
(split checkbox, cap field, Write button last, full width); `.pricing-ship-status` collapses to
`display: none` when empty (the single-run bar's header row after the verdict pill's removal).

### What this amends

**`D156`** gains one sentence (see that entry's own amendment, dated to this decision): the
per-run box/run span on an ordinary row is disclosure-gated behind Compare; an over-cap row's
warning stays named regardless.

**`D103`, `D105`, `D99`, `D98`, `D86`, `D7`, `D50`, `D118`** govern this work and are read but not
amended — they describe file semantics, controls and interaction floors this batch's JSX
restructuring does not change the behavior of. See `.../scratchpad/plans/4-pricing.md` for the
full per-decision reading that confirmed each needs no edit.

### Guard

`app/tests/pricing.spec.ts` is rewritten red-first: the two cases that asserted the ship bar's
`.pricing-ready` restated readiness now assert `.pricing-deck-title`/`.pricing-verdict-says`
instead; a regression pin keeps the over-cap warning visible with Compare off; new cases assert
the Compare toggle's default-off state, that Low/+Ship/Direct are hidden until toggled, that
`l`/`s`/`d` are inert with Compare off and live once it is on, and that "Nothing loaded." is
absent while a delayed fetch is still in flight. `make design-check ARGS=--wait
PW_ARGS="tests/pricing.spec.ts"` is the guard that runs them.

### Copy ratchet

`D194`'s ratchet on `#/pricing`'s word count (pinned in `app/tests/copy-budget.json`) is measured
against the empty/"Nothing loaded" landing fixture (`copy-budget.spec.ts`'s own known gap — it
does not stub a loaded worklist), so it sees Ruling A's headline simplification but not Ruling
B's row-level cuts. The headline-only verdict is expected to lower the pinned figure; see this
PR's own report for the measured before/after.
