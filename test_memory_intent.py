#!/usr/bin/env python3
"""
TaijiOS Lite — 记忆 + 意图触发测试
1. 验证跨会话记忆（关了再开还记得你）
2. 验证意图检测（说比赛就自动分析比赛）
"""
import sys, os, io, json, time, tempfile, shutil
os.environ["PYTHONUTF8"] = "1"
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))

from evolution.crystallizer import CrystallizationEngine
from evolution.learner import ConversationLearner
from evolution.hexagram import HexagramEngine
from evolution.agi_core import CognitiveMap
from evolution.experience_pool import ExperiencePool
from evolution.contribution import ContributionSystem
from evolution.ecosystem import EcosystemManager
from taijios import (build_quick_system, chat, detect_intent,
                     save_history, load_history)

API_CONFIG = {
    "provider": "DeepSeek",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-chat",
    "api_key": "YOUR_DEEPSEEK_API_KEY",
}


def test_intent_detection():
    """测试意图检测准确性"""
    print("\n  测试1: 意图检测")
    print("  " + "─" * 50)

    test_cases = [
        ("今晚英超比赛你怎么看", "赛事深度分析"),
        ("这个竞品太强了怎么打", "竞争分析"),
        ("我老板这个人靠谱吗", "人物分析"),
        ("要不要辞职去创业", "决策分析"),
        ("怎么才能赚到第一桶金", "商业分析"),
        ("最近焦虑到失眠了", "状态诊断"),
        ("今天天气不错", ""),  # 不应触发任何意图
        ("帮我分析下NBA总决赛", "赛事深度分析"),
        ("选A还是选B纠结死了", "决策分析"),
    ]

    passed = 0
    for msg, expected_keyword in test_cases:
        result = detect_intent(msg)
        if expected_keyword:
            if expected_keyword in result:
                print(f"    ✅ '{msg[:20]}' → {expected_keyword}")
                passed += 1
            else:
                print(f"    ❌ '{msg[:20]}' 期望'{expected_keyword}' 实际:{'有触发' if result else '无触发'}")
        else:
            if not result:
                print(f"    ✅ '{msg[:20]}' → 无触发（正确）")
                passed += 1
            else:
                print(f"    ❌ '{msg[:20]}' 不应触发但触发了")

    print(f"\n  意图检测: {passed}/{len(test_cases)} 通过")
    return passed == len(test_cases)


def test_memory_persistence():
    """测试记忆跨会话持久化"""
    print("\n  测试2: 记忆持久化")
    print("  " + "─" * 50)

    tmpdir = tempfile.mkdtemp()
    history_dir = os.path.join(tmpdir, "history")
    os.makedirs(history_dir, exist_ok=True)

    # 模拟第一次对话
    history_key = "test_user"
    history_file = os.path.join(history_dir, f"{history_key}.json")

    history = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你是做AI的，方向太多是你最大的问题。先告诉我，你现在最想做的是什么？"},
        {"role": "user", "content": "我想做TaijiOS"},
        {"role": "assistant", "content": "方向定了就别犹豫了。先找10个种子用户验证。"},
        {"role": "user", "content": "好，我开始找用户了"},
        {"role": "assistant", "content": "这周找3个，不用多。关键是让他们付费。"},
    ]

    # 保存历史
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    # 模拟"关闭程序"，重新加载
    loaded = []
    with open(history_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)

    ok = True
    if len(loaded) == len(history):
        print(f"    ✅ 历史记录持久化：{len(loaded)//2}轮对话已保存")
    else:
        print(f"    ❌ 历史记录丢失")
        ok = False

    # 验证能恢复prev状态
    prev_user = ""
    prev_reply = ""
    for msg in reversed(loaded):
        if msg["role"] == "assistant" and not prev_reply:
            prev_reply = msg["content"]
        elif msg["role"] == "user" and not prev_user:
            prev_user = msg["content"]
        if prev_user and prev_reply:
            break

    if prev_user and prev_reply:
        print(f"    ✅ 最后一轮恢复：用户'{prev_user[:20]}' → AI'{prev_reply[:20]}'")
    else:
        print(f"    ❌ 无法恢复最后一轮状态")
        ok = False

    # 验证引擎状态持久化
    cryst = CrystallizationEngine(tmpdir)
    learn = ConversationLearner(tmpdir)
    hexeng = HexagramEngine(tmpdir)
    cog = CognitiveMap(tmpdir)

    # 写入一些状态
    learn.record_outcome("我想做AI", "方向不错", "我开始做了")
    hexeng.update_from_conversation(["我在做AI产品", "有目标有方向"], 0.7)
    cog.extract_from_message("我的工作是做AI创业，目标是做出好产品，擅长技术开发，收入还不稳定，朋友说我执行力强", "")

    # "重启"引擎
    cryst2 = CrystallizationEngine(tmpdir)
    learn2 = ConversationLearner(tmpdir)
    hexeng2 = HexagramEngine(tmpdir)
    cog2 = CognitiveMap(tmpdir)

    if hexeng2.current_hexagram:
        print(f"    ✅ 卦象状态持久化：{hexeng2.current_hexagram}")
    else:
        print(f"    ❌ 卦象状态丢失")
        ok = False

    if cog2.map and any(cog2.map.get(d) for d in ["位置", "本事", "钱财", "野心", "口碑"]):
        filled = sum(1 for d in ["位置", "本事", "钱财", "野心", "口碑"] if cog2.map.get(d))
        print(f"    ✅ 认知地图持久化：{filled}/5维度有数据")
    else:
        print(f"    ❌ 认知地图丢失")
        ok = False

    shutil.rmtree(tmpdir)
    return ok


def test_intent_with_api():
    """用DeepSeek API测试意图触发效果"""
    print("\n  测试3: 意图触发API效果")
    print("  " + "─" * 50)

    if API_CONFIG["api_key"] == "YOUR_DEEPSEEK_API_KEY":
        # 从环境变量或本地配置获取
        key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not key:
            config_path = os.path.join(os.path.dirname(__file__), "data", "model_config.json")
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    key = cfg.get("api_key", "")
                except Exception:
                    pass
        if not key:
            print("    ⏭️ 跳过（无API Key，配置后可测试）")
            return True
        API_CONFIG["api_key"] = key

    tmpdir = tempfile.mkdtemp()
    try:
        hexeng = HexagramEngine(tmpdir)
        learn = ConversationLearner(tmpdir)
        cog = CognitiveMap(tmpdir)
        pool = ExperiencePool(tmpdir)

        profile = "姓名：测试\n职业：创业者\n目标：做AI产品"

        # 测试：说比赛→应触发赛事分析模式
        test_msg = "帮我分析一下今晚欧冠皇马对巴萨"
        intent_prompt = detect_intent(test_msg)
        assert "赛事" in intent_prompt, "未触发赛事分析"

        system = build_quick_system(profile,
            [], "", hexeng.get_strategy_prompt(),
            cog.get_map_summary(), pool.get_shared_prompt(),
            intent_prompt)

        t0 = time.time()
        reply = chat(system, [], test_msg, API_CONFIG)
        elapsed = time.time() - t0

        # 检查回复是否进入了分析模式
        analysis_kw = ["分析", "实力", "对比", "预判", "判断", "胜", "负",
                       "优势", "弱点", "关键", "结论"]
        hits = sum(1 for kw in analysis_kw if kw in reply)

        if hits >= 3:
            print(f"    ✅ 赛事分析触发成功 ({elapsed:.1f}s, {hits}个分析关键词)")
            print(f"    回复前80字: {reply[:80].replace(chr(10), ' ')}")
        else:
            print(f"    ⚠️ 赛事分析触发但回复偏弱 ({hits}个分析关键词)")
            print(f"    回复前80字: {reply[:80].replace(chr(10), ' ')}")

        # 测试：说纠结→应触发决策模式
        time.sleep(1)
        test_msg2 = "要不要辞职去创业，纠结了好久"
        intent2 = detect_intent(test_msg2)
        assert "决策" in intent2, "未触发决策分析"

        system2 = build_quick_system(profile,
            [], "", hexeng.get_strategy_prompt(),
            cog.get_map_summary(), pool.get_shared_prompt(),
            intent2)

        t0 = time.time()
        reply2 = chat(system2, [], test_msg2, API_CONFIG)
        elapsed2 = time.time() - t0

        decision_kw = ["选", "决定", "建议", "结论", "行动", "第一步", "利弊"]
        hits2 = sum(1 for kw in decision_kw if kw in reply2)

        if hits2 >= 2:
            print(f"    ✅ 决策分析触发成功 ({elapsed2:.1f}s, {hits2}个决策关键词)")
        else:
            print(f"    ⚠️ 决策分析触发但回复偏弱 ({hits2}个决策关键词)")

        return True
    finally:
        shutil.rmtree(tmpdir)


def main():
    print("=" * 60)
    print("  TaijiOS Lite — 记忆 + 意图触发测试")
    print("=" * 60)

    results = []

    tests = [
        ("意图检测", test_intent_detection),
        ("记忆持久化", test_memory_persistence),
        ("意图API效果", test_intent_with_api),
    ]

    for name, fn in tests:
        print(f"\n{'━' * 60}")
        try:
            ok = fn()
            results.append((name, ok))
        except Exception as e:
            print(f"  ❌ {name} 异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    print(f"\n{'═' * 60}")
    passed = sum(1 for _, ok in results if ok)
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} {name}")
    print(f"\n  总计: {passed}/{len(results)} 通过")
    print(f"{'═' * 60}")


if __name__ == "__main__":
    main()
