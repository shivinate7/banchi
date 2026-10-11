13. ~~**Order flow, boxes, and search**~~ — done. The spec is at `docs/specs/order-flow.md`. It covers the store's fungible-copy model (D7 amended) and the box object with its retroactive capacity (D20). It also covers per-box section layouts (D10 amended), the search-and-sell screens on both sides, and the operations D26-D29 ratify.

    Every item in the step's scope is built and reachable:

    - schema v2 and its migration, the server routes, and the shared search components;
    - the Fulfiller's search;
    - D26: `retired` and re-shoot in place, both with controls on the owner's screen;
    - D27: session state in `sessionStorage`;
    - D28: the layout fix and the twenty-second answer undo;
    - D29: group-answer a homogeneous queue;
    - D58: the gap convention as `neighbors` and `section_gaps`.

    D31 then merged `#/boxes` and `#/pull` into `#/inventory`. The screens this step names by their old routes are modes of one.

    The Outstanding list ran to five entries. All five were already on disk. A stale record is believed as hard as a true one. No check compares a list of prose claims with the tree. The list was rebuilt from a grep.

    The real gap was the client half. Box delete, the mid-box delete with its contiguous shift, and the retroactive claim corrections passed T7 with no client function and no control. The step could read as complete while three operations were unusable. They are reachable now, and `app/tests/inventory.spec.ts` asserts it. `CLAUDE.md`'s route-is-not-a-feature rule records that finding as a standing rule.
