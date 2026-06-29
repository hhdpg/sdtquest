"""SessionManager 单元测试。

测试会话管理器的所有功能:
- 基本消息添加和获取
- LRU 淘汰
- TTL 过期
- 并发安全
- 会话清理
"""

import time
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from src.bot.session import SessionManager
from src.domain.models import Conversation, Message


class TestSessionManager:
    """SessionManager 单元测试"""

    @pytest.fixture
    def session_manager(self) -> SessionManager:
        """创建默认配置的 SessionManager"""
        return SessionManager(max_history=5, ttl_seconds=300, max_sessions=3)

    # ====================================================================
    # 基本操作
    # ====================================================================

    def test_init_defaults(self) -> None:
        """测试默认初始化"""
        manager = SessionManager()
        assert manager.max_history == 10  # 默认值
        assert manager.ttl_seconds == 300
        assert manager.max_sessions == 1000
        assert manager.active_count == 0

    def test_init_custom_values(self) -> None:
        """测试自定义初始化"""
        manager = SessionManager(max_history=20, ttl_seconds=600, max_sessions=500)
        assert manager.max_history == 20
        assert manager.ttl_seconds == 600
        assert manager.max_sessions == 500

    def test_add_message_creates_conversation(self, session_manager: SessionManager) -> None:
        """测试添加消息时自动创建会话"""
        msg = Message(role="user", content="你好")
        session_manager.add_message("conv_1", msg)

        assert session_manager.active_count == 1
        assert "conv_1" in session_manager.session_ids

    def test_get_history_empty_conversation(self, session_manager: SessionManager) -> None:
        """测试获取不存在的会话历史"""
        history = session_manager.get_history("nonexistent")
        assert history == []

    def test_add_and_get_message(self, session_manager: SessionManager) -> None:
        """测试添加消息后获取"""
        msg = Message(role="user", content="如何创建订单?")
        session_manager.add_message("conv_1", msg)

        history = session_manager.get_history("conv_1")
        assert len(history) == 1
        assert history[0].content == "如何创建订单?"
        assert history[0].role == "user"

    def test_add_multiple_messages(self, session_manager: SessionManager) -> None:
        """测试添加多条消息"""
        msgs = [
            Message(role="user", content="问题1"),
            Message(role="assistant", content="回答1"),
            Message(role="user", content="问题2"),
        ]
        for msg in msgs:
            session_manager.add_message("conv_1", msg)

        history = session_manager.get_history("conv_1")
        assert len(history) == 3
        assert history[0].content == "问题1"
        assert history[1].content == "回答1"
        assert history[2].content == "问题2"

    def test_max_history_limit(self) -> None:
        """测试超过最大历史数时的截断"""
        manager = SessionManager(max_history=3, ttl_seconds=300)

        # 添加 6 条消息
        for i in range(6):
            msg = Message(role="user", content=f"消息{i}")
            manager.add_message("conv_1", msg)

        # get_history 只返回最近 3 条
        history = manager.get_history("conv_1")
        assert len(history) == 3
        assert history[0].content == "消息3"
        assert history[2].content == "消息5"

    # ====================================================================
    # TTL 过期
    # ====================================================================

    def test_expired_session_returns_empty(self, session_manager: SessionManager) -> None:
        """测试过期会话返回空列表"""
        msg = Message(role="user", content="测试")
        session_manager.add_message("conv_1", msg)

        # 手动设置过期时间
        conv = session_manager._conversations["conv_1"]
        conv.last_active = datetime.now() - timedelta(seconds=600)

        history = session_manager.get_history("conv_1")
        assert history == []
        assert session_manager.active_count == 0  # 过期会话被清除

    def test_expired_session_recreated_on_add(self, session_manager: SessionManager) -> None:
        """测试过期会话重新添加消息时重新创建"""
        msg1 = Message(role="user", content="旧消息")
        session_manager.add_message("conv_1", msg1)

        # 手动设置过期
        conv = session_manager._conversations["conv_1"]
        conv.last_active = datetime.now() - timedelta(seconds=600)

        # 添加新消息应该重新创建会话
        msg2 = Message(role="user", content="新消息")
        session_manager.add_message("conv_1", msg2)

        history = session_manager.get_history("conv_1")
        assert len(history) == 1
        assert history[0].content == "新消息"

    # ====================================================================
    # LRU 淘汰
    # ====================================================================

    def test_lru_eviction(self) -> None:
        """测试 LRU 淘汰最久未活跃的会话"""
        manager = SessionManager(max_history=5, ttl_seconds=300, max_sessions=3)

        # 创建 3 个会话
        for i in range(3):
            msg = Message(role="user", content=f"消息{i}")
            manager.add_message(f"conv_{i}", msg)
            time.sleep(0.01)  # 确保 last_active 不同

        assert manager.active_count == 3

        # 创建第 4 个会话，应该淘汰 conv_0（最久未活跃）
        msg = Message(role="user", content="新消息")
        manager.add_message("conv_3", msg)

        assert manager.active_count == 3
        assert "conv_0" not in manager.session_ids
        assert "conv_3" in manager.session_ids

    def test_lru_access_updates_activity(self) -> None:
        """测试访问会话会更新活跃时间"""
        manager = SessionManager(max_history=5, ttl_seconds=300, max_sessions=3)

        # 创建 3 个会话
        for i in range(3):
            msg = Message(role="user", content=f"消息{i}")
            manager.add_message(f"conv_{i}", msg)
            time.sleep(0.01)

        # 访问 conv_0，更新其活跃时间
        manager.get_history("conv_0")
        time.sleep(0.01)

        # 创建第 4 个会话，应该淘汰 conv_1（最久未活跃）
        msg = Message(role="user", content="新消息")
        manager.add_message("conv_3", msg)

        assert "conv_0" in manager.session_ids
        assert "conv_1" not in manager.session_ids

    # ====================================================================
    # 清理和移除
    # ====================================================================

    def test_clear_conversation(self, session_manager: SessionManager) -> None:
        """测试清空会话"""
        msg = Message(role="user", content="测试")
        session_manager.add_message("conv_1", msg)

        session_manager.clear("conv_1")
        history = session_manager.get_history("conv_1")
        assert history == []

    def test_clear_nonexistent_conversation(self, session_manager: SessionManager) -> None:
        """测试清空不存在的会话不报错"""
        session_manager.clear("nonexistent")  # 不应抛异常

    def test_remove_conversation(self, session_manager: SessionManager) -> None:
        """测试移除会话"""
        msg = Message(role="user", content="测试")
        session_manager.add_message("conv_1", msg)

        session_manager.remove("conv_1")
        assert session_manager.active_count == 0
        assert "conv_1" not in session_manager.session_ids

    def test_remove_nonexistent_conversation(self, session_manager: SessionManager) -> None:
        """测试移除不存在的会话不报错"""
        session_manager.remove("nonexistent")  # 不应抛异常

    def test_cleanup_expired(self) -> None:
        """测试批量清理过期会话"""
        manager = SessionManager(max_history=5, ttl_seconds=300)

        # 添加 3 个会话
        for i in range(3):
            msg = Message(role="user", content=f"消息{i}")
            manager.add_message(f"conv_{i}", msg)

        # 让 conv_0 和 conv_1 过期
        manager._conversations["conv_0"].last_active = datetime.now() - timedelta(seconds=600)
        manager._conversations["conv_1"].last_active = datetime.now() - timedelta(seconds=600)

        cleaned = manager.cleanup_expired()
        assert cleaned == 2
        assert manager.active_count == 1
        assert "conv_2" in manager.session_ids

    # ====================================================================
    # 统计信息
    # ====================================================================

    def test_get_stats(self, session_manager: SessionManager) -> None:
        """测试获取统计信息"""
        stats = session_manager.get_stats()
        assert stats["active_sessions"] == 0
        assert stats["max_history"] == 5
        assert stats["ttl_seconds"] == 300
        assert stats["total_messages"] == 0

        # 添加消息后再统计
        session_manager.add_message("conv_1", Message(role="user", content="问题"))
        session_manager.add_message("conv_1", Message(role="assistant", content="回答"))
        session_manager.add_message("conv_2", Message(role="user", content="问题2"))

        stats = session_manager.get_stats()
        assert stats["active_sessions"] == 2
        assert stats["total_messages"] == 3

    # ====================================================================
    # 消息数量溢出保护
    # ====================================================================

    def test_message_overflow_protection(self) -> None:
        """测试消息数量溢出保护（超过 max_history*2 时截断到 max_history 条）"""
        manager = SessionManager(max_history=3, ttl_seconds=300)

        # 添加 10 条消息（超过 max_history * 2 = 6）
        for i in range(10):
            msg = Message(role="user", content=f"消息{i}")
            manager.add_message("conv_1", msg)

        # 内部消息列表应保持在 max_history * 2 以内
        conv = manager._conversations["conv_1"]
        assert len(conv.messages) <= manager.max_history * 2

        # get_history 只返回最近 max_history 条
        history = manager.get_history("conv_1")
        assert len(history) <= manager.max_history
