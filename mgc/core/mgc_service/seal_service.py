"""Script seal service for external node execution.

Provides script sealing for P2P (point-to-point) execution authorization.

1.5.4 update:
- seal_script 始终走双层加密：
  1) RSA(target_or_default_pub, aes_key_4) → rsa_cipher
  2) AES-GCM(SHA256(source_node_pub)[:32], rsa_cipher, aad=mode) → ext03
- 1.0 老 sealed 包（ext09=""）走旁路：直接 RSA(node_priv, ext03) → aes_key_4。
"""

import logging
from typing import Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)

# 1.5.4：ext09 取值常量
EXT09_P2P   = "p2p mode"     # PM 决策 2.1：用对方 node_pub 包 AES_KEY_4
EXT09_FREE  = "free mode"    # PM 决策 2.2：用 default_node_pub 包（任何 mgc 可解）
EXT09_CHAIN = "chain mode"   # 1.6.0：按 target 拆包，每包用目标节点 node_pub 包裹


def _read_sealed_ext(data: Optional[Dict[str, Any]], key: str) -> str:
    """Read a sealed ext field, accepting the 1.5.4 unprefixed key (`ext03`)
    and the legacy underscored alias (`ext_03`) for backward compatibility
    with payloads persisted before the rename.

    Args:
        data: The sealed payload dict (or None).
        key: The 1.5.4 key name, e.g. "ext01" / "ext03" / "ext07" / "ext09".

    Returns:
        The field value as a string, or "" if neither key is present.
    """
    if not data:
        return ""
    if key in data and data[key]:
        return data[key]
    # Legacy alias: insert underscore after the 4th character ("ext" prefix).
    legacy = "ext_" + key[3:]
    return data.get(legacy, "") or ""


class SealServiceError(Exception):
    """Seal service error."""
    pass


class SealService:
    """Service for sealing scripts to external nodes."""

    def __init__(self, sensitive_service=None, node_key_service=None):
        """
        Initialize SealService.

        Args:
            sensitive_service: SensitiveService for content storage
            node_key_service: NodeKeyService for key operations
        """
        self.sensitive_service = sensitive_service
        self.node_key_service = node_key_service
        # 1.5.4：free mode 用的共享默认公钥（懒缓存）
        self._default_node_pub_cache: Optional[str] = None

    def _get_default_node_pub(self) -> str:
        """取 default_node_pub PEM（free mode 用）。懒加载缓存。

        Returns:
            PEM 字符串

        Raises:
            SealServiceError: 没有 sensitive_service / db 不可用
        """
        if self._default_node_pub_cache:
            return self._default_node_pub_cache
        if not self.node_key_service:
            raise SealServiceError(
                "SealService: node_key_service is required for free mode"
            )
        try:
            pub = self.node_key_service.get_default_public_key()
            if not pub:
                # 1.5.4：首次 seal free mode 时主动 ensure_default_keys
                pub = self.node_key_service.ensure_default_keys()
            self._default_node_pub_cache = pub
            return pub
        except Exception as e:
            raise SealServiceError(
                f"Failed to load default_node_pub: {e}"
            ) from e
    
    def seal_script(
        self,
        content: str,
        out_node_pub: str = "",
        mode: str = EXT09_P2P,
        source_node_pub: str = "",
    ) -> Dict[str, Any]:
        """
        Seal script for external node. 1.5.4+ always uses double-layer encryption.

        Flow:
            1. Generate one-time AES_KEY_4
            2. Encrypt content with AES_KEY_4 (existing path)
            3. Pick RSA wrapping pub:
               - mode == EXT09_P2P  → use out_node_pub (must be non-empty)
               - mode == EXT09_FREE → use shared default_node_pub
               - mode == EXT09_CHAIN → use out_node_pub (该 target 节点的 node_pub)
            4. RSA-wrap aes_key_4 → rsa_cipher
            5. AES-256-GCM wrap rsa_cipher with key = SHA256(source_node_pub)[:32],
               AAD = mode (string bytes) → ext03
            6. Return content + ext03 + ext07 (= source_node_pub) + ext09 (= mode)

        Args:
            content: Plain text script to seal
            out_node_pub: 目标节点 PEM 公钥；p2p / chain mode 必传，free mode 可为空
            mode: EXT09_P2P / EXT09_FREE / EXT09_CHAIN
            source_node_pub: 授权方（调用方自己）node_pub PEM，**必传**

        Returns:
            Dictionary:
            {
                "content": "AES encrypted script",
                "ext01": "",
                "ext03": "AES-GCM(rsa_cipher, key=SHA256(source_node_pub)[:32], aad=mode)",
                "ext07": source_node_pub,
                "ext09": mode
            }

        Raises:
            SealServiceError: source_node_pub 为空 / out_node_pub 缺失(p2p, chain) / 加密失败
        """
        if not content:
            raise SealServiceError("Content cannot be empty")

        # PM 决策：1.5.4+ 默认所有密封都必须 ext07 鉴权，source_node_pub 为空直接报错
        if not source_node_pub:
            raise SealServiceError(
                "source_node_pub is required since mgc 1.5.4: every sealed "
                "script must be authorized by the source node's public key "
                "(used as the outer AES-GCM wrap key for ext03). "
                "Hint: mgc_get(info_type='__NODE_PUB__', info_owner='__NODE_PUB__') "
                "to fetch your own node_pub and pass it as source_node_pub."
            )

        if mode == EXT09_P2P:
            if not out_node_pub:
                raise SealServiceError(
                    "out_node_pub is required for p2p mode (target node's public key)"
                )
            wrap_pub = out_node_pub
        elif mode == EXT09_FREE:
            # free mode: 用共享默认公钥
            wrap_pub = self._get_default_node_pub()
        elif mode == EXT09_CHAIN:
            # 1.6.0 chain mode: 与 p2p 同构——用**该 target 节点**的 node_pub 包裹 AES key。
            # 加密路径 / AAD 规则完全不变，仅 mode token 不同（aad = b"chain mode"），
            # 与写入 record 的 ext09 一致，unseal 侧无需任何改动。
            if not out_node_pub:
                raise SealServiceError(
                    "out_node_pub is required for chain mode (target node's public key)"
                )
            wrap_pub = out_node_pub
        else:
            raise SealServiceError(
                f"Unknown mode {mode!r}; expected {EXT09_P2P!r}, "
                f"{EXT09_FREE!r} or {EXT09_CHAIN!r}"
            )

        try:
            from mgc.domain.crypto_layer.aes_key_n import generate_aes_key_4, encrypt_with_aes_key_4
            from mgc.core.crypto.rsa_crypto import encrypt_with_node_pub
            from mgc.domain.crypto_layer.aes_gcm_wrap import (
                aes_256_gcm_wrap,
                derive_key_from_node_pub_canonical,
            )

            aes_key = generate_aes_key_4()
            encrypted_content, _ = encrypt_with_aes_key_4(content, aes_key)
            # rsa_crypto 返回 base64 str，AES-GCM wrap 直接接收 str（内部 utf-8 encode）
            rsa_cipher_str = encrypt_with_node_pub(aes_key, wrap_pub)
            outer_key = derive_key_from_node_pub_canonical(source_node_pub)
            ext03 = aes_256_gcm_wrap(
                rsa_cipher_str,
                outer_key,
                aad=mode.encode("utf-8"),
            )

            return {
                "content": encrypted_content,
                "ext01": "",
                "ext03": ext03,
                # 1.5.4：新增字段（输出字段名统一无下划线，与 mgc_save / 存储层一致）
                "ext07": source_node_pub,
                "ext09": mode,
            }
        except SealServiceError:
            raise
        except ValueError as ve:
            # Most common cause: PEM key missing newlines (single-line vs multi-line).
            err = str(ve)
            if "PEM" in err or "pre boundary" in err or "boundary" in err:
                raise SealServiceError(
                    "Invalid PEM public key format: the key must be a multi-line PEM "
                    "with REAL newline characters between the header, each base64 line, "
                    "and the footer. Got: '" + err + "'. "
                    "Hint: use mgc_get(info_type='__NODE_PUB__') to fetch the canonical "
                    "multi-line PEM and pass it verbatim."
                )
            raise SealServiceError(f"Seal failed: {ve}")
        except Exception as e:
            raise SealServiceError(f"Seal failed: {e}")
    
    def unseal_script(self, sealed_data: Dict[str, Any]) -> str:
        """
        Unseal and decrypt script for execution. 1.5.4+ supports double-layer.

        Flow (1.5.4+, ext09 非空):
            1. 选 RSA priv_key：本机 node_priv 或 default_node_priv
               （mode == free 用 default_node_priv，否则用本机 node_priv）
            2. AES-GCM unwrap ext03 (key=SHA256(ext07)[:32], aad=mode) → rsa_cipher
            3. RSA(node_priv, rsa_cipher) → aes_key_4
            4. AES_decrypt(content, aes_key_4) → plain text

        Flow (1.0 legacy, ext09 == ""):
            直接 RSA(node_priv, ext03) → aes_key_4 → AES_decrypt(content)

        Args:
            sealed_data: Dictionary with content, ext01, ext03, ext07, ext09

        Returns:
            Decrypted plain text script

        Raises:
            SealServiceError: ext07 / ext09 缺失 / AES-GCM tag 失配 / RSA / AES 失败
        """
        content = sealed_data.get("content", "")
        encrypted_key = _read_sealed_ext(sealed_data, "ext03")
        ext07 = _read_sealed_ext(sealed_data, "ext07")
        ext09 = _read_sealed_ext(sealed_data, "ext09")

        if not content or not encrypted_key:
            raise SealServiceError("Invalid sealed data: missing content or ext03")

        # === 老 sealed 包（1.0~1.5.3）：ext09="" 走旁路 ===
        if not ext09:
            try:
                from mgc.core.crypto.rsa_crypto import decrypt_with_node_priv
                priv_key = self._get_priv_key()
                aes_key = decrypt_with_node_priv(encrypted_key, priv_key)
                return self._decrypt_aes(encrypted_key, content, aes_key)
            except Exception as e:
                raise SealServiceError(f"Unseal failed (legacy path): {e}")

        # === 1.5.4+ 双层解密路径 ===
        if not ext07:
            raise SealServiceError(
                "Invalid sealed data: ext09 is non-empty (1.5.4+) but ext07 is "
                "missing. Source node public key (ext07) is required; verify "
                "the package was sealed by a trusted source."
            )

        try:
            from mgc.core.crypto.rsa_crypto import decrypt_with_node_priv
            from mgc.domain.crypto_layer.aes_gcm_wrap import (
                aes_256_gcm_unwrap,
                derive_key_from_node_pub,
                derive_key_from_node_pub_canonical,
            )

            # 选 RSA priv_key
            if ext09 == EXT09_FREE:
                # free mode: 用 default_node_priv
                if not self.node_key_service:
                    raise SealServiceError(
                        "SealService: node_key_service required for free mode unseal"
                    )
                priv_key = self.node_key_service.get_default_private_key()
                if not priv_key:
                    priv_key = self.node_key_service.ensure_default_keys()  # 触发 ensure
                    priv_key = self.node_key_service.get_default_private_key()
                if not priv_key:
                    raise SealServiceError(
                        "default_node_priv not available; cannot unseal free mode"
                    )
            else:
                # p2p mode (默认): 用本机 node_priv
                priv_key = self._get_priv_key()

            # 1) AES-GCM 解外层 → rsa_cipher
            # 归一化 key 优先（跨平台稳定）；失败回退原始字节 hash（兼容 1.5.4 已存包）。
            try:
                rsa_cipher = aes_256_gcm_unwrap(
                    encrypted_key,
                    derive_key_from_node_pub_canonical(ext07),
                    aad=ext09.encode("utf-8"),
                )
            except Exception:
                rsa_cipher = aes_256_gcm_unwrap(
                    encrypted_key,
                    derive_key_from_node_pub(ext07),
                    aad=ext09.encode("utf-8"),
                )

            # 2) RSA 解内层 → aes_key_4
            # aes_256_gcm_unwrap 已返回 str（utf-8 decode），直接喂给 rsa_crypto
            aes_key = decrypt_with_node_priv(rsa_cipher, priv_key)

            # 3) AES 解密文
            return self._decrypt_aes(encrypted_key, content, aes_key)
        except SealServiceError:
            raise
        except Exception as e:
            raise SealServiceError(
                f"Double-layer unseal failed: {e}"
            ) from e

    def _get_priv_key(self) -> str:
        """从 node_key_service 或 sensitive_service（SYSTEM/node_priv）取本机 RSA 私钥。

        供 unseal_script 与 unseal_and_run 共用，避免两处各自硬编码/重复实现。
        返回空字符串时由调用方决定是否抛 Private key not found 异常。
        """
        priv_key = ""
        if self.node_key_service:
            priv_key = self.node_key_service.get_private_key()
        elif self.sensitive_service:
            priv_data = self.sensitive_service.get_sensitive(
                info_type="node_priv",
                info_owner="SYSTEM"
            )
            if priv_data:
                priv_key = priv_data[0].get("plain_text", "")
        return priv_key
    
    def _decrypt_aes(self, encrypted_key: str, content: str, aes_key: str) -> str:
        """Internal AES decryption helper."""
        from mgc.domain.crypto_layer.aes_key_n import decrypt_with_aes_key_4
        return decrypt_with_aes_key_4(content, aes_key)
    
    def unseal_and_run(self, sealed_data: Dict[str, Any]) -> Tuple[str, str, str]:
        """
        Unseal and prepare script for execution.

        Detects if data is sealed (has ext03) and decrypts if needed.
        1.5.4+：若 ext09 非空，调用 unseal_script 走双层解密路径。
        """
        content = sealed_data.get("content", "")
        ext01 = _read_sealed_ext(sealed_data, "ext01")
        ext03 = _read_sealed_ext(sealed_data, "ext03")

        if not ext03:
            return content, ext01, ""

        # 1.5.4：双层入口交给 unseal_script（含老路径旁路）
        try:
            decrypted_content = self.unseal_script(sealed_data)
            return decrypted_content, ext01, ext03
        except Exception as e:
            raise SealServiceError(f"Sealed script decryption failed: {e}")