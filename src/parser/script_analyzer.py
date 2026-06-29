"""Vue 组件 script 区块分析器模块。

本模块负责分析 Vue 单文件组件 <script> 区块中的:
- methods 对象内每个方法的定义(方法名、方法体、是否 async)
- 方法体内的 store dispatch/commit 调用
- 方法体内的 API 函数调用
- 方法体内的弹窗可见性变量赋值(如 this.dialogVisible = true)
- 方法体内调用的其他 methods 方法

这些信息用于追踪 button @click → method → API 的完整链路。

典型用法:
    >>> from src.parser.script_analyzer import ScriptAnalyzer
    >>> analyzer = ScriptAnalyzer()
    >>> methods = analyzer.analyze_methods(script_content)
    >>> for m in methods:
    ...     print(m.name, m.dispatched_actions, m.called_apis)
"""

from __future__ import annotations

import re

import tree_sitter
from loguru import logger

from src.parser.models import MethodInfo
from src.parser.ts_utils import parse_javascript


# ============================================================================
# ScriptAnalyzer
# ============================================================================

class ScriptAnalyzer:
    """
    Vue 组件 <script> 区块分析器。

    使用 tree-sitter 解析 JavaScript AST,提取 methods 对象内的
    方法定义,并分析方法体内的各种调用。
    """

    def analyze_methods(self, script_content: str) -> list[MethodInfo]:
        """
        从 <script> 内容中提取 methods 对象内的所有方法。

        Args:
            script_content: <script> 标签内的 JavaScript 代码

        Returns:
            MethodInfo 列表,每个方法包含名称、方法体、内部调用等信息
        """
        if not script_content or not script_content.strip():
            return []

        try:
            tree = parse_javascript(script_content)
        except Exception as e:
            logger.warning("script 解析失败 | error={}", e)
            return []

        root = tree.root_node

        # 查找 methods: { ... } 对象
        methods_object = self._find_methods_object(root)
        if methods_object is None:
            return []

        # 提取每个方法定义
        methods: list[MethodInfo] = []
        for child in methods_object.children:
            if child.type == "method_definition":
                method = self._parse_method_definition(child, script_content)
                if method is not None:
                    methods.append(method)
            elif child.type == "pair":
                # 形如 loadData: function() {} 或 loadData: async () => {}
                method = self._parse_pair_as_method(child, script_content)
                if method is not None:
                    methods.append(method)

        # 提取方法之间的调用关系(第二次遍历,需要所有方法名)
        method_names = {m.name for m in methods}
        for method in methods:
            method.called_methods = self._find_method_calls_in_body(
                method.body, method_names - {method.name},
            )

        logger.debug(
            "Script 方法分析完成 | methods={}",
            len(methods),
        )

        return methods

    def _find_methods_object(self, root: tree_sitter.Node) -> tree_sitter.Node | None:
        """查找 export default { methods: { ... } } 中的 methods 对象"""
        # 查找顶层的 export default { ... }
        export_object = self._find_export_default_object(root)
        if export_object is None:
            # 也可能是 module.exports = { ... }
            export_object = self._find_module_exports_object(root)
        if export_object is None:
            return None

        # 在 export 对象中找 methods: { ... }
        return self._find_property_object(export_object, "methods")

    def _find_export_default_object(self, root: tree_sitter.Node) -> tree_sitter.Node | None:
        """查找 export default { ... }"""
        for node in root.children:
            if node.type == "export_statement":
                for child in node.children:
                    if child.type == "object":
                        return child
        return None

    def _find_module_exports_object(self, root: tree_sitter.Node) -> tree_sitter.Node | None:
        """查找 module.exports = { ... }"""
        for node in root.children:
            if node.type == "expression_statement":
                text = self._node_text(node)
                if "module.exports" in text:
                    for child in node.children:
                        if child.type == "assignment_expression":
                            for sub in child.children:
                                if sub.type == "object":
                                    return sub
        return None

    def _find_property_object(
        self,
        parent: tree_sitter.Node,
        key: str,
    ) -> tree_sitter.Node | None:
        """在父对象中查找指定 key 对应的 object 值"""
        for child in parent.children:
            if child.type == "pair":
                key_node = None
                value_node = None
                for pair_child in child.children:
                    if pair_child.type == "property_identifier":
                        key_node = pair_child
                    elif pair_child.type not in (":", "property_identifier"):
                        value_node = pair_child
                if key_node is not None and self._node_text(key_node) == key:
                    if value_node is not None and value_node.type == "object":
                        return value_node
        return None

    def _parse_method_definition(
        self,
        node: tree_sitter.Node,
        script_content: str,
    ) -> MethodInfo | None:
        """解析 method_definition 节点(方法简写形式)"""
        method_name = ""
        is_async = False
        body_text = ""
        body_node = None

        for child in node.children:
            if child.type == "async":
                is_async = True
            elif child.type == "property_identifier":
                method_name = self._node_text(child)
            elif child.type == "statement_block":
                body_node = child

        if not method_name:
            return None

        if body_node is not None and body_node.text is not None:
            body_text = self._node_text(body_node)

        method = MethodInfo(
            name=method_name,
            body=body_text,
            async_=is_async,
        )

        # 分析方法体内的调用
        self._analyze_method_body(method, body_node, script_content)

        return method

    def _parse_pair_as_method(
        self,
        node: tree_sitter.Node,
        script_content: str,
    ) -> MethodInfo | None:
        """解析 pair 节点(形如 loadData: function() {} 或 loadData: async () => {})"""
        key_node = None
        value_node = None
        for child in node.children:
            if child.type == "property_identifier":
                key_node = child
            elif child.type not in (":", "property_identifier"):
                value_node = child

        if key_node is None or value_node is None:
            return None

        # 值必须是函数/箭头函数
        if value_node.type not in ("function", "arrow_function", "generator_function"):
            return None

        method_name = self._node_text(key_node)
        is_async = any(c.type == "async" for c in value_node.children)
        body_node = None
        for child in value_node.children:
            if child.type == "statement_block":
                body_node = child
                break

        body_text = self._node_text(body_node) if body_node is not None else ""

        method = MethodInfo(
            name=method_name,
            body=body_text,
            async_=is_async,
        )
        self._analyze_method_body(method, body_node, script_content)
        return method

    def _analyze_method_body(
        self,
        method: MethodInfo,
        body_node: tree_sitter.Node | None,
        script_content: str,
    ) -> None:
        """
        分析方法体内的调用。

        填充 method 的:
        - dispatched_actions
        - committed_mutations
        - called_apis
        - referenced_dialogs
        """
        if body_node is None:
            return

        body_text = self._node_text(body_node)

        # 1. 提取 dispatch('xxx') 调用
        method.dispatched_actions = self._extract_string_args(body_text, r"dispatch\s*\(\s*['\"]([^'\"]+)['\"]")

        # 2. 提取 commit('xxx') 调用
        method.committed_mutations = self._extract_string_args(body_text, r"commit\s*\(\s*['\"]([^'\"]+)['\"]")

        # 3. 提取 API 函数调用(非 this. 前缀的函数调用)
        method.called_apis = self._extract_api_calls(body_node)

        # 4. 提取弹窗可见性赋值 (this.dialogVisible = true/false)
        method.referenced_dialogs = self._extract_dialog_assignments(body_text)

    def _extract_string_args(self, text: str, pattern: str) -> list[str]:
        """使用正则提取函数调用中的字符串参数"""
        matches = re.findall(pattern, text)
        return list(dict.fromkeys(matches))

    def _extract_api_calls(self, body_node: tree_sitter.Node) -> list[str]:
        """
        从方法体的 AST 中提取 API 函数调用。

        识别标准:
        - call_expression 的函数是 identifier(如 `getOrderList(params)`)
        - 不是 this.xxx 形式(那是方法调用)
        - 不是内置函数(console, JSON 等)
        """
        excluded = {
            "if", "for", "while", "switch", "catch", "return", "throw",
            "console", "JSON", "Math", "Date", "Promise",
            "setTimeout", "setInterval", "clearTimeout", "clearInterval",
        }
        calls: list[str] = []
        self._walk_for_api_calls(body_node, calls, excluded)
        return list(dict.fromkeys(calls))

    def _walk_for_api_calls(
        self,
        node: tree_sitter.Node,
        calls: list[str],
        excluded: set[str],
    ) -> None:
        """递归遍历 AST 查找 API 调用"""
        if node.type == "call_expression":
            # 检查函数部分
            for child in node.children:
                if child.type == "identifier":
                    name = self._node_text(child)
                    if name not in excluded and not name[0].isupper():
                        # 排除纯大写开头的(通常是类名)
                        calls.append(name)
                    break
                elif child.type == "member_expression":
                    # this.$store.dispatch('xxx') 这种不算 API
                    # 但可能是 someModule.apiFunc()
                    member_text = self._node_text(child)
                    if not member_text.startswith("this.") and not member_text.startswith("this.$"):
                        # 取最后一段作为函数名
                        parts = member_text.split(".")
                        if len(parts) >= 2:
                            func_name = parts[-1]
                            if func_name not in excluded:
                                calls.append(func_name)
                    break

        for child in node.children:
            self._walk_for_api_calls(child, calls, excluded)

    def _extract_dialog_assignments(self, body_text: str) -> list[str]:
        """
        提取弹窗可见性变量赋值。

        匹配: this.dialogVisible = true/false,  this.xxxDialogVisible = true
        返回: 被赋值的变量名(去掉 this. 前缀)
        """
        pattern = r"this\.(\w*[Dd]ialog\w*|\w*[Pp]opup\w*|\w*[Mm]odal\w*)\s*=\s*(true|false)"
        matches = re.findall(pattern, body_text)
        # matches 是 [(变量名, 值), ...] 形式
        return list(dict.fromkeys(m[0] for m in matches))

    def _find_method_calls_in_body(
        self,
        body_text: str,
        known_methods: set[str],
    ) -> list[str]:
        """
        在方法体中查找调用其他已知方法的情况。

        匹配 this.methodName() 形式。
        """
        called: list[str] = []
        for method_name in known_methods:
            pattern = rf"this\.{re.escape(method_name)}\s*\("
            if re.search(pattern, body_text):
                called.append(method_name)
        return called

    @staticmethod
    def _node_text(node: tree_sitter.Node) -> str:
        """获取节点的文本内容"""
        if node.text is None:
            return ""
        return node.text.decode("utf-8")
