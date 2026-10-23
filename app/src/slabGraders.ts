/* THE GRADERS THE ADD SHEET OFFERS: a copy of `store/slabs.GRADERS`, in its order. A copy exists
 * because no route sends the list yet (`docs/specs/my-slabs.md` 4.8). `tests/unit/slab-graders.unit.ts`
 * fails when the two differ, so a grader added there is added here, or the build is red. */
export const SLAB_GRADERS = ['psa', 'beckett', 'bgs', 'bvg', 'sgc', 'cgc'] as const

export type SlabGrader = (typeof SLAB_GRADERS)[number]
