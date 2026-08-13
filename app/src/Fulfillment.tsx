import { useCallback, useEffect, useState, type ReactNode } from 'react'

import type { InventoryCard, SaleResult } from './types'
import { ServerError, getInventory, markSold, photoUrl, positionLabel, undoSale } from './server'
import { PullConfirm } from './PullConfirm'
import './Fulfillment.css'

/* The Fulfillment view — docs/DESIGN.md, "Fulfillment view — hard constraints".
 *
 * D5's second persona: a retired, non-technical family member who fills orders from his own
 * device. This screen is the entire product for him. He never sees the capture screen, the
 * pull preview, the review queue or a terminal, so anything this file fails to say is not
 * said anywhere — and there is nobody in the room to ask.
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
 *     `SaleResult.restores_to` is the newest thing this rule reaches: it is a pipeline state
 *     word, it is read for whether it is null, and it is never drawn.
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
 *     one action and carries it. The receipts above both — see `Sale` — carry no fill either,
 *     which is what lets them sit over the card panel without making the fill mean "press
 *     something".
 *
 * FIVE THINGS THIS FILE DECIDES THAT docs/DESIGN.md DOES NOT SETTLE. Each is marked at the
 * code that makes it, and each names what would settle it. They are gathered here because a
 * reader deciding whether to trust this screen should be able to see all five at once: what
 * "a card to pull" means with no orders in the system, how long undo stays, when the list is
 * read again, the hash route this is mounted at (which only `App.tsx` can make true), and the
 * nav that must not render over it (in the stylesheet, and only until the shell stops drawing
 * one here).
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

/* HOW LONG UNDO STAYS — the second assumption.
 *
 * docs/DESIGN.md's floor is ">= 10s window" and this is double it. The floor is a floor
 * rather than a target, and the two directions cost differently: a window that is too long
 * costs a line of text on a screen he is not looking at, while a window that is too short
 * costs a sale recorded against the wrong card with no way back. He is retired and not
 * hurried; twenty seconds is the reading speed this is drawn for, not the clicking speed.
 *
 * IT IS PER SALE, NOT PER SCREEN, and that is the fix rather than a refinement. This was one
 * slot — a single `Sale | null` that the next mark-sold overwrote — so the ordinary flow voided
 * the guarantee: a real order pull is two or three cards in a row, the second sale silently
 * discarded the first card's undo, and it re-armed the clock for the new card only. The
 * design row reads "present on every mark-sold", and every is the word that was not honoured.
 *
 * WHAT WOULD SETTLE THE LENGTH: watching him undo one. Gate B item 6 again.
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
 * told about, and how. `UNDO_WINDOW_MS` above is the other half of the same split — the route
 * is what makes the sale reversible, and this file decides how long the control stays up.
 */

/* THE THREE REFUSAL CODES THIS SCREEN BRANCHES ON, each with a different ruling. They were one
 * list called ALREADY_THERE, both members answered as success, and that list was wrong about
 * one of its two members in a way that lost data.
 *
 * `not_sold` on a REVERSAL is success. The card is not sold, which is what the tap asked for —
 * the other device reversed it first, which D13 permits by design and neither device is told
 * about. Reported as a failure it is a dead end: the message would say press it again, pressing
 * it again would answer the same way, and the only person who could act on that is not in the
 * room.
 *
 * `already_sold` on a SALE IS NOT THIS DEVICE'S SALE, and reading it as one is a data-integrity
 * bug rather than a cosmetic one. It means somebody else already sold that copy. Answered as
 * success it printed "Marked sold." and offered an Undo — and that Undo would have reached the
 * server and reversed the OTHER device's real sale, putting a card back on TCGplayer that a
 * buyer has paid for. The stale list this device was holding is what made the tap possible at
 * all, so the answer is to say plainly what happened and read the cards again.
 *
 * `sold_origin_unknown` is a refusal with no remedy he owns. `history.jsonl` cannot say what
 * state the card was in before the sale, so the route will not guess, and pressing Undo again
 * answers identically forever. The control comes down and the sentence names the one action
 * that is actually available to him: ask.
 *
 * The CODES and never the messages. The codes are a stable vocabulary worth branching on; the
 * messages are written for the owner and none of them may reach this screen. */
const ALREADY_SOLD = 'already_sold'
const NOT_SOLD = 'not_sold'
const NO_ORIGIN = 'sold_origin_unknown'

/** The server's code for a thrown thing, or `''` for anything that is not a refusal — a dead
 *  network, a body that did not parse, a bug in this app. Empty rather than null so every
 *  comparison below is a plain `===` against a code that cannot match. */
function refusalCode(err: unknown): string {
  return err instanceof ServerError ? err.code : ''
}

/** Reverse one sale, with `not_sold` read as success for the reason above. Selling has no
 *  such wrapper on purpose: after the `already_sold` bug there is no refusal on that side
 *  this screen may quietly swallow. */
async function unsell(box: number, index: number): Promise<void> {
  try {
    await undoSale(box, index)
  } catch (err) {
    if (refusalCode(err) === NOT_SOLD) return
    throw err
  }
}

/** Whether the sale just recorded can be taken back, out of the server's own answer.
 *
 *  ABSENT IS READ AS NULL, deliberately, and the direction is the safe one. A server old
 *  enough to answer this route without the field would otherwise arrive as `undefined` and
 *  typecheck as a string, and this module casts rather than validates — the same gap
 *  `server.ts:positionLabel` guards on the position label. Suppressing an undo that would
 *  have worked costs him a tap and a question; offering one that cannot work is the defect
 *  this whole path exists to remove. */
function canTakeBack(result: SaleResult): boolean {
  const origin: unknown = result.restores_to
  return typeof origin === 'string' && origin.trim() !== ''
}

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

/** One card that has just left his list, and what he can still do about it.
 *
 *  A LIST OF THESE AND NOT ONE, which is the whole of finding 1's fix. See `UNDO_WINDOW_MS`
 *  for what the single slot cost. Each carries its own `until`, so a second sale cannot
 *  extend or shorten the first card's window, and each renders its own panel — so the count
 *  on screen is the count of sales still standing rather than the most recent one. */
type Sale = {
  card: Sellable

  /** Wall-clock deadline, fixed when the sale is recorded and never touched again. A
   *  duration held here instead would have to be restarted on every re-render. */
  until: number

  /** The sentence at the top of the panel. Two of them exist: his own sale, and the other
   *  device's, which is a receipt for a card leaving his list rather than for anything he
   *  did. Both are receipts, so both are drawn the same way. */
  said: string

  /** False when there is nothing to offer — the server said the sale cannot be reversed, the
   *  reversal was refused with no remedy, or this was never this device's sale. `note` then
   *  says why, because a control that quietly is not there is indistinguishable from one he
   *  failed to find. */
  canUndo: boolean

  /** The second sentence, under the position. Why there is no Undo, or what went wrong with
   *  one. IT LIVES ON THE SALE AND NOT IN `trouble` BY CONSTRUCTION: a failed-undo message
   *  held in screen-wide state outlived the Undo button it told him to press, so the screen
   *  ended up carrying an instruction pointing at a control that was no longer there. Held
   *  here, the sentence and the button expire together because they are the same object. */
  note: string | null
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
  /** Written by this file, never by the server. See the register note at the top. Screen-wide
   *  and short-lived: it belongs to the mark-sold he just attempted, and it is cleared at the
   *  start of the next attempt and on every navigation. Anything that has to outlive a
   *  navigation belongs on a `Sale`, where it expires with the control it refers to. */
  const [trouble, setTrouble] = useState<string | null>(null)

  /** The sales he can still take back, newest first. */
  const [sales, setSales] = useState<Sale[]>([])

  /** The key whose photo did not load, not a boolean: an `onError` for the previous card can
   *  land after he has moved on, and a boolean would blame the card he is looking at. */
  const [photoMissing, setPhotoMissing] = useState<string | null>(null)

  /** READ THE CARDS AGAIN. The list was read once at mount and never again, which is what let
   *  him tap Mark sold on a card the other device had already sold — the stale row was still
   *  on screen an hour later. D13 puts two devices on one store with no session between them,
   *  so the only defence a client has is to re-read at the moments the list can have moved
   *  under it: coming back to it, and finishing a sale. Not a poll — a timer that re-reads
   *  while he is reading is a list that reorders under his thumb. */
  const reread = useCallback(() => setReads((count) => count + 1), [])

  useEffect(() => {
    // StrictMode runs effects twice in dev and a slow first answer can land after the
    // second. The flag makes the late arrival a no-op rather than a flicker.
    let livePage = true
    getInventory()
      /* `.then(ok).catch(fail)` AND NOT `.then(ok, fail)`, which is the whole of finding 6's
       * fix and reads like a style choice. The two-argument form does not cover its own
       * success handler: anything thrown while walking the answer — `Object.entries` on a
       * body with no `cards`, which is what an older or wrong server returns — became an
       * unhandled rejection, and the screen sat on "Getting the cards." for the rest of the
       * morning with no failure shown and no control to press. This form catches both, so a
       * body this screen cannot read fails the same way a dead server does. */
      .then((inventory) => {
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
      })
      .catch(() => {
        if (!livePage) return
        /* THE LIST HE ALREADY HAS IS NOT THROWN AWAY. This used to `setCards(null)`, which
         * was right when the only read was the first one and is wrong now that a re-read can
         * fail: taking a working list off the screen because a refresh did not answer leaves
         * him with less than he had. The full-screen failure below is reached only when
         * there is nothing to show; otherwise the notice sits above the list he is using. */
        setLoadFailed(true)
      })
    return () => {
      livePage = false
    }
  }, [reads])

  /* ONE TIMER FOR THE WHOLE LIST, armed at the soonest deadline rather than one per sale.
   *
   * Each sale carries its own `until`, so this cannot re-arm anybody's window: it fires at
   * the front of the queue, drops whatever has actually expired, and the state change arms it
   * again for the next one. The slack is what stops a timer that fires a hair early from
   * dropping nothing, returning the same array, and leaving the panel up forever — React
   * bails out on an identical reference, so nothing would re-arm it. */
  useEffect(() => {
    if (sales.length === 0) return
    const soonest = Math.min(...sales.map((sale) => sale.until))
    const timer = window.setTimeout(
      () =>
        setSales((held) => {
          const standing = held.filter((sale) => sale.until > Date.now())
          return standing.length === held.length ? held : standing
        }),
      Math.max(0, soonest - Date.now()) + 25,
    )
    return () => window.clearTimeout(timer)
  }, [sales])

  const chosen = cards?.find((card) => card.key === chosenKey) ?? null

  /** Newest first. The sale he is most likely to want back is the one he just made, and the
   *  list everywhere else on this screen is box-walk order for a reason that does not apply
   *  here: these are events, not places. A second sale of the same position replaces its
   *  receipt rather than stacking one on it. */
  const remember = useCallback((sale: Omit<Sale, 'until'>) => {
    setSales((held) => [
      { ...sale, until: Date.now() + UNDO_WINDOW_MS },
      ...held.filter((standing) => standing.card.key !== sale.card.key),
    ])
  }, [])

  const drop = useCallback((card: Sellable) => {
    setCards((prev) => (prev === null ? prev : prev.filter((row) => row.key !== card.key)))
    setChosenKey(null)
    setPulled(false)
  }, [])

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
        const reversible = canTakeBack(await markSold(card.box, card.index))
        drop(card)
        // "Mark sold" produced "Marked sold" — the copy rule that an action keeps its name
        // through the flow, and the reason this state is what the confirmation reads from.
        remember({
          card,
          said: 'Marked sold.',
          canUndo: reversible,
          note: reversible
            ? null
            : 'You cannot take this one back here. Ask for help if it is wrong.',
        })
        reread()
      } catch (err) {
        if (refusalCode(err) === ALREADY_SOLD) {
          /* Not this device's sale, so no Undo — see the ruling at ALREADY_SOLD. Drawn as a
           * receipt rather than as an error because that is what it is from where he sits: a
           * card left his list, and he did not do it. */
          drop(card)
          remember({
            card,
            said: 'Already sold.',
            canUndo: false,
            note: 'Somebody else sold this card, so it has come off your list.',
          })
          reread()
          return
        }
        setTrouble('Nothing was saved. Press Mark sold again.')
      } finally {
        setSaving(false)
      }
    },
    [saving, drop, remember, reread],
  )

  const doUndo = useCallback(
    async (card: Sellable) => {
      if (saving) return
      setSaving(true)
      setTrouble(null)
      try {
        await unsell(card.box, card.index)
        setCards((prev) =>
          prev === null ? prev : inWalkOrder([...prev.filter((row) => row.key !== card.key), card]),
        )
        setSales((held) => held.filter((standing) => standing.card.key !== card.key))
        reread()
      } catch (err) {
        const dead = refusalCode(err) === NO_ORIGIN
        /* The message goes ON THE SALE, so it cannot outlive the button it names. Says what he
         * can see rather than what the request did: "the sale is still saved" was the first
         * draft and is not always true — the reversal can fail after the other device has
         * already made it — while "the card is not back" is true in every case that reaches
         * this line, which is the test a sentence on this screen has to pass. */
        setSales((held) =>
          held.map((standing) =>
            standing.card.key !== card.key
              ? standing
              : {
                  ...standing,
                  canUndo: dead ? false : standing.canUndo,
                  note: dead
                    ? 'This card stays sold. Ask for help to put it back.'
                    : 'The card did not come back. Press Undo again.',
                },
          ),
        )
      } finally {
        setSaving(false)
      }
    },
    [saving, reread],
  )

  /* THE RECEIPTS SIT ABOVE EVERY SCREEN THIS VIEW HAS, and that placement is the second half
   * of finding 1. They were rendered inside the list branch only, so walking into a card
   * hid the Undo while its clock kept running: a ten-second promise that could be on screen
   * for two of them. Above the branch, the control survives navigation and the window means
   * what it says.
   *
   * They carry no fill. docs/DESIGN.md reserves the solid accent for a screen with exactly
   * one thing to do, and a receipt is the way back from the thing he has already done — so
   * the card panel underneath keeps the only fill on screen and the rule is not bent to make
   * this work. */
  const receipts = sales.map((sale) => (
    <div className="fulfillment-panel" key={sale.card.key}>
      <p className="fulfillment-say">{sale.said}</p>
      <p className="fulfillment-place">{sale.card.place}</p>
      {sale.note === null ? null : <p className="fulfillment-say">{sale.note}</p>}
      {!sale.canUndo ? null : (
        /* The place is in the accessible name and not on the button. Two receipts standing at
           once make three buttons that all read "Undo" to anything that cannot see the panel
           they sit in; the visible word stays one word, which is what the copy rules ask of a
           control, and the name says which card it belongs to. */
        <button
          className="fulfillment-plain"
          type="button"
          aria-label={`Undo ${sale.card.place}`}
          onClick={() => void doUndo(sale.card)}
        >
          Undo
        </button>
      )}
    </div>
  ))

  /* A re-read that failed while he already had a list. Says what happened and what to do, and
   * keeps the list — see the loader's catch for why it is not a full-screen failure. */
  const stale =
    loadFailed && cards !== null ? (
      <div className="fulfillment-panel">
        <p className="fulfillment-say">
          These cards may have changed since they were last checked. Try again.
        </p>
        <button
          className="fulfillment-plain"
          type="button"
          onClick={() => {
            setLoadFailed(false)
            reread()
          }}
        >
          Try again
        </button>
      </div>
    ) : null

  let body: ReactNode

  if (cards === null && loadFailed) {
    body = (
      <>
        <h1 className="fulfillment-title">Cards to pull</h1>
        <p className="fulfillment-say">The cards did not load. Try again.</p>
        <button
          className="fulfillment-plain"
          type="button"
          onClick={() => {
            setLoadFailed(false)
            reread()
          }}
        >
          Try again
        </button>
      </>
    )
  } else if (cards === null) {
    body = (
      <>
        <h1 className="fulfillment-title">Cards to pull</h1>
        <p className="fulfillment-say">Getting the cards.</p>
      </>
    )
  } else if (chosen !== null) {
    /* THE CARD PANEL — one card, one action, and the fill that says so.
     *
     * Photo-confirm before each pull, which is D6's whole reason for `GET /photo/<box>/<index>`
     * existing: he sees the card's own capture photo beside its location before he pulls it.
     * The list is replaced rather than sat beside, so there is one thing on screen and one
     * thing to do — which is what lets this screen carry the solid fill at all.
     */
    body = (
      <>
        {/* Leaving, not answering, so it is drawn quiet and sits above the card rather than
            beside the action. A second filled control here would make the fill mean "press
            something", which is the drift docs/DESIGN.md's two-jobs rule exists to stop.
            Going back re-reads the cards: the list he is returning to is the one thing on
            this screen that another device can change while he is not looking at it. */}
        <button
          className="fulfillment-plain"
          type="button"
          onClick={() => {
            setChosenKey(null)
            setPulled(false)
            setTrouble(null)
            reread()
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

        {trouble === null ? null : <p className="fulfillment-say">{trouble}</p>}

        {/* THE TWO STEPS DO NOT SHARE A SPOT, and that is a hazard fixed rather than a layout
            preference. "Pull" and "Mark sold" were the same control in the same place, one
            state apart, so a double-tap on Pull sold the card — one tap of overshoot between
            looking at a photo and recording a sale. The confirmation now takes the slot the
            button was in, at the same box model, so the second tap of a double-tap lands on a
            sentence and "Mark sold" starts below where "Pull" ended.

            The alternative was arming the second button on a timer. Rejected: a control that
            ignores a press is a control he presses harder, and it would have made the fix
            invisible to the thing that has to check it. This one is measurable — the spec
            takes both boxes and asserts they do not overlap. */}
        <div className="fulfillment-action">
          {pulled ? (
            <>
              {/* "Pull" produces "Pulled." — the copy rule, and the reason this reads as one
                  flow rather than as two screens. */}
              <p className="fulfillment-pulled">Pulled.</p>
              <PullConfirm label="Mark sold" onConfirm={() => void doSell(chosen)} />
            </>
          ) : (
            <PullConfirm label="Pull" onConfirm={() => setPulled(true)} />
          )}
        </div>
      </>
    )
  } else {
    body = (
      <>
        <h1 className="fulfillment-title">Cards to pull</h1>
        <p className="fulfillment-say">
          Tap the card the order asks for. You will see its photo and where to find it.
        </p>

        {trouble === null ? null : <p className="fulfillment-say">{trouble}</p>}

        {cards.length === 0 ? (
          <p className="fulfillment-say">
            No cards are for sale right now. There is nothing to pull.
          </p>
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
      </>
    )
  }

  return (
    <main className="fulfillment">
      {receipts}
      {stale}
      {body}
    </main>
  )
}
