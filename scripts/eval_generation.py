#!/usr/bin/env python3
"""生成层回归评测：卡片 → 检索 → Prompt → LLM → 答案质量。

为什么需要这一层：
    validate_cards.py 只查卡片格式，eval_cards.py 只查关键词命中，
    test_e2e.py 只查向量召回。三者都测不出「检索正确、答案却只说
    『去某页面查看』」——2026-11 实测该缺陷导致要点覆盖只有 72%。

指标：
    · 检索 top1 命中率 —— 期望卡片是否排在第一位
    · 要点覆盖率     —— 答案里出现了多少关键事实（核心指标）
    · 拒答率         —— 知识库没有的问题是否正确说「没有资料」
    · 枚举泄漏数     —— 答案里出现了几个英文常量/表名/路由
    · 平均字数       —— 防止为凑要点把答案写成长篇

用法:
    # 评测 GLM（默认读 .env 的 LLM_PROVIDER）
    uv run scripts/eval_generation.py --provider glm

    # 两个 provider 对照，防止只为一家调参
    uv run scripts/eval_generation.py --compare

    # 作为门禁：不达标退出码 1
    uv run scripts/eval_generation.py --provider glm --gate
"""

import argparse
import asyncio
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from scripts.golden_cases import (
    GOLDEN_CASES,
    REFUSAL_CASES,
    REFUSAL_MARKER,
    GoldenCase,
)

# 需要检测的「系统内部标识」只有三类，都是业务人员看不懂的：
#   1. 蛇形枚举常量（IMPORT / ALREADY_CREATE_ORDER / REVIEW_PASS）
#   2. 驼峰字段名（customerOrderNo / monthlyCardUuid）
#   3. 前端路由（/adiBus/order / united-store-ms…/#/login）
# 注意：WMS / POD / O2O / API / SKU / HRMI 这类是业务术语（系统名、
# 产品名），业务人员本来就在用，不算泄漏，不能误报。
LEAK_PATTERNS = (
    # 下划线连接的枚举：至少两段全大写，或单段但足够长
    re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b"),
    re.compile(r"\b[A-Z]{6,}\b"),
    re.compile(r"\b[a-z]+[A-Z][a-zA-Z0-9]{2,}\b"),
    re.compile(r"(?<![\w/])/[a-zA-Z][a-zA-Z0-9/]{4,}"),
)

# 业务方认可、可以出现在答案里的英文缩写（白名单）
ALLOWED_TERMS = frozenset({"JSON"})

# 门禁阈值（2026-11 GLM 实测基线：要点 97%、拒答 100%）
GATE_KEY_FACT_RATE = 0.95
GATE_REFUSAL_RATE = 1.0
GATE_MAX_LEAKS = 0


@dataclass
class CaseResult:
    """单条用例结果。"""

    question: str
    expected_card: str
    retrieved_card: str = ""
    answer: str = ""
    key_facts_total: int = 0
    key_facts_hit: int = 0
    leaked: list[str] = field(default_factory=list)
    # 被视为检索正确的卡片集合（期望卡 + 内容重叠的替代卡）
    acceptable: tuple[str, ...] = ()

    @property
    def retrieve_ok(self) -> bool:
        return (
            self.retrieved_card == self.expected_card
            or self.retrieved_card in self.acceptable
        )

    @property
    def facts_ok(self) -> bool:
        return self.key_facts_hit == self.key_facts_total


@dataclass
class ProviderReport:
    """单个 provider 的汇总结果。"""

    provider: str
    cases: list[CaseResult] = field(default_factory=list)
    refusals: list[tuple[str, str, bool]] = field(default_factory=list)

    @property
    def retrieve_rate(self) -> float:
        if not self.cases:
            return 0.0
        return sum(1 for c in self.cases if c.retrieve_ok) / len(self.cases)

    @property
    def key_fact_rate(self) -> float:
        total = sum(c.key_facts_total for c in self.cases)
        if total == 0:
            return 0.0
        return sum(c.key_facts_hit for c in self.cases) / total

    @property
    def refusal_rate(self) -> float:
        if not self.refusals:
            return 0.0
        return sum(1 for _, _, ok in self.refusals if ok) / len(self.refusals)

    @property
    def leak_count(self) -> int:
        return sum(len(c.leaked) for c in self.cases)

    @property
    def avg_chars(self) -> float:
        answered = [len(c.answer) for c in self.cases if c.answer]
        return sum(answered) / len(answered) if answered else 0.0

    def gate_failures(self) -> list[str]:
        """返回未通过的门禁项（空列表表示全部通过）。"""
        failures: list[str] = []
        if self.key_fact_rate < GATE_KEY_FACT_RATE:
            failures.append(
                f"要点覆盖率 {self.key_fact_rate:.0%} < {GATE_KEY_FACT_RATE:.0%}"
            )
        if self.refusal_rate < GATE_REFUSAL_RATE:
            failures.append(
                f"拒答率 {self.refusal_rate:.0%} < {GATE_REFUSAL_RATE:.0%}"
            )
        if self.leak_count > GATE_MAX_LEAKS:
            failures.append(f"枚举泄漏 {self.leak_count} 处 > {GATE_MAX_LEAKS}")
        return failures


def find_leaks(text: str) -> list[str]:
    """
    找出答案中泄漏的内部标识。

    Args:
        text: LLM 答案

    Returns:
        去重后的泄漏片段
    """
    found: set[str] = set()
    for pattern in LEAK_PATTERNS:
        found.update(pattern.findall(text))
    return sorted(t for t in found if t not in ALLOWED_TERMS)


async def evaluate_case(
    case: GoldenCase, pipeline, llm, repeats: int = 1
) -> CaseResult:
    """
    跑一条黄金集用例。

    同一 Prompt 多次生成时模型可能不稳定（实测「收单商品怎么上架」
    5 次里有 1 次编造了不存在的按钮）。repeats>1 时取**最差一次**的结果，
    这样偶发退化不会被平均值掩盖。

    Args:
        case: 用例
        pipeline: RAGPipeline
        llm: 当前 provider 的 LLM 客户端
        repeats: 同一条用例生成几次

    Returns:
        CaseResult
    """
    from src.domain.models import Question
    from src.domain.ports import GenerateOptions

    result = CaseResult(
        question=case.question,
        expected_card=case.expected_card,
        key_facts_total=len(case.key_facts),
        acceptable=case.acceptable_cards,
    )

    question = Question(
        text=case.question, sender_id="eval", conversation_id="eval"
    )
    rag = await pipeline.query(question)

    if not rag.documents:
        return result

    result.retrieved_card = rag.documents[0].id

    worst_hit = -1
    worst_answer = ""
    worst_leaks: list[str] = []
    for _ in range(max(1, repeats)):
        answer = (
            await llm.generate(rag.prompt, GenerateOptions(temperature=0.3))
        ).strip()

        hit = sum(1 for fact in case.key_facts if fact in answer)
        leaks = find_leaks(answer)

        # 命中更少 → 更差；命中相同但有泄漏、此前没泄漏 → 更差
        is_worse = (
            worst_hit < 0
            or hit < worst_hit
            or (hit == worst_hit and leaks and not worst_leaks)
        )
        if is_worse:
            worst_hit = hit
            worst_answer = answer
            worst_leaks = leaks

    result.key_facts_hit = max(worst_hit, 0)
    result.answer = worst_answer
    result.leaked = worst_leaks

    if not result.retrieve_ok:
        logger.warning(
            "检索未命中期望卡 | question={} | expected={} | got={}",
            case.question, case.expected_card, result.retrieved_card,
        )

    return result


async def evaluate_refusal(question: str, pipeline, llm) -> tuple[str, str, bool]:
    """
    跑一条拒答用例。

    Args:
        question: 无答案的问题
        pipeline: RAGPipeline
        llm: LLM 客户端

    Returns:
        (问题, 答案, 是否正确拒答)
    """
    from src.domain.models import Question
    from src.domain.ports import GenerateOptions

    q = Question(text=question, sender_id="eval", conversation_id="eval")
    rag = await pipeline.query(q)

    if not rag.documents:
        # 检索阶段就判定无知识，等价于正确拒答
        return question, "（检索未命中）", True

    answer = (await llm.generate(rag.prompt, GenerateOptions(temperature=0.3))).strip()
    return question, answer, REFUSAL_MARKER in answer


async def run_provider(provider: str, repeats: int = 1) -> ProviderReport:
    """
    跑完一个 provider 的全部用例。

    Args:
        provider: local / glm
        repeats: 每条用例生成几次（取最差一次）

    Returns:
        ProviderReport
    """
    from src.llm.factory import LLMProviderManager
    from src.rag.context import ContextAssembler
    from src.rag.pipeline import RAGPipeline
    from src.rag.retriever import HybridRetriever

    manager = LLMProviderManager(provider)
    pipeline = RAGPipeline(
        retriever=HybridRetriever(provider_manager=manager),
        context_assembler=ContextAssembler(provider_manager=manager),
    )

    report = ProviderReport(provider=provider)
    for case in GOLDEN_CASES:
        report.cases.append(
            await evaluate_case(case, pipeline, manager.llm, repeats=repeats)
        )
        print(f"  · {case.question}")

    for question in REFUSAL_CASES:
        report.refusals.append(
            await evaluate_refusal(question, pipeline, manager.llm)
        )

    return report


def print_report(report: ProviderReport) -> None:
    """打印单个 provider 的详细结果。"""
    print(f"\n{'=' * 68}")
    print(f"provider = {report.provider}")
    print(f"{'=' * 68}")

    print(f"\n【有答案的问题】{len(report.cases)} 条")
    for c in report.cases:
        mark = "✅" if c.retrieve_ok and c.facts_ok else "❌"
        detail = f"{c.key_facts_hit}/{c.key_facts_total}"
        print(f"  {mark} {c.question[:22]:24s} 要点{detail:5s} {len(c.answer):3d}字")
        if not c.retrieve_ok:
            print(f"       检索: 期望 {c.expected_card}，实际 {c.retrieved_card or '未命中'}")
        if c.leaked:
            print(f"       枚举泄漏: {c.leaked}")
        if c.key_facts_hit < c.key_facts_total:
            print(f"       答案: {c.answer[:120]}")

    print(f"\n【无答案的问题】{len(report.refusals)} 条")
    for question, answer, ok in report.refusals:
        mark = "✅" if ok else "❌"
        print(f"  {mark} {question[:22]:24s} {answer[:60]}")

    print(f"\n{'-' * 68}")
    print(f"检索 top1 命中率  {report.retrieve_rate:6.1%}")
    print(f"要点覆盖率        {report.key_fact_rate:6.1%}")
    print(f"拒答率            {report.refusal_rate:6.1%}")
    print(f"枚举泄漏          {report.leak_count:6d} 处")
    print(f"平均回答字数      {report.avg_chars:6.0f}")


def print_comparison(reports: list[ProviderReport]) -> None:
    """打印多 provider 对照表。"""
    print(f"\n{'=' * 68}")
    print("对照表")
    print(f"{'=' * 68}")
    header = f"{'指标':<18s}" + "".join(
        f"{r.provider:>12s}" for r in reports
    )
    print(header)
    rows = (
        ("检索 top1 命中", lambda r: f"{r.retrieve_rate:.0%}"),
        ("要点覆盖", lambda r: f"{r.key_fact_rate:.0%}"),
        ("拒答率", lambda r: f"{r.refusal_rate:.0%}"),
        ("枚举泄漏", lambda r: str(r.leak_count)),
        ("平均字数", lambda r: f"{r.avg_chars:.0f}"),
    )
    for label, getter in rows:
        print(f"{label:<18s}" + "".join(f"{getter(r):>12s}" for r in reports))


async def main_async(args) -> int:
    """入口。"""
    providers = ["local", "glm"] if args.compare else [args.provider]

    reports: list[ProviderReport] = []
    for provider in providers:
        extra = f"，每条生成 {args.repeats} 次取最差" if args.repeats > 1 else ""
        print(f"\n>>> 评测 {provider}（{len(GOLDEN_CASES)} 条黄金集 "
              f"+ {len(REFUSAL_CASES)} 条拒答{extra}）")
        reports.append(await run_provider(provider, repeats=args.repeats))

    for report in reports:
        print_report(report)

    if len(reports) > 1:
        print_comparison(reports)

    if not args.gate:
        return 0

    failed = False
    print(f"\n{'=' * 68}")
    print("门禁结果")
    print(f"{'=' * 68}")
    for report in reports:
        failures = report.gate_failures()
        if failures:
            failed = True
            print(f"❌ {report.provider}")
            for f in failures:
                print(f"   - {f}")
        else:
            print(f"✅ {report.provider} 全部通过")

    return 1 if failed else 0


def main() -> int:
    """命令行入口。"""
    from src.config import settings

    parser = argparse.ArgumentParser(description="生成层回归评测")
    parser.add_argument(
        "--provider",
        choices=["local", "glm"],
        default=settings.LLM_PROVIDER,
        help=f"评测哪个 provider（默认取配置 {settings.LLM_PROVIDER}）",
    )
    parser.add_argument(
        "--compare", action="store_true", help="同时评测 local 与 glm 并对照"
    )
    parser.add_argument(
        "--gate", action="store_true", help="作为门禁运行，不达标退出码 1"
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="每条用例生成几次并取最差结果。模型存在随机性，"
             "门禁建议用 3，避免偶发编造被平均值掩盖",
    )
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr, level="ERROR")

    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
