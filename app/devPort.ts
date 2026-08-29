import { createHash } from 'node:crypto'
import { statSync } from 'node:fs'
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
const BASE_PORT = 5173
const WORKTREE_LOW = 5200
const WORKTREE_SLOTS = 300

function repoRoot(): string {
  return resolve(dirname(fileURLToPath(import.meta.url)), '..')
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

export function devPort(): number {
  const root = repoRoot()
  if (!isLinkedWorktree(root)) return BASE_PORT
  const digest = createHash('sha256').update(root).digest()
  return WORKTREE_LOW + (digest.readUInt32BE(0) % WORKTREE_SLOTS)
}

export const DEV_PORT = devPort()
export const DEV_URL = `http://localhost:${DEV_PORT}`
