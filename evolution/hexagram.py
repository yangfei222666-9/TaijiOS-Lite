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

    # ── 变爻推演系统 ──────────────────────────────────────────

    def divine(self, user_messages: list, positive_rate: float = 0.5) -> dict:
        """
        易经推演：根据当前卦象 + 变爻 → 推算变卦 → 给出预判。
        在用户对话3轮以上后触发。

        返回: {
            "current": 当前卦信息,
            "changing_lines": 哪些爻在动,
            "future": 变卦信息,
            "prediction": 推演预判文本,
            "advice": 行动建议,
        }
        """
        old_lines = self.current_lines.copy()

        # 先用最新消息更新卦象
        self.update_from_conversation(user_messages, positive_rate)
        new_lines = self.current_lines.copy()

        # 检测变爻（哪些爻从上次发生了变化）
        changing = []
        for i in range(6):
            if old_lines[i] != new_lines[i]:
                changing.append(i)

        # 如果没有自然变爻，用消息情感强度推算动爻
        if not changing:
            changing = self._detect_dynamic_lines(user_messages)

        # 计算变卦（变爻取反）
        future_lines = new_lines.copy()
        for i in changing:
            future_lines[i] = 1 - future_lines[i]

        # 映射变卦
        lower = tuple(future_lines[0:3])
        upper = tuple(future_lines[3:6])
        lower_name = TRIGRAMS.get(lower, "坤")
        upper_name = TRIGRAMS.get(upper, "乾")

        # 临时切换lines算变卦名
        saved = self.current_lines
        self.current_lines = future_lines
        future_hex = self._map_to_strategy_hexagram(lower_name, upper_name)
        self.current_lines = saved

        current_strat = HEXAGRAM_STRATEGIES.get(self.current_hexagram,
                                                 HEXAGRAM_STRATEGIES["坤"])
        future_strat = HEXAGRAM_STRATEGIES.get(future_hex,
                                                HEXAGRAM_STRATEGIES["坤"])

        # 生成推演
        prediction = self._generate_prediction(
            self.current_hexagram, current_strat,
            future_hex, future_strat,
            changing, new_lines, future_lines)

        return {
            "current": {
                "hexagram": self.current_hexagram,
                "name": current_strat["name"],
                "lines": new_lines,
                "lines_display": "".join("⚊" if l == 1 else "⚋" for l in new_lines),
                "strategy": current_strat["strategy"],
            },
            "changing_lines": changing,
            "future": {
                "hexagram": future_hex,
                "name": future_strat["name"],
                "lines": future_lines,
                "lines_display": "".join("⚊" if l == 1 else "⚋" for l in future_lines),
                "strategy": future_strat["strategy"],
            },
            "prediction": prediction["prediction"],
            "advice": prediction["advice"],
            "display": prediction["display"],
        }

    def _detect_dynamic_lines(self, user_messages: list) -> list:
        """
        当没有自然变爻时，用消息内容的情感强度推算动爻。
        情感最激烈的维度 = 动爻（将要发生变化的维度）。
        """
        text = " ".join(user_messages[-6:]) if user_messages else ""
        scores = {}

        for line_num in range(1, 6):  # 1-5爻，6爻由正面率决定
            yin_hits = sum(1 for kw in LINE_KEYWORDS[line_num]["yin"] if kw in text)
            yang_hits = sum(1 for kw in LINE_KEYWORDS[line_num]["yang"] if kw in text)
            # 冲突越大 = 越可能是动爻
            scores[line_num - 1] = abs(yin_hits - yang_hits) + (yin_hits + yang_hits) * 0.3

        if not any(scores.values()):
            # 完全没命中，默认五爻动（方向将变）
            return [4]

        # 取冲突最大的1-2个爻为动爻
        sorted_lines = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        result = []
        for idx, score in sorted_lines:
            if score > 0:
                result.append(idx)
            if len(result) >= 2:
                break

        return result if result else [4]

    # 爻位名称和维度映射
    LINE_NAMES = {
        0: ("初爻", "情绪基底"),
        1: ("二爻", "行动力"),
        2: ("三爻", "认知清晰度"),
        3: ("四爻", "资源状态"),
        4: ("五爻", "方向感"),
        5: ("上爻", "整体满意度"),
    }

    # 变卦推演语义库
    TRANSITION_INSIGHTS = {
        # (当前卦, 变卦) → 推演
        ("乾", "渐"): ("盛极将缓", "你现在状态很好，但即将进入稳扎稳打的阶段。别因为顺风就加速，该减速的时候要减速。", "把当前优势固化成可持续的模式，别贪快。"),
        ("乾", "观"): ("高处不胜寒", "全阳之后需要观察，你可能忽略了某些隐患。", "停下来看一圈，有没有你没注意到的风险。"),
        ("坤", "复"): ("否极泰来", "最低谷已过，转机正在酝酿。一个小的正面信号即将出现。", "抓住第一个积极信号，不要犹豫，立刻行动。"),
        ("坤", "屯"): ("破土而出", "蛰伏够了，该开始行动。虽然万事开头难，但不迈出第一步就永远在原地。", "只做一件最小的事，不要想太多。"),
        ("困", "井"): ("困中寻源", "你觉得被困住，但答案不在外面，在你自己身上。向内挖掘，你有被忽视的资源。", "列出你已有的所有资源，重新审视哪些能组合出新价值。"),
        ("困", "复"): ("绝处逢生", "困境即将触底反弹，但需要你主动抓住那个转折点。", "本周内做一个你一直在拖延的决定。"),
        ("屯", "乾"): ("破局上升", "启动期的困难快过了，即将进入上升通道。", "加大投入，这是加速的窗口。"),
        ("屯", "渐"): ("起步稳住", "起步阶段开始稳定，接下来要一步步走扎实。", "设3个月里程碑，每月验证一个核心假设。"),
        ("观", "乾"): ("入场时机到", "观望够了，你已经看清了局势，该下场了。", "本周就行动，别再分析了。"),
        ("观", "困"): ("看太久会错过", "一直在观望导致错过时机，资源在消耗。", "给自己设一个死线，过了就必须做决定。"),
        ("渐", "乾"): ("稳中求进", "渐进积累到了临界点，可以大胆一搏。", "挑一个你最有把握的方向，全力投入。"),
        ("渐", "困"): ("进展受阻", "循序渐进的节奏被打断，可能遇到卡点。", "先解决卡点，别绕过去，绕过去后面还会遇到。"),
        ("剥", "复"): ("剥极必复", "下滑到底了，反弹即将开始。易经说剥极必复，这是铁律。", "现在不是止损，是准备接住反弹。"),
        ("复", "渐"): ("恢复稳定", "触底反弹后进入稳步恢复期，别急着冲。", "恢复期最重要的是节奏，不要因为好转就放飞。"),
        ("既济", "未济"): ("盛转危", "事情刚成，但隐患已经埋下。既济之后必是未济，古今皆然。", "复盘成功的原因，看哪些是运气哪些是实力。"),
        ("未济", "既济"): ("临门一脚", "差最后一步就成了。坚持，别在终点前放弃。", "把全部精力集中在最后一个卡点上。"),
        ("涣", "渐"): ("散而复聚", "精力分散的状态将收束，焦点正在形成。", "删掉清单上一半的事，只留最重要的3件。"),
        ("师", "比"): ("独战转联盟", "不用一个人扛了，该找帮手了。", "列出3个能帮你的人，本周联系他们。"),
    }

    def _generate_prediction(self, current_hex, current_strat,
                              future_hex, future_strat,
                              changing, current_lines, future_lines) -> dict:
        """生成推演文本"""
        # 查找精确匹配的推演
        transition = self.TRANSITION_INSIGHTS.get((current_hex, future_hex))

        if transition:
            title, prediction, advice = transition
        else:
            # 通用推演：根据阴阳变化趋势生成
            yang_now = sum(current_lines)
            yang_future = sum(future_lines)

            if yang_future > yang_now:
                title = "阳气上升"
                prediction = f"从{current_strat['name']}转向{future_strat['name']}，状态在变好。变化的维度正在从阴转阳，抓住这个上升势头。"
                advice = f"顺势而为：{future_strat['strategy']}"
            elif yang_future < yang_now:
                title = "需要蓄力"
                prediction = f"从{current_strat['name']}转向{future_strat['name']}，部分维度在走弱。不是坏事，是提醒你该收一收了。"
                advice = f"防守优先：{future_strat['strategy']}"
            else:
                title = "格局转换"
                prediction = f"阴阳总量不变但格局在变，从{current_strat['name']}的局面转向{future_strat['name']}。内在结构在调整。"
                advice = f"顺应变化：{future_strat['strategy']}"

        # 变爻描述
        changing_desc = []
        for i in changing:
            name, dim = self.LINE_NAMES.get(i, (f"第{i+1}爻", "未知"))
            direction = "阴→阳" if current_lines[i] == 0 else "阳→阴"
            changing_desc.append(f"{name}({dim}){direction}")

        # 构建展示文本
        cur_display = "".join("⚊" if l == 1 else "⚋" for l in current_lines)
        fut_display = "".join("⚊" if l == 1 else "⚋" for l in future_lines)

        display = f"""
  ┌─────────────────────────────────────
  │ 军师推演 —— {title}
  │
  │ 当前：{current_strat['name']} {cur_display}
  │ 变爻：{', '.join(changing_desc)}
  │ 变卦：{current_strat['name']} → {future_strat['name']} {fut_display}
  │
  │ 推演：{prediction}
  │
  │ 建议：{advice}
  └─────────────────────────────────────"""

        return {
            "prediction": prediction,
            "advice": advice,
            "display": display,
        }

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
        from .safe_io import safe_json_load
        data = safe_json_load(self.state_path, None)
        if data:
            self.current_lines = data.get("lines", self.current_lines)
            self.current_hexagram = data.get("hexagram", self.current_hexagram)

    def _save_state(self):
        from .safe_io import safe_json_save
        data = {
            "lines": self.current_lines,
            "hexagram": self.current_hexagram,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        safe_json_save(self.state_path, data)

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
