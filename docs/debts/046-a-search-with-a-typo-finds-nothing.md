## 46 — a search with a typo finds nothing, and no near match is offered

**The finding.** D271 (one forgiving search matcher) leaves one gap open: FLT-05, typos and a
near match. A query like `Rekenton` returns zero results today. The owner gets no hint that
`Renekton` was meant. Round 12 of D271, 2026-09-26, confirmed this as the one open gap. The
other listed gaps had closed in earlier rounds.

**Two options, both costed on 2026-09-27.**

| | Suggest | Match it |
|---|---|---|
| What changes | Only the zero-result state. Exact matching is untouched. | The matcher itself, in both copies (`server/match.py` and `app/src/kit/match.ts`). |
| Build | A near-name lookup on a zero result, with Python's `difflib` on the server and a small browser copy. The screen shows "Did you mean" as a tap target. | A fuzzy hit must join the ranking and the FTS candidate step. No first hit that the case table pins may change. It must stay fast per keystroke over about 3,500 cards. |
| Risk | Low. It draws only on a zero result. | Real. A short query can fuzz into a wrong card, and a typo can show a different card with no sign. |
| Cost | One Sonnet lane, about the size of a small lane, and one lean review. | Two or three times that, an adversarial review, and likely a second round. |

The orchestrator recommends Suggest. It keeps D271's exact rule intact and adds a separate hint.

**The owner's ruling (2026-09-27, verbatim).** `save both options as a debt to address later, good suggestions, not what i need built rn`.

**Why it is not done now.** The owner deferred it. Nothing breaks without it. A typo costs one
retype.
