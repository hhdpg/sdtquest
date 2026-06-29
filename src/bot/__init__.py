"""钉钉机器人模块。

本模块实现了钉钉 Stream 消息收发和会话管理功能。

主要类:
- BotRouter: Stream 连接管理器
- BotHandler: 消息处理器
- DingTalkMessageSender: 消息发送器（实现 MessageSender 接口）
- SessionManager: 会话管理器（维护多轮对话上下文）

典型用法:
    >>> from src.bot import BotRouter, BotHandler, DingTalkMessageSender, SessionManager
    >>> session_mgr = SessionManager()
    >>> sender = DingTalkMessageSender(client=dingtalk_client)
    >>> handler = BotHandler(qa_service=qa, sender=sender, session_manager=session_mgr)
    >>> router = BotRouter(handler=handler)
    >>> await router.start()
"""

from src.bot.handler import BotHandler
from src.bot.router import BotRouter
from src.bot.sender import DingTalkMessageSender
from src.bot.session import SessionManager

__all__ = [
    "BotHandler",
    "BotRouter",
    "DingTalkMessageSender",
    "SessionManager",
]
