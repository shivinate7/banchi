## D140 — The number is claimed at the merge, because what main has taken is not knowable before it

**Ruled by the owner 2026-09-11, the same day D72's repair half was built.** That work made the provable half of a renumber block the commit. This entry is the owner's answer to why a renumber happens at all: *"rework the decision system so that branches claim decision numbers only at merge time"*. A branch no longer takes a number. It writes a SLUG, and `scripts/claim-ids.py` substitutes the number at the moment the merge knows what main has taken.

**The allocation's only input is what main holds, and a branch cannot have that.** Every renumber in this repo's history is that one sentence: a branch reads `origin/main`, takes the next free id, and is wrong the moment another branch merges first. Thirteen renumber events are recorded in D72, and the collisions are structural rather than careless — D16 carries three entries numbered `## D50` at once, written by three sessions that each took the next free number against the same base and all merged. **A guess made at the wrong time cannot be made more carefully.**

### The vocabulary is a slug, and two segments is what keeps it out of prose

**`## D140`, cited as `(D140)`, in prose and in code comments and in `governed_by` alike.** `C-<slug>` for the code-card track, and `step <slug>` for the build order, which has no letter in front of it. The letter says which namespace; the slug says which entry, which is more than a number ever said while the branch was open.

**Two segments minimum.** `D-pad` is one and is ordinary prose; `D140` is three and is an id. Measured over every `.md`, `.py`, `.ts`, `.tsx` and `.css` in the tree the day the vocabulary was chosen: **zero tokens of either shape existed**, so nothing had to be renamed to make room and no existing sentence changed meaning.

**Lowercase, because the letter carries the namespace.** A mixed-case slug would make `D-Merge-Time-Ids` and `D140` two ids for one entry with nothing to say so — the duplicate-heading problem D16 blocks, reintroduced through spelling.

**A step's slug lives in its list marker's place, which markdown cannot hold.** There is no ordered-list marker that can read a slug, so an unclaimed step is written with a `0.` marker carrying its slug in backticks ahead of the title, and the claim rewrites the marker and the token together. `0.` is never an id, so the mirror row reads it as the slug and never as zero.

### It is claimed inside `make merge`, before the merge, and the wait is the point

**The owner's ruling, chosen against two faster options.** `make merge` allocates, commits the substitution to the PR branch, pushes it, waits for that commit's checks to go green, and only then merges. Nothing that main has never run CI over reaches main.

**The two it was chosen over are recorded because they will be proposed again.** Claiming by an explicit press before asking for the merge leaves a race — narrow, minutes rather than days, but a race — and claiming on main *after* merging puts a substitution nothing verified onto the protected branch, recoverable only by another pull request. The wait costs one CI run per merge. That is the whole price, and it is paid once per entry rather than once per collision.

**The allocation is `max + 1` and never the lowest free id.** `store/master.py:next_box_number` allocates lowest-free and is right to, because a box number is a label on a drawer that has been emptied. An id here is CITED: D80 culled step 12 and says the hole is correct, and reusing 12 would resurrect every `step 12` in the tree onto a step that is not the one meant — D72's citation drift, arriving through the allocator instead of through a rename. **`max + 1` also keeps a sorted list sorted**, so a slug appended to the end of a `governed_by` list is in the right place before and after the claim.

### What it retires

**`renumbered ids` and `vacated ids` are deleted, and D72's mechanism with them.** Both rows exist to repair a renumber; a branch that never takes a number never vacates one. D72 keeps its account of the incidents — those are evidence and are never rewritten to match a later tree — and stops being a live mechanism. The convention *renumber your own, never another's* is retired in the same breath, having been a rule about who loses a race that no longer runs.

**What replaces them is one row that cannot be satisfied by accident.** `id claims` reads every slug in the tree: each resolves to a slug heading, each heading's slug is unique, each is well-formed — and **main carries none**, which is the invariant the whole design rests on and the only one that catches a claim that half-landed.

### The first claim was made by hand, and that is the bootstrap rather than the workflow

**The pull request that brought the claimer could not be claimed by it.** `make merge` does the claiming, and the `make merge` that merges this change is MAIN's — which knows nothing about slugs. Merging it unclaimed would have landed a heading with no number on main, which is the single outcome this entry exists to prevent. So its own ids were substituted on the branch with the branch's own script, by hand, and it was merged with `--no-claim`.

**Every pull request after it claims automatically, because main has the tool by then.** A hand-claim anywhere in this history is the bootstrap and is not the intended workflow; the workflow is `make merge` and nothing else. This paragraph exists so a reader finding that commit does not copy it.

**And it found a second one, in this file's own auditor.** `scripts/docs-audit.py` used a real, live slug as its self-test fixture — deliberately, so the citations would resolve — and the claim substituted it, turning two assertions about a SLUG into assertions about a NUMBER. **A claim is exhaustive text replacement and cannot tell a fixture from prose.** So: **never name a live slug in a comment or a fixture.** Compose a fixture's ids from pieces, the way this repo already composes numeric ones for the same reason one level down, and describe a shape in prose rather than spelling an id that exists. A comment block in that file came back reading *"a branch writes `## D140`"*, which is how the rule was found.

**The bootstrap earned its keep by finding a bug the self-test could not see.** A step is cited in prose as `step <slug>`, so that is the token — but `docs/map.py` stores the id BARE, as the `n` field, which no token of that shape reaches. The fixture had no map, so sixteen green arms said nothing about it, and the first real claim would have left the map holding a slug while `docs/GATES.md` took the number. `build order mirror` would have failed the commit, so it was never going to reach main silently — but it would have failed it in a way nobody had predicted. `renumber_map` is the second edit here that is not a token substitution, it writes an INTEGER because that row compares by equality against `int()`, and two arms with a real map now cover it.

### The known limit: two OPEN pull requests can still pick the same number

**This removes the treadmill, not the collision, and the distinction is the whole of what it is worth.** The claim reads main at claim time, so it cannot see a number held by a pull request that has not merged yet. Two open branches can still be allocated the same id, and whichever merges second is wrong.

**Both halves were measured on one evening, 2026-09-11, which is why this paragraph can be exact.** A branch renumbered **three times in one session** — D132 to D135 to D137 to D138 — each one a hand-audited sweep across a dozen files where a stale citation still resolves and nothing mechanical separates it from a real reference to the number's new occupant; **three sites were missed on the first pass** and found afterwards by a separate audit. That same evening this entry's own branch was allocated D139, another open pull request merged first and took it, and the repair was **one command over ten files** with a row asserting that no slug survived it. Same class of event. Two very different costs.

**The residual collision is deliberately not closed, and this is the reasoning rather than an oversight.** Reading open pull requests at claim time would put the network and `gh` on the path of `make merge`, for a failure that is already LOUD: `decision index` reconciles `CLAUDE.md`'s index against the headings IN ORDER, so the second merge fails its own commit rather than landing quietly. A guess that is caught is not the same defect as a guess that resolves, and it is the second kind this entry was written for. **Closing it would trade a loud, cheap, mechanical failure for a network dependency in the one command that moves main.**

### Amended 2026-09-11: the claimer is a no-op once a branch has claimed, and that is a gap

**The section above closes the collision it can see and says nothing about the one it makes.** `plan` reads SLUGS. A branch that has already claimed has none left, so `scripts/claim-ids.py` printed `no unclaimed slug in this tree — nothing to do.` and exited — **a true statement about slugs and an incomplete one about safety.** The number it allocated can be taken by main *afterwards*, and nothing looked again.

**It happened TWICE on the evening this entry was written, and a person was the mechanism both times.** PR #262 and PR #265 were allocated the same decision number; #262 merged first, and #265 re-claimed before its own merge. Then PR #265 and PR #270 were allocated the next one; #265 merged first, and #270 had to renumber. **The first was caught before the merge and cost a re-claim. The second was caught only because one session read another session's pull request title.** That asymmetry is the whole argument: both were luck, and only the first had a mechanism anywhere near it.

**`--stale` is the second look, and it is not the residual collision above.** It takes every allocated id this branch ADDS since its merge base with the ref — decision heading, code-card `C` entry, build-order step — and asserts each is still free *on that ref*. The branch's difference against the merge base is exactly the set it is claiming to own; every id main already held is in the branch's copy too, and reporting those would report most of the file.

**The baseline is the MERGE BASE and never the ref, which is the one way to write this check so it cannot see its own subject.** Measured against the ref's current content, an id the ref has just taken reads as already present on both sides, every collision cancels itself out, and the check reports clean forever while being exactly as green as it was before it existed. That mutation is in `scripts/claim-selftest.py` by name, and it is one of seven the staleness arms catch.

**It REPORTS and it never repairs, on this entry's own ordering hazard.** An un-claim has to happen BEFORE a merge and never after: once main is merged in, a substitution on that token reaches main's own copy of the entry too. So it names the collision, says what the id would become, exits non-zero, and leaves the decision to a person or to `make merge`.

**Free is set membership, never a comparison against the ceiling.** D80 culls step 12 and rules the hole correct, so a branch holding an id *below* main's highest that main does not hold is right and must not be refused. `max + 1` still answers what the NEXT id is; only the set answers whether a GIVEN one is taken.

**It needs neither the network nor `gh`, so the ruling above is untouched.** Reading open pull requests is still rejected, and this does not want them: an open pull request's number is not yet a fact about main, and **the branch that merges second is the one that has to move** — so the case that actually bites is the one where the other branch has already LANDED, which a local ref read can see for nothing.

**It runs in two places and they are worth different things.** `make merge` asks for it before every merge, in preview as well as on the press, and that is the authoritative run because the fetch immediately above it makes the answer current. `make check` and `make ci-check` run it too, as `make claim-stale`, where it is the earlier and cheaper warning. **It can only ever under-report against a stale `origin/main`, never over-report**, so a `make check` whose ref is a day old misses a collision it would have caught and invents none — which is what makes it safe on a path that gates. A clone with no `origin/main` at all is ALLOWED and says so, which is `revert-guard`'s call for `revert-guard`'s reason.

**`decision index` stays the backstop and is not weakened or duplicated.** It reconciles `CLAUDE.md`'s index against the headings IN ORDER and still fails the second branch's own commit. What it cannot do is fail it EARLY: by the time that row speaks, two headings already carry one number and the cost falls on whoever merged second. This is the same finding, one step sooner and on the branch that can still cheaply move.

**What it still cannot see is unchanged: two OPEN pull requests, before either has landed.** Neither is a fact about main yet, and nothing local can make them one.

### Amended 2026-09-11: the claim and its guard must walk the same files, and `.js` was in neither

**The substitution reaches a file or it does not, and `.js` did not.** `TEXT_SUFFIXES` carried `.mjs` and not `.js`, and `decision ids in code` walked `.py`, `.ts`, `.tsx` and `.css` — so a slug in a `.js` file survived the claim and no row afterwards could see that it had. Both sets gained it together, which is the only way to add one: a file the claimer rewrites and the guard cannot read is a file this invariant is not asserted over.

**It was found by the first ORDINARY merge, not by the bootstrap, and it fired.** `app/eslint.config.js` cites decisions in its own comments — six of them, listed under its `governed_by` — and the branch that hit this had written its slug there twice. Unfixed, main would now hold two citations of an id that had just been given a number, in the one file neither reader opens. Fixed, that file cites `D142` and the claim covered ten files instead of nine. **The evidence is on main either way**, which is what separates this from the reasoning that preceded it.

**The rule it generalises: the suffix set is every extension that can hold a citation.** A config file's comments are as real as a script's, and nobody had decided otherwise — nobody had considered `.js` at all. `SKIP` is the list that gets a judgement; this one gets completeness.

### What it does not decide

**Not whether an id may ever be typed as a number again.** A session amending an existing entry cites it by its number, as it always has; the slug is for an entry that does not have a number YET. **Not the commit messages** — a message written on the branch names the slug and cannot be rewritten after a push, so the claim commit's own message is where the pair is recorded. **And not D80's stable-id ruling**, which this strengthens rather than reopens: that entry forbids renumbering an EXISTING step because 218 references would silently follow the number instead of the step, and a number claimed at the merge cannot collide, so nothing is ever renumbered to resolve one.