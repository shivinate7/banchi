import { useEffect, useRef, useState } from 'react'
import { isEditableTarget } from './keys'
import type { InventoryCard } from './types'
import type { Failure } from './server'
import {
  describeFailure,
  positionLabel,
  placeSentence,
  getInventory,
  photoUrl,
  reshootPhoto,
  newCaptureId,
} from './server'
import './PullPreview.css'

/* The pull preview — docs/specs/capture-app.md §7, plus ONE WRITE it did not have then.
 *
 * This is the last link in the Gate B chain: a card photographed at the start of a run
 * shows up here with the right photo at the right box, section and card. That single
 * claim is still the whole screen, and this header said LOOK ONLY for as long as it was
 * the whole truth. It stopped being that when the re-shoot control landed, and the header
 * changes with the screen rather than surviving it — the drift docs/DESIGN.md's review
 * queue header is a worked example of, pointing the other way.
 *
 * THE ONE WRITE, AND ITS WHOLE EXTENT: replacing a photograph. D26's re-shoot half —
 * new bytes and a rebuilt sidecar at the same position, record untouched, label
 * unchanged, allocator never involved. D26 recorded the placement as an open question in
 * as many words — "where the control lives (pull preview, or a per-card view) is a design
 * question still open" — and the owner's ruling is the pull preview: this is the screen
 * where a bad photo is DISCOVERED, because checking photos against positions is the thing
 * it is for, and a remedy that lives anywhere else costs a navigation with the defect
 * still on screen. Nothing else here writes; mark-sold remains another screen's.
 *
 * NO CONFIRM DIALOG, AND THE ACTION IS IRREVERSIBLE — both at once, deliberately, and the
 * reasoning is capture-undo's (docs/DESIGN.md) transposed: the old bytes are gone, not
 * archived, but the CARD is still in its slot, so the remedy for a wrong re-shoot is
 * another re-shoot. What bounds the loss on undo — the card still in your hand — is here
 * the card still in its box. A dialog would tax every correct replacement to soften a
 * mistake that has a two-tap repair.
 *
 * The photo comes from `GET /photo/<box>/<index>`, which is D6's route and the reason
 * that route exists at all: the review queue requires it and the pull modal reuses it.
 *
 * Owner-side, so density is fine and docs/DESIGN.md's Fulfillment floors do not bind.
 * They bind on 7b's pull modal, which is a different screen for a different person;
 * borrowing them here would make this screen look like his and set the expectation that
 * it is safe for him to use, which it is not — it lists every card in every state, speaks
 * the pipeline's vocabulary, and now carries a control that destroys a photograph.
 */

/* The position label is READ off the wire and never composed here, and the rule now lives in
 * `server.ts:positionLabel` — this file wrote it, the inventory view copied it verbatim, and
 * one rule about one field is one function. The whole argument went across with it, including
 * the part this screen learned the hard way: an earlier draft ported the arithmetic and D10's
 * 25-cards-per-divider constant into TypeScript, which is one divider size living in two
 * languages with nothing keeping them in step — and of the two answers, the one on screen is
 * the one a person walks to a box with.
 *
 * What stayed here is the fallback at the call sites below, which is this screen's decision
 * rather than the rule's: a row with no label shows its store key with `no label` in front of
 * it. Recomputing the label locally would trade a visible gap for an invisible disagreement,
 * and only one of those sends someone to the wrong slot.
 */

/* The inventory arrives as a map keyed `"3/1"`. The key is kept for identity and React,
 * and shown verbatim in the one case where a row carries no label — never parsed into a
 * position: a store key and a physical location are two different facts that agree for the
 * first 25 cards in a box and diverge from card 26 on, where `3/26` is Section 2, Card 1. */
type Row = { key: string; card: InventoryCard }

/* Box-walk order — box, then index. The same order `store/queues.py:sort_key` falls back
 * to and the order the cards physically sit in, so reading down this list is walking the
 * box. Rejected: newest first, which is the order you want while capturing and the wrong
 * one while checking a run against the boxes on the desk. */
function rowsOf(cards: Record<string, InventoryCard>): Row[] {
  return Object.entries(cards)
    .map(([key, card]) => ({ key, card }))
    .sort((a, b) => a.card.box - b.card.box || a.card.index - b.card.index)
}

// -------------------------------------------------------------- stepping through the list

/* Left and Right move the selection one card, in the order `rowsOf` already put them in and
 * no other. The owner asked for this by name — "fast nav" — and what makes it fast is not the
 * binding but the two properties below: a held key repeats, and the ends stop.
 *
 * NOTHING HERE WRITES, and adding a key does not bend the look-only rule in this file's
 * header. A selection change is the same non-event a click on a row already was; the keys buy
 * a hand back, not a new power.
 *
 * ONE TABLE, TWO CONSUMERS: the handler reads `key` and `delta`, and the chips in the header
 * draw `label`. ReviewQueue.tsx pairs each key with its label constant for this reason, and
 * the reason is worth repeating — a screen that can advertise a key nothing listens for will
 * eventually do it, and that failure is invisible until someone presses the key.
 *
 * HOME AND END WERE CONSIDERED AND DECLINED. First and last card is a real want in a box of
 * two hundred, but at window scope those two keys are the page's own — End is how you reach
 * the bottom of the facts panel — and a screen that takes them is a screen quietly
 * disagreeing with the browser. The other draft scoped them to "only while the list has
 * focus", which costs a rule you cannot see: one key doing two things depending on where
 * focus happens to be is exactly the kind of thing that gets diagnosed months later. If
 * walking a long box with a held key turns out to be too slow in practice, the fix to reach
 * for first is Home and End bound on the list with the chips moved onto it — never a wrap.
 */
const STEPS = [
  { key: 'ArrowLeft', label: '←', delta: -1 },
  { key: 'ArrowRight', label: '→', delta: 1 },
] as const


/* `describeFailure` and `Failure` LIVED HERE and moved to server.ts on 2026-08-13, beside
 * the `ServerError` they destructure. This file's copy was the original and the argument in
 * its docstring travelled with it whole — including the reason it does not offer `make
 * server`, which this screen learned by getting it wrong first. Two later screens had copied
 * it byte for byte, and both of those comments named server.ts as the destination; the third
 * copy is what made the move due. */

/* A POOLED CARD — the owner's ruling that a code card is a count, not a location
 * (`pipeline/games.py`'s `located` flag; "Code cards are pooled inventory, not located" in
 * docs/DECISIONS.md). The server sends its row with no flat label and a `place` block
 * carrying `located: false` plus the game's display name, so this screen can tell the
 * design fact from the fault it already draws a panel for: a row whose box will not coerce
 * arrives with no `place` at all. `!== false` keeps an older server's rows — no flag
 * anywhere — reading as located, which they all are. */
function isPooled(card: InventoryCard): boolean {
  return card.place?.located === false
}

/** The row line and the machine line for a pooled card, one composer for both call sites.
 *  The display name is the server's stamp off the registry; `pooled ·` in front of the
 *  store key so `5/2` cannot read as a position — the same trick the no-label fallback
 *  below plays with `no label ·`. */
function pooledText(card: InventoryCard, key: string): string {
  return `${card.place?.game_display ?? card.game ?? 'pooled'} · pooled · ${key}`
}

type Detail = { label: string; value: string; mono: boolean }

/* What is shown beside the photo, and the reason it is more than the position.
 *
 * §7 asks for the photo and the label. `state` earns its line anyway: it is the other
 * half of the Gate B question — the photo proves the capture landed, the state proves
 * whether anything downstream has touched it. The rest are the fields a run is debugged
 * with, and this is the screen open while it is being debugged.
 *
 * A card's name is a thing a human reads, so it takes the body face; everything else is a
 * value being compared against something, so it takes the utility face. That is
 * docs/DESIGN.md's mono-carries-all-metadata rule applied one field at a time rather than
 * one panel at a time.
 */
function detailsOf(card: InventoryCard): Detail[] {
  return [
    { label: 'Card', value: card.name ?? 'not identified yet', mono: card.name === null },
    { label: 'Number', value: collectorNumber(card), mono: true },
    // The record's own game claim, verbatim. Null means written before the field existed
    // — the pipeline reads that as pokemon, and saying "not recorded" is the honest form
    // of the same fact. Earns its line the day boxes are mixed: it is what explains why
    // the panel above says pooled, or does not.
    { label: 'Game', value: card.game ?? 'not recorded', mono: true },
    { label: 'State', value: card.state, mono: true },
    { label: 'Captured', value: card.captured_at ?? 'not recorded', mono: true },
    { label: 'Set hint', value: card.set_hint ?? 'none', mono: true },
    { label: 'Finish', value: card.metadata_finish ?? 'none recorded', mono: true },
  ]
}

/* Shown as the model returned it, unpadded. `pipeline/join.py:join_key` zero-fills to
 * three digits to match the export's `Number` column, and doing that here would put a
 * string on screen that nothing in the run ever said — which is the wrong trade on the
 * screen someone opens to find out what the run actually said. */
function collectorNumber(card: InventoryCard): string {
  if (card.number === null) return 'none'
  return card.printed_total === null ? card.number : `${card.number}/${card.printed_total}`
}

export function PullPreview() {
  const [rows, setRows] = useState<Row[] | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  /* The key whose photo 404'd, not a boolean: an `onError` from the previously selected
   * card can land after the selection has moved, and a boolean would blame the wrong
   * card for a missing file. */
  const [photoAbsent, setPhotoAbsent] = useState<string | null>(null)
  const [reloads, setReloads] = useState(0)
  /* Each re-shot card's NEW capture id, by row key — the cache nonce PhotoPanel appends
   * after a replacement, and nothing else. The id rather than a counter because it
   * already names the exact photograph the screen expects, so a `?reshot=<id>` in a
   * network log is self-explaining. Kept across reloads deliberately: the URL is the
   * same stable one, and the bytes behind it are still the ones this id names. */
  const [reshot, setReshot] = useState<Record<string, string>>({})
  /* The key of the replacement in flight, or null — one at a time, the same rule every
   * write in this app follows: `Store.write()` takes the file lock per call. */
  const [reshootBusy, setReshootBusy] = useState<string | null>(null)
  /* A refusal PAIRED WITH ITS CARD, not floated loose: stepping to the next card must
   * not carry the previous card's refusal under a photo it says nothing about. */
  const [reshootFailure, setReshootFailure] = useState<{ key: string; failure: Failure } | null>(
    null,
  )
  const listRef = useRef<HTMLUListElement | null>(null)

  /* The re-shoot, from a picked file to the server. The base64 the wire wants is the
   * data-URL's payload — sliced at the first comma rather than split, and RAW, no
   * `data:` prefix, exactly as `capture()` documents: the server refuses the prefixed
   * shape loudly rather than letting two spellings spread.
   *
   * A FRESH CAPTURE ID PER PICK, and that is safe HERE in a way it is not on the capture
   * screen. There the id must survive a retry because a replay with a new id burns an
   * index; a re-shoot allocates nothing, so the lost-response worst case is the same
   * bytes written to the same position twice with one extra history line. Holding the id
   * across a retry would buy machinery, not safety.
   *
   * On success: remember the id as this card's cache nonce, then re-read the inventory —
   * the record's `photo` and `capture_id` changed server-side, the loader keeps the
   * selection, and it also resets `photoAbsent`, which is how a card whose photo file
   * was LOST comes back to life when a re-shoot gives the route bytes to serve again. */
  const beginReshoot = (row: Row, file: File) => {
    setReshootBusy(row.key)
    const reader = new FileReader()
    reader.onload = () => {
      const url = String(reader.result)
      const imageBase64 = url.slice(url.indexOf(',') + 1)
      const captureId = newCaptureId()
      reshootPhoto(row.card.box, row.card.index, imageBase64, captureId)
        .then(() => {
          setReshot((held) => ({ ...held, [row.key]: captureId }))
          setReshootBusy(null)
          setReshootFailure(null)
          setReloads((n) => n + 1)
        })
        .catch((err: unknown) => {
          setReshootBusy(null)
          /* Verbatim, owner screen: `card_sold` and `card_retired` should be unreachable
           * (the control is not drawn for either state), but a second device can move a
           * card between this screen's read and the press, and the server's message
           * names the way back better than anything composed here could. */
          setReshootFailure({ key: row.key, failure: describeFailure(err) })
        })
    }
    reader.onerror = () => {
      setReshootBusy(null)
      setReshootFailure({
        key: row.key,
        failure: describeFailure(reader.error ?? new Error('the picked file could not be read')),
      })
    }
    reader.readAsDataURL(file)
  }

  useEffect(() => {
    // StrictMode runs effects twice in dev, and a slow first response can land after the
    // second one. The flag makes the late arrival a no-op rather than a flicker.
    let live = true
    /* `.then(ok).catch(fail)` AND NOT `.then(ok, fail)`. The two-argument form does not cover
     * its own success handler, so anything thrown while walking the answer — `rowsOf` over a
     * body with no `cards`, which is what an older or wrong server returns — becomes an
     * unhandled rejection: no failure panel, no Reload to press, and the screen stuck on
     * "Reading the inventory." Fulfillment.tsx watched exactly that happen for a morning and
     * fixed itself; this file kept the shape for another ten days, which is the argument for
     * the eslint rule in `app/eslint.config.js` rather than for a fourth copy of this comment.
     * With `.catch` a body this screen cannot read fails the same way a dead server does. */
    getInventory()
      .then((inventory) => {
        if (!live) return
        const next = rowsOf(inventory.cards)
        setRows(next)
        setFailure(null)
        setPhotoAbsent(null)
        /* Keep the selection across a reload when the card is still there. An undo on the
         * capture screen deletes the newest card outright — D10, no tombstone — so a key
         * held blindly would render an empty panel that reads as a bug rather than as the
         * deletion it is. */
        setSelected((prev) =>
          prev !== null && next.some((row) => row.key === prev) ? prev : (next[0]?.key ?? null),
        )
      })
      .catch((err: unknown) => {
        if (!live) return
        setRows(null)
        setFailure(describeFailure(err))
      })
    return () => {
      live = false
    }
  }, [reloads])

  /* THE ARROW KEYS, armed on the window rather than on the list itself, so the owner does not
   * have to click a row before the keyboard does anything — a fast nav that needs a mouse
   * click to arm it is not one. `trigger.ts` and ReviewQueue.tsx both bind this way and both
   * arm it from an effect that exists only while their screen is mounted; this is that shape
   * a third time, teardown included, which is the half of it that keeps a second mount from
   * leaving two listeners walking the list two cards at a time.
   *
   * `selected` is deliberately NOT a dependency. The move is a functional update, so the
   * handler closes over `rows` alone and is registered once per inventory read instead of
   * once per keystroke — at auto-repeat pace the second shape churns a window listener thirty
   * times a second, and the stale closure it would otherwise need is a real bug rather than a
   * style question.
   */
  useEffect(() => {
    if (rows === null || rows.length === 0) return

    const onKeyDown = (event: KeyboardEvent) => {
      /* Modifiers belong to the browser and the OS: Cmd-Left is Back and Alt-Left is a word
       * jump, and neither should quietly become a card. Shift is left out of that list for
       * the reason trigger.ts gives — it does not change which key was pressed — and a held
       * Shift silently killing the nav would be the worse of the two failures. */
      if (event.metaKey || event.ctrlKey || event.altKey) return

      const step = STEPS.find((candidate) => candidate.key === event.key)
      if (step === undefined) return
      if (isEditableTarget(event.target)) return

      /* AUTO-REPEAT IS THE FEATURE HERE, which is why there is no `event.repeat` guard and
       * why its absence is written down rather than left looking like an omission. trigger.ts
       * refuses a repeat because a held key there is a stack of captures of one card sitting
       * in the lens; ReviewQueue.tsx refuses one because a held key there is a run of answers,
       * and every answer is a write. Here the action is a selection change on a screen that
       * writes nothing: holding Right walks the box, letting go stops it, and nothing has been
       * spent that has to be walked back.
       *
       * What it does cost is a photo request per card as the panel keeps up. The browser
       * abandons the ones it does not finish, and a debounce was declined: it would leave the
       * photo showing one card while the highlight and the position label showed another,
       * which is precisely the disagreement this screen exists to rule out.
       */

      /* Prevented before the move rather than after it, because a refusal at the end of the
       * list is still this handler answering for the key. The alternative lets a held Right
       * start scrolling the page sideways the moment it runs out of cards, which reads as the
       * list having thrown you somewhere. Every press that reached one of the returns above
       * keeps its normal behaviour, which is the whole reason this line sits here and not at
       * the top. */
      event.preventDefault()

      setSelected((prev) => {
        const at = rows.findIndex((row) => row.key === prev)

        /* Not in this list at all — hard to reach, since the loader plants the selection on
         * the first row and only drops it when there is nothing to select. Step in from the
         * end you are stepping from, so a first press does something rather than nothing. */
        if (at === -1) {
          const landing = step.delta === 1 ? rows[0] : rows[rows.length - 1]
          return landing?.key ?? prev
        }

        /* BOTH ENDS STOP, and the missing index is what stops them: one past either end,
         * `rows[...]` is undefined under noUncheckedIndexedAccess and the selection is left
         * exactly where it was. Wrapping was the alternative and it is the wrong one —
         * arriving back at card 1 after the last card of a two-hundred-card box loses your
         * place without saying so, and the list is then lying about where its end is. A list
         * that stops is telling the truth. */
        return rows[at + step.delta]?.key ?? prev
      })
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [rows])

  /* Keep the selected row where it can be seen. The failure this prevents is specific, and it
   * is the one that makes a keyboard list feel broken: the detail panel updates, the marked
   * row is three screens up inside its own scroller, and the only thing that visibly moved is
   * on the other side of the page.
   *
   * `block: 'nearest'` so it scrolls only when it has to, which is what keeps it from
   * fighting the mouse — a click on a row that was already visible moves nothing.
   *
   * READ OFF `aria-current` rather than off a ref per row. That attribute is already this
   * screen's answer to "which row is current", so the row that scrolls is by construction the
   * row that is marked; a parallel map of refs is a second answer to the same question, and
   * the day the two disagree nothing says so. */
  useEffect(() => {
    const current = listRef.current?.querySelector('[aria-current="true"]')
    if (current instanceof HTMLElement) current.scrollIntoView({ block: 'nearest' })
  }, [selected, rows])

  const selectedRow = rows?.find((row) => row.key === selected) ?? null

  /* Read once for the selected card and passed down, rather than read again inside
   * PhotoPanel. Two reads of the same field cannot disagree today, but they are two places
   * to edit the day the field is renamed, and the failure mode of getting that half-right
   * is a photo captioned with a position beside a panel saying there is none. */
  const selectedLabel = selectedRow === null ? null : positionLabel(selectedRow.card)

  /* Read once beside the label it sits under, for the label's own reason: one read, one
   * value, and no way for the sentence's presence test and its rendering to disagree. */
  const selectedSentence = selectedRow === null ? null : placeSentence(selectedRow.card.place)

  return (
    <main className="pull-preview">
      <header className="pull-preview-head">
        <h1 className="pull-preview-title">Pull preview</h1>
        {/* This lede said "Nothing on this screen changes anything" for as long as that was
            true. The re-shoot ended it, and the copy rule is active voice about what
            actually happens — a lede quietly overclaiming safety on the screen with the
            one photograph-destroying control would be the worst place in the app to keep
            a stale sentence. */}
        <p className="pull-preview-lede">
          Every captured card, where it sits, and the photo taken of it. The one thing this
          screen changes is a photograph: Re-shoot replaces a bad one, and nothing else moves.
        </p>
        <div className="pull-preview-controls">
          {/* A reload is a GET. The ban in §7 is on acting — writing a state, marking a
              sale, pulling a card — and re-reading the inventory is none of those. It
              earns its place because Gate B alternates between capturing on one screen and
              checking here, and the alternative is teaching the operator to reload the
              browser, which also throws away the selection. No accent fill: docs/DESIGN.md
              reserves the solid fill for a screen with exactly one thing to do, and this
              screen's one thing is to be looked at. */}
          <button className="pull-preview-reload" type="button" onClick={() => setReloads((n) => n + 1)}>
            Reload
          </button>
          {rows === null ? null : (
            <span className="pull-preview-count">
              {rows.length} {rows.length === 1 ? 'card' : 'cards'}
            </span>
          )}
          {/* "Every choice shows its key" — docs/DESIGN.md, owner-side, where an hour spent
              checking a run against the boxes on the desk is a keyboard and not a mouse. A
              hotkey nobody can see is a hotkey nobody uses, and this screen had no chrome to
              discover it from at all.

              In the header rather than pinned to the list, because that is where the binding
              actually is: the keys are on the window and work wherever you are on this screen,
              so a chip attached to the list would claim a smaller thing than the truth.

              Drawn only with two cards to step between. A hint offering to move you through a
              list of one is chrome that has stopped being true, and the empty and failed
              states have no list under it at all. */}
          {rows === null || rows.length < 2 ? null : (
            <span className="pull-preview-keys">
              {STEPS.map((step) => (
                <kbd className="pull-preview-key" key={step.key}>
                  {step.label}
                </kbd>
              ))}
              step one card
            </span>
          )}
        </div>
      </header>

      {failure === null ? null : (
        <div className="pull-preview-note">
          <p className="pull-preview-note-text">{failure.message}</p>
          {/* The CODE beneath the sentence, and never the sentence again.
              docs/DESIGN.md's rule is "human label large, machine string small beneath
              it", and the machine string it means is a greppable token — `store_busy`,
              `unreachable` — that says something the label above it does not. An earlier
              draft printed the server's one message in both slots, which is not that rule
              but a stutter, and it cost the small line the only job it has: getting from
              what is on screen to what the server said, with `git grep`. Owner-side only,
              and this screen is owner-side. */}
          <p className="pull-preview-machine">{failure.code}</p>
        </div>
      )}

      {rows === null && failure === null ? (
        <p className="pull-preview-note-text">Reading the inventory.</p>
      ) : null}

      {rows !== null && rows.length === 0 ? (
        <p className="pull-preview-note-text">No cards captured yet.</p>
      ) : null}

      {rows !== null && rows.length > 0 ? (
        <div className="pull-preview-body">
          {/* Focusable and labelled, so the interaction is reachable rather than folklore: a
              keyboard user gets a tab stop that announces itself as the list of cards and says
              which keys it answers to. `aria-keyshortcuts` is the machine-readable half of the
              chips in the header — the same fact, said once to a person and once to a screen
              reader, and neither of them by a comment in a file nobody reading the screen can
              see. The keys are bound on the window and work whether or not this has focus, so
              this attribute claims less than the binding delivers, which is the safe
              direction for a claim to be wrong in. */}
          <ul
            className="pull-preview-list"
            ref={listRef}
            tabIndex={0}
            aria-label="Captured cards, in box-walk order"
            aria-keyshortcuts="ArrowLeft ArrowRight"
          >
            {rows.map((row) => (
              <li key={row.key}>
                {/* Plain buttons, and they stay plain buttons now that the arrow keys are
                    bound. Tab reaches every one of them for free, the click path is untouched,
                    and `aria-current` below is still the one mark of which row is current — a
                    roving-focus listbox would trade all three for an activedescendant dance
                    this screen does not need.

                    FOCUS DELIBERATELY DOES NOT FOLLOW THE SELECTION. It is the obvious next
                    step and it is the wrong one: a held Right would fire a focus move per
                    card, dragging focus out of wherever the owner left it and scrolling on its
                    own account, thirty times a second. The row is marked, not focused, and the
                    scroll effect above is what keeps it on screen.

                    The sentence this replaces said a key map here would be "a vocabulary to
                    learn for no decision". That was true of a screen driven with a mouse and
                    stopped being true the moment the owner asked to walk a box from the
                    keyboard — two keys, one meaning, and still nothing written. */}
                <button
                  className="pull-preview-row"
                  type="button"
                  aria-current={row.key === selected ? 'true' : undefined}
                  onClick={() => setSelected(row.key)}
                >
                  {/* The store key when the server sent no label, so the rows stay
                      distinguishable enough to pick one — with the word `no label` in
                      front of it, because `3/30` alone reads like a position and is not
                      one. The detail panel says the rest; a row has no room for it.
                      A POOLED ROW IS THE DELIBERATE HALF OF THAT CASE and gets its own
                      words: the pooled fact, never `no label`, which reads as a fault. */}
                  <span className="pull-preview-row-position">
                    {positionLabel(row.card) ??
                      (isPooled(row.card) ? pooledText(row.card, row.key) : `no label · ${row.key}`)}
                  </span>
                  <span className="pull-preview-row-name">{row.card.name ?? row.card.state}</span>
                </button>
              </li>
            ))}
          </ul>

          {selectedRow === null ? null : (
            <section className="pull-preview-detail">
              {selectedLabel === null && isPooled(selectedRow.card) ? (
                /* Pooled, not missing — the deliberate case, before the fault below can
                   claim it. The sentence says what the card IS so the absent label stops
                   looking like something to go and fix. */
                <div className="pull-preview-gap">
                  <p className="pull-preview-note-text">
                    This card is pooled — a count, not a location. It has no box, section or
                    card position to show; the key below names its photo and sidecar on
                    disk, and nothing else.
                  </p>
                  <p className="pull-preview-machine">
                    located: false · {pooledText(selectedRow.card, selectedRow.key)}
                  </p>
                </div>
              ) : selectedLabel === null ? (
                /* The gap, drawn as a panel in the space the label would have filled.
                   Loud rather than blank: this screen's whole claim is that it says where
                   a card is, and a screen that has quietly stopped making that claim
                   should not look like one that is still making it. */
                <div className="pull-preview-gap">
                  {/* Both causes, because the sentence has to survive being read on the
                      wrong one: a restart fixes an old server and does nothing at all for a
                      record whose box will not coerce. Naming only the likelier one would
                      send the operator round a loop that cannot work. */}
                  <p className="pull-preview-note-text">
                    The capture server sent no position label for this card, and this screen
                    does not work one out for itself. Either an older server is running —
                    restart it with `make server` and reload — or this record's box or index
                    is not a number, which `GET /status` reports.
                  </p>
                  {/* The field and its state, in the shape the missing-photo panel below
                      uses — `photo: null` there, `label: absent` here — plus the store key,
                      which is what a `curl /inventory | grep` needs to see it for itself. */}
                  <p className="pull-preview-machine">label: absent · key {selectedRow.key}</p>
                </div>
              ) : (
                /* The payload of the whole screen. Utility face because it is a position,
                   and sized up because it is the one thing being checked against a physical
                   box across the desk. */
                <>
                  <p className="pull-preview-position">{selectedLabel}</p>
                  {/* D30's sentence, quiet, directly under the label it makes countable:
                      "between Mantine and Thievul · 2 slots in this section are empty".
                      `Card 17` is the seventeenth SLOT, and once the section has permanent
                      gaps that is no longer the seventeenth card a hand can count to —
                      the neighbours restore the count and the gap tally says why it came
                      out short. Composed by `server.ts:placeSentence`, the one composer,
                      which answers null — and this renders nothing, never a guess — for a
                      pooled card, an older server, or a decoration the server degraded. */}
                  {selectedSentence === null ? null : (
                    <p className="pull-preview-between">{selectedSentence}</p>
                  )}
                </>
              )}

              <PhotoPanel
                row={selectedRow}
                label={selectedLabel}
                absent={photoAbsent === selectedRow.key}
                onAbsent={() => setPhotoAbsent(selectedRow.key)}
                nonce={reshot[selectedRow.key] ?? null}
              />

              <ReshootControl
                row={selectedRow}
                busy={reshootBusy === selectedRow.key}
                failure={
                  reshootFailure !== null && reshootFailure.key === selectedRow.key
                    ? reshootFailure.failure
                    : null
                }
                onPick={(file) => beginReshoot(selectedRow, file)}
              />

              <dl className="pull-preview-facts">
                {detailsOf(selectedRow.card).map((detail) => (
                  <div className="pull-preview-fact" key={detail.label}>
                    <dt>{detail.label}</dt>
                    <dd className={detail.mono ? 'is-util' : undefined}>{detail.value}</dd>
                  </div>
                ))}
              </dl>
            </section>
          )}
        </div>
      ) : null}
    </main>
  )
}

type PhotoPanelProps = {
  row: Row

  /** The server's own position label, or null when this row arrived without one. Handed
   *  down rather than derived here — see the note beside `selectedLabel`. */
  label: string | null

  absent: boolean
  onAbsent: () => void

  /** The capture id of a photo THIS SESSION replaced at this position, or null for the
   *  ordinary card. Non-null appends `?reshot=<id>` to the img src — see the comment at
   *  `base` below for why that is the one legitimate query parameter on this URL. */
  nonce: string | null
}

/* Two ways a photo can be missing, and they are different facts, so they get different
 * sentences rather than one broken image.
 *
 *   `photo` is null   — no photo was ever stored. `emit` can record a card that was never
 *                       photographed, and `store/master.py` keeps the field null for it.
 *   the route 404s    — the record claims a photo and the file is not there. That is a
 *                       store that has lost something, and it is worth saying so plainly.
 *
 * Both print the URL that was asked for, so the next move is a curl rather than a guess.
 */
function PhotoPanel({ row, label, absent, onAbsent, nonce }: PhotoPanelProps) {
  /* One phrasing, used by both the sentence beside a missing photo and the alt text on a
   * present one, so those two cannot end up disagreeing about where the card is. The
   * fallback says `store key` out loud rather than printing `3/30` bare: bare, it reads
   * like a position, and the whole point of the null case is that no position was sent. */
  const where = label ?? `store key ${row.key}`

  if (row.card.photo === null) {
    return (
      <div className="pull-preview-absent">
        <p className="pull-preview-note-text">No photo was stored for this card.</p>
        <p className="pull-preview-machine">photo: null</p>
      </div>
    )
  }

  /* The URL as `server.ts` mints it — with nothing appended, EXCEPT after a re-shoot.
   *
   * There is a real hazard here and it is worth naming rather than inheriting silently:
   * undo deletes a photo and releases its index, so the next capture reuses this exact URL
   * for different bytes, and `GET /photo` sends no `Cache-Control`, no `ETag` and no
   * `Last-Modified`. A browser that held one of these would show a stale photo at a correct
   * position — precisely the failure this screen exists to catch, and invisible when it
   * happens.
   *
   * A LOAD-TIME cache-busting parameter minted here was written and then removed, and it
   * stays removed. `server.ts:photoUrl`'s comment rejects that fix by name — the general
   * repair belongs in a response header on the server, one line in
   * `server/capture_server.py:_send` — and a nonce on every render would defeat what
   * caching this screen benefits from while papering over the missing header.
   *
   * THE RE-SHOOT NONCE IS THE ONE EXCEPTION, ARGUED AGAINST THAT COMMENT RATHER THAN
   * AROUND IT. What that comment refuses is a guess: a parameter added on every load
   * because the bytes MIGHT have changed. After `reshootPhoto` succeeds there is no might
   * — THIS screen sent the new bytes to this exact URL, so rendering the src that a
   * moment ago showed the photograph it just destroyed is showing a picture the store no
   * longer holds, the stale-photo failure above realised by our own hand. One screen, at
   * the one moment it knows, appending the id of the photograph it expects: that is
   * cache-busting as a statement of fact, not as a workaround, and photoUrl's comment now
   * names it as the standing exception. */
  const base = photoUrl(row.card.box, row.card.index)
  const src = nonce === null ? base : `${base}?reshot=${nonce}`

  if (absent) {
    return (
      <div className="pull-preview-absent">
        <p className="pull-preview-note-text">
          The record has a photo but the file is not on disk. The card is still at {where} —
          and a photo added below replaces nothing, it is the first one this position would
          have again.
        </p>
        <p className="pull-preview-machine">{src}</p>
      </div>
    )
  }

  return (
    <img
      /* Remounted per card AND per replacement: `src` in the key means a re-shoot swaps
         the element rather than mutating it, so a failed load cannot leave the previous
         photograph's broken state attached to the new one. */
      key={`${row.key}:${src}`}
      className="pull-preview-photo"
      src={src}
      alt={`The card photographed at ${where}`}
      onError={onAbsent}
    />
  )
}

/* The re-shoot control — the pull preview's one write. The header at the top of this file
 * carries the ruling (D26's second half, placed here by the owner) and the no-dialog
 * argument; what this component decides is the MECHANISM, and the honest one on this
 * screen is a file.
 *
 * NOT A CAMERA, ON PURPOSE. This screen has none, and wiring one in would duplicate the
 * capture screen's whole device-picker apparatus (D13: no facingMode, UVC labels, a
 * rotation chip) for a control used once in a while. The rig capture screen is for live
 * shooting; this control replaces a bad STORED photo with a better frame from wherever
 * the owner has one — a re-shot rig frame saved to disk, a phone photo airdropped over.
 * `accept="image/jpeg"` because the server stores what it is given and never converts
 * (`image_not_jpeg` is its word on anything else, rendered verbatim below).
 *
 * NOT DRAWN AT ALL FOR A SOLD OR RETIRED CARD — the `restores_to` lesson, learned twice:
 * never offer a control whose only behaviour is a refusal. The server would refuse both
 * (`card_sold`: the stored photo is the dispute record; `card_retired`: a photo of a card
 * that left is a photo of nothing), and this screen reads the same state field the server
 * checks. Not-rendered rather than disabled, the same ruling the shell applies to nav.
 */
type ReshootControlProps = {
  row: Row
  busy: boolean

  /** This card's own refusal or null — the caller keys failures by row so another card's
   *  refusal cannot render under this card's photo. */
  failure: Failure | null

  onPick: (file: File) => void
}

function ReshootControl({ row, busy, failure, onPick }: ReshootControlProps) {
  const inputRef = useRef<HTMLInputElement | null>(null)

  if (row.card.state === 'sold' || row.card.state === 'retired') return null

  return (
    <div className="pull-preview-reshoot">
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg"
        hidden
        onChange={(event) => {
          const file = event.target.files?.[0]
          /* Cleared before use, so picking the SAME file again fires onChange again —
           * which is exactly what a retry after a refusal is. */
          event.target.value = ''
          if (file !== undefined) onPick(file)
        }}
      />
      {/* No accent fill: docs/DESIGN.md reserves the solid fill for a screen with exactly
          one thing to do, and this screen's one thing is still to be looked at. The label
          changes with the fact — a card `emit` recorded without a photograph has nothing
          to re-shoot, and the route's own comment calls that case the first photograph
          the position has, so the button says so rather than claiming a replacement. */}
      <button
        className="pull-preview-reload"
        type="button"
        disabled={busy}
        onClick={() => inputRef.current?.click()}
      >
        {busy
          ? 'Replacing the photo…'
          : row.card.photo === null
            ? 'Add a photo'
            : 'Re-shoot this photo'}
      </button>
      {failure === null ? null : (
        <div className="pull-preview-note">
          <p className="pull-preview-note-text">{failure.message}</p>
          <p className="pull-preview-machine">{failure.code}</p>
        </div>
      )}
    </div>
  )
}
