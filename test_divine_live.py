#!/usr/bin/env python3
"""
TaijiOS Lite — 变爻推演集成测试（DeepSeek API）
验证推演在真实对话流中的触发：每3轮自动推演
"""
import sys, os, io, json, time, tempfile, shutil
os.environ["PYTHONUTF8"] = "1"
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))

from evolution.crystallizer import CrystallizationEngine
from evolution.learner import ConversationLearner
from evolution.hexagram import HexagramEngine, HEXAGRAM_STRATEGIES
from evolution.agi_core import CognitiveMap
from evolution.experience_pool import ExperiencePool
from taijios import build_quick_system, chat

API_CONFIG = {
    "provider": "DeepSeek",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-chat",
    "api_key": "YOUR_DEEPSEEK_API_KEY",
}

PROFILE = """个体认知档案（快速版）
姓名：测试用户
年龄：28
性别：男
职业/身份：创业者
自述优点：执行力强
当前困扰：方向太多
核心目标：做出一个好产品
"""

# 6轮对话，第3轮和第6轮应触发推演
CONVERSATIONS = [
    "我想做一个AI产品，你觉得方向怎么样？",
    "手上有5万块，一个人干，怎么开始？",
    "最近很焦虑，觉得自己是不是在浪费时间",     # 第3轮 → 触发推演
    "好吧，那我先从找10个种子用户开始",
    "找到3个了，反馈还不错，有人愿意付费",
    "我觉得方向对了，下一步该做什么？",           # 第6轮 → 触发推演
]


def main():
    print("=" * 60)
    print("  TaijiOS — 变爻推演集成测试（DeepSeek API）")
    print("  6轮对话，第3轮和第6轮应触发推演")
    print("=" * 60)

    tmpdir = tempfile.mkdtemp()
    try:
        cryst = CrystallizationEngine(tmpdir)
        learn = ConversationLearner(tmpdir)
        hexeng = HexagramEngine(tmpdir)
        cog = CognitiveMap(tmpdir)
        pool = ExperiencePool(tmpdir)

        history = []
        prev_user = ""
        prev_reply = ""
        divine_triggered = []

        for i, msg in enumerate(CONVERSATIONS, 1):
            print(f"\n{'━' * 60}")
            print(f"  第{i}轮 | 用户: {msg[:40]}")
            print(f"{'━' * 60}")

            # 更新学习器
            if prev_user and prev_reply:
                learn.record_outcome(prev_user, prev_reply, msg)

            recent = [m["content"] for m in history if m["role"] == "user"] + [msg]
            rate = learn.get_positive_rate()

            # 核心测试：每3轮触发推演
            round_count = len(history) // 2 + 1
            if round_count >= 3 and round_count % 3 == 0:
                divination = hexeng.divine(recent, rate)
                if divination and divination.get("display"):
                    print(divination["display"])
                    divine_triggered.append(i)
                    print(f"  → 推演已触发！当前:{divination['current']['name']} → 变卦:{divination['future']['name']}")
                else:
                    print(f"  → 第{i}轮应触发推演但返回为空！")
            else:
                hexeng.update_from_conversation(recent, rate)

            cog.extract_from_message(msg, "")

            system = build_quick_system(PROFILE,
                cryst.get_active_rules(),
                learn.get_experience_summary(),
                hexeng.get_strategy_prompt(),
                cog.get_map_summary(),
                pool.get_shared_prompt())

            # API调用
            t0 = time.time()
            try:
                reply = chat(system, history, msg, API_CONFIG)
                elapsed = time.time() - t0
                # 截取前80字展示
                short = reply[:80].replace("\n", " ")
                print(f"  军师({elapsed:.1f}s): {short}...")
            except Exception as e:
                elapsed = time.time() - t0
                print(f"  ❌ API错误({elapsed:.1f}s): {str(e)[:60]}")
                prev_user = msg
                prev_reply = ""
                time.sleep(2)
                continue

            history.append({"role": "user", "content": msg})
            history.append({"role": "assistant", "content": reply})
            prev_user = msg
            prev_reply = reply

            if i < len(CONVERSATIONS):
                time.sleep(1)

        # 结果
        print(f"\n{'═' * 60}")
        print(f"  测试结果")
        print(f"{'═' * 60}")
        print(f"  推演触发轮次: {divine_triggered}")
        print(f"  最终卦象: {hexeng.current_hexagram}")
        print(f"  最终六爻: {hexeng.current_lines}")

        # 验证
        ok = True
        if 3 in divine_triggered:
            print(f"  ✅ 第3轮正确触发推演")
        else:
            print(f"  ❌ 第3轮未触发推演")
            ok = False

        if 6 in divine_triggered:
            print(f"  ✅ 第6轮正确触发推演")
        else:
            print(f"  ❌ 第6轮未触发推演")
            ok = False

        if ok:
            print(f"\n  ✅ 变爻推演集成测试全部通过")
        else:
            print(f"\n  ⚠️ 部分推演未触发")
        print(f"{'═' * 60}")

    finally:
        shutil.rmtree(tmpdir)


if __name__ == "__main__":
    main()
