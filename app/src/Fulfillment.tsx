import { useCallback, useEffect, useState } from 'react'

import type { InventoryCard } from './types'
import { ServerError, getInventory, markSold, photoUrl, positionLabel, undoSale } from './server'
import { PullConfirm } from './PullConfirm'
import './Fulfillment.css'

/* The Fulfillment view — docs/DESIGN.md, "Fulfillment view — hard constraints".
 *
 * D5's second persona: a retired, non-technical family member who fills orders from his own
 * device. This screen is the entire product for him. He never sees the capture screen, the
 * pull preview, the review queue or a terminal, so anything this file fails to say is not
 * said anywhere.
 *
 * BUILT BEFORE GATE B, at the owner's explicit instruction on this branch. Nothing below has
 * ever displayed a card that a real run produced: no card has been photographed, no
 * identification has been paid for, and no card has ever reached the `live` state this screen
 * selects on. It is built to docs/DESIGN.md and validated against that document's numbers and
 * against hand-built fixtures — see `app/tests/fulfillment.spec.ts`, which is where the
 * constraints table lives as assertions rather than as prose in this comment.
 *
 * THE REGISTER IS THE HALF OF THIS FILE THAT IS EASIEST TO BREAK BY BEING HELPFUL.
 * docs/DESIGN.md's copy rules bind hardest here: active voice, the button says exactly what
 * happens, an action keeps its name through the flow, and things are named by what the
 * Fulfiller controls — he has orders and cards, not the things this pipeline is built out of.
 * Three consequences worth stating rather than leaving to be re-derived:
 *
 *   - NO MACHINE STRING APPEARS ON THIS SCREEN. The owner-side habit of printing the
 *     pipeline's own reason string small beneath a friendly label is forbidden here by name
 *     ("Owner-side only: the Fulfillment banned-word list forbids this register entirely").
 *     `PullPreview.tsx` does the opposite and is right to — that is his screen, this is not.
 *   - THE SERVER'S OWN MESSAGES ARE NOT SHOWN EITHER, and this is the one place this app
 *     deliberately departs from `docs/specs/capture-app.md` section 4. Those strings are
 *     written for the person who can act on them: they name store locks, `make server` and
 *     routes. Every one of them is correct and none of them is his. So failures here say what
 *     happened and what to do next in his vocabulary, and the detail stays where it is
 *     actionable — the owner reads the same failure with the message intact on his screens.
 *   - THE SOLID ACCENT FILL IS THE POINT OF THIS SCREEN. docs/DESIGN.md reserves it for a
 *     screen with exactly one thing to do, and calls his pull-confirm "the loudest thing he
 *     ever sees". So the flow below is shaped so that there IS exactly one thing to do at
 *     each step: the list offers many cards and carries no fill, and the card panel offers
 *     one action and carries it.
 *
 * FOUR THINGS THIS FILE DECIDES THAT docs/DESIGN.md DOES NOT SETTLE. Each is marked at the
 * code that makes it, and each names what would settle it. They are gathered here because a
 * reader deciding whether to trust this screen should be able to see all four at once: what
 * "a card to pull" means with no orders in the system, how long undo stays, the hash route
 * this is mounted at (which only `App.tsx` can make true), and the nav that must not render
 * over it (in the stylesheet, and only until the shell stops drawing one here).
 */

/* WHICH CARDS HE SEES — the first assumption, and the largest.
 *
 * D7 describes the real input: "Order pulls select specific positions and mark them sold
 * individually." There are no orders in this system. Nothing reads a TCGplayer order, no
 * route serves one, and `store/master.py` has no order record — so "the cards in this order"
 * cannot be answered today and this screen answers the nearest question it can: every card
 * that is for sale, in box-walk order, for him to find the one the order names.
 *
 * `live` and nothing else. `store/master.py` documents the ladder: `pushed` means a row was
 * written into an import file, `staged` means TCGplayer confirmed it, and only `live` means a
 * later export showed quantity against it — which is to say only a `live` card is one a buyer
 * could have ordered. Marking a `captured` card sold would record a sale of something that
 * was never listed.
 *
 * WHAT WOULD SETTLE IT: an order feed. Until one exists this list is a haystack he searches
 * by name, and the first real order is what will say whether that is acceptable — which is
 * item 6 of the Gate B measurements in `docs/specs/capture-app.md` section 10.2.
 */
const FOR_SALE = 'live'

/* HOW LONG UNDO STAYS — the fifth assumption.
 *
 * docs/DESIGN.md's floor is ">= 10s window" and this is double it. The floor is a floor
 * rather than a target, and the two directions cost differently: a window that is too long
 * costs a line of text on a screen he is not looking at, while a window that is too short
 * costs a sale recorded against the wrong card with no way back. He is retired and not
 * hurried; twenty seconds is the reading speed this is drawn for, not the clicking speed.
 *
 * WHAT WOULD SETTLE IT: watching him undo one. Gate B item 6 again.
 */
const UNDO_WINDOW_MS = 20_000

/* THE SALE GOES THROUGH `server.ts` LIKE EVERY OTHER CALL IN THIS APP.
 *
 * It did not until 2026-08-13: this file built its own `fetch` against
 * `POST /inventory/<box>/<index>/sold`, and its own base URL out of `photoUrl`, because that
 * module belonged to another group on the day the route landed. It said in as many words that
 * the whole block should be deleted the moment `server.ts` exported a mark-sold call. It has,
 * so it was — `markSold` and `undoSale`, one route in both directions, and the reasoning about
 * the empty body and the missing server-side expiry moved across with them.
 *
 * What stayed here is the only part of it that was ever this screen's: which refusals he is
 * told about. `UNDO_WINDOW_MS` above is the other half of the same split — the route is what
 * makes the sale reversible, and this file decides how long the control stays on screen.
 */

/* `already_sold` and `not_sold` are answered as success, and that is the only thing this
 * screen knows about the server's vocabulary.
 *
 * Both mean the card is already in the state he just asked for — the other device sold it, or
 * reversed it, which D13 permits by design and neither device is told about. Reported as a
 * failure they are a dead end: the message would say press it again, pressing it again would
 * answer the same way, and the only person who could act on that is not in the room. Treated
 * as success the screen ends up saying what is true.
 *
 * IT LIVES HERE AND NOT IN `server.ts` FOR THE SAME REASON THE MESSAGES DO NOT REACH THIS
 * SCREEN: it is a ruling about one persona (D5). On the owner's screens the same refusal is
 * worth seeing, so the wire keeps throwing it and this view is where it is caught.
 *
 * Deliberately the CODE and never the message. The codes are a stable vocabulary worth
 * branching on; the messages are written for the owner and none of them may reach this
 * screen — see the register note at the top of this file. */
const ALREADY_THERE = ['already_sold', 'not_sold']

async function sale(box: number, index: number, undo: boolean): Promise<void> {
  try {
    await (undo ? undoSale(box, index) : markSold(box, index))
  } catch (err) {
    if (err instanceof ServerError && ALREADY_THERE.includes(err.code)) return
    throw err
  }
}

const sellCard = (box: number, index: number) => sale(box, index, false)
const unsellCard = (box: number, index: number) => sale(box, index, true)

/** One card he can be asked to pull: where it is, and what it is called.
 *
 *  `place` is the server's own rendered label — `pipeline/join.py:Position.label`, decorated
 *  onto every inventory row by `do_inventory`. It is never composed here, for the reason
 *  `types.ts` states on the field: a second renderer is a second copy of D10's divider size,
 *  and of the two answers the one on screen is the one somebody walks to a box with. */
type Sellable = {
  key: string
  box: number
  index: number
  place: string
  name: string
}

/* A card with no rendered position is LEFT OUT of his list, and counted where he can see the
 * count.
 *
 * `do_inventory` leaves a row undecorated when its box or index will not coerce to an integer,
 * on the grounds that a placeholder label would name a position that does not exist. That is
 * the right call and it lands here as a card this screen cannot use for its only purpose: the
 * whole of what it does is say where a card is. `PullPreview.tsx` shows such a row with its
 * store key beside it, which is exactly right on the owner's screen and is the machine
 * register this one may not use.
 *
 * So it is dropped from the walk and reported as a number instead. Never dropped silently —
 * CLAUDE.md's hard rule is that no card leaves the pipeline unrecorded, and a row he cannot
 * see and cannot be told about is the shape that rule forbids.
 */
function sellable(key: string, card: InventoryCard): Sellable | null {
  /* The same one-line rule the owner's two screens read that field with, and the same
   * function — `server.ts:positionLabel`. What differs is what each screen does with a null,
   * and that difference is the argument below rather than a second reader of the field. */
  const place = positionLabel(card)
  if (place === null) return null
  return {
    key,
    box: card.box,
    index: card.index,
    place,
    /* A live card has been identified, so a null name is not expected — but it is cheap to
     * survive and expensive to render as "null" on the one screen with no way to report a
     * bug. The fallback is a sentence rather than a placeholder token, because everything
     * else in this column is a card's name and he has no way to know a token is not one. */
    name: card.name ?? 'This card has no name recorded',
  }
}

/** Box-walk order: box, then index. The order the cards physically sit in, which is the
 *  order docs/DESIGN.md requires of this view and the same order `store/queues.py:sort_key`
 *  falls back to. Reading down the list is walking the boxes. */
function inWalkOrder(cards: Sellable[]): Sellable[] {
  return [...cards].sort((a, b) => a.box - b.box || a.index - b.index)
}

export function Fulfillment() {
  const [cards, setCards] = useState<Sellable[] | null>(null)
  const [unplaced, setUnplaced] = useState(0)
  const [loadFailed, setLoadFailed] = useState(false)
  const [reads, setReads] = useState(0)

  /* The card he is holding, if any, and whether he has confirmed it against its photo.
   * Two pieces of state rather than one enum, because they answer two questions that stay
   * separate: which card, and how far through its two steps. */
  const [chosenKey, setChosenKey] = useState<string | null>(null)
  const [pulled, setPulled] = useState(false)

  const [saving, setSaving] = useState(false)
  /** Written by this file, never by the server. See the register note at the top. */
  const [trouble, setTrouble] = useState<string | null>(null)

  /** The sale he can still take back. Cleared when the window closes. */
  const [sold, setSold] = useState<Sellable | null>(null)

  /** The key whose photo did not load, not a boolean: an `onError` for the previous card can
   *  land after he has moved on, and a boolean would blame the card he is looking at. */
  const [photoMissing, setPhotoMissing] = useState<string | null>(null)

  useEffect(() => {
    // StrictMode runs effects twice in dev and a slow first answer can land after the
    // second. The flag makes the late arrival a no-op rather than a flicker.
    let livePage = true
    getInventory().then(
      (inventory) => {
        if (!livePage) return
        const forSale = Object.entries(inventory.cards).filter(
          ([, card]) => card.state === FOR_SALE,
        )
        const placed: Sellable[] = []
        for (const [key, card] of forSale) {
          const row = sellable(key, card)
          if (row !== null) placed.push(row)
        }
        setCards(inWalkOrder(placed))
        setUnplaced(forSale.length - placed.length)
        setLoadFailed(false)
      },
      () => {
        if (!livePage) return
        setCards(null)
        setLoadFailed(true)
      },
    )
    return () => {
      livePage = false
    }
  }, [reads])

  useEffect(() => {
    if (sold === null) return
    const timer = window.setTimeout(() => setSold(null), UNDO_WINDOW_MS)
    return () => window.clearTimeout(timer)
  }, [sold])

  const chosen = cards?.find((card) => card.key === chosenKey) ?? null

  const doSell = useCallback(
    async (card: Sellable) => {
      /* Guarded rather than disabled. docs/DESIGN.md gives this view no disabled state at all
       * — `PullConfirm`'s `disabled` prop is documented as owner-side only — and a control
       * that greys out under his finger is a control he presses again harder. A second press
       * while the first is in flight does nothing instead. */
      if (saving) return
      setSaving(true)
      setTrouble(null)
      try {
        await sellCard(card.box, card.index)
        setCards((prev) => (prev === null ? prev : prev.filter((row) => row.key !== card.key)))
        setChosenKey(null)
        setPulled(false)
        // "Mark sold" produced "Marked sold" — the copy rule that an action keeps its name
        // through the flow, and the reason this state is what the confirmation reads from.
        setSold(card)
      } catch {
        setTrouble('Nothing was saved. Press Mark sold again.')
      } finally {
        setSaving(false)
      }
    },
    [saving],
  )

  const doUndo = useCallback(
    async (card: Sellable) => {
      if (saving) return
      setSaving(true)
      setTrouble(null)
      try {
        await unsellCard(card.box, card.index)
        setCards((prev) => (prev === null ? prev : inWalkOrder([...prev, card])))
        setSold(null)
      } catch {
        // Says what he can see rather than what the request did. "The sale is still saved"
        // was the first draft and is not always true — the reversal can fail after the other
        // device has already made it — while "the card is not back" is true in every case
        // that reaches this line, which is the test a sentence on this screen has to pass.
        setTrouble('The card did not come back. Press Undo again.')
      } finally {
        setSaving(false)
      }
    },
    [saving],
  )

  if (loadFailed) {
    return (
      <main className="fulfillment">
        <h1 className="fulfillment-title">Cards to pull</h1>
        <p className="fulfillment-say">The cards did not load. Try again.</p>
        <button
          className="fulfillment-plain"
          type="button"
          onClick={() => {
            setLoadFailed(false)
            setReads((n) => n + 1)
          }}
        >
          Try again
        </button>
      </main>
    )
  }

  if (cards === null) {
    return (
      <main className="fulfillment">
        <h1 className="fulfillment-title">Cards to pull</h1>
        <p className="fulfillment-say">Getting the cards.</p>
      </main>
    )
  }

  /* THE CARD PANEL — one card, one action, and the fill that says so.
   *
   * Photo-confirm before each pull, which is D6's whole reason for `GET /photo/<box>/<index>`
   * existing: he sees the card's own capture photo beside its location before he pulls it.
   * The list is replaced rather than sat beside, so there is one thing on screen and one
   * thing to do — which is what lets this screen carry the solid fill at all.
   */
  if (chosen !== null) {
    return (
      <main className="fulfillment">
        {/* Leaving, not answering, so it is drawn quiet and sits above the card rather than
            beside the action. A second filled control here would make the fill mean "press
            something", which is the drift docs/DESIGN.md's two-jobs rule exists to stop. */}
        <button
          className="fulfillment-plain"
          type="button"
          onClick={() => {
            setChosenKey(null)
            setPulled(false)
            setTrouble(null)
          }}
        >
          Back to the cards
        </button>

        <p className="fulfillment-place fulfillment-place-large">{chosen.place}</p>

        {photoMissing === chosen.key ? (
          /* The photo is gone and the card is not. Says where it still is, because that is
             the only part of this screen he needs to finish the job. */
          <p className="fulfillment-say">
            The photo is missing. The card is still in the place above.
          </p>
        ) : (
          <img
            // Remounted per card so a failed load cannot leave the previous card's broken
            // state attached to the next one's element.
            key={chosen.key}
            className="fulfillment-photo"
            src={photoUrl(chosen.box, chosen.index)}
            alt={`The card in ${chosen.place}`}
            onError={() => setPhotoMissing(chosen.key)}
          />
        )}

        <p className="fulfillment-name">{chosen.name}</p>

        {/* One line, and it changes only after the pull. "Pull" produces "Pulled." — the copy
            rule, and the reason this reads as one flow rather than as two screens. */}
        {pulled ? <p className="fulfillment-say">Pulled.</p> : null}

        {trouble === null ? null : <p className="fulfillment-say">{trouble}</p>}

        <div className="fulfillment-action">
          {pulled ? (
            <PullConfirm label="Mark sold" onConfirm={() => void doSell(chosen)} />
          ) : (
            <PullConfirm label="Pull" onConfirm={() => setPulled(true)} />
          )}
        </div>
      </main>
    )
  }

  return (
    <main className="fulfillment">
      <h1 className="fulfillment-title">Cards to pull</h1>
      <p className="fulfillment-say">
        Tap the card the order asks for. You will see its photo and where to find it.
      </p>

      {sold === null ? null : (
        <div className="fulfillment-sold">
          <p className="fulfillment-say">Marked sold.</p>
          <p className="fulfillment-place">{sold.place}</p>
          {/* Not filled. He has already done the one thing this screen asked; undo is the
              way back from it, not the next step, and the fill belongs to whatever there is
              exactly one of. */}
          <button className="fulfillment-plain" type="button" onClick={() => void doUndo(sold)}>
            Undo
          </button>
        </div>
      )}

      {trouble === null ? null : <p className="fulfillment-say">{trouble}</p>}

      {cards.length === 0 ? (
        <p className="fulfillment-say">No cards are for sale right now. There is nothing to pull.</p>
      ) : (
        <ul className="fulfillment-list">
          {cards.map((card) => (
            <li key={card.key}>
              {/* The whole row is the target. A row with a button on it has two things to hit
                  and one of them is smaller than the other; this way the smallest target on
                  the screen is the size of the row. */}
              <button
                className="fulfillment-row"
                type="button"
                onClick={() => {
                  setChosenKey(card.key)
                  setPulled(false)
                  setTrouble(null)
                }}
              >
                <span className="fulfillment-name">{card.name}</span>
                <span className="fulfillment-place">{card.place}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* Counted, never silently dropped — see `sellable`. Reads as a sentence rather than as
          a number in a chip, because the only thing he can do about it is tell someone. */}
      {unplaced === 0 ? null : (
        <p className="fulfillment-say">
          {unplaced === 1
            ? '1 card for sale is not shown here, because its place is missing. Ask for help with that one.'
            : `${unplaced} cards for sale are not shown here, because their places are missing. Ask for help with those.`}
        </p>
      )}
    </main>
  )
}
