"""Root-layout README inventory runs before push.

tests/scripts/test_chaos_engine_token_waste_6161.py still describes the older
gate, and tests/scripts/quarantine.txt keeps that module out of collection
because it imports SHAFT-only scripts.agents. This module is the check CI runs.
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tip = load(ROOT / "skills/local-agency/scripts/tip_preflight.py", "ce_tip_preflight_root_inventory")
readme = load(ROOT / "scripts/ci/validate_chaos_engine_readme.py", "ce_readme_inventory_root")


class RootLayoutInventoryPreflightTest(unittest.TestCase):
    def test_skip_set_matches_the_readme_scanner(self):
        self.assertEqual(readme.PACKAGED_PYTHON_SKIP, tip.PACKAGED_PYTHON_SKIP)

    def test_root_layout_python_runs_inventory(self):
        calls = []

        def validator(root):
            calls.append(root)
            return ["source-derived inventory drift: python-libraries"]

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "install.py").write_text("# harness\n", encoding="utf-8")
            (root / "VERSION").write_text("0\n", encoding="utf-8")
            for path in ("official_self_heal.py", "skills/local-agency/scripts/tip_preflight.py"):
                calls.clear()
                failures = tip.preflight_failures(root, [path], inventory_validator=validator)
                self.assertEqual([root], calls, path)
                self.assertTrue(
                    any("source-derived inventory drift: python-libraries" in item and "--write" in item for item in failures),
                    path,
                )

    def test_harness_skipped_trees_and_markdown_do_not_run_inventory(self):
        calls = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "install.py").write_text("# harness\n", encoding="utf-8")
            (root / "VERSION").write_text("0\n", encoding="utf-8")
            tip.preflight_failures(
                root,
                ["README.md", "tests/test_x.py", "scripts/ci/x.py", ".github/workflows/x.py", "experiments/x.py"],
                inventory_validator=lambda candidate: calls.append(candidate) or [],
            )
            self.assertEqual([], calls)

    def test_adopter_product_python_skips_inventory(self):
        calls = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "install.py").write_text("# product only\n", encoding="utf-8")
            tip.preflight_failures(root, ["app.py"], inventory_validator=lambda candidate: calls.append(candidate) or [])
            self.assertEqual([], calls)

    def test_overlay_python_still_runs_inventory_without_harness_markers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            failures = tip.preflight_failures(
                root,
                ["chaos-engine/new_module.py"],
                inventory_validator=lambda _root: ["source-derived inventory drift: python-libraries"],
            )
            self.assertTrue(any("source-derived inventory drift: python-libraries" in item and "--write" in item for item in failures))

    def test_docs_name_the_root_layout_gate(self):
        tip_doc = (ROOT / "references/tip-churn-preflight.md").read_text(encoding="utf-8")
        coach = (ROOT / "skills/local-agency/references/coach-loop.md").read_text(encoding="utf-8")
        for text in (tip_doc, coach):
            self.assertIn("install.py", text)
            self.assertIn("VERSION", text)
            self.assertIn("experiments/", text)
