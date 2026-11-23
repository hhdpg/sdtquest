"""Axios API 解析器单元测试"""

from pathlib import Path

import pytest

from src.domain.exceptions import ParserError
from src.parser.api_parser import APIParser


class TestAPIParser:
    """APIParser 单元测试"""

    @pytest.fixture
    def parser(self) -> APIParser:
        return APIParser()

    # ====================================================================
    # 基础解析
    # ====================================================================

    def test_parse_function_declaration(self, parser: APIParser) -> None:
        """测试 export function 形式"""
        code = """
        import request from '@/utils/request'

        export function getOrderList(params) {
          return request({
            url: '/api/orders',
            method: 'get',
            params
          })
        }
        """
        apis = parser.parse_code(code)
        assert len(apis) == 1
        assert apis[0].function_name == "getOrderList"
        assert apis[0].method == "get"
        assert apis[0].url == "/api/orders"

    def test_parse_arrow_function(self, parser: APIParser) -> None:
        """测试 export const = arrow 形式"""
        code = """
        export const deleteOrder = (id) => request({
          url: `/api/orders/${id}`,
          method: 'delete'
        })
        """
        apis = parser.parse_code(code)
        assert len(apis) == 1
        assert apis[0].function_name == "deleteOrder"
        assert apis[0].method == "delete"
        assert apis[0].url == "/api/orders/${id}"

    def test_parse_multiple_apis(self, parser: APIParser) -> None:
        """测试多个 API 解析"""
        code = """
        export function getOrders(params) {
          return request({ url: '/api/orders', method: 'get', params })
        }
        export function createOrder(data) {
          return request({ url: '/api/orders', method: 'post', data })
        }
        export function deleteOrder(id) {
          return request({ url: '/api/orders/' + id, method: 'delete' })
        }
        """
        apis = parser.parse_code(code)
        assert len(apis) == 3
        assert apis[0].method == "get"
        assert apis[1].method == "post"
        assert apis[2].method == "delete"

    def test_parse_directory(self, parser: APIParser, sample_api_dir: Path) -> None:
        """测试从目录解析"""
        apis = parser.parse_directory(sample_api_dir)
        assert len(apis) >= 2
        function_names = {a.function_name for a in apis}
        assert "getOrderList" in function_names
        assert "getUserList" in function_names

    def test_parse_directory_not_exists(self, parser: APIParser) -> None:
        """测试解析不存在的目录"""
        with pytest.raises(ParserError, match="不存在"):
            parser.parse_directory("/non/existent/dir")

    # ====================================================================
    # API 调用提取
    # ====================================================================

    def test_extract_api_calls_from_script(self, parser: APIParser) -> None:
        """测试从 script 提取 API 调用"""
        script = """
        import { getOrderList, createOrder } from '@/api/order'

        export default {
          methods: {
            async load() {
              const res = await getOrderList()
              await createOrder(this.form)
            }
          }
        }
        """
        calls = parser.extract_api_calls_from_script(script)
        assert "getOrderList" in calls
        assert "createOrder" in calls

    def test_extract_api_calls_excludes_builtins(self, parser: APIParser) -> None:
        """测试 API 调用提取排除内置函数"""
        script = """
        console.log('test')
        JSON.parse('{}')
        Promise.resolve()
        setTimeout(() => {}, 100)
        """
        calls = parser.extract_api_calls_from_script(script)
        assert "console" not in calls
        assert "JSON" not in calls
        assert "Promise" not in calls
        assert "setTimeout" not in calls


class TestAPIParserTemplateAndNesting:
    """模板字符串 URL 与嵌套目录

    回归保护: 实际项目用 const base = `${process.env.X}/api` 定义前缀，
    接口 URL 写成 url: `${base}/order/query`；且 API 文件按业务域放在
    子目录（src/api/biz/order.js）。旧实现只 glob 顶层 *.js 且不展开变量，
    导致 800+ 个接口解析出 0 条。
    """

    @pytest.fixture
    def parser(self) -> APIParser:
        return APIParser()

    def test_template_variable_resolved(self, parser: APIParser) -> None:
        """模板字符串中的常量应被展开"""
        code = """
        const baseUrl = `${process.env.VUE_APP_SYS_API}/hd-united-store/api`
        export function queryOrder(params) {
          return request({
            url: `${baseUrl}/order/batch/query`,
            method: 'get',
            params
          })
        }
        """
        apis = parser.parse_code(code)

        assert len(apis) == 1
        assert apis[0].function_name == "queryOrder"
        assert apis[0].method == "get"
        assert apis[0].url == "{ENV}/hd-united-store/api/order/batch/query"

    def test_const_without_request_not_parsed(self, parser: APIParser) -> None:
        """纯字符串常量不应被当成接口"""
        code = """
        const baseUrl = `${process.env.X}/api`
        const headers = { 'Content-Type': 'application/json' }
        export function queryUser() {
          return request({ url: `${baseUrl}/user/info`, method: 'POST' })
        }
        """
        apis = parser.parse_code(code)

        names = [a.function_name for a in apis]
        assert "queryUser" in names
        assert "baseUrl" not in names
        assert "headers" not in names

    def test_directory_recursive(self, parser: APIParser, tmp_path: Path) -> None:
        """应递归扫描子目录中的 API 文件"""
        sub = tmp_path / "biz"
        sub.mkdir()
        (sub / "order.js").write_text(
            "export function getOrder(p) {\n"
            "  return request({ url: '/api/order', method: 'get', params: p })\n"
            "}\n",
            encoding="utf-8",
        )

        apis = parser.parse_directory(tmp_path)

        assert len(apis) == 1
        assert apis[0].function_name == "getOrder"
