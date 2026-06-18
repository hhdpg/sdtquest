"""钉钉智能问答机器人 — 应用启动入口"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from src.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("🚀 启动钉钉智能问答机器人...")
    logger.info(f"环境: {settings.APP_ENV}")
    logger.info(f"日志级别: {settings.LOG_LEVEL}")

    yield

    # 关闭时执行
    logger.info("🛑 正在关闭应用...")


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例"""

    app = FastAPI(
        title=settings.APP_NAME,
        description="钉钉智能问答机器人 — 基于本地大模型的 RAG 问答系统",
        version="0.1.0",
        lifespan=lifespan
    )

    # 这里后续会注册路由
    # from src.api.routes import health, chat, knowledge, analytics
    # app.include_router(health.router)
    # app.include_router(chat.router, prefix="/api")
    # app.include_router(knowledge.router, prefix="/api")
    # app.include_router(analytics.router, prefix="/api")

    return app


# 创建应用实例
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.APP_ENV == "development"
    )
