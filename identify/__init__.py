"""Identification — Claude Haiku vision, owned end to end (D2).

Split in two so the harness can test the contract without the network:

  prompt   pure. The system prompt, the JSON schema, the enum, and the parser that
           turns one model response into the `IdentifiedCard` fields the join needs.
           A fingerprint over all of it goes into every T1 result file, because a
           score without the prompt that produced it cannot be compared to anything.
  batch    transport. The Anthropic **Batch API** — never sequential real-time calls.
           v1 claimed Batch and shipped real-time; that is the bug this split exists
           to make visible, since `batch.py` is the only file that talks to Anthropic
           and it has no per-card request path to fall back to.

`pipeline/` stays pure by its own docstring, so this cannot live there. Build-order
step 5's batch script and harness T1 both drive `batch.run_batch`, which is the point:
T1 scores the code that will actually run, not a stand-in for it.
"""
