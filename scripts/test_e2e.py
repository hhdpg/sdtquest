#!/usr/bin/env python3
"""端到端测试：卡片 → 向量库 → 混合检索 → 召回率。

与 eval_cards.py 的区别：
  · eval_cards 只测关键词打分（不依赖向量库）
  · 本脚本测完整链路：YAML → embedding → ChromaDB → HybridRetriever

用法:
    uv run scripts/test_e2e.py --dir data/cards
    uv run scripts/test_e2e.py --dir data/cards --rebuild
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from src.rag.card_scoring import card_to_dict
from src.rag.embedding import EmbeddingService
from src.rag.retriever import HybridRetriever
from src.rag.vectorstore import ChromaVectorStore
from src.llm.factory import collection_for
from scripts.card_loader import build_embedding_text, load_cards, to_knowledge_item
from scripts.eval_cards import CASES, REAL_QUESTIONS

# 卡片加载与转换统一走 scripts/card_loader.py，
# 保证「评估时向量化什么」与「建库时向量化什么」完全一致。


async def build_index(cards: list[dict], clear: bool = True, provider: str = "local") -> int:
    """
    把卡片写入指定 provider 的向量库。

    Args:
        cards: 卡片列表
        clear: 是否先清空
        provider: local（bge-m3）/ glm（embedding-3）

    Returns:
        写入的条目数
    """
    store = ChromaVectorStore(collection_name=collection_for(provider))
    embed = EmbeddingService.for_provider(provider)

    if clear:
        print(f"🗑️  清空向量库 [{store.collection_name}]...")
        await store.clear()

    print(f"🔢 [{provider}] 向量化 {len(cards)} 张卡片...")
    items = [to_knowledge_item(c) for c in cards]
    # 与 build_index.py 用同一份向量化文本（含 title + anchors）
    docs = [build_embedding_text(c) for c in cards]

    embeddings = await embed.embed_documents(docs)
    for it, emb in zip(items, embeddings):
        it.embedding = emb

    await store.add(items)
    count = await store.count()
    print(f"✅ 入库 {len(items)} 条到 [{store.collection_name}]，现有 {count} 条")
    return count


async def run_e2e(cards: list[dict], provider: str = "local") -> tuple[int, int, int, int]:
    """
    跑端到端检索。

    Returns:
        (本域正确数, 本域总数, 跨域命中数, 跨域总数)
    """
    retriever = HybridRetriever(
        vectorstore=ChromaVectorStore(collection_name=collection_for(provider)),
        embedding=EmbeddingService.for_provider(provider),
    )

    print("\n【本域问题】")
    ok = 0
    for q, expected in CASES.items():
        results = await retriever.retrieve(q, top_k=2)
        got = results[0].id if results else "无命中"
        if got == expected:
            ok += 1
            print(f"  ✅ {q}")
        else:
            print(f"  ❌ {q} → 期望 {expected}，实际 {got}")

    print(f"  ── 正确 {ok}/{len(CASES)}")

    print("\n【线上真实问题】")
    hit = 0
    for q in REAL_QUESTIONS:
        results = await retriever.retrieve(q, top_k=2)
        if results:
            hit += 1
            print(f"  ✅ {q} → {results[0].id}")
        else:
            print(f"  ❌ {q} → （无命中）")

    print(f"  ── 命中 {hit}/{len(REAL_QUESTIONS)}")
    return ok, len(CASES), hit, len(REAL_QUESTIONS)


async def main_async(args) -> int:
    root = Path(args.dir)
    if not root.is_dir():
        print(f"❌ 目录不存在: {root}")
        return 1

    cards = load_cards(root)
    if not cards:
        print("❌ 未加载到卡片")
        return 1

    print(f"\n🔍 加载 {len(cards)} 张卡片")

    if args.no_build:
        print("（跳过建库，使用现有索引）")
    else:
        await build_index(cards, clear=args.rebuild or True, provider=args.provider)

    ok, total, hit, real_total = await run_e2e(cards, provider=args.provider)

    rate = ok / total if total else 0
    print("\n" + "=" * 72)
    print(f"端到端本域召回率: {rate:.0%}（{ok}/{total}）")
    print(f"线上问题命中数:   {hit}/{real_total}")

    return 0 if rate >= 0.9 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="端到端测试")
    parser.add_argument("--dir", type=str, default="data/cards")
    parser.add_argument("--rebuild", action="store_true", help="重建索引")
    parser.add_argument("--no-build", action="store_true", help="跳过建库")
    parser.add_argument(
        "--provider", choices=["local", "glm"], default="local",
        help="使用哪个供应商的向量库与 embedding（默认 local）",
    )
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr, level="WARNING")

    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
