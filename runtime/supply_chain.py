"""Outside-skill supply-chain refusal gate.

The gate checks tier, a pin or content hash, an injected-instruction scan, and
provenance. It never installs files. Signing is optional and not implemented.
"""

from __future__ import annotations

import hashlib
import importlib.util
import re
import sys
from pathlib import Path

POLICY_RELATIVE = "docs/skill-supply-chain.md"
CORE_TIER = "core"
COMMUNITY_TIER = "community"
NEVER_AUTO_TRUST = frozenset({"web", "tool-output", "other-agent", "unknown"})
TRUST_VALUES = frozenset({"trusted", "verified", "quarantined"})

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ignore-previous", re.compile(r"ignore\s+(?:all\s+)?previous", re.IGNORECASE)),
    ("override-ethics", re.compile(r"override\s+ethics", re.IGNORECASE)),
    ("exfiltrate", re.compile(r"exfiltrate", re.IGNORECASE)),
    (
        "hidden-html-instruction",
        re.compile(r"<!--[\s\S]{0,400}?ignore\s+previous", re.IGNORECASE),
    ),
    (
        "hidden-markup",
        re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden", re.IGNORECASE),
    ),
)


class OutsideSkill:
    """One outside skill submitted for a decision. Bytes stay with the caller."""

    def __init__(
        self,
        name: str,
        body: str,
        tier: str = "",
        version: str = "",
        content_hash: str = "",
        origin: str = "",
        trust: str = "",
        verified_by: str = "",
        verified_at: str = "",
        explicit: bool = False,
        policy_present: bool = False,
        signature: str = "",
        core_names: frozenset[str] = frozenset(),
        allow: tuple[tuple[str, str], ...] = (),
    ) -> None:
        self.name = name
        self.body = body
        self.tier = tier
        self.version = version
        self.content_hash = content_hash
        self.origin = origin
        self.trust = trust
        self.verified_by = verified_by
        self.verified_at = verified_at
        self.explicit = explicit
        self.policy_present = policy_present
        self.signature = signature
        self.core_names = core_names
        self.allow = allow


def content_hash(data: bytes) -> str:
    """SHA-256 hex digest of skill bytes. This is the pin, not a signature."""
    return hashlib.sha256(data).hexdigest()


def core_skill_names() -> frozenset[str]:
    """Portable and vendor skill names. Community must not override these."""
    path = Path(__file__).resolve().with_name("harness_index.py")
    spec = importlib.util.spec_from_file_location("_ce_supply_harness_index", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    harness_index = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness_index)
    names = {row[0] for row in harness_index.SKILLS}
    names.update(row[0] for row in harness_index.VENDOR)
    return frozenset(names)


def policy_document_present(root: Path) -> bool:
    """True when the written policy is in force at root. Absence means refuse."""
    path = Path(root) / POLICY_RELATIVE
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8").casefold()
    required = ("core", "community", "hash", "scan", "provenance", "ethics", "optional")
    return all(word in text for word in required)


def included_in_default_portable(tier: str) -> bool:
    """Community skills are not in the default portable payload."""
    return tier == CORE_TIER


def scan_skill_text(text: str, allow: tuple[tuple[str, str], ...] = ()) -> list[str]:
    """Fail closed on injected-instruction patterns.

    An allow entry is one pattern name plus a documented reason. A blank reason
    does not silence the finding. There is no global off switch.
    """
    reasons = {name: reason for name, reason in allow}
    if "all" in reasons or "*" in reasons:
        return ["injected-instruction scan has no global off switch"]
    findings: list[str] = []
    for name, pattern in _PATTERNS:
        if name in reasons:
            if not str(reasons[name]).strip():
                findings.append(f"allow-list entry {name} has no documented reason")
            continue
        if pattern.search(text):
            findings.append(name)
    return findings


def scan_skill_tree(root: Path, allow: tuple[tuple[str, str], ...] = ()) -> list[str]:
    """Scan every text file under a skill tree, including non-skill assets."""
    findings: list[str] = []
    root = Path(root)
    if not root.exists():
        return findings
    paths = [root] if root.is_file() else sorted(path for path in root.rglob("*") if path.is_file())
    for path in paths:
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        if b"\0" in raw:
            continue
        for hit in scan_skill_text(raw.decode("utf-8", errors="ignore"), allow):
            findings.append(f"{hit} in {path.name}")
    return findings


def pin_mismatch(path: Path, expected: str) -> str | None:
    """Return an error when on-disk bytes do not match the pinned hash."""
    try:
        actual = content_hash(Path(path).read_bytes())
    except OSError as exc:
        return f"pin unreadable for {path}: {exc}"
    if actual != expected:
        return f"pin mismatch for {path}: expected {expected} got {actual}"
    return None


def lock_entry(name: str, body: bytes, version: str) -> dict[str, str]:
    """One community lock row. Version and hash are both recorded."""
    return {
        "name": name,
        "tier": COMMUNITY_TIER,
        "version": version,
        "content_hash": content_hash(body),
    }


def refusal_reason(request: OutsideSkill) -> str | None:
    """Why an outside skill is refused, or None when the policy is satisfied."""
    reasons: list[str] = []
    if not request.policy_present:
        reasons.append("supply-chain policy is not in force")
    if request.tier != COMMUNITY_TIER:
        reasons.append("outside skill tier must be community")
    names = request.core_names or core_skill_names()
    if request.name.casefold() in {item.casefold() for item in names}:
        reasons.append(f"name collision with core skill {request.name}")
    if not request.explicit:
        reasons.append("community install requires an explicit owner action")
    if not request.version and not request.content_hash:
        reasons.append("pin or content hash required")
    if request.content_hash and request.content_hash != content_hash(request.body.encode("utf-8")):
        reasons.append("content hash does not match the skill bytes")
    findings = scan_skill_text(request.body, request.allow)
    if request.signature and findings:
        findings = [*findings, "signature does not skip the scan"]
    if findings:
        reasons.append("injected-instruction scan failed: " + ", ".join(findings))
    reasons.extend(_provenance_reasons(request))
    if not reasons:
        return None
    return "; ".join(reasons)


def _provenance_reasons(request: OutsideSkill) -> list[str]:
    if not request.origin or not request.trust:
        return ["provenance required"]
    reasons: list[str] = []
    if request.trust not in TRUST_VALUES:
        reasons.append("provenance trust is outside the memory-provenance vocabulary")
    if request.origin in NEVER_AUTO_TRUST and request.trust != "quarantined":
        reasons.append("web, tool-output, and other-agent origins are never auto-trusted")
    if request.trust == "verified" and (not request.verified_by or not request.verified_at):
        reasons.append("verified provenance needs verifiedBy and verifiedAt")
    if request.trust == "trusted":
        reasons.append("community skills start quarantined, not trusted")
    return reasons


def _flag_map(args: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    index = 0
    while index < len(args):
        token = args[index]
        if token.startswith("--") and index + 1 < len(args):
            fields[token[2:]] = args[index + 1]
            index += 2
            continue
        index += 1
    return fields


def main(arguments: list[str] | None = None) -> int:
    """`tool.py supply-chain`: pin check and provenance. Exit 1 is a real miss."""
    args = list(sys.argv[1:] if arguments is None else arguments)
    if not args or args[0] in {"-h", "--help"}:
        print(
            "usage: tool.py supply-chain pin PATH HASH\n"
            "       tool.py supply-chain provenance --name NAME --origin ORIGIN --trust TRUST",
            file=sys.stderr,
        )
        return 2
    if args[0] == "pin":
        if len(args) != 3:
            print("usage: tool.py supply-chain pin PATH HASH", file=sys.stderr)
            return 2
        mismatch = pin_mismatch(Path(args[1]), args[2])
        if mismatch:
            print(mismatch, file=sys.stderr)
            return 1
        print("pin ok")
        return 0
    if args[0] == "provenance":
        fields = _flag_map(args[1:])
        origin = fields.get("origin", "")
        trust = fields.get("trust", "")
        if not origin or not trust:
            print("provenance required", file=sys.stderr)
            return 1
        print(
            f"name={fields.get('name', '')} tier={fields.get('tier', COMMUNITY_TIER)} "
            f"origin={origin} trust={trust}"
        )
        return 0
    print("usage: tool.py supply-chain pin|provenance", file=sys.stderr)
    return 2


def stage_outside_skill(dest: Path, request: OutsideSkill) -> dict[str, object]:
    """Decide an outside skill. Never writes dest, even when the policy passes.

    Signing is reported as optional and not implemented. A signature is not a pass.
    """
    if not isinstance(dest, Path):
        raise TypeError("dest must be a path; this gate does not create it")
    reason = refusal_reason(request)
    return {
        "accepted": reason is None,
        "installed": False,
        "reason": reason,
        "signing": "optional-not-implemented",
    }
