# Rules source

Canonical policy is `skills/chaos-engine/SKILL.md` plus `identity.md`.
The one generated sentence is `hosts.instruction_block()`.
Thin pointers use `hosts.import_pointer_instruction()`.
Copilot uses `hosts.copilot_instruction_block()` (same sentence, `../` paths).
Codex config uses `hosts.codex_content()`.
Codex and Grok hooks use `hosts.lifecycle_hooks_document()`.
Do not copy that sentence into host files by hand.

## Generated set

- `AGENTS.md`
- `CLAUDE.md`
- `GEMINI.md`
- `.github/copilot-instructions.md`
- `.codex/config.toml`
- `.codex/hooks.json`
- `.grok/hooks/lifecycle.json`

`CLAUDE.md` and `GEMINI.md` are `@AGENTS.md` only.
Codex and Grok hook files are mechanical config. They reference the router by
not copying the policy sentence. The router path is
`.chaos-engine/skills/chaos-engine/SKILL.md`.

## Nested project files

Nested `AGENTS.md` files stay user-owned. Install does not rewrite them.
Hookless entry loads user-owned text through `hosts.load_project_agents`.
The closest file to the edited path wins over the repo root for project
instructions: root text is first, the closest file is last.
Iron laws, ethics, and person-only rules still outrank any project file.
Owner chat still outranks the files, except person-only and ethics.
