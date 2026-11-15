"""HTTP客户端模块 (v1.0)

用途：
- 提供HTTP请求、文件下载、断点续传功能
- 支持超时、重试和错误处理
- 用于版本检查、技能包下载、心跳上报

规范：
- 所有网络请求必须捕获异常
- 支持双源下载和自动切换
- 无网络时不阻塞核心功能
"""

import time
from typing import Dict, Optional, Any
from pathlib import Path


class HttpClient:
    """HTTP客户端"""
    
    def __init__(self, timeout: int = 30, retries: int = 3):
        """
        初始化HTTP客户端
        
        @param timeout: 默认超时时间（秒）
        @param retries: 默认重试次数
        """
        self.timeout = timeout
        self.retries = retries
    
    def get(self, url: str, timeout: int = None, **kwargs) -> Dict:
        """
        发送GET请求
        
        @param url: 请求地址
        @param timeout: 超时时间（毫秒）
        @param kwargs: 其他requests参数
        @return: {"status": "success"/"error", "data"/"message": ...}
        """
        try:
            import requests
            
            timeout_sec = (timeout / 1000) if timeout else self.timeout
            
            response = requests.get(url, timeout=timeout_sec, **kwargs)
            response.raise_for_status()
            
            try:
                data = response.json()
            except ValueError:
                data = response.text
            
            return {"status": "success", "data": data}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def post(self, url: str, data: Dict = None, json: Dict = None,
             timeout: int = None, **kwargs) -> Dict:
        """
        发送POST请求
        
        @param url: 请求地址
        @param data: 表单数据
        @param json: JSON数据
        @param timeout: 超时时间（毫秒）
        @param kwargs: 其他requests参数
        @return: {"status": "success"/"error", "data"/"message": ...}
        """
        try:
            import requests
            
            timeout_sec = (timeout / 1000) if timeout else self.timeout
            
            response = requests.post(
                url, data=data, json=json,
                timeout=timeout_sec, **kwargs
            )
            response.raise_for_status()
            
            try:
                resp_data = response.json()
            except ValueError:
                resp_data = response.text
            
            return {"status": "success", "data": resp_data}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def patch(self, url: str, json: Dict = None,
              timeout: int = None, **kwargs) -> Dict:
        """
        发送PATCH请求

        @param url: 请求地址
        @param json: JSON数据
        @param timeout: 超时时间（秒）
        @param kwargs: 其他requests参数
        @return: {"status": "success"/"error", "data"/"message": ...}
        """
        try:
            import requests

            timeout_sec = (timeout / 1000) if timeout else self.timeout

            response = requests.patch(
                url, json=json,
                timeout=timeout_sec, **kwargs
            )
            response.raise_for_status()

            try:
                resp_data = response.json()
            except ValueError:
                resp_data = response.text

            return {"status": "success", "data": resp_data}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def download(self, url: str, save_path: str,
                 timeout: int = None, resume: bool = True) -> Dict:
        """
        下载文件（支持断点续传）
        
        @param url: 下载地址
        @param save_path: 保存路径
        @param timeout: 超时时间（毫秒）
        @param resume: 是否支持断点续传
        @return: {"status": "success"/"error", "path"/"message": ...}
        """
        try:
            import requests
            
            timeout_sec = (timeout / 1000) if timeout else self.timeout
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            headers = {}
            existing_size = 0
            
            # 断点续传
            if resume and save_path.exists():
                existing_size = save_path.stat().st_size
                headers["Range"] = f"bytes={existing_size}-"
            
            response = requests.get(
                url, headers=headers, timeout=timeout_sec, stream=True
            )
            response.raise_for_status()
            
            mode = "ab" if resume and existing_size > 0 else "wb"
            with open(save_path, mode) as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            return {"status": "success", "path": str(save_path)}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def download_with_fallback(self, primary_url: str, secondary_url: str,
                               save_path: str, timeout: int = None,
                               max_retry: int = 3) -> Dict:
        """
        双源下载（主源失败自动切换备源）
        
        @param primary_url: 主源地址
        @param secondary_url: 备源地址
        @param save_path: 保存路径
        @param timeout: 超时时间（毫秒）
        @param max_retry: 每源最大重试次数
        @return: {"status": "success"/"error", "path"/"message": ...}
        """
        urls = [("primary", primary_url), ("secondary", secondary_url)]
        
        for source_name, url in urls:
            if not url:
                continue
            
            for attempt in range(max_retry):
                result = self.download(url, save_path, timeout)
                if result["status"] == "success":
                    return {**result, "source": source_name}
                
                if attempt < max_retry - 1:
                    time.sleep(2)
        
        return {
            "status": "error",
            "message": "所有下载源均失败"
        }
    
    def check_connectivity(self, url: str, timeout: int = 3000) -> bool:
        """
        检查网络连通性
        
        @param url: 测试地址
        @param timeout: 超时时间（毫秒）
        @return: True=可连通，False=不可连通
        """
        result = self.get(url, timeout=timeout)
        return result["status"] == "success"
