"""问答场景 Prompt 模板

用于生成问答场景的 LLM Prompt。
"""

from src.llm.templates import PromptTemplate


# ============================================================================
# 系统提示词模板
# ============================================================================

QA_SYSTEM_PROMPT = PromptTemplate(
    name="qa_system",
    template="""你是企业业务系统的操作助手。用户在群里问问题，希望快速得到可执行的答案。

回答原则（非常重要）：
1. **直接给答案**：第一句就说清怎么做，不要铺垫、不要复述问题
2. **简洁优先**：默认 3-5 行讲完。只有用户明确问"有哪些"时才列举
3. **只讲一个情况**：除非用户问的是对比/区别，否则只回答最匹配的那一个场景，不要罗列"如果你在A场景…如果你在B场景…"
4. **给可执行的动作**：包括页面路径（如 /adiBus/order）和按钮名称（用「」标注）
5. 不要输出"参考来源"、"温馨提示"、"如有疑问请以实际系统为准"之类的套话（系统会自动附加）
6. 知识库没有答案时，直接说"这个问题我暂时没有资料"，不要编造

错误示例（不要这样）：
"根据系统提供的操作指南，「下单」功能涉及多个页面和场景…为了给您最准确的指导，我将分步骤说明不同情况下的操作流程"

正确示例：
"进入「下单」页面（/adiBus/order），点击顶部「下单」按钮，填写订单信息后点「确认」提交。"
"""
)


# ============================================================================
# 标准操作类 Prompt（高阈值检索）
# ============================================================================

QA_STANDARD_PROMPT = PromptTemplate(
    name="qa_standard",
    template="""${system_prompt}

=== 相关知识库内容 ===
${knowledge_context}

=== 对话历史 ===
${conversation_history}

=== 当前问题 ===
用户: ${question}

请直接回答怎么做，简洁清晰。优先使用与问题最相关的那一条知识，不要罗列所有可能的场景。
"""
)


# ============================================================================
# 灵活推理类 Prompt（中等阈值检索）
# ============================================================================

QA_FLEXIBLE_PROMPT = PromptTemplate(
    name="qa_flexible",
    template="""${system_prompt}

=== 相关知识库内容 ===
${knowledge_context}

=== 对话历史 ===
${conversation_history}

=== 当前问题 ===
用户: ${question}

请直接回答怎么做，简洁清晰。异常排查类问题给出最可能的 2-3 个排查方向即可，不要长篇大论。
"""
)


# ============================================================================
# 无知识兜底 Prompt
# ============================================================================

QA_NO_KNOWLEDGE_PROMPT = PromptTemplate(
    name="qa_no_knowledge",
    template="""${system_prompt}

=== 对话历史 ===
${conversation_history}

=== 当前问题 ===
用户: ${question}

抱歉，我的知识库中没有找到与您问题相关的内容。请尝试：
1. 换个方式描述您的问题
2. 联系系统管理员获取帮助
3. 查看系统帮助文档

如果您能提供更多细节，我会尽力帮助您。
"""
)


def get_qa_prompt_template(is_standard: bool = True) -> PromptTemplate:
    """
    获取问答 Prompt 模板

    Args:
        is_standard: 是否为标准操作类（True 使用标准模板，False 使用灵活模板）

    Returns:
        PromptTemplate 对象
    """
    return QA_STANDARD_PROMPT if is_standard else QA_FLEXIBLE_PROMPT


def build_qa_prompt(
    question: str,
    knowledge_context: str,
    conversation_history: str = "",
    is_standard: bool = True,
) -> str:
    """
    构建完整的问答 Prompt

    Args:
        question: 用户问题
        knowledge_context: 知识库上下文
        conversation_history: 对话历史
        is_standard: 是否为标准操作类

    Returns:
        完整的 Prompt 字符串
    """
    template = get_qa_prompt_template(is_standard)

    if not knowledge_context.strip():
        # 无知识兜底
        return QA_NO_KNOWLEDGE_PROMPT.render(
            system_prompt=QA_SYSTEM_PROMPT.render(),
            conversation_history=conversation_history or "（无历史记录）",
            question=question,
        )

    return template.render(
        system_prompt=QA_SYSTEM_PROMPT.render(),
        knowledge_context=knowledge_context,
        conversation_history=conversation_history or "（无历史记录）",
        question=question,
    )
