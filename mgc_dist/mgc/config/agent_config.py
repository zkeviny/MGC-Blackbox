"""Agent交互配置

用途：
- 预留Agent交互相关的配置
- 为未来Agent Skills调用提供配置支持
- 定义Agent交互的参数和规则

依赖：
- 无外部依赖

未来演进：
- 实现Agent Skills的配置管理
- 支持多Agent平台的适配
"""

# Agent交互配置
AGENT_CONFIG = {
    "version": "1.0",  # Agent配置版本
    "skills": {
        "name": "MirginCipher",  # Skills名称
        "description": "AI Agent隐私信息加密工具",  # Skills描述
        "version": "1.0.0"  # Skills版本
    },
    "interaction": {
        "timeout": 30,  # 交互超时时间（秒）
        "retry_count": 3  # 重试次数
    }
}

# Agent调用参数
AGENT_PARAMS = {
    "input_types": ["text", "file"],  # 支持的输入类型
    "output_types": ["text"],  # 支持的输出类型
    "max_input_size": 1024 * 1024  # 最大输入大小（字节）
}
