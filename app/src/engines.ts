/* WHO READS THE CARDS: the two engines the runs sheet offers, in the operator's words.

   `docs/specs/identify-engine-pick.md` is the design and D2 carries the owner's ruling. The wire names are
   `marqo-b` (the free reader, which matches a photograph to stock photos) and `haiku` (the paid
   read). The free read is the default pick each time the composer opens, and the pick is not
   stored on the device.

   D196 keeps a model's name off the screen, with TWO NAMED EXCEPTIONS on the owner's word: each
   pick's hover tooltip names its model. The two constants below are those two strings. The
   `no mechanism on screen` row reads each constant from THIS FILE and exempts exactly that text,
   so the declaration shape matters: one line, one pair of quotes, no backslash and no `${`.
   Nothing else on a screen may name either model. */

export type Engine = 'marqo-b' | 'haiku'

export const DEFAULT_ENGINE: Engine = 'marqo-b'

export const HAIKU_NAME_TOOLTIP = 'Claude Haiku 4.5 by Anthropic, sent through the Batch API'
export const MATCHER_NAME_TOOLTIP = 'Marqo ecommerce-B, an open image model, run on this Mac'
