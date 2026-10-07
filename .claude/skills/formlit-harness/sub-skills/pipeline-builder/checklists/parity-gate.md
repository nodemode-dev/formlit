# Parity gate

Report each figure as a number in `backend/HASHOUT_LOG.md` and in the hand-back.

- [ ] Kernel against reference: render the same photo and settings through `kernel.finish` and `finish.finish` at 1024 px; max absolute difference at most 1 level in 8 bits, on a raw, a JPEG and a photo with two masks
- [ ] Region against full: `render_region` of a centre region at 1:1 against the same crop of a full render; max difference at most 1 level, no visible seam at the region edge
- [ ] Timing: cached render of a 24 MP raw at 1024 px after one warm-up, stated in milliseconds, against the previous figure in the log
- [ ] Defaults unchanged: a photo with empty develop settings renders the same before and after the change (difference 0 to 1 level)
- [ ] Export path: `./formlit cli export.run ids=[...] preset=builtin.full` writes a JPEG that looks the same as the window's preview
