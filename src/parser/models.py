"""Parser 数据模型模块。

定义代码解析过程中产生的所有中间数据结构,包括路由信息、页面信息、
组件信息(按钮/表单/表格/弹窗)、方法信息、操作流程、Store 信息、
API 信息以及完整的解析结果。

主要类:
- RouteInfo: 路由条目信息
- PageInfo: 页面信息(含路由、组件、方法、操作流程、Store、API 关联)
- ButtonInfo: 按钮组件信息
- FormInfo: 表单组件信息
- FormField: 表单字段信息
- TableInfo: 表格组件信息
- TableColumn: 表格列信息
- DialogInfo: 弹窗组件信息
- MethodInfo: Vue 组件 methods 中的方法信息
- OperationStep: 操作流程中的单个步骤
- OperationFlow: 完整的操作流程(button → method → API 链路)
- StoreModuleInfo: Vuex Store 模块信息
- APIInfo: API 接口定义信息
- SFCParseResult: 单个 .vue 文件的解析结果
- ParseResult: 整个 Vue 项目的解析结果

典型用法:
    >>> from src.parser.models import PageInfo, ButtonInfo
    >>> page = PageInfo(name="订单管理", path="/order/list")
    >>> btn = ButtonInfo(text="新建", event="handleCreate")
    >>> page.buttons.append(btn)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


# ============================================================================
# 路由与页面
# ============================================================================

@dataclass
class RouteInfo:
    """
    Vue Router 路由条目信息。

    Attributes:
        path: 路由路径,如 "/order/list"
        name: 路由名称,如 "OrderList"
        title: 页面标题(取自 meta.title),如 "订单列表"
        component_path: 组件路径,如 "@/views/order/list"
        parent_path: 父路由路径(用于嵌套路由)
        children: 子路由列表
        source_file: 来源文件路径
    """
    path: str = ""
    name: str = ""
    title: str = ""
    component_path: str = ""
    parent_path: str = ""
    children: list[RouteInfo] = field(default_factory=list)
    source_file: str = ""

    @property
    def full_path(self) -> str:
        """拼接完整路径(含父路径)"""
        if self.parent_path and not self.path.startswith("/"):
            return f"{self.parent_path.rstrip('/')}/{self.path}"
        return self.path


@dataclass
class PageInfo:
    """
    页面信息,聚合一个页面的全部解析结果。

    Attributes:
        name: 页面名称(meta.title 或从路由推导)
        path: 路由路径
        component_path: 组件路径
        source_file: 实际 .vue 文件路径
        buttons: 页面包含的按钮列表
        forms: 页面包含的表单列表
        tables: 页面包含的表格列表
        dialogs: 页面包含的弹窗列表
        methods: 页面 script 中提取的方法列表
        operation_flows: 追踪得到的操作流程列表
        store_modules: 页面使用的 Vuex Store 模块
        api_calls: 页面调用的 API 列表
        route: 关联的路由信息
    """
    name: str = ""
    path: str = ""
    component_path: str = ""
    source_file: str = ""
    buttons: list[ButtonInfo] = field(default_factory=list)
    forms: list[FormInfo] = field(default_factory=list)
    tables: list[TableInfo] = field(default_factory=list)
    dialogs: list[DialogInfo] = field(default_factory=list)
    methods: list[MethodInfo] = field(default_factory=list)
    operation_flows: list[OperationFlow] = field(default_factory=list)
    store_modules: list[str] = field(default_factory=list)
    api_calls: list[str] = field(default_factory=list)
    route: RouteInfo | None = None


# ============================================================================
# Element UI 组件
# ============================================================================

@dataclass
class ButtonInfo:
    """
    按钮组件信息。

    Attributes:
        text: 按钮文本,如 "新建订单"
        event: @click 事件处理函数名,如 "handleCreate"
        permission: v-permission 权限标识,如 "order:create"
        button_type: el-button type 属性,如 "primary"
        size: 按钮尺寸
        source_line: 来源代码行号(用于定位)
    """
    text: str = ""
    event: str = ""
    permission: str = ""
    button_type: str = ""
    size: str = ""
    source_line: int = 0


@dataclass
class FormField:
    """
    表单字段信息。

    Attributes:
        name: 字段名(prop 属性),如 "orderNo"
        label: 字段标签,如 "订单编号"
        field_type: 字段类型(input/select/date 等),从子组件推断
        placeholder: 占位提示
        required: 是否必填
    """
    name: str = ""
    label: str = ""
    field_type: str = ""
    placeholder: str = ""
    required: bool = False


@dataclass
class FormInfo:
    """
    表单组件信息。

    Attributes:
        model: v-model 绑定的数据对象名,如 "form"
        rules: 校验规则对象名,如 "rules"
        fields: 表单字段列表
        source_line: 来源代码行号
    """
    model: str = ""
    rules: str = ""
    fields: list[FormField] = field(default_factory=list)
    source_line: int = 0


@dataclass
class TableColumn:
    """
    表格列信息。

    Attributes:
        prop: 列字段名,如 "orderNo"
        label: 列标题,如 "订单编号"
        width: 列宽
        sortable: 是否可排序
        formatter: 格式化函数
    """
    prop: str = ""
    label: str = ""
    width: str = ""
    sortable: bool = False
    formatter: str = ""


@dataclass
class TableInfo:
    """
    表格组件信息。

    Attributes:
        data: v-model 数据源,如 "tableData"
        columns: 表格列定义列表
        source_line: 来源代码行号
    """
    data: str = ""
    columns: list[TableColumn] = field(default_factory=list)
    source_line: int = 0


@dataclass
class DialogInfo:
    """
    弹窗组件信息。

    Attributes:
        title: 弹窗标题
        visible: 可见性绑定变量,如 "dialogVisible"
        content_hint: 弹窗内容提示(如包含的表单或文本)
        source_line: 来源代码行号
    """
    title: str = ""
    visible: str = ""
    content_hint: str = ""
    source_line: int = 0


# ============================================================================
# Vuex Store
# ============================================================================

@dataclass
class StoreModuleInfo:
    """
    Vuex Store 模块信息。

    Attributes:
        name: 模块名称,如 "order"
        namespaced: 是否开启命名空间
        state_fields: state 字段名列表,如 ["list", "detail", "loading"]
        actions: actions 方法名列表,如 ["fetchList", "createOrder"]
        mutations: mutations 方法名列表,如 ["SET_LIST", "SET_LOADING"]
        getters: getters 方法名列表
        source_file: 来源文件路径
    """
    name: str = ""
    namespaced: bool = True
    state_fields: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    mutations: list[str] = field(default_factory=list)
    getters: list[str] = field(default_factory=list)
    source_file: str = ""


# ============================================================================
# API 接口
# ============================================================================

@dataclass
class APIInfo:
    """
    API 接口定义信息。

    Attributes:
        function_name: 函数名,如 "createOrder"
        method: HTTP 方法,如 "post"
        url: 请求路径,如 "/api/orders"
        params: 参数描述(原始代码片段)
        source_file: 来源文件路径
        source_line: 来源代码行号
    """
    function_name: str = ""
    method: str = ""
    url: str = ""
    params: str = ""
    source_file: str = ""
    source_line: int = 0


# ============================================================================
# <script> 方法信息
# ============================================================================

@dataclass
class MethodInfo:
    """
    Vue 组件 <script> 中 methods 对象内的方法信息。

    用于追踪 button @click → method → API 调用的链路。

    Attributes:
        name: 方法名,如 "handleCreate"
        body: 方法体的原始代码文本
        async_: 是否为 async 方法
        dispatched_actions: 方法体内 dispatch 的 store actions
        committed_mutations: 方法体内 commit 的 mutations
        called_apis: 方法体内调用的 API 函数名
        referenced_dialogs: 方法体内操作(显示/隐藏)的弹窗变量名
        called_methods: 方法体内调用的其他方法名(本组件 methods 内的)
    """
    name: str = ""
    body: str = ""
    async_: bool = False
    dispatched_actions: list[str] = field(default_factory=list)
    committed_mutations: list[str] = field(default_factory=list)
    called_apis: list[str] = field(default_factory=list)
    referenced_dialogs: list[str] = field(default_factory=list)
    called_methods: list[str] = field(default_factory=list)


# ============================================================================
# 操作流程(结构化操作指南)
# ============================================================================

@dataclass
class OperationStep:
    """
    操作流程中的单个步骤。

    Attributes:
        action: 步骤动作描述,如 "点击「新建订单」按钮"
        target: 作用目标,如 "页面顶部操作区"
        detail: 补充说明,如 "需要 order:create 权限"
    """
    action: str = ""
    target: str = ""
    detail: str = ""


@dataclass
class OperationFlow:
    """
    一个完整的操作流程,由 button → method → API 链路追踪得到。

    用于生成结构化的操作指南,直接回答"怎么做 X"类问题。

    Attributes:
        name: 操作名称,如 "创建订单"
        entry_button: 触发此操作的入口按钮(ButtonInfo)
        entry_method: 入口方法名,如 "handleCreate"
        steps: 操作步骤列表
        form_involved: 涉及的表单(FormInfo,可选)
        dialog_involved: 涉及的弹窗(DialogInfo,可选)
        api_endpoints: 最终调用的 API 列表(APIInfo,从 ParseResult 关联得到)
        store_actions: 触发的 store actions 列表
        expected_outcome: 预期结果描述,如 "创建成功,列表自动刷新"
    """
    name: str = ""
    entry_button: ButtonInfo | None = None
    entry_method: str = ""
    steps: list[OperationStep] = field(default_factory=list)
    form_involved: FormInfo | None = None
    dialog_involved: DialogInfo | None = None
    api_endpoints: list[APIInfo] = field(default_factory=list)
    store_actions: list[str] = field(default_factory=list)
    expected_outcome: str = ""


# ============================================================================
# SFC 解析结果
# ============================================================================

@dataclass
class SFCParseResult:
    """
    单个 .vue 单文件组件的解析结果。

    Attributes:
        file_path: 文件路径
        template_content: <template> 部分原始内容
        script_content: <script> 部分原始内容
        style_content: <style> 部分原始内容
        buttons: 提取的按钮列表
        forms: 提取的表单列表
        tables: 提取的表格列表
        dialogs: 提取的弹窗列表
        methods: 提取的 methods 方法列表
        operation_flows: 追踪得到的操作流程列表
        dispatched_actions: <script> 中 dispatch 的 actions 列表
        committed_mutations: <script> 中 commit 的 mutations 列表
        called_apis: <script> 中调用的 API 函数名列表
    """
    file_path: str = ""
    template_content: str = ""
    script_content: str = ""
    style_content: str = ""
    buttons: list[ButtonInfo] = field(default_factory=list)
    forms: list[FormInfo] = field(default_factory=list)
    tables: list[TableInfo] = field(default_factory=list)
    dialogs: list[DialogInfo] = field(default_factory=list)
    methods: list[MethodInfo] = field(default_factory=list)
    operation_flows: list[OperationFlow] = field(default_factory=list)
    dispatched_actions: list[str] = field(default_factory=list)
    committed_mutations: list[str] = field(default_factory=list)
    called_apis: list[str] = field(default_factory=list)


# ============================================================================
# 项目解析结果
# ============================================================================

@dataclass
class ParseResult:
    """
    整个 Vue 项目的解析结果汇总。

    Attributes:
        project_root: 项目根目录
        routes: 解析出的所有路由
        pages: 解析出的所有页面详情
        store_modules: 解析出的所有 Vuex Store 模块
        api_definitions: 解析出的所有 API 定义
        errors: 解析过程中收集的错误(非致命)
    """
    project_root: Path = field(default_factory=Path)
    routes: list[RouteInfo] = field(default_factory=list)
    pages: list[PageInfo] = field(default_factory=list)
    store_modules: list[StoreModuleInfo] = field(default_factory=list)
    api_definitions: list[APIInfo] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def get_stats(self) -> dict[str, int]:
        """获取解析结果统计"""
        return {
            "routes": len(self.routes),
            "pages": len(self.pages),
            "buttons": sum(len(p.buttons) for p in self.pages),
            "forms": sum(len(p.forms) for p in self.pages),
            "tables": sum(len(p.tables) for p in self.pages),
            "dialogs": sum(len(p.dialogs) for p in self.pages),
            "store_modules": len(self.store_modules),
            "api_definitions": len(self.api_definitions),
            "errors": len(self.errors),
        }
