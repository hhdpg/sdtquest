"""问答管道集成测试模块。

测试完整 RAG + LLM 问答流程的端到端行为（mock Ollama）。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.domain.enums import AnswerStatus, KnowledgeType, QuestionCategory
from src.domain.models import Answer, KnowledgeItem, Message, Question
from src.domain.ports import GenerateOptions


class TestQAPipelineIntegration:
    """完整问答管道集成测试"""

    @pytest.mark.asyncio
    async def test_full_qa_flow(self):
        """测试完整问答流程（mock LLM 和 VectorStore）"""
        from src.services.qa_service import QAService
        from src.rag.pipeline import RAGPipeline, RAGResult
        from src.rag.context import ContextAssembler
        from unittest.mock import MagicMock

        # Mock LLM
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value="点击订单管理页面的「新建订单」按钮即可。")

        # Mock RAG Pipeline
        knowledge = [
            KnowledgeItem(
                id="k1",
                type=KnowledgeType.BUTTON,
                title="新建订单",
                content="在订单管理页面点击「新建订单」按钮。",
                page_name="订单管理",
                page_path="/order",
            ),
        ]
        rag_result = RAGResult(
            question=MagicMock(),
            prompt="组装好的 prompt",
            documents=knowledge,
            sources=["订单管理 - 新建订单"],
            category=QuestionCategory.OPERATION_GUIDE,
        )
        mock_pipeline = MagicMock(spec=RAGPipeline)
        mock_pipeline.query = AsyncMock(return_value=rag_result)

        # Mock Repo
        mock_repo = MagicMock()
        mock_repo.save = MagicMock()

        # Mock Classifier
        mock_classifier = AsyncMock()
        mock_classifier.classify = AsyncMock(return_value=QuestionCategory.OPERATION_GUIDE)

        # 组装服务
        service = QAService(
            llm=mock_llm,
            rag_pipeline=mock_pipeline,
            question_repo=mock_repo,
            classifier=mock_classifier,
        )

        # 执行完整流程
        answer = await service.ask(
            question_text="如何创建订单?",
            conversation_id="conv_integration_test",
            sender_id="user_integration",
        )

        # 验证
        assert isinstance(answer, Answer)
        assert answer.status == AnswerStatus.SUCCESS
        assert "新建订单" in answer.text
        assert answer.category == QuestionCategory.OPERATION_GUIDE
        assert answer.confidence > 0
        assert answer.sources == ["订单管理 - 新建订单"]

        # 验证依赖调用
        mock_classifier.classify.assert_called_once()
        mock_pipeline.query.assert_called_once()
        mock_llm.generate.assert_called_once()
        mock_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_qa_flow_with_unknown_question(self):
        """测试知识库外问题的处理"""
        from src.services.qa_service import QAService
        from src.rag.pipeline import RAGPipeline, RAGResult
        from unittest.mock import MagicMock

        mock_llm = AsyncMock()
        mock_pipeline = MagicMock(spec=RAGPipeline)
        # RAG 返回空文档
        rag_result = RAGResult(
            question=MagicMock(),
            prompt="",
            documents=[],
            sources=[],
            category=QuestionCategory.GENERAL,
        )
        mock_pipeline.query = AsyncMock(return_value=rag_result)

        mock_repo = MagicMock()
        mock_repo.save = MagicMock()

        service = QAService(
            llm=mock_llm,
            rag_pipeline=mock_pipeline,
            question_repo=mock_repo,
        )

        answer = await service.ask("未知问题", "conv_1")

        # 应该返回 NO_MATCH 状态
        assert answer.status == AnswerStatus.NO_MATCH
        assert "未找到" in answer.text or "抱歉" in answer.text

    @pytest.mark.asyncio
    async def test_qa_flow_with_llm_failure(self):
        """测试 LLM 故障时的容错"""
        from src.services.qa_service import QAService
        from src.rag.pipeline import RAGPipeline, RAGResult
        from src.domain.exceptions import LLMServiceError
        from unittest.mock import MagicMock

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(side_effect=LLMServiceError("Ollama 服务挂了"))

        knowledge = [KnowledgeItem(
            id="k1", type=KnowledgeType.BUTTON,
            title="T", content="C",
        )]
        rag_result = RAGResult(
            question=MagicMock(),
            prompt="test",
            documents=knowledge,
            sources=["T"],
            category=QuestionCategory.GENERAL,
        )
        mock_pipeline = MagicMock(spec=RAGPipeline)
        mock_pipeline.query = AsyncMock(return_value=rag_result)

        mock_repo = MagicMock()
        mock_repo.save = MagicMock()

        service = QAService(
            llm=mock_llm,
            rag_pipeline=mock_pipeline,
            question_repo=mock_repo,
        )

        answer = await service.ask("问题", "conv_1")

        # 应该返回 ERROR 状态而不是抛出异常
        assert answer.status == AnswerStatus.ERROR
        # 应该仍然记录了问答日志
        mock_repo.save.assert_called_once()


class TestAnalyticsIntegration:
    """分析汇总集成测试"""

    @pytest.mark.asyncio
    async def test_full_analytics_flow(self, tmp_path):
        """测试完整分析流程（真实 SQLite）"""
        from src.infrastructure.database import DatabaseManager
        from src.infrastructure.repositories.question_repo import SQLiteQuestionRepository
        from src.services.analytics_service import AnalyticsService
        from src.domain.enums import AnswerStatus, QuestionCategory
        from src.domain.models import Answer, Question

        # 设置真实数据库
        db_path = str(tmp_path / "analytics.db")
        DatabaseManager.reset()
        db = DatabaseManager(db_path=db_path)
        db.initialize_tables()
        repo = SQLiteQuestionRepository(db_manager=db)

        # 插入测试数据
        for i in range(5):
            q = Question(
                id=f"q{i}",
                text=f"问题 {i}",
                sender_id="user_1",
                conversation_id="conv_1",
                category=QuestionCategory.OPERATION_GUIDE,
            )
            a = Answer(
                id=f"q{i}",
                question_id=f"q{i}",
                text=f"答案 {i}",
                confidence=0.8,
                category=QuestionCategory.OPERATION_GUIDE,
                status=AnswerStatus.SUCCESS,
            )
            repo.save(q, a)

        # 测试 AnalyticsService
        service = AnalyticsService(question_repo=repo)

        # 获取统计
        summary = await service.get_summary(days=7)
        assert summary["total"] == 5
        assert summary["avg_confidence"] > 0
        assert summary["success_rate"] == 1.0

        # 获取高频问题
        top = await service.get_top_questions(days=7, limit=5)
        # 每个问题只出现 1 次，min_count 默认为 2，所以为空
        # 这里验证方法不抛出异常即可

        # 生成日报
        report = await service.generate_daily_report(days=1)
        assert "智能问答" in report
        assert "操作指南" in report or "统计" in report

        # 保存汇总
        await service.save_daily_summary(days=1)

        DatabaseManager.reset()


class TestKnowledgeServiceIntegration:
    """知识库服务集成测试"""

    @pytest.mark.asyncio
    async def test_import_document(self, tmp_path):
        """测试文档导入流程"""
        from unittest.mock import MagicMock, AsyncMock
        from src.services.knowledge_service import KnowledgeService
        from src.domain.enums import KnowledgeType

        # 创建测试文件
        test_file = tmp_path / "test.md"
        test_file.write_text(
            "# 测试文档\n\n"
            "这是测试文档内容。\n\n"
            "## 章节一\n\n"
            "更多内容。"
        )

        # Mock 依赖
        mock_vectorstore = AsyncMock()
        mock_vectorstore.add = AsyncMock()
        mock_vectorstore.count = AsyncMock(return_value=1)

        mock_llm = AsyncMock()
        mock_repo = MagicMock()
        mock_repo.save = MagicMock()
        mock_repo.find_all = MagicMock(return_value=[])

        service = KnowledgeService(
            vectorstore=mock_vectorstore,
            llm=mock_llm,
            knowledge_repo=mock_repo,
        )

        # 导入文件（不使用 LLM 丰富，避免依赖真实 LLM）
        items = await service.import_from_file(str(test_file), enrich=False)

        assert len(items) >= 1
        mock_vectorstore.add.assert_called()

    @pytest.mark.asyncio
    async def test_get_stats(self, tmp_path):
        """测试知识库统计"""
        from unittest.mock import MagicMock, AsyncMock
        from src.services.knowledge_service import KnowledgeService

        mock_vectorstore = AsyncMock()
        mock_vectorstore.count = AsyncMock(return_value=42)

        mock_repo = MagicMock()
        mock_repo.get_stats = MagicMock(return_value={
            "total": 42,
            "by_type": {"button": 20, "page": 10, "form": 12},
            "page_count": 5,
        })

        service = KnowledgeService(
            vectorstore=mock_vectorstore,
            knowledge_repo=mock_repo,
        )

        stats = await service.get_stats()
        assert stats["total"] == 42
        assert stats["vector_count"] == 42
        assert stats["page_count"] == 5
