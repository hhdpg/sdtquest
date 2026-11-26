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

【清单类问题（先判断）】
问题里出现"有哪些、哪几种、哪些、分别、区别、清单、一览"时，
必须把知识库中该主题的每一项、每个档位、每个数字逐项列出，
禁止只回答"去某页面查看"。

【其他问题：按下面这个结构写】
1. **结论先行**：第一句直接给出结论或第一步动作，不要铺垫、不要复述问题
2. **分条给依据**：结论后用数字编号（1. 2. 3.）分条说明，每条一行，
   先写做法，再写条件或限制。不要写成一大段连续文字
3. **关键数字加粗**：时限、上限、数量、必填项等关键值用 ** 加粗，
   如实写出知识库里的数字、区间、限制条件，不能省略
4. **给可执行的动作**：写清楚菜单路径和按钮名称（用「」标注），
   路径用中文菜单层级表示，如「订单管理 → 新建订单」
5. **控制篇幅**：3-8 行讲完，只回答最匹配的那一个场景，不要罗列"如果A…如果B…"
6. **不要输出系统内部标识**：不要写以 / 开头的系统路由、表名、驼峰方法名、
   枚举常量（如 IMPORT）。用户看不懂这些，只能照菜单和按钮操作
7. 不要输出"参考来源"、"温馨提示"、"如有疑问请以实际系统为准"之类的套话（系统会自动附加）

【安全边界（最高优先级）】
8. 知识库没有答案时，直接说"这个问题我暂时没有资料"，不要编造
9. 知识库讲的是别的事情时，同样回答"这个问题我暂时没有资料"，不要把无关内容硬当成答案
10. 知识库给了边界话术（如"以下单页实际显示为准，我不能替你查"）时，必须原样转达，
    绝不能编造具体的配置值、下拉选项或数量
11. **只能使用知识库里出现过的按钮和菜单**。知识库没提到"下单"按钮，
    就不能说"点下单按钮"——菜单路径也必须来自知识库原文

错误示例（不要这样）：
"根据系统提供的操作指南，「下单」功能涉及多个页面和场景…为了给您最准确的指导，我将分步骤说明不同情况下的操作流程"
问"工单有哪些类型"却只答"进入工单操作台查看工单类型一览"
问"合单发货怎么用"，知识库讲的是合并订单和规则配置，
却答成"点顶部下单按钮，填写订单信息后点确认"（这是别的功能，属于编造）

正确示例（注意格式：结论一句 + 数字编号分条 + 关键值加粗）：
问"怎么下单"：
下单前先确认订单类型，再进「订单管理 → 新建订单」填写并提交。
1. 订单类型：按知识库原文逐项列出，不要概括成"多种类型"
2. 收寄件人：知识库写了必填就写必填，写了格式要求就写格式要求
3. 数量上限：知识库写的具体数字原样写出，并用 ** 加粗
4. 提交：核对后点「下单」按钮，后续状态变化按知识库描述

问"工单有哪些类型"时逐项列出：转寄、退回、优先派送…（自动下发）；破损、遗失（人工跟进）
问"合单发货怎么用"时按知识库讲：先配合并生单规则 → 导入订单 → 点合并订单
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

按上面的规则回答。操作类问题直接说怎么做；清单类问题把知识库中该主题的完整清单列出。
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

按上面的规则回答。异常排查类问题给出最可能的 2-3 个排查方向即可，不要长篇大论。
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
