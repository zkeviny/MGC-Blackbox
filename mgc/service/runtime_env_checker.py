"""Runtime environment checker (mgc_run advisory warnings).

Lightweight, deadline-bounded checks performed BEFORE executing a stored
script via mgc_run (and mgc_get action=run). Produces advisory warnings
that are appended to the run response without blocking execution.

Checks:
  - Platform compatibility (current OS vs ext06)
  - Python dependency availability (importlib.util.find_spec)
  - Node.js dependency availability (require.resolve via a fixed helper)

Failure modes (all are safe degradations; no exceptions escape):
  - empty ext05/ext06 -> skip that check
  - Node command not found / helper failure / protocol mismatch / timeout
    -> skip Node dep check, do NOT mark packages as missing
  - deadline reached mid-check -> keep results gathered so far

Public API:
    check(entry: dict, current_os: str, deadline_sec: float = 3.0)
        -> list[RuntimeWarning]
"""

from __future__ import annotations

import importlib.util
import json
import logging
import platform as _platform
import subprocess
import sys
import time
from dataclasses import dataclass, field

from mgc.service.script_dependency_service import _parse_interpreter_family

_logger = logging.getLogger(__name__)


_DEFAULT_DEADLINE_SEC = 3.0

# Fixed helper source. MUST NOT be modified by any caller input.
# Protocol v1:
#   stdin  : JSON {"protocol_version": 1, "packages": ["a","b"]}
#   stdout : JSON {"protocol_version": 1, "results": {"a":"FOUND","b":"MISSING"}}
NODE_HELPER_PROTOCOL_VERSION = 1

_NODE_RESOLVE_HELPER_SOURCE = r"""
'use strict';
let raw = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => raw += chunk);
process.stdin.on('end', () => {
    let input;
    try { input = JSON.parse(raw); } catch (e) {
        process.stdout.write(JSON.stringify({protocol_version: 1, error: 'PARSE_ERROR'}));
        return;
    }
    if (!input || input.protocol_version !== 1 || !Array.isArray(input.packages)) {
        process.stdout.write(JSON.stringify({protocol_version: 1, error: 'BAD_INPUT'}));
        return;
    }
    const results = {};
    for (const pkg of input.packages) {
        if (typeof pkg !== 'string' || !pkg) { results[pkg] = 'BAD_NAME'; continue; }
        try {
            require.resolve(pkg);
            results[pkg] = 'FOUND';
        } catch (e) {
            if (e && e.code === 'MODULE_NOT_FOUND') results[pkg] = 'MISSING';
            else results[pkg] = 'ERROR';
        }
    }
    process.stdout.write(JSON.stringify({protocol_version: 1, results}));
});
"""

# User-facing warning messages (English, intentional)
_MSG_DEP_MISSING = (
    "Please review the run result. Required dependencies may not be satisfied "
    "\u2014 if the script fails, install the packages listed in ext05."
)
_MSG_PLATFORM_INCOMPAT = (
    "Please review the run result. The current platform may not be supported "
    "\u2014 this script cannot run on macOS / Linux / Windows. If it fails, "
    "contact the provider for a fully compatible version."
)


@dataclass
class RuntimeWarning:
    code: str
    message: str
    details: list[str] = field(default_factory=list)


def _detect_current_os() -> str:
    """Map Python's platform to one of {windows, macos, linux}."""
    try:
        if sys.platform.startswith("win"):
            return "windows"
        if sys.platform == "darwin":
            return "macos"
        # Linux / other Unix -> linux
        return "linux"
    except Exception:
        # Fallback to platform module
        sysname = (_platform.system() or "").lower()
        if sysname.startswith("win"):
            return "windows"
        if sysname == "darwin":
            return "macos"
        return "linux"


def _parse_json_list(raw: str, allowed: set[str] | None) -> list[str]:
    """Parse a JSON array string. Bad JSON -> []. If `allowed` given, filter."""
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    items = [str(x) for x in data if isinstance(x, str) and x]
    if allowed is not None:
        items = [x for x in items if x in allowed]
    return items


def _check_platform(entry: dict, current_os: str) -> RuntimeWarning | None:
    platforms = _parse_json_list(entry.get("ext06", ""), allowed={"windows", "macos", "linux"})
    if not platforms:
        # Empty / unparseable -> cannot determine, no warning
        return None
    if current_os in platforms:
        return None
    return RuntimeWarning(
        code="PLATFORM_INCOMPAT",
        message=_MSG_PLATFORM_INCOMPAT,
        details=[current_os],
    )


def _check_python_deps(deps: list[str], deadline: float) -> list[str]:
    """Return list of packages whose import spec cannot be found."""
    missing: list[str] = []
    for pkg in deps:
        if time.monotonic() > deadline:
            _logger.debug("dep check deadline reached; remaining packages skipped")
            break
        try:
            if importlib.util.find_spec(pkg) is None:
                missing.append(pkg)
        except Exception:
            # importlib.util.find_spec may raise for some pathological names
            missing.append(pkg)
    return missing


def _check_node_deps(deps: list[str], deadline: float) -> list[str] | None:
    """Return list of MISSING packages, or None if the check was skipped/failed.

    None signals "could not determine" — caller should NOT treat these as
    missing (this is the documented safe-degradation path).
    """
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        _logger.debug("node dep check deadline reached before call")
        return None
    try:
        proc = subprocess.Popen(
            ["node", "-e", _NODE_RESOLVE_HELPER_SOURCE],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
    except FileNotFoundError:
        _logger.debug("node command not found; skipping node dep check")
        return None
    except Exception as e:
        _logger.debug("node helper launch error: %s", e)
        return None

    try:
        try:
            stdout, _ = proc.communicate(
                input=json.dumps({
                    "protocol_version": NODE_HELPER_PROTOCOL_VERSION,
                    "packages": deps,
                }).encode("utf-8"),
                timeout=remaining,
            )
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            _logger.debug("node helper timeout; skipping dep check")
            return None
    finally:
        pass

    if proc.returncode != 0:
        _logger.debug("node helper exit %s; skipping dep check", proc.returncode)
        return None

    try:
        payload = json.loads(stdout)
    except Exception:
        _logger.debug("node helper stdout parse failed; skipping dep check")
        return None

    if not isinstance(payload, dict):
        _logger.debug("node helper stdout not an object; skipping dep check")
        return None
    if payload.get("protocol_version") != NODE_HELPER_PROTOCOL_VERSION:
        _logger.debug("node helper protocol mismatch; skipping dep check")
        return None
    results = payload.get("results")
    if not isinstance(results, dict):
        _logger.debug("node helper results missing; skipping dep check")
        return None

    missing: list[str] = []
    for pkg in deps:
        status = results.get(pkg)
        if status == "MISSING":
            missing.append(pkg)
    return missing


def check(entry: dict, current_os: str | None = None,
          deadline_sec: float = _DEFAULT_DEADLINE_SEC) -> list[RuntimeWarning]:
    """Run all checks. Returns list of RuntimeWarning (possibly empty).

    All check failures are absorbed as "skip" — no exceptions escape.
    """
    if current_os is None:
        current_os = _detect_current_os()

    warnings: list[RuntimeWarning] = []
    deadline = time.monotonic() + max(0.0, deadline_sec)

    # Platform check (synchronous, instant)
    pw = _check_platform(entry, current_os)
    if pw is not None:
        warnings.append(pw)

    # Dependency check
    deps = _parse_json_list(entry.get("ext05", ""), allowed=None)
    if not deps:
        return warnings

    family = _parse_interpreter_family(entry.get("ext01", ""))
    missing: list[str] | None = None

    if family == "python":
        missing = _check_python_deps(deps, deadline)
    elif family == "node":
        missing = _check_node_deps(deps, deadline)
    else:
        # Unknown interpreter (bash / ruby / etc.) — do not check deps
        return warnings

    # If missing is None, the check was skipped (Node failure). Do not warn.
    if missing is not None and missing:
        warnings.append(RuntimeWarning(
            code="DEP_MISSING",
            message=_MSG_DEP_MISSING,
            details=missing,
        ))
    return warnings