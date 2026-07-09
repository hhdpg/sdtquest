"""公共模块。

提供跨模块共享的工具和常量:
- utils: 通用工具函数（文本处理、ID 生成、时间格式化）
- cache: LRU 缓存
- constants: 全局常量

典型用法:
    >>> from src.shared.utils import truncate_text, generate_uuid
    >>> from src.shared.cache import LRUCache
    >>> from src.shared.constants import APP_NAME
"""

from src.shared.cache import LRUCache
from src.shared.constants import APP_DESCRIPTION, APP_NAME, APP_VERSION
from src.shared.utils import (
    clean_whitespace,
    extract_chinese_words,
    format_datetime,
    format_relative_time,
    generate_short_id,
    generate_uuid,
    safe_json_dumps,
    safe_json_loads,
    strip_think_tags,
    truncate_text,
)

__all__ = [
    # utils
    "generate_uuid",
    "generate_short_id",
    "truncate_text",
    "clean_whitespace",
    "strip_think_tags",
    "format_datetime",
    "format_relative_time",
    "safe_json_dumps",
    "safe_json_loads",
    "extract_chinese_words",
    # cache
    "LRUCache",
    # constants
    "APP_NAME",
    "APP_VERSION",
    "APP_DESCRIPTION",
]
