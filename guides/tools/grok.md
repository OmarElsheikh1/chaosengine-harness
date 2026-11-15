# Grok

Host id: `grok`.

Install as in [INSTALL.md](../../INSTALL.md), then name this host with `--hosts grok` or `CHAOS_ENGINE_HOST=grok`. Naming `grok` does not by itself merge the lean config span.

Grok reads `AGENTS.md` and `.grok/plugins/chaos-engine`. Lifecycle hooks match the Codex set, including PreToolUse and Stop. ChaosEngine still emits a deny and exit code 2. This host can ignore that exit (GAP-EXIT2 in `references/host-parity-matrix.md`).

Published context and instruction caps are `unknown`. See [capability profiles](../../references/profiles/capabilities.md).

Example, checked by the offline conformance job: install into a repository of stories, then follow [the scrum-master start](../start-scrum-master.md). No Java is required.

<!-- host-doc-example: grok
entry: AGENTS.md
paths: AGENTS.md, .grok/hooks/lifecycle.json
config_keys: hooks
-->
