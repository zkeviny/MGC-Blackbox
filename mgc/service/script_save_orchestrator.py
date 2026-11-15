"""Save orchestrator for script entries.

Centralises the auto-fill decision for ext05 / ext06:

- If the caller did NOT explicitly include the field in their request
  (i.e. the key is not in `fields_set`), run static analysis and fill it.
- If the caller DID explicitly include the field (even as empty string),
  respect their value.

All analyzer calls are wrapped in try/except so analyser failures never
block the main save flow.
"""

from __future__ import annotations

import logging
from typing import Any

from mgc.service import script_dependency_service, script_platform_service

_logger = logging.getLogger(__name__)


def enrich_script_fields(payload: dict, fields_set: set) -> dict:
    """Mutate payload in place, auto-filling ext05 / ext06 for scripts.

    Args:
        payload: the request payload (must already be a dict).
        fields_set: the set of field names explicitly set by the caller
            (typically `request.model_fields_set`).

    Returns:
        The same payload object (mutated in place for convenience).
    """
    if payload.get("info_type") != "script":
        return payload

    content = payload.get("content", "") or ""
    ext01 = payload.get("ext01", "") or ""

    # ext05: dependencies (only if caller did not provide)
    if "ext05" not in fields_set:
        try:
            payload["ext05"] = script_dependency_service.analyze(content, ext01)
        except Exception as e:
            _logger.debug("ext05 analysis failed: %s", e)
            payload["ext05"] = ""

    # ext06: compatible platforms (only if caller did not provide)
    if "ext06" not in fields_set:
        try:
            payload["ext06"] = script_platform_service.detect(content, ext01)
        except Exception as e:
            _logger.debug("ext06 analysis failed: %s", e)
            payload["ext06"] = ""

    return payload