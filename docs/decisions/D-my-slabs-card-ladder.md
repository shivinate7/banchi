## D-my-slabs-card-ladder — My Slabs reads Card Ladder with the owner's own login

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

**The owner accepts the ban risk.** These reads are automation of the owner's own account. Card
Ladder can close that account for it. The owner accepts that risk. Banchi keeps the reads at a
person's pace (the spec's pacing section) and reads only the owner's own slabs.

**The reads stay inside these bounds.**

- Banchi calls only the read callables that the spec lists, through one allow list. It never
  calls a callable that writes, such as `httpbuildcollectioncard`, and never writes the owner's
  Card Ladder collection.
- Banchi never calls `search.cardladder.com`. That host answers a Cloudflare challenge, and
  Banchi never solves or avoids a bot check, a CAPTCHA or an app check.
- A rate-limit answer stops the sweep for that day. Banchi never retries around it.

**No guessed price.** A slab with no sale at its grade shows "no sales", never a number. Card
Ladder fills such a slab with its purchase cost moved by a market index. That number is not a
price, and Banchi never shows it as one. Where Card Ladder gives two values for one slab, the
screen shows both, each with its source. Banchi does not pick one.

**Why.** Card Ladder's own screens read these values for any member, Riftbound included. Parse's
public Card Ladder API sees only public data and calls Riftbound untracked. The owner's login sees
sales, population and grade ladders that the public pages hold back. A tool built here is checked
against Card Ladder's own screens, not trusted from a vendor.

**What it protects.** The owner knows each slab's current value and how it moves, with every
number traced to a sale.

**Reopen when** Card Ladder enforces an app check or moves these callables behind a bot check.
Also reopen when it rate-limits at a person's pace, or offers the owner a supported API.

**NOT MECHANIZED until built.** The build lane adds three checks. The callable allow list is one
constant that the client reads. A test refuses any request to `search.cardladder.com`. A test
proves that a slab with no sale renders "no sales". A machine cannot see the ban risk.
