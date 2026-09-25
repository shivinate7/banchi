#!/usr/bin/env python3
"""Extract real card data from the owner's store for the demo, without personal data."""

import json
import sqlite3
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

STORE_PATH = Path("/private/tmp/claude-501/-Users-shivinate-Developer-pkmnscan--claude-worktrees-jovial-banach-362f31/1ebdf2da-7dcc-4d76-b165-08d1e23ed9b4/scratchpad/livecopy/inventory/store.sqlite")
PRICES_PATH = Path("/private/tmp/claude-501/-Users-shivinate-Developer-pkmnscan--claude-worktrees-jovial-banach-362f31/1ebdf2da-7dcc-4d76-b165-08d1e23ed9b4/scratchpad/livecopy/inventory/prices.json")

def get_db_cards() -> List[dict]:
    """Extract all cards from the store."""
    conn = sqlite3.connect(STORE_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get all cards with their key info
    cur.execute("""
        SELECT DISTINCT
            c.box, c.idx, c.game, c.sku, c.name, c.number,
            c.condition, c.state, c.capture_id, c.set_name, c.rarity
        FROM cards c
        WHERE c.sku IS NOT NULL AND c.sku != ''
        ORDER BY c.box, c.idx
    """)

    cards = [dict(row) for row in cur.fetchall()]
    conn.close()
    return cards

def get_prices() -> Dict[str, dict]:
    """Load pricing corpus."""
    data = json.loads(PRICES_PATH.read_text())
    return data.get("skus", {})

def get_listings() -> Dict[str, dict]:
    """Get listing info from store."""
    conn = sqlite3.connect(STORE_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT key as sku, live, pushed FROM listings")
    listings = {row['sku']: dict(row) for row in cur.fetchall()}
    conn.close()
    return listings

def main():
    cards = get_db_cards()
    prices = get_prices()
    listings = get_listings()

    print(f"Total cards in store: {len(cards)}")
    print(f"Cards with SKUs: {len([c for c in cards if c['sku']])}")
    print(f"SKUs in pricing corpus: {len(prices)}")
    print(f"SKUs with listings: {len(listings)}")

    # Group by game and name for variant analysis
    by_game = defaultdict(list)
    by_sku = defaultdict(list)
    by_name_game = defaultdict(list)

    games = set()
    states = set()
    conditions = set()

    for card in cards:
        games.add(card['game'])
        states.add(card['state'])
        conditions.add(card['condition'])

        sku = card['sku']
        if sku:
            by_sku[sku].append(card)

        game = card['game']
        by_game[game].append(card)

        name = card.get('name')
        if name:
            by_name_game[(name, game)].append(card)

    print(f"\nGames: {sorted(games)}")
    print(f"States: {sorted(states)}")
    print(f"Conditions: {sorted(conditions)}")
    print(f"Card names with multiple SKUs: {sum(1 for v in by_name_game.values() if len(v) > 1)}")

    # Find our specific cases
    cases = {
        'unsent_no_price': [],
        'high_value': [],
        'foil_variants': [],
        'price_mismatch': [],
    }

    for sku, sku_cards in by_sku.items():
        price_info = prices.get(sku)
        listing = listings.get(sku, {})

        # Case 1: Unsent card with no market price
        is_sent = listing.get('pushed', 0) > 0
        market_price = listing.get('market')

        if not is_sent and not market_price and len(cases['unsent_no_price']) < 15:
            card = sku_cards[0]
            if card['state'] == 'identified':
                cases['unsent_no_price'].append({
                    'sku': sku,
                    'name': card['name'],
                    'number': card['number'],
                    'game': card['game'],
                    'condition': card['condition'],
                    'reason': 'unsent, no market'
                })

        # Case 2: Cards worth $5 or more
        if isinstance(price_info, str):
            try:
                price = float(price_info)
                if price >= 5.0 and len(cases['high_value']) < 20:
                    card = sku_cards[0]
                    cases['high_value'].append({
                        'sku': sku,
                        'name': card['name'],
                        'number': card['number'],
                        'game': card['game'],
                        'price': price,
                        'condition': card['condition'],
                    })
            except ValueError:
                pass

    # Case 3: Foil and normal variants (same name, different finishes)
    for (name, game), name_cards in by_name_game.items():
        if len(name_cards) >= 2:
            finishes = set()
            for c in name_cards:
                finish = c.get('metadata_finish')
                finishes.add(finish)

            if len(finishes) > 1 and len(cases['foil_variants']) < 10:
                # Found multiple finishes of the same card
                for c in name_cards[:2]:  # Take first 2
                    cases['foil_variants'].append({
                        'sku': c['sku'],
                        'name': c['name'],
                        'number': c['number'],
                        'game': c['game'],
                        'condition': c['condition'],
                    })
                if len(cases['foil_variants']) >= 10:
                    break

    # Print summary
    print(f"\nCases found:")
    print(f"  Unsent with no price: {len(cases['unsent_no_price'])}")
    print(f"  High value ($5+): {len(cases['high_value'])}")
    print(f"  Foil variants: {len(cases['foil_variants'])}")

    print(f"\nSample unsent cards:")
    for item in cases['unsent_no_price'][:3]:
        print(f"  {item['sku']}: {item['name']} - {item['game']}")

    print(f"\nSample high-value cards:")
    for item in cases['high_value'][:3]:
        print(f"  {item['sku']}: {item['name']} - ${item['price']}")

    # Export all data
    all_data = {
        'cases': cases,
        'summary': {
            'total_cards': len(cards),
            'cards_with_skus': len([c for c in cards if c['sku']]),
            'games': sorted(games),
            'states': sorted(states),
        }
    }

    output_path = Path('scripts/demo_data_extract.json')
    output_path.write_text(json.dumps(all_data, indent=2))
    print(f"\nData exported to {output_path}")

if __name__ == "__main__":
    main()
