"""回答模型"""

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from src.domain.enums import AnswerStatus, QuestionCategory


class Answer(BaseModel):
    """
    生成的回答模型

    Attributes:
        id: 回答唯一标识 (UUID)
        question_id: 关联的问题 ID
        text: 回答文本内容
        sources: 引用的知识文档 ID 列表
        confidence: 回答置信度 (0.0-1.0)
        category: 问题分类
        status: 回答状态
        created_at: 回答创建时间
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    question_id: str = Field(..., min_length=1)
    text: str = Field(default="")
    sources: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    category: QuestionCategory = Field(default=QuestionCategory.GENERAL)
    status: AnswerStatus = Field(default=AnswerStatus.SUCCESS)
    created_at: datetime = Field(default_factory=datetime.now)

    def is_successful(self) -> bool:
        """判断回答是否成功"""
        return self.status == AnswerStatus.SUCCESS

    def has_sources(self) -> bool:
        """判断是否有引用来源"""
        return len(self.sources) > 0

    def format_with_sources(self) -> str:
        """格式化回答，附带引用来源"""
        if not self.has_sources():
            return self.text

        source_text = "\n\n---\n📚 **参考来源**:\n"
        for i, source in enumerate(self.sources, 1):
            source_text += f"{i}. {source}\n"
        return self.text + source_text
