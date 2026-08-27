import { useCallback, useEffect, useId, useState, type ReactNode } from 'react'

import type {
  BoxClaimResult,
  BoxDeleteResult,
  BoxRecord,
  GameEntry,
  BoxListingPlan,
  BoxListingRow,
  ListingReleaseResult,
  Place,
  SectionDetail,
} from './types'
import type { Failure } from './server'
import {
  applyBoxClaims,
  createBox,
  deleteBox,
  describeFailure,
  getBoxListings,
  getGames,
  releaseBoxListings,
  updateBox,
} from './server'
import { spansOf } from './PositionBar'
import './BoxOps.css'

/* The box operations — D20's object, made visible and editable, BESIDE THE BOX THEY ACT ON.
 *
 * THIS WAS A SCREEN AND IS NOW A COMPONENT (D31, 2026-08-23), and the entry is worth reading
 * before this file is changed. `#/boxes` held the registry and the layout editor with no way
 * into a box's contents at all, while `#/pull` walked a box's cards with photographs and could
 * say nothing about the box itself. The owner named it: three routes over one set of 767
 * records that "read as separate instances of one thing". So the route is gone, `BoxOps` below
 * draws onto the box header inside `BoxBrowse.tsx`'s walk, and `RegisterBox` sits beside the
 * strip that selects a box. Nothing about what a box IS changed — every paragraph below is
 * D20's argument unaltered, and the only thing this file lost is a `<main>`.
 *
 * WHY THAT MOVE IS THE RIGHT ONE AND NOT MERELY SMALLER: every control here names one box, and
 * on the old screen the box it named was a heading four hundred pixels above a divider field.
 * Rendered onto the header of the walk you are reading, `Seal box — freezes capacity at 85` is
 * a sentence about the cards immediately under it.
 *
 * WHY THIS SCREEN EXISTED AT ALL. Before D20 there was no box object anywhere in the repo: a
 * box existed because a card named one, so it could not be created empty, could not be named,
 * could not be listed anywhere but the capture screen's picker, and a mistyped number was
 * caught only by the `new_box` flag AFTER a photo had been written — which catches the first
 * typo and no other. That entry gave `store/master.py` a `Box`; this is where a human meets it.
 *
 * FOUR CONTROLS, AND THEY ARE THE FOUR THINGS D20 SAYS A BOX HAS THAT A PERSON DECIDES: what
 * it is called, where its dividers are, whether the lid is on, and whether it exists yet. Its
 * NUMBER is not among them and there is no control for it — that would be a renumber, which
 * D10 forbids outright, and every position key, photo directory and printed label is built
 * from it.
 *
 * SEALING IS THE ONE THAT MATTERS AND IT IS DRAWN THAT WAY. D20 makes capacity retroactive:
 * a box has none while it is open, and sealing freezes it at the final high-water mark. From
 * that moment every fraction in the product divides by that number — it is the difference
 * between "#40 of 53 so far" and "#40 of 250 · 16% in", and the second sentence is the whole
 * reason the object exists. So the control SAYS THE NUMBER IT WILL FREEZE before it is
 * pressed. A button reading "Seal box" alone would be a permanent decision taken against a
 * denominator the owner would have to go and find.
 *
 * OWNER-SIDE, and the Fulfillment floors do not bind — this component speaks the store's own
 * vocabulary (`fill`, `capacity`, `next index`, `sections`) on purpose, because the person
 * reading it is the person who will compare it against `inventory.json` when something is
 * wrong. D5 puts the plain register on the other persona's screens.
 *
 * NOTHING IS READ HERE AND NOTHING IS KEPT. `Inventory.tsx` states the rule and it applies
 * unchanged: D13 has exactly one place inventory lives, and a browser-side copy produces two
 * answers to "how is this box laid out" with one of them stale. Every write route answers with
 * the box row it wrote, and this component deliberately does NOT patch that answer into
 * anything — it calls `onChanged`, and the owner of the read (`BoxBrowse.tsx`) re-reads
 * `GET /boxes` and `GET /inventory` together. Both matter after a divider edit: D10 as amended
 * makes Section and Card a VIEW of an index, so moving a divider changes every card
 * decoration in the box as well as the box row.
 *
 * THE DELETE ARRIVED, AND SO DID A FIFTH CONTROL THE FOUR-CONTROL PARAGRAPH ABOVE DID NOT
 * ANTICIPATE. This file used to end by saying whole-box delete was "a server gap rather than a
 * choice" — no route, no client function, nothing to move — and naming the gate it would need
 * when it landed. It landed. `DeleteBox` below is that control under exactly that gate, which
 * the server keeps itself (`box_not_empty_of_commitments`, naming the cards), and it is the one
 * place in this app that gates: see its own header for why typing the box number beats an "are
 * you sure".
 *
 * The fifth control is `ClaimEditor` — retroactive capture claims over a whole box or over a
 * selection of it, `PUT /inventory/<box>`. It is not one of D20's four because it is not about
 * the box at all: it is about the cards in it, reached through the box because that is the unit
 * the route takes. It sits here because the SCOPE is a box, and because the same editor is what
 * `BoxBrowse.tsx` draws to correct one card — one form, two scopes, one enumeration of the
 * store's `CAPTURE_CLAIM_FIELDS` on this side.
 *
 * BOTH EXISTED AS ROUTES WITH NO CONTROL, WHICH IS THE FAILURE `CLAUDE.md` NOW HAS A HARD RULE
 * ABOUT: a route is not a feature, and nothing is built until it is reachable from a screen.
 * They shipped with full T7 coverage and zero client functions, `make check` green throughout.
 */

/** The word `state` carries when the lid is on. `types.ts:BoxState` is the union the wire
 *  ACCEPTS; this is the one value read back off disk that this screen branches on, and the
 *  type is deliberately loose on the read side for the reason that file gives. */
const CLOSED = 'closed'

/** One write at a time, and the reason is not politeness. `Store.write()` takes the file lock
 *  per call and waits up to thirty seconds for it, so two edits issued together stack against
 *  a lock and return out of order — and one of them may be a seal, which is permanent. */
type Busy = boolean

/**
 * Every write in this file, with its lock discipline, its refusal handling and its re-read in
 * one place rather than in five.
 *
 * THE RE-READ IS THE POINT, and it belongs to the caller. All three routes answer with the box
 * row they wrote, and merging that answer into held state is the tempting shortcut — it is also
 * how a screen comes to hold a second copy of the store. So this hook calls `onChanged` and
 * says nothing about what that re-reads; `BoxBrowse.tsx` re-reads the boxes AND the inventory,
 * because a divider edit relabels every card in the box (D10 as amended: the label is a view of
 * the index) and a box panel that refreshed alone would sit above a walk still drawing the old
 * sections.
 *
 * `write` RETURNS WHETHER IT SUCCEEDED so a caller can close its own editor on success and
 * leave it open on a refusal — the field still holding what was typed, beside the message
 * saying why it was refused.
 */
function useBoxWrite(onChanged: () => void): {
  busy: Busy
  trouble: Failure | null
  write: <T>(run: () => Promise<T>) => Promise<T | null>
} {
  const [busy, setBusy] = useState<Busy>(false)
  const [trouble, setTrouble] = useState<Failure | null>(null)

  /* GENERIC IN THE ANSWER, NOT JUST IN THE CALL. It was `Promise<BoxRecord> -> Promise<boolean>`
   * while the three routes it wrapped all answered a box row; the box-wide claim answers a
   * `BoxClaimResult`, whose numbers ARE the receipt, and a wrapper that threw that away would
   * have forced a fourth hand-rolled copy of the lock-and-refusal discipline beside it. `null`
   * for a refusal keeps the existing `if (await onWrite(...))` call sites reading exactly as
   * they did — a written row is truthy, a refusal is not. */
  const write = useCallback(
    async <T,>(run: () => Promise<T>): Promise<T | null> => {
      if (busy) return null
      setBusy(true)
      setTrouble(null)
      try {
        const answer = await run()
        onChanged()
        return answer
      } catch (err) {
        /* The server's own message, verbatim, with its code beneath. `_fail` already says what
         * happened and what to do next — `box_exists`, `sections_invalid`, `box_closed` all
         * name the remedy — and paraphrasing them here would be a second vocabulary nothing
         * audits. */
        setTrouble(describeFailure(err))
        return null
      } finally {
        setBusy(false)
      }
    },
    [busy, onChanged],
  )

  return { busy, trouble, write }
}

/** The refusal panel both components draw, in the owner idiom: the server's sentence, then the
 *  greppable code beneath it and never the sentence again — docs/DESIGN.md's human-label-large,
 *  machine-string-small rule. Owner-side only; the Fulfillment banned-word list forbids this
 *  register entirely and no Fulfillment route renders these classes. */
function Trouble({ failure }: { failure: Failure | null }) {
  if (failure === null) return null
  return (
    <div className="boxops-note">
      <p className="boxops-note-text">{failure.message}</p>
      <p className="boxops-machine">{failure.code}</p>
    </div>
  )
}

/** `1 card` / `4 cards`. A fourth small copy of this in the app; `Inventory.tsx` has two and
 *  `CardLocations.tsx` the third, and each was written on a day the others were not writable.
 *  All four say so. A shared module is the fix, and this is the count that makes the case. */
function count(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`
}

/** A number off the wire, or null for anything that is not one.
 *
 *  `GET /boxes` answers `fill`, `next_index` and `capacity` as null on purpose — a box with no
 *  readable position takes the first two to null while still counting its records, and an open
 *  box has no capacity at all. NULL IS NOT ZERO here for the reason `Place.fraction` states it:
 *  zero is a specific claim about a box, and "not known" is not that claim. */
function known(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

/** The dividers the box is actually rendered with, read off the server's own spans.
 *
 *  NOT `record.sections`, AND THE DIFFERENCE IS THE ONE D10 CARES ABOUT. That field is the
 *  DECLARED list and an empty one means undeclared — which D10 says the default rule then
 *  renders. A screen that read `[]` as "no dividers" would draw one undivided box over a box
 *  that has them, and a screen that filled in the default itself would own a copy of D10's
 *  divider size that nothing keeps in step with `pipeline/join.py`.
 *
 *  `sections_detail` is that rendering, computed once by the one process that imports
 *  `Position`. Reading the starts back off it is presentation, not arithmetic: every number
 *  came from the server. */
function rendered(record: BoxRecord): number[] {
  return record.sections_detail
    .map((detail) => detail.start)
    .filter((start): start is number => typeof start === 'number' && Number.isFinite(start))
}

/**
 * The indices in a divider field, or null when the text is not a list of numbers.
 *
 * THE RULE IS NOT CHECKED HERE. D10's layout rule — first divider at index 1, climbing, no
 * repeats — lives in `store/master.py:check_sections`, which refuses rather than repairing
 * precisely so that a silently sorted layout cannot relabel a box without saying so. This
 * turns a text field into a JSON array and stops. `[31, 1]` is sent and refused as
 * `sections_invalid`, with the server's own message naming the rule, which is one place the
 * rule is written down instead of two.
 *
 * An empty field is `[]`, which is a real request meaning undeclared — not "leave it alone".
 * Omitting the field is what leaves it alone, and this screen only sends it on a save.
 *
 * `.match` RATHER THAN `.split`. A separator class is the obvious tool and `app/eslint.config.js`
 * bans `split` on anything containing a comma outright, matching the regex form as well as the
 * literal — v1 bug 2, naive CSV parsing. The rule is broader than this call needs and that is
 * the point of it; matching the tokens directly asks nothing of the exception list.
 */
function readIndices(text: string): number[] | null {
  const tokens = text.match(/[^\s,]+/g) ?? []
  const out: number[] = []
  for (const token of tokens) {
    if (!/^\d+$/.test(token)) return null
    out.push(Number(token))
  }
  return out
}

/** The declared layout as a field's worth of text. Blank for an undeclared box, which is what
 *  the field means: leave it blank and the default rule renders the box. */
function writeIndices(record: BoxRecord): string {
  return record.sections.join(', ')
}

/**
 * A `Place` carrying this box's own numbers into `spansOf`, and carrying nothing else.
 *
 * THIS IS A VEHICLE AND NOT A POSITION CLAIM, which is the distinction types.ts draws on
 * `Place` and the reason this function has a comment at all. `spansOf(place, sections)` reads
 * exactly two things off the place when a section list is supplied — `box_total`, to clamp
 * against, and `index`, to decide which span the card is in — and computes every span from the
 * server's `sections_detail`. There is no card here, so `index` is 0: outside every span, so
 * no segment comes back `current`, which is correct for a drawing of a whole box.
 *
 * The forbidden thing is section arithmetic — deriving a boundary from an index and a divider
 * size — and none happens: `sections_detail` is the server's own rendering and this hands it
 * over rather than reconstructing it. `label` is empty because nothing reads it; a made-up
 * label would be the one field on this object that could be mistaken for a claim.
 */
function trackPlace(record: BoxRecord, total: number): Place {
  return {
    label: '',
    box: record.box,
    index: 0,
    section: 0,
    card: 0,
    box_name: record.name,
    section_start: 1,
    section_end: null,
    box_total: total,
    box_closed: record.state === CLOSED,
    fraction: null,
  }
}

/** The denominator this box is drawn against: its frozen capacity if it has one, else its fill
 *  so far. `server/capture_server.py:_denominator` makes the same choice for every `place`
 *  block in the product, and the two must agree — a box reading "40 of 250" on one screen and
 *  "40 of 53" on another is the second-renderer failure with a number instead of a label. */
function denominator(record: BoxRecord): number {
  return known(record.capacity) ?? known(record.fill) ?? 0
}

/**
 * The first index at which two layouts start disagreeing, or null when they agree.
 *
 * `Math.min` on a differing pair rather than the new value, because the relabel begins at the
 * EARLIER of the two: moving a divider from 31 to 26 changes what card 26 is called, and
 * moving it from 26 to 31 changes what card 26 is called too. Taking the proposed value alone
 * would under-report the first case and the sentence built from it would name too few cards.
 */
function firstChange(before: readonly number[], after: readonly number[]): number | null {
  const reach = Math.max(before.length, after.length)
  for (let at = 0; at < reach; at += 1) {
    const was = before[at]
    const now = after[at]
    if (was === undefined) return now ?? null
    if (now === undefined) return was
    if (was !== now) return Math.min(was, now)
  }
  return null
}

/** Which sections a relabel reaches, and how many cards are in them.
 *
 *  COUNTED OFF `sections_detail` AND NEVER OFF `fill`, and the difference is honesty. The
 *  tempting arithmetic is `fill - from + 1`, which is exact only if every index from 1 to the
 *  high-water mark is occupied — true today and an assumption about the store rather than a
 *  fact from it. `SectionDetail.count` is a real count of real records, so summing the sections
 *  the change reaches is a number the server stands behind. It rounds UP to a section boundary,
 *  which the sentence at the call site says out loud. */
function reached(record: BoxRecord, from: number): { sections: number[]; cards: number } {
  const hit = record.sections_detail.filter((detail: SectionDetail) => {
    const end = known(detail.end)
    // A section with no end is the open end of an open box: it runs to the back, so any change
    // at or before the back of the box is inside it.
    return end === null || end >= from
  })
  return {
    sections: hit.map((detail) => detail.section),
    cards: hit.reduce((total, detail) => total + (known(detail.count) ?? 0), 0),
  }
}

/* Register a box before a card goes into it — D20's whole reason for existing.
 *
 * THE BOX THAT HOLDS NOTHING IS THE POINT. Before this route the first thing that declared box
 * 4 was a photograph landing in it, so a typo like 33 for 3 was a valid integer, a real photo
 * and eventually a real listing. Typing the number once, on a screen, with every existing box
 * listed underneath it, is the fix.
 *
 * NO CAPACITY FIELD, EVER. D20: nobody knows a box's capacity when they start filling it, and
 * a number accepted here would be a guess that every fraction later drawn from the box
 * inherits. It is not omitted for brevity; the route does not accept one.
 *
 * IT SITS BESIDE THE STRIP THAT SELECTS A BOX (D31), which is where "with every existing box
 * listed underneath it" now literally holds: the strip IS that list, one cell per box, and the
 * typo this control exists to prevent is visible as a cell that is not there.
 */
export function RegisterBox({ onChanged }: { onChanged: () => void }) {
  const { busy, trouble, write } = useBoxWrite(onChanged)
  const onCreate = (input: { box: number; name?: string; sections?: number[] }) =>
    write(() => createBox(input))
  const [open, setOpen] = useState(false)
  const [number, setNumber] = useState('')
  const [name, setName] = useState('')
  const [dividers, setDividers] = useState('')
  const [refused, setRefused] = useState<string | null>(null)

  const submit = async () => {
    const box = readIndices(number)
    /* Exactly one number, and it is a box number rather than a divider list — the same reader
     * because the question is the same one (is this text a whole number), and the check here is
     * that there is precisely one of them. */
    if (box === null || box.length !== 1 || box[0] === undefined) {
      setRefused('A box number is a whole number, like 3.')
      return
    }
    const sections = readIndices(dividers)
    if (sections === null) {
      setRefused('Dividers are the card number each section starts at, like 1, 31, 56.')
      return
    }
    setRefused(null)

    const ok = await onCreate({
      box: box[0],
      ...(name.trim() === '' ? {} : { name: name.trim() }),
      /* Omitted when blank rather than sent as `[]`, and the two are different requests: `[]`
       * declares the box undeclared and omitting leaves its layout alone. On a box being
       * created they land in the same place, and sending the honest one keeps the history
       * event off a layout nobody typed. */
      ...(sections.length === 0 ? {} : { sections }),
    })
    if (ok) {
      setNumber('')
      setName('')
      setDividers('')
      setOpen(false)
    }
  }

  if (!open) {
    return (
      <div className="boxops-new">
        <button className="boxops-plain" type="button" onClick={() => setOpen(true)}>
          Register a box
        </button>
      </div>
    )
  }

  return (
    <div className="boxops-new boxops-new-open">
      <p className="boxops-new-head">Register a box</p>
      <div className="boxops-fields">
        <Field label="Box number" value={number} onChange={setNumber} placeholder="3" />
        <Field label="Name (optional)" value={name} onChange={setName} placeholder="SV commons" />
        <Field
          label="Dividers (optional)"
          value={dividers}
          onChange={setDividers}
          placeholder="1, 31, 56"
        />
      </div>
      <p className="boxops-hint">
        Dividers are the card number each section starts at, so the first is always 1. Leave it
        blank and the box uses the default divider size until you say otherwise. Capacity is not
        asked for here and never will be — it is frozen when the box is sealed.
      </p>
      {refused === null ? null : <p className="boxops-machine">{refused}</p>}
      <Trouble failure={trouble} />
      <div className="boxops-actions">
        <button
          className="boxops-plain"
          type="button"
          disabled={busy}
          onClick={() => void submit()}
        >
          Register
        </button>
        <button className="boxops-plain" type="button" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </div>
  )
}

/* One box: what it holds, how it is divided, and the four things that can be done to it.
 *
 * DRAWN ONTO THE HEADER OF THAT BOX'S OWN WALK (D31). What is always visible is the reading —
 * number, name, lid, the fill or the frozen capacity, and the track — because those are what a
 * person glancing at the top of a list of cards wants to know. The layout table, the store's
 * own field names and all four controls sit inside one disclosure beneath it.
 *
 * THE DISCLOSURE IS A DENSITY DECISION AND IT HAS A MEASUREMENT BEHIND IT. On `#/boxes` this
 * panel drew every box at once, 304-355px each, so four boxes made 1744px of scroll — 1.9
 * screens at 1440x900 to read four rows of information. Here exactly one box is drawn, and its
 * editors are one press away rather than permanently occupying the space above the cards. What
 * is NOT behind the disclosure is the seal's own sentence when it is pressed: D20 requires the
 * number on the button, and it is still on it.
 */
/* WHAT THIS BOX IS, drawn at the top of the walk rather than in a panel beside it.
 *
 * SPLIT OUT OF `BoxOps` ON 2026-08-25, when the box moved into the column that IS the box. The
 * owner: "merge its functionality (so not visual merge, but rebuild type merge) and all exist on
 * the left side". A panel headed `Box 2` sitting next to a column headed `BOX [2]`, re-listing
 * the sections that column already walks, was D31's finding repeating one scale down — two
 * renderings of one thing, and the inert one was the one with the title.
 *
 * So the readings come here, above the walk, where the box strip already names the box; the
 * OPERATIONS stay in `BoxOps` and go below the walk, beside `Register a box`. Two components
 * because they sit in two places, not because they are two subjects.
 *
 * NO BORDER AND NO PANEL. Everything in this column is part of one column; a bordered card here
 * would put a second box around the box. The hairline under it is the same separator the rest of
 * the file uses and the only one this system has. */
export function BoxIdentity({
  record,
  at = null,
}: {
  record: BoxRecord

  /** Where the selected card sits in this box, 0..1 — the server's own `fraction`. Null for no
   *  selection, a card in another box, or a pooled card, and the marker is not drawn. */
  at?: number | null
}) {
  /* The same four readings `BoxOps` takes below, from the same helpers — `CLOSED` rather than
     the literal, `record.fill` rather than an index arithmetic of our own, and the spans through
     `spansOf(trackPlace(...))` so this track and that one cannot disagree about a divider. */
  const sealed = record.state === CLOSED
  const fill = known(record.fill)
  const total = denominator(record)
  const spans = spansOf(trackPlace(record, total), record.sections_detail)

  return (
    <div className="boxops-identity">
      {/* NAME AND STATE ON ONE ROW WITH THE FILL, which is three facts in the height the header
          alone used to take. The box NUMBER is not repeated — `.browse-boxline` directly above
          this is the box strip, and it is already the answer to "which box". */}
      <p className="boxops-identity-line">
        {record.name === null ? null : (
          <span className="boxops-identity-name">{record.name}</span>
        )}
        <span className="boxops-identity-fill">
          {sealed && record.capacity !== null
            ? `${record.capacity} sealed`
            : fill === null
              ? 'fill unread'
              : `${fill} so far`}
        </span>
        <span className={sealed ? 'boxops-state boxops-state-sealed' : 'boxops-state'}>
          {sealed ? 'sealed' : 'open'}
        </span>
      </p>

      {/* THE TRACK IS THE BOX, one segment per section, each as wide as the run of cards it
          holds. It survives the merge where the section LIST did not, and the difference is that
          this is not a list: the walk beneath says which sections exist and how many cards are in
          each, and this says how they are shaped relative to one another.

          IT CARRIES A MARKER NOW, AND THIS COMMENT SAID IT NEVER WOULD (owner, 2026-08-25): "use
          this bar either via fill or an arrow above it to constantly be indicating where in the
          box im looking". The old sentence — "a marker means 'this card is here' and the walk
          owns that" — was true about the walk and wrong about the reader. The walk says which
          ROW you are on out of eighty-five in one section; it cannot say you are a fifth of the
          way into the box, because it only ever shows one section's worth of rows at a time.
          That is the same argument D20 makes for the box object existing at all: a bare index
          tells you nothing about where to put your thumb, and a fraction does.

          A MARKER AND NOT A FILL, which is the half the owner left open and which this repo has
          already settled. `PositionBar.tsx` refuses a travelled-distance fill in as many words:
          there is no token meaning "quiet fill" — `--hover` is documented as row hover only,
          `--line` is the 1px hairline, and `--accent` has two jobs of which this is neither —
          and the lesson `--on-accent` taught here is that the answer to "no token means what I
          mean" is a token argued for in docs/DESIGN.md, never a literal painted at the call
          site. So: the same 2px ink marker the copy rows already carry, from the same field.

          THE SERVER'S `fraction`, NEVER RECOMPUTED. `PositionBar` states the rule and the reason:
          `index / box_total` disagrees with it across a sealed box's frozen capacity, and two
          markers on one screen derived two ways would drift against each other by a pixel or by
          a section. */}
      {spans.length === 0 ? null : (
        <div
          className="boxops-track"
          role="img"
          aria-label={`Box ${record.box}, ${spans.length} sections`}
        >
          {spans.map((span) => (
            <span
              className="boxops-span"
              key={`${span.start}-${span.end}`}
              style={{ flexGrow: span.end - span.start + 1 }}
            />
          ))}
          {at === null ? null : (
            <span
              className="boxops-mark"
              style={{ left: `${Math.min(100, Math.max(0, at * 100))}%` }}
              aria-hidden="true"
            />
          )}
        </div>
      )}

      {/* The store's own field names, verbatim, so what is on screen greps to what is in
          `inventory.json`. `cards` counts records naming this box and `fill` is the high-water
          mark — they are different numbers and both are wanted, because the gap between them is
          exactly how many holes the box has.

          `sections 1 86 171 253 394` WAS HERE AND IS NOT, which is a deletion rather than a
          shortening: the walk below draws every one of those boundaries as a section header you
          can fold, tick and step into, so this printed the same list a third time on one screen.
          The field names that remain are still verbatim — the rule this comment states is about
          not prettifying `next_index`, not about carrying every field regardless of what is
          already on screen.

          LAST IN THE IDENTITY BLOCK, BETWEEN THE TWO THINGS IT RECONCILES (2026-08-25). `544
          sealed` is one line above it and the walk's own section counts are directly below, and
          for box 2 those counts sum to exactly `fill`: 85+85+82+141+150 = 543, against a section
          5 spanning #394-#544 — 151 slots holding 150 cards, which is the mid-box delete D36 was
          found by. Down among the operations these four numbers were the LAST reading in a
          sticky column capped at the viewport, so with the sections open they were not
          co-visible with `544 sealed` at any scroll position. The rule above says the field
          names are verbatim so a person can compare them against `inventory.json`; that
          comparison needs both halves on screen at once. */}
      <p className="boxops-meta">
        cards {record.cards} · sold {record.sold} · fill {fill ?? 'unknown'} · next index{' '}
        {known(record.next_index) ?? 'unknown'}
      </p>
    </div>
  )
}

export function BoxOps({
  record,
  onChanged,
  selection = [],
}: {
  record: BoxRecord
  onChanged: () => void

  /** The indices the walk currently has ticked, in this box. THE MASS-SELECT, arriving from the
   *  list that owns it: `BoxBrowse.tsx` draws the checkboxes because they belong on the rows,
   *  and this panel spends them because `PUT /inventory/<box>` is the write they are for.
   *
   *  EMPTY MEANS THE WHOLE BOX, and that is safe here in a way it is NOT on the wire.
   *  `server.ts:applyBoxClaims` omits `indices` entirely for a whole-box apply and the server
   *  refuses `[]` on purpose — an emptied selection widening to every card in the box is the
   *  accident that refusal exists to stop. So the widening happens once, here, where the scope
   *  sentence on the button says which of the two is about to happen. */
  selection?: readonly number[]
}) {
  const { busy, trouble, write } = useBoxWrite(onChanged)
  const onWrite = (patch: { name?: string; sections?: number[]; state?: 'open' | 'closed' }) =>
    write(() => updateBox(record.box, patch))
  /* Which editor is open, or null. One at a time per box: two open fields over one record is
   * two half-finished edits racing for the same lock. */
  const [editing, setEditing] = useState<'name' | 'sections' | 'claims' | null>(null)
  const [draft, setDraft] = useState('')
  const [refused, setRefused] = useState<string | null>(null)
  /* The last box-wide apply's receipt, or null. Held past the editor closing because the
   * numbers are the only evidence of what a write over eighty-five records actually did. */
  const [claimed, setClaimed] = useState<BoxClaimResult | null>(null)

  /* What an apply will reach, said the same way on the heading and on the button. The
     selection when there is one, the whole box when there is not — the widening argued at
     `selection` above, in words rather than in a silent `?? all`. */
  const scope =
    selection.length > 0
      ? `the ${count(selection.length, 'selected card', 'selected cards')}`
      : `all ${count(record.cards, 'card', 'cards')} in box ${record.box}`

  const applyClaims = async (patch: ClaimPatch) => {
    const result = await write(() =>
      applyBoxClaims(
        record.box,
        patch,
        selection.length > 0 ? [...selection] : undefined,
      ),
    )
    if (result !== null) {
      setClaimed(result)
      setEditing(null)
    }
  }

  /* The parsed layout waiting on the owner's answer to the relabel warning, or null. A separate
   * state from the draft because the warning is a statement about a PARSED layout — it names
   * the first index that moves and counts what sits behind it, and neither is knowable from the
   * text. */
  const [proposed, setProposed] = useState<number[] | null>(null)

  const sealed = record.state === CLOSED
  /* Still read here, and only for the SEAL BUTTON'S LABEL — D20 requires the number on the
     control that freezes it. `capacity`, `total` and the spans moved to `BoxIdentity` with the
     readings they draw. */
  const fill = known(record.fill)

  const startEdit = (which: 'name' | 'sections' | 'claims') => {
    setRefused(null)
    setProposed(null)
    setClaimed(null)
    setEditing(which)
    setDraft(which === 'name' ? (record.name ?? '') : writeIndices(record))
  }

  const closeEdit = () => {
    setEditing(null)
    setProposed(null)
    setRefused(null)
  }

  const saveName = async () => {
    /* A name trimmed to nothing is no name. `server.ts:createBox` omits an empty one for the
     * same reason; here the field is how a name is CLEARED, so the empty string is sent rather
     * than omitted — the PUT assigns `name` whenever the key is present, which is what puts a
     * box back to unnamed. */
    if (await onWrite({ name: draft.trim() })) closeEdit()
  }

  const proposeSections = () => {
    const indices = readIndices(draft)
    if (indices === null) {
      setRefused('Dividers are the card number each section starts at, like 1, 31, 56.')
      return
    }
    setRefused(null)
    setProposed(indices)
  }

  const saveSections = async () => {
    if (proposed === null) return
    if (await onWrite({ sections: proposed })) closeEdit()
  }

  return (
    <section className="boxops-box">

      {/* THE READINGS MOVED TO `BoxIdentity`, AT THE TOP OF THE WALK (owner, 2026-08-25).
          What stood here was the box header, the fill sentence, the segment track, a heading
          reading `Layout and controls`, and one row per section. The section rows were the
          reason to act: `.browse-secthead` in the column beside this drew `SECTION 1 · #1–#85`
          and `85` for every one of them, interactively, while this drew `Section 1 #1–#85 85
          cards` as inert text. Two renderings of one fact, and deleting the inert one is not a
          loss — the walk IS the sections list.

          The heading went with the list it named. The fill and the track went UP, to sit with
          the box strip that already names the box. What is left here is the operations, and
          they sit at the bottom of the column beside `Register a box`, which is the other
          control that acts on a box rather than on a card. */}
      <div className="boxops-more">
      {record.sections.length > 0 && record.sections_detail.length === 0 ? (
        <p className="boxops-machine">
          This box has a declared layout that will not validate, so its sections could not be
          drawn. The raw list is above; save a corrected one below.
        </p>
      ) : null}

      {editing === null ? (
        <div className="boxops-actions">
          <button
            className="boxops-plain"
            type="button"
            disabled={busy}
            onClick={() => startEdit('name')}
          >
            Rename
          </button>
          <button
            className="boxops-plain"
            type="button"
            disabled={busy}
            onClick={() => startEdit('sections')}
          >
            Edit dividers
          </button>
          {sealed ? (
            <button
              className="boxops-plain"
              type="button"
              disabled={busy}
              onClick={() => void onWrite({ state: 'open' })}
            >
              Re-open box
            </button>
          ) : (
            /* THE NUMBER IS ON THE BUTTON, and that is the requirement rather than a nicety.
               Sealing freezes capacity at the fill and every fraction in the product then
               divides by it — a control reading "Seal box" alone would take a permanent
               decision against a denominator the owner would have to go and find. Disabled when
               the fill could not be read, because the honest label cannot be written and a seal
               against an unknown number is exactly what this rule exists to prevent. */
            <button
              className="boxops-plain"
              type="button"
              disabled={busy || fill === null}
              onClick={() => void onWrite({ state: 'closed' })}
            >
              {fill === null
                ? 'Seal box — the fill could not be read'
                : `Seal box — freezes capacity at ${fill}`}
            </button>
          )}
          {/* THE ONE CONTROL HERE THAT WRITES CARDS RATHER THAN THE BOX, and its label says so
              before it is pressed — the same rule the seal follows. A selection narrows it; no
              selection means the box. `record.cards` counts records naming this box, which is
              what the route walks.

              LAST, AND THE ORDER ABOVE IT IS D20's OWN. Rename, Edit dividers, Seal is what a
              box is called, where its dividers are, and whether the lid is on — the three
              things D20 makes a box object for, in that entry's order. This one is not about
              the box at all, so it is drawn after them rather than wedged between the dividers
              and the lid. Last is also the only position in a wrapping row where a label that
              changes width with the selection can rewrap nothing but itself. */}
          {/* AND NOT DRAWN AT ALL OVER NOTHING. `Set claims on all 0 cards in box 6` was a
              real string on a real screen the moment empty boxes became reachable — a control
              offering to write a claim onto no records, whose editor would open, take a
              vocabulary, and apply to nobody. It is the only control in this panel that acts
              on CARDS, so it is the only one an empty box can leave with nothing to do; the
              other three act on the box, which exists.

              Absent rather than disabled, which is this repo's rule wherever the distinction
              has come up (docs/DESIGN.md, on the run panel's spend button): a disabled button
              is one attribute away from pressable and states a capability that is not there. */}
          {selection.length > 0 || record.cards > 0 ? (
            <button
              className="boxops-plain"
              type="button"
              disabled={busy}
              onClick={() => startEdit('claims')}
            >
              Set claims on {scope}
            </button>
          ) : null}
        </div>
      ) : editing === 'claims' ? (
        <ClaimEditor
          scope={scope}
          /* The vocabulary the chips are drawn from. A box has no game of its own — D21 makes
             `game` a per-card claim and mixed boxes legal — so there is nothing to hand down
             and the editor falls back to the registry's published default. */
          game={null}
          busy={busy}
          onApply={(patch) => void applyClaims(patch)}
          onCancel={closeEdit}
        />
      ) : editing === 'name' ? (
        <div className="boxops-editor">
          <Field label="Name" value={draft} onChange={setDraft} placeholder="SV commons" />
          <p className="boxops-hint">
            A name is a label for people. The box number is the identifier and nothing here can
            change it. Clear the field to put the box back to unnamed.
          </p>
          <div className="boxops-actions">
            <button
              className="boxops-plain"
              type="button"
              disabled={busy}
              onClick={() => void saveName()}
            >
              Save name
            </button>
            <button className="boxops-plain" type="button" onClick={closeEdit}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="boxops-editor">
          <Field label="Dividers" value={draft} onChange={setDraft} placeholder="1, 31, 56" />
          <p className="boxops-hint">
            The card number each section starts at, so the first is always 1. Leave it blank to
            go back to the default divider size.
          </p>
          {refused === null ? null : <p className="boxops-machine">{refused}</p>}

          {proposed === null ? (
            <div className="boxops-actions">
              <button
                className="boxops-plain"
                type="button"
                disabled={busy}
                onClick={proposeSections}
              >
                Check this layout
              </button>
              <button className="boxops-plain" type="button" onClick={closeEdit}>
                Cancel
              </button>
            </div>
          ) : (
            <Relabel
              record={record}
              proposed={proposed}
              busy={busy}
              onSave={() => void saveSections()}
              onCancel={() => setProposed(null)}
            />
          )}
        </div>
      )}

        {claimed === null ? null : <ClaimReceipt result={claimed} />}

        <Trouble failure={trouble} />

        {/* LAST CONTROL IN THIS COMPONENT, AND THAT IS THE ONLY PLACEMENT ARGUMENT IT NEEDS.
            Every other control here is reversible or is a reading; this one destroys a box.
            Nothing below it inside `BoxOps`, nothing beside it (`boxops-actions-lone`), and two
            presses — both of which print the box number — away from a screen that is otherwise
            for looking at cards. It read "two presses plus a typed number" until 2026-08-26,
            when the owner traded the typing for a second naming press; see `DeleteBox`.

            IT SAID "LAST IN THE DISCLOSURE" until 2026-08-25, and there has been no disclosure
            since the owner deleted the fold — BoxOps.css records the three rules that went with
            it. The placement argument never depended on it; only the thing it is last INSIDE of
            has a different name.

            WHAT SITS BELOW IT IN THE COLUMN IS `RegisterBox`, AND THAT IS DELIBERATE rather
            than an erosion of the rule above. It is not a box-2 control at all — it acts on the
            registry, not on this box — so it is separated by the widest gap in this block, and
            it wears the plain hairline where this one wears an ink border.

            THAT GAP RENDERS AT 32px AND NO DECLARATION SAYS 32 (corrected 2026-08-26). This
            comment said `.boxops-new`'s `--s5`, which is 24; the other 8 come from
            `.browse-map`'s own column `gap`, which fires between every child of that column and
            therefore stacks on top of the margin. Recorded as composed rather than silently
            re-tuned, because the two mechanisms are both correct and it is only their SUM that
            nobody chose. If 24 is ever wanted, the change is `--s5` -> `--s4` at BoxOps.css and
            not a new value here.

            AND NEVER A `border-top` ON IT. That was proposed and refused: `.boxops-new` sits
            25px below `.boxops-actions-lone`'s hairline, so a rule there would be drawn
            identically to this block's own row dividers and would read as one more box-2
            operation at exactly the point the subject stops being box 2. Leaving
            `section.boxops-box` is what carries the change of subject; air is the honest
            marker for it. */}
        {/* ABOVE THE DELETE, BECAUSE IT IS WHAT MAKES THE DELETE POSSIBLE. D34's release is
            the answer to one of the three things `box_not_empty_of_commitments` refuses on,
            and the operator meets that refusal at the control below this one. It draws
            nothing at all unless this box actually holds a listing. */}
        <ReleaseListings record={record} onChanged={onChanged} />

        <DeleteBox record={record} onChanged={onChanged} />
      </div>
    </section>
  )
}

/**
 * What editing the dividers will do, said before it is done.
 *
 * D10 AS AMENDED IS THE WHOLE OF THIS COMPONENT. "Positions are never renumbered" governs the
 * INDEX; Section and Card are a *view* of that index against the box's current layout. So
 * moving a divider relabels every card behind it and moves no card and no index — and the
 * entry is explicit that this is allowed from any screen, chosen over freezing a section once
 * a card sits in it, because correcting a wrong layout is the whole point.
 *
 * IT IS ALSO EXPLICIT ABOUT THE COST, AND THIS IS WHAT THE COST LOOKS LIKE ON A SCREEN: "a
 * mis-tap relabels a filled box and nothing flags it", mitigated by a `resectioned` history
 * event rather than by restricting the operation. D10 then names the fix to reach for FIRST if
 * that failure ever actually happens — "a confirm on an edit that moves a divider with cards
 * behind it". That is this, and it is deliberately a statement of consequence rather than an
 * "are you sure": docs/DESIGN.md bans the second on a reversible action, and this one is
 * reversible — save the old layout back and every label returns.
 *
 * THE COUNT ROUNDS UP TO A SECTION BOUNDARY AND THE SENTENCE SAYS SO. `reached` explains why
 * the exact per-card number is not available and why the available one is honest.
 */
function Relabel({
  record,
  proposed,
  busy,
  onSave,
  onCancel,
}: {
  record: BoxRecord
  proposed: readonly number[]
  busy: Busy
  onSave: () => void
  onCancel: () => void
}) {
  const from = firstChange(rendered(record), proposed)
  const hit = from === null ? null : reached(record, from)

  return (
    <div className="boxops-relabel">
      <p className="boxops-relabel-head">
        {proposed.length === 0
          ? 'Going back to the default divider size'
          : `New dividers: ${proposed.join(', ')}`}
      </p>

      {from === null ? (
        <p className="boxops-note-text">
          This is the layout the box already renders with, so nothing will be relabelled.
        </p>
      ) : (
        <>
          <p className="boxops-note-text">
            This is a <strong>relabel, not a renumber</strong>. No card moves and no index
            changes — Section and Card are a view of a card&rsquo;s index against the box&rsquo;s
            dividers, so every card from #{from} on will simply be called something different
            from now on.
          </p>
          <p className="boxops-note-text">
            {hit === null || hit.sections.length === 0
              ? 'How many cards that reaches could not be read from this box.'
              : `That reaches ${hit.sections.length === 1 ? 'section' : 'sections'} ` +
                `${hit.sections.join(', ')} — ${count(hit.cards, 'card', 'cards')}. ` +
                'The count is by whole section, so it includes any card early in the first ' +
                'one that keeps its label.'}
          </p>
        </>
      )}

      <div className="boxops-actions">
        <button className="boxops-plain" type="button" disabled={busy} onClick={onSave}>
          Save dividers
        </button>
        <button className="boxops-plain" type="button" onClick={onCancel}>
          Back
        </button>
      </div>
    </div>
  )
}

/** One labelled text field. A real `<label>` bound by id rather than an `aria-label`: two
 *  mechanisms for one job is one that can be deleted without the other noticing, and the
 *  visible label still grows the click target. `SearchField.tsx` makes the same call. */
function Field({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string
  value: string
  onChange: (next: string) => void
  placeholder?: string
}) {
  const id = useId()
  return (
    <div className="boxops-field">
      <label className="boxops-field-label" htmlFor={id}>
        {label}
      </label>
      <input
        className="boxops-field-input"
        id={id}
        type="text"
        /* Off on all four: a box name is not a word, an address or a sentence, and a browser
           correcting one mid-edit is a wrong answer somebody has to notice to undo. */
        autoComplete="off"
        autoCorrect="off"
        autoCapitalize="off"
        spellCheck={false}
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  )
}

// ---------------------------------------------------------------- retroactive capture claims

/* THE CLAIM EDITOR — one body, two scopes: every card in a box (or a selection of them), and
 * one card on the detail panel. It is the client half of `PUT /inventory/<box>` and
 * `PUT /inventory/<box>/<index>`, and it exists because those routes did not have one.
 *
 * A ROUTE IS NOT A FEATURE (CLAUDE.md, 2026-08-23). `applyBoxClaims` was built and covered by
 * T7 with no client function and no control on any screen, which is the repo's own recorded
 * failure — `docs/GATES.md` step 7 tells the same story about three screens missing from the
 * routes table while every check was green. `updateCard` had the same hole in a smaller shape:
 * it accepted four claims and not `rarity_claim`, which the route had always taken, so the one
 * claim a correction is most likely to be ABOUT was the one no screen could correct.
 *
 * IT LIVES IN THIS FILE BECAUSE THE BOX-WIDE APPLY IS A BOX OPERATION, and the per-card
 * correction is the same form with one card in its scope sentence. Two copies of a five-field
 * tri-state form is two things to keep in step, and the fields are the store's own
 * `CAPTURE_CLAIM_FIELDS` — one editor is one place they are enumerated on this side.
 *
 * EVERY FIELD IS TRI-STATE, WHICH IS THE WHOLE OF THE DESIGN. The routes distinguish three
 * requests and a form with only inputs can express two of them:
 *
 *   unticked          the field is omitted — leave whatever the card says alone
 *   ticked, filled    set it to this
 *   ticked, empty     send `null` — clear the claim back to none
 *
 * `server.ts:updateCard` keeps those apart with `in` rather than a truthiness test, and this
 * is the control surface that makes the distinction reachable. A form that sent every field on
 * every save would flatten a whole box's set hints the first time somebody fixed one note.
 *
 * `game` HAS NO CLEARED FORM and its row has no empty option. D21: the field is required and
 * its default is a read-side backfill for records written before it existed, never a
 * write-side default — so there is nothing to clear it to.
 *
 * THE GAME SELECT DRIVES THE VOCABULARY WHETHER OR NOT IT IS SENT. Finishes and rarities are
 * per-game (D22), so the chips have to come from somewhere even when the game is not being
 * changed; they come from whatever this select says, which starts on the card's own game (or
 * the registry default for a box-wide apply). On a MIXED box that is a guess about which
 * vocabulary the operator means, and it is deliberately not resolved here — the server
 * validates every card against its own game and refuses the whole call with the offenders
 * named, which is a better answer than a screen that quietly narrows the offer.
 *
 * NOTHING IS PRE-TICKED. An editor that opened with a field armed would apply it to eighty-five
 * cards on the first press of Apply.
 */

/** The five claims, in the order the capture screen asks for them. */
type ClaimField = 'game' | 'setHint' | 'variant' | 'rarityClaim' | 'note'

export type ClaimPatch = {
  setHint?: string | null
  /** D3 rung 1's finish claim, A LIST since the amendment of 2026-08-23: one member
   *  determines, two or more filter the candidate rows. `null` clears the claim, which is
   *  what an armed-but-empty control sends. */
  variant?: readonly string[] | null
  game?: string
  rarityClaim?: string[] | null
  note?: string | null
}

export function ClaimEditor({
  scope,
  game,
  busy,
  onApply,
  onCancel,
}: {
  /** What the apply will reach, as a sentence — "all 85 cards in box 95", "the 12 selected
   *  cards", "this card". Written by the caller because only the caller knows the scope, and
   *  drawn on the button as well as above the fields: the seal control's rule (D20 — the
   *  number is ON the button) applied to the other write in this file that reaches many
   *  records at once. */
  scope: string

  /** The game whose finish and rarity vocabulary the chips are drawn from, before the operator
   *  changes it. Null falls back to the registry's own default (D21), never to a hardcoded
   *  `pokemon` — that would be a second decision that has to agree with `games.DEFAULT_GAME`. */
  game: string | null

  busy: boolean
  onApply: (patch: ClaimPatch) => void
  onCancel: () => void
}) {
  const [entries, setEntries] = useState<readonly GameEntry[] | null>(null)
  const [fallback, setFallback] = useState<string | null>(null)
  const [armed, setArmed] = useState<readonly ClaimField[]>([])
  const [pickedGame, setPickedGame] = useState<string | null>(game)
  const [setHint, setSetHint] = useState('')
  const [variant, setVariant] = useState<readonly string[]>([])
  const [rarity, setRarity] = useState<readonly string[]>([])
  const [note, setNote] = useState('')
  const [refused, setRefused] = useState<string | null>(null)

  /* THE REGISTRY, ONCE, AND ALLOWED TO FAIL QUIETLY IN ONE DIRECTION ONLY. `GET /games` is the
   * one home for the vocabulary (D22) and nothing here invents a fallback list — a guessed
   * rarity becomes a price, which is what that entry refuses. If the read fails the two chip
   * rows say they have no vocabulary and offer nothing; the set hint and the note are plain
   * text and keep working, because neither is drawn from the registry.
   *
   * `.then(ok).catch(fail)` and never `.then(ok, fail)` — `app/eslint.config.js` bans the
   * two-argument form outright, and the success handler here walks a body off the wire. */
  useEffect(() => {
    let live = true
    getGames()
      .then((registry) => {
        if (!live) return
        setEntries(registry.games)
        setFallback(registry.default)
      })
      .catch(() => {
        if (!live) return
        setEntries([])
      })
    return () => {
      live = false
    }
  }, [])

  const key = pickedGame ?? fallback
  const entry = entries?.find((candidate) => candidate.key === key) ?? null
  const isArmed = (field: ClaimField) => armed.includes(field)
  const arm = (field: ClaimField, on: boolean) =>
    setArmed((held) => (on ? [...held.filter((f) => f !== field), field] : held.filter((f) => f !== field)))

  const submit = () => {
    if (armed.length === 0) {
      /* Refused here rather than sent. An empty patch is a well-formed request that writes
       * nothing, so the server would answer success and the screen would print a receipt for
       * an operation that did not happen — which is worse than a sentence saying so. */
      setRefused('Tick a field before applying. Nothing was sent.')
      return
    }
    setRefused(null)

    const patch: ClaimPatch = {}
    /* Built key by key with `if`, never spread from a record of undefineds: `'setHint' in
     * fields` is what `server.ts` tests, and a key present with an undefined value would read
     * as a clear rather than as an omission. */
    if (isArmed('game') && key !== null) patch.game = key
    if (isArmed('setHint')) patch.setHint = setHint.trim() === '' ? null : setHint.trim()
    if (isArmed('variant')) patch.variant = variant.length === 0 ? null : [...variant]
    if (isArmed('rarityClaim')) patch.rarityClaim = rarity.length === 0 ? null : [...rarity]
    if (isArmed('note')) patch.note = note.trim() === '' ? null : note.trim()
    onApply(patch)
  }

  return (
    <div className="boxops-editor">
      <p className="boxops-claim-scope">Change claims on {scope}</p>

      <ClaimRow
        field="game"
        label="Game"
        armed={isArmed('game')}
        onArm={arm}
        says="required — there is nothing to clear it to"
      >
        <select
          className="boxops-field-input"
          value={key ?? ''}
          disabled={entries === null}
          onChange={(event) => setPickedGame(event.target.value)}
          aria-label="Game"
        >
          {entries === null ? <option value="">reading the registry…</option> : null}
          {(entries ?? []).map((candidate) => (
            <option key={candidate.key} value={candidate.key}>
              {candidate.display}
            </option>
          ))}
        </select>
      </ClaimRow>

      <ClaimRow
        field="setHint"
        label="Set hint"
        armed={isArmed('setHint')}
        onArm={arm}
        says="leave empty to clear it"
      >
        <PlainInput value={setHint} onChange={setSetHint} placeholder="ME01" label="Set hint" />
      </ClaimRow>

      <ClaimRow
        field="variant"
        label="Finish"
        armed={isArmed('variant')}
        onArm={arm}
        says="none ticked clears it, and the ladder infers the finish instead"
      >
        {/* CHIPS, NOT A SELECT, since D3 rung 1's claim became a SET on 2026-08-23. A
            single `<select>` cannot express `{normal, reverse_holo}` — the claim a box of
            mixed-finish stock actually wants — and the one it could express, one finish,
            is the DETERMINING case rather than the filtering one. Deliberately the rarity
            row's markup below, cell for cell: D3's stated point is that a screen whose
            claims all work one way is one rule to hold, and this editor is the only other
            place in the product where a finish claim is made.

            A game with fewer than two finishes still draws the row here, unlike the
            capture screen, and that is not an oversight: this editor's whole job is
            retroactive correction, and CLEARING a claim on a `misc` or `pokemon_code` card
            that should never have carried one is a real thing to want. The empty-vocabulary
            case says so rather than drawing an empty box. */}
        {(entry?.finishes ?? []).length === 0 ? (
          <p className="boxops-machine">
            {entry === null ? 'finishes: unread' : `finishes: none for ${entry.display}`}
          </p>
        ) : (
          <div className="boxops-chips">
            {(entry?.finishes ?? []).map((name) => {
              const on = variant.includes(name)
              return (
                <button
                  key={name}
                  className="boxops-chip"
                  type="button"
                  aria-pressed={on}
                  onClick={() =>
                    setVariant((held) =>
                      held.includes(name)
                        ? held.filter((f) => f !== name)
                        : // Rebuilt in the game's enum order, never tap order — the same
                          // canonical form `pipeline/variant.py:_check_claim` and the
                          // capture route impose, so a restated claim diffs as no change.
                          (entry?.finishes ?? []).filter(
                            (f) => f === name || held.includes(f),
                          ),
                    )
                  }
                >
                  {name}
                </button>
              )
            })}
          </div>
        )}
      </ClaimRow>

      <ClaimRow
        field="rarityClaim"
        label="Rarity"
        armed={isArmed('rarityClaim')}
        onArm={arm}
        says="none ticked clears it"
      >
        {/* The game's exact `Rarity` cells, verbatim and in stack order — D22's rule that a
            second friendly vocabulary is a thing nothing audits. A game with no ladder
            (`misc`) offers none and says so rather than drawing an empty box. */}
        {(entry?.rarities ?? []).length === 0 ? (
          <p className="boxops-machine">
            {entry === null ? 'rarities: unread' : `rarities: none for ${entry.display}`}
          </p>
        ) : (
          <div className="boxops-chips">
            {(entry?.rarities ?? []).map((name) => {
              const on = rarity.includes(name)
              return (
                <button
                  key={name}
                  className="boxops-chip"
                  type="button"
                  aria-pressed={on}
                  onClick={() =>
                    setRarity((held) =>
                      held.includes(name) ? held.filter((r) => r !== name) : [...held, name],
                    )
                  }
                >
                  {name}
                </button>
              )
            })}
          </div>
        )}
      </ClaimRow>

      <ClaimRow
        field="note"
        label="Note"
        armed={isArmed('note')}
        onArm={arm}
        says="free text — the only handle an unidentified card has"
      >
        <PlainInput value={note} onChange={setNote} placeholder="blue-eyes, japanese" label="Note" />
      </ClaimRow>

      <p className="boxops-hint">
        A ticked field is written; an unticked one is left exactly as it is. A ticked field left
        empty clears the claim. Finish and rarity are per-game, so the vocabulary above comes
        from the game selected here — the server checks every card against its OWN game and
        refuses the whole apply, naming the cards, rather than writing some of them.
      </p>
      {refused === null ? null : <p className="boxops-machine">{refused}</p>}

      <div className="boxops-actions">
        <button className="boxops-plain" type="button" disabled={busy} onClick={submit}>
          {busy ? 'Applying…' : `Apply to ${scope}`}
        </button>
        <button className="boxops-plain" type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  )
}

/** One tri-state row: the arming checkbox, the label it names, and the control it governs.
 *
 *  THE CONTROL IS NOT DISABLED WHEN THE ROW IS UNARMED, deliberately. Filling a field and then
 *  ticking it is the order half the people will use, and a disabled input that has to be
 *  unlocked first turns one gesture into two on the screen the owner spends hours in. What the
 *  tick decides is whether the value is SENT, and the row says so in its own words. */
function ClaimRow({
  field,
  label,
  says,
  armed,
  onArm,
  children,
}: {
  field: ClaimField
  label: string
  says: string
  armed: boolean
  onArm: (field: ClaimField, on: boolean) => void
  children: ReactNode
}) {
  const id = useId()
  return (
    <div className={armed ? 'boxops-claim-row boxops-claim-armed' : 'boxops-claim-row'}>
      <input
        className="boxops-check"
        id={id}
        type="checkbox"
        checked={armed}
        onChange={(event) => onArm(field, event.target.checked)}
      />
      <label className="boxops-claim-label" htmlFor={id}>
        {label}
      </label>
      <div className="boxops-claim-control">{children}</div>
      <span className="boxops-claim-says">{says}</span>
    </div>
  )
}

/** A text input with no `<label>` of its own — `ClaimRow` above owns the label and binds it to
 *  the checkbox, which is the control that decides whether this value is written at all. The
 *  `aria-label` is what keeps the input itself named for a screen reader without a second
 *  visible label beside the row's. */
function PlainInput({
  value,
  onChange,
  placeholder,
  label,
}: {
  value: string
  onChange: (next: string) => void
  placeholder?: string
  label: string
}) {
  return (
    <input
      className="boxops-field-input"
      type="text"
      aria-label={label}
      autoComplete="off"
      autoCorrect="off"
      autoCapitalize="off"
      spellCheck={false}
      placeholder={placeholder}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  )
}

/** The receipt a box-wide apply leaves. Four numbers that are not the same number, drawn apart
 *  for the reason `Inventory.tsx` draws its two tallies apart: `eligible` is what the scope
 *  reached, `applied` is what actually changed, and `unchanged` is the difference — cards that
 *  already said what was asked for, which is a success and not a failure. `skipped` names the
 *  sold and retired cards the route stepped over, because D10 and D26 make those records
 *  history and a count alone would not say which ones. */
function ClaimReceipt({ result }: { result: BoxClaimResult }) {
  return (
    <div className="boxops-receipt">
      <p className="boxops-note-text">
        {result.applied === 0
          ? 'Nothing changed — every card in scope already said this.'
          : `${count(result.applied, 'card', 'cards')} changed.`}
      </p>
      <p className="boxops-machine">
        box {result.box} · eligible {result.eligible} · applied {result.applied} · unchanged{' '}
        {result.unchanged} · sidecars {result.sidecars_rewritten} · skipped{' '}
        {result.skipped_terminal}
      </p>
      {result.skipped.length === 0 ? null : (
        <p className="boxops-machine">
          stepped over: {result.skipped.map((row) => `#${row.index} ${row.state}`).join(' · ')}
        </p>
      )}
    </div>
  )
}

/** One SKU's line in the plan and in the receipt. `2 of 5 staged · box 3 holds 3`.
 *
 *  MONO, BECAUSE IT IS ALL NUMBERS. docs/DESIGN.md: the utility face carries every count in
 *  the product, and this row is nothing but counts and a SKU. */
function ListingLine({ row }: { row: BoxListingRow }) {
  const gives = Object.entries(row.releases)
  const keeps = Object.entries(row.after)
  return (
    <p className="boxops-machine">
      {row.sku} · {gives.length === 0 ? 'nothing' : gives.map(([k, n]) => `${n} ${k}`).join(' ')}
      {keeps.length === 0 ? '' : ` · keeps ${keeps.map(([k, n]) => `${n} ${k}`).join(' ')}`}
      {row.also_in_boxes.length === 0
        ? ''
        : ` · also ${row.also_in_boxes.map((o) => `box ${o.box} (${o.copies})`).join(', ')}`}
    </p>
  )
}

/* THE LISTING RELEASE — D34, and the door `box_not_empty_of_commitments` was missing.
 *
 * WHAT IT IS FOR, IN THE ORDER THE OPERATOR MEETS IT. The delete below refuses on three
 * grounds: a sold card, a retired card, a card whose SKU holds a TCGplayer listing stage. The
 * first two reverse on their own controls and the refusal says so. The third had no control
 * anywhere, and no path through the pipeline either — `staged` is drawn down in exactly one
 * place, `cli/cmd_join.py`, by the RISE in live quantity a fresh Filtered Export reports. That
 * is the right answer for an import that lands and no answer at all for one that does not, so
 * a staged row cleared by hand on TCGplayer left a count nothing could ever take back down.
 * Box 1's 53 Gate B cards sat behind 45 such records and the box was undeletable, not by any
 * rule anybody had argued for.
 *
 * IT IS TWO STEPS, AND THE FIRST IS FREE. Opening the panel fetches `GET /boxes/<box>/listings`
 * and draws the plan; the button that asserts does not exist until that has answered. This is
 * D33's preflight-then-confirm shape one register down — there the free step puts the cost on
 * screen before the control that spends appears, here it puts the SKUs, the copy counts and
 * THE OTHER BOXES on screen before the control that claims appears. No extra press: the fetch
 * runs on open, so the numbers arrive without being asked for.
 *
 * IT SHIPPED WITHOUT THAT AND THE OWNER CAUGHT IT. The first build zeroed each SKU outright
 * and reported which other boxes it had reached in the RECEIPT — honest, and after the write.
 * Two things changed together: the release is now budgeted by this box's unsold copies, so it
 * cannot give up what only another box's copies could account for; and the plan is drawn
 * before the press.
 *
 * `frees_box` IS DRAWN LOUDEST, because it is the one outcome a person would otherwise read as
 * a bug. A shared SKU leaves a remainder, a remainder keeps the card listing-held, and the box
 * therefore STAYS refused after a release that did exactly what it said. The owner ruled that
 * remainder in deliberately; the panel's job is to say so first.
 *
 * IT DRAWS NOTHING WHEN THERE IS NOTHING TO RELEASE, which is why the entry button reads
 * `record.listed` rather than offering itself unconditionally. This is a screen whose question
 * is where a card is; a control for a state most boxes are never in is chrome the rest of the
 * time.
 *
 * ONE PRESS, AND THE DELETE BENEATH IT TAKES TWO — a difference that survives the owner's
 * 2026-08-26 change and is smaller than it was. The delete used to demand the box number TYPED,
 * because its risk is destroying box 9 while looking at box 95; it now demands a second press
 * on a control that names the box, for the reason recorded at `DeleteBox`. Either way this one
 * stays at one press: its risk is a claim that turns out to be wrong, and neither typing digits
 * nor pressing twice makes anyone go and check TCGplayer. The preflight above the button is the
 * gate here — the numbers are what a person can actually check.
 */
function ReleaseListings({
  record,
  onChanged,
}: {
  record: BoxRecord
  onChanged: () => void
}) {
  const [open, setOpen] = useState(false)
  const [plan, setPlan] = useState<BoxListingPlan | null>(null)
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [trouble, setTrouble] = useState<Failure | null>(null)
  const [receipt, setReceipt] = useState<ListingReleaseResult | null>(null)

  const box = record.box

  /* THE PLAN IS FETCHED ON OPEN AND RE-FETCHED IF THE BOX CHANGES UNDER THE PANEL. The second
     half matters: the box strip can move while this is open, and a plan describing box 1 drawn
     above a button that would release box 3 is the exact mis-aim the whole preflight exists to
     prevent. `ignore` drops a slow answer that lands after the box moved on. */
  useEffect(() => {
    if (!open) return
    let ignore = false
    setLoading(true)
    setPlan(null)
    setTrouble(null)
    getBoxListings(box)
      .then((answer) => {
        if (!ignore) setPlan(answer)
      })
      .catch((err) => {
        if (!ignore) setTrouble(describeFailure(err))
      })
      .finally(() => {
        if (!ignore) setLoading(false)
      })
    return () => {
      ignore = true
    }
  }, [open, box])

  const run = async () => {
    if (busy) return
    setBusy(true)
    setTrouble(null)
    try {
      const result = await releaseBoxListings(box)
      setReceipt(result)
      setOpen(false)
      setPlan(null)
      /* The re-read is the caller's, as every write in this file leaves it. It matters more
         here than elsewhere: `record.listed` is what draws this control, and the delete panel
         under it recites the same three counts. Both are stale until the box row comes back. */
      onChanged()
    } catch (err) {
      setTrouble(describeFailure(err))
    } finally {
      setBusy(false)
    }
  }

  /* The receipt outlives the panel, and unlike the delete's it outlives the FACT: once the
     counts are down there is nothing on any screen that says what they were. Every SKU is
     listed rather than sampled because that list is what makes the claim checkable against
     TCGplayer afterwards — the one thing a person could still go and do. */
  if (receipt !== null) {
    const gave = Object.entries(receipt.given_up)
    return (
      <div className="boxops-receipt">
        <p className="boxops-note-text">
          Released {count(receipt.released, 'SKU', 'SKUs')} in box {receipt.box}
          {gave.length === 0
            ? '.'
            : `, giving up ${gave.map(([stage, n]) => `${n} ${stage}`).join(' · ')}.`}{' '}
          Nothing was deleted — these are counts, and staging again re-establishes them.
        </p>
        {receipt.frees_box ? null : (
          <p className="boxops-note-text">
            <strong>Box {receipt.box} is still held.</strong>{' '}
            {count(receipt.still_held.length, 'SKU', 'SKUs')} kept copies this box could not
            account for
            {receipt.also_in_boxes.length === 0
              ? ''
              : `, and ${receipt.also_in_boxes.map((b) => `box ${b}`).join(', ')} hold copies of
                 them`}
            . Those copies are still believed to be on TCGplayer, so the delete will go on
            refusing — which is the point of releasing only what this box's cards could back.
          </p>
        )}
        {receipt.listings.map((row) => (
          <ListingLine key={row.sku} row={row} />
        ))}
      </div>
    )
  }

  if (record.listed === 0) return null

  if (!open) {
    return (
      <div className="boxops-actions boxops-actions-lone">
        <button className="boxops-plain" type="button" onClick={() => setOpen(true)}>
          Release the listing hold on {count(record.listed, 'card', 'cards')}…
        </button>
      </div>
    )
  }

  return (
    <div className="boxops-danger">
      <p className="boxops-note-text">
        {count(record.listed, 'card', 'cards')} in box {box}{' '}
        {record.listed === 1 ? 'belongs' : 'belong'} to a SKU this store believes TCGplayer is
        holding — pushed, staged, or live. Releasing records that{' '}
        <strong>you have checked TCGplayer and it is holding none of them</strong>. Nothing here
        can verify that: a Filtered Export reports live quantity and an Export From Staged lists
        only the rows that are there, so absence proves nothing.
      </p>

      {loading ? <p className="boxops-hint">Reading what these SKUs are holding…</p> : null}

      {plan === null ? null : (
        <>
          <p className="boxops-hint">
            Each SKU gives up at most the copies this box holds, so nothing another box's copies
            could account for is touched.{' '}
            {plan.frees_box ? (
              <>This releases box {box} completely.</>
            ) : (
              <>
                <strong>This will not free box {box}.</strong>{' '}
                {count(plan.still_held.length, 'SKU', 'SKUs')} will keep copies
                {plan.also_in_boxes.length === 0
                  ? ''
                  : ` that ${plan.also_in_boxes.map((b) => `box ${b}`).join(', ')} also hold`}
                , so the delete will go on refusing.
              </>
            )}
          </p>
          {plan.listings.map((row) => (
            <ListingLine key={row.sku} row={row} />
          ))}
        </>
      )}

      <Trouble failure={trouble} />
      <div className="boxops-actions">
        {/* ABSENT, NOT DISABLED, UNTIL THE FREE STEP HAS ANSWERED — docs/DESIGN.md's rule for
            the run panel's spend button, applied for the same reason: a disabled button is one
            attribute away from pressable, and that attribute is what a later refactor drops
            without noticing. An element that is not rendered has to be deliberately re-added. */}
        {plan === null || plan.skus === 0 ? null : (
          <button className="boxops-plain" type="button" disabled={busy} onClick={() => void run()}>
            {busy ? 'Releasing…' : 'TCGplayer holds none of these — release'}
          </button>
        )}
        <button
          className="boxops-plain"
          type="button"
          onClick={() => {
            setOpen(false)
            setPlan(null)
            setTrouble(null)
          }}
        >
          Cancel
        </button>
      </div>
    </div>
  )
}

/* THE WHOLE-BOX DELETE — D10's third 2026-08-23 ruling, and the most destructive action in the
 * product.
 *
 * THIS FILE SAID IN WRITING THAT THE CONTROL BELONGED HERE "when the route lands", and named
 * the gate: refused while the box holds any sold, retired or listing-held card. The route has
 * landed and the server keeps that gate itself — `box_not_empty_of_commitments`, naming up to
 * eight of them — so what this control owes is the other half: a confirmation worth the act,
 * and a receipt worth reading afterwards.
 *
 * IT GATES, AND IT IS THE ONE PLACE IN THIS APP THAT DOES. docs/DESIGN.md bans the confirm
 * dialog on a reversible action and then carves out "genuinely destructive actions may still
 * gate". Every other write on these screens sits inside that ban with an undo behind it: a
 * sale reverses, a retirement reverses, a divider edit is a relabel you can save back, a
 * re-shoot leaves the card in its box. This one has NO undo — the records, the photographs and
 * the sidecars are gone, and unlike capture-undo the cards are not in your hand.
 *
 * THE GATE IS TWO PRESSES THAT BOTH NAME THE BOX (owner, 2026-08-26). It was a TYPED box
 * number, and the argument for that is worth keeping because it is most of the argument for
 * what replaced it: a yes/no dialog is answered by the same reflex that pressed the button,
 * and this control's whole risk is deleting box 9 while looking at box 95. Typing could not be
 * done by momentum, and it forced the operator to read which box they were aimed at.
 *
 * WHAT THE OWNER MEASURED AGAINST IT was twelve empty spam boxes and twelve typed numbers, the
 * session after the box strip started showing empty boxes at all — their instruction: "make
 * deleting boxes just require a confirm click, not type something". A gate whose cost scales
 * with how many boxes you are tidying up is a gate that gets resented, and a resented gate is
 * read past rather than read.
 *
 * SO THE HALF THAT SURVIVES IS THE HALF THAT WAS DOING THE WORK: naming the target. `Delete
 * box 6…` opens the panel and `Delete box 6 permanently` fires it, so the number is printed
 * twice and the second press is on a control that has to be found rather than one sitting
 * under the pointer. What is given up is the momentum guarantee, deliberately and by the
 * owner. This is still NOT the "are you sure" the ban is about: that dialog's confirm says
 * nothing about what it is confirming, and both of these say the box.
 *
 * IF THAT TURNS OUT TO BE TOO LITTLE, the fix to reach for first is graduating it by what the
 * box HOLDS rather than restoring it everywhere — an empty box's delete destroys a name and a
 * number, and box 2's destroys 543 photographs. That is one condition on `record.cards`, and
 * it is written down here rather than built because the owner asked for the simple thing.
 *
 * THE REFUSAL IS SHOWN WHOLE. `box_not_empty_of_commitments` names which cards hold the box
 * open; reducing it to "cannot delete" would leave the owner with no way to find them.
 */
function DeleteBox({
  record,
  onChanged,
}: {
  record: BoxRecord
  onChanged: () => void
}) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [trouble, setTrouble] = useState<Failure | null>(null)
  const [receipt, setReceipt] = useState<BoxDeleteResult | null>(null)

  const run = async () => {
    if (busy) return
    setBusy(true)
    setTrouble(null)
    try {
      const result = await deleteBox(record.box)
      setReceipt(result)
      setOpen(false)
      /* The re-read is the caller's, as every write in this file leaves it: the box is gone
       * from `GET /boxes` and its cards are gone from `GET /inventory`, and the walk's own
       * shelf effect falls to the first shelf that still exists. Nothing here patches a
       * held copy of either. */
      onChanged()
    } catch (err) {
      setTrouble(describeFailure(err))
    } finally {
      setBusy(false)
    }
  }

  /* The receipt outlives the panel and the box. It is drawn from the server's own per-kind
     counts because they are the only evidence the operation did what it said — there is
     nothing left to go and check. */
  if (receipt !== null) {
    return (
      <div className="boxops-receipt">
        <p className="boxops-note-text">Box {receipt.deleted_box} is gone. There is no undo.</p>
        <p className="boxops-machine">
          cards {receipt.cards} · photos {receipt.photos} · sidecars {receipt.sidecars} · review{' '}
          {receipt.review_deleted} · parked {receipt.parked_deleted} · cache{' '}
          {receipt.cache_deleted} · registry {String(receipt.registry_deleted)} · directory{' '}
          {String(receipt.directory_removed)}
        </p>
        {receipt.directory_removed ? null : (
          <p className="boxops-note-text">
            The photo directory was left in place because it still holds a file this delete did
            not account for. Nothing was removed that was not listed above.
          </p>
        )}
      </div>
    )
  }

  if (!open) {
    return (
      /* THE ENTRY CARRIES THE WEIGHT, NOT ONLY THE CONFIRM. `boxops-plain-danger` was drawn
         on the confirm inside this panel and nowhere else — i.e. only once the operator had
         already decided to look at it — so the button that OPENS an irreversible whole-box
         delete was byte-identical to Rename and Edit dividers. It is the one step of emphasis
         this palette allows, and it was being spent where attention already was.

         `boxops-actions-lone` stops it sharing a wrapping row. The claim button beside it
         carries a state-dependent label — "Set claims on the 12 selected cards" becomes "Set
         claims on all 544 cards in box 2" — which changes width by ~150px whenever a tick
         changes in the OTHER column, rewrapping the row and moving this button under the
         cursor between one glance and the next. Fitts assumes a stationary target. */
      <div className="boxops-actions boxops-actions-lone">
        <button
          className="boxops-plain boxops-plain-danger"
          type="button"
          onClick={() => setOpen(true)}
        >
          Delete box {record.box}…
        </button>
      </div>
    )
  }

  return (
    <div className="boxops-danger">
      <p className="boxops-note-text">
        This deletes <strong>every record, photograph and sidecar</strong> in box {record.box} —{' '}
        {count(record.cards, 'card', 'cards')} — along with its queue entries, its identification
        cache and the box itself. <strong>There is no undo.</strong> Unlike an undone capture,
        these cards are not in your hand.
      </p>
      {/* THE HINT NAMES WHICH GROUND, NOW THAT THE BOX ROW CARRIES ALL THREE (D34). It used
          to recite the rule — "sold, retired or listed" — which is what the refusal says, and
          the operator would learn which of the three applied to THIS box only by pressing an
          irreversible button and reading the error. The three have different remedies, so
          which one it is decides what they do next. */}
      <p className="boxops-hint">
        {record.sold + record.retired + record.listed === 0
          ? 'A box holding a sold, retired or listed card is refused: those records are history and commitments, not clutter.'
          : `This box will be refused: ${[
              record.sold ? `${count(record.sold, 'card', 'cards')} sold` : null,
              record.retired ? `${count(record.retired, 'card', 'cards')} retired` : null,
              record.listed ? `${count(record.listed, 'card', 'cards')} listed` : null,
            ]
              .filter((part): part is string => part !== null)
              .join(', ')}. Sold and retired cards reverse on their own controls; a listing hold is released above.`}
      </p>
      <Trouble failure={trouble} />
      {/* THE CONFIRM NAMES THE BOX, which is the whole of the gate now that the typed field is
          gone. `Delete box 6 permanently` rather than `Delete permanently`: a confirm that does
          not say what it is confirming is the "are you sure" docs/DESIGN.md bans, and the only
          thing separating this from one is that both presses print the number. */}
      <div className="boxops-actions">
        <button
          className="boxops-plain boxops-plain-danger"
          type="button"
          disabled={busy}
          onClick={() => void run()}
        >
          {busy ? 'Deleting…' : `Delete box ${record.box} permanently`}
        </button>
        <button
          className="boxops-plain"
          type="button"
          onClick={() => {
            setOpen(false)
            setTrouble(null)
          }}
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
