"""Axios API 接口定义解析器模块。

本模块负责解析 Vue 2 项目中的 API 接口定义文件(通常在 src/api/ 目录下),
使用 tree-sitter 构建 JavaScript AST,提取:
- 函数名
- HTTP 方法
- 请求路径
- 参数

典型用法:
    >>> from src.parser.api_parser import APIParser
    >>> parser = APIParser()
    >>> apis = parser.parse_directory("src/api")
    >>> for api in apis:
    ...     print(api.function_name, api.method, api.url)
"""

from __future__ import annotations

import re
from pathlib import Path

import tree_sitter
from loguru import logger

from src.domain.exceptions import ParserError
from src.parser.models import APIInfo
from src.parser.ts_utils import parse_javascript


# ============================================================================
# APIParser
# ============================================================================

class APIParser:
    """
    Axios API 接口定义解析器。

    使用 tree-sitter 解析 JavaScript AST,从 API 定义文件中提取
    函数名、HTTP 方法、请求路径和参数。

    Attributes:
        api_dirs: 默认的 API 目录名列表
    """

    def __init__(self) -> None:
        """初始化 API 解析器"""
        self.api_dirs = ["api", "apis", "services"]

    def parse_directory(self, dir_path: str | Path) -> list[APIInfo]:
        """
        扫描整个 API 目录,解析所有接口定义文件。

        Args:
            dir_path: API 目录路径

        Returns:
            解析出的 API 信息列表
        """
        path = Path(dir_path)
        if not path.exists() or not path.is_dir():
            raise ParserError(f"API 目录不存在: {dir_path}")

        apis: list[APIInfo] = []
        for js_file in sorted(path.glob("*.js")):
            try:
                found = self.parse_file(js_file)
                apis.extend(found)
            except ParserError as e:
                logger.warning("解析 API 文件失败 | file={} | error={}", js_file, e)

        logger.info("API 解析完成 | dir={} | apis={}", dir_path, len(apis))
        return apis

    def parse_file(self, file_path: str | Path) -> list[APIInfo]:
        """
        解析单个 API 定义文件。

        Args:
            file_path: API 文件路径

        Returns:
            解析出的 API 信息列表

        Raises:
            ParserError: 文件不存在或解析失败
        """
        path = Path(file_path)
        if not path.exists():
            raise ParserError(f"API 文件不存在: {file_path}")

        try:
            code = path.read_text(encoding="utf-8")
            return self.parse_code(code, source_file=str(path))
        except UnicodeDecodeError as e:
            raise ParserError(f"API 文件编码错误: {file_path}") from e
        except ParserError:
            raise
        except Exception as e:
            raise ParserError(f"解析 API 文件失败: {file_path}, {e}") from e

    def parse_code(self, code: str, source_file: str = "") -> list[APIInfo]:
        """
        解析 API 定义 JavaScript 代码。

        支持两种常见形式:
        1. export function xxx(params) { return request({ url, method, ... }) }
        2. export const xxx = params => request({ url, method, ... })

        Args:
            code: JavaScript 代码内容
            source_file: 来源文件路径(用于记录)

        Returns:
            解析出的 API 信息列表
        """
        tree = parse_javascript(code)
        root = tree.root_node

        apis: list[APIInfo] = []

        for node in root.children:
            # 形式 1: export function xxx(params) { ... }
            if node.type == "export_statement":
                for child in node.children:
                    if child.type == "function_declaration":
                        api = self._parse_function_declaration(child, source_file)
                        if api is not None:
                            apis.append(api)
                    elif child.type == "lexical_declaration":
                        # export const xxx = ...
                        for sub in child.children:
                            if sub.type == "variable_declarator":
                                api = self._parse_variable_declarator(sub, source_file)
                                if api is not None:
                                    apis.append(api)
            # 形式 2: function xxx(params) { ... } (非 export,但可能在文件中)
            elif node.type == "function_declaration":
                api = self._parse_function_declaration(node, source_file)
                if api is not None:
                    apis.append(api)
            # 形式 3: const xxx = params => ...
            elif node.type == "lexical_declaration":
                for child in node.children:
                    if child.type == "variable_declarator":
                        api = self._parse_variable_declarator(child, source_file)
                        if api is not None:
                            apis.append(api)

        return apis

    def extract_api_calls_from_script(self, script_content: str) -> list[str]:
        """
        从 <script> 内容中提取 API 函数调用。

        匹配形如: getOrderList(params), createOrder(data)

        Args:
            script_content: <script> 标签内的 JavaScript 代码

        Returns:
            调用到的 API 函数名列表(去重)
        """
        # 匹配 functionCall( 模式,排除一些常见非 API 调用
        pattern = r"""(?:^|[^.\w])([A-Z]?[a-zA-Z][a-zA-Z0-9]*)\s*\("""
        matches = re.findall(pattern, script_content)

        # 过滤掉一些常见的非 API 调用
        excluded = {
            "if", "for", "while", "switch", "catch", "return", "throw",
            "function", "class", "new", "import", "export", "const", "let",
            "var", "this", "console", "JSON", "Math", "Date", "Promise",
            "setTimeout", "setInterval", "clearTimeout", "clearInterval",
            "require", "define", "computed", "watch", "methods", "data",
        }
        filtered = [m for m in matches if m not in excluded and len(m) > 1]

        # 保持去重且顺序
        return list(dict.fromkeys(filtered))

    # ========================================================================
    # 内部方法
    # ========================================================================

    def _parse_function_declaration(
        self,
        func_node: tree_sitter.Node,
        source_file: str,
    ) -> APIInfo | None:
        """解析 export function xxx(params) { return request({ ... }) }"""
        function_name = ""
        params_text = ""
        body_node = None

        for child in func_node.children:
            if child.type == "identifier":
                function_name = self._node_text(child)
            elif child.type == "formal_parameters":
                params_text = self._node_text(child)
            elif child.type == "statement_block":
                body_node = child

        if not function_name:
            return None

        # 从函数体中提取 request({ ... }) 调用
        method, url = self._extract_request_info(body_node)

        return APIInfo(
            function_name=function_name,
            method=method,
            url=url,
            params=params_text,
            source_file=source_file,
        )

    def _parse_variable_declarator(
        self,
        declarator: tree_sitter.Node,
        source_file: str,
    ) -> APIInfo | None:
        """解析 export const xxx = params => request({ ... })"""
        function_name = ""
        params_text = ""
        value_node = None

        for child in declarator.children:
            if child.type == "identifier":
                function_name = self._node_text(child)
            elif child.type == "formal_parameters":
                params_text = self._node_text(child)
            elif child.type in ("arrow_function", "function"):
                # 从箭头函数或函数表达式中提取参数和请求信息
                for sub in child.children:
                    if sub.type == "formal_parameters":
                        params_text = self._node_text(sub)
                value_node = child

        if not function_name:
            return None

        # 从函数体中提取 request({ ... }) 调用
        method, url = self._extract_request_info(value_node)

        return APIInfo(
            function_name=function_name,
            method=method,
            url=url,
            params=params_text,
            source_file=source_file,
        )

    def _extract_request_info(
        self,
        node: tree_sitter.Node | None,
    ) -> tuple[str, str]:
        """
        从节点中提取 request({ url, method }) 的信息。

        返回 (method, url) 元组。
        """
        if node is None:
            return "", ""

        text = self._node_text(node)

        # 查找 request({...}) 或 service({...}) 调用
        # 简单正则:匹配 request({ url: '...', method: '...' })
        url = ""
        method = ""

        url_match = re.search(r"""url:\s*['"]([^'"]+)['"]""", text)
        if url_match:
            url = url_match.group(1)

        method_match = re.search(r"""method:\s*['"]([^'"]+)['"]""", text)
        if method_match:
            method = method_match.group(1).lower()

        # 也支持模板字符串: url: `/api/xxx/${id}`
        if not url:
            url_match = re.search(r"""url:\s*`([^`]+)`""", text)
            if url_match:
                url = url_match.group(1)

        return method, url

    @staticmethod
    def _node_text(node: tree_sitter.Node) -> str:
        """获取节点的文本内容"""
        if node.text is None:
            return ""
        return node.text.decode("utf-8")
