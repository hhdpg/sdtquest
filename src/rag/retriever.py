"""混合检索器模块

实现 Dense + Sparse 混合检索，使用 RRF 融合排序。
"""

import re
from collections import defaultdict
from typing import Any

from loguru import logger

from src.config import settings
from src.domain.enums import QuestionCategory
from src.domain.models import KnowledgeItem
from src.rag.embedding import EmbeddingService
from src.rag.vectorstore import ChromaVectorStore


# 关键词检索的停用词：这些疑问/虚词几乎出现在任何问句中，
# 作为 OR 条件只会引入噪声，不能反映问题的具体主题。
_SPARSE_STOPWORDS: tuple[str, ...] = (
    "如何", "怎么", "怎样", "什么", "哪里", "在哪", "哪个",
    "为什么", "是不是", "能不能", "可以", "请问", "一下",
    "操作", "使用", "需要", "应该", "我要", "我想", "帮我",
)


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
            # 执行 Dense 检索（取带分数的结果，阈值在余弦相似度量纲上判断）
            dense_scored = await self._dense_retrieve(query, top_k * 2, threshold, filters)
            logger.debug("Dense 检索完成 | found={}", len(dense_scored))

            # 执行 Sparse 检索（关键词字面量匹配）
            sparse_results = await self._sparse_retrieve(query, top_k * 2, filters)
            logger.debug("Sparse 检索完成 | found={}", len(sparse_results))

            # RRF 只负责融合排序，不参与阈值判断
            dense_results = [item for item, _ in dense_scored]
            merged = self._rrf_merge(dense_results, sparse_results)

            # 若 Dense 无任何命中，则说明语义上也不相关，直接判定未命中；
            # 否则以 RRF 排序结果取 top_k（阈值已在上一步按余弦相似度过滤）
            if not dense_results:
                logger.info(
                    "混合检索未命中 | dense=0 | sparse={} | reason=语义相似度低于阈值",
                    len(sparse_results),
                )
                return []

            items = [item for item, _ in merged[:top_k]]
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
    ) -> list[tuple[KnowledgeItem, float]]:
        """
        执行 Dense（语义）检索

        Args:
            query: 查询文本
            top_k: 返回数量
            threshold: 余弦相似度阈值（0-1，直接在此量纲上过滤）
            filters: 过滤条件

        Returns:
            (知识条目, 余弦相似度) 列表
        """
        try:
            # 向量化查询
            query_embedding = await self.embedding.embed_query(query)

            # 向量检索（带相似度分数）
            results = await self.vectorstore.search_scored(
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

        从查询中提取中文 n-gram 关键词，通过 ChromaDB 的文档内字面匹配召回。
        该路径不依赖 embedding，与 Dense 检索形成互补。

        Args:
            query: 查询文本
            top_k: 返回数量
            filters: 过滤条件

        Returns:
            知识条目列表
        """
        try:
            keywords = self._extract_keywords(query)
            if not keywords:
                return []

            results = await self.vectorstore.search_by_keywords(
                keywords=keywords,
                top_k=top_k,
                filters=filters,
            )
            return results
        except Exception as e:
            logger.error("Sparse 检索失败 | error={}", str(e))
            return []

    def _extract_keywords(self, query: str) -> list[str]:
        """
        从查询中提取用于字面匹配的关键词。

        中文没有天然词边界，这里用 n-gram 近似：
        先按标点切分，再对中文片段取 2~4 字滑动窗口，
        同时保留英文/数字连续串。为保证召回率，取前若干个。

        Args:
            query: 查询文本

        Returns:
            去重后的关键词列表（最多 RAG_SPARSE_MAX_KEYWORDS 个）
        """
        # 英文单词/数字串
        latin_tokens = re.findall(r"[A-Za-z][A-Za-z0-9_]+|\d+", query)

        # 中文片段
        chinese_segments = re.findall(r"[\u4e00-\u9fff]+", query)

        keywords: list[str] = []
        seen: set[str] = set()

        def _add(token: str) -> None:
            if not self._is_meaningful_keyword(token):
                return
            if token not in seen:
                seen.add(token)
                keywords.append(token)

        for token in latin_tokens:
            _add(token)

        for segment in chinese_segments:
            seg_len = len(segment)
            # 片段本身较短时优先作为整体关键词
            if seg_len <= 4:
                _add(segment)
            # 4~2 字滑动窗口（长词更具体，优先保留）
            for size in (4, 3, 2):
                if seg_len < size:
                    continue
                for start in range(seg_len - size + 1):
                    _add(segment[start:start + size])

        # OR 条件过多会拖慢检索，截断到上限
        return keywords[: settings.RAG_SPARSE_MAX_KEYWORDS]

    @staticmethod
    def _is_meaningful_keyword(token: str) -> bool:
        """
        判断关键词是否有检索区分度。

        过滤掉过短片段和疑问/虚词 n-gram（如 "如何"、"何创"），
        这类词几乎出现在任何问句中，加入 OR 条件只会引入噪声。

        Args:
            token: 候选关键词

        Returns:
            是否保留该关键词
        """
        if len(token) < 2:
            return False

        # 纯英文/数字直接保留
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]+|\d+", token):
            return True

        # 关键词若由疑问/虚词构成则丢弃
        for stopword in _SPARSE_STOPWORDS:
            if token in stopword or stopword in token:
                return False
        return True

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
        """根据问题类型获取余弦相似度阈值"""
        if category == QuestionCategory.OPERATION_GUIDE:
            return settings.RAG_THRESHOLD_STANDARD
        elif category == QuestionCategory.PROCESS_INQUIRY:
            return settings.RAG_THRESHOLD_PROCESS
        elif category == QuestionCategory.ANOMALY_TROUBLESHOOT:
            return settings.RAG_THRESHOLD_FLEXIBLE
        else:
            return settings.RAG_THRESHOLD_GENERAL


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
        threshold: float | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[KnowledgeItem]:
        """
        执行检索

        Args:
            query: 查询文本
            top_k: 返回数量
            threshold: 余弦相似度阈值，默认使用配置的通用阈值
            filters: 过滤条件

        Returns:
            知识条目列表
        """
        if threshold is None:
            threshold = settings.RAG_THRESHOLD_GENERAL

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
