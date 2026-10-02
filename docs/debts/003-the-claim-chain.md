## 3 — The claim chain

**A capture-time claim crosses hops that nothing binds together.** `CAPTURE_CLAIM_FIELDS` in `store/master.py` binds the server side (the record upsert, the `allocate_capture` pass-through, `sidecar_payload`, `PUT_FIELDS`), and T7's `check_capture_claim_chain` iterates it. Still unbound:

- The three app-side hops, `app/src/CaptureScreen.tsx`, `app/src/types.ts` and `app/src/server.ts`. No Python constant reaches a `.tsx`, and `make typecheck` sees a field added to `types.ts`, never one omitted.
- `cli/cmd_identify.py` builds `master.Card(...)` literally instead of through `allocate_capture`, so it carries the claim names by hand. This is the one closable hop.

**The operator's `note` never reaches the model.** `identify/prompt.py:user_text` takes `set_hint`, `with_crops`, `strategy` and `rarity_claim`, and no note. `identify/sidecar.py`, `cli/cmd_identify.py` and `CAPTURE_CLAIM_FIELDS` all carry it. For `misc` it stands in for a set hint that does not exist. Routing it through `set_hint` would tell the model the note is a stack label. The proper fix is a note clause on `Profile` and a `user_text` parameter, which changes `prompt_fingerprint` and so what T1's recorded scores are evidence about.

**Spec fixtures are untyped copies of the wire.** A field added to a wire type breaks a stub only when a browser suite runs. Annotating a fixture with its `app/src/types.ts` type moves that failure onto `make check`'s typecheck. `capture-claims.spec.ts`, `capture-undo.spec.ts` and `inventory.spec.ts` do it for `GameRegistry`. Most spec files do not: 37 of 55 import no type from `app/src/types.ts`.

**Outcome at risk.** A claim missing from a sidecar, or a finish reverting after a correction, shows at the far end, and debugging starts at the screen.

**Closes when.** `cmd_identify` allocates through `allocate_capture`, the note has a prompt clause under its own fingerprint decision, and each fixture is annotated with its wire type.
