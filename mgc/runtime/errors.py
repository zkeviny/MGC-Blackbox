"""MGC runtime errors.

1.5.1 Sprint 2.5 phase3 精简版：仅保留必要错误类。
"""


class MgcScriptExecutionError(Exception):
    """用户脚本执行异常。"""
    pass


class MgcSecurityViolation(Exception):
    """安全违规（如 patched_run 拦截到不在授权集合内的脚本调用）。"""
    def __init__(self, target: str, reason: str = ""):
        self.target = target
        self.reason = reason
        super().__init__(f"security violation: target={target}, reason={reason}")