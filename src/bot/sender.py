"""消息发送模块。

本模块实现了消息发送功能，封装 DingTalkClient 底层 API 调用，
提供符合 domain/ports.py 中 MessageSender 接口的实现。

主要类:
- DingTalkMessageSender: 钉钉消息发送器，实现 MessageSender 接口

典型用法:
    >>> from src.bot.sender import DingTalkMessageSender
    >>> from src.infrastructure.external.dingtalk_client import DingTalkClient
    >>> sender = DingTalkMessageSender(client=DingTalkClient())
    >>> msg_id = await sender.send_text("conv_123", "Hello!")
"""

import json
from typing import Any

from loguru import logger

from src.domain.exceptions import DingTalkAPIError
from src.infrastructure.external.dingtalk_client import DingTalkClient


class DingTalkMessageSender:
    """
    钉钉消息发送器。

    实现 domain/ports.py 中的 MessageSender 接口，封装 DingTalkClient
    提供统一的消息发送能力。

    支持功能:
    - 发送纯文本消息
    - 发送 Markdown 格式消息
    - 更新已发送的消息（撤回后重发）

    Attributes:
        client: 底层钉钉 API 客户端

    Example:
        >>> sender = DingTalkMessageSender(client=dingtalk_client)
        >>> msg_id = await sender.send_markdown("conv_123", "标题", "**内容**")
    """

    def __init__(self, client: DingTalkClient):
        """
        初始化消息发送器。

        Args:
            client: DingTalkClient 实例
        """
        self.client = client
        # 维护 message_id -> (conversation_id, content) 的映射，用于更新消息
        self._message_registry: dict[str, dict[str, Any]] = {}

        logger.info("DingTalkMessageSender 初始化完成")

    async def send_text(self, conversation_id: str, text: str) -> str:
        """
        发送纯文本消息。

        Args:
            conversation_id: 会话 ID
            text: 文本内容

        Returns:
            消息 ID

        Raises:
            DingTalkAPIError: 发送失败
        """
        if not conversation_id:
            raise DingTalkAPIError("会话 ID 不能为空")
        if not text:
            raise DingTalkAPIError("消息内容不能为空")

        try:
            message_id = await self.client.send_text(
                open_conversation_id=conversation_id,
                content=text,
            )

            # 注册消息，以便后续更新
            self._message_registry[message_id] = {
                "conversation_id": conversation_id,
                "msg_type": "text",
                "content": text,
            }

            logger.info(
                "发送文本消息成功 | conversation={} | message_id={}",
                conversation_id[:20],
                message_id[:20] if message_id else "N/A",
            )
            return message_id

        except DingTalkAPIError:
            raise
        except Exception as e:
            logger.error("发送文本消息异常 | error={}", str(e))
            raise DingTalkAPIError(f"发送文本消息失败: {e}") from e

    async def send_markdown(
        self,
        conversation_id: str,
        title: str,
        text: str,
    ) -> str:
        """
        发送 Markdown 格式消息。

        Args:
            conversation_id: 会话 ID
            title: 消息标题
            text: Markdown 内容

        Returns:
            消息 ID

        Raises:
            DingTalkAPIError: 发送失败
        """
        if not conversation_id:
            raise DingTalkAPIError("会话 ID 不能为空")
        if not text:
            raise DingTalkAPIError("消息内容不能为空")

        try:
            message_id = await self.client.send_markdown(
                open_conversation_id=conversation_id,
                title=title,
                text=text,
            )

            # 注册消息
            self._message_registry[message_id] = {
                "conversation_id": conversation_id,
                "msg_type": "markdown",
                "title": title,
                "content": text,
            }

            logger.info(
                "发送 Markdown 消息成功 | conversation={} | title={} | message_id={}",
                conversation_id[:20],
                title,
                message_id[:20] if message_id else "N/A",
            )
            return message_id

        except DingTalkAPIError:
            raise
        except Exception as e:
            logger.error("发送 Markdown 消息异常 | error={}", str(e))
            raise DingTalkAPIError(f"发送 Markdown 消息失败: {e}") from e

    async def update_message(self, message_id: str, new_content: str) -> None:
        """
        更新已发送的消息。

        由于钉钉 API 对消息更新的支持有限，此方法的实现策略是:
        1. 尝试调用 client.update_message() 直接更新
        2. 如果失败，则撤回原消息并发送新消息

        Args:
            message_id: 消息 ID
            new_content: 新的消息内容

        Raises:
            DingTalkAPIError: 更新失败
        """
        if not message_id:
            raise DingTalkAPIError("消息 ID 不能为空")

        # 获取原消息的注册信息
        original = self._message_registry.get(message_id)

        try:
            # 先尝试直接更新
            await self.client.update_message(message_id, new_content)
            logger.info("消息更新成功 | message_id={}", message_id[:20])

            # 更新注册信息
            if original:
                original["content"] = new_content

        except Exception as e:
            logger.warning(
                "直接更新消息失败，尝试撤回重发 | message_id={} | error={}",
                message_id[:20],
                str(e),
            )

            # 回退策略: 撤回旧消息，发送新消息
            if original:
                try:
                    # 撤回旧消息
                    recall_success = await self.client.recall_message(message_id)

                    if recall_success:
                        # 发送新消息
                        conversation_id = original["conversation_id"]
                        msg_type = original.get("msg_type", "markdown")

                        if msg_type == "markdown":
                            title = original.get("title", "回答")
                            await self.send_markdown(conversation_id, title, new_content)
                        else:
                            await self.send_text(conversation_id, new_content)

                        # 清理旧注册信息
                        del self._message_registry[message_id]
                        logger.info("撤回重发成功 | old_message_id={}", message_id[:20])
                    else:
                        logger.error("撤回消息失败 | message_id={}", message_id[:20])
                        raise DingTalkAPIError("撤回消息失败，无法更新")

                except DingTalkAPIError:
                    raise
                except Exception as inner_e:
                    logger.error("撤回重发异常 | error={}", str(inner_e))
                    raise DingTalkAPIError(f"撤回重发失败: {inner_e}") from inner_e
            else:
                logger.warning(
                    "消息未在注册表中，无法撤回重发 | message_id={}",
                    message_id[:20],
                )
                raise DingTalkAPIError("消息未在注册表中，无法更新")

    async def send_thinking_hint(self, conversation_id: str) -> str:
        """
        发送 "正在思考..." 的即时反馈消息。

        用于在机器人处理问题时给用户即时反馈，降低等待焦虑。

        Args:
            conversation_id: 会话 ID

        Returns:
            消息 ID
        """
        thinking_text = "🤔 正在为您查找答案，请稍候..."
        return await self.send_text(conversation_id, thinking_text)

    async def send_error_message(self, conversation_id: str, message: str | None = None) -> str:
        """
        发送错误提示消息。

        Args:
            conversation_id: 会话 ID
            message: 自定义错误消息，默认使用通用提示

        Returns:
            消息 ID
        """
        error_text = message or "⚠️ 抱歉，暂时无法回答您的问题，请稍后再试。"
        return await self.send_text(conversation_id, error_text)

    def cleanup_registry(self) -> int:
        """
        清理消息注册表（定期调用，防止内存泄漏）。

        Returns:
            清理的条目数量
        """
        # 由于消息更新功能在钉钉 API 中有限，注册表可以保留
        # 这里提供一个接口供外部定期清理
        count = len(self._message_registry)
        self._message_registry.clear()
        logger.debug("消息注册表已清理 | count={}", count)
        return count
