"""Vue Router 路由配置解析器模块。

本模块负责解析 Vue Router 3 的路由配置文件(通常是 src/router/index.js),
使用 tree-sitter 构建 JavaScript AST,遍历提取:
- 路由路径 (path)
- 页面名称 (meta.title)
- 组件路径 (component)
- 嵌套关系 (children)
- 构建页面层级树

典型用法:
    >>> from src.parser.router_parser import RouterParser
    >>> parser = RouterParser()
    >>> routes = parser.parse_file("src/router/index.js")
    >>> for r in routes:
    ...     print(r.path, r.title)
"""

from __future__ import annotations

from pathlib import Path

import tree_sitter
from loguru import logger

from src.domain.exceptions import ParserError
from src.parser.models import RouteInfo
from src.parser.ts_utils import parse_javascript


# ============================================================================
# RouterParser
# ============================================================================

class RouterParser:
    """
    Vue Router 路由配置解析器。

    使用 tree-sitter 解析 JavaScript AST,从 Vue Router 配置文件中提取
    路由定义,支持嵌套路由和动态导入的组件路径解析。

    Attributes:
        supported_filenames: 支持的路由配置文件名列表
    """

    def __init__(self) -> None:
        """初始化路由解析器"""
        self.supported_filenames = ["index.js", "index.ts", "router.js", "router.ts"]

    def parse_file(self, file_path: str | Path) -> list[RouteInfo]:
        """
        解析单个路由配置文件,提取所有路由定义。

        Args:
            file_path: 路由配置文件路径

        Returns:
            解析出的路由信息列表(扁平化,包含嵌套路由)

        Raises:
            ParserError: 文件不存在或解析失败
        """
        path = Path(file_path)
        if not path.exists():
            raise ParserError(f"路由配置文件不存在: {file_path}")

        try:
            code = path.read_text(encoding="utf-8")
            return self.parse_code(code, source_file=str(path))
        except UnicodeDecodeError as e:
            raise ParserError(f"路由文件编码错误: {file_path}") from e
        except ParserError:
            raise
        except Exception as e:
            raise ParserError(f"解析路由文件失败: {file_path}, {e}") from e

    def parse_code(self, code: str, source_file: str = "") -> list[RouteInfo]:
        """
        解析路由配置 JavaScript 代码字符串。

        Args:
            code: JavaScript 代码内容
            source_file: 来源文件路径(仅用于记录)

        Returns:
            解析出的路由信息列表
        """
        tree = parse_javascript(code)
        root = tree.root_node

        routes: list[RouteInfo] = []

        # 查找包含路由数组的变量声明,如 const routes = [...]
        # 以及 new Router({ routes: [...] })
        for node in root.children:
            # 形式: const routes = [...] / export const routes = [...]
            if node.type == "lexical_declaration":
                found = self._extract_routes_from_declaration(node, source_file)
                routes.extend(found)
            elif node.type == "export_statement":
                # export const routes = [...]
                for child in node.children:
                    if child.type == "lexical_declaration":
                        found = self._extract_routes_from_declaration(child, source_file)
                        routes.extend(found)
                    # export default new Router({ routes: [...] })
                    elif child.type == "new_expression":
                        found = self._extract_routes_from_new_router(child, code, source_file)
                        routes.extend(found)

        logger.info(
            "路由解析完成 | source={} | routes={}",
            source_file or "<string>",
            len(routes),
        )
        return routes

    def _extract_routes_from_declaration(
        self,
        node: tree_sitter.Node,
        source_file: str,
    ) -> list[RouteInfo]:
        """从变量声明中提取路由数组"""
        routes: list[RouteInfo] = []
        for child in node.children:
            if child.type == "variable_declarator":
                # 找到数组
                for sub in child.children:
                    if sub.type == "array":
                        for item in sub.children:
                            if item.type == "object":
                                route = self._parse_route_object(item, source_file)
                                if route is not None:
                                    routes.append(route)
        return routes

    def _extract_routes_from_new_router(
        self,
        new_expr: tree_sitter.Node,
        code: str,
        source_file: str,
    ) -> list[RouteInfo]:
        """从 new Router({ routes }) 中提取路由配置"""
        routes: list[RouteInfo] = []
        # 找到 arguments 中的 object
        for child in new_expr.children:
            if child.type == "arguments":
                for arg in child.children:
                    if arg.type == "object":
                        # 查找 routes 属性
                        routes_array = self._find_property_value(arg, "routes")
                        if routes_array is not None and routes_array.type == "array":
                            for item in routes_array.children:
                                if item.type == "object":
                                    route = self._parse_route_object(item, source_file)
                                    if route is not None:
                                        routes.append(route)
                        # 形如 { routes } 的简写,需要从作用域查找(这里不深入)
        return routes

    def _parse_route_object(
        self,
        obj_node: tree_sitter.Node,
        source_file: str,
    ) -> RouteInfo | None:
        """
        解析单个路由对象 { path, name, component, meta, children }。

        Args:
            obj_node: tree-sitter object 节点
            source_file: 来源文件路径

        Returns:
            解析出的 RouteInfo,如果 path 为空则返回 None
        """
        path = self._get_string_property(obj_node, "path") or ""
        name = self._get_string_property(obj_node, "name") or ""
        component_path = self._get_component_path(obj_node)
        title = self._get_meta_title(obj_node)

        if not path:
            return None

        route = RouteInfo(
            path=path,
            name=name,
            title=title,
            component_path=component_path,
            source_file=source_file,
        )

        # 递归处理 children
        children_array = self._find_property_value(obj_node, "children")
        if children_array is not None and children_array.type == "array":
            for child_node in children_array.children:
                if child_node.type == "object":
                    child_route = self._parse_route_object(child_node, source_file)
                    if child_route is not None:
                        child_route.parent_path = path
                        route.children.append(child_route)

        return route

    def _get_meta_title(self, obj_node: tree_sitter.Node) -> str:
        """从 meta: { title: 'xxx' } 中提取 title"""
        meta_node = self._find_property_value(obj_node, "meta")
        if meta_node is None or meta_node.type != "object":
            return ""
        return self._get_string_property(meta_node, "title")

    def _get_component_path(self, obj_node: tree_sitter.Node) -> str:
        """
        提取组件路径,支持两种形式:
        1. component: Layout (标识符)
        2. component: () => import('@/views/xxx') (动态导入)
        3. component: '@/views/xxx' (字符串,少见)
        """
        comp_node = self._find_property_value(obj_node, "component")
        if comp_node is None:
            return ""

        # 形式 1: 标识符,如 component: Layout
        if comp_node.type == "identifier":
            return self._node_text(comp_node)

        # 形式 3: 字符串字面量
        if comp_node.type == "string":
            return self._node_text(comp_node).strip("'\"")

        # 形式 2: 箭头函数包含 import()
        if comp_node.type in ("arrow_function", "function"):
            text = self._node_text(comp_node)
            # 提取 import('...') 中的路径
            return self._extract_import_path(text)

        return ""

    def _extract_import_path(self, code: str) -> str:
        """从 import('...') 表达式中提取路径字符串"""
        # 简单正则:import('xxx') 或 import("xxx")
        import re
        match = re.search(r"""import\(\s*['"]([^'"]+)['"]\s*\)""", code)
        return match.group(1) if match else ""

    def _find_property_value(
        self,
        obj_node: tree_sitter.Node,
        key: str,
    ) -> tree_sitter.Node | None:
        """在 object 节点中查找指定 key 的 value 节点"""
        for child in obj_node.children:
            if child.type == "pair":
                # pair 结构: property_identifier : value
                key_node = None
                value_node = None
                for pair_child in child.children:
                    if pair_child.type == "property_identifier":
                        key_node = pair_child
                    elif pair_child.type not in (":", "property_identifier"):
                        value_node = pair_child
                if key_node is not None:
                    key_text = self._node_text(key_node)
                    if key_text == key:
                        return value_node
            # 处理 shorthand_property_identifier (如 { routes })
            elif child.type == "shorthand_property_identifier":
                if self._node_text(child) == key:
                    # 简写形式,无法深入解析,返回 None
                    return None
        return None

    def _get_string_property(self, obj_node: tree_sitter.Node, key: str) -> str:
        """从 object 节点中获取字符串类型属性的值"""
        value_node = self._find_property_value(obj_node, key)
        if value_node is None:
            return ""
        if value_node.type == "string":
            # 去除引号
            text = self._node_text(value_node)
            return text.strip("'\"")
        if value_node.type == "number":
            return self._node_text(value_node)
        return ""

    @staticmethod
    def _node_text(node: tree_sitter.Node) -> str:
        """获取节点的文本内容"""
        if node.text is None:
            return ""
        return node.text.decode("utf-8")
