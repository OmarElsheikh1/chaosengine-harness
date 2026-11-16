# Frozen procedure

Committed in the same commit as `rubric.md`, `PROMPT.txt`, `CANNED.txt`, and `fixtures/AGENTS.md`, before the first measured run. Later edits to this file invalidate the freeze.

## Machine and client

- Host: Mohab's ROG, Linux, one machine for every run.
- Client: the `grok` binary on `PATH`. Record `grok --version` into each run's `meta.json`.
- Model flag: `--model grok-4.7` on every session, including graders. A launcher probe that was not a measured arm showed the CLI recording that flag as the `modelUsage` key `grok-4.7-build`. On that probe the CLI meter matched this file's grok-4.7 price table ($0.021208 for 7983 input, 10112 cached input, and 31 output). Each measured run records the `modelUsage` key it actually received. Estimated USD still uses the table below.
- Reasoning: the CLI default. The flag `--reasoning-effort` is omitted.
- Permission: `--permission-mode bypassPermissions` so a headless session can write files. Same on every arm.
- Prompt delivery: `--verbatim --prompt-file` pointing at `PROMPT.txt`.
- Plan mode stays available. `--no-plan` is not passed.
- Max turns per Grok invocation: 40.
- Session wall clock: 45 minutes (2700 seconds) for the whole Grok conversation, including canned-reply resumes. `timeout` exit 124 counts as a run, correctness 0, time 2700.
- Each run uses its own `--leader-socket` under that run's `raw/` directory and its own `--session-id`.
- `~/.m2` stays warm and is not wiped. The same cache is on the classpath for every arm.
- Chrome is installed. The runner does not add headless properties and does not edit generated tests.

## Harness pin for arm C

`harness-pin.txt` is the full `origin/main` SHA at freeze time:

`a74873e53754f130ae0841459b0229575a4d6c14`

Arm C installs with the official one-liner, pinned to that SHA so the five C runs cannot drift if `main` moves, and names the Grok host the way `guides/tools/grok.md` requires:

```bash
curl -fsSL "$url" | bash -s -- "$url" --hosts grok
```

`$url` is `https://raw.githubusercontent.com/ShaftHQ/chaosengine-harness/<pin>/install.sh`. The install runs with the project directory as the working directory. Install wall clock is recorded separately and is not the session-time metric. The install attempt itself is capped at 25 minutes so a hung download still leaves a scored run. The removed transcript-store opt-in is not enabled.

## Campaign order

`run.sh <arm> <run>` performs one run. The campaign is interleaved:

```text
A1 B1 C1 A2 B2 C2 A3 B3 C3 A4 B4 C4 A5 B5 C5
```

`campaign.sh` calls `run.sh` in that order and stops the campaign on a runner crash. A timeout or a failing Maven build is a recorded run, not a crash.

## What each run stores

Under `raw/<arm>/<NN>/`:

- `meta.json` with exit code, times, usage, model, questions, install result
- `grok-stdout.txt`, `grok-stderr.txt`, `transcript.md` when `grok export` works
- `mvn-1.log`, `mvn-2.log`, `mvn-3.log` and `mvn-N.exit`
- `surefire-N/` copied after each Maven run when Surefire wrote XML

`outputs/<arm>-<NN>.tar.gz` is the project without `target/`, `.git/`, `.chaos-engine/`, or `*.sock`. The host receipt, when present, is copied into `raw/`.

## Clarifying questions

After each Grok invocation, if `pom.xml` is still absent and the assistant text ends with `?`, send `CANNED.txt` once via `grok -r <session-id> -p` and count it. Do this at most 3 times, and only while session time remains. A finished project that merely ends with a question mark is not a question.

## Correctness heuristics

These rules implement the rubric. They are not revised after the first measured run.

Functional points use Maven run 1 only. Determinism uses runs 1, 2, and 3. Each Maven invocation is capped at 10 minutes. The runner chooses the `pom.xml` nearest the project root, at depth at most 3.

- Build, 10: run 1 reached test execution (a Surefire XML report exists, or the log contains `Tests run:`) and the log does not contain `COMPILATION ERROR`. No `pom.xml` scores 0.
- Login, 8: a run-1 passing testcase whose Java method body contains `standard_user`. Method bodies are split on `@Test` methods when that annotation is present. Otherwise the whole class counts as the body.
- Checkout, 12: a run-1 passing testcase whose method body contains `checkout` and one of `checkout-complete`, `checkout_complete`, `Checkout: Complete`, or `Thank you for your order`.
- Determinism, 5: start at 5 when a `pom.xml` exists. Subtract 5 for each of the three Maven runs whose exit code is not 0. Floor at 0.
- Negative, 5: a run-1 passing testcase whose method body contains `locked_out_user` or both `wrong` and `password`.

A timeout of the Grok session forces every correctness component to 0, including when partial files exist.

## Price table

Published on <https://docs.x.ai/docs/models> and read on 2026-11-15. Model `grok-4.7`.

| Prompt size | Input / 1M | Cached input / 1M | Output / 1M |
| --- | --- | --- | --- |
| under 200k tokens | 2.00 | 0.50 | 6.00 |
| 200k tokens or more | 4.00 | 1.00 | 12.00 |

Prompt size is `input_tokens + cache_read_input_tokens`. The long-context rate applies to every token in that request when the sum reaches 200000. Reasoning tokens are recorded and are not added on top of `output_tokens`. The CLI `total_cost_usd` is stored as `meter_cost_usd` and is not overwritten by this estimate.

## Quality graders

`score.py --grade` builds a blind copy per run: it deletes `AGENTS.md`, `.chaos-engine/`, `.grok/`, `.chaos-engine-hosts.json`, and `*.sock`, then renames the copy to a random id. The map is `raw/blind-map.json` and is not shown to the grader.

Each grader is one Grok session, `--max-turns 1`, `--disable-web-search`, and `--json-schema` requiring integer scores at or below each maximum, plus a short `notes` string. The prompt quotes the quality section of `rubric.md`, tells the grader not to call tools, and includes the blinded source files up to 120000 characters. Two sessions, two session ids, same prompt. Reported quality is the mean of the parsed totals.

Static-analysis points inside readability stay with the grader. The runner does not invoke PMD or Checkstyle itself.

## Charts

`score.py --write-results` writes `results.csv` and, when matplotlib imports, these PNGs in `charts/`:

- `score-bar.png`, `quality-bar.png`, `correctness-bar.png`, `tokens-bar.png`, `time-bar.png`
- `score-vs-tokens.png`
- `score-box.png`

Bar height is the mean. The box plot uses the total score of each run.
