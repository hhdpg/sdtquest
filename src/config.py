from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """全局配置类,使用 Pydantic Settings 从环境变量和 .env 文件加载配置"""

    # ── 应用 ──
    APP_NAME: str = "dingtalk-qa-bot"
    APP_ENV: str = "development"            # development / production
    LOG_LEVEL: str = "INFO"

    # ── 钉钉 ──
    DINGTALK_APP_KEY: str = ""
    DINGTALK_APP_SECRET: str = ""
    DINGTALK_BOT_CODE: str = ""

    # ── Ollama ──
    # 注: Ollama 仅支持 GGUF 格式，不支持 Apple MLX。
    # 选用 9B(4-bit, 约 6GB) 以适配 24GB 内存，原 35B(23GB) 会触发换页导致推理极慢。
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3.5:9b"
    OLLAMA_EMBEDDING_MODEL: str = "bge-m3"
    OLLAMA_TIMEOUT: int = 120               # 秒
    OLLAMA_MAX_CONCURRENT: int = 2          # 最大并发推理
    # 思考模式开关: qwen3.5 等思考模型会先输出推理过程，
    # 占用 num_predict 配额。问答场景通常无需思考，默认关闭以保证正式回答完整。
    OLLAMA_THINK: bool = False

    # ── RAG ──
    CHROMA_PERSIST_DIR: str = "./data/chroma_db"
    CHROMA_COLLECTION: str = "knowledge_base"
    RAG_TOP_K: int = 5
    # 阈值均为「余弦相似度」(0-1)，基于 bge-m3 实测校准:
    # 相关问句 top-1 落在 0.51~0.65，无关问句 top-1 落在 0.31~0.37。
    RAG_THRESHOLD_STANDARD: float = 0.52    # 标准操作类：要求高精度
    RAG_THRESHOLD_PROCESS: float = 0.48      # 流程咨询类
    RAG_THRESHOLD_FLEXIBLE: float = 0.45     # 异常排查类：多召回一些候选
    RAG_THRESHOLD_GENERAL: float = 0.45      # 未分类问题
    RAG_SPARSE_MAX_KEYWORDS: int = 8         # 关键词检索最多使用的 n-gram 数
    # 上下文长度控制（字符数）：避免 prompt 超出模型上下文窗口导致回答被截断
    RAG_MAX_DOC_CHARS: int = 1500            # 单篇知识文档最大字符数
    RAG_MAX_CONTEXT_CHARS: int = 6000        # 所有知识文档的合计上限

    # ── 生成参数 ──
    LLM_TEMPERATURE_STANDARD: float = 0.3
    LLM_TEMPERATURE_FLEXIBLE: float = 0.7
    LLM_MAX_TOKENS: int = 2048
    LLM_CONTEXT_WINDOW: int = 8192

    # ── 数据库 ──
    ANALYTICS_DB_PATH: str = "./data/analytics.db"

    # ── 代码解析 ──
    PARSER_DEFAULT_PROJECT_ROOT: str = ""
    PARSER_SUPPORTED_EXTENSIONS: list[str] = [".vue", ".js", ".ts", ".json"]

    # ── 会话 ──
    SESSION_MAX_HISTORY: int = 10           # 最大保留对话轮数
    SESSION_TTL_SECONDS: int = 300          # 会话超时 (5分钟)

    # ── 限流 ──
    # 同一用户两次提问的最小间隔。仅用于防止误触/刷屏，取值应远小于
    # 一次问答的耗时（9B 模型通常 2-10 秒），否则会误伤正常的连续追问。
    RATE_LIMIT_PER_USER: int = 3            # 同一用户提问最小间隔 (秒)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True
    }


# 创建全局配置实例
settings = Settings()
