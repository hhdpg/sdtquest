"""BotRouter 单元测试。

测试 Stream 连接管理器的功能:
- 初始化
- 回调消息解析
- 停止
- 配置校验
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.bot.handler import BotHandler
from src.bot.router import BotRouter
from src.domain.exceptions import DingTalkAPIError
from src.infrastructure.external.dingtalk_client import DingTalkClient


class TestBotRouter:
    """BotRouter 单元测试"""

    @pytest.fixture
    def mock_handler(self) -> MagicMock:
        """创建 Mock BotHandler"""
        handler = MagicMock(spec=BotHandler)
        handler.on_message = AsyncMock()
        return handler

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """创建 Mock DingTalkClient"""
        client = MagicMock(spec=DingTalkClient)
        client.app_key = "test_key_123456"
        client.app_secret = "test_secret"
        return client

    @pytest.fixture
    def router(self, mock_handler: MagicMock, mock_client: MagicMock) -> BotRouter:
        """创建 BotRouter"""
        return BotRouter(
            handler=mock_handler,
            client=mock_client,
            max_reconnect_attempts=3,
            base_reconnect_delay=1.0,
        )

    # ====================================================================
    # 初始化
    # ====================================================================

    def test_init_default_client(self, mock_handler: MagicMock) -> None:
        """测试默认创建 DingTalkClient"""
        router = BotRouter(handler=mock_handler)
        assert router.client is not None
        assert isinstance(router.client, DingTalkClient)

    def test_init_custom_client(self, mock_handler: MagicMock, mock_client: MagicMock) -> None:
        """测试传入自定义 client"""
        router = BotRouter(handler=mock_handler, client=mock_client)
        assert router.client is mock_client

    def test_init_properties(self, router: BotRouter) -> None:
        """测试初始化属性"""
        assert router.max_reconnect_attempts == 3
        assert router.base_reconnect_delay == 1.0
        assert router.is_running is False

    # ====================================================================
    # 配置校验
    # ====================================================================

    @pytest.mark.asyncio
    async def test_start_without_credentials(self, mock_handler: MagicMock) -> None:
        """测试未配置凭证时启动报错"""
        client = MagicMock(spec=DingTalkClient)
        client.app_key = ""
        client.app_secret = ""
        router = BotRouter(handler=mock_handler, client=client)

        with pytest.raises(DingTalkAPIError, match="凭证未配置"):
            await router.start()

    # ====================================================================
    # 消息解析
    # ====================================================================

    def test_parse_callback(self, router: BotRouter) -> None:
        """测试解析 Stream 回调消息"""
        callback = MagicMock()
        callback.conversation_id = "conv_123"
        callback.sender_id = "user_456"
        callback.sender_nick = "测试用户"
        callback.text = MagicMock()
        callback.text.content = "@机器人 如何创建订单?"
        callback.message_id = "msg_789"
        callback.conversation_type = "2"
        callback.chatbot_user_id = "bot_001"
        callback.session_webhook = "https://example.com/webhook"
        callback.session_webhook_expired_time = 1234567890

        result = router._parse_callback(callback)

        assert result["conversation_id"] == "conv_123"
        assert result["sender_id"] == "user_456"
        assert result["sender_nick"] == "测试用户"
        assert result["text"] == "@机器人 如何创建订单?"
        assert result["message_id"] == "msg_789"
        assert result["conversation_type"] == "2"

    def test_parse_callback_with_none_text(self, router: BotRouter) -> None:
        """测试解析空文本回调"""
        callback = MagicMock()
        callback.conversation_id = "conv_123"
        callback.sender_id = "user_456"
        callback.sender_nick = "用户"
        callback.text = None
        callback.message_id = "msg_789"
        callback.conversation_type = "2"

        result = router._parse_callback(callback)
        assert result["text"] == ""

    def test_parse_callback_with_missing_fields(self, router: BotRouter) -> None:
        """测试解析缺少字段的回调"""
        callback = MagicMock(spec=[])  # 没有任何属性
        callback.conversation_id = "conv_123"

        result = router._parse_callback(callback)
        assert result["conversation_id"] == "conv_123"
        assert result["sender_id"] == ""

    def test_parse_callback_extracts_at_flag_and_webhook(self, router: BotRouter) -> None:
        """解析回调应提取 is_in_at_list 与 session_webhook"""
        callback = MagicMock()
        callback.conversation_id = "conv_123"
        callback.sender_id = "user_1"
        callback.sender_nick = "张三"
        callback.text = MagicMock(content="问题")
        callback.message_id = "msg_1"
        callback.conversation_type = "2"
        callback.chatbot_user_id = "bot_1"
        callback.session_webhook = "https://x/sendBySession?s=1"
        callback.session_webhook_expired_time = 123
        callback.is_in_at_list = True

        result = router._parse_callback(callback)
        assert result["is_in_at_list"] is True
        assert result["session_webhook"] == "https://x/sendBySession?s=1"

    def test_parse_callback_missing_at_flag_is_none(self, router: BotRouter) -> None:
        """缺失 is_in_at_list 时应为 None（而非 False 导致误拦截）"""
        callback = MagicMock(spec=["conversation_id", "sender_id"])
        callback.conversation_id = "conv_123"
        callback.sender_id = "user_1"

        result = router._parse_callback(callback)
        assert result["is_in_at_list"] is None

    def test_sdk_client_class_is_importable(self) -> None:
        """dingtalk-stream SDK 的客户端类名必须与代码一致

        回归保护: 代码曾使用 OpenDingTalkStreamClient，而实际安装的 SDK
        导出的是 DingTalkStreamClient，导致机器人启动时 ImportError 静默失败。
        """
        from dingtalk_stream import DingTalkStreamClient  # noqa: F401

        # 确认代码引用的类可被导入
        import src.bot.router  # noqa: F401

    def test_parse_callback_from_real_callback_message(self, router: BotRouter) -> None:
        """必须能从 SDK 真实传递的 CallbackMessage 中解析出业务字段

        回归保护: SDK 的 route_message 传给 handler.process 的是
        CallbackMessage，业务数据封装在 .data 中，而非直接挂在对象上。
        旧实现直接 getattr(callback, "conversation_id") 拿到全空值，
        导致群里发消息后机器人收不到任何有效内容、也不回复。
        """
        import json

        from dingtalk_stream import CallbackMessage

        raw = {
            "specVersion": "1.0",
            "type": "CALLBACK",
            "headers": {
                "topic": "/v1.0/im/bot/messages/get",
                "contentType": "application/json",
                "messageId": "stream_msg_1",
            },
            "data": json.dumps({
                "conversationId": "cid_real_123",
                "senderId": "user_real_456",
                "senderNick": "张三",
                "msgId": "msg_real_789",
                "conversationType": "2",
                "chatbotUserId": "bot_1",
                "isInAtList": True,
                "sessionWebhook": "https://oapi.dingtalk.com/robot/sendBySession?session=abc",
                "sessionWebhookExpiredTime": 9999999999999,
                "text": {"content": " 怎么下单"},
                "msgtype": "text",
                "robotCode": "dingsh",
            }),
        }
        callback = CallbackMessage.from_dict(raw)

        parsed = router._parse_callback(callback)

        assert parsed["conversation_id"] == "cid_real_123"
        assert parsed["sender_id"] == "user_real_456"
        assert parsed["sender_nick"] == "张三"
        assert parsed["text"] == " 怎么下单"
        assert parsed["message_id"] == "msg_real_789"
        assert parsed["is_in_at_list"] is True
        assert parsed["session_webhook"].endswith("session=abc")

    def test_parse_callback_unparseable_returns_empty(self, router: BotRouter) -> None:
        """无法解析的回调应返回空字段而非抛异常"""
        callback = MagicMock(spec=["data"])
        callback.data = None

        parsed = router._parse_callback(callback)

        assert parsed["conversation_id"] == ""
        assert parsed["text"] == ""

    # ====================================================================
    # 停止
    # ====================================================================

    @pytest.mark.asyncio
    async def test_stop(self, router: BotRouter) -> None:
        """测试停止 Stream 连接"""
        router._running = True
        router._stream_client = MagicMock()
        router._stream_client.disconnect = MagicMock()

        await router.stop()

        assert router.is_running is False
        router._stream_client = None

    @pytest.mark.asyncio
    async def test_stop_without_running(self, router: BotRouter) -> None:
        """测试未运行时停止不报错"""
        router._running = False
        router._stream_client = None

        await router.stop()
        assert router.is_running is False

    @pytest.mark.asyncio
    async def test_stop_client_without_disconnect(self, router: BotRouter) -> None:
        """测试客户端没有 disconnect 方法"""
        router._running = True
        router._stream_client = MagicMock(spec=[])  # 没有 disconnect

        await router.stop()
        assert router.is_running is False

    # ====================================================================
    # is_running
    # ====================================================================

    def test_is_running_initially_false(self, router: BotRouter) -> None:
        """测试初始状态 is_running 为 False"""
        assert router.is_running is False

    def test_is_running_after_set(self, router: BotRouter) -> None:
        """测试设置 _running 后 is_running 变化"""
        router._running = True
        assert router.is_running is True
