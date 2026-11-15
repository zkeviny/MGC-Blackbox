"""文件输入模块

用途：
- 处理文件输入
- 读取文件内容并转换为标准化输入数据
- 为解析层提供文件输入数据

依赖：
- 依赖models/input_model.py
- 依赖utils/path_utils.py

未来演进：
- 可扩展支持更多文件类型
- 可添加文件验证和错误处理
"""

import os
import json
from mgc.models.input_model import InputData
from mgc.utils.path_utils import get_absolute_path
from mgc.utils.cache_utils import save_input_cache
from mgc.utils.request_converter import convert_to_mgc_request

class FileInput:
    """文件输入处理
    
    实现文件输入功能，支持txt文件解析
    """
    
    def __init__(self):
        """初始化文件输入处理器"""
        pass
    
    def read_file(self, file_path, agent_uuid: str = ""):
        """读取文件内容
        
        Args:
            file_path: 文件路径
            agent_uuid: Agent UUID标识（来源优先级：入参 > 配置 > 默认值）
        
        Returns:
            InputData: 标准化输入数据
        
        Raises:
            ValueError: 当agent_uuid缺失时抛出异常
        """
        if not agent_uuid:
            raise ValueError("agent_uuid is required for data isolation")
        
        absolute_path = get_absolute_path(file_path)
        if not os.path.exists(absolute_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # 读取文件内容
        content = None
        error_message = None
        try:
            # 尝试以UTF-8编码读取
            with open(absolute_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # 尝试以GBK编码读取
            try:
                with open(absolute_path, 'r', encoding='gbk') as f:
                    content = f.read()
            except Exception as e:
                error_message = f"Failed to read file: {str(e)}"
        except Exception as e:
            error_message = f"Failed to read file: {str(e)}"

        # 如果读取失败，保存到缓存并抛出异常
        if content is None:
            save_input_cache(
                input_type="file",
                content="",
                error_message=error_message,
                source_path=file_path
            )
            raise IOError(error_message)
        
        # 解析文件内容，提取info_owner和info_type
        try:
            info_owner, info_type = self._parse_file_content(content)
        except ValueError as e:
            # 解析失败，保存到缓存
            save_input_cache(
                input_type="file",
                content=content,
                error_message=str(e),
                source_path=file_path
            )
            raise

        # 验证文件格式
        if not self.validate_file(content):
            error_msg = "Invalid file format"
            save_input_cache(
                input_type="file",
                content=content,
                error_message=error_msg,
                source_path=file_path
            )
            raise ValueError(error_msg)
        
        # 创建标准化输入数据
        return InputData(
            input_type="file",
            content=content,
            source_path=file_path,
            info_owner=info_owner,
            info_type=info_type,
            agent_uuid=agent_uuid
        )
    
    def _parse_file_content(self, content):
        """解析文件内容，提取info_owner和info_type
        
        Args:
            content: 文件内容
        
        Returns:
            tuple: (info_owner, info_type)
        """
        # 简单解析逻辑：假设文件内容格式为 key: value 形式
        # 例如：
        # info_owner: 张三
        # info_type: 手机号
        info_owner = None
        info_type = None
        
        lines = content.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('info_owner:'):
                info_owner = line.split(':', 1)[1].strip()
            elif line.startswith('info_type:'):
                info_type = line.split(':', 1)[1].strip()
        
        # 验证必填字段
        if not info_owner:
            raise ValueError("Missing info_owner in file")
        if not info_type:
            raise ValueError("Missing info_type in file")
        
        return info_owner, info_type
    
    def validate_file(self, content):
        """验证文件
        
        Args:
            content: 文件内容
        
        Returns:
            bool: 文件是否有效
        """
        # 验证文件格式是否符合mgc_query_list.md规范
        # 检查是否包含info_owner和info_type
        lines = content.strip().split('\n')
        has_info_owner = False
        has_info_type = False
        
        for line in lines:
            line = line.strip()
            if line.startswith('info_owner:'):
                has_info_owner = True
            elif line.startswith('info_type:'):
                has_info_type = True
        
        return has_info_owner and has_info_type

    def to_mgc_request(self, input_data: InputData):
        """转换为MGCRequest对象

        Args:
            input_data: InputData对象

        Returns:
            MGCRequest: MGC请求对象
        """
        return convert_to_mgc_request(input_data)
