---
name: pipeline-builder
description: "Owns formlit's develop pipeline under backend/app/develop and its decode inputs: the numpy reference, the numba finish kernel and its parity, the stage cache, region renders for 1:1, geometry and coordinate frames, masks evaluation, Camera Look, lens blur and retouch. Load for a new develop control, wrong colours, slow renders, seams at 1:1, or kernel changes."
---

# Pipeline Builder

## Purpose

Change how pixels are computed without breaking the two promises the pipeline makes: the kernel matches the numpy reference, and a 1:1 region matches the same area of a full render. Hands back the change with parity and timing figures.

## Preconditions

`backend/HASHOUT_LOG.md` read, and `references/pipeline.md` for the stage order and coordinate frames.

## Procedure

1. Place the change in its stage (`references/pipeline.md`): decode, geometry, white balance and linear adjustments, planes, masks, finish. A new slider is an entry in `shared/controls.json` (read by `app/develop/settings.py` and served to the window by `develop.controls`) plus its math in the stage that owns it.
2. Implement in the numpy reference first (`finish.py`, `planes.py`, `masks.py`). The reference is what exports, thumbnails and headless renders trust.
3. Mirror in the kernel (`kernel.py`): new parameters go into the `flags` and `params` arrays, with a presence flag so photos without the setting skip the work. Keep integer arithmetic masked to int64 (numba promotes uint32 silently).
4. Cache keys: anything that changes a stage's output must be in that stage's key in `render.py` (`geo`, `lin_key`, plane sigmas, `mask_key`), or the stage cache serves stale pixels.
5. Run `checklists/parity-gate.md`: kernel against reference, region against full, and timing.
6. Bump `SOURCE_VERSION` in `app/services/decode.py` only when decoded sources change; it invalidates every cached source.
7. Record the decision and the figures in `backend/HASHOUT_LOG.md`.

## Gate

Done when the parity gate's three figures are recorded and within bounds.

## Hands back

The change, the parity figures (max absolute difference in 8-bit levels), the cached render time at 1024 px, and any cache or version bump.

## Owned resources

- `references/pipeline.md` stages, coordinate frames, the cache and the kernel contract
- `checklists/parity-gate.md` the numbers every pipeline change reports
