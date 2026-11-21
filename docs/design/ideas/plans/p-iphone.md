# p-iphone

**1. Lock-Screen Pick Walk**
**The idea:** When an order arrives, the Fulfiller's phone shows a Live Activity on the lock screen with the next card to pull: box, section and position. They hold the phone in one hand and walk the dividers with the other. The camera then checks the pulled card, with one buzz for right and two for wrong.
**Who it helps:** The Fulfiller, and the owner, who no longer gets asked "which one is it?"
**Why now:** A busy day has 11 orders and a peak day has 39, spread over 6 boxes of up to 732 cards. One mispick means a refund, bad feedback and a lost card, and most cards earn too little to absorb that.
**Rough shape:**
- A notification says "3 orders, 7 cards, about 6 minutes". The Fulfiller taps Start, and the lock screen shows "Box 4, section 11, about 38th card".
- The walk is ordered by box and section, so they never go back to a box they have finished.
- They hold the card to the camera: one buzz means bag it, two buzzes means it is the wrong printing, with a side-by-side photo.
- A "put back" mode does the same thing in reverse for cancelled orders and returns.
**Risk:** If the camera check is slower than reading the card, the Fulfiller will stop using it.

**2. Card-Show Pocket Verdict**
**The idea:** At a card show, a shop or a friend's binder, the owner points the phone at a card and gets an instant verdict from their own data. It shows how many they already has, how fast that card sells for him, what it really fetches, and a buy-under price. It answers "should I buy this for my store?", which a price app does not.
**Who it helps:** The owner, when buying stock.
**Why now:** With 3,600 cards and sales history behind them, the store knows its own sell-through. That knowledge is stuck on a Mac at home when the decision happens at a folding table.
**Rough shape:**
- Before leaving, they syncs an offline snapshot of their own stock, sales speed and prices to the phone.
- They points the camera at a card and sees a large verdict, BUY UNDER $X or PASS, with "you have 4, sold 1 in 90 days" underneath.
- They taps to log a buy, and the phone builds a running "bought today" list for the next capture run.
- A slab mode reads the grade and certificate label and compares against graded sales, not raw-card prices.
**Risk:** The card has to be recognised on the phone without the paid identify step, or one weekend at a show runs up the bill.

**3. Price Calls on the Lock Screen**
**The idea:** The owner decides prices, but only a few decisions matter. Those few reach him as notifications they can answer with a tap: a slab's market price jumps 30%, a high-value card sells twice in a week, or a listing has been undercut. They answers with Raise to $X, Hold or Look later, without opening anything.
**Who it helps:** The owner, wherever they is.
**Why now:** Most cards are worth under a few dollars, and bulk rules should price them with no attention. The handful of costly cards and slabs are where a late reaction loses real money, and the owner is often away from the Mac when the market moves.
**Rough shape:**
- Each notification carries one decision, with its price chart and a recent sale, and is answered by long-pressing it.
- They sets the alert threshold in dollars at risk, not by card, so cheap cards never trigger an alert.
- A widget shows "2 calls waiting" and nothing else.
- Each answer queues a listing change for the next upload, and each queued change can be undone.
**Risk:** Too many alerts teach him to swipe them all away, so the threshold must be strict from day one.

**Bet:** Build the Lock-Screen Pick Walk first. It runs every day, it serves the one person who cannot fall back on the desk screens, and it catches mispicks before they reach a buyer.
