"""端口接口定义模块

定义基础设施层的接口规范，遵循依赖倒置原则。
实现类在 infrastructure/ 或相应模块中提供。
"""

from typing import AsyncIterator, Protocol

from src.domain.models import Answer, KnowledgeItem, Message, Question
from src.domain.enums import QuestionCategory


# ============================================================================
# 生成选项
# ============================================================================

class GenerateOptions:
    """
    LLM 生成选项

    Attributes:
        temperature: 生成温度，0.0-1.0，越高越随机
        max_tokens: 最大生成 token 数
        top_p: Top-p 采样参数
        stop: 停止词列表
    """
    def __init__(
        self,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        top_p: float = 0.9,
        stop: list[str] | None = None,
    ):
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.stop = stop or []


# ============================================================================
# LLM 客户端接口
# ============================================================================

class LLMClient(Protocol):
    """
    LLM 客户端接口

    定义与大语言模型交互的标准接口。
    实现类: OllamaClient (src/llm/client.py)
    """

    async def generate(
        self,
        prompt: str,
        options: GenerateOptions | None = None
    ) -> str:
        """
        生成文本

        Args:
            prompt: LLM 提示词
            options: 生成选项

        Returns:
            生成的文本
        """
        ...

    async def generate_stream(
        self,
        prompt: str,
        options: GenerateOptions | None = None
    ) -> AsyncIterator[str]:
        """
        流式生成文本

        Args:
            prompt: LLM 提示词
            options: 生成选项

        Yields:
            生成的文本片段
        """
        ...

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """
        批量向量化文本

        Args:
            texts: 待向量化的文本列表

        Returns:
            向量列表，每个向量是一个浮点数列表
        """
        ...


# ============================================================================
# 向量存储接口
# ============================================================================

class VectorStore(Protocol):
    """
    向量存储接口

    定义向量数据库的标准操作接口。
    实现类: ChromaVectorStore (src/rag/vectorstore.py)
    """

    async def add(self, items: list[KnowledgeItem]) -> None:
        """
        添加知识文档到向量库

        Args:
            items: 知识条目列表
        """
        ...

    async def search(
        self,
        query: list[float],
        top_k: int = 5,
        threshold: float = 0.0,
        filters: dict | None = None
    ) -> list[KnowledgeItem]:
        """
        按向量检索相似文档

        Args:
            query: 查询向量
            top_k: 返回结果数量
            threshold: 相似度阈值
            filters: 元数据过滤条件

        Returns:
            按相似度排序的知识条目列表
        """
        ...

    async def delete(self, ids: list[str]) -> None:
        """
        删除指定文档

        Args:
            ids: 文档 ID 列表
        """
        ...

    async def clear(self) -> None:
        """清空向量库"""
        ...

    async def count(self) -> int:
        """获取文档总数"""
        ...


# ============================================================================
# 问题仓储接口
# ============================================================================

class QuestionRepository(Protocol):
    """
    问题仓储接口

    定义问答记录的持久化操作接口。
    实现类: SQLiteQuestionRepository (src/infrastructure/repositories/question_repo.py)
    """

    def save(self, question: Question, answer: Answer) -> None:
        """
        保存问答记录

        Args:
            question: 问题对象
            answer: 回答对象
        """
        ...

    def find_recent(
        self,
        days: int = 7,
        limit: int = 100
    ) -> list[tuple[Question, Answer]]:
        """
        查询最近的问答记录

        Args:
            days: 查询最近 N 天
            limit: 最大返回数量

        Returns:
            问答记录列表
        """
        ...

    def count_by_category(self, days: int = 7) -> dict[QuestionCategory, int]:
        """
        按分类统计问题数量

        Args:
            days: 统计最近 N 天

        Returns:
            分类到数量的映射
        """
        ...

    def find_unanswered(self, days: int = 7, limit: int = 50) -> list[Question]:
        """
        查询未回答的问题

        Args:
            days: 查询最近 N 天
            limit: 最大返回数量

        Returns:
            未回答的问题列表
        """
        ...

    def get_top_questions(
        self,
        days: int = 7,
        limit: int = 10
    ) -> list[tuple[str, int]]:
        """
        获取高频问题

        Args:
            days: 统计最近 N 天
            limit: 返回数量

        Returns:
            (问题文本, 出现次数) 列表
        """
        ...


# ============================================================================
# 消息发送接口
# ============================================================================

class MessageSender(Protocol):
    """
    消息发送接口

    定义消息发送的标准接口。
    实现类: DingTalkSender (src/bot/sender.py)
    """

    async def send_text(self, conversation_id: str, text: str) -> str:
        """
        发送纯文本消息

        Args:
            conversation_id: 会话 ID
            text: 文本内容

        Returns:
            消息 ID
        """
        ...

    async def send_markdown(
        self,
        conversation_id: str,
        title: str,
        text: str
    ) -> str:
        """
        发送 Markdown 格式消息

        Args:
            conversation_id: 会话 ID
            title: 消息标题
            text: Markdown 内容

        Returns:
            消息 ID
        """
        ...

    async def update_message(self, message_id: str, new_content: str) -> None:
        """
        更新已发送的消息

        Args:
            message_id: 消息 ID
            new_content: 新的消息内容
        """
        ...
