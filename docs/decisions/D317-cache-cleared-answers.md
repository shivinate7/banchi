## D317 — The cache keeps a cleared answer

**The cache keeps one answer per position, and a cleared answer is permanent.** `store/cache.py` is the home. A cleared answer is a person's answer. No re-run, new prompt or changed photograph replaces it (`Cache.reusable`, `Cache.put`). A later read that disagrees is reported, and the person's answer stands. This keeps a machine from overwriting a person's work.

- **A position never carries one card's answer to another card.** The index can come back: undo hands the newest index to the next capture (D10, inventory model) and a box number is reused (D20, a box is an object). So every path that frees or reassigns a position acts on the entry. `server/capture_server._drop_from_stores` drops it for card delete, card remove and box delete, cleared or not. The mid-box shift in `do_remove_card` and the move routes re-key it with the card.
- **A cleared answer that does not parse goes to review.** It is never paid for again and never used.
- **Each entry records the game it was read under.** A card whose game changed is a miss. This keeps an answer read for one game from naming a card claimed in another (D21, game is a per-card claim).
- **The judge is `cli/cmd_identify.cached_refusal`.** An entry with no recorded game is judged by its shape and stays usable. A cleared entry of another game goes to Review as `cleared_answer_unreadable` and is not paid. A reattached answer records the game its batch was sent under (the manifest's `sent_games`).
- **Not built.** Nothing sets `cleared_by_human` on a cache entry. The review route sets it on the queue entry. `store/cache._parse_entry` returns None for a record that does not construct, so the card is read again and paid for. Nothing reads the rows that `Rows` skips for the cache.
