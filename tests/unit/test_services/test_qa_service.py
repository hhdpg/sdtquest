"""问答服务单元测试模块。

测试 QAService 的完整业务编排逻辑。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.domain.enums import AnswerStatus, QuestionCategory
from src.domain.exceptions import (
    KnowledgeNotFoundError,
    LLMServiceError,
    QuestionProcessingError,
)
from src.domain.models import Answer
from src.rag.pipeline import RAGPipeline, RAGResult
from src.services.qa_service import QAService


class TestQAServiceInit:
    """QAService 初始化测试"""

    def test_init_with_all_deps(self, mock_llm, mock_question_repo):
        """测试完整依赖初始化"""
        pipeline = MagicMock(spec=RAGPipeline)
        classifier = AsyncMock()
        session = MagicMock()

        service = QAService(
            llm=mock_llm,
            rag_pipeline=pipeline,
            question_repo=mock_question_repo,
            classifier=classifier,
            session_manager=session,
        )

        assert service.llm is mock_llm
        assert service.rag_pipeline is pipeline
        assert service.classifier is classifier
        assert service.session_manager is session

    def test_init_optional_deps_none(self, mock_llm, mock_question_repo):
        """测试可选依赖为 None"""
        pipeline = MagicMock(spec=RAGPipeline)
        service = QAService(
            llm=mock_llm,
            rag_pipeline=pipeline,
            question_repo=mock_question_repo,
        )
        assert service.classifier is None
        assert service.session_manager is None

    def test_init_custom_temperatures(self, mock_llm, mock_question_repo):
        """测试自定义温度参数"""
        pipeline = MagicMock(spec=RAGPipeline)
        service = QAService(
            llm=mock_llm,
            rag_pipeline=pipeline,
            question_repo=mock_question_repo,
            standard_temperature=0.2,
            flexible_temperature=0.8,
        )
        assert service.standard_temperature == 0.2
        assert service.flexible_temperature == 0.8


class TestQAServiceAsk:
    """QAService.ask() 方法测试"""

    @pytest.fixture
    def service(self, mock_llm, mock_question_repo, mock_classifier):
        pipeline = MagicMock(spec=RAGPipeline)
        return QAService(
            llm=mock_llm,
            rag_pipeline=pipeline,
            question_repo=mock_question_repo,
            classifier=mock_classifier,
        )

    @pytest.mark.asyncio
    async def test_ask_empty_question_raises(self, service):
        """测试空问题抛出异常"""
        with pytest.raises(QuestionProcessingError, match="不能为空"):
            await service.ask("", "conv_123")

    @pytest.mark.asyncio
    async def test_ask_whitespace_question_raises(self, service):
        """测试纯空白问题抛出异常"""
        with pytest.raises(QuestionProcessingError, match="不能为空"):
            await service.ask("   \n\t  ", "conv_123")

    @pytest.mark.asyncio
    async def test_ask_too_long_question_raises(self, service):
        """测试超长问题抛出异常"""
        long_text = "a" * 2001
        with pytest.raises(QuestionProcessingError, match="过长"):
            await service.ask(long_text, "conv_123")

    @pytest.mark.asyncio
    async def test_ask_success(self, service, mock_llm, sample_knowledge_items):
        """测试成功问答流程"""
        # 准备 RAG 结果
        rag_result = RAGResult(
            question=MagicMock(),
            prompt="test prompt",
            documents=sample_knowledge_items,
            sources=["订单管理"],
            category=QuestionCategory.OPERATION_GUIDE,
        )
        service.rag_pipeline.query = AsyncMock(return_value=rag_result)
        mock_llm.generate = AsyncMock(return_value="点击新建按钮即可。")

        # 执行
        answer = await service.ask("如何创建订单?", "conv_123", sender_id="user_1")

        # 验证
        assert isinstance(answer, Answer)
        assert answer.status == AnswerStatus.SUCCESS
        assert answer.text == "点击新建按钮即可。"
        assert answer.confidence > 0
        assert answer.sources == ["订单管理"]
        mock_llm.generate.assert_called_once()
        service.question_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_ask_strips_think_tags(self, service, mock_llm, sample_knowledge_items):
        """测试自动去除 think 标签"""
        rag_result = RAGResult(
            question=MagicMock(),
            prompt="test",
            documents=sample_knowledge_items,
            sources=[],
            category=QuestionCategory.GENERAL,
        )
        service.rag_pipeline.query = AsyncMock(return_value=rag_result)
        mock_llm.generate = AsyncMock(
            return_value="<think>让我思考一下</think>实际答案"
        )

        answer = await service.ask("问题", "conv_1")
        assert "<think>" not in answer.text
        assert "实际答案" in answer.text

    @pytest.mark.asyncio
    async def test_ask_knowledge_not_found_returns_no_match(
        self, service, sample_question
    ):
        """测试知识未找到时返回友好提示"""
        # RAG 检索返回空文档
        rag_result = RAGResult(
            question=MagicMock(),
            prompt="test",
            documents=[],
            sources=[],
            category=QuestionCategory.GENERAL,
        )
        service.rag_pipeline.query = AsyncMock(return_value=rag_result)

        answer = await service.ask("不存在的问题", "conv_1")
        assert answer.status == AnswerStatus.NO_MATCH
        assert "未找到" in answer.text

    @pytest.mark.asyncio
    async def test_ask_llm_error_returns_error_answer(self, service, mock_llm, sample_knowledge_items):
        """测试 LLM 错误时返回错误状态答案"""
        rag_result = RAGResult(
            question=MagicMock(),
            prompt="test",
            documents=sample_knowledge_items,
            sources=[],
            category=QuestionCategory.GENERAL,
        )
        service.rag_pipeline.query = AsyncMock(return_value=rag_result)
        mock_llm.generate = AsyncMock(side_effect=LLMServiceError("LLM 挂了"))

        answer = await service.ask("问题", "conv_1")
        assert answer.status == AnswerStatus.ERROR
        assert "繁忙" in answer.text or "稍后" in answer.text

    @pytest.mark.asyncio
    async def test_ask_uses_category_temperature(self, service, mock_llm, sample_knowledge_items):
        """测试不同分类使用不同温度"""
        rag_result = RAGResult(
            question=MagicMock(),
            prompt="test",
            documents=sample_knowledge_items,
            sources=[],
            category=QuestionCategory.OPERATION_GUIDE,
        )
        service.rag_pipeline.query = AsyncMock(return_value=rag_result)
        mock_llm.generate = AsyncMock(return_value="answer")

        await service.ask("如何操作?", "conv_1")

        # 验证调用时使用了标准温度 0.3
        call_args = mock_llm.generate.call_args
        options = call_args[0][1]
        assert options.temperature == 0.3

    @pytest.mark.asyncio
    async def test_ask_without_classifier(self, mock_llm, mock_question_repo, sample_knowledge_items):
        """测试没有分类器时正常处理"""
        pipeline = MagicMock(spec=RAGPipeline)
        rag_result = RAGResult(
            question=MagicMock(),
            prompt="test",
            documents=sample_knowledge_items,
            sources=[],
            category=None,
        )
        pipeline.query = AsyncMock(return_value=rag_result)
        mock_llm.generate = AsyncMock(return_value="answer")

        service = QAService(
            llm=mock_llm,
            rag_pipeline=pipeline,
            question_repo=mock_question_repo,
            classifier=None,
        )

        answer = await service.ask("问题", "conv_1")
        assert answer.status == AnswerStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_ask_with_session_manager(self, mock_llm, mock_question_repo, mock_classifier):
        """测试带会话管理器的处理"""
        pipeline = MagicMock(spec=RAGPipeline)
        session = MagicMock()
        session.get_history = MagicMock(return_value=[])

        rag_result = RAGResult(
            question=MagicMock(),
            prompt="test",
            documents=[MagicMock()],
            sources=[],
            category=QuestionCategory.GENERAL,
        )
        pipeline.query = AsyncMock(return_value=rag_result)
        mock_llm.generate = AsyncMock(return_value="answer")

        service = QAService(
            llm=mock_llm,
            rag_pipeline=pipeline,
            question_repo=mock_question_repo,
            classifier=mock_classifier,
            session_manager=session,
        )

        await service.ask("问题", "conv_1")
        session.get_history.assert_called_with("conv_1")


class TestQAServiceConfidence:
    """置信度计算测试"""

    @pytest.fixture
    def service(self, mock_llm, mock_question_repo):
        pipeline = MagicMock(spec=RAGPipeline)
        return QAService(
            llm=mock_llm,
            rag_pipeline=pipeline,
            question_repo=mock_question_repo,
        )

    def test_calculate_confidence_zero_docs(self, service):
        """测试 0 文档置信度为 0"""
        rag_result = MagicMock(documents=[])
        conf = service._calculate_confidence(rag_result, None)
        assert conf == 0.0

    def test_calculate_confidence_one_doc(self, service):
        """测试 1 文档置信度"""
        rag_result = MagicMock(documents=[MagicMock()])
        conf = service._calculate_confidence(rag_result, QuestionCategory.GENERAL)
        assert conf == 0.6

    def test_calculate_confidence_many_docs(self, service):
        """测试多文档置信度"""
        rag_result = MagicMock(documents=[MagicMock()] * 5)
        conf = service._calculate_confidence(rag_result, QuestionCategory.GENERAL)
        assert conf == 0.75  # min(0.6 + 4*0.1, 0.75)

    def test_calculate_confidence_operation_guide(self, service):
        """测试操作指南类置信度上限"""
        rag_result = MagicMock(documents=[MagicMock()] * 10)
        conf = service._calculate_confidence(rag_result, QuestionCategory.OPERATION_GUIDE)
        assert conf <= 0.85

    def test_calculate_confidence_anomaly(self, service):
        """测试异常排查置信度上限"""
        rag_result = MagicMock(documents=[MagicMock()] * 10)
        conf = service._calculate_confidence(rag_result, QuestionCategory.ANOMALY_TROUBLESHOOT)
        assert conf <= 0.80


class TestQAServicePostProcess:
    """后处理测试"""

    @pytest.fixture
    def service(self, mock_llm, mock_question_repo):
        pipeline = MagicMock(spec=RAGPipeline)
        return QAService(
            llm=mock_llm,
            rag_pipeline=pipeline,
            question_repo=mock_question_repo,
        )

    def test_post_process_empty_text(self, service):
        """测试空文本返回友好提示"""
        rag_result = MagicMock(category=QuestionCategory.GENERAL)
        result = service._post_process("", rag_result)
        assert "抱歉" in result

    def test_post_process_strips_think(self, service):
        """测试去除 think 标签"""
        rag_result = MagicMock(category=QuestionCategory.GENERAL)
        result = service._post_process("<think>思考</think>答案", rag_result)
        assert "think" not in result.lower() or "答案" in result

    def test_post_process_preserves_normal(self, service):
        """测试正常文本保持不变"""
        rag_result = MagicMock(category=QuestionCategory.GENERAL)
        result = service._post_process("这是正常答案", rag_result)
        assert result == "这是正常答案"


class TestQAServiceTemperature:
    """温度选择测试"""

    @pytest.fixture
    def service(self, mock_llm, mock_question_repo):
        pipeline = MagicMock(spec=RAGPipeline)
        return QAService(
            llm=mock_llm,
            rag_pipeline=pipeline,
            question_repo=mock_question_repo,
        )

    def test_operation_guide_temperature(self, service):
        """测试操作指南使用标准温度"""
        temp = service._get_temperature(QuestionCategory.OPERATION_GUIDE)
        assert temp == 0.3

    def test_process_inquiry_temperature(self, service):
        """测试流程咨询使用灵活温度"""
        temp = service._get_temperature(QuestionCategory.PROCESS_INQUIRY)
        assert temp == 0.7

    def test_anomaly_temperature(self, service):
        """测试异常排查使用灵活温度"""
        temp = service._get_temperature(QuestionCategory.ANOMALY_TROUBLESHOOT)
        assert temp == 0.7

    def test_general_temperature(self, service):
        """测试其他分类使用灵活温度"""
        temp = service._get_temperature(QuestionCategory.GENERAL)
        assert temp == 0.7

    def test_none_temperature(self, service):
        """测试 None 分类使用灵活温度"""
        temp = service._get_temperature(None)
        assert temp == 0.7
