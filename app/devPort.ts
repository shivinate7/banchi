import { createHash } from 'node:crypto'
import { realpathSync, statSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
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
// A LINKED WORKTREE'S `.git` IS A FILE, not a directory — the same one fact
// `scripts/worktree-guard.sh` and `scripts/docs-audit.py` both detect on, kept identical
// here on purpose so there is one rule to learn rather than three spellings of it.
//
// DERIVED, NOT ALLOCATED, so it is stable. The same worktree answers the same port on every
// run, which is what makes the printed URL worth bookmarking and what keeps two concurrent
// sessions in two trees off each other. An allocator handing out the next free port would
// give one tree a different answer every run, and `strictPort` would then be unable to tell
// "someone else is here" from "I moved".
//
// COLLISIONS ARE POSSIBLE AND ARE LOUD. Two worktree paths can hash into one slot; with 300
// slots and a handful of trees it is a couple of percent. `vite.config.ts` keeps
// `strictPort`, so the second one refuses to start rather than quietly serving elsewhere —
// which is the same reason that flag is set at all. The remedy is to rename the worktree
// directory; the port follows the path.
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

function isLinkedWorktree(root: string): boolean {
  try {
    return statSync(resolve(root, '.git')).isFile()
  } catch {
    // No `.git` at all — a tarball, a container copy, a CI checkout that stripped it.
    // Behave like the main tree: 5173 is what every doc says, and inventing a port for a
    // checkout that has no identity to derive one from would be worse than the default.
    return false
  }
}

// Exported so `scripts/port-agreement.py` can feed it the same synthetic paths it feeds
// `server/ports.py:slot_for` and diff the answers. A pure function of a string is the only
// part of this that can be compared across two languages without a filesystem in the way.
export function slotFor(root: string): number {
  const digest = createHash('sha256').update(canonical(root)).digest()
  return digest.readUInt32BE(0) % WORKTREE_SLOTS
}

function portFor(base: number, low: number): number {
  const root = repoRoot()
  if (!isLinkedWorktree(root)) return base
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
