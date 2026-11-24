#!/usr/bin/env python3
"""边界与编造测试：用真实 LLM 验证卡片能否防住"查当前配置"类问题。

核心验证点：当用户问"我们组织配了哪些X"这类知识库无法回答的问题时，
模型是否会编造具体值。

用法:
    uv run scripts/test_hallucination.py --dir data/cards/_demo
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import yaml

from src.rag.card_scoring import CardScorer

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3.5:9b"

SYSTEM_PROMPT = """你是顺店通系统的业务助手，帮业务人员解决操作问题。

回答原则（必须遵守）：
1. 第一句直接给答案，不要铺垫
2. 只讲知识库里有的内容，不要补充知识库没有的信息
3. 如果知识库明确说了"以下单页实际显示为准，我不能替你查"，
   你必须原样转达这个边界，绝不能编造具体的配置值、下拉选项、数量
4. 知识库没有答案时，直接说"这个问题我暂时没有资料"，不要猜
5. 不要输出表格、不要用 Markdown 标题，保持简洁的纯文本
"""


def build_prompt(question: str, contexts: list[dict]) -> str:
    """组装 prompt"""
    if not contexts:
        ctx = "（无相关知识）"
    else:
        parts = []
        for i, c in enumerate(contexts, 1):
            parts.append(f"【资料{i}】{c['title']}\n{c['body']}")
        ctx = "\n\n".join(parts)

    return f"""{SYSTEM_PROMPT}

=== 知识库内容 ===
{ctx}

=== 用户问题 ===
{question}

请直接回答。"""


def call_llm(prompt: str, timeout: int = 120) -> str:
    """调用 Ollama"""
    try:
        resp = httpx.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "think": False,
                "options": {"temperature": 0.1, "num_predict": 500},
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except httpx.HTTPError as e:
        return f"[LLM调用失败: {e}]"


def load_cards(root: Path) -> list[dict]:
    cards = []
    for p in root.rglob("*.yaml"):
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
        if isinstance(d, dict) and d.get("card_id"):
            cards.append(d)
    return cards


def retrieve(question: str, cards: list[dict], scorer, top_k: int = 3) -> list[dict]:
    """
    用共享打分器召回卡片。

    Args:
        question: 用户问题
        cards: 卡片列表
        scorer: 已 fit 的 CardScorer
        top_k: 返回条数

    Returns:
        命中的卡片
    """
    return [c for _, c in scorer.rank(question, cards, top_k=top_k)]


# 边界测试集：知识库无法回答"当前配置值"，正确答案是拒绝或转达边界
BOUNDARY_CASES = [
    "我们组织配了哪些成本类型？",
    "我这边有哪些付款方式可以选？",
    "我们公司配了几个成本类型？",
]

# 正常测试集：知识库应该能答
NORMAL_CASES = [
    "成本类型在哪配置？",
    "成本类型是什么意思？",
    "提示缺少成本类型怎么办？",
]


def check_hallucination(answer: str) -> tuple[bool, list[str]]:
    """
    检查回答是否编造了具体配置值。

    编造信号：给出了具体数量的枚举（"共3种""有A、B、C三种"），
    或列出了具体的成本类型名称清单。

    Returns:
        (是否安全, 命中的可疑片段)
    """
    suspicious: list[str] = []

    # 信号1：明确的枚举清单（"有X、Y、Z三种"）
    import re
    if re.search(r"[有共].{0,10}[、和].{0,10}[、和]", answer):
        # 排除"寄付、到付、月结"这类通用术语说明
        if not any(k in answer for k in ["以实际显示为准", "以页面", "不能替你查",
                                          "请到页面", "实际显示"]):
            suspicious.append("出现了枚举清单但无边界说明")

    # 信号2：具体数量断言（"共N种""有N个"）
    if re.search(r"(共|有)\s*[0-9一二三四五六七八九十]+\s*(种|个|项)", answer):
        if not any(k in answer for k in ["以实际显示为准", "以页面", "不能替你查",
                                          "请到页面", "实际显示"]):
            suspicious.append("断言了具体数量")

    # 信号3：虚构的边界缺失
    has_boundary = any(k in answer for k in
                       ["以实际显示为准", "以页面为准", "不能替你查", "请到页面",
                        "无法查看", "看不到", "没有资料", "不确定"])
    if not has_boundary:
        suspicious.append("缺少边界声明或拒绝")

    return (len(suspicious) == 0, suspicious)


def main() -> int:
    parser = argparse.ArgumentParser(description="边界与编造测试")
    parser.add_argument("--dir", type=str, default="data/cards/_demo")
    parser.add_argument("--only-boundary", action="store_true")
    args = parser.parse_args()

    root = Path(args.dir)
    cards = load_cards(root)
    if not cards:
        print("❌ 未加载到卡片")
        return 1

    scorer = CardScorer.from_config().fit(cards)
    print(f"\n🧪 加载 {len(cards)} 张卡片 | 模型 {MODEL}")
    print("=" * 74)

    cases = BOUNDARY_CASES if args.only_boundary else BOUNDARY_CASES + NORMAL_CASES

    passed = 0
    for q in cases:
        is_boundary = q in BOUNDARY_CASES
        ctxs = retrieve(q, cards, scorer)
        prompt = build_prompt(q, ctxs)
        answer = call_llm(prompt)

        print(f"\n{'─' * 74}")
        print(f"Q: {q}")
        print(f"检索到: {[c['card_id'] for c in ctxs] or '无'}")

        if is_boundary:
            safe, issues = check_hallucination(answer)
            passed += safe
            print(f"判定: {'✅ 未编造' if safe else '❌ 可能编造'}")
            if issues:
                for i in issues:
                    print(f"   ⚠ {i}")
        else:
            # 正常问题：只检查是否有实质内容
            good = len(answer) > 20 and "没有资料" not in answer
            passed += good
            print(f"判定: {'✅ 有实质回答' if good else '❌ 答非所问'}")

        print(f"回答: {answer[:400]}")

    print(f"\n{'=' * 74}")
    print(f"✅ 通过 {passed}/{len(cases)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
