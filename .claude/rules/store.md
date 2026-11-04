---
paths:
  - "store/**"
---

# The store

- **The store of record is one SQLite file** (D88, SQLite and one transaction per write). `inventory.json` is
  legacy and read by nothing.
- **No automatic sectioning** (D10, inventory model). A divider is put in with `S` on the capture screen
  (`store/master.py:open_section`, inside the store lock).
- **A box is addressed by name, and names are unique** (D20, a box is an object). `Box.bid` is a never-reused
  index drawn on no screen (D145, a box has an index nobody sees). A run records `bid`, never the name (D56, a run names the drawer).
