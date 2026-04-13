"""
对话学习器 — 从每次对话中自动学习

功能：
1. 记录每次对话的outcome（正面/负面/挫败度）
2. 从用户下一句话推断上一轮回复的质量
3. 生成对话经验教训
4. 注入经验到下一次system prompt
"""

import json
import os
import time
import logging
from typing import List, Optional

logger = logging.getLogger("learner")

# 负面信号关键词
NEGATIVE_SIGNALS = [
    "不对", "不是", "错了", "你没懂", "不好", "离谱", "废话",
    "不是这个意思", "跑题了", "太泛了", "没用", "不准",
    "说了不是", "你搞错了", "重新", "算了",
]

# 正面信号关键词
POSITIVE_SIGNALS = [
    "对", "说得好", "有道理", "是的", "确实", "牛", "厉害",
    "说到点上了", "就是这样", "继续", "接着说", "深入",
    "好的", "明白了", "有意思", "学到了",
]


class ConversationLearner:
    """对话闭环学习器"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.outcomes_path = os.path.join(data_dir, "soul_outcomes.jsonl")
        self.lessons_path = os.path.join(data_dir, "lessons.json")
        self.stats_path = os.path.join(data_dir, "learn_stats.json")
        self._conversation_count = 0
        self._last_outcome: Optional[dict] = None

    def record_outcome(self, user_message: str, ai_reply: str,
                       next_user_message: str = ""):
        """
        记录一轮对话的outcome。
        用下一句用户消息推断当前回复的质量。
        """
        positive = True
        frustration = 0.0

        if next_user_message:
            negative_hits = sum(1 for kw in NEGATIVE_SIGNALS if kw in next_user_message)
            positive_hits = sum(1 for kw in POSITIVE_SIGNALS if kw in next_user_message)

            if negative_hits > positive_hits:
                positive = False
                frustration = min(1.0, negative_hits * 0.2)
            elif positive_hits > 0:
                positive = True
                frustration = 0.0
            # 都没有命中 → 保持默认positive（中性视为正面）

        outcome = {
            "timestamp": time.time(),
            "user_message": user_message[:200],
            "ai_reply_preview": ai_reply[:100],
            "positive": positive,
            "frustration": frustration,
        }

        try:
            with open(self.outcomes_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(outcome, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning("Record outcome failed: %s", e)

        self._last_outcome = outcome
        self._conversation_count += 1
        self._update_stats(positive)

    def get_experience_summary(self) -> str:
        """生成经验摘要（用于注入system prompt）"""
        stats = self._load_stats()
        if stats.get("total", 0) < 3:
            return ""

        total = stats["total"]
        positive_rate = stats.get("positive", 0) / max(total, 1)

        lines = []
        lines.append(f"[历史经验] 共{total}轮对话，满意率{positive_rate:.0%}")

        # 加载最近的负面经验
        recent_negatives = self._get_recent_negatives(5)
        if recent_negatives:
            lines.append("近期需改进：")
            for neg in recent_negatives:
                msg = neg.get("user_message", "")[:30]
                lines.append(f"  - 用户说「{msg}」时回复不够好")

        return "\n".join(lines)

    def should_crystallize(self) -> bool:
        """是否该触发结晶（每10轮对话一次）"""
        return self._conversation_count > 0 and self._conversation_count % 10 == 0

    def _get_recent_negatives(self, n: int = 5) -> list:
        """获取最近n条负面outcome"""
        if not os.path.exists(self.outcomes_path):
            return []
        negatives = []
        try:
            with open(self.outcomes_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    o = json.loads(line)
                    if not o.get("positive", True):
                        negatives.append(o)
        except Exception:
            pass
        return negatives[-n:]

    def _update_stats(self, positive: bool):
        stats = self._load_stats()
        stats["total"] = stats.get("total", 0) + 1
        if positive:
            stats["positive"] = stats.get("positive", 0) + 1
        else:
            stats["negative"] = stats.get("negative", 0) + 1
        stats["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        try:
            with open(self.stats_path, "w", encoding="utf-8") as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_stats(self) -> dict:
        if not os.path.exists(self.stats_path):
            return {"total": 0, "positive": 0, "negative": 0}
        try:
            with open(self.stats_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"total": 0, "positive": 0, "negative": 0}

    def get_positive_rate(self) -> float:
        """获取满意率（供卦象引擎使用）"""
        stats = self._load_stats()
        total = stats.get("total", 0)
        if total == 0:
            return 0.5
        return stats.get("positive", 0) / max(total, 1)

    def get_stats_display(self) -> str:
        """获取可展示的统计信息"""
        stats = self._load_stats()
        total = stats.get("total", 0)
        if total == 0:
            return ""
        pos = stats.get("positive", 0)
        neg = stats.get("negative", 0)
        rate = pos / max(total, 1)
        return f"[进化统计] {total}轮对话 | 满意率{rate:.0%} | 正面{pos} 负面{neg}"
