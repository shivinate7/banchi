// Protects: The dispenser deals one card per command, paced, over an allow-listed link, and stops on empty, error, silence, a lost link or Stop.
// Governs: D316, D19
import { expect, test } from './unit'
import { createDealer, DEAL_GAP_MS } from '../../src/dealer'

/* THE DISPENSER'S LINK AND LOOP, driven with no React and no clock. `navigator.bluetooth` is a fake
 * that replays tcg-dealer's RECORDED sequences (fixtures/paced_loop_10_of_10.json and
 * fixtures/empty_hopper.json, copied below as pairs: the reply to each START and its delay).
 * Like tcg-dealer's own `mock_dealer.py`, it rejects a START that is not the next expected write
 * and any payload off the allow list. A rejected write is also recorded, so a product that
 * swallows the error still fails here. `bad_card_length.json` is never replayed: its payload
 * (`MOTOR:START:<n>`) is the one this product must never send.
 *
 * SYNTHETIC, NOT RECORDED: the ERROR reply, silence, a disconnect mid-loop, and Stop while a
 * START is in flight. tcg-dealer has no fixture for them. `STOP` is accepted at any time. */

const SERVICE = '7e8a1e10-1234-4bcd-8aef-1234567890ab'
const ALLOWED = ['MOTOR:START', 'MOTOR:STOP']

type Pair = readonly [reply: string | null, afterMs: number]
const COMPLETE: Pair = ['MOTOR:COMPLETE', 420]
// RECORDED: paced_loop_10_of_10.json (10 x START, COMPLETE after 420 ms)
const PACED_10: Pair[] = Array.from({ length: 10 }, () => COMPLETE)
// RECORDED: empty_hopper.json (3 cards, then the 4th START gets END after 540 ms)
const EMPTY_HOPPER: Pair[] = [COMPLETE, COMPLETE, COMPLETE, ['MOTOR:END', 540]]

/* ---- a controllable clock: setTimeout, clearTimeout and Date.now only ---- */
type Timer = { at: number; fn: () => void; id: number }
const realImmediate = setImmediate
const realSetTimeout = globalThis.setTimeout
const realClearTimeout = globalThis.clearTimeout
const realNow = Date.now
let now = 0
let timers: Timer[] = []
let nextId = 1

function installClock(): void {
  now = 1_000_000
  timers = []
  globalThis.setTimeout = ((fn: () => void, ms = 0) => {
    const id = nextId++
    timers.push({ at: now + Number(ms), fn, id })
    return id as never
  }) as never
  globalThis.clearTimeout = ((id: number) => {
    timers = timers.filter((t) => t.id !== id)
  }) as never
  Date.now = () => now
}
function restoreClock(): void {
  globalThis.setTimeout = realSetTimeout
  globalThis.clearTimeout = realClearTimeout
  Date.now = realNow
}
async function flush(): Promise<void> {
  for (let i = 0; i < 6; i += 1) await new Promise<void>((r) => realImmediate(r))
}
async function advance(ms: number): Promise<void> {
  const target = now + ms
  await flush()
  for (;;) {
    const due = timers.filter((t) => t.at <= target).sort((a, b) => a.at - b.at || a.id - b.id)[0]
    if (due === undefined) break
    timers = timers.filter((t) => t !== due)
    now = due.at
    due.fn()
    await flush()
  }
  now = target
  await flush()
}

/* ---- the fake dispenser ---- */
type Listener = (event: unknown) => void
const rig = {
  pairs: [] as Pair[],
  next: 0,
  writes: [] as string[],
  rejected: [] as string[],
  requests: [] as unknown[],
  latency: 0,
  inFlight: 0,
  maxInFlight: 0,
  notify: [] as Listener[],
  down: [] as Listener[],
}

function reset(pairs: Pair[], latency = 0): void {
  Object.assign(rig, { pairs, next: 0, writes: [], rejected: [], latency, inFlight: 0, maxInFlight: 0, notify: [], down: [] })
}
function emit(text: string): void {
  const value = new DataView(new TextEncoder().encode(text).buffer)
  for (const fn of rig.notify) fn({ target: { value } })
}
function disconnect(): void {
  for (const fn of rig.down) fn({})
}

async function write(data: BufferSource): Promise<void> {
  const bytes = ArrayBuffer.isView(data) ? new Uint8Array(data.buffer, data.byteOffset, data.byteLength) : new Uint8Array(data)
  const text = new TextDecoder().decode(bytes)
  rig.writes.push(text)
  if (!ALLOWED.includes(text)) {
    rig.rejected.push(text)
    throw new Error(`payload off the allow list: ${text}`)
  }
  rig.inFlight += 1
  rig.maxInFlight = Math.max(rig.maxInFlight, rig.inFlight)
  if (text === 'MOTOR:START') {
    const pair = rig.pairs[rig.next]
    if (pair === undefined) {
      rig.inFlight -= 1
      rig.rejected.push(text)
      throw new Error('START is not the next expected write')
    }
    rig.next += 1
    if (pair[0] !== null) globalThis.setTimeout(() => emit(pair[0] as string), pair[1])
  }
  if (rig.latency > 0) await new Promise<void>((r) => globalThis.setTimeout(r, rig.latency))
  rig.inFlight -= 1
}

function characteristic(uuid: string): Record<string, unknown> {
  const self: Record<string, unknown> = {
    uuid,
    properties: { write: true, writeWithoutResponse: true, notify: true },
    writeValue: write,
    writeValueWithResponse: write,
    writeValueWithoutResponse: write,
    startNotifications: async () => self,
    stopNotifications: async () => self,
    addEventListener: (name: string, fn: Listener) => {
      if (name === 'characteristicvaluechanged') rig.notify.push(fn)
    },
    removeEventListener: () => {},
  }
  return self
}

const server = {
  connected: true,
  connect: async () => server,
  disconnect: () => {},
  getPrimaryService: async (uuid: string) => {
    if (uuid !== SERVICE) throw new Error('no such service')
    return { getCharacteristic: async (c: string) => characteristic(c) }
  },
}
/* ONE device object for the whole file: the product keeps the device in module memory, so a second
   test's Connect reuses it. Its behaviour is the mutable `rig`, reset per test. */
const device = {
  name: 'ESP_OTA_GATTS',
  gatt: server,
  addEventListener: (name: string, fn: Listener) => {
    if (name === 'gattserverdisconnected') rig.down.push(fn)
  },
  removeEventListener: () => {},
}
Object.defineProperty(globalThis, 'navigator', {
  configurable: true,
  value: {
    bluetooth: {
      requestDevice: async (options: unknown) => {
        rig.requests.push(options)
        return device
      },
    },
  },
})

/* tolerant read: the contract names `state`, `cards`, `said`, not how createDealer exposes them */
type Snap = { state: string; cards: number; said: string }
function read(dealer: unknown): Snap {
  const d = dealer as { getSnapshot?: () => Snap; snapshot?: () => Snap } & Snap
  return d.getSnapshot?.() ?? d.snapshot?.() ?? { state: d.state, cards: d.cards, said: d.said }
}
type Dealer = { connect: () => Promise<void>; start: () => unknown; stop: () => unknown }

async function connected(pairs: Pair[], latency = 0): Promise<Dealer> {
  reset(pairs, latency)
  const dealer = createDealer() as unknown as Dealer
  await dealer.connect()
  await flush()
  return dealer
}

test.describe.configure({ mode: 'serial' })
test.beforeEach(installClock)
test.afterEach(() => {
  restoreClock()
  expect(rig.rejected, 'a write was rejected by the fake dispenser').toEqual([])
})

test('the gap constant is the 200 ms the motion trigger was tuned on', () => {
  expect(DEAL_GAP_MS).toBe(200)
})

test('Connect asks the chooser first, with the name and service filters, and reaches connected', async () => {
  reset(PACED_10)
  rig.requests = []
  const dealer = createDealer() as unknown as Dealer
  const pending = dealer.connect()
  // requestDevice is the first await in the click handler: it was called before any tick passed
  expect(rig.requests).toHaveLength(1)
  expect(rig.requests[0]).toMatchObject({
    filters: [{ name: 'ESP_OTA_GATTS' }, { services: [SERVICE] }],
    optionalServices: [SERVICE],
  })
  await pending
  await flush()
  expect(read(dealer).state).toBe('connected')
  expect(read(dealer).said).toBe('Connected')
})

test('a second Connect in the same page load skips the chooser', async () => {
  reset(PACED_10)
  const before = rig.requests.length
  const dealer = createDealer() as unknown as Dealer
  await dealer.connect()
  await flush()
  expect(rig.requests.length).toBe(before)
  expect(read(dealer).state).toBe('connected')
})

test('paced loop, 10 of 10: START, wait for COMPLETE, gap, repeat, with the gap honored', async () => {
  const dealer = await connected(PACED_10)
  void dealer.start()
  await flush()
  expect(read(dealer).state).toBe('dealing')
  expect(rig.writes).toEqual(['MOTOR:START'])
  await advance(419)
  expect(read(dealer).cards).toBe(0)
  await advance(1)
  expect(read(dealer).cards).toBe(1)
  expect(read(dealer).said).toBe('Dealing, 1 card')
  // the next START waits DEAL_GAP_MS after COMPLETE, and not a tick less
  await advance(DEAL_GAP_MS - 1)
  expect(rig.writes).toEqual(['MOTOR:START'])
  await advance(1)
  expect(rig.writes).toEqual(['MOTOR:START', 'MOTOR:START'])
  // eight more cards: the 10th COMPLETE lands 420 ms after the 10th START
  await advance(8 * (420 + DEAL_GAP_MS) + 420)
  expect(read(dealer).cards).toBe(10)
  expect(rig.writes.filter((w) => w === 'MOTOR:START')).toHaveLength(10)
  expect(rig.maxInFlight).toBe(1)
  // Stop before the 11th START: the fixture holds no 11th card, so none may be sent
  await dealer.stop()
  await flush()
  await advance(5_000)
  expect(rig.writes.filter((w) => w === 'MOTOR:START')).toHaveLength(10)
  expect(rig.writes.at(-1)).toBe('MOTOR:STOP')
  expect(read(dealer).state).toBe('stopped')
  expect(read(dealer).said).toBe('Stopped after 10 cards')
})

test('empty hopper: 3 cards, then END is a stop and not an error', async () => {
  const dealer = await connected(EMPTY_HOPPER)
  void dealer.start()
  await advance(3 * (420 + DEAL_GAP_MS) + 540 + 10)
  expect(read(dealer).cards).toBe(3)
  expect(read(dealer).state).toBe('stopped')
  expect(read(dealer).said).toBe('Out of cards after 3')
  expect(rig.writes.filter((w) => w === 'MOTOR:START')).toHaveLength(4)
  await advance(10_000)
  expect(rig.writes.filter((w) => w === 'MOTOR:START')).toHaveLength(4)
})

test('SYNTHETIC: an ERROR reply stops the loop in the error state', async () => {
  const dealer = await connected([COMPLETE, ['MOTOR:ERROR', 300], COMPLETE])
  void dealer.start()
  await advance(420 + DEAL_GAP_MS + 300 + 10)
  expect(read(dealer).state).toBe('error')
  expect(read(dealer).cards).toBe(1)
  await advance(10_000)
  expect(rig.writes.filter((w) => w === 'MOTOR:START')).toHaveLength(2)
})

test('SYNTHETIC: a reply outside the known four stops the loop', async () => {
  const dealer = await connected([['MOTOR:CLEARED', 100], COMPLETE])
  void dealer.start()
  await advance(1_000)
  expect(read(dealer).state).not.toBe('dealing')
  expect(rig.writes.filter((w) => w === 'MOTOR:START')).toHaveLength(1)
})

test('SYNTHETIC: 5 s with no reply stops with the no-answer line', async () => {
  const dealer = await connected([[null, 0]])
  void dealer.start()
  await advance(4_999)
  expect(read(dealer).state).toBe('dealing')
  await advance(2)
  expect(read(dealer).state).toBe('error')
  expect(read(dealer).said).toBe('No answer. Check it is on and nothing else is using it.')
})

test('SYNTHETIC: a lost link mid-loop stops with the lost line and sends nothing more', async () => {
  const dealer = await connected(PACED_10)
  void dealer.start()
  await advance(420 + DEAL_GAP_MS + 100)
  disconnect()
  await flush()
  const sent = rig.writes.length
  expect(read(dealer).state).toBe('error')
  expect(read(dealer).said).toBe('Lost the dispenser. Check it is on, then connect again.')
  await advance(10_000)
  expect(rig.writes).toHaveLength(sent)
})

test('SYNTHETIC: Stop while a START is pending sends STOP next, after the write, and no START after it', async () => {
  const dealer = await connected(PACED_10, 50)
  void dealer.start()
  await advance(10)
  void dealer.stop()
  await advance(1_000)
  expect(rig.writes).toEqual(['MOTOR:START', 'MOTOR:STOP'])
  expect(rig.maxInFlight).toBe(1)
  // the card already moving still lands
  expect(read(dealer).cards).toBe(1)
  expect(read(dealer).state).toBe('stopped')
})

test('Stop during the gap sends STOP and ends dealing', async () => {
  const dealer = await connected(PACED_10)
  void dealer.start()
  await advance(420 + 50)
  await dealer.stop()
  await advance(5_000)
  expect(rig.writes).toEqual(['MOTOR:START', 'MOTOR:STOP'])
  expect(read(dealer).state).toBe('stopped')
})

test('the only payloads ever written are on the allow list', async () => {
  const dealer = await connected(EMPTY_HOPPER)
  void dealer.start()
  await advance(5_000)
  await dealer.stop()
  await advance(1_000)
  for (const w of rig.writes) expect(ALLOWED).toContain(w)
})

test('SYNTHETIC: Stop with a START in flight, then Start within 0.45 s, waits for the old COMPLETE or a 1 s settle', async () => {
  // the old START's COMPLETE would land at 420 ms
  const dealer = await connected(PACED_10)
  void dealer.start()
  await advance(100)
  void dealer.stop()
  await advance(50)
  void dealer.start()
  await advance(100)
  // 250 ms in: the old card is still moving, so no second START may have gone out
  expect(rig.writes.filter((w) => w === 'MOTOR:START')).toHaveLength(1)
  await advance(150)
  // 400 ms: still before the old COMPLETE at 420 ms
  expect(rig.writes.filter((w) => w === 'MOTOR:START')).toHaveLength(1)
  await advance(19)
  expect(rig.writes.filter((w) => w === 'MOTOR:START')).toHaveLength(1)
  // the old COMPLETE lands at 420 ms and releases the deferred START, once, after the STOP
  await advance(10)
  expect(rig.writes.filter((w) => w === 'MOTOR:START')).toHaveLength(2)
  expect(rig.writes.indexOf('MOTOR:STOP')).toBeLessThan(rig.writes.lastIndexOf('MOTOR:START'))
  expect(rig.maxInFlight).toBe(1)
  await dealer.stop()
})

test('SYNTHETIC: Stop with a START in flight and no COMPLETE ever, a Start waits out a ~1 s settle after STOP', async () => {
  const dealer = await connected([[null, 0], COMPLETE])
  void dealer.start()
  await advance(100)
  void dealer.stop()
  await advance(50)
  void dealer.start()
  // STOP at 100 ms: the settle ends at 1100 ms
  await advance(940)
  expect(rig.writes.filter((w) => w === 'MOTOR:START')).toHaveLength(1)
  await advance(20)
  expect(rig.writes.filter((w) => w === 'MOTOR:START')).toHaveLength(2)
  await dealer.stop()
})

test('SYNTHETIC: Stop, Start (pending), Stop again before the old COMPLETE: no START ever goes out', async () => {
  const dealer = await connected(PACED_10)
  void dealer.start()
  await advance(100)
  void dealer.stop()
  await advance(50)
  void dealer.start() // pending behind the old card
  await advance(50)
  void dealer.stop() // a safety stop before the old COMPLETE at 420 ms
  await advance(10_000)
  expect(rig.writes.filter((w) => w === 'MOTOR:START')).toHaveLength(1)
  expect(read(dealer).state).toBe('stopped')
})
