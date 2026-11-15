"""Script platform detector (ext06).

Statically infers the set of platforms on which a script can run, using
an "uncertainty-graded" strategy:

  1. No platform-limiting signals detected
       -> '["windows","macos","linux"]'   (static inference: "no limit found")
  2. Single, unconditional platform limit (e.g. hardcoded Windows path)
       -> e.g. '["windows"]'
  3. Complete if/elif/else platform condition tree
       -> union of branch target platforms (still static inference only)
  4. try/except / dynamic conditions / env-var based branches
       -> do NOT participate in narrowing or widening the conclusion
  5. Conflicting unconditional limits OR analyzer failure
       -> "" (cannot determine)

Public API:
    detect(content: str, ext01: str) -> str
        Returns a JSON array string of compatible platforms, or "" on failure.

NOTE: This module produces STATIC INFERENCE ONLY. It does NOT verify that
the script can actually run on each declared platform.
"""

from __future__ import annotations

import ast
import json
import re

from mgc.service.script_dependency_service import (
    _parse_interpreter_family,
    _safe_split_command,
)

_MAX_SCRIPT_SIZE_BYTES = 1024 * 1024  # 1 MiB

_PLATFORM_ORDER = ("windows", "macos", "linux")
_ALL_PLATFORMS = list(_PLATFORM_ORDER)
_NON_WINDOWS = ("macos", "linux")  # PR-8: 用在 else 分支补全

_PLATFORM_STRATEGY_VERSION = 2  # conservative-grading strategy


# Windows hardcoded patterns
_RE_WIN_DRIVE = re.compile(r"[A-Za-z]:\\")
_RE_WIN_UNC = re.compile(r"\\\\[A-Za-z]+")
_RE_WIN_KEYWORD = re.compile(r"\bwin32\b|os\.name\s*==\s*['\"]nt['\"]")
# macOS hardcoded patterns
_RE_MAC_USER = re.compile(r"/Users/|/private/")
_RE_MAC_DARWIN = re.compile(r"os\.name\s*==\s*['\"]posix['\"].*darwin|platform\.system\(\)\s*==\s*['\"]Darwin['\"]")
# Linux hardcoded patterns (used conservatively — only in main code area)
# /usr/local/, /usr/bin/, /opt/ are common Linux install paths. They also
# appear on macOS (/usr/local is Homebrew's default), but combined with
# windows patterns they correctly drive the conflict -> "" branch.
_RE_LINUX_PATH = re.compile(r"/etc/|/var/|/usr/local/|/usr/bin/|/opt/")


def _ordered_union(platforms: set[str]) -> list[str]:
    """Return platforms in fixed order, deduped."""
    return [p for p in _PLATFORM_ORDER if p in platforms]


def _ast_detect_python_platforms(content: str) -> set[str] | None:
    """Detect platform branches in a Python AST.

    Returns:
        - set of platforms if a complete if/elif/else branch tree is found
          (union of branch target platforms)
        - None if no platform branch tree is found (caller falls back to
          pattern detection)

    Scans both top-level statements AND the body of top-level
    FunctionDef / AsyncFunctionDef nodes, so that platform branching hidden
    inside helper functions (e.g. ``get_binary_path()``) is still picked up.

    Only direct, unconditional comparisons of well-known platform identifiers
    are recognised. Per strategy rule 4 we do NOT descend into:
      - try / except blocks (dynamic fallback)
      - with blocks (context-manager dynamic)
      - nested function / lambda bodies (scope-local)
      - class bodies (instance-local)
      - any non-static expression

    For an ``else:`` branch that itself is not a platform condition, we
    sniff the branch body for a static string literal that contains a
    Linux-only path hint (``/usr/local/``, ``/usr/bin/``, ``/opt/``).
    This is heuristic but bounded: only used to ADD linux to the union,
    never to remove platforms already inferred from explicit branches.
    """
    try:
        tree = ast.parse(content)
    except Exception:
        return None

    _RE_LINUX_PATH_HINT = re.compile(r"/usr/local/|/usr/bin/|/opt/")

    collected: list = []

    def sniff_linux_from_body(body) -> bool:
        """Return True if any return/assign RHS contains a Linux-path literal.

        PR-8 扩展：原实现只检查 RHS 是否为 ``ast.Constant`` 字符串字面量。
        实际脚本常见写法 ``else: log_dir = home / ".mgc" / "logs"`` 的 RHS
        是 ``ast.BinOp``（路径拼接），不是直接字面量。改为递归遍历整个
        表达式树，凡嵌套在 BinOp / Subscript / Attribute / Call 等节点内
        的 ``ast.Constant`` 字符串字面量都会被扫描到。
        """
        def _walk(node) -> bool:
            if node is None:
                return False
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                return bool(_RE_LINUX_PATH_HINT.search(node.value))
            # 递归子节点：BinOp.left/right、Attribute.value、Subscript.value、
            # Call.args、JoinedStr.values 等所有可能含字面量的位置。
            for child in ast.iter_child_nodes(node):
                if _walk(child):
                    return True
            return False

        for n in body:
            if isinstance(n, ast.Return) and _walk(n.value):
                return True
            if isinstance(n, ast.Assign):
                # ast.Assign.value is a single expression node (or list for
                # tuple-unpacking targets). Normalise to iterable.
                rhs = n.value
                rhs_list = rhs if isinstance(rhs, (list, tuple)) else [rhs]
                for v in rhs_list:
                    if _walk(v):
                        return True
        return False

    def walk_if_chain(start: ast.If, sink: list) -> None:
        current = start
        # PR-8: 显式声明的 OS 集合（用全部 if/elif 累积的并集）。
        # else 视为"全集 − 显式声明集"——覆盖 windows-only / linux-only /
        # win32+darwin / win32+linux 等各种 if/elif 组合。
        explicit_in_chain: set[str] = set()
        terminal_else_body = None
        while isinstance(current, ast.If):
            targets = _platform_targets_from_test(current.test)
            if targets is None:
                # Chain stops being platform branches. The current If is
                # itself a terminal else (test=None); use its body.
                terminal_else_body = current.body
                break
            explicit_in_chain |= targets
            sink.append(targets)
            if current.orelse and len(current.orelse) == 1:
                next_node = current.orelse[0]
                # If orelse[0] is itself an If (elif), keep walking.
                # Otherwise it's the terminal else body (a list of stmts).
                if isinstance(next_node, ast.If):
                    current = next_node
                else:
                    # orelse is a single non-If statement (e.g. Return).
                    terminal_else_body = current.orelse
                    break
            else:
                break
        # PR-8: else 分支补全策略
        #   1) 原行为：仅当链路中无显式 linux 且 else 体含 Linux 路径字面量
        #      时加入 {"linux"}，覆盖 `else: return "/usr/local/bin/x"` 之类。
        #   2) 新增补全：if/elif 链未覆盖全部平台（explicit_in_chain != ALL）
        #      时，else 视为"全集 − 显式声明集"。覆盖 `if win32 / else`、
        #      `if linux / else`、`if win32+darwin / else` 等常见组合。
        if terminal_else_body is not None:
            added_linux_by_hint = False
            if "linux" not in explicit_in_chain:
                if sniff_linux_from_body(terminal_else_body):
                    sink.append({"linux"})
                    added_linux_by_hint = True
            if not added_linux_by_hint and explicit_in_chain != set(_PLATFORM_ORDER):
                complement = set(_PLATFORM_ORDER) - explicit_in_chain
                if complement:
                    sink.append(complement)

    def harvest(body) -> None:
        for node in body:
            if isinstance(node, ast.If):
                walk_if_chain(node, collected)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Recurse one level into top-level function bodies only.
                # Do NOT recurse into nested functions / classes — those
                # are out of scope per strategy rule 4.
                harvest(node.body)

    harvest(tree.body)

    if not collected:
        return None
    union: set[str] = set()
    for t in collected:
        union |= t
    return union


def _platform_targets_from_test(test: ast.AST) -> set[str] | None:
    """Return a set of platforms referenced in a static comparison, or None.

    Recognises patterns like:
        sys.platform == 'win32'      -> {'windows'}
        sys.platform.startswith('darwin') -> {'macos'}
        sys.platform.startswith('linux')  -> {'linux'}
        os.name == 'nt'              -> {'windows'}
        platform.system() == 'Linux' -> {'linux'}
    """
    plats: set[str] = set()

    def add_if_platform(value: str) -> None:
        v = value.lower()
        if v in ("win32", "windows", "nt", "cygwin", "msys"):
            plats.add("windows")
        elif v in ("darwin", "macos", "osx"):
            plats.add("macos")
        elif v in ("linux", "linux2"):
            plats.add("linux")

    # Compare node: Eq / NotEq (and NotIn / In / NotEq are filtered above).
    if isinstance(test, ast.Compare):
        left = test.left
        comparators = test.comparators
        if len(comparators) != 1 or len(test.ops) != 1:
            return None
        op = test.ops[0]
        if not isinstance(op, (ast.Eq, ast.NotEq)):
            return None
        right = comparators[0]
        if isinstance(right, ast.Constant) and isinstance(right.value, str):
            add_if_platform(right.value)
        elif isinstance(left, ast.Constant) and isinstance(left.value, str):
            add_if_platform(left.value)
        # else: not a static string comparison
    # Call node: x.startswith('darwin') -> {'macos'} / startswith('linux') -> {'linux'}
    elif isinstance(test, ast.Call):
        func = test.func
        # Must be an attribute access on a Name (e.g. sys.platform.startswith)
        if isinstance(func, ast.Attribute) and func.attr == "startswith":
            if test.args and isinstance(test.args[0], ast.Constant) and isinstance(test.args[0].value, str):
                add_if_platform(test.args[0].value)

    if plats:
        return plats
    return None


def _strip_shebang(content: str) -> str:
    """Strip the optional shebang line so it doesn't pollute pattern detection.

    A shebang like '#!/usr/bin/env python' lives at the very start of many
    scripts and would falsely match the Linux pattern ('/usr/bin/').
    """
    if content.startswith("#!"):
        # Drop everything up to and including the first newline.
        nl = content.find("\n")
        if nl >= 0:
            return content[nl + 1:]
        return ""  # shebang only, no body
    return content


def _pattern_detect_platforms(content: str) -> set[str]:
    """Return the union of platforms matched by hardcoded patterns."""
    body = _strip_shebang(content)
    found: set[str] = set()
    if _RE_WIN_DRIVE.search(body) or _RE_WIN_UNC.search(body) or _RE_WIN_KEYWORD.search(body):
        found.add("windows")
    if _RE_MAC_USER.search(body) or _RE_MAC_DARWIN.search(body):
        found.add("macos")
    if _RE_LINUX_PATH.search(body):
        found.add("linux")
    return found


def _conflicting_unconditional(platforms: set[str]) -> bool:
    """Heuristic: pattern-detected platforms from different OS families that
    could not coexist in a single unconditional script.

    Real conflict example: script contains both `C:\\Windows` (Windows) and
    `/etc/passwd` (Linux) with no branching — likely a copy-paste error or
    multi-OS sample, not a single-platform script.
    """
    return bool({"windows"} & platforms) and bool({"linux", "macos"} & platforms)


def detect(content: str, ext01: str) -> str:
    """Return JSON array string of statically inferred platforms, or '' on failure."""
    if not content:
        return ""
    try:
        if len(content.encode("utf-8")) > _MAX_SCRIPT_SIZE_BYTES:
            return ""
    except Exception:
        return ""

    family = _parse_interpreter_family(ext01)

    # Strategy step 3: AST platform condition tree (Python only for v1.5.0)
    ast_platforms: set[str] | None = None
    if family == "python":
        ast_platforms = _ast_detect_python_platforms(content)

    if ast_platforms is not None:
        # Complete branch tree found; result = union of branch targets.
        return json.dumps(_ordered_union(ast_platforms), ensure_ascii=False)

    # Strategy step 2: pattern-based detection
    pattern_platforms = _pattern_detect_platforms(content)

    if not pattern_platforms:
        # Strategy step 1: no limits detected -> all platforms
        return json.dumps(_ALL_PLATFORMS, ensure_ascii=False)

    # Conflict check: conflicting unconditional limits -> "" (cannot determine)
    if _conflicting_unconditional(pattern_platforms):
        return ""

    return json.dumps(_ordered_union(pattern_platforms), ensure_ascii=False)