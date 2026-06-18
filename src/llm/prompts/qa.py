"""问答场景 Prompt 模板

用于生成问答场景的 LLM Prompt。
"""

from src.llm.templates import PromptTemplate


# ============================================================================
# 系统提示词模板
# ============================================================================

QA_SYSTEM_PROMPT = PromptTemplate(
    name="qa_system",
    template="""你是企业业务系统的智能问答助手，负责解答用户关于系统操作、业务流程和异常排查的问题。

回答要求：
1. 用中文回答，条理清晰，分步骤说明
2. 如果涉及具体页面或按钮，明确指出位置（用「」标注）
3. 优先基于提供的知识库内容回答，不确定时诚实告知
4. 回答末尾附上参考来源（如果有）
5. 如有必要，添加免责声明："如有疑问请以实际系统为准"
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

请基于上述知识库内容，给出准确、详细的回答。如果知识库中没有相关信息，请诚实告知用户。
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

请结合知识库内容和你自己的理解，给出合理的回答。对于异常排查类问题，可以提供排查思路和可能的解决方案。
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
