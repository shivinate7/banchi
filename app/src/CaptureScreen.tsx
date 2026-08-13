import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'

import type { CardSummary, Finish } from './types'
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

/** One capture made in this session: what the server recorded, and what we sent with it. */
type Shot = {
  card: CardSummary
  // The client's own copy of what accompanied this photo, NOT a server echo — the capture
  // response carries neither. Shown under the photo because the bar above shows what the
  // *next* card will get, and a stack toggled wrong is D3's expensive failure: it is
  // discovered here or not until the review queue.
  setHint: string | null
  finish: Finish
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
  const [finish, setFinish] = useState<Finish>('normal')

  // The server's own high-water mark per box, from GET /status. Display only — the docstring
  // on `Inventory.next_index` says so, and the allocator takes no index for exactly that
  // reason. Kept current locally rather than refetched after every capture: a round trip per
  // card at a rig that fires every few seconds buys nothing a reload cannot fix.
  const [nextIndex, setNextIndex] = useState<Record<string, number>>({})
  const [statusNote, setStatusNote] = useState<Note | null>(null)

  const [shots, setShots] = useState<Shot[]>([])
  const [halt, setHalt] = useState<Halt | null>(null)
  const [busy, setBusy] = useState(false)
  const [undoNote, setUndoNote] = useState<(Note & { done: boolean }) | null>(null)
  const [revision, setRevision] = useState(0)

  // Read synchronously inside the capture path. React state cannot serve here: two fires in
  // one tick — a key repeat, or a focused button activated by the same press — would both
  // read the stale `false` and send two photos of one card.
  const busyRef = useRef(false)

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
    // Newest first, and only this box: the route deletes the newest card in the box it is
    // given, and repeated undo walks backwards one card per call.
    for (let i = shots.length - 1; i >= 0; i -= 1) {
      const shot = shots[i]
      if (shot !== undefined && shot.card.box === box) {
        return { box: shot.card.box, index: shot.card.index, label: shot.card.label }
      }
    }
    if (nextForBox === undefined || nextForBox <= 1) return null
    return { box, index: nextForBox - 1, label: null }
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

      try {
        const card = await capture({
          box,
          imageBase64: frame,
          setHint: hint,
          variant: finish,
          // Fresh per photograph. This is the retry guard from spec 5.5 and nothing more:
          // resending one id returns the original card with `created` false and burns no
          // index. It guards a single lost response, which is why it is not a queue.
          captureId: newCaptureId(),
        })
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
        setHalt({ where: 'server', ...describe(err) })
      }
    } finally {
      busyRef.current = false
      setBusy(false)
    }
  }, [box, camera, finish, halt, setHint])

  const doUndo = useCallback(async () => {
    if (busyRef.current || undoTarget === null) return
    busyRef.current = true
    setBusy(true)
    setUndoNote(null)
    try {
      const result = await undoCapture(undoTarget.box, undoTarget.index)
      setShots((prev) =>
        prev.filter(
          (shot) => !(shot.card.box === undoTarget.box && shot.card.index === undoTarget.index),
        ),
      )
      setNextIndex((prev) => ({ ...prev, [String(undoTarget.box)]: undoTarget.index }))
      setRevision((prev) => prev + 1)
      setUndoNote({ done: true, text: `Undone ${result.deleted}`, code: null })
    } catch (err) {
      // Deliberately not a halt. Spec 5.5 stops the run when a card may have gone past
      // unrecorded; a refused undo changed nothing at all, and the refusal names the position
      // that IS undoable. That is information beside the control, not a stopped run.
      setUndoNote({ done: false, ...describe(err) })
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
    const typed = Number.parseInt(boxDraft, 10)
    if (!Number.isInteger(typed) || typed < 1) {
      // A courtesy, not the authority: the server validates the box and answers
      // `box_invalid`. This just saves the round trip.
      setBoxNote('A box is a whole number, 1 or higher.')
      return
    }
    // No confirmation step (spec 5.2). The typed number becomes the current box; if it is
    // already in use it is simply selected.
    setBox(typed)
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
      ? 'Captures are paused. Resume them below.'
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
          {boxIsEmpty ? <p className="capture-flag">box {box} holds no cards yet</p> : null}
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
              is how one physical card ends up with two positions or none. */}
          <p className="capture-halt-message">
            {halt.where === 'camera'
              ? 'Set aside the card at the lens and check the camera feed before you resume.'
              : 'Set aside the card at the lens: it may not have been recorded.'}
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
          <PullConfirm label="Resume captures" onConfirm={() => setHalt(null)} />
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
                <span>{last.finish}</span>
                {last.card.new_box ? <span className="capture-flag">new box</span> : null}
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
                {/* Lower case and no separators when the label is unknown, so a fallback can
                    never be mistaken for the rendered position label above it. */}
                <p className="capture-label">
                  {undoTarget.label ?? `box ${undoTarget.box}, index ${undoTarget.index}`}
                </p>
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
