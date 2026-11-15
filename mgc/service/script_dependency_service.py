"""Script dependency analyzer (ext05).

Extracts third-party module identifiers (import name / require specifier)
from Python AST or Node.js regex matching.

Note: extracted names are identifiers, NOT PyPI / npm distribution names.
For example, `import yaml` yields "yaml" (not "PyYAML"). Do not use the
result to drive automatic dependency installation.

Public API:
    analyze(content: str, ext01: str) -> str
        Returns a JSON array string of package names (sorted, deduped),
        or "" on failure / unsupported language / empty input.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from typing import Iterable

_MAX_SCRIPT_SIZE_BYTES = 1024 * 1024  # 1 MiB


_PYTHON_STDLIB_FALLBACK = frozenset({
    "os", "sys", "re", "json", "datetime", "time", "math", "random",
    "collections", "itertools", "functools", "pathlib", "glob", "shutil",
    "subprocess", "threading", "multiprocessing", "socket", "http",
    "urllib", "argparse", "logging", "unittest", "typing", "dataclasses",
    "asyncio", "hashlib", "hmac", "secrets", "base64", "struct", "io",
    "csv", "sqlite3", "ssl", "email", "html", "xml", "string", "textwrap",
    "traceback", "warnings", "weakref", "operator", "copy", "pprint",
    "enum", "abc", "contextlib", "concurrent", "queue", "heapq",
    "bisect", "array", "types", "inspect", "dis", "ast", "tokenize",
    "importlib", "builtins", "errno", "signal", "fcntl", "select",
    "socket", "pty", "tty", "pwd", "grp", "resource", "syslog",
    "cgi", "wsgiref", "xmlrpc", "ipaddress", "uuid", "decimal",
    "fractions", "numbers", "cmath", "statistics", "zoneinfo",
    "calendar", "locale", "unicodedata", "stringprep", "rlcompleter",
    "profile", "pstats", "timeit", "trace", "faulthandler", "tracemalloc",
    "ensurepip", "zipimport", "pkgutil", "modulefinder", "py_compile",
    "compileall", "pyclbr", "tabnanny", "code", "codeop", "macpath",
    "ntpath", "posixpath", "genericpath", "stat", "fileinput",
})


_NODEJS_BUILTINS_FALLBACK = frozenset({
    "fs", "path", "http", "https", "url", "querystring", "os", "util",
    "events", "stream", "buffer", "crypto", "zlib", "child_process",
    "cluster", "net", "tls", "dgram", "dns", "readline", "tty",
    "vm", "assert", "module", "worker_threads", "perf_hooks", "async_hooks",
    "console", "process", "timers", "punycode", "string_decoder",
    "diagnostics_channel", "trace_events", "wasi",
})


_NODEJS_BUILTIN_PREFIXES = ("node:",)


# Regex patterns for Node.js
_RE_NODE_REQUIRE = re.compile(r"require\(\s*(['\"`])([^'\"`]+)\1\s*\)")
_RE_NODE_IMPORT_FROM = re.compile(
    r"import\s+(?:[^'\"]+?\s+from\s+)?(['\"`])([^'\"`]+)\1"
)
_RE_NODE_IMPORT_DYNAMIC = re.compile(r"import\(\s*(['\"`])([^'\"`]+)\1\s*\)")


def _python_stdlib() -> frozenset[str]:
    """Best-effort Python stdlib set: prefer sys.stdlib_module_names (3.10+)."""
    try:
        names = getattr(sys, "stdlib_module_names", None)
        if names:
            return frozenset(names)
    except Exception:
        pass
    return _PYTHON_STDLIB_FALLBACK


def _safe_split_command(ext01: str) -> str:
    """Return the basename of the first whitespace-separated token."""
    if not ext01:
        return ""
    # Plain whitespace split — do NOT use shlex (avoids shell-style quirks).
    parts = ext01.strip().split()
    if not parts:
        return ""
    first = parts[0]
    # Strip any directory components
    if "/" in first or "\\" in first:
        first = first.replace("\\", "/").rsplit("/", 1)[-1]
    # Strip executable suffix on Windows
    if first.lower().endswith(".exe"):
        first = first[:-4]
    return first.lower()


def _parse_interpreter_family(ext01: str) -> str | None:
    """Return 'python' | 'node' | None based on the first token of ext01."""
    base = _safe_split_command(ext01)
    if not base:
        return None
    if base == "py" or base.startswith("python"):
        return "python"
    if base.startswith("node"):
        return "node"
    return None


def _normalize_python_name(name: str) -> str | None:
    """Return top-level package name from a Python import target."""
    if not name:
        return None
    name = name.strip()
    if not name:
        return None
    # Top-level only
    return name.split(".", 1)[0]


def _analyze_python(content: str) -> str:
    """Parse Python source via AST and extract third-party imports.

    PR-8 (depends 增强):
    - 额外识别 `__import__('pandas')` / `__import__("pymysql")` 这类字符串式
      import 调用（常见于延迟加载 / 依赖自检 / try-except import）。它们
      在 AST 里是 ``ast.Call(func=ast.Name('__import__'), args=[Constant('x')])``，
      原本只扫 ``ast.Import`` / ``ast.ImportFrom`` 的识别器会漏掉。
    - 同时兼容 `builtins.__import__('x')`（``ast.Call(func=ast.Attribute(
      value=ast.Name('builtins'), attr='__import__'))``），按字符串字面量
      第一参数解析。
    """
    stdlib = _python_stdlib()
    found: set[str] = set()
    try:
        tree = ast.parse(content)
    except Exception:
        return ""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = _normalize_python_name(alias.name)
                if top and top not in stdlib:
                    found.add(top)
        elif isinstance(node, ast.ImportFrom):
            # Skip relative imports (level > 0)
            if (node.level or 0) > 0:
                continue
            top = _normalize_python_name(node.module or "")
            if top and top not in stdlib:
                found.add(top)
        elif isinstance(node, ast.Call):
            # `__import__('pandas')` → add 'pandas'
            # `builtins.__import__('pandas')` → add 'pandas'
            func = node.func
            is_dunder_import = (
                (isinstance(func, ast.Name) and func.id == "__import__")
                or (
                    isinstance(func, ast.Attribute)
                    and func.attr == "__import__"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "builtins"
                )
            )
            if not is_dunder_import:
                continue
            if not node.args:
                continue
            first = node.args[0]
            if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
                continue
            top = _normalize_python_name(first.value)
            if top and top not in stdlib:
                found.add(top)
    return json.dumps(sorted(found), ensure_ascii=False)


def _normalize_node_specifier(spec: str) -> str | None:
    """Normalize a Node.js require/import specifier.

    - "@scope/pkg/sub"   -> "@scope/pkg"
    - "lodash/fp"        -> "lodash"
    - "node:fs"          -> None (builtin prefix; will be filtered by caller)
    - "fs"               -> None (builtin)
    - "./*.js" / "/abs"  -> None (relative / absolute path)
    - ""                 -> None
    """
    if not spec:
        return None
    spec = spec.strip()
    if not spec:
        return None
    # Reject obvious relative/absolute paths
    if spec.startswith(".") or spec.startswith("/") or spec.startswith("\\"):
        return None
    # Skip builtin prefix
    for prefix in _NODEJS_BUILTIN_PREFIXES:
        if spec.startswith(prefix):
            return None
    # Skip plain builtins
    head = spec.split("/", 1)[0]
    if head in _NODEJS_BUILTINS_FALLBACK:
        return None
    # Scoped package: @scope/pkg[/sub...]
    if spec.startswith("@"):
        parts = spec.split("/")
        if len(parts) < 2:
            return None
        return f"{parts[0]}/{parts[1]}"
    # Unscoped: lodash[/sub...]
    return head


def _analyze_nodejs(content: str) -> str:
    """Extract third-party Node.js require/import specifiers."""
    found: set[str] = set()
    for pattern in (_RE_NODE_REQUIRE, _RE_NODE_IMPORT_FROM, _RE_NODE_IMPORT_DYNAMIC):
        for _quote, spec in pattern.findall(content):
            normalized = _normalize_node_specifier(spec)
            if normalized:
                found.add(normalized)
    return json.dumps(sorted(found), ensure_ascii=False)


def analyze(content: str, ext01: str) -> str:
    """Return JSON array string of third-party import names, or "" on failure."""
    if not content:
        return ""
    try:
        if len(content.encode("utf-8")) > _MAX_SCRIPT_SIZE_BYTES:
            return ""
    except Exception:
        return ""
    family = _parse_interpreter_family(ext01)
    if family == "python":
        return _analyze_python(content)
    if family == "node":
        return _analyze_nodejs(content)
    return ""