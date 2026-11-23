"""Vue Router 解析器单元测试"""

from pathlib import Path

import pytest

from src.domain.exceptions import ParserError
from src.parser.router_parser import RouterParser


class TestRouterParser:
    """RouterParser 单元测试"""

    @pytest.fixture
    def parser(self) -> RouterParser:
        return RouterParser()

    # ====================================================================
    # 基础解析
    # ====================================================================

    def test_parse_simple_route(self, parser: RouterParser) -> None:
        """测试简单路由解析"""
        code = """
        const routes = [
          {
            path: '/user',
            name: 'User',
            component: () => import('@/views/user/index'),
            meta: { title: '用户管理' }
          }
        ]
        """
        routes = parser.parse_code(code)
        assert len(routes) == 1
        assert routes[0].path == "/user"
        assert routes[0].name == "User"
        assert routes[0].title == "用户管理"
        assert routes[0].component_path == "@/views/user/index"

    def test_parse_nested_routes(self, parser: RouterParser) -> None:
        """测试嵌套路由解析"""
        code = """
        const routes = [
          {
            path: '/order',
            component: Layout,
            meta: { title: '订单管理' },
            children: [
              {
                path: 'list',
                name: 'OrderList',
                component: () => import('@/views/order/list'),
                meta: { title: '订单列表' }
              },
              {
                path: 'detail/:id',
                name: 'OrderDetail',
                component: () => import('@/views/order/detail'),
                meta: { title: '订单详情' }
              }
            ]
          }
        ]
        """
        routes = parser.parse_code(code)
        assert len(routes) == 1
        parent = routes[0]
        assert parent.path == "/order"
        assert parent.title == "订单管理"
        assert parent.component_path == "Layout"
        assert len(parent.children) == 2

        child1 = parent.children[0]
        assert child1.path == "list"
        assert child1.full_path == "/order/list"
        assert child1.title == "订单列表"
        assert child1.component_path == "@/views/order/list"

        child2 = parent.children[1]
        assert child2.path == "detail/:id"
        assert child2.full_path == "/order/detail/:id"

    def test_parse_export_default_router(self, parser: RouterParser) -> None:
        """测试 export default new Router() 形式"""
        code = """
        const routes = [
          { path: '/a', meta: { title: 'A' }, component: () => import('@/views/a') }
        ]
        export default new Router({ routes })
        """
        routes = parser.parse_code(code)
        assert len(routes) == 1
        assert routes[0].path == "/a"

    def test_parse_empty_routes(self, parser: RouterParser) -> None:
        """测试空路由数组"""
        code = "const routes = []"
        routes = parser.parse_code(code)
        assert len(routes) == 0

    def test_parse_route_without_path(self, parser: RouterParser) -> None:
        """测试无 path 属性的路由(应被跳过)"""
        code = """
        const routes = [
          { name: 'NoPath', meta: { title: 'No Path' } }
        ]
        """
        routes = parser.parse_code(code)
        assert len(routes) == 0

    def test_parse_file(self, parser: RouterParser, sample_router_file: Path) -> None:
        """测试从文件解析"""
        routes = parser.parse_file(sample_router_file)
        assert len(routes) == 2
        assert routes[0].path == "/order"
        assert routes[1].path == "/user"

    def test_parse_file_not_exists(self, parser: RouterParser) -> None:
        """测试解析不存在的文件"""
        with pytest.raises(ParserError, match="不存在"):
            parser.parse_file("/non/existent/file.js")


class TestRouterParserModuleFormats:
    """模块化路由与 require() 组件解析

    回归保护: Vue Element Admin 类模板把路由拆分到 router/modules/*.js，
    每个文件导出单个根路由对象，并用 resolve => require([...], resolve)
    异步加载组件。旧解析器只支持数组 + import()，导致 900+ 个 vue 文件解析出 0 个页面。
    """

    @pytest.fixture
    def parser(self) -> RouterParser:
        return RouterParser()

    def test_single_object_declaration(self, parser: RouterParser) -> None:
        """const xxxRouter = { path, children } 应被解析为一条根路由"""
        code = """
        const businessRouter = {
          path: '/operators',
          component: Layout,
          meta: { title: '运营管理' },
          children: [
            { path: 'businessManage', name: 'businessManage', meta: { title: '商户管理' } }
          ]
        }
        """
        routes = parser.parse_code(code)

        assert len(routes) == 1
        assert routes[0].path == "/operators"
        assert routes[0].title == "运营管理"
        assert len(routes[0].children) == 1
        assert routes[0].children[0].title == "商户管理"

    def test_require_array_component(self, parser: RouterParser) -> None:
        """resolve => require(['@/pages/xxx'], resolve) 应提取出组件路径"""
        code = """
        const r = {
          path: 'businessManage',
          component: resolve => (require(['@/pages/business/businessManage'], resolve)),
          meta: { title: '商户管理' }
        }
        """
        routes = parser.parse_code(code)

        assert len(routes) == 1
        assert routes[0].component_path == "@/pages/business/businessManage"

    def test_require_string_component(self, parser: RouterParser) -> None:
        """require('@/pages/xxx') 字符串形式也应支持"""
        code = """
        const r = {
          path: 'foo',
          component: resolve => require('@/pages/foo/index'),
          meta: { title: 'Foo' }
        }
        """
        routes = parser.parse_code(code)

        assert routes[0].component_path == "@/pages/foo/index"

    def test_import_component_still_works(self, parser: RouterParser) -> None:
        """原有 import() 形式不应被破坏"""
        code = """
        const r = {
          path: 'bar',
          component: () => import('@/views/bar/index'),
          meta: { title: 'Bar' }
        }
        """
        routes = parser.parse_code(code)

        assert routes[0].component_path == "@/views/bar/index"
