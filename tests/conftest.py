"""pytest 全局 fixture 模块。

提供所有测试共用的 fixture,包括:
- sample_vue_project 路径 fixture
- Mock Ollama / 钉钉 API
- 临时 SQLite / ChromaDB
- 内存数据库
"""

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.enums import AnswerStatus, KnowledgeType, QuestionCategory
from src.domain.models import Answer, KnowledgeItem, Message, Question
from src.domain.ports import GenerateOptions


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


# ============================================================================
# 事件循环 fixture
# ============================================================================

@pytest.fixture
def event_loop():
    """为每个测试创建新的事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# 测试数据 fixtures
# ============================================================================

@pytest.fixture
def sample_question() -> Question:
    """创建示例 Question 对象"""
    return Question(
        id="q_test_001",
        text="如何创建订单?",
        sender_id="user_test",
        conversation_id="conv_test",
        category=QuestionCategory.OPERATION_GUIDE,
    )


@pytest.fixture
def sample_answer() -> Answer:
    """创建示例 Answer 对象"""
    return Answer(
        id="a_test_001",
        question_id="q_test_001",
        text="在订单管理页面点击新建按钮即可创建订单。",
        sources=["订单管理 - 新建订单"],
        confidence=0.85,
        category=QuestionCategory.OPERATION_GUIDE,
        status=AnswerStatus.SUCCESS,
    )


@pytest.fixture
def sample_knowledge_items() -> list[KnowledgeItem]:
    """创建示例 KnowledgeItem 列表"""
    return [
        KnowledgeItem(
            id="k_001",
            type=KnowledgeType.BUTTON,
            title="新建订单",
            content="在订单管理页面点击右上角「新建订单」按钮，填写订单信息后提交。",
            page_name="订单管理",
            page_path="/order-management",
            source_file="src/views/order/list.vue",
            tags=["订单", "创建"],
        ),
        KnowledgeItem(
            id="k_002",
            type=KnowledgeType.PAGE,
            title="订单管理页面",
            content="订单管理页面用于查看和管理所有订单。",
            page_name="订单管理",
            page_path="/order-management",
            tags=["订单"],
        ),
    ]


@pytest.fixture
def sample_messages() -> list[Message]:
    """创建示例消息列表"""
    return [
        Message(role="user", content="如何创建订单?"),
        Message(role="assistant", content="点击新建按钮即可。"),
    ]


# ============================================================================
# Mock fixtures
# ============================================================================

@pytest.fixture
def mock_llm() -> AsyncMock:
    """Mock LLM 客户端"""
    llm = AsyncMock()
    llm.generate = AsyncMock(return_value="这是 LLM 生成的答案。")
    llm.generate_stream = AsyncMock()
    llm.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3] * 341])
    return llm


@pytest.fixture
def mock_vectorstore() -> AsyncMock:
    """Mock 向量存储"""
    store = AsyncMock()
    store.add = AsyncMock()
    store.search = AsyncMock(return_value=[])
    store.delete = AsyncMock()
    store.clear = AsyncMock()
    store.count = AsyncMock(return_value=0)
    return store


@pytest.fixture
def mock_question_repo() -> MagicMock:
    """Mock 问题仓储"""
    repo = MagicMock()
    repo.save = MagicMock()
    repo.find_recent = MagicMock(return_value=[])
    repo.count_by_category = MagicMock(return_value={})
    repo.find_unanswered = MagicMock(return_value=[])
    repo.get_top_questions = MagicMock(return_value=[])
    repo.save_daily_summary = MagicMock()
    return repo


@pytest.fixture
def mock_classifier() -> AsyncMock:
    """Mock 问题分类器"""
    classifier = AsyncMock()
    classifier.classify = AsyncMock(return_value=QuestionCategory.OPERATION_GUIDE)
    return classifier


@pytest.fixture
def mock_session_manager() -> MagicMock:
    """Mock 会话管理器"""
    manager = MagicMock()
    manager.get_history = MagicMock(return_value=[])
    return manager


# ============================================================================
# 临时目录 / 数据库 fixtures
# ============================================================================

@pytest.fixture
def temp_db_path(tmp_path: Path) -> str:
    """创建临时 SQLite 数据库路径"""
    return str(tmp_path / "test_analytics.db")


@pytest.fixture
def temp_chroma_dir(tmp_path: Path) -> str:
    """创建临时 ChromaDB 持久化目录"""
    return str(tmp_path / "test_chroma_db")


# ============================================================================
# 环境隔离 fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def isolate_env(monkeypatch, tmp_path):
    """
    自动隔离测试环境变量。

    重定向所有文件路径到临时目录，避免影响真实数据。
    """
    monkeypatch.setenv("ANALYTICS_DB_PATH", str(tmp_path / "analytics.db"))
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path / "chroma_db"))
    monkeypatch.setenv("DINGTALK_APP_KEY", "test_key_for_testing")
    monkeypatch.setenv("DINGTALK_APP_SECRET", "test_secret_for_testing")
