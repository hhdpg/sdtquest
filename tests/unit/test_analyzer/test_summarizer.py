"""问题汇总器单元测试。

测试 QuestionSummarizer 的统计功能。
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock

from src.analyzer.summarizer import QuestionSummarizer, SummaryResult, CategoryStats
from src.domain.enums import AnswerStatus, QuestionCategory
from src.domain.models import Answer, Question


class TestQuestionSummarizer:
    """问题汇总器测试类"""

    @pytest.fixture
    def mock_repo(self):
        """创建模拟仓储"""
        repo = Mock()
        return repo

    @pytest.fixture
    def summarizer(self, mock_repo):
        """创建汇总器实例"""
        return QuestionSummarizer(question_repo=mock_repo)

    @pytest.fixture
    def sample_records(self):
        """创建测试数据"""
        records = []

        # 创建一些测试问答记录
        test_data = [
            ("如何创建订单?", QuestionCategory.OPERATION_GUIDE, AnswerStatus.SUCCESS, 0.85),
            ("系统报错了", QuestionCategory.ANOMALY_TROUBLESHOOT, AnswerStatus.SUCCESS, 0.75),
            ("审批流程", QuestionCategory.PROCESS_INQUIRY, AnswerStatus.NO_MATCH, 0.0),
            ("你好", QuestionCategory.GENERAL, AnswerStatus.SUCCESS, 0.6),
            ("如何删除用户?", QuestionCategory.OPERATION_GUIDE, AnswerStatus.SUCCESS, 0.9),
        ]

        for i, (text, category, status, confidence) in enumerate(test_data):
            question = Question(
                id=f"q_{i}",
                text=text,
                sender_id=f"user_{i % 2}",  # 2个用户
                conversation_id=f"conv_{i}",
                category=category,
                created_at=datetime.now(),
            )
            answer = Answer(
                id=f"a_{i}",
                question_id=f"q_{i}",
                text="回答内容",
                sources=[],
                confidence=confidence,
                category=category,
                status=status,
                created_at=datetime.now(),
            )
            records.append((question, answer))

        return records

    # ── 汇总测试 ──

    @pytest.mark.asyncio
    async def test_get_summary_empty(self, summarizer, mock_repo):
        """测试空数据的汇总"""
        mock_repo.find_recent.return_value = []

        result = await summarizer.get_summary(days=7)

        assert result.total == 0
        assert result.days == 7

    @pytest.mark.asyncio
    async def test_get_summary_with_data(self, summarizer, mock_repo, sample_records):
        """测试有数据的汇总"""
        mock_repo.find_recent.return_value = sample_records

        result = await summarizer.get_summary(days=7)

        assert result.total == 5
        assert result.days == 7
        assert result.active_users == 2  # user_0, user_1

        # 检查分类统计
        assert len(result.category_stats) > 0

        # 检查整体统计
        assert 0.0 <= result.avg_confidence <= 1.0
        assert 0.0 <= result.success_rate <= 1.0

    @pytest.mark.asyncio
    async def test_get_summary_category_counts(self, summarizer, mock_repo, sample_records):
        """测试分类数量统计"""
        mock_repo.find_recent.return_value = sample_records

        result = await summarizer.get_summary(days=7)

        # 找到操作指南的统计
        operation_stats = next(
            (s for s in result.category_stats if s.category == QuestionCategory.OPERATION_GUIDE),
            None
        )

        assert operation_stats is not None
        assert operation_stats.count == 2  # 2个操作指南问题

    @pytest.mark.asyncio
    async def test_summary_to_dict(self, summarizer, mock_repo, sample_records):
        """测试汇总结果转字典"""
        mock_repo.find_recent.return_value = sample_records

        result = await summarizer.get_summary(days=7)
        data = result.to_dict()

        assert "total" in data
        assert "days" in data
        assert "by_category" in data
        assert "avg_confidence" in data
        assert "success_rate" in data
        assert "active_users" in data

    # ── 高频问题测试 ──

    @pytest.mark.asyncio
    async def test_get_top_questions(self, summarizer, mock_repo):
        """测试获取高频问题"""
        mock_repo.get_top_questions.return_value = [
            ("如何创建订单?", 10),
            ("怎么删除用户?", 5),
            ("导出报表", 3),
        ]

        results = await summarizer.get_top_questions(days=7, limit=10)

        assert len(results) == 3
        assert results[0]["question"] == "如何创建订单?"
        assert results[0]["count"] == 10
        assert results[0]["rank"] == 1

    @pytest.mark.asyncio
    async def test_get_top_questions_min_count(self, summarizer, mock_repo):
        """测试最小出现次数过滤"""
        mock_repo.get_top_questions.return_value = [
            ("高频问题", 10),
            ("低频问题", 1),
        ]

        results = await summarizer.get_top_questions(days=7, min_count=2)

        assert len(results) == 1
        assert results[0]["question"] == "高频问题"

    # ── 未回答问题测试 ──

    @pytest.mark.asyncio
    async def test_get_unanswered(self, summarizer, mock_repo):
        """测试获取未回答问题"""
        unanswered_questions = [
            Question(
                id="q_1",
                text="知识库没有的问题",
                sender_id="user_1",
                conversation_id="conv_1",
                created_at=datetime.now(),
            ),
        ]
        mock_repo.find_unanswered.return_value = unanswered_questions

        results = await summarizer.get_unanswered(days=7)

        assert len(results) == 1
        assert results[0]["text"] == "知识库没有的问题"

    # ── 活跃用户测试 ──

    @pytest.mark.asyncio
    async def test_get_active_users(self, summarizer, mock_repo, sample_records):
        """测试获取活跃用户"""
        mock_repo.find_recent.return_value = sample_records

        results = await summarizer.get_active_users(days=7)

        assert len(results) > 0
        # 检查是否按提问次数排序
        if len(results) > 1:
            assert results[0]["question_count"] >= results[1]["question_count"]

    # ── 趋势测试 ──

    @pytest.mark.asyncio
    async def test_get_trend(self, summarizer, mock_repo, sample_records):
        """测试获取问题趋势"""
        mock_repo.find_recent.return_value = sample_records

        results = await summarizer.get_trend(days=7)

        assert len(results) == 7
        # 检查日期格式
        for item in results:
            assert "date" in item
            assert "count" in item


class TestCategoryStats:
    """分类统计测试类"""

    def test_to_dict(self):
        """测试转字典"""
        stats = CategoryStats(
            category=QuestionCategory.OPERATION_GUIDE,
            count=10,
            percentage=0.5,
            avg_confidence=0.8,
            success_rate=0.9,
        )

        data = stats.to_dict()

        assert data["category"] == "operation_guide"
        assert data["category_name"] == "操作指南"
        assert data["count"] == 10
        assert data["percentage"] == 0.5
        assert data["avg_confidence"] == 0.8
        assert data["success_rate"] == 0.9

    def test_category_name(self):
        """测试分类中文名"""
        stats = CategoryStats(category=QuestionCategory.OPERATION_GUIDE)
        assert stats.category_name == "操作指南"

        stats = CategoryStats(category=QuestionCategory.ANOMALY_TROUBLESHOOT)
        assert stats.category_name == "异常排查"


class TestSummaryResult:
    """汇总结果测试类"""

    def test_to_dict(self):
        """测试转字典"""
        result = SummaryResult(
            total=100,
            days=7,
            avg_confidence=0.8,
            success_rate=0.9,
            active_users=10,
        )

        data = result.to_dict()

        assert data["total"] == 100
        assert data["days"] == 7
        assert "start_date" in data
        assert "end_date" in data
        assert data["avg_confidence"] == 0.8
        assert data["success_rate"] == 0.9
        assert data["active_users"] == 10
