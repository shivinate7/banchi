## The harness is the contract

`make harness` runs seven tests and exits non-zero on any failure. Nothing is "done" until it exits 0 and the output has been seen. Without it, "looks done" is the only signal an agent has.

T1–T4 are the original contract. T5 and T6 arrived with batch script v2 (build-order step 4). A wrong price is a distinct failure from a wrong match. A card the pipeline cannot find in its own photograph is a third thing again. Each deserves its own failing test name.

T7 widened what the harness is for. T1–T6 check rules: what a card is worth, which row it matches, which queue it lands in. T7 checks bookkeeping and wiring: where a physical card is recorded, whether a correction reaches the file that will be read, which column a price is pulled from. This was a deliberate change to the contract. `store/`, `server/` and `cli/` held about 40% of product code with nothing checking any of it, and build-order step 7 was about to add writers to all three.

T9 widened it again. Every test above this line supplies its own inputs: fixtures it wrote, symbols its own encoder drew, composites it rendered. That makes their answer keys exact, and it caps what they can catch. T9 is the first test whose inputs are **recordings of the physical rig**. It exists because the two Playwright specs over the motion trigger were green through all three versions of a card-present gate, including the two that silently dropped cards. Both drew their own frames, so they could not fail. See D81.

Every threshold below is a number, not an adjective. `ID_ACCURACY_FLOOR=0.95` is a spec; "about 95%" is an opinion an agent can talk itself past.
