# Deviations

The rubric, prompt, fixture, and price table in the freeze commit stay as committed. This file records the one procedure change made after an uncounted pilot.

## 2026-11-15: turn cap

`procedure.md` set `--max-turns 40`. That cap is not in the issue. The issue's cap is 45 minutes.

Pilot arm A, run 1, under the freeze commit, exited after 40 turns and 272 seconds with `stop_reason=max_turn_requests`. The transcript shows research tool calls and no project files. The 45-minute timer never bound the session. That pilot is stored under `pilot/A1-40turn/` and is not one of the five measured runs.

Measured runs use `--max-turns 400` so the 45-minute timeout is the binding cap. The turn cap will not be tuned again after a measured run. A measured run that hits 400 turns is scored from the files it wrote. Only a 45-minute timeout forces correctness to 0.

The tool-call counter now counts `- ` lines under `## Tools` in `grok export` output. The first counter looked for `### Tool` and recorded 0 for the pilot even though the transcript listed tools.
