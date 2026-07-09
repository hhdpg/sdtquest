"""FastAPI 应用模块。

本模块提供 FastAPI 应用的创建和配置功能。
"""

from src.api.app import create_fastapi_app

__all__ = [
    "create_fastapi_app",
]
