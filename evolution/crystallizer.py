"""
经验结晶引擎 — 从对话模式中自动提取规则

不依赖LLM。纯规则引擎：
1. 负面模式(连续N次不满) → 生成"避免"规则
2. 正面模式(连续M次满意) → 生成"保持"规则
3. 转折模式(从不满到满意) → 生成"发现"规则
"""

import json
import os
import time
import hashlib
import logging
from collections import defaultdict
from typing import Optional

logger = logging.getLogger("crystallization")


class CrystallizationEngine:
    NEGATIVE_STREAK_THRESHOLD = 3
    POSITIVE_STREAK_THRESHOLD = 4
    TURNAROUND_WINDOW = 5
    MIN_OUTCOMES = 5          # 降低门槛，ICI Chat场景数据少
    MAX_CRYSTALS = 20
    CONFIDENCE_DECAY = 0.01

    SCENE_KEYWORDS = {
        "做人": ["关系", "朋友", "家人", "人际", "沟通", "相处", "感情", "情绪"],
        "做事": ["工作", "赚钱", "项目", "创业", "事业", "方向", "目标", "计划"],
        "认知": ["为什么", "原理", "怎么理解", "认知", "分析", "解读", "ICI"],
        "情绪": ["烦", "累", "焦虑", "迷茫", "不知道", "纠结", "难受", "压力"],
    }

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.outcomes_path = os.path.join(data_dir, "soul_outcomes.jsonl")
        self.crystals_path = os.path.join(data_dir, "experience_crystals.json")
        self.crystals: list = []
        self._load_crystals()

    def crystallize(self) -> list:
        """核心方法：扫描outcomes，识别模式，生成新结晶"""
        outcomes = self._load_outcomes()
        if len(outcomes) < self.MIN_OUTCOMES:
            return []

        new_crystals = []
        scene_groups = self._group_by_scene(outcomes)

        for scene, group in scene_groups.items():
            if len(group) < 3:
                continue
            for detect_fn in [self._detect_negative_streak,
                              self._detect_positive_streak,
                              self._detect_turnaround]:
                crystal = detect_fn(scene, group)
                if crystal and not self._is_duplicate(crystal):
                    new_crystals.append(crystal)

        crystal = self._detect_frustration_pattern(outcomes)
        if crystal and not self._is_duplicate(crystal):
            new_crystals.append(crystal)

        self._decay_confidence()

        for c in new_crystals:
            self.crystals.append(c)
            logger.info("[CRYSTAL] new: %s", c["rule"][:40])

        if len(self.crystals) > self.MAX_CRYSTALS:
            self.crystals.sort(key=lambda c: c.get("confidence", 0), reverse=True)
            self.crystals = self.crystals[:self.MAX_CRYSTALS]

        self.crystals = [c for c in self.crystals if c.get("confidence", 0) >= 0.3]
        self._save_crystals()
        return new_crystals

    def get_active_rules(self) -> list:
        """获取当前有效的结晶规则（用于注入system prompt）"""
        return [c for c in self.crystals if c.get("confidence", 0) >= 0.5]

    def _classify_scene(self, message: str) -> str:
        msg = message.lower()
        best_scene, best_score = "general", 0
        for scene, keywords in self.SCENE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in msg)
            if score > best_score:
                best_score = score
                best_scene = scene
        return best_scene

    def _group_by_scene(self, outcomes: list) -> dict:
        groups = defaultdict(list)
        for o in outcomes:
            msg = o.get("user_message", "") or o.get("message", "")
            if not msg:
                continue
            scene = self._classify_scene(msg)
            groups[scene].append(o)
        return dict(groups)

    def _detect_negative_streak(self, scene: str, group: list) -> Optional[dict]:
        streak = 0
        max_streak = 0
        for o in group:
            if not o.get("positive", True):
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0
        if max_streak < self.NEGATIVE_STREAK_THRESHOLD:
            return None

        rule = self._negative_rule(scene)
        return self._make_crystal(rule, f"{scene}场景连续{max_streak}次负面",
                                  "auto_negative", scene, len(group),
                                  min(0.7 + max_streak * 0.05, 0.95))

    def _detect_positive_streak(self, scene: str, group: list) -> Optional[dict]:
        streak = 0
        max_streak = 0
        for o in group:
            if o.get("positive", True):
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0
        if max_streak < self.POSITIVE_STREAK_THRESHOLD:
            return None

        rule = self._positive_rule(scene)
        return self._make_crystal(rule, f"{scene}场景连续{max_streak}次正面",
                                  "auto_positive", scene, len(group),
                                  min(0.6 + max_streak * 0.04, 0.90))

    def _detect_turnaround(self, scene: str, group: list) -> Optional[dict]:
        for i in range(len(group) - 1):
            if not group[i].get("positive", True) and group[i + 1].get("positive", True):
                frust_before = group[i].get("frustration", 0.3)
                frust_after = group[i + 1].get("frustration", 0)
                if frust_before > frust_after:
                    rule = f"{scene}场景：从不满到满意，关键是调整了回复策略"
                    return self._make_crystal(rule,
                                              f"转折模式：挫败度{frust_before:.2f}→{frust_after:.2f}",
                                              "auto_turnaround", scene, 2, 0.70)
        return None

    def _detect_frustration_pattern(self, outcomes: list) -> Optional[dict]:
        high_frust = [o for o in outcomes if o.get("frustration", 0) > 0.3]
        if len(high_frust) < 3:
            return None
        pos_count = sum(1 for o in high_frust if o.get("positive", True))
        pos_rate = pos_count / len(high_frust)
        if pos_rate < 0.4:
            rule = "用户挫败度高时，优先共情再解决问题，不要直接给方案"
            return self._make_crystal(rule,
                                      f"高挫败场景{len(high_frust)}次，正面率{pos_rate:.0%}",
                                      "auto_emotional", "emotional",
                                      len(high_frust), 0.80)
        return None

    def _negative_rule(self, scene: str) -> str:
        rules = {
            "做人": "做人问题不要空谈道理，直接用ICI藏三方数据分析关系博弈",
            "做事": "做事问题不要笼统建议，先确认突破/守成/关系/规则哪种类型",
            "认知": "认知问题不要堆概念，用一个具体例子打通",
            "情绪": "用户情绪低落时不要说教，先共情再分析",
        }
        return rules.get(scene, f"{scene}场景回复方式需要调整")

    def _positive_rule(self, scene: str) -> str:
        rules = {
            "做人": "做人分析当前的藏三方博弈拆解方式有效，保持",
            "做事": "做事分析当前的接口匹配策略有效，保持",
            "认知": "认知解读当前的精气神三层分析方式有效，保持",
            "情绪": "情绪回应当前的共情方式有效，保持",
        }
        return rules.get(scene, f"{scene}场景当前策略有效，保持")

    def _make_crystal(self, rule, evidence, category, trigger, count, confidence):
        return {
            "id": f"auto_{hashlib.md5(rule.encode()).hexdigest()[:8]}",
            "rule": rule,
            "evidence": evidence,
            "confidence": confidence,
            "category": category,
            "trigger": f"{trigger}场景",
            "auto_generated": True,
            "generated_at": time.time(),
            "source_count": count,
        }

    def _is_duplicate(self, new_crystal: dict) -> bool:
        new_rule = new_crystal["rule"]
        for existing in self.crystals:
            overlap = len(set(new_rule) & set(existing["rule"])) / max(
                len(set(new_rule) | set(existing["rule"])), 1)
            if overlap > 0.7:
                existing["confidence"] = min(1.0, existing["confidence"] + 0.05)
                existing["source_count"] = existing.get("source_count", 1) + new_crystal.get("source_count", 1)
                return True
        return False

    def _decay_confidence(self):
        for c in self.crystals:
            if c.get("auto_generated"):
                c["confidence"] = max(0.0, c["confidence"] - self.CONFIDENCE_DECAY)

    def _load_outcomes(self) -> list:
        if not os.path.exists(self.outcomes_path):
            return []
        outcomes = []
        try:
            with open(self.outcomes_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        outcomes.append(json.loads(line))
        except Exception:
            pass
        return outcomes

    def _load_crystals(self):
        from .safe_io import safe_json_load
        data = safe_json_load(self.crystals_path, None)
        if data:
            self.crystals = data.get("crystals", [])
        else:
            self.crystals = []

    def _save_crystals(self):
        from .safe_io import safe_json_save
        data = {
            "version": 2,
            "crystallized_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_crystals": len(self.crystals),
            "crystals": self.crystals,
        }
        safe_json_save(self.crystals_path, data)
