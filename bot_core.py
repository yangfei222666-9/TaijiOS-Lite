#!/usr/bin/env python3
"""
TaijiOS Bot 核心 — 多用户引擎管理

每个用户一套独立引擎（结晶/学习/卦象/认知/经验池）。
飞书Bot和Telegram Bot共用这个核心。
"""
import os
import sys
import json
import time
import logging
from pathlib import Path

os.environ["PYTHONUTF8"] = "1"

if getattr(sys, 'frozen', False):
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).parent

sys.path.insert(0, str(APP_DIR))

from evolution.crystallizer import CrystallizationEngine
from evolution.learner import ConversationLearner
from evolution.hexagram import HexagramEngine, HEXAGRAM_STRATEGIES
from evolution.agi_core import CognitiveMap
from evolution.experience_pool import ExperiencePool
from evolution.contribution import ContributionSystem
from evolution.ecosystem import EcosystemManager
from taijios import (build_quick_system, chat, detect_intent,
                     KnowledgeBase, KNOWLEDGE_DIR)

logger = logging.getLogger("bot_core")

BOT_DATA_DIR = APP_DIR / "data" / "bot_users"
BOT_DATA_DIR.mkdir(parents=True, exist_ok=True)


class UserSession:
    """单个用户的完整引擎套件 + 对话历史"""

    def __init__(self, user_id: str, user_name: str = ""):
        self.user_id = user_id
        self.user_name = user_name
        self.user_dir = BOT_DATA_DIR / user_id
        self.user_dir.mkdir(exist_ok=True)

        evo_dir = str(self.user_dir / "evolution")
        os.makedirs(evo_dir, exist_ok=True)

        self.crystallizer = CrystallizationEngine(evo_dir)
        self.learner = ConversationLearner(evo_dir)
        self.hexagram = HexagramEngine(evo_dir)
        self.cognitive = CognitiveMap(evo_dir)
        self.pool = ExperiencePool(evo_dir)
        self.contribution = ContributionSystem(evo_dir)
        self.ecosystem = EcosystemManager(evo_dir)

        self.history = self._load_history()
        self.profile = self._load_profile()
        self.prev_user = ""
        self.prev_reply = ""

        # 恢复上次对话状态
        if self.history and len(self.history) >= 2:
            for msg in reversed(self.history):
                if msg["role"] == "assistant" and not self.prev_reply:
                    self.prev_reply = msg["content"]
                elif msg["role"] == "user" and not self.prev_user:
                    self.prev_user = msg["content"]
                if self.prev_user and self.prev_reply:
                    break

    def _load_history(self) -> list:
        path = self.user_dir / "history.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return []

    def _save_history(self):
        path = self.user_dir / "history.json"
        text = json.dumps(self.history, ensure_ascii=False, indent=2)
        path.write_text(text, encoding="utf-8")

    def _load_profile(self) -> str:
        path = self.user_dir / "profile.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                parts = [f"姓名：{data.get('name', self.user_name or '未知')}"]
                for k, label in [("age", "年龄"), ("gender", "性别"),
                                 ("job", "职业"), ("goal", "目标")]:
                    if data.get(k):
                        parts.append(f"{label}：{data[k]}")
                return "个体认知档案（快速版）\n" + "\n".join(parts)
            except Exception:
                pass
        # 默认档案（只有名字）
        name = self.user_name or "未知"
        return f"个体认知档案（快速版）\n姓名：{name}"

    def save_profile(self, data: dict):
        path = self.user_dir / "profile.json"
        data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        self.profile = self._load_profile()

    def get_round_count(self) -> int:
        return len(self.history) // 2 + 1


class TaijiBot:
    """
    TaijiOS Bot 核心引擎。
    管理多用户会话，处理消息，返回回复。
    """

    def __init__(self, model_config: dict):
        self.model_config = model_config
        self.sessions = {}  # user_id → UserSession
        self.knowledge = KnowledgeBase(str(KNOWLEDGE_DIR))
        logger.info(f"TaijiBot 初始化 | 模型: {model_config.get('provider')} | "
                    f"知识库: {self.knowledge.get_status()}")

    def get_session(self, user_id: str, user_name: str = "") -> UserSession:
        """获取或创建用户会话"""
        if user_id not in self.sessions:
            self.sessions[user_id] = UserSession(user_id, user_name)
        return self.sessions[user_id]

    def handle_message(self, user_id: str, user_name: str,
                       message: str) -> str:
        """
        处理一条用户消息，返回军师回复。
        自动处理：引擎更新、意图检测、知识库检索、推演、积分。
        """
        session = self.get_session(user_id, user_name)

        # 命令处理
        cmd = message.strip().lower()
        if cmd in ("status", "状态"):
            return self._cmd_status(session)
        if cmd in ("help", "帮助"):
            return self._cmd_help()
        if cmd in ("kb", "知识库"):
            return self.knowledge.get_status()

        # 1. 学习器反馈
        if session.prev_user and session.prev_reply:
            session.learner.record_outcome(
                session.prev_user, session.prev_reply, message)

        # 2. 收集最近消息
        recent = [m["content"] for m in session.history
                  if m["role"] == "user"]
        recent.append(message)
        rate = session.learner.get_positive_rate()

        # 3. 推演检测（每3轮）
        divine_text = ""
        round_count = session.get_round_count()
        if round_count >= 3 and round_count % 3 == 0:
            divination = session.hexagram.divine(recent, rate)
            if divination and divination.get("display"):
                divine_text = divination["display"]
        else:
            session.hexagram.update_from_conversation(recent, rate)

        # 4. 意图检测
        intent_prompt = detect_intent(message)

        # 5. 知识库检索
        kb_prompt = self.knowledge.get_knowledge_prompt(message)

        # 6. 认知提取
        session.cognitive.extract_from_message(message, "")

        # 7. 构建 system prompt
        system = build_quick_system(
            session.profile,
            session.crystallizer.get_active_rules(),
            session.learner.get_experience_summary(),
            session.hexagram.get_strategy_prompt(),
            session.cognitive.get_map_summary(),
            session.pool.get_shared_prompt(),
            intent_prompt,
            kb_prompt)

        # 8. 调用 AI
        try:
            reply = chat(system, session.history, message, self.model_config)
        except Exception as e:
            err = str(e)
            if "401" in err or "auth" in err.lower():
                return "[错误] API Key 无效，请检查配置"
            elif "429" in err or "rate" in err.lower():
                return "[错误] 请求太频繁，等几秒再试"
            else:
                return f"[错误] {err[:100]}"

        # 9. 后续更新
        session.cognitive.extract_from_message(message, reply)
        session.contribution.add_points("chat")
        session.ecosystem.record_action("chat")

        # 10. 结晶检查
        crystal_text = ""
        if session.learner.should_crystallize():
            new_crystals = session.crystallizer.crystallize()
            if new_crystals:
                crystal_text = "\n".join(
                    f"  ✦ {c['rule']}" for c in new_crystals)
                crystal_text = f"\n\n[进化] 新增{len(new_crystals)}条经验结晶：\n{crystal_text}"

        # 11. 成就检查
        achieve_text = ""
        new_ach = session.ecosystem.check_achievements(
            session.ecosystem.get_stats())
        for a in new_ach:
            achieve_text += f"\n  ★ 成就解锁：{a['name']} — {a['desc']}"

        # 12. 保存历史
        session.history.append({"role": "user", "content": message})
        session.history.append({"role": "assistant", "content": reply})
        if len(session.history) > 40:
            # 压缩前提取认知
            old = session.history[:len(session.history) - 40]
            for m in old:
                if m["role"] == "user":
                    session.cognitive.extract_from_message(m["content"], "")
            session.history = session.history[-40:]
        session._save_history()

        session.prev_user = message
        session.prev_reply = reply

        # 13. 组装最终回复
        parts = []
        if divine_text:
            parts.append(divine_text)
        parts.append(reply)
        if crystal_text:
            parts.append(crystal_text)
        if achieve_text:
            parts.append(achieve_text)

        return "\n".join(parts)

    def handle_greeting(self, user_id: str, user_name: str) -> str:
        """新用户或回来的用户打招呼"""
        session = self.get_session(user_id, user_name)
        rounds = len(session.history) // 2

        if rounds > 0:
            # 老用户
            hex_strat = HEXAGRAM_STRATEGIES.get(
                session.hexagram.current_hexagram, {})
            style = hex_strat.get("style", "")
            crystals = len(session.crystallizer.get_active_rules())
            msg = f"欢迎回来，{user_name or '主公'}！"
            msg += f"\n上次聊了{rounds}轮，我都记得。"
            if crystals:
                msg += f"\n已积累{crystals}条关于你的经验。"
            if style:
                msg += f"\n当前状态：{style[:30]}"
            return msg
        else:
            return (f"你好，{user_name or '主公'}！"
                    f"\n我是你的认知军师 TaijiOS。"
                    f"\n像诸葛亮对刘备——看清局势，给出判断。"
                    f"\n直接说你想聊什么，不用寒暄。")

    def _cmd_status(self, s: UserSession) -> str:
        """状态命令"""
        hex_name = s.hexagram.current_hexagram
        strat = HEXAGRAM_STRATEGIES.get(hex_name, {})
        crystals = len(s.crystallizer.get_active_rules())
        rounds = len(s.history) // 2
        dims = sum(1 for d in ["位置","本事","钱财","野心","口碑"]
                   if s.cognitive.map.get(d))
        level = s.contribution.level[0]
        points = s.contribution.total_points

        lines = [
            f"━━ TaijiOS 进化状态 ━━",
            f"卦象：{strat.get('name', hex_name)}",
            f"策略：{strat.get('style', '')}",
            f"结晶：{crystals}条",
            f"认知：{dims}/5维度",
            f"对话：{rounds}轮",
            f"等级：{level} | {points}积分",
            f"知识库：{self.knowledge.get_status()}",
        ]
        return "\n".join(lines)

    def _cmd_help(self) -> str:
        return ("━━ TaijiOS 命令 ━━\n"
                "status — 查看进化状态\n"
                "help — 显示本帮助\n"
                "kb — 查看知识库\n"
                "\n直接打字就是和军师对话，不需要命令。\n"
                "说比赛就分析比赛，说纠结就帮你决断。")
