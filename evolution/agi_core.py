"""
AGI进化核心 — 持续加深认知 + 跨维度推理 + 主动洞察

三层进化：
  L1 记忆层：记住用户说过的关键信息（认知地图）
  L2 推理层：从多次对话中发现用户自己没意识到的模式
  L3 预判层：基于卦象趋势+认知地图，主动推送洞察

与易经融合：
  卦象 = 用户当前状态的快照
  AGI = 让这个快照越来越精准的引擎
  结晶 = 验证过的规律沉淀
"""

import json
import os
import time
import logging
from typing import Optional

logger = logging.getLogger("agi_core")


class CognitiveMap:
    """用户认知地图 — 跨对话持续构建"""

    # 五个维度的关键词提取
    DIMENSION_KEYWORDS = {
        "位置": ["工作", "职位", "角色", "身份", "在哪", "做什么的", "行业"],
        "本事": ["擅长", "会", "技能", "能力", "强项", "本事", "优势"],
        "钱财": ["收入", "赚", "钱", "存款", "负债", "财务", "资源"],
        "野心": ["想要", "目标", "梦想", "野心", "方向", "计划", "未来"],
        "口碑": ["别人说", "评价", "朋友", "名声", "信任", "口碑", "关系"],
    }

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.map_path = os.path.join(data_dir, "cognitive_map.json")
        self.insights_path = os.path.join(data_dir, "agi_insights.jsonl")
        self.map = self._load_map()

    def extract_from_message(self, user_message: str, ai_reply: str):
        """从每轮对话中提取认知碎片，更新地图"""
        for dim, keywords in self.DIMENSION_KEYWORDS.items():
            for kw in keywords:
                if kw in user_message:
                    # 提取包含关键词的那句话
                    sentences = user_message.replace("。", "\n").replace(
                        "，", "\n").replace("！", "\n").split("\n")
                    for s in sentences:
                        s = s.strip()
                        if kw in s and len(s) > 4:
                            if dim not in self.map:
                                self.map[dim] = []
                            # 去重
                            if s not in self.map[dim]:
                                self.map[dim].append(s)
                                # 只保留最近10条
                                if len(self.map[dim]) > 10:
                                    self.map[dim] = self.map[dim][-10:]
                            break

        self.map["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.map["total_extractions"] = self.map.get("total_extractions", 0) + 1
        self._save_map()

    def detect_patterns(self) -> list:
        """
        跨维度模式检测（L2推理层）
        发现用户自己没意识到的矛盾或机会
        """
        patterns = []

        # 模式1：有野心但没行动（野心维度有内容，本事/位置维度空）
        if self.map.get("野心") and not self.map.get("本事"):
            patterns.append({
                "type": "gap",
                "insight": "你提了很多想要的，但从没聊过你擅长什么。野心没有本事托底，容易变成焦虑。",
                "action": "下次对话引导用户聊「你最拿手的是什么」",
            })

        # 模式2：频繁提钱但没提方向
        if self.map.get("钱财") and not self.map.get("野心"):
            patterns.append({
                "type": "gap",
                "insight": "你一直在聊钱的问题，但没说过你想往哪走。赚钱是手段不是方向。",
                "action": "下次对话引导用户聊「你最想达到的状态是什么」",
            })

        # 模式3：有口碑但没位置
        if self.map.get("口碑") and not self.map.get("位置"):
            patterns.append({
                "type": "gap",
                "insight": "别人对你评价不错，但你自己好像没有明确的角色定位。口碑是软的，位置才是硬的。",
                "action": "下次对话引导用户聊「你在当前局面里是什么角色」",
            })

        # 模式4：所有维度都有内容 = 认知相对完整
        filled = sum(1 for d in ["位置", "本事", "钱财", "野心", "口碑"]
                     if self.map.get(d))
        if filled >= 4:
            patterns.append({
                "type": "ready",
                "insight": "认知地图基本完整，可以开始做深度交叉分析了。",
                "action": "主动做五维度交叉分析",
            })

        # 模式5：反复提同一个词 = 执念/卡点
        all_texts = []
        for dim in ["位置", "本事", "钱财", "野心", "口碑"]:
            all_texts.extend(self.map.get(dim, []))
        if all_texts:
            from collections import Counter
            words = []
            for t in all_texts:
                words.extend(t)
            common = Counter(words).most_common(3)
            # 如果某个字出现频率超高，可能是执念
            if common and common[0][1] > len(all_texts) * 2:
                patterns.append({
                    "type": "obsession",
                    "insight": f"你反复提到「{common[0][0]}」相关的内容，这可能是你当前的核心卡点。",
                    "action": "直接点破这个执念",
                })

        return patterns

    def get_map_summary(self) -> str:
        """生成认知地图摘要（注入system prompt）"""
        filled = {}
        for dim in ["位置", "本事", "钱财", "野心", "口碑"]:
            items = self.map.get(dim, [])
            if items:
                filled[dim] = items[-3:]  # 最近3条

        if not filled:
            return ""

        lines = ["\n## 认知地图（从历史对话中积累）"]
        for dim, items in filled.items():
            lines.append(f"【{dim}】")
            for item in items:
                lines.append(f"  - 用户说过：「{item[:40]}」")

        patterns = self.detect_patterns()
        if patterns:
            lines.append("\n## AGI洞察（跨维度分析发现）")
            for p in patterns:
                lines.append(f"- {p['insight']}")

        return "\n".join(lines)

    def get_display(self) -> str:
        """给status命令显示的格式"""
        dims = ["位置", "本事", "钱财", "野心", "口碑"]
        filled = sum(1 for d in dims if self.map.get(d))
        total = self.map.get("total_extractions", 0)
        lines = [f"[认知地图] {filled}/5维度已填充 | 共提取{total}条"]
        for d in dims:
            items = self.map.get(d, [])
            status = f"{len(items)}条" if items else "空"
            lines.append(f"  {d}：{status}")
        return "\n".join(lines)

    def _load_map(self) -> dict:
        from .safe_io import safe_json_load
        return safe_json_load(self.map_path, {})

    def _save_map(self):
        from .safe_io import safe_json_save
        safe_json_save(self.map_path, self.map)
