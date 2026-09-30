## 46 — a search with a typo finds nothing, and no near match is offered

D271's one open gap (FLT-05): a query like `Rekenton` returns zero results and gives no hint that `Renekton` was meant. A typo costs one retype. The owner deferred both costed options.

| | Suggest | Match it |
|---|---|---|
| What changes | Only the zero-result state | The matcher, in both copies (`server/match.py`, `app/src/kit/match.ts`) |
| Build | A near-name lookup on a zero result (`difflib` on the server, a small browser copy), shown as a "Did you mean" tap target | A fuzzy hit joins the ranking and the FTS candidate step. No first hit the case table pins may change. It must stay fast per keystroke over about 3,500 cards |
| Risk | Low: it draws only on a zero result | Real: a short query can fuzz into a wrong card, and a typo can show a different card with no sign |
| Cost | One small lane and one lean review | Two or three times that, an adversarial review, likely a second round |

Recommended: Suggest. It keeps D271's exact rule and adds a separate hint.

**Outcome at risk.** One retype per typo.

**Closes when.** The owner picks an option.
