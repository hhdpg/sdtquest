"""Vuex Store 解析器模块。

本模块负责解析 Vue 2 项目中的 Vuex Store 模块(通常在 src/store/ 目录下),
使用 tree-sitter 构建 JavaScript AST,提取:
- state 字段
- actions 方法
- mutations 方法
- getters 方法
- namespaced 配置

典型用法:
    >>> from src.parser.store_parser import StoreParser
    >>> parser = StoreParser()
    >>> modules = parser.parse_directory("src/store")
    >>> for m in modules:
    ...     print(m.name, m.actions)
"""

from __future__ import annotations

import re
from pathlib import Path

import tree_sitter
from loguru import logger

from src.domain.exceptions import ParserError
from src.parser.models import StoreModuleInfo
from src.parser.ts_utils import parse_javascript


# ============================================================================
# StoreParser
# ============================================================================

class StoreParser:
    """
    Vuex Store 解析器。

    使用 tree-sitter 解析 JavaScript AST,从 Store 模块文件中提取
    state、actions、mutations、getters 等定义。

    Attributes:
        store_dirs: 默认的 Store 目录名列表
    """

    def __init__(self) -> None:
        """初始化 Store 解析器"""
        self.store_dirs = ["store", "stores"]
        self.modules_subdirs = ["modules"]

    def parse_directory(self, dir_path: str | Path) -> list[StoreModuleInfo]:
        """
        扫描整个 Store 目录,解析所有模块文件。

        支持两种目录布局:
        1. src/store/index.js + src/store/modules/*.js (模块化)
        2. src/store/*.js (扁平)

        Args:
            dir_path: Store 目录路径

        Returns:
            解析出的 Store 模块信息列表
        """
        path = Path(dir_path)
        if not path.exists() or not path.is_dir():
            raise ParserError(f"Store 目录不存在: {dir_path}")

        modules: list[StoreModuleInfo] = []
        seen_files: set[Path] = set()

        # 查找 modules 子目录
        for subdir_name in self.modules_subdirs:
            modules_dir = path / subdir_name
            if modules_dir.is_dir():
                for js_file in modules_dir.glob("*.js"):
                    if js_file in seen_files:
                        continue
                    seen_files.add(js_file)
                    try:
                        module = self.parse_file(js_file)
                        if module.name == "":
                            module.name = js_file.stem
                        modules.append(module)
                    except ParserError as e:
                        logger.warning("解析 Store 模块失败 | file={} | error={}", js_file, e)

        # 直接位于 store/ 目录下的 js 文件(非 index.js)
        for js_file in path.glob("*.js"):
            if js_file.name in ("index.js", "index.ts") or js_file in seen_files:
                continue
            seen_files.add(js_file)
            try:
                module = self.parse_file(js_file)
                if module.name == "":
                    module.name = js_file.stem
                modules.append(module)
            except ParserError as e:
                logger.warning("解析 Store 模块失败 | file={} | error={}", js_file, e)

        logger.info("Store 解析完成 | dir={} | modules={}", dir_path, len(modules))
        return modules

    def parse_file(self, file_path: str | Path) -> StoreModuleInfo:
        """
        解析单个 Vuex Store 模块文件。

        Args:
            file_path: Store 模块文件路径

        Returns:
            StoreModuleInfo

        Raises:
            ParserError: 文件不存在或解析失败
        """
        path = Path(file_path)
        if not path.exists():
            raise ParserError(f"Store 模块文件不存在: {file_path}")

        try:
            code = path.read_text(encoding="utf-8")
            return self.parse_code(code, source_file=str(path), module_name=path.stem)
        except UnicodeDecodeError as e:
            raise ParserError(f"Store 文件编码错误: {file_path}") from e
        except ParserError:
            raise
        except Exception as e:
            raise ParserError(f"解析 Store 模块失败: {file_path}, {e}") from e

    def parse_code(
        self,
        code: str,
        source_file: str = "",
        module_name: str = "",
    ) -> StoreModuleInfo:
        """
        解析 Store 模块 JavaScript 代码。

        Args:
            code: JavaScript 代码内容
            source_file: 来源文件路径(用于记录)
            module_name: 模块名称(用于记录)

        Returns:
            StoreModuleInfo
        """
        tree = parse_javascript(code)
        root = tree.root_node

        module = StoreModuleInfo(name=module_name, source_file=source_file)

        # 查找 export default { ... } 对象
        store_object = self._find_export_default_object(root)
        if store_object is None:
            # 可能是 module.exports = { ... }
            store_object = self._find_module_exports_object(root)
        if store_object is None:
            # 可能是一个 const xxx = { ... },然后 export default xxx
            store_object = self._find_store_object_by_variable(root)

        if store_object is None:
            logger.warning("未找到 Store 对象 | source={}", source_file)
            return module

        # 检查 namespaced
        namespaced_value = self._find_property_value(store_object, "namespaced")
        if namespaced_value is not None:
            module.namespaced = self._node_text(namespaced_value).lower() == "true"

        # 提取 state
        state_node = self._find_property_value(store_object, "state")
        if state_node is not None:
            module.state_fields = self._extract_state_fields(state_node)

        # 提取 actions
        actions_node = self._find_property_value(store_object, "actions")
        if actions_node is not None and actions_node.type == "object":
            module.actions = self._extract_method_names(actions_node)

        # 提取 mutations
        mutations_node = self._find_property_value(store_object, "mutations")
        if mutations_node is not None and mutations_node.type == "object":
            module.mutations = self._extract_method_names(mutations_node)

        # 提取 getters
        getters_node = self._find_property_value(store_object, "getters")
        if getters_node is not None and getters_node.type == "object":
            module.getters = self._extract_method_names(getters_node)

        return module

    def extract_dispatches_from_script(self, script_content: str) -> list[str]:
        """
        从 <script> 内容中提取 dispatch 调用的 actions 列表。

        匹配形如: this.$store.dispatch('order/fetchList') 或 dispatch('fetchList')

        Args:
            script_content: <script> 标签内的 JavaScript 代码

        Returns:
            action 名称列表(去重)
        """
        pattern = r"""dispatch\(\s*['"]([^'"]+)['"]"""
        matches = re.findall(pattern, script_content)
        return list(dict.fromkeys(matches))

    def extract_commits_from_script(self, script_content: str) -> list[str]:
        """
        从 <script> 内容中提取 commit 调用的 mutations 列表。

        Args:
            script_content: <script> 标签内的 JavaScript 代码

        Returns:
            mutation 名称列表(去重)
        """
        pattern = r"""commit\(\s*['"]([^'"]+)['"]"""
        matches = re.findall(pattern, script_content)
        return list(dict.fromkeys(matches))

    # ========================================================================
    # 内部方法
    # ========================================================================

    def _find_export_default_object(self, root: tree_sitter.Node) -> tree_sitter.Node | None:
        """查找 export default { ... } 中的对象"""
        for node in root.children:
            if node.type == "export_statement":
                for child in node.children:
                    if child.type == "object":
                        return child
        return None

    def _find_module_exports_object(self, root: tree_sitter.Node) -> tree_sitter.Node | None:
        """查找 module.exports = { ... } 中的对象"""
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

    def _find_store_object_by_variable(self, root: tree_sitter.Node) -> tree_sitter.Node | None:
        """查找 const store = { ... }; export default store 中的对象"""
        # 查找 export default 后的标识符
        exported_name = None
        for node in root.children:
            if node.type == "export_statement":
                for child in node.children:
                    if child.type == "identifier":
                        exported_name = self._node_text(child)
                        break

        if not exported_name:
            return None

        # 查找同名变量声明
        for node in root.children:
            if node.type == "lexical_declaration":
                for child in node.children:
                    if child.type == "variable_declarator":
                        for sub in child.children:
                            if sub.type == "identifier" and self._node_text(sub) == exported_name:
                                # 找到同名声明,取 object 值
                                for val in child.children:
                                    if val.type == "object":
                                        return val
        return None

    def _find_property_value(
        self,
        obj_node: tree_sitter.Node,
        key: str,
    ) -> tree_sitter.Node | None:
        """在 object 节点中查找指定 key 的 value 节点"""
        for child in obj_node.children:
            if child.type == "pair":
                key_node = None
                value_node = None
                for pair_child in child.children:
                    if pair_child.type == "property_identifier":
                        key_node = pair_child
                    elif pair_child.type not in (":", "property_identifier"):
                        value_node = pair_child
                if key_node is not None and self._node_text(key_node) == key:
                    return value_node
        return None

    def _extract_state_fields(self, state_node: tree_sitter.Node) -> list[str]:
        """
        提取 state 字段名。支持两种形式:
        1. state: { list: [], detail: null, loading: false } (对象)
        2. state: () => ({ list: [], loading: false }) (工厂函数)
        """
        # 工厂函数形式: () => ({ ... })
        if state_node.type in ("arrow_function", "function"):
            for child in state_node.children:
                if child.type == "object":
                    state_node = child
                    break
                # 也可能被括号包裹 (parenthesized_expression)
                if child.type == "parenthesized_expression":
                    for sub in child.children:
                        if sub.type == "object":
                            state_node = sub
                            break

        if state_node.type != "object":
            return []

        fields: list[str] = []
        for child in state_node.children:
            if child.type == "pair":
                for sub in child.children:
                    if sub.type == "property_identifier":
                        fields.append(self._node_text(sub))
                        break
        return fields

    def _extract_method_names(self, methods_node: tree_sitter.Node) -> list[str]:
        """从 actions/mutations/getters 对象中提取方法名"""
        names: list[str] = []
        for child in methods_node.children:
            if child.type == "pair":
                # 普通属性: fetchList: function(...) {}  或  fetchList: async (...) => {}
                for sub in child.children:
                    if sub.type == "property_identifier":
                        names.append(self._node_text(sub))
                        break
            elif child.type == "method_definition":
                # 方法简写: async fetchList({ commit }) { ... }
                for sub in child.children:
                    if sub.type == "property_identifier":
                        names.append(self._node_text(sub))
                        break
        return names

    @staticmethod
    def _node_text(node: tree_sitter.Node) -> str:
        """获取节点的文本内容"""
        if node.text is None:
            return ""
        return node.text.decode("utf-8")
