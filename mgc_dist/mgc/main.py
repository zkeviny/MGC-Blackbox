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

    return mgc_core_service


def _update_webui_token():
    """在主程序完全启动后，更新 WebUI 的 token"""
    import socket
    import threading

    default_port = 57218

    def _is_port_available(port: int) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return True
        except OSError:
            return False

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
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return True
        except OSError:
            return False

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
    if not initialize():
        return 1

    initialization_success = False

    print(f"MirginCipher v{VERSION}")
    print("A trusted boundary for intent‑safe AI execution.")
    print("===============================")
    print("Start MGC core service...")
    print("===============================")

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
        
        if db_key_decrypt_failed:
            print("\nHardware environment changed, start interactive initialization...")
        elif db_exists and not db_key_exists:
            print("\nDatabase exists but key file missing, start key recovery...")
        else:
            print("\nFirst installation detected, start interactive initialization...")

        from mgc.presentation.interaction.dialog_factory import DialogFactory
        import os
        dialog_type = os.environ.get("MGC_DIALOG_TYPE")
        dialog = DialogFactory.create(dialog_type)

        choice = dialog.show_user_notice()
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

        if choice == 3:
            change_result = dialog.input_change_root_key()
            if change_result is None:
                print("Root key change cancelled")
                return 1

            old_personal_key, old_weight_param, new_personal_key, new_weight_param = change_result

            try:
                from mgc.core.mgc_service.root_key_change_service import RootKeyChangeService
                from mgc.core.mgc_service.database.database_handler import DatabaseHandler

                db_handler = DatabaseHandler()
                service = RootKeyChangeService(db_handler)

                service.change_root_key(
                    old_personal_key,
                    old_weight_param,
                    new_personal_key,
                    new_weight_param
                )

                print("\nRoot key changed successfully!")
                print("\nStarting MGC service...")
                initialization_success = True
            except Exception as e:
                print(f"\nRoot key change failed: {e}")
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

    _update_webui_token()

    if initialization_success:
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

    print(f"[INFO] Delete: MGC considers all stored info as user's valuable assets, so delete functionality is NOT provided. To delete manually: Use WebUI Database Audit to get DB key, then delete via DB Browser.")

    try:
        from mgc.service.update_service import UpdateService
        us = UpdateService()
        vc = us.check_version()
        if vc.get("status") == "success" and vc.get("update_level") != "OPTIONAL":
            lv = vc.get("local_version", "")
            rv = vc.get("remote_version", "")
            ul = vc.get("update_level", "")
            if ul == "REQUIRED":
                print(f"[WARNING] CRITICAL UPDATE AVAILABLE: MGC {rv} released (REQUIRED). Your version {lv} is no longer supported. Please upgrade manually: pip install --upgrade mgc-blackbox")
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
    return asyncio.run(main_async())


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="MirginCipher MGC")
    parser.add_argument("--mcp", action="store_true", help="Start as MCP Server (stdio mode)")
    args = parser.parse_args()

    if args.mcp:
        from mgc.presentation.interaction.mcp import run_stdio
        run_stdio()
    else:
        sys.exit(main())

