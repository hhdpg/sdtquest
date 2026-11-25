"""知识卡片加载与转换（脚本共用）。

为什么抽出来：
    build_index.py 与 test_e2e.py 原先各自实现了一遍 load_cards /
    to_knowledge_item。两处漂移会直接导致「建库时向量化 A 文本、
    评估时向量化 B 文本」，测出来的分数不再代表线上实际效果。

向量化文本的取舍（2026-11 实测，GLM embedding-3，20 条真实问法）：
    · 只用 one_liner + body：top1 命中 16/20
    · 加上 title + anchors：  top1 命中 18/20
    原因是 title 与 anchors 写的就是「用户会怎么问」，
    而 one_liner/body 写的是「答案」，两者语义空间不同。
    卡片正文本身不重复标题（已校验），因此这里加进来不会引入冗余。
"""

from pathlib import Path

import yaml
from loguru import logger

from src.domain.enums import KnowledgeType
from src.domain.models import KnowledgeItem

# 卡型 → KnowledgeType 的映射（写入向量库时用）
TYPE_MAP: dict[str, KnowledgeType] = {
    "task": KnowledgeType.PAGE,
    "rule": KnowledgeType.MANUAL,
    "trouble": KnowledgeType.MANUAL,
    "glossary": KnowledgeType.MANUAL,
    "flow": KnowledgeType.WORKFLOW,
    "state": KnowledgeType.MANUAL,
    "faq": KnowledgeType.MANUAL,
}


def load_cards(root: Path) -> list[dict]:
    """
    加载卡片目录下全部 YAML。

    Args:
        root: 卡片根目录

    Returns:
        卡片 dict 列表（按文件名排序，保证建库顺序稳定）
    """
    cards: list[dict] = []
    for p in sorted(root.rglob("*.yaml")):
        try:
            d = yaml.safe_load(p.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            logger.warning("卡片解析失败 | file={} | error={}", p.name, e)
            continue
        if isinstance(d, dict) and d.get("card_id"):
            cards.append(d)
    return cards


def build_embedding_text(card: dict) -> str:
    """
    拼接用于向量化的文本。

    顺序：标题(含用户问法) → 一句话答案 → 正文 → 关键词。
    标题和 anchors 必须进来，否则用户换个说法提问就召不回。

    Args:
        card: 卡片 dict

    Returns:
        供 embedding 使用的文本
    """
    anchors = [str(a) for a in (card.get("anchors") or [])]

    parts = [card.get("title", "").strip()]
    one_liner = (card.get("one_liner") or "").strip()
    if one_liner:
        parts.append(one_liner)
    body = (card.get("body") or "").strip()
    if body:
        parts.append(body)
    if anchors:
        parts.append("关键词：" + "、".join(anchors))

    return "\n\n".join(p for p in parts if p)


def to_knowledge_item(card: dict) -> KnowledgeItem:
    """
    卡片 dict → KnowledgeItem（写入向量库）。

    content 同时承担两个角色：向量库里的 document 字段。
    这里存 one_liner + body（不含标题与 anchors），
    因为标题会由 ContextAssembler 单独输出，避免 prompt 内重复。
    向量化用的是 build_embedding_text()，与 content 分离。

    Args:
        card: 卡片 dict

    Returns:
        KnowledgeItem
    """
    content = f"{card.get('one_liner', '')}\n\n{card.get('body', '')}".strip()
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
