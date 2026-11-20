"""Log the URL when a contract-cell child receives an HTTP error.

Imported automatically through PYTHONPATH. The URL query is omitted so a token
in a signed link is not written to the job log.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.parse
import urllib.request

_original = urllib.request.urlopen


def _safe_url(url: object) -> str:
    raw = getattr(url, "full_url", None) or str(url)
    parts = urllib.parse.urlsplit(raw)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _urlopen(url, data=None, timeout=None, *args, **kwargs):
    try:
        if timeout is None:
            return _original(url, data, *args, **kwargs)
        return _original(url, data, timeout, *args, **kwargs)
    except urllib.error.HTTPError as error:
        if error.code in {403, 429}:
            target = getattr(error, "url", None) or url
            sys.stderr.write(
                f"installer-contract: HTTP {error.code} {error.reason} {_safe_url(target)}\n"
            )
        raise


urllib.request.urlopen = _urlopen
