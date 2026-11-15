"""ScriptExecutionService — 1.5.1 Sprint 2.5 phase3 统一执行入口。

职责：
1. 统一处理解密（get_sensitive）+ unseal（sealed package）
2. 构造 ScriptExecutionContext（含 ext08 分流）
3. 调用 script_executor.execute_script_ctx（fire-and-forget）
4. 持有 mgc_api_port + mgc_api_token（注入 bootstrap payload 用）

设计：
- 主进程永不阻塞（execute_script_ctx fire-and-forget）
- patched_run 自己 Popen bootstrap 子进程跑被调脚本（不通过主进程）
- 业务代码 0 改动
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from mgc.runtime.workflow_registry import ScriptExecutionContext

logger = logging.getLogger(__name__)


class ScriptExecutionService:
    """统一脚本执行服务。"""

    def __init__(self, sensitive_service, script_executor):
        """
        Args:
            sensitive_service: SensitiveService 实例（用于 get_sensitive + unseal）
            script_executor: ScriptExecutorService 实例（用于 execute_script_ctx）
        """
        self.sensitive_service = sensitive_service
        self.script_executor = script_executor
        self._mgc_api_port: Optional[int] = None
        self._mgc_api_token: Optional[str] = None
        # 1.5.4：unseal 失败时携带原始错误信息，让上层能透出友好文案
        self._last_unseal_error: Optional[str] = None

    def set_api_info(self, port: int, token: str) -> None:
        """注入 mgc 主进程 HTTP API 信息（bootstrap 子进程 HTTP 调用主进程时用）。

        应在 mgc 主进程 HTTP 服务启动后调用一次。
        """
        self._mgc_api_port = port
        self._mgc_api_token = token

    def execute(
        self,
        *,
        info_type: str,
        info_owner: str,
        diff_1: str = "",
        diff_2: str = "",
        diff_3: str,
        runtime_ext02: Optional[str] = None,
    ) -> Dict[str, Any]:
        """统一执行入口（fire-and-forget，返回 pid）。

        流程：
        1. get_sensitive 拿记录（含 plain_text + 全部 ext 字段）
        2. unseal（如果 ext04 非空）
        3. 构造 ScriptExecutionContext
        4. execute_script_ctx fire-and-forget（Popen bootstrap + 立即返回）

        Args:
            info_type: 信息类型（"script" / "text" / "sealed"）
            info_owner: 信息归属人
            diff_1/2/3: 差异字段
            runtime_ext02: 运行时参数（覆盖存储的 ext02）

        Returns:
            {pid, status: "started"} 或 {status: "failed", error}
        """
        import traceback
        # phase6 收尾：runtime_ext02 可能含业务日期/敏感 args，INFO 日志仅显示长度
        logger.info(
            f"ScriptExecutionService.execute ENTER: info_owner={info_owner}, "
            f"diff_3={diff_3}, runtime_ext02_len={len(runtime_ext02) if runtime_ext02 else 0}"
        )
        try:
            # Step 1: 解密
            self._last_unseal_error = None
            script_content = self._decrypt_and_unseal(
                info_type=info_type,
                info_owner=info_owner,
                diff_1=diff_1,
                diff_2=diff_2,
                diff_3=diff_3,
            )
            if not script_content:
                # 1.5.4：把 unseal 原始错误透出（PM Q8 决策：告知"来源方公钥错误"）
                err = self._last_unseal_error or "Script not found or decrypt failed"
                return {"status": "failed", "error": err}

            # Step 2: 拿完整记录（用于 ctx 构造）
            records = self.sensitive_service.get_sensitive(
                info_type=info_type,
                info_owner=info_owner,
                diff_1=diff_1,
                diff_2=diff_2,
                diff_3=diff_3,
            )
            if not records:
                return {"status": "failed", "error": "Script not found after decrypt"}
            record = records[0]

            # Step 3: 构造 ctx
            ctx = self._build_ctx(record, runtime_ext02)

            # Step 4: fire-and-forget 执行（启动 bootstrap）
            return self.script_executor.execute_script_ctx(
                ctx=ctx,
                script_content=script_content,
            )

        except Exception as e:
            logger.exception(f"ScriptExecutionService.execute failed: {e}")
            return {"status": "failed", "error": str(e)}

    def _decrypt_and_unseal(
        self,
        *,
        info_type: str,
        info_owner: str,
        diff_1: str,
        diff_2: str,
        diff_3: str,
    ) -> Optional[str]:
        """解密 + unseal（统一处理普通 folder 和 sealed package）。

        1. get_sensitive 解 AES_KEY_N 拿 plain_text
        2. 如果 ext04 非空（sealed package），调 seal_service.unseal_script 二次解密
        """
        try:
            records = self.sensitive_service.get_sensitive(
                info_type=info_type,
                info_owner=info_owner,
                diff_1=diff_1,
                diff_2=diff_2,
                diff_3=diff_3,
            )
            # phase6 收尾：DEBUG-decrypt_unseal 降级为 logger.debug()，隐藏 ext03
            # /plain_text_len / info_owner（避免 args 透传或脚本长度信息出现在主进程日志里）。
            # 触发可见条件：MGC_LOG_LEVEL=DEBUG。
            import logging as _lg
            _lg.getLogger(__name__).debug(
                f"[decrypt_unseal] query ok, "
                f"diff_3={diff_3}, has_records={bool(records)}"
            )
            if not records:
                return None
            record = records[0]
            plain_text = record.get("plain_text", "")
            _lg.getLogger(__name__).debug(
                f"[decrypt_unseal] record loaded, "
                f"diff_3={diff_3}, has_ext03={bool(record.get('ext03'))}"
            )

            # 普通 folder：plain_text 已经是明文
            # Sealed package：plain_text 仍是 base64 密文，需要 ext03（RSA encrypted
            # AES_KEY_4）+ node_priv 二次解密。1.5.1 BUG-A：之前误判 ext04，
            # 导致 sealed 脚本走 phase3 新路径时永远拿不到明文。
            ext03 = record.get("ext03", "")
            if not ext03:
                return plain_text

            # Sealed package：unseal 二次解密
            # 1.5.1 BUG-C 后续：fallback 自己创建 SealService（与 api_router 老 sealed 分支
            # 的 unseal_and_run 同样的模式），不依赖 sensitive_service.seal_service 属性注入。
            seal_service = getattr(self.sensitive_service, "seal_service", None)
            if not seal_service:
                from mgc.core.mgc_service.seal_service import SealService
                from mgc.core.mgc_service.node_key_service import (
                    get_or_init_node_key_service,
                )
                # 1.5.4：free mode unseal 需要 default_node_priv，必须从 sensitive_service
                # 注入 node_key_service；p2p mode 走 _get_priv_key 不依赖它但仍传入
                # （helper 内部同时支持"已有实例"与"lazy-init"两条路径）
                seal_service = SealService(
                    sensitive_service=self.sensitive_service,
                    node_key_service=get_or_init_node_key_service(self.sensitive_service),
                )
                logger.debug(
                    f"[decrypt_unseal] seal_service not pre-injected, "
                    f"created fallback for diff_3={diff_3}"
                )

            try:
                result = seal_service.unseal_script({
                    "content": plain_text,
                    "ext03": ext03,
                    "ext01": record.get("ext01", ""),
                    "ext07": record.get("ext07", ""),
                    "ext09": record.get("ext09", ""),
                })
                _lg.getLogger(__name__).debug(
                    f"[decrypt_unseal] unseal_script ok, "
                    f"diff_3={diff_3}, len={len(result) if result else 0}"
                )
                return result
            except Exception as e:
                logger.error(f"unseal failed for {diff_3}: {e}")
                # 1.5.4：把原始 unseal 错误透传给上层（PM Q8：链路鉴权失败应当
                # 告知"来源方公钥错误"，让用户知道是 ext07/ext09 被改了）
                self._last_unseal_error = str(e)
                return None

        except Exception as e:
            logger.error(f"_decrypt_and_unseal error: {e}")
            self._last_unseal_error = str(e)
            return None

    def _build_ctx(
        self,
        record: Dict[str, Any],
        runtime_ext02: Optional[str],
    ) -> ScriptExecutionContext:
        """构造 ScriptExecutionContext（含 ext08 解析 + 同包 records）。"""
        ext08_str = record.get("ext08", "")
        ext08_dict: Optional[Dict[str, Any]] = None
        if ext08_str:
            try:
                ext08_dict = json.loads(ext08_str) if isinstance(ext08_str, str) else ext08_str
            except (json.JSONDecodeError, ValueError, TypeError):
                ext08_dict = None

        # 拿同包所有 record（含被调脚本的密文）
        all_records = self._list_records_by_pkg(
            record.get("info_owner", ""),
            record.get("diff_1", ""),
            record.get("diff_2", ""),
        )

        return ScriptExecutionContext(
            execution_id=str(uuid.uuid4()),
            info_owner=record.get("info_owner", ""),
            diff_1=record.get("diff_1", ""),
            diff_2=record.get("diff_2", ""),
            diff_3=record.get("diff_3", ""),
            ext01=record.get("ext01", ""),
            ext02=runtime_ext02 if runtime_ext02 is not None else record.get("ext02", ""),
            ext08=ext08_dict,
            workspace="",  # phase3 不物化
            module_file="",  # phase3 不读文件
            all_records=all_records or [],
            parent_execution_id=None,
            internal_token=self._mgc_api_token,
            hard_deadline=None,
            started_at=None,
        )

    def _list_records_by_pkg(
        self,
        info_owner: str,
        diff_1: str,
        diff_2: str,
    ) -> List[Dict[str, Any]]:
        """列同 package 所有 record（用于 patched_run lookup 索引）。

        实现：通过 execute_query 直接查 DB（不走 get_sensitive，避免递归解密）。
        """
        try:
            db_handler = self.sensitive_service.database_handler
            # 注意：SQLite 的 NULL 比较规则要求用 (col IS NULL OR col = ?)。
            # 业务场景下 diff_1 经常为 NULL（普通 folder 存时未指定 diff_1），
            # 严格 diff_1 = ? 会过滤掉这些 record。
            query = (
                "SELECT info_type, info_owner, diff_1, diff_2, diff_3, "
                "ext01, ext02, ext04, ext08 "
                "FROM mgc_info_1 "
                "WHERE info_owner = ? "
                "AND (diff_1 IS NULL OR diff_1 = ?) "
                "AND (diff_2 IS NULL OR diff_2 = ?)"
            )
            rows = db_handler.execute_query(
                query, (info_owner, diff_1, diff_2)
            )
            logger.info(
                f"_list_records_by_pkg: info_owner={info_owner}, diff_1={diff_1!r}, "
                f"diff_2={diff_2!r}, rows={len(rows) if rows else 0}"
            )
            if not rows:
                return []
            return [dict(r) for r in rows]
        except Exception as e:
            logger.warning(f"_list_records_by_pkg error: {e}")
            return []