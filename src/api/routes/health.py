"""健康检查路由模块。

提供系统健康检查接口，用于监控和负载均衡器探测服务状态。
"""

from pathlib import Path

from fastapi import APIRouter, Request
from loguru import logger

from src.config import settings

router = APIRouter(tags=["health"])


@router.get("/health", summary="健康检查")
async def health_check() -> dict[str, str]:
    """
    健康检查接口。

    返回系统状态，用于负载均衡器或监控系统探测服务是否存活。

    Returns:
        包含状态信息的字典:
        - status: 服务状态（"ok" 表示正常）
        - environment: 运行环境
        - version: 服务版本
    """
    logger.debug("健康检查请求")
    return {
        "status": "ok",
        "environment": settings.APP_ENV,
        "version": "0.1.0",
    }


@router.get("/health/detailed", summary="详细健康检查")
async def detailed_health_check(request: Request) -> dict:
    """
    详细健康检查接口。

    返回更详细的系统状态信息，包括各组件状态。

    Returns:
        详细状态信息字典
    """
    # 以运行时当前 provider 为准（可能已被 /api/llm/switch 切换），
    # 避免把未启用的服务（如本地 Ollama）判为故障。
    manager = getattr(request.app.state, "provider_manager", None)
    provider = manager.current if manager is not None else settings.LLM_PROVIDER

    checks = {
        "app": _check_app(),
        "database": _check_database(),
        "chromadb": _check_chromadb(),
        "llm": await _check_llm(provider),
    }

    # 总体状态：所有组件都正常时为 "ok"，否则为 "degraded"
    all_ok = all(c["status"] == "ok" for c in checks.values())

    return {
        "status": "ok" if all_ok else "degraded",
        "environment": settings.APP_ENV,
        "version": "0.1.0",
        "components": checks,
    }


def _check_app() -> dict[str, str]:
    """检查应用本身状态"""
    return {"status": "ok"}


def _check_database() -> dict[str, str]:
    """检查 SQLite 数据库状态"""
    try:
        from src.infrastructure.database import get_db_manager

        db_manager = get_db_manager()
        db_path = Path(settings.ANALYTICS_DB_PATH)
        if not db_path.exists():
            return {"status": "ok", "path": str(db_path), "note": "数据库文件不存在，将在首次写入时创建"}

        # 真正探活：执行一次轻量查询，确认连接可用
        db_manager.get_connection().execute("SELECT 1").fetchone()
        return {"status": "ok", "path": str(db_path)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _check_chromadb() -> dict[str, str]:
    """检查 ChromaDB 状态"""
    try:
        chroma_path = Path(settings.CHROMA_PERSIST_DIR)
        if chroma_path.exists():
            return {"status": "ok", "path": str(chroma_path)}
        return {"status": "ok", "path": str(chroma_path), "note": "ChromaDB 目录不存在，将在首次使用时创建"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _check_llm(provider: str) -> dict[str, str]:
    """
    按当前 provider 检查 LLM 服务状态。

    - local: 探测本地 Ollama 的 /api/tags
    - glm: 校验 API Key 是否已配置（不发起计费请求）

    Args:
        provider: 当前使用的 provider

    Returns:
        组件状态字典
    """
    if provider == "glm":
        if not settings.GLM_API_KEY:
            return {"status": "error", "provider": "glm", "error": "GLM_API_KEY 未配置"}
        return {"status": "ok", "provider": "glm", "model": settings.GLM_MODEL}

    try:
        from src.shared.http import create_direct_client

        async with create_direct_client(timeout=5.0) as client:
            response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                return {"status": "ok", "provider": "local", "url": settings.OLLAMA_BASE_URL}
            return {
                "status": "error", "provider": "local",
                "url": settings.OLLAMA_BASE_URL, "error": f"HTTP {response.status_code}",
            }
    except Exception as e:
        return {"status": "error", "provider": "local", "error": str(e)}
