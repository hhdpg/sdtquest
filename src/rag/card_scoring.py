"""卡片检索打分模块。

承载「九条防误召回规则」，供正式检索器与评估脚本共用。
所有业务配置从 config/retrieval.yaml 读取，新业务接入只改配置不改代码。

九条规则：
  1. 泛化词不给分        —— 出现在多数卡里的词单独命中不计分
  2. 泛化词兜底          —— 问题全由泛化词构成时降权但保留召回
  3. 中文 n-gram 碎片过滤 —— 过滤"么批"这类跨词边界碎片
  4. 跨字段去重计分      —— 同一 token 在 title/one_liner/anchors 只计一次
  5. 标题命中加权        —— title 是最精确的语义标签
  6. IDF 自动降权        —— 按文档频率降低高频词权重
  7. 业务域隔离          —— 问题与卡片域无交集时大幅降权
  8. 卡型意图一致性      —— 意图与卡型不符时降权
  9. 反向动作排除        —— 问"导出"不命中讲"导入"的卡

典型用法:
    >>> from src.rag.card_scoring import CardScorer
    >>> scorer = CardScorer.from_config()
    >>> scorer.fit(cards)                       # 计算 IDF
    >>> results = scorer.rank("怎么下单", cards)  # 返回 [(score, card), ...]
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from loguru import logger

DEFAULT_CONFIG_PATH = Path("config/retrieval.yaml")

# 疑问/虚词片段：n-gram 产生的跨词边界碎片特征。
# 含这些字的短 token 基本不可能是有意义的业务词。
# "怎"：如"报销单怎么填"里的"单怎"，跨词边界无意义，且会误命中任何含"单"的卡。
FRAGMENT_CHARS = ("么", "样", "哪", "怎")


@dataclass(frozen=True)
class RetrievalConfig:
    """检索评分配置（从 YAML 加载后的不可变快照）"""

    ngram_sizes: tuple[int, ...]
    stopwords: frozenset[str]
    generic_tokens: frozenset[str]
    troubleshoot_markers: frozenset[str]
    intents: dict[str, tuple[frozenset[str], frozenset[str]]]
    domains: dict[str, frozenset[str]]
    opposite_actions: tuple[frozenset[str], ...]
    weights: dict[str, float]
    threshold: float
    small_corpus_size: int
    # 规则10：专属域。这些域只服务特定人群（如技术对接人问开放接口），
    # 普通业务问题不该命中它们，即使卡片正文里出现了业务词。
    exclusive_domains: frozenset[str] = frozenset()
    # 属于专属域的卡片模块名（按卡片的 module 字段精确匹配）
    exclusive_modules: frozenset[str] = frozenset()


def load_config(path: str | Path | None = None) -> RetrievalConfig:
    """
    从 YAML 加载检索配置。

    Args:
        path: 配置文件路径，默认 config/retrieval.yaml

    Returns:
        RetrievalConfig 实例

    Raises:
        FileNotFoundError: 配置文件不存在
        ValueError: 配置格式错误
    """
    import yaml

    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        raise FileNotFoundError(f"检索配置文件不存在: {cfg_path}")

    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"配置文件格式错误（顶层应为映射）: {cfg_path}")

    tok = raw.get("tokenizer") or {}
    thresholds = raw.get("thresholds") or {}

    intents: dict[str, tuple[frozenset[str], frozenset[str]]] = {}
    for name, spec in (raw.get("intents") or {}).items():
        markers = frozenset(spec.get("markers") or [])
        card_types = frozenset(spec.get("card_types") or [])
        if not markers:
            logger.warning("意图缺少 markers，已跳过 | intent={}", name)
            continue
        intents[name] = (markers, card_types)

    domains: dict[str, frozenset[str]] = {}
    for name, spec in (raw.get("domains") or {}).items():
        kws = frozenset((spec or {}).get("keywords") or [])
        if not kws:
            logger.warning("业务域缺少 keywords，已跳过 | domain={}", name)
            continue
        domains[name] = kws

    opposites = tuple(
        frozenset(pair) for pair in (raw.get("opposite_actions") or [])
        if isinstance(pair, (list, tuple)) and len(pair) == 2
    )

    return RetrievalConfig(
        ngram_sizes=tuple(tok.get("ngram_sizes") or (2, 3, 4)),
        stopwords=frozenset(tok.get("stopwords") or []),
        generic_tokens=frozenset(raw.get("generic_tokens") or []),
        troubleshoot_markers=frozenset(raw.get("troubleshoot_markers") or []),
        intents=intents,
        domains=domains,
        opposite_actions=opposites,
        weights=dict(raw.get("weights") or {}),
        threshold=float(thresholds.get("keyword_score", 3.0)),
        small_corpus_size=int(thresholds.get("small_corpus_size", 50)),
        exclusive_domains=frozenset(raw.get("exclusive_domains") or []),
        exclusive_modules=frozenset(raw.get("exclusive_modules") or []),
    )


@lru_cache(maxsize=4)
def _cached_config(path_str: str) -> RetrievalConfig:
    """配置缓存，避免重复读盘"""
    return load_config(path_str)


def get_config(path: str | Path | None = None) -> RetrievalConfig:
    """获取（带缓存的）检索配置"""
    return _cached_config(str(path or DEFAULT_CONFIG_PATH))


# 老 KnowledgeType → 七类卡型的映射。
# 历史数据（page/workflow/manual 等）接入新检索时按此归一到卡型，
# 否则意图匹配（依赖卡型）会完全失效。
LEGACY_TYPE_MAP: dict[str, str] = {
    "page": "task",        # 页面说明 ≈ 任务卡
    "button": "task",
    "form": "task",
    "workflow": "flow",    # 流程说明 ≈ 流程卡
    "api": "rule",         # 接口约定 ≈ 规则
    "manual": "faq",       # 手动文档 归入问答
}

CARD_TYPES = frozenset({
    "glossary", "task", "rule", "state", "trouble", "flow", "faq",
})


def card_to_dict(item: object) -> dict:
    """
    把 KnowledgeItem 适配成 CardScorer 需要的 dict。

    KnowledgeItem 的字段与卡片 schema 不同（content vs body，tags vs anchors），
    这里做一次映射，让正式检索器无需改造数据模型即可复用打分逻辑。

    Args:
        item: KnowledgeItem 实例或已符合 schema 的 dict

    Returns:
        标准化卡片 dict
    """
    if isinstance(item, dict):
        return item

    raw_type = getattr(getattr(item, "type", None), "value", "manual")
    card_type = raw_type if raw_type in CARD_TYPES else LEGACY_TYPE_MAP.get(raw_type, "faq")

    tags = getattr(item, "tags", None) or []
    return {
        "card_id": getattr(item, "id", ""),
        "type": card_type,
        "title": getattr(item, "title", ""),
        # 老 KnowledgeItem 没有 one_liner，用 content 首句兜底
        "one_liner": getattr(item, "one_liner", "") or _first_sentence(
            getattr(item, "content", "")
        ),
        "body": getattr(item, "content", ""),
        "anchors": list(tags),
        "module": getattr(item, "module", "") or "",
    }


def _first_sentence(text: str, limit: int = 80) -> str:
    """取文本首句，用于 one_liner 兜底"""
    if not text:
        return ""
    for sep in ("。", "\n", "！", "？"):
        idx = text.find(sep)
        if 0 < idx <= limit:
            return text[:idx]
    return text[:limit]


class CardScorer:
    """
    卡片检索打分器。

    封装九条规则，对外只暴露 rank()/score()。
    业务配置全部来自 RetrievalConfig，无任何业务硬编码。

    Attributes:
        config: 检索配置
        idf: token → IDF 系数（需先调用 fit）
    """

    def __init__(self, config: RetrievalConfig):
        """
        初始化打分器。

        Args:
            config: 检索配置
        """
        self.config = config
        self.idf: dict[str, float] = {}
        self._fitted_size: int = 0
        self.w = config.weights

    @classmethod
    def from_config(cls, path: str | Path | None = None) -> "CardScorer":
        """从配置文件创建打分器"""
        return cls(get_config(path))

    # ── 分词（规则3）──────────────────────────────────
    def tokenize(self, text: str) -> set[str]:
        """
        中文 n-gram 分词，过滤无意义碎片。

        Args:
            text: 待分词文本

        Returns:
            token 集合
        """
        tokens: set[str] = set()
        stop = self.config.stopwords

        for m in re.findall(r"[A-Za-z][A-Za-z0-9_]*|\d+", text):
            tokens.add(m.lower())

        for seg in re.findall(r"[\u4e00-\u9fff]+", text):
            for size in self.config.ngram_sizes:
                if len(seg) < size:
                    continue
                for i in range(len(seg) - size + 1):
                    tok = seg[i:i + size]
                    if tok in stop:
                        continue
                    # 规则3：过滤跨词边界碎片（"么批""是什"）
                    if any(c in tok for c in FRAGMENT_CHARS):
                        continue
                    tokens.add(tok)

        return tokens

    # ── IDF（规则6）───────────────────────────────────
    def fit(self, cards: list[dict]) -> "CardScorer":
        """
        根据卡片集合计算 IDF。

        出现在越多卡片里的 token 区分度越低。

        ⚠️ IDF 必须基于**全库**计算，不能对候选子集重复计算，
        否则同一张卡在不同候选池里会得到不同分数，导致排序不稳定。
        若传入卡片数与上次 fit 相同，复用已有 IDF。

        Args:
            cards: 全部卡片

        Returns:
            self（便于链式调用）
        """
        if self.idf and self._fitted_size == len(cards):
            return self

        doc_freq: Counter[str] = Counter()
        for card in cards:
            text = " ".join([
                str(card.get("title", "")),
                str(card.get("one_liner", "")),
                " ".join(str(a) for a in (card.get("anchors") or [])),
            ])
            for tok in self.tokenize(text):
                doc_freq[tok] += 1

        total = max(len(cards), 1)
        self.idf = {
            tok: math.log((total + 1) / (freq + 1)) + 0.3
            for tok, freq in doc_freq.items()
        }
        self._fitted_size = len(cards)
        return self

    # ── 意图与域识别（规则7、8）────────────────────────
    def detect_intents(self, question: str) -> set[str]:
        """识别问题命中的动作意图"""
        return {
            name for name, (markers, _) in self.config.intents.items()
            if any(m in question for m in markers)
        }

    def is_troubleshoot(self, question: str) -> bool:
        """判断是否为排障类问题"""
        return any(m in question for m in self.config.troubleshoot_markers)

    def detect_domains(self, question: str) -> set[str]:
        """识别问题所属业务域"""
        return {
            name for name, kws in self.config.domains.items()
            if any(kw in question for kw in kws)
        }

    def card_domains(self, card: dict) -> set[str]:
        """识别卡片所属业务域"""
        text = self._card_text(card)
        return {
            name for name, kws in self.config.domains.items()
            if any(kw in text for kw in kws)
        }

    # ── 主评分入口 ────────────────────────────────────
    def score(self, question: str, card: dict) -> float:
        """
        计算问题与卡片的匹配分。

        Args:
            question: 用户问题
            card: 卡片数据（dict）

        Returns:
            匹配分，越高越相关
        """
        w = self.w
        q_tokens = self.tokenize(question)
        if not q_tokens:
            return 0.0

        # 规则1：泛化词不给分；
        # 规则2：若全是泛化词，退化使用但整体降权
        discriminant = q_tokens - self.config.generic_tokens
        degraded = False
        if not discriminant:
            discriminant = q_tokens
            degraded = True

        # 规则4：跨字段去重，同一 token 只取最高权重
        field_texts = [
            (str(card.get("one_liner", "")), w.get("one_liner", 3.0)),
            (str(card.get("title", "")), w.get("title", 2.5)),
            (" ".join(str(a) for a in (card.get("anchors") or [])), w.get("anchors", 2.0)),
        ]
        best_weight: dict[str, float] = {}
        for text, weight in field_texts:
            for tok in discriminant & self.tokenize(text):
                best_weight[tok] = max(best_weight.get(tok, 0.0), weight)

        total = 0.0
        if best_weight:
            total = sum(
                self.idf.get(tok, 1.0) * weight
                for tok, weight in best_weight.items()
            ) / (len(discriminant) ** 0.5)

        # 规则5：标题命中加权
        title_hits = discriminant & self.tokenize(str(card.get("title", "")))
        if title_hits:
            coverage = len(title_hits) / len(discriminant)
            total *= 1.0 + coverage * w.get("title_coverage_boost", 0.6)

        # 规则8：意图与卡型对齐
        card_type = card.get("type", "")
        intents = self.detect_intents(question)
        if best_weight and intents:
            for name in intents:
                _, card_types = self.config.intents[name]
                total *= (w.get("intent_match", 1.5) if card_type in card_types
                          else w.get("intent_miss", 0.75))

        # 卡型意图一致性
        is_trouble = self.is_troubleshoot(question)
        if card_type == "trouble" and not is_trouble:
            total *= w.get("trouble_without_marker", 0.25)
        elif card_type in ("task", "flow") and is_trouble:
            total *= w.get("task_flow_with_marker", 0.6)

        # body 作弱信号
        body_tokens = self.tokenize(str(card.get("body", "")))
        body_hits = discriminant & body_tokens
        if body_hits:
            total += w.get("body", 0.3) * sum(
                self.idf.get(tok, 1.0) for tok in body_hits
            ) / (len(discriminant) ** 0.5)

        # 规则9：反向动作
        if self._has_opposite_action(question, self._card_text(card)):
            total *= w.get("opposite_action", 0.2)

        # 规则7：业务域隔离
        q_domains = self.detect_domains(question)
        c_domains = self.card_domains(card)
        if q_domains and c_domains and not (q_domains & c_domains):
            total *= w.get("domain_conflict", 0.15)
        elif q_domains and not c_domains:
            total *= w.get("domain_unknown", 0.7)

        # 规则10：专属域隔离
        # 开放接口卡正文会大量出现「订单」「取消」等业务词，因此也会被规则7
        # 判为「订单」域，于是一条业务问题「怎么取消订单」会被接口卡抢走首位。
        # 这里按「问题是否命中该专属域」再降一次权：接口问题不受影响，
        # 业务问题则把接口卡压到业务卡之下。
        #
        # 判定用卡片的 module 而非正文关键词：业务卡的 source_ref/正文也会
        # 提到「开放接口」，用关键词会让业务卡误中降权。
        card_module = str(card.get("module", "")).strip()
        if card_module in self.config.exclusive_modules:
            if not (q_domains & self.config.exclusive_domains):
                total *= w.get("exclusive_domain_miss", 0.55)

        # 规则2：泛化词兜底
        if degraded:
            total *= w.get("degraded", 0.5)
            # 兜底模式下所有卡都只靠泛化词命中，极易同分。
            # 决胜依据依次为：title 完整包含问题 > one_liner 以问题词开头。
            total += self._degraded_tiebreak(question, card) * 0.8

        return total

    def _degraded_tiebreak(self, question: str, card: dict) -> float:
        """
        泛化词兜底模式下的同分决胜。

        判定顺序（信息量由强到弱）：
          1.0  title 完整包含问题原文（"怎么下单" 出现在 title 里）
          0.6  title 的问题词占比高
          0.3  one_liner 以问题词开头

        Args:
            question: 用户问题
            card: 卡片

        Returns:
            0–1 的决胜分
        """
        q = question.strip().rstrip("？?。.")
        title = str(card.get("title", ""))
        one_liner = str(card.get("one_liner", ""))

        if q and q in title:
            return 1.0

        q_tokens = self.tokenize(question)
        if not q_tokens:
            return 0.0

        title_hits = q_tokens & self.tokenize(title)
        if title_hits:
            coverage = len(title_hits) / len(q_tokens)
            # title 是用户问法的浓缩，覆盖率越高越贴合
            return 0.3 + 0.3 * coverage

        if one_liner.startswith(tuple(q_tokens)):
            return 0.3
        return 0.0

    def rank(
        self,
        question: str,
        cards: list[dict],
        top_k: int = 3,
        threshold: float | None = None,
    ) -> list[tuple[float, dict]]:
        """
        对卡片排序并返回 Top-K。

        Args:
            question: 用户问题
            cards: 候选卡片
            top_k: 返回条数
            threshold: 命中阈值，默认取配置值

        Returns:
            [(分数, 卡片), ...]，按分数降序，已过滤低于阈值的
        """
        th = self.config.threshold if threshold is None else threshold
        # 小语料自适应：卡片数少时 IDF 差异小、命中词权重低，
        # 沿用大库阈值会把有效结果全部滤掉。按语料规模线性下调。
        if threshold is None and len(cards) < self.config.small_corpus_size:
            ratio = len(cards) / max(self.config.small_corpus_size, 1)
            th = self.config.threshold * max(ratio, 0.15)
        ranked = [(self.score(question, c), c) for c in cards]
        # 同分决胜：title 完整包含问题原文的卡优先（title 是用户问法的浓缩）。
        # 避免"提示缺少成本类型"时订单卡与同城卡并列、排序随机。
        q_norm = question.strip().rstrip("？?。.")
        ranked.sort(
            key=lambda x: (x[0], self._exact_title_bonus(q_norm, x[1])),
            reverse=True,
        )
        return [(s, c) for s, c in ranked[:top_k] if s > th]

    @staticmethod
    def _exact_title_bonus(question: str, card: dict) -> int:
        """title 是否完整包含问题原文（仅用于同分排序）"""
        if question and question in str(card.get("title", "")):
            return 1
        return 0

    # ── 内部辅助 ──────────────────────────────────────
    @staticmethod
    def _card_text(card: dict) -> str:
        """拼接卡片全部可检索文本"""
        return " ".join([
            str(card.get("title", "")),
            str(card.get("one_liner", "")),
            " ".join(str(a) for a in (card.get("anchors") or [])),
            str(card.get("body", "")),
        ])

    def _has_opposite_action(self, question: str, card_text: str) -> bool:
        """检测问题与卡片是否为相反方向的动作"""
        for pair in self.config.opposite_actions:
            a, b = tuple(pair)
            q_a, q_b = a in question, b in question
            c_a, c_b = a in card_text, b in card_text
            if q_a and not q_b and c_b and not c_a:
                return True
            if q_b and not q_a and c_a and not c_b:
                return True
        return False

