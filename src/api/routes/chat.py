"""对话 API 路由模块。

提供调试用的对话接口，用于本地测试和开发调试。

接口:
- POST /api/chat: 发送问题并获取回答
"""

from typing import Any

from fastapi import APIRouter, Depends
from loguru import logger
from pydantic import BaseModel, Field

from src.api.deps import get_qa_service
from src.domain.enums import QuestionCategory
from src.services import QAService

router = APIRouter()


# ============================================================================
# 请求/响应模型
# ============================================================================

class ChatRequest(BaseModel):
    """
    对话请求模型。

    Attributes:
        question: 用户问题文本
        conversation_id: 会话 ID（可选，用于维护上下文）
        sender_id: 发送人 ID（可选）
        category: 问题分类（可选，不指定则自动分类）
        temperature: 生成温度（可选）

    Example:
        >>> request = ChatRequest(question="如何创建订单?")
    """
    question: str = Field(
        ...,
        description="用户问题文本",
        min_length=1,
        max_length=2000,
        examples=["如何创建订单?"],
    )
    conversation_id: str = Field(
        default="default",
        description="会话 ID，用于维护上下文",
    )
    sender_id: str = Field(
        default="api_debug",
        description="发送人 ID",
    )
    category: str | None = Field(
        default=None,
        description="问题分类（operation_guide/process_inquiry/anomaly_troubleshoot/general）",
    )
    temperature: float | None = Field(
        default=None,
        description="生成温度（0.0-1.0）",
        ge=0.0,
        le=1.0,
    )


class ChatResponse(BaseModel):
    """
    对话响应模型。

    Attributes:
        answer: 回答文本
        question_id: 问题 ID
        answer_id: 回答 ID
        category: 问题分类
        confidence: 置信度（0.0-1.0）
        status: 回答状态（success/no_match/error/timeout）
        sources: 引用来源列表

    Example:
        >>> response = ChatResponse(
        ...     answer="创建订单的步骤...",
        ...     category="operation_guide",
        ...     confidence=0.85,
        ... )
    """
    answer: str = Field(..., description="回答文本")
    question_id: str = Field(..., description="问题 ID")
    answer_id: str = Field(..., description="回答 ID")
    category: str = Field(..., description="问题分类")
    confidence: float = Field(..., description="置信度")
    status: str = Field(..., description="回答状态")
    sources: list[str] = Field(default_factory=list, description="引用来源列表")


# ============================================================================
# API 路由
# ============================================================================

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="调试用对话接口",
    description="发送问题并获取回答，用于本地测试和开发调试",
)
async def chat(
    request: ChatRequest,
    qa_service: QAService = Depends(get_qa_service),
) -> ChatResponse:
    """
    处理对话请求。

    调用 QAService 生成回答，返回完整的回答信息。

    Args:
        request: 对话请求
        qa_service: 问答服务（通过依赖注入获取）

    Returns:
        对话响应

    Example:
        POST /api/chat
        {
            "question": "如何创建订单?",
            "conversation_id": "test_123"
        }
    """
    logger.info(
        "收到对话请求 | question={} | conversation={}",
        request.question[:50],
        request.conversation_id,
    )

    # 解析分类（如果提供）
    category = None
    if request.category:
        try:
            category = QuestionCategory(request.category)
        except ValueError:
            logger.warning("无效的问题分类: {}", request.category)

    # 调用问答服务
    answer = await qa_service.ask(
        question_text=request.question,
        conversation_id=request.conversation_id,
        sender_id=request.sender_id,
        category=category,
        temperature=request.temperature,
    )

    logger.info(
        "对话完成 | status={} | confidence={:.2f} | sources={}",
        answer.status.value,
        answer.confidence,
        len(answer.sources),
    )

    return ChatResponse(
        answer=answer.text,
        question_id=answer.question_id,
        answer_id=answer.id,
        category=answer.category.value,
        confidence=answer.confidence,
        status=answer.status.value,
        sources=answer.sources,
    )


@router.post(
    "/chat/simple",
    summary="简单对话接口",
    description="简化的对话接口，只返回回答文本",
)
async def chat_simple(
    request: ChatRequest,
    qa_service: QAService = Depends(get_qa_service),
) -> dict[str, str]:
    """
    简化的对话请求。

    只返回回答文本，适用于快速测试。

    Args:
        request: 对话请求
        qa_service: 问答服务

    Returns:
        包含回答文本的字典
    """
    answer = await qa_service.ask(
        question_text=request.question,
        conversation_id=request.conversation_id,
        sender_id=request.sender_id,
    )

    return {"answer": answer.text}
