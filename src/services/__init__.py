"""业务服务层模块。

本模块提供应用层的核心业务服务，编排底层模块完成完整的业务用例。

主要服务:
- QAService: 问答服务，编排 RAG 检索 + LLM 生成 + 日志记录
- KnowledgeService: 知识库管理服务，支持代码构建和文档导入
- AnalyticsService: 分析汇总服务，统计分析和日报生成

服务异常:
- QAServiceError: 问答服务异常
- KnowledgeBuildError: 知识库构建异常
- DailyReportError: 日报生成异常

典型用法:
    >>> from src.services import QAService, KnowledgeService, AnalyticsService
"""

from src.services.analytics_service import AnalyticsService, DailyReportError
from src.services.knowledge_service import KnowledgeBuildError, KnowledgeService
from src.services.qa_service import QAService, QAServiceError

__all__ = [
    "QAService",
    "QAServiceError",
    "KnowledgeService",
    "KnowledgeBuildError",
    "AnalyticsService",
    "DailyReportError",
]
