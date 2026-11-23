"""混合检索器单元测试模块。

测试 HybridRetriever 的 Dense + Sparse 检索和 RRF 融合排序。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.domain.enums import KnowledgeType, QuestionCategory
from src.domain.models import KnowledgeItem
from src.rag.retriever import HybridRetriever, SimpleRetriever


def make_item(id: str, title: str = "test", content: str = "content") -> KnowledgeItem:
    """创建测试用 KnowledgeItem"""
    return KnowledgeItem(
        id=id,
        type=KnowledgeType.BUTTON,
        title=title,
        content=content,
        page_name="测试页面",
    )


class TestHybridRetrieverRRF:
    """RRF 融合排序测试"""

    @pytest.fixture
    def retriever(self):
        with patch("src.rag.retriever.ChromaVectorStore"), \
             patch("src.rag.retriever.EmbeddingService"):
            return HybridRetriever()

    def test_rrf_merge_single_list(self, retriever):
        """测试单列表 RRF 合并"""
        items = [make_item("a"), make_item("b"), make_item("c")]
        result = retriever._rrf_merge(items)

        assert len(result) == 3
        # 第一个 item rank 0, 分数最高
        assert result[0][0].id == "a"
        assert result[0][1] > result[1][1] > result[2][1]

    def test_rrf_merge_two_lists(self, retriever):
        """测试双列表 RRF 合并（RRF 的核心场景）"""
        list1 = [make_item("a"), make_item("b"), make_item("c")]
        list2 = [make_item("b"), make_item("c"), make_item("d")]

        result = retriever._rrf_merge(list1, list2)

        # b 和 c 在两个列表都出现，RRF 分数更高
        ids = [item.id for item, _ in result]
        assert "b" in ids[:2]  # b 应该在最前面
        assert "c" in ids[:2]  # c 也应在前两位

    def test_rrf_merge_empty_lists(self, retriever):
        """测试空列表合并"""
        result = retriever._rrf_merge([], [])
        assert result == []

    def test_rrf_merge_partial_overlap(self, retriever):
        """测试部分重叠的列表合并"""
        list1 = [make_item("a"), make_item("b")]
        list2 = [make_item("c"), make_item("d")]

        result = retriever._rrf_merge(list1, list2)

        assert len(result) == 4
        # 所有 item 都出现一次，分数应该相近
        ids = [item.id for item, _ in result]
        assert set(ids) == {"a", "b", "c", "d"}

    def test_rrf_merge_deduplicates(self, retriever):
        """测试 RRF 去重"""
        item = make_item("same_id", title="t1")
        result = retriever._rrf_merge([item], [item])

        assert len(result) == 1
        assert result[0][0].id == "same_id"


class TestHybridRetrieverCategoryConfig:
    """分类参数配置测试"""

    @pytest.fixture
    def retriever(self):
        with patch("src.rag.retriever.ChromaVectorStore"), \
             patch("src.rag.retriever.EmbeddingService"):
            return HybridRetriever()

    def test_operation_guide_top_k(self, retriever):
        """测试操作指南类 top_k"""
        k = retriever._get_top_k_by_category(QuestionCategory.OPERATION_GUIDE)
        assert k == 5

    def test_anomaly_troubleshoot_top_k(self, retriever):
        """测试异常排查类 top_k（需要更多上下文）"""
        k = retriever._get_top_k_by_category(QuestionCategory.ANOMALY_TROUBLESHOOT)
        assert k == 8

    def test_operation_guide_threshold(self, retriever):
        """测试操作指南类阈值（高阈值）"""
        from src.config import settings

        t = retriever._get_threshold_by_category(QuestionCategory.OPERATION_GUIDE)
        assert t == settings.RAG_THRESHOLD_STANDARD

    def test_anomaly_threshold(self, retriever):
        """测试异常排查类阈值（低阈值）"""
        from src.config import settings

        t = retriever._get_threshold_by_category(QuestionCategory.ANOMALY_TROUBLESHOOT)
        assert t == settings.RAG_THRESHOLD_FLEXIBLE

    def test_general_threshold(self, retriever):
        """测试其他分类阈值"""
        from src.config import settings

        t = retriever._get_threshold_by_category(QuestionCategory.GENERAL)
        assert t == settings.RAG_THRESHOLD_GENERAL

    def test_thresholds_are_cosine_scale(self, retriever):
        """阈值应为余弦相似度量纲(0-1)，不能超出实际相似度分布范围

        回归保护: 历史上阈值配置为 0.8，而 bge-m3 实测相关问句 top-1
        仅约 0.51~0.65，导致所有检索结果都被过滤、问答恒为未命中。
        """
        for category in QuestionCategory:
            t = retriever._get_threshold_by_category(category)
            assert 0.0 < t < 0.75, f"{category} 阈值 {t} 超出余弦相似度合理区间"


class TestHybridRetrieverRetrieve:
    """检索流程测试"""

    @pytest.mark.asyncio
    async def test_retrieve_calls_dense_and_sparse(self):
        """测试检索同时调用 Dense(带分数) 和 Sparse(关键词)"""
        mock_vs = MagicMock()
        mock_vs.search_scored = AsyncMock(return_value=[(make_item("dense_1"), 0.62)])
        mock_vs.search_by_keywords = AsyncMock(return_value=[make_item("sparse_1")])

        mock_emb = MagicMock()
        mock_emb.embed_query = AsyncMock(return_value=[0.1, 0.2])

        retriever = HybridRetriever(vectorstore=mock_vs, embedding=mock_emb)
        result = await retriever.retrieve("测试查询")

        # 应该调用 dense 和 sparse 两条路径
        mock_vs.search_scored.assert_called_once()
        mock_vs.search_by_keywords.assert_called_once()
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_retrieve_returns_empty_when_dense_below_threshold(self):
        """Dense 无命中时不应因 Sparse 关键词偶然命中而误报

        Sparse 是字面匹配，容易在语义不相关时产生噪声命中，
        因此最终是否命中必须以 Dense 的语义相似度为准。
        """
        mock_vs = MagicMock()
        # Dense 在阈值过滤后为空
        mock_vs.search_scored = AsyncMock(return_value=[])
        # Sparse 却命中了（关键词偶然匹配）
        mock_vs.search_by_keywords = AsyncMock(return_value=[make_item("noise")])

        mock_emb = MagicMock()
        mock_emb.embed_query = AsyncMock(return_value=[0.1, 0.2])

        retriever = HybridRetriever(vectorstore=mock_vs, embedding=mock_emb)
        result = await retriever.retrieve("完全不相关的问题")

        assert result == []


class TestKeywordExtraction:
    """关键词提取测试"""

    @pytest.fixture
    def retriever(self):
        with patch("src.rag.retriever.ChromaVectorStore"), \
             patch("src.rag.retriever.EmbeddingService"):
            return HybridRetriever()

    def test_extract_chinese_ngrams(self, retriever):
        """中文查询应产出 n-gram 关键词"""
        keywords = retriever._extract_keywords("如何创建订单")
        assert "创建订单" in keywords
        assert "创建" in keywords

    def test_extract_latin_tokens(self, retriever):
        """英文/数字应作为整体关键词保留"""
        keywords = retriever._extract_keywords("Excel 报表怎么导出")
        assert "Excel" in keywords

    def test_extract_respects_max_limit(self, retriever):
        """关键词数量应受配置上限约束"""
        from src.config import settings

        keywords = retriever._extract_keywords("这是一个非常长的问题需要被切分成很多很多的关键词片段")
        assert len(keywords) <= settings.RAG_SPARSE_MAX_KEYWORDS

    def test_extract_empty_query(self, retriever):
        """空查询返回空关键词"""
        assert retriever._extract_keywords("") == []


class TestSimpleRetriever:
    """简单检索器测试"""

    @pytest.mark.asyncio
    async def test_simple_retrieve(self):
        """测试简单检索（仅 Dense）"""
        with patch("src.rag.retriever.ChromaVectorStore") as mock_vs_cls, \
             patch("src.rag.retriever.EmbeddingService") as mock_emb_cls:
            mock_vs = MagicMock()
            mock_vs.search = AsyncMock(return_value=[make_item("item1")])
            mock_vs_cls.return_value = mock_vs

            mock_emb = MagicMock()
            mock_emb.embed_query = AsyncMock(return_value=[0.1, 0.2])
            mock_emb_cls.return_value = mock_emb

            retriever = SimpleRetriever(vectorstore=mock_vs, embedding=mock_emb)
            result = await retriever.retrieve("查询")

            assert len(result) == 1
            mock_emb.embed_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_simple_retrieve_error_returns_empty(self):
        """测试检索异常返回空列表"""
        with patch("src.rag.retriever.EmbeddingService") as mock_emb_cls:
            mock_emb = MagicMock()
            mock_emb.embed_query = AsyncMock(side_effect=Exception("失败"))
            mock_emb_cls.return_value = mock_emb

            retriever = SimpleRetriever()
            result = await retriever.retrieve("查询")

            assert result == []


class TestHybridRetrieverWithRealStore:
    """使用真实 ChromaDB 的检索端到端测试

    这组测试覆盖历史 bug 的完整链路: Dense 相似度 → 阈值过滤 → RRF 融合。
    之前阈值被错误地映射到 RRF 分数量纲，导致所有结果恒被过滤，问答恒未命中。
    """

    @pytest.fixture
    def real_retriever(self, tmp_path):
        """构造使用真实向量库的检索器（embedding 用假实现，避免依赖 Ollama）"""
        import math

        from src.rag.vectorstore import ChromaVectorStore

        # 简易确定性 embedding: 根据关键词命中构造向量，模拟语义相似
        def fake_embed(text: str) -> list[float]:
            keywords = ["订单", "创建", "删除", "报表", "导出", "审批"]
            raw = [float(kw in text) for kw in keywords] + [0.01]
            norm = math.sqrt(sum(v * v for v in raw)) or 1.0
            return [v / norm for v in raw]

        vs = ChromaVectorStore(
            persist_dir=str(tmp_path / "chroma"),
            collection_name=f"retriever_{tmp_path.name}",
        )
        emb = MagicMock()
        emb.embed_query = AsyncMock(side_effect=fake_embed)
        emb.embed_documents = AsyncMock(
            side_effect=lambda texts: [fake_embed(t) for t in texts]
        )
        return HybridRetriever(vectorstore=vs, embedding=emb), vs, emb

    @pytest.mark.asyncio
    async def test_relevant_query_returns_hit(self, real_retriever):
        """相关内容问句应能召回知识（而非恒为空）"""
        retriever, vs, emb = real_retriever

        items = [
            make_item("k1", "创建订单", "创建订单 订单列表"),
            make_item("k2", "删除订单", "删除订单 订单列表"),
        ]
        await vs.add_with_embeddings(items, await emb.embed_documents(
            [i.to_document_string() for i in items]
        ))

        results = await retriever.retrieve("创建订单", threshold=0.3)

        assert len(results) > 0
        assert results[0].id == "k1"

    @pytest.mark.asyncio
    async def test_irrelevant_query_returns_empty(self, real_retriever):
        """完全无关问句应被阈值拒答"""
        retriever, vs, emb = real_retriever

        items = [make_item("k1", "创建订单", "创建订单 订单列表")]
        await vs.add_with_embeddings(items, await emb.embed_documents(
            [i.to_document_string() for i in items]
        ))

        # 阈值设得很高，无关查询不应该命中
        results = await retriever.retrieve("股票行情", threshold=0.9)

        assert results == []

    @pytest.mark.asyncio
    async def test_threshold_uses_cosine_not_rrf_scale(self, real_retriever):
        """阈值必须在余弦相似度量纲上生效

        回归保护: 若阈值被错误映射到 RRF 分数量纲(约 0.01~0.06)，
        则任何合理的余弦阈值(如 0.5)都会把全部结果过滤掉。
        """
        retriever, vs, emb = real_retriever

        items = [make_item("k1", "创建订单", "创建订单 订单列表")]
        await vs.add_with_embeddings(items, await emb.embed_documents(
            [i.to_document_string() for i in items]
        ))

        # 用真实的默认操作指南阈值（约 0.5），相关查询应能通过
        results = await retriever.retrieve(
            "创建订单", category=QuestionCategory.OPERATION_GUIDE
        )
        assert len(results) > 0, "余弦阈值未被正确应用，检索恒为空"
