"""Element UI 组件提取器模块。

本模块负责解析 Vue 单文件组件的 <template> 部分,使用 BeautifulSoup
提取 Element UI 组件信息:
- el-button: 按钮文本、@click 事件、v-permission 权限
- el-form + el-form-item: 表单字段名、标签、校验规则
- el-table + el-table-column: 表格列定义
- el-dialog: 弹窗内容和触发条件

典型用法:
    >>> from src.parser.component_parser import ComponentParser
    >>> parser = ComponentParser()
    >>> buttons, forms, tables, dialogs = parser.parse(template_html)
"""

from __future__ import annotations

from bs4 import BeautifulSoup, Tag
from loguru import logger


# ============================================================================
# ComponentParser
# ============================================================================

class ComponentParser:
    """
    Element UI 组件提取器。

    使用 BeautifulSoup 解析 HTML 模板,提取 Element UI 组件信息。

    Attributes:
        BUTTON_TAG: 按钮标签名
        FORM_TAG: 表单标签名
        FORM_ITEM_TAG: 表单项标签名
        TABLE_TAG: 表格标签名
        TABLE_COLUMN_TAG: 表格列标签名
        DIALOG_TAG: 弹窗标签名
    """

    BUTTON_TAG = "el-button"
    FORM_TAG = "el-form"
    FORM_ITEM_TAG = "el-form-item"
    TABLE_TAG = "el-table"
    TABLE_COLUMN_TAG = "el-table-column"
    DIALOG_TAG = "el-dialog"

    def parse(
        self,
        template_content: str,
    ) -> tuple[
        list,
        list,
        list,
        list,
    ]:
        """
        解析 <template> 内容,提取全部 Element UI 组件。

        Args:
            template_content: <template> 标签内的 HTML 字符串

        Returns:
            (buttons, forms, tables, dialogs) 四元组
        """
        from src.parser.models import ButtonInfo, DialogInfo, FormInfo, TableInfo

        if not template_content or not template_content.strip():
            return [], [], [], []

        soup = BeautifulSoup(template_content, "html.parser")

        buttons = self.extract_buttons(soup)
        forms = self.extract_forms(soup)
        tables = self.extract_tables(soup)
        dialogs = self.extract_dialogs(soup)

        logger.debug(
            "组件提取完成 | buttons={} | forms={} | tables={} | dialogs={}",
            len(buttons),
            len(forms),
            len(tables),
            len(dialogs),
        )

        return buttons, forms, tables, dialogs

    # ========================================================================
    # 按钮提取
    # ========================================================================

    def extract_buttons(self, soup: BeautifulSoup) -> list:
        """
        提取所有 el-button 组件信息。

        Args:
            soup: BeautifulSoup 实例

        Returns:
            ButtonInfo 列表
        """
        from src.parser.models import ButtonInfo

        buttons: list[ButtonInfo] = []

        for tag in soup.find_all(self.BUTTON_TAG):
            if not isinstance(tag, Tag):
                continue

            text = tag.get_text(strip=True)
            event = tag.get("@click") or ""
            permission = tag.get("v-permission") or ""
            button_type = tag.get("type") or ""
            size = tag.get("size") or ""

            # 去除 permission 属性中的方括号和引号
            permission = permission.strip("[]").strip("'\"")

            # 如果按钮内没有文本,尝试查找 slot 或 title
            if not text:
                title_attr = tag.get("title")
                if title_attr:
                    text = str(title_attr)

            buttons.append(ButtonInfo(
                text=text,
                event=self._clean_binding(event),
                permission=permission,
                button_type=button_type,
                size=size,
            ))

        return buttons

    # ========================================================================
    # 表单提取
    # ========================================================================

    def extract_forms(self, soup: BeautifulSoup) -> list:
        """
        提取所有 el-form 及其字段信息。

        Args:
            soup: BeautifulSoup 实例

        Returns:
            FormInfo 列表
        """
        from src.parser.models import FormField, FormInfo

        forms: list[FormInfo] = []

        for form_tag in soup.find_all(self.FORM_TAG):
            if not isinstance(form_tag, Tag):
                continue

            model = form_tag.get(":model") or form_tag.get("v-model") or ""
            rules = form_tag.get(":rules") or ""
            model = self._clean_binding(model)
            rules = self._clean_binding(rules)

            fields: list[FormField] = []

            for item_tag in form_tag.find_all(self.FORM_ITEM_TAG):
                if not isinstance(item_tag, Tag):
                    continue

                label = item_tag.get("label") or ""
                prop = item_tag.get("prop") or ""
                required = "required" in (item_tag.attrs or {})

                # 推断字段类型(根据子组件)
                field_type = self._infer_field_type(item_tag)

                # 查找 placeholder
                placeholder = ""
                input_tag = item_tag.find(["el-input", "el-select", "el-date-picker"])
                if isinstance(input_tag, Tag):
                    placeholder = input_tag.get("placeholder") or ""

                fields.append(FormField(
                    name=prop,
                    label=label,
                    field_type=field_type,
                    placeholder=placeholder,
                    required=required,
                ))

            forms.append(FormInfo(
                model=model,
                rules=rules,
                fields=fields,
            ))

        return forms

    def _infer_field_type(self, item_tag: Tag) -> str:
        """
        根据表单项内的子组件推断字段类型。

        Args:
            item_tag: el-form-item 标签

        Returns:
            字段类型字符串(input/select/date/checkbox/radio/switch/upload/其他)
        """
        type_mapping = {
            "el-input": "input",
            "el-select": "select",
            "el-date-picker": "date",
            "el-time-picker": "time",
            "el-checkbox": "checkbox",
            "el-checkbox-group": "checkbox",
            "el-radio": "radio",
            "el-radio-group": "radio",
            "el-switch": "switch",
            "el-upload": "upload",
            "el-input-number": "number",
            "el-cascader": "cascader",
            "el-tree-select": "tree-select",
            "el-autocomplete": "autocomplete",
        }

        for tag_name, field_type in type_mapping.items():
            if item_tag.find(tag_name):
                return field_type

        # 如果是 textarea
        input_tag = item_tag.find("el-input")
        if isinstance(input_tag, Tag) and input_tag.get("type") == "textarea":
            return "textarea"

        return "input"

    # ========================================================================
    # 表格提取
    # ========================================================================

    def extract_tables(self, soup: BeautifulSoup) -> list:
        """
        提取所有 el-table 及其列定义。

        Args:
            soup: BeautifulSoup 实例

        Returns:
            TableInfo 列表
        """
        from src.parser.models import TableColumn, TableInfo

        tables: list[TableInfo] = []

        for table_tag in soup.find_all(self.TABLE_TAG):
            if not isinstance(table_tag, Tag):
                continue

            data = table_tag.get(":data") or table_tag.get("data") or ""
            data = self._clean_binding(data)

            columns: list[TableColumn] = []

            for col_tag in table_tag.find_all(self.TABLE_COLUMN_TAG, recursive=False):
                if not isinstance(col_tag, Tag):
                    continue

                prop = col_tag.get("prop") or ""
                label = col_tag.get("label") or ""
                width = col_tag.get("width") or col_tag.get("min-width") or ""
                sortable_attr = col_tag.get("sortable")
                sortable = sortable_attr is not None and sortable_attr != "false"
                formatter = col_tag.get(":formatter") or col_tag.get("formatter") or ""
                formatter = self._clean_binding(formatter)

                columns.append(TableColumn(
                    prop=prop,
                    label=label,
                    width=width,
                    sortable=sortable,
                    formatter=formatter,
                ))

            # 嵌套的 el-table-column(多级表头),仅取最外层
            if not columns:
                for col_tag in table_tag.find_all(self.TABLE_COLUMN_TAG):
                    if not isinstance(col_tag, Tag):
                        continue
                    prop = col_tag.get("prop") or ""
                    label = col_tag.get("label") or ""
                    if prop or label:
                        columns.append(TableColumn(prop=prop, label=label))

            tables.append(TableInfo(data=data, columns=columns))

        return tables

    # ========================================================================
    # 弹窗提取
    # ========================================================================

    def extract_dialogs(self, soup: BeautifulSoup) -> list:
        """
        提取所有 el-dialog 弹窗信息。

        Args:
            soup: BeautifulSoup 实例

        Returns:
            DialogInfo 列表
        """
        from src.parser.models import DialogInfo

        dialogs: list[DialogInfo] = []

        for dialog_tag in soup.find_all(self.DIALOG_TAG):
            if not isinstance(dialog_tag, Tag):
                continue

            title = dialog_tag.get("title") or ""
            visible = dialog_tag.get(":visible.sync") or dialog_tag.get("visible") or ""
            visible = self._clean_binding(visible)

            # 提取弹窗内容提示
            content_parts: list[str] = []
            if dialog_tag.find(self.FORM_TAG):
                content_parts.append("包含表单")
            if dialog_tag.find(self.TABLE_TAG):
                content_parts.append("包含表格")

            # 查找 slot=footer 提示
            footer = dialog_tag.find(attrs={"slot": "footer"})
            if footer:
                content_parts.append("含底部操作区")

            content_hint = ",".join(content_parts) if content_parts else ""

            # 如果 title 是绑定表达式,尝试提取
            title = self._clean_binding(title)

            dialogs.append(DialogInfo(
                title=title,
                visible=visible,
                content_hint=content_hint,
            ))

        return dialogs

    # ========================================================================
    # 工具方法
    # ========================================================================

    @staticmethod
    def _clean_binding(value: str) -> str:
        """
        清理 Vue 绑定表达式,去除 v-bind 前缀和引号。

        Args:
            value: 原始属性值,如 ":model", "form", "'订单详情'"

        Returns:
            清理后的字符串
        """
        if not value:
            return ""
        value = value.strip()
        # 去除 Vue 绑定前缀
        if value.startswith(":") or value.startswith("v-bind:"):
            value = value.split(":", 1)[-1] if ":" in value else value
        # 去除首尾引号
        if (value.startswith("'") and value.endswith("'")) or \
           (value.startswith('"') and value.endswith('"')):
            value = value[1:-1]
        return value
