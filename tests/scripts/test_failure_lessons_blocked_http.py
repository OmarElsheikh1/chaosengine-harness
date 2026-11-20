"""Blocked HTTP URL, one-request retry, and sqlite close (#failure lessons)."""

from __future__ import annotations

import importlib.util
import io
import json
import sqlite3
import tempfile
import time
import unittest
import unittest.mock as mock
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
DEPENDENCIES = ROOT / "runtime" / "dependencies.py"
INSTALLER = ROOT / "install.py"


def load_dependencies():
    spec = importlib.util.spec_from_file_location("ce_failure_lesson_dependencies", DEPENDENCIES)
    if spec is None or spec.loader is None:
        raise RuntimeError("dependency controller could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_installer():
    spec = importlib.util.spec_from_file_location("ce_failure_lesson_installer", INSTALLER)
    if spec is None or spec.loader is None:
        raise RuntimeError("installer could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _http(url: str, code: int, reason: str, headers: dict[str, str] | None = None):
    return urllib.error.HTTPError(url, code, reason, headers or {}, None)


class OpenWithRetryLessonTest(unittest.TestCase):
    URL = "https://api.github.com/repos/a/b/releases/latest?access_token=should-not-leak"

    def setUp(self):
        self.module = load_dependencies()

    def test_rate_limit_403_retries_once_then_returns_body(self):
        body = object()
        error = _http(self.URL, 403, "rate limit exceeded", {"Retry-After": "5"})
        opener = mock.Mock(side_effect=[error, body])
        sleeper = mock.Mock()
        found = self.module._open_with_retry(
            opener, urllib.request.Request(self.URL), timeout=5, sleeper=sleeper
        )
        self.assertIs(body, found)
        self.assertEqual(2, opener.call_count)
        sleeper.assert_called_once_with(5.0)

    def test_rate_limit_403_second_failure_names_status_and_safe_path(self):
        opener = mock.Mock(
            side_effect=[
                _http(self.URL, 403, "rate limit exceeded", {"Retry-After": "5"}),
                _http(self.URL, 403, "rate limit exceeded", {"Retry-After": "5"}),
            ]
        )
        sleeper = mock.Mock()
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self.module._open_with_retry(opener, self.URL, timeout=5, sleeper=sleeper)
        self.assertEqual(2, opener.call_count)
        sleeper.assert_called_once_with(5.0)
        message = str(raised.exception)
        self.assertIn("403", message)
        self.assertIn("/repos/a/b/releases/latest", message)
        self.assertNotIn("should-not-leak", message)
        self.assertNotIn("access_token", message)

    def test_forbidden_403_without_retry_after_is_not_retried(self):
        opener = mock.Mock(side_effect=_http(self.URL, 403, "Forbidden", {}))
        sleeper = mock.Mock()
        with self.assertRaises(urllib.error.HTTPError):
            self.module._open_with_retry(opener, self.URL, timeout=5, sleeper=sleeper)
        self.assertEqual(1, opener.call_count)
        sleeper.assert_not_called()

    def test_non_http_error_message_is_unchanged(self):
        opener = mock.Mock(side_effect=ValueError("maven pin rejected"))
        sleeper = mock.Mock()
        with self.assertRaises(ValueError) as raised:
            self.module._open_with_retry(opener, self.URL, timeout=5, sleeper=sleeper)
        self.assertEqual("maven pin rejected", str(raised.exception))
        self.assertEqual(1, opener.call_count)
        sleeper.assert_not_called()

    def test_rate_limit_reset_without_retry_after_waits_once_then_fails(self):
        reset = str(int(time.time()) + 10_000)
        error = _http(
            self.URL,
            403,
            "rate limit exceeded",
            {"X-RateLimit-Reset": reset},
        )
        opener = mock.Mock(side_effect=error)
        sleeper = mock.Mock()
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self.module._open_with_retry(opener, self.URL, timeout=5, sleeper=sleeper)
        self.assertEqual(1, opener.call_count)
        sleeper.assert_called_once_with(60.0)
        message = str(raised.exception)
        self.assertIn("403", message)
        self.assertIn("/repos/a/b/releases/latest", message)
        self.assertNotIn("should-not-leak", message)


class BlockedHttpReasonTest(unittest.TestCase):
    def test_report_blocked_names_status_path_and_rate_headers(self):
        installer = load_installer()
        url = "https://user:sekret@api.github.com/repos/a/b?access_token=should-not-leak#frag"
        error = _http(
            url,
            403,
            "rate limit exceeded",
            {
                "Retry-After": "5",
                "X-RateLimit-Remaining": "3",
                "X-RateLimit-Reset": "1700000000",
            },
        )
        args = SimpleNamespace(json=True, command="install", project=None)
        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout):
            self.assertEqual(1, installer._report_blocked(args, error))
        payload = json.loads(stdout.getvalue())
        reason = payload["reason"]
        self.assertIn("403", reason)
        self.assertIn("rate limit exceeded", reason)
        self.assertIn("/repos/a/b", reason)
        self.assertIn("Retry-After: 5", reason)
        self.assertIn("X-RateLimit-Remaining: 3", reason)
        self.assertIn("X-RateLimit-Reset: 1700000000", reason)
        self.assertNotIn("should-not-leak", reason)
        self.assertNotIn("sekret", reason)
        self.assertNotIn("is spent", reason)

        text_args = SimpleNamespace(json=False, command="install", project=None)
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            installer._report_blocked(text_args, error)
        printed = stderr.getvalue()
        self.assertIn("reason:", printed)
        self.assertIn("403", printed)
        self.assertIn("/repos/a/b", printed)
        self.assertIn("Retry-After: 5", printed)
        self.assertNotIn("should-not-leak", printed)
        self.assertNotIn("sekret", printed)


class SqliteCloseLessonTest(unittest.TestCase):
    def test_exact_target_checkpoints_and_closes_when_checkpoint_fails(self):
        module = load_dependencies()
        connection = mock.MagicMock()
        connection.execute.side_effect = sqlite3.Error("checkpoint failed")

        def connect(database, *args, **kwargs):
            Path(database).touch()
            return connection

        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(module.sqlite3, "connect", side_effect=connect):
                module.ensure_mempalace_exact_target(Path(temporary))
        connection.execute.assert_any_call("PRAGMA wal_checkpoint(TRUNCATE)")
        connection.close.assert_called_once()
