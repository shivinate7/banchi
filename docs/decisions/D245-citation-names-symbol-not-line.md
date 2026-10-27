# D245 — A citation names a symbol, not a line

A citation names a symbol, a section or a decision id, never a line number. A line number rots on the next edit to any line above it, and a citation of one reads as true when it is wrong.

Kind: process
Home: scripts/docs_audit/paths_commands.py

### The measurement, and why the obvious guard is the wrong one

**Unreadable.** A citation written `path:N` was invisible to every row. `scripts/docs_audit/paths_commands.py`'s `_CANDIDATE_RE` has no `:` in its character class. So a line of `docs/GATES.md` was extracted as the bare filename. The file resolved, and the `paths` row reported "references resolve". A citation could point at a line deleted weeks earlier, and the row stayed green. The row was not wrong about what it checked. It was read as checking something wider.

**Thirteen visible.** 713 line anchors were in the staged documents. 13 pointed past their target's end.

**The disease is far wider.** Of 443 anchors into code, 313 name an identifier in the same sentence. Those can be checked without reading meaning. **219 of them point at the wrong line**, a rate of 69.7%. A stricter probe counted only sentences naming a bare identifier, not a path. It put the rate at 183 of 206, or 89%.

The two populations differ and are NOT reconciled here. Neither definition leaves the direction in doubt. Most line anchors into code in this repo were already wrong.

**So the obvious row is the wrong one.** A row that only asks whether line N exists would go green over 219 known-wrong citations. It would print a confident verdict while doing it. A guard that reads green over its own subject is the founding complaint here. It was the first design proposed for this work, and the measurement rejected it.

### What is built

A line number rots on the next edit to any line above it. A symbol does not. `check_paths` already verified a `module.attribute` citation against `module_attributes()`. The primitive existed. The work was to move prose onto it, not to build a second reader for a form nothing can keep true.

One `line anchors` row refuses every line anchor, such as `path:N` and `path:N-M`, in a document and in a code comment, with no list and no exemption. A lane converted the last 776 anchors to symbols (D280, offender lists replace pinned counts). The row gates and writes nothing (D18).

**The TypeScript reader** extends the `module.attribute` form to `.ts` and `.tsx`. Both were in `KNOWN_SUFFIXES` and so never reached the fallback. The reader works statically. Its docstring names what it cannot see: a symbol from a generic factory, a re-export, and a name assembled at run time.

The row reads this entry too, so an example anchor here is written in words, never as `path:N` with a real number.

### What the row cannot see, stated rather than implied

D149 ruled that a section number which resolves is not a citation that is right. No check can read what a sentence is about. D149 measured the nearest proxy at one genuine catch against three false alarms over 38 citations, and declined it.

Nothing here repeals that. The row reads SHAPE. It makes a line number impossible and makes no citation right: a symbol that exists may still be the wrong one.

### The addresses D149 records

D149 names four addresses in the file the decisions once were. Those are a RECORD of where wrong citations stood when that file was one document. Rewriting them falsifies the record. They read as words ("the old decisions file, line 9522"), which no line-anchor shape matches. So no exemption is needed.

`docs/specs/capture-server.md` is cited as live authority by many sites, several of them in code. Those callers cite it by SECTION, which is the durable form.

A citation that points at nothing is dropped, never re-aimed at a nearby record, which would manufacture a source.

### Proved by violating it

The audit's self-test drives `check_line_anchors` over fixtures. Each line-anchor shape goes red. A symbol, and a line written in words, go green.
