"""上下文组装器单元测试模块。

测试 ContextAssembler 的 Prompt 组装逻辑。
"""

import pytest

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


class TestContextAssemblerDedup:
    """向量库文档头去重测试

    向量库存的 document 是 to_document_string() 产物，已含
    「标题/页面/路径/内容/标签」。组装 Prompt 若再拼一遍，每张卡白占约 150 字。
    """

    def test_strip_header_removes_title_and_tags(self):
        """应剥掉标题/页面/路径/标签，只留正文"""
        raw = (
            "标题: 工单有哪些类型？\n"
            "页面: 顺店通\n"
            "路径: 工单管理 → 工单操作台\n"
            "内容: 转寄、退回、破损、遗失\n"
            "标签: 工单类型, 自动工单"
        )
        body = ContextAssembler._strip_document_header(raw)
        assert body == "转寄、退回、破损、遗失"

    def test_strip_header_keeps_plain_content(self):
        """非该格式的纯正文应原样返回"""
        assert ContextAssembler._strip_document_header("普通正文") == "普通正文"

    def test_titles_not_duplicated_in_context(self):
        """组装后的上下文里，标题只出现一次"""
        raw = "标题: 唯一标题XYZ\n页面: 模块A\n路径: 菜单 → 子菜单\n内容: 正文内容\n标签: t1"
        doc = make_doc(title="唯一标题XYZ", content=raw)
        context = ContextAssembler()._build_knowledge_context([doc])
        assert context.count("唯一标题XYZ") == 1


class TestContextAssemblerEntryPath:
    """菜单入口路径测试

    知识卡片的 page_path 是中文菜单层级，是用户唯一能照做的定位；
    代码解析知识的 page_path 是 URL / 前端路由，必须过滤。
    """

    def test_chinese_menu_path_kept(self):
        """中文菜单路径应进入上下文"""
        doc = KnowledgeItem(
            id="k1", type=KnowledgeType.MANUAL, title="导出POD",
            content="标题: 导出POD\n页面: 订单\n路径: 订单管理 → 订单列表\n内容: 勾选后点导出",
            page_path="订单管理 → 订单列表",
        )
        context = ContextAssembler()._build_knowledge_context([doc])
        assert "订单管理 → 订单列表" in context

    def test_url_path_filtered(self):
        """URL 形式的路径不应出现（业务人员看不懂）"""
        doc = KnowledgeItem(
            id="k1", type=KnowledgeType.MANUAL, title="某页面",
            content="内容",
            page_path="https://talent.sf-express.com/static-portal/#/",
        )
        context = ContextAssembler()._build_knowledge_context([doc])
        assert "talent.sf-express.com" not in context

    def test_route_path_filtered(self):
        """前端路由（以 / 开头）不应出现"""
        doc = KnowledgeItem(
            id="k1", type=KnowledgeType.MANUAL, title="某页面",
            content="内容",
            page_path="/adiBus/order",
        )
        context = ContextAssembler()._build_knowledge_context([doc])
        assert "/adiBus/order" not in context

    def test_entry_path_survives_header_strip(self):
        """剥掉文档头后，page_path 仍要单独保留"""
        doc = KnowledgeItem(
            id="k1", type=KnowledgeType.MANUAL, title="状态",
            content="标题: 状态\n页面: 订单\n路径: 订单管理 → 订单列表\n内容: 导入→已完成",
            page_path="订单管理 → 订单列表",
        )
        context = ContextAssembler()._build_knowledge_context([doc])
        assert "入口: 订单管理 → 订单列表" in context
        assert context.count("订单管理 → 订单列表") == 1


class TestContextAssemblerBudget:
    """上下文长度预算按 provider 区分测试"""

    class _FakeManager:
        def __init__(self, provider):
            self.current = provider

    def test_glm_budget_is_larger(self):
        """GLM 窗口大，单篇上限应高于本地模型"""
        from src.config import settings

        assert settings.RAG_MAX_DOC_CHARS_GLM > settings.RAG_MAX_DOC_CHARS
        assert settings.RAG_MAX_CONTEXT_CHARS_GLM > settings.RAG_MAX_CONTEXT_CHARS

    def test_long_doc_kept_under_glm(self):
        """超过本地单篇上限的内容，在 GLM 下不应被截断"""
        from src.config import settings

        long_body = "正" * (settings.RAG_MAX_DOC_CHARS + 500)
        doc = make_doc(content=long_body)

        glm_ctx = ContextAssembler(
            provider_manager=self._FakeManager("glm")
        )._build_knowledge_context([doc])
        local_ctx = ContextAssembler(
            provider_manager=self._FakeManager("local")
        )._build_knowledge_context([doc])

        assert "已截断" not in glm_ctx
        assert "已截断" in local_ctx


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


class TestContextLengthControl:
    """上下文长度控制测试

    回归保护: RAG prompt 曾达到 13000+ 字符，超过 Ollama 默认 num_ctx(4096)，
    导致 9B 模型只输出前几个字（如仅"根据"两字）。
    """

    def test_long_doc_is_truncated(self):
        """单篇超长文档应被截断"""
        from src.config import settings
        from src.rag.context import ContextAssembler

        assembler = ContextAssembler()
        long_content = "订单流程说明。" * 2000  # 远超单篇上限
        doc = KnowledgeItem(
            id="k1", type=KnowledgeType.MANUAL, title="订单",
            content=long_content,
        )

        context = assembler._build_knowledge_context([doc])

        assert len(context) <= settings.RAG_MAX_DOC_CHARS + 200  # 留出标题/标签余量
        assert "内容过长已截断" in context

    def test_total_context_respects_limit(self):
        """多篇文档合计不应超过总上限"""
        from src.config import settings
        from src.rag.context import ContextAssembler

        assembler = ContextAssembler()
        docs = [
            KnowledgeItem(
                id=f"k{i}", type=KnowledgeType.MANUAL, title=f"文档{i}",
                content="内容" * 900,  # 每篇接近单篇上限
            )
            for i in range(10)
        ]

        context = assembler._build_knowledge_context(docs)

        assert len(context) <= settings.RAG_MAX_CONTEXT_CHARS + 300

    def test_short_docs_not_truncated(self):
        """短文档应完整保留"""
        from src.rag.context import ContextAssembler

        assembler = ContextAssembler()
        doc = KnowledgeItem(
            id="k1", type=KnowledgeType.MANUAL, title="订单",
            content="订单创建流程：先校验再入库。",
        )

        context = assembler._build_knowledge_context([doc])

        assert "订单创建流程：先校验再入库。" in context
        assert "已截断" not in context
