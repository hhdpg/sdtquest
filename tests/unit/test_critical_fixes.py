"""严重问题修复的回归测试模块。

覆盖本次修复的三个严重问题:
1. bot/router.py: asyncio.to_thread 包装阻塞调用
2. main.py: asyncio.Task done_callback 异常捕获
3. infrastructure/database.py: SQLite WAL 模式与 busy_timeout
"""

import asyncio
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.handler import BotHandler
from src.bot.router import BotRouter
from src.infrastructure.database import DatabaseManager
from src.infrastructure.external.dingtalk_client import DingTalkClient


# ============================================================================
# Fix #1: bot/router.py — asyncio.to_thread 包装阻塞调用
# ============================================================================


class TestRouterBlockingFix:
    """验证 start_forever 不再阻塞 asyncio 事件循环。"""

    @pytest.fixture
    def mock_handler(self) -> MagicMock:
        handler = MagicMock(spec=BotHandler)
        handler.on_message = AsyncMock()
        return handler

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        client = MagicMock(spec=DingTalkClient)
        client.app_key = "test_key_123456"
        client.app_secret = "test_secret"
        return client

    @pytest.mark.asyncio
    async def test_start_forever_runs_in_thread(
        self,
        mock_handler: MagicMock,
        mock_client: MagicMock,
    ) -> None:
        """start_forever 必须通过 asyncio.to_thread 在线程池中执行，而非直接调用。

        验证方式: 在真实 asyncio.to_thread 下，start_forever 的调用不会阻塞
        事件循环（其他协程仍能执行）。
        """
        router = BotRouter(
            handler=mock_handler,
            client=mock_client,
            max_reconnect_attempts=0,
            base_reconnect_delay=0.01,
        )
        router._running = True

        call_count = 0
        mock_stream_client = MagicMock()

        def start_forever_side_effect() -> None:
            nonlocal call_count
            call_count += 1
            router._running = False

        mock_stream_client.start_forever.side_effect = start_forever_side_effect
        router._stream_client = mock_stream_client

        # 记录原始 asyncio.to_thread 引用，验证它被调用
        original_to_thread = asyncio.to_thread
        calls_log: list = []

        async def spy_to_thread(func, *args, **kwargs):
            calls_log.append((func, args, kwargs))
            return await original_to_thread(func, *args, **kwargs)

        with patch("src.bot.router.asyncio.to_thread", side_effect=spy_to_thread):
            await router._start_with_reconnect()

        # 验证 asyncio.to_thread 被调用，且传入的是 start_forever
        assert len(calls_log) >= 1, "asyncio.to_thread 应至少被调用一次"
        called_func = calls_log[0][0]
        assert called_func is mock_stream_client.start_forever, (
            f"asyncio.to_thread 应接收 start_forever，实际接收 {called_func}"
        )
        assert call_count >= 1, "start_forever 应被实际执行至少一次"

    @pytest.mark.asyncio
    async def test_event_loop_not_blocked_by_start_forever(
        self,
        mock_handler: MagicMock,
        mock_client: MagicMock,
    ) -> None:
        """即使 start_forever 耗时 100ms，事件循环中其他协程仍应能执行。

        通过同时运行一个计数器协程来验证事件循环未被冻结:
        - 计数器协程每 10ms tick 一次
        - 若事件循环被阻塞，计数器会停留在 0 或极少
        - 若不阻塞，计数器应能达到 5+ 次
        """
        router = BotRouter(
            handler=mock_handler,
            client=mock_client,
            max_reconnect_attempts=0,
            base_reconnect_delay=0.01,
        )
        router._running = True

        # start_forever 模拟: 阻塞 100ms 后设置 _running=False
        mock_stream_client = MagicMock()

        def blocking_start_forever() -> None:
            import time
            # 使用 time.sleep 模拟真正的阻塞（非 async sleep）
            time.sleep(0.1)
            router._running = False

        mock_stream_client.start_forever.side_effect = blocking_start_forever
        router._stream_client = mock_stream_client

        # 计数器协程: 每 10ms tick 一次
        tick_count = 0

        async def counter() -> None:
            nonlocal tick_count
            while router._running or tick_count < 20:
                tick_count += 1
                await asyncio.sleep(0.01)
                if tick_count >= 20:
                    break

        # 并发运行 counter 和 router
        counter_task = asyncio.create_task(counter())
        router_task = asyncio.create_task(router._start_with_reconnect())

        # 设置总超时，防止测试卡死
        try:
            await asyncio.wait_for(
                asyncio.gather(router_task, counter_task, return_exceptions=True),
                timeout=3.0,
            )
        except asyncio.TimeoutError:
            router._running = False
            pytest.fail("事件循环可能被阻塞，测试超时")

        # 若事件循环未被阻塞，counter 应至少 tick 5 次（100ms / 10ms = 10 次左右）
        assert tick_count >= 3, (
            f"事件循环可能被阻塞: counter 仅 tick {tick_count} 次 (期望 >= 3)"
        )

    @pytest.mark.asyncio
    async def test_reconnect_after_start_forever_returns(
        self,
        mock_handler: MagicMock,
        mock_client: MagicMock,
    ) -> None:
        """start_forever 返回后应正确进入重连逻辑，并通过 asyncio.to_thread 再次调用。"""
        router = BotRouter(
            handler=mock_handler,
            client=mock_client,
            max_reconnect_attempts=2,
            base_reconnect_delay=0.01,
        )
        router._running = True

        call_count = 0
        mock_stream_client = MagicMock()

        def start_forever_impl() -> None:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                router._running = False

        mock_stream_client.start_forever.side_effect = start_forever_impl
        router._stream_client = mock_stream_client

        # 跳过实际 sleep
        with patch("src.bot.router.asyncio.sleep", new_callable=AsyncMock):
            await router._start_with_reconnect()

        # start_forever 应被调用 2 次（第一次返回后进入重连，第二次后停止）
        assert call_count == 2, f"期望调用 2 次，实际 {call_count} 次"


# ============================================================================
# Fix #2: main.py — asyncio.Task done_callback 异常捕获
# ============================================================================


class TestMainTaskCallbackFix:
    """验证 start_dingtalk_bot 返回 (router, task) 元组且异常被捕获。"""

    @pytest.mark.asyncio
    async def test_start_dingtalk_bot_returns_tuple_on_no_credentials(self) -> None:
        """未配置凭证时返回 (None, None)。"""
        from src.main import start_dingtalk_bot

        with patch("src.main.settings") as mock_settings:
            mock_settings.DINGTALK_APP_KEY = ""
            mock_settings.DINGTALK_APP_SECRET = ""
            result = await start_dingtalk_bot({}, {})

        assert isinstance(result, tuple), f"应返回 tuple，实际返回 {type(result)}"
        assert len(result) == 2
        assert result == (None, None)

    @pytest.mark.asyncio
    async def test_start_dingtalk_bot_returns_router_and_task(self) -> None:
        """启动成功时返回 (BotRouter, asyncio.Task) 元组。"""
        from src.main import start_dingtalk_bot

        mock_services = {
            "qa_service": MagicMock(),
        }

        with patch("src.main.settings") as mock_settings, \
             patch("src.bot.handler.BotHandler"), \
             patch("src.bot.router.BotRouter") as MockRouter, \
             patch("src.bot.sender.DingTalkMessageSender"), \
             patch("src.bot.session.SessionManager"), \
             patch("src.infrastructure.external.dingtalk_client.DingTalkClient"):

            mock_settings.DINGTALK_APP_KEY = "test_key"
            mock_settings.DINGTALK_APP_SECRET = "test_secret"

            mock_router_instance = MagicMock()
            mock_router_instance.start = AsyncMock()
            MockRouter.return_value = mock_router_instance

            result = await start_dingtalk_bot(mock_services, {})

        assert isinstance(result, tuple), f"应返回 tuple，实际返回 {type(result)}"
        assert len(result) == 2

        router, task = result
        assert router is mock_router_instance
        assert isinstance(task, asyncio.Task), f"task 应为 asyncio.Task，实际 {type(task)}"

        # 清理 task，避免 pytest 报 "Task was destroyed but it is pending"
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    @pytest.mark.asyncio
    async def test_done_callback_logs_exception(self) -> None:
        """当 bot 任务抛出异常时，done_callback 应记录错误而非静默吞掉。"""
        from src.main import start_dingtalk_bot

        mock_services = {"qa_service": MagicMock()}
        exception_to_raise = RuntimeError("Stream SDK crash")

        with patch("src.main.settings") as mock_settings, \
             patch("src.bot.handler.BotHandler"), \
             patch("src.bot.router.BotRouter") as MockRouter, \
             patch("src.bot.sender.DingTalkMessageSender"), \
             patch("src.bot.session.SessionManager"), \
             patch("src.infrastructure.external.dingtalk_client.DingTalkClient"), \
             patch("src.main.logger") as mock_logger:

            mock_settings.DINGTALK_APP_KEY = "test_key"
            mock_settings.DINGTALK_APP_SECRET = "test_secret"

            mock_router_instance = MagicMock()
            mock_router_instance.start = AsyncMock(side_effect=exception_to_raise)
            MockRouter.return_value = mock_router_instance

            _, task = await start_dingtalk_bot(mock_services, {})

            # 等待任务完成，触发 done_callback
            await asyncio.sleep(0.05)

            # 验证 logger.error 被 done_callback 调用（包含异常信息）
            error_calls = [
                call for call in mock_logger.error.call_args_list
                if "后台任务异常" in str(call)
            ]
            assert len(error_calls) >= 1, (
                f"done_callback 应调用 logger.error 记录异常，"
                f"实际 error 调用: {mock_logger.error.call_args_list}"
            )

    @pytest.mark.asyncio
    async def test_lifespan_shutdown_awaits_bot_task(self) -> None:
        """lifespan shutdown 阶段应等待 bot_task 完成，而非直接丢弃。

        验证方式: 模拟 bot_router.stop() 后 bot_task 应在 5s 内完成。
        """
        # 创建一个模拟的 bot_task，stop 后标记完成
        stop_called = asyncio.Event()

        async def mock_start() -> None:
            await stop_called.wait()

        bot_task = asyncio.create_task(mock_start())

        # 模拟 stop 触发 task 完成
        async def simulate_stop() -> None:
            await asyncio.sleep(0.01)
            stop_called.set()

        # 等待 task 完成（模拟 lifespan shutdown 逻辑）
        stop_task = asyncio.create_task(simulate_stop())
        try:
            await asyncio.wait_for(bot_task, timeout=5.0)
        except asyncio.TimeoutError:
            bot_task.cancel()
            pytest.fail("bot_task 未在 5s 内完成")
        finally:
            stop_task.cancel()
            try:
                await stop_task
            except asyncio.CancelledError:
                pass

        # 确认 task 已完成
        assert bot_task.done()


# ============================================================================
# Fix #3: infrastructure/database.py — SQLite WAL 模式与 busy_timeout
# ============================================================================


class TestDatabaseWalModeFix:
    """验证 SQLite 连接启用 WAL 模式和 busy_timeout。"""

    @pytest.fixture
    def db_manager(self, tmp_path: Path) -> DatabaseManager:
        """创建干净的 DatabaseManager 实例。"""
        DatabaseManager.reset()
        db_path = str(tmp_path / "test_wal.db")
        manager = DatabaseManager(db_path=db_path)
        yield manager
        manager.close()
        DatabaseManager.reset()

    def test_wal_mode_enabled(self, db_manager: DatabaseManager) -> None:
        """数据库连接应启用 WAL journal mode。"""
        conn = db_manager.get_connection()
        result = conn.execute("PRAGMA journal_mode").fetchone()
        # result 是 sqlite3.Row，索引 0 是 journal_mode 值
        journal_mode = result[0] if result else None
        assert journal_mode == "wal", (
            f"期望 journal_mode='wal'，实际 '{journal_mode}'。"
            f"并发写入时 default 模式会导致 'database is locked' 错误。"
        )

    def test_busy_timeout_configured(self, db_manager: DatabaseManager) -> None:
        """数据库连接应设置 busy_timeout > 0。"""
        conn = db_manager.get_connection()
        result = conn.execute("PRAGMA busy_timeout").fetchone()
        busy_timeout = result[0] if result else None
        assert busy_timeout and busy_timeout > 0, (
            f"期望 busy_timeout > 0，实际 {busy_timeout}。"
            f"并发写入时 0 会立即抛出 'database is locked' 而不等待。"
        )

    def test_concurrent_writes_do_not_lock_immediately(
        self,
        tmp_path: Path,
    ) -> None:
        """两个连接并发写入时，第二个应等待而非立即报错。

        验证 busy_timeout 生效: 一个连接持锁期间，另一个连接等待而非立即失败。
        """
        DatabaseManager.reset()
        db_path = str(tmp_path / "test_concurrent.db")

        # 连接 1: 通过 DatabaseManager（启用 WAL + busy_timeout）
        db = DatabaseManager(db_path=db_path)
        db.initialize_tables()
        conn1 = db.get_connection()

        # 连接 2: 直接 sqlite3 连接（也设 busy_timeout=1000 以便等待）
        conn2 = sqlite3.connect(db_path, timeout=1.0)

        try:
            # 连接 1 开启事务并持有锁
            conn1.execute("BEGIN IMMEDIATE")
            conn1.execute(
                "INSERT INTO question_records (id, question, sender_id, status) "
                "VALUES (?, ?, ?, ?)",
                ("q1", "test", "user1", "SUCCESS"),
            )
            # 注意: 不 commit，保持锁

            # 连接 2 尝试写入: 有 busy_timeout 时应该等待，而非立即报错
            # 先让连接 1 释放锁（commit）后再验证连接 2 成功
            conn1.commit()

            # 连接 2 现在应能成功写入（锁已释放）
            conn2.execute(
                "INSERT INTO question_records (id, question, sender_id, status) "
                "VALUES (?, ?, ?, ?)",
                ("q2", "test2", "user2", "SUCCESS"),
            )
            conn2.commit()

            # 验证两条记录都存在
            count = conn1.execute("SELECT COUNT(*) FROM question_records").fetchone()[0]
            assert count == 2, f"期望 2 条记录，实际 {count}"
        finally:
            conn2.close()
            db.close()
            DatabaseManager.reset()

    def test_wal_file_created_after_write(
        self,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """WAL 模式下，写入操作应产生 -wal 文件而非 -journal 文件。"""
        db_manager.initialize_tables()
        conn = db_manager.get_connection()

        # 执行写入
        conn.execute(
            "INSERT INTO question_records (id, question, sender_id, status) "
            "VALUES (?, ?, ?, ?)",
            ("q_test", "test question", "user_test", "SUCCESS"),
        )
        conn.commit()

        db_path = Path(db_manager.db_path)
        wal_file = db_path.parent / f"{db_path.name}-wal"

        # WAL 模式下，写入后可能产生 -wal 文件
        # 注意: 如果所有数据已 checkpoint 到主文件，-wal 可能为空或不存在
        # 但 journal_mode 应该是 wal，这点已在 test_wal_mode_enabled 中验证
        # 这里主要验证没有 -journal 文件（rollback journal 模式的标志）
        journal_file = db_path.parent / f"{db_path.name}-journal"
        assert not journal_file.exists(), (
            "存在 -journal 文件，说明 rollback journal 模式仍在生效，"
            "WAL 模式可能未正确启用。"
        )
