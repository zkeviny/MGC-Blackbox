"""
国际化配置模块

功能：
- 定义所有界面和提示信息的英文版本
- 提供统一的消息访问接口
- 支持未来的多语言扩展

依赖：
- 无

限制条件：
- 所有消息必须与"document\1.0细节需求文档\界面和提示信息中英文映射表.md"保持一致
"""

class Messages:
    """消息常量类"""

    # ==================== API返回消息 ====================
    
    class API:
        """API返回消息"""
        
        # 通用消息
        USER_NOT_AGREE_INSTALLATION = "User did not agree to installation"
        INIT_SERVICE_NOT_INITIALIZED = "Initialization service not initialized"
        OPERATION_SUCCESSFUL = "Operation successful"
        ENCRYPTION_SERVICE_NOT_INITIALIZED = "Encryption service not initialized"
        SENSITIVE_SERVICE_NOT_INITIALIZED = "Sensitive information hosting service not initialized"
        MIGRATION_SERVICE_NOT_INITIALIZED = "Migration authorization service not initialized"
        STATUS_SERVICE_NOT_INITIALIZED = "Status query service not initialized"
        MGC_CORE_SERVICE_NOT_INITIALIZED = "MGC core service not initialized"
        UPDATE_SERVICE_NOT_INITIALIZED = "Update service not initialized"
        
        # 加密解密消息
        ENCRYPTION_SUCCESSFUL = "Encryption successful"
        BATCH_ENCRYPTION_SUCCESSFUL = "Batch encryption successful"
        DECRYPTION_SUCCESSFUL = "Decryption successful"
        BATCH_DECRYPTION_SUCCESSFUL = "Batch decryption successful"
        
        # 敏感信息托管消息
        SAVE_SUCCESSFUL = "Save successful"
        DELETE_SUCCESSFUL = "Delete successful"
        UPDATE_SUCCESSFUL = "Update successful"
        
        # 迁移授权消息
        MIGRATION_AUTHORIZATION_SUCCESSFUL = "Migration authorization successful"
        MODIFICATION_SUCCESSFUL = "Modification successful"
        
        # 服务控制消息
        SERVICE_STARTED_SUCCESSFULLY = "Service started successfully"
        SERVICE_STOPPED_SUCCESSFULLY = "Service stopped successfully"
        SERVICE_RESTARTED_SUCCESSFULLY = "Service restarted successfully"
        
        # AI转发消息
        ADD_SUCCESSFUL = "Add successful"
        VERIFICATION_SUCCESSFUL = "Verification successful"
    
    # ==================== 打包卸载消息 ====================
    
    class Package:
        """Package异常消息"""
        
        PACKAGE_CONFIG_FILE_NOT_FOUND = "Package config file not found: {file_path}"
        CORE_MODULE_IMPORT_FAILED = "Failed to import core module: {error}"
        INSTALL_VERIFICATION_FAILED = "Installation verification failed"
        INSTALL_VERIFICATION_SUCCESSFUL = "Installation verification successful"
        USER_DATA_WILL_BE_PRESERVED = "Note: User data will be preserved"
        WARNING_USER_DATA_WILL_BE_DELETED = "Warning: User data will be deleted"
        CONFIRM_DELETE_USER_DATA = "Confirm deletion of user data? (yes/no): "
        CANCEL_UNINSTALLATION = "Cancel uninstallation"
        UNINSTALL_COMPLETE = "Uninstallation complete"
        PLEASE_RUN = "Please run: {command}"
        CONFIGURE_ENVIRONMENT_VARIABLES_FIRST = "Note: Configure environment variables first"
        RELEASE_URL_FROM_CONFIG_FILE = "Note: release_url is read from config file to avoid hardcoding"
        PACKAGE_CONFIG_FILE_USED_FOR_PACKAGING = "Note: This file is used for package configuration, hardcoding is prohibited"
        PYPROJECT_TOML_ENV_VAR_CONFIG = "Note: URLs in pyproject.toml also need to be configured via environment variables to avoid hardcoding"
    
    # ==================== 异常消息 ====================
    
    class SkillsManager:
        """SkillsManager异常消息"""
        
        LOAD_SKILLS_FAILED = "Failed to load Skills"
        SKILL_NAME_CANNOT_BE_EMPTY = "Skill name cannot be empty"
        GET_SKILL_FAILED = "Failed to get Skill"
        SKILL_NAME_AND_CONTENT_CANNOT_BE_EMPTY = "Skill name and content cannot be empty"
        SKILL_ALREADY_EXISTS = "Skill '{skill_name}' already exists"
        ADD_SKILL_FAILED = "Failed to add Skill"
        UPDATE_SKILL_FAILED = "Failed to update Skill"
        SKILL_DOES_NOT_EXIST = "Skill '{skill_name}' does not exist"
        DELETE_SKILL_FAILED = "Failed to delete Skill"
        LIST_SKILLS_FAILED = "Failed to list Skills"
        GET_VERSION_INFO_FAILED = "Failed to get version information"
        CHECK_UPDATES_FAILED = "Failed to check updates"
        NETWORK_TIMEOUT = "Network timeout, switched to offline mode"
        RECORD_HEARTBEAT_FAILED = "Failed to record heartbeat"
        GET_HEARTBEAT_STATS_FAILED = "Failed to get heartbeat statistics"
        PREPARE_UNINSTALL_FAILED = "Failed to prepare uninstall"
        FILE_LOCK_TIMEOUT = "File lock timeout, operation aborted"
    
    class DatabaseHandler:
        """DatabaseHandler异常消息"""
        
        READ_DATABASE_CONFIG_FAILED = "Failed to read database configuration"
        CONNECT_DATABASE_FAILED = "Failed to connect to database"
        DISCONNECT_DATABASE_FAILED = "Failed to disconnect from database"
        DATABASE_NOT_CONNECTED = "Database not connected"
        DATABASE_REKEY_FAILED = "Failed to rekey database"
        EXECUTE_QUERY_FAILED = "Failed to execute query"
        EXECUTE_UPDATE_FAILED = "Failed to execute update"
        INIT_TABLES_FAILED = "Failed to initialize database tables: {error}"
        UNSUPPORTED_DATABASE_TYPE = "Unsupported database type: {db_type}"
    
    class MGCCoreService:
        """MGCCoreService异常消息"""
        
        PORT_ALREADY_IN_USE = "Port {port} is already in use"
        START_MGC_CORE_SERVICE_FAILED = "Failed to start MGC core service"
        STOP_MGC_CORE_SERVICE_FAILED = "Failed to stop MGC core service"
        RESTART_MGC_CORE_SERVICE_FAILED = "Failed to restart MGC core service"
    
    class SensitiveService:
        """SensitiveService异常消息"""
        
        PARAMETERS_CANNOT_BE_EMPTY = "Parameters cannot be empty"
        DATABASE_OPERATION_FAILED = "Database operation failed"
        SAVE_AI_API_KEY_FAILED = "Failed to save AI API Key"
        SAVE_CODE_SENSITIVE_INFO_FAILED = "Failed to save code sensitive information"
        GET_HOSTING_LIST_FAILED = "Failed to get hosting list"
        KEY_ALIAS_CANNOT_BE_EMPTY = "Key alias cannot be empty"
        KEY_ALIAS_DOES_NOT_EXIST = "Key alias '{key_alias}' does not exist"
        DELETE_SENSITIVE_INFO_FAILED = "Failed to delete sensitive information"
        UPDATE_KEY_ALIAS_FAILED = "Failed to update key alias '{key_alias}'"
        UPDATE_SENSITIVE_INFO_FAILED = "Failed to update sensitive information"
    
    class InitService:
        """InitService异常消息"""
        
        ROOT_KEY_AND_MIGRATION_KEY_CANNOT_BE_EMPTY = "Root key and migration key cannot be empty"
        DATABASE_CONNECTION_FAILED = "Database connection failed"
        INITIALIZATION_INSTALLATION_FAILED = "Initialization installation failed"
    
    class MigrateService:
        """MigrateService异常消息"""
        
        MIGRATION_KEY_CANNOT_BE_EMPTY = "Migration key cannot be empty"
        MIGRATION_KEY_VERIFICATION_FAILED = "Migration key verification failed"
        OLD_MIGRATION_KEY_VERIFICATION_FAILED = "Old migration key verification failed"
        DEVICE_MIGRATION_AUTHORIZATION_FAILED = "Device migration authorization failed"
        MODIFY_MIGRATION_KEY_FAILED = "Failed to modify migration key"
        MIGRATION_KEY_FILE_DOES_NOT_EXIST = "Migration key file does not exist"
        VERIFY_MIGRATION_KEY_FAILED = "Failed to verify migration key"
    
    class StatusService:
        """StatusService异常消息"""
        
        GET_RUNNING_STATUS_FAILED = "Failed to get running status"
        GET_DEVICE_INFO_FAILED = "Failed to get device information"
        GET_LOGS_FAILED = "Failed to get logs"
    
    class CryptoService:
        """CryptoService异常消息"""
        
        EXTRACT_DYNAMIC_SALT_FAILED = "Failed to extract dynamic salt"
        ENCRYPTION_CONTENT_CANNOT_BE_EMPTY = "Encryption content cannot be empty"
        HASH_CALCULATION_FAILED = "Hash calculation failed"
        ENCRYPTION_FAILED = "Encryption failed"
        ENCRYPTION_CONTENT_LIST_CANNOT_BE_EMPTY = "Encryption content list cannot be empty"
        BATCH_ENCRYPTION_FAILED = "Batch encryption failed"
        DECRYPTION_CONTENT_CANNOT_BE_EMPTY = "Decryption content cannot be empty"
        CIPHER_FORMAT_ERROR = "Cipher format error"
        ROOT_KEY_MISMATCH_DECRYPTION_FAILED = "Root key mismatch, decryption failed"
        CIPHER_BASE64_DECODING_FAILED = "Cipher Base64 decoding failed"
        DECRYPTION_FAILED = "Decryption failed"
    
    class APIRouter:
        """APIRouter异常消息"""
        
        MISSING_AUTHORIZATION_HEADER = "Missing Authorization header"
        REQUEST_TIMEOUT = "Request timeout"
        REQUEST_FAILED = "Request failed: {error}"
    
    # ==================== 安装模块异常 ====================
    
    class DailyAccountGenerator:
        """DailyAccountGenerator异常消息"""
        
        ROOT_KEY_CANNOT_BE_EMPTY_FOR_DYNAMIC_SALT = "Root key cannot be empty, must provide root key to generate dynamic salt"
        ROOT_KEY_FORMAT_ERROR_PERSONAL_KEY_WEIGHT_PARAM = "Root key format error, should be 'personal_key_weight_parameter'"
        GENERATE_DAILY_ACCOUNT_FAILED = "Failed to generate device daily account: {error}"
        GENERATE_ACCOUNT_CREDENTIALS_FAILED = "Failed to generate account credentials: {error}"
        CREATE_ACCOUNT_FAILED = "Failed to create account: {error}"
        GRANT_PERMISSIONS_FAILED = "Failed to grant permissions: {error}"
        REGENERATE_DAILY_ACCOUNT_FAILED = "Failed to regenerate device daily account: {error}"
        DELETE_DAILY_ACCOUNTS_FAILED = "Failed to delete device daily accounts"
    
    class KeysInput:
        """KeysInput异常消息"""
        
        USER_INTERRUPTED_KEY_INPUT = "User interrupted key input"
        POPUP_INTERACTION_MODE_EXCEPTION = "Popup interaction mode exception: {error}"
        COMMAND_MODE_KEYS_CANNOT_BE_EMPTY = "Command mode: Root key and migration key cannot be empty"
        COMMAND_AUTOMATIC_MODE_EXCEPTION = "Command automatic mode exception: {error}"
        ROOT_KEY_FORMAT_ERROR = "Root key format error, should be 'root_key' or 'root_key weight_parameter'"
        ROOT_KEY_CANNOT_BE_EMPTY = "Root key cannot be empty"
        ROOT_KEY_LENGTH_TOO_SHORT = "Root key length cannot be less than {min_length} digits"
        ROOT_KEY_LENGTH_TOO_LONG = "Root key length cannot be more than {max_length} digits"
        WEIGHT_PARAM_CANNOT_BE_EMPTY = "Weight parameter cannot be empty"
        WEIGHT_PARAM_MUST_BE_DIGITS = "Weight parameter must be digits"
        WEIGHT_PARAM_LENGTH_TOO_SHORT = "Weight parameter length cannot be less than {min_length} digits"
        WEIGHT_PARAM_LENGTH_TOO_LONG = "Weight parameter length cannot be more than {max_length} digits"
        MIGRATE_KEY_CANNOT_BE_EMPTY = "Migration key cannot be empty"
        MIGRATE_KEY_LENGTH_TOO_SHORT = "Migration key length cannot be less than {min_length} digits"
        MIGRATE_KEY_LENGTH_TOO_LONG = "Migration key length cannot be more than {max_length} digits"
        SAVE_PATH_CANNOT_BE_EMPTY = "Save path cannot be empty"
        WEIGHT_PARAM_CANNOT_BE_EMPTY_FORMAT = "Weight parameter cannot be empty, please input 'root_key weight_parameter' format"
        WEIGHT_PARAM_ERROR = "Weight parameter error: {error_msg}"
        ROOT_KEY_AND_MIGRATE_KEY_CANNOT_BE_EMPTY = "Root key and migration key cannot be empty"
        ROOT_KEY_AND_MIGRATE_KEY_CANNOT_BE_SAME = "Root key and migration key cannot be the same"
    
    class RootKeyEncryptor:
        """RootKeyEncryptor异常消息"""
        
        ROOT_KEY_AND_HARDWARE_FINGERPRINT_CANNOT_BE_EMPTY = "Root key and hardware fingerprint cannot be empty"
        ROOT_KEY_ENCRYPTION_FAILED = "Root key encryption failed: {error}"
        MIGRATE_KEY_CANNOT_BE_EMPTY = "Migration key cannot be empty"
        MIGRATE_KEY_HASH_CALCULATION_FAILED = "Migration key hash calculation failed: {error}"
        MGC_ROOT_SECURE_TABLE_ALREADY_HAS_DATA = "Data already exists in mgc_root_secure table, cannot insert duplicate"
        ROOT_KEY_STORAGE_FAILED = "Root key storage failed: {error}"
        ENCRYPT_AND_STORE_ROOT_KEY_FAILED = "Failed to encrypt and store root key: {error}"
        ROOT_KEY_NOT_FOUND_IN_DATABASE = "Root key not found in database"
        ROOT_KEY_VERIFICATION_FAILED = "Root key verification failed: {error}"
        MIGRATE_KEY_HASH_NOT_FOUND_IN_DATABASE = "Migration key hash value not found in database"
        MIGRATE_KEY_VERIFICATION_FAILED = "Migration key verification failed: {error}"
        ROOT_KEY_VERIFICATION_FAILED_RETRIEVE = "Root key verification failed"
        ROOT_KEY_FORMAT_ERROR_PERSONAL_KEY_WEIGHT_PARAM = "Root key format error, should be 'personal_key_weight_parameter'"
        ROOT_KEY_RETRIEVAL_FAILED = "Root key retrieval failed: {error}"

    class RootKeyChangeService:
        """RootKeyChangeService异常消息"""

        PERSONAL_KEY_AND_WEIGHT_PARAM_CANNOT_BE_EMPTY = "Personal key and weight parameter cannot be empty"
        NEW_PERSONAL_KEY_AND_WEIGHT_PARAM_CANNOT_BE_EMPTY = "New personal key and weight parameter cannot be empty"
        NEW_KEY_CANNOT_BE_SAME_AS_OLD_KEY = "New key cannot be the same as old key"
        ROOT_KEY_AUTHENTICATION_FAILED = "Root key authentication failed"
        ROOT_KEY_NOT_FOUND_IN_DATABASE = "Root key not found in database"
        WEIGHT_PARAM_NOT_FOUND_IN_DATABASE = "Weight parameter not found in database"
        FAILED_TO_GET_ROOT_KEY_FROM_DB = "Failed to get root key from database: {error}"
        FAILED_TO_GET_WEIGHT_PARAM_FROM_DB = "Failed to get weight parameter from database: {error}"
        FAILED_TO_UPDATE_ROOT_KEY_IN_DB = "Failed to update root key in database: {error}"
        FAILED_TO_UPDATE_WEIGHT_PARAM_IN_DB = "Failed to update weight parameter in database: {error}"
        ROOT_KEY_CHANGE_FAILED = "Root key change failed: {error}"

    class MigrationAccountCreator:
        """MigrationAccountCreator异常消息"""
        
        MIGRATE_KEY_CANNOT_BE_EMPTY = "Migration key cannot be empty"
        ACCOUNT_ALREADY_EXISTS = "Account {account_name} already exists"
        CREATE_MIGRATION_ACCOUNT_FAILED = "Failed to create migration account: {error}"
        CREATE_ACCOUNT_FAILED = "Failed to create account: {error}"
        GRANT_PERMISSIONS_FAILED = "Failed to grant permissions: {error}"
    
    class EnvFactorGenerator:
        """EnvFactorGenerator异常消息"""
        
        ROOT_KEY_CANNOT_BE_EMPTY = "Root key cannot be empty"
        MGC_SYSTEM_ENV_TABLE_ALREADY_HAS_DATA = "Data already exists in mgc_system_env table, cannot insert duplicate"
        MGC_INFO_1_ENV_FACTOR_ALREADY_EXISTS = "Environment factor already exists in mgc_info_1 table, cannot insert duplicate"
        GENERATE_INITIAL_ENV_FACTOR_FAILED = "Failed to generate initial environment factor: {error}"
        ENCRYPT_ENV_FACTOR_FAILED = "Failed to encrypt environment factor: {error}"
        STORE_ENV_FACTOR_FAILED = "Failed to store environment factor: {error}"
        GENERATE_AND_STORE_ENV_FACTOR_FAILED = "Failed to generate and store initial environment factor: {error}"
    
    class MigrateKeySaver:
        """MigrateKeySaver异常消息"""
        
        SAVE_MIGRATE_KEY_FAILED = "Failed to save migration key: {error}"
        CREATE_SAVE_DIRECTORY_FAILED = "Failed to create save directory: {error}"
        WRITE_MIGRATE_KEY_FILE_FAILED = "Failed to write migration key file: {error}"
    
    class MigrateKeySaverUI:
        """MigrateKeySaver用户界面提示"""
        
        SAVE_SUCCESS_TITLE = "[Migration Key Saved Successfully]"
        MIGRATE_KEY_SAVED_TO = "Migration key has been saved to: {save_path}"
        IMPORTANT_NOTICE = "Important Notice:"
        KEY_LOSS_CANNOT_MIGRATE = "- If this key is lost, environment migration will be impossible and cannot be recovered"
        DO_NOT_SHARE_KEY = "- Do not share this key with anyone"
        SAVE_IN_SAFE_LOCATION = "- It is recommended to save this file in a safe location"
        MIGRATE_KEY_SAVED_TO_COMMAND = "Migration key has been saved to: {save_path}"
        KEEP_SAFE_CANNOT_RECOVER = "Please keep it safe, if lost, environment migration will be impossible and cannot be recovered"
        SAVE_FAILED_TITLE = "[Migration Key Save Failed]"
        ERROR_INFORMATION = "Error information: {error_msg}"
        ERROR_MESSAGE = "{error_msg}"
    
    class UserNotice:
        """UserNotice异常消息"""
        
        POPUP_INTERACTION_MODE_EXCEPTION = "Popup interaction mode exception: {error}"
        COMMAND_AUTOMATIC_MODE_EXCEPTION = "Command automatic mode exception: {error}"
        UNKNOWN_INSTALLATION_SOURCE = "Unknown installation source: {install_source}"
    
    # ==================== 用户界面提示 ====================
    
    class UserNotice:
        """用户须知提示"""
        
        TITLE = "[MirginCipher Security Notice]"
        TOOL_DESCRIPTION = "This tool is a local top-secret black box for encrypting and storing various sensitive information. All information is not stored in the cloud;"
        INFO_MANAGEMENT = "After information is stored, it will be managed by MGC system and can only be accessed through this tool. Direct viewing or export is not possible;"
        PRIVILEGE_DESCRIPTION = "The current version does not provide database highest privileges. Related credentials will be automatically destroyed after initialization;"
        UNINSTALLATION_DESCRIPTION = "Uninstallation only removes the program, data is retained. Reinstalling MGC allows reuse;"
        COMPLETE_CLEANUP = "You can manually delete related files for complete cleanup. After deletion, reinstalling MGC will not recover information."
        AGREEMENT_NOTICE = "By agreeing, you acknowledge and agree to the above rules."
        PRIVACY_STATEMENT = "*Only you are the sole keeper of your information."
        ENTER_YOUR_CHOICE = "Please enter your choice:"
        AGREE_OPTION = "[1] Agree"
        EXIT_OPTION = "[2] Exit"
        SELECT_OPTION = "Please select [1/2]:"
        AGREED_SUCCESS = "You have agreed to the user notice, continuing installation process..."
        EXITED_SUCCESS = "You have exited the installation process"
        INVALID_INPUT = "Invalid input, please select again [1/2]"
        USER_INTERRUPTED = "User interrupted, exiting installation process"
        DETECTED_AGREE_PARAMETER = "Detected --agree parameter, automatically agreeing to user notice"
        ENTER_YES_TO_AGREE = "Please enter 'yes' to agree to the user notice, any other input will exit the installation process"
        ENTER_YOUR_CHOICE_AGAIN = "Please enter your choice:"
        AGREED_SUCCESS_AGAIN = "You have agreed to the user notice, continuing installation process..."
        DID_NOT_AGREE = "You did not agree to the user notice, exiting the installation process"
        USER_INTERRUPTED_AGAIN = "User interrupted, exiting the installation process"
    
    class KeysInputUI:
        """密钥输入提示"""
        
        KEY_CONFIGURATION_TITLE = "[Key Configuration]"
        USER_INTERRUPTED_EXIT = "User interrupted, exiting installation process"
        ROOT_KEY_INPUT_TITLE = "[Root Key Input]"
        ROOT_KEY_NOTE = "Note: Root key is 8+ alphanumeric characters, not exported, not archived, leaves no trace, and is remembered by the user"
        ENTER_ROOT_KEY = "Please enter root key"
        WEIGHT_PARAMETER_INPUT_TITLE = "[Weight Parameter Input]"
        WEIGHT_PARAMETER_NOTE = "Note: Weight parameter is a 1-10 digit integer"
        ENTER_WEIGHT_PARAMETER = "Please enter weight parameter"
        ROOT_KEY_AND_WEIGHT_FORMAT_CORRECT = "Root key and weight parameter format is correct"
        MIGRATION_KEY_INPUT_TITLE = "[Migration Key Input]"
        MIGRATION_KEY_NOTE_1 = "Note: Migration key is saved in MGC root directory by default, please keep it safe,"
        MIGRATION_KEY_NOTE_2 = "If lost, environment migration will be impossible and cannot be recovered"
        ENTER_MIGRATION_KEY = "Please enter migration key"
        MIGRATION_KEY_FORMAT_CORRECT = "Migration key format is correct"
        MIGRATION_KEY_SAVE_PATH_TITLE = "[Migration Key Save Path]"
        DEFAULT_PATH = "Default path: {default_path}"
        PRESS_ENTER_TO_USE_DEFAULT = "Note: Press Enter directly to use the default path"
        ENTER_SAVE_PATH = "Please enter save path (leave empty to use default)"
        SAVE_PATH = "Save path: {save_path}"
    
    # ==================== HTTP异常消息 ====================
    
    class HTTP:
        """HTTP异常消息"""
        
        MISSING_AUTHORIZATION_HEADER = "Missing Authorization header"
        REQUEST_TIMEOUT = "Request timeout"
        REQUEST_FAILED = "Request failed: {error}"


def get_message(message_class, message_name, **kwargs):
    """
    获取消息
    
    入参：
        message_class: 消息类（如Messages.API）
        message_name: 消息名称（如USER_NOT_AGREE_INSTALLATION）
        **kwargs: 格式化参数（如skill_name="test"）
    
    出参：
        str: 格式化后的消息
    """
    message = getattr(message_class, message_name, None)
    if message is None:
        return f"Message not found: {message_class.__name__}.{message_name}"
    
    try:
        return message.format(**kwargs)
    except (KeyError, ValueError) as e:
        return message


def get_api_message(message_name, **kwargs):
    """
    获取API消息
    
    入参：
        message_name: 消息名称
        **kwargs: 格式化参数
    
    出参：
        str: 格式化后的消息
    """
    return get_message(Messages.API, message_name, **kwargs)


def get_exception_message(exception_class, message_name, **kwargs):
    """
    获取异常消息
    
    入参：
        exception_class: 异常类（如Messages.SkillsManager）
        message_name: 消息名称
        **kwargs: 格式化参数
    
    出参：
        str: 格式化后的消息
    """
    return get_message(exception_class, message_name, **kwargs)


def get_ui_message(ui_class, message_name, **kwargs):
    """
    获取UI消息
    
    入参：
        ui_class: UI类（如Messages.UserNotice）
        message_name: 消息名称
        **kwargs: 格式化参数
    
    出参：
        str: 格式化后的消息
    """
    return get_message(ui_class, message_name, **kwargs)
