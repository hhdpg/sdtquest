"""Vue SFC 解析器单元测试"""

from pathlib import Path

import pytest

from src.domain.exceptions import ParserError
from src.parser.vue_parser import VueProjectParser, VueSFCParser


class TestVueSFCParser:
    """VueSFCParser 单元测试"""

    @pytest.fixture
    def parser(self) -> VueSFCParser:
        return VueSFCParser()

    # ====================================================================
    # SFC 区块分割
    # ====================================================================

    def test_extract_template_block(self, parser: VueSFCParser) -> None:
        """测试 template 区块提取"""
        content = """
        <template>
          <div>内容</div>
        </template>
        <script>
        export default {}
        </script>
        """
        result = parser.parse_content(content)
        assert "<div>内容</div>" in result.template_content
        assert "export default" in result.script_content

    def test_extract_nested_template(self, parser: VueSFCParser) -> None:
        """测试嵌套 template 标签的正确处理"""
        content = """
        <template>
          <div>
            <el-table>
              <el-table-column>
                <template slot-scope="scope">
                  <el-button @click="handle(scope)">操作</el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-dialog title="弹窗">
              <div>对话框</div>
            </el-dialog>
          </div>
        </template>
        <script>
        export default {}
        </script>
        """
        result = parser.parse_content(content)
        # 应包含所有组件(包括 dialog,嵌套在 template 内)
        assert "el-dialog" in result.template_content
        assert "slot-scope" in result.template_content
        assert len(result.dialogs) == 1
        assert result.dialogs[0].title == "弹窗"

    def test_extract_script_and_style(self, parser: VueSFCParser) -> None:
        """测试 script 和 style 区块提取"""
        content = """
        <template><div /></template>
        <script>
        export default { name: 'Test' }
        </script>
        <style scoped>
        .test { color: red; }
        </style>
        """
        result = parser.parse_content(content)
        assert "export default" in result.script_content
        assert ".test" in result.style_content

    def test_parse_order_list_vue(self, parser: VueSFCParser, sample_order_list_vue: Path) -> None:
        """测试解析订单列表页"""
        result = parser.parse_file(sample_order_list_vue)

        # 应有多个按钮
        assert len(result.buttons) >= 4
        button_texts = [b.text for b in result.buttons]
        assert "新建订单" in button_texts
        assert "导出" in button_texts

        # 应有搜索表单和创建表单
        assert len(result.forms) == 2

        # 应有订单表格
        assert len(result.tables) == 1

        # 应有新建订单弹窗
        assert len(result.dialogs) == 1
        assert result.dialogs[0].title == "新建订单"

        # 应提取出 dispatch 调用
        assert "order/fetchList" in result.dispatched_actions

    def test_parse_file_not_exists(self, parser: VueSFCParser) -> None:
        """测试解析不存在的文件"""
        with pytest.raises(ParserError, match="不存在"):
            parser.parse_file("/non/existent/file.vue")

    # ====================================================================
    # 操作流程追踪
    # ====================================================================

    def test_extract_methods_from_vue(self, parser: VueSFCParser, sample_order_list_vue: Path) -> None:
        """测试从 Vue 文件中提取 methods"""
        result = parser.parse_file(sample_order_list_vue)
        assert len(result.methods) >= 5
        method_names = {m.name for m in result.methods}
        assert "handleCreate" in method_names
        assert "submitCreate" in method_names
        assert "loadData" in method_names

    def test_trace_operation_flows(self, parser: VueSFCParser, sample_order_list_vue: Path) -> None:
        """测试 button → method → API 链路追踪"""
        result = parser.parse_file(sample_order_list_vue)
        assert len(result.operation_flows) >= 3

        # 按入口按钮文本查找流程
        flow_by_button = {
            f.entry_button.text: f for f in result.operation_flows
            if f.entry_button and f.entry_button.text
        }

        # 新建订单流程应该追踪到弹窗
        create_flow = flow_by_button.get("新建订单")
        assert create_flow is not None
        assert create_flow.dialog_involved is not None
        assert create_flow.dialog_involved.title == "新建订单"

    def test_trace_api_in_flow(self, parser: VueSFCParser, sample_order_list_vue: Path) -> None:
        """测试流程中能追踪到 API/Store 调用"""
        result = parser.parse_file(sample_order_list_vue)

        # 找到"确定"按钮的流程(提交表单)
        submit_flow = None
        for f in result.operation_flows:
            if f.entry_button and f.entry_button.text == "确定":
                submit_flow = f
                break

        assert submit_flow is not None
        # 应该追踪到 store action
        assert "order/createOrder" in submit_flow.store_actions
        # 应该关联创建表单
        assert submit_flow.form_involved is not None
        assert submit_flow.form_involved.model == "createForm"


class TestVueProjectParser:
    """VueProjectParser 单元测试"""

    @pytest.fixture
    def parser(self, sample_vue_project: Path) -> VueProjectParser:
        return VueProjectParser(sample_vue_project)

    def test_parse_project_routes(self, parser: VueProjectParser) -> None:
        """测试项目路由解析"""
        result = parser.parse()
        assert len(result.routes) >= 2

        paths = [r.path for r in result.routes]
        assert "/order" in paths
        assert "/user" in paths

    def test_parse_project_pages(self, parser: VueProjectParser) -> None:
        """测试项目页面解析"""
        result = parser.parse()
        # 应至少有 3 个页面(订单列表、订单详情、用户管理)
        assert len(result.pages) >= 3

        page_names = {p.name for p in result.pages}
        assert "订单列表" in page_names
        assert "用户管理" in page_names

    def test_parse_project_store_modules(self, parser: VueProjectParser) -> None:
        """测试项目 Store 模块解析"""
        result = parser.parse()
        assert len(result.store_modules) >= 2
        names = {m.name for m in result.store_modules}
        assert "order" in names
        assert "user" in names

    def test_parse_project_api_definitions(self, parser: VueProjectParser) -> None:
        """测试项目 API 定义解析"""
        result = parser.parse()
        assert len(result.api_definitions) >= 5
        function_names = {a.function_name for a in result.api_definitions}
        assert "getOrderList" in function_names

    def test_parse_project_stats(self, parser: VueProjectParser) -> None:
        """测试解析统计"""
        result = parser.parse()
        stats = result.get_stats()
        assert stats["routes"] >= 2
        assert stats["pages"] >= 3
        assert stats["store_modules"] >= 2
        assert stats["api_definitions"] >= 5
        assert stats["buttons"] >= 5
        assert stats["forms"] >= 1
        assert stats["tables"] >= 1

    def test_parse_nonexistent_project(self) -> None:
        """测试解析不存在的项目"""
        parser = VueProjectParser("/non/existent/project")
        with pytest.raises(ParserError, match="不存在"):
            parser.parse()
