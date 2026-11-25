"""LLM 客户端工厂与运行时供应商管理

负责按 provider 创建 LLM 客户端与配套资源，并支持运行时切换。

设计要点
--------
1. **LLM 与向量索引必须成对切换**：本地用 bge-m3(1024 维)、远程用
   embedding-3，两者语义空间不同，向量库不能混用。因此切换 provider 时，
   客户端、Embedding 服务、Chroma 集合三者一起换。
2. **切换不重建已有对象**：已创建的服务实例持有 manager 引用，
   每次问答从 manager 取当前 provider，避免重建 QAService。
3. **配置是重启后的默认值**：LLM_PROVIDER 决定启动时用哪个；
   运行时切换只影响当前进程，重启后仍是配置值（可通过写 .env 固化）。
"""

from dataclasses import dataclass

from loguru import logger

from src.config import settings
from src.domain.exceptions import LLMServiceError

SUPPORTED_PROVIDERS = ("local", "glm")


@dataclass
class ProviderBundle:
    """
    一个 provider 对应的完整运行资源。

    Attributes:
        provider: 供应商标识（local / glm）
        llm: 对话用 LLM 客户端
        embedding: 与该 provider 配套的 Embedding 服务
        collection: 该 provider 使用的 Chroma 集合名
        model: 当前对话模型名，便于展示
    """

    provider: str
    llm: object
    embedding: object
    collection: str
    model: str


def collection_for(provider: str) -> str:
    """
    返回 provider 对应的 Chroma 集合名。

    不同 embedding 模型的向量维度/语义空间不通用，必须各用各的集合，
    否则会因维度不一致直接报错，或检索到语义错乱的结果。

    Args:
        provider: local / glm

    Returns:
        集合名
    """
    if provider == "glm":
        return settings.CHROMA_COLLECTION_GLM
    return settings.CHROMA_COLLECTION


def build_bundle(provider: str) -> ProviderBundle:
    """
    按 provider 构建客户端与 embedding。

    Args:
        provider: local / glm

    Returns:
        ProviderBundle

    Raises:
        LLMServiceError: provider 不支持
    """
    from src.rag.embedding import EmbeddingService

    if provider == "local":
        from src.llm.client import OllamaClient

        llm = OllamaClient()
        return ProviderBundle(
            provider="local",
            llm=llm,
            embedding=EmbeddingService(client=llm, add_query_prefix=True),
            collection=collection_for("local"),
            model=settings.OLLAMA_MODEL,
        )

    if provider == "glm":
        from src.llm.glm_client import GLMClient

        llm = GLMClient()
        return ProviderBundle(
            provider="glm",
            llm=llm,
            embedding=EmbeddingService(client=llm, add_query_prefix=False),
            collection=collection_for("glm"),
            model=settings.GLM_MODEL,
        )

    raise LLMServiceError(
        f"不支持的 LLM_PROVIDER={provider}，可选: {', '.join(SUPPORTED_PROVIDERS)}"
    )


class LLMProviderManager:
    """
    LLM 供应商管理器。

    持有各 provider 的资源，并按需切换当前生效的一个。
    使用懒加载：只有真正被选用的 provider 才会初始化客户端。

    Attributes:
        current: 当前生效的 provider 标识
    """

    def __init__(self, default_provider: str | None = None):
        """
        初始化管理器。

        Args:
            default_provider: 启动时使用的 provider，默认取 LLM_PROVIDER
        """
        provider = (default_provider or settings.LLM_PROVIDER).lower().strip()
        if provider not in SUPPORTED_PROVIDERS:
            logger.warning(
                "LLM_PROVIDER 配置无效，回退到 local | configured={}", provider
            )
            provider = "local"

        self.current = provider
        self._bundles: dict[str, ProviderBundle] = {}
        logger.info("LLMProviderManager 初始化 | current={}", provider)

    @property
    def bundle(self) -> ProviderBundle:
        """当前 provider 的资源（懒加载）"""
        if self.current not in self._bundles:
            self._bundles[self.current] = build_bundle(self.current)
        return self._bundles[self.current]

    @property
    def llm(self):
        """当前对话客户端"""
        return self.bundle.llm

    @property
    def embedding(self):
        """当前 Embedding 服务"""
        return self.bundle.embedding

    @property
    def collection(self) -> str:
        """当前 provider 的向量集合名"""
        return self.bundle.collection

    def get_bundle(self, provider: str) -> ProviderBundle:
        """获取指定 provider 的资源（懒加载，不改变当前）"""
        if provider not in SUPPORTED_PROVIDERS:
            raise LLMServiceError(
                f"不支持的 provider={provider}，可选: {', '.join(SUPPORTED_PROVIDERS)}"
            )
        if provider not in self._bundles:
            self._bundles[provider] = build_bundle(provider)
        return self._bundles[provider]

    def switch(self, provider: str) -> ProviderBundle:
        """
        切换当前 provider。

        Args:
            provider: 目标 provider

        Returns:
            切换后的资源

        Raises:
            LLMServiceError: provider 不支持
        """
        target = provider.lower().strip()
        b = self.get_bundle(target)
        old = self.current
        self.current = target
        logger.info(
            "LLM provider 已切换 | {} -> {} | model={} | collection={}",
            old, target, b.model, b.collection,
        )
        return b

    def describe(self) -> dict:
        """返回当前状态摘要，供接口展示"""
        from src.rag.vectorstore import ChromaVectorStore

        b = self.bundle
        # 只读探测当前集合已有多少条，便于判断是否已建索引
        try:
            store = ChromaVectorStore(collection_name=b.collection)
            count = store.collection.count()
        except Exception as e:  # 探测失败不应影响主流程
            logger.warning("统计向量集合失败 | collection={} | error={}", b.collection, e)
            count = -1

        # 预警：索引为空则检索必然失败；GLM 未配 key 则调用必然失败
        warnings: list[str] = []
        if count == 0:
            warnings.append(
                f"当前索引 {b.collection} 为空，问答将检索不到知识，"
                f"请执行 scripts/build_index.py --provider {self.current}"
            )
        if self.current == "glm" and not settings.GLM_API_KEY:
            warnings.append("GLM_API_KEY 未配置，调用会失败")

        return {
            "provider": self.current,
            "model": b.model,
            "collection": b.collection,
            "document_count": count,
            "supported": list(SUPPORTED_PROVIDERS),
            "ready": not warnings,
            "warnings": warnings,
        }
