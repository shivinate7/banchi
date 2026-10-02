/* WHICH MARK PALETTE A CARD'S RARITY WEARS: the one table (game, rarity, palette), read by the
 * neighbour row's mark (`PlaceNeighbors`'s `mark`) and by nothing else.
 *
 * THE RARITY NAMES ARE `pipeline/games.py`'s, VERBATIM, and `make docs-audit`'s `game vocabulary`
 * row fails when a game's `rarities` entry has no line here (or a line here names no rarity), so
 * a rarity the registry gains cannot go without a color. The palettes are `markPalettes.ts`'s
 * (docs/specs/logo.md section 9). Nothing here names a hex.
 *
 * RIFTBOUND wears its gem colors: Common white gold, Uncommon mint, Rare rose gold, Epic orange,
 * Showcase yellow gold; Promo is not a rung and stays bluesteel.
 *
 * POKEMON and ONE PIECE are ladders, plainest to richest in `games.py`'s STACK ORDER: bluesteel,
 * mint, lilacish, white gold, rose gold, yellow gold, orange, with the chase ranks on the golds.
 * One Piece's tail (TR, L, PR, DON!!) is stack order, not rank, and it is on yellow gold because
 * the stack puts it after the Secret Rare.
 *
 * AN UNREAD, UNKNOWN OR UNLISTED RARITY IS BLUESTEEL, the mark's default: a color is never
 * guessed. Code cards (`pokemon_code`) and `misc` stay bluesteel. */
import { DEFAULT_VARIANT, type LogoVariant } from './markPalettes'

export const RARITY_MARKS: Readonly<Record<string, Readonly<Record<string, LogoVariant>>>> = {
  pokemon: {
    'Common': 'bluesteel',
    'Uncommon': 'mint',
    'Rare': 'lilacish',
    'Holo Rare': 'lilacish',
    'Double Rare': 'whiteGold',
    'Radiant Rare': 'whiteGold',
    'ACE SPEC Rare': 'whiteGold',
    'Illustration Rare': 'roseGold',
    'Ultra Rare': 'roseGold',
    'Special Illustration Rare': 'yellowGold',
    'Hyper Rare': 'yellowGold',
    'Secret Rare': 'orange',
    'Rainbow Rare': 'orange',
  },
  pokemon_code: {
    'Code Card': 'bluesteel',
  },
  riftbound: {
    'Common': 'whiteGold',
    'Uncommon': 'mint',
    'Rare': 'roseGold',
    'Epic': 'orange',
    'Showcase': 'yellowGold',
    'Promo': 'bluesteel',
  },
  one_piece: {
    'C': 'bluesteel',
    'UC': 'mint',
    'R': 'lilacish',
    'SR': 'whiteGold',
    'SEC': 'roseGold',
    'TR': 'yellowGold',
    'L': 'yellowGold',
    'PR': 'yellowGold',
    'DON!!': 'yellowGold',
  },
}

/** The palette for one card: its game's key and its catalogue rarity. Bluesteel for anything the
 *  table does not name, including a card with no game or no rarity. */
export function markFor(game: string | null | undefined, rarity: string | null | undefined): LogoVariant {
  if (game == null || rarity == null) return DEFAULT_VARIANT
  return RARITY_MARKS[game]?.[rarity] ?? DEFAULT_VARIANT
}
