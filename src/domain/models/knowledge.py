"""知识条目模型"""

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from src.domain.enums import KnowledgeType


class KnowledgeItem(BaseModel):
    """
    知识条目模型

    表示一条从代码解析或手动文档中提取的知识

    Attributes:
        id: 知识条目唯一标识 (UUID)
        type: 知识类型
        title: 知识标题
        content: 知识内容（详细描述）
        page_name: 所属页面名称（可选）
        page_path: 页面路由路径（可选）
        source_file: 来源文件路径（可选）
        tags: 标签列表，用于过滤检索
        embedding: 向量表示（入库后由向量库管理）
        created_at: 创建时间
        updated_at: 更新时间
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: KnowledgeType = Field(default=KnowledgeType.MANUAL)
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    page_name: str | None = None
    page_path: str | None = None
    source_file: str | None = None
    tags: list[str] = Field(default_factory=list)
    embedding: list[float] | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def to_document_string(self) -> str:
        """转换为用于向量化的文档字符串"""
        parts = [f"标题: {self.title}"]

        if self.page_name:
            parts.append(f"页面: {self.page_name}")
        if self.page_path:
            parts.append(f"路径: {self.page_path}")

        parts.append(f"内容: {self.content}")

        if self.tags:
            parts.append(f"标签: {', '.join(self.tags)}")

        return "\n".join(parts)

    def get_metadata(self) -> dict:
        """获取用于向量库存储的元数据"""
        return {
            "type": self.type.value,
            "title": self.title,
            "page_name": self.page_name or "",
            "page_path": self.page_path or "",
            "source_file": self.source_file or "",
            "tags": ",".join(self.tags),
        }
