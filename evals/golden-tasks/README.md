# Grok golden tasks

This corpus is a local regression ledger for the owner's Grok path. Each task records checks, not prompts.

`conformance.py` scores a task with `run_golden_task`. A check that did not run is `skipped`. A check that ran but was not measured is `unknown`. Neither value is a pass. CI does not call a model and does not need a vendor API key.
