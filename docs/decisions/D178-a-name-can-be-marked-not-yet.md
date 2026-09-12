## D178 — A document may name what it would create, and the marking expires by itself

**A `+` in front of a path, a `make` target or a `PKMNSCAN_` name means the thing does not exist yet.** Three mechanical docs-audit rows verify that a named thing is real — the `paths` row, the make-targets row and the `env vars` row — and a design document's whole job is to name what it would create. Without a marker those two things cannot both be served.

**The owner asked for this, and asked for it as a design question rather than a workaround.** Their words, on being shown the established practice: *"i mean just cuz convention is established doesnt mean that's the best way right? i told you that if there's something in the docs that doesn't sound too ideal, to push back — isn't there a more optimal way of having dynamic labeling of naming things before theyre built to avoid conflicts?"*

### The two things it replaces, and why each was worse

**Spelling the name bare, without a code span.** This is what the repo had been doing and it is what a session reached for first. It works by making the checker unable to SEE the reference, which is evasion rather than declaration — and it costs the reader the one thing a code span is for, since a bare +scripts/guard-shell.py in a sentence is no longer distinguishable from prose. **It also does not work at all for `env vars`**, which reads markdown for `PKMNSCAN_` tokens whether they are backticked or not. A fix that covers two of three rows and lies to the reader about the third is not a convention worth keeping.

**An allowlist line per reference.** `scripts/docs-audit-allow.txt` already accepts *"named before it is built"* as a reason and is self-cleaning — its own row fails when a listed path exists — so this would have worked correctly. It was declined on two counts. It puts a name's status two directories from the sentence that uses it, so a reader learns nothing from the reference itself. And it is an **exact-match roster that every branch edits**: one shelf document naming twenty-one unbuilt mechanisms would have added twenty-one lines to a live conflict surface, on a day when five PRs were already colliding in two shared files.

**The allowlist keeps the job it is actually for, and the distinction is worth two mechanisms.** A path listed there is meant to be unresolvable FOREVER — `app/src/orderWalk.ts` is deleted and its references record the deletion (D96). **A `+` says *not yet*, which is a claim with an expiry.**

### It expires by itself, and that is the load-bearing half

**Every one of the three rows FAILS when a marked name EXISTS**, so the sigil has to come off in the PR that builds the thing. A marker that could be left on would turn every proposal into a permanent exemption — which is the failure the allowlist's own header already records, in its words: *"an allowlist that only grows turns into a list of things nobody has looked at since."*

### What it deliberately does not mark

A `+` is read **only where a row was about to make a claim about existence**, and only when the token it precedes is shaped like a path, a make target or an env name. `+x` is a file mode and D44's entry contains one; it matches nothing here and never will.

### It caught its own author twice, which is the evidence it works

**A concrete example name inside the checker made that name real.** Documenting the sigil in `scripts/docs-audit.py` with a full `PKMNSCAN_`-prefixed example put that name in the `env vars` haystack — so every marked reference to it in a design document then failed as *"the code reads it now."* **A mechanism whose documentation lives inside its own subject has to be written for that**, and the examples in that docstring name the prefix and stop.

**And a generated document broke a path across a line.** `textwrap` split `scripts/githooks/pre-commit` on its hyphen, leaving the prefix alone on one line as a reference to nothing — which the `paths` row correctly refused, and which no sigil should have silenced. Eleven tokens were broken that way in one file. The repair is the generator's, not the checker's.

### Proved by violation — six arms, six caught

Three that must still fail: an UNMARKED missing path, an UNMARKED missing `make` target, an UNMARKED undocumented env name. Three on the sigil itself: a marked path that exists, a marked target that exists, and the sigil reader deleted so every marked name fails again.

### Reopening condition

**If a marked name survives more than one release of the thing it names, the expiry is not working** and the answer is not a longer grace period — it is that the proposal was abandoned and its document should say so. And if a fourth row ever grows an existence claim, it reads the same sigil; a second marking convention would be the drift this one exists to end.

### A wrinkle worth recording, because it will bite the next author

**Two of these rows are NAMED after the thing they check**, so writing about them inside a code span makes the row read its own name as a claim: `` `make targets` `` is a row, not a target, and it fails the make-targets row every time somebody documents it. The entry above says *the make-targets row* in plain words for exactly that reason. **A checker whose row name is also a valid subject of that row cannot be discussed in its own vocabulary** — worth knowing before naming the next one.
