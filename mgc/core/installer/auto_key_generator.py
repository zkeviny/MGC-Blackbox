"""
1.5.3 新增：自动生成 personal_key 与 weight 参数

用途：
- 提供"随机生成信任根"能力，作为初次安装的选项 1（CLI / WebUI Random 按钮共用）。
- 生成 8 位 ascii_letters + digits 组合作为 personal_key，1 位 1-9 整数作为 weight_param。
- 将明文凭证写入 ~/.mgc/secrets/personal_key.txt（含风险提示），并调 db_key_manager.save 落 DB_KEY.json（加密形式）。
- **不**初始化数据库（数据库初始化由调用方在后续调 StorageService.initialize_database）。

流程：
    1. 生成 personal_key (8 chars)
    2. 生成 weight_param (1 char, 1-9)
    3. 落 SECRETS_DIR/personal_key.txt（明文 + WARNING；存在则备份为 personal_key_backup_<ts>.txt）
    4. 调 db_key_manager.save(personal_key, weight_param) 落加密 DB_KEY.json
    5. 返回 dict { personal_key, weight_param, saved_path }

约束：
- 调用方负责后续的 StorageService.initialize_database（fresh install 场景必须先于本模块返回后立即调用）。
- 不创建 dialog、不启 WebUI、不输出到 stdout（终端打印由 main.py / app.py 负责）。
"""

import secrets
import string
import shutil
import time
from datetime import datetime


class AutoKeyGenerator:
    """1.5.3 随机信任根生成器"""

    PERSONAL_KEY_LENGTH = 8
    WEIGHT_MIN = 1
    WEIGHT_MAX = 9

    @classmethod
    def run(cls) -> dict:
        """
        生成 personal_key / weight_param，落明文 txt，保存 DB_KEY.json。

        出参 dict：
            - personal_key: str（8 位 ascii_letters + digits）
            - weight_param: str（1 位 1-9，字符串形式）
            - saved_path: str（personal_key.txt 的绝对路径）
        """
        personal_key = cls._generate_personal_key()
        weight_param = cls._generate_weight()
        saved_path = cls._save_plaintext(personal_key, weight_param)

        # 写加密 DB_KEY.json（与现有 db_key_manager.save 接口一致）
        from mgc.key_storage import db_key_manager
        db_key_manager.save(personal_key, weight_param)

        return {
            "personal_key": personal_key,
            "weight_param": weight_param,
            "saved_path": saved_path,
        }

    @classmethod
    def _generate_personal_key(cls, length: int = None) -> str:
        """生成 length 位 random 由 [ascii_letters + digits] 组成"""
        if length is None:
            length = cls.PERSONAL_KEY_LENGTH
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    @classmethod
    def _generate_weight(cls) -> str:
        """生成 1 位 1-9 的 weight_param（字符串）"""
        value = secrets.randbelow(cls.WEIGHT_MAX - cls.WEIGHT_MIN + 1) + cls.WEIGHT_MIN
        return str(value)

    @classmethod
    def _save_plaintext(cls, personal_key: str, weight_param: str) -> str:
        """将 personal_key / weight_param 写入 SECRETS_DIR/personal_key.txt"""
        from mgc.config.path_config import PERSONAL_KEY_FILE, SECRETS_DIR

        SECRETS_DIR.mkdir(parents=True, exist_ok=True)
        target = PERSONAL_KEY_FILE

        # 已存在则备份
        if target.exists():
            backup_name = f"personal_key_backup_{int(time.time())}.txt"
            backup_path = SECRETS_DIR / backup_name
            shutil.copy2(target, backup_path)

        timestamp = datetime.now().isoformat()  # 本地时间（非 UTC）
        content = (
            "MGC Personal Key\n"
            f"Personal Key: {personal_key}\n"
            f"Weight Param: {weight_param}\n"
            f"Created At: {timestamp}\n"
            "\n"
            "[WARNING] This file contains plaintext credentials. Keep it safe.\n"
            "[WARNING] Loss of these values will make your encrypted data unrecoverable.\n"
        )
        target.write_text(content, encoding="utf-8")
        return str(target)