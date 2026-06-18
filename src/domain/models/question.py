"""问题模型"""

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from src.domain.enums import QuestionCategory


class Question(BaseModel):
    """
    用户提问模型

    Attributes:
        id: 问题唯一标识 (UUID)
        text: 问题文本内容
        sender_id: 发送人的钉钉 ID
        conversation_id: 会话 ID，用于维护上下文
        category: 问题分类，分类后填充
        created_at: 问题创建时间
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    text: str = Field(..., min_length=1, max_length=2000)
    sender_id: str = Field(..., min_length=1)
    conversation_id: str = Field(..., min_length=1)
    category: QuestionCategory | None = None
    created_at: datetime = Field(default_factory=datetime.now)

    def set_category(self, category: QuestionCategory) -> "Question":
        """设置问题分类并返回新实例"""
        return self.model_copy(update={"category": category})

    def is_classifiable(self) -> bool:
        """判断问题是否可分类（非空且长度足够）"""
        return len(self.text.strip()) >= 4
