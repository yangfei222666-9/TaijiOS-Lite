#!/usr/bin/env python3
"""
TaijiOS Lite — 变爻推演系统测试
测试 divine() 方法的完整链路：卦象变化→变爻检测→变卦推算→预判生成
"""
import sys, os, io, tempfile, shutil
os.environ["PYTHONUTF8"] = "1"
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))

from evolution.hexagram import HexagramEngine, HEXAGRAM_STRATEGIES

def test_basic_divine():
    """基础推演：从乾卦开始，负面消息后推演"""
    tmpdir = tempfile.mkdtemp()
    try:
        eng = HexagramEngine(tmpdir)
        assert eng.current_hexagram == "乾", f"初始应为乾，实际 {eng.current_hexagram}"

        # 正常对话3轮
        msgs1 = ["我在做AI产品", "计划找用户测试", "方向是AI认知军师"]
        eng.update_from_conversation(msgs1, 0.7)
        print(f"  初始卦象: {eng.current_hexagram} {eng.current_lines}")

        # 情绪转负面 → 应触发变爻
        msgs2 = msgs1 + ["最近很焦虑", "不知道做什么", "觉得迷茫没方向"]
        result = eng.divine(msgs2, 0.3)

        assert result is not None, "divine() 返回了 None"
        assert "current" in result, "缺少 current"
        assert "future" in result, "缺少 future"
        assert "changing_lines" in result, "缺少 changing_lines"
        assert "prediction" in result, "缺少 prediction"
        assert "advice" in result, "缺少 advice"
        assert "display" in result, "缺少 display"
        assert len(result["changing_lines"]) > 0, "没有检测到变爻"

        print(f"  当前卦: {result['current']['name']} {result['current']['lines_display']}")
        print(f"  变爻: {result['changing_lines']}")
        print(f"  变卦: {result['future']['name']} {result['future']['lines_display']}")
        print(f"  预判长度: {len(result['prediction'])}字")
        print(f"  建议长度: {len(result['advice'])}字")
        assert len(result["prediction"]) > 10, "预判文本太短"
        assert len(result["advice"]) > 5, "建议文本太短"
        assert "军师推演" in result["display"], "display 格式不对"
        print("  ✅ 基础推演测试通过")
        return True
    finally:
        shutil.rmtree(tmpdir)


def test_no_change_divine():
    """无自然变爻：连续相同消息，应通过 _detect_dynamic_lines 推算动爻"""
    tmpdir = tempfile.mkdtemp()
    try:
        eng = HexagramEngine(tmpdir)
        # 两轮相同风格的消息
        msgs = ["我计划做AI", "有目标有方向"]
        eng.update_from_conversation(msgs, 0.6)
        hex_before = eng.current_hexagram
        lines_before = eng.current_lines.copy()

        # 再来类似的消息，不会有自然变化
        msgs2 = msgs + ["继续做AI产品", "目标明确"]
        result = eng.divine(msgs2, 0.6)

        assert result is not None
        assert len(result["changing_lines"]) > 0, "即使无自然变爻也应推算出动爻"
        print(f"  无变化场景 - 推算动爻: {result['changing_lines']}")
        print(f"  当前: {result['current']['name']} → 变卦: {result['future']['name']}")
        print("  ✅ 无自然变爻测试通过")
        return True
    finally:
        shutil.rmtree(tmpdir)


def test_transition_insights():
    """测试精确匹配的推演语义库"""
    tmpdir = tempfile.mkdtemp()
    try:
        eng = HexagramEngine(tmpdir)

        # 先设置到困卦状态（资源匮乏）
        msgs_low = ["没钱没资源", "不知道做什么", "搞不懂为什么", "缺人缺时间", "不确定该不该做"]
        eng.update_from_conversation(msgs_low, 0.2)
        print(f"  低谷卦: {eng.current_hexagram} {eng.current_lines}")

        # 然后突然好转
        msgs_up = msgs_low + ["我决定了方向是AI", "有信心冲一把", "我在做产品"]
        result = eng.divine(msgs_up, 0.7)

        assert result is not None
        print(f"  转变: {result['current']['name']} → {result['future']['name']}")
        print(f"  变爻: {result['changing_lines']}")
        assert len(result["display"]) > 50, "display 文本太短"
        print("  ✅ 转变推演测试通过")
        return True
    finally:
        shutil.rmtree(tmpdir)


def test_display_format():
    """测试推演展示格式完整性"""
    tmpdir = tempfile.mkdtemp()
    try:
        eng = HexagramEngine(tmpdir)
        msgs = ["我很焦虑", "不知道做什么", "迷茫", "方向太多选不了"]
        result = eng.divine(msgs, 0.3)

        display = result["display"]
        assert "┌" in display, "缺少边框上"
        assert "└" in display, "缺少边框下"
        assert "军师推演" in display, "缺少标题"
        assert "当前" in display, "缺少当前卦"
        assert "变爻" in display, "缺少变爻"
        assert "变卦" in display, "缺少变卦"
        assert "推演" in display, "缺少推演"
        assert "建议" in display, "缺少建议"
        print(f"  展示文本:\n{display}")
        print("  ✅ 展示格式测试通过")
        return True
    finally:
        shutil.rmtree(tmpdir)


def test_line_names():
    """测试变爻描述有维度名称"""
    tmpdir = tempfile.mkdtemp()
    try:
        eng = HexagramEngine(tmpdir)
        # 制造情绪变化
        eng.current_lines = [1, 1, 1, 1, 1, 1]
        eng._save_state()

        msgs = ["好焦虑啊", "迷茫不知道做什么", "完全搞不懂"]
        result = eng.divine(msgs, 0.3)

        display = result["display"]
        # 应包含维度名称
        dimension_found = False
        for dim_name in ["情绪基底", "行动力", "认知清晰度", "资源状态", "方向感", "整体满意度"]:
            if dim_name in display:
                dimension_found = True
                break
        assert dimension_found, "变爻描述中缺少维度名称"
        print("  ✅ 变爻维度名称测试通过")
        return True
    finally:
        shutil.rmtree(tmpdir)


def test_multiple_rounds():
    """模拟多轮对话推演"""
    tmpdir = tempfile.mkdtemp()
    try:
        eng = HexagramEngine(tmpdir)
        scenarios = [
            (["我在做AI", "有信心"], 0.7, "积极开局"),
            (["有点焦虑", "不知道行不行"], 0.4, "开始怀疑"),
            (["没钱了", "不知道做什么"], 0.2, "低谷"),
            (["决定了就做这个", "开始执行"], 0.6, "恢复"),
            (["找到用户了", "有反馈了"], 0.8, "上升"),
        ]

        all_msgs = []
        for msgs, rate, label in scenarios:
            all_msgs.extend(msgs)
            # 每3轮推演一次（模拟实际逻辑）
            round_count = len(all_msgs) // 2
            if round_count >= 3 and round_count % 3 == 0:
                result = eng.divine(all_msgs, rate)
                print(f"  [{label}] {result['current']['name']} → {result['future']['name']} "
                      f"变爻:{result['changing_lines']}")
            else:
                eng.update_from_conversation(all_msgs, rate)
                print(f"  [{label}] {eng.current_hexagram} (非推演轮)")

        print("  ✅ 多轮推演测试通过")
        return True
    finally:
        shutil.rmtree(tmpdir)


def main():
    print("=" * 55)
    print("  TaijiOS Lite — 变爻推演系统测试")
    print("=" * 55)

    tests = [
        ("基础推演", test_basic_divine),
        ("无自然变爻", test_no_change_divine),
        ("转变推演", test_transition_insights),
        ("展示格式", test_display_format),
        ("变爻维度", test_line_names),
        ("多轮推演", test_multiple_rounds),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        print(f"\n{'─' * 55}")
        print(f"  测试: {name}")
        print(f"{'─' * 55}")
        try:
            if fn():
                passed += 1
            else:
                failed += 1
                print(f"  ❌ {name} 失败")
        except Exception as e:
            failed += 1
            print(f"  ❌ {name} 异常: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'═' * 55}")
    print(f"  结果: {passed}/{passed + failed} 通过")
    if failed == 0:
        print(f"  ✅ 变爻推演系统全部测试通过")
    else:
        print(f"  ⚠️ {failed}个测试失败")
    print(f"{'═' * 55}")


if __name__ == "__main__":
    main()
