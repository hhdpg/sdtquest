"""Embedding 服务模块

封装文本向量化功能，支持：
- 本地 Ollama bge-m3（1024 维，查询需 instruction prefix）
- 远程智谱 GLM embedding-3（维度可配，无需 prefix）

两种模型的语义空间与维度不同，构建的向量库必须隔离，
通过 EmbeddingService.for_provider() 按 provider 创建。
"""

from loguru import logger

from src.config import settings
from src.domain.exceptions import LLMServiceError


class EmbeddingService:
    """
    Embedding 服务

    封装文本向量化，屏蔽不同 provider 的差异（prefix、批大小）。

    Attributes:
        client: LLM 客户端（需实现 embed 方法）
        instruction_prefix: 查询时的指令前缀（仅 bge-m3 需要）
    """

    # bge-m3 查询时的 instruction prefix
    QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

    # 向量化批大小：过大会让请求体超出服务端限制（HTTP 400）
    EMBED_BATCH_SIZE = 10

    def __init__(
        self,
        client=None,
        add_query_prefix: bool = True,
    ):
        """
        初始化 Embedding 服务

        Args:
            client: LLM 客户端，默认创建本地 Ollama 客户端
            add_query_prefix: 是否在查询时添加 instruction prefix
        """
        if client is None:
            from src.llm.client import OllamaClient
            client = OllamaClient()
        self.client = client
        self.add_query_prefix = add_query_prefix
        logger.info("EmbeddingService 初始化 | add_query_prefix={}", add_query_prefix)

    @classmethod
    def for_provider(cls, provider: str) -> "EmbeddingService":
        """
        按 provider 创建配套的 Embedding 服务。

        不同模型的 prefix 要求不同，这里集中处理，避免调用方到处判断。

        Args:
            provider: "local"（bge-m3）或 "glm"（embedding-3）

        Returns:
            EmbeddingService 实例
        """
        if provider == "glm":
            from src.llm.glm_client import GLMClient
            # embedding-3 不要求查询 prefix
            return cls(client=GLMClient(), add_query_prefix=False)
        if provider == "local":
            from src.llm.client import OllamaClient
            return cls(client=OllamaClient(), add_query_prefix=True)
        raise LLMServiceError(f"未知的 embedding provider: {provider}")

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        向量化文档（用于索引构建）

        会自动分批，避免一次性提交过多文本导致 Ollama 请求体过大返回 400。

        Args:
            texts: 文档文本列表

        Returns:
            向量列表

        Raises:
            LLMServiceError: 向量化失败
        """
        if not texts:
            return []

        # 分批向量化：单批次文本过多会让请求体超出 Ollama 限制（HTTP 400）
        batch_size = self.EMBED_BATCH_SIZE
        all_embeddings: list[list[float]] = []

        try:
            for start in range(0, len(texts), batch_size):
                batch = texts[start:start + batch_size]
                # 文档不需要添加 instruction prefix
                embeddings = await self.client.embed(batch)
                all_embeddings.extend(embeddings)
                logger.debug(
                    "文档向量化进度 | {}/{}",
                    min(start + batch_size, len(texts)), len(texts),
                )

            logger.debug(
                "文档向量化完成 | count={} | dims={}",
                len(all_embeddings),
                len(all_embeddings[0]) if all_embeddings else 0,
            )
            return all_embeddings
        except Exception as e:
            logger.error("文档向量化失败 | error={}", str(e))
            raise LLMServiceError(f"文档向量化失败: {e}") from e

    async def embed_query(self, query: str) -> list[float]:
        """
        向量化查询（用于检索）

        bge-m3 模型建议在查询时添加 instruction prefix 以提高检索效果。

        Args:
            query: 查询文本

        Returns:
            查询向量

        Raises:
            LLMServiceError: 向量化失败
        """
        if not query.strip():
            raise LLMServiceError("查询文本不能为空")

        try:
            # 添加 instruction prefix（如果需要）
            if self.add_query_prefix:
                query_with_prefix = self.QUERY_INSTRUCTION + query
            else:
                query_with_prefix = query

            embeddings = await self.client.embed([query_with_prefix])
            if not embeddings:
                raise LLMServiceError("Embedding 返回空结果")

            logger.debug(
                "查询向量化完成 | query_len={} | dims={}",
                len(query), len(embeddings[0])
            )
            return embeddings[0]
        except Exception as e:
            logger.error("查询向量化失败 | error={}", str(e))
            raise LLMServiceError(f"查询向量化失败: {e}") from e

    async def embed_batch(
        self,
        texts: list[str],
        is_query: bool = False,
        batch_size: int = 32,
    ) -> list[list[float]]:
        """
        批量向量化

        支持自动分批处理大量文本。

        Args:
            texts: 文本列表
            is_query: 是否为查询（决定是否添加 prefix）
            batch_size: 每批大小

        Returns:
            向量列表
        """
        if not texts:
            return []

        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            if is_query:
                # 查询需要添加 prefix
                batch_with_prefix = [
                    self.QUERY_INSTRUCTION + t if self.add_query_prefix else t
                    for t in batch
                ]
                embeddings = await self.client.embed(batch_with_prefix)
            else:
                embeddings = await self.client.embed(batch)

            all_embeddings.extend(embeddings)

            logger.debug(
                "批量向量化进度 | {}/{}",
                min(i + batch_size, len(texts)), len(texts)
            )

        return all_embeddings
