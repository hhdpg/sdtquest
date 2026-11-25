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

    # ── LLM 供应商选择 ──
    # local = 本地 Ollama；glm = 智谱开放平台（远程 API）
    # 启动时读取此值；运行时可经 /api/llm/switch 临时切换，重启后以此为准。
    LLM_PROVIDER: str = "local"

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

    # ── 智谱 GLM（远程 API）──
    # 与 Ollama 并存，通过 LLM_PROVIDER 选择使用哪一个。
    GLM_API_KEY: str = ""
    GLM_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    # 免费模型清单（均为免费）：glm-4.7-flash(30B SOTA，能力最强但高峰期限流严重)、
    # glm-4-flash-250414(稳定)、glm-4.5-flash、glm-z1-flash(推理型)。
    # 实测 glm-4-flash-250414 最稳定，作为默认。
    GLM_MODEL: str = "glm-4-flash-250414"
    # 备用模型：主模型返回 429（免费模型访问量过大）时按顺序自动降级。
    # 逗号分隔；留空表示不降级。
    GLM_FALLBACK_MODELS: str = "glm-4.7-flash,glm-4.5-flash"
    # 思考模式：glm-4.7-flash 等默认带推理过程会占满输出配额，
    # 问答场景关闭（emitted 为 thinking.type=disabled）。
    GLM_THINKING: bool = False
    # embedding-3 支持 256-2048 维自定义。与本地 bge-m3(1024) 语义空间不同，
    # 必须使用独立向量库（见 CHROMA_COLLECTION_GLM），不能与本地索引混用。
    GLM_EMBEDDING_MODEL: str = "embedding-3"
    GLM_EMBEDDING_DIMENSIONS: int = 1024
    GLM_TIMEOUT: int = 120
    GLM_MAX_CONCURRENT: int = 4

    # ── RAG ──
    CHROMA_PERSIST_DIR: str = "./data/chroma_db"
    CHROMA_COLLECTION: str = "knowledge_base"
    # 不同 embedding 模型向量维度/语义空间不同，必须各用各的集合：
    # 本地 bge-m3 用 CHROMA_COLLECTION，GLM embedding-3 用以下集合。
    CHROMA_COLLECTION_GLM: str = "knowledge_base_glm"
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
