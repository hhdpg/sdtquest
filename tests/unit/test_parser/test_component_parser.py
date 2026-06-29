"""Element UI 组件提取器单元测试"""

import pytest

from src.parser.component_parser import ComponentParser
from src.parser.models import ButtonInfo, DialogInfo, FormInfo, TableInfo


class TestComponentParser:
    """ComponentParser 单元测试"""

    @pytest.fixture
    def parser(self) -> ComponentParser:
        return ComponentParser()

    # ====================================================================
    # 按钮提取
    # ====================================================================

    def test_extract_button_basic(self, parser: ComponentParser) -> None:
        """测试基础按钮提取"""
        template = '<el-button @click="handleCreate">新建订单</el-button>'
        buttons, _, _, _ = parser.parse(template)

        assert len(buttons) == 1
        assert buttons[0].text == "新建订单"
        assert buttons[0].event == "handleCreate"

    def test_extract_button_with_permission(self, parser: ComponentParser) -> None:
        """测试带权限的按钮提取"""
        template = '<el-button v-permission="[\'order:create\']">新建</el-button>'
        buttons, _, _, _ = parser.parse(template)

        assert len(buttons) == 1
        assert buttons[0].permission == "order:create"

    def test_extract_button_with_type(self, parser: ComponentParser) -> None:
        """测试按钮类型属性提取"""
        template = '<el-button type="primary" size="small">按钮</el-button>'
        buttons, _, _, _ = parser.parse(template)

        assert len(buttons) == 1
        assert buttons[0].button_type == "primary"
        assert buttons[0].size == "small"

    def test_extract_multiple_buttons(self, parser: ComponentParser) -> None:
        """测试多个按钮提取"""
        template = """
        <div>
          <el-button @click="a">A</el-button>
          <el-button @click="b">B</el-button>
          <el-button @click="c">C</el-button>
        </div>
        """
        buttons, _, _, _ = parser.parse(template)
        assert len(buttons) == 3
        assert [b.text for b in buttons] == ["A", "B", "C"]

    # ====================================================================
    # 表单提取
    # ====================================================================

    def test_extract_form_basic(self, parser: ComponentParser) -> None:
        """测试基础表单提取"""
        template = """
        <el-form :model="form" :rules="rules">
          <el-form-item label="订单编号" prop="orderNo">
            <el-input v-model="form.orderNo" />
          </el-form-item>
        </el-form>
        """
        _, forms, _, _ = parser.parse(template)

        assert len(forms) == 1
        assert forms[0].model == "form"
        assert forms[0].rules == "rules"
        assert len(forms[0].fields) == 1
        assert forms[0].fields[0].label == "订单编号"
        assert forms[0].fields[0].name == "orderNo"
        assert forms[0].fields[0].field_type == "input"

    def test_extract_form_field_types(self, parser: ComponentParser) -> None:
        """测试表单字段类型推断"""
        template = """
        <el-form>
          <el-form-item label="文本" prop="text">
            <el-input />
          </el-form-item>
          <el-form-item label="选择" prop="select">
            <el-select />
          </el-form-item>
          <el-form-item label="日期" prop="date">
            <el-date-picker />
          </el-form-item>
          <el-form-item label="开关" prop="switch">
            <el-switch />
          </el-form-item>
        </el-form>
        """
        _, forms, _, _ = parser.parse(template)
        assert len(forms) == 1

        field_types = [f.field_type for f in forms[0].fields]
        assert field_types == ["input", "select", "date", "switch"]

    def test_extract_form_required_field(self, parser: ComponentParser) -> None:
        """测试必填字段识别"""
        template = """
        <el-form>
          <el-form-item label="必填项" prop="required" required>
            <el-input />
          </el-form-item>
          <el-form-item label="选填项" prop="optional">
            <el-input />
          </el-form-item>
        </el-form>
        """
        _, forms, _, _ = parser.parse(template)
        assert forms[0].fields[0].required is True
        assert forms[0].fields[1].required is False

    # ====================================================================
    # 表格提取
    # ====================================================================

    def test_extract_table_basic(self, parser: ComponentParser) -> None:
        """测试基础表格提取"""
        template = """
        <el-table :data="tableData">
          <el-table-column prop="name" label="名称" width="120" />
          <el-table-column prop="status" label="状态" sortable />
        </el-table>
        """
        _, _, tables, _ = parser.parse(template)

        assert len(tables) == 1
        assert tables[0].data == "tableData"
        assert len(tables[0].columns) == 2
        assert tables[0].columns[0].prop == "name"
        assert tables[0].columns[0].label == "名称"
        assert tables[0].columns[0].width == "120"
        assert tables[0].columns[1].sortable is True

    # ====================================================================
    # 弹窗提取
    # ====================================================================

    def test_extract_dialog_basic(self, parser: ComponentParser) -> None:
        """测试基础弹窗提取"""
        template = """
        <el-dialog :visible.sync="dialogVisible" title="编辑订单">
          <div>弹窗内容</div>
        </el-dialog>
        """
        _, _, _, dialogs = parser.parse(template)

        assert len(dialogs) == 1
        assert dialogs[0].title == "编辑订单"
        assert dialogs[0].visible == "dialogVisible"

    def test_extract_dialog_with_form(self, parser: ComponentParser) -> None:
        """测试包含表单的弹窗"""
        template = """
        <el-dialog title="新建">
          <el-form :model="form">
            <el-form-item label="字段" prop="field" />
          </el-form>
          <div slot="footer">
            <el-button>确定</el-button>
          </div>
        </el-dialog>
        """
        _, _, _, dialogs = parser.parse(template)

        assert len(dialogs) == 1
        assert "包含表单" in dialogs[0].content_hint
        assert "含底部操作区" in dialogs[0].content_hint

    # ====================================================================
    # 边界情况
    # ====================================================================

    def test_parse_empty_template(self, parser: ComponentParser) -> None:
        """测试空模板"""
        buttons, forms, tables, dialogs = parser.parse("")
        assert buttons == []
        assert forms == []
        assert tables == []
        assert dialogs == []

    def test_parse_no_element_ui(self, parser: ComponentParser) -> None:
        """测试不含 Element UI 组件的模板"""
        template = "<div><span>普通内容</span></div>"
        buttons, forms, tables, dialogs = parser.parse(template)
        assert buttons == []
        assert forms == []
        assert tables == []
        assert dialogs == []

    def test_clean_binding(self, parser: ComponentParser) -> None:
        """测试 Vue 绑定表达式清理"""
        assert parser._clean_binding(":model") == "model"
        assert parser._clean_binding("v-bind:model") == "model"
        assert parser._clean_binding("'hello'") == "hello"
        assert parser._clean_binding('"world"') == "world"
        assert parser._clean_binding("plain") == "plain"
        assert parser._clean_binding("") == ""
