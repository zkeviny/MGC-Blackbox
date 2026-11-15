-- MGC数据库表创建脚本（SQLCipher/SQLite版本）
-- 创建日期：2026-03-27
-- 版本：1.0
-- 说明：创建MGC核心服务所需的数据库表（SQLite语法）

-- 创建mgc_sensitive_info表（敏感信息托管）
CREATE TABLE IF NOT EXISTS mgc_sensitive_info (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key_alias TEXT NOT NULL,
  sensitive_type TEXT NOT NULL,
  provider_alias TEXT,
  provider_name TEXT,
  provider_base_url TEXT,
  sensitive_cipher TEXT NOT NULL,
  status TEXT DEFAULT 'enabled',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_sensitive_key_alias ON mgc_sensitive_info(key_alias);
CREATE INDEX IF NOT EXISTS idx_sensitive_type ON mgc_sensitive_info(sensitive_type);
CREATE INDEX IF NOT EXISTS idx_provider_alias ON mgc_sensitive_info(provider_alias);

-- 创建mgc_ai_providers表（AI服务商管理）
CREATE TABLE IF NOT EXISTS mgc_ai_providers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  provider_alias TEXT NOT NULL,
  provider_name TEXT NOT NULL,
  provider_base_url TEXT NOT NULL,
  api_key_cipher TEXT NOT NULL,
  status TEXT DEFAULT 'enabled',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_verified_at TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_provider_alias ON mgc_ai_providers(provider_alias);
CREATE INDEX IF NOT EXISTS idx_provider_name ON mgc_ai_providers(provider_name);
CREATE INDEX IF NOT EXISTS idx_status ON mgc_ai_providers(status);

-- 创建mgc_operation_logs表（操作日志）
CREATE TABLE IF NOT EXISTS mgc_operation_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  operation_type TEXT NOT NULL,
  operation_result TEXT NOT NULL,
  request_id TEXT,
  provider_alias TEXT,
  key_alias TEXT,
  error_message TEXT,
  duration_ms INTEGER,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_operation_type ON mgc_operation_logs(operation_type);
CREATE INDEX IF NOT EXISTS idx_operation_result ON mgc_operation_logs(operation_result);
CREATE INDEX IF NOT EXISTS idx_created_at ON mgc_operation_logs(created_at);

-- 创建mgc_system_env表（环境因子）
CREATE TABLE IF NOT EXISTS mgc_system_env (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  env_factor_cipher TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建mgc_root_secure表（根密钥存储）
CREATE TABLE IF NOT EXISTS mgc_root_secure (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  root_key_cipher TEXT NOT NULL,
  migrate_key_hash TEXT NOT NULL,
  hardware_fp TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
