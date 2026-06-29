"""知识文档构建器模块。

本模块负责将 Vue 项目解析结果转换为 KnowledgeItem 列表,按页面组织知识:
- 每个页面生成一个综合文档(包含页面说明、菜单路径、按钮操作、表单字段、关联 API)
- 可选调用 LLM 丰富描述(由上层 KnowledgeService 负责)

典型用法:
    >>> from src.parser.builder import KnowledgeBuilder
    >>> from src.parser.vue_parser import VueProjectParser
    >>> parser = VueProjectParser("path/to/vue-project")
    >>> parse_result = parser.parse()
    >>> builder = KnowledgeBuilder()
    >>> items = builder.build(parse_result)
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from loguru import logger

from src.domain.enums import KnowledgeType
from src.domain.models import KnowledgeItem
from src.parser.models import (
    APIInfo,
    ButtonInfo,
    DialogInfo,
    FormField,
    FormInfo,
    MethodInfo,
    OperationFlow,
    OperationStep,
    PageInfo,
    ParseResult,
    StoreModuleInfo,
    TableColumn,
    TableInfo,
)


# ============================================================================
# KnowledgeBuilder
# ============================================================================

class KnowledgeBuilder:
    """
    知识文档构建器。

    将 Vue 项目解析结果转换为 KnowledgeItem 列表,按页面聚合组织。
    支持生成:
    - 页面综合文档(描述页面入口、操作概览)
    - 操作流程指南(每个按钮触发的完整操作流程,推荐)
    - 按钮/表单/表格单独条目(可选)

    Attributes:
        include_page_doc: 是否为每个页面生成综合文档
        include_operation_flows: 是否为每个操作流程生成结构化指南(推荐 True)
        include_buttons: 是否为每个按钮单独生成知识条目
        include_forms: 是否为每个表单单独生成知识条目
        include_tables: 是否为每个表格单独生成知识条目
    """

    def __init__(
        self,
        include_page_doc: bool = True,
        include_operation_flows: bool = True,
        include_buttons: bool = False,
        include_forms: bool = False,
        include_tables: bool = False,
    ) -> None:
        """
        初始化知识构建器。

        Args:
            include_page_doc: 是否为每个页面生成综合文档
            include_operation_flows: 是否为每个操作流程生成结构化指南
            include_buttons: 是否为每个按钮单独生成知识条目
            include_forms: 是否为每个表单单独生成知识条目
            include_tables: 是否为每个表格单独生成知识条目
        """
        self.include_page_doc = include_page_doc
        self.include_operation_flows = include_operation_flows
        self.include_buttons = include_buttons
        self.include_forms = include_forms
        self.include_tables = include_tables

    def build(self, parse_result: ParseResult) -> list[KnowledgeItem]:
        """
        将完整解析结果构建为知识条目列表。

        Args:
            parse_result: Vue 项目解析结果

        Returns:
            KnowledgeItem 列表
        """
        items: list[KnowledgeItem] = []

        for page in parse_result.pages:
            if self.include_page_doc:
                page_item = self._build_page_document(page, parse_result)
                if page_item is not None:
                    items.append(page_item)

            # 操作流程指南(推荐默认开启)
            if self.include_operation_flows:
                for flow in page.operation_flows:
                    flow_item = self._build_operation_flow_item(page, flow, parse_result)
                    if flow_item is not None:
                        items.append(flow_item)

            if self.include_buttons:
                for button in page.buttons:
                    item = self._build_button_item(page, button)
                    if item is not None:
                        items.append(item)

            if self.include_forms:
                for form in page.forms:
                    item = self._build_form_item(page, form)
                    if item is not None:
                        items.append(item)

            if self.include_tables:
                for table in page.tables:
                    item = self._build_table_item(page, table)
                    if item is not None:
                        items.append(item)

        logger.info(
            "知识构建完成 | pages={} | items={}",
            len(parse_result.pages),
            len(items),
        )

        return items

    def build_from_page(self, page: PageInfo) -> list[KnowledgeItem]:
        """
        从单个页面构建知识条目(供外部单独使用)。

        Args:
            page: 页面信息

        Returns:
            KnowledgeItem 列表
        """
        items: list[KnowledgeItem] = []
        if self.include_page_doc:
            item = self._build_page_document(page)
            if item is not None:
                items.append(item)

        if self.include_buttons:
            for button in page.buttons:
                item = self._build_button_item(page, button)
                if item is not None:
                    items.append(item)

        if self.include_forms:
            for form in page.forms:
                item = self._build_form_item(page, form)
                if item is not None:
                    items.append(item)

        if self.include_tables:
            for table in page.tables:
                item = self._build_table_item(page, table)
                if item is not None:
                    items.append(item)

        return items

    # ========================================================================
    # 内部构建方法
    # ========================================================================

    def _build_page_document(
        self,
        page: PageInfo,
        parse_result: ParseResult | None = None,
    ) -> KnowledgeItem | None:
        """
        为单个页面生成综合知识文档。

        Args:
            page: 页面信息
            parse_result: 完整解析结果(可选,用于补充 Store/API 关联)

        Returns:
            KnowledgeItem,如果页面没有任何内容则返回 None
        """
        # 跳过空页面
        if not page.buttons and not page.forms and not page.tables and not page.dialogs:
            return None

        content_parts: list[str] = []

        # 页面说明
        content_parts.append(f"【页面说明】{page.name}")
        if page.path:
            content_parts.append(f"访问路径: {page.path}")
        if page.source_file:
            content_parts.append(f"来源文件: {page.source_file}")

        # 操作流程概览(如果有)
        if page.operation_flows:
            content_parts.append("\n【操作流程概览】")
            # 过滤出有意义的流程(有 store actions 或有 dialog)
            meaningful_flows = [
                f for f in page.operation_flows
                if f.store_actions or f.dialog_involved or f.api_endpoints
            ]
            for flow in meaningful_flows[:10]:  # 最多显示 10 个
                content_parts.append(f"  - {flow.name}: 详见「{page.name} - {flow.name}操作流程」")

        # 按钮操作
        if page.buttons:
            content_parts.append("\n【可用操作】")
            for button in page.buttons:
                button_desc = self._describe_button(button)
                content_parts.append(f"  - {button_desc}")

        # 表单字段
        if page.forms:
            content_parts.append("\n【表单字段】")
            for form in page.forms:
                content_parts.append(self._describe_form(form))

        # 表格列
        if page.tables:
            content_parts.append("\n【数据展示】")
            for table in page.tables:
                content_parts.append(self._describe_table(table))

        # 弹窗
        if page.dialogs:
            content_parts.append("\n【弹窗功能】")
            for dialog in page.dialogs:
                content_parts.append(self._describe_dialog(dialog))

        # 关联 API
        related_apis = self._find_related_apis(page, parse_result)
        if related_apis:
            content_parts.append("\n【关联接口】")
            for api in related_apis:
                api_desc = f"  - {api.function_name}: {api.method.upper()} {api.url}"
                content_parts.append(api_desc)

        # 关联 Store actions
        related_actions = self._find_related_actions(page, parse_result)
        if related_actions:
            content_parts.append("\n【数据操作】")
            for action in related_actions:
                content_parts.append(f"  - {action}")

        content = "\n".join(content_parts)

        # 生成标签
        tags = self._generate_tags(page)

        return KnowledgeItem(
            id=str(uuid4()),
            type=KnowledgeType.PAGE,
            title=f"{page.name}页面操作指南",
            content=content,
            page_name=page.name,
            page_path=page.path,
            source_file=page.source_file,
            tags=tags,
        )

    def _build_operation_flow_item(
        self,
        page: PageInfo,
        flow: OperationFlow,
        parse_result: ParseResult | None = None,
    ) -> KnowledgeItem | None:
        """
        为单个操作流程生成结构化操作指南。

        输出格式示例:
            操作流程: 创建订单

            步骤 1: 在「订单列表」页面 → 点击「新建订单」按钮
                    需要权限: order:create
            步骤 2: 在弹出的「新建订单」对话框中操作
                    填写字段: 订单编号[必填]、客户名称[必填]
            步骤 3: 点击「确定」提交
                    触发数据操作: order/createOrder
                    后端接口: POST /api/orders

            预期结果: 订单创建成功,列表自动刷新

        Args:
            page: 所属页面
            flow: 操作流程
            parse_result: 完整解析结果(用于关联 API 定义)

        Returns:
            KnowledgeItem,如果流程无实质内容则返回 None
        """
        # 跳过只有入口按钮、没有实质动作的流程(如纯路由跳转)
        if not flow.steps or len(flow.steps) < 2:
            # 但也保留有 API/store 调用的流程
            if not flow.store_actions and not flow.api_endpoints:
                return None

        content_parts: list[str] = []

        # 标题
        content_parts.append(f"操作流程: {flow.name}")
        content_parts.append("")

        # 页面入口
        if page.path:
            content_parts.append(f"页面入口: {page.name} ({page.path})")
            content_parts.append("")

        # 步骤
        dialog_step_shown = False
        for i, step in enumerate(flow.steps, 1):
            step_line = f"步骤 {i}: {step.action}"
            content_parts.append(step_line)
            if step.detail:
                content_parts.append(f"        {step.detail}")

            # 在弹窗步骤上附带表单字段信息(每个流程只展示一次)
            if (not dialog_step_shown
                    and flow.dialog_involved
                    and flow.form_involved
                    and ("弹出的" in step.action or "对话框" in step.action)):
                field_descriptions = []
                for field in flow.form_involved.fields:
                    desc = field.label or field.name
                    if field.required:
                        desc += "[必填]"
                    field_descriptions.append(desc)
                if field_descriptions:
                    content_parts.append(
                        f"        填写字段: {', '.join(field_descriptions)}",
                    )
                dialog_step_shown = True

        # 后端 API 信息(从 parse_result 关联得到)
        api_info_lines = self._collect_api_info_for_flow(flow, parse_result)
        if api_info_lines:
            content_parts.append("\n后端接口:")
            content_parts.extend(api_info_lines)

        # Store actions
        if flow.store_actions:
            content_parts.append(f"\n触发数据操作: {', '.join(flow.store_actions)}")

        # 预期结果
        if flow.expected_outcome:
            content_parts.append(f"\n预期结果: {flow.expected_outcome}")

        content = "\n".join(content_parts)

        # 生成标签(页面名 + 流程名 + 涉及的 API 名)
        tags = [page.name, flow.name]
        if flow.entry_button and flow.entry_button.permission:
            tags.append(f"权限:{flow.entry_button.permission}")
        for api in flow.api_endpoints:
            tags.append(api.function_name)
        tags = list(dict.fromkeys(tags))[:10]

        return KnowledgeItem(
            id=str(uuid4()),
            type=KnowledgeType.WORKFLOW,
            title=f"{page.name} - {flow.name}操作流程",
            content=content,
            page_name=page.name,
            page_path=page.path,
            source_file=page.source_file,
            tags=tags,
        )

    def _collect_api_info_for_flow(
        self,
        flow: OperationFlow,
        parse_result: ParseResult | None,
    ) -> list[str]:
        """
        为操作流程收集关联的后端 API 信息。

        通过 store action 名称关联 API 定义(启发式:
        action 名 "createOrder" 对应 API 函数 "createOrder")。

        Args:
            flow: 操作流程
            parse_result: 完整解析结果

        Returns:
            格式化的 API 信息行列表
        """
        if parse_result is None:
            return []

        # 构建 API 函数名到 APIInfo 的映射
        api_map: dict[str, APIInfo] = {
            api.function_name: api
            for api in parse_result.api_definitions
        }

        lines: list[str] = []
        seen: set[str] = set()

        # 1. 直接关联的 API 端点
        for api in flow.api_endpoints:
            if api.function_name not in seen:
                lines.append(f"  - {api.function_name}: {api.method.upper()} {api.url}")
                seen.add(api.function_name)

        # 2. 通过 store action 间接关联
        # action 名通常是动词+名词,如 "createOrder"、"fetchList"
        # API 函数名也类似,做模糊匹配
        for action in flow.store_actions:
            # action 可能是 "order/createOrder" 形式
            action_name = action.split("/")[-1] if "/" in action else action
            # 尝试匹配 API 函数
            for api_name, api in api_map.items():
                if api_name in seen:
                    continue
                # 启发式匹配:动作名包含 API 名,或反之
                if (action_name.lower() in api_name.lower()
                        or api_name.lower() in action_name.lower()):
                    lines.append(
                        f"  - {api_name}: {api.method.upper()} {api.url} "
                        f"(通过 store action: {action})",
                    )
                    seen.add(api_name)

        return lines

    def _build_button_item(
        self,
        page: PageInfo,
        button: ButtonInfo,
    ) -> KnowledgeItem | None:
        """为单个按钮生成知识条目"""
        if not button.text:
            return None

        content_parts = [
            f"在「{page.name}」页面中,",
            f"点击「{button.text}」按钮可以执行相关操作。",
        ]

        if button.permission:
            content_parts.append(f"需要权限: {button.permission}")
        if page.path:
            content_parts.append(f"页面路径: {page.path}")

        content = "\n".join(content_parts)
        tags = [page.name, button.text, "按钮操作"]

        return KnowledgeItem(
            id=str(uuid4()),
            type=KnowledgeType.BUTTON,
            title=f"{page.name} - {button.text}",
            content=content,
            page_name=page.name,
            page_path=page.path,
            source_file=page.source_file,
            tags=tags,
        )

    def _build_form_item(
        self,
        page: PageInfo,
        form: FormInfo,
    ) -> KnowledgeItem | None:
        """为单个表单生成知识条目"""
        if not form.fields:
            return None

        content_parts = [
            f"在「{page.name}」页面中包含一个表单,",
            f"数据对象: {form.model}," if form.model else "",
            "\n表单字段:",
        ]
        content_parts = [p for p in content_parts if p]

        for field in form.fields:
            field_desc = f"  - {field.label or field.name}"
            if field.field_type:
                field_desc += f" ({field.field_type})"
            if field.required:
                field_desc += " [必填]"
            content_parts.append(field_desc)

        content = "\n".join(content_parts)
        tags = [page.name, "表单"]

        return KnowledgeItem(
            id=str(uuid4()),
            type=KnowledgeType.FORM,
            title=f"{page.name} - 表单",
            content=content,
            page_name=page.name,
            page_path=page.path,
            source_file=page.source_file,
            tags=tags,
        )

    def _build_table_item(
        self,
        page: PageInfo,
        table: TableInfo,
    ) -> KnowledgeItem | None:
        """为单个表格生成知识条目"""
        if not table.columns:
            return None

        content_parts = [
            f"在「{page.name}」页面中展示数据表格,",
            f"数据源: {table.data}," if table.data else "",
            "\n表格列:",
        ]
        content_parts = [p for p in content_parts if p]

        for col in table.columns:
            col_desc = f"  - {col.label or col.prop}"
            if col.sortable:
                col_desc += " (可排序)"
            content_parts.append(col_desc)

        content = "\n".join(content_parts)
        tags = [page.name, "表格"]

        return KnowledgeItem(
            id=str(uuid4()),
            type=KnowledgeType.PAGE,
            title=f"{page.name} - 数据表格",
            content=content,
            page_name=page.name,
            page_path=page.path,
            source_file=page.source_file,
            tags=tags,
        )

    # ========================================================================
    # 辅助方法
    # ========================================================================

    def _describe_button(self, button: ButtonInfo) -> str:
        """生成按钮描述"""
        text = button.text or "未命名按钮"
        desc = f"「{text}」"
        if button.permission:
            desc += f" [权限: {button.permission}]"
        if button.button_type:
            desc += f" (样式: {button.button_type})"
        return desc

    def _describe_form(self, form: FormInfo) -> str:
        """生成表单描述"""
        lines = []
        if form.model:
            lines.append(f"数据对象: {form.model}")
        for field in form.fields:
            line = f"  - {field.label or field.name}"
            if field.field_type:
                line += f" ({field.field_type})"
            if field.required:
                line += " [必填]"
            lines.append(line)
        return "\n".join(lines)

    def _describe_table(self, table: TableInfo) -> str:
        """生成表格描述"""
        lines = []
        if table.data:
            lines.append(f"数据源: {table.data}")
        col_names = [col.label or col.prop for col in table.columns if col.label or col.prop]
        if col_names:
            lines.append(f"列: {', '.join(col_names)}")
        return "\n".join(lines)

    def _describe_dialog(self, dialog: DialogInfo) -> str:
        """生成弹窗描述"""
        title = dialog.title or "未命名弹窗"
        desc = f"「{title}」"
        if dialog.content_hint:
            desc += f" ({dialog.content_hint})"
        return desc

    def _find_related_apis(
        self,
        page: PageInfo,
        parse_result: ParseResult | None,
    ) -> list[APIInfo]:
        """查找页面关联的 API 接口"""
        if parse_result is None or not page.api_calls:
            return []

        api_map = {
            api.function_name: api
            for api in parse_result.api_definitions
        }
        return [api_map[name] for name in page.api_calls if name in api_map]

    def _find_related_actions(
        self,
        page: PageInfo,
        parse_result: ParseResult | None,
    ) -> list[str]:
        """查找页面关联的 Store actions"""
        return list(page.store_modules)

    def _generate_tags(self, page: PageInfo) -> list[str]:
        """为页面生成标签列表"""
        tags = [page.name]
        if page.buttons:
            tags.extend([b.text for b in page.buttons if b.text])
        return list(dict.fromkeys(tags))[:10]  # 最多 10 个标签,去重
