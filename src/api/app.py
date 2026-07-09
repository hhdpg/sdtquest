"""FastAPI 应用模块。

本模块负责创建和配置 FastAPI 应用实例，包括:
- 创建 FastAPI 实例并设置元信息
- 注册所有 API 路由
- 配置全局异常处理
- 配置 CORS 跨域支持
- 设置应用生命周期钩子

典型用法:
    >>> from src.api.app import create_fastapi_app
    >>> app = create_fastapi_app()
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from src.config import settings
from src.domain.exceptions import AppException


def create_fastapi_app() -> FastAPI:
    """
    创建并配置 FastAPI 应用实例。

    配置内容包括:
    - 应用元信息（标题、描述、版本）
    - CORS 跨域中间件
    - 全局异常处理器
    - 所有 API 路由注册

    Returns:
        配置完成的 FastAPI 应用实例

    Example:
        >>> app = create_fastapi_app()
        >>> app.title
        'dingtalk-qa-bot'
    """
    # ── 创建 FastAPI 实例 ──
    app = FastAPI(
        title=settings.APP_NAME,
        description="钉钉智能问答机器人 — 基于本地大模型的 RAG 问答系统",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ── 配置 CORS ──
    _setup_cors(app)

    # ── 注册全局异常处理器 ──
    _setup_exception_handlers(app)

    # ── 注册路由 ──
    _register_routes(app)

    # ── 注册中间件 ──
    _setup_middlewares(app)

    logger.info("FastAPI 应用创建完成 | docs_url=/docs")

    return app


def _setup_cors(app: FastAPI) -> None:
    """
    配置 CORS 跨域中间件。

    开发环境允许所有来源，生产环境应限制为特定域名。

    Args:
        app: FastAPI 应用实例
    """
    if settings.APP_ENV == "development":
        allow_origins = ["*"]
    else:
        # 生产环境可以配置允许的域名
        allow_origins = []

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    logger.debug("CORS 配置完成 | allow_origins={}", allow_origins)


def _setup_exception_handlers(app: FastAPI) -> None:
    """
    注册全局异常处理器。

    捕获所有 AppException 及其子类，返回统一的错误格式。

    Args:
        app: FastAPI 应用实例
    """

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        """处理业务异常"""
        logger.warning(
            "业务异常 | code={} | message={} | path={}",
            exc.code,
            exc.message,
            request.url.path,
        )
        return JSONResponse(
            status_code=400,
            content={
                "error": exc.code,
                "message": exc.message,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """处理未捕获的异常"""
        logger.exception(
            "未处理的异常 | path={} | error={}",
            request.url.path,
            str(exc),
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_ERROR",
                "message": "服务器内部错误，请稍后再试",
            },
        )

    logger.debug("全局异常处理器注册完成")


def _register_routes(app: FastAPI) -> None:
    """
    注册所有 API 路由。

    Args:
        app: FastAPI 应用实例
    """
    from src.api.routes import analytics, chat, health, knowledge

    # 健康检查（无前缀）
    app.include_router(health.router)

    # 业务路由（/api 前缀）
    app.include_router(chat.router, prefix="/api", tags=["chat"])
    app.include_router(knowledge.router, prefix="/api", tags=["knowledge"])
    app.include_router(analytics.router, prefix="/api", tags=["analytics"])

    logger.debug("API 路由注册完成")


def _setup_middlewares(app: FastAPI) -> None:
    """
    注册自定义中间件。

    Args:
        app: FastAPI 应用实例
    """

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """请求日志中间件"""
        import time

        start_time = time.time()

        response = await call_next(request)

        latency = time.time() - start_time

        logger.info(
            "HTTP 请求 | method={} | path={} | status={} | latency={:.3f}s",
            request.method,
            request.url.path,
            response.status_code,
            latency,
        )

        return response
