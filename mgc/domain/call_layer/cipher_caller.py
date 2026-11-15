"""加密单元调用模块

用途：
- v1.0：实现加密单元调用逻辑和匹配结果处理
- 根据判断层的匹配结果调用匹配成功的加密单元
- 仅提取明文信息返回，不泄露密文片段
- 实现跨Agent/跨设备校验，禁止跨Agent/跨设备调用

依赖：
- 依赖models/cognition_model.py
- 依赖domain/judge_layer/cipher_matcher.py

未来演进：
- v2.0+可扩展支持跨Agent/跨设备调用
- 可扩展支持更多调用操作
- 可添加调用验证和错误处理
"""

from mgc.models.cognition_model import CognitionRule
from mgc.domain.judge_layer.cipher_matcher import DuplicateCheckResult
from typing import Dict, Optional


class CipherCaller:
    """加密单元调用器
    
    v1.0核心功能：
    - 根据判断层的匹配结果调用匹配成功的加密单元
    - 仅提取明文核心信息返回（info_type, info_owner, content等）
    - 实现跨Agent/跨设备校验，禁止跨Agent/跨设备调用
    - 根据匹配结果返回相应信息
    """
    
    def __init__(self):
        """初始化加密单元调用器
        
        初始化上下文字段为None，调用前需先调用set_agent_context设置
        """
        self.current_agent_uuid = None
        self.current_device_id = None
    
    def set_agent_context(self, agent_uuid: str, device_id: str):
        """设置Agent上下文
        
        Args:
            agent_uuid: Agent UUID标识
            device_id: 设备ID标识
        """
        self.current_agent_uuid = agent_uuid
        self.current_device_id = device_id
    
    def call_cipher_unit(self, cognition_rule: CognitionRule, agent_uuid: str, device_id: str, 
                        cipher_matcher=None, hardware_hash: str = "", 
                        cognition_encryptor=None) -> Dict:
        """调用匹配成功的加密单元
        
        Args:
            cognition_rule: 认知规则
            agent_uuid: Agent UUID标识
            device_id: 设备ID标识
            cipher_matcher: 密文匹配器（依赖注入）
            hardware_hash: 硬件指纹哈希值
            cognition_encryptor: 认知信息加密器（依赖注入）
        
        Returns:
            dict: 调用结果
                - success: bool - 是否成功
                - scenario: int - 场景标识（1=成功，2=匹配失败）
                - plaintext_info: dict - 明文核心信息（匹配成功时）
                - message: str - 操作结果提示
        
        Raises:
            ValueError: 当输入参数无效或校验失败时抛出异常
        """
        try:
            if not cognition_rule:
                raise ValueError("CognitionRule cannot be None")
            
            # 跨Agent/跨设备校验
            self._validate_agent_context(agent_uuid, device_id)
            
            # 密文匹配校验（如果提供了cipher_matcher和cognition_encryptor）
            if cipher_matcher and cognition_encryptor:
                # 先调用加密层生成InfoStorageUnit
                storage_unit = cognition_encryptor.encrypt(cognition_rule, agent_uuid)
                
                # 然后将InfoStorageUnit传递给判断层进行密文匹配
                if not cipher_matcher.match_cipher(storage_unit, hardware_hash):
                    return {
                        "success": False,
                        "scenario": "match_failed",
                        "message": "密文匹配失败"
                    }
            
            # 提取明文核心信息
            plaintext_info = self._extract_plaintext_info(cognition_rule)
            
            return {
                "success": True,
                "scenario": "success",
                "plaintext_info": plaintext_info,
                "message": "加密单元调用成功"
            }
        except Exception as e:
            raise ValueError(f"Failed to call cipher unit: {str(e)}")
    
    def _extract_plaintext_info(self, cognition_rule: CognitionRule) -> Dict:
        """提取明文核心信息
        
        仅提取明文核心信息返回（info_type, info_owner, content等）
        不泄露密文片段（extract_account, extract_password等）
        
        Args:
            cognition_rule: 认知规则
        
        Returns:
            dict: 明文核心信息
        """
        return {
            "info_type": cognition_rule.info_type,
            "info_owner": cognition_rule.info_owner,
            "content": cognition_rule.content
        }
    
    def _validate_agent_context(self, agent_uuid: str, device_id: str, strict: bool = True) -> bool:
        """实现跨Agent/跨设备校验
        
        依赖的上下文来源：
        - agent_uuid：从InputData.agent_uuid获取，用于标识Agent身份
        - device_id：从硬件指纹获取，用于标识设备身份
        
        校验逻辑：
        - strict=True：检查agent_uuid和device_id是否匹配，禁止跨Agent/跨设备调用
        - strict=False：仅验证参数有效性，不进行跨Agent/跨设备检查
        
        Args:
            agent_uuid: Agent UUID标识
            device_id: 设备ID标识
            strict: 是否严格模式（默认True，检查跨Agent/跨设备）
        
        Returns:
            bool: 是否通过校验
        
        Raises:
            ValueError: 当校验失败时抛出异常
        """
        try:
            if not agent_uuid or not device_id:
                raise ValueError("Agent context cannot be empty")
            
            if strict:
                if not self.current_agent_uuid or not self.current_device_id:
                    raise ValueError("Agent context not set")
                
                if agent_uuid != self.current_agent_uuid:
                    raise ValueError("Cross-agent call is not allowed")
                
                if device_id != self.current_device_id:
                    raise ValueError("Cross-device call is not allowed")
            
            return True
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to validate agent context: {str(e)}")
    
    def process_duplicate_result(self, duplicate_result: DuplicateCheckResult) -> Dict:
        """处理DuplicateCheckResult
        
        根据匹配结果返回相应信息，支持三种查重场景的处理结果
        
        Args:
            duplicate_result: 查重结果
        
        Returns:
            dict: 处理结果
                - success: bool - 是否成功
                - scenario: int - 场景标识（1=无可用字段组合，2=有字段组合但无完全一致内容，3=存在完全一致）
                - plaintext_info: dict - 明文核心信息（场景1和2时为None）
                - message: str - 操作结果提示
        
        Raises:
            ValueError: 当输入参数无效时抛出异常
        """
        try:
            if not duplicate_result:
                raise ValueError("DuplicateCheckResult cannot be None")
            
            if duplicate_result.scenario == 1:
                return self._handle_scenario_1()
            elif duplicate_result.scenario == 2:
                return self._handle_scenario_2()
            elif duplicate_result.scenario == 3:
                return self._handle_scenario_3(duplicate_result)
            else:
                raise ValueError(f"Invalid scenario: {duplicate_result.scenario}")
        except Exception as e:
            raise ValueError(f"Failed to process duplicate result: {str(e)}")
    
    def _handle_scenario_1(self) -> Dict:
        """处理场景1：无可用字段组合
        
        返回无重复，允许新增
        
        Returns:
            dict: 处理结果
        """
        return {
            "success": True,
            "scenario": 1,
            "plaintext_info": None,
            "message": "无可用字段组合，允许新增"
        }
    
    def _handle_scenario_2(self) -> Dict:
        """处理场景2：有字段组合但无完全一致内容
        
        返回无重复，允许新增
        
        Returns:
            dict: 处理结果
        """
        return {
            "success": True,
            "scenario": 2,
            "plaintext_info": None,
            "message": "有字段组合但无完全一致内容，允许新增"
        }
    
    def _handle_scenario_3(self, duplicate_result: DuplicateCheckResult) -> Dict:
        """处理场景3：存在完全一致的字段内容组合
        
        返回重复，提示用户选择（更新/新增/放弃）
        
        Args:
            duplicate_result: 查重结果
        
        Returns:
            dict: 处理结果
        """
        return {
            "success": False,
            "scenario": 3,
            "plaintext_info": None,
            "message": "存在完全一致的字段内容组合，请选择操作（更新/新增/放弃）",
            "existing_rule": duplicate_result.existing_rule
        }
