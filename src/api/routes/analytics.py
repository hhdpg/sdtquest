"""统计分析 API 路由模块。

提供问答数据的统计分析、高频问题查询、日报生成等接口。

接口:
- GET /api/analytics/summary: 获取问题统计摘要
- GET /api/analytics/top-questions: 获取高频问题
- GET /api/analytics/unanswered: 获取未回答问题
- GET /api/analytics/report: 生成日报/周报
- POST /api/analytics/report: 生成并保存日报
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from loguru import logger
from pydantic import BaseModel, Field

from src.api.deps import get_analytics_service
from src.services import AnalyticsService

router = APIRouter()


# ============================================================================
# 响应模型
# ============================================================================

class SummaryResponse(BaseModel):
    """
    统计摘要响应模型。

    Attributes:
        total: 问题总数
        days: 统计天数
        by_category: 各分类问题数量
        avg_confidence: 平均置信度
        success_rate: 成功回答比例

    Example:
        >>> summary = SummaryResponse(
        ...     total=100,
        ...     days=7,
        ...     by_category={"operation_guide": 50},
        ...     avg_confidence=0.85,
        ...     success_rate=0.95,
        ... )
    """
    total: int = Field(..., description="问题总数")
    days: int = Field(..., description="统计天数")
    by_category: dict[str, int] = Field(default_factory=dict, description="各分类问题数量")
    avg_confidence: float = Field(default=0.0, description="平均置信度")
    success_rate: float = Field(default=0.0, description="成功回答比例")


class TopQuestionItem(BaseModel):
    """
    高频问题条目模型。
    """
    question: str = Field(..., description="问题文本")
    count: int = Field(..., description="出现次数")
    rank: int = Field(..., description="排名")


class TopQuestionsResponse(BaseModel):
    """
    高频问题响应模型。
    """
    questions: list[TopQuestionItem] = Field(default_factory=list, description="高频问题列表")
    days: int = Field(..., description="统计天数")


class UnansweredQuestionItem(BaseModel):
    """
    未回答问题条目模型。
    """
    id: str = Field(..., description="问题 ID")
    text: str = Field(..., description="问题文本")
    sender_id: str = Field(..., description="发送人 ID")
    created_at: str = Field(..., description="创建时间")


class UnansweredResponse(BaseModel):
    """
    未回答问题响应模型。
    """
    questions: list[UnansweredQuestionItem] = Field(default_factory=list, description="未回答问题列表")
    days: int = Field(..., description="统计天数")
    total: int = Field(..., description="未回答问题总数")


class ReportResponse(BaseModel):
    """
    报告响应模型。
    """
    status: str = Field(..., description="状态")
    report: str = Field(default="", description="报告内容（Markdown 格式）")
    message: str = Field(default="", description="状态消息")


# ============================================================================
# API 路由
# ============================================================================

@router.get(
    "/analytics/summary",
    response_model=SummaryResponse,
    summary="获取统计摘要",
    description="获取问题分类统计、平均置信度、成功率等",
)
async def get_summary(
    days: int = Query(default=7, ge=1, le=365, description="统计最近 N 天"),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> SummaryResponse:
    """
    获取问题统计摘要。

    包括:
    - 问题总数
    - 各分类问题数量
    - 平均置信度
    - 成功回答比例

    Args:
        days: 统计天数
        analytics_service: 分析汇总服务

    Returns:
        统计摘要
    """
    logger.info("获取统计摘要 | days={}", days)

    summary = await analytics_service.get_summary(days=days)

    return SummaryResponse(
        total=summary["total"],
        days=summary["days"],
        by_category=summary["by_category"],
        avg_confidence=summary["avg_confidence"],
        success_rate=summary["success_rate"],
    )


@router.get(
    "/analytics/top-questions",
    response_model=TopQuestionsResponse,
    summary="获取高频问题",
    description="获取最近 N 天内出现频率最高的问题",
)
async def get_top_questions(
    days: int = Query(default=7, ge=1, le=365, description="统计最近 N 天"),
    limit: int = Query(default=10, ge=1, le=100, description="返回数量"),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> TopQuestionsResponse:
    """
    获取高频问题列表。

    Args:
        days: 统计天数
        limit: 返回数量
        analytics_service: 分析汇总服务

    Returns:
        高频问题列表
    """
    logger.info("获取高频问题 | days={} | limit={}", days, limit)

    questions = await analytics_service.get_top_questions(
        days=days,
        limit=limit,
    )

    items = [
        TopQuestionItem(
            question=q["question"],
            count=q["count"],
            rank=q["rank"],
        )
        for q in questions
    ]

    return TopQuestionsResponse(
        questions=items,
        days=days,
    )


@router.get(
    "/analytics/unanswered",
    response_model=UnansweredResponse,
    summary="获取未回答问题",
    description="获取知识库未覆盖或处理出错的问题",
)
async def get_unanswered(
    days: int = Query(default=7, ge=1, le=365, description="查询最近 N 天"),
    limit: int = Query(default=20, ge=1, le=100, description="返回数量"),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> UnansweredResponse:
    """
    获取未回答的问题列表。

    这些问题是知识库未覆盖或处理出错的问题，
    可用于发现知识库的盲区。

    Args:
        days: 查询天数
        limit: 返回数量
        analytics_service: 分析汇总服务

    Returns:
        未回答问题列表
    """
    logger.info("获取未回答问题 | days={} | limit={}", days, limit)

    questions = await analytics_service.get_unanswered(
        days=days,
        limit=limit,
    )

    items = [
        UnansweredQuestionItem(
            id=q["id"],
            text=q["text"],
            sender_id=q["sender_id"],
            created_at=q["created_at"],
        )
        for q in questions
    ]

    return UnansweredResponse(
        questions=items,
        days=days,
        total=len(items),
    )


@router.get(
    "/analytics/report",
    response_model=ReportResponse,
    summary="生成报告",
    description="生成日报或周报（Markdown 格式）",
)
async def generate_report(
    days: int = Query(default=1, ge=1, le=30, description="统计天数（1=日报，7=周报）"),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> ReportResponse:
    """
    生成报告。

    生成 Markdown 格式的日报或周报，包含:
    - 问题分类统计
    - 高频问题 TOP 5
    - 未回答问题
    - 平均置信度和成功率

    Args:
        days: 统计天数
        analytics_service: 分析汇总服务

    Returns:
        报告内容
    """
    logger.info("生成报告 | days={}", days)

    report = await analytics_service.generate_daily_report(
        days=days,
        push_to_dingtalk=False,
    )

    period = "日报" if days == 1 else f"周报（近 {days} 天）"

    return ReportResponse(
        status="success",
        report=report,
        message=f"{period}生成成功",
    )


@router.post(
    "/analytics/report/save",
    response_model=ReportResponse,
    summary="生成并保存报告",
    description="生成报告并保存到数据库",
)
async def save_report(
    days: int = Query(default=1, ge=1, le=30, description="统计天数"),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> ReportResponse:
    """
    生成并保存报告。

    生成报告后将统计结果保存到 daily_summary 表。

    Args:
        days: 统计天数
        analytics_service: 分析汇总服务

    Returns:
        报告内容
    """
    logger.info("生成并保存报告 | days={}", days)

    try:
        # 生成报告
        report = await analytics_service.generate_daily_report(
            days=days,
            push_to_dingtalk=False,
        )

        # 保存到数据库
        await analytics_service.save_daily_summary(days=days)

        period = "日报" if days == 1 else f"周报（近 {days} 天）"

        return ReportResponse(
            status="success",
            report=report,
            message=f"{period}已保存",
        )

    except Exception as e:
        logger.error("生成并保存报告失败 | error={}", str(e))
        return ReportResponse(
            status="error",
            report="",
            message=f"报告生成失败: {str(e)}",
        )
