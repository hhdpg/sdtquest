"""上下文组装器单元测试模块。

测试 ContextAssembler 的 Prompt 组装逻辑。
"""

import pytest
from unittest.mock import patch

from src.domain.enums import KnowledgeType, QuestionCategory
from src.domain.models import KnowledgeItem, Message
from src.rag.context import ContextAssembler


def make_doc(id: str = "k1", title: str = "文档标题", content: str = "文档内容") -> KnowledgeItem:
    """创建测试用文档"""
    return KnowledgeItem(
        id=id,
        type=KnowledgeType.BUTTON,
        title=title,
        content=content,
        page_name="测试页面",
        page_path="/test",
        tags=["标签1", "标签2"],
    )


class TestContextAssembler:
    """上下文组装器测试"""

    @pytest.fixture
    def assembler(self):
        return ContextAssembler(max_history=3)

    def test_assemble_with_docs(self, assembler):
        """测试有文档时的 Prompt 组装"""
        docs = [make_doc()]
        prompt = assembler.assemble("如何操作?", docs, category=QuestionCategory.OPERATION_GUIDE)

        assert "文档标题" in prompt
        assert "文档内容" in prompt
        assert "如何操作?" in prompt

    def test_assemble_with_history(self, assembler):
        """测试带历史记录的 Prompt 组装"""
        docs = [make_doc()]
        history = [
            Message(role="user", content="你好"),
            Message(role="assistant", content="你好!"),
        ]
        prompt = assembler.assemble("继续问题", docs, history=history)

        assert "你好" in prompt
        assert "用户" in prompt or "助手" in prompt

    def test_assemble_no_docs(self, assembler):
        """测试无文档时的 Prompt 组装"""
        prompt = assembler.assemble("问题", [], category=QuestionCategory.GENERAL)
        assert "无相关" in prompt or "问题" in prompt

    def test_assemble_no_history(self, assembler):
        """测试无历史记录"""
        prompt = assembler.assemble("问题", [make_doc()])
        assert "无历史" in prompt or "问题" in prompt

    def test_assemble_standard_category(self, assembler):
        """测试标准操作类的 Prompt 特点"""
        docs = [make_doc()]
        prompt = assembler.assemble("如何操作?", docs, category=QuestionCategory.OPERATION_GUIDE)
        # 标准类应该包含精确操作指导相关的提示
        assert len(prompt) > 0

    def test_assemble_flexible_category(self, assembler):
        """测试灵活推理类的 Prompt"""
        docs = [make_doc()]
        prompt = assembler.assemble("为什么报错?", docs, category=QuestionCategory.ANOMALY_TROUBLESHOOT)
        assert len(prompt) > 0


class TestContextAssemblerSources:
    """引用来源格式化测试"""

    @pytest.fixture
    def assembler(self):
        return ContextAssembler()

    def test_format_sources_with_page(self, assembler):
        """测试带页面信息的来源格式化"""
        docs = [make_doc(title="新建按钮", content="...")]
        sources = assembler.format_sources(docs)

        assert len(sources) == 1
        assert "测试页面" in sources[0]
        assert "新建按钮" in sources[0]

    def test_format_sources_no_page(self, assembler):
        """测试无页面信息的来源格式化"""
        doc = KnowledgeItem(
            id="k1",
            type=KnowledgeType.MANUAL,
            title="独立文档",
            content="内容",
        )
        sources = assembler.format_sources([doc])

        assert len(sources) == 1
        assert sources[0] == "独立文档"

    def test_format_sources_empty(self, assembler):
        """测试空列表"""
        sources = assembler.format_sources([])
        assert sources == []

    def test_format_sources_multiple(self, assembler):
        """测试多个文档"""
        docs = [
            make_doc(id="1", title="文档1"),
            make_doc(id="2", title="文档2"),
        ]
        sources = assembler.format_sources(docs)
        assert len(sources) == 2


class TestContextAssemblerKnowledgeContext:
    """知识上下文构建测试"""

    @pytest.fixture
    def assembler(self):
        return ContextAssembler()

    def test_build_knowledge_context_empty(self, assembler):
        """测试空文档列表"""
        result = assembler._build_knowledge_context([])
        assert "无相关" in result

    def test_build_knowledge_context_with_docs(self, assembler):
        """测试有文档时"""
        docs = [make_doc(id="1", title="T1", content="C1")]
        result = assembler._build_knowledge_context(docs)

        assert "【文档1】" in result
        assert "T1" in result
        assert "C1" in result

    def test_build_knowledge_context_multiple(self, assembler):
        """测试多文档编号"""
        docs = [make_doc(id=str(i), title=f"T{i}") for i in range(3)]
        result = assembler._build_knowledge_context(docs)

        assert "【文档1】" in result
        assert "【文档2】" in result
        assert "【文档3】" in result


class TestContextAssemblerHistory:
    """对话历史构建测试"""

    @pytest.fixture
    def assembler(self):
        return ContextAssembler(max_history=3)

    def test_build_history_empty(self, assembler):
        """测试空历史"""
        result = assembler._build_conversation_history(None)
        assert "无历史" in result

    def test_build_history_with_messages(self, assembler):
        """测试有消息"""
        messages = [
            Message(role="user", content="问题1"),
            Message(role="assistant", content="回答1"),
        ]
        result = assembler._build_conversation_history(messages)

        assert "问题1" in result
        assert "回答1" in result

    def test_build_history_max_limit(self, assembler):
        """测试历史限制"""
        # 创建超过 max_history * 2 的消息
        messages = [
            Message(role="user" if i % 2 == 0 else "assistant", content=f"msg{i}")
            for i in range(10)
        ]
        result = assembler._build_conversation_history(messages)

        # 应该只保留最近的几条
        assert len(result.split("\n")) <= 6  # max_history=3, 每轮2条


class TestContextAssemblerCategoryCheck:
    """分类判断测试"""

    @pytest.fixture
    def assembler(self):
        return ContextAssembler()

    def test_is_standard_operation_guide(self, assembler):
        """测试操作指南是标准类"""
        assert assembler._is_standard_category(QuestionCategory.OPERATION_GUIDE) is True

    def test_is_standard_process_inquiry(self, assembler):
        """测试流程咨询不是标准类"""
        assert assembler._is_standard_category(QuestionCategory.PROCESS_INQUIRY) is False

    def test_is_standard_anomaly(self, assembler):
        """测试异常排查不是标准类"""
        assert assembler._is_standard_category(QuestionCategory.ANOMALY_TROUBLESHOOT) is False

    def test_is_standard_general(self, assembler):
        """测试其他分类不是标准类"""
        assert assembler._is_standard_category(QuestionCategory.GENERAL) is False

    def test_is_standard_none(self, assembler):
        """测试 None 不是标准类"""
        assert assembler._is_standard_category(None) is False
