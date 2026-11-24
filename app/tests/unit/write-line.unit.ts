// Protects: D329 (a press that must wait says so at once, and one write line serves every screen): writes run in the order pressed and one at a time, a waiting press reads as queued, cancel drops a waiting write before it is sent, a write that throws does not strand the ones behind it, and the count is the writes not yet answered.
// Governs: D329; docs/specs/undo.md section 10

import { existsSync } from 'node:fs'

import { expect, test } from './unit'

/* THE LINE'S API, AS THIS FILE PINS IT. The shared line moves out of OrdersWalkPane.tsx into `app/src/writeLine.ts`, and it exports:
 *   queueWrite(run)  enqueues one write and returns its job; `done` settles when the write has answered, and also when it was cancelled.
 *   isQueued(job)    true while the job waits its turn; false once it is out, answered, or cancelled.
 *   cancel(job)      drops a job still waiting, before it is sent, and returns true; returns false for a job already out.
 *   writesInLine()   the writes not yet answered: those waiting and the one out.
 *   sayQueued(what)  the words a waiting press reads: "Waits for the <what> to save."
 * Nothing imports the module statically. A static import of a file that is not there fails the whole file as a crash, and a crash
 * is not a red. `line()` asserts the file first and imports it only after that. The module is a new file, so on the old commit its
 * absence is the one cause these cases can name. The import is a variable, so the type comes from the local `WriteLine` alone. */

type LineJob = { readonly done: Promise<void> }
type WriteLine = {
  queueWrite: (run: () => Promise<void>) => LineJob
  isQueued: (job: LineJob) => boolean
  cancel: (job: LineJob) => boolean
  writesInLine: () => number
  sayQueued: (what: string) => string
}

const LINE_FILE = new URL('../../src/writeLine.ts', import.meta.url)

async function line(): Promise<WriteLine> {
  expect(
    existsSync(LINE_FILE),
    'the page write line is not in app/src/writeLine.ts yet, so no write can be queued through it (D329: one line for every screen)',
  ).toBe(true)
  return (await import(LINE_FILE.href)) as WriteLine
}

/** A gate a case holds open: a write waits on it, the case lets it through by calling `release`. */
function gate(): { promise: Promise<void>; release: () => void } {
  let release: () => void = () => {}
  const promise = new Promise<void>((resolve) => {
    release = resolve
  })
  return { promise, release }
}

test('writes run in the order they were pressed', async () => {
  const { queueWrite } = await line()
  const ran: string[] = []
  const first = queueWrite(async () => {
    ran.push('first')
  })
  const second = queueWrite(async () => {
    ran.push('second')
  })
  const third = queueWrite(async () => {
    ran.push('third')
  })
  await Promise.all([first.done, second.done, third.done])
  expect(ran, 'the line sends its writes in the order they were pressed').toEqual(['first', 'second', 'third'])
})

test('one write is out at a time: the next is sent only after the one before it has answered', async () => {
  const { queueWrite } = await line()
  const hold = gate()
  let inFlight = 0
  let most = 0
  const out = async (wait?: Promise<void>) => {
    inFlight += 1
    most = Math.max(most, inFlight)
    if (wait !== undefined) await wait
    inFlight -= 1
  }
  const first = queueWrite(() => out(hold.promise))
  const second = queueWrite(() => out())
  await expect.poll(() => inFlight, 'the first write is out while the second waits').toBe(1)
  hold.release()
  await Promise.all([first.done, second.done])
  expect(most, 'no two writes are out together, because the server never hears two of the page writes at once').toBe(1)
})

test('a press that waits reads as queued until its turn comes, and the write out is not queued', async () => {
  const { queueWrite, isQueued } = await line()
  const hold = gate()
  let queuedWhenItRan: boolean | null = null
  const first = queueWrite(() => hold.promise)
  const second: LineJob = queueWrite(async () => {
    queuedWhenItRan = isQueued(second)
  })
  expect(isQueued(second), 'a press that must wait is queued at once').toBe(true)
  expect(isQueued(first), 'the write out is not queued: it has its turn').toBe(false)
  hold.release()
  await second.done
  expect(queuedWhenItRan, 'once its turn comes the write is no longer queued').toBe(false)
  await first.done
})

test('cancel drops a waiting write before it is sent, and the write behind it still runs', async () => {
  const { queueWrite, cancel, isQueued } = await line()
  const hold = gate()
  const ran: string[] = []
  const first = queueWrite(async () => {
    await hold.promise
    ran.push('first')
  })
  const dropped = queueWrite(async () => {
    ran.push('dropped')
  })
  const last = queueWrite(async () => {
    ran.push('last')
  })
  expect(cancel(dropped), 'a write still waiting its turn can be cancelled').toBe(true)
  expect(isQueued(dropped), 'a cancelled write is no longer queued').toBe(false)
  expect(cancel(first), 'a write already out cannot be cancelled').toBe(false)
  hold.release()
  await Promise.all([first.done, last.done, dropped.done])
  expect(ran, 'the cancelled write never reached the server, and the write behind it still ran').toEqual(['first', 'last'])
})

test('a write that throws does not strand the writes behind it', async () => {
  const { queueWrite, writesInLine } = await line()
  const before = writesInLine()
  const ran: string[] = []
  const broken = queueWrite(async () => {
    throw new Error('the server did not answer')
  })
  const after = queueWrite(async () => {
    ran.push('after')
  })
  await broken.done.catch(() => undefined)
  await after.done
  expect(ran, 'the write behind a throw still runs').toEqual(['after'])
  await expect.poll(() => writesInLine(), 'the count is back where it started once the line drains').toBe(before)
})

test('the count is the writes not yet answered, waiting or out', async () => {
  const { queueWrite, writesInLine } = await line()
  const before = writesInLine()
  const hold = gate()
  const first = queueWrite(() => hold.promise)
  const second = queueWrite(async () => undefined)
  expect(writesInLine(), 'two writes are unanswered: one out and one waiting').toBe(before + 2)
  hold.release()
  await first.done
  await expect.poll(() => writesInLine(), 'the answered write leaves the count').toBe(before + 1)
  await second.done
  await expect.poll(() => writesInLine(), 'the last answer leaves the count').toBe(before)
})

test('sayQueued names what the press waits for, in the words every screen shares', async () => {
  const { sayQueued } = await line()
  expect(sayQueued('sale')).toBe('Waits for the sale to save.')
  expect(sayQueued('retirement')).toBe('Waits for the retirement to save.')
  expect(sayQueued('move')).toBe('Waits for the move to save.')
  expect(sayQueued('answer')).toBe('Waits for the answer to save.')
})
