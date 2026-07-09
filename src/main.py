"""钉钉智能问答机器人 — 应用启动入口。

本模块是整个应用的启动入口，负责:
1. 加载配置
2. 初始化基础设施（SQLite、ChromaDB）
3. 创建服务实例（QAService、KnowledgeService、AnalyticsService）
4. 启动 FastAPI（uvicorn）
5. 启动 DingTalk Stream（异步任务）
6. 注册定时任务（每日汇总）

典型用法:
    >>> uv run uvicorn src.main:create_app --host 0.0.0.0 --port 8000
    >>> # 或
    >>> uv run python -m src.main
"""

import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from loguru import logger

from src.config import settings


# ============================================================================
# 日志配置
# ============================================================================

def setup_logging() -> None:
    """
    配置日志系统。

    使用 loguru 配置控制台和文件输出，设置日志轮转和保留策略。
    """
    # 移除默认 handler
    logger.remove()

    # 控制台输出（带彩色格式）
    logger.add(
        sys.stderr,
        level=settings.LOG_LEVEL,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level:<8}</level> | "
            "<cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # 文件输出（按天轮转）
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.add(
        str(log_dir / "bot_{time:YYYY-MM-DD}.log"),
        rotation="1 day",
        retention="30 days",
        compression="gz",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {module}:{function}:{line} | {message}",
        encoding="utf-8",
    )

    logger.info("日志系统初始化完成 | level={}", settings.LOG_LEVEL)


# ============================================================================
# 基础设施初始化
# ============================================================================

def init_infrastructure() -> dict:
    """
    初始化基础设施组件。

    包括:
    - SQLite 数据库（创建表）
    - ChromaDB 向量库
    - 创建各 Repository 实例

    Returns:
        包含各基础设施实例的字典
    """
    logger.info("初始化基础设施...")

    # ── SQLite 数据库 ──
    from src.infrastructure.database import DatabaseManager

    db_manager = DatabaseManager()
    db_manager.initialize_tables()
    logger.info("SQLite 数据库初始化完成 | path={}", settings.ANALYTICS_DB_PATH)

    # ── Repository 实例 ──
    from src.infrastructure.repositories.knowledge_repo import SQLiteKnowledgeRepository
    from src.infrastructure.repositories.question_repo import SQLiteQuestionRepository

    question_repo = SQLiteQuestionRepository(db_manager=db_manager)
    knowledge_repo = SQLiteKnowledgeRepository(db_manager=db_manager)

    # ── ChromaDB 向量库 ──
    from src.rag.vectorstore import ChromaVectorStore

    vectorstore = ChromaVectorStore()
    logger.info("ChromaDB 初始化完成 | persist_dir={}", settings.CHROMA_PERSIST_DIR)

    return {
        "db_manager": db_manager,
        "question_repo": question_repo,
        "knowledge_repo": knowledge_repo,
        "vectorstore": vectorstore,
    }


# ============================================================================
# 服务实例创建
# ============================================================================

def create_services(infra: dict) -> dict:
    """
    创建业务服务实例。

    包括:
    - LLM 客户端
    - RAG 管道
    - QAService
    - KnowledgeService
    - AnalyticsService

    Args:
        infra: 基础设施实例字典

    Returns:
        包含各服务实例的字典
    """
    logger.info("创建业务服务...")

    # ── LLM 客户端 ──
    from src.llm.client import OllamaClient

    llm_client = OllamaClient()
    logger.info("Ollama 客户端初始化完成 | model={}", settings.OLLAMA_MODEL)

    # ── Embedding 服务 ──
    from src.rag.embedding import EmbeddingService

    embedding_service = EmbeddingService()
    logger.info("Embedding 服务初始化完成")

    # ── RAG 管道 ──
    from src.rag.pipeline import RAGPipeline

    rag_pipeline = RAGPipeline()
    logger.info("RAG 管道初始化完成")

    # ── 问题分类器 ──
    from src.analyzer.classifier import QuestionClassifier

    classifier = QuestionClassifier()
    logger.info("问题分类器初始化完成")

    # ── QAService ──
    from src.services.qa_service import QAService

    qa_service = QAService(
        llm=llm_client,
        rag_pipeline=rag_pipeline,
        question_repo=infra["question_repo"],
        classifier=classifier,  # 注入问题分类器
        session_manager=None,  # 会话管理器待 Bot 模块完成后注入
    )
    logger.info("QAService 初始化完成")

    # ── KnowledgeService ──
    from src.services.knowledge_service import KnowledgeService

    knowledge_service = KnowledgeService(
        vectorstore=infra["vectorstore"],
        llm=llm_client,
        knowledge_repo=infra["knowledge_repo"],
        embedding=embedding_service,
    )
    logger.info("KnowledgeService 初始化完成")

    # ── AnalyticsService ──
    from src.services.analytics_service import AnalyticsService

    analytics_service = AnalyticsService(
        question_repo=infra["question_repo"],
    )
    logger.info("AnalyticsService 初始化完成")

    return {
        "llm_client": llm_client,
        "embedding_service": embedding_service,
        "rag_pipeline": rag_pipeline,
        "qa_service": qa_service,
        "knowledge_service": knowledge_service,
        "analytics_service": analytics_service,
    }


# ============================================================================
# DingTalk Bot 启动
# ============================================================================

async def start_dingtalk_bot(services: dict, infra: dict) -> object | None:
    """
    启动钉钉机器人（如果配置了凭证）。

    在后台异步任务中运行 Stream 连接。

    Args:
        services: 服务实例字典
        infra: 基础设施实例字典

    Returns:
        BotRouter 实例（如果启动成功），否则返回 None
    """
    # 检查是否配置了钉钉凭证
    if not settings.DINGTALK_APP_KEY or not settings.DINGTALK_APP_SECRET:
        logger.warning("钉钉凭证未配置，跳过机器人启动")
        return None

    try:
        from src.bot.handler import BotHandler
        from src.bot.router import BotRouter
        from src.bot.sender import DingTalkMessageSender
        from src.bot.session import SessionManager
        from src.infrastructure.external.dingtalk_client import DingTalkClient

        # ── 创建 Bot 组件 ──
        dingtalk_client = DingTalkClient()
        sender = DingTalkMessageSender(client=dingtalk_client)
        session_manager = SessionManager()

        # 注入 SessionManager 到 QAService
        services["qa_service"].session_manager = session_manager

        # ── 创建 BotHandler ──
        handler = BotHandler(
            qa_service=services["qa_service"],
            sender=sender,
            session_manager=session_manager,
        )

        # ── 创建 BotRouter ──
        bot_router = BotRouter(
            handler=handler,
            client=dingtalk_client,
        )

        # 在后台任务中启动 Stream 连接
        asyncio.create_task(bot_router.start())
        logger.info("钉钉机器人已在后台启动")

        return bot_router

    except ImportError as e:
        logger.warning("钉钉相关依赖未安装，跳过机器人启动: {}", e)
        return None
    except Exception as e:
        logger.error("钉钉机器人启动失败: {}", e)
        return None


# ============================================================================
# 定时任务
# ============================================================================

def setup_scheduler(services: dict) -> object | None:
    """
    设置定时任务（每日汇总）。

    使用 APScheduler 在每日凌晨 2:00 执行日报生成和保存。

    Args:
        services: 服务实例字典

    Returns:
        Scheduler 实例（如果设置成功），否则返回 None
    """
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        scheduler = AsyncIOScheduler()

        # 每日凌晨 2:00 生成并保存日报
        scheduler.add_job(
            services["analytics_service"].generate_daily_report,
            "cron",
            hour=2,
            minute=0,
            kwargs={"days": 1, "push_to_dingtalk": False},
            id="daily_report",
            name="每日日报生成",
            replace_existing=True,
        )

        # 每日凌晨 2:30 保存汇总数据
        scheduler.add_job(
            services["analytics_service"].save_daily_summary,
            "cron",
            hour=2,
            minute=30,
            kwargs={"days": 1},
            id="daily_summary",
            name="每日汇总保存",
            replace_existing=True,
        )

        scheduler.start()
        logger.info("定时任务调度器启动完成")

        return scheduler

    except ImportError:
        logger.warning("APScheduler 未安装，定时任务未启用")
        return None
    except Exception as e:
        logger.error("定时任务设置失败: {}", e)
        return None


# ============================================================================
# 应用生命周期
# ============================================================================

@asynccontextmanager
async def lifespan(app):
    """
    应用生命周期管理。

    启动时:
    - 配置日志
    - 初始化基础设施
    - 创建服务实例
    - 启动钉钉机器人
    - 设置定时任务

    关闭时:
    - 关闭钉钉机器人
    - 关闭数据库连接
    """
    # ── 启动阶段 ──
    logger.info("🚀 启动钉钉智能问答机器人...")
    logger.info("环境: {}", settings.APP_ENV)
    logger.info("日志级别: {}", settings.LOG_LEVEL)

    # 初始化基础设施
    infra = init_infrastructure()

    # 创建服务
    services = create_services(infra)

    # 启动钉钉机器人
    bot_router = await start_dingtalk_bot(services, infra)

    # 设置定时任务
    scheduler = setup_scheduler(services)

    # 将服务和组件注入到 app.state
    app.state.qa_service = services["qa_service"]
    app.state.knowledge_service = services["knowledge_service"]
    app.state.analytics_service = services["analytics_service"]
    app.state.bot_router = bot_router
    app.state.session_manager = getattr(services["qa_service"], "session_manager", None)
    app.state.infra = infra
    app.state.services = services
    app.state.scheduler = scheduler

    logger.info("✅ 应用启动完成")

    yield

    # ── 关闭阶段 ──
    logger.info("🛑 正在关闭应用...")

    # 关闭钉钉机器人
    if bot_router is not None:
        await bot_router.stop()

    # 关闭调度器
    if scheduler is not None:
        scheduler.shutdown(wait=False)

    # 关闭数据库连接
    db_manager = infra.get("db_manager")
    if db_manager is not None:
        db_manager.close()

    logger.info("应用已关闭")


# ============================================================================
# FastAPI 应用工厂
# ============================================================================

def create_app():
    """
    创建 FastAPI 应用实例（工厂函数）。

    用于 uvicorn 启动:
        uv run uvicorn src.main:create_app --factory

    Returns:
        配置完成的 FastAPI 应用实例
    """
    # 配置日志
    setup_logging()

    # 创建 FastAPI 应用
    from src.api.app import create_fastapi_app

    app = create_fastapi_app()

    # 设置生命周期钩子
    app.router.lifespan_context = lifespan

    return app


# ============================================================================
# 直接运行入口
# ============================================================================

def main() -> None:
    """
    主函数，直接运行应用。

    使用 uvicorn 启动应用:
        uv run python -m src.main
    """
    # 配置日志
    setup_logging()

    # 确保数据目录存在
    Path("data").mkdir(exist_ok=True)
    Path("data/logs").mkdir(parents=True, exist_ok=True)

    logger.info("🚀 启动钉钉智能问答机器人...")
    logger.info("环境: {}", settings.APP_ENV)
    logger.info("日志级别: {}", settings.LOG_LEVEL)

    # 启动 uvicorn
    uvicorn.run(
        "src.main:create_app",
        host="0.0.0.0",
        port=8000,
        reload=settings.APP_ENV == "development",
        factory=True,
    )


# 创建应用实例（兼容旧的启动方式）
app = create_app()


if __name__ == "__main__":
    main()
