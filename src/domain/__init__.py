"""Domain 层 — 领域模型、枚举、接口、异常定义

本模块定义了应用的核心领域概念，包括：
- 领域模型: Question, Answer, KnowledgeItem, Conversation, Message
- 枚举定义: QuestionCategory, KnowledgeType, AnswerStatus
- 端口接口: LLMClient, VectorStore, QuestionRepository, MessageSender
- 异常定义: AppException 及其子类

约束:
- 本模块不 import 任何其他 src/ 下的模块
- 纯 Python + Pydantic 实现
"""

# 枚举
from src.domain.enums import AnswerStatus, KnowledgeType, QuestionCategory

# 模型
from src.domain.models import (
    Answer,
    Conversation,
    KnowledgeItem,
    Message,
    Question,
)

# 端口接口
from src.domain.ports import (
    GenerateOptions,
    LLMClient,
    MessageSender,
    QuestionRepository,
    VectorStore,
)

# 异常
from src.domain.exceptions import (
    AppException,
    ConfigurationError,
    DingTalkAPIError,
    KnowledgeNotFoundError,
    LLMServiceError,
    ParserError,
    QuestionProcessingError,
    VectorStoreError,
)

__all__ = [
    # 枚举
    "QuestionCategory",
    "KnowledgeType",
    "AnswerStatus",
    # 模型
    "Question",
    "Answer",
    "KnowledgeItem",
    "Conversation",
    "Message",
    # 端口接口
    "GenerateOptions",
    "LLMClient",
    "VectorStore",
    "QuestionRepository",
    "MessageSender",
    # 异常
    "AppException",
    "QuestionProcessingError",
    "KnowledgeNotFoundError",
    "LLMServiceError",
    "VectorStoreError",
    "DingTalkAPIError",
    "ParserError",
    "ConfigurationError",
]
