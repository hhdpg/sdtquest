"""ChromaVectorStore 单元测试模块。

使用真实 ChromaDB（临时目录）验证向量写入、相似度检索与关键词检索，
无需 Ollama —— 向量由测试直接构造，避免依赖外部 embedding 服务。

覆盖的重要回归场景:
1. 写入时缺少 embedding 必须报错，而不是让 ChromaDB 回退到 384 维默认模型
   与 bge-m3 的 1024 维集合冲突（历史上导致 Sparse 检索每次失败）。
2. 余弦相似度分数必须能正确返回，供上层做阈值判断。
3. 关键词检索使用 where_document，不依赖 embedding，与向量维度解耦。
"""

import math
from pathlib import Path

import pytest

from src.domain.enums import KnowledgeType
from src.domain.exceptions import VectorStoreError
from src.domain.models import KnowledgeItem
from src.rag.vectorstore import ChromaVectorStore

DIM = 8


def make_item(item_id: str, title: str, content: str) -> KnowledgeItem:
    """构造测试知识条目"""
    return KnowledgeItem(
        id=item_id,
        type=KnowledgeType.PAGE,
        title=title,
        content=content,
        page_name="测试页面",
        page_path="/test",
        source_file="test.vue",
        tags=["测试"],
    )


def vec(values: list[float]) -> list[float]:
    """归一化向量，使余弦相似度等于点积，便于断言"""
    norm = math.sqrt(sum(v * v for v in values))
    padded = values + [0.0] * (DIM - len(values))
    return [v / norm for v in padded]


@pytest.fixture
def store(tmp_path: Path) -> ChromaVectorStore:
    """每个测试使用独立临时目录的向量库"""
    return ChromaVectorStore(
        persist_dir=str(tmp_path / "chroma"),
        collection_name=f"test_{tmp_path.name}",
    )


class TestAddWithEmbeddings:
    """向量写入测试"""

    @pytest.mark.asyncio
    async def test_add_and_count(self, store: ChromaVectorStore):
        """正常写入后数量正确"""
        items = [make_item("k1", "创建订单", "点击新建按钮创建订单")]
        await store.add_with_embeddings(items, [vec([1.0, 0.0, 0.0])])

        assert await store.count() == 1

    @pytest.mark.asyncio
    async def test_add_requires_embedding(self, store: ChromaVectorStore):
        """缺少 embedding 时必须报错

        回归保护: 曾经在缺少 embedding 时交给 ChromaDB 默认 embedding 函数
        (384 维)，而集合由 bge-m3 创建(1024 维)，导致写入/检索维度冲突。
        """
        items = [make_item("k1", "创建订单", "点击新建按钮创建订单")]
        # 未设置 item.embedding
        with pytest.raises(VectorStoreError, match="embedding"):
            await store.add(items)

    @pytest.mark.asyncio
    async def test_add_with_backfilled_embedding(self, store: ChromaVectorStore):
        """回填 embedding 字段后可以直接走 add()"""
        item = make_item("k1", "创建订单", "点击新建按钮创建订单")
        item = item.model_copy(update={"embedding": vec([1.0, 0.0, 0.0])})

        await store.add([item])
        assert await store.count() == 1

    @pytest.mark.asyncio
    async def test_add_empty_list_noop(self, store: ChromaVectorStore):
        """空列表不写入"""
        await store.add([])
        assert await store.count() == 0

    @pytest.mark.asyncio
    async def test_add_with_embeddings_length_mismatch(self, store: ChromaVectorStore):
        """条目数与向量数不匹配时报错"""
        items = [make_item("k1", "a", "b"), make_item("k2", "c", "d")]
        with pytest.raises(VectorStoreError, match="不匹配"):
            await store.add_with_embeddings(items, [vec([1.0])])


class TestSearchScored:
    """带分数检索测试"""

    @pytest.mark.asyncio
    async def test_search_scored_returns_similarity(self, store: ChromaVectorStore):
        """返回的相似度分数应与余弦相似度一致"""
        items = [
            make_item("k1", "创建订单", "点击新建按钮创建订单"),
            make_item("k2", "删除订单", "勾选订单后点击删除"),
        ]
        await store.add_with_embeddings(
            items,
            [vec([1.0, 0.0, 0.0]), vec([0.0, 1.0, 0.0])],
        )

        # 查询向量与 k1 完全同向
        results = await store.search_scored(vec([1.0, 0.0, 0.0]), top_k=2)

        assert len(results) == 2
        top_item, top_score = results[0]
        assert top_item.id == "k1"
        assert top_score > 0.99  # 余弦相似度接近 1

    @pytest.mark.asyncio
    async def test_search_scored_applies_threshold(self, store: ChromaVectorStore):
        """低于阈值的结果应被过滤"""
        items = [
            make_item("k1", "创建订单", "创建订单内容"),
            make_item("k2", "无关内容", "完全无关的内容"),
        ]
        await store.add_with_embeddings(
            items,
            [vec([1.0, 0.0, 0.0]), vec([0.0, 1.0, 0.0])],
        )

        # 与 k1 同向、与 k2 正交(相似度 0)，阈值 0.5 应只剩 k1
        results = await store.search_scored(vec([1.0, 0.0, 0.0]), top_k=2, threshold=0.5)

        assert len(results) == 1
        assert results[0][0].id == "k1"

    @pytest.mark.asyncio
    async def test_search_delegates_to_scored(self, store: ChromaVectorStore):
        """search() 应返回与 search_scored() 一致的条目"""
        items = [make_item("k1", "创建订单", "创建订单内容")]
        await store.add_with_embeddings(items, [vec([1.0, 0.0, 0.0])])

        items_only = await store.search(vec([1.0, 0.0, 0.0]), top_k=1)
        assert len(items_only) == 1
        assert items_only[0].id == "k1"

    @pytest.mark.asyncio
    async def test_search_empty_vector(self, store: ChromaVectorStore):
        """空查询向量返回空列表"""
        assert await store.search_scored([]) == []


class TestSearchByKeywords:
    """关键词检索测试"""

    @pytest.mark.asyncio
    async def test_keyword_contains_match(self, store: ChromaVectorStore):
        """关键词通过文档内字面匹配召回，不依赖 embedding"""
        items = [
            make_item("k1", "创建订单", "在订单列表点击新建按钮创建订单"),
            make_item("k2", "导出报表", "在报表中心点击导出按钮生成Excel"),
        ]
        await store.add_with_embeddings(
            items,
            [vec([1.0, 0.0, 0.0]), vec([0.0, 1.0, 0.0])],
        )

        results = await store.search_by_keywords(["导出"], top_k=5)
        assert len(results) == 1
        assert results[0].id == "k2"

    @pytest.mark.asyncio
    async def test_keyword_multiple_or_semantics(self, store: ChromaVectorStore):
        """多个关键词是 OR 语义"""
        items = [
            make_item("k1", "创建订单", "点击新建按钮创建订单"),
            make_item("k2", "删除订单", "勾选后删除订单"),
        ]
        await store.add_with_embeddings(
            items,
            [vec([1.0, 0.0, 0.0]), vec([0.0, 1.0, 0.0])],
        )

        results = await store.search_by_keywords(["创建", "删除"], top_k=5)
        assert {item.id for item in results} == {"k1", "k2"}

    @pytest.mark.asyncio
    async def test_keyword_no_match(self, store: ChromaVectorStore):
        """无匹配关键词返回空"""
        items = [make_item("k1", "创建订单", "点击新建按钮创建订单")]
        await store.add_with_embeddings(items, [vec([1.0, 0.0, 0.0])])

        assert await store.search_by_keywords(["股票", "天气"], top_k=5) == []

    @pytest.mark.asyncio
    async def test_keyword_empty_input(self, store: ChromaVectorStore):
        """空关键词列表直接返回空，不报错"""
        assert await store.search_by_keywords([], top_k=5) == []
        assert await store.search_by_keywords(["", "  "], top_k=5) == []

    @pytest.mark.asyncio
    async def test_keyword_with_metadata_filter(self, store: ChromaVectorStore):
        """关键词检索可与元数据过滤组合"""
        items = [make_item("k1", "创建订单", "点击新建按钮创建订单")]
        await store.add_with_embeddings(items, [vec([1.0, 0.0, 0.0])])

        # type 是 page，应命中
        hit = await store.search_by_keywords(["创建"], top_k=5, filters={"type": "page"})
        assert len(hit) == 1

        # type 不匹配，应过滤掉
        miss = await store.search_by_keywords(["创建"], top_k=5, filters={"type": "button"})
        assert miss == []


class TestDeleteAndClear:
    """删除与清空测试"""

    @pytest.mark.asyncio
    async def test_delete(self, store: ChromaVectorStore):
        """按 id 删除"""
        items = [make_item("k1", "创建订单", "内容一"), make_item("k2", "删除订单", "内容二")]
        await store.add_with_embeddings(
            items,
            [vec([1.0, 0.0, 0.0]), vec([0.0, 1.0, 0.0])],
        )

        await store.delete(["k1"])
        assert await store.count() == 1

    @pytest.mark.asyncio
    async def test_clear(self, store: ChromaVectorStore):
        """清空后数量归零，且仍可继续写入"""
        items = [make_item("k1", "创建订单", "内容一")]
        await store.add_with_embeddings(items, [vec([1.0, 0.0, 0.0])])

        await store.clear()
        assert await store.count() == 0

        # 清空后可继续使用
        await store.add_with_embeddings(items, [vec([1.0, 0.0, 0.0])])
        assert await store.count() == 1
