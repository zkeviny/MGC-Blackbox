"""文本输出模块

用途：
- v1.0：实现文本输出功能和操作结果提示
- 接收调用层输出的明文核心信息，仅输出操作结果
- 返回Agent友好的文本提示，支持三种查重场景的提示信息

依赖：
- 依赖domain/call_layer/cipher_caller.py

未来演进：
- v2.0+可扩展支持更多输出格式
- 可添加输出验证和错误处理
"""

from typing import Dict


class TextOutput:
    """文本输出处理器
    
    v1.0核心功能：
    - 接收调用层输出的明文核心信息，仅输出操作结果
    - 允许输出的字段范围：info_type、info_owner（仅标签信息）
    - 不输出完整明文内容（content字段及其子串）
    - 禁止输出密文片段（extract_account、extract_password等）
    - 返回Agent友好的文本提示，支持三种查重场景的提示信息
    """
    
    def __init__(self):
        """初始化文本输出处理器"""
        pass
    
    def render_output(self, caller_result: Dict) -> Dict:
        """渲染输出结果
        
        接收调用层输出的明文核心信息，仅输出操作结果
        
        Args:
            caller_result: 调用层输出结构
                - success: bool - 是否成功
                - plaintext_info: dict - 明文核心信息（info_type, info_owner, content）
                - message: str - 操作结果提示
                - scenario: int - 查重场景（1/2/3）
        
        Returns:
            dict: 输出层输出结构
                - success: bool - 是否成功
                - message: str - Agent友好的文本提示
                - scenario: int - 查重场景（1/2/3）
                - info_type: str - 信息类型（仅标签信息）
                - info_owner: str - 信息归属（仅标签信息）
        
        Raises:
            ValueError: 当输入参数无效时抛出异常
        """
        try:
            if not caller_result:
                raise ValueError("Caller result cannot be None")
            
            return self.render_result_message(caller_result)
        except Exception as e:
            raise ValueError(f"Failed to render output: {str(e)}")
    
    def _filter_sensitive_fields(self, plaintext_info: Dict) -> Dict:
        """过滤敏感字段
        
        仅允许输出info_type、info_owner（仅标签信息）
        不输出完整明文内容（content字段及其子串）
        禁止输出密文片段（extract_account、extract_password等）
        
        Args:
            plaintext_info: 明文核心信息
        
        Returns:
            dict: 过滤后的明文信息（仅包含info_type、info_owner）
        """
        filtered = {}
        
        # 仅允许输出info_type、info_owner
        if "info_type" in plaintext_info:
            filtered["info_type"] = plaintext_info["info_type"]
        
        if "info_owner" in plaintext_info:
            filtered["info_owner"] = plaintext_info["info_owner"]
        
        return filtered
    
    def render_result_message(self, caller_result: Dict) -> Dict:
        """渲染操作结果提示
        
        返回Agent友好的文本提示，支持三种查重场景的提示信息
        
        Args:
            caller_result: 调用层输出结构
                - success: bool - 是否成功
                - scenario: int - 查重场景（1/2/3）
                - plaintext_info: dict - 明文核心信息
        
        Returns:
            dict: 操作结果提示
                - success: bool - 是否成功
                - message: str - Agent友好的文本提示
                - scenario: int - 查重场景（1/2/3）
                - info_type: str - 信息类型（仅标签信息）
                - info_owner: str - 信息归属（仅标签信息）
        
        Raises:
            ValueError: 当输入参数无效时抛出异常
        """
        try:
            if not caller_result:
                raise ValueError("Caller result cannot be None")
            
            scenario = caller_result.get("scenario", 0)
            plaintext_info = caller_result.get("plaintext_info", {})
            
            # 过滤敏感字段
            filtered_info = self._filter_sensitive_fields(plaintext_info)
            
            # 根据查重场景渲染提示信息
            if scenario == 1:
                return self._render_scenario_1(filtered_info)
            elif scenario == 2:
                return self._render_scenario_2(filtered_info)
            elif scenario == 3:
                return self._render_scenario_3(filtered_info)
            else:
                raise ValueError(f"Invalid scenario: {scenario}")
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to render result message: {str(e)}")
    
    def _render_scenario_1(self, filtered_info: Dict) -> Dict:
        """渲染场景1提示（无重复）
        
        返回"操作成功：允许新增"
        
        Args:
            filtered_info: 过滤后的明文信息（仅包含info_type、info_owner）
        
        Returns:
            dict: 操作结果提示
        """
        return {
            "success": True,
            "message": "操作成功：允许新增",
            "scenario": 1,
            "info_type": filtered_info.get("info_type", ""),
            "info_owner": filtered_info.get("info_owner", "")
        }
    
    def _render_scenario_2(self, filtered_info: Dict) -> Dict:
        """渲染场景2提示（有字段组合但无完全一致内容）
        
        返回"操作成功：允许新增"
        
        Args:
            filtered_info: 过滤后的明文信息（仅包含info_type、info_owner）
        
        Returns:
            dict: 操作结果提示
        """
        return {
            "success": True,
            "message": "操作成功：允许新增",
            "scenario": 2,
            "info_type": filtered_info.get("info_type", ""),
            "info_owner": filtered_info.get("info_owner", "")
        }
    
    def _render_scenario_3(self, filtered_info: Dict) -> Dict:
        """渲染场景3提示（存在完全一致的字段内容组合）
        
        返回"操作失败：存在重复，请选择操作（更新/新增/放弃）"
        
        Args:
            filtered_info: 过滤后的明文信息（仅包含info_type、info_owner）
        
        Returns:
            dict: 操作结果提示
        """
        return {
            "success": False,
            "message": "操作失败：存在重复，请选择操作（更新/新增/放弃）",
            "scenario": 3,
            "info_type": filtered_info.get("info_type", ""),
            "info_owner": filtered_info.get("info_owner", "")
        }
