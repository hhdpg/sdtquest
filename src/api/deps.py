"""FastAPI 依赖注入模块。

本模块提供 FastAPI 路由所需的依赖注入函数，从 app.state 获取服务实例。

主要依赖:
- get_qa_service: 获取问答服务
- get_knowledge_service: 获取知识库管理服务
- get_analytics_service: 获取分析汇总服务
- get_settings: 获取全局配置

典型用法:
    >>> from fastapi import Depends
    >>> from src.api.deps import get_qa_service
    >>> @router.post("/chat")
    ... async def chat(qa_service: QAService = Depends(get_qa_service)):
    ...     return await qa_service.ask(question)
"""

from typing import TYPE_CHECKING

from fastapi import Request
from loguru import logger

from src.config import Settings, settings

if TYPE_CHECKING:
    from src.services import AnalyticsService, KnowledgeService, QAService


def get_settings() -> Settings:
    """
    获取全局配置实例。

    Returns:
        全局 Settings 实例
    """
    return settings


def get_qa_service(request: Request) -> "QAService":
    """
    获取问答服务实例。

    从 FastAPI 的 app.state 中获取 QAService 实例，
    该实例在应用启动时由 main.py 注入。

    Args:
        request: FastAPI 请求对象

    Returns:
        QAService 实例

    Raises:
        RuntimeError: 服务未初始化
    """
    qa_service = getattr(request.app.state, "qa_service", None)
    if qa_service is None:
        logger.error("QAService 未初始化，请检查 main.py 中的启动逻辑")
        raise RuntimeError("QAService 未初始化")
    return qa_service


def get_knowledge_service(request: Request) -> "KnowledgeService":
    """
    获取知识库管理服务实例。

    从 FastAPI 的 app.state 中获取 KnowledgeService 实例。

    Args:
        request: FastAPI 请求对象

    Returns:
        KnowledgeService 实例

    Raises:
        RuntimeError: 服务未初始化
    """
    knowledge_service = getattr(request.app.state, "knowledge_service", None)
    if knowledge_service is None:
        logger.error("KnowledgeService 未初始化，请检查 main.py 中的启动逻辑")
        raise RuntimeError("KnowledgeService 未初始化")
    return knowledge_service


def get_analytics_service(request: Request) -> "AnalyticsService":
    """
    获取分析汇总服务实例。

    从 FastAPI 的 app.state 中获取 AnalyticsService 实例。

    Args:
        request: FastAPI 请求对象

    Returns:
        AnalyticsService 实例

    Raises:
        RuntimeError: 服务未初始化
    """
    analytics_service = getattr(request.app.state, "analytics_service", None)
    if analytics_service is None:
        logger.error("AnalyticsService 未初始化，请检查 main.py 中的启动逻辑")
        raise RuntimeError("AnalyticsService 未初始化")
    return analytics_service


def get_bot_router(request: Request):
    """
    获取 Bot 路由器实例（用于钉钉消息收发）。

    从 FastAPI 的 app.state 中获取 BotRouter 实例。

    Args:
        request: FastAPI 请求对象

    Returns:
        BotRouter 实例，可能为 None（如果未启用钉钉机器人）
    """
    return getattr(request.app.state, "bot_router", None)


def get_session_manager(request: Request):
    """
    获取会话管理器实例。

    Args:
        request: FastAPI 请求对象

    Returns:
        SessionManager 实例
    """
    return getattr(request.app.state, "session_manager", None)
