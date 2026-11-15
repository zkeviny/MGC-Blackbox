-- MGC数据库表创建脚本
-- 创建日期：2026-03-27
-- 版本：1.0
-- 说明：创建MGC核心服务所需的数据库表

-- 创建mgc_sensitive_info表（敏感信息托管）
CREATE TABLE IF NOT EXISTS `mgc_sensitive_info` (
  id INT PRIMARY KEY AUTO_INCREMENT,
  key_alias VARCHAR(255) NOT NULL COMMENT '密钥别名（唯一标识）',
  sensitive_type VARCHAR(50) NOT NULL COMMENT '敏感信息类型：api_key/code',
  provider_alias VARCHAR(255) COMMENT '服务商别名（API Key类型）',
  provider_name VARCHAR(255) COMMENT '服务商名称',
  provider_base_url MEDIUMTEXT COMMENT '服务商接口地址',
  sensitive_cipher MEDIUMTEXT NOT NULL COMMENT '敏感信息密文',
  status VARCHAR(20) DEFAULT 'enabled' COMMENT '状态：enabled/disabled',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_key_alias (key_alias),
  KEY idx_sensitive_type (sensitive_type),
  KEY idx_provider_alias (provider_alias)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='MGC 敏感信息托管表';

-- 创建mgc_ai_providers表（AI服务商管理）
CREATE TABLE IF NOT EXISTS `mgc_ai_providers` (
  id INT PRIMARY KEY AUTO_INCREMENT,
  provider_alias VARCHAR(255) NOT NULL COMMENT '服务商别名（唯一标识）',
  provider_name VARCHAR(255) NOT NULL COMMENT '服务商名称',
  provider_base_url MEDIUMTEXT NOT NULL COMMENT '服务商接口地址',
  api_key_cipher MEDIUMTEXT NOT NULL COMMENT 'API Key密文',
  status VARCHAR(20) DEFAULT 'enabled' COMMENT '状态：enabled/disabled',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  last_verified_at DATETIME COMMENT '最后验证时间',
  UNIQUE KEY uk_provider_alias (provider_alias),
  KEY idx_provider_name (provider_name),
  KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='MGC AI服务商管理表';

-- 创建mgc_operation_logs表（操作日志）
CREATE TABLE IF NOT EXISTS `mgc_operation_logs` (
  id INT PRIMARY KEY AUTO_INCREMENT,
  operation_type VARCHAR(50) NOT NULL COMMENT '操作类型：init/encrypt/decrypt/migrate/save_sensitive/delete_sensitive/add_provider/delete_provider',
  operation_result VARCHAR(20) NOT NULL COMMENT '操作结果：success/failure',
  request_id VARCHAR(255) COMMENT '请求ID',
  provider_alias VARCHAR(10) COMMENT '服务商别名（脱敏：仅存前后2位，如op****ai）',
  key_alias VARCHAR(10) COMMENT '密钥别名（脱敏：仅存前后2位，如db****rd）',
  error_message TEXT COMMENT '错误信息',
  duration_ms INT COMMENT '耗时（毫秒）',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_operation_type (operation_type),
  KEY idx_operation_result (operation_result),
  KEY idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='MGC 操作日志表';
