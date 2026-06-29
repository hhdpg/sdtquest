"""知识构建器单元测试"""

from pathlib import Path

import pytest

from src.domain.enums import KnowledgeType
from src.parser.builder import KnowledgeBuilder
from src.parser.models import (
    APIInfo,
    ButtonInfo,
    DialogInfo,
    FormField,
    FormInfo,
    PageInfo,
    ParseResult,
    TableColumn,
    TableInfo,
)


class TestKnowledgeBuilder:
    """KnowledgeBuilder 单元测试"""

    @pytest.fixture
    def builder(self) -> KnowledgeBuilder:
        return KnowledgeBuilder()

    @pytest.fixture
    def sample_page(self) -> PageInfo:
        """创建示例页面"""
        return PageInfo(
            name="订单管理",
            path="/order/list",
            component_path="@/views/order/list",
            source_file="src/views/order/list.vue",
            buttons=[
                ButtonInfo(text="新建", event="handleCreate", button_type="primary"),
                ButtonInfo(text="导出", event="handleExport"),
            ],
            forms=[
                FormInfo(
                    model="form",
                    fields=[
                        FormField(name="orderNo", label="订单编号", field_type="input", required=True),
                        FormField(name="customer", label="客户名称", field_type="input"),
                    ],
                ),
            ],
            tables=[
                TableInfo(
                    data="tableData",
                    columns=[
                        TableColumn(prop="orderNo", label="订单编号"),
                        TableColumn(prop="status", label="状态"),
                    ],
                ),
            ],
            dialogs=[
                DialogInfo(title="新建订单", visible="dialogVisible"),
            ],
            store_modules=["order/fetchList"],
            api_calls=["getOrderList"],
        )

    @pytest.fixture
    def api_def(self) -> APIInfo:
        return APIInfo(
            function_name="getOrderList",
            method="get",
            url="/api/orders",
        )

    # ====================================================================
    # 页面文档构建
    # ====================================================================

    def test_build_page_document(self, builder: KnowledgeBuilder, sample_page: PageInfo) -> None:
        """测试生成页面综合文档"""
        parse_result = ParseResult(pages=[sample_page])
        items = builder.build(parse_result)

        assert len(items) == 1
        item = items[0]
        assert item.type == KnowledgeType.PAGE
        assert "订单管理" in item.title
        assert item.page_name == "订单管理"
        assert item.page_path == "/order/list"

        # 内容应包含页面说明、按钮、表单、表格、弹窗
        assert "页面说明" in item.content
        assert "新建" in item.content
        assert "订单编号" in item.content
        assert "tableData" in item.content
        assert "新建订单" in item.content

    def test_build_with_api_relation(
        self,
        builder: KnowledgeBuilder,
        sample_page: PageInfo,
        api_def: APIInfo,
    ) -> None:
        """测试关联 API 信息"""
        parse_result = ParseResult(pages=[sample_page], api_definitions=[api_def])
        items = builder.build(parse_result)

        assert len(items) == 1
        assert "关联接口" in items[0].content
        assert "getOrderList" in items[0].content
        assert "GET" in items[0].content

    def test_build_tags(self, builder: KnowledgeBuilder, sample_page: PageInfo) -> None:
        """测试标签生成"""
        parse_result = ParseResult(pages=[sample_page])
        items = builder.build(parse_result)

        tags = items[0].tags
        assert "订单管理" in tags
        assert "新建" in tags

    # ====================================================================
    # 细分知识条目构建
    # ====================================================================

    def test_build_all_types(
        self,
        sample_page: PageInfo,
    ) -> None:
        """测试生成所有类型知识条目"""
        builder = KnowledgeBuilder(
            include_page_doc=True,
            include_buttons=True,
            include_forms=True,
            include_tables=True,
        )
        parse_result = ParseResult(pages=[sample_page])
        items = builder.build(parse_result)

        # 1 page + 2 buttons + 1 form + 1 table = 5
        assert len(items) == 5
        types = [it.type for it in items]
        assert KnowledgeType.PAGE in types
        assert KnowledgeType.BUTTON in types
        assert KnowledgeType.FORM in types

    def test_skip_empty_page(self, builder: KnowledgeBuilder) -> None:
        """测试跳过空页面"""
        empty_page = PageInfo(name="空页面", path="/empty")
        parse_result = ParseResult(pages=[empty_page])
        items = builder.build(parse_result)
        assert len(items) == 0

    # ====================================================================
    # 从项目级解析结果构建
    # ====================================================================

    def test_build_from_project(
        self,
        builder: KnowledgeBuilder,
        sample_vue_project: Path,
    ) -> None:
        """测试从项目级解析结果构建"""
        from src.parser.vue_parser import VueProjectParser

        parser = VueProjectParser(sample_vue_project)
        parse_result = parser.parse()
        items = builder.build(parse_result)

        assert len(items) >= 3  # 至少 3 个页面

        # 检查所有条目都有必要字段
        for item in items:
            assert item.id
            assert item.title
            assert item.content
            assert item.type in (
                KnowledgeType.PAGE,
                KnowledgeType.BUTTON,
                KnowledgeType.FORM,
                KnowledgeType.WORKFLOW,
                KnowledgeType.API,
                KnowledgeType.MANUAL,
            )

    def test_build_from_page_single(
        self,
        builder: KnowledgeBuilder,
        sample_page: PageInfo,
    ) -> None:
        """测试从单个页面构建"""
        items = builder.build_from_page(sample_page)
        assert len(items) >= 1
        assert items[0].type == KnowledgeType.PAGE

    # ====================================================================
    # 操作流程指南构建
    # ====================================================================

    def test_build_operation_flow_item(self, builder: KnowledgeBuilder) -> None:
        """测试构建操作流程知识条目"""
        from src.parser.models import OperationFlow, OperationStep

        flow = OperationFlow(
            name="创建订单",
            entry_method="handleCreate",
            steps=[
                OperationStep(action="点击「创建订单」按钮"),
                OperationStep(action="在弹出的「创建订单」中操作"),
                OperationStep(action="触发数据操作: order/createOrder"),
            ],
            store_actions=["order/createOrder"],
        )
        page = PageInfo(
            name="订单列表",
            path="/order/list",
            operation_flows=[flow],
        )
        parse_result = ParseResult(pages=[page])
        items = builder.build(parse_result)

        # 应该有 1 个 page + 1 个 workflow
        workflow_items = [i for i in items if i.type == KnowledgeType.WORKFLOW]
        assert len(workflow_items) == 1
        item = workflow_items[0]

        assert "创建订单操作流程" in item.title
        assert "操作流程: 创建订单" in item.content
        assert "步骤 1" in item.content
        assert "步骤 2" in item.content
        assert "order/createOrder" in item.content

    def test_build_with_api_endpoint_in_flow(
        self,
        builder: KnowledgeBuilder,
    ) -> None:
        """测试操作流程中关联 API 端点"""
        from src.parser.models import APIInfo, OperationFlow, OperationStep

        api_def = APIInfo(
            function_name="createOrder",
            method="post",
            url="/api/orders",
        )
        flow = OperationFlow(
            name="创建",
            steps=[
                OperationStep(action="点击按钮"),
                OperationStep(action="触发数据操作"),
            ],
            store_actions=["order/createOrder"],
        )
        page = PageInfo(name="订单", path="/order", operation_flows=[flow])
        parse_result = ParseResult(pages=[page], api_definitions=[api_def])
        items = builder.build(parse_result)

        workflow_items = [i for i in items if i.type == KnowledgeType.WORKFLOW]
        assert len(workflow_items) == 1
        # 应该包含关联的 API 信息
        assert "createOrder" in workflow_items[0].content
        assert "POST" in workflow_items[0].content
        assert "/api/orders" in workflow_items[0].content

    def test_build_operation_flows_from_project(
        self,
        builder: KnowledgeBuilder,
        sample_vue_project: Path,
    ) -> None:
        """测试从项目解析结果构建操作流程"""
        from src.parser.vue_parser import VueProjectParser

        parser = VueProjectParser(sample_vue_project)
        parse_result = parser.parse()
        items = builder.build(parse_result)

        workflow_items = [i for i in items if i.type == KnowledgeType.WORKFLOW]
        assert len(workflow_items) >= 3  # 至少有几个操作流程

        # 应该有一个"新建订单"操作流程
        create_flow = next(
            (i for i in workflow_items if "新建订单" in i.title),
            None,
        )
        assert create_flow is not None
        # 应该包含表单字段信息
        assert "订单编号" in create_flow.content or "客户名称" in create_flow.content

    def test_include_operation_flows_toggle(self) -> None:
        """测试 include_operation_flows 开关"""
        from src.parser.models import OperationFlow, OperationStep

        flow = OperationFlow(
            name="测试",
            steps=[
                OperationStep(action="点击按钮"),
                OperationStep(action="触发操作"),
            ],
            store_actions=["test/action"],
        )
        page = PageInfo(name="测试页", path="/test", operation_flows=[flow])
        parse_result = ParseResult(pages=[page])

        # 开启时(默认)
        builder_with = KnowledgeBuilder(include_operation_flows=True)
        items_with = builder_with.build(parse_result)
        assert any(i.type == KnowledgeType.WORKFLOW for i in items_with)

        # 关闭时
        builder_without = KnowledgeBuilder(include_operation_flows=False)
        items_without = builder_without.build(parse_result)
        assert not any(i.type == KnowledgeType.WORKFLOW for i in items_without)

