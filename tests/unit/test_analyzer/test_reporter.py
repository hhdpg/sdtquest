"""报告生成器单元测试。

测试 ReportGenerator 的报告生成功能。
"""

import pytest
from unittest.mock import Mock, AsyncMock

from src.analyzer.reporter import ReportGenerator, generate_daily_report
from src.analyzer.summarizer import QuestionSummarizer, SummaryResult, CategoryStats
from src.domain.enums import QuestionCategory


class TestReportGenerator:
    """报告生成器测试类"""

    @pytest.fixture
    def mock_summarizer(self):
        """创建模拟汇总器"""
        summarizer = Mock(spec=QuestionSummarizer)
        return summarizer

    @pytest.fixture
    def reporter(self, mock_summarizer):
        """创建报告生成器实例"""
        return ReportGenerator(summarizer=mock_summarizer)

    @pytest.fixture
    def sample_summary(self):
        """创建测试汇总数据"""
        return SummaryResult(
            total=100,
            days=7,
            category_stats=[
                CategoryStats(
                    category=QuestionCategory.OPERATION_GUIDE,
                    count=50,
                    percentage=0.5,
                    avg_confidence=0.85,
                    success_rate=0.95,
                ),
                CategoryStats(
                    category=QuestionCategory.ANOMALY_TROUBLESHOOT,
                    count=30,
                    percentage=0.3,
                    avg_confidence=0.7,
                    success_rate=0.8,
                ),
            ],
            avg_confidence=0.8,
            success_rate=0.9,
            active_users=15,
        )

    # ── 日报生成测试 ──

    @pytest.mark.asyncio
    async def test_generate_daily_report(self, reporter, mock_summarizer, sample_summary):
        """测试生成日报"""
        mock_summarizer.get_summary.return_value = sample_summary
        mock_summarizer.get_top_questions.return_value = [
            {"question": "如何创建订单?", "count": 10, "rank": 1},
            {"question": "怎么删除用户?", "count": 5, "rank": 2},
        ]
        mock_summarizer.get_unanswered.return_value = [
            {"text": "知识库没有的问题", "id": "q1"},
        ]

        report = await reporter.generate_daily_report(days=1)

        # 检查报告内容
        assert "智能问答日报" in report
        assert "100" in report  # 总问题数
        assert "操作指南" in report
        assert "如何创建订单" in report
        assert "知识库盲区" in report

    @pytest.mark.asyncio
    async def test_generate_weekly_report(self, reporter, mock_summarizer, sample_summary):
        """测试生成周报"""
        mock_summarizer.get_summary.return_value = sample_summary
        mock_summarizer.get_top_questions.return_value = []
        mock_summarizer.get_unanswered.return_value = []

        report = await reporter.generate_weekly_report()

        assert "周报" in report
        assert "近 7 天" in report

    @pytest.mark.asyncio
    async def test_generate_report_empty_data(self, reporter, mock_summarizer):
        """测试空数据生成报告"""
        empty_summary = SummaryResult(total=0, days=7)
        mock_summarizer.get_summary.return_value = empty_summary
        mock_summarizer.get_top_questions.return_value = []
        mock_summarizer.get_unanswered.return_value = []

        report = await reporter.generate_daily_report(days=7)

        assert "暂无数据" in report or "总问题数" in report

    @pytest.mark.asyncio
    async def test_generate_report_error_handling(self, reporter, mock_summarizer):
        """测试报告生成错误处理"""
        mock_summarizer.get_summary.side_effect = Exception("数据库错误")

        report = await reporter.generate_daily_report(days=1)

        assert "报告生成失败" in report
        assert "数据库错误" in report

    # ── 报告内容格式测试 ──

    @pytest.mark.asyncio
    async def test_report_contains_overview(self, reporter, mock_summarizer, sample_summary):
        """测试报告包含概览部分"""
        mock_summarizer.get_summary.return_value = sample_summary
        mock_summarizer.get_top_questions.return_value = []
        mock_summarizer.get_unanswered.return_value = []

        report = await reporter.generate_daily_report()

        assert "概览" in report
        assert "问题总数" in report
        assert "活跃用户" in report
        assert "平均置信度" in report
        assert "成功回答率" in report

    @pytest.mark.asyncio
    async def test_report_contains_category_stats(self, reporter, mock_summarizer, sample_summary):
        """测试报告包含分类统计"""
        mock_summarizer.get_summary.return_value = sample_summary
        mock_summarizer.get_top_questions.return_value = []
        mock_summarizer.get_unanswered.return_value = []

        report = await reporter.generate_daily_report()

        assert "问题分类统计" in report
        assert "操作指南" in report
        assert "异常排查" in report

    @pytest.mark.asyncio
    async def test_report_contains_suggestions(self, reporter, mock_summarizer):
        """测试报告包含改进建议"""
        # 创建一个成功率低的汇总数据
        low_success_summary = SummaryResult(
            total=100,
            days=7,
            avg_confidence=0.5,
            success_rate=0.6,  # 低于 80%
            active_users=10,
        )
        mock_summarizer.get_summary.return_value = low_success_summary
        mock_summarizer.get_top_questions.return_value = []
        mock_summarizer.get_unanswered.return_value = []

        report = await reporter.generate_daily_report()

        assert "改进建议" in report

    # ── 钉钉推送测试 ──

    @pytest.mark.asyncio
    async def test_push_to_dingtalk_without_client(self, reporter):
        """测试没有钉钉客户端时推送"""
        result = await reporter.push_to_dingtalk(
            report="测试报告",
            conversation_id="conv_123",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_push_to_dingtalk_success(self, mock_summarizer):
        """测试钉钉推送成功"""
        mock_client = Mock()
        mock_client.send_markdown = AsyncMock(return_value=True)

        reporter = ReportGenerator(
            summarizer=mock_summarizer,
            dingtalk_client=mock_client,
        )

        result = await reporter.push_to_dingtalk(
            report="测试报告",
            conversation_id="conv_123",
            title="日报",
        )

        assert result is True
        mock_client.send_markdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_push_to_dingtalk_error(self, mock_summarizer):
        """测试钉钉推送失败"""
        mock_client = Mock()
        mock_client.send_markdown = AsyncMock(side_effect=Exception("网络错误"))

        reporter = ReportGenerator(
            summarizer=mock_summarizer,
            dingtalk_client=mock_client,
        )

        result = await reporter.push_to_dingtalk(
            report="测试报告",
            conversation_id="conv_123",
        )

        assert result is False

    # ── 便捷函数测试 ──

    @pytest.mark.asyncio
    async def test_generate_daily_report_function(self, mock_summarizer, sample_summary):
        """测试便捷函数"""
        mock_summarizer.get_summary.return_value = sample_summary
        mock_summarizer.get_top_questions.return_value = []
        mock_summarizer.get_unanswered.return_value = []

        report = await generate_daily_report(summarizer=mock_summarizer, days=1)

        assert "智能问答" in report


class TestReportGeneratorSuggestions:
    """报告建议生成测试"""

    @pytest.fixture
    def mock_summarizer(self):
        return Mock(spec=QuestionSummarizer)

    @pytest.fixture
    def reporter(self, mock_summarizer):
        return ReportGenerator(summarizer=mock_summarizer)

    @pytest.mark.asyncio
    async def test_suggestion_low_success_rate(self, reporter, mock_summarizer):
        """测试低成功率建议"""
        summary = SummaryResult(
            total=100,
            days=7,
            success_rate=0.6,  # 低于 80%
        )
        mock_summarizer.get_summary.return_value = summary
        mock_summarizer.get_top_questions.return_value = []
        mock_summarizer.get_unanswered.return_value = []

        report = await reporter.generate_daily_report()

        assert "扩充知识库" in report or "提高回答准确率" in report

    @pytest.mark.asyncio
    async def test_suggestion_many_unanswered(self, reporter, mock_summarizer):
        """测试多未回答问题建议"""
        summary = SummaryResult(total=100, days=7)
        mock_summarizer.get_summary.return_value = summary
        mock_summarizer.get_top_questions.return_value = []
        mock_summarizer.get_unanswered.return_value = [
            {"text": f"问题{i}"} for i in range(10)
        ]

        report = await reporter.generate_daily_report()

        assert "补充相关知识" in report or "未成功回答" in report

    @pytest.mark.asyncio
    async def test_suggestion_high_frequency_question(self, reporter, mock_summarizer):
        """测试高频问题建议"""
        summary = SummaryResult(total=100, days=7)
        mock_summarizer.get_summary.return_value = summary
        mock_summarizer.get_top_questions.return_value = [
            {"question": "如何创建订单?", "count": 10, "rank": 1},
        ]
        mock_summarizer.get_unanswered.return_value = []

        report = await reporter.generate_daily_report()

        assert "高频问题" in report or "整理为文档" in report
