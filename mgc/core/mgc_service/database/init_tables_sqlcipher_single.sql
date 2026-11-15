-- SQLCipher mgc_info_1 单表初始化脚本
-- 版本：1.0
-- 描述：SQLCipher 模式下使用单表存储所有核心数据
-- 字段说明：
--   id: 自增主键
--   extract_account: 虚拟账户（派生凭证）
--   extract_password: 虚拟密码（派生凭证）
--   info_plaintext: 信息明文（初始环境密文/个性化权重/根密钥等）
--   diff_1, diff_2, diff_3: 差异字段（用于不同场景）
--   ext01~ext30: 预留扩展字段

CREATE TABLE IF NOT EXISTS mgc_info_1 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    extract_account TEXT NOT NULL,
    extract_password TEXT NOT NULL,
    info_plaintext TEXT,
    info_type TEXT NOT NULL,
    info_owner TEXT NOT NULL,
    diff_1 TEXT,
    diff_2 TEXT,
    diff_3 TEXT,
    created_at TEXT,
    updated_at TEXT,
    ext01 TEXT,
    ext02 TEXT,
    ext03 TEXT,
    ext04 TEXT,
    ext05 TEXT,
    ext06 TEXT,
    ext07 TEXT,
    ext08 TEXT,
    ext09 TEXT,
    ext10 TEXT,
    ext11 TEXT,
    ext12 TEXT,
    ext13 TEXT,
    ext14 TEXT,
    ext15 TEXT,
    ext16 TEXT,
    ext17 TEXT,
    ext18 TEXT,
    ext19 TEXT,
    ext20 TEXT,
    ext21 TEXT,
    ext22 TEXT,
    ext23 TEXT,
    ext24 TEXT,
    ext25 TEXT,
    ext26 TEXT,
    ext27 TEXT,
    ext28 TEXT,
    ext29 TEXT,
    ext30 TEXT
);

-- 初始化场景：写入根密钥和环境密文
-- INSERT INTO mgc_info_1 (extract_account, extract_password, info_plaintext, diff_1)
-- VALUES (?, ?, ?, ?);

-- 迁移场景：通过 extract_account + extract_password 匹配获取记录
-- SELECT * FROM mgc_info_1 WHERE extract_account = ? AND extract_password = ?;
