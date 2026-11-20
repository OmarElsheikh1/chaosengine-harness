"""Latest Temurin with no binary for this platform yet falls back to the pinned runtime."""
import importlib.util
import json
import sys
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def load():
    spec = importlib.util.spec_from_file_location("ce_deps_java", ROOT / "runtime" / "dependencies.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module




def http(code):
    return urllib.error.HTTPError("u", code, "x", {}, None)


class JavaPinnedFallbackTest(TestCase):
    def setUp(self):
        self.assertRegex(load()._pinned_temurin_version(), r"^25\.\d+(?:\.\d+)+\+\d+$")

    def test_404_on_latest_falls_back_to_pinned(self):
        module = load()
        pinned = module._pinned_temurin_version()
        requested = "25.0.99+1"
        self.assertNotEqual(requested, pinned)
        calls = []

        def fake(version, **_):
            calls.append(version)
            if version == requested:
                raise http(404)
            return "/java"

        with mock.patch.object(module, "_install_temurin_release", side_effect=fake):
            self.assertEqual("/java", module.install_exact_java(requested, system="windows"))
        self.assertEqual([requested, pinned], calls)

    def test_other_errors_and_pinned_itself_still_raise(self):
        module = load()
        pinned = module._pinned_temurin_version()
        with mock.patch.object(module, "_install_temurin_release", side_effect=http(403)):
            with self.assertRaises(urllib.error.HTTPError):
                module.install_exact_java("25.0.99+1", system="windows")
        with mock.patch.object(module, "_install_temurin_release", side_effect=http(404)) as fake:
            with self.assertRaises(urllib.error.HTTPError):
                module.install_exact_java(pinned, system="windows")
            self.assertEqual(1, fake.call_count)


class JavaResolveAgreesWithInstallTest(TestCase):
    """A rerun must reuse the pinned JDK when the latest GA is unpublished here."""

    def test_unpublished_latest_resolves_to_pinned(self):
        module = load()
        pinned = module._pinned_temurin_version()

        def opener(url, timeout):
            raise http(404)

        self.assertEqual(pinned, module._published_temurin_or_pinned("25.0.99+1", opener=opener))

    def test_published_latest_and_other_errors_keep_latest(self):
        module = load()

        class Ok:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        self.assertEqual("25.0.99+1", module._published_temurin_or_pinned("25.0.99+1", opener=lambda u, timeout: Ok()))

        def forbidden(url, timeout):
            raise http(403)

        self.assertEqual("25.0.99+1", module._published_temurin_or_pinned("25.0.99+1", opener=forbidden))


class TemurinFourComponentBuildTest(TestCase):
    """Adoptium GA 25.0.5.1+2 has one more dotted component than 25.0.5+8."""

    def test_pinned_archive_url_matches_the_recorded_linux_artifact(self):
        module = load()
        spec = json.loads((ROOT / "dependencies.json").read_text(encoding="utf-8"))
        pinned = spec["runtimes"]["temurin"]["version"]
        expected = spec["runtimes"]["temurin"]["artifacts"]["linux-x64"]["url"]
        with mock.patch.object(module.platform, "machine", return_value="x86_64"):
            self.assertEqual(expected, module._temurin_url(pinned, "linux"))
            self.assertEqual(
                "https://github.com/adoptium/temurin25-binaries/releases/download/"
                "jdk-25.0.5%2B8/OpenJDK25U-jdk_x64_linux_hotspot_25.0.5_8.tar.gz",
                module._temurin_url("25.0.5+8", "linux"),
            )
        with self.assertRaises(ValueError):
            module._temurin_url("25+2", "linux")

    def test_java_probe_keeps_every_dotted_component(self):
        module = load()
        contract = {"probe": ["java", "-version"]}

        def runner(_command, **_kwargs):
            return SimpleNamespace(
                returncode=0,
                stdout='openjdk version "25.0.5.1+2"\n',
                stderr="",
            )

        probed = module.probe_account_dependency(
            "java", "/usr/bin/java", contract, runner=runner
        )
        self.assertEqual("25.0.5.1+2", probed["version"])

        def older(_command, **_kwargs):
            return SimpleNamespace(
                returncode=0,
                stdout='openjdk version "25.0.5+8"\n',
                stderr="",
            )

        self.assertEqual(
            "25.0.5+8",
            module.probe_account_dependency(
                "java", "/usr/bin/java", contract, runner=older
            )["version"],
        )

    def test_stable_channel_accepts_a_four_component_ga(self):
        module = load()
        payload = {
            "versions": [
                {"major": 25, "semver": "25.0.5+8"},
                {"major": 25, "semver": "25.0.5.1+2"},
            ]
        }

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read(self, _size):
                return json.dumps(payload).encode()

        self.assertEqual(
            "25.0.5.1+2",
            module.resolve_stable_version(
                "java",
                {
                    "minimumVersion": "25.0.0",
                    "stableChannel": "https://example.invalid/java",
                },
                opener=lambda *_args, **_kwargs: Response(),
            ),
        )
