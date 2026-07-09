"""API 路由模块"""

from src.api.routes import analytics, chat, health, knowledge

__all__ = [
    "health",
    "chat",
    "knowledge",
    "analytics",
]
