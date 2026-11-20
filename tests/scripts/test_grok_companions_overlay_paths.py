"""The companions publisher points an install overlay at `.chaos-engine/`."""

from __future__ import annotations

import importlib.util
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REMOVED = re.compile(r"(?<!\.)chaos-engine/(?:skills|references|companions)/")


def load_publisher(path: Path):
    spec = importlib.util.spec_from_file_location("grok_model_load_overlay_paths", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CompanionsOverlayPathTests(unittest.TestCase):
    def test_publish_into_an_overlay_emits_dot_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            overlay = project / ".chaos-engine"
            skill = overlay / "skills" / "chaos-engine" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("# skill\n", encoding="utf-8")
            (overlay / "identity.md").write_text("# identity\n", encoding="utf-8")
            installed = overlay / "grok_model_load.py"
            installed.write_bytes((ROOT / "runtime" / "grok_model_load.py").read_bytes())
            # The retired nested tree must not be what the card names.
            self.assertFalse((project / "chaos-engine" / "skills").exists())

            module = load_publisher(installed)
            written = module.publish(project)

            card = project / ".grok" / "rules" / "companions.md"
            self.assertIn(card.as_posix(), written)
            text = card.read_text(encoding="utf-8")
            self.assertEqual(text, module.COMPANIONS)
            self.assertIsNone(REMOVED.search(text), REMOVED.findall(text))
            self.assertIn(".chaos-engine/skills/<name>/SKILL.md", text)
            self.assertIn(".chaos-engine/references/roles.md", text)
            self.assertIn(".chaos-engine/references/execution-workflows.md", text)
            self.assertIn(".chaos-engine/companions/ethics-card.md", text)
            self.assertIn(".chaos-engine/references/iterative-flow.md", text)


if __name__ == "__main__":
    unittest.main()
