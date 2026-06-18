"""Prompt 模板模块

提供各种场景的 Prompt 模板。
"""

from src.llm.prompts.classify import (
    CATEGORY_KEYWORDS,
    build_classify_prompt,
    classify_by_keywords,
)
from src.llm.prompts.enrichment import (
    build_enrichment_prompt,
)
from src.llm.prompts.qa import (
    build_qa_prompt,
    get_qa_prompt_template,
)

__all__ = [
    # QA Prompt
    "build_qa_prompt",
    "get_qa_prompt_template",
    # Enrichment Prompt
    "build_enrichment_prompt",
    # Classify Prompt
    "build_classify_prompt",
    "classify_by_keywords",
    "CATEGORY_KEYWORDS",
]
