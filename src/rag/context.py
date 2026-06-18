"""上下文组装模块

将检索结果组装为 LLM Prompt。
"""

from loguru import logger

from src.domain.enums import QuestionCategory
from src.domain.models import KnowledgeItem, Message
from src.llm.prompts.qa import (
    QA_SYSTEM_PROMPT,
    build_qa_prompt,
)


class ContextAssembler:
    """
    上下文组装器

    将检索到的知识文档、对话历史和用户问题组装为最终 Prompt。

    Attributes:
        max_history: 最大对话历史轮数
    """

    def __init__(self, max_history: int = 3):
        """
        初始化上下文组装器

        Args:
            max_history: 最大对话历史轮数
        """
        self.max_history = max_history
        logger.info("ContextAssembler 初始化 | max_history={}", max_history)

    def assemble(
        self,
        question: str,
        docs: list[KnowledgeItem],
        history: list[Message] | None = None,
        category: QuestionCategory | None = None,
    ) -> str:
        """
        组装完整的 Prompt

        Args:
            question: 用户问题
            docs: 检索到的知识文档
            history: 对话历史
            category: 问题分类

        Returns:
            完整的 Prompt 字符串
        """
        # 构建知识上下文
        knowledge_context = self._build_knowledge_context(docs)

        # 构建对话历史
        conversation_history = self._build_conversation_history(history)

        # 确定是否为标准操作类
        is_standard = self._is_standard_category(category)

        # 使用 Prompt 模板构建
        prompt = build_qa_prompt(
            question=question,
            knowledge_context=knowledge_context,
            conversation_history=conversation_history,
            is_standard=is_standard,
        )

        logger.debug(
            "Prompt 组装完成 | question_len={} | docs={} | history={} | prompt_len={}",
            len(question), len(docs),
            len(history) if history else 0,
            len(prompt)
        )

        return prompt

    def _build_knowledge_context(self, docs: list[KnowledgeItem]) -> str:
        """
        构建知识上下文文本

        Args:
            docs: 知识文档列表

        Returns:
            格式化的知识上下文字符串
        """
        if not docs:
            return "（无相关知识）"

        parts = []
        for i, doc in enumerate(docs, 1):
            doc_parts = [f"【文档{i}】{doc.title}"]

            # 添加页面信息
            if doc.page_name:
                doc_parts.append(f"页面: {doc.page_name}")
            if doc.page_path:
                doc_parts.append(f"路径: {doc.page_path}")

            # 添加内容
            doc_parts.append(f"内容: {doc.content}")

            # 添加标签
            if doc.tags:
                doc_parts.append(f"标签: {', '.join(doc.tags)}")

            parts.append("\n".join(doc_parts))

        return "\n\n".join(parts)

    def _build_conversation_history(
        self,
        history: list[Message] | None,
    ) -> str:
        """
        构建对话历史文本

        Args:
            history: 对话历史

        Returns:
            格式化的对话历史字符串
        """
        if not history:
            return "（无历史记录）"

        # 取最近的几轮对话
        recent = history[-self.max_history * 2:]  # 每轮包含用户和助手各一条

        parts = []
        for msg in recent:
            role = "用户" if msg.is_user() else "助手"
            parts.append(f"{role}: {msg.content}")

        return "\n".join(parts) if parts else "（无历史记录）"

    def _is_standard_category(self, category: QuestionCategory | None) -> bool:
        """
        判断是否为标准操作类

        Args:
            category: 问题分类

        Returns:
            True 表示标准操作类，False 表示灵活推理类
        """
        if category is None:
            return False
        return category == QuestionCategory.OPERATION_GUIDE

    def format_sources(self, docs: list[KnowledgeItem]) -> list[str]:
        """
        格式化引用来源

        Args:
            docs: 知识文档列表

        Returns:
            引用来源列表
        """
        sources = []
        for doc in docs:
            if doc.page_name:
                sources.append(f"{doc.page_name} - {doc.title}")
            else:
                sources.append(doc.title)
        return sources
