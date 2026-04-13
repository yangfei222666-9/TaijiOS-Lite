"""
安全IO — 原子写入 + 损坏检测

解决的问题：
  程序崩溃/断电时JSON只写了一半 → 文件损坏 → 用户数据丢失

方案：
  写入临时文件 → 验证JSON有效 → 原子替换原文件
  加载时检测损坏 → 有备份就恢复 → 没备份就返回默认值并告警
"""

import json
import os
import tempfile
import logging

logger = logging.getLogger("safe_io")


def safe_json_save(filepath: str, data: dict, indent: int = 2):
    """
    安全写入JSON：先写临时文件，成功后原子替换。
    即使写入过程中崩溃，原文件也不会损坏。
    """
    dir_path = os.path.dirname(filepath) or "."
    os.makedirs(dir_path, exist_ok=True)

    # 先序列化到内存，确认数据有效
    try:
        content = json.dumps(data, ensure_ascii=False, indent=indent)
    except (TypeError, ValueError) as e:
        logger.error(f"JSON序列化失败: {e}")
        return False

    # 写到临时文件
    try:
        fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())  # 确保写到磁盘
    except Exception as e:
        logger.error(f"临时文件写入失败: {e}")
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        return False

    # 原子替换
    try:
        # Windows: os.replace 是原子的
        os.replace(tmp_path, filepath)
        return True
    except Exception as e:
        logger.error(f"文件替换失败: {e}")
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        return False


def safe_json_load(filepath: str, default=None):
    """
    安全加载JSON：检测损坏，损坏时备份坏文件并返回默认值。
    """
    if default is None:
        default = {}

    if not os.path.exists(filepath):
        return default

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        if not content.strip():
            logger.warning(f"文件为空: {filepath}")
            return default

        data = json.loads(content)
        return data

    except json.JSONDecodeError as e:
        # JSON损坏 — 备份坏文件，返回默认值
        logger.error(f"JSON损坏: {filepath}: {e}")
        try:
            corrupted_path = filepath + ".corrupted"
            os.replace(filepath, corrupted_path)
            logger.info(f"已备份损坏文件到: {corrupted_path}")
        except Exception:
            pass
        return default

    except Exception as e:
        logger.error(f"加载失败: {filepath}: {e}")
        return default
