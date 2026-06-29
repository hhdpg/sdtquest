"""DingTalkMessageSender 单元测试。

测试消息发送器的所有功能:
- 发送纯文本消息
- 发送 Markdown 消息
- 更新消息
- 即时反馈和错误消息
- 异常处理
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.bot.sender import DingTalkMessageSender
from src.domain.exceptions import DingTalkAPIError
from src.infrastructure.external.dingtalk_client import DingTalkClient


class TestDingTalkMessageSender:
    """DingTalkMessageSender 单元测试"""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """创建 Mock DingTalkClient"""
        client = MagicMock(spec=DingTalkClient)
        client.send_text = AsyncMock(return_value="msg_id_123")
        client.send_markdown = AsyncMock(return_value="msg_id_456")
        client.update_message = AsyncMock()
        client.recall_message = AsyncMock(return_value=True)
        return client

    @pytest.fixture
    def sender(self, mock_client: MagicMock) -> DingTalkMessageSender:
        """创建 DingTalkMessageSender"""
        return DingTalkMessageSender(client=mock_client)

    # ====================================================================
    # send_text
    # ====================================================================

    @pytest.mark.asyncio
    async def test_send_text_success(self, sender: DingTalkMessageSender, mock_client: MagicMock) -> None:
        """测试成功发送文本消息"""
        msg_id = await sender.send_text("conv_123", "Hello!")

        mock_client.send_text.assert_called_once_with(
            open_conversation_id="conv_123",
            content="Hello!",
        )
        assert msg_id == "msg_id_123"

    @pytest.mark.asyncio
    async def test_send_text_empty_conversation_id(self, sender: DingTalkMessageSender) -> None:
        """测试空会话 ID 报错"""
        with pytest.raises(DingTalkAPIError, match="会话 ID 不能为空"):
            await sender.send_text("", "Hello!")

    @pytest.mark.asyncio
    async def test_send_text_empty_content(self, sender: DingTalkMessageSender) -> None:
        """测试空消息内容报错"""
        with pytest.raises(DingTalkAPIError, match="消息内容不能为空"):
            await sender.send_text("conv_123", "")

    @pytest.mark.asyncio
    async def test_send_text_api_error(self, mock_client: MagicMock) -> None:
        """测试 API 错误传播"""
        mock_client.send_text = AsyncMock(side_effect=DingTalkAPIError("API 错误"))
        sender = DingTalkMessageSender(client=mock_client)

        with pytest.raises(DingTalkAPIError, match="API 错误"):
            await sender.send_text("conv_123", "Hello!")

    @pytest.mark.asyncio
    async def test_send_text_unexpected_error(self, mock_client: MagicMock) -> None:
        """测试非预期异常被包装为 DingTalkAPIError"""
        mock_client.send_text = AsyncMock(side_effect=RuntimeError("未知错误"))
        sender = DingTalkMessageSender(client=mock_client)

        with pytest.raises(DingTalkAPIError, match="发送文本消息失败"):
            await sender.send_text("conv_123", "Hello!")

    # ====================================================================
    # send_markdown
    # ====================================================================

    @pytest.mark.asyncio
    async def test_send_markdown_success(self, sender: DingTalkMessageSender, mock_client: MagicMock) -> None:
        """测试成功发送 Markdown 消息"""
        msg_id = await sender.send_markdown("conv_123", "标题", "**内容**")

        mock_client.send_markdown.assert_called_once_with(
            open_conversation_id="conv_123",
            title="标题",
            text="**内容**",
        )
        assert msg_id == "msg_id_456"

    @pytest.mark.asyncio
    async def test_send_markdown_empty_content(self, sender: DingTalkMessageSender) -> None:
        """测试空 Markdown 内容报错"""
        with pytest.raises(DingTalkAPIError, match="消息内容不能为空"):
            await sender.send_markdown("conv_123", "标题", "")

    @pytest.mark.asyncio
    async def test_send_markdown_empty_conversation_id(self, sender: DingTalkMessageSender) -> None:
        """测试空会话 ID 报错"""
        with pytest.raises(DingTalkAPIError, match="会话 ID 不能为空"):
            await sender.send_markdown("", "标题", "内容")

    # ====================================================================
    # update_message
    # ====================================================================

    @pytest.mark.asyncio
    async def test_update_message_success(self, sender: DingTalkMessageSender, mock_client: MagicMock) -> None:
        """测试成功更新消息"""
        # 先发送消息注册到 registry
        await sender.send_text("conv_123", "原始内容")

        # 更新消息
        await sender.update_message("msg_id_123", "新内容")

        mock_client.update_message.assert_called_once_with("msg_id_123", "新内容")

    @pytest.mark.asyncio
    async def test_update_message_empty_id(self, sender: DingTalkMessageSender) -> None:
        """测试空消息 ID 报错"""
        with pytest.raises(DingTalkAPIError, match="消息 ID 不能为空"):
            await sender.update_message("", "新内容")

    @pytest.mark.asyncio
    async def test_update_message_fallback_to_recall_and_resend(
        self, sender: DingTalkMessageSender, mock_client: MagicMock
    ) -> None:
        """测试更新失败时回退到撤回重发"""
        # 先发送 markdown 消息
        await sender.send_markdown("conv_123", "标题", "原始内容")

        # update_message 失败
        mock_client.update_message = AsyncMock(side_effect=Exception("更新失败"))

        # 更新应该回退到撤回重发
        await sender.update_message("msg_id_456", "新内容")

        mock_client.recall_message.assert_called_once_with("msg_id_456")
        # 撤回后应重发 markdown
        assert mock_client.send_markdown.call_count == 2  # 原始 + 重发

    @pytest.mark.asyncio
    async def test_update_message_not_registered(
        self, sender: DingTalkMessageSender, mock_client: MagicMock
    ) -> None:
        """测试更新未注册的消息"""
        mock_client.update_message = AsyncMock(side_effect=Exception("更新失败"))

        with pytest.raises(DingTalkAPIError, match="消息未在注册表中"):
            await sender.update_message("unknown_msg_id", "新内容")

    # ====================================================================
    # send_thinking_hint
    # ====================================================================

    @pytest.mark.asyncio
    async def test_send_thinking_hint(self, sender: DingTalkMessageSender, mock_client: MagicMock) -> None:
        """测试发送思考中提示"""
        msg_id = await sender.send_thinking_hint("conv_123")

        mock_client.send_text.assert_called_once()
        call_args = mock_client.send_text.call_args
        assert call_args[1]["open_conversation_id"] == "conv_123"
        assert "正在为您查找答案" in call_args[1]["content"]
        assert msg_id == "msg_id_123"

    # ====================================================================
    # send_error_message
    # ====================================================================

    @pytest.mark.asyncio
    async def test_send_error_message_default(self, sender: DingTalkMessageSender, mock_client: MagicMock) -> None:
        """测试发送默认错误消息"""
        msg_id = await sender.send_error_message("conv_123")

        mock_client.send_text.assert_called_once()
        call_args = mock_client.send_text.call_args
        assert "暂时无法回答" in call_args[1]["content"]

    @pytest.mark.asyncio
    async def test_send_error_message_custom(self, sender: DingTalkMessageSender, mock_client: MagicMock) -> None:
        """测试发送自定义错误消息"""
        msg_id = await sender.send_error_message("conv_123", "自定义错误")

        mock_client.send_text.assert_called_once()
        call_args = mock_client.send_text.call_args
        assert call_args[1]["content"] == "自定义错误"

    # ====================================================================
    # cleanup_registry
    # ====================================================================

    def test_cleanup_registry(self, sender: DingTalkMessageSender) -> None:
        """测试清理消息注册表"""
        # 先注册一些消息
        sender._message_registry["msg_1"] = {"content": "test1"}
        sender._message_registry["msg_2"] = {"content": "test2"}

        count = sender.cleanup_registry()
        assert count == 2
        assert len(sender._message_registry) == 0

    # ====================================================================
    # MessageSender Protocol 兼容
    # ====================================================================

    def test_implements_message_sender_protocol(self) -> None:
        """测试实现 MessageSender 协议"""
        from src.domain.ports import MessageSender

        mock_client = MagicMock(spec=DingTalkClient)
        sender = DingTalkMessageSender(client=mock_client)

        # 检查方法存在
        assert hasattr(sender, "send_text")
        assert hasattr(sender, "send_markdown")
        assert hasattr(sender, "update_message")
