"""领域异常定义模块

定义应用中的异常层级结构，便于统一错误处理。

异常层级:
    AppException (基类)
    ├── QuestionProcessingError (问答处理失败)
    ├── KnowledgeNotFoundError (知识未找到)
    ├── LLMServiceError (LLM 服务错误)
    ├── VectorStoreError (向量库错误)
    ├── DingTalkAPIError (钉钉 API 错误)
    └── ParserError (代码解析错误)
"""


class AppException(Exception):
    """
    应用基础异常类

    所有业务异常的基类，提供统一的错误码和消息格式。

    Attributes:
        message: 错误描述信息
        code: 错误码，用于前端展示和日志记录
    """
    code: str = "UNKNOWN_ERROR"

    def __init__(self, message: str, code: str | None = None):
        self.message = message
        if code:
            self.code = code
        super().__init__(message)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


# ============================================================================
# 业务异常
# ============================================================================

class QuestionProcessingError(AppException):
    """
    问题处理失败

    当问题处理过程中发生错误时抛出，如：
    - 问题文本为空或格式不正确
    - 问题分类失败
    - 上下文获取失败
    """
    code = "QA_PROCESSING_ERROR"


class KnowledgeNotFoundError(AppException):
    """
    知识库中未找到匹配内容

    当检索未能找到与问题相关的知识时抛出。
    这通常不是系统错误，而是知识库覆盖不足。
    """
    code = "KNOWLEDGE_NOT_FOUND"


# ============================================================================
# 基础设施异常
# ============================================================================

class LLMServiceError(AppException):
    """
    LLM 服务调用失败

    当调用大语言模型服务时发生错误，如：
    - Ollama 服务不可用
    - 模型未加载
    - 生成超时
    - 网络连接失败
    """
    code = "LLM_SERVICE_ERROR"


class VectorStoreError(AppException):
    """
    向量库操作失败

    当操作向量数据库时发生错误，如：
    - ChromaDB 连接失败
    - 向量写入失败
    - 检索操作失败
    """
    code = "VECTOR_STORE_ERROR"


class DingTalkAPIError(AppException):
    """
    钉钉 API 调用失败

    当调用钉钉开放平台 API 时发生错误，如：
    - 认证失败
    - 消息发送失败
    - 网络超时
    """
    code = "DINGTALK_API_ERROR"


class ParserError(AppException):
    """
    代码解析失败

    当解析前端代码时发生错误，如：
    - 文件不存在
    - 语法解析失败
    - 不支持的文件格式
    """
    code = "PARSER_ERROR"


# ============================================================================
# 配置异常
# ============================================================================

class ConfigurationError(AppException):
    """
    配置错误

    当配置项缺失或无效时抛出。
    """
    code = "CONFIGURATION_ERROR"
