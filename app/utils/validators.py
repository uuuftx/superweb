"""通用验证工具"""

import re
from typing import Optional, Any
from pathlib import Path


def validate_workflow_name(name: str) -> tuple[bool, Optional[str]]:
    """
    验证工作流名称

    Args:
        name: 工作流名称

    Returns:
        (is_valid, error_message)
    """
    if not name:
        return False, "工作流名称不能为空"

    if len(name) > 100:
        return False, "工作流名称不能超过100个字符"

    # 只允许中文、字母、数字、下划线、连字符
    if not re.match(r'^[\u4e00-\u9fa5a-zA-Z0-9_\-]+$', name):
        return False, "工作流名称只能包含中文、字母、数字、下划线和连字符"

    return True, None


def validate_filename(filename: str, allowed_extensions: list[str] = None) -> tuple[bool, Optional[str]]:
    """
    验证文件名安全性

    Args:
        filename: 文件名
        allowed_extensions: 允许的扩展名列表（不含点号）

    Returns:
        (is_valid, error_message)
    """
    if not filename:
        return False, "文件名不能为空"

    # 检查路径遍历攻击
    if '/' in filename or '\\' in filename or '..' in filename:
        return False, "文件名包含非法字符"

    # 检查扩展名
    if allowed_extensions:
        if not any(filename.endswith(f'.{ext}') for ext in allowed_extensions):
            return False, f"只允许的文件类型: {', '.join(allowed_extensions)}"

    return True, None


def sanitize_path(path: str, base_dir: str = None) -> Optional[str]:
    """
    清理路径，防止路径遍历攻击

    Args:
        path: 要清理的路径
        base_dir: 基础目录（绝对路径）

    Returns:
        安全的绝对路径，如果不安全则返回None
    """
    if not path:
        return None

    # 解析路径
    p = Path(path).resolve()

    # 检查是否包含父目录引用
    if '..' in str(p):
        return None

    # 如果提供了基础目录，确保路径在基础目录内
    if base_dir:
        base = Path(base_dir).resolve()
        try:
            p.relative_to(base)
        except ValueError:
            return None

    return str(p)


def validate_json_path(json_path: str) -> tuple[bool, Optional[str]]:
    """
    验证JSON路径表达式

    Args:
        json_path: JSON路径（如 data.users[0].name）

    Returns:
        (is_valid, error_message)
    """
    if not json_path:
        return True, None

    # 基本的JSONPath验证
    pattern = r'^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*(\[\d+\])?)*$'
    if not re.match(pattern, json_path):
        return False, f"无效的JSON路径: {json_path}"

    return True, None


def truncate_string(s: str, max_length: int = 100, suffix: str = '...') -> str:
    """
    截断字符串到指定长度

    Args:
        s: 原始字符串
        max_length: 最大长度
        suffix: 截断后添加的后缀

    Returns:
        截断后的字符串
    """
    if len(s) <= max_length:
        return s
    return s[:max_length - len(suffix)] + suffix
