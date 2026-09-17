## The harness is the contract

`make harness` runs seven tests and exits non-zero on any failure. Nothing is "done" until
it exits 0 and you have seen the output. This is the whole reason the project can be run
by an agent unattended — without it, "looks done" is the only available signal.

T1–T4 are the original contract. T5 and T6 arrived with batch script v2 (build-order
step 4): a wrong price is a distinct failure from a wrong match, and a card the pipeline
cannot find in its own photograph is a third thing again. Each deserves its own failing
test name.

T7 arrived before step 7 and widened what the harness is *for*. T1–T6 all check rules —
what a card is worth, which row it matches, which queue it lands in. T7 checks bookkeeping
and wiring: where a physical card is recorded, whether a correction reaches the file that
will actually be read, which column a price is pulled from. That was a deliberate change to
this contract, argued on the grounds that `store/`, `server/` and `cli/` held about 40% of
product code with nothing checking any of it, and that build-order step 7 was about to add
writers to all three.

T9 widened it a second time, 2026-08-31, and the argument is the same shape. **Every test
above this line supplies its own inputs** — fixtures it wrote, symbols its own encoder drew,
composites it rendered — which is what makes their answer keys exact and is also a ceiling
on what they can catch. T9 is the first one whose inputs are **recordings of the physical
rig**, and it exists because the two Playwright specs over the motion trigger were green
through all three versions of a card-present gate, including the two that were silently
dropping cards. They could not have failed: both draw their own frames. See D81.

Every threshold below is a number, not an adjective. `ID_ACCURACY_FLOOR=0.95` is a spec;
"about 95%" is an opinion an agent can talk itself past.
