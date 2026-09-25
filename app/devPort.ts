import { createHash } from 'node:crypto'
import { readFileSync, realpathSync, statSync } from 'node:fs'
import { homedir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

// ONE DEV PORT PER CHECKOUT, DERIVED FROM WHERE THE CHECKOUT IS.
//
// `vite.config.ts` and `playwright.config.ts` both import this so they cannot disagree
// about which port this tree serves on — and them disagreeing is not hypothetical, it is
// the defect this file exists to close.
//
// THE BUG, measured 2026-08-29. Both configs hardcoded 5173 and Playwright ran with
// `reuseExistingServer: true`, so `make design-check` in a git worktree ATTACHED TO THE
// MAIN TREE'S dev server and asserted docs/DESIGN.md's floors against code the worktree
// had never seen. It passed. A green design-check meant nothing about the branch being
// worked on, and nothing said so — the worst shape a check can fail in, because the only
// signal it gives is the one you were hoping for.
//
// WHAT WAS NOT THE BUG, and this is the part worth being exact about: `reuseExistingServer`
// is not the culprit and turning it off is not the fix. It exists for two real reasons
// stated in `playwright.config.ts`'s own comment — a cold repo gets a server without anyone
// remembering to background `make dev`, and a dev server you already have running is
// attached to rather than fought with over a `strictPort` port. Turning it off would keep
// both trees on 5173 and merely convert a silent wrong answer into a hard failure, while
// ALSO breaking the case where you have `make dev` up in the tree you are testing.
//
// The shared PORT is the whole fault. Give each checkout its own and reuse becomes safe by
// construction: the only server that can ever be on this tree's port is this tree's.
//
// THE MAIN WORKING TREE KEEPS 5173. It is in CLAUDE.md, in the Makefile's help, in
// docs/specs, and in the muscle memory of anyone who has run this. Nothing about the
// ordinary single-checkout workflow changes; only a linked worktree moves.
//
// THE MAIN TREE'S `.git` IS A DIRECTORY, and that is the one fact that keeps 5173. A linked
// worktree's `.git` is a FILE. A copy with no `.git` has neither. Both of those move.
//
// DERIVED, NOT ALLOCATED, so it is stable. The same worktree answers the same port on every
// run, which is what makes the printed URL worth bookmarking and what keeps two concurrent
// sessions in two trees off each other. An allocator handing out the next free port would
// give one tree a different answer every run, and `strictPort` would then be unable to tell
// "someone else is here" from "I moved".
//
// COLLISIONS WERE NOT A COUPLE OF PERCENT, AND ONE WAS SILENT
// (D261). With about 35 worktrees on this Mac
// and 300 slots, a shared slot is more likely than not. On 2026-09-24 two live worktrees
// derived 5218, and a design-check in one ATTACHED to the other's Vite and passed. So two
// things changed. A checkout may CLAIM a slot in one machine-wide registry, and `slotFor`
// reads it before the hash (`scripts/port-slots.py claim` is the one writer; `make dev`,
// `make server`, `make up` and `make design-check` claim first). And a server this suite
// reuses must say which checkout it serves: `checkoutIdentity.ts` refuses the run otherwise.
// `vite.config.ts` still keeps `strictPort`, so a second server on one port refuses to start.
//
// THE CAPTURE SERVER'S PORT IS DERIVED HERE TOO, FROM THE SAME SLOT (D43). This file solved
// the shared-port fault for Vite and Playwright and stopped there; `server/capture_server.py`
// stayed on a bare 8000 and `app/src/server.ts` asked for `http://localhost:8000` whatever
// tree it was served from. The store is ALREADY per-checkout — `store/files.py:home()`
// defaults to the checkout the code runs from — so a shared port means tree A's UI is
// answered by tree B's server over tree B's inventory. One direction drives the owner's real
// 767 cards from a branch; the other writes real capture photographs into a directory that is
// deleted with the worktree. `server/ports.py` carries the argument; it is the Python twin of
// this file and `scripts/port-agreement.py` is what keeps the two honest.
//
// ONE SLOT, TWO PORTS, so a tree reads as a pair — 5276 beside 8176 — and there is one number
// to recognise rather than two unrelated ones.
const BASE_PORT = 5173
const CAPTURE_BASE_PORT = 8000
const WORKTREE_LOW = 5200
const CAPTURE_LOW = 8100
const WORKTREE_SLOTS = 300

function repoRoot(): string {
  return resolve(dirname(fileURLToPath(import.meta.url)), '..')
}

// `realpathSync` rather than the bare `resolve()` this used before, so a path reached through
// a symlink hashes identically to the path itself — `/tmp` is a symlink to `/private/tmp` on
// this machine and one worktree genuinely lives under it. Python's `Path.resolve()` is the
// same operation, which is what lets the two implementations agree at all. Measured before it
// was changed: every worktree in this clone answers the same slot either way, so no existing
// dev port moved.
function canonical(root: string): string {
  try {
    return realpathSync(root)
  } catch {
    return root
  }
}

// ONLY A `.git` DIRECTORY KEEPS 5173 AND 8000 (D268, a copied tree never
// gets the live port). This used to ask "is `.git` a FILE?" and read every other answer as
// "the main tree". On 2026-09-23 a scratch copy of main with no `.git` built an app. It
// baked 8000, the owner's LIVE capture server, and the page read the real store. So the
// base ports now go to the one tree that proves it is the primary checkout. A linked
// worktree, a tarball, a container copy and a copy without its `.git` all take a slot from
// their own path. A wrong guess here costs a moved port, never a write to the owner's store.
// A plain `cp -r` copies `.git` too, as does a second clone: that tree still gets 5173 and
// 8000, an accepted risk recorded in the decision entry.
// `server/ports.py:is_primary_checkout` is the twin, and `make port-agreement` asks both
// of them over a copy of each kind of tree.
function isPrimaryCheckout(root: string): boolean {
  try {
    return statSync(resolve(root, '.git')).isDirectory()
  } catch {
    // No `.git` at all, or a stat that fails: not the primary checkout.
    return false
  }
}

// THE CLAIMED SLOTS, `server/ports.py:read_claims`'s twin. `PKMNSCAN_SLOT_REGISTRY`
// overrides where the file is. A missing, unreadable or malformed file reads as "nothing
// claimed", and so does an entry that is not a whole slot inside the band. This file only
// ever READS the registry.
export const SLOT_REGISTRY_ENV = 'PKMNSCAN_SLOT_REGISTRY'

function slotRegistry(): string | null {
  const override = (process.env[SLOT_REGISTRY_ENV] ?? '').trim()
  if (override) return override
  try {
    return join(homedir(), '.pkmnscan', 'port-slots.json')
  } catch {
    return null
  }
}

// A SLOT WRITTEN `149.0` OR `1.49e2` IS NOT A WHOLE SLOT. JSON.parse reads both as the
// integer 149, and Python's json reads them as floats, which `read_claims` refuses. Only the
// written text can tell them apart, so every number literal with a fraction or an exponent
// becomes `null` before the parse. The pattern matches a whole string first, so a digit
// inside a path is never read as a number. `scripts/port-agreement.py` asks both sides.
function wholeNumbersOnly(text: string): string {
  return text.replace(/"(?:[^"\\]|\\.)*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g, (token) =>
    token.startsWith('"') || !/[.eE]/.test(token) ? token : 'null',
  )
}

function claimedSlot(root: string): number | null {
  const path = slotRegistry()
  if (!path) return null
  try {
    const data: unknown = JSON.parse(wholeNumbersOnly(readFileSync(path, 'utf-8')))
    const slots = (data as { slots?: unknown } | null)?.slots
    if (!slots || typeof slots !== 'object') return null
    const value = (slots as Record<string, unknown>)[canonical(root)]
    return Number.isInteger(value) && (value as number) >= 0 && (value as number) < WORKTREE_SLOTS
      ? (value as number)
      : null
  } catch {
    return null
  }
}

// The slot the path alone derives, used when no slot is claimed.
export function hashedSlot(root: string): number {
  const digest = createHash('sha256').update(canonical(root)).digest()
  return digest.readUInt32BE(0) % WORKTREE_SLOTS
}

// Exported so `scripts/port-agreement.py` can feed it the same paths it feeds
// `server/ports.py:slot_for`, over the same registry, and diff the answers.
export function slotFor(root: string): number {
  return claimedSlot(root) ?? hashedSlot(root)
}

// The resolved path of THIS checkout. `checkoutIdentity.ts` serves it and compares it.
export function checkoutRoot(): string {
  return canonical(repoRoot())
}

function portFor(base: number, low: number): number {
  const root = repoRoot()
  if (isPrimaryCheckout(root)) return base
  return low + slotFor(root)
}

export function devPort(): number {
  return portFor(BASE_PORT, WORKTREE_LOW)
}

export function capturePort(): number {
  return portFor(CAPTURE_BASE_PORT, CAPTURE_LOW)
}

export const DEV_PORT = devPort()
export const DEV_URL = `http://localhost:${DEV_PORT}`
export const CAPTURE_PORT = capturePort()
export const CAPTURE_URL = `http://localhost:${CAPTURE_PORT}`
