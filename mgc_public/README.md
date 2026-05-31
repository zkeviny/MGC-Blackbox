MGC Blackbox — Public Interface Layer
This directory contains the public interface layer of MGC Blackbox, including:

API Layer (mgc/api)

MCP Server Layer (mgc/mcp)

WebUI Integration Layer (mgc/webui)

These modules define the public-facing behavior of MGC Blackbox and are safe to publish.

Not the full source code
This directory does not contain the full implementation of MGC Blackbox.

The secure execution core, including:

encrypted execution engine

sealed script loader

anti‑tampering logic

key management

compiled crypto layer

is distributed only in compiled form inside the official installation package (mgc_dist)
and is not included in this repository for security and anti‑tampering reasons.

Why only the public layer is included
MGC Blackbox is a local encrypted execution layer.
To ensure:

security

integrity

tamper‑resistance

commercial licensing boundaries

the core cryptographic components are intentionally closed-source.

The files in this directory are provided to:

help developers understand the public API

enable MCP integration

support WebUI extension

allow ecosystem tooling

without exposing internal secure logic.

Where is the full functionality?
The complete runtime, including the compiled secure core,
is available in the official installation package:

mgc_dist/
This package contains the full, functional version of MGC Blackbox.

License
This public interface layer is provided under the MGC Custom License.
The secure core remains proprietary.

See the root LICENSE file for details
