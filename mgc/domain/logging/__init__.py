"""
Logging module for MGC operation logs
"""
from mgc.domain.logging.operation_log_manager import (
    OperationLogManager,
    get_operation_log_manager
)

__all__ = [
    "OperationLogManager",
    "get_operation_log_manager"
]
