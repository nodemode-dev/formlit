# Verification

Every interface change is checked in a browser before it lands, and checked the slow way, because a flash or a layout jump is invisible on a fast machine with a warm cache.

## The throttled run

1. Boot formlit (`./formlit boot`) and open http://localhost:5390 in Chromium with DevTools.
2. In Performance, set CPU to 4x slowdown; in Network, choose a slow 3G-class profile and disable the cache.
3. Hard-reload, then exercise every path the change touched: open and close the panel or dialog, switch modules, change the selection, drag the slider, run the command.
4. Watch the moment of change, not the end state: no blank frame, no theme or font flash, no row that rebuilds, no jump in layout.
5. Record the result with a layout-shift observer (cumulative layout shift must stay 0 after the first paint) and check the console for errors.

The same run can be scripted with Playwright: emulate `Emulation.setCPUThrottlingRate` at 4 and `Network.emulateNetworkConditions` with 150 ms latency, observe `layout-shift` entries, and screenshot each step.

## Engine changes

Run the command from the CLI (`./formlit cli <id> ...`) against a scratch catalog (`FORMLIT_DATA_DIR`), check the rendered result with `/api/photos/{id}/render`, and when a render path changed, compare the numba kernel and the numpy reference on the same settings.

## What tests to write

formlit's behaviour to cover is described in the planning sidecar's `TEST_PLAN.md`, written for a fresh session that has not seen the implementation.
