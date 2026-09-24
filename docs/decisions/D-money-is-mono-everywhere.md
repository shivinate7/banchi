## D-money-is-mono-everywhere — Every dollar figure takes the mono face, and a check that reads the rendered page enforces it

**The owner's ruling, 2026-09-23.** The owner asked to see both options drawn before a choice.
After the pictures, the owner picked option A. Every dollar figure on every screen takes the
mono face through `.bn-money`. That includes a price inside an input and a figure inside a
chip. A check refuses a dollar figure drawn in any other face.

This confirms D221 (money stays mono) and fixes the premise it stood on. The record of the
review is `docs/reviews/ux-2026-09-23/`. The finding is UX-043.

### The premise that no longer holds

D221 says that Pricing's worklist, Revenue's totals and the front page "agree on the mono
face already". That was false when D221 was written, and nothing checked it.

### The evidence

The visual and coherence lenses measured each `$n.nn` text node with `getComputedStyle` at
1440 (VIS-04, COH-15). Sales uses `.bn-money`, JetBrains Mono. The Pricing market column uses
Inter 13px at 600. The Pricing price field uses Inter 16px at 700. The Shipping chips use Inter
11px at 600. The Review candidates use Manrope 18px at 800. The Kit stat uses Manrope 22px at
800. So one kind of number had four faces.

### What D221 protected, and what protects it now

D221 protects one outcome: a dollar figure reads as one kind of number on every screen. Its
ruling was sound. It failed because nothing read it. D221 argued the rule could not be
mechanized, because CSS alone cannot tell a dollar figure from a SKU. That is true for a
static reader of CSS. It is not true for a reader of the rendered page, which sees the text.

So the rule gets a reader of the rendered page. A browser check walks each route in the
populated fixtures. It finds every visible text node and every input value that holds a
dollar figure. It fails when the computed face of any of them is not the mono face. The
static half is the guards lane's rule: no `$` template with `.toFixed(` outside
`app/src/money.ts`.

### What changes on screen

`.bn-money` is the only way to draw money. The kit-data lane's `Money` primitive draws it, with
the `$` always present (UX-043). Pricing, Shipping, Review and the Kit move onto it. Dates,
names, counts and eyebrows leave the mono face (UX-087). Mono stays for SKUs, run ids, card
numbers, key caps and money.

### What is built, and what is still open

NOT BUILT. The kit-data lane builds the primitive. The text-checks lane builds the rendered-page
check, by the orchestrator's call, because that lane already reads rendered text.
CLAUDE.md's type paragraph carries a NOT MECHANIZED sentence about money. That sentence goes
when the check lands, in the same change.
