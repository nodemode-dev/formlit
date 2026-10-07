# Zero flash

Nothing blinks, shifts or rebuilds. A change that loads new text or media lands in place, once, when ready.

## The pre-write statement

Before any DOM change, state: the node and property written; what in that container stays untouched; what space is already reserved for the result. "The container" as the node means it is a re-render: narrow it.

## Patterns that satisfy it

| Need | Pattern | Helper |
| --- | --- | --- |
| A list that changes | keyed reconcile, update in place, insert only where order differs | `patchList` in `src/ui/dom.ts` |
| Text or a class that may not have changed | write only when different | `setText`, `setClass`, `setHidden`, `setStyleVar`, `setValue` |
| A new image for the same slot | decode off screen, swap `src` once | `loadInto`, `swapMedia` |
| A new document in an iframe | load into a hidden second frame, swap visibility on load | Web module's double-buffered frames |
| Map tiles at a new zoom | keep the old tiles scaled as a ghost layer until the new ones load | `TileMap` in `src/modules/output/map.ts` |
| A slow operation | show progress only after 300 ms, keep it 250 ms once shown | `delayedIndicator`, `pendingClass` |
| First paint | theme boot inline in `index.html`, fonts preloaded, the app revealed after `document.fonts.ready` | `revealApp` |
| Space for late content | fixed sizes, `aspect-ratio`, reserved rows | `reserve` |

## Throttled verification

Chrome DevTools or Playwright with CPU throttling at 4x or more and a slow network, hard reload, then exercise every path the change touched and watch the moment of change, not the end state. The turn ledger records one of: verified under throttling, verified without throttling and why, or not verified.
