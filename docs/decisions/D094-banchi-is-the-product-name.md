## D94 — Banchi names everything; --bn-* names styles

**Banchi names everything: the app, the repository, the checkout, the CLI, the env vars and the machine state.** Banchi (番地) is a lot number, the address of a thing. Every card in this store has an address: box, then section, then card (D58). The owner ruled that the one name goes all the way down. When a program name and a screen name disagree, each reader must translate between them. That cost is larger than the cost of one rename.

**The rename covers these names.** `./pkmnscan` becomes `./banchi`. `PKMNSCAN_*` becomes `BANCHI_*`. `~/.pkmnscan` becomes `~/.banchi`. The `com.pkmnscan.*` launchd labels become `com.banchi.*`. `~/Developer/pkmnscan` becomes `~/Developer/banchi`. The store stays `inventory/store.sqlite` (D88), because that name holds no product name. Fixtures are never modified, so a fixture that holds the old name keeps it.

**Done is `git grep -i pkmnscan` printing nothing outside `fixtures/`.** The rename merged, so a new `pkmnscan` is a defect. The remaining hits are this entry, CLAUDE.md's "Banchi names everything" section, and the code that moves or removes machine state left under the old name (`~/.pkmnscan` and `com.pkmnscan.*` plists).

**One derived name is already guarded.** GitHub Pages serves a project site at `/<repo>/`. `.github/workflows/demo.yml` derives `DEMO_BASE` from the repository name, so a rename cannot leave it pointing at the old one. GitHub redirects the old repository name, so old clone URLs and merged PR links still resolve.

**The plumbing was frozen, and the diff is what says so.** `app/src/server.ts` moved 11 lines and `app/src/types.ts` moved 6 across the whole rebuild, against 1,693 in `App.tsx` alone. Every server call, state machine, keyboard binding and handler was held still while markup, CSS, information architecture and interaction were replaced; the screen agents were denied the wire files outright and told that where a field does not exist on this branch they draw the correct shape against what does, leaving a one-line comment naming the field a merge brings. That freeze is why every settled plumbing decision in this file survives a rebuild this size: the thing that changed is the only thing that was allowed to.

### The tokens are the system, and dark is not a skin

**`app/src/tokens.css` declares 152 `--bn-*` names in three registers** — ink for what you read, line for what separates, brand for where to look, indigo for action and vermilion for what is live — over type, spacing, radius, motion and elevation scales. No component sheet may name a color. Light is bare `:root`; dark is `:root[data-theme="dark"]` and redefines the same names rather than adding new ones, so a screen written against the tokens is right in both themes without knowing either exists. The choice is the person's and lives in `localStorage` under `banchi.theme`, which is D27's device-local rule applied to the one fact here that is genuinely about the device in front of you: it is not inventory, and two people at two screens may want different answers.

**The legacy aliases at the foot of that file are a migration seam, and this entry records what they were for because they are already spent.** `--ink`, `--muted`, `--line`, `--accent`, `--field`, `--display`, `--util`, `--s1` through `--s8` and `--r` resolve to their `--bn-*` equivalents. Keeping them live is what let every screen re-skin the moment the token file landed, and then be rebuilt one at a time by agents working in parallel, instead of all at once or not at all. **The migration finished inside the same job**: of the 30 stylesheets under `app/src`, not one reads a legacy name today, against 255 uses of `var(--bn-ink)` alone. They are deliberately not deleted in the change that emptied them — a token file and thirty stylesheets moving in one commit is a revert nobody can take apart — and they cost nothing while they wait. This is not the shape D10's `CARDS_PER_SECTION` deletion took: that constant was deleted because it asserted something false about the operator's boxes, and an alias asserts nothing.

### The kit is the vocabulary, not a folder of helpers

**`app/src/kit/` and `app/src/kit.css` hold the primitives new screen work is written in**: `Button` in seven variants and four sizes, `Kbd`, `Pill`, `Chip`, `PageHeader`, `EmptyState`, `Notice`, `Segmented`, `Stat`, `Logo`, a 70-name `Icon` set, and a global `toast` stack, over `.bn-*` classes for pages, panels, wells, fields, tables, lists, sheets, modals, menus and receipts. `#/gallery` renders all of it as 22 live sections and is a registered route (D95), so the kit cannot rot unseen the way an undocumented set of helpers does.

**Uniformity is the point, and D50 is the entry this discharges.** That ruling says an interactive element's feedback belongs to the product rather than to each stylesheet; before this there was no product-level place to put it, so every sheet answered the question again. There is one now, and a screen that needs a primitive the kit lacks builds it under a screen-prefixed class and reports it for promotion rather than inventing a second `Button`.

### What is given up, and what would reopen this

**Nothing mechanical checks that a component sheet names no color, and nothing checks that a new screen imports the kit.** `docs/DESIGN.md`'s token table is checked and its Fulfillment floors are asserted in a browser by `make design-check`; the `--bn-*` discipline is a rule someone reads, which `CLAUDE.md` already records as the weakest kind of guard this repo has. A `--bn-*`-aware version of the existing raw-color row is the obvious reader and is not built here.

**What would reopen this: a third theme, or a second product on these tokens.** Both are reasons to promote `[data-theme]` from two named sheets to a generated palette, and neither has been asked for. The aliases are the one piece of housekeeping this entry leaves owed: the grep is already empty, so they are dead code, and the commit that deletes them takes the paragraph above with it.

---
