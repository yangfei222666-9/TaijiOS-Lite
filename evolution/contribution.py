"""
贡献积分系统 — 越分享越强大

积分来源：
  对话积分：每轮对话 +1
  结晶积分：每产出一条结晶 +10
  分享积分：导出经验包 +20
  传播积分：你的经验被别人导入 +30/人
  验证积分：你导入的经验被AI采纳（置信度上升）+5
  易经积分：查看易经课堂 +2
  连续积分：连续使用天数 × 5

等级体系：
  Lv1 新兵（0-49）     → 刚开始了解自己
  Lv2 校尉（50-199）   → 开始有认知积累
  Lv3 将军（200-499）  → 认知地图初步成型
  Lv4 军师（500-999）  → 经验丰富，可以帮别人
  Lv5 国士（1000+）    → 认知进化的先行者

积分用途：
  达到Lv3自动解锁导出功能（不用Premium也能导出）
  达到Lv4显示「军师」徽章
  达到Lv5显示「国士」徽章 + 专属激活码
"""

import json
import os
import time
import hashlib
import logging
from .safe_io import safe_json_save, safe_json_load

logger = logging.getLogger("contribution")


# 等级定义
LEVELS = [
    (0,    "Lv1 新兵",   "刚开始了解自己"),
    (50,   "Lv2 校尉",   "开始有认知积累"),
    (200,  "Lv3 将军",   "认知地图初步成型"),
    (500,  "Lv4 军师",   "经验丰富，可以帮别人"),
    (1000, "Lv5 国士",   "认知进化的先行者"),
]

# 积分动作
POINT_ACTIONS = {
    "chat":         1,    # 每轮对话
    "crystal":      10,   # 产出一条结晶
    "export":       20,   # 导出经验包
    "imported_by":  30,   # 经验被别人导入（每人次）
    "import":       5,    # 导入别人的经验
    "yijing":       2,    # 查看易经课堂
    "daily_streak": 5,    # 连续使用（每天 × 5）
    "share":        3,    # 生成分享卡片
}


class ContributionSystem:
    """用户贡献积分追踪"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.score_path = os.path.join(data_dir, "contribution.json")
        self.data = self._load()

    @property
    def total_points(self) -> int:
        return self.data.get("total_points", 0)

    @property
    def level(self) -> tuple:
        """返回 (等级名, 描述, 下一级需要的分数)"""
        pts = self.total_points
        current = LEVELS[0]
        next_threshold = LEVELS[1][0] if len(LEVELS) > 1 else 999999
        for i, (threshold, name, desc) in enumerate(LEVELS):
            if pts >= threshold:
                current = (name, desc)
                if i + 1 < len(LEVELS):
                    next_threshold = LEVELS[i + 1][0]
                else:
                    next_threshold = 0  # 满级
        return current[0], current[1], next_threshold

    # 冷却时间（秒）：防止刷积分
    COOLDOWNS = {
        "yijing": 60,    # 易经课堂：1分钟冷却
        "share": 120,    # 分享卡片：2分钟冷却
    }

    def add_points(self, action: str, count: int = 1) -> int:
        """
        增加积分。有冷却时间的动作会被限制。
        返回本次获得的积分数。
        """
        # 冷却检查
        cd = self.COOLDOWNS.get(action, 0)
        if cd > 0:
            cooldowns = self.data.setdefault("_cooldowns", {})
            last = cooldowns.get(action, 0)
            now = time.time()
            if now - last < cd:
                return 0  # 冷却中，不加分
            cooldowns[action] = now

        points = POINT_ACTIONS.get(action, 0) * count
        if points <= 0:
            return 0

        self.data["total_points"] = self.data.get("total_points", 0) + points

        # 记录明细
        history = self.data.setdefault("history", [])
        history.append({
            "action": action,
            "points": points,
            "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })
        # 只保留最近100条明细
        if len(history) > 100:
            self.data["history"] = history[-100:]

        # 更新连续使用天数
        self._update_streak()

        self._save()
        return points

    def check_daily_bonus(self) -> int:
        """
        检查今日是否已签到，未签到则自动签到。
        返回签到获得的积分（0表示今天已签过）。
        """
        today = time.strftime("%Y-%m-%d")
        last_check = self.data.get("last_daily", "")

        if last_check == today:
            return 0

        self.data["last_daily"] = today
        streak = self.data.get("streak", 0) + 1
        self.data["streak"] = streak

        # 连续天数积分
        bonus = min(streak, 30) * POINT_ACTIONS["daily_streak"]
        self.data["total_points"] = self.data.get("total_points", 0) + bonus

        self._save()
        return bonus

    def get_contributor_id(self) -> str:
        """生成匿名贡献者ID（用于经验包追踪）"""
        cid = self.data.get("contributor_id")
        if not cid:
            # 用时间戳+随机数生成唯一ID
            raw = f"taiji_{time.time()}_{os.getpid()}"
            cid = hashlib.md5(raw.encode()).hexdigest()[:8]
            self.data["contributor_id"] = cid
            self._save()
        return cid

    def get_display(self) -> str:
        """状态展示"""
        pts = self.total_points
        level_name, level_desc, next_pts = self.level
        streak = self.data.get("streak", 0)

        lines = [f"[贡献] {pts}积分 | {level_name} — {level_desc}"]
        if next_pts > 0:
            remain = next_pts - pts
            lines.append(f"  距离下一级还需{remain}积分")
        else:
            lines.append(f"  已达最高等级！")
        if streak > 1:
            lines.append(f"  连续使用{streak}天")

        return "\n".join(lines)

    def get_leaderboard_entry(self) -> dict:
        """生成排行榜条目（用于导出包附带）"""
        return {
            "contributor_id": self.get_contributor_id(),
            "points": self.total_points,
            "level": self.level[0],
            "streak": self.data.get("streak", 0),
        }

    def get_points_breakdown(self) -> str:
        """积分明细展示"""
        history = self.data.get("history", [])
        if not history:
            return "  暂无积分记录"

        lines = ["  最近积分记录："]
        for entry in history[-10:]:
            action = entry.get("action", "")
            pts = entry.get("points", 0)
            t = entry.get("time", "")[:10]
            action_names = {
                "chat": "对话", "crystal": "结晶", "export": "导出",
                "imported_by": "被导入", "import": "导入",
                "yijing": "易经", "daily_streak": "签到", "share": "分享",
            }
            name = action_names.get(action, action)
            lines.append(f"    +{pts} {name} ({t})")

        return "\n".join(lines)

    def _update_streak(self):
        """更新连续使用天数"""
        today = time.strftime("%Y-%m-%d")
        last = self.data.get("last_active", "")
        self.data["last_active"] = today

        if last == today:
            return  # 今天已记录
        # 不检查是否连续，由check_daily_bonus处理

    def _load(self) -> dict:
        return safe_json_load(self.score_path,
                              {"total_points": 0, "streak": 0, "history": []})

    def _save(self):
        safe_json_save(self.score_path, self.data)
