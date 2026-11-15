"""
令牌管理器
负责 MGC 本机令牌生成、存储、校验
"""
import os
import platform
import secrets
import base64
from pathlib import Path
from typing import Optional
import logging

from mgc.config.path_config import DB_DIR

logger = logging.getLogger(__name__)


class TokenManager:
    """
    令牌管理器
    
    功能：
    - 生成一次性随机令牌（内存存储，每次启动重新生成）
    - 令牌文件存储（与 vault 同目录）
    - 设置严格权限（仅当前用户可读写）
    - 令牌校验
    """
    
    TOKEN_FILE_NAME = ".mgc_token"
    TOKEN_LENGTH = 32  # 32 bytes -> ~43 chars base64
    
    def __init__(self, vault_dir: str = None):
        """
        初始化令牌管理器
        
        入参：
            vault_dir: vault 目录（默认与数据库同目录）
        """
        self.vault_dir = Path(vault_dir) if vault_dir else DB_DIR
        self._ensure_vault_dir()
        
        self._token: Optional[str] = None
        self._token_file = self.vault_dir / self.TOKEN_FILE_NAME
    
    def _ensure_vault_dir(self):
        """确保 vault 目录存在"""
        if not self.vault_dir.exists():
            self.vault_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_token(self) -> str:
        """
        生成随机令牌
        
        出参：
            32位随机字符串（Base64编码）
        """
        token_bytes = secrets.token_bytes(self.TOKEN_LENGTH)
        self._token = base64.urlsafe_b64encode(token_bytes).decode("utf-8")
        return self._token
    
    def save_token(self, token: str = None):
        """
        保存令牌到文件（设置权限）
        
        入参：
            token: 令牌（可选，不提供则使用内存中的令牌）
        """
        if token is None:
            token = self._token or self.generate_token()
        
        if token != self._token:
            self._token = token
        
        with open(self._token_file, "w", encoding="utf-8") as f:
            f.write(token)
        
        self._set_file_permissions()
        
        logger.info(f"Token saved: {self._token_file}")
    
    def load_token(self) -> Optional[str]:
        """
        加载令牌
        
        出参：
            令牌字符串，若文件不存在则返回 None
        """
        if self._token:
            return self._token
        
        if not self._token_file.exists():
            return None
        
        try:
            with open(self._token_file, "r", encoding="utf-8") as f:
                self._token = f.read().strip()
            return self._token
        except Exception as e:
            logger.debug(f"Failed to load token: {e}")
            return None
    
    def get_token(self) -> str:
        """
        获取令牌（自动加载或生成）
        
        出参：
            令牌字符串
        """
        if not self._token:
            self.load_token()
        
        if not self._token:
            self.generate_token()
            self.save_token()
        
        return self._token
    
    def validate_token(self, token: str) -> bool:
        """
        校验令牌
        
        入参：
            token: 待校验的令牌
            
        出参：
            True 表示有效，False 表示无效
        """
        if not token or not self._token:
            return False
        
        return token == self._token
    
    def _set_file_permissions(self):
        """
        设置令牌文件最小权限
        
        - Windows: 使用 icacls 设置仅当前用户可读写
        - Linux/macOS: chmod 600
        """
        system = platform.system()
        
        try:
            if system == "Windows":
                current_user = os.getenv("USERNAME", "Everyone")
                os.system(f'icacls "{self._token_file}" /inheritance:r /T >nul 2>&1')
                os.system(f'icacls "{self._token_file}" /grant:r "{current_user}:(R,W)" /T >nul 2>&1')
            else:
                os.chmod(self._token_file, 0o600)
            
            logger.debug(f"Token file permissions set: {system}")
        except Exception as e:
            logger.error(f"Failed to set token file permissions: {e}")
    
    def delete_token(self):
        """删除令牌文件"""
        if self._token_file.exists():
            self._token_file.unlink()
            logger.info("Token deleted")
        
        self._token = None


_token_manager = None


def get_token_manager(vault_dir: str = None) -> TokenManager:
    """
    获取令牌管理器单例
    
    入参：
        vault_dir: vault 目录
        
    出参：
        TokenManager 实例
    """
    global _token_manager
    
    if _token_manager is None:
        _token_manager = TokenManager(vault_dir=vault_dir)
    
    return _token_manager
