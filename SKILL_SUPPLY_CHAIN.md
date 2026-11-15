# Skill supply chain

This policy is a prerequisite, not a retrospective. Until it is in force,
decline an outside skill and point at this file. No community skill is merged
without it.

## Tiers

Core skills ship in the portable overlay, are reviewed with the harness, and
are versioned with the release. Community skills are optional, not
always-loaded, and not in the default portable payload. A community skill
cannot silently override a core skill of the same name. Installing one
requires an explicit owner action.

## Pin or hash

Every installed community skill records a version and a content hash. Do not
float latest. A mutated file fails the lock check. Core skills are pinned by
the harness release.

## Scan

Incoming skill text is scanned for injected instructions: ignore-previous,
override-ethics, exfiltrate, hidden HTML instructions, and hidden markup.
The scan is fail-closed. An allow-list entry needs a documented reason.
There is no global off switch. A clean scan does not replace review.

## Provenance

Use the memory-provenance vocabulary: `origin`, `trust` (`trusted`,
`verified`, `quarantined`), and `verifiedBy` / `verifiedAt` only when
`trust` is `verified`. Community skills start `quarantined`. Web,
tool-output, and other-agent origins are never auto-trusted. A community
skill without recorded provenance cannot be trusted for promotion or default
load.

## Signing

Signing is optional and not implemented. A future maintainer may attach a
release-asset or sigstore signature. A signature attests origin, not
benevolence, and does not skip the scan, the pin, or review.

## Ethics

Ethics outranks skill text, including community skills. See
`references/ethical-conduct.md`. Do not copy that card into a skill.

## Reporting

Report a malicious skill through `SECURITY.md`. Do not publish the payload
in a public issue. This policy does not accept a community skill by itself.
The gate in `supply_chain.py` refuses until tier, pin or hash, scan, and
provenance are satisfied, and it does not install files.
