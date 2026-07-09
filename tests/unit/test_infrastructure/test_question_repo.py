"""SQLite 问题仓储单元测试模块。

测试 SQLiteQuestionRepository 的 CRUD 操作。
"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.domain.enums import AnswerStatus, QuestionCategory
from src.domain.models import Answer, Question
from src.infrastructure.database import DatabaseManager
from src.infrastructure.repositories.question_repo import SQLiteQuestionRepository


@pytest.fixture
def db_and_repo(tmp_path):
    """创建数据库和仓储"""
    db_path = str(tmp_path / "test.db")
    # 重置单例以确保干净的测试环境
    DatabaseManager.reset()
    db = DatabaseManager(db_path=db_path)
    db.initialize_tables()
    repo = SQLiteQuestionRepository(db_manager=db)
    yield db, repo
    DatabaseManager.reset()


def make_question(
    qid: str = "q1",
    text: str = "测试问题",
    category: QuestionCategory = QuestionCategory.OPERATION_GUIDE,
    created_at: datetime | None = None,
) -> Question:
    """创建测试 Question"""
    return Question(
        id=qid,
        text=text,
        sender_id="user_test",
        conversation_id="conv_test",
        category=category,
        created_at=created_at or datetime.now(),
    )


def make_answer(
    aid: str = "q1",
    qid: str = "q1",
    status: AnswerStatus = AnswerStatus.SUCCESS,
    confidence: float = 0.8,
    category: QuestionCategory = QuestionCategory.OPERATION_GUIDE,
) -> Answer:
    """创建测试 Answer"""
    return Answer(
        id=aid,
        question_id=qid,
        text="这是回答",
        sources=["来源1"],
        confidence=confidence,
        status=status,
        category=category,
    )


class TestSQLiteQuestionRepoSave:
    """保存测试"""

    def test_save_success(self, db_and_repo):
        """测试成功保存"""
        db, repo = db_and_repo
        q = make_question()
        a = make_answer()

        repo.save(q, a)

        # 验证能查询到
        result = repo.find_by_id(a.id)
        assert result is not None
        saved_q, saved_a = result
        assert saved_q.text == "测试问题"
        assert saved_a.text == "这是回答"

    def test_save_multiple(self, db_and_repo):
        """测试保存多条"""
        db, repo = db_and_repo
        for i in range(3):
            repo.save(make_question(qid=f"q{i}"), make_answer(aid=f"q{i}", qid=f"q{i}"))

        records = repo.find_recent(days=1)
        assert len(records) == 3


class TestSQLiteQuestionRepoQuery:
    """查询测试"""

    def test_find_recent_empty(self, db_and_repo):
        """测试空库查询"""
        db, repo = db_and_repo
        records = repo.find_recent(days=7)
        assert records == []

    def test_find_recent_with_data(self, db_and_repo):
        """测试有数据时查询"""
        db, repo = db_and_repo
        repo.save(make_question(qid="q1"), make_answer(aid="q1"))
        records = repo.find_recent(days=1)
        assert len(records) == 1

    def test_find_unanswered(self, db_and_repo):
        """测试查询未回答问题"""
        db, repo = db_and_repo
        repo.save(make_question(qid="q1"), make_answer(aid="q1", status=AnswerStatus.SUCCESS))
        repo.save(make_question(qid="q2"), make_answer(aid="q2", status=AnswerStatus.NO_MATCH))
        repo.save(make_question(qid="q3"), make_answer(aid="q3", status=AnswerStatus.ERROR))

        unanswered = repo.find_unanswered(days=7)
        assert len(unanswered) == 2

    def test_count_by_category(self, db_and_repo):
        """测试按分类统计"""
        db, repo = db_and_repo
        repo.save(
            make_question(qid="q1", category=QuestionCategory.OPERATION_GUIDE),
            make_answer(aid="q1", category=QuestionCategory.OPERATION_GUIDE),
        )
        repo.save(
            make_question(qid="q2", category=QuestionCategory.OPERATION_GUIDE),
            make_answer(aid="q2", category=QuestionCategory.OPERATION_GUIDE),
        )
        repo.save(
            make_question(qid="q3", category=QuestionCategory.ANOMALY_TROUBLESHOOT),
            make_answer(aid="q3", category=QuestionCategory.ANOMALY_TROUBLESHOOT),
        )

        counts = repo.count_by_category(days=7)
        assert counts[QuestionCategory.OPERATION_GUIDE] == 2
        assert counts[QuestionCategory.ANOMALY_TROUBLESHOOT] == 1

    def test_get_top_questions(self, db_and_repo):
        """测试高频问题"""
        db, repo = db_and_repo
        # 保存相同问题多次
        for i in range(3):
            repo.save(make_question(qid=f"q{i}", text="相同问题"), make_answer(aid=f"q{i}"))
        repo.save(make_question(qid="q3", text="不同问题"), make_answer(aid="q3"))

        top = repo.get_top_questions(days=7, limit=5)
        assert len(top) == 2
        assert top[0][0] == "相同问题"
        assert top[0][1] == 3


class TestSQLiteQuestionRepoDailySummary:
    """每日汇总保存测试"""

    def test_save_daily_summary(self, db_and_repo):
        """测试保存每日汇总"""
        db, repo = db_and_repo
        today = datetime.now().strftime("%Y-%m-%d")

        repo.save_daily_summary(
            date_str=today,
            category="operation_guide",
            question_count=10,
            top_questions_json=json.dumps([{"question": "测试", "count": 5}]),
        )

        # 验证写入
        cursor = db.execute(
            "SELECT * FROM daily_summary WHERE date = ? AND category = ?",
            (today, "operation_guide"),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["question_count"] == 10

    def test_save_daily_summary_upsert(self, db_and_repo):
        """测试 UPSERT 幂等性"""
        db, repo = db_and_repo
        today = datetime.now().strftime("%Y-%m-%d")

        repo.save_daily_summary(today, "operation_guide", 10, "[]")
        repo.save_daily_summary(today, "operation_guide", 20, "[]")  # 覆盖

        cursor = db.execute(
            "SELECT question_count FROM daily_summary WHERE date = ? AND category = ?",
            (today, "operation_guide"),
        )
        row = cursor.fetchone()
        assert row["question_count"] == 20  # 应该是更新的值


class TestSQLiteQuestionRepoConversion:
    """数据转换测试"""

    def test_row_to_item_preserves_sources(self, db_and_repo):
        """测试保存和查询保留 sources"""
        db, repo = db_and_repo
        a = make_answer()
        a.sources = ["来源A", "来源B"]
        repo.save(make_question(qid="q1"), a)

        _, saved_a = repo.find_by_id("q1")
        assert saved_a.sources == ["来源A", "来源B"]

    def test_row_to_item_handles_unknown_category(self, db_and_repo):
        """测试未知分类不抛出异常"""
        db, repo = db_and_repo
        # 直接插入未知分类
        db.execute(
            """
            INSERT INTO question_records
            (id, question, answer, category, sender_id, conversation_id, confidence, status, sources, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("q_unknown", "问题", "回答", "unknown_category", "user", "conv", 0.5, "success", "[]", datetime.now().isoformat()),
        )
        db.commit()

        result = repo.find_by_id("q_unknown")
        # 应该返回 GENERAL 作为默认分类
        assert result is not None
        _, a = result
        assert a.category == QuestionCategory.GENERAL
