"""代码解析模块。

本模块实现 Vue 2 前端代码的自动化解析,从代码中提取操作知识:
- Vue Router 路由配置解析
- Element UI 组件提取(按钮/表单/表格/弹窗)
- Vuex Store 状态/操作解析
- Axios API 接口定义解析
- Vue 单文件组件(SFC)解析
- 知识文档构建

主要类:
- VueProjectParser: 项目级解析入口(推荐使用)
- VueSFCParser: 单文件组件解析
- RouterParser: 路由配置解析
- ComponentParser: Element UI 组件提取
- StoreParser: Vuex Store 解析
- APIParser: API 接口解析
- KnowledgeBuilder: 知识文档构建

典型用法:
    >>> from src.parser import VueProjectParser, KnowledgeBuilder
    >>> parser = VueProjectParser("path/to/vue-project")
    >>> parse_result = parser.parse()
    >>> builder = KnowledgeBuilder()
    >>> knowledge_items = builder.build(parse_result)
"""

from src.parser.api_parser import APIParser
from src.parser.builder import KnowledgeBuilder
from src.parser.component_parser import ComponentParser
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
    RouteInfo,
    SFCParseResult,
    StoreModuleInfo,
    TableColumn,
    TableInfo,
)
from src.parser.router_parser import RouterParser
from src.parser.script_analyzer import ScriptAnalyzer
from src.parser.store_parser import StoreParser
from src.parser.vue_parser import VueProjectParser, VueSFCParser

__all__ = [
    # 解析器
    "VueProjectParser",
    "VueSFCParser",
    "RouterParser",
    "ComponentParser",
    "StoreParser",
    "APIParser",
    "ScriptAnalyzer",
    "KnowledgeBuilder",
    # 数据模型
    "RouteInfo",
    "PageInfo",
    "ButtonInfo",
    "FormInfo",
    "FormField",
    "TableInfo",
    "TableColumn",
    "DialogInfo",
    "MethodInfo",
    "OperationStep",
    "OperationFlow",
    "StoreModuleInfo",
    "APIInfo",
    "SFCParseResult",
    "ParseResult",
]
