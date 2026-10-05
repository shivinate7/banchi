/* THE DISPENSER (D316, docs/specs/dispenser.md). The one home of the Web Bluetooth
 * link to the tcg-dealer dispenser, its command allow list and the paced deal loop. No other file
 * talks to the dispenser. `createDealer` is plain TypeScript with no React; `useDealer` is the
 * screen's hook over it. Nothing here is stored, and dealing never resumes on its own (D19). */
import { useCallback, useEffect, useRef, useSyncExternalStore } from 'react'

/* ---- the little of Web Bluetooth this file uses, typed locally (no @types package) ---- */
type Listener = (event: { target?: { value?: DataView } }) => void
interface BtCharacteristic {
  writeValue(data: BufferSource): Promise<void>
  startNotifications(): Promise<unknown>
  addEventListener(name: string, fn: Listener): void
  removeEventListener(name: string, fn: Listener): void
}
interface BtService {
  getCharacteristic(uuid: string): Promise<BtCharacteristic>
}
interface BtServer {
  connect(): Promise<BtServer>
  getPrimaryService(uuid: string): Promise<BtService>
}
interface BtDevice {
  gatt?: BtServer
  addEventListener(name: string, fn: () => void): void
  removeEventListener(name: string, fn: () => void): void
}
interface BtApi {
  requestDevice(options: unknown): Promise<BtDevice>
}
function bluetooth(): BtApi | undefined {
  return (navigator as unknown as { bluetooth?: BtApi }).bluetooth
}

export const DEVICE_NAME = 'ESP_OTA_GATTS'
const SERVICE = '7e8a1e10-1234-4bcd-8aef-1234567890ab'
const COMMAND = '7e8a1e11-1234-4bcd-8aef-1234567890ab'
const REPLY = '7e8a1e12-1234-4bcd-8aef-1234567890ab'
/** The only payloads this product ever writes. Never `MOTOR:START:<n>`, `WIFI:`, `OTA:` or `0x01`. */
const ALLOWED = ['MOTOR:START', 'MOTOR:STOP'] as const
type Command = (typeof ALLOWED)[number]
/** Pause after COMPLETE before the next START (about 0.6 s a card, the pace motion was tuned on). */
/** The newest tiles the Recent rail draws while the dispenser deals: three rows of its five columns. */
export const DEALING_RAIL_TILES = 15

/** After the photo is taken (and COMPLETE came), how long before the next START. */
export const DEAL_GAP_MS = 50
/** After COMPLETE, how long the photo may take to be taken before the dealer stops. */
export const SAVE_WAIT_MS = 3_000
const SILENCE_MS = 5_000
/** After Stop, how long a START still in the air may take to answer before its card is written off. */
const SETTLE_MS = 1_000

export const SAID_LOST = 'Lost the dispenser. Check it is on, then connect again.'
const SAID_SILENT = 'No answer. Check it is on and nothing else is using it.'
const SAID_FAULT = 'The dispenser reported a fault. Check it, then connect again.'
export const SAID_OFF = 'Bluetooth is off. Turn it on, then connect again.'
const SAID_FAILED = 'Could not connect. Check it is on, then try again.'
export const SAID_NO_PHOTO = 'Stopped: no photo came after the last card. Check the tray.'
export const SAID_NOT_SAVED = 'Stopped: a photo was not saved. Check the last card, then start again.'
export const SAID_DROPPED = 'Stopped: a card was not photographed. Resume captures first.'

export type DealerState = 'idle' | 'connecting' | 'connected' | 'dealing' | 'stopped' | 'error'
export interface DealerSnapshot {
  readonly state: DealerState
  readonly cards: number
  readonly said: string
}

const cardsWord = (n: number) => `${n} ${n === 1 ? 'card' : 'cards'}`

// The chosen device lives in module memory, so a second Connect in the same page load skips the chooser.
let remembered: BtDevice | null = null

/** A timing event the dealer reports: the owner's trace carries it (`MotionTrace.mark`). */
export type DealerMark = 'photo-taken' | 'save-answered' | 'start-sent'

export function createDealer({ onMark }: { onMark?: (name: DealerMark, card: number) => void } = {}) {
  let state: DealerState = 'idle'
  let cards = 0
  let note: string | null = null // a said line that outlives later replies, until the next Start
  let ended = false // the hopper ran out
  let snap: DealerSnapshot = { state, cards, said: 'Not connected' }
  const subs = new Set<() => void>()
  let command: BtCharacteristic | null = null
  let teardown: (() => void) | null = null
  let queue: Promise<void> = Promise.resolve()
  let pending = false // a Start is waiting for the old card
  let awaiting = false // a START went out and its reply has not come
  let silence: ReturnType<typeof setTimeout> | undefined
  let gap: ReturnType<typeof setTimeout> | undefined
  let settle: ReturnType<typeof setTimeout> | undefined
  let saveWait: ReturnType<typeof setTimeout> | undefined
  let completed = false // this card's COMPLETE came
  let taken = false // this card's photo was taken
  let sent = 0 // STARTs sent this run: the card number
  let out = new Set<{ card: number }>() // saves not yet answered

  const derive = (): string => {
    if (note !== null) return note
    switch (state) {
      case 'idle': return 'Not connected'
      case 'connecting': return 'Connecting'
      case 'connected': return 'Connected'
      case 'dealing': return `Dealing, ${cardsWord(cards)}`
      case 'stopped': return ended ? `Out of cards after ${cards}` : `Stopped after ${cardsWord(cards)}`
      default: return SAID_FAULT
    }
  }
  const publish = () => {
    const said = derive()
    if (snap.state === state && snap.cards === cards && snap.said === said) return
    snap = { state, cards, said }
    for (const fn of subs) fn()
  }
  const clearTimers = () => {
    clearTimeout(silence)
    clearTimeout(gap)
    clearTimeout(saveWait)
  }
  /* Writes go one at a time, in order: a Stop waits for the write in flight. */
  const write = (text: Command): Promise<void> => {
    if (!ALLOWED.includes(text)) return Promise.reject(new Error(`payload off the allow list: ${text}`))
    const run = queue.then(() => {
      if (command === null) throw new Error('no link')
      return command.writeValue(new TextEncoder().encode(text))
    })
    queue = run.catch(() => {})
    return run
  }
  /* ONE end for every dealing path. */
  const finish = (to: DealerState, why: string | null, sendStop: boolean) => {
    clearTimers()
    state = to
    note = why
    if (sendStop) void write('MOTOR:STOP').catch(() => {})
    publish()
  }
  const lost = () => {
    command = null
    teardown?.()
    teardown = null
    awaiting = false
    finish('error', SAID_LOST, false)
  }
  const deal = () => {
    if (state !== 'dealing') return
    awaiting = true
    completed = false
    taken = false
    sent += 1
    const card = sent
    write('MOTOR:START')
      .then(() => {
        onMark?.('start-sent', card)
        if (state !== 'dealing') return
        clearTimeout(silence)
        silence = setTimeout(() => {
          awaiting = false
          finish('error', SAID_SILENT, true)
        }, SILENCE_MS)
      })
      .catch(() => {
        if (state === 'dealing') lost()
      })
  }
  /* The next START needs this card's COMPLETE and its photo TAKEN, in either order, and no
   * earlier card's save still out: at most one photo is ever unsaved. */
  const next = () => {
    if (state !== 'dealing' || !completed || !taken) return
    for (const t of out) if (t.card !== sent) return
    completed = false // extra photos for one card let one card through
    clearTimeout(saveWait)
    gap = setTimeout(deal, DEAL_GAP_MS)
  }
  const onReply = (text: string) => {
    if (!awaiting) return
    if (text === 'MOTOR:COMPLETE') {
      awaiting = false
      clearTimeout(silence)
      clearTimeout(settle)
      cards += 1
      if (state === 'dealing') {
        completed = true
        if (taken) next()
        else saveWait = setTimeout(() => finish('stopped', SAID_NO_PHOTO, true), SAVE_WAIT_MS)
      }
      publish() // a card already moving when Stop was pressed still counts
      release()
      return
    }
    if (state !== 'dealing') return
    awaiting = false
    if (text === 'MOTOR:END') {
      ended = true
      finish('stopped', null, false) // the hopper is empty: no STOP needed
    } else {
      finish('error', SAID_FAULT, false)
    }
  }

  async function connect(): Promise<void> {
    if (state === 'connecting' || state === 'connected' || state === 'dealing' || state === 'stopped') return
    const api = bluetooth()
    if (api === undefined) return
    teardown?.() // a reconnect drops the old link's listeners first
    teardown = null
    state = 'connecting'
    note = null
    publish()
    try {
      // requestDevice is the first await in the click handler: Chrome needs the user gesture alive.
      remembered ??= await api.requestDevice({
        filters: [{ name: DEVICE_NAME }, { services: [SERVICE] }],
        optionalServices: [SERVICE],
      })
    } catch (e) {
      const { name = '', message = '' } = e as { name?: string; message?: string }
      if (name === 'AbortError' || (name === 'NotFoundError' && /cancel/i.test(message))) {
        state = 'idle' // the owner closed the chooser: nothing to say
      } else {
        state = 'error'
        note = name === 'NotFoundError' ? SAID_OFF : SAID_FAILED
      }
      publish()
      return
    }
    const device = remembered
    try {
      const server = await device.gatt?.connect()
      const service = await server?.getPrimaryService(SERVICE)
      const cmd = await service?.getCharacteristic(COMMAND)
      const reply = await service?.getCharacteristic(REPLY)
      if (cmd === undefined || reply === undefined) throw new Error('no dispenser service')
      const heard: Listener = (event) => {
        const value = event.target?.value
        if (value !== undefined) onReply(new TextDecoder().decode(value))
      }
      reply.addEventListener('characteristicvaluechanged', heard)
      await reply.startNotifications()
      device.addEventListener('gattserverdisconnected', lost)
      teardown = () => {
        reply.removeEventListener('characteristicvaluechanged', heard)
        device.removeEventListener('gattserverdisconnected', lost)
      }
      command = cmd
      state = 'connected'
      publish()
    } catch {
      state = 'error'
      note = SAID_FAILED
      publish()
    }
  }

  /* The old card is down (or written off): a Start that was waiting for it may go. */
  const release = () => {
    if (!pending || state === 'dealing') return
    pending = false
    begin()
  }
  function begin(): void {
    cards = 0
    sent = 0
    out = new Set()
    note = null
    ended = false
    state = 'dealing'
    publish()
    deal()
  }
  /** A Start while a START is still awaiting its COMPLETE waits for it, or for the settle timer. */
  async function start(): Promise<void> {
    if (command === null || (state !== 'connected' && state !== 'stopped')) return
    if (awaiting) pending = true
    else begin()
  }

  /** Stop sends STOP after any write in flight. A card already moving still lands. */
  async function stop(why?: string): Promise<void> {
    pending = false // every stop cancels a Start that is waiting for the old card
    if (state !== 'dealing') return
    clearTimers()
    state = 'stopped'
    note = why ?? null
    publish()
    // a START still in the air may land; if it never answers, write the card off so Start can run again
    if (awaiting) settle = setTimeout(() => {
        awaiting = false
        release()
      }, SETTLE_MS)
    await write('MOTOR:STOP').catch(() => {})
  }

  return {
    connect,
    start,
    stop,
    getSnapshot: () => snap,
    subscribe(fn: () => void) {
      subs.add(fn)
      return () => void subs.delete(fn)
    },
    /** The photo is taken (frame grabbed). Runs `save` at once and returns its outcome. While
     *  dealing it retries once, and a second failure stops the dealer: the card is never lost
     *  silently. The next START does not wait for the save, only for an earlier one. */
    photoTaken(save: () => Promise<unknown>): Promise<unknown> {
      if (state !== 'dealing') return save()
      const ticket = { card: sent }
      out.add(ticket)
      onMark?.('photo-taken', ticket.card)
      taken = true
      const done = (async () => {
        try {
          const v = await save().catch(() => save())
          onMark?.('save-answered', ticket.card)
          return v
        } catch (e) {
          void stop(SAID_NOT_SAVED)
          throw e
        } finally {
          out.delete(ticket)
          next()
        }
      })()
      done.catch(() => {}) // the caller reads the failure; this keeps it from going unhandled
      next()
      return done
    },
    /** Stop dealing and drop the listeners. For unmount. */
    dispose() {
      void stop()
      clearTimeout(settle)
      pending = false
      teardown?.()
      teardown = null
    },
  }
}

export type Dealer = ReturnType<typeof createDealer>

/** True where Chrome's Web Bluetooth exists. */
export const dealerSupported = () => bluetooth() !== undefined

export function useDealer({
  onMark,
  halted,
  dropped,
  ready,
  armed,
}: {
  readonly onMark?: (name: DealerMark, card: number) => void
  readonly halted: boolean
  readonly dropped: number
  readonly ready: boolean
  readonly armed: boolean
}) {
  const ref = useRef<Dealer | null>(null)
  ref.current ??= createDealer({ onMark })
  const dealer = ref.current
  const snap = useSyncExternalStore(dealer.subscribe, dealer.getSnapshot)
  const droppedAtStart = useRef(dropped)
  const start = useCallback(() => {
    droppedAtStart.current = dropped
    return dealer.start()
  }, [dealer, dropped])

  useEffect(() => () => dealer.dispose(), [dealer])
  useEffect(() => {
    const hide = () => {
      if (document.hidden) void dealer.stop()
    }
    document.addEventListener('visibilitychange', hide)
    return () => document.removeEventListener('visibilitychange', hide)
  }, [dealer])
  useEffect(() => {
    if (halted || !ready || !armed) void dealer.stop()
  }, [dealer, halted, ready, armed])
  useEffect(() => {
    if (dropped > droppedAtStart.current) void dealer.stop(SAID_DROPPED)
  }, [dealer, dropped])

  return { ...snap, connect: dealer.connect, photoTaken: dealer.photoTaken, start, stop: () => dealer.stop() }
}
