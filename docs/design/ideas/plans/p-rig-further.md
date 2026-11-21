# p-rig-further

**Section close-out at each divider**

The rig speaks only when a section needs the owner, and only at a divider, while that section is still in the tray. Everything below is invented from the brief; I read no code.

**1. The core loop, from the owner's view at the rig**
1. The owner feeds a section. Cards stack in the output tray in feed order, and the rig stays silent.
2. The divider passes. One soft tick confirms the rig counted it.
3. The verdict arrives within about a second, before the next card goes in:
   - Clean: nothing more happens, and the owner keeps feeding.
   - Flagged: a two-note chime, then the count spoken aloud ("two"). The feeder holds for the owner.
4. The owner looks at the screen once. Each flag shows its photo, the problem and the tray position ("31st from the top, face down").
5. The owner counts down the tray, pulls the card, fixes it and puts it back in the same slot. The owner taps "fixed", or re-feeds that card through the rig to replace its photo.
6. If a fix takes too long (a stuck sleeve, an unclear card), the owner taps "carry". The flag keeps its box, section and position, and feeding resumes.
7. The next section starts. Positions count from zero again, so any slip stays inside the section just closed.

**2. The rig screen states**
- **Clean section:** no screen change beyond a thin green line on the section list ("S7 · 58 ✓"). No sound beyond the divider tick.
- **Section with 2 to fix:** two photo tiles, each with its problem (face down, blurred, not a card) and its tray position. Buttons: Fixed, Re-feed, Carry. The feeder resumes when both are cleared.
- **Double-feed inside a section:** a separate tile. "Card 23 may hide a second card. Positions after 23 may be off by one." The fix is to lift cards 23 and 24, feed the hidden one alone, and let the rig shift the later positions by one. If carried, every position after 23 is marked "unsure", not just card 23.
- **Missing divider:** "Section 5 ran long: 118 cards. The set changed at card 61." The owner can put a divider at tray position 61 and tap Split, or tap "One section" if the long run is deliberate.
- **Flag carried into the next session:** the first screen before feeding says "1 open from last time: Box 3, section 7, card 31, face down." The card is now in the box, not the tray, so the fix means pulling it there. The owner can also leave it for later. It never disappears without a tap.
- **End-of-box summary:** sections, cards, flags fixed at a divider, flags carried, and one plain verdict: "Positions trusted: 21 of 22 sections."

**3. What the owner hears and sees without looking up**
- Hears: a tick per divider, the two-note chime plus the spoken count for flags, and a low buzz when the rig pauses itself mid-section on a double-feed.
- Sees: the whole screen edge changes colour, readable from the side. Green fades within a second, amber holds until the flags are cleared, red means paused mid-section.
- Feels: the feeder stops on its own when a flag is open, so the owner cannot feed past a problem by habit.

**4. The smallest first version worth shipping**
- The divider verdict built only from free checks the rig can run locally: a card back showing, a blurred or empty frame, a likely double-feed, and a section much longer than usual (the missing divider).
- Tray position for each flag, Fixed and Carry, and the carried list shown at the next session's start.
- Left out of the first version: checking the set-and-number order, the spoken count (the chime alone is enough), and the end-of-box summary beyond a single line.

**5. One measure that says it worked**
Minutes of cleanup after the session per hour of capture, measured as time spent fixing positions or photos after the rig stops. The target is near zero. A later check is the position errors the Fulfiller meets per 100 picks.

**6. Questions only the owner can answer**
1. What decides where a divider goes: one per set, a fixed card count, or a box layout? This decides whether a set change with no divider counts as an error.
2. In the tray, is the first card fed at the bottom or the top, and is the owner willing to pull a card from the tray mid-session? If not, every flag is carried and the loop is a different product.
3. Should an open flag stop the feeder, or only chime? Stopping protects the positions but costs flow on a fast run.
