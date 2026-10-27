# D320 — My Slabs reads Card Ladder with the owner's own login

Kind: build
Plan: docs/specs/my-slabs.md#build-plan (macOS)

**The owner ruled it.** Banchi gets a My Slabs screen. The owner types or uploads a slab's cert
and grader. Banchi reads that slab's value, sales and population from Card Ladder with the owner's
paid login, and keeps one snapshot per slab per day. `docs/specs/my-slabs.md` is the spec.

**The login is a token in `.env`, like the TCGplayer cookie.** Card Ladder signs in with Firebase.
The owner copies their Firebase refresh token into the gitignored `.env` as
`CARDLADDER_REFRESH_TOKEN`. The server exchanges it for a one-hour ID token at Google's token
endpoint and sends that token with each call. No refusal, log line or screen prints the token,
only its key's name. This is the same shape as `TCGPLAYER_STORE_COOKIE` (D216, the history host
blocks this project's agent).

**The reads are paced and scoped.** Banchi keeps the reads at a person's pace (the spec's pacing
section) and reads only the owner's own slabs.

**The reads stay inside these bounds.**

- Banchi calls only the read callables that the spec lists, through one allow list. It never
  calls a callable that writes, such as `httpbuildcollectioncard`, and never writes the owner's
  Card Ladder collection.
- Banchi never calls `search.cardladder.com`.
- A rate-limit answer stops the sweep for that day. Banchi never retries around it.
- Card Ladder calls go through D319's home with idempotent=False, so a 429 is never retried.

**No guessed price.** A slab with no sale at its grade shows "no sales", never a number. The
slab's value is Card Ladder's estimate, trusted only by the spec's rules (section 4.3). Where
Card Ladder gives two values for one slab, the screen shows both, each with its source.

**Why.** Card Ladder's own screens read these values for any member, Riftbound included. Parse's
public Card Ladder API sees only public data and calls Riftbound untracked. The owner's login sees
sales, population and grade ladders that the public pages hold back. A tool built here is checked
against Card Ladder's own screens, not trusted from a vendor.

**What it protects.** The owner knows each slab's current value and how it moves, with every
number traced to a sale.

**Reopen when** Card Ladder rate-limits at a person's pace, or offers the owner a supported API.

**Three checks hold the bounds.** The callable allow list is one constant,
`cardladder.ALLOWED_CALLABLES`, that the client reads. `scripts/cardladder-selftest.py` refuses any
request to `search.cardladder.com`. `app/tests/slabs.spec.ts` proves that a slab with no sale
renders "No sales".
