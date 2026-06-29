"""Tree-sitter 工具模块。

封装 tree-sitter 的 Language 和 Parser 创建逻辑,供各解析器复用。
避免每个解析器重复初始化 Language 实例。
"""

from __future__ import annotations

import tree_sitter
import tree_sitter_javascript as tsjs


# 全局 JavaScript Language 实例(Language 构造成本较高)
_JS_LANGUAGE = tree_sitter.Language(tsjs.language())


def get_javascript_language() -> tree_sitter.Language:
    """获取全局 JavaScript Language 实例"""
    return _JS_LANGUAGE


def create_javascript_parser() -> tree_sitter.Parser:
    """创建一个新的 JavaScript Parser 实例(Parser 不是线程安全的,每次解析新建)"""
    return tree_sitter.Parser(_JS_LANGUAGE)


def parse_javascript(code: str | bytes) -> tree_sitter.Tree:
    """
    解析 JavaScript 代码为 AST。

    Args:
        code: JavaScript 代码,可以是 str 或 bytes

    Returns:
        解析后的 tree-sitter Tree 实例
    """
    if isinstance(code, str):
        code = code.encode("utf-8")
    parser = create_javascript_parser()
    return parser.parse(code)
