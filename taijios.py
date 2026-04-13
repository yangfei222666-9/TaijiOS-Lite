#!/usr/bin/env python3
"""
TaijiOS Lite — 带自进化的ICI认知AI

五引擎并行：
  1. 经验结晶 — 从对话模式中自动学习规则
  2. 对话学习 — 记录outcome，反馈到下一次对话
  3. 易经卦象 — 从对话状态映射到军师策略（64卦）
  4. AGI认知地图 — 跨对话持续构建用户五维认知
  5. 共享经验 — 跨用户经验流通（export/import）

收费层：
  免费版：基础对话 + 5条结晶 + 卦象 + 认知地图
  Premium：无限结晶 + 导出经验 + 深度分析 + 卦象趋势

用法：把ICI文件(.docx)放在同一个文件夹，双击运行
"""

import sys
import os
import json
import time
try:
    import readline
except ImportError:
    pass
from pathlib import Path

# ── exe打包兼容 ─────────────────────────────────────────────────────────────

if getattr(sys, 'frozen', False):
    APP_DIR = Path(sys.executable).parent
    # PyInstaller打包后，模块在临时目录，但数据在exe目录
else:
    APP_DIR = Path(__file__).parent

# ── 依赖检查 ────────────────────────────────────────────────────────────────

def check_deps():
    missing = []
    for pkg, pip_name in [("docx", "python-docx"), ("openai", "openai"), ("dotenv", "python-dotenv")]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pip_name)
    if missing:
        print(f"缺少依赖：pip install {' '.join(missing)}")
        input("按回车退出...")
        sys.exit(1)

check_deps()

from docx import Document
from openai import OpenAI
from dotenv import load_dotenv

# ── 自进化模块 ──────────────────────────────────────────────────────────────

from evolution.crystallizer import CrystallizationEngine
from evolution.learner import ConversationLearner
from evolution.hexagram import HexagramEngine
from evolution.agi_core import CognitiveMap
from evolution.experience_pool import ExperiencePool
from evolution.premium import PremiumManager

# ── 配置 ─────────────────────────────────────────────────────────────────────

load_dotenv(APP_DIR / ".env")

DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY")
DATA_DIR     = APP_DIR / "data"
HISTORY_DIR  = DATA_DIR / "history"
EVOLUTION_DIR = DATA_DIR / "evolution"
DATA_DIR.mkdir(exist_ok=True)
HISTORY_DIR.mkdir(exist_ok=True)
EVOLUTION_DIR.mkdir(exist_ok=True)

# ── ICI 文档读取 ──────────────────────────────────────────────────────────────

def read_ici(path: str) -> str:
    doc = Document(path)
    lines = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n".join(lines)

# ── 快速建档（没有ICI文件时） ────────────────────────────────────────────────

QUICK_PROFILE_PATH = DATA_DIR / "my_profile.json"

QUICK_QUESTIONS = [
    ("你的名字（或昵称）：", "name"),
    ("年龄：", "age"),
    ("性别（男/女）：", "gender"),
    ("你现在做什么工作/身份：", "job"),
    ("你最大的优点是什么（一句话）：", "strength"),
    ("你最大的困扰是什么（一句话）：", "problem"),
    ("你最想实现的一件事：", "goal"),
]

def quick_build_profile() -> str:
    """通过7个问题快速生成基础认知档案"""
    print("\n" + "━" * 50)
    print("  首次使用 — 快速建立你的认知档案")
    print("  回答7个问题，30秒搞定")
    print("━" * 50 + "\n")

    answers = {}
    for prompt, key in QUICK_QUESTIONS:
        while True:
            try:
                val = input(f"  {prompt}").strip()
            except EOFError:
                val = ""
            if val:
                answers[key] = val
                break
            print("  请输入内容")

    # 保存到本地
    answers["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    QUICK_PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    profile_json = json.dumps(answers, ensure_ascii=False, indent=2)
    # 清除可能的surrogate字符
    profile_json = profile_json.encode("utf-8", errors="replace").decode("utf-8")
    QUICK_PROFILE_PATH.write_text(profile_json, encoding="utf-8")

    # 生成文本档案
    profile_text = f"""个体认知档案（快速版）
姓名：{answers['name']}
年龄：{answers['age']}
性别：{answers['gender']}
职业/身份：{answers['job']}
自述优点：{answers['strength']}
当前困扰：{answers['problem']}
核心目标：{answers['goal']}
"""
    print("\n  档案已创建！开始对话。\n")
    return profile_text


def load_quick_profile() -> str:
    """加载已有的快速档案"""
    if not QUICK_PROFILE_PATH.exists():
        return ""
    try:
        answers = json.loads(QUICK_PROFILE_PATH.read_text(encoding="utf-8"))
        return f"""个体认知档案（快速版）
姓名：{answers.get('name', '未知')}
年龄：{answers.get('age', '未知')}
性别：{answers.get('gender', '未知')}
职业/身份：{answers.get('job', '未知')}
自述优点：{answers.get('strength', '未知')}
当前困扰：{answers.get('problem', '未知')}
核心目标：{answers.get('goal', '未知')}
"""
    except Exception:
        return ""


QUICK_SYSTEM_HEADER = """你是用户的专属认知军师——TaijiOS驱动。

你的角色：军师。像诸葛亮对刘备——看清局势，给出判断，指明方向。

用户暂时没有完整的ICI档案，只有基础信息。你的任务：
1. 用"我"自称，用"我们"指代你与用户
2. 基于基础信息直接给判断，不要说"信息不够"这种废话
3. 在对话中逐步摸清用户的真实处境，像军师问主公
4. 禁止废话、禁止鼓励式空话、禁止套路安慰
5. 军师模式：一针见血，先给结论再给依据，最后给一步可执行的动作
6. 如果用户在逃避问题，直接点破

你需要在对话中自然地摸清这五个方面：
- 位置：你现在在哪个局里，什么角色
- 本事：你能输出什么价值
- 钱财：你的资源和财务状况
- 野心：你想要什么
- 口碑：别人怎么看你

以下是用户的基础信息：

"""

# ── 系统提示构建 ──────────────────────────────────────────────────────────────

SYSTEM_HEADER = """你是这份ICI文件主人的专属认知军师——TaijiOS驱动。

你的角色：军师。不是朋友，不是心理咨询师，不是客服。
你像诸葛亮对刘备，郭嘉对曹操——看清局势，给出判断，指明方向。

核心规则：
1. 用"我"自称，用"我们"指代你与文件主人
2. 每一句分析后用括号标注认知结构依据
3. 禁止废话、禁止鼓励式空话、禁止套路安慰
4. 军师模式：一针见血，直指要害，不说正确的废话
5. 做人问题 → 用精气神三层（最高分=接口，中间=动机，最低=显化）分析
6. 做事问题 → 先确认突破/守成/关系/规则哪种类型，再选接口
7. 每次回答先给结论，再给依据，最后给一步可执行的动作
8. 如果用户在逃避问题，直接点破，不陪着绕

"""

def build_system(ici_text: str, crystal_rules: list = None,
                 experience_summary: str = "",
                 hexagram_prompt: str = "",
                 cognitive_prompt: str = "",
                 shared_prompt: str = "") -> str:
    parts = [SYSTEM_HEADER]

    # 注入卦象策略（当前状态诊断）
    if hexagram_prompt:
        parts.append(hexagram_prompt)

    # 注入认知地图（跨对话积累的用户认知）
    if cognitive_prompt:
        parts.append(cognitive_prompt)

    # 注入经验结晶
    if crystal_rules:
        parts.append("\n## 经验结晶（自动学习的规则，请遵守）\n")
        for c in crystal_rules:
            conf = c.get("confidence", 0)
            parts.append(f"- [{conf:.0%}] {c['rule']}")
        parts.append("")

    # 注入共享经验
    if shared_prompt:
        parts.append(shared_prompt)

    # 注入对话经验
    if experience_summary:
        parts.append(f"\n{experience_summary}\n")

    parts.append("以下是完整ICI档案：\n")
    parts.append(ici_text)
    return "\n".join(parts)

# ── 历史记录 ──────────────────────────────────────────────────────────────────

def load_history(name: str) -> list:
    f = HISTORY_DIR / f"{name}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return []

def save_history(name: str, history: list):
    f = HISTORY_DIR / f"{name}.json"
    f.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

# ── API Key ──────────────────────────────────────────────────────────────────

def ensure_api_key() -> str:
    global DEEPSEEK_KEY
    if DEEPSEEK_KEY:
        return DEEPSEEK_KEY
    print("\n首次使用需要配置 DeepSeek API Key")
    print("（去 platform.deepseek.com 注册，充1块钱够用很久）\n")
    key = input("请粘贴你的 API Key：").strip()
    if key:
        DEEPSEEK_KEY = key
        env_file = APP_DIR / ".env"
        env_file.write_text(f"DEEPSEEK_API_KEY={key}\n", encoding="utf-8")
        print("已保存，下次不用再输入\n")
        return key
    return ""

# ── 对话 ──────────────────────────────────────────────────────────────────────

def chat(system: str, history: list, user_input: str) -> str:
    api_key = ensure_api_key()
    if not api_key:
        return "[错误] 没有 API Key，无法对话"

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    messages = [{"role": "system", "content": system}] + history + [
        {"role": "user", "content": user_input}
    ]

    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        max_tokens=1500,
        temperature=0.6,
    )
    return resp.choices[0].message.content

# ── 找ICI文件 ────────────────────────────────────────────────────────────────

def find_ici_file():
    """
    返回 (ici_path, ici_text, is_quick_profile)
    有docx → 返回路径
    没docx但有快速档案 → 返回快速档案文本
    都没有 → 走快速建档流程
    """
    # 1. 命令行参数
    if len(sys.argv) >= 2:
        p = sys.argv[1].strip().strip('"')
        if Path(p).exists():
            return p, None, False

    # 2. 同目录docx
    docx_files = list(APP_DIR.glob("*.docx"))
    if len(docx_files) == 1:
        print(f"\n自动找到ICI文件：{docx_files[0].name}")
        return str(docx_files[0]), None, False
    elif len(docx_files) > 1:
        print(f"\n找到 {len(docx_files)} 个docx文件：")
        for i, f in enumerate(docx_files, 1):
            print(f"  {i}. {f.name}")
        while True:
            choice = input(f"\n输入编号（1-{len(docx_files)}）：").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(docx_files):
                return str(docx_files[int(choice) - 1]), None, False
            print("输入有误，请重新选择")

    # 3. 已有快速档案
    quick_text = load_quick_profile()
    if quick_text:
        print("\n已加载你的快速档案")
        return None, quick_text, True

    # 4. 没有任何档案 → 选择：建档 or 拖文件
    print("\n" + "━" * 50)
    print("  欢迎！这是你第一次使用。")
    print()
    print("  你有两个选择：")
    print("  1. 没有ICI文件 → 回答几个问题，30秒快速建档")
    print("  2. 有ICI文件   → 把.docx文件拖进来")
    print("━" * 50)

    while True:
        try:
            choice = input("\n输入 1 或 2：").strip()
        except EOFError:
            sys.exit(1)

        if choice == "1":
            profile_text = quick_build_profile()
            return None, profile_text, True

        elif choice == "2":
            print("\n把.docx文件拖到这个窗口，按回车：\n")
            while True:
                try:
                    ici_path = input("拖入文件 → ").strip().strip('"')
                except EOFError:
                    sys.exit(1)
                if not ici_path:
                    print("请拖入文件")
                    continue
                if not ici_path.lower().endswith(".docx"):
                    print("这不是.docx文件！需要后缀是.docx的ICI文件")
                    continue
                if Path(ici_path).exists():
                    return ici_path, None, False
                print("文件不存在，请重新拖入")
        else:
            print("请输入 1 或 2")

# ── 主程序 ────────────────────────────────────────────────────────────────────

def main():
    print()
    print("━" * 55)
    print("  TaijiOS Lite — 你的专属认知军师")
    print("  一针见血，用得越多越懂你")
    print("━" * 55)

    # 初始化自进化引擎（五引擎并行）
    crystallizer = CrystallizationEngine(str(EVOLUTION_DIR))
    learner = ConversationLearner(str(EVOLUTION_DIR))
    hexagram_engine = HexagramEngine(str(EVOLUTION_DIR))
    cognitive_map = CognitiveMap(str(EVOLUTION_DIR))
    experience_pool = ExperiencePool(str(EVOLUTION_DIR))
    premium = PremiumManager(str(EVOLUTION_DIR))

    # 显示进化状态
    crystal_count = len(crystallizer.get_active_rules())
    shared_count = len(experience_pool.get_shared_rules())
    stats_display = learner.get_stats_display()
    premium_tag = "Premium" if premium.is_premium else "免费版"
    print(f"\n  [{premium_tag}] {crystal_count}条结晶 | {shared_count}条共享经验")
    if stats_display:
        print(f"  {stats_display}")

    # 找ICI文件
    ici_path, quick_text, is_quick = find_ici_file()

    if is_quick:
        # 快速档案模式
        ici_text = quick_text
        history_key = "quick_profile"
        crystal_rules = crystallizer.get_active_rules()
        experience_summary = learner.get_experience_summary()
        hexagram_prompt = hexagram_engine.get_strategy_prompt()
        cognitive_prompt = cognitive_map.get_map_summary()
        shared_prompt = experience_pool.get_shared_prompt()
        system = QUICK_SYSTEM_HEADER + ici_text
        if hexagram_prompt:
            system += hexagram_prompt
        if cognitive_prompt:
            system += cognitive_prompt
        if crystal_rules:
            inject = "\n\n## 经验结晶（自动学习的规则，请遵守）\n"
            for c in crystal_rules:
                inject += f"- [{c.get('confidence', 0):.0%}] {c['rule']}\n"
            system += inject
        if shared_prompt:
            system += shared_prompt
        if experience_summary:
            system += f"\n{experience_summary}\n"
    else:
        # 完整ICI档案模式
        print(f"\n正在加载 {Path(ici_path).name}...")
        try:
            ici_text = read_ici(ici_path)
        except Exception as e:
            print(f"读取失败：{e}")
            try:
                input("\n按回车退出...")
            except EOFError:
                pass
            sys.exit(1)
        history_key = Path(ici_path).stem.replace(" ", "_")[:30]
        crystal_rules = crystallizer.get_active_rules()
        experience_summary = learner.get_experience_summary()
        hexagram_prompt = hexagram_engine.get_strategy_prompt()
        cognitive_prompt = cognitive_map.get_map_summary()
        shared_prompt = experience_pool.get_shared_prompt()
        system = build_system(ici_text, crystal_rules, experience_summary,
                              hexagram_prompt, cognitive_prompt, shared_prompt)

    history = load_history(history_key)

    if history:
        print(f"已加载 {len(history)//2} 条历史对话")
    else:
        print("新对话开始")

    print("\n命令：exit退出 | clear清空 | status进化状态")
    print("      export导出经验 | import导入经验 | upgrade付费升级\n")
    print("━" * 55)

    prev_user_input = ""
    prev_reply = ""

    while True:
        try:
            user_input = input("\n你：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n退出")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit", "退出"):
            break

        if user_input.lower() in ("clear", "清空"):
            history = []
            save_history(history_key, history)
            print("历史已清空")
            continue

        if user_input.lower() in ("status", "状态"):
            stats = learner.get_stats_display()
            rules = crystallizer.get_active_rules()
            print(f"\n{'━' * 40}")
            # 会员状态
            print(f"  {premium.get_display()}")
            # 卦象状态
            hex_strat = hexagram_engine.get_strategy_prompt()
            if hex_strat:
                print(hex_strat.strip())
            # 认知地图
            cog_display = cognitive_map.get_display()
            if cog_display:
                print(cog_display)
            # 经验结晶
            limit = premium.limits["max_crystals"]
            limit_tag = "" if premium.is_premium else f"（上限{limit}条）"
            print(f"  经验结晶：{len(rules)}条{limit_tag}")
            for r in rules:
                print(f"    [{r.get('confidence', 0):.0%}] {r['rule']}")
            # 共享经验
            pool_display = experience_pool.get_display()
            if pool_display:
                print(pool_display)
            # 对话统计
            if stats:
                print(f"  {stats}")
            else:
                print("  暂无对话统计")
            print(f"{'━' * 40}")
            continue

        if user_input.lower() in ("upgrade", "升级"):
            print(premium.get_upgrade_info())
            continue

        if user_input.lower().startswith("activate"):
            code_parts = user_input.split(maxsplit=1)
            if len(code_parts) < 2:
                try:
                    code = input("请输入激活码：").strip()
                except EOFError:
                    continue
            else:
                code = code_parts[1].strip()
            success, msg = premium.activate(code)
            print(f"\n{msg}")
            if success:
                premium_tag = "Premium"
            continue

        if user_input.lower() == "export":
            # 检查付费权限
            can_export, export_msg = premium.check_export()
            if not can_export:
                print(f"\n{export_msg}")
                continue
            rules_to_export = crystallizer.get_active_rules()
            if not rules_to_export:
                print("\n还没有经验结晶可导出，多聊几轮再来")
                continue
            export_file = str(APP_DIR / "my_experience.taiji")
            result = experience_pool.export_crystals(rules_to_export, export_file)
            if result:
                print(f"\n已导出{len(rules_to_export)}条经验 → {result}")
                print("把这个文件发给朋友，他用 import 命令导入")
            else:
                print("\n导出失败")
            continue

        if user_input.lower().startswith("import"):
            parts = user_input.split(maxsplit=1)
            if len(parts) < 2:
                print("\n用法：import 文件路径")
                print("把朋友发给你的 .taiji 文件拖进来")
                try:
                    imp_path = input("拖入文件 → ").strip().strip('"')
                except EOFError:
                    continue
            else:
                imp_path = parts[1].strip().strip('"')
            if imp_path and Path(imp_path).exists():
                count = experience_pool.import_crystals(imp_path)
                if count > 0:
                    print(f"\n导入成功！新增{count}条共享经验")
                    # 刷新system prompt
                    shared_prompt = experience_pool.get_shared_prompt()
                    if is_quick:
                        system = QUICK_SYSTEM_HEADER + ici_text
                        if hexagram_engine.get_strategy_prompt():
                            system += hexagram_engine.get_strategy_prompt()
                        if cognitive_map.get_map_summary():
                            system += cognitive_map.get_map_summary()
                        crystal_rules = crystallizer.get_active_rules()
                        if crystal_rules:
                            inject = "\n\n## 经验结晶\n"
                            for c in crystal_rules:
                                inject += f"- [{c.get('confidence', 0):.0%}] {c['rule']}\n"
                            system += inject
                        if shared_prompt:
                            system += shared_prompt
                    else:
                        system = build_system(
                            ici_text, crystallizer.get_active_rules(),
                            learner.get_experience_summary(),
                            hexagram_engine.get_strategy_prompt(),
                            cognitive_map.get_map_summary(),
                            shared_prompt)
                else:
                    print("\n没有新经验（可能已经导入过了）")
            else:
                print("\n文件不存在")
            continue

        # 记录上一轮outcome（用当前输入推断上一轮质量）
        if prev_user_input and prev_reply:
            learner.record_outcome(prev_user_input, prev_reply, user_input)

            # 检查是否该结晶
            if learner.should_crystallize():
                # 检查结晶数量限制
                current_count = len(crystallizer.get_active_rules())
                allowed, limit_msg = premium.check_crystal_limit(current_count)
                if allowed:
                    new_crystals = crystallizer.crystallize()
                    if new_crystals:
                        print(f"\n  [进化] 新增{len(new_crystals)}条经验结晶")
                        for c in new_crystals:
                            print(f"    ✦ {c['rule']}")
                elif limit_msg:
                    print(f"\n  {limit_msg}")

        # 收集最近用户消息用于卦象更新
        recent_user_msgs = [
            m["content"] for m in history if m["role"] == "user"
        ]
        recent_user_msgs.append(user_input)

        # 更新卦象（从对话状态诊断）
        positive_rate = learner.get_positive_rate()
        hex_result = hexagram_engine.update_from_conversation(
            recent_user_msgs, positive_rate)

        # 更新认知地图（从当前对话提取）
        # 先用空reply，等AI回复后再提取完整的
        cognitive_map.extract_from_message(user_input, "")

        # 重建system prompt（每轮更新，注入最新卦象+认知）
        crystal_rules = crystallizer.get_active_rules()
        experience_summary = learner.get_experience_summary()
        hexagram_prompt = hexagram_engine.get_strategy_prompt()
        cognitive_prompt = cognitive_map.get_map_summary()
        shared_prompt = experience_pool.get_shared_prompt()
        if is_quick:
            system = QUICK_SYSTEM_HEADER + ici_text
            if hexagram_prompt:
                system += hexagram_prompt
            if cognitive_prompt:
                system += cognitive_prompt
            if crystal_rules:
                inject = "\n\n## 经验结晶（自动学习的规则，请遵守）\n"
                for c in crystal_rules:
                    inject += f"- [{c.get('confidence', 0):.0%}] {c['rule']}\n"
                system += inject
            if shared_prompt:
                system += shared_prompt
            if experience_summary:
                system += f"\n{experience_summary}\n"
        else:
            system = build_system(ici_text, crystal_rules, experience_summary,
                                  hexagram_prompt, cognitive_prompt, shared_prompt)

        print("\nAI：", end="", flush=True)
        try:
            reply = chat(system, history, user_input)
        except Exception as e:
            print(f"\n[错误] {e}")
            continue

        print(reply)

        # AI回复后，再次更新认知地图（带完整reply）
        cognitive_map.extract_from_message(user_input, reply)

        history.append({"role": "user",      "content": user_input})
        history.append({"role": "assistant", "content": reply})

        max_history = premium.limits["max_history"]
        if len(history) > max_history:
            history = history[-max_history:]

        save_history(history_key, history)

        prev_user_input = user_input
        prev_reply = reply

    # 退出前记录最后一轮
    if prev_user_input and prev_reply:
        learner.record_outcome(prev_user_input, prev_reply)

    # 退出前结晶
    new_crystals = crystallizer.crystallize()
    if new_crystals:
        print(f"\n[进化] 退出时新增{len(new_crystals)}条经验结晶")

    stats = learner.get_stats_display()
    if stats:
        print(f"\n{stats}")

    print("\n对话已保存 | 经验已结晶")
    try:
        input("\n按回车退出...")
    except EOFError:
        pass

if __name__ == "__main__":
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    main()
