import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'

import type { CardSummary, Finish, FinishClaim } from './types'
import { ServerError, capture, getStatus, newCaptureId, photoUrl, undoCapture } from './server'
import { manualTrigger } from './trigger'
import { useCamera } from './useCamera'
import { CameraPicker } from './CameraPicker'
import { PullConfirm } from './PullConfirm'
import './CaptureScreen.css'

/* The capture screen — docs/specs/capture-app.md section 5.
 *
 * The screen the owner spends hours in, and the only one Gate B exercises end to end. Every
 * shape below is settled in that spec against a named alternative; where this file makes a
 * call the spec left open, the comment says so and names what it beat.
 *
 * The one thing to hold on to while reading: a card that passes the lens with no record and
 * no photo is unrecoverable — nothing afterwards can say which card it was. Section 5.5 is
 * the whole reason a failed capture stops the run instead of retrying quietly, and the
 * in-flight guard, the halt state and the disabled control below all serve that one rule.
 */

// The trigger seam (spec section 6). Gate B fires on a key and a button; at Gate C the
// motion state machine drops into this same slot and this screen does not change.
//
// 'c' rather than Space or Enter, which are the obvious rig keys and lost for a specific
// reason: both activate whatever button currently has focus. Click Undo with the mouse and
// Space would then mean undo AND capture on every press — a double-fire that writes a
// position for a card nobody photographed. A letter key activates nothing.
const CAPTURE_KEY = 'c'
const UNDO_KEY = 'u'

// What the chips say. The key compared against `event.key` is lower case; the chip is not.
const CAPTURE_KEY_LABEL = 'C'
const UNDO_KEY_LABEL = 'U'

// The enum the server validates against, in ladder-neutral order. Rendered verbatim rather
// than as friendly labels: D3 rung 1 treats this as a trusted claim, and the string on
// screen is the string written into the sidecar and quoted back by a review reason. Friendly
// labels would create a second vocabulary nothing audits — docs/DESIGN.md's own argument for
// showing reason codes as well as names.
const FINISHES: readonly Finish[] = ['normal', 'holo', 'reverse_holo']

/* The fourth state of the finish control, and THE DEFAULT: no claim at all.
 *
 * It is not a fourth member of the enum — the server answers anything outside
 * `pipeline/variant.py:FINISHES` with `variant_invalid` — it is `null`, and it sends no
 * `variant` key at all, exactly as a blank set hint sends no `set_hint`. Both rules come
 * from the same sentence in `sidecar_payload`: the file stays a record of claims the
 * operator actually made (D3 rung 1).
 *
 * THE NEXT PERSON TO TIDY THIS WILL WANT TO DEFAULT IT TO 'normal'. What that costs is
 * structural rather than cosmetic. `pipeline/variant.py:resolve` reaches rung 2
 * (CATALOG_FORCED, "one condition row for that number, so the row decides") and rung 3
 * (detection as a cross-check) only where the sidecar recorded no variant. A default claim
 * on every capture makes both rungs unreachable for every card this product will ever
 * photograph — and D3's own example, the holofoil-only SV-era rare, then returns
 * METADATA_NOT_STOCKED and costs a review-queue tap in place of resolving untouched. That
 * is the zero-attention-per-card property in CLAUDE.md's first line, spent on a claim
 * nobody made.
 *
 * Lower case with a space, which no member of the enum can be. Same trick as the undo
 * fallback further down: a state label must never be readable as a machine string.
 */
const NO_CLAIM_LABEL = 'no claim'

/** One capture made in this session: what the server recorded, and what we sent with it. */
type Shot = {
  card: CardSummary
  // The client's own copy of what accompanied this photo, NOT a server echo — the capture
  // response carries neither. Shown under the photo because the bar above shows what the
  // *next* card will get, and a stack toggled wrong is D3's expensive failure: it is
  // discovered here or not until the review queue.
  setHint: string | null
  // Null when nothing was claimed, which is what was sent: no `variant` key at all. Shown
  // as such rather than as 'normal', because the whole point of the state is that the two
  // are different things.
  finish: FinishClaim
}

/** A message the app shows verbatim. `code` is the server's own error code, or null when
 *  the failure never reached the server. */
type Note = { text: string; code: string | null }

/** A stopped run. `where` decides what to do next, which is the only thing the app adds to
 *  the server's own message — spec section 4 forbids paraphrasing that message. */
type Halt = Note & { where: 'camera' | 'server' }

/** What the next undo would delete. `label` is null for a card captured before this session
 *  loaded: `pipeline/join.py:Position.label` renders that string and the app never composes
 *  a second one, so with no capture response in hand there is nothing to show but the two
 *  numbers the server gave us. */
type UndoTarget = { box: number; index: number; label: string | null }

/** What to call a position on screen — the server's own rendered label, or the two raw
 *  numbers when there is no capture response holding one.
 *
 *  Lower case and no separators in the fallback, so it can never be mistaken for the
 *  rendered label: `Box 3 · Section 1 · Card 7` is a string only `pipeline/join.py` writes,
 *  and a client-side imitation of it would be a second copy of D10's divider size that
 *  nothing keeps in step. Both forms go on screen in the utility face — a position is
 *  metadata, and docs/DESIGN.md gives every number in the product to Martian Mono. */
function positionText(target: UndoTarget): string {
  return target.label ?? `box ${target.box}, index ${target.index}`
}

/* What counts as a box on the way in: digits, and nothing else.
 *
 * Deliberately not `Number.parseInt`, which was here and reads '1e3' as 1 and '3.7' as 3 —
 * handing back a DIFFERENT box that is entirely valid and that the operator never typed.
 * Neither is hypothetical: `<input type="number">` accepts both as values, so both arrive
 * here as strings, and the box decides which physical box a photo is filed into. A wrong
 * one is a real photo at a real position in a box that was never opened, which is the same
 * class of damage as the 33-for-3 typo spec 5.2 accepted knowingly — accepted there because
 * the operator typed it, and not acceptable here because nobody did.
 *
 * Leading zeros are allowed through ('003' is 3): they are unambiguous and a rig operator
 * typing one meant the box they got.
 */
const BOX_DIGITS = /^[0-9]+$/

function describe(err: unknown): Note {
  // The server's own message, unchanged. docs/DESIGN.md's copy rules already reach these
  // strings — they say what happened and what to do next — and rewording them into
  // something friendlier makes them less actionable, not more.
  if (err instanceof ServerError) return { text: err.message, code: err.code }
  if (err instanceof Error) return { text: err.message, code: null }
  return { text: String(err), code: null }
}

function photoSrc(box: number, index: number, revision: number): string {
  /* A position can hold different bytes than it did five seconds ago: undo hard-deletes the
   * photo and releases the index, and the next capture into that box takes it back. The URL
   * is identical either way, so a cached image shows the card that was just deleted.
   *
   * On this screen that is not a cosmetic bug. The reason you undo is that the photo was
   * bad; you re-shoot, and the panel shows you the bad photo again, at the one moment the
   * whole layout exists to let you judge it.
   *
   * `server.ts` argues against a cache-busting parameter and it is right about the two
   * things it names: minting one inside `photoUrl` would thread it through every caller and
   * would defeat caching for the pull preview, which wants neither. Neither applies to one
   * caller doing it locally, and the fix that module recommends — a cache header from the
   * server — is a change to a file this session does not own. If that header lands, this
   * function is what should be deleted.
   */
  const url = photoUrl(box, index)
  return `${url}${url.includes('?') ? '&' : '?'}v=${revision}`
}

function blurActive(): void {
  // A trigger ignores keys typed into an input, a textarea or a select — correctly, since
  // typing a set name must not photograph five cards. The cost is that focus left in a field
  // makes C and U dead keys, and a dead key at a rig reads as a broken app. So Enter hands
  // focus back rather than leaving the operator pressing a key nothing is listening for.
  if (document.activeElement instanceof HTMLElement) document.activeElement.blur()
}

export function CaptureScreen() {
  const camera = useCamera()

  // Box, set hint and finish are client state resent on every capture (spec 5.2). The server
  // holds no notion of a current box, which is what lets two devices work without a session.
  const [box, setBox] = useState<number | null>(null)
  const [boxDraft, setBoxDraft] = useState('')
  const [boxNote, setBoxNote] = useState<string | null>(null)
  const [setHint, setSetHint] = useState('')
  // Null, not 'normal'. See NO_CLAIM_LABEL above: the default has to be "the operator has
  // said nothing", or D3's rungs 2 and 3 are dead for every card this rig ever sees.
  const [finish, setFinish] = useState<FinishClaim>(null)

  // The server's own high-water mark per box, from GET /status. Display only — the docstring
  // on `Inventory.next_index` says so, and the allocator takes no index for exactly that
  // reason. Kept current locally rather than refetched after every capture: a round trip per
  // card at a rig that fires every few seconds buys nothing a reload cannot fix.
  const [nextIndex, setNextIndex] = useState<Record<string, number>>({})
  const [statusNote, setStatusNote] = useState<Note | null>(null)

  const [shots, setShots] = useState<Shot[]>([])
  const [halt, setHalt] = useState<Halt | null>(null)
  const [busy, setBusy] = useState(false)
  // `position` is the rendered label of what was deleted, shown separately from `text` so it
  // can carry the utility face inside a body sentence. Null on a refusal, where the whole
  // message is the server's own and names its own position.
  const [undoNote, setUndoNote] = useState<
    (Note & { done: boolean; position: string | null }) | null
  >(null)
  const [revision, setRevision] = useState(0)

  // The position a replayed capture came back with, or null. Set only when the server
  // answers `created: false` — see the capture path below for why that is the payoff of
  // holding the capture id rather than a curiosity.
  const [replayed, setReplayed] = useState<string | null>(null)

  // Read synchronously inside the capture path. React state cannot serve here: two fires in
  // one tick — a key repeat, or a focused button activated by the same press — would both
  // read the stale `false` and send two photos of one card.
  const busyRef = useRef(false)

  /* The id of the photograph in flight, held across a halt and cleared only when the server
   * has answered. THIS REF IS THE RETRY GUARD (spec 5.5); without it there is none.
   *
   * The id used to be minted inline in the call argument, which meant no code path could
   * ever resend one — so the server's replay branch and every reader of `created` were dead
   * code, and the guard looked covered while guarding nothing. What that costs is the worst
   * failure this screen has: the server commits and the response is lost, leaving a record
   * and a photo at index N for a card that is not in the box. Re-shoot and the card is
   * recorded twice; skip it and every card after it sits one physical slot from its recorded
   * position for the rest of the box, which is the one thing D10's positions cannot survive.
   *
   * A ref rather than state, for the same reason `busyRef` is one: it is read and written
   * inside the capture path, where a value that only updates on the next render is a value
   * that is wrong exactly when it matters.
   */
  const captureIdRef = useRef<string | null>(null)

  const loadStatus = useCallback(async () => {
    try {
      const status = await getStatus()
      setNextIndex(status.next_index ?? {})
      setStatusNote(
        status.next_index === null
          ? {
              text:
                status.problem ??
                'The server could not list the boxes in use. Positions cannot be allocated until that is corrected.',
              code: null,
            }
          : null,
      )
    } catch (err) {
      setStatusNote(describe(err))
    }
  }, [])

  useEffect(() => {
    void loadStatus()
  }, [loadStatus])

  const boxes = useMemo(
    () =>
      Object.keys(nextIndex)
        .map((key) => Number(key))
        .filter((value) => Number.isInteger(value))
        .sort((left, right) => left - right),
    [nextIndex],
  )

  const nextForBox = box === null ? undefined : nextIndex[String(box)]

  // Information, not a confirmation step. The owner was offered a confirmation on a new box
  // and declined it (spec 5.2), and this does not reinstate one: nothing is blocked and
  // nothing is dismissed. It is also the earlier of the two chances to catch a typed 33 for
  // 3 — the server's own `new_box` flag arrives after a photo has already been written.
  const boxIsEmpty = box !== null && (nextForBox === undefined || nextForBox <= 1)

  const last = shots.length === 0 ? undefined : shots[shots.length - 1]

  const undoTarget = useMemo<UndoTarget | null>(() => {
    if (box === null) return null

    // The server's own newest for this box: the high-water mark, minus one. Zero for a box
    // it has never heard of, which is the same thing as empty for the comparison below.
    const serverNewest = nextForBox === undefined ? 0 : nextForBox - 1

    // Newest first, and only this box: the route deletes the newest card in the box it is
    // given, and repeated undo walks backwards one card per call.
    for (let i = shots.length - 1; i >= 0; i -= 1) {
      const shot = shots[i]
      if (shot !== undefined && shot.card.box === box) {
        /* THE SERVER WINS WHERE IT IS AHEAD. This session's shots carry a rendered label and
         * a thumbnail and `/status` carries neither, so a shot is the better thing to show —
         * but only while the two still agree about which card is newest.
         *
         * They stop agreeing in exactly two ways, and both are ordinary. A capture that
         * committed and lost its response (spec 5.5) is a card the server has and this list
         * does not; so is a capture the other device made into the same box, which D13
         * permits by design. In both cases the shot names a position that is no longer the
         * newest, and the route refuses anything but the newest — so nothing is destroyed,
         * but the control has shown the operator the wrong card and the press buys a
         * refusal. Spec 5.4 wants an undo you can aim, and aiming at a stale local guess is
         * the thing it is arguing against.
         */
        if (serverNewest > shot.card.index) break
        return { box: shot.card.box, index: shot.card.index, label: shot.card.label }
      }
    }
    if (serverNewest < 1) return null
    return { box, index: serverNewest, label: null }
  }, [box, nextForBox, shots])

  const doCapture = useCallback(async () => {
    if (busyRef.current) return
    // A halted run ignores the trigger entirely. Not "queues it": spec 5.5 rejected
    // queue-and-continue outright, because photos held in the browser and not yet on the Mac
    // are a second place inventory lives, and D13 has exactly one.
    if (halt !== null || box === null || !camera.ready) return

    busyRef.current = true
    setBusy(true)
    try {
      let frame: string
      try {
        frame = await camera.grabFrameJpeg()
      } catch (err) {
        // A capture that produced no frame is a capture that produced no record. Same halt,
        // different remedy — the run stops either way.
        setHalt({ where: 'camera', ...describe(err) })
        return
      }

      // Trimmed once, so what is shown under the photo is exactly what was sent.
      const hint = setHint.trim() === '' ? undefined : setHint.trim()

      /* One id per PHOTOGRAPH, not one per request — that distinction is the whole guard.
       * Minted here rather than at the top of this function so that a camera fault on a
       * fresh card leaves no id lying in the ref; minted from the ref rather than fresh so
       * that the fire after a resume carries the id of the photograph that halted.
       *
       * A newly grabbed frame with a held id is correct and not a compromise: on a replay
       * the server ignores the image entirely and answers with the card it already
       * committed. That is what lets the halt message ask for the same card back at the
       * lens — whichever way the lost request went, one press resolves it.
       */
      const captureId = captureIdRef.current ?? newCaptureId()
      captureIdRef.current = captureId

      try {
        const card = await capture({
          box,
          imageBase64: frame,
          setHint: hint,
          // Omitted when nothing has been claimed, so the sidecar records no `variant` and
          // D3's rungs 2 and 3 stay live for this card. See NO_CLAIM_LABEL.
          variant: finish ?? undefined,
          captureId,
        })
        // Answered, so the next photograph gets its own id. Cleared on a replay too: the
        // ambiguity that id existed to resolve is now resolved.
        captureIdRef.current = null
        /* `created: false` means this id had already been committed — the halt before it
         * lost a response, not a card. The server returned the original position and burned
         * no index, which is only true because the id was held across the halt.
         *
         * Surfaced rather than swallowed, because the operator is holding a card and needs
         * to know whether it has a position. Cleared by the next capture that creates one. */
        setReplayed(card.created ? null : card.label)
        setShots((prev) =>
          // A replayed capture_id returns the original card with `created` false. Guarding on
          // the key rather than on `created` keeps that from appending a second entry for one
          // physical card, which would put a phantom position under the undo control.
          prev.some((shot) => shot.card.key === card.key)
            ? prev
            : [...prev, { card, setHint: hint ?? null, finish }],
        )
        setNextIndex((prev) => ({ ...prev, [String(card.box)]: card.index + 1 }))
        setRevision((prev) => prev + 1)
        setUndoNote(null)
      } catch (err) {
        // The id stays in the ref. This is the case it exists for: the request may have
        // committed, and only resending the same id can tell the difference without costing
        // a position.
        setHalt({ where: 'server', ...describe(err) })
      }
    } finally {
      busyRef.current = false
      setBusy(false)
    }
  }, [box, camera, finish, halt, setHint])

  const doUndo = useCallback(async () => {
    if (busyRef.current || undoTarget === null) return
    // Read once into a local: `undoTarget` is derived from state this function is about to
    // change, so the value that named what would be deleted is the only value entitled to
    // say what was.
    const target = undoTarget
    busyRef.current = true
    setBusy(true)
    setUndoNote(null)
    try {
      /* The response is discarded on purpose. Its `deleted` is the store's own key — "3/7" —
       * and that is not a thing the operator has ever seen on this screen or anywhere else;
       * `types.ts` says as much where it defines the field ("Not a label and not a SKU").
       * What goes on screen is the rendered position that was under the control a moment
       * ago, which is the same string the server sent when the card was captured. */
      await undoCapture(target.box, target.index)
      setShots((prev) =>
        prev.filter((shot) => !(shot.card.box === target.box && shot.card.index === target.index)),
      )
      setNextIndex((prev) => ({ ...prev, [String(target.box)]: target.index }))
      setRevision((prev) => prev + 1)
      // Whatever the replay note said is about a card that may be the one just deleted, and
      // a stale sentence about a position that no longer exists is worse than none.
      setReplayed(null)
      // "Undo capture" produced "Undone" — docs/DESIGN.md's copy rule that an action keeps
      // its name through the flow.
      setUndoNote({ done: true, text: 'Undone', position: positionText(target), code: null })
    } catch (err) {
      // Deliberately not a halt. Spec 5.5 stops the run when a card may have gone past
      // unrecorded; a refused undo changed nothing at all, and the refusal names the position
      // that IS undoable. That is information beside the control, not a stopped run.
      setUndoNote({ done: false, position: null, ...describe(err) })
    } finally {
      busyRef.current = false
      setBusy(false)
    }
  }, [undoTarget])

  // Only the first of these is the seam Gate C replaces: the motion state machine becomes
  // another capture trigger and this screen does not change. Undo is on the same primitive
  // for its guards rather than for its future — auto-repeat, held modifiers and keys typed
  // into an input are all decided once, in one module, instead of in a second window
  // listener here that would have to be kept in step with it. Undo stays manual forever.
  const captureTrigger = useMemo(() => manualTrigger(CAPTURE_KEY), [])
  const undoTrigger = useMemo(() => manualTrigger(UNDO_KEY), [])

  // Both triggers arm once and dispatch through a ref. Re-arming whenever the closure
  // changes would work today — a keydown listener costs nothing to re-add — and would be
  // wrong at Gate C, where the thing behind the capture seam holds phase (motion, stabilize,
  // capture, cooldown). Tearing that down on every keystroke in the set hint field would
  // reset the state machine mid-card.
  const fireCaptureRef = useRef<() => void>(() => {})
  const fireUndoRef = useRef<() => void>(() => {})
  useEffect(() => {
    fireCaptureRef.current = () => void doCapture()
  }, [doCapture])
  useEffect(() => {
    fireUndoRef.current = () => void doUndo()
  }, [doUndo])
  useEffect(() => captureTrigger.start(() => fireCaptureRef.current()), [captureTrigger])
  useEffect(() => undoTrigger.start(() => fireUndoRef.current()), [undoTrigger])

  function onBoxSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault()
    const draft = boxDraft.trim()
    // Digits first, value second. `Number` rather than `Number.parseInt` once the shape is
    // known: parseInt reads a prefix and discards the rest, which is exactly the silent
    // coercion BOX_DIGITS exists to refuse. isSafeInteger then catches a string of twenty
    // digits, which is well formed and still not a box.
    const value = BOX_DIGITS.test(draft) ? Number(draft) : Number.NaN
    if (!Number.isSafeInteger(value) || value < 1) {
      // A courtesy, not the authority: the server validates the box and answers
      // `box_invalid`. This just saves the round trip. It says what a box is rather than
      // what was wrong with the draft, because the two rejected shapes — '1e3' and '3.7' —
      // are both things a person would call a number.
      setBoxNote('A box is a whole number, 1 or higher. Type the digits only.')
      return
    }
    // No confirmation step (spec 5.2). The typed number becomes the current box; if it is
    // already in use it is simply selected.
    setBox(value)
    setBoxDraft('')
    setBoxNote(null)
    blurActive()
  }

  function onHintSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault()
    blurActive()
  }

  const canCapture = halt === null && !busy && box !== null && camera.ready

  /* Why the capture control is unavailable — first match wins, in the order the operator
   * can act on them.
   *
   * The camera's own faults are deliberately not in this list. `useCamera` reports a missing
   * remembered device and a stream error, CameraPicker prints both verbatim a few pixels
   * above this line, and spec 6.1's requirement that the app say so and ask rather than fall
   * back to another lens is met there. Repeating either sentence here would put the same
   * words on screen twice and give a later edit two places to keep true. */
  const blocked =
    halt !== null
      ? // Above, not below: the halt renders before the stage, so the resume control is up
        // the page from this line in both the two-column and the stacked layout. Pointing
        // the operator the wrong way costs the seconds a stopped run has least of, and
        // docs/DESIGN.md's copy rules ask an error to say what to do next — which includes
        // being right about where.
        'Captures are paused. Resume them above.'
      : box === null
        ? 'Pick a box, or type a new one, before capturing.'
        : null

  return (
    <main className="capture">
      <header className="capture-bar">
        <section className="capture-field">
          {/* A caption, not a heading — the same call Gallery.tsx makes for its specimen
              captions. The one heading on this screen is the halt, which is the only thing
              here that is document structure rather than a label on a control. */}
          <p className="capture-field-name">Box</p>
          <div className="capture-boxes">
            {boxes.map((known) => (
              <button
                key={known}
                type="button"
                className="capture-chip"
                aria-pressed={known === box}
                onClick={() => setBox(known)}
              >
                <span className="capture-chip-value">{known}</span>
                {/* Verbatim from GET /status. Not a card count — it is a high-water mark, and
                    the two disagree the moment a record is removed. */}
                <span className="capture-chip-note">next {nextIndex[String(known)] ?? '?'}</span>
              </button>
            ))}
            {boxes.length === 0 ? (
              <p className="capture-quiet">No box holds a card yet. Type a number.</p>
            ) : null}
          </div>

          <form className="capture-inline" onSubmit={onBoxSubmit}>
            <input
              className="capture-number"
              type="number"
              min="1"
              step="1"
              inputMode="numeric"
              placeholder="new"
              aria-label="Start a new box"
              value={boxDraft}
              onChange={(event) => {
                setBoxDraft(event.target.value)
                setBoxNote(null)
              }}
            />
            <button type="submit" className="capture-go">
              Use box <kbd className="capture-key">↵</kbd>
            </button>
          </form>
          {boxNote === null ? null : <p className="capture-quiet">{boxNote}</p>}
          {/* A state label, not a sentence. The flag style is the utility face at 10px, and
              docs/DESIGN.md gives mono the metadata and the body face every sentence a human
              reads — so what goes in a flag has to be metadata. "box 3 holds no cards yet"
              was prose wearing a chip; this is the same fact in the register the chip is set
              in, and it keeps the separator the position label uses. */}
          {boxIsEmpty ? <p className="capture-flag">box {box} · empty</p> : null}
        </section>

        <form className="capture-field" onSubmit={onHintSubmit}>
          <p className="capture-field-name">Set hint</p>
          {/* Free text, not a picker: there is no catalog in the repo until build-order step
              9, so a picker has no list to offer. Optional, and worth the control — without
              it a collector number that matches rows in two sets reviews as `set_ambiguous`. */}
          <input
            className="capture-text"
            type="text"
            placeholder="sv09"
            aria-label="Set hint"
            value={setHint}
            onChange={(event) => setSetHint(event.target.value)}
          />
        </form>

        <section className="capture-field">
          <p className="capture-field-name">Finish</p>
          <div className="capture-boxes">
            {/* No claim first, because it is where every run starts and where the operator
                comes back to when a stack ends. Drawn distinct — dashed, see the stylesheet
                — and deliberately not in --accent or the flag style: this is the resting
                state, and a default drawn as a warning teaches the operator to clear it by
                picking a finish, which is the one thing it exists to stop. */}
            <button
              type="button"
              className="capture-chip capture-chip-unclaimed"
              aria-pressed={finish === null}
              onClick={() => setFinish(null)}
            >
              <span className="capture-chip-value">{NO_CLAIM_LABEL}</span>
            </button>
            {FINISHES.map((value) => (
              <button
                key={value}
                type="button"
                className="capture-chip"
                aria-pressed={value === finish}
                onClick={() => setFinish(value)}
              >
                <span className="capture-chip-value">{value}</span>
              </button>
            ))}
          </div>
        </section>

        {statusNote === null ? null : (
          <section className="capture-field capture-field-wide">
            <p className="capture-field-name">Server</p>
            <p className="capture-quiet">{statusNote.text}</p>
            <button type="button" className="capture-go" onClick={() => void loadStatus()}>
              Ask again
            </button>
          </section>
        )}
      </header>

      {halt === null ? null : (
        <section className="capture-halt" role="alert">
          <h2 className="capture-halt-title">
            {halt.where === 'camera'
              ? 'Captures are paused. No frame came from the camera.'
              : 'Captures are paused. The card was not recorded.'}
          </h2>
          {/* The server's own message, unchanged (spec section 4). */}
          <p className="capture-halt-message">{halt.text}</p>
          {/* What to do next, which docs/DESIGN.md's copy rules require of an error and which
              the server cannot know. "May not have been recorded" rather than "was not":
              a request can commit and lose its response, and claiming certainty either way
              is how one physical card ends up with two positions or none.

              The server line asks for the same card back rather than for it to be set aside,
              and that instruction is only honest because the capture id is now held across
              the halt. One press then settles it both ways: if the request never committed
              the card is recorded normally, and if it did the server replays the original
              position and burns no index. Set the card aside instead and the run continues
              with the ambiguity unresolved, which is the state D10's positions cannot
              survive. */}
          <p className="capture-halt-message">
            {halt.where === 'camera'
              ? 'Set aside the card at the lens and check the camera feed before you resume.'
              : 'Leave the card at the lens and capture it again after you resume. It may ' +
                'already have been recorded, and the app will say so rather than give it a ' +
                'second position.'}
          </p>
          <p className="capture-halt-message">
            {last === undefined ? (
              'Nothing has been recorded in this session.'
            ) : (
              <>
                The last card recorded is{' '}
                <span className="capture-inline-label">{last.card.label}</span>.
              </>
            )}
          </p>
          {/* Human sentence large, machine string small — the reason-code pattern from
              docs/DESIGN.md, owner-side, so what you saw on screen is greppable across the
              app and the server log. */}
          {halt.code === null ? null : <p className="capture-halt-code">{halt.code}</p>}
          {/* The fill moves here while the run is stopped: the capture control renders
              disabled, so there is again exactly one thing to do, which is what
              docs/DESIGN.md reserves the solid accent for. No key hint — an explicit
              acknowledgement is the point, and a key would let muscle memory resume a run
              the operator has not read the message on. */}
          <PullConfirm
            label="Resume captures"
            onConfirm={() => {
              setHalt(null)
              /* Ask the server where the box actually is. The local high-water mark is a
               * guess from the moment a capture fails: the request may have committed and
               * lost its response, in which case this box's next index moved and nothing on
               * this side saw it — and undo would then aim one card too early. Nothing else
               * in the screen refetches `/status`, by design (a round trip per card at a rig
               * firing every few seconds buys nothing), so this resume is the one moment the
               * stale number can be corrected without a reload.
               *
               * Run on both kinds of halt rather than only the server one. A camera fault
               * sent no request, but a stopped run is also a window in which the other
               * device (D13) can capture into the same box — and one path is easier to keep
               * true than two conditioned on a distinction that does not change the answer.
               */
              void loadStatus()
            }}
          />
        </section>
      )}

      <div className="capture-stage">
        <section className="capture-panel">
          <p className="capture-panel-name">Live</p>
          <div className="capture-frame">
            {/* muted and playsInline are required for autoplay to start at all; neither is a
                preference. No facingMode anywhere — v1 bug 3, and D13 records why: the Cam
                Link presents the rig camera as a plain UVC webcam, indistinguishable by kind
                from the laptop's own. */}
            <video className="capture-media" ref={camera.videoRef} autoPlay playsInline muted />
            {/* The state of the frame, not an explanation of it — the picker below carries
                the explanation. `deviceId` is null when nothing is open at all, which
                `useCamera` guarantees is never a silent stand-in for another camera. */}
            {camera.ready ? null : (
              <p className="capture-frame-note">
                {camera.deviceId === null ? 'No camera is open.' : 'Waiting for frames.'}
              </p>
            )}
          </div>
          <div className="capture-controls">
            <CameraPicker camera={camera} />
            <PullConfirm
              label="Capture card"
              onConfirm={() => void doCapture()}
              disabled={!canCapture}
              keyHint={CAPTURE_KEY_LABEL}
            />
            {/* Which trigger is armed, as the machine string it calls itself. One span, and
                at Gate C it reads `motion` instead without this screen changing. */}
            <p className="capture-trigger">{captureTrigger.name}</p>
            {blocked === null ? null : <p className="capture-quiet">{blocked}</p>}
            {/* The one thing the retry guard is for, said out loud. It appears only after a
                resume, and it is the answer to the question the halt could not settle: the
                paused capture did reach the server, so this photograph took no new position.
                Beside the capture control rather than in the panel opposite, because that is
                where the operator is looking at the moment they press again. */}
            {replayed === null ? null : (
              <p className="capture-quiet">
                Already recorded at{' '}
                <span className="capture-inline-label">{replayed}</span>. The paused capture
                did reach the server, so nothing new was recorded and no position was used.
                Move on to the next card.
              </p>
            )}
          </div>
        </section>

        <section className="capture-panel">
          <p className="capture-panel-name">Last capture</p>
          <div className="capture-frame">
            {last === undefined ? (
              <p className="capture-frame-note">
                Nothing captured in this session yet. The photo of each card lands here, big
                enough to catch a blur or a finger before the card goes back in the box.
              </p>
            ) : (
              // The bytes the Mac stored, not the frame the browser holds. A local preview
              // would show a photo even when the server recorded nothing, which is the one
              // failure this screen exists to make loud.
              <img
                className="capture-media"
                src={photoSrc(last.card.box, last.card.index, revision)}
                alt={`Capture at ${last.card.label}`}
              />
            )}
          </div>
          {last === undefined ? null : (
            <div className="capture-said">
              {/* Rendered by pipeline/join.py and returned by the server. The app never
                  composes a second one. */}
              <p className="capture-label">{last.card.label}</p>
              <p className="capture-said-meta">
                <span>{last.setHint ?? 'no set hint'}</span>
                {/* The same words the chip carries, so one state has one name. Read in the
                    finish slot beside "no set hint", which is what supplies the noun. */}
                <span>{last.finish ?? NO_CLAIM_LABEL}</span>
                {last.card.new_box ? <span className="capture-flag">new box</span> : null}
                {/* Every other flag here describes the capture; this one describes what the
                    server did with it. Kept beside them anyway, and per shot rather than as
                    one banner, because the session list has to stay honest about which
                    photograph took a position and which found one already taken. */}
                {last.card.created ? null : (
                  <span className="capture-flag">already recorded</span>
                )}
              </p>
            </div>
          )}
        </section>
      </div>

      {/* Always visible, never appearing after a capture: a control that appears and
          disappears is one you have to look for at the moment you are least inclined to. */}
      <footer className="capture-undo">
        <div className="capture-undo-target">
          {undoTarget === null ? (
            <p className="capture-quiet">Nothing in this box to undo.</p>
          ) : (
            <>
              {/* Empty alt on purpose, not by omission: the position beside it is the same
                  fact in words, and what the thumbnail adds — whether this is the card you
                  meant — is not a thing alt text can carry. */}
              <img
                className="capture-undo-thumb"
                src={photoSrc(undoTarget.box, undoTarget.index, revision)}
                alt=""
              />
              <div>
                <p className="capture-field-name">Undo deletes</p>
                <p className="capture-label">{positionText(undoTarget)}</p>
              </div>
            </>
          )}
        </div>
        <div className="capture-undo-action">
          {/* No dialog, one tap, repeating (spec 5.4). The deleted photo is of a card still
              in your hand, so the remedy for a wrong undo is to photograph it again — which
              is why this is the stated exception to the no-confirm rule rather than a
              violation of it. Allowed while the run is halted: the halt is about capturing,
              and correcting the last good card is exactly what a stopped run is for. */}
          <button
            type="button"
            className="capture-undo-go"
            onClick={() => void doUndo()}
            disabled={undoTarget === null || busy}
          >
            Undo capture <kbd className="capture-key">{UNDO_KEY_LABEL}</kbd>
          </button>
          {undoNote === null ? null : (
            <p className={undoNote.done ? 'capture-quiet' : 'capture-refused'}>
              {undoNote.text}
              {/* The position in the utility face, inline in a body sentence — the same
                  string the server rendered when the card was captured. This used to say
                  "Undone 3/7": the store's own key, in the body face, naming a thing the
                  operator has never seen on any screen. */}
              {undoNote.position === null ? null : (
                <>
                  {' '}
                  <span className="capture-inline-label">{undoNote.position}</span>
                </>
              )}
              {undoNote.code === null ? null : (
                <span className="capture-halt-code"> {undoNote.code}</span>
              )}
            </p>
          )}
        </div>
      </footer>
    </main>
  )
}
