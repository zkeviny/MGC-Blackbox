"""本地进程间通信模块

用途：
- 实现AI/Agent与黑盒接口的本地进程间通信
- 支持Python subprocess或本地Socket通信方式
- 提供标准化的通信接口

依赖：
- 依赖core/interface/blackbox_interface.py
"""

import json
import subprocess
import sys
import os
from typing import Dict, Any
from mgc.core.interface.blackbox_interface import BlackboxInterface

class LocalIPC:
    """本地进程间通信实现"""
    
    def __init__(self):
        """初始化本地IPC"""
        self.blackbox = BlackboxInterface()
    
    def send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """发送请求到黑盒接口
        
        Args:
            request: 请求数据
            
        Returns:
            Dict[str, Any]: 响应数据
        """
        try:
            # 转换请求为JSON字符串
            request_json = json.dumps(request, ensure_ascii=False)
            
            # 调用黑盒接口处理请求
            response_json = self.blackbox.handle_request(request_json)
            
            # 解析响应
            response = json.loads(response_json)
            return response
        except Exception as e:
            return {
                "request_id": request.get("request_id", ""),
                "code": 500,
                "message": f"通信异常: {str(e)}",
                "data": {},
                "timestamp": int(os.time()) if 'os' in dir() else 0
            }
    
    def run_as_subprocess(self):
        """以子进程方式运行，处理标准输入输出"""
        try:
            while True:
                # 读取标准输入
                line = sys.stdin.readline()
                if not line:
                    break
                
                try:
                    # 解析输入
                    request = json.loads(line.strip())
                    
                    # 处理请求
                    response = self.send_request(request)
                    
                    # 输出响应
                    print(json.dumps(response, ensure_ascii=False))
                    sys.stdout.flush()
                except json.JSONDecodeError:
                    error_response = {
                        "request_id": "",
                        "code": 400,
                        "message": "JSON格式错误",
                        "data": {},
                        "timestamp": int(os.time()) if 'os' in dir() else 0
                    }
                    print(json.dumps(error_response, ensure_ascii=False))
                    sys.stdout.flush()
                except Exception as e:
                    error_response = {
                        "request_id": "",
                        "code": 500,
                        "message": f"处理异常: {str(e)}",
                        "data": {},
                        "timestamp": int(os.time()) if 'os' in dir() else 0
                    }
                    print(json.dumps(error_response, ensure_ascii=False))
                    sys.stdout.flush()
        except KeyboardInterrupt:
            pass
    
    def initialize_storage(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """初始化存储服务
        
        Args:
            config: 初始化配置（包含 mysql_host, mysql_port, mysql_root_password, agent_uuid, personal_key, weight_param）
            
        Returns:
            Dict[str, Any]: 初始化结果
        """
        try:
            response_json = self.blackbox.initialize_storage(
                mysql_host=config.get("mysql_host", "localhost"),
                mysql_port=config.get("mysql_port", 3306),
                mysql_root_password=config.get("mysql_root_password", ""),
                agent_uuid=config.get("agent_uuid", ""),
                personal_key=config.get("personal_key", ""),
                weight_param=config.get("weight_param", 0)
            )
            return json.loads(response_json)
        except Exception as e:
            return {
                "code": 500,
                "message": f"初始化异常: {str(e)}",
                "data": {}
            }
    
    def cleanup(self):
        """清理资源"""
        self.blackbox.cleanup()


def main():
    """主函数，用于子进程模式"""
    ipc = LocalIPC()
    ipc.run_as_subprocess()


if __name__ == "__main__":
    main()
