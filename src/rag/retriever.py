"""混合检索器模块

实现 Dense + Sparse 混合检索，使用 RRF 融合排序。
"""

from collections import defaultdict
from typing import Any

from loguru import logger

from src.config import settings
from src.domain.enums import QuestionCategory
from src.domain.models import KnowledgeItem
from src.rag.embedding import EmbeddingService
from src.rag.vectorstore import ChromaVectorStore


class HybridRetriever:
    """
    混合检索器

    结合 Dense（语义）和 Sparse（关键词）检索，使用 RRF 融合排序。

    Attributes:
        vectorstore: 向量存储
        embedding: Embedding 服务
        rrf_k: RRF 算法的 k 参数
    """

    def __init__(
        self,
        vectorstore: ChromaVectorStore | None = None,
        embedding: EmbeddingService | None = None,
        rrf_k: int = 60,
    ):
        """
        初始化混合检索器

        Args:
            vectorstore: 向量存储实例
            embedding: Embedding 服务实例
            rrf_k: RRF 算法的 k 参数（默认 60）
        """
        self.vectorstore = vectorstore or ChromaVectorStore()
        self.embedding = embedding or EmbeddingService()
        self.rrf_k = rrf_k
        logger.info("HybridRetriever 初始化 | rrf_k={}", rrf_k)

    async def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        threshold: float | None = None,
        category: QuestionCategory | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[KnowledgeItem]:
        """
        执行混合检索

        根据问题类型自动调整检索策略。

        Args:
            query: 查询文本
            top_k: 返回结果数量
            threshold: 相似度阈值
            category: 问题分类（用于自动调整策略）
            filters: 元数据过滤条件

        Returns:
            按相关性排序的知识条目列表
        """
        # 根据问题类型调整参数
        if category:
            top_k = top_k or self._get_top_k_by_category(category)
            threshold = threshold if threshold is not None else self._get_threshold_by_category(category)
        else:
            top_k = top_k or settings.RAG_TOP_K
            threshold = threshold if threshold is not None else settings.RAG_THRESHOLD_FLEXIBLE

        logger.debug(
            "开始混合检索 | query_len={} | top_k={} | threshold={} | category={}",
            len(query), top_k, threshold, category.value if category else None
        )

        try:
            # 执行 Dense 检索
            dense_results = await self._dense_retrieve(query, top_k * 2, 0.0, filters)
            logger.debug("Dense 检索完成 | found={}", len(dense_results))

            # 执行 Sparse 检索（这里简化为基于文本的检索）
            sparse_results = await self._sparse_retrieve(query, top_k * 2, filters)
            logger.debug("Sparse 检索完成 | found={}", len(sparse_results))

            # RRF 融合排序
            merged = self._rrf_merge(dense_results, sparse_results)

            # 应用阈值过滤
            final_results = [
                (item, score) for item, score in merged
                if score >= self._normalize_threshold(threshold)
            ]

            # 取 top_k
            final_results = final_results[:top_k]

            items = [item for item, _ in final_results]
            logger.info(
                "混合检索完成 | dense={} | sparse={} | merged={} | final={}",
                len(dense_results), len(sparse_results),
                len(merged), len(items)
            )

            return items

        except Exception as e:
            logger.error("混合检索失败 | error={}", str(e))
            return []

    async def _dense_retrieve(
        self,
        query: str,
        top_k: int,
        threshold: float,
        filters: dict[str, Any] | None,
    ) -> list[KnowledgeItem]:
        """
        执行 Dense（语义）检索

        Args:
            query: 查询文本
            top_k: 返回数量
            threshold: 阈值
            filters: 过滤条件

        Returns:
            知识条目列表
        """
        try:
            # 向量化查询
            query_embedding = await self.embedding.embed_query(query)

            # 向量检索
            results = await self.vectorstore.search(
                query=query_embedding,
                top_k=top_k,
                threshold=threshold,
                filters=filters,
            )

            return results
        except Exception as e:
            logger.error("Dense 检索失败 | error={}", str(e))
            return []

    async def _sparse_retrieve(
        self,
        query: str,
        top_k: int,
        filters: dict[str, Any] | None,
    ) -> list[KnowledgeItem]:
        """
        执行 Sparse（关键词）检索

        使用 ChromaDB 的文本匹配功能作为稀疏检索的替代。

        Args:
            query: 查询文本
            top_k: 返回数量
            filters: 过滤条件

        Returns:
            知识条目列表
        """
        try:
            # 使用 ChromaDB 的文本检索
            results = await self.vectorstore.search_with_text(
                query_text=query,
                top_k=top_k,
                threshold=0.0,  # 稀疏检索不应用阈值
                filters=filters,
            )
            return results
        except Exception as e:
            logger.error("Sparse 检索失败 | error={}", str(e))
            return []

    def _rrf_merge(
        self,
        *result_lists: list[KnowledgeItem],
    ) -> list[tuple[KnowledgeItem, float]]:
        """
        RRF (Reciprocal Rank Fusion) 融合排序

        算法: score = sum(1 / (k + rank_i))

        Args:
            *result_lists: 多个检索结果列表

        Returns:
            (知识条目, RRF 分数) 列表，按分数降序排列
        """
        # 计算每个文档的 RRF 分数
        scores: dict[str, float] = defaultdict(float)
        items_map: dict[str, KnowledgeItem] = {}

        for results in result_lists:
            for rank, item in enumerate(results):
                # RRF 分数 = 1 / (k + rank)
                rrf_score = 1.0 / (self.rrf_k + rank + 1)
                scores[item.id] += rrf_score
                items_map[item.id] = item

        # 按分数排序
        sorted_items = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        return [(items_map[doc_id], score) for doc_id, score in sorted_items]

    def _get_top_k_by_category(self, category: QuestionCategory) -> int:
        """根据问题类型获取 top_k"""
        if category == QuestionCategory.OPERATION_GUIDE:
            return 5  # 标准操作类需要更精确的结果
        elif category == QuestionCategory.PROCESS_INQUIRY:
            return 6
        elif category == QuestionCategory.ANOMALY_TROUBLESHOOT:
            return 8  # 异常排查需要更多上下文
        else:
            return 5

    def _get_threshold_by_category(self, category: QuestionCategory) -> float:
        """根据问题类型获取阈值"""
        if category == QuestionCategory.OPERATION_GUIDE:
            return settings.RAG_THRESHOLD_STANDARD  # 0.8
        elif category == QuestionCategory.PROCESS_INQUIRY:
            return 0.7
        elif category == QuestionCategory.ANOMALY_TROUBLESHOOT:
            return settings.RAG_THRESHOLD_FLEXIBLE  # 0.6
        else:
            return 0.5

    def _normalize_threshold(self, threshold: float) -> float:
        """
        将相似度阈值转换为 RRF 分数阈值

        注意：这是一个简化的实现，实际 RRF 分数范围与余弦相似度不同
        """
        # RRF 分数通常在 0.01-0.1 之间，这里做一个简单的映射
        return threshold * 0.1


class SimpleRetriever:
    """
    简单检索器

    仅使用 Dense 检索，适用于快速原型开发。
    """

    def __init__(
        self,
        vectorstore: ChromaVectorStore | None = None,
        embedding: EmbeddingService | None = None,
    ):
        """
        初始化简单检索器

        Args:
            vectorstore: 向量存储实例
            embedding: Embedding 服务实例
        """
        self.vectorstore = vectorstore or ChromaVectorStore()
        self.embedding = embedding or EmbeddingService()

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.5,
        filters: dict[str, Any] | None = None,
    ) -> list[KnowledgeItem]:
        """
        执行检索

        Args:
            query: 查询文本
            top_k: 返回数量
            threshold: 阈值
            filters: 过滤条件

        Returns:
            知识条目列表
        """
        try:
            query_embedding = await self.embedding.embed_query(query)
            results = await self.vectorstore.search(
                query=query_embedding,
                top_k=top_k,
                threshold=threshold,
                filters=filters,
            )
            return results
        except Exception as e:
            logger.error("检索失败 | error={}", str(e))
            return []
