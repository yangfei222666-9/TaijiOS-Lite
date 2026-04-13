"""
TaijiOS 生态制度 — 让认知进化形成网络效应

核心：每个TaijiOS实例 = 一个智能体(Agent)节点
      所有智能体组成「认知进化网络」，互相学习、分享、迭代

智能体网络：
  Agent A 对话进化 → 经验结晶 → 导出.taiji
                                    ↓
  Agent B 导入 → 验证 → 置信度↑ → 融入自己的认知
                                    ↓
  Agent C 导入A+B的经验 → 交叉验证 → 全网经验质量↑
                                    ↓
  所有Agent的共享池越来越强 → 新Agent加入就自带全网最佳经验

生态循环：
  个人进化 → 经验结晶 → 分享经验 → 他人导入 → 验证提升置信度
       ↑                                              |
       └──────── 更好的共享经验池 ←─────────────────────┘

用户成长路径：
  新兵 → 自己用，积累经验
  校尉 → 开始有结晶，可以帮到自己
  将军 → 可以导出经验，开始帮别人
  军师 → 经验丰富，成为节点，经验被大量导入
  国士 → 生态贡献者，推动整个网络进化

生态规则：
  1. 经验质量靠验证 — 被越多人导入+采纳，置信度越高
  2. 分享越多越强 — 你的经验帮了别人，你也得积分
  3. 多样性优先 — 不同人的经验交叉验证，比单人重复更有价值
  4. 军师无废话 — 经验结晶只保留真正有用的规则
  5. 开放流通 — .taiji文件可以在任何渠道传播
  6. 智能体自治 — 每个Agent独立进化，但经验共享

成就系统：
  解锁条件基于真实行为，不是充钱
"""

import json
import os
import time
import logging
from .safe_io import safe_json_save, safe_json_load

logger = logging.getLogger("ecosystem")


# ── 成就定义 ──────────────────────────────────────────

ACHIEVEMENTS = {
    # 对话类
    "first_chat": {
        "name": "初出茅庐",
        "desc": "完成第一次对话",
        "condition": lambda s: s.get("total_chats", 0) >= 1,
        "points": 5,
    },
    "chat_10": {
        "name": "言之有物",
        "desc": "累计对话10轮",
        "condition": lambda s: s.get("total_chats", 0) >= 10,
        "points": 10,
    },
    "chat_50": {
        "name": "促膝长谈",
        "desc": "累计对话50轮",
        "condition": lambda s: s.get("total_chats", 0) >= 50,
        "points": 20,
    },
    "chat_200": {
        "name": "知己知彼",
        "desc": "累计对话200轮",
        "condition": lambda s: s.get("total_chats", 0) >= 200,
        "points": 50,
    },

    # 结晶类
    "first_crystal": {
        "name": "初见端倪",
        "desc": "产出第一条经验结晶",
        "condition": lambda s: s.get("total_crystals", 0) >= 1,
        "points": 10,
    },
    "crystal_10": {
        "name": "集腋成裘",
        "desc": "累计10条经验结晶",
        "condition": lambda s: s.get("total_crystals", 0) >= 10,
        "points": 30,
    },

    # 分享类
    "first_export": {
        "name": "乐善好施",
        "desc": "第一次导出经验",
        "condition": lambda s: s.get("total_exports", 0) >= 1,
        "points": 15,
    },
    "first_import": {
        "name": "兼收并蓄",
        "desc": "第一次导入别人的经验",
        "condition": lambda s: s.get("total_imports", 0) >= 1,
        "points": 10,
    },
    "imported_by_3": {
        "name": "桃李天下",
        "desc": "你的经验被3人以上导入",
        "condition": lambda s: s.get("imported_by_count", 0) >= 3,
        "points": 50,
    },

    # 连续使用类
    "streak_3": {
        "name": "三日不辍",
        "desc": "连续使用3天",
        "condition": lambda s: s.get("streak", 0) >= 3,
        "points": 10,
    },
    "streak_7": {
        "name": "七日精进",
        "desc": "连续使用7天",
        "condition": lambda s: s.get("streak", 0) >= 7,
        "points": 25,
    },
    "streak_30": {
        "name": "月度修行",
        "desc": "连续使用30天",
        "condition": lambda s: s.get("streak", 0) >= 30,
        "points": 100,
    },

    # 易经类
    "yijing_first": {
        "name": "问道周易",
        "desc": "第一次查看易经课堂",
        "condition": lambda s: s.get("total_yijing", 0) >= 1,
        "points": 5,
    },
    "yijing_10": {
        "name": "易理初通",
        "desc": "查看易经课堂10次",
        "condition": lambda s: s.get("total_yijing", 0) >= 10,
        "points": 20,
    },

    # 生态类
    "share_card": {
        "name": "广而告之",
        "desc": "生成分享卡片",
        "condition": lambda s: s.get("total_shares", 0) >= 1,
        "points": 5,
    },
    "ecosystem_aware": {
        "name": "生态觉醒",
        "desc": "查看生态制度",
        "condition": lambda s: s.get("viewed_ecosystem", 0) >= 1,
        "points": 5,
    },
}


# ── 生态角色定义 ──────────────────────────────────────

ECOSYSTEM_ROLES = {
    "newcomer": {
        "name": "探索者",
        "min_points": 0,
        "desc": "刚加入生态，正在了解自己",
        "rights": ["基础对话", "导入经验", "查看卦象"],
        "duties": ["持续对话，积累认知"],
    },
    "contributor": {
        "name": "贡献者",
        "min_points": 50,
        "desc": "开始产出经验，能帮到自己",
        "rights": ["经验结晶", "易经课堂", "分享卡片"],
        "duties": ["产出高质量对话", "尝试不同话题"],
    },
    "sharer": {
        "name": "传播者",
        "min_points": 200,
        "desc": "有足够经验可以帮别人",
        "rights": ["导出经验包", "完整认知地图"],
        "duties": ["主动分享经验", "帮助新人入门"],
    },
    "mentor": {
        "name": "导师",
        "min_points": 500,
        "desc": "经验被多人采纳，是生态节点",
        "rights": ["军师徽章", "优先体验新功能"],
        "duties": ["维护经验质量", "引导社区方向"],
    },
    "sage": {
        "name": "先行者",
        "min_points": 1000,
        "desc": "认知进化的标杆，推动网络进化",
        "rights": ["国士徽章", "专属激活码", "生态治理投票权"],
        "duties": ["推广认知进化理念", "贡献顶级经验"],
    },
}


class EcosystemManager:
    """生态系统管理器 — 成就、角色、网络健康"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.eco_path = os.path.join(data_dir, "ecosystem.json")
        self.data = self._load()

    def get_role(self, total_points: int) -> dict:
        """根据积分确定生态角色"""
        current = ECOSYSTEM_ROLES["newcomer"]
        current_key = "newcomer"
        for key, role in ECOSYSTEM_ROLES.items():
            if total_points >= role["min_points"]:
                current = role
                current_key = key
        return {"key": current_key, **current}

    def check_achievements(self, stats: dict) -> list:
        """
        检查并解锁成就。
        stats 应包含：total_chats, total_crystals, total_exports,
                      total_imports, imported_by_count, streak,
                      total_yijing, total_shares, viewed_ecosystem
        返回本次新解锁的成就列表。
        """
        unlocked = self.data.get("unlocked_achievements", [])
        newly_unlocked = []

        for aid, achievement in ACHIEVEMENTS.items():
            if aid in unlocked:
                continue
            try:
                if achievement["condition"](stats):
                    unlocked.append(aid)
                    newly_unlocked.append({
                        "id": aid,
                        "name": achievement["name"],
                        "desc": achievement["desc"],
                        "points": achievement["points"],
                    })
            except Exception:
                pass

        if newly_unlocked:
            self.data["unlocked_achievements"] = unlocked
            self._save()

        return newly_unlocked

    def record_action(self, action: str, count: int = 1):
        """记录生态行为（用于成就统计）"""
        action_map = {
            "chat": "total_chats",
            "crystal": "total_crystals",
            "export": "total_exports",
            "import": "total_imports",
            "imported_by": "imported_by_count",
            "yijing": "total_yijing",
            "share": "total_shares",
            "view_ecosystem": "viewed_ecosystem",
        }
        stat_key = action_map.get(action)
        if stat_key:
            stats = self.data.setdefault("stats", {})
            stats[stat_key] = stats.get(stat_key, 0) + count
            self._save()

    def update_streak(self, streak: int):
        """更新连续使用天数（从contribution同步）"""
        stats = self.data.setdefault("stats", {})
        stats["streak"] = streak
        self._save()

    def get_stats(self) -> dict:
        """获取所有统计数据"""
        return self.data.get("stats", {})

    def get_unlocked_achievements(self) -> list:
        """获取已解锁的成就列表"""
        unlocked = self.data.get("unlocked_achievements", [])
        result = []
        for aid in unlocked:
            if aid in ACHIEVEMENTS:
                a = ACHIEVEMENTS[aid]
                result.append({
                    "id": aid,
                    "name": a["name"],
                    "desc": a["desc"],
                    "points": a["points"],
                })
        return result

    def get_locked_achievements(self) -> list:
        """获取未解锁的成就列表（提示下一步目标）"""
        unlocked = set(self.data.get("unlocked_achievements", []))
        result = []
        for aid, a in ACHIEVEMENTS.items():
            if aid not in unlocked:
                result.append({
                    "id": aid,
                    "name": a["name"],
                    "desc": a["desc"],
                    "points": a["points"],
                })
        return result

    def register_agent(self, contributor_id: str, agent_info: dict):
        """注册/更新本地Agent节点信息"""
        network = self.data.setdefault("agent_network", {})
        network["self"] = {
            "id": contributor_id,
            "crystals": agent_info.get("crystals", 0),
            "shared_rules": agent_info.get("shared_rules", 0),
            "points": agent_info.get("points", 0),
            "level": agent_info.get("level", ""),
            "last_active": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self._save()

    def record_peer(self, peer_id: str, peer_info: dict):
        """记录接触过的其他Agent节点（通过导入/导出）"""
        peers = self.data.setdefault("known_peers", {})
        existing = peers.get(peer_id, {})
        existing.update({
            "id": peer_id,
            "last_exchange": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "exchanges": existing.get("exchanges", 0) + 1,
            "rules_received": existing.get("rules_received", 0) + peer_info.get("rules_count", 0),
        })
        peers[peer_id] = existing
        self._save()

    def get_network_stats(self) -> dict:
        """获取Agent网络统计"""
        peers = self.data.get("known_peers", {})
        stats = self.get_stats()
        return {
            "known_agents": len(peers),
            "total_exchanges": sum(p.get("exchanges", 0) for p in peers.values()),
            "total_rules_received": sum(p.get("rules_received", 0) for p in peers.values()),
            "total_exports": stats.get("total_exports", 0),
            "total_imports": stats.get("total_imports", 0),
        }

    def get_ecosystem_display(self, total_points: int) -> str:
        """完整的生态制度展示"""
        role = self.get_role(total_points)
        unlocked = self.get_unlocked_achievements()
        locked = self.get_locked_achievements()
        stats = self.get_stats()
        net = self.get_network_stats()

        lines = []
        lines.append("")
        lines.append("━" * 50)
        lines.append("  TaijiOS 生态制度 — 认知进化共同体")
        lines.append("━" * 50)

        # 生态理念
        lines.append("")
        lines.append("  核心理念：")
        lines.append("    每个TaijiOS = 一个智能体(Agent)")
        lines.append("    所有智能体组成认知进化网络")
        lines.append("    你的经验帮别人，别人的经验帮你")
        lines.append("    网络越大，每个人进化越快")

        # 你的Agent节点
        lines.append("")
        lines.append(f"  你的角色：【{role['name']}】— {role['desc']}")
        lines.append(f"  当前积分：{total_points}")
        lines.append("")
        lines.append("  你的权益：")
        for r in role["rights"]:
            lines.append(f"    ● {r}")
        lines.append("  你的责任：")
        for d in role["duties"]:
            lines.append(f"    ○ {d}")

        # Agent网络状态
        lines.append("")
        lines.append("  ── 智能体网络 ──")
        lines.append(f"    已连接Agent数：{net['known_agents']}")
        lines.append(f"    经验交换次数：{net['total_exchanges']}")
        lines.append(f"    收到的规则数：{net['total_rules_received']}")
        lines.append(f"    导出次数：{net['total_exports']} | 导入次数：{net['total_imports']}")

        # 智能体互学机制
        lines.append("")
        lines.append("  ── 智能体互学机制 ──")
        lines.append("    1. 你对话 → 军师为你产出经验结晶")
        lines.append("    2. 你导出 → .taiji经验包发给任何Agent")
        lines.append("    3. 对方导入 → 经验融入对方的认知系统")
        lines.append("    4. 多人验证 → 置信度上升，经验质量越来越高")
        lines.append("    5. 全网受益 → 新Agent加入直接继承最佳经验")
        lines.append("")
        lines.append("    每个Agent独立进化，但经验实时流通")
        lines.append("    你的军师 + 别人的军师 = 超级军师团")

        # 成长路径
        lines.append("")
        lines.append("  ── 成长路径 ──")
        for key, r in ECOSYSTEM_ROLES.items():
            marker = "▶" if key == role["key"] else " "
            pts = r["min_points"]
            lines.append(f"  {marker} {r['name']}（{pts}分）— {r['desc']}")

        # 成就墙
        lines.append("")
        lines.append("  ── 成就墙 ──")
        if unlocked:
            for a in unlocked:
                lines.append(f"    ★ {a['name']} — {a['desc']}（+{a['points']}分）")
        else:
            lines.append("    还没有成就，继续加油！")

        # 下一个目标
        if locked:
            lines.append("")
            lines.append("  ── 下一步目标 ──")
            shown = 0
            for a in locked:
                if shown >= 3:
                    lines.append(f"    ... 还有{len(locked) - shown}个成就等你解锁")
                    break
                lines.append(f"    ○ {a['name']} — {a['desc']}")
                shown += 1

        # 六条铁律
        lines.append("")
        lines.append("  ── 六条铁律 ──")
        lines.append("    1. 经验靠验证 — 被越多Agent采纳，质量越高")
        lines.append("    2. 分享越多越强 — 帮别人就是帮自己")
        lines.append("    3. 多样性优先 — 不同Agent的经验交叉验证最有价值")
        lines.append("    4. 军师无废话 — 只保留真正有用的规则")
        lines.append("    5. 开放流通 — .taiji文件自由传播，无平台绑定")
        lines.append("    6. 随时迭代 — 每个Agent随时准备好接收新经验")

        # 参与方式
        lines.append("")
        lines.append("  ── 如何参与 ──")
        lines.append("    → 坚持对话，让你的Agent越来越懂你")
        lines.append("    → 用 export 导出经验，发给其他Agent")
        lines.append("    → 用 import 导入别人的经验包")
        lines.append("    → 用 share 生成分享卡片，招募新Agent加入")
        lines.append("    → 用 yijing 学习易经，理解卦象背后的智慧")
        lines.append("    → 邀请更多人，壮大智能体网络")

        lines.append("")
        lines.append("  你不是一个人在进化。")
        lines.append("  每个Agent都是网络的一个神经元。")
        lines.append("  网络越大，每个人越聪明。")
        lines.append("━" * 50)

        return "\n".join(lines)

    def get_brief_display(self, total_points: int) -> str:
        """简要生态状态（用于status命令）"""
        role = self.get_role(total_points)
        unlocked_count = len(self.data.get("unlocked_achievements", []))
        total_count = len(ACHIEVEMENTS)
        return f"  [生态] {role['name']} | 成就 {unlocked_count}/{total_count}"

    def _load(self) -> dict:
        return safe_json_load(self.eco_path,
                              {"unlocked_achievements": [], "stats": {}})

    def _save(self):
        safe_json_save(self.eco_path, self.data)
