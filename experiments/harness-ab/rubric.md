# Frozen rubric

This file is frozen before the first measured run. Do not edit it after any arm has started. The commit that adds this file is the rubric SHA. `procedure.md` in the same commit freezes the runner flags and the automated scoring rules that implement this rubric.

## Prompt

The prompt file is `PROMPT.txt`. Its text is:

```text
Create SHAFT_Engine UI tests for https://www.saucedemo.com: a login test, and a test that adds an item to the cart and completes checkout.
```

If an agent asks a clarifying question, every arm gets the same canned reply from `CANNED.txt`:

```text
Use your best judgement and proceed.
```

Count how many times that reply is sent.

## Arms

| Arm | Folder | Contents before the Grok session |
| --- | --- | --- |
| A bare | `exp/A-bare/run-NN/` | empty |
| B AGENTS.md | `exp/B-agentsmd/run-NN/` | only `fixtures/AGENTS.md` |
| C ChaosEngine | `exp/C-chaosengine/run-NN/` | empty, then the official installer pinned by `harness-pin.txt`, with `--hosts grok` |

## Cost

- Tokens: total, input, output, and cached input, from the CLI usage object.
- Estimated USD from the published grok-4.7 list price in `procedure.md`. Also record the CLI `total_cost_usd` meter when it is present.
- Wall-clock time of the Grok session. A timeout is capped at 45 minutes.
- Agent turns (`num_turns`) and tool-call count when the transcript exposes one.
- Clarifying questions asked.

## Correctness, 0-40 (automated)

- Builds with no manual fixes: 10
- Login test passes for `standard_user`: 8
- Cart-plus-checkout test passes end to end and asserts the order-complete page: 12
- Tests are deterministic: 3 consecutive reruns all green, or 5 points off per flaky rerun: 5
- At least one negative or assertion-meaningful check, for example `locked_out_user` or a wrong password: 5

No person edits the project between the session and `mvn -q test`.

## Quality, 0-60 (blind)

- Design, 15: Page Object Model or equivalent separation, no duplication, and sensible test and page structure.
- SHAFT idioms, 15: uses SHAFT's fluent API correctly (`SHAFT.GUI.WebDriver`, `SHAFT.TestData`, properties-based config), no raw Selenium where SHAFT covers it, and a correct Maven setup with a current SHAFT version.
- Robustness, 10: stable locators (`data-test` or ids), no hard sleeps, and relies on SHAFT's built-in waits.
- Test data and config, 5: credentials and URLs externalised (JSON or properties), with no hardcoded secrets in tests.
- Readability and maintainability, 10: naming, small methods, comments only where useful, and static analysis (PMD or Checkstyle warning count, normalised).
- Repo hygiene, 5: README or run instructions, `.gitignore`, and no junk files.

## Scoring protocol

- Strip `AGENTS.md`, `.chaos-engine/`, and other harness artefacts. Give each output a random id before grading.
- Two independent graders use this rubric: a Grok CLI session with tools disabled, and a second Grok session with the same prompt. Report both scores. An item whose scores differ by more than 20% of that item's maximum is listed with both notes.
- Reported quality for a run is the mean of the two grader totals. A grader that returns no parseable score is omitted and named. If both fail, quality is blank.
- Total score = correctness + quality, out of 100.
- Also report quality per 100k tokens and quality per minute.

## Integrity

Report a loss or a tie when that is what the runs show. Deviations go in `REPORT.md` and are not used to change this rubric.
