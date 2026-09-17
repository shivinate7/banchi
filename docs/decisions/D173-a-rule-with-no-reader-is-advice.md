## D173 — A rule that can be enforced mechanically is enforced mechanically, and a rule with no reader is advice

**A rule that can be mechanically enforced must be mechanically enforced, and a new rule is not finished until its enforcement exists or its unenforceability is argued.**

The owner's instruction, 2026-09-12, and the second half is the part that makes this an entry
rather than a chore: *"i need this everything fucking mechanically fixed im tired of prose
being bypassed"* … *"every rule for all time, anything that can be mechanically enforced,
should be mechanically enforced, and make this a rule to enforce going forward too via
claude.md or otherwise."*

### The argument

**This repo's prose is bypassed, and not by sessions that had not read it.** That is the whole
case, and every item in it landed inside twenty-four hours on 2026-09-11/12:

- A session wrote `a-pgrep-waiter-matches-itself` into its own memory directory,
**read that file in the session** , and then wrote the exact waiter loop it forbids. The loop
matched its
  own command line, never fired, and swallowed the notification it existed to produce. That
  file now records the reason in its own words: it was *"phrased as an explanation to recall
  rather than a prohibition to trip over."*
- The same session wrote a rule against silencing a write and then ran two commits under
  `>/dev/null 2>&1`, swallowed both refusals, and reported "pushed" off a stale `git log`.
- DEBT11 carried a sentence about two observed mutation failures that were
  **measured false on both counts**. Nothing read it, so nothing contradicted it.
- `node scripts/screen-freshness.mjs --self-test` exited 1 on main, from 17 exports missing
  from its RECORDED table, **while sitting on no `make` target** — and the plain
  `screen-freshness` beside it passed and printed *"classification has moved since it was
  recorded — run --self-test"*. The check told the operator to run the check that was red, and
  nothing made them.

**Against all of that, the mechanised rows have a clean record.** `raw color`, `storage keys`,
`route census`, `check census`, `codex hooks`, `id claims` and `shell substitution` have not
been bypassed once. Not because the sessions reading them were more careful — several are the
same sessions — but because **none of them can be.** A commit that breaks one does not land.

So the difference in outcome does not track how well a rule is written, how emphatically, or
how recently. It tracks whether anything reads it.

### What this decides

1. **A rule added to `CLAUDE.md`'s Hard rules arrives with its enforcement, in the same PR.**
   Not as a follow-up: the first hard rule in that file already establishes that the remaining
   half of a task is not a follow-up, and this is that rule applied to rule-writing.
2. **If it cannot be mechanised, the rule says so inside itself** — `**NOT MECHANIZED:**`,
   followed by what a machine would have to be able to SEE. That sentence is the deliverable,
   not an apology. It is also where the next session looks when the mechanism becomes possible.
3. **The count of unenforced rules is pinned and reconciled in both directions**, which is the
   part a mutation arm had to teach (below).

### The mechanism

`make docs-audit`'s **`rule enforcement`** row. It parses every top-level rule under
`## Hard rules` and requires each to either name a mechanism **that resolves** — a `make`
target real in the Makefile, a docs-audit row name this file actually registers, or a path
under `scripts/`, `harness/tests/`, `app/tests/` or `.github/workflows/` that exists — or carry
the bold sentinel with at least twelve words of argument after it.

**A citation is checked against the thing it names, not against a pattern.** A rule naming a
deleted guard is worse than a rule naming nothing, because it reads as coverage.

Two numbers are pinned in the row rather than derived, and both are deliberate:

- **`HARD_RULE_FLOOR`** — the rule count. A reader that finds nothing, over a section somebody
reworded or a parser somebody broke, would otherwise print `ok`.
**That is this repo's signature defect** : a guard that cannot tell *"nothing is wrong"* from
*"nothing is known
  yet"*, of which nine instances landed in twenty-four hours, two of them docs rows that passed
  while reporting `0 entries` over an emptied corpus. Fewer rules than the floor reads as a
  broken reader.
- **`PROSE_ONLY_EXPECTED`** — this file's prose debt, and **an equality, not a ceiling.** With
  a ceiling, deleting a rule's `NOT MECHANIZED:` admission SURVIVED a mutation arm: that rule's
  prose also mentions `make harness` as *evidence*, so with the admission gone it read as
mechanised and the debt silently fell from six to five.
**A number checked in one direction only lets an honest admission be deleted for free.** Build a
mechanism and you lower the pin
  in the same commit; add an unenforced rule and you raise it and say why.

**Today: twelve hard rules, six naming a mechanism that resolves, six arguing their own unenforceability.**
Those six are named in the file itself: the route-reachability rule, never
guess an identification, no manual third-party UI step, fix the cause never the symptom, a
settled decision is an argument, and check whether a task is yours before handing it over.

### Proved by violation — ten arms, ten caught

A mechanism citation deleted · a sentinel deleted from a rule that names another mechanism
(the arm that changed the design) · a sentinel deleted from a rule that names none · an
argument truncated below the word floor · a citation naming a `make` target that does not
exist · a citation naming a path that does not exist · the heading reworded · a rule deleted ·
an extra unenforced rule added · a mechanism *built* without the pin lowered.

**One arm survives by definition and is recorded rather than explained away**: deleting the
rule-count floor from inside the row leaves it printing `ok` over a section a rule short.
`check dispatch` sees a whole row go missing and nothing sees an assertion inside one go
missing — the same shape that row's own comment already states, where a detector cannot detect
its own absence.

### What it cannot see

**Whether the named mechanism actually covers the rule.** A rule could cite `make lint` and be
about something lint never reads; this row reads the citation, not the coverage. That is the
judgement it deliberately leaves to a person, and it is why the sentinel's argument has to be
written out rather than ticked.

**And it governs one surface.** `CLAUDE.md`'s Working agreement, its Commands prose, the
~170 entries under `docs/decisions/`, `docs/DEBTS.md`, and the owner's standing instructions in
the memory directory are all rule surfaces and none is read here yet. A full audit of those
surfaces is the work this entry begins rather than completes.

### Reopening condition

**If the pin is raised twice without a mechanism landing between, this row has become a formality**
and the answer is not a bigger number — it is that the rule being added does not
belong in Hard rules at all. And if a mechanism proposed for one of the six turns out to be
cheap, the sentinel it replaces is the specification for it: each one already names what a
machine would have to see.
