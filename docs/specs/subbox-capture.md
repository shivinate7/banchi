# Sub-box capture: a picked section fills like a sub-box

**Status: SPECIFIED. Lane A (store, server, harness, records) is being built on
`ux/subbox-store`. Lane B (the Capture screen) and Lane C (the Move-to-box section choice) are
NOT BUILT.** Written 2026-09-26 from the plan the owner ruled on the same day. The decision
entry has the slug `sections-are-sub-boxes`.

## 0. The ask, in the owner's words

```
if i am in section 1, and i am capturing away, then section 1 is continuing to expand, if i am
selecting section 2, then i am capturing that fills in section 2, kinda like a subbox
```

The owner's rulings on the plan's three questions are in section 9.

## 1. Wire contract

Lanes B and C build against this. The client names a section by its **divider key**, a
string. The store chooses the position. No request carries an index or an order key.

A divider key is the string that `store/master.py:divider_key` writes. A whole-number key
reads `"31"`. A fractional key reads as Python's `repr`, such as `"5.0009765625"`. Compare
keys as strings. Never parse one and never compose one.

### 1.1 `GET /boxes`

Each `sections_detail[]` item gets one new field.

| Field | Type | Meaning |
|---|---|---|
| `div` | string | The divider key of this section. Section 1 of a box with no declared dividers has `"1"`, or the lowest card key when a card was placed in front of card 1. |

### 1.2 `POST /capture`

| Field | Where | Type | Meaning |
|---|---|---|---|
| `section` | body, optional | string | The divider key of the section to capture into. Missing or `null`: the capture works as before, at the back of the box. |
| `section_div` | response | string or null | The divider key of the section the card went into, read after the write. It is correct after a re-space. It is null only for a pooled card, which has no section. |

Each refusal writes nothing, uses no index and stores no photograph.

| Status | Code | When |
|---|---|---|
| 409 | `section_gone` | The box has no section with that divider key. Read `GET /boxes` again. |
| 400 | `section_invalid` | `section` is not a string. |

A replay of a `capture_id` that is already recorded answers 200 with the first card. It
ignores `section`.

### 1.3 `POST /boxes/<box>/sections` (S)

The body is `{}` or `{"after": "<div>"}`.

- With no `after`, or with `after` naming the last section, S works as before. The divider
  goes in front of the next card at the back of the box.
- With `after` naming a section that is not the last, the owner's Q1 ruling applies. One new
  divider goes directly behind the last card of that section. It stands in front of the next
  section's divider. No card key changes. The sections after it move up one number. Their
  card numbers stay the same.

The response is the box row, as before. The new section is the one directly after the
`after` section in `sections_detail`. Its `div` is the key to capture into next.

| Status | Code | When |
|---|---|---|
| 409 | `section_empty` | The named section has no card record in it yet (as before, for the last section). |
| 409 | `section_gone` | The box has no section with that divider key. |
| 400 | `section_invalid` | `after` is not a string. |

### 1.4 `DELETE /boxes/<box>/sections?div=<div>` (U after S)

- With no `div`, it works as before. It removes the last divider if no card on hand stands
  behind it.
- With `div`, it removes that one divider and no other. It refuses the first divider. It
  refuses a section that holds a card on hand. A departed record in the section does not hold
  it.

| Status | Code | When |
|---|---|---|
| 400 | `sections_invalid` | The first section, or a section with a card on hand (as before). |
| 409 | `section_gone` | The box has no section with that divider key. |

### 1.5 The two Move-to-box routes

`POST /inventory/<box>/<index>/move` (one card) and `POST /inventory/<box>/move` (ticked cards,
or a whole box) take one more optional field.

| Field | Type | Meaning |
|---|---|---|
| `section` | string | A divider key of `to_box`. Each moved card goes to the tail of that section, in the order sent. It uses the same key rule as a capture. Missing: the card goes to the back of `to_box`, as before. |

| Status | Code | When |
|---|---|---|
| 409 | `section_gone` | `to_box` has no section with that divider key. Nothing moves. |
| 400 | `section_invalid` | `section` is not a string. |

The owner ruled that a move has no default destination. The screen enforces it (Lane C). It
sends `section` on every Move-to-box. The server keeps the old back-of-box answer for a body
with no `section`, so older callers keep working. Section 7 gives the reason.

The Map's drag (`POST /boxes/<box>/cards/move`) does not change. It already names an exact
gap.
