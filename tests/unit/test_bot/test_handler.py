"""BotHandler 单元测试。

测试消息处理器的所有功能:
- @提及检测和问题提取
- 去重检查
- 限流检查
- 异步调用 QAService
- 异常兜底
- 回答格式化
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.handler import BotHandler
from src.bot.sender import DingTalkMessageSender
from src.bot.session import SessionManager
from src.domain.enums import AnswerStatus, QuestionCategory
from src.domain.models import Answer, Message
from src.services.qa_service import QAService


class TestBotHandler:
    """BotHandler 单元测试"""

    @pytest.fixture
    def mock_qa_service(self) -> MagicMock:
        """创建 Mock QAService"""
        service = MagicMock(spec=QAService)
        service.ask = AsyncMock(return_value=Answer(
            id="answer_1",
            question_id="q_1",
            text="这是回答内容",
            sources=["来源1", "来源2"],
            confidence=0.85,
            category=QuestionCategory.OPERATION_GUIDE,
            status=AnswerStatus.SUCCESS,
        ))
        return service

    @pytest.fixture
    def mock_sender(self) -> MagicMock:
        """创建 Mock Sender"""
        sender = MagicMock(spec=DingTalkMessageSender)
        sender.send_text = AsyncMock(return_value="hint_msg_id")
        sender.send_markdown = AsyncMock(return_value="answer_msg_id")
        sender.send_thinking_hint = AsyncMock(return_value="hint_msg_id")
        sender.send_error_message = AsyncMock(return_value="error_msg_id")
        sender.update_message = AsyncMock()
        return sender

    @pytest.fixture
    def session_manager(self) -> SessionManager:
        """创建 SessionManager"""
        return SessionManager(max_history=5, ttl_seconds=300)

    @pytest.fixture
    def handler(
        self,
        mock_qa_service: MagicMock,
        mock_sender: MagicMock,
        session_manager: SessionManager,
    ) -> BotHandler:
        """创建 BotHandler"""
        return BotHandler(
            qa_service=mock_qa_service,
            sender=mock_sender,
            session_manager=session_manager,
            rate_limit_seconds=5,
        )

    def _make_message_data(
        self,
        text: str = "@机器人 如何创建订单?",
        conversation_id: str = "conv_123",
        sender_id: str = "user_456",
        message_id: str = "msg_789",
    ) -> dict:
        """创建测试消息数据"""
        return {
            "conversation_id": conversation_id,
            "sender_id": sender_id,
            "sender_nick": "测试用户",
            "text": text,
            "message_id": message_id,
            "conversation_type": "2",
        }

    # ====================================================================
    # 问题提取
    # ====================================================================

    def test_extract_question_with_at_mention(self, handler: BotHandler) -> None:
        """测试提取带 @提及的问题"""
        result = handler._extract_question("@机器人 如何创建订单?")
        assert result == "如何创建订单?"

    def test_extract_question_with_multiple_at(self, handler: BotHandler) -> None:
        """测试提取带多个 @的问题"""
        result = handler._extract_question("@张三 @机器人 怎么操作?")
        assert result == "怎么操作?"

    def test_extract_question_without_at(self, handler: BotHandler) -> None:
        """测试提取不带 @的问题"""
        result = handler._extract_question("如何创建订单?")
        assert result == "如何创建订单?"

    def test_extract_question_with_whitespace(self, handler: BotHandler) -> None:
        """测试去除多余空白"""
        result = handler._extract_question("  @机器人   如何  创建  订单?  ")
        assert result == "如何 创建 订单?"

    def test_extract_question_empty(self, handler: BotHandler) -> None:
        """测试空文本"""
        result = handler._extract_question("")
        assert result == ""

    def test_extract_question_only_at(self, handler: BotHandler) -> None:
        """测试只有 @没有实际问题"""
        result = handler._extract_question("@机器人")
        assert result == ""

    def test_extract_question_only_at_with_spaces(self, handler: BotHandler) -> None:
        """测试 @后只有空白"""
        result = handler._extract_question("@机器人   ")
        assert result == ""

    # ====================================================================
    # 去重检查
    # ====================================================================

    @pytest.mark.asyncio
    async def test_is_duplicate_first_time(self, handler: BotHandler) -> None:
        """测试首次消息不重复"""
        result = await handler._is_duplicate("msg_1")
        assert result is False

    @pytest.mark.asyncio
    async def test_is_duplicate_same_id(self, handler: BotHandler) -> None:
        """测试相同消息 ID 被判定为重复"""
        await handler._is_duplicate("msg_1")
        result = await handler._is_duplicate("msg_1")
        assert result is True

    @pytest.mark.asyncio
    async def test_is_duplicate_different_ids(self, handler: BotHandler) -> None:
        """测试不同消息 ID 不重复"""
        await handler._is_duplicate("msg_1")
        result = await handler._is_duplicate("msg_2")
        assert result is False

    # ====================================================================
    # 限流检查
    # ====================================================================

    @pytest.mark.asyncio
    async def test_is_rate_limited_first_time(self, handler: BotHandler) -> None:
        """测试首次提问不限流"""
        result = await handler._is_rate_limited("user_1")
        assert result is False

    @pytest.mark.asyncio
    async def test_is_rate_limited_within_interval(self, handler: BotHandler) -> None:
        """测试间隔内限流"""
        await handler._update_rate_limit("user_1")
        result = await handler._is_rate_limited("user_1")
        assert result is True

    @pytest.mark.asyncio
    async def test_is_rate_limited_after_interval(self, handler: BotHandler) -> None:
        """测试间隔后不限流"""
        handler._user_last_ask_time["user_1"] = time.time() - 10  # 10 秒前
        result = await handler._is_rate_limited("user_1")
        assert result is False

    # ====================================================================
    # 完整消息处理流程
    # ====================================================================

    @pytest.mark.asyncio
    async def test_on_message_success(
        self, handler: BotHandler, mock_qa_service: MagicMock, mock_sender: MagicMock
    ) -> None:
        """测试成功的消息处理流程"""
        message_data = self._make_message_data()
        await handler.on_message(message_data)

        # 验证调用了 QAService
        mock_qa_service.ask.assert_called_once()

        # 验证发送了思考中提示
        mock_sender.send_thinking_hint.assert_called_once()

        # 验证更新了消息
        mock_sender.update_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_message_empty_question(
        self, handler: BotHandler, mock_qa_service: MagicMock
    ) -> None:
        """测试空问题不处理"""
        message_data = self._make_message_data(text="@机器人")
        await handler.on_message(message_data)

        # 不应调用 QAService
        mock_qa_service.ask.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_message_duplicate_ignored(
        self, handler: BotHandler, mock_qa_service: MagicMock
    ) -> None:
        """测试重复消息被忽略"""
        message_data = self._make_message_data()

        # 第一次处理
        await handler.on_message(message_data)
        assert mock_qa_service.ask.call_count == 1

        # 第二次相同消息 ID 应被忽略
        await handler.on_message(message_data)
        assert mock_qa_service.ask.call_count == 1  # 没有增加

    @pytest.mark.asyncio
    async def test_on_message_rate_limited(
        self, handler: BotHandler, mock_qa_service: MagicMock, mock_sender: MagicMock
    ) -> None:
        """测试限流消息"""
        message_data = self._make_message_data()

        # 第一次处理
        await handler.on_message(message_data)
        assert mock_qa_service.ask.call_count == 1

        # 立即再发（应被限流），用不同 message_id
        message_data["message_id"] = "msg_different"
        await handler.on_message(message_data)
        assert mock_qa_service.ask.call_count == 1  # 限流，未调用

        # 验证发送了限流提示
        assert mock_sender.send_text.call_count == 1

    @pytest.mark.asyncio
    async def test_on_message_session_history_updated(
        self, handler: BotHandler, session_manager: SessionManager
    ) -> None:
        """测试会话历史被正确更新"""
        message_data = self._make_message_data(text="@机器人 如何创建订单?")
        await handler.on_message(message_data)

        history = session_manager.get_history("conv_123")
        assert len(history) == 2  # user + assistant
        assert history[0].role == "user"
        assert history[0].content == "如何创建订单?"
        assert history[1].role == "assistant"

    # ====================================================================
    # 异常处理
    # ====================================================================

    @pytest.mark.asyncio
    async def test_on_message_llm_error(
        self, handler: BotHandler, mock_qa_service: MagicMock, mock_sender: MagicMock
    ) -> None:
        """测试 LLM 服务错误"""
        from src.domain.exceptions import LLMServiceError

        mock_qa_service.ask = AsyncMock(side_effect=LLMServiceError("LLM 错误"))
        message_data = self._make_message_data()
        await handler.on_message(message_data)

        # 应发送错误消息
        mock_sender.update_message.assert_called_once()
        call_args = mock_sender.update_message.call_args
        assert "服务繁忙" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_on_message_processing_error(
        self, handler: BotHandler, mock_qa_service: MagicMock, mock_sender: MagicMock
    ) -> None:
        """测试问题处理错误"""
        from src.domain.exceptions import QuestionProcessingError

        mock_qa_service.ask = AsyncMock(side_effect=QuestionProcessingError("处理失败"))
        message_data = self._make_message_data()
        await handler.on_message(message_data)

        # 应发送错误消息
        mock_sender.update_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_message_unknown_error(
        self, handler: BotHandler, mock_qa_service: MagicMock, mock_sender: MagicMock
    ) -> None:
        """测试未知错误"""
        mock_qa_service.ask = AsyncMock(side_effect=RuntimeError("未知错误"))
        message_data = self._make_message_data()
        await handler.on_message(message_data)

        # 应发送通用错误消息
        mock_sender.update_message.assert_called_once()
        call_args = mock_sender.update_message.call_args
        assert "暂时无法回答" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_on_message_hint_send_fails(
        self, handler: BotHandler, mock_qa_service: MagicMock, mock_sender: MagicMock
    ) -> None:
        """测试发送思考提示失败不影响主流程"""
        mock_sender.send_thinking_hint = AsyncMock(side_effect=Exception("发送失败"))
        message_data = self._make_message_data()
        await handler.on_message(message_data)

        # 即使提示发送失败，回答仍应发送
        mock_sender.send_markdown.assert_called_once()

    # ====================================================================
    # 回答格式化
    # ====================================================================

    def test_format_answer_with_sources(self, handler: BotHandler) -> None:
        """测试带引用来源的回答格式化"""
        answer = Answer(
            id="a_1",
            question_id="q_1",
            text="回答内容",
            sources=["来源1", "来源2"],
            confidence=0.85,
            status=AnswerStatus.SUCCESS,
        )

        formatted = handler._format_answer(answer)
        assert "回答内容" in formatted
        assert "来源1" in formatted
        assert "来源2" in formatted
        assert "参考来源" in formatted
        assert "实际系统操作为准" in formatted

    def test_format_answer_without_sources(self, handler: BotHandler) -> None:
        """测试无引用来源的回答格式化"""
        answer = Answer(
            id="a_1",
            question_id="q_1",
            text="回答内容",
            sources=[],
            confidence=0.85,
            status=AnswerStatus.SUCCESS,
        )

        formatted = handler._format_answer(answer)
        assert "回答内容" in formatted
        assert "参考来源" not in formatted
        assert "实际系统操作为准" in formatted

    def test_format_answer_truncates_sources(self, handler: BotHandler) -> None:
        """测试来源过多时截断"""
        answer = Answer(
            id="a_1",
            question_id="q_1",
            text="回答内容",
            sources=[f"来源{i}" for i in range(10)],
            confidence=0.85,
            status=AnswerStatus.SUCCESS,
        )

        formatted = handler._format_answer(answer)
        # 最多显示 5 个来源
        assert "来源0" in formatted
        assert "来源4" in formatted
        assert "来源5" not in formatted

    # ====================================================================
    # 问题长度截断
    # ====================================================================

    @pytest.mark.asyncio
    async def test_on_message_truncates_long_question(
        self, handler: BotHandler, mock_qa_service: MagicMock
    ) -> None:
        """测试过长问题被截断"""
        handler.max_question_length = 10
        message_data = self._make_message_data(text="这是一个非常长的问题" * 5)
        await handler.on_message(message_data)

        # QAService 应被调用，但问题被截断
        mock_qa_service.ask.assert_called_once()
        call_args = mock_qa_service.ask.call_args
        assert len(call_args[1]["question_text"]) <= 10
