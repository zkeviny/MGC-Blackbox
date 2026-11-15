"""A2A 1.0 协议适配层：MGC 密封包 ⇄ A2A Part / Artifact / Task。

定位（对应主需求二 D5）：
    MGC 自身**不实现** A2A 协议栈。本模块只做一件事——把 MGC 的密封包
    产物映射到 A2A 1.0 的协议结构上，让任意 A2A runtime 能承载并传递。

设计要点：
    - A2A 1.0 的 Part 是 protobuf 类型，承载二进制文件用
      `raw`(bytes) + `filename`(str) + `media_type`(str) 三个字段。
      `.mgc_file` 是 zip（PK 头），直接塞进 raw，无需 base64、无格式转换。
    - node_pub 通过 `Part.metadata`（google.protobuf.Struct）随包传递，
      接收端不需要另开渠道问编排方。
    - 密封子包的 `info_owner` / `diff_2` / `ext09` 等身份字段已写在
      MGCFILE.json 内，接收端导入时以包内容为准，本层不重复传。

依赖：
    a2a-sdk==1.0.3（协议版本 1.0）。SDK 缺失时本模块导入即失败，
    不做静默降级——静默降级会让协议适配问题在生产环境里消失。
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

try:
    from a2a.types import Artifact, Message, Part, Task, TaskState
except ImportError as exc:  # pragma: no cover - 依赖缺失即失败
    raise ImportError(
        "a2a-sdk is required for the A2A protocol bridge. "
        "Install it with: pip install 'a2a-sdk==1.0.3'"
    ) from exc

from google.protobuf.struct_pb2 import Struct, Value

# .mgc_file 是 zip 容器
MEDIA_TYPE_MGC_FILE = "application/vnd.mgc.sealed-package+zip"
MEDIA_TYPE_MARKDOWN = "text/markdown"

# Part.metadata 的键名约定（编排方写、接收端读）
META_INFO_OWNER = "mgc_info_owner"
META_DIFF_1 = "mgc_diff_1"
META_DIFF_2 = "mgc_diff_2"
META_NODE_PUB = "mgc_node_pub"
META_PACKAGE_INDEX = "mgc_package_index"
META_SEAL_MODE = "mgc_seal_mode"
META_FINGERPRINT = "mgc_node_pub_fingerprint"
META_SCHEMA = "mgc_a2a_schema"

# 本适配层使用的 metadata schema 标识。接收端据此判断 Part 是不是 MGC 交付物，
# 而不是靠猜 mime_type（自定义 mime 在不同 runtime 里可能被改写）。
MGC_A2A_SCHEMA = "mgc.sealed-package/v1"


def _struct_to_dict(st: Struct) -> Dict[str, Any]:
    """protobuf Struct → 普通 dict。"""
    from google.protobuf.json_format import MessageToDict

    if not st or not st.fields:
        return {}
    return MessageToDict(st)


def _dict_to_struct(d: Dict[str, Any]) -> Struct:
    """普通 dict → protobuf Struct。"""
    from google.protobuf.json_format import ParseDict

    st = Struct()
    if d:
        ParseDict(d, st)
    return st


def build_package_metadata(
    info_owner: str,
    diff_1: str,
    diff_2: str,
    node_pub: str = "",
    package_index: int = 0,
    seal_mode: str = "chain mode",
    fingerprint: str = "",
) -> Dict[str, Any]:
    """构造 Part.metadata 字典（约定见模块级常量）。"""
    meta: Dict[str, Any] = {META_SCHEMA: MGC_A2A_SCHEMA}
    if info_owner:
        meta[META_INFO_OWNER] = info_owner
    if diff_1:
        meta[META_DIFF_1] = diff_1
    if diff_2:
        meta[META_DIFF_2] = diff_2
    if node_pub:
        meta[META_NODE_PUB] = node_pub
    if package_index:
        meta[META_PACKAGE_INDEX] = package_index
    if seal_mode:
        meta[META_SEAL_MODE] = seal_mode
    if fingerprint:
        meta[META_FINGERPRINT] = fingerprint
    return meta


def mgc_file_to_part(
    mgc_file_path: str,
    filename: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Part:
    """把 .mgc_file 转成 A2A Part（raw 承载原始字节）。

    不做 base64、不做格式转换 —— .mgc_file 本身就是 zip，直接作为
    Part.raw 的载荷，接收端还原后字节完全一致。
    """
    if not os.path.isfile(mgc_file_path):
        raise FileNotFoundError(f"mgc_file not found: {mgc_file_path}")
    with open(mgc_file_path, "rb") as f:
        payload = f.read()
    name = filename or os.path.basename(mgc_file_path)
    part = Part(raw=payload, filename=name, media_type=MEDIA_TYPE_MGC_FILE)
    if metadata:
        part.metadata.CopyFrom(_dict_to_struct(metadata))
    return part


def readme_to_part(
    readme_path: str,
    filename: str = "README.md",
    metadata: Optional[Dict[str, Any]] = None,
) -> Part:
    """把 readme 转成 A2A Part（text 承载）。"""
    if not os.path.isfile(readme_path):
        raise FileNotFoundError(f"readme not found: {readme_path}")
    with open(readme_path, "r", encoding="utf-8") as f:
        text = f.read()
    part = Part(text=text, filename=filename, media_type=MEDIA_TYPE_MARKDOWN)
    if metadata:
        part.metadata.CopyFrom(_dict_to_struct(metadata))
    return part


def build_package_artifact(
    mgc_file_path: str,
    readme_path: str = "",
    filename: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    artifact_id: str = "",
    description: str = "",
) -> Artifact:
    """把一个密封子包封装成 A2A Artifact。

    Artifact.parts = [mgc_file Part, readme Part]
    —— 一个 Artifact 一个节点授权单元，与 chain mode 的「子包 ↔ 目标节点」一一对应。
    """
    parts: List[Part] = [mgc_file_to_part(mgc_file_path, filename, metadata)]
    if readme_path:
        parts.append(readme_to_part(readme_path))
    art = Artifact(
        artifact_id=artifact_id or os.path.basename(mgc_file_path),
        parts=parts,
    )
    if description:
        art.description = description
    return art


def build_delivery_artifacts(
    packages: List[Dict[str, Any]],
    info_owner: str,
    diff_1: str = "",
    diff_2: str = "",
) -> List[Artifact]:
    """把 export_chain_package 返回的 packages 列表整体转成 Artifact 列表。

    packages 里每一项需含：mgc_file_path / readme_path / package_file_name /
    node_pub / node_pub_fingerprint（后两个由 exporter 提供）。
    """
    artifacts: List[Artifact] = []
    for pkg in packages:
        meta = build_package_metadata(
            info_owner=info_owner,
            diff_1=diff_1,
            diff_2=diff_2,
            node_pub=pkg.get("node_pub", ""),
            package_index=int(pkg.get("package_index", 0) or 0),
            seal_mode="chain mode",
            fingerprint=pkg.get("node_pub_fingerprint", ""),
        )
        artifacts.append(
            build_package_artifact(
                mgc_file_path=pkg["mgc_file_path"],
                readme_path=pkg.get("readme_path", ""),
                filename=pkg.get("package_file_name", ""),
                metadata=meta,
                artifact_id=f"mgc-package-{pkg.get('package_index', 0)}",
                description=(
                    f"Sealed package for node "
                    f"{pkg.get('node_pub_fingerprint', 'unknown')}"
                ),
            )
        )
    return artifacts


def build_delivery_task(
    packages: List[Dict[str, Any]],
    info_owner: str,
    diff_1: str = "",
    diff_2: str = "",
    task_id: str = "",
    context_id: str = "",
    instruction: str = "",
) -> Task:
    """把一组子包封装成 A2A Task（一次任务交付）。

    Task.artifacts 承载各节点子包；Task.status.message 里带一条纯文本
    说明（编排指引），让接收方 agent 不必解析 readme 就能知道要干什么。
    """
    artifacts = build_delivery_artifacts(packages, info_owner, diff_1, diff_2)
    text = instruction or (
        f"MGC sealed delivery: {len(artifacts)} package(s) for task "
        f"'{info_owner}/{diff_2}'. Import each .mgc_file with mgc_save_file, "
        f"then run the entry script with mgc_run. Each package is sealed to a "
        f"single target node; only that node can decrypt it."
    )
    status_msg = Message(
        message_id=f"{task_id or 'mgc-delivery'}-instruction",
        context_id=context_id,
        role="ROLE_AGENT",
        parts=[Part(text=text)],
    )
    task = Task(
        id=task_id or f"mgc-delivery-{info_owner}-{diff_2}",
        context_id=context_id,
        artifacts=artifacts,
    )
    # protobuf enum 用数值常量赋值（写字符串会被当成未定义值）
    task.status.state = TaskState.TASK_STATE_INPUT_REQUIRED
    task.status.message.CopyFrom(status_msg)
    return task


def build_agent_card(
    name: str,
    description: str,
    url: str,
    node_pub: str = "",
    fingerprint: str = "",
    skills: Optional[List[Dict[str, Any]]] = None,
    version: str = "1.0.0",
) -> Any:
    """构造 MGC 节点的 A2A AgentCard。

    node_pub 放进 `capabilities.extensions[].uri` —— A2A 规范给扩展位留了
    正式入口，接收端可从 AgentCard 直接拿到本节点公钥，无需另开渠道。
    """
    from a2a.types import (
        AgentCapabilities,
        AgentCard,
        AgentExtension,
        AgentInterface,
        AgentSkill,
    )

    card = AgentCard(
        name=name,
        description=description,
        version=version,
        default_input_modes=["application/vnd.mgc.sealed-package+zip", "text/plain"],
        default_output_modes=["text/plain", "application/vnd.mgc.sealed-package+zip"],
    )
    card.supported_interfaces.append(
        AgentInterface(url=url, protocol_binding="JSONRPC")
    )
    # protobuf 的 message 字段不允许整体赋值，只能 CopyFrom
    card.capabilities.CopyFrom(AgentCapabilities())
    if node_pub:
        ext = AgentExtension(
            uri="urn:mgc:node-pub",
            description=(
                "MGC node public key (PEM). Use as chain-mode ext04 target "
                "to authorize this node to receive sealed packages."
            ),
            params={"node_pub": node_pub, "fingerprint": fingerprint},
        )
        card.capabilities.extensions.append(ext)
    for sk in skills or []:
        card.skills.append(
            AgentSkill(
                id=sk.get("id", "mgc-sealed-delivery"),
                name=sk.get("name", "MGC Sealed Delivery"),
                description=sk.get("description", "Import and execute MGC sealed packages"),
                tags=list(sk.get("tags", ["mgc", "sealed", "chain-mode"])),
                examples=list(sk.get("examples", [])),
                input_modes=list(sk.get("input_modes", ["application/vnd.mgc.sealed-package+zip"])),
                output_modes=list(sk.get("output_modes", ["text/plain"])),
            )
        )
    return card


# ---- 接收侧 ----


def extract_mgc_parts(task: Any) -> List[Dict[str, Any]]:
    """从接收到的 Task / Artifact / Message 里提取 MGC 交付物。

    返回 [{filename, bytes, media_type, metadata}, ...]，
    过滤掉非 MGC 的 Part（靠 metadata 的 schema 标识判定）。
    """
    found: List[Dict[str, Any]] = []

    def _collect_parts(parts) -> None:
        for p in parts:
            meta = _struct_to_dict(p.metadata)
            if meta.get(META_SCHEMA) != MGC_A2A_SCHEMA:
                continue
            if p.raw:
                found.append({
                    "filename": p.filename,
                    "bytes": p.raw,
                    "media_type": p.media_type,
                    "metadata": meta,
                })

    def _collect_artifacts(artifacts) -> None:
        for art in artifacts:
            _collect_parts(art.parts)

    if hasattr(task, "artifacts"):
        _collect_artifacts(task.artifacts)
    if hasattr(task, "history"):
        for msg in task.history:
            _collect_parts(msg.parts)
    if hasattr(task, "parts"):
        _collect_parts(task.parts)
    return found


def persist_mgc_parts(
    parts: List[Dict[str, Any]],
    output_dir: str,
) -> List[str]:
    """把提取出的 Part 落盘成文件，返回落盘路径列表。

    落盘的是**密文容器**（.mgc_file 本身已是密文 zip），不是明文，
    因此中间落盘不破坏「磁盘上无明文」的安全属性。
    """
    os.makedirs(output_dir, exist_ok=True)
    paths: List[str] = []
    for item in parts:
        name = item.get("filename") or "package.mgc_file"
        target = os.path.join(output_dir, name)
        with open(target, "wb") as f:
            f.write(item["bytes"])
        paths.append(target)
    return paths
