"""Script 区块分析器单元测试"""

from pathlib import Path

import pytest

from src.parser.script_analyzer import ScriptAnalyzer


class TestScriptAnalyzer:
    """ScriptAnalyzer 单元测试"""

    @pytest.fixture
    def analyzer(self) -> ScriptAnalyzer:
        return ScriptAnalyzer()

    # ====================================================================
    # 方法提取
    # ====================================================================

    def test_analyze_simple_methods(self, analyzer: ScriptAnalyzer) -> None:
        """测试提取简单 methods 定义"""
        script = """
        export default {
          methods: {
            handleCreate() {
              this.dialogVisible = true
            },
            async submitForm() {
              await this.$store.dispatch('order/create', this.form)
            }
          }
        }
        """
        methods = analyzer.analyze_methods(script)
        assert len(methods) == 2
        names = {m.name for m in methods}
        assert names == {"handleCreate", "submitForm"}

    def test_analyze_async_flag(self, analyzer: ScriptAnalyzer) -> None:
        """测试 async 标记识别"""
        script = """
        export default {
          methods: {
            async fetchData() { await this.loadData() },
            handleClick() { this.x = 1 }
          }
        }
        """
        methods = analyzer.analyze_methods(script)
        async_map = {m.name: m.async_ for m in methods}
        assert async_map["fetchData"] is True
        assert async_map["handleClick"] is False

    def test_analyze_dispatch_calls(self, analyzer: ScriptAnalyzer) -> None:
        """测试提取 dispatch 调用"""
        script = """
        export default {
          methods: {
            async loadData() {
              await this.$store.dispatch('order/fetchList')
              await this.$store.dispatch('user/getInfo')
            }
          }
        }
        """
        methods = analyzer.analyze_methods(script)
        assert len(methods) == 1
        assert set(methods[0].dispatched_actions) == {"order/fetchList", "user/getInfo"}

    def test_analyze_commit_calls(self, analyzer: ScriptAnalyzer) -> None:
        """测试提取 commit 调用"""
        script = """
        export default {
          methods: {
            update() {
              this.$store.commit('SET_LOADING', true)
            }
          }
        }
        """
        methods = analyzer.analyze_methods(script)
        assert methods[0].committed_mutations == ["SET_LOADING"]

    def test_analyze_api_calls(self, analyzer: ScriptAnalyzer) -> None:
        """测试提取 API 函数调用"""
        script = """
        import { getOrderList, createOrder } from '@/api/order'

        export default {
          methods: {
            async loadData() {
              const res = await getOrderList()
              this.data = res.data
            },
            async save() {
              await createOrder(this.form)
            }
          }
        }
        """
        methods = analyzer.analyze_methods(script)
        method_map = {m.name: m for m in methods}
        assert "getOrderList" in method_map["loadData"].called_apis
        assert "createOrder" in method_map["save"].called_apis

    def test_analyze_dialog_assignments(self, analyzer: ScriptAnalyzer) -> None:
        """测试提取弹窗可见性赋值"""
        script = """
        export default {
          methods: {
            openDialog() {
              this.createDialogVisible = true
            },
            closeDialog() {
              this.createDialogVisible = false
              this.editPopupVisible = false
            }
          }
        }
        """
        methods = analyzer.analyze_methods(script)
        method_map = {m.name: m for m in methods}
        assert "createDialogVisible" in method_map["openDialog"].referenced_dialogs
        dialogs_in_close = set(method_map["closeDialog"].referenced_dialogs)
        assert "createDialogVisible" in dialogs_in_close
        assert "editPopupVisible" in dialogs_in_close

    def test_analyze_method_calls(self, analyzer: ScriptAnalyzer) -> None:
        """测试提取方法调用链"""
        script = """
        export default {
          methods: {
            handleSearch() {
              this.loadData()
            },
            async loadData() {
              await this.fetchData()
            },
            async fetchData() {}
          }
        }
        """
        methods = analyzer.analyze_methods(script)
        method_map = {m.name: m for m in methods}
        assert "loadData" in method_map["handleSearch"].called_methods
        assert "fetchData" in method_map["loadData"].called_methods

    def test_analyze_empty_script(self, analyzer: ScriptAnalyzer) -> None:
        """测试空 script"""
        methods = analyzer.analyze_methods("")
        assert methods == []

    def test_analyze_no_methods(self, analyzer: ScriptAnalyzer) -> None:
        """测试没有 methods 的组件"""
        script = """
        export default {
          name: 'Test',
          data() { return {} }
        }
        """
        methods = analyzer.analyze_methods(script)
        assert methods == []
