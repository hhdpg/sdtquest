"""问题分类器模块。

本模块实现基于规则+关键词匹配的问题分类器，对用户问题进行自动分类。

分类类型:
- 操作指南 (operation_guide): 询问如何操作某个功能
- 流程咨询 (process_inquiry): 询问业务流程
- 异常排查 (anomaly_troubleshoot): 报告问题或异常
- 其他/闲聊 (general): 不属于以上类型

典型用法:
    >>> from src.analyzer.classifier import QuestionClassifier
    >>> classifier = QuestionClassifier()
    >>> category = await classifier.classify("如何创建订单?")
    >>> print(category)
    QuestionCategory.OPERATION_GUIDE
"""

import re
from typing import Protocol

from loguru import logger

from src.domain.enums import QuestionCategory


# ============================================================================
# 分类规则定义
# ============================================================================

# 分类关键词配置
CATEGORY_KEYWORDS: dict[QuestionCategory, list[str]] = {
    QuestionCategory.ANOMALY_TROUBLESHOOT: [
        # 异常/错误类关键词（优先级最高）
        "报错", "错误", "失败", "异常", "出问题", "出错了",
        "为什么", "怎么回事", "怎么办", "不行了", "不了",
        "打不开", "加载不了", "闪退", "卡住", "崩溃",
        "无法", "不能", "不可以", "出错", "故障",
    ],
    QuestionCategory.PROCESS_INQUIRY: [
        # 流程类关键词
        "流程", "审批", "步骤", "先后", "顺序",
        "整个", "完整", "全部过程", "怎么做", "处理流程",
        "业务流程", "操作流程", "工作流程",
    ],
    QuestionCategory.OPERATION_GUIDE: [
        # 操作类关键词（最常见）
        "怎么", "如何", "在哪里", "哪儿", "在哪",
        "操作", "使用", "怎么用", "如何使用",
        "教程", "方法", "步骤", "指南",
        "创建", "删除", "修改", "编辑", "添加", "新增",
        "查询", "搜索", "导出", "导入", "上传", "下载",
        "打开", "关闭", "设置", "配置",
    ],
}

# 闲聊/问候模式
GREETING_PATTERNS: list[str] = [
    r"^(你好|您好|hi|hello|嗨|hey)[!！。.？?]?$",
    r"^(谢谢|感谢|多谢|thx|thanks)[!！。.？?]?$",
    r"^(再见|拜拜|bye|goodbye)[!！。.？?]?$",
    r"^(嗯|哦|好的|收到|ok|OK)[!！。.？?]?$",
]


# ============================================================================
# ML 分类器接口（预留扩展）
# ============================================================================

class MLClassifier(Protocol):
    """
    机器学习分类器接口（预留扩展）。

    后续可以训练 SVM、TextCNN 等模型替换规则分类器。
    """

    async def predict(self, text: str) -> tuple[QuestionCategory, float]:
        """
        预测问题分类

        Args:
            text: 问题文本

        Returns:
            (分类结果, 置信度) 元组
        """
        ...


# ============================================================================
# 问题分类器
# ============================================================================

class QuestionClassifier:
    """
    问题分类器。

    基于规则+关键词匹配对用户问题进行分类。

    分类优先级:
    1. 闲聊/问候检测
    2. 异常排查（负面关键词优先）
    3. 流程咨询
    4. 操作指南
    5. 其他/默认

    Attributes:
        keywords: 分类关键词配置
        use_ml_fallback: 是否在规则匹配失败时使用 ML 分类器

    Example:
        >>> classifier = QuestionClassifier()
        >>> await classifier.classify("如何创建订单?")
        QuestionCategory.OPERATION_GUIDE
        >>> await classifier.classify("提交订单报错了")
        QuestionCategory.ANOMALY_TROUBLESHOOT
    """

    def __init__(
        self,
        keywords: dict[QuestionCategory, list[str]] | None = None,
        ml_classifier: MLClassifier | None = None,
    ):
        """
        初始化问题分类器。

        Args:
            keywords: 自定义关键词配置，默认使用内置配置
            ml_classifier: 可选的 ML 分类器（用于规则匹配失败时的兜底）
        """
        self.keywords = keywords or CATEGORY_KEYWORDS
        self.ml_classifier = ml_classifier

        logger.info(
            "QuestionClassifier 初始化 | categories={} | ml_fallback={}",
            len(self.keywords),
            ml_classifier is not None,
        )

    async def classify(
        self,
        question: str,
    ) -> QuestionCategory:
        """
        对问题进行分类。

        这是 Classifier Protocol 的实现方法，可直接注入 QAService。

        Args:
            question: 问题文本

        Returns:
            问题分类
        """
        if not question or not question.strip():
            return QuestionCategory.GENERAL

        question = question.strip()

        # 1. 检查是否为闲聊/问候
        if self._is_greeting(question):
            logger.debug("分类为闲聊 | question={}", question[:30])
            return QuestionCategory.GENERAL

        # 2. 规则匹配（按优先级顺序）
        # 优先级: 异常排查 > 流程咨询 > 操作指南
        priority_order = [
            QuestionCategory.ANOMALY_TROUBLESHOOT,
            QuestionCategory.PROCESS_INQUIRY,
            QuestionCategory.OPERATION_GUIDE,
        ]

        for category in priority_order:
            if self._match_keywords(question, category):
                logger.debug("规则匹配分类 | category={} | question={}", category.value, question[:30])
                return category

        # 3. ML 分类器兜底
        if self.ml_classifier is not None:
            try:
                category, confidence = await self.ml_classifier.predict(question)
                if confidence > 0.6:
                    logger.debug("ML 分类 | category={} | confidence={:.2f}", category.value, confidence)
                    return category
            except Exception as e:
                logger.warning("ML 分类失败，使用默认分类 | error={}", str(e))

        # 4. 默认分类
        logger.debug("默认分类 | question={}", question[:30])
        return QuestionCategory.GENERAL

    async def classify_with_confidence(
        self,
        question: str,
    ) -> tuple[QuestionCategory, float]:
        """
        对问题进行分类并返回置信度。

        Args:
            question: 问题文本

        Returns:
            (分类结果, 置信度) 元组，置信度范围 0.0-1.0
        """
        if not question or not question.strip():
            return QuestionCategory.GENERAL, 0.0

        question = question.strip()

        # 闲聊检测
        if self._is_greeting(question):
            return QuestionCategory.GENERAL, 1.0

        # 计算各分类的匹配分数
        scores: dict[QuestionCategory, float] = {}
        for category, keywords_list in self.keywords.items():
            score = self._calculate_score(question, keywords_list)
            scores[category] = score

        # 找到最高分
        if scores:
            best_category = max(scores, key=scores.get)  # type: ignore
            best_score = scores[best_category]

            if best_score > 0:
                # 归一化置信度
                total = sum(scores.values())
                confidence = best_score / total if total > 0 else 0.5
                return best_category, min(confidence, 1.0)

        # ML 兜底
        if self.ml_classifier is not None:
            try:
                return await self.ml_classifier.predict(question)
            except Exception:
                pass

        return QuestionCategory.GENERAL, 0.3

    def _is_greeting(self, text: str) -> bool:
        """
        检查是否为闲聊/问候。

        Args:
            text: 问题文本

        Returns:
            True 表示是闲聊
        """
        text_lower = text.lower().strip()

        for pattern in GREETING_PATTERNS:
            if re.match(pattern, text_lower):
                return True

        return False

    def _match_keywords(
        self,
        question: str,
        category: QuestionCategory,
    ) -> bool:
        """
        检查问题是否匹配指定分类的关键词。

        Args:
            question: 问题文本
            category: 目标分类

        Returns:
            True 表示匹配
        """
        keywords_list = self.keywords.get(category, [])
        question_lower = question.lower()

        for keyword in keywords_list:
            if keyword in question_lower:
                return True

        return False

    def _calculate_score(
        self,
        question: str,
        keywords_list: list[str],
    ) -> float:
        """
        计算问题与关键词列表的匹配分数。

        Args:
            question: 问题文本
            keywords_list: 关键词列表

        Returns:
            匹配分数（匹配关键词数量）
        """
        question_lower = question.lower()
        score = 0.0

        for keyword in keywords_list:
            if keyword in question_lower:
                # 关键词越长，权重越高
                score += len(keyword)

        return score


# ============================================================================
# 批量分类
# ============================================================================

async def classify_batch(
    questions: list[str],
    classifier: QuestionClassifier | None = None,
) -> list[QuestionCategory]:
    """
    批量分类问题。

    Args:
        questions: 问题列表
        classifier: 分类器实例，默认创建新的

    Returns:
        分类结果列表
    """
    if classifier is None:
        classifier = QuestionClassifier()

    results = []
    for question in questions:
        category = await classifier.classify(question)
        results.append(category)

    return results
