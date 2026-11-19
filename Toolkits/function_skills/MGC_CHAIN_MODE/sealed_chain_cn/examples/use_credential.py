#!/usr/bin/env python3
"""use_credential.py — 在密封态安全使用本地 MGC 中的凭证

核心原则：凭证不出域。
  凭证始终留在执行方本地的 MGC 里（info_type=text）。
  本脚本被密封成 .py 后交给执行 agent，运行时通过 MGC REST API 读取凭证，
  用完即弃，只输出结果摘要，不打印也不回传凭证本身。

为什么不能把凭证放进子包：
  MGC chain mode 只加密脚本，CSV/JSON/config 在子包里是明文。
  因此凭证绝不能作为文件下发给对方，只能由对方自行存入本地 MGC。

用法：
  1) 执行方先把自己的凭证存进本地 MGC（仅本机可读）：
     mgc_save(
         info_type="text",
         info_owner="local_credentials",
         diff_2="credential",
         diff_3="api_token.txt",
         content="sk-your-token",
     )

  2) 密封态执行（脚本由 chain mode 子包提供）：
     mgc_run(
         info_type="script",
         info_owner="<包内 info_owner>",
         diff_3="use_credential.py",
         ext02='["--owner","local_credentials","--name","api_token.txt"]',
     )

  3) 本地调试（明文，直接读磁盘文件）：
     python3 use_credential.py --local --token-file ./api_token.txt

零第三方依赖（标准库 urllib）。
"""

import argparse
import hashlib
import hmac
import json
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

MGC = "http://127.0.0.1:57219"
TOKEN_PATH = Path.home() / ".mgc/database/mgc_black_box/.mgc_token"


def _mgc_post(path, payload):
    """调用本地 MGC REST API。"""
    token = TOKEN_PATH.read_text(encoding="utf-8").strip()
    req = Request(
        f"{MGC}{path}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "X-MGC-Token": token,
        },
        method="POST",
    )
    with urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def read_credential_from_mgc(info_owner, diff_2, diff_3):
    """从本地 MGC 读取 text 类型凭证，返回字符串内容。"""
    resp = _mgc_post(
        "/api/mgc/sensitive/get",
        {
            "info_type": "text",
            "info_owner": info_owner,
            "diff_2": diff_2,
            "diff_3": diff_3,
        },
    )
    data = resp.get("data", "")
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        return data.get("content", "")
    raise RuntimeError(f"unexpected data type: {type(data)}")


def fingerprint(secret):
    """凭证指纹：只暴露不可逆短摘要，便于排障又不泄露凭证。"""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:12]


def use_credential(secret, payload):
    """用凭证完成一次签名调用（示例为 HMAC-SHA256，可替换为真实 API 调用）。"""
    signature = hmac.new(
        secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return {
        "ok": True,
        "credential_fingerprint": fingerprint(secret),
        "payload": payload,
        "signature_prefix": signature[:16],
        "signed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }


def main():
    parser = argparse.ArgumentParser(description="在密封态安全使用本地 MGC 凭证")
    parser.add_argument("--owner", default="local_credentials",
                        help="本地 MGC 中凭证的 info_owner")
    parser.add_argument("--diff-2", default="credential",
                        help="本地 MGC 中凭证的 diff_2")
    parser.add_argument("--name", default="api_token.txt",
                        help="本地 MGC 中凭证的 diff_3")
    parser.add_argument("--token-file", default=None,
                        help="本地调试用：直接读取磁盘上的凭证文件")
    parser.add_argument("--local", action="store_true",
                        help="明文调试模式（读磁盘，不访问 MGC）")
    parser.add_argument("--payload", default="demo-task-payload",
                        help="待签名的任务内容")
    parser.add_argument("--output", default=None,
                        help="结果输出路径（默认桌面）")
    args = parser.parse_args()

    if args.local or args.token_file:
        if not args.token_file:
            parser.error("--local 模式需要同时指定 --token-file")
        secret = Path(args.token_file).read_text(encoding="utf-8").strip()
        mode = "local"
    else:
        secret = read_credential_from_mgc(args.owner, args.diff_2, args.name).strip()
        mode = "mgc-rest"

    if not secret:
        raise RuntimeError("credential is empty")

    result = use_credential(secret, args.payload)
    result["mode"] = mode

    out = Path(args.output) if args.output else (Path.home() / "Desktop" / "credential_use_result.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[use_credential] mode={mode} fingerprint={result['credential_fingerprint']} -> {out}",
          file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
