#!/usr/bin/env python3
"""Extract real card facts (no personal data) for demo supplement.

Extracts names, sets, numbers, rarities, SKUs, market prices, and sale patterns.
Creates a JSON file of real card data the seed can optionally use.
"""

import json
import sqlite3
from pathlib import Path
from collections import defaultdict
from decimal import Decimal

STORE_PATH = Path("/private/tmp/claude-501/-Users-shivinate-Developer-pkmnscan--claude-worktrees-jovial-banach-362f31/1ebdf2da-7dcc-4d76-b165-08d1e23ed9b4/scratchpad/livecopy/inventory/store.sqlite")

def get_all_cards() -> list:
    """Get all unique card SKUs with their card facts."""
    conn = sqlite3.connect(STORE_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get one card per SKU, with aggregated state info
    cur.execute("""
        SELECT
            c.sku,
            c.name,
            c.number,
            c.game,
            c.set_name,
            c.rarity,
            c.condition,
            COUNT(CASE WHEN c.state = 'sold' THEN 1 END) as sold_count,
            COUNT(CASE WHEN c.state = 'identified' THEN 1 END) as on_hand_count,
            GROUP_CONCAT(DISTINCT c.rarity) as rarities,
            GROUP_CONCAT(DISTINCT c.condition) as conditions
        FROM cards c
        WHERE c.sku IS NOT NULL AND c.sku != ''
        GROUP BY c.sku, c.condition
        ORDER BY c.sku
    """)

    all_cards = []
    for row in cur.fetchall():
        card = dict(row)
        # Get market price from skus table
        cur2 = conn.cursor()
        cur2.execute("SELECT payload FROM skus WHERE key = ?", (card['sku'],))
        sku_row = cur2.fetchone()

        market_price = None
        if sku_row and sku_row[0]:
            try:
                payload = json.loads(sku_row[0])
                if 'raw' in payload and 'TCG Market Price' in payload['raw']:
                    price_str = payload['raw']['TCG Market Price']
                    try:
                        market_price = float(price_str)
                    except ValueError:
                        pass
            except:
                pass

        card['market_price'] = market_price
        all_cards.append(card)

    conn.close()
    return all_cards

def main():
    cards = get_all_cards()

    print(f"Total unique SKUs: {len(cards)}")

    # Categorize cards
    unsent_no_price = []
    high_value = []
    multi_condition = []
    sold_cards = []

    conn = sqlite3.connect(STORE_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get listing info
    cur.execute("SELECT key as sku, live, pushed FROM listings")
    listings = {row['sku']: dict(row) for row in cur.fetchall()}
    conn.close()

    for card in cards:
        sku = card['sku']
        listing = listings.get(sku, {})
        is_sent = listing.get('pushed', 0) > 0
        market = card.get('market_price')

        # Case 1: Unsent with no market price
        if not is_sent and not market and len(unsent_no_price) < 15:
            unsent_no_price.append(card)

        # Case 2: High value ($5+)
        if market and market >= 5.0 and len(high_value) < 15:
            high_value.append(card)

        # Case 3: Multiple conditions (potential foil/normal variants)
        if card.get('conditions') and ',' in (card.get('conditions') or ''):
            if len(multi_condition) < 15:
                multi_condition.append(card)

        # Case 4: Cards that have sold
        if card.get('sold_count', 0) > 0 and len(sold_cards) < 20:
            sold_cards.append(card)

    print(f"  Unsent with no price: {len(unsent_no_price)}")
    print(f"  High value ($5+): {len(high_value)}")
    print(f"  Multiple conditions: {len(multi_condition)}")
    print(f"  With sales: {len(sold_cards)}")

    # Print samples
    print("\nSample unsent cards:")
    for card in unsent_no_price[:3]:
        print(f"  {card['sku']}: {card['name']} - {card['game']}")

    print("\nSample high-value cards:")
    for card in high_value[:5]:
        print(f"  {card['sku']}: {card['name']} - ${card['market_price']}")

    print("\nSample multi-condition cards:")
    for card in multi_condition[:3]:
        print(f"  {card['sku']}: {card['name']} - {card['conditions']}")

    # Create export: real card facts without personal data
    export_data = {
        'extracted_at': '2026-09-25',
        'description': 'Real card facts from owner store (no personal data)',
        'cases': {
            'unsent_no_price': unsent_no_price[:15],
            'high_value': high_value[:15],
            'multi_condition': multi_condition[:15],
            'with_sales': sold_cards[:20],
        },
        'summary': {
            'total_skus': len(cards),
            'games': list(set(c['game'] for c in cards)),
            'total_on_hand': sum(c.get('on_hand_count', 0) for c in cards),
            'total_sold': sum(c.get('sold_count', 0) for c in cards),
        }
    }

    output = Path('scripts/real_card_facts.json')
    output.write_text(json.dumps(export_data, indent=2, default=str))
    print(f"\nExported to {output}")

if __name__ == "__main__":
    main()
