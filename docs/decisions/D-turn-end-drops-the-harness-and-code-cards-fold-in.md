## D-turn-end-drops-the-harness-and-code-cards-fold-in — The harness leaves turn end, and code cards fold into one rules file

**TWO RULINGS, ONE SESSION, 2026-09-20.** Both change how a session runs, not what the
product does. Both are recorded here together. Both are the owner reshaping process
overhead this same session measured, not two unrelated architecture calls.

### Ruling 1 — the harness leaves turn end

**THE OWNER'S WORDS, VERBATIM, asked where the ten-test harness should run:**

```
Drop it from turn end entirely.
```

The owner gave this after a measured cost of 23-24s on every single turn. The harness now
runs on the commit path (`make check`) and in CI only. This half is the owner's ruling, not
this session's judgment call.

**WHAT WAS LEFT OPEN: what the Stop hook does instead.** Two shapes were offered. Run
nothing, or run some far cheaper check. This session chose nothing. The argument follows.

**A CHEAP CHECK PICKED AT RANDOM COSTS MORE THAN IT BUYS.** No single fast probe stands in
for ten tests covering `store`, `pipeline`, `identify`, `server`, `codes`, and their joins.
`cd app && npx tsc --noEmit` only catches TypeScript errors. Most turns never touch `app/`.
Running it anyway, on every turn, points a check at a file nobody wrote this turn. That is
what "a guard must see its subject" warns against. A turn-end check with no real
relationship to what changed teaches a reader to ignore it. That is the same failure the
"cry-wolf guard is spent" rule names for a guard that fires on nothing wrong.

**THE COMMIT PATH ALREADY CATCHES A BROKEN PIPELINE, JUST NOT EVERY TURN.** `make check`
still runs `harness` first in its list (D161). CI runs it again. A session that never
commits mid-break can carry a broken pipeline through every turn until the next commit or
CI run. That could be many turns in one long session. Nothing else inside a turn now
notices. This is the real cost of the ruling, stated plainly rather than hidden in a quiet
script. The owner accepted the harness leaving turn end with that cost in view.

**THE HOOK STAYS ON THE ROSTER, DOING NO WORK, RATHER THAN BEING DELETED.** `--status` still
answers why nothing is running, matching the file's own honesty rule from before this
change. `make status`'s "turn gate" line still reads it. `PKMNSCAN_GATE=off` stays
recognised, though it changes nothing now. A shell profile that already sets it is not
silently turned into a no-op with no trace.

**MEASURED, BEFORE AND AFTER.** `time make harness` on this tree: 24.85s. `time
scripts/stop-gate.sh` after this change: 0.006s. The Stop hook no longer spends the owner's
CPU on every turn end, on the machine their capture server and rig also run on.

### Ruling 2 — code cards fold into one rules file

**THE OWNER'S WORDS, VERBATIM, on why the codes track framing is wrong:**

```
Saying it's its own track is stupid, it's just a feature at this point and one I've not used
at all yet.
```

**ASKED WHAT TO DO ABOUT IT, THE OWNER CHOSE THEIR OWN OPTION, VERBATIM:**

```
Code stays and keeps working. I mark the feature dormant in one place, fold
code-card-fork/CLAUDE.md into the main file so there is no second rules document, and stop
the docs from reading as active work.
```

This whole ruling is the owner's, not argued here. What follows is how this session
executed it.

**NOTHING IS DELETED FROM THE BUILD.** `codes/`, the `#/codes` route, harness test T8, and
the QR decode all keep running, unchanged. This ruling is about documents and framing, not
code.

**THE FOLD IS A SYMLINK CHAIN, NOT A COPY.** `code-card-fork/CLAUDE.md` is now a relative
symlink to the root `CLAUDE.md`. That is the same pattern `AGENTS.md` already used for
Codex (D135). `code-card-fork/AGENTS.md` already pointed at the sibling `CLAUDE.md`. It now
resolves through that symlink to the same root file, one hop further, with no edit needed
there. No document reads a copy. Reading either file in either directory reads the one
file.

**THE AUDIT ROWS NAMED IN THE BRIEF DO NOT READ THIS FILE'S CONTENT.** `codex hooks`
compares only `.codex/hooks.json` against `.claude/settings.json`'s hooks block. `repo map`
compares only `docs/map.py`'s own `COMPONENTS`/`TRACKS` data against the tree. Neither
names `code-card-fork/CLAUDE.md`'s content directly, so the fold does not touch either
row's inputs.

**ONE PLACE MARKS DORMANCY, DATED.** The new "Code cards (dormant feature)" section in
`CLAUDE.md`, headed "DORMANT as of 2026-09-20," is that one place. It says a session must
not read the feature as active work unless the owner names it. It says not to repeat the
marker elsewhere. The root file's opening paragraph, already present before this entry,
points at that section rather than restating the dormancy claim a second time.

**D14'S STRUCTURAL HALF STAYS OUT OF SCOPE, ON THE BRIEF'S OWN INSTRUCTION.**
`docs/map.py`'s `TRACKS` tuple, `codes/` as its own package, and
`scripts/decision-context.py`'s track banner are all untouched. `TRACKS`'s `"rules"` field
still names `code-card-fork/CLAUDE.md`. That path still exists and still resolves, through
the new symlink, to the folded content. Nothing in `TRACKS` needed editing for that to stay
true.

**THE FOLDED PROSE WAS REWRITTEN, NOT PASTED, TO KEEP THE FILE'S OWN ZERO-ERROR FLOOR.**
`scripts/ste-ratchet.json` pins root `CLAUDE.md` at zero STE errors (D226). The original
`code-card-fork/CLAUDE.md` carried nine, mostly semicolons and one run-on sentence. Six
sentences were split, and every semicolon was removed, before the content moved. Every
rule and every measured number carried over unchanged.

### What moved, for a reader auditing this entry

- `CLAUDE.md` — opening paragraph rewritten. A new "Code cards (dormant feature)" section
  added. The Map section's own line about `code-card-fork/CLAUDE.md` rewritten.
- `code-card-fork/CLAUDE.md` — replaced with a relative symlink to `../CLAUDE.md`.
- `code-card-fork/AGENTS.md` — unchanged, and now resolves one hop further to the same file.
- `scripts/stop-gate.sh` — rewritten. Runs nothing at turn end. `--status` reports why.
- `docs/map.py` — the `stop-gate.sh` component entry's `does` field updated to match.
