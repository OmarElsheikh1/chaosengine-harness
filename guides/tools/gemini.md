# Gemini CLI

Host id: `gemini`.

Install as in [INSTALL.md](../../INSTALL.md). Inference never selects Gemini. Name it with `--hosts gemini` or `CHAOS_ENGINE_HOST=gemini`. The hook launcher is Node.js (`hooks/launch.js`).

Gemini reads `GEMINI.md` and the skill adapter `.gemini/skills/chaos-engine/SKILL.md`. Lifecycle hooks include SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, Stop, PreCompact, and SessionEnd. Host event names such as BeforeTool map to those canonical events. Exit code 2 is honored.

Published context and instruction caps are `unknown`. See [capability profiles](../../references/profiles/capabilities.md).

Example, not yet validated by the offline conformance job: install into a repository of test plans, then follow [the tester start](../start-tester.md). No Java is required.
