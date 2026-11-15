# Capability profiles

On-demand limits for the eight install host ids. Not a skill. Not loaded at SessionStart. Not a measured benchmark.

Vendor context windows and instruction-size caps stay `unknown` until an official source is pinned in this file. A missing host, or a host whose hard cap is `unknown`, keeps triage defaults from `references/token-budget-modes.md`. Safety, negation, attribution, and hard blocks never shrink. When a docs-drift pin changes, review this file in that same follow-up. Do not re-measure a live model.

`entry_files` and `hooks` are harness facts from `hooks/kernel.py` and `hosts.py`, not vendor size limits.

| id | entry_files | hooks | hard_cap_bytes | source |
| --- | --- | --- | --- | --- |
| claude | CLAUDE.md, .claude/skills/chaos-engine/SKILL.md | lifecycle, exit 2 honored | unknown | hooks/kernel.py |
| codex | AGENTS.md, .agents/skills/chaos-engine/SKILL.md | lifecycle, exit 2 honored | unknown | hooks/kernel.py |
| gemini | GEMINI.md, .gemini/skills/chaos-engine/SKILL.md | lifecycle via hooks/launch.js, exit 2 honored | unknown | hooks/kernel.py |
| grok | AGENTS.md, .grok/plugins/chaos-engine | lifecycle, exit 2 not honored | unknown | hooks/kernel.py |
| copilot | AGENTS.md, .github/copilot-instructions.md, .github/skills/chaos-engine/SKILL.md | lifecycle, exit 2 not honored | unknown | hooks/kernel.py |
| opencode | AGENTS.md | instruction-only | unknown | hosts.py |
| cursor | AGENTS.md | instruction-only | unknown | hosts.py |
| grok-bot | references/bot-entry.md | instruction-only, no receipt shim | unknown | hosts.py |

## Harness budgets

These numbers are ChaosEngine rules. They are not vendor caps. `brief_fits` does not apply them as a host hard cap.

| fact | bytes | kind | source |
| --- | --- | --- | --- |
| SessionStart locator | 4096 | harness-budget | references/host-parity-matrix.md |
| Always-loaded instruction lines | 150 | harness-recommendation | token_economy.py |
