"""Node key service for managing node RSA key pairs.

Handles generation, storage, and retrieval of node public/private keys.

1.5.2 hotfix P0: All node-owned credentials (registered in
NODE_CREDENTIALS_REGISTRY) are written through an independent SQL path
that bypasses sensitive_service._save_to_mgc_info_1's NODE_KEY_WRITE_PROTECTED
guard. This makes NodeKeyService the single legitimate writer for
node identity credentials.

1.5.4: Adds ``DEFAULT_NODE_PEM_PUB`` / ``DEFAULT_NODE_PEM_PRIV`` — a
fixed RSA-2048 keypair that ALL 1.5.4+ nodes share. Used for free-mode
sealing: the ext03 inner layer is RSA-wrapped by this public key so any
mgc node can unwrap it; the outer layer is AES-GCM keyed by SHA-256(ext07)
so only parties that know the source node_pub can recover the inner
RSA ciphertext. See ``ensure_default_keys``.
"""

import logging
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

PUB_KEY_INFO_TYPE = "__NODE_PUB__"
PUB_KEY_INFO_OWNER = "__NODE_PUB__"

# 1.5.4+：所有节点共享的固定 RSA-2048 密钥对（free mode 用）。
# 这是一对真实生成的密钥，**所有 1.5.4+ 节点必须共用**。
# 由 ensure_default_keys() 在 db 没有时写入 SQLCipher；已有则不动。
# 切勿随意更换（更换即所有 free mode sealed 包失效）。
DEFAULT_NODE_PEM_PUB = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAnooAnQzgNYaNcPvO2x9x\n"
    "3Vxz28FBIhNzX8ZCiEwzUfiG61Gg3UmRCdRXbPLuXKgDb9Z/66Vs/aWVfzInq7G1\n"
    "GwhV3McreW4Ixm2WHmVtN4GYF8xqd77BUj3QJwE3N3PkFuL2pX8TM0R87hx4k7zy\n"
    "EwMDT6dWjWmVZBNTG00V+snBT+Wn3Pkwjrg4wyCQmiBRzSzSGqYoqlsBU76X0Qcx\n"
    "qzEy+efWq6Ef0pOS4ZymeW6wu5m7JvsdsmOk4mzihoUVRpxKCd4r1axdklw3RN/U\n"
    "v1KMQ/vG+hsBfMRc3YnuyO4crjbBt3p+h8ZZpr2p3uXy+UBh9nhD6c1u8NVBhzsb\n"
    "2wIDAQAB\n"
    "-----END PUBLIC KEY-----"
)
DEFAULT_NODE_PEM_PRIV = (
    "-----BEGIN RSA PRIVATE KEY-----\n"
    "MIIEowIBAAKCAQEAnooAnQzgNYaNcPvO2x9x3Vxz28FBIhNzX8ZCiEwzUfiG61Gg\n"
    "3UmRCdRXbPLuXKgDb9Z/66Vs/aWVfzInq7G1GwhV3McreW4Ixm2WHmVtN4GYF8xq\n"
    "d77BUj3QJwE3N3PkFuL2pX8TM0R87hx4k7zyEwMDT6dWjWmVZBNTG00V+snBT+Wn\n"
    "3Pkwjrg4wyCQmiBRzSzSGqYoqlsBU76X0QcxqzEy+efWq6Ef0pOS4ZymeW6wu5m7\n"
    "JvsdsmOk4mzihoUVRpxKCd4r1axdklw3RN/Uv1KMQ/vG+hsBfMRc3YnuyO4crjbB\n"
    "t3p+h8ZZpr2p3uXy+UBh9nhD6c1u8NVBhzsb2wIDAQABAoIBAEEh6BudeRV0aHKE\n"
    "+Rhb5E8xluWvER+7RviPfrD5QVJJXMCbog+XlC8qHhrD+Tp2yiatxJMevNa+Ktt9\n"
    "Uv/+O63V8FSKPOmf05oV1ok5WTPnGYGZeRol881iWLxViwZMpeXjK7qVKOG0nvDC\n"
    "IKVtiDRYVglo8a2aNYZOTCPYuRF1IQhgCgcDqrk73G9SyC5cPLRyD9BXiSiQmvZi\n"
    "7sPFQ64O2Gz0v5G6Gae82upvEZZXWz7xR9UdmHbG0Y9Tho0CO627bN+2t+jDDBjN\n"
    "FP9JalBxSTOG5AL9UzfoSvWWdGbe1IBPh/X+F9TjpjDXH9nd271ZlRmSuGF6TT1Y\n"
    "isG+mokCgYEAvQqW198iq1VBrWg5+N22R8zCxEomhYNPcmhwN1zJjEAH5IgIC+ZP\n"
    "OMnqkdWPCxiwsKkqtedNaB336mnSAt60ir/y2Mk3bt00dZD63JVg7pVY5XCh9j+F\n"
    "1hdVJv4fXjkvzydgcxw+FWNW8CYPP57zM07tN1kOU2m/TXrC/vQai8kCgYEA1rGa\n"
    "pR6BfzsGvfvZ7Yy6LpUJgHayQOZiDYw2Ux34FLKuSVOc9HHjx/j2ViV0QEgtupCv\n"
    "sk+TpGUohHWK5YHmA2g9ZX1frHb6ePA2NpqJNuEaupcDAtUu3Y+bezTp5GB1IUUi\n"
    "1b1WDj7PjpRYgzfTjAUwv2thG12O5XugSS4a9IMCgYB4d9sQzl2lmbs06oqnEYMr\n"
    "1kz4EdjilH94hR2d6j92ZQeilx2pl6c8pVAah2GUzLMsoWFacoBdrVtjwvPWaF3d\n"
    "Xd1AUVpGCCl6El4LXBZddEcmT9SmvGxptozJQIB05zSUap+IO6NEtf2dJGPrQzvw\n"
    "ooeBEfuTJHyIv4asOpsAIQKBgEI7hFPQN28CzK+rlK2eLonUXJwPAirXaAR57wBx\n"
    "TGlGPlJMwyz+PaEhgw1MfLKgEctue2Vs+0VKF9fVU0Y+brE6ZUZ8CRnxko/guzjZ\n"
    "L9+ITnClyb4D+nNLrFG0HzvfLgNXismZoYS/h9SamzvP6ylVKJbFD64bjMvq+aXZ\n"
    "3WL1AoGBAKtT4oj1EyzCVze3JxJnkzpzOy0fGvEDf+4fVHX+ubnBDvgfQ3ZaTLax\n"
    "5E5bJP6VRlXSsAeCnfGmY+znzD3i6ESXYogAPCxpVjxvQYkyGdD9be0CN75+Fg7Y\n"
    "+pnkkiehpy0B6yrCziomv/WWQfd9GErNwDkbFzS0Teco9YkCYzxG\n"
    "-----END RSA PRIVATE KEY-----"
)

# 1.5.4：注册表别名，便于 ensure_default_keys 用同一个写入路径
DEFAULT_PUB_INFO_TYPE = "__DEFAULT_NODE_PUB__"
DEFAULT_PUB_INFO_OWNER = "__DEFAULT_NODE_PUB__"


class NodeKeyServiceError(Exception):
    """Node key service error."""
    pass


def get_or_init_node_key_service(sensitive_service):
    """1.5.4 helper: 从 sensitive_service 上拿 node_key_service；没有则 lazy-init。

    sensitive_service 上通常没有显式注入 node_key_service 属性（ApiRouter 的
    多个分支都是 `getattr(self.sensitive_service, "node_key_service", None)`，
    永远拿 None）。SealService 1.5.4+ 又必须注入才能支持 free mode unseal。

    调用方统一走这个 helper，避免 4 处复制粘贴 lazy-init 代码。

    Args:
        sensitive_service: SensitiveService 实例（可为 None）

    Returns:
        NodeKeyService 实例；sensitive_service=None 时返回 None
        （调用方自己决定要不要走 fallback 路径）
    """
    if sensitive_service is None:
        return None
    nks = getattr(sensitive_service, "node_key_service", None)
    if nks is not None:
        return nks
    try:
        return NodeKeyService(sensitive_service=sensitive_service)
    except Exception as e:
        logger.warning(
            "get_or_init_node_key_service: lazy init failed: %s", e,
        )
        return None


class NodeKeyService:
    """Service for managing node keys."""

    def __init__(self, sensitive_service=None):
        """
        Initialize NodeKeyService.

        Args:
            sensitive_service: SensitiveService instance for key storage
        """
        self.sensitive_service = sensitive_service
        self._pub_key = None
        self._priv_key = None

    def get_public_key(self) -> Optional[str]:
        """
        Get node public key.

        If not exists, generates new key pair automatically.

        Returns:
            Public key string or None
        """
        if self._pub_key:
            return self._pub_key

        if not self.sensitive_service:
            raise NodeKeyServiceError("SensitiveService not initialized")

        try:
            data = self.sensitive_service.get_sensitive(
                info_type=PUB_KEY_INFO_TYPE,
                info_owner=PUB_KEY_INFO_OWNER
            )
            if data:
                self._pub_key = data[0].get("plain_text", "")
                return self._pub_key
        except Exception as e:
            logger.warning(f"Failed to get public key: {e}")

        return None

    def _generate_and_store(self) -> Tuple[str, str]:
        """Generate new key pair and persist via independent SQL path.

        1.5.2 hotfix P0: All writes go through ``_write_node_credentials``,
        which iterates ``NODE_CREDENTIALS_REGISTRY`` and writes each
        node-owned credential directly via ``database_handler`` —
        bypassing sensitive_service's ``NODE_KEY_WRITE_PROTECTED`` guard.
        This is the only legitimate writer for node credentials.

        1.5.2 hotfix P0 follow-up: exceptions are NO LONGER swallowed
        here. If persistence fails (e.g. SQL schema error, missing
        crypto factor), the exception propagates to the caller so the
        failure is visible — the previous silently-swallowed exception
        masked a schema bug that left the database empty while the
        caller believed generation succeeded.
        """
        from mgc.core.crypto.rsa_crypto import generate_node_keypair

        pub_key, priv_key = generate_node_keypair()

        self._pub_key = pub_key
        self._priv_key = priv_key

        if self.sensitive_service:
            # 注册表驱动：一次写入所有节点身份凭证（pub + priv）。
            # 异常自然上抛——上层（如 api_router）已 try/except NodeKeyServiceError。
            self._write_node_credentials({
                PUB_KEY_INFO_TYPE: pub_key,
                "node_priv":        priv_key,
            })
            logger.info("Node credentials saved via independent SQL paths")

        return pub_key, priv_key

    # ------------------------------------------------------------------ #
    #  注册表驱动的独立 SQL 写入路径（1.5.2 hotfix P0 统一重构）          #
    # ------------------------------------------------------------------ #

    def _write_node_credentials(self, credentials: Dict[str, str]) -> None:
        """Persist every node-owned credential via independent SQL path.

        Args:
            credentials: {info_type: plaintext_value, ...}. Each info_type
                MUST be registered in NODE_CREDENTIALS_REGISTRY, otherwise
                the call is refused with NodeKeyServiceError.
        """
        from mgc.core.mgc_service.node_credentials_registry import (
            node_credential_owner,
        )

        db_handler = getattr(self.sensitive_service, "database_handler", None)
        if db_handler is None:
            raise NodeKeyServiceError("database_handler not available on sensitive_service")

        for info_type, plaintext in credentials.items():
            owner = node_credential_owner(info_type)
            if owner is None:
                raise NodeKeyServiceError(
                    f"Refusing to write unregistered credential '{info_type}'. "
                    f"Add it to NODE_CREDENTIALS_REGISTRY first."
                )
            self._write_one_credential_direct(db_handler, info_type, owner, plaintext)

    def _write_one_credential_direct(self, db_handler, info_type: str, info_owner: str,
                                     plaintext: str) -> None:
        """Insert or update a single node credential via database_handler.

        Bypasses sensitive_service._save_to_mgc_info_1 entirely — this is
        the ONLY legitimate path to write node credentials. Schema
        (info_type / info_owner / diff_* / info_plaintext /
        extract_account / extract_password) matches the real mgc_info_1
        table layout (see init_tables_sqlcipher_single.sql) and aligns
        with sensitive_service._save_to_mgc_info_1.

        1.5.2 hotfix P0 follow-up: the previous version of this method
        mistakenly included ``environment_cipher`` / ``weight_param`` /
        ``salts`` as INSERT columns — those are crypto *factors* (input
        to AES derivation), NOT database columns. The bug caused lazy
        generation via ``ensure_public_key()`` to silently fail
        (logged as ``Failed to execute update``) and is fixed here.
        """
        check_sql = (
            "SELECT id FROM mgc_info_1 "
            "WHERE info_type = ? AND info_owner = ? "
            "AND diff_1 IS NULL AND diff_2 IS NULL AND diff_3 IS NULL"
        )
        existing = db_handler.execute_query(check_sql, (info_type, info_owner))

        cipher_text = self._encrypt_for_storage(plaintext, info_type, info_owner)

        if existing:
            update_sql = (
                "UPDATE mgc_info_1 SET info_plaintext = ? "
                "WHERE info_type = ? AND info_owner = ? "
                "AND diff_1 IS NULL AND diff_2 IS NULL AND diff_3 IS NULL"
            )
            db_handler.execute_update(update_sql, (cipher_text, info_type, info_owner))
        else:
            insert_sql = (
                "INSERT INTO mgc_info_1 "
                "(extract_account, extract_password, info_plaintext, "
                "info_type, info_owner, diff_1, diff_2, diff_3) "
                "VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL)"
            )
            account, password = self.sensitive_service._generate_account_password(
                info_type=info_type, info_owner=info_owner,
                diff_1=None, diff_2=None, diff_3=None,
            )
            db_handler.execute_update(insert_sql, (
                account, password,
                cipher_text,
                info_type, info_owner,
            ))
        logger.info(f"'{info_type}' written via NodeKeyService independent path")

    def _encrypt_for_storage(self, content: str, info_type: str, info_owner: str) -> str:
        """Encrypt arbitrary content for storage, using sensitive_service's crypto.

        Parameterized replacement for the previous hardcoded
        ``_encrypt_pub_key_for_storage`` so the same routine can encrypt
        any node credential regardless of its info_type/info_owner.

        1.5.2 hotfix P1 follow-up: validate crypto factors before passing
        to encrypt_text. Lazy initialization may run before
        ``environment_cipher`` is populated (the cipher is normally read
        from the DB on first access). Encrypting with a None factor would
        either crash deep inside ``generate_info_cipher`` or produce
        unrecoverable ciphertext. Fail fast with a clear error instead.
        """
        env_cipher = self.sensitive_service.environment_cipher
        weight = self.sensitive_service.weight_param
        salts = self.sensitive_service.dynamic_salts
        if env_cipher is None or weight is None or salts is None:
            raise NodeKeyServiceError(
                "NODE_KEY_CRYPTO_FACTORS_UNAVAILABLE: sensitive_service "
                "crypto factors not initialized (environment_cipher / "
                "weight_param / dynamic_salts). Refusing to encrypt "
                f"'{info_type}' — caller must ensure SensitiveService is "
                "fully initialized before invoking NodeKeyService."
            )
        info_fields = {
            "info_type": info_type,
            "info_owner": info_owner,
            "diff_1": None,
            "diff_2": None,
            "diff_3": None,
            "environment_cipher": env_cipher,
            "weight_param": weight,
            "salts": salts,
        }
        return self.sensitive_service.crypto_service.encrypt_text(content, info_fields)

    def ensure_public_key(self) -> str:
        """Return existing node public key, or generate a new keypair.

        Write protection (P0 fix 2026-09-27): generation only happens
        when the node has NO keypair at all (no pub record AND no priv
        record). If node_priv exists but the __NODE_PUB__ record is
        missing/unreadable, refuse to regenerate — a new keypair would
        silently invalidate every sealed script bound to the old key.
        reset_keypair() remains the only explicit overwrite entry.

        1.5.2 hotfix P2 follow-up: also check the INVERSE — if __NODE_PUB__
        exists but node_priv is missing, refuse and surface the
        half-written state. A partial write typically means a previous
        generation crashed mid-loop (e.g. node_priv write failed after
        __NODE_PUB__ succeeded); auto-regenerating would create a new
        keypair that mismatches the existing public key.

        Returns:
            Public key string

        Raises:
            NodeKeyServiceError: when an existing keypair is detected
                but regeneration was requested (write protection hit),
                OR when the persisted credentials are in an inconsistent
                half-written state.
        """
        existing_pub = self.get_public_key()
        existing_priv = self.get_private_key()

        if existing_pub and existing_priv:
            # Both credentials present — fully consistent, return pub.
            return existing_pub

        if existing_pub and not existing_priv:
            # __NODE_PUB__ exists but node_priv is missing — half-written state.
            raise NodeKeyServiceError(
                "NODE_KEY_INCONSISTENT_STATE: __NODE_PUB__ record exists "
                "but node_priv record is missing. This indicates a partial "
                "write from a previous generation. Auto-regenerating would "
                "mismatch the existing public key and invalidate all sealed "
                "scripts. Recovery: run NodeKeyService.reset_keypair() to "
                "delete both records and start fresh, or manually restore "
                "node_priv from backup."
            )

        if not existing_pub and existing_priv:
            # node_priv exists but __NODE_PUB__ is missing/unreadable.
            raise NodeKeyServiceError(
                "NODE_KEY_WRITE_PROTECTED: node_priv exists but __NODE_PUB__ "
                "record is missing or unreadable. Regenerating would "
                "invalidate all sealed scripts bound to the old key. This "
                "usually means a wrong info_owner was used. Correct usage: "
                "mgc_get(info_type='__NODE_PUB__', info_owner='__NODE_PUB__')."
            )

        # Neither exists — first-time generation.
        pub_key, _ = self._generate_and_store()
        return pub_key

    def get_private_key(self) -> Optional[str]:
        """
        Get node private key.

        Returns:
            Private key string or None
        """
        if self._priv_key:
            return self._priv_key

        if not self.sensitive_service:
            raise NodeKeyServiceError("SensitiveService not initialized")

        try:
            data = self.sensitive_service.get_sensitive(
                info_type="node_priv",
                info_owner="SYSTEM"
            )
            if data:
                self._priv_key = data[0].get("plain_text", "")
                return self._priv_key
        except Exception as e:
            logger.warning(f"Failed to get private key: {e}")

        return None

    # --------------------------------------------------------------- #
    #  1.5.4：所有节点共享的固定默认密钥对（free mode 用）             #
    # --------------------------------------------------------------- #

    def ensure_default_keys(self) -> str:
        """确保 SQLCipher 中存在 default_node_pub / default_node_priv。

        1.5.4+ 需求 2.2：所有 1.5.4+ 节点共用同一对 RSA 密钥，
        PEM 在本文件顶部以常量形式硬编码。ensure_default_keys 检查 db：
        已存在则直接返回；不存在则通过 _write_node_credentials 写入。

        与 ensure_public_key 的差异：
        - 本机 keypair 是随机的（generate_node_keypair）；
        - default keypair 是固定的（PEM 常量），不需要生成。

        Returns:
            default_node_pub PEM 字符串

        Raises:
            NodeKeyServiceError: sensitive_service / database_handler 未就绪
        """
        if not self.sensitive_service:
            raise NodeKeyServiceError("SensitiveService not initialized")

        existing = self.get_default_public_key()
        if existing:
            return existing

        # 不存在 → 写入
        self._write_node_credentials({
            DEFAULT_PUB_INFO_TYPE: DEFAULT_NODE_PEM_PUB,
            "default_node_priv":    DEFAULT_NODE_PEM_PRIV,
        })
        logger.info("default_node_credentials initialized via independent SQL path")
        return DEFAULT_NODE_PEM_PUB

    def get_default_public_key(self) -> Optional[str]:
        """从 SQLCipher 取 default_node_pub（PEM）。不存在返回 None。"""
        if not self.sensitive_service:
            return None
        try:
            data = self.sensitive_service.get_sensitive(
                info_type=DEFAULT_PUB_INFO_TYPE,
                info_owner=DEFAULT_PUB_INFO_OWNER,
            )
            if data:
                return data[0].get("plain_text", "") or None
        except Exception as e:
            logger.warning(f"Failed to get default public key: {e}")
        return None

    def get_default_private_key(self) -> Optional[str]:
        """从 SQLCipher 取 default_node_priv（PEM）。不存在返回 None。"""
        if not self.sensitive_service:
            return None
        try:
            data = self.sensitive_service.get_sensitive(
                info_type="default_node_priv",
                info_owner="SYSTEM",
            )
            if data:
                return data[0].get("plain_text", "") or None
        except Exception as e:
            logger.warning(f"Failed to get default private key: {e}")
        return None

    def reset_keypair(self) -> Dict[str, str]:
        """
        Reset keypair (for testing or re-generation).

        Returns:
            Dictionary with new public and private keys
        """
        self._pub_key = None
        self._priv_key = None

        pub_key, priv_key = self._generate_and_store()

        return {
            "public_key": pub_key,
            "private_key": priv_key
        }