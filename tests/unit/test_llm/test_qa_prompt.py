"""问答 Prompt 模板回归测试。

要求持续有效的两点（均来自 2026-11 实测）：
1. 清单类问题必须逐项列全 —— 模型曾对「工单有哪些类型」只答「去页面查看」，
   要点覆盖仅 72%；补上该规则后升到 100%。
2. 必须禁止代码路由、禁止套话、知识库没答案时拒答 —— 防止后续改模板时被删掉。
"""

from src.llm.prompts.qa import (
    QA_NO_KNOWLEDGE_PROMPT,
    QA_STANDARD_PROMPT,
    QA_SYSTEM_PROMPT,
    build_qa_prompt,
)


class TestQuestionPromptRules:
    """系统提示词应包含的关键规则"""

    def test_list_question_rule_present(self):
        """必须要求清单类问题逐项列出"""
        text = QA_SYSTEM_PROMPT.render()
        assert "有哪些" in text
        assert "逐项列出" in text or "每一项" in text

    def test_forbids_page_only_answer(self):
        """必须禁止只回答'去某页面查看'"""
        text = QA_SYSTEM_PROMPT.render()
        assert "禁止只回答" in text

    def test_forbids_code_routes(self):
        """必须禁止输出以 / 开头的系统路由"""
        text = QA_SYSTEM_PROMPT.render()
        assert "系统路由" in text

    def test_no_answer_fallback_rule(self):
        """知识库没答案时必须拒答，不得编造"""
        text = QA_SYSTEM_PROMPT.render()
        assert "暂时没有资料" in text
        assert "不要编造" in text

    def test_boundary_phrases_preserved(self):
        """边界话术要原样转达，不能编造配置值"""
        text = QA_SYSTEM_PROMPT.render()
        assert "边界话术" in text


class TestBuildQaPrompt:
    """构建逻辑测试"""

    def test_empty_context_uses_fallback(self):
        """没有知识时走兜底模板"""
        prompt = build_qa_prompt(question="怎么下单", knowledge_context="")
        assert "这个问题" in prompt or "没有找到" in prompt

    def test_context_rendered(self):
        """有知识时应把内容放进 Prompt"""
        prompt = build_qa_prompt(
            question="怎么下单",
            knowledge_context="【文档1】下单步骤",
        )
        assert "下单步骤" in prompt
        assert "怎么下单" in prompt
