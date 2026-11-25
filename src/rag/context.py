"""上下文组装模块

将检索结果组装为 LLM Prompt。
"""

from loguru import logger

from src.config import settings
from src.domain.enums import QuestionCategory
from src.domain.models import KnowledgeItem, Message
from src.llm.prompts.qa import build_qa_prompt


class ContextAssembler:
    """
    上下文组装器

    将检索到的知识文档、对话历史和用户问题组装为最终 Prompt。

    Attributes:
        max_history: 最大对话历史轮数
        provider_manager: LLM 供应商管理器。传入后按当前 provider
            选择上下文长度预算（GLM 窗口大，可容纳更长的卡片）
    """

    def __init__(self, max_history: int = 3, provider_manager=None):
        """
        初始化上下文组装器

        Args:
            max_history: 最大对话历史轮数
            provider_manager: LLM 供应商管理器（可选）
        """
        self.max_history = max_history
        self.provider_manager = provider_manager
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

        会按单文档和整体上限截断，避免 prompt 超出模型上下文窗口
        导致回答被截断（9B 模型在超长 prompt 下只输出前几个 token）。
        GLM 窗口远大于本地模型，使用更宽松的上限。

        Args:
            docs: 知识文档列表

        Returns:
            格式化的知识上下文字符串
        """
        if not docs:
            return "（无相关知识）"

        glm = (
            self.provider_manager is not None
            and self.provider_manager.current == "glm"
        )
        max_doc_chars = (
            settings.RAG_MAX_DOC_CHARS_GLM if glm else settings.RAG_MAX_DOC_CHARS
        )
        max_total_chars = (
            settings.RAG_MAX_CONTEXT_CHARS_GLM if glm
            else settings.RAG_MAX_CONTEXT_CHARS
        )

        parts = []
        used = 0
        for i, doc in enumerate(docs, 1):
            raw = doc.content
            content = self._strip_document_header(raw)
            if len(content) > max_doc_chars:
                content = content[:max_doc_chars] + "\n...(内容过长已截断)"
                logger.debug(
                    "知识文档超长已截断 | title={} | 原始长度={}",
                    doc.title, len(raw),
                )

            doc_parts = [f"【文档{i}】{doc.title}"]

            # 添加页面信息（只给菜单名，不给代码路由：
            # 前端路由如 /adiBus/order 业务人员看不懂，且会被模型照抄进答案）
            if doc.page_name:
                doc_parts.append(f"所属模块: {doc.page_name}")

            # 菜单入口：知识卡片的 page_path 是中文菜单层级
            #（如「订单管理 → 订单列表」），是用户唯一能照做的定位信息，
            # 必须保留。但代码解析来的知识 page_path 是 URL / 前端路由，
            # 业务人员看不懂，过滤掉。
            entry_path = self._usable_entry_path(doc.page_path)
            if entry_path:
                doc_parts.append(f"入口: {entry_path}")

            # 添加内容
            doc_parts.append(f"内容: {content}")

            # 添加标签
            if doc.tags:
                doc_parts.append(f"标签: {', '.join(doc.tags)}")

            block = "\n".join(doc_parts)

            # 整体预算控制：超限则停止追加后续文档
            if used + len(block) > max_total_chars:
                logger.info(
                    "上下文达到长度上限，其余文档已跳过 | 已用={} | 上限={} | 跳过数量={}",
                    used, max_total_chars, len(docs) - (i - 1),
                )
                break

            parts.append(block)
            used += len(block)

        return "\n\n".join(parts)

    @staticmethod
    def _usable_entry_path(page_path: str | None) -> str:
        """
        判断 page_path 能否给业务人员看。

        知识卡片填的是中文菜单层级（如「订单管理 → 新建订单」），可以直接展示；
        代码解析来的知识填的是 URL 或前端路由（如 https://… /adiBus/order），
        业务人员看不懂，也不该出现在答案里。

        Args:
            page_path: 知识条目的 page_path

        Returns:
            可展示的菜单路径；不可用时返回空字符串
        """
        if not page_path:
            return ""

        value = page_path.strip()
        if not value or value.startswith(("/", "http://", "https://")):
            return ""

        return value

    @staticmethod
    def _strip_document_header(content: str) -> str:
        """
        去掉向量库文档里自带的标题/页面/路径/标签行。

        向量库存的 document 是 to_document_string() 的产物，已包含
        「标题: …\n页面: …\n路径: …\n内容: …\n标签: …」。
        组装 Prompt 时又拼了一遍标题和标签，会白占约 150 字/卡。

        Args:
            content: 向量库中的原始文档字符串

        Returns:
            只保留正文（若不符合该格式则原样返回）
        """
        marker = "\n内容: "
        idx = content.find(marker)
        if not content.startswith("标题: ") or idx < 0:
            return content

        body = content[idx + len(marker):]

        # 去掉末尾的「标签: …」行
        tag_marker = "\n标签: "
        tag_idx = body.rfind(tag_marker)
        if tag_idx >= 0:
            body = body[:tag_idx]

        return body.strip()

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
