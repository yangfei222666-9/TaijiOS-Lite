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
import logging
from typing import Optional

logger = logging.getLogger("experience_pool")


class ExperiencePool:
    """跨用户共享经验池"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.pool_path = os.path.join(data_dir, "shared_pool.json")
        self.pool = self._load_pool()

    def export_crystals(self, crystal_rules: list, export_path: str) -> str:
        """
        导出当前用户的结晶经验为匿名经验包。
        返回导出文件路径。
        """
        if not crystal_rules:
            return ""

        package = {
            "format": "taiji_experience_v1",
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "count": len(crystal_rules),
            "crystals": []
        }

        for rule in crystal_rules:
            # 匿名化：只保留规则和置信度，去掉用户相关信息
            package["crystals"].append({
                "rule": rule.get("rule", ""),
                "confidence": rule.get("confidence", 0.5),
                "scene": rule.get("scene", ""),
                "verified_by": 1,  # 至少被自己验证
            })

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
        返回新导入的规则数。
        """
        try:
            with open(import_path, "r", encoding="utf-8") as f:
                package = json.load(f)
        except Exception as e:
            logger.error(f"导入失败: {e}")
            return 0

        if package.get("format") != "taiji_experience_v1":
            return 0

        new_count = 0
        existing_rules = {item["rule"] for item in self.pool.get("shared", [])}

        for crystal in package.get("crystals", []):
            rule_text = crystal.get("rule", "")
            if not rule_text:
                continue

            if rule_text in existing_rules:
                # 已有的规则：增加验证次数，提高置信度
                for item in self.pool["shared"]:
                    if item["rule"] == rule_text:
                        item["verified_by"] = item.get("verified_by", 1) + 1
                        # 每多一个人验证，置信度微增（上限0.95）
                        item["confidence"] = min(
                            0.95, item["confidence"] + 0.05)
                        break
            else:
                # 新规则：以较低初始置信度加入
                self.pool.setdefault("shared", []).append({
                    "rule": rule_text,
                    "confidence": max(0.3, crystal.get("confidence", 0.5) * 0.6),
                    "scene": crystal.get("scene", ""),
                    "verified_by": 1,
                    "imported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                })
                new_count += 1
                existing_rules.add(rule_text)

        self.pool["last_import"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._save_pool()
        return new_count

    def get_shared_rules(self) -> list:
        """获取共享池中置信度 >= 0.4 的规则"""
        return [
            item for item in self.pool.get("shared", [])
            if item.get("confidence", 0) >= 0.4
        ]

    def get_shared_prompt(self) -> str:
        """生成注入system prompt的共享经验"""
        rules = self.get_shared_rules()
        if not rules:
            return ""

        lines = ["\n## 共享经验（来自其他用户的验证规律）"]
        for r in rules[:8]:  # 最多注入8条
            verified = r.get("verified_by", 1)
            tag = f"[{verified}人验证]" if verified > 1 else "[共享]"
            lines.append(f"- {tag} {r['rule']}")

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
        if not os.path.exists(self.pool_path):
            return {"shared": []}
        try:
            with open(self.pool_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"shared": []}

    def _save_pool(self):
        os.makedirs(os.path.dirname(self.pool_path) or ".", exist_ok=True)
        try:
            with open(self.pool_path, "w", encoding="utf-8") as f:
                json.dump(self.pool, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
