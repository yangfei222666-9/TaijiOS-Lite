"""
TaijiOS Premium 收费层 — 解锁高级进化功能

免费版：
  - 基础对话 + 经验结晶 + 卦象诊断 + 认知地图
  - 5条结晶上限
  - 共享经验只读（不能导出）

付费版（激活码）：
  - 无限结晶
  - 完整共享经验（导入导出）
  - 深度交叉分析（认知地图五维交叉）
  - 卦象趋势追踪（看你的状态变化曲线）
  - 优先体验新功能

激活方式：
  输入激活码 → 本地验证 + 写入license文件
"""

import json
import os
import time
import hashlib
import logging
from typing import Optional

logger = logging.getLogger("premium")

# ── 激活码体系 ──────────────────────────────────────────────────────────────
# 简单的离线验证方案：
# 激活码 = 前缀 + 时间戳哈希 + 校验位
# 后续可以接线上验证

ACTIVATION_PREFIX = "TAIJI"
# 预置的有效激活码种子（用于生成和验证）
VALID_SEEDS = [
    "yangfei2026", "taijios_alpha", "taijios_beta",
    "early_bird_001", "early_bird_002", "early_bird_003",
    "friend_pass_01", "friend_pass_02", "friend_pass_03",
    "vip_launch_01", "vip_launch_02", "vip_launch_03",
]


def generate_activation_code(seed: str) -> str:
    """从种子生成激活码"""
    h = hashlib.sha256(seed.encode()).hexdigest()[:12].upper()
    return f"{ACTIVATION_PREFIX}-{h[:4]}-{h[4:8]}-{h[8:12]}"


def get_all_valid_codes() -> set:
    """生成所有有效激活码"""
    return {generate_activation_code(s) for s in VALID_SEEDS}


# ── 功能限制 ──────────────────────────────────────────────────────────────

FREE_LIMITS = {
    "max_crystals": 5,          # 最多5条结晶
    "can_export": False,        # 不能导出经验
    "can_import": True,         # 可以导入（推广用）
    "deep_analysis": False,     # 不能深度交叉分析
    "hex_trend": False,         # 不能看卦象趋势
    "max_history": 20,          # 历史对话保留20轮
}

PREMIUM_LIMITS = {
    "max_crystals": 999,        # 无限结晶
    "can_export": True,         # 可以导出经验
    "can_import": True,         # 可以导入
    "deep_analysis": True,      # 深度交叉分析
    "hex_trend": True,          # 卦象趋势
    "max_history": 40,          # 历史对话保留40轮
}


class PremiumManager:
    """收费层管理器"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.license_path = os.path.join(data_dir, "license.json")
        self.license = self._load_license()

    @property
    def is_premium(self) -> bool:
        return self.license.get("activated", False)

    @property
    def limits(self) -> dict:
        return PREMIUM_LIMITS if self.is_premium else FREE_LIMITS

    def activate(self, code: str) -> tuple:
        """
        激活付费版。
        返回 (success: bool, message: str)
        """
        code = code.strip().upper()
        valid_codes = get_all_valid_codes()

        if code in valid_codes:
            self.license = {
                "activated": True,
                "code": code,
                "activated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "plan": "premium",
            }
            self._save_license()
            return True, "激活成功！已解锁全部高级功能"
        else:
            return False, "激活码无效，请检查后重试"

    def check_crystal_limit(self, current_count: int) -> tuple:
        """
        检查结晶数量是否超限。
        返回 (allowed: bool, message: str)
        """
        limit = self.limits["max_crystals"]
        if current_count >= limit:
            if not self.is_premium:
                return False, f"免费版最多{limit}条结晶，输入 upgrade 解锁无限结晶"
            return False, "结晶已达上限"
        return True, ""

    def check_export(self) -> tuple:
        """检查是否允许导出"""
        if not self.limits["can_export"]:
            return False, "导出经验是付费功能，输入 upgrade 解锁"
        return True, ""

    def check_deep_analysis(self) -> tuple:
        """检查是否允许深度分析"""
        if not self.limits["deep_analysis"]:
            return False, "深度交叉分析是付费功能，输入 upgrade 解锁"
        return True, ""

    def get_display(self) -> str:
        """状态展示"""
        if self.is_premium:
            activated_at = self.license.get("activated_at", "未知")
            return f"[会员] Premium 已激活 | {activated_at}"
        else:
            return "[免费版] 输入 upgrade 查看付费功能"

    def get_upgrade_info(self) -> str:
        """升级信息展示"""
        if self.is_premium:
            return "你已经是Premium会员了！"
        return """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  TaijiOS Premium — 解锁完整进化能力

  免费版 vs Premium：
  ┌────────────┬───────┬─────────┐
  │ 功能       │ 免费  │ Premium │
  ├────────────┼───────┼─────────┤
  │ 基础对话   │  ✓    │   ✓     │
  │ 卦象诊断   │  ✓    │   ✓     │
  │ 认知地图   │  ✓    │   ✓     │
  │ 经验结晶   │ 5条   │  无限   │
  │ 导出经验   │  ✗    │   ✓     │
  │ 导入经验   │  ✓    │   ✓     │
  │ 深度分析   │  ✗    │   ✓     │
  │ 卦象趋势   │  ✗    │   ✓     │
  │ 历史轮次   │ 20轮  │  40轮   │
  └────────────┴───────┴─────────┘

  激活方式：输入 activate <激活码>
  获取激活码：联系杨飞
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    def _load_license(self) -> dict:
        from .safe_io import safe_json_load
        return safe_json_load(self.license_path, {})

    def _save_license(self):
        from .safe_io import safe_json_save
        safe_json_save(self.license_path, self.license)
