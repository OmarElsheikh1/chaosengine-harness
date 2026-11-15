"""Plugin CHANGELOG and COMPATIBILITY must name the harness VERSION."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.ci.check_plugin_changelog_version import defects, engine_version, main

ROOT = Path(__file__).resolve().parents[2]


class PluginChangelogVersionTest(unittest.TestCase):
    def fixture(self, version: str, changelog: str, compatibility: str) -> Path:
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (root / "VERSION").write_text(version + "\n", encoding="utf-8")
        plugin = root / "agent-plugins/chaos-engine"
        plugin.mkdir(parents=True)
        (plugin / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
        (plugin / "COMPATIBILITY.md").write_text(compatibility, encoding="utf-8")
        (root / "pom.xml").write_text("<project><version>0.0.0</version></project>\n", encoding="utf-8")
        return root

    def test_version_file_not_pom_is_the_plugin_version(self) -> None:
        root = self.fixture(
            "9.9.9",
            "# Changelog\n\n## 9.9.9 - 2026-11-15\n\n- x\n",
            "Evidence for 9.9.9.\n",
        )
        self.assertEqual("9.9.9", engine_version(root))
        self.assertEqual([], defects(root))
        self.assertEqual(0, main(["--root", str(root)]))

    def test_missing_changelog_or_compatibility_names_the_version(self) -> None:
        root = self.fixture("9.9.9", "# Changelog\n\n## 9.9.8 - 2026-11-15\n", "Evidence for 9.9.8.\n")
        problems = defects(root)
        self.assertEqual(2, len(problems))
        self.assertIn("## 9.9.9", problems[0])
        self.assertIn("9.9.9", problems[1])
        self.assertEqual(1, main(["--root", str(root)]))

    def test_prefix_heading_does_not_count(self) -> None:
        root = self.fixture("9.9.9", "## 9.9.90 - 2026-11-15\n", "9.9.9\n")
        self.assertTrue(defects(root))

    def test_repository_version_file_is_covered(self) -> None:
        version = engine_version(ROOT)
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), version)
        self.assertNotEqual("", version)
        self.assertEqual([], defects(ROOT))
        self.assertEqual(0, main(["--root", str(ROOT)]))


if __name__ == "__main__":
    unittest.main()
