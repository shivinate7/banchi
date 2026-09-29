# Token budget audit — 2026-09-27

Owner's ruling that started this lane: *"Prune memory.md now, and then send an audit
lane."* The owner also asked a follow-up question. Token savings should not stop at the
decision index alone. Other sources should hold savings too.

This report answers that question. It measures every source that loads into a Claude Code
session in this repo. It proposes a cut or an on-demand move for each one. It changes
nothing else. The owner rules on each proposal before anything moves.

**Method.** Byte counts come from `wc -c` on the file as it stands on this branch
(`ux/pr4b-token-audit`). Token counts are bytes divided by four. Each one carries the label
*approximate, not measured*, per D60's own caveat. A safe, read-only hook ran directly to
measure its output. An unsafe hook's output came from reading its source and estimating,
and that is said in the text.

## 1. CLAUDE.md, by section

`AGENTS.md`, `code-card-fork/AGENTS.md` and `code-card-fork/CLAUDE.md` are relative symlinks
to `CLAUDE.md` (D135). This count treats the four as one file. File total: 111,021 bytes,
about 27,755 tokens (approximate, not measured).

| Section | Bytes | Outcome protected | How often needed | Proposal | What protects the outcome after |
|---|---|---|---|---|---|
| Preamble + "The name is the app's" (D94) | 3,043 | A session does not rename the checkout, the CLI, or a package while renaming the app | Every session that touches naming | KEEP | - |
| Commands | 34,170 | A session finds the right `make`/`./pkmnscan` command and its flags without guessing | Every session that runs a command | CUT to name, one-line purpose, and flags. Move the "why" prose to the Makefile's own per-target comments (already there for most targets) and to `make explain` | The Makefile comment block above each target, and `make help`'s existing ~22 KB echo listing |
| Front end: screens table | 5,198 | A session knows the fourteen routes, which four sit off-nav, and does not build a fifteenth by accident | Screen work only | KEEP. The census below depends on the exact sentence | - |
| Front end: design system | 5,633 | A session does not hand-roll a color, a button, or a money format the kit already owns | Screen work only | KEEP. Dense mechanism citations, not narrative | - |
| Front end: shell | 998 | A session finds the shortcut table and the error-boundary shape before changing either | Shell work only | KEEP | - |
| Front end: verifying a screen | 391 | A session knows the three widths and two themes to check | Screen work only | KEEP | - |
| Code cards (dormant feature) | 5,853 | A session does not treat a dormant feature as active work. A session does not rebuild QR or ledger logic the spec already argues against | Rare. The owner has not run this feature since 2026-09-20 | MOVE the two `###` subsections (op detail, 4,089 bytes combined) to `docs/specs/code-cards.md`. That file already calls itself "the spec and supersedes this section's architecture." KEEP one paragraph: the dormancy marker and a pointer | `docs/specs/code-cards.md`, cited by the pointer paragraph |
| Things you will get wrong without being told (top-level) | 9,000 | A session does not restart the live capture server, mis-key a join, or reuse a stored key wrongly | Frequent. This is the most-cited "you will get this wrong" list | MOVE the incident narratives (measured thread counts, the 950-row zero-join story, the Q2 ruling quote) to the decision entries they already cite (D138/DEBT11, D35, D164). KEEP the bold rule sentence and its mechanism citation in each bullet | The cited decision entry, one click away through `make map ARGS=D<n>` |
| Hard rules | 10,038 | A rule with no mechanism is not silently unenforced (D173) | Every session. This is also the `rule enforcement` docs-audit row's own subject | KEEP whole. This is the row's input, not narrative | - |
| Working agreement | 526 | A session knows the report format before writing one | Every session that reports | KEEP | - |
| Working agreement: writing a brief | 2,909 | A session names the rendering component, never asks for an undone state, and fences by behavior | Briefing work only | MOVE the "the round this cost" incident stories to a decision entry, or a debt entry the practice already implies. KEEP the three bolded practices and their one-line reason | A named decision or debt entry |
| Map: prose + pointers | ~6,594 | A session knows where `docs/map.py`, `docs/decisions/`, `docs/GATES.md`, `docs/DEBTS.md` and the specs live, and their status | Every session doing architecture work | KEEP | - |
| Map: decision index (fenced list, D1-D301) | 26,420 | A session can look up a decision id's one-line gist before reading the entry | Frequent, but as a lookup table, not prose to read in order | OUT OF SCOPE, already ruled. Becomes `make map ARGS=--decisions` plus one pointer line, in another lane. This report only counts its bytes | `make map ARGS=--decisions`, or `make map ARGS="D<n> --full"` for one entry |

Two sections carry almost no narrative and need no proposal. **Hard rules** is the literal
input to the `rule enforcement` docs-audit row (see section 3). The **design system** and
**screens** subsections stay dense with active mechanism citations: which test, which row,
which file. Cutting them would cut the citation, not the fat.

## 2. The global file (read-only, propose only)

`~/Developer/claude-settings/CLAUDE.md`: 10,830 bytes, about 2,708 tokens (approximate, not
measured). This file sits outside the repo. It loads before every session in every repo the
owner works in, not only this one. It is not this lane's to edit. A proposal against it
would need the owner's own word, in that file's own home. Two observations, not proposals:

- It already reads as a rules-and-citations file, not a narrative one. It runs much denser
  per byte than CLAUDE.md's narrative sections. There is less low-hanging fruit here than in
  this repo's own file.
- The "Roles, if this session can spawn agents" paragraph runs long. It only matters to a
  session that orchestrates. Whether that is worth a conditional load is the owner's call, on
  their own file, not a Banchi proposal.

## 3. docs-audit rows that read CLAUDE.md, verified, not assumed

The brief named nine rows as examples that parse CLAUDE.md: `rule enforcement`,
`route census`, `storage keys`, `derived numbers`, `check census`, `codex hooks`,
`serve scope`, `guard scope`, `design tokens`. Reading `scripts/docs-audit.py` shows that
four of the nine do not read CLAUDE.md at all:

| Row | Reads CLAUDE.md? | What it actually reads |
|---|---|---|
| `rule enforcement` | Yes. Only the `## Hard rules` heading and its blocks | `CLAUDE.md` |
| `route census` | Yes. A whole-file text search for a route-count sentence | `CLAUDE.md`, `README.md`, `docs/map.py` |
| `storage keys` | Yes. The `**N keys are stored on the device**` sentence and its roster | `CLAUDE.md` |
| `check census` | Yes. The `make check # ...` line | `Makefile`, `CLAUDE.md` |
| `derived numbers` | Yes, but not tied to CLAUDE.md. Any `<!-- derived:name -->` marker in any markdown file counts | every `.md` file, source-agnostic |
| `codex hooks` | No | `.codex/hooks.json` against `.claude/settings.json`, both JSON, no prose |
| `design tokens` | No | `docs/DESIGN.md` against `app/src/tokens.css` |
| `serve scope` | No | `scripts/serve-scope.py` against `scripts/serve-selftest.py` and `Makefile` |
| `guard scope` | No | `scripts/guard-scope.py` against `Makefile` |

This matters for every proposal below. A move that stays inside CLAUDE.md's own text, or
moves to another markdown file, does not blind `codex hooks`, `design tokens`, `serve
scope`, or `guard scope`. They never watched CLAUDE.md to begin with.

**What each proposal above requires of the four rows that do read CLAUDE.md:**

- **Commands cut.** `check census` needs the exact `make check # harness + docs-audit + ...`
  line. It must still resolve as a list of `+`-joined check names, somewhere in `CLAUDE.md`
  and in `Makefile`. The short version must keep that one line word for word. `rule
  enforcement`, `route census`, and `storage keys` do not read the Commands section at all.
  Unaffected.
- **Code cards move.** None of the four rows reads this section. `rule enforcement` reads
  only `## Hard rules`. The code-cards section carries its own separate `### Hard rules`
  sub-heading. `HARD_RULES_HEADING = "## Hard rules"` matches `##` only, never `###`. The
  code-cards sub-heading was never in that row's scope either way. Unaffected.
- **Incident-narrative move (get-wrong sections).** `storage keys` reads the
  `**Eleven keys are stored on the device**` paragraph, inside the top-level "Things you will
  get wrong" section. That paragraph must stay carved out and byte-for-byte. Its key roster is
  what the row reconciles against `app/src`. Every other bullet in that section stays free to
  move. `rule enforcement`, `route census`, and `check census` do not read this section.
  Unaffected.
- **`derived numbers`.** No proposal here touches it. The design-system subsection (which
  carries the three `<!-- derived:... -->` markers) is not proposed for a move. For any
  future move: the marker must travel with its own sentence, into whichever markdown file it
  lands in. The row reads every markdown file, not CLAUDE.md alone.

No proposal here removes a citation the `paths` row resolves against. Moved prose keeps its
backticked paths, just in a different file.

## 4. MEMORY.md (read-only, pruned today)

The session memory file, under the home directory's `.claude` folder at
`projects/-Users-shivinate-Developer-pkmnscan/memory/MEMORY.md`: 14,760 bytes, 71
entries, about 3,690 tokens (approximate, not measured). The owner's ruling pruned it today.
Two lines read as closed incident reports, not durable lessons. That is the shape of a stale
entry. This report flags them and deletes neither, because the checks they describe have not
run again this session. A wrong deletion here loses a real lesson.

- Line 34, "reap-selftest red on main," describes `make check` failing on `origin/main`
  itself at write time. If current main already fixed that, the entry is stale. This is
  unverified. Confirming it means running the full `make check` suite, which an audit-only
  lane should not spend.
- Line 57, "Archive sweep preview is silent," ends "owner wants it investigated." That reads
  as an open item logged as a memory line, not a lesson. If someone already investigated it,
  the finding belongs in a debt or decision entry, and this line can go. This is unverified.

Every other line in the file reads as a durable lesson: a trap, a tool quirk, or a standing
practice. This report proposes no further cut beyond these two candidates.

## 5. Hooks, per-session and per-turn cost

`.claude/settings.json` lists these hooks. Each row shows a typical run's output:

| Event | Hook | Typical output | Notes |
|---|---|---|---|
| SessionStart | `scripts/worktree-guard.sh` | ~0 bytes once a worktree is provisioned | Prints only on the primary checkout off `main`, or while building a fresh `.venv`. Once per session |
| PreToolUse (Write/Edit) | `scripts/guard-opsec.sh` | 0 bytes on an ordinary edit | Fires only on a code-card photo or code string |
| PreToolUse (Write/Edit) | `scripts/decision-context.py` | 0 to 38,130+ bytes, per edit | See below. This is the single largest source this audit found |
| PreToolUse (Bash) | `scripts/reap.py --hook` | 0 bytes | Measured silent on an ordinary command |
| PreToolUse (Bash) | `scripts/silent-write-guard.py --hook` | 0 bytes | Measured silent on an ordinary command |
| PreToolUse (Bash, Write/Edit) | `scripts/guard-shell.py --hook` | 0 bytes | Measured silent on an ordinary command |
| PostToolUse (Write/Edit) | `scripts/typecheck-hook.py` | 0 bytes | Silent on non-`.ts`/`.tsx` files and on a clean compile. Prints `tsc` errors only on a real break |
| Stop | `scripts/stop-gate.sh` | 0 bytes | Disarmed since D248. The harness left turn end. Reading the script confirms it always exits 0 |
| SessionEnd / WorktreeRemove | `scripts/session-teardown.sh` | ~1 line | Once per session end, after the session has stopped reading context |

This repo's `.claude/settings.json` carries no `UserPromptSubmit` hook.

**`scripts/decision-context.py` is the finding.** It renders every decision that governs the
edited file. That means the full heading plus every bullet ruling. It fires on every single
Write/Edit, not once per session. This tree measured:

| File | Governing decisions | Output bytes |
|---|---|---|
| `pipeline/pricing.py` | 6 | 3,188 |
| `store/db.py` | 19 | 7,125 |
| `pipeline/join.py` | 45 | 15,371 |
| `app/src/App.tsx` | 37 | 15,407 |
| `app/src/Pricing.tsx` | 58 | 21,675 |
| `server/capture_server.py` | 108 | 38,130 |

`server/capture_server.py` alone outweighs CLAUDE.md's entire Commands section, 34,170
bytes. It re-injects on every edit to that file in a session, not once. A screen-work
session that edits `app/src/Pricing.tsx` three times in one sitting pays roughly 65,000
bytes of near-identical decision text for that file alone.

**Proposal:** shrink the injected context to one line per governing decision, id plus title,
the same shape as CLAUDE.md's own decision index. Drop the bulleted rulings body. Full text
stays one command away, exactly as CLAUDE.md's own map section already tells a session to
use: `make map ARGS=<path>`. On the worst case measured:

- `server/capture_server.py`: 38,130 bytes today. A headings-only version costs about
  11,765 bytes (the file's own `docs/map.py` description line, 2,984 bytes, plus 108
  id-and-title lines, 8,781 bytes). That is about 26,365 bytes saved, per edit.

This is a code change to `scripts/decision-context.py`, not a CLAUDE.md edit. Building it
sits outside this lane's own scope. This report names it because the brief asked for this
source to be measured, and because it outweighs every CLAUDE.md section on a per-edit basis.
A second, smaller observation follows in section 6, question Q4: 108 governing decisions on
one file is itself a question worth asking.

## 6. Skills (`.claude/skills/`)

Only two skills live in this repo: `tcgplayer-csv` and `text-density`. Their `description`
lines load every session, whether or not the session uses them. Their bodies load only on
demand.

| Skill | Description line (loads every session) | Body (on demand) |
|---|---|---|
| `tcgplayer-csv` | ~240 bytes | 3,541 bytes |
| `text-density` | ~230 bytes | 3,580 bytes |

Combined always-loaded cost: about 470 bytes, about 118 tokens (approximate, not measured).
This is negligible. No proposal follows. This is already the on-demand shape every other
source here is asked to move toward.

## Ranked by bytes saved

This list orders proposals by the size of the cut, largest first. The
`scripts/decision-context.py` row is per edit, not per session. It does not add directly
onto the others. Its worst measured instance already outranks every CLAUDE.md proposal below
it.

| Rank | Proposal | Bytes saved | Frequency |
|---|---|---|---|
| 1 | `scripts/decision-context.py`: headings-only injection | ~26,365 (worst case, `server/capture_server.py`) | Per edit to a governed file, repeatable within one session |
| 2 | Commands section: name, one line, and flags only | ~28,000-30,000 (estimate) | Once per session |
| 3 | Code cards section: move op detail to `docs/specs/code-cards.md` | ~5,000 | Once per session |
| 4 | Incident narration: move to cited decision or debt entries (get-wrong sections and writing-a-brief) | ~5,000-6,000 (estimate) | Once per session |
| 5 | MEMORY.md: two candidate stale lines | 350 to 400 | Once per session, pending owner confirmation |
| - | Decision index, 26,420 bytes | out of scope, already ruled | assigned to another lane |
| - | Global CLAUDE.md, hooks besides decision-context.py, skills | no action proposed | measured only |

Suppose ranks 2 through 4 all land. CLAUDE.md drops from 111,021 bytes to roughly
73,000-75,000 bytes, before the decision-index lane runs. It drops to roughly 47,000-49,000
bytes after both lanes land. That is about a 57% cut from where the file stands today.

## Questions for the owner

**Q1. Commands section, how far to cut?**
Three options. (a) Leave it: 34,170 bytes, the largest CLAUDE.md section. (b) Cut to name,
one short purpose, and flags. Point to the Makefile's own per-target comments and to
`make explain` for the "why." A spot check on `hooks`, `up`, and `guard-scope` found
comparable rationale already in the Makefile. Full parity across all fifty targets is not
yet checked line by line. (c) Delete the block outright and point at `make help`, which is
itself a third, independently hand-maintained copy of the same list, about 22 KB, see below.
**Recommendation: (b)**, with a follow-up pass to confirm parity. It is the largest single
cut available inside this repo's own control.

**Q1a. A side finding, not a proposal on its own.** Three hand-maintained copies of the
command list exist today: the Makefile's own per-target comments, the Makefile's `help:`
target (~22,372 bytes of `@echo` lines), and CLAUDE.md's Commands section (34,170 bytes).
They have already drifted in wording. The `make hooks` one-line description differs between
`help:` and CLAUDE.md. A `make docs-audit` row could reconcile `help:` against CLAUDE.md's
short list, the way `check census` already reconciles the `check:` recipe. That is a build
task, not this lane's.

**Q2. Code cards section, move to the spec now, or wait for the owner to pick the feature
back up?**
The section already states that the spec "supersedes this section's architecture."
**Recommendation: move now.** A dormant feature's operating detail costs every session the
same as if the feature were active. The pointer already exists to redirect a session that
needs it.

**Q3. Incident narration, worth the effort?**
This carries the lowest-confidence estimate here, about 5,000 to 6,000 bytes, and the most
labor. It needs many small edits across two sections. Each moved story needs a real decision
or debt entry to receive it. Some may not have one yet. D60's rule says cite rather than
restate, so a new entry may be needed instead of stretching an existing one to fit.
**Recommendation:** do this after Q1 and Q2, not before. The ratio of effort to bytes saved
runs worse here than anywhere else ranked above it.

**Q4. `scripts/decision-context.py`, build the headings-only cut?**
This is a code change, not a document edit. It belongs to a build lane once the owner rules
on it, not to this audit. **Recommendation: yes.** It is the single biggest number in this
whole report, and the fix already has a precedent in this repo: D60's own "index up front,
body on demand" shape. A second question sits inside this one. Does 108 governing decisions
on `server/capture_server.py` signal that `docs/map.py`'s `governed_by` list for that file
has grown past what is useful, apart from how it renders? This report does not measure that.
It flags the question for whoever picks up the build.

**Q5. Global `~/Developer/claude-settings/CLAUDE.md`, anything to flag?**
This report measures it only, per the brief. It is not this repo's to edit. No proposal
follows. See section 2 for the two observations recorded there.

## The owner's rulings (2026-09-27)

- Q4, the edit hook: `Id + title only (Recommended)`. `scripts/decision-context.py` prints one
  line per governing decision. The full text stays behind `make map ARGS=<path>`.
- Q1, the Commands section: `One source, two views (Recommended)`. The Makefile comment on each
  target is the only source. `make help` prints from it. CLAUDE.md keeps the name and one line
  per target, and a docs-audit row checks that list against the Makefile both ways.
- Q2, code cards: `Move now (Recommended)`. CLAUDE.md keeps the dormancy marker, the opsec hard
  rules and one pointer to `docs/specs/code-cards.md`.
- Q3, incident stories: `they can be straight deleted tbh`. Each rule stays. Its story is
  deleted, not moved.
- One lane does Q1, Q2 and Q3 together with the decision-index ruling in the test audit's
  TIERS.md, because all four edit CLAUDE.md.
