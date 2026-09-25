#!/usr/bin/env python3
"""Extract comprehensive card facts for demo - 150-300 real cards with test cases.

Extracts real card data (names, sets, numbers, rarities, SKUs, market prices, sales)
without personal data. Focuses on finding cases: high-value, unsent, multi-condition,
and real sales data.
"""

import json
import sqlite3
from pathlib import Path
from collections import defaultdict
from datetime import datetime

STORE_PATH = Path("/private/tmp/claude-501/-Users-shivinate-Developer-pkmnscan--claude-worktrees-jovial-banach-362f31/1ebdf2da-7dcc-4d76-b165-08d1e23ed9b4/scratchpad/livecopy/inventory/store.sqlite")

def main():
    conn = sqlite3.connect(STORE_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get all SKUs with their card data
    cur.execute("""
        SELECT DISTINCT
            c.sku,
            c.name,
            c.number,
            c.game,
            c.set_name,
            c.rarity,
            c.condition,
            c.captured_at,
            c.state_at,
            COUNT(CASE WHEN c2.state = 'sold' THEN 1 END) as sold_count,
            COUNT(CASE WHEN c2.state = 'identified' THEN 1 END) as on_hand_count
        FROM cards c
        LEFT JOIN cards c2 ON c.sku = c2.sku
        WHERE c.sku IS NOT NULL AND c.sku != ''
        GROUP BY c.sku, c.condition
        ORDER BY c.sku
    """)

    all_records = {}
    for row in cur.fetchall():
        sku = row['sku']
        if sku not in all_records:
            all_records[sku] = dict(row)

    # Get market prices and listing info
    cur.execute("SELECT key as sku, live, pushed FROM listings")
    listings = {row['sku']: dict(row) for row in cur.fetchall()}

    cur.execute("SELECT key as sku, payload FROM skus")
    market_prices = {}
    for row in cur.fetchall():
        try:
            if row['payload']:
                payload = json.loads(row['payload'])
                if 'raw' in payload and 'TCG Market Price' in payload['raw']:
                    try:
                        price = float(payload['raw']['TCG Market Price'])
                        market_prices[row['sku']] = price
                    except:
                        pass
        except:
            pass

    # Load prices.json for typed prices
    prices_path = Path("/private/tmp/claude-501/-Users-shivinate-Developer-pkmnscan--claude-worktrees-jovial-banach-362f31/1ebdf2da-7dcc-4d76-b165-08d1e23ed9b4/scratchpad/livecopy/inventory/prices.json")
    prices_data = json.loads(prices_path.read_text())
    typed_prices = prices_data.get('skus', {})

    conn.close()

    # Categorize cards for test cases
    cases = {
        'unsent_no_price': [],
        'high_value_5plus': [],
        'price_mismatch_25pct': [],
        'multi_condition': [],
        'with_sales': [],
        'general': []
    }

    seen_skus = set()

    for sku, card in all_records.items():
        if sku in seen_skus:
            continue

        listing = listings.get(sku, {})
        is_sent = listing.get('pushed', 0) > 0
        market = market_prices.get(sku)
        typed = typed_prices.get(sku)

        # Case 1: Unsent with no market price
        if not is_sent and not market and len(cases['unsent_no_price']) < 5:
            cases['unsent_no_price'].append(card)
            seen_skus.add(sku)
            continue

        # Case 2: High value ($5+)
        if market and market >= 5.0 and len(cases['high_value_5plus']) < 15:
            cases['high_value_5plus'].append(card)
            seen_skus.add(sku)
            continue

        # Case 3: Price mismatch 25%+
        if market and isinstance(typed, str):
            try:
                typed_f = float(typed)
                pct_diff = abs(typed_f - market) / market * 100 if market > 0 else 0
                if pct_diff >= 25 and len(cases['price_mismatch_25pct']) < 5:
                    card['typed_price'] = typed_f
                    card['market_price'] = market
                    card['pct_diff'] = round(pct_diff, 1)
                    cases['price_mismatch_25pct'].append(card)
                    seen_skus.add(sku)
                    continue
            except ValueError:
                pass

        # Case 4: With sales history
        if card.get('sold_count', 0) > 0 and len(cases['with_sales']) < 30:
            card['market_price'] = market
            cases['with_sales'].append(card)
            seen_skus.add(sku)
            continue

        # General cards
        if len(cases['general']) < 200:
            card['market_price'] = market
            cases['general'].append(card)
            seen_skus.add(sku)

    # Find multi-condition cards from seen_skus
    cur = sqlite3.connect(STORE_PATH)
    cur.row_factory = sqlite3.Row
    cur2 = cur.cursor()

    for sku in list(seen_skus)[:100]:  # Check first 100
        cur2.execute("""
            SELECT DISTINCT c.name, c.number, c.game, c.set_name, c.condition, c.rarity, c.sku
            FROM cards c
            WHERE c.sku = ?
        """, (sku,))

        variants = cur2.fetchall()
        if len(variants) > 1:
            # Found foil and normal variant
            conditions_set = set(v['condition'] for v in variants)
            if len(conditions_set) > 1 and len(cases['multi_condition']) < 5:
                for v in variants[:2]:
                    card_dict = dict(v)
                    card_dict['market_price'] = market_prices.get(sku)
                    cases['multi_condition'].append(card_dict)
                    if len(cases['multi_condition']) >= 10:
                        break

    cur.close()

    # Prepare export
    all_cards = []
    for case_name, cards in cases.items():
        for card in cards:
            card['case'] = case_name
            all_cards.append(card)

    print(f"Extracted {len(all_cards)} total cards across cases:")
    for case_name, cards in cases.items():
        print(f"  {case_name}: {len(cards)}")

    output = Path('scripts/demo_cards_comprehensive.json')
    output.write_text(json.dumps({
        'cards': all_cards,
        'summary': {
            'total': len(all_cards),
            'by_case': {k: len(v) for k, v in cases.items()},
            'extracted_at': datetime.now().isoformat(),
        }
    }, indent=2, default=str))

    print(f"\nExported to {output}")

if __name__ == "__main__":
    main()
