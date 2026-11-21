# p-ambient-further

**Tombstone slips, in more depth.** A paper slip takes the place of every pulled card. Its torn-off stub travels with the card to packing, and the next re-capture removes the slips and fills the gaps.

**1. Core loop**
1. Orders import, and each sold line resolves to one card with its box, section and position.
2. The printer prints one strip per card in walk order, then a footer saying how many slips were printed.
3. The Fulfiller tears off a strip, goes to the box and section printed on it, and finds the slot using the two neighbour cards.
4. They compare the card with its name and number on the strip, tear the strip at the dashed line, and leave the tall half in the slot with its black band standing above the cards.
5. The stub goes with the card to the packing pile. When packing, they match the stub's order number to the mailer and drop the stub in a tray.
6. The store marks the card "pulled, tombstone in slot" when the strip prints (see question 3).
7. Before a section is re-captured, they lift out every tombstone and scan each one's QR code with a USB scanner. One beep means it matches a shipped order. Two beeps means a mystery.
8. The re-capture records the section without the gaps, and the tombstones go in the recycling.

**2. States a person meets**
- **Normal slip:** both neighbours are where the strip says. Swap, tear, done.
- **A neighbour moved:** a neighbour's name does not match. They count positions from the nearest divider, compare the card's name and number before pulling, and tick the "neighbour off" box on the stub. That section goes to the front of the re-capture queue.
- **A return goes back:** they put the card directly in front of its tombstone and leave the tombstone in place. At re-capture, a card standing in front of its own tombstone counts as restored. Nobody touches a screen.
- **A mystery tombstone:** a slip whose QR code matches no open or shipped order. It goes to review with the photo of that slot. The system never guesses whether the card left the house.
- **A cancelled order:** a "CANCEL #1234" strip prints with the same neighbour lines. If the card was pulled, it goes back in front of the tombstone, which is the same flow as a return. If it was never pulled, they bin both strips.
- **A slab:** the strip says SLAB and the last 4 digits of the cert number, which they compare before pulling. A slab needs no tombstone if it lives in its own box (see question 2).

**3. The strip on 58 mm paper (about 32 characters a line), top to bottom**
```
████████████████████████████████   black band, stands above the cards
SOLD - LEAVE IN SLOT
BOX 3  SEC 7  (TDR 150-199)
POS 42 of 118
before: Mossling 196/165
after : Pebblet 198/165
[ QR code: tombstone id ]
#1234-2
- - - - - - - tear here - - - - -
ORDER #1234   card 2 of 3
Cinderwyrm ex 197/165  NM
$4.25            [ ] neighbour off
[ dithered thumbnail, 30 mm ]
```
The tall half is about 100 mm, so it stands about 12 mm above 88 mm cards.

**4. Smallest first version**
- The first version prints text and a QR code only, with no thumbnail. That is one strip per sold card, printed after each order import.
- The store marks a card pulled when its strip prints, and a cancel strip reverses that.
- A tombstone is cleared only by hand before a re-capture, using the USB scanner's beeps. The rig does not need to recognise tombstones yet.
- Hardware is about $60: a 58 mm USB thermal printer and a USB QR scanner.
- Returns, a "neighbour off" tick that the store reads, and slabs wait for the second version.

**5. One measure**
Count positions that are off at re-capture, per 100 cards pulled since the section's last capture. Measure it once before tombstones as a baseline, then at each re-capture after. They work if the number falls.

**6. Owner questions**
1. Is a stored position a count from the divider, or a fixed capture order? If it is a fixed order, tombstones protect less and the neighbour names do most of the work.
2. Do slabs and valuable cards sit inside long-box sections, or in their own box?
3. Should a card count as pulled when its strip prints, or when its stub is scanned at packing? I recommend at print, with cancel strips, because it adds no step for the Fulfiller.

I still read no file. Whether positions are stored as a count from the divider is unknown, so question 1 decides how much this direction is worth.
