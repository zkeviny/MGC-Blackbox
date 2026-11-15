"""MGC workflow registry — 1.5.1 Sprint 2.5 phase3 精简版。

仅保留 ScriptExecutionContext dataclass + from_dict / to_dict。
phase3 重构后不再需要 registry 跟踪 / sweeper / get / register / unregister。
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class ScriptExecutionContext:
    """脚本执行上下文（bootstrap 子进程 stdin payload 的结构化表示）。

    Attributes:
        execution_id: 唯一执行 ID（UUID）
        info_owner: 信息归属人
        diff_1/2/3: 差异字段
        ext01: 启动命令
        ext02: 运行参数
        ext08: 静态分析结果（含 calls / is_dependency 等）
        workspace: 物化目录（phase3 不再物化，默认空字符串）
        module_file: 脚本路径（phase3 不读文件，默认空字符串）
        all_records: 同 package 所有 record 列表（含被调脚本）
        parent_execution_id: 父执行 ID（patched_run 递归时使用）
        internal_token: 内部 RPC token（patched_run 调 /sensitive/get 用）
        hard_deadline: 硬截止时间戳（timeout 监控，phase3 暂不实现）
        started_at: 启动时间戳
    """
    execution_id: str = ""
    info_owner: str = ""
    diff_1: str = ""
    diff_2: str = ""
    diff_3: str = ""
    ext01: str = ""
    ext02: str = ""
    ext08: Optional[Dict[str, Any]] = None
    workspace: str = ""
    module_file: str = ""
    all_records: List[Dict[str, Any]] = field(default_factory=list)
    parent_execution_id: Optional[str] = None
    internal_token: Optional[str] = None
    hard_deadline: Optional[float] = None
    started_at: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScriptExecutionContext":
        """从 dict 构造 ScriptExecutionContext（bootstrap 读 stdin 后调用）。"""
        return cls(
            execution_id=data.get("execution_id", ""),
            info_owner=data.get("info_owner", ""),
            diff_1=data.get("diff_1", ""),
            diff_2=data.get("diff_2", ""),
            diff_3=data.get("diff_3", ""),
            ext01=data.get("ext01", ""),
            ext02=data.get("ext02", ""),
            ext08=data.get("ext08"),
            workspace=data.get("workspace", ""),
            module_file=data.get("module_file", ""),
            all_records=data.get("all_records", []) or [],
            parent_execution_id=data.get("parent_execution_id"),
            internal_token=data.get("internal_token"),
            hard_deadline=data.get("hard_deadline"),
            started_at=data.get("started_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 dict（payload 构造时使用）。"""
        return asdict(self)
