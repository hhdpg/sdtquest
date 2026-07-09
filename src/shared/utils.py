"""公共工具模块。

提供跨模块共享的通用工具函数，包括:
- 文本处理（截断、清理、关键词提取）
- ID 生成
- 时间格式化
- JSON 安全序列化
"""

import json
import re
from datetime import datetime
from uuid import uuid4


# ============================================================================
# ID 生成
# ============================================================================

def generate_uuid() -> str:
    """
    生成 UUID 字符串

    Returns:
        UUID 字符串（小写，无连字符的短格式）
    """
    return str(uuid4())


def generate_short_id(prefix: str = "") -> str:
    """
    生成短 ID（UUID 前 8 位）

    Args:
        prefix: 可选前缀

    Returns:
        短 ID 字符串
    """
    short = uuid4().hex[:8]
    return f"{prefix}{short}" if prefix else short


# ============================================================================
# 文本处理
# ============================================================================

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    截断文本到指定长度

    Args:
        text: 原始文本
        max_length: 最大长度（包含 suffix）
        suffix: 截断后缀

    Returns:
        截断后的文本
    """
    if not text or len(text) <= max_length:
        return text or ""
    return text[: max_length - len(suffix)] + suffix


def clean_whitespace(text: str) -> str:
    """
    清理多余空白字符

    将多个连续空白字符替换为单个空格，并去除首尾空白。
    保留换行符，但合并连续换行。

    Args:
        text: 原始文本

    Returns:
        清理后的文本
    """
    if not text:
        return ""
    # 合并连续换行
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 合并行内空白
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def strip_think_tags(text: str) -> str:
    """
    去除 LLM 输出中的 <think>...</think> 标签

    Args:
        text: LLM 生成的原始文本

    Returns:
        去除 think 标签后的文本
    """
    if not text or "<think>" not in text:
        return text or ""
    return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()


# ============================================================================
# 时间处理
# ============================================================================

def format_datetime(dt: datetime | None = None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    格式化日期时间

    Args:
        dt: 日期时间对象，默认使用当前时间
        fmt: 格式化字符串

    Returns:
        格式化后的时间字符串
    """
    if dt is None:
        dt = datetime.now()
    return dt.strftime(fmt)


def format_relative_time(dt: datetime) -> str:
    """
    格式化为相对时间（如 "5 分钟前"、"2 小时前"）

    Args:
        dt: 日期时间对象

    Returns:
        相对时间字符串
    """
    now = datetime.now()
    diff = (now - dt).total_seconds()

    if diff < 60:
        return "刚刚"
    elif diff < 3600:
        minutes = int(diff / 60)
        return f"{minutes} 分钟前"
    elif diff < 86400:
        hours = int(diff / 3600)
        return f"{hours} 小时前"
    elif diff < 86400 * 30:
        days = int(diff / 86400)
        return f"{days} 天前"
    else:
        return dt.strftime("%Y-%m-%d")


# ============================================================================
# JSON 处理
# ============================================================================

def safe_json_dumps(obj, ensure_ascii: bool = False, default=str) -> str:
    """
    安全的 JSON 序列化

    Args:
        obj: 待序列化对象
        ensure_ascii: 是否转义非 ASCII 字符
        default: 默认序列化函数（处理 datetime 等）

    Returns:
        JSON 字符串
    """
    try:
        return json.dumps(obj, ensure_ascii=ensure_ascii, default=default)
    except (TypeError, ValueError) as e:
        return f'{{"error": "JSON 序列化失败: {e}"}}'


def safe_json_loads(text: str, default=None):
    """
    安全的 JSON 反序列化

    Args:
        text: JSON 字符串
        default: 解析失败时的默认值

    Returns:
        反序列化后的对象，或 default
    """
    if not text:
        return default
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


# ============================================================================
# 关键词提取
# ============================================================================

def extract_chinese_words(text: str, min_length: int = 2) -> list[str]:
    """
    提取中文词语（简易分词）

    基于连续中文字符匹配，适用于简单场景。

    Args:
        text: 输入文本
        min_length: 最小词语长度

    Returns:
        中文词语列表（去重）
    """
    if not text:
        return []
    # 匹配连续中文字符
    words = re.findall(r"[一-鿿]+", text)
    # 过滤短词并去重
    seen: set[str] = set()
    result: list[str] = []
    for word in words:
        if len(word) >= min_length and word not in seen:
            seen.add(word)
            result.append(word)
    return result
