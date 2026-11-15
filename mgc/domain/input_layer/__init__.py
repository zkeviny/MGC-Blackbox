"""录入层包标识

用途：
- 标识input_layer包，使Python能够识别为可导入的包
- 统一导出录入层功能

依赖：
- 无外部依赖

未来演进：
- 可扩展支持对话和工作流输入
"""

# 导出录入层功能
from .file_input import FileInput
from .text_input import TextInput
from .dialogue_input import DialogueInput
from .workflow_input import WorkflowInput

__all__ = ["FileInput", "TextInput", "DialogueInput", "WorkflowInput"]
