## D140 — Merge claims the decision number

**Ruled by the owner: a branch never takes a record number. The merge tool claims it, before the merge.** The owner asked why a renumber happens at all. A branch reads `origin/main`, takes the next free id, and is wrong when another branch merges first. The allocation needs what main holds, and a branch cannot have that.

**The shared merge tool makes the claim, and no Banchi code owns it.** `make merge` runs the `merge` command. It lives in claude-settings and reads `.github/stamp.json`. The tool allocates in a temporary worktree at the pull request head. It commits the numbers to the PR branch with a `Record-claim` trailer. It waits for that commit's checks, and only then merges. Nothing that main has never run CI over reaches main. A stopped merge undoes its claim commit. The config holds the record kinds, the `regenerate` command, the gloss rule for CLAUDE.md and the `merge` block (D42, main moves by pull request).

### The vocabulary is a slug, and two segments keep it out of prose

**`## D140`, cited as `(D140)`, in prose, in code comments and in `governed_by`.** A branch writes `D-<slug>` for a decision, `C-<slug>` for the code-card track and `DEBT-<slug>` for a debt. The letter names the namespace and the slug names the entry. A build step has no letter. Number it by hand. The tool refuses an unclaimed `step <slug>` marker (`unclaimed` in the config).

**Two segments minimum.** `D-pad` is one segment and is ordinary prose. Two or more segments make an id. The slug grammar is `slugRegex` in `.github/stamp.json`. The docs-audit `claim vocabulary` row reconciles it with the auditor's own.

**Lowercase, because the letter carries the namespace.** A mixed-case slug gives two spellings to one entry, and nothing says so.

### The claim is `max + 1` against main's tip, and the wait is the point

**The owner chose this against two faster options.** They are recorded because someone will propose them again. A claim by an explicit press before the merge leaves a narrow race. A claim on main after the merge puts an unverified substitution on the protected branch, and only another pull request can repair it. The cost is one CI run per merge.

**The allocation is `max + 1` and never the lowest free id,** because an id is cited. D80 (a section needs a reader or goes) culled step 12 and rules the hole correct. The ceiling is above every number in the branch tree and in the tip of the base. So a number that main took since the cut is never reused.

**Mode `check` runs on every pull request and every push to main.** It is the `records` job in `.github/workflows/check.yml`. It refuses a number that a branch wrote by hand. One exception: a `Record-claim` commit added it and main's tip lacks it. On main it refuses any pending record. The docs-audit `id claims` row reads every slug in the tree. Each slug resolves to a slug heading, and each is unique and well formed. **Main carries none.**

### What it retired

**`renumbered ids` and `vacated ids`.** Both rows repaired a renumber. A branch that never takes a number never vacates one. The old local claimer is gone, with its stale-claim second look. The tool's base-tip ceiling and mode `check` answer the same question in CI. The tool also reads main again before the press.

### The known limit: two OPEN pull requests can pick the same number

**This removes the treadmill, not the collision.** The claim reads main at claim time. It cannot see a number held by a pull request that has not merged. The branch that merges second claims again. The owner rejected reading open pull requests. That puts the network on the claim for a failure that is already loud, because mode `check` refuses the second branch's stale number.

### What it does not decide

**Not whether an id may be typed as a number again.** A session that amends an existing entry cites it by number. The slug is for an entry with no number yet. **Not the commit messages.** A message written on the branch names the slug, and the claim commit's own message records the pair. **Not D80's stable build-step ids.**

**The tool walks every extension that can hold a citation,** `.js` and `.mjs` included. The docs-audit `decision ids in code` row walks the same set. A file that the tool rewrites and the guard cannot read is a hole in both.
