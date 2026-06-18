"""知识丰富场景 Prompt 模板

用于将代码片段转换为通俗易懂的描述。
"""

from src.llm.templates import PromptTemplate


# ============================================================================
# 知识丰富 Prompt
# ============================================================================

ENRICHMENT_PROMPT = PromptTemplate(
    name="enrichment",
    template="""你是一个代码解读专家，擅长将前端代码转换为通俗易懂的操作说明。

请根据以下代码片段，生成通俗易懂的功能描述。

要求：
1. 用非技术人员能理解的语言描述
2. 说明这个功能的用途和操作方式
3. 如果涉及按钮、表单等，说明其位置和用途
4. 如有相关的数据字段，解释其含义
5. 描述控制在 100 字以内

=== 代码片段 ===
${code_snippet}

=== 页面信息 ===
页面名称: ${page_name}
页面路径: ${page_path}

=== 组件类型 ===
${component_type}

请生成功能描述：
"""
)


# ============================================================================
# 批量知识丰富 Prompt
# ============================================================================

BATCH_ENRICHMENT_PROMPT = PromptTemplate(
    name="batch_enrichment",
    template="""你是一个代码解读专家。请为以下多个组件生成功能描述。

要求：
1. 每个描述控制在 50 字以内
2. 用通俗易懂的语言
3. 按 JSON 格式输出

=== 页面信息 ===
页面名称: ${page_name}

=== 组件列表 ===
${components}

请按以下 JSON 格式输出（不要包含其他内容）：
[
  {"id": "组件ID", "description": "功能描述"},
  ...
]
"""
)


def build_enrichment_prompt(
    code_snippet: str,
    page_name: str = "",
    page_path: str = "",
    component_type: str = "",
) -> str:
    """
    构建知识丰富 Prompt

    Args:
        code_snippet: 代码片段
        page_name: 页面名称
        page_path: 页面路径
        component_type: 组件类型（如 el-button, el-form 等）

    Returns:
        完整的 Prompt 字符串
    """
    return ENRICHMENT_PROMPT.render(
        code_snippet=code_snippet,
        page_name=page_name or "未知",
        page_path=page_path or "未知",
        component_type=component_type or "未知",
    )
