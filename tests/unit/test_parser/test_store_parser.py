"""Vuex Store 解析器单元测试"""

from pathlib import Path

import pytest

from src.domain.exceptions import ParserError
from src.parser.store_parser import StoreParser


class TestStoreParser:
    """StoreParser 单元测试"""

    @pytest.fixture
    def parser(self) -> StoreParser:
        return StoreParser()

    # ====================================================================
    # 基础解析
    # ====================================================================

    def test_parse_basic_store(self, parser: StoreParser) -> None:
        """测试基础 Store 解析"""
        code = """
        export default {
          namespaced: true,
          state: {
            list: [],
            loading: false
          },
          actions: {
            async fetchList({ commit }) {},
            async create({ commit }, data) {}
          },
          mutations: {
            SET_LIST(state, list) {},
            SET_LOADING(state, loading) {}
          },
          getters: {
            list: state => state.list
          }
        }
        """
        module = parser.parse_code(code, module_name="test")

        assert module.name == "test"
        assert module.namespaced is True
        assert set(module.state_fields) == {"list", "loading"}
        assert set(module.actions) == {"fetchList", "create"}
        assert set(module.mutations) == {"SET_LIST", "SET_LOADING"}
        assert module.getters == ["list"]

    def test_parse_state_factory_function(self, parser: StoreParser) -> None:
        """测试 state 工厂函数形式"""
        code = """
        export default {
          state: () => ({
            count: 0,
            items: []
          }),
          mutations: {},
          actions: {}
        }
        """
        module = parser.parse_code(code)
        assert set(module.state_fields) == {"count", "items"}

    def test_parse_module_exports(self, parser: StoreParser) -> None:
        """测试 module.exports 形式"""
        code = """
        module.exports = {
          namespaced: true,
          state: { value: 0 },
          actions: { inc({ commit }) {} },
          mutations: { INC(state) {} }
        }
        """
        module = parser.parse_code(code)
        assert module.namespaced is True
        assert module.state_fields == ["value"]

    def test_parse_variable_export(self, parser: StoreParser) -> None:
        """测试 const xxx = {...}; export default xxx 形式"""
        code = """
        const order = {
          namespaced: true,
          state: { list: [] },
          actions: { fetch({ commit }) {} },
          mutations: { SET_LIST() {} }
        }
        export default order
        """
        module = parser.parse_code(code)
        assert module.namespaced is True
        assert module.state_fields == ["list"]
        assert module.actions == ["fetch"]

    def test_parse_directory(self, parser: StoreParser, sample_store_dir: Path) -> None:
        """测试从目录解析"""
        modules = parser.parse_directory(sample_store_dir)
        # 应该解析出 order 和 user 两个模块
        names = {m.name for m in modules}
        assert "order" in names
        assert "user" in names

    def test_parse_directory_not_exists(self, parser: StoreParser) -> None:
        """测试解析不存在的目录"""
        with pytest.raises(ParserError, match="不存在"):
            parser.parse_directory("/non/existent/dir")

    def test_parse_file_not_exists(self, parser: StoreParser) -> None:
        """测试解析不存在的文件"""
        with pytest.raises(ParserError, match="不存在"):
            parser.parse_file("/non/existent/file.js")

    # ====================================================================
    # dispatch/commit 提取
    # ====================================================================

    def test_extract_dispatches(self, parser: StoreParser) -> None:
        """测试从 script 中提取 dispatch 调用"""
        script = """
        methods: {
          async load() {
            await this.$store.dispatch('order/fetchList')
            await this.$store.dispatch('user/getInfo')
          }
        }
        """
        dispatches = parser.extract_dispatches_from_script(script)
        assert "order/fetchList" in dispatches
        assert "user/getInfo" in dispatches

    def test_extract_commits(self, parser: StoreParser) -> None:
        """测试从 script 中提取 commit 调用"""
        script = """
        methods: {
          update() {
            this.$store.commit('SET_LOADING', true)
          }
        }
        """
        commits = parser.extract_commits_from_script(script)
        assert "SET_LOADING" in commits

    def test_extract_dispatches_dedup(self, parser: StoreParser) -> None:
        """测试 dispatch 调用去重"""
        script = """
        dispatch('order/fetchList')
        dispatch('order/fetchList')
        dispatch('order/fetchList')
        """
        dispatches = parser.extract_dispatches_from_script(script)
        assert dispatches == ["order/fetchList"]
