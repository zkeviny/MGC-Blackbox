"""Agent交互相关异常

用途：
- 定义Agent交互相关的异常类
- 为Agent交互提供标准化的异常处理
- 确保Agent交互过程中的错误能够被正确捕获和处理

依赖：
- 无外部依赖

未来演进：
- 可扩展支持更多Agent交互相关的异常类型
"""

class AgentException(Exception):
    """Agent异常基类"""
    pass

class InputError(AgentException):
    """输入错误"""
    pass

class OutputError(AgentException):
    """输出错误"""
    pass

class ValidationError(AgentException):
    """验证错误"""
    pass
