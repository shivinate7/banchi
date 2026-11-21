# p-seasons-further

# Season Clock, in more depth

**1. The core loop**

*How events get onto the clock*
- **Hand-entered.** The owner types a name, a date or date range, a kind (release, prerelease, rotation, tournament, holiday, school break) and the sets it touches. That takes about 30 seconds, one or two times a month.
- **Learned.** The clock scans past order files for days well above the normal level. For each one it asks: "Nov 8–17 ran at 3x normal, mostly set X. What was it?" One answer turns that spike into a labelled past event.
- **Imported.** If the owner keeps a release list somewhere, it can be pasted in as a batch. This is optional, and the clock never depends on it.

*How the guess is made*
- The guess comes from the past events of the same kind: how much orders rose, for how many days, and which sets and boxes they came from. With one past event, the guess is "last time". With several, it is a range.

*The owner's view, by stage*
- **A week before:** a prep card with the expected orders per day as a range, the dates, the sets likely to sell, the supplies to have on hand, and the extra Fulfiller sessions.
- **On the day:** expected orders next to orders so far, as of the last order import.
- **After:** guess against what happened, side by side. The owner gives one tap, "useful" or "missed", and the event joins the history.

**2. The screen's states**
- **Quiet stretch.** "Nothing expected for 3 weeks. Normal: about 3 orders a day." The quiet weeks are a hint to run the capture rig.
- **Event a week out.** The prep card leads, with dates, the range, supply counts, Fulfiller days and the sets to watch.
- **First event of its kind, no history.** Labelled "No past event like this." It borrows the closest kind with a wide band, or says "no guess, watch this one." It never shows a single number.
- **Surprise spike.** Orders run above the band with no event behind them. "Today: 14 orders, about 5 expected. Is something happening?" The owner can name it, which adds it to the history.
- **After the event.** Two lines, guess and actual, over the event's days. It shows which sets sold more or less than guessed, plus the "useful" or "missed" tap.
- **Two events at once.** For example, a holiday that overlaps a release. Both markers show, and the guess says it cannot separate them.

**3. What the Fulfiller sees**

Plain sentences only, like these:
- "Busy days ahead: Friday to Sunday. Expect about 20 orders a day."
- "Have 60 mailers, 200 sleeves and 2 rolls of tape ready by Thursday."
- "Most cards will come from boxes 3 and 5."
- In quiet weeks: "Normal week. Nothing to prepare."

They see no charts, no ranges and no event history.

**4. The smallest first version worth shipping**
- Hand-entered events only.
- A chart of orders per day from past order files, with the events marked on it.
- The guess is just "last time an event of this kind happened": its daily orders, shown next to the coming dates.
- The after-event comparison.
- The Fulfiller's one-line message.

Spike learning, import, supply counts and box hints come later.

**5. One measure that says it worked**

Of the days with 10 or more orders, the share that had a prep card at least 5 days before. Today that share is zero. The goal is most of them.

**6. Questions only the owner can answer**
- How far back do the saved order files go, and do they cover at least one past release season? If they do not, the first version starts with no history at all.
- Will you enter one or two events a month by hand, or does the clock only work for you if events arrive on their own?
- Are the Fulfiller's hours fixed, or can they move? If they are fixed, the Fulfiller's view drops "extra sessions" and only says what to prepare.
