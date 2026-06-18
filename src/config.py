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
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3.5:35b-a3b-instruct-4bit"
    OLLAMA_EMBEDDING_MODEL: str = "bge-m3"
    OLLAMA_TIMEOUT: int = 120               # 秒
    OLLAMA_MAX_CONCURRENT: int = 2          # 最大并发推理

    # ── RAG ──
    CHROMA_PERSIST_DIR: str = "./data/chroma_db"
    CHROMA_COLLECTION: str = "knowledge_base"
    RAG_TOP_K: int = 5
    RAG_THRESHOLD_STANDARD: float = 0.8     # 标准操作类阈值
    RAG_THRESHOLD_FLEXIBLE: float = 0.6     # 灵活推理类阈值

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
    RATE_LIMIT_PER_USER: int = 60           # 同一用户提问间隔 (秒)
    MAX_QUEUE_SIZE: int = 100               # 消息队列最大长度

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True
    }


# 创建全局配置实例
settings = Settings()
