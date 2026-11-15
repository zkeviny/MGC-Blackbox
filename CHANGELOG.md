# Changelog

## 1.6.0
- **Chain mode — split one task across multiple devices**: one orchestrated task can now be split into one sealed sub-package per target node — each node receives only the files it was granted, and can decrypt and run only those. Useful when a single workflow needs several devices to cooperate, with each device seeing only its own part of the task. Producing nodes need mgc 1.6.0+; receiving nodes only need 1.5.4+.
- **A2A protocol adaptation**: sealed packages can now be converted to and from A2A 1.0 structures, so a task package can travel over agent-to-agent messaging. MGC itself does not handle transport — the agent decides how the package travels.
- **Skill spec updated**: new chain mode coverage in the skill document — when to use it, how to seal for multiple nodes, and how a receiving node imports and runs its sub-package.

## 1.5.4
- **Seal free mode**: a single script or workflow file can now be sealed without passing `node_pub`; the package stays encrypted but any mgc node can import it and run.
- **Link authorization**: sealed packages are bound to the source node; any modification to the package prevents it from being decrypted and run again.
- **New MCP tool: `mgc_delete`**: agents can delete a record stored in mgc by calling `mgc_delete` after the user has explicitly approved.
- **Linux compatibility fixes**: several platform-specific bugs on Linux are resolved, so sealed workflows that already worked on macOS / Windows now behave the same on Linux.
- **Cross-folder workflow auto-recognition**: same-folder script imports and cross-folder subprocess calls are now fully recognised when saving a workflow, so the whole package can be executed under sealed mode without plain text on disk.
- **`mgc_run` no longer requires `diff_1`**
- **`mgc_seal` exports a sealed capsule file**
- **Breaking change**: output_dir is now required for all seal/package operations. Existing automations that relied on the default output location must be updated.

## 1.5.3
- Improved first-time setup experience: introduced interactive CLI initialization flow and a strong random key generator for personal key / weight parameter, lowering the barrier for new users.

## 1.5.2
- Fixed several issues when MGC executes sealed workflows.

## 1.5.1
- **Cross-script auto-recognition in skill packages & workflows** — when a skill package or workflow is stored, MGC now automatically detects how scripts inside it call each other (`import`, `from-import`, relative-path subprocess). At runtime, those cross-script calls are intercepted and routed through sealed execution, so the whole package runs as a coherent workflow with no plaintext on disk. The same auto-recognition also works seamlessly with sealed cross-node delivery — the receiving node runs the package locally, without re-importing or rewriting the original workflow.

## 1.5.0
- **Folder workflow & cross-node delegation**：Support bulk-storage of skill / workflow folders, and cross-node authorization via sealed folder packages, using `mgc_package` (plain export) or `mgc_seal_package` (sealed `.mgc_file`).
- **Script intelligence & experience- When saving a script, MGC now auto-extracts its third-party dependency list**: into `ext05` and its compatible platform list into `ext06`.
- **Documentation**: Updated `mgc/docs/skill_spec.md` to reflect the latest capabilities (folder workflow, sealed packages, script intelligence, cross-node delegation).

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

## 1.4.4
- Updated project metadata (keywords, classifiers, dependency declarations).

## 1.4.5
- Fixed non-sealed script internal MGC API call timeout issue.
- Changed script execution to non-blocking (return PID immediately).

## 1.4.6
- Added WebUI delete functionality (info_type + diff_1/2/3 conditions).
- MCP delete tool not supported (prevents AI-triggered deletion).
- Updated skill spec documentation.

## 1.4.7
- NEW MCP tool: `mgc_run` — dedicated script execution. `mgc_get action=run` retained for backward compatibility.
- WebUI: Hide Delete button for `__NODE_PUB__` row to prevent accidental deletion.
- WebUI: New Settings dropdown in skill page consolidating Root Key Change, Database Audit, Protection Mode, and Node Public Key viewer.
- WebUI: New "MGC Skills" button in skill page top bar (blue, language-aware routing to skillhub.cn / clawhub.ai).
- WebUI: Logo now always links to GitHub repo, no more language-based routing.

## 1.4.8
- WebUI: Personal key validation — minimum 8 characters required.
- Fixed retry button state not resetting after validation error on root key change page.

## 1.4.9
- Added sandbox mode to adapt to sandbox Agents, such as Trae Work and Workbuddy.
- Added `mgc --status` command to check MGC status and sandbox mode.
- Fixed Windows stdio MCP Chinese encoding issue.
- Users can update the MGC version via the WebUI.

## 1.4.10
- When a script is stored, MGC automatically parses and extracts its args.
- WebUI experience optimizations.
- NEW MCP tool: `mgc_find` — fuzzy-search entries with auto-applied LIKE wildcards (`match_mode`: substring / prefix / suffix / exact). `mgc_list` retained for backward compatibility.
- Updated `mgc_seal` MCP tool schema description.