# Changelog

## 1.0.0
- Core functionality completed: internal encrypted execution and plaintext storage/retrieval interfaces.
- External scripts can call and operate on internal encrypted information.

## 1.1.0
- Encryption & Protection: cross‑environment/system migration, root‑key rotation, protection mode.
- Operational Auditing: database audit logging.
- Interaction Overhaul: MCP-based interaction; WebUI interaction (Tkinter removed).
- Scenario Enhancements: encrypted execution of internal scripts.

## 1.2.0
- Interaction Overhaul: WebUI manual input/extraction.
- Scenario Enhancements: single-call encrypted chaining of internal scripts, stored information, and prompts.
- Encryption & Protection: migration disabled under protection mode.
- Additional experience and performance improvements.

## 1.3.0
- Packaging & engineering improvements for multi-platform and multi‑Python‑version distribution.

## 1.3.3
- Fixed MCP auto-start MGC; optimized MCP interaction.
- Other: hide copy skill button in Safari; updated skill_spec.md with MCP config.

## 1.4.0
- NEW: Seal script for external node execution (mgc_seal).
- NEW: Get page Smart Seal detection for stored data.
- Enhanced MCP tools with improved descriptions.
- Optimized UI interactions and field truncation.
- Fixed ext01-ext30 fields in SEAL response.

## 1.4.1
- Fixed missing BaseDialog import in WebUI.
- MCP: Improved UTF-8 encoding for requests.
- MCP: Filter None values from request payload.
- Note: MCP tools may not support Chinese content (use WebUI or REST API).

## 1.4.2
- REMOVED: Remote Gist heartbeat collection (privacy-first).
- Disabled hardcoded GitHub PAT token.
- Heartbeat now defaults to OFF; can be enabled via config.
- Improved security: zero telemetry, local-only operation.

## 1.4.3
- Fixed MCP ext parameters not passing to API.
- Fixed sealed script run returning null.
- Added minimal response for sealed script execution (security).
- Updated skill_spec.md with ext field protocol.
- Updated WebUI seal to use ext04 for node_pub.
