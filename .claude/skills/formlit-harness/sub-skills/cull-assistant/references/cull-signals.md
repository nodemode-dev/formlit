# Cull signals

`analyze_culling` writes these into each photo's `meta.cull` (read them with `get_photo`):

| field | what it is | where it misleads |
| --- | --- | --- |
| `sharpness` | the 90th percentile of Laplacian variance over a 6 x 6 tile grid (the sharpest part of the frame), or the sharpest face when faces were found, on a log scale of 0 to 100 | heavy texture (foliage, gravel) scores high even when the subject is soft; a tiny sharp area in a soft frame still scores well |
| `exposure` | 100 minus penalties for highlights at 250 and above beyond 1 percent, shadows at 4 and below beyond 2 percent, and distance of the mean from 0.45 | high-key and low-key work scores as badly exposed |
| `faces` | detected faces count (when the faces model is installed) | profiles and small faces are missed |
| `group` | index of the near-duplicate group: consecutive frames within 3 seconds whose difference hashes differ by 12 bits or fewer, or by 6 or fewer at any time apart | panning bursts with a changing background split into several groups |
| `groupSize` | frames in the group | |
| `best` | the frame in the group with the highest 0.75 x sharpness + 0.25 x exposure | it cannot see closed eyes or expressions |
| `faceList` | up to six faces, largest first: `box` [x0, y0, x1, y1] 0 to 1 across the photo as shown, the face's own `sharpness`, and `eyesOpen` (None for small faces) | empty without the faces model; small or profile faces are missed |
| `run` | when the analysis ran, in milliseconds; group indexes are only comparable within one run | |

`get_cull_groups` (command `cull.groups`) returns the photos in the order given, gathered into groups by (run, group), each with its best frame and every photo's scores including `faceList`. It is the same view as the window's Cull mode (K), so a person and an agent can talk about "burst 3" and mean the same frames.

`apply_culling` rules: `rejectBlurry` rejects sharpness under `threshold`; `rejectDuplicates` rejects every non-best frame in groups larger than one; `pickBest` picks the best of each group larger than one. A frame in a group of one is left unflagged unless it is blurry.

Install the faces model (`run_command` with `ai.download`, model `faces`) before analysis when the shoot is people: sharpness is then measured on faces, which is what matters for portraits and events.
