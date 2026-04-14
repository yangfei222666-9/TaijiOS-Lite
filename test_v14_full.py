#!/usr/bin/env python3
"""
TaijiOS v1.4.0 — 全功能多轮真实API测试
知识库 + 意图触发 + 记忆 + 推演 + 引擎联动

10轮对话覆盖：知识库调用、意图触发、推演、情绪转变、决策、比赛分析
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
from evolution.contribution import ContributionSystem
from evolution.ecosystem import EcosystemManager
from taijios import (build_quick_system, chat, detect_intent, KnowledgeBase)

API_CONFIG = {
    "provider": "DeepSeek",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-chat",
    "api_key": "YOUR_DEEPSEEK_API_KEY",
}

PROFILE = """个体认知档案（快速版）
姓名：杨飞
年龄：1993
性别：男
"""

# 10轮对话：覆盖全部新功能
CONVERSATIONS = [
    # R1-2: 基础对话 + 认知建立
    "我做了一个AI产品叫TaijiOS，帮我分析下这个产品定位行不行",
    "TaijiOS和ChatGPT比有什么优势？怎么打差异化？",
    # R3: 触发推演（第3轮）+ 知识库调用（问竞品）
    "帮我分析下竞品，我要不要换个方向",
    # R4: 意图触发（赚钱）
    "手上只有3万块，怎么靠TaijiOS赚到第一桶金",
    # R5: 意图触发（情绪低落）
    "最近焦虑到失眠，觉得一个人扛不住了",
    # R6: 触发推演（第6轮）+ 意图触发（决策）
    "要不要找合伙人？还是继续一个人干",
    # R7: 意图触发（比赛分析）— 验证非创业场景
    "说个轻松的，帮我分析下今晚欧冠皇马对巴萨谁赢",
    # R8: 知识库调用（问融资）
    "我接下来该不该找投资？还是先跑通商业模式",
    # R9: 触发推演（第9轮）
    "找到3个付费用户了，反馈不错，下一步怎么放大",
    # R10: 盲区检测
    "你觉得我最大的盲点是什么？不要客气直接说",
]


def main():
    print("=" * 65)
    print("  TaijiOS v1.4.0 — 全功能10轮真实API测试")
    print("  知识库 + 意图触发 + 推演 + 记忆 + 引擎联动")
    print("=" * 65)

    tmpdir = tempfile.mkdtemp()
    # 创建知识库
    kb_dir = os.path.join(tmpdir, "knowledge")
    os.makedirs(kb_dir)

    # 复制知识库文件
    src_kb = os.path.join(os.path.dirname(__file__), "knowledge")
    if os.path.exists(src_kb):
        for f in os.listdir(src_kb):
            shutil.copy2(os.path.join(src_kb, f), kb_dir)

    knowledge = KnowledgeBase(kb_dir)
    print(f"\n  {knowledge.get_status()}")

    cryst = CrystallizationEngine(tmpdir)
    learn = ConversationLearner(tmpdir)
    hexeng = HexagramEngine(tmpdir)
    cog = CognitiveMap(tmpdir)
    pool = ExperiencePool(tmpdir)
    cont = ContributionSystem(tmpdir)
    eco = EcosystemManager(tmpdir)

    history = []
    prev_user = ""
    prev_reply = ""

    results = {
        "rounds": [],
        "intents_triggered": [],
        "divinations_triggered": [],
        "kb_hits": [],
        "hex_changes": [],
        "errors": [],
    }

    for i, msg in enumerate(CONVERSATIONS, 1):
        print(f"\n{'━' * 65}")
        print(f"  第{i}轮 | 用户: {msg[:50]}")
        print(f"{'━' * 65}")

        # 引擎更新
        if prev_user and prev_reply:
            learn.record_outcome(prev_user, prev_reply, msg)

        recent = [m["content"] for m in history if m["role"] == "user"] + [msg]
        rate = learn.get_positive_rate()

        # 推演检测
        round_count = len(history) // 2 + 1
        divine_this_round = False
        if round_count >= 3 and round_count % 3 == 0:
            divination = hexeng.divine(recent, rate)
            if divination and divination.get("display"):
                print(divination["display"])
                results["divinations_triggered"].append(i)
                divine_this_round = True
        else:
            hexeng.update_from_conversation(recent, rate)

        hex_name = hexeng.current_hexagram
        strat = HEXAGRAM_STRATEGIES.get(hex_name, {})
        results["hex_changes"].append(strat.get("name", hex_name))

        # 意图检测
        intent_prompt = detect_intent(msg)
        if intent_prompt:
            intent_tag = intent_prompt.split("：")[1].split("】")[0] if "：" in intent_prompt else "?"
            print(f"  [意图触发] {intent_tag}")
            results["intents_triggered"].append((i, intent_tag))

        # 知识库检索
        kb_prompt = knowledge.get_knowledge_prompt(msg)
        if kb_prompt:
            # 显示命中的知识块来源
            kb_results = knowledge.search(msg)
            sources = set(r["source"] for r in kb_results)
            print(f"  [知识库命中] {', '.join(sources)}")
            results["kb_hits"].append((i, list(sources)))

        # 认知提取
        cog.extract_from_message(msg, "")

        # 构建prompt
        system = build_quick_system(PROFILE,
            cryst.get_active_rules(),
            learn.get_experience_summary(),
            hexeng.get_strategy_prompt(),
            cog.get_map_summary(),
            pool.get_shared_prompt(),
            intent_prompt,
            kb_prompt)

        # API调用
        t0 = time.time()
        try:
            reply = chat(system, history, msg, API_CONFIG)
            elapsed = time.time() - t0
        except Exception as e:
            elapsed = time.time() - t0
            err = str(e)[:80]
            print(f"  ❌ API错误({elapsed:.1f}s): {err}")
            results["rounds"].append({"round": i, "status": "error", "time": elapsed})
            results["errors"].append(f"R{i}: {err}")
            prev_user = msg
            prev_reply = ""
            time.sleep(2)
            continue

        # 质量检查
        checks = {}
        checks["length"] = len(reply) > 80
        style_kw = ["主公","军师","建议","判断","分析","方向","问题","核心","关键",
                     "直接","结论","行动","验证","策略","现在","必须","不要","先",
                     "依据","风险","机会","优势","弱点"]
        checks["style"] = sum(1 for kw in style_kw if kw in reply) >= 2
        bad_kw = ["作为AI","作为语言模型","我无法","作为一个AI"]
        checks["no_fluff"] = not any(kw in reply for kw in bad_kw)

        # 检查知识库引用（如果有kb_prompt，回复应该引用相关内容）
        if kb_prompt:
            kb_ref_kw = ["TaijiOS", "竞品", "差异化", "Agent", "易经", "DeepSeek",
                         "军师", "产品", "模型", "创业", "融资", "投资"]
            checks["kb_used"] = sum(1 for kw in kb_ref_kw if kw in reply) >= 2

        round_result = {
            "round": i,
            "status": "pass" if all(checks.values()) else "warn",
            "checks": checks,
            "time": elapsed,
            "reply_len": len(reply),
            "divine": divine_this_round,
            "intent": bool(intent_prompt),
            "kb": bool(kb_prompt),
        }
        results["rounds"].append(round_result)

        # 展示回复
        short = reply[:120].replace("\n", " ")
        tags = []
        if checks.get("style"):
            tags.append("军师风格✅")
        else:
            tags.append("风格⚠️")
        if checks.get("no_fluff"):
            tags.append("非套话✅")
        if checks.get("kb_used") is not None:
            tags.append("知识库引用✅" if checks["kb_used"] else "知识库引用⚠️")
        print(f"  [{elapsed:.1f}s] {' '.join(tags)}")
        print(f"  军师: {short}...")

        # 更新
        cog.extract_from_message(msg, reply)
        cont.add_points("chat")
        eco.record_action("chat")

        history.append({"role": "user", "content": msg})
        history.append({"role": "assistant", "content": reply})
        prev_user = msg
        prev_reply = reply

        if i < len(CONVERSATIONS):
            time.sleep(1)

    # ── 总结 ──
    print(f"\n\n{'═' * 65}")
    print(f"  v1.4.0 全功能测试总结")
    print(f"{'═' * 65}")

    passed = sum(1 for r in results["rounds"] if r["status"] == "pass")
    warned = sum(1 for r in results["rounds"] if r["status"] == "warn")
    errors = sum(1 for r in results["rounds"] if r["status"] == "error")
    total = len(results["rounds"])

    print(f"\n  对话: {passed}通过 / {warned}警告 / {errors}错误 (共{total}轮)")

    # 意图触发
    print(f"\n  意图触发 ({len(results['intents_triggered'])}次):")
    for rd, tag in results["intents_triggered"]:
        print(f"    R{rd}: {tag}")

    # 推演
    print(f"\n  推演触发 ({len(results['divinations_triggered'])}次):")
    for rd in results["divinations_triggered"]:
        print(f"    R{rd}: 变爻推演")

    # 知识库
    print(f"\n  知识库命中 ({len(results['kb_hits'])}次):")
    for rd, sources in results["kb_hits"]:
        print(f"    R{rd}: {', '.join(sources)}")

    # 卦象变化
    unique_hex = []
    for h in results["hex_changes"]:
        if not unique_hex or unique_hex[-1] != h:
            unique_hex.append(h)
    print(f"\n  卦象轨迹: {' → '.join(unique_hex)}")

    # 认知维度
    dims = {}
    for d in ["位置", "本事", "钱财", "野心", "口碑"]:
        dims[d] = len(cog.map.get(d, []))
    filled = sum(1 for v in dims.values() if v > 0)
    print(f"  认知积累: {filled}/5维度 {dims}")
    print(f"  积分: {cont.total_points}")

    # 验证清单
    print(f"\n{'═' * 65}")
    print(f"  功能验证清单")
    print(f"{'═' * 65}")

    checklist = [
        ("知识库加载", knowledge.chunks, f"{len(knowledge.chunks)}个知识块"),
        ("知识库检索", len(results["kb_hits"]) > 0, f"{len(results['kb_hits'])}次命中"),
        ("意图触发", len(results["intents_triggered"]) >= 3, f"{len(results['intents_triggered'])}次触发"),
        ("变爻推演", len(results["divinations_triggered"]) >= 2, f"{len(results['divinations_triggered'])}次推演"),
        ("军师风格", all(r.get("checks", {}).get("style", True)
                       for r in results["rounds"] if r["status"] != "error"),
         "全程保持"),
        ("无AI套话", all(r.get("checks", {}).get("no_fluff", True)
                       for r in results["rounds"] if r["status"] != "error"),
         "全程通过"),
        ("认知积累", filled >= 3, f"{filled}/5维度"),
        ("卦象运转", len(unique_hex) >= 2, f"{len(unique_hex)}次变化"),
        ("零API错误", errors == 0, f"{errors}个错误"),
    ]

    all_pass = True
    for name, ok, detail in checklist:
        icon = "✅" if ok else "❌"
        if not ok:
            all_pass = False
        print(f"  {icon} {name} — {detail}")

    print(f"\n{'═' * 65}")
    if all_pass:
        print(f"  ✅ v1.4.0 全功能测试通过 — 知识库+意图+推演+记忆全部在线")
    else:
        print(f"  ⚠️ 部分功能需要检查")
    print(f"{'═' * 65}")

    shutil.rmtree(tmpdir)


if __name__ == "__main__":
    main()
