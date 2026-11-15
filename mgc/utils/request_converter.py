"""请求转换工具模块

用途：
- 提供InputData到MGCRequest的转换功能
- 支持在需要时创建标准化的请求对象

依赖：
- src.models.input_model.InputData
- src.models.input_model.MGCRequest
- src.config.enum_config.OperationType

未来演进：
- 可扩展支持更多转换场景
"""

import time
from mgc.models.input_model import InputData, MGCRequest
from mgc.config.enum_config import OperationType


def convert_to_mgc_request(input_data: InputData) -> MGCRequest:
    """将InputData转换为MGCRequest

    Args:
        input_data: 录入层输出数据

    Returns:
        MGCRequest: MGC请求模型

    Raises:
        ValueError: 当缺少必要字段时抛出异常
    """
    # 生成请求ID
    timestamp = int(time.time())
    request_id = f"req-{timestamp}"

    # 获取操作类型，默认为ADD
    operation_type = input_data.operation or OperationType.ADD

    # 构建params字段
    params = {}
    if input_data.info_owner:
        params["info_owner"] = input_data.info_owner
    if input_data.info_type:
        params["info_type"] = input_data.info_type

    # 创建MGCRequest对象
    return MGCRequest(
        request_id=request_id,
        agent_uuid=input_data.agent_uuid or "",
        operation_type=operation_type,
        params=params,
        info_owner=input_data.info_owner,
        info_type=input_data.info_type,
        content=input_data.content if isinstance(input_data.content, str) else str(input_data.content)
    )
