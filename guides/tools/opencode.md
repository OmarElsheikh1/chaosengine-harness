# OpenCode

Host id: `opencode`.

Install as in [INSTALL.md](../../INSTALL.md). Inference never selects OpenCode. Name it with `--hosts opencode` or `CHAOS_ENGINE_HOST=opencode`.

OpenCode is instruction-only. It reads `AGENTS.md`. There is no project hook runtime to install. Completing this host writes `.opencode/plugins/chaos-engine-receipt.js`. The read gate is the research receipt (`retrieve:`) instead of a pre-tool hook (GAP-OPENCODE-HOOKS).

Published context and instruction caps are `unknown`. See [capability profiles](../../references/profiles/capabilities.md).

Example, not yet validated by the offline conformance job: install into a docs-only repository, then follow [the tester start](../start-tester.md). No Java is required. ChaosEngine does not install the OpenCode product.
