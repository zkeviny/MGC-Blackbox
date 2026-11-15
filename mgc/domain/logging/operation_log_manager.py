"""
操作日志管理器
负责记录 MGC 敏感信息操作日志（存入/取出/删除/迁移）
"""
import os
import gzip
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import logging

from mgc.config.path_config import DB_DIR

logger = logging.getLogger(__name__)


class OperationLogManager:
    """
    操作日志管理器
    
    功能：
    - 记录敏感信息操作日志（存入/取出/删除/迁移）
    - JSON Lines 格式存储
    - 整行加密（复用 CryptoService）
    - 自动滚动（10MB/7天）
    """
    
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    RETAIN_DAYS = 7
    
    def __init__(self, crypto_service=None, log_dir: str = None):
        """
        初始化操作日志管理器
        
        入参：
            crypto_service: 加密服务实例（用于日志加密）
            log_dir: 日志目录（默认与 vault 同目录）
        """
        self.crypto_service = crypto_service
        self.log_dir = Path(log_dir) if log_dir else DB_DIR
        self._ensure_log_dir()
        
        self._lock = threading.Lock()
    
    def _ensure_log_dir(self):
        """确保日志目录存在"""
        if not self.log_dir.exists():
            self.log_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def _log_file_path(self) -> Path:
        """当前日志文件路径"""
        return self.log_dir / "mgc_operation.log"
    
    def _get_dated_log_path(self, date_str: str = None) -> Path:
        """获取带日期的日志文件路径"""
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
        return self.log_dir / f"mgc_operation_{date_str}.log"
    
    def _encrypt_line(self, plaintext: str) -> str:
        """加密单行日志（复用 CryptoService）"""
        if self.crypto_service:
            return self.crypto_service.encrypt_text(plaintext)
        return plaintext
    
    def _decrypt_line(self, ciphertext: str) -> str:
        """解密单行日志"""
        if self.crypto_service:
            return self.crypto_service.decrypt_text(ciphertext)
        return ciphertext
    
    def log_operation(self, operation_type: str, key_alias: str,
                     operation_result: str, duration_ms: int = None,
                     info_owner: str = None):
        """
        记录操作日志
        
        入参：
            operation_type: 操作类型（SAVE/GET/DELETE/MIGRATE）
            key_alias: 信息键名
            operation_result: 操作结果（SUCCESS/FAILED）
            duration_ms: 操作耗时（毫秒）
            info_owner: 信息归属人
        """
        log_entry = {
            "timestamp": datetime.now().isoformat() + "Z",
            "operation": operation_type,
            "key_alias": key_alias,
            "result": operation_result,
        }
        
        if duration_ms is not None:
            log_entry["duration_ms"] = duration_ms
        
        if info_owner:
            log_entry["info_owner"] = info_owner
        
        plaintext = json.dumps(log_entry, ensure_ascii=False)
        ciphertext = self._encrypt_line(plaintext)
        
        self._write_log(ciphertext)
    
    def _write_log(self, ciphertext: str):
        """写入日志（线程安全）"""
        with self._lock:
            log_path = self._log_file_path
            
            if log_path.exists() and log_path.stat().st_size > self.MAX_FILE_SIZE:
                self._rotate_log(log_path)
            
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(ciphertext + "\n")
    
    def _rotate_log(self, log_path: Path):
        """滚动日志（后台异步执行压缩和清理）"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archived_path = log_path.parent / f"{log_path.stem}.{timestamp}{log_path.suffix}"
        
        log_path.rename(archived_path)
        
        threading.Thread(target=self._compress_log, args=(archived_path,)).start()
        threading.Thread(target=self._cleanup_old_logs).start()
    
    def _compress_log(self, file_path: Path):
        """压缩日志文件"""
        try:
            with open(file_path, "rb") as f_in:
                with gzip.open(f"{file_path}.gz", "wb") as f_out:
                    f_out.writelines(f_in)
            os.remove(file_path)
            logger.debug(f"Log compression completed: {file_path}")
        except Exception as e:
            logger.debug(f"Log compression failed: {e}")
    
    def _cleanup_old_logs(self):
        """清理过期日志"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.RETAIN_DAYS)
            
            for file in self.log_dir.glob("mgc_operation*.log*"):
                if file.suffix == ".gz":
                    continue
                
                mtime = datetime.fromtimestamp(file.stat().st_mtime)
                if mtime < cutoff_date:
                    file.unlink()
                    logger.debug(f"Expired log deleted: {file}")
        except Exception as e:
            logger.debug(f"Log cleanup failed: {e}")
    
    def query_logs(self, start_time: str = None, end_time: str = None,
                   operation_type: str = None, limit: int = 100) -> List[Dict]:
        """
        查询日志
        
        入参：
            start_time: 开始时间（ISO格式）
            end_time: 结束时间（ISO格式）
            operation_type: 操作类型过滤
            limit: 返回条数限制
            
        出参：
            日志列表（已解密）
        """
        logs = []
        
        log_files = sorted(self.log_dir.glob("mgc_operation*.log*"), reverse=True)
        
        for log_file in log_files:
            try:
                if log_file.suffix == ".gz":
                    opener = gzip.open
                else:
                    opener = open
                
                with opener(log_file, "rt", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        try:
                            plaintext = self._decrypt_line(line)
                            entry = json.loads(plaintext)
                            
                            if self._filter_log(entry, start_time, end_time, operation_type):
                                logs.append(entry)
                                
                                if len(logs) >= limit:
                                    return logs
                        except Exception:
                            continue
            
            except Exception as e:
                logger.debug(f"Failed to read log file {log_file}: {e}")
        
        return logs
    
    def _filter_log(self, entry: Dict, start_time: str, end_time: str,
                    operation_type: str) -> bool:
        """过滤日志条目"""
        if operation_type and entry.get("operation") != operation_type:
            return False
        
        if start_time or end_time:
            log_time = entry.get("timestamp", "")
            
            if start_time and log_time < start_time:
                return False
            if end_time and log_time > end_time:
                return False
        
        return True


_operation_log_manager = None


def get_operation_log_manager(crypto_service=None) -> OperationLogManager:
    """
    获取操作日志管理器单例
    
    入参：
        crypto_service: 加密服务实例
        
    出参：
        OperationLogManager 实例
    """
    global _operation_log_manager
    
    if _operation_log_manager is None:
        _operation_log_manager = OperationLogManager(crypto_service=crypto_service)
    
    return _operation_log_manager
