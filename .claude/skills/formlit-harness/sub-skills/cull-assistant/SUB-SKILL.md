---
name: cull-assistant
description: "Owns choosing the keepers from a shoot in formlit over MCP: sharpness and exposure scoring, near-duplicate groups, faces, picks, rejects, ratings, labels and the human review pass. Load when someone asks to cull, pick the best, find the sharp ones, remove duplicates or rate a shoot."
---

# Cull Assistant

## Purpose

Reduce a shoot to its keepers without losing anything: score, group, flag, then verify by looking. Hands back the pick and reject counts, the ids of each, and the frames that need a person's eye.

## Preconditions

The shoot's ids, from catalog-keeper.

## Procedure

1. `analyze_culling` on the ids. It writes `meta.cull` per photo (see `references/cull-signals.md`) and changes no flags. On a large shoot this is the slow step; it waits until done.
2. Decide the policy with the person's words: "pick the best" means `pickBest` only; "get rid of the blurry ones" adds `rejectBlurry`; "one of each" adds `rejectDuplicates`. When they said none of these, use `pickBest` alone.
3. `apply_culling` with that policy. Lower `threshold` (default 35) for intentionally soft work such as night street or motion blur; raise it for studio and product.
4. Review: run `checklists/cull-review.md`. Look at the best and the runner-up of the three largest groups and at the two lowest-scoring rejects with `get_preview` at 768.
5. Overrides go through `set_flag`; star ratings through `set_rating` (5 for portfolio, 4 for client delivery, 3 for keep) only when the person asked for ratings.
6. Gather the picks: `find_photos` with `{"flags": ["pick"]}` on the shoot's source, then `create_collection` named after the shoot plus "Picks".

## Gate

Done when the review checklist is complete and its findings are in the reply, and the picks are in a collection.

## Hands back

Counts and ids of picks and rejects, the collection id, and any frames flagged for the person (closed eyes, missed focus that scored well).

## Owned resources

- `references/cull-signals.md` what each score means and where it misleads
- `checklists/cull-review.md` the look-before-you-trust pass
