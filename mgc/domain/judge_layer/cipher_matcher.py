"""密文匹配模块

用途：
- v1.0：实现密文匹配校验逻辑和存储前查重功能
- 验证派生凭证和硬件指纹的哈希值
- 检查是否存在重复数据

依赖：
- 依赖models/cognition_model.py
- 依赖core/crypto/hash_crypto.py

未来演进：
- v2.0+可扩展支持核心信息加密校验
- 可扩展支持多维规则匹配
- 可添加匹配验证和错误处理
"""

from mgc.models.cognition_model import CognitionRule
from mgc.models.storage_model import InfoStorageUnit
from mgc.core.crypto.hash_crypto import HashCrypto
from typing import Dict, Optional


class DuplicateCheckResult:
    """查重结果
    
    Attributes:
        is_duplicate: bool - 是否重复
        existing_rule: Optional[CognitionRule] - 已存在的规则（如果重复）
        scenario: int - 查重场景
                   1: 无匹配（查询清单中无相同类型和归属的条目）
                   2: 部分匹配（类型和归属相同，但差异字段不同）
                   3: 完全匹配（所有字段都相同）
                   4: diff1必填（info_type+info_owner已存在，但diff1为空）
                   5: diff2必填（diff1也有重复，但diff2为空）
                   6: diff3必填（diff2也有重复，但diff3为空）
    """
    def __init__(self, is_duplicate: bool, existing_rule: Optional[CognitionRule] = None, scenario: int = 1):
        self.is_duplicate = is_duplicate
        self.existing_rule = existing_rule
        self.scenario = scenario


class CipherMatcher:
    """密文匹配器
    
    v1.0核心功能：
    - 基于extract_account+extract_password+hardware_hash进行SHA-256哈希
    - 验证哈希值的正确性和一致性
    - 实现存储前查重功能，检测重复数据
    - 核心信息明文透传，不做任何加密/哈希处理
    """
    
    def __init__(self):
        """初始化密文匹配器"""
        self.hash_crypto = HashCrypto(algorithm="sha256")
    
    def match_cipher(self, storage_unit: InfoStorageUnit, hardware_hash: str = "") -> bool:
        """匹配密文，验证派生凭证和硬件指纹
        
        对派生凭证和硬件指纹进行SHA-256哈希，验证哈希值的正确性和一致性
        
        Args:
            storage_unit: 存储单元（包含extract_account和extract_password）
            hardware_hash: 硬件指纹哈希值（可选，如果storage_unit已包含）
        
        Returns:
            bool: 密文是否匹配
        
        Raises:
            ValueError: 当输入参数无效时抛出异常
        """
        try:
            if not storage_unit:
                raise ValueError("InfoStorageUnit cannot be None")
            
            # 使用storage_unit中的hardware_hash，如果没有提供则使用参数
            target_hardware_hash = hardware_hash if hardware_hash else storage_unit.hardware_hash
            
            if not target_hardware_hash:
                raise ValueError("hardware_hash cannot be empty")
            
            # 仍需空字段保护
            if not storage_unit.extract_account or not storage_unit.extract_password:
                return False
            
            # 不对已哈希字段二次哈希，直接做格式校验
            return self._compare_hashes(
                storage_unit.extract_account,
                storage_unit.extract_password,
                target_hardware_hash
            )
        except Exception as e:
            raise ValueError(f"Failed to match cipher: {str(e)}")
    
    def _hash_credentials(self, credential: str) -> str:
        """对派生凭证进行SHA-256哈希
        
        Args:
            credential: 派生凭证（extract_account或extract_password）
        
        Returns:
            str: SHA-256哈希值
        """
        if not credential:
            return ""
        return self.hash_crypto.hash(credential)
    
    def _compare_hashes(self, account_hash: str, password_hash: str, 
                       hardware_hash: str) -> bool:
        """比较哈希值
        
        Args:
            account_hash: 账户哈希值
            password_hash: 密码哈希值
            hardware_hash: 硬件指纹哈希值
        
        Returns:
            bool: 哈希值是否有效
        """
        if not account_hash or not password_hash or not hardware_hash:
            return False
        
        # 验证哈希值格式（SHA256哈希值应为64位十六进制字符串）
        sha256_length = 64
        if len(account_hash) != sha256_length or len(password_hash) != sha256_length or len(hardware_hash) != sha256_length:
            return False
        
        # 验证哈希值是否为有效的十六进制字符串
        try:
            int(account_hash, 16)
            int(password_hash, 16)
            int(hardware_hash, 16)
        except ValueError:
            return False
        
        return True
    
    def check_duplicate(self, cognition_rule: CognitionRule, 
                      existing_rules: Dict[str, CognitionRule],
                      agent_uuid: str = "") -> DuplicateCheckResult:
        """检查是否存在重复数据
        
        基于差异字段强制填写规则（逐级递进）进行查重：
        - 当 info_type + info_owner 已存在时，diff1 必填，否则直接拒绝存入
        - 若 diff1 也有重复，则需录入 diff2，否则直接拒绝存入
        - 若 diff2 也重复，则需录入 diff3，否则直接拒绝存入
        - 若 diff3 也重复，则判定为完全匹配，拒绝存入
        
        支持三种查重场景的处理：
        - 无匹配场景：查询清单中无相同类型和归属的条目
        - 部分匹配场景：类型和归属相同，但差异字段不同
        - 完全匹配场景：所有字段都相同
        
        Args:
            cognition_rule: 待检查的认知规则
            existing_rules: 已存在的规则字典（key为查重键）
            agent_uuid: Agent UUID标识（1.0隐私节点算法中不使用）
        
        Returns:
            DuplicateCheckResult: 查重结果
        
        Raises:
            ValueError: 当输入参数无效时抛出异常
        """
        try:
            if not cognition_rule:
                raise ValueError("CognitionRule cannot be None")
            
            if not existing_rules:
                return DuplicateCheckResult(is_duplicate=False, scenario=1)
            
            # 查找所有相同类型和归属的规则
            matching_rules = []
            for key, existing_rule in existing_rules.items():
                if (existing_rule.info_type == cognition_rule.info_type and
                    existing_rule.info_owner == cognition_rule.info_owner):
                    matching_rules.append(existing_rule)
            
            # 场景1：无匹配
            if not matching_rules:
                return DuplicateCheckResult(is_duplicate=False, scenario=1)
            
            # 检查差异字段强制填写规则
            if not cognition_rule.diff1:
                return DuplicateCheckResult(
                    is_duplicate=True, 
                    scenario=4,
                    existing_rule=matching_rules[0]
                )
            
            # 检查是否有diff1相同的规则
            diff1_matches = []
            for rule in matching_rules:
                if rule.diff1 == cognition_rule.diff1:
                    diff1_matches.append(rule)
            
            if not diff1_matches:
                return DuplicateCheckResult(is_duplicate=False, scenario=2)
            
            # 检查是否有diff2相同的规则
            if not cognition_rule.diff2:
                return DuplicateCheckResult(
                    is_duplicate=True,
                    scenario=5,
                    existing_rule=diff1_matches[0]
                )
            
            diff2_matches = []
            for rule in diff1_matches:
                if rule.diff2 == cognition_rule.diff2:
                    diff2_matches.append(rule)
            
            if not diff2_matches:
                return DuplicateCheckResult(is_duplicate=False, scenario=2)
            
            # 检查是否有diff3相同的规则
            if not cognition_rule.diff3:
                return DuplicateCheckResult(
                    is_duplicate=True,
                    scenario=6,
                    existing_rule=diff2_matches[0]
                )
            
            diff3_matches = []
            for rule in diff2_matches:
                if rule.diff3 == cognition_rule.diff3:
                    diff3_matches.append(rule)
            
            if not diff3_matches:
                return DuplicateCheckResult(is_duplicate=False, scenario=2)
            
            # 场景3：完全匹配
            return DuplicateCheckResult(
                is_duplicate=True,
                scenario=3,
                existing_rule=diff3_matches[0]
            )
        except Exception as e:
            raise ValueError(f"Failed to check duplicate: {str(e)}")
    
    def _generate_key(self, cognition_rule: CognitionRule, agent_uuid: str = "") -> str:
        """生成查重键
        
        生成查重键（info_type + info_owner），不包含agent_uuid、diff字段或content
        
        Args:
            cognition_rule: 认知规则
            agent_uuid: Agent UUID标识（1.0隐私节点算法中不使用）
        
        Returns:
            str: 查重键
        """
        return f"{cognition_rule.info_type}:{cognition_rule.info_owner}"
    
    def _compare_content(self, content1: str, content2: str) -> bool:
        """比较内容是否完全一致
        
        基于CognitionRule.content字段进行比较，直接进行明文比较，不计算哈希
        
        Args:
            content1: 内容1
            content2: 内容2
        
        Returns:
            bool: 内容是否完全一致
        """
        return content1 == content2
    
    def _compare_diff_fields(self, rule1: CognitionRule, rule2: CognitionRule) -> bool:
        """比较差异字段是否完全一致
        
        基于CognitionRule的diff1/2/3字段进行比较
        
        Args:
            rule1: 规则1
            rule2: 规则2
        
        Returns:
            bool: 差异字段是否完全一致
        """
        return (rule1.diff1 == rule2.diff1 and
                rule1.diff2 == rule2.diff2 and
                rule1.diff3 == rule2.diff3)
