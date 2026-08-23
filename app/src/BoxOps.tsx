import { useCallback, useId, useState } from 'react'

import type { BoxRecord, Place, SectionDetail } from './types'
import type { Failure } from './server'
import { createBox, describeFailure, updateBox } from './server'
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
 * ONE OPERATION D31 NAMES IS NOT HERE, AND ITS ABSENCE IS A SERVER GAP RATHER THAN A CHOICE.
 * D31 lists "name, sections, seal, delete" as the four that move onto the box header; D10's
 * third 2026-08-23 ruling specifies whole-box delete. There is no `DELETE /boxes/<box>` route
 * and no client function for one, so there is nothing to move. When the route lands, its
 * control belongs in this file, under the same gate D10 puts on it — refused while the box
 * holds any sold, retired or listing-held card.
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
  write: (run: () => Promise<BoxRecord>) => Promise<boolean>
} {
  const [busy, setBusy] = useState<Busy>(false)
  const [trouble, setTrouble] = useState<Failure | null>(null)

  const write = useCallback(
    async (run: () => Promise<BoxRecord>): Promise<boolean> => {
      if (busy) return false
      setBusy(true)
      setTrouble(null)
      try {
        await run()
        onChanged()
        return true
      } catch (err) {
        /* The server's own message, verbatim, with its code beneath. `_fail` already says what
         * happened and what to do next — `box_exists`, `sections_invalid`, `box_closed` all
         * name the remedy — and paraphrasing them here would be a second vocabulary nothing
         * audits. */
        setTrouble(describeFailure(err))
        return false
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
export function BoxOps({ record, onChanged }: { record: BoxRecord; onChanged: () => void }) {
  const { busy, trouble, write } = useBoxWrite(onChanged)
  const onWrite = (patch: { name?: string; sections?: number[]; state?: 'open' | 'closed' }) =>
    write(() => updateBox(record.box, patch))
  /* Which editor is open, or null. One at a time per box: two open fields over one record is
   * two half-finished edits racing for the same lock. */
  const [editing, setEditing] = useState<'name' | 'sections' | null>(null)
  const [draft, setDraft] = useState('')
  const [refused, setRefused] = useState<string | null>(null)

  /* The parsed layout waiting on the owner's answer to the relabel warning, or null. A separate
   * state from the draft because the warning is a statement about a PARSED layout — it names
   * the first index that moves and counts what sits behind it, and neither is knowable from the
   * text. */
  const [proposed, setProposed] = useState<number[] | null>(null)

  const sealed = record.state === CLOSED
  const fill = known(record.fill)
  const capacity = known(record.capacity)
  const total = denominator(record)
  const spans = spansOf(trackPlace(record, total), record.sections_detail)

  const startEdit = (which: 'name' | 'sections') => {
    setRefused(null)
    setProposed(null)
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
      <header className="boxops-box-head">
        <h2 className="boxops-box-number">Box {record.box}</h2>
        <span className="boxops-box-name">{record.name ?? 'unnamed'}</span>
        {/* The lid, said in the store's own word. Outlined rather than filled: docs/DESIGN.md
            gives the solid accent to a screen with exactly one thing to do, and a state chip is
            a reading rather than a control. No accent at all here — sealed and open are both
            ordinary conditions of a box, and neither is the system being unsure. */}
        <span className={sealed ? 'boxops-state boxops-state-sealed' : 'boxops-state'}>
          {sealed ? 'sealed' : 'open'}
        </span>
      </header>

      {/* THE TWO DENOMINATORS ARE DRAWN AS TWO DIFFERENT SENTENCES, which is D20's whole
          distinction and the thing this screen must not blur. A sealed box divides by a number
          that is final; an open one divides by how many cards are in it SO FAR, and the same
          card reads 30% today and 12% next week without having moved. `so far` is doing real
          work in that sentence and is not filler. */}
      <p className="boxops-fill">
        {sealed && capacity !== null ? (
          <>
            <span className="boxops-fill-number">{capacity}</span>
            <span className="boxops-fill-word">cards, sealed</span>
          </>
        ) : fill === null ? (
          <>
            <span className="boxops-fill-word">how full this box is could not be read</span>
          </>
        ) : (
          <>
            <span className="boxops-fill-number">{fill}</span>
            <span className="boxops-fill-word">cards so far</span>
          </>
        )}
      </p>

      {/* THE TRACK IS THE BOX, one segment per section, each as wide as the run of cards it
          holds. Every span comes from `sections_detail` through `spansOf` — see `trackPlace`
          for why nothing here computes a boundary. No marker: a marker means "this card is
          here" and there is no card on this screen. */}
      {spans.length === 0 ? (
        <p className="boxops-machine">This box holds nothing to draw yet.</p>
      ) : (
        <div className="boxops-track" role="img" aria-label={`Box ${record.box}, ${spans.length} sections`}>
          {spans.map((span) => (
            <span
              className="boxops-span"
              key={`${span.start}-${span.end}`}
              /* flex-grow rather than a width percentage: the segments are siblings in a flex
                 row, so their proportions are exactly the spans and no rounding has to be
                 reconciled against 100%. PositionBar.tsx draws its track the same way. */
              style={{ flexGrow: span.end - span.start + 1 }}
            />
          ))}
        </div>
      )}

      {/* THE LAYOUT AND THE FOUR CONTROLS, ONE PRESS DOWN. Everything above this line is a
          reading of the box a person wants at a glance over its cards; everything inside it is
          an operation on the box or the raw fields an operation is checked against. Closed by
          default and remembered by nothing — a disclosure is not session state (D27 is about
          the capture screen's claims, and this is a panel that redraws per box anyway).

          `<details>` rather than a button and a boolean, for `Inventory.tsx`'s reason: the
          element already owns the open/closed semantics a screen reader announces, and a
          hand-rolled toggle is a second implementation of a thing the platform ships. The
          marker is drawn rather than left to the browser, same as that file's, so the render
          `make screenshot` takes matches the browser the owner works in. */}
      <details className="boxops-more">
        <summary className="boxops-more-head">
          <span className="boxops-marker" aria-hidden="true" />
          <span className="boxops-more-label">Layout and controls</span>
          <span className="boxops-more-hint">
            {record.sections_detail.length === 0
              ? 'rename · dividers · seal'
              : `${count(record.sections_detail.length, 'section', 'sections')} · rename · dividers · seal`}
          </span>
        </summary>

      {record.sections_detail.length === 0 ? null : (
        <ul className="boxops-sections">
          {record.sections_detail.map((detail) => (
            <li className="boxops-section" key={detail.section}>
              <span className="boxops-section-name">Section {detail.section}</span>
              <span className="boxops-section-span">
                {/* An open last section has no end, and it is drawn as open rather than filled
                    in with the box total: the two mean different things, and the second is a
                    claim about where a divider is. */}
                {known(detail.end) === null
                  ? `#${detail.start} onward`
                  : `#${detail.start}–#${detail.end}`}
              </span>
              <span className="boxops-section-count">{count(known(detail.count) ?? 0, 'card', 'cards')}</span>
            </li>
          ))}
        </ul>
      )}

      {/* The store's own field names, verbatim, so what is on screen greps to what is in
          `inventory.json`. `cards` counts records naming this box and `fill` is the high-water
          mark — they are different numbers and both are wanted, because the gap between them is
          exactly how many holes the box has. */}
      <p className="boxops-meta">
        cards {record.cards} · sold {record.sold} · fill {fill ?? 'unknown'} · next index{' '}
        {known(record.next_index) ?? 'unknown'} · sections{' '}
        {record.sections.length === 0 ? 'undeclared' : record.sections.join(' ')}
      </p>

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
        </div>
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

        <Trouble failure={trouble} />
      </details>
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
