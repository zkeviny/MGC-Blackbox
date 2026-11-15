"""Script callgraph analysis service — 1.5.1 Sprint 2.5 phase5+.

职责:
- analyze_callgraph(): 保存期 AST 扫描，输出 ext08 JSON 字符串。
- collect_deny_map(): 运行时由 bootstrap preflight 调用（phase5+ 已基本无内容，保留向后兼容）；与 analyze_callgraph 共享
  CallgraphVisitor；deny map 不持久化。

设计:
- 仅识别同 info_owner + diff_2（同 .mgc_file 包内）的 import / from-import / open 相对路径引用。
- phase5+：from-import 入 ext08.calls（kind=from_import），让 import hook 可识别 + unseal。
  评审 3.2 整改：from-import 不再标记为 unsupported_from_imports。
- 不持久化 raw_ref / version 字段；典型 ext08 长度 50-200 字符。
- SQLCipher 默认 schema 的 ext08 列为 TEXT，无字节上限；不再跳过写入。

phase5+ 整改记录：
- visit_ImportFrom：仅入 calls（kind=from_import），不再追加 unsupported_from_imports
- 新增 name / asname 字段记录 from-import 细节（评审 §四.2 风险补充）
- collect_deny_map 仍可用但不再含 from-import 项（向后兼容保留）
"""
from __future__ import annotations
import ast
import json
import logging
import posixpath
from typing import Any, Dict, List, Optional, Set

_logger = logging.getLogger(__name__)

# 1.5.1 Sprint 1（v3 修订）：SQLCipher 主库 ext08 列为 TEXT，无字节上限。
# phase4：去掉 100 字节跳过写入的限制，calls 多 / diff_3 长也完整落库。
# 注：旧 MySQL 远程库 schema 仍是 VARCHAR(100)，但保存路径只走 SQLCipher。
EXT08_MAX_BYTES = None  # None 表示不限制（由 DB schema 兜底）


def _resolve_to_diff_3(
    current_diff_3: str, raw_ref: str, all_diff_3s: Set[str]
) -> Optional[str]:
    """v2 路径解析。

    1. 以 current_diff_3 的目录为基准（dirname）。
    2. raw_ref 是模块名（如 "parser" / "helpers.parse"）→ 试 "<name>.py" 和 "<cur_dir>/<name>.py"。
    3. raw_ref 是相对路径（"./x.json" / "../x.py" / "lib.py"）→ normpath 后查 all_diff_3s。
    4. raw_ref 含 "/"，按相对路径处理。
    5. 找不到 → None。
    6. 绝对路径 / 跨包（.. 跳出 cur_dir）→ None。
    """
    cur_dir = posixpath.dirname(current_diff_3)
    candidates: List[str] = []

    # 绝对路径不入同包
    if raw_ref.startswith("/"):
        return None

    # 路径形态（含 "/" 或以 "./" 或 "../" 开头）按相对路径处理
    if "/" in raw_ref or raw_ref.startswith("."):
        if cur_dir:
            candidates.append(posixpath.normpath(cur_dir + "/" + raw_ref))
        else:
            candidates.append(posixpath.normpath(raw_ref))
        # 异常 case: candidates 含 ".."，可能跳出 cur_dir → 后续 normpath 会处理；
        # normpath 不会自动删除 "../"，需要后续判断是否还在 cur_dir 子树下
    else:
        # 模块名形态：可能是 "parser" / "helpers.parse" → 试 .py 追加
        # 也可能是 "lib.py" 这种已带扩展名的形式
        candidates.append(raw_ref)
        if not raw_ref.endswith(".py"):
            mod_as_path = raw_ref.replace(".", "/") + ".py"
            candidates.append(mod_as_path)
            if cur_dir:
                candidates.append(posixpath.normpath(cur_dir + "/" + mod_as_path))
        else:
            if cur_dir:
                candidates.append(posixpath.normpath(cur_dir + "/" + raw_ref))

    # 过滤：候选路径必须在 cur_dir 子树下（不允许 ../ 跳出）
    # 必须在 normpath 之前判断 raw_ref，因为 normpath 会把 'pkg/../outside.py' 简化成 'outside.py'
    if ".." in raw_ref.split("/"):
        return None

    for c in candidates:
        if c in all_diff_3s:
            return c
    # Bug A fix: root-level script (cur_dir="") cannot find same-pkg
    # modules via the candidates above. Fallback: if a unique <basename>.py
    # exists anywhere in the package, resolve to it. Strict len(hits)==1
    # prevents ambiguous matches (e.g. two helper.py).
    if cur_dir == "" and not raw_ref.startswith("."):
        raw_basename = raw_ref if raw_ref.endswith(".py") else raw_ref + ".py"
        suffix_hits = [d for d in all_diff_3s if d.endswith("/" + raw_basename)]
        if len(suffix_hits) == 1:
            return suffix_hits[0]
    return None


# ext10 — MGC 运行兼容性静态分析 (advisory only, never blocks save).
#
# Even with the callgraph (ext08) and the basename-unique-match for absolute
# paths (subprocess_adapter) in place, business code that does a fatal
# precheck like `if not Path(...).exists(): sys.exit(1)` exits before any
# interceptor can route it. Static analysis on save surfaces this so the
# caller can fix or refactor the script before relying on mgc_run.
UNSAFE_PATTERNS: Dict[str, str] = {
    "fatal_path_check": (
        "Path(...).exists() pre-check followed by sys.exit / raise / assert — "
        "MGC's in-memory execution model returns False for any path derived "
        "from __file__, so the script exits before MGC's subprocess interception "
        "can run."
    ),
}


def _detect_sealed_unsafe_patterns(source_text: str) -> List[str]:
    """Identify MGC-known incompatible patterns for ext10 static analysis.

    Args:
        source_text: Python 源码字符串

    Returns:
        命中的 pattern code 列表（来自 UNSAFE_PATTERNS），空列表表示 supported
    """
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        # 语法错误：保守地返回 unsupported（避免误判为 supported）
        return ["fatal_path_check"]
    if _has_fatal_path_check(tree):
        return ["fatal_path_check"]
    return []


def _has_fatal_path_check(tree: ast.AST) -> bool:
    """检测 `if not X.exists(): sys.exit(1) / raise` 或 `assert not X.exists()` 模式。

    合并旧版的 fatal_exists_check + exists_then_assert — 二者本质相同（业务
    用 .exists() 强退），仅触发条件有 if / assert 区别。
    """
    for node in ast.walk(tree):
        is_if = isinstance(node, ast.If)
        is_assert = isinstance(node, ast.Assert)
        if not (is_if or is_assert):
            continue
        test = node.test
        # test 必须是 `not X.exists()`
        # 注：Python 3.8+ ast.Not 是 singleton 类，但 `ast.Not == ast.Not`
        # 在某些 Python 版本返回 False（_ast 模块特性），必须用 isinstance
        if not isinstance(test, ast.UnaryOp) or not isinstance(test.op, ast.Not):
            continue
        if not _is_exists_call(test.operand):
            continue
        # if 形式：body / orelse 须含 sys.exit / raise
        # assert 形式：本身在 assert 处 abort，已经够 fatal
        if is_assert:
            return True
        if _block_has_fatal(node.body) or _block_has_fatal(node.orelse):
            return True
    return False


def _is_exists_call(node: ast.AST) -> bool:
    """判断 node 是否为 `X.exists()` 形式（X 是 Name / BinOp / Call 都算）。"""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "exists"
    )


def _block_has_fatal(block: List[ast.stmt]) -> bool:
    """检测 block 是否含 sys.exit() / raise / raise SystemExit。"""
    for stmt in block:
        if isinstance(stmt, ast.Raise):
            return True
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            if isinstance(call.func, ast.Attribute) and call.func.attr == "exit":
                # sys.exit / SystemExit / os._exit 都算
                if isinstance(call.func.value, ast.Name):
                    return True
        if isinstance(stmt, ast.If):
            # 嵌套 if 也算
            if _block_has_fatal(stmt.body) or _block_has_fatal(stmt.orelse):
                return True
    return False


class CallgraphVisitor(ast.NodeVisitor):
    """v3 严格策略 (1.5.1 phase5+)：

    - 仅解析 ast.Import / ast.ImportFrom（写入 calls）
    - 仅解析显式字符串字面量（避免变量）
    - 不解析 docstring / 注释 / 字符串字面量内的引用
    - phase5+ 整改：from-import 不再追加到 unsupported_from_imports，
      改为写入 calls（kind=from_import），让 import hook 可识别 + unseal
    - 仅处理 Path.__truediv__ 形式的 BinOp（"Path(...) / 'x'" 或 "Path(__file__).parent / 'x'"）

    字段：
    - calls: List[Dict] — 入 ext08.calls 的调用关系（含 import / from_import / subprocess / path 四种 kind）
    - unsupported_from_imports: List[Dict] — phase5+ 后基本为空，保留字段向后兼容
    """

    def __init__(self, current_diff_3: str, all_diff_3s: Set[str]):
        self.current_diff_3 = current_diff_3
        self.all_diff_3s = all_diff_3s
        self.calls: List[Dict[str, Any]] = []
        # Bug C fix: collect all targets found via visit_BinOp so that
        # subsequent subprocess calls (e.g. `subprocess.run([sys.executable,
        # str(TARGET_SCRIPT)])`) can resolve TARGET_SCRIPT by name. Maps the
        # ast.Name id (e.g. "TARGET_SCRIPT") to its resolved diff_3.
        self._path_name_map: Dict[str, str] = {}
        # Bug C fix: cmd = [literal, str(NAME), ...] assignments
        # are collected so `subprocess.run(cmd)` (where cmd is an ast.Name) can
        # be resolved by walking the list and reusing path_name_map entries.
        # Maps name → list-of-diff_3-resolved (deduped, preserves order).
        self._list_name_map: Dict[str, List[str]] = {}
        # Bug C fix: def run_X(script_path, ...): the formal
        # parameter name (e.g. "script_path") is associated with the function
        # name (e.g. "run_via_subprocess_cross_folder") so that subsequent
        # `run_via_subprocess_cross_folder(TARGET_SCRIPT, args)` can be
        # resolved by binding the actual arg (TARGET_SCRIPT) to the formal
        # parameter (script_path → look up in _path_name_map).
        self._func_param_map: Dict[str, Dict[str, int]] = {}
        # phase5+：保留字段向后兼容，正常 from-import 不再写入此处
        self.unsupported_from_imports: List[Dict[str, Any]] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            resolved = _resolve_to_diff_3(
                self.current_diff_3, alias.name, self.all_diff_3s
            )
            if resolved:
                self.calls.append(
                    {
                        "target_diff_3": resolved,
                        "kind": "import",
                        "line": node.lineno,
                    }
                )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """phase5+ 整改：from-import 同时入 calls（hook 可识别），不再追加 unsupported。

        评审 3.2 整改：
        - import hook 已可覆盖 from-import 形态，让 mgc sealed 链路覆盖业界 ~90% 写法
        - 不再标记为 unsupported_from_imports（避免下游消费方误判为"不可运行"）
        - 新增 name / asname 字段记录 from-import 细节（评审 §四.2 风险补充）

        评审 §四.2 as 别名说明：
        - `from X import Y as Z` 中 ast.alias.name 是 'Y'，alias.asname 是 'Z'
        - callgraph 取 alias.name（实际 import 的名字），asname 用于审计展示
        - hook 不需要区分 asname，Python 解释器自动处理

        限制：
        - level>=2 跨包 import 仍不回退（与 visit_Import 一致）
        - 动态 import（importlib.import_module("X")）不支持（§7.2 已知限制）
        """
        # level>=2 视为跨包（PM 化简：静默回退到 Python 默认）
        if node.level and node.level >= 2:
            return
        module_name = node.module or ""
        if not module_name:
            return
        for alias in node.names:
            resolved = _resolve_to_diff_3(
                self.current_diff_3, module_name, self.all_diff_3s
            )
            if resolved:
                # phase5+：仅入 calls，让 import hook 可识别 + unseal
                self.calls.append(
                    {
                        "target_diff_3": resolved,
                        "kind": "from_import",  # ★ 新增 kind，hook 与 5+1 都按 import 同等对待
                        "line": node.lineno,
                        "name": alias.name,           # 评审 §四.2：实际 import 的名字
                        "asname": alias.asname or "", # 评审 §四.2：别名（如 from X import Y as Z）
                    }
                )
                # ★ 不再追加到 unsupported_from_imports（评审 3.2 整改）
                # 旧行为（phase4）会同时写 calls=[] 和 unsupported=[{...}]，
                # 下游读到 unsupported 非空会误判为"不可运行"。
                # phase5 后：hook 已可覆盖，unsupported_from_imports 不再含 from-import 项。

    def visit_Call(self, node: ast.Call) -> None:
        # 1.5.1 phase6 task 7：subprocess.run / Popen / check_output / check_call
        #   识别形如 subprocess.run([literal_path, ...]) 的 call site，
        #   把第一个字符串字面量解析到 ext08 calls kind=subprocess。
        #   运行时拦截由 subprocess_adapter.patched_run 完成（独立于 ext08）。
        if self._try_visit_subprocess(node):
            return
        # Cross-folder helper functions, e.g.
        # `run_via_subprocess_cross_folder(TARGET_SCRIPT, args)` where the
        # first arg is an ast.Name → look up _func_param_map to find which
        # formal param it maps to, then look up that formal param's first
        # usage in the function body. Conservative: only emit path if
        # the first arg is a known Name bound to a Path BinOp earlier.
        if isinstance(node.func, ast.Name) and node.func.id in getattr(self, "_func_param_map", {}):
            if node.args:
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Name) and first_arg.id in self._path_name_map:
                    self.calls.append({
                        "target_diff_3": self._path_name_map[first_arg.id],
                        "kind": "path",
                        "line": node.lineno,
                    })
        # open("./x.json") / open("./x.json", "r") ← 仅第一个位置参数是字面量字符串
        if isinstance(node.func, ast.Name) and node.func.id == "open":
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(
                node.args[0].value, str
            ):
                target = _resolve_to_diff_3(
                    self.current_diff_3, node.args[0].value, self.all_diff_3s
                )
                if target:
                    self.calls.append(
                        {
                            "target_diff_3": target,
                            "kind": "path",
                            "line": node.lineno,
                        }
                    )

    # 1.5.1 phase6 task 7：subprocess call site 识别（kind=subprocess）
    _SUBPROCESS_FUNCS = {
        "run",
        "Popen",
        "call",
        "check_call",
        "check_output",
        "call_args",
    }

    # Only runtime-interpreter variables in the whitelist are skipped; any
    # other ast.Name is rejected (defence against false positives).
    # 避免把 `subprocess.run([user_var, "x.py"])` 误识别为调用 x.py。
    # 与 mgc/docs/skill_spec.md 第 26 行 `sys.executable` 承诺对齐。
    _INTERPRETER_NAME_IDS = frozenset({
        "executable",          # sys.executable
        "python",
        "python3",
        "python.exe",
        "python3.exe",
        "sys.executable",      # 兼容 sys.executable 字面被解析为 ast.Name 的边缘情况
    })

    def _try_visit_subprocess(self, node: ast.Call) -> bool:
        """识别 `subprocess.<name>([literal, ...])` 形态。

        支持：
        - subprocess.run / Popen / call / check_call / check_output / call_args
        - 也支持 from subprocess import run; run(...) 形态
          （visit_Call 不区分 callee 来源，只要 callee.id 命中即可）

        phase3-r2 extension:
        - 第一个参数可以是 ast.Name 指向 list 字面量（`cmd = [...]; subprocess.run(cmd)`）
        - 第一个参数可以是 list/tuple 字面量，元素是 str(NAME) 形式

        限制：
        - List 内第一个元素为字符串字面量才解析
        - 不识别 sys.executable 之类的 Name（避免误判）
        """
        # 取 callee 名：subprocess.run / from-subprocess-import 形态
        func = node.func
        callee_name: Optional[str] = None
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            # subprocess.run / subprocess.Popen / ...
            if func.value.id == "subprocess" and func.attr in self._SUBPROCESS_FUNCS:
                callee_name = func.attr
        elif isinstance(func, ast.Name) and func.id in self._SUBPROCESS_FUNCS:
            # from subprocess import run; run(...)
            callee_name = func.id
        if callee_name is None:
            return False

        # 第一个位置参数：list/tuple 字面量 OR 指向 list 的 Name
        if not node.args:
            return False
        first = node.args[0]

        # subprocess.run(cmd) where cmd is an ast.Name pointing
        # to a list assignment → walk the list, resolve each element.
        if isinstance(first, ast.Name) and first.id in getattr(self, "_list_name_map", {}):
            for resolved_target in self._list_name_map[first.id]:
                self.calls.append({
                    "target_diff_3": resolved_target,
                    "kind": "subprocess",
                    "line": node.lineno,
                    "callee": callee_name,
                })
            return True

        # 仅 ast.List / ast.Tuple 字面量
        if not isinstance(first, (ast.List, ast.Tuple)):
            return False
        if not first.elts:
            return False
        # The first element of the list must be a string literal (avoid treating
        # sys.executable and similar variables as targets). Only runtime
        # interpreter variables in the whitelist are skipped; any other
        # ast.Name / ast.Attribute is rejected.
        # 找到 list 内第一个 ast.Constant 字符串作为 target；同时保留原 BinOp / Call 形态兼容。
        # max iterations = 4（避免深层循环误判）。
        # 注意：`sys.executable` 在 Python AST 里是 ast.Attribute(value=ast.Name('sys'), attr='executable')，
        # 不是 ast.Name——1.5.1 注释里的 "不识别 sys.executable" 是基于错误假设写的。
        target_str: Optional[str] = None
        for _elt in first.elts[:4]:
            # 跳过白名单内的运行时解释器变量（ast.Name / ast.Attribute / ast.Constant 三形态都覆盖）
            if isinstance(_elt, ast.Name) and _elt.id in self._INTERPRETER_NAME_IDS:
                continue
            if isinstance(_elt, ast.Attribute) and _elt.attr in self._INTERPRETER_NAME_IDS:
                continue   # 覆盖 sys.executable / sys.python 形态
            if isinstance(_elt, ast.Constant) and isinstance(_elt.value, str) and _elt.value in self._INTERPRETER_NAME_IDS:
                continue   # 覆盖 subprocess.run(["python", ...]) 字面 "python"
            if isinstance(_elt, ast.Constant) and isinstance(_elt.value, str):
                # 非白名单字面 → 直接是 target
                target_str = _elt.value
                break
            if isinstance(_elt, ast.BinOp) and isinstance(_elt.op, ast.Div):
                if isinstance(_elt.right, ast.Constant) and isinstance(_elt.right.value, str):
                    target_str = _elt.right.value
                    break
            if isinstance(_elt, ast.Call) and _elt.args:
                _inner = _elt.args[0]
                if isinstance(_inner, ast.BinOp) and isinstance(_inner.op, ast.Div):
                    if isinstance(_inner.right, ast.Constant) and isinstance(_inner.right.value, str):
                        target_str = _inner.right.value
                        break
                # Bug C fix: `str(TARGET_SCRIPT)` is ast.Call with
                # args[0]=ast.Name. If the inner name was bound to a
                # Path/__file__ BinOp earlier, reuse the resolved target.
                if isinstance(_inner, ast.Name) and _inner.id in getattr(self, "_path_name_map", {}):
                    target_str = self._path_name_map[_inner.id]
                    break
            # Bug C fix: ast.Name may refer to a Path/__file__ BinOp
            # assigned earlier (e.g. `TARGET_SCRIPT = PKG_ROOT / "x.py"`).
            # If visit_BinOp already recorded a path under this name, reuse it.
            if isinstance(_elt, ast.Name) and _elt.id in getattr(self, "_path_name_map", {}):
                target_str = self._path_name_map[_elt.id]
                break
            # 其它形态：不再兼容，停止扫描
            break
        if target_str is None:
            return False

        # 不解析绝对路径或跨包（与 _resolve_to_diff_3 一致）
        resolved = _resolve_to_diff_3(
            self.current_diff_3, target_str, self.all_diff_3s
        )
        if resolved:
            self.calls.append(
                {
                    "target_diff_3": resolved,
                    "kind": "subprocess",
                    "line": node.lineno,
                    "callee": callee_name,
                }
            )
            return True
        return False

    def visit_BinOp(self, node: ast.BinOp) -> None:
        # Path(__file__).parent / "x" 或 Path("x") / "y"
        if not (
            isinstance(node.op, ast.Div)
            and isinstance(node.right, ast.Constant)
            and isinstance(node.right.value, str)
        ):
            return
        target = _resolve_to_diff_3(
            self.current_diff_3, node.right.value, self.all_diff_3s
        )
        if not target:
            return
        # Bug C fix: remember the assignment target so subprocess calls
        # referencing this Name later can resolve it. ast.Assign.targets is a
        # list; the BinOp may be the value of `X = ...` or `X: T = ...` form.
        try:
            for parent in getattr(self, "_parent_map", {}).get(id(node), []):
                if isinstance(parent, ast.Assign):
                    for tgt in parent.targets:
                        if isinstance(tgt, ast.Name):
                            self._path_name_map[tgt.id] = target
        except Exception:
            pass
        # v2 简化：直接入 calls（不再细分 Path/__file__ 形式）
        self.calls.append(
            {"target_diff_3": target, "kind": "path", "line": node.lineno}
        )

    def visit_Assign(self, node: ast.Assign) -> None:
        """Bug C fix: collect list literal assignments.

        Handle `cmd = [literal, str(NAME), ...]` and `cmd = [str(NAME), ...]`
        so that `subprocess.run(cmd)` (where cmd is an ast.Name) can be
        resolved by walking the list. Each element is tried:
        - ast.Constant string (skip interpreter whitelist)
        - ast.Call where args[0] is ast.Name with a path_name_map entry
        - ast.BinOp with right-hand ast.Constant string (Path / "x")
        - ast.Name with a path_name_map entry

        IMPORTANT: must call self.generic_visit(node) so child BinOp / Name
        / FunctionDef nodes still get visited. Otherwise visit_BinOp won't
        fire and _path_name_map stays empty.
        """
        if isinstance(node.value, (ast.List, ast.Tuple)):
            targets: List[str] = []
            for elt in node.value.elts[:8]:
                resolved = self._resolve_call_element(elt)
                if resolved:
                    targets.append(resolved)
            if targets:
                # Dedup while preserving order
                seen: set = set()
                deduped: List[str] = []
                for t in targets:
                    if t not in seen:
                        seen.add(t)
                        deduped.append(t)
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        self._list_name_map[tgt.id] = deduped
        # Always recurse into children so visit_BinOp / visit_Call still fire
        self.generic_visit(node)

    def _resolve_call_element(self, elt: ast.AST) -> Optional[str]:
        """Resolve a single element of a list literal to a diff_3 if possible.

        Used by visit_Assign and visit_Call (for str(NAME) wrapping).
        """
        # str(NAME) where NAME was bound to a Path / "x" earlier
        if isinstance(elt, ast.Call) and elt.args:
            inner = elt.args[0]
            if isinstance(inner, ast.Name) and inner.id in self._path_name_map:
                return self._path_name_map[inner.id]
            if isinstance(inner, ast.BinOp) and isinstance(inner.op, ast.Div):
                if isinstance(inner.right, ast.Constant) and isinstance(inner.right.value, str):
                    return _resolve_to_diff_3(
                        self.current_diff_3, inner.right.value, self.all_diff_3s,
                    )
        # Path / "x" BinOp
        if isinstance(elt, ast.BinOp) and isinstance(elt.op, ast.Div):
            if isinstance(elt.right, ast.Constant) and isinstance(elt.right.value, str):
                return _resolve_to_diff_3(
                    self.current_diff_3, elt.right.value, self.all_diff_3s,
                )
        # Bare Name referencing a Path BinOp earlier
        if isinstance(elt, ast.Name) and elt.id in self._path_name_map:
            return self._path_name_map[elt.id]
        return None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Bug C fix: register formal parameter name → position.

        `def run_via_subprocess_cross_folder(script_path, ...):` registers
        script_path=0, args=1 so subsequent calls to
        `run_via_subprocess_cross_folder(TARGET_SCRIPT, args)` can look up
        which actual argument maps to which formal parameter.
        """
        params: Dict[str, int] = {}
        for idx, arg in enumerate(node.args.args):
            params[arg.arg] = idx
        if params:
            self._func_param_map[node.name] = params
        # Recurse so subprocess.run(cmd) inside the function body still fires
        # visit_Call / _try_visit_subprocess.
        self.generic_visit(node)


def analyze_callgraph(script_records: List[Dict[str, Any]]) -> Dict[str, str]:
    """保存期主入口：对每个 script record 做 AST 扫描，输出 ext08 JSON 字符串。

    Args:
        script_records: parse_folder 返回的 records 列表
            每条至少含 {"diff_3": str, "content": str, "info_type": "script"|...}
            调用方保证 records 全部属于同一个 info_owner + diff_2（同包）。

    Returns:
        {diff_3: ext08_json_str} 字典。
        - 仅 info_type == "script" 才进入输出
        - 解析失败的脚本写入 "{}"，不抛异常
        - 单条 ext08 > EXT08_MAX_BYTES 字节时跳过写入 + 警告日志（不破坏 DB 列）

    行为：
    - 历史数据不重算（PM 化简）：仅在本次 mgc_save_file 触发时跑；已有 record 不动。
    - sealed 包路径不动（Sprint 2/3 扩展 sealed_package_importer）。
    """
    # 1. 收集同包内全部 diff_3（不只是脚本；数据文件也在 all_diff_3s 用于 path 类解析）
    all_diff_3s: Set[str] = set()
    for rec in script_records:
        d = rec.get("diff_3", "")
        if d:
            all_diff_3s.add(d)

    # 2. 对每个脚本 record 跑 AST visitor
    # 设计：每个 script record 都写入 ext08（无 calls 时写 "{}"），便于下游统一处理
    result: Dict[str, str] = {}
    for rec in script_records:
        if rec.get("info_type") != "script":
            continue
        diff_3 = rec.get("diff_3", "")
        content = rec.get("content", "")
        if not diff_3:
            continue

        # content 为空：直接写 "{}"
        if not content:
            result[diff_3] = "{}"
            continue

        # AST 解析（语法错误不阻断保存；写入 "{}"）
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            _logger.warning(
                "callgraph: AST parse failed for %s: %s; writing empty ext08",
                diff_3, e,
            )
            result[diff_3] = "{}"
            continue

        visitor = CallgraphVisitor(diff_3, all_diff_3s)
        # Bug C fix: build a {child_id: [parent_node]} map so
        # visit_BinOp can find the enclosing ast.Assign and remember the
        # variable name (e.g. TARGET_SCRIPT) → diff_3 mapping.
        try:
            parent_map: Dict[int, List[ast.AST]] = {}
            for _parent in ast.walk(tree):
                for _child in ast.iter_child_nodes(_parent):
                    parent_map.setdefault(id(_child), []).append(_parent)
            visitor._parent_map = parent_map
        except Exception:
            visitor._parent_map = {}
        visitor.visit(tree)

        ext08_obj: Dict[str, Any] = {}
        if visitor.calls:
            ext08_obj["calls"] = visitor.calls

        ext08_str = json.dumps(ext08_obj, ensure_ascii=False, separators=(",", ":"))

        # 长度超限：phase4 v3 修订——SQLCipher ext08 TEXT 不再设上限。
        # 仅当 EXT08_MAX_BYTES 不为 None（兼容旧 MySQL VARCHAR(100) 部署）才跳过。
        if EXT08_MAX_BYTES is not None and len(ext08_str.encode("utf-8")) > EXT08_MAX_BYTES:
            _logger.warning(
                "ext08 for %s is %d bytes (> %d); skipped to keep DB column intact.",
                diff_3, len(ext08_str.encode("utf-8")), EXT08_MAX_BYTES,
            )
            ext08_str = ""

        result[diff_3] = ext08_str

    return result


def collect_deny_map(
    script_records: List[Dict[str, Any]], current_diff_3: str
) -> List[Dict[str, Any]]:
    """运行时由 bootstrap preflight 调用：派生当前脚本的 from-import deny 项。

    与 analyze_callgraph 共享 CallgraphVisitor；deny map 不持久化，运行期临时派生。

    phase5+ 评审 3.2 整改：
    - from-import 已入 calls（kind=from_import），import hook 可识别 + unseal
    - 因此本函数返回的 deny 项**仅包含真正"不支持"的写法**（如未来扩展的 AST 黑名单）
    - 当前 phase5 落地后，正常 from-import 不会再出现在此列表
    - 函数保留向后兼容（未来若需新增"拒绝某些 import"逻辑时可扩展）

    判定边界：
    - from X import Y 的 X 能解析为同包内 .py → 不入 deny（phase5 改：入 calls）
    - from .X（隐式相对）= from X → 不入 deny（phase5 改：入 calls）
    - from ..X（level≥2）→ 不入（静默回退，与 visit_ImportFrom 一致）
    - from third_party import X → 不入（不误伤第三方）

    Args:
        script_records: 从 mgc 拉取的同包全部 record 列表（每个 record 至少含 diff_3 + content）
        current_diff_3: 当前执行脚本的 diff_3

    Returns:
        deny 项列表。phase5+ 后通常为空列表（from-import 已入 calls）。
    """
    all_diff_3s: Set[str] = set()
    for rec in script_records:
        d = rec.get("diff_3", "")
        if d:
            all_diff_3s.add(d)

    target_rec = next(
        (r for r in script_records if r.get("diff_3") == current_diff_3), None
    )
    if not target_rec:
        return []
    content = target_rec.get("content", "")
    if not content:
        return []

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    visitor = CallgraphVisitor(current_diff_3, all_diff_3s)
    visitor.visit(tree)
    return visitor.unsupported_from_imports
