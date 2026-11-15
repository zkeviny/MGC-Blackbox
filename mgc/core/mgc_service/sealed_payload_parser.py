"""密封胶囊解析与落盘工具。

WebUI / MCP / API 三条存入入口共用同一套解析规则，避免各路径行为漂移。

判定为密封胶囊需同时满足：
  1. content 能被 json.loads 解析为 dict
  2. 含 ext03（密封 key），兼容 1.5.4 之前的 ext_03 写法
  3. 含 content 字段且是 base64 密文形态

合并优先级：info_owner 由调用方显式指定时保留调用方的值，
其余字段一律以胶囊内容为准。
"""

import json
import re
from datetime import datetime
from pathlib import Path

# base64 密文形态：纯 base64 字符且长度 ≥ 100，与 WebUI 侧历史判定保持一致
_BASE64_BLOB = re.compile(r"^[A-Za-z0-9+/=]{100,}$")

# Windows 保留字符（Mac 文件系统对 ':' 同样受限，Linux 仅禁 '/'，取并集）
_WIN_RESERVED_CHARS = r'<>:"/\\|?*'

# Windows 保留设备名
_WIN_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

_IDENTITY_FIELDS = ("info_type", "info_owner", "diff_1", "diff_2", "diff_3")

# ext 字段回显白名单（存入成功后需告知调用方的元数据）
_STORED_META_EXT = (1, 2, 3, 5, 6, 7, 9)


def parse_sealed_payload(content):
    """识别密封胶囊 JSON。

    返回规范化字段字典；内容不是密封胶囊时返回 None。
    """
    if not content or not isinstance(content, str):
        return None
    stripped = content.strip()
    if not stripped.startswith("{"):
        return None
    try:
        data = json.loads(stripped)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None

    ext03 = data.get("ext03") or data.get("ext_03") or ""
    body = data.get("content") or ""
    if not isinstance(ext03, str) or not ext03:
        return None
    if not isinstance(body, str) or not _BASE64_BLOB.match(body):
        return None

    parsed = {
        "info_type": data.get("info_type") or data.get("type") or "script",
        "info_owner": data.get("info_owner") or data.get("owner") or "",
        "diff_1": data.get("diff_1") or "",
        "diff_2": data.get("diff_2") or "",
        "diff_3": data.get("diff_3") or "",
        "content": body,
    }
    for i in range(1, 31):
        key = f"ext{i:02d}"
        parsed[key] = data.get(key) or data.get(f"ext_{i:02d}") or ""
    return parsed


def resolve_owner(capsule_owner, request):
    """决定最终使用的 info_owner。

    info_owner 在 save 请求里是必填项，调用方总会显式传值（可能为空串），
    因此用 model_fields_set 判断"是否由调用方指定"，而不是看值是否非空。
    """
    fields_set = getattr(request, "model_fields_set", None)
    explicitly_set = "info_owner" in fields_set if fields_set is not None else False
    if explicitly_set and str(getattr(request, "info_owner", "") or "").strip():
        return getattr(request, "info_owner")
    return capsule_owner or getattr(request, "info_owner", "") or ""


def apply_sealed_payload(request, parsed):
    """把胶囊解析结果写入 save 请求对象（原地修改）。"""
    request.content = parsed["content"]
    request.info_type = parsed["info_type"]
    request.info_owner = resolve_owner(parsed["info_owner"], request)
    request.diff_1 = parsed["diff_1"]
    request.diff_2 = parsed["diff_2"]
    request.diff_3 = parsed["diff_3"]
    for i in range(1, 31):
        key = f"ext{i:02d}"
        if parsed.get(key):
            setattr(request, key, parsed[key])


def build_stored_meta(request):
    """存入成功后回显给调用方的元数据（identity 类 + 关键 ext 类）。"""
    meta = {field: getattr(request, field, "") or "" for field in _IDENTITY_FIELDS}
    for i in _STORED_META_EXT:
        meta[f"ext{i:02d}"] = getattr(request, f"ext{i:02d}", "") or ""
    return meta


def sanitize_path_segment(value, fallback="capsule", max_len=64):
    """把任意字符串清洗成跨 Mac / Windows / Linux 安全的单个路径段。

    Windows 禁用 <>:"/\\|?* 且保留 CON / PRN / AUX / NUL / COM1-9 / LPT1-9，
    不允许目录名以点或空格结尾。

    1.6.0 抽出：chain mode 的主文件夹名与子包 .mgc_file 文件名复用本规则，
    保证跨平台一致（Q4：只要能够区分且跨平台无问题即可）。

    Args:
        value: 原始字符串（info_owner / diff_2 等）
        fallback: 清洗后为空时使用的占位值
        max_len: 清洗后的最大长度

    Returns:
        安全的路径段字符串
    """
    slug = re.sub(f"[{_WIN_RESERVED_CHARS}\\x00-\\x1f]", "_", str(value or ""))
    slug = slug.strip(". ") or fallback
    if slug.upper() in _WIN_RESERVED_NAMES:
        slug = f"_{slug}"
    slug = slug[:max_len].rstrip(". ") or fallback
    return slug


def collapse_underscores(value):
    """把连续两个及以上的下划线归一为单个下划线。

    1.6.0 chain mode：<owner>__<diff_2>__<序号> 用双下划线做分隔符，
    若段内本身含连续下划线会造成切分歧义，故先归一。
    """
    return re.sub(r"_{2,}", "_", str(value or ""))


def build_capsule_dirname(info_owner, timestamp=None):
    """生成跨 Mac / Windows / Linux 安全的胶囊目录名。

    Windows 禁用 <>:"/\\|?* 且保留 CON / PRN / AUX / NUL / COM1-9 / LPT1-9，
    不允许目录名以点或空格结尾，路径总长上限 260。
    """
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = sanitize_path_segment(info_owner)
    return f"{slug}_{timestamp}"


def write_capsule_json(output_dir, info_owner, payload, timestamp=None):
    """把密封胶囊写到 output_dir 下的时间戳子目录，返回落盘路径。

    强制 UTF-8 + LF，避免 Windows 把 \\n 翻译成 \\r\\n 后跨设备内容不一致。
    目录已存在时直接报错，绝不覆盖已有产物。
    """
    root = Path(output_dir).expanduser().resolve()
    capsule_dir = root / build_capsule_dirname(info_owner, timestamp)
    capsule_dir.mkdir(parents=True, exist_ok=False)

    capsule_path = capsule_dir / "sealed_capsule.json"
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with open(capsule_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return capsule_path


def build_capsule_payload(row, sealed):
    """组装落盘用的胶囊内容：identity 类 + diff 类 + ext 类 + content。

    row 为源记录，sealed 为 seal_script() 的输出。除 content（密文）外
    全部原样透传，不做归一化。空值字段一律省略——胶囊里只保留实际有值的
    字段，避免 30 个空 extNN 干扰调用方和人工阅读。
    """
    payload = {}
    for field in _IDENTITY_FIELDS:
        value = row.get(field, "") or ""
        if value:
            payload[field] = value
    payload.setdefault("info_type", "script")

    for i in range(1, 31):
        key = f"ext{i:02d}"
        value = sealed.get(key) or row.get(key, "") or ""
        if value:
            payload[key] = value

    payload["content"] = sealed.get("content", "")
    return payload


def resolve_output_dir(output_dir):
    """校验并规范化调用方传入的落盘目录。不做桌面兜底——路径必须显式指定。"""
    if not output_dir or not str(output_dir).strip():
        raise ValueError(
            "output_dir is required: pass an absolute directory to write the sealed "
            "capsule into. There is no desktop fallback because the location differs "
            "across platforms."
        )
    return Path(str(output_dir)).expanduser()


def current_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_writable_dir(path):
    """确保目录可创建，失败时给出可定位的错误信息。"""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise OSError(
            f"Cannot create output directory '{path}': {e}. "
            f"Check the path exists and is writable."
        ) from e
    return path