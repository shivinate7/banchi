## DEBT-send-bar-zero-runs-or-load-fail — the send bar draws, then disappears, with zero runs or a failed load

**With zero runs, or a failed worklist load, the pending send bar draws and then disappears.** `Pricing.tsx` renders the bar only while `barLoading || loaded.length > 0` holds. Once the load ends with nothing loaded, the bar leaves the layout.

- **Result:** the bar leaves the layout after it has drawn. D313 forbids a move the person did not make (nothing on screen moves unless the person moved it).
- **Not fixed because** no spec covers this path. There is no written state for the bar to meet, so no build target exists.
- **Closes when** a spec states what the bar shows with zero runs and on a failed worklist load, and a test asserts that state.
- **Points to** D277 (Pricing lists all rows; the slim bar's three tiles), D313 (nothing on screen moves unless the person moved it).

**Outcome at risk.** The send bar has no stated state on two paths. A bar that draws and vanishes passes every check, because no spec says it is wrong.
