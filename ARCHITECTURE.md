# TaijiOS Lite — 架构全景 & 能力说明

> 每个TaijiOS实例 = 一个自进化智能体(Agent)
> 所有Agent组成认知进化网络，互相学习，越用越聪明

---

## 一句话说清楚

**TaijiOS是一个带自进化能力的AI认知军师。**
它不只是聊天机器人——它会从你的对话中自动学习规则、用易经诊断你的状态、跨对话构建你的认知地图、和其他Agent交换经验。用得越久，它越懂你。

---

## 系统全景图

```
用户
 │
 ▼
┌──────────────────────────────────────────────────┐
│  TaijiOS Lite v1.3.0                             │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ 经验结晶 │  │ 对话学习 │  │ 易经卦象 │       │
│  │ 引擎     │  │ 引擎     │  │ 引擎     │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
│       │             │             │              │
│       ▼             ▼             ▼              │
│  ┌─────────────────────────────────────┐         │
│  │         System Prompt 动态注入       │         │
│  │  结晶规则 + 卦象策略 + 认知地图      │         │
│  │  + 共享经验 + 对话历史               │         │
│  └─────────────────────────────────────┘         │
│       │             │             │              │
│       ▼             ▼             ▼              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ AGI认知  │  │ 共享经验 │  │ 生态系统 │       │
│  │ 地图     │  │ 池(v2)   │  │ 管理器   │       │
│  └──────────┘  └────┬─────┘  └──────────┘       │
│                     │                            │
│                     ▼                            │
│              .taiji 经验包                        │
│         (结晶 + 易经 + 灵魂)                      │
│                     │                            │
└─────────────────────┼────────────────────────────┘
                      │
                      ▼
              其他 TaijiOS Agent
              (导入 → 验证 → 进化)
```

---

## 八大引擎详解

### 1. 经验结晶引擎 `evolution/crystallizer.py`

**做什么：** 从对话模式中自动提取规则，注入到 system prompt。

```
用户反复在焦虑时跑题 → 系统发现模式 → 结晶：
  "用户焦虑时容易发散，应先锚定一个具体问题再展开"
```

- 三类结晶：避免类 / 保持类 / 发现类
- 置信度机制：被验证越多次，规则权重越高
- 自动触发：每10轮对话检查一次是否该结晶

**接入点：** 每轮对话后 `crystallizer.crystallize()` → 规则注入 `build_system()`

---

### 2. 对话学习引擎 `evolution/learner.py`

**做什么：** 用"下一句话"推断"上一轮回复"的质量。

```
AI说了一段分析 → 用户回"说得对" → 系统记录：上一轮=正面
AI说了一段分析 → 用户回"你没理解我" → 系统记录：上一轮=负面
```

- 记录到 `soul_outcomes.jsonl`
- 计算正面率 `get_positive_rate()` → 影响卦象上爻
- 生成经验摘要 `get_experience_summary()` → 注入 system prompt

**接入点：** 每轮对话开始时 `learner.record_outcome(prev_input, prev_reply, current_input)`

---

### 3. 易经卦象引擎 `evolution/hexagram.py`

**做什么：** 把对话状态映射到64卦，动态切换军师策略。

```
六爻对应六个维度：
  初爻 = 情绪基底（稳定/焦虑）
  二爻 = 行动力（有目标/迷茫）
  三爻 = 认知清晰度（清晰/混沌）
  四爻 = 资源状态（充足/匮乏）
  五爻 = 方向感（明确/摇摆）
  上爻 = 整体满意度（正面率决定）

每爻 = 阳(1) 或 阴(0) → 6位二进制 → 64种状态 → 映射到16种核心策略
```

**16种军师策略：**
| 卦名 | 风格 | 触发条件 |
|------|------|----------|
| 乾 | 进攻型：放手干 | 全阳或接近全阳 |
| 坤 | 防守型：先稳住 | 全阴或接近全阴 |
| 屯 | 启动型：从0到1 | 有方向但资源不足 |
| 蒙 | 启蒙型：先搞清楚 | 认知混沌 |
| 需 | 等待型：时机未到 | 资源不够，方向有 |
| 讼 | 调解型：先解决冲突 | 情绪波动+行动受阻 |
| 师 | 统帅型：带兵打仗 | 有资源有方向 |
| 比 | 联盟型：找人帮忙 | 缺资源但有口碑 |
| 观 | 点破型：看破不说破 | 认知有但不行动 |
| 剥 | 止损型：该放手了 | 多维度消极 |
| 复 | 复苏型：重新开始 | 情绪回暖 |
| 困 | 破局型：逆境突围 | 资源匮乏但有野心 |
| 渐 | 稳进型：一步一步来 | 稳定但缓慢 |
| 既济 | 居安型：别浪 | 状态好但满意度低 |
| 未济 | 冲刺型：最后一步 | 接近目标差临门一脚 |
| 涣 | 聚焦型：收心 | 散乱分心 |

**接入点：** 每轮 `hexagram.update_from_conversation()` → `get_strategy_prompt()` → 注入 system prompt

---

### 4. AGI认知地图 `evolution/agi_core.py`

**做什么：** 跨对话持续构建用户的五维认知档案，发现盲区和矛盾。

```
五个维度（来自ICI框架）：
  位置 — 你在什么局里，什么角色
  本事 — 你能输出什么价值
  钱财 — 你的资源和财务状况
  野心 — 你想要什么
  口碑 — 别人怎么看你
```

**三层进化：**
- L1 记忆层：从对话中提取关键信息到对应维度
- L2 推理层：跨维度发现矛盾（有野心没本事=焦虑源、有口碑没位置=浪费）
- L3 预判层：五维交叉分析主动推送洞察

**接入点：** 每轮 `cognitive_map.extract_from_message()` → `get_map_summary()` → 注入 system prompt

---

### 5. 共享经验池 `evolution/experience_pool.py`

**做什么：** 让Agent之间互相学习。v2格式携带易经+灵魂数据。

```
导出流程：
  你的结晶规则 + 当前卦象 + 认知模式 → .taiji文件 (v2)

导入流程：
  .taiji文件 → 规则以60%置信度入池 → 被多人验证 → 置信度上升
  同时存储来源Agent的卦象和灵魂快照 → 交叉验证

.taiji v2 文件结构：
{
  "format": "taiji_experience_v2",
  "agent_id": "abc12345",
  "crystals": [...经验规则...],
  "hexagram": {当前卦象快照},
  "soul": {认知模式（已匿名）}
}
```

**信任机制：**
- 新导入规则置信度 = 原始 × 0.6（最低0.3）
- 每多一个Agent验证 → 置信度 +0.05（上限0.95）
- 置信度 < 0.4 的规则不注入 system prompt

**接入点：** export/import 命令 → `get_shared_prompt()` → 注入 system prompt

---

### 6. Premium付费层 `evolution/premium.py`

**做什么：** 免费版限功能，激活码解锁全部。

| 功能 | 免费版 | Premium |
|------|--------|---------|
| 经验结晶 | 5条上限 | 无限 |
| 导出经验 | 不可 | 可以 |
| 对话历史 | 20轮 | 40轮 |
| 深度分析 | 不可 | 可以 |
| 卦象趋势 | 不可 | 可以 |

**激活码体系：** SHA256(seed + "taiji_premium_2024") → 格式 TAIJI-XXXX-XXXX-XXXX

---

### 7. 贡献积分系统 `evolution/contribution.py`

**做什么：** 量化每个Agent的贡献，驱动成长。

| 行为 | 积分 |
|------|------|
| 每轮对话 | +1 |
| 产出结晶 | +10 |
| 导出经验 | +20 |
| 被人导入 | +30/人 |
| 导入经验 | +5 |
| 易经课堂 | +2 |
| 分享卡片 | +3 |
| 每日签到 | 连续天数 × 5 |

**五级体系：**
```
Lv1 新兵（0分）    → 刚开始了解自己
Lv2 校尉（50分）   → 开始有认知积累
Lv3 将军（200分）  → 认知地图初步成型
Lv4 军师（500分）  → 经验丰富，可以帮别人
Lv5 国士（1000分） → 认知进化的先行者
```

---

### 8. 生态制度 `evolution/ecosystem.py`

**做什么：** 把所有Agent组成一个有规则的进化网络。

**Agent网络机制：**
```
Agent A 对话进化 → 经验结晶 → 导出 .taiji
                                  ↓
Agent B 导入 → 验证 → 置信度↑ → 融入认知
                                  ↓
Agent C 导入 A+B → 交叉验证 → 全网经验质量↑
                                  ↓
新Agent加入 → 直接继承最佳经验 → 起点更高
```

**16个成就：**
初出茅庐、言之有物、促膝长谈、知己知彼、初见端倪、集腋成裘、
乐善好施、兼收并蓄、桃李天下、三日不辍、七日精进、月度修行、
问道周易、易理初通、广而告之、生态觉醒

**5个生态角色：**
探索者 → 贡献者 → 传播者 → 导师 → 先行者

**六条铁律：**
1. 经验靠验证 — 被越多Agent采纳，质量越高
2. 分享越多越强 — 帮别人就是帮自己
3. 多样性优先 — 不同Agent交叉验证最有价值
4. 军师无废话 — 只保留真正有用的规则
5. 开放流通 — .taiji文件自由传播，无平台绑定
6. 随时迭代 — 每个Agent随时准备好接收新经验

---

## API 接口（前端/HUD/移动端对接）

`api_server.py` 提供完整的REST + WebSocket接口：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/chat` | POST | 对话（支持流式） |
| `/api/voice` | POST | 语音输入（预留ASR对接） |
| `/api/status` | GET | 完整进化状态 |
| `/api/hexagram` | GET | 当前卦象详情 |
| `/api/cognitive_map` | GET | 认知地图 |
| `/api/contribution` | GET | 积分信息 |
| `/api/ecosystem` | GET | 生态制度 + Agent网络 |
| `/api/hud` | GET | HUD轻量数据（桌面悬浮窗） |
| `/ws/chat` | WebSocket | 实时对话（文本+语音流） |

**HUD数据格式（30秒刷新）：**
```json
{
  "hexagram": "乾",
  "lines": "⚊⚊⚊⚊⚊⚊",
  "style": "进攻型军师",
  "level": "Lv2 校尉",
  "points": 85,
  "streak": 3,
  "positive_rate": 0.72
}
```

---

## 多模型兼容

支持12个AI提供商，全部走OpenAI兼容接口：

| 类别 | 提供商 |
|------|--------|
| 推荐 | DeepSeek、OpenAI (GPT)、Claude |
| 国产 | 通义千问、智谱GLM、豆包、Moonshot、百川、零一万物 |
| 高级 | Ollama本地、OpenRouter聚合、自定义API |

每个模型配以分步引导，从注册到获取Key到开始使用。

---

## 数据流（一轮对话发生了什么）

```
用户输入
  │
  ├─→ learner.record_outcome()      // 用当前输入推断上一轮质量
  ├─→ hexagram.update()             // 更新六爻 → 切换军师策略
  ├─→ cognitive_map.extract()       // 提取认知碎片到五维地图
  ├─→ rebuild system prompt         // 注入最新的一切
  │     ├─ 卦象策略
  │     ├─ 认知地图
  │     ├─ 经验结晶
  │     ├─ 共享经验（含Agent网络洞察）
  │     └─ 对话经验摘要
  │
  ├─→ AI回复
  │
  ├─→ cognitive_map.extract(reply)  // 从AI回复再提取
  ├─→ contribution.add_points()     // 对话积分
  ├─→ ecosystem.record_action()     // 生态行为记录
  ├─→ ecosystem.check_achievements()// 检查成就解锁
  │
  └─→ crystallizer.crystallize()    // 每10轮检查是否该结晶
```

---

## 文件结构

```
TaijiOS-Lite/
├── taijios.py              # 主程序入口（~1200行）
├── api_server.py           # REST/WebSocket API
├── ARCHITECTURE.md         # 本文档
├── README.md               # 用户说明
├── test_all.py             # 全功能测试（16模块10项测试）
│
├── evolution/              # 八大引擎
│   ├── __init__.py
│   ├── crystallizer.py     # 经验结晶引擎
│   ├── learner.py          # 对话学习引擎
│   ├── hexagram.py         # 易经卦象引擎
│   ├── agi_core.py         # AGI认知地图
│   ├── experience_pool.py  # 共享经验池（v2 Agent互学）
│   ├── premium.py          # 付费层管理
│   ├── contribution.py     # 贡献积分系统
│   └── ecosystem.py        # 生态制度（Agent网络）
│
└── data/                   # 运行时数据（自动创建）
    ├── evolution/
    │   ├── crystals.json       # 经验结晶
    │   ├── soul_outcomes.jsonl # 对话质量记录
    │   ├── hexagram.json       # 卦象状态
    │   ├── cognitive_map.json  # 认知地图
    │   ├── shared_pool.json    # 共享经验池
    │   ├── premium.json        # 付费状态
    │   ├── contribution.json   # 积分数据
    │   └── ecosystem.json      # 生态数据
    ├── history/                # 对话历史
    └── model_config.json       # 模型配置
```

---

## 如何对接基座

TaijiOS的每个引擎都是独立的Python类，可以单独使用：

```python
from evolution.hexagram import HexagramEngine
from evolution.agi_core import CognitiveMap
from evolution.ecosystem import EcosystemManager

# 初始化（传数据目录）
hexagram = HexagramEngine("/path/to/data")
cognitive = CognitiveMap("/path/to/data")
ecosystem = EcosystemManager("/path/to/data")

# 每轮对话调用
hexagram.update_from_conversation(user_messages, positive_rate)
cognitive.extract_from_message(user_input, ai_reply)
ecosystem.record_action("chat")

# 获取注入system prompt的内容
strategy = hexagram.get_strategy_prompt()
knowledge = cognitive.get_map_summary()
```

**对接要点：**
1. 所有引擎通过JSON文件持久化，无需数据库
2. 所有引擎独立运行，互不依赖，可按需接入
3. API Server提供完整HTTP接口，前端直接调用
4. .taiji文件是标准JSON，任何语言都能解析
5. 兼容任何OpenAI格式的大模型API

---

## 进化路线图

```
v1.0  基础对话 + 经验结晶
v1.1  易经卦象 + AGI认知地图 + 共享经验
v1.2  多模型 + Premium + 积分 + 全UX
v1.3  生态制度 + Agent网络 + v2互学 ← 当前
v1.4  [规划] 前端Web界面 + HUD悬浮窗
v1.5  [规划] Agent自动发现 + P2P经验同步
v2.0  [规划] 多Agent协作 + 认知图谱可视化
```

---

*TaijiOS — 你不是一个人在进化。每个Agent都是网络的一个神经元。*
