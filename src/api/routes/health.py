"""健康检查路由模块。

提供系统健康检查接口，用于监控和负载均衡器探测服务状态。
"""

from fastapi import APIRouter
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
async def detailed_health_check() -> dict:
    """
    详细健康检查接口。

    返回更详细的系统状态信息，包括各组件状态。

    Returns:
        详细状态信息字典
    """
    import os
    from pathlib import Path

    # 检查各组件状态
    checks = {
        "app": _check_app(),
        "database": _check_database(),
        "chromadb": _check_chromadb(),
        "ollama": await _check_ollama(),
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
        if db_path.exists():
            return {"status": "ok", "path": str(db_path)}
        return {"status": "ok", "path": str(db_path), "note": "数据库文件不存在，将在首次写入时创建"}
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


async def _check_ollama() -> dict[str, str]:
    """检查 Ollama 服务状态"""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                return {"status": "ok", "url": settings.OLLAMA_BASE_URL}
            return {"status": "error", "url": settings.OLLAMA_BASE_URL, "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"status": "error", "url": settings.OLLAMA_BASE_URL, "error": str(e)}
