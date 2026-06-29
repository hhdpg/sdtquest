"""会话管理模块。

本模块实现了 Bot 层的会话上下文管理功能，负责维护每个会话的对话历史，
支持 LRU 淘汰过期会话，确保线程安全。

主要类:
- SessionManager: 会话管理器，维护多轮对话上下文

典型用法:
    >>> from src.bot.session import SessionManager
    >>> manager = SessionManager(max_history=10, ttl_seconds=300)
    >>> manager.add_message("conv_123", user_message)
    >>> history = manager.get_history("conv_123")
"""

import asyncio
import threading
from datetime import datetime
from typing import Any

from loguru import logger

from src.config import settings
from src.domain.models import Conversation, Message


class SessionManager:
    """
    会话管理器。

    维护每个会话的对话历史，支持:
    - LRU 淘汰: 超出最大会话数时，淘汰最久未活跃的会话
    - TTL 过期: 超过 TTL 时间的会话自动清理
    - 线程安全: 支持多线程/异步环境下的并发访问

    Attributes:
        max_history: 每个会话最大保留的对话轮数
        ttl_seconds: 会话超时时间（秒），默认 300（5 分钟）
        max_sessions: 最大会话数量，超出时 LRU 淘汰

    Example:
        >>> manager = SessionManager(max_history=10, ttl_seconds=300)
        >>> msg = Message(role="user", content="如何创建订单?")
        >>> manager.add_message("conv_123", msg)
        >>> history = manager.get_history("conv_123")
        >>> len(history)
        1
    """

    def __init__(
        self,
        max_history: int | None = None,
        ttl_seconds: int | None = None,
        max_sessions: int = 1000,
    ):
        """
        初始化会话管理器。

        Args:
            max_history: 每个会话最大保留的对话轮数，默认从配置读取
            ttl_seconds: 会话超时时间（秒），默认从配置读取
            max_sessions: 最大会话数量，超出时 LRU 淘汰
        """
        self.max_history: int = max_history if max_history is not None else settings.SESSION_MAX_HISTORY
        self.ttl_seconds: int = ttl_seconds if ttl_seconds is not None else settings.SESSION_TTL_SECONDS
        self.max_sessions: int = max_sessions

        self._conversations: dict[str, Conversation] = {}
        self._lock = threading.Lock()

        logger.info(
            "SessionManager 初始化 | max_history={} | ttl={}s | max_sessions={}",
            self.max_history,
            self.ttl_seconds,
            self.max_sessions,
        )

    def get_history(self, conversation_id: str) -> list[Message]:
        """
        获取指定会话的对话历史。

        如果会话不存在或已过期，返回空列表。

        Args:
            conversation_id: 会话 ID

        Returns:
            消息列表，按时间正序排列
        """
        with self._lock:
            conversation = self._conversations.get(conversation_id)

            if conversation is None:
                logger.debug("会话不存在 | conversation_id={}", conversation_id[:20])
                return []

            # 检查是否过期
            if conversation.is_expired(self.ttl_seconds):
                logger.info(
                    "会话已过期，清除 | conversation_id={} | last_active={}",
                    conversation_id[:20],
                    conversation.last_active,
                )
                del self._conversations[conversation_id]
                return []

            # 更新活跃时间（访问也算活跃）
            conversation.last_active = datetime.now()

            messages = conversation.get_recent_messages(self.max_history)
            logger.debug(
                "获取对话历史 | conversation_id={} | message_count={}",
                conversation_id[:20],
                len(messages),
            )
            return messages

    def add_message(self, conversation_id: str, message: Message) -> None:
        """
        添加消息到指定会话。

        如果会话不存在，则创建新会话。如果超出最大会话数，
        则淘汰最久未活跃的会话（LRU）。

        Args:
            conversation_id: 会话 ID
            message: 消息对象
        """
        with self._lock:
            # 检查会话是否存在，不存在则创建
            if conversation_id not in self._conversations:
                self._create_conversation(conversation_id)

            conversation = self._conversations[conversation_id]

            # 检查是否过期，过期则重置
            if conversation.is_expired(self.ttl_seconds):
                logger.info(
                    "会话已过期，重新创建 | conversation_id={}",
                    conversation_id[:20],
                )
                self._conversations[conversation_id] = Conversation(id=conversation_id)
                conversation = self._conversations[conversation_id]

            # 添加消息
            conversation.add_message(message)

            # 限制消息数量（保留最近的 N 条）
            if len(conversation.messages) > self.max_history * 2:
                conversation.messages = conversation.messages[-self.max_history:]

            logger.debug(
                "消息已添加 | conversation_id={} | role={} | total={}",
                conversation_id[:20],
                message.role,
                conversation.message_count(),
            )

    def clear(self, conversation_id: str) -> None:
        """
        清空指定会话的历史。

        Args:
            conversation_id: 会话 ID
        """
        with self._lock:
            if conversation_id in self._conversations:
                self._conversations[conversation_id].clear()
                logger.info("会话已清空 | conversation_id={}", conversation_id[:20])
            else:
                logger.debug("会话不存在，无需清空 | conversation_id={}", conversation_id[:20])

    def remove(self, conversation_id: str) -> None:
        """
        移除指定会话。

        Args:
            conversation_id: 会话 ID
        """
        with self._lock:
            if conversation_id in self._conversations:
                del self._conversations[conversation_id]
                logger.info("会话已移除 | conversation_id={}", conversation_id[:20])

    def cleanup_expired(self) -> int:
        """
        清理所有过期的会话。

        Returns:
            被清理的会话数量
        """
        with self._lock:
            expired_ids = [
                conv_id
                for conv_id, conv in self._conversations.items()
                if conv.is_expired(self.ttl_seconds)
            ]

            for conv_id in expired_ids:
                del self._conversations[conv_id]

            if expired_ids:
                logger.info("清理过期会话 | count={} | remaining={}", len(expired_ids), len(self._conversations))

            return len(expired_ids)

    @property
    def active_count(self) -> int:
        """
        当前活跃的会话数量。

        Returns:
            活跃会话数
        """
        with self._lock:
            return len(self._conversations)

    @property
    def session_ids(self) -> list[str]:
        """
        当前所有活跃会话的 ID 列表。

        Returns:
            会话 ID 列表
        """
        with self._lock:
            return list(self._conversations.keys())

    def _create_conversation(self, conversation_id: str) -> None:
        """
        创建新会话（内部方法，需在锁内调用）。

        如果超出最大会话数，先淘汰最久未活跃的会话。

        Args:
            conversation_id: 会话 ID
        """
        # LRU 淘汰: 超出最大会话数时，淘汰最久未活跃的
        if len(self._conversations) >= self.max_sessions:
            self._evict_lru()

        self._conversations[conversation_id] = Conversation(id=conversation_id)
        logger.debug(
            "创建新会话 | conversation_id={} | total={}",
            conversation_id[:20],
            len(self._conversations),
        )

    def _evict_lru(self) -> None:
        """
        淘汰最久未活跃的会话（内部方法，需在锁内调用）。
        """
        if not self._conversations:
            return

        # 找到最久未活跃的会话
        oldest_id = min(
            self._conversations,
            key=lambda cid: self._conversations[cid].last_active,
        )

        del self._conversations[oldest_id]
        logger.info(
            "LRU 淘汰会话 | conversation_id={} | remaining={}",
            oldest_id[:20],
            len(self._conversations),
        )

    def get_stats(self) -> dict[str, Any]:
        """
        获取会话管理器统计信息。

        Returns:
            包含活跃会话数、最大历史数等信息的字典
        """
        with self._lock:
            total_messages = sum(
                conv.message_count() for conv in self._conversations.values()
            )
            return {
                "active_sessions": len(self._conversations),
                "max_sessions": self.max_sessions,
                "max_history": self.max_history,
                "ttl_seconds": self.ttl_seconds,
                "total_messages": total_messages,
            }
