"""问题分析模块。

本模块提供问题分析与汇总功能，包括:
- 问题分类器（基于规则+关键词匹配）
- 问题汇总统计
- 报告生成

主要类:
- QuestionClassifier: 问题分类器
- QuestionSummarizer: 问题汇总器
- ReportGenerator: 报告生成器

典型用法:
    >>> from src.analyzer import QuestionClassifier, QuestionSummarizer, ReportGenerator
    >>> classifier = QuestionClassifier()
    >>> category = await classifier.classify("如何创建订单?")
"""

from src.analyzer.classifier import (
    CATEGORY_KEYWORDS,
    QuestionClassifier,
    classify_batch,
)
from src.analyzer.reporter import (
    ReportGenerator,
    generate_daily_report,
)
from src.analyzer.summarizer import (
    CategoryStats,
    QuestionSummarizer,
    SummaryResult,
)

__all__ = [
    # 分类器
    "QuestionClassifier",
    "CATEGORY_KEYWORDS",
    "classify_batch",
    # 汇总器
    "QuestionSummarizer",
    "SummaryResult",
    "CategoryStats",
    # 报告生成器
    "ReportGenerator",
    "generate_daily_report",
]
