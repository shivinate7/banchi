## DEBT86 — Capabilities written twice that have not drifted yet

**A whole-repo sweep found capabilities with more than one implementation whose copies still agree.** The hard rule "one home per capability" covers them. The ten copies that had already drifted are fixed separately. These are next.

- **Server:**
  - Position label: `capture_server._Places.of` and `pipeline_routes._position_label`.
  - On-hand count: about 9 inline walks beside `master.Inventory.copies_on_hand`.
  - Transport: `tcg_export` and `order_transport` each define `_cookie`, `_agent`, `_open`, `_check_status` and `_NoRedirect`.
  - Box parsing: `_require_box` and `_require_to_box`, and `codes_routes._box_of`, which has no check for a box below 1.
  - Clock: `send_routes._now`, `_iso` and `_parse` beside `pipeline_routes._now_iso`.
  - SKU cell: the read `str(row.get(SKU_COLUMN) or "").strip()` appears 12 times.
  - Numbers: `capture_server._number_compare_key` beside `identity_binding._read_number_key`. A hand `zfill(3)` sits beside `join_key`.
- **Pipeline:**
  - `pipeline/setnames.py` `fold` is a verbatim copy of `pipeline/join.py` `normalize_set`.
  - `pricearchive.CANCELED_STATUS` repeats `store/orders.py` `TERMINAL_STATUSES`.
  - `sku_name_contradictions` tests the literal "sold" where `master.SOLD` exists.
- **Identify:** `geometry.crop.MAX_REGION_EDGE` and `identify.images.MAX_EDGE` are both 1568. `SIDECAR_SUFFIX` is defined in `identify/sidecar.py` and again in `server/capture_server.py`.
- **App:**
  - Percent formats in PriceMovers, PriceTrend and Revenue.
  - About 40 bare `toLocaleString()` calls beside the kit's fixed 'en-US'.
  - A hand-rolled `<details>` at 8 sites, because the kit has no disclosure.
- **Not fixed because** none gives a wrong answer today, and the drifted copies came first.
- **Closes when** each item calls its one home, or carries a written reason in the `capability homes` registry.

**Outcome at risk.** The next change to one copy leaves the other behind. That is how the free reader came to refuse 263 cards.
