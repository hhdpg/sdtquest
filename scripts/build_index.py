#!/usr/bin/env python3
"""知识卡片索引构建脚本。

把 data/cards 下的 YAML 卡片向量化并写入指定 provider 的向量库。

为什么需要按 provider 分别建库：
    本地 bge-m3 与远程 GLM embedding-3 的向量维度、语义空间都不同，
    不能共用一个 Chroma 集合，否则维度冲突直接报错、或检索结果错乱。
    因此每个 provider 各自一份索引。

用法:
    # 建本地索引（bge-m3）
    uv run scripts/build_index.py --provider local

    # 建远程索引（GLM embedding-3，需要先配 GLM_API_KEY）
    uv run scripts/build_index.py --provider glm

    # 两个都建
    uv run scripts/build_index.py --provider all

    # 只增量追加（不清空）
    uv run scripts/build_index.py --provider local --no-clear
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from loguru import logger

from src.domain.enums import KnowledgeType
from src.domain.models import KnowledgeItem
from src.llm.factory import SUPPORTED_PROVIDERS, collection_for
from src.rag.embedding import EmbeddingService
from src.rag.vectorstore import ChromaVectorStore

# 卡型 → KnowledgeType 的映射（写入向量库时用）
TYPE_MAP = {
    "task": KnowledgeType.PAGE,
    "rule": KnowledgeType.MANUAL,
    "trouble": KnowledgeType.MANUAL,
    "glossary": KnowledgeType.MANUAL,
    "flow": KnowledgeType.WORKFLOW,
    "state": KnowledgeType.MANUAL,
    "faq": KnowledgeType.MANUAL,
}


def load_cards(root: Path) -> list[dict]:
    """加载卡片目录下全部 YAML"""
    cards = []
    for p in sorted(root.rglob("*.yaml")):
        try:
            d = yaml.safe_load(p.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            print(f"⚠️  {p.name} 解析失败: {e}")
            continue
        if isinstance(d, dict) and d.get("card_id"):
            cards.append(d)
    return cards


def to_knowledge_item(card: dict) -> KnowledgeItem:
    """
    卡片 dict → KnowledgeItem。

    把 one_liner + body 拼成 content，让向量化同时捕捉问法与答案。
    """
    content = f"{card.get('one_liner', '')}\n\n{card.get('body', '')}"
    anchors = [str(a) for a in (card.get("anchors") or [])]
    return KnowledgeItem(
        id=card["card_id"],
        type=TYPE_MAP.get(card.get("type", ""), KnowledgeType.MANUAL),
        title=card.get("title", ""),
        content=content,
        page_name=card.get("module", ""),
        page_path=card.get("entry_path", ""),
        tags=anchors,
        source_file="; ".join(str(s) for s in (card.get("source_ref") or [])),
        one_liner=card.get("one_liner"),
        module=card.get("module"),
    )


async def build_for_provider(provider: str, cards: list[dict], clear: bool) -> int:
    """
    为单个 provider 建索引。

    Args:
        provider: local / glm
        cards: 卡片列表
        clear: 是否先清空该集合

    Returns:
        写入条数
    """
    collection = collection_for(provider)
    store = ChromaVectorStore(collection_name=collection)
    embed = EmbeddingService.for_provider(provider)

    if clear:
        print(f"🗑️  [{provider}] 清空集合 {collection}")
        await store.clear()

    items = [to_knowledge_item(c) for c in cards]
    print(f"🔢 [{provider}] 向量化 {len(items)} 张卡片 → {collection}")

    embeddings = await embed.embed_documents([it.content for it in items])
    for it, emb in zip(items, embeddings):
        it.embedding = emb

    await store.add(items)
    count = await store.count()
    print(f"✅ [{provider}] 入库完成，集合 {collection} 现有 {count} 条")
    return count


async def main_async(args) -> int:
    root = Path(args.dir)
    if not root.is_dir():
        print(f"❌ 目录不存在: {root}")
        return 1

    cards = load_cards(root)
    if not cards:
        print("❌ 未加载到卡片")
        return 1

    providers = list(SUPPORTED_PROVIDERS) if args.provider == "all" else [args.provider]

    for provider in providers:
        try:
            await build_for_provider(provider, cards, clear=not args.no_clear)
        except Exception as e:
            print(f"❌ [{provider}] 建库失败: {e}")
            if args.provider != "all":
                return 1

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="按 provider 构建卡片向量索引")
    parser.add_argument("--dir", type=str, default="data/cards", help="卡片目录")
    parser.add_argument(
        "--provider", choices=[*SUPPORTED_PROVIDERS, "all"], default="local",
        help="为哪个供应商建库（默认 local）",
    )
    parser.add_argument("--no-clear", action="store_true", help="不清空已有集合，追加写入")
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr, level="WARNING")

    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
