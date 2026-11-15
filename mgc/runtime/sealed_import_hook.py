"""MGC Sealed Import Hook — 1.5.1 Sprint 2.5 phase5+.

目标场景：解决 sealed 脚本 `import X` / `from X import Y` 形态的跨脚本调用，
让 mgc sealed 链路覆盖业界 ~90% 本地工作流写法。

核心设计（详见 [1.5.1 import-hook方案.md](../document/1.5需求文档/1.5.1需求计划/1.5.1%20import-hook方案.md)）：

```
业务脚本                sys.meta_path 链          主进程
─────────              ───────────────          ──────
import config  ───►    MgcSealedFinder  ───►    HTTP /sensitive/unseal_for_child
                            │          ◄────── 明文
                            ▼
                        exec(plaintext,
                             sys.modules['config'].__dict__)
                            │
                            ▼
                        sys.modules['config'] = module_obj
                            │
                            ▼
业务脚本 ◄────────────── Python import 系统
```

关键点：
- `sys.meta_path.insert(0, MgcSealedFinder())`：注册到 finder 链最前
- hook `exec` 时设 `mod.__dict__["__file__"] = "script/config.py"`（统一 POSIX 风格）
- 循环 import 处理：`sys.modules[modname] = None` 占位（PEP 328 标准做法）
- 模块白名单：仅 caller.ext08.calls 里登记的模块名才拦截
- 5+1 校验：完全复用 phase4 unseal_for_child RPC + internal_token 鉴权

与 phase4 现有 patched_run 链路的关系：
- patched_run 拦截 subprocess.run（脚本级 subprocess 调用）
- 本 hook 拦截 Python import（模块级 import 调用）
- 两者并存：subprocess 写法 + import 写法都支持
- 两者复用 unseal_for_child RPC + 5+1 校验，架构一致

限制（详见方案 §7.2）：
- 虚拟 `__file__` 不支持实际 open 数据文件（sealed 场景下文件不在磁盘）
- 同包同名脚本冲突（与 callgraph 同包约束一致）
- 动态 import（importlib.import_module）不支持
- 跨包 level≥2 import 不支持
"""
from __future__ import annotations

import importlib.util
import json
import logging
import os
import sys
from types import ModuleType
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================
# 常量
# ============================================================

# 同包 module import / from-import 的 kind 标识
_KIND_IMPORT = "import"
_KIND_FROM_IMPORT = "from_import"

# 跨平台虚拟路径：统一 POSIX 风格，pathlib 三平台兼容
# 业务侧 Path(__file__).parent / "data.json" 可解析为 "script/data.json"
_VIRTUAL_FILE_SUFFIX = ".py"


# ============================================================
# MgcSealedFinder — 注册到 sys.meta_path
# ============================================================

class MgcSealedFinder:
    """注册到 sys.meta_path，在业务 import 时拦截 sealed 同包模块。

    Attributes:
        context: ScriptExecutionContext（含 ext08.calls / info_owner 等）
        mgc_api_port: 主进程 HTTP 端口（finder 调 /sensitive/unseal_for_child 用）
        mgc_api_token: mgc 主进程 HTTP token（X-MGC-Token）
        internal_token: phase4 内部 RPC token（X-MGC-Internal-Token，与 mgc_api_token 隔离）
        session_cache: 同包模块缓存（避免重复 unseal，仅子进程生命周期有效）

    安全模型：
    - internal_token 仅在主进程内存生成，外部拿不到
    - hook 白名单 = caller.ext08.calls，超出范围 return None（让 PathFinder 接手）
    - 5+1 校验由主进程 unseal_for_child handler 强制执行（info_owner + diff_1 + diff_2 + ext08.calls）
    """

    def __init__(
        self,
        context: Any,
        mgc_api_port: Optional[int],
        mgc_api_token: Optional[str],
        internal_token: Optional[str] = "",
    ):
        """初始化 finder，构建白名单索引（_managed_index）。

        Args:
            context: ScriptExecutionContext（含 ext08.calls / info_owner 等）
            mgc_api_port: 主进程 HTTP 端口（finder 调 /sensitive/unseal_for_child）
            mgc_api_token: 主进程 HTTP token（X-MGC-Token）
            internal_token: phase4 内部 RPC token（X-MGC-Internal-Token），默认空字符串
        """
        self.context = context
        self.mgc_api_port = mgc_api_port
        self.mgc_api_token = mgc_api_token or ""
        self.internal_token = internal_token or ""
        # 同包模块缓存（fullname -> module），仅子进程生命周期有效
        self.session_cache: Dict[str, ModuleType] = {}
        # ext08.calls 索引（fullname_lower -> target_diff_3），加速白名单判定
        self._managed_index: Dict[str, str] = self._build_managed_index(context)
        # === 1.5.2 hotfix (P0 caller context 栈) ===
        # 链式 import 时，exec_module 会把 child context 压栈，B 内部 import
        # config_a 触发的 unseal_for_child 必须用 B 的 ext08.calls 作为 caller，
        # 而不是顶层 D 的（否则主进程 5+1 校验拒绝 → NOT_IN_CALLS）。
        # 栈顶 = 当前正在 exec 的模块的 context；栈空时回退到 self.context（顶层 caller）。
        self._context_stack: List[Any] = []

    # ---------- 公开接口：PEP 451 finder ----------

    def find_spec(self, fullname, path, target=None):
        """PEP 451 finder 接口。

        流程：
        1. 白名单校验：仅 caller.ext08.calls 里登记的模块名才拦截
        2. 命中：占位 sys.modules（防 A→B→A 循环）→ 返回 ModuleSpec + 自定义 Loader
        3. 未命中：return None（让 PathFinder 接手）

        Args:
            fullname: 要 import 的模块完整名（如 "config"）
            path: Python 内部传的搜索路径（meta_path 协议要求，可忽略）
            target: Python 3.9+ 优化字段，importlib 传入可忽略

        Returns:
            importlib.util.ModuleSpec 或 None。None 表示"我不负责"，让下一个 finder 接手。
        """
        # 1. 白名单校验
        target_diff_3 = self._resolve_diff_3(fullname)
        if target_diff_3 is None:
            return None  # 让其他 finder（PathFinder）接手

        # 2. 占位：先在 sys.modules 占位，防 A→B→A 循环 import
        # PEP 328 标准做法
        if fullname not in sys.modules:
            placeholder = ModuleType(fullname)
            placeholder.__file__ = "<mgc-circular-import-placeholder>"
            placeholder.__path__ = []  # 当包用时需要
            sys.modules[fullname] = placeholder

        # 3. 返回 ModuleSpec + 自定义 Loader
        return importlib.util.spec_from_loader(
            fullname,
            MgcSealedLoader(
                fullname=fullname,
                finder=self,
                target_diff_3=target_diff_3,
            ),
            is_package=False,  # 平铺脚本目录，不当 package
        )

    # ---------- 内部：白名单索引 ----------

    def _build_managed_index(self, context: Any) -> Dict[str, str]:
        """构造 fullname_lower -> target_diff_3 索引（仅 import/from_import kind）。

        跨平台：Windows 平台统一 lower() 比对，避免大小写问题。
        其他平台：直接用 fullname（保留大小写敏感）。

        Args:
            context: ScriptExecutionContext（取 ext08.calls）

        Returns:
            fullname（已按平台归一化大小写）→ target_diff_3 的索引 dict
        """
        index: Dict[str, str] = {}
        if context is None:
            return index
        ext08 = getattr(context, "ext08", None) or {}
        if not isinstance(ext08, dict):
            return index
        calls = ext08.get("calls", [])
        if not isinstance(calls, list):
            return index

        for c in calls:
            if not isinstance(c, dict):
                continue
            target_diff_3 = c.get("target_diff_3", "")
            kind = c.get("kind", "")
            if not target_diff_3:
                continue
            if kind not in (_KIND_IMPORT, _KIND_FROM_IMPORT):
                continue
            module_name = _diff_3_to_module(target_diff_3)
            if not module_name:
                continue
            # 跨平台：Windows 平台统一 lower()
            key = module_name.lower() if sys.platform == "win32" else module_name
            index[key] = target_diff_3
        return index

    def _resolve_diff_3(self, fullname: str) -> Optional[str]:
        """从 fullname（模块名）反查 target_diff_3。

        跨平台：Windows 平台统一 lower() 比对。

        Args:
            fullname: 要 import 的模块完整名

        Returns:
            对应的 target_diff_3（如 "script/config.py"），未命中返回 None
        """
        key = fullname.lower() if sys.platform == "win32" else fullname
        return self._managed_index.get(key)


# ============================================================
# MgcSealedLoader — 负责 unseal + exec module
# ============================================================

class MgcSealedLoader:
    """自定义 loader，负责 unseal + exec + 设 __file__/__name__/__loader__。

    Attributes:
        fullname: 模块名（如 "config"）
        finder: 所属 MgcSealedFinder
        target_diff_3: 在 mgc 中的 diff_3 路径（如 "script/config.py"）
    """

    def __init__(self, fullname: str, finder: MgcSealedFinder, target_diff_3: str):
        """初始化 loader，记录模块名、所属 finder、目标 diff_3 路径。

        Args:
            fullname: 模块名（如 "config"）
            finder: 所属 MgcSealedFinder
            target_diff_3: 在 mgc 中的 diff_3 路径（如 "script/config.py"）
        """
        self.fullname = fullname
        self.finder = finder
        self.target_diff_3 = target_diff_3

    def create_module(self, spec):
        """让 Python 用默认行为（空 module 对象），我们自己 exec 填它。

        PEP 451：返回 None 表示用默认 module。

        Args:
            spec: importlib.util.ModuleSpec（PEP 451 协议要求）

        Returns:
            None（Python 自动创建空 module）
        """
        return None

    def exec_module(self, module):
        """unseal + exec + 设 __file__/__name__/__loader__。

        流程：
        1. 查缓存（同一模块不重复 unseal）
        2. HTTP unseal_for_child RPC 拿明文 + child ext08
        3. 临时切 hook managed_index 到 child ext08（支持多层链式 import）
        4. exec 填 module 命名空间（包 try/except 避免 traceback 泄密）
        5. 还原 hook managed_index
        6. 设虚拟 __file__ / __name__ / __loader__
        7. 清理占位残留字段（__path__）
        8. 缓存

        Args:
            module: 已由 create_module 创建的空 module 对象

        Raises:
            ImportError: unseal 失败 / sealed 模块语法错 / exec 异常
                （错误消息不含 plaintext，防 traceback 泄密）
        """
        # 1. 查缓存
        if self.fullname in self.finder.session_cache:
            cached = self.finder.session_cache[self.fullname]
            module.__dict__.update(cached.__dict__)
            return

        # 2. HTTP unseal_for_child RPC（1.5.2 hotfix：返回 child ext08）
        unseal_result = self._unseal_via_rpc()
        if unseal_result is None:
            raise ImportError(
                f"MgcSealedLoader: unseal failed for {self.fullname} "
                f"(target_diff_3={self.target_diff_3})"
            )
        plaintext, child_ext08_str = unseal_result

        # 3. 临时切 hook managed_index + caller context 栈（多层链式 import 关键）
        #    例如：A → B → C。当 exec B 时，hook 需用 B 的 ext08 才能识别 B → C，
        #    且 B 内部 import config_a 触发的 unseal_for_child 必须用 B 的 caller_calls
        #    作为凭证（5+1 校验），否则主进程会拒。
        #    旧行为：始终用 caller（A）的 ext08，B → C 找不到 → ModuleNotFoundError。
        #    旧行为（hotfix 前）：即使找到 B，exec 期间 _unseal_via_rpc 还是用
        #    self.finder.context（A 的）→ caller_calls=[B,C] 不含 config_a → NOT_IN_CALLS。
        #    新行为：exec 期间同时压栈 child 的 managed_index 和 child context，
        #    exec 后弹栈。child_ext08_str 为空时（1.5.1 后端 / 子无调用方）保持 caller 行为。
        old_index = None
        old_ctx = None
        swapped = False
        child_ctx_wrapper = None
        if child_ext08_str:
            try:
                child_ext08_dict = json.loads(child_ext08_str) if isinstance(child_ext08_str, str) else child_ext08_str
            except (json.JSONDecodeError, ValueError):
                child_ext08_dict = {}
            if isinstance(child_ext08_dict, dict):
                # _build_managed_index 内部用 getattr(context, "ext08", None) 取 ext08，
                # 直接传 dict 会取不到，包 SimpleNamespace 让其暴露 ext08 属性
                from types import SimpleNamespace
                # === 1.5.2 hotfix (P0 caller context 栈) ===
                # 同时把 caller context 的 info_owner/diff_1/diff_2 继承自栈顶（默认顶层 caller），
                # 但 ext08 用 child 的——这样 B 内部 import config_a 时，RPC 发出的 caller_ext08_calls
                # 是 B 的，主进程 5+1 校验就能接受 config_a。
                parent_ctx = (
                    self.finder._context_stack[-1]
                    if self.finder._context_stack
                    else self.finder.context
                )
                child_ctx_wrapper = SimpleNamespace(
                    info_owner=getattr(parent_ctx, "info_owner", "") or "",
                    diff_1=getattr(parent_ctx, "diff_1", "") or "",
                    diff_2=getattr(parent_ctx, "diff_2", "") or "",
                    ext08=child_ext08_dict,
                )
                new_index = self.finder._build_managed_index(child_ctx_wrapper)
                old_index = self.finder._managed_index
                self.finder._managed_index = new_index
                # 压栈 caller context（B exec 期间 RPC 用 B 的 ext08）
                old_ctx = None  # 标记无需手动记栈顶，因为 _unseal_via_rpc 自己会读栈顶
                self.finder._context_stack.append(child_ctx_wrapper)
                swapped = True

        # 4. exec 填 module 命名空间（包 try/except 避免 traceback 泄密）
        try:
            exec(
                compile(plaintext, f"<mgc-sealed:{self.target_diff_3}>", "exec"),
                module.__dict__,
            )
        except SyntaxError as e:
            if swapped:
                self.finder._managed_index = old_index
                # 弹栈 caller context（即使抛错也必须弹，否则栈不平衡）
                if self.finder._context_stack and self.finder._context_stack[-1] is child_ctx_wrapper:
                    self.finder._context_stack.pop()
            raise ImportError(
                f"MgcSealedLoader: syntax error in sealed module {self.fullname}"
            ) from None  # 不暴露 plaintext
        except Exception as e:
            if swapped:
                self.finder._managed_index = old_index
                if self.finder._context_stack and self.finder._context_stack[-1] is child_ctx_wrapper:
                    self.finder._context_stack.pop()
            raise ImportError(
                f"MgcSealedLoader: exec failed for {self.fullname}: "
                f"{type(e).__name__}"
            ) from None  # 不暴露 plaintext

        # 5. 还原 hook managed_index + 弹栈 caller context（exec 成功路径）
        if swapped:
            self.finder._managed_index = old_index
            if self.finder._context_stack and self.finder._context_stack[-1] is child_ctx_wrapper:
                self.finder._context_stack.pop()

        # 6. 设虚拟 __file__ / __name__ / __loader__
        #    虚拟路径统一 POSIX 风格（如 "script/config.py"），pathlib 三平台兼容
        module.__file__ = self.target_diff_3
        module.__name__ = self.fullname
        module.__loader__ = self

        # 7. 清理占位残留字段
        #    find_spec 占位时设了 __path__=[]，避免污染 Python package 语义
        if hasattr(module, "__path__"):
            try:
                del module.__path__
            except AttributeError:
                pass

        # 8. 缓存
        self.finder.session_cache[self.fullname] = module

    # ---------- 内部：HTTP unseal RPC ----------

    def _unseal_via_rpc(self) -> Optional[Tuple[str, str]]:
        """POST /api/mgc/sensitive/unseal_for_child。

        5+1 校验由主进程强制执行（同 owner + diff_1 + diff_2 + ext08.calls 包含 target）。

        Returns:
            (plain_text, child_ext08_str) 元组；失败返回 None。
            1.5.2 hotfix：同时返回 child 的 ext08 字符串，让 exec_module
            在执行 child 期间临时切 hook 的 managed_index 到 child，
            支持多层链式 import（A → B → C）。
            1.5.2 hotfix (P0 caller context 栈)：caller 字段（info_owner /
            diff_1 / diff_2 / ext08.calls）从 context_stack 栈顶取，而非
            始终用顶层 caller——这样 B 内部 import config_a 时，发给主进程
            的 caller_ext08_calls 是 B 的，主进程 5+1 校验才能通过。
        """
        # 取当前生效的 caller context：栈顶优先，栈空时回退顶层 self.context
        if self.finder._context_stack:
            ctx = self.finder._context_stack[-1]
        else:
            ctx = self.finder.context
        if not self.finder.mgc_api_port or not self.finder.mgc_api_token:
            logger.error(
                "MgcSealedLoader: mgc_api_port / mgc_api_token not set, "
                "cannot fetch plaintext"
            )
            return None
        if not self.finder.internal_token:
            logger.error(
                "MgcSealedLoader: internal_token not set, "
                "cannot call /sensitive/unseal_for_child"
            )
            return None

        # 延迟导入 requests（避免 bootstrap 启动时硬依赖）
        try:
            import requests  # noqa: F401
        except ImportError:
            logger.error("MgcSealedLoader: 'requests' library not available")
            return None

        # 提取 caller_ext08.calls（callgraph 静态授权）
        ext08 = getattr(ctx, "ext08", None) or {}
        if not isinstance(ext08, dict):
            ext08 = {}
        caller_calls = ext08.get("calls", []) if isinstance(ext08.get("calls"), list) else []

        try:
            resp = requests.post(
                f"http://127.0.0.1:{self.finder.mgc_api_port}"
                f"/api/mgc/sensitive/unseal_for_child",
                headers={
                    "X-MGC-Token": self.finder.mgc_api_token,
                    "X-MGC-Internal-Token": self.finder.internal_token,
                    "Content-Type": "application/json",
                },
                json={
                    # caller 身份（来自 ScriptExecutionContext，bootstrap payload 已含完整 5 字段）
                    "caller_info_owner": getattr(ctx, "info_owner", "") or "",
                    "caller_diff_1": getattr(ctx, "diff_1", "") or "",
                    "caller_diff_2": getattr(ctx, "diff_2", "") or "",
                    "caller_ext08_calls": caller_calls,
                    # ★ phase5+ 修复：补传 target 完整 5 字段，让主进程用 4 字段主键精确查 target
                    #   （之前只传 target_diff_3，导致同 info_owner 多 diff_2 时查到错 record → DIFF2_MISMATCH）
                    #   import hook 的语义：被 import 的脚本必须在 caller 同 diff_2 包内
                    "target_info_type": "script",
                    "target_info_owner": getattr(ctx, "info_owner", "") or "",
                    "target_diff_1": getattr(ctx, "diff_1", "") or "",
                    "target_diff_2": getattr(ctx, "diff_2", "") or "",  # ★ 关键：与 caller 同包
                    "target_diff_3": self.target_diff_3,
                },
                timeout=30,
            )
            resp.raise_for_status()
            body = resp.json()
            if body.get("code") != 200:
                logger.warning(
                    f"MgcSealedLoader: /sensitive/unseal_for_child returned "
                    f"code={body.get('code')} msg={body.get('msg')}"
                )
                return None
            data = body.get("data")
            # === 1.5.2 hotfix：data 可能是 dict（新版后端，含 plain_text + ext08）
            #     或 str（1.5.1 后端，纯明文）。两种都兼容。===
            if isinstance(data, str):
                # 1.5.1 后端 / 旧后端：纯字符串。child_ext08 视为空（无链式能力）。
                plain = data if data else None
                if not plain:
                    return None
                return (plain, "")
            if isinstance(data, dict):
                plain = data.get("plain_text") or data.get("content") or ""
                child_ext08 = data.get("ext08", "") or ""
                if not plain:
                    return None
                return (plain, child_ext08)
            return None
        except Exception as e:
            logger.error(f"MgcSealedLoader: HTTP unseal_for_child failed: {e}")
            return None


# ============================================================
# 模块级辅助函数
# ============================================================

def _diff_3_to_module(target_diff_3: str) -> str:
    """把 target_diff_3（如 'script/config.py' / 'script/sub/config.py'）转模块名。

    规则（评审 3.3 整改）：
    - 取 basename，去扩展名（os.path.splitext(os.path.basename(...))[0]）
    - 与 Python 平铺目录 import 语义一致
    - 例：'script/config.py' → 'config'
    - 例：'script/sub/config.py' → 'config'（basename 简化，深层子目录不支持）

    限制：
    - 同包同名脚本在不同子目录（script/a/config.py + script/b/config.py）
      都会转成 'config'，会冲突。本方案不支持，callgraph 同包约束亦同。

    Args:
        target_diff_3: mgc 中的 diff_3 路径

    Returns:
        模块名（如 "config"）；空字符串若输入无效
    """
    if not target_diff_3 or not isinstance(target_diff_3, str):
        return ""
    basename = os.path.basename(target_diff_3)
    if not basename:
        return ""
    module_name = os.path.splitext(basename)[0]
    return module_name


# ============================================================
# 模块级：install / uninstall
# ============================================================

def install_sealed_import_hook(
    context: Any,
    mgc_api_port: Optional[int] = None,
    mgc_api_token: Optional[str] = None,
    internal_token: Optional[str] = "",
) -> MgcSealedFinder:
    """安装 MgcSealedFinder 到 sys.meta_path（monkey-patch import 系统）。

    通常在 bootstrap.main() 启动时调用（与 install_subprocess_adapter 并存）。
    安装后，业务代码 `import X` / `from X import Y` 会被 hook 拦截。

    Args:
        context: ScriptExecutionContext（当前 root 脚本的 ctx）
        mgc_api_port: mgc 主进程 HTTP 端口（finder 调 /sensitive/unseal_for_child 用）
        mgc_api_token: mgc 主进程 HTTP token（X-MGC-Token）
        internal_token: phase4 内部 RPC token（X-MGC-Internal-Token，与 mgc_api_token 隔离）

    Returns:
        安装的 MgcSealedFinder 实例（供后续 uninstall 用）
    """
    finder = MgcSealedFinder(
        context=context,
        mgc_api_port=mgc_api_port,
        mgc_api_token=mgc_api_token,
        internal_token=internal_token,
    )
    # 注册到 finder 链最前（优先于 PathFinder）
    sys.meta_path.insert(0, finder)

    managed_count = len(finder._managed_index)
    logger.info(
        f"sealed_import_hook installed: managed={managed_count}, "
        f"port={mgc_api_port}"
    )
    return finder


def uninstall_sealed_import_hook(finder: MgcSealedFinder) -> None:
    """卸载 MgcSealedFinder（从 sys.meta_path 移除）。

    通常在 bootstrap 子进程退出前调用（避免污染后续 exec）。

    Args:
        finder: 要卸载的 MgcSealedFinder 实例（install_sealed_import_hook 的返回值）

    Note:
        重复 uninstall安全（finder 不在 meta_path 时仅 warning，不抛异常）
    """
    try:
        sys.meta_path.remove(finder)
        logger.info("sealed_import_hook uninstalled")
    except ValueError:
        # finder 不在 meta_path 中（可能重复 uninstall），忽略
        logger.warning("sealed_import_hook: finder not in meta_path, skipping")


# ============================================================
# 暴露 API
# ============================================================

__all__ = [
    "MgcSealedFinder",
    "MgcSealedLoader",
    "install_sealed_import_hook",
    "uninstall_sealed_import_hook",
]
