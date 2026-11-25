"""生成回归评测的黄金集。

每条用例：问题 → 期望命中的卡片 → 答案里必须出现的关键事实。

为什么要有「必须出现的关键事实」：
    结构校验（validate_cards）和检索回归（eval_cards）都测不出
    「检索对了、答案却只说『去某页面查看』」这类缺陷。
    2026-11 实测：同一批卡片，提示词改前要点覆盖 72%，改后 97%，
    该指标是唯一能抓到这种退化的。

维护约定：
    · key_facts 取自卡片正文的原文用词，不要改写成同义词
      （否则模型用同义表述会被误判为缺失）
    · 一个事实用 2-6 个字、有区分度的词，别用「订单」这种泛词
    · 用户换个说法提问的用例（口语化）与标准问法都要有
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GoldenCase:
    """一条黄金集用例。"""

    question: str
    expected_card: str
    key_facts: tuple[str, ...] = ()
    # 期望拒答：知识库没有答案，应回答「没有资料」
    should_refuse: bool = False
    # 可接受的替代卡片：两张卡内容边界重叠时，命中任意一张都算检索正确。
    # 只用于已确认的卡片设计重叠，不要拿来放宽检索标准。
    acceptable_cards: tuple[str, ...] = ()


# ── 有答案的问题：必须命中卡片，且答案含全部关键事实 ──
GOLDEN_CASES: tuple[GoldenCase, ...] = (
    # 订单域
    GoldenCase(
        "怎么下单",
        "order-task-create",
        ("新建订单", "下单"),
    ),
    GoldenCase(
        "订单怎么创建",
        "order-task-create",
        ("新建订单",),
    ),
    GoldenCase(
        "订单都有哪些状态",
        "order-state-machine",
        ("导入", "已下单", "已取件", "运输中", "派送中", "已完成"),
    ),
    GoldenCase(
        "订单状态有哪几种",
        "order-state-machine",
        ("导入", "运输中", "已完成"),
    ),
    GoldenCase(
        "下单类型有哪些区别",
        "order-glossary-order-types",
        ("标准", "异地代发", "调拨", "退货"),
        # order-glossary-order-fields 正文也讲下单类型差异，内容边界重叠。
        # 实测命中它时要点仍 4/4 全对，是卡片设计问题而非检索退化，记在待办里。
        acceptable_cards=("order-glossary-order-fields",),
    ),
    GoldenCase(
        "下单类型怎么选",
        "order-glossary-order-types",
        ("标准", "异地代发", "调拨", "退货"),
        acceptable_cards=("order-glossary-order-fields", "order-task-create"),
    ),
    GoldenCase(
        "怎么取消订单",
        "order-rule-cancel-delete",
        ("取消",),
    ),
    GoldenCase(
        "怎么修改订单",
        "order-rule-modify-limits",
        ("修改订单信息",),
    ),
    GoldenCase(
        "怎么批量导出POD",
        "order-task-export-pod",
        ("20", "zip"),
    ),
    GoldenCase(
        "取件时间选不了",
        "order-trouble-pick-time",
        ("2",),
    ),
    # 顺店通通用
    GoldenCase(
        "工单有哪些类型",
        "sdt-glossary-ticket-types",
        ("转寄", "退回", "破损", "遗失"),
    ),
    GoldenCase(
        "月结挂账有哪几种方式",
        "sdt-glossary-monthly-billing-modes",
        ("按组织", "按成本类型", "顺丰产品", "自选"),
    ),
    GoldenCase(
        "版本有哪些套餐",
        "sdt-glossary-pricing-edition",
        ("标准版", "专业版", "高级版", "旗舰版"),
    ),
    GoldenCase(
        "怎么加员工账号",
        "sdt-task-add-account",
        ("账号",),
    ),
    GoldenCase(
        "运费预算超了会怎样",
        "sdt-rule-freight-budget",
        ("审批", "寄付现结"),
    ),
    GoldenCase(
        "库存怎么管理",
        "sdt-task-inventory-query",
        ("库存",),
    ),
    GoldenCase(
        "面单打印怎么设置",
        "sdt-task-print-settings",
        ("打印",),
    ),
    GoldenCase(
        "怎么对账",
        "sdt-task-order-reconcile",
        ("对账",),
    ),
    # 人力资源
    GoldenCase(
        "怎么发起第三方测评",
        "hr-task-create-assessment",
        ("测评",),
    ),
    GoldenCase(
        "测评怎么导入参与人员",
        "hr-task-import-participants",
        ("导入",),
    ),
)


# ── 无答案的问题：必须拒答，不能编造 ──
REFUSAL_CASES: tuple[str, ...] = (
    "我们公司现在的月结卡号是多少",
    "今天天气怎么样",
    "帮我写一首诗",
    "增值税税率是多少",
    "社保怎么交",
    "个税怎么申报",
    "Excel 求和公式怎么写",
    "顺丰股价多少",
    "电脑蓝屏怎么办",
    "年会在哪里办",
)

REFUSAL_MARKER = "没有资料"


def card_ids() -> set[str]:
    """已知卡片 ID 集合（用于校验黄金集不写错卡名）。"""
    from pathlib import Path

    from scripts.card_loader import load_cards

    return {c["card_id"] for c in load_cards(Path("data/cards"))}
