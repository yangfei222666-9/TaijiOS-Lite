"""
易经卦象引擎 — 从对话状态映射到卦象策略

原理：
  用户的对话状态 = 6个维度的得分(0~1)
  6个维度 → 6爻 → 阴阳 → 64卦之一
  每个卦对应一个军师策略（AI怎么回你）

六爻对应（从下到上）：
  初爻：情绪基底（挫败度低=阳，高=阴）
  二爻：行动力（有具体目标=阳，迷茫=阴）
  三爻：认知清晰度（自我认知清=阳，混沌=阴）
  四爻：资源状态（有资源/支持=阳，匮乏=阴）
  五爻：方向感（方向明确=阳，摇摆=阴）
  上爻：整体满意度（正面多=阳，负面多=阴）
"""

import json
import os
import time
import logging
from typing import Optional

logger = logging.getLogger("hexagram")

# 8个基础卦（三爻组合）
TRIGRAMS = {
    (1, 1, 1): "乾", (0, 0, 0): "坤",
    (1, 0, 0): "震", (0, 1, 1): "巽",
    (0, 1, 0): "坎", (1, 0, 1): "离",
    (0, 0, 1): "艮", (1, 1, 0): "兑",
}

# 核心16卦策略（覆盖最常见状态，其余归类到最近的）
HEXAGRAM_STRATEGIES = {
    "乾": {"name": "乾为天", "strategy": "全面向好，趁势推进，给出最大胆的建议",
            "style": "进攻型军师：放手干，现在是你的窗口期"},
    "坤": {"name": "坤为地", "strategy": "蓄力等待，不要急于行动，帮用户梳理而非推动",
            "style": "防守型军师：先把地基打牢，别急"},
    "屯": {"name": "水雷屯", "strategy": "万事开头难，帮用户拆解第一步，不要给大蓝图",
            "style": "启动型军师：只说下一步，别说第十步"},
    "蒙": {"name": "山水蒙", "strategy": "用户认知模糊，用具体例子启蒙，不要讲道理",
            "style": "启蒙型军师：举例子，别讲理"},
    "需": {"name": "水天需", "strategy": "条件未成熟，帮用户识别在等什么，耐心引导",
            "style": "等待型军师：告诉他等什么、等多久"},
    "讼": {"name": "天水讼", "strategy": "内心冲突激烈，先帮用户看清矛盾双方，不要站队",
            "style": "调解型军师：把两边都摆出来"},
    "师": {"name": "地水师", "strategy": "需要组织资源行动，帮用户调兵遣将",
            "style": "统帅型军师：排兵布阵，给执行方案"},
    "比": {"name": "水地比", "strategy": "需要找盟友，帮用户识别谁能帮他",
            "style": "联盟型军师：你不是一个人在打"},
    "观": {"name": "风地观", "strategy": "用户在高处观望但不入场，推他一把",
            "style": "点破型军师：看够了就该下场了"},
    "剥": {"name": "山地剥", "strategy": "状态在下滑，帮用户止损而非扩张",
            "style": "止损型军师：先别想赚，先别亏"},
    "复": {"name": "地雷复", "strategy": "触底反弹的迹象，鼓励用户抓住转折点",
            "style": "复苏型军师：转机来了，准备好"},
    "困": {"name": "泽水困", "strategy": "资源耗尽，帮用户在绝境中找到突破口",
            "style": "破局型军师：穷则变，变则通"},
    "渐": {"name": "风山渐", "strategy": "循序渐进，帮用户设小目标不要跳步",
            "style": "稳进型军师：一步一步来"},
    "既济": {"name": "水火既济", "strategy": "当前事情做成了，但要警惕盛极而衰",
              "style": "居安型军师：成了不代表稳了"},
    "未济": {"name": "火水未济", "strategy": "还没搞定但有希望，帮用户坚持最后一段",
              "style": "冲刺型军师：快到了，别松劲"},
    "涣": {"name": "风水涣", "strategy": "精力分散，帮用户收拢焦点",
            "style": "聚焦型军师：砍掉多余的，只做一件事"},
}

# 六爻关键词检测
LINE_KEYWORDS = {
    # 初爻：情绪（阴=负面情绪）
    1: {"yin": ["烦", "累", "焦虑", "压力", "迷茫", "难受", "崩溃", "不知道"],
        "yang": ["还好", "可以", "不错", "开心", "有信心", "冲"]},
    # 二爻：行动力（阴=无行动）
    2: {"yin": ["不知道做什么", "没方向", "想太多", "纠结", "犹豫"],
        "yang": ["我在做", "我想", "计划", "打算", "正在", "准备"]},
    # 三爻：认知（阴=迷糊）
    3: {"yin": ["为什么", "搞不懂", "不理解", "什么意思", "怎么回事"],
        "yang": ["我知道", "我明白", "确实", "对", "原来", "有道理"]},
    # 四爻：资源（阴=匮乏）
    4: {"yin": ["没钱", "没资源", "没人", "没时间", "缺"],
        "yang": ["有", "资源", "认识", "可以用", "够"]},
    # 五爻：方向（阴=摇摆）
    5: {"yin": ["不确定", "要不要", "该不该", "选哪个", "两难"],
        "yang": ["决定了", "就这样", "目标", "方向是", "我要"]},
    # 上爻：满意度（从历史正面率推断）
    6: {"yin": [], "yang": []},  # 由stats驱动，不靠关键词
}


class HexagramEngine:
    """对话状态 → 卦象 → 军师策略"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.state_path = os.path.join(data_dir, "hexagram_state.json")
        self.history_path = os.path.join(data_dir, "hexagram_history.jsonl")
        self.current_lines = [1, 1, 1, 1, 1, 1]  # 默认全阳（乾）
        self.current_hexagram = "乾"
        self._load_state()

    def update_from_conversation(self, user_messages: list,
                                  positive_rate: float = 0.5) -> dict:
        """
        从最近对话内容更新六爻状态。
        返回当前卦象和策略。
        """
        # 合并最近消息
        text = " ".join(user_messages[-10:]) if user_messages else ""

        # 计算每一爻
        for line_num in range(1, 7):
            if line_num == 6:
                # 上爻由满意率决定
                self.current_lines[5] = 1 if positive_rate >= 0.5 else 0
            else:
                yin_hits = sum(1 for kw in LINE_KEYWORDS[line_num]["yin"] if kw in text)
                yang_hits = sum(1 for kw in LINE_KEYWORDS[line_num]["yang"] if kw in text)
                if yin_hits > yang_hits:
                    self.current_lines[line_num - 1] = 0
                elif yang_hits > yin_hits:
                    self.current_lines[line_num - 1] = 1
                # 都没命中保持不变

        # 映射到卦象
        lower = tuple(self.current_lines[0:3])
        upper = tuple(self.current_lines[3:6])
        lower_name = TRIGRAMS.get(lower, "坤")
        upper_name = TRIGRAMS.get(upper, "乾")
        self.current_hexagram = self._map_to_strategy_hexagram(
            lower_name, upper_name)

        self._save_state()
        self._log_history()

        strategy = HEXAGRAM_STRATEGIES.get(self.current_hexagram,
                                            HEXAGRAM_STRATEGIES["坤"])
        return {
            "hexagram": self.current_hexagram,
            "name": strategy["name"],
            "strategy": strategy["strategy"],
            "style": strategy["style"],
            "lines": self.current_lines.copy(),
        }

    def get_strategy_prompt(self) -> str:
        """生成注入system prompt的卦象策略"""
        strategy = HEXAGRAM_STRATEGIES.get(self.current_hexagram,
                                            HEXAGRAM_STRATEGIES["坤"])
        lines_display = "".join("⚊" if l == 1 else "⚋" for l in self.current_lines)
        return (
            f"\n## 当前卦象：{strategy['name']}（{lines_display}）\n"
            f"军师策略：{strategy['strategy']}\n"
            f"风格定位：{strategy['style']}\n"
        )

    def _map_to_strategy_hexagram(self, lower: str, upper: str) -> str:
        """将上下卦映射到有策略的卦名"""
        # 精确匹配
        mapping = {
            ("乾", "乾"): "乾", ("坤", "坤"): "坤",
            ("震", "坎"): "屯", ("坎", "艮"): "蒙",
            ("坎", "乾"): "需", ("乾", "坎"): "讼",
            ("坤", "坎"): "师", ("坎", "坤"): "比",
            ("坤", "巽"): "观", ("艮", "坤"): "剥",
            ("坤", "震"): "复", ("坎", "兑"): "困",
            ("艮", "巽"): "渐", ("坎", "离"): "既济",
            ("离", "坎"): "未济", ("坎", "巽"): "涣",
        }
        result = mapping.get((lower, upper))
        if result:
            return result

        # 模糊匹配：按阴阳数量归类
        yang_count = sum(self.current_lines)
        if yang_count >= 5:
            return "乾"
        elif yang_count <= 1:
            return "坤"
        elif yang_count == 4:
            return "渐"  # 大部分好，缓进
        elif yang_count == 2:
            return "困" if self.current_lines[0] == 0 else "复"
        else:  # 3阴3阳
            if self.current_lines[0] == 0:
                return "屯"
            else:
                return "观"

    def _load_state(self):
        if not os.path.exists(self.state_path):
            return
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.current_lines = data.get("lines", self.current_lines)
            self.current_hexagram = data.get("hexagram", self.current_hexagram)
        except Exception:
            pass

    def _save_state(self):
        os.makedirs(os.path.dirname(self.state_path) or ".", exist_ok=True)
        data = {
            "lines": self.current_lines,
            "hexagram": self.current_hexagram,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        try:
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _log_history(self):
        entry = {
            "timestamp": time.time(),
            "hexagram": self.current_hexagram,
            "lines": self.current_lines.copy(),
        }
        try:
            with open(self.history_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass
