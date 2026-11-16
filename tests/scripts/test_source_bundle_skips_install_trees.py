"""source_bundle must skip install trees before the grader character cap."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCORE = ROOT / "experiments" / "harness-ab" / "score.py"


def _score():
    specification = importlib.util.spec_from_file_location("harness_ab_score", SCORE)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"cannot load {SCORE}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class SourceBundleSkipTest(unittest.TestCase):
    def test_bundle_skips_install_trees_and_existing_strip_dirs(self):
        score = _score()
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / ".agents").mkdir()
            (project / ".memory").mkdir()
            (project / ".git").mkdir()
            (project / ".agents" / "a.md").write_text("agents-install-tree\n", encoding="utf-8")
            (project / ".memory" / "b.md").write_text("memory-install-tree\n", encoding="utf-8")
            (project / ".git" / "note.md").write_text("git-should-stay-skipped\n", encoding="utf-8")
            (project / "pom.xml").write_text("<project>pom-marker</project>\n", encoding="utf-8")
            bundle = score.source_bundle(project)
        self.assertIn("pom.xml", bundle)
        self.assertIn("pom-marker", bundle)
        self.assertNotIn("agents-install-tree", bundle)
        self.assertNotIn("memory-install-tree", bundle)
        self.assertNotIn(str(Path(".agents") / "a.md"), bundle)
        self.assertNotIn(str(Path(".memory") / "b.md"), bundle)
        self.assertNotIn("git-should-stay-skipped", bundle)
        self.assertNotIn(str(Path(".git") / "note.md"), bundle)


if __name__ == "__main__":
    unittest.main()
