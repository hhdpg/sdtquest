"""知识库管理 API 路由模块。

提供知识库构建、统计、查询等接口。

接口:
- POST /api/knowledge/build: 触发知识库构建
- GET /api/knowledge/stats: 获取知识库统计
- GET /api/knowledge/items: 查询知识条目列表
- GET /api/knowledge/pages: 获取页面列表
- DELETE /api/knowledge/items/{item_id}: 删除知识条目
- POST /api/knowledge/import: 导入文档
"""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from src.api.deps import get_knowledge_service
from src.domain.enums import KnowledgeType
from src.services import KnowledgeService

router = APIRouter()


# ============================================================================
# 请求/响应模型
# ============================================================================

class KnowledgeBuildRequest(BaseModel):
    """
    知识库构建请求模型。

    Attributes:
        project_root: 前端项目路径
        enrich: 是否使用 LLM 丰富描述（默认 True）

    Example:
        >>> request = KnowledgeBuildRequest(project_root="/path/to/frontend")
    """
    project_root: str = Field(
        ...,
        description="前端项目路径",
        examples=["/path/to/frontend"],
    )
    enrich: bool = Field(
        default=True,
        description="是否使用 LLM 丰富描述",
    )


class KnowledgeBuildResponse(BaseModel):
    """
    知识库构建响应模型。

    Attributes:
        status: 构建状态
        total: 总条目数
        enriched: 丰富的条目数
        vectorized: 向量化的条目数
        stored: 入库的条目数
        message: 状态消息

    Example:
        >>> response = KnowledgeBuildResponse(
        ...     status="success",
        ...     total=100,
        ...     enriched=100,
        ...     vectorized=100,
        ...     stored=100,
        ... )
    """
    status: str = Field(..., description="构建状态")
    total: int = Field(default=0, description="总条目数")
    enriched: int = Field(default=0, description="丰富的条目数")
    vectorized: int = Field(default=0, description="向量化的条目数")
    stored: int = Field(default=0, description="入库的条目数")
    message: str = Field(default="", description="状态消息")


class KnowledgeStatsResponse(BaseModel):
    """
    知识库统计响应模型。

    Attributes:
        total: 总条目数
        vector_count: 向量库文档数
        db_total: 数据库条目数
        by_type: 按类型统计
        page_count: 页面数量

    Example:
        >>> stats = KnowledgeStatsResponse(total=100, vector_count=100)
    """
    total: int = Field(..., description="总条目数")
    vector_count: int = Field(default=0, description="向量库文档数")
    db_total: int = Field(default=0, description="数据库条目数")
    by_type: dict[str, int] = Field(default_factory=dict, description="按类型统计")
    page_count: int = Field(default=0, description="页面数量")


class KnowledgeImportRequest(BaseModel):
    """
    文档导入请求模型。

    Attributes:
        file_path: 文件路径
        dir_path: 目录路径（与 file_path 二选一）
        enrich: 是否使用 LLM 丰富描述
        recursive: 是否递归扫描子目录

    Example:
        >>> request = KnowledgeImportRequest(file_path="/path/to/doc.md")
    """
    file_path: str | None = Field(
        default=None,
        description="文件路径",
    )
    dir_path: str | None = Field(
        default=None,
        description="目录路径",
    )
    enrich: bool = Field(
        default=False,
        description="是否使用 LLM 丰富描述",
    )
    recursive: bool = Field(
        default=True,
        description="是否递归扫描子目录",
    )


class KnowledgeItemResponse(BaseModel):
    """
    知识条目响应模型。
    """
    id: str = Field(..., description="知识条目 ID")
    type: str = Field(..., description="知识类型")
    title: str = Field(..., description="标题")
    content: str = Field(..., description="内容")
    page_name: str | None = Field(default=None, description="所属页面")
    page_path: str | None = Field(default=None, description="页面路径")
    tags: list[str] = Field(default_factory=list, description="标签列表")


# ============================================================================
# API 路由
# ============================================================================

@router.post(
    "/knowledge/build",
    response_model=KnowledgeBuildResponse,
    summary="触发知识库构建",
    description="从前端代码解析并构建知识库",
)
async def build_knowledge(
    request: KnowledgeBuildRequest,
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
) -> KnowledgeBuildResponse:
    """
    触发知识库构建。

    从指定的前端项目路径解析代码，构建知识库。

    Args:
        request: 构建请求
        knowledge_service: 知识库管理服务

    Returns:
        构建结果
    """
    logger.info(
        "收到知识库构建请求 | project_root={} | enrich={}",
        request.project_root,
        request.enrich,
    )

    # 验证路径
    project_path = Path(request.project_root)
    if not project_path.exists() or not project_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"项目路径不存在或不是目录: {request.project_root}",
        )

    try:
        # 调用 Parser 解析代码
        from src.parser import VueProjectParser
        from src.parser.models import ParserConfig

        config = ParserConfig(
            project_root=project_path,
        )
        parser = VueProjectParser(config=config)
        parse_result = parser.parse()

        # 转换为 KnowledgeItem
        from src.parser.builder import KnowledgeBuilder

        builder = KnowledgeBuilder()
        knowledge_items = builder.build(parse_result)

        # 构建知识库
        stats = await knowledge_service.build_from_code(
            knowledge_items=knowledge_items,
            enrich=request.enrich,
        )

        logger.info(
            "知识库构建完成 | total={} | enriched={} | vectorized={} | stored={}",
            stats["total"],
            stats["enriched"],
            stats["vectorized"],
            stats["stored"],
        )

        return KnowledgeBuildResponse(
            status="success",
            total=stats["total"],
            enriched=stats["enriched"],
            vectorized=stats["vectorized"],
            stored=stats["stored"],
            message="知识库构建成功",
        )

    except Exception as e:
        logger.error("知识库构建失败 | error={}", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"知识库构建失败: {str(e)}",
        )


@router.get(
    "/knowledge/stats",
    response_model=KnowledgeStatsResponse,
    summary="获取知识库统计",
    description="获取知识库的统计信息",
)
async def get_knowledge_stats(
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
) -> KnowledgeStatsResponse:
    """
    获取知识库统计信息。

    Args:
        knowledge_service: 知识库管理服务

    Returns:
        统计信息
    """
    logger.info("收到知识库统计请求")

    stats = await knowledge_service.get_stats()

    return KnowledgeStatsResponse(
        total=stats.get("total", 0),
        vector_count=stats.get("vector_count", 0),
        db_total=stats.get("db_total", 0),
        by_type=stats.get("by_type", {}),
        page_count=stats.get("page_count", 0),
    )


@router.get(
    "/knowledge/items",
    response_model=list[KnowledgeItemResponse],
    summary="查询知识条目",
    description="查询知识条目列表，支持按类型和页面过滤",
)
async def get_knowledge_items(
    item_type: str | None = None,
    page_name: str | None = None,
    limit: int = 100,
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
) -> list[KnowledgeItemResponse]:
    """
    查询知识条目列表。

    Args:
        item_type: 知识类型过滤
        page_name: 页面名称过滤
        limit: 最大返回数量
        knowledge_service: 知识库管理服务

    Returns:
        知识条目列表
    """
    logger.info(
        "查询知识条目 | type={} | page={} | limit={}",
        item_type,
        page_name,
        limit,
    )

    # 解析类型
    type_enum = None
    if item_type:
        try:
            type_enum = KnowledgeType(item_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"无效的知识类型: {item_type}",
            )

    items = await knowledge_service.get_knowledge_items(
        item_type=type_enum,
        page_name=page_name,
        limit=limit,
    )

    return [
        KnowledgeItemResponse(
            id=item.id,
            type=item.type.value,
            title=item.title,
            content=item.content,
            page_name=item.page_name,
            page_path=item.page_path,
            tags=item.tags,
        )
        for item in items
    ]


@router.get(
    "/knowledge/pages",
    response_model=list[str],
    summary="获取页面列表",
    description="获取知识库中的所有页面名称",
)
async def get_knowledge_pages(
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
) -> list[str]:
    """
    获取知识库中的所有页面名称。

    Args:
        knowledge_service: 知识库管理服务

    Returns:
        页面名称列表
    """
    logger.info("获取页面列表")

    return await knowledge_service.get_pages()


@router.delete(
    "/knowledge/items/{item_id}",
    summary="删除知识条目",
    description="删除指定的知识条目",
)
async def delete_knowledge_item(
    item_id: str,
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
) -> dict[str, Any]:
    """
    删除知识条目。

    Args:
        item_id: 知识条目 ID
        knowledge_service: 知识库管理服务

    Returns:
        删除结果
    """
    logger.info("删除知识条目 | id={}", item_id)

    success = await knowledge_service.delete_knowledge(item_id)

    if success:
        return {"status": "success", "message": "删除成功"}
    else:
        raise HTTPException(
            status_code=400,
            detail=f"删除失败: {item_id}",
        )


@router.post(
    "/knowledge/import",
    summary="导入文档",
    description="从文件或目录导入文档到知识库",
)
async def import_documents(
    request: KnowledgeImportRequest,
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
) -> dict[str, Any]:
    """
    导入文档到知识库。

    支持从单个文件或整个目录导入 Markdown 和纯文本文件。

    Args:
        request: 导入请求
        knowledge_service: 知识库管理服务

    Returns:
        导入结果
    """
    logger.info(
        "收到文档导入请求 | file={} | dir={} | enrich={} | recursive={}",
        request.file_path,
        request.dir_path,
        request.enrich,
        request.recursive,
    )

    if not request.file_path and not request.dir_path:
        raise HTTPException(
            status_code=400,
            detail="必须提供 file_path 或 dir_path",
        )

    try:
        items = []

        if request.file_path:
            # 导入单个文件
            file_items = await knowledge_service.import_from_file(
                file_path=request.file_path,
                enrich=request.enrich,
            )
            items.extend(file_items)

        if request.dir_path:
            # 导入目录
            dir_items = await knowledge_service.import_from_directory(
                dir_path=request.dir_path,
                enrich=request.enrich,
                recursive=request.recursive,
            )
            items.extend(dir_items)

        logger.info("文档导入完成 | count={}", len(items))

        return {
            "status": "success",
            "imported_count": len(items),
            "message": f"成功导入 {len(items)} 个文档",
        }

    except Exception as e:
        logger.error("文档导入失败 | error={}", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"文档导入失败: {str(e)}",
        )
