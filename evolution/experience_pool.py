"""
共享经验池 — 跨用户经验流通

原理：
  每个用户的结晶经验 → 导出为匿名经验包
  别人导入 → 进入"共享池"，和个人结晶分开
  共享经验有独立的置信度衰减：被多人验证 → 置信度上升

命令：
  export → 导出你的经验包（.taiji文件）
  import <路径> → 导入别人的经验包
"""

import json
import os
import time
import re
import logging
from typing import Optional
from .safe_io import safe_json_save, safe_json_load

logger = logging.getLogger("experience_pool")

# 安全：限制导入规则的内容
MAX_RULE_LENGTH = 100        # 单条规则最大长度
MAX_PATTERN_LENGTH = 80      # 认知模式最大长度
MAX_IMPORT_RULES = 20        # 单次导入最大规则数
BLOCKED_PATTERNS = [
    r"(?i)ignore.*instruction",
    r"(?i)forget.*previous",
    r"(?i)system.*prompt",
    r"(?i)你是一个",
    r"(?i)你的角色",
    r"(?i)override",
    r"(?i)bypass",
    r"(?i)pretend",
    r"(?i)假装",
    r"(?i)忽略.*指令",
    r"(?i)忘记.*规则",
]


def _sanitize_text(text: str, max_len: int) -> str:
    """清理导入文本：截断 + 去除潜在注入"""
    if not isinstance(text, str):
        return ""
    text = text.strip()[:max_len]
    # 去除markdown/特殊格式
    text = text.replace("#", "").replace("```", "").replace("---", "")
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, text):
            logger.warning(f"Blocked suspicious import text: {text[:30]}...")
            return ""
    return text


# 脱敏：导出时过滤个人敏感信息
PII_PATTERNS = [
    # 证件类
    (r"\d{17}[\dXx]", "[身份证号]"),                  # 18位身份证（必须在手机号前）
    (r"\d{15}", "[身份证号]"),                         # 15位身份证
    # 联系方式
    (r"1[3-9]\d{9}", "[手机号]"),                     # 手机号
    (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[邮箱]"),  # 邮箱
    (r"(?:https?://)\S+", "[链接]"),                   # URL
    # 人名（带称谓）
    (r"[\u4e00-\u9fff]{2,4}(?:先生|女士|老师|总|哥|姐|叔|阿姨|老板|经理|主任|院长|教授|同学|医生|律师|老公|老婆|男友|女友|男朋友|女朋友|爱人|丈夫|妻子|媳妇|对象)", "[某人]"),
    # 感情/亲密关系描述
    (r"(?:我|他|她)(?:和|跟|与)[\u4e00-\u9fff]{2,4}(?:在一起|分手|离婚|结婚|复合|吵架|出轨|暧昧|恋爱|同居)", "[感情经历]"),
    (r"(?:前男友|前女友|前任|前夫|前妻|初恋)[\u4e00-\u9fff]{0,4}", "[前任]"),
    (r"(?:喜欢|爱上|暗恋|追求|表白)[\u4e00-\u9fff]{2,4}", "[感情细节]"),
    # 地址
    (r"[\u4e00-\u9fff]{2,6}(?:省|市|区|县|镇|村|路|街|巷|号|弄|栋|幢|室|楼)", "[地址]"),
    # 公司/学校名
    (r"[\u4e00-\u9fff]{2,8}(?:公司|集团|有限|股份|科技|学院|大学|中学|小学|幼儿园|医院)", "[机构]"),
    # 微信/QQ等社交账号
    (r"(?:微信|wx|WeChat)[：:\s]*\S{5,20}", "[社交账号]"),
    (r"(?:QQ|qq)[：:\s]*\d{5,12}", "[社交账号]"),
]


def _desensitize_text(text: str) -> str:
    """脱敏处理：去除个人敏感信息（姓名、感情、联系方式、地址等）"""
    if not isinstance(text, str):
        return ""
    for pattern, replacement in PII_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text


class ExperiencePool:
    """跨用户共享经验池"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.pool_path = os.path.join(data_dir, "shared_pool.json")
        self.pool = self._load_pool()

    def export_crystals(self, crystal_rules: list, export_path: str,
                        hexagram_data: dict = None,
                        cognitive_data: dict = None,
                        contributor_id: str = "") -> str:
        """
        导出当前Agent的完整经验包（经验结晶 + 易经卦象 + 认知灵魂）。
        每个Agent导出的包携带三层数据：
          1. 经验结晶 — 从对话中提炼的规则
          2. 易经快照 — 当前卦象和六爻状态（Agent的"气运"）
          3. 灵魂认知 — 五维认知地图的积累（Agent的"灵魂"）
        返回导出文件路径。
        """
        if not crystal_rules:
            return ""

        package = {
            "format": "taiji_experience_v2",
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "agent_id": contributor_id,
            "count": len(crystal_rules),
            "crystals": [],
        }

        for rule in crystal_rules:
            # 导出时脱敏：去除规则中的个人信息
            clean_rule = _desensitize_text(rule.get("rule", ""))
            clean_scene = _desensitize_text(rule.get("scene", ""))
            package["crystals"].append({
                "rule": clean_rule,
                "confidence": rule.get("confidence", 0.5),
                "scene": clean_scene,
                "verified_by": 1,
            })

        # 附带易经卦象快照（Agent的当前气运状态）
        if hexagram_data:
            package["hexagram"] = {
                "current": hexagram_data.get("hexagram", ""),
                "lines": hexagram_data.get("lines", []),
                "strategy": hexagram_data.get("strategy", ""),
                "note": "此Agent导出时的卦象状态，仅供参考",
            }

        # 附带灵魂认知数据（匿名化+脱敏的五维认知模式）
        if cognitive_data:
            clean_patterns = [
                _desensitize_text(p) for p in cognitive_data.get("patterns", [])
                if _desensitize_text(p)
            ]
            package["soul"] = {
                "dimensions": cognitive_data.get("dimensions", {}),
                "patterns": clean_patterns,
                "note": "此Agent的认知模式（已匿名脱敏），可交叉验证",
            }

        try:
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(package, f, ensure_ascii=False, indent=2)
            return export_path
        except Exception as e:
            logger.error(f"导出失败: {e}")
            return ""

    def import_crystals(self, import_path: str) -> int:
        """
        导入别人的经验包到共享池。
        兼容v1和v2格式。v2额外携带易经+灵魂数据。
        返回新导入的规则数。
        """
        try:
            with open(import_path, "r", encoding="utf-8") as f:
                package = json.load(f)
        except Exception as e:
            logger.error(f"导入失败: {e}")
            return 0

        fmt = package.get("format", "")
        if fmt not in ("taiji_experience_v1", "taiji_experience_v2"):
            return 0

        new_count = 0
        existing_rules = {item["rule"] for item in self.pool.get("shared", [])}

        crystals = package.get("crystals", [])
        if not isinstance(crystals, list):
            return 0
        crystals = crystals[:MAX_IMPORT_RULES]  # 限制数量

        for crystal in crystals:
            if not isinstance(crystal, dict):
                continue
            rule_text = _sanitize_text(crystal.get("rule", ""), MAX_RULE_LENGTH)
            if not rule_text:
                continue

            if rule_text in existing_rules:
                for item in self.pool["shared"]:
                    if item["rule"] == rule_text:
                        item["verified_by"] = item.get("verified_by", 1) + 1
                        item["confidence"] = min(
                            0.95, item["confidence"] + 0.05)
                        break
            else:
                conf = crystal.get("confidence", 0.5)
                if not isinstance(conf, (int, float)):
                    conf = 0.5
                self.pool.setdefault("shared", []).append({
                    "rule": rule_text,
                    "confidence": max(0.3, min(conf, 1.0) * 0.6),
                    "scene": str(crystal.get("scene", ""))[:30],
                    "verified_by": 1,
                    "imported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "from_agent": str(package.get("agent_id", ""))[:16],
                })
                new_count += 1
                existing_rules.add(rule_text)

        # v2: 存储来源Agent的易经和灵魂快照（已清理）
        if fmt == "taiji_experience_v2":
            agent_id = str(package.get("agent_id", "unknown"))[:16]
            snapshots = self.pool.setdefault("agent_snapshots", {})
            # 清理soul patterns
            raw_soul = package.get("soul", {})
            if isinstance(raw_soul, dict):
                clean_patterns = []
                for p in raw_soul.get("patterns", [])[:5]:
                    cleaned = _sanitize_text(str(p), MAX_PATTERN_LENGTH)
                    if cleaned:
                        clean_patterns.append(cleaned)
                clean_soul = {
                    "dimensions": raw_soul.get("dimensions", {}),
                    "patterns": clean_patterns,
                }
            else:
                clean_soul = {}
            snapshots[agent_id] = {
                "hexagram": package.get("hexagram", {}),
                "soul": clean_soul,
                "imported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }

        self.pool["last_import"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._save_pool()
        return new_count

    def get_agent_snapshots(self) -> dict:
        """获取所有已导入的Agent快照（易经+灵魂）"""
        return self.pool.get("agent_snapshots", {})

    def get_shared_rules(self) -> list:
        """获取共享池中置信度 >= 0.4 的规则"""
        return [
            item for item in self.pool.get("shared", [])
            if item.get("confidence", 0) >= 0.4
        ]

    def get_shared_prompt(self) -> str:
        """生成注入system prompt的共享经验（含Agent网络洞察）"""
        rules = self.get_shared_rules()
        snapshots = self.get_agent_snapshots()

        if not rules and not snapshots:
            return ""

        lines = []

        if rules:
            lines.append("\n## 共享经验（来自其他Agent的验证规律）")
            for r in rules[:8]:
                verified = r.get("verified_by", 1)
                agent = r.get("from_agent", "")
                tag = f"[{verified}Agent验证]" if verified > 1 else "[共享]"
                lines.append(f"- {tag} {r['rule']}")

        if snapshots:
            lines.append(f"\n## Agent网络洞察（{len(snapshots)}个Agent的认知交汇）")
            for aid, snap in list(snapshots.items())[:3]:
                soul = snap.get("soul", {})
                patterns = soul.get("patterns", [])
                if patterns:
                    for p in patterns[:2]:
                        lines.append(f"- [Agent {aid[:4]}] {p}")

        return "\n".join(lines)

    def get_display(self) -> str:
        """给status命令显示"""
        shared = self.pool.get("shared", [])
        active = [s for s in shared if s.get("confidence", 0) >= 0.4]
        if not shared:
            return "[共享经验] 空 | 用 export 导出你的经验，用 import 导入别人的"
        lines = [f"[共享经验] {len(active)}条生效 / {len(shared)}条总计"]
        for r in active[:5]:
            verified = r.get("verified_by", 1)
            lines.append(f"  [{verified}人验证] {r['rule'][:40]}")
        return "\n".join(lines)

    def _load_pool(self) -> dict:
        return safe_json_load(self.pool_path, {"shared": []})

    def _save_pool(self):
        safe_json_save(self.pool_path, self.pool)
