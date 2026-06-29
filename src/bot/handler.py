"""消息处理模块。

本模块实现了钉钉消息的处理逻辑，负责接收群内 @机器人 的消息，
提取问题文本，异步调用 QAService 生成回答，并通过消息发送器回复结果。

主要类:
- BotHandler: 消息处理器，编排消息接收→处理→回复的完整流程

典型用法:
    >>> from src.bot.handler import BotHandler
    >>> handler = BotHandler(
    ...     qa_service=qa_service,
    ...     sender=sender,
    ...     session_manager=session_manager,
    ... )
    >>> await handler.on_message(message_data)
"""

import asyncio
import re
import time
from typing import Any

from loguru import logger

from src.bot.sender import DingTalkMessageSender
from src.bot.session import SessionManager
from src.config import settings
from src.domain.exceptions import DingTalkAPIError, LLMServiceError, QuestionProcessingError
from src.domain.models import Answer, Message
from src.services.qa_service import QAService


class BotHandler:
    """
    钉钉消息处理器。

    负责处理群内 @机器人 的消息，编排完整的消息处理流程:
    1. 检测是否为 @机器人 的消息
    2. 去重检查（消息 ID）
    3. 限流检查（同一用户 60 秒内不重复处理）
    4. 即时回复 "正在思考..."
    5. 提取问题文本（去除 @部分）
    6. 异步调用 QAService 生成回答
    7. 发送回答或兜底错误消息
    8. 更新会话历史

    Attributes:
        qa_service: 问答服务实例
        sender: 消息发送器
        session_manager: 会话管理器
        rate_limit_seconds: 同一用户限流间隔（秒）
        max_question_length: 最大问题长度

    Example:
        >>> handler = BotHandler(qa_service=qa, sender=sender, session_manager=sm)
        >>> await handler.on_message({
        ...     "conversation_id": "conv_123",
        ...     "sender_id": "user_456",
        ...     "text": "@机器人 如何创建订单?",
        ...     "message_id": "msg_789",
        ... })
    """

    def __init__(
        self,
        qa_service: QAService,
        sender: DingTalkMessageSender,
        session_manager: SessionManager,
        rate_limit_seconds: int | None = None,
        max_question_length: int = 2000,
    ):
        """
        初始化消息处理器。

        Args:
            qa_service: QAService 实例
            sender: DingTalkMessageSender 实例
            session_manager: SessionManager 实例
            rate_limit_seconds: 同一用户限流间隔（秒），默认从配置读取
            max_question_length: 最大问题长度
        """
        self.qa_service = qa_service
        self.sender = sender
        self.session_manager = session_manager
        self.rate_limit_seconds: int = (
            rate_limit_seconds if rate_limit_seconds is not None
            else settings.RATE_LIMIT_PER_USER
        )
        self.max_question_length = max_question_length

        # 去重: 记录已处理的消息 ID（防止重复处理）
        self._processed_message_ids: set[str] = set()
        self._processed_ids_lock = asyncio.Lock()

        # 限流: 记录每个用户最后一次提问的时间
        self._user_last_ask_time: dict[str, float] = {}
        self._rate_limit_lock = asyncio.Lock()

        logger.info(
            "BotHandler 初始化 | rate_limit={}s | max_length={}",
            self.rate_limit_seconds,
            self.max_question_length,
        )

    async def on_message(self, message_data: dict[str, Any]) -> None:
        """
        处理收到的钉钉消息（Stream 回调入口）。

        完整的处理流程:
        1. 检测 @提及
        2. 去重检查
        3. 限流检查
        4. 提取问题文本
        5. 发送即时反馈
        6. 异步调用 QAService
        7. 发送回答
        8. 更新会话历史

        Args:
            message_data: 消息数据字典，包含以下字段:
                - conversation_id: 会话 ID
                - sender_id: 发送人 ID
                - sender_nick: 发送人昵称
                - text: 消息文本
                - message_id: 消息 ID
                - conversation_type: 会话类型（"1" 单聊, "2" 群聊）
        """
        start_time = time.time()

        # 提取消息字段
        conversation_id = message_data.get("conversation_id", "")
        sender_id = message_data.get("sender_id", "")
        sender_nick = message_data.get("sender_nick", "")
        raw_text = message_data.get("text", "")
        message_id = message_data.get("message_id", "")

        logger.info(
            "收到消息 | sender={}({}) | text={} | msg_id={}",
            sender_nick,
            sender_id[:10] if sender_id else "N/A",
            raw_text[:50] if raw_text else "",
            message_id[:20] if message_id else "N/A",
        )

        # ── 1. 去重检查 ──
        if message_id and await self._is_duplicate(message_id):
            logger.debug("重复消息，跳过 | message_id={}", message_id[:20])
            return

        # ── 2. 限流检查 ──
        if sender_id and await self._is_rate_limited(sender_id):
            logger.info(
                "用户被限流 | sender={} | interval={}s",
                sender_id[:10],
                self.rate_limit_seconds,
            )
            try:
                await self.sender.send_text(
                    conversation_id,
                    f"⏱️ 您的提问过于频繁，请 {self.rate_limit_seconds} 秒后再试。",
                )
            except Exception as e:
                logger.error("发送限流提示失败 | error={}", str(e))
            return

        # ── 3. 提取问题文本 ──
        question_text = self._extract_question(raw_text)
        if not question_text:
            logger.debug("问题文本为空，跳过 | raw_text={}", raw_text[:50])
            return

        # 长度校验
        if len(question_text) > self.max_question_length:
            logger.info("问题过长，截断 | original_len={}", len(question_text))
            question_text = question_text[:self.max_question_length]

        # ── 4. 发送即时反馈 ──
        hint_message_id = ""
        try:
            hint_message_id = await self.sender.send_thinking_hint(conversation_id)
        except Exception as e:
            logger.warning("发送即时反馈失败 | error={}", str(e))

        # ── 5. 记录用户消息到会话 ──
        user_message = Message(role="user", content=question_text)
        self.session_manager.add_message(conversation_id, user_message)

        # 更新限流时间
        if sender_id:
            await self._update_rate_limit(sender_id)

        # ── 6. 调用 QAService 生成回答 ──
        try:
            answer = await self.qa_service.ask(
                question_text=question_text,
                conversation_id=conversation_id,
                sender_id=sender_id,
            )

            # ── 7. 发送回答 ──
            await self._send_answer(conversation_id, hint_message_id, answer)

            # ── 8. 记录助手消息到会话 ──
            assistant_message = Message(role="assistant", content=answer.text)
            self.session_manager.add_message(conversation_id, assistant_message)

            latency = time.time() - start_time
            logger.info(
                "消息处理完成 | sender={} | status={} | confidence={:.2f} | latency={:.1f}s",
                sender_nick,
                answer.status.value,
                answer.confidence,
                latency,
            )

        except QuestionProcessingError as e:
            logger.error("问题处理失败 | error={}", str(e))
            await self._handle_error(conversation_id, hint_message_id, str(e))

        except LLMServiceError as e:
            logger.error("LLM 服务异常 | error={}", str(e))
            await self._handle_error(
                conversation_id,
                hint_message_id,
                "⚠️ 服务繁忙，请稍后再试。",
            )

        except Exception as e:
            logger.exception("消息处理未知异常 | error={}", str(e))
            await self._handle_error(
                conversation_id,
                hint_message_id,
                "⚠️ 暂时无法回答您的问题，请联系管理员。",
            )

    async def _is_duplicate(self, message_id: str) -> bool:
        """
        检查消息是否重复。

        Args:
            message_id: 消息 ID

        Returns:
            True 表示重复，False 表示新消息
        """
        async with self._processed_ids_lock:
            if message_id in self._processed_message_ids:
                return True
            self._processed_message_ids.add(message_id)

            # 防止集合无限增长，保留最近 1000 条
            if len(self._processed_message_ids) > 1000:
                # 清除一半（简单策略）
                to_remove = list(self._processed_message_ids)[:500]
                for mid in to_remove:
                    self._processed_message_ids.discard(mid)

            return False

    async def _is_rate_limited(self, sender_id: str) -> bool:
        """
        检查用户是否被限流。

        Args:
            sender_id: 用户 ID

        Returns:
            True 表示被限流，False 表示可以处理
        """
        async with self._rate_limit_lock:
            last_time = self._user_last_ask_time.get(sender_id, 0)
            elapsed = time.time() - last_time
            return elapsed < self.rate_limit_seconds

    async def _update_rate_limit(self, sender_id: str) -> None:
        """
        更新用户的限流时间戳。

        Args:
            sender_id: 用户 ID
        """
        async with self._rate_limit_lock:
            self._user_last_ask_time[sender_id] = time.time()

            # 防止字典无限增长，清理超过 10 分钟的记录
            now = time.time()
            expired = [
                uid for uid, ts in self._user_last_ask_time.items()
                if now - ts > 600
            ]
            for uid in expired:
                del self._user_last_ask_time[uid]

    def _extract_question(self, raw_text: str) -> str:
        """
        从原始消息文本中提取问题内容。

        去除 @机器人 的部分、多余空白字符。

        Args:
            raw_text: 原始消息文本

        Returns:
            提取后的问题文本，为空时返回空字符串
        """
        if not raw_text:
            return ""

        text = raw_text.strip()

        # 去除 @机器人 的标记（钉钉格式: @xxx）
        # 匹配 @开头的文本，后跟空格或非中文字符
        text = re.sub(r"@\S+\s*", "", text)

        # 去除可能的机器人名称前缀
        # 钉钉消息中 @后面可能带机器人名称
        text = re.sub(r"^[\s​]+", "", text)

        # 去除多余空白
        text = re.sub(r"\s+", " ", text).strip()

        return text

    async def _send_answer(
        self,
        conversation_id: str,
        hint_message_id: str,
        answer: Answer,
    ) -> None:
        """
        发送回答消息。

        如果有 hint_message_id，尝试更新该消息为最终回答；
        否则发送新的 Markdown 消息。

        Args:
            conversation_id: 会话 ID
            hint_message_id: "思考中..." 消息的 ID
            answer: 回答对象
        """
        # 格式化回答内容
        formatted_text = self._format_answer(answer)

        if hint_message_id:
            # 尝试更新 "思考中..." 消息
            try:
                await self.sender.update_message(hint_message_id, formatted_text)
                logger.debug("已更新提示消息为最终回答 | hint_id={}", hint_message_id[:20])
                return
            except Exception as e:
                logger.warning(
                    "更新提示消息失败，发送新消息 | hint_id={} | error={}",
                    hint_message_id[:20],
                    str(e),
                )

        # 发送新的 Markdown 消息
        await self.sender.send_markdown(
            conversation_id=conversation_id,
            title="回答",
            text=formatted_text,
        )

    def _format_answer(self, answer: Answer) -> str:
        """
        格式化回答内容。

        在回答末尾附加引用来源和免责声明。

        Args:
            answer: 回答对象

        Returns:
            格式化后的 Markdown 文本
        """
        parts = [answer.text]

        # 附加引用来源
        if answer.sources:
            source_list = "\n".join(f"- {s}" for s in answer.sources[:5])
            parts.append(f"\n\n---\n**参考来源:**\n{source_list}")

        # 免责声明
        parts.append("\n\n> 💡 如有疑问请以实际系统操作为准。")

        return "".join(parts)

    async def _handle_error(
        self,
        conversation_id: str,
        hint_message_id: str,
        error_text: str,
    ) -> None:
        """
        处理错误情况，向用户发送错误提示。

        Args:
            conversation_id: 会话 ID
            hint_message_id: "思考中..." 消息的 ID
            error_text: 错误提示文本
        """
        if hint_message_id:
            try:
                await self.sender.update_message(hint_message_id, error_text)
                return
            except Exception:
                pass

        try:
            await self.sender.send_error_message(conversation_id, error_text)
        except Exception as e:
            logger.error("发送错误消息也失败 | error={}", str(e))
