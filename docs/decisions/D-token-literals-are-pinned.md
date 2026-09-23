## D-token-literals-are-pinned — A literal that duplicates a token is caught by family, and the ratchet is pinned per file

`docs/reviews/ux-2026-09-20/RANKING.md` section 4 names a defect class. It is "literals that
duplicate a token exactly". `css-var-check.py` cannot see it. That checker catches a `var()`
pointed at nothing. This defect is the opposite shape: a plain value where a `var()` belongs.
`font-size: 22px` sits where `var(--bn-fs-2xl)` belongs. `transition: ... 480ms` sits where
`var(--bn-t-draw)` belongs. The pixel is identical today. It stops being identical the moment
the token moves. Nothing today says so. `docs/reviews/ux-2026-09-20/system.md`'s inventories
are the measured count this entry builds against. `scripts/token-literal-check.py` is the
guard. This entry is its argument.

**THE SWEEP THAT WOULD REMOVE THESE LITERALS IS NOT THIS BRANCH'S WORK.** It is a separate
lane. It is held behind other lanes' merges. Two branches must not fight over one call site.
This entry argues the GUARD only: how it decides a finding, and how it lands without blocking
on a cleanup nobody has done yet.

### Why property family, never value alone

The same number means different things in different places. `4px` is `--bn-1` in `padding`.
`4px` is `--bn-r-xs` in `border-radius`. `16px` is `--bn-4` (spacing) or `--bn-fs-lg`
(font-size) or `--bn-r-xl` (radius), depending only on which property holds it. A checker
matching value alone would call `border: 1px solid` a duplicate of some spacing token, for no
reason a person would accept. It would conflate two independent scales sharing one step.

So the check reads `tokens.css` and sorts its tokens into six families. Each family is a
name pattern: `--bn-fs-*` (font-size), `--bn-lh-*` (line-height), `--bn-tracking-*`
(letter-spacing), `--bn-<n>`/`--bn-0-5`/`--bn-0-75`/`--bn-1-5` (spacing: padding, margin, gap,
inset), `--bn-r`/`--bn-r-*` (border-radius), `--bn-t`/`--bn-t-*` (duration: transition,
animation). A literal is compared only against the tokens of its own property's family. The
families are derived from `tokens.css`'s own names on every run. Nothing here is a copied
list. A token added, renamed or re-valued changes what the next run looks for. No edit to the
checker is needed.

**Why `spacing` is padding/margin/gap/inset, and not every length property.** `top`/`right`/
`bottom`/`left` (position offsets) can numerically equal a spacing token too. `width`/`height`
can as well. An offset is not a gap. It is a different semantic wearing the same number. The
review named padding/margin/gap/inset by example, in RANKING.md section 4. Widening the family
to every length property is a scope decision for a person. It is argued here, not assumed. The
same restraint keeps offsets and dimensions out of `PROPERTY_FAMILIES` today.

**`--ff-fs-*`, Fulfillment's own font-size scale, is NOT in `tokens.css`.** It is declared
inside `Fulfillment.css` itself. This was checked before writing this entry, not assumed. Per
the brief's own instruction, that means `--ff-fs-*` stays OUT of scope. Including it would mean
reading a second file's scale for one screen's stylesheet. That is a real widening. It is not
this branch's call to make alone. `Fulfillment.css`'s OTHER properties — padding, margin, gap,
border-radius, transition — stay in scope through the shared `--bn-*` families. They did
surface real findings there.

### What is left out, and why

Colour tokens are left out. A hex or `rgba(...)` literal is already `raw color`'s row.
Checking it here too would report the same defect under two names. Font-family tokens
(`--bn-font-*`) are left out. A stack is not one comparable scalar. Shadow (`--bn-shadow-*`)
and easing (`--bn-ease*`) tokens are left out. They are multi-value composites nobody retypes
by coincidence. Shell dimensions are left out too: `--bn-sidebar-w`, `--bn-rail-w`,
`--bn-topbar-h`, `--bn-page-w*`, `--bn-control-h*`. Each names one place in the shell. None is
a value ordinary screen CSS would reach for on its own. Three scalar constants have no
property family of their own in this repo's CSS: `--bn-disabled`, `--bn-stagger`,
`--bn-stagger-cap`. They are left out too. The legacy aliases at the foot of `tokens.css` are
left out. CLAUDE.md's own ruling says a new rule may not read one. Every family pattern here
matches `--bn-` names only. The legacy names are not `--bn-` names.

### Why a per-file pin, and not landing red, and not the sweep first

Main already carries the literals this check is built to catch. The review measured them. This
entry's own first run over the real tree found 578, across 32 files. Three options were open.

1. **Gate at zero and fail the tree today.** Refused. `make check` would go red on main
   itself, over a defect nobody asked this branch to fix. Every other lane's merge would block
   until the sweep lands. The sweep is deliberately not this branch's work.
2. **Land the sweep first, in this branch.** Refused by the brief this entry was written
   under. The sweep touches call sites other lanes are editing right now. Landing it here
   would collide with work already in flight.
3. **Pin each file's current count as a ceiling, per file.** This is D229's own shape, moved
   here from `docs-audit`'s prose ratchet. A file's count may only go DOWN from here. The
   sweep, whenever it lands, lowers pins. Nothing about the guard blocks it or requires it
   first.

Option 3 is what shipped. `scripts/token-literal-check.json` holds `{"files": {"<path>":
<count>}}`. It is produced only by `scripts/token-literal-check-pin.py --pin`. That is a
person's own act. It is never the check itself. D18 says nothing that writes may gate a
commit. A file the pin has never seen, but that now carries a finding, fails. This matches a
raised count. A file whose count fell is accepted silently and printed. It is never a
failure. Both are D229's own two non-failure states, carried over unchanged.

### The allow-list, and what is in it today

`scripts/token-literal-allow.json` exists for one case. A literal can match a token's value by
coincidence, while meaning something else in spirit. The brief's own example is a 1px hairline
border that happens to equal a token nobody meant to reference.

**No entry is in it as of this branch.** `border`/`border-width`, where a hairline would live,
is not one of the families this checker reads at all. No such coincidence was found needing an
excuse. The mechanism is built
and proved instead. A stale entry — one matching no real finding — fails the check. This is
mutation-tested in `token-literal-check.py --self-test`. It is proved against the day a real
one-off shows up, not invented for this entry alone.

### What the guard cannot see

A literal built inside a template string, or a computed value such as `` `${n}px` `` or
`calc()`, is invisible. This checker does not evaluate expressions. `css-var-check.py` states
the same limit for its own reach. A TSX inline style, such as `style={{ fontSize: 22 }}`, is
measured but never gated. The real scan this entry cites found 13 such literals, across 88
TS/TSX files. The count is printed on every run. Gating it would need the same string and
bracket-key definition machinery `css-var-check.py` built for its own reason. This repo has
not yet measured that a literal duplicate is common enough in TSX to be worth that cost. A
near-miss, such as `17px` beside a `16px` token, is invisible by design. This check is about
an EXACT duplicate. It answers whether one number states the same fact twice. It is not a
design judgement about whether two close values should be reconciled.

### Governed by

D18: a generator may write. Nothing that writes may gate a commit — the pin file and its
`--pin` script. D173: a rule that can be enforced mechanically is enforced mechanically.
D161: `make check` proves the product first, guard self-tests last. D229: the ratchet is
pinned per file, moved here from the prose ratchet it was built for.
