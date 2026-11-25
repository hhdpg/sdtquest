"""LLM 供应商管理路由模块。

提供运行时的供应商查看与切换能力：
- GET  /api/llm/status     查看当前 provider、模型与索引条数
- GET  /api/llm/providers  列出支持的 provider
- POST /api/llm/switch     切换到指定 provider

注意：切换只影响当前进程，重启后以 .env 的 LLM_PROVIDER 为准。
若切换到的 provider 索引为空，问答会因检索不到知识而降级，
建议切换前先执行 scripts/build_index.py --provider <name>。
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel, Field

from src.llm.factory import SUPPORTED_PROVIDERS, LLMProviderManager

router = APIRouter()


def get_provider_manager(request: Request) -> LLMProviderManager:
    """从 app.state 获取供应商管理器"""
    manager = getattr(request.app.state, "provider_manager", None)
    if manager is None:
        raise RuntimeError("LLMProviderManager 未初始化")
    return manager


class SwitchRequest(BaseModel):
    """切换请求"""

    provider: str = Field(..., description="目标 provider：local 或 glm")
    force: bool = Field(
        default=False,
        description="目标索引为空时是否强制切换（默认拒绝，避免切换后检索不到知识）",
    )


@router.get("/llm/status", summary="查看当前 LLM 供应商状态")
async def llm_status(
    manager: LLMProviderManager = Depends(get_provider_manager),
) -> dict:
    """返回当前生效的 provider、模型和索引条数。"""
    return manager.describe()


@router.get("/llm/providers", summary="列出支持的 LLM 供应商")
async def llm_providers() -> dict:
    """返回支持的 provider 列表及各自说明。"""
    return {
        "supported": list(SUPPORTED_PROVIDERS),
        "detail": {
            "local": "本地 Ollama（bge-m3 向量，1024 维）",
            "glm": "智谱开放平台（embedding-3 向量，维度可配）",
        },
    }


@router.post("/llm/switch", summary="运行时切换 LLM 供应商")
async def llm_switch(
    req: SwitchRequest,
    manager: LLMProviderManager = Depends(get_provider_manager),
) -> dict:
    """
    切换当前 LLM 供应商。

    切换会同时更换对话模型与其配套的向量索引，无需重启。
    """
    target = req.provider.lower().strip()
    if target not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的 provider: {target}，可选: {', '.join(SUPPORTED_PROVIDERS)}",
        )

    # 前置校验：切过去若没有可用索引，问答必然检索不到知识。
    # 这是实际踩过的坑（切到 GLM 后 79 条卡全丢），默认拒绝并给出修复命令。
    try:
        bundle = manager.get_bundle(target)  # 先探测，不改变当前状态
    except Exception as e:
        logger.error("准备 provider 失败 | target={} | error={}", target, e)
        raise HTTPException(
            status_code=400,
            detail=f"无法初始化 provider {target}: {e}. "
                   f"智谱需先在 .env 配置 GLM_API_KEY",
        ) from e

    try:
        from src.rag.vectorstore import ChromaVectorStore
        count = ChromaVectorStore(collection_name=bundle.collection).collection.count()
    except Exception as e:
        logger.warning("探测索引条数失败 | collection={} | error={}", bundle.collection, e)
        count = -1

    if count == 0 and not req.force:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{target} 的向量索引 {bundle.collection} 为空，切换后检索不到任何知识。"
                f"请先执行 scripts/build_index.py --provider {target} 建库，"
                f"或传 force=true 强制切换。"
            ),
        )

    try:
        old = manager.current
        manager.switch(target)
    except Exception as e:
        logger.error("切换 provider 失败 | target={} | error={}", target, e)
        raise HTTPException(status_code=500, detail=f"切换失败: {e}") from e

    logger.info("provider 切换成功 | {} -> {}", old, target)
    return {
        "switched": True,
        "from": old,
        "to": target,
        "model": bundle.model,
        "collection": bundle.collection,
        "indexed": count,
        "note": "仅当前进程生效，重启后以 .env 的 LLM_PROVIDER 为准",
    }
