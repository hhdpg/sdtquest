"""问题分类场景 Prompt 模板

用于对用户问题进行自动分类。
"""

from src.llm.templates import PromptTemplate


# ============================================================================
# 问题分类 Prompt
# ============================================================================

CLASSIFY_PROMPT = PromptTemplate(
    name="classify",
    template="""你是一个问题分类助手。请判断用户问题属于以下哪个类别：

1. operation_guide（操作指南）- 询问如何操作、在哪里操作、步骤是什么
   示例：怎么创建订单？在哪里导出报表？如何修改密码？

2. process_inquiry（流程咨询）- 询问业务流程、审批步骤、先后顺序
   示例：采购审批流程是怎样的？提交后经过哪些步骤？

3. anomaly_troubleshoot（异常排查）- 询问报错、失败原因、问题排查
   示例：为什么提示权限不足？提交订单报错怎么办？页面加载失败？

4. general（其他/闲聊）- 不属于以上类别的问题
   示例：你好、谢谢、今天天气怎么样？

=== 用户问题 ===
${question}

请只输出类别名称（operation_guide / process_inquiry / anomaly_troubleshoot / general），不要输出其他内容。
"""
)


# ============================================================================
# 带上下文的问题分类 Prompt
# ============================================================================

CLASSIFY_WITH_CONTEXT_PROMPT = PromptTemplate(
    name="classify_with_context",
    template="""你是一个问题分类助手。请根据用户问题及其上下文判断问题类别。

类别说明：
1. operation_guide（操作指南）- 询问如何操作、功能使用
2. process_inquiry（流程咨询）- 询问业务流程、审批流程
3. anomaly_troubleshoot（异常排查）- 询问报错、问题排查
4. general（其他/闲聊）

=== 对话历史 ===
${conversation_history}

=== 当前问题 ===
${question}

请只输出类别名称，不要输出其他内容。
"""
)


# 分类类别关键词（用于规则匹配兜底）
CATEGORY_KEYWORDS = {
    "operation_guide": [
        "怎么", "如何", "在哪里", "步骤", "操作", "使用", "功能",
        "创建", "删除", "修改", "添加", "查看", "导出", "导入",
    ],
    "process_inquiry": [
        "流程", "审批", "步骤", "先后", "顺序", "经过", "之后",
        "然后", "接下来", "第一", "第二步",
    ],
    "anomaly_troubleshoot": [
        "报错", "失败", "为什么", "不了", "无法", "错误", "异常",
        "问题", "怎么办", "怎么回事", "不能",
    ],
    "general": [
        "你好", "谢谢", "再见", "早上好", "下午好",
    ],
}


def build_classify_prompt(question: str) -> str:
    """
    构建问题分类 Prompt

    Args:
        question: 用户问题

    Returns:
        完整的 Prompt 字符串
    """
    return CLASSIFY_PROMPT.render(question=question)


def classify_by_keywords(question: str) -> str:
    """
    使用关键词匹配进行问题分类（规则兜底）

    Args:
        question: 用户问题

    Returns:
        分类结果，如果无法匹配则返回 general
    """
    question_lower = question.lower()

    # 按优先级检查各类别
    for category in [
        "anomaly_troubleshoot",  # 异常排查优先
        "process_inquiry",       # 流程咨询次之
        "operation_guide",       # 操作指南
        "general",               # 闲聊
    ]:
        keywords = CATEGORY_KEYWORDS.get(category, [])
        for keyword in keywords:
            if keyword in question_lower:
                return category

    # 默认返回 general
    return "general"
