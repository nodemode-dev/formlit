# Lightroom parity rubric

The score compares formlit with Lightroom Classic row by row, the same way the form family's comparison pages do.

## Counting

| Grade | Points | Meaning |
| --- | --- | --- |
| Full | 1 | implemented and wired from the interface through to rendering or export; a person can do it in the window and an agent can do it over MCP |
| Partial | 0.5 | it works, but part of Lightroom's behaviour is missing, or it is reachable only from one side |
| None | 0 | absent |

Score = points / scored rows, as a percentage with one decimal. Platform rows (desktop app, web app, tablet and phone, cloud) are listed but not scored.

## Rules

- Every Full names the file where the trace ends (the command or the writer), so a reviewer can follow it.
- A Partial says in a few words what is missing.
- A row is graded on what ships in this version, not on what is planned.
- A feature behind an optional install (an AI model, ffmpeg) still counts when the install is offered in the app and the failure says what to install.

## Categories

Import and catalog; Library and organizing; Culling and views; Develop tone and colour; Detail, optics and geometry; Local and retouching; AI and computational; Output; Platform (not scored). `docs/PARITY.md` holds the rows.
