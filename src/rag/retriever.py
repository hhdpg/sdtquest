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
        provider_manager=None,
    ):
        """
        初始化混合检索器

        Args:
            vectorstore: 向量存储实例
            embedding: Embedding 服务实例
            rrf_k: RRF 算法的 k 参数（默认 60）
            provider_manager: LLM 供应商管理器。传入后可随运行时切换
                自动更换向量集合与 embedding；不传则使用固定实例。
        """
        self._fixed_vectorstore = vectorstore
        self._fixed_embedding = embedding or EmbeddingService()
        self.provider_manager = provider_manager
        self._provider_stores: dict[str, ChromaVectorStore] = {}
        self.rrf_k = rrf_k
        logger.info(
            "HybridRetriever 初始化 | rrf_k={} | provider_manager={}",
            rrf_k, type(provider_manager).__name__ if provider_manager else None,
        )

    @property
    def embedding(self) -> EmbeddingService:
        """当前生效的 Embedding 服务（随 provider 切换）"""
        if self.provider_manager is not None:
            return self.provider_manager.embedding
        return self._fixed_embedding

    @property
    def vectorstore(self) -> ChromaVectorStore:
        """
        当前生效的向量存储。

        有 provider_manager 时按其集合名取（按 provider 缓存实例），
        保证问答用的是与当前 embedding 配套的那个索引。
        """
        if self.provider_manager is None:
            return self._fixed_vectorstore or ChromaVectorStore()

        coll = self.provider_manager.collection
        if coll not in self._provider_stores:
            self._provider_stores[coll] = ChromaVectorStore(collection_name=coll)
        return self._provider_stores[coll]

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
            if threshold is None:
                threshold = self._get_threshold_by_category(QuestionCategory.GENERAL)

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

            # 重排需要比最终结果更大的候选池——若先按 top_k 截断，
            # 正确答案可能已被切掉，重排也救不回来。
            # 取 top_k*3（向上取整且至少 10 条）作为重排输入。
            pool_size = max(top_k * 3, 10)
            candidates = [item for item, _ in merged[:pool_size]]

            # ── 关键词规则重排（九条防误召回规则）──
            # RRF 只看相对排名，无法处理"泛化词误命中""跨域串味"等问题。
            # 这里用 card_scoring 对候选池重新打分，再截断到 top_k。
            items = self._rerank_with_rules(query, candidates, dense_scored, top_k)

            logger.info(
                "混合检索完成 | dense={} | sparse={} | merged={} | final={}",
                len(dense_results), len(sparse_results),
                len(merged), len(items)
            )

            return items

        except Exception as e:
            logger.error("混合检索失败 | error={}", str(e))
            return []

    def _rerank_with_rules(
        self,
        query: str,
        items: list[KnowledgeItem],
        dense_scored: list[tuple[KnowledgeItem, float]],
        top_k: int,
    ) -> list[KnowledgeItem]:
        """
        用九条关键词规则对候选集重排。

        只重排已有候选，不改变候选集；若规则打分全部低于阈值，
        回退到原向量排序，避免规则配置缺失时把结果清空。

        Args:
            query: 查询文本
            items: 向量/关键词召回后的候选
            dense_scored: 带相似度分数的候选（用于回退）
            top_k: 返回条数

        Returns:
            重排后的知识条目
        """
        try:
            from src.rag.card_scoring import card_to_dict

            scorer = self._get_scorer()
            corpus = self._load_corpus()

            # 重排优先用全库原始卡片：向量库往返会丢失 one_liner 等字段，
            # 导致分数失真。按 card_id 从全库取原始 dict。
            if corpus:
                by_cid = {c["card_id"]: c for c in corpus}
                card_dicts = []
                item_by_cid = {}
                for it in items:
                    cid = it.id
                    item_by_cid[cid] = it
                    card_dicts.append(by_cid.get(cid) or card_to_dict(it))
            else:
                card_dicts = [card_to_dict(it) for it in items]
                item_by_cid = {card_to_dict(it)["card_id"]: it for it in items}

            scorer.fit(corpus if corpus else card_dicts)

            ranked = scorer.rank(query, card_dicts, top_k=len(card_dicts))
            if not ranked:
                # 规则分全部低于阈值：可能是配置缺失或新业务未接入，
                # 此时信任向量召回，不做干预。
                logger.warning(
                    "规则重排无命中，回退向量排序 | candidates={}",
                    len(items),
                )
                return items[:top_k]

            # 按重排后的 card_id 顺序还原 KnowledgeItem
            reranked = [item_by_cid[d["card_id"]] for _, d in ranked
                        if d["card_id"] in item_by_cid]

            # 重排结果之后，补齐规则未覆盖的候选（保持原有相对顺序）
            seen = {it.id for it in reranked}
            for it in items:
                if it.id not in seen:
                    reranked.append(it)

            logger.debug(
                "规则重排完成 | before={} | after={}",
                items[0].title[:20] if items else "",
                reranked[0].title[:20] if reranked else "",
            )
            return reranked[:top_k]

        except Exception as e:
            # 重排是增强能力，失败不应影响主检索链路
            logger.warning("规则重排失败，回退向量排序 | error={}", str(e))
            return items[:top_k]

    def _get_scorer(self):
        """惰性初始化打分器（配置缺失时抛错会被上层捕获）"""
        if not hasattr(self, "_scorer") or self._scorer is None:
            from src.rag.card_scoring import CardScorer

            self._scorer = CardScorer.from_config()
        return self._scorer

    def _load_corpus(self) -> list[dict]:
        """
        加载全库卡片用于 IDF 计算。

        IDF 是全局统计量，必须基于全库而非候选子集，否则排序不稳定。
        结果缓存在实例上，避免每轮重读。

        Returns:
            全库卡片 dict 列表；加载失败时返回空列表
        """
        if getattr(self, "_corpus", None) is not None:
            return self._corpus

        from pathlib import Path

        import yaml

        from src.rag.card_scoring import card_to_dict

        self._corpus: list[dict] = []
        cards_dir = Path("data/cards")
        if not cards_dir.is_dir():
            logger.debug("全库目录不存在，IDF 退回候选池 | dir={}", cards_dir)
            return self._corpus

        for p in cards_dir.rglob("*.yaml"):
            try:
                d = yaml.safe_load(p.read_text(encoding="utf-8"))
            except yaml.YAMLError:
                continue
            if isinstance(d, dict) and d.get("card_id"):
                self._corpus.append(card_to_dict(d))

        logger.debug("全库加载完成 | cards={}", len(self._corpus))
        return self._corpus

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
        """
        根据问题类型获取余弦相似度阈值。

        两个 provider 的 embedding 分布不同，阈值必须分别取：
        GLM embedding-3 整体相似度更高，沿用 bge-m3 的阈值会误召回。

        Args:
            category: 问题分类

        Returns:
            当前 provider 下该分类的阈值
        """
        glm = self._using_glm()

        if category == QuestionCategory.OPERATION_GUIDE:
            return (
                settings.RAG_THRESHOLD_GLM_STANDARD if glm
                else settings.RAG_THRESHOLD_STANDARD
            )
        elif category == QuestionCategory.PROCESS_INQUIRY:
            return (
                settings.RAG_THRESHOLD_GLM_PROCESS if glm
                else settings.RAG_THRESHOLD_PROCESS
            )
        elif category == QuestionCategory.ANOMALY_TROUBLESHOOT:
            return (
                settings.RAG_THRESHOLD_GLM_FLEXIBLE if glm
                else settings.RAG_THRESHOLD_FLEXIBLE
            )
        return (
            settings.RAG_THRESHOLD_GLM_GENERAL if glm
            else settings.RAG_THRESHOLD_GENERAL
        )

    def _using_glm(self) -> bool:
        """
        当前检索是否走 GLM embedding。

        Returns:
            True 表示当前 provider 为 glm
        """
        return (
            self.provider_manager is not None
            and self.provider_manager.current == "glm"
        )


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
