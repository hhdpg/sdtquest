"""Stream 连接管理模块。

本模块负责管理钉钉 Stream 模式 WebSocket 长连接的初始化和生命周期，
包括初始化 dingtalk-stream 客户端、注册消息回调、自动重连机制。

主要类:
- BotRouter: Stream 连接管理器，编排 Stream 连接的建立和维护

典型用法:
    >>> from src.bot.router import BotRouter
    >>> from src.bot.handler import BotHandler
    >>> router = BotRouter(handler=handler)
    >>> await router.start()  # 启动 Stream 连接
"""

import asyncio
from typing import Any

from loguru import logger

from src.bot.handler import BotHandler
from src.domain.exceptions import DingTalkAPIError
from src.infrastructure.external.dingtalk_client import DingTalkClient


class BotRouter:
    """
    Stream 连接管理器。

    负责管理钉钉 Stream 模式的 WebSocket 长连接:
    - 初始化 dingtalk-stream 客户端
    - 注册消息回调到 BotHandler
    - 自动重连机制（断线后指数退避重连）
    - 优雅关闭

    Attributes:
        handler: 消息处理器实例
        client: 钉钉 API 客户端
        max_reconnect_attempts: 最大重连次数（0 表示无限重试）
        base_reconnect_delay: 基础重连延迟（秒）

    Example:
        >>> router = BotRouter(handler=handler, client=client)
        >>> await router.start()
    """

    def __init__(
        self,
        handler: BotHandler,
        client: DingTalkClient | None = None,
        max_reconnect_attempts: int = 0,
        base_reconnect_delay: float = 5.0,
    ):
        """
        初始化 Stream 连接管理器。

        Args:
            handler: BotHandler 实例
            client: DingTalkClient 实例，默认自动创建
            max_reconnect_attempts: 最大重连次数，0 表示无限重试
            base_reconnect_delay: 基础重连延迟（秒），实际延迟会指数增长
        """
        self.handler = handler
        self.client = client or DingTalkClient()
        self.max_reconnect_attempts = max_reconnect_attempts
        self.base_reconnect_delay = base_reconnect_delay

        self._running = False
        self._stream_client: Any = None
        self._reconnect_count = 0

        logger.info(
            "BotRouter 初始化 | max_reconnect={} | base_delay={}s",
            max_reconnect_attempts if max_reconnect_attempts > 0 else "无限",
            base_reconnect_delay,
        )

    async def start(self) -> None:
        """
        启动 Stream 连接。

        初始化 dingtalk-stream 客户端并建立 WebSocket 长连接。
        如果连接断开，自动重连（支持指数退避）。

        Raises:
            DingTalkAPIError: dingtalk-stream 未安装或配置错误
        """
        # 校验配置
        if not self.client.app_key or not self.client.app_secret:
            raise DingTalkAPIError(
                "钉钉应用凭证未配置，请设置 DINGTALK_APP_KEY 和 DINGTALK_APP_SECRET"
            )

        # 导入 dingtalk-stream SDK
        try:
            from dingtalk_stream import (
                AckMessage,
                ChatbotHandler,
                ChatbotMessage,
                Credential,
                DingTalkStreamClient,
            )
        except ImportError:
            logger.error("请先安装 dingtalk-stream: uv pip install dingtalk-stream")
            raise DingTalkAPIError("dingtalk-stream SDK 未安装")

        self._running = True

        # 创建自定义 Stream 消息处理器
        router_ref = self

        class StreamMessageHandler(ChatbotHandler):
            """内部 Stream 消息处理器，转发消息到 BotHandler"""

            def __init__(self):
                super().__init__()

            async def process(self, callback):
                """
                Stream 回调入口。

                注意: SDK 的 route_message 传进来的是 CallbackMessage，
                业务字段（conversationId/senderId/text 等）封装在其 data 中，
                需用 ChatbotMessage.from_dict(callback.data) 解析。

                无论处理成功与否都返回 ACK 避免钉钉重试。
                """
                try:
                    message_data = router_ref._parse_callback(callback)
                    await router_ref.handler.on_message(message_data)
                    return AckMessage.STATUS_OK, "OK"
                except Exception as e:
                    logger.exception(
                        "Stream 消息处理异常 | error={} | msg_id={}",
                        str(e),
                        getattr(getattr(callback, "headers", None), "message_id", "N/A"),
                    )
                    # 即使处理失败也返回 OK，避免钉钉反复重试
                    return AckMessage.STATUS_OK, "OK"

        # 配置 credential 和 handler
        credential = Credential(self.client.app_key, self.client.app_secret)
        stream_handler = StreamMessageHandler()

        # 创建 Stream 客户端
        self._stream_client = DingTalkStreamClient(credential)
        self._stream_client.register_callback_handler(
            ChatbotMessage.TOPIC,
            stream_handler,
        )

        logger.info("🚀 启动钉钉 Stream 连接...")

        # 启动连接（带重连机制）
        await self._start_with_reconnect()

    async def _start_with_reconnect(self) -> None:
        """
        带自动重连的 Stream 连接启动。

        使用指数退避策略: 延迟 = base_delay * 2^reconnect_count，
        最大不超过 300 秒（5 分钟）。
        """
        while self._running:
            try:
                logger.info(
                    "建立 Stream 连接 | attempt={}",
                    self._reconnect_count + 1,
                )

                # start_forever 是阻塞调用，使用 asyncio.to_thread 在线程池中运行，
                # 避免阻塞 asyncio 事件循环导致 FastAPI 等其他协outine 无法执行。
                await asyncio.to_thread(self._stream_client.start_forever)

                # 如果正常退出
                if not self._running:
                    break

                logger.warning("Stream 连接断开")

            except Exception as e:
                if not self._running:
                    break

                logger.error(
                    "Stream 连接异常 | error={} | reconnect_count={}",
                    str(e),
                    self._reconnect_count,
                )

            # 检查是否超过最大重连次数
            self._reconnect_count += 1
            if (
                self.max_reconnect_attempts > 0
                and self._reconnect_count > self.max_reconnect_attempts
            ):
                logger.error(
                    "超过最大重连次数 | max={}",
                    self.max_reconnect_attempts,
                )
                self._running = False
                break

            # 指数退避
            delay = min(
                self.base_reconnect_delay * (2 ** (self._reconnect_count - 1)),
                300.0,
            )
            logger.info(
                "等待重连 | delay={:.1f}s | attempt={}",
                delay,
                self._reconnect_count,
            )
            await asyncio.sleep(delay)

    async def stop(self) -> None:
        """
        优雅关闭 Stream 连接。
        """
        logger.info("正在关闭 Stream 连接...")
        self._running = False

        # 尝试关闭 stream client
        if self._stream_client is not None:
            try:
                # dingtalk-stream 的 client 可能没有显式的 close 方法
                if hasattr(self._stream_client, "disconnect"):
                    self._stream_client.disconnect()
                elif hasattr(self._stream_client, "close"):
                    self._stream_client.close()
            except Exception as e:
                logger.warning("关闭 Stream 客户端异常 | error={}", str(e))

        self._stream_client = None
        logger.info("Stream 连接已关闭")

    @property
    def is_running(self) -> bool:
        """
        检查 Stream 连接是否正在运行。

        Returns:
            True 表示运行中
        """
        return self._running

    def _parse_callback(self, callback: Any) -> dict[str, Any]:
        """
        解析 Stream 回调消息为统一的消息数据字典。

        SDK 传给 process() 的是 CallbackMessage，其业务字段在 .data 中，
        需要先用 ChatbotMessage.from_dict() 转换，才能拿到
        conversationId / senderId / text 等字段。

        Args:
            callback: dingtalk-stream 的 CallbackMessage

        Returns:
            标准化的消息数据字典
        """
        # 将 CallbackMessage 转成 ChatbotMessage（业务消息）
        chat = self._to_chatbot_message(callback)
        if chat is None:
            logger.warning(
                "无法从回调中解析 ChatbotMessage | type={}",
                type(callback).__name__,
            )
            return self._empty_message()

        # 提取文本内容
        text_content = ""
        if getattr(chat, "text", None) is not None:
            text_obj = chat.text
            text_content = (
                text_obj.content if hasattr(text_obj, "content") else str(text_obj)
            )

        message_data = {
            "conversation_id": getattr(chat, "conversation_id", "") or "",
            # sender_id 是钉钉的加密 openId（形如 $:LWCP_v1:$...），仅用于
            # 会话追踪与限流，不能用于 @。@ 必须使用真实 userId。
            "sender_id": getattr(chat, "sender_id", "") or "",
            # sender_staff_id 才是企业内的真实 userId（staffId），用于 @用户。
            # 部分场景可能缺失，此时回退为空串（不 @，避免出现加密串）。
            "sender_staff_id": getattr(chat, "sender_staff_id", "") or "",
            "sender_nick": getattr(chat, "sender_nick", "") or "",
            "text": text_content,
            "message_id": getattr(chat, "message_id", "") or "",
            "conversation_type": getattr(chat, "conversation_type", "") or "",
            "chatbot_user_id": getattr(chat, "chatbot_user_id", "") or "",
            "session_webhook": getattr(chat, "session_webhook", "") or "",
            "session_webhook_expired_time": getattr(
                chat, "session_webhook_expired_time", 0
            ),
            # is_in_at_list 用于判断消息是否 @ 了机器人；
            # 部分钉钉版本可能缺失该字段，此时为 None，由 handler 决定不拦截。
            "is_in_at_list": getattr(chat, "is_in_at_list", None),
        }

        logger.debug(
            "解析 Stream 回调 | conversation={} | sender={} | text_len={} | at={}",
            message_data["conversation_id"][:20] if message_data["conversation_id"] else "N/A",
            message_data["sender_nick"],
            len(message_data["text"]),
            message_data["is_in_at_list"],
        )

        return message_data

    @staticmethod
    def _to_chatbot_message(callback: Any) -> Any:
        """
        将回调对象转换为 ChatbotMessage。

        Stream SDK 的 route_message 传给 handler 的是 CallbackMessage，
        业务数据在 .data 字典中。若传入的已经是 ChatbotMessage（例如单测直接
        构造），则原样返回。

        Args:
            callback: CallbackMessage 或 ChatbotMessage

        Returns:
            ChatbotMessage 实例；无法解析时返回 None
        """
        from dingtalk_stream import ChatbotMessage

        # 已经是 ChatbotMessage（含 conversation_id 属性）
        if hasattr(callback, "conversation_id"):
            return callback

        # CallbackMessage：业务数据在 .data
        data = getattr(callback, "data", None)
        if isinstance(data, dict):
            try:
                return ChatbotMessage.from_dict(data)
            except Exception as e:
                logger.error("ChatbotMessage.from_dict 失败 | error={}", str(e))
                return None

        return None

    @staticmethod
    def _empty_message() -> dict[str, Any]:
        """返回空的消息数据字典（解析失败时兜底）"""
        return {
            "conversation_id": "",
            "sender_id": "",
            "sender_staff_id": "",
            "sender_nick": "",
            "text": "",
            "message_id": "",
            "conversation_type": "",
            "chatbot_user_id": "",
            "session_webhook": "",
            "session_webhook_expired_time": 0,
            "is_in_at_list": None,
        }
