#!/usr/bin/env python3
"""知识卡校验脚本。

按 docs/knowledge-design-v2.md §4.3 校验 YAML 卡片是否合规。

用法:
    uv run scripts/validate_cards.py --dir data/cards
    uv run scripts/validate_cards.py --dir data/cards --verbose

依赖:
    - PyYAML
"""

import argparse
import re
import sys
from pathlib import Path

# 确保可以导入 src 模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

try:
    import yaml
except ImportError:
    print("❌ 缺少 PyYAML，请先安装: uv add pyyaml")
    sys.exit(1)


REQUIRED_FIELDS = (
    "card_id", "type", "title", "one_liner", "body",
    "anchors", "module", "source_ref", "owner", "verified_at",
)

VALID_TYPES = {"glossary", "task", "rule", "state", "trouble", "flow", "faq"}

# 代码名泄漏检测：标题/一句话答案中不应出现这些形态
CODE_LEAK_PATTERNS = (
    (re.compile(r"\bus_[a-z_]+\b"), "表名"),
    (re.compile(r"\b[a-z]+[A-Z]\w*\b"), "驼峰标识符"),
    (re.compile(r"\b[A-Z][A-Z0-9_]{3,}\b"), "枚举常量"),
    (re.compile(r"/api/[a-zA-Z0-9/_-]+"), "接口路径"),
)

MIN_ONELINER_CHARS = 10
MAX_ONELINER_CHARS = 80
MIN_BODY_CHARS = 60
MAX_BODY_CHARS = 600
MIN_ANCHORS = 3


def validate_card(card: dict, path: Path) -> list[str]:
    """
    校验单张卡片。

    Args:
        card: 卡片数据
        path: 卡片文件路径（用于错误定位）

    Returns:
        错误信息列表，空列表表示通过
    """
    errors: list[str] = []

    # 必填字段
    for f in REQUIRED_FIELDS:
        if not card.get(f):
            errors.append(f"缺少必填字段: {f}")

    if errors:
        return errors

    # 卡型合法
    if card["type"] not in VALID_TYPES:
        errors.append(f"非法卡型: {card['type']}（应为 {sorted(VALID_TYPES)}）")

    # 一句话答案长度
    one_liner = str(card["one_liner"])
    if len(one_liner) > MAX_ONELINER_CHARS:
        errors.append(f"one_liner 超过 {MAX_ONELINER_CHARS} 字（当前 {len(one_liner)}）")
    if len(one_liner) < MIN_ONELINER_CHARS:
        errors.append(f"one_liner 过短（当前 {len(one_liner)} 字）")

    # 正文长度
    body = str(card["body"])
    if not (MIN_BODY_CHARS <= len(body) <= MAX_BODY_CHARS):
        errors.append(
            f"body 长度 {len(body)} 字，应在 {MIN_BODY_CHARS}–{MAX_BODY_CHARS} 之间"
        )

    # anchors 数量
    anchors = card["anchors"]
    if not isinstance(anchors, list):
        errors.append("anchors 应为列表")
    elif len(anchors) < MIN_ANCHORS:
        errors.append(f"anchors 至少 {MIN_ANCHORS} 个（当前 {len(anchors)}）")
    else:
        # anchors 必须是字符串；纯数字锚点无检索价值
        for a in anchors:
            if not isinstance(a, str):
                errors.append(f"anchors 含非字符串项: {a!r}（请加引号）")
            elif a.isdigit():
                errors.append(f"anchors 含纯数字项: {a}（无检索价值，建议删除）")

    # source_ref
    if not isinstance(card["source_ref"], list) or not card["source_ref"]:
        errors.append("source_ref 应为非空列表")
    else:
        for ref in card["source_ref"]:
            ref_str = str(ref)
            # 裸 "#1.2" 这种脱离文件名的引用无法定位
            if ref_str.startswith("#"):
                errors.append(f"source_ref 缺少文件名: {ref_str}")
            # 路径含 .md# 但被 YAML 截断的迹象（长度异常短）
            elif len(ref_str) < 8:
                errors.append(f"source_ref 过短，可能被 YAML 截断: {ref_str}")

    # 代码名泄漏（只查用户可见的 title / one_liner）
    for field in ("title", "one_liner"):
        text = str(card.get(field, ""))
        for pattern, label in CODE_LEAK_PATTERNS:
            if pattern.search(text):
                errors.append(f"{field} 含{label}，违反双视图规范: {pattern.search(text).group()}")

    # card_id 格式
    if not re.match(r"^[a-z0-9]+-[a-z0-9-]+$", str(card["card_id"])):
        errors.append(f"card_id 格式建议为 module-cardtype-slug，当前: {card['card_id']}")

    return errors


def check_duplicates(cards: list[tuple[Path, dict]]) -> list[str]:
    """检查 card_id 重复"""
    seen: dict[str, Path] = {}
    errors: list[str] = []
    for path, card in cards:
        cid = card.get("card_id")
        if not cid:
            continue
        if cid in seen:
            errors.append(f"card_id 重复: {cid} （{seen[cid].name} 与 {path.name}）")
        else:
            seen[cid] = path
    return errors


def check_relations(cards: list[tuple[Path, dict]]) -> list[str]:
    """
    检查 related 关联的连通性。

    · 断链：related 指向不存在的 card_id
    · 孤立：既没有被别人引用，自己也没有 related
    · 单向：A 关联 B，但 B 没关联 A（只提示，不算错误）

    Args:
        cards: 卡片列表

    Returns:
        错误信息列表
    """
    all_ids = {c.get("card_id") for _, c in cards if c.get("card_id")}
    errors: list[str] = []
    incoming: dict[str, int] = {cid: 0 for cid in all_ids}

    for path, card in cards:
        cid = card.get("card_id")
        if not cid:
            continue
        for rel in (card.get("related") or []):
            if rel not in all_ids:
                errors.append(f"断链: {cid} → {rel}（目标卡片不存在）")
            else:
                incoming[rel] = incoming.get(rel, 0) + 1

    for path, card in cards:
        cid = card.get("card_id")
        if not cid:
            continue
        has_out = bool(card.get("related"))
        has_in = incoming.get(cid, 0) > 0
        if not has_out and not has_in:
            errors.append(f"孤立卡: {cid}（无任何关联，检索时无法串联上下文）")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="校验知识卡是否符合设计规范")
    parser.add_argument("--dir", type=str, default="data/cards", help="卡片目录")
    parser.add_argument("--verbose", "-v", action="store_true", help="输出详细信息")
    args = parser.parse_args()

    root = Path(args.dir)
    if not root.is_dir():
        print(f"❌ 目录不存在: {root}")
        return 1

    files = sorted(root.rglob("*.yaml")) + sorted(root.rglob("*.yml"))
    if not files:
        print(f"⚠️  {root} 下未找到 YAML 卡片")
        return 1

    print(f"\n📋 校验 {len(files)} 张卡片（{root}）")
    print("=" * 64)

    all_cards: list[tuple[Path, dict]] = []
    failed = 0

    for path in files:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            print(f"❌ {path.name}\n   YAML 解析失败: {str(e)[:120]}")
            failed += 1
            continue

        if not isinstance(data, dict):
            print(f"❌ {path.name}\n   顶层应为映射结构")
            failed += 1
            continue

        all_cards.append((path, data))
        errors = validate_card(data, path)

        if errors:
            failed += 1
            print(f"\n❌ {path.name}  [{data.get('card_id', '?')}]")
            for err in errors:
                print(f"   · {err}")
        elif args.verbose:
            print(f"✅ {path.name}  [{data['card_id']}]  {data['type']}")

    dup_errors = check_duplicates(all_cards)
    if dup_errors:
        failed += len(dup_errors)
        print("\n❌ 重复检查")
        for err in dup_errors:
            print(f"   · {err}")

    rel_errors = check_relations(all_cards)
    if rel_errors:
        failed += len(rel_errors)
        print("\n❌ 关联连通性检查")
        for err in rel_errors:
            print(f"   · {err}")

    print("\n" + "=" * 64)
    passed = len(files) - failed
    print(f"{'✅' if failed == 0 else '⚠️ '} 通过 {passed}/{len(files)} 张卡片")
    if failed:
        print(f"   失败 {failed} 项，请按提示修正后重跑")

    # 卡型分布
    if all_cards:
        from collections import Counter
        dist = Counter(c.get("type", "?") for _, c in all_cards)
        print("\n📊 卡型分布: " + "  ".join(f"{k}={v}" for k, v in sorted(dist.items())))

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
