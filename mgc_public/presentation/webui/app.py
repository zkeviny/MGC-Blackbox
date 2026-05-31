"""
MGC WebUI FastAPI Application

用途：
- 初始化安装页面
- 根密钥录入
- 安装进度
- SKILL 文档展示
"""

import sys
import os
import asyncio
import shutil
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


class StartInstallRequest(BaseModel):
    mode: str


import mgc
from mgc.presentation.interaction.base_dialog import BaseDialog

MGC_ROOT = os.path.dirname(os.path.abspath(mgc.__file__))
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)
if not os.path.exists(TEMPLATES_DIR):
    os.makedirs(TEMPLATES_DIR)

app = FastAPI(title="MGC Blackbox")
import logging
logger = logging.getLogger("MirginCipher")
logger.debug(f"app.py loaded, app id = {id(app)}, initial state.token = {getattr(app.state, 'token', 'NOT_SET')}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

install_state = {
    "mode": None,
    "personal_key": None,
    "weight_param": None,
    "db_path": None,
    "step": "install",
    "stop_requested": False,
}

stop_event = None
_stop_server = None


def set_stop_callback(callback):
    global stop_event, _stop_server
    stop_event = callback


def set_server_control(stop_server_func):
    global _stop_server
    _stop_server = stop_server_func


class RootKeyRequest(BaseModel):
    personal_key: str
    weight_param: str
    db_path: Optional[str] = None


def _is_initialized() -> bool:
    """检查 MGC 主服务端口是否在监听"""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        result = sock.connect_ex(('127.0.0.1', 57219))
        return result == 0
    finally:
        sock.close()


@app.get("/", response_class=HTMLResponse)
async def root():
    if _is_initialized():
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/skill")
    return await load_template("install.html")


@app.get("/root-key", response_class=HTMLResponse)
async def root_key_page():
    if _is_initialized():
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/skill")
    return await load_template("root_key.html")


@app.get("/installing", response_class=HTMLResponse)
async def installing_page():
    if _is_initialized():
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/skill")
    return await load_template("installing.html")


@app.get("/skill", response_class=HTMLResponse)
async def skill_page():
    return await load_template("skill.html")


@app.get("/save", response_class=HTMLResponse)
async def save_page():
    from mgc.config.user_settings import get_protection_mode
    if get_protection_mode():
        return RedirectResponse(url="/skill?blocked=save")
    return await load_template("save.html")


@app.get("/get", response_class=HTMLResponse)
async def get_page():
    from mgc.config.user_settings import get_protection_mode
    if get_protection_mode():
        return RedirectResponse(url="/skill?blocked=get")
    return await load_template("get.html")


@app.get("/get_info", response_class=HTMLResponse)
async def get_info_page():
    return await load_template("get_info.html")

@app.get("/get_sealed_info", response_class=HTMLResponse)
async def get_sealed_info_page():
    return await load_template("get_sealed_info.html")


@app.get("/root-key-change", response_class=HTMLResponse)
async def root_key_change_page():
    return await load_template("root_key_change.html")


@app.get("/api/install/status")
async def get_install_status():
    return {
        "step": install_state["step"],
        "mode": install_state["mode"],
    }


@app.get("/api/token")
async def get_token(request: Request):
    token = getattr(request.app.state, 'token', None)
    logger.debug(f"/api/token called, app.state.token = {token[:20] if token else 'None'}...")
    if not token:
        logger.warning("app.state.token is None or missing")
    return PlainTextResponse(token or "")


@app.get("/api/protection_mode")
async def get_protection_mode():
    from mgc.config.user_settings import get_protection_mode
    return {"protection_mode": get_protection_mode()}


@app.post("/api/install/start")
async def start_install(data: StartInstallRequest):
    mode = data.mode
    if mode not in ["new_install", "reload"]:
        raise HTTPException(status_code=400, detail="Invalid mode")
    install_state["mode"] = mode
    install_state["step"] = "root_key"
    return {"status": "ok", "redirect": "/root-key"}


@app.post("/api/install/root-key")
async def submit_root_key(data: RootKeyRequest):
    if not data.personal_key or not data.weight_param:
        raise HTTPException(status_code=400, detail="Personal key and weight required")

    if len(data.weight_param) != 1 or not data.weight_param.isdigit():
        raise HTTPException(status_code=400, detail="Weight must be single digit 1-9")

    install_state["personal_key"] = data.personal_key
    install_state["weight_param"] = data.weight_param
    install_state["db_path"] = data.db_path

    if data.db_path and install_state["mode"] == "reload":
        from mgc.config.path_config import DB_DIR
        target_db = DB_DIR / "mgc_black_box.db"
        if os.path.exists(data.db_path) and data.db_path != str(target_db):
            os.makedirs(os.path.dirname(target_db), exist_ok=True)
            shutil.copy2(data.db_path, target_db)

    install_state["step"] = "installing"

    result = await do_install(data.personal_key, data.weight_param)

    if result["status"] == "success":
        try:
            from mgc.presentation.interaction.webui_dialog import set_webui_result
            set_webui_result({
                "personal_key": data.personal_key,
                "weight_param": data.weight_param,
                "db_path": data.db_path,
                "result": BaseDialog.RESULT_NEW_INSTALL if install_state["mode"] == "new_install" else BaseDialog.RESULT_MIGRATE
            })
        except ImportError:
            pass
        install_state["step"] = "installing"
        return {"status": "ok", "redirect": "/installing"}
    else:
        return {"status": "error", "message": "Root key error, please try again."}


async def do_install(personal_key: str, weight_param: str):
    try:
        from mgc.key_storage import db_key_manager
        from mgc.core.database.sqlcipher_handler import SQLCipherHandler
        from mgc.domain.crypto_layer.root_key_crypto import get_aes_key_2

        aes_key_2 = get_aes_key_2(personal_key, weight_param)
        SQLCipherHandler.set_aes_key_2(aes_key_2)
        db_key_manager.save(personal_key, weight_param)

        from mgc.core.mgc_service.root_key_change_service import RootKeyChangeService
        from mgc.core.mgc_service.database.database_handler import DatabaseHandler
        db_handler = DatabaseHandler()
        service = RootKeyChangeService(db_handler)
        service.verify_old_key(personal_key, weight_param)

        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/install/cancel")
async def cancel_install():
    install_state.clear()
    install_state["step"] = "install"
    return {"status": "ok"}


class RootKeyVerifyRequest(BaseModel):
    personal_key: str
    weight_param: str


class RootKeyChangeRequest(BaseModel):
    old_personal_key: str
    old_weight_param: str
    new_personal_key: str
    new_weight_param: str


@app.post("/api/root-key/verify")
async def verify_root_key(data: RootKeyVerifyRequest):
    try:
        from mgc.core.mgc_service.root_key_change_service import RootKeyChangeService
        from mgc.core.mgc_service.database.database_handler import DatabaseHandler

        db_handler = DatabaseHandler()
        service = RootKeyChangeService(db_handler)

        service.verify_old_key(data.personal_key, data.weight_param)

        return {"status": "success", "message": "Verification successful"}
    except Exception as e:
        return {"status": "failed", "message": str(e)}


@app.post("/api/root-key/change")
async def change_root_key(data: RootKeyChangeRequest):
    try:
        from mgc.core.mgc_service.root_key_change_service import RootKeyChangeService
        from mgc.core.mgc_service.database.database_handler import DatabaseHandler

        db_handler = DatabaseHandler()
        service = RootKeyChangeService(db_handler)

        service.change_root_key(
            data.old_personal_key,
            data.old_weight_param,
            data.new_personal_key,
            data.new_weight_param
        )

        return {"status": "success", "message": "Root key changed successfully"}
    except Exception as e:
        return {"status": "failed", "message": str(e)}


class DbAuditKeyRequest(BaseModel):
    personal_key: str
    weight_param: str


@app.post("/api/db-audit/key")
async def get_db_audit_key(data: DbAuditKeyRequest):
    """
    Get database audit key (AES_KEY_2 or AES_KEY_2+AES_KEY_1)

    This endpoint:
    1. Verifies the provided root key
    2. Decrypts DB_KEY.json to retrieve AES_KEY_2
    3. If protection_mode is enabled, appends AES_KEY_1
    4. Returns the key for database audit purposes
    """
    try:
        from mgc.core.mgc_service.root_key_change_service import RootKeyChangeService
        from mgc.core.mgc_service.database.database_handler import DatabaseHandler
        from mgc.key_storage.db_key_manager import load as load_db_key
        from mgc.config.user_settings import get_protection_mode
        from mgc.domain.crypto_layer.root_key_crypto import get_aes_key_1

        db_handler = DatabaseHandler()
        service = RootKeyChangeService(db_handler)

        service.verify_old_key(data.personal_key, data.weight_param)

        db_key = load_db_key()

        if get_protection_mode():
            aes_key_1 = get_aes_key_1()
            db_key = db_key + aes_key_1

        return {"status": "success", "db_key": db_key}
    except Exception as e:
        return {"status": "failed", "message": str(e)}


@app.get("/api/skill/download")
async def download_skill():
    skill_path = os.path.join(MGC_ROOT, "docs", "skill_spec.md")
    if os.path.exists(skill_path):
        return FileResponse(skill_path, media_type="text/markdown", filename="mgc_skill.md")
    raise HTTPException(status_code=404, detail="Skill file not found")


@app.get("/api/skill/content")
async def get_skill_content():
    """获取 skill 内容"""
    from fastapi.responses import PlainTextResponse
    try:
        skill_path = os.path.join(MGC_ROOT, "docs", "skill_spec.md")
        if os.path.exists(skill_path):
            with open(skill_path, "r", encoding="utf-8") as f:
                return PlainTextResponse(f.read(), media_type="text/markdown")
        return PlainTextResponse("Skill file not found", media_type="text/markdown")
    except Exception:
        return PlainTextResponse("Skill file not found", media_type="text/markdown")


@app.get("/api/mcp_config/content")
async def get_mcp_config_content():
    """获取 mcp_config.json 内容"""
    from fastapi.responses import PlainTextResponse
    try:
        from mgc.config.path_config import SKILLS_DIR
        config_file = SKILLS_DIR / "mcp_config.json"
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                return PlainTextResponse(f.read(), media_type="application/json")
        return PlainTextResponse('{"error": "mcp_config.json not found"}', media_type="application/json")
    except Exception:
        return PlainTextResponse('{"error": "Failed to read mcp_config.json"}', media_type="application/json")


@app.get("/api/install/notice")
async def get_notice():
    from fastapi.responses import PlainTextResponse
    notice_path = os.path.join(MGC_ROOT, "config", "user_notice.txt")
    try:
        with open(notice_path, "r", encoding="utf-8") as f:
            content = f.read()
        return PlainTextResponse(content=content, media_type="text/plain; charset=utf-8")
    except Exception:
        return PlainTextResponse(content="Security Notice", media_type="text/plain; charset=utf-8")


@app.post("/api/service/stop")
async def stop_service():
    install_state["stop_requested"] = True
    if stop_event:
        stop_event.set()
    return {"status": "ok"}


@app.get("/api/mgc/status")
async def get_mgc_status():
    if install_state["step"] == "installing" and not install_state.get("stop_requested"):
        return {"data": {"status": "running"}}
    return {"data": {"status": "stopped"}}


@app.get("/api/mgc/proxy/status")
async def proxy_mgc_status():
    import urllib.request
    import json
    try:
        req = urllib.request.Request("http://127.0.0.1:57219/api/mgc/status")
        with urllib.request.urlopen(req, timeout=3) as response:
            if response.status == 200:
                data = response.read().decode()
                return json.loads(data)
    except Exception:
        pass
    return {"data": {"status": "stopped"}}


@app.post("/api/mgc/proxy/save")
async def proxy_mgc_save(req: Request):
    import urllib.request
    import json
    import logging
    logger = logging.getLogger("MirginCipher")
    try:
        body = await req.json()
        token = req.headers.get("x-mgc-token", "")
        logger.info(f"proxy_mgc_save called")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-MGC-Token"] = token
        data = json.dumps(body).encode("utf-8")
        logger.info(f"proxy_mgc_save sending to 57219: {list(body.keys())}")
        request_obj = urllib.request.Request(
            "http://127.0.0.1:57219/api/mgc/sensitive/save",
            data=data,
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(request_obj, timeout=10) as response:
            result = response.read().decode()
            logger.info(f"proxy_mgc_save response: {response.status}")
            if response.status == 200:
                return json.loads(result)
    except urllib.error.HTTPError as e:
        try:
            error_body = e.read().decode()
            logger.error(f"proxy_mgc_save HTTPError {e.code}: {error_body[:500]}")
            return json.loads(error_body)
        except Exception:
            logger.error(f"proxy_mgc_save HTTPError {e.code}: {str(e)}")
            return {"code": e.code, "msg": str(e)}
    except Exception as e:
        logger.error(f"proxy_mgc_save error: {e}")
        return {"code": 500, "msg": str(e)}
    return {"code": 500, "msg": "Unknown error"}


@app.post("/api/mgc/proxy/get")
async def proxy_mgc_get(req: Request):
    import urllib.request
    import json
    import logging
    logger = logging.getLogger("MirginCipher")
    try:
        body = await req.json()
        token = req.headers.get("x-mgc-token", "")
        logger.info(f"proxy_mgc_get called")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-MGC-Token"] = token
        data = json.dumps(body).encode("utf-8")
        logger.info(f"proxy_mgc_get sending to 57219: {list(body.keys())}")
        request_obj = urllib.request.Request(
            "http://127.0.0.1:57219/api/mgc/sensitive/get",
            data=data,
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(request_obj, timeout=10) as response:
            result = response.read().decode()
            logger.info(f"proxy_mgc_get response: {response.status}")
            if response.status == 200:
                return json.loads(result)
    except urllib.error.HTTPError as e:
        try:
            error_body = e.read().decode()
            logger.error(f"proxy_mgc_get HTTPError {e.code}: {error_body[:500]}")
            return json.loads(error_body)
        except Exception:
            logger.error(f"proxy_mgc_get HTTPError {e.code}: {str(e)}")
            return {"code": e.code, "msg": str(e)}
    except Exception as e:
        logger.error(f"proxy_mgc_get error: {e}")
        return {"code": 500, "msg": str(e)}
    return {"code": 500, "msg": "Unknown error"}


@app.get("/api/user/settings")
async def get_user_settings():
    from mgc.config.user_settings import get_protection_mode
    return {"protection_mode": get_protection_mode()}


@app.post("/api/user/settings")
async def update_user_settings(req: Request):
    try:
        body = await req.json()
        token = req.headers.get("x-mgc-token", "")
        app_token = getattr(req.app.state, 'token', None)
        if not token or token != app_token:
            return {"status": "error", "message": "Invalid token"}, 401

        enabled = body.get("protection_mode")
        if enabled is not None:
            from mgc.config.user_settings import get_protection_mode, set_protection_mode
            from mgc.core.database.sqlcipher_handler import SQLCipherHandler
            from mgc.core.mgc_service.database.database_handler import DatabaseHandler

            old_mode = get_protection_mode()

            if old_mode != enabled:
                import logging
                logger = logging.getLogger("MirginCipher")

                old_db_key = SQLCipherHandler._get_db_key()

                result = set_protection_mode(enabled)

                new_db_key = SQLCipherHandler._get_db_key()

                db_handler = DatabaseHandler()
                db_handler.temp_key_storage(old_db_key, new_db_key)

                logger.info(f"Protection mode changed: {old_mode} -> {enabled}, rekey completed")
            else:
                result = set_protection_mode(enabled)

        return {"status": "ok"}
    except Exception as e:
        import logging
        logger = logging.getLogger("MirginCipher")
        logger.error(f"update_user_settings error: {e}")
        return {"status": "error"}, 500


@app.post("/api/mgc/service/stop")
async def stop_service_v2():
    install_state["stop_requested"] = True
    if stop_event:
        stop_event.set()
    if _stop_server:
        try:
            _stop_server()
        except Exception:
            pass
    import os
    os._exit(0)
    return {"status": "ok"}


async def shutdown():
    await asyncio.sleep(1)
    if stop_event:
        stop_event.set()


async def load_template(name: str) -> str:
    path = os.path.join(TEMPLATES_DIR, name)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return get_default_template(name)


def get_default_template(name: str) -> str:
    base = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>MGC Blackbox</title>
        <style>
            body { font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Noto Sans', 'DejaVu Sans', sans-serif; margin: 40px; }
            .container { max-width: 600px; margin: 0 auto; }
            h1 { color: #333; }
            button { padding: 10px 20px; margin: 5px; cursor: pointer; }
            input { padding: 8px; margin: 5px; width: 200px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>MGC Blackbox</h1>
    """
    if name == "install.html":
        base += """
            <div id="notice"></div>
            <div>
                <button onclick="startInstall('new_install')">New install</button>
                <button onclick="startInstall('reload')">Reload</button>
                <button onclick="cancel()">Do not install</button>
            </div>
            <script>
                async function startInstall(mode) {
                    await fetch('/api/install/start', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({mode})
                    });
                    window.location.href = '/root-key';
                }
                async function cancel() {
                    await fetch('/api/install/cancel', {method: 'POST'});
                    document.body.innerHTML = '<div style="text-align:center;margin-top:100px;color:#666;">Installation cancelled. You can close this window.</div>';
                }
            </script>
        """
    elif name == "root_key.html":
        base += """
            <p>[WARNING] Please remember your personal key and weight parameter.</p>
            <p>[WARNING] Loss will result in unrecoverable data and failed migration.</p>
            <div id="dbPathField" style="display:none">
                <label>Database Path: <input type="text" id="dbPath"></label>
            </div>
            <div>
                <label>Personal Key: <input type="password" id="personalKey"></label>
            </div>
            <div>
                <label>Weight Parameter (1-9): <input type="text" id="weightParam" maxlength="1"></label>
            </div>
            <div>
                <button onclick="submit()">Confirm</button>
                <button onclick="cancel()">Cancel</button>
            </div>
            <script>
                async function submit() {
                    const personalKey = document.getElementById('personalKey').value;
                    const weightParam = document.getElementById('weightParam').value;
                    const dbPath = document.getElementById('dbPath').value;
                    await fetch('/api/install/root-key', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({personal_key: personalKey, weight_param: weightParam, db_path: dbPath})
                    });
                    window.location.href = '/installing';
                }
                async function cancel() {
                    await fetch('/api/install/cancel', {method: 'POST'});
                    window.close();
                }
            </script>
        """
    elif name == "installing.html":
        base += """
            <p>Installing...</p>
            <script>
                setTimeout(() => window.location.href = '/skill', 3000);
            </script>
        """
    elif name == "skill.html":
        base += """
            <h2>Skill Documentation</h2>
            <p><a href="/api/skill/download" target="_blank">View Skill</a></p>
            <button onclick="stop()">Stop MGC</button>
            <script>
                async function stop() {
                    await fetch('/api/service/stop', {method: 'POST'});
                    document.body.innerHTML = '<div style="text-align:center;margin-top:100px;color:#666;">MGC stopped. You can close this window.</div>';
                }
            </script>
        """
    base += """
        </div>
    </body>
    </html>
    """
    return base


def run_webui(port: int = 57218, stop_callback=None):
    import uvicorn
    global stop_event
    if stop_callback:
        set_stop_callback(stop_callback)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")


if __name__ == "__main__":
    run_webui()