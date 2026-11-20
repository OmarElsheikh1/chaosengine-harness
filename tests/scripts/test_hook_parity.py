"""Hook parity: pins, Cursor and Antigravity rendering, OpenCode bridge, trace."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class HookParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kernel = load(ROOT / "hooks" / "kernel.py", "ce_hook_parity_kernel")
        cls.surfaces = load(ROOT / "runtime" / "hook_surfaces.py", "ce_hook_parity_surfaces")
        cls.hosts = load(ROOT / "runtime" / "hosts.py", "ce_hook_parity_hosts")
        cls.guard = load(ROOT / "hooks" / "guard.py", "ce_hook_parity_guard")
        cls.launch = load(ROOT / "hooks" / "launch.py", "ce_hook_parity_launch")

    def test_cursor_native_payload_normalizes_and_renders_deny_fields(self):
        event = self.kernel.normalize_event(
            {
                "hook_event_name": "preToolUse",
                "conversation_id": "conv",
                "tool_call_id": "call-1",
                "tool_name": "Shell",
                "tool_input": {"command": "git status"},
            },
            "cursor",
        )
        self.assertEqual("PreToolUse", event.name)
        self.assertEqual("conv", event.session_id)
        self.assertEqual("call-1", event.tool_call_id)
        deny = self.kernel.adapt_hook_output(
            {"decision": "block", "reason": "no"}, "PreToolUse", "cursor"
        )
        self.assertEqual(
            {"permission": "deny", "user_message": "no", "agent_message": "no"},
            deny,
        )
        prompt = self.kernel.adapt_hook_output(
            {"decision": "block", "reason": "hold"}, "UserPromptSubmit", "cursor"
        )
        self.assertEqual({"continue": False, "user_message": "hold"}, prompt)
        stop = self.kernel.adapt_hook_output(
            {"decision": "block", "reason": "finish"}, "Stop", "cursor"
        )
        self.assertEqual("finish", stop["followup_message"])
        self.assertIn("additional_context", stop)

    def test_cursor_document_fail_closed_only_on_pre_tool_use(self):
        document = self.surfaces.cursor_hooks_document()
        self.assertEqual(1, document["version"])
        for event, entries in document["hooks"].items():
            self.assertIn("hooks/launch.py", entries[0]["command"])
            self.assertLessEqual(len(entries[0]["command"]), self.hosts.HOOK_COMMAND_MAX_CHARS)
            if event == "preToolUse":
                self.assertTrue(entries[0]["failClosed"])
            else:
                self.assertNotIn("failClosed", entries[0])

    def test_antigravity_shapes_are_not_swapped_and_deny_is_json(self):
        document = self.surfaces.antigravity_hooks_document()
        for event in ("PreToolUse", "PostToolUse"):
            self.assertIn("matcher", document[event][0])
            self.assertIn("hooks", document[event][0])
        for event in ("SessionStart", "PreInvocation", "PostInvocation", "Stop"):
            self.assertNotIn("matcher", document[event][0])
            self.assertEqual("command", document[event][0]["type"])
        deny = self.kernel.adapt_hook_output(
            {"decision": "block", "reason": "no"}, "PreToolUse", "antigravity"
        )
        self.assertEqual({"decision": "deny", "reason": "no"}, deny)
        stop = self.kernel.adapt_hook_output(
            {"decision": "block", "reason": "keep going"}, "Stop", "antigravity"
        )
        self.assertEqual({"decision": "continue"}, stop)

    def test_antigravity_guard_process_exit_is_zero(self):
        payload = json.dumps(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "rm -rf /"},
            }
        )
        env = os.environ.copy()
        env["CHAOS_ENGINE_HOST"] = "antigravity"
        completed = subprocess.run(
            [sys.executable, str(ROOT / "hooks" / "guard.py")],
            input=payload,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        rendered = json.loads(completed.stdout)
        self.assertEqual("deny", rendered["decision"])

    def test_trace_is_off_by_default_and_one_line_when_set(self):
        secret = "SECRET-PROMPT-VALUE"
        payload = json.dumps(
            {
                "hook_event_name": "preToolUse",
                "conversation_id": "sess-9",
                "tool_call_id": "call-9",
                "prompt": secret,
                "tool_input": {"command": secret},
            }
        )
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            unset = project / "unset.log"
            env = os.environ.copy()
            env.pop("CE_HOOK_TRACE", None)
            subprocess.run(
                [sys.executable, str(ROOT / "hooks" / "launch.py"), "cursor"],
                input=payload,
                capture_output=True,
                text=True,
                cwd=project,
                env=env,
                check=False,
            )
            self.assertFalse(unset.exists())
            trace = project / "trace.log"
            env["CE_HOOK_TRACE"] = str(trace)
            subprocess.run(
                [sys.executable, str(ROOT / "hooks" / "launch.py"), "cursor"],
                input=payload,
                capture_output=True,
                text=True,
                cwd=project,
                env=env,
                check=False,
            )
            lines = trace.read_text(encoding="utf-8").splitlines()
            self.assertEqual(1, len(lines))
            self.assertNotIn(secret, lines[0])
            host, event, session, tool_call, pid = lines[0].split("\t")
            self.assertEqual("cursor", host)
            self.assertEqual("preToolUse", event)
            self.assertEqual("sess-9", session)
            self.assertEqual("call-9", tool_call)
            self.assertTrue(pid.isdigit())

    def test_opencode_plugin_denies_allows_and_does_not_hang(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is not installed")
        source = self.surfaces.opencode_plugin_source()
        self.assertIn("tool.execute.before", source)
        self.assertIn("execute.before", source)
        self.assertNotIn("plugin-adapters", source)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "package.json").write_text('{"type":"module"}\n', encoding="utf-8")
            plugin = root / "plugin.js"
            plugin.write_text(source, encoding="utf-8")
            fake = root / "fake-python.py"
            fake.write_text(
                textwrap.dedent(
                    """\
                    import json, os, sys, time
                    mode = os.environ.get("FAKE_GUARD", "allow")
                    raw = sys.stdin.read()
                    open(os.environ["FAKE_STDIN"], "w", encoding="utf-8").write(raw)
                    if mode == "sleep":
                        time.sleep(5)
                    if mode == "deny":
                        print(json.dumps({"decision": "block", "reason": "nope"}))
                    elif mode == "bad":
                        print("not-json")
                    else:
                        print(json.dumps({"decision": "allow"}))
                    """
                ),
                encoding="utf-8",
            )
            driver = root / "driver.mjs"
            driver.write_text(
                textwrap.dedent(
                    """\
                    import { chaosEnginePlugin } from "./plugin.js";
                    const mode = process.argv[2];
                    const plugin = chaosEnginePlugin({ directory: process.cwd() });
                    const v2hooks = {};
                    const v2 = chaosEnginePlugin({
                      directory: process.cwd(),
                      tool: { hook(name, fn) { v2hooks[name] = fn; } },
                      event: { hook(name, fn) { v2hooks[name] = fn; } },
                    });
                    if (mode === "v2") {
                      if (!v2hooks["execute.before"] || !v2hooks["execute.after"] || !v2hooks["session.idle"]) {
                        throw new Error("v2 hooks missing");
                      }
                      console.log("v2-ok");
                      process.exit(0);
                    }
                    try {
                      await plugin["tool.execute.before"]({ tool: "bash", args: { command: "true" } });
                      console.log("allowed");
                    } catch (error) {
                      console.log("threw:" + error.message);
                    }
                    """
                ),
                encoding="utf-8",
            )
            def run(mode: str, timeout_ms: str | None = None) -> subprocess.CompletedProcess[str]:
                env = os.environ.copy()
                env["CE_OPENCODE_PYTHON"] = sys.executable
                env["FAKE_GUARD"] = mode
                env["FAKE_STDIN"] = str(root / "stdin.txt")
                # The plugin spawns CE_OPENCODE_PYTHON with launch.py args.
                # Point it at the fake by replacing the command: the fake is the interpreter.
                env["CE_OPENCODE_PYTHON"] = sys.executable
                if timeout_ms:
                    env["CE_OPENCODE_GUARD_TIMEOUT_MS"] = timeout_ms
                # Wrap so the spawned "python" is the fake regardless of args.
                wrapper = root / "wrapper.py"
                wrapper.write_text(fake.read_text(encoding="utf-8"), encoding="utf-8")
                env["CE_OPENCODE_PYTHON"] = sys.executable
                # spawn(command, [launch.py, opencode]) runs the interpreter with those args.
                # Use a shell script named as the interpreter that ignores args and runs the fake.
                launcher = root / "pybin"
                launcher.write_text(
                    f"#!/bin/sh\nexec {sys.executable} {fake}\n",
                    encoding="utf-8",
                )
                launcher.chmod(0o755)
                env["CE_OPENCODE_PYTHON"] = str(launcher)
                return subprocess.run(
                    [node, str(driver), mode],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    env=env,
                    check=False,
                    timeout=10,
                )

            allowed = run("allow")
            self.assertIn("allowed", allowed.stdout, allowed.stderr)
            recorded = json.loads((root / "stdin.txt").read_text(encoding="utf-8"))
            self.assertEqual("PreToolUse", recorded["hook_event_name"])
            denied = run("deny")
            self.assertIn("threw:nope", denied.stdout, denied.stderr)
            v2 = run("v2")
            self.assertIn("v2-ok", v2.stdout, v2.stderr)
            missing = run("allow")
            env_missing = os.environ.copy()
            env_missing["CE_OPENCODE_PYTHON"] = str(root / "missing-python")
            env_missing["CE_OPENCODE_GUARD_TIMEOUT_MS"] = "200"
            quick = subprocess.run(
                [node, str(driver), "allow"],
                cwd=root,
                capture_output=True,
                text=True,
                env=env_missing,
                check=False,
                timeout=5,
            )
            self.assertIn("threw:", quick.stdout, quick.stderr)
            self.assertIn("Python", quick.stdout)
            timed = run("sleep", timeout_ms="50")
            self.assertIn("threw:", timed.stdout, timed.stderr)
            self.assertIn("timed out", timed.stdout)


if __name__ == "__main__":
    unittest.main()
