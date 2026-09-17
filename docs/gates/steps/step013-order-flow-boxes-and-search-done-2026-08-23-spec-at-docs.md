13. ~~**Order flow, boxes, and search**~~ — **done 2026-08-23.** Spec at `docs/specs/order-flow.md`. the store's fungible-copy model (D7 amended), the box
    object and its retroactive capacity (D20), per-box section layouts (D10 amended), the
    search-and-sell screens on both sides, and the operations D26-D30 ratify.

    **Every item this step was scoped around is built and reachable as of 2026-08-23**:
    schema v2 with its migration, the server routes, the shared search components, the
    Fulfiller's search, D26 (`retired` and re-shoot in place, both with controls on the
    owner's screen), D27 (session state in `sessionStorage`), D28 in both halves (the
    layout fix and the twenty-second answer undo), D29 (group-answer a homogeneous queue)
    and D30 (the gap convention as `neighbors` and `section_gaps`). D31 then merged
    `#/boxes` and `#/pull` into `#/inventory`, so the screens this step names by their old
    routes are modes of one.

    **This step's Outstanding list ran to five entries while all five were already on disk,
    which is the failure this file warns about pointing the other way.** A stale record is
    believed exactly as hard as a true one, and nothing mechanical checks a list of prose
    claims against the tree. Rebuilt from a grep rather than from the previous list.

    **What was outstanding was never in this list at all: the CLIENT half.** Box delete,
    the mid-box delete with its contiguous shift, and the retroactive claim corrections all
    passed T7 with no client function and no control on any screen — so this step could
    read as complete while three of its operations were unusable. They are reachable now,
    and `app/tests/inventory.spec.ts` asserts it. `CLAUDE.md`'s route-is-not-a-feature rule
    is that discovery written down as a standing rule.