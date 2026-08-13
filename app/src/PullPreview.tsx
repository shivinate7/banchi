import { useEffect, useState } from 'react'
import type { InventoryCard } from './types'
import { ServerError, getInventory, photoUrl } from './server'
import './PullPreview.css'

/* The pull preview — docs/specs/capture-app.md §7. LOOK ONLY.
 *
 * This is the last link in the Gate B chain: a card photographed at the start of a run
 * shows up here with the right photo at the right box, section and card. That single
 * claim is the whole screen, which is why nothing on it writes. Mark-sold was offered to
 * the owner and declined for this pass — it needs a route that does not exist and pulls
 * 7b work into the gate.
 *
 * The photo comes from `GET /photo/<box>/<index>`, which is D6's route and the reason
 * that route exists at all: the review queue requires it and the pull modal reuses it.
 *
 * Owner-side for Gate B, so density is fine and docs/DESIGN.md's Fulfillment floors do
 * not bind. They bind on 7b's pull modal, which is a different screen for a different
 * person; borrowing them here would make this screen look like his and set the
 * expectation that it is safe for him to use, which it is not — it lists every card in
 * every state and speaks the pipeline's vocabulary.
 */

/* pipeline/join.py:CARDS_PER_SECTION. Duplicated rather than shared, because nothing
 * carries a constant across the Python and the app today and inventing a channel for one
 * number is worse than restating it beside the renderer that uses it. D10 calls it
 * configurable; if it ever moves, it moves in both files or the app sends a person to the
 * wrong slot. */
const CARDS_PER_SECTION = 25

/* Renders exactly what `pipeline/join.py:Position.label` renders, separator included.
 *
 * The server returns a `label` only from `POST /capture` and `PUT /inventory/...`; an
 * inventory row carries box and index and nothing else, so this screen has to build it.
 * Getting it wrong sends a person to the wrong slot, which is the entire failure this
 * product exists to avoid, so it is written as a port of the Python rather than as
 * arithmetic that happens to agree.
 *
 * The floor-mod is not decoration. JavaScript's `%` is a remainder and Python's is a
 * modulo, and they disagree for a negative left operand: an index of 0 would give card 0
 * here and card 25 there. The server never allocates an index below 1, so this can only
 * fire on a hand-edited inventory.json — which is precisely the case where a silently
 * different answer would be believed.
 */
function positionLabel(box: number, index: number): string {
  const section = Math.floor((index - 1) / CARDS_PER_SECTION) + 1
  const card = ((((index - 1) % CARDS_PER_SECTION) + CARDS_PER_SECTION) % CARDS_PER_SECTION) + 1
  return `Box ${box} · Section ${section} · Card ${card}`
}

/* The inventory arrives as a map keyed `"3/1"`. The key is kept for identity and React,
 * and never parsed: the label is built from `box` and `index` because a store key and a
 * physical location are two different facts that happen to agree today. */
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

type Failure = { code: string | null; message: string; hint: string | null }

/* docs/specs/capture-app.md §4: every response the app surfaces uses the server's own
 * message, because those strings say what happened and what to do next and a friendlier
 * paraphrase is a less actionable one. So a `ServerError` contributes its message
 * verbatim and no hint of ours.
 *
 * A transport failure is the case that rule does not cover: there is no server message
 * because there was no response. `TypeError: Failed to fetch` is true and useless, so it
 * is shown as the machine string it is and given the one sentence the copy rules ask for.
 */
function describeFailure(err: unknown): Failure {
  if (err instanceof ServerError) return { code: err.code, message: err.message, hint: null }
  const message = err instanceof Error ? err.message : String(err)
  return { code: null, message, hint: 'The capture server did not answer. Start it with `make server`.' }
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

  useEffect(() => {
    // StrictMode runs effects twice in dev, and a slow first response can land after the
    // second one. The flag makes the late arrival a no-op rather than a flicker.
    let live = true
    getInventory().then(
      (inventory) => {
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
      },
      (err) => {
        if (!live) return
        setRows(null)
        setFailure(describeFailure(err))
      },
    )
    return () => {
      live = false
    }
  }, [reloads])

  const selectedRow = rows?.find((row) => row.key === selected) ?? null

  return (
    <main className="pull-preview">
      <header className="pull-preview-head">
        <h1 className="pull-preview-title">Pull preview</h1>
        <p className="pull-preview-lede">
          Every captured card, where it sits, and the photo taken of it. Nothing on this screen
          changes anything.
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
        </div>
      </header>

      {failure === null ? null : (
        <div className="pull-preview-note">
          <p className="pull-preview-note-text">{failure.hint ?? failure.message}</p>
          {/* Human label large, machine string small beneath it — docs/DESIGN.md's reason-code
              rule, which exists so that what you saw on screen is greppable against the run
              report. Owner-side only, and this screen is owner-side. */}
          <p className="pull-preview-machine">
            {failure.code === null ? failure.message : `${failure.code} — ${failure.message}`}
          </p>
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
          <ul className="pull-preview-list">
            {rows.map((row) => (
              <li key={row.key}>
                {/* Plain buttons rather than a roving-focus listbox with arrow keys. Tab
                    reaches every one of them for free, and docs/DESIGN.md's every-choice-
                    shows-its-key rule is about the review queue, where a key press commits
                    an answer. Nothing here commits anything, so a key map would be a
                    vocabulary to learn for no decision. */}
                <button
                  className="pull-preview-row"
                  type="button"
                  aria-current={row.key === selected ? 'true' : undefined}
                  onClick={() => setSelected(row.key)}
                >
                  <span className="pull-preview-row-position">
                    {positionLabel(row.card.box, row.card.index)}
                  </span>
                  <span className="pull-preview-row-name">{row.card.name ?? row.card.state}</span>
                </button>
              </li>
            ))}
          </ul>

          {selectedRow === null ? null : (
            <section className="pull-preview-detail">
              {/* The payload of the whole screen. Utility face because it is a position,
                  and sized up because it is the one thing being checked against a physical
                  box across the desk. */}
              <p className="pull-preview-position">
                {positionLabel(selectedRow.card.box, selectedRow.card.index)}
              </p>

              <PhotoPanel
                row={selectedRow}
                absent={photoAbsent === selectedRow.key}
                onAbsent={() => setPhotoAbsent(selectedRow.key)}
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
  absent: boolean
  onAbsent: () => void
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
function PhotoPanel({ row, absent, onAbsent }: PhotoPanelProps) {
  const label = positionLabel(row.card.box, row.card.index)

  if (row.card.photo === null) {
    return (
      <div className="pull-preview-absent">
        <p className="pull-preview-note-text">No photo was stored for this card.</p>
        <p className="pull-preview-machine">photo: null</p>
      </div>
    )
  }

  /* The URL as `server.ts` mints it, with nothing appended.
   *
   * There is a real hazard here and it is worth naming rather than inheriting silently:
   * undo deletes a photo and releases its index, so the next capture reuses this exact URL
   * for different bytes, and `GET /photo` sends no `Cache-Control`, no `ETag` and no
   * `Last-Modified`. A browser that held one of these would show a stale photo at a correct
   * position — precisely the failure this screen exists to catch, and invisible when it
   * happens.
   *
   * A cache-busting query parameter minted here was written and then removed. `server.ts`
   * owns this URL and its own comment rejects that fix by name, on the grounds that the
   * repair belongs in a response header on the server. That is right, and two files in one
   * commit arguing opposite sides of the same hazard is worse than the hazard: the next
   * session would have to work out which one was thinking. The practical exposure is small
   * — with no validator and no freshness header there is nothing for a browser to compute a
   * heuristic lifetime from — and it goes to zero the moment the server sends
   * `Cache-Control: no-store`, which is one line in `server/capture_server.py:_send`. */
  const base = photoUrl(row.card.box, row.card.index)

  if (absent) {
    return (
      <div className="pull-preview-absent">
        <p className="pull-preview-note-text">
          The record has a photo but the file is not on disk. Nothing here can restore it — the
          card is still at {label}.
        </p>
        <p className="pull-preview-machine">{base}</p>
      </div>
    )
  }

  return (
    <img
      /* Remounted per card so a failed load cannot leave the previous card's broken state
         attached to the next one's element. */
      key={row.key}
      className="pull-preview-photo"
      src={base}
      alt={`The card photographed at ${label}`}
      onError={onAbsent}
    />
  )
}
