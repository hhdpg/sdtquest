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
