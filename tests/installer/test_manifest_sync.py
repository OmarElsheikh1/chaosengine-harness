"""Issue 32 per-file sync, kept edits, and a truncated curl|bash guard."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


def _bootstrap():
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("ce_bootstrap_sync", root / "bootstrap.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PlanSyncTest(unittest.TestCase):
    def test_truncated_curl_bash_and_foreign_edit_are_preserved_or_refused(self):
        boot = _bootstrap()
        remote = {"owned.txt": {"sha256": "a" * 64, "gitBlobSha1": "b" * 40, "size": 1, "mode": "100644"}}
        base = {"owned.txt": "c" * 64}
        local = {"owned.txt": "d" * 64}
        actions = {row["path"]: row["action"] for row in boot.plan_file_actions(remote, base, local)}
        self.assertEqual("edited", actions["owned.txt"])
        script = (Path(__file__).resolve().parents[2] / "install.sh").read_text(encoding="utf-8")
        self.assertIn('main "$@"', script)
        body = script.splitlines()
        while body and not body[-1].strip():
            body.pop()
        self.assertTrue(body[-1].startswith("main "))
        truncated = "\n".join(body[:-1]) + "\n"
        import os
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "install.sh"
            path.write_text(truncated, encoding="utf-8")
            path.chmod(0o755)
            completed = subprocess.run(
                ["sh", str(path)],
                cwd=temporary,
                env={**os.environ, "CHAOS_ENGINE_RESOLVE_ONLY": "1"},
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(0, completed.returncode)
        self.assertEqual("", completed.stdout)
        self.assertEqual("", completed.stderr)


def _install():
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("ce_install_receipt_stage", root / "install.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AddonReceiptStageTest(unittest.TestCase):
    def test_candidate_stage_does_not_seal_addon_receipts(self):
        install = _install()
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            receipt = source / "addons" / "shaft-engine-users" / "receipt.json"
            receipt.parent.mkdir(parents=True)
            receipt.write_text('{"tag":"1"}\n', encoding="utf-8")
            skill = source / "skills" / "chaos-engine" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("skill\n", encoding="utf-8")
            stage = Path(temporary) / "stage"
            stage.mkdir()
            ownership, payload_files, receipt_files = install.payload_ownership(source, [skill, receipt])
            install.copy_owned_payload(stage, source, payload_files, receipt_files, ownership)
            self.assertEqual(["skills/chaos-engine/SKILL.md"], sorted(ownership))
            self.assertTrue((stage / "addons" / "shaft-engine-users" / "receipt.json").is_file())
            self.assertEqual(ownership, install.installed_payload(stage))

    def test_legacy_sealed_receipt_backup_rotates_on_reinstall(self):
        install = _install()
        source = Path(__file__).resolve().parents[2]
        relative = "addons/shaft-engine-users/receipt.json"
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "consumer"
            project.mkdir()
            install.install(project, source, "1" * 40)
            target = project / ".chaos-engine"
            receipt = target / "addons" / "shaft-engine-users" / "receipt.json"
            receipt.parent.mkdir(parents=True, exist_ok=True)
            receipt.write_text('{"tag":"legacy"}\n', encoding="utf-8")
            manifest_path = target / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][relative] = hashlib.sha256(receipt.read_bytes()).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            self.assertNotIn(relative, install.installed_payload(target))
            install.verify_install(target)
            receipt.write_text('{"tag":"rewritten"}\n', encoding="utf-8")
            install.verify_install(target)
            self.assertEqual([], install.verify_payload_report(project)["drifted"])
            backup = project / install.BACKUP_NAME
            shutil.copytree(target, backup)
            owned = backup / "install.py"
            original = owned.read_bytes()
            owned.write_bytes(original + b"\n")
            with self.assertRaises(ValueError) as raised:
                install.verify_install(backup)
            self.assertIn(str(backup), str(raised.exception))
            owned.write_bytes(original)
            install.install(project, source, "2" * 40)
            install.verify_install(project / ".chaos-engine")
            self.assertFalse((project / ".chaos-engine.backup.next").exists())
            self.assertTrue((backup / relative).is_file())

    def test_archive_ignores_a_rewritten_legacy_receipt(self):
        install = _install()
        source = Path(__file__).resolve().parents[2]
        relative = "addons/shaft-engine-users/receipt.json"
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "consumer"
            project.mkdir()
            install.install(project, source, "1" * 40)
            target = project / ".chaos-engine"
            receipt = target / relative
            receipt.parent.mkdir(parents=True, exist_ok=True)
            receipt.write_text('{"tag":"legacy"}\n', encoding="utf-8")
            manifest_path = target / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][relative] = hashlib.sha256(b"old\n").hexdigest()
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            receipt.write_text('{"tag":"rewritten"}\n', encoding="utf-8")
            archive = project / "recovery.zip"
            install.archive_install(target, archive)
            self.assertTrue(archive.is_file())

    def test_uninstall_refuses_a_drifted_pack_neighbor(self):
        install = _install()
        source = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "consumer"
            project.mkdir()
            install.install(project, source, "1" * 40)
            neighbor = project / ".chaos-engine" / "packs" / "java" / "maven_tools.py"
            neighbor.write_bytes(neighbor.read_bytes() + b"\n")
            with self.assertRaises(ValueError) as raised:
                install.content_edits_allow_uninstall(project)
            self.assertIn("ownership drift", str(raised.exception))


class KeepEditsAndFallbackDownloadTest(unittest.TestCase):
    def test_keep_edits_ignores_receipts_and_matching_cr_bytes(self):
        boot = _bootstrap()
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            overlay = project / ".chaos-engine"
            overlay.mkdir()
            body = b"line\r\n"
            (overlay / "install.py").write_bytes(body)
            receipt = overlay / "addons" / "shaft-engine-users" / "receipt.json"
            receipt.parent.mkdir(parents=True)
            receipt.write_text('{"tag":"rewritten"}\n', encoding="utf-8")
            manifest = {
                "files": {
                    "install.py": hashlib.sha256(body).hexdigest(),
                    "addons/shaft-engine-users/receipt.json": "0" * 64,
                }
            }
            (overlay / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            self.assertEqual([], boot.verify_named_paths(overlay))
            (overlay / "install.py").write_bytes(b"edited\n")
            self.assertEqual(["install.py"], boot.verify_named_paths(overlay))

    def test_absolute_pack_script_and_bad_ref_do_not_run(self):
        boot = _bootstrap()
        with tempfile.TemporaryDirectory() as temporary:
            profile = Path(temporary) / "profile.json"
            profile.write_text(
                json.dumps({"postInstall": {"script": "/tmp/evil.py", "args": ["--install-shaft-cli"]}}) + "\n",
                encoding="utf-8",
            )
            self.assertIsNone(boot._post_install_entry(profile))
            calls: list[str] = []

            def opener(request, timeout=30):
                calls.append(getattr(request, "full_url", ""))
                raise OSError("network")

            with self.assertRaises(ValueError):
                boot.run_pack_post_install(
                    Path(temporary),
                    "ShaftHQ/SHAFT_ENGINE",
                    "main",
                    {"script": "scripts/mcp/install_shaft_agentic_tools.py", "args": [], "ref": "../main"},
                    opener=opener,
                )
            self.assertEqual([], calls)
            import os
            os.environ["CHAOS_ENGINE_OFFLINE"] = "1"
            try:
                with self.assertRaises(ValueError) as raised:
                    boot.run_pack_post_install(
                        Path(temporary),
                        "ShaftHQ/SHAFT_ENGINE",
                        "a" * 40,
                        {"script": "scripts/mcp/install_shaft_agentic_tools.py", "args": [], "ref": "main"},
                        opener=opener,
                    )
                self.assertIn("offline", str(raised.exception))
                self.assertEqual([], calls)
            finally:
                os.environ.pop("CHAOS_ENGINE_OFFLINE", None)

    def test_fallback_reuses_installed_bytes_and_the_blob_cache(self):
        import os

        boot = _bootstrap()
        skill = b"skill\n"
        cached = b"cached\n"
        fresh = b"fresh\n"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.environ["CHAOS_ENGINE_CACHE_DIR"] = str(root / "cache")
            try:
                project = root / "proj"
                installed = project / ".chaos-engine" / "skills" / "chaos-engine"
                installed.mkdir(parents=True)
                (installed / "SKILL.md").write_bytes(skill)
                cached_sha = boot.git_blob_sha1(cached)
                digest = hashlib.sha256(cached).hexdigest()
                boot.store_cached_blob(digest, cached)
                (project / ".chaos-engine" / "manifest.json").write_text(
                    json.dumps({"files": {"cached.txt": digest}}), encoding="utf-8"
                )
                calls: list[str] = []

                class Response:
                    def __init__(self, payload: bytes):
                        self.payload = payload

                    def __enter__(self):
                        return self

                    def __exit__(self, *args):
                        return False

                    def read(self, count=-1):
                        payload, self.payload = self.payload, b""
                        return payload if count < 0 else payload[:count]

                def opener(request, timeout=30):
                    calls.append(request.full_url)
                    return Response(fresh)

                selected = [
                    (boot.PurePosixPath("chaos-engine/skills/chaos-engine/SKILL.md"), len(skill), boot.git_blob_sha1(skill)),
                    (boot.PurePosixPath("chaos-engine/cached.txt"), len(cached), cached_sha),
                    (boot.PurePosixPath("chaos-engine/fresh.txt"), len(fresh), boot.git_blob_sha1(fresh)),
                ]
                destination = root / "dest"
                destination.mkdir()
                boot._write_selected_blobs(
                    selected,
                    sum(item[1] for item in selected),
                    set(),
                    encoded_repository="ShaftHQ/chaosengine-harness",
                    commit="c" * 40,
                    destination=destination,
                    opener=opener,
                    reporter=None,
                    root_layout=True,
                    project=project,
                )
                self.assertEqual(1, len(calls))
                self.assertIn("fresh.txt", calls[0])
                self.assertEqual(skill, (destination / "chaos-engine/skills/chaos-engine/SKILL.md").read_bytes())
                self.assertEqual(cached, (destination / "chaos-engine/cached.txt").read_bytes())
                self.assertEqual(fresh, (destination / "chaos-engine/fresh.txt").read_bytes())
            finally:
                os.environ.pop("CHAOS_ENGINE_CACHE_DIR", None)

    def test_tools_optional_only_when_skip_was_recorded(self):
        install = _install()
        source = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "consumer"
            project.mkdir()
            target = install.install(project, source, "1" * 40)

            class Host:
                def retrieval_configs_healthy(self, _project):
                    return True

                def maven_tools_cache_status(self):
                    return {"status": "absent"}

                def mempalace_runtime_status(self, _project):
                    return {"status": "healthy"}

            result = {"distribution": "portable", "status": "healthy"}
            install.attach_component_status(
                result, project, target, "absent", Host(), inspect_retrieval_state=False
            )
            self.assertNotEqual("optional", result["components"]["tools"].get("taskImpact"))
            install.mark_tools_skipped(target)
            marked = {"distribution": "portable", "status": "healthy"}
            install.attach_component_status(
                marked, project, target, "absent", Host(), inspect_retrieval_state=False
            )
            self.assertEqual("optional", marked["components"]["tools"]["taskImpact"])
            self.assertTrue(install.tools_were_skipped(target))
            payload = target / "install.py"
            inode = payload.stat().st_ino
            install.install(project, source, "1" * 40)
            self.assertEqual(inode, payload.stat().st_ino)
            self.assertFalse(install.tools_were_skipped(target))
            install.mark_tools_skipped(target)
            self.assertTrue(install.tools_were_skipped(target))

    def test_home_profile_does_not_download_and_sealed_pins_commit(self):
        import io
        import os
        import types
        from contextlib import redirect_stderr

        boot = _bootstrap()
        commit = "ab" * 20
        script = "scripts/mcp/install_shaft_agentic_tools.py"
        profile = {
            "name": "shaft",
            "repository": "evil/repo",
            "defaultBranch": "main",
            "postInstall": {"script": script, "args": ["--install-shaft-cli"]},
        }
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            home = project / "shaft-skills" / "ce-pack"
            home.mkdir(parents=True)
            (home / "entrypoint.md").write_text("entrypoint\n", encoding="utf-8")
            (home / "profile.json").write_text(json.dumps(profile) + "\n", encoding="utf-8")
            entries = boot.pack_post_installs(project)
            self.assertEqual([True], [entry["home"] for entry in entries])
            calls: list[str] = []

            def opener(request, timeout=30):
                calls.append(getattr(request, "full_url", str(request)))
                raise OSError("network")

            with self.assertRaises(ValueError) as raised:
                boot.run_pack_post_install(
                    project, "ShaftHQ/chaosengine-harness", commit, entries[0], opener=opener,
                )
            self.assertIn("no local script", str(raised.exception))
            self.assertEqual([], calls)
            local = project.joinpath(*script.split("/"))
            local.parent.mkdir(parents=True)
            local.write_text("print('local')\n", encoding="utf-8")
            ran: list[list[str]] = []

            def runner(argv, cwd=None, check=False):
                ran.append(list(argv))
                return types.SimpleNamespace(returncode=0)

            code = boot.run_pack_post_install(
                project, "ShaftHQ/chaosengine-harness", commit, entries[0], opener=opener, runner=runner,
            )
            self.assertEqual(0, code)
            self.assertEqual([], calls)
            self.assertIn(str(local), ran[0][1])
            local.unlink()
            sealed = project / ".chaos-engine" / "packs" / "shaft" / "profile.json"
            sealed.parent.mkdir(parents=True)
            sealed.write_text(json.dumps(profile) + "\n", encoding="utf-8")
            shutil.rmtree(home)
            sealed_entries = boot.pack_post_installs(project)
            self.assertEqual([False], [entry["home"] for entry in sealed_entries])
            urls: list[str] = []
            original = boot.read_response

            def read_response(_opener, url, **_kwargs):
                urls.append(url)
                return b"raise SystemExit(0)\n"

            boot.read_response = read_response
            try:
                code = boot.run_pack_post_install(
                    project,
                    "ShaftHQ/chaosengine-harness",
                    commit,
                    sealed_entries[0],
                    opener=opener,
                    runner=runner,
                )
            finally:
                boot.read_response = original
            self.assertEqual(0, code)
            self.assertEqual(1, len(urls))
            self.assertIn(f"ShaftHQ/chaosengine-harness/{commit}/", urls[0])
            self.assertNotIn("evil", urls[0])
            self.assertNotIn("/main/", urls[0])
            self.assertEqual([], calls)

            def explode(_opener, url, **_kwargs):
                raise boot.UpstreamReadError("unable to download", url_path="/shaft", http_status=500)

            boot.read_response = explode
            args = types.SimpleNamespace(
                project=str(project),
                repository="ShaftHQ/chaosengine-harness",
                branch=commit,
                skip_pack_post_install=False,
            )
            stderr = io.StringIO()
            try:
                with redirect_stderr(stderr):
                    exit_code = boot.post_install_packs(args, {"commit": commit})
                boot.read_response = lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    RuntimeError("GitHub API rate limit reached")
                )
                with redirect_stderr(stderr):
                    limited = boot.post_install_packs(args, {"commit": commit})
            finally:
                boot.read_response = original
                os.environ.pop("CHAOS_ENGINE_OFFLINE", None)
            self.assertEqual(1, exit_code)
            self.assertEqual(1, limited)
            text = stderr.getvalue()
            self.assertIn("ChaosEngine itself is installed", text)
            self.assertIn("could not start", text)
