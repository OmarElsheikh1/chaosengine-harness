"""Doctor store probes must not make the next doctor JSON grow retrieve usage."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, relative: str):
    path = ROOT / relative
    if not path.is_file() and "/" not in relative:
        nested = ROOT / "runtime" / relative
        if nested.is_file():
            path = nested
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {relative}")
    spec.loader.exec_module(module)
    return module


class DoctorRetrieveProbeUsageTest(unittest.TestCase):
    def test_probe_does_not_append_usage_and_a_counted_retrieve_does(self) -> None:
        overlay = _load("ce_overlay_probe_usage", "overlay_match.py")
        retrieve = _load("ce_retrieve_probe_usage", "retrieve.py")
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            usage = project / ".chaos-engine-state" / "retrieve-usage.json"
            reports = overlay._probe_degraded_retrieves(project)
            self.assertEqual({"graphify", "mempalace"}, {item.get("store") for item in reports})
            self.assertFalse(usage.exists(), usage)
            receipt = retrieve.retrieve(
                "doctor policy", store="graphify", project=project, account=True
            )
            self.assertIn(receipt.get("status"), {"used", "skipped"})
            document = json.loads(usage.read_text(encoding="utf-8"))
            self.assertEqual(1, len(document["records"]))
