# Codex

Host id: `codex`.

Install as in [INSTALL.md](../../INSTALL.md), then name this host with `--hosts codex` or `CHAOS_ENGINE_HOST=codex`. Codex registers a marketplace when `codex` is on `PATH`. A missing CLI still leaves the adapter files.

Codex reads `AGENTS.md` and the skill adapter `.agents/skills/chaos-engine/SKILL.md`. Lifecycle hooks include SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, PostToolUseFailure, Stop, SubagentStop, and SessionEnd. Exit code 2 is honored.

Published context and instruction caps are `unknown`. See [capability profiles](../../references/profiles/capabilities.md).

Example, not yet validated by the offline conformance job: install into a repository of stories, then follow [the developer start](../start-developer.md). No Java is required.
