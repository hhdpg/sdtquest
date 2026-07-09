"""全局常量定义模块。

定义跨模块共享的常量值，避免魔法数字和硬编码字符串。

包括:
- 应用元信息
- 默认值
- 正则表达式
- 提示文案
"""

# ============================================================================
# 应用元信息
# ============================================================================

APP_NAME: str = "dingtalk-qa-bot"
APP_VERSION: str = "0.1.0"
APP_DESCRIPTION: str = "钉钉智能问答机器人 — 基于本地大模型的 RAG 问答系统"


# ============================================================================
# 默认值
# ============================================================================

# 问答相关
DEFAULT_MAX_QUESTION_LENGTH: int = 2000
DEFAULT_TOP_K: int = 5
DEFAULT_CONFIDENCE: float = 0.0

# 检索相关
DEFAULT_RAG_THRESHOLD_STANDARD: float = 0.8
DEFAULT_RAG_THRESHOLD_FLEXIBLE: float = 0.6
DEFAULT_RRF_K: int = 60

# 会话相关
DEFAULT_MAX_HISTORY: int = 10
DEFAULT_SESSION_TTL_SECONDS: int = 300  # 5 分钟
DEFAULT_MAX_SESSIONS: int = 1000

# 限流相关
DEFAULT_RATE_LIMIT_SECONDS: int = 60

# LLM 相关
DEFAULT_LLM_TEMPERATURE_STANDARD: float = 0.3
DEFAULT_LLM_TEMPERATURE_FLEXIBLE: float = 0.7
DEFAULT_LLM_MAX_TOKENS: int = 2048
DEFAULT_LLM_CONTEXT_WINDOW: int = 8192
DEFAULT_LLM_TIMEOUT_SECONDS: int = 120
DEFAULT_LLM_MAX_CONCURRENT: int = 2

# 分块相关
DEFAULT_CHUNK_SIZE: int = 3000

# 消息去重
MAX_PROCESSED_MESSAGE_IDS: int = 1000

# 日志相关
MAX_LOG_TEXT_LENGTH: int = 50  # 日志中截断文本的长度


# ============================================================================
# 提示文案
# ============================================================================

# 即时反馈消息
THINKING_HINT_MESSAGE: str = "🤔 正在为您查找答案，请稍候..."

# 限流提示
RATE_LIMIT_MESSAGE: str = "⏱️ 您的提问过于频繁，请 {seconds} 秒后再试。"

# 错误提示
ERROR_MESSAGE_SERVICE_BUSY: str = "⚠️ 服务繁忙，请稍后再试。"
ERROR_MESSAGE_CONTACT_ADMIN: str = "⚠️ 暂时无法回答您的问题，请联系管理员。"
ERROR_MESSAGE_TIMEOUT: str = "⚠️ 回答超时，请稍后再试。"

# 未匹配知识时的友好提示
NO_MATCH_MESSAGE: str = (
    "抱歉，当前知识库中未找到与您问题相关的内容。\n\n"
    "您可以尝试:\n"
    "- 使用更具体的关键词描述问题\n"
    "- 提供页面名称或功能模块信息\n"
    "- 联系管理员补充相关知识"
)

# 免责声明
DISCLAIMER_MESSAGE: str = "\n\n> 💡 如有疑问请以实际系统操作为准。"

# 钉钉凭证未配置提示
DINGTALK_CREDENTIALS_MISSING_MESSAGE: str = (
    "钉钉应用凭证未配置，请设置 DINGTALK_APP_KEY 和 DINGTALK_APP_SECRET"
)


# ============================================================================
# 问题分类关键词（用于初始分类器）
# ============================================================================

QUESTION_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "operation_guide": [
        "怎么", "如何", "在哪里", "操作", "使用",
        "创建", "删除", "修改", "编辑", "添加", "查询",
        "导出", "导入", "上传", "下载", "打开", "设置",
    ],
    "process_inquiry": [
        "流程", "审批", "步骤", "先后", "顺序",
        "整个", "完整", "全部过程", "业务流程",
    ],
    "anomaly_troubleshoot": [
        "报错", "错误", "失败", "异常", "为什么",
        "怎么办", "打不开", "加载不了", "无法", "不能",
    ],
}


# ============================================================================
# bge-m3 Embedding 相关
# ============================================================================

# bge-m3 查询时的 instruction prefix
BGE_M3_QUERY_INSTRUCTION: str = (
    "Represent this sentence for searching relevant passages: "
)
BGE_M3_VECTOR_DIMENSION: int = 1024
BGE_M3_MAX_INPUT_TOKENS: int = 8192


# ============================================================================
# 钉钉 API 相关
# ============================================================================

DINGTALK_API_BASE_URL: str = "https://oapi.dingtalk.com"
DINGTALK_NEW_API_BASE_URL: str = "https://api.dingtalk.com"
DINGTALK_TOKEN_REFRESH_BUFFER_SECONDS: int = 300  # 提前 5 分钟刷新


# ============================================================================
# 日报/报告相关
# ============================================================================

REPORT_TITLE_DAILY: str = "智能问答日报"
REPORT_TITLE_WEEKLY: str = "智能问答周报"
REPORT_TOP_QUESTIONS_LIMIT: int = 10
REPORT_UNANSWERED_LIMIT: int = 10

# 改进建议阈值
REPORT_SUGGEST_SUCCESS_RATE_THRESHOLD: float = 0.8
REPORT_SUGGEST_UNANSWERED_THRESHOLD: int = 5
REPORT_SUGGEST_CONFIDENCE_THRESHOLD: float = 0.6
REPORT_SUGGEST_HIGH_FREQUENCY_THRESHOLD: int = 5
