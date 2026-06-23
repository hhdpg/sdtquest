"""问答服务模块。

本模块实现了问答服务的核心业务编排逻辑，串联 RAG 检索、LLM 生成、
问题分类、日志记录等流程，对外提供统一的问答接口。

主要类:
- QAService: 问答服务主类，编排完整的问答流程

典型用法:
    >>> from src.services.qa_service import QAService
    >>> from src.llm.client import OllamaClient
    >>> from src.rag.pipeline import RAGPipeline
    >>> from src.infrastructure.repositories.question_repo import SQLiteQuestionRepository
    >>> service = QAService(llm=llm_client, rag_pipeline=pipeline, question_repo=repo)
    >>> answer = await service.ask("如何创建订单?", "conv_123")
    >>> print(answer.text)
"""

import asyncio
import re
import time
from typing import Any, Protocol
from uuid import uuid4

from loguru import logger

from src.config import settings
from src.domain.enums import AnswerStatus, QuestionCategory
from src.domain.exceptions import (
    KnowledgeNotFoundError,
    LLMServiceError,
    QuestionProcessingError,
)
from src.domain.models import Answer, Message, Question
from src.domain.ports import LLMClient, GenerateOptions
from src.rag.pipeline import RAGPipeline, RAGResult


# ============================================================================
# 可选依赖的 Protocol 定义
# ============================================================================

class Classifier(Protocol):
    """问题分类器接口（可选依赖）

    用于对问题进行分类。实现类可以来自 analyzer/classifier.py。
    """

    async def classify(self, question: str) -> QuestionCategory:
        """
        对问题进行分类

        Args:
            question: 问题文本

        Returns:
            问题分类
        """
        ...


class SessionManager(Protocol):
    """会话管理器接口（可选依赖）

    用于维护对话上下文历史。实现类可以来自 bot/session.py。
    """

    def get_history(self, conversation_id: str) -> list[Message]:
        """
        获取指定会话的对话历史

        Args:
            conversation_id: 会话 ID

        Returns:
            消息列表
        """
        ...


# ============================================================================
# QAService
# ============================================================================

class QAService:
    """
    问答服务类。

    负责编排完整的问答流程，包括:
    1. 获取会话上下文（可选）
    2. 问题分类（可选）
    3. RAG 检索相关知识
    4. 组装 Prompt（内置于 RAG 管道中）
    5. 调用 LLM 生成答案
    6. 回答后处理（格式化、引用标注）
    7. 记录问答日志

    不同问题分类使用不同的生成策略:
    - 标准操作类 (operation_guide): temperature=0.3, 检索阈值>0.8
    - 灵活推理类 (process_inquiry, anomaly_troubleshoot): temperature=0.7, 检索阈值>0.6
    - 其他 (general): 使用灵活推理策略

    Attributes:
        llm: LLM 客户端，用于生成答案
        rag_pipeline: RAG 管道，用于检索知识
        question_repo: 问题仓储，用于保存问答记录
        classifier: 问题分类器（可选）
        session_manager: 会话管理器（可选）
        standard_temperature: 标准操作类的生成温度
        flexible_temperature: 灵活推理类的生成温度

    Example:
        >>> service = QAService(llm=llm_client, rag_pipeline=pipeline, question_repo=repo)
        >>> answer = await service.ask("如何创建订单?", "conv_123")
        >>> print(answer.text)
        '创建订单的步骤如下...'
        >>> print(answer.confidence)
        0.85

    Note:
        - 标准操作类问题使用 temperature=0.3，确保回答准确
        - 灵活推理类问题使用 temperature=0.7，允许更灵活的推理
        - 处理时间通常 < 30 秒

    See Also:
        - RAGPipeline: RAG 检索管道
        - ContextAssembler: 上下文组装器
    """

    def __init__(
        self,
        llm: LLMClient,
        rag_pipeline: RAGPipeline,
        question_repo: Any,
        classifier: Classifier | None = None,
        session_manager: SessionManager | None = None,
        standard_temperature: float | None = None,
        flexible_temperature: float | None = None,
    ):
        """
        初始化问答服务。

        Args:
            llm: LLM 客户端实例
            rag_pipeline: RAG 管道实例
            question_repo: 问题仓储实例
            classifier: 问题分类器（可选，未提供则跳过分类）
            session_manager: 会话管理器（可选，未提供则不使用对话历史）
            standard_temperature: 标准操作类温度，默认从配置读取
            flexible_temperature: 灵活推理类温度，默认从配置读取
        """
        self.llm = llm
        self.rag_pipeline = rag_pipeline
        self.question_repo = question_repo
        self.classifier = classifier
        self.session_manager = session_manager
        self.standard_temperature = (
            standard_temperature
            if standard_temperature is not None
            else settings.LLM_TEMPERATURE_STANDARD
        )
        self.flexible_temperature = (
            flexible_temperature
            if flexible_temperature is not None
            else settings.LLM_TEMPERATURE_FLEXIBLE
        )
        logger.info(
            "QAService 初始化 | standard_temp={} | flexible_temp={} | classifier={} | session={}",
            self.standard_temperature,
            self.flexible_temperature,
            type(classifier).__name__ if classifier else None,
            type(session_manager).__name__ if session_manager else None,
        )

    async def ask(
        self,
        question_text: str,
        conversation_id: str,
        sender_id: str = "",
        history: list[Message] | None = None,
        category: QuestionCategory | None = None,
        temperature: float | None = None,
    ) -> Answer:
        """
        处理用户问题并生成答案。

        完整的处理流程:
        1. 验证问题文本
        2. 获取会话上下文（从 session_manager 或参数获取）
        3. 问题分类（如果未提供且分类器可用）
        4. RAG 检索相关知识
        5. 组装 Prompt（内置于 RAG 管道中）
        6. 调用 LLM 生成答案
        7. 后处理（格式化、引用标注）
        8. 记录问答日志

        Args:
            question_text: 用户问题文本，不能为空
            conversation_id: 会话 ID，用于维护上下文
            sender_id: 发送人 ID
            history: 对话历史（可选，优先级高于 session_manager）
            category: 问题分类，如果为 None 则自动分类
            temperature: LLM 生成温度，如果为 None 则根据分类自动选择

        Returns:
            Answer: 生成的答案对象，包含答案文本、引用来源、置信度等

        Raises:
            QuestionProcessingError: 问题文本为空或处理过程中发生严重错误
        """
        start_time = time.time()

        # ── 1. 验证问题 ──
        if not question_text or not question_text.strip():
            raise QuestionProcessingError("问题文本不能为空")

        question_text = question_text.strip()
        if len(question_text) > 2000:
            raise QuestionProcessingError("问题文本过长（最大 2000 字符）")

        # ── 2. 创建 Question 对象 ──
        question = Question(
            text=question_text,
            sender_id=sender_id or "unknown",
            conversation_id=conversation_id,
        )

        # ── 3. 获取对话历史 ──
        if history is None and self.session_manager is not None:
            try:
                history = self.session_manager.get_history(conversation_id)
            except Exception as e:
                logger.warning("获取对话历史失败 | error={}", str(e))
                history = None

        # ── 4. 问题分类 ──
        if category is None:
            category = await self._classify_question(question_text)

        if category is not None:
            question = question.set_category(category)

        # ── 5. 确定生成温度 ──
        effective_temperature = temperature if temperature is not None else self._get_temperature(category)

        logger.info(
            "收到问题 | sender={} | text={} | category={} | temperature={}",
            sender_id,
            question_text[:50],
            category.value if category else None,
            effective_temperature,
        )

        # ── 6. RAG 检索 + LLM 生成 ──
        try:
            # RAG 检索
            rag_result = await self._retrieve(question, history, category)

            # LLM 生成
            answer_text = await self._generate(rag_result.prompt, category, effective_temperature)

            # 后处理
            answer_text = self._post_process(answer_text, rag_result)

            # 构建 Answer
            answer = Answer(
                id=str(uuid4()),
                question_id=question.id,
                text=answer_text,
                sources=rag_result.sources,
                confidence=self._calculate_confidence(rag_result, category),
                category=category or QuestionCategory.GENERAL,
                status=AnswerStatus.SUCCESS,
            )

        except asyncio.TimeoutError as e:
            logger.error("问题处理超时 | question_id={}", question.id)
            answer = self._create_error_answer(question, "回答超时，请稍后再试")
            raise QuestionProcessingError("回答超时") from e

        except KnowledgeNotFoundError:
            # 知识未找到时，生成友好的提示回复，而非抛出异常
            answer = self._create_no_match_answer(question, category)

        except LLMServiceError as e:
            logger.error("LLM 服务错误 | question_id={} | error={}", question.id, str(e))
            answer = self._create_error_answer(question, "服务繁忙，请稍后再试")

        except Exception as e:
            logger.error("问题处理异常 | question_id={} | error={}", question.id, str(e))
            answer = self._create_error_answer(question, "暂时无法回答，请稍后再试")

        # ── 7. 记录问答日志 ──
        self._save_record(question, answer)

        latency = time.time() - start_time
        logger.info(
            "问答完成 | status={} | confidence={:.2f} | latency={:.1f}s | sources={}",
            answer.status.value,
            answer.confidence,
            latency,
            len(answer.sources),
        )

        return answer

    async def _classify_question(self, question_text: str) -> QuestionCategory | None:
        """
        对问题进行分类。

        如果配置了分类器则调用分类器，否则返回 None。

        Args:
            question_text: 问题文本

        Returns:
            问题分类，无法分类时返回 None
        """
        if self.classifier is None:
            return None

        try:
            category = await self.classifier.classify(question_text)
            logger.info(
                "问题分类 | category={} | text={}",
                category.value,
                question_text[:30],
            )
            return category
        except Exception as e:
            logger.warning("问题分类失败，使用默认分类 | error={}", str(e))
            return None

    def _get_temperature(self, category: QuestionCategory | None) -> float:
        """
        根据问题分类获取生成温度。

        标准操作类使用较低温度（0.3）确保准确性，
        其他分类使用较高温度（0.7）允许灵活推理。

        Args:
            category: 问题分类

        Returns:
            生成温度值
        """
        if category == QuestionCategory.OPERATION_GUIDE:
            return self.standard_temperature
        return self.flexible_temperature

    async def _retrieve(
        self,
        question: Question,
        history: list[Message] | None,
        category: QuestionCategory | None,
    ) -> RAGResult:
        """
        执行 RAG 检索。

        Args:
            question: 问题对象
            history: 对话历史
            category: 问题分类

        Returns:
            RAG 检索结果

        Raises:
            KnowledgeNotFoundError: 未找到相关知识
        """
        rag_result = await self.rag_pipeline.query(
            question=question,
            history=history,
            category=category,
        )

        if not rag_result.documents:
            logger.warning("RAG 检索未命中 | question={}", question.text[:50])
            raise KnowledgeNotFoundError(
                f"未找到与问题相关的知识: {question.text[:50]}"
            )

        logger.info(
            "检索结果 | top_k={} | sources={}",
            len(rag_result.documents),
            rag_result.sources,
        )

        return rag_result

    async def _generate(
        self,
        prompt: str,
        category: QuestionCategory | None,
        temperature: float,
    ) -> str:
        """
        调用 LLM 生成答案。

        Args:
            prompt: 组装好的 Prompt
            category: 问题分类
            temperature: 生成温度

        Returns:
            LLM 生成的原始文本

        Raises:
            LLMServiceError: LLM 服务调用失败
        """
        options = GenerateOptions(
            temperature=temperature,
            max_tokens=settings.LLM_MAX_TOKENS,
        )

        answer_text = await self.llm.generate(prompt, options)

        logger.debug(
            "LLM 生成完成 | text_len={} | temperature={}",
            len(answer_text),
            temperature,
        )

        return answer_text

    def _post_process(self, answer_text: str, rag_result: RAGResult) -> str:
        """
        对 LLM 生成的答案进行后处理。

        处理流程:
        1. 检查空回复
        2. 去除 <think> 标签内容
        3. 统一编号格式（针对操作指南类）

        Args:
            answer_text: LLM 生成的原始文本
            rag_result: RAG 检索结果

        Returns:
            处理后的答案文本
        """
        if not answer_text or not answer_text.strip():
            return "抱歉，暂时无法生成回答，请稍后再试。"

        result = answer_text.strip()

        # 去除 <think>...</think> 标签（部分模型会输出思考过程）
        if "<think>" in result:
            result = re.sub(r"<think>.*?</think>\s*", "", result, flags=re.DOTALL)
            result = result.strip()

        # 操作指南类：确保步骤编号格式一致（1. 2. 3.）
        if rag_result.category == QuestionCategory.OPERATION_GUIDE:
            # 统一 "步骤1：" 或 "Step 1:" 为 "1. "
            result = re.sub(
                r"^(步骤\s*(\d+)\s*[：:]\s*)",
                r"\2. ",
                result,
                flags=re.MULTILINE,
            )

        return result

    def _calculate_confidence(
        self,
        rag_result: RAGResult,
        category: QuestionCategory | None,
    ) -> float:
        """
        根据检索结果计算回答置信度。

        基于检索到的文档数量、分类阈值等因素综合计算。

        Args:
            rag_result: RAG 检索结果
            category: 问题分类

        Returns:
            置信度值 (0.0-1.0)
        """
        doc_count = len(rag_result.documents)

        if doc_count == 0:
            return 0.0

        # 基础分：根据文档数量（1个文档 0.6, 3个以上 0.9）
        base_score = min(0.6 + (doc_count - 1) * 0.1, 0.9)

        # 根据分类调整：标准操作类要求更高，置信度略低
        if category == QuestionCategory.OPERATION_GUIDE:
            return min(base_score, 0.85)
        elif category == QuestionCategory.PROCESS_INQUIRY:
            return base_score
        elif category == QuestionCategory.ANOMALY_TROUBLESHOOT:
            return min(base_score, 0.80)
        else:
            return min(base_score, 0.75)

    def _create_no_match_answer(
        self,
        question: Question,
        category: QuestionCategory | None,
    ) -> Answer:
        """
        创建未匹配知识的回复。

        Args:
            question: 问题对象
            category: 问题分类

        Returns:
            状态为 NO_MATCH 的 Answer
        """
        text = (
            "抱歉，当前知识库中未找到与您问题相关的内容。\n\n"
            "您可以尝试:\n"
            "- 使用更具体的关键词描述问题\n"
            "- 提供页面名称或功能模块信息\n"
            "- 联系管理员补充相关知识"
        )
        return Answer(
            id=str(uuid4()),
            question_id=question.id,
            text=text,
            sources=[],
            confidence=0.0,
            category=category or QuestionCategory.GENERAL,
            status=AnswerStatus.NO_MATCH,
        )

    def _create_error_answer(
        self,
        question: Question,
        message: str,
    ) -> Answer:
        """
        创建错误状态回复。

        Args:
            question: 问题对象
            message: 错误提示消息

        Returns:
            状态为 ERROR 的 Answer
        """
        return Answer(
            id=str(uuid4()),
            question_id=question.id,
            text=message,
            sources=[],
            confidence=0.0,
            category=QuestionCategory.GENERAL,
            status=AnswerStatus.ERROR,
        )

    def _save_record(self, question: Question, answer: Answer) -> None:
        """
        保存问答记录到数据库。

        失败时仅记录日志，不影响主流程返回。

        Args:
            question: 问题对象
            answer: 回答对象
        """
        try:
            self.question_repo.save(question, answer)
            logger.debug(
                "问答记录已保存 | question_id={} | answer_id={}",
                question.id,
                answer.id,
            )
        except Exception as e:
            logger.error(
                "保存问答记录失败 | question_id={} | error={}",
                question.id,
                str(e),
            )


# ============================================================================
# 服务层异常
# ============================================================================

class QAServiceError(Exception):
    """问答服务异常"""
    pass
