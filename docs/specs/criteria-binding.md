# Spec — bind the published criterion to the value the gate compares

Status: **specified, not built.** Raised by the review of the audit-retirement branch as
findings 2 and 14. Nothing here is implemented; the two defects below are live.

The audit-retirement branch fixed the same bug class three times, and named the rule for
spotting it in `harness/tests/t1_id_eval.py`: repeated *reads* of one name are fine, the
defect is two independent *decisions* that must agree, where only one of them moves. Two
survivors of that sweep are recorded here rather than fixed in place, because the obvious
fix for each one walks into a trap in the auditor that has to be designed for first.

---

## The two defects

### A — the threshold is published as prose and compared as a float

`harness/tests/t1_id_eval.py` carries both, two lines apart:

```python
PASS_CRITERIA = "holdout_accuracy >= 0.95"     # what every doc layer publishes
ID_ACCURACY_FLOOR = 0.95                       # what `passed` actually compares
```

`scripts/docs-audit.py`'s `pass criteria` row extracts numbers from the *string* and
asserts each appears in `### T1` of `docs/GATES.md`. Nothing reads `ID_ACCURACY_FLOOR`.
Lower it to `0.90` and change nothing else: `make harness` stays green, the whole audit
stays clean, and `docs/GATES.md`, the module docstring and `PASS_CRITERIA` all keep
publishing 0.95. Verified.

Raising the floor is caught, because the harness fails. **Lowering it — the direction that
weakens the gate — is invisible at every layer.**

### B — the results-file key is a literal beside a derived value

Commit `8017298` made the split one decision, `gated_split`, and every label derive from
it. One residue: the payload key is still hand-written.

```python
"gated_on": gated_split,              # derived
"holdout_accuracy": gate_accuracy,    # literal key, value from gated_split
```

Move `gated_split` to the tune half and the file publishes the tune number under a key
named `holdout_accuracy`. The `criteria evidence` row builds `gated + "_accuracy"` =
`"tune_accuracy"`, does not find it in `PASS_CRITERIA`, and fires — so B is caught today,
but by a check that reports the *criterion* as wrong rather than the key. Fixing A without
fixing B makes that worse: see the interaction below.

---

## The interaction, designed up front

The obvious fix for A is to derive the string from the float:

```python
PASS_CRITERIA = f"holdout_accuracy >= {ID_ACCURACY_FLOOR}"
```

**That silently disables one check and spuriously fires two others.** Measured against the
shipped auditor, not reasoned about:

| `PASS_CRITERIA` written as | `string_assign` returns |
|---|---|
| `"holdout_accuracy >= 0.95"` | `'holdout_accuracy >= 0.95'` |
| `f"holdout_accuracy >= {FLOOR}"` | `None` |
| `"holdout_accuracy >= " + str(FLOOR)` | `None` |
| `"holdout_accuracy >= {0}".format(FLOOR)` | `None` |
| `("holdout_accuracy " ">= 0.95")` (adjacent literals) | `'holdout_accuracy >= 0.95'` |

`string_assign` evaluates with `ast.literal_eval`, and an f-string is a `JoinedStr`, not a
literal. Three consequences, in descending order of how much they matter:

1. **`criteria evidence` goes silent, not red.** It builds its map as
   `{name: string_assign(...)}`, so the value becomes `None`, `criteria.get("T1")` is
   `None`, and the `text is None` branch `continue`s. The row then reports
   `1 scored run, gate field published` having compared nothing. This is review finding 7
   — the missing ADVISORY downgrade — reached by the front door.
2. `pass criteria` reports `no module-level PASS_CRITERIA string to read` and blocks. Loud,
   correct, and the reason A cannot simply be fixed in place.
3. **Float repr is not the published spelling.** `f"{0.90}"` is `"0.9"`. A floor lowered to
   0.90 would derive `>= 0.9` while `docs/GATES.md` says `0.90`, firing `criteria wording`
   for a real change that was correctly made. Worse, the number check asks whether `"0.9"`
   appears in the section text, and `"0.95"` contains `"0.9"` — so the number leg would
   pass on a stale doc. Any derivation must format explicitly (`:.2f`), and the format is
   part of the contract, not a detail.

## What to build

Three pieces, in this order. Each is independently landable and the order matters — the
first exists so the second cannot go quiet.

1. **Close the silent branch first.** `check_criteria_evidence`'s `text is None` path must
   report, not `continue`. The retired count-of-checks row had the shape to copy: it
   downgraded itself to `ADVISORY` and said so in its summary — *"the reader could not
   account for every check"* — rather than publishing a confident line about a comparison
   it did not make. A row that could not find its subject must never summarize as though
   it did. **This is worth landing on its own even if nothing below is built**, because it
   is the difference between the auditor failing and the auditor going quiet.

2. **Teach `string_assign` the derived forms, or teach the tests one blessed form.** Two
   viable designs; pick one and record which:

   - *Widen the reader*: handle `JoinedStr` where every interpolation resolves to a
     module-level literal in the same file, evaluated with `ast` and never by importing.
     Keeps the tests readable. Costs real parser surface in a file whose whole argument is
     that it does not run project code.
   - *Narrow the writer*: keep `PASS_CRITERIA` a plain literal forever and add a separate
     check binding the numbers inside it to the module-level constants the test compares —
     `0.95` in the string must equal `ID_ACCURACY_FLOOR`. No new string forms, no new
     evaluation, and it catches the defect from the other side.

   **The second is the better fit for this repo** and is the recommendation: it adds a
   comparison rather than an evaluator, it leaves `PASS_CRITERIA` greppable, and it does
   not put an interpreter on the audit path. Recorded as a recommendation, not a ruling.

3. **Derive the results key** — `f"{gated_split}_accuracy"` as the payload key — only after
   1 and 2. Note the ordering trap: `scripts/status.py` reads keys out of the score file,
   and `docs/GATES.md` names `holdout_accuracy` in `### T1`. Deriving the key means both
   follow, and the check that would have caught them following incorrectly is the one
   being repaired in step 1.

## What must not be built

**No generator.** Writing `docs/GATES.md`'s `- **Pass**:` line from the constant is
forbidden by D18, and the seam list there is empty by design. Every option above is a
comparison that fails; none of them writes. If a future session finds itself proposing
that the doc be generated, that is a change to D18 argued on its own terms, not a step in
this spec.

## How this gets verified

Bind the acceptance to the failure, not to a green run — the branch that produced these
findings was green at every commit. Both must hold in a scratch clone:

- lower `ID_ACCURACY_FLOOR` to `0.90` and change nothing else → the audit exits 1 naming
  the disagreement, and does not merely go quiet;
- move `gated_split` to the tune half → the audit exits 1 naming the *key*, and no row
  reports a confident summary about a subject it could not locate.

Add both to `scripts/docs-audit.py --self-test`. A check with no self-test case is a check
this repo has already learned it cannot trust.
