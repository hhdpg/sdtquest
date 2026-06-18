"""Embedding 服务模块

封装 bge-m3 向量化功能，支持查询时的 instruction prefix。
"""

from loguru import logger

from src.domain.exceptions import LLMServiceError
from src.llm.client import OllamaClient


class EmbeddingService:
    """
    Embedding 服务

    封装 bge-m3 向量化功能，提供文本向量化接口。

    Attributes:
        client: Ollama 客户端
        instruction_prefix: 查询时的指令前缀（bge-m3 要求）
    """

    # bge-m3 查询时的 instruction prefix
    QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

    def __init__(
        self,
        client: OllamaClient | None = None,
        add_query_prefix: bool = True,
    ):
        """
        初始化 Embedding 服务

        Args:
            client: Ollama 客户端，默认创建新实例
            add_query_prefix: 是否在查询时添加 instruction prefix
        """
        self.client = client or OllamaClient()
        self.add_query_prefix = add_query_prefix
        logger.info("EmbeddingService 初始化 | add_query_prefix={}", add_query_prefix)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        向量化文档（用于索引构建）

        Args:
            texts: 文档文本列表

        Returns:
            向量列表

        Raises:
            LLMServiceError: 向量化失败
        """
        if not texts:
            return []

        try:
            # 文档不需要添加 instruction prefix
            embeddings = await self.client.embed(texts)
            logger.debug(
                "文档向量化完成 | count={} | dims={}",
                len(texts), len(embeddings[0]) if embeddings else 0
            )
            return embeddings
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
