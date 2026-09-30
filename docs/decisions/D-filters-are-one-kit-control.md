## D-filters-are-one-kit-control — Filters are one kit control

**Every filter and sort row is one kit control, one width.** In the Filters popover and sheet,
Game, Set, Rarity and Sort fill the same width (D195, same-role buttons share a width). No screen
draws its own filter row. A screen that filters calls `FilterBar`, `FilterChips` or `Select`.

**The sort direction is inside the Sort control.** `SortControl` is one bordered field. The key
fills it. The direction toggle is a segment at its end, split by a divider. There is no loose icon.

**One value style.** At rest, every value reads in `--bn-ink-2` at weight 500. "Any" and "Most
recent" look the same, legible and not placeholder-faint. A set filter takes the accent edge, the
accent tint and `--bn-accent-hover` ink. A set filter is never marked by weight alone.

**Thumb targets are 40px or more** (`--bn-control-h`). Only `--bn-*` tokens.

**Enforced** by `app/tests/filter-standard.spec.ts` (row width, set versus rest) and by
`make kit-adoption`: R2-class reserves the kit's filter classes (`bn-pick`, `bn-fchip`,
`bn-filterchips`, `bn-sort`, `bn-filterbar`, `bn-hidetoggle`).
