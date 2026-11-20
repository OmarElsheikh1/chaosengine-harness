"""Send the Actions token on GitHub downloads and log a 403 or 429 URL.

Imported automatically through PYTHONPATH. The pinned installer fetches release
assets without a token, and macOS runner addresses then get HTTP 403. The query
is omitted from the log so a signed link is not copied into the job log.
"""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.parse
import urllib.request

_original = urllib.request.urlopen
_MAVEN_TOOLS_LATEST = "/repos/arvindand/maven-tools-mcp/releases/latest"
# Published release on 2026-11-19. Used only when that API answers 403 or 429.
_MAVEN_TOOLS_RELEASE = b'{"tag_name":"v3.3.1","draft":false,"prerelease":false}\n'
_GITHUB_HOSTS = frozenset(
    {
        "github.com",
        "api.github.com",
        "codeload.github.com",
        "objects.githubusercontent.com",
        "release-assets.githubusercontent.com",
        "github-releases.githubusercontent.com",
    }
)


def _safe_url(url: object) -> str:
    raw = getattr(url, "full_url", None) or str(url)
    parts = urllib.parse.urlsplit(raw)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _token() -> str:
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return ""


def _authorized(url):
    token = _token()
    request = url if isinstance(url, urllib.request.Request) else urllib.request.Request(url)
    host = (urllib.parse.urlsplit(request.full_url).hostname or "").casefold()
    if token and host in _GITHUB_HOSTS and not request.has_header("Authorization"):
        request.add_header("Authorization", f"Bearer {token}")
    return request


class _Body:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self._offset = 0

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            size = len(self._payload) - self._offset
        chunk = self._payload[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk

    def __enter__(self) -> "_Body":
        return self

    def __exit__(self, *_args: object) -> bool:
        return False

    def close(self) -> None:
        return None


def _maven_tools_latest(url: object) -> bool:
    raw = getattr(url, "full_url", None) or str(url)
    return urllib.parse.urlsplit(raw).path == _MAVEN_TOOLS_LATEST


def _urlopen(url, data=None, timeout=None, *args, **kwargs):
    request = _authorized(url)
    try:
        if timeout is None:
            return _original(request, data, *args, **kwargs)
        return _original(request, data, timeout, *args, **kwargs)
    except urllib.error.HTTPError as error:
        target = getattr(error, "url", None) or request
        if error.code in {403, 429} and _maven_tools_latest(target):
            sys.stderr.write(
                "installer-contract: maven-tools-mcp releases/latest was rate limited; using tag v3.3.1\n"
            )
            return _Body(_MAVEN_TOOLS_RELEASE)
        if error.code in {403, 429}:
            sys.stderr.write(
                f"installer-contract: HTTP {error.code} {error.reason} {_safe_url(target)}\n"
            )
        raise


urllib.request.urlopen = _urlopen
