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
        t = retriever._get_threshold_by_category(QuestionCategory.OPERATION_GUIDE)
        assert t == 0.8

    def test_anomaly_threshold(self, retriever):
        """测试异常排查类阈值（低阈值）"""
        t = retriever._get_threshold_by_category(QuestionCategory.ANOMALY_TROUBLESHOOT)
        assert t == 0.6

    def test_general_threshold(self, retriever):
        """测试其他分类阈值"""
        t = retriever._get_threshold_by_category(QuestionCategory.GENERAL)
        assert t == 0.5


class TestHybridRetrieverRetrieve:
    """检索流程测试"""

    @pytest.mark.asyncio
    async def test_retrieve_calls_dense_and_sparse(self):
        """测试检索同时调用 Dense 和 Sparse"""
        with patch("src.rag.retriever.ChromaVectorStore") as mock_vs_cls, \
             patch("src.rag.retriever.EmbeddingService") as mock_emb_cls:
            mock_vs = MagicMock()
            mock_vs.search = AsyncMock(return_value=[make_item("dense_1")])
            mock_vs.search_with_text = AsyncMock(return_value=[make_item("sparse_1")])
            mock_vs_cls.return_value = mock_vs

            mock_emb = MagicMock()
            mock_emb.embed_query = AsyncMock(return_value=[0.1, 0.2])
            mock_emb_cls.return_value = mock_emb

            retriever = HybridRetriever(vectorstore=mock_vs, embedding=mock_emb)
            result = await retriever.retrieve("测试查询")

            # 应该调用 dense 和 sparse
            mock_vs.search.assert_called_once()
            mock_vs.search_with_text.assert_called_once()


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
        with patch("src.rag.retriever.ChromaVectorStore") as mock_vs_cls, \
             patch("src.rag.retriever.EmbeddingService") as mock_emb_cls:
            mock_emb = MagicMock()
            mock_emb.embed_query = AsyncMock(side_effect=Exception("失败"))
            mock_emb_cls.return_value = mock_emb

            retriever = SimpleRetriever()
            result = await retriever.retrieve("查询")

            assert result == []
