# TaijiOS Lite

带自进化的ICI认知AI。读取你的ICI档案（个体认知身份标识），用AI成为你的数字自我。

## 特性

- **ICI档案解读** — 读取.docx格式的ICI文件，AI自动激活为你的认知镜像
- **经验结晶** — 从对话模式中自动提取规则（避免/保持/发现三类）
- **对话学习** — 用你的下一句话推断上一轮回复质量，持续优化
- **进化统计** — 满意率、对话轮次、结晶数实时追踪
- **军事模式** — 效率拉满，方向明确，禁止废话

## 快速开始

### 方式一：下载exe（不需要Python）

从 [Releases](../../releases) 下载 `TaijiOS-Lite.zip`，解压后：

1. 把你的ICI文件（.docx）放进同一个文件夹
2. 双击 `TaijiOS-Lite.exe`
3. 首次运行粘贴 DeepSeek API Key（去 [platform.deepseek.com](https://platform.deepseek.com) 注册）

### 方式二：从源码运行

```bash
pip install python-docx openai python-dotenv
python taijios.py
```

## 自进化原理

```
你说话 → AI回复 → 你的下一句话 → 系统推断上一轮好不好
                                        ↓
                          正面/负面记录到 soul_outcomes.jsonl
                                        ↓
                          每10轮自动触发结晶引擎
                                        ↓
                        提取规则注入system prompt → AI变得更准
```

## 对话命令

| 命令 | 作用 |
|------|------|
| `exit` / `退出` | 退出对话 |
| `clear` / `清空` | 清空历史 |
| `status` / `状态` | 查看进化统计和经验结晶 |

## 项目结构

```
taijios.py              # 主程序
evolution/
  crystallizer.py       # 经验结晶引擎（纯规则，不依赖LLM）
  learner.py            # 对话学习器（正面/负面信号检测）
```

## 什么是ICI

ICI = Individual Cognitive Identity = 个体认知身份标识

把一个人拆成5个维度（位置、本事、钱财、野心、口碑），每个维度3个藏三方，加上认知结构和功能组，形成完整的认知档案。

## License

MIT
