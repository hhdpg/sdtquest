#!/usr/bin/env python3
"""卡片召回验证脚本（不依赖向量库，纯本地匹配）。

用线上真实问题测试卡片能否被检索到，验证卡片设计是否解决"答得浅"。

打分逻辑已抽取到 src/rag/card_scoring.py，本脚本只负责：
  · 维护测试问题集
  · 加载卡片、调用打分器
  · 输出命中报告

用法:
    uv run scripts/eval_cards.py --dir data/cards/_demo
    uv run scripts/eval_cards.py --dir data/cards --threshold 5
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml

from src.rag.card_scoring import CardScorer

# ── 测试问题集 ──────────────────────────────────────────

# 线上真实问题（来自 data/analytics.db.question_records 去重结果）
# 这是「当前知识库尚未覆盖」的问题集，用于验证系统能否诚实地说"没资料"
REAL_QUESTIONS = [
    "怎么下单",
    "订单怎么创建",
    "订单审批流程是什么",
    "怎么批量导出POD",
    "阿迪订单页面有哪些操作按钮",
    "怎么查询所有订单",
    "库存怎么管理",
    "新增报表里没看到体积",
    "为什么权限被拒绝",
    "运单是什么",
]

# 已知缺口：这些问题需要专门的卡，但当前 demo 卡片集未覆盖。
# 评估时允许"误命中"，但应在报告中标为待补卡。
KNOWN_GAPS = {
    "怎么下单",
    "订单怎么创建",
    "订单审批流程是什么",
    "怎么批量导出POD",
    "阿迪订单页面有哪些操作按钮",
    "怎么查询所有订单",
    "库存怎么管理",
    "新增报表里没看到体积",
    "运单是什么",
}

# 本域问题：每一对都是「问题 → 应该命中的卡片」
CASES: dict[str, str] = {
    # 人力资源 / 测评
    "怎么发起第三方测评": "hr-task-create-assessment",
    "测评怎么导入参与人员": "hr-task-import-participants",
    "测评发布后还能改吗": "hr-rule-assessment-publish",
    "怎么催办没做测评的人": "hr-task-track-assessment",
    "测评状态有哪些": "hr-glossary-assessment-status",
    "选不到测评类型怎么办": "hr-trouble-no-type",
    # 顺店通通用
    "下不了单说没有权限": "sdt-trouble-no-order-permission",
    "提示缺少成本类型怎么办": "order-trouble-missing-cost-type",
    "巴枪提示月结卡号不可用": "sdt-trouble-monthly-card",
    "批量导入提示地址有错误": "sdt-trouble-import-address",
    "忘记密码登不上了": "sdt-trouble-reset-password",
    "批量下单还提示业务类型不可用": "sdt-trouble-biz-type-unavailable",
    # 同城急送
    "同城急送怎么开通": "sdt-flow-tc-service-setup",
    "同城急送开通流程": "sdt-flow-tc-service-setup",
    "同城急送怎么下单": "sdt-task-tc-order",
    "同城急送的成本类型有哪些区别": "sdt-glossary-tc-cost-type",
    "怎么判断同城急送配好了": "sdt-rule-tc-store-config",
    "店铺ID怎么配": "sdt-rule-tc-store-config",
    "同城急送下单规则怎么配": "sdt-rule-tc-order-rule",
    # 业务配置
    "怎么给下单设审批": "sdt-rule-approval-config",
    "一个组织能有几个下单规则": "sdt-rule-order-option-limit",
    "怎么新增员工账号": "sdt-task-add-account",
    "组织能删除吗": "sdt-task-add-org",
    # 订单域
    "成本类型在哪配置": "order-task-config-options",
    "成本类型是什么意思": "order-glossary-order-fields",
}


def load_cards(root: Path) -> list[dict]:
    """
    加载目录下全部卡片。

    Args:
        root: 卡片目录

    Returns:
        卡片 dict 列表
    """
    cards: list[dict] = []
    for p in sorted(list(root.rglob("*.yaml")) + list(root.rglob("*.yml"))):
        try:
            d = yaml.safe_load(p.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            print(f"⚠️  YAML 解析失败，跳过 | {p.name} | {e}")
            continue
        if isinstance(d, dict) and d.get("card_id"):
            cards.append(d)
    return cards


def run_cases(scorer: CardScorer, cards: list[dict], threshold: float | None) -> tuple[int, int]:
    """
    跑本域测试集。

    Args:
        scorer: 已 fit 的打分器
        cards: 卡片列表
        threshold: 阈值（None 用配置值）

    Returns:
        (正确数, 总数)
    """
    print("\n【本域问题】")
    ok = 0
    for q, expected in CASES.items():
        ranked = scorer.rank(q, cards, top_k=2, threshold=threshold)
        if ranked and ranked[0][1]["card_id"] == expected:
            ok += 1
            print(f"  ✅ {q}")
            print(f"       → {ranked[0][1]['card_id']} ({ranked[0][0]:.1f})")
        else:
            actual = ranked[0][1]["card_id"] if ranked else "无命中"
            print(f"  ❌ {q}")
            print(f"       → 期望 {expected}，实际 {actual}")
            if ranked:
                print(f"       → 分数 {ranked[0][0]:.1f}")
    print(f"  ── 正确 {ok}/{len(CASES)}")
    return ok, len(CASES)


def run_real_questions(
    scorer: CardScorer, cards: list[dict], threshold: float | None,
) -> tuple[int, int]:
    """
    跑线上真实问题（验证能否诚实说"没资料"）。

    Args:
        scorer: 打分器
        cards: 卡片列表
        threshold: 阈值

    Returns:
        (命中数, 总数)
    """
    print("\n【线上真实问题】（未覆盖的应诚实返回空）")
    hit = 0
    for q in REAL_QUESTIONS:
        ranked = scorer.rank(q, cards, top_k=2, threshold=threshold)
        is_gap = q in KNOWN_GAPS
        if ranked:
            hit += 1
            mark = "⚠️ " if is_gap else "✅"
            print(f"  {mark} {q}")
            print(f"       → {ranked[0][1]['card_id']} ({ranked[0][0]:.1f})")
        else:
            print(f"  ❌ {q}")
            print("       → （无命中，需补卡）")
    print(f"  ── 命中 {hit}/{len(REAL_QUESTIONS)}")
    return hit, len(REAL_QUESTIONS)


def main() -> int:
    parser = argparse.ArgumentParser(description="验证卡片召回效果")
    parser.add_argument("--dir", type=str, default="data/cards/_demo")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--threshold", type=float, default=None,
                        help="命中阈值（默认取 config/retrieval.yaml）")
    parser.add_argument("--config", type=str, default=None,
                        help="检索配置路径（默认 config/retrieval.yaml）")
    args = parser.parse_args()

    root = Path(args.dir)
    if not root.is_dir():
        print(f"❌ 目录不存在: {root}")
        return 1

    cards = load_cards(root)
    if not cards:
        print("❌ 未加载到卡片")
        return 1

    try:
        scorer = CardScorer.from_config(args.config).fit(cards)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return 1

    th = scorer.config.threshold if args.threshold is None else args.threshold
    print(f"\n🔍 加载 {len(cards)} 张卡片 | 阈值 {th} | Top-{args.top_k}")
    print("=" * 72)

    ok, total = run_cases(scorer, cards, args.threshold)
    run_real_questions(scorer, cards, args.threshold)

    rate = ok / total if total else 0
    print("\n" + "=" * 72)
    print(f"本域召回率: {rate:.0%}（{ok}/{total}）")

    return 0 if rate >= 0.95 else 1


if __name__ == "__main__":
    sys.exit(main())
