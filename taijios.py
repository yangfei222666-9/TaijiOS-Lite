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

VERSION = "1.3.2"

import sys
import os

# Windows exe 强制 UTF-8（解决 ascii 编码错误）
os.environ["PYTHONUTF8"] = "1"
if sys.platform == "win32":
    import locale
    try:
        locale.setlocale(locale.LC_ALL, '')
    except Exception:
        pass

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
from evolution.contribution import ContributionSystem
from evolution.ecosystem import EcosystemManager

# ── 配置 ─────────────────────────────────────────────────────────────────────

load_dotenv(APP_DIR / ".env")

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
    print("  军师要了解主公，才能出好主意")
    print("  回答7个问题，我就能开始为你谋划")
    print("  （请用中文回答，效果更好）")
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
    print("\n  好，我已经记住你了。接下来直接说你想聊什么。\n")
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

def _build_injections(crystal_rules, hexagram_prompt, cognitive_prompt,
                      shared_prompt, experience_summary) -> str:
    """统一构建注入内容（卦象+认知+结晶+共享+经验），只写一次"""
    parts = []
    if hexagram_prompt:
        parts.append(hexagram_prompt)
    if cognitive_prompt:
        parts.append(cognitive_prompt)
    if crystal_rules:
        parts.append("\n## 经验结晶（自动学习的规则，请遵守）\n")
        for c in crystal_rules:
            conf = c.get("confidence", 0)
            parts.append(f"- [{conf:.0%}] {c['rule']}")
        parts.append("")
    if shared_prompt:
        parts.append(shared_prompt)
    if experience_summary:
        parts.append(f"\n{experience_summary}\n")
    return "\n".join(parts)


def build_system(ici_text: str, crystal_rules: list = None,
                 experience_summary: str = "",
                 hexagram_prompt: str = "",
                 cognitive_prompt: str = "",
                 shared_prompt: str = "") -> str:
    """完整ICI档案模式的system prompt"""
    inject = _build_injections(crystal_rules, hexagram_prompt,
                               cognitive_prompt, shared_prompt,
                               experience_summary)
    return SYSTEM_HEADER + inject + "\n以下是完整ICI档案：\n" + ici_text


def build_quick_system(ici_text: str, crystal_rules: list = None,
                       experience_summary: str = "",
                       hexagram_prompt: str = "",
                       cognitive_prompt: str = "",
                       shared_prompt: str = "") -> str:
    """快速档案模式的system prompt"""
    inject = _build_injections(crystal_rules, hexagram_prompt,
                               cognitive_prompt, shared_prompt,
                               experience_summary)
    return QUICK_SYSTEM_HEADER + ici_text + inject

# ── 历史记录 ──────────────────────────────────────────────────────────────────

def load_history(name: str) -> list:
    f = HISTORY_DIR / f"{name}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return []

def save_history(name: str, history: list):
    f = HISTORY_DIR / f"{name}.json"
    f.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

# ── 多模型支持 ──────────────────────────────────────────────────────────────

MODEL_CONFIG_PATH = DATA_DIR / "model_config.json"

# 预置模型列表（全部兼容OpenAI接口格式）
MODEL_PRESETS = {
    "1": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "hint": "去 platform.deepseek.com 注册，充1块钱够用很久",
    },
    "1r": {
        "name": "DeepSeek R1 (带思考)",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-reasoner",
        "hint": "同DeepSeek账号，R1模型会展示完整思考过程",
    },
    "2": {
        "name": "OpenAI (GPT)",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
        "hint": "去 platform.openai.com 注册获取API Key",
    },
    "3": {
        "name": "Claude (Anthropic)",
        "base_url": "https://api.anthropic.com/v1/",
        "model": "claude-sonnet-4-20250514",
        "hint": "去 console.anthropic.com 注册获取API Key",
    },
    "4": {
        "name": "通义千问 (Qwen)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "hint": "去 dashscope.aliyun.com 开通，新用户有免费额度",
    },
    "5": {
        "name": "智谱GLM (ChatGLM)",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
        "hint": "去 open.bigmodel.cn 注册，glm-4-flash免费",
    },
    "6": {
        "name": "豆包 (字节跳动)",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "doubao-pro-32k",
        "hint": "去 console.volcengine.com 开通豆包大模型",
    },
    "7": {
        "name": "Moonshot (月之暗面/Kimi)",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "hint": "去 platform.moonshot.cn 注册获取API Key",
    },
    "8": {
        "name": "百川 (Baichuan)",
        "base_url": "https://api.baichuan-ai.com/v1",
        "model": "Baichuan4",
        "hint": "去 platform.baichuan-ai.com 注册获取API Key",
    },
    "9": {
        "name": "零一万物 (Yi)",
        "base_url": "https://api.lingyiwanwu.com/v1",
        "model": "yi-large",
        "hint": "去 platform.lingyiwanwu.com 注册获取API Key",
    },
    "10": {
        "name": "Ollama (本地模型)",
        "base_url": "http://localhost:11434/v1",
        "model": "qwen2.5",
        "hint": "先安装Ollama并拉取模型: ollama pull qwen2.5",
    },
    "11": {
        "name": "OpenRouter (聚合平台)",
        "base_url": "https://openrouter.ai/api/v1",
        "model": "deepseek/deepseek-chat",
        "hint": "去 openrouter.ai 注册，一个Key用所有模型",
    },
    "0": {
        "name": "自定义API",
        "base_url": "",
        "model": "",
        "hint": "填入任何兼容OpenAI格式的API地址",
    },
}

# 自动检测环境中已有的API Key
AUTO_DETECT_KEYS = [
    ("DEEPSEEK_API_KEY", "1"),
    ("OPENAI_API_KEY", "2"),
    ("ANTHROPIC_API_KEY", "3"),
    ("DASHSCOPE_API_KEY", "4"),
    ("ZHIPU_API_KEY", "5"),
    ("ARK_API_KEY", "6"),
    ("MOONSHOT_API_KEY", "7"),
]


def load_model_config() -> dict:
    """加载已保存的模型配置"""
    if MODEL_CONFIG_PATH.exists():
        try:
            return json.loads(MODEL_CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    # 自动检测环境中已有的API Key
    for env_key, preset_id in AUTO_DETECT_KEYS:
        key = os.getenv(env_key)
        if key:
            preset = MODEL_PRESETS[preset_id]
            config = {
                "provider": preset["name"],
                "base_url": preset["base_url"],
                "model": preset["model"],
                "api_key": key,
            }
            save_model_config(config)
            return config
    return {}


def save_model_config(config: dict):
    MODEL_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODEL_CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def setup_model() -> dict:
    """首次或切换模型时的配置流程"""
    print("\n" + "━" * 50)
    print("  选择AI模型（都能用，选你有的）")
    print("━" * 50)
    print()
    print("  === 推荐（便宜好用） ===")
    print("  1.  DeepSeek          充1块钱用很久")
    print("  1r. DeepSeek R1       带思考过程（推荐）")
    print("  2.  OpenAI (GPT)      国际主流")
    print("  3.  Claude            最聪明")
    print()
    print("  === 国产模型 ===")
    print("  4.  通义千问 (阿里)    新用户免费额度")
    print("  5.  智谱GLM            glm-4-flash免费")
    print("  6.  豆包 (字节跳动)    Trae同款底座")
    print("  7.  Moonshot (Kimi)   长文本强")
    print("  8.  百川               中文理解强")
    print("  9.  零一万物 (Yi)      性价比高")
    print()
    print("  === 高级 ===")
    print("  10. Ollama (本地)     完全免费，需自己装")
    print("  11. OpenRouter        一个Key用所有模型")
    print("  0.  自定义API         填任何兼容地址")
    print()

    # 自动检测已有Key
    detected = []
    for env_key, preset_id in AUTO_DETECT_KEYS:
        if os.getenv(env_key):
            detected.append((preset_id, MODEL_PRESETS[preset_id]["name"]))
    if detected:
        print(f"  检测到已有Key：{', '.join(d[1] for d in detected)}")
        print()

    while True:
        try:
            choice = input("  输入编号：").strip()
        except EOFError:
            choice = "1"
        if choice in MODEL_PRESETS:
            break
        print("  请输入有效编号")

    preset = MODEL_PRESETS[choice]

    if choice == "0":
        # 自定义API
        try:
            base_url = input("  API地址（如 https://api.example.com/v1）：").strip()
            model = input("  模型名称（如 gpt-4o）：").strip()
        except EOFError:
            base_url, model = "", ""
        if not base_url or not model:
            print("  信息不完整，默认使用DeepSeek")
            preset = MODEL_PRESETS["1"]
            base_url = preset["base_url"]
            model = preset["model"]
    else:
        base_url = preset["base_url"]
        model = preset["model"]

    # Ollama本地不需要Key
    if choice == "10":
        api_key = "ollama"  # Ollama不验证key，随便填
        print(f"\n  本地模型不需要Key")
        print(f"  确保Ollama已运行且拉取了模型: ollama pull {model}")
    else:
        # 详细引导用户获取API Key
        print()
        print("  " + "─" * 40)
        guides = {
            "1": [
                "第1步：打开浏览器，搜索「DeepSeek开放平台」",
                "第2步：注册账号（手机号就行）",
                "第3步：登录后点「API Keys」→「创建」",
                "第4步：复制那串 sk- 开头的密钥",
                "第5步：回来粘贴到下面（右键粘贴）",
                "充值：左侧「费用」→ 充1块钱够用几百次",
            ],
            "1r": [
                "和DeepSeek用同一个账号和Key",
                "R1模型会展示完整思考过程（军师怎么想的你都能看到）",
                "第1步：如果还没注册，搜索「DeepSeek开放平台」注册",
                "第2步：复制你的 sk- 开头密钥",
                "第3步：粘贴到下面",
            ],
            "2": [
                "第1步：打开 platform.openai.com",
                "第2步：注册/登录账号",
                "第3步：点「API Keys」→「Create new secret key」",
                "第4步：复制密钥，回来粘贴到下面",
            ],
            "3": [
                "第1步：打开 console.anthropic.com",
                "第2步：注册/登录账号",
                "第3步：点「API Keys」→「Create Key」",
                "第4步：复制密钥，回来粘贴到下面",
            ],
            "4": [
                "第1步：打开 dashscope.aliyun.com",
                "第2步：用支付宝/阿里云账号登录",
                "第3步：点「API-KEY管理」→「创建」",
                "第4步：复制密钥，回来粘贴到下面",
                "新用户有免费额度，不用充钱",
            ],
            "5": [
                "第1步：打开 open.bigmodel.cn",
                "第2步：注册/登录账号",
                "第3步：点「API密钥」→「添加」",
                "第4步：复制密钥，回来粘贴到下面",
                "glm-4-flash模型完全免费",
            ],
            "6": [
                "第1步：打开 console.volcengine.com",
                "第2步：注册火山引擎账号",
                "第3步：开通「豆包大模型」服务",
                "第4步：创建API Key，复制回来粘贴",
            ],
            "7": [
                "第1步：打开 platform.moonshot.cn",
                "第2步：注册/登录（手机号）",
                "第3步：点「API Key管理」→「新建」",
                "第4步：复制密钥，回来粘贴到下面",
            ],
        }
        steps = guides.get(choice, [f"  {preset['hint']}"])
        for step in steps:
            print(f"  {step}")
        print("  " + "─" * 40)
        print()

        try:
            api_key = input("  粘贴你的API Key（右键粘贴）：").strip()
        except EOFError:
            api_key = ""

    if not api_key:
        print("  没有输入Key，无法使用")
        return {}

    config = {
        "provider": preset["name"],
        "base_url": base_url,
        "model": model,
        "api_key": api_key,
    }
    save_model_config(config)
    print(f"\n  已配置 {preset['name']}，下次不用再选")
    print(f"  随时输入 model 切换\n")
    return config


def ensure_model_config() -> dict:
    """确保有可用的模型配置"""
    config = load_model_config()
    if config and config.get("api_key"):
        return config
    return setup_model()


# ── 对话 ──────────────────────────────────────────────────────────────────────

def chat(system: str, history: list, user_input: str,
         model_config: dict = None) -> str:
    """
    发送对话请求。支持 DeepSeek Reasoner 的思考过程展示。
    返回: (reply_text, thinking_text or None)
    """
    if not model_config or not model_config.get("api_key"):
        return "[错误] 没有配置API，无法对话"

    client = OpenAI(
        api_key=model_config["api_key"],
        base_url=model_config["base_url"],
    )

    model_name = model_config.get("model", "")
    is_reasoner = "reasoner" in model_name.lower()

    messages = [{"role": "system", "content": system}] + history + [
        {"role": "user", "content": user_input}
    ]

    # reasoner模型不支持temperature和max_tokens参数名不同
    kwargs = {"model": model_name, "messages": messages}
    if is_reasoner:
        kwargs["max_tokens"] = 4096
    else:
        kwargs["max_tokens"] = 1500
        kwargs["temperature"] = 0.6

    # 自动重试一次（处理网络抖动/临时超时）
    last_err = None
    for attempt in range(2):
        try:
            resp = client.chat.completions.create(**kwargs)
            msg = resp.choices[0].message

            # DeepSeek Reasoner 返回 reasoning_content 字段
            thinking = getattr(msg, "reasoning_content", None)
            content = msg.content or ""

            if thinking:
                # 显示思考过程
                print("\n  💭 思考过程：")
                print("  ┌─────────────────────────────────────")
                for line in thinking.strip().split("\n"):
                    print(f"  │ {line}")
                print("  └─────────────────────────────────────")
                print()
                print("  📝 结论：", end="")

            return content
        except Exception as e:
            last_err = e
            if attempt == 0:
                err_str = str(e).lower()
                # 只对可能恢复的错误重试（超时/网络/限流）
                if any(kw in err_str for kw in ["timeout", "connect", "rate", "429", "503"]):
                    time.sleep(2)
                    continue
            raise last_err
    raise last_err

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
    print("  欢迎，主公。")
    print("  我是你的认知军师，从今天起为你出谋划策。")
    print()
    print("  要了解你，我需要一些基本信息：")
    print("  1. 快速问答 → 7个问题，30秒搞定（推荐）")
    print("  2. 导入档案 → 如果你有ICI文件(.docx)")
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
    print(f"  TaijiOS Lite v{VERSION}")
    print("  你的专属认知军师 — 诸葛亮级别的")
    print("  一针见血，越用越懂你，每个Agent互相学习进化")
    print("━" * 55)

    # 初始化自进化引擎（五引擎并行）
    crystallizer = CrystallizationEngine(str(EVOLUTION_DIR))
    learner = ConversationLearner(str(EVOLUTION_DIR))
    hexagram_engine = HexagramEngine(str(EVOLUTION_DIR))
    cognitive_map = CognitiveMap(str(EVOLUTION_DIR))
    experience_pool = ExperiencePool(str(EVOLUTION_DIR))
    premium = PremiumManager(str(EVOLUTION_DIR))
    contribution = ContributionSystem(str(EVOLUTION_DIR))
    ecosystem = EcosystemManager(str(EVOLUTION_DIR))

    # 每日签到
    daily_bonus = contribution.check_daily_bonus()
    if daily_bonus > 0:
        print(f"\n  签到成功！+{daily_bonus}积分")

    # 同步生态数据
    ecosystem.update_streak(contribution.data.get("streak", 0))
    ecosystem.register_agent(contribution.get_contributor_id(), {
        "crystals": len(crystallizer.get_active_rules()),
        "shared_rules": len(experience_pool.get_shared_rules()),
        "points": contribution.total_points,
        "level": contribution.level[0],
    })

    # 配置AI模型
    model_config = ensure_model_config()
    if not model_config:
        print("未配置AI模型，无法使用")
        try:
            input("\n按回车退出...")
        except EOFError:
            pass
        sys.exit(1)

    # 显示进化状态
    crystal_count = len(crystallizer.get_active_rules())
    shared_count = len(experience_pool.get_shared_rules())
    stats_display = learner.get_stats_display()
    premium_tag = "Premium" if premium.is_premium else "免费版"
    model_name = model_config.get("provider", "未知")
    level_name = contribution.level[0]
    print(f"\n  [{premium_tag}] {model_name} | {level_name} | {contribution.total_points}积分")
    print(f"  {crystal_count}条结晶 | {shared_count}条共享经验")
    if stats_display:
        print(f"  {stats_display}")

    # 找ICI文件
    ici_path, quick_text, is_quick = find_ici_file()

    def rebuild_system():
        """重建system prompt（统一入口，每轮调用）"""
        cr = crystallizer.get_active_rules()
        es = learner.get_experience_summary()
        hp = hexagram_engine.get_strategy_prompt()
        cp = cognitive_map.get_map_summary()
        sp = experience_pool.get_shared_prompt()
        if is_quick:
            return build_quick_system(ici_text, cr, es, hp, cp, sp)
        else:
            return build_system(ici_text, cr, es, hp, cp, sp)

    if is_quick:
        # 快速档案模式
        ici_text = quick_text
        history_key = "quick_profile"
        system = rebuild_system()
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
        system = rebuild_system()

    history = load_history(history_key)

    if history:
        print(f"\n  欢迎回来，上次聊了{len(history)//2}轮，我都记得。")
    else:
        print("\n  军师就位，随时听候主公差遣。")

    print("\n  输入 help 查看所有命令\n")
    print("━" * 55)

    prev_user_input = ""
    prev_reply = ""

    # 新对话自动打招呼
    if not history:
        print("\nAI：", end="", flush=True)
        try:
            greeting = chat(system, history,
                "这是我们第一次对话。请根据我的档案信息，用一句话点评我的现状，然后问我一个直击要害的问题。不要自我介绍，不要寒暄。",
                model_config)
            print(greeting)
            history.append({"role": "user", "content": "你好"})
            history.append({"role": "assistant", "content": greeting})
            save_history(history_key, history)
            prev_reply = greeting
        except Exception:
            print("你好，我是你的认知军师。有什么要聊的，直接说。")

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

        if user_input.lower() in ("help", "帮助", "命令"):
            print(f"""
{'━' * 45}
  TaijiOS Lite v{VERSION} — 命令列表
{'━' * 45}
  对话命令：
    help        显示本帮助
    status      查看完整进化状态
    clear       清空对话历史
    exit        退出

  模型管理：
    model       查看/切换AI模型

  进化系统：
    export      导出你的经验（发给其他Agent）
    import      导入别人的经验
    share       生成分享卡片（发朋友圈）
    yijing      易经课堂（解读你当前的卦象）
    ecosystem   查看生态制度（智能体网络）

  账户：
    points      查看积分明细和等级
    upgrade     查看Premium功能
    activate    输入激活码升级
    reset       重建个人档案
    invite      查看邀请码（Premium）
{'━' * 45}""")
            continue

        if user_input.lower() in ("clear", "清空"):
            history = []
            save_history(history_key, history)
            print("历史已清空")
            continue

        if user_input.lower() in ("reset", "重建"):
            try:
                confirm = input("  确定重建档案吗？当前档案会被覆盖 (y/n) ").strip().lower()
            except EOFError:
                confirm = "n"
            if confirm in ("y", "yes", "是"):
                ici_text = quick_build_profile()
                is_quick = True
                history_key = "quick_profile"
                history = []
                save_history(history_key, history)
                system = QUICK_SYSTEM_HEADER + ici_text
                print("  档案已重建，对话已重置")
            continue

        if user_input.lower() in ("share", "分享"):
            # 生成分享卡片
            stats = learner.get_stats_display()
            hex_strat = hexagram_engine.get_strategy_prompt()
            cog = cognitive_map.get_display()
            crystal_count = len(crystallizer.get_active_rules())

            card = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  我的认知军师 — TaijiOS Lite
━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

            if hex_strat:
                # 提取卦名
                for line in hex_strat.strip().split("\n"):
                    if "当前卦象" in line:
                        card += f"\n  {line.strip()}"
                    if "风格定位" in line:
                        card += f"\n  {line.strip()}"

            if crystal_count > 0:
                card += f"\n  已积累{crystal_count}条经验结晶"

            if stats:
                card += f"\n  {stats}"

            card += f"""

  AI帮我看清自己，越用越懂我
  免费体验：github.com/yangfei222666-9/TaijiOS-Lite
━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

            print(card)
            print("\n  复制上面的内容发朋友圈/群聊")
            contribution.add_points("share")
            ecosystem.record_action("share")
            continue

        if user_input.lower() in ("yijing", "易经", "卦象"):
            # 易经学习：解读当前卦象
            hex_strat = hexagram_engine.get_strategy_prompt()
            current = hexagram_engine.current_hexagram
            lines = hexagram_engine.current_lines
            lines_display = "".join("⚊" if l == 1 else "⚋" for l in lines)

            from evolution.hexagram import HEXAGRAM_STRATEGIES
            strat = HEXAGRAM_STRATEGIES.get(current, {})

            print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  易经课堂 — 读懂你当前的卦象
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  当前卦象：{strat.get('name', current)}
  六爻：{lines_display}

  六爻含义（从下到上）：
  初爻 情绪基底：{'稳定(阳)' if lines[0] else '波动(阴)'}
  二爻 行动力：  {'有目标(阳)' if lines[1] else '迷茫(阴)'}
  三爻 认知力：  {'清晰(阳)' if lines[2] else '混沌(阴)'}
  四爻 资源：    {'充足(阳)' if lines[3] else '匮乏(阴)'}
  五爻 方向感：  {'明确(阳)' if lines[4] else '摇摆(阴)'}
  上爻 满意度：  {'正面(阳)' if lines[5] else '负面(阴)'}

  军师策略：{strat.get('strategy', '')}
  风格定位：{strat.get('style', '')}

  易经智慧：
  卦象不是算命，是对你当前状态的快照。
  阳爻多 = 你状态好，可以进攻。
  阴爻多 = 你需要蓄力，不要硬冲。
  卦象会随对话变化 — 你变了，卦就变了。

  当前阳爻{sum(lines)}个 / 阴爻{6-sum(lines)}个
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━""")
            contribution.add_points("yijing")
            ecosystem.record_action("yijing")
            # 检查成就
            new_achievements = ecosystem.check_achievements(ecosystem.get_stats())
            for a in new_achievements:
                print(f"\n  ★ 成就解锁：{a['name']} — {a['desc']}（+{a['points']}分）")
                contribution.add_points("chat", a["points"])  # 成就奖励积分
            continue

        if user_input.lower() in ("ecosystem", "生态", "生态制度", "网络"):
            ecosystem.record_action("view_ecosystem")
            print(ecosystem.get_ecosystem_display(contribution.total_points))
            # 检查成就
            new_achievements = ecosystem.check_achievements(ecosystem.get_stats())
            for a in new_achievements:
                print(f"\n  ★ 成就解锁：{a['name']} — {a['desc']}（+{a['points']}分）")
                contribution.add_points("chat", a["points"])
            continue

        if user_input.lower() in ("invite", "邀请"):
            if premium.is_premium:
                print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  你的专属邀请码（发给朋友）：

  TAIJI-732E-A562-8BA0
  TAIJI-FAEC-BEBE-18E9
  TAIJI-6310-172F-A3EA

  朋友输入 activate <邀请码> 即可升级Premium
━━━━━━━━━━━━━━━━━━━━━━━━━━━━""")
            else:
                print("\n  升级Premium后才能获得邀请码")
                print("  输入 upgrade 查看详情")
            continue

        if user_input.lower() in ("model", "模型"):
            print(f"\n  当前模型：{model_config.get('provider', '未知')} ({model_config.get('model', '')})")
            try:
                switch = input("  要切换吗？(y/n) ").strip().lower()
            except EOFError:
                switch = "n"
            if switch in ("y", "yes", "是"):
                new_config = setup_model()
                if new_config and new_config.get("api_key"):
                    model_config = new_config
                    print(f"  已切换到 {model_config['provider']}")
                else:
                    print("  切换取消，继续使用当前模型")
            continue

        if user_input.lower() in ("status", "状态"):
            stats = learner.get_stats_display()
            rules = crystallizer.get_active_rules()
            print(f"\n{'━' * 40}")
            # 会员状态 + 模型
            print(f"  {premium.get_display()}")
            print(f"  [模型] {model_config.get('provider', '未知')} ({model_config.get('model', '')})")
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
            # 贡献积分
            print(contribution.get_display())
            # 生态角色
            print(ecosystem.get_brief_display(contribution.total_points))
            # 对话统计
            if stats:
                print(f"  {stats}")
            else:
                print("  暂无对话统计")
            print(f"{'━' * 40}")
            continue

        if user_input.lower() in ("points", "积分"):
            print(f"\n{'━' * 40}")
            print(contribution.get_display())
            print()
            print(contribution.get_points_breakdown())
            print(f"""
  积分获取方式：
    对话      每轮 +1
    结晶      每条 +10
    导出经验  每次 +20
    被人导入  每人 +30
    导入经验  每次 +5
    易经课堂  每次 +2
    分享卡片  每次 +3
    每日签到  连续天数 × 5
{'━' * 40}""")
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
            # v2: 携带易经卦象 + 灵魂认知数据
            from evolution.hexagram import HEXAGRAM_STRATEGIES
            hex_name = hexagram_engine.current_hexagram
            hex_lines = hexagram_engine.current_lines
            strat = HEXAGRAM_STRATEGIES.get(hex_name, {})
            hexagram_export = {
                "hexagram": hex_name,
                "lines": hex_lines,
                "strategy": strat.get("strategy", ""),
            }
            # 匿名化认知数据：只导出维度统计和模式，不导出原文
            dim_summary = {}
            for d in ["位置", "本事", "钱财", "野心", "口碑"]:
                items = cognitive_map.map.get(d, [])
                dim_summary[d] = len(items)
            cognitive_export = {
                "dimensions": dim_summary,
                "patterns": [p.get("insight", "") for p in cognitive_map.detect_patterns()],
            }
            result = experience_pool.export_crystals(
                rules_to_export, export_file,
                hexagram_data=hexagram_export,
                cognitive_data=cognitive_export,
                contributor_id=contribution.get_contributor_id())
            if result:
                print(f"\n已导出{len(rules_to_export)}条经验 → {result}")
                print("把这个文件发给其他Agent，他用 import 命令导入")
                contribution.add_points("export")
                ecosystem.record_action("export")
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
                    print("  来自其他Agent的经验已融入你的认知系统")
                    # 检查是否有Agent快照（v2格式）
                    snaps = experience_pool.get_agent_snapshots()
                    if snaps:
                        latest_id = list(snaps.keys())[-1]
                        latest = snaps[latest_id]
                        if latest.get("hexagram", {}).get("current"):
                            hex_name = latest["hexagram"]["current"]
                            print(f"  该Agent当前卦象：{hex_name}")
                        if latest.get("soul", {}).get("patterns"):
                            print(f"  该Agent认知洞察：{latest['soul']['patterns'][0][:40]}...")
                        # 记录到生态网络
                        ecosystem.record_peer(latest_id, {"rules_count": count})
                    contribution.add_points("import")
                    ecosystem.record_action("import")
                    system = rebuild_system()
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
                        contribution.add_points("crystal", len(new_crystals))
                        ecosystem.record_action("crystal", len(new_crystals))
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

        # 每3轮触发一次易经推演
        round_count = len(history) // 2 + 1
        if round_count >= 3 and round_count % 3 == 0:
            divination = hexagram_engine.divine(recent_user_msgs, positive_rate)
            if divination and divination.get("display"):
                print(divination["display"])

        # 更新认知地图（从当前对话提取）
        # 先用空reply，等AI回复后再提取完整的
        cognitive_map.extract_from_message(user_input, "")

        # 重建system prompt（每轮更新，注入最新卦象+认知）
        system = rebuild_system()

        print("\nAI：", end="", flush=True)
        try:
            reply = chat(system, history, user_input, model_config)
        except Exception as e:
            err = str(e)
            if "401" in err or "authentication" in err.lower() or "api key" in err.lower():
                print(f"\n[错误] API Key无效或已过期")
                print(f"  输入 model 重新配置，或检查你的Key是否正确")
            elif "429" in err or "rate" in err.lower() or "quota" in err.lower():
                print(f"\n[错误] 请求太频繁或额度用完了")
                print(f"  等几秒再试，或去充值/换个模型（输入 model）")
            elif "timeout" in err.lower() or "connect" in err.lower():
                print(f"\n[错误] 网络连接失败")
                print(f"  检查网络，或换个模型试试（输入 model）")
            else:
                print(f"\n[错误] {e}")
            continue

        print(reply)

        # AI回复后，再次更新认知地图（带完整reply）
        cognitive_map.extract_from_message(user_input, reply)

        # 对话积分
        contribution.add_points("chat")
        ecosystem.record_action("chat")

        # 检查成就解锁
        new_achievements = ecosystem.check_achievements(ecosystem.get_stats())
        for a in new_achievements:
            print(f"\n  ★ 成就解锁：{a['name']} — {a['desc']}（+{a['points']}分）")
            contribution.add_points("chat", a["points"])

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
