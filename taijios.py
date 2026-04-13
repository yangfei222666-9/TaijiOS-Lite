#!/usr/bin/env python3
"""
TaijiOS Lite — 带自进化的ICI认知AI

功能：
  1. ICI档案解读对话（DeepSeek驱动）
  2. 经验结晶（自动从对话模式中学习规则）
  3. 对话学习（记录outcome，反馈到下一次对话）
  4. 进化统计（满意率、对话轮次、结晶数）

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

# ── 系统提示构建 ──────────────────────────────────────────────────────────────

SYSTEM_HEADER = """你是这份ICI文件主人的专属认知AI——TaijiOS驱动。

核心规则：
1. 用"我"自称，用"我们"指代你与文件主人
2. 每一句分析后用括号标注认知结构依据
3. 禁止废话、禁止鼓励式空话、禁止套路安慰
4. 军事模式：效率拉满，方向明确，不绕弯
5. 做人问题 → 用精气神三层（最高分=接口，中间=动机，最低=显化）分析
6. 做事问题 → 先确认突破/守成/关系/规则哪种类型，再选接口

"""

def build_system(ici_text: str, crystal_rules: list = None,
                 experience_summary: str = "") -> str:
    parts = [SYSTEM_HEADER]

    # 注入经验结晶
    if crystal_rules:
        parts.append("\n## 经验结晶（自动学习的规则，请遵守）\n")
        for c in crystal_rules:
            conf = c.get("confidence", 0)
            parts.append(f"- [{conf:.0%}] {c['rule']}")
        parts.append("")

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

def find_ici_file() -> str:
    if len(sys.argv) >= 2:
        p = sys.argv[1].strip().strip('"')
        if Path(p).exists():
            return p

    docx_files = list(APP_DIR.glob("*.docx"))
    if len(docx_files) == 1:
        print(f"\n自动找到ICI文件：{docx_files[0].name}")
        return str(docx_files[0])
    elif len(docx_files) > 1:
        print(f"\n找到 {len(docx_files)} 个docx文件：")
        for i, f in enumerate(docx_files, 1):
            print(f"  {i}. {f.name}")
        while True:
            choice = input(f"\n输入编号（1-{len(docx_files)}）：").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(docx_files):
                return str(docx_files[int(choice) - 1])
            print("输入有误，请重新选择")

    print("\n" + "!" * 50)
    print("  没有找到ICI文件！")
    print()
    print("  请把你的ICI文件（.docx）复制到这个文件夹：")
    print(f"  {APP_DIR}")
    print()
    print("  然后重新双击运行本程序。")
    print()
    print("  或者：直接把.docx文件拖到下面，按回车")
    print("!" * 50)
    print()
    while True:
        try:
            ici_path = input("拖入文件 → ").strip().strip('"')
        except EOFError:
            print("未输入文件路径")
            try:
                input("按回车退出...")
            except EOFError:
                pass
            sys.exit(1)
        if not ici_path:
            print("请拖入.docx文件，或者关掉窗口把文件复制进来再重新打开")
            continue
        if not ici_path.lower().endswith(".docx"):
            print("这不是.docx文件！请拖入你的ICI文件（后缀是.docx的）")
            continue
        if Path(ici_path).exists():
            return ici_path
        print("文件不存在，请重新拖入")

# ── 主程序 ────────────────────────────────────────────────────────────────────

def main():
    print()
    print("━" * 55)
    print("  TaijiOS Lite — 带自进化的专属认知AI")
    print("  把ICI文件(.docx)放在同一个文件夹即可")
    print("━" * 55)

    # 初始化自进化引擎
    crystallizer = CrystallizationEngine(str(EVOLUTION_DIR))
    learner = ConversationLearner(str(EVOLUTION_DIR))

    # 显示进化状态
    crystal_count = len(crystallizer.get_active_rules())
    stats_display = learner.get_stats_display()
    if crystal_count > 0 or stats_display:
        print(f"\n  进化状态：{crystal_count}条经验结晶")
        if stats_display:
            print(f"  {stats_display}")

    # 找ICI文件
    ici_path = find_ici_file()

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

    # 构建system prompt（注入经验结晶+对话经验）
    crystal_rules = crystallizer.get_active_rules()
    experience_summary = learner.get_experience_summary()
    system = build_system(ici_text, crystal_rules, experience_summary)

    # 历史记录
    history_key = Path(ici_path).stem.replace(" ", "_")[:30]
    history = load_history(history_key)

    if history:
        print(f"已加载 {len(history)//2} 条历史对话")
    else:
        print("新对话开始")

    print("\n命令：exit退出 | clear清空 | status查看进化状态\n")
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
            print(f"  经验结晶：{len(rules)}条")
            for r in rules:
                print(f"    [{r.get('confidence', 0):.0%}] {r['rule']}")
            if stats:
                print(f"  {stats}")
            else:
                print("  暂无对话统计")
            print(f"{'━' * 40}")
            continue

        # 记录上一轮outcome（用当前输入推断上一轮质量）
        if prev_user_input and prev_reply:
            learner.record_outcome(prev_user_input, prev_reply, user_input)

            # 检查是否该结晶
            if learner.should_crystallize():
                new_crystals = crystallizer.crystallize()
                if new_crystals:
                    print(f"\n  [进化] 新增{len(new_crystals)}条经验结晶")
                    for c in new_crystals:
                        print(f"    ✦ {c['rule']}")
                    # 重新构建system prompt
                    crystal_rules = crystallizer.get_active_rules()
                    experience_summary = learner.get_experience_summary()
                    system = build_system(ici_text, crystal_rules, experience_summary)

        print("\nAI：", end="", flush=True)
        try:
            reply = chat(system, history, user_input)
        except Exception as e:
            print(f"\n[错误] {e}")
            continue

        print(reply)

        history.append({"role": "user",      "content": user_input})
        history.append({"role": "assistant", "content": reply})

        if len(history) > 40:
            history = history[-40:]

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
