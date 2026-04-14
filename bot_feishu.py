#!/usr/bin/env python3
"""
TaijiOS 飞书Bot — 认知军师上飞书

用法：
  1. 去飞书开放平台(open.feishu.cn)创建企业自建应用
  2. 添加「机器人」能力
  3. 配置事件订阅：接收消息 im.message.receive_v1
  4. 配置环境变量或 .env：
     FEISHU_APP_ID=你的App ID
     FEISHU_APP_SECRET=你的App Secret
     FEISHU_VERIFICATION_TOKEN=事件订阅的Verification Token（可选）
     DEEPSEEK_API_KEY=你的DeepSeek Key
  5. python bot_feishu.py
  6. 把 http://你的服务器:9090/webhook/event 填到飞书事件订阅URL

支持：
  - 私聊：每个用户独立会话
  - 群聊：@机器人触发
  - 命令：status / help / kb
"""
import os
import sys
import json
import time
import logging
import hashlib
import requests
import threading
from pathlib import Path

os.environ["PYTHONUTF8"] = "1"
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv

APP_DIR = Path(__file__).parent
load_dotenv(APP_DIR / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("feishu")

# ── 配置 ────────────────────────────────────────────

FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_VERIFY_TOKEN = os.getenv("FEISHU_VERIFICATION_TOKEN", "")
FEISHU_ENCRYPT_KEY = os.getenv("FEISHU_ENCRYPT_KEY", "")

API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
API_BASE = os.getenv("API_BASE_URL", "https://api.deepseek.com")
API_MODEL = os.getenv("API_MODEL", "deepseek-chat")
API_PROVIDER = os.getenv("API_PROVIDER", "DeepSeek")

PORT = int(os.getenv("FEISHU_BOT_PORT", "9090"))

if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
    print("错误：需要设置飞书应用配置")
    print("  在 .env 文件添加:")
    print("    FEISHU_APP_ID=你的App ID")
    print("    FEISHU_APP_SECRET=你的App Secret")
    print("  去 open.feishu.cn 创建企业自建应用")
    sys.exit(1)

if not API_KEY:
    config_path = APP_DIR / "data" / "model_config.json"
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            API_KEY = cfg.get("api_key", "")
            API_BASE = cfg.get("base_url", API_BASE)
            API_MODEL = cfg.get("model", API_MODEL)
            API_PROVIDER = cfg.get("provider", API_PROVIDER)
        except Exception:
            pass
    if not API_KEY:
        print("错误：需要设置 AI 模型的 API Key")
        sys.exit(1)

MODEL_CONFIG = {
    "provider": API_PROVIDER,
    "base_url": API_BASE,
    "model": API_MODEL,
    "api_key": API_KEY,
}


# ── 飞书 API ────────────────────────────────────────

class FeishuAPI:
    """飞书 API 封装"""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._token = ""
        self._token_expires = 0

    def get_token(self) -> str:
        """获取 tenant_access_token"""
        if self._token and time.time() < self._token_expires - 60:
            return self._token

        resp = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=10,
        )
        data = resp.json()
        if data.get("code") == 0:
            self._token = data["tenant_access_token"]
            self._token_expires = time.time() + data.get("expire", 7200)
            return self._token
        else:
            logger.error(f"获取token失败: {data}")
            return ""

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.get_token()}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def reply_message(self, message_id: str, text: str):
        """回复消息"""
        # 飞书消息最大长度约30000字符，一般够用
        content = json.dumps({"text": text}, ensure_ascii=False)
        resp = requests.post(
            f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply",
            headers=self._headers(),
            json={
                "content": content,
                "msg_type": "text",
            },
            timeout=30,
        )
        result = resp.json()
        if result.get("code") != 0:
            logger.error(f"回复失败: {result}")
        return result

    def send_message(self, receive_id: str, text: str,
                     receive_id_type: str = "open_id"):
        """主动发消息"""
        content = json.dumps({"text": text}, ensure_ascii=False)
        resp = requests.post(
            f"https://open.feishu.cn/open-apis/im/v1/messages",
            headers=self._headers(),
            params={"receive_id_type": receive_id_type},
            json={
                "receive_id": receive_id,
                "content": content,
                "msg_type": "text",
            },
            timeout=30,
        )
        return resp.json()

    def get_user_info(self, open_id: str) -> dict:
        """获取用户信息"""
        try:
            resp = requests.get(
                f"https://open.feishu.cn/open-apis/contact/v3/users/{open_id}",
                headers=self._headers(),
                params={"user_id_type": "open_id"},
                timeout=10,
            )
            data = resp.json()
            if data.get("code") == 0:
                return data.get("data", {}).get("user", {})
        except Exception as e:
            logger.warning(f"获取用户信息失败: {e}")
        return {}


# ── 消息处理 ────────────────────────────────────────

# 消息去重（飞书可能重复推送）
_processed_msgs = set()
_processed_lock = threading.Lock()


def is_duplicate(msg_id: str) -> bool:
    with _processed_lock:
        if msg_id in _processed_msgs:
            return True
        _processed_msgs.add(msg_id)
        # 只保留最近1000条
        if len(_processed_msgs) > 1000:
            _processed_msgs.clear()
        return False


def handle_event(event: dict, feishu: FeishuAPI, taiji_bot) -> dict:
    """处理飞书事件"""
    header = event.get("header", {})
    event_type = header.get("event_type", "")

    if event_type != "im.message.receive_v1":
        return {"code": 0}

    payload = event.get("event", {})
    message = payload.get("message", {})
    msg_id = message.get("message_id", "")
    msg_type = message.get("message_type", "")
    chat_type = message.get("chat_type", "")  # p2p / group

    # 去重
    if is_duplicate(msg_id):
        return {"code": 0}

    # 只处理文本消息
    if msg_type != "text":
        feishu.reply_message(msg_id, "目前只支持文字消息，直接打字就好。")
        return {"code": 0}

    # 解析消息内容
    try:
        content = json.loads(message.get("content", "{}"))
        text = content.get("text", "").strip()
    except Exception:
        text = ""

    if not text:
        return {"code": 0}

    # 群聊中去掉 @mention
    mentions = payload.get("message", {}).get("mentions", [])
    for m in mentions:
        key = m.get("key", "")
        if key:
            text = text.replace(key, "").strip()

    # 获取用户信息
    sender = payload.get("sender", {})
    sender_id = sender.get("sender_id", {})
    open_id = sender_id.get("open_id", "")
    user_id = sender_id.get("user_id", open_id)

    # 尝试获取用户名
    user_name = ""
    user_info = feishu.get_user_info(open_id)
    if user_info:
        user_name = user_info.get("name", "")

    logger.info(f"[{user_name or open_id[:8]}] {text[:50]}")

    # 异步处理（避免飞书超时）
    def process_and_reply():
        try:
            reply = taiji_bot.handle_message(user_id, user_name, text)
            feishu.reply_message(msg_id, reply)
            logger.info(f"  → 回复 {len(reply)}字")
        except Exception as e:
            logger.error(f"处理消息失败: {e}")
            feishu.reply_message(msg_id, f"军师遇到问题了：{str(e)[:50]}")

    threading.Thread(target=process_and_reply, daemon=True).start()
    return {"code": 0}


# ── Flask 服务器 ────────────────────────────────────

def create_flask_app(feishu: FeishuAPI, taiji_bot):
    """创建 Flask app 处理飞书 webhook"""
    try:
        from flask import Flask, request, jsonify
    except ImportError:
        print("需要安装 Flask: pip install flask")
        sys.exit(1)

    app = Flask(__name__)

    @app.route("/webhook/event", methods=["POST"])
    def webhook():
        data = request.json or {}

        # URL验证（飞书首次配置时会发送验证请求）
        if "challenge" in data:
            return jsonify({"challenge": data["challenge"]})

        # Token验证
        if FEISHU_VERIFY_TOKEN:
            token = data.get("header", {}).get("token", "")
            if token != FEISHU_VERIFY_TOKEN:
                return jsonify({"code": 401, "msg": "invalid token"}), 401

        # 处理事件
        result = handle_event(data, feishu, taiji_bot)
        return jsonify(result)

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({
            "status": "ok",
            "bot": "TaijiOS Feishu Bot",
            "knowledge": taiji_bot.knowledge.get_status(),
            "users": len(taiji_bot.sessions),
        })

    return app


# ── 无 Flask 的简易 HTTP 服务器 ─────────────────────

def create_simple_server(feishu: FeishuAPI, taiji_bot):
    """不依赖 Flask 的简易 HTTP 服务器"""
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != "/webhook/event":
                self.send_response(404)
                self.end_headers()
                return

            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)

            try:
                data = json.loads(body)
            except Exception:
                self.send_response(400)
                self.end_headers()
                return

            # URL验证
            if "challenge" in data:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(
                    {"challenge": data["challenge"]}).encode())
                return

            # Token验证
            if FEISHU_VERIFY_TOKEN:
                token = data.get("header", {}).get("token", "")
                if token != FEISHU_VERIFY_TOKEN:
                    self.send_response(401)
                    self.end_headers()
                    return

            result = handle_event(data, feishu, taiji_bot)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())

        def do_GET(self):
            if self.path == "/health":
                resp = json.dumps({
                    "status": "ok",
                    "bot": "TaijiOS Feishu Bot",
                    "users": len(taiji_bot.sessions),
                })
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(resp.encode())
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass  # 不打印默认日志

    return HTTPServer(("0.0.0.0", PORT), Handler)


# ── 主入口 ────────────────────────────────────────────

def main():
    from bot_core import TaijiBot

    feishu = FeishuAPI(FEISHU_APP_ID, FEISHU_APP_SECRET)

    # 验证token
    token = feishu.get_token()
    if not token:
        print("飞书Token获取失败，检查 APP_ID 和 APP_SECRET")
        sys.exit(1)

    taiji_bot = TaijiBot(MODEL_CONFIG)

    print("=" * 50)
    print(f"  TaijiOS 飞书Bot 已启动")
    print(f"  模型: {API_PROVIDER} ({API_MODEL})")
    print(f"  知识库: {taiji_bot.knowledge.get_status()}")
    print(f"  端口: {PORT}")
    print(f"  Webhook: http://0.0.0.0:{PORT}/webhook/event")
    print("=" * 50)

    # 尝试用 Flask，没有就用内置 HTTP
    try:
        import flask
        app = create_flask_app(feishu, taiji_bot)
        print(f"  使用 Flask 服务器\n")
        app.run(host="0.0.0.0", port=PORT, debug=False)
    except ImportError:
        print(f"  使用内置 HTTP 服务器（安装flask可获得更好性能）\n")
        server = create_simple_server(feishu, taiji_bot)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n退出")
            server.server_close()


if __name__ == "__main__":
    main()
