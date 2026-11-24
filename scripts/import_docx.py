#!/usr/bin/env python3
"""Word 文档导入脚本。

将 .docx/.doc 操作手册转换为分节的 Markdown，作为知识卡（task/flow）的素材来源。

用法:
    uv run scripts/import_docx.py --file /path/to/manual.docx
    uv run scripts/import_docx.py --dir /path/to/docs --output data/docs_md
    uv run scripts/import_docx.py --file a.docx --no-split        # 不按节拆分

依赖:
    - pandoc（必须有）: brew install pandoc
    - 转换后用 --dry-run 预览，确认清洗效果再落盘
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

# 确保可以导入 src 模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

MARKDOWN_EXTENSIONS = {".docx", ".doc", ".doc"}
DEFAULT_OUTPUT = "data/docs_md"

# 需要整节丢弃的章节标题（大小写不敏感）
DROP_SECTION_PATTERNS = (
    r"^目\s*录$",
    r"^修订(记录|历史)$",
    r"^版本(记录|历史|说明)$",
    r"^文档(修订|变更)",
    r"^前\s*言$",
    r"^声\s*明$",
    r"^版权",
    r"^change\s*log$",
    r"^revision\s*history$",
)

# 封面类内容特征：命中任一即视为封面，整节丢弃
COVER_PATTERNS = (
    r"版权\s*所有",
    r"未经.*授权",
    r"©\s*copyright",
    r"confidential",
)

# 需要删除的正文噪声行
NOISE_LINE_PATTERNS = (
    r"^\s*第\s*\d+\s*页\s*(共\s*\d+\s*页)?\s*$",
    r"^\s*Page\s+\d+\s*(of\s+\d+)?\s*$",
    r"^\s*[\-_=]{3,}\s*$",          # 分隔线
    r"^\s*内部资料.*$",
    r"^\s*机密.*$",
    r"^\s*版权所有.*$",
)


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="将 docx 操作手册转换为分节 Markdown（知识卡素材）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --file ./手册.docx
  %(prog)s --dir ./docs --output data/docs_md
  %(prog)s --file ./手册.docx --no-split
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", type=str, help="单个 docx 文件路径")
    group.add_argument("--dir", type=str, help="目录（递归处理所有 docx）")

    parser.add_argument("--output", type=str, default=DEFAULT_OUTPUT,
                        help=f"输出目录（默认 {DEFAULT_OUTPUT}）")
    parser.add_argument("--no-split", action="store_true",
                        help="不按标题拆分，输出单个 md 文件")
    parser.add_argument("--dry-run", action="store_true",
                        help="只打印转换结果预览，不写入文件")
    parser.add_argument("--keep-media", action="store_true",
                        help="提取文档中的图片到 media 目录")
    parser.add_argument("--min-chars", type=int, default=100,
                        help="过滤内容过少的节（默认 100 字）")
    parser.add_argument("--max-chars", type=int, default=800,
                        help="单节最大字符数，超出继续细分（默认 800，对齐设计规范）")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志")

    return parser.parse_args()


def check_pandoc() -> str:
    """检查 pandoc 是否可用，返回可执行路径"""
    pandoc = shutil.which("pandoc")
    if not pandoc:
        raise RuntimeError(
            "未找到 pandoc。请先安装:\n"
            "  macOS:   brew install pandoc\n"
            "  Ubuntu:  sudo apt install pandoc"
        )
    return pandoc


def convert_docx_to_markdown(
    pandoc: str,
    src: Path,
    media_dir: Path | None = None,
) -> str:
    """
    使用 pandoc 将 docx 转为 Markdown。

    Args:
        pandoc: pandoc 可执行路径
        src: 源 docx 文件
        media_dir: 图片提取目录（None 表示不提取）

    Returns:
        转换后的 Markdown 文本

    Raises:
        RuntimeError: 转换失败
    """
    cmd = [pandoc, str(src), "-t", "markdown-pipe_tables", "--wrap=none"]

    if media_dir is not None:
        media_dir.mkdir(parents=True, exist_ok=True)
        cmd.append(f"--extract-media={media_dir}")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=180, check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"pandoc 转换超时: {src.name}") from e

    if result.returncode != 0:
        raise RuntimeError(f"pandoc 转换失败: {src.name} | {result.stderr[:300]}")

    return result.stdout


# 伪标题识别：很多 Word 手册用纯文本编号当标题（"一、"、"1.1"），
# 而非 Word 标题样式，pandoc 不会转成 # 标题。这里按编号模式还原层级。
PSEUDO_HEADING_PATTERNS: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"^第[一二三四五六七八九十百]+[章篇]\s*"), 1),
    (re.compile(r"^[一二三四五六七八九十]+\s*[、.．]\s*"), 2),
    (re.compile(r"^（[一二三四五六七八九十]+）\s*"), 2),
    (re.compile(r"^\(\s*[一二三四五六七八九十]+\s*\)\s*"), 2),
    (re.compile(r"^\d+\.\d+\.\d+\s+"), 4),
    (re.compile(r"^\d+\.\d+\s+"), 3),
    (re.compile(r"^\d+\s*[、．]\s*"), 2),
)

# 伪标题排除：这些行的形态不应被误判为标题
PSEUDO_HEADING_EXCLUDE = (
    r"^\|", r"^\+", r"^[-*+]\s", r"^>", r"^\s*$",
)

# 伪标题最大长度（超过则认为是正文）
PSEUDO_HEADING_MAX_LEN = 50


def promote_pseudo_headings(markdown: str) -> str:
    """
    把纯文本编号标题（"一、"、"1.1"）提升为 Markdown 标题。

    仅在满足以下全部条件时提升：
      · 上一行为空（或文档开头）
      · 行首匹配编号模式
      · 行长度不超过 PSEUDO_HEADING_MAX_LEN
      · 不在表格块内
      · 不以句号/感叹号/问号结尾（标题通常不带句末标点）

    Args:
        markdown: 清洗后的 Markdown

    Returns:
        标题已提升的 Markdown
    """
    lines = markdown.split("\n")
    out: list[str] = []
    in_table = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # 跟踪表格块（grid 表格以 +---+ 作边框）
        if re.match(r"^\+[-=+]+\+?\s*$", stripped):
            in_table = not in_table if stripped.startswith("+---") else in_table
        if re.match(r"^\+[-=+]+\+\s*$", stripped):
            in_table = False

        prev_blank = (i == 0) or (not lines[i - 1].strip())
        ends_sentence = bool(re.search(r"[。！？；;]\s*$", stripped))

        if (
            prev_blank
            and not in_table
            and stripped
            and not any(re.match(p, stripped) for p in PSEUDO_HEADING_EXCLUDE)
            and len(stripped) <= PSEUDO_HEADING_MAX_LEN
            and not ends_sentence
        ):
            for pattern, level in PSEUDO_HEADING_PATTERNS:
                if pattern.match(stripped):
                    # 去掉原有编号，保留标题文字
                    text = pattern.sub("", stripped).strip() or stripped
                    out.append("")
                    out.append("#" * level + " " + text)
                    break
            else:
                out.append(line)
        else:
            out.append(line)

    result = "\n".join(out)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def clean_markdown(text: str) -> str:
    """
    清洗 pandoc 输出的 Markdown。

    去除页码、页眉页脚残留、分隔线、机密声明等噪声。

    Args:
        text: 原始 Markdown

    Returns:
        清洗后的 Markdown
    """
    lines = text.split("\n")
    kept: list[str] = []

    for line in lines:
        stripped = line.strip()

        # 空行保留（用于分段），但连续空行合并
        if not stripped:
            if kept and kept[-1] == "":
                continue
            kept.append("")
            continue

        if any(re.match(p, stripped, re.IGNORECASE) for p in NOISE_LINE_PATTERNS):
            continue

        # 压缩表格单元格内的对齐空格，避免 token 浪费
        if stripped.startswith("|"):
            stripped = re.sub(r" {2,}", " ", stripped)
            kept.append(stripped)
            continue

        kept.append(line.rstrip())

    result = "\n".join(kept)

    # 压缩 3 个以上连续空行
    result = re.sub(r"\n{3,}", "\n\n", result)

    # 清理 pandoc 的 emf/wmf 图片（Word 矢量图，多数无显示价值且体积大）
    result = re.sub(r"!\[\]\([^)]*\.(emf|wmf)[^)]*\)(\{[^}]*\})?", "", result, flags=re.IGNORECASE)

    return result.strip()


def split_by_sections(
    markdown: str,
    doc_name: str,
    max_chars: int = 800,
    min_chars: int = 100,
) -> list[tuple[str, str]]:
    """
    按标题层级把文档拆成若干节。

    优先在一级/二级标题处切；若某节内容超过 max_chars，
    依次尝试三级、四级标题细分；仍超长则按段落兜底切分。
    最后合并过小的碎片，避免丢失内容。

    Args:
        markdown: 清洗后的 Markdown
        doc_name: 文档名（不含扩展名）
        max_chars: 单节最大字符数
        min_chars: 单节最小字符数，低于则与相邻节合并

    Returns:
        [(节标题路径, 节内容), ...]
    """
    # 第一步：按一/二级标题粗切
    sections = _split_at_level(markdown, doc_name, levels=(1, 2))

    # 第一步半：先丢弃目录/修订记录/封面等整节，
    # 否则这些巨型节点会被后续细分放大成上百个碎片
    sections = [
        (t, c) for t, c in sections
        if not is_droppable_section(t, c)
    ]

    # 第二步：超长节逐级用更深标题细分
    for level in (3, 4, 5, 6):
        refined: list[tuple[str, str]] = []
        for title, content in sections:
            if len(content) <= max_chars:
                refined.append((title, content))
                continue

            subs = _split_at_level(content, title, levels=(level,))
            if len(subs) > 1:
                refined.extend(subs)
            else:
                refined.append((title, content))
        sections = refined

    # 第三步：仍未达标的，按段落兜底切分
    fragmented: list[tuple[str, str]] = []
    for title, content in sections:
        if len(content) <= max_chars:
            fragmented.append((title, content))
            continue

        chunks = _split_by_paragraphs(content, max_chars)
        if len(chunks) == 1:
            fragmented.append((title, content))
            continue
        for i, chunk in enumerate(chunks, 1):
            fragmented.append((f"{title} ({i})", chunk))

    # 第四步：合并过小碎片，避免被 min_chars 过滤时丢内容
    return _merge_small_sections(fragmented, min_chars, max_chars)


def _merge_small_sections(
    sections: list[tuple[str, str]],
    min_chars: int,
    max_chars: int,
) -> list[tuple[str, str]]:
    """
    合并过小的节到相邻节。

    优先与前一个节合并（保持阅读顺序）；合并后不超过 max_chars * 1.5
    以免破坏分块上限。

    Args:
        sections: 待处理节列表
        min_chars: 最小字符数
        max_chars: 最大字符数

    Returns:
        合并后的节列表
    """
    if not sections:
        return []

    merged: list[tuple[str, str]] = []

    for title, content in sections:
        if len(content) >= min_chars or not merged:
            merged.append((title, content))
            continue

        prev_title, prev_content = merged[-1]
        if len(prev_content) + len(content) <= max_chars * 1.5:
            merged[-1] = (prev_title, f"{prev_content}\n\n{content}")
        else:
            merged.append((title, content))

    return merged


def _split_by_paragraphs(content: str, max_chars: int, overlap_ratio: float = 0.1) -> list[str]:
    """
    按段落边界把超长内容切块，保留少量重叠。

    用于无法靠标题再细分的巨型表格或长段落。

    Args:
        content: 内容
        max_chars: 每块上限
        overlap_ratio: 重叠比例（0–0.2）

    Returns:
        切分后的块列表
    """
    if len(content) <= max_chars:
        return [content]

    paragraphs = content.split("\n\n")
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        # 单段自身就超长：按行硬切
        if len(para) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            lines = para.split("\n")
            buf = ""
            for line in lines:
                if len(buf) + len(line) + 1 > max_chars and buf:
                    chunks.append(buf)
                    buf = line
                else:
                    buf = f"{buf}\n{line}" if buf else line
            if buf:
                current = buf
            continue

        if len(current) + len(para) + 2 > max_chars:
            if current:
                chunks.append(current)
            # 保留上一块末尾作重叠，避免语义断裂
            overlap = ""
            if chunks and overlap_ratio > 0:
                tail_len = int(max_chars * overlap_ratio)
                overlap = chunks[-1][-tail_len:] + "\n\n"
            current = overlap + para
        else:
            current = f"{current}\n\n{para}" if current else para

    if current.strip():
        chunks.append(current)

    return chunks


def _split_at_level(
    markdown: str,
    prefix: str,
    levels: tuple[int, ...],
) -> list[tuple[str, str]]:
    """
    在指定的标题层级处切分。

    Args:
        markdown: Markdown 文本
        prefix: 标题路径前缀（文档名或上级标题）
        levels: 参与切分的标题级别，如 (1, 2)

    Returns:
        [(节标题路径, 节内容), ...]
    """
    lines = markdown.split("\n")
    sections: list[tuple[str, str]] = []

    # 记录各级标题当前值，用于拼接路径
    hierarchy: dict[int, str] = {}
    buffer: list[str] = []
    is_first = True

    def flush() -> None:
        nonlocal buffer, is_first
        content = "\n".join(buffer).strip()
        # 首个块若没有标题，视为前言，不单独成节
        if not content or is_first:
            buffer = []
            is_first = False
            return

        path_parts = [prefix] if prefix else []
        for lvl in sorted(hierarchy):
            if hierarchy[lvl]:
                path_parts.append(hierarchy[lvl])

        # 去重相邻重复项
        deduped: list[str] = []
        for p in path_parts:
            if not deduped or deduped[-1] != p:
                deduped.append(p)

        sections.append((" > ".join(deduped), content))
        buffer = []

    heading_re = re.compile(r"^(#{1,6})\s+(.+)$")

    for line in lines:
        m = heading_re.match(line)
        if m and len(m.group(1)) in levels:
            flush()
            lvl = len(m.group(1))
            hierarchy[lvl] = m.group(2).strip()
            # 清除更深层级的残留
            for deeper in [k for k in hierarchy if k > lvl]:
                del hierarchy[deeper]
            buffer = [line]
        else:
            m_any = heading_re.match(line)
            if m_any and not is_first:
                # 非切分层级的标题，更新层级但不切分
                lvl = len(m_any.group(1))
                if lvl < max(levels, default=1):
                    pass
                else:
                    hierarchy[lvl] = m_any.group(2).strip()
                    for deeper in [k for k in hierarchy if k > lvl]:
                        del hierarchy[deeper]
            buffer.append(line)

    flush()

    # 若没有任何切分点，返回整段
    if not sections and markdown.strip():
        return [(prefix, markdown.strip())]

    return sections


def is_droppable_section(title: str, content: str = "") -> bool:
    """
    判断整节是否应该丢弃。

    丢弃条件：标题命中黑名单、或内容明显是封面/版权页。

    Args:
        title: 节标题路径
        content: 节内容（用于识别封面）

    Returns:
        是否丢弃
    """
    leaf = title.split(" > ")[-1].strip()
    if any(re.match(p, leaf, re.IGNORECASE) for p in DROP_SECTION_PATTERNS):
        return True

    # 封面识别：短内容且含版权声明
    if len(content) < 600:
        head = content[:600]
        if any(re.search(p, head, re.IGNORECASE) for p in COVER_PATTERNS):
            return True

    return False


def sanitize_filename(name: str) -> str:
    """把标题转成安全文件名"""
    name = re.sub(r"[\\/:*?\"<>|]", "_", name)
    name = re.sub(r"\s+", "_", name.strip())
    return name[:80] or "untitled"


def process_file(
    pandoc: str,
    src: Path,
    output_dir: Path,
    split: bool = True,
    keep_media: bool = False,
    min_chars: int = 100,
    max_chars: int = 800,
    pseudo_headings: bool = True,
    dry_run: bool = False,
) -> dict[str, int]:
    """
    处理单个 docx 文件。

    Args:
        pandoc: pandoc 路径
        src: 源文件
        output_dir: 输出根目录
        split: 是否按节拆分
        keep_media: 是否提取图片
        min_chars: 节的最小字符数，低于此值丢弃
        max_chars: 单节最大字符数，超出继续细分
        pseudo_headings: 是否把纯文本编号标题提升为 Markdown 标题
        dry_run: 只预览不写盘

    Returns:
        统计信息 {"sections": n, "chars": n, "skipped": n}
    """
    doc_name = src.stem
    media_dir = output_dir / "media" / sanitize_filename(doc_name) if keep_media else None

    raw = convert_docx_to_markdown(pandoc, src, media_dir)
    cleaned = clean_markdown(raw)
    if pseudo_headings:
        cleaned = promote_pseudo_headings(cleaned)

    stats = {"sections": 0, "chars": len(cleaned), "skipped": 0}

    if not split:
        if dry_run:
            print(f"\n{'=' * 60}\n📄 {src.name}（不拆分，{len(cleaned)} 字）\n{'=' * 60}")
            print(cleaned[:2000])
            print("..." if len(cleaned) > 2000 else "")
        else:
            out = output_dir / f"{sanitize_filename(doc_name)}.md"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(f"# {doc_name}\n\n{cleaned}", encoding="utf-8")
            logger.info("已输出 | file={} | chars={}", out, len(cleaned))
        stats["sections"] = 1
        return stats

    sections = split_by_sections(
        cleaned, doc_name, max_chars=max_chars, min_chars=min_chars,
    )
    kept_sections = []

    for title, content in sections:
        if is_droppable_section(title, content):
            stats["skipped"] += 1
            continue
        if len(content) < min_chars:
            stats["skipped"] += 1
            continue
        kept_sections.append((title, content))

    if dry_run:
        print(f"\n{'=' * 60}")
        print(f"📄 {src.name}")
        print(f"   原始 {len(cleaned)} 字 → {len(sections)} 节 → 保留 {len(kept_sections)} 节"
              f"（丢弃 {stats['skipped']}）")
        print("=" * 60)
        for title, content in kept_sections[:5]:
            print(f"\n▸ {title}  [{len(content)} 字]")
            print(content[:300].replace("\n", "\n  ") + ("..." if len(content) > 300 else ""))
        if len(kept_sections) > 5:
            print(f"\n... 还有 {len(kept_sections) - 5} 节")
    else:
        doc_out = output_dir / sanitize_filename(doc_name)
        doc_out.mkdir(parents=True, exist_ok=True)
        for idx, (title, content) in enumerate(kept_sections, 1):
            leaf = title.split(" > ")[-1]
            filename = f"{idx:03d}_{sanitize_filename(leaf)}.md"
            (doc_out / filename).write_text(
                f"<!-- source: {src.name} -->\n<!-- section: {title} -->\n\n{content}\n",
                encoding="utf-8",
            )
        logger.info(
            "已输出 | doc={} | sections={} | skipped={}",
            doc_name, len(kept_sections), stats["skipped"],
        )

    stats["sections"] = len(kept_sections)
    return stats


def collect_files(args: argparse.Namespace) -> list[Path]:
    """收集待处理文件"""
    if args.file:
        p = Path(args.file)
        if not p.exists():
            raise FileNotFoundError(f"文件不存在: {p}")
        if p.suffix.lower() not in {".docx", ".doc"}:
            raise ValueError(f"不支持的格式: {p.suffix}（仅支持 .docx/.doc）")
        return [p]

    d = Path(args.dir)
    if not d.is_dir():
        raise FileNotFoundError(f"目录不存在: {d}")

    files = [f for f in d.rglob("*") if f.suffix.lower() in {".docx", ".doc"}]
    # 跳过 Word 临时文件
    files = [f for f in files if not f.name.startswith("~$")]
    return sorted(files)


def main() -> int:
    """主函数"""
    args = parse_args()

    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

    try:
        pandoc = check_pandoc()
    except RuntimeError as e:
        print(f"❌ {e}")
        return 1

    try:
        files = collect_files(args)
    except (FileNotFoundError, ValueError) as e:
        print(f"❌ {e}")
        return 1

    if not files:
        print("⚠️  未找到 docx 文件")
        return 1

    output_dir = Path(args.output)
    print(f"\n📚 待处理 {len(files)} 个文件 → {output_dir}")
    if args.dry_run:
        print("   （预览模式，不写入文件）")

    total_sections = 0
    failed: list[tuple[str, str]] = []

    for src in files:
        try:
            stats = process_file(
                pandoc=pandoc,
                src=src,
                output_dir=output_dir,
                split=not args.no_split,
                keep_media=args.keep_media,
                min_chars=args.min_chars,
                max_chars=args.max_chars,
                dry_run=args.dry_run,
            )
            total_sections += stats["sections"]
        except RuntimeError as e:
            logger.error("处理失败 | file={} | error={}", src.name, str(e))
            failed.append((src.name, str(e)))

    print(f"\n{'=' * 60}")
    print(f"✅ 处理完成 | 文件 {len(files) - len(failed)}/{len(files)} | 节数 {total_sections}")
    if failed:
        print(f"❌ 失败 {len(failed)}:")
        for name, err in failed:
            print(f"   - {name}: {err[:100]}")
    if not args.dry_run and total_sections:
        print(f"\n下一步：检查 {output_dir} 下的 md 文件，确认分节合理后")
        print("       再按设计文档 §5.3 / §5.7 合成 task / flow 卡。")
    print("=" * 60)

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
