#!/usr/bin/env python3
"""清理 pandoc 转换的 Word 正文（含目录锚点、图片占位符）。

针对大型 Word 手册：pandoc 用 --extract-media 分离图片后，
正文仍残留大量 [](#_Toc...) 目录锚点和 ![](media/...) 图片引用。
本脚本清理这些噪声，还原可读的正文结构。

用法:
    uv run scripts/clean_docx_body.py --file body.md --output clean.md
    uv run scripts/clean_docx_body.py --file body.md --drop-toc
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

# Word 内部锚点：#_Toc12345、#_top 等
ANCHOR_PATTERN = r"\{#[^}]*\.anchor\}"
# 空链接 [](#_Toc...) 及其包裹
EMPTY_ANCHOR_LINK = r"\[[^\]]*\]\(#[^)]*\)"
# 图片引用 ![alt](path){width=...}
IMAGE_REF = r"!\[[^\]]*\]\([^)]*\)(\{[^}]*\})?"
# 残留的列表锚点前缀 "1.  " 带到 bold 标题前
LIST_PREFIX = r"^\s*(?:\d+\.|[•·▪-])\s+"


def strip_toc(markdown: str) -> str:
    """
    删除文档开头的目录区。

    目录特征：连续多行形如 [标题 [页码](#_Tocxxx)](#_Tocxxx)。

    Args:
        markdown: 原始 Markdown

    Returns:
        去掉目录后的 Markdown
    """
    lines = markdown.split("\n")
    toc_end = 0

    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        # 目录行典型形态：含有 #_Toc 的链接
        if "#_Toc" in s and s.startswith("["):
            toc_end = i + 1
            continue
        # 第一个非目录、非空行之后停止
        if toc_end > 0:
            break

    if toc_end == 0:
        return markdown

    logger.info("删除目录区 | lines={}", toc_end)
    return "\n".join(lines[toc_end:])


def parse_toc_hierarchy(markdown: str) -> tuple[dict[str, int], dict[str, int]]:
    """
    从文档开头的目录区解析「标题 → 层级」。

    Word 手册的目录形如：
        [2.1组织管理 [19](#_Toc18961)](#_Toc18961)

    返回两个映射：
      · 按 anchor ID（_Toc18961）→ 层级：**首选**，同名标题不会冲突
      · 按归一化标题 → 层级：兜底，正文锚点缺失时使用

    Args:
        markdown: 含目录区的 Markdown

    Returns:
        (anchor 映射, 标题映射)，层级从 2 开始（一级=2）
    """
    by_anchor: dict[str, int] = {}
    by_title: dict[str, int] = {}

    toc_line = re.compile(
        r"^\[\s*\d+(?:\.\d+)*\s*([^\[]+?)\s*\[\d+\]\(#(_Toc\w+)\)\]"
    )

    for line in markdown.split("\n"):
        m = toc_line.match(line.strip())
        if not m:
            continue
        title, anchor = m.group(1).strip(), m.group(2)
        # 层级用编号段数推导：从整行前缀取
        num_m = re.match(r"^\[\s*(\d+(?:\.\d+)*)", line.strip())
        depth = num_m.group(1).count(".") + 1 if num_m else 2
        level = min(depth + 1, 6)

        by_anchor[anchor] = level
        # 同名标题保留第一次出现（避免被后面的同名项覆盖）
        key = _normalize_title(title)
        by_title.setdefault(key, level)

    return by_anchor, by_title


def _normalize_title(title: str) -> str:
    """标题归一化：去空白、去尾部标点，用于跨源匹配"""
    t = re.sub(r"\s+", "", title)
    return t.rstrip("：:。.").lower()


def promote_list_headings(
    markdown: str,
    toc_anchors: dict[str, int] | None = None,
    toc_titles: dict[str, int] | None = None,
) -> str:
    """
    把带锚点的有序列表标题还原为 Markdown 标题。

    原形态：`1.  []{#_Toc47sz53 .anchor}**店铺管理**`
    目标：  `### 店铺管理`

    层级查找顺序（可靠性递减）：
      1. 正文中残留的 anchor ID → 目录层级（最准，同名不冲突）
      2. 标题文本 → 目录层级
      3. 缩进推断（每 4 空格一级）
      4. 默认二级

    Args:
        markdown: Markdown 文本
        toc_anchors: {anchor ID: 层级}
        toc_titles: {归一化标题: 层级}

    Returns:
        标题已还原的 Markdown
    """
    lines = markdown.split("\n")
    out: list[str] = []
    toc_anchors = toc_anchors or {}
    toc_titles = toc_titles or {}
    by_anchor = by_title = by_indent = 0

    for line in lines:
        m = re.match(
            r"^(\s*)(?:\d+\.|[•·▪])\s+\[\]\{#(_Toc\w+)[^}]*\.anchor\}\s*\*\*([^*]+)\*\*\s*$",
            line,
        )
        m2 = None if m else re.match(
            r"^(\s*)(?:\d+\.|[•·▪])\s+(?:\{\#(_Toc\w+)[^}]*\.anchor\}\s*)?\*\*([^*]{2,40})\*\*\s*$",
            line,
        )

        hit = m or m2
        if hit:
            groups = hit.groups()
            if len(groups) == 3:
                indent_s, anchor, title = groups
            else:
                indent_s, title = groups
                anchor = ""
            indent = len(indent_s)
            title = title.strip()
            key = _normalize_title(title)

            if anchor and anchor in toc_anchors:
                level = toc_anchors[anchor]
                by_anchor += 1
            elif key in toc_titles:
                level = toc_titles[key]
                by_title += 1
            else:
                level = min(2 + indent // 4, 6)
                by_indent += 1

            out.append("")
            out.append("#" * level + " " + title.rstrip("：:"))
            continue

        out.append(line)

    logger.info(
        "标题层级来源 | by_anchor={} | by_title={} | by_indent={}",
        by_anchor, by_title, by_indent,
    )

    result = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", result)


def clean_body(markdown: str, keep_images: bool = False) -> str:
    """
    清理正文噪声。

    Args:
        markdown: Markdown 文本
        keep_images: 是否保留图片引用

    Returns:
        清理后的 Markdown
    """
    text = markdown

    # 1. 删除空锚点链接 [](#_Toc...)
    text = re.sub(EMPTY_ANCHOR_LINK, "", text)

    # 2. 删除残留的 anchor span
    text = re.sub(ANCHOR_PATTERN, "", text)

    # 3. 图片引用
    if not keep_images:
        text = re.sub(IMAGE_REF, "", text)
    else:
        # 保留但简化：只留相对路径
        text = re.sub(r"!\[[^\]]*\]\(([^)]+)\)\{[^}]*\}", r"![\1](\1)", text)

    # 4. 清理行首多余空白与空列表标记
    text = re.sub(r"^\s*(?:\d+\.|\[-\])\s*$", "", text, flags=re.MULTILINE)

    # 5. 压缩空行
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="清理 pandoc 转换的 Word 正文")
    parser.add_argument("--file", required=True, help="pandoc 输出的 Markdown")
    parser.add_argument("--output", help="输出路径（默认 <file>.clean.md）")
    parser.add_argument("--keep-images", action="store_true", help="保留图片引用")
    parser.add_argument("--drop-toc", action="store_true", help="删除开头目录区")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    src = Path(args.file)
    if not src.exists():
        print(f"❌ 文件不存在: {src}")
        return 1

    raw = src.read_text(encoding="utf-8")
    before = len(raw)

    text = raw
    # 目录必须在删除前解析，层级信息只存在于目录里
    toc_anchors, toc_titles = parse_toc_hierarchy(text)
    logger.info("目录解析 | anchors={} | titles={}", len(toc_anchors), len(toc_titles))

    if args.drop_toc:
        text = strip_toc(text)
    text = promote_list_headings(text, toc_anchors, toc_titles)
    text = clean_body(text, keep_images=args.keep_images)

    out_path = Path(args.output) if args.output else src.with_suffix(".clean.md")
    out_path.write_text(text, encoding="utf-8")

    headings = len(re.findall(r"^#{1,6}\s", text, flags=re.MULTILINE))
    logger.info(
        "清理完成 | before={} | after={} | reduction={:.0%} | headings={}",
        before, len(text), 1 - len(text) / before if before else 0, headings,
    )

    print(f"\n✅ 已输出: {out_path}")
    print(f"   {before:,} 字 → {len(text):,} 字（-{1 - len(text) / before:.0%}）")
    print(f"   标题数: {headings}")
    if args.verbose:
        for line in text.split("\n")[:40]:
            print("   " + line)

    return 0


if __name__ == "__main__":
    sys.exit(main())
