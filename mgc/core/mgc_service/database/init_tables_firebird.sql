-- MGC Firebird数据库表创建脚本
-- 创建日期：2026-03-30
-- 版本：1.0
-- 说明：创建MGC核心服务所需的Firebird数据库表

-- 创建自增ID生成器
CREATE SEQUENCE GEN_MGC_ID;
CREATE SEQUENCE GEN_MGC_ENV_ID;

-- 创建mgc_system_env表（系统环境因子）
CREATE TABLE mgc_system_env (
    id INTEGER PRIMARY KEY,
    env_factor_cipher BLOB SUB_TYPE TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建mgc_root_secure表（根密钥安全存储）
CREATE TABLE mgc_root_secure (
    id INTEGER PRIMARY KEY,
    root_key_cipher BLOB SUB_TYPE TEXT NOT NULL,
    migrate_key_hash VARCHAR(255) NOT NULL,
    hardware_fp VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建mgc_sensitive_info表（敏感信息托管）
CREATE TABLE mgc_sensitive_info (
  id INTEGER PRIMARY KEY,
  key_alias VARCHAR(255) NOT NULL,
  sensitive_type VARCHAR(50) NOT NULL,
  provider_alias VARCHAR(255),
  provider_name VARCHAR(255),
  provider_base_url BLOB SUB_TYPE TEXT,
  sensitive_cipher BLOB SUB_TYPE TEXT NOT NULL,
  status VARCHAR(20) DEFAULT 'enabled',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uk_key_alias UNIQUE (key_alias)
);

CREATE INDEX idx_sensitive_type ON mgc_sensitive_info(sensitive_type);
CREATE INDEX idx_provider_alias ON mgc_sensitive_info(provider_alias);

-- 创建mgc_ai_providers表（AI服务商管理）
CREATE TABLE mgc_ai_providers (
  id INTEGER PRIMARY KEY,
  provider_alias VARCHAR(255) NOT NULL,
  provider_name VARCHAR(255) NOT NULL,
  provider_base_url BLOB SUB_TYPE TEXT NOT NULL,
  api_key_cipher BLOB SUB_TYPE TEXT NOT NULL,
  status VARCHAR(20) DEFAULT 'enabled',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_verified_at TIMESTAMP,
  CONSTRAINT uk_provider_alias UNIQUE (provider_alias)
);

CREATE INDEX idx_provider_name ON mgc_ai_providers(provider_name);
CREATE INDEX idx_status ON mgc_ai_providers(status);

-- 创建mgc_operation_logs表（操作日志）
CREATE TABLE mgc_operation_logs (
  id INTEGER PRIMARY KEY,
  operation_type VARCHAR(50) NOT NULL,
  operation_result VARCHAR(20) NOT NULL,
  request_id VARCHAR(255),
  provider_alias VARCHAR(10),
  key_alias VARCHAR(10),
  error_message BLOB SUB_TYPE TEXT,
  duration_ms INTEGER,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_op_type ON mgc_operation_logs(operation_type);
CREATE INDEX idx_op_result ON mgc_operation_logs(operation_result);
CREATE INDEX idx_op_created ON mgc_operation_logs(created_at);