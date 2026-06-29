"""pytest 全局 fixture 模块。

提供所有测试共用的 fixture,包括:
- sample_vue_project 路径 fixture
- Mock Ollama / 钉钉 API
- 临时目录等
"""

from pathlib import Path

import pytest


# ============================================================================
# Fixture 路径
# ============================================================================

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """返回测试 fixture 根目录"""
    return FIXTURES_DIR


@pytest.fixture
def sample_vue_project() -> Path:
    """返回模拟 Vue 2 项目的根目录"""
    return FIXTURES_DIR / "sample_vue_project"


@pytest.fixture
def sample_router_file(sample_vue_project: Path) -> Path:
    """返回路由配置文件路径"""
    return sample_vue_project / "src" / "router" / "index.js"


@pytest.fixture
def sample_order_list_vue(sample_vue_project: Path) -> Path:
    """返回订单列表页 Vue 文件路径"""
    return sample_vue_project / "src" / "views" / "order" / "list.vue"


@pytest.fixture
def sample_store_dir(sample_vue_project: Path) -> Path:
    """返回 Store 目录路径"""
    return sample_vue_project / "src" / "store"


@pytest.fixture
def sample_api_dir(sample_vue_project: Path) -> Path:
    """返回 API 目录路径"""
    return sample_vue_project / "src" / "api"
