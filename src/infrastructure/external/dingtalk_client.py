"""钉钉 API 客户端模块

封装钉钉开放平台 API 调用，支持消息发送、更新等操作。
"""

import asyncio
from typing import Any

import httpx
from loguru import logger

from src.config import settings
from src.domain.exceptions import DingTalkAPIError


class DingTalkClient:
    """
    钉钉 API 客户端

    封装钉钉开放平台 API 调用，提供消息发送、更新等功能。

    Attributes:
        app_key: 应用 AppKey
        app_secret: 应用 AppSecret
        access_token: 访问令牌（自动刷新）
    """

    API_BASE_URL = "https://oapi.dingtalk.com"
    NEW_API_BASE_URL = "https://api.dingtalk.com"

    def __init__(
        self,
        app_key: str | None = None,
        app_secret: str | None = None,
    ):
        """
        初始化钉钉客户端

        Args:
            app_key: 应用 AppKey，默认从配置读取
            app_secret: 应用 AppSecret，默认从配置读取
        """
        self.app_key = app_key or settings.DINGTALK_APP_KEY
        self.app_secret = app_secret or settings.DINGTALK_APP_SECRET
        self._access_token: str | None = None
        self._token_expires_at: float = 0

        logger.info("DingTalkClient 初始化 | app_key={}***", self.app_key[:6] if self.app_key else "")

    async def get_access_token(self) -> str:
        """
        获取访问令牌

        Returns:
            访问令牌字符串

        Raises:
            DingTalkAPIError: 获取令牌失败
        """
        import time

        # 检查令牌是否过期
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.NEW_API_BASE_URL}/v1.0/oauth2/accessToken",
                    json={
                        "appKey": self.app_key,
                        "appSecret": self.app_secret,
                    },
                )
                response.raise_for_status()
                result = response.json()

            self._access_token = result.get("accessToken")
            # 令牌有效期通常为 7200 秒，提前 5 分钟刷新
            self._token_expires_at = time.time() + result.get("expireIn", 7200) - 300

            logger.debug("获取访问令牌成功")
            return self._access_token

        except httpx.HTTPStatusError as e:
            logger.error("获取访问令牌失败 | status={}", e.response.status_code)
            raise DingTalkAPIError(f"获取访问令牌失败: {e.response.status_code}") from e
        except Exception as e:
            logger.error("获取访问令牌异常 | error={}", str(e))
            raise DingTalkAPIError(f"获取访问令牌异常: {e}") from e

    async def send_text(
        self,
        open_conversation_id: str,
        content: str,
    ) -> str:
        """
        发送纯文本消息

        Args:
            open_conversation_id: 会话 ID
            content: 文本内容

        Returns:
            消息 ID

        Raises:
            DingTalkAPIError: 发送失败
        """
        return await self._send_message(
            open_conversation_id=open_conversation_id,
            msg_type="text",
            msg_content={"content": content},
        )

    async def send_markdown(
        self,
        open_conversation_id: str,
        title: str,
        text: str,
    ) -> str:
        """
        发送 Markdown 格式消息

        Args:
            open_conversation_id: 会话 ID
            title: 消息标题
            text: Markdown 内容

        Returns:
            消息 ID

        Raises:
            DingTalkAPIError: 发送失败
        """
        return await self._send_message(
            open_conversation_id=open_conversation_id,
            msg_type="markdown",
            msg_content={"title": title, "text": text},
        )

    async def _send_message(
        self,
        open_conversation_id: str,
        msg_type: str,
        msg_content: dict[str, Any],
    ) -> str:
        """
        发送消息的内部实现

        Args:
            open_conversation_id: 会话 ID
            msg_type: 消息类型 (text/markdown/action_card 等)
            msg_content: 消息内容

        Returns:
            消息 ID

        Raises:
            DingTalkAPIError: 发送失败
        """
        token = await self.get_access_token()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.NEW_API_BASE_URL}/v1.0/robot/groupMessages/send",
                    headers={
                        "x-acs-dingtalk-access-token": token,
                        "Content-Type": "application/json",
                    },
                    json={
                        "msgParam": str(msg_content).replace("'", '"'),
                        "msgKey": self._get_msg_key(msg_type),
                        "openConversationId": open_conversation_id,
                        "robotCode": self.app_key,
                    },
                )
                response.raise_for_status()
                result = response.json()

            message_id = result.get("processQueryKey", "")
            logger.info(
                "发送消息成功 | conversation={} | type={}",
                open_conversation_id[:20], msg_type
            )
            return message_id

        except httpx.HTTPStatusError as e:
            logger.error(
                "发送消息失败 | status={} | error={}",
                e.response.status_code, e.response.text[:200]
            )
            raise DingTalkAPIError(f"发送消息失败: {e.response.status_code}") from e
        except Exception as e:
            logger.error("发送消息异常 | error={}", str(e))
            raise DingTalkAPIError(f"发送消息异常: {e}") from e

    async def update_message(
        self,
        message_id: str,
        new_content: str,
    ) -> None:
        """
        更新已发送的消息

        注意: 钉钉 API 对消息更新的支持有限，此方法可能不适用于所有场景。

        Args:
            message_id: 消息 ID
            new_content: 新的消息内容

        Raises:
            DingTalkAPIError: 更新失败
        """
        # 钉钉 API 更新消息的实现取决于具体的 API 版本
        # 这里提供一个占位实现
        logger.warning(
            "更新消息功能需要特殊权限 | message_id={} | 钉钉 API 限制",
            message_id
        )
        # 实际上可以通过发送新消息或撤回重发来模拟更新

    async def recall_message(
        self,
        message_id: str,
    ) -> bool:
        """
        撤回消息

        Args:
            message_id: 消息 ID

        Returns:
            是否撤回成功
        """
        token = await self.get_access_token()

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.NEW_API_BASE_URL}/v1.0/robot/groupMessages/recall",
                    headers={
                        "x-acs-dingtalk-access-token": token,
                        "Content-Type": "application/json",
                    },
                    json={
                        "processQueryKey": message_id,
                        "robotCode": self.app_key,
                    },
                )
                response.raise_for_status()

            logger.info("撤回消息成功 | message_id={}", message_id)
            return True

        except Exception as e:
            logger.error("撤回消息失败 | message_id={} | error={}", message_id, str(e))
            return False

    def _get_msg_key(self, msg_type: str) -> str:
        """
        获取消息类型的 msgKey

        Args:
            msg_type: 消息类型

        Returns:
            对应的 msgKey
        """
        msg_key_map = {
            "text": "sampleText",
            "markdown": "sampleMarkdown",
            "action_card": "sampleActionCard",
            "link": "sampleLink",
        }
        return msg_key_map.get(msg_type, "sampleText")

    async def health_check(self) -> bool:
        """
        检查钉钉 API 是否可用

        Returns:
            True 表示可用，False 表示不可用
        """
        try:
            await self.get_access_token()
            return True
        except Exception:
            return False


# ============================================================================
# Stream 模式处理器
# ============================================================================

class DingTalkStreamHandler:
    """
    钉钉 Stream 模式消息处理器

    用于接收群内 @机器人 的消息。
    """

    def __init__(self, client: DingTalkClient):
        """
        初始化 Stream 处理器

        Args:
            client: 钉钉客户端
        """
        self.client = client
        self._message_callback = None

    def register_callback(self, callback) -> None:
        """
        注册消息回调函数

        Args:
            callback: 回调函数，签名 async def callback(message_data: dict) -> None
        """
        self._message_callback = callback
        logger.info("消息回调已注册")

    async def start(self) -> None:
        """
        启动 Stream 连接

        注意: 需要安装 dingtalk-stream SDK
        """
        try:
            from dingtalk_stream import AckMessage, ChatbotHandler, ChatbotMessage, Credential, OpenDingTalkStreamClient
        except ImportError:
            logger.error("请先安装 dingtalk-stream: pip install dingtalk-stream")
            raise DingTalkAPIError("dingtalk-stream 未安装")

        class MyHandler(ChatbotHandler):
            """自定义消息处理器"""

            def __init__(self, callback):
                super().__init__()
                self.callback = callback

            async def process(self, callback: ChatbotMessage):
                """处理收到的消息"""
                try:
                    message_data = {
                        "conversation_id": callback.conversation_id,
                        "sender_id": callback.sender_id,
                        "sender_nick": callback.sender_nick,
                        "text": callback.text.content if callback.text else "",
                        "message_id": callback.message_id,
                        "conversation_type": callback.conversation_type,
                    }

                    if self.callback:
                        await self.callback(message_data)

                    return AckMessage.STATUS_OK, "OK"
                except Exception as e:
                    logger.error("处理消息异常 | error={}", str(e))
                    return AckMessage.STATUS_SYSTEM_EXCEPTION, str(e)

        credential = Credential(self.client.app_key, self.client.app_secret)
        handler = MyHandler(self._message_callback)

        stream_client = OpenDingTalkStreamClient(credential)
        stream_client.register_callback_handler(
            ChatbotMessage.TOPIC,
            handler,
        )

        logger.info("启动钉钉 Stream 连接...")
        stream_client.start_forever()
