"""Vue 2 单文件组件(SFC)解析器模块。

本模块是 Vue 文件解析的入口,负责:
1. 拆分 .vue 文件的 <template>、<script>、<style> 三部分
2. 调用 ComponentParser 解析 template 中的 Element UI 组件
3. 调用 StoreParser 和 APIParser 提取 script 中的 dispatch/commit/API 调用
4. 汇总解析结果为 SFCParseResult

典型用法:
    >>> from src.parser.vue_parser import VueSFCParser
    >>> parser = VueSFCParser()
    >>> result = parser.parse_file("src/views/order/list.vue")
    >>> print(result.buttons, result.forms)
"""

from __future__ import annotations

import re
from pathlib import Path

from loguru import logger

from src.domain.exceptions import ParserError
from src.parser.api_parser import APIParser
from src.parser.component_parser import ComponentParser
from src.parser.models import (
    ButtonInfo,
    DialogInfo,
    FormInfo,
    MethodInfo,
    OperationFlow,
    OperationStep,
    SFCParseResult,
)
from src.parser.script_analyzer import ScriptAnalyzer
from src.parser.store_parser import StoreParser


# ============================================================================
# Vue SFC 区块分割正则
# ============================================================================

# 匹配 <script> 标签(支持 lang 等属性)
_SCRIPT_RE = re.compile(
    r"<script(\s[^>]*)?>(.+?)</script>",
    re.DOTALL,
)
# 匹配 <style> 标签(支持 lang、scoped 等属性)
_STYLE_RE = re.compile(
    r"<style(\s[^>]*)?>(.+?)</style>",
    re.DOTALL,
)
# 匹配 <template> 开始标签(用于定位起点)
_TEMPLATE_START_RE = re.compile(
    r"<template(\s[^>]*)?>",
    re.DOTALL,
)


# ============================================================================
# VueSFCParser
# ============================================================================

class VueSFCParser:
    """
    Vue 2 单文件组件解析器。

    负责拆分 .vue 文件的三个区块(template/script/style),
    并调用各子解析器提取组件、Store、API 信息,
    追踪 button @click → method → API 的完整操作流程链路。

    Attributes:
        component_parser: Element UI 组件提取器
        store_parser: Vuex Store 解析器(用于提取 script 中的 dispatch/commit)
        api_parser: API 解析器(用于提取 script 中的 API 调用)
        script_analyzer: script 区块分析器(提取 methods 及其内部调用)
    """

    def __init__(self) -> None:
        """初始化 SFC 解析器"""
        self.component_parser = ComponentParser()
        self.store_parser = StoreParser()
        self.api_parser = APIParser()
        self.script_analyzer = ScriptAnalyzer()

    def parse_file(self, file_path: str | Path) -> SFCParseResult:
        """
        解析单个 .vue 文件。

        Args:
            file_path: .vue 文件路径

        Returns:
            SFCParseResult 解析结果

        Raises:
            ParserError: 文件不存在或解析失败
        """
        path = Path(file_path)
        if not path.exists():
            raise ParserError(f"Vue 文件不存在: {file_path}")

        try:
            content = path.read_text(encoding="utf-8")
            return self.parse_content(content, source_file=str(path))
        except UnicodeDecodeError as e:
            raise ParserError(f"Vue 文件编码错误: {file_path}") from e
        except ParserError:
            raise
        except Exception as e:
            raise ParserError(f"解析 Vue 文件失败: {file_path}, {e}") from e

    def parse_content(self, content: str, source_file: str = "") -> SFCParseResult:
        """
        解析 .vue 文件内容字符串。

        Args:
            content: .vue 文件内容
            source_file: 来源文件路径(用于记录)

        Returns:
            SFCParseResult 解析结果,包含:
            - template 中的组件(按钮/表单/表格/弹窗)
            - script 中的方法列表和操作流程
            - 追踪得到的 button → method → API 操作流程链路
        """
        result = SFCParseResult(file_path=source_file)

        # ── 1. 拆分 SFC 区块 ──
        result.template_content = self._extract_template_block(content)
        result.script_content = self._extract_block(content, _SCRIPT_RE)
        result.style_content = self._extract_block(content, _STYLE_RE)

        # ── 2. 解析 template 中的 Element UI 组件 ──
        if result.template_content:
            buttons, forms, tables, dialogs = self.component_parser.parse(
                result.template_content,
            )
            result.buttons = buttons
            result.forms = forms
            result.tables = tables
            result.dialogs = dialogs

        # ── 3. 解析 script 中的 Store 和 API 调用(顶层) ──
        if result.script_content:
            result.dispatched_actions = self.store_parser.extract_dispatches_from_script(
                result.script_content,
            )
            result.committed_mutations = self.store_parser.extract_commits_from_script(
                result.script_content,
            )
            result.called_apis = self.api_parser.extract_api_calls_from_script(
                result.script_content,
            )

            # ── 4. 分析 script 中的 methods ──
            result.methods = self.script_analyzer.analyze_methods(result.script_content)

        # ── 5. 追踪 button → method → API 操作流程 ──
        result.operation_flows = self._trace_operation_flows(result)

        logger.debug(
            "SFC 解析完成 | file={} | buttons={} | forms={} | tables={} | dialogs={} | methods={} | flows={}",
            source_file or "<string>",
            len(result.buttons),
            len(result.forms),
            len(result.tables),
            len(result.dialogs),
            len(result.methods),
            len(result.operation_flows),
        )

        return result

    def _trace_operation_flows(self, result: SFCParseResult) -> list[OperationFlow]:
        """
        追踪 button @click → method → API 的完整操作流程。

        对每个有 @click 事件的按钮:
        1. 找到对应的方法
        2. 递归展开该方法调用的其他方法(展开到 3 层)
        3. 汇总所有 dispatch/commit/API 调用
        4. 关联相关的弹窗和表单

        Args:
            result: SFC 解析结果(包含 buttons、methods、dialogs、forms)

        Returns:
            追踪得到的操作流程列表
        """
        if not result.buttons or not result.methods:
            return []

        # 构建方法名到 MethodInfo 的索引
        method_map: dict[str, MethodInfo] = {m.name: m for m in result.methods}
        # 构建弹窗 visible 变量到 DialogInfo 的索引
        dialog_map: dict[str, DialogInfo] = {d.visible: d for d in result.dialogs if d.visible}

        flows: list[OperationFlow] = []
        for button in result.buttons:
            if not button.event:
                continue
            # 提取事件处理方法名(可能有参数,如 handleDelete(scope.row))
            method_name = button.event.split("(")[0].strip()
            if method_name not in method_map:
                continue

            # 递归展开方法调用链
            aggregated = self._expand_method_calls(
                method_name, method_map, visited=set(), max_depth=3,
            )

            # 构建操作流程
            flow = OperationFlow(
                name=button.text or method_name,
                entry_button=button,
                entry_method=method_name,
                store_actions=list(aggregated["dispatched_actions"]),
            )

            # 填充步骤
            flow.steps = self._build_operation_steps(button, aggregated, dialog_map)

            # 关联弹窗(在方法链中有引用的)
            for dialog_var in aggregated["referenced_dialogs"]:
                if dialog_var in dialog_map:
                    flow.dialog_involved = dialog_map[dialog_var]
                    break

            # 关联表单(如果弹窗包含表单,或方法涉及表单)
            if flow.dialog_involved is not None and "包含表单" in flow.dialog_involved.content_hint:
                # 找到弹窗内的表单:优先匹配方法体中引用的表单模型
                flow.form_involved = self._find_form_for_flow(
                    flow, result.forms, method_map, aggregated,
                )
            elif result.forms:
                # 非弹窗场景,查找方法体中实际引用的表单
                referenced_form = self._find_form_for_flow(
                    flow, result.forms, method_map, aggregated,
                )
                if referenced_form is not None:
                    flow.form_involved = referenced_form

            # 关联 API 调用
            flow.api_endpoints = []  # 由上层(构建器)根据 store_actions 关联

            flows.append(flow)

        return flows

    def _expand_method_calls(
        self,
        method_name: str,
        method_map: dict[str, MethodInfo],
        visited: set[str],
        max_depth: int,
    ) -> dict:
        """
        递归展开方法调用链,聚合所有 dispatch/API/dialog 引用。

        Args:
            method_name: 当前方法名
            method_map: 方法名 → MethodInfo 映射
            visited: 已访问的方法名(防止循环)
            max_depth: 最大展开深度

        Returns:
            聚合的调用信息字典:
            - dispatched_actions: set
            - committed_mutations: set
            - called_apis: set
            - referenced_dialogs: set
            - visited_methods: set
        """
        if method_name in visited or max_depth <= 0 or method_name not in method_map:
            return {
                "dispatched_actions": set(),
                "committed_mutations": set(),
                "called_apis": set(),
                "referenced_dialogs": set(),
                "visited_methods": set(),
            }

        visited.add(method_name)
        method = method_map[method_name]

        aggregated = {
            "dispatched_actions": set(method.dispatched_actions),
            "committed_mutations": set(method.committed_mutations),
            "called_apis": set(method.called_apis),
            "referenced_dialogs": set(method.referenced_dialogs),
            "visited_methods": {method_name},
        }

        # 递归展开子方法调用
        for sub_method_name in method.called_methods:
            sub_result = self._expand_method_calls(
                sub_method_name, method_map, visited, max_depth - 1,
            )
            for key in aggregated:
                if isinstance(aggregated[key], set):
                    aggregated[key] |= sub_result[key]

        return aggregated

    def _build_operation_steps(
        self,
        button: ButtonInfo,
        aggregated: dict,
        dialog_map: dict[str, DialogInfo],
    ) -> list[OperationStep]:
        """
        根据聚合的调用信息构建操作步骤列表。

        Args:
            button: 入口按钮
            aggregated: 聚合的调用信息
            dialog_map: 弹窗变量名 → DialogInfo 映射

        Returns:
            操作步骤列表
        """
        steps: list[OperationStep] = []

        # 步骤 1: 点击入口按钮
        steps.append(OperationStep(
            action=f"点击「{button.text or button.event}」按钮",
            detail=f"权限: {button.permission}" if button.permission else "",
        ))

        # 步骤 2: 如果会打开弹窗,提示弹窗操作
        for dialog_var in aggregated["referenced_dialogs"]:
            if dialog_var in dialog_map:
                dialog = dialog_map[dialog_var]
                steps.append(OperationStep(
                    action=f"在弹出的「{dialog.title or '对话框'}」中操作",
                    detail=dialog.content_hint or "",
                ))
                break

        # 步骤 3: 如果有 store actions,说明数据操作
        if aggregated["dispatched_actions"]:
            actions = list(aggregated["dispatched_actions"])
            steps.append(OperationStep(
                action=f"触发数据操作: {', '.join(actions)}",
                detail="系统将调用后端接口处理",
            ))

        return steps

    def _method_uses_form(
        self,
        method: MethodInfo | None,
        forms: list[FormInfo],
    ) -> bool:
        """判断方法是否涉及表单操作(通过方法体内容启发式判断)"""
        if method is None or not forms:
            return False
        # 检查方法体中是否出现 form 引用
        for form in forms:
            if form.model and form.model in method.body:
                return True
        return False

    def _find_form_for_flow(
        self,
        flow: OperationFlow,
        forms: list[FormInfo],
        method_map: dict[str, MethodInfo],
        aggregated: dict,
    ) -> FormInfo | None:
        """
        为操作流程找到关联的表单。

        优先级:
        1. 入口方法(直接触发按钮的方法)体中引用的表单模型
        2. 方法链中引用的表单模型(排除仅被 loadData 等查询方法引用的表单)
        3. 与弹窗变量名相近的表单(启发式,如 createDialogVisible ↔ createForm)
        4. 若找不到,返回 None

        Args:
            flow: 操作流程
            forms: 页面所有表单
            method_map: 方法映射
            aggregated: 聚合的调用信息

        Returns:
            关联的表单,或 None
        """
        if not forms:
            return None

        # 优先级 1: 入口方法体中直接引用的表单
        entry_method = method_map.get(flow.entry_method)
        if entry_method is not None:
            for form in forms:
                if form.model and form.model in entry_method.body:
                    return form

        # 优先级 2: 方法链中引用的表单(排除入口方法已处理的情况)
        # 只考虑非"通用查询"类方法引用的表单
        # (loadData 这类刷新方法通常引用 searchForm,但不代表它是该操作的表单)
        chained_body = ""
        for method_name in aggregated["visited_methods"]:
            if method_name == flow.entry_method:
                continue
            method = method_map.get(method_name)
            if method:
                # 排除典型的数据加载/刷新方法(它们通常引用搜索表单,而非操作表单)
                if method.name.lower().startswith(("load", "fetch", "refresh", "get")):
                    continue
                chained_body += " " + method.body

        if chained_body.strip():
            for form in forms:
                if form.model and form.model in chained_body:
                    return form

        # 优先级 3: 名称相近(如 createDialogVisible ↔ createForm)
        if flow.dialog_involved and flow.dialog_involved.visible:
            dialog_var = flow.dialog_involved.visible
            prefix = ""
            for suffix in ("DialogVisible", "PopupVisible", "ModalVisible",
                           "Dialog", "Popup", "Modal", "Visible"):
                if dialog_var.endswith(suffix) and len(dialog_var) > len(suffix):
                    prefix = dialog_var[:-len(suffix)]
                    break

            if prefix:
                for form in forms:
                    if form.model and form.model.startswith(prefix):
                        return form

        return None

    def _extract_template_block(self, content: str) -> str:
        """
        提取 <template> 区块内容,正确处理嵌套的 <template> 标签。

        Vue SFC 的 template 中可能存在嵌套 template (如 slot-scope),
        需要按标签配对查找最外层 </template> 闭合位置。

        Args:
            content: .vue 文件完整内容

        Returns:
            template 区块内容(去除首尾空白),未找到则返回空字符串
        """
        start_match = _TEMPLATE_START_RE.search(content)
        if start_match is None:
            return ""

        start_pos = start_match.end()  # <template ...> 之后

        # 从 start_pos 开始,按 <template 和 </template> 配对查找闭合位置
        depth = 1
        pos = start_pos
        lower_content = content.lower()

        while depth > 0 and pos < len(content):
            next_open = lower_content.find("<template", pos)
            next_close = lower_content.find("</template>", pos)

            if next_close == -1:
                # 没有闭合标签,取到末尾
                break

            if next_open != -1 and next_open < next_close:
                # 先遇到开标签
                # 检查是否是完整的 <template> 或 <template ...>
                after_tag = next_open + len("<template")
                if after_tag < len(content) and content[after_tag] in (" ", ">", "\n", "\r", "\t"):
                    depth += 1
                pos = after_tag
            else:
                # 先遇到闭标签
                depth -= 1
                if depth == 0:
                    return content[start_pos:next_close].strip()
                pos = next_close + len("</template>")

        return content[start_pos:].strip()

    def _extract_block(self, content: str, pattern: re.Pattern) -> str:
        """
        使用正则提取 SFC 区块内容。

        Args:
            content: .vue 文件完整内容
            pattern: 区块匹配正则

        Returns:
            区块内容(去除首尾空白),未找到则返回空字符串
        """
        match = pattern.search(content)
        if match is None:
            return ""
        return match.group(2).strip()


# ============================================================================
# VueProjectParser — 项目级解析入口
# ============================================================================

class VueProjectParser:
    """
    Vue 2 项目级解析入口。

    串联路由解析、组件解析、Store 解析、API 解析,输出完整的 ParseResult。

    Attributes:
        project_root: 项目根目录
        vue_parser: 单文件组件解析器
        router_parser: 路由解析器(从 router_parser 模块导入)
        store_parser: Vuex Store 解析器
        api_parser: API 解析器
    """

    def __init__(self, project_root: str | Path) -> None:
        """
        初始化项目解析器。

        Args:
            project_root: Vue 项目根目录
        """
        self.project_root = Path(project_root)
        self.vue_parser = VueSFCParser()
        # 延迟导入避免循环依赖
        from src.parser.router_parser import RouterParser
        self.router_parser = RouterParser()
        self.store_parser = StoreParser()
        self.api_parser = APIParser()

    def parse(self) -> "ParseResult":
        """
        完整解析整个 Vue 项目。

        流程:
        1. 扫描项目结构,识别目录布局
        2. 解析路由配置 → 页面列表
        3. 解析每个页面 .vue 文件 → 提取组件
        4. 解析 Vuex Store → 提取数据操作
        5. 解析 API 文件 → 提取接口定义
        6. 汇总所有解析结果

        Returns:
            ParseResult 完整解析结果

        Raises:
            ParserError: 项目目录不存在或关键解析失败
        """
        from src.parser.models import PageInfo, ParseResult

        if not self.project_root.exists():
            raise ParserError(f"项目目录不存在: {self.project_root}")

        result = ParseResult(project_root=self.project_root)

        # ── 1. 解析路由 ──
        router_file = self._find_router_file()
        if router_file is not None:
            try:
                result.routes = self.router_parser.parse_file(router_file)
            except ParserError as e:
                result.errors.append(f"路由解析失败: {e}")

        # ── 2. 解析 Store ──
        store_dir = self._find_store_dir()
        if store_dir is not None:
            try:
                result.store_modules = self.store_parser.parse_directory(store_dir)
            except ParserError as e:
                result.errors.append(f"Store 解析失败: {e}")

        # ── 3. 解析 API ──
        api_dir = self._find_api_dir()
        if api_dir is not None:
            try:
                result.api_definitions = self.api_parser.parse_directory(api_dir)
            except ParserError as e:
                result.errors.append(f"API 解析失败: {e}")

        # ── 4. 解析页面 Vue 文件 ──
        pages = self._build_pages_from_routes(result.routes)
        self._parse_page_files(pages)
        result.pages = pages

        logger.info(
            "项目解析完成 | root={} | routes={} | pages={} | store_modules={} | apis={}",
            self.project_root,
            len(result.routes),
            len(result.pages),
            len(result.store_modules),
            len(result.api_definitions),
        )

        return result

    def _find_router_file(self) -> Path | None:
        """在项目根目录下查找路由配置文件"""
        candidates = [
            self.project_root / "src" / "router" / "index.js",
            self.project_root / "src" / "router" / "index.ts",
            self.project_root / "src" / "router.js",
            self.project_root / "router" / "index.js",
        ]
        for c in candidates:
            if c.exists():
                return c
        return None

    def _find_store_dir(self) -> Path | None:
        """在项目根目录下查找 Store 目录"""
        candidates = [
            self.project_root / "src" / "store",
            self.project_root / "store",
        ]
        for c in candidates:
            if c.is_dir():
                return c
        return None

    def _find_api_dir(self) -> Path | None:
        """在项目根目录下查找 API 目录"""
        candidates = [
            self.project_root / "src" / "api",
            self.project_root / "src" / "apis",
            self.project_root / "src" / "services",
            self.project_root / "api",
        ]
        for c in candidates:
            if c.is_dir():
                return c
        return None

    def _build_pages_from_routes(self, routes) -> list:
        """
        从路由列表构建页面列表(扁平化)。

        Args:
            routes: 路由信息列表

        Returns:
            PageInfo 列表(每个叶子路由对应一个页面)
        """
        from src.parser.models import PageInfo

        pages: list[PageInfo] = []

        def visit(route) -> None:
            # 只处理指向文件路径的组件(以 @/ 或 ./ 开头)
            # 跳过 Layout 等纯组件标识符
            if not route.component_path:
                pass
            elif route.component_path.startswith("@") or route.component_path.startswith("."):
                page = PageInfo(
                    name=route.title or route.name or route.path,
                    path=route.full_path,
                    component_path=route.component_path,
                    route=route,
                )
                pages.append(page)
            for child in route.children:
                visit(child)

        for route in routes:
            visit(route)

        return pages

    def _parse_page_files(self, pages: list) -> None:
        """
        尝试为每个页面找到对应的 .vue 文件并解析。

        根据 component_path (如 @/views/order/list) 推断文件路径,
        然后调用 VueSFCParser 解析。

        Args:
            pages: 待解析的页面列表
        """
        for page in pages:
            vue_file = self._resolve_component_path(page.component_path)
            if vue_file is None:
                continue

            try:
                sfc_result = self.vue_parser.parse_file(vue_file)
                page.source_file = str(vue_file)
                page.buttons = sfc_result.buttons
                page.forms = sfc_result.forms
                page.tables = sfc_result.tables
                page.dialogs = sfc_result.dialogs
                page.methods = sfc_result.methods
                page.operation_flows = sfc_result.operation_flows
                page.store_modules = sfc_result.dispatched_actions
                page.api_calls = sfc_result.called_apis
            except ParserError as e:
                logger.warning("页面解析失败 | page={} | error={}", page.name, e)

    def _resolve_component_path(self, component_path: str) -> Path | None:
        """
        将 @/views/xxx 形式的组件路径解析为实际的 .vue 文件路径。

        Args:
            component_path: 组件路径,如 "@/views/order/list"

        Returns:
            找到的 .vue 文件路径,未找到返回 None
        """
        if not component_path:
            return None

        # 跳过标识符形式的组件(如 Layout,非路径)
        if not component_path.startswith("@") and not component_path.startswith("."):
            return None

        # 移除 @/ 或 ./ 前缀
        relative = component_path
        if relative.startswith("@/"):
            relative = relative[2:]
        elif relative.startswith("./"):
            relative = relative[2:]

        # 在 src/ 目录下查找
        base = self.project_root / "src" / relative
        candidates = [
            base.with_suffix(".vue"),
            base / "index.vue",
            base.with_suffix(".tsx"),
            base.with_suffix(".jsx"),
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return None
