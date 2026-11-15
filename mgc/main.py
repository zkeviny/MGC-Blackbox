"""项目入口文件

用途：
- 启动MGC核心服务（FastAPI）
- 挂载/api/mgc与/v1路由
- 支持Agent Skills调用
"""

import sys
import os
import asyncio
from pathlib import Path
from typing import Optional

# 标准流统一 UTF-8：Windows 控制台默认代码页可能是 cp936，StreamHandler 写中文
# 会触发 UnicodeEncodeError（CREATE_NO_WINDOW 重定向管道场景尤其明显）。
# errors="backslashreplace" 保证异常字符只影响该条日志，不会让日志调用本身抛错。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:
            # 部分嵌入式 Python 运行时不支持 reconfigure，忽略即可
            pass

MGC_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from mgc.utils.version_utils import get_version

VERSION = get_version()

from mgc.core.mgc_service import (
    MGCCoreService,
    APIRouterManager,
    SensitiveService,
    MigrateService,
    StatusService,
    SkillsManager,
    DatabaseHandler,
)
from mgc.service.update_service import UpdateService
from mgc.utils.path_utils import ensure_directories
from mgc.utils.log_utils import logger


def check_tkinter() -> bool:
    """Check if tkinter is available"""
    try:
        import tkinter
        return True
    except ImportError:
        import platform
        if platform.system() == "Darwin":
            print("[WARNING] tkinter not installed")
            print("Please run: brew install python-tk")
        elif platform.system() == "Linux":
            print("[WARNING] tkinter not installed")
            print("Please run: sudo apt-get install python3-tk")
        return False


def check_database_exists() -> bool:
    """Check if database exists"""
    from mgc.config.path_config import DB_FILE
    return DB_FILE.exists()


def check_db_key_exists() -> bool:
    """Check if DB_KEY.json exists"""
    from mgc.key_storage import db_key_manager
    return db_key_manager.exists()


def get_aes_key_2_from_db_key() -> Optional[str]:
    """Get AES_KEY_2 from DB_KEY.json"""
    from mgc.key_storage import db_key_manager
    try:
        return db_key_manager.load()
    except Exception as e:
        logger.warning(f"Failed to get key from DB_KEY.json: {e}")
        return None


def validate_startup_factors(
    root_key: str,
    weight_param: int,
    db_handler
) -> dict:
    """Project initialization

    校验所有核心因子是否存在且有效，缺失则终止启动。

    入参：
        root_key: 根密钥（personal_key_weight_param格式）
        weight_param: 权重参数
        db_handler: 数据库处理器

    出参：
        dict: 校验通过的因子字典

    异常：
        ValueError: 任一因子缺失或无效
    """
    from mgc.domain.crypto_layer.dynamic_salt import extract_dynamic_salts
    from mgc.domain.crypto_layer import get_hardware_info
    from mgc.utils.log_utils import logger

    if not root_key or not weight_param:
        raise ValueError("Startup factor missing: root_key or weight_param")

    salts = extract_dynamic_salts(root_key, weight_param)
    if not salts:
        raise ValueError("Startup factor missing: dynamic_salts calculation failed")

    result = db_handler.execute_query(
        "SELECT COUNT(*) as count FROM mgc_info_1 WHERE diff_1 = 'environment_cipher'"
    )
    if not result or result[0]['count'] == 0:
        raise ValueError("Startup factor missing: environment_cipher not stored")

    hw = get_hardware_info()
    if not hw or not hw[0] or not hw[1]:
        raise ValueError("Startup factor missing: hardware_fingerprint")

    logger.info("Startup factors validated")

    return {
        "root_key": root_key,
        "weight_param": weight_param,
        "salts": salts,
        "hardware_fingerprint": hw,
    }


def initialize() -> bool:
    """初始化项目基础目录"""
    try:
        ensure_directories()
        logger.info("Project initialization successful")
        return True
    except Exception as e:
        logger.error(f"Project initialization failed: {str(e)}")
        return False


def build_services():
    """Build and inject all service instances"""
    from mgc.config.database_config import DatabaseConfig

    config = DatabaseConfig.get_config()
    db_type = config.get("database_type", "sqlcipher")
    logger.info(f"Database type: {db_type}")

    sensitive_service = None
    crypto_service = None

    if db_type == "sqlcipher":
        from mgc.core.database.sqlcipher_handler import SQLCipherHandler
        sqlcipher_config = config.get("sqlcipher", {})
        db_file = sqlcipher_config.get("db_file", "")
        logger.info(f"SQLCipher database file: {db_file}")
        logger.info("SQLCipher initialized (on-demand)")

    db_handler = DatabaseHandler()

    try:
        if db_type == "sqlcipher":
            logger.info("SQLCipher mode, skip connection at startup (set key at initialization)")
        else:
            db_handler.connect()
            logger.info("Database connection successful")
    except Exception as e:
        logger.warning(f"Database connection failed, will retry on first use: {e}")

    crypto_service = None

    if db_type == "sqlcipher":
        from mgc.core.database.sqlcipher_handler import SQLCipherHandler
        from mgc.domain.crypto_layer.hardware_fingerprint import get_hardware_info
        from mgc.config.path_config import DB_FILE

        db_file = DB_FILE
        is_initialized = False

        if db_file.exists():
            try:
                aes_key_2 = None
                db_key_exists = check_db_key_exists()
                logger.info(f"Database exists, DB_KEY.json exists: {db_key_exists}")

                if db_key_exists:
                    aes_key_2 = get_aes_key_2_from_db_key()
                    if aes_key_2:
                        logger.info("Successfully got AES_KEY_2 from DB_KEY.json")
                        SQLCipherHandler.set_aes_key_2(aes_key_2)

                        db_handler.connect()

                        env_check = db_handler.execute_query(
                            "SELECT COUNT(*) as count FROM mgc_info_1 WHERE diff_1 = 'environment_cipher'"
                        )
                        root_check = db_handler.execute_query(
                            "SELECT COUNT(*) as count FROM mgc_info_1 WHERE diff_1 = 'ROOT_KEY'"
                        )

                        if (env_check and env_check[0]['count'] > 0 and
                            root_check and root_check[0]['count'] > 0):
                            is_initialized = True
                            logger.info("Detected initialized state, initialize crypto_service from database")

                            from mgc.core.mgc_service.crypto_service import CryptoService
                            
                            root_key_record = db_handler.execute_query(
                                "SELECT info_plaintext FROM mgc_info_1 WHERE diff_1 = 'ROOT_KEY'"
                            )
                            if root_key_record and root_key_record[0]['info_plaintext']:
                                stored = root_key_record[0]['info_plaintext']
                                from mgc.core.installer.root_key_encryptor import RootKeyEncryptor
                                from mgc.domain.crypto_layer.root_key_parser import parse_root_key
                                encryptor = RootKeyEncryptor()
                                root_key_data = encryptor.decrypt_root_key_from_db(
                                    stored, aes_key_2
                                )
                                root_key = root_key_data['root_key']
                                personal_key, weight_param = parse_root_key(root_key)
                                logger.info("Root key decrypted successfully")

                                weight_param_record = db_handler.execute_query(
                                    "SELECT info_plaintext FROM mgc_info_1 WHERE diff_1 = 'weight_param'"
                                )
                                if weight_param_record and weight_param_record[0]['info_plaintext']:
                                    from mgc.domain.crypto_layer.root_key_crypto import decrypt_weight_param
                                    encrypted_wp = weight_param_record[0]['info_plaintext']
                                    try:
                                        expanded_weight_param = decrypt_weight_param(encrypted_wp, aes_key_2)
                                        weight_param = int(expanded_weight_param)
                                        logger.info("Weight param decrypted successfully")
                                    except Exception as e:
                                        logger.warning(f"Weight param decryption failed, using parsed value: {e}")
                            else:
                                raise ValueError("Root key record not found, please re-initialize")
                            
                            crypto_service = CryptoService(personal_key, weight_param)
                            logger.info(f"crypto_service initialized")

                            validate_startup_factors(root_key, weight_param, db_handler)

                            initialization_success = True

                            from mgc.core.mgc_service.sensitive_service import SensitiveService
                            sensitive_service = SensitiveService(crypto_service, db_handler)
                            logger.info(f"sensitive_service initialized")
                    else:
                        logger.warning("DB_KEY.json decryption failed")
                else:
                    logger.warning("DB_KEY.json does not exist, enter interactive initialization")
            except Exception as e:
                logger.warning(f"Initialization check failed: {e}")
                if "execute query" in str(e).lower() or "hmac" in str(e).lower():
                    import os
                    from mgc.key_storage.db_key_manager import _get_db_key_file_path
                    db_key_path = _get_db_key_file_path()
                    if os.path.exists(db_key_path):
                        os.remove(db_key_path)
                        print("DB_KEY deleted due to key error, please re-enter root key")
                        # 1.5.3.1 反馈#4：提示秘钥文件路径
                        from mgc.config.i18n_config import Messages
                        from mgc.config.path_config import PERSONAL_KEY_FILE
                        if PERSONAL_KEY_FILE.exists():
                            print(Messages.InitFlow.DBKEY_ERROR_HINT.format(path=str(PERSONAL_KEY_FILE)))

    if sensitive_service is None:
        if crypto_service is None:
            raise ValueError("CryptoService not initialized, please ensure initialization is complete or root key exists in database")
        from mgc.domain.crypto_layer.root_key_parser import parse_root_key
        parsed_root_key, parsed_weight = parse_root_key(root_key)
        validate_startup_factors(parsed_root_key, parsed_weight, db_handler)
        from mgc.core.mgc_service.sensitive_service import SensitiveService
        sensitive_service = SensitiveService(crypto_service, db_handler)
        logger.info(f"sensitive_service initialized")
    migrate_service = MigrateService(database_handler=db_handler)
    mgc_core_service = MGCCoreService()
    status_service = StatusService(mgc_core_service)
    skills_manager = SkillsManager()

    from mgc.core.auth import get_token_manager
    token_mgr = get_token_manager()
    token_mgr.generate_token()
    token_mgr.save_token()
    logger.info("Token rotated on startup")

    api_router_manager = APIRouterManager(
        mgc_core_service=mgc_core_service,
        crypto_service=crypto_service,
        sensitive_service=sensitive_service,
        migrate_service=migrate_service,
        status_service=status_service,
        skills_manager=skills_manager,
        database_handler=db_handler,
        update_service=UpdateService(),
    )
    mgc_core_service.include_router(api_router_manager.router)
    # phase3：把 sensitive_service 引用挂到 mgc_core_service 上（main_async set_api_info 用）
    mgc_core_service.sensitive_service = sensitive_service
    mgc_core_service.api_router_manager = api_router_manager

    return mgc_core_service


def _update_webui_token():
    """在主程序完全启动后，更新 WebUI 的 token"""
    import socket
    import threading

    default_port = 57218

    def _is_port_available(port: int) -> bool:
        """判断端口是否真的被占用（排除 TIME_WAIT 假占用）。

        phase7 #9: 升级时旧主进程 TIME_WAIT 残留会让 bind 假性失败。
        采用方案 A+B：
          A. bind + SO_REUSEADDR → 覆盖 TIME_WAIT 残留
          B. bind 失败时降级为 connect 精确诊断是否真有 LISTEN
        """
        # A: bind with SO_REUSEADDR（覆盖 TIME_WAIT 残留）
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
                return True  # bind 成功 → 端口可用
        except OSError:
            pass

        # B: bind 失败 → connect 精确诊断
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                s.connect(("127.0.0.1", port))
                return False  # connect 成功 → 真有进程在 LISTEN → 不可用
        except (OSError, socket.timeout):
            return False  # bind 失败 + connect 失败 → 罕见情况，跳过

    def _run_webui(port: int, token: str):
        from mgc.presentation.webui.app import app
        app.state.token = token
        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")

    try:
        from mgc.presentation.webui.app import app
        from mgc.core.auth import get_token_manager

        token_mgr = get_token_manager()
        token = token_mgr.get_token()

        if not token:
            logger.warning("_update_webui_token: token is empty")
            return

        app.state.token = token

        if _is_port_available(default_port):
            thread = threading.Thread(target=_run_webui, args=(default_port, token), daemon=True)
            thread.start()
            print(f"\n[INFO] WEBUI started on http://127.0.0.1:{default_port}/skill")
        else:
            print(f"\n[INFO] WEBUI already running on http://127.0.0.1:{default_port}/skill")
    except Exception as e:
        logger.error(f"_update_webui_token error: {e}")


def _start_webui_if_needed():
    """检查并启动 WEBUI 服务（如果未启动）- 早期启动用"""
    import socket
    import threading

    default_port = 57218

    def _is_port_available(port: int) -> bool:
        """判断端口是否真的被占用（排除 TIME_WAIT 假占用）。

        phase7 #9: 升级时旧主进程 TIME_WAIT 残留会让 bind 假性失败。
        采用方案 A+B：
          A. bind + SO_REUSEADDR → 覆盖 TIME_WAIT 残留
          B. bind 失败时降级为 connect 精确诊断是否真有 LISTEN
        """
        # A: bind with SO_REUSEADDR（覆盖 TIME_WAIT 残留）
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
                return True  # bind 成功 → 端口可用
        except OSError:
            pass

        # B: bind 失败 → connect 精确诊断
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                s.connect(("127.0.0.1", port))
                return False  # connect 成功 → 真有进程在 LISTEN → 不可用
        except (OSError, socket.timeout):
            return False  # bind 失败 + connect 失败 → 罕见情况，跳过

    def _run_webui(port: int, token: str):
        from mgc.presentation.webui.app import app
        app.state.token = token
        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")

    if _is_port_available(default_port):
        from mgc.core.auth import get_token_manager
        token = get_token_manager().get_token()
        thread = threading.Thread(target=_run_webui, args=(default_port, token), daemon=True)
        thread.start()
        print(f"\n[INFO] WEBUI started on http://127.0.0.1:{default_port}/skill")
    else:
        print(f"\n[INFO] WEBUI already running on http://127.0.0.1:{default_port}/skill")


async def main_async() -> int:
    # Check if MGC core service port is already in use
    import socket
    default_port = 57219

    def _is_port_occupied(port: int) -> bool:
        """判断端口是否真的有进程在 LISTEN（排除 TIME_WAIT 假占用）。

        phase7 #9: 升级时旧主进程 TIME_WAIT 残留会让 bind 假性失败，
        导致误判为"MGC 已运行"而退出启动。
        采用方案 A+B：
          A. bind + SO_REUSEADDR → 覆盖 TIME_WAIT 残留；bind 成功说明端口可用
          B. bind 失败时降级为 connect 精确诊断是否真有 LISTEN
        """
        # A: bind with SO_REUSEADDR（覆盖 TIME_WAIT 残留）
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
                return False  # bind 成功 → 端口可用，未被占用
        except OSError:
            pass

        # B: bind 失败 → connect 精确诊断
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                s.connect(("127.0.0.1", port))
                return True  # connect 成功 → 真有进程在 LISTEN → 已被占用
        except (OSError, socket.timeout):
            return False  # bind 失败 + connect 失败 → 罕见情况，按"未占用"处理

    if _is_port_occupied(default_port):
        print(f"[INFO] MGC already running on port {default_port}")
        return 0

    if not initialize():
        return 1

    initialization_success = False

    print(f"MirginCipher v{VERSION}")
    # 修复 Windows GBK 编码问题：使用 ASCII 连字符替代 U+2011
    print("Multi-Agent Cross-Device Task Encryption, Execution & Delivery Tool.")
    print("===============================")
    print("Start MGC core service...")
    print("===============================")

    # 沙盒模式提示
    from mgc.domain.crypto_layer import is_sandbox_mode
    if is_sandbox_mode():
        print("\n[INFO] Sandbox Mode: If MCP cannot be used, call MGC through its FastAPI service instead.")

    db_exists = check_database_exists()
    db_key_exists = check_db_key_exists() if db_exists else False
    db_key_decrypt_failed = False

    if db_exists and db_key_exists:
        from mgc.config.user_settings import get_protection_mode
        if get_protection_mode():
            import os
            from mgc.key_storage.db_key_manager import _get_db_key_file_path
            db_key_path = _get_db_key_file_path()
            print(f"\nProtection mode enabled, deleting DB_KEY...")
            if os.path.exists(db_key_path):
                os.remove(db_key_path)
                print("DB_KEY deleted")
            db_key_exists = False

    if db_exists and db_key_exists:
        aes_key_2 = get_aes_key_2_from_db_key()
        if aes_key_2:
            from mgc.core.database.sqlcipher_handler import SQLCipherHandler
            SQLCipherHandler.set_aes_key_2(aes_key_2)
            from mgc.core.mgc_service.database.database_handler import DatabaseHandler
            db_handler = DatabaseHandler()
            try:
                db_handler.connect()
                print("\nKey verification successful, start MGC...")
            except Exception:
                db_key_decrypt_failed = True
                print("\nKey verification failed, hardware environment may have changed...")
        else:
            db_key_decrypt_failed = True
            print("\nDB_KEY.json decryption failed, hardware environment may have changed...")

    dialog = None
    if not db_exists or not db_key_exists or db_key_decrypt_failed:
        need_init = True
        db_key_recovered = False

        from mgc.presentation.interaction.dialog_factory import DialogFactory
        import os
        dialog_type = os.environ.get("MGC_DIALOG_TYPE")

        # 1.5.3 新增：判定 fresh install vs 恢复场景
        # 恢复场景 = db 存在但 DB_KEY 丢失 / 解密失败（必须输入原 key 才能恢复，不允许随机生成）
        is_recovery = db_key_decrypt_failed or (db_exists and not db_key_exists)

        if db_key_decrypt_failed:
            print("\nHardware environment changed, start interactive initialization...")
            # 设置环境变量，告知 WebUI 直接进入 root key 页
            os.environ["MGC_DB_KEY_DECRYPT_FAILED"] = "1"
        elif db_exists and not db_key_exists:
            # 2026-09-04 PR-9: database 存在但 DBKEY 缺失（dbkey.json 被删除等场景），
            # 也直接进入 root-key 页验证根密钥；不要让用户先选 confirm/migrate。
            # 之前这里没设 env，导致用户看到 install.html 必须先选一次，体验差且易选错。
            os.environ["MGC_DB_KEY_DECRYPT_FAILED"] = "1"
            print("\nDatabase exists but key file missing, start key recovery...")
        else:
            print("\nFirst installation detected, start interactive initialization...")

        dialog = DialogFactory.create(dialog_type)

        # 1.5.3.1：fresh install 与恢复场景都先走 CLI 询问
        # - fresh install：1=随机 / 2=WebUI / 3=取消
        # - 恢复场景：1=WebUI 设置 / 2=CLI 直接输入 / 3=取消（不允许随机，避免覆盖原密钥）
        from mgc.presentation.interaction.base_dialog import BaseDialog
        from mgc.config.i18n_config import Messages

        if is_recovery:
            # 恢复场景：CLI 询问走 WebUI 还是 CLI 直接输入
            # CLI banner 已在 choose_recovery_path() 内部打印（CLI_RECOVERY_BANNER）
            init_choice = dialog.choose_recovery_path()
        else:
            # fresh install：3 选项
            init_choice = dialog.choose_init_path()

        if init_choice == BaseDialog.RESULT_CANCEL_INSTALL:
            print("\nInstallation cancelled by user.")
            return 1

        if init_choice == BaseDialog.RESULT_RANDOM_GENERATE:
            # fresh install 选项 1：随机生成 + 落盘 + 直接初始化
            try:
                from mgc.core.installer.auto_key_generator import AutoKeyGenerator

                result = AutoKeyGenerator.run()
                personal_key = result["personal_key"]
                weight_param = result["weight_param"]
                saved_path = result["saved_path"]
                print()
                print(Messages.InitFlow.CLI_RANDOM_GENERATED.format(path=saved_path))
                print(Messages.InitFlow.CLI_RANDOM_WARNING)

                from mgc.service.storage_service import StorageService
                storage_service = StorageService()
                init_result = storage_service.initialize_database(
                    agent_uuid="init",
                    personal_key=personal_key,
                    weight_param=int(weight_param),
                )
                if not init_result or init_result.get("code") != 200:
                    print(f"\n[ERROR] Initialization failed: {init_result.get('message', 'unknown error')}")
                    return 1

                initialization_success = True
                skip_dialog_message = True
            except Exception as e:
                import traceback
                print(f"\n[ERROR] Random key init failed: {type(e).__name__}: {e}")
                print(traceback.format_exc())
                return 1
        elif init_choice == BaseDialog.RESULT_WEBUI_RECOVERY or init_choice == BaseDialog.RESULT_NEW_INSTALL:
            # 恢复场景选 1（WebUI）或 fresh install 选 2（WebUI）：启动 WebUI
            # 1.5.3.1 反馈#6：选项 2 必须真的启 WebUI，并多一个确认环节
            try:
                from mgc.presentation.interaction.webui_dialog import WebuiDialog
                webui_dialog = WebuiDialog()
                # 启 WebUI + 自动开浏览器 + 等待用户完成
                # （必须先 show_user_notice，_start_webui_service 才会设 self._port）
                webui_dialog.show_user_notice()
                # 1.5.3.1 反馈#4 修复：CLI 选 2 后给用户英文提示，让其知道 WebUI 已启动
                # 1.5.3.2 bug 修复：用 webui_dialog._port（实际监听端口，可能降级），
                # 之前写死 57218，降级时提示错误
                print()
                print("Launching MGC WebUI in your default browser...")
                print("Please complete the setup in the browser window. MGC CLI will wait here until you finish.")
                print(f"If the browser does not open automatically, navigate to http://127.0.0.1:{webui_dialog._port}/ manually.")
                print()
                # 等 WebUI 完成安装
                from mgc.presentation.interaction.webui_dialog import wait_for_completion, get_webui_result
                wait_for_completion()
                webui_result = get_webui_result()
                if webui_result.get("result") == BaseDialog.RESULT_CANCEL:
                    print("\nInstallation cancelled in WebUI.")
                    return 1

                # 【1.5.3.1 反馈 #4 修复】与 1.5.2 时代 main.py:623-645 行为对称：
                # WebUI 流程完成后，do_install 只写了 DB_KEY.json，没有建 db / 加密 root_key。
                # 这里在 WebUI 路径结束时显式调 StorageService.initialize_database。
                # 1.5.2 时代的 main.py:582-655 走的就是这条路径：
                #     input_root_key() 拿 key → StorageService.initialize_database 建 db
                # 注意：仅 fresh install（RESULT_NEW_INSTALL）需要；migrate 走 RESULT_MIGRATE，
                #      不需要重新 init（已有 root_key 记录）；WebUI Random 走 RESULT_RANDOM_GENERATE
                #      已在 /api/install/random-key-confirm 中完成 init。
                if webui_result.get("result") == BaseDialog.RESULT_NEW_INSTALL:
                    personal_key = webui_result.get("personal_key", "")
                    weight_param = webui_result.get("weight_param", "")
                    if personal_key and weight_param:
                        try:
                            from mgc.service.storage_service import StorageService
                            from mgc.domain.crypto_layer.root_key_parser import parse_root_key

                            # 1.5.2 时代做法：parse_root_key 拆 personal_key / weight
                            parsed_personal_key, parsed_weight = parse_root_key(
                                f"{personal_key}_{weight_param}"
                            )
                            storage_service = StorageService()
                            init_result = storage_service.initialize_database(
                                agent_uuid="init",
                                personal_key=parsed_personal_key,
                                weight_param=parsed_weight,
                            )
                            if not init_result or init_result.get("code") != 200:
                                print(
                                    f"\n[ERROR] WebUI init db failed: "
                                    f"{init_result.get('message', 'unknown') if init_result else 'no result'}"
                                )
                                return 1
                            logger.info("WebUI fresh install db initialized successfully")
                        except Exception as inner_e:
                            import traceback
                            print(f"\n[ERROR] WebUI init db failed: {type(inner_e).__name__}: {inner_e}")
                            print(traceback.format_exc())
                            return 1

                initialization_success = True
                skip_dialog_message = True
            except Exception as e:
                import traceback
                print(f"\n[ERROR] WebUI init failed: {type(e).__name__}: {e}")
                print(traceback.format_exc())
                return 1
        elif init_choice == BaseDialog.RESULT_CLI_INPUT:
            # 恢复场景选 2：CLI 直接输入秘钥
            try:
                personal_key, weight_param = dialog.input_root_key()
                if not personal_key:
                    print("Root key cannot be empty")
                    return 1

                # 走 DB_KEY 恢复路径
                from mgc.core.database.sqlcipher_handler import SQLCipherHandler
                from mgc.domain.crypto_layer.root_key_crypto import get_aes_key_2
                from mgc.key_storage import db_key_manager

                aes_key_2 = get_aes_key_2(personal_key, weight_param)
                SQLCipherHandler.set_aes_key_2(aes_key_2)

                from mgc.core.mgc_service.database.database_handler import DatabaseHandler
                db_handler = DatabaseHandler()
                db_handler.connect()

                db_key_manager.save(personal_key, weight_param)
                print("\nKey recovery successful.")
                db_key_exists = True
                db_key_recovered = True
                initialization_success = False  # 后续 build_services 会接管
                skip_dialog_message = True  # 跳过 dialog.show_message（已在 CLI 完成恢复）
            except Exception as e:
                import traceback
                print(f"\n[ERROR] CLI key recovery failed: {type(e).__name__}: {e}")
                print(traceback.format_exc())
                return 1
        else:
            # 未知 / 旧值
            choice = init_choice
            skip_dialog_message = False

        if not skip_dialog_message:
            if choice == dialog.RESULT_NO_INSTALL or choice == dialog.RESULT_CANCEL:
                print("Installation cancelled")
                return 1

            if choice == dialog.RESULT_MIGRATE:
                personal_key, weight_param, db_path = dialog.input_migrate_key()
                if not personal_key:
                    print("Personal key cannot be empty")
                    return 1

                try:
                    import shutil
                    from mgc.key_storage import db_key_manager
                    from mgc.core.database.sqlcipher_handler import SQLCipherHandler
                    from mgc.domain.crypto_layer.root_key_crypto import get_aes_key_2

                    target_db = os.path.join(MGC_ROOT, "src", "database", "mgc_black_box", "mgc_black_box.db")
                    if os.path.exists(db_path) and db_path != target_db:
                        os.makedirs(os.path.dirname(target_db), exist_ok=True)
                        shutil.copy2(db_path, target_db)
                        print(f"\nDatabase copied from {db_path}")

                    aes_key_2 = get_aes_key_2(personal_key, weight_param)
                    SQLCipherHandler.set_aes_key_2(aes_key_2)
                    db_key_manager.save(personal_key, weight_param)
                    print("\nMigration completed successfully")

                    print("\nStarting MGC service...")
                    initialization_success = True
                except Exception as e:
                    print(f"\nMigration failed: {e}")
                    return 1

            if choice == dialog.RESULT_NEW_INSTALL:
                personal_key, weight_param = dialog.input_root_key()
                if not personal_key:
                    print("Root key cannot be empty")
                    return 1

                migrate_key = personal_key + weight_param
                root_key = f"{personal_key}_{weight_param}"

                if db_exists and (not db_key_exists or db_key_decrypt_failed):
                    print("\nDatabase exists, verifying key...")
                    try:
                        from mgc.core.database.sqlcipher_handler import SQLCipherHandler
                        from mgc.domain.crypto_layer.root_key_crypto import get_aes_key_2
                        from mgc.key_storage import db_key_manager

                        aes_key_2 = get_aes_key_2(personal_key, weight_param)
                        SQLCipherHandler.set_aes_key_2(aes_key_2)

                        from mgc.core.mgc_service.database.database_handler import DatabaseHandler
                        db_handler = DatabaseHandler()
                        db_handler.connect()

                        print("Key verification successful, recovering key file...")
                        db_key_manager.save(personal_key, weight_param)
                        print("Key file recovered")

                        print("\nKey verification successful, start MGC...")
                        db_key_exists = True
                        db_key_recovered = True
                    except Exception as e:
                        print(f"\nKey verification failed: {e}")
                        print("Please verify your personal key and weight parameter")
                        return 1

                if not db_key_exists:
                    confirm_msg = f"Root Key: {root_key}\nMigrate Key: {migrate_key}\n\nConfirm to start initialization?"
                    if not dialog.confirm(confirm_msg):
                        print("Installation cancelled")
                        return 1

                if not db_key_recovered:
                    try:
                        from mgc.service.storage_service import StorageService
                        from mgc.domain.crypto_layer.root_key_parser import parse_root_key

                        personal_key, weight_param = parse_root_key(root_key)

                        storage_service = StorageService()
                        result = storage_service.initialize_database(
                            agent_uuid="init",
                            personal_key=personal_key,
                            weight_param=weight_param
                        )

                        if result and result.get("code") == 200:
                            from mgc.core.mgc_service.database.database_handler import DatabaseHandler
                            init_db_handler = DatabaseHandler()
                            init_db_handler.connect()
                            validate_startup_factors(root_key, weight_param, init_db_handler)
                            # Migration key file display disabled
                            # from mgc.utils.path_utils import get_migration_key_file
                            # migration_key_file = get_migration_key_file()
                            initialization_success = True
                        else:
                            dialog.show_message("Initialization Failed", result.get("message", "Unknown error"))
                            return 1
                    except Exception as e:
                        import traceback
                        error_msg = f"{type(e).__name__}: {str(e)}"
                        print(f"Initialization error: {error_msg}")
                        print(traceback.format_exc())
                        dialog.show_message("Initialization Failed", error_msg)
                        return 1
                else:
                    initialization_success = False
            else:
                initialization_success = False

    mgc_core_service = build_services()
    await mgc_core_service.start()

    # phase3：注入主进程 HTTP API 信息（bootstrap patched_run 用）
    try:
        from mgc.core.auth import get_token_manager
        token_mgr = get_token_manager()
        token = token_mgr.get_token()
        # sensitive_service 通过 mgc_core_service.sensitive_service 拿到（避免 main_async 局部变量作用域问题）
        ss = getattr(mgc_core_service, "sensitive_service", None)
        if ss is None:
            # 兜底：从 api_router_manager 拿
            ss = getattr(getattr(mgc_core_service, "api_router_manager", None), "sensitive_service", None)
        if ss is not None and token:
            ss.set_api_info(port=57219, token=token)
            logger.info(f"phase3: sensitive_service.set_api_info injected (port=57219)")
        else:
            logger.warning(f"phase3: sensitive_service not found via mgc_core_service")
    except Exception as e:
        logger.warning(f"phase3: failed to inject API info: {e}")

    _update_webui_token()

    if initialization_success:
        # 1.5.3：Random 路径（CLI 选项 1）已显示 saved_path + WARNING，跳过 dialog.show_message
        if not skip_dialog_message:
            dialog.show_message("Initialization Complete", "MirginCipher installed.\n\nPlease remember your personal key and weight parameter.\nLoss will result in unrecoverable data.")

    from mgc.config.path_config import PROJECT_ROOT, SKILLS_DIR, DOCS_DIR
    import shutil
    from mgc.presentation.interaction.mcp.mcp_server import _ensure_mcp_config

    skill_doc_dest = SKILLS_DIR / "mgc_skill.md"
    skill_doc_src = DOCS_DIR / "skill_spec.md"
    if skill_doc_src.exists():
        shutil.copy(skill_doc_src, skill_doc_dest)
    print(f"\n[INFO] Skill docs: {skill_doc_dest}")

    _ensure_mcp_config()
    print(f"[INFO] MCP config: {SKILLS_DIR / 'mcp_config.json'}")

    try:
        from mgc.service.update_service import UpdateService
        us = UpdateService()
        vc = us.check_version()
        # Print hint for ANY available update (including OPTIONAL patch
        # releases). WARNING level reserved for REQUIRED only.
        ul = vc.get("update_level", "")
        rv = vc.get("remote_version", "")
        lv = vc.get("local_version", "")
        has_newer = (
            vc.get("status") == "success"
            and ul in ("OPTIONAL", "RECOMMENDED", "REQUIRED")
            and rv
            and rv != lv
        )
        if has_newer:
            # Prefer WebUI one-click upgrade. auto_update=1 makes the
            # upgrade dialog auto-open when the URL is visited.
            webui_upgrade_url = ""
            try:
                import socket
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.3)
                    if s.connect_ex(('127.0.0.1', 57218)) == 0:
                        webui_upgrade_url = (
                            "http://127.0.0.1:57218/skill?auto_update=1"
                        )
            except Exception:
                pass
            if ul == "REQUIRED":
                if webui_upgrade_url:
                    print(f"[WARNING] CRITICAL UPDATE AVAILABLE: MGC {rv} released (REQUIRED). Your version {lv} is no longer supported.")
                    print(f"          Open: {webui_upgrade_url}")
                else:
                    print(f"[WARNING] CRITICAL UPDATE AVAILABLE: MGC {rv} released (REQUIRED). Your version {lv} is no longer supported. Run: pip install --upgrade mgc-blackbox")
            else:
                if webui_upgrade_url:
                    print(f"[INFO] MGC {rv} available ({ul}). Open: {webui_upgrade_url}")
                else:
                    print(f"[INFO] MGC {rv} available ({ul}). Run: pip install --upgrade mgc-blackbox")
    except Exception:
        pass

    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        print("\nReceived stop signal, shutting down service...")
        await mgc_core_service.stop()
        print("Service stopped")

    return 0


def main() -> int:
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--mcp":
        from mgc.presentation.interaction.mcp import run_stdio
        run_stdio()
        return 0
    # Delegate --status to the CLI handler in the __main__ block
    # so `python -m mgc --status` works (not only `python mgc/main.py --status`).
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        return _cli_status()
    return asyncio.run(main_async())


def _cli_status() -> int:
    """Handle `mgc --status` (human-readable status print)."""
    import socket
    from mgc.domain.crypto_layer import is_sandbox_mode
    from mgc.config.path_config import get_runtime_root

    def is_port_open(port: int) -> bool:
        """Check if a TCP port is currently in LISTEN state."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            return result == 0
        except Exception:
            return False

    try:
        from mgc import __version__
    except ImportError:
        __version__ = "unknown"

    webui_running = is_port_open(57218)
    api_running = is_port_open(57219)
    running = webui_running or api_running

    def fmt(value, width=10):
        return str(value).ljust(width)

    print("MGC Blackbox Status")
    print("-" * 40)
    print(f"  {fmt('Version:')}     {__version__}")
    print(f"  {fmt('Running:')}     {'yes' if running else 'no'}")
    print(f"  {fmt('Sandbox:')}     {'on' if is_sandbox_mode() else 'off'}")
    print(f"  {fmt('WebUI:')}       {'http://127.0.0.1:57218/skill' if webui_running else 'not running'}")
    print(f"  {fmt('Main API:')}    {'http://127.0.0.1:57219' if api_running else 'not running'}")
    print(f"  {fmt('Data Path:')}   {get_runtime_root()}")
    return 0


if __name__ == "__main__":
    import argparse
    import json
    import socket

    parser = argparse.ArgumentParser(description="MirginCipher MGC")
    parser.add_argument("--mcp", action="store_true", help="Start as MCP Server (stdio mode)")
    parser.add_argument("--status", action="store_true", help="Show MGC status")
    args = parser.parse_args()

    if args.status:
        # Show MGC status in human-readable form.
        from mgc.domain.crypto_layer import is_sandbox_mode
        from mgc.config.path_config import get_runtime_root

        def is_port_open(port):
            """Check if a TCP port is currently in LISTEN state."""
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            try:
                result = sock.connect_ex(('127.0.0.1', port))
                sock.close()
                return result == 0
            except Exception:
                return False

        try:
            from mgc import __version__
        except ImportError:
            __version__ = "unknown"

        webui_running = is_port_open(57218)
        api_running = is_port_open(57219)
        running = webui_running or api_running

        def fmt(value, width=10):
            return str(value).ljust(width)

        print("MGC Blackbox Status")
        print("-" * 40)
        print(f"  {fmt('Version:')}     {__version__}")
        print(f"  {fmt('Running:')}     {'yes' if running else 'no'}")
        print(f"  {fmt('Sandbox:')}     {'on' if is_sandbox_mode() else 'off'}")
        print(f"  {fmt('WebUI:')}       {'http://127.0.0.1:57218/skill' if webui_running else 'not running'}")
        print(f"  {fmt('Main API:')}    {'http://127.0.0.1:57219' if api_running else 'not running'}")
        print(f"  {fmt('Data Path:')}   {get_runtime_root()}")
        sys.exit(0)

    if args.mcp:
        from mgc.presentation.interaction.mcp import run_stdio
        run_stdio()
    else:
        sys.exit(main())

