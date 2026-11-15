"""Agent交互辅助工具

用途：
- 提供Agent交互相关的辅助函数
- 支持Agent Skills调用的格式化
- 为Agent交互提供工具支持

依赖：
- 无外部依赖

未来演进：
- 可扩展支持更多Agent交互功能
- 可添加Agent平台适配
"""

from mgc.config.agent_config import AGENT_CONFIG, AGENT_PARAMS

# 格式化Agent响应
def format_agent_response(response_data):
    """格式化Agent响应
    
    Args:
        response_data: 响应数据
    
    Returns:
        dict: 格式化后的响应
    """
    return {
        "version": AGENT_CONFIG["version"],
        "data": response_data,
        "status": "success"
    }

# 验证Agent输入
def validate_agent_input(input_data):
    """验证Agent输入
    
    Args:
        input_data: 输入数据
    
    Returns:
        bool: 输入是否有效
    """
    # 未来可实现输入验证逻辑
    return True

# 处理Agent错误
def handle_agent_error(error):
    """处理Agent错误
    
    Args:
        error: 错误信息
    
    Returns:
        dict: 错误响应
    """
    return {
        "version": AGENT_CONFIG["version"],
        "error": str(error),
        "status": "error"
    }
