import sys, os
R=sys.argv[1]; SH=sys.argv[2]
HOUSE=open(f"{R}/pull/pull-blind-1.md").read().split("## House rules")[1]
HOUSE="## House rules"+HOUSE
WEBDEV="## Device\ndesktop width: 1440. Then 820 (a tablet or narrow window). Light and dark themes. Pointer at 1440; touch at 820."
PHONEDEV="## Device\niPhone Duo, folded: size not written, draw at a typical modern iPhone size and say so. Then iPhone Duo, unfolded: size not written, draw at the unfolded size you choose and say so. Touch only. Follow skill `ios-apps`."
TAIL="- The owner will click through every concept: each press, sheet, state and step works in the page. Use made-up names and cards only. Drawings only: build nothing, open no pull request, commit and push after each pass to the branch `design-mock/{d}`."
S={
"pricing":dict(
 job="""The owner sells trading cards online and must set and send the price of every card they have for sale. They hold nothing; they sit at a desk. They must find out which prices need their eye, which are ready, and what will change when they send. Done looks like: every price they mean to send is sent, the ones they hold back are held on purpose, and they can see what went out.

Things the job handles:
- About 1,100 items for sale, each with a current price, a market price and a suggested price; one item may have several copies.
- On a typical day about 34 need the owner's eye, about 60 copies are ready to go, about 90 prices would move, and about 30 are held back by choice.
- Some items have no market price at all and must be priced by hand.
- Sending changes the live prices buyers see; the owner wants to know exactly what a send will do before it happens.""",
 screen="Pricing (route `#/pricing`, `app/src/Pricing.tsx`; run `make orient ARGS=app/src/Pricing.tsx`). Read docs/specs/pricing-suggest.md and docs/specs/stale-listings.md, docs/debts DEBT89, DEBT90, DEBT91, and the existing pricing mockups in docs/design/ (pricing-owed, pricing-send-notices, pricing-suggest).",
 shots="pricing-*.png", pains=["About 9 status lines (send bar, five tallies, movers, two 'no read has run' lines, markup, value line, 'readings not matched') come before row 1 of 1,110.","The page is ~122,000px tall at 820 and the send bar jumps (DEBT89-91).","'64 copies ready' here, '18 ready' on Home, '18 SKUs, 92 Live Copies' on the send button: one count, three units."],
 cover="the header and send bar, the row list with its filters, one row's detail and price history, holding back an item, the send review and its receipt, and the empty and done states.",
 dirs=["one question at a time: the screen opens on the next price that needs the owner, and the full table is a second view","a single send review: everything a send will change, shown as one diff the owner reads top to bottom before pressing"]),
"review":dict(
 job="""The owner photographs thousands of cards, and a reader names most of them. For the doubtful ones, the owner must answer which exact printing the card is, one card at a time, for hours, at a desk with a keyboard. They also start a paid reading of a batch of photos now and then, which costs money. Done looks like: every doubtful card has an answer, nothing was guessed, and the owner knows what each paid read cost and found.

Things the job handles:
- A batch is a box of 545 to 732 photos; 1 to 100 cards per sitting; about 46 sittings on record.
- A doubtful card has its photo and 2 to 8 candidate printings, each with its own image, set, number and market price.
- Reasons a card is doubtful: about 19 kinds (for example two printings look the same, the set symbol is unreadable).
- The paid read costs real money per card; the owner must see the cost before starting it.""",
 screen="Review (route `#/review`, `app/src/Review.tsx`; run `make orient ARGS=app/src/Review.tsx`), and its runs sheet with the Identify composer (RunsComposer, RunPanel). Read docs/specs/capture-app.md (review sections), docs/DESIGN.md section 'The review queue', docs/specs/term-audit.md items 3 and 8. The demo cannot show the question card: read the code for it.",
 shots="review-*.png", pains=["The one press that spends money is four layers deep: an unlabeled clock icon, a sheet of 46 runs (most read 'This run has no box on record. Written'), Identify, then a 3-step dialog.","'Hover a bar to see its steps' fails on touch.","The question card's four count labels name pipeline steps ('Waiting for a Paid Look', 'Not Looked at Yet'), not the owner's words."],
 cover="the question card with its candidates and keyboard flow, the counts header, the history of sittings, starting a paid read with its cost, a read in progress, and its result.",
 dirs=["keyboard-only speed: one card, one keystroke per answer, nothing on screen that the keys cannot reach","money in plain sight: the paid read is a first-class action on the first screen, with cost and expected yield up front"]),
"orders":dict(
 job="""The owner sees who is owed which cards and then walks the boxes to pick them. At a desk first, then standing at the shelf. They must find out which buyers are owed what, which cards are short, and the walking order through the boxes. Done looks like: every pickable card picked, each short card named, and each copy marked sold.

Things the job handles:
- About 74 open buyers (948 in all), 256 copies owed, 92 to pick over 18 sections on a busy run.
- A card may be owed 2 and have 3 on hand in different boxes; some are short; some can come from either of two printings.
- Each copy has a box, a section and a position number, and a photo.""",
 screen="Orders (route `#/orders`, `app/src/Orders.tsx`, its walk pane OrdersWalkPane/OrderPickPane; run `make orient ARGS=app/src/Orders.tsx`). Read docs/specs/order-flow.md, docs/specs/order-walk-plan.md, docs/specs/order-pipeline.md, decision D288 (repeated actions are labeled icons), and docs/design/orders-ship-to.",
 shots="orders-*.png and orders-walk-*.png", pains=["Sell is a bare $ glyph on each copy, its word only in a hover tooltip.","At 820 the rail is icons only.","92 picks over 18 sections carry '3 short' and '(either)' pills nobody explains."],
 cover="the buyer list, the walk with its sections, one pick, selling a copy, a short card, an either-printing card, and the done state.",
 dirs=["the walk as a checklist on paper: print-like, one line per pick, big tick targets","section-at-a-time: the screen shows only the section the owner stands in, with a mini-map of the rest"]),
"inventory":dict(
 job="""The owner needs to answer "where is this card, and how many do I have?" and then sell, retire or move one copy. At a desk or standing at the shelf. Done looks like: the card found, its spot known, and the change made with a way back.

Things the job handles:
- About 3,600 cards on hand in about 6 boxes of 545 to 732 cards, 9 to 22 sections each, with a position number.
- One product may have several copies in different boxes, each with its own photo and condition.
- About 40 boxes have been emptied or removed over time, with their records kept.
- Views the owner wants: a list to search, a picture of the boxes, and progress by card set.""",
 screen="Inventory (route `#/inventory`, `app/src/Inventory.tsx`, CardPane, CopiesPanel, CopyMapView; run `make orient ARGS=app/src/Inventory.tsx`). Read docs/specs/box-map.md, docs/specs/holdings-roster.md, docs/specs/master-set.md, docs/specs/card-detail.md, and docs/design/inventory-*.",
 shots="inventory-*.png, inventory-shelf-*.png, inventory-sets-*.png", pains=["Sell, retire and move are bare icons on each copy.","The box list scrolls inside a 4-row box.","The photo is a zoomed slice with the card's name cut off."],
 cover="search, the result list, the card pane with its copies, the map of boxes with the card lit, sell/retire/move with undo, and set progress.",
 dirs=["the physical shelf as the home screen: boxes drawn to scale, search lights up spots"]),
"counts":dict(
 job="""Several screens count the same open work: orders, cards owed, cards to pull, cards that cannot be found, prices ready to send. The owner must trust one number for each thing, wherever they look. Done looks like: one word and one unit per thing, the same on every screen, and each number explains itself on demand.""",
 screen="Cross-screen: the counts on Home (`app/src/Home.tsx`), Orders (`Orders.HEADLINE_LABELS`), Cards to Pull (`Fulfillment` totalWanted/shortfallCount) and Pricing. Read docs/specs/term-audit.md. Draw Home plus the headline strip of each of those screens with one shared vocabulary.",
 shots="home-*.png, orders-*.png, fulfillment-*.png, pricing-*.png", pains=["Home: 75, '256 owed, 164 unfilled'. Orders: 74 buyers, 92 to pick, 164 not in boxes. Cards to Pull: 74 Left, 176 unlocated. Pricing: '64 copies ready' vs '18 ready' on Home vs '18 SKUs, 92 Live Copies' on send.","Each counts a different thing under a different word, and no screen says which."],
 cover="Home and each screen's headline, a 'what does this count' popover, and a glossary view.", dirs=[]),
"capture":dict(
 job="""The owner sits at a rig: a camera looks down on a tray, and a card dispenser drops one card at a time onto it. Before a run they pick which storage box and which labelled section the cards are going into. Then every card is photographed as it lands, at about 1,300 an hour, while the owner's hands load the dispenser and watch for jams. Done looks like: every card photographed once, in the right box and section and order, with bad shots caught and redone at once, and the sitting closed.

Things the job handles:
- A box takes 545 to 732 cards in 9 to 22 sections; a section break is marked as cards flow.
- 802 cards in 37 minutes on a good sitting; a jam, a double drop or a blurred shot must be undone without losing the place.
- A quick free reader names most cards as they land; the owner only needs to know if something is wrong.
- The screen is a few steps away from the owner's eyes; hands are busy.""", screen="Capture (route `#/capture`, `app/src/Capture.tsx`; run `make orient ARGS=app/src/Capture.tsx`). The owner photographs each card as a dispenser drops it under a 4K camera, picking box and section first; 802 cards in 37 minutes. Read docs/specs/capture-app.md section 2, docs/specs/dispenser.md, docs/specs/subbox-capture.md, docs/specs/term-audit.md item 2.",
 shots="capture-*.png", pains=["Four panels, nine one-letter keys.","Words like 'Stack', 'Rig', 'Set Hint Needed', 'Background Match' and 'Tuning'.","The free reader has 11 names."],
 cover="setup (box, section), the live feed at pace, a section divider, undo, a jam or misread, and the end of a sitting.", dirs=["heads-up at pace: one glance from across the rig tells the owner it is fine"]),
}
PH={
"phone-find":dict(
 job="""The owner stands at the shelf with a phone and asks "where is this card, and how many do I have?" Then they sell, retire or move one copy right there. Sometimes they hold the card and want the phone to recognise it. Done looks like: the card found, its spot shown, the change made with a way back.

Things the job handles:
- About 3,600 cards in about 6 boxes of 545 to 732 cards, 9 to 22 labelled sections each, with a position number.
- One product may have several copies in different boxes, each with its own photo and condition.
- The records live on a Mac at home, reached over the home network; away from home it may be out of reach.""",
 screen="Inventory (`#/inventory`, CardPane, CopiesPanel, CopyMapView) moved to a native iPhone app. Read docs/specs/box-map.md, docs/specs/card-detail.md, docs/debts DEBT76 and DEBT77, docs/specs/lean-server.md section 7.",
 shots="inventory-*.png", pains=["Sell, retire and move are bare icons.","The box list scrolls inside a 4-row box.","The photo crops the card's name."],
 cover="search, scan a card in hand, result, card with copies, map of boxes, sell/retire/move with undo, and Mac out of reach.", dirs=[]),
"phone-slabs":dict(job="""The owner keeps a ledger of graded cards sealed in plastic cases, each with a label: grading company, grade and a certificate number. They add one by holding the case up to the phone, and they want to see what the whole ledger and each case are worth today. Done looks like: the case added with no typing, its value shown, and the ledger total current.

Things the job handles:
- Up to about 400 graded cases; about 4 grading companies; grades 1 to 10 with halves.
- Each case: card name, set, number, grade, certificate number, a photo, what was paid and today's value.
- The records live on a Mac at home, reached over the home network; away from home it may be out of reach.""", screen="Slabs (`#/slabs`, SlabSheet) as a native iPhone flow: add a graded slab by pointing the camera at its cert label, see the ledger and each slab's value. Read docs/specs/my-slabs.md and docs/specs/lean-server.md section 7 (a plain-http page loses the camera; a native app keeps it).",
 shots="slabs-*.png", pains=["Adding one means typing a cert number and picking a grader."],
 cover="the ledger, scanning a cert, the confirm sheet with grade and value, a failed scan, and a slab's detail.",
 dirs=["the camera is the home screen: open the app and it is already reading a cert"]),
}
def blind(name, s, n, phone=False):
    d=f"{name}-blind-{n}"
    t=f"Designer kind: blind\nDesigner: {d}\n\n## Job\n{s['job']}\n{TAIL.format(d=d)}\n\n{PHONEDEV if phone else WEBDEV}\n\n{HOUSE}"
    return d,t
def informed(name, s, kind, n, nb, direction=None, phone=False):
    d=f"{name}-{kind}-{n}"
    head=f"Designer kind: {kind}\nBlind designers: {nb}\nDesigner: {d}\n"+(f"Direction: {direction}\n" if direction else "")
    pains="\n".join(f"{i+1}. {p}" for i,p in enumerate(s['pains']))
    dev = ("## Device\niPhone Duo, folded first, then unfolded, each its own layout. Follow skill `ios-apps`, section Mockups: native controls, system font, safe areas, 44pt targets; run `python3 ~/.claude/lint/check_ios_mockup.py <mockup>` before you report. Never wait for or boot a simulator: read Apple's pages on the web and be directionally accurate. Map `--bn-*` colours onto a native look; light and dark."
           if phone else "## Device\n1440, then 820. Light and dark. `--bn-*` tokens only (docs/DESIGN.md).")
    body=f"""
## Screen
{s['screen']}
Live demo: https://shivinate7.github.io/banchi/ . Screenshots already taken in {SH}/: {s['shots']}. Read one section at a time.

## Pain points to fix, largest first (from an audit)
{pains}

## Cover
{s['cover']}

{dev}

## Deliver
Interactive HTML: each press, sheet, state and step works, with hash deep links per state, so the owner can click through and pick. Write docs/design/{d}.html and docs/design/{d}-notes.md, and print your designer kind{' and direction' if direction else ''} on the page. Load `frontend-design` first. Mockups only: the owner has not ruled on any of this, so build nothing, change no product code, open no pull request. Commit and push branch `design-mock/{d}` after each pass. The repo is public: made-up names and cards only, never a buyer name from the demo. Report in 20 lines or fewer: files, branch, and the one idea that matters most.
"""
    return d, head+body
plan={"pricing":"bid","review":"bid","orders":"bid","inventory":"bi","counts":"bi","capture":"bd","phone-find":"bi","phone-slabs":"bd"}
for name,code in plan.items():
    phone=name.startswith("phone")
    s=(PH if phone else S)[name]
    os.makedirs(f"{R}/{name}",exist_ok=True)
    nb=code.count("b")
    out=[]
    if "b" in code: out.append(blind(name,s,1,phone))
    if "i" in code: out.append(informed(name,s,"informed",1,nb,None,phone))
    for k,dr in enumerate([c for c in code if c=="d"]):
        out.append(informed(name,s,"directed",k+1,nb,s['dirs'][k],phone))
    for d,t in out:
        if nb==0 and "Blind designers: 0" in t:
            t=t.replace("Blind designers: 0","Blind designers: none, owner: \"literally churn mockups\" (this screen's blind designs come in a later wave)")
        open(f"{R}/{name}/{d}.md","w").write(t)
        print(f"{R}/{name}/{d}.md")
