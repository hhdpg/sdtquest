#!/usr/bin/env python3
"""卡片召回验证脚本（不依赖向量库，纯本地匹配）。

用线上真实问题测试卡片能否被检索到，验证卡片设计是否解决"答得浅"。

打分逻辑已抽取到 src/rag/card_scoring.py，本脚本只负责：
  · 维护测试问题集
  · 加载卡片、调用打分器
  · 输出命中报告

用法:
    uv run scripts/eval_cards.py --dir data/cards
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

# 已知缺口：这些问题需要专门的卡，但当前卡片集未覆盖。
# 评估时允许"误命中"，但应在报告中标为待补卡。
# 2026-11-24 补卡后：下单/审批/POD/运单等已有卡，仅剩下列真实缺口。
KNOWN_GAPS = {
    "阿迪订单页面有哪些操作按钮",   # 阿迪定制页，无通用卡
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
    # 月结
    "月结卡号怎么验证": "sdt-task-verify-monthly-account",
    "月结账号未校验怎么办": "sdt-task-verify-monthly-account",
    "月结号是怎么挂的": "sdt-glossary-monthly-billing-modes",
    "按组织挂月结还是按成本类型挂": "sdt-glossary-monthly-billing-modes",
    # 打印与权限
    "面单打印怎么设置": "sdt-task-print-settings",
    "支持什么打印机": "sdt-task-print-settings",
    "数据安全怎么配": "sdt-rule-data-security",
    "为什么有的脱敏有的没脱敏": "sdt-rule-data-security",
    "角色权限怎么配": "sdt-rule-role-permission",
    "员工登录后按钮点不了": "sdt-rule-role-permission",
    # FAQ 报错
    "提示系统异常请联系管理员": "sdt-trouble-system-exception",
    "报请求入参对象转换失败": "sdt-trouble-input-convert-fail",
    "提示没有当前用户电话号码信息": "sdt-trouble-no-phone",
    "导入用户报导入excle出错": "sdt-trouble-import-excel-error",
    "提示下单方式不符合": "sdt-trouble-order-method-mismatch",
    "下单失败没有具体原因": "sdt-trouble-order-fail-no-reason",
    "小程序查快递提示用户无权访问": "sdt-trouble-miniapp-no-access",
    "为什么会出现重复运单号": "sdt-trouble-duplicate-waybill",
    # 新业务域
    "怎么给客户开通商户": "sdt-task-open-merchant",
    "提示来源单号已存在": "sdt-rule-merchant-source-unique",
    "监控预警规则怎么设": "sdt-task-monitoring-rule",
    "工单处理流程是怎样的": "sdt-flow-ticket-process",
    "新建工单提示未查到关联订单": "sdt-trouble-ticket-not-found",
    "订单对账怎么做": "sdt-task-order-reconcile",
    "各个版本有什么区别": "sdt-glossary-pricing-edition",
    "场景码怎么配置": "sdt-task-scenario-code",
    "企业微信授权怎么配": "sdt-task-wecom-auth",
    "月结卡号维护是什么": "sdt-glossary-monitoring-monthly-card",
    # 查询/报表/库存
    "怎么查询所有运单": "order-task-query-waybill",
    "运单列表怎么导出": "order-task-query-waybill",
    "我的报表怎么建": "sdt-task-custom-report",
    "报表取数字段没有体积": "sdt-task-custom-report",
    "库存怎么查询": "sdt-task-inventory-query",
    # 2026-11-24 第二轮补卡（前后端代码比对）
    "怎么批量下单": "order-task-batch-import",
    "批量导入运单有什么限制": "order-task-batch-import",
    "订单下单后还能改吗": "order-rule-modify-limits",
    "改订单地址有什么限制": "order-rule-modify-limits",
    "月结付款码怎么用": "sdt-task-month-paycode",
    "到付件怎么挂月结": "sdt-task-month-paycode",
    "运费预算怎么配": "sdt-rule-freight-budget",
    "超预算了会怎样": "sdt-rule-freight-budget",
    "客户退货能用寄付月结吗": "order-rule-customer-return-monthly",
    "标准下单和调拨下单有什么区别": "order-glossary-order-types",
    "异地代发和客户退货区别": "order-glossary-order-types",
    "快速收单是什么": "sdt-flow-quick-receipt",
    "收单码怎么用": "sdt-flow-quick-receipt",
    "门店要货单怎么走": "sdt-flow-requisition",
    "要货超时自动拒单": "sdt-flow-requisition",
    "店铺怎么创建": "sdt-task-shop-manage",
    "店铺停用有什么影响": "sdt-task-shop-manage",
    "商品中心是干什么的": "sdt-task-product-center",
    "地址簿怎么用": "sdt-task-address-book",
    "为什么看不到别人的地址": "sdt-task-address-book",
    "到齐派怎么用": "sdt-flow-requirement-plan",
    "需求单怎么变成运单": "sdt-flow-requirement-plan",
    "工单有哪些类型": "sdt-glossary-ticket-types",
    "哪些工单自动处理": "sdt-glossary-ticket-types",
    # ── 开放接口域（客户技术对接，2026-11-25 新增 23 张卡）──
    "对接接口前要准备什么": "sdt-api-how-to-get-appid",
    "appId和密钥从哪来": "sdt-api-how-to-get-appid",
    "签名怎么算": "sdt-api-sign-howto",
    "签名一直不通过": "sdt-api-sign-howto",
    "接口报时间戳超时": "sdt-api-timestamp-window",
    "时间戳有什么要求": "sdt-api-timestamp-window",
    "参数异常和签名错误怎么区分": "sdt-api-auth-error-diff",
    "接口都报参数异常分不清": "sdt-api-auth-error-diff",
    "下单失败一般是什么原因": "sdt-api-create-order-fail-reasons",
    "下单报错但订单还在": "sdt-api-order-created-but-failed",
    "下单接口报错订单还在已导入": "sdt-api-order-created-but-failed",
    "重复提交会下重单吗": "sdt-api-idempotent-scope",
    "有没有幂等": "sdt-api-idempotent-scope",
    "箱号有什么规则": "sdt-api-boxno-rules",
    "接口下单箱号重复报错": "sdt-api-boxno-rules",
    "接口传月结卡报未验证": "sdt-api-monthly-card-check",
    "超预算下单会被拦吗": "sdt-api-freight-budget-block",
    "统一下单几个接口区别": "sdt-api-order-variant-diff",
    "标准下单和店配下单区别": "sdt-api-order-variant-diff",
    "子单号怎么申请": "sdt-api-sub-order-apply",
    "申请子单被拒": "sdt-api-sub-order-apply",
    "预下单接口干什么": "sdt-api-preorder-times",
    "国补订单有什么要求": "sdt-api-subsidy-order-rules",
    "取消订单为什么不能取消": "sdt-api-cancel-state-machine",
    "取消订单报订单不存在": "sdt-api-cancel-state-machine",
    "取消订单用哪个接口": "sdt-api-cancel-v1-v2-diff",
    "三方快递怎么取消": "sdt-api-cancel-v1-v2-diff",
    "订单确认接口是干什么的": "sdt-api-confirm-order",
    "订单放行和退回怎么调": "sdt-api-delivery-trigger",
    "时效查询怎么算的": "sdt-api-deliver-tm",
    "时效和账单对不上": "sdt-api-deliver-tm",
    "运单号校验是校验什么": "sdt-api-waybill-validate",
    "清单运费查询怎么查": "sdt-api-freight-query",
    "地址解析报地址不规范": "sdt-api-address-identify",
    "下单结果查询报取消订单失败": "sdt-api-order-search",
    "调度信息查询一次能查多少": "sdt-api-schedule-query",
    "接口查月结卡下有哪些运单": "sdt-api-monthly-waybill-query",
    "路由查询接口两个版本区别": "sdt-api-route-query-v1-v2",
    "路由查询查不到": "sdt-api-route-query-v1-v2",
    "全渠道路由查询为什么要钱": "sdt-api-route-pay-query",
    "路由推送一条都没收到": "sdt-api-route-push",
    "云打印pdf打不开": "sdt-api-cloud-print",
    "O2O取号走丰门还是顺丰": "sdt-api-oto-take-number",
    "插件打印最多几张": "sdt-api-oto-print",
    "O2O拦截接口怎么用": "sdt-api-oto-interceptor",
    "怎么获取电子面单模板": "sdt-api-print-template",
    "月结码怎么生成": "sdt-api-monthly-code",
    "第三方token怎么获取": "sdt-api-third-token",
    "时间戳超时到底是15分钟还是3分钟": "sdt-api-timeout-vs-token-window",
    "同城创建订单会不会重复下单": "sdt-api-tc-create-order",
    "同城订单什么时候不能取消": "sdt-api-tc-cancel-order",
    "同城回调状态码什么意思": "sdt-api-tc-callback-status",
    "同城回调必须返回什么": "sdt-api-tc-callback-return",
    "同城回调没收到": "sdt-api-tc-callback-not-received",
    "同城状态流和实时信息区别": "sdt-api-tc-order-flow",
    "接口推送店铺经纬度没收到": "sdt-api-shop-push-trouble",
    "清单运费推送没收到": "sdt-api-fee-push-trouble",
    "推送失败会重试几次": "sdt-api-push-retry-mechanism",
    "阿迪收方信息怎么接": "sdt-api-adi-receiver-push",
    "接口报错该不该重试": "sdt-api-error-code-retryable",
    "开放接口对接需要配置哪些": "sdt-api-config-where",
    "路由推送要配哪几项": "sdt-api-route-push-config",
    "运费推送要配什么": "sdt-api-fee-push-config",
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
    parser.add_argument("--dir", type=str, default="data/cards")
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
