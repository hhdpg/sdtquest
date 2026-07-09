"""问题分类器单元测试。

测试 QuestionClassifier 的分类功能。
"""

import pytest

from src.analyzer.classifier import QuestionClassifier, classify_batch
from src.domain.enums import QuestionCategory


class TestQuestionClassifier:
    """问题分类器测试类"""

    @pytest.fixture
    def classifier(self):
        """创建分类器实例"""
        return QuestionClassifier()

    # ── 操作指南分类测试 ──

    @pytest.mark.asyncio
    async def test_classify_operation_guide_basic(self, classifier):
        """测试基本操作指南分类"""
        questions = [
            "如何创建订单?",
            "怎么删除用户?",
            "在哪里导出报表?",
            "订单怎么查询?",
        ]

        for question in questions:
            result = await classifier.classify(question)
            assert result == QuestionCategory.OPERATION_GUIDE, \
                f"问题 '{question}' 应分类为 operation_guide，实际为 {result.value}"

    @pytest.mark.asyncio
    async def test_classify_operation_guide_actions(self, classifier):
        """测试操作类关键词"""
        questions = [
            "创建新订单",
            "删除这条记录",
            "修改用户信息",
            "导出数据",
            "上传文件",
        ]

        for question in questions:
            result = await classifier.classify(question)
            assert result == QuestionCategory.OPERATION_GUIDE, \
                f"问题 '{question}' 应分类为 operation_guide"

    # ── 异常排查分类测试 ──

    @pytest.mark.asyncio
    async def test_classify_anomaly_troubleshoot(self, classifier):
        """测试异常排查分类"""
        questions = [
            "提交订单报错了",
            "页面加载失败",
            "为什么不能登录?",
            "系统出问题了",
            "打不开这个页面",
        ]

        for question in questions:
            result = await classifier.classify(question)
            assert result == QuestionCategory.ANOMALY_TROUBLESHOOT, \
                f"问题 '{question}' 应分类为 anomaly_troubleshoot，实际为 {result.value}"

    @pytest.mark.asyncio
    async def test_classify_anomaly_priority(self, classifier):
        """测试异常排查优先级高于操作指南"""
        # 同时包含操作和异常关键词，应优先分类为异常
        question = "如何创建订单?但是报错了"
        result = await classifier.classify(question)
        assert result == QuestionCategory.ANOMALY_TROUBLESHOOT

    # ── 流程咨询分类测试 ──

    @pytest.mark.asyncio
    async def test_classify_process_inquiry(self, classifier):
        """测试流程咨询分类"""
        questions = [
            "审批流程是怎样的?",
            "整个业务流程是什么?",
            "采购流程步骤",
            "工作流程说明",
        ]

        for question in questions:
            result = await classifier.classify(question)
            assert result == QuestionCategory.PROCESS_INQUIRY, \
                f"问题 '{question}' 应分类为 process_inquiry，实际为 {result.value}"

    # ── 闲聊分类测试 ──

    @pytest.mark.asyncio
    async def test_classify_greeting(self, classifier):
        """测试闲聊/问候分类"""
        questions = [
            "你好",
            "谢谢",
            "再见",
            "好的",
            "Hi",
            "Thanks",
        ]

        for question in questions:
            result = await classifier.classify(question)
            assert result == QuestionCategory.GENERAL, \
                f"问题 '{question}' 应分类为 general"

    # ── 边界情况测试 ──

    @pytest.mark.asyncio
    async def test_classify_empty_question(self, classifier):
        """测试空问题"""
        result = await classifier.classify("")
        assert result == QuestionCategory.GENERAL

    @pytest.mark.asyncio
    async def test_classify_whitespace_question(self, classifier):
        """测试空白问题"""
        result = await classifier.classify("   ")
        assert result == QuestionCategory.GENERAL

    @pytest.mark.asyncio
    async def test_classify_unknown_question(self, classifier):
        """测试无法分类的问题"""
        # 没有明显关键词的问题应该分类为 general
        # 注意：包含"怎么"会被分类为 operation_guide，所以选择不含任何关键词的句子
        questions = [
            "今天天气不错",
            "这是一段测试文本",
            "随机内容而已",
        ]

        for question in questions:
            result = await classifier.classify(question)
            assert result == QuestionCategory.GENERAL, \
                f"问题 '{question}' 应分类为 general，实际为 {result.value}"

    # ── 带置信度分类测试 ──

    @pytest.mark.asyncio
    async def test_classify_with_confidence(self, classifier):
        """测试带置信度的分类"""
        question = "如何创建订单?"
        category, confidence = await classifier.classify_with_confidence(question)

        assert category == QuestionCategory.OPERATION_GUIDE
        assert 0.0 <= confidence <= 1.0

    @pytest.mark.asyncio
    async def test_classify_with_confidence_empty(self, classifier):
        """测试空问题的置信度"""
        category, confidence = await classifier.classify_with_confidence("")
        assert category == QuestionCategory.GENERAL
        assert confidence == 0.0

    # ── 批量分类测试 ──

    @pytest.mark.asyncio
    async def test_classify_batch(self):
        """测试批量分类"""
        questions = [
            "如何创建订单?",
            "系统报错了",
            "你好",
        ]

        results = await classify_batch(questions)

        assert len(results) == 3
        assert results[0] == QuestionCategory.OPERATION_GUIDE
        assert results[1] == QuestionCategory.ANOMALY_TROUBLESHOOT
        assert results[2] == QuestionCategory.GENERAL


class TestQuestionClassifierCustomKeywords:
    """自定义关键词配置测试"""

    @pytest.mark.asyncio
    async def test_custom_keywords(self):
        """测试自定义关键词"""
        custom_keywords = {
            QuestionCategory.OPERATION_GUIDE: ["自定义操作词"],
        }

        classifier = QuestionClassifier(keywords=custom_keywords)

        # 使用自定义关键词
        result = await classifier.classify("使用自定义操作词")
        assert result == QuestionCategory.OPERATION_GUIDE
