"""外部服务适配器模块

提供第三方服务的封装。
"""

from src.infrastructure.external.dingtalk_client import (
    DingTalkClient,
    DingTalkStreamHandler,
)

__all__ = [
    "DingTalkClient",
    "DingTalkStreamHandler",
]
