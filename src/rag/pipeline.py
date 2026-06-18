"""RAG 主流程模块

编排完整的检索增强生成流程。
"""

from dataclasses import dataclass
from typing import Any

from loguru import logger

from src.domain.enums import QuestionCategory
from src.domain.models import KnowledgeItem, Message, Question
from src.rag.context import ContextAssembler
from src.rag.retriever import HybridRetriever, SimpleRetriever


@dataclass
class RAGResult:
    """
    RAG 检索结果

    Attributes:
        question: 原始问题
        prompt: 组装好的 Prompt
        documents: 检索到的知识文档
        sources: 引用来源列表
        category: 问题分类
    """
    question: Question
    prompt: str
    documents: list[KnowledgeItem]
    sources: list[str]
    category: QuestionCategory | None = None


class RAGPipeline:
    """
    RAG 主流程编排

    编排完整的检索流程：
    1. 根据问题类型选择检索策略
    2. 执行混合检索
    3. 组装上下文
    4. 返回 RAGResult

    Attributes:
        retriever: 检索器
        context_assembler: 上下文组装器
    """

    def __init__(
        self,
        retriever: HybridRetriever | SimpleRetriever | None = None,
        context_assembler: ContextAssembler | None = None,
        use_hybrid: bool = True,
    ):
        """
        初始化 RAG 管道

        Args:
            retriever: 检索器实例
            context_assembler: 上下文组装器实例
            use_hybrid: 是否使用混合检索（否则使用简单检索）
        """
        if retriever:
            self.retriever = retriever
        elif use_hybrid:
            self.retriever = HybridRetriever()
        else:
            self.retriever = SimpleRetriever()

        self.context_assembler = context_assembler or ContextAssembler()
        logger.info(
            "RAGPipeline 初始化 | retriever_type={}",
            type(self.retriever).__name__
        )

    async def query(
        self,
        question: Question,
        history: list[Message] | None = None,
        category: QuestionCategory | None = None,
        filters: dict[str, Any] | None = None,
    ) -> RAGResult:
        """
        执行 RAG 检索流程

        Args:
            question: 用户问题
            history: 对话历史
            category: 问题分类
            filters: 检索过滤条件

        Returns:
            RAGResult 对象
        """
        logger.info(
            "开始 RAG 流程 | question_id={} | category={}",
            question.id, category.value if category else None
        )

        try:
            # 执行检索
            documents = await self.retriever.retrieve(
                query=question.text,
                top_k=None,  # 使用默认值
                threshold=None,
                category=category,
                filters=filters,
            )

            # 组装上下文
            prompt = self.context_assembler.assemble(
                question=question.text,
                docs=documents,
                history=history,
                category=category,
            )

            # 构建引用来源
            sources = self.context_assembler.format_sources(documents)

            result = RAGResult(
                question=question,
                prompt=prompt,
                documents=documents,
                sources=sources,
                category=category,
            )

            logger.info(
                "RAG 流程完成 | docs_found={} | prompt_len={}",
                len(documents), len(prompt)
            )

            return result

        except Exception as e:
            logger.error("RAG 流程失败 | error={}", str(e))
            raise

    async def query_simple(
        self,
        question_text: str,
        top_k: int = 5,
    ) -> list[KnowledgeItem]:
        """
        简单查询接口（仅检索，不组装 Prompt）

        Args:
            question_text: 问题文本
            top_k: 返回数量

        Returns:
            知识条目列表
        """
        return await self.retriever.retrieve(
            query=question_text,
            top_k=top_k,
        )


class RAGPipelineBuilder:
    """
    RAG 管道构建器

    提供流畅的 API 来构建 RAG 管道。
    """

    def __init__(self):
        """初始化构建器"""
        self._retriever = None
        self._context_assembler = None
        self._use_hybrid = True

    def with_retriever(self, retriever) -> "RAGPipelineBuilder":
        """设置检索器"""
        self._retriever = retriever
        return self

    def with_context_assembler(self, assembler: ContextAssembler) -> "RAGPipelineBuilder":
        """设置上下文组装器"""
        self._context_assembler = assembler
        return self

    def use_hybrid_retrieval(self, use: bool = True) -> "RAGPipelineBuilder":
        """设置是否使用混合检索"""
        self._use_hybrid = use
        return self

    def build(self) -> RAGPipeline:
        """构建 RAG 管道"""
        return RAGPipeline(
            retriever=self._retriever,
            context_assembler=self._context_assembler,
            use_hybrid=self._use_hybrid,
        )
